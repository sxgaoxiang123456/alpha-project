import httpx


class TelegramClient:
    """Telegram Bot API 客户端，发送文本消息。"""

    BASE_URL = "https://api.telegram.org/bot{token}/sendMessage"

    def __init__(
        self,
        bot_token: str,
        chat_id: str,
        proxy: str | None = None,
    ):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.proxy = proxy
        self._url = self.BASE_URL.format(token=bot_token)

    def send_message(self, text: str) -> dict:
        """发送 Telegram 文本消息。

        Returns:
            dict: {"success": bool, "error_type": str|None, "error_message": str|None}
            error_type 取值: auth_error, rate_limited, network_error
        """
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "HTML",
        }
        try:
            kwargs = {"json": payload, "timeout": 30}
            if self.proxy:
                kwargs["proxy"] = self.proxy
            response = httpx.post(self._url, **kwargs)
        except Exception as exc:
            return {
                "success": False,
                "error_type": "network_error",
                "error_message": str(exc),
            }

        if response.status_code == 200:
            data = response.json()
            if data.get("ok"):
                return {"success": True, "error_type": None, "error_message": None}

        error_type = "client_error"
        error_message = f"HTTP {response.status_code}"

        try:
            data = response.json()
            desc = data.get("description", "")
            error_code = data.get("error_code", 0)
            error_message = desc or error_message
            if error_code == 401 or "Unauthorized" in desc:
                error_type = "auth_error"
            elif error_code == 429 or "Too Many Requests" in desc:
                error_type = "rate_limited"
        except Exception:
            pass

        return {
            "success": False,
            "error_type": error_type,
            "error_message": error_message,
        }
