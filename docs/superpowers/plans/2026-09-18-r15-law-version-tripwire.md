# R15 法律版本适用绊线 · 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 verifier 能确定性地拦住"按 `law_as_of` 版本的法回答 2021-01-01 分水岭前事实"的时效类错答，并给评测通道补上 `law_as_of` 注入出口。

**Architecture:** 判定真源落在 `agent/limitation_calc.py`（时效判定的既有单一真源），以**纯新增函数**形式提供 `law_version_crosses_watershed`；`agent/verifier.py` 只消费它并在 claim 循环末尾加一道独立门；`agent/service.py` 把 `AgentRun.law_as_of` 透传给 verifier；开关 `settings.law_version_tripwire_check` 默认关，关闭时行为逐字不变。评测侧（`scripts/gate2_runner.py`）把首轮请求体抽成 `_round1_payload` helper，按案例声明的 `as_of_date` 透传 `law_as_of`，镜像既有 `case_domain` 链路。

**Tech Stack:** Python 3.11 / pydantic v2 / pytest / ruff + mypy / SQLAlchemy（只读消费 `AgentRun`）。无新依赖。

## Global Constraints

以下为**逐字约束**，每个任务的隐含要求都包含本节：

- **不得改动 `law_as_of` 的缺省行为**：`backend/agent/repository.py:72` 的 `law_as_of=law_as_of or date.today()` 一字不动，`backend/models.py:144` 的 `Column(Date, nullable=False, default=date.today)` 不动。依据 `docs/handoff-external-harness-20260918.md` §2.3：「不要改成必填、不要动默认行为」。
- **新开关默认关**：`law_version_tripwire_check: bool = False`。**本批不得在任何地方把它打开**——依据交接书 §2.2：「开启 = 评测批预登记事项，不是代码改动」。
- **仍冻结的文件不得触碰**：`agent/state_machine.py`、`prompts.py`、`scripts/gate5_judge.py`（`backend/pyproject.toml` ruff exclude 仍含这三项；触碰即阻断候选冻结，须 Owner 决策卡）。依据交接书 §2.1。
- **不碰 T0 冻结评测集**：`evals/frozen-cases-v2.json`（20 条 FROZEN）不改；本批用独立新文件。
- **禁止 `git stash` / `git reset --hard` / `git clean`**（会毁并行会话证据）。依据交接书 §5。
- **多会话共用工作树**：动手前查 `git log --oneline -1` + `git status --short -ununo`；只 stage 本会话文件；看到别的会话在改同一文件 → 停手确认。
- **关键编辑后必须 `git diff` 复核落盘**（Edit 报成功 ≠ 落盘，交接书 §6 有实例）。
- **全量测试必须 `--basetemp=全新目录`**，输出重定向到文件。
- **含反引号/`$` 的 Python 一律写 .py 文件执行**，不用 heredoc。
- **提交前手动跑 pre-commit**：`.git/hooks/pre-commit` 不存在，`git commit` 不会自动跑钩子。必须 `backend/venv/Scripts/pre-commit.exe run --files <改动文件>` 并报退出码。
- **声称完成前过证据五连问**（skill `show-your-work-new`）。

---

## 车道与真源归属（先读，决定为什么这样切文件）

| 文件 | 最近归属 | 本计划动作 | 冲突风险 |
|---|---|---|---|
| `backend/agent/limitation_calc.py` | R11（外部 harness 批次，已并入本会话接手） | **纯新增**函数 + `__all__` 追加一项 | 低（不改既有行） |
| `backend/settings.py` | 无人近期触碰 | 新增 1 个 flag | 低 |
| `backend/agent/verifier.py` | 本会话 `02e3851`（20:22） | 加参数 + 独立判定块 + **PASS 结果携带基准日（F1：喂 `render_verified` 二次验证）** + 提模块级 import | 低（同文件同作者；`main.py` 无需改） |
| `backend/agent/service.py` | 14:56，无近期提交 | `verify(...)` 加 1 个 kwarg | 低 |
| `backend/scripts/gate2_runner.py` | 外部 harness 批次 §4.1 | 抽 helper + 换调用点 + 1 个 argparse | 中（改动既有行） |
| `backend/tests/test_agent_verifier.py` | **并行会话 20:13** | **不动** | 规避 |
| `backend/tests/test_gate2_runner.py` | **并行会话 20:13** | **不动**（作为 helper 重构的回归保护网跑它） | 规避 |
| `backend/tests/test_limitation_calc.py` | R11 批次 | **不动**（新测试另建文件） | 规避 |
| `backend/tests/conftest.py`、`rag_chain.py`、`knowledge_service.py`、`tests/test_citation.py`、`tests/test_chroma_isolation.py` | **并行会话 T-E（chroma 隔离）在途**，21:4x 实测未提交 | **一律不碰、不 stage、不 revert**；基线数字带 `DIRTY_` 定语（F4） | 🔴 高（对方在改收集期行为） |
| `backend/agent/repository.py` | 并行会话 19:25 解冻 | **仅 docstring** 补 1 行 | 中 |

**为什么判定写在 limitation_calc 而不是 verifier**：时效判定的单一真源已在该模块（`CIVIL_CODE_EFFECTIVE`、`extract_dates`、`_CIVIL_KEYWORDS` 全在那里）。在 verifier 内联会造出第二处"最早事实日 vs 分水岭"计算，是本仓库审查规范点名的重复。

**已撤回的一条**：`controlled_limitation_tokens` 用最早事实日比硬编码 2021、不看 `law_as_of`，**不是 bug**——`limitation_calc.py:22-26` 边界 1 明文「白名单函数对分水岭前事实一律返回空集……宁可放行原校验（fail-open）也不放错 token」。本批不修它，也不上报。

---

## 审核记录（vet-plan-new 五问，2026-09-18 21:4x 实测于 `02e3851`）

计划初稿经对抗审核后**改掉 7 处**，其中两处是"上线即坏"级别：

| # | 发现 | 证据（本机实测） | 处置 |
|---|---|---|---|
| F1 🔴 | **`verify()` 有两个调用点**：`verifier.py:226` 的 `render_verified()` 会**二次验证**，且不传 `law_as_of`。生产链路 `main.py:878 finalize_verified_agent_answer → render_verified`。开关一开：首轮 PASS → 二次验证命中 `LAW_TRIPWIRE_NOT_WIRED` → `render_verified` 返回 None → 用户拿到 `VERIFIER_NOT_PASS`，**绊线自己的原因码永远看不见，且评测批 100% 失败** | `grep .verify(` → 仅 `service.py:472` 与 `verifier.py:226`；`render_verified` 调用点 `main.py:878` + `tests/test_agent_chat_integration.py:348` | 按 `verifier.py:46-49` 既有先例（`covered_issues_exempt` 随结果传递，"否则二次验证用默认空集会再次拦下部分交付"）**同型修复**：`VerificationResult.law_as_of` 携带 → 见 Task 2 Step 6b。不改 `render_verified`/`Finalizer` 签名（会砸到并行会话 20:13 的 `test_agent_chat_integration.py`） |
| F2 🔴 | **Task 4 的对照样本 JSON 字段类型全错**：真实 `frozen-cases-v2.json` 里 `round1_facts`/`round2_facts` 是 **str**（我写成数组）、`required_laws` 是 **`[[法名, 条号int]]`**（我写成 `["《民法典》第一百八十八条"]`）、且新案例必须带 `fact_reveal`。`gate5_judge.py:93` 逐字 `int(x[1])` → 字符串条目直接 **ValueError 崩判分** | `validate_cases.py:37-40,75`、`gate5_judge.py:93,142`、E01 实例 dump | 已重写 Task 4 Step 7（含 `fact_reveal`/`scope_trigger`/`forbidden_articles`）+ Step 8 加**结构契约测试**（把形状钉死，不依赖人眼） |
| F3 | `settings.settings.model_fields[...]` 在实例上访问：pydantic 2.13.4 实测抛 `PydanticDeprecatedSince211`（V3 移除） | `python -W error::DeprecationWarning -c "import settings;settings.settings.model_fields['phantom_tool_check']"` → 报 DeprecationWarning | 改类访问 `settings_module.Settings.model_fields[...]`（`settings.py:12 class Settings(BaseSettings)`、`:198 settings = Settings()`） |
| F4 | Task 0「工作树干净」的前置**已不成立**：并行会话正在做 **T-E chroma 隔离**，在途改 `tests/conftest.py`(+94 行，含 `_prepare_test_chroma()` 收集期副作用)、`rag_chain.py`、`knowledge_service.py`、`test_citation.py`，新增未跟踪 `test_chroma_isolation.py`。`verifier.py`/`gate2_runner.py` mtime 21:23 但内容与 HEAD 一致（被同步回提交态，非丢失） | `git status --short -uno` + `git diff --stat` + `git diff conftest.py` | 基线口径改为「**脏树上的 `DIRTY_BASELINE`**」并抄录对方文件清单；Task 6 差值规则加"对方若中途提交则重取基线"的显式分支。conftest 在收集期建临时 chroma ⇒ 可能新增 skip 数，差值只认**我的 lane 文件** |
| F5 | **代理目标**：「passed +N」不是本批目标。绊线默认关 ⇒ 全绿只证明"没弄坏别的"，**不证明保护存在** | 逻辑事实 | DoD 明确为三条（见 Task 6 Step 6）：① probe「没有这道门就放行」；② 开关开的 verifier **与 render_verified** 两侧行为测试；③ 对照臂数字（本批**不产出**）。并如实写明：`先立尺子再投入` 这条纪律本批**未满足**（Owner 选 E1 证据级别），不假装满足 |
| F6 | 新题集 `watershed-cases-r15.json` 不进 `candidate-hashes.json`，也没有 `validate_cases.py` 覆盖（该脚本硬编码 V2 路径 + 断言 20 例） | `validate_cases.py:24,56` | 落盘时记 **sha256** 进收口报告，题集内容此后改动须换 `schema_version`（基线冻结纪律的最小履行） |
| F7 | Task 4 Step 9 原本要跑 `mypy scripts/gate2_runner.py`：实测 **RC=1 + 4 个既有错误**（`scripts/` 在 mypy exclude 内，该文件从未被类型检查过）⇒ 照原计划会把对方文件的既有债当成本批的红灯，诱发"顺手修"越界 | 本机 `mypy scripts/gate2_runner.py` 输出（`_r15_mypy_probe.txt`）+ `pyproject.toml` mypy 注释自述"已知…4 个既有错误" | 删掉该命令，改为"注解手写对 + 由 5 条契约测试代偿"，并把这条限制写进收口报告（Task 4 Step 9 已改） |

**逐问结论（简）**：
1. **边界**：判定留在 `limitation_calc`（时效真源），verifier 只消费——`writer.py:24` 已模块级 import 同一模块，无循环依赖（`limitation_calc` 只 import `re/unicodedata/collections/datetime`）。
2. **更优解（F1 的三条路）**：改 `render_verified` 签名 → 砸对方测试文件，否；二次验证跳过绊线 → 破坏"digest 必须逐字复现"的完整性设计，否；**随结果携带** → 与 `covered_issues_exempt` 同型、零签名破坏，取。
3. **教训对照**：命中 `[PL#14] 假接线`（F1/F2：文档说"接线完成"而二次验证与判分端都不认）、`[fz] judge 基线污染`（F2 崩判分）、`[PL#5] 配置默认值`（F1 正是"开关一开才发现没接"）。`[fz] 降级静默改路径` 由 `test_new_reason_codes_are_not_technical_fallbacks` 拦住。
4. **事实**：`verifier.py:15/244/259-265/369-371/400-405/455-462/465-473`、`service.py:471-476/486-523`、`settings.py:80`、`limitation_calc.py:205/208`、`models.py:144`、`routing_metrics.py:13-21,63`、`schemas.py:70`、`gate2_runner.py:55-65,68,293-298,460-465`、`pyproject exclude=state_machine/prompts/gate5_judge`、`venv/Scripts/pre-commit.exe` 存在——**全部本会话逐行复核过**。唯一不可核的是基线数字（F4 ⇒ Task 0 现场取）。
5. **DoD**：见 F5。

---

## Task 0: 在当前 HEAD 重取全量基线（解掉 1233 与 1236 的口径冲突）

