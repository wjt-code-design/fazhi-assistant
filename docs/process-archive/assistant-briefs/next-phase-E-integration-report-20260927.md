# E 集成轮工作汇报（2026-09-27）

写给 Owner（可转发）。派单：`docs/process-archive/assistant-briefs/next-phase-E-integration-20260927.md`。
本文把 E 本轮（本职五项 + 对 A–D 的第三方审核 + D1/D2 落地）**汇总成一份**，供你一次读完。
明细正文在 `docs/process-archive/progress-handoff-report-20260925.md` §9.12.1–§9.12.16；本文是它的**一页式汇总**。下表区分历史读数与本轮现量；未标注“本轮复跑”的历史门禁数，不代表本轮重测。

---

## 0. 一页汇总

**最终判定：②（阶段任务完成，候选仍被具名风险阻断）** —— 判定不变，但**阻断路径已换**：原先那条"CI 形状门禁红"在本轮被修掉了。

- **不是 ①**（"本地候选就绪"）：`pip-audit -r` 仍 **rc=1**（138 条 / 10 包，本轮未动 requirements，已现量核）；
  未推送 ⇒ **远端 CI 的真实运行无证据**，本机重放不等于 CI 绿；候选语料**未真实入库**（授权未到 T3–T8）；口令轮换在册未做。
- **不是 ③**（"门禁失败、候选未就绪"）：门禁**不再失败**——纯发布物树上步骤 1–6 全 rc=0（见 §9）。
  原由里的"收集期 1 error + 16 failed"已由票 T-B 消掉并复跑验证；那句"A–D 的归属文件没有一条新红"则已删权（是过度归因，见 §0 末与主报告 §9.12.4 末）。
- 历史表述保留在下面表格里**当轮（E1–E5）的读数**，它们是"修复前"的证据，不回写；现量与归因看 §8–§9。

**你今早那两问的答案（现量在 §5 头两行，明细在主报告 §9.12.15）**

- **推送：不推。** 三条事实决定：`git merge-base HEAD origin/master` ⇒ **无共同祖先**（rc=1）；`rev-list --left-right` ⇒ **192 / 187**；
  本地 `origin/master` ref 比真远端**旧 12 笔**。无祖先 ⇒ 推 master 只能 force，而 force 是你定的禁手；唯一合规形状就是路线 A 的**一次性快照分支**。
  而它前置的**口令轮换还没做**——**轮换之前推，等于先把历史里的凭据暴露面打开**，把最危险的一步排到最前面。
  推也不解锁任何待办（真实入库、pip-audit 落地都不依赖远端）。建议顺序：轮换 → `:104` 复扫（含要不要把 `api.siliconflow.cn` 换成占位符，**这条你未裁**）
  → 推快照分支（**永不 force，回车你按**）→ **拿远端 CI 读数替换本机这份等形重放**。
- **pip-audit：分四档，别当一件事做。** 每一档"升级能不能清零"我都**钉住候选版本重跑 audit 实测**过：
  **两行区间可清零 91/138**（pypdf `<6.0`→`>=6.16.1,<7.0` 实测 77→**0**，直接 import 面只有 1 个文件；fastapi 0.110→`>=0.141,<0.142` 整棵树实测 **0 条**、连带 starlette 那 14 条）；
  **langchain 一族 37 条是"能级迁移"不是升级**（只有 1.x 归零，0.3.x 中间态仍脏：community 0.3.27 自己 0 条却拖出 7 条）；
  **transformers 8 条不碰**（5.10.0 实测 0 条，但它是本地 embedding 链路依赖、我们 0 文件直接 import ⇒ 一动就要重嵌整库 10266 块）；
  **chromadb 2 条不碰且升不动**（两条 `fix_versions` 皆空，**最新版 1.5.9 实测反而 5 条**，再加 `chroma_db` 迁移不可逆、9 文件直接依赖）。
  CI 的门**不为了绿而放宽**：①② 落地后剩 47 条，用**逐条 ID 的 `--ignore-vuln` 白名单 + 每条归因**留档。前置：**任何升级票必须从全新自洽 venv 起步**（现 venv `pip check` rc=1 两条、pypdf/uvicorn 越过声明上限）。

| 维度 | 读数（口径见正文 §2） | 结论 |
|---|---|---|
| 候选语料输入校验 | `--validate-only` rc=**0**，"文件校验通过：3 条" | 通过 |
| 候选语料 dry-run（副本库） | rc=**0**，"将删除 **2** 旧片段（其中 **2** 条为无时效遗留块），新增 **3**，跳过 **0**" | 通过 |
| 固定 24 项快速门禁（历史读数；脚本 @ `d3735bb6`） | **23/24**，rc=1；本轮未重跑整套 24 项 | 本轮 T-C 对失败题做了单题追踪，支持“候选池第 3 → rerank 第 8 → top-6 截掉”；不把历史总数写成本轮现量，见 §7(3) |
| CI 形状门禁（纯发布物树） | 提交前复量：ruff/format/mypy 全 rc=0（mypy **74** files）、`pytest --co` **rc=0**；主树定向 `pytest -m "not slow"` **46 passed, 1 deselected** | 原先那条 `--co` rc=2（1 error）**已由 T-B 收口**（`fdf802d`）；`16 failed` 那批 = `test_eval_agent` 2 + `test_gate2_runner` 14，同因同修；收口时整门已在纯发布物树复跑，见 §9 |
| 前端 / 守卫 | `npm run check` rc=0（vitest 54 passed）；`npm run build` rc=0；`test_budget_guard.py` 9 passed | 通过 |
| 依赖审计 `pip-audit -r` | rc=**1**，**138** 条 / 命中 **10** 包 / 扫描 **132** 包 | **红**；**已选型**（不是"未处置"）：两行区间清零 91 条、langchain 37 条走迁移评估、transformers+chromadb 10 条登记不碰 —— 见 §0 末与主报告 §9.12.15 |
| 六步 CI 形状门禁（对代码快照 `360dca7`） | ①ruff ②format(**266 files**) ③mypy(**74 files**) ④agent-quality ⑤守卫(**9 passed**) ⑥全量(**1639 passed / 0 failed / cov 84.91%**) | 该快照六步 rc 全 0。当前 HEAD `553912b` 相对它只增加两份报告文档，未对 `553912b` 字面重跑；代码门禁证据适用于同一代码快照，但**不等于远端 CI 绿** |
| 真实库副作用 | 5 个库的尺寸 + mtime 前后**逐字相同**；chroma 目录指纹 `39f77952…` 不变；无 `-wal/-shm`。**复放这一轮再量一次**：`app.db` 20205568/09-19、`data/app.db` 19939328/09-23、`chroma.sqlite3` 210051072/09-21 跑前跑后一致 | **零写入** |

**本轮实际动过的文件（按提交结果重列，HEAD 后现量）**

| 文件 | 性质 | 状态 |
|---|---|---|
| `backend/knowledge_service.py`、`backend/observability.py`、`backend/tests/test_knowledge_service.py` | T-A 泄露通道 | **已提交 `4a37fe4`** |
| `dispatch-output/task1/hidden_runner.py`、`backend/scripts/gate2_runner.py`、`backend/tests/{test_harness_fact_reveal,test_gate2_runner,test_eval_agent}.py` | T-B 干净检出 | **已提交 `fdf802d`** |
| `dispatch-output/c-retrieval-trace-20260927/`（探针 + 4 次读数 + 对照腿，共 11 文件） | T-C 丢失点定位证据 | **已提交 `15b4249`** |
| `docs/process-archive/progress-handoff-report-20260925.md`（§9.12 全节）＋ 本文 | E 的审核与落地记录 | 已提交于 `553912b`；本次口径更正仅改文档，尚未提交 |
| `dispatch-output/d-t5-import-types-20260927/{run_mutations.py,mutation-readings.txt}` | D1 修的驱动 + 读数 | **已提交并验收**：驱动收口于 `8272322`，后续读数/基线说明见 `27a1285`、`65f2964` |
| `dispatch-output/b-citation-checks-20260927/{run_mutations.py,mutation-readings.txt}` | B 的驱动 + T-D 加固与读数 | **已提交并验收**：初始读数 `6f95d3a`，加固验收 `8272322` |
| `docs/process-archive/assistant-briefs/t7-dependency-upgrade-options-20260927.md`、A/C 回执、五份派单 brief、`docs/process-archive/superpowers/plans/2026-09-27-post-E-followup-recommendations.md` | 其他会话起草并经 F-4 归档 | **已提交 `1504392`，均已跟踪**；T7 是分案建议，未改 `requirements*` 或共享 venv |

