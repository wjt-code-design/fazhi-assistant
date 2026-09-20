# 票 H · 合同出口的写缓存闸与降级注记（E5/E6 三格 + 新增 E15）

**开工基线**：`2693745`（含 `1c05599` 为祖先）→ **本票提交**：`3f3bf0f`（+ 取证补正提交见文末）
**票面**：`docs/handoff-gap-tickets-h-i-j-20260920.md` §票 H
**执行范围**：`stream()` 分支0.3 合同报告那一个 `if answer:` 块 + 它的注记帧出口。别的一律没动。

---

## P0 边界自查

```
P0 边界自查：开关默认值=保持 False（preflight 生效值读数 false）  agent/=未动（git status 为空）
            evals/=未动（仅一条本会话之前就存在的 ?? 残留，未触碰）
            gate2_runner sha=ae2e412059ed68ac1514c62727cee61c50b8a2d6fe7e38a77c7e05631847e295 ✓
HEAD=2693745（开工时）  开工前脏项=无（三棵树 porcelain 全空）
```

六条自查读数（§0.5.1）逐条落盘：`00-pre-flight.json`。
⚠️ 一处**副作用**已还原：`preflight_p9.py` 会就地重写它自己的 `00-pre-flight-readings.json`
（只差一个行尾换行）⇒ 已 `git checkout --` 还原，本票不带该文件。

---

## H-1 写缓存闸（已交付）

**改法**（`backend/main.py` 分支0.3）：

```
- if cache_key:
+ degraded = use_router and flag_degraded
+ if cache_key and not bad and not degraded:
      answer_cache.put(cache_key, answer, pre["sources"], model="contract_review")
```

`bad = citation_verify(answer)` 本来就在**上一行**算好（判定是既有的，没新造规则）；
`degraded` 是 H-2 的同源信号。**短路保护**：`flag_degraded` 只在 `use_router and not use_light`
那一支被赋过值（合同分支里 `use_router` 为真 ⇒ `use_light` 已被强制 False ⇒ 该支必已执行），
而合同分支在 `use_router` 为假时同样会走到 ⇒ 直接读裸名会 `NameError`。

**先红**（`01-red-before.stdout.txt`，红因原文）：

```
>       assert sink == [], f"引用未收录的合同报告进了缓存：{sink}"
E       AssertionError: 引用未收录的合同报告进了缓存：[{'key': 'dd3d4f9d…', 'answer': '【风险评估】第一条…',
        'sources': [...], 'model': 'contract_review'}]
```

红在**功能缺失**（缓存里确实躺了一条带未收录引用的报告），不是 TypeError/笔误。

**控制腿**：`test_control_good_report_is_still_cached_once` —— `bad` 为空时**必须**仍写一次，
且写进去的就是不带注记的报告正文（`sink[0]["answer"] == CONTRACT_ANSWER`）。
没有这条腿，「把特性改没了却报成修好了」也能全绿。

**代价（一起登记）**：带告警的报告从此不进缓存 ⇒ 同一份合同重问会重烧 token。
若 Owner 不接受，替代方案是「照写，但把注记一并写进被缓存的那份」——那要改缓存条目语义，须另裁。
（该结论已写进登记表 E5×写缓存闸 格。）

---

## H-2 配额降级注记（先取证，后接线）

### 先量的收场（打桩计数，不是推断）

`test_contract_failover_endings_are_characterized` 把三条收场逐个数出来并落盘
（`contract-failover-endings.json` 由用例写入其 `tmp_path`，读数原文在下）：

| 收场 | 构造方式 | 实测 |
|---|---|---|
| ① 正常 | 三次 config 之一产出非空 | 报告正文帧 = `CONTRACT_ANSWER`，无 error 帧 |
| ② 三次尝试**全空内容、无异常** | `astream` 一个非空块都不产 | 内容帧 `[]`、error 帧 `[]` —— **静默** |
| ③ 末次尝试抛异常 | 三次都抛 | error 帧 `["服务暂时无响应，请稍后重试"]`，`boom_astream_calls=3` |

