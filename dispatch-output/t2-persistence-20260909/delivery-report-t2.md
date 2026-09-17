# T2 交付报告：回喂预算持久化及版本传递

日期：2026-09-09。执行基线：`docs/agent-architecture-audit-and-execution-plan-20260909.md`（T0 manifest 见同目录 `candidate-manifest-t0.md`）。责任范围：T0 + T2（主规划书授权："你负责执行主规划书 T0、T2，并参考教学手册"）。T1/T3–T8 未开工。

---

## Ticket / 输入候选哈希

- HEAD：`ebe82e2bda26185236d50afd780cfb48c7c5e946`（与审查书一致）
- 输入候选关键哈希（T0 采集，前 16 位）：service.py `7588a65a80cb553f`、verifier.py `47b37a0a421eaa2c`、chat_integration.py `f05c43c33b7d1e53`、writer.py `e0bc200ab3befd66`、test_agent_chat_integration.py `b8b636ebff6960e7`、未跟踪 test_agent_coverage_loop.py `bbbb5e7aea3617ed`

## 本次只修什么

仅一件事：coverage 回喂（verifier RESEARCH_MORE → writer 定向重渲染）路径上的预算消耗先经 CAS 落盘、版本随保存递增传递到终稿保存与公开返回值。不改 verifier、writer、feedback 构造、equality guard、ownership/CAS、系统提示词、判分器。

## 为什么原实现失败（精确路径）

1. `service.py:125`（原 `_coverage_research_loop`）：`state.verifier_research_returns += 1` 原地修改内存快照，无任何持久化。
2. 回喂成功 → verifier 对内存 state PASS → `finalizer` 通过。
3. `service.py:321` `persist_agent_final_once(..., expected_version=state_version, state=state)`。
4. `chat_integration.py:190`：`persisted_state != state`（数据库 state_json 计数=0 vs 内存计数=1）→ `AgentFinalizationConflict("Finalization state does not match the durable checkpoint")`。
5. service 捕获后返回 `AGENT_FINALIZATION_CONFLICT`，终稿永不落盘。

## 修改文件及接口影响

| 文件 | 改动 | 接口影响 |
|---|---|---|
| `backend/agent/service.py`（`7588a65a` → `aa2e4af4`，自审修复后 `0764bf55`） | `_coverage_research_loop` 改造为持久化编排：`register_verifier_research_return` 构造 next_state（不再原地改旧快照）→ `compare_and_save` CAS 保存（checkpoint: `decision="coverage_rewrite_attempt"`, `reason_code="EVIDENCE_COVERAGE_DEFICIENT"`, `result_code="ATTEMPT_RESERVED"`）→ 保存成功才外呼 `render_for_coverage`；返回 `_CoverageLoopOutcome(verification, draft, state, state_version, failure_reason)` 显式携带新版本；外层跟随新 state/version 走 finalizer 与终稿保存。自审修复：保存后的 render/verify 异常在 helper 内转为 `VERIFIER_TECHNICAL_FAILURE` outcome 并携带已保存新版本，杜绝过时版本号逃逸到公开返回值 | helper 签名扩展（runtime, db, saved_record, state, state_version, verification, draft, cancelled）；`AgentStep.decision` 新值 `coverage_rewrite_attempt`（无白名单消费者，兼容）；其余公开接口零变化 |
| `backend/tests/test_agent_chat_integration.py`（`b8b636eb` → `ef23994f`，自审后 `8a4cf093`） | 新增 1 集成红绿测试 + 6 负例（含自审补的"重写后 verifier 崩溃必须报告已保存版本"）+ 两个争点 fixture（transport/gateway/bootstrap 均从实际输入提取服务端生成的 issue/evidence ID） | 纯新增 |
| `backend/tests/test_agent_coverage_loop.py`（`bbbb5e7a` → `e9008c6fb487888a`，未跟踪文件） | helper 层测试适配新签名；预算/落盘断言改为真实 SQLite + create_run；新增真实 CAS 冲突输家负例 | 纯更新（原 4 个 helper 用例语义保留） |

repository.py / chat_integration.py / state_machine.py / verifier.py / writer.py / prompts.py / gate5_judge.py：**零改动**（哈希前后一致，见下）。

## 红测试命令、退出码、失败原因

