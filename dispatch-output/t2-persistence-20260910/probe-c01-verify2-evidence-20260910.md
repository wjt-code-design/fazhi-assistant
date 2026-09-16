# C01 探针证据记录（第 2 次，`probe-c01-verify2-20260910`）— 2026-09-10

> 结论：**通过**，且满足"issue ≥ 4"硬判据与"修复分支真被触发"的加强判据。
> 每条均可由 `app.db` / sessions JSON 复算。

## 1. 运行参数

| 项 | 值 |
|---|---|
| run 名 | `probe-c01-verify2-20260910` |
| 命令 | `gate2_runner.py --run probe-c01-verify2-20260910 --case C01 --base-url http://127.0.0.1:8001` |
| 产物 | `release-evidence/legal-agent-v1-complex-v1-20260907/gate2-run-probe-c01-verify2-20260910-sessions.json` |
| 服务 | `backend/` venv python 3.11，uvicorn `main:app` @ `127.0.0.1:8001`，`AGENT_ENABLED=true`（已用非付费哨兵验证门放行） |
| 耗时 | 2m25s（含 2 轮澄清往返） |
| 付费口径 | **1 题**（完整 agent run） |

**环境偏离记录**：为绕开沙箱代理劫持 localhost，本次以 `NO_PROXY=127.0.0.1,localhost` 运行 runner。
除此以外与预登记参数一致（run 名按 §5.4 规律、case=C01、base-url 端口 8001）。

## 2. sessions JSON（runner 侧）

```
[C01] rounds=3 clar_rounds=2 answered=1 unmatched=1 final_chars=878
      agent_completed=True over2=False errors=[]
```

- `errors=[]` → **无 `EVIDENCE_COVERAGE_DEFICIENT`** ✅
- `agent_completed=True`、`final_chars=878` → 产出终稿

## 3. DB 侧证据（`backend/app.db`）

**注意口径**：`agent_runs.id` 是 UUID 字符串，`ORDER BY id` 是字典序、**无意义**；必须按 `rowid` 或 `created_at` 取最新。

### 3.1 本次 run

```
rowid=223  run=e47bbcdb-…  conv=2325  status=completed  state_version=17
created_at = 2026-09-10 07:11:17 UTC（=15:11 本地）
issues=4 | 有证据的 issue=4 | 未覆盖=0 | clarifications=2 tool_calls=4 steps=16
  issue_69d82004d7733a4fa7c770a1  evidence_obs=1
  issue_91ea72e8b1ccb1c83b10ce25  evidence_obs=1
  issue_c166043c838d9ea0838b34f6  evidence_obs=1
  issue_1443b1a6dc57d30ca2fb396b  evidence_obs=1
action_fingerprints=4
```

### 3.2 steps 轨迹（`agent_steps`，按 id 升序；只列决策步）

| # | state_version | decision | reason_code | tool |
|---|---|---|---|---|
| 2028 | 1 | bootstrap | BUDGETS_SNAPSHOTTED | — |
| 2029 | 2 | tool_call | EXECUTING | retrieve_laws |
| 2030 | 3 | tool_result | TOOL_SUCCEEDED | retrieve_laws |
| 2031 | 4 | clarification | OUTCOME_CHANGING_FACT_UNKNOWN | — |
| 2032 | 5 | user_fact | USER_CLARIFICATION_RECORDED | — |
| 2033 | 6 | tool_call | EXECUTING | retrieve_laws |
| 2034 | 7 | tool_result | TOOL_SUCCEEDED | retrieve_laws |
| 2035 | 8 | clarification | OUTCOME_CHANGING_FACT_UNKNOWN | — |
| 2036 | 9 | user_fact | USER_CLARIFICATION_RECORDED | — |
| 2037 | 10 | tool_call | EXECUTING | retrieve_laws |
| 2038 | 11 | tool_result | TOOL_SUCCEEDED | retrieve_laws |
| **2039** | **12** | **backfill_retrieval** | **CLARIFY_BUDGET_EXHAUSTED_PENDING_RETRIEVAL** | — |
| **2040** | **13** | **tool_call** | **EXECUTING** | **retrieve_laws（补尾部 issue）** |
| 2041 | 14 | tool_result | TOOL_SUCCEEDED | retrieve_laws |
| 2042 | 15 | conditional_analysis | CLARIFY_BUDGET_EXHAUSTED | — |
| 2043 | 16 | coverage_rewrite_attempt | EVIDENCE_COVERAGE_DEFICIENT | — |
| 2044 | 17 | finalize | VERIFIED_FINAL_STORED | — |

