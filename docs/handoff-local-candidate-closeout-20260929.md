# 交接书 · 本地候选收口（pypdf / FastAPI 隔离升级）—— 2026-09-29

> **本文是本批次「本地候选收口 A–F」的接手入口，可单独交给接手者，不需要此前任何会话上下文。**
> 配套三份（按权威顺序）：① 规划书与执行记录 `docs/superpowers/plans/2026-09-28-local-candidate-closeout-plan.md`（**冲突时以它为准**）；
> ② 证据索引 `dispatch-output/local-candidate-closeout-20260928/README.md`；③ 阶段正文 `docs/progress-handoff-report-20260925.md` §9.12.17 与
> `docs/assistant-briefs/next-phase-E-integration-report-20260927.md` 第十一节（两者同源）。
> 本文只写**接手真正需要知道的东西**：状态、命令、读数、坑、以及还没定的决策。

---

## 0. 30 秒定位

- 仓库：`C:\Users\33393\Desktop\ai-legal-helper`（Windows / Git Bash；**全部本地提交，远端未推送**）。
- 发布线 `master` = `87e5227`（**本文初次落地的那笔提交**；其后只可能再叠加文档提交，一律以 `git log` 实测为准）；
  **代码候选**在另一个 worktree 的分支上：`codex/local-candidate-closeout` = `fbc29e8`
  → 目录 `C:\Users\33393\.codex\worktrees\local-candidate-closeout\ai-legal-helper`。
- **接手第一件事（3 条命令，别跳）**：

```bash
export PATH=/c/Users/33393/.workbuddy/binaries/PortableGit/versions/1.2.0/usr/bin:$PATH
cd /c/Users/33393/Desktop/ai-legal-helper
git log --oneline -6                        # 确认 master 实际 HEAD（并行会话会提交）
git rev-parse --verify refs/heads/codex/local-candidate-closeout   # ⚠️ 见 §9.1：这个引用会被删除
git worktree list                            # 确认候选 worktree 仍显示 fbc29e8 [codex/local-candidate-closeout]
```

- **结论：阶段仍未完成 / 候选受阻。** 卡在两个 Owner 动作上（见 §6），不是卡在技术上。

---

## 1. 一句话现状

隔离环境里的两项依赖升级（pypdf、FastAPI）**代码与测试都做完并已提交**，九步门禁的**结论**是可复现的（[1]–[5] 真绿、[6]–[8] 的路径假红已用候选解释器复跑为 rc0/rc0/9 passed、47 条 / 8 包是重试后的漏洞读数）；
**但**这句话的证据出处此前挂错了一份日志 —— `postcommit-gates.log` 里 [6]–[8] 仍是红的、第 9 步那次 rc=1 也**不是**"漏洞非零"而是扫描器 `ReadTimeout`，
逐条更正见 §4.1（这里不写"九步在同一份日志里全绿"）；
隔离语料在副本上跑完导入/幂等/恢复；**但**剩余依赖风险尚未获得 Owner 接受，**真实 rerank 因凭据待轮换而未复验** ⇒ 按规划书 F 节判据只能给「阶段仍未完成 / 候选受阻」。

**2026-09-29 接续会话后追加（Owner 已裁三题，见 §8 台账）**：凭据**尚未轮换**⇒ 本轮不调用真实 rerank；
候选**不合并**master，等风险裁定；**B 档运行时探针已做完** ⇒ §6② 里"grep 判不了内部路径"那一档的证据等级
已从"静态 0 命中"升到"运行时 0 调用"，**D2 现在缺的只是 Owner 签字，不缺材料**。
三态结论仍是**阶段仍未完成 / 候选受阻**，但受阻的原因已从"材料不全"收窄为"两项裁定未落笔"。

---

## 2. 代码落在哪（最容易搞混的地方）

**代码只在这个分支，没有合进 master。** 两处提交：

| 位置 | HEAD | 内容 |
|---|---|---|
| `master`（发布线） | `87e5227` | `aec8d5c` 之后**只有文档**：`725a207` 两份报告、`8ae321b` 计划书+证据目录、`0429c42` 计划书对账、`e4ea073` 恢复工具+bundle 登记、`87e5227` 本交接书 |
| `codex/local-candidate-closeout`（候选） | `fbc29e8` | 起点 `aec8d5c`，**4 笔 / 7 文件**（见下表），**未合入 master、未推送、未建远端分支** |

候选分支改动面（`git diff --name-status aec8d5c..fbc29e8`）：

| 提交 | 文件 | 内容 |
|---|---|---|
| `ca0eb5e` | `backend/requirements.txt`、`backend/knowledge_service.py`、`backend/tests/test_pdf_upload.py`(新) | pypdf 固定 `6.16.1`；把 `pypdf.errors.PyPdfError` 转成受控 `ValueError`（此前坏 PDF 会漏成 500）；新增 PDF 上传三路用例 |
| `ecdc6b3` | `backend/requirements.txt`、`backend/main.py`、`backend/tests/test_upload_rate_limit.py`(新) | FastAPI 固定 `0.141.1`（Starlette 由解析器选定，未硬钉）；`main.py` 补 mypy 必需类型标注（**有复现依据**，见 §4 注）；新增真实限流 429 用例 |
| `39f4266` | `backend/tests/test_request_bootstrap.py` | 留痕断言改用独立 `logging.Handler` 捕获（语义不变，只换捕获方式） |
| `fbc29e8` | `docs/assistant-briefs/t7-dependency-upgrade-options-20260927.md` | T7 分案的执行口径修订 |

---

## 3. 环境怎么重建（可复现）

- 独立 Python 3.11 环境（**不是**共享 `backend/venv`，共享那份全程未动）：
  `C:\Users\33393\AppData\Local\Temp\legal-closeout-20260928\venv\Scripts\python.exe`（Python 3.11.0）
- 离线 wheelhouse：`C:\Users\33393\AppData\Local\Temp\legal-closeout-20260928\wheelhouse`（重建前先核对这个目录）
- 关键版本：pypdf **6.16.1** · fastapi **0.141.1** · starlette **1.7.0** · pydantic **2.13.5** · SQLAlchemy **2.1.1** ·
  mypy **2.3.1** · pytest **8.4.2** · ruff **0.16.9** · chromadb 0.4.24 · langchain 0.1.20（完整表见证据目录 `candidate-versions-final.log`）

> 若该目录已被清理：先在仓库外建 Python 3.11 venv → 装 CPU torch（`pip install torch --index-url https://download.pytorch.org/whl/cpu`）→
> 再装 `backend/requirements-dev.txt`。**不要**用共享 venv 的 `pip freeze` 当安装依据（它已有声明冲突）。

---

## 4. 怎么验证（照抄；逐条预期读数）

在**候选树**的 `backend/` 里跑（下面命令实测过，读数就是 2026-09-28 那次的结果）：

```bash
export PATH=/c/Users/33393/.workbuddy/binaries/PortableGit/versions/1.2.0/usr/bin:$PATH
PY="C:/Users/33393/AppData/Local/Temp/legal-closeout-20260928/venv/Scripts/python.exe"
CAND="/c/Users/33393/.codex/worktrees/local-candidate-closeout/ai-legal-helper"
cd "$CAND/backend"
export JWT_SECRET='test-jwt-secret-for-ci-only' LLM_API_KEY='test-key-not-for-real-calls' LLM_BASE_URL='https://test.invalid/v1'
export EMBEDDING_PROVIDER=local RERANK_ENABLED=false EMBEDDING_QUOTA_TOTAL=0 RERANK_QUOTA_TOTAL=0
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 LANGCHAIN_TRACING_V2=false LANGSMITH_TRACING=false
export COVERAGE_FILE='C:/Users/33393/AppData/Local/Temp/legal-closeout-20260928/cov'

"$PY" -m pip check                                   # No broken requirements found        rc=0
"$PY" -m ruff check .                                # All checks passed                   rc=0
"$PY" -m ruff format --check .                       # 全部已格式化                        rc=0
"$PY" -m mypy .                                      # Success: no issues found in 74 files rc=0
"$PY" -m pytest -q -p no:cacheprovider -m 'not slow' --cov=. --cov-fail-under=70 \
  --basetemp='C:/Users/33393/AppData/Local/Temp/legal-closeout-20260928/pt-1'
# 1650 passed, 10 skipped, 18 deselected, coverage 85.25%（约 211s）  rc=0
```

质量守卫（注意路径要用 `C:/...`）：

```bash
AQ="C:/Users/33393/Desktop/ai-legal-helper/dispatch-output/agent-quality-20260911"
"$PY" -m ruff check "$AQ"                             # All checks passed        rc=0
"$PY" -m ruff format --check "$AQ"                    # 4 files already formatted rc=0
"$PY" -m pytest -q -p no:cacheprovider "$AQ/test_budget_guard.py"   # 9 passed      rc=0
```

### 4.1 门禁日志的出处更正（2026-09-29 本会话现量）

**此前四份文档都写"`postcommit-gates.log` 里有 `[6R]/[7R]/[8R]` 三段路径修正后的重跑" —— 那句话不成立。**
现量（`grep -E '\[6R\]|\[7R\]|\[8R\]' postcommit-gates.log` → **rc=1，0 命中**；全仓只有文档里提到过这三个标记）：

