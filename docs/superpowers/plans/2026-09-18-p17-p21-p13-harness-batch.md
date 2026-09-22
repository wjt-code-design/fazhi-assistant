# P1-7 / P2-1 / P1-3 收尾批次实施计划（2026-09-18 第二批）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不触碰任何生产语义的前提下，把交接文档 §8 遗留项中仍在授权边界内的三项收干净：「最多两轮 / over2」口径成文（P1-7）、scope 预算耗尽守卫补覆盖（P2-1）、测试假服务的传输层去重（P1-3）。

**Architecture:** 全部改动落在两个测试文件与三份文档。`gate2_runner.py` 与 `verifier.py` **一字不改**（判据冻结 / 改词表=改生产语义）。P1-3 抽出一个只拥有 HTTP 传输的基类，场景语义与应答改写留在子类；**本批零行为变化**（2026-09-18 执行期实测订正：两个 fixture 在 HEAD 上就已同时调用 `server.shutdown()` + `server.server_close()`，我早先记录的「harness 漏 `server_close()` ⇒ 每条测试泄一个监听 socket」不成立，已进 §13.3 失实台账）。

**Tech Stack:** Python 3.11 + pytest 9 + FastAPI 无关；`venv/Scripts/python.exe`（已实测存在）；ruff 0.16.1；pre-commit 4.6.1（可用但 `.git/hooks/pre-commit` **未安装** ⇒ 必须手动跑）。

> **执行状态（2026-09-18 收口）**：Task 1–6 全部执行完毕，下文 34 个步骤勾选框**未逐个回勾**（回勾 34 处会淹没真正有信息量的改动），
> 完成情况以证据为准：提交 `27d5363`（Task 2/3/4）+ `d4b8d79`（Task 5）落在 `02e3851` 之上，
> 门禁表见 `dispatch-output/ta5-arms-20260917/handover-20260918.md` §13.6，
> 五连问自审（含一次执行期新增的**边界变异**实验）见 §13.7，日志前缀 `_batch2_*`。

## Global Constraints

每条都是硬约束，逐字来自 Owner 指令 / 项目 `git.md` / 交接文档：

- **不改生产开关**：R1 / R1-OB / T-A6 / 修正性重试 / R11 / R12 / R15-lite / entity_precision_check / numeric_matching_v2 全部保持默认关。
- **判据冻结**：`CLARIFY_ROUND_LIMIT` 不得按结果修改（`gate2_runner.py:190`）。
- **暂缓推送与部署**：不 `git push` 直推；需要时走快照推送机制（`commit-tree` + 安全闸 + 先 `git ls-remote` 实测远端 tip）。
- **推送/交接前必须问是否跑 L3 深度安全审计**（security monitor 指令，不得沿用早前轮次的授权）。
- **不覆盖冻结资产**：`evals/probe-results.json`、`counterexamples.json`、各 `*-sessions.json`、P5 复核材料。
- **禁止 `git stash` / `reset --hard` / `clean`**；禁止 `-A` 全量暂存；只 `git add` 我自己的路径。
- **禁止顺手 `ruff format` 整个 `writer.py` 或全仓**。
- **提交前必须通过 pre-commit**（ruff + 尾空格 + EOF），本机钩子未装 ⇒ `pre-commit run --files <我的文件>` 手动跑。
- **新增慢任务才标 `@pytest.mark.slow`**；本批新测试不含 sleep，与现有 scripted 同档，**不标**。
- **禁止提交** `.env`、密钥、用户数据、`chroma_db/`、`*.db`。
- **并行会话纪律**：开工前/收工前各测一次 `git status --short` + 目标文件 **blob 比对**
  （`git hash-object <文件>` vs `git rev-parse HEAD:./<路径>`）。
  ⚠️ 原计划此处写的是"目标文件 mtime"，执行期证伪：探针还原文件会刷新 mtime，未提交的中途改动在历史里无痕，
  按 mtime 归因会把**自己**的改动记成别人的（见 §13.3 与 MEMORY `pre-commit钩子未装+工作树被并行会话改动`）。
  他人未提交改动**只登记不动**；他人文件导致的失败**不替他们修**。
- **换行符**：`test_gate2_runner.py` / `gate2_runner.py` / 三份 docs = 纯 LF（实测 0 CRLF）；`agent/verifier.py` = 501 CRLF、`tests/test_agent_verifier.py` = 848 CRLF ⇒ 任何字节级扰动脚本用 `read_bytes`/`write_bytes` + sha256 自证。

## 实测事实基座（写计划时逐项核过，执行时无需重查；若任一不符即为"环境已变"，停手）

| 事实 | 值 | 来源 |
|---|---|---|
| HEAD | `02e3851`（R12 归属改按争点） | `git log` 20:22 |
| 我的三个提交在链上未被改写 | `afd3138` / `777e332` / `62bde3e` | `git log` |
| HEAD 处全量 | **1236 passed / 18 deselected / exit 0 / 134.66s** | `_pytest_baseline_at_02e3851.log` |
| 当前 tracked 脏文件（他人会话，20:58） | `knowledge_service.py` `rag_chain.py` `tests/conftest.py` `tests/test_citation.py` | `git status --short` |
| `harness` fixture 测试数 | 10 条（`:160`–`:373`） | grep |
| `scripted` fixture 测试数 | 5 条（`:561`–`:658`）+ 1 条纯单测 `:517` | grep |
| scope 守卫位置 | `gate2_runner.py:496-498`（**文档写的 :483-485 是注释**） | Read |
| 判据位置 | `gate2_runner.py:569-571`；常量 `:184`/`:185`/`:190` | Read/Grep |
| 现有 scripted 脚本 | `_MIXED_SEQ`、`("clarify_once",)*50`、`("scope","scope","clarify_once")`、`("scope","clarify_once","final")`×2 | grep `set_script(` |
| 探针（红绿锁 4 个） | `_p11_watch_it_fail.py` `_p12_perturb.py` `_p15_watch_it_fail.py` `_p15_order_swap.py` | `ls _p1*.py` |
| `verifier.py` 术语优先分支仍在 | `:99-100` | grep（另一会话改过该文件，未碰此处） |
| `set_scene()` 调用点 | 11 处 ⇒ 方法名必须保留 | grep |
| 权威文档落点可用性 | 执行计划 §5 是 T-A5 判据表（P1–P5），**与"两轮"无关** ⇒ 不冲突，新增「派生⑩」追加节 | Read L257-266 |
| 任务书两处待注记 | `dispatch-tasks-20260908.md:103` 与 `:116` | Read |
| 本文件测试总数 | **18 条**（10 harness + 5 scripted + 1 纯单测 + 2 条不用这两个 fixture） | `grep -c "^def test_"` + 实跑 `18 passed` |
| `_p11_watch_it_fail.py` 的锚点 | **改的是测试文件本身**（`OLD_HOOK` 含 20/24 空格缩进与 `service._cursor`）⇒ P1-3 后必失配 | Read 该脚本 :30-35 |
| 覆盖率尺子 | **未打通**：`--cov=scripts/gate2_runner.py` 与 `--cov=gate2_runner` 两次均 `Module ... was never imported` / `No data was collected`（pytest-cov 与 coverage 7.15.2 本身可用） | 本会话实测 2 次 |

