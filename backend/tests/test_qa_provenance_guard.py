"""QA 语料的来源可校验性闸门（第四轮核对 §10 第 2 条；第 8 节②的闭口）。

失效模式：`qa_pairs` 里凡是给不出「条文引用 + 版本基准日」的记录，下游既无法校验它引的法
今天是否还有效，也无法判断它跨没跨法版本分水岭。此前 `_qa_direct_return` 对这类记录是
**放行**的（`evidence` 解析不出条文 ⇒ 跳过时效校验 ⇒ 原样直返），而 `main._build_messages`
还会把同一条记录以"此前已确认的问答（可优先参考）"注入 prompt——那是第二个出口，
第 8 节②只闭了第一个。

判据的形状（Owner 裁决：按证据形状整类拒绝，不按来源前缀）：
`evidence` 至少含一条 source 与 article 都非空的引用，**且** `law_as_of_basis` 是有效 YYYY-MM-DD 日期。
⇒ `feedback:` 来源天然落在判据外，未来任何新来源也默认 fail-closed，
   同时补掉 `search_qa` 用 `.get("evidence", "")` 造成的缺键 fail-open。

对照组（必须一直绿）：来源可校验的记录照常直返、照常注入 prompt——
只测拦截不测放行的门，等于没有门。
"""

import os
import sys
from datetime import date

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

import main
import retrieval  # 票 W1 起时效判据住在 `retrieval.qa_citations_in_kb` ⇒ 替身打在 retrieval 侧

_VERIFIABLE = {
    "question": "试用期最长多久",
    "answer": "最长六个月",
    "score": 0.95,
    "evidence": "劳动合同法|第十九条",
    "law_as_of_basis": "2026-01-01",
    "fingerprint": "",
}


def _pre(qa_hit):
    return {"rewritten": "试用期最长多久", "qa_hit": qa_hit}


def _kb(monkeypatch, docs):
    """把"条文能否在库中查到"钉成给定读数。

    **两处都打**：票 W1（2026-09-25）之前 `_qa_direct_return` 读 `main.exact_article_lookup`，
    之后读 `retrieval.qa_citations_in_kb` 里的同名模块全局。本文件的先红腿要能在**改前树**上复取，
    只打一处会让对照腿在另一侧树上假红（拦它的是进程私有空库，不是被检的那道判据）。
    """
    monkeypatch.setattr(main, "exact_article_lookup", lambda src, art: docs)
    monkeypatch.setattr(retrieval, "exact_article_lookup", lambda src, art: docs)


def _qa(**over):
    hit = dict(_VERIFIABLE)
    hit.update(over)
    return hit


def _make_messages_pre(qa_hit):
    """键集取自 tests/test_request_bootstrap.py 的 LEGACY_KEYS 真形状，不自造字段。"""
    return {
        "conv_id": 1,
        "intent": "legal_query",
        "image": None,
        "recent": [],
        "rewritten": "试用期最长多久",
        "user_text": "试用期最长多久",
        "summary": "",
        "qa_hit": qa_hit,
        "context": "劳动合同法 第十九条 ...",
        "sources": [{"source": "劳动合同法", "article": "第十九条"}],
        "image_rel": None,
        "thumb_rel": None,
        "is_exam": False,
        "has_options": False,
        "contract_data": None,
    }


def _prompt_text(pre) -> str:
    return "\n".join(getattr(m, "content", "") or "" for m in main._build_messages(pre))


# ==================== 判据本体 ====================


def test_cited_articles_parses_all_three_corpus_shapes():
    from retrieval_core import cited_articles

    assert cited_articles("劳动合同法|第十九条") == [("劳动合同法", "第十九条")]
    refs = '[{"source": "民法典", "article": "第一百八十八条"}, {"source": "个人所得税法", "article": ""}]'
    # 空 article 的那条不成引用，但同数组里另一条成立 ⇒ 整条记录仍可校验（不误伤存量 1 条）
    assert cited_articles(refs) == [("民法典", "第一百八十八条")]
    assert cited_articles("[]") == []
    assert cited_articles("feedback:down") == []
    assert cited_articles("") == []
    assert cited_articles("[not json") == []


