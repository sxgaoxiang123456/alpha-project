import asyncio
import time
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.database import Base
from backend.app.schemas.dashboard import DashboardViewResponse
from backend.app.schemas.quote import MarketIndex, Quote
from backend.app.services.dashboard_service import DashboardService


def _make_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    return Session()


def _mock_market_service():
    s = MagicMock()
    s.get_indices = MagicMock(return_value=[
        MarketIndex(
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
        Quote(
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


class TestDashboardService:
    @pytest.mark.asyncio
    async def test_parallel_calls_aggregation(self):
        """验证并行调用 5 个上游服务，聚合结果完整。"""
        db = _make_db()
        market_svc = _mock_market_service()
        quote_svc = _mock_quote_service()
        cache_svc = _mock_cache_service()

        service = DashboardService(
            db=db,
            market_index_service=market_svc,
            quote_service=quote_svc,
            cache_service=cache_svc,
            timeout_seconds=0.1,
        )

        result = await service.build_dashboard_view()

        assert isinstance(result, DashboardViewResponse)
        assert len(result.market_indices) == 1
        assert result.market_indices[0].name == "上证指数"
        assert len(result.watchlist) == 1
        assert result.watchlist[0].code == "600000"
        assert result.briefing is not None
        assert len(result.briefing.insights) == 1

        # 验证并行调用发生
        market_svc.get_indices.assert_called_once()
        quote_svc.get_watchlist_quotes.assert_called_once()
        cache_svc.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_timeout_degradation(self):
        """验证单个服务超时后降级，不影响整体响应。"""
        db = _make_db()
        market_svc = _mock_market_service()

        # quote 服务模拟超时（线程中 sleep 超过 timeout）
        def slow_quote():
            time.sleep(0.5)
            return []

        quote_svc = MagicMock()
        quote_svc.get_watchlist_quotes = slow_quote

        cache_svc = _mock_cache_service()

        service = DashboardService(
            db=db,
            market_index_service=market_svc,
            quote_service=quote_svc,
            cache_service=cache_svc,
            timeout_seconds=0.1,
        )

        result = await service.build_dashboard_view()

        # 大盘数据正常返回
        assert len(result.market_indices) == 1
        # 自选股因超时空值降级
        assert result.watchlist == []
        # 整体响应仍成功
        assert isinstance(result, DashboardViewResponse)

    @pytest.mark.asyncio
    async def test_all_empty_data(self):
        """验证无自选股、无预警时的空数据聚合。"""
        db = _make_db()
        market_svc = MagicMock()
        market_svc.get_indices = MagicMock(return_value=[])
        quote_svc = MagicMock()
        quote_svc.get_watchlist_quotes = MagicMock(return_value=[])
        cache_svc = MagicMock()
        cache_svc.get = MagicMock(return_value=None)

        service = DashboardService(
            db=db,
            market_index_service=market_svc,
            quote_service=quote_svc,
            cache_service=cache_svc,
            timeout_seconds=0.1,
        )

        result = await service.build_dashboard_view()

        assert result.market_indices == []
        assert result.watchlist == []
        assert result.alerts == []
        assert result.push_history == []
        assert result.channel_status == []