**边界（本轮没做什么，一句不省）**：未部署；未真实入库（只 `--dry-run`）；**未推送**；未改历史；
**未调用答案生成模型**；本轮**未运行** `smoke_citation_full.py` 与 `smoke_citation_fast.py`（两脚本 `os.chdir` + `load_dotenv(".env")`，
会装真实配置与真实配额库）。表中的 **23/24 是此前固定快门禁的历史结果**，本轮只对失败题做 T-C 单题追踪；未回显任何 `.env` 值（只报存在性/长度）；未动真实库；未 bulk-stage、未 `git add -A`。

---

## 1. 本轮范围与授权

- **本职五项**（派单第 1–5 步）：对账 A–D 差异与文件归属 → 候选语料 `--validate-only` + 副本库 `--dry-run`
  → 真实 rerank 下的固定 24 项快速门禁 → CI 形状全量门禁 + 前端 + T5 直接检查 → 真实库指纹前后核对。
- **追加一项**（Owner 指示"你先审核一遍它们的工作"）：对 B/C/D 的交付做**第三方审核**——独立复现招牌数字、
  **读代码本体**判正确性（不是"测试绿就算对"）、抓过度声明与不可复现证据。
- **D1/D2 落地**（Owner 裁决 + 指示"你来执行"）：D1 由 E 就地修 D 的变异驱动；D2 把 B 的驱动/读数入库。

---

## 2. 本职五项读数（本机实测）

### E2 候选语料：`--validate-only` 与副本库 `--dry-run`

- 候选文件是**仓库根**的 `data/laws_extra.candidate-20260925.json`
  （派单写的 `backend/data/` 下**不存在**该文件）；sha256 `f32f585259c9a381…`。
- `--validate-only`（绝对路径入参 + 隔离环境变量）：rc=**0**，"文件校验通过：3 条；未连接知识库"。
- `--dry-run`（`%TEMP%` 下的 chroma 副本 + 私有 `QUOTA_DB`/`DATABASE_URL`、`EMBEDDING_PROVIDER=local`、
  `RERANK_ENABLED=false`）：rc=**0**；三条 = 民法典第一千二百六十条 / 劳动争议调解仲裁法第二十七条 / 合同法第四百二十八条，
  前两条各带一条"与 1 条无时效旧块并存（将被 T1 取代）"的告警。
- 副作用为零：真实库尺寸/mtime 前后逐字相同、副本上未生成 `-wal/-shm`、私有临时目录跑完仍为空。
- ⚠️ 口径：`EMBEDDING_PROVIDER=local` ⇒ 走集合 `legal_provisions_cos`（10266 条）；副本里 `legal_provisions_te4`
  同为 10266 条，**两者并存勿混读**。

### E3 真实 rerank 下的 24 项门禁（你已授权）

- 有效配置只报存在性：`rerank_enabled=True`、`rerank_model=BAAI/bge-reranker-v2-m3`、
  端点 `https://api.siliconflow.cn/v1`、两个 key 均 `SET(51 chars)`、`rerank_quota_total=0`。
  **`0` 是"纯开关模式"不是耗尽**：`quota_utils.py:121` 在所有模型 total≤0 时直接返回队列首个模型（不限流）。
- 预检 1 次真实远端调用：`_rerank_docs` 返回非 `None`（该函数**所有失败路径都返回 None**）⇒ 远端真的答了；耗时 2.73s。
- **固定 24 项快速门禁（历史读数）**（`scripts/smoke_citation_fast.py` @ `d3735bb6`，rerank 开）：**23/24，rc=1**；
  红点仍是 `retrieve("周末加班，加班费怎么算？")` 期望 `劳动法 × 第四十四条`。
- 逐题探针（7 次调用）：**7/7 成功、0 降级**；召回 6/7；漏的那题**重排后 top-6** 里无第四十四条。
  ⚠️（E 自审更正）：该探针只记**候选数量**与**重排后 top-6**，**未记送入 rerank 的 12 条身份** ⇒
  "第四十四条不在候选池"**推不出来**，已撤回。
- **⇒ 定位结论（票 T-C，E 独立复跑第 4 次确认）：丢失在重排。**
  - 重排前 12 条候选里，目标**在池内第 3 位**（向量路 rank 3 / 距 0.390）；
  - 真实 `BAAI/bge-reranker-v2-m3` 把它降到**第 8 位**（rel 0.0195 < 6 条噪声条 0.024–0.35）；
  - 最终 `docs[:6]` 截掉它 ⇒ `hit=False`；**对照腿**（同池、关 rerank）它回到 **top-6 第 3 位**。
  - ⇒ 召回没丢、后处理没丢；"rerank 只改序不新增候选，故开了 rerank 也修不掉"**方向反了**——rerank 正是这条红的原因。
  - 边界：**rerank 模型排序质量**问题，非 T1–T5 代码回归；23/24 是历史总数，本轮未复测整体门禁。**修复另开票**。
  - 证据：`dispatch-output/c-retrieval-trace-20260927/`（探针脚本 + 4 份脱敏读数）；真库指纹跑前后不变。

### E4 综合门禁

读数分两种口径，**必须分开看**：

**(a) 纯发布物树**（`git archive HEAD` 解开，只有 tracked 文件、**无 `.env`**）—— 这就是 CI 看到的东西：

| 门 | 读数 | rc |
|---|---|---|
| `ruff check .` | All checks passed! | 0 |
| `ruff format --check .` | 267 files already formatted | 0 |
| `mypy .` | Success: no issues found in **74** source files | 0 |
| `pytest --co -q` | **Interrupted: 1 error during collection**（1645/1663） | **2** |
| `pytest --cov=. --cov-fail-under=70 -q --ignore=tests/test_harness_fact_reveal.py` | **16 failed, 1619 passed, 10 skipped, 18 deselected**，cov **84.91%** | **1** |
| `mypy --follow-imports=skip scripts/import_laws.py`（T5 直接检查） | Success: no issues found in 1 source file | 0 |

两处红**都已逐条落到具体文件**，不是"环境问题"四个字：

1. **收集期 1 error = `tests/test_harness_fact_reveal.py`**：它在 import 期加载 `dispatch-output/task1/hidden_runner.py`，
   后者读同目录 `hidden-cases-v1.json`，而 `.gitignore:77` 整目录忽略了 `dispatch-output/task1/`、该 JSON **从未入库**
   （`git log --all -- '*hidden-cases-v1.json'` 为空），`hidden_runner.py` 反倒被跟踪 ⇒ **任何干净检出都收不了集**。
   **本机工作树因为 JSON 在本地才绿 —— 典型"本地绿 ≠ CI 绿"。**
2. **16 条 failed** = 14 条 `tests/test_gate2_runner.py`（`FileNotFoundError: backend/.env`，`gate2_runner.py:404` 无条件读，
   而 `.env` 被 `.gitignore:26` 忽略）+ 2 条 `tests/test_eval_agent.py` 的 `release_eligible` 断言（**本仓已登记**：
   `gate_exit_registry.py:549` 写明"基线余 2 条红 … 属副本缺未跟踪资产"）。
   ⇒ **16 条 = 副本缺未跟踪资产，与 A–D 的改动无关**（A–D 的文件一律不在失败集合里；`1619 passed` 含 B 新入库的 23 条）。

**(b) 本机工作树口径（对照，非 CI）**：前端 `npm run check` rc=**0**（ESLint 无告警、`tsc --noEmit` 过、vitest **54 passed**）；
`npm run build` rc=**0**（7/7 静态页）；`dispatch-output/agent-quality-20260911` 守卫 `ruff check` rc=0 / `test_budget_guard.py` **9 passed**。

**(c) 依赖审计**：`pip-audit -r requirements.txt` ⇒ rc=**1**，"Found **138** known vulnerabilities in **10** packages"
（chromadb 0.4.24 / langchain 0.1.20 / langchain-community 0.0.38 / langchain-core 0.1.53 / langchain-openai 0.1.7 /
langchain-text-splitters 0.0.2 / langsmith 0.1.147 / pypdf 5.9.0 / starlette 0.37.2 / transformers 4.57.6）。
**这是先前存在的红**，处置路径在 A 的 T7 分案，本轮**未选型、未升级**。

### E5 真实库指纹前后核对

| 路径 | 尺寸 | mtime（前 = 后，逐字相同） |
|---|---|---|
| `backend/chroma_db/chroma.sqlite3` | 210051072 | 2026-09-21 02:06:44.4748985 |
| `backend/app.db` | 20205568 | 2026-09-19 00:28:25.7167075 |
| `backend/data/app.db` | 19939328 | 2026-09-23 14:51:15.9526019 |
| `backend/data/quota_used.sqlite` | 12288 | 2026-09-19 00:12:51.5697889 |
| `data/quota_used.sqlite` | 4096 | 2026-08-08 04:18:56.2141190 |

