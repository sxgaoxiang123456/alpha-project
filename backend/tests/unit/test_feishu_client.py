"""T4: 飞书客户端测试。

RED 阶段 —— feishu_client 尚未实现，测试应先 FAIL。
"""

from unittest.mock import MagicMock

import pytest


class TestFeishuClientSend:
    """飞书卡片发送核心逻辑。"""

    def test_send_card_success(self, monkeypatch):
        from backend.app.services.feishu_client import FeishuClient

        mock_run = MagicMock(return_value=MagicMock(
            returncode=0,
            stdout='{"code": 0, "msg": "ok"}',
            stderr="",
        ))
        monkeypatch.setattr("subprocess.run", mock_run)

        client = FeishuClient(
            app_id="test_app_id",
            app_secret="test_secret",
            brand="test_brand",
            chat_id="test_chat_id",
        )
        result = client.send_card({"header": {"title": "测试"}})

        assert result["success"] is True
        assert result.get("error_type") is None

    def test_send_card_rate_limited(self, monkeypatch):
        from backend.app.services.feishu_client import FeishuClient

        mock_run = MagicMock(return_value=MagicMock(
            returncode=1,
            stdout='{"code": 99991400, "msg": "too many requests"}',
            stderr="",
        ))
        monkeypatch.setattr("subprocess.run", mock_run)

        client = FeishuClient(
            app_id="test_app_id",
            app_secret="test_secret",
            brand="test_brand",
            chat_id="test_chat_id",
        )
        result = client.send_card({"header": {"title": "测试"}})

        assert result["success"] is False
        assert result["error_type"] == "rate_limited"

    def test_send_card_auth_error(self, monkeypatch):
        from backend.app.services.feishu_client import FeishuClient

        mock_run = MagicMock(return_value=MagicMock(
            returncode=1,
            stdout='{"code": 99991663, "msg": "auth failed"}',
            stderr="",
        ))
        monkeypatch.setattr("subprocess.run", mock_run)

        client = FeishuClient(
            app_id="test_app_id",
            app_secret="test_secret",
            brand="test_brand",
            chat_id="test_chat_id",
        )
        result = client.send_card({"header": {"title": "测试"}})

        assert result["success"] is False
        assert result["error_type"] == "auth_error"

    def test_send_card_network_error(self, monkeypatch):
        from backend.app.services.feishu_client import FeishuClient

        mock_run = MagicMock(return_value=MagicMock(
            returncode=1,
            stdout="",
            stderr="Connection timeout",
        ))
        monkeypatch.setattr("subprocess.run", mock_run)

        client = FeishuClient(
            app_id="test_app_id",
            app_secret="test_secret",
            brand="test_brand",
            chat_id="test_chat_id",
        )
        result = client.send_card({"header": {"title": "测试"}})

        assert result["success"] is False
        assert result["error_type"] == "network_error"

    def test_send_card_subprocess_exception(self, monkeypatch):
        from backend.app.services.feishu_client import FeishuClient

        mock_run = MagicMock(side_effect=Exception("lark-cli not found"))
        monkeypatch.setattr("subprocess.run", mock_run)

        client = FeishuClient(
            app_id="test_app_id",
            app_secret="test_secret",
            brand="test_brand",
            chat_id="test_chat_id",
        )
        result = client.send_card({"header": {"title": "测试"}})

        assert result["success"] is False
        assert result["error_type"] == "client_error"