> **票面假设被读数推翻一处**：H-2 原文说「failover 全灭时**只能落到外层 error 帧**」——
> 那只是 ③ 那一支。② 那一支（三次都返回空内容且不抛异常）**既不产 error 帧也不产任何注记帧**，
> 用户看到 step 帧之后直接 `[DONE]`。合同分支是全仓**唯一**不产 error 帧的生成出口。

### 接线（交付）

```
+ if degraded:
+     answer += NOTE_QUOTA
+     yield … NOTE_QUOTA …  # gate-exit: E15
```

与流式出口 E13 同族（S2：不静默烧耗尽模型），并让降级报告**不进缓存**（写闸第二条件）。

**先红**（同 `01-red-before.stdout.txt`）：

```
>       assert main.NOTE_QUOTA in joined, "降级产出未明说（应追加 NOTE_QUOTA 注记帧）"
E       AssertionError: 降级产出未明说（应追加 NOTE_QUOTA 注记帧）
E       assert '\n\n> 注：模型配额紧张，本回答仅供参考。' in '【风险评估】第一条…建议不超过六个月。'
```

**控制腿**：`test_control_non_degraded_report_has_no_quota_note`（未降级时不得出现 NOTE_QUOTA）。

### 可达性（真实配置读数）

`probe_contract_reachability.py`（只读、不桩判定函数、不调模型）：

```
is_contract_review_real = true      need_clarify = false      n_blocks = 5   n_docs = 24
main._cacheable = true             cache_key 非 None          level = 极高
feature_router = true              feature_multi_analyze = true
registry.default_key = agent_text_37max0608
registry.is_unavailable(default_key) = false      ⇒ degraded 今天恒假
verdict_contract_branch_entered_in_real_config = true
```

⇒ 两条读数，各自的含义分开写清：
1. **合同分支入口在真实配置下确实进得去**（登记表 E5 的 `traffic` 因此由「静态可达（执行未证）」
   改为「有执行取证」）。
2. **E15 那一帧今天零命中**（`degraded` 恒假）⇒ 它是「接线正确、今天不生效」，**不是**「线上已生效」。

---

## 未覆盖（如实登记）

1. **②「静默空」这一支今天仍不受保护**：它不产 error 帧，用户看到的是「无响应」。
   补 error 帧会改用户可见行为，且超 H-2 的射程（票面把外层 error 帧归为「不在本表范围」）⇒
   **须 Owner 另裁**，本票不当成已修。（已写进 E5×配额降级注记 格。）
2. **合同报告没有端到端真实取证**（一次真实模型调用产出一份真实报告）：要花钱，属评测批事项。
   本票所有判据都在端点级用替身模型取得。
3. E5/E6/E15 之外，本票**没有**动自检、多选完整性、版本绊线三格（分别归票 J、票 I/A-C）。

---

## 仪器层：R1 读数为什么作废，R2 怎么修

R1 用 `run_mutations_full.py` 原编排串跑 baseline+M1+M2+M3，四个跑次共用同一个
`--basetemp=<out>/bt`。pytest 每次启动都会**整树删掉**已存在的 `--basetemp`：

- 第一跑（baseline）时 `bt` 是空的 ⇒ 干净（`tests=1383 failures=0 errors=0`）；
- 从那之后 `bt` 里躺着上一轮 1383 个用例的临时目录，下一跑启动时那条**批量删除**撞上
  WorkBuddy 沙箱的 safe-delete 批量守卫 ⇒ M1/M2/M3 **各报 225 条 setup error，数字逐字相同**。

守卫自己的报错原文（`mut-out/stdout-H-M1_….txt`）：

```
[safe-delete][SAFE_DELETE_BULK_CONFIRM_REQUIRED]
{"count":437,"threshold":50,"scope":"turn","targets":["\\?\…\hij-h-20260920\mut-out\bt"],"targetCount":1}
```