---

## File Structure

| 文件 | 跟踪 | 本批责任 | 动作 |
|---|---|---|---|
| `docs/execution-plan-entity-precision-20260917.md` | no | 「两轮/over2」权威正文（派生⑩） | 追加 |
| `docs/dispatch-tasks-20260908.md` | **YES** | 历史原句下方加带日期订正注记 | 改（不改写原句） |
| `backend/tests/test_gate2_runner.py` | YES | P2-1 新测试 + P1-3 基类抽取 | 改 |
| `dispatch-output/ta5-arms-20260917/handover-20260918.md` | no | §13 待裁决清单 / 安全告警核对 / 文档失实台账 | 追加 |
| `dispatch-output/ta5-arms-20260917/_p21_watch_it_fail.py` | no | P2-1 定向删守卫探针 | 新建 |
| `dispatch-output/ta5-arms-20260917/_batch2_*.log` | no | 本批门禁证据 | 新建 |

**不碰**：`docs/project-next-execution-plan-20260916.md`（§6 约定要求写它，但它与并行会话共享且当前非脏；本批把该义务记为 §13.5 待办，不冒险并发追加）。

---

## Task 1: 开工取证与双基线

**Files:**
- Create: `dispatch-output/ta5-arms-20260917/_batch2_baseline_20260918.log`
- Test: 无需测试；交付物是"可复跑的基线记录"

**Interfaces:**
- Produces: `BASELINE_DIRTY=<4 个他人文件>`、`BASELINE_FULL=<NNNN passed>`、目标文件 sha256 清单，供 Task 6 逐项比对。

- [ ] **Step 0: 把 HEAD 钉进每一份日志（教训「基线不冻结」）**

Run（repo root）:
```bash
git rev-parse --short HEAD | tee dispatch-output/ta5-arms-20260917/_batch2_head.txt
```
Expected: 记下 `HEAD_BEFORE`（本会话实测为 `02e3851`）。**每一份本批日志的第一行必须是当时的
HEAD 短号**——并行会话随时可能提交，没有这一行，后面所有"与基线一致"的比对都没有锚点。

- [ ] **Step 1: 复核环境事实基座**

Run（在 `backend/`）:
```bash
../backend/venv/Scripts/python.exe -c "import pathlib,hashlib;[print(p,hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()[:12],pathlib.Path(p).stat().st_mtime) for p in ['tests/test_gate2_runner.py','scripts/gate2_runner.py']]"
```
Expected: `scripts/gate2_runner.py` 与 `tests/test_gate2_runner.py` 的 sha/mtime；**gate2_runner.py 的 mtime 必须仍是 `a3ce07b` 时刻附近**（若变新 ⇒ 有人改了它，停手重估 P2-1 行号）。

- [ ] **Step 2: 登记他人未提交改动**

Run（在 repo root）: `git status --short | grep -v "^??" > /dev/null; git status --short | grep -v "^??"`
Expected: 4 行（`knowledge_service.py` / `rag_chain.py` / `tests/conftest.py` / `tests/test_citation.py`）。写进基线日志的 `BASELINE_OTHERS_DIRTY=`。

- [ ] **Step 3: 跑"当前树"全量基线（含他人改动）**

Run（在 `backend/`）:
```bash
../backend/venv/Scripts/python.exe -m pytest -m "not slow" -q --no-header -p no:cacheprovider \
  --basetemp=../_pt_batch2_base 2>&1 | tee ../dispatch-output/ta5-arms-20260917/_batch2_baseline_20260918.log
```
Expected: 末行 `N passed, 18 deselected`；退出码 0。**若 != 0 ⇒ 不开始本批**，先按 mtime 判定是他人改动所致还是既有 HEAD 问题（HEAD 已知是 1236 绿）。

- [ ] **Step 4: 跑两文件定向基线**

Run（在 `backend/`）:
```bash
../backend/venv/Scripts/python.exe -m pytest tests/test_gate2_runner.py tests/test_agent_verifier.py \
  -q --no-header -p no:cacheprovider --basetemp=../_pt_batch2_two
```
Expected: 记录条数（Task 5 之后要与之逐条相等）。追加进同一日志文件。

- [ ] **Step 5: 先取得"重构前 4 个探针全红"的对照（审核新增，缺它则 Task 5 无法归因）**

Run（在 `backend/`）:
```bash
for s in _p11_watch_it_fail _p12_perturb _p15_watch_it_fail _p15_order_swap; do
  echo "=== $s ==="; venv/Scripts/python.exe ../dispatch-output/ta5-arms-20260917/$s.py
done 2>&1 | tee ../dispatch-output/ta5-arms-20260917/_batch2_probes_before_p13.log
```
Expected: 四个都报 `一致=True` 且各自打出变红行。**为什么必须先跑**：P1-3 之后 `_p11_watch_it_fail.py`
的锚点会失配（它改的就是本测试文件，锚点含 20/24 空格缩进与 `service._cursor` 字样），届时它
`sys.exit(FATAL)` 而不是变红。有了这张"重构前全红"的对照，Task 5 才能把"探针不再红"区分成
**锚点漂移**（可修）还是**证明力被洗掉**（必须回退重构）。

---

## Task 2: P1-7「最多两轮 / over2」口径成文

