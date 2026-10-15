# 工作汇报：法律版本替换安全复核（2026-09-27）

> 单文件可转发。任务来源：`C:\Users\33393\Desktop\ai-legal-helper\docs\assistant-briefs\version-safety-review.md`
> 技术明细与逐条证据：`C:\Users\33393\Desktop\ai-legal-helper\docs\assistant-briefs\version-safety-review-findings-20260927.md`（下称"明细件"）
> 汇报人：Qoder 复核会话；执行 2026-09-27 15:58 – 17:0x（本机）；工作区性质：只读复核，**未编辑任何既有文件**

---

## 0. 一页汇总

**做了什么**：按派单对工作区里尚未提交的 T1/T2 修复做只读安全复核，**做了两轮**（第二轮是对自己第一版的反向自证）。
范围锁在 `backend/law_versions.py`、`backend/knowledge_service.py`、`backend/scripts/import_laws.py` 与三个相关测试文件。

**总结论（一句话）**：**没有发现会误删法律片段、会错误放行冲突版本、或会把安全的历史版本误拦的新确证缺陷；
但发现一处收紧判据的连带后果落在"没有任何人工裁决机会"的管理端直写路径上，需要你拍一下（W1）。**

**本轮被复核的快照**（HEAD `7eda4bb`，工作区未提交；开工 15:58 与收口复量两次一致 ⇒ 结论针对这份码）：

```
eac495bc5b69  backend/law_versions.py          405d3a02c621  backend/knowledge_service.py
746725317cad  backend/scripts/import_laws.py   354275c08199  backend/tests/test_law_versions.py
5d377af20cc3  backend/tests/test_import_laws_preflight.py
```

**四项关键读数（全部本机实跑，非引用）**：

| 读数 | 值 | 现量口径 |
|---|---|---|
| 三条候选在真实库副本上的预检 | 将替换 2 / 新增 3 / 跳过 0，rc=0 | 明细件 §1.1；与汇报 §9.11 的声称**逐字一致** |
| 改后测试在**改前实现**上 | 20 条红 = **11 条判据方向** + 2 条文案 + 7 条只钉形状 | 明细件 §1.3（`--junit-xml` 逐用例映射） |
| 全量差分（HEAD 树 vs 工作区树） | 两侧各 12 failed，**差集为空**；1547 → 1568 passed | 明细件 §1.4 |
| 仓库自带引用门禁 两态 A/B | 原始副本 24/24，**已导入副本也是 24/24** | 明细件 §1.2 |

**待你拍的只有 1 件（W1）**：管理端直写路径在"生效日留空"时重传同一条文，从**替换**变成**静默并存**，
且那两份无日期旧块**事后补日期也清不掉**（单向棘轮）。推荐方案与理由见 §1。

---

## 1. 决策台账（本轮新增，编号接续 `docs/progress-handoff-report-20260925.md` §0 的 D 序列；**我没有写进那个共享文件**，需要并的话你说一声或让在写它的那个会话并）

| # | 待决问题 | 选项 | 我的推荐与实测依据 | 影响面 |
|---|---|---|---|---|
| **W1** | 管理端"无生效日重传同一条文"从替换变静默并存，要不要补、怎么补 | ① `KnowledgeAddIn` 在 `article` 非空时要求 `effective_from` 必填；② 保持判据不动、把冲突数报给操作者（端点响应 + 登记后的日志字段）；③ 不处理，当作在册限制 | **①**（若只能挑一个）。实测：同一探针脚本跑两棵树 —— 基线树 1 块 / 工作区树 2 块 / 再带日期写入 3 块，三者 `version_id` 相同；表单默认态即触发（`KnowledgeSection.tsx:45` 空日期 + `:72` `\|\| undefined`）。方向 ① 与本仓已签的"缺失不是安全状态"（`status` 改必填）同向。**不要**为"让它替换"回退 `law_versions.py:133-140`，那正是本轮防的误删 | 生产码 + 管理端 UI + 1 条用例 |
| **W2** | 低-2（写侧 `except Exception` 无日志的盲区）要不要顺手补 | ① 补一行登记过的 `logging.warning` + 一条"注入异常 ⇒ 日志里看得见那个键"的腿；② 归口 T 组另开票 | **①**。已用变异证实：副本树上让 `_same_article_body` 抛错 ⇒ 写侧那条用例**照样 1 passed**，而单元层同注入 22 条红 ⇒ 盲区只在这一条路上，补它成本一行 | 生产码 1 处 |
| **W3** | E7 补日期会撞上的 5 组多片段条文（35 块）要不要现在定处置口径 | ① 记进 E7 票面为已知前置；② 现在给判据加"多片段拼接"比对；③ 人工整条重录这 5 条 | **①＋③，别做 ②**。读数：10266 块 / 10236 个 `(source, article)` 组，**5 组 35 块**多片段（港基本法 160=19、澳基本法 145=6、地方组织法 50=4、刑法 452=3、广告法 58=3，全 upload 无日期）。拼接猜测会把"整条正文一致"这条唯一的删除保险拆掉，方向上我同意 §9.11 已有的"不引入猜测" | E7 / 导入窗口 |
| **W4** | 本轮复核件怎么归口 | ① 折进共享汇报 §9.12 + 台账；② 保持独立文件，汇报 §0 只加一行指针 | **②**。跨会话共写那份收口文件的规矩是你 09-26 Q7 定的（同一时刻只有一个会话写），我不清楚此刻谁在写 | 文档 |

---

## 2. 本轮工作明细（按时间顺序）

