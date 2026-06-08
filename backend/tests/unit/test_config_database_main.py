import importlib
import sys

from fastapi import FastAPI
from fastapi.testclient import TestClient


def import_fresh(module_name: str, *module_names_to_clear: str):
    for name in module_names_to_clear:
        for loaded_name in list(sys.modules):
            if loaded_name == name or loaded_name.startswith(f"{name}."):
                sys.modules.pop(loaded_name, None)
    return importlib.import_module(module_name)


def test_settings_reads_database_url_from_environment(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./data/test-watchlist.db")
    config = import_fresh("backend.app.config", "backend.app.config")

    settings = config.Settings(_env_file=None)

    assert settings.database_url == "sqlite:///./data/test-watchlist.db"


def test_settings_uses_sqlite_default_when_database_url_missing(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    config = import_fresh("backend.app.config", "backend.app.config")

    settings = config.Settings(_env_file=None)

    assert settings.database_url == "sqlite:///./data/watchlist.db"


def test_database_exposes_engine_session_base_and_init_db(monkeypatch, tmp_path):
    database_path = tmp_path / "watchlist.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database_path}")
    database = import_fresh(
        "backend.app.database",
        "backend.app.models.group",
        "backend.app.models.stock",
        "backend.app.models",
        "backend.models",
        "backend.app.config",
        "backend.app.database",
    )

    assert database.engine is not None
    assert database.SessionLocal is not None
    assert database.Base is not None
    assert callable(database.init_db)

    database.init_db()

    assert database_path.exists()
    database.engine.dispose()


class TestFeishuEnvConfig:
    def test_feishu_env_fields_read_from_environment(self, monkeypatch):
        monkeypatch.setenv("FEISHU_APP_ID", "cli_test_app")
        monkeypatch.setenv("FEISHU_APP_SECRET", "cli_test_secret")
        monkeypatch.setenv("FEISHU_CHAT_ID", "oc_testchat")
        config = import_fresh("backend.app.config", "backend.app.config")
        settings = config.Settings(_env_file=None)

        assert settings.feishu_app_id == "cli_test_app"
        assert settings.feishu_app_secret == "cli_test_secret"
        assert settings.feishu_chat_id == "oc_testchat"

    def test_feishu_brand_defaults_to_feishu(self, monkeypatch):
        monkeypatch.delenv("FEISHU_BRAND", raising=False)
        config = import_fresh("backend.app.config", "backend.app.config")
        settings = config.Settings(_env_file=None)

        assert settings.feishu_brand == "feishu"

    def test_feishu_config_complete_when_all_present(self, monkeypatch):
        monkeypatch.setenv("FEISHU_APP_ID", "test")
        monkeypatch.setenv("FEISHU_APP_SECRET", "test")
        monkeypatch.setenv("FEISHU_CHAT_ID", "test")
        config = import_fresh("backend.app.config", "backend.app.config")
        settings = config.Settings(_env_file=None)

        assert settings.feishu_config_complete is True

    def test_feishu_config_incomplete_when_missing(self, monkeypatch):
        monkeypatch.setenv("FEISHU_APP_ID", "test")
        monkeypatch.delenv("FEISHU_APP_SECRET", raising=False)
        monkeypatch.delenv("FEISHU_CHAT_ID", raising=False)
        config = import_fresh("backend.app.config", "backend.app.config")
        settings = config.Settings(_env_file=None)

        assert settings.feishu_config_complete is False

    def test_feishu_fields_none_by_default(self, monkeypatch):
        monkeypatch.delenv("FEISHU_APP_ID", raising=False)
        monkeypatch.delenv("FEISHU_APP_SECRET", raising=False)
        monkeypatch.delenv("FEISHU_CHAT_ID", raising=False)
        config = import_fresh("backend.app.config", "backend.app.config")
        settings = config.Settings(_env_file=None)

        assert settings.feishu_app_id is None
        assert settings.feishu_app_secret is None
        assert settings.feishu_chat_id is None
        assert settings.feishu_config_complete is False


class TestPushServiceFactory:
    def test_factory_creates_feishu_client_when_env_complete(self, monkeypatch, tmp_path):
        database_path = tmp_path / "factory.db"
        monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database_path}")
        monkeypatch.setenv("FEISHU_APP_ID", "cli_test_app")
        monkeypatch.setenv("FEISHU_APP_SECRET", "cli_test_secret")
        monkeypatch.setenv("FEISHU_CHAT_ID", "oc_testchat")
        main = import_fresh(
            "backend.app.main",
            "backend.app.main",
            "backend.app.config",
            "backend.app.database",
            "backend.app.dependencies",
            "backend.app.models",
            "backend.app.routers",
            "backend.models",
        )
        try:
            main.init_db()
            push_service = main._push_service_factory()
            assert push_service.feishu is not None, "完整 env 应创建 FeishuClient"
            assert push_service.feishu.app_id == "cli_test_app"
            assert push_service.feishu.chat_id == "oc_testchat"
        finally:
            database = sys.modules.get("backend.app.database")
            if database is not None:
                database.engine.dispose()

    def test_factory_no_feishu_client_when_env_incomplete(self, monkeypatch, tmp_path):
        database_path = tmp_path / "factory_incomplete.db"
        monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database_path}")
        monkeypatch.setenv("FEISHU_APP_ID", "cli_test_app")
        monkeypatch.delenv("FEISHU_APP_SECRET", raising=False)
        monkeypatch.delenv("FEISHU_CHAT_ID", raising=False)
        main = import_fresh(
            "backend.app.main",
            "backend.app.main",
            "backend.app.config",
            "backend.app.database",
            "backend.app.dependencies",
            "backend.app.models",
            "backend.app.routers",
            "backend.models",
        )
        try:
            main.init_db()
            push_service = main._push_service_factory()
            assert push_service.feishu is None, "不完整 env 不应创建 FeishuClient"
        finally:
            database = sys.modules.get("backend.app.database")
            if database is not None:
                database.engine.dispose()

    def test_factory_defaults_brand_to_feishu(self, monkeypatch, tmp_path):
        database_path = tmp_path / "factory_brand.db"
        monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database_path}")
        monkeypatch.setenv("FEISHU_APP_ID", "cli_test_app")
        monkeypatch.setenv("FEISHU_APP_SECRET", "cli_test_secret")
        monkeypatch.setenv("FEISHU_CHAT_ID", "oc_testchat")
        monkeypatch.delenv("FEISHU_BRAND", raising=False)
        main = import_fresh(
            "backend.app.main",
            "backend.app.main",
            "backend.app.config",
            "backend.app.database",
            "backend.app.dependencies",
            "backend.app.models",
            "backend.app.routers",
            "backend.models",
        )
        try:
            main.init_db()
            push_service = main._push_service_factory()
            assert push_service.feishu is not None
            assert push_service.feishu.brand == "feishu", "FEISHU_BRAND 缺失应默认 feishu"
        finally:
            database = sys.modules.get("backend.app.database")
            if database is not None:
                database.engine.dispose()

    def test_factory_ignores_lark_webhook(self, monkeypatch, tmp_path):
        database_path = tmp_path / "factory_webhook.db"
        monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database_path}")
        monkeypatch.setenv("FEISHU_APP_ID", "cli_test_app")
        monkeypatch.setenv("FEISHU_APP_SECRET", "cli_test_secret")
        monkeypatch.setenv("FEISHU_CHAT_ID", "oc_testchat")
        main = import_fresh(
            "backend.app.main",
            "backend.app.main",
            "backend.app.config",
            "backend.app.database",
            "backend.app.dependencies",
            "backend.app.models",
            "backend.app.routers",
            "backend.models",
        )
        try:
            main.init_db()
            # 插入历史 lark_webhook 验证不被 factory 用作 Feishu 配置来源
            db = main.SessionLocal()
            from backend.app.models.app_setting import AppSetting
            db.add(AppSetting(key="lark_webhook", value="https://old-webhook.example.com", category="lark"))
            db.commit()
            db.close()

            push_service = main._push_service_factory()
            assert push_service.feishu is not None, "env 完整时应用 env 创建 FeishuClient"
            assert push_service.feishu.app_id == "cli_test_app"
        finally:
            database = sys.modules.get("backend.app.database")
            if database is not None:
                database.engine.dispose()


def test_fastapi_app_serves_health_and_docs(monkeypatch, tmp_path):
    database_path = tmp_path / "backend.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database_path}")
    main = import_fresh(
        "backend.app.main",
        "backend.app.main",
        "backend.app.config",
        "backend.app.database",
        "backend.app.dependencies",
        "backend.app.models",
        "backend.app.routers",
        "backend.models",
    )

    try:
        assert isinstance(main.app, FastAPI)

        with TestClient(main.app) as client:
            health_response = client.get("/health")
            docs_response = client.get("/docs")
            quotes_response = client.get("/quotes")
            quote_refresh_job = main.app.state.scheduler.get_job("quote_refresh")

        assert health_response.status_code == 200
        assert health_response.json() == {
            "status": "ok",
            "message": "A股自动盯盘AI助手运行中",
        }
        assert docs_response.status_code == 200
        assert "Swagger UI" in docs_response.text
        assert quotes_response.status_code == 200
        assert quotes_response.json() == []
        assert quote_refresh_job is not None
        assert (
            quote_refresh_job.trigger.interval.total_seconds()
            == main.settings.quote_refresh_interval_minutes * 60
        )
    finally:
        database = sys.modules.get("backend.app.database")
        if database is not None:
            database.engine.dispose()
