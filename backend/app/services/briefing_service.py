import json
import logging
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from backend.app.models.alert_trigger import AlertTrigger
from backend.app.schemas.briefing import BriefingResponse, MarketIndexSnapshot, TopMover
from backend.app.schemas.push import PushMessageRequest
from backend.app.services.briefing_llm_client import BriefingLLMClient, LLMResult
from backend.app.services.prompt_loader import PromptLoader
from backend.app.services.top_mover_service import TopMoverService

logger = logging.getLogger(__name__)


class BriefingService:
    """简报生成编排服务。"""

    QUOTE_REFRESH_WAIT_SECONDS = 15
    BRIEFING_TOTAL_TIMEOUT_SECONDS = 60

    def __init__(
        self,
        db: Session,
        market_index_service: Any,
        quote_service: Any,
        top_mover_service: TopMoverService,
        prompt_loader: PromptLoader,
        llm_client: BriefingLLMClient,
        is_trading_day: Callable[[date], bool],
        push_service: Any | None = None,
        cache_service: Any | None = None,
        fallback_quotes_provider: Callable[[], dict[str, dict[str, Any]] | None] = None,
        quote_refresh_waiter: Callable[[int], bool] | None = None,
    ):
        self.db = db
        self.market_index_service = market_index_service
        self.quote_service = quote_service
        self.top_mover_service = top_mover_service
        self.prompt_loader = prompt_loader
        self.llm_client = llm_client
        self.is_trading_day = is_trading_day
        self.push_service = push_service
        self.cache_service = cache_service
        self.fallback_quotes_provider = fallback_quotes_provider
        self.quote_refresh_waiter = quote_refresh_waiter

    def generate(
        self,
        *,
        current_date: date | None = None,
        manual: bool = False,
    ) -> BriefingResponse | None:
        """生成早盘简报。非交易日且非手动时返回 None。"""
        today = current_date or date.today()

        if not manual and not self.is_trading_day(today):
            logger.info("非交易日 %s，跳过简报生成", today)
            return None

        start_time = datetime.now(UTC)

        # FR-013: 等待行情刷新完成（最多 15 秒），超时则基于缓存独立执行
        if self.quote_refresh_waiter is not None:
            refreshed = self.quote_refresh_waiter(self.QUOTE_REFRESH_WAIT_SECONDS)
            if not refreshed:
                logger.warning("行情刷新等待超时，基于缓存数据生成简报")

        # 1. 准备数据
        indices = self.market_index_service.get_indices(use_cache=True)
        watchlist_quotes = self.quote_service.get_watchlist_quotes(use_cache=True)

        fallback_quotes = None
        if self.fallback_quotes_provider is not None:
            try:
                fallback_quotes = self.fallback_quotes_provider()
            except Exception:
                logger.exception("全市场异动补充数据获取失败")

        top_movers = self.top_mover_service.compute_top_movers(
            watchlist_quotes, fallback_quotes=fallback_quotes
        )

        alert_history = self._get_alert_history(today)

        market_indices = {
            idx.index_name: MarketIndexSnapshot(
                current=float(idx.current_point or 0),
                change_pct=float(idx.change_percent or 0),
            )
            for idx in indices
        }

        # 2. 渲染 Prompt
        prompt = self.prompt_loader.render(
            today=today.isoformat(),
            market_indices={
                name: {"current": snap.current, "change_pct": snap.change_pct}
                for name, snap in market_indices.items()
            },
            top_movers=[m.model_dump() for m in top_movers],
            alert_history=alert_history,
        )

        # 3. 调用 LLM
        llm_result = self.llm_client.generate(prompt)

        # 4. 构建结果
        briefing = self._build_briefing(
            today=today,
            market_indices=market_indices,
            top_movers=top_movers,
            llm_result=llm_result,
        )

        # 5. 缓存并推送
        self._cache_briefing(briefing)
        self._push_briefing(briefing)

        elapsed = (datetime.now(UTC) - start_time).total_seconds()
        logger.info(
            "简报生成完成: date=%s, degraded=%s, elapsed=%.2fs",
            today,
            briefing.is_degraded,
            elapsed,
        )

        return briefing

    def _get_alert_history(self, today: date) -> list[str]:
        """获取过去 24 小时预警记录摘要。"""
        cutoff = datetime(today.year, today.month, today.day, tzinfo=UTC) - timedelta(hours=24)
        try:
            triggers = (
                self.db.query(AlertTrigger)
                .filter(AlertTrigger.triggered_at >= cutoff)
                .order_by(AlertTrigger.triggered_at.desc())
                .limit(20)
                .all()
            )
            return [
                f"{t.stock_code} {t.condition_type} {t.trigger_value}"
                for t in triggers
            ]
        except Exception:
            logger.exception("预警历史查询失败")
            return []

    def _build_briefing(
        self,
        *,
        today: date,
        market_indices: dict[str, MarketIndexSnapshot],
        top_movers: list[TopMover],
        llm_result: LLMResult,
    ) -> BriefingResponse:
        """根据 LLM 结果构建简报响应。"""
        if not llm_result.is_degraded and llm_result.data:
            insights = llm_result.data.get("insights", [])
            if not isinstance(insights, list):
                insights = [str(insights)]
            return BriefingResponse(
                date=today.isoformat(),
                market_indices=market_indices,
                top_movers=top_movers,
                insights=insights,
                is_degraded=False,
                generated_at=datetime.now(UTC),
            )

        return BriefingResponse(
            date=today.isoformat(),
            market_indices=market_indices,
            top_movers=top_movers,
            insights=[],
            is_degraded=True,
            degraded_reason=llm_result.error_reason or "LLM 调用失败",
            generated_at=datetime.now(UTC),
        )

    def _cache_briefing(self, briefing: BriefingResponse) -> None:
        """缓存最新简报。"""
        if self.cache_service is None:
            return
        try:
            self.cache_service.set(
                "latest_briefing",
                json.dumps(briefing.model_dump(mode="json"), ensure_ascii=False),
                ttl_seconds=300,
            )
        except Exception:
            logger.exception("简报缓存失败")

    def _push_briefing(self, briefing: BriefingResponse) -> None:
        """通过推送服务发送简报。"""
        if self.push_service is None:
            return
        try:
            content = {
                "date": briefing.date,
                "market_indices": {
                    name: {"current": snap.current, "change_pct": snap.change_pct}
                    for name, snap in briefing.market_indices.items()
                },
                "top_movers": [m.model_dump(mode="json") for m in briefing.top_movers],
                "insights": briefing.insights,
                "is_degraded": briefing.is_degraded,
                "degraded_reason": briefing.degraded_reason,
                "metadata": {
                    "is_degraded": briefing.is_degraded,
                    "degraded_reason": briefing.degraded_reason,
                },
            }
            message = PushMessageRequest(
                message_type="briefing",
                content=content,
            )
            self.push_service.send(message)
        except Exception:
            logger.exception("简报推送提交失败")
