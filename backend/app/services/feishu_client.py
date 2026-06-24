import json
import subprocess
import sys


class FeishuClient:
    """飞书 Open API 客户端，通过 lark-cli 发送卡片消息。

    lark-cli v1.x 使用预先注册的应用身份（config init + auth login），
    不支持内联 --app-id / --app-secret。构造函数中保证 lark-cli 配置完成，
    发送时用 --as bot 切换为机器人身份。
    """

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
        self._ensure_config()

    def _ensure_config(self):
        """确保 lark-cli 已注册本应用，缺少时自动 init。"""
        try:
            result = subprocess.run(
                ["lark-cli", "config", "show"],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0:
                info = json.loads(result.stdout)
                if info.get("appId") == self.app_id:
                    return  # already configured
        except Exception:
            pass  # lark-cli may not be installed; non-fatal

        try:
            subprocess.run(
                ["lark-cli", "config", "init",
                 "--app-id", self.app_id,
                 "--brand", self.brand],
                input=self.app_secret + "\n",
                capture_output=True, text=True, timeout=30,
            )
        except Exception:
            pass  # non-fatal: proceed with existing config if any

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
            if self.app_secret and self.app_secret in error_msg:
                error_msg = error_msg.replace(self.app_secret, "***")
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
        """调用 lark-cli api，使用预注册的机器人身份。

        lark-cli v1.x 不支持内联 --app-id/--app-secret，需预先运行
        lark-cli config init + lark-cli auth login 完成注册和鉴权。
        """
        cmd = [
            "lark-cli",
            "api",
            "POST",
            "im/v1/messages",
            "--params", json.dumps({"receive_id_type": "chat_id"}),
            "--data",
            json.dumps(payload, ensure_ascii=False),
            "--as", "bot",
        ]
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
        )
