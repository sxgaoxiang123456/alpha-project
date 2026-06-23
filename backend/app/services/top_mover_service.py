import logging
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from backend.app.models.historical_quote import HistoricalQuote
from backend.app.schemas.briefing import TopMover
from backend.app.schemas.quote import Quote

logger = logging.getLogger(__name__)


class TopMoverService:
    """异动 TOP 5 计算服务。"""

    HISTORY_DAYS = 5
    VOLUME_SPIKE_THRESHOLD = 2.0
    PRICE_CHANGE_THRESHOLD = 3.0

    def __init__(self, db: Session, history_days: int = HISTORY_DAYS):
        self.db = db
        self.history_days = history_days

    def compute_top_movers(
        self,
        watchlist_quotes: list[Quote],
        fallback_quotes: dict[str, dict[str, Any]] | None = None,
    ) -> list[TopMover]:
        """计算异动 TOP 5，优先自选股，不足时从全市场补充。"""
        watchlist_candidates = self._compute_watchlist_candidates(watchlist_quotes)
        watchlist_candidates.sort(key=lambda x: x["score"], reverse=True)
        selected = watchlist_candidates[:5]

        if len(selected) < 5 and fallback_quotes:
            market_candidates = self._compute_market_candidates(fallback_quotes)
            market_candidates.sort(key=lambda x: x["score"], reverse=True)
            remaining = 5 - len(selected)
            selected.extend(market_candidates[:remaining])

        return [
            TopMover(
                stock_code=c["stock_code"],
                stock_name=c["stock_name"],
                move_type=c["move_type"],
                value=c["value"],
                change_percent=c["change_percent"],
                sector=c.get("sector"),
                insight=c.get("insight"),
                data_sufficient=c["data_sufficient"],
            )
            for c in selected
        ]

    def _compute_watchlist_candidates(
        self, watchlist_quotes: list[Quote]
    ) -> list[dict[str, Any]]:
        """基于自选股计算异动候选。"""
        candidates = []
        today = date.today()
        start_date = today - timedelta(days=self.history_days + 5)

        for quote in watchlist_quotes:
            history = (
                self.db.query(HistoricalQuote)
                .filter(
                    HistoricalQuote.stock_code == quote.stock_code,
                    HistoricalQuote.date >= start_date,
                    HistoricalQuote.date < today,
                )
                .order_by(HistoricalQuote.date.desc())
                .limit(self.history_days)
                .all()
            )

            avg_volume = self._compute_avg_volume(history)
            current_volume = int(quote.volume or 0)
            volume_spike_ratio = (
                current_volume / avg_volume if avg_volume > 0 else 0.0
            )
            change_percent = float(quote.change_percent or 0)

            move_type, value = self._classify_move(volume_spike_ratio, change_percent)
            data_sufficient = len(history) >= 3

            score = volume_spike_ratio + abs(change_percent) * 0.5
            if not data_sufficient:
                score *= 0.5

            candidates.append(
                {
                    "stock_code": quote.stock_code,
                    "stock_name": quote.stock_name,
                    "move_type": move_type,
                    "value": round(value, 2),
                    "change_percent": round(change_percent, 2),
                    "score": score,
                    "data_sufficient": data_sufficient,
                    "insight": self._build_insight(move_type, value, data_sufficient),
                }
            )

        return candidates

    def _compute_market_candidates(
        self, fallback_quotes: dict[str, dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """基于全市场补充数据计算异动候选。"""
        candidates = []
        for code, raw in fallback_quotes.items():
            volume = int(raw.get("volume") or 0)
            change_pct = float(raw.get("change_pct") or 0)
            volume_spike_ratio = 0.0
            move_type, value = self._classify_move(volume_spike_ratio, change_pct)

            candidates.append(
                {
                    "stock_code": code,
                    "stock_name": str(raw.get("name", code)),
                    "move_type": move_type,
                    "value": round(value, 2),
                    "change_percent": round(change_pct, 2),
                    "score": abs(change_pct),
                    "data_sufficient": False,
                    "insight": self._build_insight(move_type, value, False),
                }
            )
        return candidates

    def _compute_avg_volume(self, history: list[HistoricalQuote]) -> float:
        """计算历史均量。"""
        if not history:
            return 0.0
        total = sum(int(h.volume) for h in history)
        return total / len(history)

    def _classify_move(self, volume_spike_ratio: float, change_percent: float) -> tuple[str, float]:
        """根据量价特征分类异动类型并返回代表数值。未达阈值时标记为 normal。"""
        if volume_spike_ratio >= self.VOLUME_SPIKE_THRESHOLD:
            return "volume_spike", volume_spike_ratio
        if change_percent >= self.PRICE_CHANGE_THRESHOLD:
            return "price_surge", change_percent
        if change_percent <= -self.PRICE_CHANGE_THRESHOLD:
            return "price_drop", change_percent
        return "normal", change_percent

    def _build_insight(
        self, move_type: str, value: float, data_sufficient: bool
    ) -> str:
        """生成一句话异动说明。"""
        suffix = "" if data_sufficient else "（历史数据不足，仅供参考）"
        if move_type == "volume_spike":
            return f"成交量为近期均量的 {value:.1f} 倍{suffix}"
        if move_type == "price_surge":
            return f"涨幅 {value:.2f}%，短期异动{suffix}"
        if move_type == "price_drop":
            return f"跌幅 {abs(value):.2f}%，短期异动{suffix}"
        return f"当前涨跌幅 {value:.2f}%，未达异动阈值{suffix}"
