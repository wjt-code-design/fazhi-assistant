"""历史查询基准日必须进入**取数口径**，而不是只在末尾剔除（AUTH-2 续，2026-09-23）。

产品契约：`law_as_of` 是普通已认证用户可用的公开历史查询条件。若各检索支路仍按**当日**
cutoff 捞证据、事后才用历史日期过滤，则后果不是"返回了错版法"而是**静默丢证据**：
历史有效版本从没被召回，当日版本被过滤掉 ⇒ 该场景证据变薄甚至为空，用户看不到任何提示。

本文件钉住"谁去库里捞条文"这一层的 cutoff 透传（全 mock，不碰真实 KB、不调网络）：
1. `retrieval.retrieve_exam` —— 题干/每个选项/两处兜底，四个 `hybrid_retrieve` 调用点都要带 cutoff；
2. `retrieval.scenario_supplement_docs` —— 关键词命中组与罪名兜底集的 `exact_article_lookup`；
3. `domain_rules._lookup_all` 的三个静态条文集（作弊/格式条款/消费欺诈）；
4. `domain_rules.contract_supplement_docs` 与 `build_contract_data` —— 且 `blocks` 里的条号必须
   与 cutoff 下真正取到的 `docs` 一致（此前末尾只重过滤局部 `docs`，`blocks` 没跟着变）。
"""

import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import domain_rules  # noqa: E402
import retrieval  # noqa: E402

CUTOFF = "2019-01-01"


def _doc(source, article, effective_from="2010-01-01", effective_to="", status="现行"):
    return SimpleNamespace(
        page_content=f"{source}{article}",
        metadata={
            "source": source,
            "article": article,
            "effective_from": effective_from,
            "effective_to": effective_to,
            "status": status,
        },
    )


