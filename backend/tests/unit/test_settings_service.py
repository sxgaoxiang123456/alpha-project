import pytest
from cryptography.fernet import Fernet
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.database import Base
from backend.app.models.app_setting import AppSetting
from backend.app.services.settings_service import SettingsService


def _make_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    return Session()


class TestSettingsService:
    def test_set_and_get_plain_setting(self):
        """验证普通字段可正常写入和读取。"""
        db = _make_db()
        service = SettingsService(db, encryption_key=Fernet.generate_key())

        service.set_setting("theme", "dark", encrypt=False)
        result = service.get_setting("theme")

        assert result == "dark"

        # 验证数据库中明文存储
        row = db.query(AppSetting).filter_by(key="theme").first()
        assert row.value == "dark"
        assert row.is_encrypted is False

    def test_set_and_get_encrypted_setting(self):
        """验证加密字段写入后数据库中存储密文，读取时自动解密。"""
        db = _make_db()
        key = Fernet.generate_key()
        service = SettingsService(db, encryption_key=key)

        service.set_setting("lark_webhook", "https://secret.url", encrypt=True)
        result = service.get_setting("lark_webhook")

        # 读取返回明文
        assert result == "https://secret.url"

        # 数据库中存储密文
        row = db.query(AppSetting).filter_by(key="lark_webhook").first()
        assert row.is_encrypted is True
        assert row.value != "https://secret.url"

        # 验证密文可被正确解密
        fernet = Fernet(key)
        decrypted = fernet.decrypt(row.value.encode()).decode()
        assert decrypted == "https://secret.url"

    def test_get_nonexistent_setting_returns_none(self):
        db = _make_db()
        service = SettingsService(db, encryption_key=Fernet.generate_key())

        assert service.get_setting("not_exist") is None

    def test_get_all_by_category(self):
        db = _make_db()
        service = SettingsService(db, encryption_key=Fernet.generate_key())

        service.set_setting("lark_webhook", "url1", category="lark")
        service.set_setting("lark_app_id", "id1", category="lark")
        service.set_setting("telegram_token", "tok1", category="telegram")
        service.set_setting("theme", "dark", category="preference")

        lark_settings = service.get_all_by_category("lark")
        assert len(lark_settings) == 2
        assert {s.key for s in lark_settings} == {"lark_webhook", "lark_app_id"}

        telegram_settings = service.get_all_by_category("telegram")
        assert len(telegram_settings) == 1
        assert telegram_settings[0].key == "telegram_token"

    def test_update_existing_setting(self):
        db = _make_db()
        service = SettingsService(db, encryption_key=Fernet.generate_key())

        service.set_setting("theme", "dark")
        service.set_setting("theme", "light")

        assert service.get_setting("theme") == "light"
        rows = db.query(AppSetting).filter_by(key="theme").all()
        assert len(rows) == 1

    def test_encrypt_without_key_raises_error(self):
        """验证无加密密钥时，加密操作报错。"""
        db = _make_db()
        service = SettingsService(db, encryption_key=None)

        with pytest.raises(ValueError, match="加密密钥未配置"):
            service.set_setting("secret", "val", encrypt=True)

    def test_decrypt_without_key_raises_error(self):
        """验证读取加密字段但无密钥时，报错。"""
        db = _make_db()
        key = Fernet.generate_key()
        service_with_key = SettingsService(db, encryption_key=key)
        service_with_key.set_setting("secret", "val", encrypt=True)

        service_no_key = SettingsService(db, encryption_key=None)
        with pytest.raises(ValueError, match="加密密钥未配置"):
            service_no_key.get_setting("secret")

    def test_category_defaults_to_general(self):
        db = _make_db()
        service = SettingsService(db, encryption_key=Fernet.generate_key())

        service.set_setting("key1", "val1")
        row = db.query(AppSetting).filter_by(key="key1").first()
        assert row.category == "general"