- 命令与原文：见 `t2-red-evidence.md`。pytest 报告 `1 failed`（退出码 1；控制台经 tail 截取，原始退出码未直接捕获，如实标注）。
- 失败原因：`AssertionError: unexpected failure: AGENT_FINALIZATION_CONFLICT` —— 正是目标缺陷路径，非错误 ID/解析/证据问题。
- 中间一次死于 `ISSUE_DECOMPOSITION_INVALID`（fixture 的 fact quote 不在 raw_query 内），按教学手册先修 fixture 后重跑，未盲目循环重试。

## 绿测试命令、退出码、原始输出路径

- `dispatch-output/t2-persistence-20260909/t2-green-core.txt`：coverage_loop + chat_integration 全文件，自审修复后复跑 **30 passed，exit=0**。
- 受影响回归组（15 个 agent/chat 测试文件，322 例）：**320 passed + 2 failed**；仅有的 2 个失败与审查基线完全一致（T2 之前即红）：
  1. `test_agent_gate.py::test_settings_default_safe_off_and_task_7_budget_snapshot_sources`（F7：settings 16 vs 期待 8，契约漂移待 T5）
  2. `test_agent_resume.py::test_http_resume_failures_bypass_pre_and_emit_no_sse[payload_update1-501-...]`（F7：400 vs 501，根因未定，T5）
  - 原始输出：`agent-regression-after-t2.txt`（注：该文件因重定向缓冲只捕获到点阵，失败名单由 gate+resume 两文件单跑复核确认如上）。

## 负例覆盖和未覆盖项

已覆盖（全部真实 service/repository/final storage 或真实 SQLite CAS）：

| 负例 | 行为验证 |
|---|---|
| attempt 保存失败（patch compare_and_save 抛 OSError） | writer 零新增外呼；返回 AGENT_STORAGE_FAILURE；DB 零 attempt 落盘、计数 0 |
| 真实 CAS 冲突（输家持过期版本 99） | RunVersionConflict 真实抛出；输家不执行重写；零状态写入 |
| 重写生成非法证据 ID | 无 assistant；已用预算经重载可见保留（=1）；writer 失败阶段可查（writer 恰 2 次调用、reason EVIDENCE_COVERAGE_DEFICIENT） |
| 重写仍缺绑定 | verifier 按预算耗尽 FAIL_SAFE；无死循环（writer 恰 2 次） |
| 重写保存后断连（生成前取消） | 无 attempt 落盘、无 assistant、无 feedback 外呼（CLIENT_DISCONNECTED 既有契约保持） |
| 跨用户 run_id | OWNERSHIP_FAILURE；owner run 的 state_json/version 零变化 |
| 预算重载 | 主绿测试断言 `reloaded.verifier_research_returns == 1` 且 attempt checkpoint（v+1）先于终稿（v+2）落盘 |
| 重复终稿/终稿冲突 | persist 层既有测试覆盖（idempotent replay、concurrent conflict、foreign owner）——未新增，沿用 |

未覆盖（如实列出，不冒充）：
1. 双进程/双线程真实并发（两个 Session 同时跑 execute_agent_request）；CAS 输家用"过期版本注入"模拟，冲突机制真实但并发拓扑未复现。
2. FAILED 状态持久化（writer/verifier 失败分支保存失败终态）——属 T3 范围，本轮失败路径仍返回 failure result 不落 FAILED（测试中已断言 `status == "drafting"` 如实记录现状）。
3. 初始生成的全请求去重（教学手册明确 T2 的 CAS 不证明这一点，未混入）。
4. 全量 tests/（非 agent 文件）与线上运行。

## 冻结物前后哈希（前 16 位，均未变化）

verifier.py `47b37a0a`、chat_integration.py `f05c43c3`、state_machine.py `9de7c35f`、repository.py `57c1c00d`、writer.py `e0bc200a`、prompts.py `65c5211c`、gate5_judge.py `90487960`、frozen-cases-v1.json `be281ab2`、hidden-cases-v1.json `d1f0b1f0`、gate2-run-gate5-dev-run-{9,10,11}-sessions.json `08181f2e`/`e11c104b`/`bd56d3e1`。equality guard / ownership / CAS 检查一行未动。

## 自审记录（2026-09-09 21:56 追加，发现 1 缺陷已修复）

逐行复核 helper 与外层、重跑全组后的结论：

