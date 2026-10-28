"""生成层输出归一（确定性纯函数，2026-08-07 B1/B2/B3）。

替代前端"事后猜测性正则兜底"（stripUnprovidedHint / fixCurrencyTypos）：
后端生成层做主约束，前端只做展示。零 LLM、零 BGE、不 import retrieval，可单测。

- money_normalize：人民币 $ / ¥ 笔误归一为"元"（前缀/后缀/范围形）
- strip_unprovided_notes：删除"未检索到/建议核对原文"矛盾句（带库证据 source_in_kb）
- strip_internal_notes：删除"提供条文/检索范围/引用缺失"等内部流程话术（F3，2026-10-27）
- detect_conclusion_contradiction：检测"依据 X 条"与"X 条未提供"并存的结论矛盾（F4，2026-10-27）
"""

import re

from coverage_gate import article_number

# ---- 币种归一 ----
# 模型偶发把人民币"元"误写成 $（150-200$3 / $150 / 100$）。只处理"数字邻接 $/¥"；
# $ 后非数字（LaTeX $\neq$）不匹配；OUTPUT_FORMAT_RULE 已禁 LaTeX，此处仅兜底。
_MONEY_RANGE_RE = re.compile(r"(\d[\d,.]*)\s*[-~～至到]\s*(\d[\d,.]*)\s*[$¥]\s*\d*")
_MONEY_PREFIX_RE = re.compile(r"[$¥]\s*(\d[\d,.]*)")
_MONEY_SUFFIX_RE = re.compile(r"(\d[\d,.]*)\s*[$¥]\s*\d*")


def money_normalize(text: str) -> str:
    """人民币 $/¥ 笔误归一为"元"。范围形 150-200$3 → 150-200元（$ 后垃圾数字丢弃）。

    顺序：范围 → 后缀（数字后 $，如 100$3 → 100元）→ 前缀（$ 前无数字，如 $150 → 150元）。
    后缀必须先于前缀——"100$3" 若前缀先跑会命中 $3 → "1003元"（错）。
    """
    if not text:
        return text
    text = _MONEY_RANGE_RE.sub(r"\1-\2元", text)
    text = _MONEY_SUFFIX_RE.sub(r"\1元", text)
    text = _MONEY_PREFIX_RE.sub(r"\1元", text)
    return text


# ---- 省略书名的连续条号展开（B3 补充，2026-08-07；对抗审计 v2 #6 收紧）----
# 模型常输出"《民法典》第七百一十五条（...解释...）、第七百一十六条"——第二条省略书名，
# 前端标注/弹卡需书名。展开为《书名》第X条：存储一致、citation_grounding 抽取更准。
# 收紧：只展开「书名+条号+续接标点/括号+独立条号」的连续省略形式。原实现按句维护"最近书名"，
# 会把合同文本的条款号（"第九条 争议解决"）错补成《最近书名》，污染合同评估答案与引用统计。
_ART_CORE = r"(?:第[零〇○一二三四五六七八九十百千万0-9０-９]+条(?:之[一二三四五六七八九十百千万0-9０-９]+)?)"
# group1=前缀(含《X》条号+续接标点/括号/空白) group2=书名 group3=独立条号
_CONTIN_RE = re.compile(
    r"(《([^》]{1,24}?)》\s*" + _ART_CORE + r"\s*(?:[、，,和及与]|（[^（）]*）|\([^()]*\)|\s)*)"
    r"(" + _ART_CORE + r")"
)


def expand_citations(text: str) -> str:
    """把紧跟书名引用的省略条号展开为《书名》第X条（仅连续续接形式）。

    独立的合同条款号（"第九条 争议解决"）前面无书名续接，不展开；幂等，已展开重跑无变化。
    """
    if not text:
        return text
    prev = None
    while prev != text:
        prev = text
        text = _CONTIN_RE.sub(lambda m: f"{m.group(1)}《{m.group(2)}》{m.group(3)}", text)
    return text


