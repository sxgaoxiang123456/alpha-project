from datetime import UTC, datetime, timedelta
from unittest import mock

import backend.app.routers.briefing
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.database import Base
from backend.app.main import app
from backend.app.services.cache_service import CacheService


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


@pytest.fixture
def client(db_session):
    def _get_db():
        yield db_session

    app.dependency_overrides = {}
    from backend.app.dependencies import get_db

    app.dependency_overrides[get_db] = _get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


class TestBriefingAPI:
    def test_post_generate_trading_day_returns_accepted(self, client, db_session):
        with mock.patch(
            "backend.app.routers.briefing._trigger_manual_briefing"
        ) as mock_trigger:
            response = client.post("/api/briefing/generate")

        assert response.status_code == 202
        assert response.json()["status"] == "accepted"
        mock_trigger.assert_called_once()

    def test_post_generate_non_trading_day_returns_422(self, client, db_session):
        from backend.app.core import trading_calendar

        original = trading_calendar.is_trading_day
        trading_calendar.is_trading_day = lambda d: False
        try:
            response = client.post("/api/briefing/generate")
            assert response.status_code == 422
            assert "非交易日" in response.json()["detail"]
        finally:
            trading_calendar.is_trading_day = original

    def test_post_generate_cooldown_returns_429(self, client, db_session):
        cache = CacheService(db_session)
        cache.set(
            "briefing_manual_cooldown",
            datetime.now(UTC).isoformat(),
            ttl_seconds=60,
        )
        db_session.commit()

        with mock.patch(
            "backend.app.routers.briefing._get_cache_service",
            return_value=cache,
        ):
            response = client.post("/api/briefing/generate")

        assert response.status_code == 429
        assert "冷却" in response.json()["detail"]

    def test_get_latest_returns_cached_briefing(self, client, db_session):
        cache = CacheService(db_session)
        cache.set(
            "latest_briefing",
            '{"date": "2026-06-23", "market_indices": {}, "top_movers": [], "insights": ["测试"], "is_degraded": false}',
            ttl_seconds=300,
        )
        db_session.commit()

        with mock.patch(
            "backend.app.routers.briefing._get_cache_service",
            return_value=cache,
        ):
            response = client.get("/api/briefing/latest")

        assert response.status_code == 200
        assert response.json()["insights"] == ["测试"]

    def test_get_latest_no_cache_returns_404(self, client, db_session):
        cache = CacheService(db_session)

        with mock.patch(
            "backend.app.routers.briefing._get_cache_service",
            return_value=cache,
        ):
            response = client.get("/api/briefing/latest")

        assert response.status_code == 404
