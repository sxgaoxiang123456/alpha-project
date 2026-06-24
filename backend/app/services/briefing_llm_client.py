import json
import logging
import time
from dataclasses import dataclass
from typing import Any

import httpx

logger = logging.getLogger(__name__)


@dataclass
class LLMResult:
    """LLM 调用结果。"""

    is_degraded: bool = False
    data: dict[str, Any] | None = None
    error_reason: str | None = None


class BriefingLLMClient:
    """简报 LLM 客户端：封装 DeepSeek API 调用、超时、重试与降级。"""

    DEFAULT_BASE_URL = "https://api.deepseek.com"
    DEFAULT_MODEL = "deepseek-v4-flash"
    DEFAULT_TIMEOUT_SECONDS = 30
    DEFAULT_RETRY_ATTEMPTS = 3
    DEFAULT_RETRY_INTERVAL_SECONDS = 5

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = DEFAULT_BASE_URL,
        model: str = DEFAULT_MODEL,
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
        retry_attempts: int = DEFAULT_RETRY_ATTEMPTS,
        retry_interval_seconds: int = DEFAULT_RETRY_INTERVAL_SECONDS,
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.retry_attempts = retry_attempts
        self.retry_interval_seconds = retry_interval_seconds

    def generate(self, prompt: str) -> LLMResult:
        """调用 LLM 生成简报解读，失败时返回降级结果。"""
        if not self.api_key:
            return LLMResult(
                is_degraded=True,
                error_reason="DEEPSEEK_API_KEY 未配置",
            )

        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": "你是 A 股市场简报助手，只输出合法 JSON。",
                },
                {"role": "user", "content": prompt},
            ],
            "response_format": {"type": "json_object"},
        }

        last_error: str | None = None
        for attempt in range(1, self.retry_attempts + 1):
            try:
                with httpx.Client(timeout=self.timeout_seconds) as client:
                    response = client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                result_data = response.json()
                content = self._extract_content(result_data)
                if not content:
                    last_error = "LLM 返回内容为空"
                else:
                    parsed = json.loads(content)
                    return LLMResult(is_degraded=False, data=parsed)
            except httpx.TimeoutException:
                last_error = f"LLM 调用超时（第 {attempt} 次）"
            except httpx.HTTPStatusError as exc:
                last_error = f"LLM HTTP 错误 {exc.response.status_code}"
            except json.JSONDecodeError as exc:
                last_error = f"LLM 返回 JSON 解析失败: {exc}"
            except Exception as exc:
                last_error = f"LLM 调用异常: {exc}"

            if attempt < self.retry_attempts:
                logger.warning("%s，%s 秒后重试", last_error, self.retry_interval_seconds)
                time.sleep(self.retry_interval_seconds)
            else:
                logger.error("LLM 连续 %s 次调用失败，降级为模板简报", self.retry_attempts)

        return LLMResult(
            is_degraded=True,
            error_reason=last_error or "LLM 调用失败",
        )

    def _extract_content(self, data: dict[str, Any]) -> str | None:
        """从 OpenAI 兼容响应中提取文本内容。"""
        choices = data.get("choices") if isinstance(data, dict) else None
        if not choices or not isinstance(choices, list):
            return None
        message = choices[0].get("message") if choices else None
        if not message or not isinstance(message, dict):
            return None
        content = message.get("content")
        if isinstance(content, str):
            return content.strip()
        return None
