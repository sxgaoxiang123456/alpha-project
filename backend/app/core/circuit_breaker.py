"""熔断器 — 数据源连续失败熔断与恢复。

状态机: Closed → (3次失败) → Open → (探测成功) → Half-Open → (2次成功) → Closed
         ↑________________________________________(探测失败)_________________|
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from sqlalchemy.orm import Session

from backend.app.models.data_source_status import DataSourceStatus


class CircuitState(Enum):
    """熔断器状态。"""

    CLOSED = "closed"       # 正常，允许请求
    OPEN = "open"           # 熔断，禁止请求
    HALF_OPEN = "half_open"  # 探测中，仅允许探测请求


class CircuitBreaker:
    """数据源熔断器，状态持久化到 SQLite。"""

    def __init__(
        self,
        db: Session,
        failure_threshold: int = 3,
        recovery_threshold: int = 2,
    ):
        self.db = db
        self.failure_threshold = failure_threshold
        self.recovery_threshold = recovery_threshold

    def _get_or_create(self, name: str) -> DataSourceStatus:
        record = self.db.get(DataSourceStatus, name)
        if record is None:
            record = DataSourceStatus(name=name, status=CircuitState.CLOSED.value)
            self.db.add(record)
            self.db.commit()
        return record

    def get_state(self, name: str) -> CircuitState:
        record = self._get_or_create(name)
        try:
            return CircuitState(record.status)
        except ValueError:
            return CircuitState.CLOSED

    def can_execute(self, name: str, *, is_probe: bool = False) -> bool:
        state = self.get_state(name)
        if state == CircuitState.CLOSED:
            return True
        if state == CircuitState.OPEN:
            return False
        if state == CircuitState.HALF_OPEN:
            return is_probe
        return True

    def record_success(self, name: str) -> None:
        record = self._get_or_create(name)
        record.consecutive_failures = 0
        record.last_success_at = datetime.now(timezone.utc)
        self.db.commit()

    def record_failure(self, name: str, error: str) -> None:
        record = self._get_or_create(name)
        record.consecutive_failures += 1
        record.last_failure_at = datetime.now(timezone.utc)
        record.last_error = error

        if record.consecutive_failures >= self.failure_threshold:
            record.status = CircuitState.OPEN.value

        self.db.commit()

    def record_probe_success(self, name: str) -> None:
        record = self._get_or_create(name)
        if record.status != CircuitState.HALF_OPEN.value:
            # 首次探测: Open → Half-Open, 成功计数从 0 开始（不计入 recovery）
            record.status = CircuitState.HALF_OPEN.value
            record.consecutive_successes = 0
        else:
            # Half-Open 状态下的成功才计入 recovery
            record.consecutive_successes += 1
            if record.consecutive_successes >= self.recovery_threshold:
                record.status = CircuitState.CLOSED.value
                record.consecutive_failures = 0
                record.consecutive_successes = 0

        record.last_success_at = datetime.now(timezone.utc)
        self.db.commit()

    def record_probe_failure(self, name: str, error: str) -> None:
        record = self._get_or_create(name)
        record.status = CircuitState.OPEN.value
        record.consecutive_failures += 1
        record.last_failure_at = datetime.now(timezone.utc)
        record.last_error = error
        record.consecutive_successes = 0
        self.db.commit()
