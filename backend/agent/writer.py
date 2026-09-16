"""Evidence-bounded drafting boundary for the legal agent.

The generator is untrusted. It receives a compact allowlisted payload and may
only propose structured claims. Stable provenance identifiers and all support
decisions are derived and checked by this module.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import unicodedata
from collections.abc import Mapping, Sequence
from enum import StrEnum
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from prompts import AGENT_WRITER_SYSTEM
from settings import settings

from .schemas import Fact, LegalAgentState, LegalValidity, SourceType

DraftSection = Literal["conclusion", "issue_analysis", "risk"]
_MAX_EVIDENCE_SNIPPET = 1200


class WriterStatus(StrEnum):
    READY = "READY"
    FAIL_SAFE = "FAIL_SAFE"


class WriterFact(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    fact_id: str = Field(min_length=1)
    statement: str = Field(min_length=1)
    source: SourceType
    source_ref: str = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)


class WriterEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    evidence_id: str = Field(min_length=1)
    source_ref: str = Field(min_length=1)
    source_type: SourceType
    snippet: str = Field(min_length=1, max_length=_MAX_EVIDENCE_SNIPPET)
    legal_validity: LegalValidity


class WriterIssue(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    issue_id: str = Field(min_length=1)
    question: str = Field(min_length=1)
    facts: tuple[WriterFact, ...] = ()
    evidence: tuple[WriterEvidence, ...] = ()
    unknown_facts: tuple[str, ...] = ()


class WriterPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    issues: tuple[WriterIssue, ...]
    resolved_conflict_ids: tuple[str, ...] = ()


class DraftClaim(BaseModel):
    """Server-accepted claim ledger entry; never parsed directly from the model."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    claim_id: str = Field(min_length=1)
    issue_id: str = Field(min_length=1)
    text: str = Field(min_length=1)
    evidence_ids: tuple[str, ...]
    fact_ids: tuple[str, ...]
    section: DraftSection


class DraftClaimCheck(BaseModel):
    """Immutable service-authored audit record, not a model support verdict."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    claim: str = Field(min_length=1)
    supported: bool
    evidence_ids: tuple[str, ...] = ()
    rationale: str = Field(min_length=1)


class DraftAnswer(BaseModel):
    """Structured draft. Rendering resolves only the accepted Claim ledger."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    conclusion: tuple[DraftClaim, ...] = ()
    issue_analysis: tuple[DraftClaim, ...] = ()
    risks: tuple[DraftClaim, ...] = ()
    missing_information: tuple[str, ...] = ()
    claim_checks: tuple[DraftClaimCheck, ...] = ()


class WriterResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status: WriterStatus
    draft: DraftAnswer | None = None
    reason_code: str
    dropped_claim_ids: tuple[str, ...] = ()


class DraftGenerator(Protocol):
    # 2026-09-13：writer 无重试/无回喂（Ticket 2），generate 不再有 feedback 关键字。
    def generate(self, *, payload: WriterPayload, system_prompt: str) -> object: ...


