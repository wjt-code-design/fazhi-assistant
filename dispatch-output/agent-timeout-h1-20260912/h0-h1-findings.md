# H0 起点核对 + H1 检索超时定位（2026-09-12）

接手依据：`docs/final-agent-handoff-20260912.md`。本文只记录**已核实事实**与**明确标注的未证部分**。
本轮未改任何项目文件，未发起任何付费调用（费用增量 0）。

## H0 起点核对

| 项 | 结果 |
|---|---|
| 7 个候选文件 SHA-256 | **全部匹配**第一轮 `candidate-manifest.json` 的 `after_sha256`，行数一致 |
| 工作区 | 大量未提交修改（预期），**不可**整仓 reset |
| 服务/runner 进程 | 无匹配实例（tasklist 无常驻 python/uvicorn/serve；18111 无监听） |
| 未决外部请求 | cost ledger 4 次预约全部有 finished 记录 |
| 隔离库终态 | `status=failed`，`state_version=4`，`last_error_code=TOOL_TIMEOUT` |

### 「HTTP 200 + 1053 字符 + Agent failed」为何同时成立（已核实）

- `agent_runs.status='failed'`、`agent_completed=false` —— **Agent 主链路未完成**。
- SSE 事件序列 `status, restart, content×172`：`restart` 只由 fallback 产生，`content` 只由 **fast path** 产生。
  → Agent 返回的 outcome 是 **`fallback`**（TOOL_TIMEOUT 属可回退的技术故障），随后主程序走了 Fast Path 降级链。
- DB 里那条 1053 字符 assistant 消息是 **Fast Path 的 RAG 答案**，不是 Agent 终稿，不能计入 Agent 成果。

## H1 根因：超时来自「配置延迟尺度不匹配」，不是架构缺陷

### 已核实的三处常量与实测

| 位置 | 值 | 性质 |
|---|---|---|
| `backend/tools/gateway.py:126` `retrieve_laws` `timeout_seconds` | **8.0s** | 外层等待上限（硬编码，`settings.py` 无对应开关） |
| `backend/retrieval.py:111-120` SiliconFlow rerank `httpx.post(timeout=…)` | **30s** | 内层单次 HTTP 超时 |
| 实测 rerank 实际耗时（本轮账本） | **11.86s / 5.82s**，均 HTTP 200 | 真实依赖延迟 |

→ 内层依赖真实延迟 **1.5–2.5 倍**于外层等待上限，`TOOL_TIMEOUT` 不是边界情况，而是稳定复现的预期结果。

### C01 统一时间线（DB 存的是 UTC naive，+8 得北京时间；与账本 epoch 对齐误差 <0.01s）

| 北京时间 | 事件 | 证据 |
|---|---|---|
| 22:07:48.96 | qwen 第 1 次调用发起（Agent 首个 LLM 步） | cost-ledger call1 reserved |
| 22:08:10.96 | qwen 第 1 次返回（耗时 22.0s） | cost-ledger call1 finished |
| 22:08:11.06 | `retrieve_laws` 提交（state_version=2） | agent_steps id=2 |
| **22:08:13.20** | **rerank #1 HTTP 启动**（提交后 2.14s，即本地检索段） | cost-ledger call2 reserved |
| 22:08:19.07 | 外层 8.006s 到期 → `TOOL_TIMEOUT`（state_version=3） | agent_steps id=3 duration_ms=8006 |
| 22:08:19.09 | failure 落库（state_version=4） | agent_steps id=4 |
| **22:08:19.34** | **rerank #2 HTTP 启动**（到期后 0.27s） | cost-ledger call3 reserved |
| 22:08:25.06 | rerank #1 返回 200（11.86s） | cost-ledger call2 finished |
| 22:08:25.16 | rerank #2 返回 200（5.82s） | cost-ledger call3 finished |
| 22:08:31.13 | qwen 第 2 次调用发起（Fast Path 生成降级答案） | cost-ledger call4 reserved |
| 22:08:51.94 | 返回 → 1053 字符 fallback 文本 | cost-ledger call4 finished |

### 三条可核实结论

1. **到期后才启动新的远程调用：是。** rerank #2 在外层到期后 **0.27s** 发起。
   来源已由代码路径确认：Agent 返回 `fallback` → `main.py:1404 fallback_to_fast_path` →
   `main.py:714 _prepare_fast_path_only` → `main.py:668 retrieve=retrieve` →
   `retrieval.retrieve()` → `hybrid_retrieve()` → `_rerank_docs()`。
   即 **Fast Path 对自己的第二次检索**，与超时工具线程**并发重叠**。
   → 一条用户消息触发了 **2 次本地检索 + 2 次远程 rerank + 2 次 LLM 调用**，其中第一次检索其实会在超时后约 4s 成功返回 200（冗余）。
