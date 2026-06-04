from datetime import datetime

from sqlalchemy import DateTime, Index, Integer
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.database import Base


class CooldownTracker(Base):
    __tablename__ = "cooldown_trackers"

    rule_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    last_triggered_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False
    )
    cooldown_minutes: Mapped[int] = mapped_column(Integer, nullable=False)

    __table_args__ = (
        Index("ix_cooldown_trackers_rule_id", "rule_id", unique=True),
    )
