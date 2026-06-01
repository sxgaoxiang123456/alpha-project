from collections.abc import Callable, Iterable, Mapping
from typing import Any

from pydantic import ValidationError

from app.schemas.stock import StockSearchResult, validate_stock_code

StockProviderLookup = Callable[[str], Any]


class StockCodeFormatError(ValueError):
    pass


class StockDataSourceUnavailableError(RuntimeError):
    pass


def search_stock(
    query: str | None,
    *,
    manual_name: str | None = None,
    akshare_lookup: StockProviderLookup | None = None,
    baostock_lookup: StockProviderLookup | None = None,
) -> StockSearchResult | None:
    code = _validate_exact_code(query)
    akshare_lookup = akshare_lookup or _akshare_lookup
    baostock_lookup = baostock_lookup or _baostock_lookup

    stock, akshare_unavailable = _lookup_one(code, akshare_lookup)
    if stock is not None:
        return stock

    stock, baostock_unavailable = _lookup_one(code, baostock_lookup)
    if stock is not None:
        return stock

    if akshare_unavailable and baostock_unavailable:
        return _manual_unverified_stock(code, manual_name)

    return None


def search_stocks(
    query: str | None,
    *,
    akshare_lookup: StockProviderLookup | None = None,
    baostock_lookup: StockProviderLookup | None = None,
) -> list[StockSearchResult]:
    keyword = _normalize_query(query)
    if not keyword:
        return []

    if _is_ascii_six_digit(keyword):
        stock = search_stock(
            keyword,
            akshare_lookup=akshare_lookup,
            baostock_lookup=baostock_lookup,
        )
        return [stock] if stock is not None else []

    if _looks_like_invalid_code(keyword):
        raise StockCodeFormatError("股票代码必须是 6 位数字")

    akshare_lookup = akshare_lookup or _akshare_lookup
    try:
        provider_result = akshare_lookup(keyword)
    except StockDataSourceUnavailableError:
        raise
    except Exception as exc:
        raise StockDataSourceUnavailableError("股票数据源不可用") from exc

    results = _coerce_stock_results(provider_result)
    if not results and _provider_items(provider_result):
        raise StockDataSourceUnavailableError("股票数据源返回结构异常")
    return results


def _normalize_query(query: str | None) -> str:
    if not isinstance(query, str):
        raise StockCodeFormatError("股票代码必须是 6 位数字")
    return query.strip()


def _validate_exact_code(query: str | None) -> str:
    code = _normalize_query(query)
    try:
        return validate_stock_code(code)
    except ValueError as exc:
        raise StockCodeFormatError("股票代码必须是 6 位数字") from exc


def _lookup_one(query: str, lookup: StockProviderLookup) -> tuple[StockSearchResult | None, bool]:
    try:
        provider_result = lookup(query)
    except Exception:
        return None, True

    raw_items = _provider_items(provider_result)
    results = _coerce_stock_results(provider_result)
    for result in results:
        if result.code == query:
            return result, False

    if results:
        return None, False
    if raw_items:
        return None, True
    return None, False


def _manual_unverified_stock(code: str, manual_name: str | None) -> StockSearchResult:
    if manual_name is None or not manual_name.strip():
        raise StockDataSourceUnavailableError("股票数据源不可用")

    return StockSearchResult(
        code=code,
        name=manual_name.strip(),
        market=_infer_market(code),
        status="待验证",
    )


def _coerce_stock_results(provider_result: Any) -> list[StockSearchResult]:
    items = _provider_items(provider_result)
    if not items:
        return []

    stocks: list[StockSearchResult] = []
    for item in items:
        stock = _coerce_stock_result(item)
        if stock is not None:
            stocks.append(stock)
    return stocks


def _provider_items(provider_result: Any) -> list[Mapping[str, Any]]:
    if provider_result is None:
        return []

    if isinstance(provider_result, Mapping):
        items = [provider_result]
    elif isinstance(provider_result, Iterable) and not isinstance(provider_result, (str, bytes)):
        items = list(provider_result)
    else:
        return []

    return [item for item in items if isinstance(item, Mapping)]


def _coerce_stock_result(raw: Mapping[str, Any]) -> StockSearchResult | None:
    code = _normalize_code(raw.get("code", ""))
    name = raw.get("name") or raw.get("code_name") or raw.get("名称")
    market = raw.get("market") or raw.get("交易所") or _infer_market(code)
    status = _normalize_status(raw.get("status", "正常"))

    try:
        return StockSearchResult(
            code=code,
            name=str(name).strip() if name is not None else "",
            market=str(market).strip() if market is not None else "",
            sector=raw.get("sector") or raw.get("行业"),
            status=status,
        )
    except (TypeError, ValueError, ValidationError):
        return None


def _normalize_code(value: Any) -> str:
    code = str(value).strip()
    if "." in code:
        code = code.split(".")[-1]
    return code.zfill(6) if code.isascii() and code.isdigit() else code


def _normalize_status(value: Any) -> str:
    if value in (1, "1", "正常", "上市"):
        return "正常"
    if value in (0, "0", "退市"):
        return "退市"
    return str(value).strip()


def _infer_market(code: str) -> str:
    if code.startswith("6"):
        return "沪"
    if code.startswith(("0", "3")):
        return "深"
    if code.startswith(("4", "8")):
        return "北"
    return "未知"


def _akshare_lookup(query: str):
    import akshare as ak

    stock_list = ak.stock_info_a_code_name()
    if "code" not in stock_list.columns or "name" not in stock_list.columns:
        raise StockDataSourceUnavailableError("AkShare 股票列表结构异常")

    codes = stock_list["code"].astype(str).str.zfill(6)
    if _is_ascii_six_digit(query):
        matches = stock_list.loc[codes == query]
    else:
        matches = stock_list.loc[
            stock_list["name"].astype(str).str.contains(query, na=False, regex=False)
        ]

    if matches.empty:
        return [] if not _is_ascii_six_digit(query) else None

    results = []
    for index, row in matches.head(20).iterrows():
        code = str(codes.loc[index])
        results.append(
            {
                "code": code,
                "name": row["name"],
                "market": _infer_market(code),
                "status": "正常",
            }
        )

    return results if not _is_ascii_six_digit(query) else results[0]


def _baostock_lookup(query: str):
    import baostock as bs

    login_result = bs.login()
    if getattr(login_result, "error_code", "0") != "0":
        raise StockDataSourceUnavailableError("BaoStock 登录失败")

    try:
        result_set = bs.query_stock_basic(code=_baostock_code(query))
        if getattr(result_set, "error_code", "0") != "0":
            raise StockDataSourceUnavailableError("BaoStock 查询失败")
        if not result_set.next():
            return None

        row = dict(zip(result_set.fields, result_set.get_row_data(), strict=False))
        code = _normalize_code(row.get("code", query))
        return {
            "code": code,
            "name": row.get("code_name") or row.get("name"),
            "market": _infer_market(code),
            "status": _normalize_status(row.get("status", "正常")),
        }
    finally:
        bs.logout()


def _baostock_code(code: str) -> str:
    prefix = "sh" if code.startswith("6") else "sz"
    return f"{prefix}.{code}"


def _is_ascii_six_digit(value: str) -> bool:
    return len(value) == 6 and value.isascii() and value.isdigit()


def _looks_like_invalid_code(value: str) -> bool:
    return len(value) == 6 and any(character.isdigit() for character in value)
