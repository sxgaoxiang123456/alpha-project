import importlib
import sys
from datetime import date, datetime, timedelta

import pytest


_BACKEND_MODULES_TO_CLEAR = [
    "backend.app.main",
    "backend.app.config",
    "backend.app.database",
    "backend.app.dependencies",
    "backend.app.models",
    "backend.app.models.historical_quote",
    "backend.app.routers",
    "backend.app.routers.quotes",
    "backend.app.services.cache_service",
    "backend.app.services.data_source_facade",
    "backend.app.services.market_index",
    "backend.app.services.quote_service",
    "backend.app.core.trading_calendar",
]


def _is_backend_module_to_clear(loaded_name):
    return any(
        loaded_name == name or loaded_name.startswith(f"{name}.")
        for name in _BACKEND_MODULES_TO_CLEAR
    )


@pytest.fixture(autouse=True)
def _restore_backend_modules():
    original_modules = {
        name: module
        for name, module in sys.modules.items()
        if _is_backend_module_to_clear(name)
    }
    yield

    database = sys.modules.get("backend.app.database")
    if database is not None:
        database.engine.dispose()

    for loaded_name in list(sys.modules):
        if _is_backend_module_to_clear(loaded_name):
            sys.modules.pop(loaded_name, None)
    sys.modules.update(original_modules)


def _fresh_main_for_cleanup(monkeypatch, tmp_path):
    """设置临时数据库后重新导入 main 模块，返回 cleanup 函数和 SessionLocal。"""
    database_path = tmp_path / "cleanup_test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database_path}")

    for loaded_name in list(sys.modules):
        if _is_backend_module_to_clear(loaded_name):
            sys.modules.pop(loaded_name, None)

    main = importlib.import_module("backend.app.main")
    main.init_db()
    return main


class TestCleanupOldHistoricalQuotes:
    def test_deletes_records_older_than_90_days(self, monkeypatch, tmp_path):
        main = _fresh_main_for_cleanup(monkeypatch, tmp_path)

        # 插入 100 天前的记录
        old_date = date.today() - timedelta(days=100)
        with main.SessionLocal() as session:
            from backend.app.models.historical_quote import HistoricalQuote
            session.add(HistoricalQuote(
                stock_code="600519", date=old_date,
                open=1500, close=1510, high=1520, low=1490,
                volume=10000, turnover=15000000,
            ))
            session.commit()

        result = main.cleanup_old_historical_quotes()
        assert result == 1

        with main.SessionLocal() as session:
            remaining = session.query(main.HistoricalQuote).count()
            assert remaining == 0

    def test_keeps_records_within_90_days(self, monkeypatch, tmp_path):
        main = _fresh_main_for_cleanup(monkeypatch, tmp_path)

        recent_date = date.today() - timedelta(days=30)
        with main.SessionLocal() as session:
            from backend.app.models.historical_quote import HistoricalQuote
            session.add(HistoricalQuote(
                stock_code="000001", date=recent_date,
                open=10, close=10.5, high=11, low=9.8,
                volume=50000, turnover=520000,
            ))
            session.commit()

        result = main.cleanup_old_historical_quotes()
        assert result == 0

        with main.SessionLocal() as session:
            remaining = session.query(main.HistoricalQuote).count()
            assert remaining == 1

    def test_mixed_old_and_recent_only_deletes_old(self, monkeypatch, tmp_path):
        main = _fresh_main_for_cleanup(monkeypatch, tmp_path)

        old_date = date.today() - timedelta(days=120)
        recent_date = date.today() - timedelta(days=10)
        with main.SessionLocal() as session:
            from backend.app.models.historical_quote import HistoricalQuote
            session.add_all([
                HistoricalQuote(
                    stock_code="600519", date=old_date,
                    open=1500, close=1510, high=1520, low=1490,
                    volume=10000, turnover=15000000,
                ),
                HistoricalQuote(
                    stock_code="000001", date=recent_date,
                    open=10, close=10.5, high=11, low=9.8,
                    volume=50000, turnover=520000,
                ),
            ])
            session.commit()

        result = main.cleanup_old_historical_quotes()
        assert result == 1

        with main.SessionLocal() as session:
            remaining = session.query(main.HistoricalQuote).all()
            assert len(remaining) == 1
            assert remaining[0].stock_code == "000001"

    def test_exactly_90_days_ago_is_kept(self, monkeypatch, tmp_path):
        """恰好 90 天前的记录应保留（< 非 <=）。"""
        main = _fresh_main_for_cleanup(monkeypatch, tmp_path)

        boundary_date = date.today() - timedelta(days=90)
        with main.SessionLocal() as session:
            from backend.app.models.historical_quote import HistoricalQuote
            session.add(HistoricalQuote(
                stock_code="600519", date=boundary_date,
                open=1500, close=1510, high=1520, low=1490,
                volume=10000, turnover=15000000,
            ))
            session.commit()

        result = main.cleanup_old_historical_quotes()
        assert result == 0

        with main.SessionLocal() as session:
            remaining = session.query(main.HistoricalQuote).count()
            assert remaining == 1

    def test_respects_custom_retention_days(self, monkeypatch, tmp_path):
        main = _fresh_main_for_cleanup(monkeypatch, tmp_path)

        old_date = date.today() - timedelta(days=40)
        with main.SessionLocal() as session:
            from backend.app.models.historical_quote import HistoricalQuote
            session.add(HistoricalQuote(
                stock_code="600519", date=old_date,
                open=1500, close=1510, high=1520, low=1490,
                volume=10000, turnover=15000000,
            ))
            session.commit()

        result = main.cleanup_old_historical_quotes(retention_days=30)
        assert result == 1

        with main.SessionLocal() as session:
            remaining = session.query(main.HistoricalQuote).count()
            assert remaining == 0

    def test_empty_table_returns_zero(self, monkeypatch, tmp_path):
        main = _fresh_main_for_cleanup(monkeypatch, tmp_path)
        result = main.cleanup_old_historical_quotes()
        assert result == 0
