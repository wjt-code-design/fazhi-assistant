# 给接手助手的实施教学手册

配套执行基线：`agent-architecture-audit-and-execution-plan-20260909.md`。
本手册解释实现方法，不扩大该书授权范围。下文骨架是设计示例，未作为业务补丁执行或测试；不要把示例直接粘贴后宣布完成。以当前仓库签名、测试和调用结果为准。

## 先理解我要你解决什么

你接手的不是“让模型再试一次”，而是让一次重试在数据库、内存和最终输出之间保持一致。

当前错误链条是：

```text
数据库：DRAFTING，version=v，research_returns=0
内存：  DRAFTING，version=v，research_returns=0
回喂：  只把内存 research_returns 改为 1
验证：  对这份内存状态 PASS
保存：  数据库状态 != 内存状态 → 正确地拒绝
```

正确顺序应是：

```text
验证确有可重写缺口，且未断连、预算尚有剩余
构造 next_state（计数+1，不原地改旧快照）
CAS：数据库 v → v+1，持久化 next_state 与 attempt 步骤
成功后才调用 writer
verifier 验证当前 state 与新 draft
finalizer 使用同一对 state/draft 和对应 verification
最终保存以 v+1 为 expected_version → COMPLETED / v+2
```

其中 v 是进入这段流程时的版本，不是整个请求固定从 0 开始。只要中间又保存了状态，就必须继续跟随新版本。

不要删掉状态相等检查，不要从比较中排除预算，不要把内存计数改回 0 来骗过保存层。这些方法会让一次测试通过，却破坏真实恢复语义。

## 第一课：先做能击中缺陷的测试

从 `backend/tests/test_agent_chat_integration.py` 的 `test_real_agent_service_runs_adapters_controller_gateway_writer_verifier_and_storage` 入手。这里已经有真实 service、数据库 fixture、受控 transport、ToolGateway 和 `_finalize`，不需要新建测试框架。

安排两个 issue，每个都有合法有效证据。第一次 writer 响应只覆盖一个 issue，第二次响应覆盖两个。模型可以是脚本替身；service、repository、verifier 和最终 storage 必须真实执行。

注意 issue/evidence ID 是服务端生成的。像现有 transport 一样从实际输入提取引用，不写死猜测 ID。fixture 的法律文本只是工程测试数据，不作为法律正确性的金标；不要把现有示例里的条文与主题匹配关系当成真实法律知识。

测试结构示意：

```python
# 以下名称代表要适配现有 fixture 的步骤，不是现成可导入函数。
# Arrange: 两个 issue + 各自有效证据 + 首稿缺一个绑定 + 次稿补齐。
# Act: execute_agent_request(..., llm=scripted_transport,
#                            gateway=controlled_gateway, finalizer=_finalize)
# Assert:
assert result.outcome == "completed"
assert stored_run.status == "completed"
assert reloaded_state.verifier_research_returns == 1
assert assistant_message_count == 1
assert writer_call_count == 2
assert result.state_version == stored_run.state_version
```

再检查步骤链中存在调用前保存的 attempt，其 version 小于 completed 的 version。预算次数从 AgentRun.state_json 重载断言，不能只读内存。当前 AgentStep.budget_snapshot 保存的是预算配置上限，不包含运行时已用计数，不能拿它证明已用次数。

红阶段应该看到终稿状态冲突或结果不是 completed；如果先死于错误 ID、解析失败或无证据，说明你没构造到目标路径，先修 fixture。不得 mock `persist_agent_final_once` 或让 verifier 永远 PASS 来绕开目标行为。

为定位 F1，可保留已有 AST 隔离复现；它不能取代这条集成测试。

## 第二课：最小保存代码应该怎么写

当前已有接口：

- `load_owned_run(db, run_id=..., user_id=..., conversation_id=...)`
- `register_verifier_research_return(state) -> LegalAgentState`
- `compare_and_save(db, run=..., expected_version=..., state=..., status=..., checkpoint=...) -> AgentRun`
- `CheckpointMetadata`：decision、reason_code、result_code、last_error_code 等。

`compare_and_save` 的更新过滤本身是 run.id + version；调用者必须先用 load_owned_run 确认归属。不要改成按任意 run_id 取记录后直接写。

建议先在 service 中做一个短小的私有保存 helper，或者在重写分支直接调用现有接口；哪种更少重复就用哪种。不引入通用 WorkflowContext、RepositoryFactory 或重试状态引擎。

```python
# 代码骨架：放在 service 的已确认 owner、version、state 一致的分支内。
# 所需 imports 和异常处理应按仓库实际代码补齐。
next_state = register_verifier_research_return(state)
saved_record = compare_and_save(
    db,
    run=saved_record,                 # 来自 load_owned_run
    expected_version=state_version,
    state=next_state,
    status=next_state.status.value,
    checkpoint=CheckpointMetadata(
        decision="coverage_rewrite_attempt",  # 新诊断值，需确认消费者兼容
        reason_code="EVIDENCE_COVERAGE_DEFICIENT",
        result_code="ATTEMPT_RESERVED",
    ),
)
# 验证当前 Session 的 refresh/expire 语义后，读取保存后的版本。
# 不要假设所有测试 session_factory 都设置相同的 expire_on_commit。
state = next_state
state_version = saved_record.state_version
rerendered = runtime.writer.render_for_coverage(state, feedback)
```

