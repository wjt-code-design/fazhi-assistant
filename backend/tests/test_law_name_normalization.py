"""DB-18（2026-10-09，审查报告 B-49）：法名归一收成唯一真源，且全/半角括注都剥。

背景：库存 `source` 是裸名（`劳动合同法`），而外部权威源与模型输出常写成
`中华人民共和国劳动合同法(2012修正)`（元典智库返回的法规名正是此形状，实测见
`docs/backend-readonly-audit-20260929.md` §12.6）。这条规则此前在本仓有**四份**实现
（`retrieval._source_key`、`retrieval.parse_article_query` 内联剥前缀、
`agent.writer._canonical_law_name`、`scripts/smoke_citation_full.norm_law_name`），
且**全部只认全角 `（…）`** ⇒ 半角版本括注不被容忍，10 个引用校验消费点
（`article_in_kb`/`source_in_kb`/`_src_set_cache`/`main.py` 两处…）会把"其实有据可查"
判成"库里没有"——引用校验**假阴性**，比误拦更难查。

本文件钉三件事：① 真源只有一个、四种形状都剥得掉；② 各消费点仍与真源逐字相等（防再漂）；
③ 负向自证——只认全角的旧写法**过不了**半角样本，否则这几条断言是恒真的。
"""

from __future__ import annotations

import pathlib
import re

import domain_rules
import retrieval
from agent.writer import _canonical_law_name

# 全称 / 简称 / 全角括注 / 半角括注 / 前缀+半角（元典真实形状）/ 前缀后带空格 / 空白 / 空值
SAMPLES: list[tuple[str | None, str]] = [
    ("中华人民共和国劳动合同法", "劳动合同法"),
    ("中华人民共和国劳动合同法(2012修正)", "劳动合同法"),
    ("劳动合同法(2012修正)", "劳动合同法"),
    ("劳动合同法（2012修正）", "劳动合同法"),
    ("中华人民共和国 民法典", "民法典"),
    ("宪法（1982年）", "宪法"),
    ("  劳动法  ", "劳动法"),
    ("消费者权益保护法", "消费者权益保护法"),
    ("", ""),
    (None, ""),
]


def test_truth_source_strips_both_bracket_shapes() -> None:
    for raw, want in SAMPLES:
        got = domain_rules.norm_law_name(raw)  # type: ignore[arg-type]
        assert got == want, f"归一失配：{raw!r} → {got!r}，应为 {want!r}"


def test_only_the_trailing_bracket_is_stripped() -> None:
    """只剥**尾部**一个括注，与改前 `_source_key` 同界（不顺手把语义改宽）。"""
    assert domain_rules.norm_law_name("宪法修正案（一）（二）") == "宪法修正案（一）"
    assert domain_rules.norm_law_name("民法典(合同编)(2020)") == "民法典(合同编)"


def test_legacy_fullwidth_only_regex_cannot_pass_the_halfwidth_sample() -> None:
    """负向自证：旧的那份只认全角的正则必须**过不了**半角样本 ⇒ 尺子能红。"""
    legacy = re.compile(r"（[^）]*）\s*$")
    half = "劳动合同法(2012修正)"
    assert legacy.sub("", half).strip() == half, "旧正则竟能剥半角 ⇒ 本轮判据对象是空的，断言无意义"
    assert domain_rules.norm_law_name(half) == "劳动合同法", "真源必须剥掉半角括注（B-49 正身）"


def test_retrieval_source_key_equals_the_truth() -> None:
    for raw, want in SAMPLES:
        assert retrieval._source_key(raw) == want, f"retrieval._source_key 与真源分叉：{raw!r}"  # type: ignore[arg-type]


def test_writer_canonical_law_name_equals_the_truth() -> None:
    """`agent/writer.py` 那份此前**零测试覆盖**，且是四份里唯一带括注正则的第二个实现。"""
    for raw, want in SAMPLES:
        assert _canonical_law_name(raw) == want, f"writer._canonical_law_name 与真源分叉：{raw!r}"  # type: ignore[arg-type]


def test_parse_article_query_normalizes_like_the_truth() -> None:
    """条号直查侧（原先内联一份剥前缀字面量）归一结果必须与真源同值。

    抽取正则的第 1 组只允许汉字/书名号内容，不含括号 ⇒ 本用例断言的是"不再有第二份规则"，
    而不是新行为；`《》` 形态与"裸名+条号"形态都走一遍。
    """
    for _raw, want in SAMPLES:
        if not want:
            continue
        parsed = retrieval.parse_article_query(f"《{want}》第一百八十八条")
        assert parsed is not None and parsed[0] == want, f"parse_article_query 归一与真源分叉：{want!r}"
        bare = retrieval.parse_article_query(f"{want}第一百八十八条")
        assert bare is not None and bare[0] == want, f"裸名形态分叉：{want!r}"


def test_script_copy_delegates_instead_of_duplicating() -> None:
    """`scripts/smoke_citation_full.py` 必须引用真源，而不是留着第五份字面量副本。"""
    src = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "smoke_citation_full.py"
    text = src.read_text(encoding="utf-8")
    assert "from domain_rules import norm_law_name" in text, "脚本副本未接真源"
    assert 're.compile(r"（[^）]*）' not in text, "脚本里还留着第二份去括注正则"
