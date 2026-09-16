# Legal Agent V1 灰度、回滚与证据运行手册

本手册是生产变更门禁，不是上线记录。执行人必须把每次命令输出、报告路径、审批人和时间写入部署日志；缺少证据时状态只能记为 `BLOCKED`，不得口头宣称发布成功。

## 1. 范围、角色与硬边界

- 适用范围：Legal Agent V1 的 Gate Shadow、冻结报告对照、5%→10%→25%→50%→100% 灰度及流量回滚。
- 不包含：数据库破坏性迁移、模型/embedding 切换、多 worker、公共 Web 搜索、Agent 写工具。
- 发布负责人：执行配置变更、收集命令输出，不得自行批准自己的阶段升级。
- 审批人：核对同 hash 报告、恢复演练和阶段观测证据，在部署日志中实名批准或拒绝。
- 事件负责人：触发 stop condition 后决定流量回滚；数据恢复只在确认数据损坏后另行授权。
- 密钥只通过运行环境注入。部署日志只记录变量是否存在、配置的非敏感值和版本，不记录 secret 内容。

## 2. 发布证据包

每次候选版本建立一个不可覆盖的目录，至少保存：

```text
release-evidence/<release-id>/
├── release-manifest.json
├── release-policy.json
├── capture-protocol.json
├── frozen-eval-cases.json
├── existing-rag-capture.json
├── agent-capture.json
├── existing-rag-report.json
├── agent-report.json
├── agent-audit.json
├── release-check.json
├── backup-restore-rehearsal.txt
├── preflight-tests.txt
├── shadow-observation.json
├── stage-observations/
│   ├── 005.json
│   ├── 010.json
│   ├── 025.json
│   ├── 050.json
│   └── 100.json
└── deployment-log.md
```

`agent-audit.json` 必须从 `docs/release-evidence/agent-audit.template.json` 复制后填写；它是结构化审核结论，不得包含案件原文、用户身份、密钥或绝对路径。审核人必须逐 case 对照 Agent report 的脱敏 `trace_ref`，并使用 `finding` 而非把已发现问题写成备注或遗漏该行。`trace_ref` 只能使用不透明的 `trace://` 标识（ASCII 字母数字及 `.`、`_`、`-`、`/`），不得使用本地路径、自然语言、URL query/fragment、conversation/user id 或原始 trace 内容。

人工脱敏采集、工件规范化、联合审核与发布检查的交接顺序见 `docs/release-evidence/controlled-offline-dual-run-checklist.md`。该清单只指导创建真实 evidence，不能用模板、占位符或合成数据宣称通过发布门禁。

报告必须来自同一份人工冻结题集，`freeze_hash`、evaluator version、`rubric_hash`、adapter identity、样本量、case rows、git revision、时间戳和执行环境均可追溯，且 `release_eligible=true`。无 adapter 运行只验证 plumbing，不能进入 release checker 的 PASS 路径。安全 findings 必须来自确定性 trace extractor 或独立人工审计标签，不能让被测模型自报安全。LLM Judge 只能附作趋势信息，不能替代确定性安全门禁或单独批准上线。

每次采集前必须先创建并验证 `release-manifest.json`。它是不可变的、无密钥的发布边界，至少绑定候选 commit 与 build digest、题集 hash、evaluator/rubric/policy hash、法规语料与索引 hash、法域和 `law_as_of`、模型与 prompt/tool/config hash，以及 timeout/concurrency/cache/network/retry 采集策略。重试控制内嵌在 `capture-protocol.json`，因此 `retry_policy_sha256` 必须与 `protocol_sha256` 相同，避免维护第二份不可复核的策略。manifest 不包含用户文本、原始 trace、密钥、conversation id 或绝对路径。模板位于 `docs/release-evidence/`；将模板复制到全新的 evidence 目录并填写真实值后，先验证 release policy 并将输出的 `sha256` 填入 manifest：

```bash
cd backend
python scripts/release_policy.py --policy ../release-evidence/<release-id>/release-policy.json
```

再验证 manifest：

```bash
cd backend
python scripts/release_manifest.py \
  --manifest ../release-evidence/<release-id>/release-manifest.json \
  --release-policy ../release-evidence/<release-id>/release-policy.json \
  --capture-protocol ../release-evidence/<release-id>/capture-protocol.json
```

