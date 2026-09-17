from __future__ import annotations

import sys
import time
from datetime import date, datetime
from threading import Barrier, Event, Thread
from types import SimpleNamespace

import pytest
from pydantic import BaseModel, ValidationError

from agent.schemas import LegalAgentState, ToolCallDecision
from agent.schemas import Observation as CanonicalObservation
from tools.contracts import (
    AskUserInput,
    AskUserOutput,
    ContractInput,
    ContractOutput,
    LookupArticleInput,
    LookupArticleOutput,
    MemoryMessage,
    RetrievalMetadata,
    RetrieveLawsInput,
    RetrieveLawsOutput,
    RetrieveMemoryInput,
    RetrieveMemoryOutput,
    ToolContext,
    ToolEvidence,
    map_document,
)
from tools.gateway import (
    DuplicateToolCall,
    ToolAuthorizationError,
    ToolGateway,
    UnknownTool,
)


@pytest.fixture
def context() -> ToolContext:
    return ToolContext(user_id=7, conversation_id=11, run_id="run-a", law_as_of=date(2024, 1, 2))


def decision(tool_name: str, args: BaseModel, issue_id: str = "issue-a") -> ToolCallDecision:
    return ToolCallDecision(issue_id=issue_id, tool_name=tool_name, args=args)


def test_unknown_tool_never_calls_wrapper(context):
    calls = []
    gateway = ToolGateway(wrapper_overrides={"retrieve_laws": lambda *_: calls.append(1)})

    with pytest.raises(UnknownTool):
        gateway.execute(context, decision("not_allowlisted", RetrieveLawsInput(query="请求")))

    assert calls == []


def test_model_supplied_ownership_is_rejected_before_execution(context):
    class HostileArgs(BaseModel):
        conversation_id: int

    calls = []
    gateway = ToolGateway(wrapper_overrides={"retrieve_memory": lambda *_: calls.append(1)})

    with pytest.raises(ToolAuthorizationError):
        gateway.execute(context, decision("retrieve_memory", HostileArgs(conversation_id=999)))

    assert calls == []
    assert "conversation_id" not in RetrieveMemoryInput.model_fields


def test_nested_model_supplied_ownership_is_rejected_before_execution(context):
    class HostileNestedArgs(BaseModel):
        payload: dict[str, dict[str, int]]

    calls = []
    gateway = ToolGateway(wrapper_overrides={"retrieve_memory": lambda *_: calls.append(1)})

    with pytest.raises(ToolAuthorizationError):
        gateway.execute(
            context,
            decision("retrieve_memory", HostileNestedArgs(payload={"owner": {"user_id": 999}})),
        )

    assert calls == []


def test_duplicate_and_canonical_field_order_are_blocked_before_second_execution(context):
    class ReorderedRetrieveInput(BaseModel):
        k: int
        query: str

    calls = []
    output = RetrieveLawsOutput(statement="未检索到匹配的法律资料。", evidence=[])
    gateway = ToolGateway(wrapper_overrides={"retrieve_laws": lambda *_: calls.append(1) or output})

    first = decision("retrieve_laws", RetrieveLawsInput(query="民法", k=3))
    same = decision("retrieve_laws", ReorderedRetrieveInput(k=3, query="民法"))
    gateway.execute(context, first)
    with pytest.raises(DuplicateToolCall):
        gateway.execute(context, same)

    assert calls == [1]


def test_invalid_typed_args_do_not_reach_wrapper(context):
    class InvalidArgs(BaseModel):
        query: str
        k: int

    calls = []
    gateway = ToolGateway(wrapper_overrides={"retrieve_laws": lambda *_: calls.append(1)})

    with pytest.raises(ValidationError):
        gateway.execute(context, decision("retrieve_laws", InvalidArgs(query="", k=0)))

    assert calls == []


