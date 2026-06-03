"""HealthChecker 单元测试 — 定时探测与熔断器状态恢复。"""

from unittest.mock import MagicMock, patch

import pytest

from backend.app.core.circuit_breaker import CircuitBreaker, CircuitState
from backend.app.core.health_checker import HealthChecker
from backend.app.database import Base, SessionLocal, engine
from backend.app.models.data_source_status import DataSourceStatus
from backend.app.services.data_source import (
    AkShareDataSource,
    BaoStockDataSource,
    DataSourceError,
)


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
    session.query(DataSourceStatus).delete()
    session.commit()
    session.close()


@pytest.fixture
def checker(db) -> HealthChecker:
    cb = CircuitBreaker(db, failure_threshold=3, recovery_threshold=2)
    return HealthChecker(
        circuit_breaker=cb,
        primary=AkShareDataSource(),
        fallback=BaoStockDataSource(),
    )


class TestCheckPrimary:
    """主源健康检查测试。"""

    def test_closed_source_success_stays_closed(self, checker: HealthChecker, db):
        """CLOSED 状态探测成功应保持 CLOSED。"""
        assert checker._circuit_breaker.get_state("akshare") == CircuitState.CLOSED

        with patch.object(
            checker._primary,
            "fetch_realtime",
            return_value={"000001": {"name": "平安银行", "price": 10.0}},
        ):
            checker.check_all()

        assert checker._circuit_breaker.get_state("akshare") == CircuitState.CLOSED

    def test_open_source_success_goes_half_open(self, checker: HealthChecker, db):
        """OPEN 状态探测成功应进入 HALF_OPEN。"""
        # 先熔断主源
        for _ in range(3):
            checker._circuit_breaker.record_failure("akshare", error="timeout")
        assert checker._circuit_breaker.get_state("akshare") == CircuitState.OPEN

        with patch.object(
            checker._primary,
            "fetch_realtime",
            return_value={"000001": {"name": "平安银行", "price": 10.0}},
        ):
            checker.check_all()

        assert checker._circuit_breaker.get_state("akshare") == CircuitState.HALF_OPEN

    def test_open_source_two_successes_restores_closed(self, checker: HealthChecker, db):
        """OPEN 状态连续 2 次探测成功应恢复 CLOSED。"""
        for _ in range(3):
            checker._circuit_breaker.record_failure("akshare", error="timeout")
        assert checker._circuit_breaker.get_state("akshare") == CircuitState.OPEN

        with patch.object(
            checker._primary,
            "fetch_realtime",
            return_value={"000001": {"name": "平安银行", "price": 10.0}},
        ):
            checker.check_all()  # OPEN → HALF_OPEN
            checker.check_all()  # HALF_OPEN 第 1 次成功
            checker.check_all()  # HALF_OPEN 第 2 次成功 → CLOSED

        assert checker._circuit_breaker.get_state("akshare") == CircuitState.CLOSED

    def test_open_source_failure_stays_open(self, checker: HealthChecker, db):
        """OPEN 状态探测失败应保持 OPEN。"""
        for _ in range(3):
            checker._circuit_breaker.record_failure("akshare", error="timeout")
        assert checker._circuit_breaker.get_state("akshare") == CircuitState.OPEN

        with patch.object(
            checker._primary,
            "fetch_realtime",
            side_effect=DataSourceError("timeout", "still down"),
        ):
            checker.check_all()

        assert checker._circuit_breaker.get_state("akshare") == CircuitState.OPEN


class TestCheckFallback:
    """备源健康检查测试。"""

    def test_fallback_checked(self, checker: HealthChecker, db):
        with patch.object(
            checker._fallback,
            "fetch_realtime",
            return_value={"000001": {"name": "平安银行", "price": 10.0}},
        ):
            checker.check_all()

        # 备源应保持 CLOSED
        assert checker._circuit_breaker.get_state("baostock") == CircuitState.CLOSED


class TestLogging:
    """日志输出测试。"""

    def test_success_logged(self, checker: HealthChecker, caplog):
        import logging

        caplog.set_level(logging.INFO)

        with patch.object(
            checker._primary,
            "fetch_realtime",
            return_value={"000001": {"name": "平安银行", "price": 10.0}},
        ):
            with patch.object(
                checker._fallback,
                "fetch_realtime",
                return_value={"000001": {"name": "平安银行", "price": 10.0}},
            ):
                checker.check_all()

        assert "health_check" in caplog.text or "akshare" in caplog.text

    def test_failure_logged(self, checker: HealthChecker, caplog):
        import logging

        caplog.set_level(logging.INFO)

        with patch.object(
            checker._primary,
            "fetch_realtime",
            side_effect=DataSourceError("timeout", "down"),
        ):
            with patch.object(
                checker._fallback,
                "fetch_realtime",
                return_value={"000001": {"name": "平安银行", "price": 10.0}},
            ):
                checker.check_all()

        assert "timeout" in caplog.text or "failed" in caplog.text