上面代码不是完整补丁：

1. 保存前需要检查取消、预算和可修复性。
2. `register_verifier_research_return` 会在超限时抛 BudgetExceeded；不能无脑映射为 verifier 技术失败。
3. CAS 冲突不外呼、不重新读取新版本强行覆盖；返回现有冲突语义。
4. 数据库失败不外呼，返回 storage failure；repository 已 rollback，不在坏事务上继续写。
5. 保存后的 state/version 必须传到 service 的最终保存及公开返回值。

原 helper 只返回 `(verification, draft)`，这是目前接口承载信息不足的地方。最小方案是让 service 持有整个重写控制段。若保留 helper，它必须显式返回更新后的 state/version 等必要数据，不靠修改调用者看不见的局部变量。先不用新增类包装五个字段；真有多个调用者时再判断。

不在模型调用期间持有数据库写事务。先完成小事务，再外呼，最后以版本约束写结果。预算预留后进程退出会消耗一次机会，这是有意的保守策略；它不保证外部 API exactly-once，不能在文档里夸大。

## 第三课：补齐你最容易漏掉的负例

按以下顺序增加测试，每个都写清外呼次数和重载状态：

| 故障注入 | 应有行为 |
|---|---|
| attempt 保存失败 | writer 新调用为 0；不 completed |
| 两个请求使用同一旧版本预留同一机会 | 只有一个 CAS 成功；输家不执行重写 |
| 保存成功后模拟中断，再重载 | 已用预算仍为 1；不恢复成 0 |
| 重写生成非法证据 ID | 无 assistant；已用预算保留；可查 writer 失败阶段 |
| 重写仍缺绑定 | verifier 按预算拒绝；不无限循环 |
| 终稿保存冲突 | 不覆盖更新状态；不重复插入 Message |
| 跨用户/跨会话 run_id | 拒绝且零状态写入 |
| 取消发生在生成前或终稿前 | 按既有断连契约无 assistant；不擅自重新生成 |

精确区分并发范围：T2 的 CAS 保护新增 coverage attempt，不自动证明整个最初 writer 调用已经具备全请求去重。若发现初始生成也可重复，另登记证据和边界，不把它悄悄塞进本次修复。

## 第四课：不要让 writer 去修它没有能力修的问题

RESEARCH_MORE 是 verifier 的结论，不能仅凭这个枚举决定重写。先做修复分流：

```text
状态不合法 → 停止，报告状态完整性问题
存在未解决 critical conflict → 不调用 writer 试图解除 conflict
缺有效法条证据 → 不调用 writer 创造法条；记录需要研究
证据齐全但 claim 未绑定 → 可以消耗一次重写机会
预算耗尽 → 停止
```

coverage_feedback_payload 只负责构造反馈，不要往里加数据库操作。它与 verifier 有相似判断，在 verifier 冻结期间允许局部修复分类，但必须用真实 verifier 对照负例，不能自创更宽松的 PASS 标准。

已有证据的判断必须沿着 issue 的成功 observation 链接走，不能只看整个 state.evidence 是否有任意有效法条，否则会跨争点“借证据”。反馈只列合法 ID，不把金标期待的法条硬塞进去。

最小失败持久化思路：

```python
# 示意：仅用于已有、归属和版本已确认的 DRAFTING 业务失败。
failed_state = transition(state, AgentStatus.FAILED)
saved_record = compare_and_save(
    db,
    run=saved_record,
    expected_version=state_version,
    state=failed_state,
    status=failed_state.status.value,
    checkpoint=CheckpointMetadata(
        decision="failure",
        reason_code=public_reason,
        result_code=stage_reason,
        last_error_code=public_reason,
    ),
)
```

CLIENT_DISCONNECTED、CAS 冲突、数据库故障、尚未创建 run 的分解失败不能一概套用这个骨架。断连保留现有契约；冲突不覆盖；数据库坏了不能声称已落盘；没有 run 时走安全诊断日志。

## 第五课：schema fallback 要按错误原因执行

你现在看到的是大范围 `except Exception: pass`。不要把它改成另一种字符串猜测：例如只要出现“400”就降级。400 也可能是其他参数错误。

先检查项目实际安装的 transport/SDK 异常、status_code、结构化错误体，再定义很窄的 `is_schema_capability_rejection(exc)`。这个名字是拟新增 helper，不是当前库 API。只识别已证明表示 response_format/json_schema 不支持的错误；未知错误保守不降级。

```python
# 设计伪代码，不是已验证 SDK 适配实现。
if not callable(getattr(transport, "bind", None)):
    return invoke_plain_once()
bound = build_bound_transport()  # 本地 schema 构造异常应保留诊断
try:
    return invoke_bound_once(bound)
except Exception as exc:
    record_sanitized_failure(exc)
    if not is_schema_capability_rejection(exc):
        raise
return invoke_plain_once()
```

