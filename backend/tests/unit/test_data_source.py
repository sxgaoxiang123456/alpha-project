"""数据源适配器单元测试 — AkShare/BaoStock 异常映射与格式标准化。"""

from unittest.mock import MagicMock, patch

import pytest
import requests

from backend.app.services.data_source import (
    AkShareDataSource,
    BaoStockDataSource,
    DataSourceError,
)


class TestDataSourceError:
    """DataSourceError 异常测试。"""

    def test_error_types(self):
        assert DataSourceError("timeout", "connection timeout").error_type == "timeout"
        assert DataSourceError("rate_limited", "too many requests").error_type == "rate_limited"
        assert DataSourceError("format_error", "invalid json").error_type == "format_error"
        assert DataSourceError("unknown", "something wrong").error_type == "unknown"

    def test_str_representation(self):
        err = DataSourceError("timeout", "connection timeout")
        assert str(err) == "[timeout] connection timeout"


class TestAkShareDataSource:
    """AkShare 适配器测试。"""

    @pytest.fixture
    def source(self) -> AkShareDataSource:
        return AkShareDataSource()

    def test_fetch_realtime_success(self, source: AkShareDataSource):
        with patch.object(
            source,
            "_fetch_from_akshare",
            return_value={
                0: {"代码": "600519", "名称": "贵州茅台", "最新价": 1800.0, "涨跌幅": 1.23},
            },
        ):
            result = source.fetch_realtime(["600519"])

        assert "600519" in result
        assert result["600519"]["name"] == "贵州茅台"
        assert result["600519"]["price"] == 1800.0
        assert result["600519"]["change_pct"] == 1.23

    def test_fetch_realtime_timeout(self, source: AkShareDataSource):
        with patch.object(
            source,
            "_fetch_from_akshare",
            side_effect=TimeoutError("Request timed out"),
        ):
            with pytest.raises(DataSourceError) as exc_info:
                source.fetch_realtime(["600519"])
        assert exc_info.value.error_type == "timeout"

    def test_fetch_realtime_rate_limited(self, source: AkShareDataSource):
        with patch.object(
            source,
            "_fetch_from_akshare",
            side_effect=requests.HTTPError("429 Too Many Requests"),
        ):
            with pytest.raises(DataSourceError) as exc_info:
                source.fetch_realtime(["600519"])
        assert exc_info.value.error_type == "rate_limited"

    def test_fetch_realtime_format_error(self, source: AkShareDataSource):
        with patch.object(
            source,
            "_fetch_from_akshare",
            return_value={"invalid": "structure"},
        ):
            with pytest.raises(DataSourceError) as exc_info:
                source.fetch_realtime(["600519"])
        assert exc_info.value.error_type == "format_error"

    def test_fetch_realtime_empty_codes(self, source: AkShareDataSource):
        result = source.fetch_realtime([])
        assert result == {}


class TestBaoStockDataSource:
    """BaoStock 适配器测试。"""

    @pytest.fixture
    def source(self) -> BaoStockDataSource:
        return BaoStockDataSource()

    def test_fetch_realtime_success(self, source: BaoStockDataSource):
        with patch.object(
            source,
            "_fetch_from_baostock",
            return_value={
                "600519": {
                    "name": "贵州茅台",
                    "price": 1800.0,
                    "change_pct": 1.23,
                    "open": 1790.0,
                    "pre_close": 1780.0,
                },
            },
        ):
            result = source.fetch_realtime(["600519"])

        assert "600519" in result
        assert result["600519"]["name"] == "贵州茅台"
        assert result["600519"]["price"] == 1800.0
        assert result["600519"]["change_pct"] == 1.23

    def test_fetch_realtime_timeout(self, source: BaoStockDataSource):
        with patch.object(
            source,
            "_fetch_from_baostock",
            side_effect=TimeoutError("Request timed out"),
        ):
            with pytest.raises(DataSourceError) as exc_info:
                source.fetch_realtime(["600519"])
        assert exc_info.value.error_type == "timeout"

    def test_return_format_matches_akshare(self, source: BaoStockDataSource):
        """BaoStock 返回格式应与 AkShare 一致。"""
        with patch.object(
            source,
            "_fetch_from_baostock",
            return_value={
                "600519": {
                    "name": "贵州茅台",
                    "price": 1800.0,
                    "change_pct": 1.23,
                    "open": 1790.0,
                    "pre_close": 1780.0,
                },
            },
        ):
            result = source.fetch_realtime(["600519"])

        # 验证返回结构与 AkShare 一致
        stock = result["600519"]
        assert "name" in stock
        assert "price" in stock
        assert "change_pct" in stock

    def test_fetch_realtime_empty_codes(self, source: BaoStockDataSource):
        result = source.fetch_realtime([])
        assert result == {}
