from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from fakeredis import FakeRedis
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.core.redis_cache import RedisCache
from backend.app.database import Base
from backend.app.models.watchlist import WatchlistItem
from backend.app.schemas.quote import Quote
from backend.app.services.quote_service import QuoteService


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    import backend.app.models  # noqa: F401
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def redis_cache():
    return RedisCache(client=FakeRedis(decode_responses=True))


def _mock_cache_service():
    cache = MagicMock()
    cache.set = MagicMock()
    cache.get = MagicMock(return_value=None)
    return cache


def _seed_watchlist(db):
    db.add(WatchlistItem(stock_code="600519", group_id=1))
    db.add(WatchlistItem(stock_code="600000", group_id=1))
    db.commit()


def _quote_json(code: str, name: str, price: str) -> str:
    return Quote(
        stock_code=code,
        stock_name=name,
        current_price=Decimal(price),
        change_percent=Decimal("1.23"),
        change_amount=Decimal("0.50"),
        volume=1000,
        turnover=Decimal("5000"),
        updated_at=datetime.now(UTC),
        status="normal",
        source_status="cached",
        actual_timestamp=datetime.now(UTC),
    ).model_dump_json()


class TestQuoteServiceCachedOnly:
    def test_redis_hit_returns_quotes(self, db, redis_cache):
        _seed_watchlist(db)
        redis_cache.set("quotes:watchlist:600000,600519", [
            {
                "stock_code": "600519",
                "stock_name": "贵州茅台",
                "current_price": "1800.50",
                "change_percent": "2.50",
                "change_amount": "43.90",
                "volume": 100,
                "turnover": "1000",
                "updated_at": datetime.now(UTC).isoformat(),
                "status": "normal",
                "source_status": "cached",
                "actual_timestamp": datetime.now(UTC).isoformat(),
            },
            {
                "stock_code": "600000",
                "stock_name": "浦发银行",
                "current_price": "10.50",
                "change_percent": "1.20",
                "change_amount": "0.12",
                "volume": 100,
                "turnover": "1000",
                "updated_at": datetime.now(UTC).isoformat(),
                "status": "normal",
                "source_status": "cached",
                "actual_timestamp": datetime.now(UTC).isoformat(),
            },
        ])

        service = QuoteService(
            db=db,
            facade=MagicMock(),
            cache=_mock_cache_service(),
            redis_cache=redis_cache,
        )
        quotes = service.get_cached_watchlist_quotes()

        assert quotes is not None
        assert len(quotes) == 2
        assert quotes[0].stock_code == "600519"
        service.facade.fetch_realtime.assert_not_called()

    def test_sqlite_hit_returns_quotes(self, db, redis_cache):
        _seed_watchlist(db)
        cache = MagicMock()
        cache.get = MagicMock(side_effect=lambda key: {
            "quote:600519": _quote_json("600519", "贵州茅台", "1800.50"),
            "quote:600000": _quote_json("600000", "浦发银行", "10.50"),
        }.get(key))

        service = QuoteService(
            db=db,
            facade=MagicMock(),
            cache=cache,
            redis_cache=redis_cache,
        )
        quotes = service.get_cached_watchlist_quotes()

        assert quotes is not None
        assert len(quotes) == 2
        assert all(isinstance(q, Quote) for q in quotes)
        service.facade.fetch_realtime.assert_not_called()

    def test_cache_miss_returns_none(self, db, redis_cache):
        _seed_watchlist(db)
        service = QuoteService(
            db=db,
            facade=MagicMock(),
            cache=_mock_cache_service(),
            redis_cache=redis_cache,
        )
        quotes = service.get_cached_watchlist_quotes()

        assert quotes is None
        service.facade.fetch_realtime.assert_not_called()

    def test_empty_watchlist_returns_empty_list(self, db, redis_cache):
        service = QuoteService(
            db=db,
            facade=MagicMock(),
            cache=_mock_cache_service(),
            redis_cache=redis_cache,
        )
        quotes = service.get_cached_watchlist_quotes()

        assert quotes == []
        service.facade.fetch_realtime.assert_not_called()
