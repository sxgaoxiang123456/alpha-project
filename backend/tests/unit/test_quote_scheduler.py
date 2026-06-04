from datetime import date
from unittest.mock import Mock

from backend.app.core.quote_scheduler import QuoteScheduler, register_quote_refresh_job


def test_quote_scheduler_refreshes_quotes_and_market_indices_on_trading_day():
    quote_service = Mock()
    market_index_service = Mock()
    scheduler = QuoteScheduler(
        quote_service=quote_service,
        market_index_service=market_index_service,
        is_trading_day=lambda current_date: True,
    )

    scheduler.refresh_if_trading_day(current_date=date(2026, 6, 4))

    quote_service.get_watchlist_quotes.assert_called_once_with()
    market_index_service.get_indices.assert_called_once_with()


def test_quote_scheduler_skips_refresh_on_non_trading_day():
    quote_service = Mock()
    market_index_service = Mock()
    scheduler = QuoteScheduler(
        quote_service=quote_service,
        market_index_service=market_index_service,
        is_trading_day=lambda current_date: False,
    )

    scheduler.refresh_if_trading_day(current_date=date(2026, 6, 6))

    quote_service.get_watchlist_quotes.assert_not_called()
    market_index_service.get_indices.assert_not_called()


def test_register_quote_refresh_job_adds_three_minute_interval_job():
    scheduler_backend = Mock()
    quote_scheduler = Mock()

    register_quote_refresh_job(scheduler_backend, quote_scheduler)

    scheduler_backend.add_job.assert_called_once_with(
        quote_scheduler.refresh_if_trading_day,
        "interval",
        minutes=3,
        id="quote_refresh",
        replace_existing=True,
    )
