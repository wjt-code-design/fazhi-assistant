# 可并行派发的独立任务 · 全量清单（2026-09-20）

> **这份文件怎么用**：**只把本文件转发给一个新的独立对话即可**，不需要额外说明。
> 每张任务卡自带：启动语（可整段粘贴）、读写路径（全部绝对路径）、判据、验收命令。
> 开场请先读 **§1 硬约束** 与 **§2 通用纪律**，再按 §8 挑一张卡开工。

---

## §0 一句话结论与现状

- 本清单覆盖：**票 H/J 两轮里撞到的 + 登记表结构化扫描出来的 + 两份 backlog/交接文档抽出来的 + 五个盲区补扫的**。
- **不能并行的只有一条**：票 I（缓存复用型答复的版本判定）—— 它正在**另一个会话**里做，
  并且它与本清单里的 **T11** 抢同一个单点资源（见 §1）。
- 本清单里 **T1、T3、T4、T6–T10、T12 共 9 张卡可以真并行**；
  **T2 与 T11 必须串行**（两者都必须在 **live 树**跑：T11 要真实库的隔离指纹，T2 要真实 KB，
  而票 I 此刻正在改 live 树的 `main.py` ⇒ 同时开会两败）。
- 这个数字是**复审后订正过的**：初稿把 T2 误列为"可并行"，复审时发现它进不了副本树（详见 T2 卡）。

---

## §1 硬约束：三个「单点资源」（同一时刻只允许一个会话写）

| 资源（绝对路径） | 谁在用 | 后果 |
|---|---|---|
| `C:\Users\33393\Desktop\ai-legal-helper\backend\main.py` | 正在做的票 I | 两会话同改 ⇒ 互相覆盖；且任何"全量门禁轮"期间它被改动 ⇒ 该轮 **RUN_VOID**（读数整轮作废） |
| `C:\Users\33393\Desktop\ai-legal-helper\backend\gate_exit_registry.py` 与其生成物 `C:\Users\33393\Desktop\ai-legal-helper\docs\gate-exit-registry.md` | 任何"回表"动作 | 生成物只有一个真源；两会话各自回表 ⇒ 后者的 md 覆盖前者 |
| `C:\Users\33393\Desktop\ai-legal-helper\backend\scripts\gate2_runner.py` | **冻结件**（sha256 被锚定） | 改动即断锚 |

**附加的单写者资源**：真实 Chroma 语料集合 `qa_pairs`（279 条）—— 票 I 要往里写版本标；
**T7 的"补采指纹"实现也写它** ⇒ 两者必须串行（谁先谁后见 §4 冲突矩阵）。

**禁区（违反即停手）**：不推送、不部署；不改任何生产开关默认值；不改
`C:\Users\33393\Desktop\ai-legal-helper\backend\scripts\gate2_runner.py`；
**别碰另一会话的在途文件** `C:\Users\33393\Desktop\ai-legal-helper\docs\code-review-report-02e3851-20260918.md`。

---

## §2 通用纪律（每张卡都适用，逐条都是本仓真踩过的）

1. **只写自己的交付目录**（每张卡都给了）。不改 `backend/**`、上述三个单点资源。
2. **要跑全量 pytest 的任务，必须在自己的副本树里跑**，禁止在 live 工作树跑全量——
   live 树此刻正被票 I 编辑，两败（你的轮次作废 + 抢文件）。
3. **每个跑次用自己唯一的 `--basetemp`**（共用会撞沙箱 safe-delete 批量守卫，产出"整轮瞬间全灭"的假读数）。
4. **判成败看产物，不看退出码**：每个跑次必须回读 `junit` / `verdict.json` 这类产物；
   "进程退出了"不等于"跑出了读数"（本仓真实事故：执行器 `ModuleNotFoundError` 让整轮瞬间全灭，
   stdout 只有 traceback，看着像"跑完了"）。
5. **先红要看对的原因**：断言要亲眼看过它为**功能缺失**红，而不是 `TypeError`/`AttributeError`/笔误。
6. **"拦住了"必须配同形状的控制腿**：证明同一请求形状本来会通过（否则断言可能是空枪）。
7. **涉及共享状态的判据，要给"与邻居同跑"的复现命令**（本仓真实事故：定向单跑 7 passed，
   全量跑因模块级 `answer_cache` 被别的测试文件写入而 3 条红）。
8. **本机环境**：前台 shell 是 Git Bash；若 `grep`/`wc` 等命令找不到，先执行
   `export PATH=/c/Users/33393/.workbuddy/binaries/PortableGit/versions/1.2.0/usr/bin:$PATH`。
   计数不要在 `| head` 之后做；退出码不要经管道取。
9. **证据要入库**（`git add <显式路径>` + 手跑 pre-commit），不要只留在工作树 ——
   本仓真实事故：一份写在盘上的文件后来从工作树消失，同目录其余 30+ 份证据都在。
