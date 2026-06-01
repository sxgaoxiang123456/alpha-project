from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import get_settings
from app.database import init_db
from app.routers.import_export import router as import_export_router
from app.routers.watchlist import router as watchlist_router

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

app.include_router(watchlist_router)
app.include_router(import_export_router)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {
        "status": "ok",
        "message": f"{settings.app_name}运行中",
    }