输出的 `sha256` 是该清单的精确字节 hash。候选代码、题集、知识库/索引、模型、prompt、工具策略、配置、release policy 或采集协议任一项变化，均须使用新的 `release-id` 并重新双跑；不得复用旧 evidence。

先用经过审计的两个 generic adapter，或优先使用同一候选 revision 下离线采集的冻结 artifact，分别生成报告。artifact 不得调用模型、查询运行中数据库或读取用户会话；它只保存经脱敏处理的逐 case 结构化答案、trace reference、采集 revision 和不含用户内容的 execution id。`<module>:<callable>` 是部署方实现并版本化的接口，不是可直接复制的字面量：

```bash
cd backend
python scripts/eval_agent.py --mode existing_rag --cases data/eval_agent_complex.json \
  --adapter <module>:<existing-rag-adapter> \
  --output ../release-evidence/<release-id>/existing-rag-report.json
python scripts/eval_agent.py --mode agent --cases data/eval_agent_complex.json \
  --adapter <module>:<agent-trace-adapter> \
  --output ../release-evidence/<release-id>/agent-report.json
```

冻结 artifact 路径如下；两个 capture 必须分别匹配对应 mode，并与 `data/eval_agent_complex.json` 的原始字节 hash 完全一致：

```bash
cd backend
python scripts/eval_agent.py --mode existing_rag --cases data/eval_agent_complex.json \
  --artifact ../release-evidence/<release-id>/existing-rag-capture.json \
  --output ../release-evidence/<release-id>/existing-rag-report.json
python scripts/eval_agent.py --mode agent --cases data/eval_agent_complex.json \
  --artifact ../release-evidence/<release-id>/agent-capture.json \
  --output ../release-evidence/<release-id>/agent-report.json
```

新证据必须是 `legal-agent-eval-artifact/v2`，带 `mode`、`freeze_hash`、40 位 `source_git_revision`、脱敏 `source_execution_id`、`release_manifest_sha256` 和完整有序 `{id, answer}` case rows。v1 只为读取旧证据保留，不能通过使用 `--release-manifest` 的正式发布检查。`existing-rag-capture.json` 与 `agent-capture.json` 是正式证据包的必存输入，必须和 report 一起以只新增、不覆盖方式保存，供后续文件级 SHA 复核；不得只保留报告中的自述 hash。任何 hash/mode/case 顺序不一致、重复/缺失 case、未知 schema 字段或已有输出文件都会阻断。release checker 要求两个 artifact 同时存在且 `source_git_revision` 与 release manifest 的 candidate commit 完全相同；一个 artifact 配一个 generic adapter，或跨候选 revision 对照，均会阻断。报告会保存 artifact SHA-256 和 source provenance，而不保存 artifact 绝对路径。

当前仓库提供了 generic adapter contract、只读 artifact adapter 和离线 artifact normalizer，但尚无真实 Existing RAG/Agent capture。normalizer 只能把另行受控、人工脱敏的 `legal-agent-eval-answers/v1` `{id, answer}` 文件绑定到题集；它不接触运行中数据库、用户会话或模型，也不会自行发起采集。它拒绝额外字段（包括 conversation/user id）、缺失/重排/重复 case、无效 revision、非不透明的 execution id 和已有目标文件。`source_execution_id` 只能是最多 100 个字符的 ASCII 不透明批次 ID（字母数字及 `.`、`_`、`-`），不得使用路径、URL、会话/用户 ID 或自然语言；但代码不能可靠识别 answer prose 中的个人信息，因此脱敏仍需采集责任人和独立审计确认。完成受控采集、独立审计和真实报告落盘前，本节执行状态为 `BLOCKED`。

```bash
cd backend
python scripts/create_eval_artifact.py --mode agent --cases data/eval_agent_complex.json \
  --answers ../release-evidence/<release-id>/agent-answers.deidentified.json \
  --source-git-revision <40-char-candidate-commit> \
  --source-execution-id <opaque-deidentified-capture-id> \
  --release-manifest ../release-evidence/<release-id>/release-manifest.json \
  --release-policy ../release-evidence/<release-id>/release-policy.json \
  --capture-protocol ../release-evidence/<release-id>/capture-protocol.json \
  --output ../release-evidence/<release-id>/agent-capture.json
```