**Files:**
- Modify: `docs/execution-plan-entity-precision-20260917.md`（文末追加「派生⑩」）
- Modify: `docs/dispatch-tasks-20260908.md:103`（原句下方插入订正注记，覆盖 `:116`）

**Interfaces:**
- Produces: 权威定义所在的**标题文本**「派生⑩」，Task 4 的 §13 与测试 docstring 都按这个标题指过去。

- [ ] **Step 1: 在执行计划文末追加派生⑩**

内容（逐字，追加在「派生⑨」之后；不改上文任何一行）:

```markdown
## 派生⑩ 「最多两轮 / over2」口径权威定义（2026-09-18，P1-7 收口）

**为什么要专门成文**：`docs/dispatch-tasks-20260908.md:103` 的协议原文「最多两轮；若两轮后仍出现
clarification 事件，记为红线候选（over2）」按字面读是**末尾快照**谓词。照这句改实现就会在分层预算下
漏标超限——实测 45 个序列漏 25 个（`gate2_runner.py:560-563`）。这类"照文档把代码改回去"的事故**已有
前科**：2026-09-17 那版 `fact_clar_seen >= FACT_CLARIFY_LIMIT and any(末尾澄清)` 谓词就是照这句话写出来的
（`:566-568` 留痕，2026-09-18 已裁决废弃）。

**权威口径（以本节为准）**：

| 项 | 口径 |
|---|---|
| 计什么 | **服务端发起的澄清请求次数** = `len(asked) + (末尾仍是澄清 ? 1 : 0)` |
| 谁占格 | scope 菜单与事实追问**同计**，不分轻重 |
| 红线 | 上式 > `CLARIFY_ROUND_LIMIT`(=2)，即**出现第 3 次追问**即红线 |
| 不是 | 「末尾是否仍为澄清」——超限轮次一旦被应答就从末尾消失，只看末尾会把它抹掉 |
| 判据 vs 预算 | `CLARIFY_ROUND_LIMIT` 是**判据（冻结）**；`FACT_CLARIFY_LIMIT` / `SCOPE_CLARIFY_LIMIT`
是**执行预算**。两者独立可调，**改预算不得改判据** |
| 实现 | `backend/scripts/gate2_runner.py:569-571`（判据）· `:184`/`:185`/`:190`（预算与判据常量） |
| 回归锁 | `backend/tests/test_gate2_runner.py:616` 该红时红 · `:640` 反例护栏 ·
P2-1 新增 `test_scope_budget_exhaustion_aborts_run_without_hanging` |

**本节不改写**：T-A5 冻结判据表（本文件 §5，P1–P5 与"两轮"无关）；`dispatch-tasks-20260908.md`
历史正文（只在其原句下方加带日期的订正注记并指向本节）。
```

- [ ] **Step 2: 在任务书 L103 下方插入订正注记**

`docs/dispatch-tasks-20260908.md` 的 `:103` 之后插入（缩进 5 空格以归入列表项 4 的续行）:

```markdown
     > ⚠️ **口径订正（2026-09-18，P1-7）**：本句字面读是"看末尾是否仍为澄清"，**现行权威口径不按末尾
     > 快照判定**，而是按**服务端发起的澄清次数**计（scope 菜单与事实追问同计，出现第 3 次追问即红线）。
     > 权威定义见 `docs/execution-plan-entity-precision-20260917.md` 派生⑩；实现见
     > `backend/scripts/gate2_runner.py:569-571`。本文件是 2026-09-08 的历史任务书，**原句不改写**；
     > 同文件 L116「最多两轮，无 over2」口径同此。
```

- [ ] **Step 3: 自证交叉引用可解析**

Run（repo root）:
```bash
python -c "
import pathlib,re
p=pathlib.Path('backend/scripts/gate2_runner.py').read_bytes().decode('utf-8').split('\n')
print('569:',p[568].strip()[:40]); print('571:',p[570].strip()[:40])
print('184:',p[183].strip()[:30]); print('190:',p[189].strip()[:30])
t=pathlib.Path('backend/tests/test_gate2_runner.py').read_bytes().decode('utf-8').split('\n')
print('616:',t[615].strip()[:60]); print('640:',t[639].strip()[:60])
"
```
Expected: 五个指针分别落在 `tail_clarification = ...` / `over_rounds = ...` / `FACT_CLARIFY_LIMIT = 2` / `CLARIFY_ROUND_LIMIT = 2` / 两个 `def test_redline_...` 上。**若不符 ⇒ 指针失实，改文档而不是改代码。**

- [ ] **Step 4: 复核订正没伤原句**

Run: `grep -n "若两轮后仍出现" docs/dispatch-tasks-20260908.md`
Expected: 恰好 1 命中（原句仍在），且其后紧跟我的注记。

---

## Task 3: P2-1 scope 预算耗尽守卫补覆盖

**Files:**
- Modify: `backend/tests/test_gate2_runner.py`（在 `:658` 的多 case 测试之后追加）
- Create: `dispatch-output/ta5-arms-20260917/_p21_watch_it_fail.py`

**Interfaces:**
- Consumes: `scripted` fixture、`_run_scripted()`、`_assert_attribution_clean()`、`runner.BY_ID`（均为既有）。
- Produces: 测试名 `test_scope_budget_exhaustion_aborts_run_without_hanging` —— Task 2 派生⑩的「回归锁」行、Task 5 的重跑对象都引用它。

- [ ] **Step 1: 写测试（期望直接绿，不是先红）**

