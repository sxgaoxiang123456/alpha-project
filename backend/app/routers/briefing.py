import json
import logging
import sys
from datetime import UTC, date, datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from backend.app.core import trading_calendar
from backend.app.dependencies import get_db
from backend.app.services.cache_service import CacheService

router = APIRouter(prefix="/api/briefing", tags=["briefing"])

_logger = logging.getLogger(__name__)

BRIEFING_MANUAL_COOLDOWN_KEY = "briefing_manual_cooldown"
LATEST_BRIEFING_CACHE_KEY = "latest_briefing"
MANUAL_COOLDOWN_SECONDS = 30


def _get_cache_service(db: Session = Depends(get_db)) -> CacheService:
    return CacheService(db)


def _trigger_manual_briefing(app) -> None:
    """后台触发手动简报生成。"""
    try:
        factory = app.state.briefing_service_factory
        service = factory()
        service.generate(current_date=date.today(), manual=True)
    except Exception:
        _logger.exception("手动简报生成失败")


def _current_cache_service(db: Session = Depends(get_db)) -> CacheService:
    """依赖包装，用于在测试补丁和模块重载场景下稳定解析 _get_cache_service。"""
    return sys.modules[__name__]._get_cache_service(db)


@router.post("/generate", status_code=202)
def generate_briefing(
    background_tasks: BackgroundTasks,
    request: Request,
    cache: CacheService = Depends(_current_cache_service),
) -> dict:
    if not trading_calendar.is_trading_day(date.today()):
        raise HTTPException(status_code=422, detail="今日非交易日，暂无简报")

    if not cache.set_nx(
        BRIEFING_MANUAL_COOLDOWN_KEY,
        datetime.now(UTC).isoformat(),
        ttl_seconds=MANUAL_COOLDOWN_SECONDS,
    ):
        raise HTTPException(status_code=429, detail="简报刷新冷却中，请稍后再试")

    trigger_fn = sys.modules[__name__]._trigger_manual_briefing
    background_tasks.add_task(trigger_fn, request.app)
    return {"status": "accepted"}


@router.get("/latest")
def get_latest_briefing(cache: CacheService = Depends(_current_cache_service)) -> dict:
    raw = cache.get(LATEST_BRIEFING_CACHE_KEY)
    if raw is None:
        raise HTTPException(status_code=404, detail="今日暂无简报")

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail="简报缓存格式异常") from exc

    return data
