"""部门法守卫：R1 检索池程序法过滤 + R1b 终稿程序法串台校验。

设计依据：docs/preregistration-dept-law-filter-r1-20260913.md（2026-09-13 预注册冻结）。

- R1（retrieval 侧）：Agent 逐争点检索后，把「他域专属程序法」条文从证据池剔除，
  防跨部门法混入（C05 实证：民事案检索召回行政/刑事诉讼法条文）。
- R1b（finalize 侧）：对终稿引用清单做同表判域检查，防生成期注入（writer 直接引用
  程序法，绕过检索池过滤——C05 型）。proc_misroute 为独立红线（不阻断 agent_completed，
  由评测侧对 FAIL 码判定）。

关键纪律：
- **实体法永不过滤**（民法典/刑法/劳动法等跨域适用是真实法律场景，如民刑分流 C10）。
- 判域指示词冲突或零指示 → mixed → **不过滤**（保守优先，行为与现状一致）。
- 域表只认「专属程序法」：民事诉讼法/刑事诉讼法/行政诉讼法/行政复议法/
  海事诉讼特别程序法（与预注册 §2 域表一致）。域映射：
    civil↔{民事诉讼法}；criminal↔{刑事诉讼法}；administrative↔{行政诉讼法,行政复议法}；
    special-maritime↔{海事诉讼特别程序法}。
  **仲裁法不在域表**（跨域通用程序法，约定仲裁属 civil 域场景由 writer/verifier 处理，
  不按程序法域表过滤——2026-09-14 深度检查修正 docstring，实现与预注册本就一致）。
- 本模块为纯函数 + settings 读取，无 IO；开关：
    settings.agent_dept_filter（R1）、settings.agent_proc_misroute_check（R1b）。
"""

from __future__ import annotations

import logging
import re
from collections.abc import Iterable

from settings import settings

logger = logging.getLogger("legal.agent")

# 专属程序法 → 所属域。一个法可属多域（程序法跨域适用时显式列出）。
PROC_LAW_DOMAIN: dict[str, set[str]] = {
    "民事诉讼法": {"civil"},
    "刑事诉讼法": {"criminal"},
    "行政诉讼法": {"administrative"},
    "行政复议法": {"administrative"},
    "海事诉讼特别程序法": {"special-maritime"},
}
_CN_PREFIX = "中华人民共和国"


def _norm_law_name(name: str) -> str:
    """法名归一：去「中华人民共和国」前缀（与 retrieval._norm_source 同口径）。

    writer 生成引用时全称/简称混用（E01 实测两种形态并存）；R1b 终稿串台判定
    必须容忍全称，否则《中华人民共和国行政诉讼法》漏检（2026-09-14 深度检查发现）。
    """
    name = (name or "").strip()
    return name[len(_CN_PREFIX) :] if name.startswith(_CN_PREFIX) else name


# 判域指示词（命中即贡献该域；多域命中→mixed→不过滤）
_CRIM_HINTS = ("刑事", "诈骗", "报警", "判刑", "犯罪", "入罪", "报案", "侦查")
_ADMIN_HINTS = ("行政", "政府", "处罚", "罚款", "听证", "复议", "许可")
_CIVIL_HINTS = ("民事", "借款", "买卖", "劳动", "合同", "消费", "赔偿", "时效", "起诉", "租赁", "仲裁")
_HINT_DOMAIN: dict[str, str] = {}
for _h in _CRIM_HINTS:
    _HINT_DOMAIN[_h] = "criminal"
for _h in _ADMIN_HINTS:
    _HINT_DOMAIN[_h] = "administrative"
for _h in _CIVIL_HINTS:
    _HINT_DOMAIN[_h] = "civil"
# 仲裁法特殊：约定仲裁属民事域，允许；仅"仲裁"出现不足以判 criminal。
_ART_FULL_RE = re.compile(
    r"《([^》]+)》\s*第\s*([零〇○一二三四五六七八九十百千万0-9]+)\s*条(之[零〇○一二三四五六七八九十百千万0-9]+)?"
)


def domain_of_text(text: str) -> str | None:
    """判域：命中多域或零域 → None（mixed，不过滤）。返回单一域字符串。"""
    hits = {_HINT_DOMAIN[w] for w in _HINT_DOMAIN if w in (text or "")}
    if len(hits) == 1:
        return next(iter(hits))
    return None


def filter_docs_by_domain(docs: Iterable[object], domain: str) -> list[object]:
    """R1：剔除他域专属程序法条文。docs 元素有 .metadata（Document）或 dict。

    保留：实体法（非专属程序法）、以及「属于当前域的程序法」（如 civil 域的民事诉讼法）。
    剔除：专属程序法且不在当前域（行/刑诉法出现在 civil 案 → 剔）。
    """
    kept: list[object] = []
    for doc in docs:
        src = _doc_source(doc)
        src_doms = PROC_LAW_DOMAIN.get(src or "") if src else None
        if src_doms is not None and domain not in src_doms:
            continue  # 他域程序法，剔除
        kept.append(doc)
    return kept


def _doc_source(doc: object) -> str | None:
    md = getattr(doc, "metadata", None)
    if isinstance(md, dict):
        src = md.get("source")
        return str(src) if src else None
    if isinstance(doc, dict):
        src = doc.get("source") or (doc.get("metadata") or {}).get("source")
        return str(src) if src else None
    return None


def final_draft_proc_misroute(answer: str, domain: str | None) -> list[str]:
    """R1b：抽取终稿引用清单，返回「他域专属程序法」条目的原文写法列表。空=无串台。

    仅当 domain 为单一明确域（非 None）时判定；mixed（None）→ 空（保守，不误报）。
    """
    if not answer or domain is None:
        return []
    bad: list[str] = []
    for m in _ART_FULL_RE.finditer(answer):
        src = _norm_law_name(m.group(1).strip("《》"))
        src_doms = PROC_LAW_DOMAIN.get(src)
        if src_doms is not None and domain not in src_doms:
            bad.append(m.group(0))  # 专属程序法，且不在当前域 → 串台
    return bad


def check_proc_misroute(answer: str, domain: str | None) -> bool:
    """R1b 开关门禁：返回 True=有串台（调用方应 fail-closed 或记红线）。"""
    if not settings.agent_proc_misroute_check:
        return False
    bad = final_draft_proc_misroute(answer, domain)
    if bad:
        logger.warning(
            "proc_misroute_detected",
            extra={"proc_misroute_citations": bad, "agent_domain": domain},
        )
        return True
    return False