10. **通用工具路径**：
    - 解释器（唯一可用）：`C:\Users\33393\Desktop\ai-legal-helper\backend\venv\Scripts\python.exe`
    - pre-commit：`C:\Users\33393\Desktop\ai-legal-helper\backend\venv\Scripts\pre-commit.exe`
    - 副本树搭器：`C:\Users\33393\Desktop\ai-legal-helper\dispatch-output\s6-stream-gate-20260920\make_copytree.py`
    - junit 判据唯一实现：`C:\Users\33393\Desktop\ai-legal-helper\dispatch-output\s5-followup-20260920\run_mutations_full.py`
    - 有自证的全量门禁跑者：`C:\Users\33393\Desktop\ai-legal-helper\dispatch-output\te-chroma-isolation-20260918\run_gate_full.py`
    - 真实库只读读数脚本：`C:\Users\33393\Desktop\ai-legal-helper\dispatch-output\hij-h-20260920\probe_real_db_readonly.py`

---

## §3 任务卡（T1–T12）

> **编号说明**：**没有 T5** —— T5 = 票 I（缓存复用型答复的版本判定），它**不派发**：
> 它正在另一个会话里做，且独占 §1 的第 1 个单点资源（`backend\main.py`）。
> 编号沿用前几版派发计划，**故意不重排**，免得已发出的卡号对不上。

### T1 · 定位「全量 lane 的 flaky 簇」（**优先级最高**）

- **启动语（整段粘贴）**：在 `C:\Users\33393\Desktop\ai-legal-helper` 做一次**只读诊断**：
  定位全量 pytest lane 里那簇 flaky 用例。只写 `dispatch-output\t1-flaky-20260920\`，不改任何产品代码。
  纪律照本文件 §2。
- **为什么它是最高优先**：它**污染所有人的变异差分基线**。同一条命令我实测过 **0 红 / 3 红 / 8 红**，
  红的是同一批用例（见下"已知红名单"）。
- **交付路径**：`C:\Users\33393\Desktop\ai-legal-helper\dispatch-output\t1-flaky-20260920\`
  必需产物：`matrix.json`（用例 × 跑次 红绿矩阵）、`report.md`、`run-1..N.stdout.txt`（**N ≥ 5**）
- **输入路径**：
  - 0 红基线：`...\dispatch-output\hij-h-20260920\mut-r2\baseline\full-baseline.xml`
  - 8 红基线：`...\dispatch-output\hij-h-20260920\mut-r2b\baseline\full-baseline.xml`
  - 8 红基线（另一批）：`...\dispatch-output\hij-j-20260920\mut\baseline\full-baseline.xml`
  - 解析函数：用 `...\dispatch-output\s5-followup-20260920\run_mutations_full.py` 的 `failed_set()` / `suite_stats()`，**别另写一份**。
- **已知红名单（起点，不是结论）**：`test_backup_data`×4、`test_capture_eval::test_capture_rejects_non_20_case_set_and_existing_output`、
  `test_request_bootstrap::test_persisted_image_files_are_cleaned_after_later_failure[classify|commit|describe]`
- **副本树搭法（跑全量必须在副本树）**：
  1) 先记下用哪个 commit：**优先 `1e969f2`**（它与本文件已有的 0 红 / 3 红 / 8 红三次读数**同一棵树** ⇒ 可直接对账）；
     若该提交在你的克隆里取不到，改用你开工时的 `git rev-parse HEAD`，**并把该 hash 写进报告**。
  2) 搭树：`C:\Users\33393\Desktop\ai-legal-helper\backend\venv\Scripts\python.exe C:\Users\33393\Desktop\ai-legal-helper\dispatch-output\s6-stream-gate-20260920\make_copytree.py <上一步的hash> <T1交付目录>\copytree`
     （该脚本会把工作树里的 `backend\tests\_sse_harness.py` 等测试文件覆盖进副本 —— 这是**有意**的：两侧必须同一套测试代码。）
  3) 写假 `.env`（**只有这三行**，覆盖到 `<copytree>\backend\.env`）：
     `JWT_SECRET=fake-for-copytree-only` / `LLM_API_KEY=fake-for-copytree-only` / `LLM_BASE_URL=http://127.0.0.1:9/v1`
     （端口 9 是 discard：万一顺路真去调模型会**当场失败**，而不是静默烧额度。⚠️ 只往副本里写，**不要**读写 live 的 `backend\.env`。）
- **确切命令（第 N 次跑，N = 1..5；把 `<T1交付目录>` 与 `<N>` 换成真实值）**：
  ```
  cd C:\Users\33393\Desktop\ai-legal-helper\dispatch-output\t1-flaky-20260920\copytree\backend
  C:\Users\33393\Desktop\ai-legal-helper\backend\venv\Scripts\python.exe -m pytest tests/ -q -p no:cacheprovider --basetemp=C:\Users\33393\Desktop\ai-legal-helper\dispatch-output\t1-flaky-20260920\bt<N> --junitxml=C:\Users\33393\Desktop\ai-legal-helper\dispatch-output\t1-flaky-20260920\run-<N>.xml -m "not slow" > C:\Users\33393\Desktop\ai-legal-helper\dispatch-output\t1-flaky-20260920\run-<N>.stdout.txt 2>&1
  ```
  ⚠️ **两个要点**：① `--basetemp` **每次不同**（`bt1`、`bt2`…共用会撞沙箱 safe-delete 批量守卫 ⇒ 整轮假失败）；
  ② `-m "not slow"` **必须带**（18 条 slow 需要填充过的 KB，否则混进恒定红）。
