from datetime import UTC, datetime

from sqlalchemy import CheckConstraint, DateTime, Index, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.database import Base


def _utcnow():
    return datetime.now(UTC).replace(tzinfo=None)


_VALID_CONDITION_TYPES = (
    "price_above",
    "price_below",
    "change_pct_above",
    "change_pct_below",
    "volume_above",
)
_VALID_LEVELS = ("watch", "alert")
_VALID_STATUSES = ("active", "paused")


class AlertRule(Base):
    __tablename__ = "alert_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    stock_code: Mapped[str] = mapped_column(String(6), nullable=False)
    condition_type: Mapped[str] = mapped_column(String(32), nullable=False)
    threshold: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    cooldown_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    level: Mapped[str] = mapped_column(String(16), nullable=False, default="watch")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    last_evaluated_result: Mapped[bool | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=_utcnow, onupdate=_utcnow
    )

    __table_args__ = (
        Index("ix_alert_rules_stock_code", "stock_code"),
        CheckConstraint(
            condition_type.in_(_VALID_CONDITION_TYPES),
            name="ck_alert_rules_condition_type",
        ),
        CheckConstraint(
            level.in_(_VALID_LEVELS),
            name="ck_alert_rules_level",
        ),
        CheckConstraint(
            status.in_(_VALID_STATUSES),
            name="ck_alert_rules_status",
        ),
    )