外加两条独立读数：`backend/chroma_db` 目录指纹前后同为 `39f779520bd796ef…`；
`find backend/chroma_db backend/data data -newermt '-30 minutes'` **无输出**；目录内**无 `-wal`/`-shm`**。
⇒ 本阶段对真实库**零写入**。

---

## 3. 对 B/C/D 的第三方审核（只认本机复跑与本机读数）

### 3.1 招牌读数逐条复现（rc 全 0）

| 交付 | 命令（cwd = `backend`） | 读数 |
|---|---|---|
| B | `pytest tests/test_smoke_citation_assertions.py` | `23 passed` |
| C | `pytest tests/test_knowledge_service.py tests/test_phase5.py -m "not slow"` | `11 passed, 1 deselected` |
| C | `pytest tests/test_log_field_whitelist.py` | `2 passed` |
| D | `pytest tests/test_import_laws_preflight.py` | `17 passed` |

⚠️ **更正我自己**：主报告 §9.12 早前把 B 记成 `30 passed`，那是 **B 的 23 + `test_qa_citation_gate_symmetry.py` 的 7**
的**合并跑**；**B 自己的套件是 23 条**。

### 3.2 代码本体判定（判"对不对"，不判"测试绿不绿"）

- **B fast**：`recall_hit` 要求**同一条 doc** 同时满足 `source∈期望 ∧ article∈期望`（"任中一条"语义保留）✅；
  旧形状 `any(a in arts for a in ea)` 已删净。
- **B full**：`citation_pairs` 先按**生产写库顺序**过 `output_normalize.expand_law_names → expand_citations` 再邻接配对；
  `answer_cites` 比的是**归一法名相等 ∧ 条号原文 ∈ 期望列表**。两条"不许漂移"绊线**已现量核对**：
  `_ART_CORE` 是 `retrieval._ART_FULL_RE.pattern` 里的逐字子串；`norm_law_name` 与 `_source_key` 等价；
  `output_normalize` **仅 import `re`** ⇒ "import 期无模型成本"成立。
- **C**：写库侧确用**裸真值**（`knowledge_service.py:184`/`:204`），端点侧现亦为**裸真值**（`schemas.py:189`）✅。
  守卫的**过拒面已排**：`KnowledgeAddIn` 只被 `main.py:2669 admin_add_knowledge` 一个端点消费，`origin` 由服务端写死 `manual`。
  `law_version_judgment_failed` 已登记 `observability._ACCOUNT_FIELDS`，且 `test_log_field_whitelist.py` 是
  **带 watch-it-fail 自证的 AST 哨兵** ✅。

### 3.3 三处过程缺口（不影响已复现的读数，影响"可复核性"）

1. **B 的证据原本不在库里**：`dispatch-output/b-citation-checks-20260927/` 未跟踪且未被忽略 ⇒ B 的"8/8 KILLED"
   **无法只凭仓库复现**。**已由 D2 处置**（见 §4）。
2. **C 没有可复跑的变异驱动**：`dispatch-output/` 下与 C 相关的只有 `d3-article-key-probe-20260927.py`；
   C 报告 §2 的变异 A/B 是**散文描述**，无脚本 ⇒ 不可由文件复跑。
3. **C 的 `.strip()` → 裸真值这笔，git 里看不见**：`git diff 7eda4bb HEAD -- backend/schemas.py` 把整个守卫渲染成
   **纯新增 `+`**，没有一行 `-` 是删 `.strip()` 的 ⇒ "修前判 `self.article.strip()`"**既不能证实也不能证伪**。
   **当前态**可核：`:189` 是裸真值。

### 3.4 本轮最重的一条：**D 的变异仪在新树上是"假绿机器"**

- **复现**：删掉副本树后按驱动自己的跑法重跑 ⇒ `干净基线：rc=2  1 warning, 1 error in 15.66s  失败集 = 1 条`，
  随后 **5 只变异全部**输出 `⚠️ 零新增红 —— 这条接线在本仓所有测试里没有守卫（变异存活）`。
- **根因**：`build_tree()` 只复制 `git ls-files` 的结果，而 `hidden_runner.py` 在**模块级**读那两个**未入库** JSON
  ⇒ **任何新树的收集期必报错、整会话中断**（15 秒就结束；D 的原始读数是 136 秒 / `27 failed, 1590 passed`，说明当时真的跑完了）。
- **后果**：D 公布的 5 处变异读数**不能由入库的驱动复现**；且驱动**缺一道闸**——基线没真跑过时必须中止
  （**B 的驱动有这道闸，D 的没有**）。
- **公平起见**：D 的**方法**（锚点唯一预检、`--collect-only` 单取分母、junit 集合差分、sha256 还原）是本案最扎实的一份，
  5 处锚点在原运行里也都过预检；缺口是"树自足"与"基线必须真跑过"，**不是算术或结论**。

---

## 4. D1 / D2 落地结果

### D2（B 的证据入库）—— 已执行

提交 **`6f95d3a`**（`test(票B): 引用冒烟变异仪与读数入库（8 只全 KILLED，可复跑）`），**2 文件 / 199 插入**，
只提这两个文件、`git diff --cached --name-only` 逐个核过**未夹带**；**未推送**。
⇒ B 的 8/8 自此**可由仓库复现**。⚠️ 入库的 `mutation-readings.txt` 是 **E 按同一驱动复跑**的产物
（读数与 B 公布同集合），非 B 原件——B 原件已被 E 的复跑覆盖。

### D1（D 的驱动）—— 已由 E 就地执行

改的是 `dispatch-output/d-t5-import-types-20260927/run_mutations.py`（**+67 / −6**），四处：

1. **基线闸**：`junit 用例数 < collect-only 数` 即中止并 `return 3`，**且不写读数**。判据**不是** `==0`——
   收集期报错时 junit 里仍剩 **1 条**"收集错误"伪用例（实测 `collect-only=1663 / junit=1`）；
   **E 第一版写成 `==0`，实测没拦住**（已把这次踩坑记进驱动 docstring 与代码注释）。
2. **树自足**：`build_tree()` 显式补拷**两个**未入库的收集期依赖
   （`dispatch-output/task1/hidden-cases-v1.json`、`hidden-round-protocol-v1.json`），缺任一即 `raise SystemExit`。
   **只补第一个仍会断**（E 实测踩过）。
3. **附录保留 + 落 LF**：`write_readings()` 只重写机器读数、原样保留 `## 附…`；且把 `Path.write_text` 换成
   `open(..., newline="")` —— 前者在 Windows 上把 `\n` 翻成 CRLF，而本仓 `.gitattributes` 是 `* text=auto eol=lf`
   ⇒ index 归一后 `git status` **永显 ` M`**（实测：一次退化运行把该文件写成 **111 行全 CRLF**，HEAD 是纯 LF）。
   **这条是 D 原驱动自带的缺陷**，非本轮引入。
4. 驱动 docstring 补 ④–⑦ 四条硬约束。

**负向自检（证明闸真的会红）**：临时把 protocol JSON 移出副本树 ⇒ 驱动打印
`‼️ 基线没真跑过（collect-only=1663，junit 用例数=1）⇒ 变异实验无意义，直接退出。`、`rc=3`，
且 `mutation-readings.txt` **逐字节未动**。`write_readings` 另做独立自检（往临时路径喂旧内容 + 一段 `## 附`）
⇒ `CRLF=0 / 附录在 / 正文在`。

**修复后的有效运行（exit 0）**：`副本树建好：617 个文件（含 2 个未入库补拷）`；**分母 1667**
（退化运行时是 1663 ⇒ 那两个 JSON 缺席时正好少收 4 条）；干净基线 `rc=1  21 failed, 1621 passed, 25 skipped`、
`失败集 = 21 条 / junit 用例数 = 1667`；**五处变异全部 KILLED：新增红 4 / 1 / 6 / 1 / 2**。

> **D 的原始结论未被推翻**：D 原跑为 **3 / 1 / 6 / 1 / 2**，与本次**同集合**；M1 的 3→4 已定到 **C 的拆条**
> （`test_version_judgment_crash_keeps_old_chunks` / `..._is_visible_in_structured_log` 两条都在 `setup` 上红）。
> **D1 修的是可复现性（新树会复现出"全存活"），不是结论。**

**D1 第③项（时效声明）已落在读数文件的 `## 附六`**：披露"邻居 `test_knowledge_service.py` 已由 C 拆成两条"、
`test_import_laws_preflight.py` 的 sha256 交付态 `1e85b76989232a7b` 与 D 那次 `d446ed48a914a8dd` 的关系、
`knowledge_service.py` 无漂移（`fa986e230e6de1ca`），并**标注 `## 附一` 那份"27 条既有红"已过期**（现 21 条）。

