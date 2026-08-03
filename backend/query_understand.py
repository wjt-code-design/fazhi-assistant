"""法律查询分解（query decomposition）：把自然语言查询解析成独立检索单元。

背景（2026-08-04 diagnosing-bugs → 架构改进）：长题干法考题整句检索时场景词淹没核心
罪名，关键条文掉出候选池 → agent 拿不到定罪条款。初次修复用「位置切片」（>60 字才触发），
解决了长题干，但架构上仍依赖 BGE 对罪名的语义匹配（余弦仅 0.72）+ top-2 保底参数，
对短复合查询/含法条引用查询无机制保证。

本模块把「位置切片」升级为「查询分解」：
  1. 原始整句（保底，不劣于旧版）
  2. 法条引用锚点（《X法》第X条 / 第X条）—— BM25 精确命中
  3. 具体罪名锚点（X罪，剥连接修饰）—— 定义该罪名的条文必被独立检索
  4. 长文本切片（>60 字：选项/句子）—— 防场景稀释

机制保证：锚点是「独立检索单元」，其 top-3 命中保底进结果（hybrid_retrieve），
不再依赖整句 BGE 余弦分。任何含罪名/法条引用的查询，无论长短，核心条文都不会丢。

为什么不用「法律概念词表」（如 COMPLEX_KEYWORDS）做锚点：该词表是复杂度分级用的
泛主题词（"行政复议"/"刑事"/"证据"），作为检索锚点过于泛化——独立检索 top-3 是
泛命中（复议法各条），强制保底会挤掉整句的措辞桥接召回（2026-08-04 实测：桥接
case "行政复议受案范围"召回"第十一条"被"行政复议"锚点稀释回归）。锚点只保留
「高区分度」的两类：法条引用、具体罪名。

纯逻辑模块，无 LLM 调用，无嵌入；分解结果由调用方（hybrid_retrieve）执行检索。
"""

import re

SLICE_MIN_CHARS = 60  # 超过该长度才做位置切片（短查询切片无收益且增开销）
SLICE_MAX = 5  # 切片段数上限（不含整句/锚点）

# 单元类型：强锚点（保底进结果）vs 弱单元（只扩大候选池）
KIND_ORIGINAL = "original"  # 整句
KIND_ANCHOR = "anchor"  # 法条引用/罪名——强锚点，top-3 保底
KIND_SLICE = "slice"  # 长文本切片段——只扩候选池，不保底

# 法条引用：《X法》第X条 或 独立"第X条"
_LAW_REF_RE = re.compile(r"《[^》]+》\s*第[零〇一二三四五六七八九十百千万]+条|第[零〇一二三四五六七八九十百千万]+条")

# 具体罪名：X罪（从"罪"字向前贪心，遇连接词/动宾/人称停用字截断）
_CRIME_RE = re.compile(r"([一-鿿]{2,8}罪)")
_CRIME_STOP = "构成了和与、的甲乙丙他她它我是我们你你们这那之其"  # 出现即截断
# 疑问词开头 → 非具体罪名（"什么罪/何罪/何种罪/哪罪"是提问，不是罪名）
_QUESTION_CRIME = ("什么罪", "何罪", "何种罪", "哪罪", "啥罪")

# 法考题信号：选项模式或"判断正误"措辞
_CHOICE_RE = re.compile(r"[A-D]：")
_JUDGE_MARKS = ("错误的是", "正确的是", "下列说法", "哪一项", "哪些说法")

# 中文标点切句
_SENT_SPLIT_RE = re.compile(r"[，。？；！、\n]")


def extract_law_refs(text: str) -> list[str]:
    """法条引用锚点：去重保序。"""
    return list(dict.fromkeys(_LAW_REF_RE.findall(text or "")))


def extract_crimes(text: str) -> list[str]:
    """具体罪名锚点：去重保序。遇连接/动宾/人称停用字截断，保留罪名核心。"""
    out: list[str] = []
    for m in _CRIME_RE.finditer(text or ""):
        w = m.group(1)
        i = len(w) - 1  # '罪' 的索引
        j = i
        while j > 0 and w[j - 1] not in _CRIME_STOP:
            j -= 1
        cand = w[j : i + 1]
        if (
            len(cand) >= 2
            and cand not in _QUESTION_CRIME
            and not any(x in cand for x in ("犯罪", "有罪", "无罪"))
            and cand not in out
        ):
            out.append(cand)
    return out


def _is_exam_question(text: str) -> bool:
    """法考题信号：选项模式或判断正误措辞。"""
    return bool(_CHOICE_RE.search(text)) or any(m in text for m in _JUDGE_MARKS)


def _split_by_choice(text: str) -> list[str]:
    """按选项切分：题干 + 每个选项独立成段。保留选项前缀（A：…）供检索定位。"""
    parts = re.split(r"(?=[A-D]：)", text)
    return [p.strip() for p in parts if len(p.strip()) >= 4][:SLICE_MAX]


def _split_by_sentence(text: str) -> list[str]:
    """按中文标点切句，取较长句（保留有信息量的），上限 SLICE_MAX。"""
    parts = [s.strip() for s in _SENT_SPLIT_RE.split(text)]
    out = [s for s in parts if len(s) >= 6]
    return out[:SLICE_MAX] if out else [text]


def decompose(query: str, concept_keywords: tuple = ()) -> list[tuple[str, str]]:
    """把查询分解为独立检索单元（去重保序），返回 [(text, kind), ...]。

    类型：
      original — 整句保底（永远首位）
      anchor   — 法条引用/罪名：强锚点，独立检索且 top-3 命中保底进结果
      slice    — 长文本切片段：只扩大候选池，不保底（避免单元过多稀释锚点保底）

    顺序：整句 → 法条引用 → 罪名 → 长文本切片。
    注意：不用概念词表做锚点（泛主题词独立检索会稀释整句桥接，见模块 docstring）。
    """
    query = (query or "").strip()
    if not query:
        return [(query, KIND_ORIGINAL)]
    units: list[tuple[str, str]] = []
    seen: set[str] = set()

    def add(s: str, kind: str) -> None:
        s = s.strip()
        if s and s not in seen:
            seen.add(s)
            units.append((s, kind))

    add(query, KIND_ORIGINAL)  # 1. 整句保底
    for ref in extract_law_refs(query):  # 2. 法条引用（强锚点）
        add(ref, KIND_ANCHOR)
    for crime in extract_crimes(query):  # 3. 罪名（强锚点）
        add(crime, KIND_ANCHOR)
    if len(query) > SLICE_MIN_CHARS:  # 4. 长文本切片（弱单元，只扩候选池）
        if _is_exam_question(query):
            segs = _split_by_choice(query)
        else:
            segs = _split_by_sentence(query)
        for s in segs:
            add(s, KIND_SLICE)
    return units
