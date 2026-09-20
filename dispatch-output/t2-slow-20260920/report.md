# T2 · `-m slow` 那 18 条到底跑不跑得通（只读诊断）

> trace_id: `t2-slow-20260920` ｜ 优先级 P1 ｜ 只读诊断，只写本交付目录
> 判据口径以 `ALL-PARALLEL-TASKS.md` 的 **T2 卡**为准；禁令与终止条件以 `01-pilot-briefs.md` 为准。

---

## 0. 开工/收工锚点（基线哈希）

| 项 | 值 | 备注 |
|---|---|---|
| 开工 `git rev-parse HEAD` | `2a48f3ec0f4b906302755504131c5da252e38f77` | 与 `baseline.json`/卡一致 |
| 收工 `git rev-parse HEAD`（复测） | `2a48f3ec0f4b906302755504131c5da252e38f77` | **未变**，运行期间无其他会话提交 |
| `sha256(backend/main.py)`（开工实测） | `4807cc9e4b9dd14334b754f63dea53ff9c1b669157647b93de21bab5be4cbe5f` | 与 `baseline.json` 一致，产品码未被触碰 |
| 真实 KB 文档数（读 `backend/chroma_db`，只读） | **10266** 条 | `real_kb` fixture 阈值 1000 ⇒ 不会触发空库 skip |
| 跑次 | live 树 `backend/`，两条命令各跑 1 次 | 均在 live 树，读真实 `chroma_db` |

**路径坑规避**：`--basetemp` / `--junitxml` / 重定向目标一律用原生 `C:/...` 绝对路径（T1 踩过的 `/c/Users/...` 相对路径误解析坑已规避）；两条跑次 `--basetemp` 各异（`t2slow` / `t2notslow`）。判成败看 junit/产物，不看退出码。

---

## 1. 两条跑次逐项计数表

| 跑次 | selected(收集) | passed | failed | skipped | errors | deselected | 合计(本表口径) |
|---|---|---|---|---|---|---|---|
| **slow** (`-m slow`) | 18 | 13 | 5 | 0 | 0 | 1399 | 18 + 1399 = **1417** |
| **not-slow** (`-m "not slow"`) | 1399 | 1396 | 1 | 2 | 0 | 18 | 1399 + 18 = **1417** |

> 数据源：两台跑的 `*.xml`（`tests`/`failures`/`skipped`/`errors` 属性）+ `*.stdout.txt` 的 `short test summary info` 行。计数不经管道、不取退出码。

### 分母对账

- 卡里判据写的分母：`1408 = 1390 + 18`。
- **实测分母 = 1417 = 1399 + 18 = 18 + 1399**。
- 两条跑次**互相自洽**：slow 的 deselected(1399) == not-slow 的 selected(1399)；not-slow 的 deselected(18) == slow 的 selected(18)。⇒ 真·全集 = **1417**。
- **结论**：卡的 `1408` 是写卡时的过期快照；当前套件比当时多了 **9 条测试**（1408 → 1417）。分母不自洽于卡的旧数字，但与两次实测完全自洽，故按实测 **1417** 上报，卡数字作废标注。
- `errors` 两跑均为 **0** ⇒ 两跑都是有效读数，无"整轮崩盘"型假读数。

### skip 与 failed 严格分列（卡硬要求）

- **slow 跑**：`skipped=0`、`failed=5`。`skipped=0` 是关键证据——`real_kb` fixture 仅在主库 `< 1000` 条时 `pytest.skip`；实测 KB=10266 条 ⇒ **未发生任何"环境缺 KB"的 skip**。5 条红**全是真失败，一条都不是环境 skip**。
- **not-slow 跑**：`skipped=2`（均为 env 开关门控的帧采集用例，非 KB），`failed=1`（测试/代码签名不同步，见 §3）。

---

## 2. slow 18 条逐条结果 + 5 条红的原文与归类

18 条全在 `tests/` 下、标记 `pytest.mark.slow`，且依赖真实 KB（`real_kb` fixture，已在签名内）。**全部被收集并执行（无 skip、无收集期炸）**。

**13 passed**：`test_domain_rules::test_cheating_docs_lookup_real_kb`、`test_consumer_clause_docs_lookup_real_kb`、`test_import_docs::test_import_one_end_to_end`、`test_import_docs::test_import_one_idempotent_by_hash`、`test_knowledge_service::test_concurrent_add_text_idempotent`、`test_retrieval_rerank::test_high_altitude_fall_precision`、`test_admin_reconsideration_scope`、`test_personal_info_principles`、`test_shareholder_capital_deadline`、`test_short_name_exact_lookup`、`test_short_name_citation_verify`、`test_scenario_supplement::test_unrelated_scenario_no_trigger`、`test_statute_supplement::test_all_supplement_articles_exist_in_kb`。

**5 failed（全部 `tests/test_scenario_supplement.py`，根因同源：真实 KB 未命中这些"补充组"条文）**：

