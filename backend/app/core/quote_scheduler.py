from collections.abc import Callable
from datetime import date
from typing import Any


class QuoteScheduler:
    def __init__(
        self,
        *,
        quote_service: Any,
        market_index_service: Any,
        is_trading_day: Callable[[date], bool],
    ):
        self.quote_service = quote_service
        self.market_index_service = market_index_service
        self.is_trading_day = is_trading_day

    def refresh_if_trading_day(self, *, current_date: date | None = None) -> None:
        today = current_date or date.today()
        if not self.is_trading_day(today):
            return

        self.quote_service.get_watchlist_quotes()
        self.market_index_service.get_market_indices()


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
