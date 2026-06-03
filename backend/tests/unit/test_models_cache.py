"""CacheEntry 与 DataSourceStatus 模型测试。"""

import pytest
from sqlalchemy import inspect

from backend.app.database import Base, engine
from backend.app.models.cache_entry import CacheEntry
from backend.app.models.data_source_status import DataSourceStatus


class TestCacheEntry:
    """CacheEntry 模型测试。"""

    @pytest.fixture(autouse=True, scope="class")
    def _create_tables(self):
        Base.metadata.create_all(bind=engine)
        yield
        # 不删除表，便于其他测试复用

    def test_table_has_expected_columns(self):
        """表应含 4 个字段：key, content, cached_at, expires_at。"""
        inspector = inspect(engine)
        columns = {c["name"] for c in inspector.get_columns("cache_entries")}
        assert columns == {"key", "content", "cached_at", "expires_at"}

    def test_key_is_primary_key(self):
        """key 字段应为联合主键的一部分（或单字段主键）。"""
        inspector = inspect(engine)
        pk = inspector.get_pk_constraint("cache_entries")
        assert "key" in pk["constrained_columns"]

    def test_expires_at_has_index(self):
        """expires_at 字段应有索引，加速过期查询。"""
        inspector = inspect(engine)
        indexes = {idx["name"] for idx in inspector.get_indexes("cache_entries")}
        assert "ix_cache_entries_expires_at" in indexes

    def test_model_can_be_instantiated(self):
        """CacheEntry 对象可正常创建。"""
        from datetime import datetime, timedelta, timezone

        now = datetime.now(timezone.utc)
        entry = CacheEntry(
            key="realtime_600519",
            content='{"price": 1800.0}',
            cached_at=now,
            expires_at=now + timedelta(hours=1),
        )
        assert entry.key == "realtime_600519"
        assert entry.content == '{"price": 1800.0}'


class TestDataSourceStatus:
    """DataSourceStatus 模型测试。"""

    def test_table_has_expected_columns(self):
        """表应含 6 个字段。"""
        inspector = inspect(engine)
        columns = {c["name"] for c in inspector.get_columns("data_source_status")}
        expected = {
            "name",
            "status",
            "consecutive_failures",
            "last_success_at",
            "last_failure_at",
            "last_error",
        }
        assert columns == expected

    def test_name_is_primary_key(self):
        """name 字段应为主键。"""
        inspector = inspect(engine)
        pk = inspector.get_pk_constraint("data_source_status")
        assert "name" in pk["constrained_columns"]

    def test_model_can_be_instantiated(self):
        """DataSourceStatus 对象可正常创建。"""
        ds = DataSourceStatus(
            name="akshare",
            status="available",
            consecutive_failures=0,
        )
        assert ds.name == "akshare"
        assert ds.status == "available"
