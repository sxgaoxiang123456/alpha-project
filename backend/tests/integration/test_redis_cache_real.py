"""Redis 真库验证 — 用真实 Redis 容器验证 redis_cache.py 的读写/TTL/降级。

归档信息（testing-system-blueprint）:
- Feature: 008-redis-adjust
- 缺口来源: test-routing-advisor -> backend-testing
- 命中缺口: 真库数据层验证
- 三层节奏: 中层（真实容器启动，约 5-10s）
- 可追溯 ID: TR-008-BE-001 ~ TR-008-BE-005
"""

import json

import pytest
from testcontainers.redis import RedisContainer

from backend.app.core.redis_cache import RedisCache


@pytest.fixture(scope="module")
def real_redis():
    """启动真实 Redis 容器，yield 客户端，结束后自动清理。"""
    with RedisContainer("redis:7-alpine") as redis:
        client = redis.get_client(decode_responses=True)
        yield client
        # testcontainers 上下文退出时自动停容器


@pytest.fixture
def cache(real_redis):
    """基于真实 Redis 的 RedisCache 实例。"""
    return RedisCache(client=real_redis)


class TestRedisCacheRealReadWrite:
    """TR-008-BE-001: 真实 Redis 读写验证。"""

    def test_set_and_get_hit(self, cache: RedisCache):
        cache.set("quotes:market", {"sh000001": 3000.5})
        result = cache.get("quotes:market")
        assert result == {"sh000001": 3000.5}

    def test_set_overwrites_existing(self, cache: RedisCache):
        cache.set("quotes:market", {"sh000001": 3000.5})
        cache.set("quotes:market", {"sh000001": 3100.0})
        result = cache.get("quotes:market")
        assert result == {"sh000001": 3100.0}

    def test_get_nonexistent_returns_none(self, cache: RedisCache):
        assert cache.get("nonexistent_key") is None

    def test_delete_removes_key(self, cache: RedisCache):
        cache.set("quotes:market", {"sh000001": 3000.5})
        cache.delete("quotes:market")
        assert cache.get("quotes:market") is None


class TestRedisCacheRealTTL:
    """TR-008-BE-002: 真实 Redis TTL 验证。"""

    def test_ttl_expires(self, cache: RedisCache):
        cache.set("quotes:market", {"sh000001": 3000.5}, ttl_seconds=1)
        assert cache.get("quotes:market") == {"sh000001": 3000.5}
        import time

        time.sleep(1.5)
        assert cache.get("quotes:market") is None

    def test_default_ttl_60s(self, cache: RedisCache, real_redis):
        cache.set("quotes:market", {"sh000001": 3000.5})
        ttl = real_redis.ttl("quotes:market")
        assert ttl == 60


class TestRedisCacheRealJSON:
    """TR-008-BE-003: 真实 Redis JSON 序列化/反序列化验证。"""

    def test_complex_object_roundtrip(self, cache: RedisCache):
        data = {
            "code": "600519",
            "price": 1800.5,
            "change_pct": 2.5,
            "nested": {"level": 1, "items": ["a", "b"]},
        }
        cache.set("quote:600519", data)
        result = cache.get("quote:600519")
        assert result == data

    def test_list_roundtrip(self, cache: RedisCache):
        data = [
            {"code": "600000", "price": 10.5},
            {"code": "600519", "price": 1800.5},
        ]
        cache.set("quotes:watchlist", data)
        result = cache.get("quotes:watchlist")
        assert result == data

    def test_quote_schema_roundtrip(self, cache: RedisCache):
        """验证与生产一致的数据结构可正确序列化。"""
        from datetime import UTC, datetime

        quote_data = {
            "stock_code": "600519",
            "stock_name": "贵州茅台",
            "current_price": 1800.5,
            "change_percent": 2.5,
            "change_amount": 43.9,
            "updated_at": datetime.now(UTC).isoformat(),
            "status": "normal",
            "source_status": "cached",
        }
        cache.set("quotes:watchlist:600519", [quote_data])
        result = cache.get("quotes:watchlist:600519")
        assert len(result) == 1
        assert result[0]["stock_code"] == "600519"
        assert result[0]["current_price"] == 1800.5


class TestRedisCacheRealDegradation:
    """TR-008-BE-004: 真实 Redis 连接异常降级验证。"""

    def test_none_client_degrades_gracefully(self):
        """redis_cache=None 时所有操作返回 None 不抛异常。"""
        cache = RedisCache(client=None)
        assert cache.get("any_key") is None
        assert cache.set("any_key", {"data": 1}) is None
        assert cache.delete("any_key") is None

    def test_closed_client_degrades_gracefully(self):
        """Redis 连接被关闭后降级为 None 不抛异常。"""
        from redis import Redis

        client = Redis(host="127.0.0.1", port=65535, socket_connect_timeout=0.1)
        cache = RedisCache(client=client)
        assert cache.get("any_key") is None
        assert cache.set("any_key", {"data": 1}) is None


class TestRedisCacheRealKeyNaming:
    """TR-008-BE-005: 真实 Redis key 命名规范验证。"""

    def test_market_index_key(self, cache: RedisCache):
        cache.set("quotes:market", {"sh000001": 3000.5})
        assert cache.get("quotes:market") is not None

    def test_watchlist_key_with_hash(self, cache: RedisCache):
        cache.set("quotes:watchlist:abc123", [{"code": "600000"}])
        assert cache.get("quotes:watchlist:abc123") is not None
