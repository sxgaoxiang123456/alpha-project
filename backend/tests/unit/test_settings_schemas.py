import pytest
from pydantic import ValidationError

from backend.app.schemas.settings import SettingCategory, SettingRequest, SettingResponse


class TestSettingCategory:
    def test_valid_categories(self):
        """验证所有合法 category 均可接受。"""
        for cat in SettingCategory:
            req = SettingRequest(key="k", value="v", category=cat)
            assert req.category == cat

    def test_invalid_category_raises_validation_error(self):
        """验证无效 category 触发 pydantic.ValidationError。"""
        with pytest.raises(ValidationError):
            SettingRequest(key="k", value="v", category="invalid_cat")


class TestSettingRequest:
    def test_key_required(self):
        with pytest.raises(ValidationError):
            SettingRequest(value="v")

    def test_value_required(self):
        with pytest.raises(ValidationError):
            SettingRequest(key="k")

    def test_category_defaults_to_general(self):
        req = SettingRequest(key="k", value="v")
        assert req.category == SettingCategory.GENERAL

    def test_is_encrypted_defaults_to_false(self):
        req = SettingRequest(key="k", value="v")
        assert req.is_encrypted is False

    def test_max_key_length(self):
        """key 超过 128 字符应报错。"""
        with pytest.raises(ValidationError):
            SettingRequest(key="x" * 129, value="v")

    def test_max_value_length(self):
        """value 超过 65535 字符应报错。"""
        with pytest.raises(ValidationError):
            SettingRequest(key="k", value="v" * 65536)


class TestSettingResponse:
    def test_response_structure(self):
        resp = SettingResponse(
            key="lark_webhook",
            value="https://example.com",
            category=SettingCategory.LARK,
            is_encrypted=True,
            updated_at="2026-06-05T10:00:00+00:00",
        )
        assert resp.key == "lark_webhook"
        assert resp.category == SettingCategory.LARK
        assert resp.is_encrypted is True