**通过项**：CAS 失败三分支语义与既有 `_failure_or_fallback` 映射一致（AGENT_FINALIZATION_CONFLICT/AGENT_STORAGE_FAILURE/CLIENT_DISCONNECTED 行为不变，由同码同函数保证）；多轮循环的 state/saved_record/version 传递正确；`monkeypatch service.compare_and_save` 不影响 controller（controller 走 repository 模块内引用）；`VERIFIER_TECHNICAL_FAILURE` 按既有 routing_metrics 分类为技术 fallback（非回归，测试初版断言 `failed` 是我写错，已按既有语义修正）；跨用户负例中 COMPLETED run 的重入路径（controller COMPLETED 分支 → load_owned_run None → OWNERSHIP_FAILURE）符合既有契约；manifest 文件与实际采集数据一致。

**发现并修复的缺陷**：重写后 `verify` 异常原本逃逸到外层 catch，公开返回的 `state_version` 是过时旧值（attempt 已保存至 v+1）——违反教学手册第二课第 5 点"保存后的 state/version 必须传到公开返回值"。修复：helper 内把保存后的 render/verify 异常转为 `VERIFIER_TECHNICAL_FAILURE` outcome 并携带已保存新版本；外层 catch 现在只可能收到保存前异常（断连检查/feedback 构造），版本恒准确。新增负例 `test_coverage_rewrite_verifier_crash_reports_saved_version_and_keeps_budget` 锁定该行为（attempt 版本 == 公开版本、预算重载=1、零 assistant）。

**修复后核验**：核心组 30 passed；冻结物哈希仍全部不变；service.py 最终哈希 `0764bf55e556a3de`。

## T3 交付记录（2026-09-09 22:06 追加）

依据主规划书 T3（依赖 T2，同 service.py 串行）+ 教学手册第四课，Owner 指示"继续执行任务"后开工。

**改动**（service.py `0764bf55` → `c6abfaa8`；verifier/feedback/verifier 判定零改动）：

1. **可重写性分流 `_rewrite_worth_attempting`**：存在 unresolved critical conflict → 不重写（writer 无法解除 conflict）；缺绑定 issue 中任一无成功 observation 链接的生效成文法证据 → 不重写（writer 创造不了法条，混合场景同样不浪费外呼）；仅纯 binding 缺口（全部 deficient issue 均有可用证据）才消耗重写预算。判定为复刻计算（`_deficient_issue_ids`），verifier 一行不改。接入点：`_coverage_research_loop` 的 feedback 构造之前。
2. **失败持久化 `_persist_drafting_failure`**（F3）：writer 失败（stage `WRITER:<code>`）、verifier 异常（`VERIFIER:EXCEPTION`）、attempt 后 verify 异常（`VERIFIER:EXCEPTION_AFTER_ATTEMPT`）、verifier 终态（`VERIFIER:<verdict>`，含 RESEARCH_MORE 预算耗尽与 REWRITE）、finalizer 异常/终态门失败（`FINALIZER:*`）均落 FAILED 终态 + last_error_code + failure step；steps 预算耗尽防御沿用 controller 模式；版本冲突/存储故障不覆盖不伪报（返回原失败码）。CLIENT_DISCONNECTED 三处检查点保持既有断连契约不落 FAILED。
3. **REWRITE 明确记录为未实现修复能力**：stage=`VERIFIER:REWRITE`，不增加循环。

**测试**（核心组 33 passed；全组 325 例 = 323 passed + 2 known-red，零新增失败；回归输出 `t3-regression.txt`，失败名单由 gate/resume/controller/rollout 四文件单跑复核）：

- 更新 2 个 T2 测试到 T3 契约：invalid_evidence（status drafting→failed + last_error_code + failure step `VERIFIER:RESEARCH_MORE`）；verifier_crash（attempt v+1 → FAILED v+2，公开版本跟随）。
- 新增 3 个：`test_overconfident_rewrite_verdict_persisted_as_unimplemented`（REWRITE 落盘，无 attempt、预算 0）；`test_failure_persistence_storage_error_keeps_original_reason`（FAILED 落盘时 DB 故障 → 不伪报、状态仍 drafting、attempt 保留、原失败码）；`test_coverage_loop_skips_rerender_when_deficient_issue_has_no_usable_evidence`（缺绑定争点仅 SUPERSEDED 证据 → 零外呼零落盘）。

**T3 DoD 核对**：无有效证据零重写 ✓（helper 层负例；注：service 集成层无证据场景会被 controller 扇出+replan 预算先拦截为 STOPPED，到不了 writer，此为分层事实）；conflict-only 零无效重写 ✓（既有负例 + 分流）；conflict+binding-gap 零无效重写 ✓（分流 conflict 短路）；合法 binding 缺口最多预算次数 ✓（T2 主绿测试）；重写失败重载可见原因和已用预算 ✓（last_error_code + state_json）；REWRITE 明确记录未实现 ✓。**验收 VERIFIED**。