2. **后台容量释放：约 6s 后。** 超时线程无法被 `future.cancel()` 强停（`gateway.py:3-5, 239-241` 已声明），
   直到 22:08:25.16 才释放执行器容量。`BoundedExecutor(max_workers=4, max_outstanding=8)` 本身有界。
3. **晚到结果未破坏终态：已核实无覆盖。** run 保持 `failed` / `state_version=4`；
   fallback 的 assistant 消息经由 Fast Path 正常写入，不是 Agent 终稿守卫漏放。

### 未证实（不得据此下结论）

- 两次 rerank 是否为**同一 query**：guard 未记录 stage / request_id / query 摘要哈希。代码路径说明二者来自不同层，但无直接日志。
- 冷启动 / 本地检索 / 远程重排的**精确耗时拆分**。仅测得：提交 → 首次 rerank = 2.14s（本地段）；rerank HTTP = 11.86s。
- 是否构成「架构缺陷」：证据只支持**外层等待上限与真实依赖延迟不匹配**；外层快速失败 + 内部有限收尾本身可以是合理设计。
- 原 judge 的法律语义结果：`passed=False` 未做人工/独立复核，保留 REVIEW。

## 待用户拍板的产品口径

交接文档明确：**用户尚未给出「必须在 8 秒内完成」的产品要求，现有常量不视为已确认 SLA**。
因此下一步的最小修复方向取决于一个产品取舍：

- **甲：放宽外层等待**（如 `retrieve_laws` 8s → 覆盖实测 p95 的 ~20s），并把内层 rerank HTTP 超时压到剩余预算之内，
  使超时前能降级为余弦精排并**返回成功**而非 `TOOL_TIMEOUT`。代价：最坏用户等待从 8s 上升到 ~20s。
- **乙：收紧内层、保住 8s**（rerank 超时 30s → 约 6s），让超时前必然降级为余弦精排并返回成功。
  代价：rerank 时常被跳过，检索排序质量下降（与 ADR-011「rerank 是准度主菜」冲突）。
- **丙：两者折中**（外层放宽到 ~15s，内层 rerank 设 ~10s 且严格小于剩余预算）。

共同点：都需要**内层超时严格小于外层剩余预算**这一条，否则 `TOOL_TIMEOUT` 会持续复现。

用户口径（2026-09-12）：选 **丙（折中）**；冗余放大问题按我的建议处理 —— **先只定时限，不动 fallback**。

## H1 修复记录（已实施，6 个文件）

方案：外层等待放宽 + 内层尝试上限收紧 + **把外层剩余预算作为单调时钟截止点传给内层**，
使内层在启动任何新远程调用前先检查预算。不改 fallback、不改缓存策略、不改 steps/tool_calls 硬上限。

| 文件 | 改动 |
|---|---|
| `backend/tools/contracts.py` | `ToolContext` 新增 `tool_deadline_monotonic: float \| None = None`（服务器独占注入；`ToolContext` 从不被序列化，已核实） |
| `backend/tools/gateway.py` | 新增 `_with_wait_deadline()`，提交前把 `time.monotonic() + timeout_seconds` 写进上下文；`retrieve_laws` 外层等待 **8.0 → 15.0** |
| `backend/tools/legal_retrieval.py` | **有** deadline 时才透传 `deadline_monotonic`；无 deadline 时参数与历史逐字一致（既有签名测试锁住） |
| `backend/retrieval.py` | 新增 `_RERANK_ATTEMPT_TIMEOUT_S = 12.0`、`_RERANK_DEADLINE_MARGIN_S = 0.3`、`_rerank_budget_allows()`、`_RERANK_TIMEOUT_ERRORS`；`_rerank_docs` 每次尝试前查预算，预算不足直接返回 None；三处 HTTP 超时 30 → 12；**超时不再被当成模型故障**（不 `mark_utility_depleted`、不换下一个模型，直接降级余弦精排）；`retrieve`/`hybrid_retrieve` 增加可选 `deadline_monotonic` 透传 |
| `backend/tests/test_retrieval_rerank.py` | 新增 4 项：不变式断言（内层 < 外层）、预算不足 0 次远程调用、超时分类、无 deadline 的共享路径回归 |
| `backend/tests/test_tool_gateway.py` | 新增 2 项：gateway 注入单调截止点、`retrieve_laws` 仅在有预算时透传 |

有界性论证：每次尝试仅在「剩余 ≥ 尝试上限 + 余量」时才启动，故每次尝试最多消耗 `剩余 − 余量`，
逐次迭代后 `Σ消耗 ≤ 初始剩余`，即内层总耗时被外层截止点**硬界定**，不会在外层放弃等待后再开新远程调用。

### 反例（watch-it-fail 已实测变红，非仅断言）

