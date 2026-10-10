# A 轴 · 规范与代码质量评审（2026-10-10 深夜）

对象：`codex/nondeploy-closeout-20261010` 的五笔（`0b54396..HEAD`，含 `9e3cfc5`），生产面 diff ≈ 540 行 + 11 只测试。
**⚠️ 头一条必须写在最前面：这份是我（这些改动的作者）自己做的。**
原计划两路独立 agent（A 规范 / B 规格）到 22:15 仍**零产物**（`.output` 停在 20:30/20:31、0 字节，运行根无它们的任何文件），形状与今日证死的那只 D agent 相同 ⇒ 我按"不再等"处置。
⇒ **按 `docs/code-review-standard.md` 的"独立复核必须非实现者"，本文件不满足独立性**：它能当自查与材料，**不能**充当关卡所要求的独立腿。要满足纪律，需另派一只非本会话的评审（票面可直接引用本文件的判据清单，让它逐条复算或推翻）。

## §0 汇总

| 档 | 条数 | 是什么 |
|---|---|---|
| 通过（有读数支撑） | 7 | 解冻纪律、共享状态清理、异常顺序、配置三轴、日志白名单、测试防假绿、文档/代码一致性 |
| **存疑（写给 Owner 裁）** | 1 | 探针失败 ⇒ **回落**（宽）vs 保持空（窄）：与 D-4"收窄"方向相反，但**有测试钉住**是有意为之 |
| 建议（小改） | 2 | `count()` 在缓存查询之前（每次落空仍打一次库）；`ResumeRunConflict` 注释列 4 类成因、实码 7 值（注释是子集，非错） |
| 缺陷 | 0 | — |

## §1 冻结与解冻纪律 —— 通过

`agent/state_machine.py` 本轮解冻：`backend/pyproject.toml` 的 ruff `exclude` 由 3 项减为 2 项，并在文件里补了解冻记录（判据/改动量/实测代价）。
格式化那笔的**AST 等价**我用独立脚本复算过（`evidence/ast_equal_statemachine.py`：`ast_dump` sha 两侧相同、体量 5694→5672 B）。
冻结文件（`prompts.py`、`gate5_judge.py`）本轮 **0 改动**（`git diff --name-only` 无命中）。

## §2 共享可变状态 —— 通过（1 条小建议）

新增两只进程内缓存：`_CATEGORY_ADVERTISED: dict[str, bool]`（键=集合名）、`_CATEGORY_MISS_SEEN: set[str]`（键=`stage|category|outcome`）。
- **清理**：`invalidate()` 里两只都清（`retrieval.py:691/693`），且都在 `with _bm25_lock` 之内 ⇒ 知识增删后不会带旧记忆。**这条我一度怀疑漏清，读全文后自己驳回**（只 grep 了 `-A6` 窗口）。
- **有界性**：集合名的基数是"本进程见过的集合数"；抑制键基数是 stage×category×outcome 的组合 ⇒ 实际有界，不是无界增长。
- **并发**：8 处读写点（`818/826/842/844`）在锁外；CPython 下单次 dict/set 操作原子，最坏是"重复 warn/重算"，不会丢更新。
- **建议（不阻塞）**：`_corpus_advertises_category` 里 `cached` 查询排在 `col.count()` **之后** ⇒ 命中缓存时仍打一次库。把缓存查询提到 `count()` 之前即可。

## §3 异常与降级面 —— 通过（1 条待裁）

- `agent/service.py:635` 的 `except BudgetExceeded` 在宽 `except Exception` **之前**、`:214` 的窄捕获也正确 ⇒ 不是死代码（这类"顺序写反＝恒不触发"是本仓登记过的形状）。
- `retrieval.py:824` 的 `except Exception: # noqa: BLE001` 只包住探针，`return False` ⇒ 走"回落一次"的旧形状；注释写明"探测能力缺失不该变成用户侧硬失败"。**它没有静默改走更贵的路**：回落只多一次无过滤检索。
- `retrieval.py:432` 的 `except Exception` 是**在册已裁**（保留 `exc_info`、不重开统一收口）的那处，本轮未动其口径。
- **待裁（D-24，新）**：探针失败 ⇒ `False` ⇒ **回落**（无过滤）。设计文档说"维度存在而值不存在 ⇒ 保持空，不许跨类 borrow"，但**探针失败时无法区分这两种情形**，代码选了"宽"的一侧。它被 `test_probe_unavailable_keeps_the_old_shape` 钉住（负控断言回落腿跑过）⇒ 是有意为之，但与 Owner 裁的 D-4"**收窄**"方向相反。两个选项：维持（可用性优先）／改成"探针失败⇒保持空"（安全优先）。**我不替 Owner 选。**

## §4 配置与默认值 —— 通过

