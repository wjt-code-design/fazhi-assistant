# C 助手工作汇报 · 版本安全 W1 / W2（2026-09-27）

票面：`C:\Users\33393\Desktop\ai-legal-helper\docs\assistant-briefs\next-phase-C-version-write-20260927.md`
仓库：`C:\Users\33393\Desktop\ai-legal-helper`　分支：`master`

会话起点 `HEAD` = `7eda4bb`；本汇报收口时 `HEAD` = `9557dfb`。**我自己未提交、未推送、未还原任何他人改动**；但期间提交 `ac426c2 chore(工作区快照): 并入并行会话的未提交修改（T1/T2 版本判据 + T5 导入类型门 + 文档/前端/证据）` 把整个工作树（含并行会话的 WIP 与我的改动）一并入了库 —— 会话起点那条"寄生未提交 WIP"的风险随之消解（见 §0 补记）。

---

## §0 汇总（可转发部分）

### 交付判据逐条

| 票面判据 | 结论 | 读数 |
|---|---|---|
| W1 接口拒绝有可运行回归 | **达标** | `backend/tests/test_phase5.py:193` + `:273` 两条端点回归；合并跑 `11 passed, 1 deselected, rc=0` |
| W2 失败既可见 | **达标** | `backend/tests/test_knowledge_service.py:204` 断言归因键进结构化 payload（`:222`），红→绿已自证 |
| W2 不误删旧块 | **达标** | 同文件 `:196` 独立断言"判定崩溃时旧块仍存活"，与上一条**互为独立用例**，各有单点变异自证 |
| 测试只用项目隔离夹具 | **达标** | 走 `backend/tests/conftest.py:33-40` 的隔离 lane；真库指纹零改动（§4） |

### 门禁读数（工作目录 = `C:\Users\33393\Desktop\ai-legal-helper\backend`）

| 命令 | 读数 | rc |
|---|---|---|
| `venv\Scripts\python.exe -B -m pytest tests/test_knowledge_service.py tests/test_phase5.py -q -m "not slow" -p no:cacheprovider` | `11 passed, 1 deselected` | **0** |
| `venv\Scripts\python.exe -B -m pytest tests/test_log_field_whitelist.py -q -p no:cacheprovider` | `2 passed` | **0** |
| `venv\Scripts\python.exe -B -m ruff check knowledge_service.py schemas.py observability.py tests/test_knowledge_service.py tests/test_phase5.py` | `All checks passed!` | **0** |
| `venv\Scripts\python.exe -B -m ruff format --check <同上 5 文件>` | `5 files already formatted` | **0** |
| `venv\Scripts\python.exe -B -m mypy .` | `Success: no issues found in 74 source files` | **0** |

偏离票面一处并声明：多加了 `-p no:cacheprovider`（避免再写 `.pytest_cache/`），其余参数逐字照票面。

### ⚠️ 会话起点那条风险：已消解（原记录保留，不删）

**原记录（写于 `HEAD = 7eda4bb`，当时为真）**：`backend/schemas.py` 里的 W1 守卫（票面①）**不在 `HEAD` 里**，是另一路会话的未提交 WIP ⇒ 我的两条 W1 回归之所以能绿，寄生在那份 WIP 上。

**现读（`HEAD = 9557dfb`，2026-09-27 复核）**：

- `git show HEAD:backend/schemas.py`：`:190` 有 `if self.article and not self.effective_from: raise ValueError("填写条文时必须提供施行日期")`，`:185-188` 是我那段注释 ⇒ **守卫已在 `HEAD` 里**。
- `git diff --numstat -- backend/schemas.py backend/knowledge_service.py backend/observability.py backend/tests/test_knowledge_service.py backend/tests/test_phase5.py` → **空** ⇒ 这 5 个文件的工作树内容逐字等于 `HEAD`。
- 独立佐证（排除"内容过滤器把差异吃掉"这条）：我的注释原文出现在 `HEAD` 的**同几行**上（`:185-188`），不是"归一后看不出"。
- ⇒ 上面两组 pytest 读数**就是跑在纯 `HEAD` 内容上**的，不再寄生任何未提交 WIP。

