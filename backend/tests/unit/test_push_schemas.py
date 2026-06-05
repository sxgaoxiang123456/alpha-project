"""T3: Push Pydantic schemas 测试。

RED 阶段 —— schemas 尚未创建，测试应先 FAIL。
"""

import pytest
from pydantic import ValidationError


class TestPushMessageRequest:
    """PushMessageRequest 请求模型校验。"""

    def test_valid_message(self):
        from backend.app.schemas.push import PushMessageRequest

        msg = PushMessageRequest(
            message_type="alert",
            priority="high",
            content={"stock_code": "600519", "price": 1498.50},
        )
        assert msg.message_type == "alert"
        assert msg.priority == "high"
        assert msg.target_channel is None

    def test_invalid_message_type_raises(self):
        from backend.app.schemas.push import PushMessageRequest

        with pytest.raises(ValidationError):
            PushMessageRequest(
                message_type="invalid",
                priority="normal",
                content={},
            )

    def test_invalid_priority_raises(self):
        from backend.app.schemas.push import PushMessageRequest

        with pytest.raises(ValidationError):
            PushMessageRequest(
                message_type="alert",
                priority="urgent",
                content={},
            )

    def test_invalid_target_channel_raises(self):
        from backend.app.schemas.push import PushMessageRequest

        with pytest.raises(ValidationError):
            PushMessageRequest(
                message_type="alert",
                priority="normal",
                content={},
                target_channel="wechat",
            )


class TestPushLogResponse:
    """PushLogResponse 响应模型校验。"""

    def test_valid_response(self):
        from datetime import UTC, datetime
        from backend.app.schemas.push import PushLogResponse

        resp = PushLogResponse(
            id=1,
            message_id="msg-001",
            message_type="alert",
            channel="feishu",
            status="sent",
            created_at=datetime.now(UTC),
        )
        assert resp.id == 1
        assert resp.error_reason is None

    def test_invalid_status_raises(self):
        from datetime import UTC, datetime
        from backend.app.schemas.push import PushLogResponse

        with pytest.raises(ValidationError):
            PushLogResponse(
                id=1,
                message_id="msg-001",
                message_type="alert",
                channel="feishu",
                status="unknown",
                created_at=datetime.now(UTC),
            )


class TestPushChannelStatus:
    """PushChannelStatus 通道状态模型校验。"""

    def test_valid_status(self):
        from datetime import UTC, datetime
        from backend.app.schemas.push import PushChannelStatus

        status = PushChannelStatus(
            name="feishu",
            status="active",
            consecutive_failures=0,
            rate_limited=False,
            updated_at=datetime.now(UTC),
        )
        assert status.name == "feishu"

    def test_invalid_channel_status_raises(self):
        from datetime import UTC, datetime
        from backend.app.schemas.push import PushChannelStatus

        with pytest.raises(ValidationError):
            PushChannelStatus(
                name="feishu",
                status="broken",
                consecutive_failures=0,
                rate_limited=False,
                updated_at=datetime.now(UTC),
            )
