"""缓存服务单元测试 — 读写、过期判断、批量清理。"""

import pytest
from sqlalchemy.orm import Session

from backend.app.database import Base, SessionLocal, engine
from backend.app.models.cache_entry import CacheEntry
from backend.app.services.cache_service import CacheService


@pytest.fixture(autouse=True, scope="module")
def _setup_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture
def db() -> Session:
    session = SessionLocal()
    yield session
    session.rollback()
    session.query(CacheEntry).delete()
    session.commit()
    session.close()


@pytest.fixture
def cache(db: Session) -> CacheService:
    return CacheService(db)


class TestCacheWrite:
    """缓存写入测试。"""

    def test_write_and_read_hit(self, cache: CacheService, db: Session):
        cache.set("realtime_600519", '{"price": 1800.0}')
        result = cache.get("realtime_600519")
        assert result == '{"price": 1800.0}'

    def test_write_overwrites_existing(self, cache: CacheService, db: Session):
        cache.set("realtime_600519", '{"price": 1800.0}')
        cache.set("realtime_600519", '{"price": 1850.0}')
        result = cache.get("realtime_600519")
        assert result == '{"price": 1850.0}'

    def test_write_sets_expiration(self, cache: CacheService, db: Session):
        from datetime import datetime, timedelta

        before = datetime.utcnow()
        cache.set("realtime_600519", '{"price": 1800.0}')
        after = datetime.utcnow()

        record = db.get(CacheEntry, "realtime_600519")
        assert record is not None
        assert record.expires_at is not None
        # 默认 1 小时过期
        assert before + timedelta(minutes=59) < record.expires_at < after + timedelta(minutes=61)


class TestCacheRead:
    """缓存读取测试。"""

    def test_get_nonexistent_returns_none(self, cache: CacheService, db: Session):
        assert cache.get("nonexistent_key") is None

    def test_get_expired_returns_none(self, cache: CacheService, db: Session):
        from datetime import datetime, timedelta

        # 写入一条已过期 1 小时的缓存
        expired_time = datetime.utcnow() - timedelta(hours=2)
        db.add(CacheEntry(
            key="expired_key",
            content='{"price": 100.0}',
            cached_at=expired_time,
            expires_at=expired_time + timedelta(hours=1),
        ))
        db.commit()

        assert cache.get("expired_key") is None

    def test_get_valid_returns_content(self, cache: CacheService, db: Session):
        from datetime import datetime, timedelta

        now = datetime.utcnow()
        db.add(CacheEntry(
            key="valid_key",
            content='{"price": 200.0}',
            cached_at=now,
            expires_at=now + timedelta(hours=1),
        ))
        db.commit()

        assert cache.get("valid_key") == '{"price": 200.0}'


class TestCacheCleanup:
    """缓存清理测试。"""

    def test_cleanup_removes_expired_entries(self, cache: CacheService, db: Session):
        from datetime import datetime, timedelta

        now = datetime.utcnow()
        # 添加 2 条过期 + 1 条有效
        db.add(CacheEntry(
            key="expired_1",
            content='"old"',
            cached_at=now - timedelta(hours=3),
            expires_at=now - timedelta(hours=2),
        ))
        db.add(CacheEntry(
            key="expired_2",
            content='"old"',
            cached_at=now - timedelta(hours=5),
            expires_at=now - timedelta(hours=4),
        ))
        db.add(CacheEntry(
            key="valid_1",
            content='"fresh"',
            cached_at=now,
            expires_at=now + timedelta(hours=1),
        ))
        db.commit()

        deleted = cache.cleanup_expired()
        assert deleted == 2

        # 验证过期条目已删除
        assert db.get(CacheEntry, "expired_1") is None
        assert db.get(CacheEntry, "expired_2") is None
        assert db.get(CacheEntry, "valid_1") is not None

    def test_cleanup_no_expired_returns_zero(self, cache: CacheService, db: Session):
        from datetime import datetime, timedelta

        now = datetime.utcnow()
        db.add(CacheEntry(
            key="valid",
            content='"fresh"',
            cached_at=now,
            expires_at=now + timedelta(hours=1),
        ))
        db.commit()

        assert cache.cleanup_expired() == 0
