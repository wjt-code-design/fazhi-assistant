# Agent V2 架构优化执行书（L1/L2/L3 根因修复）

> 日期：2026-09-09
> 上游证据：`docs/v1-candidate-fix-options-20260908.md` §5（run-1~8 全 0/10，停损已触发）、
> run-8 取证（dispatch-output/root_cause_analysis.py、inspect_steps.py、inspect_evidence.py 输出）
> 执行者：后续实施助手 ｜ 验收者：独立审核助手 / Owner
> 性质：**架构级修复，非补丁**——上一候选已按停损纪律回滚（1b5a96c），本执行书是结构性差距的正面对策。

## 0. 根因结论（已固化证据，执行者不必重查）

| 层 | 根因 | 实测证据 | 杀伤率 |
|---|---|---|---|
| **L1** | Planner JSON 结构化输出失败，死亡点集中在"研究结束→转终稿"决策（controller.py:437 的 decide 调用） | run-8 中 7/10 死于 PLANNER_PARSE_ERROR；步骤表显示全部发生在检索/澄清已成功之后的下一个决策点；F3 提示增强实验反证（3/10→7/10，提示词修不了） | 70% |
| **L2** | 法条级引用召回缺口：(a) planner 检索查询不按争点扇出（C10：全刑法查询，0 民法查询，缺民法典577）；(b) 检索 top-k 无文章级精度（C09：召回消法53/41 但非金标消法26） | C09 成功题 11 条证据仍缺 1/4 金标；C10 证据全偏科 | 幸存者 ~90% |
| **L3** | 16 步预算被 2 轮澄清 + 回喂重试吃掉，仅剩 2-3 次检索 | 成功会话内 CLARIFY_BUDGET_EXHAUSTED 频出 | 放大器 |

**核心对策**（编号 G1-G5，前 3 项为纯工程，后 2 项为 Owner 决策项）：

- **G1 确定性终稿门**：把"是否转终稿"从 LLM 手里拿走——预算耗尽/证据已足时服务端直接裁定，跳过 planner 调用（打 L1）。
- **G2 争点强制检索扇出**：分解出的每个 issue 在进入 planner 循环前先做一次 issue 定向检索（打 L2a）。
- **G3 检索文章级重排**（可选增强）：retrieve_laws 结果按 issue 相关性重排再截断（打 L2b）。
- **G4 预算重分配**（Owner 决策）：max_steps 16→24。
- **G5 评测金标松绑**（Owner 决策）：必需依据命中阈值从"全部"松为"≥3/4 或语义等价"。

## 1. 执行边界

### 1.1 必须完成（工程项）

1. G1 确定性终稿门（controller.py，含单测，先红后绿）。
2. G2 争点强制检索扇出（controller.py + gateway 复用，含单测，先红后绿）。
3. run-9 验证轮（LongCat，两层 judge 判定，不择优）。

### 1.2 明确禁止

- 不改冻结物：frozen-cases/round-protocol/rubric/fact-ids、hidden-*、历史 sessions（run-1~8 是对照基线）。
- 不改评测器（gate5_judge.py 两层判定已纠偏冻结；G5 若获批由 Owner 下另书）。
- 不改 prompt 文本（F3 已证提示增强为回归，本执行书不动 `_PLANNER_SYSTEM_PROMPT`）。
- 不调除验证轮（run-9 一轮）外的任何在线模型；验证轮前须 Owner 确认。
- 不实现 G4/G5（配置与决策项，见 §4）。

### 1.3 现有锚点（精确位置）

| 锚点 | 位置 | 说明 |
|---|---|---|
| planner 决策循环 | `backend/agent/controller.py:432` `while True:` | G1 门插入点（decide 之前） |
| parse 失败 fail-closed | `backend/agent/controller.py:446-478` | 保留不动（回喂仍有效） |
| 评估器 | `backend/agent/evaluator.py:48-95` | `evaluate()`：MISSING_FACT(:67)/MISSING_EVIDENCE(:86)/SUFFICIENT(:92) |
| 工具执行 | `backend/agent/controller.py:480-494` | `decision` 为 ToolCallDecision 时 `_execute_tool` |
| 预算 | `backend/agent/schemas.py:195-199`；`.env AGENT_MAX_STEPS=16` | `max_steps`/`max_clarifications` |
| 检索工具 | `backend/tools/gateway.py` ToolGateway | `retrieve_laws(query, k)` 现成可用 |

