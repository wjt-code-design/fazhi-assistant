# 票 D-3：langchain 族跨大版本迁移（**独立迁移票**，2026-10-11 01:2x 写出）

> 派单对象：新会话/builder。本轮收尾**不做**这条（收尾轮里做跨大版本迁移＝制造不可审的巨大 diff）。
> 触发：`reports/decisions-needed-20261010.md` §E 的 A 堆 13 条依赖通报，Owner 已裁"走 D-3 独立迁移票"。
> 本票自足：下面每条指针都写成命令，不需要读别的会话的记忆。**动手前先跑 §1 的三条现量**，与本票不符就先回报差异，不要按本票数字硬改。

## 0 一句话目标

把 `backend/requirements.txt:5-9` 的五个 langchain 族版本窗从 `0.1/0.0.x` 抬到 **1.x**，
让 `pip-audit` 里 langchain 族的 **13 个 distinct 主 ID** 清零，
并且用**同一批尺子在旧树/新树各跑一次**证明"检索与引用校验的语义没跟着 `Runnable` 接口漂移"。

## 1 现场事实（2026-10-11 现量。⚠️ 03:3x 起候选分支多了**第 6 笔 `4300c71`＝docs-only 入册**：`git diff 9e3cfc5..HEAD --name-only` 只含 `docs/closeout-20261010/` 下 27 只 `.md`、**非 docs 文件数 0** ⇒ 代码字节与 `9e3cfc5` 完全相同。你若读到 `HEAD ≠ 9e3cfc5` 属预期，**不算基线被破坏、不必回报**；`0b54396..HEAD` 现为 6 笔。本节下面所有代码相关读数仍以 `9e3cfc5` 那棵树为准，未随文档笔变化。

**分母（审计件复算，复算器 `evidence/audit_axes.js`：`node audit_axes.js <audit-*.json>`）**
- `evidence/audit-cand-runtime.json` 与 `evidence/audit-cand-dev.json` 两份读数**完全相同**：条目 **24** / distinct 主 ID **15** / 涉及包 **5**
  （`chromadb, langchain-core, langchain-openai, langchain-text-splitters, langsmith`）。
- **每包条目数**（同一 ID 在同包可出现两次）：`langchain-core 11` / `langsmith 5` / `langchain-text-splitters 4` / `langchain-openai 2` / `chromadb 2` = 22 族内条目 + 2 = 全 24。
- **每包 distinct 主 ID**：`langchain-core 6` / `langsmith 4` / `langchain-text-splitters 2` / `langchain-openai 1` ⇒ **和 = 并集 = 13，跨包无重叠**（重复只发生在同一只包内部）。
- **langchain 族 distinct 主 ID = 13**；**族主 ID + aliases = 38**；`distinct ID with fix_versions` 与 distinct 同值（⇒ 有无修复线不是差异来源）；族内 CVE 前缀只有 `langsmith 1`，其余是 PYSEC。
- ⇒ 报"关闭几条"必须点名口径（条目 / distinct 主 ID / 主 ID+别名）。在册另有教训：`fix_versions` 是**离散版本号**不是区间，判"升级能否清零"要**钉候选版本重跑**。
- ⚠️ **本票更正一处、并撤回一处我自己的错**：
  `reports/decisions-needed-20261010.md:62` 原写 `core(7)/openai(1)/splitters(2)/langsmith(3)` ⇒ **错**（7 与 3 在任何轴上都数不出来）。
  `reports/owner-decisions-20261010.md:35` 的 `core 6 / langsmith 4 / splitters 2 / openai 1` ⇒ **在 distinct 主 ID 轴上正确，保持原样**。
  （我 01:2x 曾把后一句也判成"不可复现"，那是我只跑条目轴就否人的错，已撤回——见 `decisions-needed` §E 更正注第 2 条。）

