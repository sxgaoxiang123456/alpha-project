import importlib
import sys
from decimal import Decimal

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


def import_fresh(module_name: str, *module_names_to_clear: str):
    for name in module_names_to_clear:
        sys.modules.pop(name, None)
    return importlib.import_module(module_name)


def _fresh_app(monkeypatch, tmp_path):
    database_path = tmp_path / "watchlist.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database_path}")

    modules_to_clear = [
        "backend.app.main",
        "backend.app.routers",
        "backend.app.services.stock_search",
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

    main = importlib.import_module("backend.app.main")
    return main.app, database_path


def _mock_search_stock_result(code: str, name: str):
    return {
        "code": code,
        "name": name,
        "market": "沪",
        "sector": "白酒",
        "status": "正常",
    }


class TestPostWatchlist:
    def test_add_stock_returns_201_and_item(self, monkeypatch, tmp_path):
        app, db_path = _fresh_app(monkeypatch, tmp_path)

        import backend.app.services.stock_search as ss

        original_search = ss.search_stock

        def mock_search(query, **kwargs):
            if query == "600519":
                from backend.app.schemas.stock import StockSearchResult

                return StockSearchResult.model_validate(
                    _mock_search_stock_result("600519", "贵州茅台")
                )
            return original_search(query, **kwargs)

        monkeypatch.setattr(ss, "search_stock", mock_search)

        with TestClient(app) as client:
            response = client.post(
                "/watchlist",
                json={"stock_code": "600519", "cost_price": "1500.50", "shares": 100},
            )

        assert response.status_code == 201
        data = response.json()
        assert data["stock_code"] == "600519"
        assert data["cost_price"] == "1500.50"
        assert data["shares"] == 100
        assert data["group_id"] == 1
        assert data["stock"]["name"] == "贵州茅台"

    def test_add_duplicate_stock_returns_409(self, monkeypatch, tmp_path):
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
            response = client.post("/watchlist", json={"stock_code": "600519"})

        assert response.status_code == 409
        assert "重复" in response.json()["detail"] or "已存在" in response.json()["detail"]

    def test_add_invalid_code_returns_404(self, monkeypatch, tmp_path):
        app, db_path = _fresh_app(monkeypatch, tmp_path)

        import backend.app.services.stock_search as ss

        def mock_search(query, **kwargs):
            return None

        monkeypatch.setattr(ss, "search_stock", mock_search)

        with TestClient(app) as client:
            response = client.post("/watchlist", json={"stock_code": "999999"})

        assert response.status_code == 404
        assert "不存在" in response.json()["detail"] or "未找到" in response.json()["detail"]

    def test_add_over_limit_returns_429(self, monkeypatch, tmp_path):
        app, db_path = _fresh_app(monkeypatch, tmp_path)

        import backend.app.services.stock_search as ss

        def mock_search(query, **kwargs):
            from backend.app.schemas.stock import StockSearchResult

            return StockSearchResult.model_validate(
                _mock_search_stock_result(query, f"股票{query}")
            )

        monkeypatch.setattr(ss, "search_stock", mock_search)

        with TestClient(app) as client:
            for i in range(100):
                code = f"{600000 + i:06d}"
                resp = client.post("/watchlist", json={"stock_code": code})
                assert resp.status_code == 201, f"Failed at {code}: {resp.json()}"

            response = client.post("/watchlist", json={"stock_code": "999999"})

        assert response.status_code == 429
        assert "上限" in response.json()["detail"] or "100" in response.json()["detail"]


class TestGetWatchlistSearch:
    def test_search_by_code_returns_candidates(self, monkeypatch, tmp_path):
        app, db_path = _fresh_app(monkeypatch, tmp_path)

        import backend.app.services.stock_search as ss

        def mock_search_stocks(query, **kwargs):
            from backend.app.schemas.stock import StockSearchResult

            return [
                StockSearchResult.model_validate(
                    _mock_search_stock_result("600519", "贵州茅台")
                )
            ]

        monkeypatch.setattr(ss, "search_stocks", mock_search_stocks)

        with TestClient(app) as client:
            response = client.get("/watchlist/search?q=600519")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["code"] == "600519"
        assert data[0]["name"] == "贵州茅台"

    def test_search_by_name_returns_candidates(self, monkeypatch, tmp_path):
        app, db_path = _fresh_app(monkeypatch, tmp_path)

        import backend.app.services.stock_search as ss

        def mock_search_stocks(query, **kwargs):
            from backend.app.schemas.stock import StockSearchResult

            return [
                StockSearchResult.model_validate(
                    _mock_search_stock_result("600519", "贵州茅台")
                ),
                StockSearchResult.model_validate(
                    _mock_search_stock_result("600809", "山西汾酒")
                ),
            ]

        monkeypatch.setattr(ss, "search_stocks", mock_search_stocks)

        with TestClient(app) as client:
            response = client.get("/watchlist/search?q=茅台")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert [item["code"] for item in data] == ["600519", "600809"]


class TestGetWatchlist:
    def test_list_returns_items_with_stock_and_group(self, monkeypatch, tmp_path):
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
            response = client.get("/watchlist")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["stock_code"] == "600519"
        assert data[0]["shares"] == 100
        assert data[0]["stock"]["name"] == "贵州茅台"
        assert data[0]["group"]["name"] == "默认分组"

    def test_list_empty_returns_empty_array(self, monkeypatch, tmp_path):
        app, db_path = _fresh_app(monkeypatch, tmp_path)

        with TestClient(app) as client:
            response = client.get("/watchlist")

        assert response.status_code == 200
        assert response.json() == []
