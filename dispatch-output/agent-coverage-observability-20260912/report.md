# 覆盖率闸门失败「可归因化」— 变更报告（2026-09-12）

承接 `agent-quality-h3-20260912/h3-diagnosis-coverage-gate.md` 的建议第 1 项。
**本轮不修业务缺陷，只让下一次覆盖率失败可归因。** 未部署、未提交、未推送、未付费。增量花费 **0 元**。

## 1. 为什么需要这个改动

H3 的 C01 真实运行终态是 `failed / EVIDENCE_COVERAGE_DEFICIENT / VERIFIER:FAIL_SAFE`。
`verifier.py:289` 的判据是 `not issue_claims or not has_effective_statute` ——
「该争点**没有 claim**」与「有 claim 但**未绑定生效成文法**」两种缺口在归档里**完全同形**，
且草稿未持久化，导致一次付费运行的结果无法归因（只能停在推测）。

## 2. 改了什么（3 个文件）

| 文件 | 改动 |
|---|---|
| `backend/agent/service.py` | 新增 `_coverage_issue_facts(state, draft)`：逐争点输出 `{issue_id, claims, claims_bound_effective_statute, deficient}`（**只含标识与计数，无任何文本**）；在终态非 PASS 分支（原 `_persist_drafting_failure` 之前）发一条 `legal.agent` 结构化日志 `coverage_gate_terminal_failure`，携带 `verdict` / `agent_issue_count` / `agent_coverage_gap_count` / `agent_coverage_issues` |
| `backend/observability.py` | `_ACCOUNT_FIELDS` **尾部追加** `agent_coverage_issues`（不动既有顺序，遵守该文件自带规则）。未登记会被 JSON formatter 静默丢弃 |
| `backend/tests/test_agent_chat_integration.py` | 新增 2 项测试：终态失败的逐争点诊断（驱动 `_CoverageLoopTransport(feedback_mode="still_deficient")`，走真实 `execute_agent_request`）+ 白名单登记回归 |

**为什么用日志而不是 DB**：仓库测试对 `AgentStep.result_summary` 有**精确等值断言**
（`VERIFIER:REWRITE` / `ATTEMPT_RESERVED` / `WRITER:UNKNOWN_EVIDENCE_ID`，见 test_agent_chat_integration.py:984/1158、
test_agent_coverage_loop.py:192），该列由 `CheckpointMetadata.result_code` 写入，
改其语义会破坏既有契约；新增 decision 行则有扰动步骤序列的风险。日志方案零 DB 结构扰动，
且字段白名单机制本就是仓库既有的诊断通道（V2-T8 先例：`agent_coverage_gap_count` 等）。

**判定口径复用而非重写**：`_coverage_issue_facts` 用 `writer.issue_is_deficient`（其 docstring 自称
谓词单一真源）与 `is_effective_statute`，并与 `_deficient_issue_ids` 同用 `state.evidence` 全局视图，
口径与既有缺绑定分流一致。**未修改 `verifier.py`**（`service.py:129` 注明该文件冻结，执行书 T0 红线）。

## 3. 顺带修掉的一个潜在缺陷（必须披露）

`service.py` 原第 387 行在 `except Exception:` 块内有一句**冗余的局部 `import logging`**
（模块顶部第 5 行已导入）。它把 `logging` 变成 `execute_agent_request` 整个函数的**局部名**，
因此任何**绕过该 except 块**却使用 `logging` 的路径都会抛
`UnboundLocalError: cannot access local variable 'logging'`。我的埋点首次运行即撞上它（见 `watch-red`→`watch-green` 之间的失败）。
删除该冗余导入后行为不变（同名模块级导入已在作用域内），并消除了这个潜在缺陷。**此为必要改动，不是顺手重构。**

## 4. 怎样证明

### 4.1 watch-it-fail（实现前先跑，确实变红且原因正确）

`watch-red-coverage-diag.txt`：实现前跑新测试 → **2 failed**，失败原因是设计要测的东西，不是笔误：

```
>       assert records, "覆盖率终态失败必须留下 agent_coverage_issues 诊断，否则失败不可归因"
E       AssertionError: 覆盖率终态失败必须留下 agent_coverage_issues 诊断，否则失败不可归因
E       assert []
...
>       assert "agent_coverage_issues" in _ACCOUNT_FIELDS
E       AssertionError: assert 'agent_coverage_issues' in ('method', 'path', 'status', ...)
```

同一次运行里 `assert result.reason_code == "EVIDENCE_COVERAGE_DEFICIENT"` **已通过** ⇒
测试确实驱动到了目标终态，不是在别的分支上空断言。

