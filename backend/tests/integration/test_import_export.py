import io
import sys
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient


def _fresh_app(monkeypatch, tmp_path):
    database_path = tmp_path / "watchlist.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database_path}")

    modules_to_clear = [
        "backend.app.main",
        "backend.app.routers.watchlist",
        "backend.app.routers.import_export",
        "backend.app.services.stock_search",
        "backend.app.services.csv_import",
        "backend.app.dependencies",
        "backend.app.models.group",
        "backend.app.models.stock",
        "backend.app.models.watchlist",
        "backend.models",
        "backend.app.database",
        "backend.app.config",
    ]
    for name in modules_to_clear:
        sys.modules.pop(name, None)

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


class TestImportWatchlist:
    def test_import_valid_csv_returns_200_with_success_details(self, monkeypatch, tmp_path):
        app, db_path = _fresh_app(monkeypatch, tmp_path)

        import backend.app.services.stock_search as ss

        def mock_search(query, **kwargs):
            from backend.app.schemas.stock import StockSearchResult

            return StockSearchResult.model_validate(
                _mock_search_stock_result(query, f"股票{query}")
            )

        monkeypatch.setattr(ss, "search_stock", mock_search)

        csv_content = "code,name,group,cost_price,shares\n600000,股票1,默认分组,10.50,100\n600001,股票2,持仓,,\n"

        with TestClient(app) as client:
            response = client.post(
                "/watchlist/import",
                files={"file": ("watchlist.csv", io.BytesIO(csv_content.encode("utf-8")), "text/csv")},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success_count"] == 2
        assert data["failure_count"] == 0
        assert len(data["successes"]) == 2

    def test_import_csv_with_invalid_rows_returns_partial_success(self, monkeypatch, tmp_path):
        app, db_path = _fresh_app(monkeypatch, tmp_path)

        import backend.app.services.stock_search as ss

        def mock_search(query, **kwargs):
            from backend.app.schemas.stock import StockSearchResult

            return StockSearchResult.model_validate(
                _mock_search_stock_result(query, f"股票{query}")
            )

        monkeypatch.setattr(ss, "search_stock", mock_search)

        csv_content = "code,name,group,cost_price,shares\n600000,股票1,默认分组,,\n60001A,错误格式,默认分组,,\n600002,股票2,持仓,,\n"

        with TestClient(app) as client:
            response = client.post(
                "/watchlist/import",
                files={"file": ("watchlist.csv", io.BytesIO(csv_content.encode("utf-8")), "text/csv")},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success_count"] == 2
        assert data["failure_count"] == 1
        assert len(data["failures"]) == 1
        assert "60001A" in data["failures"][0]["code"] or "格式错误" in data["failures"][0]["reason"]

    def test_import_over_100_rows_returns_400(self, monkeypatch, tmp_path):
        app, db_path = _fresh_app(monkeypatch, tmp_path)

        lines = ["code,name,group,cost_price,shares"]
        for i in range(101):
            lines.append(f"{600000 + i:06d},股票{i},默认分组,,")
        csv_content = "\n".join(lines)

        with TestClient(app) as client:
            response = client.post(
                "/watchlist/import",
                files={"file": ("watchlist.csv", io.BytesIO(csv_content.encode("utf-8")), "text/csv")},
            )

        assert response.status_code == 400
        assert "100" in response.json()["detail"] or "上限" in response.json()["detail"]

    def test_import_oversized_file_returns_413(self, monkeypatch, tmp_path):
        app, db_path = _fresh_app(monkeypatch, tmp_path)

        # 100 行但每行很长，总大小超过 512KB（行数不超 100，但文件大小超限）
        long_name = "x" * 6000
        lines = ["code,name,group"]
        for i in range(99):
            lines.append(f"{600000 + i:06d},{long_name},default")
        large_content = "\n".join(lines).encode("utf-8")
        assert len(large_content) > 512 * 1024

        with TestClient(app) as client:
            response = client.post(
                "/watchlist/import",
                files={"file": ("huge.csv", io.BytesIO(large_content), "text/csv")},
            )

        assert response.status_code == 413


class TestExportWatchlist:
    def test_export_returns_csv_file(self, monkeypatch, tmp_path):
        app, db_path = _fresh_app(monkeypatch, tmp_path)

        import backend.app.services.stock_search as ss

        def mock_search(query, **kwargs):
            from backend.app.schemas.stock import StockSearchResult

            return StockSearchResult.model_validate(
                _mock_search_stock_result(query, f"股票{query}")
            )

        monkeypatch.setattr(ss, "search_stock", mock_search)

        with TestClient(app) as client:
            client.post("/watchlist", json={"stock_code": "600519", "cost_price": "1500.50", "shares": 100})
            response = client.get("/watchlist/export")

        assert response.status_code == 200
        assert response.headers["content-type"] == "text/csv; charset=utf-8"
        assert "attachment" in response.headers["content-disposition"]
        assert "watchlist" in response.headers["content-disposition"]

        content = response.content.decode("utf-8")
        assert "code,name,group,cost_price,shares" in content
        assert "600519" in content
        assert "股票600519" in content
        assert "1500.50" in content
        assert "100" in content

    def test_export_empty_watchlist_returns_header_only(self, monkeypatch, tmp_path):
        app, db_path = _fresh_app(monkeypatch, tmp_path)

        with TestClient(app) as client:
            response = client.get("/watchlist/export")

        assert response.status_code == 200
        content = response.content.decode("utf-8")
        assert "code,name,group,cost_price,shares" in content
        lines = [line for line in content.strip().split("\n") if line.strip()]
        assert len(lines) == 1  # 只有表头
