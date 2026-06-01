import csv
import io

from backend.models.group import DEFAULT_GROUP_NAME


def export_watchlist_to_csv(items: list[dict]) -> bytes:
    """将自选股列表导出为 UTF-8 CSV 字节流。

    输出列与导入格式保持一致：code, name, group, cost_price, shares。
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
                "name": stock.get("name", "") if stock else "",
                "group": group.get("name", DEFAULT_GROUP_NAME) if group else DEFAULT_GROUP_NAME,
                "cost_price": f"{cost_price}" if cost_price is not None else "",
                "shares": f"{shares}" if shares is not None else "",
            }
        )

    return output.getvalue().encode("utf-8")
