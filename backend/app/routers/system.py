"""系统级路由 — 数据源状态、健康检查等。"""

from typing import Any

from fastapi import APIRouter, Depends

from backend.app.core.circuit_breaker import CircuitBreaker, CircuitState
from backend.app.database import SessionLocal
from backend.app.dependencies import get_db
from backend.app.models.data_source_status import DataSourceStatus

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/data-sources")
def get_data_sources(db: SessionLocal = Depends(get_db)) -> dict[str, Any]:
    """返回当前各数据源健康状态、当前活跃源。"""
    cb = CircuitBreaker(db)

    # 查询所有数据源状态
    records = db.query(DataSourceStatus).all()

    # 如果没有记录，返回默认状态
    if not records:
        records = [
            DataSourceStatus(name="akshare", status="closed"),
            DataSourceStatus(name="baostock", status="closed"),
        ]

    sources = []
    for r in records:
        sources.append({
            "name": r.name,
            "status": r.status,
            "consecutive_failures": r.consecutive_failures,
            "consecutive_successes": r.consecutive_successes,
            "last_success_at": r.last_success_at.isoformat() if r.last_success_at else None,
            "last_failure_at": r.last_failure_at.isoformat() if r.last_failure_at else None,
            "last_error": r.last_error,
        })

    # 确定当前活跃源
    active_source = _resolve_active_source(cb, records)

    return {
        "sources": sources,
        "active_source": active_source,
    }


def _resolve_active_source(
    cb: CircuitBreaker,
    records: list[DataSourceStatus],
) -> str:
    """根据熔断器状态确定当前活跃的数据源。"""
    # 优先主源（akshare），如果未熔断
    if cb.can_execute("akshare"):
        return "akshare"
    # 主源熔断，尝试备源
    if cb.can_execute("baostock"):
        return "baostock"
    # 全部熔断，返回 unavailable
    return "unavailable"