**仍然成立的部分**：守卫是随"工作区快照"提交并入的，**不是我自己提交的**，它的归属仍记在并行会话（T1/T2）名下（§1）。

---

## §1 修改文件（逐处可核；"我的笔" ≠ "该文件的 diff"）

| 文件 | 我的改动 | 归属 |
|---|---|---|
| `backend\tests\test_phase5.py` | 新增 `test_admin_knowledge_rejects_whitespace_only_article_without_date`（`:273`，含对照腿），+70 行 | 我的 |
| `backend\schemas.py` | `:189` 谓词 `self.article.strip()` → `self.article`，并补 4 行注释说明为何**不能**用 `.strip()` | 票面外，按交办人"按你的建议执行"授权 |
| `backend\observability.py` | `:133` 归因键的注释改准（原文"不含法名之外的任何内容"与事实不符） | 票面外，按交办人解冻授权 |
| `backend\tests\test_knowledge_service.py` | 仅模块表头 `:1`（原文"（slow，真实 chroma）"与事实不符） | 我的 |

`backend\knowledge_service.py` **本轮未改**（W2 那三笔在此前轮次已落，见 §2）。

上表 4 处改动（含 `schemas.py`、`observability.py` 两笔票面外改动）现均已随 `ac426c2` 进入 `HEAD`。

**本轮新增的未跟踪产物（我建、我不提交）**：`dispatch-output\d3-article-key-probe-20260927.py`（D3 探针）+ 本汇报自身。二者 `git ls-files` 均为空 ⇒ 报告里的 D3 读数不在库里，复现路径见 §2 末节的命令。

⚠️ **归属声明**：该探针是**新建文件**，不在票面归属清单（票面只给 3 个 owned + 3 个只读）里 —— 它只读、不导入任何归属外既有文件的可写路径，未改任何归属外文件；但按"碰归属外先报交办人"的规矩在此显式列出。若要撤，删该文件即可，报告 §2 末节保留读数并注明探针已撤。

### 归属判定方法与结论（重要）

我解析了本会话的 tool_use 记录逐笔列名，**不是靠 grep**（grep 会把我的思考文本一起匹配、判不了）：

- 我在 `knowledge_service.py` 只有 **3 笔**：`:28` `logger = ...`、`import logging`、`:226-237` 的 warning 块。
- **同期该文件里还有不是我写的 hunk**：`effective_to` 贯通 2 处、docstring 1 处、注释 1 处 —— 并行会话的 WIP。会话起点它们在 `git diff` 里可见；现已被 `ac426c2` 一并提交，故 `git diff` 现在为空（内容仍在 `HEAD`，只是不再"未提交"）。我按"不还原他人工作"一笔未动。
- 同理 `backend\law_versions.py`、`backend\tests\test_law_versions.py`、`frontend\app\admin\sections\KnowledgeSection.tsx` 在会话起点 `git status` 里是 ` M`，但**我一笔未动**（mtime 见 §4）；现同样被 `ac426c2` 提交。注意前端文件**不在 `backend/` 下**（票面亦写作 `frontend/app/admin/sections/KnowledgeSection.tsx`）。

### 票面第 3 步（范围纪律）的遵守

`backend\knowledge_service.py:195-196`（`file_hash` 查找的 `except`）与 `:249-250`（删旧时的 `except`）**我一笔未动**，与票面"不顺手改"一致；同根因的新发现按票面"给出证据、由交办人定范围"处理（见 §5 D3）。

---

## §2 前后行为

### 本轮（空格洞，已修）

