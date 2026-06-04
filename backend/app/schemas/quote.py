from datetime import date, datetime
from decimal import Decimal
import re

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from backend.app.schemas.stock import validate_stock_code


_SOURCE_STATUSES = {"primary", "fallback", "cached", "unavailable"}
_QUOTE_STATUSES = {"normal", "suspended", "missing", "abnormal", "market_closed"}
_INDEX_CODE_PATTERN = re.compile(r"(sh|sz)[0-9]{6}")


class Quote(BaseModel):
    stock_code: str = Field(..., min_length=6, max_length=6)
    stock_name: str = Field(..., min_length=1, max_length=64)
    current_price: Decimal | None = Field(default=None, gt=0)
    change_percent: Decimal | None = Field(default=None, ge=-100, le=100)
    change_amount: Decimal | None = None
    volume: int | None = Field(default=None, ge=0)
    turnover: Decimal | None = Field(default=None, ge=0)
    updated_at: datetime
    status: str = Field(..., min_length=1)
    source_status: str = Field(..., min_length=1)
    actual_timestamp: datetime

    @field_validator("stock_code")
    @classmethod
    def validate_code(cls, value: str) -> str:
        return validate_stock_code(value)

    @field_validator("stock_name")
    @classmethod
    def reject_blank_stock_name(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("字段不能为空")
        return stripped

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        if value not in _QUOTE_STATUSES:
            raise ValueError(f"status must be one of {_QUOTE_STATUSES}, got '{value}'")
        return value

    @field_validator("source_status")
    @classmethod
    def validate_source_status(cls, value: str) -> str:
        if value not in _SOURCE_STATUSES:
            raise ValueError(f"source_status must be one of {_SOURCE_STATUSES}, got '{value}'")
        return value


class MarketIndex(BaseModel):
    index_code: str = Field(..., min_length=8, max_length=8)
    index_name: str = Field(..., min_length=1, max_length=64)
    current_point: Decimal = Field(..., gt=0)
    change_percent: Decimal = Field(..., ge=-100, le=100)
    change_amount: Decimal
    turnover: Decimal = Field(..., ge=0)
    updated_at: datetime
    source_status: str = Field(..., min_length=1)
    actual_timestamp: datetime

    @field_validator("index_code")
    @classmethod
    def validate_index_code(cls, value: str) -> str:
        if _INDEX_CODE_PATTERN.fullmatch(value) is None:
            raise ValueError("指数代码必须是 sh/sz + 6 位数字")
        return value

    @field_validator("index_name")
    @classmethod
    def reject_blank_index_name(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("字段不能为空")
        return stripped

    @field_validator("source_status")
    @classmethod
    def validate_source_status(cls, value: str) -> str:
        if value not in _SOURCE_STATUSES:
            raise ValueError(f"source_status must be one of {_SOURCE_STATUSES}, got '{value}'")
        return value


class HistoricalQuoteRequest(BaseModel):
    stock_code: str = Field(..., min_length=6, max_length=6)
    start_date: date
    end_date: date

    @field_validator("stock_code")
    @classmethod
    def validate_code(cls, value: str) -> str:
        return validate_stock_code(value)

    @model_validator(mode="after")
    def validate_date_range(self):
        if self.start_date > self.end_date:
            raise ValueError("start_date must be earlier than or equal to end_date")
        return self


class HistoricalQuoteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    stock_code: str = Field(..., min_length=6, max_length=6)
    date: date
    open: Decimal = Field(..., gt=0)
    close: Decimal = Field(..., gt=0)
    high: Decimal = Field(..., gt=0)
    low: Decimal = Field(..., gt=0)
    volume: int = Field(..., ge=0)
    turnover: Decimal = Field(..., ge=0)

    @field_validator("stock_code")
    @classmethod
    def validate_code(cls, value: str) -> str:
        return validate_stock_code(value)
