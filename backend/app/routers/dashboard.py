"""Dashboard 路由 — 首页渲染与行情 Partial HTML。"""

import hashlib
import json

from fastapi import APIRouter, Depends, Request, Response
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


def _compute_etag(market_data: dict) -> str:
    """基于行情数据核心字段计算 ETag（MD5 hash）。

    只包含大盘指数点位/涨跌幅和自选股价格/涨跌幅，不包含时间戳和模板结构。
    """
    try:
        # 提取核心字段（支持 dict 和 Pydantic 模型）
        indices = market_data.get("market_indices", [])
        watchlist = market_data.get("watchlist", [])

        def _get(obj, key, default=0):
            if hasattr(obj, key):
                return getattr(obj, key, default)
            if isinstance(obj, dict):
                return obj.get(key, default)
            return default

        core = {
            "indices": [
                {"p": float(_get(idx, "current_value", 0)), "c": float(_get(idx, "change_percent", 0))}
                for idx in indices
            ],
            "watchlist": [
                {"p": float(_get(stock, "current_price", 0)), "c": float(_get(stock, "change_percent", 0))}
                for stock in watchlist
            ],
        }
        payload = json.dumps(core, sort_keys=True, ensure_ascii=False, default=str)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]
    except Exception:
        # ETag 计算异常时降级为空字符串（不触发 304）
        return ""


@router.get("/market_data")
async def market_data_partial(request: Request, db: Session = Depends(get_db)):
    """行情数据 Partial HTML — 用于 AJAX 刷新，支持 ETag/304。

    只返回大盘指数 + 自选股行情，不查询预警/推送历史/通道状态/简报。
    数据无变化时返回 304，不重新渲染模板。
    """
    from backend.app.main import templates

    service = _get_dashboard_service(db)
    data = await service.get_market_data()

    # 计算 ETag
    etag = _compute_etag(data)

    # 检查 If-None-Match
    client_etag = request.headers.get("if-none-match")
    if client_etag and client_etag == etag and etag:
        return Response(status_code=304, headers={"etag": etag})

    # 渲染 Partial HTML
    market_indices = data.get("market_indices", [])
    watchlist = data.get("watchlist", [])

    html = templates.TemplateResponse(
        request,
        "components/market_data_partial.html",
        {
            "market_indices": market_indices,
            "watchlist": watchlist,
            "degraded": data.get("degraded", False),
            "last_refresh": data.get("last_refresh"),
        },
    )

    # 添加 ETag 头
    html.headers["etag"] = etag
    return html
