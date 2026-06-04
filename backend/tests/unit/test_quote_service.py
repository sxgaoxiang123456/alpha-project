from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.database import Base
from backend.app.models.group import Group
from backend.app.models.stock import Stock
from backend.app.models.watchlist import WatchlistItem
from backend.app.schemas.data_fetch import DataFetchResult
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
                    "change_pct": 1.25,
                    "change_amount": 18.5,
                    "volume": 100000,
                    "amount": 150050000.0,
                },
                "000001": {
                    "name": "平安银行",
                    "price": 12.34,
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

    engine = create_engine("sqlite:///:memory:")
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
            quotes = QuoteService(
                db=session,
                facade=facade,
                cleaner=DataCleaner(),
            ).get_watchlist_quotes(actual_timestamp=actual_timestamp)

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
