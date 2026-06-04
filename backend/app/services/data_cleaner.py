from collections.abc import Mapping
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from backend.app.schemas.quote import Quote


class DataCleaner:
    def clean_quote(
        self,
        stock_code: str,
        raw: Mapping[str, Any] | None,
        *,
        source_status: str,
        actual_timestamp: datetime | None = None,
    ) -> Quote:
        now = datetime.now(UTC)
        timestamp = actual_timestamp or now

        if raw is None:
            return Quote(
                stock_code=stock_code,
                stock_name=stock_code,
                current_price=None,
                change_percent=None,
                change_amount=None,
                volume=None,
                turnover=None,
                updated_at=now,
                status="missing",
                source_status=source_status,
                actual_timestamp=timestamp,
            )

        name = str(raw.get("name") or stock_code).strip() or stock_code
        price = self._decimal_or_none(raw.get("price"))
        pre_close = self._decimal_or_none(raw.get("pre_close"))
        change_percent = self._decimal_or_none(raw.get("change_pct"))
        volume = self._int_or_none(raw.get("volume"))
        turnover = self._decimal_or_none(raw.get("amount", raw.get("turnover")))

        if self._is_suspended(raw):
            return Quote(
                stock_code=stock_code,
                stock_name=name,
                current_price=pre_close if pre_close and pre_close > 0 else None,
                change_percent=None,
                change_amount=None,
                volume=None,
                turnover=turnover,
                updated_at=now,
                status="suspended",
                source_status=source_status,
                actual_timestamp=timestamp,
            )

        status = "normal"
        if price is None or price <= 0:
            status = "abnormal"
            price = None
        if change_percent is not None and abs(change_percent) > self._change_limit(stock_code):
            status = "abnormal"
        if volume == 0:
            status = "abnormal"

        return Quote(
            stock_code=stock_code,
            stock_name=name,
            current_price=price,
            change_percent=change_percent,
            change_amount=self._decimal_or_none(raw.get("change_amount")),
            volume=volume,
            turnover=turnover,
            updated_at=now,
            status=status,
            source_status=source_status,
            actual_timestamp=timestamp,
        )

    def _is_suspended(self, raw: Mapping[str, Any]) -> bool:
        status = str(raw.get("status", "")).strip().lower()
        return status in {"停牌", "suspended"} or raw.get("is_suspended") is True

    def _change_limit(self, stock_code: str) -> Decimal:
        if stock_code.startswith(("688", "300")):
            return Decimal("30")
        return Decimal("20")

    def _decimal_or_none(self, value: Any) -> Decimal | None:
        if value is None or value == "":
            return None
        return Decimal(str(value))

    def _int_or_none(self, value: Any) -> int | None:
        if value is None or value == "":
            return None
        return int(value)
