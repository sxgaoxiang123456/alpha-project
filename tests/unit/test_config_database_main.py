import importlib
import sys

from fastapi import FastAPI
from fastapi.testclient import TestClient


def import_fresh(module_name: str, *module_names_to_clear: str):
    for name in module_names_to_clear:
        sys.modules.pop(name, None)
    return importlib.import_module(module_name)


def test_settings_reads_database_url_from_environment(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./data/test-watchlist.db")
    config = import_fresh("app.config", "app.config")

    settings = config.Settings(_env_file=None)

    assert settings.database_url == "sqlite:///./data/test-watchlist.db"


def test_settings_uses_sqlite_default_when_database_url_missing(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    config = import_fresh("app.config", "app.config")

    settings = config.Settings(_env_file=None)

    assert settings.database_url == "sqlite:///./data/watchlist.db"


def test_database_exposes_engine_session_base_and_init_db(monkeypatch, tmp_path):
    database_path = tmp_path / "watchlist.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database_path}")
    database = import_fresh("app.database", "app.config", "app.database")

    assert database.engine is not None
    assert database.SessionLocal is not None
    assert database.Base is not None
    assert callable(database.init_db)

    database.init_db()

    assert database_path.exists()
    database.engine.dispose()


def test_fastapi_app_serves_health_and_docs(monkeypatch, tmp_path):
    database_path = tmp_path / "app.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database_path}")
    main = import_fresh("app.main", "app.config", "app.database", "app.main")

    assert isinstance(main.app, FastAPI)

    with TestClient(main.app) as client:
        health_response = client.get("/health")
        docs_response = client.get("/docs")

    assert health_response.status_code == 200
    assert health_response.json() == {
        "status": "ok",
        "message": "A股自动盯盘AI助手运行中",
    }
    assert docs_response.status_code == 200
    assert "Swagger UI" in docs_response.text
