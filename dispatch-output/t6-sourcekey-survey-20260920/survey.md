# T6 普查报告 · I-6 同族：还有哪些调用点用 source 精确匹配会漏掉带年份括注的库内源名

## 基线锚定（必填）

- `git rev-parse HEAD` = `beb4d5c09a7a28e2987488b86031780f6ed7d8c5`
- `sha256(backend/retrieval.py)` = `59596c826ab11dc7c036242d90545fe2ddd77f387facb52e4f87f25f0dfc0476`
  （与 takeover baseline.json 中 retrieval.py 快照哈希**逐字一致** ⇒ 确认读的是票 I 在 beb4d5c 合入 I-6 后的提交版，无漂移）
- `sha256(backend/main.py)` = `a31b7b4c34c71692f860e1730fe1e7188e6b49f46790ab8211b328137e50be83`
  （⚠️ 与 baseline.json 快照 `6a320e4…` **不同**：ticket I 彼时在途写 main.py，本值是开工时现值；锚定即为此目的——结论对着当前版本，事后可复核）

> **范围声明**：本结论**不含 `exact_article_lookup` 本体**。该函数本体由票 I 在 `beb4d5c` 合入 I-6 修好（已用 `_source_key` 回退容错），不属本卡射程。本卡只普查其余 6 个调用点。

## 参照实现与测试锚点

- 唯一正确形态：`backend/retrieval.py::_source_key` —— 去 `中华人民共和国` 前缀 + 去尾部 `（年份/版本）` 括注；docstring 原文点名 `宪法（1982年）`。`article_in_kb` / `source_in_kb` / `citation_verify` / `classify_*` / `citation_grounding` / `_expected_law_keys` / `_doc_expected_key` 全部复用它，证明"全仓唯一归一规则"已存在，不应另写第二份去括注正则。
- 测试锚点（本卡采用）：`backend/tests/test_citation.py`
  - `test_source_key_handles_xianfa_bracket`：断言 `R._source_key("宪法（1982年）") == "宪法"`、全称变体同归 `宪法`。
  - `test_verify_against_real_kb`（real_kb 集成）：断言 `《宪法》第二条` 在库不报（括注边界已容忍）。
- **不使用**票 I 新写的 `backend/tests/test_exact_article_lookup_sourcekey.py` 作为本卡证据（纪律禁止）。

## 已确立的库内事实（支撑逐点结论）

1. **带括注源确实存在**：`宪法（1982年）` 是库内源名。证据链：I-6 docstring 明示 + `test_citation.py::test_verify_against_real_kb`（real_kb 用例 line ~102「宪法括注边界 → 在库不报」）共同佐证，非推测。
2. **seed 源名全 clean**：`knowledge_base.build` 注入 `source = law["title"]`（`data/laws.json`）。实测 laws.json 7 行 title = 劳动合同法/民法典/消费者权益保护法/刑法/道路交通安全法，**全为干净短名、无宪法、无括注**。
3. **带括注源由 import_docs 产生且自洽**：`import_docs.short_source()` 仅剥 `_\d{8}$` 日期后缀与 `中华人民共和国` 前缀，**不剥 `（）` 括注** ⇒ `宪法（1982年）.txt` 仍以 `宪法（1982年）` 入库，写入与查询同形。即：带括注形态是写路径自身保持一致的，不是散落各处随机产生的。

---

## 逐调用点结论（6 处，跨 4 文件）

### KS-1 · `backend/knowledge_service.py` · `add_text` · L204
**是否要 `_source_key` 容错：要。**
- 代码：`existing = _collection().get(where={"$and":[{"source":source},{"article":article}]})`，精确 source+article，非 `_source_key`。
- `source` 来自调用方（admin 上传 / `import_laws.py` 传 `source=title`）。
- 理由：该查找决定"是否替换旧版"。库内宪法为带括注 `宪法（1982年）`（import_docs 产生）；若调用方以短名 `宪法` 重传/再导入，`where source='宪法'` 命中不到 `宪法（1982年）` → `stale_ids` 空 → 不替换只追加 → 同法同条重复积累。对干净短名法（seed 5 部）虽无歧义，但跨写入端/跨次导入形式不一致即漏替换。
- 最小修法：仿 I-6 回退——先 `where={"article":article}` 取同条号族，再 Python 侧 `_source_key(str(meta['source']))==_source_key(source)` 筛待替换项交 `replaceable_version_ids`。复用唯一归一规则，不另写去括注正则。

