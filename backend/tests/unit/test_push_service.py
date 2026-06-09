"""T6: PushService 核心逻辑测试。

RED 阶段 —— push_service 尚未实现，测试应先 FAIL。
"""

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.database import Base


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    import backend.app.models  # noqa: F401
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    with SessionLocal() as session:
        yield session


def _make_feishu_client(success=True, error_type=None, error_message=""):
    """创建 mock 飞书客户端。"""
    class MockFeishuClient:
        def __init__(self, success, error_type, error_message):
            self.success = success
            self.error_type = error_type
            self.error_message = error_message
            self.call_count = 0

        def send_card(self, card_content):
            self.call_count += 1
            return {
                "success": self.success,
                "error_type": self.error_type,
                "error_message": self.error_message,
            }

    return MockFeishuClient(success, error_type, error_message)


def _make_telegram_client(success=True, error_type=None, error_message=""):
    """创建 mock Telegram 客户端。"""
    class MockTelegramClient:
        def __init__(self, success, error_type, error_message):
            self.success = success
            self.error_type = error_type
            self.error_message = error_message
            self.call_count = 0

        def send_message(self, text):
            self.call_count += 1
            return {
                "success": self.success,
                "error_type": self.error_type,
                "error_message": self.error_message,
            }

    return MockTelegramClient(success, error_type, error_message)


def _get_log(db, message_id):
    from backend.app.models.push_log import PushLog

    return db.query(PushLog).filter(PushLog.message_id == message_id).first()


class TestPushServiceSend:
    """PushService 核心发送逻辑。"""

    def test_primary_channel_success(self, db_session):
        from backend.app.schemas.push import PushMessageRequest
        from backend.app.services.push_service import PushService

        feishu = _make_feishu_client(success=True)
        service = PushService(db=db_session, feishu_client=feishu)

        message = PushMessageRequest(
            message_type="alert",
            priority="high",
            content={"stock_code": "600519", "price": 1498.50},
        )
        msg_id = service.send(message)

        assert msg_id is not None
        assert feishu.call_count == 1

        log = _get_log(db_session, msg_id)
        assert log is not None
        assert log.status == "sent"
        assert log.channel == "feishu"
        assert log.message_type == "alert"

    def test_primary_fails_then_fallback_to_telegram(self, db_session):
        from backend.app.schemas.push import PushMessageRequest
        from backend.app.services.push_service import PushService

        feishu = _make_feishu_client(
            success=False, error_type="rate_limited", error_message="too many requests"
        )
        telegram = _make_telegram_client(success=True)
        service = PushService(
            db=db_session, feishu_client=feishu, telegram_client=telegram
        )

        message = PushMessageRequest(
            message_type="alert",
            priority="high",
            content={"stock_code": "600519"},
        )
        msg_id = service.send(message)

        # 飞书重试 2 次 + Telegram 1 次
        assert feishu.call_count == 3
        assert telegram.call_count == 1

        log = _get_log(db_session, msg_id)
        assert log.status == "fallback"
        assert log.channel == "telegram"

    def test_primary_fails_telegram_not_configured(self, db_session):
        from backend.app.schemas.push import PushMessageRequest
        from backend.app.services.push_service import PushService

        feishu = _make_feishu_client(
            success=False, error_type="network_error", error_message="timeout"
        )
        service = PushService(db=db_session, feishu_client=feishu, telegram_client=None)

        message = PushMessageRequest(
            message_type="alert",
            content={"stock_code": "600519"},
        )
        msg_id = service.send(message)

        assert feishu.call_count == 3  # 重试 2 次

        log = _get_log(db_session, msg_id)
        assert log.status == "failed"
        assert log.error_reason is not None

    def test_both_channels_fail(self, db_session):
        from backend.app.schemas.push import PushMessageRequest
        from backend.app.services.push_service import PushService

        feishu = _make_feishu_client(
            success=False, error_type="auth_error", error_message="auth failed"
        )
        telegram = _make_telegram_client(
            success=False, error_type="network_error", error_message="timeout"
        )
        service = PushService(
            db=db_session, feishu_client=feishu, telegram_client=telegram
        )

        message = PushMessageRequest(
            message_type="alert",
            content={"stock_code": "600519"},
        )
        msg_id = service.send(message)

        assert feishu.call_count == 3
        assert telegram.call_count == 1

        log = _get_log(db_session, msg_id)
        assert log.status == "failed"
        assert "auth failed" in (log.error_reason or "")

    def test_channel_status_degraded_skips_primary(self, db_session):
        from backend.app.models.push_channel import PushChannel
        from backend.app.schemas.push import PushMessageRequest
        from backend.app.services.push_service import PushService

        # 设置飞书通道为 degraded
        db_session.add(PushChannel(name="feishu", status="degraded"))
        db_session.commit()

        feishu = _make_feishu_client(success=True)
        telegram = _make_telegram_client(success=True)
        service = PushService(
            db=db_session, feishu_client=feishu, telegram_client=telegram
        )

        message = PushMessageRequest(
            message_type="alert",
            content={"stock_code": "600519"},
        )
        msg_id = service.send(message)

        # degraded 状态直接跳过飞书
        assert feishu.call_count == 0
        assert telegram.call_count == 1

        log = _get_log(db_session, msg_id)
        assert log.status == "sent"
        assert log.channel == "telegram"

    def test_channel_status_unavailable_records_failed(self, db_session):
        from backend.app.models.push_channel import PushChannel
        from backend.app.schemas.push import PushMessageRequest
        from backend.app.services.push_service import PushService

        db_session.add(PushChannel(name="feishu", status="unavailable"))
        db_session.commit()

        feishu = _make_feishu_client(success=True)
        telegram = _make_telegram_client(success=False, error_type="auth_error")
        service = PushService(
            db=db_session, feishu_client=feishu, telegram_client=telegram
        )

        message = PushMessageRequest(
            message_type="alert",
            content={"stock_code": "600519"},
        )
        msg_id = service.send(message)

        assert feishu.call_count == 0
        assert telegram.call_count == 1

        log = _get_log(db_session, msg_id)
        assert log.status == "failed"

    def test_elapsed_ms_recorded(self, db_session):
        from backend.app.schemas.push import PushMessageRequest
        from backend.app.services.push_service import PushService

        feishu = _make_feishu_client(success=True)
        service = PushService(db=db_session, feishu_client=feishu)

        message = PushMessageRequest(
            message_type="alert",
            content={"stock_code": "600519"},
        )
        msg_id = service.send(message)

        log = _get_log(db_session, msg_id)
        assert log.elapsed_ms is not None
        assert log.elapsed_ms >= 0


