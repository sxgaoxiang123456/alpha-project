from datetime import date
from unittest.mock import Mock
import threading
import time

from freezegun import freeze_time

from backend.app.core.quote_scheduler import (
    QuoteScheduler,
    register_briefing_job,
    register_quote_refresh_job,
)


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


def test_quote_scheduler_uses_today_for_trading_day_check_when_date_omitted():
    quote_service = Mock()
    market_index_service = Mock()
    checked_dates = []
    scheduler = QuoteScheduler(
        quote_service=quote_service,
        market_index_service=market_index_service,
        is_trading_day=lambda current_date: checked_dates.append(current_date) or True,
    )

    with freeze_time("2026-06-04"):
        scheduler.refresh_if_trading_day()

    assert checked_dates == [date(2026, 6, 4)]
    quote_service.get_watchlist_quotes.assert_called_once_with()
    market_index_service.get_indices.assert_called_once_with()


def test_quote_scheduler_skips_refresh_for_frozen_non_trading_day():
    quote_service = Mock()
    market_index_service = Mock()
    checked_dates = []
    scheduler = QuoteScheduler(
        quote_service=quote_service,
        market_index_service=market_index_service,
        is_trading_day=lambda current_date: checked_dates.append(current_date) or False,
    )

    with freeze_time("2026-06-06"):
        scheduler.refresh_if_trading_day()

    assert checked_dates == [date(2026, 6, 6)]
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


# ---------- T11: 简报定时触发 ----------

def test_send_briefing_on_trading_day():
    quote_service = Mock()
    market_index_service = Mock()
    market_index_service.get_indices.return_value = {
        "上证指数": Mock(current_value=3050.25, change_percent=0.5),
    }
    briefing_service = Mock()
    briefing_service_factory = Mock(return_value=briefing_service)

    scheduler = QuoteScheduler(
        quote_service=quote_service,
        market_index_service=market_index_service,
        is_trading_day=lambda current_date: True,
        briefing_service_factory=briefing_service_factory,
    )

    scheduler.send_briefing_if_trading_day(current_date=date(2026, 6, 4))

    briefing_service_factory.assert_called_once()
    briefing_service.generate.assert_called_once_with(current_date=date(2026, 6, 4))


def test_skip_briefing_on_non_trading_day():
    quote_service = Mock()
    market_index_service = Mock()
    briefing_service = Mock()
    briefing_service_factory = Mock(return_value=briefing_service)

    scheduler = QuoteScheduler(
        quote_service=quote_service,
        market_index_service=market_index_service,
        is_trading_day=lambda current_date: False,
        briefing_service_factory=briefing_service_factory,
    )

    scheduler.send_briefing_if_trading_day(current_date=date(2026, 6, 6))

    briefing_service_factory.assert_not_called()
    briefing_service.generate.assert_not_called()


def test_skip_briefing_when_briefing_service_not_configured():
    quote_service = Mock()
    market_index_service = Mock()

    scheduler = QuoteScheduler(
        quote_service=quote_service,
        market_index_service=market_index_service,
        is_trading_day=lambda current_date: True,
        briefing_service_factory=None,
    )

    scheduler.send_briefing_if_trading_day(current_date=date(2026, 6, 4))

    quote_service.get_watchlist_quotes.assert_not_called()


def test_register_briefing_job_adds_850_cron_job():
    scheduler_backend = Mock()
    quote_scheduler = Mock()

    register_briefing_job(scheduler_backend, quote_scheduler)

    scheduler_backend.add_job.assert_called_once_with(
        quote_scheduler.send_briefing_if_trading_day,
        "cron",
        hour=8,
        minute=50,
        id="briefing_push",
        replace_existing=True,
    )


def test_wait_for_quote_refresh_returns_true_after_refresh_completes():
    quote_service = Mock()
    quote_service.get_watchlist_quotes.side_effect = lambda: time.sleep(0.1)
    market_index_service = Mock()
    scheduler = QuoteScheduler(
        quote_service=quote_service,
        market_index_service=market_index_service,
        is_trading_day=lambda current_date: True,
    )

    thread = threading.Thread(target=scheduler.refresh_if_trading_day, kwargs={"current_date": date(2026, 6, 4)})
    thread.start()
    time.sleep(0.05)

    assert scheduler.wait_for_quote_refresh(timeout_seconds=2) is True
    thread.join(timeout=2)
    assert not thread.is_alive()


def test_wait_for_quote_refresh_returns_false_on_timeout():
    quote_service = Mock()
    quote_service.get_watchlist_quotes.side_effect = lambda: time.sleep(1.0)
    market_index_service = Mock()
    scheduler = QuoteScheduler(
        quote_service=quote_service,
        market_index_service=market_index_service,
        is_trading_day=lambda current_date: True,
    )

    thread = threading.Thread(target=scheduler.refresh_if_trading_day, kwargs={"current_date": date(2026, 6, 4)})
    thread.start()
    time.sleep(0.05)

    assert scheduler.wait_for_quote_refresh(timeout_seconds=0.1) is False
    thread.join(timeout=2)
