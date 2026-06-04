"""数据源适配器 — AkShare/BaoStock 统一接口封装。

策略模式：抽象基类 DataSource 定义统一接口 fetch_realtime(codes)，
每个具体适配器处理各自的调用方式和异常映射。
"""

from abc import ABC, abstractmethod
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
            raw = self._fetch_from_akshare()
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
            if codes and code not in codes:
                continue
            try:
                result[code] = {
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

    def _fetch_from_akshare(self) -> dict:
        """实际调用 AkShare API，子类/测试可覆盖。"""
        import akshare as ak

        df = ak.stock_zh_a_spot_em()
        return df.to_dict(orient="index")


class BaoStockDataSource(DataSource):
    """BaoStock 备用数据源适配器。"""

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
        """实际调用 BaoStock API，子类/测试可覆盖。"""
        import baostock as bs

        # 登录 BaoStock
        lg = bs.login()
        if lg.error_code != "0":
            raise DataSourceError("unknown", f"BaoStock login failed: {lg.error_msg}")

        try:
            result: dict[str, dict[str, Any]] = {}
            for code in codes:
                # BaoStock 代码格式: sh.600519
                bs_code = f"sh.{code}" if code.startswith("6") else f"sz.{code}"
                rs = bs.query_history_k_data_plus(
                    bs_code,
                    "date,time,code,open,high,low,close,preclose,volume,amount,",
                    frequency="5",
                    adjustflag="3",
                )
                if rs.error_code != "0":
                    continue

                data_list = []
                while (rs.error_code == "0") and rs.next():
                    data_list.append(rs.get_row_data())

                if data_list:
                    latest = data_list[-1]
                    close_val = float(latest[6]) if latest[6] else 0.0
                    preclose_val = float(latest[7]) if latest[7] else 0.0
                    change_pct = (
                        round((close_val - preclose_val) / preclose_val * 100, 2)
                        if preclose_val != 0
                        else 0.0
                    )
                    result[code] = {
                        "name": "",  # BaoStock 历史接口不返回名称
                        "price": close_val,
                        "change_pct": change_pct,
                        "open": float(latest[3]) if latest[3] else 0.0,
                        "high": float(latest[4]) if latest[4] else 0.0,
                        "low": float(latest[5]) if latest[5] else 0.0,
                        "pre_close": preclose_val,
                        "volume": int(latest[8]) if latest[8] else 0,
                        "amount": float(latest[9]) if latest[9] else 0.0,
                    }
            return result
        finally:
            bs.logout()
