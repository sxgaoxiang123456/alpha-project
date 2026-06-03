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