**最终哈希**：service.py `c6abfaa8a055420d`、test_agent_chat_integration.py `2858622984a7cb09`、test_agent_coverage_loop.py `775b9e9349784af8`；冻结物（verifier/chat_integration/state_machine/repository/writer/prompts/gate5_judge）全部不变。

**已知限制（如实）**：① `AGENT_STATE_INTEGRITY_FAILURE`（WAITING_USER 校验失败）不落 FAILED（非 DRAFTING 业务失败，保持原样）；② 失败保存与终稿保存共享 CAS 语义，双进程并发下输家的失败保存会被正确拒绝（不覆盖）；③ gate/resume 两红仍属 T5；④ 自审补充登记：外层 loop 调用的 `except Exception`（仅剩断连检查/feedback 构造等保存前异常）不落 FAILED——与 verifier 异常分支不对称但属极罕见确定性代码路径，保持原样；`_persist_drafting_failure` 的 `transition` 若因状态非 DRAFTING 抛 `InvalidTransition` 会被 `except Exception` 静默吞掉返回原版本（全部调用点均已保证 DRAFTING，不可达防御路径，未单独区分异常类型）。

## T4 交付记录（2026-09-09 22:44 追加）

依据主规划书 T4（依赖 T0，与 T2/T3 无文件冲突）+ 教学手册第五课。改动：runtime.py（`c73cefe9` → `1899dc5a`）、test_agent_runtime.py（`bd831d27`）。llm_registry.py **零改动**（`max_retries=3` 保持，2588386a 未变）。

**实现**：

1. **窄判定 `is_schema_capability_rejection(exc)`**：双条件——`status_code == 400`（平台证据：LongCat 对不支持的 response_format 实测 400，probe_longcat_response_format.py）**且** 错误文本（str(exc)+body）含 response_format / json_schema / structured output 关键词（内容证据）。401/403/422/429/5xx/超时/连接/无 status_code 本地异常/无关键词 400 一律 False（不降级、不重复外呼）。鸭子类型读取，不 import openai。
2. **共用调用边界 `_invoke_with_schema_fallback`**：三 adapter（issue/planner/draft）三份重复 try/except 收敛为一个 helper——无 bind 普通调用一次；本地 schema/bind 构造失败保留诊断（`bind_construct_failed` 事件）后普通调用一次；绑定调用失败仅明确能力拒绝降级一次，其他异常原样抛出；降级后仍失败原样抛出不二次降级。严格本地 schema 校验（_strict_json/adapter 层校验）不变。
3. **观测 `_log_adapter_invoke`**：`legal.agent` logger 记录 stage/mode/异常分类/状态码/耗时，无凭据无用户内容。

**测试**（test_agent_runtime.py 37 passed；更新 2 个 W 阶段测试 + 新增 14 个）：

- 2 个旧"降级"测试的替身从 `RuntimeError("400 invalid schema")` 字符串模拟升级为结构化 `_PlatformStatusError(400, "...response_format with json_schema")`——这不是改断言凑绿，而是替身贴近真实 openai SDK 异常形态（教学手册明确禁止"只要出现 400 字样就降级"的字符串猜测）。
- 判定器表驱动单测（400±关键词/401/403/422/429/500/超时/连接/body 关键词）。
- 三 adapter 契约一致：参数化（issue/planner/draft）× {能力拒绝降级恰一次，401 原样抛零降级}。
- 补齐：无 bind 恰一次；本地构造失败降级 + caplog 验证诊断事件；降级后仍失败传播；429/未知 400/超时零降级。

**回归**：13 文件 265 passed 全绿 + gate/resume 已知 2 红（不变）⇒ 全组 330 例零新增失败。**DoD 核对**：bind 成功一次 ✓；无 bind 一次 ✓；能力拒绝至多一次降级 ✓；超时/鉴权负例不降级 ✓；严格本地校验不变 ✓；三 adapter 契约一致 ✓。**验收 VERIFIED**。

**边界声明**：测试断言的是 adapter 层 `transport.invoke` 调用次数；`max_retries=3` 的客户端内置重试在边界之内，本测试不构成网络请求次数证明（审计书 F4 要求如实声明）。

**最终哈希**：runtime.py `1899dc5ad184db9b`、test_agent_runtime.py `bd831d272dea123f`、service.py `c6abfaa8`（T3 后未动）、llm_registry.py `2588386a`（未动）；冻结物全部不变。