**Files:** 无代码改动；产出留痕文件 `_r15tripwire_baseline.txt`（仓库根，未跟踪）。

**Interfaces:**
- Produces: 两个可引用的基线数字——`DIRTY_BASELINE_PASSED`（全量，脏树）与 `LANE_BASELINE`（本批 lane 定向），供 Task 6 的"零回归"陈述使用。

- [ ] **Step 1: 确认 HEAD 与"谁在动工作树"（F4：干净不是前置条件，**归属清楚**才是）**

Run: `cd "C:/Users/33393/Desktop/ai-legal-helper" && git log --oneline -1 && git status --short --untracked-files=no && git diff --stat`
Expected: HEAD 为 `02e3851` 或其后代。

⚠️ **2026-09-18 21:4x 实测：工作树不干净，且不是本会话造成的**——并行会话在做 T-E「chroma 隔离」，在途修改
`backend/tests/conftest.py`(+94 行：收集期 `_prepare_test_chroma()` 建临时库 + 新 `real_kb` fixture)、
`backend/rag_chain.py`、`backend/knowledge_service.py`、`backend/tests/test_citation.py`、
`docs/dispatch-tasks-20260908.md`，另新增未跟踪 `backend/tests/test_chroma_isolation.py`。
处置口径（写死，不靠临场判断）：
1. 这些文件**一个都不改、不 stage、不 revert**；把 `git status --short -uno` 的完整输出抄进本批记录。
2. 本批基线数字因此**不对应任何提交**，命名为 `DIRTY_BASELINE`（不是"干净基线"），报告里必须带这个定语。
3. `conftest.py` 的收集期改动会改变全量分母（真实语料用例可能 skip）⇒ **只有"同树同口径的差值"有意义**，
   绝对值不得与交接书里的 1233/1236 横向比较。
4. 若 Step 3 与 Task 6 之间对方提交了新东西（`git log -1` 变了）→ 差值规则失效，**重取一次 `DIRTY_BASELINE`**
   并在报告里写清新旧两个数。
5. 本会话 lane 文件（`verifier.py`/`gate2_runner.py` mtime 21:23 而内容与 HEAD 一致）若出现**非本会话 hunk**
   → 立即停手确认（交接书 §5）。

- [ ] **Step 2: 跑门禁三绿（脏树上跑，非 0 时先归因再决定开工）**

Run:
```bash
cd "C:/Users/33393/Desktop/ai-legal-helper/backend" && ./venv/Scripts/python.exe -m ruff format --check . > ../_r15tripwire_rufffmt.txt 2>&1; echo "FMT_RC=$?"; ./venv/Scripts/python.exe -m ruff check . > ../_r15tripwire_ruff.txt 2>&1; echo "RUFF_RC=$?"; ./venv/Scripts/python.exe -m mypy . > ../_r15tripwire_mypy.txt 2>&1; echo "MYPY_RC=$?"
```
Expected: `FMT_RC=0` `RUFF_RC=0` `MYPY_RC=0`。
**非 0 时的分支（不是"停手"一条路）**：读日志首行定位文件——
- 失实文件 ∈ 对方在途清单（`conftest.py`/`rag_chain.py`/…）→ 记录"门禁失败归属 X 会话"，**不改对方文件**，
  本批仍可在自己的 lane 上开工，但收口报告必须写明"三绿是**局部**结论"；
- 失实文件 ∈ 本批 lane → 先修基线再继续（不带着红开工）。

- [ ] **Step 3: 跑全量（不含 slow）+ 跑本批 lane 定向，两份数字都要**

Run:
```bash
cd "C:/Users/33393/Desktop/ai-legal-helper/backend" && ./venv/Scripts/python.exe -m pytest -q -m "not slow" --basetemp="../_pt_r15tripwire_base" > "../_r15tripwire_baseline.txt" 2>&1; echo "PYTEST_RC=$?"
```
Expected: `PYTEST_RC=0`，末行形如 `NNNN passed, NNN deselected in NNNs`。把该 `NNNN` 记为 `DIRTY_BASELINE_PASSED`。
（参考量级：交接书 §0 记 1233（树在 `777e332`）；本会话此前在 `02e3851` 附近实测 1236。二者都不是当前树，
**以本步实测为准**，旧数字一律作废。deselected 数也会因对方 conftest 改动而变，别假设是 18。）

再跑一份**本批 lane 定向**（对方在途文件不参与，数字最稳，是 Task 6 差值的主口径）：
```bash
cd "C:/Users/33393/Desktop/ai-legal-helper/backend" && ./venv/Scripts/python.exe -m pytest tests/test_agent_verifier.py tests/test_phantom_check.py tests/test_limitation_calc.py tests/test_agent_chat_integration.py tests/test_agent_gate.py tests/test_gate2_runner.py tests/test_request_bootstrap.py -q -m "not slow" --basetemp="../_pt_r15tripwire_lane" > "../_r15tripwire_lane_baseline.txt" 2>&1; echo "RC=$?"
```
Expected: `RC=0`；记为 `LANE_BASELINE`。

**红了的口径**：全量若红且红点落在对方在途文件覆盖的范围（`test_citation.py`/chroma 相关）→ 把
`DIRTY_BASELINE` 降级为 `PARTIAL`，收口时**只声称 lane 零回归**，不写"全量全绿"。

- [x] **Step 4: 无代码可提交，跳过 commit**

**Task 0 实测结果（2026-09-18 22:4x）**：
- HEAD = `d4b8d79`（比计划撰写时的 `02e3851` 多两枚对方提交：`27d5363` test_gate2_runner +36、
  `d4b8d79` test_gate2_runner 假服务抽基类 −148/+135）。`git log 02e3851..HEAD -- <本批 lane 6 文件>` **空**
  ⇒ 我的 lane 无人触碰，可直接开工。
- 门禁三绿：`FMT_RC=0` `RUFF_RC=0` `MYPY_RC=0`（日志 `_r15tripwire_rufffmt.txt`/`_ruff.txt`/`_mypy.txt`）。
- `LANE_BASELINE = 227 passed / RC=0 / 44.96s`（`_r15tripwire_lane_baseline.txt`）← **本批主口径**。
- 全量：`1240 passed / 4 failed / 18 deselected / 87.38s`（`_r15tripwire_baseline.txt`）⇒ **判为 `PARTIAL`**：
  4 红全在 `tests/test_query_understand.py`（`test_hybrid_retrieve_*` ×3 + `test_retrieve_exam_default_cap`），
  失败签名是 `AssertionError: … 实际无：set()` + chroma 日志 "elements in index **0**"
  ⇒ 正是对方在途 conftest 把 `CHROMA_DIR` 指到**空临时库**、而该文件尚未迁 `real_kb`
  （实测 `grep -c real_kb tests/test_query_understand.py` = **0**，而 `test_citation`/`test_domain_rules`/
  `test_retrieval_rerank`/`test_statute_supplement` 四个同类文件都在脏改动清单里）。
  **归属：并行会话 T-E，与本批无关，不改对方文件、不改 conftest。**
  ⇒ `DIRTY_BASELINE_PASSED = 1240`，Task 6 全量口径按"同 4 红 + 我的 +21"核对；
  收口**只声称 lane 零回归**，不写"全量全绿"（Task 0 Step 3 的 PARTIAL 分支已触发）。

---

## Task 1: 判定真源 `law_version_crosses_watershed`

**Files:**
- Modify: `backend/agent/limitation_calc.py`（在 `controlled_limitation_tokens` 之后、`__all__` 之前插入新函数；`__all__` 追加一项）
- Test: `backend/tests/test_r15_version_tripwire.py`（新建）

**Interfaces:**
- Consumes: 模块内既有 `CIVIL_CODE_EFFECTIVE: date`、`extract_dates(texts: Iterable[str]) -> list[date]`、`_CIVIL_KEYWORDS`、`_LABOR_KEYWORDS`（均为本模块私有，同模块内使用合法）。
- Produces: `law_version_crosses_watershed(claim_text: str, fact_texts: Iterable[str], law_as_of: date | None) -> bool`。Task 2 消费。

- [ ] **Step 1: 建测试文件，写 8 条纯函数用例（此时函数不存在，应当红）**

Create `backend/tests/test_r15_version_tripwire.py`：

```python
"""R15 法律版本适用绊线（2026-09-18/19 批次）。

期望值的独立来源（不是本实现）：
- 分水岭 2021-01-01、普通诉讼时效 3 年、劳动仲裁 1 年 —— `limitation_calc.py:7-15`
  代码级常量段自述的法条依据（《民法典》188/1260、《民法通则》135、《劳动争议调解仲裁法》27），
  与 `backend/domain_rules.py:162-170` 的「民事·诉讼时效 → (民法典, 第一百八十八条)」登记一致
  （该表**接线状态=暂存未接线**，见 `:104-111`；本测试只取其**法条知识**作独立来源，不依赖其接线）；
- 「跨 2021 分水岭拿 today 当基准日必然算错时效」——
  `docs/external-harness-plan-gap-analysis-20260918.md:118`（§五 R15 行：「基准日默认设为今天 →
  跨法修订场景必然错」）与 `:136-137`（T1 = 方案称"最高频最致命"那类 + §六 判断 2）。
"""

from __future__ import annotations

from datetime import date

from agent.limitation_calc import law_version_crosses_watershed

_TIMING_CLAIM = "本案请求权适用《民法典》第一百八十八条，诉讼时效期间为三年。"
_PRE = ["2019年3月5日双方签订借款合同，对方当日未付款"]
_POST = ["2023年8月1日对方拖欠货款"]
_AS_OF_TODAY = date(2026, 9, 18)


def test_pre_watershed_fact_with_post_watershed_baseline_is_conflict():
    assert law_version_crosses_watershed(_TIMING_CLAIM, _PRE, _AS_OF_TODAY) is True


def test_same_side_of_watershed_is_not_conflict():
    assert law_version_crosses_watershed(_TIMING_CLAIM, _POST, _AS_OF_TODAY) is False


def test_injected_pre_watershed_baseline_matches_pre_watershed_fact():
    assert law_version_crosses_watershed(_TIMING_CLAIM, _PRE, date(2020, 6, 1)) is False


def test_missing_baseline_cannot_judge():
    assert law_version_crosses_watershed(_TIMING_CLAIM, _PRE, None) is False


def test_no_parseable_fact_date_does_not_trip():
    """无日期 ≠ 有冲突：拦它会误伤「诉讼时效是几年」这类纯法条陈述（2026-09-18 决策）。"""
    assert law_version_crosses_watershed(_TIMING_CLAIM, ["对方拖欠货款未还"], _AS_OF_TODAY) is False


def test_claim_without_limitation_assertion_does_not_trip():
    assert law_version_crosses_watershed("2019年3月5日的借款到期未还。", _PRE, _AS_OF_TODAY) is False


def test_labor_arbitration_is_outside_the_civil_code_watershed():
    """劳动仲裁时效依据劳调法 27 条（2008 年生效），与民法典分水岭无关。"""
    claim = "仲裁时效为一年，自当事人知道权利被侵害之日起算。"
    assert law_version_crosses_watershed(claim, _PRE, _AS_OF_TODAY) is False


def test_chinese_numeral_dates_are_not_parsed():
    """extract_dates 刻意只认阿拉伯数字日期 → 判不了就不拦（fail-open，模块边界一致）。"""
    assert law_version_crosses_watershed(_TIMING_CLAIM, ["二〇一九年三月五日借款"], _AS_OF_TODAY) is False
```

- [ ] **Step 2: 跑测试，确认失败原因是"函数不存在"**

Run: `cd "C:/Users/33393/Desktop/ai-legal-helper/backend" && ./venv/Scripts/python.exe -m pytest tests/test_r15_version_tripwire.py -q > ../_r15tripwire_t1_red.txt 2>&1; echo "RC=$?"`
Expected: `RC=1`，且日志含 `ImportError: cannot import name 'law_version_crosses_watershed'`。**若报别的错，先修到这条错因为止**（否则后面无法证明红过）。

- [ ] **Step 3: 实现函数（插在 `controlled_limitation_tokens` 之后）**

在 `backend/agent/limitation_calc.py:205`（`controlled_limitation_tokens` 的 `}` 收尾行）之后、`__all__` 之前插入：

