from datetime import date
from decimal import Decimal

from freezegun import freeze_time
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.core.quote_scheduler import QuoteScheduler
from backend.app.database import Base
from backend.app.models.group import Group
from backend.app.models.historical_quote import HistoricalQuote
from backend.app.models.stock import Stock
from backend.app.models.watchlist import WatchlistItem
from backend.app.schemas.data_fetch import DataFetchResult
from backend.app.schemas.quote import MarketIndex, Quote
from backend.app.services.cache_service import CacheService
from backend.app.services.data_cleaner import DataCleaner
from backend.app.services.market_index import MarketIndexService
from backend.app.services.quote_service import QuoteService


class FakeFacade:
    def __init__(self):
        self.calls = []

    def fetch_realtime(self, codes):
        self.calls.append(list(codes))
        if codes == ["600519"]:
            data = {
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
                }
            }
        else:
            data = {
                "sh000001": {
                    "name": "上证指数",
                    "price": 3123.45,
                    "change_pct": 0.85,
                    "change_amount": 26.1,
                    "amount": 450000000000.0,
                },
                "sz399001": {
                    "name": "深证成指",
                    "price": 9876.54,
                    "change_pct": -0.35,
                    "change_amount": -34.2,
                    "amount": 520000000000.0,
                },
                "sz399006": {
                    "name": "创业板指",
                    "price": 2012.34,
                    "change_pct": 1.15,
                    "change_amount": 22.8,
                    "amount": 210000000000.0,
                },
            }

        return DataFetchResult(
            status="primary",
            data=data,
            source="akshare",
            response_time_ms=1.0,
        )


def _session_factory(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'quote_scheduler.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    return engine, sessionmaker(bind=engine)


def _seed_watchlist(session):
    session.add(Group(id=1, name="默认分组", is_default=True))
    session.add(Stock(code="600519", name="贵州茅台", market="沪", sector="白酒"))
    session.add(WatchlistItem(stock_code="600519", group_id=1))
    session.commit()


def _scheduler(session, session_factory, facade, is_trading_day):
    cache = CacheService(session)
    return (
        QuoteScheduler(
            quote_service=QuoteService(
                db=session,
                facade=facade,
                cleaner=DataCleaner(),
                cache=cache,
                history_session_factory=session_factory,
            ),
            market_index_service=MarketIndexService(facade=facade, cache=cache),
            is_trading_day=is_trading_day,
        ),
        cache,
    )


def test_quote_scheduler_refresh_updates_cache_and_persists_history(tmp_path):
    engine, Session = _session_factory(tmp_path)
    try:
        with Session() as session:
            _seed_watchlist(session)
            facade = FakeFacade()
            scheduler, cache = _scheduler(session, Session, facade, lambda current_date: True)

            with freeze_time("2026-06-04 10:00:00"):
                scheduler.refresh_if_trading_day()

                cached_quote = Quote.model_validate_json(cache.get("quote:600519"))
                cached_index = MarketIndex.model_validate_json(cache.get("market_index:sh000001"))

            assert facade.calls == [["600519"], ["sh000001", "sz399001", "sz399006"]]
            assert cached_quote.stock_code == "600519"
            assert cached_quote.status == "normal"
            assert cached_quote.source_status == "primary"
            assert cached_index.index_name == "上证指数"
            assert cached_index.source_status == "primary"

            historical_quote = session.get(HistoricalQuote, ("600519", date(2026, 6, 4)))
            assert historical_quote is not None
            assert historical_quote.open == Decimal("1490.00")
            assert historical_quote.close == Decimal("1500.50")
            assert historical_quote.high == Decimal("1510.00")
            assert historical_quote.low == Decimal("1488.00")
            assert historical_quote.volume == 100000
            assert historical_quote.turnover == Decimal("150050000.00")
    finally:
        engine.dispose()


def test_quote_scheduler_skips_integration_refresh_on_non_trading_day(tmp_path):
    engine, Session = _session_factory(tmp_path)
    try:
        with Session() as session:
            _seed_watchlist(session)
            facade = FakeFacade()
            scheduler, cache = _scheduler(session, Session, facade, lambda current_date: False)

            with freeze_time("2026-06-06 10:00:00"):
                scheduler.refresh_if_trading_day()

            assert facade.calls == []
            assert cache.get("quote:600519") is None
            assert session.get(HistoricalQuote, ("600519", date(2026, 6, 6))) is None
    finally:
        engine.dispose()
