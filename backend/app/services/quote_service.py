from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

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
    ):
        self.db = db
        self.facade = facade
        self.cleaner = cleaner or DataCleaner()
        self.cache = cache
        self.ttl_seconds = ttl_seconds

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

        return quotes
