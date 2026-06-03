"""数据源获取请求/响应 Schema。"""

from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


class DataFetchRequest(BaseModel):
    """对外部数据源的行情查询请求。"""

    codes: list[str] = Field(default_factory=list, description="股票代码列表")


class DataFetchResult(BaseModel):
    """数据获取的统一响应结构，调用方无感知底层数据源状态。"""

    status: str = Field(
        ...,
        description="数据源状态: primary / fallback / cached / unavailable",
    )
    data: Optional[dict[str, Any]] = Field(
        default=None,
        description="获取到的行情数据，unavailable 时为 None",
    )
    source: Optional[str] = Field(
        default=None,
        description="实际使用的数据源标识，如 akshare / baostock / cache",
    )
    response_time_ms: Optional[float] = Field(
        default=None,
        description="请求响应耗时（毫秒）",
    )

    @field_validator("status")
    @classmethod
    def _validate_status(cls, v: str) -> str:
        allowed = {"primary", "fallback", "cached", "unavailable"}
        if v not in allowed:
            raise ValueError(f"status must be one of {allowed}, got '{v}'")
        return v