**D1 带出的新发现（待裁，见 §5 待裁①②）**：副本树 `TREE_SPECS` 不含仓库**根文件** ⇒ B 的
`test_smoke_citation_assertions::test_gate_item_counts_match_contributing` 在树里是**环境假红**
（它读**根目录** `CONTRIBUTING.md`）。E **未擅自改树、也未改任何工程码**，只做标注。

---

## 5. 待裁与待办台账（**一句话一条，可一词一行答**）

| # | 事项 | 我的建议 |
|---|---|---|
| **推送** | 现在推远端吗？ | **不推**（无共同祖先 ⇒ 只能 force，force 是你定的禁手；快照分支的前置**口令轮换未做**，轮换前推=先打开凭据暴露面；推也不解锁任何待办）。要推的合规形状与顺序已写在 §0 末与主报告 §9.12.15(4)，**回车由你按** |
| **pip-audit** | 138 条怎么选？ | **①pypdf 抬区间**（实测 77→0，import 面 1 文件，先做）→ **②fastapi→0.141**（整棵树实测 0，连带清掉 starlette 14 条，①+②=91 条）→ **③langchain 37 条排"迁移评估票"不排升级票**（只有 1.x 归零，0.3.x 中间态脏）→ **④transformers 8 条 / chromadb 2 条登记不碰**（前者一动要重嵌整库；后者最新版实测 5 条比现在更差且迁移不可逆）→ **⑤CI 门不放宽**，剩 47 条用逐 ID `--ignore-vuln` 白名单 + 归因。**任何升级票的前置 = 全新自洽 venv** |
| 待裁① | 把 `CONTRIBUTING.md` 加进驱动 `TREE_SPECS`，消掉那条环境假红？ | **两侧都已解决**：B 侧由 T-D 带进 specs；**D 侧由我按 Owner 的「按建议动手」补上**——副本树 615→616、机器基线红 **5→4**、五只变异仍 KILLED 5/5、自证 5/5 PASS、rc=0（现量见主报告 §9.12.14） |
| 待裁② | 让驱动把**基线红清单**（不止计数）机器生成进读数？ | **已实现**（`8272322`）：D 的读数现在有 `### 基线红清单（机器生成，逐条列全；共 5 条）`，并写明"不要用人工附录里的旧名单对账"。附一那份手写 27 条**保留原样**（它已过期，是历史证据） |
| 待裁③ | 本轮产物**是否现在提交**？ | **已执行**：T-A/B/C 与报告先后提交；T-D 驱动/读数于 `8272322` 收口，其他派单、回执、T7 分案和计划于 `1504392` 归档。最初提交时的“扣住”是阶段性状态，已不适用于当前文件状态。全程未 `git add -A`、未推送 |
| 派单 | 后续派单书 `docs/process-archive/superpowers/plans/2026-09-27-post-E-followup-recommendations.md` 的 **A–F** 六项谁做？ | **A–F 全部执行完毕**（按你发话"直接派子 agent 执行"）：A/B/C/D 由我派发 + 独立复跑验收（§7），E 项就地执行、F1 已撤回并定论，**F 项 1–5 由我收口**（§8、§9、主报告 §9.12.12–13）。剩余待裁只有 A-①/A-② 与下面几行 |
| F1 | §9.12.3 "第四十四条**根本不在候选池**" 过度归因 | **已撤回，并已定论**：票 T-C 实测**丢在重排**（池内第 3 → rerank 降到第 8 → 截掉；对照腿关 rerank 即命中）。见 §7 |
| A-① | `backend/retrieval.py:431` 有**同类形状**的 `exc_info=True`（`"QA 引用的条文核验读库失败…"`） | **改判：建议保留、不收口**。我先前那句"同一泄露形状、留一处等于留半扇门"只比了形状、没读函数本体；读完的事实是——这条链上没有任何 `raise` 把条文正文拼进异常消息（`retrieval.py` 全文只有 `raise_for_status()` 与一个裸 `raise`），`_valid_docs` 虽把正文读进 `Document`，但抛出来的只会是 chroma 返回形状类的 `KeyError/IndexError`（消息里是缺失的键名）。而 T-A 那处的异常消息是**我们自己用 `new_content` 拼的** ⇒ 两者不是一个泄露面。这里的栈反而有诊断价值（键形状问题不带栈看不懂）。详见附录 A 第 7 条 |
| A-② | T-A 去掉 `exc_info` 后该分支**不再有栈**，只剩类名 + 法名/条号 | **建议接受**（要原文可按同法名/条号本地复现）；若要"可归因又不泄原文"，需在 `observability` 侧加**脱敏归因字段**——那超出 T-A 白名单，另裁 |
| A/B/C | 三票交付与验收（全通过；T-C 结论=**丢在重排**） | 见 §7；**只有 A-①/A-② 待裁** |
| D | T-D（两枚变异驱动加固） | **已交付 + 已验收 + 已入库 `8272322`**（B 8/8、D 5/5 全杀，自证 B 5 条 / D 5 条我本机全 PASS）。E 验收时另补一条"固定快照"闸，见 §7(6) |
| B-D1 | `ac426c2` 提交信息没写 B 那三处改了什么 | 台账补一行归属，**不 amend** |
| B-D2 | `docs/ARCHITECTURE.md:107/:109`、`docs/capability-matrix.md:29` 仍是旧计数（`17 项`/`10 场景`） | 改成脚本现量 `24 项`/`12 场景` |
| 派单-E | 派单书 §E：T7 分案三处自相矛盾/不成立 | **已修订并归档**：`docs/process-archive/assistant-briefs/t7-dependency-upgrade-options-20260927.md` 已在 `1504392` 跟踪——更正 ①历史 23/24 口径 ②pypdf 失败回退路径 ③FastAPI 失败回退步骤。**只记账，未动 `requirements*/venv`** |
| B-D4 | CONTRIBUTING 的"24 项"与测试的"23 条"易串轴 | 一行改动待你授权 |
| C-D2 | `observability.py:133` 那笔是否保留 | 待你裁 |
| C-D4 | 今天这笔是否折进 findings §2（C 台账唯一必须由你**指定文件归属**的一条） | 待你裁 |
| 归属 | **同类物两种待遇**：D 的产物已入库（`9557dfb`），而 A 的回执、A 的 T7 分案、C 的回执、B 的变异产物目录、**五份派单 brief 本身**均未跟踪 | **已按派单书 F 项 4 收平**（`1504392`，38 文件）：口径取"必要派单/回执/评审/可复现证据一律入库"。入库前扫密 0 命中、7 个证据文件由 CRLF 归一为 LF |
| 忽略 | `.qoder/`、`caddy_data/`、`caddy_config/`、`backend/.ptmp-s4-run2/`（`git check-ignore -v` 全 NOT IGNORED） | **已补**（`a5c129d`）：四个目录现量**被跟踪文件为 0**，故忽略不会让任何东西"看起来消失"。写 `caddy_data/` 的真实理由是 Caddy 一签证书就往它下面落**私钥** |

---

## 6. 现量核验指针（可复核，2026-09-28 收口时重测）

- **哈希指针只写命令、不抄数**：本文件每改一次，里面写的「当前 HEAD」就当场过期（这一轮我自己就撞上过）。
  复现命令：`git log --oneline 6f95d3a..HEAD`——**笔数与哈希一律以该命令为准，我不在这里抄数**。
  清单：`4a37fe4`(T-A) → `fdf802d`(T-B) → `15b4249`(T-C 证据)
  → `6ce1e8b`(两份报告) → `1504392`(归档 F-4) → `d41cf5e`(旧计数修正) → `a5c129d`(.gitignore)
  → `8272322`(T-D) → `27a1285`(读数附七)。E 全程**未推送、未改历史、未 `git add -A`、未部署、未动真实库**。
- 本次复核开始时 HEAD = `553912b`；该提交只更新两份报告。当前这次口径更正也只修改两份报告，尚未提交；未改代码、测试、依赖或数据，也未重跑门禁。
- **当时的提交记录**：§9.12.1–§9.12.11 自 `6ce1e8b` 起已入库；此前汇总收口时，主报告为 1425 行、对 HEAD 的 `git diff --numstat` 为 **94 / 2**（HEAD 版 1333 行）。
  那 2 行删除是把"环境假红"那段的措辞改准，**未删任何已提交的历史结论**；这些行数与 diff 是当时快照读数，不是本次文档更正后的现量。
- 明细落点：主报告 §9.12.1–§9.12.15（§9.12.10 = A/B/C 验收、§9.12.11 = 提交执行记录、
  §9.12.12 = 票 T-D 验收与 E 的补闸、§9.12.13 = F 项 2/5 综合门禁与最终回报、§9.12.14 = Owner 裁后动手的两件（A-① 改判 + D 补根文件）、
  **§9.12.15 = 推送判定 + pip-audit 选型实测 + 六步门禁对当时代码快照 `360dca7` 的复放；§9.12.16 记录后续 HEAD 对账**）。
