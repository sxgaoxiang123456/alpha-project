"""Dashboard 路由 — 首页渲染与行情 Partial HTML。"""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from backend.app.core.redis_cache import RedisCache
from backend.app.dependencies import get_db
from backend.app.services.dashboard_service import DashboardService
from backend.app.services.market_index import MarketIndexService
from backend.app.services.quote_service import QuoteService
from backend.app.services.cache_service import CacheService
from backend.app.database import SessionLocal

router = APIRouter(tags=["dashboard"])


def _get_dashboard_service(db: Session) -> DashboardService:
    """构造 DashboardService，注入上游依赖。"""
    from backend.app.main import _redis_client

    facade_module = __import__("backend.app.services.data_source_facade", fromlist=["DataSourceFacade"])
    facade = facade_module.DataSourceFacade(db)
    cache = CacheService(db)
    redis_cache = RedisCache(client=_redis_client)
    return DashboardService(
        db=db,
        market_index_service=MarketIndexService(facade=facade, cache=cache, redis_cache=redis_cache),
        quote_service=QuoteService(db=db, facade=facade, cache=cache, redis_cache=redis_cache),
        cache_service=cache,
        redis_cache=redis_cache,
    )


@router.get("/", response_class=HTMLResponse)
async def dashboard_page(request: Request, db: Session = Depends(get_db)):
    """Dashboard 首页 — 渲染完整页面。"""
    from backend.app.main import templates

    service = _get_dashboard_service(db)
    view = await service.build_dashboard_view()

    # Pydantic model 转 dict 传入模板，避免 Jinja2 缓存问题
    view_dict = view.model_dump(mode="json") if hasattr(view, "model_dump") else view

    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {"view": view_dict},
    )


@router.get("/market_data", response_class=HTMLResponse)
async def market_data_partial(request: Request, db: Session = Depends(get_db)):
    """行情数据 Partial HTML — 用于 AJAX 刷新。"""
    from backend.app.main import templates

    service = _get_dashboard_service(db)
    view = await service.build_dashboard_view()

    # Pydantic model 转 dict 传入模板
    def _dump(obj):
        return obj.model_dump(mode="json") if hasattr(obj, "model_dump") else obj

    return templates.TemplateResponse(
        request,
        "components/market_data.html",
        {
            "market_indices": [_dump(m) for m in view.market_indices],
            "watchlist": [_dump(s) for s in view.watchlist],
            "briefing": _dump(view.briefing) if view.briefing else None,
        },
    )
