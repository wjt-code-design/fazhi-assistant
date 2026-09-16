# 法智 Legal Agent V1 设计规格

## 1. 目标与范围

### 目标

在不降低简单法律咨询确定性、引用校验和安全边界的前提下，为复杂法律任务增加受限的自主研究能力：识别争点与关键事实缺口，选择已授权工具，依据证据决定是否继续研究或向用户追问，并将最终结论映射到可追溯证据。

### 成功的真实定义

对同一冻结的复杂法律任务集，Agent Path 相比既有 RAG 能提升争点覆盖和重要结论的证据支持率，同时不出现事实编造、越权工具调用、无限循环或未标识的技术降级。

### V1 范围

- Single Agent Runtime：一个受限的 AgentController，不使用在线多 Agent 协作。
- Fast Path / Agent Path 分流、Shadow Mode、灰度与一键回滚。
- 可恢复的 AgentRun、显式状态机、有限重规划和关键事实澄清。
- 只读 typed tools：法律检索、精确法条定位、合同分析、会话记忆读取、引用验证、向用户提问。
- Issue、Fact、Observation、Evidence、Claim-Evidence 的结构化记录与审计。
- Writer 与 Verifier 分离；保留现有 citation_verify、quality.self_check、normalize。

### V1 非目标

- 全量 Free ReAct、在线 Multi-Agent、LangGraph 迁移。
- 公网案例或法律网页搜索。
- Agent 直接使用 SQL、文件系统、Chroma、缓存写入或知识库更新。
- 自动采纳 QA、修改用户资料、修改系统配置或建立跨会话用户画像。
- 大规模前端重做；前端仅消费新增的 SSE 状态事件并展示非思维链进度。

## 2. 统一术语

| 术语 | 定义 |
| --- | --- |
| Fast Path | 既有确定性 RAG、合同、学习、闲聊、拒答等路径；不运行 AgentController。 |
| Agent Path | 仅处理通过 Agent Gate 的复杂任务的受限研究路径。 |
| AgentRun | 一次可跨 HTTP 请求恢复的复杂任务执行实体，不等同于整个 Conversation。 |
| AgentState | AgentRun 的当前可执行状态快照；不写入 Conversation Summary。 |
| Issue | 为达成目标而必须解决的法律争点。 |
| Fact | 有明确来源的事实；推断不得写入 Fact。 |
| Unknown Fact | 可能改变结论、但目前未得到可靠来源支持的事实。 |
| Evidence | 支持或反驳某一 Issue/Claim 的不可变来源快照，带法律版本和原文定位。 |
| Observation | 一次工具执行的受控摘要，不等同于原始工具结果。 |
| Claim | 最终答复中的重要事实或法律结论，必须绑定 Evidence。 |
| Tool Gateway | 统一执行工具授权、参数校验、预算、超时、审计和幂等的服务端边界。 |
| law_as_of | 本次任务适用法律的基准日期；由服务端当前日期或用户已确认的事实日期确定。 |

## 3. 架构与责任边界

```text
Client
  -> Auth / Rate Limit / Input Normalize / Safety
  -> Agent Gate
       -> Fast Path -> existing RAG / existing finalization
       -> Agent Path -> AgentController
             -> Planner -> ToolGateway -> typed read-only tool
             -> Observation -> Evidence Evaluator
             -> replan | ask user | draft
             -> Writer -> Verifier
  -> citation_verify -> quality.self_check -> normalize -> store -> SSE
```

### Agent 的职责

- 提取 Goal、Issue、Fact 与 Unknown Fact。
- 基于当前 Issue 和已验证 Evidence 选择下一步已授权动作。
- 判断证据不足、事实不足、冲突或可结束。
- 输出解释性 Reason Code；Reason Code 不代替系统授权。

### 确定性系统的职责

- 身份认证、用户与会话归属、权限、限流、预算、超时、重试、审计和持久化。
- 法律生效日期、状态与精确条文的确定性过滤。
- 工具 schema 验证、调用次数、重复动作阻断和 feature flag。
- 引用存在性校验、输出规范化、安全策略和降级可见性。

### 禁止跨越的边界

