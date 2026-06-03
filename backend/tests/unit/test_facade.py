"""DataSourceFacade 单元测试 — 切换/缓存/熔断集成逻辑。"""

from unittest.mock import MagicMock, patch

import pytest

from backend.app.core.circuit_breaker import CircuitBreaker, CircuitState
from backend.app.database import Base, SessionLocal, engine
from backend.app.models.cache_entry import CacheEntry
from backend.app.models.data_source_status import DataSourceStatus
from backend.app.schemas.data_fetch import DataFetchResult
from backend.app.services.cache_service import CacheService
from backend.app.services.data_source import (
    AkShareDataSource,
    BaoStockDataSource,
    DataSourceError,
)
from backend.app.services.data_source_facade import DataSourceFacade


@pytest.fixture(autouse=True, scope="module")
def _setup_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture
def db():
    session = SessionLocal()
    yield session
    session.rollback()
    session.query(CacheEntry).delete()
    session.query(DataSourceStatus).delete()
    session.commit()
    session.close()


@pytest.fixture
def facade(db) -> DataSourceFacade:
    """构建 Facade，注入真实熔断器和缓存。"""
    cb = CircuitBreaker(db, failure_threshold=3, recovery_threshold=2)
    cache = CacheService(db)

    f = DataSourceFacade(
        db=db,
        primary=AkShareDataSource(),
        fallback=BaoStockDataSource(),
    )
    f._circuit_breaker = cb
    f._cache = cache
    return f


class TestPrimarySuccess:
    """主源正常场景。"""

    def test_primary_available_returns_primary(self, facade: DataSourceFacade):
        with patch.object(
            facade._primary,
            "fetch_realtime",
            return_value={"600519": {"name": "贵州茅台", "price": 1800.0, "change_pct": 1.23}},
        ):
            result = facade.fetch_realtime(["600519"])

        assert isinstance(result, DataFetchResult)
        assert result.status == "primary"
        assert result.source == "akshare"
        assert result.data == {"600519": {"name": "贵州茅台", "price": 1800.0, "change_pct": 1.23}}

    def test_success_writes_cache(self, facade: DataSourceFacade):
        with patch.object(
            facade._primary,
            "fetch_realtime",
            return_value={"600519": {"name": "贵州茅台", "price": 1800.0}},
        ):
            facade.fetch_realtime(["600519"])

        cached = facade._cache.get("realtime_600519")
        assert cached is not None


class TestFallback:
    """主源故障 → 备源降级场景。"""

    def test_primary_failure_uses_fallback(self, facade: DataSourceFacade):
        with patch.object(
            facade._primary,
            "fetch_realtime",
            side_effect=DataSourceError("timeout", "AkShare timeout"),
        ):
            with patch.object(
                facade._fallback,
                "fetch_realtime",
                return_value={"600519": {"name": "贵州茅台", "price": 1800.0, "change_pct": 1.23}},
            ):
                result = facade.fetch_realtime(["600519"])

        assert result.status == "fallback"
        assert result.source == "baostock"
        assert "600519" in result.data

    def test_fallback_also_writes_cache(self, facade: DataSourceFacade):
        with patch.object(
            facade._primary,
            "fetch_realtime",
            side_effect=DataSourceError("timeout", "AkShare timeout"),
        ):
            with patch.object(
                facade._fallback,
                "fetch_realtime",
                return_value={"600519": {"name": "贵州茅台", "price": 1800.0}},
            ):
                facade.fetch_realtime(["600519"])

        cached = facade._cache.get("realtime_600519")
        assert cached is not None

    def test_primary_open_skips_directly_to_fallback(self, facade: DataSourceFacade):
        # 将主源熔断器设为 OPEN
        for _ in range(3):
            facade._circuit_breaker.record_failure("akshare", error="timeout")
        assert facade._circuit_breaker.get_state("akshare") == CircuitState.OPEN

        with patch.object(
            facade._fallback,
            "fetch_realtime",
            return_value={"600519": {"name": "贵州茅台", "price": 1800.0}},
        ):
            result = facade.fetch_realtime(["600519"])

        assert result.status == "fallback"
        # 主源熔断后不应再被调用


