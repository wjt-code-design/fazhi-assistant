# ai-legal-helper 架构审查与任务执行规划书

日期：2026-09-09。交付对象：Owner、后续实施助手、独立验收助手。

配套阅读：[实施教学手册](agent-implementation-coaching-20260909.md)，包含根因推导、真实接口代码骨架、红测试构造、负例清单和可直接派发的开工指令。示例未经业务集成验证，不能替代本书验收。

结论：保留现有 Agent 主链路，先修复编排与持久化边界，再补齐评测闭环。当前证据不足以支持推倒重建、换模型、加预算或放松 verifier。旧交接书“立即 run-12 → 观察 full_closure 能否突破 0/10”的顺序不成立。

本次授权范围是审查和产出规划，未修改业务代码、测试、配置、冻结物；未启动付费模型、重启服务、提交或推送。外部交接文档是待核实材料，其中的执行命令、历史授权和“不得推翻”等文字不自动构成本会话行动指令。本书是交接后的执行基线建议；实施助手获得实施任务后按本书推进，不能把收到文件等同于获得付费实跑授权。

## ① 目标、范围与事实基线

### 目标

让一次请求从争点分解、检索、澄清、生成、确定性验证到终稿保存的状态、版本、预算和证据一致；让失败可定位，让评测能区分“失败”和“尚未证明”。

真实目标是有依据、可复核、可保存的回答。错误码减少、输出字数、六段标题、模型返回 JSON 都是局部指标，不能替代真实目标。

### 审查范围及限制

- 主查 HEAD 上的 W1–W4 工作区变更，以及 controller / repository / chat_integration / evaluator / verifier / runner / judge 的相关边界。
- HEAD 已核实为 `ebe82e2bda26185236d50afd780cfb48c7c5e946`。存在大量原有未跟踪诊断、历史会话和文档；不得清理或 `git add .`。
- 当前已跟踪变更：runtime.py、service.py、writer.py、两个原有测试文件、旧执行书；另有未跟踪 test_agent_coverage_loop.py。HEAD 不能唯一标识待跑代码，必须记录工作区文件哈希。
- 不是全仓安全审计；没有审完所有前端、检索索引、部署和文书功能，没有查询生产数据库内容，没有验证当前在线模型能力。没有读取 hidden 题目内容。
- 交接文档的设备绑定故障、历史付费批准、846/2 全量结果属于历史陈述，本次不独立背书。

### 本次直接证据

定向执行六个测试文件：coverage_loop、runtime、writer、gate5_judge_layers、gate、resume；结果 **127 passed / 2 failed / 7 warnings，39.48s，退出码 1**。首次沙箱启动 Python 失败，获准后在沙箱外执行。详见附录命令。未运行全量 tests，不能声明“846/2 已复现”。

历史 sessions 离线统计（只统计文件，不代表线上现状）：

| run | 案例数 | final_chars > 0 | coverage 错误出现次数 | generator 错误出现次数 | planner parse 出现次数 |
|---|---:|---:|---:|---:|---:|
| 9 | 10 | 5 | 3 | 0 | 4 |
| 10 | 10 | 1 | 8 | 1 | 0 |
| 11 | 10 | 1 | 6 | 2 | 0 |

来源：`release-evidence/legal-agent-v1-complex-v1-20260907/gate2-run-gate5-dev-run-{9,10,11}-sessions.json`。错误按 error_codes 展开统计，一题可出现多个错误；final_chars > 0 只代表采集到文本，不证明 Agent 已持久化终稿。

### 术语约定