**版本窗（`backend/requirements.txt:5-9` 原文）**
`langchain-core>=0.1,<0.2` / `langchain-openai>=0.1,<0.2` / `langchain-chroma>=0.1,<0.2` /
`langchain-huggingface>=0.0.3,<0.1` / `langchain-text-splitters>=0.0.2,<0.1`
⇒ 迁移面是**五个窗**，其中 `langchain-chroma` 与 `langchain-huggingface` **没有通报但必须一起动**（被族内依赖钉住）。

**真实调用面（复算命令在下面，别按旧说法读）**
```bash
W=<候选>/backend
grep -arn "from langchain\|import langchain\|from langsmith\|import langsmith" --include=*.py "$W"
```
现量：**61 行 import**，按档 = 生产 **16 行 / 11 只文件**、`scripts/` **5 行**、`tests/` **40 行**；文件级总计 **39 只**（生产 11 / tests+scripts 28）。
按包名 = `langchain_core 44` / `langchain_openai 8` / `langchain_chroma 6` / `langchain_text_splitters 2` / `langchain_huggingface 1`；**`langsmith` 零直接 import**（它是被 `langchain-core` 钉进来的传递依赖）。
生产 11 只：`agent/runtime.py`、`chunking.py`、`knowledge_base.py`、`knowledge_service.py`、`llm_registry.py`、`main.py`、`memory.py`、`multimodal.py`、`rag_chain.py`、`retrieval.py`、`retrieval_core.py`。
⚠️ **旧说法低估**：`owner-decisions-20261010.md:37` 写"改 `retrieval.py`/`rag_chain.py`/`llm_registry.py` 的调用面"= 3 只；真面是 **11 只生产文件 + 5 只 scripts + 40 只测试**。

**环境与红线（会决定你的读数）**
- 解释器用 **`candidate-envB`**（`C:/Users/33393/Desktop/fazhi-nondeploy-closeout-20261010-b4e7a2/candidate-envB/Scripts/python.exe`，Py 3.11.0；torch 2.13.0+cpu / SQLAlchemy 2.1.4 / chromadb 0.4.24 / fastapi 0.141.1）。本机另有 `backend/venv`（pytest 9.1.1 + fastapi 0.110.3），**两套包集合不同 ⇒ 跨套比较不可归因给单个包**。
- 全量门禁基线（2026-10-11 现量，`evidence/gates-rerun-20261011.log`）：**1925 passed / 0 failed / 10 skipped / 18 deselected / cov 86.35% / rc=0**。

## 2 执行顺序（先产尺子再动依赖；顺序本身是判据）

1. **冻结 API 清单**（不装新包也能做）：从 §1 的 61 行 import 里抽出**被产品真正调用的符号**，逐个查它在 `langchain-* 1.x` 的在册位置与破坏性变更说明。
   现量符号集 = **16 个 `module.symbol`**（61 行 import 全表匹配、`unmatched=0`；复算器 `evidence/d3_symbol_surface.py`，`node`/`python` 皆可，按 `from <mod> import <a,b>` 拆分并去掉 `as` 别名）：
   `langchain_core.documents.Document` 27 · `langchain_openai.ChatOpenAI` 7 · `langchain_core.messages.HumanMessage` 7 · `langchain_chroma.Chroma` 6 ·
   `langchain_core.messages.SystemMessage` 5 · `langchain_core.output_parsers.StrOutputParser` 3 · `langchain_core.messages.AIMessage` 3 ·
   `langchain_core.messages.AIMessageChunk` 2 · `langchain_core.runnables.RunnableSerializable` 2 · `langchain_text_splitters.RecursiveCharacterTextSplitter` 2 ·
   `langchain_core.callbacks.BaseCallbackHandler` 1 · `langchain_core.callbacks.AsyncCallbackHandler` 1 · `langchain_core.callbacks.manager.AsyncCallbackManager` 1 ·
   `langchain_core.embeddings.Embeddings` 1 · `langchain_openai.OpenAIEmbeddings` 1 · `langchain_huggingface.HuggingFaceEmbeddings` 1。
   ⚠️ **就地更正**：本节初稿只列了 12 个符号（把点分子模块的 `from langchain_core.messages import …` 漏掉了），**漏的恰是最危险的两块**——
   `callbacks`（`AsyncCallbackManager`/`BaseCallbackHandler`/`AsyncCallbackHandler`）与 `runnables.RunnableSerializable`，
   这两族在 0.2/0.3→1.x 之间反复改过签名与序列化基类。**别按初稿那张表开工。**
   ⇒ 落 `evidence/d3_api_freeze.json`（每行：符号 / 来源包 / 旧窗 / 1.x 位置 / 是否改名 / 调用点 `file:line`）。
   **没这张表就不要开始装包**——否则 diff 里分不清"依赖升级"与"我顺手重构"。