## 2. G1：确定性终稿门（Task 1-2）

### 设计

在 `while True:` 循环体**最顶端**（planner.decide 之前）加服务端判定：

```python
forced = self._deterministic_finish_gate(run.state)
if forced is not None:
    # 确定性终稿门（V2-G1）：不再让 LLM 决定"何时转终稿"。
    # 触发条件（满足其一）：
    #   A. 评估器判 SUFFICIENT（每 issue 有有效成文法证据且无未知关键事实）→ 直接 DRAFTING；
    #   B. 澄清预算已耗尽 且 每个 issue 已至少挂 1 条证据 → 强制 DRAFTING（条件化分析）。
    # 两者都绕过 planner.decide，消灭 run-8 的主死亡模式。
    handled = self._handle_evaluation(run, forced)
    if isinstance(handled, ControllerResult):
        return handled
    # handled 是 ControllerRun：状态已被推进（如转 DRAFTING）。
    # 必须跳出本循环，交由 run() 的状态分派处理新状态——继续循环会导致门重入
    # （状态若仍在 PLANNING 且评估结果不变 → 死循环）。
    run = handled
    break
```

**前置核实步骤（已完成，2026-09-09 复查 controller.py:642-712）**：
- [x] `_handle_evaluation` 对 `SUFFICIENT` 返回 **ControllerResult**（`transition(run.state, DRAFTING)` + `_save`，:648-655）——**永不返回 ControllerRun**，门合并语义成立，无需改设计。
- [x] `MISSING_FACT` + 预算耗尽时，`_handle_evaluation` 已含 `CLARIFY_BUDGET_EXHAUSTED` → 转 DRAFTING 分支（:657-672）——**B 条件可直接复用，无需新造状态转换**。
- [x] `MISSING_EVIDENCE`/`CONFLICT` → `_handle_evaluation` 走 `register_replan` 返回 **ControllerRun(PLANNING)**（:694-708）——门若放行该类会自触发死循环，**门函数因此只捕获 SUFFICIENT 与（MISSING_FACT+耗尽+有证据）两类**（见下方实现）。
- [ ] `_execute_tool` 失败路径返回类型（G2 用）：**待 Task 3 核查**（读到 :480-494 附近确认）。

**门函数（新方法，controller.py 内）**：

```python
def _deterministic_finish_gate(self, state: LegalAgentState) -> EvaluationDecision | None:
    """V2-G1：LLM 决策前置的确定性闸门。返回非 None 表示跳过 planner。"""
    evaluation = self._evaluator.evaluate(state)
    if evaluation.outcome is EvaluationOutcome.SUFFICIENT:
        return evaluation  # A：证据已足，无需再问 planner"下一步"（_handle_evaluation 会转 DRAFTING 返回结果）
    # B：MISSING_FACT + 澄清预算耗尽 + 每 issue 至少 1 条证据 → 强制条件化（转 DRAFTING）。
    #    注意 B 只捕获 MISSING_FACT：若评估结果是 MISSING_EVIDENCE/CONFLICT，
    #    _handle_evaluation 会走 replan 回到 PLANNING（:698），门放行它会造成自触发死循环——故不捕获。
    if (
        evaluation.outcome is EvaluationOutcome.MISSING_FACT
        and self._clarify_budget_exhausted(state)
        and self._every_issue_has_evidence(state)
    ):
        return evaluation
    return None
```

**实现要点**（执行者注意）：
- "澄清预算已耗尽"的判定复用 `_handle_evaluation` MISSING_FACT 分支内已有的同款逻辑（controller.py:657 附近，`CLARIFY_BUDGET_EXHAUSTED` 的触发条件），抽成 `_clarify_budget_exhausted(state) -> bool` 供两处共用——**不要写第二份预算判定**（单一真源）。
- `_every_issue_has_evidence(state)`：`all(any(obs.issue_id == i.issue_id and obs.status == "succeeded" and obs.evidence_ids for obs in state.observations) for i in state.issues)`。
- 门只在 `AgentStatus.PLANNING` 下生效（循环入口已在 PLANNING 分支内，天然满足）。
- **fail-closed 不弱化**：门未触发时走原 planner 路径（含回喂重试），一切既有失败保护保留。
- **死循环防护**：门触发 → `_handle_evaluation` 返回 ControllerRun 后必须 `break` 出决策循环（见上方调用点代码注释）；若 break 后状态仍为 PLANNING（理论不该发生），由 run() 顶部的状态分派兜底报错而非静默重试。