```python
def law_version_crosses_watershed(
    claim_text: str,
    fact_texts: Iterable[str],
    law_as_of: date | None,
) -> bool:
    """True = 「按 law_as_of 版本的法回答分水岭前事实」的版本适用冲突（R15，2026-09-18）。

    判据全确定性，任一不满足 → False（不拦，调用方行为逐字不变）：
    1. claim 断言**民事**时效结论（命中 _CIVIL_KEYWORDS）；劳动仲裁走劳调法 27 条
       （2008 年生效，与民法典分水岭无关）→ 一律 False；
    2. `law_as_of` 已给定（None = 调用方没给基准日，无从判定）；
    3. 事实文本含可解析日期（无日期不拦：「没日期就不许谈时效」会误伤纯法条陈述）；
    4. 最早事实日（本模块边界 3 的起算锚）与 `law_as_of` **分跨** CIVIL_CODE_EFFECTIVE 两侧。

    与 `controlled_limitation_tokens` 的分工（不是重复）：后者只在**数字白名单**维度
    收回放行（fail-open，边界 1 刻意保守），本函数在**版本适用**维度终止作答
    （fail-closed）。它覆盖的是既有门看不见的一类：claim 不带年数 token（仅引用
    《民法典》某条）时，numeric 门无 token 可算、citation 门只验"条文是否在证据池"
    ——而证据池本身就是按 law_as_of 做 cutoff 捞的，必然只捞得到分水岭后的法。
    """
    text = unicodedata.normalize("NFKC", claim_text or "")
    if any(keyword in text for keyword in _LABOR_KEYWORDS):
        return False
    if not any(keyword in text for keyword in _CIVIL_KEYWORDS):
        return False
    if law_as_of is None:
        return False
    dates = extract_dates(fact_texts)
    if not dates:
        return False
    return (dates[0] < CIVIL_CODE_EFFECTIVE) != (law_as_of < CIVIL_CODE_EFFECTIVE)
```

- [ ] **Step 4: `__all__` 追加（保持字母序，ruff 不强制但既有风格如此）**

把 `backend/agent/limitation_calc.py` 的 `__all__` 改为：

```python
__all__ = [
    "CIVIL_CODE_EFFECTIVE",
    "CIVIL_GENERAL_YEARS",
    "CIVIL_MAXIMUM_YEARS",
    "CIVIL_PRE_CODE_YEARS",
    "LABOR_ARBITRATION_YEARS",
    "calc_limitation",
    "controlled_limitation_tokens",
    "extract_dates",
    "law_version_crosses_watershed",
]
```

- [ ] **Step 5: 跑测试确认 8 条全绿**

Run: `cd "C:/Users/33393/Desktop/ai-legal-helper/backend" && ./venv/Scripts/python.exe -m pytest tests/test_r15_version_tripwire.py -q > ../_r15tripwire_t1_green.txt 2>&1; echo "RC=$?"`
Expected: `RC=0`，末行 `8 passed`。

- [ ] **Step 6: 定向跑 R11 原测试，确认纯新增未扰动既有行为**

Run: `cd "C:/Users/33393/Desktop/ai-legal-helper/backend" && ./venv/Scripts/python.exe -m pytest tests/test_limitation_calc.py tests/test_r15_version_tripwire.py -q > ../_r15tripwire_t1_neighbor.txt 2>&1; echo "RC=$?"`
Expected: `RC=0`，无 failed。

- [ ] **Step 7: lint + 类型 + 提交**

Run: `cd "C:/Users/33393/Desktop/ai-legal-helper/backend" && ./venv/Scripts/python.exe -m ruff check agent/limitation_calc.py tests/test_r15_version_tripwire.py && ./venv/Scripts/python.exe -m ruff format agent/limitation_calc.py tests/test_r15_version_tripwire.py && ./venv/Scripts/python.exe -m mypy agent/limitation_calc.py; echo "MYPY_RC=$?"`
Expected: 无 error；`MYPY_RC=0`。format 若改写了文件，重跑 Step 5 确认仍绿。

```bash
cd "C:/Users/33393/Desktop/ai-legal-helper" && git add backend/agent/limitation_calc.py backend/tests/test_r15_version_tripwire.py && git diff --cached --name-only && git commit -m "feat(R15): 时效版本适用判定真源 law_version_crosses_watershed（纯新增，未接线）"
```
Expected: `git diff --cached --name-only` **只列出这两个路径**；多出一个就停手（裹进了别人的文件）。

---

## Task 2: 开关 + verifier 门（含接线自检）

**Files:**
- Modify: `backend/settings.py:80`（`phantom_tool_check` 之后）
- Modify: `backend/agent/verifier.py`（import 区 `:3-16`；`VerificationResult` `:40-49`；`verify` 签名 `:259-265`；claim 循环前 `_phantom_executions` 邻行；`FABRICATED_CITATION` 块 `:400-405` 之后；PASS 返回 `:455-462`；`_result` `:465-473`；`render_verified` `:217-226`）
- Test: `backend/tests/test_r15_version_tripwire.py`（续写）

**Interfaces:**
- Consumes: Task 1 的 `law_version_crosses_watershed(claim_text, fact_texts, law_as_of) -> bool`；`DeterministicVerifier._fact_texts(state) -> list[str]`（`verifier.py:244`，staticmethod）；`self._result(verdict, unsupported_claim_ids, reason_code, *, draft=None, state=None, covered_issues_exempt=frozenset())`（`verifier.py:465-473`，staticmethod）。
- Produces: `DeterministicVerifier.verify(state, draft, *, covered_issues_exempt=frozenset(), law_as_of: date | None = None) -> VerificationResult`。Task 3 消费 `law_as_of` kwarg。`VerificationResult.law_as_of: date | None = None`（**随结果携带**，供 `render_verified` 的二次验证复用——F1 修复）。新理由码 `LAW_TRIPWIRE_NOT_WIRED`、`LAW_VERSION_WATERSHED_MISMATCH`。

- [ ] **Step 1: 写「flag 默认关 + 7 条 verifier 行为」测试（应红）**

追加到 `backend/tests/test_r15_version_tripwire.py`。import 区在既有基础上补（**以下已实测为真实可导入名**，见 `tests/test_phantom_check.py:8-23`：`import settings as settings_module` 是顶层模块而非 `agent.settings`；`Fact`/`LegalIssue` 是普通 `BaseModel`（`schemas.py:50-66`，无 frozen）⇒ 可直接赋值改 statement，不必 deepcopy）：

```python
import pytest

import settings as settings_module
from agent.verifier import DeterministicVerifier, VerificationVerdict, render_verified
from agent.writer import EvidenceBoundedWriter
from routing_metrics import is_technical_fallback_reason
from tests.test_phantom_check import SingleClaimGenerator, writer_state
```

**注意（F3）**：默认值断言必须走**类** `settings_module.Settings.model_fields`（`settings.py:12` 定义
`class Settings(BaseSettings)`、`:198` 才有实例 `settings`）。实测 pydantic 2.13.4 下
`settings.settings.model_fields[...]`（实例访问）抛 `PydanticDeprecatedSince211`，V3 会移除。

```python
def _state_with_pre_watershed_fact():
    """把 writer_state 的事实改成 2019 年（分水岭前），其余结构复用 R12 已验证可用的 fixture。"""
    state = writer_state()
    state.issues[0].facts[0].statement = "2019年3月5日对方拖欠货款"
    return state


def test_tripwire_flag_defaults_off():
    assert settings_module.Settings.model_fields["law_version_tripwire_check"].default is False


def test_verifier_flag_off_leaves_cross_watershed_draft_passing(monkeypatch: pytest.MonkeyPatch):
    """默认关：同一条 draft 照常通过（行为逐字不变，基线安全）。"""
    monkeypatch.setattr(settings_module.settings, "law_version_tripwire_check", False)
    state = _state_with_pre_watershed_fact()
    draft = EvidenceBoundedWriter(SingleClaimGenerator(_TIMING_CLAIM)).render(state).draft
    assert draft is not None
    verdict = DeterministicVerifier().verify(state, draft, law_as_of=_AS_OF_TODAY)
    assert verdict.verdict is VerificationVerdict.PASS


def test_verifier_flag_on_blocks_cross_watershed_draft(monkeypatch: pytest.MonkeyPatch):
    """开关开 + 2019 事实 + today 基准 + claim 引用《民法典》→ 终态拒答。"""
    monkeypatch.setattr(settings_module.settings, "law_version_tripwire_check", True)
    state = _state_with_pre_watershed_fact()
    draft = EvidenceBoundedWriter(SingleClaimGenerator(_TIMING_CLAIM)).render(state).draft
    assert draft is not None
    verdict = DeterministicVerifier().verify(state, draft, law_as_of=_AS_OF_TODAY)
    assert verdict.verdict is VerificationVerdict.FAIL_SAFE
    assert verdict.reason_code == "LAW_VERSION_WATERSHED_MISMATCH"


def test_verifier_flag_on_keeps_post_watershed_draft_passing(monkeypatch: pytest.MonkeyPatch):
    """同开关下 2023 事实必须放行——防修成"一律拦"。"""
    monkeypatch.setattr(settings_module.settings, "law_version_tripwire_check", True)
    state = writer_state()
    draft = EvidenceBoundedWriter(SingleClaimGenerator(_TIMING_CLAIM)).render(state).draft
    assert draft is not None
    verdict = DeterministicVerifier().verify(state, draft, law_as_of=_AS_OF_TODAY)
    assert verdict.verdict is VerificationVerdict.PASS


def test_verifier_flag_on_without_baseline_fails_as_wiring_error(monkeypatch: pytest.MonkeyPatch):
    """接线自检：开关开而 law_as_of 没透传 ⇒ 绊线会静默失效，宁可显式失败。"""
    monkeypatch.setattr(settings_module.settings, "law_version_tripwire_check", True)
    state = writer_state()
    draft = EvidenceBoundedWriter(SingleClaimGenerator(_TIMING_CLAIM)).render(state).draft
    assert draft is not None
    verdict = DeterministicVerifier().verify(state, draft)
    assert verdict.verdict is VerificationVerdict.FAIL_SAFE
    assert verdict.reason_code == "LAW_TRIPWIRE_NOT_WIRED"


def test_pass_result_carries_the_baseline_date(monkeypatch: pytest.MonkeyPatch):
    """F1 修复的一半：PASS 结果必须带上基准日，供 render_verified 的二次验证复用。"""
    monkeypatch.setattr(settings_module.settings, "law_version_tripwire_check", True)
    state = writer_state()
    draft = EvidenceBoundedWriter(SingleClaimGenerator(_TIMING_CLAIM)).render(state).draft
    assert draft is not None
    verdict = DeterministicVerifier().verify(state, draft, law_as_of=_AS_OF_TODAY)
    assert verdict.verdict is VerificationVerdict.PASS
    assert verdict.law_as_of == _AS_OF_TODAY


def test_render_verified_reveals_with_tripwire_on(monkeypatch: pytest.MonkeyPatch):
    """F1 的正题：`render_verified` 内部会**再跑一次 verify**（verifier.py:226，经
    main.py:878 走生产链路）。它若不复用首轮基准日，二次验证就会命中
    LAW_TRIPWIRE_NOT_WIRED ⇒ 整轮交付 None，用户看到的是 VERIFIER_NOT_PASS，
    绊线原因码永远浮不上来。这条测试就是那道接线的看门狗。"""
    monkeypatch.setattr(settings_module.settings, "law_version_tripwire_check", True)
    state = writer_state()
    draft = EvidenceBoundedWriter(SingleClaimGenerator(_TIMING_CLAIM)).render(state).draft
    assert draft is not None
    verdict = DeterministicVerifier().verify(state, draft, law_as_of=_AS_OF_TODAY)
    assert verdict.verdict is VerificationVerdict.PASS, "前置失效：本轮就没通过，本测试需重做"
    assert render_verified(state, draft, verdict) is not None


def test_new_reason_codes_are_not_technical_fallbacks():
    """两个新理由码必须留在业务失败侧：落进 TECHNICAL_FALLBACK_REASON_CODES 会
    把"明确拒答"变成"静默降级到快速通道"（service._failure_or_fallback 的分支）。"""
    assert not is_technical_fallback_reason("LAW_VERSION_WATERSHED_MISMATCH")
    assert not is_technical_fallback_reason("LAW_TRIPWIRE_NOT_WIRED")
```

