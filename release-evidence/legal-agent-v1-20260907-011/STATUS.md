# GATE BLOCKED — allowed=false（方括号记法修复候选 011，v2 政策）

## Boundary
- Release ID: `legal-agent-v1-20260907-011`
- Git revision: `cd86512e646706fd146aeb2a801011096f10693d`
- Backend image: `sha256:b7ffc86411eb136ca41e61094978f28b94be8f199c3a9fb005752edd1acec3ea`（tag `:011`，含方括号修复 + 生成端书名号强制约束）
- Case-set: `86066616…`（v1.2 混合 30 题，与 009/010 相同）
- Manifest: `260896a6…`；Policy: v2（`- 1/N` 泛化）
- Reviewer: 执行者本人（豁免披露延续）

## 采集与结果
- 双路径 60/60：RAG 30/30 零失败（attempt 1）；Agent 30/30（2 题首采分解失败后重采，见下）
- 指标：rag quality **0.6167** / agent quality **0.5167**（010: 0.6583/0.4917；009: 0.6167/0.5833）
- clar_prec：rag 1.0 / agent 0.1667；安全项双方全 0
- 门禁（release-check-20260907.json）：**allowed=false, reasons=[AGENT_QUALITY_BELOW_EXISTING_RAG]**
  （agent 0.5167 < rag 0.6167 - 1/30，差距 -0.10）

## 主目标：方括号记法修复实证 ✅
- **生成端**：SYSTEM_BASE 引用核对纪律补充「必须用《法律全称》第X条书名号，禁止方括号/无书名号变体」；
  011 RAG/Agent 采集 169 处引用全部书名号，**零方括号**（010 有 1 题方括号漏抽）。
- **采集适配器**：capture_eval 新增 _BRACKET_CITATION_RE（[法名 第X条]/[法名第X条]）兼容，
  010 实证受影响题 loan-interest-answer-a2 evidence [] → [民法典:680]；评估器 v1.2.0 零改动。
- **效果**：011 agent 0.5167 > 010 0.4917（+0.025），方括号修复的评估公平性收益实证。

## 采集过程诚实记录
- Agent 首采 2 题（loan-limitations-01 / law-date-conflict-15）SSE `ISSUE_DECOMPOSITION_INVALID`
  （分解器 strict JSON 校验失败，fail-closed）→ **R11 分解失败形态的真实复现取证**
  （结构化日志 agent_pre_run_failure 已落盘）。按纪律保留原失败行（rows.json），
  以新 execution id `eval011-agent-retry2-20260907` 重采 2/2 通过（偶发稀有变体确认，
  与 contract-14 采样 15/15 结论一致）。
- 011 Agent gate 路由 6/30，与 009/010 完全一致（gate 确定性无回归）。

## 治理
- 模板教训：release-policy 填 v2 语义需**同时改 threshold 与 rollback_condition**
  （011 首跑漏改 rollback → RELEASE_POLICY_METRIC_SEMANTICS_INVALID，防护脚本
  diag/diff_policy_011.py 已列差异后修复）。
- 发布资格继续 BLOCKED：Agent v1 相对 RAG 质量优势未获证实（008 终局语义延续）。