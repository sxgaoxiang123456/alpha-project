from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


# .env 文件始终位于 backend/ 目录下（与 config.py 同级父目录）
_ENV_FILE = Path(__file__).parent.parent / ".env"


class Settings(BaseSettings):
    """应用运行配置。"""

    app_name: str = "A股自动盯盘AI助手"
    database_url: str = "sqlite:///./data/watchlist.db"
    log_level: str = "INFO"

    # 数据源配置
    data_source_timeout: int = 10  # 单次请求超时（秒）
    data_source_retry: int = 1  # 重试次数
    health_check_interval_minutes: int = 5  # 健康检查间隔（分钟）

    # 预警配置
    max_alert_rules: int = Field(default=50, ge=1)
    default_cooldown_minutes: int = Field(default=30, ge=5, le=120)

    # 行情配置
    quote_refresh_interval_minutes: int = Field(default=3, ge=1, le=5)
    quote_cache_ttl_seconds: int = Field(default=300, gt=0)
    trading_calendar: str = "cn_stock"

    # 飞书主通道配置（只读 .env，不入库）
    feishu_app_id: str | None = None
    feishu_app_secret: str | None = None
    feishu_brand: str = "feishu"
    feishu_chat_id: str | None = None

    # 加密配置
    encryption_key: str | None = None

    @property
    def feishu_config_complete(self) -> bool:
        """飞书主通道运行时配置完整性：三要素均非空时返回 True。"""
        return all([
            self.feishu_app_id,
            self.feishu_app_secret,
            self.feishu_chat_id,
        ])

    model_config = SettingsConfigDict(env_file=str(_ENV_FILE), extra="ignore")


@lru_cache
def get_settings() -> Settings:
    """返回缓存后的应用配置。"""

    return Settings()
