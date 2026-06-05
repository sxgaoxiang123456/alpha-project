import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

from backend.app.database import Base
from backend.app.models.app_setting import AppSetting


def _make_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    return Session()


class TestAppSettingModel:
    def test_table_creation_succeeds(self):
        """验证 AppSetting 表能成功创建，且包含所有字段。"""
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=engine)

        inspector = inspect(engine)
        columns = {col["name"] for col in inspector.get_columns("app_settings")}

        assert "key" in columns
        assert "value" in columns
        assert "category" in columns
        assert "is_encrypted" in columns
        assert "updated_at" in columns
        assert len(columns) == 5

    def test_category_index_exists(self):
        """验证 category 索引存在。"""
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=engine)

        inspector = inspect(engine)
        indexes = inspector.get_indexes("app_settings")
        index_names = {idx["name"] for idx in indexes}

        assert "ix_app_settings_category" in index_names

    def test_crud_basic(self):
        """验证基本增删改查。"""
        db = _make_db()

        setting = AppSetting(
            key="test_key",
            value="test_value",
            category="preference",
            is_encrypted=False,
        )
        db.add(setting)
        db.commit()

        result = db.query(AppSetting).filter_by(key="test_key").first()
        assert result is not None
        assert result.value == "test_value"
        assert result.category == "preference"
        assert result.is_encrypted is False
        assert result.updated_at is not None

    def test_encrypted_setting(self):
        """验证加密标记配置项可正常存储。"""
        db = _make_db()

        setting = AppSetting(
            key="secret_token",
            value="encrypted_blob_here",
            category="lark",
            is_encrypted=True,
        )
        db.add(setting)
        db.commit()

        result = db.query(AppSetting).filter_by(key="secret_token").first()
        assert result.is_encrypted is True
        assert result.category == "lark"

    def test_default_category(self):
        """验证未指定 category 时默认值为 general。"""
        db = _make_db()

        setting = AppSetting(key="no_cat", value="val")
        db.add(setting)
        db.commit()

        result = db.query(AppSetting).filter_by(key="no_cat").first()
        assert result.category == "general"

    def test_key_is_primary_key(self):
        """验证 key 是主键。"""
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=engine)

        inspector = inspect(engine)
        pk = inspector.get_pk_constraint("app_settings")
        assert pk["constrained_columns"] == ["key"]
