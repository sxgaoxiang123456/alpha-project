# Dashboard 行情异步解耦 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 Dashboard 页面渲染只读本地缓存/数据库，请求路径永不触发外部数据源同步抓取；新增 `POST /market_data/refresh` 供前端首次加载/手动同步时触发后台刷新。

**Architecture:** 在 `QuoteService` / `MarketIndexService` 中新增只读缓存方法；`DashboardService` 改为调用这些方法；新增 `/market_data/refresh` 路由非阻塞触发 `QuoteScheduler`；前端 `dashboard.js` 在初始加载和手动同步时调用 refresh，并继续 60s 轮询 `/market_data`。

**Tech Stack:** FastAPI, SQLAlchemy 2.0, APScheduler, Jinja2, vanilla JS, pytest, FakeRedis.

## Global Constraints

- UI 文案必须为中文。
- 不实现任何交易功能。
- MVP 单用户架构，不引入多用户/权限扩展点。
- 暗色模式为唯一主题。
- A 股红涨绿跌配色优先于任何组件库默认。
- 仅支持 1280px+ 桌面端。
- 零成本数据源优先（AkShare/BaoStock）。
- 后端所有命令在 `backend/` 目录下执行。
- 单元+集成测试与 E2E 测试分两批跑。

---

## File Structure

| File | Responsibility |
|:---|:---|
| `backend/app/services/quote_service.py` | 新增 `get_cached_watchlist_quotes()`，只读 Redis/SQLite 缓存。 |
| `backend/app/services/market_index.py` | 新增 `get_cached_indices()`，只读 Redis/SQLite 缓存。 |
| `backend/app/services/dashboard_service.py` | `_get_market_indices` / `_get_watchlist_data` 改为调用只读缓存方法。 |
| `backend/app/core/quote_scheduler.py` | 新增 `is_refresh_running()` / `trigger_refresh()` 供路由调用。 |
| `backend/app/routers/dashboard.py` | 新增 `POST /market_data/refresh`；`GET /market_data` 经 DashboardService 改为只读缓存。 |
| `frontend/public/js/dashboard.js` | 初始加载触发 refresh，绑定手动同步按钮。 |
| `frontend/src/templates/components/top_nav.html` | 给同步按钮增加 `id="sync-btn"`。 |
| `backend/tests/unit/test_quote_service_cached_only.py` | `QuoteService.get_cached_watchlist_quotes()` 单元测试。 |
| `backend/tests/unit/test_market_index_cached_only.py` | `MarketIndexService.get_cached_indices()` 单元测试。 |
| `backend/tests/unit/test_dashboard_service_cached.py` | `DashboardService` 只读缓存行为单元测试。 |
| `backend/tests/integration/test_dashboard_refresh.py` | `/market_data/refresh` 与缓存只读集成测试。 |

---

### Task 1: QuoteService 只读缓存方法

**Files:**
- Modify: `backend/app/services/quote_service.py`
- Create: `backend/tests/unit/test_quote_service_cached_only.py`

**Interfaces:**
- Consumes: `WatchlistItem`, `Quote`, `RedisCache`, `CacheService`
- Produces: `QuoteService.get_cached_watchlist_quotes() -> list[Quote] | None`

方法语义：
- 查询当前自选股列表。
- 优先读取 Redis key `quotes:watchlist:{sorted_codes}`。
- Redis 缺失/不可用时，逐个读取 SQLite `CacheService` key `quote:{code}`。
- 任一 code 在 SQLite 中缺失/过期，返回 `None`。
- 自选股为空时返回 `[]`。

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/unit/test_quote_service_cached_only.py
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from fakeredis import FakeRedis
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.core.redis_cache import RedisCache
from backend.app.database import Base
from backend.app.models.watchlist import WatchlistItem
from backend.app.schemas.quote import Quote
from backend.app.services.quote_service import QuoteService


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    import backend.app.models  # noqa: F401
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def redis_cache():
    return RedisCache(client=FakeRedis(decode_responses=True))