1. `test_id5_statutory_inheritance_prepends_1155`
   原文：`AssertionError: assert '第一千一百五十五条' in []`（`scenario_supplement_docs(q)` 返回的 article 元数据列表为空）
2. `test_id16_labor_dispute_prepends_47_and_53`
   原文：`AssertionError: assert '第四十七条' in []`
3. `test_guarantee_contract_triggers_692_693`
   原文：`AssertionError: assert '第六百九十二条' in []`
4. `test_company_law_49_no_old_breach_clause`
   原文：`AssertionError: 公司法第49条应存在于知识库`（即 `exact_article_lookup("公司法","第四十九条")` 返回 `[]`）
5. `test_all_supplement_articles_exist`
   原文：`AssertionError: 补充组条文不在知识库: [('death_review','刑事诉讼法','第二百四十六条'), ('self_defense','刑法','第二十条'), …（全部补充组条文均 missing）]`

**归类（环境缺 KB / 真回归）**：
- 这 5 条 **不是"环境缺 KB"的 skip**——由 `skipped=0` + KB=10266 条双重证实，`real_kb` 从未 skip，库真实存在且庞大。
- 故在卡的二选一里，它们落于**「真失败（失败侧）」**：真实 KB（10266 条）**未命中**这些特定的"补充组"条文——`exact_article_lookup` / `scenario_supplement_docs` 对这些 (source, article) 返回空。
- 进一步性质：**属「KB 数据覆盖缺口 / 检索口径（source-key 匹配）」类**。第 4/5 条用**裸源名**（如 `"公司法"`、`"民法典"`）仍查不到，与 T6 / 票 I-6 正在修的 `exact_article_lookup` 源名/括注匹配问题**同源可疑**。
- 是否构成"**代码真回归**"（库曾经有、被改丢）还是"**库从未装入这些条文**"，需产品/检索侧结合 KB provenance 判定——超出本只读诊断范围，故**不臆断为真回归**，只确定：①是真失败、②不是环境缺 KB 的 skip。这正满足卡的"别把环境缺 KB 的 skip 报成回归，也别反过来"。

---

## 3. not-slow 跑的 1 条红（超出 slow-18 核心，但诚实列出）

- `tests/test_phase3.py::test_chat_streams_persists_and_request_id`
  原文：`[chat-stream] TypeError: test_chat_streams_persists_and_request_id.<locals>.<lambda>() takes 1 positional argument but 2 were given`
  根因：用例 `monkeypatch.setattr(main, "make_chain", lambda llm: FakeChain())`，但 `main.make_chain` 现被以 **2 个参数**调用 ⇒ lambda 签名不匹配。属**测试/代码签名不同步的真失败**，**非 KB、非环境缺库**。
- not-slow 的 2 条 skipped：`未设 FZ_DUMP_FRAMES`（1a 改前/改后逐帧比对采集口）、`未设 S6_DUMP_FRAMES`（票 C 改前/改后逐帧比对采集口）——env 开关门控的合法 skip，非 KB、非回归。

---

## 4. 健康度自检（针对 not-slow 跑的 <3min 告警）

- not-slow 实测耗时 **172s（2m52s）**，略低于卡给的 3min 警戒线。
- 按 T1 报告 `dispatch-output/t1-flaky-20260920/report.md` 的"轮次健康度"法自检：
  - junit `tests="1399"`（=全集−18）⇒ **分母完整，未被路径坑塌缩**；
  - `errors="0"`、**无 "ERROR collecting" / 批量 setup error**；
  - 与 slow 跑自洽（1399 互等）。
  ⇒ **判定为有效读数**，非 T1 式 `/c/Users` 路径误解析导致的"整轮 225 个 setup error 假崩盘"。可放心交数。

---

## 5. 五段回报（按 `01-pilot-briefs.md` §2 固定格式）

### ① 结论
那 18 条 **能跑通**（18 条全部被收集并执行，0 条因环境缺 KB 而 skip，0 条收集期炸），但**有 5 条失败**：5 条红均因真实 KB（10266 条）未命中 `test_scenario_supplement` 断言的特定"补充组"条文，属真失败（KB 覆盖/检索口径类），**不是环境缺 KB 的 skip**，也**不是整轮崩盘假读数**。

### ② 产物路径 + 关键读数
- `C:\Users\33393\Desktop\ai-legal-helper\dispatch-output\t2-slow-20260920\slow-run.xml`（tests=18 / failures=5 / skipped=0 / errors=0）
- `C:\Users\33393\Desktop\ai-legal-helper\dispatch-output\t2-slow-20260920\slow-run.stdout.txt`（末行：`5 failed, 13 passed, 1399 deselected`）
- `C:\Users\33393\Desktop\ai-legal-helper\dispatch-output\t2-slow-20260920\notslow-run.xml`（tests=1399 / failures=1 / skipped=2 / errors=0）
- `C:\Users\33393\Desktop\ai-legal-helper\dispatch-output\t2-slow-20260920\notslow-run.stdout.txt`（末行：`1 failed, 1396 passed, 2 skipped, 18 deselected`）
- `C:\Users\33393\Desktop\ai-legal-helper\dispatch-output\t2-slow-20260920\report.md`（本文件）
- 锚点：HEAD=`2a48f3e…`；`sha256(backend/main.py)=4807cc9e…`；真实 KB=**10266** 条。

