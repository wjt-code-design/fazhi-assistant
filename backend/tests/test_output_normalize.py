"""B1/B2/B3 生成层输出归一测试（2026-08-07）。纯函数，不碰数据库/BGE。

- money_normalize：币种 $/¥→元（范围/后缀/前缀），LaTeX 不误伤
- strip_unprovided_notes：库内删句 / 库外保句 / 无书名删
- citation_grounding：三分法分类（注入 in_kb，不查 Chroma）
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

from output_normalize import expand_citations, money_normalize, strip_unprovided_notes  # noqa: E402
import retrieval as R  # noqa: E402


# ---------------- money_normalize ----------------
def test_money_range_typo():
    assert money_normalize("150-200$3") == "150-200元"


def test_money_suffix_typo():
    assert money_normalize("100$") == "100元"
    assert money_normalize("100$3") == "100元"  # $ 后垃圾数字丢弃


def test_money_prefix():
    assert money_normalize("$150") == "150元"
    assert money_normalize("¥100") == "100元"


def test_money_no_false_positive():
    assert money_normalize("违约金五千元") == "违约金五千元"
    assert money_normalize("150-200元") == "150-200元"
    assert money_normalize("方程 x$\\neq$y") == "方程 x$\\neq$y"  # LaTeX 不误伤


# ---------------- expand_citations（省略书名展开） ----------------
def test_expand_continuation_with_parenthetical():
    # 用户实测：两条法条间夹括号说明，第二条省略书名
    src = "法条依据：《民法典》第七百一十五条（承租人经同意转租时）、第七百一十六条（未经同意转租时）。"
    out = expand_citations(src)
    assert "《民法典》第七百一十五条" in out
    assert "《民法典》第七百一十六条" in out


def test_expand_simple_continuation():
    out = expand_citations("《民法典》第四百九十七条、第五百六十三条。")
    assert "《民法典》第五百六十三条" in out


def test_expand_idempotent_and_cross_sentence():
    src = "《民法典》第一百八十二条。第一百八十三条另有规定。"
    out = expand_citations(src)
    assert "第一百八十三条" in out  # 跨句不归上一个书名（。断开）


def test_expand_no_book_untouched():
    out = expand_citations("合同第九条约定争议解决方式。")
    assert out == "合同第九条约定争议解决方式。"


# ---------------- strip_unprovided_notes ----------------
def test_strip_in_kb_drops_contradiction():
    in_kb = lambda s: s == "民法典"
    out = strip_unprovided_notes("《民法典》相关条文未在本次检索中提供，建议核对原文。其余正常。", in_kb)
    assert "建议核对" not in out
    assert "其余正常" in out


def test_strip_out_of_kb_keeps_honest_note():
    in_kb = lambda s: s == "民法典"
    out = strip_unprovided_notes("《某司法解释》相关条文未收录，建议核对原文。", in_kb)
    assert "某司法解释" in out  # 真未收录 → 保留诚实说明


def test_strip_bare_noise_deleted():
    in_kb = lambda s: True
    assert strip_unprovided_notes("建议核对原文。", in_kb) == ""


# ---------------- citation_grounding（三分法） ----------------
def test_grounding_three_buckets():
    stats = {}
    in_kb = lambda src, art: src in ("民法典", "劳动法")
    answer = "根据《民法典》第一百八十二条和《劳动法》第五十条，以及《某法》第九条。"
    sources = [{"source": "民法典", "article": "第一百八十二条"}]
    in_ctx, rm, hal = R.citation_grounding(answer, sources, stats, in_kb=in_kb)
    assert len(in_ctx) == 1  # 民法典第一百八十二条 ∈ 上下文
    assert len(rm) == 1  # 劳动法第五十条 在库未召回
    assert len(hal) == 1  # 某法第九条 不在库 → 真幻觉
    assert stats == {"in_context": 1, "recall_miss": 1, "hallucination": 1}


def test_grounding_no_citations():
    stats = {}
    in_ctx, rm, hal = R.citation_grounding("没有引用任何条文。", [], stats, in_kb=lambda *a: True)
    assert in_ctx == [] and rm == [] and hal == []
    assert stats == {}
