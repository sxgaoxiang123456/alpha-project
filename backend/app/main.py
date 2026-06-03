from contextlib import asynccontextmanager

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import joinedload

from backend.app.config import get_settings
from backend.app.core.circuit_breaker import CircuitBreaker
from backend.app.core.health_checker import HealthChecker
from backend.app.database import SessionLocal, init_db
from backend.app.models.group import Group
from backend.app.models.watchlist import WatchlistItem
from backend.app.routers.groups import router as groups_router
from backend.app.routers.import_export import router as import_export_router
from backend.app.routers.system import router as system_router
from backend.app.routers.watchlist import router as watchlist_router
from backend.app.services.data_source import AkShareDataSource, BaoStockDataSource

settings = get_settings()


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