- **修前**：`article=" "` + 无施行日期 → 端点 **`200 {"added_chunks":1}`**（真写了一块）。连传两次即造出同 `version_id`（实测 `lv-9901dbc75`）、`effective_from=''` 的**双胞胎块**，无日期可判 ⇒ `replaceable_version_ids` 把它归 `coexist` ⇒ **事后清不掉**，与 `version-safety-review-findings-20260927.md` §2 中-1 是同一个终态。
- **修后**：同一 payload → **422 且 `"施行日期"` 在响应体内**，且该 source **零块**（校验发生在写库之前）。
- **对照腿（防"端点对这条一律拒绝"）**：同一 payload **只补日期一栏** → **200 且 ≥1 块**。
- **既有边界未变**：`article="第一条"` + 无日期 → 422；`article=""` + 无日期 → 200。

根因是**一处谓词不一致**：端点判 `self.article.strip()`（`backend\schemas.py:189` 修前），写库判裸真值 `and article`（`backend\knowledge_service.py:184`、`:204`）。空白条号在端点算"没填"、在写库算"填了"。

### 前轮（W1 / W2 主体，仍属本票交付）

- **W1 端点契约**（`backend\tests\test_phase5.py:193`）：钉"**先拒绝再写库**"这个顺序——拒绝后该 source 一个块都没有；并保留"无条号的一般知识不填日期仍可存"的边界腿。
- **W2 降级可见**：`add_text` 的替换判据整段包在 `except Exception` 里，"判据整体崩塌"与"判定后决定不替换"在库侧结果完全相同（旧块都留着）。先证现状**零告警**（红：`AssertionError: 判定崩溃应恰好留一条 warning，实际 0 条；全部日志：[]`），再加一条 warning（`backend\knowledge_service.py:230`），归因键 `law_version_judgment_failed` 登记进 `backend\observability.py:133`（不登记会被 `_JsonFormatter` 静默丢弃 ⇒ W2 白写）。
- **两条用例互为独立（§7 本轮复核实测，不是继承来的读数）**：`:196` 钉安全侧（旧块未误删）、`:204` 钉可见侧（键进 payload + 异常身份可定位 + 正文令牌不落日志）。各做**单点**变异（锚点计数预检 = 1，`backend\knowledge_service.py` sha256 前后一致 `fa986e23…aecf`）：
  - 变异 B：`logger.warning(` → `logger.debug(` ⇒ `FAILED …::test_version_judgment_crash_is_visible_in_structured_log` / `1 passed`
  - 变异 A：判据 `except` 内 `:229` 的 `stale_ids = []` → `stale_ids = list(existing["ids"])`（"判定失败 ⇒ 按旧口径全删"）⇒ `FAILED …::test_version_judgment_crash_keeps_old_chunks` / `1 passed`
  - ⚠️ **自纠**：我原先记的"变异 A = `if n and stale_ids:` → `if n:`"**不具区分度**（本轮实测 `2 passed`，两条都没红）——崩溃路径里 `stale_ids` 本就是 `[]`，删空列表什么也没发生。安全侧的牙长在 `:229` 那一行上，变异必须打那一行。
- **slow 标记**：按本轮裁定**不标**（理由：`CONTRIBUTING.md:17` 的口径是"真实 KB"，而本模块全部用例走隔离 lane；且标了 CI 的 `-m "not slow"` 会把它筛掉，交付判据在票面自己的命令下失去读数）。该文件原有 1 条未标用例（`:88`）也是同一先例。

### D3 补跑实测：`article` 前后带空格（2026-09-27，探针 `dispatch-output\d3-article-key-probe-20260927.py`）

同源、同条号、同施行日期，只差首尾空格，两次 `add_text`（隔离 lane：`QUOTA_DB` / `DATABASE_URL` / `CHROMA_DIR` 三条 env 无条件指 `%TEMP%`）：

跑法（工作目录 = `C:\Users\33393\Desktop\ai-legal-helper\backend`）—— 探针**未跟踪**、我按票面不提交，故数字要可核只能照此重跑：

```
venv\Scripts\python.exe -B ..\dispatch-output\d3-article-key-probe-20260927.py
```

