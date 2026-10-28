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
from domain_rules import COMPLEX_KEYWORDS, norm_law_name
from retrieval import canon_source

# 置信度标定结论（scripts/calibrate_confidence.py，2026-08-03 实测）：正向 eval_set
# 28 例 top1 余弦全 ≥ 0.637；underspecified 3 例 0.611-0.634；chitchat 0.35-0.43；
# 但 out_of_kb（工伤保险条例 0.677 / 实施条例 0.747 等）检索到相近条文也高分——
# 置信度分无法单独区分「库外」，故库外由 REFUSE_MARKS + 源名存在性检查承担，
# 不再设置信度阈值分支（否则弱命中会误拒答"相近条文"的有效问题）。

# 库外硬信号：问题指向知识库明确未收录的规范层级/来源 → 不反问，直接诚实拒答
# （反问对这类问题无意义——信息已够，缺的是库本身）
REFUSE_MARKS = (
    "司法解释",
    "部门规章",
    "裁判倾向",
    "判决倾向",
    "某地法院",
    "判例",
    "典型案例",
    "指导意见",
    "实施细则",
    "公报案例",
)

# 法名抽取：书名号优先（《工伤保险条例》→ 精确指名）；裸名要求「X法」/「X条例」形态，
# 且「法」前一字不能是通用词尾（合/违/犯/司/执/办/律/做/看/说/写/想/无/非/方/设/定/的/据——
# "合法/违法/处理办法/法律/做法/看法/无法/非法/方法/设法/法定/遗产的法/根据法"等通用词误报，
# 真实案例：保险诈骗罪考题「无法」「非法」、遗产继承「法定/根据法定」均曾被误抽成法名致误拒答；
# "律师法"等真实法名不受影响。⚠ 该黑名单是持续维护的（中文组合开放，出现新误报即补；
# 更稳方案=用"在库法名"白名单校验候选，见 roadmap 已知限制）。
# 上限 60 而非 24：司法解释官方名实测 27 字（《最高人民法院关于审理民间借贷案件适用法律若干问题的规定》），
# 24 会把它整条漏掉——书引检查与口径①的"缺依据要显形"都会对它静默失效。上限只为防"整段被当名字"的极端输入。
_SOURCE_QUOTE_RE = re.compile(r"《([^》]{1,60}?)》")
_BOOK_TITLE_RE = re.compile(r"《[^》]{0,60}》")


def _strip_book_titles(text: str) -> str:
    """去掉书名号及其内容，只留正文——用于「规范层级词」硬信号判定。

    书名号内是**点名的具体法源**，归属口径①（`missing_sources`）处理，不能在这里
    按层级词整题拒答。实证（2026-10-25 六问考题）：《公司法解释三》逐字为
    「公·司·法·解·释·三」，内含连续子串「司法解释」，旧写法使所有引用公司法
    解释三的题目被误拒答，即使检索有命中。
    """
    return _BOOK_TITLE_RE.sub("", text or "")


_SOURCE_BARE_RE = re.compile(
    r"([一-龥]{2,12}(?<!合)(?<!违)(?<!犯)(?<!司)(?<!执)(?<!办)(?<!律)(?<!做)(?<!看)(?<!说)(?<!写)(?<!想)(?<!无)(?<!非)(?<!方)(?<!设)(?<!定)(?<!的)(?<!据)法(?!律)(?:实施条例)?|[一-龥]{2,10}?条例)"
)
# 裸名前缀修剪：介词/动词不属法名（「根据劳动合同法」→「劳动合同法」）
_PREP_PREFIX = ("根据", "按照", "依据", "依照", "参照", "适用", "违反", "基于")

# 疑问/通用修饰词：裸名正则会贪婪吞掉这些前缀致误抽法名（真实 case：法考题
# 「不管何种刑法学说」被整段抽成法名 → source_in_kb 判不在库 → 误拒答）。
# 抽取前从文本中剥离（书引《X法》不受影响），2026-08-04 架构级修复。
_QUERY_WORDS = ("不管何种", "何种", "什么", "这种", "那种", "哪种", "哪部", "啥")