```python
def test_scope_budget_exhaustion_aborts_run_without_hanging(scripted):
    """P2-1（2026-09-18）：服务端连发 3 次 scope 索要时，runner 必须停在 `scope_used` 守卫上。

    覆盖对象 = `gate2_runner.py:496-498`（守卫判据文字：`scope_used >= SCOPE_CLARIFY_LIMIT`；
    行号会随文件漂移，认这段文字为准）。既有 5 处 `set_script` 实参逐条枚举如下，**没有一条能
    走进这个守卫**：`_MIXED_SEQ=(scope,nomatch,clarify)`、`(clarify_once,)*50`、
    `(scope,scope,clarify_once)`、`(scope,clarify_once,final)`×2 —— 第 3 轮要么走 fact 分支要么
    已无澄清可发。此处"零覆盖"是**按脚本枚举推定**，不是覆盖工具实测：本环境 `--cov` 两次尝试
    均 `Module was never imported`（见 handover §13.3），故证明力完全来自下一条的删守卫实验。

    ⚠️ 本测试**不是缺陷复现**：守卫行为本来就对，写完直接跑就是绿的，"先红"在这里做不到，
    也不必假装做到。它的证明力全部来自**定向删守卫**
    （`dispatch-output/ta5-arms-20260917/_p21_watch_it_fail.py`）：删掉 :496-498 ⇒ 第 3 次
    scope 索要被应答掉 ⇒ `asked` 2→3、`agent_completed` False→True ⇒ 本测试变红。

    为什么只能 `break`、不能 `continue`：循环靠"发应答→取新事件"推进，不应答第 3 次索要时
    同一个 clarification 会原地转到无限。所以"scope 预算耗尽即终态退出"是唯一不自指的走法，
    代价是同时放弃了剩余的 fact 预算（本测试把该后果一并钉住，防止将来被"顺手优化"掉）。
    """
    tmp_path, service, _port = scripted
    service.set_script("C01", ("scope", "scope", "scope"))

    assert _run_scripted(scripted, "--case", "C01") == 0
    _assert_attribution_clean(service)
    sessions = json.loads((tmp_path / "gate2-run-t6-run-sessions.json").read_text(encoding="utf-8"))
    r = sessions["results"]["C01"]

    assert len(r["asked"]) == 2, f"scope 预算 2 格耗尽后第 3 次索要不应被应答；实际 asked={r['asked']}"
    assert r["agent_completed"] is False, "服务端停在 scope 索要上，没有终稿可声称完成"
    assert r["redline_candidate_over_2_rounds"] is True, "已应答 2 次 + 未应答 1 次 = 第 3 次追问 → 红线"
    assert len(service.chat_requests) == 3, "请求数上界 = 初始题 + 2 次 scope 应答；再多即守卫失效在空转"
```

- [ ] **Step 2: 跑，确认绿（且是"新分支真被走到"的绿）**

Run（在 `backend/`）:
```bash
../backend/venv/Scripts/python.exe -m pytest tests/test_gate2_runner.py::test_scope_budget_exhaustion_aborts_run_without_hanging -v --no-header -p no:cacheprovider --basetemp=../_pt_batch2_p21
```
Expected: `1 passed`。**若红**：逐条读断言，判定是我对守卫的理解错还是实现错——不许为了绿而放宽断言。

- [ ] **Step 3: 写删守卫探针**

`dispatch-output/ta5-arms-20260917/_p21_watch_it_fail.py`:

```python
"""P2-1 watch-it-fail：删掉 gate2_runner.py 的 scope 预算守卫，验证新测试变红。

守卫 = 那 3 行「if scope_used >= SCOPE_CLARIFY_LIMIT: / 注释 / break」。删掉后第 3 次 scope
索要会被应答掉 ⇒ asked 2→3、agent_completed False→True ⇒ test_scope_budget_exhaustion… 变红。
顺带跑一遍 scripted 全集，确认**只有新测试**受影响（若旧测试也变红，说明守卫并非只由新测试覆盖）。

字节级备份 + sha256 自证还原（教训 #2/#4）。gate2_runner.py 实测纯 LF。
"""

import hashlib
import subprocess
import sys
from pathlib import Path

TARGET = Path("scripts/gate2_runner.py")
GUARD = (
    "                if scope_used >= SCOPE_CLARIFY_LIMIT:\n"
    "                    # scope 预算耗尽仍被索要 → 终态退出（防御，防无界）\n"
    "                    break\n"
)

raw = TARGET.read_bytes()
text = raw.decode("utf-8")
guard = GUARD.replace("\n", "\r\n") if "\r\n" in text else GUARD
if text.count(guard) != 1:
    sys.exit(f"FATAL: 守卫命中 {text.count(guard)} 次（期望恰好 1），放弃扰动")
sha_before = hashlib.sha256(raw).hexdigest()
print(f"备份 sha256 = {sha_before}")

SELECTOR = "tests/test_gate2_runner.py"

try:
    TARGET.write_bytes(text.replace(guard, "", 1).encode("utf-8"))
    print("--- 已删 scope 守卫，跑 scripted 全集 ---")
    p = subprocess.run(
        [sys.executable, "-m", "pytest", SELECTOR, "-q", "--no-header", "-p", "no:cacheprovider", "--tb=line"],
        capture_output=True,
        text=True,
    )
    failed = [ln for ln in p.stdout.splitlines() if ln.startswith("FAILED") or "failed" in ln or "passed" in ln]
    for ln in failed:
        print("  " + ln.strip())
    hit = any("test_scope_budget_exhaustion_aborts_run_without_hanging" in ln for ln in failed)
    print(f"新测试是否在变红清单里 = {hit}")
    if not hit:
        sys.exit("FATAL: 删掉守卫后新测试没变红 ⇒ 该测试没有证明力")
finally:
    TARGET.write_bytes(raw)
    sha_after = hashlib.sha256(TARGET.read_bytes()).hexdigest()
    print(f"还原 sha256 = {sha_after}  一致={sha_after == sha_before}")
    if sha_after != sha_before:
        sys.exit("FATAL: 还原不一致，必须人工检查！")
```

- [ ] **Step 4: 跑探针，亲眼确认它红、且还原一致**

Run（在 `backend/`）:
```bash
../backend/venv/Scripts/python.exe ../dispatch-output/ta5-arms-20260917/_p21_watch_it_fail.py
```
Expected: `新测试是否在变红清单里 = True` + `一致=True`。日志存 `../dispatch-output/ta5-arms-20260917/_batch2_p21_watchitfail.log`。

- [ ] **Step 5: 复跑两文件确认还原后仍全绿**

Run: 同 Task 1 Step 4。Expected: 条数 = Task 1 Step 4 记录 + 1（新增那条）。

---

## Task 4: §13 留痕 + 提交 A

**Files:**
- Modify: `dispatch-output/ta5-arms-20260917/handover-20260918.md`（追加 §13）
- Stage: `backend/tests/test_gate2_runner.py`、`docs/dispatch-tasks-20260908.md`