invoke_* 名称代表要复用现有 `_invoke` 的位置，不是要求再写多层包装。判定器本身也要测试。三个 adapter 共用一次策略，不复制三份 try/except。

区分“adapter 调用次数”和“SDK 内部网络 attempt 次数”。现有 max_retries=3 仍要纳入观测；只 mock transport.invoke 一次，不能宣称网络只请求一次。T4 不要求你自动修改全局 SDK 重试配置，先给出明确的总调用边界及相关测试。

最低测试集：bind 成功、无 bind、明确能力拒绝、401、429、超时、未知 400、本地 schema 构造失败、降级后仍失败。不要把全部异常归为平台能力不支持。

## 第六课：评测不能靠改 passed 解决

冻结 judge 保留；创建 sidecar 是补齐人工/独立复核记录，不是发明宽松判分器。

建议记录结构：

```json
{
  "schema_version": 1,
  "run_id": "待填真实 run",
  "sessions_sha256": "待填实际哈希",
  "case_id": "Cxx",
  "reviews": [
    {
      "rule": "R9_claim_evidence_binding",
      "status": "REVIEW",
      "reviewer": "待填独立复核者",
      "evidence_refs": [],
      "reason": "尚未取得逐 claim 支撑证据"
    }
  ]
}
```

这是单项示例，不能拿它当完整 R1–R12 schema。必需规则集合来自冻结 rubric，其中复合规则需保留子项；不能只数出 12 行就判完成。

聚合逻辑先验证 run/hash/case、规则集合完整性和重复项，再聚合：有 FAIL 为失败，无 FAIL 但有 REVIEW/缺证据为待复核，所有必需项已独立验证才算 reviewed closure。模板里的 reviewer、占位哈希和空证据不能被接受为通过。

语义支撑需要看 claim 内容与证据是否支持其结论，不能只在文本里搜索 evidence ID。使用原模型自行评“自己回答正确”不能作为独立通过依据。

测试聚合器时可以构造完整正例记录；它只证明聚合逻辑可达。真实法律结论仍需真实独立复核，不把 synthetic PASS 写入开发案例质量报告。

## 第七课：长跑先保证产物不丢、不重写

原 runner 在整批末尾 write_text，先修这个运行风险再花钱。

最简单落地方式：run 开始用独占创建的 manifest 或锁文件占用 run 标识；每题完成把当前聚合 JSON 写到同目录临时文件，flush 后按需要 fsync，再用 `os.replace` 原子替换该 run 的当前 checkpoint。初始化时已经存在的 run 不能因 replace 被覆盖。

`os.replace` 的“同一 run 内更新 checkpoint”和“允许覆盖旧 run”是两回事。必须先分清 create 与 resume 两个入口。resume 校验原候选哈希、案例清单、协议版本，跳过已完成案例；不能把相同 `--run` 当作授权重跑。

客户端超时后暂停队列，保留 partial 和未知服务端状态。不知道旧请求是否仍在运行，就不能发下一题或者补发旧题。不要仅仅加 `except TimeoutError: continue`。

先用本地假 HTTP 服务验证中断、错误、部分响应和重复 run 名。产物同时区分最终文本和实际 Agent 完成记录，不能用 final_chars > 0 替代持久化成功。

## 每个 ticket 你要交给我的内容

```text
Ticket / 输入候选哈希：
本次只修什么：
为什么原实现失败（精确路径）：
修改文件及接口影响：
红测试命令、退出码、失败原因：
绿测试命令、退出码、原始输出路径：
负例覆盖和未覆盖项：
冻结物前后哈希：
验收状态 VERIFIED / BLOCKED：
下一 ticket 可否开始及理由：
```

没有亲眼看到红就如实写“已有测试，本次未验证红阶段”，不要补造历史。不要写“所有测试通过”但附件是两个失败。重命令失败后先分析，不自动循环执行。

我希望你先交 T2 的真实集成红测试设计与结果，再交修复证据；这不是要求每一步向 Owner 申请批准，已获任务授权的范围内继续完成即可。碰到付费范围变化、冻结标准必须变更等真实边界时，说明具体原因再提问。

## 可以直接发给实施助手的开工指令

> 你负责执行主规划书 T0、T2，并参考教学手册。只改必要的 service 持久化编排和相关测试，保护既有未提交改动。先复用 test_agent_chat_integration.py 做“首稿缺绑定→重写通过→真实终稿保存”的红测试，证明当前缺陷确实触发；再用现有 register_verifier_research_return / compare_and_save 修复调用前预算保存及版本传递。保持 chat_integration 的状态相等、归属、CAS 检查。补保存失败零外呼、旧版本冲突、预算重载、重复终稿和断连测试。不要改 verifier、金标、系统提示词，不启动实跑，不并行修改 service.py。最终按教学手册交付证据；不得仅凭 helper PASS 宣称完成。
