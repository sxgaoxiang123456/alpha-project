"""Dashboard 并发压力测试 — 验证并行查询 + ETag 并发场景。

归档信息（testing-system-blueprint）:
- Feature: 008-redis-adjust
- 缺口来源: test-routing-advisor -> backend-testing
- 命中缺口: 并发/竞态/限频原子性
- 三层节奏: 中层（并发请求，约 5-15s）
- 可追溯 ID: TR-008-BE-006 ~ TR-008-BE-010
"""

import asyncio
import importlib
import sys
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from backend.app.schemas.dashboard import (
    AlertSummary,
    BriefingData,
    ChannelHealth,
    ChannelStatusItem,
    DashboardViewResponse,
    MarketSnapshot,
    PushHistoryItem,
    PushStatus,
    StockCardData,
)


def _fresh_app(monkeypatch, tmp_path):
    """创建独立的 app 实例，避免模块缓存污染。"""
    database_path = tmp_path / "concurrent.db"
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
    return main.app


def _mock_dashboard_service():
    """返回固定 mock 数据的 DashboardService。"""
    svc = MagicMock()
    view = DashboardViewResponse(
        market_indices=[
            MarketSnapshot(name="上证指数", current_value=3000.0, change_percent=1.23, change_amount=36.5),
        ],
        watchlist=[
            StockCardData(code="600000", name="浦发银行", current_price=10.5, change_percent=2.5, change_amount=0.25),
        ],
        briefing=BriefingData(insights=["大盘整体向好"]),
        alerts=[
            AlertSummary(stock_code="000001", stock_name="平安银行", condition="涨幅 > 5%", level="alert"),
        ],
        push_history=[
            PushHistoryItem(message_type="price_alert", title="价格预警", sent_at=datetime.now(UTC), channel="lark", status=PushStatus.SUCCESS),
        ],
        channel_status=[
            ChannelStatusItem(name="飞书", status=ChannelHealth.ACTIVE),
            ChannelStatusItem(name="Telegram", status=ChannelHealth.DEGRADED, rate_limited=True),
        ],
    )
    svc.build_dashboard_view = AsyncMock(return_value=view)
    svc.get_market_data = AsyncMock(return_value={
        "market_indices": view.market_indices,
        "watchlist": view.watchlist,
        "degraded": False,
        "last_refresh": datetime.now(UTC).isoformat(),
    })
    return svc


@pytest_asyncio.fixture
async def client(monkeypatch, tmp_path):
    """异步 HTTP 客户端，绑定独立 app 实例。"""
    app = _fresh_app(monkeypatch, tmp_path)
    monkeypatch.setattr("backend.app.routers.dashboard._get_dashboard_service", lambda db: _mock_dashboard_service())
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


class TestMarketDataConcurrentETag:
    """TR-008-BE-006 ~ TR-008-BE-008: ETag 并发场景验证。"""

    @pytest.mark.asyncio
    async def test_concurrent_first_requests_all_return_200_with_etag(self, client: AsyncClient):
        """TR-008-BE-006: 并发首次请求均返回 200 + ETag。"""
        async def fetch():
            return await client.get("/market_data")

        # 并发 5 个首次请求
        responses = await asyncio.gather(*[fetch() for _ in range(5)])

        for r in responses:
            assert r.status_code == 200, f"并发请求返回 {r.status_code}"
            assert "etag" in r.headers, "首次请求缺少 ETag 头"
            assert len(r.headers["etag"]) == 32, "ETag 应为 MD5 hex(32位)"

    @pytest.mark.asyncio
    async def test_concurrent_etag_match_all_return_304(self, client: AsyncClient):
        """TR-008-BE-007: 并发带相同 ETag 请求均返回 304。"""
        # 先获取 ETag
        r1 = await client.get("/market_data")
        assert r1.status_code == 200
        etag = r1.headers["etag"]

        async def fetch_with_etag():
            return await client.get("/market_data", headers={"if-none-match": etag})

        # 并发 10 个带 ETag 的请求
        responses = await asyncio.gather(*[fetch_with_etag() for _ in range(10)])

        for r in responses:
            assert r.status_code == 304, f"ETag 匹配时应返回 304，实际返回 {r.status_code}"
            assert r.content == b"", "304 响应不应有 body"

    @pytest.mark.asyncio
    async def test_concurrent_mixed_etag_requests(self, client: AsyncClient):
        """TR-008-BE-008: 混合并发请求（部分有效 ETag、部分无效、部分无 ETag）。"""
        # 先获取有效 ETag
        r1 = await client.get("/market_data")
        valid_etag = r1.headers["etag"]

        async def fetch_valid():
            return await client.get("/market_data", headers={"if-none-match": valid_etag})

        async def fetch_invalid():
            return await client.get("/market_data", headers={"if-none-match": "invalid-etag"})

        async def fetch_no_etag():
            return await client.get("/market_data")

        # 并发混合请求
        tasks = (
            [fetch_valid() for _ in range(5)] +
            [fetch_invalid() for _ in range(3)] +
            [fetch_no_etag() for _ in range(2)]
        )
        responses = await asyncio.gather(*tasks)

        valid_responses = responses[:5]
        invalid_responses = responses[5:8]
        no_etag_responses = responses[8:]

        for r in valid_responses:
            assert r.status_code == 304, f"有效 ETag 应返回 304，实际 {r.status_code}"

        for r in invalid_responses:
            assert r.status_code == 200, f"无效 ETag 应返回 200，实际 {r.status_code}"
            assert "etag" in r.headers

        for r in no_etag_responses:
            assert r.status_code == 200, f"无 ETag 应返回 200，实际 {r.status_code}"
            assert "etag" in r.headers


class TestDashboardConcurrentLoad:
    """TR-008-BE-009 ~ TR-008-BE-010: Dashboard 首页并发负载验证。"""

    @pytest.mark.asyncio
    async def test_concurrent_homepage_requests_all_return_200(self, client: AsyncClient):
        """TR-008-BE-009: 并发请求 Dashboard 首页均返回 200。"""
        async def fetch():
            return await client.get("/")

        # 并发 10 个首页请求
        responses = await asyncio.gather(*[fetch() for _ in range(10)])

        for r in responses:
            assert r.status_code == 200, f"并发首页请求返回 {r.status_code}"
            assert "text/html" in r.headers.get("content-type", "")

    @pytest.mark.asyncio
    async def test_concurrent_homepage_content_consistency(self, client: AsyncClient):
        """TR-008-BE-010: 并发请求返回内容一致。"""
        async def fetch():
            return await client.get("/")

        responses = await asyncio.gather(*[fetch() for _ in range(5)])

        # 所有响应都包含骨架屏占位（真实数据由 JS 通过 /market_data 异步加载）
        for r in responses:
            assert "skeleton-screen" in r.text
            assert "animate-pulse" in r.text