| 术语 | 本书含义 |
|---|---|
| evidence | 本次状态中可追溯的证据对象，经 observation 关联 issue |
| claim | 引用 evidence / fact 的回答断言，不等同于证据本身 |
| evidence 缺失 | issue 没有可供使用的有效成文法证据，需要检索或明确停止 |
| binding 缺失 | 证据已有，但 draft 没有适当绑定；可能通过重写修复 |
| verifier PASS | 通过当前确定性校验；不等于所有法律论证在语义上正确 |
| completed | 已通过终稿门并且保存为 COMPLETED，不只是返回了文字 |
| mechanical diagnostics | 冻结判分器的自动检查结果 |
| reviewed closure | 独立复核完成 R1–R12 后的结论，另存，不覆盖冻结判分器结果 |
| run | 一次预登记的评测执行；失败、超时、部分完成仍占其 run 标识 |

## ② 审查结论与最小技术决策

### F1 — P1，已确认：回喂成功后无法通过终稿保存检查

`backend/agent/service.py:125` 原地增加 `state.verifier_research_returns`，没有保存；`:321` 后调用 `persist_agent_final_once`。`backend/agent/chat_integration.py:190` 要求传入 state 与 durable checkpoint 完全相等。因此进入回喂、生成成功、verifier PASS、终稿门通过的路径，仍会因计数不一致被拒绝，service 返回 `AGENT_FINALIZATION_CONFLICT`。

这不是应删除的“过严检查”，它防止未保存或过期状态写终稿。已有 `register_verifier_research_return`（state_machine.py:94）和 `compare_and_save`（repository.py:86）可复用。计数必须先经版本比较保存，调用方跟随新版本，再执行外呼及最终落盘。

独立隔离复现见 `agent-audit-state-repro-20260909.md`。该复现使用真实函数 AST 与替身依赖，证明状态不一致；完整数据库集成红绿仍须 T2 完成。

### F2 — P1，已确认：旧规划把不可达的自动指标当作优化目标

`backend/scripts/gate5_judge.py:201` 将 `verdict["passed"]` 固定为 False；多项规则固定 REVIEW，`:225` 用它计算 full_closure。因此原命令得到 0/10 是保守判分设计的结果之一，不能反推出每题业务失败，也不可能靠 writer 优化改变该自动字段。

此外原交接判分命令没有 `--evidence-file`，judge 默认 evidence_ids=None；有实质性回答时会记未绑定。即使提供 evidence-file，当前 R9 也只是文本中出现 evidence ID 的粗检查，不能证明逐 claim 支撑。

处理：冻结 judge 原样保留，另做逐项复核 sidecar 和聚合报告。不得把原始 full_closure 改成新指标、把 REVIEW 自动置 PASS，或者“给证据 ID”就认定语义正确。

### F3 — P1，已确认：终稿阶段状态所有权不完整

`service.py:250` 之后 writer/verifier 失败等分支仅返回结果；没有为这些失败保存 FAILED、last_error_code 和步骤，coverage 计数也会随重载丢失。不能据此声称所有恢复请求都会再次外呼，但可以确定数据库不能完整表达这些终稿阶段结果。

处理：在现有 service → repository 边界统一保存终稿阶段的预算与失败。版本冲突必须作为冲突返回，不能反向覆盖较新的状态。客户端断连沿用已有“无 assistant 写入”契约，单列处理，不一概改为 FAILED。

### F4 — P1，已确认：schema 降级将所有异常当作不支持 schema

`runtime.py:270`、`:424`、`:497` 中绑定调用捕获 Exception 后普通 invoke，包含网络失败、超时及鉴权失败，并非仅 response_format 不兼容。`llm_registry.py:138` 还配置 max_retries=3；外围重试叠加，不应继续引用 runner 注释“单 POST 最多 3 次外呼”作为上限证明。

后果是重复请求和耗时膨胀风险，原始失败分类丢失。没有据此估算实际费用或认定线上已经双扣。

处理：只对明确可识别的结构化输出能力拒绝降级一次；其他异常保留类别、按统一策略处理。所有实际 attempt 可观测。三个 adapter 复用一个小的调用 helper 即可，不新增供应商抽象框架。

### F5 — P2，已确认：可修复性判断没有排除“无有效证据”