| 项 | 现量 | 依据 |
|---|---|---|
| torch 三轴 | `requirements.txt:46` = `torch==2.13.0`；`Dockerfile` 与 `ci.yml` = `2.13.0+cpu` | **不是不一致**：`+cpu` 只能从镜像源解析（PEP 440 下 `==2.13.0` 匹配 `2.13.0+cpu`），理由写在 `requirements.txt:34-45` |
| SQLAlchemy 下限 | `sqlalchemy>=2.1,<3.0`（`:25`），并写明"红绿由 SQLAlchemy 版本决定，不是 mypy 版本、也不是本轮引入" | 我复算过：候选闭包 2.1.4 下 `mypy .` Success |
| CI 红线 | 无 `continue-on-error`、无降 `--cov-fail-under`（唯一命中的是**注释**里那句"不用 continue-on-error 凑绿"） | `git diff … -- ci.yml` |
| 新增 CI 步 | dev 轴 `pip-audit` + 前端三条腿；勘误注记（`a934fa7`）已把"两轴同集"写清 | 同一处 |

## §5 日志与事件白名单 —— 通过

`observability._ACCOUNT_FIELDS` 新增 **5** 项（`agent_resume_reason`、`category_filter_value/stage/outcome`、`model_failure_channel/reason`），每项都带"未登记会被 JSON formatter 静默丢弃"的理由与"不含用户文本"的声明。
实现侧同步：`main.py` 的 409 捕获真的把 `reason_code` 写进结构化日志；`controller.ResumeRunConflict` 现带 `reason_code`，**全仓无裸 `raise ResumeRunConflict()`**（0 命中）。
小注（非错）：docstring 列了 4 类成因，实际码有 **7** 个值（`cas_conflict`/`state_unreadable`/`answer_invalid`/`step_budget`/`state_stale`/`pending_anchor_mismatch`/`issue_missing`）⇒ 注释是子集。

## §6 测试质量 —— 通过

| 文件 | asserts | `is not None` | mock | 说明 |
|---|---|---|---|---|
| test_llm_reject_channel | 42 | 0 | 21（SDK 桩） | 断言是状态码网格与账面对照（`mark_depleted` 100→0 vs `mark_rejected` 100→100） |
| test_agent_budget_terminal_edges | 15 | 0 | 0 | 钉 `FREE_STEP_EDGES` 集合本身 |
| test_retrieval_category_narrow_fallback | 22 | 5 | 3 | 含"判定应当真的去问集合，而不是恒真"与"同一集合不该每次重探" |
| test_backup_restore_drill | 22 | 0 | 12 | 双向 WAL 断言、精确目标集合、`*.wal/*.shm` 不存在 |
| test_loader_trust_gate | 7 | 1 | 0 | AST 腿 + `_refusing_default` 负向自证 |
| test_import_laws_guard | 11 | 1 | 4（子进程） | 三条腿走真 CLI |

**红过**：四台变异仪各自点名到腿（category M1→2 failed / M2→4 failed；loader M2→2 failed / M4→1 failed；drill M1/M2 打红特定腿；B-45 M1 删守卫→红在分歧腿）。
**限制**：reject_channel / drill 的桩是"内存 fake" ⇒ 只覆盖"映射与账目"，不覆盖真实 SDK/磁盘异常形状（这类缺口已由 D 单的真实浏览器验收与 E.3 的真实 sqlite/chroma 部分补上）。

## §7 文档与代码一致性 —— 通过（含一处更正）

- `retrieval._norm_source` 的 docstring 改成**反向教材**（说明它为何弱一档、被哪条测试当"照抄错对象"的反面样本）——这正是本仓最需要的那类注释。
- `domain_rules.norm_law_name` 的"射程"段明确列出**没并进来**的 6 处（写侧 `import_docs`、`capture_eval`、`gen_qwen_cases`、弱一档的 `_norm_source`/`dept_guard`）⇒ 不会让人把"收口"读成"全仓只剩一份"。
- 更正一条**我在本轮早先量错、现已改正**的坐标：`RetrieveLawsInput` 不在 `backend/schemas.py`，而在 **`backend/tools/contracts.py:84`**，`category` 字段在 `:89`（`str | None = Field(default=None, max_length=100)`）。D-8 的前提（尚未摘除）成立。

## §8 复算（整块可重跑，只读）

```bash
C=/c/Users/33393/Desktop/ai-legal-helper/.worktrees/nondeploy-closeout-20261010
git -C "$C" diff --numstat 0b54396..HEAD | sort -k1,1nr | head -8
git -C "$C" diff --name-only 0b54396..HEAD | grep -cE "prompts\.py|gate5_judge"     # 0=冻结文件没被碰
sed -n '685,695p' "$C/backend/retrieval.py"                                        # 两只缓存都在 invalidate 里、都在锁内
sed -n '630,645p' "$C/backend/agent/service.py"                                    # except BudgetExceeded 在 Exception 之前
grep -nE "torch|sqlalchemy" "$C/backend/requirements.txt" | tail -4
git -C "$C" grep -c "raise ResumeRunConflict()" -- backend/                        # 0=每个抛点都带码
grep -n "category" "$C/backend/tools/contracts.py" | head -3                       # D-8 前提：字段仍在
```
