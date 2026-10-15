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
import retrieval  # 票 W1 起时效判据住在 `retrieval.qa_citations_in_kb` ⇒ 替身打在 retrieval 侧（一处 patch 同时管两个出口）

BASIS = "2026-08-23"


def _pre(qa_hit=None, rewritten="", fingerprint=""):
    return {"rewritten": rewritten, "qa_hit": qa_hit}


def _kb(monkeypatch, docs):
    """把"条文能否在库中查到"钉成给定读数。

    **两处都打**：票 W1（2026-09-25）之前 `_qa_direct_return` 读的是 `main.exact_article_lookup`，
    之后读的是 `retrieval.qa_citations_in_kb` 里的同名模块全局。只打一处，另一侧的树就会把
    拦截归因到**进程私有空库**上（假红：拦它的不是时效判据，是 fixture 没覆盖的那个 import）。
    """
    monkeypatch.setattr(main, "exact_article_lookup", lambda src, art: docs)
    monkeypatch.setattr(retrieval, "exact_article_lookup", lambda src, art: docs)


def test_direct_return_low_score_misses():
    pre = _pre(qa_hit={"score": 0.8, "answer": "A", "fingerprint": "", "evidence": ""})
    assert main._qa_direct_return(pre) is None


def test_direct_return_non_option_hits(monkeypatch):
    """非选项题 + 高余弦 + evidence 有效 → 直返（零 LLM）。"""
    _kb(monkeypatch, ["doc"])
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
    _kb(monkeypatch, ["doc"])
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
    _kb(monkeypatch, ["doc"])
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
    monkeypatch.setattr(retrieval, "exact_article_lookup", lambda src, art: [])
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
