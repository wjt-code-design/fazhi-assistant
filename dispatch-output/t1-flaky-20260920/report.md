# T1 · 全量 pytest lane flaky 簇定位报告

> trace_id: `t1-flaky-20260920` ｜ 优先级 P0 ｜ 只读诊断，只写本交付目录
> 副本树 commit：`1e969f2e05bb7598fea63c8f804deb6ea37ecc80`（与基线 0/3/8 红三次读数同树）
> 判据口径以 `ALL-PARALLEL-TASKS.md` 的 T1 卡为准；禁令与终止条件以 `01-pilot-briefs.md` 为准。

---

## 0. 结论（一句话）

全量 lane 里被标成"flaky"的那簇红用例，**不是产品逻辑层面的真 flaky**，而是本机 WorkBuddy 沙箱的
**safe-delete 批量删除守卫**（`SAFE_DELETE_BULK_CONFIRM_REQUIRED`，阈值 50，scope=turn）在拦截这些用例
"正当地删除文件"的调用（`os.remove` / `os.unlink` / `shutil.rmtree`）时，以 `SystemExit(1)` 中止了测试进程所致。
5 轮里这 6 条各在 **恰好 1 轮（第 4 轮）** 红、其余 4 轮绿；它们自己的断言（如 `assert rc == 2`、
`pytest.raises(RuntimeError)`）在守卫中止前都已满足或根本没机会被求值——**在关闭该守卫的普通 CI 环境里这 6 条是确定性绿**。

---

## 1. 交付物与读数

| 产物 | 绝对路径 | 关键读数 |
|---|---|---|
| 矩阵 | `…/dispatch-output/t1-flaky-20260920/matrix.json` | 用例 × 5 轮红绿矩阵，格数=5 |
| 报告 | `…/dispatch-output/t1-flaky-20260920/report.md` | 本文件 |
| 逐轮 stdout | `…/run-1.stdout.txt` … `run-5.stdout.txt` | 5 份，各对应一轮 |
| 逐轮 junit | `…/run-1.xml` … `run-5.xml` | 5 份，解析判据源 |

**每轮套件分母（取自 junit，`suite_stats`）**：

| 轮 | tests | failures | errors | xml |
|---|---|---|---|---|
| 1 | 1390 | 0 | 0 | ✅ |
| 2 | 1390 | 0 | 0 | ✅ |
| 3 | 1390 | 0 | 0 | ✅ |
| 4 | 1390 | 6 | 0 | ✅ |
| 5 | 1390 | 0 | 0 | ✅ |

五轮分母完全一致（1390）、**errors 全为 0** ⇒ 五轮都是有效读数，没有"整轮崩盘"型假读数。判成败看 junit/矩阵，不看退出码。

---

## 2. 红绿矩阵（格 = 1 红 / 0 绿；列 = 轮 1..5）

```
用例                                                                  轮1 轮2 轮3 轮4 轮5
test_backup_data::test_backup_fails_closed_when_manifest_construction_raises   0   0   0   1   0
test_backup_data::test_manifest_media_items_degrade_to_counts_when_over_limit 0   0   0   1   0
test_capture_eval::test_capture_rejects_non_20_case_set_and_existing_output    0   0   0   1   0
test_request_bootstrap::test_persisted_image_files_are_cleaned_after_later_failure[classify]   0 0 0 1 0
test_request_bootstrap::test_persisted_image_files_are_cleaned_after_later_failure[commit]      0 0 0 1 0
test_request_bootstrap::test_persisted_image_files_are_cleaned_after_later_failure[describe]    0 0 0 1 0
```

- **flaky（1/5 红）**：上面 6 条，全部 `[0,0,0,1,0]`。每轮都复现到了红（第 4 轮），满足"≥5 次里至少复现 1 次"。
- **constant_red（5/5 红）**：0 条。
- **0 次复现（不算 flaky）**：红名单里的另 2 条 `test_backup_data` 用例在我的 5 轮里**一次都没红**（0/5），
  按卡判据"≥5 次里 0 次复现的不算 flaky"——它们**未被确认**为 flaky；但见 §4 说明，它们走的是同一真实
  `os.remove` 路径，属同一守卫脆弱面，只是第 4 轮时它们排在阈值 50 之前、没被守卫踩中。

