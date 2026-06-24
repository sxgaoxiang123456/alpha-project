import re
from dataclasses import dataclass, field
from typing import Any

from backend.app.schemas.nl_alert import StockCandidate


@dataclass
class ParsedAlertIntent:
    stock_code: str | None = None
    stock_name: str | None = None
    condition_type: str | None = None
    threshold: float | None = None
    confidence: float = 0.0
    ambiguity: bool = False
    candidates: list[StockCandidate] = field(default_factory=list)
    unsupported_condition: str | None = None
    message: str | None = None
    invalid: bool = False
    invalid_reason: str | None = None


class RuleBasedParser:
    """基于规则/正则的中文自然语言预警解析器。"""

    _CONDITION_PATTERNS: dict[str, list[str]] = {
        "change_pct_above": [
            r"涨幅(?:超过|大于|超)\s*(\d+(?:\.\d+)?)",
            r"涨超\s*(\d+(?:\.\d+)?)",
        ],
        "change_pct_below": [
            r"跌幅(?:超过|大于|超)\s*(\d+(?:\.\d+)?)",
            r"跌超\s*(\d+(?:\.\d+)?)",
        ],
        "price_above": [
            r"(?<![涨跌幅])(?:涨到|突破|高于|超过|大于)\s*(\d+(?:\.\d+)?)",
        ],
        "price_below": [
            r"(?<![涨跌幅])(?:跌破|跌到|低于|小于)\s*(\d+(?:\.\d+)?)",
        ],
    }

    _UNSUPPORTED_PATTERNS: dict[str, list[str]] = {
        "成交量": [
            r"成交量",
            r"(?:volume|vol)",
        ],
    }

    _MULTI_CONDITION_MARKERS = ["和", "与", "以及", "及"]
    _MULTI_CLAUSE_MARKERS = ["或", "还是", "并且", "且"]

    def parse(self, query: str) -> ParsedAlertIntent:
        text = query.strip()
        if not text:
            return self._low_confidence("空输入")

        # 检查不支持的类型（优先级高于具体条件）
        unsupported = self._detect_unsupported_condition(text)
        if unsupported:
            intent = self._base_intent(text)
            intent.unsupported_condition = unsupported
            intent.confidence = self._compute_confidence(
                stock_score=1.0 if self._extract_stock(text)[0] else 0.0,
                condition_score=1.0,
                threshold_score=1.0 if self._extract_any_threshold(text) else 0.0,
                consistency_score=0.0,
            )
            return intent

        # 检查多股票/组合条件
        invalid_reason = self._detect_invalid_input(text)
        if invalid_reason:
            intent = self._base_intent(text)
            intent.invalid = True
            intent.invalid_reason = invalid_reason
            intent.confidence = 0.0
            return intent

        # 提取条件
        condition_type, threshold, condition_score = self._extract_condition(text)
        if condition_type is None:
            # 没有命中任何条件：尝试仅提取股票，作为低置信度结果
            stock_code, stock_name = self._extract_stock(text)
            intent = self._base_intent(text)
            intent.stock_code = stock_code
            intent.stock_name = stock_name
            intent.confidence = self._compute_confidence(
                stock_score=1.0 if (stock_code or stock_name) else 0.0,
                condition_score=0.0,
                threshold_score=0.0,
                consistency_score=0.0,
            )
            return intent

        # 提取股票
        stock_code, stock_name = self._extract_stock(text)

        intent = self._base_intent(text)
        intent.stock_code = stock_code
        intent.stock_name = stock_name
        intent.condition_type = condition_type
        intent.threshold = threshold
        intent.confidence = self._compute_confidence(
            stock_score=1.0 if (stock_code or stock_name) else 0.0,
            condition_score=condition_score,
            threshold_score=1.0 if threshold is not None else 0.0,
            consistency_score=1.0 if (stock_code or stock_name) else 0.0,
        )
        return intent

    def _base_intent(self, query: str) -> ParsedAlertIntent:
        return ParsedAlertIntent(message=query)

    def _detect_unsupported_condition(self, text: str) -> str | None:
        for name, patterns in self._UNSUPPORTED_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    return name
        return None

    def _detect_invalid_input(self, text: str) -> str | None:
        codes = re.findall(r"\b\d{6}\b", text)
        if len(codes) >= 2:
            return "multi_stock"

        # 通过连接词判断多个股票名/条件
        if any(marker in text for marker in self._MULTI_CONDITION_MARKERS):
            # 简单启发：出现连接词且前面有条件关键词，视为多股票
            if self._has_condition_keyword(text):
                return "multi_stock"

        condition_count = self._count_distinct_conditions(text)
        if condition_count >= 2 or any(marker in text for marker in self._MULTI_CLAUSE_MARKERS):
            return "multi_condition"

        return None

    def _has_condition_keyword(self, text: str) -> bool:
        for patterns in self._CONDITION_PATTERNS.values():
            for pattern in patterns:
                if re.search(pattern, text):
                    return True
        return False

    def _count_distinct_conditions(self, text: str) -> int:
        found: set[str] = set()
        for condition_type, patterns in self._CONDITION_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, text):
                    found.add(condition_type)
                    break
        return len(found)

    def _extract_condition(self, text: str) -> tuple[str | None, float | None, float]:
        # 优先匹配涨跌幅（避免价格正则错误命中数字）
        for condition_type in ("change_pct_above", "change_pct_below", "price_above", "price_below"):
            patterns = self._CONDITION_PATTERNS[condition_type]
            for pattern in patterns:
                match = re.search(pattern, text)
                if match:
                    value = float(match.group(1))
                    if condition_type == "change_pct_below":
                        value = -abs(value)
                    elif condition_type == "change_pct_above":
                        value = abs(value)
                    return condition_type, value, 1.0
        return None, None, 0.0

    def _extract_any_threshold(self, text: str) -> bool:
        _, threshold, _ = self._extract_condition(text)
        return threshold is not None

    def _extract_stock(self, text: str) -> tuple[str | None, str | None]:
        # 优先识别 6 位代码
        code_match = re.search(r"\b\d{6}\b", text)
        if code_match:
            return code_match.group(0), None

        # 通过第一个条件关键词定位股票名
        first_keyword_pos = self._first_condition_keyword_position(text)
        if first_keyword_pos is not None and first_keyword_pos > 0:
            prefix = text[:first_keyword_pos]
            name = self._extract_chinese_name(prefix)
            if name:
                return None, name

        # fallback：从句首提取中文名称
        name = self._extract_chinese_name(text)
        if name:
            return None, name

        return None, None

    def _first_condition_keyword_position(self, text: str) -> int | None:
        positions: list[int] = []
        for patterns in self._CONDITION_PATTERNS.values():
            for pattern in patterns:
                match = re.search(pattern, text)
                if match:
                    positions.append(match.start())
        for patterns in self._UNSUPPORTED_PATTERNS.values():
            for pattern in patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    positions.append(match.start())
        return min(positions) if positions else None

    def _extract_chinese_name(self, text: str) -> str | None:
        # 取连续中文或字母数字（股票名）序列，忽略前导非中文字符
        match = re.search(r"[一-龥A-Za-z0-9]+", text)
        if match:
            candidate = match.group(0).strip()
            # 过滤掉常见动词/代词等干扰词
            if candidate and candidate not in ("我", "帮我", "请", "把", "给", "让"):
                return candidate
        return None

    def _low_confidence(self, reason: str) -> ParsedAlertIntent:
        intent = ParsedAlertIntent(message=reason)
        intent.confidence = 0.0
        return intent

    def _compute_confidence(
        self,
        *,
        stock_score: float,
        condition_score: float,
        threshold_score: float,
        consistency_score: float,
    ) -> float:
        return round(
            stock_score * 0.25
            + condition_score * 0.25
            + threshold_score * 0.25
            + consistency_score * 0.25,
            2,
        )

    def to_dict(self, intent: ParsedAlertIntent) -> dict[str, Any]:
        return {
            "stock_code": intent.stock_code,
            "stock_name": intent.stock_name,
            "condition_type": intent.condition_type,
            "threshold": intent.threshold,
            "confidence": intent.confidence,
        }