| 步骤 | 读数 |
|---|---|
| 写 `"第一〇一条"` | 1 块，`article='第一〇一条'`，`version_id=lv-f7bb637d96c4b9fa0e5fbde1` |
| 再写 `" 第一〇一条 "`（同日期） | **新增** 1 块 ⇒ 共 **2** 块，`article=' 第一〇一条 '`，**`version_id` 与上一条完全相同** |
| `where(article="第一〇一条")` | 只命中不带空格那块 |
| `where(article=" 第一〇一条 ")` | 只命中带空格那块 |
| 再重传一次 `"第一〇一条"` | 仍是 **2** 块 ⇒ 空格块**不被版本替换逻辑清掉**（该逻辑按裸 `article` 键查，永远看不到对方；只能按 `doc_id` 手工删） |

⇒ 三件事全部实测成立（原先只在代码上推）：① metadata 里的 `article` 是**原样**存（`backend\chunking.py:182` 不 strip）；② `version_id` **相同**（`backend\law_versions.py:66` 的 `derive_version_id` 对 article 做了 strip）；③ `backend\knowledge_service.py:210` 那条 `where` 是**键精确**的 ⇒ 两变体互不认账，形成"**同 version_id 的双胞胎**"，与 findings §2 中-1 属同一类终态（差别：本例两块都带日期，故在管理端按 source 列表里看得见、可按 `doc_id` 手工删；findings 那个洞是 `effective_from=''`） 。

真库边界（探针跑前/跑后双向读数）：`find chroma_db -newermt "2026-09-27 00:00"` 均**空**；指纹 `b551677bddab4b85` / 210051072 B / `2026-09-21 02:06:44` **未变**；无 `-wal`/`-shm`；探针写在 `%TEMP%\d3_chroma_<pid>`。

---

## §3 红 → 绿自证（同一棵树，只差 `schemas.py` 那一行）

```
修前  backend\tests\test_phase5.py:324
      AssertionError: 条号只填空格且无生效日应被拒，实际 200：{"added_chunks":1}
      → 1 failed in 13.04s
修后  fixture 起手断言"起点零块" + 422 + 零块 + 对照腿 200
      → backend\tests\test_phase5.py 单文件 8 passed in 16.61s
```

---

## §4 边界取证