def test_empty_retrieval_is_successful_and_fabricates_no_evidence(context):
    gateway = ToolGateway(
        wrapper_overrides={
            "retrieve_laws": lambda *_: RetrieveLawsOutput(statement="未检索到匹配的法律资料。", evidence=[])
        }
    )

    observation = gateway.execute(context, decision("retrieve_laws", RetrieveLawsInput(query="不存在")))

    assert observation.model_dump(mode="json") == {
        "issue_id": "issue-a",
        "tool_name": "retrieve_laws",
        "status": "succeeded",
        "statement": "未检索到匹配的法律资料。",
        "evidence_ids": [],
        "confidence": None,
        "output": {
            "kind": "retrieve_laws",
            "statement": "未检索到匹配的法律资料。",
            "evidence": [],
            "retrieval": None,
        },
        "error_code": None,
        "duration_ms": pytest.approx(observation.duration_ms),
    }


def test_timeout_and_exception_are_failed_observations_without_fallback(context):
    calls = []

    def slow(*_):
        calls.append("slow")
        time.sleep(0.05)
        return RetrieveLawsOutput(statement="late", evidence=[])

    timeout_gateway = ToolGateway(
        wrapper_overrides={"retrieve_laws": slow}, policy_overrides={"retrieve_laws": {"timeout_seconds": 0.001}}
    )
    timed_out = timeout_gateway.execute(context, decision("retrieve_laws", RetrieveLawsInput(query="超时")))

    def broken(*_):
        calls.append("broken")
        raise RuntimeError("secret database detail")

    exception_gateway = ToolGateway(wrapper_overrides={"retrieve_laws": broken})
    failed = exception_gateway.execute(context, decision("retrieve_laws", RetrieveLawsInput(query="异常")))

    assert timed_out.status == "failed"
    assert timed_out.error_code == "TOOL_TIMEOUT"
    assert failed.status == "failed"
    assert failed.error_code == "TOOL_EXECUTION_ERROR"
    assert "secret" not in failed.statement
    assert calls == ["slow", "broken"]


def test_max_calls_are_isolated_by_gateway_instance_and_run(context):
    calls = []

    def wrapper(*_):
        calls.append(1)
        return RetrieveLawsOutput(statement="ok", evidence=[])

    policy = {"retrieve_laws": {"max_calls_per_run": 1}}
    first = ToolGateway(wrapper_overrides={"retrieve_laws": wrapper}, policy_overrides=policy)
    second = ToolGateway(wrapper_overrides={"retrieve_laws": wrapper}, policy_overrides=policy)

    first.execute(context, decision("retrieve_laws", RetrieveLawsInput(query="a"), "one"))
    over_limit = first.execute(context, decision("retrieve_laws", RetrieveLawsInput(query="b"), "two"))
    second.execute(context, decision("retrieve_laws", RetrieveLawsInput(query="b"), "two"))
    another_run = context.model_copy(update={"run_id": "run-b"})
    first.execute(another_run, decision("retrieve_laws", RetrieveLawsInput(query="c"), "three"))

    assert over_limit.status == "failed"
    assert over_limit.error_code == "TOOL_CALL_LIMIT_EXCEEDED"
    assert calls == [1, 1, 1]


def test_raw_documents_map_to_deep_typed_evidence_with_bounded_snippet(monkeypatch):
    from tools import legal_retrieval

    raw = SimpleNamespace(
        page_content="甲" * 900,
        metadata={
            "id": "chunk-9",
            "source": "中华人民共和国民法典",
            "article": "第一条",
            "effective_date": "2021-01-01",
            "invalid_date": None,
            "score": 0.875,
            "category": "法律",
            "version_id": "lv-example",
            "source_url": "https://www.gov.cn/example",
            "source_document_sha256": "a" * 64,
            "reviewed_at": "2026-09-05",
        },
    )
    monkeypatch.setattr(legal_retrieval, "_retrieve", lambda **_: [raw])

    result = legal_retrieval.retrieve_laws(
        ToolContext(user_id=1, conversation_id=2, run_id="r", law_as_of=date(2024, 1, 2)),
        RetrieveLawsInput(query="民法典第一条", k=2),
    )

    assert result.model_dump(mode="json") == {
        "kind": "retrieve_laws",
        "statement": "检索到 1 条法律资料。",
        "evidence": [
            {
                "source_id": "chunk-9",
                "source": "中华人民共和国民法典",
                "article": "第一条",
                "snippet": "甲" * 600,
                "legal_validity": "effective",
                "effective_date": "2021-01-01",
                "invalid_date": None,
                "score": 0.875,
                "metadata": {
                    "category": "法律",
                    "version_id": "lv-example",
                    "source_url": "https://www.gov.cn/example",
                    "source_document_sha256": "a" * 64,
                    "reviewed_at": "2026-09-05",
                },
            }
        ],
        "retrieval": {"query": "民法典第一条", "requested_k": 2, "returned_count": 1},
    }


