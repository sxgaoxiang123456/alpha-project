from datetime import UTC, datetime
from decimal import Decimal


def test_clean_quote_returns_standard_quote_for_valid_payload():
    from backend.app.services.data_cleaner import DataCleaner
    from backend.app.schemas.quote import Quote

    actual_timestamp = datetime(2026, 6, 4, 10, 0, tzinfo=UTC)

    quote = DataCleaner().clean_quote(
        "600519",
        {
            "name": " 贵州茅台 ",
            "price": 1500.5,
            "change_pct": 1.25,
            "volume": 100000,
            "amount": 150050000.0,
        },
        source_status="primary",
        actual_timestamp=actual_timestamp,
    )

    assert isinstance(quote, Quote)
    assert quote.stock_code == "600519"
    assert quote.stock_name == "贵州茅台"
    assert quote.current_price == Decimal("1500.5")
    assert quote.change_percent == Decimal("1.25")
    assert quote.volume == 100000
    assert quote.turnover == Decimal("150050000.0")
    assert quote.status == "normal"
    assert quote.source_status == "primary"
    assert quote.actual_timestamp == actual_timestamp


def test_clean_quote_marks_negative_price_abnormal():
    from backend.app.services.data_cleaner import DataCleaner

    actual_timestamp = datetime(2026, 6, 4, 10, 0, tzinfo=UTC)

    quote = DataCleaner().clean_quote(
        "600519",
        {
            "name": "贵州茅台",
            "price": -10,
            "change_pct": 1.25,
            "volume": 100000,
            "amount": 150050000.0,
        },
        source_status="primary",
        actual_timestamp=actual_timestamp,
    )

    assert quote.status == "abnormal"
    assert quote.current_price is None


def test_clean_quote_marks_non_star_market_large_change_abnormal():
    from backend.app.services.data_cleaner import DataCleaner

    actual_timestamp = datetime(2026, 6, 4, 10, 0, tzinfo=UTC)

    quote = DataCleaner().clean_quote(
        "600519",
        {
            "name": "贵州茅台",
            "price": 1500.5,
            "change_pct": 25,
            "volume": 100000,
            "amount": 150050000.0,
        },
        source_status="fallback",
        actual_timestamp=actual_timestamp,
    )

    assert quote.status == "abnormal"
    assert quote.current_price == Decimal("1500.5")
    assert quote.change_percent == Decimal("25")


def test_clean_quote_marks_zero_volume_non_suspended_stock_abnormal():
    from backend.app.services.data_cleaner import DataCleaner

    actual_timestamp = datetime(2026, 6, 4, 10, 0, tzinfo=UTC)

    quote = DataCleaner().clean_quote(
        "600519",
        {
            "name": "贵州茅台",
            "price": 1500.5,
            "change_pct": 1.25,
            "volume": 0,
            "amount": 150050000.0,
        },
        source_status="primary",
        actual_timestamp=actual_timestamp,
    )

    assert quote.status == "abnormal"
    assert quote.volume == 0


def test_clean_quote_keeps_star_market_change_within_30_percent_normal():
    from backend.app.services.data_cleaner import DataCleaner

    actual_timestamp = datetime(2026, 6, 4, 10, 0, tzinfo=UTC)

    quote = DataCleaner().clean_quote(
        "688001",
        {
            "name": "华兴源创",
            "price": 42.5,
            "change_pct": 25,
            "volume": 100000,
            "amount": 4250000.0,
        },
        source_status="primary",
        actual_timestamp=actual_timestamp,
    )

    assert quote.status == "normal"
    assert quote.change_percent == Decimal("25")


def test_clean_quote_marks_suspended_stock_and_uses_last_close_price():
    from backend.app.services.data_cleaner import DataCleaner

    actual_timestamp = datetime(2026, 6, 4, 10, 0, tzinfo=UTC)

    quote = DataCleaner().clean_quote(
        "000001",
        {
            "name": "平安银行",
            "status": "停牌",
            "price": 0,
            "pre_close": 12.34,
            "change_pct": 0,
            "volume": 0,
            "amount": 0,
        },
        source_status="primary",
        actual_timestamp=actual_timestamp,
    )

    assert quote.status == "suspended"
    assert quote.current_price == Decimal("12.34")
    assert quote.change_percent is None
    assert quote.volume is None


def test_clean_quote_marks_missing_payload():
    from backend.app.services.data_cleaner import DataCleaner

    actual_timestamp = datetime(2026, 6, 4, 10, 0, tzinfo=UTC)

    quote = DataCleaner().clean_quote(
        "600519",
        None,
        source_status="unavailable",
        actual_timestamp=actual_timestamp,
    )

    assert quote.status == "missing"
    assert quote.stock_name == "600519"
    assert quote.current_price is None
    assert quote.source_status == "unavailable"
