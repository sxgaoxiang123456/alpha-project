from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

DEFAULT_GROUP_ID = 1
DEFAULT_GROUP_NAME = "默认分组"


class Group(Base):
    """自选股分组模型。"""

    __tablename__ = "groups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
