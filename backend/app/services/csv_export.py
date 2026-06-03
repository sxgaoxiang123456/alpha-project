import csv
import io

from backend.app.models.group import DEFAULT_GROUP_NAME


# 公式注入触发字符：Excel / Google Sheets / WPS 会将以此类字符开头的单元格解释为公式
_FORMULA_START_CHARS = frozenset("=+-@")


def _sanitize_csv_field(value: str) -> str:
    """阻止 CSV 公式注入：对以公式触发字符开头的值前缀单引号。"""
    if value and value[0] in _FORMULA_START_CHARS:
        return "'" + value
    return value


def export_watchlist_to_csv(items: list[dict]) -> bytes:
    """将自选股列表导出为 UTF-8 CSV 字节流。

    输出列与导入格式保持一致：code, name, group, cost_price, shares。
    对可能包含公式注入 payload 的字段（name）进行净化。
    """
    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=["code", "name", "group", "cost_price", "shares"],
    )
    writer.writeheader()

    for item in items:
        stock = item.get("stock") or {}
        group = item.get("group") or {}

        cost_price = item.get("cost_price")
        shares = item.get("shares")

        writer.writerow(
            {
                "code": item.get("stock_code", ""),
                "name": _sanitize_csv_field(stock.get("name", "") if stock else ""),
                "group": _sanitize_csv_field(group.get("name", DEFAULT_GROUP_NAME) if group else DEFAULT_GROUP_NAME),
                "cost_price": f"{cost_price}" if cost_price is not None else "",
                "shares": f"{shares}" if shares is not None else "",
            }
        )

    return output.getvalue().encode("utf-8")