def test_repealed_document_is_effective_at_historical_law_as_of():
    raw = SimpleNamespace(
        page_content="历史条文",
        metadata={
            "status": "已废止",
            "effective_from": "1999-10-01",
            "effective_to": "2020-12-31",
        },
    )

    assert map_document(raw, date(2000, 1, 1)).legal_validity == "effective"
    assert map_document(raw, date(2021, 1, 1)).legal_validity == "superseded"


def test_map_document_derives_stable_source_id_when_chunk_id_missing():
    """Gate 5 证据链修复：检索产物 metadata 无 chunk_id/id/doc_id 时，派生确定性 source_id。

    此前 source_id 恒为 None → controller._convert_tool_evidence 按
    all((source_id, source, article, snippet)) 全部丢弃 → evidence=0 →
    verifier 必 EVIDENCE_COVERAGE_DEFICIENT、六段式永远无法产出。
    """
    raw = SimpleNamespace(
        page_content="第三章　劳动合同和集体合同\n第四十条　有下列情形之一的，用人单位提前三十日以书面形式通知劳动者本人或者额外支付劳动者一个月工资后，可以解除劳动合同",
        metadata={"source": "劳动合同法", "article": "第四十条"},
    )
    tev = map_document(raw, date(2026, 8, 1))
    assert tev.source_id is not None and len(tev.source_id) == 24
    # 确定性：同输入两次派生结果一致（可追溯、同 chunk 幂等）
    tev2 = map_document(raw, date(2026, 8, 1))
    assert tev2.source_id == tev.source_id
    # 不同内容 → 不同 id（chunk 变更即失效，防止证据错配）
    raw2 = SimpleNamespace(
        page_content="另一条文内容完全不一样",
        metadata={"source": "劳动合同法", "article": "第四十条"},
    )
    assert map_document(raw2, date(2026, 8, 1)).source_id != tev.source_id


def test_map_document_explicit_chunk_id_still_takes_priority():
    """回归：已有显式 chunk_id 的文档仍使用显式 id，派生逻辑仅在缺失时兜底。"""
    raw = SimpleNamespace(
        page_content="条文内容",
        metadata={"source": "民法典", "article": "第一百八十八条", "chunk_id": "abc123"},
    )
    assert map_document(raw, date(2026, 8, 1)).source_id == "abc123"
    raw_id = SimpleNamespace(
        page_content="条文内容",
        metadata={"source": "民法典", "article": "第一百八十八条", "id": "db_id_9"},
    )
    assert map_document(raw_id, date(2026, 8, 1)).source_id == "db_id_9"


def test_contract_output_maps_documents_and_does_not_expose_raw_objects(monkeypatch):
    from tools import contract

    raw = SimpleNamespace(page_content="证据", metadata={"source": "劳动合同法", "article": "第十条"})
    monkeypatch.setattr(
        contract,
        "_build_contract_data",
        lambda _text: {
            "truncated": False,
            "need_clarify": False,
            "blocks": [{"n": 1, "label": "第一条", "text": "工资", "articles": ["第十条"], "tags": []}],
            "docs": [raw],
            "level": "低",
            "basis": ["未发现高风险词"],
        },
    )

    result = contract.analyze_contract(
        ToolContext(user_id=1, conversation_id=2, run_id="r", law_as_of=date.today()),
        ContractInput(text="工资约定"),
    )

    assert result.evidence[0].source == "劳动合同法"
    assert result.model_dump(mode="json")["blocks"][0]["text"] == "工资"
    assert all(not hasattr(item, "page_content") for item in result.evidence)


