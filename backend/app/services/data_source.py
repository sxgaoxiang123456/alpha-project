"""数据源适配器 — AkShare/BaoStock 统一接口封装。

策略模式：抽象基类 DataSource 定义统一接口 fetch_realtime(codes)，
每个具体适配器处理各自的调用方式和异常映射。
"""

from abc import ABC, abstractmethod
from threading import Lock
from typing import Any

import requests


class DataSourceError(Exception):
    """数据源调用异常，统一封装底层差异。"""

    def __init__(self, error_type: str, message: str):
        self.error_type = error_type
        self.message = message
        super().__init__(f"[{error_type}] {message}")


class DataSource(ABC):
    """数据源抽象基类。"""

    @abstractmethod
    def fetch_realtime(self, codes: list[str]) -> dict[str, dict[str, Any]]:
        """获取实时行情数据，返回标准化结构。

        Returns:
            {code: {"name": str, "price": float, "change_pct": float, ...}}
        """

    def _map_exception(self, exc: Exception) -> DataSourceError:
        """将底层异常映射为统一的 DataSourceError。"""
        if isinstance(exc, TimeoutError):
            return DataSourceError("timeout", str(exc))
        if isinstance(exc, requests.HTTPError):
            if "429" in str(exc):
                return DataSourceError("rate_limited", str(exc))
            return DataSourceError("http_error", str(exc))
        return DataSourceError("unknown", str(exc))


class AkShareDataSource(DataSource):
    """AkShare 主数据源适配器。"""

    def fetch_realtime(self, codes: list[str]) -> dict[str, dict[str, Any]]:
        if not codes:
            return {}

        try:
            raw = self._fetch_from_akshare(codes)
        except TimeoutError as exc:
            raise self._map_exception(exc) from exc
        except requests.HTTPError as exc:
            raise self._map_exception(exc) from exc
        except Exception as exc:
            raise self._map_exception(exc) from exc

        result: dict[str, dict[str, Any]] = {}
        for idx, row in raw.items():
            try:
                code = str(row.get("代码", "")).strip()
            except AttributeError as exc:
                raise DataSourceError(
                    "format_error", f"Unexpected response structure: {exc}"
                ) from exc
            if not code:
                continue
            # AkShare 返回纯数字代码，需映射为系统格式
            # 支持两种传入格式：纯数字（600519）或带前缀（sh600519）
            mapped_code = self._map_akshare_code(code)
            if codes and code not in codes and mapped_code not in codes:
                continue
            # 使用传入格式中匹配的 key
            lookup_code = code if code in codes else mapped_code
            try:
                result[lookup_code] = {
                    "name": str(row.get("名称", "")),
                    "price": float(row.get("最新价", 0) or 0),
                    "change_pct": float(row.get("涨跌幅", 0) or 0),
                    "open": float(row.get("今开", 0) or 0),
                    "high": float(row.get("最高", 0) or 0),
                    "low": float(row.get("最低", 0) or 0),
                    "pre_close": float(row.get("昨收", 0) or 0),
                    "volume": int(row.get("成交量", 0) or 0),
                    "amount": float(row.get("成交额", 0) or 0),
                    "status": str(row.get("状态", "")),
                }
            except (ValueError, TypeError, AttributeError) as exc:
                raise DataSourceError(
                    "format_error", f"Failed to parse row for {code}: {exc}"
                ) from exc

        if not result:
            raise DataSourceError("format_error", "No valid data found in response")

        return result

    def _map_akshare_code(self, code: str) -> str:
        """将 AkShare 纯数字代码映射为系统格式 (sh000001 / sz399001)。"""
        code = code.strip()
        if code.startswith("6"):
            return f"sh{code}"
        return f"sz{code}"

    def _fetch_from_akshare(self, codes: list[str]) -> dict:
        """实际调用 AkShare API，子类/测试可覆盖。

        区分股票和指数：股票调用 stock_zh_a_spot_em，指数调用 stock_zh_index_spot_em。
        """
        import akshare as ak

        # 区分股票代码和指数代码
        index_codes = {"sh000001", "sz399001", "sz399006", "sz399005"}
        has_index = any(c in index_codes for c in codes)
        has_stock = any(c not in index_codes for c in codes)

        result: dict[str, Any] = {}

        if has_stock:
            df = ak.stock_zh_a_spot_em()
            result.update(df.to_dict(orient="index"))

        if has_index:
            df_idx = ak.stock_zh_index_spot_em()
            result.update(df_idx.to_dict(orient="index"))

        return result


