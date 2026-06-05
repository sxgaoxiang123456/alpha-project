"""T5: Telegram 客户端测试。

RED 阶段 —— telegram_client 尚未实现，测试应先 FAIL。
"""

from unittest.mock import MagicMock

import pytest


class TestTelegramClientSend:
    """Telegram 文本消息发送核心逻辑。"""

    def test_send_message_success(self, monkeypatch):
        from backend.app.services.telegram_client import TelegramClient

        mock_post = MagicMock(return_value=MagicMock(
            status_code=200,
            json=MagicMock(return_value={"ok": True, "result": {"message_id": 123}}),
        ))
        monkeypatch.setattr("httpx.post", mock_post)

        client = TelegramClient(
            bot_token="test_token",
            chat_id="123456",
        )
        result = client.send_message("测试消息")

        assert result["success"] is True
        assert result.get("error_type") is None
        mock_post.assert_called_once()

    def test_send_message_auth_error(self, monkeypatch):
        from backend.app.services.telegram_client import TelegramClient

        mock_post = MagicMock(return_value=MagicMock(
            status_code=401,
            json=MagicMock(return_value={"ok": False, "error_code": 401, "description": "Unauthorized"}),
        ))
        monkeypatch.setattr("httpx.post", mock_post)

        client = TelegramClient(
            bot_token="bad_token",
            chat_id="123456",
        )
        result = client.send_message("测试消息")

        assert result["success"] is False
        assert result["error_type"] == "auth_error"

    def test_send_message_rate_limited(self, monkeypatch):
        from backend.app.services.telegram_client import TelegramClient

        mock_post = MagicMock(return_value=MagicMock(
            status_code=429,
            json=MagicMock(return_value={"ok": False, "error_code": 429, "description": "Too Many Requests"}),
        ))
        monkeypatch.setattr("httpx.post", mock_post)

        client = TelegramClient(
            bot_token="test_token",
            chat_id="123456",
        )
        result = client.send_message("测试消息")

        assert result["success"] is False
        assert result["error_type"] == "rate_limited"

    def test_send_message_network_error(self, monkeypatch):
        from backend.app.services.telegram_client import TelegramClient

        mock_post = MagicMock(side_effect=Exception("Connection timeout"))
        monkeypatch.setattr("httpx.post", mock_post)

        client = TelegramClient(
            bot_token="test_token",
            chat_id="123456",
        )
        result = client.send_message("测试消息")

        assert result["success"] is False
        assert result["error_type"] == "network_error"

    def test_send_message_with_proxy(self, monkeypatch):
        from backend.app.services.telegram_client import TelegramClient

        mock_post = MagicMock(return_value=MagicMock(
            status_code=200,
            json=MagicMock(return_value={"ok": True, "result": {"message_id": 456}}),
        ))
        monkeypatch.setattr("httpx.post", mock_post)

        client = TelegramClient(
            bot_token="test_token",
            chat_id="123456",
            proxy="http://127.0.0.1:7890",
        )
        result = client.send_message("测试消息")

        assert result["success"] is True
        # 验证 proxy 参数被传递
        _, kwargs = mock_post.call_args
        assert kwargs.get("proxy") == "http://127.0.0.1:7890"
