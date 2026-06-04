from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from backend.app.models.watchlist import WatchlistItem
from backend.app.schemas.quote import Quote
from backend.app.services.data_cleaner import DataCleaner


class QuoteService:
    def __init__(self, db: Session, facade: Any, cleaner: DataCleaner | None = None):
        self.db = db
        self.facade = facade
        self.cleaner = cleaner or DataCleaner()

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

        return [
            self.cleaner.clean_quote(
                code,
                data.get(code),
                source_status=result.status,
                actual_timestamp=timestamp,
            )
            for code in codes
        ]
