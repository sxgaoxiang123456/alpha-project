from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用运行配置。"""

    app_name: str = "A股自动盯盘AI助手"
    database_url: str = "sqlite:///./data/watchlist.db"
    log_level: str = "INFO"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    """返回缓存后的应用配置。"""

    return Settings()
