# Legal Agent V1 受控离线双跑交接清单

本清单用于将已经完成的本地 Agent、评测与发布门禁，交接给**人工受控的脱敏采集和独立审核**。它不是发布批准书，也不能替代真实 evidence；在所有真实证据齐全前，发布状态必须保持 `BLOCKED`。

## 0. 权责与禁止事项

- 发布负责人：冻结候选版本和证据边界，收集命令输出；不得批准自己的阶段升级。
- Existing RAG / Agent 采集负责人：在隔离环境分别执行双跑并导出脱敏结构化 answers；不得修改题集、补齐失败行或覆盖旧 evidence。
- 联合独立审核人：同时覆盖法律和安全审核；不得是同一采集人或候选实现者。
- 审批人：确认 evidence、恢复演练和人工审核后，才可批准进入运维 preflight。
- 禁止：真实用户会话、生产数据库导出、线上流量、密钥、绝对路径、conversation/user ID、原始 trace、未脱敏案件原文进入 release evidence。
- 禁止：由被测模型担任安全 Judge；安全 finding 必须来自确定性提取或独立审核。

## 1. 创建真实证据目录前的确认

在受控环境中选择新的 `<release-id>`，例如 `legal-agent-v1-YYYYMMDD-NNN`。不得复用已经写入 evidence 的 release id，也不得删除旧文件后重跑。

使用初始化器创建空白、明确 `BLOCKED` 的目录；该命令只复制模板，不生成题集、answers、capture、report 或发布决定：

```bash
cd backend
python scripts/init_release_evidence.py \
  --release-id <new-release-id> \
  --output ../release-evidence/<new-release-id>
```

确认以下项已冻结并记录到部署日志：

- [ ] 候选 commit 与 build digest。
- [ ] 原始冻结题集文件及其 SHA-256；题集须按既定顺序保留完整 case。
- [ ] 知识库 corpus/index manifest、法域和 `law_as_of`。
- [ ] 非敏感 runtime 配置、模型精确 ID/快照、prompt/tool policy hash。
- [ ] 采集协议：两种模式相同的 timeout、retry、并发、缓存、网络和工具预算。
- [ ] 回滚安全默认值：`AGENT_ENABLED=false`、`AGENT_TRAFFIC_PERCENT=0`。

将下列模板复制到真实 evidence 目录；模板中的尖括号内容必须填写真实值，不能保留占位符：

```text
docs/release-evidence/release-manifest.template.json  -> release-manifest.json
docs/release-evidence/release-policy.template.json    -> release-policy.json
docs/release-evidence/capture-protocol.template.json  -> capture-protocol.json
docs/release-evidence/agent-audit.template.json       -> agent-audit.json
```

## 2. 冻结并验证发布边界

先填写 `release-policy.json` 与 `capture-protocol.json`，再填写 `release-manifest.json` 中相应的 SHA-256。重试控制是 capture protocol 的一部分，`retry_policy_sha256` 与 `protocol_sha256` 必须填写同一个文件 hash。所有命令在候选版本、隔离环境内执行。

```bash
cd backend
python scripts/release_policy.py \
  --policy ../release-evidence/<release-id>/release-policy.json

python scripts/release_manifest.py \
  --manifest ../release-evidence/<release-id>/release-manifest.json \
  --release-policy ../release-evidence/<release-id>/release-policy.json \
  --capture-protocol ../release-evidence/<release-id>/capture-protocol.json
```

完成标准：两个命令均成功，manifest 输出的 SHA-256 被记录；任一真实输入变化均建立新的 release id 并重新双跑。

## 3. 人工脱敏的离线采集

分别准备以下 answers 文件：

```text
existing-rag-answers.deidentified.json
agent-answers.deidentified.json
```

每个文件只允许 `legal-agent-eval-answers/v1` schema 和按原题集顺序排列的 `{id, answer}`；不得添加任何身份、会话、路径或原始 trace 字段。保留每个失败 case 的结构化失败回答，不得删除失败行。

采集环境必须满足：

- [ ] 不访问生产数据库、用户会话或线上队列。
- [ ] 不写入 assistant message、Agent run 或业务数据库。
- [ ] Existing RAG 与 Agent 使用同一题集、同一候选 commit、同一 capture protocol。
- [ ] `source_execution_id` 是非秘密、无语义的 ASCII 批次 ID，不包含用户或会话标识。
- [ ] answers 文件已经由采集负责人完成脱敏检查。

## 4. 规范化为 v2 工件并生成报告

对每个模式分别运行 artifact normalizer；下面示例以 Agent 为例，Existing RAG 只替换 `--mode`、answers 与输出路径。

```bash
cd backend
python scripts/create_eval_artifact.py \
  --mode agent \
  --cases ../release-evidence/<release-id>/frozen-eval-cases.json \
  --answers ../release-evidence/<release-id>/agent-answers.deidentified.json \
  --source-git-revision <40-char-candidate-commit> \
  --source-execution-id <opaque-batch-id> \
  --release-manifest ../release-evidence/<release-id>/release-manifest.json \
  --release-policy ../release-evidence/<release-id>/release-policy.json \
  --capture-protocol ../release-evidence/<release-id>/capture-protocol.json \
  --output ../release-evidence/<release-id>/agent-capture.json

python scripts/eval_agent.py \
  --mode agent \
  --cases ../release-evidence/<release-id>/frozen-eval-cases.json \
  --artifact ../release-evidence/<release-id>/agent-capture.json \
  --output ../release-evidence/<release-id>/agent-report.json
```

完成标准：两份 capture 均为 v2；两份 report 均使用 artifact adapter；输出文件均为首次创建、未覆盖旧证据。

## 5. 独立联合审核

审核人以 Agent report 的脱敏 `trace_ref` 为索引，按原 case 顺序填写 `agent-audit.json`：

- [ ] `reviewer.role` 固定为 `joint-independent-review`。
- [ ] 每个 Agent report case 恰好一条 audit row。
- [ ] 法律或安全确认的问题必须填写 `decision: finding` 与受控 finding code。
- [ ] 不得将 finding 写进自由文本备注，也不得省略问题 case。
- [ ] 出现任一确认 finding，发布检查预期拒绝；不得修改答案或报告以取得通过。

## 6. 运行确定性发布检查

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

只有退出码 `0` 且 `allowed=true` 才能进入运维 preflight；它仍不是上线批准。`release-check.json` 必须固定记录两份报告、两份工件和重放题集的 SHA-256。

## 7. 结果分流

- `allowed=false`：保持 `AGENT_ENABLED=false` 与 `AGENT_TRAFFIC_PERCENT=0`；保留 evidence，不覆盖、不删除、不调整门槛后重跑。
- `allowed=true`：执行发布运行手册中的备份/隔离恢复演练、四个 preflight 剧本、人工审批记录；完成前仍不得更改线上流量。
- 任一脱敏、审核、恢复或批准缺失：状态为 `BLOCKED`，不得把离线双跑称作线上 Shadow 或发布成功。

后续详细运维步骤见 `docs/runbooks/legal-agent-v1-rollout.md`。