| 步 | `postcommit-gates.log` 里实际是什么 | rc |
|---|---|---|
| [1]–[5] `pip check` / `ruff check` / `format` / `mypy` / 全量 `pytest` | 真绿，读数照旧 | 0 |
| [6] `ruff check agent-quality` | `E902 系统找不到指定的文件`，路径被解析成 `C:\c\Users\...` | **1** |
| [7] `ruff format --check agent-quality` | 同一条路径假红 | **2** |
| [8] `test_budget_guard.py` | `file or directory not found`，no tests ran | **4** |
| [9] `pip_audit -r requirements.txt` | ⚠️ `requests.exceptions.ReadTimeout … pypi.org … (read timeout=15)` —— **扫描器自身失败，不是"漏洞非零"** | **1** |

所以：**"九步全绿在同一份日志里"这句话此前是错的**，且第 9 步那行的红**从来不是**漏洞读数 —— 47 条 / 8 包出自
`postcommit-pip-audit-retry.log`（`--timeout 60`）与入库件 `candidate-requirements-pip-audit.json`，两者要分开引。

**[6]–[8] 的当前现量**（2026-09-29 由本会话用**候选解释器**重跑，命令即上面那三条）：
`ruff check` → All checks passed **rc=0**；`ruff format --check` → 4 files already formatted **rc=0**；
`test_budget_guard.py` → **9 passed** rc=0。解释器 `C:\Users\33393\AppData\Local\Temp\legal-closeout-20260928\venv\Scripts\python.exe`
（Python 3.11.0，ruff 0.16.9）。

两点限定，别把这条读成"补上了旧证据"：
1. 这补的是**今天**的读数，**不能追溯证明 09-28 那份日志里有过三段重跑**。另有一份 `agent-quality-test.log`（内容就是 `9 passed`）
   mtime 为 **09-28 21:38:35，早于** `postcommit-gates.log` 的 09-29 00:19:14，且只覆盖 [8] 一步 ⇒ 它不是那次修正路径后的三步重跑件。
2. 重跑在主工作区 `14a04ca` 做的，但 `dispatch-output/agent-quality-20260911` 的**已跟踪内容在两棵树逐字节相同**
   （目录 tree 哈希两侧同为 `7fbfe95971302b1e2268bb8708ba05feb3f6349a`；差异只是 `.mypy_cache`/`.ruff_cache`/`__pycache__`/运行产物等未跟踪件），
   对候选树 `fbc29e8` 的同一份已跟踪副本复跑，结果同样 rc=0/rc=0/9 passed。

**原日志一字未改**（更正的是引用它的那四句话，不是日志本身）。

依赖审计（**这条的 rc=1 是"有漏洞"不是"命令失败"**）：

```bash
"$PY" -m pip_audit -r requirements.txt --format json --timeout 60
# Found 47 known vulnerabilities in 8 packages   rc=1
# fastapi / pypdf / starlette 等升级目标均为 0 条；剩余集中在 langchain 系(37)、transformers(8)、chromadb(2)
```

**两条必须知道的"假红"**（否则接手后会重复踩）：

1. **路径形态**：把 `/c/Users/...` 传给 Python / ruff / pytest 会被解析成 `C:\c\Users\...` ⇒
   `ruff E902 系统找不到指定的文件`、`pytest file or directory not found`。**一律用 `C:/...` 原生形态**（`--basetemp`/`--cov-fail-under`/重定向同理）。
2. **审计的网络失败 ≠ 零漏洞**：默认 15s 超时可能在 `pypi.org` 上 `ReadTimeout`（rc=1 但没有任何漏洞读数）。
   先分析再重试，**最多重试一次**（加大 `--timeout 60`）。两件事在报告里是分开记的。

保护对象复验（真实库零写入的自证）：

```bash
"C:/Users/33393/AppData/Local/Temp/legal-closeout-20260928/venv/Scripts/python.exe" -u \
  "C:/Users/33393/Desktop/ai-legal-helper/dispatch-output/local-candidate-closeout-20260928/verify-protected.py"
# baseline entries=41 / unchanged(size+sha256): 41 / missing: 0 / changed: 0   rc=0
```
（脚本按 `dispatch-output/local-candidate-closeout-20260928/protected-before.json` 重算 41 个对象的 size+SHA-256，
结果写入同目录 `protected-postcommit-check.log`。保护对象 = 两份 `app.db`、两处配额库、`backend/chroma_db` 全量文件等。）

前端（**本轮未改前端**，沿用既有读数）：候选树 `frontend/` 里 `npm ci` rc=0；`npm run check` 7 files / 54 tests passed；`npm run build` rc=0。

---

## 5. 已完成的验收与证据文件

| 项 | 读数 | 证据 |
|---|---|---|
| 提交后九步门禁（候选树 `fbc29e8`） | [1]–[5] rc=0；[6]–[8] 在该日志内是路径形态假红（rc 1/2/4）、[9] 是扫描器 ReadTimeout —— **两者都不是"绿"**，逐条见 §4.1 | `postcommit-gates.log`；⚠️ 该日志内**没有** `[6R]/[7R]/[8R]` 三段重跑（此前引用有误，已在 §4.1 更正）。[6]–[8] 用候选解释器于 2026-09-29 复跑为 rc0/rc0/9 passed；47/8 另出自 `postcommit-pip-audit-retry.log` |
| 依赖审计（重试读数） | 47 条 / 8 包 / 扫 132 包 | `postcommit-pip-audit-retry.log`、`candidate-requirements-pip-audit.json` |
| 依赖审计（实装环境口径） | 57 条 / 10 包 / 扫 167 包（多出 setuptools/pytest，**与 47 不可相加**） | `candidate-installed-pip-audit.json` |
| 保护对象 | 41/41 未变 | `protected-before.json`、`protected-postcommit-check.log` |
| 隔离语料（副本上） | validate-only/dry-run rc=0；首次导入替换 2 无日期旧块、新增 3、跳过 0；重跑幂等（10267 条）；恢复快照匹配导入前 10266 条 | `corpus-existing-runtime.log`、`corpus-restored-existing-runtime.log`、`verify_corpus.py` |
| PDF 修复前后对照 | 修前 2 failed / 5 passed（坏 PDF 真的返回 500）→ 修后 20 passed | `pdf-red-existing-runtime.log` / `pdf-green-existing-runtime.log` |
| 提交前定向复跑 | 110 passed / 1 skipped | `precommit-targeted.log` |
| 剩余风险逐项复核 | 26 组通报 + 每项触发条件/可达性/待裁状态 | `residual-risk-review.md` |

> 注：`.gitignore:45` 全仓忽略 `*.log`，所以上面这些日志**不会进 git**，只留在磁盘上。要转交请连目录一起拷，
> 或按 §4 重跑复现（所有读数都给了命令）。

---

## 6. 阻塞与待 Owner 决策（接手后要推动的就是这两件）

**① 凭据轮换（Owner 动作，未完成）**
此前检查本地配置时，有命令意外把 `.env` 里的 rerank 凭据值打印到了工具输出。凭据值**未写入任何仓库文件**，但应按已暴露处理：
请撤销/轮换活动的 SiliconFlow key，并确认注释里保留的旧备用 key 已失效或一并撤销（**新凭据不要发到聊天里**）。
完成后告知 ⇒ 才按既有授权**只跑一次**隔离真实 rerank 验收。
⇒ **因此本阶段没有 24/24 的新读数；报告里的 23/24 是历史值，不要当成本轮现量。**

**② 依赖风险裁定（Owner 决策，未完成）**
47 条（解析集）/ 57 条（实装集）**未获接受**。助手不代签、未加 `--ignore-vuln`、未放宽 CI。
可用的裁定材料：`residual-risk-review.md`（26 组逐项）+ 本次新增的**代码级入口证据**：

- 应用代码里这些能力符号 **0 命中**：`get_num_tokens*`、`load_prompt*`、`TracingMiddleware`、`SitemapLoader`、`FAISS`、
  `GraphCypher*`、`EverNoteLoader`、`pull_prompt`、`save_pretrained`、`LightGlue`、`X-CLIP`、`LANGCHAIN_TRACING`、`LANGSMITH`
  （唯二两处命中是 `backend/scripts/gen_r8_disposition.py` 里的**描述文字**）。
- `backend/.env` 里 `LANGCHAIN_TRACING_V2` / `LANGSMITH_TRACING` / 两个 `*_API_KEY` / `LANGCHAIN_ENDPOINT` **全部 absent** ⇒ 生产无自动追踪。
- 图片输入是**严格 data URL**（`multimodal.py` 正则校验 `^data:image/...;base64,...$`），且 `main.py` / `knowledge_service.py` / `multimodal.py` 内**无** `requests.get/post`、无 `httpx.`、无 `urlopen`。