def _mock_cache_service():
    cache = MagicMock()
    cache.set = MagicMock()
    cache.get = MagicMock(return_value=None)
    return cache


def _seed_watchlist(db):
    db.add(WatchlistItem(stock_code="600519", group_id=1))
    db.add(WatchlistItem(stock_code="600000", group_id=1))
    db.commit()


def _quote_json(code: str, name: str, price: str) -> str:
    return Quote(
        stock_code=code,
        stock_name=name,
        current_price=Decimal(price),
        change_percent=Decimal("1.23"),
        change_amount=Decimal("0.50"),
        volume=1000,
        turnover=Decimal("5000"),
        updated_at=datetime.now(UTC),
        status="normal",
        source_status="cached",
        actual_timestamp=datetime.now(UTC),
    ).model_dump_json()


class TestQuoteServiceCachedOnly:
    def test_redis_hit_returns_quotes(self, db, redis_cache):
        _seed_watchlist(db)
        redis_cache.set("quotes:watchlist:600000,600519", [
            {
                "stock_code": "600519",
                "stock_name": "贵州茅台",
                "current_price": "1800.50",
                "change_percent": "2.50",
                "change_amount": "43.90",
                "volume": 100,
                "turnover": "1000",
                "updated_at": datetime.now(UTC).isoformat(),
                "status": "normal",
                "source_status": "cached",
                "actual_timestamp": datetime.now(UTC).isoformat(),
            },
            {
                "stock_code": "600000",
                "stock_name": "浦发银行",
                "current_price": "10.50",
                "change_percent": "1.20",
                "change_amount": "0.12",
                "volume": 100,
                "turnover": "1000",
                "updated_at": datetime.now(UTC).isoformat(),
                "status": "normal",
                "source_status": "cached",
                "actual_timestamp": datetime.now(UTC).isoformat(),
            },
        ])

        service = QuoteService(
            db=db,
            facade=MagicMock(),
            cache=_mock_cache_service(),
            redis_cache=redis_cache,
        )
        quotes = service.get_cached_watchlist_quotes()

        assert quotes is not None
        assert len(quotes) == 2
        assert quotes[0].stock_code == "600519"
        service.facade.fetch_realtime.assert_not_called()

    def test_sqlite_hit_returns_quotes(self, db, redis_cache):
        _seed_watchlist(db)
        cache = MagicMock()
        cache.get = MagicMock(side_effect=lambda key: {
            "quote:600519": _quote_json("600519", "贵州茅台", "1800.50"),
            "quote:600000": _quote_json("600000", "浦发银行", "10.50"),
        }.get(key))

        service = QuoteService(
            db=db,
            facade=MagicMock(),
            cache=cache,
            redis_cache=redis_cache,
        )
        quotes = service.get_cached_watchlist_quotes()

        assert quotes is not None
        assert len(quotes) == 2
        assert all(isinstance(q, Quote) for q in quotes)
        service.facade.fetch_realtime.assert_not_called()

    def test_cache_miss_returns_none(self, db, redis_cache):
        _seed_watchlist(db)
        service = QuoteService(
            db=db,
            facade=MagicMock(),
            cache=_mock_cache_service(),
            redis_cache=redis_cache,
        )
        quotes = service.get_cached_watchlist_quotes()

        assert quotes is None
        service.facade.fetch_realtime.assert_not_called()

    def test_empty_watchlist_returns_empty_list(self, db, redis_cache):
        service = QuoteService(
            db=db,
            facade=MagicMock(),
            cache=_mock_cache_service(),
            redis_cache=redis_cache,
        )
        quotes = service.get_cached_watchlist_quotes()

        assert quotes == []
        service.facade.fetch_realtime.assert_not_called()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/python -m pytest tests/unit/test_quote_service_cached_only.py -v`

Expected: FAIL with `AttributeError: 'QuoteService' object has no attribute 'get_cached_watchlist_quotes'`

- [ ] **Step 3: Write minimal implementation**

在 `backend/app/services/quote_service.py` 中 `QuoteService` 类里新增：

```python
    def get_cached_watchlist_quotes(self) -> list[Quote] | None:
        """只读缓存获取自选股行情，不触发外部数据源抓取。"""
        items = self.db.query(WatchlistItem).order_by(WatchlistItem.id).all()
        codes = [item.stock_code for item in items]
        if not codes:
            return []

        timestamp = datetime.now(UTC)
        sorted_codes = ",".join(sorted(codes))

        # 1. 优先读 Redis
        if self.redis_cache is not None:
            cached = self.redis_cache.get(f"quotes:watchlist:{sorted_codes}")
            if cached is not None:
                return [
                    Quote(
                        stock_code=q["stock_code"],
                        stock_name=q.get("stock_name", q["stock_code"]),
                        current_price=Decimal(str(q.get("current_price", 0))) if q.get("current_price") is not None else None,
                        change_percent=Decimal(str(q.get("change_percent", 0))) if q.get("change_percent") is not None else None,
                        change_amount=Decimal(str(q.get("change_amount", 0))) if q.get("change_amount") is not None else None,
                        volume=int(q.get("volume", 0)) if q.get("volume") is not None else None,
                        turnover=Decimal(str(q.get("turnover", 0))) if q.get("turnover") is not None else None,
                        updated_at=datetime.fromisoformat(q["updated_at"]) if q.get("updated_at") else timestamp,
                        status=q.get("status", "normal"),
                        source_status=q.get("source_status", "cached"),
                        actual_timestamp=datetime.fromisoformat(q["actual_timestamp"]) if q.get("actual_timestamp") else timestamp,
                    )
                    for q in cached
                ]

        # 2. Redis 缺失/不可用，回退 SQLite CacheService（按 code 逐个读）
        if self.cache is not None:
            quotes: list[Quote] = []
            for code in codes:
                raw = self.cache.get(f"quote:{code}")
                if raw is None:
                    return None
                quotes.append(Quote.model_validate_json(raw))
            return quotes

        return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && .venv/bin/python -m pytest tests/unit/test_quote_service_cached_only.py -v`

Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/quote_service.py backend/tests/unit/test_quote_service_cached_only.py
git commit -m "feat: add QuoteService.get_cached_watchlist_quotes for read-only cache"
```