⇒ `denominator-drift` 是真坏消息（判据要求「不是 KILLED 就是坏消息」），不是噪声。
**R2 只改一处**：每个跑次用自己唯一的 `out_dir`（⇒ 唯一 basetemp，不再整树删别人的目录）；
`run_suite` / `suite_stats` / `failed_set` / 分母比对 / anchor 唯一性**一个字节不改**，直接复用
`run_mutations_full` 的函数（不产生第二份判据实现）。

⚠️ 附带一条**给下一票的仪器事实**：任何"一个 tool 调用里串跑多次 pytest 且共用 `--basetemp`"
的编排都会撞上这道守卫。唯一 basetemp 即可，**不要**去动 `CODEBUDDY_SAFE_DELETE_*` 环境变量。

---

## 回报（照票面格式逐条填数）

```
P0 边界自查：开关默认值=保持 False（生效值读数 false）  agent/=未动  evals/=未动
            gate2_runner sha=ae2e412059ed68ac1514c62727cee61c50b8a2d6fe7e38a77c7e05631847e295
HEAD=2693745  开工前脏项=无   本票提交=3f3bf0f（+ 取证补正提交）
逐条：H-1 → 写闸由 `if cache_key:` 改为 `if cache_key and not bad and not degraded:`（main.py 分支0.3）
      H-2 → 先量三条 failover 收场（打桩计数）+ 接 E15 降级注记帧（NOTE_QUOTA）
      H-3 → 未越界：合同缓存键构造未合并、`_build_contract_data` 未改、`contract_verify.py` 未动
先红：test_bad_citation_report_is_not_cached 红在 `assert sink == []`（原文见「先红」节，非 TypeError）；
      test_degraded_contract_report_carries_quota_note 红在 `assert main.NOTE_QUOTA in joined`
可达性：打桩方法=`_safe_pick` 第三元桩 True + spy `answer_cache.put`；命中次数=端点级各 1 次；桩已删=是
      真实配置读数=`probe_contract_reachability.py`（入口可达；`degraded` 恒假 ⇒ E15 今天零命中）
变异：H-M1 KILLED newly_red=test_contract_exit_gates::test_bad_citation_report_is_not_cached
      H-M2 KILLED newly_red=test_contract_exit_gates::test_degraded_contract_report_carries_quota_note
      H-M3 KILLED newly_red=同上
      分母 基线 tests=1383 errors=0；每个变异体 tests=1383 errors=0
      跑在哪棵树=dispatch-output/hij-h-20260920/copytree（git archive 3f3bf0f + 假 .env）
回表：E5×配额降级注记 / E5×写缓存闸 / E6×写缓存闸 → PASS；另新增 E15 行、E5 的 traffic 升级为
      「有执行取证」；gen 已跑=是；test_gate_exit_registry=14 passed；
      引号口径 `grep -c '"GAP-TODO"'`：8 → 5（= 8 − 3）
静态门：ruff=0  ruff format --check=0  mypy=0（73 files）  pre-commit(暂存集全跑)=0
车道/门禁：定向 48 passed / 2 skipped / 0 failed（未在 live 树跑全量，见 §0 边界 ⇒ RUN_VALID 不涉及）
      真实库零写入读数：host app.db cc=10710（mtime 09-17 02:37，本会话未变）/ quota cc=2 /
      chroma 目录内容指纹 71e7a7a4…-n38-s362449354（与上一会话 post 逐字相同）
如实登记未覆盖：① E5/E6/E15 三格以外本票一格未动（自检 / 多选完整性 / 版本绊线分归 J、I/A-C）；
      ② 合同分支「三次尝试全空内容且无异常」这一支**仍不产 error 帧**（静默空，须 Owner 另裁）；
      ③ 合同报告**没有**端到端真实模型取证（要花钱，属评测批）；④ E15 今天零命中（接线正确、不生效）；
      ⑤ **全量 lane 的基线 0 红不稳**：同配置两次跑次 0 红 / 8 红（8 条既有 flaky 簇，清单见「变异」节）
本次消耗轮次≈80
快照=无（未撞轮次上限，未使用快照协议）
需要 Owner 决策或放行=① 合同分支「静默空」是否补 error 帧；② 带告警/降级报告不进缓存的价格是否接受
证据文件清单（路径 + wc -c 字节数，均在 dispatch-output/hij-h-20260920/）：
  report.md（本文件；字节数随每次编辑变化，故不写死）/ 00-pre-flight.json 2035 /
  01-red-before.stdout.txt 8839 /
  02-green-after.stdout.txt 2627 / 00-smoke.stdout.txt 3647 / 04-static-gates.txt 2123 /
  04b-mypy-final.txt 327 / 06-precommit.txt 400 / 05-targeted-pytest.stdout.txt 1967 /
  08-copytree.txt 554 / 10-real-db-readonly.txt 355 / 11-chroma-manifest.txt 475 /
  real-db-readonly-h-post.json 353 / 13-before-junit.xml 5047 / 14-after-junit.xml 4963 /
  15-frames-BEFORE.json 2412 / 16-frames-AFTER.json 2412 / 17-reachability-realconfig.json 447 /
  18-registry-regate.stdout.txt 539 / 19-noise-no-mutation.stdout.txt 549 /
  probe_real_db_readonly.py 1457 / probe_contract_reachability.py 3625 /
  run_mutations_ticket_h.py 1942 / run_mutations_ticket_h2.py 5407
  （变异原始 junit/stdout 在 mut-r2/ 与 mut-r2b/，未入库；R1 作废读数在 mut-out/）
```

