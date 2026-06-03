"""System API 单元测试 — 数据源状态查询。"""

from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from backend.app.database import Base, SessionLocal, engine
from backend.app.models.data_source_status import DataSourceStatus
from backend.app.main import app


@pytest.fixture(autouse=True, scope="module")
def _setup_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def db():
    session = SessionLocal()
    yield session
    session.rollback()
    session.query(DataSourceStatus).delete()
    session.commit()
    session.close()


class TestDataSourcesStatus:
    """GET /system/data-sources 测试。"""

    def test_returns_data_sources_list(self, client: TestClient, db):
        db.add(DataSourceStatus(
            name="akshare",
            status="closed",
            consecutive_failures=0,
            last_success_at=datetime(2026, 6, 3, 10, 0, 0),
        ))
        db.add(DataSourceStatus(
            name="baostock",
            status="closed",
            consecutive_failures=0,
            last_success_at=datetime(2026, 6, 3, 10, 0, 0),
        ))
        db.commit()

        response = client.get("/system/data-sources")

        assert response.status_code == 200
        data = response.json()
        assert "sources" in data
        assert len(data["sources"]) == 2

    def test_shows_active_source(self, client: TestClient, db):
        db.add(DataSourceStatus(
            name="akshare",
            status="closed",
            consecutive_failures=0,
        ))
        db.commit()

        response = client.get("/system/data-sources")
        data = response.json()

        assert "active_source" in data
        # akshare closed → 活跃源是 akshare
        assert data["active_source"] == "akshare"

    def test_shows_fallback_when_primary_open(self, client: TestClient, db):
        db.add(DataSourceStatus(
            name="akshare",
            status="open",
            consecutive_failures=3,
        ))
        db.add(DataSourceStatus(
            name="baostock",
            status="closed",
            consecutive_failures=0,
        ))
        db.commit()

        response = client.get("/system/data-sources")
        data = response.json()

        # akshare open → 活跃源是 baostock
        assert data["active_source"] == "baostock"

    def test_shows_source_details(self, client: TestClient, db):
        db.add(DataSourceStatus(
            name="akshare",
            status="open",
            consecutive_failures=3,
            last_failure_at=datetime(2026, 6, 3, 9, 0, 0),
            last_error="timeout",
        ))
        db.commit()

        response = client.get("/system/data-sources")
        data = response.json()

        akshare = next(s for s in data["sources"] if s["name"] == "akshare")
        assert akshare["status"] == "open"
        assert akshare["consecutive_failures"] == 3
        assert akshare["last_error"] == "timeout"
        assert "last_failure_at" in akshare