# 裸名候选可信度（防误抽 → 误拒答，2026-08-04）：不在库的裸名，只有"长得像一部
# 具体法律的名称"才保留（触发拒答）；含连接/疑问词、或非规范词尾（"刑法和民法"/
# "合同纠纷适用…"）、或泛称法名（"行政法/刑事法"——法律大类总称非具体法）视为误抽
# 丢弃。书引（《X法》）不受此判定约束。
_JOIN_IMMUNE = ("和", "与", "或", "还是", "适用", "纠纷", "依据", "按照", "规定", "的", "不服")
# 泛称法名：法律大类总称，非具体法律（不在库且非用户点名某部法）
_GENERIC_LAWS = (
    "行政法",
    "刑事法",
    "民事法",
    "程序法",
    "实体法",
    "经济法",
    "诉讼法",
    "商法",
    "宪法学",
    "刑法学",
    "民法学",
)
# 机构/机关简称误抽（不是法律名称，2026-08-04 case：死刑复核法考题选项「最高法」被
# 抽成法名 → source_in_kb 判不在库 → 误拒答"未收录"，尽管刑诉法 246-252 已在库且检索
# 命中。同类第 3 次：毒品法场景词淹没 / 「不管何种刑法学说」/ 本次「最高法」——根因
# 都是非法律名称的短语被当成法名。机构简称是有限集合，显式免疫最稳。）
_ORG_SUSPECTS = (
    "最高法",
    "最高法院",
    "最高检",
    "最高人民检察院",
    "高法",
    "高检",
    "人民法院",
    "检察院",
    "法院",
    "公安机关",
    "公安部",
    "司法局",
    "司法部",
)


def _plausible_law(name: str) -> bool:
    """裸名是否像一部具体法律的名称（误抽免疫）。"""
    for p in ("根据", "按照", "依据", "依照", "参照", "适用", "违反", "基于"):
        if name.startswith(p):
            name = name[len(p) :]
            break
    if any(b in name for b in _JOIN_IMMUNE + _QUERY_WORDS):
        return False
    if name in _GENERIC_LAWS:
        return False
    if name in _ORG_SUSPECTS:  # 机构简称（最高法/法院等）不是法律名称，触发拒答免疫
        return False
    if not (name.endswith("法") or name.endswith("条例") or name.endswith("法典")):
        return False
    return 2 <= len(name) <= 8


def extract_source_names(text: str) -> list[str]:
    """从问题中抽取疑似法名（书引优先，裸名去常见误报，简称归一为全称），供源名存在性检查。

    修复（2026-08-04）：裸名抽取前剥离疑问/通用修饰词（不管何种/什么/这种/哪种等）——
    否则正则贪婪把「不管何种刑法」整段当法名，source_in_kb 判不在库 → 误拒答（真实 case：
    正当防卫法考题）。书引（《X法》）精确不受影响。
    """
    t = text or ""
    out: list[str] = []
    for m in _SOURCE_QUOTE_RE.finditer(t):
        name = canon_source(m.group(1).strip())
        if name and name not in out:
            out.append(name)
    t_bare = t
    for q in _QUERY_WORDS:
        t_bare = t_bare.replace(q, "")
    for m in _SOURCE_BARE_RE.finditer(t_bare):
        name = m.group(1)
        for p in _PREP_PREFIX:
            if name.startswith(p):
                name = name[len(p) :]
                break
        name = canon_source(name)
        if name and name not in out:
            out.append(name)
    return out


