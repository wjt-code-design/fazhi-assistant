# 法智 Agent 主链路工作交接（session 3）

交接日期：2026-09-12。项目根目录：`C:/Users/33393/Desktop/ai-legal-helper`。

本文以当前代码、`docs/work-progress-20260912-session2.md`、T4 两轮真实运行和 session 3 的复审/局部修复为依据。它取代旧文档中的“writer 待用户决策”和“争点数无上界”结论；历史证据仍保留，不得重写。后续用户指令优先于本文。

## 0. 接手结论

T1b 批量检索已经解决步数随争点数增长的问题。真实 C01 能进入 writer，但 qwen3.8-flash 连续两轮出现跨争点证据、非规范引用或争点遗漏，均被严格校验挡住，`agent_completed=False`。

下一阶段采用已由用户确认的最小方案：**最多处理 5 个争点；多于 5 个先让用户选择；每个争点串行、独立起草一次；服务端确定性合并；全部争点经现有 verifier 验证后才出终稿。**任一争点失败即整轮失败，不用 RAG 快答冒充 Agent 终稿。

先接收本轮尚未提交的 T1b 小修复，再实现上述方案。不要并行修改同一主链路；按本文 tickets 串行执行。

## 1. 已确认事实与口径纠正

### 1.1 当前代码事实

- 争点 schema 已有上限：`backend/agent/runtime.py` 的 `_MAX_ISSUES = 8`，提示词和 `_IssueEnvelope` 均允许 1–8 个。旧进度文档“争点数无上界”“可能 9+”不准确。
- 当前产品运行预算为 `max_steps=20`、`max_tool_calls=10`；不要继续提高。
- T1b 在一个 EXECUTING 周期执行所有待检索争点，并在一个 EVALUATING 检查点保存结果。8 争点离线样本曾达到 9/20 步并完成；真实 T4 r1 的 4 个争点全部检索。
- writer 目前一次接收所有争点；`EvidenceBoundedWriter.render()` 首次失败后还会反馈错误码并重试一次。service 的 coverage loop 也可能再次调用 writer。
- writer 失败原因不在技术 fallback 白名单中，因此正确行为是公开 `failed`，不会自动走 Fast Path。不要把 writer 失败改成技术 fallback。
- venv 没有损坏。它在受限沙箱内无法启动，但经授权在沙箱外可运行 Python 3.11.0，并完成本轮测试。

### 1.2 当前工作区

当前 HEAD：`2b70837`。T1b 主提交：`c5236ef`。以下是 session 3 的未提交修改，属于本次交付，接手时保留：

- `backend/agent/controller.py`
- `backend/tests/test_agent_controller.py`
- `dispatch-output/t1b-small-fix/`
- 本文档

仓库还有其他历史证据目录未跟踪，不能用 `git clean`、`git reset --hard` 或覆盖式还原清理。Git 对象库已有历史损坏记录；本任务不修 Git、不 push。

### 1.3 T1b 局部修复已完成

复审发现：批内第一项成功后，第二项若预算超限或触发 `DuplicateToolCall`，已发生的 observation 和 AgentEvidence 可能丢失；工具返回失败时，`batch_tool_result` 又被误标为 `SUCCEEDED`。

当前未提交补丁已经：

- 在批内 state 中即时累积 observation；
- 在预算停止和网关重复异常的终态保存中传入已物化证据；
- 在工具失败时写入实际错误码；
- 保持原 CAS 原子保存、fail-closed 和恢复不重放语义。

验证证据位于 `dispatch-output/t1b-small-fix/`：

- 有效红灯：`red2.txt` / `red2.xml`，3 项均按预期失败；
- 定向绿灯：`green.txt` / `green.xml`，3 passed；
- 全量回归：953 passed、18 deselected、50 warnings、覆盖率 78.57%，退出码 0；
- ruff、format、mypy 退出码均为 0；非 LLM citation smoke 24/24；
- 详细说明：`review-report.md`。

这些数字来自本轮实际日志。测试使用受控工具输出和真实 SQLite，不代表真实模型遵守度或法律语义已经通过。

## 2. 用户已经确认的产品决策

以下决策无需再次询问：

