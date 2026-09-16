# Legal Agent v1 部署与值守 runbook（阶段 L/M/N 准备件，2026-09-06）

**当前状态：009 候选门禁 allowed=true（2026-09-07，v2 政策单题容差），阶段 H 恢复演练已通过。**
本 runbook 的部署前置检查清单有效；**灰度执行仍需数据所有者提供目标环境并明确授权真实流量**
（部署安全位保持 AGENT_ENABLED=false）。历史 BLOCKED 记录见 004/005/006/007/008 各 STATUS.md。

## 0.5 Supplemental Safety Gate（SSG）· 附加安全阻断门禁

> **本节为灰度期附加安全阻断门禁（L2），非正式 policy**；正式 policy 语义以 v2 为准，
> SSG 不替代、不覆盖 v2。证据锚：`release-evidence/legal-agent-v1-grayscale-20260907/`。

放行条件（与 §①.5 规划公式一致）：

```
GRAYSCALE ALLOWED = Existing Release Gate PASS (v2, L1)
                 AND SSG PASS (safety_readiness_check, L2)
                 AND Production Prerequisites PASS（环境/授权/R8/回滚）
```

### ASRG 核对项（全绿才放行）
- S1 Crit/High routing FN = 0（G-1 审计：`g1-route-audit-20260907.md`，PASS）
- S2 Routing FN/FP 各 ≤5%（同上，0%/0% PASS）
- S3 Dangerous/unsafe advice = 0（G-2：`g2-audit-20260907.md`，PASS）
- S4 Evaluator 安全项 = 0（011 report 全 0；重采澄清题机械判定 0；全量重评挂账 Final Freeze）
- S5 引用安全 = 0（**必须基于 Final Freeze 后 index 重跑引用 reeval，Phase 5 验收**）
- S6 Technical fail-closed = 100%（G-4：`g4-audit-20260907.md`，30/30 实证 PASS）
- S7 Technical failure rate：灰度后启用（X/N 阈值 ADR 定稿前仅告警/观察）
- S8 Adversarial smoke baseline = PASS（G-3：`g3-audit-20260907.md`，33/33 PASS）
- S9 Required clarification recall：Crit/High miss=0（G-2，PASS）

### SLO（灰度期）
- **technical_failure_rate**：目标 <5%（ADR 草案）；超阈值且 routed_requests≥N 触发告警→HOLD/回滚。
- **p50/p90 延迟**：沿用 §2 同边界基线（p50 47-50s / p90 62-63s）。
- **引用非法率**：0（生成端书名号强制约束生效）。

### 回滚条件（只看技术类，**不含 policy refusal**）
任一触发 → `AGENT_ENABLED=false / AGENT_TRAFFIC_PERCENT=0`，保留 run/trace 证据：
1. Critical 技术故障 count ≥1（如 decomposition 全线失败、verifier 技术故障）；
2. technical_failure_rate 跌破阈值且样本 ≥N（ADR 定稿数字生效后）；
3. generation/degraded/fallback 率异常骤升（与基线比值突变）；
4. 429/余额不足/LLM provider 大面积失败（provider 侧）；
5. 任何 safety finding（危险建议、非法引用、权限绕过）——立即回滚并冻结灰度。

### 用户可见降级提示（fail-closed 兜底）
- 技术故障不得以"空响应"静默收场：前端见空/失败事件时展示
  「服务暂时不可用，请稍后重试；紧急法律问题请咨询律师」；
- `agent_pre_run_failure` / `PLANNER_PARSE_ERROR` 等事件对应的用户提示由前端映射固定文案。

## 1. 部署前置检查（gate 通过后逐项打勾）

- [ ] `release-check-*.json` allowed=true（审计签署 + 政策满足）
- [ ] 最终镜像 ID/digest 记录入发布证据；`docker run --rm --entrypoint sh <img> -c "ls /app/.env"` 无输出
- [ ] Compose secrets/env 注入核验：`.env` 不进 Git/镜像（`git status` 干净、镜像内无 .env）
- [ ] 备份：`backend/scripts/backup_data.py --out <备份目录>`，并在空目录恢复验证
- [ ] 数据库迁移：`backend/migrations.py` 幂等核验 + 回滚步骤演练
- [ ] 回滚镜像标签在位：`ai-legal-helper-backend:pre-e9b0e17`（=004 前）等
- [ ] 生产 `.env` 差异清单（不含值）人工复核；DNS/隧道/证书变更单独授权