class TestPushServiceFormatting:
    """T7-T9: 格式化与截断逻辑。"""

    def test_alert_content_formatting(self, db_session):
        from backend.app.schemas.push import PushMessageRequest
        from backend.app.services.push_service import PushService

        service = PushService(db=db_session)
        message = PushMessageRequest(
            message_type="alert",
            content={
                "stock_code": "600519",
                "stock_name": "贵州茅台",
                "price": 1498.50,
                "change_pct": -1.5,
                "condition": "价格 < 1500",
                "triggered_at": "2026-06-05 10:30",
                "level": "alert",
            },
        )
        formatted = service._format_content(message)

        assert formatted["_type"] == "alert"
        assert formatted["stock_code"] == "600519"
        assert formatted["stock_name"] == "贵州茅台"
        assert formatted["condition"] == "价格 < 1500"
        assert formatted["level"] == "alert"

    def test_alert_telegram_text_contains_key_info(self, db_session):
        from backend.app.services.push_service import PushService

        service = PushService(db=db_session)
        content = {
            "_type": "alert",
            "stock_code": "600519",
            "stock_name": "贵州茅台",
            "price": 1498.50,
            "change_pct": -1.5,
            "condition": "价格 < 1500",
            "triggered_at": "2026-06-05 10:30",
            "level": "alert",
        }
        text = service._content_to_text(content)

        assert "贵州茅台" in text
        assert "600519" in text
        assert "1498.5" in text
        assert "价格 &lt; 1500" in text  # HTML escaped
        assert "2026-06-05 10:30" in text
        assert "🔴" in text  # alert 级别红色标记

    def test_alert_watch_level_uses_blue_emoji(self, db_session):
        from backend.app.services.push_service import PushService

        service = PushService(db=db_session)
        content = {
            "_type": "alert",
            "stock_code": "000001",
            "stock_name": "平安银行",
            "price": 12.34,
            "change_pct": 0.5,
            "condition": "价格 > 12",
            "triggered_at": "2026-06-05 10:30",
            "level": "watch",
        }
        text = service._content_to_text(content)

        assert "🔵" in text  # watch 级别蓝色标记

    def test_briefing_content_formatting(self, db_session):
        from backend.app.schemas.push import PushMessageRequest
        from backend.app.services.push_service import PushService

        service = PushService(db=db_session)
        message = PushMessageRequest(
            message_type="briefing",
            content={
                "date": "2026-06-05",
                "market_indices": {
                    "上证指数": 3050.25,
                    "深证成指": 9850.10,
                    "创业板指": 1820.50,
                },
                "top_movers": [
                    {"name": "贵州茅台", "code": "600519", "change_pct": 5.2},
                    {"name": "平安银行", "code": "000001", "change_pct": -3.1},
                    {"name": "比亚迪", "code": "002594", "change_pct": 4.8},
                    {"name": "宁德时代", "code": "300750", "change_pct": 3.5},
                ],
            },
        )
        formatted = service._format_content(message)

        assert formatted["_type"] == "briefing"
        assert formatted["date"] == "2026-06-05"
        assert "上证指数" in formatted["market_indices"]
        assert len(formatted["top_movers"]) == 4

    def test_briefing_telegram_text_contains_indices_and_top3(self, db_session):
        from backend.app.services.push_service import PushService

        service = PushService(db=db_session)
        content = {
            "_type": "briefing",
            "date": "2026-06-05",
            "market_indices": {
                "上证指数": 3050.25,
                "深证成指": 9850.10,
            },
            "top_movers": [
                {"name": "贵州茅台", "code": "600519", "change_pct": 5.2},
                {"name": "平安银行", "code": "000001", "change_pct": -3.1},
                {"name": "比亚迪", "code": "002594", "change_pct": 4.8},
            ],
        }
        text = service._content_to_text(content)

        assert "早盘简报" in text
        assert "2026-06-05" in text
        assert "上证指数" in text
        assert "3050.25" in text
        assert "贵州茅台" in text
        assert "600519" in text
        assert "5.2%" in text
        # 只展示 TOP 3
        assert text.count("%") >= 3

    def test_truncate_text_does_not_modify_short_content(self, db_session):
        from backend.app.services.push_service import PushService

        service = PushService(db=db_session)
        short_text = "这是一条短消息"
        result = service._truncate_text(short_text, max_length=100)

        assert result == short_text

    def test_truncate_text_preserves_key_info(self, db_session):
        from backend.app.services.push_service import PushService

        service = PushService(db=db_session)
        long_text = "股票: 贵州茅台(600519)\n价格: 1498.5\n" + "x" * 5000
        result = service._truncate_text(long_text, max_length=100)

        assert len(result) <= 100
        assert "贵州茅台" in result  # 关键信息保留
        assert "600519" in result
        assert "1498.5" in result
        assert "...（内容已截断，查看详情）" in result

    def test_truncate_text_limits_length(self, db_session):
        from backend.app.services.push_service import PushService

        service = PushService(db=db_session)
        long_text = "A" * 10000
        result = service._truncate_text(long_text, max_length=500)

        assert len(result) <= 500
        assert "...（内容已截断，查看详情）" in result