class _GeneratedClaim(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    local_id: str = Field(min_length=1)
    issue_id: str = Field(min_length=1)
    text: str = Field(min_length=1)
    evidence_ids: list[str]
    fact_ids: list[str]
    section: DraftSection

    @model_validator(mode="after")
    def unique_references(self) -> _GeneratedClaim:
        if len(self.evidence_ids) != len(set(self.evidence_ids)):
            raise ValueError("duplicate evidence reference")
        if len(self.fact_ids) != len(set(self.fact_ids)):
            raise ValueError("duplicate fact reference")
        return self


class _GeneratedDraft(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    claims: list[_GeneratedClaim]
    missing_information: list[str]

    @model_validator(mode="after")
    def unique_local_references(self) -> _GeneratedDraft:
        local_ids = [claim.local_id for claim in self.claims]
        if len(local_ids) != len(set(local_ids)):
            raise ValueError("duplicate local claim id")
        if len(self.missing_information) != len(set(self.missing_information)):
            raise ValueError("duplicate missing information")
        return self


class _WriterFailure(ValueError):
    def __init__(self, reason_code: str) -> None:
        self.reason_code = reason_code
        super().__init__(reason_code)


def _normalize_text(text: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", text).split())


def _canonical_hash(namespace: str, payload: Mapping[str, object]) -> str:
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return f"{namespace}_{hashlib.sha256(canonical.encode('utf-8')).hexdigest()}"


def derive_fact_id(issue_id: str, fact: Fact) -> str:
    return _canonical_hash(
        "fact",
        {
            "issue_id": issue_id,
            "statement": _normalize_text(fact.statement),
            "source": fact.source.value,
            "source_ref": fact.source_ref,
            "confidence": float(fact.confidence),
        },
    )


def derive_claim_id(
    issue_id: str,
    text: str,
    evidence_ids: Sequence[str],
    fact_ids: Sequence[str],
) -> str:
    return _canonical_hash(
        "claim",
        {
            "issue_id": issue_id,
            "text": _normalize_text(text),
            "evidence_ids": sorted(evidence_ids),
            "fact_ids": sorted(fact_ids),
        },
    )


def _evidence_payload_order(evidence) -> tuple:
    """V2-W4（2026-09-09）：payload 证据确定性重排序——生效成文法优先。

    原按 evidence_id（内容哈希）排序使有效法条证据随机沉底，模型倾向只绑前部
    证据（run-11 C02 实证：金标法条在证据表中但 draft 未绑定）。排序只影响模型
    输入分布，不影响任何校验：claim_id 绑定校验与顺序无关，同一次运行内
    state_digest 保持一致。回退方式：build_writer_payload 排序 key 改回
    lambda item: item.evidence_id 即可。
    """
    effective_statute = is_effective_statute(evidence)
    return (0 if effective_statute else 1, evidence.source_ref, evidence.evidence_id)


def is_effective_statute(evidence) -> bool:
    """单一真源（T5 审查收敛）：该证据是否可作"生效成文法"绑定（STATUTE 且 EFFECTIVE）。

    service 分流/回喂构造与本模块共享同一谓词；verifier.py 因冻结保留原实现（行为一致）。
    None（证据表中无此 id）→ False。
    """
    return (
        evidence is not None
        and evidence.source_type is SourceType.STATUTE
        and evidence.legal_validity is LegalValidity.EFFECTIVE
    )


def issue_is_deficient(issue_id: str, claims: Sequence[Any], evidence_by_id: Mapping[str, Any]) -> bool:
    """该 issue 是否**缺绑定**：无 claim，或其 claims 均未绑定（STATUTE 且 EFFECTIVE）证据。

    **单一真源（F5，2026-09-10 代码审查收敛）**：service 的逐争点覆盖率诊断
    （`_coverage_issue_facts`，2026-09-12）与本谓词共享同一实现；原先 service 侧另有一份
    同义实现（`_deficient_issue_ids`，已随 coverage 回喂循环一并删除——Ticket 2 后
    首次 verifier 非 PASS 即终态失败，不再重写分流）。证据来源各自保留
    （service 用 `state.evidence` 全局视图、writer 用 per-issue 证据视图），只统一**谓词**。
    `verifier.py` 因冻结保留原实现（口径一致，执行书 T0 红线）。
    """
    issue_claims = [claim for claim in claims if claim.issue_id == issue_id]
    if not issue_claims:
        return True
    return not any(
        is_effective_statute(evidence_by_id.get(evidence_id))
        for claim in issue_claims
        for evidence_id in claim.evidence_ids
    )


def desensitize_unknown_fact(statement: str) -> str:
    """把未决事实里的**数字型 token** 替换为中性表述（代码审查 B，2026-09-15）。

    为什么：numeric 失败的唯一剩余形态是 `from_unknown_facts` —— 模型在条件化论述里复述
    未决事实的数字（实测"三十日"/"一个月"/"十二个月"），而这些数字按纪律不可作为依据
    （未决事实不能绑 fact_id），于是被正确拒绝、整轮失败。让 payload 里**没有这些数字**，
    模型就无从复述。

    口径：**与 `numeric_tokens` 同一套 pattern**（日期/金额/百分比/期限，最后 ASCII 数字兜底），
    以保证 ``numeric_tokens(desensitize(x)) & numeric_tokens(x) == set()``（有单测钉住）。
    只处理数字型 token；**无单位的序数词（如"两次"）不在该口径内**，故不动 —— 避免过度脱敏
    损失语义（案件核心表述应保留）。

    替换词按**语义类型**给中性表述，尽量保留句子可读性与语义框架，且**不引入新事实**。

    ⚠️ **不做整体 NFKC 归一化**（2026-09-15，被单测抓到的实现缺陷）：那会把全角问号/括号等
    一并改成半角，既制造无谓 diff，又会**破坏 missing_information 的逐字来源校验**
    （`_render_once` 要求模型输出的缺失信息逐字来自 payload 的 unknown_facts；
    payload 若被改写，模型复述原文反倒不匹配 → 反而制造新的失败形态）。
    故改为**只替换 pattern 匹配到的片段**（`re.sub` 天然保留非匹配部分逐字不变）。
    所用 pattern 本身已同时覆盖全角与半角数字（`[0-9０-９]` 与 `\\d`）。
    """
    desensitized = statement
    # ⚠️ 替换词不得含 verifier 的 _OVERCONFIDENT_MARKERS（"一定/必然/绝对/保证胜诉/100%"）：
    # 初版用"一定期限/一定比例" ⇒ 模型忠实复述脱敏文本时"一定"命中违禁词表 →
    # OVERCONFIDENT_WORDING 整轮失败（1e6/1e8 实测；2026-09-16 修正归因：那两次失败
    # 不是模型文风，而是本函数替换词与词表冲突——B 与文风检查互相作用的回归）。
    # 有跨模块契约测试钉住（脱敏输出 ∩ 违禁词表 == 空）。
    for pattern, replacement in (
        (_DATE_RE, "相关日期"),
        (_AMOUNT_RE, "相应金额"),
        (_PERCENT_RE, "相应比例"),
        (_DURATION_RE, "法定期限"),
    ):
        desensitized = pattern.sub(replacement, desensitized)
    return _ASCII_NUMBER_RE.sub("若干", desensitized)


def writer_unknown_facts(issue: Any, *, desensitize: bool) -> tuple[str, ...]:
    """该争点进 writer payload 的未决事实文本（脱敏开关在此收口，便于单测与审计）。"""
    statements = tuple(item.statement for item in issue.unknown_facts)
    if not desensitize:
        return statements
    return tuple(desensitize_unknown_fact(statement) for statement in statements)


def build_writer_payload(state: LegalAgentState) -> WriterPayload:
    issue_ids = [issue.issue_id for issue in state.issues]
    if not issue_ids or len(issue_ids) != len(set(issue_ids)):
        raise _WriterFailure("STATE_INTEGRITY_FAILURE")

    evidence_payloads: dict[str, dict[str, Any]] = {}
    evidence_by_id = {}
    for evidence in state.evidence:
        payload = evidence.model_dump(mode="json")
        existing = evidence_payloads.get(evidence.evidence_id)
        if existing is not None and existing != payload:
            raise _WriterFailure("STATE_INTEGRITY_FAILURE")
        evidence_payloads[evidence.evidence_id] = payload
        evidence_by_id[evidence.evidence_id] = evidence

    linked_by_issue: dict[str, set[str]] = {issue_id: set() for issue_id in issue_ids}
    for observation in state.observations:
        if observation.issue_id not in linked_by_issue:
            raise _WriterFailure("STATE_INTEGRITY_FAILURE")
        if not set(observation.evidence_ids).issubset(evidence_by_id):
            raise _WriterFailure("STATE_INTEGRITY_FAILURE")
        if observation.status != "succeeded":
            continue
        linked_by_issue[observation.issue_id].update(observation.evidence_ids)

    conflict_ids: set[str] = set()
    for conflict in state.conflicts:
        if conflict.conflict_id in conflict_ids:
            raise _WriterFailure("STATE_INTEGRITY_FAILURE")
        conflict_ids.add(conflict.conflict_id)
        if conflict.issue_id not in linked_by_issue:
            raise _WriterFailure("STATE_INTEGRITY_FAILURE")
        if not set(conflict.evidence_ids).issubset(evidence_by_id):
            raise _WriterFailure("STATE_INTEGRITY_FAILURE")

    issues: list[WriterIssue] = []
    seen_fact_payloads: dict[str, dict[str, object]] = {}
    for issue in state.issues:
        facts: list[WriterFact] = []
        for fact in issue.facts:
            if fact.source is SourceType.INFERENCE:
                continue
            fact_id = derive_fact_id(issue.issue_id, fact)
            payload = fact.model_dump(mode="json")
            existing = seen_fact_payloads.get(fact_id)
            if existing is not None and existing != payload:
                raise _WriterFailure("STATE_INTEGRITY_FAILURE")
            seen_fact_payloads[fact_id] = payload
            facts.append(
                WriterFact(
                    fact_id=fact_id,
                    statement=fact.statement,
                    source=fact.source,
                    source_ref=fact.source_ref,
                    confidence=float(fact.confidence),
                )
            )
        linked_evidence = tuple(
            WriterEvidence(
                evidence_id=evidence.evidence_id,
                source_ref=evidence.source_ref,
                source_type=evidence.source_type,
                snippet=evidence.snippet[:_MAX_EVIDENCE_SNIPPET],
                legal_validity=evidence.legal_validity,
            )
            for evidence in sorted(
                (evidence_by_id[evidence_id] for evidence_id in linked_by_issue[issue.issue_id]),
                key=_evidence_payload_order,
            )
        )
        issues.append(
            WriterIssue(
                issue_id=issue.issue_id,
                question=issue.question,
                facts=tuple(facts),
                evidence=linked_evidence,
                unknown_facts=writer_unknown_facts(issue, desensitize=settings.agent_writer_desensitize_unknown_facts),
            )
        )

    resolved_conflicts = tuple(sorted(conflict.conflict_id for conflict in state.conflicts if conflict.resolved))
    return WriterPayload(issues=tuple(issues), resolved_conflict_ids=resolved_conflicts)


_ARTICLE_CITATION_RE = re.compile(
    r"《([^》]{1,24}?)》\s*(第[零〇○一二两三四五六七八九十百千万亿0-9０-９]+条"
    r"(?:之[零〇○一二两三四五六七八九十百千万亿0-9０-９]+)?)"
)

# 条号模式（**唯一真源**，2026-09-15 去重）：供链式续引复用。
_ARTICLE_PATTERN = (
    r"第[零〇○一二两三四五六七八九十百千万亿0-9０-９]+条"
    r"(?:之[零〇○一二两三四五六七八九十百千万亿0-9０-９]+)?"
)
# 续引链的**尾部**：分隔符（、，,和及与/括注/空白）+ 一个条号。
# B1（2026-09-15 代码审查）：原实现只用 `_CONTINUATION_CITATION_RE` 匹配「A条 sep B条」**一对**，
# 且 finditer 不重叠 → **3 连及以上只提取前 2 条**（实测：`第577、578、579条` → 只得到 577/578），
# 第 3 条起因无《》前缀而落空 ⇒ ① 编造的第 3 条既不进核验集也不判非规范（引用防线盲区）；
# ② 真实的第 3 条被判 UNSUPPORTED_CITATION。改为「命名引用 + 贪心吃链」后任意长度均可。
_CHAIN_TAIL_RE = re.compile(r"(?:[、，,和及与]|（[^（）]*）|\([^()]*\)|\s)*(" + _ARTICLE_PATTERN + r")")
_HASH_CITATION_RE = re.compile(
    r"([^\s《》#]{1,24}?(?:法|典|条例|规定|办法))#\s*"
    r"(第[零〇○一二两三四五六七八九十百千万亿0-9０-９]+条"
    r"(?:之[零〇○一二两三四五六七八九十百千万亿0-9０-９]+)?)"
)
_UNBRACKETED_CITATION_RE = re.compile(
    r"(?<![《\w])([一-龥]{1,20}?(?:法|典|条例|规定|办法))\s*"
    r"(第[零〇○一二两三四五六七八九十百千万亿0-9０-９]+条"
    r"(?:之[零〇○一二两三四五六七八九十百千万亿0-9０-９]+)?)"
)
_CONTINUATION_CITATION_RE = re.compile(
    r"《[^》]{1,24}?》\s*"
    r"第[零〇○一二两三四五六七八九十百千万亿0-9０-９]+条"
    r"(?:之[零〇○一二两三四五六七八九十百千万亿0-9０-９]+)?\s*"
    r"(?:[、，,和及与]|（[^（）]*）|\([^()]*\)|\s)+\s*"
    r"第[零〇○一二两三四五六七八九十百千万亿0-9０-９]+条"
    r"(?:之[零〇○一二两三四五六七八九十百千万亿0-9０-９]+)?"
)
_NUMBER_VALUE = r"(?:\d[\d,]*(?:\.\d+)?|[零〇○一二两三四五六七八九十百千万亿]+)"
_DATE_RE = re.compile(rf"({_NUMBER_VALUE})年({_NUMBER_VALUE})月({_NUMBER_VALUE})日")
_PERCENT_RE = re.compile(rf"(?:百分之({_NUMBER_VALUE})|({_NUMBER_VALUE})\s*[%％])")
_AMOUNT_RE = re.compile(rf"(?:人民币\s*)?({_NUMBER_VALUE})\s*(万|亿)?元")
_DURATION_RE = re.compile(rf"({_NUMBER_VALUE})(?:个)?(年|月|日|天|小时|分钟|秒)")
_ASCII_NUMBER_RE = re.compile(r"(?<![A-Za-z0-9])\d[\d,]*(?:\.\d+)?")

_CN_DIGITS = {
    "零": 0,
    "〇": 0,
    "○": 0,
    "一": 1,
    "二": 2,
    "两": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
}
_CN_UNITS = {"十": 10, "百": 100, "千": 1000, "万": 10_000, "亿": 100_000_000}


def _canonical_number(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).replace(",", "").replace("两", "二")
    if re.fullmatch(r"\d+(?:\.\d+)?", normalized):
        return normalized.lstrip("0") or "0"
    if not any(character in _CN_UNITS for character in normalized):
        digits = "".join(str(_CN_DIGITS[character]) for character in normalized)
        return str(int(digits or "0"))
    total = section = current = 0
    for character in normalized:
        if character in _CN_DIGITS:
            current = _CN_DIGITS[character]
            continue
        unit = _CN_UNITS[character]
        if unit < 10_000:
            section += (current or 1) * unit
        else:
            section = (section + current) * unit
            total += section
            section = 0
        current = 0
    return str(total + section + current)


def _canonical_article(article: str) -> tuple[str, str]:
    body = article[1 : article.index("条")]
    tail = article.split("之", 1)[1] if "之" in article else ""
    return _canonical_number(body), _canonical_number(tail) if tail else ""


def _canonical_law_name(raw: str) -> str:
    """法名归一化（去「中华人民共和国」前缀与尾部括注）——`canonical_citations` 与续引展开共用。"""
    source = raw.strip()
    if source.startswith("中华人民共和国"):
        source = source[len("中华人民共和国") :]
    return re.sub(r"（[^）]*）\s*$", "", source).strip()


def canonical_citations_in_order(text: str) -> list[tuple[str, str, str]]:
    """T2（2026-09-16）：`canonical_citations` 的**顺序视图**——同一模式集、同一归一，
    返回按正文首次出现顺序去重的列表（法律依据渲染的顺序真源；集合视图 = set(本列表)）。
    终止性与 `canonical_citations` 相同（pos 严格单调递增）。"""

    citations: list[tuple[str, str, str]] = []
    seen: set[tuple[str, str, str]] = set()

    def _add(key: tuple[str, str, str]) -> None:
        if key not in seen:
            seen.add(key)
            citations.append(key)

    normalized = unicodedata.normalize("NFKC", text)
    for pattern in (_ARTICLE_CITATION_RE, _HASH_CITATION_RE, _UNBRACKETED_CITATION_RE):
        for match in pattern.finditer(normalized):
            source = _canonical_law_name(match.group(1))
            article, tail = _canonical_article(match.group(2))
            _add((source, article, tail))
            pos = match.end()
            while True:
                chained = _CHAIN_TAIL_RE.match(normalized, pos)
                if chained is None:
                    break
                chained_article, chained_tail = _canonical_article(chained.group(1))
                _add((source, chained_article, chained_tail))
                pos = chained.end()
    return citations


def canonical_citations(text: str) -> set[tuple[str, str, str]]:
    """Extract deterministic law/article keys without loading the retrieval stack.

    2026-09-15（A 项 → B1 修复）：**任意长度续引链逐条提取**，使每一条都进入核验集合。
    实现：扫「命名引用」（带法名：`《法》第X条` / `法#第X条` / `法第X条`）后，
    **贪心吃掉紧随其后的「、第X条」链**，条号归属**同一法名**（另一法名另起链）。

    **终止性**（loop-termination-preflight）：吃链 while 以 `pos` 为指针，
    每轮必须消耗 ≥1 个条号（`_ARTICLE_PATTERN` 至少 3 字符）→ `pos` **严格单调递增**、
    上界 `len(text)` → **有限步必然终止**（不依赖"是否匹配到目标"，无外部 IO，无重试）。
    T2（2026-09-16）：集合视图 = `set(canonical_citations_in_order(text))`（单一解析真源）。
    """
    return set(canonical_citations_in_order(text))


def has_noncanonical_citation(text: str) -> bool:
    """非规范引用 = 法名缺书名号（`_UNBRACKETED_CITATION_RE`）。

    2026-09-15（A 项）：**续引形式不再判为非规范**——"《民法典》第577条、第578条"是正常的
    法律写作形式；改为由 `canonical_citations` **展开为逐条引用**后**独立核验**（核验强度不变）。
    原实现直接拒绝续引，属解析能力不足造成的误杀（实测占 citation 失败 2/2）。
    """
    normalized = unicodedata.normalize("NFKC", text)
    return _UNBRACKETED_CITATION_RE.search(normalized) is not None


def citation_unsupported_shape(text: str, bound_evidence_text: str, payload: Any, issue_id: str) -> str:
    """UNSUPPORTED_CITATION 的**形态类别**（只返回类别名，不含任何文本）。

    三类根因的修法完全不同，故必须分开计数：
    - `cited_from_other_issue`：引用的法条属于**别的争点**的证据 → 争点-证据绑定/planner 问题
    - `cited_in_pool_not_bound`：该法条在**池内**（本争点或全局可引用证据）但未绑定到本 claim
      → 模型**漏绑**（改 prompt/绑定可解）
    - `cited_not_retrieved`：池内查不到 → 模型**编造或凭常识引用**（改 prompt；防幻觉重点）
    """
    missing = canonical_citations(text) - canonical_citations(bound_evidence_text)
    if not missing:
        return "unclassified"
    own_pool = canonical_citations(_citable_pool_text(next(i for i in payload.issues if i.issue_id == issue_id)))
    if missing <= own_pool:
        return "cited_in_pool_not_bound"
    other_pool = canonical_citations(
        "\n".join(_citable_pool_text(issue) for issue in payload.issues if issue.issue_id != issue_id)
    )
    if missing <= other_pool:
        return "cited_from_other_issue"
    return "cited_not_retrieved"


def _zero_per_issue(payload: Any) -> dict[str, dict[str, int]]:
    return {issue.issue_id: {"proposed": 0, "accepted": 0, "dropped": 0} for issue in payload.issues}


def log_writer_summary(
    reason_code: str,
    *,
    payload: Any,
    generated: Any,
    accepted: Sequence[Any],
    dropped: Sequence[str],
    per_issue: Mapping[str, Mapping[str, int]],
    failing_issue_id: str | None = None,
    numeric_violation: Mapping[str, Any] | None = None,
    citation_violation: str | None = None,
) -> None:
    """逐次 writer 渲染的可归因摘要（**只记标识与计数，不含草稿文本**）。

    动机（2026-09-12 归因轮）：真实 C01 终态 4/4 争点 `claims == 0`，而归档无法区分
    「模型压根没产出 claim」与「产出后因 `evidence_ids` 为空被静默丢弃」；
    而真实失败是循环内 `_fail("NON_CANONICAL_CITATION")`，归档只留下 stage 字符串，
    既不知是哪条 claim、哪个争点触发。本摘要把这三件事都记下来，使下一次失败可直接归因。

    字段已在 `observability._ACCOUNT_FIELDS` 登记（未登记会被 JSON formatter 静默丢弃）。
    """
    logging.getLogger("legal.agent").log(
        logging.INFO if reason_code == "DRAFT_VALIDATED" else logging.WARNING,
        "writer_render_summary",
        extra={
            "agent_writer_summary": {
                "reason": reason_code,
                "claims_proposed": None if generated is None else len(generated.claims),
                "claims_accepted": len(accepted),
                "claims_dropped": len(dropped),
                "per_issue": [{"issue_id": issue_id, **counts} for issue_id, counts in sorted(per_issue.items())],
                "failing_issue_id": failing_issue_id,
                # 仅当数字校验真的触发时才有值；只含计数与 issue_id。
                "numeric_violation": None if numeric_violation is None else dict(numeric_violation),
                # 仅当引用校验触发时才有值；只含**形态类别名**（不含任何法条文本）。
                "citation_violation": citation_violation,
            }
        },
    )


def numeric_tokens(text: str) -> set[str]:
    normalized = unicodedata.normalize("NFKC", text)
    occupied = [False] * len(normalized)
    tokens: set[str] = set()

    def collect(pattern: re.Pattern[str], token_builder) -> None:
        for match in pattern.finditer(normalized):
            if any(occupied[match.start() : match.end()]):
                continue
            tokens.add(token_builder(match))
            occupied[match.start() : match.end()] = [True] * (match.end() - match.start())

    # 引用跨度整体占位（含**任意长度**续引链，2026-09-15 B1）：条号属于引用，不是可溯源数字。
    # 链式占位与 `canonical_citations` 同口径（同一 `_CHAIN_TAIL_RE`），否则第 3 条起
    # 会因未占位而被当成数字 token → 误报 UNSUPPORTED_NUMERIC_TOKEN。
    def _mark(start: int, end: int) -> None:
        occupied[start:end] = [True] * (end - start)

    for pattern in (_ARTICLE_CITATION_RE, _UNBRACKETED_CITATION_RE, _CONTINUATION_CITATION_RE):
        for match in pattern.finditer(normalized):
            _mark(match.start(), match.end())
            pos = match.end()
            while True:
                chained = _CHAIN_TAIL_RE.match(normalized, pos)
                if chained is None:
                    break
                _mark(pos, chained.end())
                pos = chained.end()
    collect(
        _DATE_RE,
        lambda match: "date:" + "-".join(_canonical_number(match.group(index)) for index in (1, 2, 3)),
    )
    collect(
        _PERCENT_RE,
        lambda match: f"percentage:{_canonical_number(match.group(1) or match.group(2))}",
    )
    collect(
        _AMOUNT_RE,
        lambda match: f"amount:{_canonical_number(match.group(1))}:{match.group(2) or '元'}",
    )
    collect(
        _DURATION_RE,
        lambda match: f"duration:{_canonical_number(match.group(1))}:{match.group(2)}",
    )
    for match in _ASCII_NUMBER_RE.finditer(normalized):
        if not any(occupied[match.start() : match.end()]):
            tokens.add(f"number:{_canonical_number(match.group(0))}")
    return tokens


def unsupported_numeric_tokens(text: str, bound_source_text: str) -> set[str]:
    """`text` 中不受 `bound_source_text` 支持的数字 token 集合（唯一真源）。"""
    return numeric_tokens(text) - numeric_tokens(bound_source_text)


def _citable_pool_text(issue: Any) -> str:
    """该争点**可被 claim 引用**的文本池（事实 + 证据），用于数字分桶。"""
    parts = [fact.statement for fact in issue.facts]
    for evidence in issue.evidence:
        parts.append(evidence.source_ref)
        parts.append(evidence.snippet)
    return "\n".join(parts)


def numeric_violation_buckets(unsupported: set[str], proposed: Any, payload: Any) -> dict[str, Any]:
    """把「未支持数字」按**可解释来源**分桶（只返回计数，不返回数值本身）。

    分桶口径（按优先级依次扣除，保证各桶之和 == `unsupported_total`）：
    - `in_own_issue_other_sources`：本争点其它事实/证据里有 → 模型**漏绑**（改 payload/提示词可解）
    - `in_other_issues`：属于**别的争点** → 模型无权引用（改 planner/争点-事实绑定才可解）
    - `from_unknown_facts`：来自本争点的**未决事实**（不可作为 fact_id 绑定）
    - `nowhere`：哪里都查不到 → 模型**编造**（改提示词）

    刻意**不**返回具体数值与文本：分桶已足以区分上述三种根因，无需把数值写进日志。
    """
    own_issue = next(issue for issue in payload.issues if issue.issue_id == proposed.issue_id)
    own_tokens = numeric_tokens(_citable_pool_text(own_issue))
    other_tokens = numeric_tokens(
        "\n".join(_citable_pool_text(issue) for issue in payload.issues if issue.issue_id != proposed.issue_id)
    )
    unknown_tokens = numeric_tokens("\n".join(own_issue.unknown_facts))

    in_own = unsupported & own_tokens
    remaining = unsupported - in_own
    in_other = remaining & other_tokens
    remaining -= in_other
    from_unknown = remaining & unknown_tokens
    nowhere = remaining - from_unknown

    return {
        "issue_id": proposed.issue_id,
        "unsupported_total": len(unsupported),
        "in_own_issue_other_sources": len(in_own),
        "in_other_issues": len(in_other),
        "from_unknown_facts": len(from_unknown),
        "nowhere": len(nowhere),
    }


def merge_draft_answers(drafts: Sequence[DraftAnswer]) -> DraftAnswer:
    """Ticket 2（2026-09-12）：服务端确定性合并各单争点草稿，不调用另一模型润色或重写。

    各 section 内保持传入顺序（调用方必须按 state.issues 原顺序传入单争点草稿）；
    missing_information 做稳定去重（保留首次出现）；claim_checks 恒为空，继续由 verifier 生成。
    """
    seen_missing: set[str] = set()
    missing_information: list[str] = []
    for draft in drafts:
        for item in draft.missing_information:
            if item not in seen_missing:
                seen_missing.add(item)
                missing_information.append(item)
    return DraftAnswer(
        conclusion=tuple(claim for draft in drafts for claim in draft.conclusion),
        issue_analysis=tuple(claim for draft in drafts for claim in draft.issue_analysis),
        risks=tuple(claim for draft in drafts for claim in draft.risks),
        missing_information=tuple(missing_information),
    )


class EvidenceBoundedWriter:
    def __init__(self, generator: DraftGenerator) -> None:
        self._generator = generator

    def render(self, state: LegalAgentState) -> WriterResult:
        """按 state.issues 顺序逐争点串行起草（单次生成，无重试）。

        生产由 service 串行调用 `render_issue`（逐争点前做取消检查）；本聚合方法是
        测试与对外便捷入口，保持与 `render_issue` 完全一致的单争点语义。
        """
        try:
            payload = build_writer_payload(state)
        except _WriterFailure as exc:
            return self._fail(exc.reason_code)
        drafts: list[DraftAnswer] = []
        dropped: list[str] = []
        for issue in payload.issues:
            result = self._render_single_issue(state, issue)
            if result.status is not WriterStatus.READY or result.draft is None:
                return result  # 首个失败即停：后续争点不调用
            drafts.append(result.draft)
            dropped.extend(result.dropped_claim_ids)
        return WriterResult(
            status=WriterStatus.READY,
            draft=merge_draft_answers(drafts),
            reason_code="DRAFT_VALIDATED",
            dropped_claim_ids=tuple(dropped),
        )

    def render_issue(self, state: LegalAgentState, issue_id: str) -> WriterResult:
        """Ticket 2：单争点渲染小接口——由 service 串行驱动（支持逐争点前的取消检查）。

        复用 build_writer_payload 的既有白名单/排序/完整性校验，再按 issue_id 切出
        单争点 payload（不复制 Fact/Evidence 转换逻辑）；单次 _render_once，无回喂重试。
        """
        try:
            payload = build_writer_payload(state)
        except _WriterFailure as exc:
            return self._fail(exc.reason_code)
        issue = next((item for item in payload.issues if item.issue_id == issue_id), None)
        if issue is None:
            return self._fail("STATE_INTEGRITY_FAILURE")
        return self._render_single_issue(state, issue)

    def _render_single_issue(self, state: LegalAgentState, issue: WriterIssue) -> WriterResult:
        """构造单争点 payload 并渲染一次。resolved conflicts 只保留本争点已解决的。"""
        resolved_conflict_ids = tuple(
            sorted(
                conflict.conflict_id
                for conflict in state.conflicts
                if conflict.resolved and conflict.issue_id == issue.issue_id
            )
        )
        return self._render_once(
            WriterPayload(issues=(issue,), resolved_conflict_ids=resolved_conflict_ids),
            state,
        )

    def _render_once(self, payload: WriterPayload, state: LegalAgentState) -> WriterResult:
        # 先声明，保证任何一条失败路径（含前置失败）都能记到完整上下文。
        generated: Any = None
        accepted: list[DraftClaim] = []
        dropped: list[str] = []
        per_issue: dict[str, dict[str, int]] = _zero_per_issue(payload)
        current_issue: str | None = None
        numeric_buckets: dict[str, Any] | None = None

        def _fail_here(
            reason_code: str,
            failing_issue_id: str | None = None,
            citation_violation: str | None = None,
        ) -> WriterResult:
            """失败统一出口（前置 + 循环内）：先记可归因摘要，再返回 FAIL_SAFE。

            failing_issue_id 缺省取当前正在校验的 claim 所属争点，因此循环内任意一条
            失败都会带出「是哪个争点触发的」。
            citation_violation：引用类失败的**形态类别**（不含文本），见 citation_*_shape。
            """
            log_writer_summary(
                reason_code,
                payload=payload,
                generated=generated,
                accepted=accepted,
                dropped=dropped,
                per_issue=per_issue,
                failing_issue_id=failing_issue_id if failing_issue_id is not None else current_issue,
                numeric_violation=numeric_buckets if reason_code == "UNSUPPORTED_NUMERIC_TOKEN" else None,
                citation_violation=citation_violation,
            )
            return self._fail(reason_code)

        try:
            raw = self._generator.generate(payload=payload, system_prompt=AGENT_WRITER_SYSTEM)
        except Exception:
            return _fail_here("GENERATOR_FAILURE")
        if isinstance(raw, BaseModel):
            raw = raw.model_dump(mode="python")
        try:
            generated = _GeneratedDraft.model_validate(raw)
        except (TypeError, ValidationError, ValueError):
            return _fail_here("MALFORMED_GENERATOR_OUTPUT")

        issues = {issue.issue_id: issue for issue in payload.issues}
        evidence_issues: dict[str, set[str]] = {}
        evidence_by_id: dict[str, WriterEvidence] = {}
        fact_issue: dict[str, str] = {}
        fact_by_id: dict[str, WriterFact] = {}
        unknown_statements: set[str] = set()
        for issue in payload.issues:
            unknown_statements.update(issue.unknown_facts)
            for evidence in issue.evidence:
                evidence_issues.setdefault(evidence.evidence_id, set()).add(issue.issue_id)
                evidence_by_id[evidence.evidence_id] = evidence
            for fact in issue.facts:
                fact_issue[fact.fact_id] = issue.issue_id
                fact_by_id[fact.fact_id] = fact

        if not {_normalize_text(m) for m in generated.missing_information}.issubset(
            {_normalize_text(u) for u in unknown_statements}
        ):
            # 2a'（2026-09-15）：比对**归一化**（NFKC + 空白折叠），与下方 claim 文本同一工具。
            # 修复前为逐字比对 → LLM 仅改空白/全角半角/标点形态即 fail-closed 拒答
            # （基线库实测 UNKNOWN_MISSING_INFORMATION 占失败 run 3/14）。
            # 来源要求**不放宽**：仍必须来自本 payload 的 unknown_facts 集合。
            return _fail_here("UNKNOWN_MISSING_INFORMATION")

        # 源点规范化（2a'，2026-09-15）：把 missing_information 落为 payload 中匹配到的
        # **unknown_fact 原文**——保证下游 verifier 的逐字子集/去重检查天然通过，
        # 不产生"两处各自归一化"的分叉（下游无需改动）。
        _canon = {_normalize_text(u): u for u in unknown_statements}
        canonical_missing = tuple(_canon[_normalize_text(m)] for m in dict.fromkeys(generated.missing_information))

        seen_claim_ids: set[str] = set()
        for proposed in generated.claims:
            if proposed.issue_id not in issues:
                return _fail_here("UNKNOWN_ISSUE_ID", proposed.issue_id)
            current_issue = proposed.issue_id
            per_issue[proposed.issue_id]["proposed"] += 1
            claim_id = derive_claim_id(
                proposed.issue_id,
                proposed.text,
                proposed.evidence_ids,
                proposed.fact_ids,
            )
            if claim_id in seen_claim_ids:
                return _fail_here("CLAIM_HASH_COLLISION")
            seen_claim_ids.add(claim_id)

            for evidence_id in proposed.evidence_ids:
                if evidence_id not in evidence_by_id:
                    if any(item.evidence_id == evidence_id for item in state.evidence):
                        return _fail_here("CROSS_ISSUE_EVIDENCE")
                    return _fail_here("UNKNOWN_EVIDENCE_ID")
                if proposed.issue_id not in evidence_issues[evidence_id]:
                    return _fail_here("CROSS_ISSUE_EVIDENCE")
                evidence = evidence_by_id[evidence_id]
                if (
                    evidence.source_type is SourceType.STATUTE
                    and evidence.legal_validity is not LegalValidity.EFFECTIVE
                ):
                    return _fail_here("INVALID_STATUTE_EVIDENCE")
            for fact_id in proposed.fact_ids:
                if fact_id not in fact_by_id:
                    # Ticket 2：单争点 payload 下，"已知 fact"全集必须取自 state（与上方
                    # evidence 全集检查同一口径）；payload.issues 已只含本争点。
                    known_fact_ids = {
                        derive_fact_id(issue.issue_id, fact) for issue in state.issues for fact in issue.facts
                    }
                    if fact_id in known_fact_ids:
                        return _fail_here("CROSS_ISSUE_FACT")
                    return _fail_here("UNKNOWN_FACT_ID")
                if fact_issue[fact_id] != proposed.issue_id:
                    return _fail_here("CROSS_ISSUE_FACT")

            bound_fact_text = "\n".join(fact_by_id[fact_id].statement for fact_id in proposed.fact_ids)
            bound_evidence_text = "\n".join(
                evidence_by_id[evidence_id].source_ref + "\n" + evidence_by_id[evidence_id].snippet
                for evidence_id in proposed.evidence_ids
            )
            bound_numeric_text = "\n".join((bound_fact_text, bound_evidence_text))
            unsupported = unsupported_numeric_tokens(proposed.text, bound_numeric_text)
            if unsupported:
                # 分桶归因（只记计数）：漏绑 / 跨争点无权引用 / 来自未决事实 / 编造 —— 改法各不相同。
                numeric_buckets = numeric_violation_buckets(unsupported, proposed, payload)
                return _fail_here("UNSUPPORTED_NUMERIC_TOKEN")
            if has_noncanonical_citation(proposed.text):
                # N1（2026-09-15 代码审查）：`has_noncanonical_citation` 的定义就是
                # `_UNBRACKETED_CITATION_RE` 命中，故此处形态**恒为** `unbracketed_law_name`
                # （原独立的 `citation_noncanonical_shape()` 是恒返回同值的常量包装，已删除）。
                # ⚠️ 若将来引入第二类非规范形态（如新增续引限制），必须恢复独立分类函数，
                # 否则该观测字段会再次失真。
                return _fail_here("NON_CANONICAL_CITATION", citation_violation="unbracketed_law_name")
            if not canonical_citations(proposed.text).issubset(canonical_citations(bound_evidence_text)):
                return _fail_here(
                    "UNSUPPORTED_CITATION",
                    citation_violation=citation_unsupported_shape(
                        proposed.text, bound_evidence_text, payload, proposed.issue_id
                    ),
                )
            if not proposed.evidence_ids:
                dropped.append(claim_id)
                per_issue[proposed.issue_id]["dropped"] += 1
                continue
            per_issue[proposed.issue_id]["accepted"] += 1
            accepted.append(
                DraftClaim(
                    claim_id=claim_id,
                    issue_id=proposed.issue_id,
                    text=_normalize_text(proposed.text),
                    evidence_ids=tuple(sorted(proposed.evidence_ids)),
                    fact_ids=tuple(sorted(proposed.fact_ids)),
                    section=proposed.section,
                )
            )

        if not accepted:
            # Ticket 2 决策 4：READY 但该争点没有任何被接受 claim（含全部被丢弃）→
            # 显式失败，不等 coverage loop 补写（该循环已删除）。
            return _fail_here("ISSUE_CLAIMS_MISSING", failing_issue_id=payload.issues[0].issue_id)

        draft = DraftAnswer(
            conclusion=tuple(claim for claim in accepted if claim.section == "conclusion"),
            issue_analysis=tuple(claim for claim in accepted if claim.section == "issue_analysis"),
            risks=tuple(claim for claim in accepted if claim.section == "risk"),
            # 2a'：存 canonical 原文（保序去重）——两条变体归一化后同源时只留一条，
            # 否则下游 verifier 的重复检查会误判 FABRICATED_MISSING_INFORMATION。
            missing_information=tuple(dict.fromkeys(canonical_missing)),
        )
        log_writer_summary(
            "DRAFT_VALIDATED",
            payload=payload,
            generated=generated,
            accepted=accepted,
            dropped=dropped,
            per_issue=per_issue,
        )
        return WriterResult(
            status=WriterStatus.READY,
            draft=draft,
            reason_code="DRAFT_VALIDATED",
            dropped_claim_ids=tuple(dropped),
        )

    @staticmethod
    def _fail(reason_code: str) -> WriterResult:
        return WriterResult(status=WriterStatus.FAIL_SAFE, reason_code=reason_code)