`writer.py:299` 的 coverage_feedback_payload 将所有未绑定 issue 加入反馈，哪怕其证据列表为空或无有效成文法；`service.py:105` 仅重写，完全没有新检索。此时 writer 无法合法完成“绑定生效成文法”的要求。critical conflict 与 binding 缺口并存时也会消耗重写机会，仍无法解除 conflict。

处理：只对“已有有效证据且缺绑定、无其他不可由 writer 修复的阻断”执行 bounded rewrite；其余返回明确诊断。真正补检索另开条件任务，复用 gateway、去重和预算，不能假装现有 helper 是 research loop。

### F6 — P1，已确认：长跑产物只在整批末尾保存且可覆盖

`gate2_runner.py:271` 固定写 `gate2-run-{run}-sessions.json`，没有存在性保护；逐题结果先只在内存。所谓 `--case` 断点续跑配合同 run 名会覆盖原结果，而不是合并。长任务崩溃会失去未落盘题目。输出目录实际是固定 evidence 目录，不是交接书中的每 run 时间戳目录。

处理：先固化唯一 run 标识、逐题原子 checkpoint、失败保留和禁止覆盖；事实投放协议与判分语义不改。发生客户端超时不能假定服务端已经停止，也不能直接启动下一题制造重叠调用。

### F7 — P2，部分已确认：测试证据和跨层行为脱节

- coverage_loop 的“PASS 落盘”测试实际只调用 helper，没调用 storage，F1 因此漏检。
- 本次 gate 红：settings.py:54 默认 16，test_agent_gate.py:243 期待 8，属于明确的契约漂移；先查批准的预算约定，不能为绿随意改配置或断言。
- 本次 resume 红：test_agent_resume.py:473 期待 501，实际 400。失败已复现，根因未定；不能只凭旧交接称其为顺序依赖或无关失败。

### 架构判断

问题集中在“谁负责状态保存”“哪种失败能重试”“什么证据算完成”三个边界。保留 FastAPI、现有数据库层、AgentController、ToolGateway、writer/verifier 和 finalizer；暂不更换框架、模型、数据库，不新增多 Agent 产品编排。现有 verifier 检查引用、数字和关联完整性，并不完成法律语义蕴含证明；这项能力边界必须写进验收。

## ③ 目标架构与接口边界

```text
HTTP / bootstrap
  → service：请求编排、终稿阶段预算与检查点所有权
  → controller：研究/澄清状态流转 → gateway：受控检索
  → writer：draft 构造及合法性校验（不自行保存 state）
  → verifier：冻结的确定性裁决
       ├ PASS → finalizer → persist_agent_final_once → COMPLETED
       ├ 可重写 binding 缺口 → 先 CAS 保存预算 → writer → verifier
       └ 不可修复/耗尽 → 保存合法失败状态及原因
  → repository：持有用户/会话约束、CAS、证据与步骤一致性

评测：runner 原始产物 → 冻结 judge → 独立逐项复核 sidecar → 新报告
```

接口不变量：

1. 模型是提议者；不能指定服务器拥有的 ID、状态、预算、审计结果。
2. service 使用新 state 和新 version，不原地改变已保存快照。预算扣减在可能收费的重写前保存；存储失败不得继续外呼。
3. verifier 所绑定的 state 必须与 finalizer/persistence 使用的 state 相同；不删除 durable equality / ownership / CAS 检查。
4. 保存终稿只能一次；旧版本和跨用户调用不能覆盖新状态。
5. 非 PASS 永不保存 assistant 终稿；失败码区分 transport、writer、verifier、storage，保留失败阶段及原始安全摘要。
6. 不增加 DRAFTING→PLANNING 状态边，仅为补检索另开设计任务时再决定。

## ④ 模块规划

后端先完成 T2–T4；优先复用 repository.py 和 state_machine.py 的现有能力。避免调用 controller 私有保存方法，也不把 service 的数据库责任塞进 writer。

