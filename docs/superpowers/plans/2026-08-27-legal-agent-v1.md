# Legal Agent V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `subagent-driven-development` (recommended) or `executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a bounded, evidence-driven Legal Agent path for complex consultations while preserving the existing deterministic Legal RAG fast path and its safety gates.

**Architecture:** `main.py` becomes a request orchestrator. A new native-Python `agent` package owns explicit state transitions and a `tools` package exposes typed read-only wrappers through one gateway. SQLite persists runs and steps for the current single-worker deployment; all decisions that confer authority remain server-side.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy, Pydantic v2, SQLite, pytest, existing RAG/retrieval/contract modules, existing SSE response format.

## Global Constraints

- Do not introduce LangGraph, Multi-Agent, public web search, arbitrary SQL, arbitrary file access, or agent write tools.
- Retain the current `citation_verify`, `quality.self_check`, `output_normalize`, authentication, rate-limit and quota behavior as final deterministic gates.
- Agent V1 runs only under the repository's single-worker deployment model; no multi-worker configuration change is in scope.
- Model-generated values never set identity, authorization, conversation ownership, run ownership, legal effective date, or budget.
- New databases changes must be additive, idempotent, covered by migration tests, documented with a backup and restore procedure, and leave existing tables intact.
- Agent final-answer caching is disabled. Tool cache keys include user scope, law date, tool version and canonical arguments.
- Every new failure path has a test before its production implementation.
- Every reported benchmark result records dataset hash, command, environment and known limitation. An LLM judge is a supplemental signal, never the sole release gate.

---

## Files and responsibilities

| File | Responsibility |
| --- | --- |
| `backend/agent/schemas.py` | Immutable Pydantic contracts for state, facts, issues, evidence, decisions and verifier results. |
| `backend/agent/state_machine.py` | Allowed state transitions, budget accounting and duplicate-action fingerprints. |
| `backend/agent/repository.py` | User-scoped run persistence, optimistic version updates and step/evidence writes. |
| `backend/agent/gate.py` | Explainable rule-based Fast/Agent/Clarify/Refuse decision and shadow records. |
| `backend/agent/planner.py` | Structured planning interface; no direct tool calls or final answer generation. |
| `backend/agent/evaluator.py` | Deterministic evidence sufficiency checks and fact-gap selection. |
| `backend/agent/writer.py` | Evidence-bounded draft construction prompt and structured output parsing. |
| `backend/agent/verifier.py` | Claim-evidence coverage and output-risk verdict; no chain-of-thought retention. |
| `backend/agent/controller.py` | Bounded Plan → Tool → Observe → Evaluate loop and safe fallback result. |
| `backend/tools/contracts.py` | Tool-specific typed inputs and outputs. |
| `backend/tools/gateway.py` | Authorization injection, policy enforcement, timeout, audit, cache and observation conversion. |
| `backend/tools/legal_retrieval.py` | Read-only wrapper around existing query/retrieval functions. |
| `backend/tools/exact_article.py` | Read-only wrapper around `retrieval.exact_article_lookup`. |
| `backend/tools/contract.py` | Read-only wrapper around `domain_rules.build_contract_data`. |
| `backend/tools/memory.py` | User- and conversation-scoped reader over existing memory functions. |
| `backend/tools/clarification.py` | Structured pending-question result; never calls an LLM. |
| `backend/models.py` / `backend/migrations.py` | Additive AgentRun, AgentStep, AgentEvidence and AgentClaimCheck persistence. |
| `backend/main.py` | Request bootstrap, Fast Path delegation, controller invocation, SSE adaptation and final storage. |
| `backend/settings.py` | Safe-off feature flags and bounded Agent configuration. |
| `backend/scripts/eval_agent.py` | Frozen-complex-set evaluation and Existing-RAG versus Agent comparison. |
| `backend/data/eval_agent_complex.json` | Human-reviewed complex-task set with a separately versioned rubric. |
| `backend/data/eval_agent_complex.rubric.md` | Annotation rules for issues, facts, claims, evidence and acceptable clarifications. |
| `backend/tests/test_agent_*.py` | Unit, integration and failure-path regression coverage. |

## Task 1: Freeze a complex-task evaluation baseline before Agent code

**Files:**
- Create: `backend/data/eval_agent_complex.json`
- Create: `backend/data/eval_agent_complex.rubric.md`
- Create: `backend/scripts/eval_agent.py`
- Create: `backend/tests/test_eval_agent.py`
- Modify: `docs/BENCHMARK.md`

**Interfaces:**
- Produces `load_cases(path: Path) -> list[AgentEvalCase]`.
- Produces `evaluate_case(case: AgentEvalCase, answer: AgentEvalAnswer) -> AgentEvalResult`.
- The evaluator accepts an adapter returning the existing RAG result or an Agent trace; it must not import an LLM client itself.

- [ ] **Step 1: Write failing schema and hash tests.**

