from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError


def test_quote_accepts_valid_realtime_payload():
    from backend.app.schemas.quote import Quote

    updated_at = datetime(2026, 6, 4, 10, 0, tzinfo=UTC)

    quote = Quote(
        stock_code="600519",
        stock_name="贵州茅台",
        current_price=Decimal("1500.50"),
        change_percent=Decimal("1.25"),
        change_amount=Decimal("18.50"),
        volume=100000,
        turnover=Decimal("150050000.00"),
        updated_at=updated_at,
        status="normal",
        source_status="primary",
        actual_timestamp=updated_at,
    )

    assert quote.stock_code == "600519"
    assert quote.stock_name == "贵州茅台"
    assert quote.current_price == Decimal("1500.50")
    assert quote.source_status == "primary"


def test_quote_rejects_invalid_price_and_change_percent():
    from backend.app.schemas.quote import Quote

    updated_at = datetime(2026, 6, 4, 10, 0, tzinfo=UTC)
    valid_payload = {
        "stock_code": "600519",
        "stock_name": "贵州茅台",
        "current_price": Decimal("1500.50"),
        "change_percent": Decimal("1.25"),
        "change_amount": Decimal("18.50"),
        "volume": 100000,
        "turnover": Decimal("150050000.00"),
        "updated_at": updated_at,
        "status": "normal",
        "source_status": "primary",
        "actual_timestamp": updated_at,
    }

    with pytest.raises(ValidationError):
        Quote(**{**valid_payload, "current_price": Decimal("0")})

    with pytest.raises(ValidationError):
        Quote(**{**valid_payload, "change_percent": Decimal("101")})


def test_quote_rejects_invalid_status_values():
    from backend.app.schemas.quote import Quote

    updated_at = datetime(2026, 6, 4, 10, 0, tzinfo=UTC)
    valid_payload = {
        "stock_code": "600519",
        "stock_name": "贵州茅台",
        "current_price": Decimal("1500.50"),
        "change_percent": Decimal("1.25"),
        "change_amount": Decimal("18.50"),
        "volume": 100000,
        "turnover": Decimal("150050000.00"),
        "updated_at": updated_at,
        "status": "normal",
        "source_status": "primary",
        "actual_timestamp": updated_at,
    }

    with pytest.raises(ValidationError):
        Quote(**{**valid_payload, "status": "trading"})

    with pytest.raises(ValidationError):
        Quote(**{**valid_payload, "source_status": "remote"})


def test_market_index_accepts_fixed_index_payload():
    from backend.app.schemas.quote import MarketIndex

    updated_at = datetime(2026, 6, 4, 10, 0, tzinfo=UTC)

    index = MarketIndex(
        index_code="sh000001",
        index_name="上证指数",
        current_point=Decimal("3123.45"),
        change_percent=Decimal("0.85"),
        change_amount=Decimal("26.10"),
        turnover=Decimal("450000000000.00"),
        updated_at=updated_at,
        source_status="fallback",
        actual_timestamp=updated_at,
    )

    assert index.index_code == "sh000001"
    assert index.index_name == "上证指数"
    assert index.current_point == Decimal("3123.45")


def test_market_index_rejects_invalid_code_and_point():
    from backend.app.schemas.quote import MarketIndex

    updated_at = datetime(2026, 6, 4, 10, 0, tzinfo=UTC)
    valid_payload = {
        "index_code": "sh000001",
        "index_name": "上证指数",
        "current_point": Decimal("3123.45"),
        "change_percent": Decimal("0.85"),
        "change_amount": Decimal("26.10"),
        "turnover": Decimal("450000000000.00"),
        "updated_at": updated_at,
        "source_status": "fallback",
        "actual_timestamp": updated_at,
    }

    with pytest.raises(ValidationError):
        MarketIndex(**{**valid_payload, "index_code": "000001"})

    with pytest.raises(ValidationError):
        MarketIndex(**{**valid_payload, "current_point": Decimal("0")})


def test_historical_quote_request_rejects_inverted_date_range():
    from backend.app.schemas.quote import HistoricalQuoteRequest

    with pytest.raises(ValidationError):
        HistoricalQuoteRequest(
            stock_code="600519",
            start_date=date(2026, 6, 5),
            end_date=date(2026, 6, 4),
        )


def test_historical_quote_response_validates_from_sqlalchemy_model():
    from backend.app.models.historical_quote import HistoricalQuote
    from backend.app.schemas.quote import HistoricalQuoteResponse

    model = HistoricalQuote(
        stock_code="600519",
        date=date(2026, 6, 4),
        open=Decimal("10.00"),
        close=Decimal("10.20"),
        high=Decimal("10.50"),
        low=Decimal("9.90"),
        volume=100000,
        turnover=Decimal("1020000.00"),
    )

    response = HistoricalQuoteResponse.model_validate(model)

    assert response.stock_code == "600519"
    assert response.date == date(2026, 6, 4)
    assert response.close == Decimal("10.20")


def test_quote_schemas_are_exported_from_schema_package():
    from backend.app.schemas import HistoricalQuoteRequest, HistoricalQuoteResponse, MarketIndex, Quote

    assert Quote.__name__ == "Quote"
    assert MarketIndex.__name__ == "MarketIndex"
    assert HistoricalQuoteRequest.__name__ == "HistoricalQuoteRequest"
    assert HistoricalQuoteResponse.__name__ == "HistoricalQuoteResponse"
