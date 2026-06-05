"""Dashboard 聚合服务 — 并行调用上游服务并统一响应。"""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from backend.app.schemas.dashboard import DashboardViewResponse


class DashboardService:
    """Dashboard 首页数据聚合服务。

    通过依赖注入接收各上游服务实例，便于测试时 mock。
    """

    def __init__(
        self,
        db: Session,
        market_index_service: Any,
        quote_service: Any,
        cache_service: Any,
    ):
        self.db = db
        self.market_index_service = market_index_service
        self.quote_service = quote_service
        self.cache_service = cache_service

    async def build_dashboard_view(self) -> DashboardViewResponse:
        """聚合 Dashboard 首页全部数据。

        并行调用 5 个上游服务：大盘指数、自选股行情、预警状态、推送历史、通道状态。
        单个服务超时降级，返回缓存数据或空值。
        """
        raise NotImplementedError

    async def get_market_indices(self) -> list:
        """获取大盘指数快照。"""
        raise NotImplementedError

    async def get_watchlist_data(self) -> list:
        """获取自选股行情数据。"""
        raise NotImplementedError

    async def get_briefing(self) -> Any:
        """获取最新 AI 简报。"""
        raise NotImplementedError

    async def get_today_alerts(self) -> list:
        """获取今日预警汇总。"""
        raise NotImplementedError

    async def get_push_history(self, limit: int = 100) -> list:
        """获取最近推送历史。"""
        raise NotImplementedError

    async def get_channel_status(self) -> list:
        """获取推送通道健康状态。"""
        raise NotImplementedError
