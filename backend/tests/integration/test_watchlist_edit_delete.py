import sys

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


class TestPutWatchlist:
    def test_edit_cost_price_and_shares_returns_200(self, monkeypatch, tmp_path):
        app, db_path = _fresh_app(monkeypatch, tmp_path)

        import backend.app.services.stock_search as ss

        def mock_search(query, **kwargs):
            from backend.app.schemas.stock import StockSearchResult

            return StockSearchResult.model_validate(
                _mock_search_stock_result("600519", "贵州茅台")
            )

        monkeypatch.setattr(ss, "search_stock", mock_search)

        with TestClient(app) as client:
            client.post("/watchlist", json={"stock_code": "600519", "shares": 100})
            response = client.put(
                "/watchlist/600519",
                json={"cost_price": "1600.00", "shares": 200},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["stock_code"] == "600519"
        assert data["cost_price"] == "1600.00"
        assert data["shares"] == 200

    def test_edit_nonexistent_stock_returns_404(self, monkeypatch, tmp_path):
        app, db_path = _fresh_app(monkeypatch, tmp_path)

        with TestClient(app) as client:
            response = client.put(
                "/watchlist/999999",
                json={"cost_price": "100.00"},
            )

        assert response.status_code == 404


class TestDeleteWatchlist:
    def test_delete_single_stock_returns_204(self, monkeypatch, tmp_path):
        app, db_path = _fresh_app(monkeypatch, tmp_path)

        import backend.app.services.stock_search as ss

        def mock_search(query, **kwargs):
            from backend.app.schemas.stock import StockSearchResult

            return StockSearchResult.model_validate(
                _mock_search_stock_result("600519", "贵州茅台")
            )

        monkeypatch.setattr(ss, "search_stock", mock_search)

        with TestClient(app) as client:
            client.post("/watchlist", json={"stock_code": "600519"})
            response = client.delete("/watchlist/600519")

        assert response.status_code == 204

        # 验证列表已空
        list_resp = client.get("/watchlist")
        assert list_resp.json() == []

    def test_delete_nonexistent_stock_returns_404(self, monkeypatch, tmp_path):
        app, db_path = _fresh_app(monkeypatch, tmp_path)

        with TestClient(app) as client:
            response = client.delete("/watchlist/999999")

        assert response.status_code == 404


class TestBatchDeleteWatchlist:
    def test_batch_delete_returns_200_with_count(self, monkeypatch, tmp_path):
        app, db_path = _fresh_app(monkeypatch, tmp_path)

        import backend.app.services.stock_search as ss

        def mock_search(query, **kwargs):
            from backend.app.schemas.stock import StockSearchResult

            return StockSearchResult.model_validate(
                _mock_search_stock_result(query, f"股票{query}")
            )

        monkeypatch.setattr(ss, "search_stock", mock_search)

        with TestClient(app) as client:
            for i in range(5):
                code = f"{600000 + i:06d}"
                client.post("/watchlist", json={"stock_code": code})

            response = client.post("/watchlist/batch-delete", json={"codes": ["600000", "600001", "600002", "600003", "600004"]})

        assert response.status_code == 200
        data = response.json()
        assert data["deleted_count"] == 5
        assert "已删除" in data["message"]

    def test_batch_delete_partial_missing_returns_success_for_existing(self, monkeypatch, tmp_path):
        app, db_path = _fresh_app(monkeypatch, tmp_path)

        import backend.app.services.stock_search as ss

        def mock_search(query, **kwargs):
            from backend.app.schemas.stock import StockSearchResult

            return StockSearchResult.model_validate(
                _mock_search_stock_result(query, f"股票{query}")
            )

        monkeypatch.setattr(ss, "search_stock", mock_search)

        with TestClient(app) as client:
            client.post("/watchlist", json={"stock_code": "600000"})
            client.post("/watchlist", json={"stock_code": "600001"})

            response = client.post(
                "/watchlist/batch-delete",
                json={"codes": ["600000", "600001", "999999"]},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["deleted_count"] == 2

    def test_batch_delete_empty_codes_returns_422(self, monkeypatch, tmp_path):
        app, db_path = _fresh_app(monkeypatch, tmp_path)

        with TestClient(app) as client:
            response = client.post("/watchlist/batch-delete", json={"codes": []})

        assert response.status_code == 422
