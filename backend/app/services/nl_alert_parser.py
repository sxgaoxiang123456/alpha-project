import json
import logging
from dataclasses import replace
from typing import Any, Callable

from backend.app.schemas.nl_alert import StockCandidate
from backend.app.services.briefing_llm_client import BriefingLLMClient
from backend.app.services.prompt_loader import PromptLoader
from backend.app.services.rule_based_parser import ParsedAlertIntent, RuleBasedParser
from backend.app.services.stock_search import search_stock_candidates

logger = logging.getLogger(__name__)

StockResolver = Callable[[str], list[StockCandidate]]

DEFAULT_CONFIDENCE_THRESHOLD = 0.7


class NLAlertParser:
    """自然语言预警解析编排器：规则优先 + LLM 兜底 + 股票匹配。"""

    def __init__(
        self,
        confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
        llm_client: BriefingLLMClient | None = None,
        prompt_loader: PromptLoader | None = None,
        stock_resolver: StockResolver | None = None,
    ):
        self.confidence_threshold = confidence_threshold
        self.rule_parser = RuleBasedParser()
        self.llm_client = llm_client
        self.prompt_loader = prompt_loader or PromptLoader()
        self.stock_resolver = stock_resolver or self._default_stock_resolver

    def parse(
        self,
        query: str,
        selected_stock_code: str | None = None,
        llm_client: BriefingLLMClient | None = None,
        stock_resolver: StockResolver | None = None,
    ) -> ParsedAlertIntent:
        llm_client = llm_client or self.llm_client
        stock_resolver = stock_resolver or self.stock_resolver

        rule_intent = self.rule_parser.parse(query)

        # 明确不支持的条件直接返回，不调用 LLM
        if rule_intent.unsupported_condition:
            return rule_intent

        # 明确无效输入直接返回
        if rule_intent.invalid:
            return rule_intent

        # 规则命中且置信度足够，直接走股票匹配
        if rule_intent.confidence >= self.confidence_threshold:
            return self._resolve_stock(rule_intent, selected_stock_code, stock_resolver)

        # 用户已指定股票代码：保留规则解析的条件，直接解析指定股票
        if selected_stock_code:
            resolved = replace(
                rule_intent,
                stock_code=selected_stock_code,
                stock_name=None,
            )
            return self._resolve_stock(resolved, selected_stock_code, stock_resolver)

        # 规则未命中或低置信度，尝试 LLM 兜底
        if llm_client is not None:
            llm_intent = self._parse_with_llm(query, llm_client)
            if llm_intent.confidence >= self.confidence_threshold:
                return self._resolve_stock(llm_intent, selected_stock_code, stock_resolver)
            # LLM 也低置信度：返回 LLM 结果（通常包含 reason）
            return llm_intent

        # 无 LLM 且规则低置信度
        return rule_intent

    def _resolve_stock(
        self,
        intent: ParsedAlertIntent,
        selected_stock_code: str | None,
        stock_resolver: StockResolver,
    ) -> ParsedAlertIntent:
        # 指定代码优先
        if selected_stock_code:
            candidates = stock_resolver(selected_stock_code)
            candidate = next(
                (c for c in candidates if c.stock_code == selected_stock_code), None
            )
            if candidate is None:
                return replace(
                    intent,
                    stock_code=None,
                    stock_name=None,
                    ambiguity=False,
                    candidates=[],
                    message="股票代码不存在，请检查输入",
                    confidence=min(intent.confidence, 0.5),
                )
            return replace(
                intent,
                stock_code=candidate.stock_code,
                stock_name=candidate.stock_name,
                ambiguity=False,
                candidates=[],
            )

        # 规则/LLM 已给出明确代码
        if intent.stock_code:
            candidates = stock_resolver(intent.stock_code)
            candidate = next(
                (c for c in candidates if c.stock_code == intent.stock_code), None
            )
            if candidate is None:
                return replace(
                    intent,
                    stock_code=None,
                    stock_name=None,
                    ambiguity=False,
                    candidates=[],
                    message="未能找到匹配股票，请检查股票名称或代码",
                    confidence=min(intent.confidence, 0.5),
                )
            return replace(
                intent,
                stock_code=candidate.stock_code,
                stock_name=candidate.stock_name,
                ambiguity=False,
                candidates=[],
            )

        # 按名称匹配
        if intent.stock_name:
            candidates = stock_resolver(intent.stock_name)
            if not candidates:
                return replace(
                    intent,
                    stock_code=None,
                    stock_name=None,
                    ambiguity=False,
                    candidates=[],
                    message="未能找到匹配股票，请检查股票名称或代码",
                    confidence=min(intent.confidence, 0.5),
                )
            if len(candidates) == 1:
                candidate = candidates[0]
                return replace(
                    intent,
                    stock_code=candidate.stock_code,
                    stock_name=candidate.stock_name,
                    ambiguity=False,
                    candidates=[],
                )
            # 歧义候选
            return replace(
                intent,
                stock_code=None,
                stock_name=None,
                ambiguity=True,
                candidates=candidates,
                message="请从候选列表中选择具体股票",
                confidence=min(intent.confidence, 0.9),
            )

        # 没有任何股票信息
        return replace(
            intent,
            stock_code=None,
            stock_name=None,
            ambiguity=False,
            candidates=[],
            message="未能找到匹配股票，请检查股票名称或代码",
            confidence=min(intent.confidence, 0.0),
        )

    def _parse_with_llm(
        self,
        query: str,
        llm_client: BriefingLLMClient,
    ) -> ParsedAlertIntent:
        prompt = self.prompt_loader.render_template("nl_alert.j2", query=query)
        result = llm_client.generate(prompt)

        if result.is_degraded or not result.data:
            return ParsedAlertIntent(
                message=result.error_reason or "LLM 解析失败",
                confidence=0.0,
            )

        data = result.data
        try:
            threshold = data.get("threshold")
            if threshold is not None:
                threshold = float(threshold)
            confidence = float(data.get("confidence", 0.0))
            return ParsedAlertIntent(
                stock_code=data.get("stock_code") or None,
                stock_name=data.get("stock_name") or None,
                condition_type=data.get("condition_type") or None,
                threshold=threshold,
                confidence=confidence,
                unsupported_condition=data.get("unsupported_condition") or None,
                invalid=bool(data.get("invalid")),
                message=data.get("reasoning") or query,
            )
        except (TypeError, ValueError) as exc:
            logger.warning("LLM 返回格式异常: %s", exc)
            return ParsedAlertIntent(
                message="LLM 返回格式异常",
                confidence=0.0,
            )

    @staticmethod
    def _default_stock_resolver(query: str) -> list[StockCandidate]:
        try:
            return search_stock_candidates(query, top_n=10)
        except Exception as exc:
            logger.warning("股票匹配失败: %s", exc)
            return []