### G1-2 · `backend/scripts/gen_gate1_law_check.py` · `main` · L92
**是否要 `_source_key` 容错：当前不需修（防御性可加）。**
- 代码：`col.get(where={"$and":[{"source":{"$eq":source}},{"article":{"$eq":article}}]})`，只读核验。
- `source` 来自硬编码 `TARGETS` = 劳动法/劳动合同法/民法典/消费者权益保护法/刑法/劳动争议调解仲裁法——**全短名、无宪法**。
- 理由：库内这些法均为干净短名（seed 5 部 laws.json 实测全 clean + import_docs 清洗件 short_source 得短名），gen_gate1 以短名查、库内同形 → 不漏。宪法（带括注）不在 TARGETS，故本卡场景（短名查带括注库源）当前不触发。
- 最小修法：不需修。若未来把带括注法加入 TARGETS 或库内某法改带括注会假阴性，届时按 article 取后 `_source_key` 比对即可（防御性增强，非必需）。

### IL-3 · `backend/scripts/import_laws.py` · `_seed_conflict` · L74
**是否要 `_source_key` 容错：当前不需修（防御性可加）。**
- 代码：`get(where={"$and":[{"source":title},{"article":article}]})`，仅判断 `origin=="seed"` 冲突。
- `title` 来自 `laws_extra.json`。
- 理由：seed 源名（laws.json）实测全 clean，与 laws_extra.json 同约定 → 对 seed 5 部匹配正确、无括注歧义；宪法不在 seed 集（laws.json 无宪法），故 `_seed_conflict` 对宪法无场景。仅当 laws_extra.json 对某部法用短名、而库内该法因其他路径带括注时才会漏判 seed 冲突——属数据录入边界风险，非当前代码逻辑缺陷。
- 最小修法：不需修。可顺手以 `_source_key` 归一 title 与库内源名比对作防御；但 5 部 seed 均 clean，无紧迫性。

### IL-4 · `backend/scripts/import_laws.py` · `main` · L115
**是否要 `_source_key` 容错：要（与 KS-1 同源脆弱性）。**
- 代码：`existing = vectorstore._collection.get(where={"$and":[{"source":title},{"article":article}]})`，写入端幂等找旧版替换。
- `title` 来自 `laws_extra.json`。
- 理由：与 KS-1 同一机制。库内宪法带括注 `宪法（1982年）`；若 laws_extra.json 以短名 `宪法` 提供宪法条目，`existing` 查找命中不到 → 不替换 → 重复。对 seed 5 部（clean）无歧义，但跨写入端形式不一致即漏。
- 最小修法：仿 I-6，按 article 取后 Python 侧 `_source_key` 比对筛 stale。复用唯一归一规则。

### ID-5 · `backend/scripts/import_docs.py` · `purge_source` · L64
**是否要 `_source_key` 容错：当前不需修（自洽）。**
- 代码：`_col().get(where={"source":source})["ids"]`，按 source 精确清理残留。
- `source` 由 `--purge-source` 入参或 `--only` 经 `short_source` 派生。
- 理由：写入端即本脚本自身——`source=short_source(fname)`，short_source 保留 `（1982年）` 括注、剥 `_日期` 与 `中华人民共和国`，故写入与查询同形 → 不漏自身写入。宪法经此路径以 `宪法（1982年）` 入库且同形匹配。唯一漏删风险在运维入参：误传短名 `宪法` 去 purge 会漏删 `宪法（1982年）` 残留——属入参风险，非代码逻辑缺陷。
- 最小修法：不需修。可在 purge 前对入参也过 `_source_key` 或列出候选源名提示，作运维友好增强。