### Task 1：G1 红测试

**Files:** Modify `backend/tests/test_agent_controller.py`（追加，不动既有用例）

**先写失败测试（旧实现无门 → planner 被调用 → 用 SequencePlanner 断言"不该被问到"）：**

```python
def test_g1_deterministic_gate_skips_planner_when_sufficient():
    """G1 红：评估器判 SUFFICIENT 后，planner 不应再被调用（旧实现会调用 → 红）。
    构造：初始状态已含 issue+有效成文法证据+observation，无 unknown_facts → evaluate()=SUFFICIENT。
    """
    repository = FakeRepository(sufficient_state())   # 见步骤 2 的 fixture 构造
    planner = SequencePlanner([])                    # 空决策列表：被调用即 AssertionError
    gateway = RecordingGateway()

    result = controller(repository, planner, gateway).run("run-a", bootstrap())

    assert result.state.status in (AgentStatus.DRAFTING, AgentStatus.COMPLETED)


def test_g1_gate_forces_drafting_when_clarify_exhausted_and_evidence_present():
    """G1 红：澄清预算耗尽 + 每 issue 有证据 → 不问 planner，直接条件化转 DRAFTING。"""
    repository = FakeRepository(exhausted_with_evidence_state())
    planner = SequencePlanner([])  # 任何 decide 调用都会 AssertionError → 证明门生效
    gateway = RecordingGateway()

    result = controller(repository, planner, gateway).run("run-a", bootstrap())

    assert result.state.status is AgentStatus.DRAFTING
```

- [ ] 步骤 1：在 test 文件顶部加 fixture 构造器 `sufficient_state()` / `exhausted_with_evidence_state()`（复用既有 `initial_state()` 改造：附 STATUTE 类型、EFFECTIVE 的 Evidence + succeeded Observation；后者把 clarify 预算用满的 state 即 `budgets=AgentBudgets(max_clarifications=0)` + 证据齐全 + 保留 unknown_facts）。
- [ ] 步骤 2：`venv\Scripts\python.exe -m pytest tests/test_agent_controller.py -k g1 -q` → **预期 FAIL**（旧实现 planner 被调用，SequencePlanner([]) 抛 AssertionError；或状态停在 PLANNING）。保存输出为 red 证据。
- [ ] 步骤 3：实现 `_deterministic_finish_gate` + 循环顶端插入（上面的设计代码；`_clarify_budget_exhausted` 从 `_handle_evaluation` 抽取共用）。
- [ ] 步骤 4：重跑 → **PASS**；再跑全量 `tests/test_agent_controller.py -q` → 全绿（**关键回归**：既有 `test_parse_error_is_explicit_degraded_failure_and_never_calls_gateway` 等不能破——那些状态不满足门条件，门必须放行到 planner 路径）。
- [ ] 步骤 5：`git commit -m "feat(agent): V2-G1 确定性终稿门——SUFFICIENT/预算耗尽时跳过 planner 决策（打 L1 parse 死亡点）"`

### Task 2：G1 门覆盖负例

- [ ] 步骤 1：追加测试 `test_g1_gate_off_when_no_evidence_yet`（无任何证据时门不触发，planner 正常被调用，`SequencePlanner([tool_decision()])` 走通一轮）。
- [ ] 步骤 2：跑红→绿（若直接绿说明负例构造不严，收紧断言：planner.calls 非空）。
- [ ] 步骤 3：commit。

## 3. G2：争点强制检索扇出（Task 3-4）

### 设计

run-8 取证：C10 的 planner 只做了刑法向查询，民法向（民法典577）零查询 → 证据偏科。修复：**分解完成后、planner 循环开始前，对每个尚无证据链接的 issue 强制执行一次 issue 定向检索**（确定性、服务端发起、query=issue.question——已是用户语言，检索友好）。

