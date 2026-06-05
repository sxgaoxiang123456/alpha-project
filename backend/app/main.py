from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import delete
from sqlalchemy.orm import joinedload

from backend.app.config import get_settings
from backend.app.core.circuit_breaker import CircuitBreaker
from backend.app.core.health_checker import HealthChecker
from backend.app.core.quote_scheduler import (
    QuoteScheduler,
    register_briefing_job,
    register_quote_refresh_job,
)
from backend.app.database import SessionLocal, init_db
from backend.app.models.group import Group
from backend.app.models.historical_quote import HistoricalQuote
from backend.app.models.watchlist import WatchlistItem
from backend.app.routers.dashboard import router as dashboard_router
from backend.app.routers.groups import router as groups_router
from backend.app.routers.settings import router as settings_router
from backend.app.routers.import_export import router as import_export_router
from backend.app.routers.alerts import router as alerts_router
from backend.app.routers.push import router as push_router
from backend.app.routers.quotes import router as quotes_router
from backend.app.routers.system import router as system_router
from backend.app.routers.watchlist import router as watchlist_router
from backend.app.services.cache_service import CacheService
from backend.app.services.data_source import AkShareDataSource, BaoStockDataSource
from backend.app.services.data_source_facade import DataSourceFacade
from backend.app.services.market_index import MarketIndexService
from backend.app.services.quote_service import QuoteService

settings = get_settings()


from backend.app.core.trading_calendar import is_trading_day


def cleanup_old_historical_quotes(retention_days: int = 90) -> int:
    cutoff = datetime.now() - timedelta(days=retention_days)
    with SessionLocal() as session:
        result = session.execute(
            delete(HistoricalQuote).where(HistoricalQuote.date < cutoff.date())
        )
        session.commit()
        return result.rowcount


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()

    # 启动 APScheduler 健康检查任务
    scheduler = BackgroundScheduler()
    db = SessionLocal()
    cb = CircuitBreaker(db)
    checker = HealthChecker(
        circuit_breaker=cb,
        primary=AkShareDataSource(),
        fallback=BaoStockDataSource(),
    )
    scheduler.add_job(
        checker.check_all,
        "interval",
        minutes=settings.health_check_interval_minutes,
        id="health_check",
        replace_existing=True,
    )
    scheduler.add_job(
        lambda: CacheService(db).cleanup_expired(),
        "interval",
        hours=1,
        id="cache_cleanup",
        replace_existing=True,
    )
    scheduler.add_job(
        cleanup_old_historical_quotes,
        "cron",
        hour=3,
        minute=7,
        id="historical_cleanup",
        replace_existing=True,
    )
    facade = DataSourceFacade(db)
    quote_cache = CacheService(db)

    def _run_alert_detection() -> None:
        """行情刷新后执行预警检测。

        数据源中断保护 (FR-013): 若所有行情数据 source_status 均为
        "unavailable"，或缓存中无任何行情数据，则跳过本轮检测，避免基于
        过期数据误报。
        """
        import json
        import logging
        _logger = logging.getLogger("alert_detection")
        alert_db = SessionLocal()
        try:
            from backend.app.models.watchlist import WatchlistItem
            from backend.app.services.alert_service import detect_alerts

            stock_codes = [
                row[0] for row in alert_db.query(WatchlistItem.stock_code).all()
            ]
            quotes_dict = {}
            for code in stock_codes:
                raw = quote_cache.get(f"quote:{code}")
                if raw:
                    quotes_dict[code] = json.loads(raw)

            # FR-013: 数据源全中断时跳过检测，不基于过期数据误报
            if not quotes_dict:
                _logger.debug("无行情缓存数据，跳过预警检测")
                return

            statuses = {
                q.get("source_status", "")
                for q in quotes_dict.values()
            }
            if statuses == {"unavailable"}:
                _logger.warning("全部数据源不可用，跳过预警检测")
                return

            # A-007: 跨交易日冷却期自动重置
            from datetime import date
            from backend.app.services.alert_service import reset_all_cooldowns

            today = date.today()
            last_date = getattr(app.state, "_last_alert_detection_date", None)
            if last_date is not None and last_date != today:
                reset_all_cooldowns(alert_db)
                alert_db.commit()
                _logger.info("交易日变更 %s → %s，已重置冷却期", last_date, today)
            app.state._last_alert_detection_date = today

            triggers = detect_alerts(alert_db, quotes_dict)
            if triggers:
                alert_db.add_all(triggers)
                alert_db.commit()
                _logger.info("预警检测完成，触发 %d 条规则", len(triggers))

                # 链路贯通：将 AlertTrigger 提交给 PushService（F4→F5）
                push_service = _push_service_factory()
                from backend.app.schemas.push import PushMessageRequest

                for trigger in triggers:
                    try:
                        quote = quotes_dict.get(trigger.stock_code, {})
                        message = PushMessageRequest(
                            message_type="alert",
                            priority="high" if trigger.level == "alert" else "normal",
                            content={
                                "stock_code": trigger.stock_code,
                                "condition": f"{trigger.condition_type} {trigger.trigger_value}",
                                "level": trigger.level,
                                "price": quote.get("current_price", ""),
                                "change_pct": quote.get("change_percent", ""),
                                "triggered_at": trigger.triggered_at.isoformat() if trigger.triggered_at else "",
                            },
                        )
                        push_service.send(message)
                    except Exception:
                        _logger.exception("推送预警失败: %s", trigger.stock_code)
        except Exception:
            _logger.exception("预警检测异常")
        finally:
            alert_db.close()

    _push_db_sessions = []

    def _push_service_factory():
        from backend.app.services.push_service import PushService

        push_db = SessionLocal()
        _push_db_sessions.append(push_db)
        return PushService(db=push_db, feishu_client=None, telegram_client=None)

    quote_scheduler = QuoteScheduler(
        quote_service=QuoteService(
            db=db,
            facade=facade,
            cache=quote_cache,
            ttl_seconds=settings.quote_cache_ttl_seconds,
        ),
        market_index_service=MarketIndexService(
            facade=facade,
            cache=quote_cache,
            ttl_seconds=settings.quote_cache_ttl_seconds,
        ),
        is_trading_day=is_trading_day,
        on_quotes_refreshed=_run_alert_detection,
        push_service_factory=_push_service_factory,
    )
    register_quote_refresh_job(
        scheduler,
        quote_scheduler,
        interval_minutes=settings.quote_refresh_interval_minutes,
    )
    register_briefing_job(scheduler, quote_scheduler)
    scheduler.start()
    app.state.scheduler = scheduler

    yield

    scheduler.shutdown()
    for push_db in _push_db_sessions:
        if push_db.is_active:
            push_db.close()