### ID-6 · `backend/scripts/import_docs.py` · `import_one` · L92
**是否要 `_source_key` 容错：当前不需修（自洽）。**
- 代码：`seed_hits = _col().get(where={"$and":[{"source":source},{"origin":"seed"}]})`，整法导入取代 seed 碎片。
- `source=short_source(fname)`，同脚本派生，写入与查询同形。
- 理由：seed 源名（laws.json）clean；本路径针对整法导入覆盖 seed：fname 不带括注（如 `劳动合同法.txt`）→ source 干净，与 seed 的 clean 同形 → 正确取代。宪法若以 `宪法（1982年）.txt` 导入 source 带括注，与（若有）seed 宪法同形；但宪法本就不是 seed（laws.json 无宪法），故无 seed 取代场景。
- 最小修法：不需修。

---

## 综合判据回应

- **逐调用点给「要不要 `_source_key` 容错」**：已逐点给出（KS-1 要 / G1-2 不需 / IL-3 不需 / IL-4 要 / ID-5 不需 / ID-6 不需）。
- **逐点理由**：已给（每点含机制、库内源名形态、漏/不漏的触发条件）。
- **最小修法或"不需修"证据**：已给。需修两处（KS-1、IL-4）最小修法 = 仿 I-6 回退（按 article 取 + Python 侧 `_source_key` 比对），复用全仓唯一归一规则；不需修四处均给了实测证据（laws.json 全 clean、import_docs short_source 自洽、TARGETS 不含宪法）。
- **未另写第二份"去括注"正则**：本卡结论一律指向复用已有 `_source_key`，未定义任何新正则。
- **结论不含 `exact_article_lookup` 本体**：已声明。

---

# ② 回报形状（§2 固定五段）

**① 结论（一句话）**
除已由票 I 修好的 `exact_article_lookup` 外，6 个 source 精确匹配调用点中，**真正会因"短名查带括注库源"漏命中的只有 2 处写入/幂等路径**——`knowledge_service.add_text`(L204) 与 `import_laws.py` 主流程(L115)；其余 4 处或因自身自洽（import_docs 两处）、或因当前数据不构成（gen_gate1 不查宪法、_seed_conflict 仅限 clean 名 seed）而**当前不需修**，但 G1-2/IL-3 属防御性可加项。

**② 产物（绝对路径 + 关键读数）**
- `C:\Users\33393\Desktop\ai-legal-helper\dispatch-output\t6-sourcekey-survey-20260920\survey.md`（本报告）
- `C:\Users\33393\Desktop\ai-legal-helper\dispatch-output\t6-sourcekey-survey-20260920\call-sites.json`（6 调用点结构化表）
- 关键读数：`git rev-parse HEAD`=beb4d5c；`sha256(retrieval.py)`=59596c…0476（与 baseline 一致，确认读的是 I-6 提交版）；`sha256(main.py)`=a31b7b…be83（≠baseline 快照 6a320e…，ticket I 在途所致，已声明）。
- 库内事实：laws.json 7 行 title 全 clean（5 部 seed 法，无宪法无括注）；`宪法（1982年）` 确为库内源名（I-6 docstring + test_citation real_kb 用例佐证）。