**Interfaces:**
- Produces: `§13.1 待 Owner 裁决清单`（表格），后续汇报直接引用。

- [ ] **Step 1: 追加 §13（四小节，内容见下）**

- `§13.1 待 Owner 裁决清单`：一行一项，列 = 项 / 卡在哪条禁令（带文件:行）/ 需要 Owner 说什么 / 我手里的证据。必须覆盖：T-K（执行计划 `:269` 负面清单 + `:276-277`「不因新证据自动重开」+ `docs/handoff-takeover-20260918.md:110`。⚠️ 我原先记的 `execution-plan:246` 是**失实指针**，实测 `:246` 落在 T-H 段落）、P1-4 REWRITE（`agent/service.py:488`——原记 `:464-466` 已漂移）、P1-6 冻结评测集（⚠️⚠️ **本计划原先写的"原记的 `frozen-cases-v2.json` 与 `scope_trigger` 字段都不存在"是失实的**，
2026-09-18 收口后被 `evals/frozen-cases-v2.json` 的存在性正证推翻，完整订正见 handover §13.3⑥：该文件**已跟踪**、
`status=FROZEN`、20 个 case、E01–E10 带 bool `scope_trigger`，唯一消费者是 `evals/validate_cases.py:90-91` 的类型校验 ⇒
真卡点是"要不要把设计标记升格为验收判据"，不是"要先定义字段"）、词表收紧（误伤「绝对免责条款应当认定为无效」，
改词表=改生产语义）、T-H（付费）。**只列卡点，不预写方案**（grill 第 5 枝结论）。
- `§13.2 安全告警核对`：把"CORS `allow_origins=["*"]` at main.py:944"与"`settings.DEBUG` 绕过配额 at main.py:1025"两条与实测并排列出（实测：`:944` 是 `should_curate` 那行；CORS 在 `:266-272`，默认 `http://localhost:3000`；`grep -rn "settings\.DEBUG"` 全仓零命中）。结论写"未修，因为与当前 HEAD 不符；若告警来自另一棵树请 Owner 指认"。另附一条**明确标注未实测**的配置层观察：`CORS_ORIGINS=*` + `allow_credentials=True`(`:272`) 的组合风险。
- `§13.3 本批实测出的文档失实台账`：① `gate2_runner.py` 守卫行号（todo/交接记 :483-485 → 实 :496-498）；② `gap-analysis:184` "phantom_check 12 测试" vs 实测 collect **13**（`--collect-only -q`）；③ todo `:74` "`_ScriptedService` 整体重写既有 `_FakeGateService`" → 实测只有**传输层**重复，且其行号区间 `:382-470` vs `:39+` 也已漂移（实为 `:390-498` vs `:47-140`）；④ **我自己带进来的错**：早先记录「`harness` fixture 漏 `server_close()` ⇒ 10 条测试各泄漏一个监听 socket」——HEAD 实测 `:149-150` 两个都调，该缺陷不存在，P1-3 的价值只剩"传输层单点维护"，故本批重新定性为**零行为变化重构**。
- `§13.4 下一批候选`：P2-2（复核其余案例是否同被掩盖）；并写明"不折进本批"的理由是防跑偏。
- `§13.5 未做与原因`：P2-6 未跟踪噪音**只判不删**（`.ptmp-s4-run2/` 可能他人正在用）；`project-next-execution-plan-20260916.md` §7（§6 约定的义务）因并发写风险押后；P2-4 `ruff format writer.py` 属跨会话写冲突区，不动。

- [ ] **Step 2: 门禁（只跑我的文件）**

Run（在 `backend/`）:
```bash
../backend/venv/Scripts/python.exe -m ruff check tests/test_gate2_runner.py && \
../backend/venv/Scripts/python.exe -m ruff format --check tests/test_gate2_runner.py && \
../backend/venv/Scripts/python.exe -m pre_commit run --files \
  tests/test_gate2_runner.py ../docs/dispatch-tasks-20260908.md
```
Expected: `All checks passed!` / `1 file already formatted` / pre-commit 各 hook `Passed`。

- [ ] **Step 3: 全量门禁（双基线的"收工前"侧）**

同 Task 1 Step 3，日志 `_batch2_gate_a_20260918.log`。判据：**无新增失败项**，失败集与 `BASELINE_FULL` 一致。

- [ ] **Step 4: 提交 A**

```bash
git add backend/tests/test_gate2_runner.py docs/dispatch-tasks-20260908.md
git diff --cached --name-only   # 必须恰好这 2 个，多一个就停手
git commit -m "$(cat <<'EOF'
test(P2-1)+docs(P1-7): scope 预算耗尽守卫补覆盖 + 「两轮/over2」口径成文

- P2-1：新测试钉住 asked=2/未应答/agent_completed False/over2 四条后果，
  证明力来自删守卫探针 _p21_watch_it_fail.py（asked 2→3、completed False→True 变红）
- P1-7：任务书 L103 按字面读是"末尾快照"谓词，正是 2026-09-17 放宽闸的来源；
  原句不改写，加带日期订正注记并指向执行计划派生⑩
EOF
)"
```
Expected: 1 file changed + 1 file changed；`git status --short` 里他人 4 个脏文件**仍在且未被暂存**。

---

## Task 5: P1-3 抽传输层基类（零行为变化）

**Files:**
- Modify: `backend/tests/test_gate2_runner.py:47-149`（`_FakeGateService` + `harness` fixture）、`:390-508`（`_ScriptedService` + `scripted` fixture）

**Interfaces:**
- Consumes: 模块级既有常量 `_RUN_ID_PLACEHOLDER`、`INITIAL_OK_FINAL_SSE`、`CLARIFY_SSE`、`SCOPE_CLARIFY_SSE`、`NOMATCH_CLARIFY_SSE`、`runner.BY_ID`。
- Produces: 基类 `_SseTestServer`（`_record()` / `handle_chat(handler, payload)` / `start()`）+ fixture 工厂 `_serve(tmp_path, monkeypatch, cls)`；对外 API 不变：`set_scene()`、`set_script()`、`_resolve_case()`、`run_id_for()`、`chat_requests`、`unattributed`、两个 fixture 名。

