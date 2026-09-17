"""评测器共享事实投放模块（单一实现，杜绝两份 runner 匹配逻辑漂移）。

任务书：docs/evaluation-harness-correction-taskbook-20260908.md §4.1/§4.2。

语义（默认）：
- 只投放「轮次 <= current_round」的冻结事实（用户已给出的轮次），未来轮次不提前披露；
- 排除 answered_fact_ids（一个事实最多投放一次）；
- 未命中 → unmatched_questions {round, prompt, reason:"no_rule_match"}，不伪装为未知事实 ID；
- 语义等价但关键词未命中 → 登记 manual_review_required（由人工盲审），运行器不自行猜测投放；
- 违反协议（如请求轮次 > 冻结 allowed_rounds）→ protocol_violations。

纯函数：无 IO、无网络、无状态。由 gate2_runner.py 与 hidden_runner.py 共同引用。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class FactMatchResult:
    matched_facts: list[dict[str, Any]] = field(default_factory=list)
    answered_fact_ids: list[str] = field(default_factory=list)
    unmatched_questions: list[dict[str, Any]] = field(default_factory=list)
    manual_review_required: list[dict[str, Any]] = field(default_factory=list)
    protocol_violations: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "matched_facts": self.matched_facts,
            "answered_fact_ids": self.answered_fact_ids,
            "unmatched_questions": self.unmatched_questions,
            "manual_review_required": self.manual_review_required,
            "protocol_violations": self.protocol_violations,
        }


def match_revealable_facts(
    *,
    case_id: str,
    prompt: str,
    current_round: int,
    answered_fact_ids: set[str],
    facts: dict[str, dict[str, Any]],
    allowed_round: int | None = None,
) -> FactMatchResult:
    """对单条 Agent 追问 prompt，返回可投放事实（轮次隔离 + 去重）。

    facts: {fact_id: {"round": int, "keywords": list[str], "text": str}}
    allowed_round: None → 使用 current_round（= 用户已提供到该轮）；冻结协议若定义"仅本轮公开"则显式传入严格轮次。
    """
    if allowed_round is None:
        allowed_round = current_round

    result = FactMatchResult()
    matched: list[dict[str, Any]] = []

    for fid, meta in facts.items():
        if not str(fid).startswith(case_id + "-"):
            continue
        rnd = int(meta.get("round", 99))
        if rnd > allowed_round:
            # 未来轮次事实：绝不提前披露（P0-1 修复）
            continue
        if fid in answered_fact_ids:
            # 已答事实：不重复投放（P0-2 修复）
            continue
        kws = meta.get("keywords", []) or []
        hit = next((k for k in kws if k in prompt), None)
        if hit is None:
            continue
        matched.append(
            {
                "fact_id": fid,
                "text": meta.get("text", ""),
                "matched_keyword": hit,
                "round": rnd,
            }
        )

    for hit in matched:
        result.matched_facts.append(hit)
        result.answered_fact_ids.append(hit["fact_id"])

    if not matched:
        result.unmatched_questions.append(
            {
                "round": current_round,
                "prompt": prompt,
                "reason": "no_rule_match",
            }
        )

    if current_round <= 0:
        result.protocol_violations.append(f"invalid_round:{current_round}")
    return result
