import json
import subprocess


class FeishuClient:
    """飞书 Open API 客户端，通过 lark-cli 发送卡片消息。"""

    def __init__(
        self,
        app_id: str,
        app_secret: str,
        brand: str,
        chat_id: str,
    ):
        self.app_id = app_id
        self.app_secret = app_secret
        self.brand = brand
        self.chat_id = chat_id

    def send_card(self, card_content: dict) -> dict:
        """发送飞书卡片消息。

        Returns:
            dict: {"success": bool, "error_type": str|None, "error_message": str|None}
            error_type 取值: rate_limited, auth_error, network_error, client_error
        """
        payload = {
            "receive_id": self.chat_id,
            "msg_type": "interactive",
            "content": json.dumps(card_content, ensure_ascii=False),
        }
        try:
            result = self._call_lark_cli(payload)
        except Exception as exc:
            return {
                "success": False,
                "error_type": "client_error",
                "error_message": str(exc),
            }

        # 先尝试解析 stdout（即使 returncode != 0，lark-cli 也可能返回 JSON 错误）
        response = None
        if result.stdout.strip():
            try:
                response = json.loads(result.stdout)
            except json.JSONDecodeError:
                pass

        if response is not None:
            code = response.get("code", -1)
            if code == 0:
                return {"success": True, "error_type": None, "error_message": None}

            msg = response.get("msg", "")
            if code == 99991400 or "too many requests" in msg.lower():
                error_type = "rate_limited"
            elif code == 99991663 or "auth" in msg.lower():
                error_type = "auth_error"
            else:
                error_type = "client_error"

            return {
                "success": False,
                "error_type": error_type,
                "error_message": msg,
            }

        # stdout 为空或无法解析，退到 stderr / returncode
        if result.returncode != 0:
            error_msg = result.stderr.strip() or "Unknown subprocess error"
            return {
                "success": False,
                "error_type": "network_error",
                "error_message": error_msg,
            }

        return {
            "success": False,
            "error_type": "client_error",
            "error_message": f"Empty response: {result.stdout}",
        }

    def _call_lark_cli(self, payload: dict) -> subprocess.CompletedProcess:
        cmd = [
            "lark-cli",
            "api",
            "POST",
            "open-apis/im/v1/messages",
            "--data",
            json.dumps(payload, ensure_ascii=False),
            "--app-id",
            self.app_id,
            "--app-secret",
            self.app_secret,
        ]
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
        )