- LLM 不提供或覆盖 user_id、conversation_id、run_id 的授权范围。
- LLM JSON 不直接执行；所有工具参数必须先通过专用 Pydantic schema。
- Writer 不增加未在 Evidence 中出现的法律、事实或引用。
- Verifier 不读取或展示 Chain-of-Thought，只判断结构化 Claim、Evidence 和输出文本。
- 文档、图片描述、用户文本与历史记忆均为不可信内容，不能变成系统或工具指令。

## 4. 运行状态与恢复

AgentStatus 固定为：BOOTSTRAPPING、PLANNING、EXECUTING、EVALUATING、WAITING_USER、REPLANNING、DRAFTING、VERIFYING、COMPLETED、FAILED、REFUSED。

允许的核心迁移：

```text
BOOTSTRAPPING -> PLANNING -> EXECUTING -> EVALUATING
EVALUATING -> PLANNING | REPLANNING | WAITING_USER | DRAFTING | FAILED
WAITING_USER -> PLANNING
DRAFTING -> VERIFYING -> COMPLETED | REPLANNING | FAILED
```

每次迁移在同一数据库事务内写入状态版本、AgentStep 和审计字段。恢复请求必须以 `(run_id, state_version, user_id, conversation_id)` 比较更新；版本不匹配时拒绝重复执行并重新读取最新状态。

V1 仅支持当前单 worker 部署模型。每个 run 在进程内持有短生命周期执行锁，数据库状态版本防止同进程双请求的丢更新。未来多 worker 前，必须先迁移到具备可靠行锁/事务语义的数据库。

## 5. 数据、证据与防幻觉

### 最小持久化实体

- `agent_runs`：归属、goal、task_type、status、state_version、law_as_of、pending_question、state_json、降级与错误码、时间戳。
- `agent_steps`：run、序号、issue、决策、reason_code、工具、规范化输入、结果摘要、状态、耗时与预算快照。
- `agent_evidence`：issue、source_type、source identifier、原文定位与不可变片段、法律版本元数据、取得时间、可信度。
- `agent_claim_checks`：claim、issue、evidence ids、support verdict、verifier verdict。

`state_json` 用于恢复，表级事件用于审计和评测；两者不能成为两个可独立修改的真源。

### 证据规则

- Fact 必有 source：user、document、conversation 或 tool；Assumption 与 Unknown Fact 分表述，不得伪装成 Fact。
- 法律证据必须带知识库 document/chunk 标识、法名、条号、原文定位、effective_from、effective_to、status 与 law_as_of。
- 一个 Issue 达到 `supported` 的必要条件是：关键事实已满足、存在主要法律证据、没有未解决的关键冲突。
- 任何重要 Claim 没有 Evidence 时，Writer 删除该 Claim 或明确标识为证据不足；不得用语气弱化替代证据。
- 低置信或冲突未决时，输出范围受限的结论与需要核实的事项，不以确定性语言硬答。

### 生成与验证分离

Writer 只消费 Verified Facts、Resolved Issues、Evidence 与 Citation Candidates，先生成结构化 Draft，再渲染文本。Verifier 检查 Claim-Evidence 绑定、覆盖、事实编造、矛盾和过度自信。确定性的 citation_verify 与 quality.self_check 保持最终硬闸。LLM Verifier 不能作为唯一正确性来源。

## 6. 工具契约与预算

V1 工具全部只读，Tool Gateway 是唯一入口。

| 工具 | 允许用途 | 禁止用途 |
| --- | --- | --- |
| retrieve_laws | 调用既有 query understanding 与混合检索，获得法律候选证据 | 直接写缓存、绕开时效过滤 |
| lookup_article | 精确法名/条号定位 | 接受未验证的法名/条号作为事实 |
| analyze_contract_clause | 调用既有合同确定性骨架 | 直接生成最终法律结论 |
| retrieve_memory | 读取授权会话上下文 | 跨用户或跨会话读取 |
| verify_citations | 校验候选引用存在性 | 代替 Claim-Evidence 语义校验 |
| ask_user | 询问一个最高价值的结果改变型事实 | 收集无关背景或循环追问 |

所有工具定义独立输入与输出模型，输出不返回给 Planner 的原始大文本；Gateway 转换为 Observation。V1 预算为：最多 8 个 agent steps、10 次工具调用、3 次重规划、每个 issue 的同工具同参数最多 2 次、最多 2 次澄清、Verifier 回流研究最多 1 次。达到预算后产生可审计的 FAIL_SAFE 或受限答复。