# ---- 法律名+条号补书名号（2026-08-07）----
# 模型常写"刑法第23条"（省略《》），前端不标色、citation_grounding 抽不到《X》第N条。
# 知识库 source 名校验防误匹配（"本合同第三条"不命中）。
_COMMON_LAW_NAMES = (
    "劳动争议调解仲裁法",  # 长名在前，防子串误配（对抗审计 v2 #13：5 个补充组重点推送法律补入标注清单）
    "著作权法",
    "商标法",
    "专利法",
    "合伙企业法",
    "刑事诉讼法",
    "民事诉讼法",
    "行政处罚法",
    "行政复议法",
    "行政诉讼法",
    "劳动合同法",
    "治安管理处罚法",
    "消费者权益保护法",
    "道路交通安全法",
    "企业破产法",
    "社会保险法",
    "税收征收管理法",
    "反家庭暴力法",
    "民法典",
    "刑法",
    "劳动法",
    "保险法",
    "公司法",
    "证券法",
    "票据法",
    "宪法",
    "食品安全法",
    "产品质量法",
)


def expand_law_names(text: str) -> str:
    """把"法律名+第X条"（无书名号）补为《法律名》第X条（幂等：已有《》不动）。"""
    if not text:
        return text
    for name in _COMMON_LAW_NAMES:
        text = re.sub(
            r"(?<!《)" + re.escape(name) + r"(第[零〇○一二三四五六七八九十百千万0-9０-９]+条)",
            "《" + name + r"》\1",
            text,
        )
    return text


# ---- 矛盾句删除 ----
# 后端 prompt（SYSTEM_BASE #7）已不再要求模型写"建议核对原文"；此处是变体兜底，
# 带库证据：库内（漏召回表象）删句，库外（真未收录）保留诚实说明。
_UNPROVIDED_RE = re.compile(r"(未在本次检索中提供|未在知识库中检索到|未收录该法|建议核对原文|请核对条文原文)")


def strip_unprovided_notes(text: str, source_in_kb) -> str:
    """删除"未检索到/建议核对原文"矛盾句（带库证据）。

    source_in_kb: callable(source) -> bool，判某法是否在知识库。
    规则：句子含矛盾短语时——
      - 句中引用到的《X》有任一不在库 → 保留（真未收录的诚实说明）
      - 其余（在库 = 漏召回表象 / 无明确书名 = 纯噪音）→ 删除整句
    按句切分，只影响含矛盾短语的句子，不动正文。
    """
    if not text:
        return text
    sentences = re.split(r"(?<=[。！？!?\n])", text)
    kept = []
    for s in sentences:
        if not _UNPROVIDED_RE.search(s):
            kept.append(s)
            continue
        srcs = re.findall(r"《([^》]{1,24}?)》", s)
        if srcs and any(not source_in_kb(sx) for sx in srcs):
            kept.append(s)  # 引用真不在库的法 → 保留诚实说明
        # 否则删除（在库矛盾句 / 无书名噪音）
    return "".join(kept).strip()


# ---- 内部流程话术删除（F3，2026-10-27）----
# 事故样本：答案把"题目要求严格依据提供条文""未在提供条文中""补充依据（未在本次检索范围内，
# 条文存在于法律库）""存在引用缺失风险"等生成侧约束/检索侧状态写进用户可见正文。
# 与 strip_unprovided_notes 的分工：那个管"未检索到/建议核对"（带库证据决定删留）；
# 这个只管**流程元语言**，无库证据需求，确定性删除。
_INTERNAL_PAREN_RE = re.compile(
    r"[（(][^（）()\n]{0,240}"
    r"(?:提供条文|检索范围|引用缺失|未在提供|不在提供|条文存在于法律库)"
    r"[^（）()\n]{0,240}[）)]"
)
_INTERNAL_SENTENCE_RE = re.compile(
    r"(严格依据提供条文|题目要求[^。；！？\n]{0,12}条文|存在引用缺失风险|引用缺失风险|"
    r"未在提供条文中|不在提供条文中|未在本次检索范围内|条文存在于法律库|"
    r"需提供[^，。；！？\n]{0,40}原文|提供的检索条文中|提供的条文中|本次检索范围)"
)


def has_internal_notes(text: str) -> bool:
    """正文是否含内部流程话术（供流式路径检测：帧已吐出、无法回收，只能记日志/拦缓存）。"""
    return bool(text and (_INTERNAL_SENTENCE_RE.search(text) or _INTERNAL_PAREN_RE.search(text)))


