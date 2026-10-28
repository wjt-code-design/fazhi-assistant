"""F5 claim 级引用核验（2026-10-27）。

把答案拆成「断言（claim）→ 所引条文」，逐条判断条文是否**直接支持**该断言。

边界（刻意写死）：
- 只读：不删引用、不改正文（与 G2「标注而非拦截」口径一致）。
- 不改 ``retrieval.citation_verify`` 的既有契约（其调用点依赖「返回库外引用列表」语义）。
- judge 可注入：默认只给**词面基线**（确定性、零 LLM），不作法律结论；
  LLM/NLI judge 由调用方注入，返回值 (supported, reason)。
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass

from retrieval import extract_citations

Judge = Callable[[str, str], tuple[bool | None, str]]

_SENTENCE_RE = re.compile(r"[^。！？!?\n]+[。！？!?\n]?")
_PUNCT_RE = re.compile(r"[\s，。；：、！？,.!?;:“”‘’（）()《》〈〉\-—…]+")
LEXICAL_THRESHOLD = 0.15

JUDGE_SYSTEM_PROMPT = (
    "你是法条引用核验器。给定一条断言和它引用的法条原文，判断该条文是否**直接支持**该断言。"
    '只输出一个 JSON 对象：{"supported": true/false, "reason": "不超过40字"}。'
    "判定标准：条文的规范内容必须能支撑断言的法律命题；仅主题相近、条号真实不算支持。"
    "若断言把特别条款当作一般规则、混入条文未规定的条件，或指向与案情不符的适用场景，判 false。"
)

# 候选 v2（2026-10-27）：不替换上面的生产默认，仅供“同集调参诊断”使用。
# 针对 30 对 AI 复核暴露的 8 条过严（省略例外/条件但核心成立、相邻条文条件、措辞模态）
# 与 1 条过松（排除式引用）修订；泛化效果须用随机样本 + 独立人类复核另验。
JUDGE_SYSTEM_PROMPT_V2 = (
    "你是法条引用核验器。给定一条断言和它引用的法条原文，判断该条文是否支持断言的核心法律命题。"
    '只输出一个 JSON 对象：{"supported": true/false, "reason": "不超过40字"}。'
    "判 true：条文能推出断言的核心结论；断言省略条文的例外、但书或程序前提，但未与条文冲突；"
    "多引用断言中，本条支撑断言中对应部分即可；同义改写未改变核心义务。"
    "判 false：条号错位（该命题的规则在另一条）；断言删去条文的关键要件"
    "（如负有个人责任、数额较大、造成严重后果）后作“一律/都/即”的绝对化表述；"
    "断言与条文相反；断言只是排除式引用（“本案不涉及 X 法”），条文不支撑任何本案命题；"
    "总则性/定义性条文（犯罪定义、基本原则、适用范围）不能单独支撑具体罪名、具体构成要件"
    "或具体法律后果，此类引用过于抽象，判 false。"
    "模态口径：应当/必须视为同义；只有核心义务被改反（必须↔可以、一律↔可能）才判 false；"
    "细节程序的“并/或”不改变核心命题时不算。"
)


@dataclass(frozen=True)
class ClaimCheck:
    claim: str
    literal: str
    source: str
    article: str
    article_found: bool
    article_text: str
    lexical: float
    supported: bool | None
    method: str
    reason: str


def split_sentences(answer: str) -> list[str]:
    return [sentence.strip() for sentence in _SENTENCE_RE.findall(answer or "") if sentence.strip()]


def _bigrams(text: str) -> set[str]:
    compact = _PUNCT_RE.sub("", text or "")
    return {compact[index : index + 2] for index in range(len(compact) - 1)}


def lexical_support(claim: str, article_text: str) -> float:
    """断言字符二元组被条文覆盖的比例（0–1）。只是词面基线，不是法律判断。"""
    claim_grams = _bigrams(claim)
    if not claim_grams:
        return 0.0
    article_grams = _bigrams(article_text)
    return round(len(claim_grams & article_grams) / len(claim_grams), 3)


def _article_text(document) -> str:
    return str(getattr(document, "page_content", "") or "")


def check(
    answer: str,
    lookup,
    judge: Judge | None = None,
    *,
    threshold: float = LEXICAL_THRESHOLD,
) -> list[ClaimCheck]:
    """逐 (断言, 引用) 对核验。lookup(source, article) -> Document 列表。"""
    results: list[ClaimCheck] = []
    for sentence in split_sentences(answer):
        citations = extract_citations(sentence)
        if not citations:
            continue
        for source, article, literal in citations:
            try:
                documents = list(lookup(source, article) or [])
            except Exception:  # noqa: BLE001 —— 取不到原文按未判定处理，不影响其他断言
                documents = []
            text = _article_text(documents[0]) if documents else ""
            lexical = lexical_support(sentence, text) if text else 0.0
            if not text:
                results.append(
                    ClaimCheck(sentence, literal, source, article, False, "", 0.0, None, "none", "库内未取到条文原文")
                )
                continue
            if judge is not None:
                supported, reason = judge(sentence, text)
                method = "judge"
            else:
                supported, reason = lexical >= threshold, f"词面覆盖 {lexical:.2f}"
                method = "lexical"
            results.append(
                ClaimCheck(sentence, literal, source, article, True, text, lexical, supported, method, reason)
            )
    return results


def parse_judge_response(text: str) -> tuple[bool | None, str]:
    """解析 judge 输出：优先 JSON，其次关键词兜底；解析失败返回 (None, 原文截断)。"""
    raw = (text or "").strip()
    match = re.search(r"\{.*\}", raw, re.S)
    if match:
        try:
            data = json.loads(match.group(0))
            supported = data.get("supported")
            if isinstance(supported, bool):
                return supported, str(data.get("reason", ""))[:80]
        except json.JSONDecodeError:
            pass
    if "不支持" in raw or "false" in raw.lower():
        return False, raw[:80]
    if "支持" in raw or "true" in raw.lower():
        return True, raw[:80]
    return None, raw[:80]
