# T7 独立验收核查单（替代性）— 2026-09-10

> 产出者：接手会话。未参与 T0–T6 任何实现。
>
> **真实性标注（先说局限，再说结论）**：执行书 §222 要求「**独立**验收者检查 F1 实际跨层红绿、冻结物哈希与调用失败负例」。
> 本单**不是**该要求所指的第三方验收——我是同一 AI 工具链、同一仓库上的另一个会话，仅做到「未参与实现 + 结论全部绑定可复算证据」。
> **字面标准的独立验收仍为缺口**，是否豁免由 Owner 决定（交接文档 §5.5 已自陈该缺口）。
> 本单**不写**实现侧自审结论，只写复算过程与判定。

---

## 1. 候选完整性与冻结物（✅ 全通过）

| 核查项 | 命令/手段 | 结果 |
|---|---|---|
| HEAD 锚点 | `git rev-parse HEAD` | `ebe82e2` ✅ 与文档一致 |
| 脏量 | `git diff --shortstat HEAD` | 13 files / +1893 / −53 ✅ |
| 备份可还原 | `git apply --reverse --check candidate-post-c01fix.patch` | 通过（2324 行 / 112KB）✅ |
| 未跟踪源码副本 | `ls untracked-backup/` | 4 文件在位 ✅ |
| 候选锚定 | 逐文件 SHA256 复算 vs `candidate-manifest-20260910.json` | **17/17 零漂移** ✅ |
| 冻结物（脚本口径） | `verify_frozen_for_handoff.py` | 一致=16 / 变化=4 / 缺失=0 ✅ |
| 冻结物（哈希口径） | 13 项 SHA256 复算 | 0 漂移 ✅ |

4 项"变化"即知情授权改动（`writer.py`/`service.py`/`runtime.py`/`controller.py`），与文档一致。

## 2. F1 跨层红绿（执行书 §222 第一项）

**F1 定义**（执行书 §57–63）：回喂成功后无法通过终稿保存检查——`service.py:125` 原地加计数未保存，`chat_integration.py:190` 要求传入 state 与 durable checkpoint 完全相等 → `AGENT_FINALIZATION_CONFLICT`。

| 环节 | 核实 | 结果 |
|---|---|---|
| 隔离复现 | `docs/agent-audit-state-repro-20260909.md` | 在位（5435B）✅ |
| 集成**绿** | `test_coverage_rewrite_attempt_is_persisted_before_recall_and_completes`（`test_agent_chat_integration.py:892`） | ✅ 见下 |
| 跨层冻结 | `state_machine` / `repository` / `chat_integration` / `service` 冻结面哈希 | 0 漂移 ✅ |
| 集成**红** | 需回退 `service.py` 造 pre-fix 态 | **未复算**（会改动候选，按 §3.3 纪律不做） |

集成绿的独立判读：该用例走**真实 DB 三表**（`AgentRun` / `AgentStep` / `Message`），断言
`outcome="completed"`、`reloaded.verifier_research_returns == 1`、`attempts[0].state_version < stored_run.state_version`、
`result.state_version == stored_run.state_version`、writer 恰 2 次（首轮 + 一次回喂）。

⇒ **执行书 §101 点名的"coverage_loop 只调 helper、不调 storage，F1 因此漏检"这一缺口，已闭合。**
（T5 之前该用例的形状无法触及 storage。）

## 3. 调用失败负例（执行书 §202 DoD 逐条映射）

| DoD 条目 | 覆盖测试 | 现状 |
|---|---|---|
| 成功绑定只调用一次 | `test_schema_rejection_falls_back_exactly_once_per_adapter` | 绿 |
| 无 bind 正常调用一次 | `test_transport_without_bind_invokes_plain_exactly_once` | 绿 |
| 明确能力拒绝至多一次降级 | 同上（参数化 `adapter_name`） | 绿 |
| **超时/鉴权负例不触发格式降级** | `test_non_rejection_failures_never_fall_back`（参数化 status_code / message / exc_factory）、`test_auth_failure_on_bound_invoke_propagates_without_fallback_per_adapter` | 绿 |
| 最终仍走严格本地 schema 校验 | `test_local_schema_build_failure_falls_back_with_diagnostic` | 绿 |
| 三个 adapter 契约一致 | 上述参数化用例跨 adapter | 绿 |

## 4. 全量测试（本次本人运行，非引用旧输出）

`903 tests / 0 failures / 0 errors / 0 skipped`，239.22s。
机器可读口径取自 `--junitxml`（本机 pytest 退出码被 safe-delete 钩子污染，不可信，见 §8.7）。

---

## 5. ⚠️ 发现的问题（按严重度）

### 5.1 🔴 `master` 的 git 历史存在**缺失对象**（资产完整性）

**事实（非推测）**：

- `git rev-list --count master` → `error: Could not read 03a2f140eb847ee149a91de31fdc368834f6621c`
- `git cat-file -t 03a2f14…` → 对象不存在（`could not get object info`）
- `git cat-file -t 0c1eb0c…` → **存在**（commit）
- `git merge-base --is-ancestor 0c1eb0c master` → **是**
- `git log --oneline master` 可读至 `613ecb3`，再往前即被该缺失对象阻断
- **不是浅克隆**：`git rev-parse --is-shallow-repository` = `false`，无 `.git/shallow`
- 其他 ref 完好：`origin/master`=192 提交、`codex/legal-agent-v1`=233、`v1.0.0`=42