- 证据落点（全部已入库）：变异读数 `dispatch-output/d-t5-import-types-20260927/mutation-readings.txt`
  （机器段 + 附一至**附七**）、`dispatch-output/b-citation-checks-20260927/mutation-readings.txt`；
  检索定位 `dispatch-output/c-retrieval-trace-20260927/`（探针 + 5 份读数）；本轮派单/回执/评审 38 文件见 `1504392`。
- 本轮 E 的**仓外**临时读数（`%TEMP%`，不入库）：`e2-dryrun.txt`、`e3-gate-rerank.txt`、`e3-detail-rerank.txt`、
  `e4b-*.txt`、`e-b-selftest.txt`、`e-b-full.txt`、`e-d-selftest.txt`、`e-d-selftest2.txt`、`e-d-full.txt`、
  `e-d-full2.txt`、`e-f2-gate.txt` 与归档树 `e-f2-tree/`；CRLF 归一前的备份 `crlf-bak-20260928/`、
  `tc-crlf-bak-20260928/`、T-D 交付原件备份 `td-delivered-bak-20260928/`、D1 驱动原件 `d1-bak/`；
  §9.12.15 这一轮新增：归档树 `e-f2-tree-20260928/`、六步日志 `e-f2-replay-20260928.log`、
  pip-audit 原始 JSON `pip-audit-20260928.json`（+ `.err`）。**它们只是备份与原始 stdout**：
  入库读数与它们逐字同源，看仓库文件即可复核。

---

## 7. 后续派单（A/B/C）执行与验收（2026-09-27/28 夜；**E 既派发又独立复跑**）

依据：`docs/process-archive/superpowers/plans/2026-09-27-post-E-followup-recommendations.md`；按 `module-dispatch-new` 三契约派发。
**对 skill 的一处偏离（写明理由）**：skill 要求"独立 worktree 隔离"，但本仓 `.env`、`backend/chroma_db`、
`dispatch-output/task1/*.json` 全是**未跟踪/被忽略**的 ⇒ fresh worktree 里全缺（B 的"干净树"证据、C 的真实检索都会缺料）。
故改用**文件白名单 + 各自独立证据目录 + 隔离环境变量**达成同效：三票触碰文件两两不相交，且**谁都不提交**。

**（1）T-A 日志异常泄露通道 —— 通过（E 复跑）**
- 交付：`knowledge_service.py` 去掉 `exc_info=True`（保留 `law_version_judgment_failed` + 异常类名 + 法名/条号）；
  `observability.py` 只改注释（把无举证的"不含条文正文"换成**可查事实** + 举证用例指针）；
  `tests/test_knowledge_service.py` 换替身**把入参正文复述进异常消息**，断言 `exc` 键为空、合成标记/异常原文/`Traceback`/正文记号都不得出现，
  **并新增**"类名 + 法名 + 条号必须可读"的**正向**断言。
- E 复跑：`pytest tests/test_knowledge_service.py tests/test_log_field_whitelist.py -q -m "not slow"` → **5 passed, 1 deselected**（隔离库）；改前同 rc=0。
  关键点：**旧断言 `"injected judgment boom" in payload["exc"]` 本身就是在要求泄露**，删它不算削弱（新断言在"不泄"维度严格更强）。
- 指向待裁：§5 的 **A-①**（`retrieval.py:431` 同类通道，全仓仅剩这一处）、**A-②**（本分支"无栈"取舍）。

**（2）T-B 干净检出测试依赖 —— 通过（E 复跑）**
- 交付：`hidden_runner.py` 模块级 JSON 读取**改为运行期**（`_read_json`/`load_cases`/`load_protocol` + lazy `_facts()`）；
  `gate2_runner.py` 的 `.env` 改"存在才读、缺则回落环境变量"；`test_harness_fact_reveal.py` 自带**脱敏内联夹具**；
  `test_gate2_runner.py`/`test_eval_agent.py` 注入假凭据/假 git rev。**未新增任何文件**（夹具一律内联，保证 `git ls-files` 树上自足）。
- E 复跑（**自己建树**）：`git ls-files` 副本树（**2509 文件、无 `.env`、无盲测 JSON**）+ CI 形状 `pytest --co -q -m "not slow"`
  ⇒ **1649/1667 collected、rc=0、零 collection error**（改前 `1645/1663 + Interrupted: 1 error`）。
  主树（真盲测集在）跑三文件 ⇒ **41 passed**（证明 lazy 路径对真材料仍可用）。
- E 核对：新增行**无** `skip`/`xfail`；`NO_MATCH_REPLY` 由 `PROTO.get(...)` 改字面量（协议不入库，必须如此）。
- 遗留（不阻断收集，供后续票）：`dispatch-output/verify_similarity.py:16`（**被跟踪**）仍模块级读 `hidden-cases-v1.json`，
  但它不在 `testpaths`、不匹配收集模式。

**（3）T-C 检索丢失点定位 —— 通过（E 独立复跑第 4 次）**
- 结论**写回主报告 §9.12.3 的"定位结论"段**：**丢在重排**（目标在候选池第 3 位 → 被真实 rerank 降到第 8 位 → `docs[:6]` 截掉）；
  对照腿（关 rerank、同池余弦精排）该题命中。
- E 复跑：`probe_trace_44.py everify1` ⇒ 与探针前 3 次**逐条一致**；真库指纹 `620bf0127dee` 前后不变。
- 边界：探针**未跑整门 24 项**（纪律使然）；"23/24 总数"仍是历史读数，本次只做**单点复现 + 机制定位**。

**（4）E 在验收中发现并就地修的问题（纪律事故，落正文）**
- **子助手把 13 个文件整篇写成 CRLF**（HEAD 侧均为**纯 LF**）。T-A/T-B 侧 3 个：`observability.py`（241 CRLF）、`tests/test_eval_agent.py`（401）、
  `tests/test_gate2_runner.py`（717）。T-C 侧 10 个：`dispatch-output/c-retrieval-trace-20260927/` 的**全部读数**（合计 5891 处 CRLF；探针 `.py` 本身是 LF）。
  E 已**逐文件归一为 LF**（备份 `%TEMP%/crlf-bak-20260928/`、`%TEMP%/tc-crlf-bak-20260928/`），
  归一后每文件 **CRLF 数 == 归一后 LF 数**、`git diff --stat` 只显示意图内的行数变动 ⇒ 内容无损。
  **根因**：子助手写入路径默认 `newline=None`（同 §4 第 3 条那个 D 驱动老毛病）。
- ⇒ 纪律补充：**派发契约要显式要求"落 LF、改完自量 `CRLF=0`"**，且**集成者在 `git add` 之前必须复量一遍**——
  实测唯一自动信号是 `git add` 时那句 `CRLF will be replaced by LF the next time Git touches it`，`git diff --stat` **根本不提示**。

**（5）本轮新增待裁/待办**
- 待裁③｜`retrieval.py:431` 同类 `exc_info` 是否同批收口（§5 A-①）——**仍未裁**，且本轮提交后它是全仓业务点**唯一**一处。
- 待裁④｜T-A "无栈"取舍是否接受，或另加"脱敏归因字段"（§5 A-②）——**仍未裁**。
- 待办｜T-D（两枚变异驱动加固）——**已交付并验收入库**，见下面第 (6) 节。

**（6）T-D 交付、E 复跑与验收补闸（`8272322` + `27a1285`）**
- 交付内容：两枚驱动都加上「每只变异验运行完整性（本次 junit 用例数 ≥ 基线）」与「无效/存活/还原失败一律非零退出」，
  基线红清单改为**机器生成逐条列全**；B 改到**副本树**施变、还原进 `finally`、并逐文件核对 live sha 未动。
- E 本机复跑：B 自证 **5/5 PASS**、B 全量 **8/8 KILLED rc=0**（在库读数由我这次运行产出）；
  D 自证 **4/4 PASS**、D 全量 **5/5 KILLED rc=0**，与交付版**逐条一致**（175 对 175 行，5 处差异全在被 220 字符截断的
  消息尾部：新分配的 UUID 与并发用例的消息顺序）。全程活动工作树三个变异目标 sha 未变、真实库 mtime 未变。
- **E 验收时补的一闸**：派单书要求"每轮固定一个明确快照"，交付版只做到一半——归属文件是**每只变异前从 live 重取**，
  并发会话若中途改 `import_laws.py`，基线腿与变异腿就拼成两个版本，而读数里只有建树时刻的 sha，**事后看不出来**。
  现改为归属文件与邻居同走 `.orig`（建树即快照、不回读 live），并加 `snapshot_drift()` 在建树时与跑完后各比一次 +
  `--selftest drift` 证明这把新尺子**能红也能放**（建树 `drift=[]` → 改副本树两个文件各自报出 → 还原后归零）。
  ruff 对照交付版**零新增**（同 1 条既有 `PLW1510`；`dispatch-output` 不在 CI 的 ruff 作用面）。
