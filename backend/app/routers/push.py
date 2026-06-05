from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.app.dependencies import get_db
from backend.app.models.push_log import PushLog
from backend.app.schemas.push import PushLogResponse

router = APIRouter(prefix="/push", tags=["push"])


def _parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    # URL 中 '+' 被解码为空格，需要还原
    value = value.replace(" ", "+")
    # 支持带时区和无时区的 ISO 格式，统一转为 naive UTC
    value = value.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is not None:
            from datetime import UTC
            dt = dt.astimezone(UTC).replace(tzinfo=None)
        return dt
    except ValueError:
        return None


@router.get("/logs", response_model=list[PushLogResponse])
def list_push_logs(
    db: Session = Depends(get_db),
    message_type: str | None = Query(default=None),
    status: str | None = Query(default=None),
    start_time: str | None = Query(default=None),
    end_time: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
) -> list[PushLogResponse]:
    """查询推送历史日志，支持按类型、状态、时间范围过滤。

    Returns:
        最近 N 条（默认 100）推送记录，按时间倒序。
    """
    query = db.query(PushLog)

    if message_type:
        query = query.filter(PushLog.message_type == message_type)
    if status:
        query = query.filter(PushLog.status == status)

    parsed_start = _parse_iso_datetime(start_time)
    if start_time is not None and parsed_start is None:
        raise HTTPException(status_code=400, detail="Invalid start_time format")
    if parsed_start:
        query = query.filter(PushLog.created_at >= parsed_start)

    parsed_end = _parse_iso_datetime(end_time)
    if end_time is not None and parsed_end is None:
        raise HTTPException(status_code=400, detail="Invalid end_time format")
    if parsed_end:
        query = query.filter(PushLog.created_at <= parsed_end)

    if parsed_start and parsed_end and parsed_start > parsed_end:
        raise HTTPException(status_code=400, detail="start_time must not be greater than end_time")

    logs = (
        query.order_by(PushLog.created_at.desc())
        .limit(limit)
        .all()
    )

    return [PushLogResponse.model_validate(log) for log in logs]
