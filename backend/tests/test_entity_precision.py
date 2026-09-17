"""T-A2 四组测试：entity_precision_check（settings 开关，默认关）。

组1 拦截（D1 选项一确定性子集）：个人独资企业法42 / 合伙企业法102（机制A）、民法典804（机制B）
组2 零误杀：review-verdicts.json 23 项独立"认可"条文（真实标注库）+ E03 认可簇互不拦
组3 开关关逐字不变：同拦截场景 off → 无新码且渲染成功
组4 watch-it-fail：检查禁用（缺陷版）→ 同场景变绿；恢复 → 红（on/off 差异断言；
    落盘由 dispatch-output/ta2-design-20260917/watch_it_fail.py 独立完成）

标注数据为真实 backend/knowledge_base/law_annotations.json（69 条）——防同源复算。
"""

from datetime import datetime

import pytest

from agent.schemas import (
    AgentBudgets,
    Evidence,
    Fact,
    LegalAgentState,
    LegalIssue,
    LegalValidity,
    Observation,
    SourceType,
)
from agent.writer import EvidenceBoundedWriter
from settings import settings


class PerIssueGenerator:
    """单争点渲染适配：generate 返回该争点的 claims。"""

    def __init__(self, claims):
        self.claims = claims

    def generate(self, *, payload, system_prompt):
        issue_id = payload.issues[0].issue_id
        return {"claims": [c for c in self.claims if c["issue_id"] == issue_id], "missing_information": []}


def make_state(*, question, facts, evidence_specs):
    """evidence_specs: list[(evidence_id, source_ref, snippet)]"""
    evidence = [
        Evidence(
            evidence_id=eid,
            source_id=f"src-{eid}",
            source_ref=ref,
            source_type=SourceType.STATUTE,
            snippet=snip,
            legal_validity=LegalValidity.EFFECTIVE,
            acquired_at=datetime(2026, 9, 17),
        )
        for eid, ref, snip in evidence_specs
    ]
    return LegalAgentState(
        budgets=AgentBudgets(max_verifier_research_returns=1),
        verifier_research_returns=0,
        issues=[
            LegalIssue(
                issue_id="issue-x",
                question=question,
                facts=[
                    Fact(statement=f, source=SourceType.USER, source_ref="user-statement", confidence=1.0)
                    for f in facts
                ],
            )
        ],
        evidence=evidence,
        observations=[
            Observation(issue_id="issue-x", statement="obs", evidence_ids=[e[0] for e in evidence_specs], confidence=1)
        ],
        conflicts=[],
    )


def render(state, claims):
    writer = EvidenceBoundedWriter(PerIssueGenerator(claims))
    return writer.render_issue(state, "issue-x")


def claim(eid, text, fact_ids=()):
    return {
        "local_id": "c1",
        "issue_id": "issue-x",
        "text": text,
        "evidence_ids": [eid],
        "fact_ids": list(fact_ids),
        "section": "conclusion",
    }


NEW_CODES = {"SUBJECT_TYPE_MISMATCH", "CLAIM_DIRECTION_REVERSED"}

# E01 复现：公司欠款案（事实类型域={公司(→法人)}）
E01_QUESTION = "一家公司欠我们货款，我们能否起诉以及债权是否成立？"
E01_FACTS = ["双方都是公司，签了买卖合同，送货单和双方盖章对账单齐全。", "一家公司欠我们货款20万元。"]
E01_EVIDENCE = [
    (
        "ev-23",
        "《公司法》第二十三条",
        "《公司法》第二十三条 公司股东滥用公司法人独立地位的，应当对公司债务承担连带责任。",
    ),
    (
        "ev-42",
        "《个人独资企业法》第四十二条",
        "《个人独资企业法》第四十二条 个人独资企业投资人在清算前或清算期间隐匿转移财产逃债的，应赔偿。",
    ),
    (
        "ev-102",
        "《合伙企业法》第一百零二条",
        "《合伙企业法》第一百零二条 合伙企业清算人隐匿转移合伙企业财产的，应退还并赔偿。",
    ),
]

# E03 复现：装修停工案（机制 B 方向颠倒）
E03_QUESTION = "用户是否有权要求装修公司返还已支付的8万元开工款及利息？"
E03_FACTS = ["装修公司收了8万开工款", "签了固定总价15万合同。"]
E03_EVIDENCE = [
    (
        "ev-804",
        "《民法典》第八百零四条",
        "《民法典》第八百零四条 因发包人的原因致使工程中途停建、缓建的，发包人应当赔偿承包人因此造成的停工、窝工等损失。",
    ),
]