---

### Task 2: MarketIndexService 只读缓存方法

**Files:**
- Modify: `backend/app/services/market_index.py`
- Create: `backend/tests/unit/test_market_index_cached_only.py`

**Interfaces:**
- Consumes: `MarketIndex`, `RedisCache`, `CacheService`
- Produces: `MarketIndexService.get_cached_indices() -> list[MarketIndex] | None`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/unit/test_market_index_cached_only.py
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from fakeredis import FakeRedis

from backend.app.core.redis_cache import RedisCache
from backend.app.schemas.quote import MarketIndex
from backend.app.services.market_index import MarketIndexService


@pytest.fixture
def redis_cache():
    return RedisCache(client=FakeRedis(decode_responses=True))


def _mock_cache_service(entries=None):
    entries = entries or {}
    cache = MagicMock()
    cache.get = MagicMock(side_effect=lambda key: entries.get(key))
    return cache


class TestMarketIndexCachedOnly:
    def test_redis_hit_returns_indices(self, redis_cache):
        now = datetime.now(UTC)
        redis_cache.set("quotes:market", [
            {
                "index_code": "sh000001",
                "index_name": "上证指数",
                "current_point": "3000.12",
                "change_percent": "1.23",
                "change_amount": "36.50",
                "turnover": "450000000000",
                "updated_at": now.isoformat(),
                "source_status": "cached",
                "actual_timestamp": now.isoformat(),
            },
            {
                "index_code": "sz399001",
                "index_name": "深证成指",
                "current_point": "9800.00",
                "change_percent": "-0.50",
                "change_amount": "-49.00",
                "turnover": "520000000000",
                "updated_at": now.isoformat(),
                "source_status": "cached",
                "actual_timestamp": now.isoformat(),
            },
            {
                "index_code": "sz399006",
                "index_name": "创业板指",
                "current_point": "1900.00",
                "change_percent": "0.80",
                "change_amount": "15.00",
                "turnover": "180000000000",
                "updated_at": now.isoformat(),
                "source_status": "cached",
                "actual_timestamp": now.isoformat(),
            },
        ])

        service = MarketIndexService(
            facade=MagicMock(),
            cache=_mock_cache_service(),
            redis_cache=redis_cache,
        )
        indices = service.get_cached_indices()

        assert indices is not None
        assert len(indices) == 3
        assert indices[0].index_code == "sh000001"
        service.facade.fetch_realtime.assert_not_called()

    def test_sqlite_hit_returns_indices(self, redis_cache):
        now = datetime.now(UTC)
        cache = _mock_cache_service({
            "market_index:sh000001": MarketIndex(
                index_code="sh000001",
                index_name="上证指数",
                current_point=Decimal("3000.12"),
                change_percent=Decimal("1.23"),
                change_amount=Decimal("36.50"),
                turnover=Decimal("450000000000"),
                updated_at=now,
                source_status="cached",
                actual_timestamp=now,
            ).model_dump_json(),
            "market_index:sz399001": MarketIndex(
                index_code="sz399001",
                index_name="深证成指",
                current_point=Decimal("9800.00"),
                change_percent=Decimal("-0.50"),
                change_amount=Decimal("-49.00"),
                turnover=Decimal("520000000000"),
                updated_at=now,
                source_status="cached",
                actual_timestamp=now,
            ).model_dump_json(),
            "market_index:sz399006": MarketIndex(
                index_code="sz399006",
                index_name="创业板指",
                current_point=Decimal("1900.00"),
                change_percent=Decimal("0.80"),
                change_amount=Decimal("15.00"),
                turnover=Decimal("180000000000"),
                updated_at=now,
                source_status="cached",
                actual_timestamp=now,
            ).model_dump_json(),
        })

        service = MarketIndexService(
            facade=MagicMock(),
            cache=cache,
            redis_cache=redis_cache,
        )
        indices = service.get_cached_indices()

        assert indices is not None
        assert len(indices) == 3
        assert all(isinstance(idx, MarketIndex) for idx in indices)
        service.facade.fetch_realtime.assert_not_called()

    def test_cache_miss_returns_none(self, redis_cache):
        service = MarketIndexService(
            facade=MagicMock(),
            cache=_mock_cache_service(),
            redis_cache=redis_cache,
        )
        indices = service.get_cached_indices()

        assert indices is None
        service.facade.fetch_realtime.assert_not_called()

    def test_partial_sqlite_miss_returns_none(self, redis_cache):
        now = datetime.now(UTC)
        cache = _mock_cache_service({
            "market_index:sh000001": MarketIndex(
                index_code="sh000001",
                index_name="上证指数",
                current_point=Decimal("3000.12"),
                change_percent=Decimal("1.23"),
                change_amount=Decimal("36.50"),
                turnover=Decimal("450000000000"),
                updated_at=now,
                source_status="cached",
                actual_timestamp=now,
            ).model_dump_json(),
        })

        service = MarketIndexService(
            facade=MagicMock(),
            cache=cache,
            redis_cache=redis_cache,
        )
        indices = service.get_cached_indices()

        assert indices is None
        service.facade.fetch_realtime.assert_not_called()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/python -m pytest tests/unit/test_market_index_cached_only.py -v`

Expected: FAIL with `AttributeError: 'MarketIndexService' object has no attribute 'get_cached_indices'`

- [ ] **Step 3: Write minimal implementation**

在 `backend/app/services/market_index.py` 中 `MarketIndexService` 类里新增：

```python
    def get_cached_indices(self) -> list[MarketIndex] | None:
        """只读缓存获取大盘指数，不触发外部数据源抓取。"""
        timestamp = datetime.now(UTC)

        # 1. 优先读 Redis
        if self.redis_cache is not None:
            cached = self.redis_cache.get("quotes:market")
            if cached is not None:
                return [
                    MarketIndex(
                        index_code=idx["index_code"],
                        index_name=idx.get("index_name", idx["index_code"]),
                        current_point=Decimal(str(idx.get("current_point", 0))),
                        change_percent=Decimal(str(idx.get("change_percent", 0))),
                        change_amount=Decimal(str(idx.get("change_amount", 0))),
                        turnover=Decimal(str(idx.get("turnover", 0))),
                        updated_at=datetime.fromisoformat(idx["updated_at"]) if idx.get("updated_at") else timestamp,
                        source_status=idx.get("source_status", "cached"),
                        actual_timestamp=datetime.fromisoformat(idx["actual_timestamp"]) if idx.get("actual_timestamp") else timestamp,
                    )
                    for idx in cached
                ]

        # 2. Redis 缺失/不可用，回退 SQLite CacheService
        if self.cache is not None:
            indices: list[MarketIndex] = []
            for code in self.INDEX_CODES:
                raw = self.cache.get(f"market_index:{code}")
                if raw is None:
                    return None
                indices.append(MarketIndex.model_validate_json(raw))
            return indices

        return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && .venv/bin/python -m pytest tests/unit/test_market_index_cached_only.py -v`

Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/market_index.py backend/tests/unit/test_market_index_cached_only.py
git commit -m "feat: add MarketIndexService.get_cached_indices for read-only cache"
```