重复动作指纹为 `issue_id + tool_name + canonicalized_args`。相同指纹再次出现时 Gateway 拒绝执行并记录 `DUPLICATE_ACTION_BLOCKED`。

## 7. Agent Gate、缓存与降级

### Gate

Fast Path 包含精确法条、简单单争点咨询、闲聊、明确模板拒答和满足安全/时效条件的缓存命中。Agent Path 仅用于多争点、多阶段、文件比较、关键事实缺口或首次检索后出现新争点的请求。

Gate 首先以可解释规则产出 Reason Code，并在 Shadow Mode 记录预测。冻结标注集校准后才允许轻模型用于边界案例；模型输出不具备绕过规则拒答或安全策略的权限。

### 缓存

- 保留 Fast Path 的既有缓存防护。
- Agent Path 缓存工具结果，键必须包含用户范围、权限范围、law_as_of、工具版本与规范化参数。
- Agent Path 的最终答案缓存 V1 默认关闭。
- 不从相似问题迁移 Fact、Issue、Evidence 或 AgentState。

### 降级

Planner 解析失败、可恢复工具故障或预算耗尽可进入既有 RAG，但响应与 trace 必须带 `degraded=true` 和原因。权限、归属、注入、安全策略与无效 law_as_of 失败不可降级，直接安全终止。部分 Agent 研究结果不得未经验证直接注入降级答复。

## 8. SSE、可观测性与隐私

SSE 仅发送 `agent_status`、`agent_step`、`tool_status`、`clarification`、`verification`、`token`、`final`、`error`、`restart`。客户端永不接收 Planner 内部推理、原始 Prompt、隐私化工具参数或未审计证据。

新增观测字段：run id、step id、gate mode/reason、issue id、tool、耗时、预算、重复阻断、状态迁移、降级原因和 verifier verdict。日志与评测样本必须脱敏用户文本、附件原文和身份字段。Agent 数据的保留期、删除联动和静态加密能力在进入真实生产流量前按部署环境形成独立 ADR。

## 9. 评测、上线与回滚

### 评测先行

建立 20–30 条复杂法律任务集；每条人工标注目标、争点、关键事实、可接受工具、预期法条、应追问事实、重要 Claim 和证据。冻结版本 hash、标注指南、执行环境和复跑命令。

Agent 与 Existing RAG 必须使用相同冻结题集对照。新增指标包括 Gate Accuracy、Issue Recall、Clarification Precision、Tool Selection Accuracy、Replan Success、Evidence Coverage、事实编造率、重复 loop 数、Agent Gain、步骤效率、TTFT 和端到端时延。所有指标记录样本量、口径和已知限制；LLM Judge 只作辅助趋势，不能单独决定上线。

### 上线顺序

1. 离线 benchmark 与工具回归。
2. Gate Shadow Mode：用户继续收到 Existing RAG 答复。
3. Agent Shadow Traffic：后台执行并与 Existing RAG 对照，不展示 Agent 答复。
4. 仅对符合 Gate 的复杂请求按 5%、10%、25%、50%、100% 逐级灰度。

每一级至少观察质量、预算超限、技术失败、降级、隐私事件和延迟；出现事实编造、越权、无限循环、非法引用、质量低于基线或安全事件即停止升级。

### 回滚

配置提供 `AGENT_ENABLED=false` 与 `AGENT_TRAFFIC_PERCENT=0`。回滚只切流量，不删除 run/trace；数据库迁移需在上线前完成备份、升级验证和恢复演练。

## 10. 已确认的关键 ADR

1. V1 采用原生 Python AgentController，而非 LangGraph：现有控制流、单 worker 部署与调试需求更匹配。
2. V1 使用 Single Agent Runtime：复杂度与调试性优先于角色分工。
3. V1 只读工具：任何有副作用的知识、配置、用户资料和权限变更不向 Agent 开放。
4. AgentState 与 Conversation Memory 分离：前者是可恢复执行状态，后者是对话上下文。
5. 先 Shadow、后灰度：没有冻结基线和对照收益，不将 Agent 答复交付给用户。