# 23 项独立"认可"（review-verdicts.json 实测，冻结断言集）
ACCEPTED_REFS = [
    "《民事诉讼法》第二十二条",
    "《企业破产法》第二十一条",
    "《公司法》第二十三条",
    "《民事诉讼法》第一百二十一条",
    "《民法典》第一百九十二条",
    "《民法典》第五百六十二条",
    "《民法典》第五百六十四条",
    "《民法典》第七百八十三条",
    "《民法典》第七百八十七条",
    "《建筑法》第七十条",
    "《道路交通安全法》第七十三条",
    "《民法典》第一千一百七十九条",
    "《广告法》第十八条",
    "《广告法》第二十八条",
    "《产品质量法》第五十九条",
    "《消费者权益保护法》第五十五条",
    "《反不正当竞争法》第九条",
    "《消费者权益保护法》第十一条",
    "《消费者权益保护法》第四十条",
    "《消费者权益保护法》第四十四条",
    "《民法典》第一千一百九十七条",
    "《证券法》第九十三条",
    "《反不正当竞争法》第二十五条",
]


def _neut_state(ref):
    return make_state(
        question="本案应如何处理？",
        facts=["本案双方为合同当事人。"],
        evidence_specs=[("ev-1", ref, f"{ref} 之条文内容。")],
    )


# ---------- 组1：拦截（开关开） ----------


@pytest.mark.parametrize(
    "eid,ref,text",
    [
        ("ev-42", "《个人独资企业法》第四十二条", "根据《个人独资企业法》第四十二条，投资人应当清偿债务。"),
        ("ev-102", "《合伙企业法》第一百零二条", "根据《合伙企业法》第一百零二条，清算人应当赔偿损失。"),
    ],
)
def test_subject_mismatch_blocks_e01(eid, ref, text, monkeypatch):
    monkeypatch.setattr(settings, "entity_precision_check", True)
    state = make_state(question=E01_QUESTION, facts=E01_FACTS, evidence_specs=E01_EVIDENCE)
    result = render(state, [claim(eid, text)])
    assert result.status.name == "FAIL_SAFE"
    assert result.reason_code == "SUBJECT_TYPE_MISMATCH"


def test_direction_reversed_blocks_e03(monkeypatch):
    monkeypatch.setattr(settings, "entity_precision_check", True)
    state = make_state(question=E03_QUESTION, facts=E03_FACTS, evidence_specs=E03_EVIDENCE)
    result = render(state, [claim("ev-804", "根据《民法典》第八百零四条，装修公司应当赔偿相关损失。")])
    assert result.status.name == "FAIL_SAFE"
    assert result.reason_code == "CLAIM_DIRECTION_REVERSED"


# ---------- 组2：零误杀（23 项认可 + E03 认可簇） ----------


@pytest.mark.parametrize("ref", ACCEPTED_REFS)
def test_no_false_kill_on_accepted(ref, monkeypatch):
    monkeypatch.setattr(settings, "entity_precision_check", True)
    state = _neut_state(ref)
    law, _, art = ref.lstrip("《").partition("》")
    text = f"根据{ref}，本案可依法主张相关权利。"
    result = render(state, [claim("ev-1", text)])
    assert result.reason_code not in NEW_CODES, f"误杀 {ref}: {result.reason_code}"


def test_no_false_kill_within_e03_accepted_cluster(monkeypatch):
    """E03 认可条文簇（承揽侧 787/783 与中性 562/564、建筑法70）互不拦截。"""
    monkeypatch.setattr(settings, "entity_precision_check", True)
    specs = [
        ("ev-787", "《民法典》第七百八十七条", "《民法典》第七百八十七条 定作人可以随时解除承揽合同。"),
        (
            "ev-783",
            "《民法典》第七百八十三条",
            "《民法典》第七百八十三条 定作人未受领工作成果的，承揽人对工作成果享有留置权。",
        ),
        ("ev-562", "《民法典》第五百六十二条", "《民法典》第五百六十二条 当事人协商一致，可以解除合同。"),
        ("ev-564", "《民法典》第五百六十四条", "《民法典》第五百六十四条 解除权行使期限为一年。"),
        (
            "ev-70",
            "《建筑法》第七十条",
            "《建筑法》第七十条 涉及建筑主体或者承重结构变动的装修工程擅自施工的，责令改正。",
        ),
    ]
    state = make_state(question=E03_QUESTION, facts=E03_FACTS, evidence_specs=specs)
    claims = [
        claim("ev-787", "根据《民法典》第七百八十七条，定作人可以解除承揽合同。"),
        claim("ev-783", "根据《民法典》第七百八十三条，承揽人可能享有留置权。"),
        claim("ev-562", "根据《民法典》第五百六十二条，双方可以协商解除。"),
    ]
    result = render(state, claims)
    assert result.reason_code not in NEW_CODES, f"E03 认可簇被误杀: {result.reason_code}"