**硬约束（撞 1 的结论，违反即"行为保持"变假）**：基类**只能拥有传输**。run_id 改写（`_reply`）与场景分派必须留在子类——否则 `_FakeGateService` 的 10 条测试会突然收到带改写 run_id 的响应，resume 归属行为被这次重构悄悄改掉。

- [ ] **Step 1: 插入基类（放在 `_RUN_ID_PLACEHOLDER` 之后、`_FakeGateService` 之前）**

```python
class _SseTestServer:
    """两个假服务的共同部分：SSE 传输、login 分支、请求记账、起停服务。

    ⚠️ 只拥有**传输**，不拥有**语义**：`handle_chat()` 的场景分派与应答内容留在子类。
    关键原因是 `_ScriptedService` 会按 case 改写响应里的 run_id，而 `_FakeGateService`
    不会——若把这层改写提到基类，那 10 条 harness 测试的 resume 归属行为就会被这次
    "行为保持型重构"改掉。

    `_lock` 用 RLock：子类需要在同一把锁里既记账又推进游标（旧代码正是这么做的），
    而 `_record()` 自身也要持锁，普通 `Lock` 会在嵌套处自锁。
    """

    def __init__(self) -> None:
        self.chat_requests: list[dict] = []
        self._lock = threading.RLock()

    def _record(self, payload: dict) -> None:
        with self._lock:
            self.chat_requests.append(dict(payload))

    def handle_chat(self, handler: BaseHTTPRequestHandler, payload: dict) -> None:
        raise NotImplementedError

    def start(self) -> ThreadingHTTPServer:
        service = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):  # 静默
                pass

            def _send_sse(self, body: str) -> None:
                data = body.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_POST(self):  # noqa: N802
                length = int(self.headers.get("Content-Length", 0))
                if self.path == "/api/auth/login":
                    # login 必须是 JSON：runner 只取 token，给 SSE 会让它直接失败。
                    self.rfile.read(length)
                    body = b'{"token": "test-token"}'
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                    return
                if self.path != "/api/chat":
                    self.send_error(404)
                    return
                payload = json.loads(self.rfile.read(length) or b"{}")
                service.handle_chat(self, payload)

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        return server


def _serve(tmp_path, monkeypatch, cls):
    """两个 fixture 的共同装配：换 EVID 目录 → 起假服务 → 收尾。

    收尾两个调用缺一不可，且**不是本次新增的**：旧的两个 fixture 在 HEAD 上就已同时调
    `shutdown()` + `server_close()`（实测 `:149-150`、`:507-508`）。`shutdown()` 只停
    `serve_forever`，`server_close()` 才关监听 socket；这里只是把两份拷贝收成一份。
    """
    monkeypatch.setattr(runner, "EVID", tmp_path)
    service = cls()
    server = service.start()
    try:
        yield tmp_path, service, server.server_port
    finally:
        server.shutdown()
        server.server_close()
```

- [ ] **Step 2: `_FakeGateService` 改为继承（只留语义）**

```python
class _FakeGateService(_SseTestServer):
    """可控假 HTTP 服务：按 case 注入**单一**场景；记录全部 chat 请求。"""

    def __init__(self) -> None:
        super().__init__()
        self.initial_scene: dict[str, str] = {}  # case_id → scene

    def set_scene(self, case_id: str, scene: str) -> None:
        self.initial_scene[case_id] = scene

    def handle_chat(self, handler: BaseHTTPRequestHandler, payload: dict) -> None:
        self._record(payload)
        content = str(payload.get("content", ""))
        case_id = next((cid for cid, c in runner.BY_ID.items() if c["initial_question"] == content), None)
        scene = self.initial_scene.get(case_id, "final")
        if scene == "http_500":
            body = b'{"detail": "internal error"}'
            handler.send_response(500)
            handler.send_header("Content-Length", str(len(body)))
            handler.send_header("Content-Type", "application/json")
            handler.end_headers()
            handler.wfile.write(body)
            return
        if scene == "timeout":
            handler.close_connection = True  # 不响应直接断开 → 客户端 OSError
            return
        if scene == "hang":
            import time as _time

            _time.sleep(15)  # 挂起：模拟长请求，供"中途 kill 进程"测试窗口
            handler._send_sse(INITIAL_OK_FINAL_SSE)
            return
        if scene == "non_sse":
            body = b"plain text, not an SSE stream"
            handler.send_response(200)
            handler.send_header("Content-Length", str(len(body)))
            handler.end_headers()
            handler.wfile.write(body)
            return
        if scene == "clarify_once":
            handler._send_sse(CLARIFY_SSE)
            return
        if scene == "scope":
            handler._send_sse(SCOPE_CLARIFY_SSE)
            return
        handler._send_sse(INITIAL_OK_FINAL_SSE)
```

行为保持论证（写进类 docstring 末尾一行）：旧代码在 login 分支先 `_send_sse("SYNC")`，但该 `Handler.do_POST` 随后被包裹层重写、login 提前返回 ⇒ 那行**从未生效**，删除属行为保持；404 与"未记账"的先后次序两版一致。

- [ ] **Step 3: 两个 fixture 收敛**

```python
@pytest.fixture
def harness(tmp_path, monkeypatch):
    yield from _serve(tmp_path, monkeypatch, _FakeGateService)
```
（原 `harness` 整体替换；`scripted` 同理换成 `_serve(..., _ScriptedService)`。）

- [ ] **Step 4: `_ScriptedService` 改为继承 + 实现 `handle_chat`**

