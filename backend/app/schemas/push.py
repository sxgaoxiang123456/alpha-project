from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

_VALID_MESSAGE_TYPES = {"alert", "briefing", "system"}
_VALID_PRIORITIES = {"normal", "high"}
_VALID_CHANNELS = {"feishu", "telegram"}
_VALID_LOG_STATUSES = {"sent", "failed", "pending", "fallback"}
_VALID_CHANNEL_STATUSES = {"active", "degraded", "unavailable"}


class PushMessageRequest(BaseModel):
    message_type: str
    priority: str = "normal"
    content: dict[str, Any]
    target_channel: str | None = None

    @field_validator("message_type")
    @classmethod
    def validate_message_type(cls, value: str) -> str:
        if value not in _VALID_MESSAGE_TYPES:
            raise ValueError(
                f"消息类型必须是 {sorted(_VALID_MESSAGE_TYPES)} 之一，当前值: '{value}'"
            )
        return value

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, value: str) -> str:
        if value not in _VALID_PRIORITIES:
            raise ValueError(
                f"优先级必须是 {sorted(_VALID_PRIORITIES)} 之一，当前值: '{value}'"
            )
        return value

    @field_validator("target_channel")
    @classmethod
    def validate_target_channel(cls, value: str | None) -> str | None:
        if value is not None and value not in _VALID_CHANNELS:
            raise ValueError(
                f"目标通道必须是 {sorted(_VALID_CHANNELS)} 之一，当前值: '{value}'"
            )
        return value


class PushLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    message_id: str
    message_type: str
    channel: str
    status: str
    error_reason: str | None = None
    elapsed_ms: int | None = None
    created_at: datetime


class PushChannelStatus(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    status: str
    consecutive_failures: int
    rate_limited: bool
    updated_at: datetime

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        if value not in _VALID_CHANNEL_STATUSES:
            raise ValueError(
                f"通道状态必须是 {sorted(_VALID_CHANNEL_STATUSES)} 之一，当前值: '{value}'"
            )
        return value
