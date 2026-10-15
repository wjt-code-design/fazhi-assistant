# 版本安全复核报告（T1/T2 工作区修复）— 2026-09-27

派单：`C:\Users\33393\Desktop\ai-legal-helper\docs\assistant-briefs\version-safety-review.md`
复核人：Qoder 会话（只读复核）；执行时间 2026-09-27 15:58 – 16:32（本机）。

## 0. 一页汇总

**结论**：**未发现"会误删法律片段"或"错误允许冲突版本进库"的新确证缺陷。**
收紧后的两条判据在真实语料上是活的、删得对、且判据本身有牙（改前实现上 20 条红，其中 **11 条钉的就是判据方向**）。

发现 **1 项需要 Owner 决定的行为回归（中）** + **3 项低severity** + **8 条仍需人工的限制（含新量化的数字）**。
本报告做过**两轮**：第二轮的三件新仪器与"抓到我自己第一版两处错"记在 §6。

| # | 严重度 | 一句话 | 要我做什么 |
|---|---|---|---|
| 1 | 中 | 管理端"无生效日重传同一条文"从**替换**变成**静默并存**，且旧的无日期块此后**永远清不掉** | 选 ①端点拒绝空日期 或 ②响应里报出未替换块数（推荐 ①） |
| 2 | 低 | 写侧 `except Exception` 把"判定崩溃"与"判定后保留"混成同一个结果，无日志 | 一行 `logging.warning` + 登记白名单字段 |
| 3 | 低 | `ReplacementPlan` 丢了"为什么必须分桶"的理由注释，两个新 helper 换英文注释 | 把理由补回，别补语言规范 |
| 4 | 低 | 批内"可安全并存"的两代条文**一行都不打印** | 复用 `LINE_HISTORICAL`，措辞改"本批内" |

**被复核的快照**（HEAD `7eda4bb`，工作区未提交；收口时复量与开工一致 ⇒ 结论针对这份码）：

```
eac495bc5b69  C:\Users\33393\Desktop\ai-legal-helper\backend\law_versions.py        (mtime 09-27 15:06)
405d3a02c621  C:\Users\33393\Desktop\ai-legal-helper\backend\knowledge_service.py   (15:09)
746725317cad  C:\Users\33393\Desktop\ai-legal-helper\backend\scripts\import_laws.py (15:09)
354275c08199  C:\Users\33393\Desktop\ai-legal-helper\backend\tests\test_law_versions.py (15:07)
5d377af20cc3  C:\Users\33393\Desktop\ai-legal-helper\backend\tests\test_import_laws_preflight.py (15:10)
```

**边界自证**：未编辑任何既有文件（只新增本报告与 `dispatch-output\version-safety-review-20260927\` 里的探针脚本）；
真实知识库零改动 —— `backend\chroma_db\chroma.sqlite3` 开工与收口两次复量同为
`sha256` 前缀 `b551677bddab4b85`、mtime 仍 `2026-09-21 02:06:44`；未调模型/云（`LLM_BASE_URL=http://127.0.0.1:9/v1`
+ 假 key + `EMBEDDING_PROVIDER=local`）；所有写入只发生在私有副本
`C:\Users\33393\AppData\Local\Temp\vsr-review-20260927\`（`chroma_db` 已导入态 / `chroma_pristine` 原始态 / `empty_*` 空库）。

---

## 1. 先说成立的部分（每条都是本机实跑，不是推理）

### 1.1 T1 的遗留块判据在真实语料上"活着"，且删掉的两块正文完整一致

`docs/h1-law-version-collision-tickets-20260926.md` §0 记的旧读数是"**将替换 0**"（判据永不触发）。
工作区码在真实库副本上的读数（私有副本，非共享 TEMP）：

```
共 3 条，开始预检：
  将替换 1 旧片段 + 新增：民法典 第一千二百六十条
  ⚠️ 与 1 条无时效旧块并存（将被 T1 取代）：民法典 第一千二百六十条
  将替换 1 旧片段 + 新增：劳动争议调解仲裁法 第二十七条
  ⚠️ 与 1 条无时效旧块并存（将被 T1 取代）：劳动争议调解仲裁法 第二十七条
  将替换 0 旧片段 + 新增：合同法 第四百二十八条