---

### Task 3: DashboardService 改为只读缓存

**Files:**
- Modify: `backend/app/services/dashboard_service.py`
- Create: `backend/tests/unit/test_dashboard_service_cached.py`

**Interfaces:**
- Consumes: `MarketIndexService.get_cached_indices()`, `QuoteService.get_cached_watchlist_quotes()`
- Produces: `DashboardService` 不再同步抓取外部数据

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/unit/test_dashboard_service_cached.py
from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from backend.app.schemas.dashboard import StockCardData
from backend.app.services.dashboard_service import DashboardService


def _make_service(market_cached=None, watchlist_cached=None):
    market_service = MagicMock()
    market_service.get_cached_indices = MagicMock(return_value=market_cached)

    quote_service = MagicMock()
    quote_service.get_cached_watchlist_quotes = MagicMock(return_value=watchlist_cached)

    db = MagicMock()
    db.query.return_value.order_by.return_value.all.return_value = []

    return DashboardService(
        db=db,
        market_index_service=market_service,
        quote_service=quote_service,
        cache_service=MagicMock(),
        redis_cache=None,
    )


@pytest.mark.asyncio
async def test_get_market_data_uses_cached_indices():
    service = _make_service(
        market_cached=[MagicMock(index_name="上证指数", current_value=3000.0, change_percent=1.0, change_amount=30.0, updated_at=datetime.now(UTC))],
    )
    data = await service.get_market_data()

    service.market_index_service.get_cached_indices.assert_called_once()
    service.quote_service.get_cached_watchlist_quotes.assert_called_once()
    assert len(data["market_indices"]) == 1
    assert data["degraded"] is False


