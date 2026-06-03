"""熔断器单元测试 — 状态转换、持久化恢复、并发安全。"""

import pytest
from sqlalchemy.orm import Session

from backend.app.core.circuit_breaker import CircuitBreaker, CircuitState
from backend.app.database import Base, SessionLocal, engine
from backend.app.models.data_source_status import DataSourceStatus


@pytest.fixture(autouse=True, scope="module")
def _setup_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture
def db() -> Session:
    session = SessionLocal()
    yield session
    session.rollback()
    # 清理熔断器状态表
    session.query(DataSourceStatus).delete()
    session.commit()
    session.close()


@pytest.fixture
def cb(db: Session) -> CircuitBreaker:
    return CircuitBreaker(db, failure_threshold=3, recovery_threshold=2)


class TestClosedState:
    """Closed 状态测试 — 正常服务。"""

    def test_initial_state_is_closed(self, cb: CircuitBreaker, db: Session):
        assert cb.get_state("akshare") == CircuitState.CLOSED
        assert cb.can_execute("akshare") is True

    def test_single_failure_stays_closed(self, cb: CircuitBreaker, db: Session):
        cb.record_failure("akshare", error="timeout")
        assert cb.get_state("akshare") == CircuitState.CLOSED
        assert cb.can_execute("akshare") is True

    def test_two_failures_stay_closed(self, cb: CircuitBreaker, db: Session):
        cb.record_failure("akshare", error="timeout")
        cb.record_failure("akshare", error="timeout")
        assert cb.get_state("akshare") == CircuitState.CLOSED

    def test_three_failures_opens_circuit(self, cb: CircuitBreaker, db: Session):
        cb.record_failure("akshare", error="timeout")
        cb.record_failure("akshare", error="timeout")
        cb.record_failure("akshare", error="timeout")
        assert cb.get_state("akshare") == CircuitState.OPEN
        assert cb.can_execute("akshare") is False

    def test_success_resets_failure_count(self, cb: CircuitBreaker, db: Session):
        cb.record_failure("akshare", error="timeout")
        cb.record_failure("akshare", error="timeout")
        cb.record_success("akshare")
        assert cb.get_state("akshare") == CircuitState.CLOSED
        # 第 3 次失败才 open
        cb.record_failure("akshare", error="timeout")
        assert cb.get_state("akshare") == CircuitState.CLOSED


class TestOpenState:
    """Open 状态测试 — 熔断后。"""

    def _open_circuit(self, cb: CircuitBreaker):
        for _ in range(3):
            cb.record_failure("akshare", error="timeout")
        assert cb.get_state("akshare") == CircuitState.OPEN

    def test_open_blocks_execution(self, cb: CircuitBreaker, db: Session):
        self._open_circuit(cb)
        assert cb.can_execute("akshare") is False

    def test_open_allows_probe(self, cb: CircuitBreaker, db: Session):
        self._open_circuit(cb)
        # Half-Open 状态下仅允许探测
        cb.record_probe_success("akshare")
        assert cb.get_state("akshare") == CircuitState.HALF_OPEN

    def test_failure_count_persisted(self, cb: CircuitBreaker, db: Session):
        self._open_circuit(cb)
        record = db.get(DataSourceStatus, "akshare")
        assert record is not None
        assert record.consecutive_failures == 3
        assert record.status == "open"


class TestHalfOpenState:
    """Half-Open 状态测试 — 探测恢复。"""

    def _half_open_circuit(self, cb: CircuitBreaker):
        for _ in range(3):
            cb.record_failure("akshare", error="timeout")
        cb.record_probe_success("akshare")
        assert cb.get_state("akshare") == CircuitState.HALF_OPEN

    def test_single_probe_success_stays_half_open(self, cb: CircuitBreaker, db: Session):
        self._half_open_circuit(cb)
        cb.record_probe_success("akshare")
        # 需要连续 2 次成功才恢复 closed
        assert cb.get_state("akshare") == CircuitState.HALF_OPEN

    def test_two_probe_successes_closes_circuit(self, cb: CircuitBreaker, db: Session):
        self._half_open_circuit(cb)
        cb.record_probe_success("akshare")
        cb.record_probe_success("akshare")
        assert cb.get_state("akshare") == CircuitState.CLOSED
        assert cb.can_execute("akshare") is True

    def test_probe_failure_reopens_circuit(self, cb: CircuitBreaker, db: Session):
        self._half_open_circuit(cb)
        cb.record_probe_failure("akshare", error="timeout")
        assert cb.get_state("akshare") == CircuitState.OPEN


class TestPersistence:
    """持久化恢复测试。"""

    def test_state_recovered_from_db(self, db: Session):
        # 先在一个熔断器实例中制造 open 状态
        cb1 = CircuitBreaker(db, failure_threshold=3, recovery_threshold=2)
        for _ in range(3):
            cb1.record_failure("akshare", error="timeout")

        # 新建另一个实例，应能恢复状态
        db2 = SessionLocal()
        cb2 = CircuitBreaker(db2, failure_threshold=3, recovery_threshold=2)
        assert cb2.get_state("akshare") == CircuitState.OPEN
        db2.close()

    def test_record_tracks_last_error(self, cb: CircuitBreaker, db: Session):
        cb.record_failure("akshare", error="rate_limited")
        record = db.get(DataSourceStatus, "akshare")
        assert record.last_error == "rate_limited"

    def test_success_updates_last_success_at(self, cb: CircuitBreaker, db: Session):
        from datetime import datetime, timezone

        cb.record_success("akshare")

        record = db.get(DataSourceStatus, "akshare")
        assert record.last_success_at is not None
        assert isinstance(record.last_success_at, datetime)
        # 只验证时间戳在合理范围内（前后 5 秒）
        now_ts = datetime.now(timezone.utc).timestamp()
        record_ts = record.last_success_at.replace(tzinfo=timezone.utc).timestamp()
        assert abs(now_ts - record_ts) < 5