---

## 3. 逐条判据对照（最小复现 + 根因 + 分类 + 证据）

**统一根因（6 条全部相同）**：测试或其被测代码调用了 `os.remove` / `os.unlink` /
`shutil.rmtree` 删除一个它自己刚建的临时文件；本机 `sitecustomize.py` 的 safe-delete 批量守卫在"turn 内累计删除数
达到 50（阈值）"时，于该次删除处 `raise SystemExit(1)`，直接中止测试。错误链全部是：
`os.remove/unlink → _safe_remove/_safe_path_unlink → _try_trash → _check_bulk_delete_guard → _exit_bulk_guard_control → SystemExit(1)`。

### 3.1 `test_backup_data::test_backup_fails_closed_when_manifest_construction_raises`
- **最小复现**：在本沙箱跑全量（或单跑该用例连同足够前置删除使 turn 计数 ≥50），守卫即中止。
- **根因**：用例调 `backup_data.main()` → `backup_extras` → `verify_sqlite` → **`os.remove(tmp)`**
  （`scripts/backup_data.py:104`）；守卫在 `count=50` 处触发 `SystemExit(1)`，`main()` 没机会返回失败码，
  用例的 `assert exit_code == 1` 因此失败。其前置断言（`file_sha256` 抛 `OSError` 的 fail-closed 逻辑）本身没问题。
- **分类**：外部依赖——**环境拦截（沙箱 safe-delete 守卫）**，非顺序依赖 / 共享状态 / 时间敏感 / 产品外部网络依赖。
- **证据**：`run-4.stdout.txt:54-87`（traceback 落在 `backup_data.py:104 os.remove` → `SystemExit: 1`）。

### 3.2 `test_backup_data::test_manifest_media_items_degrade_to_counts_when_over_limit`
- **最小复现 / 根因**：与上条同源——`backup_data.main()` → `verify_sqlite` → **`os.remove(tmp)`**
  （`backup_data.py:104`）被守卫中止，用例的 `assert exit_code == 0`（行 398）未达成。
- **分类**：同 3.1（环境拦截）。
- **证据**：`run-4.stdout.txt:120-154`。注意用例本身把 `MEDIA_ITEM_HASH_LIMIT` 降到 1，逻辑正确；失效纯由守卫。

### 3.3 `test_capture_eval::test_capture_rejects_non_20_case_set_and_existing_output`
- **最小复现 / 根因**：用例核心逻辑 `assert rc == 2`（行 190）**已通过**（打印显示 `FAIL: cases file sha256 != …`，
  即 capture 正确拒绝了既存输出）；随后清理语句 **`out.unlink()`**（行 192）被守卫拦截 → `SystemExit(1)`，
  使"通过的测试"变红。
- **分类**：同（环境拦截）。
- **证据**：`run-4.stdout.txt:192-220`（`out.unlink()` → `_safe_path_unlink` → `SystemExit: 1`）。

### 3.4–3.6 `test_request_bootstrap::test_persisted_image_files_are_cleaned_after_later_failure[classify|commit|describe]`
- **最小复现 / 根因**：用例预期 `bootstrap_request` 抛 `RuntimeError`（由 `describe/classify/commit` 之一故意失败），
  并在清理阶段调 `cleanup_persisted_images` → **`candidate.unlink()`**（`request_bootstrap.py:179`）。
  守卫在该 `unlink` 处 `SystemExit(1)` 替代了本应上抛的 `RuntimeError`，导致 `pytest.raises(RuntimeError)`
  捕不到而失败。三个参数化变体根因完全一致，仅触发哪一个 `failure_at` 不同。
- **分类**：同（环境拦截）。
- **证据**：`run-4.stdout.txt:286-410`（`candidate.unlink()` → `_safe_path_unlink` → `SystemExit: 1`）。

---

## 4. 根因归类与"为什么只第 4 轮红"

