"""回答自检（M2）：纯函数、零 LLM，判定一次回答是否「合格」。

判定规则（与质量门禁/缓存写闸共用）：
- 非空、非过短（< MIN_ANSWER_LEN）。
- 引用校验通过：答案中所有《法名》第X条都必须在知识库（复用 citation_verify）。
- 检索命中（context_present=True）时必须含引用——轻量模型最常见的掉链子；
  但「诚实拒答」（库未覆盖）不算失败。
- 无命中（context_present=False）时若无诚实拒答措辞 → 「无据胡答」判失败。
- 无引用且命中含糊填充话（VAGUE_PHRASES）→ 含糊判失败。

自检不保证「引对题」（引在库≠引对条文），那是语义层，靠 full 门禁 + QA 人工沉淀兜底。
"""
import re
from dataclasses import dataclass

import query_understand
import retrieval as R
from domain_rules import MIN_ANSWER_LEN, VAGUE_PHRASES

# 诚实拒答信号（无命中场景的合理回答，不算失败）
_HONEST_REFUSE_MARKS = (
    "无法完整回答", "未覆盖", "未收录", "未提供相关", "没有提供相关", "未包含",
    "根据现有资料无法完整回答",
)


@dataclass
class Verdict:
    ok: bool
    reason: str = ""


def detect_vague(text: str) -> bool:
    """检测「无引用 + 含糊填充话」的含糊回答；有引用即不算含糊。"""
    t = text or ""
    if R.extract_citations(t):
        return False
    return any(p in t for p in VAGUE_PHRASES)


def _is_honest_refusal(text: str) -> bool:
    return any(m in text for m in _HONEST_REFUSE_MARKS)


def self_check(answer: str, context_present: bool, in_kb=None) -> Verdict:
    """自检。context_present = 本轮检索是否命中条文。

    in_kb 可注入（测试用假库）；默认 None → citation_verify 走真实知识库。
    """
    a = (answer or "").strip()
    if not a:
        return Verdict(False, "empty")
    if len(a) < MIN_ANSWER_LEN:
        return Verdict(False, "too_short")

    # 引用校验：不在库的引用 → 判失败
    bad = R.citation_verify(a, in_kb=in_kb)
    if bad:
        return Verdict(False, f"cite_bad:{len(bad)}")

    cites = R.extract_citations(a)
    # 含糊填充话检测提前：无引用 + 含糊词 → 无论命中与否都判含糊
    #（必须在前，否则会被 no_citation_while_hit / no_ground 分支吞掉而不可达）
    if not cites and detect_vague(a):
        return Verdict(False, "vague")

    if context_present and not cites:
        # 检索命中却无引用（排除诚实拒答——库有命中但模型坚持说没有，也算异常）
        if not _is_honest_refusal(a):
            return Verdict(False, "no_citation_while_hit")
    if not context_present and not cites:
        # 无命中：必须诚实拒答，否则是无据胡答
        if not _is_honest_refusal(a):
            return Verdict(False, "no_ground_but_answered")

    return Verdict(True, "")


# ---------------- 多选完整性（决策 8，2026-08-05） ----------------
# 兼容两种逐项判断格式（实测模型输出）：
# ① `X项判断：正确/错误`（实际输出格式，2026-08-05 eval 实测）
# ② `…【判断】正确/错误`（SYSTEM_STUDY 标准格式——回找上一【判断】后块内首个选项标号）
# 结论段（"A、B 正确"）不参与——避免与逐项判断重复/误读。格式不符 → 保守空集。
_VERDICT_RE = re.compile(r"([A-H])项?判断\s*[：:]\s*(正确|错误|不正确)")
_VERDICT_BLOCK_RE = re.compile(r"【判断】\s*(正确|错误|不正确)")
_OPT_LABEL_RE = re.compile(r"([A-H])[．.、:：]")


def _answer_declared_correct(answer: str) -> set[str]:
    """从回答抽取被判「正确」的选项字母。兼容 X项判断 / 【判断】两种格式。"""
    out: set[str] = set()
    t = answer or ""
    for m in _VERDICT_RE.finditer(t):  # 格式①：X项判断：正确
        if m.group(2) == "正确":
            out.add(m.group(1))
    for m in _VERDICT_BLOCK_RE.finditer(t):  # 格式②：【判断】正确 —— 块内首个标号
        if m.group(1) != "正确":
            continue
        prev = t.rfind("【判断】", 0, m.start())
        seg = t[(prev + 4) if prev >= 0 else 0 : m.start()]
        lm = _OPT_LABEL_RE.search(seg)
        if lm:
            out.add(lm.group(1))
    return out


def multi_incomplete(question: str, answer: str) -> bool:
    """多选完整性症状检测：多选题型（题干含 多选/哪些/正确的有）+ 回答只声明 1 个正确项。

    运行时无 ground truth，只能做症状检测——抓住用户报告的核心失败模式（多选题
    只给一个坚定答案）；不定项（可合法 1 项）与单选/unknown 不触发。确定性纯函数。
    """
    if query_understand.question_type(question) != "multi":
        return False
    n_opt = query_understand.option_count(question)
    return n_opt >= 2 and len(_answer_declared_correct(answer)) == 1