插入点：controller.py `run()` 中进入 PLANNING 循环前（:425 `structural = ...` 之前）：

```python
# V2-G2 争点强制扇出：每个无证据 issue 先做一次定向检索，消灭"只查一个角度"的偏科。
run = self._seed_issue_retrievals(run)
```

新方法（类型已核对：`ToolCallDecision` 见 `backend/agent/schemas.py:144`（BaseModel，`kind` 有默认值），`RetrieveLawsInput` 见 `backend/tools/contracts.py:75`（`query: str`、`k: int = 4`））：

```python
def _seed_issue_retrievals(self, run: ControllerRun) -> ControllerRun:
    """V2-G2：对每个尚无成功 observation 证据的 issue 执行一次 retrieve_laws(query=issue.question)。
    构造 ToolCallDecision 走 _execute_tool 既有路径（重复去重/预算/fail-closed 全保留），不绕过 gateway。
    """
    for issue in run.state.issues:
        linked = any(
            obs.issue_id == issue.issue_id and obs.status == "succeeded" and obs.evidence_ids
            for obs in run.state.observations
        )
        if linked:
            continue
        decision = ToolCallDecision(
            issue_id=issue.issue_id,
            tool_name="retrieve_laws",
            args=RetrieveLawsInput(query=issue.question, k=4),
        )
        outcome = self._execute_tool(run, decision)
        if isinstance(outcome, ControllerResult):
            # 工具执行把状态推到终态（如 fail-closed/预算停）：扇出提前结束，返回当前 run
            return run
        run = outcome
        if run.state.status is not AgentStatus.PLANNING:
            break  # 评估器已推进状态（如转 DRAFTING），后续 issue 无需再扇出
    return run
```

**实现要点**：
- `ToolCallDecision`/`RetrieveLawsInput` 的精确构造方式参照 controller 既有 import 与 `parse_plan_decision` 的产物类型（执行时先读 `agent/planner.py` 确认构造签名，**以实际类型为准**，勿按本文伪代码盲写）。
- `_execute_tool` 内部已有 duplicate-action 指纹去重（gateway.py:190），同一 issue 不会重复检索。
- 每次扇出后状态可能被 `_handle_evaluation` 推进（tool 执行路径里已含评估），要跟随 `run` 的最新引用。
- 扇出产生的额外步骤计入 steps 预算（G4 未批时 16 步内约余 2-3 次检索 + 扇出 N issue，需在验证轮观测是否触发 BUDGET_EXCEEDED——若大面积触发，那是 G4 的决策证据，不是本任务缺陷）。

### Task 3：G2 红测试

```python
def test_g2_issue_fanout_retrieves_for_evidence_less_issues():
    """G2 红：进入 PLANNING 后，无证据 issue 应被自动扇出检索（旧实现不扇出 → planner 才是唯一检索发起者）。
    断言：gateway 收到 retrieve_laws 调用，且 query 含 issue.question 关键词；planner 不必先被调。
    """
    repository = FakeRepository(initial_state())  # 含 issue-a"诉讼时效"，无证据
    planner = SequencePlanner([])                 # planner 零调用：扇出+评估即可推进（构造 state 使扇出后 SUFFICIENT）
    gateway = RecordingGateway()

    result = controller(repository, planner, gateway).run("run-a", bootstrap())

    assert any("诉讼时效" in str(call) for call in gateway.calls)  # 扇出检索确实发生
```

- [ ] 步骤 1：写红测试（RecordingGateway 的 calls 结构先读 fixture 确认断言形式）。
- [ ] 步骤 2：跑 → FAIL（旧实现扇出不存在，gateway.calls 为空/靠 planner）。
- [ ] 步骤 3：实现 `_seed_issue_retrievals` + 插入调用。
- [ ] 步骤 4：全量 controller 测试回归全绿。
- [ ] 步骤 5：commit `feat(agent): V2-G2 争点强制检索扇出——每 issue 至少一次定向检索，消灭证据偏科（打 L2a）`。

### Task 4：G3 检索文章级重排（可选，时间盒 1 次实现尝试）