**③ 判据对照（逐条抄判据，标 满足/不满足）**
| 判据（来自 T6 卡 / §2） | 状态 | 说明 |
|---|---|---|
| 逐调用点给「要不要 `_source_key` 容错」+ 理由 + 最小修法（或"不需修"证据） | 满足 | KS-1/IL-4=要；G1-2/IL-3/ID-5/ID-6=不需，均附理由与证据 |
| 我不接受：只说"建议统一"而不逐点给理由 | 满足 | 每点独立给出机制与触发条件，无笼统"建议统一" |
| 禁：另写一份"去括注"正则（第二份规则） | 满足 | 结论一律指向复用既有 `_source_key`，未定义新正则 |
| 禁：改码 | 满足 | 全程只读，未修改任何文件（含 retrieval.py） |
| 禁：把票 I 新测试 test_exact_article_lookup_sourcekey.py 算作证据 | 满足 | 仅用 test_citation.py 作锚点 |
| 终止条件：5 个文件逐点结论，各 ≤2 次读尝试；读不出标 UNVERIFIED | 满足 | 4 个源文件 + 1 个测试锚点文件均一次读通（retrieval.py/knowledge_service.py/gen_gate1_law_check.py/import_laws.py/import_docs.py/test_citation.py/knowledge_base.py/laws.json）；无 UNVERIFIED 点 |
| 禁止 git 写操作 | 满足 | 仅执行 `git rev-parse HEAD`（只读）与 sha256sum（只读） |

**④ 我复跑的命令（确切，可照跑）**
```
# 锚定（只读，无 git 写）
cd C:\Users\33393\Desktop\ai-legal-helper
git rev-parse HEAD
sha256sum backend/retrieval.py backend/main.py

# 复核对本卡结论最关键的两处证据（库内 seed 源名是否 clean、宪法是否带括注）
grep -n '"title"' data/laws.json
# → 应见 7 行全为干净短名（劳动合同法/民法典/消费者权益保护法/刑法/道路交通安全法），无宪法、无括注

# 复对 import_docs 是否保留括注（不剥 '（）'）
grep -n "_DATE_SUFFIX_RE\|def short_source\|_PREFIX" backend/scripts/import_docs.py
# → short_source 仅 sub("_\\d{8}$") 与去 '中华人民共和国' 前缀，不含对 '（）' 的处理

# 复对 _source_key 语义（本卡采用，不采用票 I 新测试）
grep -n "_source_key" backend/retrieval.py
# + 跑锚点测试（只读，不写库）：
C:\Users\33393\Desktop\ai-legal-helper\backend\venv\Scripts\python.exe -m pytest backend/tests/test_citation.py::test_source_key_handles_xianfa_bracket backend/tests/test_citation.py::test_verify_against_real_kb -q
# 注：test_verify_against_real_kb 标 real_kb，需真实 chroma_db，缺则跳过该条、不影响其余结论
```

**⑤ 诚实登记（没做到的 / 读不到的 / 未证实的 + 越界写声明）**
- **未直接读 chroma_db 验证"宪法（1982年）"实际条目**：本卡为源码级普查，未跑库内读取脚本。带括注源存在的判定来自 I-6 docstring 与 `test_citation.py::test_verify_against_real_kb`（real_kb 集成用例）两条既有证据，**非本卡独立复现**；若需对库内现状做不可辩驳的读数，应另跑 `probe_real_db_readonly.py` 查 `source` 枚举（超出本卡射程，未做）。
- **laws_extra.json 是否含宪法短名条目未查证**：IL-3/IL-4 的"不需修/要容错"判定基于"laws_extra.json 与 laws.json 同约定"的推断 + 库内宪法带括注事实；未读取 `data/laws_extra.json` 确认其是否真有宪法条目（该文件可能不存在或为空）。若实战中存在以短名 `宪法` 录入的 laws_extra 条目，则 IL-4 的"要容错"从潜在风险转为实际命中——此点标记为**推断未实证**。
- **未证实项**：gen_gate1 的"不需修"依赖"库内宪法之外各法均 clean"——该点由 laws.json（seed）与 import_docs 写入约定支撑，但未经 chroma_db 全量 `source` 枚举复核，标记为**推断未实证**。
- **越界写声明**：本卡**无任何越界写**。唯一写集为交付目录 `dispatch-output\t6-sourcekey-survey-20260920\`（survey.md、call-sites.json）。未改 `backend/**`（含 retrieval.py/main.py）、未碰 `gate_exit_registry.py`/`gate2_runner.py`/`docs/code-review-report-02e3851-20260918.md`、未执行任何 git 写操作（add/commit/stash/checkout/restore/push/reset 均未执行）。
