"""DataFetch Pydantic Schema 测试。"""

import pytest
from pydantic import ValidationError

from backend.app.schemas.data_fetch import DataFetchRequest, DataFetchResult


class TestDataFetchRequest:
    """DataFetchRequest schema 测试。"""

    def test_valid_request(self):
        req = DataFetchRequest(codes=["600519", "000001"])
        assert req.codes == ["600519", "000001"]

    def test_empty_codes_allowed(self):
        req = DataFetchRequest(codes=[])
        assert req.codes == []


class TestDataFetchResult:
    """DataFetchResult schema 测试。"""

    def test_valid_status_primary(self):
        result = DataFetchResult(
            status="primary",
            data={"600519": {"price": 1800.0}},
            source="akshare",
        )
        assert result.status == "primary"

    def test_valid_status_fallback(self):
        result = DataFetchResult(
            status="fallback",
            data={"600519": {"price": 1800.0}},
            source="baostock",
        )
        assert result.status == "fallback"

    def test_valid_status_cached(self):
        result = DataFetchResult(
            status="cached",
            data={"600519": {"price": 1800.0}},
            source="cache",
        )
        assert result.status == "cached"

    def test_valid_status_unavailable(self):
        result = DataFetchResult(
            status="unavailable",
            data=None,
            source=None,
        )
        assert result.status == "unavailable"

    def test_invalid_status_raises_validation_error(self):
        with pytest.raises(ValidationError) as exc_info:
            DataFetchResult(
                status="invalid_status",
                data={"600519": {"price": 1800.0}},
                source="akshare",
            )
        assert "status" in str(exc_info.value)

    def test_none_data_allowed(self):
        result = DataFetchResult(
            status="unavailable",
            data=None,
            source=None,
        )
        assert result.data is None