- **判据**：① 同一条命令重复 ≥5 次，给红/绿矩阵；② 每条 flaky 给**最小复现**与**根因**
  （不接受"可能跟负载有关"）；③ 归类到「顺序依赖 / 共享状态 / 时间敏感 / 外部依赖」并逐条给证据。
- **我不接受**：≥5 次里 **0 次复现**的"疑似 flaky"（那叫没复现）；只跑一次就下结论。
- **验收命令**：你给的那条命令我再跑 ≥3 次，矩阵须与你**逐格一致**。

### T2 · `-m slow` 那 18 条到底跑不跑得通（**⚠️ 必须在 live 树跑 ⇒ 与票 I 互斥**）

- **启动语**：在 `C:\Users\33393\Desktop\ai-legal-helper` 做**只读诊断**：`-m slow` 的 18 条用例能不能跑通。
  只写 `dispatch-output\t2-slow-20260920\`。纪律照 §2。
- **⚠️ 为什么它不能像 T1 那样进副本树**：这 18 条要**真实知识库**（`real_kb` 显式 opt-in 的 fixture），而
  `tests\conftest.py` 在测试默认层把 `CHROMA_DIR` 指到进程私有临时目录 ⇒ 副本树里它们会 **skip 而不是跑**。
  ⇒ 它必须在 **live 树**（读真实 `backend\chroma_db`）跑 ⇒ **与票 I 互斥**（票 I 正在改 `main.py`，
  这些用例会 import 它）。**⇒ 与 T11 同批串行，不要与票 I 同时开。**
- **交付路径**：`...\dispatch-output\t2-slow-20260920\`（`slow-run.stdout.txt`、`slow-run.xml`、`notslow-run.xml`、`report.md`）
- **输入路径**：需要 KB 的树 = `...\backend\chroma_db`（**只读**）；清单仪器 `...\dispatch-output\te-chroma-isolation-20260918\manifest_chroma.py`
- **已知事实**：`pytest -m slow --collect-only` = `18/1408 collected`；**18 条至今没有本轮绿证**。
- **确切命令**（跑两次，分别落盘；**两者都在 live 树**，见上方 ⚠️）：
  ```
  cd C:\Users\33393\Desktop\ai-legal-helper\backend
  C:\Users\33393\Desktop\ai-legal-helper\backend\venv\Scripts\python.exe -m pytest tests/ -q -p no:cacheprovider --basetemp=%TEMP%\t2slow --junitxml=C:\Users\33393\Desktop\ai-legal-helper\dispatch-output\t2-slow-20260920\slow-run.xml -m slow > C:\Users\33393\Desktop\ai-legal-helper\dispatch-output\t2-slow-20260920\slow-run.stdout.txt 2>&1
  C:\Users\33393\Desktop\ai-legal-helper\backend\venv\Scripts\python.exe -m pytest tests/ -q -p no:cacheprovider --basetemp=%TEMP%\t2notslow --junitxml=C:\Users\33393\Desktop\ai-legal-helper\dispatch-output\t2-slow-20260920\notslow-run.xml -m "not slow" > C:\Users\33393\Desktop\ai-legal-helper\dispatch-output\t2-slow-20260920\notslow-run.stdout.txt 2>&1
  ```
  （两次跑同一个 live 树、`--basetemp` 各自不同；**不要**用 `| head`／`| tail` 取计数，会被截断。）
- **判据**：`passed/failed/deselected` 逐项 + **分母对账**（`1408 = 1390 + 18`）；若有红，逐条给红因原文，
  并判断是「环境缺 KB」还是「真回归」。
- **我不接受**：把"环境缺 KB 的 skip"报成回归，或反过来。
- **边界**：不得为了跑通去改 `backend\.env`。

### T3 · 两份 `app.db` 的口径统一

- **启动语**：在 `C:\Users\33393\Desktop\ai-legal-helper` 做**只读**取证：把两份 `app.db` 的口径统一成一张表，
  并回答"宿主那份今天还是不是被写的"。**绝不开事务/不 VACUUM/不改 schema**。只写 `dispatch-output\t3-appdb-20260920\`。
- **交付路径**：`...\dispatch-output\t3-appdb-20260920\`（`report.md`、`readings.json`）
- **输入路径**：
  - 已有取证：`...\dispatch-output\appdb-lastwrite-forensics-20260919\report.md`（第 179 行把两份并列写着）
  - 宿主文件：`...\backend\data\app.db`；配额库：`...\backend\data\quota_used.sqlite`
  - 读数脚本（可复用）：`...\dispatch-output\hij-h-20260920\probe_real_db_readonly.py`
- **关键事实（我独立读到的现值，供你对账）**：宿主 `app.db` = `change_counter 10710 / size 19939328 / mtime 2026-09-17 02:37`；
  容器内那份 = `10784 / 20205568 / mtime 2026-09-19 00:28`（**不是同一个文件**）。
- **判据**：给一张「文件 → 路径 → cc/size/mtime → 谁在写 → 生产真源是不是它」的表 + 一条可复跑命令。
- **我不接受**：两份混在一句话里报；或对容器那份下结论却没实际读到它。

### T4 · 未跟踪资产清点（**只出建议，不许删**）

- **启动语**：在 `C:\Users\33393\Desktop\ai-legal-helper` 清点未跟踪资产并给入库/清理建议。
  **不许执行任何删除**。只写 `dispatch-output\t4-assets-20260920\`。
- **交付路径**：`...\dispatch-output\t4-assets-20260920\`（`inventory.md`、`classification.json`）
- **已知事实**：`git status --porcelain` 现值 = 全仓 **360** 项未跟踪（`docs\` 30 + `dispatch-output\` 299）。
- **判据**：按四类逐项归类「必须入库 / 建议入库 / 可清理 / 别动」，每项给路径与理由；
  "可清理"只**列清单**。
- **我不接受**：任何实际删除；把别人的在途产物算作自己的
  （例：`...\docs\code-review-report-02e3851-20260918.md` 正被另一会话改）。
- **附加要求（本轮新增）**：对 `dispatch-output\` 下的目录，**按磁盘占用从大到小排序取前 10 个**（给出排序命令与读数），
  逐个回答一句：**它背后还有没有"没落地的事"** —— 即：留着它是因为它是证据，还是因为它里面还有未完成的工作。
  （已知大概率进前 10 的：`_pt_r15full2\`、`_pt_r15tripwire_*\`、各条线自己的 `copytree\` / `beforetree\` / `mut-*\`。）

### T6 · I-6 同族普查：还有哪些调用点会漏掉带年份括注的库内源名

- **启动语**：在 `C:\Users\33393\Desktop\ai-legal-helper` 做一次**只读普查**：除
  `backend\retrieval.py` 的 `exact_article_lookup`（另一会话正在修）之外，还有哪些调用点用"source 精确匹配"，
  会漏掉库内带年份括注的源名（如 `宪法（1982年）`）。**只普查 + 出报告，不改代码**。只写 `dispatch-output\t6-sourcekey-survey-20260920\`。
- **交付路径**：`...\dispatch-output\t6-sourcekey-survey-20260920\`（`survey.md`、`call-sites.json`）
- **待判调用点（已实测存在）**：`...\backend\knowledge_service.py`、`...\backend\scripts\gen_gate1_law_check.py`、
  `...\backend\scripts\import_laws.py`（2 处）、`...\backend\scripts\import_docs.py`（2 处）
- **正确形态的参照实现**：`...\backend\retrieval.py` 的 `_source_key`（`article_in_kb` / `source_in_kb` /
  引用校验都在用它；它的 docstring 原文就点名了「宪法（1982年）」）。
- **已有测试锚点**：`...\backend\tests\test_citation.py`（断言 `_source_key("宪法（1982年）") == "宪法"`）。
- **判据**：逐调用点给「要不要 `_source_key` 容错」+ 理由 + 最小修法（或"不需修"的证据）。
- **我不接受**：只说"建议统一"而不逐点给理由；**另写一份"去括注"正则**（那就是第二份规则）。

### T7 · `options_fingerprint` 只有 60/279 的根因（**必须先于任何"补采"**）

- **启动语**：在 `C:\Users\33393\Desktop\ai-legal-helper` 做**只读**诊断：语料 `qa_pairs` 里
  `options_fingerprint` 只有 60/279，而带选项的记录有 166 条 —— **为什么缺**？补采能把覆盖提到多少？
  **只读、只算、不写真实语料**。只写 `dispatch-output\t7-fingerprint-coverage-20260920\`。
- **交付路径**：`...\dispatch-output\t7-fingerprint-coverage-20260920\`（`report.md`、`recompute.json`）
- **输入路径**：
  - 已有清点（**别重做**）：`...\dispatch-output\i1-e2-hitrate-20260920\`
  - 语料写入者：`...\backend\scripts\gen_qa_corpus.py`；题库来源：`...\backend\qa_seeds.py`
  - 指纹函数：`...\backend\query_understand.py` 的 `_options_fingerprint`
  - 读侧护栏：`...\backend\main.py` 的 `_qa_direct_return`
  - 只读盘点脚本（含逐条备份，可复用）：`...\dispatch-output\hij-i-20260920\probe_i2_corpus_inventory.py`
- **判据**：① 60 条的指纹是**谁在哪一步写进去的**（代码出处）；② 用 `_options_fingerprint` 对 279 条**现算一遍**，
  给出"理论上可提取"的条数；③ 明确回答补采能把覆盖面提到多少（**给数**）。
- **我不接受**："建议补采"而没有上面的**数**；拿 60 当分子却说覆盖 279（分母口径要写给谁）。
- ⚠️ **它的"补采"实现与票 I 的语料写入必须串行**（见 §4）。

### T8 · E2 出口（QA 持久语义缓存直返）有没有票 J 那类多选缺口

- **启动语**：在 `C:\Users\33393\Desktop\ai-legal-helper` 做**只读**调查：E2 出口是否也存在
  "多选题只给一个正确项却能零 token 直返"的缺口（票 J 只对齐了轻量出口 E7）。只写 `dispatch-output\t8-e2-multi-20260920\`。
  **不许改 E2 的三道既有护栏**。
- **交付路径**：`...\dispatch-output\t8-e2-multi-20260920\`（`report.md`、`probe.json`）
- **输入路径**：登记表 E2 行（`...\backend\gate_exit_registry.py` 里 `"id": "E2"` 那段）；
  读侧实现 `...\backend\main.py` 的 `_qa_direct_return`；判据函数（**复用**）`...\backend\quality.py` 的 `multi_incomplete`；
  端点级夹具 `...\backend\tests\_sse_harness.py`；票 J 的同类修复可参照 `...\backend\tests\test_light_exit_gates.py`
- **判据**：① 实测"多选题 + 语料只声明一个正确项"能不能直返；② 量化它属于**会命中**还是**理论可达**；
  ③ 给"要不要补判定"的结论**并写清权衡**。
- **我不接受**：只说"应该加上"而无权衡 —— E2 的卖点恰恰是零 token 直返，加判定就是削弱该卖点。

### T9 · 评测可信度两格 `BLOCKED` 的「绕开清单」

- **启动语**：在 `C:\Users\33393\Desktop\ai-legal-helper` 做**只读**整理：登记表里 E1/E2 的「评测可信度」
  两格是 `BLOCKED`（既有事故：`qa_cache` 污染 judge 基线，0.43/0.57/0.64 三个数全失真）。
  产出一份「跑评测时必须绕开什么」的清单。只写 `dispatch-output\t9-eval-credibility-20260920\`。
- **交付路径**：`...\dispatch-output\t9-eval-credibility-20260920\`（`checklist.md`、`findings.json`）
- **输入路径**：`...\backend\main.py`（`record("qa_cache", ...)` 与 `body.no_cache`）、
  `...\backend\tests\test_light_exit_gates.py`（no_cache 用法样例）、
  `...\dispatch-output\i1-e2-hitrate-20260920\`、`...\docs\project-quality-guide-20260914.md`
- **判据**：逐条给「要绕开什么 + 代码出处（文件 + 符号）+ 今天是否已被防住（是/否 + 证据）」，
  产出可直接贴进评测批 checklist 的清单。
- **我不接受**：只说"要注意缓存"而不给"哪一行、哪个开关、哪条命令"。

### T10 · `DISABLED` 11 格 + `GAP-ACCEPTED` 5 格的语义分类

- **启动语**：在 `C:\Users\33393\Desktop\ai-legal-helper` 做**只读**口径整理：登记表里 `DISABLED` 11 格、
  `GAP-ACCEPTED` 5 格，逐格判定它属于哪一类语义。只写 `dispatch-output\t10-disabled-taxonomy-20260920\`。
  **不许改词表**（`PARTIAL` 已被裁为不加）。
- **交付路径**：`...\dispatch-output\t10-disabled-taxonomy-20260920\`（`taxonomy.md`、`cells.json`）
- **输入路径**：真源 `...\backend\gate_exit_registry.py`；词表出处 `...\docs\capability-matrix.md`（开篇写「状态只有三种」）；
  本轮扫描读数 `...\dispatch-output\hij-h-20260920\23-sweep-nonpass-cells.json`（非 PASS/NA 的 20 格与
  PASS 但带"未完成语义"的 10 格清单）
- **判据**：逐格判定属于「结构性不适用 / 今天零流量 / 真缺口已裁定接受 / 真缺口待修」之一 + 引用取证原文；
  对"该不该拆词"给建议（**但不许改**）。
- **我不接受**：把"今天零流量"和"结构不适用"混为一谈（这正是本轮扫出来的问题）。

### T11 · 补一次全量测试门禁（**必须串行，不能与票 I 并行**）

- **为什么单列**：`d4b8d79..HEAD` 期间 `backend/` 下含**生产码**被多条并行线改过
  ⇒ **当前 HEAD 上没有全量绿证**。这不是修 bug，是给"HEAD 是好的"这句话补仪器。
- **⚠️ 串行原因（关键）**：它要在 **live 树**跑全量门禁（隔离指纹读真实 `backend\app.db` / `quota_used.sqlite` /
  `chroma_db` 整目录 ⇒ 在副本树里那三条"前后未变"退化成恒真、RUN_VALID 不成立）。
  而票 I 此刻**正在改 live 树的 `main.py`** ⇒ 门禁轮期间有 `.py` 被改动 ⇒ 整轮 **RUN_VOID**。
  **⇒ 只能在票 I 收工（或明确暂停）之后跑。**
- **权威细节（务必先读，别只照本卡）**：`C:\Users\33393\Desktop\ai-legal-helper\docs\handoff-takeover-20260919.md`
  —— 它是一份**已经写好的完整接手票**（含 §1 前置取证 P1–P7、§3 A1 的确切命令与分诊表、§4 不许动清单、
  §5 收口纪律、§6 命令写法四坑）。**转发时应与本卡一起转发该文件。**
- **交付路径**：产物落在 `...\dispatch-output\te-chroma-isolation-20260918\`（按该文件的命名：
  `gate-<标签>.log` / `gate-<标签>-source-sha.json` / `gate-<标签>-verdict.txt`）
- **命令（照抄，标签自取）**：
  `cd C:\Users\33393\Desktop\ai-legal-helper\backend` 然后
  `./venv/Scripts/python.exe ../dispatch-output/te-chroma-isolation-20260918/run_gate_full.py <你的标签>`
  **不许裸跑 pytest**（裸跑出的红在多会话工作树里无法归因）。
- **判据（两类别混）**：回归判据 = pytest 退出码 + 末行计数，**仅在 `verdict = RUN_VALID` 时有效**；
  隔离判据 = 真实 `backend\chroma_db` 清单前后一致，**`RUN_VOID` 时依然有效**。
- **我不接受**：`RUN_VOID` 时报"全量绿"（该轮 passed/failed 作废）；把
  "database is locked"照抄成"已知 flake"放行（该字符串在 `backend\` 的 `.py` 里 0 命中，从未复现）。

### T12 · 前端面普查（本会话一格没碰过）

- **启动语**：在 `C:\Users\33393\Desktop\ai-legal-helper` 做一次**只读**普查：`frontend\` 目录下
  有没有**未落地的核实工作**（例如：文档里承诺过但前端未实现/未验证的点、构建是否可跑、
  与后端接口的契约是否对齐）。只写 `dispatch-output\t12-frontend-sweep-20260920\`。**不改前端代码。**
- **交付路径**：`...\dispatch-output\t12-frontend-sweep-20260920\`（`report.md`）
- **输入路径**：`...\frontend\`（注意 `node_modules\` 很大，**不要**递归读）；
  `...\docs\frontend-*.md`（多份未跟踪文档，含执行书与评审）；`...\docs\ADR.md` 里的前端相关条目
- **边界（把"只读"讲准，免得自相矛盾）**：允许跑**已存在的**构建命令（它会写 `frontend\.next\` 之类的构建产物 ——
  这是**本卡唯一允许**写在交付目录之外的写入，**必须在报告里写明它实际写了哪些目录**）；
  **禁止** `npm install` / 改 `package.json` / 改任何前端源码；**禁止**递归读 `node_modules\`（很大）。
- **判据**：明确回答三件事 —— ① 有没有**可执行的**待办（有则给出处，无则明说"无"）；
  ② 构建命令今天能不能跑通（跑就贴产物路径 + 退出码；跑不通报错因原文，并区分"缺依赖"与"真失败"）；
  ③ 有没有与后端契约不一致的证据（接口路径/字段/错误码逐项对）。
- **我不接受**：把"我看了一眼觉得没问题"当结论；或顺手改前端代码。

---

## §4 并行冲突矩阵（照这张表决定能不能同时开工）

| 任务 | 写 live 树产品码？ | 跑 live 全量？ | 写真实语料？ | 可与票 I 并行？ | 备注 |
|---|---|---|---|---|---|
| T1 flaky | 否 | **否（必须自己的副本树）** | 否 | ✅ | 最高优先 |
| T2 slow | 否 | **是（只能在 live 树跑 `-m slow` 子集：需真实 KB）** | 否 | ❌ **必须串行** | 同 T11：与票 I 抢 live 树 |
| T3 app.db | 否 | 否 | 否 | ✅ | **绝对只读** |
| T4 资产清点 | 否 | 否 | 否 | ✅ | **不许删** |
| T6 同族普查 | 否 | 否 | 否 | ✅ | 只读源码 |
| T7 指纹根因 | 否 | 否 | **否（只算）** | ✅ | 其"补采"实现必须与票 I 串行 |
| T8 E2 多选 | 否 | 否 | 否（只读语料） | ✅ | 不许改 E2 护栏 |
| T9 评测可信度 | 否 | 否 | 否 | ✅ | 只读 |
| T10 词表分类 | 否 | 否 | 否 | ✅ | **不许改词表** |
| T12 前端普查 | 否 | 否 | 否 | ✅ | 只读 |
| **T11 全量门禁** | 否 | **是（必须 live）** | 否 | ❌ **必须串行** | 与票 I 撞 RUN_VALID |
| 票 I（另一会话） | **是** | 仅在无人在跑时 | **是**（已获授权） | — | — |

**必须串行的四处**：① **T11** 与票 I（RUN_VALID 冲突）；② **T2** 与票 I（同样要在 live 树跑）；
③ T7 的"补采"实现与票 I 的语料写入（同一份 `qa_pairs`）；④ 任何"回表"动作彼此
（都写同一份 `docs\gate-exit-registry.md`）。
⇒ 一句话：**只有"纯只读"的 9 张卡能真并行**；凡是要碰 live 树或真实语料写入的，都要排队。

---

## §5 需要 Owner 裁决才能开工的（**不要当任务派出去**）

| 事项 | 出处 | 卡在哪 |
|---|---|---|
| `scope_trigger` 升格为验收判据（P1-6） | `...\docs\progress-and-backlog-20260919.md` §5-B1 | 升格=改判据读取端；且"只作记录"那句已写在**冻结文件**里 ⇒ 照字面改就是破冻结 |
| 词表收紧（专有名词白名单） | 同上 §5-B2 | 改词表=改生产语义；需先给误伤样本的 watch-it-fail |
| T-K 跨域引用收紧 | 同上 §5-B3 | 执行书 `docs\execution-plan-entity-precision-20260917.md` 明写"不再投入"与"须 Owner 明确推翻" |
| T-H 过度保守修复（B4） | 同上 §5-B4 | **需付费额度** |
| P1-4 REWRITE 不触发第二轮 writer（B5） | 同上 §5-B5 | 生产语义 |
| 合同分支「静默空」是否补 error 帧 | 票 H 报告 `...\dispatch-output\hij-h-20260920\report.md` | 改用户可见行为，超票 H-2 射程 |
| 带告警/降级报告不进缓存的价格 | 票 H-1 已实现并登记代价 | 是否接受"同题重问会重烧 token" |
| 登记表「今天不命中的条件门」统一状态词 | 本轮已裁 `PARTIAL` **不加** | 若仍想统一，需 Owner 指定词与真源改动范围 |
| **R15 四项 P1**（限时法条适用链） | `...\docs\code-review-report-02e3851-20260918.md` 里**另一会话**新写的一节 | **动 `backend\agent\limitation_calc.py` + `main.py` ⇒ 与票 I 抢单点资源 ⇒ 只能排队**；且它属他人产出，需 Owner 决定是否立项 |
| ADR-018 已知残留 ④（快车道检索 cutoff 不随 `law_as_of` 变） | `...\docs\ADR.md` §已知残留④ | 结构性不对等（快车道无 run 对象），ADR 自己写明"不是实现缺陷" |

---

## §6 诚实登记：仍然没扫过的面

1. **另一会话 R15 四项 P1 的细节** —— 我只知道它的标题与位置，**没读过完整论证**（那属于他人产出区，本轮只在冲突矩阵里标了它抢资源）。
2. **`dispatch-output\` 里 299 项未跟踪资产"背后有没有未落地的事"** —— T4 只清点分类。
3. **前端面的实际工作量** —— T12 就是为回答它而设的普查。
4. **`-m slow` 那 18 条之外**，是否有别的 marker/opt-in 用例从未在门禁里跑过 —— 未查。
5. **"未扫面"这件事本身**：本清单仍是"扫出来的"，不是"枚举证明出来的"；
   若要更强，办法是把 §1 的三个单点资源 + §3 的 12 张卡对所有 `docs\*.md` 与本轮扫描产物做一次交叉覆盖检查。

---

## §7 建议的开工顺序

```
第一波（可同时开工，互不干扰 · 9 张）：T1（优先）· T3 · T4 · T6 · T7 · T8 · T9 · T10 · T12
                              ↓ 全部收工
