"""F8 自然语言设预警 API 集成测试。"""

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.database import Base
from backend.app.dependencies import get_db
from backend.app.routers.alerts_nl import get_nl_alert_parser, router
from backend.app.schemas.nl_alert import StockCandidate
from backend.app.services.nl_alert_parser import NLAlertParser


def _fake_candidates(query: str) -> list[StockCandidate]:
    data = {
        "600519": StockCandidate(stock_code="600519", stock_name="贵州茅台", sector="白酒", market_cap=20000.0, match_score=1.0),
        "600036": StockCandidate(stock_code="600036", stock_name="招商银行", sector="银行", market_cap=8500.5, match_score=1.0),
        "601166": StockCandidate(stock_code="601166", stock_name="兴业银行", sector="银行", market_cap=3200.0, match_score=1.0),
    }
    if query in data:
        return [data[query]]
    if query == "银行":
        return [data["600036"], data["601166"]]
    if "茅台" in query:
        return [data["600519"]]
    if "五粮液" in query:
        return [StockCandidate(stock_code="000858", stock_name="五粮液", sector="白酒", market_cap=5000.0, match_score=1.0)]
    if query.isdigit() and len(query) == 6:
        return [StockCandidate(stock_code=query, stock_name=f"股票{query}", sector="未知", market_cap=0.0, match_score=1.0)]
    return []


def _make_client():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    import backend.app.models  # noqa: F401
    Base.metadata.create_all(bind=engine)

    app = FastAPI()

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    parser = NLAlertParser(confidence_threshold=0.7, stock_resolver=_fake_candidates)

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_nl_alert_parser] = lambda: parser
    app.include_router(router)

    return TestClient(app), TestingSessionLocal


class TestCreateAlertFromNaturalLanguage:
    def test_create_price_below(self):
        client, _ = _make_client()
        resp = client.post("/alerts/natural-language", json={"query": "茅台跌破 1500 提醒我"})
        assert resp.status_code == 200, resp.json()
        data = resp.json()
        assert data["success"] is True
        assert data["rule"]["stock_code"] == "600519"
        assert data["rule"]["condition_type"] == "price_below"
        assert data["rule"]["threshold"] == 1500.0
        assert "贵州茅台" in data["message"]

    def test_create_price_above_with_code(self):
        client, _ = _make_client()
        resp = client.post("/alerts/natural-language", json={"query": "600519 涨到 1600 提醒我"})
        assert resp.status_code == 200, resp.json()
        data = resp.json()
        assert data["rule"]["condition_type"] == "price_above"
        assert data["rule"]["threshold"] == 1600.0

    def test_create_change_pct_below(self):
        client, _ = _make_client()
        resp = client.post("/alerts/natural-language", json={"query": "五粮液跌幅超过 3% 提醒我"})
        assert resp.status_code == 200, resp.json()
        data = resp.json()
        assert data["rule"]["condition_type"] == "change_pct_below"
        assert data["rule"]["threshold"] == -3.0

    def test_ambiguous_stock_name_returns_candidates(self):
        client, _ = _make_client()
        resp = client.post("/alerts/natural-language", json={"query": "银行跌破 10 元提醒我"})
        assert resp.status_code == 200, resp.json()
        data = resp.json()
        assert data["success"] is False
        assert data["candidates"]
        assert len(data["candidates"]) >= 2

    def test_selected_stock_code_creates_rule(self):
        client, _ = _make_client()
        resp = client.post("/alerts/natural-language", json={
            "query": "银行跌破 10 元提醒我",
            "selected_stock_code": "601166",
        })
        assert resp.status_code == 200, resp.json()
        data = resp.json()
        assert data["success"] is True
        assert data["rule"]["stock_code"] == "601166"

    def test_low_confidence_rejected(self):
        client, _ = _make_client()
        resp = client.post("/alerts/natural-language", json={"query": "帮我看着点茅台"})
        assert resp.status_code == 200, resp.json()
        data = resp.json()
        assert data["success"] is False
        assert "未能理解" in data["message"]

    def test_unsupported_volume_condition(self):
        client, _ = _make_client()
        resp = client.post("/alerts/natural-language", json={"query": "茅台成交量突破 10 万手提醒我"})
        assert resp.status_code == 200, resp.json()
        data = resp.json()
        assert data["success"] is False
        assert "成交量" in data["message"]

    def test_empty_query_rejected(self):
        client, _ = _make_client()
        resp = client.post("/alerts/natural-language", json={"query": ""})
        assert resp.status_code == 422

    def test_too_long_query_rejected(self):
        client, _ = _make_client()
        resp = client.post("/alerts/natural-language", json={"query": "x" * 201})
        assert resp.status_code == 422

    def test_duplicate_rule_rejected(self):
        client, _ = _make_client()
        client.post("/alerts/natural-language", json={"query": "茅台跌破 1500 提醒我"})
        resp = client.post("/alerts/natural-language", json={"query": "茅台跌破 1500 提醒我"})
        assert resp.status_code == 200, resp.json()
        data = resp.json()
        assert data["success"] is False
        assert "已存在" in data["message"]

    def test_rule_limit_rejected(self):
        client, _ = _make_client()
        for i in range(50):
            code = f"60{i:04d}"
            resp = client.post("/alerts/natural-language", json={
                "query": f"{code} 跌到 1 提醒我",
            })
            assert resp.status_code == 200, f"第 {i+1} 条失败: {resp.json()}"
            assert resp.json()["success"] is True, resp.json()

        resp = client.post("/alerts/natural-language", json={"query": "茅台跌破 1500 提醒我"})
        assert resp.status_code == 200, resp.json()
        data = resp.json()
        assert data["success"] is False
        assert "上限" in data["message"]
