"""有界候选的**纯选择**模块（票 C21-A Task 1）。

它只回答一个问题：在数量受限的候选窗内，**选中哪一条**（或明确不选），以及为什么。
它**不判资格**——`allowed` 由适配器用 `qa_eligibility`（唯一真源）判好后传进来；
它**不碰 SQL/向量/模型/日志**（只 import 标准库），因此可以被纯函数测试独立覆盖。

契约要点（设计合同 §3，逐条）：
- 窗口 8 + 1 哨兵：只对前 8 条做可服务选择；第 9 条**只判边界风险**，不作第 9 个服务项，
  前 8 条全拒时**不拿第 9 条兜底**。
- 分数：内部用**未舍入**有限分。`cosine` 沿 `1 - distance` 夹取 [0,1] 的口径在适配器做；
  本模块只校验「有限」——θ−NaN/Inf 一律不放行（`score_error`）。
- 同分组：以**最高合格分**为固定锚，与其差 ≤ 1e-6 的算「同等匹配」。**不得链式扩组**
  （不能把 0.9500000/0.9500009/0.9500018 三档并成一组）。
- 重复认定：只在最高合格同分组内比较**严格五元组** `question/answer/evidence/
  law_as_of_basis/fingerprint`（CRLF→LF，其余原样保留）。不同元组、必要字段缺失或
  无稳定身份 ⇒ 不选（`ambiguous` / `unstable_id`）。
- 确定重复且身份齐全时，按向量 doc id 的 Unicode 字典序、再按 candidate id 数值选最小项。
- 选中时**原对象返回**（不复制、不丢 QaHit 槽），reason 经独立结果传递。

`reason` 取值仅限有限枚举 `hit / empty / score_error / no_eligible / ambiguous /
unstable_id / window_boundary`。
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date

# 工程初值（设计合同 §3.1）：窗口 8 + 1 个边界哨兵；同分带 1e-6。
WINDOW = 8
TIE_EPSILON = 1e-6

REASONS = (
    "hit",
    "empty",
    "score_error",
    "no_eligible",
    "ambiguous",
    "unstable_id",
    "window_boundary",
)


@dataclass(frozen=True)
class Candidate:
    """一条原始候选：适配器实际传 `QaHit`（`hit`），选中必须**原对象**返回。

    `allowed` 是适配器用 `qa_eligibility` 判出的资格位（本模块不自行判资格）。
    `raw_score` 是**未舍入**分数。
    """

    hit: Mapping
    doc_id: str | None
    raw_score: float
    allowed: bool


@dataclass(frozen=True)
class Selection:
    """选择结果：选中的原对象（或 None）、归因 reason、窗内实际扫描条数。"""

    hit: Mapping | None
    reason: str
    scanned: int


def _normalize_newlines(value) -> str:
    """正文/问题/依据**只统一 CRLF 为 LF**，保留空格、标点、数字、否定词与引用顺序。"""
    if value is None:
        return ""
    return str(value).replace("\r\n", "\n").replace("\r", "\n")


def _valid_basis(value) -> bool:
    """基准日必须是有效的 `YYYY-MM-DD`（与 `retrieval_core.qa_provenance_verifiable` 同口径）。"""
    if not isinstance(value, str):
        return False
    try:
        return date.fromisoformat(value).isoformat() == value
    except ValueError:
        return False


def _identity_tuple(hit) -> tuple[str, str, str, str, str] | None:
    """严格五元组；必要字段缺失/非法返回 None（＝这一条不能参与重复认定）。

    前三者必须非空；基准日必须有效；`fingerprint` **键必须存在**（非选项题允许空值）。
    """
    if not isinstance(hit, Mapping):
        return None
    if "fingerprint" not in hit:
        return None
    question = _normalize_newlines(hit.get("question"))
    answer = _normalize_newlines(hit.get("answer"))
    evidence = _normalize_newlines(hit.get("evidence"))
    fingerprint = _normalize_newlines(hit.get("fingerprint"))
    if not question.strip() or not answer.strip() or not evidence.strip():
        return None
    if not _valid_basis(hit.get("law_as_of_basis")):
        return None
    return (question, answer, evidence, str(hit.get("law_as_of_basis")), fingerprint)


def _order_key(candidate: Candidate):
    """重复项的稳定排序键：doc id 的 Unicode 字典序优先，其次 candidate id 数值。

    两条都没有可用身份 ⇒ None（`unstable_id`）。带 doc id 的排在不带 doc id 的前面，
    使「无 candidate id 的真实种子」仍能被 doc id 稳定归属。
    """
    doc_id = candidate.doc_id
    cand_id = candidate.hit.get("qa_candidate_id") if isinstance(candidate.hit, Mapping) else None
    has_doc = isinstance(doc_id, str) and doc_id != ""
    has_cand = isinstance(cand_id, int) and not isinstance(cand_id, bool)
    if not has_doc and not has_cand:
        return None
    return (doc_id is None or doc_id == "", doc_id if has_doc else "", cand_id if has_cand else -1)


def _is_finite_score(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def _boundary_risky(items: Sequence[Candidate], best: float, boundary_unsafe: bool) -> bool:
    """边界哨兵是否构成风险。

    `boundary_unsafe` 是适配器显式给出的风险位；此外第 9 条（哨兵）分数落入所选最高分的
    同分带、或高于该带时同样判风险。哨兵计分异常 ⇒ 无法证明边界安全 ⇒ 保守判风险。
    窗口不足 9 条时不凭空制造风险。
    """
    if boundary_unsafe:
        return True
    if len(items) <= WINDOW:
        return False
    sentinel = items[WINDOW]
    if not _is_finite_score(sentinel.raw_score):
        return True
    return float(sentinel.raw_score) >= best - TIE_EPSILON


def select_candidate(
    candidates: Sequence[Candidate],
    *,
    threshold: float = 0.7,
    boundary_unsafe: bool = False,
) -> Selection:
    """在候选窗内做有界、可归因、稳定的选择（见模块 docstring）。

    不修改入参序列/`hit`；不复制 `hit`（选中时返回原对象）。
    """
    items = list(candidates)
    window = items[:WINDOW]
    scanned = len(window)
    if not window:
        return Selection(None, "empty", 0)

    finite = [_is_finite_score(c.raw_score) for c in window]
    selectable = [
        c for c, ok in zip(window, finite, strict=True) if ok and c.allowed and float(c.raw_score) >= threshold
    ]
    if not selectable:
        # 计分异常与「窗内无合格项」分键归因（不放行同一条腿）。
        reason = "no_eligible" if all(finite) else "score_error"
        return Selection(None, reason, scanned)

    best = max(float(c.raw_score) for c in selectable)

    # 边界风险优先拒绝：哨兵与所选最高分同带或更高时，窗内结论不能代表窗外。
    if _boundary_risky(items, best, boundary_unsafe):
        return Selection(None, "window_boundary", scanned)

    group = [c for c in selectable if best - float(c.raw_score) <= TIE_EPSILON]
    if len(group) == 1:
        return Selection(group[0].hit, "hit", scanned)

    tuples = [_identity_tuple(c.hit) for c in group]
    if any(t is None for t in tuples) or len(set(tuples)) != 1:
        # 同分组内有不同元组或必要字段缺失 ⇒ 无法证明同一答案版本 ⇒ 不选。
        return Selection(None, "ambiguous", scanned)

    keys = [_order_key(c) for c in group]
    if any(k is None for k in keys) or len(set(keys)) != len(keys):
        return Selection(None, "unstable_id", scanned)

    winner = min(zip(keys, group, strict=True), key=lambda pair: pair[0])[1]
    return Selection(winner.hit, "hit", scanned)
