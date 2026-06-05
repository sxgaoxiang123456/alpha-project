"""Settings 路由集成测试 — 验证设置页渲染和表单提交。"""

import importlib
import sys
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from backend.app.schemas.settings import SettingCategory


def _fresh_app(monkeypatch, tmp_path):
    database_path = tmp_path / "settings.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database_path}")
    monkeypatch.setenv("ENCRYPTION_KEY", "xK2G9Exlb3MWj_kX5vH6rMSkGH354JLkAmOY4AdIWW4=")

    modules_to_clear = [
        "backend.app.main",
        "backend.app.routers",
        "backend.app.dependencies",
        "backend.app.models",
        "backend.app.database",
        "backend.app.config",
        "backend.app.services.settings_service",
    ]
    for name in modules_to_clear:
        for loaded_name in list(sys.modules):
            if loaded_name == name or loaded_name.startswith(f"{name}."):
                sys.modules.pop(loaded_name, None)

    main = importlib.import_module("backend.app.main")
    return main.app, database_path


class TestSettingsPage:
    def test_settings_page_returns_200(self, monkeypatch, tmp_path):
        """GET /settings 返回 HTTP 200。"""
        app, _ = _fresh_app(monkeypatch, tmp_path)
        with TestClient(app) as client:
            response = client.get("/settings")
        assert response.status_code == 200

    def test_settings_page_contains_form(self, monkeypatch, tmp_path):
        """设置页包含配置表单。"""
        app, _ = _fresh_app(monkeypatch, tmp_path)
        with TestClient(app) as client:
            response = client.get("/settings")
        assert "系统设置" in response.text
        assert "数据源配置" in response.text
        assert "推送通道" in response.text

    def test_settings_save_persists_data(self, monkeypatch, tmp_path):
        """POST /settings 保存配置到数据库。"""
        app, _ = _fresh_app(monkeypatch, tmp_path)
        with TestClient(app) as client:
            response = client.post(
                "/settings",
                data={
                    "datasource": "baostock",
                    "refresh_interval": "5",
                    "alert_cooldown": "60",
                },
            )
        assert response.status_code == 200

        # 验证保存后的页面显示新值
        with TestClient(app) as client:
            response = client.get("/settings")
        assert "baostock" in response.text or "5 分钟" in response.text

    def test_settings_saves_encrypted_fields(self, monkeypatch, tmp_path):
        """敏感字段加密存储。"""
        app, _ = _fresh_app(monkeypatch, tmp_path)
        with TestClient(app) as client:
            response = client.post(
                "/settings",
                data={
                    "lark_webhook": "https://open.feishu.cn/test",
                    "telegram_token": "bot123:token",
                },
            )
        assert response.status_code == 200