# 具体法律场景词：命中任一即视为「有具体事实场景」，不算信息不足。
# 复用 COMPLEX_KEYWORDS（离婚/工伤/股权等既是高利害也是具体场景），另补通用场景词。
_TOPIC_WORDS = COMPLEX_KEYWORDS + (
    "欠",
    "借",
    "钱",
    "合同",
    "工资",
    "加班",
    "房租",
    "买房",
    "房子",
    "车",
    "事故",
    "受伤",
    "打人",
    "骂人",
    "赔偿",
    "起诉",
    "报警",
    "失业",
    "裁员",
    "辞退",
    "解雇",
    "社保",
    "公积金",
    "保险",
    "诈骗",
    "骗",
    "偷",
    "抢",
    "抵押",
    "担保",
    "辞职",
    "退休",
    "物业",
    "租赁",
    "违约",
    "货款",
    "借款",
    "债务",
    "股份",
    "举报",
    "投诉",
    "仲裁",
    "法院",
    "律师",
    "拘留",
    "判刑",
    "坐牢",
    "犯罪",
    "罚款",
    "扣工资",
    "拖欠",
    "分手",
)

# 信息不足信号：指代不明开头 / 指代短语 / 泛咨询 / 宽泛问。
# 2026-10-25：「怎么办 / 怎么处理」从宽泛问里移除——口语化测评（59 题）实测 4 题
# 因「场景描述 + 怎么处理」被误判信息不足（如「耕地上擅自建房会被怎么处理」）。
# 这两句是中文里最常见的具体求助句式，本身不代表缺事实；保留的合法性问句
# （合法吗/违法吗/违反第几条/能告吗）仍能覆盖「这个合法吗」这类真模糊问法。
_UNDERSPEC_RE = re.compile(
    r"^(这个|那个|它|他|她|他们|这样|这种|那样|那种|这些|那些|该)"
    r"|(这样|这种|那样|那种)(做|干|处理)"  # 指代式问法（动词必须出现，避免「这种情况」误判）
    r"|^我想(咨询|问|请教|了解一下)"
    r"|(合法吗|犯法吗|违法吗|违反第几条|能告吗|能不能告|算不算(违法|犯罪))[吗呢？?]*$"
)

# 回溯式追问（2026-10-26）：「我前面问的是什么情况？」「刚才说到哪了？」
# 这类句子**必须依赖对话历史**才能答。有历史时由 memory.rewrite_query 改写成独立检索句；
# 空历史（新会话首问）时既无前文可回溯，检索又会命中一批噪声条文，只能视为信息不足去反问。
# 只在「无历史」时启用，避免误伤有历史的多轮追问；长度与自包含描述另行把关（见 is_history_referral）。
_HISTORY_REFERRAL_RE = re.compile(
    r"(?:前面|刚才|之前|上面|上一条|上一个|先前)[^，。！？]{0,6}(?:问|说|提|聊|讲)(?:的|过)?(?:是|啥|什么|哪|到哪)"
)


def is_history_referral(text: str) -> bool:
    """是否是「回指前文」的追问（且本身没带新事实）。仅凭文本判定，是否真有历史由调用方判。"""
    t = (text or "").strip()
    if not t or len(t) > 30:
        return False  # 长句通常自带案情描述，不该因含「之前」就被反问
    return bool(_HISTORY_REFERRAL_RE.search(t))


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


_QUOTED_LAW_SUFFIXES = ("法", "法典", "条例", "解释", "规定", "办法", "细则", "通则")


def _quoted_source_looks_like_law(name: str) -> bool:
    """书引语境下的"像不像法源名称"（口径①，2026-10-13）。

    与 `_plausible_law` **故意分开**：那个服务于裸名抽取（长串多半是误抽，故限长 2–8、只认 法/条例/法典）；
    书名号里是用户明确写下的名字——官方全称（《中华人民共和国合同法》，12 字）、
    司法解释名（《…的解释（一）》，带括号后缀）都必须算"点名了法源"，否则它们不在库时会被静默放过，
    而"缺依据要显形"正是口径①的落点。只把明显的文书/合同名排除（以 合同/协议/通知/书/函/状/意见 结尾）。
    """
    n = re.sub(r"[（(][^）)]*[）)]\s*$", "", (name or "").strip())
    if not n or n.endswith(("合同", "协议", "通知", "书", "函", "状", "意见")):
        return False
    return n.endswith(_QUOTED_LAW_SUFFIXES)


