# Agent V2 专项执行书草案：writer→verifier 链路修复（W1-W4）

> 日期：2026-09-09 ｜ 起草：接手实施助手（承接 handoff §4.1 待 Owner 批复项）
> 上游：`docs/v2-optimization-execution-taskbook-20260909.md` 附录 B（run-11 判定）、V1 任务书（金标/归因框架）、`docs/adr-longcat-response-format-20260909.md`、`docs/v1-candidate-fix-options-20260908.md`（F1 未执行遗产）
> 性质：**架构级专项，非补丁**——死亡点已从 L1（parse，run-10 起清零）与 L2a（检索偏科，G2 已打掉）转移至"writer 生成 → verifier 判定"链路。
> ⚠️ 本文件为 DRAFT：任何代码实施须 Owner 批复后方可开始；获批后本文件转为正式执行书（去 DRAFT 标记）。

## 0. 根因结论（本次接手通读 writer.py / verifier.py / service.py / runtime.py 全文后确认）

**主死亡机制（EVIDENCE_COVERAGE_DEFICIENT 6/10，final 不落盘）**：

1. `EvidenceBoundedWriter.render` 内部为全有全无校验：任何一条 claim 出现数字逸出 / 非规范引用 / 错绑 evidence_id / 跨 issue 引用 → 整份 draft fail-safe（回喂重试一次，仍败全拒）。
2. render 成功后，`DeterministicVerifier.verify`（verifier.py:281-296）要求**每个 issue 至少一条 claim 绑定生效成文法证据**，否则 `EVIDENCE_COVERAGE_DEFICIENT`。
3. **编排层断裂点**：service.py 中 verify 非 PASS 直接 `_failure_or_fallback(verification.reason_code)` 终态失败——verifier 已有的 RESEARCH_MORE 语义（verifier.py:298-304，按 `verifier_research_returns < max_verifier_research_returns` 区分）在编排层**从未被消费**，没有定向回喂、没有二次渲染。
4. run-11 DB 实证（C02，conv=2308）：金标法条已在证据表（G2 扇出生效）→ 问题不在召回，在 **writer 生成时未把已召回证据绑进 per-issue claims**（claims 无证据被 dropped / 错误分布 / 绑定失败），且全链路无任何补救循环。

**次级失败面**：

- C07 `ISSUE_DECOMPOSITION_INVALID`：decomposer 走普通 `_invoke`，无结构化输出约束（runtime.py LLMIssueDecomposer.decompose），输出 schema 偏差 → pre-run 死亡（elapsed 1081s 后 agent_pre_run_failure）。
- C01/C10 `GENERATOR_FAILURE`：writer 生成调用层失败。

## 1. 对策（W1-W4）

| 编号 | 对策 | 打击面 | 性质 |
|---|---|---|---|
| **W1** | verifier deficient → 定向 coverage 回喂重渲染（服务端编排循环） | 主失败面 6/10 | 编排层，纯工程 |
| **W2** | writer 接 response_format=json_schema（复用方案A模板） | GENERATOR_FAILURE / MALFORMED + 绑定稳定性 | 模型接口层 |
| **W3** | decomposer 接 response_format=json_schema | C07 分解校验失败 | 模型接口层 |
| **W4** | writer payload 证据确定性重排序（Owner 决策项） | LLM 绑定正确率 | 灰色地带，需 Owner 明确批准 |

### W1：定向 coverage 回喂（核心，打主失败面）

**现状锚点**：service.py `execute_agent_request` 尾段——`runtime.writer.render(state)` → `runtime.verifier.verify(state, draft)` → 非 PASS 即失败返回。

**设计**：

- verify 返回 `EVIDENCE_COVERAGE_DEFICIENT` 且 `state.verifier_research_returns < budgets.max_verifier_research_returns` 时，服务端构造**定向 feedback**：缺失 issue 清单（哪些 issue 无生效成文法 claim）+ 该 issue 当前 claims 绑定概况 + 该 issue 可用证据清单（evidence_id + source_ref + legal_validity，只列 payload 中真实存在的标识），调用 writer 二次渲染（复用 `_render_once` 的既有 feedback 通道），`verifier_research_returns` 计数 +1；重渲染结果走同一 verifier；仍 deficient → 按原 verdict 语义终态失败。
- **verifier.py 判定逻辑一行不改**：W1 只新增编排层消费路径，把 verifier 已有的 RESEARCH_MORE 语义真正接上。与既有"错误回喂重试（2026-09-08）与模型无关"设计同构。
- feedback 由服务端确定性组装（只含 payload 中真实存在的 evidence_id / issue_id），不把模型输出当真值，不引入新的越权信息。
- 接口建议：`EvidenceBoundedWriter` 暴露带 feedback 的公开重渲染入口（如 `render(state, feedback=...)` 或独立方法），fail-safe 语义不变；`verifier_research_returns` 自增函数现状为实施前置核实项（schemas.py，若无现成 register 函数则新增）。
- 实施前置核实：`routing_metrics.is_technical_fallback_reason` 对 `EVIDENCE_COVERAGE_DEFICIENT` 的归类（影响 fallback/failed 分类与前端 restart 事件）；gate2_runner 对 fallback 的处理方式。

**测试（先红后绿）**：

- verify 首判 deficient → 断言第二次 render 收到含"缺失 issue + 可用证据清单"的 feedback → 重渲染 PASS → final 正常落盘。
- 预算耗尽（research_returns 已达 max）→ 不重渲染，直接失败。
- 重渲染后仍 deficient → 失败，reason_code 保持 EVIDENCE_COVERAGE_DEFICIENT。
- 回归：既有 chat_integration 全量用例绿；controller 测试不动（W1 不改 controller.py）。

### W2：writer response_format=json_schema

