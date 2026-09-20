# 并行派发卡（可整段粘贴给独立会话）— 2026-09-20 R2

**根目录（下称 `<R>`）**：`C:\Users\33393\Desktop\ai-legal-helper`
**解释器（唯一可用）**：`<R>\backend\venv\Scripts\python.exe`
**pre-commit**：`<R>\backend\venv\Scripts\pre-commit.exe`
**口径总纲**：`<R>\dispatch-output\hij-h-20260920\16-dispatch-plan.md`（第 0 节与 R2 追加节）
**任务清单来源**：同上文件；本卡片只补"完整路径 + 粘贴语 + 验收命令"。

> 通用硬提醒（每张卡都适用）：
> 1. **只写自己的交付目录**；不改 `backend/**`、`docs/gate-exit-registry.md`、`backend/scripts/gate2_runner.py`。
> 2. 要跑**全量 pytest** 的任务，必须在**自己的副本树**里跑（`make_copytree.py`，见 T1 卡）；
>    **禁止在 live 工作树跑全量**（此刻 live 树正被票 I 编辑 ⇒ 两败）。
> 3. 每个跑次用**自己唯一的 `--basetemp`**（共用会撞沙箱 safe-delete 批量守卫）。
> 4. 结论要指到**命令 + 产物文件**；"跑完了"不算，**产物在**才算。
> 5. 本机 git-bash 缺 PATH：先 `export PATH=/c/Users/33393/.workbuddy/binaries/PortableGit/versions/1.2.0/usr/bin:$PATH`。
> 6. 别碰另一会话的在途文件 `<R>\docs\code-review-report-02e3851-20260918.md`。

---

## T1 · 全量 lane 的 flaky 簇定位（**优先**）