`is_technical_fallback_reason` 与 `TECHNICAL_FALLBACK_REASON_CODES` 实测在 `backend/routing_metrics.py:13-21,63`（顶层模块，非 `agent/`）。

- [ ] **Step 2: 跑测试确认红的原因正确**

Run: `cd "C:/Users/33393/Desktop/ai-legal-helper/backend" && ./venv/Scripts/python.exe -m pytest tests/test_r15_version_tripwire.py -q > ../_r15tripwire_t2_red.txt 2>&1; echo "RC=$?"`
Expected: `RC=1`。逐条失败原因必须是**这几种**（对不上就说明测试没测到东西）：

| 测试 | 加 flag 前的失败 | 加 flag 后、加门前的失败 |
|---|---|---|
| `test_tripwire_flag_defaults_off` | `KeyError: 'law_version_tripwire_check'`（`model_fields` 查不到） | PASS |
| 六条 `monkeypatch.setattr(..., "law_version_tripwire_check", ...)` 用例 | `AttributeError: 'Settings' object has no attribute …` | 见下几行 |
| `…_flag_off_leaves_cross_watershed_draft_passing` | 同上 | **PASS**（关着就该逐字不变） |
| `…_flag_on_blocks_cross_watershed_draft` | 同上 | `assert <VerificationVerdict.PASS> is VerificationVerdict.FAIL_SAFE` ← **这条必须是"放行了"而不是报错**，它才是"门此前不存在"的证据 |
| `…_flag_on_keeps_post_watershed_draft_passing` | 同上 | PASS |
| `…_flag_on_without_baseline_fails_as_wiring_error` | 同上 | `assert … PASS is … FAIL_SAFE` |
| `test_pass_result_carries_the_baseline_date` | 同上 | `AttributeError: 'VerificationResult' object has no attribute 'law_as_of'`（字段还没加）→ Step 6b 加字段后、PASS 未携带时红在 `assert None == datetime.date(2026, 9, 18)` |
| `test_render_verified_reveals_with_tripwire_on` | 同上 | `TypeError`/`AttributeError`（同上）→ **携带修好后、`render_verified` 未透传时**红在 `assert None is not None`（这条就是 F1 的现场） |
| `test_new_reason_codes_are_not_technical_fallbacks` | **PASS**（锁的是既有不变量；红在既有事实上的测试是坏测试） | PASS |

若拦截那条报 `TypeError: verify() got an unexpected keyword argument 'law_as_of'`，先只做 Step 7 的签名改动再重跑，直到看见"放行"这一红。

- [ ] **Step 3: 加开关**

`backend/settings.py:80` 的 `phantom_tool_check: bool = False` 之后插入：

```python
    # R15 法律版本适用绊线（2026-09-18，外部 harness 方案差距分析 P0-2 之评测侧配套）：
    # claim 按 law_as_of 版本的法回答 2021-01-01（《民法典》1260 条）分水岭前的事实 →
    # verifier 终态拒答（LAW_VERSION_WATERSHED_MISMATCH）。判定真源
    # agent/limitation_calc.law_version_crosses_watershed；默认关 = verifier 行为逐字不变
    # （与 phantom_tool_check / entity_precision_check 同一开关惯例；开启属评测批预登记事项）。
    law_version_tripwire_check: bool = False
```

- [ ] **Step 4: verifier 提模块级 import**

`backend/agent/verifier.py:15` 由 `from . import phantom_check` 改为：

```python
from . import limitation_calc, phantom_check
```

同时把 `verifier.py:369-371` 里那处函数内 import 删掉（现在冗余）：

```python
                unsupported_v -= self._fact_allowlist(state)
                # R11 受控时效放行集（与 writer 同口径；claim 断言时效结论 + 事实含日期才触发）。
                unsupported_v -= limitation_calc.controlled_limitation_tokens(claim.text, self._fact_texts(state))
```

并在 import 区加 `from datetime import date`（放在 `from enum import StrEnum` 之前，随后由 ruff isort 定序）。

- [ ] **Step 5: 接线自检 + 按争点预取事实文本**

在 `verifier.py` 里 `_phantom_executions = ...` 那一段之后（同一缩进层级，claim 循环之前）追加：

```python
        # R15 版本适用绊线：开关开而基准日没透传 = 接线丢失（历史上此类丢参真实发生过，
        # 见 docs/handoff-external-harness-20260918.md §2.4 透传锁），显式失败不静默放行。
        if settings.law_version_tripwire_check and law_as_of is None:
            return self._result(VerificationVerdict.FAIL_SAFE, [], "LAW_TRIPWIRE_NOT_WIRED")
        _tripwire_fact_texts = self._fact_texts(state) if settings.law_version_tripwire_check else []
```

- [ ] **Step 6: claim 循环内加判定**

在 `verifier.py:400-405` 的 `FABRICATED_CITATION` 返回块之后（仍在 `for claim in claims:` 内）追加：

```python
            # R15 版本适用绊线（law_version_tripwire_check，默认关 = 行为逐字不变）：
            # 判定真源在 limitation_calc.law_version_crosses_watershed（单一真源，此处只消费）。
            if settings.law_version_tripwire_check and limitation_calc.law_version_crosses_watershed(
                claim.text, _tripwire_fact_texts, law_as_of
            ):
                return self._result(
                    VerificationVerdict.FAIL_SAFE,
                    [claim.claim_id],
                    "LAW_VERSION_WATERSHED_MISMATCH",
                )
```

- [ ] **Step 6b: 把基准日随 PASS 结果携带，喂给二次验证（F1 修复，本任务真正的接线）**

`render_verified`（`verifier.py:217-239`）在首轮 PASS 后会**再跑一次 `verify()`**（`:226`）做
digest 复核，生产入口是 `main.py:878`（`finalize_verified_agent_answer`，即 service 用的 finalizer）。
它拿不到 `law_as_of` ⇒ 开关一开，二次验证必然命中 `LAW_TRIPWIRE_NOT_WIRED` ⇒ 返回 None ⇒
用户侧只看到 `VERIFIER_NOT_PASS`。这是**同一文件里已经解决过一次的问题**——`:46-49` 的
`covered_issues_exempt` 注释原文："service 的豁免集合随结果传递，供 render_verified 的 fresh
二次验证使用同一豁免（否则二次验证用默认空集会再次拦下部分交付）"。本步按同型解法做，
**不改 `render_verified` / `Finalizer` 签名**（改了会砸到并行会话 20:13 的
`tests/test_agent_chat_integration.py:348`，那是对方的 `_Final(answer=render_verified(state, draft, verification))`）。

四处改动，逐字如下（`VerificationResult` 用的 `date` 由 Step 4 已加的模块级 import 提供）：

1）`VerificationResult`（`:40-49`）在 `covered_issues_exempt` 字段之后追加（同样**不参与 digest**）：

```python
    # R15（2026-09-18）：基准日随结果传递，供 render_verified 的 fresh 二次验证复用同一基准
    # （与上面 covered_issues_exempt 同款理由：否则二次验证用 None 会走到 LAW_TRIPWIRE_NOT_WIRED）。
    # 不参与 digest——digest 只绑定 state/draft 内容。
    law_as_of: date | None = None
```

2）`_result`（`:465-473`）的关键字参数区加一项，并在 `VerificationResult(...)` 构造里传递：

```python
        covered_issues_exempt: frozenset[str] = frozenset(),
        law_as_of: date | None = None,
    ) -> VerificationResult:
```

```python
             covered_issues_exempt=covered_issues_exempt,
             law_as_of=law_as_of,
```

3）唯一的 PASS 返回（`:455-462`）加一行（**只有 PASS 需要**：非 PASS 走不到二次验证，
`render_verified:224` 会先返回 None）：

```python
        return self._result(
            VerificationVerdict.PASS,
            [],
            "VERIFIED",
            draft=draft,
            covered_issues_exempt=covered_issues_exempt,
            state=state,
            law_as_of=law_as_of,
        )
```

4）`render_verified` 内的二次验证（`:226`）复用结果里的基准日：

```python
    fresh = DeterministicVerifier().verify(
        state,
        draft,
        covered_issues_exempt=verification.covered_issues_exempt,
        law_as_of=verification.law_as_of,
    )
```

**方向自检**：若某处手工构造的 PASS 结果没带 `law_as_of`（如 `test_agent_verifier.py:360` 的
`forged_pass`），二次验证在开关关时无差别；开关开时落 `LAW_TRIPWIRE_NOT_WIRED` → 交付 None——
**fail-closed 方向正确**（宁可不出答案，不出错答案），无需为它开豁免。

- [ ] **Step 7: verify 签名加参数**

`verifier.py:259-265` 的关键字参数区改为：

```python
    def verify(
        self,
        state: LegalAgentState,
        draft: DraftAnswer,
        *,
        covered_issues_exempt: frozenset[str] = frozenset(),
        law_as_of: date | None = None,
    ) -> VerificationResult:
```

并在其 docstring 末尾追加一段（保持既有 docstring 风格）：

```
        `law_as_of`（R15 版本适用绊线）：本次任务适用法律的基准日，由调用方（service）从
        `AgentRun.law_as_of` 透传。**默认 None ⇒ 绊线不可判 ⇒ 不拦**；但开关一开而这里仍是
        None，视为接线丢失并 fail-closed（`LAW_TRIPWIRE_NOT_WIRED`），因为静默放行正是该门要防的失败模式。
```

- [ ] **Step 8: 跑测试确认全绿**

Run: `cd "C:/Users/33393/Desktop/ai-legal-helper/backend" && ./venv/Scripts/python.exe -m pytest tests/test_r15_version_tripwire.py -q > ../_r15tripwire_t2_green.txt 2>&1; echo "RC=$?"`
Expected: `RC=0`，`16 passed`（Task 1 的 8 条 + 本任务 8 条）。

- [ ] **Step 9: 跑 verifier/writer 邻近既有套，确认零回归**

Run: `cd "C:/Users/33393/Desktop/ai-legal-helper/backend" && ./venv/Scripts/python.exe -m pytest tests/test_agent_verifier.py tests/test_phantom_check.py tests/test_limitation_calc.py -q -m "not slow" --basetemp="../_pt_r15tripwire_t2" > ../_r15tripwire_t2_neighbor.txt 2>&1; echo "RC=$?"`
Expected: `RC=0`，无 failed。（`test_agent_verifier.py` 只跑不改——它是并行会话 20:13 的文件。）

- [ ] **Step 10: lint/类型/提交**

Run: `cd "C:/Users/33393/Desktop/ai-legal-helper/backend" && ./venv/Scripts/python.exe -m ruff check agent/verifier.py settings.py tests/test_r15_version_tripwire.py && ./venv/Scripts/python.exe -m ruff format agent/verifier.py settings.py tests/test_r15_version_tripwire.py && ./venv/Scripts/python.exe -m mypy agent/verifier.py; echo "MYPY_RC=$?"`
Expected: 无 error、`MYPY_RC=0`。若 format 改动了文件，`git diff` 逐行复核**只含本次 hunk**，再重跑 Step 8。

```bash
cd "C:/Users/33393/Desktop/ai-legal-helper" && git add backend/settings.py backend/agent/verifier.py backend/tests/test_r15_version_tripwire.py && git diff --cached --name-only && git commit -m "feat(R15): verifier 版本适用绊线 + 基准日随 PASS 结果喂给 render_verified 二次验证（默认关）"
```

---

## Task 3: service 透传 + watch-it-fail 留痕（probe）

**Files:**
- Modify: `backend/agent/service.py:472-476`
- Create: `backend/tests/_r15_tripwire_probe.py`

**Interfaces:**
- Consumes: Task 2 的 `verify(..., law_as_of=...)`；`saved_record.law_as_of`（`AgentRun` 列，`models.py:144` NOT NULL）。
- Produces: 生产链路上 verifier 拿到真实基准日。

- [ ] **Step 1: 改调用点**

`backend/agent/service.py:471-476` 改为：