```python
def test_eval_cases_have_stable_required_fields(tmp_path):
    path = tmp_path / "cases.json"
    path.write_text('[{"id":"loan-limitations-01","query":"...","issues":["时效"],"critical_facts":["还款日期"],"expected_laws":["民法典:188"],"expected_clarification":"是否约定还款日期","important_claims":["可否起诉"]}]', encoding="utf-8")
    cases, freeze_hash = load_cases(path)
    assert cases[0].id == "loan-limitations-01"
    assert len(freeze_hash) == 64

def test_eval_rejects_untraceable_claim_support():
    result = evaluate_case(case_with_one_claim(), AgentEvalAnswer(claims=[{"text": "可起诉", "evidence_ids": []}]))
    assert result.evidence_coverage == 0.0
```

- [ ] **Step 2: Run the focused tests and verify red.**

Run: `cd backend; python -m pytest tests/test_eval_agent.py -v`

Expected: FAIL because the evaluator, cases and result contracts do not exist.

- [ ] **Step 3: Implement the frozen-set contracts and deterministic scoring.**

```python
class AgentEvalCase(BaseModel):
    id: str
    query: str
    issues: list[str]
    critical_facts: list[str]
    expected_laws: list[str]
    expected_clarification: str | None
    important_claims: list[str]

def freeze_hash(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()

def evaluate_case(case: AgentEvalCase, answer: AgentEvalAnswer) -> AgentEvalResult:
    supported = sum(bool(claim.evidence_ids) for claim in answer.claims)
    return AgentEvalResult(evidence_coverage=supported / len(case.important_claims))
```

Create 20–30 reviewed cases covering multi-issue consultation, contract comparison, missing critical facts, law-date conflict and prompt-injection text. The rubric defines one canonical issue granularity, which facts are outcome-changing, and what constitutes primary legal evidence. Do not mark LLM-generated prose as a gold answer.

- [ ] **Step 4: Implement the CLI and document baseline execution.**

`eval_agent.py` must require `--mode existing_rag|agent`, `--cases`, and `--output`; write timestamped JSON including `freeze_hash`, git revision, mode, sample size, metrics and known limitations. Add the exact command and the statement that the first run is a baseline rather than a release claim to `docs/BENCHMARK.md`.

- [ ] **Step 5: Verify green and commit.**

Run: `cd backend; python -m pytest tests/test_eval_agent.py -v`

Expected: PASS. Then run `python scripts/eval_agent.py --help` and confirm it lists all required arguments.

Commit: `git add backend/data backend/scripts/eval_agent.py backend/tests/test_eval_agent.py docs/BENCHMARK.md && git commit -m "test: add legal agent evaluation baseline"`

**DoD:** The dataset is human-reviewed, its hash is emitted by a deterministic command, malformed data fails validation, and the evaluator reports unsupported claims as unsupported.

## Task 2: Add durable, user-scoped Agent persistence and migration checks

**Files:**
- Modify: `backend/models.py`
- Modify: `backend/migrations.py`
- Create: `backend/agent/repository.py`
- Create: `backend/tests/test_agent_repository.py`
- Modify: `backend/tests/conftest.py`
- Modify: `docs/ADR.md`

**Interfaces:**
- Produces `create_run(db, *, user_id: int, conversation_id: int, state: LegalAgentState) -> AgentRun`.
- Produces `load_owned_run(db, *, run_id: str, user_id: int, conversation_id: int) -> AgentRun | None`.
- Produces `compare_and_save(db, *, run: AgentRun, expected_version: int, state: LegalAgentState, status: str) -> AgentRun` and raises `RunVersionConflict` on a stale version.

- [ ] **Step 1: Write red ownership, version-conflict and migration tests.**

```python
def test_other_user_cannot_load_agent_run(db, owner, other, conversation):
    run = create_run(db, user_id=owner.id, conversation_id=conversation.id, state=bootstrap_state())
    assert load_owned_run(db, run_id=run.id, user_id=other.id, conversation_id=conversation.id) is None

def test_stale_state_version_cannot_overwrite_newer_run(db, owner, conversation):
    run = create_run(db, user_id=owner.id, conversation_id=conversation.id, state=bootstrap_state())
    compare_and_save(db, run=run, expected_version=0, state=planning_state(), status="planning")
    with pytest.raises(RunVersionConflict):
        compare_and_save(db, run=run, expected_version=0, state=planning_state(), status="planning")
```

- [ ] **Step 2: Run the focused test and verify red.**

Run: `cd backend; python -m pytest tests/test_agent_repository.py -v`

Expected: FAIL because models and repository functions do not exist.

- [ ] **Step 3: Add additive models and idempotent migration registration.**

Use a UUID string primary key for `AgentRun`. Add `AgentRun`, `AgentStep`, `AgentEvidence`, and `AgentClaimCheck` in `models.py`; all child rows reference `agent_runs.id`. `AgentRun` has indexed `user_id`, `conversation_id`, `status`, integer `state_version`, `law_as_of`, nullable `pending_question`, `state_json`, nullable `degraded_reason`, nullable `last_error_code`, and timestamps. Steps and evidence store summary/provenance rather than raw prompts.