预检完成：将删除 2 旧片段（其中 2 条是无时效遗留块），新增 3 条，跳过 0 条。
```

与汇报 §9.11 声称的"替换 2 / 新增 3 / 跳过 0，rc=0"**逐字一致**（该声称成立）。空集合假绿已排除：
同一轮 `collection.count() = 10266`。

**但"数字对上"不等于"删得对"**，所以逐块看了残差（`probe_dump.py`，原始串直印）：

| 条文 | 旧块（归一后长度） | 新块（归一后长度） | 被容忍的差异 |
|---|---|---|---|
| 民法典 1260 | 165 字 → 141 | 141 字 → 141 | 首行章节"第十章　建筑物和物件损害责任" + 条号"第一千二百六十条" + 全角空格 |
| 调解仲裁法 27 | 290 字 → 272 | 275 字 → 272 | 首行章节"第三章　仲　　裁" + 条号"第二十七条" + 空白 |

⇒ 两块都是 `old_after_known_prefix == new` **逐字相等**，漏句/漏款/未知前缀一条都没有。
`_same_article_body`（`law_versions.py:25-38`）确实是"完整正文一致"而不是包含关系。

### 1.2 替换之后丢掉的"章节行 + 条号"没有可测的召回代价

这条此前**没人量过**（§9.11 只跑了改前 `smoke_citation_fast`）。因为 `retrieval_core.build_bm25` 只对
`page_content` 分词（`retrieval_core.py:200-204`），新块正文里不再含"第十章 建筑物和物件损害责任""第一千二百六十条"
这些字面 ⇒ 理论上有丢词面。做了改前/改后逐位对照（同一棵私有副本，先跑 8 题，**真实导入**，再跑同 8 题 + 4 题专攻丢词）：

```
lines before/after: 43 43
rank/source/article differences: 0
text-head differences: 4
```

专攻丢词的 4 题（"第十章 建筑物和物件损害责任" / "建筑物和物件损害责任这一章的最后一条…" /
"第三章 仲裁 劳动争议" / 裸条号"第一千二百六十条"）在 PRISTINE 与 IMPORTED 两态下 top-6
**法名/条号逐位相同**。⇒ 该丢词面**今天不改变任何一次召回位次**。

**第二轮补的更强仪器**（§1.2 第一版只有我自己挑的 12 题，代表性不足）：把仓库自带的门禁
`scripts/smoke_citation_fast.py` 在两态副本上各跑一遍：

```
SMOKE_pristine_RC=0   fast 门禁：24/24 通过   [FAIL] 行数 0
SMOKE_imported_RC=0   fast 门禁：24/24 通过   [FAIL] 行数 0
```

⇒ 同一离线口径下，导入前后**都是 24/24**，替换没有把这道门禁打红。
（口径限制见 §4 第 5 条：`EMBEDDING_PROVIDER=local` + `RERANK_ENABLED=false`，生产云端重排未覆盖；
这条**不能**用来关闭 §9.9 在原配置下那 23/24，两件事口径不同。）

### 1.3 收紧后的判据有牙（尺子能红）

把改后的两个测试文件覆盖到一棵 HEAD 码的副本树上跑（`redcheck` 树，只读原树）：

```
20 failed, 19 passed, 1 warning in 20.74s     ← 用例级 20 条 = 8 个 def 家族（含参数化展开）
  test_undated_legacy_copy_is_not_replaced_by_truncated_article
  test_missing_new_date_does_not_bypass_complete_body_check
  test_empty_version_ids_do_not_bypass_complete_body_check
  test_derived_version_id_without_dates_does_not_delete_different_body
  test_same_version_id_never_deletes_seed
  test_undated_legacy_copy_requires_known_prefix
  test_nonoverlapping_dated_versions_are_compatible / test_old_end_before_new_start_...
  test_overlapping_or_unverifiable_dated_versions_still_conflict[5 个参数]
  test_non_contained_block_is_called_out / test_overlapping_dated_version_is_reported_as_time_conflict
  test_writer_keeps_complete_legacy_article_when_new_text_is_truncated
  test_dry_run_keeps_nonoverlapping_historical_version[2 个参数]
  test_same_article_batch_duplicate_or_overlap_blocks_before_writing[2 个参数]