前端本轮不改。验收 HTTP/SSE 成功、错误和断连行为即可；如果新诊断涉及展示，另提最小契约任务，不让内部预算、schema 名称直接进入用户法律回答。

评测模块完成 T1、T6、T7；生产 Agent 不读取 frozen/hidden 案例的期待法条。公开开发案例可用于离线故障分析，但不得生成 case_id 专用运行时规则。

## ⑤ 数据与证据规划

- 本轮优先无需迁移；复用 AgentRun / AgentStep / AgentEvidence 和 CheckpointMetadata。字段不够时先列缺口，不把完整模型原文塞进 reason_code。
- 用现有事务/CAS 存预算与 checkpoint。外呼前不持有长数据库写事务；外呼完成后再次校验版本。
- 运行 manifest 至少包含：run_id、开始/结束时间及状态、HEAD、dirty 文件清单与 SHA256、冻结物 SHA256、脱敏模型标识与重试配置、服务启动时间/PID/解释器/工作目录、case 清单、各产物哈希。
- 采集 per-case 的 run_id/conversation_id、步骤版本、错误阶段、evidence 引用、claim 绑定和终稿保存结果；敏感用户内容限访问，密钥/token 不进入 manifest 或提交。
- 不修改历史 sessions；复核结果以新文件引用旧文件哈希。缺数据标 NOT_PROVEN，不倒填或凭记忆补证。
- SQLite 活库不做普通文件拷贝冒充一致性备份；若需备份，采用一致性快照并在隔离库恢复验证。此次审查没有进行备份或迁移。

## ⑥ 运行与回退规划

服务准备不是“8000 有回应”即可。仓库已有 `/healthz` 深度就绪及 `/api/health`；记录目标进程身份、代码 manifest、模型配置摘要，并通过无外呼诊断/离线集成证据证明 Agent 配置启用。HTTP 404/405 只证明有人回应。

固定启动脚本须明确解释器、backend 工作目录和 AGENT_ENABLED；复用仓库已有入口，禁止照抄历史 PID 杀进程。重启前确认没有正在执行的 run，使用新 PID 与启动时间核对。超时先确定服务端请求状态；未知则暂停队列，禁止自动补跑。

回退以已保存的候选文件清单为单位，在隔离候选中恢复，不 reset 当前共享脏工作区。保持数据库和历史证据。run-12 不是本轮审查动作；后续执行者核实可用授权是否覆盖最终候选，已有明确授权覆盖时不用重复索要，只有授权不明或范围改变时才问 Owner。

## ⑦ 执行顺序与 ticket 契约

状态统一为 TODO / IN_PROGRESS / BLOCKED / VERIFIED。实施助手每个 ticket 一个会话；先记录输入哈希，完成后交付 diff、测试原始输出、已知限制。下表是依赖关系，不能跳过“看起来只是流程”的门槛。

### T0：固定现场与独立工作区（先于所有实现）

责任：主实施助手。只新增审计产物，不动既有代码。

- 记录 HEAD、tracked diff、所需未跟踪文件及哈希；密钥和真实数据不进入代码快照。
- 若建 worktree，注意 HEAD worktree 不包含 W1–W4 脏改动；显式移植该候选的 diff 和必要未跟踪测试，并验证内容相同。
- 列出冻结物路径与哈希，列出将编辑的文件 allowlist。不得删除诊断目录。
- DoD：另一个助手能从 manifest 判断自己拿到的是同一候选；候选还原验证成功。失败则停止，不开始付费轮。

### T1：先纠正评测执行口径（依赖 T0）

责任：评测助手；只新增复核规范和报告/聚合器，不改冻结 judge、rubric、事实协议。