**第 2039 行是本轮最关键的一条证据**：`backfill_retrieval` / `CLARIFY_BUDGET_EXHAUSTED_PENDING_RETRIEVAL`
正是 C01 修复**新增分支**的专属 checkpoint 元数据（`controller.py:815-822`）。
它出现 ⇒ 修复的目标代码路径**确实被执行**（不是空过）；紧随其后的 2040 行即为被补齐的那个 issue 发起的检索。

### 3.3 终稿落盘

```
conv=2325  messages: user len=34 | assistant len=878
```
恰 1 条 assistant 消息 ⇒ 终稿按契约落盘（F1 链路正常）。

## 4. 与 pre-fix 同构运行对照

```
rowid=222  run=2ba87b17…  conv=2323  status=drafting  created=2026-09-10 05:00:00 UTC
issues=4 | 有证据=3 | 未覆盖=1（issue_2a8b2eb1967cf1218fc39bb4 = 0）
clarifications=2  tool_calls=3  steps=12  action_fingerprints=3
```

| 轴 | pre-fix（rowid=222） | post-fix（rowid=223） |
|---|---|---|
| issue 数 | 4 | 4（同构，可比） |
| clarification 轮 | 2 | 2（同构） |
| tool_calls | **3** | **4** |
| 未覆盖 issue | **1** | **0** |
| 终态 | `drafting`（未达终态） | `completed` |
| 终稿 | 无 | 878 字符 |

该签名与交接文档 §4.1 对 probe-15 的描述（`issues=4 但只检索了 3 个`、`clarifications=2/2`、`tool_calls=3`）**逐项吻合**。

## 5. 判据核对（含 §12.2 修正后的硬判据）

| 判据 | 要求 | 实测 | 判定 |
|---|---|---|---|
| §6.3 原判据 | `errors` 无 `EVIDENCE_COVERAGE_DEFICIENT` | `errors=[]` | ✅ |
| §6.3 原判据 | observations 覆盖全部 issue | 4/4 | ✅ |
| **§12.2 硬判据** | **issue 数 ≥ 4**（否则空过） | **4** | ✅ |
| **加强判据** | **修复分支指纹出现** | `backfill_retrieval` @ v12 | ✅ |

**四条全中** ⇒ 本轮不是空过，是对修复的**真实链路验证**。

## 6. 未验证 / 不得声称

- **未跑两层 judge**（`gate5_judge.py`），故 **`full_closure` 未复算**——本记录不声称质量提升。
- `coverage_rewrite_attempt EVIDENCE_COVERAGE_DEFICIENT`（v16）**仍然出现**：按 §7 定义该码是"writer 没引用"，
  修复只解决"issue 未检索"，不解决"writer 不引用"。**属预期内，不是回归。**
- 本记录不构成对其它 9 题的任何结论；run-13 尚未开跑。

## 7. 另附：第 1 次探针（未通过，留档）

```
run=probe-c01-verify-20260910  18s
[C01] rounds=1 clar_rounds=0 final_chars=0 agent_completed=False
      errors=['ISSUE_DECOMPOSITION_INVALID']
```
失败点在 `create_run` 之前（DB 无 `agent_run` 记录），付费仅消耗 1 次分解外呼。
性质：**分解波动**——同输入同模型进程内复现成功（771 字符合法 JSON、3 issues），
故非确定性缺陷；与基线 run-9(2/10) / run-11(1/10) 一致。详见同目录 `decomposer_diagnosis_20260910.log`。