第二波（必须独占 live 树 · 2 张，且要等票 I 收工）：T2（-m slow）· T11（全量门禁）
                              ↓
本文件之外：R15 四项 P1 与 ADR-018 残留④ 需要 Owner 先决定立项（它们与票 I 抢 main.py）
```

---

## §8 速查：每张卡的交付目录（唯一写集）

| 任务 | 交付目录 |
|---|---|
| T1 | `C:\Users\33393\Desktop\ai-legal-helper\dispatch-output\t1-flaky-20260920\` |
| T2 | `C:\Users\33393\Desktop\ai-legal-helper\dispatch-output\t2-slow-20260920\` |
| T3 | `C:\Users\33393\Desktop\ai-legal-helper\dispatch-output\t3-appdb-20260920\` |
| T4 | `C:\Users\33393\Desktop\ai-legal-helper\dispatch-output\t4-assets-20260920\` |
| T6 | `C:\Users\33393\Desktop\ai-legal-helper\dispatch-output\t6-sourcekey-survey-20260920\` |
| T7 | `C:\Users\33393\Desktop\ai-legal-helper\dispatch-output\t7-fingerprint-coverage-20260920\` |
| T8 | `C:\Users\33393\Desktop\ai-legal-helper\dispatch-output\t8-e2-multi-20260920\` |
| T9 | `C:\Users\33393\Desktop\ai-legal-helper\dispatch-output\t9-eval-credibility-20260920\` |
| T10 | `C:\Users\33393\Desktop\ai-legal-helper\dispatch-output\t10-disabled-taxonomy-20260920\` |
| T11 | `C:\Users\33393\Desktop\ai-legal-helper\dispatch-output\te-chroma-isolation-20260918\`（按既有命名） |
| T12 | `C:\Users\33393\Desktop\ai-legal-helper\dispatch-output\t12-frontend-sweep-20260920\` |

**相关但**不属本清单**的文件（可一并转发）**：
- 权威接手票（T11 必读）：`C:\Users\33393\Desktop\ai-legal-helper\docs\handoff-takeover-20260919.md`
- 待办四类清单（含 Owner 裁决项）：`C:\Users\33393\Desktop\ai-legal-helper\docs\progress-and-backlog-20260919.md` §5
- H/I/J 三票票面与判据口径：`C:\Users\33393\Desktop\ai-legal-helper\docs\handoff-gap-tickets-h-i-j-20260920.md`

---

## §9 复审记录（2026-09-20 写完后立即自查）

**方法**：不看草稿记忆，按"执行者视角"逐卡自问四问 ——
① 能不能**照着做**（有没有确切命令/路径）？② 判据能不能**被第三方判定**（有没有含糊词）？
③ 卡与卡之间**有没有互相矛盾**？④ 有没有**必须读别的文件才知道怎么做**的死角？

**查出 8 条，全部已改**（改动都在本文件内，下面逐条说明，便于对照）：

| # | 问题（歧义/不清楚） | 性质 | 处置 |
|---|---|---|---|
| 1 | §0 说"不能并行的只有票 I"，但 T11 明明也串行 ⇒ 自相矛盾 | **硬矛盾** | 已订正为"**9 张可并行 / 2 张串行（T2、T11）**" |
| 2 | **T2 被误列为"可并行"** —— 它要真实 KB（`real_kb` fixture），而 `conftest` 在测试层把 `CHROMA_DIR` 指向进程私有临时目录 ⇒ 副本树里只会 skip ⇒ 只能在 live 树跑 ⇒ 与票 I 互斥 | **实质性错误**（最严重的一条） | T2 卡加 ⚠️ 说明；§4 矩阵该行由 ✅ 改 ❌；§7 顺序把它移入第二波 |
| 3 | T1 只有"副本树搭法"，**没有确切 pytest 命令行** ⇒ 执行者得自己拼 | 描述不清楚 | 已补完整命令行（含 `--junitxml`、`--basetemp`、输出重定向），并点明 `-m "not slow"` 与"唯一 basetemp"两个必踩点 |
| 4 | T1 的 commit 该用哪个有歧义（写死了 `1e969f2`，但执行者可能取不到） | 描述不清楚 | 已写明：**优先 `1e969f2`**（与已有 0/3/8 三次读数同树可比），取不到则用开工时 HEAD 并**把 hash 写进报告** |
| 5 | T2 同样缺确切命令行 | 描述不清楚 | 已补两条完整命令（`-m slow` / `-m "not slow"` 各一） |
| 6 | T4 的"体量最大的几批"**不可判定**（谁算最大？几批?） | 含糊 | 已改为"按磁盘占用**排序取前 10**，并给出排序命令与读数" |
| 7 | T12 自相矛盾：声明"只读"，却要求跑 `npm run build`（build 必然写盘） | **硬矛盾** | 已把边界写准：允许跑**已存在**的构建命令，但必须**报告它实际写了哪些目录**；禁止 `npm install`/改源码/递归读 `node_modules` |
| 8 | §2 第 9 条"证据要入库"没说清**哪些件** 入库 | 描述不清楚 | 本条补充：**至少 `report.md` 入库**（`git add <显式路径>` + 手跑 pre-commit）；junit / `copytree\` / `bt*\` 这类大体积中间产物**不入库** |

**复审后仍然存在的三条已知不足（如实标注，不假装已解决）**：
1. **判据可判定但不机器化**：每张卡的判据都能被人判定，但没有"一键验收脚本"⇒ 验收要靠 Owner 侧人工复跑。
2. **T11 对外部文件有硬依赖**：它的完整判据在 `docs\handoff-takeover-20260919.md` 里，本卡只给"最小可执行 + 指路"。
   ⇒ **转发本文件时应一并转发那一份**（本卡内已标红注明）。
3. **§6 的"未扫面"是真话**：本清单是"扫出来的"，不是"枚举证明出来的"；要做到枚举级，
   需要把 §1 的三个单点资源与 §3 的卡片对 `docs\*.md` 和本轮扫描产物做一次交叉覆盖检查（尚未做）。
