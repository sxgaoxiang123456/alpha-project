import csv
import io
from decimal import Decimal

MAX_CSV_ROWS = 100


class CsvRowCountExceededError(ValueError):
    """CSV 行数超过上限。"""


class CsvParseError(ValueError):
    """CSV 解析失败。"""


def parse_csv_rows(content: bytes) -> list[dict]:
    """将 UTF-8 CSV 字节流解析为原始字典列表。

    不执行业务校验，仅做格式解析和行数检查。
    行数超过 ``MAX_CSV_ROWS`` 时抛出 ``CsvRowCountExceededError``。
    """
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise CsvParseError("CSV 文件编码必须是 UTF-8") from exc

    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        raise CsvParseError("无法解析 CSV 表头")

    required_columns = {"code", "name"}
    if not required_columns.issubset(set(reader.fieldnames)):
        raise CsvParseError(
            f"CSV 缺少必需列: {required_columns - set(reader.fieldnames)}"
        )

    rows = list(reader)
    if len(rows) > MAX_CSV_ROWS:
        raise CsvRowCountExceededError(
            f"单次最多导入 {MAX_CSV_ROWS} 行，当前 {len(rows)} 行，请分批处理"
        )

    result: list[dict] = []
    for row in rows:
        result.append(
            {
                "code": row.get("code", ""),
                "name": row.get("name", ""),
                "group": row.get("group", "默认分组"),
                "cost_price": row.get("cost_price", ""),
                "shares": row.get("shares", ""),
            }
        )

    return result


def _stock_name(stock, fallback: str) -> str:
    """从 search_stock 返回值中提取名称，兼容 dict 和 Pydantic 模型。"""
    if stock is None:
        return fallback
    if isinstance(stock, dict):
        return stock.get("name", fallback)
    return getattr(stock, "name", fallback)


def _stock_market(stock) -> str:
    if stock is None:
        return ""
    if isinstance(stock, dict):
        return stock.get("market", "")
    return getattr(stock, "market", "")


def _stock_sector(stock):
    if stock is None:
        return None
    if isinstance(stock, dict):
        return stock.get("sector")
    return getattr(stock, "sector", None)


def _stock_status(stock) -> str:
    if stock is None:
        return "正常"
    if isinstance(stock, dict):
        return stock.get("status", "正常")
    return getattr(stock, "status", "正常")


def import_watchlist_from_csv(
    rows: list[dict],
    search_stock_func=None,
    find_or_create_group_func=None,
    existing_codes: set[str] | None = None,
    current_watchlist_count: int = 0,
    max_watchlist_size: int = 100,
) -> dict:
    """逐行导入自选股，支持部分成功。

    返回::

        {
            "success_count": int,
            "failure_count": int,
            "successes": list[dict],
            "failures": list[dict],
        }
    """
    if search_stock_func is None:
        from app.services.stock_search import search_stock

        search_stock_func = search_stock

    if find_or_create_group_func is None:
        find_or_create_group_func = _default_find_or_create_group

    if existing_codes is None:
        existing_codes = set()

    successes: list[dict] = []
    failures: list[dict] = []
    seen_codes: set[str] = set()
    remaining_slots = max_watchlist_size - current_watchlist_count

    for idx, row in enumerate(rows):
        line = idx + 1
        code = row.get("code", "")
        name = row.get("name", "")
        group_name = row.get("group", "默认分组")
        cost_price = row.get("cost_price")
        shares = row.get("shares")

        # 代码格式校验
        if not code or len(code) != 6 or not code.isdigit():
            failures.append(
                {
                    "line": line,
                    "code": code,
                    "reason": "股票代码格式错误",
                }
            )
            continue

        # CSV 内重复
        if code in seen_codes:
            failures.append(
                {
                    "line": line,
                    "code": code,
                    "reason": "股票代码重复",
                }
            )
            continue

        # 已存在于自选股
        if code in existing_codes:
            failures.append(
                {
                    "line": line,
                    "code": code,
                    "reason": f"股票 {code} 已存在于自选股列表中",
                }
            )
            continue

        # 上限检查
        if len(successes) >= remaining_slots:
            failures.append(
                {
                    "line": line,
                    "code": code,
                    "reason": "自选股数量已达上限（100只）",
                }
            )
            continue

        # 数据源查询
        stock = search_stock_func(code)
        if stock is None:
            failures.append(
                {
                    "line": line,
                    "code": code,
                    "reason": f"股票 {code} 不存在",
                }
            )
            continue

        seen_codes.add(code)

        # 分组处理
        group = find_or_create_group_func(group_name)
        group_id = group["id"]

        # 构建成功项
        item: dict = {
            "stock_code": code,
            "name": _stock_name(stock, name),
            "market": _stock_market(stock),
            "sector": _stock_sector(stock),
            "status": _stock_status(stock),
            "group_id": group_id,
            "group_name": group_name,
        }

        # 成本价/持股数转换（非数字字符串视为单条失败）
        if cost_price is not None and cost_price != "":
            try:
                item["cost_price"] = Decimal(str(cost_price))
            except Exception:
                failures.append(
                    {
                        "line": line,
                        "code": code,
                        "reason": f"成本价格式错误: {cost_price}",
                    }
                )
                continue

        if shares is not None and shares != "":
            try:
                item["shares"] = int(shares)
            except Exception:
                failures.append(
                    {
                        "line": line,
                        "code": code,
                        "reason": f"持股数格式错误: {shares}",
                    }
                )
                continue

        successes.append(item)

    return {
        "success_count": len(successes),
        "failure_count": len(failures),
        "successes": successes,
        "failures": failures,
    }


def _default_find_or_create_group(name: str) -> dict:
    """默认分组查找/创建（占位实现，实际应由 group_service 提供）。"""
    from app.models.group import DEFAULT_GROUP_ID, DEFAULT_GROUP_NAME

    if name == DEFAULT_GROUP_NAME:
        return {"id": DEFAULT_GROUP_ID, "name": name}
    return {"id": 2, "name": name}