仅当 run-9 后 G2 已生效但 coverage 仍 >3/10 时实施。方案：`backend/retrieval*.py` 在返回前按"条款标题与 query 的字段重叠度"做轻量重排（确定性，无 LLM）。**若 run-9 数据不支持（召回本已含金标但未被引用），G3 判 NOT_NEEDED 并记录**——避免为不存在的问题写代码。

## 4. G4/G5/G6：Owner 决策项（不实施，仅决策件）

| 项 | 内容 | 建议默认 |
|---|---|---|
| G4 | `.env AGENT_MAX_STEPS=16 → 24`（G2 扇出按 issue 数吃 steps 预算；扇出是本地向量库检索，延迟成本近零，瓶颈只在步数配额） | 建议批准；批准后随 run-9 一并生效 |
| G5 | 金标口径：`required_laws 全命中` → `≥75% 命中或语义等价条款命中`（C09 按新口径即通过；需改 gate5_judge 判定 + 任务书 §6.8 措辞） | 建议保守：**先按原口径跑 run-9 拿数据**，若 G1/G2 生效后仍卡在"仅缺 1 条"再松绑 |
| G6 | 生成模型升级或结构化输出 API：优先**先查 LongCat 是否支持 `response_format`/json_schema**（若支持，配置级改动可能比 G1 更便宜且无代码风险）；不支持再评估换模型（qwen-max/DeepSeek 等）。V1 任务书 §3.7 的"评测用 LongCat"是 V1 冻结要求非永久约束；回喂机制已证模型无关。 | 缓议：先跑 G1/G2 验证 run-9；若 parse 残余仍 >1/10，G6 升级为首选 |

### 4.1 已考虑并否决/延后的替代方案（ADR 摘要）

| 替代 | 权衡 | 结论 |
|---|---|---|
| **plan-then-execute**（LLM 只在开头产一次研究计划，执行全确定性） | 比 G1 更彻底地消灭 parse 失败；但改动面大（重写决策循环），且 V1 任务书 §3.1 冻结"不重写 Agent"，V2 立项时才可议 | 延后：若 G1/G2 后 parse 仍 >1/10，升为 V2 首选架构方案 |
| **检索查询多路复用**（单次 retrieve_laws 发多 query） | 一次调用覆盖多角度；但需改 contracts/gateway 输入 schema，且与"每 issue 定向"的语义重叠 | 否决：G2 扇出已覆盖，避免为同一问题留两个入口 |
| **提高 k（4→12）** | 一行配置；但会稀释证据质量（writer 要在更多噪声里选） | 否决：C09 证据 11 条已含噪声（保险法无关条款），增 k 恶化信噪比 |

## 5. 验证协议（run-9）

1. 前置快照纪律：HEAD + git status + 服务启动时间（带 `AGENT_ENABLED=true`）+ runner sha；G4 若获批一并生效并记录。
2. `gate2_runner.py --run gate5-dev-run-9 --all`（LongCat 单轮，不重试择优）。
3. 两层 judge 判定：`gate5_judge.py .../gate2-run-gate5-dev-run-9-sessions.json`。
4. **判据**（相对 run-6/8 的三主轴；指标 2 用金标命中率而非"每 issue 有证据"——后者会被 G2 扇出自动满足，属自证代理目标）：
   - PLANNER_PARSE_ERROR ≤ 1/10（G1 直接效果，run-8 为 7/10）；
   - **金标法条命中改善**：两层 judge 的 `missing_required_statute_ids` 总条数相对 run-8 显著下降（run-8 基线 = 15 条缺失，按 judge 输出逐题手工加总：C01=4/C02=2/C03=0/C04=2/C05=0/C06=1/C07=2/C08=1/C09=1/C10=2；目标 < 8 条），且无证据偏科题（C10 类"某法律域 0 命中"消失）；
   - full_closure 相对 0/10 有实质抬升（mechanical 只作诊断）。
5. **停止条件**：parse 仍 ≥4/10 → G1 门未覆盖实际死亡路径，回根因（读 sessions 的 rounds 与 steps 表定位门为何未触发）；同一缺陷连续 2 轮修复仍无改善 → 停，升级 Owner 复评。

## 6. DoD