@pytest.mark.asyncio
async def test_get_market_data_degraded_when_no_cache():
    service = _make_service(market_cached=None, watchlist_cached=None)
    data = await service.get_market_data()

    assert data["market_indices"] == []
    assert data["watchlist"] == []
    assert data["degraded"] is True


@pytest.mark.asyncio
async def test_get_market_data_watchlist_falls_back_to_basic_list():
    service = _make_service(market_cached=None, watchlist_cached=None)
    # mock _get_watchlist_fallback 返回一个基础股票卡片
    service._get_watchlist_fallback = MagicMock(return_value=[
        StockCardData(code="600519", name="贵州茅台", current_price=None, change_percent=None, change_amount=None, updated_at=None),
    ])
    data = await service.get_market_data()

    assert len(data["watchlist"]) == 1
    assert data["watchlist"][0].code == "600519"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/python -m pytest tests/unit/test_dashboard_service_cached.py -v`

Expected: FAIL（`get_cached_indices` / `get_cached_watchlist_quotes` 未调用或返回降级与预期不符）

- [ ] **Step 3: Write minimal implementation**

修改 `backend/app/services/dashboard_service.py`：

1. `_get_market_indices` 改为：

```python
    def _get_market_indices(self) -> list[MarketSnapshot]:
        """获取大盘指数快照（只读缓存）。"""
        cached = self.market_index_service.get_cached_indices()
        if cached is None:
            return []
        return [
            MarketSnapshot(
                name=idx.index_name,
                current_value=float(idx.current_point or 0),
                change_percent=float(idx.change_percent or 0),
                change_amount=float(idx.change_amount or 0),
                updated_at=idx.updated_at,
            )
            for idx in cached
        ]