**我提的三档处置口径（待 Owner 定，可推翻）**：
- **A 档 · 入口级证据充分、建议带范围与复审日期接受**：LangChain 各 loader/retriever/prompt-loader、LangSmith 一族、Chroma HTTP 面、Transformers 的 `save_pretrained`/LightGlue/X-CLIP。
- **B 档 · grep 判不了内部路径，建议先做低成本运行时探针**：Core 反序列化族、Transformers 模型 config RCE、疑似包映射错的 `CVE-2024-7774`
  → 做法：把对应入口桩住跑一遍现有 1650 条测试 + 两条应用路径，看调用次数是否为 0，把证据从"静态 0 命中"升到"运行时 0 调用"。
- **C 档 · 大版本迁移，建议单独立票、不进本阶段**：LangChain 0.1→\*、Transformers、Chroma（动它们等于 RAG/Agent 重构，超出本阶段边界）。

> ⚠️ 边界：A 档是**入口级证据**，不是"不可达证明"；`residual-risk-review.md` 里的同一条限定继续有效。

**B 档已于 2026-09-29 做完**（Owner 裁「先做探针我再裁」）。仪器、驱动、读数与逐条判定表都在
`dispatch-output/local-candidate-closeout-20260928/`（判定表由读数现生：`python b_probe_matrix.py` → `b-probe-verdict-matrix.md`）。
给裁定用的四条结论，都带"这一条是从哪两个场看出来的"：

| 组 | 运行时读数（测试场 1660 条 + 两条应用路径） | 这条能撑到什么程度 |
|---|---|---|
| Core 反序列化 / 模板构造 | 7 只桩**两场均 0 调用**，且相关模块都在场（不是缺席导致的空读数）；另有一条静态事实：候选工作树 `backend/` 里 `PromptTemplate` **0 个文件命中**（tests 与 scripts 全扫），问答链是 `rag_chain.py:137` 的 `llm \| StrOutputParser()` | 支撑"应用不把外部内容当序列化对象或模板配置重建"，仍不是不可达证明 |
| 图片 token 计数（SSRF 族） | **只有测试场是阴性证据**：3 只桩 0 调用，且 `langchain_openai` 在该场在场。应用路径场是**未测**——该场驱动从不 import `main`/`llm_registry`（`llm_registry.py:20` 是模块级 `from langchain_openai import ChatOpenAI`，真实 `/api/chat` 必加载），所以"该场 `chat_models.base` NEVER-IMPORTED"只说明驱动没建聊天客户端。外联另有直接读数（见下） | 支撑"本场没有走到计数抓 URL 的路径"；`CVE-2024-7774` 的**包映射疑点这把尺子管不着**，仍是待办 |
| Transformers 模型 config | 模型/config/tokenizer 加载**各 1 次**，调用方唯一归到 `backend/rag_chain.py:39`，模型名只有源码常量 `BAAI/bge-base-zh-v1.5`，**`trust_remote_code` 取值 `False`**（键在场不算证据，值才算）。⚠️ 这条只覆盖**把它当实参传的** `G3a PreTrainedModel` 与 `G3b AutoConfig`；`G3d` tokenizer（实参键 `_commit_hash,_from_auto,cache_dir,revision,token`）与 `G3e SentenceTransformer.__init__`（实参键 `cache_folder,device`）的实参里**没有这个键** —— 不是"实参为空"，是"这个键根本没传"，所以不能替它们背书 | 支撑"加载面只有一个钉死常量、未主动放行远程代码"；⚠️ **不支撑**"`CVE-2026-4372` 已缓解"：候选实装 transformers **4.57.6** 落在该通报 `< 5.3.0` 区间内，公告明写该缺陷绕过 `trust_remote_code`。模型文件本身的完整性也仍未验（属 A 档之外的另一件事） |
| 未被引用的 loader / 追踪 | `langsmith.middleware`、`SitemapLoader`、`EverNoteLoader`、`FAISS`、`GraphCypherQAChain` 两场均**从未被导入**；`langsmith.client.Client` 在场但 0 次实例化、`pull_prompt` 0 次。结构性的那条：`langchain_community` 与 `langchain.chains` 两场均从未被导入 | 支撑"这些能力不在运行路径上"；将来若新增入口，本读数即失效，须重跑 |

**外联是直接读数，不是推断，而且是"全部键"读出来的不是打印窗口读出来的**：测试场 348 次事件 / 206 个键逐条机器归类
（`b_probe_net_audit.py`，自带 8 条合成反例证明归类器能红）——连接类目的为
**312 次 127.0.0.1 + 1 次对 `test.invalid:443` 的 DNS 解析尝试 + 35 次"键里没有主机字段"**（`ctypes.dlopen` 与
`subprocess.Popen`，单列一档、不折进"环回"）。那 1 次非环回**已归因到用例**：
`tests/test_phase3.py::test_healthz_components` → `backend/main.py:337-342` 的 `socket.create_connection`，
是 `/healthz` 对 `LLM_BASE_URL` 主机的**设计内**连通探测（假端点解析失败，**无对应 `socket.connect`，连接未建立**），
不是任何 CVE 目标路径。应用路径场连接类事件 **0** 次，只有本地 DLL 加载与 torch 的 `ver`/`lscpu` CPU 探测。
> ⇒ 给裁定的一句话：本探针能撑"这 22 个运行期入口不在路径上"，**撑不起"这个应用不会 outbound"**——
> 它自己有一个按配置外发的健康检查点。
>
> ⚠️ **而且这次普查是在外发面被关掉的前提下跑的**：驱动设 `RERANK_ENABLED=false`、`EMBEDDING_PROVIDER=local`、
> 配额总量 0、`LLM_BASE_URL` 指向保留不可解析域（`b_probe_run_suite.py:32-36`、`b_probe_app_paths.py:40-44`），
> 而**本机 `backend/.env` 实为 `RERANK_ENABLED=true`**。于是这几条**带凭据的真实外呼路一次都没进过样本**：
> rerank（`retrieval.py:85-87` 的开关短路掉 `retrieval.py:168`/`:184` 的 `httpx.post(.../rerank, Authorization: Bearer …)`）、
> 云端嵌入（`EMBEDDING_PROVIDER=aliyun`）、LLM 调用本身（`llm_registry` → `ChatOpenAI`）、
> MCP 侧 `mcp_server.py:45,51` 的 `httpx.Client`、以及 `/api/chat/transcribe`（`main.py:1464`）这类按请求走云的端点。
> 另注：`knowledge_base.py:5` 会**无条件**把 `HF_HUB_OFFLINE` 改回 `0`，本轮两场都没导入它（读数里 `hf-mirror` 0 痕迹），
> 所以"离线"这两场成立，但它是**结果不是保证**。⇒ 接受 D2 时"外联已普查"这句话只对本案两个窗口成立，别当成全量外发审计。

**这批探针没有改变的东西**：`pip-audit` 仍是解析集 47 条 / 8 包、实装集 57 条 / 10 包的**红**读数——
探针**不减漏洞条数**，只把可达性证据从静态升到运行时。**接受范围与复审日期仍需 Owner 落笔**，助手不代签。

**D2 可签文本（草案）** —— Owner 直接改字或划掉即可；本草案**不是**签字，落笔前 `residual-risk-review.md` 的共同状态仍是
"未接受、未忽略、未解除"。写它的唯一目的：把"接受面 == 证据面"钉成一段可划改的文字，别让签字时顺手签进没测过的东西。

> **签字对象只有一件事**：在**本地候选形态**下，这批**应用运行时**依赖通报（`requirements.txt` 解析集那一根轴，26 条）**本阶段不做版本升级、不做代码改动**。
> 它**不等于**发布/部署/将来服务化也可以，**不等于**"不可达证明"，**也不清零**下面第六条列的那几条在册阻塞；
> ⚠️ **并且它的射程不含「二·补」那两根轴**（开发/构建工具通报、以及根本没被审计的 `torch`）—— 那两件不因本笔签字而有了结论。

**一、接受范围**（档位沿用上面 §6② 的三档口径，逐档绑各自的证据等级；**签的是"读数说的那件事"，不是档位标签**）

- **A 档**（入口级静态 0 命中，且运行时读数显示相关模块从未被导入 / 在场但 0 实例化）：接受"本阶段不动代码"。
- **B 档**（有运行期入口可桩、两场上留下三种读数之一的）。⚠️ **别把这一档统一读成"0 调用"**——矩阵里三种形态都有：
  ① **ZERO-CALL**（Core 反序列化族、模板构造、`pull_prompt` 等）；
  ② **1-CALLS 但可唯一归因**（模型/config/tokenizer 加载各 1 次：调用方唯一到 `rag_chain.py:39`、
  模型名只有源码常量 `BAAI/bge-base-zh-v1.5`）——这**不是**"没跑到"，
  而是"跑到了、但跑的是钉死的受信常量"，接受的依据因此与 ① 不同。
  ⚠️ **`trust_remote_code=False` 只覆盖 `G3a`（`PreTrainedModel.from_pretrained`）与 `G3b`（`AutoConfig.from_pretrained`）**
  ——这两只桩的实参里确实带了该键且值为 `False`；`G3d`（tokenizer `from_pretrained`，实参键
  `_commit_hash,_from_auto,cache_dir,revision,token`）与 `G3e`（`SentenceTransformer.__init__`，实参键 `cache_folder,device`）
  **实参里没有这个键**，不能由它背书（读数见 `b-probe-verdict-matrix.md` 的 G3 行）。
  ⚠️ **并且这条对 `CVE-2026-4372` 本身不构成安全证明**：候选实装的 transformers 是 **4.57.6**（由 `sentence-transformers>=2.5,<3.0` 传递解析得来，
  `requirements.txt` 未直接钉它），落在该通报的受影响区间 `< 5.3.0` 内，而公告原文写明该缺陷
  **"bypasses the `trust_remote_code` security mechanism"** —— ⇒ 签"`trust_remote_code=False`"签的是**我们没有主动放行远程代码**这件事，
  **不等于**这条通报在该版本上已被缓解；模型**文件**的来源与完整性也仍未验（第二栏 ⑤）。
  ③ **某场未测**（`G2a` 在应用路径场是 NEVER-IMPORTED，因为该场驱动从不构造聊天客户端，**不是**"证明它不导入"）。
  证据 = `b-probe-verdict-matrix.md` 的两场读数（1660 条非 slow 测试 + 两条直调应用路径），
  由 `python b_probe_matrix.py` 现生，**逐条对应关系不手抄**。
