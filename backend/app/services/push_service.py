import html
import json
import time
import uuid
from datetime import UTC, datetime

from backend.app.models.push_channel import PushChannel
from backend.app.models.push_log import PushLog
from backend.app.schemas.push import PushMessageRequest


class PushService:
    """核心推送服务：通道选择、重试、降级、日志记录。"""

    def __init__(self, db, feishu_client=None, telegram_client=None):
        self.db = db
        self.feishu = feishu_client
        self.telegram = telegram_client

    def send(self, message: PushMessageRequest) -> str:
        """提交推送请求，同步执行发送，返回 message_id。"""
        message_id = str(uuid.uuid4())

        log = PushLog(
            message_id=message_id,
            message_type=message.message_type,
            channel="unknown",
            status="pending",
        )
        self.db.add(log)
        self.db.commit()

        self._execute_send(message_id, message)
        return message_id

    def _execute_send(self, message_id: str, message: PushMessageRequest):
        """同步执行发送逻辑：通道检查 → 主通道尝试 → 重试 → 降级 → 日志更新。"""
        start_time = time.perf_counter()

        # 格式化内容
        content = self._format_content(message)

        # 检查通道状态
        channel_status = self._get_channel_status("feishu")

        primary_result = None
        fallback_result = None
        used_channel = None

        if channel_status == "active":
            # 尝试主通道（飞书），最多重试 2 次
            primary_result = self._try_channel("feishu", content, max_retries=2)
            if primary_result and primary_result["success"]:
                used_channel = "feishu"

        # 主通道失败或 degraded，尝试 Telegram
        if used_channel is None and self.telegram is not None:
            tg_status = self._get_channel_status("telegram")
            if tg_status != "unavailable":
                fallback_result = self._try_channel("telegram", content, max_retries=0)
                if fallback_result and fallback_result["success"]:
                    used_channel = "telegram"

        # 双通道均失败，更新失败日志
        elapsed_ms = int((time.perf_counter() - start_time) * 1000)
        final_result = (
            fallback_result
            if fallback_result is not None
            else primary_result
        )
        self._update_log(
            message_id, used_channel, primary_result, fallback_result, elapsed_ms, channel_status
        )

        # 更新通道失败计数
        if primary_result and not primary_result["success"]:
            self._record_channel_failure("feishu", primary_result.get("error_type"))
        if fallback_result and not fallback_result["success"]:
            self._record_channel_failure("telegram", fallback_result.get("error_type"))

    def _try_channel(self, channel: str, content, max_retries: int = 2) -> dict | None:
        """尝试通过指定通道发送，支持重试。"""
        client = self.feishu if channel == "feishu" else self.telegram
        if client is None:
            return None

        last_result = None
        for attempt in range(max_retries + 1):
            if attempt > 0:
                time.sleep(0.5 * (2 ** (attempt - 1)))
            if channel == "feishu":
                last_result = client.send_card(content)
            else:
                last_result = client.send_message(self._content_to_text(content))

            if last_result["success"]:
                return last_result

        return last_result

    def _get_channel_status(self, channel_name: str) -> str:
        """查询通道状态，默认 active。"""
        record = self.db.get(PushChannel, channel_name)
        if record is None:
            return "active"
        return record.status

    def _update_log(
        self,
        message_id: str,
        used_channel: str | None,
        primary_result: dict | None,
        fallback_result: dict | None,
        elapsed_ms: int,
        primary_status: str,
    ):
        """更新推送日志状态。"""
        log = (
            self.db.query(PushLog)
            .filter(PushLog.message_id == message_id)
            .first()
        )
        if log is None:
            return

        log.elapsed_ms = elapsed_ms

        final_result = fallback_result if fallback_result is not None else primary_result

        if used_channel is not None and final_result and final_result["success"]:
            log.channel = used_channel
            # 主通道 active 但调用失败后降级到 Telegram → fallback
            # 主通道 degraded/unavailable 时 Telegram 成功 → sent
            if used_channel == "telegram" and primary_status == "active":
                log.status = "fallback"
            else:
                log.status = "sent"
            self._reset_channel_success(used_channel)
        else:
            log.status = "failed"
            # 双通道均失败时，优先使用主通道错误信息
            if primary_result and not primary_result["success"]:
                log.error_reason = primary_result.get("error_message", "Unknown error")
            elif fallback_result and not fallback_result["success"]:
                log.error_reason = fallback_result.get("error_message", "Unknown error")
            else:
                log.error_reason = "No available channel"

        self.db.commit()

    def _record_channel_failure(self, channel_name: str, error_type: str | None = None):
        """记录通道失败，连续失败过多则标记为 degraded/unavailable。

        使用原子 UPDATE 避免并发 read-modify-write 丢失更新。
        """
        from sqlalchemy import update

        now = datetime.now(UTC).replace(tzinfo=None)

        # 先尝试原子 UPDATE（记录已存在）
        stmt = (
            update(PushChannel)
            .where(PushChannel.name == channel_name)
            .values(
                consecutive_failures=PushChannel.consecutive_failures + 1,
                updated_at=now,
            )
        )
        if error_type == "rate_limited":
            stmt = stmt.values(rate_limited=True)

        result = self.db.execute(stmt)
        self.db.commit()

        if result.rowcount == 0:
            # 记录不存在，尝试 INSERT（可能与其他线程竞态）
            record = PushChannel(
                name=channel_name,
                status="active",
                consecutive_failures=1,
                rate_limited=(error_type == "rate_limited"),
                updated_at=now,
            )
            self.db.add(record)
            try:
                self.db.commit()
            except Exception:
                self.db.rollback()
                # 其他线程已插入，回退为原子 UPDATE
                stmt = (
                    update(PushChannel)
                    .where(PushChannel.name == channel_name)
                    .values(
                        consecutive_failures=PushChannel.consecutive_failures + 1,
                        updated_at=now,
                    )
                )
                if error_type == "rate_limited":
                    stmt = stmt.values(rate_limited=True)
                self.db.execute(stmt)
                self.db.commit()

        # 更新状态阈值（基于已准确的 consecutive_failures）
        record = self.db.get(PushChannel, channel_name)
        if record is not None:
            new_status = record.status
            if record.consecutive_failures >= 5:
                new_status = "unavailable"
            elif record.consecutive_failures >= 3:
                new_status = "degraded"
            if new_status != record.status:
                record.status = new_status
                self.db.commit()

    def _reset_channel_success(self, channel_name: str):
        """通道成功发送后重置失败计数和限流标记。

        使用原子 UPDATE 避免并发 read-modify-write。
        """
        from sqlalchemy import update

        now = datetime.now(UTC).replace(tzinfo=None)

        stmt = (
            update(PushChannel)
            .where(PushChannel.name == channel_name)
            .values(
                consecutive_failures=0,
                rate_limited=False,
                status="active",
                updated_at=now,
            )
        )
        self.db.execute(stmt)
        self.db.commit()

    def _mark_failed(self, message_id: str):
        """将 pending 日志标记为 failed（异常兜底）。"""
        log = (
            self.db.query(PushLog)
            .filter(PushLog.message_id == message_id)
            .first()
        )
        if log is not None:
            log.status = "failed"
            log.error_reason = "Async execution exception"
            self.db.commit()

    # ---------- 格式化方法 (T7/T8) ----------

    def _format_content(self, message: PushMessageRequest) -> dict:
        """将推送请求格式化为卡片/文本内容。"""
        if message.message_type == "alert":
            content = self._format_alert_content(message.content)
        elif message.message_type == "briefing":
            content = self._format_briefing_content(message.content)
        else:
            content = message.content

        # JSON 预检查：确保内容可被序列化
        try:
            json.dumps(content, ensure_ascii=False)
        except (TypeError, ValueError):
            content = {"_type": "raw", "error": "Content serialization failed"}
        return content

    def _format_alert_content(self, content: dict) -> dict:
        """预警内容结构化。"""
        return {
            "_type": "alert",
            "stock_code": content.get("stock_code", ""),
            "stock_name": content.get("stock_name", ""),
            "price": content.get("price", ""),
            "change_pct": content.get("change_pct", ""),
            "condition": content.get("condition", ""),
            "triggered_at": content.get("triggered_at", ""),
            "level": content.get("level", "watch"),
        }

    def _format_briefing_content(self, content: dict) -> dict:
        """简报内容结构化。"""
        return {
            "_type": "briefing",
            "date": content.get("date", ""),
            "market_indices": content.get("market_indices", {}),
            "top_movers": content.get("top_movers", []),
        }

    def _content_to_text(self, content: dict) -> str:
        """将结构化内容转换为 Telegram 纯文本。"""
        msg_type = content.get("_type")
        if msg_type == "alert":
            text = self._format_alert_text(content)
        elif msg_type == "briefing":
            text = self._format_briefing_text(content)
        else:
            lines = []
            for key, value in content.items():
                if not key.startswith("_"):
                    lines.append(f"{key}: {value}")
            text = "\n".join(lines) if lines else "推送消息"

        return self._truncate_text(text, max_length=4000)

    def _format_alert_text(self, content: dict) -> str:
        """预警 Telegram 文本格式（HTML 转义用户输入）。"""
        level_emoji = "🔴" if content.get("level") == "alert" else "🔵"
        return (
            f"{level_emoji} 预警提醒\n"
            f"股票: {html.escape(str(content.get('stock_name', '')))}({html.escape(str(content.get('stock_code', '')))})\n"
            f"当前价格: {html.escape(str(content.get('price', '')))}\n"
            f"涨跌幅: {html.escape(str(content.get('change_pct', '')))}%\n"
            f"触发条件: {html.escape(str(content.get('condition', '')))}\n"
            f"触发时间: {html.escape(str(content.get('triggered_at', '')))}"
        )

    def _format_briefing_text(self, content: dict) -> str:
        """简报 Telegram 文本格式（HTML 转义用户输入）。"""
        date = html.escape(str(content.get("date", "")))
        indices = content.get("market_indices", {})
        top_movers = content.get("top_movers", [])

        lines = [f"📊 早盘简报 {date}", ""]
        lines.append("【大盘指数】")
        for name, value in indices.items():
            lines.append(f"  {html.escape(str(name))}: {html.escape(str(value))}")
        lines.append("")
        lines.append("【异动 TOP 3】")
        for i, mover in enumerate(top_movers[:3], 1):
            lines.append(
                f"  {i}. {html.escape(str(mover.get('name', '')))}"
                f"({html.escape(str(mover.get('code', '')))}): "
                f"{html.escape(str(mover.get('change_pct', '')))}%"
            )
        return "\n".join(lines)

    # ---------- 截断方法 (T9) ----------

    def _truncate_text(self, text: str, max_length: int = 4000) -> str:
        """超长文本截断，保留关键信息。"""
        if len(text) <= max_length:
            return text
        truncated = text[: max_length - 20]
        return truncated + "\n...（内容已截断，查看详情）"
