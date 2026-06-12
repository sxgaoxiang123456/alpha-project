"""dashboard_service 性能单元测试 — 并行查询耗时、ETag 计算正确性。"""

import time
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from backend.app.schemas.dashboard import MarketSnapshot, StockCardData
from backend.app.services.dashboard_service import DashboardService


def _make_db():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from backend.app.database import Base
    import backend.app.models  # noqa: F401
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def _mock_market_service():
    s = MagicMock()
    s.get_indices = MagicMock(return_value=[
        MagicMock(
            index_code="sh000001", index_name="上证指数",
            current_point=Decimal("3000.50"), change_percent=Decimal("1.23"),
            change_amount=Decimal("36.50"), turnover=Decimal("1234567890"),
            updated_at=datetime.now(UTC),
            source_status="primary", actual_timestamp=datetime.now(UTC),
        ),
    ])
    return s


def _mock_quote_service():
    s = MagicMock()
    s.get_watchlist_quotes = MagicMock(return_value=[
        MagicMock(
            stock_code="600000", stock_name="浦发银行",
            current_price=Decimal("10.50"), change_percent=Decimal("2.50"),
            change_amount=Decimal("0.25"), updated_at=datetime.now(UTC),
            status="normal", source_status="primary", actual_timestamp=datetime.now(UTC),
        ),
    ])
    return s


def _mock_cache_service():
    s = MagicMock()
    s.get = MagicMock(return_value='{"insights": ["大盘向好"]}')
    return s


class TestDashboardServiceParallel:
    """并行查询性能测试。"""

    @pytest.mark.asyncio
    async def test_parallel_db_queries_faster_than_sequential(self):
        """验证 3 个 DB 查询并行执行总耗时 < 150ms（每个 mock 耗时 50ms）。"""
        db = _make_db()
        market_svc = _mock_market_service()
        quote_svc = _mock_quote_service()
        cache_svc = _mock_cache_service()

        service = DashboardService(
            db=db,
            market_index_service=market_svc,
            quote_service=quote_svc,
            cache_service=cache_svc,
            timeout_seconds=1.0,
        )

        # mock 并行查询方法，每个 sleep 50ms
        with patch.object(service, '_get_today_alerts_parallel', side_effect=lambda: (__import__('time').sleep(0.05), [])[-1]), \
             patch.object(service, '_get_push_history_parallel', side_effect=lambda: (__import__('time').sleep(0.05), [])[-1]), \
             patch.object(service, '_get_channel_status_parallel', side_effect=lambda: (__import__('time').sleep(0.05), [])[-1]):

            start = time.perf_counter()
            result = await service.build_dashboard_view()
            elapsed = time.perf_counter() - start

        # 串行执行需要 > 150ms，并行应 < 150ms
        assert elapsed < 0.15, f"并行查询耗时 {elapsed:.3f}s，预期 < 0.15s"
        assert isinstance(result.alerts, list)
        assert isinstance(result.push_history, list)
        assert isinstance(result.channel_status, list)


class TestDashboardServiceETag:
    """ETag 相关测试。"""

    @pytest.mark.asyncio
    async def test_market_data_includes_market_indices_and_watchlist(self):
        """get_market_data 只返回行情相关数据。"""
        db = _make_db()
        market_svc = _mock_market_service()
        quote_svc = _mock_quote_service()
        cache_svc = _mock_cache_service()

        service = DashboardService(
            db=db,
            market_index_service=market_svc,
            quote_service=quote_svc,
            cache_service=cache_svc,
            timeout_seconds=1.0,
        )

        data = await service.get_market_data()

        assert "market_indices" in data
        assert "watchlist" in data
        assert "degraded" in data
        assert "alerts" not in data
        assert "push_history" not in data
        assert "channel_status" not in data
        assert "briefing" not in data
