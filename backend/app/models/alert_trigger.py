from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.database import Base


def _utcnow():
    return datetime.now(UTC).replace(tzinfo=None)


class AlertTrigger(Base):
    __tablename__ = "alert_triggers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    rule_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("alert_rules.id"), nullable=False
    )
    stock_code: Mapped[str] = mapped_column(String(6), nullable=False)
    condition_type: Mapped[str] = mapped_column(String(32), nullable=False)
    trigger_value: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    triggered_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=_utcnow
    )
    level: Mapped[str] = mapped_column(String(16), nullable=False)
    push_status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="pending"
    )
    merged_rule_ids: Mapped[str | None] = mapped_column(String(256), nullable=True)