（中间还红过一次，原因是第 3 节那个 `UnboundLocalError` —— 属实现缺陷，修掉后转绿，已如实保留记录。）

### 4.2 转绿（`watch-green2-coverage-diag.txt`）

`2 passed`。关键断言：
`deficient[0]["claims"] == 0` —— 即替身场景下诊断准确识别出「该争点**完全没有 claim**」这一支，
而不是含混地报「未绑定」。覆盖到的争点则断言 `claims_bound_effective_statute >= 1`。

期望值的**独立来源**：`feedback_mode="still_deficient"` 替身的行为（首轮与回喂都只绑第一个争点）
是测试夹具里**写死的**，与被测的 `_coverage_issue_facts` 无同源关系。

### 4.3 全量离线回归（最终字节）

| 检查 | 结果 | 证据 |
|---|---|---|
| CI 范围测试 + 覆盖率 | **exit 0；941 passed，0 failed / 0 error；覆盖率 78.42%** | `full-tests.txt`、`full-tests.exit.txt`、`full-junit.xml` |
| 全后端 Ruff | exit 0 | `lint.txt`、`lint.exit.txt` |
| 全后端格式检查 | 207 files already formatted，exit 0 | `format.txt`、`format.exit.txt` |
| 全后端 mypy | 63 source files，无问题，exit 0 | `mypy.txt`、`mypy.exit.txt` |

数目自洽：**933（第一轮）→ 939（H1 加 6 项）→ 941（本轮加 2 项）**，无既有用例被删除或跳过。
JUnit 独立读数：`tests=941 failures=0 errors=0 skipped=0`。

### 4.4 字段真能渲染进日志行（独立核验）

`probe_log_field_rendering.py` → `probe-log-rendering.txt`（可复跑，零外呼）：

```
registered_in_whitelist=True
rendered={"ts": "...", "level": "WARNING", "logger": "legal.agent", "msg": "coverage_gate_terminal_failure",
 "verdict": "FAIL_SAFE", "agent_issue_count": 2, "agent_coverage_gap_count": 1,
 "agent_coverage_issues": [{"issue_id": "issue_a", "claims": 1, "claims_bound_effective_statute": 1, "deficient": false},
                           {"issue_id": "issue_b", "claims": 0, "claims_bound_effective_statute": 0, "deficient": true}]}
```

生产链路可达性：`legal.agent`（默认 propagate=True）→ 父 logger `legal`（`setup_logging` 挂 JSON handler，
级别 INFO ≤ WARNING）→ 输出。H3 的 `server.log` 已见同族结构化行，故该通道在生产/验收宿主中确实生效。

## 5. 已知限制（不要当成已完成的事）

1. **没修任何业务缺陷。** 覆盖率闸门仍会失败；本改动只让**下一次失败可归因**。
   其价值要等下一轮付费运行才能证实（未验证）。
2. **只记计数，不记草稿。** 能区分「无 claim」与「有 claim 未绑定」，但**说不出该引哪条法**。
3. **口径有两套视图，日志记的是其中一套。** `_coverage_issue_facts` 与 `_deficient_issue_ids` 一致地
   用 `state.evidence`（**全局**）视图；而 `writer.coverage_feedback_payload` 用的是**每争点**证据视图
   （`service.py:127-129` 明确说明二者不同且为有意设计）。因此日志是**权威裁决的旁证**，
   在极端边界下可能与 `verifier.py` 的判定不完全一致。
4. **渲染这一环没有固化为例行测试。** 仓库守卫只断言「字段已登记」（与 V2-T8 先例一致），
   「确实渲染」用独立脚本核验（4.4）。将来若有人改 formatter 的取值方式，例行测试不会报警。
5. **流程缺口（连续第二轮）**：3 个改动文件在编辑前**未保存字节级快照**，因此没有「纯本轮差异」的 diff 产物；
   `candidate-manifest.json` 只提供 post 哈希与 `.after` 快照。回退需按第 2、3 节逐条反向操作。
6. 本轮**未**验证真实模型行为；C01 的失败仍未修复，检索质量问题（诊断报告第二节）仍待处理。

## 6. 下一步

1. 若要归因**当前这次**已发生的 C01 失败（`h3-diag`），本改动帮不上 —— 它只对**未来**的运行生效。
   若要追查这一次，只能靠离线复现（已证实「问题在 rerank 之前」，见诊断报告）。
2. 建议先处理**检索输入**（`retrieve_laws` 的 query 无锚点 / Agent 路径无改写阶段），
   这需要单独规划 + 离线反例 + 重记候选。
3. 之后再考虑是否申请下一轮付费验证（剩余 **19.9825580 元**）。