def test_qa_provenance_verifiable_requires_citation_and_basis():
    from retrieval_core import qa_provenance_verifiable

    assert qa_provenance_verifiable(_qa()) is True
    assert qa_provenance_verifiable(_qa(evidence="[]")) is False  # 实测存量 5 条的形状
    assert qa_provenance_verifiable(_qa(evidence="feedback:down")) is False
    assert qa_provenance_verifiable(_qa(law_as_of_basis="")) is False
    assert qa_provenance_verifiable(_qa(law_as_of_basis="  ")) is False
    assert qa_provenance_verifiable({"answer": "x"}) is False  # 两个键都缺 ⇒ 不可校验，不是放行
    assert qa_provenance_verifiable(None) is False


@pytest.mark.parametrize("basis", ["not-a-date", "2026-02-30", "2026-01-01T00:00:00", "20260101", 20260101])
def test_qa_provenance_rejects_invalid_version_date(basis):
    from retrieval_core import qa_provenance_verifiable

    assert qa_provenance_verifiable(_qa(law_as_of_basis=basis)) is False


@pytest.mark.parametrize("basis", ["2024-02-29", "2020-12-31", "2021-01-01"])
def test_qa_provenance_accepts_valid_calendar_date(basis):
    from retrieval_core import qa_provenance_verifiable

    assert qa_provenance_verifiable(_qa(law_as_of_basis=basis)) is True


@pytest.mark.parametrize("law_as_of", [None, date(2020, 12, 31), date(2026, 9, 25)])
def test_direct_return_refuses_invalid_version_date(monkeypatch, law_as_of):
    _kb(monkeypatch, ["doc"])
    assert main._qa_direct_return(_pre(_qa(law_as_of_basis="not-a-date")), law_as_of) is None


# ==================== 出口 1：零模型直返 ====================


def test_direct_return_refuses_entry_without_citable_evidence(monkeypatch):
    """旧行为：`evidence='[]'` 解析不出条文 → 跳过时效校验 → 原样直返。本用例据此先红。"""
    _kb(monkeypatch, ["doc"])
    pre = _pre(_qa(evidence="[]"))
    assert main._qa_direct_return(pre) is None


def test_direct_return_refuses_entry_without_version_basis(monkeypatch):
    """旧行为：缺 basis → 分水岭守卫跳过（'不拦，保持旧行为'）→ 直返。"""
    _kb(monkeypatch, ["doc"])
    pre = _pre(_qa(law_as_of_basis=""))
    assert main._qa_direct_return(pre) is None


def test_direct_return_still_hits_on_verifiable_entry(monkeypatch):
    """对照腿：来源可校验 + 条文仍有效 → 直返能力不得被这次收口打掉。"""
    _kb(monkeypatch, ["doc"])
    assert main._qa_direct_return(_pre(_qa())) == "最长六个月"


def test_direct_return_still_refuses_dead_article(monkeypatch):
    """对照腿：既有的时效护栏不能被新判据取代——条文不在库仍须 miss。"""
    _kb(monkeypatch, [])
    assert main._qa_direct_return(_pre(_qa())) is None


# ==================== 出口 2：prompt 注入（第 8 节②漏掉的那一个） ====================


def test_prompt_omits_note_when_the_producer_dropped_the_hit():
    """链条后半：产生处判过之后，`qa_hit=None` 的 `pre` 不会再注入任何东西。

    ⚠️ 本用例**不是**红腿（旧行为下也绿）。真正证明"不可校验记录进不了 `qa_hit`"的红腿在
    `tests/test_request_bootstrap.py::test_fast_path_drops_qa_hit_whose_provenance_is_not_verifiable`
    ——那才是"现行请求拿不到这条注入"的那一环。两条合起来才是这条出口的完整判据：
    前半（产生处给 None）+ 后半（None ⇒ 不注入）。只测后半等于没测。
    """
    pre = _make_messages_pre(None)
    assert "此前已确认的问答" not in _prompt_text(pre)


def test_prompt_keeps_verifiable_qa_hit():
    """对照腿：可校验记录仍须出现在 prompt 里，否则这条注入通道等于被整体关掉。"""
    pre = _make_messages_pre(_qa())
    text = _prompt_text(pre)
    assert "此前已确认的问答" in text
    assert "最长六个月" in text