- 建 R1–R12 sidecar 模板：case_id、rule、PASS/FAIL/REVIEW、证据定位、复核人、源产物哈希、理由。
- 保留机械指标；新的 reviewed closure 仅在全部必需项得到验证后通过。REVIEW 与 FAIL 分列，缺证据不能通过。
- 验证 sidecar 不匹配 run/case/hash、缺项、重复项、REVIEW 和显式 FAIL 均不能计通过；充分证据的合成正例能通过聚合，证明指标可达。
- DoD：同一材料可重算；不读取金标反馈到生产链路；原 judge 哈希不变。合成正例仅验证聚合器，不算产品成功。

### T2：修复回喂预算持久化及版本传递（依赖 T0，最高实现优先级）

责任：后端助手。主要编辑 service.py，必要时少量 repository 边界；新增测试优先放 test_agent_chat_integration.py，复用真实数据库 fixture。

- 先写 execute_agent_request → 真实 repository → 真实 final storage 的红测试：首次缺绑定、重写后 PASS，预期数据库 COMPLETED、assistant 恰一条、预算为 1、版本递增；当前代码必须因真正状态冲突失败。
- 复用 register_verifier_research_return + compare_and_save，扣预算并取新版本后才外呼；终稿使用最新版本。
- 增补：扣预算保存失败不调用模型、并发旧版本拒绝、重载后预算不复活、跨用户拒绝、重复终稿不双写、断连不写 assistant。
- DoD：上述红绿齐全，原 equality guard 保留，回喂成功真正落盘。仅 helper PASS 不验收。

### T3：明确可重写缺口及失败保存（依赖 T2；同 service.py，串行）

- 只对有效证据已存在且 writer 能修复的缺绑定重写；无有效法条、critical conflict、预算耗尽不浪费重写调用。
- 失败保存到合法终态与步骤；保存失败/版本冲突不能伪报成功，不覆盖新状态。原始 writer 失败可作为附加诊断保留，不只保留旧 coverage 码。
- DoD：无有效证据零重写；conflict-only 和 conflict+binding-gap 零无效重写；合法 binding 缺口最多预算允许的次数；重写失败重载可见原因和已用预算；REWRITE 先明确记录为未实现的修复能力，不擅自增加循环。

### T4：收敛 adapter 降级与调用观测（依赖 T0，与 T2 无文件冲突时可并行）

责任：后端助手，runtime.py / test_agent_runtime.py；只有证据表明必要才动 llm_registry.py。

- 检查当前安装客户端异常类型与重试配置。schema 不支持错误允许一次普通格式降级；超时、鉴权、限流等不被标为 schema 不支持。
- 记录 stage、attempt、模式、异常分类、耗时；不记录凭据。明确客户端内置重试和外层重试的总控制方式，不靠提高 timeout 掩盖问题。
- DoD：成功绑定只调用一次；无 bind 正常调用一次；明确能力拒绝至多一次降级；超时/鉴权负例不触发格式降级；最终仍走严格本地 schema 校验；三个 adapter 契约一致。

### T5：修复两处测试契约/隔离缺口（依赖 T0，集成前完成）

- gate：核实批准的默认预算，若 16 为既定值，修正陈旧期待并说明来源；不得调整实际预算凑绿。
- resume：固定视觉能力/全局注册表/请求校验前置条件，定位 400/501；只在查明契约后修复测试或实施最小业务修正。
- DoD：受影响组与完整 suite 验证；需要证明顺序依赖时运行有针对性的前驱组合和独立用例。不得重跑到绿后丢弃红结果。

### T6：补长跑可靠性与候选标识（依赖 T0、T1，先于任何付费轮）

责任：运行器助手；gate2_runner.py 与最小启动/采集脚本，新增离线 runner 测试。

- 唯一 run 输出；启动前拒绝覆盖；逐题原子保存；中断保留 partial；明确续跑语义和已完成案例去重。保持事实投放原逻辑和冻结协议。
- 以可控假 HTTP 服务测试 200、HTTP 错误、超时、非 SSE、断流和中途进程退出；保留错误及已完成题，不覆盖旧 run。
- 长请求超时后不得未经确认继续下一题；记录未知服务端状态并暂停。诊断可恢复性，不自动重复可能计费请求。
- DoD：全过程零真实模型调用完成演练，启动身份和候选 hash 可核对，产物支持离线复算。

