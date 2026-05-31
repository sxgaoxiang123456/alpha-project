import re

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StockBase(BaseModel):
    """股票基础信息 schema。"""

    code: str = Field(..., min_length=6, max_length=6)
    name: str = Field(..., min_length=1, max_length=64)
    market: str = Field(..., min_length=1, max_length=16)
    sector: str | None = Field(default=None, max_length=64)
    status: str = Field(default="正常", min_length=1, max_length=16)

    @field_validator("code")
    @classmethod
    def validate_code(cls, value: str) -> str:
        return validate_stock_code(value)

    @field_validator("name", "market", "status")
    @classmethod
    def reject_blank_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("字段不能为空")
        return stripped


class StockResponse(StockBase):
    """股票响应 schema，支持从 SQLAlchemy 对象构造。"""

    model_config = ConfigDict(from_attributes=True)


class StockSearchResult(StockResponse):
    """股票搜索候选结果 schema。"""



def validate_stock_code(value: str) -> str:
    """校验 A 股 6 位数字代码。"""

    if re.fullmatch(r"[0-9]{6}", value) is None:
        raise ValueError("股票代码必须是 6 位数字")
    return value
