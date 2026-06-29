"""F8 NL 预警并发原子性验证。

验证 /api/alerts/natural-language 在并发创建规则时：
1. 50 条上限不被突破；
2. 重复规则不会重复创建。
"""

from concurrent.futures import ThreadPoolExecutor, as_completed

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.database import Base
from backend.app.dependencies import get_db
from backend.app.routers.alerts_nl import get_nl_alert_parser, router as nl_router
from backend.app.schemas.nl_alert import StockCandidate
from backend.app.services.nl_alert_parser import NLAlertParser


def _fake_candidates(query: str) -> list[StockCandidate]:
    """确定性股票解析：任何 6 位代码或名称都返回唯一候选。"""
    if query.isdigit() and len(query) == 6:
        return [StockCandidate(stock_code=query, stock_name=f"股票{query}", sector="未知", market_cap=0.0, match_score=1.0)]
    if "茅台" in query:
        return [StockCandidate(stock_code="600519", stock_name="贵州茅台", sector="白酒", market_cap=20000.0, match_score=1.0)]
    return [StockCandidate(stock_code="000001", stock_name=query, sector="未知", market_cap=0.0, match_score=1.0)]


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
    app.include_router(nl_router)

    return TestClient(app)


def _create_nl_rule(client, query):
    return client.post("/api/alerts/natural-language", json={"query": query})


class TestConcurrentNLAlertLimit:
    def test_concurrent_nl_create_does_not_exceed_50(self):
        """45 条已有 + 10 条并发 → 最终 ≤ 50 条。"""
        client = _make_client()

        for i in range(45):
            code = f"60{i:04d}"
            resp = _create_nl_rule(client, f"{code} 跌到 1 提醒我")
            assert resp.status_code == 200, f"创建第 {i+1} 条失败: {resp.json()}"
            assert resp.json()["success"] is True, resp.json()

        queries = [f"61{i:04d} 跌到 1 提醒我" for i in range(10)]

        def post_rule(query):
            return query, _create_nl_rule(client, query).json()

        results = []
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(post_rule, q) for q in queries]
            for future in as_completed(futures):
                results.append(future.result())

        success_count = sum(1 for _, data in results if data.get("success"))
        assert success_count <= 5, f"成功创建 {success_count} 条，超过 5 个名额"

    def test_concurrent_nl_create_all_49_then_2(self):
        """49 条已有 + 2 条并发 → 仅 1 条成功。"""
        client = _make_client()

        for i in range(49):
            code = f"60{i:04d}"
            resp = _create_nl_rule(client, f"{code} 跌到 1 提醒我")
            assert resp.status_code == 200
            assert resp.json()["success"] is True

        queries = ["610000 跌到 1 提醒我", "610001 跌到 1 提醒我"]

        def post_rule(query):
            return query, _create_nl_rule(client, query).json()

        results = []
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(post_rule, q) for q in queries]
            for future in as_completed(futures):
                results.append(future.result())

        success_count = sum(1 for _, data in results if data.get("success"))
        assert success_count == 1, f"预期 1 条成功，实际 {success_count} 条"

    def test_concurrent_duplicate_nl_rule_not_double_created(self):
        """同一 NL 请求并发 5 次 → 仅 1 条成功创建。"""
        client = _make_client()

        query = "600519 跌破 1500 提醒我"

        def post_rule(_):
            return _create_nl_rule(client, query).json()

        results = []
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(post_rule, i) for i in range(5)]
            for future in as_completed(futures):
                results.append(future.result())

        success_count = sum(1 for data in results if data.get("success"))
        assert success_count == 1, f"重复规则应仅创建 1 条，实际 {success_count} 条"