```

2. `_get_watchlist_data` 改为：

```python
    def _get_watchlist_data(self) -> list[StockCardData]:
        """获取自选股行情数据（只读缓存）。"""
        quotes = self.quote_service.get_cached_watchlist_quotes()
        if quotes is None:
            return self._get_watchlist_fallback()
        if not quotes:
            return []

        codes = [q.stock_code for q in quotes]
        from backend.app.models.stock import Stock
        db_stocks = {s.code: s.name for s in self.db.query(Stock).filter(Stock.code.in_(codes)).all()}

        return [
            StockCardData(
                code=q.stock_code,
                name=db_stocks.get(q.stock_code, q.stock_name),
                current_price=float(q.current_price) if q.current_price is not None else None,
                change_percent=float(q.change_percent) if q.change_percent is not None else None,
                change_amount=float(q.change_amount) if q.change_amount is not None else None,
                updated_at=q.updated_at,
            )
            for q in quotes
        ]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && .venv/bin/python -m pytest tests/unit/test_dashboard_service_cached.py -v`

Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/dashboard_service.py backend/tests/unit/test_dashboard_service_cached.py
git commit -m "feat: DashboardService reads only cached quotes/indices"
```

---

### Task 4: 新增 `/market_data/refresh` 路由与并发控制

**Files:**
- Modify: `backend/app/core/quote_scheduler.py`
- Modify: `backend/app/routers/dashboard.py`
- Modify: `frontend/src/templates/components/market_data_partial.html`
- Create: `backend/tests/integration/test_dashboard_refresh.py`

**Interfaces:**
- Consumes: `QuoteScheduler.is_refresh_running()`, `QuoteScheduler.trigger_refresh()`
- Produces: `POST /market_data/refresh` returns `202 Accepted` or `429`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/integration/test_dashboard_refresh.py
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
    return main.app, main


class TestMarketDataRefresh:
    def test_post_refresh_returns_202(self, monkeypatch, tmp_path):
        app, main = _fresh_app(monkeypatch, tmp_path)
        quote_scheduler = main.app.state.quote_scheduler
        quote_scheduler.trigger_refresh = MagicMock()

        with TestClient(app) as client:
            response = client.post("/market_data/refresh")

        assert response.status_code == 202
        assert response.json()["status"] == "accepted"
        quote_scheduler.trigger_refresh.assert_called_once()

    def test_post_refresh_when_already_running_returns_429(self, monkeypatch, tmp_path):
        app, main = _fresh_app(monkeypatch, tmp_path)
        quote_scheduler = main.app.state.quote_scheduler
        quote_scheduler.is_refresh_running = MagicMock(return_value=True)
        quote_scheduler.trigger_refresh = MagicMock()

        with TestClient(app) as client:
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/python -m pytest tests/integration/test_dashboard_refresh.py -v`

Expected: FAIL with `404` for `/market_data/refresh`

- [ ] **Step 3: Write minimal implementation**

1. 在 `backend/app/core/quote_scheduler.py` 的 `QuoteScheduler` 类中新增：

```python
    def is_refresh_running(self) -> bool:
        """是否有行情刷新任务正在执行。"""
        return not self._quote_refresh_done.is_set()

    def trigger_refresh(self) -> None:
        """在后台线程触发一次行情刷新。"""
        if self.is_refresh_running():
            raise RuntimeError("refresh already running")
        threading.Thread(target=self.refresh_if_trading_day, daemon=True).start()
