# Gate 0：现场仅盘点报告（复杂法律咨询 Agent V1 第一阶段）

> 任务书：`docs/agent-complex-consultation-v1-taskbook-20260907.md` §9 Gate 0
> 日期：2026-09-07 · 实施助手提交 · **只读，未改任何业务代码**
> 状态：待 Owner 与审查者确认基线后方可进入 Gate 1 之后的改动

---

## 1. git 现场

- HEAD：`5c374e0`（master；为灰度治理/doc 提交，**行为代码自 `4e6950a` 后无变更**）
- `git status --short` 未提交修改 **13 个 M + 5 未跟踪**：

| 类别 | 文件 | 处置建议 |
|---|---|---|
| CRLF 行尾噪声（12） | CONTRIBUTING.md、prompts.py、retrieval.py、capture_eval.py、recompute_boundary_manifests.py、test_capture_eval.py、test_citation.py、test_prompts.py、diag/PROGRESS、bind_claims.py、capability-matrix.md、quality-eval-report.md | 已实证 `--ignore-space-at-eol` **0 内容差异**；不提交 |
| 历史证据草稿（1） | `release-evidence/.../independent-review-draft-sha.json` | haimeng 填写的**签署草稿完整副本**（与权威 `independent-review-20260907.json` 同位，历史材料） |
| 旧灰度实验 trace（4 未跟踪） | `diag/grayscale-g1-reroute-{agent,rag}-20260907/`、`grayscale-g3-redteam-20260907/`、`grayscale-g4-fault-20260907/` | 上一任务采集产物；本阶段**不引用、不扩建**（任务书 §3.8） |
| 本任务书（1 未跟踪） | `docs/agent-complex-consultation-v1-taskbook-20260907.md` | 以 Owner 提供的在库版本为准（跟踪与否待定） |

- worktrees：`.worktrees/legal-agent-v1` = 分支 `codex/legal-agent-v1`@`8aecf3e`（推测为审查侧 Codex 工作树，**本助手不进入、不从中读取隐藏题**）；005-009/e9b0e17 detached（历史候选）。

## 2. Agent 主链（第一阶段保留对象，任务书 §3.1）

| 组件 | 位置 | 备注 |
|---|---|---|
| 入口 | `main.py` `/api/chat`（gate 判定 → agent 或 RAG） | gate=agent/gate.py（含既有刑民边界规则，历史材料保留） |
| 执行 | `agent/service.py` `execute_agent_request`（"Execute **or resume** one bounded Agent run"，已有 resume 语义） | 同会话恢复基础 |
| 状态存储 | `agent/repository.py`（agent_runs + LegalAgentState 持久化） | 预算/指纹真源 |
| 澄清交互 | `tools/gateway.py` allowlist 中 `ask_user`（1.0s/0 重试/3 calls/read_only）+ service 返回 `clarification` | **多轮追问的关键工具** |
| 多轮上下文 | `request_bootstrap.py` `recent_messages` / `RecentMessageSnapshot` | 用户更正/继承的承载点 |
| 工具 allowlist | `tools/gateway.py` `_POLICIES`（5 个，**全部 read_only=True**） | retrieve_laws / lookup_article / analyze_contract / retrieve_memory / ask_user |
| 引用链 | verifier/writer/claims evidence_ids（011 已实证书名号强制） | 六段式证据绑定基础 |

**需 Gate 1/2 核验的边界疑点**：`retrieve_memory`（3.0s/4 calls/read_only）——需确认是**会话内**记忆还是跨会话（决策 §3.2 禁跨会话案件记忆）；
若为跨会话检索，第一阶段须确认其数据域或禁用，防止与"不实现跨会话案件记忆"冲突。

## 3. LongCat 配置非敏感摘要

- 现役文本旗舰由 `.env` `LLM_MODELS_JSON` 整体覆盖（非 DEFAULT_ROLES 默认）：
  `key=longcat_text_flag`、`model=LongCat-2.0`、`modality=text`、`tier=flag`、`priority=0`、
  `disable_thinking=False`、`quota_total=1,000,000`（provider=longcat-openai-compatible，与 011 manifest runtime 一致）。
- 密钥/Base URL 不回显（任务书 §10 禁 evidence 泄密）。

## 4. corpus / index 边界（Gate 0 快照，Gate 2 基线将重算 exact hash）

- 活动 collection（restore drill 实证）：`legal_provisions_cos`=10266、`qa_pairs`=279（合计 10545）；
  chroma 内另有 `*_te4` 变体 collection（10266/21）——**需确认 active collections 是否含 te4**（切换 embedding 的产物，潜在边界混淆点）。
- corpus logical hash：`d76220e7…`（011 快照；10545 记录、canonical 8840943）；
  index 当前物理 hash：`f48285e8…`（011 锚 5092468d 已漂移——历史判定为物理漂移、语义未变，旧任务已闭环）。

## 5. 旧灰度文件对本候选的影响

- SSG/ASRG/README_WITH_EXEMPTION/evidence-manifest/ADR：**冻结为历史实验材料**，不作为本阶段通过依据、不继续扩建（任务书 §3.8/§11.1 ✅）。
- gate 加固（CRIMINAL_CIVIL_BOUNDARY，上一任务行为变更）：按 §3.1"保留现有 gate"——现役代码保留；C10 场景主题一致，但**不作 SSG 依据引用**。
- 灰度 trace 目录：历史证据，本候选不读。

## 6. 候选基线建议（待 Owner/审查者拍板）

- **行为代码基线**：`4e6950a`（011 + gate 加固；与 HEAD 行为等价、且为 freeze 的 frozen rev；
  更干净避免 doc 提交噪声）。HEAD `5c374e0`（含 doc，行为同）亦可，二选一由 Owner/审查者确认。
- Gate 2 基线将用 **全新 cache namespace/禁缓存** 与 exact hash（prompt/config/题集/corpus/index）。

## 7. 请求确认项（Owner）

1. 批准候选基线 commit（建议 `4e6950a`）；
2. 批准进入 Gate 1（10 题规格审核 + 10 个待核法条逐项 corpus 核验）；
3. 对 `retrieve_memory` 边界（会话内/跨会话）给出语义裁决或授权实施者核验后报告；
4. 确认 active collection 范围（是否含 `*_te4`）。

---
*本报告不含绝对宿主路径重名数据、密钥或用户数据；全部结论可复现（git/文件路径均相对仓库）。*