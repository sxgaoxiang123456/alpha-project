"""响应式与视觉合规测试 — 验证 HTML 包含响应式类和设计系统 token。"""

import importlib
import sys
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from backend.app.schemas.dashboard import (
    BriefingData,
    DashboardViewResponse,
    MarketSnapshot,
    StockCardData,
)


def _fresh_app(monkeypatch, tmp_path):
    database_path = tmp_path / "responsive.db"
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


class TestResponsiveClasses:
    def test_grid_system_present(self, monkeypatch, tmp_path):
        """页面使用 12 列网格系统。"""
        app, _ = _fresh_app(monkeypatch, tmp_path)
        monkeypatch.setattr("backend.app.routers.dashboard._get_dashboard_service", lambda db: _mock_dashboard_service())
        with TestClient(app) as client:
            response = client.get("/")
        assert "grid-cols-12" in response.text
        assert "col-span-12" in response.text

    def test_viewport_meta_tag(self, monkeypatch, tmp_path):
        """页面包含 viewport meta 标签。"""
        app, _ = _fresh_app(monkeypatch, tmp_path)
        monkeypatch.setattr("backend.app.routers.dashboard._get_dashboard_service", lambda db: _mock_dashboard_service())
        with TestClient(app) as client:
            response = client.get("/")
        assert 'name="viewport"' in response.text
        assert "width=device-width" in response.text


class TestVisualCompliance:
    def test_design_system_tokens_present(self, monkeypatch, tmp_path):
        """页面使用设计系统颜色/字体 token。"""
        app, _ = _fresh_app(monkeypatch, tmp_path)
        monkeypatch.setattr("backend.app.routers.dashboard._get_dashboard_service", lambda db: _mock_dashboard_service())
        with TestClient(app) as client:
            response = client.get("/")
        assert "bg-surface-raised" in response.text  # 骨架屏使用 surface-raised
        assert "text-on-surface" in response.text
        assert "font-headline-md" in response.text

    def test_material_symbols_loaded(self, monkeypatch, tmp_path):
        """页面加载 Material Symbols 字体。"""
        app, _ = _fresh_app(monkeypatch, tmp_path)
        monkeypatch.setattr("backend.app.routers.dashboard._get_dashboard_service", lambda db: _mock_dashboard_service())
        with TestClient(app) as client:
            response = client.get("/")
        assert "Material+Symbols+Outlined" in response.text

    def test_tailwind_config_custom_colors(self, monkeypatch, tmp_path):
        """Tailwind 配置包含自定义颜色。"""
        app, _ = _fresh_app(monkeypatch, tmp_path)
        monkeypatch.setattr("backend.app.routers.dashboard._get_dashboard_service", lambda db: _mock_dashboard_service())
        with TestClient(app) as client:
            response = client.get("/")
        assert "market-up" in response.text
        assert "market-down" in response.text