运行发布检查：

```bash
cd backend
python scripts/check_agent_release.py \
  --existing ../release-evidence/<release-id>/existing-rag-report.json \
  --agent ../release-evidence/<release-id>/agent-report.json \
  --release-manifest ../release-evidence/<release-id>/release-manifest.json \
  --agent-audit ../release-evidence/<release-id>/agent-audit.json \
  --release-policy ../release-evidence/<release-id>/release-policy.json \
  --capture-protocol ../release-evidence/<release-id>/capture-protocol.json \
  --existing-artifact ../release-evidence/<release-id>/existing-rag-capture.json \
  --agent-artifact ../release-evidence/<release-id>/agent-capture.json \
  --cases ../release-evidence/<release-id>/frozen-eval-cases.json \
  --output ../release-evidence/<release-id>/release-check.json
```

退出码 `0` 且 `allowed=true` 只是进入运维 preflight 的必要条件，不是生产发布完成声明。checker 从逐 case evidence 独立重算所有顶层 aggregate，并要求 `agent-audit.json` 覆盖 Agent report 的每个 case，匹配同一 manifest 与 trace reference。它还会直接读取两份指定的 v2 capture 文件，复算 SHA-256，并核对模式、冻结题集、case 顺序、候选 revision、执行编号和 manifest 绑定；随后以指定的原始 case set 对冻结回答做只读、确定性评分重放，逐 case 对照报告。`release-check.json` 会固定记录两份报告、两份工件和被重放题集的 SHA-256，便于后续独立审计。报告内自述的工件信息或自行填写的评分不能替代真实文件与重放结果。正式 release audit 的角色必须是 `joint-independent-review`，即同时涵盖独立法律与安全审核；仅法律或仅安全审核即使格式有效也会阻断。缺失审核、案件/trace 不一致或任何确认 finding 同样会阻断。以下任一项同样会阻断：冻结 hash/evaluator/rubric 不同、复现元数据缺失、aggregate 冲突、关键事实编造、越权、无限循环、非法引用，或 Agent 复杂任务质量低于同题集 Existing RAG。evaluator 和 checker 输出路径均使用排他创建；已有文件时退出码 `2` 且原内容保持不变，必须创建新的 release id，不得覆盖旧证据。

## 3. 部署前 preflight

### 3.1 冻结版本与配置

- 记录候选 git revision、构建产物 digest、迁移版本和上次可用 revision。
- 确认 `AGENT_ENABLED=false`、`AGENT_TRAFFIC_PERCENT=0` 是候选版本的安全默认值。
- 确认 `JWT_SECRET`、`LLM_API_KEY`、管理员密码等只存在于受控环境；缺失必须 fail-fast。
- 在候选 revision 上保存后端测试、Ruff、mypy 基线和前端 build 的新鲜输出。
- 在采集前填写并冻结 `release-policy.json`：每项指标必须有 unit、direction、threshold、aggregation、minimum sample、observation window、唯一允许的 exclusions、data source、owner 与 rollback condition；不得在看到结果后改尺子。当前 V1 checker 只接受并执行模板中的两项确定性门槛：`complex_task_quality` 必须为 `agent >= existing_rag`，`safety_findings` 必须为 `0`；缺项、加项、弱化 threshold/aggregation/data source/rollback condition 均会阻断。新增可发布指标必须先扩展 checker 与契约测试，不能仅修改 policy JSON。
- 在采集前填写并冻结 `capture-protocol.json`：Existing/Agent 题集顺序、超时、重试、并发、缓存、联网、工具预算和失败行保留规则必须一致。先使用纯合成、无敏感数据样本 dry-run；dry-run 不通过不得采集冻结题集。

### 3.2 备份与隔离恢复演练

普通 Agent 流量回滚不恢复数据库，因为 run/step/claim trace 必须保留。数据库恢复只用于迁移或数据损坏。上线前仍必须完成可恢复性证明：

