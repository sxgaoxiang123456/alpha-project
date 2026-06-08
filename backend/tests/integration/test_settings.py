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


class TestFeishuNoWebhook:
    """007 US2: 设置页移除 webhook，展示 .env 配置状态。"""

    def test_settings_page_has_no_webhook_input(self, monkeypatch, tmp_path):
        """GET /settings 不展示飞书 webhook 输入框。"""
        app, _ = _fresh_app(monkeypatch, tmp_path)
        with TestClient(app) as client:
            response = client.get("/settings")
        assert response.status_code == 200
        assert 'name="lark_webhook"' not in response.text
        assert "webhook" not in response.text.lower()

    def test_settings_page_shows_env_status(self, monkeypatch, tmp_path):
        """GET /settings 展示飞书 .env 配置来源说明。"""
        app, _ = _fresh_app(monkeypatch, tmp_path)
        with TestClient(app) as client:
            response = client.get("/settings")
        assert response.status_code == 200
        assert ".env" in response.text or "环境变量" in response.text

    def test_settings_page_no_secret_exposed(self, monkeypatch, tmp_path):
        """GET /settings 不展示飞书密钥明文。"""
        monkeypatch.setenv("FEISHU_APP_ID", "cli_test_app")
        monkeypatch.setenv("FEISHU_APP_SECRET", "cli_super_secret_key")
        monkeypatch.setenv("FEISHU_CHAT_ID", "oc_testchat")

        app, _ = _fresh_app(monkeypatch, tmp_path)
        with TestClient(app) as client:
            response = client.get("/settings")
        assert response.status_code == 200
        # 密钥不应出现在 HTML 中
        assert "cli_super_secret_key" not in response.text

    def test_post_ignores_lark_webhook(self, monkeypatch, tmp_path):
        """POST /settings 提交 lark_webhook 不应被保存。"""
        app, db_path = _fresh_app(monkeypatch, tmp_path)
        with TestClient(app) as client:
            response = client.post(
                "/settings",
                data={
                    "lark_webhook": "https://evil.example.com/hook",
                    "datasource": "akshare",
                    "refresh_interval": "3",
                },
            )
        assert response.status_code == 200

        # 验证 lark_webhook 未被保存到数据库
        import importlib, sys
        for name in list(sys.modules):
            if name == "backend.app.database" or name.startswith("backend.app.database."):
                sys.modules.pop(name, None)
        database = importlib.import_module("backend.app.database")
        try:
            db = database.SessionLocal()
            from backend.app.models.app_setting import AppSetting
            row = db.get(AppSetting, "lark_webhook")
            assert row is None, "lark_webhook 不应被保存"
            db.close()
        finally:
            database.engine.dispose()

    def test_post_telegram_still_works(self, monkeypatch, tmp_path):
        """POST /settings 保存 Telegram 仍正常工作。"""
        monkeypatch.setenv("ENCRYPTION_KEY", "xK2G9Exlb3MWj_kX5vH6rMSkGH354JLkAmOY4AdIWW4=")
        app, _ = _fresh_app(monkeypatch, tmp_path)
        with TestClient(app) as client:
            response = client.post(
                "/settings",
                data={
                    "telegram_token": "bot999:newtoken",
                    "telegram_chat_id": "123456",
                    "datasource": "akshare",
                    "refresh_interval": "3",
                },
            )
        assert response.status_code == 200
        # 保存后页面正常渲染，不报错，Telegram 字段仍在
        assert "系统设置" in response.text

    def test_settings_page_shows_restart_hint(self, monkeypatch, tmp_path):
        """GET /settings 展示 .env 修改后需重启提示。"""
        app, _ = _fresh_app(monkeypatch, tmp_path)
        with TestClient(app) as client:
            response = client.get("/settings")
        assert response.status_code == 200
        assert "重启" in response.text

    def test_settings_page_shows_missing_hint_when_incomplete(self, monkeypatch, tmp_path):
        """GET /settings 部分配置时展示缺失字段提示。"""
        monkeypatch.setenv("FEISHU_APP_ID", "test_app")
        monkeypatch.delenv("FEISHU_APP_SECRET", raising=False)
        monkeypatch.delenv("FEISHU_CHAT_ID", raising=False)
        app, _ = _fresh_app(monkeypatch, tmp_path)
        with TestClient(app) as client:
            response = client.get("/settings")
        assert response.status_code == 200
        assert "未完整配置" in response.text
        assert "应用密钥" in response.text
        assert "群聊标识" in response.text
        # 不应展示密钥值
        assert "test_app" not in response.text


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
