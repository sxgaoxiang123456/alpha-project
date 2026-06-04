"""
C1 · 并发竞态补测：验证 100 只上限在并发下不被突破。

Gap ID: C1
Risk Tier: P0
Traceability: 覆盖 FR-009（自选股数量达到 100 只上限时拒绝新增）

SQLite 下由于文件级锁行为与 PostgreSQL 不同，本测试同时验证：
1. 并发请求不会导致总数超过 100（不变量）；
2. 若 SQLite 锁机制阻止并发写入，则请求应收到受控错误而非静默成功。
"""

import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

import pytest
from fastapi.testclient import TestClient


def _fresh_app(monkeypatch, tmp_path):
    database_path = tmp_path / "watchlist.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database_path}")

    modules_to_clear = [
        "backend.app.main",
        "backend.app.routers",
        "backend.app.services.stock_search",
        "backend.app.services.csv_import",
        "backend.app.dependencies",
        "backend.app.models",
        "backend.models",
        "backend.app.database",
        "backend.app.config",
    ]
    for name in modules_to_clear:
        for loaded_name in list(sys.modules):
            if loaded_name == name or loaded_name.startswith(f"{name}."):
                sys.modules.pop(loaded_name, None)

    main = __import__("backend.app.main", fromlist=["backend"])
    return main.app, database_path


def _mock_search_stock_result(code: str, name: str):
    return {
        "code": code,
        "name": name,
        "market": "沪",
        "sector": "白酒",
        "status": "正常",
    }


class TestConcurrentWatchlistLimit:
    """并发添加自选股，验证 100 只上限不会被突破。"""

    def test_concurrent_adds_at_limit_do_not_exceed_100(self, monkeypatch, tmp_path):
        """
        先填充 99 只股票，然后 5 个并发请求同时尝试添加不同股票。
        断言：最终总数 ≤ 100，且超出上限的请求收到 429。
        """
        app, db_path = _fresh_app(monkeypatch, tmp_path)

        import backend.app.services.stock_search as ss

        def mock_search(query, **kwargs):
            from backend.app.schemas.stock import StockSearchResult

            return StockSearchResult.model_validate(
                _mock_search_stock_result(query, f"股票{query}")
            )

        monkeypatch.setattr(ss, "search_stock", mock_search)

        # 预填充 99 只不同的股票
        with TestClient(app) as client:
            for i in range(99):
                code = f"{600000 + i:06d}"
                resp = client.post("/watchlist", json={"stock_code": code})
                assert resp.status_code == 201, f"预填充失败 at {code}: {resp.text}"

            # 确认当前数量
            list_resp = client.get("/watchlist")
            assert len(list_resp.json()) == 99

        # 5 个并发请求，每只不同代码
        codes_to_add = ["999995", "999996", "999997", "999998", "999999"]

        def _try_add(code: str):
            # 每个线程独立的 TestClient，但共享数据库文件
            with TestClient(app) as client:
                return client.post("/watchlist", json={"stock_code": code})

        results = []
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {executor.submit(_try_add, code): code for code in codes_to_add}
            for future in as_completed(futures):
                code = futures[future]
                try:
                    resp = future.result(timeout=10)
                    results.append((code, resp.status_code))
                except Exception as exc:
                    results.append((code, f"exception: {exc}"))

        # 最终数量校验
        with TestClient(app) as client:
            final_list = client.get("/watchlist")
            final_count = len(final_list.json())

        # 不变量：总数绝不超过 100
        assert final_count <= 100, (
            f"并发突破上限！最终数量 {final_count} > 100。\n"
            f"各请求结果: {results}"
        )

        # 统计成功数（201）与拒绝数（429）
        success_count = sum(1 for _, status in results if status == 201)
        rejected_count = sum(1 for _, status in results if status == 429)

        # 恰好 1 只成功，其余被拒绝
        assert success_count == 1, (
            f"预期恰好 1 只成功，实际 {success_count}。结果: {results}"
        )
        assert rejected_count == 4, (
            f"预期 4 只被拒绝，实际 {rejected_count}。结果: {results}"
        )

    def test_concurrent_adds_same_code_only_one_succeeds(self, monkeypatch, tmp_path):
        """
        并发添加同一只未存在的股票，验证仅 1 次成功，其余收到 409（重复）。
        这是 count 检查之外的第二个竞态窗口：唯一性检查与 INSERT 之间。
        """
        app, db_path = _fresh_app(monkeypatch, tmp_path)

        import backend.app.services.stock_search as ss

        def mock_search(query, **kwargs):
            from backend.app.schemas.stock import StockSearchResult

            return StockSearchResult.model_validate(
                _mock_search_stock_result("600519", "贵州茅台")
            )

        monkeypatch.setattr(ss, "search_stock", mock_search)

        # 预热：先触发 lifespan 初始化数据库，避免并发线程同时建表冲突
        with TestClient(app) as client:
            client.get("/health")

        def _try_add():
            with TestClient(app) as client:
                return client.post("/watchlist", json={"stock_code": "600519"})

        results = []
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(_try_add) for _ in range(5)]
            for future in as_completed(futures):
                try:
                    resp = future.result(timeout=10)
                    results.append(resp.status_code)
                except Exception as exc:
                    results.append(f"exception: {exc}")

        with TestClient(app) as client:
            final_list = client.get("/watchlist")
            final_count = len(final_list.json())

        # 不变量：同一只股票只能出现 1 次
        assert final_count == 1, (
            f"并发重复添加成功！最终数量 {final_count} > 1。结果: {results}"
        )

        success_count = sum(1 for s in results if s == 201)
        conflict_count = sum(1 for s in results if s == 409)

        assert success_count == 1, f"预期 1 次 201，实际 {success_count}。结果: {results}"
        assert conflict_count == 4, f"预期 4 次 409，实际 {conflict_count}。结果: {results}"