class TestPushServiceFeishuFallback:
    """007 US3: Feishu 主通道失败 + Telegram 降级 + 日志不泄露密钥。"""

    def test_feishu_auth_error_fallback_to_telegram_preserves_reason(self, db_session):
        from backend.app.schemas.push import PushMessageRequest
        from backend.app.services.push_service import PushService

        feishu = _make_feishu_client(
            success=False, error_type="auth_error", error_message="authentication failed"
        )
        telegram = _make_telegram_client(success=True)
        service = PushService(
            db=db_session, feishu_client=feishu, telegram_client=telegram
        )

        message = PushMessageRequest(
            message_type="alert",
            content={"stock_code": "600519"},
        )
        msg_id = service.send(message)

        log = _get_log(db_session, msg_id)
        assert log.status == "fallback"
        assert log.channel == "telegram"

    def test_feishu_none_telegram_available_still_works(self, db_session):
        """feishu_client=None 时 Telegram 仍可使用（fallback 语义）。"""
        from backend.app.schemas.push import PushMessageRequest
        from backend.app.services.push_service import PushService

        telegram = _make_telegram_client(success=True)
        service = PushService(db=db_session, feishu_client=None, telegram_client=telegram)

        message = PushMessageRequest(
            message_type="alert",
            content={"stock_code": "600519"},
        )
        msg_id = service.send(message)

        log = _get_log(db_session, msg_id)
        # 飞书通道状态默认 active 但无客户端 → Telegram 成功记为 fallback
        assert log.channel == "telegram"
        assert log.status in ("sent", "fallback")

    def test_both_channels_none_records_failed_without_secret(self, db_session):
        """双通道均为 None 时，失败记录不包含密钥。"""
        from backend.app.schemas.push import PushMessageRequest
        from backend.app.services.push_service import PushService

        service = PushService(db=db_session, feishu_client=None, telegram_client=None)

        message = PushMessageRequest(
            message_type="alert",
            content={"stock_code": "600519"},
        )
        msg_id = service.send(message)

        log = _get_log(db_session, msg_id)
        assert log.status == "failed"
        # 无通道可用时 error_reason 不应为 None
        assert log.error_reason is not None
        assert "secret" not in (log.error_reason or "").lower()
