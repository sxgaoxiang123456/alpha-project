from datetime import date

import pytest

from backend.app.core.trading_calendar import TRADING_CALENDAR_CACHE, is_trading_day


@pytest.fixture(autouse=True)
def _clear_cache():
    TRADING_CALENDAR_CACHE.clear()
    yield
    TRADING_CALENDAR_CACHE.clear()


class TestIsTradingDayWeekend:
    def test_saturday_returns_false_without_calling_akshare(self, monkeypatch):
        """周末直接返回 False，不触发 AkShare 调用。"""
        import akshare

        called = False

        def fake_calendar():
            nonlocal called
            called = True
            raise RuntimeError("should not be called")

        monkeypatch.setattr(akshare, "tool_trade_date_hist_sina", fake_calendar)
        result = is_trading_day(date(2026, 6, 6))  # 周六
        assert result is False
        assert called is False

    def test_sunday_returns_false(self):
        result = is_trading_day(date(2026, 6, 7))  # 周日
        assert result is False


class TestIsTradingDayFallback:
    def test_akshare_failure_falls_back_to_weekday_check(self, monkeypatch):
        """AkShare 调用失败时降级为 weekday 判断。"""
        import akshare

        monkeypatch.setattr(
            akshare, "tool_trade_date_hist_sina",
            lambda: (_ for _ in ()).throw(RuntimeError("API unavailable")),
        )
        # 周四，降级后应判为交易日
        result = is_trading_day(date(2026, 6, 4))
        assert result is True

    def test_akshare_import_error_falls_back_to_weekday(self, monkeypatch):
        """AkShare 导入失败时降级为 weekday 判断。"""
        import sys

        # 阻止 akshare 在函数内被 import
        original_import = __builtins__["__import__"]

        def block_akshare(name, *args, **kwargs):
            if name == "akshare":
                raise ImportError("No module named 'akshare'")
            return original_import(name, *args, **kwargs)

        monkeypatch.setitem(__builtins__, "__import__", block_akshare)
        # 周四
        result = is_trading_day(date(2026, 6, 4))
        assert result is True

    def test_cache_prevents_repeated_akshare_calls(self, monkeypatch):
        """命中缓存后不重复调用 AkShare。"""
        import akshare

        call_count = 0

        def counting_calendar():
            nonlocal call_count
            call_count += 1
            import pandas as pd
            return pd.DataFrame({"trade_date": [date(2026, 6, 4)]})

        monkeypatch.setattr(akshare, "tool_trade_date_hist_sina", counting_calendar)
        # 第一次调用
        r1 = is_trading_day(date(2026, 6, 4))
        # 第二次调用应命中缓存
        r2 = is_trading_day(date(2026, 6, 4))
        assert r1 is True
        assert r2 is True
        assert call_count == 1


class TestIsTradingDaySuccess:
    def test_known_trading_day_returns_true(self, monkeypatch):
        """AkShare 返回包含该日期时判为交易日。"""
        import akshare
        import pandas as pd

        monkeypatch.setattr(
            akshare, "tool_trade_date_hist_sina",
            lambda: pd.DataFrame({"trade_date": [date(2026, 6, 4)]}),
        )
        result = is_trading_day(date(2026, 6, 4))
        assert result is True

    def test_non_trading_weekday_returns_false(self, monkeypatch):
        """AkShare 返回不包含该工作日时判为非交易日（如节假日）。"""
        import akshare
        import pandas as pd

        monkeypatch.setattr(
            akshare, "tool_trade_date_hist_sina",
            lambda: pd.DataFrame({"trade_date": [date(2026, 6, 5)]}),
        )  # 只有 6/5，不含 6/4
        result = is_trading_day(date(2026, 6, 4))
        assert result is False
