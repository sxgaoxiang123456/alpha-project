"""F8 NL 预警外部依赖韧性验证。

验证 /api/alerts/natural-language 在 LLM 或股票数据源故障时，
仍返回清晰降级响应，不泄露异常、不崩溃。
"""

from fastapi import FastAPI
from fastapi.testclient import TestClient
import httpx
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from unittest import mock

from backend.app.database import Base
from backend.app.dependencies import get_db
from backend.app.routers.alerts_nl import get_nl_alert_parser, router as nl_router
from backend.app.schemas.nl_alert import StockCandidate
from backend.app.services.briefing_llm_client import BriefingLLMClient
from backend.app.services.nl_alert_parser import NLAlertParser


def _make_client(*, stock_resolver=None, llm_client=None):
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

    parser = NLAlertParser(
        confidence_threshold=0.7,
        llm_client=llm_client,
        stock_resolver=stock_resolver,
    )

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_nl_alert_parser] = lambda: parser
    app.include_router(nl_router)

    return TestClient(app)


class _TimeoutTransport(httpx.MockTransport):
    """每次请求都抛出超时异常。"""

    def __init__(self):
        super().__init__(self.handle_request)

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("Request timed out")


class TestNLAlertLLMResilience:
    """LLM 兜底失败时，NL endpoint 返回降级响应。"""

    def test_llm_degraded_returns_graceful_message(self):
        """无 API key 的 LLM client 触发降级 → endpoint 返回未能理解。"""
        client = _make_client(
            stock_resolver=lambda q: [StockCandidate(stock_code="600519", stock_name="贵州茅台", sector="白酒", market_cap=20000.0, match_score=1.0)],
            llm_client=BriefingLLMClient(api_key=""),
        )

        # 该 query 规则解析器置信度不足，会尝试 LLM；LLM 无 key 立即降级
        resp = client.post("/api/alerts/natural-language", json={"query": "帮我盯着点茅台"})
        assert resp.status_code == 200, resp.json()
        data = resp.json()
        assert data["success"] is False
        assert "未能理解" in data["message"]
        assert data.get("rule") is None
        assert data.get("candidates") is None

    def test_llm_timeout_returns_graceful_message(self):
        """LLM 超时降级 → endpoint 返回未能理解。"""
        real_client_class = httpx.Client

        def _factory(*args, **kwargs):
            return real_client_class(transport=_TimeoutTransport())

        with mock.patch(
            "backend.app.services.briefing_llm_client.httpx.Client",
            side_effect=_factory,
        ):
            llm_client = BriefingLLMClient(
                api_key="test-key",
                base_url="https://api.deepseek.com",
                timeout_seconds=1,
                retry_attempts=1,
                retry_interval_seconds=0,
            )
            client = _make_client(
                stock_resolver=lambda q: [StockCandidate(stock_code="600519", stock_name="贵州茅台", sector="白酒", market_cap=20000.0, match_score=1.0)],
                llm_client=llm_client,
            )

            resp = client.post("/api/alerts/natural-language", json={"query": "帮我盯着点茅台"})

        assert resp.status_code == 200, resp.json()
        data = resp.json()
        assert data["success"] is False
        assert "未能理解" in data["message"]


class TestNLAlertStockResolverResilience:
    """股票数据源失败时，NL endpoint 返回降级响应。"""

    def test_stock_resolver_failure_returns_graceful_message(self):
        """股票数据源抛异常 → endpoint 返回未能找到匹配股票。"""
        with mock.patch(
            "backend.app.services.nl_alert_parser.search_stock_candidates",
            side_effect=RuntimeError("akshare 连接失败"),
        ):
            client = _make_client()
            resp = client.post("/api/alerts/natural-language", json={"query": "茅台跌破 1500 提醒我"})

        assert resp.status_code == 200, resp.json()
        data = resp.json()
        assert data["success"] is False
        assert "未能找到匹配股票" in data["message"]

    def test_stock_resolver_returns_empty_returns_graceful_message(self):
        """股票数据源返回空列表 → endpoint 返回未能找到匹配股票。"""
        with mock.patch(
            "backend.app.services.nl_alert_parser.search_stock_candidates",
            return_value=[],
        ):
            client = _make_client()
            resp = client.post("/api/alerts/natural-language", json={"query": "茅台跌破 1500 提醒我"})

        assert resp.status_code == 200, resp.json()
        data = resp.json()
        assert data["success"] is False
        assert "未能找到匹配股票" in data["message"]
