"""实体法适用精度校验（T-A2，2026-09-17）：SUBJECT_TYPE_MISMATCH / CLAIM_DIRECTION_REVERSED。

位置 = writer 渲染循环（与 citation 检查同位；触发后走既有争点级部分交付/uncovered 流程，
**不进 verifier 终态、不进检索过滤层**——service.py:466 非 PASS 即终态失败，会违反 T-A5 P3）。
开关 = `settings.entity_precision_check`（**默认 False → writer 行为逐字不变**）。
数据源 = `backend/knowledge_base/law_annotations.json`（T-A1 38 + T-A2 31 = 69 条；
`_ta2.direction_subjects` 为 D3 授权扩展块，T-A1 四字段契约不变）。

D1 决策（Owner 2026-09-17 拍板：选项一）——仅确定性子集，实现期实测覆盖：
- 机制 A 拦：E01 个人独资企业法42、合伙企业法102（修正标注后）
- 机制 B 拦：E03 民法典804
- 残余 7 项（精确清单见测试与 design-prereg.md）：E04 劳动仲裁法6/消保法49（归 R1/R1-OB
  他域过滤线，实体法 49 需 domain_tags 机制）、E05 药品管理法128/131、E03 民法典801/802/807
  （需 domain_tags/争点匹配机制）——T-A5 批次实测后 Owner 再议。

fail-open 原则：标注缺失/条目无标注/类型词无法提取/句式不匹配 → 检查跳过（不拦）。
本模块函数绝不 raise。
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

_ANNOTATIONS_PATH = Path(__file__).resolve().parent.parent / "knowledge_base" / "law_annotations.json"

# 同义角色归一表（v1 预注册，覆盖金标案例角色词；未收录角色不归一 = 仅精确匹配）。
# 不同法律关系主角色不合并（定作人≠发包人、承揽人≠承包人——E03 定性矛盾正靠此区分）。
_ROLE_SYNONYMS: dict[str, tuple[str, ...]] = {
    "承包人": ("承包人", "施工单位", "装修公司", "施工方", "施工人", "承揽人"),
    "发包人": ("发包人", "建设单位", "业主"),
    "定作人": ("定作人", "定作方"),
    "承揽人": ("承揽人",),
    "劳动者": ("劳动者", "职工", "员工"),
    "用人单位": ("用人单位", "雇主"),
    "消费者": ("消费者", "买家", "购买者"),
    "经营者": ("经营者", "商家", "销售者", "卖家"),
    "债权人": ("债权人",),
    "债务人": ("债务人", "欠款人", "借款人"),
    "保证人": ("保证人",),
    "受害人": ("受害人", "被侵权人", "受害方"),
    "机动车方": ("机动车方", "机动车驾驶", "机动车一方"),
}

# subject_types 的「主体类型词」子集（其余为请求权角色词——机制 A 不用角色词比对，防 E01 型误杀）。
_SUBJECT_TYPE_WORDS = (
    "自然人",
    "法人",
    "公司",
    "个人独资企业",
    "合伙企业",
    "非法人组织",
    "消费者",
    "经营者",
    "劳动者",
    "用人单位",
    "机动车方",
    "行政机关",
    "平台",
)
# 主体类型等价族（公司 ⊆ 法人）：事实侧出现"公司"时，条文侧"法人"视为匹配。
_TYPE_EQUIV = {"公司": "法人"}

_REQUESTER_RE = re.compile(r"(?:要求|请求|责令|促使|让)\s*([一-龥]{2,10}?)(?=承担|返还|支付|赔偿|履行|退还|双倍|继续)")


def _norm_role(word: str) -> str | None:
    """角色词 → 规范角色名（同义表归一）；未收录返回 None。"""
    w = word.strip()
    for canonical, synonyms in _ROLE_SYNONYMS.items():
        if w in synonyms:
            return canonical
    return None


def _norm_roles(words: list[str]) -> set[str]:
    out: set[str] = set()
    for w in words:
        r = _norm_role(w)
        if r is not None:
            out.add(r)
    return out


def _type_words(words: list[str]) -> set[str]:
    """subject_types 中的主体类型词（角色词剔除）；公司→法人等价归一。"""
    out: set[str] = set()
    for w in words:
        if w in _SUBJECT_TYPE_WORDS:
            out.add(_TYPE_EQUIV.get(w, w))
    return out


@lru_cache(maxsize=1)
def _load_annotations() -> dict[tuple[str, str, str], dict]:
    """law_annotations.json → {(law_short, article_arabic, tail): annotation}；缺失/损坏 → {}（fail-open）。

    延迟导入 `_canonical_number`（单一真源在 writer；模块级导入会与本模块形成循环——
    writer 渲染循环 import 本模块）。
    """
    from .writer import _canonical_number

    try:
        data = json.loads(_ANNOTATIONS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    out: dict[tuple[str, str, str], dict] = {}
    for key, ann in (data.get("annotations") or {}).items():
        law, _, article = key.partition("#")
        try:
            arabic = _canonical_number(article[1 : article.index("条")])
        except (ValueError, IndexError):
            continue
        tail = article.split("之", 1)[1] if "之" in article else ""
        out[(law, arabic, _canonical_number(tail) if tail else "")] = ann
    return out


def _fact_type_domain(fact_texts: list[str]) -> set[str]:
    """案件事实文本中的主体类型域（词表类型词出现即收录；公司→法人等价扩展）。"""
    joined = "\n".join(fact_texts)
    domain: set[str] = set()
    for w in _SUBJECT_TYPE_WORDS:
        if w in joined:
            domain.add(_TYPE_EQUIV.get(w, w))
    return domain


def subject_type_mismatch(
    cited_keys: set[tuple[str, str, str]],
    fact_texts: list[str],
) -> bool:
    """机制 A：claim 所引条文的**主体类型词**与案件事实主体类型域完全不相交 → SUBJECT_TYPE_MISMATCH。

    fail-open：事实域为空 / 条文无标注 / 条文无类型词（仅角色词或空）→ False（跳过）。
    """
    domain = _fact_type_domain(fact_texts)
    if not domain or not cited_keys:
        return False
    annotations = _load_annotations()
    for key in cited_keys:
        ann = annotations.get(key)
        if not ann:
            continue
        type_words = _type_words(ann.get("subject_types") or [])
        if not type_words:
            continue  # 仅角色词/空 → 无法判主体域，跳过（fail-open）
        if type_words.isdisjoint(domain):
            return True
    return False


def direction_reversed(
    cited_keys: set[tuple[str, str, str]],
    issue_question: str,
) -> bool:
    """机制 B：impose_duty 条文的义务主体 ≠ 被索赔方、且被索赔方恰为该条权利主体 → 方向颠倒。

    被索赔方从 issue.question 的「要求/请求 … 承担|返还|支付|赔偿|退还」句式提取并归一。
    fail-open：无标注 / direction_subjects 为空 / 角色词未收录 / 句式不匹配 → False。
    """
    annotations = _load_annotations()
    m = _REQUESTER_RE.search(issue_question or "")
    if m is None:
        return False
    target = _norm_role(m.group(1))
    if target is None:
        return False
    for ref_key in cited_keys:
        ann = annotations.get(ref_key)
        if not ann or ann.get("claim_direction") != "impose_duty":
            continue
        t2 = ann.get("_ta2") or {}
        duty = _norm_roles(t2.get("duty_subjects") or [])
        right = _norm_roles(t2.get("right_subjects") or [])
        if not duty or not right:
            continue
        if target in right and target not in duty:
            return True
    return False
