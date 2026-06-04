"""T5-T6: 预警规则 API 测试。

采用 FastAPI + 内存 SQLite 方案，直接路由注册，避免 main.py 复杂依赖。
"""

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.database import Base
from backend.app.dependencies import get_db
from backend.app.routers.alerts import router


def _make_client():
    """创建使用内存 SQLite 的 TestClient。"""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(
        autocommit=False, autoflush=False, bind=engine
    )

    import backend.app.models  # noqa: F401
    Base.metadata.create_all(bind=engine)

    app = FastAPI()

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    app.include_router(router)

    return TestClient(app), TestingSessionLocal


class TestCreateAlertRule:
    """T5: POST /alerts 创建预警规则。"""

    def test_create_price_below_rule(self):
        client, _ = _make_client()
        resp = client.post("/alerts", json={
            "stock_code": "600519",
            "condition_type": "price_below",
            "threshold": 1500.00,
            "cooldown_minutes": 30,
            "level": "watch",
        })
        assert resp.status_code == 201, resp.json()
        data = resp.json()
        assert data["stock_code"] == "600519"
        assert data["condition_type"] == "price_below"
        assert data["threshold"] == 1500.00
        assert data["id"] is not None
        assert data["status"] == "active"

    def test_create_with_defaults(self):
        client, _ = _make_client()
        resp = client.post("/alerts", json={
            "stock_code": "000001",
            "condition_type": "price_above",
            "threshold": 10.00,
        })
        assert resp.status_code == 201, resp.json()
        data = resp.json()
        assert data["cooldown_minutes"] == 30
        assert data["level"] == "watch"

    def test_create_rejects_invalid_condition_type(self):
        client, _ = _make_client()
        resp = client.post("/alerts", json={
            "stock_code": "600519",
            "condition_type": "invalid_type",
            "threshold": 100.0,
        })
        assert resp.status_code == 422

    def test_create_rejects_invalid_stock_code(self):
        client, _ = _make_client()
        resp = client.post("/alerts", json={
            "stock_code": "12345",
            "condition_type": "price_below",
            "threshold": 10.0,
        })
        assert resp.status_code == 422

    def test_create_rejects_negative_price_threshold(self):
        client, _ = _make_client()
        resp = client.post("/alerts", json={
            "stock_code": "600519",
            "condition_type": "price_below",
            "threshold": -1.0,
        })
        assert resp.status_code == 422

    def test_50_rules_limit_rejected(self):
        client, _ = _make_client()
        for i in range(50):
            code = f"60{i:04d}"
            resp = client.post("/alerts", json={
                "stock_code": code,
                "condition_type": "price_below",
                "threshold": 100.0,
            })
            assert resp.status_code == 201, f"第 {i+1} 条规则创建失败: {resp.json()}"

        resp = client.post("/alerts", json={
            "stock_code": "600519",
            "condition_type": "price_below",
            "threshold": 100.0,
        })
        assert resp.status_code == 429
        assert "50" in resp.json()["detail"]


class TestListAlertRules:
    """T5: GET /alerts 查询预警规则列表。"""

    def test_list_returns_empty(self):
        client, _ = _make_client()
        resp = client.get("/alerts")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_returns_created_rules(self):
        client, _ = _make_client()
        client.post("/alerts", json={
            "stock_code": "600519",
            "condition_type": "price_below",
            "threshold": 1500.00,
        })
        client.post("/alerts", json={
            "stock_code": "000001",
            "condition_type": "price_above",
            "threshold": 10.00,
        })

        resp = client.get("/alerts")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2

    def test_list_filters_by_status(self):
        client, _ = _make_client()
        client.post("/alerts", json={
            "stock_code": "600519",
            "condition_type": "price_below",
            "threshold": 1500.00,
        })
        client.post("/alerts", json={
            "stock_code": "000001",
            "condition_type": "price_above",
            "threshold": 10.00,
        })

        resp = client.get("/alerts?status=active")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

        resp = client.get("/alerts?status=paused")
        assert resp.status_code == 200
        assert resp.json() == []


class TestUpdateAlertRule:
    """T5: PUT /alerts/{id} 修改预警规则。"""

    def test_update_threshold(self):
        client, _ = _make_client()
        create_resp = client.post("/alerts", json={
            "stock_code": "600519",
            "condition_type": "price_below",
            "threshold": 1500.00,
        })
        rule_id = create_resp.json()["id"]

        resp = client.put(f"/alerts/{rule_id}", json={
            "threshold": 1450.00,
        })
        assert resp.status_code == 200
        assert resp.json()["threshold"] == 1450.00

    def test_update_nonexistent_returns_404(self):
        client, _ = _make_client()
        resp = client.put("/alerts/99999", json={
            "threshold": 100.0,
        })
        assert resp.status_code == 404


class TestDeleteAlertRule:
    """T5: DELETE /alerts/{id} 删除预警规则。"""

    def test_delete_rule(self):
        client, _ = _make_client()
        create_resp = client.post("/alerts", json={
            "stock_code": "600519",
            "condition_type": "price_below",
            "threshold": 1500.00,
        })
        rule_id = create_resp.json()["id"]

        resp = client.delete(f"/alerts/{rule_id}")
        assert resp.status_code == 204

        list_resp = client.get("/alerts")
        assert list_resp.json() == []

    def test_delete_nonexistent_returns_404(self):
        client, _ = _make_client()
        resp = client.delete("/alerts/99999")
        assert resp.status_code == 404


class TestToggleAlertRule:
    """T6: PATCH /alerts/{id}/toggle 切换规则状态。"""

    def test_toggle_active_to_paused(self):
        client, _ = _make_client()
        create_resp = client.post("/alerts", json={
            "stock_code": "600519",
            "condition_type": "price_below",
            "threshold": 1500.00,
        })
        rule_id = create_resp.json()["id"]

        resp = client.patch(f"/alerts/{rule_id}/toggle")
        assert resp.status_code == 200
        assert resp.json()["status"] == "paused"

    def test_toggle_paused_to_active(self):
        client, _ = _make_client()
        create_resp = client.post("/alerts", json={
            "stock_code": "600519",
            "condition_type": "price_below",
            "threshold": 1500.00,
        })
        rule_id = create_resp.json()["id"]

        client.patch(f"/alerts/{rule_id}/toggle")
        resp = client.patch(f"/alerts/{rule_id}/toggle")
        assert resp.status_code == 200
        assert resp.json()["status"] == "active"

    def test_toggle_nonexistent_returns_404(self):
        client, _ = _make_client()
        resp = client.patch("/alerts/99999/toggle")
        assert resp.status_code == 404