---

## 变异（R2）

**跑在哪棵树**：`dispatch-output/hij-h-20260920/copytree`（`git archive 3f3bf0f` + 假 `backend/.env`，
不进 live 树）。`PYTEST_EXTRA=["-m","not slow"]`，每个跑次**唯一 basetemp**。

**基线分母**（**两次独立跑次**，同一棵树、同一条命令、各自唯一 basetemp）：

| 跑次 | `tests` | `failures` | `errors` | 落盘 |
|---|---|---|---|---|
| `mut-r2/baseline`（本票差分用的基线） | 1383 | **0** | 0 | `mut-r2/baseline/full-baseline.xml` |
| `mut-r2b/baseline`（复核用） | 1383 | **8** | 0 | `mut-r2b/baseline/full-baseline.xml` |

> 分母口径：1383 = 票 C 的 1378 + 本票新增 5 条。**0 failure** 而不是 §0.5.2(e) 记的 2 条，是因为
> 副本树按 §0.5.2(e-补) 自备了假 `backend/.env` ⇒ 那两条 `release_eligible` 不再红。
> 两条车道同一个口径，差的这 2 条单独说明，不混算。
>
> ⚠️ **但"基线 0 红"不稳**：第二次同配置跑次出了 **8 条红**（见下节）。这 8 条是**全量 lane 里的既有
> flaky 簇**（同三个文件），**与开关、与树、与本票都无关** —— 决定性证据就是"不施加任何变异也复现同一集合"。
> ⇒ 差分基线取第一次（0 红）那一轮；你重跑时若基线本身带这 8 条，把它们从 `newly_red` 里减掉再判。

| 变异 | 改什么 | 分母 | 结果 | `newly_red`（本票判据那一条） |
|---|---|---|---|---|
| **H-M1** `write_gate_blind_to_bad` | `if cache_key and not bad and not degraded:` → 去掉 `and not bad` | `tests=1383 errors=0` | **KILLED** | `test_contract_exit_gates::test_bad_citation_report_is_not_cached` |
| **H-M2** `write_gate_blind_to_degraded` | 同上去掉 `and not degraded` | `tests=1383 errors=0` | **KILLED** | `test_contract_exit_gates::test_degraded_contract_report_carries_quota_note` |
| **H-M3** `degraded_note_not_emitted` | `if degraded:` → `if degraded and False:`（锚点留在源码里 ⇒ 出口条数不变，归因干净） | `tests=1383 errors=0` | **KILLED** | 同上 |

三个变异体的 `main_py_restored_byte_exact` 全为 `true`（跑完逐字节还原，无变异残留）。