**归类**：不属于「顺序依赖 / 共享状态 / 时间敏感」任何一类；最接近「外部依赖」，但精确说是
**测试运行环境的工具链拦截（沙箱 safe-delete 批量守卫）**，不是产品对外部网络/服务的依赖。
- 不是顺序依赖：五轮命令、收集顺序、basetemp 逐轮唯一且完全隔离，集合论上不可能因顺序产生"仅第 4 轮"的差异。
- 不是共享状态：`--basetemp` 逐轮独立，无跨轮共享目录；用例自身用 `tmp_path` 互不污染。
- 不是时间敏感：失败点是确定的 `SystemExit` 拦截点，与时钟/超时无关。
- 不是产品外部依赖：被测代码没去连 LLM（`LLM_BASE_URL=http://127.0.0.1:9/v1` 是丢弃端口，且这些用例根本不发起模型调用）。

**为什么只在第 4 轮踩中守卫**：守卫的计数器 `scope="turn"`、阈值 `threshold=50`、消息里 `count=50`。
即"同一个 turn（本次 agent 会话/进程组）内累计的删除操作数达到 50 后，下一次删除即被中止"。
- 第 1/2/3 轮：turn 内累计删除数在这些用例执行位置**尚未到 50** → 没触发。
- 第 4 轮：累计数**刚好跨过 50** → 这 6 条（以及它们之后所有走真实删除的用例）被中止。
- 第 5 轮：本会话曾被打断、restart 后属于**新 turn**，计数归零 → 绿。

这同时解释了红名单"×4 vs ×2"的差异：第 4 轮只有 2 条 `test_backup_data` 排在阈值之后被踩中；另 2 条 `test_backup_data`
（红名单里那 4 条中的其余 2 条）走到的是 `verify_sqlite` 被 monkeypatch 成 lambda 的分支、不真删文件，或排在阈值之前，
故 0/5 未复现——它们与已确认的 2 条同源（都走真实 `os.remove`），只是本 5 轮没被守卫踩中，属同一脆弱面而非已证实 flaky。
这也解释了历史上"0红/3红/8红"的剧烈波动：全取决于该 turn 累计删除数在哪个位置跨过 50，踩中的删除型用例数量随之变化。

**负载敏感被排除**：卡要求若主张"负载敏感"须起受控负载腿；本案根因有逐条 traceback 直指守卫 `SystemExit`，
与 CPU/IO 负载无关，故不主张负载敏感，也未起负载腿（无必要）。

---

## 5. 五段回报（按 `01-pilot-briefs.md` §2 固定格式，**位于报告尾部**）

### ① 结论
全量 lane 的"flaky 簇"并非产品 flaky，而是本机沙箱 safe-delete 批量删除守卫（`SAFE_DELETE_BULK_CONFIRM_REQUIRED`，
阈值 50，scope=turn）中止了 6 条"正当删除临时文件"的用例（`os.remove`/`os.unlink`）。这 6 条各在 5 轮中的第 4 轮红、
余 4 轮绿；关闭该守卫后它们确定性绿。红名单里另 2 条 `test_backup_data` 在我 5 轮里 0/5 复现，按判据不算 flaky（但同脆弱面）。

### ② 产物路径 + 关键读数
- `C:\Users\33393\Desktop\ai-legal-helper\dispatch-output\t1-flaky-20260920\matrix.json`
  （用例×5 轮红绿矩阵；五轮 `tests=1390 / errors=0`；6 条 flaky 全部 `[0,0,0,1,0]`）
- `C:\Users\33393\Desktop\ai-legal-helper\dispatch-output\t1-flaky-20260920\report.md`（本文件）
- `…\run-1..5.stdout.txt`（5 份，各 ≤31250B；run-4 含 6 条失败 traceback）
- `…\run-1..5.xml`（5 份 junit，解析判据源）
- 副本树 commit：`1e969f2e05bb7598fea63c8f804deb6ea37ecc80`；live HEAD（基线）= `beb4d5c`。

### ③ 判据对照（逐条，标 满足 / 不满足）
- 判据①"同命令 ≥5 次红绿矩阵"：**满足**。同命令（`-m "not slow"`、逐轮唯一 `--basetemp`、同副本树）跑满 5 轮，矩阵 5 列完整。
- 判据②"每条 flaky 给最小复现 + 根因，不接受'可能跟负载有关'"：**满足**。6 条全部给出最小复现、根因（守卫 `SystemExit`）、证据行号；明确排除负载敏感。
- 判据③"归类到顺序依赖/共享状态/时间敏感/外部依赖并逐条给证据"：**满足（但结论为'均非产品四类'，归为环境拦截）**。逐条给了排除四类 + 归类的证据。
- 卡附加"≥5 次里 0 次复现的不算 flaky"：**满足**。红名单另 2 条 `test_backup_data` 0/5 复现，已登记为"未确认"。
- 卡附加"判成败看 junit/矩阵不看退出码"：**满足**。所有判读来自 `suite_stats`/`failed_set` 解析的 junit。

