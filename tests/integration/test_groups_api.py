import sys

import pytest
from fastapi.testclient import TestClient


def _fresh_app(monkeypatch, tmp_path):
    database_path = tmp_path / "watchlist.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database_path}")

    modules_to_clear = [
        "backend.main",
        "backend.routers.watchlist",
        "backend.routers.groups",
        "backend.routers.import_export",
        "backend.services.stock_search",
        "backend.services.csv_import",
        "backend.dependencies",
        "backend.models.group",
        "backend.models.stock",
        "backend.models.watchlist",
        "backend.models",
        "backend.database",
        "backend.config",
    ]
    for name in modules_to_clear:
        sys.modules.pop(name, None)

    main = __import__("backend.main", fromlist=["backend"])
    return main.app, database_path


class TestPostGroups:
    def test_create_group_returns_201(self, monkeypatch, tmp_path):
        app, db_path = _fresh_app(monkeypatch, tmp_path)

        with TestClient(app) as client:
            response = client.post("/groups", json={"name": "持仓"})

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "持仓"
        assert "id" in data

    def test_create_duplicate_group_returns_409(self, monkeypatch, tmp_path):
        app, db_path = _fresh_app(monkeypatch, tmp_path)

        with TestClient(app) as client:
            client.post("/groups", json={"name": "持仓"})
            response = client.post("/groups", json={"name": "持仓"})

        assert response.status_code == 409
        assert "已存在" in response.json()["detail"] or "重复" in response.json()["detail"]


class TestGetGroups:
    def test_list_groups_includes_default(self, monkeypatch, tmp_path):
        app, db_path = _fresh_app(monkeypatch, tmp_path)

        with TestClient(app) as client:
            response = client.get("/groups")

        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        assert any(g["name"] == "默认分组" for g in data)

    def test_list_groups_after_create(self, monkeypatch, tmp_path):
        app, db_path = _fresh_app(monkeypatch, tmp_path)

        with TestClient(app) as client:
            client.post("/groups", json={"name": "持仓"})
            client.post("/groups", json={"name": "观察"})
            response = client.get("/groups")

        assert response.status_code == 200
        data = response.json()
        names = [g["name"] for g in data]
        assert "默认分组" in names
        assert "持仓" in names
        assert "观察" in names


class TestPutGroups:
    def test_rename_group_returns_200(self, monkeypatch, tmp_path):
        app, db_path = _fresh_app(monkeypatch, tmp_path)

        with TestClient(app) as client:
            create_resp = client.post("/groups", json={"name": "持仓"})
            group_id = create_resp.json()["id"]
            response = client.put(f"/groups/{group_id}", json={"name": "长线持仓"})

        assert response.status_code == 200
        assert response.json()["name"] == "长线持仓"

    def test_rename_to_existing_name_returns_409(self, monkeypatch, tmp_path):
        app, db_path = _fresh_app(monkeypatch, tmp_path)

        with TestClient(app) as client:
            client.post("/groups", json={"name": "持仓"})
            create_resp = client.post("/groups", json={"name": "观察"})
            group_id = create_resp.json()["id"]
            response = client.put(f"/groups/{group_id}", json={"name": "持仓"})

        assert response.status_code == 409

    def test_rename_nonexistent_group_returns_404(self, monkeypatch, tmp_path):
        app, db_path = _fresh_app(monkeypatch, tmp_path)

        with TestClient(app) as client:
            response = client.put("/groups/999", json={"name": "新名称"})

        assert response.status_code == 404


class TestDeleteGroups:
    def test_delete_group_with_move_to_default(self, monkeypatch, tmp_path):
        app, db_path = _fresh_app(monkeypatch, tmp_path)

        import backend.services.stock_search as ss

        def mock_search(query, **kwargs):
            from backend.schemas.stock import StockSearchResult

            return StockSearchResult.model_validate(
                {"code": query, "name": f"股票{query}", "market": "沪", "sector": None, "status": "正常"}
            )

        monkeypatch.setattr(ss, "search_stock", mock_search)

        with TestClient(app) as client:
            # 创建分组并添加股票
            group_resp = client.post("/groups", json={"name": "持仓"})
            group_id = group_resp.json()["id"]
            client.post("/watchlist", json={"stock_code": "600000", "group_id": group_id})

            # 删除分组，选择移入默认
            response = client.delete(f"/groups/{group_id}?strategy=move_to_default")

        assert response.status_code == 200
        assert response.json()["moved_count"] == 1

    def test_delete_group_with_delete_all(self, monkeypatch, tmp_path):
        app, db_path = _fresh_app(monkeypatch, tmp_path)

        import backend.services.stock_search as ss

        def mock_search(query, **kwargs):
            from backend.schemas.stock import StockSearchResult

            return StockSearchResult.model_validate(
                {"code": query, "name": f"股票{query}", "market": "沪", "sector": None, "status": "正常"}
            )

        monkeypatch.setattr(ss, "search_stock", mock_search)

        with TestClient(app) as client:
            group_resp = client.post("/groups", json={"name": "观察"})
            group_id = group_resp.json()["id"]
            client.post("/watchlist", json={"stock_code": "600000", "group_id": group_id})

            response = client.delete(f"/groups/{group_id}?strategy=delete_all")

        assert response.status_code == 200
        assert response.json()["deleted_count"] == 1

    def test_delete_default_group_returns_403(self, monkeypatch, tmp_path):
        app, db_path = _fresh_app(monkeypatch, tmp_path)

        with TestClient(app) as client:
            response = client.delete("/groups/1")

        assert response.status_code == 403

    def test_delete_nonexistent_group_returns_404(self, monkeypatch, tmp_path):
        app, db_path = _fresh_app(monkeypatch, tmp_path)

        with TestClient(app) as client:
            response = client.delete("/groups/999")

        assert response.status_code == 404

    def test_delete_group_with_invalid_strategy_returns_422(self, monkeypatch, tmp_path):
        app, db_path = _fresh_app(monkeypatch, tmp_path)

        with TestClient(app) as client:
            response = client.delete("/groups/2?strategy=invalid_strategy")

        assert response.status_code == 422