### ③ 判据对照（逐条，标 满足 / 不满足）
- 判据①"两条跑次 passed/failed/skipped/deselected 逐项落表"：**满足**（§1 表已给，skip/failed 严格分列）。
- 判据②"分母对账 1408 = 1390 + 18"：**不满足（卡的分母已过期）**。实测全集 = **1417 = 1399 + 18**，两跑互证；卡写 1408 比当前少 9 条，按实测 1417 上报并标注卡数字作废。
- 判据③"skip 与 failed 必须分开数"：**满足**。slow：skipped=0 / failed=5；not-slow：skipped=2 / failed=1。
- 判据④"有红逐条给红因原文 + 判定环境缺KB/真回归"：**满足**。slow 5 红原文见 §2；均判定"非环境缺KB（KB=10266）→ 真失败（KB 覆盖/检索口径类）"；not-slow 1 红原文见 §3，判定"测试/代码签名不同步真失败"。
- 判据⑤"不接受把环境缺KB的skip报成回归或反之"：**满足**。`skipped=0` 证实无环境缺KB skip；未将任何 skip 当回归；5 红均未错归为环境 skip。

### ④ 我复跑的命令（确切，可直接照跑）
```
# 在 live 树 C:\Users\33393\Desktop\ai-legal-helper\backend 下，两条各跑一次、--basetemp 不同：
C:/Users/33393/Desktop/ai-legal-helper/backend/venv/Scripts/python.exe -m pytest tests/ -q -p no:cacheprovider --basetemp=C:/Users/33393/AppData/Local/Temp/t2slow --junitxml=C:/Users/33393/Desktop/ai-legal-helper/dispatch-output/t2-slow-20260920/slow-run.xml -m slow > C:/Users/33393/Desktop/ai-legal-helper/dispatch-output/t2-slow-20260920/slow-run.stdout.txt 2>&1

C:/Users/33393/Desktop/ai-legal-helper/backend/venv/Scripts/python.exe -m pytest tests/ -q -p no:cacheprovider --basetemp=C:/Users/33393/AppData/Local/Temp/t2notslow --junitxml=C:/Users/33393/Desktop/ai-legal-helper/dispatch-output/t2-slow-20260920/notslow-run.xml -m "not slow" > C:/Users/33393/Desktop/ai-legal-helper/dispatch-output/t2-slow-20260920/notslow-run.stdout.txt 2>&1
```
⚠️ 路径坑：`--basetemp`/`--junitxml`/重定向目标必须原生 `C:/...` 绝对路径；传 `/c/Users/...` 会被 Python 当相对路径解析成 `C:\c\Users\...` 致整轮假崩盘（T1 已实测）。

### ⑤ 诚实登记 + 越界写声明
- **没做到的 / 未证实的**：未判定 slow 5 红是"代码真回归（库曾含后被改丢）"还是"库从未装入这些条文"——需产品/检索侧结合 KB provenance 与 I-6 整改判定，超出本题只读诊断范围；仅能确定它们是真失败且非环境缺KB skip。未在关闭 safe-delete 守卫等"干净环境"复跑（本案未触发该守卫，慢跑 54s、非慢跑 172s 均无 `SystemExit` 假红）。
- **读不到的 / 未证实的**：无。真实 KB 实读 10266 条；两跑均为有效读数（分母完整、errors=0）。
- **健康度**：not-slow 172s 略 <3min 告警线，但按 T1"轮次健康度"法核验为有效读数（分母完整、无批量 setup error），非路径坑假崩盘。
- **越界写声明**：**无越界写**。写集仅 `dispatch-output\t2-slow-20260920\`（4 产物）+ 两个 Temp basetemp（`C:\Users\33393\AppData\Local\Temp\t2slow`、`t2notslow`）。未执行任何 git 写操作；未改 `backend\.env` 或 `backend\**` 任何文件（`git status backend` 仅余票 I 在途未跟踪项 `.ptmp-s4-run2\`，非我所写）；HEAD 开工=收工=`2a48f3e`；`main.py` 哈希与基线一致，产品码未被触碰。

---

## 6. 给下游的建议（非卡要求，附加）
slow 5 红集中在 `test_scenario_supplement.py` 的"补充组条文在库一致性"。若要让这 18 条稳定绿，正确方向是核对真实 `backend/chroma_db` 是否确实装入 `scenario_supplements.json` 所列 (source, article)，以及 `exact_article_lookup` 对裸源名（如 `"公司法"`）的匹配口径——后者与 T6 / 票 I-6 的源名括注匹配问题同源，建议合并排查，而非改测试。