```

⇒ **这些红是断言级的，不是 collection 期炸出来的**（无收集错误）。第二轮改用 `--junit-xml` 逐用例映射
（第一版用 `--tb=line` 抽错误行，**漏计 1 条**——见 §6），20 条红的准确分布是：

- **11 条决策方向红**：6 条 `assert ['d0'] == []`（旧实现把该保留的判成**可删**：截断新文 / 空日期 /
  空 version_id / 派生 ID 相同但正文不同 / seed 块 / 未知前缀）、1 条写侧旧块被真删
  （`test_writer_keeps_complete_legacy_article_when_new_text_is_truncated`）、
  2 条 `SystemExit: 1`（旧实现会把可安全并存的历史版本**整批误拦**）、
  2 条 `冲突批次不应开始写入`（旧实现没有批内查重，会直接开始写）。
- **2 条报警文案红**（`未判定冲突` vs 旧文案 `互不包含`）——钉的是措辞不是判据。
- **7 条 `AttributeError`**（旧实现根本没有 `conflicts` / `compatible_versions` 这两个名字）——只钉形状。

⇒ 也就是说"新判据被证伪"这一类实际是 **11 条**，不是全部 20 条；那 7+2 条只是签名/文案漂移。
`conflicts`、`compatible_versions` 这两个新名字的**语义**由上面 11 条里的 4 条（2 条"整批误拦"＋2 条"批内查重"）
与 §1.6 的三形状独立实测兜着 —— 那 4 条读的是判定结果，不是属性存在性。
取数命令在 §5，逐用例映射原文在 `dispatch-output\version-safety-review-20260927\redcheck_junit_map.txt`。

### 1.4 全量差分：本轮改动没有把别处打红

两棵私有副本树（`git archive HEAD` 基线 + 只 overlay 7 个改动文件）各跑一遍全量：

```
base_RC=1     12 failed, 1547 passed, 25 skipped, 145.61s
patched_RC=1  12 failed, 1568 passed, 25 skipped, 176.70s
=== ONLY IN PATCHED (regressions) ===   (空)
=== ONLY IN BASE (fixed) ===            (空)
```

那 12 条两侧同现（副本树缺 `release-evidence/`、仓库根 md、`sample_laws` 一类未跟踪件：
`test_chunking`×7、`test_eval_agent`×2、`test_gate5_judge_layers`×1、`test_gate_exit_registry`×1、
`test_init_release_evidence`×1 —— 名单与逐条 node id 已存
`dispatch-output\version-safety-review-20260927\base.failed` / `patched.failed`，`diff` 结果为**逐字节相同**），
差集为空才是回归证据 ⇒ **零回归**，+21 通过数 = 新增用例。

### 1.5 边界语义与读侧一致

`_periods_do_not_overlap`（`law_versions.py:41-52`）用**严格 `<`** 判分离；读侧
`retrieval_core.is_valid_by_time` 是 `if et and et < today: return False`（`:57`）⇒ `effective_to`
当日仍有效（含端），与已签的 B 口径"最后有效日（含）"同源。相邻更替（旧止 2020-12-31 / 新起 2021-01-01）
判"可并存"，同日重合（旧止 = 新起）判冲突 —— 两侧都有用例钉住。

### 1.6 批内查重三形状独立实测（不依赖仓库自带用例）

对**空**私有库跑合成批（`受控复核法 第一条`），验证 T2 既不误拦也不漏放：

| 批内容 | 结果 |
|---|---|
| 旧版 1995-01-01→2021-12-31 ＋ 新版 2022-01-01 | rc=0，"新增 2 条" |
| 顺序倒过来（新版在前） | rc=0，同上 ⇒ 判定与批内顺序无关 |
| 丙版 2020-01-01（无止日）＋ 2022-01-01 | `OVERLAP_PY_RC=1`，打印"整批未写入任何内容"，且**一条都没写**（被"写了但被桩吞掉"排除：库仍空） |

（第三条的 rc 是**单独取**的，没走管道 —— 前两条形如 `RC=0` 那行取自管道尾，不作主张。）

### 1.7 静态检查与消费者一致性

`ruff check .` rc=0；`ruff format --check .` = 265 files already formatted；`mypy .` rc=0（73 source files）
—— 与 §9.11 自述一致，且 §9.11 那句"mypy 的既有 `scripts/` 排除范围没有变化"**成立**（`import_laws.py` 不在类型检查面里）。
全仓 grep 消费点：除 `import_laws.py:203-233`（读 `conflicts`/`compatible_versions`）与
`knowledge_service.py:212-222`（只读 `.replaceable`）外，**没有别处还在用 `.coexist` 做阻断** ⇒ 无漏改消费者。

---

## 2. 确证问题（按严重度）

### 中-1 管理端"无生效日重传"由替换变静默并存，且旧的无日期块事后清不掉

- **位置**：判据 `C:\Users\33393\Desktop\ai-legal-helper\backend\law_versions.py:133-140`
  （`same_version` 新增 `effective_from` 非空前置）；放大点
  `C:\Users\33393\Desktop\ai-legal-helper\backend\knowledge_service.py:212-222`（写侧只消费 `replaceable`，
  `conflicts` 既不删也不报）；触达面 `C:\Users\33393\Desktop\ai-legal-helper\frontend\app\admin\sections\KnowledgeSection.tsx:45`
  与 `:72`（表单默认 `effective_from: ""`，提交时 `|| undefined`）；端点
  `C:\Users\33393\Desktop\ai-legal-helper\backend\main.py:2668-2683`（响应只有 `added_chunks`）。
- **触发条件**：管理员两次提交同一（法律名, 条号）而**不填生效日** —— 即表单的**默认态**，
  典型动作是"发现错别字，回去再提交一次"。
- **实际 vs 预期**：预期要么替换、要么明确拒绝；实际是**静默并存**，事后补日期也救不回来。
- **复现证据**（同一脚本跑两棵树，输出原文）：

```
tree: ...\vsr-review-20260927\base\backend      has _same_article_body: False
  add#1 returned 1, add#2 returned 1
  blocks for (受控探针法,第一条) after two undated saves = 1
  VERDICT REPLACED(no duplicate)
  after a third save carrying effective_from=2024-01-01: blocks=2

