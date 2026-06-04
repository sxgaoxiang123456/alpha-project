import asyncio
from collections.abc import Mapping
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session, sessionmaker

from backend.app.models.historical_quote import HistoricalQuote
from backend.app.models.watchlist import WatchlistItem
from backend.app.schemas.quote import Quote
from backend.app.services.data_cleaner import DataCleaner


class QuoteService:
    CACHE_TTL_SECONDS = 300

    def __init__(
        self,
        db: Session,
        facade: Any,
        cleaner: DataCleaner | None = None,
        cache: Any | None = None,
        ttl_seconds: int = CACHE_TTL_SECONDS,
        history_session_factory: Any | None = None,
    ):
        self.db = db
        self.facade = facade
        self.cleaner = cleaner or DataCleaner()
        self.cache = cache
        self.ttl_seconds = ttl_seconds
        self.history_session_factory = history_session_factory or sessionmaker(bind=db.get_bind())

    def get_watchlist_quotes(
        self,
        *,
        actual_timestamp: datetime | None = None,
    ) -> list[Quote]:
        items = self.db.query(WatchlistItem).order_by(WatchlistItem.id).all()
        codes = [item.stock_code for item in items]
        if not codes:
            return []

        result = self.facade.fetch_realtime(codes)
        data = result.data or {}
        timestamp = actual_timestamp or datetime.now(UTC)
        quotes = [
            self.cleaner.clean_quote(
                code,
                data.get(code),
                source_status=result.status,
                actual_timestamp=timestamp,
            )
            for code in codes
        ]

        if self.cache is not None:
            for quote in quotes:
                self.cache.set(
                    f"quote:{quote.stock_code}",
                    quote.model_dump_json(),
                    ttl_seconds=self.ttl_seconds,
                )

        self._schedule_historical_persistence(data, timestamp)

        return quotes

    def _schedule_historical_persistence(
        self,
        data: Mapping[str, Any],
        actual_timestamp: datetime,
    ) -> None:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            asyncio.run(self._persist_historical_quotes(data, actual_timestamp))
            return

        loop.create_task(self._persist_historical_quotes(data, actual_timestamp))

    async def _persist_historical_quotes(
        self,
        data: Mapping[str, Any],
        actual_timestamp: datetime,
    ) -> None:
        with self.history_session_factory() as session:
            for code, raw in data.items():
                if not isinstance(raw, Mapping):
                    continue

                historical_quote = self._build_historical_quote(code, raw, actual_timestamp)
                if historical_quote is None:
                    continue

                existing = session.get(
                    HistoricalQuote,
                    (historical_quote.stock_code, historical_quote.date),
                )
                if existing is None:
                    session.add(historical_quote)
                else:
                    existing.open = historical_quote.open
                    existing.close = historical_quote.close
                    existing.high = historical_quote.high
                    existing.low = historical_quote.low
                    existing.volume = historical_quote.volume
                    existing.turnover = historical_quote.turnover

            session.commit()

    def _build_historical_quote(
        self,
        code: str,
        raw: Mapping[str, Any],
        actual_timestamp: datetime,
    ) -> HistoricalQuote | None:
        close = self._decimal_or_none(raw.get("close") or raw.get("price"))
        open_price = self._decimal_or_none(raw.get("open") or close)
        high = self._decimal_or_none(raw.get("high") or close)
        low = self._decimal_or_none(raw.get("low") or close)
        volume = self._int_or_none(raw.get("volume"))
        turnover = self._decimal_or_none(raw.get("amount") or raw.get("turnover"))

        prices = (open_price, close, high, low)
        if any(price is None or price <= 0 for price in prices):
            return None
        if volume is None or volume < 0 or turnover is None or turnover < 0:
            return None

        return HistoricalQuote(
            stock_code=code,
            date=actual_timestamp.date(),
            open=open_price,
            close=close,
            high=high,
            low=low,
            volume=volume,
            turnover=turnover,
        )

    def _decimal_or_none(self, value: Any) -> Decimal | None:
        if value is None or value == "":
            return None
        return Decimal(str(value))

    def _int_or_none(self, value: Any) -> int | None:
        if value is None or value == "":
            return None
        return int(value)
