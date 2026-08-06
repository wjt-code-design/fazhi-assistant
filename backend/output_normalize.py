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


# ---- 省略书名的连续条号展开（B3 补充，2026-08-07）----
# 模型常输出"《民法典》第七百一十五条（...解释...）、第七百一十六条"——第二条省略书名，
# 前端标注/弹卡需书名。展开为《最近书名》第X条：存储一致、citation_grounding 抽取更准。
_LAW_LIKE_RE = re.compile(
    r"(《([^》]{1,24}?)》\s*)?(第[零〇○一二三四五六七八九十百千万0-9０-９]+条(?:之[一二三四五六七八九十百千万0-9０-９]+)?)"
)


def expand_citations(text: str) -> str:
    """把省略书名的独立「第X条」展开为《最近书名》第X条（同句内最近《X》）。

    按句切分（。！？\n），句内维护最近书名；无书名可归的独立条号原样保留；
    已有书名的完整引用原样保留（幂等，已展开文本重跑无变化）。
    """
    if not text:
        return text
    out: list[str] = []
    for sent in re.split(r"(?<=[。！？!?\n])", text):
        last = ""

        def _repl(m: "re.Match") -> str:
            nonlocal last
            book = m.group(2) or ""
            art = m.group(3)
            if book:
                last = book
                return f"《{book}》{art}"
            if last:
                return f"《{last}》{art}"
            return art

        out.append(_LAW_LIKE_RE.sub(_repl, sent))
    return "".join(out)


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
