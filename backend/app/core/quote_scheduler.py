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
    ):
        self.quote_service = quote_service
        self.market_index_service = market_index_service
        self.is_trading_day = is_trading_day
        self.on_quotes_refreshed = on_quotes_refreshed

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