1. 所有争点必须通过证据归属、规范引用和现有终稿验证，才能 `agent_completed=True`。
2. 一次 Agent 运行最多处理 5 个争点。分解得到 6–8 个时，先让用户明确选择最多 5 个；不得自动截断、静默合并或只回答前五个。
3. 每个已选争点只接收本争点的 Fact、Evidence 和 UnknownFact，串行调用 writer。
4. 每个争点只接受一次有效生成结果。writer 校验失败后不反馈重试；coverage 不再次生成。
5. 服务端按原争点顺序合并结构化 `DraftAnswer`，不调用另一个模型润色或重写。
6. 任一争点失败、无有效 claim 或最终 verifier 不通过，整轮失败；已通过的片段只用于内部诊断，不向用户输出半成品法律结论。
7. 失败响应明确表示 Agent 无法安全完成；不得返回 RAG 快答并让用户误以为是 Agent 终稿。
8. 用户要求避免过度设计。不得新增工作流框架、并发 writer、自动改引用器、LLM judge 或新的存储服务。

“一次”指一次可供 writer 校验的模型输出。SDK 对网络错误的底层重试、供应商拒绝 JSON schema 后的兼容调用，仍须单独记录 HTTP 尝试和费用，不能被描述成零成本或一次请求。

## 3. 最小目标架构

```text
分解 1–8 个争点
  ├─ 1–5 个：继续现有检索/澄清
  └─ 6–8 个：持久化范围选择澄清 → 用户选择 1–5 个 → 继续

进入 DRAFTING
  → 按 state.issues 顺序逐个构造单争点 WriterPayload
  → 每个争点调用一次 _render_once 并执行现有严格校验
  → 任一失败：保存 FAILED，公开安全失败
  → 全部成功：确定性合并 DraftAnswer
  → 现有 DeterministicVerifier 验证一次
  → PASS 后使用现有 finalizer/CAS 保存终稿
```

边界必须保持：decomposer 只提出争点；controller 管运行状态与范围澄清；writer 只生成和校验 claim；service 编排串行起草与终稿保存；verifier 保持独立确定性验证。不要让 controller 拼答案，也不要让 writer 修改 Agent 状态。

## 4. 串行任务清单

### Ticket 0：接收 T1b 局部修复

负责人只处理 `backend/agent/controller.py`、`backend/tests/test_agent_controller.py` 及本轮证据。

执行：

1. 阅读 `dispatch-output/t1b-small-fix/review-report.md` 和 diff。
2. 确认三个参数化 SQLite 测试仍覆盖：部分成功后预算停止、网关重复异常、工具超时。
3. 不重新设计批量检索，不增加逐工具检查点；本轮只收下已验证补丁。

DoD：现有 diff 无冲突；相同三项测试通过；前序 observation、AgentEvidence、真实失败码和不继续后续工具的断言均存在。

### Ticket 1：实现可恢复的争点范围选择

优先文件：`backend/agent/schemas.py`、`backend/agent/controller.py`、`backend/agent/service.py`、直接相关测试。必要时调整 `chat_integration.py` 的公开字段，但先证明现有字段不够；不要改数据库表。

推荐最小实现：

- 保持 decomposer 能解析 1–8 个争点，**不要把 `_MAX_ISSUES` 直接改为 5**。
- 给 `LegalAgentState` 增加一个有界、服务端字段，例如 `pending_scope_issue_ids`，仅保存待选择的既有 issue_id；JSON state 可承载，无需迁移表。
- controller 在首次进入检索前发现 6–8 个争点时，转为现有 `WAITING_USER`，持久化列有序编号的问题清单和专用 reason code，例如 `ISSUE_SCOPE_SELECTION_REQUIRED`。不得发起检索。
- 公开澄清事件可使用 `issue_id="scope"`；当前 resume API 实际按 run_id/state_version 恢复，不依赖客户端回传 issue_id。
- `resume_with_user_fact()` 在普通事实澄清逻辑之前识别 scope 状态，只接受确定性编号选择（1–8 中的 1–5 个唯一编号）。合法时按原顺序保留所选 issues，清除 scope 状态并转回 PLANNING；不得把选择文本写成某个争点的 Fact。
- 空输入、非编号、重复、越界或超过 5 个选择均拒绝，并保持数据库 WAITING_USER 状态/version 不变。不要调用 LLM 理解选择。
- 范围选择属于产品约束，不消耗法律事实澄清的 `max_clarifications=2`；另用单次 pending 状态防循环。