tree: ...\ai-legal-helper\backend               has _same_article_body: True
  blocks ... after two undated saves = 2
  VERDICT DUPLICATED (+1 extra blocks)
  after a third save carrying effective_from=2024-01-01: blocks=3
```

  两次保存的块 `version_id` **相同**（`lv-ebc948079dd60fe4c315f36f`）⇒ 不是"两个不同版本"，是同一身份的两份正文。
  第三次带日期写入后仍留 3 块 ⇒ 那两份无日期旧块**从此不在任何自动替换判据的射程内**（`same_version`
  要日期相等、`legacy_undated` 要 `origin ∈ {upload, manual}` 且无 `version_id`，而它们带着 `version_id`），
  只能靠 `DELETE /api/admin/knowledge/{id}` 逐条手删。代价面本仓已量过：同一条文占两格会把别的法**挤出 top-k**
  （票 T1 §净效果：`-2 挤出`）。
- **为什么这不是"已记录的在册限制"**：§9.11 只写了抽象一句"无生效日的 manual/import 重传…重复输入可能并存"。
  它没有说 (a) 触发条件是管理表单的**默认态**而非异常输入；(b) 事后补日期**不能**回收，即并存是**单向棘轮**；
  (c) 端点/日志**零信号**，且**没有任何测试覆盖端点这一层**（`tests/test_phase5.py:108-137` 只 POST 一次且带日期；
  单元层 `test_derived_version_id_without_dates_does_not_delete_different_body` 钉的是判据本身，不是这个后果）。
- **最小修复建议（推荐 ①）**：
  ① 在 `schemas.py:154` 的 `KnowledgeAddIn` 加一条 model 级校验：`article` 非空时 `effective_from` 必填。
     与本仓已签方向一致（"缺失不是安全状态"、`status` 已从默认值改成必填），改动面一个函数 + 一条用例。
  ② 或保留现判据、把沉默变成信号：`add_text` 返回 `(n, kept_conflicting_old_blocks)` 太重，
     改在 `knowledge_service.py` 里对 `plan.conflicts` 打一条 `logging.warning`（字段须登记进
     `observability._ACCOUNT_FIELDS`，否则 `_JsonFormatter` 会**静默丢弃** —— 本仓 2026-09-25 踩过），
     并在 `main.py:2683` 的响应里带 `unreplaced_old_chunks` 供前端提示。
  ①②可以同时做；**不建议**为了"让它替换"而回退 `effective_from` 非空这条前置（那正是本轮防的误删）。

### 低-2 写侧的 `except Exception` 让"判定崩溃"与"判定后保留"长得一模一样

`knowledge_service.py:223-224`：判据整段包在 `except Exception: stale_ids = []` 里，无日志。
收紧后判据的默认侧就是"保留"，于是这条静默面的代价变高：**将来任何一次签名/类型错都会退化成"永不替换"，
而所有测试照样绿**（新用例 `test_writer_keeps_complete_legacy_article_when_new_text_is_truncated`
断言的是"旧块还在"，崩溃路径同样满足）。
**这条不是推理，第二轮做了变异**：在副本树（`patched` 树，仓库文件逐字节未动、跑完复量哈希相同）上把
`_same_article_body` 首行注入 `raise RuntimeError` ⇒

```
被注入崩溃后单跑写侧那条：  1 passed in 21.99s      ← 判据根本没跑，用例照样绿（盲区确认）
同一注入单跑 tests/test_law_versions.py（25 条）：  22 failed, 3 passed   ← 单元层有牙，只有写侧这条瞎
```
最小修复：`except Exception` 分支里补 `logging.warning("法版本判定失败，按不替换处理", exc_info=True,
extra={"law_version_judgment_failed": True})` 并登记字段；配一条"注入异常 ⇒ 日志里看得见那个键"的腿
（本仓 `test_client_law_as_of_gate.py` 已有同款形状）。**先前存在，非本轮引入**，但归口在这里更省事。

### 低-3 单一真源的理由注释被换掉了

`law_versions.py:86-101` 的 `ReplacementPlan` docstring 从"为什么是四个桶／不许调用方自己再判一遍
（本仓为 `_source_key`、`is_valid_by_time` 立的都是单一真源规矩）"压成了一句英文；新增的
`_same_article_body`、`_periods_do_not_overlap` 注释也是英文，而本文件其余 docstring 是中文带 ⚠️ 理由
（例如 `:15-22` 那条"别把 `\u3000` 当可测性"）。`CONTRIBUTING.md` 没有语言条款 ⇒ 不算违反成文规范，
但**这段注释的存在理由正是防止下一个人把桶合并回去**。最小修复：把"判据只有一份"的理由补回 `ReplacementPlan`
与 `preflight_lines`（`import_laws.py:42-48` 那句还在，是好的）。

### 低-4 批内"可安全并存"完全不播报

`import_laws.py:210-233`：批内两条同条文的不同世代若判为兼容，只留下两行
"将替换 0 旧片段 + 新增"，看不出"这两条是同一条文的两代、都会进库"。库侧同类情形有 `LINE_HISTORICAL`。
最小修复：批内兼容也复用 `LINE_HISTORICAL`（措辞"本批内保留 N 条不重叠历史版本"），不新增判据。

---

## 3. 我试过但**不成立**的方向（免得下一轮重复劳动）

- **"T1 的新分支大概在这棵库上是死码"** —— 打掉。见 §1.1，两块真实遗留块逐字命中，读数是"将替换 2"。
- **"丢掉章节行/条号会伤 BM25 召回"** —— 见 §1.2，43 行位次零差异，4 题专攻丢词也无差异。不成立（离线口径）。
- **"有日期但无 `version_id` 的旧块会被无正文比对删掉"**（我第一轮的怀疑）—— 见 §4 第 2 条：当前库 **0/10266**，
  且三条写路径都产不出这个形状。今天不可达，故不列为缺陷。
- **"批内查重会误拦合法的版本更替"** —— 见 §1.6，两种顺序都 rc=0。
- **`_periods_do_not_overlap` 的严格 `<` 是否与读侧含端语义一致** —— 一致，见 §1.5。

---

## 4. 仍需人工处理的限制（量化后的现状）

1. **长条文多片段 ⇒ 自动替换永不成立**。真实语料（私有副本读数）：`10266` 块 / `10236` 个
   `(source, article)` 组，其中 **5 组共 35 块**是多片段，全部 `origin=upload` 且两日期皆空：
   `香港特别行政区基本法 第一百六十条`=19 块、`澳门特别行政区基本法 第一百四十五条`=6、
   `地方各级人民代表大会和地方各级人民政府组织法 第五十条`=4、`刑法 第四百五十二条`=3、`广告法 第五十八条`=3
   （30 = 18+5+3+2+2 与 10266-10236 闭合）。⇒ 这 5 条走批导入必然 rc=1（每片都不等于整条正文），
   **E7 补日期时会正面撞上**。要处置得先决定：整条重录（人工确认删旧 35 块）还是给判据加"多片段拼接"比对
   （§9.11 明写"未引入片段拼接猜测"，方向我同意，别顺手做）。
2. **`same_version` 里"旧块无 `version_id` 但日期相同 ⇒ 不看正文直接删"这一支，今天 0 命中**：
   全库形状普查 = `10266/10266` 落在 `(version_id=n, ef=n, et=n)`，`origin` 全 `upload`，`status` 全 `现行`；
   且三条写路径都产不出"有日期无 version_id"（`import_docs.py` 只写 article/chapter、
   `main.py:2711-2718` 上传只写 filename/version/status、manual 与 import 必过 `version_metadata`）。
   ⇒ 它是**唯一**没有正文比对的删除面，今天不可达；哪天出现旁路写库，它就是风险点。
3. **无生效日的 manual/import 重传 ⇒ 并存**（中-1）。
4. **管理员直写路径不做整批阻断**：只保留冲突旧块，报警只存在于脚本预检（`knowledge_service.py:210-211` 注释自述）。
5. **本轮所有召回读数在离线道取的**（`EMBEDDING_PROVIDER=local` + `RERANK_ENABLED=false`）。本机真实配置是
   `rerank_enabled=True`（云端重排）⇒ 与 §9.11 同一限制：不能据此关闭 §9.9 的 23/24，也不能宣称召回问题已修。
6. **`_seed_conflict` 仍是死码**（库内 `origin=seed` = 0），所以 `law_versions.py:134` 新增的
   `origin != "seed"` 这条保护在真实库上**无从验证**，目前只有单测腿（`test_same_version_id_never_deletes_seed`）。
7. **候选批仍未真实入库**：本轮我只在自己的私有副本上执行过实写。H-1 那条"候选批不得真实入库"的阻塞
   在**判据面**已消（§1.1），但导入窗口 Owner 未撤 ⇒ 阻塞照旧。
8. **本机依赖越出区间锁**（`uvicorn 0.52.1` vs `<0.28`、`pypdf 6.14.2` vs `<6.0`）⇒ 上面这些绿灯
   不代表 CI/镜像拿到的依赖集。

---

## 5. 复现路径（探针脚本已随报告入库）

脚本本体：`C:\Users\33393\Desktop\ai-legal-helper\dispatch-output\version-safety-review-20260927\`
（`run_diff.sh`、`probe_dump.py`、`probe_manual_nodate.py`、`probe_fragments.py`、`probe_census.py`、
`probe_retrieve_ab.py`、`probe_chapter_tokens.py`）。私有数据副本在
`C:\Users\33393\AppData\Local\Temp\vsr-review-20260927\`（TEMP 会被清，脚本里的路径按需改）。

```bash
# §1.1 预检读数（务必用 CHROMA_DIR 指副本，别指 backend/chroma_db）
cd /c/Users/33393/Desktop/ai-legal-helper/backend
CHROMA_DIR=<TEMP>/vsr-review-20260927/chroma_pristine EMBEDDING_PROVIDER=local \
  venv/Scripts/python.exe -B scripts/import_laws.py --input ../data/laws_extra.candidate-20260925.json --dry-run

