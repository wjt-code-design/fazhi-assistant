"""多选答案抽取（纯逻辑，仅依赖 re——**不 import retrieval/BGE**）。

2026-08-05 从 quality 抽出：judge 基线脚本（eval_exam_professional.py）需要 multi_ok
判定，但 quality 模块级 import retrieval 会拉 BGE（~440MB），与后端双 BGE 触发 Windows
segfault（实测根因）。本模块零重量，quality/eval_exam/基线脚本共用同一份逻辑。
"""

import re

# 兼容三种逐项判断格式（实测模型/QA 语料输出）：
# ① `X项判断：正确/错误`（SYSTEM_STUDY LLM 输出）
# ② `…【判断】正确/错误`（SYSTEM_STUDY 标准格式——回找上一【判断】后块内首个选项标号）
# ③ `X. 内容 —— 正确`（qa_cache 的 glm 预生成答案格式，2026-08-05 实测）
# 结论段（"A、B 正确"）不参与——避免与逐项判断重复/误读。格式不符 → 保守空集。
_VERDICT_RE = re.compile(r"([A-H])项?判断\s*[：:]\s*(正确|错误|不正确)")
_VERDICT_BLOCK_RE = re.compile(r"【判断】\s*(正确|错误|不正确)")
# 格式③捕获 —— 后判定短语（≤20 字），按短语分类：
#   含"正确"且无"错误" → 正确（含"法理正确"/"依据不足（但法理正确）"等 hedge）
#   含"错误"/"不正确" → 错误；"无法判断"/"无法确定" → 中性（不计数）
_VERDICT_DASH_RE = re.compile(r"([A-H])[．.、:：]?[^。\n【]{0,50}——\s*([^。\n【]{0,20})")
_OPT_LABEL_RE = re.compile(r"([A-H])[．.、:：]")
# 结论段抽取（逐项判定格式太多样，结论是答案自己的总结，最鲁棒）：
# ① "正确的是 A、B、C" / "正确的选项为 A、B、C"（正确 后跟字母串）
# ② "A、B 说法正确"（字母串 后跟 正确）
_LETTER_RUN = r"[A-H](?:\s*[、，,和及与\s]*[A-H]){0,7}"
# 后缀**必选**（防"【判断】正确\n**B"跨段误匹配）：只匹配结论标记（正确的是/答案为/的选项为…）
# 允许选项被 ** 加粗包裹（markdown 结论常写成 **A、B、C**）
_CONCLUSION_RE = re.compile(r"正确(?:的是|的选项为|选项为|的答案为|答案为|项为|的有|项有|答案)[为是：:]?\s*[（(]?\*{0,2}(" + _LETTER_RUN + r")")
_CONCLUSION_PRE_RE = re.compile(r"\*{0,2}(" + _LETTER_RUN + r")\*{0,2}\s*(?:四个选项|所有选项|全部选项)?\s*的?(?:说法|表述|选项)?\s*(?:均|都|全部)?正确")


def _answer_declared_correct(answer: str) -> set[str]:
    """从回答抽取被判「正确」的选项字母。

    并集 = 逐项判定（三种格式）+ 结论段字母串。逐项判定给精度，结论给召回。
    """
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
    for m in _VERDICT_DASH_RE.finditer(t):  # 格式③：X. 内容 —— <判定短语>
        verdict = m.group(2)
        if "正确" in verdict and "错误" not in verdict:  # hedge（法理正确/依据不足但正确）也算
            out.add(m.group(1))
    for m in _CONCLUSION_RE.finditer(t):  # 结论：正确的是 A、B、C
        out |= set(re.findall(r"[A-H]", m.group(1)))
    for m in _CONCLUSION_PRE_RE.finditer(t):  # 结论：A、B 说法正确
        out |= set(re.findall(r"[A-H]", m.group(1)))
    return out


# 全选信号（multi_ok 兜底，2026-08-05 Step 1）：答案结论无字母（"全选"/"四项均正确"等表述）时的补抽。
# 仅当 未抽到任何字母结论 且 无显式错误判定 时，视为声明全部选项正确——避免把
# "逐项 C 错误…但结论全选" 的自相矛盾答案奖励为全对。
_FULL_SELECT_RE = re.compile(
    r"全选|全部正确|全部选项|四项均正确|四项都正确|四项说法均正确|均为正确"
    r"|所有选项[^。\n]{0,4}(?:均|都)?正确|四个选项[^。\n]{0,8}(?:均|都)?正确"
)


def _has_explicit_wrong(answer: str) -> bool:
    """是否显式判定了某选项「错误/不正确」（全选信号的抑制守卫）。"""
    t = answer or ""
    for m in _VERDICT_RE.finditer(t):
        if m.group(2) != "正确":
            return True
    for m in _VERDICT_BLOCK_RE.finditer(t):
        if m.group(1) != "正确":
            return True
    for m in _VERDICT_DASH_RE.finditer(t):
        if "错误" in m.group(2) or "不正确" in m.group(2):
            return True
    return False


def multi_ok(answer: str, options_verdict: dict | None) -> bool | None:
    """多选全选对判定：options_verdict 金标（{A: true/false}）→ 回答是否**恰好**列出全部正确项。

    语义 = 不漏选（true_letters ⊆ declared）**且**不误选（declared ⊆ true_letters），
    即 `declared == true_letters`——把金标为假的选项声明成"正确"（选多了）不算全选对
    （2026-08-05 diagnosing-bugs：原 `<=` 只查不漏选，误选假项也返回 True，基准被高估）。

    非多选（正确项 ≤1）→ None（不参与 multi_ok 统计）。确定性纯函数，零成本。
    """
    ov = options_verdict or {}
    true_letters = {k for k, v in ov.items() if v}
    if len(true_letters) <= 1:
        return None
    ans = answer or ""
    declared = _answer_declared_correct(ans)
    # 全选信号兜底（id10 类）：无字母结论 + 命中全选表述 + 无显式错误判定 → 视为全选。
    if _FULL_SELECT_RE.search(ans) and not declared and not _has_explicit_wrong(ans):
        declared |= set(ov.keys())
    return bool(declared == true_letters)
