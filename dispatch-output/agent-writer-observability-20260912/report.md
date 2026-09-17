# writer 侧可归因诊断 — 变更报告（2026-09-12）

目的：关掉上一轮遗留的二义性 —— 真实 C01 的 `claims == 0` 是「模型没产出」还是「产出后被静默丢弃」，
以及 `_fail` 失败原因究竟由哪个争点触发。**本轮不修业务缺陷。** 未部署、未提交、未推送。增量花费 0 元。

## 1. 改了什么（3 文件，**本轮首次做到编辑前存字节快照**）

| 文件 | before → after | 改动 |
|---|---|---|
| `backend/agent/writer.py` | 649 → 729 行 | 新增模块级 `log_writer_summary()` 与 `_zero_per_issue()`；`_render_once` 增加本地 `_fail_here()` 统一失败出口、逐争点 `proposed/accepted/dropped` 计数、成功路径也记摘要 |
| `backend/observability.py` | 178 → 183 行 | `_ACCOUNT_FIELDS` 尾部追加 `agent_writer_summary` |
| `backend/tests/test_agent_writer.py` | 467 → 537 行 | 新增 4 项测试（(a) 零 claim、(b) 被丢弃、失败原因+争点、白名单登记） |

`service.py` 与 `test_agent_chat_integration.py` 本轮**未改**（哈希已核验不变）。
`agent_writer_summary` 只含标识与计数（`reason` / `has_feedback` / 三个计数 / 逐争点明细 /
`failing_issue_id`），**不含草稿文本**。

## 2. 怎样证明

1. **watch-it-fail（实现前）**：`watch-red-writer-obs.txt` —— 4 项全红，原因为设计要测的东西：
   `assert []`（诊断不存在）、`IndexError`（取不到记录）、`'agent_writer_summary' not in _ACCOUNT_FIELDS`。
   其中第 3 项已通过 `reason_code == "NON_CANONICAL_CITATION"` 断言 ⇒ 测试驱动到了目标分支。
2. **对最终代码复验反例效力**（`probe_watch_it_fail_writer_obs.py` → `probe-watch-it-fail2.txt`）：
   把 `log_writer_summary` 打桩成 no-op 后，3 个目标**全部变红**（`AssertionError` / `IndexError`×2）
   ⇒ 测试绑的是**发射本身**，不是"某处有日志"这种偶然事实。
3. **定向**：`focused-final-writer.txt` —— `test_agent_writer.py` **32 passed**（28 旧 + 4 新，自洽）。
4. **全量（最终字节）**：`full-tests.txt` / `full-junit.xml` —— **exit 0；945 passed；0 failed / 0 error；覆盖率 78.46%**
   （933→939→941→945 逐轮自洽）。JUnit 独立读数 `tests=945 failures=0 errors=0`。
5. **静态检查**：`lint.txt` 0（All checks passed）、`format.txt` 0（207 files already formatted）、`mypy.txt` 0（63 source files）。
6. **字段真能渲染**（`probe_log_field_rendering.py` → `probe-log-rendering.txt`）：
   白名单登记 ≠ 实际渲染，独立核验 `agent_writer_summary` 确实出现在 JSON 日志行里、
   `failing_issue_id` 可还原。

## 3. 我在实现过程中犯的两个错（如实记录）

1. **`replace_all` 越界改名**：把 `_render_once` **之外**的两处 `self._fail(` 也改成了 `_fail_here(`
   （`render()` / `render_for_coverage()`），那里没有该名字 → `NameError`。
2. **`_fail_here` 自递归**：同一次 `replace_all` 把 `_fail_here` **内部**的最后一行改成了
   `return _fail_here(reason_code)` → `RecursionError`，一度让 30+ 个用例失败。
   我是靠**读真实回溯帧**定位的（不是猜），修复后全绿。

教训：`replace_all` 改名后必须**按名字逐处核对作用域**；watch-it-fail 通过 ≠ 全文件通过，
两层都要跑。

## 4. 环境坑（本轮第二次踩到 safe-delete，已写入项目 MEMORY.md）

权威全量第一次跑出 **183 errors / exit 1**，一度像实现问题。实为环境：
`pytest --basetemp` 会在**会话开始时删除**该目录，而我的 `pytest-tmp` 已累积 **335 个文件**
→ 触发 safe-delete 批量守卫（阈值 50）→ `SystemExit(1)` → 所有用 `tmp_path` 的测试在 setup 阶段失败。
**修法：`--basetemp` 每次用全新目录名**。失败产物保留为 `full-tests-BROKEN-basstemp.*`，未删除。

## 5. 已知限制

1. 仍**不含草稿文本** ⇒ 能说清计数与原因，说不出"引用了哪条法"。
2. `has_feedback` 可区分 `render()` 的首稿与通用错误回喂；但 `render_for_coverage` 也带 feedback，
   需结合调用顺序阅读。
3. 字段渲染这一环仍是**独立脚本核验**，未固化为例行测试（与上一轮 `agent_coverage_issues` 同）。
4. 本轮**未**验证真实模型；能否归因要靠下一轮付费运行（已执行，见
   `agent-writer-attribution-20260912/attribution-report.md`）。