Register new tables through `Base.metadata.create_all` in `run_migrations`. Do not add a second hand-maintained schema definition. Extend test setup to start from a fresh temporary SQLite database and run `run_migrations()` twice.

- [ ] **Step 4: Implement repository ownership and optimistic updates.**

```python
def compare_and_save(db, *, run, expected_version, state, status):
    updated = db.query(AgentRun).filter(
        AgentRun.id == run.id,
        AgentRun.state_version == expected_version,
    ).update({
        "state_json": state.model_dump_json(),
        "status": status,
        "state_version": expected_version + 1,
        "updated_at": datetime.utcnow(),
    })
    if updated != 1:
        db.rollback()
        raise RunVersionConflict(run.id)
    db.commit()
    return db.get(AgentRun, run.id)
```

Create a step row in the same transaction as each state change. The repository does not use global mutable run state.

- [ ] **Step 5: Verify green, migration idempotency and backup procedure.**

Run: `cd backend; python -m pytest tests/test_agent_repository.py -v`

Expected: PASS. Run `python -c "from migrations import run_migrations; run_migrations(); run_migrations()"` against a disposable test database. Add an ADR section with `sqlite3 app.db '.backup before_agent_v1.db'`, a restore command, and a requirement to rehearse them before production migration.

Commit: `git add backend/models.py backend/migrations.py backend/agent/repository.py backend/tests/conftest.py backend/tests/test_agent_repository.py docs/ADR.md && git commit -m "feat: persist recoverable legal agent runs"`

**DoD:** Existing tables remain intact, repeated migrations succeed, another user cannot access a run, and a stale request cannot overwrite newer state.

## Task 3: Define explicit state, transition and budget contracts

**Files:**
- Create: `backend/agent/__init__.py`
- Create: `backend/agent/schemas.py`
- Create: `backend/agent/state_machine.py`
- Create: `backend/tests/test_agent_state_machine.py`

**Interfaces:**
- Produces `LegalAgentState`, `Fact`, `UnknownFact`, `LegalIssue`, `Evidence`, `Observation`, `PlanDecision`, `ClaimCheck` and `AgentStatus`.
- Produces `transition(state: LegalAgentState, target: AgentStatus) -> LegalAgentState`.
- Produces `register_action(state, issue_id: str, tool_name: str, args: BaseModel) -> LegalAgentState` and raises `BudgetExceeded` or `DuplicateAction`.

- [ ] **Step 1: Write red state-machine tests.**

```python
def test_waiting_user_can_resume_only_to_planning():
    state = LegalAgentState(status=AgentStatus.WAITING_USER)
    assert transition(state, AgentStatus.PLANNING).status is AgentStatus.PLANNING
    with pytest.raises(InvalidTransition):
        transition(state, AgentStatus.DRAFTING)

def test_same_issue_same_tool_same_args_is_blocked():
    state = LegalAgentState()
    state = register_action(state, "issue-1", "retrieve_laws", RetrieveLawsInput(query="时效", issue_id="issue-1"))
    with pytest.raises(DuplicateAction):
        register_action(state, "issue-1", "retrieve_laws", RetrieveLawsInput(query="时效", issue_id="issue-1"))
```

- [ ] **Step 2: Run red tests.**

Run: `cd backend; python -m pytest tests/test_agent_state_machine.py -v`

Expected: FAIL because state contracts are absent.

- [ ] **Step 3: Implement discriminated state contracts.**

Use `Literal`/Enums for status, source type and decision type. `Fact` has `statement`, `source`, `source_ref` and confidence; `UnknownFact` includes `why_outcome_changes`; `Evidence` includes immutable source identifiers, snippet, legal validity metadata and acquisition time. Make `PlanDecision` a discriminated union of `ToolCallDecision`, `AskUserDecision`, `FinishResearchDecision`, `ReplanDecision`, and `StopDecision`; do not retain `tool_args: dict`.

- [ ] **Step 4: Implement a finite transition map and canonical fingerprint.**

```python
ALLOWED = {
    AgentStatus.BOOTSTRAPPING: {AgentStatus.PLANNING, AgentStatus.FAILED, AgentStatus.REFUSED},
    AgentStatus.PLANNING: {AgentStatus.EXECUTING, AgentStatus.WAITING_USER, AgentStatus.DRAFTING, AgentStatus.FAILED},
    AgentStatus.EXECUTING: {AgentStatus.EVALUATING, AgentStatus.FAILED},
}

def action_fingerprint(issue_id: str, tool_name: str, args: BaseModel) -> str:
    canonical = json.dumps(args.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(f"{issue_id}|{tool_name}|{canonical}".encode()).hexdigest()
```

Count steps, tool calls, replans, clarification count and per-issue duplicate attempts. Exceeding a configured bound returns an explicit safe terminal decision; no counter is a module global.

- [ ] **Step 5: Verify green and commit.**

Run: `cd backend; python -m pytest tests/test_agent_state_machine.py -v`

Expected: PASS.

