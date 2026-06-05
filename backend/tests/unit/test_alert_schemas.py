"""T4: Alert Pydantic Schemas 测试。

RED 阶段 —— schema 尚未创建，测试应先 FAIL。
"""

import pytest
from pydantic import ValidationError


class TestAlertRuleRequest:
    """AlertRuleRequest schema 校验测试。"""

    @pytest.fixture(autouse=True)
    def _import_schemas(self):
        from backend.app.schemas.alert import AlertRuleRequest  # noqa: F401

    def test_valid_price_below_rule(self):
        from backend.app.schemas.alert import AlertRuleRequest

        req = AlertRuleRequest(
            stock_code="600519",
            condition_type="price_below",
            threshold=1500.00,
        )
        assert req.stock_code == "600519"
        assert req.condition_type == "price_below"
        assert req.threshold == 1500.00
        assert req.cooldown_minutes == 30
        assert req.level == "watch"

    def test_valid_full_fields(self):
        from backend.app.schemas.alert import AlertRuleRequest

        req = AlertRuleRequest(
            stock_code="000001",
            condition_type="change_pct_above",
            threshold=5.00,
            cooldown_minutes=60,
            level="alert",
        )
        assert req.cooldown_minutes == 60
        assert req.level == "alert"

    def test_invalid_stock_code_too_short(self):
        from backend.app.schemas.alert import AlertRuleRequest

        with pytest.raises(ValidationError):
            AlertRuleRequest(
                stock_code="60051",
                condition_type="price_below",
                threshold=10.0,
            )

    def test_invalid_condition_type(self):
        from backend.app.schemas.alert import AlertRuleRequest

        with pytest.raises(ValidationError):
            AlertRuleRequest(
                stock_code="600519",
                condition_type="invalid",
                threshold=10.0,
            )

    def test_invalid_level(self):
        from backend.app.schemas.alert import AlertRuleRequest

        with pytest.raises(ValidationError):
            AlertRuleRequest(
                stock_code="600519",
                condition_type="price_below",
                threshold=10.0,
                level="urgent",
            )

    def test_cooldown_out_of_range(self):
        from backend.app.schemas.alert import AlertRuleRequest

        with pytest.raises(ValidationError):
            AlertRuleRequest(
                stock_code="600519",
                condition_type="price_below",
                threshold=10.0,
                cooldown_minutes=3,
            )

        with pytest.raises(ValidationError):
            AlertRuleRequest(
                stock_code="600519",
                condition_type="price_below",
                threshold=10.0,
                cooldown_minutes=121,
            )

    def test_negative_price_threshold(self):
        from backend.app.schemas.alert import AlertRuleRequest

        with pytest.raises(ValidationError):
            AlertRuleRequest(
                stock_code="600519",
                condition_type="price_below",
                threshold=-1.0,
            )

    def test_change_pct_out_of_range(self):
        from backend.app.schemas.alert import AlertRuleRequest

        with pytest.raises(ValidationError):
            AlertRuleRequest(
                stock_code="600519",
                condition_type="change_pct_above",
                threshold=35.0,
            )

    def test_volume_threshold_not_negative(self):
        from backend.app.schemas.alert import AlertRuleRequest

        with pytest.raises(ValidationError):
            AlertRuleRequest(
                stock_code="600519",
                condition_type="volume_above",
                threshold=-100,
            )


class TestAlertRuleResponse:
    """AlertRuleResponse schema 测试。"""

    @pytest.fixture(autouse=True)
    def _import_schemas(self):
        from backend.app.schemas.alert import AlertRuleResponse  # noqa: F401

    def test_from_attributes_mode(self):
        """验证 orm_mode (from_attributes=True) 已配置。"""
        from backend.app.schemas.alert import AlertRuleResponse
        assert AlertRuleResponse.model_config.get("from_attributes") is True

    def test_construct_with_data(self):
        from datetime import datetime
        from backend.app.schemas.alert import AlertRuleResponse

        now = datetime.now()
        resp = AlertRuleResponse(
            id=1,
            stock_code="600519",
            condition_type="price_below",
            threshold=1500.00,
            cooldown_minutes=30,
            level="watch",
            status="active",
            last_evaluated_result=None,
            created_at=now,
            updated_at=now,
        )
        assert resp.id == 1
        assert resp.stock_code == "600519"