def strip_internal_notes(text: str) -> str:
    """删除生成侧/检索侧内部话术（确定性、幂等；按句删除 + 括号内元语言先行剥离）。

    只删含流程元语言的句子/括号；含法条引用与实质分析的正文不动。
    """
    if not text:
        return text
    stripped = _INTERNAL_PAREN_RE.sub("", text)
    sentences = re.split(r"(?<=[。！？!?\n])", stripped)
    kept = []
    for sentence in sentences:
        if not sentence:
            continue
        if _INTERNAL_SENTENCE_RE.search(sentence) or sentence.strip() in {"补充依据", "补充依据："}:
            continue
        kept.append(sentence)
    out = "".join(kept)
    out = re.sub(r"[，；]{2,}", "，", out)
    out = re.sub(r"。\s*。", "。", out)
    out = re.sub(r"\n{3,}", "\n\n", out)
    return out.strip()


# ---- 结论与限定语矛盾检测（F4，2026-10-27）----
# 事故样本："依据《刑法》第二百三十四条"与"（未直接列出 234 条全文）"并存。
# 只做检测（返回被同时"依据"又"声明缺失"的条号），不改写正文；调用方决定记录/降级。
# 矛盾提示（F4，2026-10-27）：仅在整答出口追加。措辞刻意避开
# strip_unprovided_notes 的"建议核对原文/请核对条文原文"与 strip_internal_notes
# 的流程词，确保不会被二次清理。
CONTRADICTION_NOTE = "\n\n提示：结论与所引条文不一致，请以条文原文为准。"

_ARTICLE_IN_TEXT_RE = re.compile(r"(?:第)?([零〇一二两三四五六七八九十百千0-9]+)条")
_NEGATED_RE = re.compile(r"(?:未(?:直接)?列出|未提供|未包含|缺失|不存在|没有(?:提供|包含))")
_RELIED_RE = re.compile(r"(?:依据|根据|依照|按照)")
_CLAUSE_RE = re.compile(r"[^，；,;]+[，；,;]?")
_PRONOUN_RE = re.compile(r"(?:该|本|上述|前述)(?:条文|条款|条|规定)")


def _articles_in(text: str) -> set[int]:
    return {number for literal in _ARTICLE_IN_TEXT_RE.findall(text) if (number := article_number(literal)) is not None}


def _clauses(text: str) -> list[str]:
    return [clause for clause in _CLAUSE_RE.findall(text) if clause.strip()]


def _negated_articles(clause: str) -> set[int]:
    """否定短语实际指向的条号：取距离最近的条号，避免同小句其他条号被连带误伤。

    规则：否定短语后有条号 → 取其后第一个；否则取前面最后一个；若前文有"均/都/全部"
    则整组都算。无条号返回空（代词指代由调用方处理）。
    """
    match = _NEGATED_RE.search(clause)
    if not match:
        return set()
    numbered = [
        (item.start(), number)
        for item in _ARTICLE_IN_TEXT_RE.finditer(clause)
        if (number := article_number(item.group(1))) is not None
    ]
    if not numbered:
        return set()
    if re.search(r"(?:均|都|全部)", clause[max(0, match.start() - 6) : match.start()]):
        return {number for _, number in numbered}
    before = [item for item in numbered if item[0] < match.start()]
    after = [item for item in numbered if item[0] > match.start()]
    if after:
        return {after[0][1]}
    if before:
        return {before[-1][1]}
    return set()


def detect_conclusion_contradiction(text: str) -> list[str]:
    """返回"既被依据又被声明缺失"的条号（阿拉伯数字、升序）。

    - 条号归一为数字（"第二百三十四条" ≡ "234条"）；
    - 否定只取**同小句里距离否定短语最近的条号**；无条号时仅当出现
      "该条/本条/上述条文"才回看最近一个"依据"句。避免"依据 14、234（未直接列出
      234 全文）"把 14 也误判，以及"根据 584 条，未包含精神损害"这类正常表述被误报。
    """
    if not text:
        return []
    sentences = [sentence for sentence in re.split(r"(?<=[。！？!?\n])", text) if sentence.strip()]
    relied: set[int] = set()
    negated: set[int] = set()
    for index, sentence in enumerate(sentences):
        for clause in _clauses(sentence):
            articles = _articles_in(clause)
            if _RELIED_RE.search(clause):
                relied |= articles
            if not _NEGATED_RE.search(clause):
                continue
            pointed = _negated_articles(clause)
            negated |= pointed
            if pointed or articles or not _PRONOUN_RE.search(clause):
                continue
            for previous in reversed(sentences[: index + 1]):
                previous_articles = _articles_in(previous)
                if previous_articles and _RELIED_RE.search(previous):
                    negated |= previous_articles
                    break
    return [str(number) for number in sorted(relied & negated)]