Commit: `git add backend/agent backend/tests/test_agent_state_machine.py && git commit -m "feat: define bounded legal agent state machine"`

**DoD:** Invalid state transitions, duplicate actions, and every configured budget limit are deterministic and covered by tests.

## Task 4: Wrap existing capabilities as typed, read-only tools behind one gateway

**Files:**
- Create: `backend/tools/__init__.py`
- Create: `backend/tools/contracts.py`
- Create: `backend/tools/gateway.py`
- Create: `backend/tools/legal_retrieval.py`
- Create: `backend/tools/exact_article.py`
- Create: `backend/tools/contract.py`
- Create: `backend/tools/memory.py`
- Create: `backend/tools/clarification.py`
- Create: `backend/tests/test_tool_gateway.py`

**Interfaces:**
- Produces `ToolContext(user_id: int, conversation_id: int, run_id: str, law_as_of: date)` server-side only.
- Produces `ToolGateway.execute(context: ToolContext, decision: ToolCallDecision) -> Observation`.
- Produces typed `RetrieveLawsInput/Output`, `LookupArticleInput/Output`, `ContractInput/Output`, `MemoryInput/Output` and `AskUserOutput`.

- [ ] **Step 1: Write red policy tests.**

```python
def test_gateway_uses_server_context_not_model_user_id():
    decision = ToolCallDecision(tool_name="retrieve_memory", input=RetrieveMemoryInput(conversation_id=999))
    with pytest.raises(ToolAuthorizationError):
        gateway.execute(ToolContext(user_id=1, conversation_id=2, run_id="r", law_as_of=date.today()), decision)

def test_gateway_blocks_duplicate_before_calling_tool(mocker):
    execute = mocker.patch("tools.legal_retrieval.retrieve")
    gateway.execute(ctx, retrieve_decision())
    with pytest.raises(DuplicateAction):
        gateway.execute(ctx, retrieve_decision())
    execute.assert_called_once()
```

- [ ] **Step 2: Run red tests.**

Run: `cd backend; python -m pytest tests/test_tool_gateway.py -v`

Expected: FAIL because the typed gateway does not exist.

- [ ] **Step 3: Implement typed wrappers without changing retrieval algorithms.**

`legal_retrieval.py` calls existing `query_understand` and `retrieval.retrieve`; `exact_article.py` calls existing `exact_article_lookup`; `contract.py` calls `build_contract_data`; `memory.py` opens a scoped SQLAlchemy session and calls existing memory readers. Each wrapper maps existing documents to typed results containing source, article, content snippet, metadata and retrieval meta. Do not return raw `Document` objects to Planner.

- [ ] **Step 4: Implement Gateway policy enforcement and observations.**

Define each policy with `read_only=True`, timeout, retry count and max calls/run. The gateway injects `ToolContext`; it rejects caller-provided ownership fields, validates the Pydantic input, checks status/budget/fingerprint, records timing and converts output to an `Observation`. A tool timeout returns `Observation(status="failed", error_code="TOOL_TIMEOUT")`; it never silently switches to another tool.

- [ ] **Step 5: Verify old retrieval behavior and gateway tests.**

Run: `cd backend; python -m pytest tests/test_tool_gateway.py tests/test_retrieval_rerank.py tests/test_contract_review.py -v`

Expected: PASS.

Commit: `git add backend/tools backend/tests/test_tool_gateway.py && git commit -m "feat: add typed read-only legal tools"`

**DoD:** Planner-facing outputs are typed, every call is auditable and user-scoped, duplicate/unauthorized calls never reach tool code, and existing retrieval/contract tests remain green.

## Task 5: Extract request bootstrap from the current fixed retrieval path

**Files:**
- Modify: `backend/main.py:497-676`
- Create: `backend/request_bootstrap.py`
- Create: `backend/tests/test_request_bootstrap.py`
- Modify: `backend/tests/test_pre_rewrite_order.py`

**Interfaces:**
- Produces `bootstrap_request(user_id, conversation_id, text, image, client_truncated) -> RequestBootstrap`.
- Produces `prepare_fast_path(bootstrap: RequestBootstrap) -> dict` preserving the existing `_pre` result keys.
- Retains `_pre(...) -> dict` as a compatibility wrapper calling the two functions until all callers migrate.

- [ ] **Step 1: Write red equivalence and no-retrieval bootstrap tests.**

```python
def test_bootstrap_persists_user_message_but_does_not_retrieve(mocker, user, conversation):
    retrieve = mocker.patch("request_bootstrap.retrieve")
    result = bootstrap_request(user.id, conversation.id, "借款纠纷", None, False)
    assert result.intent == "legal_query"
    retrieve.assert_not_called()

def test_fast_path_keeps_existing_pre_contract_shape(bootstrap):
    pre = prepare_fast_path(bootstrap)
    assert {"conv_id", "sources", "context", "intent", "recent"} <= set(pre)
```

- [ ] **Step 2: Run red tests.**

Run: `cd backend; python -m pytest tests/test_request_bootstrap.py tests/test_pre_rewrite_order.py -v`

