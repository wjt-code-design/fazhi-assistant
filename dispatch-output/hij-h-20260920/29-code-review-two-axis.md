# 票 H · 双轴代码审查（Standards × Spec）

**定点**：`2693745`（票 H 的开工基线，已 `git rev-parse` 确认）
**diff**：`git diff 2693745...HEAD`（三点，比 merge-base）—— 8 文件，+923 / −35
**提交**：`3f3bf0f`（实现）、`03ced94`（取证补正）
**审查方式**：两条轴各起一个独立 sub-agent（互不共享上下文），主会话再逐条**复核**其事实基础。
**规格出处**：`docs/handoff-gap-tickets-h-i-j-20260920.md`
**标准出处**：`docs/code-review-standard.md`、`docs/project-quality-guide-20260914.md`、`backend/pyproject.toml`
+ Fowler《重构》第 3 章坏味道基线（skill 内置，工具强制的规则不重复报）

> ⚠️ **序位提醒（Owner 已裁的与之相左，必须点出）**：票面 §9-7 写的是「双轴 fresh-eyes review …
> Owner 已裁『与票 H/I/J 一起做』⇒ **三票齐了才跑**」。本次是使用者当场要求跑的 ⇒ 属于
> **提前跑**，结论应视为**票 H 的临时读数**，J/I 落库后需重跑一次才算数。

---

## Standards

（sub-agent 原文，仅做轻微措辞清理）

**（a）违反文档化标准**

- **B1 冻结物：无触碰（合规）**。本批 `git diff --name-only` 仅 `gate_exit_registry.py` / `main.py` /
  `tests/*` / `scripts/*` / `docs/*`，均非 `state_machine.py` / `prompts.py` / `gate5_judge.py`
  （冻结名单见 `pyproject.toml:17` 与 `code-review-standard.md §2 B1`）。
- **`newline=''` 硬规矩偏差**：三处 `Path.write_text(..., encoding="utf-8")` 未带 `newline=''`：
  `test_contract_exit_gates.py`（contract-failover-endings.json）、
  `probe_contract_reachability.py`（17-reachability-realconfig.json）、
  `run_mutations_ticket_h2.py`（verdict.json）。`Path.write_text` 默认 `newline=None`，
  Windows 下会把 `\n` 翻成 CRLF，与本仓「写文件必须 `newline=''`」相悖。
  判断点：该规矩的口径是否覆盖 `write_text`（非 `open`）。
- **B5 日志白名单：无违规**（本 diff 未新增 `log_account` 字段）。

**（b）基线坏味道（判断题）**

- **Duplicated Code**：`test_contract_exit_gates.py` 的 `_contents` 与 `_errors` 同形——
  均遍历 frames → `json.loads` → 判 `isinstance dict` → 按单键抽取，仅键不同 ⇒ 应合并。
- **Duplicated Code**：`_sse_harness.py` 的 `route="light_buffered"` 与 `route="contract_review"`
  两分支重复 `registry.deduct` + `model_of` 两行桩（`deduct` 那行**逐字相同**）⇒ 抽共享桩。
- **Mysterious Name**：`run_mutations_ticket_h2.py` 用 `rmf` 缩写代 `run_mutations_full`。
- **Shotgun Surgery**：票 H 改动散落 6 类文件；但 registry 是生成物、scripts 是独立取证工具，
  属本仓既定结构，未必真味。

**无发现类**：Feature Envy / Data Clumps / Primitive Obsession / Repeated Switches / Divergent Change /
Speculative Generality / Message Chains / Middle Man / Refused Bequest 均无。

### 主会话复核（Standards）

- `newline=''` 三条**事实成立**（已 `grep -n write_text(` 逐条核对到原文）⇒ 三条全修。
- 两条 Duplicated Code**事实成立** ⇒ 两条全修（见下"据审查做的修改"）。
- `rmf` 缩写：**不采纳**。它在本仓是既定写法（`run_mutations_ticket_h2.py` 与 s5 执行器同族），
  且该名字只出现在 3 行内，改名的收益小于与既有执行器分叉的成本。
- Shotgun Surgery：**不采纳**（sub-agent 自己也标了"未必真味"）；registry 是**生成物**、
  evidence 脚本是独立工具，不是同一逻辑被散点修改。
- 一处**口径补充**：那两个 dispatch-output 脚本在 `cd backend && ruff check ../dispatch-output/…`
  下会报 3 条 E402 与格式差异；但从**仓库根**（= pre-commit 的实际视角）跑是 `All checks passed`。
  本仓没有根级 ruff 配置，`backend/pyproject.toml` 的 `select`（含 E 全组）只对 backend 下的路径生效
  ⇒ **以 pre-commit 的读数为准**，不为非权威调用面加 `# noqa`（那才是噪音）。

---

## Spec

（sub-agent 原文，仅做轻微措辞清理）

**（a）缺失/部分实现**

- 本 diff 仅含票 H 文件；票 I、票 J 完全未出现（交接文件三票同述）。
- §0.5.1 要求开工自查落盘 `dispatch-output/hij-h-20260920/00-pre-flight.json`，"缺一不许动源码"
  —— diff 无此文件。
- 回表/测试引用的取证 json（`17-reachability-realconfig.json`、`00-smoke.stdout.txt`、
  `contract-failover-endings.json`）均未入库。

**（b）scope creep**