```python
    try:
        verification = runtime.verifier.verify(
            state,
            draft,
            covered_issues_exempt=frozenset(issue_id for issue_id, _ in uncovered),
            law_as_of=saved_record.law_as_of,
        )
```

- [ ] **Step 2: 复核落盘（Edit 成功 ≠ 落盘）**

Run: `cd "C:/Users/33393/Desktop/ai-legal-helper" && git diff -- backend/agent/service.py`
Expected: 恰好 1 行 `+ law_as_of=saved_record.law_as_of,`。没有这一行 = 编辑没落盘，重做。

- [ ] **Step 3: 跑 service 级既有套**

Run: `cd "C:/Users/33393/Desktop/ai-legal-helper/backend" && ./venv/Scripts/python.exe -m pytest tests/test_agent_chat_integration.py -q -m "not slow" --basetemp="../_pt_r15tripwire_t3" > ../_r15tripwire_t3.txt 2>&1; echo "RC=$?"`
Expected: `RC=0`。

- [ ] **Step 4: 写 probe（不污染源码的"没有这道门会怎样"留痕）**

Create `backend/tests/_r15_tripwire_probe.py`（`_` 前缀 ⇒ 不被默认收集，见 `backend/pyproject.toml` testpaths 口径）：

```python
"""R15 绊线的 watch-it-fail 留痕（B3，2026-09-18）。

证明「拦住这条 draft 的就是 law_version_crosses_watershed 这道判定」：把判定打桩成
恒 False（= 本批新增的门不存在），其余一切不变，断言该 draft 会一路 PASS 交付给用户。

一键复现：
    cd backend && ./venv/Scripts/python.exe -m pytest tests/_r15_tripwire_probe.py -q -m "not slow"
"""

from __future__ import annotations

from datetime import date

import pytest

import settings as settings_module
from agent import limitation_calc
from agent.verifier import DeterministicVerifier, VerificationVerdict
from agent.writer import EvidenceBoundedWriter
from tests.test_phantom_check import SingleClaimGenerator
from tests.test_r15_version_tripwire import _TIMING_CLAIM, _state_with_pre_watershed_fact


@pytest.fixture(autouse=True)
def _stub_gate(monkeypatch: pytest.MonkeyPatch):
    """开关开 + 判定恒 False —— 等价于"本批这道门还没写"的世界。"""
    monkeypatch.setattr(settings_module.settings, "law_version_tripwire_check", True)
    monkeypatch.setattr(limitation_calc, "law_version_crosses_watershed", lambda *a, **k: False)


def test_without_the_gate_the_cross_watershed_answer_ships():
    state = _state_with_pre_watershed_fact()
    draft = EvidenceBoundedWriter(SingleClaimGenerator(_TIMING_CLAIM)).render(state).draft
    assert draft is not None, "前置失效：草稿都没生成，本留痕需重做"
    verdict = DeterministicVerifier().verify(state, draft, law_as_of=date(2026, 9, 18))
    assert verdict.verdict is VerificationVerdict.PASS, (
        f"门被桩掉后仍被拦下（{verdict.reason_code}）⇒ 该缺陷其实已被别的门覆盖，本留痕需重做"
    )
```

注意：`_TIMING_CLAIM` 与 `_state_with_pre_watershed_fact` 从主测文件导入（DRY，且保证留痕与被审测试用同一份输入）。`_` 前缀名跨测试模块导入是既有做法（本仓 `tests/` 是包，见 `from tests.test_phantom_check import …`）。

- [ ] **Step 5: 跑 probe，亲眼见"没有门就放行"**

Run: `cd "C:/Users/33393/Desktop/ai-legal-helper/backend" && ./venv/Scripts/python.exe -m pytest tests/_r15_tripwire_probe.py -q > ../_r15tripwire_probe.txt 2>&1; echo "RC=$?"`
Expected: `RC=0`，`1 passed`。
若断言失败并打印出别的 reason_code —— **那不是失败，是收获**：说明该路径已被另一道门覆盖，本批绊线的价值需重新评估。此时停手，把 reason_code 抄进报告并回到 Owner。

- [ ] **Step 6: 提交**

```bash
cd "C:/Users/33393/Desktop/ai-legal-helper" && git add backend/agent/service.py backend/tests/_r15_tripwire_probe.py && git diff --cached --name-only && git commit -m "feat(R15): service 向 verifier 透传 run.law_as_of + 绊线 watch-it-fail 留痕"
```

---

## Task 4: 评测注入出口（gate2_runner 透传 law_as_of，不碰冻结集）

**Files:**
- Modify: `backend/scripts/gate2_runner.py`（新增 `_round1_payload`；`:460-464` 换调用；argparse `:293-298` 后加 `--no-as-of-date`）
- Create: `evals/watershed-cases-r15.json`
- Test: `backend/tests/test_r15_runner_injection.py`

**Interfaces:**
- Consumes: 既有 `_case_domain_of(case) -> str | None`（`:68`）、`_CASE_DOMAIN_MAP`（`:55`，含 `"诉讼时效与保证期间": "civil"`）。
- Produces: `_round1_payload(case: dict, *, no_case_domain: bool, no_as_of_date: bool) -> dict`；HTTP body 可选键 `law_as_of`（ISO 字符串）。

- [ ] **Step 1: 写 helper 的三条契约测试 + 一条题集 schema 测试（应红：AttributeError / 文件不存在）**

Create `backend/tests/test_r15_runner_injection.py`：

```python
"""R15：gate2_runner 的 law_as_of 透传契约 + 对照题集结构契约（2026-09-18）。

只锁"什么时候发这个键"与"题集字段形状对不对"，不发真实 HTTP（零模型调用、零花费）。
契约真源（独立于本实现）：`evals/validate_cases.py:37-40,75,92-99` 与
`backend/scripts/gate5_judge.py:93`（`int(x[1])` ⇒ required_laws 必须是 [[str, int]]）。
"""

from __future__ import annotations

import json
from pathlib import Path

import scripts.gate2_runner as runner

_CASE = {
    "id": "W01",
    "initial_question": "2019年3月5日借的钱，现在起诉还有效吗？",
    "domain": "诉讼时效与保证期间",
    "as_of_date": "2026-09-18",
}
_CASES_PATH = Path(__file__).resolve().parents[2] / "evals" / "watershed-cases-r15.json"


def test_payload_carries_law_as_of_when_case_declares_it():
    assert runner._round1_payload(_CASE, no_case_domain=False, no_as_of_date=False)["law_as_of"] == "2026-09-18"


def test_payload_omits_law_as_of_when_case_has_no_as_of_date():
    case = {k: v for k, v in _CASE.items() if k != "as_of_date"}
    assert "law_as_of" not in runner._round1_payload(case, no_case_domain=False, no_as_of_date=False)


def test_no_as_of_date_flag_simulates_production_shape():
    assert "law_as_of" not in runner._round1_payload(_CASE, no_case_domain=False, no_as_of_date=True)


def test_base_fields_unchanged():
    payload = runner._round1_payload(_CASE, no_case_domain=True, no_as_of_date=True)
    assert payload == {"content": _CASE["initial_question"], "no_cache": True, "force_agent": True}


def test_watershed_cases_conform_to_case_schema():
    """题集必须能被 runner + gate5_judge 消费：字段齐、类型对（F2 的看门狗）。

    期望值不来自本实现，而来自 `evals/validate_cases.py:37-40,75` 与
    `backend/scripts/gate5_judge.py:93`（`int(x[1])` ⇒ required_laws 必须 [[str,int]]）。
    """
    doc = json.loads(_CASES_PATH.read_text(encoding="utf-8"))
    assert doc["schema_version"] == "r15-watershed-v1"
    assert len(doc["cases"]) == 2
    for case in doc["cases"]:
        for field in (
            "id",
            "domain",
            "initial_question",
            "round1_facts",
            "round2_facts",
            "required_issues",
            "required_laws",
            "critical_failures",
            "deciding_facts",
            "fact_reveal",
            "as_of_date",
        ):
            assert field in case, f"{case.get('id')}: 缺字段 {field}"
        assert isinstance(case["round1_facts"], str), "round1_facts 必须是 str（v1 契约，非数组）"
        assert runner._case_domain_of(case) == "civil", f"{case['id']}: domain 未映射 ⇒ 不会发 case_domain"
        for entry in case["required_laws"]:
            assert isinstance(entry, list) and len(entry) == 2, "required_laws 条目必须是 [法名, 条号]"
            assert isinstance(entry[0], str) and isinstance(entry[1], int), "条号必须是 int，否则 judge int() 崩"
        for rnd, units in case["fact_reveal"].items():
            assert rnd in ("r1", "r2"), f"{case['id']}: 非法轮次 {rnd}"
            for unit in units:
                assert unit.get("text") and unit.get("keywords"), f"{case['id']}.{rnd}: 单元缺 text/keywords"
    # 对照臂设计：两条只差事实发生日，一侧跨分水岭一侧不跨
    w01, w02 = doc["cases"]
    assert w01["as_of_date"] == w02["as_of_date"]
    assert "2019" in w01["initial_question"] and "2023" in w02["initial_question"]
```

Step 7 的题集文件建好之前，schema 那条会因 `FileNotFoundError` 红——与 helper 的 `AttributeError`
红因不同、互不掩盖（Step 2 要求两条红因同时出现）。

- [ ] **Step 2: 跑测试确认红的原因正确（两条红因）**

Run: `cd "C:/Users/33393/Desktop/ai-legal-helper/backend" && ./venv/Scripts/python.exe -m pytest tests/test_r15_runner_injection.py -q > ../_r15tripwire_t4_red.txt 2>&1; echo "RC=$?"`
Expected: `RC=1`，日志里同时出现
① `AttributeError: module 'scripts.gate2_runner' has no attribute '_round1_payload'`（4 条 helper 用例）
② `FileNotFoundError: ... watershed-cases-r15.json`（schema 那条）。
只有其中一种红 = 另一条测试没在执行，先修到两条都红。

- [ ] **Step 3: 加 helper（插在 `_case_domain_of` 之后，即 `:70` 之后）**

```python
def _round1_payload(case: dict, *, no_case_domain: bool, no_as_of_date: bool) -> dict:
    """首轮请求体：固定三键 + 两个「按案例声明才传」的 server-owned 注入字段。

    `case_domain`（R1-OB）与 `law_as_of`（R15）同口径：生产前端不传，评测按案例声明透传；
    两个 `--no-*` 开关用于模拟生产形态（缺省=评测形态）。案例缺字段 ⇒ 不发该键，
    由服务端按自己的缺省处理（law_as_of 缺省落当日，见 repository.create_run）。
    """
    payload: dict = {"content": case["initial_question"], "no_cache": True, "force_agent": True}
    domain = None if no_case_domain else _case_domain_of(case)
    if domain is not None:
        payload["case_domain"] = domain
    if not no_as_of_date and case.get("as_of_date") is not None:
        payload["law_as_of"] = case["as_of_date"]
    return payload
```

- [ ] **Step 4: 换调用点（原 `:460-464` 五行）**

把

```python
        payload = {"content": c["initial_question"], "no_cache": True, "force_agent": True}
        _cd = None if args.no_case_domain else _case_domain_of(c)
        if _cd is not None:
            # R1-OB：tier-1 域码随请求透传（--no-case-domain 关闭=生产形态；未映射案例不带该键）
            payload["case_domain"] = _cd
```

替换为

```python
        # R1-OB 域码 + R15 基准日：两个注入字段的口径统一在 _round1_payload（含注释）。
        payload = _round1_payload(c, no_case_domain=args.no_case_domain, no_as_of_date=args.no_as_of_date)
```

- [ ] **Step 5: 加 argparse 开关（`:298` 的 `--no-case-domain` 块之后）**

```python
    ap.add_argument(
        "--no-as-of-date",
        action="store_true",
        help="不向服务端透传 law_as_of（模拟**生产形态**：基准日由服务端落当日）；缺省=案例声明 "
        "as_of_date 时透传（R15 跨 2021-01-01 分水岭对照臂口径）",
    )
```

- [ ] **Step 6: 跑新测试 + 对方那份 runner 回归套（作为重构保护网）**