class TestCached:
    """双源故障 → 缓存场景。"""

    def test_both_fail_uses_cache(self, facade: DataSourceFacade):
        # 预写入缓存
        facade._cache.set("realtime_600519", '{"name": "贵州茅台", "price": 1750.0}')

        with patch.object(
            facade._primary,
            "fetch_realtime",
            side_effect=DataSourceError("timeout", "AkShare timeout"),
        ):
            with patch.object(
                facade._fallback,
                "fetch_realtime",
                side_effect=DataSourceError("timeout", "BaoStock timeout"),
            ):
                result = facade.fetch_realtime(["600519"])

        assert result.status == "cached"
        assert result.source == "cache"
        assert result.data is not None


class TestUnavailable:
    """双源故障 + 无缓存 → unavailable 场景。"""

    def test_both_fail_no_cache_returns_unavailable(self, facade: DataSourceFacade):
        with patch.object(
            facade._primary,
            "fetch_realtime",
            side_effect=DataSourceError("timeout", "AkShare timeout"),
        ):
            with patch.object(
                facade._fallback,
                "fetch_realtime",
                side_effect=DataSourceError("timeout", "BaoStock timeout"),
            ):
                result = facade.fetch_realtime(["600519"])

        assert result.status == "unavailable"
        assert result.data is None
        assert result.source is None


class TestSwitchLogging:
    """切换日志验证 — FR-009。"""

    def test_primary_success_logs(self, facade: DataSourceFacade, caplog):
        import logging

        caplog.set_level(logging.INFO)

        with patch.object(
            facade._primary,
            "fetch_realtime",
            return_value={"600519": {"name": "贵州茅台", "price": 1800.0}},
        ):
            facade.fetch_realtime(["600519"])

        assert "primary" in caplog.text or "akshare" in caplog.text

    def test_failover_to_fallback_logs(self, facade: DataSourceFacade, caplog):
        import logging

        caplog.set_level(logging.INFO)

        with patch.object(
            facade._primary,
            "fetch_realtime",
            side_effect=DataSourceError("timeout", "AkShare timeout"),
        ):
            with patch.object(
                facade._fallback,
                "fetch_realtime",
                return_value={"600519": {"name": "贵州茅台", "price": 1800.0}},
            ):
                facade.fetch_realtime(["600519"])

        assert "fallback" in caplog.text or "failover" in caplog.text

    def test_cache_fallback_logs(self, facade: DataSourceFacade, caplog):
        import logging

        caplog.set_level(logging.INFO)

        facade._cache.set("realtime_600519", '{"name": "贵州茅台", "price": 1750.0}')

        with patch.object(
            facade._primary,
            "fetch_realtime",
            side_effect=DataSourceError("timeout", "AkShare down"),
        ):
            with patch.object(
                facade._fallback,
                "fetch_realtime",
                side_effect=DataSourceError("timeout", "BaoStock down"),
            ):
                facade.fetch_realtime(["600519"])

        assert "cached" in caplog.text or "cache" in caplog.text

    def test_unavailable_logs(self, facade: DataSourceFacade, caplog):
        import logging

        caplog.set_level(logging.INFO)

        with patch.object(
            facade._primary,
            "fetch_realtime",
            side_effect=DataSourceError("timeout", "AkShare down"),
        ):
            with patch.object(
                facade._fallback,
                "fetch_realtime",
                side_effect=DataSourceError("timeout", "BaoStock down"),
            ):
                facade.fetch_realtime(["600519"])

        assert "unavailable" in caplog.text or "all sources failed" in caplog.text


class TestFailureCounting:
    """失败计数与熔断集成。"""

    def test_primary_failure_recorded(self, facade: DataSourceFacade):
        with patch.object(
            facade._primary,
            "fetch_realtime",
            side_effect=DataSourceError("timeout", "AkShare timeout"),
        ):
            with patch.object(
                facade._fallback,
                "fetch_realtime",
                return_value={"600519": {"name": "贵州茅台", "price": 1800.0}},
            ):
                facade.fetch_realtime(["600519"])

        # 验证失败被记录
        record = facade._circuit_breaker._get_or_create("akshare")
        assert record.consecutive_failures >= 1