Expected: FAIL because bootstrap and fast preparation are not separated.

- [ ] **Step 3: Move only safe common preparation into `request_bootstrap.py`.**

Move conversation ownership lookup/creation, memory loading, image validation/description, raw-query construction, intent detection, contract-mode context resolution and user-message persistence. Preserve current order: intent is classified on raw input before generic query rewriting. Do not call retrieval, QA cache lookup, answer cache lookup or model selection during bootstrap.

- [ ] **Step 4: Move existing fixed retrieval branches into `prepare_fast_path`.**

Keep exact existing behavior for study, cheating, chitchat, contract, exam and legal-query retrieval. Return the same `pre` keys used by `_build_messages`, `_post`, cache helpers and streaming code. `_pre` becomes a thin function that calls `bootstrap_request` then `prepare_fast_path`.

- [ ] **Step 5: Verify parity and commit.**

Run: `cd backend; python -m pytest tests/test_request_bootstrap.py tests/test_pre_rewrite_order.py tests/test_routing.py tests/test_contract_review.py -v`

Expected: PASS.

Commit: `git add backend/main.py backend/request_bootstrap.py backend/tests/test_request_bootstrap.py backend/tests/test_pre_rewrite_order.py && git commit -m "refactor: split chat bootstrap from fast retrieval"`

**DoD:** The Agent Gate can run before generic retrieval, while legacy Fast Path behavior and existing pre-order guarantees remain tested.

## Task 6: Implement an explainable Gate in Shadow Mode

**Files:**
- Create: `backend/agent/gate.py`
- Modify: `backend/settings.py`
- Modify: `backend/main.py`
- Create: `backend/tests/test_agent_gate.py`
- Modify: `backend/observability.py`
- Modify: `backend/routing_metrics.py`

**Interfaces:**
- Produces `AgentGateDecision(mode: Literal["fast_path", "agent_path", "clarify", "refuse"], complexity: str, reason_codes: list[str])`.
- Produces `decide_gate(bootstrap: RequestBootstrap) -> AgentGateDecision`.

- [ ] **Step 1: Write red Gate tests.**

```python
def test_exact_article_stays_fast_path():
    assert decide_gate(bootstrap("民法典第679条是什么")).mode == "fast_path"

def test_multiple_issues_and_missing_fact_are_agent_path():
    decision = decide_gate(bootstrap("三年前借钱，对方承认过债务，现在还能起诉吗"))
    assert decision.mode == "agent_path"
    assert {"MULTI_ISSUE", "MISSING_FACTS"} <= set(decision.reason_codes)
```

- [ ] **Step 2: Run red Gate tests.**

Run: `cd backend; python -m pytest tests/test_agent_gate.py -v`

Expected: FAIL because Gate rules and metrics do not exist.

- [ ] **Step 3: Implement deterministic rules and safe-off settings.**

Add `agent_enabled: bool = False`, `agent_shadow_enabled: bool = False`, `agent_traffic_percent: int = 0`, and bounded max-step settings to `Settings`. Validate traffic percent is 0–100. Gate rules use intent, exact-article recognition, document/contract presence, multi-issue cues, multi-turn evidence and fact-gap cues. Return stable reason codes, never natural-language reasons as policy input.

- [ ] **Step 4: Wire Shadow Mode without changing visible answers.**

After bootstrap and before `prepare_fast_path`, run the Gate only when `agent_shadow_enabled` is true. Record `agent_gate_mode`, reason codes and a stable request/run correlation id; always continue through `prepare_fast_path`. Do not create a background LLM call in this task.

- [ ] **Step 5: Verify green and commit.**

Run: `cd backend; python -m pytest tests/test_agent_gate.py tests/test_routing_metrics.py tests/test_routing.py -v`

Expected: PASS.

Commit: `git add backend/agent/gate.py backend/settings.py backend/main.py backend/observability.py backend/routing_metrics.py backend/tests/test_agent_gate.py && git commit -m "feat: add explainable legal agent shadow gate"`

**DoD:** Gate decisions are repeatable, visible answers remain unchanged in Shadow Mode, and every decision has machine-readable reason codes.

## Task 7: Implement the bounded research controller and deterministic evaluator

**Files:**
- Create: `backend/agent/planner.py`
- Create: `backend/agent/evaluator.py`
- Create: `backend/agent/controller.py`
- Create: `backend/tests/test_agent_controller.py`
- Create: `backend/tests/test_agent_evaluator.py`

**Interfaces:**
- Produces `AgentController.run(run_id: str, bootstrap: RequestBootstrap) -> ControllerResult`.
- Produces `EvidenceEvaluator.evaluate(state: LegalAgentState) -> EvaluationDecision`.
- Consumes only `PlanDecision` and `ToolGateway.execute`; it never calls retrieval or LLM clients directly.

- [ ] **Step 1: Write red controller tests using fake Planner and Gateway.**