Run: `cd "C:/Users/33393/Desktop/ai-legal-helper/backend" && ./venv/Scripts/python.exe -m pytest tests/test_r15_runner_injection.py tests/test_gate2_runner.py -q -m "not slow" --basetemp="../_pt_r15tripwire_t4" > ../_r15tripwire_t4_green.txt 2>&1; echo "RC=$?"`
Expected: `RC=0` 且日志末尾**无 failed**（本文件贡献 5 条，`test_gate2_runner.py` 的条数以它自己为准，
别把两份加成一个"应等于"的数）。**保护范围要说准**：
它用**真实 `ThreadingHTTPServer`**（`:13,:120,:479`）驱动 `main()` 并记录收到的 payload
（`service.chat_requests.append(dict(payload))`，`:84,:448`），能逮住"抽 helper 后请求根本没发出去/
轮次归因错"；但它**不锁 payload 里有哪些键**（全文件无 `case_domain` 断言，实测）⇒
"键发没发"只由本任务的 5 条契约测试负责，不要对外声称"注入已被端到端测试覆盖"。
该文件**只跑不改**（并行会话 20:13 的文件）。

- [ ] **Step 7: 建非冻结对照样本（2 条，只测版本适用）——按真实 case schema（F2）**

**先订正：初稿这段的字段类型是错的**（把 `round1_facts` 写成数组、`required_laws` 写成字符串，且漏了
`fact_reveal`）。真实契约由三处实测钉死：`evals/validate_cases.py:37-40`（V1 十字段名单）、
`:75` `for src, n in c.get("required_laws", [])`（**必须是 `[["法名", 条号int]]`**）、
`backend/scripts/gate5_judge.py:93` `[[str(x[0]), int(x[1])] for x in …]`（写成字符串 ⇒ `int("民")`
**ValueError 崩判分**），以及 `gate2_runner.py:200-222`（新案例的 `fact_reveal` 才进事实投放 meta）。
E01 实测 dump：`round1_facts` 是 str；`fact_reveal = {"r1":[{"text":…,"keywords":[…]}],"r2":[…]}`。

Create `evals/watershed-cases-r15.json`：

```json
{
  "schema_version": "r15-watershed-v1",
  "purpose": "R15 跨 2021-01-01 分水岭对照臂（**非冻结集**）：同题面、仅事实发生日跨/不跨分水岭，验证 law_as_of 注入与版本适用绊线的实际效果。",
  "status": "NOT_FROZEN",
  "note": "as_of_date 由 backend/scripts/gate2_runner.py 的 _round1_payload 透传为 HTTP body 的 law_as_of；生产形态用 --no-as-of-date。本文件刻意不进 evals/frozen-cases-v2.json（T0 冻结物，改动须 Owner 决策卡 + candidate-hashes 重锚定）。不被 evals/validate_cases.py 覆盖（该脚本硬编码 V2 路径且断言 20 例）⇒ 本批用 tests/test_r15_runner_injection.py 的 schema 测试代跑结构契约，sha256 记进收口报告。",
  "cases": [
    {
      "id": "W01",
      "domain": "诉讼时效与保证期间",
      "as_of_date": "2026-09-18",
      "initial_question": "2019年3月5日对方向我借款10万元，约定当日归还，此后我一直没催过，也没还过钱。我现在起诉还能胜诉吗？",
      "round1_facts": "借款发生于2019年3月5日；约定还款日就是当天；此后没有任何催收记录。",
      "round2_facts": "期间未主张过权利，也无还款、承认等中断事由；我是个人出借，对方也是个人。",
      "fact_reveal": {
        "r1": [
          {
            "text": "钱是2019年3月5日当面给的，说好当天就还，一直到现在我都没催过。",
            "keywords": ["2019", "借款", "给的", "当天", "没催"]
          }
        ],
        "r2": [
          {
            "text": "这几年我没有主张过权利，对方也没有还过钱或者承认过欠款，没有任何中断事由。",
            "keywords": ["没有", "主张", "中断", "承认", "还过"]
          }
        ]
      },
      "required_issues": ["诉讼时效是否经过"],
      "required_laws": [],
      "forbidden_articles": [],
      "critical_failures": [
        "对2019年事实直接按《民法典》第一百八十八条给出三年时效结论而不作新旧法衔接说明",
        "把起算日或到期日说成2021年1月1日之后"
      ],
      "deciding_facts": ["权利受损日/约定还款日是否早于2021-01-01", "有无中断事由"],
      "scope_trigger": false
    },
    {
      "id": "W02",
      "domain": "诉讼时效与保证期间",
      "as_of_date": "2026-09-18",
      "initial_question": "2023年8月1日对方向我借款10万元，约定当日归还，此后我一直没催过，也没还过钱。我现在起诉还能胜诉吗？",
      "round1_facts": "借款发生于2023年8月1日；约定还款日就是当天；此后没有任何催收记录。",
      "round2_facts": "期间未主张过权利，也无还款、承认等中断事由；我是个人出借，对方也是个人。",
      "fact_reveal": {
        "r1": [
          {
            "text": "钱是2023年8月1日当面给的，说好当天就还，一直到现在我都没催过。",
            "keywords": ["2023", "借款", "给的", "当天", "没催"]
          }
        ],
        "r2": [
          {
            "text": "这几年我没有主张过权利，对方也没有还过钱或者承认过欠款，没有任何中断事由。",
            "keywords": ["没有", "主张", "中断", "承认", "还过"]
          }
        ]
      },
      "required_issues": ["诉讼时效是否经过"],
      "required_laws": [],
      "forbidden_articles": [],
      "critical_failures": ["把2023年的事实说成分水岭前情形、按旧法两年口径作答"],
      "deciding_facts": ["权利受损日晚于2021-01-01", "有无中断事由"],
      "scope_trigger": false
    }
  ]
}
```

**两条都留 `required_laws: []` 是刻意的**：判据端 `[[法名, 条号]]` 需经
`retrieval.article_in_kb` 核验（`validate_cases.py:77-78` 的口径是"required 缺库 = 评测假红，必须 0"）。
本批不开口声称「《民法典》188 条在库」——那需要真实向量库探针，而并行会话此刻正在改
`retrieval`/`rag_chain`（在途），此刻取到的数不能代表提交态。**填它 = 后续评测批的一步**，
命令已写在 Step 8b。

- [ ] **Step 8: 结构契约 + 装载校验（不靠人眼）**

先跑 schema 测试（Step 1 的第 5 条）：
Run: `cd "C:/Users/33393/Desktop/ai-legal-helper/backend" && ./venv/Scripts/python.exe -m pytest tests/test_r15_runner_injection.py -q > ../_r15tripwire_t4_green.txt 2>&1; echo "RC=$?"`
Expected: `RC=0`，`5 passed`。

再确认 runner 真能装载它（`gate2_runner` 用 `CASES = json.loads(...)["cases"]` + `BY_ID`）：
Run: `cd "C:/Users/33393/Desktop/ai-legal-helper/backend" && ./venv/Scripts/python.exe -c "import json,pathlib; d=json.loads(pathlib.Path('../evals/watershed-cases-r15.json').read_text(encoding='utf-8')); print(len(d['cases']), [c['id'] for c in d['cases']], [c['as_of_date'] for c in d['cases']], [type(c['round1_facts']).__name__ for c in d['cases']])"`
Expected: `2 ['W01', 'W02'] ['2026-09-18', '2026-09-18'] ['str', 'str']`

最后落 sha256（基线冻结纪律的最小履行，F6）：
Run: `cd "C:/Users/33393/Desktop/ai-legal-helper" && ./backend/venv/Scripts/python.exe -c "import hashlib,pathlib; print(hashlib.sha256(pathlib.Path('evals/watershed-cases-r15.json').read_bytes()).hexdigest())"`
Expected: 一串 64 位十六进制；抄进收口报告，并注明"此后改内容须换 `schema_version`"。

- [ ] **Step 8b: （可选，留给评测批）把 `required_laws` 填成判据**

只有当能跑 `article_in_kb` 探针时才填，且填之前必须**先在真库上核过**（`validate_cases.py:77-78` 口径）。
命令（会在 import 期加载 BGE，约 1 分钟；**须等 T-E 收敛后再跑**，否则读数不代表提交态）：

```bash
cd "C:/Users/33393/Desktop/ai-legal-helper/backend" && ./venv/Scripts/python.exe -c "import os; os.environ.setdefault('HF_HUB_OFFLINE','1'); from dotenv import load_dotenv; load_dotenv(override=True); from retrieval import article_in_kb; print([(s,a,article_in_kb(s,a)) for s,a in [('民法典','第188条'),('民法典','第195条'),('民法通则','第135条')]])"
```

True 的条目才写进 `required_laws`，形如 `[["民法典", 188]]`（**int 条号，不是中文数字**）；
False 的保持空着并在 `note` 里写"库缺该条"。**本批默认不填**（Step 7 已说明理由）。

- [ ] **Step 9: lint / 提交（类型检查见 F7，本任务刻意不跑）**

Run: `cd "C:/Users/33393/Desktop/ai-legal-helper/backend" && ./venv/Scripts/python.exe -m ruff check scripts/gate2_runner.py tests/test_r15_runner_injection.py && ./venv/Scripts/python.exe -m ruff format scripts/gate2_runner.py tests/test_r15_runner_injection.py; echo "RUFF_RC=$?"`

⚠️ **F7：这里刻意不跑 `mypy scripts/gate2_runner.py`**。实测该命令 **RC=1、4 个既有错误**
（`:456/:503` var-annotated ×3、`:550` attr-defined），与本批无关且早已写在 `pyproject.toml` 的
mypy 注释里（"scripts/ 在 exclude 内、不参与类型检查……已知 scripts/gate2_runner.py 有 4 个既有错误"）。
去"顺手修"= 在对方 lane 里扩面。⇒ 类型护栏由 Task 6 的 `mypy .`（不含 scripts/）+ 本任务 5 条契约测试代偿，
`_round1_payload` 的注解必须**手写正确**（`case: dict, *, no_case_domain: bool, no_as_of_date: bool) -> dict`）。

```bash
cd "C:/Users/33393/Desktop/ai-legal-helper" && git add backend/scripts/gate2_runner.py backend/tests/test_r15_runner_injection.py evals/watershed-cases-r15.json && git diff --cached --name-only && git commit -m "feat(R15): gate2_runner 按案例 as_of_date 透传 law_as_of + 分水岭对照样本（非冻结集）"
```

- [ ] **Step 10: 明确不做（写进收口报告，不留模糊）**

对照臂**本批不执行**：`gate2_runner` POST `--base-url`（默认 `http://127.0.0.1:8000`）需常驻服务 + 真实模型调用；本会话沙盒会收割子进程，服务须由 Owner 侧启动。执行命令模板（供 Owner 用）：

```bash
cd backend && ./venv/Scripts/python.exe scripts/gate2_runner.py \
  --cases-file ../evals/watershed-cases-r15.json --all
```

---

## Task 5: 留痕与订正（边界注释 + 成本失实订正 + 交接书勘误）

**Files:**
- Modify: `backend/agent/repository.py:52-57`（**仅 docstring**）
- Modify: `docs/external-harness-plan-gap-analysis-20260918.md:137-138`
- Modify: `docs/handoff-external-harness-20260918.md`（§4.1 路径勘误 + §4 追加已完成项）

- [ ] **Step 1: repository docstring 补边界（代码一字不动）**

`backend/agent/repository.py:54-56` 的 R15-lite 段末追加一行，改为：

```python
    R15-lite（2026-09-18）：`law_as_of` 缺省 None 时落当日（行为逐字不变）；评测/
    灰度通道可显式注入法律版本基准日（如 2021-01-01 民法典分水岭场景），随 run
    持久化并被工具 cutoff/证据有效性判定消费。server-owned：值只能由服务端代码设置。
    边界（R15 绊线，2026-09-18）：缺省落当日意味着**分水岭前事实会得到分水岭后的法**；
    该错答由 `verifier` 的 `law_version_tripwire_check` 拦（默认关）。本行默认行为按
    docs/handoff-external-harness-20260918.md §2.3 明确锁定，不得改成必填或报错。
```

Run: `cd "C:/Users/33393/Desktop/ai-legal-helper" && git diff -- backend/agent/repository.py`
Expected: 只有 docstring 行变化，`law_as_of=law_as_of or date.today(),` 一行**不得出现在 diff 里**。