def missing_sources(text: str) -> list[str]:
    """点名了、像法源、但不在库的来源名（去重保序）——口径①：这些是"缺少必要依据"的那部分。

    只认书名号里的名字（`_SOURCE_QUOTE_RE`），且必须先过 `_plausible_law`：
    合同/文书名（《房屋租赁合同》）不算点名法源，不进本清单。
    """
    out: list[str] = []
    seen: set[str] = set()
    for m in _SOURCE_QUOTE_RE.finditer(text or ""):
        raw = m.group(1).strip()
        if not _quoted_source_looks_like_law(raw):
            continue
        canon = canon_source(raw)
        if R.source_in_kb(canon):
            continue
        if canon not in seen:
            seen.add(canon)
            out.append(raw)
    return out


# 《民法典》第一千二百六十条明列废止的九部法律（2021-01-01 起失效）。
# 只在「用户点名了这部法」时补一句确定性说明：提示词层面时灵时不灵（2026-10-26 实测
# 同一写法在《合同法》上生效、《婚姻法》上没生效），而废止与否是法律事实，必须 100% 稳定。
_REPEALED_BY_CIVIL_CODE = {
    "婚姻法": "《民法典》婚姻家庭编",
    "继承法": "《民法典》继承编",
    "民法通则": "《民法典》",
    "收养法": "《民法典》婚姻家庭编",
    "担保法": "《民法典》",
    "合同法": "《民法典》合同编",
    "物权法": "《民法典》物权编",
    "侵权责任法": "《民法典》侵权责任编",
    "民法总则": "《民法典》总则编",
}


def repealed_notice(text: str) -> str:
    """用户点名的法律已被《民法典》废止时返回一句说明，否则返回空串。

    命中用归一后的全名精确比对：不能用子串（「合同法」是「劳动合同法」的子串）。
    """
    for name in extract_source_names(text or ""):
        key = norm_law_name(name)
        if key in _REPEALED_BY_CIVIL_CODE:
            return f"《{key}》已于 2021 年 1 月 1 日废止，相关内容现由{_REPEALED_BY_CIVIL_CODE[key]}承接。"
    return ""


def named_out_of_kb(text: str) -> list[str]:
    """问题点名、但知识库确实没有的法源名（去重保序），只用于答复末尾加确定性说明。

    与 `missing_sources` 的区别：那个只认书名号、用于拒答判定；这个同时认裸名
    （「工伤保险条例里规定的工伤认定标准」没有书名号），且**不改变回答策略**——
    2026-08-04 的裁决是「有检索依据时不为裸名拒答」，这里只把「库里没有这部法」
    如实告诉用户，避免用户以为答复依据就是它点的那部法。
    """
    out: list[str] = []
    t = text or ""
    # 书引是精确点名，不受可信度约束；裸名要排除从句片段——「不服海事法院的裁定」曾被
    # 抽成《不服海事法》，真去答会让用户看到「知识库暂无《不服海事法》全文」（2026-10-26 实测）。
    quoted = {canon_source(m.group(1).strip()) for m in _SOURCE_QUOTE_RE.finditer(t)}
    for name in extract_source_names(t):
        if not _quoted_source_looks_like_law(name):
            continue
        if name not in quoted and any(b in name for b in _JOIN_IMMUNE + _QUERY_WORDS):
            continue
        if not R.source_in_kb(name) and name not in out:
            out.append(name)
    return out


