from datetime import UTC, datetime
from decimal import Decimal

from backend.app.schemas.data_fetch import DataFetchResult


class FakeFacade:
    def __init__(self):
        self.requested_codes = None

    def fetch_realtime(self, codes):
        self.requested_codes = codes
        return DataFetchResult(
            status="primary",
            source="akshare",
            response_time_ms=12.3,
            data={
                "sh000001": {
                    "name": "上证指数",
                    "price": 3123.45,
                    "change_pct": 0.85,
                    "change_amount": 26.1,
                    "amount": 450000000000.0,
                },
                "sz399001": {
                    "name": "深证成指",
                    "price": 9876.54,
                    "change_pct": -0.42,
                    "change_amount": -41.2,
                    "amount": 520000000000.0,
                },
                "sz399006": {
                    "name": "创业板指",
                    "price": 2100.12,
                    "change_pct": 1.5,
                    "change_amount": 31.0,
                    "amount": 180000000000.0,
                },
            },
        )


class FakeCache:
    def __init__(self):
        self.entries = {}

    def set(self, key, content, ttl_seconds=None):
        self.entries[key] = (content, ttl_seconds)


def test_market_index_service_fetches_fixed_indices_and_returns_models():
    from backend.app.schemas.quote import MarketIndex
    from backend.app.services.market_index import MarketIndexService

    facade = FakeFacade()
    cache = FakeCache()
    actual_timestamp = datetime(2026, 6, 4, 10, 0, tzinfo=UTC)

    indices = MarketIndexService(facade=facade, cache=cache).get_indices(
        actual_timestamp=actual_timestamp
    )

    assert facade.requested_codes == ["sh000001", "sz399001", "sz399006"]
    assert len(indices) == 3
    assert all(isinstance(index, MarketIndex) for index in indices)
    assert [index.index_code for index in indices] == ["sh000001", "sz399001", "sz399006"]
    assert indices[0].index_name == "上证指数"
    assert indices[0].current_point == Decimal("3123.45")
    assert indices[0].change_percent == Decimal("0.85")
    assert indices[0].change_amount == Decimal("26.1")
    assert indices[0].turnover == Decimal("450000000000.0")
    assert indices[0].source_status == "primary"
    assert indices[0].actual_timestamp == actual_timestamp


def test_market_index_service_writes_each_index_to_cache_with_five_minute_ttl():
    from backend.app.services.market_index import MarketIndexService

    facade = FakeFacade()
    cache = FakeCache()

    MarketIndexService(facade=facade, cache=cache).get_indices(
        actual_timestamp=datetime(2026, 6, 4, 10, 0, tzinfo=UTC)
    )

    assert set(cache.entries) == {
        "market_index:sh000001",
        "market_index:sz399001",
        "market_index:sz399006",
    }
    assert cache.entries["market_index:sh000001"][1] == 300
    assert '"index_code":"sh000001"' in cache.entries["market_index:sh000001"][0]