# ---------- 组2b：残余 7 项精确"不拦"（D1 选项一口径固化） ----------
# 冻结口径（design-prereg.md）：E04 6/49 归 R1 线；E05 128/131、E03 801/802/807 需
# domain_tags/争点机制（T-A5 后议）。本组防止未来改检查逻辑时残余场景被意外触发。

RESIDUAL_CASES = [
    # (ref, question, facts) —— E03 机制B句式在场仍不拦（801/802/807 非 impose_duty+right 交叉形态）
    ("《民法典》第八百零一条", E03_QUESTION, E03_FACTS),
    ("《民法典》第八百零二条", E03_QUESTION, E03_FACTS),
    ("《民法典》第八百零七条", E03_QUESTION, E03_FACTS),
    # E04：事实侧无主体类型词 → 机制A fail-open
    ("《劳动争议调解仲裁法》第六条", "对方医疗费和误工费该怎么赔？", ["我开车蹭到电动车，对方轻微擦伤。"]),
    ("《消费者权益保护法》第四十九条", "对方医疗费和误工费该怎么赔？", ["我开车蹭到电动车，对方轻微擦伤。"]),
    # E05：事实侧无类型词、主体与主导相交
    ("《药品管理法》第一百二十八条", "我能要求赔偿吗？", ["网上买的保健品宣传降血糖，吃了没效果。"]),
    ("《药品管理法》第一百三十一条", "我能要求赔偿吗？", ["网上买的保健品宣传降血糖，吃了没效果。"]),
]


@pytest.mark.parametrize("ref,question,facts", RESIDUAL_CASES)
def test_residual_scenarios_not_blocked(ref, question, facts, monkeypatch):
    monkeypatch.setattr(settings, "entity_precision_check", True)
    state = make_state(question=question, facts=facts, evidence_specs=[("ev-1", ref, f"{ref} 之条文内容。")])
    result = render(state, [claim("ev-1", f"根据{ref}，本案可以依法主张相关权利。")])
    assert result.reason_code not in NEW_CODES, f"残余场景被意外拦截: {ref}: {result.reason_code}"


# ---------- 组3：开关关逐字不变 ----------


@pytest.mark.parametrize(
    "evidence_specs,question,facts,claim_kwargs",
    [
        (E01_EVIDENCE, E01_QUESTION, E01_FACTS, ("ev-42", "根据《个人独资企业法》第四十二条，投资人应当清偿债务。")),
        (E03_EVIDENCE, E03_QUESTION, E03_FACTS, ("ev-804", "根据《民法典》第八百零四条，装修公司应当赔偿相关损失。")),
    ],
)
def test_switch_off_verbatim(evidence_specs, question, facts, claim_kwargs, monkeypatch):
    monkeypatch.setattr(settings, "entity_precision_check", False)
    state = make_state(question=question, facts=facts, evidence_specs=evidence_specs)
    result = render(state, [claim(*claim_kwargs)])
    assert result.status.name == "READY" or result.status.name == "FAIL_SAFE"
    assert result.reason_code not in NEW_CODES
    if result.status.name == "READY":
        assert result.draft is not None


# ---------- 组4：watch-it-fail（缺陷版禁用检查 → 同场景绿；恢复 → 红） ----------


def test_watch_it_fail_disabled_check_turns_green(monkeypatch):
    """语义回滚：检查函数恒 False（缺陷版）→ 拦截场景不再失败；恢复后变红。"""
    from agent import entity_precision as ep

    state = make_state(question=E01_QUESTION, facts=E01_FACTS, evidence_specs=E01_EVIDENCE)
    claims = [claim("ev-42", "根据《个人独资企业法》第四十二条，投资人应当清偿债务。")]

    monkeypatch.setattr(settings, "entity_precision_check", True)
    red = render(state, claims)
    assert red.reason_code == "SUBJECT_TYPE_MISMATCH"  # 恢复版：红（拦截）

    monkeypatch.setattr(ep, "subject_type_mismatch", lambda *a, **k: False)
    monkeypatch.setattr(ep, "direction_reversed", lambda *a, **k: False)
    green = render(state, claims)
    assert green.reason_code not in NEW_CODES  # 缺陷版：绿（漏放行）
