from datetime import UTC, datetime
from decimal import Decimal

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.database import Base
from backend.app.dependencies import get_db
from backend.app.models.group import Group
from backend.app.models.stock import Stock
from backend.app.models.watchlist import WatchlistItem
from backend.app.routers.quotes import (
    get_market_index_service,
    get_quote_cache,
    get_quote_service,
    router,
)
from backend.app.schemas.quote import MarketIndex, Quote


class FakeCache:
    def __init__(self, entries):
        self.entries = entries

    def get(self, key):
        return self.entries.get(key)


class FakeQuoteService:
    def __init__(self, quotes):
        self.quotes = quotes
        self.called = False

    def get_watchlist_quotes(self):
        self.called = True
        return self.quotes


class FakeMarketIndexService:
    def __init__(self, indices):
        self.indices = indices
        self.called = False

    def get_indices(self):
        self.called = True
        return self.indices


def _market_index(code="sh000001"):
    return MarketIndex(
        index_code=code,
        index_name="上证指数",
        current_point=Decimal("3123.45"),
        change_percent=Decimal("0.85"),
        change_amount=Decimal("26.10"),
        turnover=Decimal("450000000000.00"),
        updated_at=datetime(2026, 6, 4, 10, 0, tzinfo=UTC),
        source_status="primary",
        actual_timestamp=datetime(2026, 6, 4, 9, 59, tzinfo=UTC),
    )


def _quote(code="600519", source_status="cached"):
    return Quote(
        stock_code=code,
        stock_name="贵州茅台",
        current_price=Decimal("1500.50"),
        change_percent=Decimal("1.25"),
        change_amount=Decimal("18.50"),
        volume=100000,
        turnover=Decimal("150050000.00"),
        updated_at=datetime(2026, 6, 4, 10, 0, tzinfo=UTC),
        status="normal",
        source_status=source_status,
        actual_timestamp=datetime(2026, 6, 4, 9, 59, tzinfo=UTC),
    )


def _client(cache, quote_service, market_index_service=None):
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)

    with Session() as session:
        session.add_all(
            [
                Group(id=1, name="默认分组", is_default=True),
                Stock(code="600519", name="贵州茅台", market="沪", sector="白酒"),
                WatchlistItem(stock_code="600519", group_id=1),
            ]
        )
        session.commit()

    def override_db():
        with Session() as session:
            yield session

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_quote_cache] = lambda: cache
    app.dependency_overrides[get_quote_service] = lambda: quote_service
    if market_index_service is not None:
        app.dependency_overrides[get_market_index_service] = lambda: market_index_service
    return TestClient(app), engine


def test_get_quotes_returns_cached_watchlist_quotes_without_fetching():
    cached_quote = _quote()
    cache = FakeCache({"quote:600519": cached_quote.model_dump_json()})
    quote_service = FakeQuoteService([])
    client, engine = _client(cache, quote_service)

    try:
        response = client.get("/quotes")
    finally:
        engine.dispose()

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["stock_code"] == "600519"
    assert data[0]["source_status"] == "cached"
    assert quote_service.called is False


def test_get_quotes_fetches_watchlist_quotes_when_cache_misses():
    cache = FakeCache({})
    quote_service = FakeQuoteService([_quote(source_status="primary")])
    client, engine = _client(cache, quote_service)

    try:
        response = client.get("/quotes")
    finally:
        engine.dispose()

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["stock_code"] == "600519"
    assert data[0]["source_status"] == "primary"
    assert quote_service.called is True


def test_get_market_quotes_returns_market_indices():
    cache = FakeCache({})
    quote_service = FakeQuoteService([])
    market_index_service = FakeMarketIndexService([_market_index()])
    client, engine = _client(cache, quote_service, market_index_service)

    try:
        response = client.get("/quotes/market")
    finally:
        engine.dispose()

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["index_code"] == "sh000001"
    assert data[0]["index_name"] == "上证指数"
    assert market_index_service.called is True