DoD：

- 5 个争点不触发范围澄清；6 个触发且零工具调用；
- 合法选择后仅保留所选争点、原顺序不变，并继续批量检索；
- 非法选择不写 Fact、不改版本、不发工具调用；
- 重放旧 state_version 被 CAS 拒绝；他人 run/conversation 仍拒绝；
- 不修改冻结案例或 judge。

如果上述实现迫使新增状态枚举、数据库迁移或前端协议大改，先停下写清原因；不要用字符串前缀、解析自然语言或把 scope 选择伪装成 UnknownFact 绕过去。

### Ticket 2：逐争点、单次、串行 writer

负责人处理 `backend/agent/writer.py`、`backend/agent/service.py` 及 writer/service 直接测试。不要修改 verifier 规则。

推荐最小实现：

1. 在 writer 内复用 `build_writer_payload(state)` 的既有白名单与排序，再按 issue_id 生成单争点 payload；不要复制一套 Fact/Evidence 转换逻辑。
2. `render(state)` 按 `state.issues` 顺序循环，每个 payload 只调用一次 `_render_once(payload, state)`。
3. 任一 `WriterResult` 非 READY，立即返回该错误；不得继续后续争点。
4. READY 但该争点没有任何被接受 claim，也视为显式失败，例如 `ISSUE_CLAIMS_MISSING`。不能等到 coverage loop 再补写。
5. 合并各结果的 `conclusion`、`issue_analysis`、`risks`；每个 section 内保持争点原顺序。`missing_information` 做稳定去重。`claim_checks` 仍为空，继续由 verifier 生成。
6. 删除 `render()` 的失败反馈重试。service 不再进入 `_coverage_research_loop` 重新起草；首次 verifier 非 PASS 即使用现有失败持久化。
7. 调用每个争点前检查已有 `cancelled` 回调。若为了做到这一点需要 service 驱动循环，可把“单争点 render”作为 writer 的小接口，由 service 串行调用；不要新建执行器或队列。

DoD：

- 两个争点的 generator 每次只看到一个 issue，调用顺序与 state 一致；
- 第二个争点故意引用第一个争点的 ID 时确定性失败，且不产生终稿；
- 第 N 个争点失败后调用次数恰为 N，后续争点不调用；
- 五个争点成功时恰好得到五次有效生成，合并后 verifier PASS；
- 某争点零 claim、非规范引用、数字无来源、未知/跨争点 Fact/Evidence 都失败；
- verifier RESEARCH_MORE/REWRITE/FAIL_SAFE 均不触发第二轮 writer；
- 任一失败无 assistant 终稿消息，AgentRun 保存 FAILED；
- 不改变 `derive_claim_id`、证据有效性、数字校验、规范引用、CAS 或 finalizer。

不要通过自动换 Evidence ID、删除坏 claim、改写引用文本、降低覆盖要求来转绿。这些做法会改变法律语义或静默遗漏争点。

### Ticket 3：离线集成验收

Ticket 1、2 均完成后再执行，使用新的唯一证据目录，禁止覆盖 `dispatch-output/t1b-small-fix/`。

最低验证集：

1. Ticket 1、2 的新增定向测试；
2. `tests/test_agent_writer.py`、`tests/test_agent_coverage_loop.py`、`tests/test_agent_controller.py`、相关 chat integration；
3. 完整后端 `pytest -m 'not slow' --cov=. --cov-fail-under=70`；
4. `ruff check .`、`ruff format --check .`、`mypy .`；
5. `scripts/smoke_citation_fast.py`。

先看新增测试在旧实现上因目标行为缺失而失败，保留有效红灯；环境/夹具错误不能当红灯。完整回归只在最终候选上跑一次，失败后先定位，不循环重跑制造假绿。

DoD：所有命令退出码 0；无网络调用；保存日志、JUnit、候选文件 SHA-256 和命令。覆盖率是代码执行覆盖，不代表法律准确率。

### Ticket 4：真实模型小样本验证

只有 Ticket 3 达标才能开始。先用新目录、新隔离业务库/quota 库、新 ledger、新 run 名验证 C01；一个服务、一个付费执行者、顺序运行。

停止规则：

