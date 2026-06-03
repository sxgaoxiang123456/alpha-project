"""数据源健康状态持久化模型 — 熔断器状态重启后恢复。"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.database import Base


class DataSourceStatus(Base):
    """各数据源的健康状态与熔断信息，进程重启后恢复。"""

    __tablename__ = "data_source_status"

    name: Mapped[str] = mapped_column(String(32), primary_key=True)
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="closed",
    )
    consecutive_failures: Mapped[int] = mapped_column(default=0, nullable=False)
    consecutive_successes: Mapped[int] = mapped_column(default=0, nullable=False)
    last_success_at: Mapped[Optional[datetime]] = mapped_column(default=None)
    last_failure_at: Mapped[Optional[datetime]] = mapped_column(default=None)
    last_error: Mapped[Optional[str]] = mapped_column(Text, default=None)
