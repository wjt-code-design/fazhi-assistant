# GATE BLOCKED — allowed=false（引用精度修复候选 010，v2 政策）

## Boundary
- Release ID: `legal-agent-v1-20260907-010-v2`（CONTRACT_ID 标准化：能力变化加 `-v2` 语义后缀）
- Git revision: `b59c708db5918e1442a1a15875d20acc70ebacc3`
- Backend image: `sha256:539fcd7315e3d1ef547a73ae17053c524185f29d54a603b007d155834a8a5d12`（tag `:010`，含 0adbd0e 引用精度修复）
- Case-set: `86066616…`（v1.2 混合 30 题，与 009 相同）
- Manifest: `524726f9…`（release-policy 采用 v2 泛化语义 `- 1/N`，与门禁检查器一致）
- Policy: v2（单题容差泛化文本；safety = 0）
- Reviewer: 执行者本人（用户改派豁免披露延续，与 009 同）

## 采集与结果
- 双路径 60/60 OK：RAG 30/30 零失败；Agent 30/30 零失败（含 1 题重采，见下）
- 指标：rag quality **0.6583**（009: 0.6167，↑0.0417）；agent quality **0.4917**（009: 0.5833，↓0.0917）
- clar_prec：rag 1.0 / agent 0.1667；安全项双方全 0
- 门禁（release-check-20260907.json）：**allowed=false, reasons=[AGENT_QUALITY_BELOW_EXISTING_RAG]**

## 采集过程诚实记录
- RAG：单次尝试 30/30 全过（009 曾 6 次尝试的环境问题已由 launch 脚本绝对路径/辅助容器
  播种/容器内 count 预验证根治）。
- Agent：单次采集 30/30；其中 `penalty-adjust-answer-a10` 首次返回 SSE error
  「服务暂时无响应」（LLM 瞬时故障，chars=0）——按纪律**保留原失败行**
  （diag/official-capture-010-agent/rows.json 原样），以新 execution id
  `eval010-agent-retry-penalty-a10` 重采入库（diag/penalty-a10-retry-draft.json），
  原 capture 备份于 diag/official-010-agent-capture.json.penalty-a10-orig。
- Agent 路由分布：6/30（loan-limitations-01 / contract-comparison-14 /
  law-date-conflict-15 / guarantee-expiry-17 / prompt-injection-19 /
  guarantee-period-answer-a4）——与 009 完全一致（gate 确定性无回归）。

## 质量结论：引用精度修复实证（本候选主目标）
- 三态分级重评（diag/quality-eval-20260907-reeval-010/）：60 回答 **article_missing=0、
  source_missing=0**（009 基线 1 真条号错 + 1 已废止越库）。生成端收敛实证：
  - criminal-civil-boundary-20：009「第一百零十三条」→ 010「第一百零三条」✓
  - law-date-conflict-15：009 引「合同法」→ 010 仅引现行法 ✓
  - construction-payment-16：010 全中文规范记法，无 ASCII 变体 ✓
- **结论：法条引用精度修复（classify_citation 分级 + SYSTEM_BASE 核对纪律 +
  expected_laws 检索前置）在完整新采集上实证引用问题归零。**

## Agent 质量下降归因（诚实，非引用精度回归）
1. **`[民法典 第六百八十条]` 方括号记法**（010 新出现）：答案引用不含《》书名号 →
   capture `_CITATION_RE` 与评估器 `extract_citations` 均按《》正则抽取，该题 evidence
   绑定为空 → coverage 降。**评估器 v1.2.0 冻结不改**；此为「评估器 regex 与生成端
   新记法」的一致性缺口，应在新候选登记为工程项（生成端约束统一《》记法或评估器
   兼容方括号，二选一，预注册后启用）。
2. penalty-a10 采集瞬时故障（已重采，影响有限）。
3. 澄清题 clar_prec 波动（6 问样本小）。

## 下一步
- 本候选主目标（引用精度收敛）**已达成并实证**；发布资格因 Agent 质量下降继续 BLOCKED。
- 修复 1 的策略（统一引用记法）预注册到下一候选（011）再做采集验证。
- 005-009 的治理结论延续：Agent v1「诚实反问 + 安全全零」定位不变。