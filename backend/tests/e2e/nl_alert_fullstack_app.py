"""局部前后端接缝测试专用入口 —— 为 NL 预警切片提供确定性股票解析器。

Feature: 010-natural-language-alert
缺口来源: test-routing-advisor -> fullstack-slice-testing
用途: 在真浏览器 + 真后端 + 真 DB 的 fullstack 切片中，把外部股票数据源
      stub 为内存中的确定性候选，使接缝测试不依赖 akshare/baostock 网络。
"""

from backend.app.schemas.nl_alert import StockCandidate
from backend.app.services.nl_alert_parser import NLAlertParser


def _test_stock_resolver(query: str) -> list[StockCandidate]:
    """确定性股票解析器：按关键字返回内存候选。"""
    q = query.strip()
    candidates: list[StockCandidate] = []

    def add(code: str, name: str, sector: str, score: float = 0.95) -> None:
        if not any(c.stock_code == code for c in candidates):
            candidates.append(StockCandidate(stock_code=code, stock_name=name, sector=sector, match_score=score))

    if "茅台" in q or "600519" in q:
        add("600519", "贵州茅台", "白酒")
    if "五粮液" in q or "000858" in q:
        add("000858", "五粮液", "白酒")
    if "浦发" in q or "600000" in q:
        add("600000", "浦发银行", "银行")
    if "平安" in q or "000001" in q:
        add("000001", "平安银行", "银行")
    if "银行" in q:
        add("600000", "浦发银行", "银行")
        add("000001", "平安银行", "银行")

    return candidates


# 在导入 app 前完成 patch，确保所有 NLAlertParser 实例都使用测试解析器
NLAlertParser._default_stock_resolver = staticmethod(_test_stock_resolver)

# 复用真实 app：路由、lifespan、静态文件、模板均保持原样
from backend.app.main import app  # noqa: E402,F401
