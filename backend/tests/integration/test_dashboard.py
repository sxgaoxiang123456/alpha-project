"""Dashboard 路由集成测试 — 验证页面渲染和行情 Partial HTML。"""

import importlib
import sys
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from backend.app.schemas.dashboard import BriefingData, DashboardViewResponse, MarketSnapshot, StockCardData


def _fresh_app(monkeypatch, tmp_path):
    database_path = tmp_path / "dashboard.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database_path}")

    modules_to_clear = [
        "backend.app.main",
        "backend.app.routers",
        "backend.app.dependencies",
        "backend.app.models",
        "backend.app.database",
        "backend.app.config",
    ]
    for name in modules_to_clear:
        for loaded_name in list(sys.modules):
            if loaded_name == name or loaded_name.startswith(f"{name}."):
                sys.modules.pop(loaded_name, None)

    main = importlib.import_module("backend.app.main")
    return main.app, database_path


def _mock_dashboard_service():
    """返回固定 mock 数据的 DashboardService。"""
    svc = MagicMock()
    svc.build_dashboard_view = AsyncMock(return_value=DashboardViewResponse(
        market_indices=[
            MarketSnapshot(name="上证指数", current_value=3000.0, change_percent=1.23, change_amount=36.5),
        ],
        watchlist=[
            StockCardData(code="600000", name="浦发银行", current_price=10.5, change_percent=2.5, change_amount=0.25),
        ],
        briefing=BriefingData(insights=["大盘整体向好"]),
    ))
    return svc


class TestDashboardPage:
    def test_dashboard_root_returns_200(self, monkeypatch, tmp_path):
        """GET / 返回 HTTP 200。"""
        app, _ = _fresh_app(monkeypatch, tmp_path)
        monkeypatch.setattr("backend.app.routers.dashboard._get_dashboard_service", lambda db: _mock_dashboard_service())
        with TestClient(app) as client:
            response = client.get("/")
        assert response.status_code == 200

    def test_dashboard_contains_market_section(self, monkeypatch, tmp_path):
        """页面包含大盘指数模块。"""
        app, _ = _fresh_app(monkeypatch, tmp_path)
        monkeypatch.setattr("backend.app.routers.dashboard._get_dashboard_service", lambda db: _mock_dashboard_service())
        with TestClient(app) as client:
            response = client.get("/")
        assert "大盘指数" in response.text

    def test_dashboard_contains_watchlist_section(self, monkeypatch, tmp_path):
        """页面包含自选股模块。"""
        app, _ = _fresh_app(monkeypatch, tmp_path)
        monkeypatch.setattr("backend.app.routers.dashboard._get_dashboard_service", lambda db: _mock_dashboard_service())
        with TestClient(app) as client:
            response = client.get("/")
        assert "自选股" in response.text

    def test_dashboard_contains_briefing_section(self, monkeypatch, tmp_path):
        """页面包含简报模块。"""
        app, _ = _fresh_app(monkeypatch, tmp_path)
        monkeypatch.setattr("backend.app.routers.dashboard._get_dashboard_service", lambda db: _mock_dashboard_service())
        with TestClient(app) as client:
            response = client.get("/")
        assert "AI 简报" in response.text

    def test_market_data_partial_returns_200(self, monkeypatch, tmp_path):
        """GET /market_data 返回 Partial HTML。"""
        app, _ = _fresh_app(monkeypatch, tmp_path)
        monkeypatch.setattr("backend.app.routers.dashboard._get_dashboard_service", lambda db: _mock_dashboard_service())
        with TestClient(app) as client:
            response = client.get("/market_data")
        assert response.status_code == 200

    def test_market_data_is_partial(self, monkeypatch, tmp_path):
        """market_data 返回的是 Partial HTML（不含完整 HTML 结构）。"""
        app, _ = _fresh_app(monkeypatch, tmp_path)
        monkeypatch.setattr("backend.app.routers.dashboard._get_dashboard_service", lambda db: _mock_dashboard_service())
        with TestClient(app) as client:
            response = client.get("/market_data")
        assert "<!DOCTYPE html>" not in response.text
        assert "上证指数" in response.text