**自审记录（2026-09-09 23:21 追加）**：发现并修复 1 处 P1——`_log_adapter_invoke` 的 5 个观测键不在 `observability.py` `_JsonFormatter` 的 `_ACCOUNT_FIELDS` 白名单内，生产环境会被 formatter 静默丢弃（观测目标落空，恰是该文件注释记载过的历史坑：token_est 曾因此丢失）。修复：按既有惯例把 5 键追加到白名单尾部（`llm_adapter_stage`/`llm_invoke_mode`/`llm_error_class`/`llm_error_status_code`/`llm_invoke_duration_ms`），observability.py +4 行；formatter 输出经内联验证。runtime.py 与 test_agent_runtime.py 未再改动；复跑 runtime+chat 61 passed。

## T5 交付记录（2026-09-09 23:27 追加）

两处测试契约/隔离缺口均已查明根因并修复。**全量 15 文件组 332 passed / 0 failed——交接以来首次全绿**（审计基线 127 passed / 2 failed）。

**gate 16 vs 8（契约漂移）**：考古确认 `agent_max_steps` 8→16 由 commit `03a2f14`（2026-09-08，"fix(gate4): F1根因修正——max_steps预算耗尽致第二轮409"）明确批准——两轮澄清会话在第二轮 checkpoint 时 steps=8 已耗尽预算触发 BudgetExceeded→409。`test_agent_gate.py:243` 的期待 8 是陈旧值（03a2f14 未同步测试）。修正：期待改 `(16, 10, 3, 2, 1)` 并附来源注释。**settings.py 零改动**（2c977b96 未变，实际预算未被凑绿调整）。

**resume 400 vs 501（隔离缺口，根因已定）**：探针实测（三个临时探针文件，已删）定位完整链条——`test_agent_rollout.py` 等模块在 **collection 阶段** `import agent.gate` 链式创建 settings 单例，此时 main.py 的 `load_dotenv()` 尚未执行（.env 的 `LLM_MODELS_JSON`=LongCat 表未注入 environ）→ `settings.llm_models_json` 为空 → registry 按含 vision 的 DEFAULT_ROLES 构建 → `has_modality("vision")` 漂移为 True → 图片门禁 501 不触发 → 落到 content 空校验 400。单跑时 autouse fixture 先 import main（load_dotenv 先行），settings 读到 LongCat 表（无 vision）→ 绿。**这是 settings 单例创建时机依赖 import 顺序的脆弱初始化，生产路径（main 先行）不受影响。** 修复（测试侧，按审计书"固定视觉能力前置条件"）：失败测试显式 `monkeypatch.setattr(main, "registry", SimpleNamespace(has_modality=lambda m: False))`，锁定"501 优先于 400"契约，消除 import 顺序依赖。**main.py / settings.py / llm_registry.py 零改动**。

**验证**：resume 单跑 22 passed；rollout+resume（原污染组合）54 passed；gate+resume 67 passed；全组 332/0。**T5 DoD 达成**：受影响组与组合验证齐备，未重跑凑绿（先固定前置条件后验证）。

**T5 后哈希**：test_agent_gate.py `cd3a5c85`、test_agent_resume.py `349ff43e`、settings.py `2c977b96`（未动）、main.py `63355bf2`（未动）。

**遗留改进建议（非本轮范围）**：settings 单例应在创建前确保 .env 已加载（如把 load_dotenv 移入 settings 模块），消除对 import 顺序的隐式依赖——涉及生产启动路径，须单独评估，本票按最小修正原则未动。

## T6 交付记录（2026-09-10 00:45 追加）

runner 长跑加固（F6）。改动：`gate2_runner.py`（`679a7dd1`）、新增 `tests/test_gate2_runner.py`（`ce0993a7`，8 个假 HTTP 服务离线测试，零真实模型调用）。**事实投放逻辑（post 轮次/KEYWORDS/_match_facts_tracked）与判分语义一行未动**；gate5_judge `90487960` 不变。

**实现**：① run 占用——claim 文件 `O_CREAT|O_EXCL` 独占创建（含 targets/pid/协议版本），已占用拒绝（exit 4）；② 逐题原子 checkpoint——`tmp + fsync + os.replace`，崩溃保留已完成题；③ 最终 sessions 存在即拒绝覆盖；全部完成时幂等补写缺失的 sessions（checkpoint→终稿恢复一致性）；④ `--resume`——校验 claim 存在、案例清单与 run 标识一致后跳过已完成案例（不重发请求，防重复计费）；⑤ CLIENT_TIMEOUT → `unknown_server_state` 标记 + **暂停队列**（exit 3，不发下一题）；unknown 题须人工确认后 `--retry-unknown` 才重跑（双门禁，exit 5）；⑥ 新字段 `agent_completed`（final 事件带 run_id = 终稿真实持久化）——`final_chars>0` 不再被误用为完成证据。