1. **读派单 + 锁范围**，先取被复核快照（5 个文件的 `sha256` 与 mtime），确认工作区确有未提交的 T1/T2 收紧。
2. **逐行读三个生产文件与三个测试文件的 diff**，列出四条待验假设：T1 分支是否真在真实库上触发、
   收紧后 `same_version` 是否留下"无正文比对的删除面"、`_periods_do_not_overlap` 与读侧谓词的端点语义是否同源、
   批内查重会不会误拦合法版本更替。
3. **建私有副本取证**（`%TEMP%\vsr-review-20260927\`，349 MB × 2 棵 + 若干空库），
   全程 `CHROMA_DIR` 指副本；真实库开工/收口各复量一次未变（见 §5）。
4. **第一轮结论落明细件**（§0 汇总 + 成立项 + 4 条问题 + 8 条在册限制 + 复现路径），
   并把 7 个探针脚本与原始读数归档进 `dispatch-output\version-safety-review-20260927\`。
5. **第二轮自我复核**（你上一条要求的"再复核一遍"）：三件新仪器 + **抓到我自己第一版两处错**（§3）。

---

## 3. 第二轮复核的产出（含我自己的错）

| 动作 | 结果 |
|---|---|
| 把 20 条红的分类从"正则抓错误行"换成 `--junit-xml` 逐用例映射 | **第一版数错**：我曾写"13 条判据方向红 / 6+2+2+1+1=12"，自相矛盾；真值 **11 判据方向 + 2 文案 + 7 只钉形状**。漏计的成因是 `--tb=line` 的错误行有一条没匹上正则 |
| 把召回仪器从"我自己挑的 12 题"换成仓库自带门禁的两态 A/B | 原始副本 **24/24**、已导入副本 **24/24**、rc 各自单取 = 0。"替换没丢召回"这句从此有代表性 |
| 给低-2 补变异（副本树，仓库文件未动、跑完还原并复量哈希） | 让 `_same_article_body` 抛 `RuntimeError` ⇒ 写侧那条用例**照样绿**；单元层同注入 22 条红 ⇒ 盲区定位精确到一条路径 |
| 复量被复核快照与真实库 | 5 个文件哈希与开工一致（并行会话这期间没动它们）；真实库 `b551677bddab4b85` / `2026-09-21 02:06:44` 未变 |

---

## 4. 确证问题与在册限制（详见明细件 §2、§4；这里只给口径）

- **中-1（= W1）**：管理端无生效日重传 ⇒ 静默并存、事后不可回收。端点响应只有 `added_chunks`，端点层零测试。
- **低-2（= W2）**：写侧 `except Exception: stale_ids = []` 无日志 ⇒ 崩溃与"判定后保留"同形（变异已证）。
- **低-3**：`ReplacementPlan` 的 docstring 丢了"为什么必须分桶（判据只有一份）"的理由注释；两个新 helper 换英文注释。
  `CONTRIBUTING.md` 无语言条款 ⇒ 不算违规，但那段注释正是防止下一个人把桶合并回去的东西。
- **低-4**：批内"可安全并存"的两代条文一行都不打印（库侧同类有 `LINE_HISTORICAL`）。
- **在册限制 8 条**（明细件 §4）里两条新量出来的：**全库 10266 块没有任何一条带日期** ⇒
  `same_version` 那条"不看正文直接删"的分支今天 0 命中、不可达（但它是唯一无正文比对的删除面）；
  **多片段条文 5 组 / 35 块**（= W3）。其余：候选批仍未真实入库、导入窗口未撤、`_seed_conflict` 仍是死码、
  召回读数只在离线道（生产云端重排未覆盖，**不能拿它关闭 §9.9 的 23/24**）、本机 uvicorn/pypdf 越出区间锁。

---

## 5. 证据指针与现量命令

```bash
# 被复核快照未漂移（期望前缀见 §0）
cd /c/Users/33393/Desktop/ai-legal-helper
sha256sum backend/law_versions.py backend/knowledge_service.py backend/scripts/import_laws.py | cut -c1-12

# 真实库零改动（期望 b551677bddab4b85 与 2026-09-21 02:06:44）
sha256sum backend/chroma_db/chroma.sqlite3 | cut -c1-16 && stat -c '%y' backend/chroma_db/chroma.sqlite3

# §0 第一行读数（务必把 CHROMA_DIR 指副本）
cd backend && CHROMA_DIR=<TEMP>/vsr-review-20260927/chroma_pristine EMBEDDING_PROVIDER=local \
  venv/Scripts/python.exe -B scripts/import_laws.py --input ../data/laws_extra.candidate-20260925.json --dry-run
```

全套复现命令、逐用例映射原文、两态门禁输出、差分失败名单：
`C:\Users\33393\Desktop\ai-legal-helper\dispatch-output\version-safety-review-20260927\`
（18 个文件：7 个探针脚本 + `run_diff.sh` + `run_smoke_ab.sh` + `dump.txt` / `redcheck_junit_map.txt` /
`base.failed` / `patched.failed` / `smoke_pristine.out` / `smoke_imported.out` / `retr_before.jsonl` /
`retr_after.jsonl` / `overlap.out` / `redcheck_lines.txt`）。

---

## 6. 边界：本轮**没做**的事

未编辑、未还原任何既有文件（我只新增本报告与明细件、以及那个探针目录）；未真实入库（写入只发生在私有副本）；
未 push、未动部署、未轮换凭据、未调用模型或云服务（`LLM_BASE_URL` 指死端口 + 假 key + `EMBEDDING_PROVIDER=local`）；
未扩展到 T3–T8；未跑云端重排口径的召回评测；未替你决定 W1–W4。
