"""缓存服务 — SQLite 持久化缓存读写与过期清理。"""

from datetime import datetime, timedelta

from sqlalchemy import delete
from sqlalchemy.orm import Session

from backend.app.models.cache_entry import CacheEntry


def _utc_now() -> datetime:
    """返回 naive UTC datetime（SQLite 兼容）。"""
    return datetime.utcnow()


class CacheService:
    """基于 SQLite 的持久化缓存服务。"""

    DEFAULT_TTL_SECONDS = 3600  # 1 小时

    def __init__(self, db: Session):
        self.db = db

    def set(self, key: str, content: str, ttl_seconds: int | None = None) -> None:
        """写入缓存，如 key 已存在则覆盖。"""
        now = _utc_now()
        ttl = ttl_seconds if ttl_seconds is not None else self.DEFAULT_TTL_SECONDS

        entry = self.db.get(CacheEntry, key)
        if entry is None:
            entry = CacheEntry(key=key)
            self.db.add(entry)

        entry.content = content
        entry.cached_at = now
        entry.expires_at = now + timedelta(seconds=ttl)
        self.db.commit()

    def get(self, key: str) -> str | None:
        """查询缓存，过期返回 None。"""
        entry = self.db.get(CacheEntry, key)
        if entry is None:
            return None

        if entry.expires_at < _utc_now():
            return None

        return entry.content

    def cleanup_expired(self) -> int:
        """批量清理过期条目，返回删除数量。"""
        stmt = delete(CacheEntry).where(CacheEntry.expires_at < _utc_now())
        result = self.db.execute(stmt)
        self.db.commit()
        return result.rowcount
