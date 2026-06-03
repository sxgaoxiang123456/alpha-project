"""缓存条目模型 — 数据源容灾缓存持久化。"""

from datetime import datetime, timezone

from sqlalchemy import Index, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.database import Base


class CacheEntry(Base):
    """缓存数据持久化到 SQLite，进程重启后不丢失。"""

    __tablename__ = "cache_entries"

    key: Mapped[str] = mapped_column(Text, primary_key=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    cached_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    expires_at: Mapped[datetime] = mapped_column(nullable=False)

    __table_args__ = (
        Index("ix_cache_entries_expires_at", "expires_at"),
    )