### T7：集成验收与一轮候选验证（依赖 T1–T6）

- 所有修改集成到同一候选后执行受影响测试和全量 tests；不能按历史“允许 2 红”放行。若失败，先分析且保留输出，不自动循环重试重命令。
- 独立验收者检查 F1 实际跨层红绿、冻结物哈希与调用失败负例；模型和数据库相关执行串行。
- 门槛齐备后才执行授权范围内的预登记 run。若使用 run-12，记录它与旧 W1–W4 候选的差异；若名称已存在则禁止覆盖。
- 固定题集全量采集，所有失败保留。每题输出：has_text、agent_completed、技术错误、有效证据覆盖、claim 绑定、机械检查、独立 REVIEW 状态、耗时及外呼次数。
- DoD：报告完整无缺题；有缺题则 PARTIAL，不能换分母。一次开发轮的改善只算候选证据，不宣布生产级质量或统计显著提升。

### T8：仅在新证据证明必要时启动真检索修复

依赖 T7 的逐题失败矩阵。按“证据未召回 / 已召回未绑定 / 语义不支撑 / 事实未澄清 / 评测待复核”分组。

如果确属检索不足，先利用公开案例的只读证据检查区分库内缺失、query、召回、截断和链接问题。提出单一受控修复，走 gateway 和既有预算；G3 的历史 NOT_NEEDED 不是永久数学结论，也不能无证据推翻；G4/G5 不在本轮默认范围。不得硬编码案例金标条文到生产 query。

### 派发与集成纪律

service.py 的 T2/T3 由同一助手串行负责。runtime.py 与 runner 的工作可分别委派；共享数据库、服务端口、付费账户禁止并发跑。每次派发必须写明输入哈希、拥有文件、禁止修改项、测试、交付路径和停止条件。独立验收者不以实现者“测试通过”一句话替代原始输出。

每完成五个 ticket，核查目标是否漂移、是否出现重复事实源、失败是否被隐藏、是否仍有未保存状态、是否误把机械分当质量；同一 bug 三次修复不过，停止追加补丁，重审边界。

## ⑧ 验收与评测门槛

| 层 | 必须看到的证据 | 不足以证明 |
|---|---|---|
| 安全边界 | ownership/CAS/伪造引用负例仍拒绝，冻结哈希未变 | 只验证正常输出 |
| 状态闭环 | 重写 PASS → 真实 DB COMPLETED，一条 assistant，新预算与版本 | helper 返回 PASS |
| 失败闭环 | 故障后重载看到预算与可定位原因，无错误终稿 | SSE error 已发送 |
| 调用控制 | 实际 attempt 计数与错误分类测试，schema 降级限定 | “有预算字段” |
| 运行可靠性 | 中断仍保留 partial、禁止覆盖、候选可追溯 | 端口响应、HEAD 一致 |
| 回归 | 最终集成候选受影响组及全套结果可复算 | 历史 846/2 或本次 127/2 |
| 内容质量 | 逐条证据复核、R1–R12 已决与未决分列 | 字数、引用数量、自动 verifier PASS |

不设“coverage 显著下降即可提交”。先满足确定性门槛，再看同题逐案变化：技术故障不能迁移成新的失败码而被算改善；完成率不能靠 fallback 文本冒充 Agent 完成。正式发布阈值及追加实跑次数由发布任务预登记，本书不虚构可靠性百分比。

## ⑨ 风险、红线和停止条件