2. **副本树双跑**（不动候选树、不动主仓工作区）：按在册配方建两棵树 = 旧窗树（`requirements.txt` 原样）与 1.x 树（只改 §1 那五行窗）。
   **副本树自足面（2026-10-11 现量，别再照旧册抄"四个目录"——`task1` 不是顶层目录）**
   - 被跟踪、直接跟着 `git archive`/`ls-files` 走：`release-evidence/`（**319 只，全部 tracked**）、`dispatch-output/`（盘上 848 只 / tracked **844**）、`data/`（11 只全 tracked）、根 `CONTRIBUTING.md`（tracked；消费方是 `backend/prompts.py` 与 `tests/test_agent_runtime.py`、`tests/test_smoke_citation_assertions.py`）。
   ✅ **更正（2026-10-11 04:2x，由 D-3 执行会话 §4-10 抓出、我独立复算确认）**：本行原写「**必须手工带的那一只（不在 git 里）**」——**该断言为假**。现量：`git ls-files dispatch-output/task1/` 列出 `hidden_runner.py`；`git check-ignore -v` 对它 **exit=1**（已跟踪文件不享忽略，`.gitignore:77` 那条只对未跟踪状态生效）；`git archive HEAD dispatch-output/task1` 自带该文件。⇒ **它跟着 tracked 面走，不需要手工带**。我的错因：只看了 `.gitignore` 的模式匹配就下结论，没跑 `ls-files`——正是在册那条「要查『已跟踪却被忽略』必须 `git ls-files | git check-ignore --no-index --stdin`」我没照做。
   - 只读引用、不要复制的：`docs/`（211 只 tracked）留在树里即可；`backend/docs`（3 只）跟着 tracked 走。
   - `__pycache__` 别跨树复用（旧 pyc 会让"源码是否真改了"变得不可判）。
3. **同一批尺子各跑一次**：全量 `pytest -m "not slow" --cov-fail-under=70`、`ruff check`、`ruff format --check`、`mypy`（判据认 `checked N files` 不只认 rc）、前端 `tsc`/`lint`/`vitest` 只作对照（本票不该动前端）。
   ⚠️ **不要跑 `backend/scripts/smoke_citation_fast.py`**（我本票初稿写过这条，撤回）：现量 `:84-87` = `os.chdir(BACKEND)` + `load_dotenv(".env")` ⇒
   它会装载所在树的 `.env`。在**主仓**跑＝拿真实配置与真实配额库去跑（红线）；在候选树跑虽然那份 `.env` 是 **0 字节**（只取过 stat，未读内容），
   但 `backend/chroma_db/chroma.sqlite3` 也在树里（候选该目录 du=144 KB，主仓 357 MB）⇒ 有写进去的风险。
   **替代腿（安全且等价目的）**：`tests/test_citation.py`、`tests/test_qa_citation_gate_symmetry.py`、`tests/test_smoke_citation_assertions.py`
   ——它们经 `tests/conftest.py` 把 `DATABASE_URL`/`QUOTA_DB`/`CHROMA_DIR` 重定向到临时目录，不碰真实库。
   若确需那只 smoke 脚本，只能**在副本树里**跑，且显式给出四个出口环境变量 + 六根 `*_BASE_URL` 全指 `127.0.0.1`、`RERANK_ENABLED=false`。
