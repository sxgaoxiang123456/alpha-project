import importlib
import sys
from time import perf_counter

from fastapi.testclient import TestClient


def _fresh_main(monkeypatch, tmp_path):
    database_path = tmp_path / "quotes.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database_path}")

    modules_to_clear = [
        "backend.app.main",
        "backend.app.config",
        "backend.app.database",
        "backend.app.dependencies",
        "backend.app.models",
        "backend.models",
        "backend.app.routers",
        "backend.app.services.cache_service",
        "backend.app.services.data_source_facade",
        "backend.app.services.market_index",
        "backend.app.services.quote_service",
    ]
    for name in modules_to_clear:
        for loaded_name in list(sys.modules):
            if loaded_name == name or loaded_name.startswith(f"{name}."):
                sys.modules.pop(loaded_name, None)

    return importlib.import_module("backend.app.main")


def _dispose_database():
    database = sys.modules.get("backend.app.database")
    if database is not None:
        database.engine.dispose()


def _seed_watchlist(main, stock_code="600519"):
    from backend.app.models.stock import Stock
    from backend.app.models.watchlist import WatchlistItem

    with main.SessionLocal() as session:
        session.add(Stock(code=stock_code, name="贵州茅台", market="沪", sector="白酒"))
        session.add(WatchlistItem(stock_code=stock_code, group_id=1))
        session.commit()


def _patch_facade(monkeypatch, payload):
    from backend.app.schemas.data_fetch import DataFetchResult
    from backend.app.services.data_source_facade import DataSourceFacade

    calls = []

    def fake_fetch_realtime(self, codes):
        calls.append(list(codes))
        data = payload(codes) if callable(payload) else payload
        return DataFetchResult(
            status="primary",
            data=data,
            source="akshare",
            response_time_ms=1.0,
        )

    monkeypatch.setattr(DataSourceFacade, "fetch_realtime", fake_fetch_realtime)
    return calls


def _quote_payload(codes):
    return {
        code: {
            "name": "贵州茅台",
            "price": 1500.5,
            "change_pct": 1.25,
            "change_amount": 18.5,
            "volume": 100000,
            "amount": 150050000.0,
        }
        for code in codes
    }


def _market_payload(codes):
    names = {
        "sh000001": "上证指数",
        "sz399001": "深证成指",
        "sz399006": "创业板指",
    }
    return {
        code: {
            "name": names[code],
            "price": 3123.45,
            "change_pct": 0.85,
            "change_amount": 26.1,
            "amount": 450000000000.0,
        }
        for code in codes
    }


def test_get_quotes_fetches_on_cache_miss_then_uses_real_cache(monkeypatch, tmp_path):
    main = _fresh_main(monkeypatch, tmp_path)
    calls = _patch_facade(monkeypatch, _quote_payload)

    try:
        with TestClient(main.app) as client:
            _seed_watchlist(main)

            started_at = perf_counter()
            miss_response = client.get("/quotes")
            miss_elapsed = perf_counter() - started_at
            hit_response = client.get("/quotes")

        assert miss_response.status_code == 200
        assert hit_response.status_code == 200
        assert miss_elapsed < 3

        miss_data = miss_response.json()
        hit_data = hit_response.json()
        assert len(miss_data) == 1
        assert miss_data == hit_data
        assert miss_data[0]["stock_code"] == "600519"
        assert miss_data[0]["stock_name"] == "贵州茅台"
        assert miss_data[0]["source_status"] == "primary"
        assert miss_data[0]["status"] == "normal"
        assert calls == [["600519"]]
    finally:
        _dispose_database()


def test_get_quotes_market_returns_three_market_indices_from_real_cache(monkeypatch, tmp_path):
    main = _fresh_main(monkeypatch, tmp_path)
    calls = _patch_facade(monkeypatch, _market_payload)

    try:
        with TestClient(main.app) as client:
            miss_response = client.get("/quotes/market")
            hit_response = client.get("/quotes/market")

        assert miss_response.status_code == 200
        assert hit_response.status_code == 200
        miss_data = miss_response.json()
        hit_data = hit_response.json()
        assert [item["index_code"] for item in miss_data] == [
            "sh000001",
            "sz399001",
            "sz399006",
        ]
        assert [item["index_name"] for item in miss_data] == [
            "上证指数",
            "深证成指",
            "创业板指",
        ]
        assert all(item["source_status"] == "primary" for item in miss_data)
        assert miss_data == hit_data
        assert calls == [["sh000001", "sz399001", "sz399006"]]
    finally:
        _dispose_database()
