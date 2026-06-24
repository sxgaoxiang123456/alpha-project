import logging
import threading
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
        briefing_service_factory: Callable[[], Any] | None = None,
    ):
        self.quote_service = quote_service
        self.market_index_service = market_index_service
        self.is_trading_day = is_trading_day
        self.on_quotes_refreshed = on_quotes_refreshed
        self.push_service_factory = push_service_factory
        self.briefing_service_factory = briefing_service_factory
        self._quote_refresh_done = threading.Event()
        self._quote_refresh_done.set()

    def refresh_if_trading_day(self, *, current_date: date | None = None) -> None:
        today = current_date or date.today()
        if not self.is_trading_day(today):
            logger.debug("非交易日 %s，跳过行情刷新", today)
            return

        logger.info("开始行情定时刷新")
        self._quote_refresh_done.clear()
        try:
            self.quote_service.get_watchlist_quotes()
            self.market_index_service.get_indices()
            logger.info("行情定时刷新完成")

            if self.on_quotes_refreshed:
                try:
                    self.on_quotes_refreshed()
                except Exception:
                    logger.exception("预警检测回调异常")
        finally:
            self._quote_refresh_done.set()

    def wait_for_quote_refresh(self, timeout_seconds: int = 15) -> bool:
        """等待正在执行的行情刷新完成，超时返回 False。"""
        return self._quote_refresh_done.wait(timeout=timeout_seconds)

    def send_briefing_if_trading_day(self, *, current_date: date | None = None) -> None:
        """交易日 8:50 生成并推送早盘简报。"""
        today = current_date or date.today()
        if not self.is_trading_day(today):
            logger.debug("非交易日 %s，跳过简报推送", today)
            return

        if self.briefing_service_factory is None:
            logger.debug("BriefingService 未配置，跳过简报推送")
            return

        logger.info("开始生成早盘简报")
        try:
            briefing_service = self.briefing_service_factory()
            briefing_service.generate(current_date=today)
            logger.info("早盘简报生成已提交")
        except Exception:
            logger.exception("早盘简报生成异常")


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
    """注册交易日 8:50 简报定时任务。"""
    scheduler.add_job(
        quote_scheduler.send_briefing_if_trading_day,
        "cron",
        hour=8,
        minute=50,
        id="briefing_push",
        replace_existing=True,
    )