def decide(
    intent: str,
    text: str,
    has_sources: bool,
    clarified_once: bool = False,
    *,
    has_history: bool = True,
) -> str:
    """回答策略：chat / direct / clarify / refuse。

    判定顺序（优先级从高到低）：
    1. 意图分流（chitchat → chat；非 legal_query → direct 走既有路径）
    2. 库外硬信号（司法解释/部门规章等层级词）→ refuse
    3. 书引《X法》= 用户确凿点名该部法，不在库 → refuse
       （用户明确写书名号指名，诚实拒答；即使检索命中相近条文也不硬答）
    4. 裸名法名：**有据（检索命中）→ 一律不因裸名不在库拒答**（2026-08-04 根治）。
       无据 → 保留"确凿点名的可信法名不在库"诚实拒答。
    5. 信息不足（指代不明/泛咨询/宽泛问）→ clarify（先于命中判定：没事实没法答准）
       空历史下的「回指前文」追问（我前面问的…/刚才说到哪）同样按信息不足处理：
       没有历史可回溯，检索只会捞到一批无关条文（2026-10-26 实测新会话首问）。
    6. 有据（命中）→ direct（弱命中也宁答，自检兜底）；无据 → refuse

    intent 由 classify_intent 给出；has_sources 为本轮是否检索命中；clarified_once
    为本会话是否已反问过（防死循环，由编排层维护）；has_history 为本会话是否有历史消息
    （默认 True 保持旧行为；多轮场景的回指由 memory.rewrite_query 处理，不走反问）。

    **根治说明（2026-08-04，同类第 3 次：毒品法场景词 /「不管何种刑法学说」/
    「最高法」机构简称）**：误拒答根因是把非法律名称的短语（机构简称/疑问词/通用词/
    连接短语）当法名，判"不在库"→ 拒答"未收录"，尽管知识库有相关条文且检索命中。
    裸名是否"像法名"靠启发式永远有漏网变体。根治：**有据时裸名一律不因不在库拒答**
    ——误抽短语几乎不可能命中在库法名集合，且检索有据时拒答"未收录"是伤害体验的
    误拒答，宁可基于库内相近条文尽力回答（agent 提示词第 7 条 + self_check 兜底），
    也不错误拒绝。书引《X法》是确凿点名，保留诚实拒答（无据场景）。
    """
    if intent == "chitchat":
        return "chat"
    if intent != "legal_query":
        return "direct"  # study_aid / cheating_request 走既有专门路径
    t = text or ""
    # 层级词硬信号只在正文里找：书名号内是点名法源，归口径①，见 _strip_book_titles
    if any(m in _strip_book_titles(t) for m in REFUSE_MARKS):
        return "refuse"
    # 书引《X》：口径①（2026-10-13 裁定）——**只触发法源核查，不整题拒答**。
    # ① 先问"像不像法源名称"：书名号里写合同/文书名（《房屋租赁合同》《解除通知》）不是点名某部法，
    #    不产生任何拒答（旧版把《…》一律当点名，导致合同审查题被整题拒答）；
    # ② 确实像法源、点名了、但不在库的：**有检索依据时不再拒答**，改把清单交调用方声明缺依据
    #    （见 missing_sources）；只在零检索命中时才维持诚实拒答——那才是"确实缺少必要依据"。
    quoted_missing = missing_sources(t)
    if quoted_missing and not has_sources:
        return "refuse"
    # 裸名：无据时保留"可信法名不在库"诚实拒答；有据时不拒答（根治误拒答）。
    if not has_sources:
        for name in extract_source_names(t):
            if not R.source_in_kb(name) and _plausible_law(name):
                return "refuse"
    if (detect_underspecified(t) or (not has_history and is_history_referral(t))) and not clarified_once:
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

# 诚实拒答模板：库未覆盖时说明（措辞命中 quality._HONEST_REFUSE_MARKS 的「未收录」，
# 保证若路径意外经过 self_check 也能 PASS）。2026-08-04 优化：不再一味拒绝——引导用户
# 补充法律领域/事实，主动邀请进入「基于库内相近条文尽力分析」的路径（更机智，非机械拒答）。
REFUSE_PROMPT = (
    "您的问题所涉法律条文暂未收录在当前知识库中，我暂时无法给出准确的条文依据。"
    "若您能补充：① 具体涉及的法律领域（如合同、劳动、侵权）；② 基本事实经过，"
    "我可以基于知识库中相关领域的条文尽力分析；您也可直接指明某部法律，我帮您核对是否收录。"
)
