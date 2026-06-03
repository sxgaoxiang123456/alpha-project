"""数据源 Facade — 对外统一接口，内部管理切换/缓存/熔断。

调用方通过此 facade 获取数据，完全无感知底层数据源状态。
"""

import json
import logging
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from backend.app.core.circuit_breaker import CircuitBreaker
from backend.app.schemas.data_fetch import DataFetchResult
from backend.app.services.cache_service import CacheService
from backend.app.services.data_source import (
    AkShareDataSource,
    BaoStockDataSource,
    DataSource,
    DataSourceError,
)

logger = logging.getLogger(__name__)


class DataSourceFacade:
    """数据源门面，封装多源容灾逻辑。"""

    def __init__(
        self,
        db: Session,
        primary: DataSource | None = None,
        fallback: DataSource | None = None,
    ):
        self.db = db
        self._primary = primary or AkShareDataSource()
        self._fallback = fallback or BaoStockDataSource()
        self._circuit_breaker = CircuitBreaker(db)
        self._cache = CacheService(db)

    def fetch_realtime(self, codes: list[str]) -> DataFetchResult:
        """获取实时行情，内部自动处理切换/缓存/熔断。"""
        start_at = datetime.utcnow()

        # 1. 尝试主源（如果熔断器允许）
        if self._circuit_breaker.can_execute("akshare"):
            try:
                data = self._primary.fetch_realtime(codes)
                self._circuit_breaker.record_success("akshare")
                self._cache_set(codes, data)
                result = self._build_result("primary", data, "akshare", start_at)
                logger.info(
                    {
                        "event": "data_fetch",
                        "status": "primary",
                        "source": "akshare",
                        "codes": codes,
                        "response_time_ms": result.response_time_ms,
                    }
                )
                return result
            except DataSourceError as exc:
                self._circuit_breaker.record_failure("akshare", error=exc.error_type)
                logger.warning(
                    {
                        "event": "data_fetch_failure",
                        "source": "akshare",
                        "error_type": exc.error_type,
                        "codes": codes,
                    }
                )

        # 2. 主源失败/熔断，尝试备源
        try:
            data = self._fallback.fetch_realtime(codes)
            self._cache_set(codes, data)
            result = self._build_result("fallback", data, "baostock", start_at)
            logger.warning(
                {
                    "event": "data_fetch_failover",
                    "status": "fallback",
                    "source": "baostock",
                    "codes": codes,
                    "response_time_ms": result.response_time_ms,
                }
            )
            return result
        except DataSourceError as exc:
            logger.warning(
                {
                    "event": "data_fetch_failure",
                    "source": "baostock",
                    "error_type": exc.error_type,
                    "codes": codes,
                }
            )

        # 3. 双源故障，查缓存
        cached = self._cache_get(codes)
        if cached is not None:
            result = self._build_result("cached", cached, "cache", start_at)
            logger.warning(
                {
                    "event": "data_fetch_cache_fallback",
                    "status": "cached",
                    "source": "cache",
                    "codes": codes,
                }
            )
            return result

        # 4. 全部不可用
        result = self._build_result("unavailable", None, None, start_at)
        logger.error(
            {
                "event": "data_fetch_unavailable",
                "status": "unavailable",
                "codes": codes,
            }
        )
        return result

    def _cache_set(self, codes: list[str], data: dict[str, Any]) -> None:
        """将数据写入缓存。"""
        for code in codes:
            key = f"realtime_{code}"
            self._cache.set(key, json.dumps(data.get(code, {})))

    def _cache_get(self, codes: list[str]) -> dict[str, Any] | None:
        """从缓存读取数据。"""
        result: dict[str, Any] = {}
        for code in codes:
            key = f"realtime_{code}"
            cached = self._cache.get(key)
            if cached is not None:
                try:
                    result[code] = json.loads(cached)
                except json.JSONDecodeError:
                    continue
        return result if result else None

    def _build_result(
        self,
        status: str,
        data: dict[str, Any] | None,
        source: str | None,
        start_at: datetime,
    ) -> DataFetchResult:
        """构建统一的 DataFetchResult。"""
        elapsed_ms = (datetime.utcnow() - start_at).total_seconds() * 1000
        return DataFetchResult(
            status=status,
            data=data,
            source=source,
            response_time_ms=round(elapsed_ms, 2),
        )