**测试**（假 HTTP 服务注入场景）：200 正常两题、重复 run 拒绝、claim 已占用拒绝、resume 去重不重发、超时暂停+标记、unknown 双门禁、HTTP 500 记录后继续、非 SSE 记录。全量 17 文件 **356 passed / 0 failures / 0 errors**（junitxml：`t6-full-suite-junit.xml`）。

**DoD**：零真实模型调用完成演练 ✓；启动身份（claim 含 pid/时间/清单）与候选哈希可核对 ✓；产物（checkpoint/sessions）支持离线复算 ✓。

**边界声明**：测试断言 adapter/runner 层调用次数；`has_modality` 漂移类 import 顺序问题已由 T5 固定；T7（付费轮执行）需 Owner 预登记授权，不在本轮范围。

## 双轴审查与收敛修复（2026-09-10 01:28–01:55）

using-superpowers → code-review 双轴审查（Standards/Spec 并行子代理，固定点 HEAD `ebe82e2b`，范围=本轮全部改动）。

**Standards 轴**（6 项，0 硬违反，全为判断性 smell）：证据有效性谓词三处重复（轴内最重）、Data Clumps（失败保存调用块×6）、日志事件命名、runner 魔法数、测试"或"断言。**Spec 轴**（4 项）：T4 attempt 字段缺失（硬缺口）、T6 测试断言恒真（硬缺口）、T3 conflict+binding-gap 组合测试未单列、T1 键名硬编码风险。

**已修复（3 项）**：
1. T4 attempt 字段：`llm_invoke_attempt`（bound=1 / fallback=2 / 本地构造失败=1）+ observability 白名单 + formatter 内联验证。
2. T6 resume 测试"或"断言 → 确定性断言（sessions 必存在 + agent_completed=True）。
3. 谓词收敛：`writer.is_effective_statute` 单一真源——writer 3 处（排序 key/coverage feedback/标注文本）+ service 2 处（_deficient_issue_ids/_rewrite_worth_attempting）共用；service 孤儿 import 收缩；**verifier.py 冻结保留原实现（行为一致，2 处）**；writer.py:573 反向语义（STATUTE 但非 EFFECTIVE）不套用。

**runner 中途退出显式测试**：subprocess + hang 场景 + kill 模拟进程退出 → checkpoint 保留 C01、create 重入被拒（exit 4）、resume 恢复完成 C02。**过程发现并修复一个测试污染**：子进程不经 monkeypatch，EVID 写入真实 evidence 目录——已清理残留，并为 runner 补 `--out-dir` 参数（兑现原 docstring 承诺，测试/演练可隔离产物目录）。

**最终哈希**：service.py `35791c20`（谓词收敛后）、writer.py `fd24dd16`（谓词导出，T0 时为 e0bc200a——本票经用户确认的允许改动）、gate2_runner.py `21dfa8f2`、verifier.py `47b37a0a`（冻结未动）、gate5_judge.py `90487960`（冻结未动）。全量 17 文件 **357 passed / 0 failures / 0 errors**（post-review-full-junit.xml）。

**保留未动（判断性，待 Owner 决定）**：失败保存调用块×6 的 Data Clumps（可抽 helper 参数对象，改动面 vs 收益待权衡）、日志事件按严重度分级、T3 组合专项测试、T1 键名运行时绑定校验。

**保留未动（判断性，2026-09-10 复核定案）**：失败保存调用块×6 的 Data Clumps（调用形状重复≠知识重复，抽参数对象降可读性——不修）；日志严重度分级（结构化字段已可检索，待付费轮运维反馈——P3）。**已补齐（2026-09-10）**：T3 conflict+binding-gap 组合专项测试（DoD 字面钉住）；T1 AST 哨兵——REQUIRED_REVIEW_RULES 与冻结 judge verdict R 键（13 项）一致性比对，judge 改名时哨兵红、冻结文件零改动（watch-it-fail 已验证）。全量 17 文件 **359 passed / 0 failures / 0 errors**（final-review-junit.xml）。

## 验收状态