**影响**：

1. 任何跨越该洞的历史审计（`git log -S` / `git blame` / `git bisect`）**在本仓库不可用**。
2. T5 对 `agent_max_steps=16` 的"批准来源"引用 commit `03a2f14`（交付报告 §133）⇒ **本地不可验证**。

**不阻塞 T7**：候选锚定是文件哈希 + patch，均不依赖 git 历史（patch 可逆性已实测）。

**定性边界**：**不判定为"编造哈希"**。证据显示该对象曾是 `0c1eb0c` 的父提交、`0c1eb0c` 是 master 祖先，
即它**确实在项目历史图中**，只是当前读不出。成因未查（未跑全量 `git fsck`）。

### 5.2 🟡 T5 的**实质结论**可独立验证且成立（与 5.1 解耦）

- `backend/settings.py:54` → `agent_max_steps: int = Field(default=16, ge=1, le=32)`
- `backend/settings.py` **不在脏文件表内** ⇒ 该值来自 HEAD 树，**不是脏工作树凑出来的**
- `test_agent_gate.py` 现期待 `(16, 10, 3, 2, 1)`

⇒ "代码 16 / 测试陈旧为 8"（契约漂移）的判断成立，且**未通过改 settings 凑绿**。该修复正当。

唯一缺口：批准来源不可复算（见 5.1）。建议在决策留痕中显式标注"该引用当前不可验证"。

### 5.3 🟡 `controller.py` 注释与留痕不符（数字、函数、机制**三者皆错**）

注释位置：`controller.py:708-709`、`controller.py:803-804`、`test_agent_chat_integration.py:1383`。
其表述："边界实测：单轮 **297** 次 planner/评估，终态停在非终态 planning，**靠 step 预算**才被迫中断"。

实证反例：

| 证据源 | 实测 |
|---|---|
| `boundary_empty_evidence.log`（`tripwire=100000`） | `_handle_evaluation` 空转 **10,750+** 次；该场景 **`planner_calls=0`** |
| `boundary_v1_stderr.txt` | 30s 超时 + 栈停在 SQLAlchemy 查询编译 |
| `delivery-report-t2.md §211` | 原终止性测试表现为**挂死（>300s 无输出）**；加 `planner_call_limit=50` 护栏后才"23.6s 快红" |
| `watchitfail_v1_term.txt` | 红值 = **54** 次（上限 5） |
| 交接文档 §4.4 | 297 系早期探针**自设阈值**被裸 `except` 吞掉产生的假读数 |

⇒ 注释给出的"**有界 297 + 靠 step 预算**"是错误印象，恰是本项目最忌讳的
"**自设上限伪装成界**"（§4.4 纪律 3）。**不影响行为**，但会误导后续维护者。

### 5.4 🟡 `service.py:344` 裸 `except Exception` 折叠内部不变式

内部不变式违反（无界循环、`InvalidTransition` 等）统一折叠为 `AGENT_EXECUTION_FAILURE`。
虽有 `.exception(...)` 日志，但返回码丢失异常类别——**这正是 v1"无界"被误读成"有界失败"的通道**。
建议（付费轮后）：折叠前把原异常类名写入 `degraded_reason` / `last_error_code`。

### 5.5 🟡 谓词四处复制 · 💭 风格不一致

"issue 是否已挂有效证据"在 `controller.py:692-698 / 715-722 / 748-753` 各写一份（另 `690` 被上游复用）。
改定义需同步多处。另：`_every_issue_retrieval_attempted` 为实例方法却不引用 `self`，同族兄弟是 `@staticmethod`。

---

## 6. ✅ 本次由我独立证明的事项（非采信文档）

**C01 修复的终止性成立**，四链条：

1. `action_fingerprint` 是 `(issue_id, tool, canonical(args))` 纯函数；扇出与判定两处构造参数**逐位相同**（`RetrieveLawsInput(query=issue.question, k=4)`）→ 判定不会漏配。
2. `_execute_tool` 在**执行前**（`:557`，早于 `:623` 网关调用）即 `register_action` → **检索空命中也会留痕**，这是"试过了"可被检测的前提。
3. `register_action` 用集合并集 → 指纹集**单调增**；分支仅在"存在无证据且无指纹的 issue"时回 PLANNING，而回 PLANNING 必触发扇出补齐 → 该集合收缩至空 → fall through 到 DRAFTING。
4. 幂等短路**确有必要**：`ALLOWED[PLANNING]` 不含 `PLANNING`，`EVALUATING→PLANNING` 才合法。

**边界测试口径合格**：断言用"终态 + planner 调用次数上界（`n_issues+1`=5）"这类**独立信号**，非与实现同源复算。

## 7. 结论

- **阻塞 T7 的技术前置**：无。候选/冻结物/全量测试/负例四项均通过。
- **阻塞 T7 的流程前置**：执行书 §222 要求的第三方独立验收**仍未满足**（本单为替代性，已标注局限）。
- **另有资产风险**：`master` 历史缺失对象（5.1），不阻塞 T7，但使部分历史审计不可用。
- **建议动线**：先跑 C01 单题探针止损 → 见判据后再决定是否投入 run-13 的 10 题。

> 若本单与代码、sessions JSON 或 `candidate-manifest-20260910.md` 冲突，以后者为准。