4. **语义对照**（这才是本票的真目标）：同一组 query 在旧树/新树各跑一次，对照 **召回集合、分数、以及引用校验的 (法名,条号) 配对结果**。
   chroma 的条号键是 `article` 不是 `article_number`（join 错键＝假阴性）；`real_kb` 的尺寸闸认不出副本语料，别把 skip 读成通过。
5. **依赖读数**：`pip-audit --local --no-deps`（或按在册的 `-r requirements.txt` 轴）在 1.x 树上重跑，报**三口径**：条目 / distinct 主 ID / 主 ID+aliases。
   "能否清零"要**钉候选版本重跑**，不能只看 `fix_versions`。

## 3 验收尺子（必须能红，否则判据无效）

- **基线闸**：每趟跑先比 `collected` 与 junit 用例数——`collected` 必须用 `--collect-only` 单取；若 junit 数明显小于 collected，说明有收集期报错，**那次"绿"不算**。
- **负向自证**：在新树上把**一处**迁移后的调用改坏（例如 parser 链的返回形状），必须至少咬红一条在册用例；只报"全绿"而没做过这一步＝未验收。
- **归因隔离**：任何红先做单变量隔离（旧栈 + 新代码 / 新栈 + 旧代码 之一），证明红与新依赖无关才允许归因给别的因。
- **禁止的绿**：不许用"放宽断言 / 删用例 / 加 skip / 改判据"让门禁变绿。若必须改判据，单独列出改前/改后与理由，交 Owner。

## 4 不做什么（越界即跑偏）

不迁移期间顺手重构；不动 `backend/Dockerfile`/CI 之外的部署面；不改前端；不动 `chromadb`（B 堆 2 条走在册接受，另见 D-2）；
不开/不哈希 `backend/.env*`、不读写真实 `app.db`/`chroma_db`/`quota_used.sqlite`；不 `git push`、不改历史、不部署、不碰端口 3021/8088；
不打印任何凭据值（键名/长度/数量可以）；**不做真实模型调用**（真模型验收是 F 那条链，另裁）。

## 5 停止条件（出现就停下回报，别自行推进）

1. 旧树基线就与 §1 的 1925/0/10/18 不符 ⇒ 先回报差异（可能是并行会话动了字节）。
2. 语义对照里出现**召回或引用配对变化** ⇒ 停。这条迁移的代价就是语义漂移，漂移要 Owner 裁，不是 builder 裁。
3. 需要动 `>=0.1,<0.2` 之外的第七个窗（例如上游把 `pydantic`/`openai` 一起钉） ⇒ 停，回来登记新阻塞。
4. 装包动作触到真实 `backend/venv`（本票只许动 `candidate-envB` 与副本树） ⇒ 停并还原。

## 6 交付物（单一可转发文件 + 复算入口）

`reports/d3-langchain-migration.md`：§0 汇总三行、§1 前后门禁与审计读数（三口径）、§2 API 冻结表引用、§3 语义对照表（逐 query）、
§4 我自己犯的错与更正、§5 已知限制、§6 待裁台账（每条一词可答 + 推荐）。
证据落 `evidence/`（含两棵树的 pytest 日志、pip-audit JSON、`d3_api_freeze.json`、负向自证日志）。
**默认不 commit**——除非 Owner 单独授权，且授权时先核工作树归属（并行会话的 tracked 改动不得夹带）。

## 并发纪律（Owner 说这两张票**各开一个新会话并行跑** ⇒ 这一节是硬约束，不是建议）

