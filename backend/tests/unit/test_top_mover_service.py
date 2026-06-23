from datetime import date, datetime
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.database import Base
from backend.app.models.group import Group
from backend.app.models.historical_quote import HistoricalQuote
from backend.app.models.stock import Stock
from backend.app.models.watchlist import WatchlistItem
from backend.app.schemas.briefing import TopMover
from backend.app.schemas.quote import Quote


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    import backend.app.models  # noqa: F401
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    with SessionLocal() as session:
        yield session


class TestTopMoverService:
    def test_watchlist_only_returns_top_5(self, db_session):
        from backend.app.services.top_mover_service import TopMoverService

        service = TopMoverService(db=db_session)

        # Seed 10 watchlist stocks
        watchlist_quotes = []
        for i in range(10):
            code = f"600{i:03d}"
            self._seed_stock_and_watchlist(db_session, code, f"股票{code}")
            watchlist_quotes.append(
                Quote(
                    stock_code=code,
                    stock_name=f"股票{code}",
                    current_price=Decimal("10.0") + i,
                    change_percent=Decimal(str(i)),
                    volume=1000000 * (i + 1),
                    turnover=Decimal("10000000"),
                    updated_at=datetime.now(),
                    status="normal",
                    source_status="primary",
                    actual_timestamp=datetime.now(),
                )
            )
            self._seed_history(db_session, code, days=5, base_volume=1000000)

        db_session.commit()

        movers = service.compute_top_movers(watchlist_quotes)

        assert len(movers) == 5
        assert all(isinstance(m, TopMover) for m in movers)

    def test_watchlist_insufficient_falls_back_to_market(self, db_session):
        from backend.app.services.top_mover_service import TopMoverService

        service = TopMoverService(db=db_session)

        watchlist_quotes = []
        for i in range(2):
            code = f"600{i:03d}"
            self._seed_stock_and_watchlist(db_session, code, f"股票{code}")
            watchlist_quotes.append(
                Quote(
                    stock_code=code,
                    stock_name=f"股票{code}",
                    current_price=Decimal("10.0"),
                    change_percent=Decimal("1.0"),
                    volume=2000000,
                    turnover=Decimal("20000000"),
                    updated_at=datetime.now(),
                    status="normal",
                    source_status="primary",
                    actual_timestamp=datetime.now(),
                )
            )
            self._seed_history(db_session, code, days=5, base_volume=1000000)

        db_session.commit()

        # Fallback market data: 5 stocks with higher volume spikes
        fallback_quotes = {
            f"000{i:03d}": {
                "name": f"市场股{i}",
                "price": 10.0 + i,
                "change_pct": 5.0 + i,
                "volume": 10000000 * (i + 1),
                "amount": 100000000.0,
            }
            for i in range(5)
        }

        movers = service.compute_top_movers(watchlist_quotes, fallback_quotes=fallback_quotes)

        assert len(movers) == 5
        watchlist_codes = {q.stock_code for q in watchlist_quotes}
        fallback_count = sum(1 for m in movers if m.stock_code not in watchlist_codes)
        assert fallback_count == 3

    def test_insufficient_history_marks_data_sufficient_false(self, db_session):
        from backend.app.services.top_mover_service import TopMoverService

        service = TopMoverService(db=db_session)

        code = "600001"
        self._seed_stock_and_watchlist(db_session, code, "新股")
        quote = Quote(
            stock_code=code,
            stock_name="新股",
            current_price=Decimal("10.0"),
            change_percent=Decimal("5.0"),
            volume=10000000,
            turnover=Decimal("100000000"),
            updated_at=datetime.now(),
            status="normal",
            source_status="primary",
            actual_timestamp=datetime.now(),
        )
        # Only 1 day of history
        self._seed_history(db_session, code, days=1, base_volume=1000000)
        db_session.commit()

        movers = service.compute_top_movers([quote])

        assert len(movers) == 1
        assert movers[0].data_sufficient is False

    def test_empty_watchlist_uses_fallback(self, db_session):
        from backend.app.services.top_mover_service import TopMoverService

        service = TopMoverService(db=db_session)

        fallback_quotes = {
            f"000{i:03d}": {
                "name": f"市场股{i}",
                "price": 10.0 + i,
                "change_pct": 5.0 + i,
                "volume": 10000000 * (i + 1),
                "amount": 100000000.0,
            }
            for i in range(5)
        }

        movers = service.compute_top_movers([], fallback_quotes=fallback_quotes)

        assert len(movers) == 5

    def test_classify_move_uses_thresholds(self, db_session):
        from backend.app.services.top_mover_service import TopMoverService

        service = TopMoverService(db=db_session)

        assert service._classify_move(3.0, 1.0) == ("volume_spike", 3.0)
        assert service._classify_move(1.0, 5.0) == ("price_surge", 5.0)
        assert service._classify_move(1.0, -5.0) == ("price_drop", -5.0)
        assert service._classify_move(1.0, 1.0) == ("normal", 1.0)
        assert service._classify_move(1.0, -1.0) == ("normal", -1.0)

    @staticmethod
    def _seed_stock_and_watchlist(db, code, name):
        if db.query(Group).count() == 0:
            db.add(Group(name="默认分组", is_default=True))
            db.flush()
        group = db.query(Group).order_by(Group.id).first()
        stock = Stock(code=code, name=name, market="sh")
        db.add(stock)
        db.flush()
        item = WatchlistItem(stock_code=code, group_id=group.id)
        db.add(item)

    @staticmethod
    def _seed_history(db, code, days, base_volume):
        today = date.today()
        for d in range(days, 0, -1):
            hist_date = date.fromordinal(today.toordinal() - d)
            hq = HistoricalQuote(
                stock_code=code,
                date=hist_date,
                open=Decimal("9.5"),
                close=Decimal("10.0"),
                high=Decimal("10.5"),
                low=Decimal("9.0"),
                volume=base_volume,
                turnover=Decimal("10000000"),
            )
            db.add(hq)