- **验收中发现的一处新过期**：D 读数的手写附六记着 `knowledge_service.py`"无漂移、sha=`fa986e230e6de1ca`、行号仍为 `:246`"——
  已被 T-A 追过（现量 `480f2af8acb780d4`、锚点在 `:255`，M1 仍唯一仍 KILLED）。按纪律**只标注不回填**，见附七。
- **残留（不阻断）**：D 少一条 `--selftest interrupt` 腿（B 有）。理由成立——D 的变异本来就写在副本树、且每次跑先整树重建，
  中断只会留下一个下次必然被覆盖的临时树；但它**fail-closed 而不优雅**：junit 缺失时 `failures()` 会直接抛异常
  （表现为 traceback + rc=1、且不写读数，方向是安全的）。是否补这条腿，按你一句话。


---

## 8. 提交执行记录（2026-09-28 00:5x，Owner 一词"提交"）

**（1）提交前门（逐条现量，均在本机 E 目录跑）**
- `ruff check`（7 个改动文件）→ **All checks passed**；`ruff format --check` → **7 files already formatted**。
- `mypy .`（CI 同命令）→ **Success: no issues found in 74 source files**（74 = 在册基线计数，作用面无漂移）。
  - 我先前**手点文件**跑 `mypy knowledge_service.py … scripts/gate2_runner.py` 报了 4 条——那是**我的调用方式绕过配置**造成的假信号：
    mypy 的 `exclude` 对命令行显式给的文件**不生效**，而 `pyproject.toml` 注释明写"已知 `scripts/gate2_runner.py` 有 4 个既有错误"。
    教训：**判 mypy 只认 CI 那条命令**（`mypy .`），别把手点文件的读数当门。
- `pytest tests/{test_knowledge_service,test_log_field_whitelist,test_gate2_runner,test_harness_fact_reveal,test_eval_agent}.py -q -m "not slow"`
  → **46 passed, 1 deselected**。
- 扫密（值反查，只打印键名与命中与否）：`backend/.env` 17 个 ≥8 字符的值中，9 个凭据类键（`*_API_KEY`/`JWT_SECRET`/`ADMIN_PASSWORD`/`*_TOKEN`）
  在 12 个待提文件里 **0 命中**；`sk-/AKIA/Bearer` 通用形状 **0 命中**；T-C 证据里的 `token` 字样全是 `tokens` 计数与 `max_tokens` 类字段。
  - **3 处非凭据值命中并仍入库**：`BAAI/bge-reranker-v2-m3`（公开模型名）与端点 `https://api.siliconflow.cn/v1`（厂商公开入口），
    只出现在两份报告的"有效配置"行。该端点**此前不在任何 tracked 内容里**（`git grep HEAD` 0 处）⇒ 这是**首次入库**。
    我判它不构成泄露（非密钥、无账号信息）故**保留**；若你的口径是"`.env` 里出现过的值一律不进仓"，说一声我把这两行改成 `<.env:RERANK_BASE_URL>`。

**（2）落地的四笔**
- `4a37fe4` T-A（3 文件 +51/−9）；`fdf802d` T-B（5 文件 +180/−64）；`15b4249` T-C 证据（11 文件 +6306）；本笔 docs（两份报告）。
- 每笔都先 `git add <显式路径>` 再用 `git diff --cached --name-only` 证未夹带；**未 `git add -A`、未推送、未改历史**。

**（3）我主动扣住的（不在这次提交里）**
- **两枚变异驱动**：`dispatch-output/b-citation-checks-20260927/{run_mutations.py,mutation-readings.txt}` 与
  `dispatch-output/d-t5-import-types-20260927/{run_mutations.py,mutation-readings.txt}`。
  **依据**：T-D 仍在写盘——B 的驱动 00:45 mtime、D 的读数 00:39 mtime，且 B 那两个文件在我提 T-B 之后**新出现 ` M`**。
  未验收的产物不提，正在改的文件提了会锁进半成品。**这是当时的阶段性扣留状态**：T-D 后续于 `8272322` 收口并验收。
- **别的会话起草的文件**：`docs/process-archive/assistant-briefs/t7-dependency-upgrade-options-20260927.md`（A 起草、E 改三处）、A/C 的回执、
  五份派单 brief、`docs/process-archive/superpowers/plans/2026-09-27-post-E-followup-recommendations.md` —— **当时暂扣；后续已由 `1504392` 归档并跟踪**。
- `.qoder/`、`caddy_data/`、`caddy_config/`、`backend/.ptmp-s4-run2/`：`git check-ignore` 全 NOT IGNORED 但**不该入库**（§5「忽略」行）。

**（4）提交时顺手抓到的一条仓库卫生问题（在册事实，非本次引入）**
- `dispatch-output/task1/` **整体被 `.gitignore` 命中**，而 `dispatch-output/task1/hidden_runner.py` 却是**已跟踪**文件
  ⇒ `git add` 该文件时 git 打印 "The following paths are ignored…"（本次内容仍被正常暂存，因为跟踪态优先）。
  后果：以后每次修这个文件都会看到一句误导性的 ignore 警告，且 `git add dispatch-output/task1/<新文件>` 会被**静默拒绝**。
  建议：给 `.gitignore` 加 `!dispatch-output/task1/hidden_runner.py` 一类的显式例外，或把该脚本挪出被忽略目录。


---

## 9. F 项 2/5：固定候选上的综合门禁与最终回报（2026-09-28）

**候选** = `6f95d3a..HEAD`（**笔数与清单以 `git log --oneline 6f95d3a..HEAD` 为准，我不在这里抄数**）；
起点是 T-A `4a37fe4`、T-B `fdf802d`、T-C `15b4249`、报告 `6ce1e8b`、归档 `1504392`、计数 `d41cf5e`、gitignore `a5c129d`、T-D `8272322`、附七 `27a1285`，其后到 HEAD 的几笔都是 docs 与仪表。
**门禁原先只对 `8272322` 的归档树负责**——这一条后来在当时代码快照 `360dca7` 上复放并取代。之后 `553912b` 仅更新两份报告；当前复核的精确 HEAD 口径见 §9.12.16。

**门禁重放**（下表 = **`8272322` 那一轮**的历史读数，树解到 `%TEMP%/e-f2-tree`，**2559 文件、无 `.env`、无盲测 JSON**，用 live venv 解释器在树内跑；
对**当时代码快照 `360dca7`** 的复放在 §0 表格最后一行与主报告 §9.12.15(1)，**六步全 rc=0**；当前 HEAD `553912b` 未被字面重跑）：

| 步 | 命令（与 CI 同形） | 读数 | rc |
|---|---|---|---|
| 1–2 | `ruff check .` / `ruff format --check .` | All checks passed / 全部已格式化 | **0 / 0** |
| 3 | `mypy .` | no issues found in **74** source files（与在册基线同计数） | **0** |
| 4 | `ruff check` + `format --check` `../dispatch-output/agent-quality-20260911` | All checks passed / 4 files already formatted | **0 / 0** |
| 5 | `pytest …/test_budget_guard.py` | 9 passed | **0** |
| 6 | `PYTEST_ADDOPTS="-m 'not slow'" pytest --cov=. --cov-fail-under=70 -q` | **1639 passed, 10 skipped, 18 deselected, 0 failed**，coverage **84.91%** | **0** |

**两条限定，不替我省**：① ~~那轮跑的是 `8272322` 的归档树~~ —— **在当时复核时已由新读数取代**：应 Owner 之问（"现在推不推"需要"最新候选能不能推"的证据），
六步当时在 **HEAD = `360dca7`** 的归档树上重放，六步 rc 全 0（`1639 passed / 0 failed / cov 84.91%`、`mypy 74 files`、`format 266 files`、守卫 9 passed；
日志 `%TEMP%/e-f2-replay-20260928.log`，明细主报告 §9.12.15(1)）。`8272322..360dca7` 的改动面只有四个文件（D 的驱动 + D 的读数 + 两份报告）。当前 HEAD `553912b` 只比测试快照多两份报告文档；没有对该精确 HEAD 重跑六步。
② **本机等形重放 ≠ 远端 CI 绿**：本轮**仍未推送**，远端实际运行**没有证据**——这一条不因为复放而改变，只能靠推快照分支拿到。

**这一轮消掉了 §0 表格原先那条红**：纯发布物树从"`--co` rc=2（1 error）+ `--cov` rc=1（16 failed）"变成 **0 failed / rc=0**。
那 16 条 = `test_eval_agent` 2 + `test_gate2_runner` 14，正是票 T-B 修的两类根因（模块级读未入库 JSON、无条件读 `.env`）。
但我不会把它写成"无回归"——它只说明"这两类已复现的门禁失败被修好、修完跑完整套门没引入新红"。

