# 研发过程留痕归档

> **本目录不是产品文档。** 阅读本项目请从 `docs/` 一层的正式文档开始：
> `ARCHITECTURE.md`、`ADR.md`、`BENCHMARK.md`、`PROBLEM_LOG.md`、`code-review-standard.md`、
> `gate-exit-registry.md`、`capability-matrix.md`、`law-source-inventory.md`、
> `quality-eval-report.md`、`remaining-risks.md`、`runbooks/`。

## 这里是什么

2026-08 ~ 2026-10 期间的**研发过程记录**，随项目推进逐日累积。它们的价值是「可回溯」
——某个决定为什么做、当时的证据是什么、谁在什么状态下交接的；不是「可学习」——
内容按当时的上下文写成，孤立的片段容易造成误解。

归档时间：**2026-10-29**（仓库清理时从 `docs/` 一层整体迁入，未改文件名）。

## 内容分类

| 前缀 / 目录 | 含义 |
| --- | --- |
| `handoff-*` | 会话交接记录（上下文、待办、风险） |
| `work-report-*` / `work-progress-*` | 阶段性工作汇报 |
| `progress-*` / `session-report-*` | 进度与单会话复盘 |
| `agent-*` / `plan-agent-*` | 复杂咨询链路（Agent 工作流）的设计与审计 |
| `code-review-*` / `review-*` / `reviews/` | 代码审查报告与复核记录 |
| `execution-plan-*` / `plans/` / `next-assistant-*` | 执行计划 |
| `decision-*` / `policy-*` / `full-scope-*` | 决策记录 |
| `audit_report_*` / `backend-readonly-*` / `*-audit-*` | 各类专项审计 |
| `assistant-briefs/` | 派发给执行方的任务简报 |
| `*-2026xxxx.md` | 带日期的单次记录（票据、复核、交付） |

## 命名约定

沿用归档时的原始文件名（含 `agent-` 前缀与日期戳）。原因：这些文档之间存在交叉引用，
且与 `release-evidence/`、`dispatch-output/`（本地留痕）中的批次目录名一一对应，
改名会切断可回溯链路。若确需重命名，请连同内部引用一起改。

## 与版本库的关系

- 本目录**仍在版本库内**（只是移到子目录），历史可通过 `git log` 完整追溯。
- 同期的过程产物（`dispatch-output/`、`diag/`、`reports/`、`outputs/`）体量约 4.8GB，
  已于同一次清理中**移出版本库**（文件保留在本地工作区），见根目录 `.gitignore`。