# §1.3 改前红基线（base 树来自 run_diff.sh 的 git archive HEAD）
cp -r <TEMP>/vsr-review-20260927/base <TEMP>/redcheck
cp backend/tests/test_law_versions.py backend/tests/test_import_laws_preflight.py <TEMP>/redcheck/backend/tests/
cd <TEMP>/redcheck/backend && <repo>/backend/venv/Scripts/python.exe -B -m pytest \
  tests/test_law_versions.py tests/test_import_laws_preflight.py -q -rf
# 只看红在哪一类断言上（§1.3 的分类就读自这条）：
cd <TEMP>/redcheck/backend && <repo>/backend/venv/Scripts/python.exe -B -m pytest \
  tests/test_law_versions.py tests/test_import_laws_preflight.py -q --tb=line -p no:cacheprovider \
  2>&1 | grep -E "^[A-Za-z]:.*\.py:[0-9]+: " > <TEMP>/vsr-review-20260927/redcheck_lines.txt

# §1.4 全量差分（约 6 分钟/两棵树；结尾两行 comm 的空集就是"零回归"的证据）
bash <TEMP>/vsr-review-20260927/run_diff.sh

# §1.2 改前/改后逐位对照（先跑 before，再对副本真实导入，再跑 after）
CHROMA_DIR=<TEMP>/vsr-review-20260927/chroma_pristine venv/Scripts/python.exe -B <TEMP>/.../probe_retrieve_ab.py before.jsonl

