from datetime import datetime
from enum import Enum
from typing import List

from pydantic import BaseModel, ConfigDict, Field, field_validator


class LayoutMode(str, Enum):
    """Dashboard 布局模式。"""

    DESKTOP = "desktop"
    MOBILE = "mobile"


class AlertLevel(str, Enum):
    """预警级别。"""

    ALERT = "alert"
    WATCH = "watch"


class PushStatus(str, Enum):
    """推送状态。"""

    SUCCESS = "success"
    FAILED = "failed"
    PENDING = "pending"


class ChannelHealth(str, Enum):
    """通道健康状态。"""

    ACTIVE = "active"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"


class MarketSnapshot(BaseModel):
    """大盘指数快照。"""

    name: str = Field(..., min_length=1, max_length=32)
    current_value: float = Field(...)
    change_percent: float = Field(...)
    change_amount: float = Field(...)
    updated_at: datetime | None = Field(default=None)


class StockCardData(BaseModel):
    """自选股卡片数据。

    行情获取超时/失败时，current_price / change_percent / change_amount
    可能为 None，模板层需做占位处理。
    """

    code: str = Field(..., min_length=6, max_length=6)
    name: str = Field(..., min_length=1, max_length=64)
    current_price: float | None = Field(default=None, ge=0)
    change_percent: float | None = Field(default=None)
    change_amount: float | None = Field(default=None)
    group_name: str | None = Field(default=None, max_length=64)
    trend: List[float] = Field(default_factory=list)
    updated_at: datetime | None = Field(default=None)

    @field_validator("code")
    @classmethod
    def validate_code(cls, value: str) -> str:
        if not value.isdigit() or len(value) != 6:
            raise ValueError("股票代码必须是 6 位数字")
        return value


class BriefingData(BaseModel):
    """AI 简报数据。"""

    insights: List[str] = Field(default_factory=list)
    generated_at: datetime | None = Field(default=None)


class AlertSummary(BaseModel):
    """预警汇总项。"""

    stock_code: str = Field(..., min_length=6, max_length=6)
    stock_name: str = Field(..., min_length=1, max_length=64)
    condition: str = Field(..., min_length=1, max_length=256)
    level: AlertLevel = Field(...)
    triggered_at: datetime | None = Field(default=None)


class PushHistoryItem(BaseModel):
    """推送历史记录项。"""

    message_type: str = Field(..., min_length=1, max_length=32)
    title: str = Field(..., min_length=1, max_length=256)
    sent_at: datetime | None = Field(default=None)
    channel: str = Field(..., min_length=1, max_length=32)
    status: PushStatus = Field(...)
    failure_reason: str | None = Field(default=None, max_length=512)


class ChannelStatusItem(BaseModel):
    """推送通道状态项。"""

    name: str = Field(..., min_length=1, max_length=32)
    status: ChannelHealth = Field(...)
    rate_limited: bool = Field(default=False)
    last_updated: datetime | None = Field(default=None)
    message: str | None = Field(default=None, max_length=256)


class DashboardViewResponse(BaseModel):
    """Dashboard 首页完整响应。"""

    model_config = ConfigDict(from_attributes=True)

    layout_mode: LayoutMode = Field(default=LayoutMode.DESKTOP)
    last_refresh: datetime | None = Field(default=None)
    data_version: str | None = Field(default=None, max_length=32)

    market_indices: List[MarketSnapshot] = Field(default_factory=list)
    watchlist: List[StockCardData] = Field(default_factory=list)
    briefing: BriefingData | None = Field(default=None)
    alerts: List[AlertSummary] = Field(default_factory=list)
    push_history: List[PushHistoryItem] = Field(default_factory=list)
    channel_status: List[ChannelStatusItem] = Field(default_factory=list)

    degraded: bool = Field(default=False)
    degradation_message: str | None = Field(default=None, max_length=256)
