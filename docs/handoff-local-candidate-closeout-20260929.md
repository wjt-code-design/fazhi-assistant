# 交接书 · 本地候选收口（pypdf / FastAPI 隔离升级）—— 2026-09-29

> **本文是本批次「本地候选收口 A–F」的接手入口，可单独交给接手者，不需要此前任何会话上下文。**
> 配套三份（按权威顺序）：① 规划书与执行记录 `docs/superpowers/plans/2026-09-28-local-candidate-closeout-plan.md`（**冲突时以它为准**）；
> ② 证据索引 `dispatch-output/local-candidate-closeout-20260928/README.md`；③ 阶段正文 `docs/progress-handoff-report-20260925.md` §9.12.17 与
> `docs/assistant-briefs/next-phase-E-integration-report-20260927.md` 第十一节（两者同源）。
> 本文只写**接手真正需要知道的东西**：状态、命令、读数、坑、以及还没定的决策。

---

## 0. 30 秒定位

- 仓库：`C:\Users\33393\Desktop\ai-legal-helper`（Windows / Git Bash；**全部本地提交，远端未推送**）。
- 发布线 `master` = `e4ea073`；**代码候选**在另一个 worktree 的分支上：`codex/local-candidate-closeout` = `fbc29e8`
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

隔离环境里的两项依赖升级（pypdf、FastAPI）**代码与测试都做完并已提交**，提交后九步门禁在该提交树上**全绿**（唯一红是依赖审计，且是"漏洞非零"的红，不是失败）；
隔离语料在副本上跑完导入/幂等/恢复；**但**剩余依赖风险尚未获得 Owner 接受，**真实 rerank 因凭据待轮换而未复验** ⇒ 按规划书 F 节判据只能给「阶段仍未完成 / 候选受阻」。

---

## 2. 代码落在哪（最容易搞混的地方）

**代码只在这个分支，没有合进 master。** 两处提交：

| 位置 | HEAD | 内容 |
|---|---|---|
| `master`（发布线） | `e4ea073` | `aec8d5c` 之后**只有文档**：`725a207` 两份报告、`8ae321b` 计划书+证据目录、`0429c42` 计划书对账、`e4ea073` 恢复工具+bundle 登记 |
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
| 提交后九步门禁（候选树 `fbc29e8`） | 见 §4，唯一红 = 依赖审计 47/8 | `postcommit-gates.log`（`[6R]/[7R]/[8R]` 是路径修正后的重跑） |
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
| **D2** 依赖风险口径 | 接受 / 分档 / 立即修复；接受的**范围与复审日期**怎么定 | ⏳ 未定（提案见 §6②） |
| **D3** 候选与 master | 隔离期多长、合入门槛是什么 | ⏳ 未定（当前立场：**不合并**，直到 D2 有结论） |
| **D4** 凭据与 rerank | 轮换范围（是否含旧备用 key）、复验范围与次数 | ⏳ 未定（当前立场：**只跑一次**，轮换后） |
| **D5** 下一阶段目标 | 回功能线 vs 先做发布准备 | ⏳ 未定（当前立场：先做发布准备，因为真正卡发布的是服务器选型与真实库写入策略，不是代码） |

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
   B 档先做运行时探针把证据升级；C 档立票不动。
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
