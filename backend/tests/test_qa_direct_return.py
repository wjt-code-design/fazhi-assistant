"""QA 持久语义缓存直返护栏测试（8-23 智谱免费 token 预热语料）。

四护栏：score≥0.92 + 选项指纹一致（审查 C4）+ evidence 时效有效 + 来源可校验（第四轮核对
§10 第 2 条）。任一不过 → None。

⚠️ 每条用例的 `qa_hit` 都带 `law_as_of_basis`：第五道 `qa_provenance_verifiable` 上线后，
缺它的记录会被**来源判据**先拒 ⇒ 本文件的指纹腿/时效腿会"绿在错误的维度上"（假绿）。
新判据自身的正反对用例在 `tests/test_qa_provenance_guard.py`，不在这里重复。
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

import main

BASIS = "2026-08-23"


def _pre(qa_hit=None, rewritten="", fingerprint=""):
    return {"rewritten": rewritten, "qa_hit": qa_hit}


def test_direct_return_low_score_misses():
    pre = _pre(qa_hit={"score": 0.8, "answer": "A", "fingerprint": "", "evidence": ""})
    assert main._qa_direct_return(pre) is None


def test_direct_return_non_option_hits(monkeypatch):
    """非选项题 + 高余弦 + evidence 有效 → 直返（零 LLM）。"""
    monkeypatch.setattr(main, "exact_article_lookup", lambda src, art: ["doc"])
    pre = _pre(
        qa_hit={
            "score": 0.95,
            "answer": "试用期最长六个月",
            "fingerprint": "",
            "evidence": "劳动合同法|第十九条",
            "law_as_of_basis": BASIS,
        },
        rewritten="试用期最长多久",
    )
    assert main._qa_direct_return(pre) == "试用期最长六个月"


def test_direct_return_fingerprint_mismatch_misses(monkeypatch):
    """审查 C4：选项题同题干换选项内容，指纹不同 → 必须 miss（防"选B"错位）。"""
    monkeypatch.setattr(main, "exact_article_lookup", lambda src, art: ["doc"])
    pre = _pre(
        qa_hit={
            "score": 0.99,
            "answer": "选B",
            "fingerprint": "甲\x1f乙\x1f丙\x1f丁",
            "evidence": "刑法|第二百六十四条",
            "law_as_of_basis": BASIS,
        },
        rewritten="下列说法正确的是？A.甲 B.是 C.丙 D.丁",
    )
    # 输入指纹（甲/是/丙/丁）≠ 存储指纹（甲/乙/丙/丁）→ miss
    assert main._qa_direct_return(pre) is None


def test_direct_return_fingerprint_match_hits(monkeypatch):
    """同题换标号分隔符（指纹一致）→ 命中直返。"""
    monkeypatch.setattr(main, "exact_article_lookup", lambda src, art: ["doc"])
    pre = _pre(
        qa_hit={
            "score": 0.99,
            "answer": "选B",
            "fingerprint": "甲\x1f乙\x1f丙\x1f丁",
            "evidence": "刑法|第二百六十四条",
            "law_as_of_basis": BASIS,
        },
        rewritten="下列说法正确的是？A.甲 B.乙 C.丙 D.丁",
    )
    assert main._qa_direct_return(pre) == "选B"


def test_direct_return_evidence_invalid_misses(monkeypatch):
    """evidence 条文已失效/不在库 → miss（时效护栏）。

    与 `test_qa_provenance_guard.py` 的分界：那条测"给不出引用 ⇒ 来源判据拒"，
    这条测"引用给得出、但条文查不在库 ⇒ 时效判据拒"——两道门必须能被分别打死。
    """
    monkeypatch.setattr(main, "exact_article_lookup", lambda src, art: [])
    pre = _pre(
        qa_hit={
            "score": 0.95,
            "answer": "A",
            "fingerprint": "",
            "evidence": "某法|第X条",
            "law_as_of_basis": BASIS,
        },
        rewritten="测试",
    )
    assert main._qa_direct_return(pre) is None