| 项 | 读数 |
|---|---|
| 真库目录 `backend\chroma_db\` 今日改动 | `find chroma_db -newermt "2026-09-27 00:00"`（**全层级**）→ **空** |
| 真库顶层实际内容（更正一处口径） | 除 `chroma.sqlite3` 外还有 **8 个 UUID 老 segment 目录**（mtime `2026-07-31` … `2026-08-04`，chroma 老布局）—— "顶层只有 `chroma.sqlite3`" 这个说法**不准确**；但"今日零改动"仍成立（上一条 `find` 全层级为空） |
| 真库指纹 | `chroma.sqlite3` = 210051072 B / mtime `2026-09-21 02:06:44` / `sha256[0:16] = b551677bddab4b85`（**= findings §5 期望值**） |
| 侧车文件 | 无 `-wal` / `-shm` |
| 我碰过的 5 个文件 mtime | `knowledge_service.py` 19:32:38、`test_phase5.py` 21:39:20、`schemas.py` 21:40:19、`observability.py` 21:41:20、`test_knowledge_service.py` 21:41:37 |
| 票面只读文件 mtime（均早于我的改动） | `backend\law_versions.py` 15:06:19、`backend\tests\test_law_versions.py` 17:16:38、`frontend\app\admin\sections\KnowledgeSection.tsx` 17:39:32 |
| 换行符 | 上述 5 文件全部 CRLF（CR == 总行数），且 `HEAD` blobs 亦含 CR ⇒ **不是我引入的** |

---

## §5 决策台账（待你裁；每条附我的建议）

| # | 待决项 | 我的建议 |
|---|---|---|
| D1 | ~~`schemas.py` 归属与**冲突面**~~ **已由事件消解，无需再裁**：`ac426c2` 把守卫连同我那一笔提进了 `HEAD`，不再存在"寄生未提交 WIP、对方回写即覆盖"的冲突面 | 仅余**记账**一问：守卫记在并行会话（T1/T2）还是本票 —— 我建议记 **T1/T2**，我只动了 `strip()` → 裸真值那一行 |
| D2 | `observability.py:133` 那笔是否保留 | **保留**（不登记则 W2 的键被 formatter 静默丢弃）。若你裁撤：回退 = 去掉 `extra=` 与白名单键，只留 `msg` + `exc` |
| D3 | 空格键变体：**已实测**（§2 末节，非推断）—— 同 `version_id`、两键互不认账、**版本替换逻辑**永远清不掉（手工按 `doc_id` 删可行） | **先不修、记在册**。理由：触发面要客户端主动发前后空格（比空白洞窄），且两块都带日期、管理端可见可删；修它得动 `backend\chunking.py` 或 `add_chunks` 的 metadata 归一，**不在我归属清单** ⇒ 要修请重划文件 |
| D4 | 今天这笔要不要折进 `docs\assistant-briefs\version-safety-review-findings-20260927.md` §2 | **仍待你明确**：这是我台账里唯一必须由你**指定文件归属**的一条；未划之前我不动归属外文件，以本文件为准 |

已决（备查）：slow 标记 = **不标**；`schemas.py` 空格洞 = **修 + 补回归**（而非记在册限制）。

---

## §6 未验证 / 存疑（诚实标注，勿当结论）

1. ~~D3 的空格变体（`" 第一〇一条 "`）我没有实测~~ **已于 2026-09-27 补跑并定性（读数见 §2 末节），不再是推断**；含探针跑前/跑后的真库双向边界。
2. `mypy` 本次报 `74 files`，本会话早前一次读数是 `73`。**差额我未归因**：我没有新建任何源文件；工作树里存在另一路会话的未跟踪测试文件 `backend\tests\test_smoke_citation_assertions.py`（mtime 21:32:13）；**本会话早前那次全量跑里它有 8 条红，该读数本轮未复跑**，与我的改动无关。
3. 本轮**未跑全量套件**（票面只要求两个文件 + 哨兵 + lint）。上一条里那 8 条红属未跟踪文件，不是回归。
4. ~~`backend\tests\test_phase5.py:273` 那条新回归的"基线树也会红"是推断~~ **该问法已作废**：守卫现在就在 `HEAD` 里（§0 补记），纯 `git archive HEAD` 树同样带守卫，不存在"基线树也红"。实测依据仍是 §3 那对"同一棵树、只差 `schemas.py` 一行：修前红 / 修后绿"。

---

## §7 本轮复核（收口前自审）抓到的问题

| # | 性质 | 内容 | 处置 |
|---|---|---|---|
| 1 | **错误** | §1/§4 把前端路径写成 `backend\frontend\...`；真源是 `frontend\app\admin\sections\KnowledgeSection.tsx`（票面亦无 `backend\` 前缀） | 已改 |
| 2 | **错误（自纠）** | §2 原记的"变异 A = `if n and stale_ids:` → `if n:`"**不具区分度**：实测 `2 passed`。该变异在崩溃路径上删的是空列表 | 换成打 `:229` 那一行的变异，本轮实测 `1 failed, 1 passed`（见 §2） |
| 3 | 歧义 | §6.2 原文"本次全量跑还有 8 条红"易被读成"本轮"；实为**本会话早前那次**，且本轮未复跑 | 已改措辞 |
| 4 | 歧义 | ⚠️ 段原写"两条都会红"却只给了一条的实测依据 | 已改为"`:193` 已实测 / `:273` 为推断" |
| 5 | 疏漏 | 未声明票面第 3 步（不动 `file_hash`/删旧异常分支）的遵守情况 | 已在 §1 补 |
| 6 | 疏漏 | §2 的 W2 变异读数原属"前轮"读数，本轮未重跑 | 本轮已重跑并改写为实测（§2、§7） |
| 7 | **过期（重要）** | §0 ⚠️ 段与 §5-D1 的前提"守卫不在 `HEAD`"在本轮复核时已不成立：`HEAD` 从 `7eda4bb` 走到 `9557dfb`，提交 `ac426c2` 把守卫（连同我的改动）入了库 | 已改写 §0（标"已消解"、**原记录保留不删**）+ §5-D1（标"无需再裁"） |
| 8 | **推断 → 实测** | §6.1 记"D3 未实测"、§6.4 记"`:273` 基线树会红是推断" | D3 已**实测定性**（§2 末节 + 新增探针 `dispatch-output\d3-article-key-probe-20260927.py`）；§6.4 的问法随"`HEAD` 已含守卫"而作废，两条均改写 |
| 9 | **口径不准（外源）** | §4 沿用了会话早前"真库顶层只有 `chroma.sqlite3`"的说法；实查顶层另有 8 个 07-31…08-04 的 UUID 老 segment 目录 | §4 已补一行更正；"今日零改动"结论不变（`find` 全层级为空 + 指纹未变） |
| 10 | **疏漏（本轮补，三处）** | ① D3 探针只写了路径、没写**跑法**，且未说明它**未跟踪** ⇒ 数字不可核；② §1 未列本轮新增产物；③ 探针是**新建文件、超票面归属清单**，未按"碰归属外先报"显式声明 | ①§2 末节补命令 + 未跟踪说明；②§1 补产物与 `git ls-files` 为空的读数；③§1 补归属声明与撤回方式 |

复核中**逐条读回真源**核对的指针（均无误）：`docs\assistant-briefs\version-safety-review-findings-20260927.md:16`（§0 第 1 行待裁项）、`:180`（§2 中-1）、`:224`（§2 低-2）、`:346-347`（§5 期望指纹 `b551677bddab4b85` / `2026-09-21 02:06:44`）；`backend\tests\test_phase5.py:324`（红行）；`backend\tests\test_knowledge_service.py:88 / :196 / :204 / :222`；`backend\schemas.py:189`；`backend\observability.py:133`；`backend\knowledge_service.py:28 / :184 / :204 / :226-237 / :229`。

另核对：票面自身 `docs\assistant-briefs\next-phase-C-version-write-20260927.md` = 20 行 / 2359 B / 未跟踪 / mtime `2026-09-27 19:06:08`，其归属清单、W1/W2 要求、第 3 步、验收命令与交付判据**与本汇报一致**（本汇报 §1 引用的"票面只读文件"三份即出自它）。

复核后复跑的门禁（工作目录 = `C:\Users\33393\Desktop\ai-legal-helper\backend`；**下表在 `HEAD = 9557dfb` 上又复跑一次，读数逐条相同**）：

| 命令 | 读数 | rc |
|---|---|---|
| `venv\Scripts\python.exe -B -m pytest tests/test_knowledge_service.py tests/test_phase5.py -q -m "not slow" -p no:cacheprovider` | `11 passed, 1 deselected` | **0** |
| `venv\Scripts\python.exe -B -m pytest tests/test_log_field_whitelist.py -q -p no:cacheprovider` | `2 passed` | **0** |
| `venv\Scripts\python.exe -B -m ruff check knowledge_service.py schemas.py observability.py tests/test_knowledge_service.py tests/test_phase5.py` | `All checks passed!` | **0** |
| `venv\Scripts\python.exe -B -m ruff format --check <同上 5 文件>` | `5 files already formatted` | **0** |
| `venv\Scripts\python.exe -B -m mypy .` | `Success: no issues found in 74 source files` | **0** |

`backend\knowledge_service.py` 在两次变异后已按备份还原，sha256 `fa986e230e6de1ca6f3ac51677ffe4be2d70842178417c3bca5985253207aecf` 前后一致。
