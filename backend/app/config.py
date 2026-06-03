from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用运行配置。"""

    app_name: str = "A股自动盯盘AI助手"
    database_url: str = "sqlite:///./data/watchlist.db"
    log_level: str = "INFO"

    # 数据源配置
    data_source_timeout: int = 10  # 单次请求超时（秒）
    data_source_retry: int = 1  # 重试次数
    health_check_interval_minutes: int = 5  # 健康检查间隔（分钟）

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    """返回缓存后的应用配置。"""

    return Settings()
