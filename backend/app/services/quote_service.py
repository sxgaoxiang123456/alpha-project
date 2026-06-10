import logging
from collections.abc import Mapping
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session, sessionmaker

from backend.app.models.historical_quote import HistoricalQuote
from backend.app.models.watchlist import WatchlistItem
from backend.app.schemas.quote import Quote
from backend.app.services.data_cleaner import DataCleaner

logger = logging.getLogger(__name__)


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
        redis_cache: Any | None = None,
    ):
        self.db = db
        self.facade = facade
        self.cleaner = cleaner or DataCleaner()
        self.cache = cache
        self.ttl_seconds = ttl_seconds
        self.history_session_factory = history_session_factory or sessionmaker(bind=db.get_bind())
        self.redis_cache = redis_cache

    def get_watchlist_quotes(
        self,
        *,
        actual_timestamp: datetime | None = None,
        use_cache: bool = False,
    ) -> list[Quote]:
        items = self.db.query(WatchlistItem).order_by(WatchlistItem.id).all()
        codes = [item.stock_code for item in items]
        if not codes:
            return []

        timestamp = actual_timestamp or datetime.now(UTC)

        # use_cache=True 时优先读 Redis
        if use_cache and self.redis_cache is not None:
            cache_key = f"quotes:watchlist:{','.join(sorted(codes))}"
            cached = self.redis_cache.get(cache_key)
            if cached is not None:
                logger.debug("Redis cache hit: %s", cache_key)
                return [
                    Quote(
                        stock_code=q["stock_code"],
                        stock_name=q.get("stock_name", q["stock_code"]),
                        current_price=Decimal(str(q.get("current_price", 0))),
                        change_percent=Decimal(str(q.get("change_percent", 0))),
                        change_amount=Decimal(str(q.get("change_amount", 0))),
                        updated_at=datetime.fromisoformat(q["updated_at"]) if q.get("updated_at") else timestamp,
                        status=q.get("status", "normal"),
                        source_status=q.get("source_status", "cached"),
                        actual_timestamp=timestamp,
                    )
                    for q in cached
                ]

        # Redis miss 或 use_cache=False — 调外部接口
        try:
            result = self.facade.fetch_realtime(codes)
            data = result.data or {}
            source_status = result.status
        except Exception:
            logger.exception("实时行情获取失败，降级返回基础列表")
            data = {}
            source_status = "unavailable"

        quotes = [
            self.cleaner.clean_quote(
                code,
                data.get(code),
                source_status=source_status,
                actual_timestamp=timestamp,
            )
            for code in codes
        ]

        # 写入 SQLite cache（原有行为）
        if self.cache is not None:
            for quote in quotes:
                self.cache.set(
                    f"quote:{quote.stock_code}",
                    quote.model_dump_json(),
                    ttl_seconds=self.ttl_seconds,
                )

        # 写入 Redis cache（新增）
        if use_cache and self.redis_cache is not None and quotes:
            cache_key = f"quotes:watchlist:{','.join(sorted(codes))}"
            self.redis_cache.set(
                cache_key,
                [
                    {
                        "stock_code": q.stock_code,
                        "stock_name": q.stock_name,
                        "current_price": str(q.current_price) if q.current_price is not None else "0",
                        "change_percent": str(q.change_percent) if q.change_percent is not None else "0",
                        "change_amount": str(q.change_amount) if q.change_amount is not None else "0",
                        "updated_at": q.updated_at.isoformat() if q.updated_at else timestamp.isoformat(),
                        "status": q.status,
                        "source_status": q.source_status,
                    }
                    for q in quotes
                ],
                ttl_seconds=60,
            )

        self._schedule_historical_persistence(data, timestamp)

        return quotes

    def _schedule_historical_persistence(
        self,
        data: Mapping[str, Any],
        actual_timestamp: datetime,
    ) -> None:
        import threading
        try:
            t = threading.Thread(
                target=self._persist_historical_quotes,
                args=(data, actual_timestamp),
                daemon=True,
            )
            t.start()
        except Exception:
            logger.exception("历史行情落盘调度失败")

    def _persist_historical_quotes(
        self,
        data: Mapping[str, Any],
        actual_timestamp: datetime,
    ) -> None:
        try:
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
        except Exception:
            logger.exception("历史行情异步落盘失败")

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
