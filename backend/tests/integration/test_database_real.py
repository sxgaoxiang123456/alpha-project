"""真库数据层测试 -- 验证文件级 SQLite 的约束、事务、迁移往返。

归档信息（testing-system-blueprint）:
- Feature: 006-dashboard
- 缺口 ID: 真库数据层 / 迁移 / 约束
- 路由来源: test-routing-advisor -> backend-testing
- 风险分级与发布门:
  P0 阻断发布: test_primary_key_integrity_conflict, test_transaction_rollback,
               test_file_sqlite_create_all_makes_tables
  P1 告警级:   test_settings_service_on_file_database_roundtrip,
               test_updated_at_auto_updates_on_change,
               test_file_sqlite_pragma_foreign_keys_enabled
  P2 建议级:   test_ensure_sqlite_parent_dir_creates_directories,
               test_migration_drop_all_cleans_tables
- 三层节奏: 慢层（文件级 SQLite I/O，约秒级）
- 可追溯 ID: TR-006-BE-001 ~ TR-006-BE-008
"""

import os
import tempfile
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from backend.app.database import Base, _create_engine, _ensure_sqlite_parent_dir
from backend.app.models.app_setting import AppSetting
from backend.app.services.settings_service import SettingsService
from cryptography.fernet import Fernet


class TestRealSQLiteDatabaseLayer:
    """使用真实文件级 SQLite 数据库（非 :memory:）验证数据层行为。"""

    def test_file_sqlite_create_all_makes_tables(self):
        """RED 期望：Base.metadata.create_all() 在文件库上正确建表。"""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            engine = create_engine(f"sqlite:///{db_path}")
            Base.metadata.create_all(bind=engine)

            inspector = inspect(engine)
            tables = inspector.get_table_names()
            assert "app_settings" in tables

            # 验证索引存在
            indexes = inspector.get_indexes("app_settings")
            index_names = {idx["name"] for idx in indexes}
            assert "ix_app_settings_category" in index_names
        finally:
            os.unlink(db_path)

    def test_file_sqlite_pragma_foreign_keys_enabled(self):
        """RED 期望：_create_engine 创建的 SQLite 连接自动启用外键约束。"""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            engine = _create_engine(f"sqlite:///{db_path}")
            with engine.connect() as conn:
                result = conn.execute(text("PRAGMA foreign_keys"))
                value = result.scalar()
                assert value == 1, f"期望 PRAGMA foreign_keys=ON，实际={value}"
        finally:
            os.unlink(db_path)

    def test_primary_key_integrity_conflict(self):
        """RED 期望：重复 key 插入触发 IntegrityError。"""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            engine = create_engine(f"sqlite:///{db_path}")
            Base.metadata.create_all(bind=engine)
            Session = sessionmaker(bind=engine)
            db = Session()

            row1 = AppSetting(key="theme", value="dark", category="preference")
            db.add(row1)
            db.commit()

            row2 = AppSetting(key="theme", value="light", category="preference")
            db.add(row2)
            with pytest.raises(IntegrityError):
                db.commit()
        finally:
            os.unlink(db_path)

    def test_transaction_rollback(self):
        """RED 期望：rollback() 后数据不持久化到文件库。"""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            engine = create_engine(f"sqlite:///{db_path}")
            Base.metadata.create_all(bind=engine)
            Session = sessionmaker(bind=engine)
            db = Session()

            row = AppSetting(key="rollback_test", value="v1", category="test")
            db.add(row)
            # 不 commit，直接 rollback
            db.rollback()

            # 新会话读取，应不存在
            db2 = Session()
            result = db2.get(AppSetting, "rollback_test")
            assert result is None
        finally:
            os.unlink(db_path)

    def test_settings_service_on_file_database_roundtrip(self):
        """RED 期望：SettingsService 在文件级数据库上加密读写往返正确。"""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            engine = create_engine(f"sqlite:///{db_path}")
            Base.metadata.create_all(bind=engine)
            Session = sessionmaker(bind=engine)
            db = Session()

            key = Fernet.generate_key()
            service = SettingsService(db, encryption_key=key)

            # 写入加密字段
            service.set_setting("lark_webhook", "https://secret.url", encrypt=True)

            # 关闭会话和引擎，模拟进程重启
            db.close()
            engine.dispose()

            # 重新打开文件库，验证数据仍正确
            engine2 = create_engine(f"sqlite:///{db_path}")
            Session2 = sessionmaker(bind=engine2)
            db2 = Session2()
            service2 = SettingsService(db2, encryption_key=key)

            result = service2.get_setting("lark_webhook")
            assert result == "https://secret.url"

            # 验证数据库中确实是密文
            row = db2.get(AppSetting, "lark_webhook")
            assert row.is_encrypted is True
            assert row.value != "https://secret.url"
        finally:
            os.unlink(db_path)

    def test_updated_at_auto_updates_on_change(self):
        """RED 期望：修改记录后 updated_at 自动更新。"""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            engine = create_engine(f"sqlite:///{db_path}")
            Base.metadata.create_all(bind=engine)
            Session = sessionmaker(bind=engine)
            db = Session()

            service = SettingsService(db, encryption_key=Fernet.generate_key())
            service.set_setting("theme", "dark")

            row_before = db.get(AppSetting, "theme")
            first_updated_at = row_before.updated_at

            # 修改同一 key
            import time
            time.sleep(0.01)  # 确保时间有差异
            service.set_setting("theme", "light")

            row_after = db.get(AppSetting, "theme")
            assert row_after.updated_at > first_updated_at
        finally:
            os.unlink(db_path)

    def test_ensure_sqlite_parent_dir_creates_directories(self):
        """RED 期望：_ensure_sqlite_parent_dir 能递归创建父目录。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            nested_path = Path(tmpdir) / "a" / "b" / "c" / "test.db"
            assert not nested_path.parent.exists()
            _ensure_sqlite_parent_dir(f"sqlite:///{nested_path}")
            assert nested_path.parent.exists()

    def test_migration_drop_all_cleans_tables(self):
        """RED 期望：Base.metadata.drop_all() 能清理所有表，create_all() 能重建。"""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            engine = create_engine(f"sqlite:///{db_path}")
            Base.metadata.create_all(bind=engine)

            inspector = inspect(engine)
            assert "app_settings" in inspector.get_table_names()

            Base.metadata.drop_all(bind=engine)

            inspector2 = inspect(engine)
            assert "app_settings" not in inspector2.get_table_names()

            # 重建验证
            Base.metadata.create_all(bind=engine)
            inspector3 = inspect(engine)
            assert "app_settings" in inspector3.get_table_names()
        finally:
            os.unlink(db_path)