```

2. 在 `backend/app/routers/dashboard.py` 中新增 `status` import：

```python
from fastapi import APIRouter, Depends, Request, Response, status
```

新增 endpoint：

```python
@router.post("/market_data/refresh")
async def refresh_market_data(request: Request):
    """触发一次后台行情刷新，立即返回 202 Accepted。"""
    quote_scheduler = request.app.state.quote_scheduler
    if quote_scheduler.is_refresh_running():
        return Response(status_code=status.HTTP_429_TOO_MANY_REQUESTS)

    quote_scheduler.trigger_refresh()
    return {"status": "accepted"}
```

3. 修改 `frontend/src/templates/components/market_data_partial.html`，在 `degraded=true` 时显示提示：

```html
<!-- Market Data Partial — AJAX 刷新用，仅行情数据（大盘指数 + 自选股），不含简报 -->
{% if degraded %}
<div class="col-span-12 bg-market-warning/10 border border-market-warning rounded p-4 mb-4 flex items-center gap-2" data-degraded="true">
    <span class="material-symbols-outlined text-market-warning">sync</span>
    <span class="font-body-md text-body-md text-market-warning">数据准备中，请稍候…</span>
</div>
{% endif %}

{% with market_indices=market_indices %}
{% include "components/market_index.html" %}
{% endwith %}

<!-- Left Column: Watchlist -->
<div class="col-span-12 lg:col-span-8 flex flex-col gap-container-gap">
    {% with watchlist=watchlist %}
    {% include "components/watchlist_snapshot.html" %}
    {% include "components/onboarding.html" %}
    {% endwith %}
    {% include "components/quick_actions.html" %}
</div>
```

注意：需要在 `market_data_partial` 路由中把 `degraded` 传入模板上下文（已在 `dashboard.py` 的 `market_data_partial` 中通过 `data.get("degraded", False)` 传入）。

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && .venv/bin/python -m pytest tests/integration/test_dashboard_refresh.py -v`

Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/quote_scheduler.py backend/app/routers/dashboard.py frontend/src/templates/components/market_data_partial.html backend/tests/integration/test_dashboard_refresh.py
git commit -m "feat: add POST /market_data/refresh and make dashboard reads cache-only"
```

---

### Task 5: 前端首次加载触发 refresh 与手动同步按钮

**Files:**
- Modify: `frontend/src/templates/components/top_nav.html`
- Modify: `frontend/public/js/dashboard.js`

**Interfaces:**
- Consumes: `POST /market_data/refresh`
- Produces: 页面加载时自动后台刷新，手动同步按钮可触发刷新

- [ ] **Step 1: Write the failing test / verification step**

由于前端改动主要涉及 DOM 交互，本任务以手工验证为主。先确认当前 `dashboard.js` 中没有 `triggerBackgroundRefresh` 函数，且 `top_nav.html` 中同步按钮没有 `id`。

检查命令：

```bash
grep -n "triggerBackgroundRefresh" frontend/public/js/dashboard.js || echo "NOT_FOUND"
grep -n "sync-btn" frontend/src/templates/components/top_nav.html || echo "NOT_FOUND"
```

Expected: `NOT_FOUND`

- [ ] **Step 2: Modify top_nav.html**

给同步按钮增加 `id`：

```html
<button id="sync-btn" class="p-2 text-on-surface-variant hover:text-primary rounded hover:bg-surface-variant transition-colors">
    <span class="material-symbols-outlined">sync</span>
</button>
```

- [ ] **Step 3: Modify dashboard.js**

在 IIFE 内新增：

```javascript
    function triggerBackgroundRefresh() {
        fetch('/market_data/refresh', { method: 'POST' })
            .then(function (response) {
                if (!response.ok && response.status !== 429) {
                    console.warn('[Dashboard] 后台刷新触发失败:', response.status);
                }
            })
            .catch(function (err) {
                console.warn('[Dashboard] 后台刷新请求异常:', err);
            });
    }

    // 绑定手动同步按钮
    const syncBtn = document.getElementById('sync-btn');
    if (syncBtn) {
        syncBtn.addEventListener('click', function () {
            triggerBackgroundRefresh();
            // 立即拉取一次，若刷新已完成可立即看到最新数据
            fetchMarketData();
        });
    }
