from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class GroupBase(BaseModel):
    """自选股分组基础 schema。"""

    name: str = Field(..., min_length=1, max_length=64)

    @field_validator("name")
    @classmethod
    def reject_blank_name(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("分组名不能为空")
        return stripped


class GroupCreate(GroupBase):
    """创建分组请求 schema。"""


class GroupUpdate(GroupBase):
    """更新分组请求 schema。"""


class GroupResponse(GroupBase):
    """分组响应 schema，支持从 SQLAlchemy 对象构造。"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., ge=1)
    created_at: datetime
    is_default: bool = False
