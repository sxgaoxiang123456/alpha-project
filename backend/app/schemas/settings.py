from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SettingCategory(str, Enum):
    """配置分类枚举。"""

    GENERAL = "general"
    LARK = "lark"
    TELEGRAM = "telegram"
    DATASOURCE = "datasource"
    PREFERENCE = "preference"


class SettingBase(BaseModel):
    """配置基础 schema。"""

    key: str = Field(..., min_length=1, max_length=128)
    value: str = Field(..., min_length=0, max_length=65535)
    category: SettingCategory = Field(default=SettingCategory.GENERAL)
    is_encrypted: bool = Field(default=False)

    @field_validator("key")
    @classmethod
    def reject_blank_key(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("key 不能为空")
        return stripped


class SettingRequest(SettingBase):
    """配置写入请求 schema。"""

    pass


class SettingResponse(SettingBase):
    """配置响应 schema。"""

    model_config = ConfigDict(from_attributes=True)

    updated_at: datetime
