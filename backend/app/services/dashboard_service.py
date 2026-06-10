"""Dashboard 聚合服务 — 并行调用上游服务并统一响应。"""

import asyncio
import json
import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session, sessionmaker

from backend.app.config import get_settings
from backend.app.models.alert_trigger import AlertTrigger
from backend.app.models.push_channel import PushChannel
from backend.app.models.push_log import PushLog
from backend.app.schemas.dashboard import (
    AlertSummary,
    BriefingData,
    ChannelStatusItem,
    ChannelHealth,
    DashboardViewResponse,
    MarketSnapshot,
    PushHistoryItem,
    PushStatus,
    StockCardData,
)

logger = logging.getLogger(__name__)

_TIMEOUT_SECONDS = float(get_settings().data_source_timeout)


class DashboardService:
    """Dashboard 首页数据聚合服务。

    通过依赖注入接收各上游服务实例，便于测试时 mock。
    """

    DEFAULT_TIMEOUT_SECONDS = float(get_settings().data_source_timeout)

    def __init__(
        self,
        db: Session,
        market_index_service: Any,
        quote_service: Any,
        cache_service: Any,
        timeout_seconds: float | None = None,
        session_factory: Any | None = None,
        redis_cache: Any | None = None,
    ):
        self.db = db
        self.market_index_service = market_index_service
        self.quote_service = quote_service
        self.cache_service = cache_service
        self.timeout_seconds = timeout_seconds or self.DEFAULT_TIMEOUT_SECONDS
        self._session_factory = session_factory or sessionmaker(bind=db.get_bind())
        self.redis_cache = redis_cache

    async def build_dashboard_view(self) -> DashboardViewResponse:
        """聚合 Dashboard 首页全部数据。

        并行调用上游服务：大盘指数、自选股行情、简报缓存。
        数据库查询（预警、推送历史、通道状态）顺序执行（避免 session 并发问题）。
        单个服务超时降级，返回缓存数据或空值。
        """
        # 并行调用外部上游服务（可能涉及网络 I/O）
        external_results = await asyncio.gather(
            self._with_timeout(self._run_in_thread(self._get_market_indices), [], "market_indices"),
            self._with_timeout(self._run_in_thread(self._get_watchlist_data), self._get_watchlist_fallback(), "watchlist"),
            self._with_timeout(self._run_in_thread(self._get_briefing), None, "briefing"),
            return_exceptions=True,
        )

        market_indices, watchlist, briefing = external_results
        market_indices = market_indices if isinstance(market_indices, list) else []
        watchlist = watchlist if isinstance(watchlist, list) else []

        # 数据库查询并行执行（独立 session + asyncio.gather）
        db_results = await asyncio.gather(
            self._with_timeout(self._run_in_thread(self._get_today_alerts_parallel), [], "alerts"),
            self._with_timeout(self._run_in_thread(self._get_push_history_parallel), [], "push_history"),
            self._with_timeout(self._run_in_thread(self._get_channel_status_parallel), [], "channel_status"),
            return_exceptions=True,
        )
        alerts = db_results[0] if isinstance(db_results[0], list) else []
        push_history = db_results[1] if isinstance(db_results[1], list) else []
        channel_status = db_results[2] if isinstance(db_results[2], list) else []

        # 检测是否有数据源降级
        degraded = any(
            getattr(idx, "source_status", "") == "unavailable"
            for idx in market_indices
        ) or not market_indices

        return DashboardViewResponse(
            layout_mode="desktop",
            last_refresh=datetime.now(UTC),
            market_indices=market_indices,
            watchlist=watchlist,
            briefing=briefing,
            alerts=alerts,
            push_history=push_history,
            channel_status=channel_status,
            degraded=degraded,
            degradation_message="数据更新延迟，展示缓存数据" if degraded else None,
        )

    async def _with_timeout(
        self, coro: Any, fallback: Any, name: str
    ) -> Any:
        """包装协程，超时后返回 fallback 并记录日志。"""
        try:
            return await asyncio.wait_for(coro, timeout=self.timeout_seconds)
        except asyncio.TimeoutError:
            logger.warning("Dashboard %s 查询超时，返回降级数据", name)
            return fallback
        except Exception:
            logger.exception("Dashboard %s 查询异常，返回降级数据", name)
            return fallback

    def _run_in_thread(self, func: Any) -> Any:
        """在线程池中运行同步函数。"""
        import asyncio
        return asyncio.to_thread(func)

    def _get_market_indices(self) -> list[MarketSnapshot]:
        """获取大盘指数快照（优先读 Redis 缓存）。"""
        indices = self.market_index_service.get_indices(use_cache=True)
        return [
            MarketSnapshot(
                name=idx.index_name,
                current_value=float(idx.current_point or 0),
                change_percent=float(idx.change_percent or 0),
                change_amount=float(idx.change_amount or 0),
                updated_at=idx.updated_at,
            )
            for idx in indices
        ]

    def _get_watchlist_fallback(self) -> list[StockCardData]:
        """行情获取超时/失败时的降级数据：从数据库返回基础列表（无行情）。"""
        from backend.app.models.stock import Stock
        from backend.app.models.watchlist import WatchlistItem

        items = (
            self.db.query(WatchlistItem)
            .order_by(WatchlistItem.id)
            .all()
        )
        if not items:
            return []

        codes = [item.stock_code for item in items]
        db_stocks = {
            s.code: s.name
            for s in self.db.query(Stock).filter(Stock.code.in_(codes)).all()
        }

        return [
            StockCardData(
                code=item.stock_code,
                name=db_stocks.get(item.stock_code, item.stock_code),
                current_price=None,
                change_percent=None,
                change_amount=None,
                updated_at=None,
            )
            for item in items
        ]

    def _get_watchlist_data(self) -> list[StockCardData]:
        """获取自选股行情数据。

        行情获取失败时，clean_quote 会把 stock_name 回退为 stock_code；
        这里用数据库中的 stocks 表做名称兜底，确保列表始终展示正确名称。
        """
        quotes = self.quote_service.get_watchlist_quotes(use_cache=True)
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

    def _get_briefing(self) -> BriefingData | None:
        """获取最新 AI 简报（优先读 Redis，miss 时回退 SQLite cache）。"""
        # 优先读 Redis
        if self.redis_cache is not None:
            cached = self.redis_cache.get("latest_briefing")
            if cached is not None:
                insights = cached.get("insights", []) if isinstance(cached, dict) else []
                return BriefingData(
                    insights=insights if isinstance(insights, list) else [str(insights)],
                )

        raw = self.cache_service.get("latest_briefing")
        if not raw:
            return BriefingData(insights=[])
        try:
            data = json.loads(raw) if isinstance(raw, str) else raw
            insights = data.get("insights", [])
            # 写入 Redis 缓存
            if self.redis_cache is not None:
                self.redis_cache.set("latest_briefing", data, ttl_seconds=300)
            return BriefingData(
                insights=insights if isinstance(insights, list) else [str(insights)],
            )
        except Exception:
            logger.exception("简报解析失败")
            return BriefingData(insights=[])

    def _get_today_alerts(self) -> list[AlertSummary]:
        """获取今日预警汇总（基于 UTC 日期边界）。"""
        from datetime import date, timedelta

        today = datetime.now(UTC).date()
        start_of_day = datetime(today.year, today.month, today.day, tzinfo=UTC)
        triggers = (
            self.db.query(AlertTrigger)
            .filter(
                AlertTrigger.triggered_at >= start_of_day,
            )
            .order_by(AlertTrigger.triggered_at.desc())
            .limit(50)
            .all()
        )
        return [
            AlertSummary(
                stock_code=t.stock_code,
                stock_name=t.stock_code,  # MVP 阶段无反向查询，用 code 占位
                condition=f"{t.condition_type} {t.trigger_value}",
                level=t.level,
                triggered_at=t.triggered_at,
            )
            for t in triggers
        ]

    def _get_push_history(self, limit: int = 100) -> list[PushHistoryItem]:
        """获取最近推送历史。"""
        logs = (
            self.db.query(PushLog)
            .order_by(PushLog.created_at.desc())
            .limit(limit)
            .all()
        )
        return [
            PushHistoryItem(
                message_type=log.message_type,
                title=log.message_id,
                sent_at=log.created_at,
                channel=log.channel,
                status=PushStatus(log.status) if log.status in {"success", "failed", "pending"} else PushStatus.FAILED,
                failure_reason=log.error_reason,
            )
            for log in logs
        ]

    def _get_channel_status(self) -> list[ChannelStatusItem]:
        """获取推送通道健康状态。"""
        channels = self.db.query(PushChannel).all()
        return [
            ChannelStatusItem(
                name=c.name,
                status=ChannelHealth(c.status) if c.status in {"active", "degraded", "unavailable"} else ChannelHealth.UNAVAILABLE,
                rate_limited=c.rate_limited,
                last_updated=c.updated_at,
                message="限流中" if c.rate_limited else None,
            )
            for c in channels
        ]

    # ---- 并行查询方法（使用独立 session） ----

    def _get_today_alerts_parallel(self) -> list[AlertSummary]:
        """获取今日预警汇总（独立 session 版本，用于并行查询）。"""
        from datetime import date

        today = datetime.now(UTC).date()
        start_of_day = datetime(today.year, today.month, today.day, tzinfo=UTC)
        with self._session_factory() as session:
            triggers = (
                session.query(AlertTrigger)
                .filter(AlertTrigger.triggered_at >= start_of_day)
                .order_by(AlertTrigger.triggered_at.desc())
                .limit(50)
                .all()
            )
            return [
                AlertSummary(
                    stock_code=t.stock_code,
                    stock_name=t.stock_code,
                    condition=f"{t.condition_type} {t.trigger_value}",
                    level=t.level,
                    triggered_at=t.triggered_at,
                )
                for t in triggers
            ]

    def _get_push_history_parallel(self, limit: int = 100) -> list[PushHistoryItem]:
        """获取最近推送历史（独立 session 版本，用于并行查询）。"""
        with self._session_factory() as session:
            logs = (
                session.query(PushLog)
                .order_by(PushLog.created_at.desc())
                .limit(limit)
                .all()
            )
            return [
                PushHistoryItem(
                    message_type=log.message_type,
                    title=log.message_id,
                    sent_at=log.created_at,
                    channel=log.channel,
                    status=PushStatus(log.status) if log.status in {"success", "failed", "pending"} else PushStatus.FAILED,
                    failure_reason=log.error_reason,
                )
                for log in logs
            ]

    def _get_channel_status_parallel(self) -> list[ChannelStatusItem]:
        """获取推送通道健康状态（独立 session 版本，用于并行查询）。"""
        with self._session_factory() as session:
            channels = session.query(PushChannel).all()
            return [
                ChannelStatusItem(
                    name=c.name,
                    status=ChannelHealth(c.status) if c.status in {"active", "degraded", "unavailable"} else ChannelHealth.UNAVAILABLE,
                    rate_limited=c.rate_limited,
                    last_updated=c.updated_at,
                    message="限流中" if c.rate_limited else None,
                )
                for c in channels
            ]
