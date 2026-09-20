# 票 J · 证据五连问自查（show-your-work-new，2026-09-20 收尾复验）

**性质**：对已入库交付（`1ddeaf0` / `805ad78` / `ad56d29`）的**完成声明复验**，不是新交付。
所有读数都是**本次新跑**的（skill 铁律：上一次运行的结果不是本次的证据）。
**被测态 == 提交态**：`git log` HEAD = `ad56d29`；`git status --porcelain backend/ docs/gate-exit-registry.md`
为空（唯一的 `?? backend/.ptmp-s4-run2/` 是本会话之前就在的未跟踪目录）。

---

## 一、逐声明作答

### 声明 1：J-2 三项交付都在，且四条断言真能红

| # | 问 | 答 |
|---|---|---|
| 1 | 怎么来的 | `git show 1ddeaf0 --stat`（5 文件）与 `git show 1ddeaf0:backend/main.py`；红/绿都是 pytest 实跑 |
| 2 | 能复现吗 | 能：`pytest tests/test_light_exit_gates.py`（本次新跑 **7 passed**，`12/19/20` 三份 stdout）；先红侧是 `git archive b6f0fcc` + 只放这一个测试文件 |
| 3 | 亲眼红过吗 | **是**，在**改前副本树**上：`4 failed, 3 passed`（`04-red-pretree.stdout.txt`），红因原文见下 |
| 4 | 期望独立吗 | 期望来自票面 J-2 的字面要求（"复用纯函数""`_cache_write_ok` 生效""补独立降级信号"），不是复算实现；`multi_incomplete` 的**规则**仍是流式那一份（全仓只此一处定义） |
| 5 | 已知限制 | 见第四节 |

**先红红因原文（逐条为功能缺失，非 TypeError/AttributeError）**

```
AssertionError: 多选漏答的答复进了缓存：[{… 'answer': '**A. 试用期最长不得超过六个月**【判断】正确…本题正确答案为 A。', 'model': ''}]
AssertionError: 引用不在检索条文内的答案进了缓存：[{… 'answer': '根据《民法典》第五百七十七条…'}]
AssertionError: 降级信号未独立落盘：{… 'verdict': 'vague' …} / assert None is True
AssertionError: assert None is False        （控制腿里的新字段取值断言）
```

**控制腿（3 条，两侧都应绿）**：`test_control_light_path_does_not_flag_full_multi_answer` /
`test_control_light_path_plain_question_still_cached` /
`test_control_light_path_cache_write_ok_allows_retrieved_citation`——三条都断言
「**同一请求形状照常写 1 次缓存**」⇒ 同时是先红用例的**分辨率证明**（证明 `sink == []` 是被闸拦下，
而不是"压根没有 `cache_key`"）。改前树上它们**也绿**（`04-red-pretree` 的 3 passed 就是它们）。

### 声明 2：变异 5 条，4 KILLED + 1 预期 SURVIVED

| # | 问 | 答 |
|---|---|---|
| 1 | 怎么来的 | `mut/*/verdict.json`（本次审计产出）；编排复用 `run_mutations_full` 的 `run_suite`/`suite_stats`/`failed_set`，未另写判据实现 |
| 2 | 能复现吗 | 能：`run_mutations_ticket_j.py <copytree> <out> <tag>`；跑在 `git archive 805ad78` 的副本树 |
| 3 | 亲眼红过吗 | 每个 KILLED 的 `newly_red` 与"先红"指的是**同一条用例**（M1↔多选、M2↔库外引用、M4/M5↔降级信号）⇒ 两个机制互证 |
| 4 | 期望独立吗 | 判据是 junit 差分（基线绿→变异红），非复算实现 |
| 5 | 限制 | **基线自带 8 条红**（既有 flaky 簇），见第四节 |

```
J-M1 multibad_cond_removed    KILLED   tests=1390=基线 errors=0  restored=true
J-M2 cache_write_ok_removed   KILLED   tests=1390=基线 errors=0  restored=true
J-M3 degraded_cond_removed    SURVIVED tests=1390=基线 errors=0  restored=true   ← 预期
J-M4 log_degraded_removed     KILLED   tests=1390=基线 errors=0  restored=true
J-M5 signal_never_set         KILLED   tests=1390=基线 errors=0  restored=true
```

### 声明 3：回表 E7×2 → PASS + 新增 E16；`grep -c '"GAP-TODO"'` 5 → 3

**本次新跑**：`grep -c '"GAP-TODO"' backend/gate_exit_registry.py` = **3**（= 8 − 票 H 的 3 − 本票的 2）；
`test_gate_exit_registry.py` 与受影响面同跑 = **50 passed / 2 skipped / 0 failed**。
哨兵 `test_committed_md_is_the_generated_artifact` 把"生成物 == 真源"钉成硬红，与自述无关。

### 声明 4：静态门 rc 全 0