```python
def test_controller_stops_after_evidence_is_sufficient(fake_repository):
    controller = AgentController(planner=SequencePlanner([retrieve_decision(), finish_decision()]), gateway=EvidenceGateway())
    result = controller.run(run_id="r1", bootstrap=bootstrap())
    assert result.state.status is AgentStatus.DRAFTING
    assert result.state.tool_calls == 1

def test_budget_exceeded_returns_explicit_safe_result():
    controller = AgentController(planner=RepeatingPlanner(), gateway=NoopGateway())
    result = controller.run(run_id="r1", bootstrap=bootstrap())
    assert result.degraded_reason == "AGENT_BUDGET_EXCEEDED"
```

- [ ] **Step 2: Run red tests.**

Run: `cd backend; python -m pytest tests/test_agent_controller.py tests/test_agent_evaluator.py -v`

Expected: FAIL because controller and evaluator do not exist.

- [ ] **Step 3: Implement deterministic evaluator before an LLM planner.**

The evaluator checks: required fact presence, at least one primary law evidence item, unresolved critical conflict and per-issue evidence links. Its outcomes are `SUFFICIENT`, `MISSING_FACT`, `MISSING_EVIDENCE`, `CONFLICT`, or `FAIL_SAFE`. It selects at most one outcome-changing unknown fact for clarification. It does not grade prose quality.

- [ ] **Step 4: Implement the controller loop with durable checkpoints.**

For every decision: persist `PLANNING`, validate the typed decision, persist `EXECUTING`, call the gateway, persist observation/evidence, persist `EVALUATING`, then invoke the deterministic evaluator. The first production planner may use a structured-output model only after its parser rejects unknown tools, unknown issue ids and ownership fields. A parse failure becomes `PLANNER_PARSE_ERROR` and follows the explicit fallback policy.

- [ ] **Step 5: Add failure-path tests and verify green.**

Test tool timeout, duplicate action, invalid planner tool, missing primary evidence, conflict, parse error and exhausted budget. Run:

`cd backend; python -m pytest tests/test_agent_controller.py tests/test_agent_evaluator.py tests/test_agent_state_machine.py tests/test_tool_gateway.py -v`

Expected: PASS.

Commit: `git add backend/agent/planner.py backend/agent/evaluator.py backend/agent/controller.py backend/tests/test_agent_controller.py backend/tests/test_agent_evaluator.py && git commit -m "feat: add bounded evidence-driven agent controller"`

**DoD:** No controller path can execute an unregistered tool, repeat an action indefinitely or end a supported Issue without the evaluator's required evidence checks.

## Task 8: Add WAITING_USER resume semantics without creating a new task

**Files:**
- Modify: `backend/schemas.py`
- Modify: `backend/agent/controller.py`
- Modify: `backend/agent/repository.py`
- Modify: `backend/main.py`
- Create: `backend/tests/test_agent_resume.py`

**Interfaces:**
- Adds `agent_run_id: str | None` to `ChatIn` with UUID validation.
- Produces `resume_with_user_fact(run_id, user_id, conversation_id, answer: str) -> LegalAgentState`.
- Emits `clarification` SSE data with `run_id`, prompt text and `issue_id`; never includes an internal rationale.

- [ ] **Step 1: Write red resume tests.**

```python
def test_resume_adds_sourced_fact_and_keeps_same_run(client, waiting_run):
    response = client.post("/api/chat", json={"conversation_id": waiting_run.conversation_id, "agent_run_id": waiting_run.id, "content": "约定了2023年1月还款"})
    assert response.status_code == 200
    assert get_run(waiting_run.id).state_version > waiting_run.state_version
    assert sourced_fact(get_run(waiting_run.id), "user").statement == "约定了2023年1月还款"

def test_resume_rejects_other_users_run(client, waiting_run_for_other_user):
    response = client.post("/api/chat", json={"conversation_id": 1, "agent_run_id": waiting_run_for_other_user.id, "content": "x"})
    assert response.status_code == 404
```

- [ ] **Step 2: Run red tests.**

Run: `cd backend; python -m pytest tests/test_agent_resume.py -v`

Expected: FAIL because no resume contract exists.

- [ ] **Step 3: Implement one-question, owned-run resume.**

Only a run in `WAITING_USER` may resume. The server checks the run belongs to the authenticated user and given conversation, stores the input as a user-sourced Fact, clears the pending question, increments state version and transitions to `PLANNING`. An ordinary follow-up without `agent_run_id` does not guess a run to resume.

- [ ] **Step 4: Wire safe SSE and duplicate resume handling.**

On a stale version or a second simultaneous resume request, return a deterministic conflict response without adding a duplicate Fact. The stream sends one `clarification` event when the run pauses and sends `restart` only after a validated resume begins.

- [ ] **Step 5: Verify green and commit.**

Run: `cd backend; python -m pytest tests/test_agent_resume.py tests/test_agent_repository.py tests/test_agent_state_machine.py -v`

Expected: PASS.

Commit: `git add backend/schemas.py backend/agent/controller.py backend/agent/repository.py backend/main.py backend/tests/test_agent_resume.py && git commit -m "feat: resume legal agent after user clarification"`