1. 暂停后端写入，记录源库关键表行数：`conversations`、`messages`、`agent_runs`、`agent_steps`、`agent_evidence`、`agent_claim_checks`。
2. 使用仓库脚本创建 SQLite 与 Chroma 备份；目标目录必须是受控备份卷中的全新路径，已存在时脚本退出码为 `2` 并拒绝覆盖，且不能放入 git 工作区：

   ```bash
   cd backend
   python scripts/backup_data.py --out <approved-backup-path>/<release-id>
   ```

3. 确认脚本退出码为 `0`、输出 SQLite `integrity_check=PASS` 且 Chroma 目录复制/导出完成。缺 SQLite、完整性失败、缺 Chroma、目录复制或导出失败都会非零退出且不打印“备份完成”。`--skip-chroma` / `--skip-chroma-export` 只能在数据负责人预先批准并在日志记录缩小备份范围时使用；Legal Agent 依赖 Chroma 的生产发布默认不得跳过。这些仍只是备份完整性检查，不等于恢复演练。
4. 将备份恢复到隔离的临时目录/临时容器，绝不覆盖生产路径；在恢复库运行应用迁移两次以证明幂等。
5. 对比上述关键表的源库/恢复库行数，并在恢复库执行一条只读会话查询和一条 Agent trace 关联查询。
6. 对隔离恢复环境运行 `/healthz`、Fast Path 冒烟和只读检索冒烟。全部通过后保存输出与操作者；失败即阻断。
7. 删除隔离恢复副本前确认它位于批准的临时目录。保留原备份及其 hash/介质位置。

仅有备份文件、没有隔离恢复和行数/查询证据，视为没有可用备份。

### 3.3 四个候选版本剧本

在同一候选构建上执行并保存脱敏 trace：

1. `Fast Path safe-off`：Agent 关闭时普通咨询仍走原路径，且不创建 AgentRun。
2. `Verified Agent final`：复杂任务只在 Gate 接受后进入 Agent，Verifier PASS 先于 assistant Message 和 `final` 可见。
3. `Clarification/resume`：追问由同一用户、会话、run 和精确 state version 恢复；不新增 AgentRun 或重复 user Message。
4. `Failure boundaries`：策略/所有权/输入/普通 verifier 失败不回退；白名单技术故障才记录原因并进入 Fast Path；断连无占位 assistant。

任一剧本失败，候选版本不得进入 Shadow/灰度。

## 4. Gate Shadow、受控离线双跑与 Agent Shadow Traffic

### 4.1 Gate Shadow

配置：

```dotenv
AGENT_ENABLED=false
AGENT_SHADOW_ENABLED=true
AGENT_TRAFFIC_PERCENT=0
```

用户仍收到 Existing RAG 答复。观测 `agent_gate.total_predictions`、mode counts、reason-code counts 和 technical-failure count；抽样只能使用脱敏 correlation id，不保存原始用户文本、附件或身份字段。

### 4.2 Agent Shadow Traffic

当前 V1 在线 `/api/chat` 已实现 Gate Shadow 和实时灰度，但**没有**“后台执行 Agent、同时永远向用户展示 Existing RAG”的双跑执行器。不得把 `AGENT_ENABLED=true` 冒充 Shadow Traffic。

在专用 shadow executor 和生产 evaluator adapters 接线前，现有机制只能完成 **Controlled Offline Dual-run**：针对同一冻结题集的 Existing/Agent 离线受控对照；它不是在线真实流量 Shadow。正式双跑必须使用同一 release manifest 与 capture protocol，并保留所有失败行。报告不完整或 checker 拒绝时，灰度保持阻断。未来接入后台双跑时必须保证：只读工具、独立预算、结果不写 assistant Message、不影响用户时延、脱敏 trace、有 kill switch，并另行测试。

## 5. 分级灰度

严格按 `5% → 10% → 25% → 50% → 100%`，不得跳级。每一级：

1. 由发布负责人写入目标比例，保持 `AGENT_ENABLED=true`；`AGENT_TRAFFIC_PERCENT` 只取本阶段值。
2. 重启/重载后读取运行中容器的非敏感环境值，确认实际配置，不以 `.env` 文件内容代替运行态证据。
3. 运行 `/healthz` 和四个生产剧本；任一失败立即停止。
4. 完成预先记录的观测窗口和样本条件。流量不足时延长窗口，不降低样本尺子。
5. 保存本阶段 dashboard/日志快照并再次运行同 hash release checker。
6. 审批人核对证据，在部署日志写明 `APPROVE` 或 `REJECT`。没有显式人类批准不得进入下一比例。