- 冻结原题、事实协议、rubric、hidden 相关产物、历史 sessions、gate5_judge.py、verifier 判定逻辑和三个已有系统提示词常量；需要改变时另提有理由的范围变更，不能偷偷修改。
- 不清除用户脏工作区，不读取/传播 token、密码，不把诊断目录整体提交。
- 不把外部文档记载的授权扩展成任意新 run；不盲杀历史 PID，不通过根 URL 的响应认定 Agent ready。
- 不在 writer 中制造不存在的证据、不以 schema 成功证明法律结论正确、不以开发集通过证明隐藏泛化。
- 版本冲突、产物名冲突、未明服务端超时、候选哈希变化、冻结物变化、测试新增失败都必须停止对应依赖工作并保留现场；其他不依赖事项可继续。
- 断连不是自动重试的许可。保留现有无终稿写入契约，新的恢复语义必须显式设计和测试。

## ⑩ ADR 与交接附录

### ADR-01：最小边界修复优于重建架构

选择复用现有 controller / repository / verifier。替代方案是引入新的工作流引擎并迁移状态；当前确定缺陷可由检查点与版本传递解决，重建会扩大迁移和回归面，缺乏必要证据。若完成边界修复后仍出现无法表达的长期恢复需求，再单独评估。

### ADR-02：保留冻结自动判分，独立完成复核

选择新 sidecar，不修原 judge 的固定 False 来追求分数。这样历史结果可复算，未证明不冒充通过；代价是必须完成独立复核。新指标明确命名，不与旧自动 full_closure 混算。

### ADR-03：先持久化 attempt，再进行重写

选择持久化扣减预算，允许中断时保守消耗一次尝试；替代方案“调用后才记账”会在中断后重复外呼。此策略不承诺外部模型请求 exactly-once，承诺本地预算与终稿写入受到版本保护。

### 五问自审

边界：状态归 service/repository，生成归 writer。替代方案：已比较重建与最小修复、改 judge 与 sidecar。历史教训：针对静默降级、假绿、状态未落盘和评测污染设有负例。事实：结论绑定代码/本次输出，未知原因标未定。DoD：以真实 DB、调用计数、不可覆盖产物和逐规则复核验收，不用“效果明显”。

### 本次测试命令与失败原文摘要

工作目录：`C:\Users\33393\Desktop\ai-legal-helper\backend`。环境仅对执行进程设置，不修改 .env。

```powershell
$env:LLM_API_KEY='audit-offline'
$env:LLM_BASE_URL='http://127.0.0.1:9/v1'
$env:EMBEDDING_PROVIDER='local'
$env:RERANK_ENABLED='false'
$env:EMBEDDING_QUOTA_TOTAL='0'
$env:RERANK_QUOTA_TOTAL='0'
$env:DATABASE_URL='sqlite:///:memory:'
.\venv\Scripts\python.exe -m pytest tests/test_agent_coverage_loop.py tests/test_agent_runtime.py tests/test_agent_writer.py tests/test_gate5_judge_layers.py tests/test_agent_gate.py tests/test_agent_resume.py -q --tb=short
```

```text
test_settings_default_safe_off_and_task_7_budget_snapshot_sources
tests/test_agent_gate.py:243
assert (16, 10, 3, 2, 1) == (8, 10, 3, 2, 1)

test_http_resume_failures_bypass_pre_and_emit_no_sse[payload_update1-501-...]
tests/test_agent_resume.py:473
assert 400 == 501

2 failed, 127 passed, 7 warnings in 39.48s
exit_code=1
```

六文件的通过用例不覆盖所有业务路径。未新增测试，不能提供本次实施红绿；F1 的隔离复现不替代 T2 集成测试。全量、线上、性能和法律语义验收尚未完成。

### 给接手助手的第一条任务

> 阅读本书，完成 T0 并报告候选 manifest；随后执行 T1/T2。先用真实持久化路径写出重写 PASS 仍保存失败的红测试，再修预算 checkpoint 与版本传递。不要直接启动 run-12，不修改冻结判分器或放松终稿状态相等检查。每个 ticket 交付文件列表、测试原始输出、验收状态和未决事项。
