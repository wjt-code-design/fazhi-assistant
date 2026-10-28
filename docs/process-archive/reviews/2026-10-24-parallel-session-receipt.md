# 并行会话回执存档（A/B 提交 + 后续增量）

日期：2026-10-24。对象：对本轮“代提交第三方 WIP”与“ruff rev 升级”授权的执行回执，以及之后到 `976bbee` 的增量记录。
性质：**存档**，不是新的审查结论；完整判据见各自专项报告（§5 证据入口）。

## 1. 原回执（A/B 提交结果）

### 1.1 归属更正

- 授权范围为当时 10 个未提交文件：`prompts.py`、`main.py`、`agent/runtime.py`、5 个 backend 测试、`test_prompts.py`、`frontend/tests/chat-cancel.test.ts`。
- `controller.py`/`service.py` 不在范围：已由 Owner 于 10-22 21:47 授权提交（`7c9ecee7`），前序“9 个 WIP”统计漏核此条。
- 本会话仅修复 `test_prompts.py` 的两处旧断言（正向锁新表述 + 反向锁旧句退役），随该批一并提交。

### 1.2 A：代提交第三方 WIP

- commit：`8652a005`（10 files changed，+285/−84）。
- 提交信息已写明：“代提交归属不明的第三方 WIP（10-22 18:48–21:34、10-23 00:10–19:32 两批，非本会话改动），改动者需复核。”
- 差分门禁：HEAD 干净工作树同口径 **23 failed** → 本批 **19 failed**，**0 新增、4 修复**；19 个红灯均为 HEAD 既有基线失败（测试 harness/SDK 版本），与本批无关。
- 门禁：`pytest -q -m "not slow"` 19 failed / 2024 passed / 2 skipped；ruff 0.17 check+format 全过；pre-commit（v0.16.1）全过，换 v0.17.0 后对同 10 文件复跑仍全过。
- 硬约束：只提交、不重建容器、不推送。

### 1.3 B：ruff rev 升级

- commit：`e7134804`（`.pre-commit-config.yaml`，1 file changed）。
- `rev` 从 `v0.16.1` 升到 `v0.17.0`，与工作区 ruff 0.17.0 对齐。
- `pre-commit run --all-files` 首跑命中 **1387 个既有文件**的尾随空白/末尾换行，分布在 `release-evidence/`、`diag/`、`dispatch-output/`、`data/` 等；因含冻结证据产物，**自动修复已全部回滚，未入库**，仅提交 rev 变更。
- 后果：`--all-files` 在空白债清理前仍红；按文件触发的日常门禁为绿（已实测）。未跟踪的评测产物不受影响（`--all-files` 只处理 git 跟踪文件），证据哈希未变。

### 1.4 时间与约束

- A/B 均于 2026-10-24 当天完成。
- 未推送、未重建容器、未部署；线上仍为 F3 重建时的 HEAD（`e713480`）。
- F3 闭环由并行会话执行并回执：`/api/health` 200、P0-1/P0-2/纪律/取消边界在容器内确认、K01 回归正常。**本回执未复验容器**。

## 2. 后续增量提交

| 提交 | 日期 | 内容 | 关键读数 |
|---|---|---|---|
| `5bae84c1` | 10-24 | 离线支持审查器（Q1 方案 B）本体 + 34 单测 + 两套回归集 + runner + 4 份报告 | 21 files，+3178；`agent/service.py`/`agent/runtime.py`/`main.py` 零引用 |
| `b752a11b` | 10-24 | 难绿样本（多跳 6 + 保留意见 6）与重试故障注入读数 | 60 次 9/12；修正版 15 次 15/15；注入 S1 `attempts=2` 成功、S2 `attempts=2` INVALID、S3 `attempts=1` 不重试 |
| `e7394b85` | 10-24 | 账号边界 B01/B02/B03/B05 修复 + 定向测试 | 14 passed；全量 19 failed / 2033 passed，与基线 **0 新增**；前端 91 passed、tsc 通过 |
| `ce4ac382` | 10-24 | 账号边界第 4 轮逐项修复回执 | B01/B02/B03/B05 已修复；B04 未修复（阻塞） |
| `e385f1f8` | 10-24 | 接手期工作汇报更新至 10-24 | 新增 §12 增量，原 §0–§11 保留 10-22 口径 |
| `976bbee` | 10-24 | 三份汇报/回执的过期表述与提交状态复核 | 3 files，+7/−7 |

> 本回执存档及其后的文档修订未逐条列入上表，见 `git log -- docs/process-archive/reviews`。

## 3. 当前状态

- 代码提交止于 `e7394b85`；其后均为文档提交（`ce4ac382`、`e385f1f8`、`976bbee`、本回执存档），逐条以 `git log -- docs/process-archive/reviews` 为准。工作区 tracked 零改动；未推送。
- 容器基线 `e713480`，**不含** `5bae84c1` 之后的提交；Q1 审查器与账号边界修复尚未进入容器。
- Q1 方案 B：固定 2-of-5；缺口 90 次未产出 verdict 5 次（5.56%，CI 2.40–12.36）；绿对照 60 次单次误杀 1.67%、12/12 `SUPPORTED`；难绿 9/12（3 条为出题问题）、修正 15/15；干净误杀 0；**仍不接线上**。
- 账号边界：B01 密码 UTF-8 字节边界、B02 并发失败计数、B03 未知用户名生命周期、B05 迟到 401 均已修；B04 Caddy CF 头信任链未修。
- 门禁：后端全量 19 failed / 2033 passed / 2 skipped；前端 91 passed；ruff 0.17 与 pre-commit（按文件）绿；`--all-files` 因 1387 文件空白债仍红。

## 4. 未闭合项

1. **B04**：需先确认生产入口是直连 Caddy 还是 Tunnel-only；直连则删 CF 并重建 XFF，Tunnel-only 则停发 8088，两者并存需按 cloudflared 来源白名单。决策前不改 Caddy。
2. **19 个基线失败**：`test_stream_cancellation` 15、`test_cancel_boundaries` 1、`test_llm_lifecycle` 3；HEAD 干净树同样红，按技术债另立。
3. **pre-commit 1387 文件空白债**：待定“冻结目录 excludes + 分批修”策略。
4. **Q1 线上阻断**：仍缺更大绿样本、人工仲裁流程与监控口径，未启动。

## 5. 证据入口

- [接手期工作汇报（更新至 10-24）](file:///c:/Users/33393/Desktop/ai-legal-helper/docs/process-archive/reviews/2026-10-22-full-scope-remediation-work-report.md)
- [账号边界第 4 轮修复回执](file:///c:/Users/33393/Desktop/ai-legal-helper/docs/process-archive/reviews/account-boundaries-round4-fix-receipt.md)
- [Q1 支持审查器稳定性报告 §8–§13](file:///c:/Users/33393/Desktop/ai-legal-helper/docs/process-archive/reviews/2026-10-23-round67-q1-support-review-stability.md)
- [账号边界第 4 轮只读审查（上游）](file:///c:/Users/33393/Desktop/ai-legal-helper/docs/process-archive/reviews/account-boundaries-readonly-review-round4.md)
