import logging
from collections.abc import Mapping
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from backend.app.schemas.quote import MarketIndex

logger = logging.getLogger(__name__)


class MarketIndexService:
    INDEX_CODES = ("sh000001", "sz399001", "sz399006")
    INDEX_NAMES = {
        "sh000001": "上证指数",
        "sz399001": "深证成指",
        "sz399006": "创业板指",
    }
    CACHE_TTL_SECONDS = 300

    def __init__(self, facade: Any, cache: Any, ttl_seconds: int = CACHE_TTL_SECONDS, redis_cache: Any | None = None):
        self.facade = facade
        self.cache = cache
        self.ttl_seconds = ttl_seconds
        self.redis_cache = redis_cache

    def get_indices(self, *, actual_timestamp: datetime | None = None, use_cache: bool = False) -> list[MarketIndex]:
        timestamp = actual_timestamp or datetime.now(UTC)

        # use_cache=True 时优先读 Redis
        if use_cache and self.redis_cache is not None:
            cache_key = "quotes:market"
            cached = self.redis_cache.get(cache_key)
            if cached is not None:
                logger.debug("Redis cache hit: %s", cache_key)
                return [
                    MarketIndex(
                        index_code=idx["index_code"],
                        index_name=idx.get("index_name", idx["index_code"]),
                        current_point=Decimal(str(idx.get("current_point", 0))),
                        change_percent=Decimal(str(idx.get("change_percent", 0))),
                        change_amount=Decimal(str(idx.get("change_amount", 0))),
                        turnover=Decimal(str(idx.get("turnover", 0))),
                        updated_at=datetime.fromisoformat(idx["updated_at"]) if idx.get("updated_at") else timestamp,
                        source_status=idx.get("source_status", "cached"),
                        actual_timestamp=timestamp,
                    )
                    for idx in cached
                ]

        result = self.facade.fetch_realtime(list(self.INDEX_CODES))
        data = result.data or {}
        indices = [
            self._build_index(code, data[code], result.status, timestamp)
            for code in self.INDEX_CODES
            if code in data
        ]

        for index in indices:
            self.cache.set(
                f"market_index:{index.index_code}",
                index.model_dump_json(),
                ttl_seconds=self.ttl_seconds,
            )

        # 写入 Redis cache（新增）
        if use_cache and self.redis_cache is not None and indices:
            self.redis_cache.set(
                "quotes:market",
                [
                    {
                        "index_code": idx.index_code,
                        "index_name": idx.index_name,
                        "current_point": str(idx.current_point) if idx.current_point is not None else "0",
                        "change_percent": str(idx.change_percent) if idx.change_percent is not None else "0",
                        "change_amount": str(idx.change_amount) if idx.change_amount is not None else "0",
                        "turnover": str(idx.turnover) if idx.turnover is not None else "0",
                        "updated_at": idx.updated_at.isoformat() if idx.updated_at else timestamp.isoformat(),
                        "source_status": idx.source_status,
                    }
                    for idx in indices
                ],
                ttl_seconds=60,
            )

        return indices

    def _build_index(
        self,
        code: str,
        raw: Mapping[str, Any],
        source_status: str,
        actual_timestamp: datetime,
    ) -> MarketIndex:
        return MarketIndex(
            index_code=code,
            index_name=str(raw.get("name") or self.INDEX_NAMES[code]).strip(),
            current_point=self._decimal(raw.get("price")),
            change_percent=self._decimal(raw.get("change_pct")),
            change_amount=self._decimal(raw.get("change_amount", raw.get("change", 0))),
            turnover=self._decimal(raw.get("amount", raw.get("turnover", 0))),
            updated_at=datetime.now(UTC),
            source_status=source_status,
            actual_timestamp=actual_timestamp,
        )

    def _decimal(self, value: Any) -> Decimal:
        if value is None or value == "":
            return Decimal("0")
        return Decimal(str(value))
