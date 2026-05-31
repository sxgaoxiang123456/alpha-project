from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.group import DEFAULT_GROUP_ID
from app.schemas.group import GroupResponse
from app.schemas.stock import StockResponse, validate_stock_code


class WatchlistItemCreate(BaseModel):
    stock_code: str = Field(..., min_length=6, max_length=6)
    group_id: int = Field(default=DEFAULT_GROUP_ID, ge=1)
    cost_price: Decimal | None = Field(default=None, ge=0)
    shares: int | None = Field(default=None, ge=0)

    @field_validator("stock_code")
    @classmethod
    def validate_stock_code(cls, value: str) -> str:
        return validate_stock_code(value)


class WatchlistItemUpdate(BaseModel):
    group_id: int | None = Field(default=None, ge=1)
    cost_price: Decimal | None = Field(default=None, ge=0)
    shares: int | None = Field(default=None, ge=0)


class WatchlistItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., ge=1)
    stock_code: str = Field(..., min_length=6, max_length=6)
    group_id: int = Field(..., ge=1)
    added_at: datetime
    cost_price: Decimal | None = Field(default=None, ge=0)
    shares: int | None = Field(default=None, ge=0)
    stock: StockResponse | None = None
    group: GroupResponse | None = None

    @field_validator("stock_code")
    @classmethod
    def validate_stock_code(cls, value: str) -> str:
        return validate_stock_code(value)


class WatchlistCsvRow(BaseModel):
    code: str = Field(..., min_length=6, max_length=6)
    name: str = Field(..., min_length=1, max_length=64)
    group: str = Field(default="默认分组", min_length=1, max_length=64)
    cost_price: Decimal | None = Field(default=None, ge=0)
    shares: int | None = Field(default=None, ge=0)

    @field_validator("cost_price", "shares", mode="before")
    @classmethod
    def blank_optional_number_to_none(cls, value):
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("code")
    @classmethod
    def validate_code(cls, value: str) -> str:
        return validate_stock_code(value)

    @field_validator("name", "group")
    @classmethod
    def reject_blank_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("字段不能为空")
        return stripped