**本次新跑**：`ruff check`(4 文件) = 0；`ruff format --check`(4 文件) = 0；
`mypy .` = 0（`Success: no issues found in 73 source files`）。

### 声明 5：交付物已入库、可从提交读回

`git show --stat ad56d29` 列出 `16-dispatch-plan.md`(144) / `report.md`(216) /
`run_mutations_ticket_j.py`(59)；`git show ad56d29:<path>` 能读回内容。
（这一条是**新加的**判据：本会话有一份写在盘上的文件**后来从工作树消失**，
⇒ 「只落盘」不算交付，「在提交里」才算。）

---

## 二、聚合/对比类三必查（本票的"数字"都是对比型）

| # | 必查 | 本票 |
|---|---|---|
| 1 | **键结构一致性** | 基线与变异体都用**同一个** `failed_set(junit)` 产出 `classname::name` 字符串键；差分两侧同源 ⇒ 不存在"两元组 vs 三元组"那类错配。`suite_stats` 读的是 testsuite 属性，两侧同函数 |
| 2 | **取值域核实** | 「`sink == []`」前先把 sink **内容打印进失败消息**（红因原文里能看到整条 entry）⇒ 不是靠"为空"猜的；`degraded` 用 `.get()` 并断言 `is True/False`，缺键时是干净 AssertionError 而非 KeyError |
| 3 | **解析器正确性** | junit 用 `ElementTree` 解析，且分母（1390）与 `--collect-only` 的口径（1408 = 1390 + 18 slow）**对得上** ⇒ 解析器没漏用例 |

**分母失效检查**：每个变异体 `tests == 1390 == 基线`、`errors == 0` ⇒ 非 `denominator-drift`，可判定。

---

## 三、反模式红牌 · 逐条自查

| 红牌 | 本票 |
|---|---|
| "测试通过了"（引用旧输出） | 已用本次新跑顶掉（`19-fresh-affected-face` / `20-fresh-pollution-guard`） |
| "这个数字是合理的" | 每个数字指到命令 + 落盘文件（见上表） |
| "我手动试过了" | 探针与夹具全部脚本化、读数落盘 |
| "golden 用 LLM 生成" / "判断用 LLM judge" | **不适用**：本票判据是确定性 0/1（帧内容、缓存写入次数、日志字段值） |
| "先这样，v2 再验证" | 未使用；未覆盖项显式登记（见下） |

---

## 四、已知限制（照实说）

1. **本票线上效果为零**（票面 J-3）：`llm_registry` 实配只有 `('text','flag')` ⇒ `use_light` 恒假。
   所有判据都是端点级替身模型；E7/E16 两格在表里写的是「代码正确」，**不是**「线上生效」。
2. **`not res.degraded` 当下与 `verdict == "pass"` 冗余**（J-M3 实测 SURVIVED，属预期）：
   它承的是**归因**（日志两条降级原因可分开读）与**防御性**，不承拦截。
   ⇒ 本票**没有**声称这道条件"已在拦截错答"。
3. **全量 lane 基线不稳**：本票基线自带 **8 条既有 flaky 红**（`test_backup_data`×4、
   `test_capture_eval`×1、`test_request_bootstrap::…cleaned_after_later_failure`×3）。
   三条独立读数（票 H 的 `mut-r2` 0 红 / `mut-r2b` 8 红、票 J 的 `mut` 8 红）证明它与票 J 无关，
   且**本票新增的 7 条一条都不在其中**。已列为可派发任务 **T1**。
4. **未在 live 树跑全量**（§0 边界禁止）⇒ 没有 RUN_VALID 级读数；本票门禁读数是"受影响面"口径
   （夹具使用者 5 个文件 + 登记表哨兵 = 50 passed / 2 skipped）。
5. **两条自捉的假绿已留痕但都不属"已修好的功能"**：
   study_aid 空枪（改了夹具）与跨文件缓存污染（改了夹具）。它们说明本票的第一版**证明是错的**，
   修正的是**证明**，不是产品代码之外的语义。
6. **票 I 未开**（范围外）；C 组四条 Owner 决策未决（见 16-dispatch-plan.md）。

---

## 五、本次复验留痕（全部本次新跑）

| 文件 | 内容 |
|---|---|
| `19-fresh-affected-face.stdout.txt` | 受影响面 5 文件同跑：`50 passed, 2 skipped`（rc=0） |
| `20-fresh-pollution-guard.stdout.txt` | 污染复现命令：`8 passed`（rc=0；改前是 FAILED） |
| `10-pollution-repro.stdout.txt` / `11-pollution-fixed.stdout.txt` | 污染**改前/改后**两侧读数 |
| `04-red-pretree.stdout.txt` | 先红侧：`4 failed, 3 passed` + 红因原文 |
| `mut/*/verdict.json` | 五个变异体的分母/新红/还原自证 |
| `mut/baseline/full-baseline.xml` | 基线 `tests=1390 failures=8 errors=0`（8 条 = flaky 簇，与本票无关） |
