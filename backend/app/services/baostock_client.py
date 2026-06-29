"""BaoStock 连接复用客户端。

BaoStock 使用全局连接，且每次 login/logout 开销较大。本模块在进程内
维护单一登录态，首次需要时登录，进程退出时通过 atexit 登出，避免每次
查询都重复 login/logout。
"""

import atexit
import logging
import threading
from typing import Any

logger = logging.getLogger(__name__)

_lock: threading.RLock = threading.RLock()
_logged_in: bool = False


def login() -> None:
    """确保 BaoStock 全局连接已登录。"""
    global _logged_in
    with _lock:
        if _logged_in:
            return
        import baostock as bs

        result = bs.login()
        if getattr(result, "error_code", "0") != "0":
            raise RuntimeError(
                f"BaoStock login failed: {getattr(result, 'error_msg', 'unknown')}"
            )
        _logged_in = True
        atexit.register(logout)
        logger.debug("BaoStock login success")


def logout() -> None:
    """登出 BaoStock 全局连接。"""
    global _logged_in
    with _lock:
        if not _logged_in:
            return
        try:
            import baostock as bs

            bs.logout()
        except Exception:
            logger.exception("BaoStock logout failed")
        finally:
            _logged_in = False


def query_history_k_data_plus(*args: Any, **kwargs: Any) -> Any:
    """线程安全地调用 bs.query_history_k_data_plus。"""
    import baostock as bs

    login()
    with _lock:
        return bs.query_history_k_data_plus(*args, **kwargs)


def query_stock_basic(*args: Any, **kwargs: Any) -> Any:
    """线程安全地调用 bs.query_stock_basic。"""
    import baostock as bs

    login()
    with _lock:
        return bs.query_stock_basic(*args, **kwargs)
