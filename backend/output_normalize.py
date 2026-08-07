"""生成层输出归一（确定性纯函数，2026-08-07 B1/B2/B3）。

替代前端"事后猜测性正则兜底"（stripUnprovidedHint / fixCurrencyTypos）：
后端生成层做主约束，前端只做展示。零 LLM、零 BGE、不 import retrieval，可单测。

- money_normalize：人民币 $ / ¥ 笔误归一为"元"（前缀/后缀/范围形）
- strip_unprovided_notes：删除"未检索到/建议核对原文"矛盾句（带库证据 source_in_kb）
"""
import re

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
    "著作权法", "商标法", "专利法", "合伙企业法",
    "刑事诉讼法", "民事诉讼法", "行政处罚法", "行政复议法", "行政诉讼法",
    "劳动合同法", "治安管理处罚法", "消费者权益保护法", "道路交通安全法",
    "企业破产法", "社会保险法", "税收征收管理法", "反家庭暴力法",
    "民法典", "刑法", "劳动法", "保险法", "公司法", "证券法", "票据法",
    "宪法", "食品安全法", "产品质量法",
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
_UNPROVIDED_RE = re.compile(
    r"(未在本次检索中提供|未在知识库中检索到|未收录该法|建议核对原文|请核对条文原文)"
)


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