- **C 档**（大版本迁移）：**不在本阶段任何接受范围内**，维持单独立票。

> ⚠️ **这一栏签完，第二栏那 5 件一件都没消**：其中 ① 是 **9 条探针答不上的公告，目前没有任何处置结论**
> （既未判定适用、也未判定不适用），本草案的六栏**不能**被读成对它们表态。
> 只要那 9 条与 ② `CVE-2024-7774` 映射疑点仍无处置，共同状态就得保持"**未接受、未忽略、未解除**"，
> 阶段判定也仍是「候选受阻」，不能因为一/三/四/五栏落了笔就改写成"有条件就绪"。

**二、不写进"已接受"的 5 件**（保持在册待办；签了 D2 也不代表它们有结论）

  ① 探针答不上的 9 条公告（与 `b_probe_matrix.py` 的 uncovered 同源，改一处需两处同步）：CVE-2024-3095、CVE-2024-7774、CVE-2025-6985、CVE-2026-1839、CVE-2026-41481、CVE-2026-45830、CVE-2026-45833、CVE-2026-55443、CVE-2026-9856；
  ② **D6** `CVE-2024-7774` 的包映射疑点 —— **2026-09-29 已判定**：是上游 PyPA/OSV 把 **langchainjs（npm）** 的缺陷挂到了 PyPI `langchain` 名下，
  对本项目的 Python 依赖**不适用**（证据与边界见 `residual-risk-review.md` 的「D6 结论」节）。
  ⇒ 它从"未决疑点"变成"有结论的一条处置"，但**原始告警仍在、未加 `--ignore-vuln`**，所以这一件**仍列在本栏**：签字时它算"证实不适用"，不算"没查"。
  ③ **带凭据的真实外呼路一次都没进过样本**：rerank / 云端嵌入 / LLM 调用本身 / MCP 侧 / `/api/chat/transcribe`
  （驱动把 `RERANK_ENABLED` 关成 false，而本机 `.env` 实为 true）；
  ④ `backend/scripts/*` 与**子进程 / 第二解释器**不在这两场窗口内（仪器只桩本进程）；
  ⑤ 模型**文件**完整性未验（探针只证"没放行远程代码"，不证那份权重没被动过）。

**二·补、另一根轴：本笔签字**覆盖不到**的环境范围（不是"探针射程"那条轴，是"包范围"那条轴）**

  上面的五件说的是"应用运行时那 26 条里探针答不上的部分"。复扫后另有一批**根本不在那 26 行里**的东西，
  逐条与判定见 `scope-recount-20260929.md`（重跑：`python b_scope_recount.py --write`，**本页不抄它的条数**）：

  ⑥ **开发/构建工具通报**（`pytest`、`setuptools` 两包，只在实装集命中、`requirements.txt` 解析集里没有）：
  这些是本机与 CI 的**构建期面**，与应用运行时暴露面不同轴。本笔 D2 签的是"应用运行时依赖本阶段不升级不改码"，
  **签了也不覆盖这一轴** —— 它既未判适用、也未判不适用，**保持待处置**。
  ⑦ **一个包根本没被审计**：实装 `torch 2.6.0+cpu` 在扫描读数里带 `skip_reason`（PyPI 无该分发），
  ⇒ 扫描器**没给出任何漏洞读数**。这是**盲区，不是零风险**；且**不得**拿解析集里解析出的那个 torch 版本替代它说话。
  ⑧ **两条"待核"不是"待处置"的同义词**：`CVE-2026-1839` 的跨包前提（公告要求的 torch 版本）与
  `CVE-2026-45833` 对嵌入式 chromadb 0.4.24 的适用性，**一手证据未取到**，签字时这两条只能记"未决"。
  ⇒ 另有一条已定：`CVE-2024-7774`（上面②）本轮已判定为上游映射缺陷、对本项目 Python 依赖不适用。

**三、随接受一起生效的限制**（**任一被突破 ⇒ 本接受自动失效，回到"未接受"**）

仅限本地单机使用；不对外暴露服务；不新增外部 sitemap / 网页抓取入口；不加载外部序列化对象或模板配置；
不启用公共 prompt Hub；不暴露 Chroma HTTP、不做服务化与多租户；不放开 `trust_remote_code`；不把用户内容当模板定义。

> ⚠️ 这条限制清单是**使用面约束**，不是**缓解证明**。特别是"不放开 `trust_remote_code`"这一条**挡不住 `CVE-2026-4372`**：
> 候选实装 transformers **4.57.6** 在该通报的 `< 5.3.0` 受影响区间内，公告原文写明缺陷**绕过 `trust_remote_code` 机制**
> （GHSA-29pf-2h5f-8g72，High / CVSS 7.8，修复版本 5.3.0）。 ⇒ 接受这条限制，不等于接受了一条已被缓解的通报。

**四、必须一起算进暴露面的两条应用事实**（不是缺陷，但签字时不能不知道）

- `/healthz` 会取 `settings.llm_base_url` 的主机**主动做 TCP 连通探测**（`backend/main.py:337-342`，`timeout=3`，软检查）。
- `knowledge_base.py:5` **无条件**把 `HF_HUB_OFFLINE` 改回 `0`：本轮两场都没导入它，所以"离线"成立，
  但它是**读数结果，不是环境保证**——将来任何进程 import 它，这条前提就地失效。

**五、复审日期：沿用登记表已有的 2026-10-05**，并保留"提前发布 / 启用新入口 / 收到新公告 ⇒ 立即复审"。
（不建议往后挪：那个日期是在册约定，不在助手可代改的权限里。）

**六、签了也不解除的在册阻塞（逐条都是现量，别当成"签了就清"）**

1. `pip-audit` 仍 rc=1：解析集 47 条 / 8 包、实装集 57 条 / 10 包。探针**不减漏洞条数**。
2. **未推送 ⇒ 远端 CI 没有真实运行证据**（本机纯发布物树的重放 ≠ CI 绿）。
3. 候选语料**未真实入库**（授权仍只到 S0-a/b/c + T1 + T2）。
4. **两条凭据各自的狀態不同，别合并成一条**：
   4a. **§6① 那把被意外打印过的 SiliconFlow rerank key**——按"已暴露"处理，**待撤销/轮换**（Owner 09-29 答：还没轮换）。
   ⇒ 这一条同时挡着"跑一次真实 rerank"（D4），是这批里唯一**已经暴露过**的凭据，不能漏签。
   4b. `ADMIN_PASSWORD`——轮换授权已给（D25＝1），**动作在 Owner 手上，仍未执行**；服务器侧那份 `.env` 我一概不碰。
5. ⚠️ **一处在册矛盾必须连带裁定**：`dispatch-output/t12-frontend-sweep-20260920/apply_case_domain_gate.py:104`
   的行内注释自称"**值已轮换，旧值失效**"，而台账 D25 与 Owner 09-29 的话都是"**还没轮换**"。
   注释在替 Owner 断言一件没发生的事 ⇒ 将来有人据它认为旧口令无害。**这条注释需要 Owner 定措辞**（助手不代改凭据状态结论）。
   注：`Q5`（把 `:104` 从"字面值"改成"形状匹配"）**已于 09-26 执行完毕**（现量该行是 `r"'[A-Za-z0-9]{13}'"`），
   它**不再是**推送前置——别再照旧口径把它列成待走。

6. ⚠️ **2026-09-29 复扫新置的两条在册待办**（不属于"签字即消"的那批）：
   6a. **开发/构建工具那一轴**（`pytest` / `setuptools` 的通报，只在实装集命中）—— 本笔签字**不覆盖**，仍是待处置。
   6b. **实装 `torch 2.6.0+cpu` 未被审计**（扫描读数带 `skip_reason`）—— 盲区不是零风险，需按 PyTorch 官方通报单独核查。
   ⇒ 逐条读数与三轴归属见 `dispatch-output/local-candidate-closeout-20260928/scope-recount-20260929.md`
   （重跑：`python b_scope_recount.py --write`；该件自带闭合检查，对不上就 rc=1）。

