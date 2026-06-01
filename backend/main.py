from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import joinedload

from backend.config import get_settings
from backend.database import SessionLocal, init_db
from backend.models.group import Group
from backend.models.watchlist import WatchlistItem
from backend.routers.groups import router as groups_router
from backend.routers.import_export import router as import_export_router
from backend.routers.watchlist import router as watchlist_router

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title=settings.app_name,
    description="私有部署的 A 股盯盘助手，聚焦自选股管理、行情监控与预警推送。",
    version="0.1.0",
    lifespan=lifespan,
)

app.mount("/static", StaticFiles(directory="frontend/static"), name="static")
templates = Jinja2Templates(directory="frontend/templates")

app.include_router(watchlist_router)
app.include_router(import_export_router)
app.include_router(groups_router)


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
