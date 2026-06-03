"""容灾端到端集成测试 — 完整故障→切换→恢复→切回→缓存链路。

覆盖 US-1 / US-2 全部验收场景。
"""

from unittest.mock import patch

import pytest

from backend.app.core.circuit_breaker import CircuitBreaker, CircuitState
from backend.app.database import Base, SessionLocal, engine
from backend.app.models.cache_entry import CacheEntry
from backend.app.models.data_source_status import DataSourceStatus
from backend.app.schemas.data_fetch import DataFetchResult
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
    return DataSourceFacade(
        db=db,
        primary=AkShareDataSource(),
        fallback=BaoStockDataSource(),
    )


class TestUserStory1_Failover:
    """US-1: 主数据源故障时自动切换。"""

    def test_ac1_primary_normal_returns_primary(self, facade: DataSourceFacade, db):
        """AC1: 主源正常 → 返回 primary。"""
        with patch.object(
            facade._primary, "fetch_realtime",
            return_value={"600519": {"name": "贵州茅台", "price": 1800.0, "change_pct": 1.23}},
        ):
            result = facade.fetch_realtime(["600519"])

        assert result.status == "primary"
        assert result.source == "akshare"

    def test_ac2_primary_timeout_switches_to_fallback(self, facade: DataSourceFacade, db):
        """AC2: 主源超时 → 自动尝试备源 → 返回 fallback，触发切换通知（日志）。"""
        with patch.object(
            facade._primary, "fetch_realtime",
            side_effect=DataSourceError("timeout", "AkShare timeout"),
        ):
            with patch.object(
                facade._fallback, "fetch_realtime",
                return_value={"600519": {"name": "贵州茅台", "price": 1800.0, "change_pct": 1.23}},
            ):
                result = facade.fetch_realtime(["600519"])

        assert result.status == "fallback"
        assert result.source == "baostock"
        assert "600519" in result.data

    def test_ac3_three_failures_opens_circuit(self, facade: DataSourceFacade, db):
        """AC3: 主源连续 3 次失败 → 标记为不可用，后续不再尝试 AkShare。"""
        with patch.object(
            facade._primary, "fetch_realtime",
            side_effect=DataSourceError("timeout", "AkShare timeout"),
        ):
            with patch.object(
                facade._fallback, "fetch_realtime",
                return_value={"600519": {"name": "贵州茅台", "price": 1800.0}},
            ):
                # 第 1 次
                facade.fetch_realtime(["600519"])
                # 第 2 次
                facade.fetch_realtime(["600519"])
                # 第 3 次
                facade.fetch_realtime(["600519"])

        # 第 4 次请求，AkShare 应为 OPEN
        assert facade._circuit_breaker.get_state("akshare") == CircuitState.OPEN

        call_count = [0]

        def track_primary(*args, **kwargs):
            call_count[0] += 1
            raise DataSourceError("timeout", "should not be called")

        with patch.object(facade._primary, "fetch_realtime", side_effect=track_primary):
            with patch.object(
                facade._fallback, "fetch_realtime",
                return_value={"600519": {"name": "贵州茅台", "price": 1800.0}},
            ):
                result = facade.fetch_realtime(["600519"])

        assert result.status == "fallback"
        assert call_count[0] == 0  # 主源熔断后不再被调用

    def test_ac4_health_check_restores_primary(self, facade: DataSourceFacade, db):
        """AC4: 主源不可用后，健康检查连续 2 次成功 → 恢复可用。"""
        # 先熔断主源
        for _ in range(3):
            facade._circuit_breaker.record_failure("akshare", error="timeout")
        assert facade._circuit_breaker.get_state("akshare") == CircuitState.OPEN

        # 模拟健康检查：连续 3 次探测成功
        # OPEN → HALF_OPEN (第1次, cs=0)
        # HALF_OPEN 第1次成功 (第2次, cs=1) < recovery_threshold=2
        # HALF_OPEN 第2次成功 (第3次, cs=2) ≥ recovery_threshold=2 → CLOSED
        with patch.object(
            facade._primary, "fetch_realtime",
            return_value={"000001": {"name": "平安银行", "price": 10.0}},
        ):
            facade._circuit_breaker.record_probe_success("akshare")
            facade._circuit_breaker.record_probe_success("akshare")
            facade._circuit_breaker.record_probe_success("akshare")

        assert facade._circuit_breaker.get_state("akshare") == CircuitState.CLOSED

        # 恢复后，主源应再次被优先使用
        with patch.object(
            facade._primary, "fetch_realtime",
            return_value={"600519": {"name": "贵州茅台", "price": 1800.0}},
        ):
            result = facade.fetch_realtime(["600519"])

        assert result.status == "primary"


class TestUserStory2_CacheFallback:
    """US-2: 全部数据源故障时提供缓存数据。"""

    def test_ac1_both_fail_with_cache_returns_cached(self, facade: DataSourceFacade, db):
        """AC1: 双源故障 + 有缓存 → 返回 cached。"""
        # 先通过主源写入缓存
        with patch.object(
            facade._primary, "fetch_realtime",
            return_value={"600519": {"name": "贵州茅台", "price": 1800.0}},
        ):
            facade.fetch_realtime(["600519"])

        # 双源故障
        with patch.object(
            facade._primary, "fetch_realtime",
            side_effect=DataSourceError("timeout", "AkShare down"),
        ):
            with patch.object(
                facade._fallback, "fetch_realtime",
                side_effect=DataSourceError("timeout", "BaoStock down"),
            ):
                result = facade.fetch_realtime(["600519"])

        assert result.status == "cached"
        assert result.source == "cache"
        assert result.data is not None
        assert result.data["600519"]["name"] == "贵州茅台"

    def test_ac2_both_fail_no_cache_returns_unavailable(self, facade: DataSourceFacade, db):
        """AC2: 双源故障 + 缓存过期 → 返回 unavailable。"""
        with patch.object(
            facade._primary, "fetch_realtime",
            side_effect=DataSourceError("timeout", "AkShare down"),
        ):
            with patch.object(
                facade._fallback, "fetch_realtime",
                side_effect=DataSourceError("timeout", "BaoStock down"),
            ):
                result = facade.fetch_realtime(["600519"])

        assert result.status == "unavailable"
        assert result.data is None
        assert result.source is None

    def test_ac3_recovery_from_cache_mode(self, facade: DataSourceFacade, db):
        """AC3: 缓存模式下任意源恢复 → 自动使用恢复的数据源。"""
        # 先写入缓存（通过主源）
        with patch.object(
            facade._primary, "fetch_realtime",
            return_value={"600519": {"name": "贵州茅台", "price": 1800.0}},
        ):
            facade.fetch_realtime(["600519"])

        # 双源故障 → cached
        with patch.object(
            facade._primary, "fetch_realtime",
            side_effect=DataSourceError("timeout", "AkShare down"),
        ):
            with patch.object(
                facade._fallback, "fetch_realtime",
                side_effect=DataSourceError("timeout", "BaoStock down"),
            ):
                result = facade.fetch_realtime(["600519"])
        assert result.status == "cached"

        # 备源恢复
        with patch.object(
            facade._primary, "fetch_realtime",
            side_effect=DataSourceError("timeout", "AkShare still down"),
        ):
            with patch.object(
                facade._fallback, "fetch_realtime",
                return_value={"600519": {"name": "贵州茅台", "price": 1850.0}},
            ):
                result = facade.fetch_realtime(["600519"])

        assert result.status == "fallback"
        assert result.data["600519"]["price"] == 1850.0