⇒ **D3 口径不变**：Owner 裁"等 D2 有结论再合"，这段落笔后即可谈合并窗口。
但推送的硬顺序是：**Q4（两条凭据轮换）→ 复扫 → Q6（一次性快照分支，永不 force，真推由 Owner 按回车）**。

**签字位**：一 / 二 / 三 / 四 / 五 / 六 各栏 ＿＿＿（照签 · 改第＿条 · 不接受）　Owner 日期 ＿＿＿


---

## 7. 本轮明确没做什么（边界，一条不省）

未 push、未建远端分支/PR、未部署、未启动生产容器、**未写真实库**（语料全在副本上）、**未调用生成模型**、
**未运行** `backend/scripts/smoke_citation_full.py` 与 `smoke_citation_fast.py`、未改共享 `backend/venv`、
未合并两个工作区的分支、未 `git add -A`（主工作区未跟踪 34107 个产物，只暂存了本批证据目录与本计划）、
未动其余 8 个 worktree。

---

## 8. 还没对齐的决策分支（grilling 状态）

| 分支 | 内容 | 状态 |
|---|---|---|
| **D1** 环境可靠性 | 仓库 git 缺陷（§9.1）做到哪一层 | ✅ **已定：分层** —— 回填 + 仓库外 bundle 备份已落地，**根因另立一次定向诊断**（尚未排期） |
| **D2** 依赖风险口径 | 接受 / 分档 / 立即修复；接受的**范围与复审日期**怎么定 | ⏳ **探针该给的材料已给全、签字未落**（"全"只指 B 档射程内，别读成 26 条都查过了）—— Owner 2026-09-29 裁「先做 B 档探针，我再裁」；探针已交付（§6② 那张四行表 + `b-probe-verdict-matrix.md`）。**本轮补的三样**：① 公告视角把 26 条拆成「有桩可答 17 / 探针答不上 9」（闭合 `17+9==26`），答不上那 9 条**不是"已排除"**；② 一条必须算进暴露面的应用事实——`/healthz` 会按 `LLM_BASE_URL` 主动做 TCP 探测（`backend/main.py:337-342`）；③ 主张复算 + 变异对照（复算器自身可红性已证；**条数与杀数一律只认命令合计行，本档不复抄**）。余下是接受范围与复审日期。**B 档探针射程外另有 5 件，别读成"已排除"**：① 9 条公告无桩可答（上列）；② **D6** `CVE-2024-7774` 包映射疑点；③ **带凭据的外发面未普查**（rerank / 云端嵌入 / LLM 调用本身 / MCP / `/api/chat/transcribe`，而本机 `.env` 的 rerank 是开着的 —— 见 §6② 的 ⚠️ 段）；④ `backend/scripts/*` 与子进程路径不在这两场窗口内；⑤ 模型**文件**完整性未验（探针只证"没放行远程代码"）。**同日追加**：上面这些已压成 §6② 末尾的「D2 可签文本（草案）」六栏带签字位，Owner 改字即可；复算器里有专门的主张钉"签字页那份无桩清单与复审日期必须与登记表同源"，并有**文档侧变异**证明抄错会被抓（防手抄漂移） |
| **D3** 候选与 master | 隔离期多长、合入门槛是什么 | ✅ **Owner 2026-09-29 裁：等 D2 有结论再合** —— 不合入、不推送、不建远端分支；引用与 bundle 双保险照旧 |
| **D4** 凭据与 rerank | 轮换范围（是否含旧备用 key）、复验范围与次数 | ⏳ **Owner 2026-09-29 答：还没轮换，本轮先不跑** —— 因此本阶段**没有 24/24 现量**；轮换并告知后按既有授权只跑一次 |
| **D5** 下一阶段目标 | 回功能线 vs 先做发布准备 | ⏳ 未定（当前立场：先做发布准备，因为真正卡发布的是服务器选型与真实库写入策略，不是代码） |
| **D6** `CVE-2024-7774` 包映射疑点 | 公告与包名映射核对，判是否误报 | ✅ **2026-09-29 已判定：上游 OSV 映射缺陷，对本项目 Python 依赖不适用** —— `GHSA-hc5w-c9f8-9cc4` 生态是 **npm**；`PYSEC-2024-111` 虽登记在 PyPI `langchain` 名下，正文与两条 reference 全指 **langchainjs**（commit `a0fad77d`）；公告点名的汇 `getFullPath` 及 `setFileContent`/`getParsedFile` 在实装 `langchain==0.1.20` 包体 1326 个 `.py` 中 **0 命中**。**边界**：`mdelete` 同名存在于 Python base-store ⇒ 依据是"汇不存在＋生态归属 JS"，不是"点名符号全无"；应用侧对 `langchain.storage` 零引用（含动态引用）是静态结论、非不可达证明。**原始告警保留、未加 `--ignore-vuln`**，下一轮仍会报。证据与命令见 `residual-risk-review.md`「D6 结论」节 |

---

## 9. 本机环境坑（按坑抄，别重踩）

### 9.1 🚨 仓库 git 缺陷：嵌套分支引用的写入会被外部进程删除

- **现象**：`git commit` 到 `codex/...` 分支后，`git log` 报 `your current branch ... does not have any commits yet`，
  `git worktree list` 显示 `0000000` —— **提交对象与该分支的 reflog 都完好**，只是分支指针的文件不见了。
- **实测结论（10ms 级轮询拍下来的）**：git **写成功了** —— 观测到 `mkdir refs/heads/<dir>` → 建 `.lock` → 写 reflog →
  **`.lock` 改名成 ref（文件确实出现）** → 其后 **113–144 ms（三次 122.5 / 113 / 124.5 ms）** 该 ref 与其父目录被**另一个进程**删除。
  ⇒ 不是 git 写失败，是**外部进程在 git 提交 ref 后约 120 ms 删掉它**。
- **对照**：顶层 ref（`refs/heads/master`）正常；`git init` 的**全新**仓库里嵌套引用也正常
  ⇒ **本仓库特有**，不是 git 2.55 的通用 bug（本机系统 Git 与 PortableGit 都是 `2.55.0.windows.3`）。
  `.git/config` 干净、无相关钩子、无 `.lock` 残留。**哪个进程删的：仍未定**。
- **应对（已落地，实测过两条路径）**：跑 `dispatch-output/local-candidate-closeout-20260928/restore-candidate-ref.sh`
  （两级恢复：reflog → bundle；含 `rev-parse` / `worktree list` / `log` 三处核对）。
  手工等效命令：
  `mkdir -p .git/refs/heads/codex && printf '%s\n' "$(tail -n 1 .git/logs/refs/heads/codex/local-candidate-closeout | awk '{print $2}')" > .git/refs/heads/codex/local-candidate-closeout`
  ⛔ **不要**用 `git update-ref` / `git branch -f` 去"修"它（会被再次抹除）。
- **增量备份（故意放在仓库外，便于 `.git` 本身受损）**：
  `C:\Users\33393\Desktop\ai-legal-helper-bundles\local-candidate-closeout-fbc29e8.bundle`
  （7299 B，含 `fbc29e8`，前置 `aec8d5c` 本机存在，sha256 `f706c1ccf80e39c214e29dd90b819a5416636d4d725c8b52d3a94bfc41c36de7`）。
  核对 `git bundle verify <bundle>`；重建 `git bundle create <bundle> codex/local-candidate-closeout --not master`
  （**路径必须 `C:/...`**，用 `/c/...` 会报 `.bundle.lock: No such file or directory`）。
- 排查用的可复现脚本：`dispatch-output/local-candidate-closeout-20260928/watch-ref-write.py`。
- **接手动作**：动该分支前先 `git rev-parse --verify refs/heads/codex/local-candidate-closeout`；每次提交后回填并核对。

### 9.2 其余坑

- **路径形态**：见 §4 假红①。本机 Bash 也缺 `grep/head/tail/ls/cat/dirname`，要 `export PATH=...PortableGit/versions/1.2.0/usr/bin:$PATH`。
- **pip-audit / 联网**：Python 内发起联网请求可能杀 bash 进程；审计慢就加 `--timeout`。**扫描器故障不要写成"零漏洞"。**
- **沙箱 safe-delete 批量守卫**：pytest 启动时会整树删已存在的 `--basetemp`，一个 tool 调用里**串跑多次 pytest 且共用 basetemp**
  会在第二跑起炸成大批 `SystemExit: 1` 假红 ⇒ **每跑次用唯一全新目录**；不要改 `CODEBUDDY_SAFE_DELETE_*`。
- **`.gitignore:45` 全仓忽略 `*.log`** ⇒ 证据日志不入库（见 §5 注）。
- **测试隔离**：`conftest` 已把 `DATABASE_URL`/`QUOTA_DB` pin 到进程私有临时库；候选树的 `backend/chroma_db` 是 **144KB 空桩**，
  **不是**主工作区那份 349MB 真实库 ⇒ 在候选树跑测试不会污染真实 KB。
- **别碰**：`backend/app.db`、`backend/data/app.db`、两处配额库、`backend/chroma_db`、共享 `backend/venv`。

---

## 10. 接手后的建议顺序（我的推荐，可被推翻）