**VERIFIED**（限 T2 范围）：红→绿齐备、原 equality guard 保留、回喂成功真正落盘（DB COMPLETED + assistant 恰 1 条 + 重载预算 1 + 版本递增一致）、负例与冻结物核验通过、回归零新增失败。非 T2 范围（T1/T3–T8、全量、线上、语义质量）未声称。

## C01 真实产品缺陷修复（2026-09-10，probe-15 实测发现，非本次重构引入）

**缺陷现场**（probe-15 C01）：`agent_completed=False`、`final_chars=0`、`errors=['EVIDENCE_COVERAGE_DEFICIENT']`，status=failed，clarifications=2/2，tool_calls=3/10（预算充裕），issues=4 但仅检索 3 个。

**根因（实证复现，非推测）**：`_handle_evaluation` 的 `CLARIFY_BUDGET_EXHAUSTED` 分支（controller.py:757）**无条件转 DRAFTING，不检查是否还有 issue 从未检索**。配合扇出"每轮只推进一步即被 return 打断"，澄清轮次 = 可推进 issue 数 → **issue 数 > 澄清预算+1 时，尾部 issue 必然漏检** → DRAFTING 时无证据绑定 → verifier 判 `EVIDENCE_COVERAGE_DEFICIENT` → 回喂被正确拒绝（writer 造不出未检索的法条）→ failed + 空终稿。

**复现通路**：真实 SQLAlchemy store + `execute_agent_request` + `resume_with_user_fact` + `_DEFAULT_RUN_LOCKS` 构造时序循环（run → resume → run…）。复现结果与真实现场完全同构：`status=failed / clarifications=2/2 / tool_calls=3 / steps=13 / issues=4 / 已检索=3 / 未检索=1`。

**修复 v1（错误，自审推翻）**：补 `if not self._every_issue_has_evidence(state) → 回 PLANNING`。根因测试转绿、全量通过，**但引入无界空转**——`_every_issue_has_evidence` 在检索器持续空命中时恒为 False，当作循环条件即无界重入。

**⚠️ 关于 v1 的量化（13:40 证据核查后修正，前稿数字有误）**：
- 前稿写「单轮 297 次 planner 调用、终态非终态 planning」——**该数字是我自己诊断探针的阈值截断产物**（探针设 `>300` 抛错，异常被 `service.py:345` 的裸 `except Exception` 吞成 `AGENT_EXECUTION_FAILURE`，造成了「297 次后正常结束」的假象）。
- **核查后实测**：把探针阈值提到 100000 重跑，v1 循环跑到 **10,750+ 次仍未停，最终段错误崩溃**（exit 139，栈耗尽于 SQLAlchemy 查询编译，~32s）。
- **前稿「仅靠 step 预算被迫中断」的说法是错的**：steps 全程停在 15（< max_steps=16），该回跳路径在状态已是 PLANNING 时**不消耗 step**，故 step 预算根本拦不住。
- **正确结论**：v1 是**真正无界**，与我前稿描述相比更严重。

**修复 v2（正确）**：新增 `AgentController._every_issue_retrieval_attempted(state)`（controller.py:703）作为**终止条件**——判定"每个缺证据的 issue 是否**已发起过** retrieve_laws"（查 `action_fingerprints`），而非"是否已拿到证据"。语义依据：扇出与判定两处的 fingerprint 参数完全一致（`RetrieveLawsInput(query=issue.question, k=4)`，controller.py:729 与 759）→ 一旦试过，重试必命中 duplicate 守卫、不可能产生新证据 → 补齐到头，必须 fall through 到原有确定性收敛路径。转移处保留幂等短路防 `InvalidTransition(planning→planning)`。

**三态对比（同一空证据边界场景，均为本次实测）**：

| 指标 | HEAD(pre-fix) | v1（错版） | **v2（采纳）** |
|---|---|---|---|
| turn3 status | failed（✅终态） | **无界，段错误退出（exit 139）** | failed（✅终态） |
| planner 调用 | 0 | **10,750+ 次后崩溃** | **0**（✅） |
| 第 4 个 issue 补检索 | 无 | 无 | **+1（✅已尝试）** |

**watch-it-fail 验证（skill 第 3 问：测试须亲眼为正确原因红过）**：