- C01 出现技术故障：立即停止新增案例并定位；
- 连续两轮出现相同 writer 失败族：停止，不追加提示词或扩大样本；
- `agent_completed=False`、fallback 文本、runner 退出码 0 均不计 Agent 成功；
- C01 工程链路和确定性校验通过后，才按原计划执行 C07、C10；
- 最多三个案例，不扩成整套评测。

每例记录：实际 issues 数、是否触发 scope 选择、writer 有效输出次数、每个 writer payload 的 issue 数、最终 verifier verdict、Agent 是否完成、HTTP 尝试、tokens、估算费用及未决预约。日志只记 ID/数量/错误码，不记密钥或完整用户文本。

工程门：全部选定争点均有有效 claim，引用可溯源，Agent 状态 COMPLETED，`agent_completed=True`，无 Fast Path 冒充。

法律语义门：用官方原文和独立判断记录 PASS/FAIL/REVIEW；实现者自查须标为自查。自动 `gate5_judge.py` 的总布尔值不能单独证明语义通过；不新建 LLM judge。

## 5. 成本与授权

历史账本估算：session 2 之前约 0.0711986 元，T4 两轮约 0.0463 元，合计约 **0.1174986 元**。这是各轮 ledger 估算之和，未与供应商控制台账单校准。

用户已说明 2026-09-15 前可以放开运行 qwen3.8-flash。执行口径：

- 不逐次请示已经批准的小样本 qwen3.8-flash 验证；
- 仍保留单进程 20 元失控上限、端点/模型白名单、最多 60 次 HTTP 尝试和独立 ledger；
- 不并行启动多个各自拥有 20 元限额的进程；
- schema 兼容 fallback、SDK retry、Fast Path 及 rerank 的每个 HTTP 尝试都进入账本；
- 未取得 usage 或服务端状态未知时保留最坏预约，不退款重跑；
- 2026-09-15 起恢复累计 20 元纪律，开始前重新汇总全部账本与之后新增费用。

逐争点 writer 可能把一次多争点起草从约 1 次模型生成增加为最多 5 次。付费前按候选的最大输入/输出 token 和当前官方价格重新计算单次 reservation；不能沿用旧调用成本当上界，也不能因为总额度充足而更换模型。

## 6. 接手助手执行纪律

- 这是一个强依赖链，默认由一位助手串行完成。若换助手，每个 ticket 一个会话，并把本文和上一 ticket 的证据路径交给下一位；不要并行修改 writer/service/controller。
- 开始前运行 `git status --short`，保存目标文件 hash。发现目标文件变化时先核对 diff，不能还原他人的修改。
- 每个 ticket 只改列出的直接文件；实际依赖要求扩展时在报告中说明，不顺手重构全仓。
- 同一失败连续修改三次仍无法解释，停止并审视设计，不提交第四个补丁。
- 测试需在受限环境外执行时可以申请运行权限；这不等于依赖损坏。不得重建 venv 或升级依赖，除非有新的独立证据。
- 不修改冻结 judge、题集、fact_ids、verifier 规则或历史 sessions；不把旧失败 run 补写成成功。
- 不部署、不 push、不修复 Git 对象库。Git commit 也应以用户后续指令为准。

每个 ticket 的交付报告只回答：发现什么、改了什么、怎样证明、已知限制、费用/未决请求、下一步。不要继续叠加多份相互覆盖的巨型交接文档。

## 7. 最终验收定义

本阶段完成必须同时满足：

1. T1b 局部修复仍在，批内部分成功后的持久审计不丢失；
2. 6–8 个争点先形成可恢复 scope 澄清，合法选择后只处理最多 5 个；
3. writer 每次只接收一个争点，每个选定争点一次有效生成；
4. 任一争点失败或缺 claim 时无终稿、无 Fast Path 冒充；
5. 合并草稿通过未经放宽的 DeterministicVerifier 和 finalizer；
6. 离线完整门禁通过并有新鲜证据；
7. C01 至少一轮真实模型完成，随后才决定是否继续 C07/C10；
8. 工程成功与法律语义复核分开报告，不用测试覆盖率、文本长度或 HTTP 200 代替真实目标。

如果真实运行仍失败，保留样本并按失败阶段诊断。本文不承诺 qwen3.8-flash 必然遵守约束；目标是通过缩小上下文提高成功概率，同时继续用确定性边界阻止错误输出。