1. **复核候选引用还在**（§9.1），不在就用恢复脚本；顺手 `git status` 确认两处工作树干净。
2. **推动 Owner 两件裁定**（§6）—— 这是唯一让阶段能收口的路，其余都是等。
3. **凭据轮换完成后**，按规划书 E 节跑一次隔离 rerank 验收（配额与数据库隔离、只跑一次、记录模型名/成功或降级/`(法名,条号)`）。
4. **依赖风险按 A/B/C 分档执行**：A 档请 Owner 书面接受（带范围+复审日期，`residual-risk-review.md` 里最迟复审日是 2026-10-05）；
   B 档先做运行时探针把证据升级；C 档立票不动。**09-29 更新**：B 档已做完，可签文本已按这三档写在 §6② 末尾（Owner 改字或划掉即可，不必从零起草）。
5. 只有 D2/D3 有结论后，才谈把候选分支合入 `master` 或进入发布准备（第 4 节发布表：凭据 / Git 与远端 CI / 真实语料 / 生成式验收 / 部署）。

---

## 11. 关键文件索引

| 想看什么 | 去哪 |
|---|---|
| 规划书 + A–F 执行记录（权威） | `docs/superpowers/plans/2026-09-28-local-candidate-closeout-plan.md` |
| 本批证据索引（含全部读数与缺陷留痕） | `dispatch-output/local-candidate-closeout-20260928/README.md` |
| 阶段正文（主报告） | `docs/progress-handoff-report-20260925.md` §9.12.17 |
| 一页式汇总（可直接转 Owner） | `docs/assistant-briefs/next-phase-E-integration-report-20260927.md` 第十一节 |
| 剩余依赖风险逐项 | `dispatch-output/local-candidate-closeout-20260928/residual-risk-review.md` |
| 恢复工具 / 缺陷探查 / 保护对象校验 | 同目录 `restore-candidate-ref.sh`、`watch-ref-write.py`、`verify-protected.py`（三者都已在证据目录内，可直接跑） |
| T7 分案（依赖升级选项与回退口径） | `docs/assistant-briefs/t7-dependency-upgrade-options-20260927.md` |
| B 档逐条运行时判定表（由读数现生，含「公告视角 17/9」） | `dispatch-output/local-candidate-closeout-20260928/b-probe-verdict-matrix.md`（重算：`python b_probe_matrix.py`） |
| B 档探针仪器 / 自检 / 两场入库读数 | 同目录 `b_runtime_probe.py`、`b-probe-selfcheck.log`（+ `-break.log` 负例）、`b-probe-readings-pytest-20260929-103147.json` 与 `...-103511.json`（两腿）、`b-probe-readings-app-20260929-103841.json` |
| 两腿复跑逐条比对 | 同目录 `b_probe_pair_check.py` → `b-probe-pair-check.log`（重跑：`python b_probe_pair_check.py <A> <B>`） |
| 外联逐键归类 + 归类器反例 | 同目录 `b_probe_net_audit.py` → `b-probe-net-audit.log`（`--selftest` 先跑；整体 **rc=1**，红因是那 1 次 `test.invalid` 解析） |
| 唯一非环回解析的用例归因 | 同目录 `b_probe_dns_trace.py` → `b-probe-dns-trace.json`（指向 `tests/test_phase3.py::test_healthz_components`） |
| 请求体脱敏哨兵对照 | 同目录 `b_probe_net_sanity.py` → `b-probe-net-sanity.log`（7/7 PASS） |
| 主张复算器（文档每条数字重算一遍） | 同目录 `b_probe_claim_check.py` → `b-probe-claim-check.json`（**通过数/条数不手抄**，跑命令看合计行） |
| 复算器的可红性证明（变异对照） | 同目录 `b_probe_claim_mutants.py` → `b-probe-claim-mutants.log` / `-mutants.json`（**杀数不手抄**，看命令末行"合计 k/n"） |
| 保护对象第二次复验（本轮各场跑完后） | 同目录 `verify-protected.py` → `protected-probe-rerun-check.log`（41/41 未变；09-28 那份 `protected-postcommit-check.log` 未被覆盖） |

---

## 12. 2026-09-29 接续会话补记（逐条现量，接手可直接重跑）

本轮做的**只有** Owner 裁下来的那一件（B 档探针）。代码候选、master、共享 venv、真实库都没动。

**接手时先复量，这几条是本轮开始时的现量**：

- `git log --oneline -6` → master `5be6e05`（交接书 §0 那句"只可能再叠加文档提交"成立）。
- `git rev-parse --verify refs/heads/codex/local-candidate-closeout` → **fbc29e8 仍在**（§9.1 那个缺陷本轮未复发，但纪律照做）。
- 两处工作树 `git status --short -uno` 均干净；候选差异仍是 `aec8d5c..fbc29e8` 的 **7 个文件**。
- 保护对象复验：`python verify-protected.py` → **41/41 未变** rc=0；
  目录级第二读数 `find backend/chroma_db -type f -newermt "2026-09-29 00:00"` → **0**（共 38 文件）。
  本轮 B 档各场跑完后**又复验了一次**（`python verify-protected.py <新日志路径>` → 41/41，落
  `protected-probe-rerun-check.log`），`find` 第二读数同样为 **0**。
  ⚠️ **但本轮确实覆盖过一次 09-28 那份证据日志**：早段（03:21）我无参跑了 `verify-protected.py`，
  写掉的正是报告引用的 `protected-postcommit-check.log`。两份内容 `diff` 为空（都是 41/41）⇒ **结论没丢**，
  但"未被覆盖"这句话此前是错的，已在 README G.3 第 14 条与本节缺陷清单 ⑭ 如实记账；
  随后给脚本加了可选 `argv[1]` 输出路径，避免第三次。
- 候选解释器、wheelhouse、仓库外 bundle 三样都在原位；bundle 现量在**仓库外那个目录**：
  `C:\Users\33393\Desktop\ai-legal-helper-bundles\local-candidate-closeout-fbc29e8.bundle`（7299 B，mtime 09-29 01:21；
  本轮未动候选分支，故未重建）。复核：`ls -l /c/Users/33393/Desktop/ai-legal-helper-bundles/`
  —— **别去 `Temp/legal-closeout-20260928/` 下找**，那里只有 venv 与 wheelhouse。

**本轮新增的可复核产物**（全部在证据目录，`.py`/`.json`/`.md` 入库，`.log` 按仓规不入库）：
`b-probe-survey.py`（符号存在性与静态 import 面）、`b_runtime_probe.py`（22 只桩 + 自检）、
`b_probe_alias_canary.py`、`b_probe_build_tree.py`、`b_probe_run_suite.py`、`b_probe_app_paths.py`、
`b_probe_matrix.py`（末尾新增「公告视角」：26 条公告拆成**有桩可答 17 条 / 答不上 9 条**，带 `17+9==26` 闭合检查）、
`b_probe_claim_check.py`（**主张复算器**：把文档里每条数字对着入库读数重算；**条数只认命令的合计行，本档不复抄**）、
`b_probe_pair_check.py`（两腿逐桩五轴比对）、`b_probe_net_audit.py`（对**全部**网络事件键逐条归类 + 归类器自带反例）、
`b_probe_net_sanity.py`（哨兵口令对照：证明请求体与头值进不了读数、而 URL/方法/头键名照常可判）、
`b_probe_dns_trace.py`（独立插件，把唯一那次非环回解析归因到用例）、
`b_probe_claim_mutants.py`（给复算器做变异对照：**杀了多少只只认命令末行的"合计 k/n"**，本档不复抄）。

**读数可复跑**：同一版入库代码把测试场跑了两遍（`b-probe-readings-pytest-20260929-103147.json` 与
`...-103511.json`），22 只桩在判定/计数/干跑数/调用方集合/实参摘要五个轴上**零差异**，`collected`、`exitstatus`、
`compile` 9826、net **206 类 / 348 次**、在场模块 29、别名补钉 4 项也逐一相同（`python b_probe_pair_check.py <A> <B>`，rc=0）。
被引用的读数都**晚于**仪器与驱动的最后一次代码编辑（`ls -l --time-style=+%H:%M:%S` 比 mtime 可核，
且这条已经是复算器的一条主张），即"报告里的数字出自将要提交的那版代码"。
⚠️ 上一稿引用的那对读数（`023538` / `030644`）**已因含 HTTP 请求体从磁盘删除**，见下面第 ⑨ 条。
复算器自己红过三次，三次都是它自身的缺陷（模型名没截 `kw=` 尾巴；`glob` 返回的字符串当 `Path` 用；
变异件放进临时目录跑导致 12 只全 rc=2「缺入库读数」——看着像全杀掉，其实根本没跑），修完才转绿 —— 这条也照实留着。

