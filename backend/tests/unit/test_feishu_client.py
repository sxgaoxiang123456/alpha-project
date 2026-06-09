"""飞书客户端测试。"""

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


class TestFeishuClientSecretRedaction:
    """007 US3: 密钥不泄露至错误输出。"""

    def test_stderr_with_secret_is_redacted(self, monkeypatch):
        from backend.app.services.feishu_client import FeishuClient

        mock_run = MagicMock(return_value=MagicMock(
            returncode=1,
            stdout="",
            stderr="Error: auth failed with key cli_super_secret_key_12345",
        ))
        monkeypatch.setattr("subprocess.run", mock_run)

        client = FeishuClient(
            app_id="test_app_id",
            app_secret="cli_super_secret_key_12345",
            brand="feishu",
            chat_id="test_chat_id",
        )
        result = client.send_card({"header": {"title": "测试"}})

        assert result["success"] is False
        assert result["error_type"] == "network_error"
        # 脱敏生效：error_message 不应包含原始密钥
        assert "cli_super_secret_key_12345" not in result["error_message"], (
            f"stderr 脱敏失败: error_message 仍含密钥: {result['error_message']}"
        )

    def test_stderr_without_secret_preserved_unchanged(self, monkeypatch):
        from backend.app.services.feishu_client import FeishuClient

        mock_run = MagicMock(return_value=MagicMock(
            returncode=1,
            stdout="",
            stderr="Connection refused",
        ))
        monkeypatch.setattr("subprocess.run", mock_run)

        client = FeishuClient(
            app_id="test_app_id",
            app_secret="test_secret",
            brand="feishu",
            chat_id="test_chat_id",
        )
        result = client.send_card({"header": {"title": "测试"}})

        assert result["success"] is False
        # 不含密钥的 stderr 原样保留
        assert "Connection refused" in result["error_message"]

    def test_lark_cli_not_found_classified_as_client_error(self, monkeypatch):
        from backend.app.services.feishu_client import FeishuClient

        mock_run = MagicMock(side_effect=FileNotFoundError("No such file: lark-cli"))
        monkeypatch.setattr("subprocess.run", mock_run)

        client = FeishuClient(
            app_id="test_app_id",
            app_secret="test_secret",
            brand="feishu",
            chat_id="test_chat_id",
        )
        result = client.send_card({"header": {"title": "测试"}})

        assert result["success"] is False
        assert result["error_type"] == "client_error"
        assert "No such file" in result["error_message"]