def test_memory_is_user_conversation_scoped_and_closes_session_on_success_and_failure(monkeypatch, context):
    from tools import memory as memory_tool

    class Query:
        def __init__(self, conversation):
            self.conversation = conversation

        def filter(self, *_):
            return self

        def one_or_none(self):
            return self.conversation

    class Session:
        def __init__(self, conversation):
            self.conversation = conversation
            self.closed = False

        def query(self, _model):
            return Query(self.conversation)

        def close(self):
            self.closed = True

    owned = SimpleNamespace(id=11, user_id=7, summary="摘要")
    success_session = Session(owned)
    monkeypatch.setattr(memory_tool, "_session_factory", lambda: success_session)
    monkeypatch.setattr(
        memory_tool,
        "_load_context",
        lambda _db, _conv: (
            "摘要",
            [SimpleNamespace(id=3, role="user", content="问题", created_at=datetime(2024, 1, 1))],
        ),
    )

    result = memory_tool.retrieve_memory(context, RetrieveMemoryInput(limit=3))

    assert result.summary == "摘要"
    assert result.messages[0].model_dump(mode="json") == {
        "message_id": 3,
        "role": "user",
        "content": "问题",
        "created_at": "2024-01-01T00:00:00",
    }
    assert success_session.closed is True

    foreign_session = Session(SimpleNamespace(id=11, user_id=999, summary=""))
    monkeypatch.setattr(memory_tool, "_session_factory", lambda: foreign_session)
    with pytest.raises(ToolAuthorizationError):
        memory_tool.retrieve_memory(context, RetrieveMemoryInput())
    assert foreign_session.closed is True


def test_all_registered_tools_have_typed_read_only_policies(context):
    gateway = ToolGateway()

    assert set(gateway.policies) == {
        "retrieve_laws",
        "lookup_article",
        "analyze_contract",
        "retrieve_memory",
        "ask_user",
    }
    assert all(policy.read_only for policy in gateway.policies.values())
    assert all(issubclass(policy.input_model, BaseModel) for policy in gateway.policies.values())
    assert all(issubclass(policy.output_model, BaseModel) for policy in gateway.policies.values())
    assert AskUserInput(question="请补充合同全文")
    assert LookupArticleInput(source="民法典", article="第一条")


def test_gateway_observation_is_canonical_state_type_and_survives_json_round_trip(context):
    from tools.contracts import Observation as ToolObservation

    evidence = ToolEvidence(
        source_id="chunk-1",
        source="民法典",
        article="第一条",
        snippet="立法目的",
        legal_validity="effective",
    )
    output = RetrieveLawsOutput(
        statement="检索到 1 条法律资料。",
        evidence=[evidence],
        retrieval=RetrievalMetadata(query="立法目的", requested_k=1, returned_count=1),
    )
    gateway = ToolGateway(wrapper_overrides={"retrieve_laws": lambda *_: output})

    observation = gateway.execute(
        context,
        decision("retrieve_laws", RetrieveLawsInput(query="立法目的", k=1)),
    )
    restored = LegalAgentState.model_validate_json(LegalAgentState(observations=[observation]).model_dump_json())

    assert ToolObservation is CanonicalObservation
    assert type(observation) is CanonicalObservation
    assert type(restored.observations[0]) is CanonicalObservation
    assert type(restored.observations[0].output) is RetrieveLawsOutput
    assert restored.observations[0].model_dump(mode="json") == observation.model_dump(mode="json")


@pytest.mark.parametrize(
    ("tool_name", "tool_input", "output"),
    [
        (
            "retrieve_laws",
            RetrieveLawsInput(query="民法", k=1),
            RetrieveLawsOutput(
                statement="laws",
                evidence=[ToolEvidence(source="民法典", snippet="第一条")],
                retrieval=RetrievalMetadata(query="民法", requested_k=1, returned_count=1),
            ),
        ),
        (
            "lookup_article",
            LookupArticleInput(source="民法典", article="第一条"),
            LookupArticleOutput(
                statement="article",
                evidence=[ToolEvidence(source="民法典", article="第一条", snippet="内容")],
            ),
        ),
        (
            "analyze_contract",
            ContractInput(text="工资约定"),
            ContractOutput(
                statement="contract",
                truncated=False,
                need_clarify=False,
                blocks=[],
                evidence=[],
                risk_level="低",
                basis=["确定性规则"],
            ),
        ),
        (
            "retrieve_memory",
            RetrieveMemoryInput(limit=1),
            RetrieveMemoryOutput(
                statement="memory",
                summary="摘要",
                messages=[MemoryMessage(message_id=1, role="user", content="问题")],
            ),
        ),
        (
            "ask_user",
            AskUserInput(question="请补充事实"),
            AskUserOutput(statement="clarify", question="请补充事实"),
        ),
    ],
)
def test_each_policy_output_keeps_exact_type_and_deep_content_after_state_json_round_trip(
    context,
    tool_name,
    tool_input,
    output,
):
    gateway = ToolGateway(wrapper_overrides={tool_name: lambda *_: output})
    observation = gateway.execute(context, decision(tool_name, tool_input))

    restored = LegalAgentState.model_validate_json(
        LegalAgentState(observations=[observation]).model_dump_json()
    ).observations[0]

    assert gateway.policies[tool_name].output_model is type(output)
    assert output.kind == tool_name
    assert type(observation.output) is type(output)
    assert type(restored.output) is type(output)
    assert restored.output.model_dump(mode="json") == output.model_dump(mode="json")
    with pytest.raises(ValidationError):
        type(output).model_validate({**output.model_dump(mode="python"), "unexpected": "raw"})


