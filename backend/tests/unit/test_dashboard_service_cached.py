from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from backend.app.schemas.dashboard import StockCardData
from backend.app.services.dashboard_service import DashboardService


def _make_service(market_cached=None, watchlist_cached=None):
    market_service = MagicMock()
    market_service.get_cached_indices = MagicMock(return_value=market_cached)

    quote_service = MagicMock()
    quote_service.get_cached_watchlist_quotes = MagicMock(return_value=watchlist_cached)

    db = MagicMock()
    db.query.return_value.order_by.return_value.all.return_value = []

    return DashboardService(
        db=db,
        market_index_service=market_service,
        quote_service=quote_service,
        cache_service=MagicMock(),
        redis_cache=None,
    )


@pytest.mark.asyncio
async def test_get_market_data_uses_cached_indices():
    service = _make_service(
        market_cached=[MagicMock(index_name="上证指数", current_value=3000.0, change_percent=1.0, change_amount=30.0, updated_at=datetime.now(UTC))],
    )
    data = await service.get_market_data()

    service.market_index_service.get_cached_indices.assert_called_once()
    service.quote_service.get_cached_watchlist_quotes.assert_called_once()
    assert len(data["market_indices"]) == 1
    assert data["degraded"] is False


@pytest.mark.asyncio
async def test_get_market_data_degraded_when_no_cache():
    service = _make_service(market_cached=None, watchlist_cached=None)
    data = await service.get_market_data()

    assert data["market_indices"] == []
    assert data["watchlist"] == []
    assert data["degraded"] is True


@pytest.mark.asyncio
async def test_get_market_data_watchlist_falls_back_to_basic_list():
    service = _make_service(market_cached=None, watchlist_cached=None)
    # mock _get_watchlist_fallback 返回一个基础股票卡片
    service._get_watchlist_fallback = MagicMock(return_value=[
        StockCardData(code="600519", name="贵州茅台", current_price=None, change_percent=None, change_amount=None, updated_at=None),
    ])
    data = await service.get_market_data()

    assert len(data["watchlist"]) == 1
    assert data["watchlist"][0].code == "600519"
