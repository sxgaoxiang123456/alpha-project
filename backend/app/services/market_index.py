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

    def __init__(self, facade: Any, cache: Any, ttl_seconds: int = CACHE_TTL_SECONDS):
        self.facade = facade
        self.cache = cache
        self.ttl_seconds = ttl_seconds

    def get_indices(self, *, actual_timestamp: datetime | None = None) -> list[MarketIndex]:
        result = self.facade.fetch_realtime(list(self.INDEX_CODES))
        data = result.data or {}
        timestamp = actual_timestamp or datetime.now(UTC)
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