- [x] **G1 两用例红→绿 + controller 全量回归绿 + 既有 fail-closed 用例不破**（提交 5b4449b；红证据 dispatch-output/harness-red-green/g1-red.log）
- [x] **G2 用例红→绿 + 扇出经 gateway 正常路径（指纹去重生效）**（提交 65b000a；红证据 dispatch-output/harness-red-green/g2-red.log；RecordingGateway 升级 empty/outputs 模式，chat_integration 15 用例同步适配并全绿）
- [ ] 单测合计新增 ≥3 用例，全仓 5 文件回归 145+ 全绿（controller 50 全绿；全仓现含既有基线失败 23 项：writer 21 + agent_gate 1 + agent_resume 1，均与 G1/G2/方案A 无关，stash 验证确认）
- [x] **方案 A（G6）接入 + run-10 全量判定落盘 + 与 run-6/8/9 对照表写入附录**（提交 fc47bd2 + 65b000a；见附录 A）
- [x] 未改任何冻结物/评测器/prompt；`git diff --check` 干净
- [ ] G3 做了或明确记 NOT_NEEDED（附证据）——待 run-11（G2 生效后）数据判定
- [ ] G4/G5 决策状态在本文档 §4 更新（批/不批/缓议）——见附录 A（run-10 数据显示 G4/G5 决策被激化）

## 附录 A：方案 A 接入实测与 run-10 判定（2026-09-09）

### 方案 A 接入验证（ADR 边界从"简单 schema"到"真实 prompt/联合 schema"）

- **发现并修复实现缺陷 1**：`PlanDecision.model_json_schema()` 对 `Annotated[Union[...], Field(discriminator)]`
  抛 AttributeError 被 `_invoke_planner` 的 except 静默吞掉 → **方案 A 从未真正绑定过 response_format**。
  改用 `TypeAdapter(PlanDecision).json_schema()`（探测复现：probe_longcat_planner_direct.py）。
- **发现并修复 schema 缺陷 2**：`ToolCallDecision.args: SerializeAsAny[BaseModel]` 在 schema 中编码为空
  对象 → LongCat 只能输出 `args:{}` → parse 校验失败。请求层注入具体工具输入联合
  （RetrieveLawsInput|LookupArticleInput|ContractInput|RetrieveMemoryInput）后 LongCat 正确填出
  `{"query":"…","k":4}`（probe_longcat_args_inject.py）。
- **生产链路实测**：ChatOpenAI（streaming=True，与 llm_registry._build 一致）+ `bind(response_format)` +
  `decide()` + `parse_plan_decision` 全链路通过（probe_longcat_planner_bind.py）。

### run-10 判定（方案 A 全量，LongCat，两层 judge）

| 主轴 | run-6 | run-8 | run-9(G1) | run-10(A) | 判定 |
|---|---|---|---|---|---|
| PLANNER_PARSE_ERROR | 3/10 | 7/10 | 4/10 | **0/10** | ✅ L1 判据达成（≤1/10） |
| EVIDENCE_COVERAGE_DEFICIENT（verifier 判定） | - | 2/10 | 3/10 | **8/10** | ⚠️ L2 成为主失败面 |
| GENERATOR_FAILURE | - | 0 | 0 | 1/10（C06） | - |
| has_final（final_chars>0） | - | 8/10 | 5/10 | 1/10 | ❌ 全局闭环未随 L1 修复抬升 |
| full_closure（两层 judge） | - | 0/10 | 0/10 | 0/10 | ❌ 仍 0/10 |

**解读**：方案 A 彻底消灭了 L1 parse 死亡面（7/10→0/10），但幸存者失败面暴露为 **L2 法条级引用召回缺口**
（EVIDENCE_COVERAGE_DEFICIENT 2/10→8/10）——即会话能跑到终稿，但 verifier 判定证据覆盖不足。
run-10 missing_required_statute_ids 总数 = 28（C01=4/C02=3/C03=2/C04=3/C05=2/C06=3/C07=3/C08=4/C09=2/C10=2），
相对 run-8 的 15 条不降反升——**直接证据：G2 扇出（每 issue 至少一次定向检索）是本轮之后必补的对策**。