**唯一的共享可变物 = `C:/Users/33393/Desktop/fazhi-nondeploy-closeout-20261010-b4e7a2/candidate-envB`（那套 venv）。**
独立复核票要用它复跑门禁基线（1925 passed），迁移票天生要装 1.x 包 ⇒ **两个动作碰同一个目录就会互相污染**。

1. **迁移票**：**禁止**向 `candidate-envB` 与主仓 `backend/venv` 安装/卸载任何包。
   新建自己的环境（建议 `运行根/candidate-envC-1x`），所有 1.x 安装只进那里；每次 `pip install` 前先打印 `python -V` 与 `sys.prefix` 证明前缀不是 envB/backend/venv。
2. **独立复核票**：**只读** `candidate-envB`。开跑前先做一次指纹核对，结束前再做一次：
   `python -m pip freeze --all | sort` 与 `evidence/envB-freeze.txt`（或 `evidence/envB-freeze-20261011-015x.txt`）比**行集合**（`diff <(sort A) <(sort B)`）。
   ⚠️ **别比原始 sha**：10-11 实测两份 freeze **164 行、3369 字节、排序后 0 差异，但 sha256 不同**（`fbf306dd…` vs `f6ee1ac0…`）——`pip freeze` 的顺序不稳定，比 sha 会造出假红。
   若行集合出现差异 ⇒ 立刻回报并**停止**门禁复跑（那条基线已经不属于本票）。
3. **两边都不许碰**：主仓工作树与候选工作树的任何写动作（含 `git stash|checkout|restore|clean`）、`backend/.env*`、真实 `app.db`/`data/`/`chroma_db/`/`media/`/`backups/`、docker compose 栈、端口 3021/8088。
4. **前端重建只允许一方**：`next build` 会整目录重写 `frontend/.next`。独立复核票若要复量 J3 purge **可以建**，但**必须先确认没有活进程持有 `.next`**（Windows 上有活进程时 `next build` 会**无报错无进度地卡死**）；迁移票**不许**碰前端构建。
5. **副本树各建各的**：两票的临时副本都落在**运行根下自己名字目录**（`运行根/mig-20261011/` 与 `运行根/review-20261011/`），不许互相读对方的中间产物来"印证"结论——同法复现不等于独立印证。

## 附：两棵树要分清（2026-10-11 现量，别默认候选树就是仓库根）
- **两棵树都有、一律禁读禁写**：`backend/.env`（候选那份只取 stat：**0 字节**、mtime 10-10 02:48，我没读内容）、`backend/data/`（候选 2 只：`eval_agent_complex.json` 与它的 `.rubric.md`）、`backend/chroma_db/`（候选只有 `chroma.sqlite3`，`du -sk` = **144**；主仓 = **357,096**）、`backend/media/`（候选 0 只文件）。
- **只有主仓有**：`backend/app.db`、`backend/data/app.db`、`backend/data/quota_used.sqlite`、`backend/backups/`、`backend/venv`。⇒ 「别在真实库上跑」这条在**两棵树上都成立**；候选那几只是空的/极小的，**不是安全区**。
- **主仓工作树** `C:/Users/33393/Desktop/ai-legal-helper`：HEAD `0b54396`，tracked 脏 **21**、未跟踪 **567**（02:29 现量，与 01:4x 同数）。**候选工作树** `.worktrees/nondeploy-closeout-20261010`：HEAD `9e3cfc5`、`porcelain=0`、5 笔提交。
- 副本树请建在运行根下自己名字的目录里；测试重定向用 `DATABASE_URL`/`QUOTA_DB`/`CHROMA_DIR`/`MEDIA_OUT` 四个出口 + 六根 `*_BASE_URL`（`settings.py` 现量：`llm_base_url` `zhipu_base_url` `dashscope_base_url` `embedding_base_url` `rerank_base_url` **`rerank_native_url`（:209）**），全部指 `127.0.0.1` ⇒ 不出网是构造性质。
