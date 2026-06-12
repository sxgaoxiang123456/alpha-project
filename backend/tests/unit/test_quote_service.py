import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.database import Base
from backend.app.models.cache_entry import CacheEntry
from backend.app.models.group import Group
from backend.app.models.historical_quote import HistoricalQuote
from backend.app.models.stock import Stock
from backend.app.models.watchlist import WatchlistItem
from backend.app.schemas.data_fetch import DataFetchResult
from backend.app.services.cache_service import CacheService
from backend.app.services.data_cleaner import DataCleaner


class FakeFacade:
    def __init__(self):
        self.requested_codes = None

    def fetch_realtime(self, codes):
        self.requested_codes = codes
        return DataFetchResult(
            status="primary",
            source="akshare",
            response_time_ms=18.5,
            data={
                "600519": {
                    "name": "贵州茅台",
                    "price": 1500.5,
                    "open": 1490.0,
                    "high": 1510.0,
                    "low": 1488.0,
                    "change_pct": 1.25,
                    "change_amount": 18.5,
                    "volume": 100000,
                    "amount": 150050000.0,
                },
                "000001": {
                    "name": "平安银行",
                    "price": 12.34,
                    "open": 12.2,
                    "high": 12.5,
                    "low": 12.1,
                    "change_pct": -0.5,
                    "change_amount": -0.06,
                    "volume": 200000,
                    "amount": 2468000.0,
                },
            },
        )


def test_quote_service_fetches_watchlist_quotes_and_returns_cleaned_models():
    from backend.app.schemas.quote import Quote
    from backend.app.services.quote_service import QuoteService

    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    try:
        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine)
        actual_timestamp = datetime(2026, 6, 4, 10, 0, tzinfo=UTC)

        with Session() as session:
            session.add_all(
                [
                    Group(id=1, name="默认分组", is_default=True),
                    Stock(code="600519", name="贵州茅台", market="沪", sector="白酒"),
                    Stock(code="000001", name="平安银行", market="深", sector="银行"),
                    WatchlistItem(stock_code="600519", group_id=1),
                    WatchlistItem(stock_code="000001", group_id=1),
                ]
            )
            session.commit()

            facade = FakeFacade()
            svc = QuoteService(
                db=session,
                facade=facade,
                cleaner=DataCleaner(),
            )
            with patch.object(svc, '_schedule_historical_persistence', return_value=None):
                quotes = svc.get_watchlist_quotes(actual_timestamp=actual_timestamp)

        assert facade.requested_codes == ["600519", "000001"]
        assert len(quotes) == 2
        assert all(isinstance(quote, Quote) for quote in quotes)
        assert [quote.stock_code for quote in quotes] == ["600519", "000001"]
        assert quotes[0].stock_name == "贵州茅台"
        assert quotes[0].current_price == Decimal("1500.5")
        assert quotes[0].change_percent == Decimal("1.25")
        assert quotes[0].volume == 100000
        assert quotes[0].turnover == Decimal("150050000.0")
        assert quotes[0].status == "normal"
        assert quotes[0].source_status == "primary"
        assert quotes[0].actual_timestamp == actual_timestamp
    finally:
        engine.dispose()


def test_quote_service_writes_cleaned_quotes_to_cache_with_five_minute_ttl():
    from backend.app.schemas.quote import Quote
    from backend.app.services.quote_service import QuoteService

    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    try:
        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine)
        actual_timestamp = datetime(2026, 6, 4, 10, 0, tzinfo=UTC)

        with Session() as session:
            session.add_all(
                [
                    Group(id=1, name="默认分组", is_default=True),
                    Stock(code="600519", name="贵州茅台", market="沪", sector="白酒"),
                    WatchlistItem(stock_code="600519", group_id=1),
                ]
            )
            session.commit()

            cache = CacheService(session)
            QuoteService(
                db=session,
                facade=FakeFacade(),
                cleaner=DataCleaner(),
                cache=cache,
            ).get_watchlist_quotes(actual_timestamp=actual_timestamp)

            cached_content = cache.get("quote:600519")
            assert cached_content is not None
            cached_quote = Quote.model_validate_json(cached_content)
            assert cached_quote.stock_code == "600519"
            assert cached_quote.stock_name == "贵州茅台"
            assert cached_quote.actual_timestamp == actual_timestamp

            entry = session.get(CacheEntry, "quote:600519")
            assert entry is not None
            assert entry.expires_at - entry.cached_at == timedelta(seconds=300)

            entry.expires_at = datetime.now(UTC).replace(tzinfo=None) - timedelta(seconds=1)
            session.commit()
            assert cache.get("quote:600519") is None
    finally:
        engine.dispose()


@pytest.mark.asyncio
async def test_quote_service_persists_historical_quote_in_background_task(tmp_path):
    from backend.app.services.quote_service import QuoteService

    db_path = tmp_path / "test.db"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    try:
        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine)
        actual_timestamp = datetime(2026, 6, 4, 10, 0, tzinfo=UTC)

        with Session() as session:
            session.add_all(
                [
                    Group(id=1, name="默认分组", is_default=True),
                    Stock(code="600519", name="贵州茅台", market="沪", sector="白酒"),
                    WatchlistItem(stock_code="600519", group_id=1),
                ]
            )
            session.commit()

            QuoteService(
                db=session,
                facade=FakeFacade(),
                cleaner=DataCleaner(),
                history_session_factory=Session,
            ).get_watchlist_quotes(actual_timestamp=actual_timestamp)

            # 等待后台线程完成
            await asyncio.sleep(0.3)

            # 刷新 session 以获取其他线程写入的数据
            session.expire_all()

            historical_quote = session.get(
                HistoricalQuote,
                ("600519", actual_timestamp.date()),
            )
            assert historical_quote is not None
            assert historical_quote.open == Decimal("1490.00")
            assert historical_quote.close == Decimal("1500.50")
            assert historical_quote.high == Decimal("1510.00")
            assert historical_quote.low == Decimal("1488.00")
            assert historical_quote.volume == 100000
            assert historical_quote.turnover == Decimal("150050000.00")
    finally:
        engine.dispose()