**锚点**：runtime.py `LLMDraftGenerator.generate`（现为普通 `_invoke`）；模板 = `LLMPlannerAdapter._invoke_planner`（bind + fail-safe 回退链，现成可复制）。

**设计**：构造 `_GeneratedDraft` 的 json_schema（扁平结构、无联合判别，可先试 strict=True，平台 400 则回退 strict=False/普通调用）；bind response_format；构造/调用失败一律静默回退普通 invoke。**不动** `AGENT_WRITER_SYSTEM`、`_strict_json`、既有回喂与全部 writer 校验。

**测试**：transport mock 支持 bind → 断言 response_format 传入且 schema 含 claims 字段；bind 失败 → 回退普通调用。

### W3：decomposer response_format=json_schema

**锚点**：runtime.py `LLMIssueDecomposer.decompose`（现为普通 `_invoke`）；schema = `_IssueEnvelope`（结构简单）。

**依据**：ADR 决策原文（adr-longcat-response-format §决策）明确"为 planner/decomposer/writer 引入 response_format"，当时最小步只做了 planner；本项为 ADR 遗留部分的补全。C07 判据：run-12 中 `ISSUE_DECOMPOSITION_INVALID` = 0/10。

**测试**：同 W2 模式。

### W4（Owner 决策项）：writer payload 证据确定性重排序

**现状**：`build_writer_payload` 中 linked evidence 按 `evidence_id`（sha256 哈希序）排序——LLM 视角下金标法条可能排在证据列表尾部，稀释注意力影响绑定正确率。

**提案**：改为 `(STATUTE 优先, EFFECTIVE 优先, source_ref 字典序)` 的确定性排序。纯服务端数据准备、无 LLM、不动 prompt 文本、一行可回退。

**风险声明**：payload 内容组织虽非 prompt 文本（AGENT_WRITER_SYSTEM 不动），但改变模型输入分布——按"不改 prompt"纪律的精神，**请 Owner 明确批准或否决**。建议：批准（与 G2 同理属服务端确定性输入质量优化）。

## 2. 执行边界

- 不改：verifier.py 判定逻辑（W1 仅加编排层消费路径）、gate5_judge.py、frozen-cases / round-protocol / rubric / fact-ids / hidden-* / run-1~11 历史 sessions、`_PLANNER_SYSTEM_PROMPT` / `_ISSUE_SYSTEM_PROMPT` / `AGENT_WRITER_SYSTEM` 文本。
- 金标口径维持原样（G5 维持原口径，不松绑）。
- 不调除 run-12 验证轮外的任何在线模型；run-12 实跑前须 Owner 显式授权（LongCat 付费）。
- 延续既有纪律：服务 `AGENT_ENABLED=true` 启动并记录启动时间、快照纪律（HEAD + runner sha）、LongCat 串行、既有 23 项基线测试失败非回归、先红后绿、判定结论必须可复算（sessions json / DB / 日志）。

## 3. 验证协议（run-12）

命令同 V2 执行书 §5.4：`gate2_runner.py --run gate5-dev-run-12 --all --base-url http://127.0.0.1:8000` → `gate5_judge.py` 两层判定。

| 主轴 | run-8 | run-10(A) | run-11(G2) | **run-12 判据** |
|---|---|---|---|---|
| PLANNER_PARSE_ERROR | 7/10 | 0/10 | 0/10 | 维持 0/10（回退即停查） |
| EVIDENCE_COVERAGE_DEFICIENT | 2/10 | 8/10 | 6/10 | **≤ 2/10** |
| ISSUE_DECOMPOSITION_INVALID | - | 0 | 1/10 | **0/10** |
| GENERATOR_FAILURE | - | 1/10 | 2/10 | **0/10** |
| has_final（final_chars>0） | 8/10 | 1/10 | 1/10 | **≥ 5/10** |
| full_closure（两层 judge） | 0/10 | 0/10 | 0/10 | **> 0（实质抬升）** |

解读注意：run-10 的 coverage 8/10 是 parse 清零后暴露的幸存者失败面，与 run-11 的 6/10 同质（writer 绑定失败）——W1/W2 直接对准；has_final 与 full_closure 是全局验收卡点的直接观测量。

## 4. 停止条件

- W1 回喂导致时长/成本恶化（每题最坏 +2 次生成调用）或 GENERATOR_FAILURE 上升 → 记录数据回根因，不盲目提高重渲染次数。
- run-12 coverage 仍 ≥ 4/10 → W1/W2 对绑定失败无效，升级 Owner 复评（候选方向：plan-then-execute、writer 换更强模型、verifier 阈值调整——均需新决策书）。
- 必须改冻结物/评测器/prompt 才能让测试通过 → 停，上报。
- 同一缺陷第 2 轮修复仍红 → 停，升级复评（V1 任务书 Gate 4 纪律）。

## 5. DoD

- [ ] W1 编排回喂循环落地 + 3 用例红→绿 + chat_integration 全量回归绿 + controller 测试不动
- [ ] W2 writer json_schema 接入 + 单测（bind 断言 + 回退链）
- [ ] W3 decomposer json_schema 接入 + 单测
- [ ] W4 决策记录（批/不批，附 Owner 结论）
- [ ] run-12 全量判定落盘本文件附录（对照表 + 失败归因）
- [ ] 未改任何冻结物 / prompt / 评测器；`git diff --check` 干净

## 6. 实施顺序与成本预估

1. W1（mock 测试零模型成本，先行）
2. W2 / W3（离线 + mock）
3. W4 待决策后实施（一行排序 + 对照测试）
4. 快照纪律 + run-12（LongCat 付费一轮：10 题 × 每题最坏 2 次渲染调用；串行；时长与 run-11 同量级或略增）