**决策更新（§4 G4/G5）**：
- G2 已于 65b000a 实施（本表之后），run-11 验证 G2 是否兑现"每 issue 有证据"→ 降低 coverage 失败面。
- G4（max_steps 16→24）：run-10 中多数会话死于 verifier coverage 而非预算，G4 不再是当务之急；若 run-11 扇出吃预算触发 BUDGET_EXCEEDED 再批。
- G5（金标 ≥75% 命中松绑）：run-10 的 missing 结构与 run-8 同构（多缺 1 条类），保持"先按原口径跑 run-11"。

## 附录 B：run-11 判定（G2 生效，2026-09-09 15:47 落盘）

（在附录 A run-10 判定的同一服务上跑；HEAD=ebe82e2，服务 14:06 启动于 65b000a 之后 → G2 代码生效；冻结物/评测器/prompt 未改）

| 主轴 | run-8 | run-9(G1) | run-10(A) | run-11(G2) | 判定 |
|---|---|---|---|---|---|
| PLANNER_PARSE_ERROR | 7/10 | 4/10 | 0/10 | **0/10** | ✅ 维持（G1+方案A 无回退） |
| EVIDENCE_COVERAGE_DEFICIENT | 2/10 | 3/10 | 8/10 | **6/10** | ⚠️ 略降但仍是主失败面；G2 未兑现"每 issue 有证据→coverage 下降"的预期 |
| ISSUE_DECOMPOSITION_INVALID | - | - | 0 | **1/10**（C07） | ❌ **新失败面**（首次出现，见下） |
| GENERATOR_FAILURE | - | 0 | 1/10 | **2/10**（C01/C10） | ⚠️ 上升 |
| has_final（final_chars>0） | - | 5/10 | 1/10 | **1/10**（仅 C09） | ❌ 无改善 |
| full_closure | 0/10 | 0/10 | 0/10 | **0/10** | ❌ 仍 0/10 |

**实证**：G2 扇出**确实生效**（DB agent_steps 取证：C02 conv=2308 三个 issue 在 state_v2/v7/v11 各触发一次 `retrieve_laws`，全部 TOOL_SUCCEEDED，10 条证据物化）。
且 C02 证据表**已含金标法条**（劳动法44、劳动争议调解仲裁法27）——**检索召回已覆盖金标**，但 final 仍被拒。

**根因转移结论**：L2a（检索偏科）已基本打掉（扇出把金标法条召回了证据表）；
但**新死亡点在"writer 生成 → verifier 判定"链路**：
- verifier EVIDENCE_COVERAGE_DEFICIENT（verifier.py:298-304）要求每 issue 的 claim **绑定有效成文法证据**——检索到了≠writer 正确引用；
- 6/10 会话 final 文本因 verifier 拒绝而**不落盘**（fail-safe 拦截 → final_chars=0）；
- C07 分解阶段新死因：`IssueDecompositionError`（runtime.py:281-314 五类校验之一），elapsed 1081s 后 pre-run 失败（日志 `agent_pre_run_failure` @15:09:52），**与 L1/L2 均无关，是分解模型输出质量问题**；
- C01/C10 GENERATOR_FAILURE 升至 2/10，指向 writer 侧生成本身失败。

**对 G3/G4/G5 的影响**：
- G3（文章级重排）：run-11 数据**不支持 L2b 为根因**（金标已召回证据表）→ **NOT_NEEDED**，附本附录证据。
- G4（预算 16→24）：run-11 无 BUDGET_EXCEEDED 大面积触发 → **暂不批**。
- G5（≥75% 松绑）：C09 仅缺 2 条（民法典496/577）→ 即使松绑 C09 因 mechanical_completed=R6 但缺法律域引用仍不达 full_closure；**维持原口径**。
- **L1/L2 已基本闭环，需转向 writer-verifier 链路（新失败面）**，属超越本执行书范围的架构决策，需 Owner 批复形成下一个执行书。

## 7. 执行者停止条件

- 必须改冻结物/评测器/prompt 才能让测试通过 → 停，上报
- G1 门触发条件与 MISSING_FACT 分支语义冲突（无法两全）→ 停，上报（这是设计缺陷信号）
- run-9 触发大面积 BUDGET_EXCEEDED（G2 扇出被预算卡死）→ 停，转 G4 决策，不擅自调预算
- 同一缺陷第 2 轮修复仍红 → 停，升级复评