| 反例 | 回退到修复前行为后 | 失败原因 |
|---|---|---|
| 预算不足时 0 次远程调用 | `_rerank_budget_allows` 恒 True | `assert ['m1'] == []` —— 到期后确实发起了远程调用 |
| 超时分类 | `_RERANK_TIMEOUT_ERRORS = ()` | `assert ['m1','m2'] == ['m1']` —— 超时确实被当成模型故障换了下一个并标记耗尽 |

## 残留风险与未解决项（本轮未处理，需接手判断）

1. **降级结果会进检索缓存。** `retrieval.py:817` 会缓存最终 docs，**包括 rerank 被跳过后的余弦序**。
   既有行为对「rerank 失败」就是如此（814 行的注释只为异常路径跳过了缓存）。本轮**未改**缓存策略
   （避免扩大共享路径改动）。新引入的风险是：该降级现在多了一个由**瞬时预算**触发的成因，
   缓存内容会随时序负载波动。建议后续单独评估（例如降级时跳写缓存）。
2. **冷启动/本地检索耗时的余量是常量假设，不是运行时测量。** 实测本地段 2.14s；
   若某次冷启动把本地段推到 >3s，15s 外层仍有 TOOL_TIMEOUT 余留风险。§9.2 建议的阶段计时日志尚未加。
3. **fallback 的第二次完整检索仍在。** 一条用户消息仍可能触发 2 次检索 + 2 次 rerank（本次即如此）。
   修好时限后 C01 预期不再触发 fallback，但该放大在降级场景下依然存在。未改，理由见下。
4. **测试环境未覆盖真实 rerank 延迟**（CI `RERANK_ENABLED=false`），真实分支仍需 H3 在线验证。

## H2 离线验收（最终候选字节）

隔离环境复刻第一轮 `verify.ps1` 口径（假凭据、本机 9 端口、`RERANK_ENABLED=false`、离线嵌入、
独立 test-app.sqlite / test-quota.sqlite），输出全部落在本轮目录，未覆盖第一轮证据。

| 检查 | 结果 | 证据 |
|---|---|---|
| CI 范围测试 + 覆盖率 | **exit 0；939 项通过，0 失败 0 错误；覆盖率 78.38%**（第一轮 78.35%，门槛 70%） | `full-tests.txt`、`full-tests.exit.txt`、`full-junit.xml` |
| 全后端 Ruff | 通过，exit 0 | `lint.txt`、`lint.exit.txt` |
| 全后端格式检查 | 207 files already formatted，exit 0 | `format.txt`、`format.exit.txt` |
| 全后端 mypy | 63 source files，无问题，exit 0 | `mypy.txt`、`mypy.exit.txt` |
| 定向用例（2 个改动测试文件） | 37 passed, 6 deselected | `focused-3.txt` |
| watch-it-fail 反例 | 2/2 按预期原因变红 | `watch-it-fail-3.txt`、`test_probe_watch_it_fail.py` |
| 候选清单 | 6 个 H1 文件哈希已重录；第一轮 7 文件哈希未变 | `candidate-manifest-h1.json`、`*.h1-after` |

**939 = 第一轮 933 + 本轮新增 6 项**，数目自洽，无既有用例被删除或跳过。

### 数值自洽性核验（为何 C01 修后应通过）

外层 15s − 本地检索段实测 2.14s = rerank 可用 12.86s；闸门要求 ≥ 12.0 + 0.3 = 12.3s → 12.86 ≥ 12.3 通过，
rerank 正常执行；实测 11.86s 落在 12s 尝试上限内 → 合计 14.0s < 15s，工具返回**成功**结果。
即使 rerank 撞满 12s 上限：2.14 + 12 = 14.14s < 15s → 降级余弦精排后仍返回成功，不再出现 TOOL_TIMEOUT。

### 环境问题（已定位，非代码缺陷）

第一次全量跑测试本身 **100% 全绿（939 个点、无 F/E）**，但进程 exit 1 且汇总/覆盖率输出被截断：
**safe-delete 沙箱拦下了 pytest 自身的临时目录清理**（`AppData\Local\Temp\pytest-of-33393\garbage-*`
共 336 个文件，超过 bulk 阈值 50），抛出 `SAFE_DELETE_BULK_CONFIRM_REQUIRED`。
处理：改用 `--basetemp=<本轮目录>/pytest-tmp` 把临时目录收进工作区，**未关闭安全沙箱**；
重跑即 exit 0 且输出完整。该已废弃输出保留为 `full-tests-preformat.*`，不作为验收依据。

**不动 fallback 的理由**：① 修好时限后 TOOL_TIMEOUT 大概率不再发生，fallback 不再被触发，冗余问题自然消失；
② 复用超时线程的检索结果需要新建跨路径传递/缓存机制，属于「新增调度框架」，与最小修复纪律冲突；
③ 交接文档明确要求此时的改动必须让共享检索路径的默认行为被显式考虑，本轮已尽量把改动收敛在
「默认 None = 行为不变」的可选参数上。

