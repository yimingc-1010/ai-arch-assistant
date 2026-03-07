"""Query planner: analyse user intent and produce a structured retrieval plan."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import List

from lawrag.providers.base import LLMProvider

_PLANNER_SYSTEM_PROMPT = """你是一位專業的法律資訊檢索規劃師。
你的任務是分析使用者的法律問題，並以 JSON 格式輸出一份結構化的檢索計劃。

JSON 格式如下（不要輸出任何 JSON 以外的內容）：
{
  "sub_queries": ["子查詢1", "子查詢2"],
  "required_law_types": ["母法", "子法"],
  "required_jurisdictions": ["全國"],
  "reasoning": "規劃理由"
}

規則：
- sub_queries：將複合問題拆解為 1-3 個獨立子查詢（若問題單純則只有1個）
- required_law_types：分析可能涉及的層次，從以下選擇：母法、子法、解釋函令、自治條例
  - 預設「母法」為基礎。若涉及執行、細項、標準等，加入「子法」。
  - 若涉及具體個案解釋，加入「解釋函令」。
- required_jurisdictions：選擇適用範圍
  - 務必包含「全國」作為基礎，以防止遺漏中央法規。
  - 若問題明確提到縣市，額外加入該縣市。
- reasoning：簡短解釋規劃邏輯（30字以內）"""


@dataclass
class QueryPlan:
    original_question: str
    sub_queries: List[str]
    required_law_types: List[str]
    required_jurisdictions: List[str]
    reasoning: str


class QueryPlanner:
    """Use LLM to analyse the user's question and produce a structured retrieval plan."""

    def __init__(self, llm: LLMProvider) -> None:
        self._llm = llm

    def plan(self, question: str, available_law_names: List[str]) -> QueryPlan:
        """Generate a QueryPlan for the given question.

        Args:
            question:            The user's original question.
            available_law_names: Names of laws currently ingested in the store.

        Returns:
            A QueryPlan with sub-queries, required law types, and jurisdictions.
        """
        law_list = "、".join(available_law_names) if available_law_names else "（無）"
        user_msg = (
            f"目前系統中已收錄的法規：{law_list}\n\n"
            f"使用者問題：{question}"
        )

        raw = self._llm.complete(
            system=_PLANNER_SYSTEM_PROMPT,
            user=user_msg,
            max_tokens=512,
            temperature=0.0,
        )

        return self._parse(question, raw)

    def _parse(self, question: str, raw: str) -> QueryPlan:
        """Parse the LLM JSON response into a QueryPlan, with safe fallback."""
        # Strip markdown code fences if present
        cleaned = re.sub(r"```(?:json)?\s*|\s*```", "", raw).strip()
        try:
            data = json.loads(cleaned)
            return QueryPlan(
                original_question=question,
                sub_queries=data.get("sub_queries") or [question],
                required_law_types=data.get("required_law_types") or ["母法"],
                required_jurisdictions=data.get("required_jurisdictions") or ["全國"],
                reasoning=data.get("reasoning", ""),
            )
        except (json.JSONDecodeError, TypeError):
            # Fallback: treat the whole question as a single sub-query
            return QueryPlan(
                original_question=question,
                sub_queries=[question],
                required_law_types=["母法"],
                required_jurisdictions=["全國"],
                reasoning="規劃解析失敗，使用預設策略",
            )
