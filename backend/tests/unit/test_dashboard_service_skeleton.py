"""DashboardService 接口骨架测试 — 验证类可实例化、方法签名完整。"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.database import Base
from backend.app.services.dashboard_service import DashboardService


def _make_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    return Session()


class MockService:
    """上游服务 mock。"""
    pass


class TestDashboardServiceSkeleton:
    def test_instantiation(self):
        """验证 DashboardService 可被正确实例化。"""
        db = _make_db()
        service = DashboardService(
            db=db,
            market_index_service=MockService(),
            quote_service=MockService(),
            cache_service=MockService(),
        )
        assert service is not None
        assert service.db is db
        assert service.market_index_service is not None
        assert service.quote_service is not None
        assert service.cache_service is not None

    def test_methods_exist_and_raise_not_implemented(self):
        """验证所有聚合方法存在且当前抛出 NotImplementedError。"""
        db = _make_db()
        service = DashboardService(
            db=db,
            market_index_service=MockService(),
            quote_service=MockService(),
            cache_service=MockService(),
        )

        methods = [
            ("build_dashboard_view", []),
            ("get_market_indices", []),
            ("get_watchlist_data", []),
            ("get_briefing", []),
            ("get_today_alerts", []),
            ("get_push_history", []),
            ("get_channel_status", []),
        ]

        for method_name, args in methods:
            method = getattr(service, method_name, None)
            assert method is not None, f"方法 {method_name} 不存在"

            import asyncio
            if asyncio.iscoroutinefunction(method):
                with pytest.raises(NotImplementedError):
                    asyncio.run(method(*args))
            else:
                with pytest.raises(NotImplementedError):
                    method(*args)
