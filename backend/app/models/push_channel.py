from datetime import UTC, datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.database import Base


def _utcnow():
    return datetime.now(UTC).replace(tzinfo=None)


class PushChannel(Base):
    __tablename__ = "push_channels"

    name: Mapped[str] = mapped_column(String(32), primary_key=True)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="active"
    )
    consecutive_failures: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    rate_limited: Mapped[bool] = mapped_column(
        nullable=False, default=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=_utcnow
    )