### ⚠️ 逐条如实登记：M2/M3 的 `newly_red` 里混着与本票无关的用例

| 变异 | `newly_red` 总条数 | 其中**非本票**用例 |
|---|---|---|
| H-M1 | 1 | 0 |
| H-M2 | 6 | 5 |
| H-M3 | 9 | 8 |

那批非本票用例是（三个文件）：`test_backup_data`（4 条，仅 M3 有）、
`test_capture_eval::test_capture_rejects_non_20_case_set_and_existing_output`、
`test_request_bootstrap::test_persisted_image_files_are_cleaned_after_later_failure[classify/commit/describe]`。

**它们与本票无关的证据链（三条独立读数）**：

1. 变异体只改 `stream()` 分支0.3 里一个 `if` 与一处注记帧；那批用例**一次都不进**合同分支
   （它们不构造 `contract_data`）⇒ 语义上不可能被这个变异影响。
2. 数量随**跑序单调增长**（M1: 0 → M2: 5 → M3: 8），而 M2 与 M3 改的是同一处判定的**相邻两个面**
   ⇒ 形状上像"跑序/负载"，不像"语法相关"。
3. **决定性读数（两条）**：
   - 在**未施加任何变异**的同一棵副本树上单跑这三个文件 ⇒ `52 passed, 0 failed`
     （`19-noise-no-mutation.stdout.txt`）⇒ 它们不是被变异打红的；
   - 再跑一次**完全无变异**的整棵 `tests/`（`mut-r2b/baseline`）⇒ `tests=1383 failures=8 errors=0`，
     而这 **8 条红与本表 M2/M3 的非本票 `newly_red` 逐字相同**：

     ```
     test_backup_data::test_backup_fails_closed_when_manifest_construction_raises
     test_backup_data::test_backup_maps_each_extra_source_to_its_own_package_name
     test_backup_data::test_backup_tolerates_absent_extras_and_says_so
     test_backup_data::test_manifest_media_items_degrade_to_counts_when_over_limit
     test_capture_eval::test_capture_rejects_non_20_case_set_and_existing_output
     test_request_bootstrap::test_persisted_image_files_are_cleaned_after_later_failure[classify]
     test_request_bootstrap::test_persisted_image_files_are_cleaned_after_later_failure[commit]
     test_request_bootstrap::test_persisted_image_files_are_cleaned_after_later_failure[describe]
     ```

⇒ 结论：这 8 条是**全量 lane 的既有 flaky 簇**（同一批用例，两次同配置跑次 0 红 / 8 红），
在本票的差分里被 junit 差分误记成 `newly_red`。本票的 KILL 判据**只认自己那一条**，
三条变异各有且都有（见上表最后一列）；本票新增的那条用例在**两次基线跑次里都绿**。

**给 Owner 的提醒**：你重跑我声明的这三个变异时，若 `newly_red` 里出现上面这 8 个名字，
它们与变异无关（同一集合在不施加变异时也出现），**不要**算进本票的命中；
若你的基线本身带这 8 条，先减掉再判。

---

## 两条口径订正（给下一票，别重踩）

1. **`grep -c GAP-TODO` 有两个口径，别混用**：带引号的 `grep -c '"GAP-TODO"'` 基线 **8**（= 7 个格子
   + `STATUSES` 里那 1 处），本票后 **5**；**不带引号**的 `grep -c GAP-TODO` 基线是 **10**、本票后 **7**
   —— 多的两处是模块 docstring 里不带引号的提及。§9-1 那句话说的是**带引号**口径。
2. **§0.5.5 的"现值 app.db cc `10784`"指的是容器内那份**。宿主 `backend/data/app.db` 的
   change_counter 是 **10710**、size 19939328、mtime 2026-09-17 02:37；
   `appdb-lastwrite-forensics-20260919/report.md` 第 179 行把两者并列写着
   （「`backend/data/app.db`（容器副本，cc=10710，mtime 09-17 02:37）」）。两份不是同一个文件，
   报"零写入"时要写清**读的是哪一份**。
