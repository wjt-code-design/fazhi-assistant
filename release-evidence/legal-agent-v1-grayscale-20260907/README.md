# Agent V1 灰度 SSG 证据目录导航

> 候选：`legal-agent-v1-grayscale-20260907`（commit `4e6950a814…`）
> 状态：**READY_WITH_EXEMPTION**（待部署环境后放行）· 更新：2026-09-07

## 决策链（owner 拍板，全部可追溯）

| 决策 | 依据文件 |
|---|---|
| Agent = 高风险安全护栏（非质量超越） | `docs/decision-agent-position-20260907.md`、`docs/decision-checklist-agent-20260907.md` |
| L1 质量门豁免（单候选灰度，QUALITY_GATE_ONLY，上限 5%） | `docs/ADR-20260907-l1-exemption.json`（结构化权威）+ `.md` |
| R8 整体 Risk Accepted（82 漏洞，90 天复审） | `r8-disposition-20260907.json` |
| 真实流量授权（1%→5%，kill switch） | `owner-authorization-20260907.json` |

## 阶段证据文件索引

| 阶段 | 文件 | 结论 |
|---|---|---|
| Phase 0 快照 | `snapshot-phase0.json`、`PHASE0-STATUS.md` | 8 行为维度 vs 011：7 一致，index DIFFER→S5 重跑 |
| G-1 路由 | `g1-route-audit-20260907.md`、`route-mask-grayscale.json` | S1=0 / S2=0%·0%（gate 加固后） |
| G-2 安全对照 | `g2-audit-20260907.md`、`g2-comparison-source.md` | S3=0 / S9 miss=0 / Case B |
| G-3 对抗基线 | `g3-audit-20260907.md`、`g3-audit-source.md` | S8 PASS（11 类 33 例） |
| G-4 预发布 | `g4-audit-20260907.md`、`g4-fault-agent.json` | S6=100%（LLM500 注入 30/30） |
| G-5 runbook | `docs/runbooks/deployment-v1.md` §0.5 | SSG 门禁/回滚/降级提示 |
| Phase 5 Freeze | `freeze-manifest.json`、`freeze-closure-20260907.json` | 全 SHA 冻结 + 失效重判闭环 |
| Phase 6 签署 | `independent-review-20260907.json` | haimeng PASS（sha 82f0ebfe…） |
| Phase 7 Binding | `evidence-manifest.json`、`s5-reeval*`、`s4-report-agent.json` | 全字段绑定；S4/S5 闭环 |
| R8 | `r8-audit-20260907.json`、`r8-disposition-20260907.json` | 82 漏洞/10 包；APPROVED |
| 授权 | `owner-authorization-20260907.json` | APPROVED |
| 原始回执 | `g1-reroute-agent.json`、`g1-reroute-rag.json` | 双路径 30 题 |

## 机械校验

```powershell
# 任一时刻重新校验（重生成 manifest 后）
python backend/scripts/gen_readiness_manifest.py
python backend/scripts/safety_readiness_check.py --owner-confirm <r8/env/rollback 三项 true/false>
# 期望输出 READY_WITH_EXEMPTION（环境项真实确认后）
```

## 待办（放行前）

1. 部署环境确认（服务器选型）→ 真实状态跑最终 checker；
2. 真实环境回滚演练（`backup_data.py` 已在本地验证 PASS）；
3. 灰度执行：runbook §2，`AGENT_TRAFFIC_PERCENT=1 → 5`（上限），逐级观测 + kill switch。
4. 90 天内 R8 复审（或 Agent 下一候选周期）。

## 红线备忘

- 评估器 v1.2.0 / policy v2 / 011 历史结果一律不改；
- haimeng 签名不再代填；Owner 决策均已在上述文件落档；
- 行为代码/model/prompt/工具任一变更 → §⑦ 失效矩阵重判（本目录证据可能失效）。