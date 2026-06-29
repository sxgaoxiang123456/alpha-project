import importlib
import sys
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient


def _fresh_app(monkeypatch, tmp_path):
    database_path = tmp_path / "refresh.db"
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
    # Ensure quote_scheduler is set on app.state for tests that import fresh app
    if not hasattr(main.app.state, "quote_scheduler"):
        from backend.app.core.quote_scheduler import QuoteScheduler
        from backend.app.services.data_source_facade import DataSourceFacade
        from backend.app.services.cache_service import CacheService
        from backend.app.services.market_index import MarketIndexService
        from backend.app.services.quote_service import QuoteService
        from backend.app.database import SessionLocal
        from backend.app.core.trading_calendar import is_trading_day

        db = SessionLocal()
        facade = DataSourceFacade(db)
        cache = CacheService(db)
        qs = QuoteScheduler(
            quote_service=QuoteService(db=db, facade=facade, cache=cache),
            market_index_service=MarketIndexService(facade=facade, cache=cache),
            is_trading_day=is_trading_day,
        )
        main.app.state.quote_scheduler = qs
    return main.app, main


class TestMarketDataRefresh:
    def test_post_refresh_returns_202(self, monkeypatch, tmp_path):
        app, main = _fresh_app(monkeypatch, tmp_path)

        with TestClient(app) as client:
            quote_scheduler = app.state.quote_scheduler
            quote_scheduler.trigger_refresh = MagicMock()
            response = client.post("/market_data/refresh")

        assert response.status_code == 202
        assert response.json()["status"] == "accepted"
        quote_scheduler.trigger_refresh.assert_called_once()

    def test_post_refresh_when_already_running_returns_429(self, monkeypatch, tmp_path):
        app, main = _fresh_app(monkeypatch, tmp_path)

        with TestClient(app) as client:
            quote_scheduler = app.state.quote_scheduler
            quote_scheduler.is_refresh_running = MagicMock(return_value=True)
            quote_scheduler.trigger_refresh = MagicMock()
            response = client.post("/market_data/refresh")

        assert response.status_code == 429
        quote_scheduler.trigger_refresh.assert_not_called()

    def test_get_market_data_does_not_fetch_external(self, monkeypatch, tmp_path):
        app, main = _fresh_app(monkeypatch, tmp_path)

        with TestClient(app) as client:
            response = client.get("/market_data")

        assert response.status_code == 200
        # 无缓存时 partial 应包含降级提示
        assert "数据准备中" in response.text
        assert "自选股快照" in response.text