# §4 第 1、2 条的两个普查（秒级，只读副本）
CHROMA_DIR=<TEMP>/vsr-review-20260927/chroma_pristine venv/Scripts/python.exe -B <TEMP>/.../probe_fragments.py
CHROMA_DIR=<TEMP>/vsr-review-20260927/chroma_pristine venv/Scripts/python.exe -B <TEMP>/.../probe_census.py

# 第二轮三件（§1.3 逐用例映射 / §1.2 门禁两态 A/B / 低-2 变异）
cd <TEMP>/redcheck/backend && <venv>/python.exe -B -m pytest tests/test_law_versions.py \
  tests/test_import_laws_preflight.py -q --tb=no --junit-xml=<TEMP>/vsr-review-20260927/redcheck.xml
bash <TEMP>/vsr-review-20260927/run_smoke_ab.sh          # 24 项门禁在 pristine / imported 两态各跑一遍
# 低-2 的变异在 patched 副本树上做（**不动仓库文件**）：把 law_versions._same_article_body 首行
# 换成 raise RuntimeError("injected") ⇒ 单跑写侧那条应 1 passed（盲区），单跑 tests/test_law_versions.py
# 应 22 failed / 3 passed（单元层有牙）；跑完 cp 仓库原文件回副本并复量 sha256。
```

入库的原始读数：`base.failed` / `patched.failed`（12 条逐字相同）、`redcheck_lines.txt`（20 条红的错误行）、
`dump.txt`（两块真实遗留块的逐字对照）、`retr_before.jsonl` / `retr_after.jsonl`（43 行位次对照）、
`overlap.out`（批内重叠 ⇒ 整批不写）。

**收口复量（证明没碰真实库）**：

```bash
cd /c/Users/33393/Desktop/ai-legal-helper
sha256sum backend/chroma_db/chroma.sqlite3 | cut -c1-16    # 期望 b551677bddab4b85
stat -c '%y' backend/chroma_db/chroma.sqlite3              # 期望 2026-09-21 02:06:44
```

---

## 6. 第二轮自我复核：做了什么、抓到我自己什么

对第一版报告做反向自证，三件事（都可重跑，脚本已入库）：

1. **逐用例映射 20 条红**（`--junit-xml` 取代 `--tb=line`）→ 见 §1.3 的 11/2/7 三分法。
2. **换更代表性的召回仪器**：仓库自带的 24 项门禁在两态副本上各跑一遍 = **24/24 与 24/24**（§1.2）。
3. **给低-2 那条补变异**：副本树上把 `_same_article_body` 注入 `raise RuntimeError('injected')`
   ⇒ 写侧那条用例 **1 passed**（判据没跑也绿 = 盲区成立），同注入下单元层 **22 failed / 3 passed**（单元层有牙）。
   跑完 `cp` 还原并复量：副本与被复核文件哈希均为 `eac495bc5b69…`，**仓库生产文件全程零改动**。

**抓到第一版自己的两处错（已就地订正，不是补充说明）**：

- §1.3 的分类用的是 `--tb=line` 抽错误行，**仪器漏计 1 条**（`test_overlapping_dated_version_is_reported_as_time_conflict`
  的错误行没被那条正则匹上），我当时据此写了"13 条判据方向红 / 6+2+2+1+1=12"这种自相矛盾的数 ——
  真值是 **11 条决策方向 + 2 条文案 + 7 条只钉形状 = 20**。⇒ 又一条"负向自证要断言是哪条红了"的复发：
  **按错误行分类必须逐用例映射，不能按正则抓行**（与 §1e 的 `--tb=line` 陷阱同族）。
- 第一版 §1.2 的代表性只有我自己挑的 12 题 —— 换成仓库自带门禁的两态 A/B 才有资格说"没打破召回"。

**第二轮没有动摇的结论**：无误删、无误放行；§2 的中-1 与三条低 severity 全部复量成立；
被复核快照未漂移（5 个文件 `sha256` 在 15:58 与 16:52 两次读数一致），真实库 `b551677bddab4b85` / `09-21 02:06` 未变。