**剩余阻断（任一都足以让候选停在"未就绪"）**：

1. `pip-audit -r requirements.txt` **rc=1**（138 条 / 命中 10 包 / 扫描 132 包）。本轮**未动** `requirements*`
   （`git diff --name-only 6f95d3a..HEAD` 里没有任何 requirements/lock/venv 路径，已现量核）；**选型已给**（§0 末 + 主报告 §9.12.15(3)），**执行需你另行发话**——它要求先建全新自洽 venv，那不是我这一轮能顺手做完的。
2. **远端 CI 无证据**（未推送）。本机六步等形重放全 rc=0 **不能替代**它；判"推不推"见 §0 末——**我的建议是不推，且不推的理由是顺序（轮换在前），不是"门禁没绿"**。
3. **候选语料未真实入库**（授权只到 S0-a/b/c + T1 + T2）。
4. **口令轮换未做**（`:104` 已改成形状规则，真轮换是你的动作）。
5. 两处待裁：`retrieval.py:431` 的同类 `exc_info`（本轮提交后它是全仓业务点**唯一**一处）、票 T-A 之后该分支"无栈"是否可接受。

⇒ 派单书 F 项 5 的原话是"门禁仍失败则候选仍未就绪"。本轮门禁不再失败，但 1–4 仍在 ⇒ **判定维持 ②、理由更新**。

---

## 附录 A：本轮 E 自己的自审事故（按规矩落正文，不藏）

1. **D1 第一版的基线闸判据写错**（`==0` 而非 `< collected`）⇒ 第一次重跑**没拦住**、又产出一次"全存活"退化读数。
   诊断依据：`collect-only=1663` vs `junit 用例数=1`。已修并写进代码注释。
2. **只列了一个未入库 JSON**：漏了 `hidden-round-protocol-v1.json`（`hidden_runner.py:29` 模块级也读它），
   被自己的负向自检抓出来，已补齐。
3. **复跑 D 的驱动覆盖了在库读数**（用退化读数顶掉 D 的 132 行）。已用 `git show HEAD:…>` **逐字节还原**
   （HEAD = index = worktree，blob `df1e3847…`），并清掉残留的 stat-cache 幻影 ` M`。教训：**跑别人的驱动前先确认它会不会写回在库产物**。
4. **对话中我曾说"E 的最终判定仍未给出"——这是错的**：判定 **②** 早在 §9.12.7 已落盘。特此更正。
5. **§9.12.3 的"第四十四条根本不在候选池"是我的过度归因**（由后续派单书 §C 独立复核指出，本轮已撤回）。
   我的 E3 探针只记了候选**数量**（12–15）与**重排后 top-6**，**没记**送入 rerank 的 12 条身份 ⇒
   "最终 top-6 无它"推不出"候选池无它"。教训：**声称某环节"丢失了目标"前，先确认自己是否真的观测了那个环节的输入**。
6. **我把本文件"附录 A"的标题整节吃掉了**：插入 §8 那次编辑里 `old_string` 含标题行、`new_string` 忘了把它带回去
   ⇒ 标题消失、下面 1–5 条正文还在，从文件尾部看只像"少了一条分隔线"，肉眼很容易放过。追加 §9 时才发现并补回。
   这是本仓在册事故"old≈new 的 Edit 会静默合并两行"的**姊妹形状**：替换块里含 markdown 标题时，
   **正文存在不等于标题存在**，改完必须 `grep -n "^## "` 数一遍标题，而不是只看渲染出来的段落还在不在。
7. **A-① 我给的"同批收口"建议是过度归因**（Owner 裁"按建议动手"后读函数本体才发现）：我只比了形状——
   「`logger.warning(..., exc_info=True)` 且异常在含正文的作用域里被捕」——就判它与 T-A 同一扇门。
   实际不同：T-A 的异常消息是我们自己用 `new_content` 拼出来的；`retrieval.py:431` 捕的是
   `exact_article_lookup()` 里 chroma 读库的异常，那条链上没有任何 `raise` 把正文放进消息，
   能进 `exc` 的只有键名与栈帧。⇒ 教训：**"同一形状"不是"同一风险"，判泄露面要读到被调函数本体的 raise 语句**，
   不能停在调用点那一行。这条改判同时把 §5 的 A-① 从"建议收口"改成"建议保留"。
8. **"pypdf 一行 `>=6.16.1,<7.0` 就清干净"这句当时没有读数支撑**：pip-audit 的 `fix_versions` 是**离散版本号列表**
   （pypdf 给了 28 个、starlette 6 个），不是区间，我把它当区间读了一遍就写下"一行"。方向碰巧没错，
   **但当时的形态是推理、不是证据**。现在补了证据：把 `pypdf==6.16.1` 钉住重跑 audit ⇒ **0 条**。
9. **"`fix_versions` 为空 ⇒ 永远无解"这个推法被实测打断**：transformers 那两条空 fix 的 ID，在 **5.10.0 实测是 0 条**
   （OSV 没列修复版本 ≠ 更高版本仍受影响）；chromadb 那边**恰好成立**，但那是**跑出来的**——最新版 **1.5.9 实测 5 条**，
   比我们现在的 2 条**更差**。⇒ 教训：**判"升上去还中不中"只有一个办法：钉住候选版本再跑一次 audit**；
   我上一轮给 chromadb 的"风险接受"是形状理由，这一轮才是读数。
10. **一条 blast-radius 的 grep 是双向假读数**：`grep -rhoE ... | grep -v "^./venv"` 过滤的是**匹配行**而不是**文件路径**
    ⇒ venv 里的 import 全被算进来（第一次给出"from langchain_core **3816** 处"这种数）；同一条式子又用 `^(from|import) pypdf`
    锚死行首 ⇒ **漏掉函数内缩进的 import**，于是 pypdf 报 **0 文件**（真值 1）。一个命令里同时错了两个方向，一个偏高一个偏低。
    重测（`find -not -path "./venv/*" -print0 | xargs -0 grep` + `^[[:space:]]*` 允许缩进）才给出 §0 那四档排序的依据：
    **pypdf 1 文件、chromadb 9 文件、`langchain_*` 28–33 文件，starlette / transformers / langchain-community 各 0 文件**。
    **同一个 138，要读到 import 面才分得出轻重** —— 只看 audit 条数，我会把 transformers 和 pypdf 排成同一类票。

---

## 十一、本地候选收口（2026-09-28）—— 一页式

执行入口 `docs/process-archive/superpowers/plans/2026-09-28-local-candidate-closeout-plan.md`（A–F）；证据索引
`dispatch-output/local-candidate-closeout-20260928/README.md`。**明细正文见
`docs/process-archive/progress-handoff-report-20260925.md` §9.12.17，两处使用同一份来源数据。**

**① 结论（F 节三态）**：**阶段仍未完成 / 候选受阻** —— 技术门禁与数据副本验收都通过，
但**依赖风险 47/57 条未获你接受**、**真实 rerank 未复验（凭据未轮换）**。按 F 节判据，这两条不解除就不能给"就绪"。

**② 代码落在哪**：**只在候选分支** `codex/local-candidate-closeout`（起点 `aec8d5c`），**未合入 `master`、未推送**。
四笔 / 7 文件：`ca0eb5e`(pypdf 6.16.1 + PDF 解析异常转受控 400 + 新测试) → `ecdc6b3`(FastAPI 0.141.1 + mypy 标注 + 限流用例)
→ `39f4266`(留痕捕获改独立 Handler) → `fbc29e8`(T7 分案修订)。`master` 仍是 `aec8d5c`。

**③ 提交后门禁（对无未提交修改的 `fbc29e8` 候选树，日志 `postcommit-gates.log`）**

| 步 | 读数 | rc |
|---|---|---|
| `pip check` | No broken requirements found | **0** |
| `ruff check .` / `ruff format --check .` | All checks passed / 全部已格式化 | **0 / 0** |
| `mypy .` | Success: no issues found in **74** source files | **0** |
| 全量 `pytest -m 'not slow' --cov --cov-fail-under=70` | **1650 passed, 10 skipped, 18 deselected**，coverage **85.25%** | **0** |
| agent-quality `ruff` check / format / `test_budget_guard.py` | All checks passed / 4 files formatted / **9 passed** | **0 / 0 / 0** |
| `pip_audit -r requirements.txt` | **47 条 / 8 包 / 扫 132 包** | **1**（漏洞非零） |

- **审计那行有个坑必须分开记**：首跑（`postcommit-gates.log`）**不是漏洞读数，是扫描器自身失败** ——
  `pypi.org` `ReadTimeout（read timeout=15）`。先分析、只重试一次并加大到 `--timeout 60`，才得到上表 47/8
  （日志 `postcommit-pip-audit-retry.log`）。**扫描器故障不能写成"零漏洞"，也不能和"漏洞非零"混算。**
