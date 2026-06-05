from datetime import UTC, datetime

from sqlalchemy import DateTime, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.database import Base


def _utcnow():
    return datetime.now(UTC).replace(tzinfo=None)


class PushLog(Base):
    __tablename__ = "push_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    message_id: Mapped[str] = mapped_column(String(64), nullable=False)
    message_type: Mapped[str] = mapped_column(String(16), nullable=False)
    channel: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    error_reason: Mapped[str | None] = mapped_column(String(512), nullable=True)
    elapsed_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=_utcnow
    )

    __table_args__ = (
        Index("ix_push_logs_created_at", "created_at"),
    )