| 测试 | 对「修复前/错版」跑 | 结果 |
|---|---|---|
| `test_clarify_budget_exhaustion_must_not_skip_unretrieved_issues` | 对 HEAD(pre-fix) | **RED**，`AssertionError: 转入 failed 时仍有 issue 从未被检索：['issue_f64bc...']；clarifications=2/2` —— 失败原因正是 probe-15 C01 的漏检 issue ✅ |
| `test_backfill_retrieval_terminates_when_retriever_returns_no_evidence` | 对 v1（无界） | **RED（23.6s 快红）**，`planner 被空转调用 54 次（上限 5）—— 补检索存在无界重入` ✅ |

**v1 空转的取证改进（本轮随核查新增）**：原终止性测试对无界循环表现为**挂死**（>300s 未返回、无输出），CI 里难定位。已在假 transport `_MultiIssueTransport` 加 `planner_call_limit`（默认 50）护栏——无界循环必然撞护栏 → 抛带计数的断言错误 → **从「挂死」变为「23.6s 带信息快红」**。两条输出见 `watchitfail_v1_term.txt` / `watchitfail_green_v2.txt`。

**测试（本轮实测）**：新增 3 条回归——
① `test_clarify_budget_exhaustion_must_not_skip_unretrieved_issues`（根因，对 HEAD 已验红、对 v2 绿）；
② `test_backfill_retrieval_terminates_when_retriever_returns_no_evidence`（**终止性**：断言必达终态 + `planner_calls <= n_issues+1` + 每个 issue 均留 retrieve_laws 指纹；对 v1 已验红、对 v2 绿）；
③ `test_seed_retrievals_covers_every_issue_before_forcing_drafting`（次生行为，docstring 已标注非根因，对 v2 绿）。

**全量回归（本轮实测，口径已分清）**：
- **整个 `tests/` 树（70 模块）：903 passed / 0 failed / 0 errors / 0 skipped**（228.6s）→ `fix-v2-final-junit.xml`
- **17 模块 agent 子集（与交付报告既有口径一致）：362 passed / 0 failed**（61.6s）→ `fix-v2-agent17-junit.xml`（此前 `fix-c01-regression` 为 361，+1 即新增终止性测试）
- ⚠️ 前稿曾把「361 → 903」并列表述——**二者口径不同**（361 是 17 模块子集、903 是整个 tests/ 树），不可直接比较。正确对照是 **361 → 362**。

**改动面（本轮实测，忽略换行符差异）**：`backend/agent/controller.py` 922→986 行（净增 64 行）；`backend/tests/test_agent_chat_integration.py` 733→1462 行（净增 729 行）。其余文件零改动。

**已知限制（诚实标注，勿当已验证）**：
1. 全部边界实测均在**假 gateway + 内存 SQLite** 上完成，非真实检索器/真实 DB；结论针对 controller 循环逻辑，不外推到线上数据面。
2. **生产侧无对应护栏**：`planner_call_limit` 只存在于测试。该回跳路径状态已是 PLANNING 时**不消耗 step/replan 预算**，故 v2 的正确性完全依赖 `_every_issue_retrieval_attempted` 判断无误；若未来该判断被改错，生产表现为无界空转（靠 HTTP 层超时兜底），而非被预算拦截。**是否要给该回跳路径增加预算消耗或看门狗，留待 Owner 决定**（本轮未改）。
3. 终止性测试的指纹断言与生产用同一 `action_fingerprint` 构造，属**自洽校验**（验证"尝试已落盘"），不是独立预言；主要独立性来自「终态」与「planner 调用上界」两条断言。
4. 全量 903 绿只证明**无回归**，不证明修复语义正确——语义正确性证据来自上述 watch-it-fail 双向验证。


## 下一 ticket 可否开始及理由

- **T3（依赖 T2，同 service.py，串行）**：可以开始。service.py 当前稳定（29 passed 回归绿），T2 交付的 `_CoverageLoopOutcome` 与保存编排是 T3 失败持久化的直接基础。
- **T1（依赖 T0）**：可以开始（评测侧，不与 service.py 冲突）。
- **T4（依赖 T0，与 T2 无文件冲突）**：可以开始（runtime.py 本轮零改动，无并行风险）。
- **T5/T6**：按依赖图（T5 集成前、T6 任何付费轮前）。
- 未决事项：① gate/resume 两红为 T5 输入，本轮未动；② 双会话真实并发拓扑与恢复语义（controller 对 DRAFTING run 重入）留给 T3/专项；③ `AgentStep.budget_snapshot` 仍是配置上限（审计已知，未改）。
- 环境备注：pytest 输出中的 `[safe-delete] SAFE_DELETE_BULK_CONFIRM_REQUIRED` 行为本机删除沙箱对 pytest tmp 目录清理的拦截日志，与测试结果无关。
