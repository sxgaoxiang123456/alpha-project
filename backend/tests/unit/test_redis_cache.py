"""Redis 缓存封装单元测试 — 正常读写、TTL、连接降级、JSON 序列化。"""

import json
import pytest
from fakeredis import FakeRedis

from backend.app.core.redis_cache import RedisCache


@pytest.fixture
def fake_redis():
    return FakeRedis(decode_responses=True)


@pytest.fixture
def cache(fake_redis):
    return RedisCache(client=fake_redis)


class TestRedisCacheReadWrite:
    """正常读写测试。"""

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


class TestRedisCacheTTL:
    """TTL 过期测试。"""

    def test_ttl_expires(self, cache: RedisCache, fake_redis: FakeRedis):
        cache.set("quotes:market", {"sh000001": 3000.5}, ttl_seconds=1)
        assert cache.get("quotes:market") == {"sh000001": 3000.5}
        fake_redis.expire("quotes:market", 0)
        assert cache.get("quotes:market") is None

    def test_default_ttl(self, cache: RedisCache, fake_redis: FakeRedis):
        cache.set("quotes:market", {"sh000001": 3000.5})
        ttl = fake_redis.ttl("quotes:market")
        assert ttl == 60


class TestRedisCacheJSON:
    """JSON 序列化/反序列化测试。"""

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
        data = [{"code": "600000", "price": 10.5}, {"code": "600519", "price": 1800.5}]
        cache.set("quotes:watchlist", data)
        result = cache.get("quotes:watchlist")
        assert result == data


class TestRedisCacheDegradation:
    """连接异常降级测试 — Redis 不可用时所有操作返回 None 且不抛异常。"""

    def test_get_when_redis_unavailable_returns_none(self, monkeypatch):
        broken_client = FakeRedis(decode_responses=True)
        monkeypatch.setattr(broken_client, "get", lambda key: (_ for _ in ()).throw(ConnectionError("Connection refused")))
        cache = RedisCache(client=broken_client)
        assert cache.get("any_key") is None

    def test_set_when_redis_unavailable_returns_none(self, monkeypatch):
        broken_client = FakeRedis(decode_responses=True)
        monkeypatch.setattr(broken_client, "set", lambda *a, **k: (_ for _ in ()).throw(ConnectionError("Connection refused")))
        cache = RedisCache(client=broken_client)
        assert cache.set("any_key", {"data": 1}) is None

    def test_delete_when_redis_unavailable_returns_none(self, monkeypatch):
        broken_client = FakeRedis(decode_responses=True)
        monkeypatch.setattr(broken_client, "delete", lambda *a: (_ for _ in ()).throw(ConnectionError("Connection refused")))
        cache = RedisCache(client=broken_client)
        assert cache.delete("any_key") is None

    def test_none_client_degrades_gracefully(self):
        cache = RedisCache(client=None)
        assert cache.get("any_key") is None
        assert cache.set("any_key", {"data": 1}) is None
        assert cache.delete("any_key") is None


class TestRedisCacheKeyNaming:
    """缓存 key 命名规范测试。"""

    def test_market_index_key(self, cache: RedisCache):
        cache.set("quotes:market", {"sh000001": 3000.5})
        assert cache.get("quotes:market") is not None

    def test_watchlist_key_with_hash(self, cache: RedisCache):
        cache.set("quotes:watchlist:abc123", [{"code": "600000"}])
        assert cache.get("quotes:watchlist:abc123") is not None