- [ ] **Step 2: 订正 gap-analysis 的成本判断**

`docs/external-harness-plan-gap-analysis-20260918.md:138`「改起来是一个函数的事」后追加订正，并把该条状态改写。
**注意**：`:138` 原文写的是 `repository.py:62`，实测该缺省行为在解冻后的 `repository.py:72`
（`law_as_of=law_as_of or date.today(),`）——**同一处失实有两层**（成本判断 + 行号），订正时一并写清。
目标文本（替换 `:137-138` 两行）：

```markdown
2. **R38 + R15：给评测样本加 `fact_date`，并把 `law_as_of` 默认从"今天"改成"抽到的事实日，抽不到就追问"**
   目前 `repository.py:72` 写死 `date.today()`，是明确的行为 bug 级隐患。
   ~~改起来是一个函数的事。~~ **（2026-09-18 实施时订正）**成本被低估：① 抽取环节整条不存在
   （`fact_date` 仅出现在 `limitation_calc` 形参与其测试，`calc_limitation` 生产调用方为 0）；
   ② `law_as_of` 在 `create_run` 定值，早于任何文本理解，`LegalAgentState` 无该字段、
   writer/verifier 均看不到，改默认值 = 改"基准日何时不可变"；③ `verdict` 只有 4 值、
   非 PASS 即终态 FAILED，"追问"通道挂在 controller 的 `(issue_id, UnknownFact)` 锚点上，
   基准日没有锚点。**本批已落地的部分**：verifier 版本适用绊线（`law_version_tripwire_check`，
   默认关）拦"按 law_as_of 版本的法答分水岭前事实"，含不带年数 token 的引用型错答
   （numeric/citation 两门对此类均无感）；评测注入出口 `gate2_runner --cases-file` + `as_of_date`。
   **仍缺**：事实日抽取环节、无锚点澄清态、frozen 集加 fact_date（触 T0 冻结物，需 Owner 决策卡）。
```

- [ ] **Step 3: 交接书勘误 + 进度追加**

`docs/handoff-external-harness-20260918.md:112` 的 `evals/gate2_runner.py` 订正为 `backend/scripts/gate2_runner.py`（实测：`--cases-file` 在 `:309`，首轮 payload 原在 `:460-464`，`evals/` 下无此文件）。在 §4 末尾追加：

```markdown
5. **R15 绊线已落（2026-09-18 晚，接手会话）**：`limitation_calc.law_version_crosses_watershed`
   + `verifier` 门 + `service` 透传 + `gate2_runner` 的 `as_of_date` 出口 + 非冻结对照样本。
   开关 `law_version_tripwire_check` **默认关，开启属评测批预登记**（§2.2）。
   §2.3 默认行为未动（仅补 docstring 边界）。对照臂执行仍待 Owner 侧起服务。
```

- [ ] **Step 4: 提交（文档不入 pre-commit 关键路径，但照常跑）**

```bash
cd "C:/Users/33393/Desktop/ai-legal-helper" && git add backend/agent/repository.py docs/external-harness-plan-gap-analysis-20260918.md docs/handoff-external-harness-20260918.md && git diff --cached --name-only && git commit -m "docs(R15): repository 缺省边界留痕 + 执行书成本订正 + 交接书 runner 路径勘误"
```

---

## Task 6: 收口门禁（全绿才允许声称完成）

**Files:** 无新改动。

- [ ] **Step 1: 车道复核（防并行会话在途）**

Run: `cd "C:/Users/33393/Desktop/ai-legal-helper" && git log --oneline -3 && git status --short --untracked-files=no`
Expected: HEAD 含本批 5 个提交；工作树无**非本会话**修改。若出现外来修改 → 不 stage、不改、在报告里点名归属，并检查其是否与本批文件重叠（重叠即停手确认）。

- [ ] **Step 2: 门禁三绿**

Run: `cd "C:/Users/33393/Desktop/ai-legal-helper/backend" && ./venv/Scripts/python.exe -m ruff format --check . > ../_r15tripwire_final_fmt.txt 2>&1; echo "FMT_RC=$?"; ./venv/Scripts/python.exe -m ruff check . > ../_r15tripwire_final_ruff.txt 2>&1; echo "RUFF_RC=$?"; ./venv/Scripts/python.exe -m mypy . > ../_r15tripwire_final_mypy.txt 2>&1; echo "MYPY_RC=$?"`
Expected: 三个 RC 全 0。

- [ ] **Step 3: 全量 + lane 两份数字（与 Task 0 同树口径，差值须可解释）**

Run:
```bash
cd "C:/Users/33393/Desktop/ai-legal-helper/backend" && ./venv/Scripts/python.exe -m pytest -q -m "not slow" --basetemp="../_pt_r15tripwire_final" > "../_r15tripwire_final_full.txt" 2>&1; echo "PYTEST_RC=$?"
cd "C:/Users/33393/Desktop/ai-legal-helper/backend" && ./venv/Scripts/python.exe -m pytest tests/test_agent_verifier.py tests/test_phantom_check.py tests/test_limitation_calc.py tests/test_agent_chat_integration.py tests/test_agent_gate.py tests/test_gate2_runner.py tests/test_request_bootstrap.py tests/test_r15_version_tripwire.py tests/test_r15_runner_injection.py -q -m "not slow" --basetemp="../_pt_r15tripwire_lane_final" > "../_r15tripwire_final_lane.txt" 2>&1; echo "RC=$?"
```
Expected:
- **lane（主口径）**：`RC=0` 且 passed = `LANE_BASELINE` + **22**。
  精确表：`test_r15_version_tripwire.py` = 16（Task1 8 + Task2 8）、`test_r15_runner_injection.py` = 6
  （实施时比计划多 1 条：`test_watershed_fact_reveal_is_consumable_by_runner` —— 把"题集写了
  fact_reveal 但 runner 读不到"这类静默失效钉住）。
- **全量（辅助口径）**：passed = `DIRTY_BASELINE_PASSED` + **22**（且仍带 T-E 归属的那 4 红）。
- **对不上就停手查明**：先 `git log -1` 比对 Task 0 时点（对方中途提交 ⇒ 按 Task 0 Step 1 第 4 条重取基线），
  再逐文件 `git diff --stat` 归因。禁止用"差不多/环境抖动"收口。
- Task 3 的 probe 因 `_` 前缀**不进**默认收集 ⇒ **不得**计入差值（Step 4 单独跑）。

- [ ] **Step 4: probe 单独跑一遍（不进默认收集）**

Run: `cd "C:/Users/33393/Desktop/ai-legal-helper/backend" && ./venv/Scripts/python.exe -m pytest tests/_r15_tripwire_probe.py -q > ../_r15tripwire_final_probe.txt 2>&1; echo "RC=$?"`
Expected: `RC=0`，`1 passed`。

- [ ] **Step 5: 手动 pre-commit（钩子未装，必须显式）**

Run: `cd "C:/Users/33393/Desktop/ai-legal-helper" && backend/venv/Scripts/pre-commit.exe run --files backend/agent/limitation_calc.py backend/agent/verifier.py backend/agent/service.py backend/settings.py backend/scripts/gate2_runner.py backend/tests/test_r15_version_tripwire.py backend/tests/test_r15_runner_injection.py backend/tests/_r15_tripwire_probe.py backend/agent/repository.py > _r15tripwire_precommit.txt 2>&1; echo "PRECOMMIT_RC=$?"`
Expected: `PRECOMMIT_RC=0`。非 0 → 按输出修，修完**新建 commit**（不 amend）。

- [ ] **Step 6: 证据五连问（skill `show-your-work-new`）+ DoD 对照，逐条作答后才写报告**

1. **数字怎么来的**：`DIRTY_BASELINE_PASSED` / `LANE_BASELINE` → 最终各 +22，逐项对应到
   `test_r15_version_tripwire.py`(16) + `test_r15_runner_injection.py`(6)。
2. **能复现吗**：贴 Step 2/3/4/5 的命令与 RC；lane 命令是**一条可粘贴行**，不依赖手工顺序。
3. **亲眼红过吗**：`_r15tripwire_t1_red.txt`（ImportError）/ `_r15tripwire_t2_red.txt`
   （**必须是"放行了"那一红** + `render_verified` 那两条的 `AttributeError`/`assert None is not None`）/
   `_r15tripwire_t4_red.txt`（两种红因同时出现）。
4. **期望独立吗**：分水岭与年限取自 `limitation_calc.py:7-15` 的法条自述；题集契约取自
   `validate_cases.py:37-40,75` + `gate5_judge.py:93`（**不是我的实现**）；"拿 today 当基准必错"取自
   gap-analysis `:118`/`:137`。
5. **未说出的限制**：**必须写明五条**——① 开关默认关，生产零变化；② 对照臂未执行（需服务+付费），
   所以**没有任何端到端数字**；③ 无真实"追问"通道，命中即 FAILED 终态（与执行书语义偏离，Owner 已确认）；
   ④ 抽取环节与 frozen 集 fact_date 仍缺；⑤ **基线是脏树数**（对方 T-E 在途），"全量全绿"只在
   Task 0 Step 3 判定为 `PARTIAL` 时**不得**声称。

**DoD 对照（F5：防把"+21 passed"当目标）**：本批真正的交付判据是这三条，**不是** passed 数——
- (a) probe 证明"没有这道门就放行"⇒ 门是唯一拦截者（Task 3 Step 5）；
- (b) 开关**开**时：跨分水岭 draft 被 `LAW_VERSION_WATERSHED_MISMATCH` 拦、不跨的放行、
  且 `render_verified` 仍能出答案（Task 2）；
- (c) 对照臂真实数字 —— **本批不产出**（需 Owner 侧起服务 + 模型花费）。
"先立尺子再投入"这条纪律本批**未满足**（Owner 选 E1 证据级别 = 单测红绿 + probe）；报告里如实写
"尺子已备好未读数"，禁止写成"已建立评测基线"。

---

## 收口记录（2026-09-18 23:5x 实测，Task 0→6 全走完）

> 各步的 `[ ]` 未逐个打勾（避免 30 次无信息编辑）；**每一步的执行证据都在下面这张表里**。

### 提交链（全部本地未推送，父提交 `d4b8d79`）

| 提交 | 内容 | Task |
|---|---|---|
| `7d4b2da` | `law_version_crosses_watershed` 纯新增 + 8 测（未接线） | 1 |
| `247466b` | verifier 门 + 接线自检 + **基准日随 PASS 喂给 render_verified 二次验证（F1）** + 开关 + 8 测 | 2 |
| `cf35983` | service 透传 + probe 留痕 | 3 |
| `5aa9dbd` | `gate2_runner._round1_payload` + `--no-as-of-date` + 对照样本 + 6 测 | 4 |
| `63c5101` | `create_run` docstring 边界（代码一字未动） | 5 |
| `aaf088b` | **F8**：service 读 `AgentRun.law_as_of` 补 `cast` | 6 |

### 数字（差值逐项可解释）

- `LANE_BASELINE = 227` → 终 `LANE = 249`（RC=0）= **+22** = 我的 `test_r15_version_tripwire.py` 16 +
  `test_r15_runner_injection.py` 6。
- `DIRTY_BASELINE = 1240 passed / 4 failed` → 终全量 **`1266 passed / 0 failed / 18 deselected / RC=0`**
  （140.94s）= 1240 + **22**（本批）+ **4**（T-E 会话在途把 `test_query_understand.py` 迁到 `real_kb`，
  那 4 条自己转绿）。**两个口径的差值都对得上，无残差。**
- ⚠️ **收口时点口径升级（2026-09-18 23:5x 复测）**：T-E 已把那份改动提交为 `44210ef`（夹在我的
  `7d4b2da` 与 `63c5101` 之间），且 `git status --short -uno` **为空** ⇒ 上面那次全量
  **1266 / 0 failed 对应 HEAD `aaf088b` 的提交态**，不再是"脏树数字"。
  因此 Task 0 命名的 `DIRTY_BASELINE` 只对**基线那一次**成立；终值可直接引用，但**引用时要带上
  `44210ef` 也在树里**这个条件（对方再提交相邻文件即作废，按 §(d) 全绿有保质期）。
