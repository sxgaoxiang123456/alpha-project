"""健康检查器 — 定时探测数据源可用性，驱动熔断器状态恢复。"""

import logging
from datetime import datetime, timezone

from backend.app.core.circuit_breaker import CircuitBreaker, CircuitState
from backend.app.services.data_source import DataSource, DataSourceError

logger = logging.getLogger(__name__)


class HealthChecker:
    """定时健康检查任务，每 5 分钟探测各数据源。"""

    PROBE_CODES = ["000001"]  # 轻量级探测：查询单只股票

    def __init__(
        self,
        circuit_breaker: CircuitBreaker,
        primary: DataSource,
        fallback: DataSource,
    ):
        self._circuit_breaker = circuit_breaker
        self._primary = primary
        self._fallback = fallback

    def check_all(self) -> None:
        """探测所有数据源并更新熔断器状态。"""
        self._check_one("akshare", self._primary)
        self._check_one("baostock", self._fallback)

    def _check_one(self, name: str, source: DataSource) -> None:
        """探测单个数据源。"""
        state = self._circuit_breaker.get_state(name)
        start_at = datetime.now(timezone.utc)

        try:
            source.fetch_realtime(self.PROBE_CODES)
            success = True
            error_msg = None
        except DataSourceError as exc:
            success = False
            error_msg = f"[{exc.error_type}] {exc.message}"
        except Exception as exc:
            success = False
            error_msg = str(exc)

        elapsed_ms = (datetime.now(timezone.utc) - start_at).total_seconds() * 1000

        # 更新熔断器
        if success:
            if state == CircuitState.OPEN:
                self._circuit_breaker.record_probe_success(name)
            elif state == CircuitState.HALF_OPEN:
                self._circuit_breaker.record_probe_success(name)
            else:
                # CLOSED: 刷新成功时间，不切换状态
                self._circuit_breaker.record_success(name)
        else:
            if state == CircuitState.HALF_OPEN:
                self._circuit_breaker.record_probe_failure(name, error=error_msg or "probe_failed")
            else:
                self._circuit_breaker.record_failure(name, error=error_msg or "probe_failed")

        # 结构化日志
        log_entry = {
            "event": "health_check",
            "source": name,
            "result": "success" if success else "failure",
            "response_time_ms": round(elapsed_ms, 2),
            "error": error_msg,
            "timestamp": start_at.isoformat(),
        }
        logger.info(log_entry)
