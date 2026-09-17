"""R1-OB 判域输入扩展（2026-09-16 预注册：docs/preregistration-dept-guard-r1-optionB-20260916.md）。

三级确定性来源（无模型调用），任一级得出明确域即停：

1. **tier-1 案例域码直判**：评测/灰度通道携带的 `case_domain` ∈ {civil, criminal,
   administrative, special-maritime} → 直接返回（最高置信，消解 E04 型双域文本歧义）。
   生产链路该字段缺省 None → 本级跳过。
2. **tier-2 确定性文本拼接**：`domain_of_text(用户原始问题 + " " + issue 问句)`。
   E01 型 issue 问句零指示词时，用户原始问题携带域线索。
3. **mixed/零指示 → None → 不过滤**：与 R1 保守语义逐字一致（不引入激进兜底）。

边界纪律：
- `agent.dept_guard.domain_of_text` 与指示词表为判域**唯一真源，本模块零改动它们**——
  本模块只做「判域输入构造」。
- 非法 `case_domain`（非域表键）：入站层拒绝（HTTP 422 契约）；本函数第二层防御按
  「无域码」保守处理（不抛异常、不阻塞其余路径）。
"""

from __future__ import annotations

from agent.dept_guard import domain_of_text

# 合法域码集合：= dept_guard.PROC_LAW_DOMAIN 的值并集（域码全集的单一真源在此模块）。
VALID_CASE_DOMAINS = frozenset({"civil", "criminal", "administrative", "special-maritime"})


def resolve_domain(
    case_domain: str | None,
    user_question: str | None,
    issue_text: str | None,
) -> str | None:
    """R1-OB 三级判域输入构造：tier-1 域码 > tier-2 拼接 > None。"""
    if case_domain is not None and case_domain in VALID_CASE_DOMAINS:
        return case_domain  # tier-1：评测/灰度域码直判
    text = " ".join(part for part in (user_question or "", issue_text or "") if part).strip()
    if not text:
        return None
    return domain_of_text(text)  # tier-2（mixed/零指示 → None，与 R1 保守语义一致）