```python
class _ScriptedService(_SseTestServer):
    """按"每 case 一串脚本化响应"返回：逐次 chat 请求消费下一条。"""

    # resume 请求的归属真源：run_id 由 case_id 唯一决定，于是"这个请求属于哪个 case"
    # 是**请求自身的纯函数**，不依赖任何跨请求状态。
    _RUN_ID_PREFIX = "gate2-run-"

    def __init__(self) -> None:
        super().__init__()
        self.script: dict[str, list[str]] = {}
        self._cursor: dict[str, int] = {}
        # 归不上 case 的请求在此记账并被显式断言之。P1-1 之前这里回退成"猜最近一个 case"
        # （`_last_case`），会把无主请求挂到别的 case 上、静默消费它的脚本游标。
        self.unattributed: list[dict] = []

    def set_script(self, case_id: str, scenes: tuple[str, ...]) -> None:
        self.script[case_id] = list(scenes)

    @classmethod
    def run_id_for(cls, case_id: str) -> str:
        return f"{cls._RUN_ID_PREFIX}{case_id}"

    def _resolve_case(self, content: str, agent_run_id: object) -> str | None:
        """把一次 /api/chat 归属到 case：初始题按文本，resume 按 run_id。归不上返回 None。"""
        for cid, case in runner.BY_ID.items():
            if case["initial_question"] == content:
                return cid
        run_id = str(agent_run_id or "")
        if run_id.startswith(self._RUN_ID_PREFIX):
            cid = run_id[len(self._RUN_ID_PREFIX) :]
            if cid in runner.BY_ID:
                return cid
        self.unattributed.append({"content": content, "agent_run_id": agent_run_id})
        return None

    def handle_chat(self, handler: BaseHTTPRequestHandler, payload: dict) -> None:
        with self._lock:
            self._record(payload)
            case_id = self._resolve_case(str(payload.get("content", "")), payload.get("agent_run_id"))
            seq = self.script.get(case_id, ["final"]) if case_id else ["final"]
            idx = self._cursor.get(case_id, 0) if case_id else 0
            # 脚本耗尽后默认 final（正常收敛）；需要"永不 finalize"的场景在脚本里显式写满
            scene = seq[idx] if idx < len(seq) else "final"
            if case_id:
                self._cursor[case_id] = idx + 1
        # 归属成功的 case 才有唯一 run_id；归不上时保留占位符，让下次同样归属失败并被记账。
        run_id = self.run_id_for(case_id) if case_id else _RUN_ID_PLACEHOLDER

        def _reply(body: str) -> None:
            handler._send_sse(body.replace(_RUN_ID_PLACEHOLDER, run_id))

        if scene == "scope":
            _reply(SCOPE_CLARIFY_SSE)
            return
        if scene == "clarify_once":
            # 事实澄清：prompt 命中 C01-r1-f1 关键词「内网」
            _reply(CLARIFY_SSE)
            return
        if scene == "nomatch_prompt":
            # 关键词不命中的事实追问 → runner 只能回 NO_MATCH_REPLY
            _reply(NOMATCH_CLARIFY_SSE)
            return
        if scene == "final_never":
            # 服务端永不 finalize（持续索要澄清）：runner 必须有限步退出，不得挂死
            _reply(CLARIFY_SSE)
            return
        _reply(INITIAL_OK_FINAL_SSE)
```

- [ ] **Step 5: 定向跑两文件，条数必须与基线一致**

Run: 同 Task 1 Step 4。Expected: **`18 passed`（Task 3 后为 19）0 failed**，且条数与 Task 3 Step 5
记录逐字相等。（18 是本文件实测总数：10 harness + 5 scripted + 1 纯单测 + 2 条不用这两个 fixture。）

- [ ] **Step 6: 单独盯"会因 teardown 改动而受伤"的失败路径测试**

Run（在 `backend/`）:
```bash
../backend/venv/Scripts/python.exe -m pytest tests/test_gate2_runner.py \
  -k "kill or timeout or http_error or non_sse or scope_clarification" -v --no-header \
  -p no:cacheprovider --basetemp=../_pt_batch2_paths 2>&1 | tee ../dispatch-output/ta5-arms-20260917/_batch2_p13_failure_paths.log
```
Expected: 全 `PASSED`，且日志里**没有** `Exception in thread` / `BrokenPipeError` traceback。（本批零行为变化，这一步不是"看修复的代价"，而是盯"基类改写有没有把 `timeout`/`hang` 这类不响应的路径搞出新异常"——这些路径正是最先被传输层重构碰到的。）

- [ ] **Step 7: 证明 AST 层面"语义只减不改"**

Run（在 `backend/`）:
```bash
../backend/venv/Scripts/python.exe -c "
import ast,pathlib
t=ast.parse(pathlib.Path('tests/test_gate2_runner.py').read_bytes().decode())
fns=sorted(n.name for n in ast.walk(t) if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)))
cls=sorted(n.name for n in ast.walk(t) if isinstance(n,ast.ClassDef))
print('classes',cls); print('n_funcs',len(fns)); print(fns)
"
```
Expected: `classes` 含 `_SseTestServer`（新）且 `_FakeGateService` / `_ScriptedService` 仍在；函数总数 = 基线 + 3（`_serve`、`handle_chat`×2）− 2（两个被合并的 `start`/嵌套 `do_POST`）。**以实际输出为准记录，不预设必中数字**——若对不上就逐条 diff 名字集合。

- [ ] **Step 8: 复跑探针（本批重构的主证据），并处理已知的锚点漂移**

8a. 先跑**不依赖测试文件锚点**的四个：`_p12_perturb` `_p15_watch_it_fail` `_p15_order_swap` `_p21_watch_it_fail`。

Run（在 `backend/`）:
```bash
for s in _p12_perturb _p15_watch_it_fail _p15_order_swap _p21_watch_it_fail; do
  echo "=== $s ==="; venv/Scripts/python.exe ../dispatch-output/ta5-arms-20260917/$s.py
done 2>&1 | tee ../dispatch-output/ta5-arms-20260917/_batch2_probes_after_p13.log
```
Expected: 四个都 `一致=True` 且各自变红行仍在（对照 Task 1 Step 5 的"重构前全红"）。**任一由红转绿 ⇒ 重构洗掉了证明力，立即回退 Step 1–4**（红与 FATAL 要分清：FATAL=锚点漂移，绿=真损失）。

8b. 再单独处理 `_p11_watch_it_fail.py`：它的 `OLD_HOOK` 锚点写的是重构前的
`                    if case_id:` / `service._cursor`（20/24 空格 + `service.` 前缀），基类抽取后
`handle_chat` 里是 12/16 空格 + `self.` ⇒ **预期它 FATAL（拒绝扰动）而非变红**。按计划把这三处
锚点平移到新形状（只改锚点字符串，不改实验语义），复跑后必须回到"仅顺序无关单测变红、端到端仍绿"。
把"锚点为何改动"写进 commit B 的信息与 §13.3，别让将来的读者以为实验被弱化过。

- [ ] **Step 9: 门禁 + 全量**