class _Recorder:
    """记录 (args, kwargs) 的可调用桩；返回值由调用方给定。"""

    def __init__(self, result=None):
        self.calls = []
        self.result = [] if result is None else result

    def __call__(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return list(self.result)

    @property
    def cutoffs(self):
        # 只读关键字：本仓所有取数口都按 `cutoff=` 调用，位置形参那一路径不可达（留着想兼容，
        # 真漏传时反而会静默读成 None）。
        return [kwargs.get("cutoff") for _args, kwargs in self.calls]


# ==================== 1. 考试分步检索 ====================


def _stub_exam_units(monkeypatch, rec):
    monkeypatch.setattr(retrieval.query_understand, "_split_by_choice", lambda q: ["题干", "A. 甲", "B. 乙"])
    monkeypatch.setattr(retrieval, "hybrid_retrieve", rec)


def test_retrieve_exam_passes_cutoff_to_head_and_every_option_unit(monkeypatch):
    rec = _Recorder([_doc("合同法", "第一百零七条")])
    _stub_exam_units(monkeypatch, rec)

    retrieval.retrieve_exam("题干 A. 甲 B. 乙", cutoff=CUTOFF)

    assert rec.calls, "retrieve_exam 未走 hybrid_retrieve（桩未生效）"
    assert set(rec.cutoffs) == {CUTOFF}, rec.cutoffs


def test_retrieve_exam_fallbacks_also_keep_cutoff(monkeypatch):
    """两个兜底（无选项整题兜底、全单元失败兜底）不能悄悄落回当日。"""
    empty = _Recorder([])
    monkeypatch.setattr(retrieval.query_understand, "_split_by_choice", lambda q: ["题干"])
    monkeypatch.setattr(retrieval, "hybrid_retrieve", empty)

    retrieval.retrieve_exam("题干", cutoff=CUTOFF)

    assert empty.cutoffs == [CUTOFF], empty.cutoffs

    units = _Recorder([])
    _stub_exam_units(monkeypatch, units)

    retrieval.retrieve_exam("题干 A. 甲 B. 乙", cutoff=CUTOFF)

    assert set(units.cutoffs) == {CUTOFF}, units.cutoffs


def test_retrieve_exam_default_cutoff_stays_none_for_current_date_behavior(monkeypatch):
    """不传 cutoff ⇒ 逐字保持历史调用形状（生产默认路径零变化）。"""
    rec = _Recorder([_doc("民法典", "第五百七十七条")])
    _stub_exam_units(monkeypatch, rec)

    retrieval.retrieve_exam("题干 A. 甲 B. 乙")

    assert set(rec.cutoffs) == {None}, rec.cutoffs


# ==================== 2. 场景定向补充 ====================


def test_scenario_supplement_docs_passes_cutoff_to_exact_lookup(monkeypatch):
    rec = _Recorder([_doc("合同法", "第一百一十三条")])
    monkeypatch.setattr(
        retrieval,
        "_load_supplements",
        lambda: [{"keywords": ["高空抛物"], "articles": [{"source": "侵权责任法", "article": "第八十七条"}]}],
    )
    monkeypatch.setattr(retrieval, "exact_article_lookup", rec)

    retrieval.scenario_supplement_docs("高空抛物致人损害如何承担责任", cutoff=CUTOFF)

    assert rec.calls, "关键词命中却未取条（桩未生效）"
    assert set(rec.cutoffs) == {CUTOFF}, rec.cutoffs


def test_scenario_supplement_crime_fallback_passes_cutoff(monkeypatch):
    rec = _Recorder([_doc("刑法", "第二百六十四条")])
    monkeypatch.setattr(retrieval, "_load_supplements", lambda: [])
    monkeypatch.setattr(retrieval, "exact_article_lookup", rec)

    retrieval.scenario_supplement_docs("该行为构成何罪", cutoff=CUTOFF)

    assert rec.calls, "罪名兜底集未取条（桩未生效）"
    assert set(rec.cutoffs) == {CUTOFF}, rec.cutoffs


# ==================== 3. 静态条文集（作弊/消费者） ====================


def test_static_spec_doc_sets_pass_cutoff_to_lookup(monkeypatch):
    rec = _Recorder([_doc("刑法", "第二百八十四条之一")])
    monkeypatch.setattr(retrieval, "exact_article_lookup", rec)

    domain_rules.cheating_docs(cutoff=CUTOFF)
    domain_rules.consumer_clause_docs(cutoff=CUTOFF)
    domain_rules.consumer_fraud_docs(cutoff=CUTOFF)

    assert rec.calls
    assert set(rec.cutoffs) == {CUTOFF}, rec.cutoffs


# ==================== 4. 合同证据链 ====================


def _stub_clause_mapping(monkeypatch):
    monkeypatch.setattr(
        domain_rules,
        "load_clause_supplements",
        lambda: {"违约金": [{"source": "合同法", "article": "第一百一十四条"}]},
    )


def test_contract_supplement_docs_passes_cutoff_to_lookup_and_semantic_fallback(monkeypatch):
    _stub_clause_mapping(monkeypatch)
    lookup = _Recorder([_doc("合同法", "第一百一十四条")])
    monkeypatch.setattr(retrieval, "exact_article_lookup", lookup)

    domain_rules.contract_supplement_docs("逾期付款应支付违约金", cutoff=CUTOFF)

    assert set(lookup.cutoffs) == {CUTOFF}, lookup.cutoffs

    monkeypatch.setattr(domain_rules, "load_clause_supplements", lambda: {})
    semantic = _Recorder([_doc("合同法", "第一百零七条")])
    monkeypatch.setattr(retrieval, "retrieve", semantic)

    domain_rules.contract_supplement_docs("与合同无关的措辞", cutoff=CUTOFF)

    assert semantic.cutoffs == [CUTOFF], semantic.cutoffs


def test_build_contract_data_blocks_reflect_cutoff_scoped_docs(monkeypatch):
    """数据流断言：`blocks` 的条号必须来自 cutoff 下真正取到的 `docs`。

    桩按 cutoff 分流：当日 → 《民法典》585，历史日 → 《合同法》114。旧实现把 cutoff 丢掉，
    两条通道只会给出当日版本 ⇒ 本用例红；而末尾过滤又只改局部 `docs`、不改 `blocks`
    ⇒ 光看 `contract_data["docs"]` 也会误判已修。
    """
    _stub_clause_mapping(monkeypatch)
    monkeypatch.setattr(domain_rules, "contract_split", lambda t: [("违约责任", "逾期付款应支付违约金")])

    def lookup(source, article, cutoff=None):
        if cutoff == CUTOFF:
            return [_doc("合同法", "第一百一十四条")]
        return [_doc("民法典", "第五百八十五条")]

    monkeypatch.setattr(retrieval, "exact_article_lookup", lookup)

    historical = domain_rules.build_contract_data("逾期付款应支付违约金", cutoff=CUTOFF)
    current = domain_rules.build_contract_data("逾期付款应支付违约金")

    assert historical["blocks"][0]["articles"] == ["第一百一十四条"], historical["blocks"]
    assert [d.metadata["source"] for d in historical["docs"]] == ["合同法"], historical["docs"]
    assert current["blocks"][0]["articles"] == ["第五百八十五条"], current["blocks"]
