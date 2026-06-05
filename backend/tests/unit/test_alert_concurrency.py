"""BE-G2: 并发原子性验证 — 50 条预警规则上限在并发下不被突破。

RED 阶段 —— 并发测试尚未编写。
"""

from concurrent.futures import ThreadPoolExecutor, as_completed

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.database import Base
from backend.app.dependencies import get_db
from backend.app.routers.alerts import router


def _make_client():
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

    return TestClient(app)


def _create_rule(client, stock_code):
    return client.post("/alerts", json={
        "stock_code": stock_code,
        "condition_type": "price_below",
        "threshold": 100.0,
    })


class TestConcurrentAlertLimit:
    """并发下 50 条规则上限不被突破。"""

    def test_concurrent_create_does_not_exceed_50(self):
        """N 个线程并发创建 51 条规则 → 最终 ≤ 50 条。"""
        client = _make_client()

        # Step 1: 先创建 45 条规则腾出空间
        for i in range(45):
            code = f"60{i:04d}"
            resp = _create_rule(client, code)
            assert resp.status_code == 201, f"创建第 {i+1} 条失败: {resp.json()}"

        # Step 2: 并发创建 10 条 (只有 5 个名额)
        remaining_codes = [f"61{i:04d}" for i in range(10)]

        def post_rule(code):
            return code, _create_rule(client, code).status_code

        results = []
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(post_rule, code) for code in remaining_codes]
            for future in as_completed(futures):
                results.append(future.result())

        # Step 3: 验证成功数 ≤ 5
        success_count = sum(1 for _, status in results if status == 201)
        assert success_count <= 5, f"成功创建 {success_count} 条，超过 5 个名额"

        # Step 4: 验证总数 ≤ 50
        list_resp = client.get("/alerts?status=active")
        total = len(list_resp.json())
        assert total <= 50, f"生效规则总数 {total} 超过 50 条上限"

    def test_concurrent_create_all_49_then_2(self):
        """49 条已有 + 2 条并发 → 仅 1 条成功。"""
        client = _make_client()

        for i in range(49):
            code = f"60{i:04d}"
            resp = _create_rule(client, code)
            assert resp.status_code == 201

        def post_rule(code):
            return code, _create_rule(client, code).status_code

        results = []
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(post_rule, f"61{i:04d}") for i in range(2)]
            for future in as_completed(futures):
                results.append(future.result())

        # 仅 1 条应成功
        success_count = sum(1 for _, status in results if status == 201)
        assert success_count == 1, f"预期 1 条成功，实际 {success_count} 条"

        total = len(client.get("/alerts?status=active").json())
        assert total == 50