app = FastAPI(
    title=settings.app_name,
    description="私有部署的 A 股盯盘助手，聚焦自选股管理、行情监控与预警推送。",
    version="0.1.0",
    lifespan=lifespan,
)

_PROJECT_ROOT = Path(__file__).parent.parent.parent
_FRONTEND_DIR = _PROJECT_ROOT / "frontend"

app.mount("/static", StaticFiles(directory=str(_FRONTEND_DIR / "public")), name="static")
templates = Jinja2Templates(directory=str(_FRONTEND_DIR / "src" / "templates"))

app.include_router(dashboard_router)
app.include_router(settings_router)
app.include_router(alerts_router)
app.include_router(watchlist_router)
app.include_router(import_export_router)
app.include_router(groups_router)
app.include_router(system_router)
app.include_router(quotes_router)
app.include_router(push_router)


@app.get("/watchlist-page", response_class=HTMLResponse)
def watchlist_page(request: Request):
    with SessionLocal() as db:
        items = (
            db.query(WatchlistItem)
            .options(joinedload(WatchlistItem.stock), joinedload(WatchlistItem.group))
            .all()
        )
        groups = db.query(Group).order_by(Group.is_default.desc(), Group.created_at.asc()).all()
        group_counts = {}
        for g in groups:
            group_counts[g.id] = db.query(WatchlistItem).filter_by(group_id=g.id).count()
    return templates.TemplateResponse(
        "watchlist/list.html",
        {
            "request": request,
            "items": items,
            "groups": groups,
            "group_counts": group_counts,
        },
    )


@app.get("/health")
def health_check() -> dict[str, str]:
    return {
        "status": "ok",
        "message": f"{settings.app_name}运行中",
    }
