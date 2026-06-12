"""Redis 缓存封装 — 连接管理、JSON 序列化、连接异常降级。"""

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_TTL_SECONDS = 60


class RedisCache:
    """Redis 客户端封装。

    对外提供 get/set/delete 接口，内部处理 JSON 序列化/反序列化。
    Redis 不可用时所有操作返回 None，不抛异常，由调用方决定是否回源。
    """

    def __init__(self, client: Any | None = None):
        self._client = client

    def get(self, key: str) -> Any | None:
        """读取缓存值，自动 JSON 反序列化。Redis 不可用返回 None。"""
        if self._client is None:
            return None
        try:
            raw = self._client.get(key)
            if raw is None:
                return None
            if isinstance(raw, bytes):
                raw = raw.decode("utf-8")
            return json.loads(raw)
        except Exception:
            logger.warning("Redis get 失败，key=%s", key, exc_info=True)
            return None

    def set(self, key: str, value: Any, ttl_seconds: int = DEFAULT_TTL_SECONDS) -> bool | None:
        """写入缓存值，自动 JSON 序列化。Redis 不可用返回 None。"""
        if self._client is None:
            return None
        try:
            payload = json.dumps(value, ensure_ascii=False, default=str)
            self._client.set(key, payload, ex=ttl_seconds)
            return True
        except Exception:
            logger.warning("Redis set 失败，key=%s", key, exc_info=True)
            return None

    def delete(self, key: str) -> bool | None:
        """删除缓存键。Redis 不可用返回 None。"""
        if self._client is None:
            return None
        try:
            self._client.delete(key)
            return True
        except Exception:
            logger.warning("Redis delete 失败，key=%s", key, exc_info=True)
            return None