**本轮为这批读数付的 17 处仪器/证据缺陷（全部已修，逐条可查 README G.3；其中 ⑬–⑰ 是独立评审那一轮抓出来的）**：
① 符号解析循环漏试单段包名 ⇒ 把 `transformers.PreTrainedModel.from_pretrained` 误报"不存在"；
② 仪器在别的模块执行中途对 `transformers` 做惰性 getattr ⇒ 触发循环 import、打断 `tests/test_citation.py` 收集（闸门把它拦成"实验无效"，读数改名 `.INVALID`）；
③ 分母读错轴（`1660/1678 tests collected` 取了 1678）⇒ 把一场 1660/1660 全绿的运行误判成无效；
④ 装桩时刻太晚 ⇒ 出现"G3e=0 而同一处的 `from_pretrained`=1"的自相矛盾，改为 `-p` 载入即装桩并新增 `preloaded_app_at_install` 完整性读数与非空即判无效；
⑤ 模块名与类名同名的形状解析不到 ⇒ class-init 计数器必然漏首次实例化；
⑥ 别名对照原本无区分力（`install()` 自带 sweep 把遮蔽腿也补了）⇒ 改成 `install(sweep=False)` 的 `+0 → +1` 差分；
⑦ `compile` 事件（本场 9826 次）把连接明细挤出截断窗口 ⇒ 早先"连接全环回"是从被截断的集合得出的；现单独计数、窗口 120→400；
⑧ 我把 `DATABASE_URL` 写成裸路径（要 `sqlite:///`）——测试场因 conftest 无条件覆盖它而未受影响，应用路径场第一次 upload 步骤因此失败，改对后跑通。
⑨ 🚨 **审计明细把 HTTP 请求体写进了读数**（提交前扫密才发现，各 44 条）：`urllib.Request` 事件的 `args[1]` 就是请求体，
   测试里那几次登录带的正是 `{"username": ..., "password": ...}`。两份受污染读数**已从磁盘删除**，
   仪器改成只记 URL / 方法 / 头的**键名**（对着 `Python311/Lib/urllib/request.py:518` 的审计签名核过轴，`data` 不碰），
   并补了哨兵对照 `b_probe_net_sanity.py`（7 条断言：4 条钉"这一层确实在被记"、3 条钉"哨兵 0 命中"）。
   **教训**：外联明细天然是敏感面，"只记有没有连"这件事本身就要求脱敏，此前我没这么看它。
⑩ "连接全是环回"此前是从运行器打印的前 25 条键得出的（截断集当全集）。现改为对**全部 206 个键**逐条机器归类
   （`b_probe_net_audit.py`），且"键里没有主机字段"（`ctypes.dlopen`/`subprocess.Popen`）**单列一档不许折进环回**；
   归类器自带 8 条合成反例（其中 3 条必须判成非环回），否则"0 条非环回"只是尺子瞎了。
   该审计整体 **rc=1**，红因正是唯一那次非环回解析 —— **我没有为了让它绿而放宽判据**，而是把它归因清楚。
⑪ 复算器里有一条**永远不会红**的主张（`claim(..., True, "人工核对")`），恒真的"复算"是装饰；已删并换成两条真会算的，
   另加 `b_probe_claim_mutants.py`：给每条关键主张各造反例，证明复算器真会红（只数与条数只认命令输出）。
⑫ **扫密这一步自己也造过一次假零**：把待提交清单存进变量再 `grep $FILES`，清单是仓库相对路径而 cwd 在证据目录
   ⇒ grep 全线报错被 `2>/dev/null` 吞掉，八个模式齐刷"hits=0"。改成在仓库根用 `git ls-files --others` + `xargs`，
   并**先用已知存在的假值打正向对照**（`test.invalid` 必须命中）之后才得到真读数：
   32 只待提交件里 `sk-`/`LTAI`/`AKIA`/`PRIVATE KEY`/JWT `eyJ….eyJ` **0 命中**，
   `password`/`secret`/`api_key`/`Bearer` 的命中逐条摊开全是驱动假值、脱敏检查代码本身与 pydantic 类型名 `Optional[SecretStr]`，
   `Authorization` 59 处全是头键名形态、无一处带值。**教训**：`2>/dev/null` + 变量传路径 = 假零生产器，
   负向主张必须先有一条能命中的正向对照钉住方法。
⑬ **外联归类器三处静默漏判，方向全朝"看起来更安全"**：IPv6 四元组、十进制整数 IP（`2852065534` 即
   169.254.169.254，SSRF 常用绕法）、`os.system` 带的 URL —— 三种都被旧判据归进"无主机字段"。
   改为 **non-loopback 优先** + 用 `ipaddress` 认址（顺带钉"十进制 127.0.0.1 仍是环回"不误伤）+ `os.system` 同扫；
   合成反例 8→**15 条**，并加**数据侧**对照 `--injected-selftest`（往真读数副本注入 2 类外发、只同步 kinds/total
   使"自洽"轴保持绿 ⇒ 红的只能是外发判定）。**这条最该记**：第 7、10 两处修法我当时都以为改对了，
   但自证用的合成键是按旧理解写的，所以"归类器能红"当时只覆盖了我想到的形状。
⑭ **覆盖了上一轮那份被报告引用的证据日志**（03:21 无参跑 `verify-protected.py`）；两份 `diff` 为空、结论没丢，
   但"未被覆盖"的说法此前是错的。已给脚本加可选 `argv[1]` 输出路径。
⑮ 判定表把 `NEVER-IMPORTED`（未测）与 `ZERO-CALL`（测到 0 次）混在同一个"判定集合"里打印 ⇒ 改成三档分栏。
⑯ 两条**名实不符**的主张（"qa 跑通且未调用生成模型"其实只断言字段存在；文档残留检查的 `if d.is_file()` 会让改名的文档
   整条检查空过）＋一条冗余主张（"总桩数=22"与四组之和重复）⇒ 全部换成真判据/闭合式，并补"文档在位"主张。主张 58→**61**。
⑰ 三条 **over-claim 被评审抓出后收回**：应用场那条 `langchain_openai` "从未被导入"其实是**驱动没 import `llm_registry`**
   （⇒ 改判"该场未测"）；`trust_remote_code=False` 被推广到不传该键的 `G3d/G3e`（⇒ 限定到 `G3a/G3b`）；
   外联普查没披露"带凭据外呼被开关关掉"（⇒ §6② 加 ⚠️ 段）。

**独立评审那一轮（两路正交，只读）**：A 路逐条复现行号与读数 —— 11 处不符（自检未装上的是 3 只不是 5 只、
`protected-postcommit-check.log` 的 mtime 暴露了 ⑭、`trust_remote_code` 只在两只桩上有值、"未被覆盖"与"各含 44 条"
两处措辞、`watch_ref.py` 死名、`total=1678` 只在 stdout 未落日志、main.py 行号在两棵树差 1 等），除"44 条"属删除前实测不可复算外**全部已改**；
B 路挑战论点 —— 提出 ⑬⑮⑯⑰ 与四条"为真但没披露"（子进程在外、反序列化原语无桩、脱敏只钉一类键、
`NEVER-IMPORTED` 是"包真装了但没导入"的真阴性）。**B 路的四条限定已全部写进 README G.4**，
其中"包确实装了"这条是白捡的加固：五个目标模块在候选 venv 里 `find_spec` 全部 FOUND。

**顺带查出来的一条应用事实（与风险裁定有关，不是缺陷）**：应用**有一个设计内的主动外联点** ——
`/healthz` 会拿 `settings.llm_base_url` 的主机做 TCP 连通探测（`backend/main.py:337-342`，
`socket.create_connection(..., timeout=3)`，软检查、不影响 200/503 的硬项）。
本轮那 1 次非环回解析正是它（用例 `tests/test_phase3.py::test_healthz_components`）。
⇒ B 档"运行期 0 调用 / 连接基本全环回"是**对被桩的 22 个目标**成立，**不等于**"这个应用不会 outbound"；
   Owner 接受风险时请把这一条算进暴露面。

**本轮明确没做**：未 push、未建远端分支/PR、未合并候选分支、未部署、未启动生产容器、
未写真实库（应用路径场用的是空副本集合）、未调用生成模型与真实 rerank、
未运行 `smoke_citation_full.py` / `smoke_citation_fast.py`、未改共享 `backend/venv`、未动其余 8 个 worktree、
未 `git add -A`（本轮只暂存证据目录新增件与**六份**文档：本交接书、主报告 §9.12.17(9)、E 报告⑧、计划书执行记录、证据 README）、
**未接受任何剩余风险**（探针只升级可达性证据，47/57 条 `pip-audit` 红读数一条没少），
未加 `--ignore-vuln`、未跳测试、未放宽 CI，
两只 `*.INVALID`（被闸门判废的读数）**留盘作缺陷证据但不入库**，
**未动 09-28 那三只脚本**（`verify_corpus.py` / `watch-ref-write.py` / `summarize_audit.py`
——它们各有 1 条 `UP009` 与 formatter 红，但本轮没复跑它们产出的读数，混改会让"数字出自哪版代码"变糊，理由记在 README G.6）、
**未改 `docs/assistant-briefs/t7-dependency-upgrade-options-20260927.md`**
——那文件的 T7 分档口径由候选分支 `fbc29e8` 持有，在 master 上另改会造出两处真源，留到 D3 合并时一并改。

