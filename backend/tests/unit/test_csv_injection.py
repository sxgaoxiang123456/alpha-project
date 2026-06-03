"""
C2 · CSV 公式注入安全补测。

Gap ID: C2
Risk Tier: P0
Traceability: 覆盖 FR-005 / FR-012（CSV 导入导出）

当 CSV 字段以 =、+、-、@ 开头时，Excel / Google Sheets / WPS 会将其解释为公式并执行。
恶意 payload 如 =cmd|' /C calc'!A0 可在用户打开 CSV 时执行任意命令。

本测试验证：
1. 导出时对含公式前缀的字段进行净化（前缀单引号）；
2. 导入时对含公式前缀的字段进行净化。
"""

import csv
import io

import pytest


# ---------------------------------------------------------------------------
# 常见公式注入 payload 清单（覆盖 Excel / Google Sheets / WPS）
# ---------------------------------------------------------------------------

FORMULA_PAYLOADS = [
    '=cmd|\' /C calc\'!A0',           # Excel DDE 命令执行
    '+cmd|\' /C calc\'!A0',           # + 前缀公式
    '-cmd|\' /C calc\'!A0',           # - 前缀公式
    '@SUM(A1:A10)',                   # @ 前缀公式（Excel 4.0 宏）
    '=HYPERLINK("http://evil.com")',  # 超链接公式
    '=IMPORTXML("http://evil.com", "//a")',  # Google Sheets 外部数据
]


def _decode_csv_rows(csv_bytes: bytes) -> list[dict]:
    text = csv_bytes.decode("utf-8")
    reader = csv.DictReader(io.StringIO(text))
    return list(reader)


class TestCsvExportInjection:
    """导出时阻止公式注入。"""

    def test_export_sanitizes_leading_equals(self):
        from backend.app.services.csv_export import export_watchlist_to_csv

        items = [
            {
                "stock_code": "600000",
                "stock": {"name": "=cmd|' /C calc'!A0"},
                "group": {"name": "持仓"},
                "cost_price": None,
                "shares": None,
            },
        ]

        result = export_watchlist_to_csv(items)
        rows = _decode_csv_rows(result)

        exported_name = rows[0]["name"]
        # 公式前缀必须被阻止：前缀加单引号或移除公式字符
        assert not exported_name.startswith("="), (
            f"公式注入未被阻止: {exported_name}"
        )

    @pytest.mark.parametrize("payload", FORMULA_PAYLOADS)
    def test_export_sanitizes_all_formula_prefixes(self, payload):
        from backend.app.services.csv_export import export_watchlist_to_csv

        items = [
            {
                "stock_code": "600000",
                "stock": {"name": payload},
                "group": {"name": "持仓"},
                "cost_price": None,
                "shares": None,
            },
        ]

        result = export_watchlist_to_csv(items)
        rows = _decode_csv_rows(result)

        exported_name = rows[0]["name"]
        # 不以任何公式触发字符开头
        assert exported_name[0] not in "=+-@", (
            f"公式前缀未被阻止: {exported_name!r} (原始: {payload!r})"
        )

    def test_export_does_not_sanitize_normal_names(self):
        """正常名称（不含公式前缀）不应被修改。"""
        from backend.app.services.csv_export import export_watchlist_to_csv

        items = [
            {
                "stock_code": "600519",
                "stock": {"name": "贵州茅台"},
                "group": {"name": "持仓"},
                "cost_price": Decimal("1500.50"),
                "shares": 100,
            },
        ]

        result = export_watchlist_to_csv(items)
        rows = _decode_csv_rows(result)

        assert rows[0]["name"] == "贵州茅台"


class TestCsvImportInjection:
    """导入时对公式注入 payload 进行净化。"""

    def test_import_sanitizes_leading_equals(self):
        from backend.app.services.csv_import import parse_csv_rows

        csv_content = 'code,name,group\n600000,=cmd|\' /C calc\'!A0,默认分组\n'
        parsed = parse_csv_rows(csv_content.encode("utf-8"))

        name = parsed[0]["name"]
        assert not name.startswith("="), f"导入时公式注入未被净化: {name}"

    @pytest.mark.parametrize("payload", FORMULA_PAYLOADS)
    def test_import_sanitizes_all_formula_prefixes(self, payload):
        from backend.app.services.csv_import import parse_csv_rows

        # 注意：payload 中可能包含逗号或引号，需要正确 CSV 转义
        import csv as stdlib_csv
        output = io.StringIO()
        writer = stdlib_csv.writer(output)
        writer.writerow(["600000", payload, "默认分组"])
        line = output.getvalue()

        csv_content = f"code,name,group\n{line}"
        parsed = parse_csv_rows(csv_content.encode("utf-8"))

        name = parsed[0]["name"]
        assert name[0] not in "=+-@", (
            f"导入时公式前缀未被净化: {name!r} (原始: {payload!r})"
        )

    def test_import_does_not_sanitize_normal_names(self):
        """正常名称不应被修改。"""
        from backend.app.services.csv_import import parse_csv_rows

        csv_content = "code,name,group\n600519,贵州茅台,默认分组\n"
        parsed = parse_csv_rows(csv_content.encode("utf-8"))

        assert parsed[0]["name"] == "贵州茅台"


from decimal import Decimal