- H-1 原文形状「`if cache_key and not bad:`」，实现改成 `if cache_key and not bad and not degraded:`
  —— `not degraded` 超出 H-1 字面指令（H-2 只要求加注记帧，未要求扩写缓存闸）。

**（c）看似实现但可能不对**

- H-2 要求先量 failover、"二选一：接可命中门 or 判 NA 回表"，并警告「别接恒不命中的空门
  （`[PL#14]`）」。实现自创「接线正确、今天零命中」第三态；E15 自承真实配置 `flag_degraded` 恒假
  ⇒ 门今天不触发，正踩该警告。
- 代码 `if degraded:` 无 `if answer:` 守卫，但 E15 登记 traffic 为「flag_degraded 且报告正文非空」
  —— 实作与登记不符（空答也会发注记）。
- （另注：§9-1 的 `grep -c GAP-TODO` 公式会被注释行 6/14 干扰，实测=7≠5。）

### 主会话复核（Spec）

逐条复核（trust but verify），**两条被证伪、一条成立**：

| # | 结论 | 复核证据 |
|---|---|---|
| (a)-I/J 缺失 | **不成立** | 票面 §0.5.3 明令「**一票一会话**」「顺序 H→J→I，每票 = 一个独立执行会话 = 一次独立提交」⇒ 本批**只应**含 H |
| (a)-pre-flight 未入库 | **部分成立** | 文件**在盘**（`ls -la` = 2035 B，19:17 写入）；需求原文是「读数**落盘**」，未要求入库。**但**"证据只在工作树、不在提交里"这个可复现性折损是真的 ⇒ 已在 §回报 里显式登记 |
| (a)-取证 json 未入库 | **同上口径** | 同上 |
| (b)-`not degraded` 超范围 | **成立（判断题）** | 见下"留给 Owner 的判断" |
| (c)-无 `if answer:` 守卫 | **证伪** | 实读缩进：`1889: answer = "".join(chunks)` → `1890: [16 空格] if answer:` → `1917: [20 空格] if degraded:`。注记帧**确实**被空答守卫；登记表的「报告正文非空」与实作一致 |
| (c)-踩 `[PL#14]` 假接线 | **不成立** | 见下"留给 Owner 的判断" |
| (c)-`grep -c` 公式 | **成立但已知** | 带引号口径 `grep -c '"GAP-TODO"'` = 5（= 8 − 3，与 §9-1 一致）；不带引号才是 7（docstring 两处）。本票报告末节已单列这条口径订正 |

---

## 据审查做的修改（本会话新增，均已复验）

| # | 改什么 | 依据 | 复验 |
|---|---|---|---|
| 1 | `test_contract_exit_gates.py`：`write_text(..., newline="")` | Standards `newline=''` 硬规矩 | ruff/format rc=0 |
| 2 | 同文件：`_contents` / `_errors` 合并为 `_payloads` + 两个一行派生 | Standards Duplicated Code | 34 passed / 2 skipped / 0 failed |
| 3 | `_sse_harness.py`：抽出 `_stub_quota_accounting(monkeypatch, model_name)`，两条 route 共用 | Standards Duplicated Code | 同上（含旗舰流式与票 C 的 14 条） |
| 4 | `probe_contract_reachability.py` / `run_mutations_ticket_h2.py`：`write_text(..., newline="")` | 同上 | 根视角 ruff rc=0 |

门禁：`ruff check` rc=0 / `ruff format --check` rc=0 / `mypy .` rc=0（73 files）/ pre-commit（暂存集）rc=0。

## 留给 Owner 的两个判断（我不替 Owner 裁）

**① H-2 的 `not degraded` 是否属越界（Spec (b)）**——支持保留的证据：
票面「归属一览」表把 **`E5 配额降级注记 / E5 写缓存闸 / E6 写缓存闸` 三格一并归给票 H**，
并写明「都是合同分支那一个 `if` 块里的事，**一次改完**」⇒ 写闸与降级注记在同一射程内。
且若不改写闸，降级报告会被缓存、复播时**丢掉那条免责注**——正是 H-1 自己修的缺陷形状。
⇒ 我判它是**票面授权内的判断题**，但票面 H-1 的示例形状只写了 `and not bad`，
**这一处扩写请 Owner 明示"算/不算越界"**；若要严格照字面，回退方式是把 `not degraded` 摘掉
（代价：降级报告会被缓存，E15 的注记在复播时消失）。

**② E15 是否算 `[PL#14]`「恒不命中的空门」**——反对的证据（我的判断）：
- 票面那句警告的**落点是版本绊线**（「合同事实来自上传文本而非用户自述，`_fast_path_fact_texts`
  那套取法在此不成立」）⇒ 指的是**结构性不适用**的假门；
- E15 的门是**条件门**，条件是 `flag_degraded`，而它是真实运行时状态；
- 决定性对照：流式出口 **E13 用的是同一个 `flag_degraded`**，今天同样为假、同样零命中，
  而登记表给 E13 的是 `PASS`。若 E15 算空门，E13 必须一起改判 —— 那超出票 H 射程。
⇒ 我判「条件门、今天不命中」在表里是**如实登记**，不是假接线；但**这判断也需要 Owner 确认**
（是否要把"今天不命中"的条件门统一改判成某种状态词，那是登记表口径的事，不该由执行会话单方面改）。