- 三条多出来的红是**本机路径形态**造成的假红：`/c/Users/...` 被当相对路径解析成 `C:\c\Users\...`。
  **这条坑此前已踩过，这次又踩了三次**，值得写进命令模板。
  ⚠️ **出处更正（2026-09-29）**：此前这里写"换 `C:/Users/...` 重跑全绿，日志标 `[6R]/[7R]/[8R]`"——
  `postcommit-gates.log` 内**查不到这三段**（`grep -E '\[6R\]|\[7R\]|\[8R\]'` → 0 命中，该文件第 6/7/8 步就是 rc=1/2/4 的路径假红本身）。
  上表那行 agent-quality `0 / 0 / 0` 的**当前**依据是 2026-09-29 用候选解释器的复跑（rc=0 / rc=0 / **9 passed**），
  两棵树该目录已跟踪内容逐字节相同（tree 哈希同为 `7fbfe959…`），故可归到 `fbc29e8`；**但它不能追溯证明 09-27/28 那份日志里有过重跑**。细节见交接书 §4.1。
- 41 个保护对象（两处 `app.db`、两处配额库、`chroma_db` 全量文件等）提交+测试后重算 size+SHA-256：**41/41 与 A 基线一致**，
  **真实库零写入**。候选树自带的 `chroma_db` 是 144KB 空桩，不碰主树那份 349MB 真实库。

**④ 依赖风险**：解析集 47/8/132、实装集 57/10/167（多出的是 setuptools/pytest，**两组口径不可相加**）。
**两项升级目标已归零**（pypdf 6.16.1、fastapi 0.141.1 在解析集审计中各 0 条）。
剩余 47/57 条**未获接受**，逐项清单与待裁状态在 `residual-risk-review.md`。**我不代签，也不加忽略项。**

**⑤ 本轮没做什么（一句不省）**：未部署；未写真实库；未推送、未改历史；**未调用生成模型**；
**未运行** `smoke_citation_full.py` 与 `smoke_citation_fast.py`（真实 rerank 因凭据待轮换而暂停，故本轮**没有 24/24 新读数**，
23/24 仍是历史值）；未 `git add -A`；未动共享 venv 与其余 worktree。

**⑥ 要你决策的两件事**

1. **依赖风险裁定**：基于 `residual-risk-review.md` 的具体清单与 47/57 条现状，决定后续修复分案或接受范围。
2. **凭据轮换**：活动 SiliconFlow key 与注释里保留的旧备用 key 是否都已撤销；完成后告知，我再按既有授权只跑一次隔离 rerank。

**⑦ 一条必须转达的仓库缺陷**：本仓库对**嵌套分支引用**（`refs/heads/<目录>/<名>`）的写入会被静默抹除 ——
`git update-ref refs/heads/x/y <sha>` rc=0、reflog 有记录，ref 文件却不存在；`git commit` 到 `codex/...` 分支因此
**提交成功但分支指针不落盘**，下次读就报"分支无提交"。全新仓库不复现、顶层 ref 正常 ⇒ **本仓库特有，根因未定**。
（10ms 级轮询实测把判据钉死了：git 的 `.lock`→ref 改名**成功**，ref 出现后 **113–144 ms** 被**另一个进程**删掉；
手工写的同名 ref 可存活 ≥25 分钟。）本轮靠"提交后按 reflog 回填引用"完成，做法与命令写在 §9.12.17(7)，
探查脚本 `dispatch-output/local-candidate-closeout-20260928/watch-ref-write.py`。**任何人动该分支前先复核引用仍在。**

**⑧ 2026-09-29 接续会话：B 档运行时探针已做完（Owner 裁「先做探针我再裁」）**
上面 ④ 里"grep 判不了内部路径"这一档，证据等级已从**静态 0 命中**升到**运行时 0 调用**：
测试场两腿各 selected 1660 / junit 1660 / failed 0（171.6s 与 176.9s），应用路径场两步跑通，
两场完整性读数都干净（"装桩前应用已加载"为空）。
Core 反序列化与模板构造 7 只桩两场均 **0 调用**（模块都在场，不是缺席造成的假绿）；图片 token 计数 **0 调用**；
模型与 config 加载**各 1 次**，调用方唯一归到 `backend/rag_chain.py:39`，模型名只有常量 `BAAI/bge-base-zh-v1.5`，
`trust_remote_code` **取值 False**；`langchain_community`、`langchain.chains`、`langsmith.middleware` 两场均**从未被导入**（且**不是"包没装"**：
  五个目标模块在候选 venv 里 `find_spec` 全部 FOUND ⇒ 真阴性）。
  ⚠️ **两处要收回的过头话**：① 应用路径场那条 `langchain_openai` "从未被导入"是**驱动没 import `llm_registry`**
  （真实 `/api/chat` 必加载它）⇒ 该场对 G2 是**未测**不是阴性；② `trust_remote_code=False` **只覆盖传这个实参的
  `G3a/G3b`**，`G3d/G3e` 的实参里没这个键。
外联是直接读数，不靠推断，而且是**对全部 206 个网络事件键逐条机器归类**得出的（归类器自带 8 条合成反例，其中 3 条必须判非环回）：
测试场连接类事件 **312 次环回 + 1 次对 `test.invalid:443` 的 DNS 解析尝试 + 35 次"键里没有主机字段"**
（`ctypes.dlopen`/`subprocess.Popen` 单列一档，不折进环回充数）；应用路径场 **0 次**。
那 1 次非环回**已归因到用例**：`tests/test_phase3.py::test_healthz_components` → `backend/main.py:337-342` 的
`socket.create_connection` —— 即 `/healthz` 按 `LLM_BASE_URL` 做的设计内连通探测（假端点解析失败、无 `socket.connect`、连接未建立）。
⇒ 给裁定的一句话：这批读数撑得起"这 22 个运行期入口不在路径上"，**撑不起"这个应用不会 outbound"**。
  而且**这次普查是在外发面被关掉的前提下做的**：驱动把 rerank / 云端嵌入 / 配额都关了或归零，而本机 `backend/.env`
  实为 `RERANK_ENABLED=true` ⇒ rerank 的 `httpx.post(..., Authorization: Bearer)`（`retrieval.py:85-87` 开关短路 `:168`/`:184`）、
  LLM 调用本身、`mcp_server.py:45,51`、`/api/chat/transcribe` 这些**带凭据的外呼一次都没进样本**。
  "外联已普查"这句话只对本轮两个窗口成立，**不是全量外发审计**。
**公告视角由脚本现生**：登记表 26 条公告拆成「有桩可答 **17** 条 / 探针答不上 **9** 条」（闭合 `17+9==26` PASS）；
答不上的 9 条不许读成"已排除"（Chroma HTTP 面、text-splitters 的 XSLT/URL splitter、Trainer/LightGlue/X-CLIP/save_pretrained，
以及 `CVE-2024-7774` 那条映射问题）。
⚠️ **还有一处限定**：测试场里流式生成链是**替身**（`tests/_sse_harness.py:207` 用 `_FakeChain` 顶掉 `main.make_chain`），所以那部分"0 调用"里含"替身没去调真链"的成分 ⇒ 本节所有"运行时 0 调用"都要读成"**这两个窗口内** 0 调用"。同样在外：子进程与第二解释器、类内/闭包里的别名遮蔽、`torch.load`/`pickle.loads` 等**解序列化原语**（只记导入不记调用）、以及 `langchain_core.load.dumpd` 与 `PromptTemplate.__init__` 这类没桩的入口。
边界照旧：**`pip-audit` 仍 47 条 / 8 包红**（探针不减漏洞条数，只升可达性证据等级）、**助手不代签接受范围**；
18 条 slow 未跑；真实 rerank 仍未调用（凭据待轮换）。
逐条判定表由读数现生：`dispatch-output/local-candidate-closeout-20260928/b-probe-verdict-matrix.md`；
仪器本轮付掉的 **17 处**缺陷与修法记在同目录 README 的 G.3——其中一条必须单列：
**提交前扫密发现读数里带着 HTTP 请求体**（审计事件 `urllib.Request` 的 `args[1]` 就是请求体，测试里的假口令被原样记进两份读数），
两份污染读数已从磁盘删除、仪器改为只记 URL/方法/头键名、补哨兵对照，并**用改后代码复跑了全部场**，
本节引用的读数即复跑后的那批。
主张侧另加两道：`b_probe_claim_check.py` 把文档每条数字对着入库读数重算（**条数/通过数只认命令合计行**），
`b_probe_claim_mutants.py` 用逐条反例证明**这条复算真的会红**（杀数只认命令末行"合计 k/n"）。
