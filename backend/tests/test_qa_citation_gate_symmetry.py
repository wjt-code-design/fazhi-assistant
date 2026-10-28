"""票 W1：QA 引用的条文可核验性 ⇒ **两个出口共用一份判据**（2026-09-25 Owner 裁决"对称收口"）。

失效模式（第 8 节② 的后一半）：语料命中后，这条记录有**两条**出路——
① `main._qa_direct_return` 零模型直返，② `main._build_messages` 把它作为
"此前已确认的问答（可优先参考）"注入 prompt。此前"引用的条文还在不在库"这步时效判定**只写在①里**，
② 由产生处（`request_bootstrap.prepare_fast_path`）的**形状**判据把关，而形状判据只问
"引用给不给得出"、不问"引用核验不核验得了" ⇒ 一条引用已删条目的记录照样进 prompt。

修法按裁决落成**一个函数两处调**，不是"把循环抄到第二个地方"：
`retrieval.qa_citations_in_kb` 是唯一的判据本体，①直返与②产生处（注入通道的上游）都调它。
本文件钉的是"共享"这件事本身；产生处接缝的先红腿在
`tests/test_request_bootstrap.py`（`test_fast_path_drops_qa_hit_whose_citation_is_not_in_kb` 一组）。

为什么判据本体住在 `retrieval`：它要做的是**库内**精确条号命中（`exact_article_lookup`），
而 `retrieval_core` 是全仓唯一的纯谓词层（不碰库）。方向上也只有这一条无环路——
`retrieval` 顶部就 `import retrieval_core as rc`（retrieval.py:24），反向 import 会成环。
"""

import inspect
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

import main
import retrieval

_BASIS = "2026-08-23"
_TWO_PAIRS = json.dumps(
    [{"source": "劳动合同法", "article": "第十九条"}, {"source": "某法", "article": "第X条"}],
    ensure_ascii=False,
)


def _qa(evidence="劳动合同法|第十九条", **over):
    hit = {
        "question": "试用期最长多久",
        "answer": "最长六个月",
        "score": 0.99,
        "fingerprint": "",
        "evidence": evidence,
        "law_as_of_basis": _BASIS,
    }
    hit.update(over)
    return hit


def _body(fn) -> str:
    """取**函数体**源码（全文扫描会误伤同文件里合法使用同一函数的其它路径）。"""
    return inspect.getsource(fn)


# ==================== 判据本体 ====================


def test_predicate_verifies_every_cited_article(monkeypatch):
    """逐条核验，不是"第一条过了就过"；任一查不到 ⇒ 整条记录不可核验。"""
    calls: list[tuple[str, str]] = []
    present = {("劳动合同法", "第十九条")}

    def _lookup(src, art):
        calls.append((src, art))
        return ["doc"] if (src, art) in present else []

    monkeypatch.setattr(retrieval, "exact_article_lookup", _lookup)

    assert retrieval.qa_citations_in_kb(_qa()) is True
    assert calls == [("劳动合同法", "第十九条")]

    assert retrieval.qa_citations_in_kb(_qa(evidence=_TWO_PAIRS)) is False
    assert ("某法", "第X条") in calls, "第二条引用没被核验 ⇒ 判据只看了第一条"


def test_predicate_is_fail_closed_on_unparsable_evidence_and_on_read_failure(monkeypatch):
    """两条 fail-closed：① 解析不出任何引用 ⇒ False（"没得核验"不等于"核验通过"）；
    ② 库读不动 ⇒ False（沿用直返出口既有的 `except Exception → 不直返` 口径，
    查不动不能算查得过）。"""
    monkeypatch.setattr(retrieval, "exact_article_lookup", lambda src, art: ["doc"])
    assert retrieval.qa_citations_in_kb(_qa(evidence="feedback:down")) is False
    assert retrieval.qa_citations_in_kb(_qa(evidence="")) is False
    assert retrieval.qa_citations_in_kb(None) is False

    def _boom(src, art):
        raise RuntimeError("chroma 读失败")

    monkeypatch.setattr(retrieval, "exact_article_lookup", _boom)
    assert retrieval.qa_citations_in_kb(_qa()) is False


# ==================== 共享：两个出口调的是同一个函数 ====================


def test_both_exits_call_the_same_function_object():
    """裁决的字面要求："判据上提到产生处"= 两处调**同一个**对象，不是各抄一份循环。

    谁把判据在某个出口重新内联（第二份判据 ⇒ 两份会各自漂移；本仓对 `_source_key`、
    `is_valid_by_time` 立的就是同一份"单一真源"规矩），这条直接红。
    """
    assert main.qa_citations_in_kb is retrieval.qa_citations_in_kb

    import request_bootstrap

    assert "qa_citations_in_kb" in _body(request_bootstrap.prepare_fast_path)


@pytest.mark.parametrize("fn", [main._qa_direct_return, retrieval.qa_citations_in_kb], ids=["exit-direct", "kb"])
def test_no_exit_keeps_its_own_copy_of_the_lookup_loop(fn):
    """出口侧不许再自己"解析引用 + 查库"：解析与查库是判据本体的事。

    对 `qa_citations_in_kb` 自身则反向要求它**必须**用那份唯一解析器 `rc.cited_articles`
    （否则它就是第二份形状知识——本仓第 10 节② 的原始失效模式）。
    """
    body = _body(fn)
    if fn is main._qa_direct_return:
        assert "exact_article_lookup(" not in body, "直返出口仍自带查库循环 ⇒ 存在第二份判据"
        assert "cited_articles(" not in body, "直返出口仍自己解析引用形状"
        assert "qa_citations_in_kb(" in body
    else:
        assert "cited_articles(" in body, "判据本体没用唯一解析器 ⇒ 又造了一份形状知识"


# ==================== 出口 1：直返仍按同一判据拒 ====================


@pytest.mark.parametrize(
    "docs,expected",
    [([], None), (["doc"], "最长六个月")],
    ids=["article-missing", "article-present"],
)
def test_direct_return_follows_the_shared_predicate(monkeypatch, docs, expected):
    """直返的行为**没有**因为搬判据而改变：查不到照旧 miss，查得到照旧零 token 直返。

    替身打在 `retrieval.exact_article_lookup` 上——这一处 patch 现在同时决定**两个出口**的行为，
    这正是"一个函数两处调"的可观测后果（改之前，patch `main` 只影响直返、影响不到产生处）。
    """
    monkeypatch.setattr(retrieval, "exact_article_lookup", lambda src, art: docs)
    pre = {"rewritten": "试用期最长多久", "qa_hit": _qa()}
    assert main._qa_direct_return(pre) == expected