def test_legal_retrieval_lazy_import_calls_real_target_signature(monkeypatch):
    from tools import legal_retrieval

    captured = {}

    def retrieve(query, k, category, cutoff):
        captured.update(query=query, k=k, category=category, cutoff=cutoff)
        return []

    monkeypatch.setitem(sys.modules, "retrieval", SimpleNamespace(retrieve=retrieve))
    result = legal_retrieval.retrieve_laws(
        ToolContext(user_id=1, conversation_id=2, run_id="r", law_as_of=date(2024, 3, 4)),
        RetrieveLawsInput(query="请求", k=3, category="民法"),
    )

    assert captured == {"query": "请求", "k": 3, "category": "民法", "cutoff": "2024-03-04"}
    assert result.evidence == []


def test_legal_retrieval_forwards_deadline_only_when_present(monkeypatch):
    """有预算时才透传 deadline；无预算时参数与历史完全一致（既有签名测试锁住另一半）。"""
    from tools import legal_retrieval

    seen = {}

    def retrieve(query, k, category, cutoff, **kw):
        seen.update(kw)
        return []

    monkeypatch.setitem(sys.modules, "retrieval", SimpleNamespace(retrieve=retrieve))
    deadline = time.monotonic() + 5
    legal_retrieval.retrieve_laws(
        ToolContext(
            user_id=1, conversation_id=2, run_id="r", law_as_of=date(2024, 3, 4), tool_deadline_monotonic=deadline
        ),
        RetrieveLawsInput(query="请求"),
    )
    assert seen == {"deadline_monotonic": deadline}


def test_gateway_stamps_wait_deadline_on_tool_context():
    """外层等待预算必须以单调时钟截止点注入，供包装器在启动新远程调用前检查。"""
    from tools import gateway as gateway_module

    captured = {}

    def capture(ctx, args):
        captured["deadline"] = ctx.tool_deadline_monotonic
        return RetrieveLawsOutput(statement="ok")

    gw = ToolGateway(wrapper_overrides={"retrieve_laws": capture})
    before = time.monotonic()
    obs = gw.execute(
        ToolContext(user_id=1, conversation_id=2, run_id="r", law_as_of=date(2024, 3, 4)),
        decision("retrieve_laws", RetrieveLawsInput(query="q")),
    )
    after = time.monotonic()
    assert obs.status == "succeeded"
    outer = gateway_module._POLICIES["retrieve_laws"].timeout_seconds
    assert captured["deadline"] is not None
    assert before + outer <= captured["deadline"] <= after + outer


def test_nested_output_models_forbid_unknown_fields():
    with pytest.raises(ValidationError):
        ToolEvidence.model_validate({"snippet": "内容", "raw_document": object()})