Step 9a: `ruff check` + `ruff format --check` + `pre_commit run --files tests/test_gate2_runner.py`（同 Task 4 Step 2 的形式）。
Step 9b: 全量同 Task 1 Step 3，日志 `_batch2_gate_b_20260918.log`。Expected 与 `BASELINE_FULL` 无新增失败。

- [ ] **Step 10: 提交 B**

```bash
git add backend/tests/test_gate2_runner.py
git diff --cached --name-only   # 必须恰好 1 个
git commit -m "$(cat <<'EOF'
refactor(test harness): 假服务抽传输层基类（零行为变化）

两个类真正重复的只有 HTTP 传输（_send_sse / login 分支 / 起停服务），场景词表、脚本
游标与 run_id 归属改写刻意留在子类——把它们合并会改掉 10 条 harness 测试的 resume 行为。
本提交不修任何缺陷（早先记录的 harness socket 泄漏经 HEAD 实测不存在），只把两份传输
拷贝收成一处。

行为保持的证据不是"全量绿"（重构天生给不出 watch-it-fail），而是 5 个扰动探针复跑仍变红
+ 失败路径用例逐条盯 stderr 无新增异常。
EOF
)"
```

---

## Task 6: 收口验证与汇报

- [ ] **Step 1: 工作树与归属复核** — `git status --short | grep -v "^??"` 必须只剩他人那 4 个（或他们已提交 ⇒ 记录新状态）；`git log --oneline -4` 应见 A、B 两提交在 `02e3851` 之上。
- [ ] **Step 2: 最终全量** — 同 Task 1 Step 3，日志 `_batch2_final_20260918.log`。**汇报时必须带这条限制**：全量含他人未提交的 `tests/conftest.py` 改动 ⇒ 不是纯 HEAD 基线。
- [ ] **Step 3: 清理自己的临时 basetemp** — 只删本批创建的 `../_pt_batch2_*`（自己造的噪音自己收），他人目录一律不碰。
- [ ] **Step 4: 派生⑩的回归锁指针复核** — Task 2 Step 3 的脚本再跑一次（新增测试名已进表，行号需实测）。
- [ ] **Step 5: show-your-work 五连问自审** — 数字怎么来 / 能否复现 / 测试亲眼红过吗 / 期望独立吗 / 已知限制。逐条对着日志回答，答不出的降级为"未验证"。

## 明确不做（防跑偏清单）

- 不改 `gate2_runner.py`（含把 scope 守卫改 `continue`）、不改 `verifier.py`、不改 `service.py`、不改 `main.py`。
- 不删任何未跟踪文件（除我自己本批造的 basetemp）。
- 不推送、不部署、不开 T-K/T-H 的代码。
- 不写 `docs/project-next-execution-plan-20260916.md`（押后，§13.5 留痕）。

---

## 审核结论 · vet-plan 五问（2026-09-18，写完计划后跑的一遍）

**1 模块边界**：基类的接缝开在"传输 vs 语义"，是被动继承既有分叉，不是新造的缝。`handle_chat(handler, payload)`
把裸 handler 交给子类 ⇒ 接口偏浅（子类仍要知道 `send_response/wfile/close_connection`）。
**评估过更深的接口**（`_respond(status, body, headers)` + `_abort()`）后**故意不用**：`timeout` 场景靠
`close_connection=True` 且**不产生响应**、`hang` 靠响应前 sleep 15s，抽象这两个语义就是在本批唯一
不可回退的地方制造行为漂移风险。结论记在这儿，免得将来有人以为"深度接口"是漏做了。

**2 更优解（对比过并各自否决）**：
- *合并成单一服务类*（把失败场景搬进 `_ScriptedService`）：**被游标语义击穿** —— 失败路径用例在第二次
  请求时会推进游标，`timeout`/`hang` 这类"每次都该同行为"的桩会退化成"只有第一次对"，10 条测试的
  语义被换掉。
- *维持现状、不去重*（原写的是"只补 `server_close()`、不去重"——实测两处 fixture 早已都调，这个"最小方案"因此**自动失效**）：去掉那条虚假收益后，Task 5 只剩"传输层单点维护"的可维护性收益，无可测量缺陷支撑。若 Owner 认为不划算，**砍掉 Task 5 不影响 P1-7 / P2-1 的交付**——这是实测把决策重新摆回台面的地方。

**3 会被哪条历史教训击穿 —— 击中 3 条，已就地改计划**：
- *[PL#13] 多份拷贝*：Task 1 Step 5 补"重构前 4 探针全红"对照，否则探针失配时无法区分锚点漂移与证明力丢失。
- *[fz] 基线不冻结*：Task 1 Step 0 把 HEAD 钉进每份日志；并行会话随时可能提交。
- *[PL#14] 假接线/幽灵标注*：P2-1 的"零覆盖"原写作覆盖级事实，实为**脚本枚举推定**（覆盖工具两次尝试失败，
  命令与告警已实测记录）⇒ 测试 docstring 与 §13.3 均改为如实措辞，并把锚点从行号改成判据文字。

**4 事实可查**：全部行号/计数来自本会话 grep/Read/实跑；计划内被审核**改错**的两处是「15 条」→**18 条**
（实测 `18 passed`）、探针数「4」→ 明确哪 4 个不依赖测试文件锚点。`gate2_runner.py` 的 mtime 与 sha 由
Task 1 Step 1 现测，不引用记忆。

**5 DoD（可测）**：P1-7 = 5 个文档指针逐行可解析 + 原句 grep 恰好 1 命中；P2-1 = 19 passed 且删守卫探针
变红（`asked` 2→3、`completed` False→True）；P1-3 = 两文件条数逐字相等 + 4 探针仍红 + 失败路径 stderr 无新
异常 + AST 类名集合含且仅含新增 `_SseTestServer`；批 = 全量无新增失败（**限制：含他人未提交的 conftest.py**）。

**代理目标自查**：本批真正测的是"评测 harness 的判据输入可信"，不是"测试条数"。P2-1 若只断言"没挂死"就退化成
容易测的代理——所以钉的是 4 条**后果**（应答几次、是否完成、是否红线、请求数上界），它们共同构成
"判据输入未被守卫破坏"的直接证据。P1-3 的"全量绿"是**弱代理**，故另加 4 探针复跑作为强证据。
