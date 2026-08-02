"""回答策略决策（任务2：低置信反问）：回答前把问题分到 4 档策略，零 LLM、确定性。

- chat：闲聊（intent=chitchat）→ 直接聊，不检索不质检
- direct：检索强命中（top1 余弦 ≥ TH_LOW）→ 正常 RAG 回答
- clarify：检索弱/未命中 + 问题信息不足（指代不明/无具体场景/宽泛问）→ 反问澄清模板
- refuse：库外硬信号（司法解释/部门规章/裁判倾向）或已澄清过仍无据 → 诚实拒答模板

与 quality.self_check 的分工：self_check 是「回答后」兜底；本模块在「回答前」拦截
「信息不足却硬答」与「无效反问循环」——反问/拒答零 LLM 调用（省 token、措辞稳定、可评测）。
"""

import re

import retrieval as R
from domain_rules import COMPLEX_KEYWORDS

# 置信度标定结论（scripts/calibrate_confidence.py，2026-08-03 实测）：正向 eval_set
# 28 例 top1 余弦全 ≥ 0.637；underspecified 3 例 0.611-0.634；chitchat 0.35-0.43；
# 但 out_of_kb（工伤保险条例 0.677 / 实施条例 0.747 等）检索到相近条文也高分——
# 置信度分无法单独区分「库外」，故库外由 REFUSE_MARKS + 源名存在性检查承担，
# 不再设置信度阈值分支（否则弱命中会误拒答"相近条文"的有效问题）。

# 库外硬信号：问题指向知识库明确未收录的规范层级/来源 → 不反问，直接诚实拒答
#（反问对这类问题无意义——信息已够，缺的是库本身）
REFUSE_MARKS = (
    "司法解释", "部门规章", "裁判倾向", "判决倾向", "某地法院", "判例",
    "典型案例", "指导意见", "实施细则", "公报案例",
)

# 法名抽取：书名号优先（《工伤保险条例》→ 精确指名）；裸名要求「X法」/「X条例」形态，
# 且「法」前一字不能是通用词尾（合/违/犯/司/执/办/律/做/看/说/写/想——"合法/违法/
# 处理办法/法律/做法/看法"等通用词误报；"律师法"等真实法名不受影响）；「法」后不能跟
# 「律」（防「法律」双字词被从中间打断匹配成「……下法」）。
_SOURCE_QUOTE_RE = re.compile(r"《([^》]{1,24}?)》")
_SOURCE_BARE_RE = re.compile(
    r"([一-龥]{2,12}(?<!合)(?<!违)(?<!犯)(?<!司)(?<!执)(?<!办)(?<!律)(?<!做)(?<!看)(?<!说)(?<!写)(?<!想)法(?!律)(?:实施条例)?|[一-龥]{2,10}?条例)"
)
# 裸名前缀修剪：介词/动词不属法名（「根据劳动合同法」→「劳动合同法」）
_PREP_PREFIX = ("根据", "按照", "依据", "依照", "参照", "适用", "违反", "基于")


def extract_source_names(text: str) -> list[str]:
    """从问题中抽取疑似法名（书引优先，裸名去常见误报），供源名存在性检查。"""
    t = text or ""
    out: list[str] = []
    for m in _SOURCE_QUOTE_RE.finditer(t):
        name = m.group(1).strip()
        if name and name not in out:
            out.append(name)
    for m in _SOURCE_BARE_RE.finditer(t):
        name = m.group(1)
        for p in _PREP_PREFIX:
            if name.startswith(p):
                name = name[len(p) :]
                break
        if name and name not in out:
            out.append(name)
    return out

# 具体法律场景词：命中任一即视为「有具体事实场景」，不算信息不足。
# 复用 COMPLEX_KEYWORDS（离婚/工伤/股权等既是高利害也是具体场景），另补通用场景词。
_TOPIC_WORDS = COMPLEX_KEYWORDS + (
    "欠", "借", "钱", "合同", "工资", "加班", "房租", "买房", "房子", "车",
    "事故", "受伤", "打人", "骂人", "赔偿", "起诉", "报警", "失业", "裁员",
    "辞退", "解雇", "社保", "公积金", "保险", "诈骗", "骗", "偷", "抢",
    "抵押", "担保", "辞职", "退休", "物业", "租赁", "违约", "货款", "借款",
    "债务", "股份", "举报", "投诉", "仲裁", "法院", "律师", "拘留", "判刑",
    "坐牢", "犯罪", "罚款", "扣工资", "拖欠", "分手",
)