## 2. 部署顺序（逐级灰度，禁止自动晋级）

1. Gate Shadow：只观察 gate 决策日志（`agent_gate_mode`），Agent 不执行不展示。
   ⚠️ 仓库无真 Shadow executor（不写业务副作用的双跑）；上线前需评审实现或跳过。
2. 受控离线对照：以本次 capture harness 重跑一次双路径 smoke。
3. `AGENT_TRAFFIC_PERCENT=5 → 10 → 25 → 50 → 100`，每级观测 ≥24h，
   记录：错误率、technical fallback 率、p50/p90、预算超限、用户反馈。
4. 任一 stop condition（错误率骤升、fallback 连发、429/余额、安全 finding、非法引用）
   → 立即 `AGENT_ENABLED=false / AGENT_TRAFFIC_PERCENT=0`，保留 run/trace。

**SLO 状态：未声明**（交接禁止现场编造）。上线前由负责人按同边界基线
（p50 47-50s / p90 62-63s、错误率基线以本 runbook 观测窗口数据为准）填写并冻结。

## 3. 值守表（上线后）

| 周期 | 动作 |
|---|---|
| 每日 | healthz、错误日志、429/余额、fallback 计数、磁盘/备份存在性 |
| 每周 | agent_gate/route 指标复盘、成本对账（LongCat+百炼台单） |
| 每月 | `docs/runbooks/law-updates-monthly.md` 定检、依赖安全复查、恢复抽验 |
| 每候选 | 同边界回归 + release evidence + 审计 + 恢复演练 + 逐级审批 |
| 事故 | 保存 correlation ID 脱敏证据；区分 provider/RAG/Agent/DB/代理/前端；更新 PROBLEM_LOG/ADR |

密钥轮换：定期轮换并验证旧 key 失效；过程不回显值。
（LongCat key 曾在会话中暴露——数据所有者 2026-09-06 决定暂不轮换，责任自担。）

## 3.5 灰度期监控与扫描落地（R11/R8 复审执行件）

**R11 / 技术故障监控查询模板**（日志为 `legal.chat` / `legal.agent` 结构日志）：
- 分解失败：`grep 'ISSUE_DECOMPOSITION_INVALID' <access/log>` → 出现即记录 correlation ID；
- 预运行失败：`grep 'agent_pre_run_failure' <log>` → 提供 `agent_pre_run_reason`；
- 技术故障红线：`grep -E 'PLANNER_PARSE_ERROR|VERIFIER_TECHNICAL_FAILURE|TOOL_TIMEOUT|AGENT_BUDGET_EXCEEDED' <log>`
  → 触发 ADR rollback_triggers（critical technical failure > 0 → 停）。
- 七类指标复盘：`routing_metrics` 进程内计数 + admin 面板；跨重启审计以日志为准。

**R8 复审（expiry 落地）：**
- 定时扫描：`backend/venv/Scripts/python -m pip_audit -r backend/requirements.txt`（每周，结果对比
  `r8-disposition-20260907.json` 基线；新增条目即触发复审）。
- 复审触发：90 天到期 / 下一候选周期 / 扫描新增高危条目——任一触发即按 `r8-disposition` 8 字段重审。

**policy_refusal 不计故障**：`agent_policy_refusal_rate` 与 `unnecessary clarification` 仅观测，不触发回滚。

## 4. 已知部署缺口（下一候选处理）

- `backend/.dockerignore` 已补 `.mypy_cache/`（2026-09-06）——**005 镜像构建于修复前**，
  其内含 mypy_cache（仅构建缓存，无密钥）；下一镜像自然消除。
- 真 Shadow executor 不存在（交接 M 已知）；上线前评审或跳过该级。
- SBOM 为 pip freeze 替代（`release-evidence/legal-agent-v1-20260905-005/sbom-py-freeze.txt`）；
  **CVE 扫描已集成**（pip-audit，CI 步骤 + venv 定时，见 §3.5）。
- 无生产服务器访问凭据：M/N 的实际部署动作需数据所有者提供目标环境后执行。