**本轮实际执行顺序（关系到"哪个读数出自哪版代码"）**：先交付探针并出数 → 提交前扫密发现读数里有 HTTP 请求体 →
改仪器（只记 URL/方法/头键名）+ 删两份受污染读数 → 用改后仪器复跑测试场两腿（`033015` / `033335`）→
再把本目录脚本按仓库 ruff 规则集（含 `UP`）清了一遍风格 → **清完又复跑一次全部场**
（测试场 `103147` / `103511`、应用场 `103841`、自检 `b-probe-selfcheck.json`）⇒
**报告里引用的数是最后那批**，它们晚于仪器与驱动的最后一次编辑；`033015` / `033335` 留作"风格清理前后"的对照，
两者与现行版在判定/计数/net 分类上逐条相同。

**下一步（现在唯一能推动的）**：D2 落笔。材料是 §6② 那张表 + `b-probe-verdict-matrix.md`
（含新的「公告视角」两栏：**有桩可答 17 条 / 探针答不上 9 条**）+ 上面那条 `/healthz` 主动外联事实；
请给「接受范围 + 复审日期」（`residual-risk-review.md` 里最迟复审日 2026-10-05），并单独判 D6（`CVE-2024-7774` 映射疑点）。
D4（凭据轮换）完成并告知后，才按既有授权只跑一次隔离 rerank，那才有本阶段的 24/24 现量。

### 12.1 同日二次补记：D2 可签文本已起草（Owner「你来执行」后落的笔）

- **做了什么**：§6② 末尾新增「D2 可签文本（草案）」六栏 + 签字位（接受范围只覆盖"本地候选形态下本阶段不升级不改码"、
  5 件保持在册待办、限制清单与自动失效条件、两条必须算进暴露面的应用事实、复审日期、签了也不解除的四条）。
  §8 的 D2 行与 §10 第 4 步各加一句指向它。**没有新增文件**，仍在同一份可转发交接书里。
- **⚠️ 我自己一处建议作废并改正**：起草前我在会话里把复审日期建议成"2026-12-31 或下一次依赖升级"——
  **那是错的**：`residual-risk-review.md:8` 与文末附录 `:61` 都已把复审最迟日期钉成 **2026-10-05**，
  且写明"提前发布 / 启用新入口 / 收到新公告 ⇒ 立即复审"。那个日期是在册约定，不在助手可代改的权限里。
  可签文本第五栏已按 **2026-10-05** 写，并给复算器加了一条主张专门钉"签字页日期 == 登记表日期"——
  也就是说，**这条错误如果进了签字页，复算器必须红**（已用变异对照证过它能红）。
- **复算器同步加的主张与变异（**条数只写命令，不抄数**：`python b_probe_claim_check.py` 看合计行、`b_probe_claim_mutants.py` 看"合计 k/n"）**：
  ① 签字页 ① 栏列的"无桩可答"清单，与 `residual-risk-review.md` 去重公告集减去读数里真有桩的公告集，**逐条一致**；
  ② 签字页第五栏的复审日期与登记表 `复审最迟日期为 …` 字面一致；
  ③ 签字页里出现的每条公告号都必须在登记表内（防我把不存在的通报写进签字页）；
  ④ 六栏栏目名齐备且带"签字位"（改着改着把某一栏删掉 ⇒ 红）；
  ⑤ **文档里指向本复算器的段落不得出现手抄条数**（这条是本轮自己治自己的：全仓曾有二十多处写着旧的复算/变异条数，
  加一条主张就集体过期一次；现已改成只指向命令，并由一条变异证明这把尺子能红。
  ⚠️ 它的词表**不完备**：`**N 条**主张`、跨行的"N 条⏎主张"这类形状现在抓不到 ⇒ 只能当绊线，不能当"已无手抄"的证明，
  细节与踩坑记录见证据 README 的 G.7）。
  变异侧除了改期望值，本轮**新增一类"文档侧反例"**：直接把签字页的日期抄成 2026-12-31、把无桩清单漏抄一条公告，
  要求复算器必须红且文档按**原字节**还原（sha 先留底、`finally` 还原后再比一次）。
- **本补记之后未做的事**：仍未 push、未合并、未接受任何风险（**草案不是签字**）、未动凭据、未跑真实 rerank、未写真实库。

### 12.2 独立评审轮（只读复核这份汇报）：八条发现，逐条本机复现后的采信账

评审是第三方会话、只读、按两路跑（A 逐条复现行号与读数 / B 挑战论点与补漏）。**采信单位不是"评审说多严重"，
而是"那条命令在我机器上跑出什么"**。下面每条都带判决与依据。

**已证实并已修（6 条）**

1. 🚨 **签字页第六条漏了一条在册阻塞**：我只写了 `ADMIN_PASSWORD` 未轮换，**漏了 §6① 那把被意外打印过、
   按"已暴露"处理的 SiliconFlow rerank key**——而它正是唯一"已经暴露过"的凭据，也同时挡着真实 rerank（D4）。
   漏它的后果是 Owner 把一次签字读成整批放行。⇒ 第六条改成逐条编号，两条凭据**分开列**、各自写状态。
   并加了一条主张钉这一栏（含"两条凭据都在"+"推送顺序里不许把已完成的 Q5 当待走"），配一只变异证它能红。
2. 🚨 **签字页第一栏把 B 档统一写成"两场内运行时 0 调用"，与自家读数冲突**：现量 `G3a/G3b/G3d/G3e` 两场都是
   **1-CALLS**（模型/config/tokenizer 各加载 1 次），`G2a` 在应用场是 **NEVER-IMPORTED**（该场从不构造聊天客户端，
   属"未测"）。⇒ 一栏改成"三种读数形态分列"，并写明**签的是读数说的那件事，不是档位标签**：
   ① ZERO-CALL；② 1-CALLS 但调用方与参数可唯一归因（`rag_chain.py:39`、模型名钉死、`trust_remote_code=False`）；
   ③ 某场未测。**这条若没被抓出来，就是我把"跑到了"说成"没跑到"让 Owner 签字。**
   > ⚠️ **本补记自己也留了同一处含糊**：上面那句把 `trust_remote_code=False` 与"模型/config/tokenizer 各 1 次"并排写，
   > 读起来像四个调用都带该实参，而实测只有 `G3a/G3b` 带。**签字页以 §6② 当前措辞为准**（该栏已限缩，并补了
   > transformers 4.57.6 落在 `CVE-2026-4372` 的 `< 5.3.0` 区间、公告写明绕过该机制这条事实）；本段保留作当日记录，别再从这里转抄。
3. **同源核对覆盖选反**：机器只钉了 ①②栏的清单与日期，恰恰没钉出错的第六条。⇒ 已补上第 1 条那条主张。
4. **"第五条那四条在册阻塞"指错栏**（四条在第六条）⇒ 已改成"第六条列的那几条"。
5. **复审日期只比登记表第一个出现处**（`re.search`）⇒ 改成 `findall` 要求**登记表内所有出现处彼此一致且等于页面值**，
   并加一只**文档侧变异**：真把登记表第二处（`:61`）改成 2026-11-11 ⇒ 主张必须红（现量已证：能红）。
6. **绊线会"假装干净"的段分裂形状**：空行后紧跟的**缩进续行**不并入上一段，"上一行提本件、下一行写数"就永远不进作用域。
   ⇒ 分段规则改为缩进续行折回上一段，且"单行标题段提到本件"时把下一段一并纳入作用域。
   同时按评审给的具体例子复核：`README.md` 那段确实还写着"总 120 只 / `.log` 60 只 / 可提交 58 只"这种**已过期**的快照数
   ⇒ 那一段现改成只给命令（`git ls-files` 两条），不再抄数。

**证伪或部分证伪（2 条，留反证）**

7. **"`.git/hooks` 确有 post-commit / post-checkout 在跑，窗口内提交会把改错的签字页带走"** ⇒ **一半成立**：
   两个文件确实存在，但 `wc -c` 各 **10 字节**、内容只有 `#!/bin/sh` 一行，**是空壳钩子，不执行任何动作**
   （`core.hooksPath` 未配置）。所以"钩子会做什么"不成立；不过"窗口内别人提交会带走脏文档"这句仍然有效，
   只是没人能替我保证——我改不了别人的提交时机。⇒ 加了**并发守卫**：还原前若发现该文件的字节≠我写进去的那份，
   就判这只变异**无效**并如实报（宁可不算覆盖）。窗口长度是每只约 1 秒级，但风险不为零，这条限定保留。
   顺带一条对旧结论的修正：交接书 §9.1 说"嵌套 ref 被删，**哪个进程删的仍未定**"——**不是这两个钩子**干的（它们是空壳）。
8. **"绊线词表该覆盖 `README` 里那些数"** ⇒ 部分不采纳：评审举的 `1660 / 206 类 / 348 次 / 9826` 是**运行读数**，
   不是"复算器条数"那一类手抄，本来就不在该绊线射程内（它只管"指向本件的段落里不许写本件的条数"）。
   词表也确实不完备（`**N 条**主张`、跨行写法抓不到）——这句限定我原先就写在 G.7，维持原判：**它是绊线，不是证明**。

**改完后现量**（`cd dispatch-output/local-candidate-closeout-20260928`）：`python b_probe_claim_check.py` rc=**0**、
`python b_probe_claim_mutants.py` rc=**0**（含新增的文档侧与第六条反例，条数/只数只认命令输出）。
