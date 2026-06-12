"""quote_service 缓存改造单元测试 — use_cache hit/miss/降级/行为不变。"""

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from fakeredis import FakeRedis

from backend.app.core.redis_cache import RedisCache
from backend.app.database import Base
from backend.app.models.watchlist import WatchlistItem
from backend.app.schemas.quote import Quote
from backend.app.services.quote_service import QuoteService
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


@pytest.fixture
def db():
    """创建内存数据库 session，并初始化所有表。"""
    engine = create_engine("sqlite:///:memory:")
    import backend.app.models  # noqa: F401
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def _make_db_with_watchlist(db):
    """向测试数据库插入自选股。"""
    db.add(WatchlistItem(stock_code="600519", group_id=1))
    db.add(WatchlistItem(stock_code="600000", group_id=1))
    db.commit()


def _mock_facade(data=None, status="primary"):
    facade = MagicMock()
    result = MagicMock()
    result.data = data or {
        "600519": {
            "name": "贵州茅台",
            "price": "1800.50",
            "change_pct": "2.50",
            "change_amount": "43.90",
        },
        "600000": {
            "name": "浦发银行",
            "price": "10.50",
            "change_pct": "1.20",
            "change_amount": "0.12",
        },
    }
    result.status = status
    facade.fetch_realtime = MagicMock(return_value=result)
    return facade


def _mock_cache_service():
    cache = MagicMock()
    cache.set = MagicMock()
    cache.get = MagicMock(return_value=None)
    return cache


@pytest.fixture
def redis_cache():
    return RedisCache(client=FakeRedis(decode_responses=True))


class TestQuoteServiceCacheHit:
    """use_cache=True + Redis hit 测试。"""

    def test_cache_hit_returns_redis_data_no_facade_call(self, db, redis_cache):
        """Redis hit 时直接返回缓存数据，不调用外部接口。"""
        _make_db_with_watchlist(db)
        facade = _mock_facade()
        # 预置 Redis 缓存
        redis_cache.set("quotes:watchlist:600000,600519", [
            {
                "stock_code": "600519",
                "stock_name": "贵州茅台",
                "current_price": 1800.50,
                "change_percent": 2.50,
                "change_amount": 43.90,
                "updated_at": datetime.now(UTC).isoformat(),
                "status": "normal",
                "source_status": "cached",
            },
            {
                "stock_code": "600000",
                "stock_name": "浦发银行",
                "current_price": 10.50,
                "change_percent": 1.20,
                "change_amount": 0.12,
                "updated_at": datetime.now(UTC).isoformat(),
                "status": "normal",
                "source_status": "cached",
            },
        ])

        service = QuoteService(
            db=db,
            facade=facade,
            cache=_mock_cache_service(),
            redis_cache=redis_cache,
        )
        quotes = service.get_watchlist_quotes(use_cache=True)

        assert len(quotes) == 2
        assert quotes[0].stock_code == "600519"
        facade.fetch_realtime.assert_not_called()

    def test_cache_hit_returns_quote_objects(self, db, redis_cache):
        """Redis hit 时返回 Quote 对象列表。"""
        _make_db_with_watchlist(db)
        redis_cache.set("quotes:watchlist:600519,600000", [
            {
                "stock_code": "600519",
                "stock_name": "贵州茅台",
                "current_price": 1800.50,
                "change_percent": 2.50,
                "change_amount": 43.90,
                "updated_at": datetime.now(UTC).isoformat(),
                "status": "normal",
                "source_status": "cached",
            },
        ])

        service = QuoteService(
            db=db,
            facade=_mock_facade(),
            cache=_mock_cache_service(),
            redis_cache=redis_cache,
        )
        quotes = service.get_watchlist_quotes(use_cache=True)

        assert all(isinstance(q, Quote) for q in quotes)


class TestQuoteServiceCacheMiss:
    """use_cache=True + Redis miss 测试。"""

    def test_cache_miss_calls_facade_and_writes_redis(self, db, redis_cache):
        """Redis miss 时调用外部接口，并将结果写入 Redis。"""
        _make_db_with_watchlist(db)
        facade = _mock_facade()

        service = QuoteService(
            db=db,
            facade=facade,
            cache=_mock_cache_service(),
            redis_cache=redis_cache,
        )
        quotes = service.get_watchlist_quotes(use_cache=True)

        facade.fetch_realtime.assert_called_once()
        assert len(quotes) == 2
        # 验证 Redis 被写入
        cached = redis_cache.get("quotes:watchlist:600000,600519")
        assert cached is not None
        assert len(cached) == 2


class TestQuoteServiceCacheDisabled:
    """use_cache=False 行为不变测试。"""

    def test_use_cache_false_calls_facade_directly(self, db, redis_cache):
        """use_cache=False 时直接调用外部接口，不查 Redis。"""
        _make_db_with_watchlist(db)
        facade = _mock_facade()
        # 预置 Redis 缓存
        redis_cache.set("quotes:watchlist:600000,600519", [{"stock_code": "cached"}])

        service = QuoteService(
            db=db,
            facade=facade,
            cache=_mock_cache_service(),
            redis_cache=redis_cache,
        )
        quotes = service.get_watchlist_quotes(use_cache=False)

        facade.fetch_realtime.assert_called_once()
        assert quotes[0].stock_code == "600519"  # 不是缓存的 "cached"

    def test_default_use_cache_false(self, db, redis_cache):
        """默认不传参时 use_cache=False，行为不变。"""
        _make_db_with_watchlist(db)
        facade = _mock_facade()
        redis_cache.set("quotes:watchlist:600000,600519", [{"stock_code": "cached"}])

        service = QuoteService(
            db=db,
            facade=facade,
            cache=_mock_cache_service(),
            redis_cache=redis_cache,
        )
        quotes = service.get_watchlist_quotes()

        facade.fetch_realtime.assert_called_once()
        assert quotes[0].stock_code == "600519"


class TestQuoteServiceCacheDegradation:
    """Redis 不可用降级测试。"""

    def test_redis_none_degrades_to_facade(self, db):
        """redis_cache=None 时降级为直接调用外部接口。"""
        _make_db_with_watchlist(db)
        facade = _mock_facade()

        service = QuoteService(
            db=db,
            facade=facade,
            cache=_mock_cache_service(),
            redis_cache=None,
        )
        quotes = service.get_watchlist_quotes(use_cache=True)

        facade.fetch_realtime.assert_called_once()
        assert len(quotes) == 2

    def test_redis_broken_degrades_to_facade(self, db):
        """Redis 连接异常时降级为直接调用外部接口。"""
        _make_db_with_watchlist(db)
        facade = _mock_facade()
        broken_client = FakeRedis(decode_responses=True)
        broken_client.close()
        redis_cache = RedisCache(client=broken_client)

        service = QuoteService(
            db=db,
            facade=facade,
            cache=_mock_cache_service(),
            redis_cache=redis_cache,
        )
        quotes = service.get_watchlist_quotes(use_cache=True)

        facade.fetch_realtime.assert_called_once()
        assert len(quotes) == 2