**粘贴语**
> 在 `C:\Users\33393\Desktop\ai-legal-helper` 里做一件**只读诊断**：定位全量 pytest lane 里那簇 flaky 用例。
> 判据与纪律照 `C:\Users\33393\Desktop\ai-legal-helper\dispatch-output\hij-h-20260920\16-dispatch-plan.md` 的 T1 卡。
> 不要改任何产品代码；只写 `dispatch-output\t1-flaky-20260920\`。

**交付路径**：`<R>\dispatch-output\t1-flaky-20260920\`
必需产物：`matrix.json`（用例 × 跑次的红绿矩阵）、`report.md`（每条的最小复现 + 根因 + 归类）、
`run-N.stdout.txt` × N（N≥5）。

**输入路径（读数，别重做）**
- 0 红基线：`<R>\dispatch-output\hij-h-20260920\mut-r2\baseline\full-baseline.xml`
- 8 红基线：`<R>\dispatch-output\hij-h-20260920\mut-r2b\baseline\full-baseline.xml`
- 8 红基线（票 J）：`<R>\dispatch-output\hij-j-20260920\mut\baseline\full-baseline.xml`
- 判据函数的**唯一实现**（别另写解析）：`<R>\dispatch-output\s5-followup-20260920\run_mutations_full.py`
  （用它的 `failed_set()` / `suite_stats()`）

**副本树怎么搭**（跑全量必须在副本树）
```
<R>\backend\venv\Scripts\python.exe <R>\dispatch-output\s6-stream-gate-20260920\make_copytree.py 1e969f2 <R>\dispatch-output\t1-flaky-20260920\copytree
# 再写一份假 .env（三行即可，端口 9 是 discard，防误调真模型）：
#   JWT_SECRET=...  LLM_API_KEY=...  LLM_BASE_URL=http://127.0.0.1:9/v1
# 输出到 <copytree>\backend\.env
```

**我的验收命令**：你给的那条重复命令我再来 ≥3 次，红/绿矩阵须与你**逐格一致**；
`matrix.json` 里出现次数为 0 的名字不算 flaky。

---

## T2 · `-m slow` 那 18 条

**粘贴语**
> 在 `C:\Users\33393\Desktop\ai-legal-helper` 里做一件**只读诊断**：`-m slow` 的 18 条用例到底跑不跑得通
> （`pytest -m slow --collect-only` 已确认 = `18/1408 collected`）。判据照
> `...\dispatch-output\hij-h-20260920\16-dispatch-plan.md` 的 T2 卡。只写 `dispatch-output\t2-slow-20260920\`。

**交付路径**：`<R>\dispatch-output\t2-slow-20260920\`
必需产物：`slow-run.stdout.txt` + `slow-run.xml`（junit）、`notslow-run.xml`、`report.md`（分母对账 1408=1390+18）。

**输入路径**
- 冻结用例清单来源：`<R>\docs\handoff-gap-tickets-h-i-j-20260920.md`（§0.5.2 e 条：18 条 slow 需已填充 KB）
- 需要 KB 的树：`<R>\backend\chroma_db`（**只读**；`manifest_chroma.py` 见 T3 卡可用来证明没被写）

**我的验收命令**：`pytest -m slow` 的 passed/failed 与你的报告逐项一致；未改 `<R>\backend\.env`。

---

## T3 · 两份 `app.db` 口径统一

**粘贴语**
> 在 `C:\Users\33393\Desktop\ai-legal-helper` 里做一件**只读**取证：把两份 `app.db` 的口径统一成一张表
> （宿主那份 vs 容器内那份），并回答"宿主那份今天还是不是被写的"。判据照
> `...\dispatch-output\hij-h-20260920\16-dispatch-plan.md` 的 T3 卡。**绝对只读**（不开事务/不 VACUUM/不改 schema）。
> 只写 `dispatch-output\t3-appdb-20260920\`。

**交付路径**：`<R>\dispatch-output\t3-appdb-20260920\`（`report.md` + `readings.json`）
**输入路径**
- 已有取证：`<R>\dispatch-output\appdb-lastwrite-forensics-20260919\report.md`（第 179 行把两份并列写着）
- 宿主文件：`<R>\backend\data\app.db`（只读；我独立读到的现值为 `cc=10710 / size=19939328 / mtime 2026-09-17 02:37`）
- 配额库：`<R>\backend\data\quota_used.sqlite`
- chroma 整目录清单仪器：`<R>\dispatch-output\te-chroma-isolation-20260918\manifest_chroma.py`
- 只读读数脚本（可复用）：`<R>\dispatch-output\hij-h-20260920\probe_real_db_readonly.py`

**我的验收命令**：你的读数须与我独立读到的上面三值一致。

---

## T4 · 未跟踪资产清点（只出建议）

**粘贴语**
> 在 `C:\Users\33393\Desktop\ai-legal-helper` 里清点未跟踪资产并给**入库/清理建议**（**不许实际删除**）。
> 判据照 `...\dispatch-output\hij-h-20260920\16-dispatch-plan.md` 的 T4 卡。只写 `dispatch-output\t4-assets-20260920\`。

**交付路径**：`<R>\dispatch-output\t4-assets-20260920\`（`inventory.md` + `classification.json`）
**输入**：`git status --porcelain`（实测现值：全仓 **360** 项未跟踪 = `docs/` 30 + `dispatch-output/` 299）
**边界**：`<R>\backend\.ptmp-s4-run2\` 与另一会话的在途文件属"别动"类。

**我的验收命令**：`git status --porcelain` 计数与你一致；"可清理"清单里没有已被删掉的东西。

---

## T6 · I-6 同族普查（source 精确匹配漏掉带年份括注）

**粘贴语**
> 在 `C:\Users\33393\Desktop\ai-legal-helper` 里做一次**只读普查**：除 `retrieval.py::exact_article_lookup`
> （票 I 正在修）之外，还有哪些调用点用"source 精确匹配"，会漏掉库内带年份括注的源名（如 `宪法（1982年）`）。
> 判据照 `...\dispatch-output\hij-h-20260920\16-dispatch-plan.md` 的 T6 卡。**只普查 + 出报告，不改代码**。
> 只写 `dispatch-output\t6-sourcekey-survey-20260920\`。

**交付路径**：`<R>\dispatch-output\t6-sourcekey-survey-20260920\`（`survey.md` + `call-sites.json`）
**输入路径（普查清单，已实测存在）**
- 待判调用点：`<R>\backend\knowledge_service.py`、`<R>\backend\scripts\gen_gate1_law_check.py`、
  `<R>\backend\scripts\import_laws.py`、`<R>\backend\scripts\import_docs.py`
- **正确形态的参照实现**（别另造归一规则）：`<R>\backend\retrieval.py` 的 `_source_key`
  （`article_in_kb` / `source_in_kb` / 引用校验都在用它）
- 已有测试锚点：`<R>\backend\tests\test_citation.py`（断言 `_source_key("宪法（1982年）") == "宪法"`）

**我的验收命令**：逐调用点给"要不要容错 + 理由"；出现"另写一份去括注正则"即打回。

---

## T7 · `options_fingerprint` 60/279 的根因（**必须先于任何"补采"**）

**粘贴语**
> 在 `C:\Users\33393\Desktop\ai-legal-helper` 里做一次**只读**诊断：语料 `qa_pairs` 里
> `options_fingerprint` 只有 60/279，而带选项的记录有 166 条——**为什么缺**？补采能不能把覆盖提到接近 166？
> 判据照 `...\dispatch-output\hij-h-20260920\16-dispatch-plan.md` 的 T7 卡。**只读、只算、不写真实语料**。
> 只写 `dispatch-output\t7-fingerprint-coverage-20260920\`。

**交付路径**：`<R>\dispatch-output\t7-fingerprint-coverage-20260920\`（`report.md` + `recompute.json`）
**输入路径**
- 已有清点读数（**别重做**）：`<R>\dispatch-output\i1-e2-hitrate-20260920\`（probe-A 的 279 条清点）
- 语料写入者：`<R>\backend\scripts\gen_qa_corpus.py`；题库来源：`<R>\backend\qa_seeds.py`
- 指纹函数：`<R>\backend\query_understand.py` 的 `_options_fingerprint`
- 读侧护栏：`<R>\backend\main.py` 的 `_qa_direct_return`
- 只读盘点脚本（可复用，已含逐条备份）：`<R>\dispatch-output\hij-i-20260920\probe_i2_corpus_inventory.py`

**我的验收命令**：必须给出"现算可提取条数"这个**数**；出现"建议补采"而无该数即打回。
⚠️ **它的"补采"实现与票 I 的 I-2(a) 写同一份真实语料 ⇒ 两个写入者必须串行**，且写前各自逐条备份。

---

## T8 · E2 出口有没有票 J 那类多选缺口

**粘贴语**
> 在 `C:\Users\33393\Desktop\ai-legal-helper` 里做一次**只读**调查：E2（QA 持久语义缓存直返）这个出口
> 是否也存在"多选题只给一个正确项却能零 token 直返"的缺口（票 J 只对齐了轻量出口 E7）。
> 判据照 `...\dispatch-output\hij-h-20260920\16-dispatch-plan.md` 的 T8 卡。**不许改 E2 的三道既有护栏**（票面 I-4）。
> 只写 `dispatch-output\t8-e2-multi-20260920\`。

**交付路径**：`<R>\dispatch-output\t8-e2-multi-20260920\`（`report.md` + `probe.json`）
**输入路径**
- 登记表 E2 行（现状自述）：`<R>\backend\gate_exit_registry.py` 里 `"id": "E2"` 那一段
- 读侧实现：`<R>\backend\main.py` 的 `_qa_direct_return`（三道护栏）
- 判据函数（**复用**，别重写）：`<R>\backend\quality.py` 的 `multi_incomplete`
- 端点级夹具：`<R>\backend\tests\_sse_harness.py`
- 票 J 的同类修复可作参照：`<R>\backend\tests\test_light_exit_gates.py`

**我的验收命令**：结论必须写清**权衡**（E2 的卖点就是零 token 直返，加判定 = 削弱该卖点）；
只说"应该加上"而无权衡即打回。

---

## 一页速查：谁写哪儿

| 任务 | 交付目录（唯一写集） | 是否读真实语料/chroma |
|---|---|---|
| T1 | `<R>\dispatch-output\t1-flaky-20260920\` | 只读 junit（历史产物） |
| T2 | `<R>\dispatch-output\t2-slow-20260920\` | 只读 chroma（KB） |
| T3 | `<R>\dispatch-output\t3-appdb-20260920\` | 只读 app.db / quota / chroma |
| T4 | `<R>\dispatch-output\t4-assets-20260920\` | 不读，只 `git status` |
| T6 | `<R>\dispatch-output\t6-sourcekey-survey-20260920\` | 不读，只读源码 |
| T7 | `<R>\dispatch-output\t7-fingerprint-coverage-20260920\` | **读**真实语料（只读） |
| T8 | `<R>\dispatch-output\t8-e2-multi-20260920\` | 读真实语料（只读） |
| 票 I（本会话） | `<R>\dispatch-output\hij-i-20260920\` + `backend/**` + `docs/gate-exit-registry.md` | **写**真实语料（已授权） |