def test_multiple_gateways_share_bounded_capacity_until_timed_out_tasks_finish(
    monkeypatch,
    context,
):
    from tools import gateway as gateway_module
    from tools.gateway import BoundedExecutor

    started = Event()
    release = Event()
    both_workers_started = Barrier(3)
    calls = []

    def blocking_wrapper(*_):
        calls.append("started")
        started.set()
        both_workers_started.wait(timeout=1)
        release.wait(timeout=2)
        return RetrieveLawsOutput(statement="done", evidence=[])

    executor = BoundedExecutor(max_workers=2, max_outstanding=2, thread_name_prefix="test-tool")
    monkeypatch.setattr(gateway_module, "_DEFAULT_EXECUTOR", executor)
    first_gateway = ToolGateway(
        wrapper_overrides={"retrieve_laws": blocking_wrapper},
        policy_overrides={"retrieve_laws": {"timeout_seconds": 0.01}},
    )
    second_gateway = ToolGateway(
        wrapper_overrides={"retrieve_laws": blocking_wrapper},
        policy_overrides={"retrieve_laws": {"timeout_seconds": 0.01}},
    )
    results = {}

    def execute(key, gateway, query):
        results[key] = gateway.execute(
            context,
            decision("retrieve_laws", RetrieveLawsInput(query=query), issue_id=key),
        )

    first_caller = Thread(target=execute, args=("first", first_gateway, "first"))
    second_caller = Thread(target=execute, args=("second", second_gateway, "second"))
    try:
        first_caller.start()
        second_caller.start()
        both_workers_started.wait(timeout=1)
        assert started.is_set()
        first_caller.join(timeout=1)
        second_caller.join(timeout=1)
        assert not first_caller.is_alive()
        assert not second_caller.is_alive()
        busy = first_gateway.execute(
            context,
            decision("retrieve_laws", RetrieveLawsInput(query="third"), issue_id="third"),
        )

        assert results["first"].error_code == "TOOL_TIMEOUT"
        assert results["second"].error_code == "TOOL_TIMEOUT"
        assert busy.error_code == "TOOL_BUSY"
        assert calls == ["started", "started"]
        assert executor.outstanding == 2

        release.set()
        assert executor.wait_for_idle(timeout=1)
        assert executor.outstanding == 0

        completed_gateway = ToolGateway(
            wrapper_overrides={"retrieve_laws": lambda *_: RetrieveLawsOutput(statement="done", evidence=[])}
        )
        completed = completed_gateway.execute(
            context.model_copy(update={"run_id": "run-b"}),
            decision("retrieve_laws", RetrieveLawsInput(query="fourth"), issue_id="fourth"),
        )
        assert completed.status == "succeeded"
        assert calls == ["started", "started"]
    finally:
        release.set()
        first_caller.join(timeout=1)
        second_caller.join(timeout=1)
        executor.shutdown(wait=True)


def test_queued_future_is_cancelled_when_caller_times_out(context):
    from tools.gateway import BoundedExecutor

    first_started = Event()
    queued_started = Event()
    release_first = Event()

    def blocking_wrapper(_context, args):
        if args.query == "first":
            first_started.set()
            release_first.wait(timeout=2)
        else:
            queued_started.set()
        return RetrieveLawsOutput(statement="done", evidence=[])

    executor = BoundedExecutor(max_workers=1, max_outstanding=2, thread_name_prefix="test-queued")
    first_gateway = ToolGateway(
        executor=executor,
        wrapper_overrides={"retrieve_laws": blocking_wrapper},
        policy_overrides={"retrieve_laws": {"timeout_seconds": 0.01}},
    )
    second_gateway = ToolGateway(
        executor=executor,
        wrapper_overrides={"retrieve_laws": blocking_wrapper},
        policy_overrides={"retrieve_laws": {"timeout_seconds": 0.01}},
    )
    first_result = {}

    def execute_first():
        first_result["value"] = first_gateway.execute(
            context,
            decision("retrieve_laws", RetrieveLawsInput(query="first"), issue_id="first"),
        )

    caller = Thread(target=execute_first)
    try:
        caller.start()
        assert first_started.wait(timeout=1)

        second = second_gateway.execute(
            context,
            decision("retrieve_laws", RetrieveLawsInput(query="queued"), issue_id="queued"),
        )
        caller.join(timeout=1)

        assert not caller.is_alive()
        assert first_result["value"].error_code == "TOOL_TIMEOUT"
        assert second.error_code == "TOOL_TIMEOUT"
        assert executor.outstanding == 1

        release_first.set()
        assert executor.wait_for_idle(timeout=1)
        assert not queued_started.is_set()
        assert executor.outstanding == 0
    finally:
        release_first.set()
        caller.join(timeout=1)
        executor.shutdown(wait=True)