class BaoStockDataSource(DataSource):
    """BaoStock 备用数据源适配器。"""

    INDEX_CODES = {"sh000001", "sz399001", "sz399006", "sz399005"}
    _lock = Lock()

    def fetch_realtime(self, codes: list[str]) -> dict[str, dict[str, Any]]:
        if not codes:
            return {}

        try:
            raw = self._fetch_from_baostock(codes)
        except TimeoutError as exc:
            raise self._map_exception(exc) from exc
        except requests.HTTPError as exc:
            raise self._map_exception(exc) from exc
        except Exception as exc:
            raise self._map_exception(exc) from exc

        result: dict[str, dict[str, Any]] = {}
        for code, row in raw.items():
            try:
                result[code] = {
                    "name": str(row.get("name", "")),
                    "price": float(row.get("price", 0) or 0),
                    "change_pct": float(row.get("change_pct", 0) or 0),
                    "change_amount": float(row.get("change_amount", 0) or 0),
                    "open": float(row.get("open", 0) or 0),
                    "high": float(row.get("high", 0) or 0),
                    "low": float(row.get("low", 0) or 0),
                    "pre_close": float(row.get("pre_close", 0) or 0),
                    "volume": int(row.get("volume", 0) or 0),
                    "amount": float(row.get("amount", 0) or 0),
                    "status": str(row.get("status", "")),
                }
            except (ValueError, TypeError) as exc:
                raise DataSourceError(
                    "format_error", f"Failed to parse row for {code}: {exc}"
                ) from exc

        return result

    def _fetch_from_baostock(self, codes: list[str]) -> dict[str, dict[str, Any]]:
        """实际调用 BaoStock API，子类/测试可覆盖。

        统一使用日线：最新 close 为 price，前一日 close 为 pre_close。
        BaoStock 全局连接不支持并发，使用类级锁串行化。
        """
        import baostock as bs

        with self._lock:
            lg = bs.login()
            if lg.error_code != "0":
                raise DataSourceError("unknown", f"BaoStock login failed: {lg.error_msg}")

            try:
                result: dict[str, dict[str, Any]] = {}
                for code in codes:
                    bs_code = self._to_baostock_code(code)
                    # 统一使用日线：最新 close 为 price，前一日 close 为 pre_close
                    frequency = "d"
                    fields = "date,code,open,high,low,close,volume,amount"

                    from datetime import date, timedelta
                    end = date.today().strftime("%Y-%m-%d")
                    start = (date.today() - timedelta(days=5)).strftime("%Y-%m-%d")

                    rs = bs.query_history_k_data_plus(
                        bs_code,
                        fields,
                        start_date=start,
                        end_date=end,
                        frequency=frequency,
                        adjustflag="3",
                    )
                    if rs.error_code != "0":
                        continue

                    data_list = []
                    while rs.error_code == "0" and rs.next():
                        data_list.append(rs.get_row_data())

                    if len(data_list) >= 2:
                        # 最新一根 K 线
                        latest = data_list[-1]
                        # 前一根 K 线的收盘价作为昨收
                        prev = data_list[-2]
                        close_val = float(latest[5]) if latest[5] else 0.0
                        prev_close = float(prev[5]) if prev[5] else 0.0
                        change_pct = (
                            (close_val - prev_close) / prev_close * 100
                            if prev_close > 0 else 0.0
                        )
                        result[code] = {
                            "name": "",
                            "price": close_val,
                            "change_pct": round(change_pct, 2),
                            "change_amount": round(close_val - prev_close, 2),
                            "open": float(latest[2]) if latest[2] else 0.0,
                            "high": float(latest[3]) if latest[3] else 0.0,
                            "low": float(latest[4]) if latest[4] else 0.0,
                            "pre_close": prev_close,
                            "volume": int(latest[6]) if latest[6] else 0,
                            "amount": float(latest[7]) if latest[7] else 0.0,
                        }
                    elif len(data_list) == 1:
                        # 只有一根 K 线，无法计算涨跌幅
                        latest = data_list[0]
                        close_val = float(latest[5]) if latest[5] else 0.0
                        result[code] = {
                            "name": "",
                            "price": close_val,
                            "change_pct": 0.0,
                            "change_amount": 0.0,
                            "open": float(latest[2]) if latest[2] else 0.0,
                            "high": float(latest[3]) if latest[3] else 0.0,
                            "low": float(latest[4]) if latest[4] else 0.0,
                            "pre_close": close_val,
                            "volume": int(latest[6]) if latest[6] else 0,
                            "amount": float(latest[7]) if latest[7] else 0.0,
                        }
                return result
            finally:
                bs.logout()

    def _to_baostock_code(self, code: str) -> str:
        """将系统代码格式转为 BaoStock 格式。"""
        if code.startswith("sh"):
            return f"sh.{code[2:]}"
        if code.startswith("sz"):
            return f"sz.{code[2:]}"
        if code.startswith("6"):
            return f"sh.{code}"
        return f"sz.{code}"