- 门禁：`ruff format --check .` RC=0、`ruff check .` RC=0、`mypy .` RC=0（71 files）；
  `pre-commit run --files <本批 9 文件>` **PRECOMMIT_RC=0**。
- probe：`tests/_r15_tripwire_probe.py` 单独跑 **1 passed**（默认收集不含它 ⇒ 未计入差值）。
- 题集 sha256：`evals/watershed-cases-r15.json` = `7cc61193e7cd53ce5cd4df7709438f52ef978feab4ce72fca489c3771c7ee346`。

### 变异/红因留痕（B3）

| 留痕 | 红因 |
|---|---|
| `_r15tripwire_t1_red.txt` | `ImportError: cannot import name 'law_version_crosses_watershed'`（RC=**2**，collection error，非计划写的 RC=1） |
| `_r15tripwire_t2_red.txt` | 1× `KeyError: 'law_version_tripwire_check'` + 6× `AttributeError`（monkeypatch 目标不存在）；**含"放行了"那一条** |
| `_r15tripwire_t2_mut_rv.txt` | 去掉 `render_verified` 的基准日透传 ⇒ **1 failed** `assert None is not None`（F1 看门狗有效） |
| `_r15tripwire_t2_mut_carry.txt` | 去掉 PASS 返回的携带 ⇒ **2 failed**（`assert None == date(2026,9,18)` + `assert None is not None`）⇒ 两半各自都是承重墙 |
| `_r15tripwire_t4_red.txt` / `_t4_mid.txt` | 4× `AttributeError: … no attribute '_round1_payload'` + 1× `FileNotFoundError`；中途 helper 绿后 schema 仍红 ⇒ 红因不互相掩盖 |

### 实施中新发现的 2 处（计划外，已一并处理）

- **F8**：`mypy agent/verifier.py` 单文件跑是绿的，**只有 `mypy .` 全仓才暴露**调用点类型错误——
  `models.py` 用 legacy `Column(Date)`，`saved_record.law_as_of` 静态类型是 `Column[date]`。
  修：`cast(date | None, …)`（镜像同文件 `:122` 对 `last_error_code` 的既有写法）+ 补 `from datetime import date`。
  **纪律**：本仓库改**调用点**必须跑 `mypy .`，单文件 mypy 只能证"我改的那个文件内部自洽"。
- 计划新增 1 条测试（`test_watershed_fact_reveal_is_consumable_by_runner`）：题集写了 `fact_reveal`
  ≠ runner 读得到，用 `_facts_from_case_set({}, cases)` 直接产出 4 个 fid 钉住命名协议。

### 限制（对外陈述时必须带上）

1. 开关 `law_version_tripwire_check` **默认关**，生产行为逐字不变；开启属评测批预登记（交接书 §2.2）。
2. ~~**对照臂未执行** ⇒ 本批没有任何端到端数字~~ → **已执行（2026-09-19 补做，见下《对照臂真实读数》节）**：
   臂 A 证明病在（agent 对 2019 事实按三年作答并交付），臂 B 证明药在（同一案例命中
   `LAW_VERSION_WATERSHED_MISMATCH`、零字交付，而 2023 案例仍正常交付）。
   **但两臂都只有 n=1，且开关是经 env 打开的（代码默认仍 False）** ⇒ 只能说"门在真实链路上会响"，
   不能说"评测基线已建立"（正式基线要冻结集 + 多案例 + 双集，属评测批）。
3. 无真实"追问"通道：命中即 `FAIL_SAFE` 终态 FAILED（与执行书"抽不到就追问"语义偏离，Owner 已确认）。
4. 事实日抽取环节、无锚点澄清态、frozen 集 `fact_date` 仍缺（触 T0 冻结物，需 Owner 决策卡）。
5. **service→verifier 这一跳没有独立透传锁测试**：兜底是 `LAW_TRIPWIRE_NOT_WIRED` 守卫本身——
   开关开而该跳丢参 ⇒ 每轮显式失败（响亮），不会静默放行。开关关时该跳无行为可丢。
   （交接书 §2.4 要求"每跳透传锁测试"，这一跳以守卫代替，属**有意偏离**，需 Owner 认可。）
6. `gate2_runner.py` 在 mypy exclude 内（`scripts/` 不参与类型检查，该文件有 4 个既有错误）
   ⇒ helper 无类型护栏，由 6 条契约测试代偿（F7）。
7. 两处文档订正（gap-analysis 成本+行号、交接书 §4 路径勘误+进度）**未提交**——
   `docs/` 在本仓长期未跟踪，交接书开头写明"是否入快照由 Owner 定" ⇒ 不擅自入。
   ⚠️ 代价：它们只活在当前工作树，**并行会话把树同步回提交态就会丢**（交接书 §5 事故 1 同款）。
8. 留痕文件 `_r15tripwire_t2_red.txt` 等含 `monkeypatch.setattr` 失败时 dump 的**整个 Settings 对象**
   （里面有 `.env` 的真实 key 值）。**这些 `_*` 日志一律不得 `git add`**；本批所有提交都是逐文件显式 add。

---

## 对照臂真实读数（2026-09-19 00:1x–00:4x 补做，Owner 指示「你来执行」）

> 这一节把上面限制 ② 「对照臂未执行」划掉：**三臂都跑了，用的是本机后台 uvicorn + LongCat 真实模型**。
> 产物：`dispatch-output/r15-watershed-20260918/`（`--out-dir` 隔离，**未写 release-evidence 真实树**）；
> 日志：`_r15tripwire_arm_off.txt` / `_arm_agent_off.txt` / `_arm_agent_on.txt` / `_server*.log`。

| 臂 | 服务端配置 | W01（2019 事实，注入基准日 2026-09-18） | W02（2023 事实，同基准日） |
|---|---|---|---|
| **臂 0（意外先跑）** | `.env` 无 `AGENT_ENABLED` ⇒ `main.py:1443` 把整段 agent 分支（含 `force_agent`）跳过 ⇒ **走的快车道** | 交付 738 字：「**三年**普通诉讼时效大概率已于 **2022年3月5日**前后届满」，引《民法典》192 条，**通篇无新旧法衔接说明** ⇒ 题集 `critical_failures[0]` **实测命中**；15.8s | 交付 689 字，同样按三年（其事实本就在民法典期内 ⇒ 无错） |
| **臂 A（病在）** | `AGENT_ENABLED=true`，绊线**关**（代码默认） | agent 全跑通：3 轮（2 澄清 + `verification` + `final`），`agent_completed=True`，1425 字；争点写「用户的起诉请求权是否已超过**三年**诉讼时效期间？」；法律依据清单**不含 188 条**（192/675/670/680 + 商业银行法 42） | 3 轮，2212 字，`agent_completed=True`，依据含 188 条；80.7s |
| **臂 B（药在）** | `AGENT_ENABLED=true` + `LAW_VERSION_TRIPWIRE_CHECK=true`（**运行时 env，代码默认值一字未改**） | **`errors=['LAW_VERSION_WATERSHED_MISMATCH']`、`final_chars=0`、未交付** ⇒ 绊线在真实模型输出上把跨分水岭作答拦下 | **仍正常交付 1339 字、`agent_completed=True`、无错误码** ⇒ 不是一律拦 |

**开关只经 env 打开这件事的自检**：`LAW_VERSION_TRIPWIRE_CHECK=true python -c "from settings import settings; …"`
→ `tripwire=True | phantom=False | agent_enabled=False`（没顺手把别的门一起开）。§2.2「开启属评测批
预登记，不是代码改动」按字面执行：仓库里 `settings.py` 仍是 `= False`（HEAD 复核 `git show HEAD:…` 命中 1 次）。

### 这一轮额外挖出来的 4 条（都有实测支撑）

1. 🔴 **覆盖缺口比"开关默认关"更实质**：版本门挂在 agent 的 verifier 上，**快车道没有任何版本判定**；
   而线上 `AGENT_ENABLED=False` ⇒ 今天用户实际命中的正是**没有保护**的那条路（臂 0 就是那条路的读数）。
   补法要么把版本判定下移到快车道共用真源，要么按 R15 计划推进 agent 流量——**属 Owner 决策，本批不动**。
2. ✅ 修掉一条我自己的不可归因：绊线命中时服务端日志只有 `verdict=FAIL_SAFE`，
   `agent_claim_checks` 是**空的**（我的 return 没传 `draft/state`）⇒ 提交 `5afc8d0` 补上，
   并加断言锁住。仍欠一条：**原因码本身不在 `coverage_gate_terminal_failure` 的字段里**，
   入日志需登记 observability 白名单，且该缺口对所有 claim 循环门共用 ⇒ **另开票，本批不扩面**。
3. ⚠️ 我这份对照样本还不能用：臂 B 的 W02 出现 `over2=True`（4 轮、`clar_rounds=3`、`unmatched=2`）
   ⇒ `fact_reveal` 的关键词对不上真实追问话术。评测批正式用之前**需要调题**（不是门的问题）。
   另记一条旁证：臂 A 的 W02 法律依据清单里出现**《海事诉讼特别程序法》99 条 + 《商业银行法》82 条**
   （纯民事借贷案）⇒ 跨部门法污染在 final 答案里实测存在，与 R1/R1b 相关，**归那条线，不在本批处置**。
4. 📌 环境事实订正：**常驻服务不必用户侧启动**——`Bash run_in_background` 起的 uvicorn 能在整轮评测里
   存活（本批三次起停、六次案例运行全部命中）。原先记的"沙盒会收割子进程"适用于**命令结束后的
   detach 子进程**，不适用于该机制。

### 收口数字（对照臂之后，HEAD `5afc8d0`）

- 全量 **1272 passed / 0 failed / 18 deselected**（164.91s）= 1266 + **6**
  （那 6 条来自并行会话新增的**未跟踪**文件 `backend/tests/test_chroma_dir_guard.py`，非本批；
  本批自身仍是 `test_r15_version_tripwire.py` 16 + `test_r15_runner_injection.py` 6 = **22**，
  `--collect-only` 实测 22）。
- `mypy .` RC=0（全仓，71 files）、`ruff check .` / `ruff format --check .` RC=0、
  `pre-commit`（verifier.py + 测试文件）RC=0。
- ⚠️ **索引污染实况**：收口时 `git status` 显示并行会话已把 `dispatch-output/over2-replay-20260919/*`
  **staged 进共享索引**。本批每枚提交都用显式路径 + `git diff --cached --name-only` 核对，
  `5afc8d0` 实测只含 2 个文件 ⇒ 未被裹进。**后续若还要提交，必须用
  `git commit -- <路径…>` 形式**（否则会把别人 staged 的东西一起提交）。

---

## 风险与回退

| 风险 | 触发信号 | 处置 |
|---|---|---|
| probe 显示别的门已覆盖 | Task 3 Step 5 打印非 PASS 的 reason_code | 停手上报，绊线价值重估（**不**改门去凑） |
| 并行会话改了 `verifier.py`/`limitation_calc.py` | mtime 落在本批编辑窗口之外且内容非本会话 hunk | 停手确认（交接书 §5 规则），不"顺手修"别人文件 |
| **T-E（chroma 隔离）中途提交** | `git log -1` 与 Task 0 时点不同 | 差值口径作废 ⇒ 重取 `DIRTY_BASELINE`/`LANE_BASELINE` 两个数，报告写清新旧（Task 0 Step 1 第 4 条） |
| **二次验证接线又丢**（F1 回归） | `test_render_verified_reveals_with_tripwire_on` 红在 `assert None is not None` | 说明有人改了 `render_verified`/`_result`/PASS 返回；按 Step 6b 四处逐字复原，**不**放开 `LAW_TRIPWIRE_NOT_WIRED` 守卫去"绕过" |
| helper 抽取扰动 runner | `test_gate2_runner.py` 红 | 回退 Task 4 Step 3-5（新建 revert commit，不 reset） |
| 全量差值对不上 | Task 6 Step 3 | 先 `git log -1` 比对基线时点，再逐文件 `git log -p` 归因，禁止用"环境抖动"收口 |
| 有人（含本会话）想把 `law_version_tripwire_check` 打开 | 出现在 diff 里的 `= True` 或 `.env` 改动 | **禁止**：交接书 §2.2「开启 = 评测批预登记事项」。开启须连同对照臂执行计划一起过 Owner |
