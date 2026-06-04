from contextlib import asynccontextmanager
from datetime import datetime, timedelta

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
from backend.app.core.quote_scheduler import QuoteScheduler, register_quote_refresh_job
from backend.app.database import SessionLocal, init_db
from backend.app.models.group import Group
from backend.app.models.historical_quote import HistoricalQuote
from backend.app.models.watchlist import WatchlistItem
from backend.app.routers.groups import router as groups_router
from backend.app.routers.import_export import router as import_export_router
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
    )
    register_quote_refresh_job(
        scheduler,
        quote_scheduler,
        interval_minutes=settings.quote_refresh_interval_minutes,
    )
    scheduler.start()
    app.state.scheduler = scheduler

    yield

    scheduler.shutdown()


app = FastAPI(
    title=settings.app_name,
    description="私有部署的 A 股盯盘助手，聚焦自选股管理、行情监控与预警推送。",
    version="0.1.0",
    lifespan=lifespan,
)

app.mount("/static", StaticFiles(directory="frontend/public"), name="static")
templates = Jinja2Templates(directory="frontend/src/templates")

app.include_router(watchlist_router)
app.include_router(import_export_router)
app.include_router(groups_router)
app.include_router(system_router)
app.include_router(quotes_router)


@app.get("/", response_class=HTMLResponse)
def dashboard_page(request: Request):
    return templates.TemplateResponse("watchlist/list.html", {"request": request, "items": [], "groups": []})


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