每阶段至少观察：

- Gate：预测总数、Agent/Fast mode、reason codes、technical failures。
- 实际路由：Agent/Fast 次数、fallback 次数与技术原因；不得用 Gate 预测冒充实际执行量。
- Agent 运行：状态分布、失败/降级原因、预算超限率、重复动作阻断、工具调用量。
- 质量安全：关键事实编造、非法引用、权限/隐私事件、Verifier verdict、Issue Recall、Evidence Coverage、Clarification Precision、Agent Gain。
- 性能：端到端 p50/p90、TTFT、断连、队列繁忙；比较口径和排除项必须与冻结报告一致。
- 数据/服务：`/healthz`、错误率、SQLite 锁/完整性、Chroma 可用性、assistant 单写一致性。

规范未提供统一延迟或错误率数字阈值，因此本手册不虚构。团队必须在每次发布前从现有生产 SLO/同 hash 基线填写具体 stop threshold；未填写等同不允许灰度。

## 6. 立即停止条件

以下任一事件无需等待观测窗口结束，立即停止升级并执行流量回滚：

- 任何关键事实编造、权限绕过、无限循环、非法引用、隐私/安全事件。
- Agent 复杂任务质量低于同 hash Existing RAG，或报告/hash/复现元数据不可追溯。
- 非白名单失败静默进入 Fast Path，或 fallback 原因/实际路由缺失。
- assistant 重复写入、run 所有权/version 绕过、trace 丢失或数据库完整性异常。
- `/healthz` 或四个生产剧本失败。
- 超过发布前已记录的延迟、技术失败、预算或断连 SLO。

## 7. 流量回滚

流量回滚先切断 Agent 答复，不删除 run/trace，不自动恢复数据库：

```dotenv
AGENT_ENABLED=false
AGENT_TRAFFIC_PERCENT=0
```

执行步骤：

1. 记录触发条件、当前 revision/比例、最后正常时间和事件负责人。
2. 修改受控运行环境中的两个变量并重启后端；默认同时关闭 `AGENT_SHADOW_ENABLED`，除非事件负责人明确要求继续只读 Gate 观测。
3. 从运行中容器读取非敏感配置，证明 Agent 已关闭且比例为 0。
4. 验证 `/healthz`、Fast Path safe-off、登录和核心只读检索；确认新请求不创建 AgentRun。
5. 保存回滚后的 Gate/route/错误快照。已有 AgentRun、AgentStep、Evidence、ClaimCheck 全部保留用于取证，禁止批量删除。
6. 在 `docs/PROBLEM_LOG.md` 或事故系统记录原因、影响、时间线和恢复证据。

若发现数据损坏，停止写入后由数据负责人依据已验证备份执行独立恢复流程。恢复前先保留当前损坏副本；恢复后重新比对表行数、运行迁移、`/healthz`、四个剧本和只读 trace 查询。未经单独授权，不因普通质量/延迟回滚覆盖生产数据库。

## 8. 部署日志模板

```markdown
# Legal Agent rollout <release-id>

- candidate revision / artifact digest:
- previous known-good revision:
- freeze_hash / sample_size:
- existing report / agent report / release-check paths:
- backup hash and medium:
- isolated restore evidence path and row-count result:
- preflight test/build evidence:
- predeclared observation window, minimum sample and SLO thresholds:

| Stage | Start/End | Runtime config evidence | Four scenarios | Safety/quality | Latency/budget | Decision | Human approver/time |
|---|---|---|---|---|---|---|---|
| Gate Shadow | | | | | | | |
| Offline Agent Shadow | | | | | | | |
| 5% | | | | | | | |
| 10% | | | | | | | |
| 25% | | | | | | | |
| 50% | | | | | | | |
| 100% | | | | | | | |

- rollback trigger/time:
- post-rollback config and health evidence:
- retained trace location:
- incident owner and follow-up:
```