# 信息不足信号：指代不明开头 / 指代短语 / 泛咨询 / 宽泛问。
_UNDERSPEC_RE = re.compile(
    r"^(这个|那个|它|他|她|他们|这样|这种|那样|那种|这些|那些|该)"
    r"|(这样|这种|那样|那种)(做|干|处理)?"  # 指代式问法
    r"|^我想(咨询|问|请教|了解一下)"
    r"|(合法吗|犯法吗|违法吗|违反第几条|怎么办|怎么处理|能告吗|能不能告|算不算(违法|犯罪))[吗呢？?]*$"
)


def detect_underspecified(text: str) -> bool:
    """问题是否信息不足（指代不明 / 无具体场景 / 宽泛问）。"""
    t = (text or "").strip()
    if not t:
        return False
    if R.extract_citations(t):  # 引具体条号 → 信息充分
        return False
    if any(k in t for k in REFUSE_MARKS):  # 库外硬信号 → 走拒答，不算模糊
        return False
    if any(k in t for k in _TOPIC_WORDS):  # 具体场景词 → 信息充分
        return False
    if len(t) > 40:  # 长问默认有信息量
        return False
    return bool(_UNDERSPEC_RE.search(t))


def decide(
    intent: str,
    text: str,
    has_sources: bool,
    clarified_once: bool = False,
) -> str:
    """回答策略：chat / direct / clarify / refuse。

    判定顺序（优先级从高到低）：
    1. 意图分流（chitchat → chat；非 legal_query → direct 走既有路径）
    2. 库外硬信号（司法解释/部门规章等层级词）→ refuse
    3. 问题指名的来源不在库（如「工伤保险条例」「合同法」）→ refuse
       ——检索会命中相近条文且余弦分不低（标定实测 0.65-0.77），置信度分分不出库外
    4. 信息不足（指代不明/泛咨询/宽泛问）→ clarify（先于命中判定：没事实没法答准）
    5. 有据（命中）→ direct（弱命中也宁答，自检兜底）；无据 → refuse

    intent 由 classify_intent 给出；has_sources 为本轮是否检索命中；clarified_once
    为本会话是否已反问过（防死循环，由编排层维护）。
    """
    if intent == "chitchat":
        return "chat"
    if intent != "legal_query":
        return "direct"  # study_aid / cheating_request 走既有专门路径
    t = text or ""
    if any(m in t for m in REFUSE_MARKS):
        return "refuse"
    for name in extract_source_names(t):
        if not R.source_in_kb(name):
            return "refuse"
    if detect_underspecified(t) and not clarified_once:
        return "clarify"
    # 已反问过一次，或问题信息充分：有据直接答（含弱命中），无据诚实拒答（不再反问循环）
    return "direct" if has_sources else "refuse"


# 反问模板：信息不足时引导用户补充要素（零 LLM，措辞稳定）
CLARIFY_PROMPT = (
    "您的问题缺少一些关键信息，我无法给出准确的法律分析。请补充："
    "① 具体涉及的法律场景（如合同、离婚、劳动、侵权等）；"
    "② 双方当事人的基本情况；③ 已发生的具体行为或事实经过。"
    "信息越具体，我的分析越准确。"
)

# 诚实拒答模板：库未覆盖时直接说明（措辞命中 quality._HONEST_REFUSE_MARKS 的「未收录」，
# 保证若路径意外经过 self_check 也能 PASS）
REFUSE_PROMPT = (
    "您的问题涉及的内容未收录在当前知识库中，我无法给出准确的条文依据。"
    "建议咨询专业律师；也可向我提供更具体的问题（先告知涉及的法律领域与事实经过）。"
)
