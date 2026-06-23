from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from backend.app.schemas.stock import validate_stock_code

_MOVE_TYPES = {"volume_spike", "price_surge", "price_drop", "normal"}


class TopMover(BaseModel):
    """异动股票项。"""

    model_config = ConfigDict(from_attributes=True)

    stock_code: str = Field(..., min_length=6, max_length=6)
    stock_name: str = Field(..., min_length=1, max_length=64)
    move_type: str = Field(..., min_length=1, max_length=32)
    value: float = Field(...)
    change_percent: float | None = Field(default=None)
    sector: str | None = Field(default=None, max_length=64)
    insight: str | None = Field(default=None, max_length=512)
    data_sufficient: bool = Field(default=True)

    @field_validator("stock_code")
    @classmethod
    def validate_code(cls, value: str) -> str:
        return validate_stock_code(value)

    @field_validator("move_type")
    @classmethod
    def validate_move_type(cls, value: str) -> str:
        if value not in _MOVE_TYPES:
            raise ValueError(
                f"异动类型必须是 {sorted(_MOVE_TYPES)} 之一，当前值: '{value}'"
            )
        return value


class MarketIndexSnapshot(BaseModel):
    """大盘指数快照（简报专用）。"""

    current: float = Field(...)
    change_pct: float = Field(...)


class BriefingResponse(BaseModel):
    """简报生成结果。"""

    date: str = Field(..., min_length=1, max_length=32)
    market_indices: dict[str, MarketIndexSnapshot]
    top_movers: list[TopMover]
    insights: list[str]
    is_degraded: bool = Field(default=False)
    degraded_reason: str | None = Field(default=None, max_length=256)
    generated_at: datetime | None = Field(default=None)

    @model_validator(mode="after")
    def validate_degraded_reason(self):
        if not self.is_degraded and self.degraded_reason:
            raise ValueError("非降级简报不能设置 degraded_reason")
        return self


class BriefingGenerateRequest(BaseModel):
    """手动生成简报请求。"""

    manual: bool = Field(default=False)