**DoD:** A key fact resumes exactly one owned run, an unrelated conversation cannot resume it, and duplicate HTTP requests do not duplicate facts or execution.

## Task 9: Add evidence-bounded Writer, independent checks and final deterministic gates

**Files:**
- Create: `backend/agent/writer.py`
- Create: `backend/agent/verifier.py`
- Modify: `backend/prompts.py`
- Modify: `backend/main.py`
- Create: `backend/tests/test_agent_writer.py`
- Create: `backend/tests/test_agent_verifier.py`

**Interfaces:**
- Produces `DraftAnswer(conclusion, issue_analysis, risks, missing_information, claim_checks)`.
- Produces `VerificationResult(verdict: Literal["PASS", "REWRITE", "RESEARCH_MORE", "FAIL_SAFE"], unsupported_claim_ids: list[str])`.
- Consumes only a state with evidence; the Writer cannot receive the original free-form retrieval history.

- [ ] **Step 1: Write red anti-hallucination tests.**

```python
def test_writer_drops_claim_without_evidence():
    draft = writer.render(state_with_claim("一定胜诉", evidence_ids=[]))
    assert "一定胜诉" not in draft.conclusion

def test_verifier_requests_safe_failure_after_one_research_retry():
    state = state_with_verifier_retry_count(1, unsupported_claim=True)
    assert verifier.verify(state).verdict == "FAIL_SAFE"
```

- [ ] **Step 2: Run red tests.**

Run: `cd backend; python -m pytest tests/test_agent_writer.py tests/test_agent_verifier.py -v`

Expected: FAIL because Writer and Verifier do not exist.

- [ ] **Step 3: Implement structured draft generation.**

Build a prompt from verified facts, resolved issues and compact evidence snippets only. Require every substantive claim to carry Evidence IDs. Parse into `DraftAnswer`; reject unknown evidence ids and any Fact text that is not present in the state. On parsing failure return `FAIL_SAFE`, not a raw model response.

- [ ] **Step 4: Implement verifier and finalization order.**

Verifier checks deterministic evidence id membership, important-issue coverage and contradiction markers before optional model-assisted wording review. `RESEARCH_MORE` is allowed once per run; the second failure is `FAIL_SAFE`. In `main.py`, final Agent order is Writer → Agent Verifier → `citation_verify` → `quality.self_check` → `output_normalize` → storage.

- [ ] **Step 5: Verify green and commit.**

Run: `cd backend; python -m pytest tests/test_agent_writer.py tests/test_agent_verifier.py tests/test_citation.py tests/test_quality.py tests/test_output_normalize.py -v`

Expected: PASS.

Commit: `git add backend/agent/writer.py backend/agent/verifier.py backend/prompts.py backend/main.py backend/tests/test_agent_writer.py backend/tests/test_agent_verifier.py && git commit -m "feat: verify legal agent claims against evidence"`

**DoD:** Unsupported claims never pass as supported, verifier feedback cannot create an infinite research loop, and existing citation/quality/output checks still run for Agent answers.

## Task 10: Integrate Agent Path with SSE, explicit fallback and feature flags

**Files:**
- Modify: `backend/main.py:1182-1645`
- Modify: `backend/settings.py`
- Modify: `backend/observability.py`
- Modify: `backend/routing_metrics.py`
- Create: `backend/tests/test_agent_chat_integration.py`
- Create: `backend/tests/test_sse.py`
- Modify: `README.md`

**Interfaces:**
- Produces `should_route_agent(gate, settings, stable_request_seed) -> bool`.
- Emits only declared SSE types: `agent_status`, `agent_step`, `tool_status`, `clarification`, `verification`, `token`, `final`, `error`, `restart`.
- Produces `fallback_to_fast_path(bootstrap, reason_code) -> dict` only for allow-listed technical reasons.

- [ ] **Step 1: Write red integration tests.**

```python
def test_agent_disabled_keeps_fast_path_response(client, complex_query):
    response = client.post("/api/chat", json={"content": complex_query})
    assert sse_types(response.text) == {"status", "content", "sources", "done"}

def test_permission_failure_does_not_fallback_to_fast_path(client, forbidden_agent_run):
    response = client.post("/api/chat", json={"agent_run_id": forbidden_agent_run, "content": "继续"})
    assert response.status_code == 404
    assert "degraded" not in response.text
```

- [ ] **Step 2: Run red integration tests.**

Run: `cd backend; python -m pytest tests/test_agent_chat_integration.py -v`

Expected: FAIL because Agent routing and event schema are not integrated.

- [ ] **Step 3: Wire a stable rollout selector and only allow-listed fallback.**

Hash `user_id + conversation_id + request id` to determine traffic assignment when `agent_enabled` is true and traffic percent is nonzero. Allow fallback only for `PLANNER_PARSE_ERROR`, `TOOL_TIMEOUT`, `TOOL_UNAVAILABLE`, `AGENT_BUDGET_EXCEEDED` and `VERIFIER_TECHNICAL_FAILURE`. Preserve the reason in trace and user-facing limited notice. Never fallback for authentication, ownership, injection, policy, validation or legal-date failure.