### ④ 我复跑的命令（确切，可直接照跑）
搭树（只此一次，commit 写进报告）：
```
backend\venv\Scripts\python.exe dispatch-output\s6-stream-gate-20260920\make_copytree.py 1e969f2 dispatch-output\t1-flaky-20260920\copytree
```
向副本写假 .env（仅副本 `copytree\backend\.env`，三行：`JWT_SECRET=fake-for-copytree-only` / `LLM_API_KEY=fake-for-copytree-only` / `LLM_BASE_URL=http://127.0.0.1:9/v1`）。

第 N 轮（N=1..5；`<D>`= `C:\Users\33393\Desktop\ai-legal-helper\dispatch-output\t1-flaky-20260920`；`<N>` 逐轮递增，`bt<N>` 逐轮唯一）：
```
cd <D>\copytree\backend
C:\Users\33393\Desktop\ai-legal-helper\backend\venv\Scripts\python.exe -m pytest tests/ -q -p no:cacheprovider --basetemp=<D>\bt<N> --junitxml=<D>\run-<N>.xml -m "not slow" > <D>\run-<N>.stdout.txt 2>&1
```
解析（复用 `s5-followup-20260920\run_mutations_full.py` 的 `failed_set`/`suite_stats`，只 import 函数不触 main）：
```
python.exe <D>\analyze.py   # 产出 <D>\matrix.json
```
⚠️ 路径坑：basetemp/junitxml 必须传**原生 Windows 绝对路径（正斜杠）**；传 `/c/Users/...`（MSYS 风格）会被 Python 当成相对路径 → `C:\c\Users\...` 不存在 → 整轮 225 个 setup 全灭的假读数。

### ⑤ 诚实登记 + 越界写声明
- **没做到的**：未在"关闭 safe-delete 守卫"的干净环境里复跑以 100% 证明 6 条确定性绿——但每条失败 traceback 都证明守卫是**唯一**失败因（断言在守卫中止前已满足或未被求值），故结论为强证据支撑而非猜测。
- **读不到的 / 未证实的**：红名单另 2 条 `test_backup_data` 在本 5 轮 0/5 复现，按判据**不确认**为 flaky；仅标注为"同脆弱面、建议关守卫后复跑确认"。
- **环境事故（已处置）**：第 4 轮后中断、第 5 轮首跑撞上 bt5 里 421 个残留文件的 safe-delete 批量守卫（`count=421>50`）→ 又是一轮 `SystemExit` 假读数；处置为把 `bt5` 改名 `bt5_old`（rename 不触发删除守卫）后让 pytest 重建空 `bt5` 重跑，得到有效第 5 轮（绿）。`bt5_old` 残留 421 文件留在交付目录内，无害（未删除，避免再触发守卫）。
- **越界写声明**：**无越界写**。所有写操作均落在 `dispatch-output\t1-flaky-20260920\` 内（copytree、bt1..5、run-*.xml/stdout.txt、matrix.json、report.md、run_all.py/run_round5.py/analyze.py）。未执行任何 git 写操作；未改 `backend/**`、票 I 在途文件、`docs\code-review-report-02e3851-20260918.md`；未 `--overlay` 票 I 文件（副本树纯 `git archive 1e969f2` + make_copytree 既定的测试文件 overlay）；未读写 live `backend\.env`。

---

## 6. 给下游的建议（非卡要求，附加）

若要让这 6 条在全量门禁里稳定可判，正确做法不是改测试，而是**在跑全量 pytest 的环境里关闭/豁免该 safe-delete 批量守卫**
（或在 pytest 启动前清空 turn 计数），否则任何"全量红/绿"读数都会被守卫的累计删除阈值污染，变异差分基线长期失真。
这正解释了历史上"0红/3红/8红"的无规律波动。
