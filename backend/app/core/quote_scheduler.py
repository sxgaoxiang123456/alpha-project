import logging
from collections.abc import Callable
from datetime import date
from typing import Any

logger = logging.getLogger(__name__)


class QuoteScheduler:
    def __init__(
        self,
        *,
        quote_service: Any,
        market_index_service: Any,
        is_trading_day: Callable[[date], bool],
        on_quotes_refreshed: Callable[[], None] | None = None,
        push_service_factory: Callable[[], Any] | None = None,
    ):
        self.quote_service = quote_service
        self.market_index_service = market_index_service
        self.is_trading_day = is_trading_day
        self.on_quotes_refreshed = on_quotes_refreshed
        self.push_service_factory = push_service_factory

    def refresh_if_trading_day(self, *, current_date: date | None = None) -> None:
        today = current_date or date.today()
        if not self.is_trading_day(today):
            logger.debug("非交易日 %s，跳过行情刷新", today)
            return

        logger.info("开始行情定时刷新")
        self.quote_service.get_watchlist_quotes()
        self.market_index_service.get_indices()
        logger.info("行情定时刷新完成")

        if self.on_quotes_refreshed:
            try:
                self.on_quotes_refreshed()
            except Exception:
                logger.exception("预警检测回调异常")

    def send_briefing_if_trading_day(self, *, current_date: date | None = None) -> None:
        """交易日 9:00 发送早盘简报推送。"""
        today = current_date or date.today()
        if not self.is_trading_day(today):
            logger.debug("非交易日 %s，跳过简报推送", today)
            return

        if self.push_service_factory is None:
            logger.debug("PushService 未配置，跳过简报推送")
            return

        logger.info("开始生成早盘简报")
        try:
            push_service = self.push_service_factory()
            indices = self.market_index_service.get_indices()

            from backend.app.schemas.push import PushMessageRequest

            market_indices = {}
            if indices:
                for name, idx in indices.items():
                    market_indices[name] = {
                        "current": float(idx.current_value) if hasattr(idx, "current_value") else 0,
                        "change_pct": float(idx.change_percent) if hasattr(idx, "change_percent") else 0,
                    }

            content = {
                "date": today.isoformat(),
                "market_indices": market_indices,
                "top_movers": [],
            }
            message = PushMessageRequest(
                message_type="briefing",
                content=content,
            )
            push_service.send(message)
            logger.info("早盘简报推送已提交")
        except Exception:
            logger.exception("简报推送异常")


def register_quote_refresh_job(
    scheduler: Any,
    quote_scheduler: QuoteScheduler,
    *,
    interval_minutes: int = 3,
) -> None:
    scheduler.add_job(
        quote_scheduler.refresh_if_trading_day,
        "interval",
        minutes=interval_minutes,
        id="quote_refresh",
        replace_existing=True,
    )


def register_briefing_job(
    scheduler: Any,
    quote_scheduler: QuoteScheduler,
) -> None:
    """注册交易日 9:00 简报定时任务。"""
    scheduler.add_job(
        quote_scheduler.send_briefing_if_trading_day,
        "cron",
        hour=9,
        minute=0,
        id="briefing_push",
        replace_existing=True,
    )
