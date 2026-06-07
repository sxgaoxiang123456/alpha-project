"""配置管理服务 — 用户级配置持久化与敏感字段加密。"""

from typing import List

from cryptography.fernet import Fernet
from sqlalchemy.orm import Session

from backend.app.models.app_setting import AppSetting
from backend.app.schemas.settings import SettingCategory, SettingResponse


class SettingsService:
    """应用配置管理服务，支持明文和加密存储。"""

    def __init__(self, db: Session, encryption_key: bytes | str | None = None):
        self.db = db
        self._fernet: Fernet | None = None
        if encryption_key is not None:
            key_bytes = encryption_key if isinstance(encryption_key, bytes) else encryption_key.encode()
            self._fernet = Fernet(key_bytes)

    def _require_fernet(self) -> Fernet:
        """确保 Fernet 实例存在，否则抛出异常。"""
        if self._fernet is None:
            raise ValueError("加密密钥未配置，无法处理加密字段")
        return self._fernet

    def _encrypt(self, plaintext: str) -> str:
        """加密明文，返回 Base64 编码的密文字符串。"""
        return self._require_fernet().encrypt(plaintext.encode()).decode()

    def _decrypt(self, ciphertext: str) -> str:
        """解密密文，返回明文字符串。"""
        return self._require_fernet().decrypt(ciphertext.encode()).decode()

    def get_setting(self, key: str) -> str | None:
        """根据 key 读取配置值；加密字段自动解密。"""
        row = self.db.get(AppSetting, key)
        if row is None:
            return None

        if row.is_encrypted:
            return self._decrypt(row.value)
        return row.value

    def set_setting(
        self,
        key: str,
        value: str,
        category: str = "general",
        encrypt: bool = False,
    ) -> None:
        """写入或更新配置值；encrypt=True 时自动加密存储。"""
        row = self.db.get(AppSetting, key)
        if row is None:
            row = AppSetting(key=key)
            self.db.add(row)

        row.value = self._encrypt(value) if encrypt else value
        row.category = category
        row.is_encrypted = encrypt
        self.db.commit()

    def get_all_by_category(self, category: str) -> List[SettingResponse]:
        """按分类获取所有配置项，加密字段自动解密。"""
        rows = (
            self.db.query(AppSetting)
            .filter_by(category=category)
            .order_by(AppSetting.key)
            .all()
        )
        result: List[SettingResponse] = []
        for row in rows:
            value = self._decrypt(row.value) if row.is_encrypted else row.value
            result.append(
                SettingResponse(
                    key=row.key,
                    value=value,
                    category=SettingCategory(row.category),
                    is_encrypted=row.is_encrypted,
                    updated_at=row.updated_at,
                )
            )
        return result
