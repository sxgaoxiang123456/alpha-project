from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from fakeredis import FakeRedis

from backend.app.core.redis_cache import RedisCache
from backend.app.schemas.quote import MarketIndex
from backend.app.services.market_index import MarketIndexService


@pytest.fixture
def redis_cache():
    return RedisCache(client=FakeRedis(decode_responses=True))


def _mock_cache_service(entries=None):
    entries = entries or {}
    cache = MagicMock()
    cache.get = MagicMock(side_effect=lambda key: entries.get(key))
    return cache


class TestMarketIndexCachedOnly:
    def test_redis_hit_returns_indices(self, redis_cache):
        now = datetime.now(UTC)
        redis_cache.set("quotes:market", [
            {
                "index_code": "sh000001",
                "index_name": "上证指数",
                "current_point": "3000.12",
                "change_percent": "1.23",
                "change_amount": "36.50",
                "turnover": "450000000000",
                "updated_at": now.isoformat(),
                "source_status": "cached",
                "actual_timestamp": now.isoformat(),
            },
            {
                "index_code": "sz399001",
                "index_name": "深证成指",
                "current_point": "9800.00",
                "change_percent": "-0.50",
                "change_amount": "-49.00",
                "turnover": "520000000000",
                "updated_at": now.isoformat(),
                "source_status": "cached",
                "actual_timestamp": now.isoformat(),
            },
            {
                "index_code": "sz399006",
                "index_name": "创业板指",
                "current_point": "1900.00",
                "change_percent": "0.80",
                "change_amount": "15.00",
                "turnover": "180000000000",
                "updated_at": now.isoformat(),
                "source_status": "cached",
                "actual_timestamp": now.isoformat(),
            },
        ])

        service = MarketIndexService(
            facade=MagicMock(),
            cache=_mock_cache_service(),
            redis_cache=redis_cache,
        )
        indices = service.get_cached_indices()

        assert indices is not None
        assert len(indices) == 3
        assert indices[0].index_code == "sh000001"
        service.facade.fetch_realtime.assert_not_called()

    def test_sqlite_hit_returns_indices(self, redis_cache):
        now = datetime.now(UTC)
        cache = _mock_cache_service({
            "market_index:sh000001": MarketIndex(
                index_code="sh000001",
                index_name="上证指数",
                current_point=Decimal("3000.12"),
                change_percent=Decimal("1.23"),
                change_amount=Decimal("36.50"),
                turnover=Decimal("450000000000"),
                updated_at=now,
                source_status="cached",
                actual_timestamp=now,
            ).model_dump_json(),
            "market_index:sz399001": MarketIndex(
                index_code="sz399001",
                index_name="深证成指",
                current_point=Decimal("9800.00"),
                change_percent=Decimal("-0.50"),
                change_amount=Decimal("-49.00"),
                turnover=Decimal("520000000000"),
                updated_at=now,
                source_status="cached",
                actual_timestamp=now,
            ).model_dump_json(),
            "market_index:sz399006": MarketIndex(
                index_code="sz399006",
                index_name="创业板指",
                current_point=Decimal("1900.00"),
                change_percent=Decimal("0.80"),
                change_amount=Decimal("15.00"),
                turnover=Decimal("180000000000"),
                updated_at=now,
                source_status="cached",
                actual_timestamp=now,
            ).model_dump_json(),
        })

        service = MarketIndexService(
            facade=MagicMock(),
            cache=cache,
            redis_cache=redis_cache,
        )
        indices = service.get_cached_indices()

        assert indices is not None
        assert len(indices) == 3
        assert all(isinstance(idx, MarketIndex) for idx in indices)
        service.facade.fetch_realtime.assert_not_called()

    def test_cache_miss_returns_none(self, redis_cache):
        service = MarketIndexService(
            facade=MagicMock(),
            cache=_mock_cache_service(),
            redis_cache=redis_cache,
        )
        indices = service.get_cached_indices()

        assert indices is None
        service.facade.fetch_realtime.assert_not_called()

    def test_partial_sqlite_miss_returns_none(self, redis_cache):
        now = datetime.now(UTC)
        cache = _mock_cache_service({
            "market_index:sh000001": MarketIndex(
                index_code="sh000001",
                index_name="上证指数",
                current_point=Decimal("3000.12"),
                change_percent=Decimal("1.23"),
                change_amount=Decimal("36.50"),
                turnover=Decimal("450000000000"),
                updated_at=now,
                source_status="cached",
                actual_timestamp=now,
            ).model_dump_json(),
        })

        service = MarketIndexService(
            facade=MagicMock(),
            cache=cache,
            redis_cache=redis_cache,
        )
        indices = service.get_cached_indices()

        assert indices is None
        service.facade.fetch_realtime.assert_not_called()