- [ ] **Step 4: Emit privacy-safe progress and store final results.**

Send high-level progress labels only; do not stream tool arguments, private document chunks, raw prompts or planner reasoning. Ensure `_post` writes the final answer once. On client disconnect, persist the latest completed state/step but do not leave an unbounded background loop.

- [ ] **Step 5: Verify green and commit.**

Run: `cd backend; python -m pytest tests/test_agent_chat_integration.py tests/test_sse.py tests/test_routing.py -v`

Expected: PASS. `tests/test_sse.py` asserts the Fast Path and Agent Path event contracts.

Commit: `git add backend/main.py backend/settings.py backend/observability.py backend/routing_metrics.py backend/tests/test_agent_chat_integration.py backend/tests/test_sse.py README.md && git commit -m "feat: route bounded legal agent through chat SSE"`

**DoD:** The default deployment remains Fast Path, the Agent route is deterministic per rollout seed, events disclose no reasoning or private tool inputs, and forbidden failures cannot bypass policy via RAG fallback.

## Task 11: Run Shadow evaluation, release gates and operational rollback rehearsal

**Files:**
- Modify: `docs/BENCHMARK.md`
- Modify: `docs/ADR.md`
- Create: `docs/runbooks/legal-agent-v1-rollout.md`
- Create: `backend/scripts/check_agent_release.py`
- Create: `backend/tests/test_agent_release_check.py`

**Interfaces:**
- Produces `check_agent_release(existing: Path, agent: Path) -> ReleaseCheck` with explicit failure reasons.
- Reads frozen evaluation outputs only; it does not invoke a model.

- [ ] **Step 1: Write red release-gate tests.**

```python
def test_release_check_rejects_unsupported_claim_and_loop():
    report = check_agent_release(existing_report(), agent_report(fact_hallucinations=1, infinite_loops=0))
    assert report.allowed is False
    assert "FACT_HALLUCINATION" in report.reasons

def test_release_check_rejects_dataset_hash_mismatch():
    report = check_agent_release(existing_report(freeze_hash="a"), agent_report(freeze_hash="b"))
    assert report.allowed is False
    assert report.reasons == ["FREEZE_HASH_MISMATCH"]
```

- [ ] **Step 2: Run red release-check tests.**

Run: `cd backend; python -m pytest tests/test_agent_release_check.py -v`

Expected: FAIL because release check does not exist.

- [ ] **Step 3: Implement non-negotiable release checks.**

The script rejects: mismatched dataset hash, any fact hallucination on critical facts, any permission bypass, any infinite loop, any illegal citation, absent reproducibility metadata, or Agent complex-task quality below Existing RAG. It reports Agent Gain, issue recall, evidence coverage, clarification precision, p50/p90 latency, tool calls and budget-exceeded rate without inventing pass thresholds not backed by the frozen rubric.

- [ ] **Step 4: Write the rollout and rollback runbook.**

Document: preflight backup and restore rehearsal; Shadow Gate observation; Shadow Traffic comparison; rollout at 5%, 10%, 25%, 50%, 100%; observation window and dashboard fields; stop conditions; `AGENT_ENABLED=false` and `AGENT_TRAFFIC_PERCENT=0` rollback; post-rollback trace retention and incident triage. Require a human approval recorded in the deployment log at each percentage change.

- [ ] **Step 5: Verify release script, complete full regression and commit.**

Run: `cd backend; python -m pytest tests/test_agent_release_check.py -v`

Expected: PASS.

Run: `cd backend; python -m pytest -q`

Expected: PASS; record the exact test count rather than copying a historic number.

Run: `cd backend; ruff check .; mypy .`

Expected: PASS or only pre-existing, documented baseline exclusions from `pyproject.toml`.

Commit: `git add docs/BENCHMARK.md docs/ADR.md docs/runbooks/legal-agent-v1-rollout.md backend/scripts/check_agent_release.py backend/tests/test_agent_release_check.py && git commit -m "docs: add legal agent release gates and rollback runbook"`

**DoD:** No rollout can claim success without same-hash comparison, traceable reports, all blocking safety checks clear, backup/restore rehearsal evidence and explicit human approval.

## Final plan self-review

- Spec coverage: Tasks 1–11 cover frozen evaluation, persistent state, typed tools, gate, loop, clarification, verification, SSE, fallback, observability, rollout and rollback. V1 non-goals are global constraints.
- Placeholder scan: all tasks name concrete files, interfaces, focused tests, commands and expected results. No task relies on an implicit schema or undefined tool.
- Type consistency: `LegalAgentState` is defined before repository/controller consumption; typed tool inputs flow through `PlanDecision` and `ToolGateway`; `AgentRun` ownership and state version are used consistently by resume and integration tasks.
- Scope control: UI redesign, multi-agent, LangGraph, public web search, agent write tools and horizontal scaling are explicitly excluded.
