"""配置与调度器集成测试。"""

from backend.app.config import get_settings


def test_settings_has_data_source_configs():
    settings = get_settings()
    assert hasattr(settings, "data_source_timeout")
    assert hasattr(settings, "data_source_retry")
    assert hasattr(settings, "health_check_interval_minutes")
    assert settings.data_source_timeout == 10
    assert settings.data_source_retry == 1
    assert settings.health_check_interval_minutes == 5


def test_settings_has_quote_refresh_configs():
    settings = get_settings()

    assert settings.quote_refresh_interval_minutes == 3
    assert settings.quote_cache_ttl_seconds == 300
    assert settings.trading_calendar == "cn_stock"