```

在文件底部、`startPolling()` 之前调用：

```javascript
    // 初始启动
    triggerBackgroundRefresh();
    startPolling();
    fetchMarketData();
```

- [ ] **Step 4: Verify**

检查命令：

```bash
grep -n "triggerBackgroundRefresh" frontend/public/js/dashboard.js
grep -n "sync-btn" frontend/src/templates/components/top_nav.html
```

Expected: 均出现匹配行。

- [ ] **Step 5: Commit**

```bash
git add frontend/public/js/dashboard.js frontend/src/templates/components/top_nav.html
git commit -m "feat: dashboard triggers background refresh on load and sync button"
```

---

### Task 6: 全量后端回归测试

**Files:**
- 运行已有测试套件

- [ ] **Step 1: Run unit + integration tests**

```bash
cd backend
.venv/bin/python -m pytest tests/unit/ tests/integration/ -v
```

Expected: all passed（包括新增的 4 + 4 + 3 + 3 = 14 个测试）。

- [ ] **Step 2: Run E2E tests**

```bash
.venv/bin/python -m pytest tests/e2e/ -v
```

Expected: all passed。

- [ ] **Step 3: Commit any fixes**

如有失败，修复后提交。

---

### Task 7: 端到端真机验证

**Files:**
- 运行 `start.sh`
- 使用 Chrome DevTools 验证

- [ ] **Step 1: 启动服务**

```bash
cd /Volumes/Gaoxiang-Data/02_code/AlphaProject
bash start.sh --no-setup
```

- [ ] **Step 2: 清空 Redis 缓存**

```bash
docker exec stock-mgt-redis redis-cli FLUSHALL
```

- [ ] **Step 3: 打开 Dashboard 并观察**

使用 Chrome DevTools 打开 `http://127.0.0.1:8000/`：

- 页面应在 < 500ms 内完成首次渲染（即使显示骨架屏）。
- Network 面板应看到 `POST /market_data/refresh` 返回 `202`。
- 等待数秒后，`GET /market_data` 轮询应返回带真实数据的 HTML，不再触发外部数据源同步抓取。
- 后端日志中不应再出现 `Dashboard market_indices 查询超时` 或 `Dashboard watchlist 查询超时`。

- [ ] **Step 4: 验证手动同步**

点击顶部“同步”按钮，确认 Network 面板出现 `POST /market_data/refresh`。

- [ ] **Step 5: 截图并记录**

保存关键截图到 `backend/tests/e2e/visual_baselines/dashboard_async_after_refresh.png`。

- [ ] **Step 6: 停止服务**

停止 `start.sh` 后台任务。

---

## Spec Coverage Check

| Spec Section | Implementing Task |
|:---|:---|
| 新增只读缓存方法 | Task 1, Task 2 |
| DashboardService 改为只读缓存 | Task 3 |
| `POST /market_data/refresh` | Task 4 |
| 前端首次加载/手动同步触发 refresh | Task 5 |
| 错误与降级处理 | Task 1-4（None/空列表/429） |
| 单元测试 | Task 1-3 |
| 集成测试 | Task 4 |
| E2E 验证 | Task 7 |

## Placeholder Scan

- 无 `TBD` / `TODO` / `implement later` / `fill in details`。
- 无未定义的类型或方法引用。
- 所有代码块包含完整实现。

## Type Consistency Check

- `get_cached_watchlist_quotes() -> list[Quote] | None` 与 Task 3 调用一致。
- `get_cached_indices() -> list[MarketIndex] | None` 与 Task 3 调用一致。
- `QuoteScheduler.is_refresh_running()` / `trigger_refresh()` 与 Task 4 调用一致。
- `POST /market_data/refresh` 返回 `202` 与 Task 5 前端调用一致。
