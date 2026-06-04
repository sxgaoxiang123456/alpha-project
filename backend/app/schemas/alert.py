from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from backend.app.schemas.stock import validate_stock_code

_VALID_CONDITION_TYPES = {
    "price_above",
    "price_below",
    "change_pct_above",
    "change_pct_below",
    "volume_above",
}
_VALID_LEVELS = {"watch", "alert"}


class AlertRuleRequest(BaseModel):
    stock_code: str = Field(..., min_length=6, max_length=6)
    condition_type: str = Field(..., min_length=1)
    threshold: float
    cooldown_minutes: int = Field(default=30, ge=5, le=120)
    level: str = Field(default="watch")

    @field_validator("stock_code")
    @classmethod
    def validate_code(cls, value: str) -> str:
        return validate_stock_code(value)

    @field_validator("condition_type")
    @classmethod
    def validate_condition_type(cls, value: str) -> str:
        if value not in _VALID_CONDITION_TYPES:
            raise ValueError(
                f"条件类型必须是 {sorted(_VALID_CONDITION_TYPES)} 之一，当前值: '{value}'"
            )
        return value

    @field_validator("level")
    @classmethod
    def validate_level(cls, value: str) -> str:
        if value not in _VALID_LEVELS:
            raise ValueError(
                f"触达级别必须是 {sorted(_VALID_LEVELS)} 之一，当前值: '{value}'"
            )
        return value

    @model_validator(mode="after")
    def validate_threshold(self):
        ct = self.condition_type
        t = self.threshold
        if ct in ("price_above", "price_below"):
            if t <= 0:
                raise ValueError("价格阈值必须大于 0")
        elif ct in ("change_pct_above", "change_pct_below"):
            if t < -30 or t > 30:
                raise ValueError("涨跌幅阈值必须在 -30 到 +30 之间")
        elif ct == "volume_above":
            if t < 0:
                raise ValueError("成交量阈值不能为负数")
        return self


class AlertRuleUpdateRequest(BaseModel):
    stock_code: str | None = Field(default=None, min_length=6, max_length=6)
    condition_type: str | None = Field(default=None, min_length=1)
    threshold: float | None = None
    cooldown_minutes: int | None = Field(default=None, ge=5, le=120)
    level: str | None = None

    @field_validator("stock_code")
    @classmethod
    def validate_code(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return validate_stock_code(value)

    @field_validator("condition_type")
    @classmethod
    def validate_condition_type(cls, value: str | None) -> str | None:
        if value is not None and value not in _VALID_CONDITION_TYPES:
            raise ValueError(
                f"条件类型必须是 {sorted(_VALID_CONDITION_TYPES)} 之一，当前值: '{value}'"
            )
        return value

    @field_validator("level")
    @classmethod
    def validate_level(cls, value: str | None) -> str | None:
        if value is not None and value not in _VALID_LEVELS:
            raise ValueError(
                f"触达级别必须是 {sorted(_VALID_LEVELS)} 之一，当前值: '{value}'"
            )
        return value

    @model_validator(mode="after")
    def validate_threshold(self):
        if self.threshold is None or self.condition_type is None:
            return self
        ct = self.condition_type
        t = self.threshold
        if ct in ("price_above", "price_below"):
            if t <= 0:
                raise ValueError("价格阈值必须大于 0")
        elif ct in ("change_pct_above", "change_pct_below"):
            if t < -30 or t > 30:
                raise ValueError("涨跌幅阈值必须在 -30 到 +30 之间")
        elif ct == "volume_above":
            if t < 0:
                raise ValueError("成交量阈值不能为负数")
        return self


class AlertRuleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    stock_code: str
    condition_type: str
    threshold: float
    cooldown_minutes: int
    level: str
    status: str
    last_evaluated_result: bool | None
    created_at: datetime
    updated_at: datetime


class AlertTriggerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    rule_id: int
    stock_code: str
    condition_type: str
    trigger_value: float
    triggered_at: datetime
    level: str
    push_status: str
    merged_rule_ids: str | None = None


class CooldownStatus(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    rule_id: int
    last_triggered_at: datetime
    cooldown_minutes: int
    is_cooling_down: bool = False
