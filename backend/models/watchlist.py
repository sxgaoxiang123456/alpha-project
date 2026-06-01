from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base
from backend.models.group import DEFAULT_GROUP_ID, Group
from backend.models.stock import Stock


class WatchlistItem(Base):
    """用户自选股项模型。"""

    __tablename__ = "watchlist_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    stock_code: Mapped[str] = mapped_column(
        String(6),
        ForeignKey("stocks.code"),
        nullable=False,
        unique=True,
    )
    group_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("groups.id"),
        nullable=False,
        default=DEFAULT_GROUP_ID,
    )
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    cost_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    shares: Mapped[int | None] = mapped_column(Integer, nullable=True)

    stock: Mapped[Stock] = relationship()
    group: Mapped[Group] = relationship()
