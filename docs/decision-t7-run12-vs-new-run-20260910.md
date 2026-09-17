# 决策记录：run-12 续跑 vs 重开新 run（T7）——2026-09-10

> 决策人：本会话助手（应 Owner 要求"先处理好这些问题"）
> 📌 **本文内容已整合进 `docs/handoff-20260910.md`（唯一入口，§5）。** 本文件保留作**决策留痕**；接手请以交接文档为准。
>
> Owner 已确认（2026-09-10）：新 run 名 = `gate5-dev-run-13`（见 §5）。
> 关联：`docs/handoff-t7-c01-20260910.md`、`dispatch-output/t2-persistence-20260910/t7-run13-manifest.json`、`dispatch-output/t2-persistence-20260909/t7-run12-manifest.json`

---

## 1. 问题

T7 预登记的付费轮 `gate2-run-12` 已被中断，但**不是空白起点**。实测（本次审核）证据目录里已有：

- `gate2-run-gate2-run-12.claim.json` —— run 已被占用（targets=C01…C10，pid=488，started 2026-09-10T04:21Z）
- `gate2-run-gate2-run-12-checkpoint.json` —— **已 durably 记录 4 题**
- `gate2-run-gate2-run-12-sessions.json` —— 尚未生成

已记录的 4 题（均为已发生的付费调用）：

| 案例 | error_codes | 说明 |
|---|---|---|
| C01 | `GENERATOR_FAILURE` | **不是** probe-15 的 `EVIDENCE_COVERAGE_DEFICIENT` |
| C02 | `EVIDENCE_COVERAGE_DEFICIENT` | |
| C03 | `EVIDENCE_COVERAGE_DEFICIENT` | |
| C04 | `CLIENT_TIMEOUT`（`unknown_server_state=true`） | 队列暂停（exit 3） |

**这 4 题是在 C01 修复之前、用旧候选跑的。** 因此该 run 里混着两个代码状态。

## 2. 判据（来自执行书，不是我自创的）

执行书 T7 要求：
- "**记录它与旧 W1–W4 候选的差异**"；
- run 的每一项要能归因到一个**候选**；T0 已把"候选"定义为**脏工作树 + 哈希锚定**（不是 commit）；
- "若名称已存在则禁止覆盖"。

⇒ **推导出的硬约束：一轮 run 的 10 题必须都跑在同一个候选上，否则该轮结果不可归因，不能用作 T7 验收证据。**

## 3. 两个选项的实际后果

### 选项 A：续跑（`--resume`）

runner 语义（已读源码确认）：
- `--resume` 会**跳过 checkpoint 里已记录的案例** ⇒ **C01–C03 不会重跑**；
- C04 是 `unknown_server_state`，`--resume` 下若不给 `--retry-unknown` 会 **exit 5 拒绝**；给了则删掉 C04 记录并**重跑**。

⇒ 续跑实际付费题 = C04 + C05…C10 = **7 题**，产出：
- C01–C03：**旧候选**的结果
- C04–C10：**新候选**的结果

**问题**：一个 sessions 文件里混两种代码状态 ⇒ **该轮无法归因到 post-fix 候选** ⇒ 作为 T7 验收证据**无效**。而且 C01 会永远显示为旧候选的 `GENERATOR_FAILURE`，**把修复效果掩盖掉**。

### 选项 B：重开新 run

- 10 题全部跑在**同一（post-fix）候选**上 ⇒ 可归因 ✓
- 付费题 = **10 题**

### 成本差

B 比 A 多 **3 题**（10 − 7）。

## 4. 决策：**选 B —— 重开新 run**

理由：A 省下的 3 题，换来的是**一轮无法归因、且会掩盖修复效果的验收数据**。T7 的全部价值就是产出可归因的逐题失败矩阵；用 3 题的代价保住它，是明显划算的。

**run-12 的处置：原样保留，不删除、不覆盖、不改名。** 它作为"pre-fix 候选的付费记录"留档，**不计入 T7 验收分母**（分母用新 run 的 10 题）。

## 5. 命名：**`gate5-dev-run-13`（Owner 已确认，2026-09-10）**

命令：`--run gate5-dev-run-13` → 产物 `gate2-run-gate5-dev-run-13-sessions.json`

依据（本次实测）：
- 历史轮次的**内部 `run` 字段**是 `gate5-dev-run-9 / -10 / -11`，文件名 `gate2-run-` 前缀是 runner 自己加的；
- 而 T7 预登记用的是 `--run gate2-run-12`，与历史不一致 → 产物成了**双前缀** `gate2-run-gate2-run-12-sessions.json`；
- `gate5-dev-run-13` 与 run-9/10/11 命名同构、可比。

**预登记记录已生成**：`dispatch-output/t2-persistence-20260910/t7-run13-manifest.json`
（生成脚本 `gen_run13_preregistration.py`，哈希取自 `candidate-manifest-20260910.json`，非手打）

## 6. 执行顺序与付费预算

```
① 更新候选锚定：已完成 —— dispatch-output/t2-persistence-20260910/candidate-manifest-20260910.md
② 启服务（8001，AGENT_ENABLED=true）+ /healthz 就绪
③ C01 单题探针（1 题）→ 判据：errors 里不再出现 EVIDENCE_COVERAGE_DEFICIENT
     - 若报 GENERATOR_FAILURE：不判定修复失败，另立线路记录后仍可继续
④ 探针通过 → 跑新 run 全量 10 题
```
**成功路径总付费 = 1 + 10 = 11 题**（run-12 已花的 4 题不计入）。

**红线**：C04 那类 `unknown_server_state` **未经人工确认不得重跑**；本决策不涉及重跑它（run-12 保留原样）。

## 7. 本决策的不确定项（诚实标注）

- ✅ 新 run 名**已于 2026-09-10 由 Owner 确认**：`gate5-dev-run-13`（§5）。
- C01 失败面非确定（probe-15 = EVIDENCE_COVERAGE_DEFICIENT，run-12 = GENERATOR_FAILURE）⇒ **探针可能给出任一结果**，判定口径已在 §6 ③ 写死；
- 本决策未评估"新 run 是否还需要独立验收者复核"——按执行书 T7，独立验收者的检查是在付费轮**之前**的集成验收环节，本决策不替代它。
