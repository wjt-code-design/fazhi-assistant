# 当前阶段收口：本地候选执行规划书

> **派发边界：** 第 3 节 A–F 是本地候选收口（当前阶段）任务；第 4 节是交付之后的后续阶段事项，不属于当前派发范围，除非 Owner 另行批准。执行者使用 `executing-plans`，按责任文件隔离并记录证据；不要把第 4 节当作当前待办。

> **接手指令：** 只收到本文件路径的助手，请读取本文件和第 0 节列出的证据索引，核对当前状态，完成无需 Owner 操作的未勾选项及本地交接，记录实际命令/退出码并给出第 F 节的三态结论。凭据轮换和剩余风险接受由 Owner 决定；等待期间继续可独立完成的工作。

**Goal:** 在既有“本地候选就绪、暂不部署”的目标下，解决可控的环境和依赖问题，验证隔离语料与最终代码，形成有证据的阶段结论。

**Architecture:** 先核对代码、报告和远端事实，再在独立环境中分两项处理 PDF 与 Web 依赖，随后验证隔离库和固定候选。沿用现有应用、测试和 CI，不新增通用框架。风险未解除时如实保持阻断。

**Tech Stack:** Windows PowerShell、Git、Python 3.11、pip、pytest、Ruff、mypy、pip-audit、Chroma、Next.js/Vitest。

**状态：** 当前阶段执行中，最终验收与本地收口未完成。Owner 于 2026-09-28 确认纳入两项升级。根目录 `C:\Users\33393\Desktop\ai-legal-helper`，下文仓库相对路径均相对此目录；命令中的 `$Repo` 始终指这个绝对路径。

## 0. 接手入口（先读，再执行）

本文件可单独交给接手助手；无需此前会话。先核对下列路径和 Git 状态，再从第 6 节“当前阻塞与待完成项”接手。A–D 已执行，E 的自动化检查曾在未提交工作树执行；不要因保留了原执行步骤而从 A 重新开始。提交后的完整门禁复验是明确待办，其他检查仅在相关代码、依赖、环境或证据变化时重跑。

| 位置 | 当前用途 |
|---|---|
| `C:\Users\33393\Desktop\ai-legal-helper`（`master`，基线 `aec8d5c22a202c2b7b711d169096777d316f2932`） | 主工作区；两份进度报告已有未提交修改，须保留并追加 |
| `C:\Users\33393\.codex\worktrees\local-candidate-closeout\ai-legal-helper`（`codex/local-candidate-closeout`） | 本轮代码候选；pypdf/FastAPI 修改、必要修复和测试仍未提交 |
| `C:\Users\33393\AppData\Local\Temp\legal-closeout-20260928\venv\Scripts\python.exe` | 已验证的独立 Python 解释器；不存在时先重建，不得回退到共享 venv |
| `C:\Users\33393\AppData\Local\Temp\legal-closeout-20260928\wheelhouse` | 助手已下载的离线包；重建环境时先核对该目录与证据目录内的下载回执 |
| `C:\Users\33393\Desktop\ai-legal-helper\dispatch-output\local-candidate-closeout-20260928\README.md` | 本轮证据索引；同目录有最终测试、审计和语料副本日志 |

接手时先运行：

```powershell
$Repo = 'C:\Users\33393\Desktop\ai-legal-helper'
$Candidate = 'C:\Users\33393\.codex\worktrees\local-candidate-closeout\ai-legal-helper'
git -C $Repo status --short --branch -uno
git -C $Repo status --short -- docs/superpowers/plans/2026-09-28-local-candidate-closeout-plan.md dispatch-output/local-candidate-closeout-20260928/README.md
git -C $Candidate status --short --branch
git -C $Repo rev-parse HEAD
git -C $Candidate rev-parse HEAD
```

上表是 2026-09-28 的状态快照；若提交或文件集已有变化，先查明归属，再决定哪些验收需要更新。主工作区的报告修改不会自动出现在候选工作区。

接手后按这个顺序处理：① 审阅候选差异并在候选分支精确提交；② 在提交后的候选代码上完成 E 的后端复验；③ 在主工作区保留既有修改，追加两份报告并分别提交经审阅的文档；④ 将依赖风险和真实 rerank 留作明确阻塞，待 Owner 裁定风险、轮换凭据后再完成相应验收。若 Owner 尚未处理阻塞，先完成前三步并报告“阶段仍未完成/候选受阻”。

> **2026-09-28 接手会话执行结果：①②③ 已完成，④ 的两项阻塞仍在。** 候选分支 `HEAD = fbc29e8`（4 笔 / 7 文件），master `HEAD = 8ae321b`（2 笔文档）。
> 提交后九步门禁读数见 §3 E 段；两项 Owner 动作与新发现的仓库 git 缺陷见 §6。三态结论：**阶段仍未完成 / 候选受阻**。

## 1. 当前事实与完成边界

### 1.1 已完成且不重复实现

- 当前 `master`：`aec8d5c22a202c2b7b711d169096777d316f2932`。已提交周末加班检索措辞桥接、seed 混合命中漏判修复、引用场景独立条号断言。
- 该提交前的本会话证据：三份相关测试合跑 58 passed；隔离库、真实 rerank 的快速门禁 24/24；修改文件 Ruff/格式检查通过。这些是已有证据，本文编写时没有重跑。
- E 报告的全量 1639 passed、覆盖率 84.91% 针对旧代码快照 `360dca7`，不能当作 `aec8d5c` 或未来依赖环境的全量结果。
- 当前有两份已跟踪报告修改，以及大量未跟踪产物。此前观测的 518 是 Git 状态条目数，不是文件总数；执行时重新计量。
- 138 条是升级前按 requirements 解析的历史审计结果；本轮候选 requirements 实测 47 条/8 包，独立环境实装审计 57 条/10 包（含开发工具）。三者的依赖集合不同，不能直接混为同一个指标。

### 1.2 本地阶段与发布阶段分开验收

本阶段交付：可重建的候选环境、经过兼容性验证的最小依赖修改、逐项依赖风险处置、隔离库结果、当前代码的综合门禁和明确的 Git 交接方案。

后续发布事项：其余历史凭据暴露面审计、远端推送及 CI、真实知识库更新、调用生成模型的发布冒烟、服务器选型与部署。它们保留在交接表中，不作为本阶段必须执行的动作。**例外：**本次执行时意外输出的 rerank 凭据必须由 Owner 立即轮换；这是当前安全阻塞项，不等同于要求本阶段完成所有历史凭据轮换。

**本规划新增的一项范围决定：** Owner 已批准 **pypdf 与 FastAPI 两项隔离升级、必要兼容修复和本地提交**；不升级共享 venv。B/C 按此范围执行，其余既有边界延续。

## 2. 全局约束

- 服务器尚未选择，本轮不部署、不启动生产容器或迁移真实数据。
- 不 push、不强推、不合并不相关历史、不移动 `.git`，不重跑已完成的 Git 修复 cutover/gc/prune。Git 核对在独立审计仓库进行。
- `backend/app.db`、`backend/data/app.db`、两处配额库和 `backend/chroma_db` 都是保护对象。所有有可能初始化数据库的导入、测试、冒烟，必须预先隔离数据库路径。
- 生成模型维持关闭。真实 rerank 原先已获授权，但当前因本地配置凭据需要轮换而暂停；Owner 完成轮换并告知后，按既有授权只重跑一次，不扩大模型或调用范围。测试服务用假凭据和模拟回答，LLM 端点指向不可用的本地地址。不得复制完整真实 `.env` 到候选树。
- 不覆盖共享 `backend/venv`。CPU torch 安装沿用项目路线；记录版本和来源，不因为装环境顺手升级嵌入模型、Chroma 或 LangChain。
- 不新增 `--ignore-vuln`、`continue-on-error`、测试 skip/ignore 来获得通过结果。剩余风险的接受由 Owner 决定，助手不得代签。
- 不做 RAG/Agent 重构，不扩大候选题集，不新增遥测、trigger-tree 配置或钩子；这些不属于本阶段。
- 不批量提交未跟踪产物。目标文件有他人并发修改时只暂停冲突任务，保留修改并核对归属。
- 同一失败命令先分析再重试，完全相同命令最多重试一次；同一 bug 连修三次仍不过，停止该问题的补丁循环并报告原因。

## 3. 文件责任与执行顺序

| 任务 | 允许修改的文件 | 交付 |
|---|---|---|
| A 基线、Git 与报告对账 | 本规划的执行记录；最终在两份既有报告追加现状 | 代码/环境/远端基线与剩余改动归属 |
| B PDF 依赖 | `backend/requirements.txt`；确有缺口时修改 `backend/knowledge_service.py`、`backend/tests/test_knowledge_service.py` 或新增 `backend/tests/test_pdf_upload.py` | 可安装且通过上传行为检查的 pypdf 升级 |
| C Web 依赖 | `backend/requirements.txt`；仅有复现依据时修改 `backend/main.py` 及相关既有接口测试 | FastAPI 升级及鉴权、上传、SSE、限流兼容结果 |
| D 剩余风险与隔离语料 | `docs/assistant-briefs/t7-dependency-upgrade-options-20260927.md`；必要证据 | 逐项风险清单、库副本上的导入与恢复结果 |
| E 综合验收 | 测试发现的范围内最小修复；验证结果 | 固定候选的前后端门禁和真实 rerank 结果 |
| F 提交与交接 | 两份既有报告、本规划、已通过验收的精确文件 | 本地提交、最终阶段判定、后续发布表 |

历史执行顺序为 A → B → C → D → E → F；接手时按第 0、6 节的现状处理剩余工作。B/C 共用 requirements，若需返工须串行并重新验证受影响门禁。证据只保留必要的脱敏清单、审计结果和命令日志，集中放在 `dispatch-output/local-candidate-closeout-20260928/`；不要新增另一套长期报告系统。

## A. 固定基线，核实远端和既有报告

- [x] 记录 HEAD、分支、已暂存/未暂存差异和工作树列表；先审阅两份既有报告修改，保留其历史读数。

```powershell
$Repo = 'C:\Users\33393\Desktop\ai-legal-helper'
Set-Location $Repo
git rev-parse HEAD
git status --short --branch -uno
git diff --cached --name-only
git diff --name-only
git worktree list --porcelain
git diff --check
```

- [x] 复用适合的空闲隔离 checkout；如需新建，先查看 Codex 附件，再用应用的 worktree 工具从执行时当前提交创建。主工作区两份报告的未提交修改不自动带入代码候选。
- [x] 在独立审计仓库获取最新远端 master 和本地 master。读取 remote URL 仅传给 Git，不打印可能含凭据的 URL。比较共同祖先、双方独有提交、树差异；记录每条命令的退出码。无共同祖先是调查结论，不是 Git 再次损坏的证据。
- [x] 纠正旧推送建议中的两个缺口：新分支指向 HEAD 仍会带上祖先历史；快照分支 push 不一定触发 CI。本地 `.github/workflows/ci.yml` 当前只监听 main/master 的 push 和 PR，远端实际配置还需单独读。
- [x] 提供具体同步建议及后续触发 CI 的方式；不建立远端分支/PR。历史凭据问题仅报告路径、类型、对象位置和脱敏结论，不输出值；公共服务商 URL 不自动按密钥处理。
- [x] 记录保护库的文件清单、大小、mtime 与必要哈希；若其他会话正在写库，先取得稳定副本或协调停写，不能把不一致的目录复制称为有效快照。

**验收：** 基线可追踪；最新远端关系已核或明确给出外部访问阻断；能区分“代码损坏”“历史关系不同”“报告过期”。远端暂时不可访问不阻止其余本地任务。

## B. 在独立环境中处理 pypdf

- [x] 用 Python 3.11 在仓库之外创建候选 venv。先用 pip 的 `--dry-run --report` 比较原 requirements 和候选 requirements 的解析变化；安装 CPU torch，再安装候选 `requirements-dev.txt`。不用共享环境的整份 `pip freeze` 作为安装依据，因为它已有声明冲突。
- [x] 初始评估候选为 `pypdf==6.16.1`，这是旧审计给出的修复候选，官方发布记录可查；重新查询当日告警。若该版本仍受影响，选经过官方发布和审计验证的后续 6.x 版本，记录选择依据。本地声明最终精确固定到实际验证版本，不把未经测试的版本区间写成已验证。
- [x] 候选为 6.16.1 且检查成立时，声明修改为：

```diff
-pypdf>=4.0,<6.0
+pypdf==6.16.1
```

- [x] 优先复用既有上传检查；补测试仅限实际缺口：正常含中文 PDF 提取关键文本、空文本拒绝、损坏 PDF 转为受控客户端错误。期望由固定样本确定，不要求无语义影响的所有空白字符逐字相同。
- [x] 管理端上传和合同文件上传均在隔离数据库、模拟回答环境检查；不能为测 PDF 真实调用模型或写入真实知识库。若升级暴露异常处理缺陷，只在现有解析/端点边界做最小修复。
- [x] 保存环境解析清单，运行候选解释器的 `pip check`、对应上传测试和目标文件 Ruff。对原声明与候选声明审计分别记录解析版本、漏洞 ID、别名、退出码；审计服务故障不能写成零漏洞。

**验收：** pypdf 候选目标告警被解除，上传语义与错误路径可用。全环境若被 Web 依赖冲突阻断，保留 B 的局部证据交 C 解决；B 不能据此宣称整个环境自洽。

## C. FastAPI 与传递依赖兼容收口

- [x] 在 B 候选上评估 `fastapi==0.141.1`，重新核对它与 Chroma、slowapi、Pydantic 及 OpenTelemetry 的依赖约束；对比解析清单，发现 LangChain/Chroma/嵌入链路的额外大版本变化时收窄约束或报告冲突。
- [x] 不直接强行指定 Starlette 版本，先由 FastAPI 的官方依赖声明解析兼容版本；若审计要求尚未满足，重新选 FastAPI 候选，不用不兼容的 Starlette 覆盖安装。
- [x] 候选验证成立后声明改为：

```diff
-fastapi>=0.110,<0.111
+fastapi==0.141.1
```

- [x] 本地 venv 中额外安装的 MCP/sse-starlette 不自动加入应用依赖。先区分它们是否属于本轮后端部署集合；共享环境的冲突不能通过向应用加入无用依赖“修复”。Uvicorn 保持声明约束，确有兼容冲突才提出最小调整。
- [x] 用既有测试验证鉴权和所有权、管理员权限、Pydantic 拒绝路径、上传大小/类型、文件响应以及 SSE 帧顺序和终止。相关文件包括 `backend/tests/test_auth_c_ownership_probes.py`、`test_phase5.py`、`test_stream_exit_law_version_gate.py`、`test_time_unverified_note.py` 和 `test_sse.py`。
- [x] 限流单独检查一次：`backend/tests/conftest.py` 默认自动关闭 limiter，因此普通测试绿不能证明 429 仍有效。需要时新增小范围用例，显式恢复 limiter、使用隔离计数状态与假请求，不访问真实模型。
- [x] 验证安装清单内版本均满足项目声明；候选环境 `pip check` 必须为 0。保存这一环境的解析报告、实际版本和可用于复现的约束快照；不要声称 Windows 环境证实了 Linux 部署兼容。

**验收：** 依赖自洽、相关接口契约不退化，Web 依赖告警改善有当前证据。失败时保留已通过的独立改动，回退候选文件/环境，不修改共享 venv。

## D. 剩余依赖风险与隔离语料

- [x] 对候选 requirements 解析集和候选环境实装集分别运行审计，保留原始 JSON。按漏洞 ID/别名识别重复记录，不机械相加旧报告数量。
- [x] 更新 T7 分案中的过期结论：周末加班已修复；FastAPI 候选已进入执行评估；“升级 Transformers 必然重嵌全库”不能成立为一般规则，需依据实际模型、tokenizer、归一化和向量变化判断。
- [x] LangChain 大版本迁移、Chroma 存储格式迁移及嵌入模型更换只形成单独方案。对每个剩余告警记录组件/版本、触发条件、当前可达性、缓解措施、修复方案、复审日期和接受状态。没有直接 import 不代表传递路径不可达；暂无 fix_versions 不代表永久无修复。
- [x] 助手不自动接受风险或生成忽略名单。存在剩余风险时交给 Owner 审阅具体清单；等待期间继续其余可独立完成的本地工作。
- [x] 校验 `data/laws_extra.candidate-20260925.json` 的哈希、三条条目及已有源证据。只改动文件格式的检查不能替代法律原文/效力日期复核；出现源证据缺口时剔除该条出本次执行范围并报告，不编造内容。
- [x] 从稳定库副本进行 `--validate-only`、`--dry-run`、实际副本导入、同输入重跑和恢复验证。三个数据库变量先指向副本/临时文件，再 import 任何后端模块。每个独立进程均检查变量；禁止直接复制旧命令去掉 `--dry-run` 后指向真实库。
- [x] 预期根据最新 `_seed_conflict` 和副本真实元数据确定：该跳过的 seed 保留、允许替换的版本正确替换、其他版本不被误删、重复运行不新增重复块。旧“删 2 增 3”的读数仅作历史参考，不能强行追数。
- [x] 恢复验证用导入前快照恢复到另一个临时目录并读取目标记录，检查条目和元数据一致；不删除真实数据或将恢复副本覆盖真实目录。

**验收：** 语料副本的写入/幂等/恢复结果可核，真实库指纹无本轮变动；风险清单每项有证据和处置状态。全部跳过不能证明候选成功导入，必须解释每条实际去向。

## E. 固定候选综合验收

- [x] 提交后固定候选提交 SHA、环境清单与代码/测试/依赖文件集，并在无未提交代码修改的候选树复跑 E 的后端静态检查、完整 pytest 与 `pip check`。`backend-full-tests-final-v2.log` 来自未提交工作树，当时未保存完整文件哈希，不能证明最终提交树已通过。候选树不得包含真实 `.env`、个人评测资产或生产库；之后仅改报告不再重复全量测试。

  **2026-09-28 接手会话执行结果**：候选分支 `codex/local-candidate-closeout` 落 4 笔（`ca0eb5e`/`ecdc6b3`/`39f4266`/`fbc29e8`），`HEAD = fbc29e8`，`git status` 无未提交改动；
  该树上复跑九步（日志 `dispatch-output/local-candidate-closeout-20260928/postcommit-gates.log`）：
  `pip check` 0、`ruff check`/`format --check` 0/0、`mypy .` 74 files 0、
  `pytest -m 'not slow' --cov=. --cov-fail-under=70` = **1650 passed / 10 skipped / 18 deselected / cov 85.25%**（211.38s）、
  agent-quality `ruff` 0/0 + `test_budget_guard.py` 9 passed、`pip_audit -r requirements.txt` = **47 条/8 包/扫 132 包** rc=1。
  候选树无真实 `.env`、无 `app.db`；其 `backend/chroma_db` 为 144KB 空桩，非主树 349MB 真实库。
  41 个保护对象重算 size+SHA-256 = **41/41 与 A 基线一致**（`protected-postcommit-check.log`）。
- [x] 后端使用候选解释器，从候选树 `backend/` 运行下列门禁。最终全量测试与静态检查已完成；审计命令因发现漏洞返回 1，不能作为安全通过。

```powershell
$Repo = 'C:\Users\33393\Desktop\ai-legal-helper'
$Candidate = 'C:\Users\33393\.codex\worktrees\local-candidate-closeout\ai-legal-helper'
$CandidatePython = 'C:\Users\33393\AppData\Local\Temp\legal-closeout-20260928\venv\Scripts\python.exe'
$AgentQuality = Join-Path $Repo 'dispatch-output\agent-quality-20260911'
if (-not (Test-Path -LiteralPath $CandidatePython)) { throw '候选解释器缺失；先重建隔离环境' }
if (-not (Test-Path -LiteralPath $AgentQuality)) { throw '质量守卫目录缺失；先查证据索引' }
Set-Location (Join-Path $Candidate 'backend')
$env:JWT_SECRET = 'test-jwt-secret-for-ci-only'
$env:LLM_API_KEY = 'test-key-not-for-real-calls'
$env:LLM_BASE_URL = 'https://test.invalid/v1'
$env:EMBEDDING_PROVIDER = 'local'
$env:RERANK_ENABLED = 'false'
$env:EMBEDDING_QUOTA_TOTAL = '0'
$env:RERANK_QUOTA_TOTAL = '0'
$env:HF_HUB_OFFLINE = '1'
$env:TRANSFORMERS_OFFLINE = '1'
$env:LANGCHAIN_TRACING_V2 = 'false'
$env:LANGSMITH_TRACING = 'false'
$env:COVERAGE_FILE = Join-Path $env:TEMP 'legal-closeout-20260928\candidate-coverage-handoff'
& $CandidatePython -m pip check
& $CandidatePython -m ruff check .
& $CandidatePython -m ruff format --check .
& $CandidatePython -m mypy .
& $CandidatePython -m pytest --cov=. --cov-fail-under=70 -q -m 'not slow'
& $CandidatePython -m ruff check $AgentQuality
& $CandidatePython -m ruff format --check $AgentQuality
& $CandidatePython -m pytest -q (Join-Path $AgentQuality 'test_budget_guard.py')
& $CandidatePython -m pip_audit -r requirements.txt --format json
```

逐条保存退出码；检查链失败不能被最后一条命令的退出码覆盖。`pip-audit` 的漏洞非零单列，不能与扫描器自身失败混淆。

- [x] 前端在候选树 `frontend/` 按现有 `package-lock.json` 用 `npm ci` 安装，运行 `npm run check` 与 `npm run build`。不修改前端依赖来顺手升级项目。
- [ ] 在最终候选环境和稳定 Chroma 副本上运行 `backend/scripts/smoke_citation_fast.py` 一次；先验证真实 rerank 成功响应，记录模型名、调用成功/降级以及 `(法名, 条号)` 结果。只白名单传入 rerank 所需配置，配额和数据库均隔离。
- [ ] 本批固定快速题集应达到 24/24；如因远端不可用而降级，不能计作真实 rerank 通过。先判断网络、候选依赖和数据原因，避免反复付费刷题。

  **仍为未完成（阻塞）**：真实 rerank 的**凭据轮换属 Owner 动作且未完成**，本轮**未调用真实 rerank**，因此
  **没有本阶段的 24/24 新读数**；报告与证件中继续引用历史 23/24，不得改写成本轮现量。轮换完成并告知后按既有授权只重跑一次。
- [x] 不运行会登录本地真实服务并调用生成模型的 `smoke_citation_full.py`。它列入后续发布表：需独立隔离服务、合成账户/会话和生成调用范围，然后才能执行。
- [x] 真实库指纹与 A 对照。发现变化先确认并发写入来源；无法解释时保留证据并暂停涉及数据的验收，不直接恢复覆盖。

**验收：** 技术门禁无失败、coverage ≥70%、环境 `pip check=0`；记录所有 skip/deselect 和平台范围。只在代码/环境再变化或发现未解决问题时补跑受影响检查，不因改报告重复全仓测试。

## F. 提交、文档和阶段判定

- [x] 使用 `git diff --check` 和逐文件差异复核已验证改动。分别提交 PDF、Web 依赖及必要测试，再提交经审阅的报告；两项依赖互相依赖才能合并一笔。精确暂存并检查暂存区，不带入无关产物。
  已完成：`git diff --check` 干净；PDF / Web / 测试捕获 / T7 分开四笔，`requirements.txt` 按差异块分别暂存（先 `git add -p` 只暂存 pypdf 行，再只暂存 fastapi 行）。
- [x] 代码提交只在候选工作区的 `codex/local-candidate-closeout` 上精确暂存；主工作区的两份报告在 `master` 已有未提交修改，先审阅并保留，再在主工作区分别提交经审阅的文档。报告必须写明升级代码仍只在候选分支，不得把分支提交描述成 `master` 已合入。不要把两个工作区的未提交文件相互覆盖，也不要在本轮自行合并分支。`docs/superpowers/plans/2026-09-28-local-candidate-closeout-plan.md` 与本轮证据目录目前未跟踪，若纳入文档提交也要逐项审阅和暂存。

  候选工作区截至本次复核的变更归属：PDF 为 `backend/knowledge_service.py`、`backend/tests/test_pdf_upload.py` 和 `backend/requirements.txt` 的 pypdf 行；Web 为 `backend/main.py`、`backend/tests/test_upload_rate_limit.py` 和同一 requirements 文件的 FastAPI 行；测试捕获修正为 `backend/tests/test_request_bootstrap.py`；T7 分案为 `docs/assistant-briefs/t7-dependency-upgrade-options-20260927.md`。共享的 requirements 文件按差异块暂存，提交前检查 `git diff --cached`。若接手时文件集不同，以实际差异核对归属，不照抄清单暂存。
- [x] 由当前助手统一追加 `docs/progress-handoff-report-20260925.md` 与 `docs/assistant-briefs/next-phase-E-integration-report-20260927.md` 的新阶段记录，保留现有未提交更正与历史测试时点，不批量替换历史 23/24 或旧 HEAD。
  已完成：主报告新增 `§9.12.17`，E 报告新增「十一、本地候选收口（2026-09-28）—— 一页式」；两份报告原有未提交更正**逐字保留**，未改写历史 23/24 与旧 HEAD。master 两笔：`725a207`（两份报告）、`8ae321b`（计划书 + 证据目录 24 文件）。
- [x] 两份报告使用同一来源数据：执行基线、最终代码提交、候选环境版本、命令/退出码、漏洞与接受状态、真实 rerank 条件、隔离语料结果、未提交项归属和后续发布事项。报告引用被测试的代码提交，不要求报告提交“引用自己的最终哈希”。
  已完成：两份报告同源（均引用候选 `fbc29e8` 与同一份 `postcommit-gates.log` 读数）。
- [x] 对其他 worktree 和未跟踪产物只列归属/保留建议；本轮不批量合并、删除或归档。
  已完成：其余 8 个 worktree 只登记；主工作区未跟踪 34107 个（`dispatch-output` 占 33938），未 `git add -A`；
  只暂存本证据目录与本计划。

**最终只能给以下三类结论之一：**

1. **本地候选就绪**：本阶段技术与数据副本验收全部通过，无未处置依赖风险；Git 交接方案明确，发布动作仍单列。
2. **本地候选有条件就绪**：技术与副本验收通过，但仍有 Owner 明确接受的具体本地使用风险。必须附接受范围、日期和发布限制；原始审计仍红就照实写红，不能宣称发布 CI 已绿。
3. **阶段仍未完成/候选受阻**：技术检查失败、环境不可重建、数据结果无法解释，或依赖风险仍未处置/未获接受。列出具体问题和下一项工作，不能仅以“任务都执行过”结账。

## 4. 本地交付之后的发布表

| 事项 | 本轮交付到什么程度 | 后续执行条件 |
|---|---|---|
| 凭据 | 历史暴露面和轮换清单，内容脱敏 | Owner 管理端完成轮换，验证旧凭据失效；轮换不等于抹除历史 |
| Git/远端 CI | 最新历史对账、明确同步/快照方案与 CI 触发条件 | 审阅具体可推内容及历史后再授权 push/PR；不得强推 |
| 真实语料 | 文件证据、隔离导入/恢复与逐条影响 | 对具体真实库、备份、回退和写入批次单独确认 |
| 生成式验收 | 固定脚本与隔离运行设计 | 确认生成服务、调用预算和合成数据范围 |
| 部署 | 当前阶段交接材料 | 选定服务器后另行规划部署、备份和回滚 |

## 5. 对旧建议的复核与资料依据

- PyPI 发布记录确认评估候选存在：[pypdf 发布页](https://pypi.org/project/pypdf/)、[FastAPI 发布页](https://pypi.org/project/fastapi/)。截至本次查阅，页面列出 pypdf 6.19.0、FastAPI 0.141.1；本文使用的 pypdf 6.16.1 是历史最低修复候选，是否仍满足安全要求以执行时审计为准。
- FastAPI 官方建议通过应用测试验证升级，并由 FastAPI 选择兼容 Starlette，而非独立硬钉：[About FastAPI versions](https://fastapi.tiangolo.com/deployment/versions/)。
- 本地依据：`backend/requirements.txt`、`backend/requirements-dev.txt`、`.github/workflows/ci.yml`、`backend/pyproject.toml`、`frontend/package.json`；既有 T7 分案和两份集成报告仅提供历史证据，不覆盖当前代码。
- 本计划初稿未预设“138→47”；现有候选 requirements 审计实际为 47 条/8 包，实装环境为 57 条/10 包。仍不把“升级 Transformers 必须重嵌”“快照 push 自动触发 CI”“新分支没有旧历史”当作已成立的前提。

## 6. 执行记录

Owner 已确认两项升级。候选工作树：`C:\Users\33393\.codex\worktrees\local-candidate-closeout\ai-legal-helper`；独立环境：`C:\Users\33393\AppData\Local\Temp\legal-closeout-20260928\venv`。进展和证据索引见 `dispatch-output/local-candidate-closeout-20260928/README.md`。共享 venv 不变。

wheelhouse 已由助手准备，隔离候选环境已完成离线安装；旧的“等待 wheelhouse”暂停状态已结束。候选代码/测试仍在独立 worktree，未提交、未推送。共享 venv 不变。

**派发/执行口径：** 当前剩余工作只派 A–F 中仍未完成或受阻的项目；第 4 节不派发。

### 当前阻塞与待完成项

1. **凭据安全（Owner 操作）：** 检查本地配置时曾有命令意外将 `.env` 中 rerank 凭据值打印到工具输出。凭据值不写入本计划或仓库文件；请撤销/轮换活动 SiliconFlow key，并确认注释中保留的旧备用 key 已失效或一并撤销。新凭据不要发到聊天。完成后告知，即可按既有授权恢复一次隔离 rerank 验收；轮换前不调用真实 rerank。
2. **依赖风险裁定（Owner 决策）：** requirements 审计仍有 47 条/8 包；独立环境审计为 57 条/10 包（含测试/开发工具）。需基于具体漏洞清单决定后续修复分案或接受范围；助手不得自行忽略或代签。裁定前候选不能标为就绪。
3. ~~**本地收口（执行待办）：** 更新两份进度报告，复核候选精确文件集并做经检查的本地提交。~~ **已于 2026-09-28 完成（接手会话）**：
   候选分支 4 笔（`ca0eb5e`/`ecdc6b3`/`39f4266`/`fbc29e8`，共 7 文件）+ 主工作区 2 笔（`725a207` 报告、`8ae321b` 计划与证据目录）；
   提交后九步门禁在该树上复跑（读数见 §3 E 段）。未 push、未写真实库、未部署。
4. 🚨 **新发现（2026-09-28 实测，非计划内）：本仓库对嵌套分支引用的写入会被外部进程删除。**
   `git commit`/`git update-ref` 写 `refs/heads/<目录>/<名>` 时 git **确实写成功了**（观测到 `.lock` → ref 改名，rc=0，reflog 已落），
   但 **约 113–144 ms（三次实测：122.5 / 113 / 124.5 ms）后该 ref 与其父目录被另一个进程删除**；
   顶层引用不受影响；**手工写同名 ref 文件可长期存活**（已验证 ≥25 分钟）；`git init` 的全新仓库不复现。
   ⇒ 后果是 `codex/...` 分支提交"成功"但指针不落盘，下一次读报 `your current branch ... does not have any commits yet`。
   **本轮应对已在用**：每次提交后按 reflog 回填 ref 文件并验证（命令见 `dispatch-output/local-candidate-closeout-20260928/README.md` 与主报告 §9.12.17(7)）。
   **未定因**（配置干净、无相关钩子、无 `.lock` 残留、无并发 git 进程；最可疑是同机常驻的文件监视类进程）。
   **接手者动 `codex/**` 分支前必须先复核引用仍在**；恢复靠 reflog，提交对象不会丢。

### 2026-09-29 第二次接手会话（本轮执行记录）

Owner 当场裁三题：**① 凭据尚未轮换，本轮不跑真实 rerank；② 先做 B 档运行时探针，再裁依赖风险；③ 候选不合 master，等 D2 有结论。**
⇒ 本轮只做 ②，其余按规划书边界等待。第 0 节"接手后按这个顺序处理"的 ①②③ 上一轮已完成，本轮不重复；④ 的两项阻塞仍在，其中第 2 项**材料已补齐**。

- **B 档探针已交付**（D 节"每个剩余告警记录触发条件/可达性/处置状态"这条的可达性部分，证据等级由静态升到运行时）：
  仪器与驱动 `dispatch-output/local-candidate-closeout-20260928/b_runtime_probe.py` 等 **13 只脚本**
  （`b_*.py` 12 只 + `b-probe-survey.py`；按仓库 ruff 规则集含 `UP` 全 rc=0），判定表由读数现生
  （`python b_probe_matrix.py` → `b-probe-verdict-matrix.md`，末尾新增「公告视角」：**26 条公告 = 有桩可答 17 + 答不上 9**，带闭合检查）。
  两场完整性读数：测试场两腿各 selected **1660** / junit **1660** / failed **0** / rc **0**（171.6s、176.9s）、
  应用路径场两步跑通；"装桩前应用已加载"读数两场均为空（非空即判本场不可用）。
- **判定要点**：Core 反序列化与模板构造 7 只桩两场均 **0 调用**（模块在场，非缺席）；图片 token 计数 **0 调用**；
  模型与 config 加载各 **1 次**，调用方唯一归到 `backend/rag_chain.py:39`，模型名只有常量 `BAAI/bge-base-zh-v1.5`，
  `trust_remote_code` **取值 False**；`langchain_community` / `langchain.chains` / `langsmith.middleware` 两场均**从未被导入**；
  外联为直接读数，且由**全部 206 个键逐条机器归类**得出（`b_probe_net_audit.py`，归类器自带 15 条合成反例
  ＋一条"往真读数副本注入外发"的数据侧对照）：
  测试场连接类 **312 次环回 + 1 次 `test.invalid:443` DNS 解析 + 35 次"键里没有主机字段"**，应用路径场 **0 次**。
  🚨 **本轮新查出一条应用事实（要算进暴露面）**：那 1 次非环回是 `/healthz` 的设计内主动连通探测
  （用例 `tests/test_phase3.py::test_healthz_components`，代码 `backend/main.py:337-342`，
  `socket.create_connection(..., timeout=3)`；假端点解析失败、**连接未建立**）
  ⇒ "运行期 0 调用"**不等于**"这个应用不会 outbound"。
- **读数可复跑、主张可复算、复算器自身可红**：同一版入库代码把测试场跑两遍，22 只桩在判定/计数/干跑数/调用方集合/实参摘要
  五个轴上**零差异**（比对脚本化：`python b_probe_pair_check.py <A> <B>`，junit 从各场 `junit.xml` 现算）；
  `python b_probe_claim_check.py` 把本轮文档里每条数字对着入库读数重算，现量 **61/61 通过**；
  `python b_probe_claim_mutants.py` 对 12 条关键主张各造一只"改期望值"反例，**12/12 被如期打红且红的正是该钉的那条**。
  这台复算器自己红过**三**次，三次都是它自身缺陷（模型名未截 `kw=` 尾巴、`glob` 字符串当 `Path` 用、
  变异件放临时目录跑 ⇒ 12 只全 rc=2「缺入库读数」看着像"全杀掉"），照实记。
  另删掉一条**永远不会红**的主张（`claim(..., True, "人工核对")`）——恒真的"复算"是装饰不是证据。
- **提交前扫密抓出的一次自我污染**：审计事件 `urllib.Request` 的 `args[1]` 就是 HTTP 请求体，
  两份读数各含 44 条带假口令的键。处置：污染读数**从磁盘删除**、仪器改为只记 URL/方法/头**键名**
  （签名对着 `Python311/Lib/urllib/request.py:518` 核过）、补哨兵对照 `b_probe_net_sanity.py`（7/7 PASS），
  随后又把脚本按规则集清了风格 ⇒ **清完复跑全部场**，故上面引用的读数（pytest `103147`/`103511`、app `103841`、
  selfcheck `b-probe-selfcheck.json`）都晚于仪器与驱动的最后一次编辑（该代次关系本身也是复算器的一条主张）。
- **边界与不变项**：`pip-audit` 仍 **47 条 / 8 包**（解析集）与 **57 条 / 10 包**（实装集）红，探针不减漏洞条数、**助手不代签接受范围**；
  这不是不可达证明；18 条 slow 未跑；`CVE-2024-7774` 的包映射疑点不在这把尺子射程内，已在交接书 §8 另立 **D6** 待裁；
  探针答不上的那 **9 条**公告不许被读成"已排除"。
- **本轮仪器自审（17 处缺陷，全部已修，逐条见证据 README G.3；⑬–⑰ 出自独立评审轮）**：其中四处会直接产出假结论——
  分母读错轴把一场有效运行判成无效；装桩时刻太晚造成"同一处加载 1 次、类实例化 0 次"的自相矛盾；
  把打印窗口的前 25 条键当全集得出"连接全是环回"、归类器三种形状朝"更安全"的方向静默漏判（IPv6 四元组 /
   十进制 IP / `os.system` 带 URL）。四处都由闸门、对照、提交前扫描或**独立评审**抓出来，不是靠事后阅读发现的。
   评审轮还收回三处 over-claim 并改写：应用场 G2 是"未测"不是阴性（驱动没 import `llm_registry`）、
   `trust_remote_code=False` 只覆盖 `G3a/G3b`、外联普查未含被开关关掉的**带凭据外呼**
   （rerank `retrieval.py:85-87`→`:168/:184`、LLM 本身、`mcp_server.py:45,51`、`/api/chat/transcribe`；
   本机 `.env` 里 rerank 是开着的）。另记一次自我污染：03:21 无参跑 `verify-protected.py` **覆盖了 09-28 那份证据日志**
   （两份 diff 为空、结论没丢，但"未被覆盖"的说法此前是错的；脚本已加可选 `argv[1]` 输出路径）。
- **真实库零写入的两把读数（本轮各跑两次）**：`verify-protected.py` → **41/41 未变**（09-28 那份留 `protected-postcommit-check.log`，
  本轮 B 档各场跑完后再验一次落 `protected-probe-rerun-check.log`，同为 41/41；脚本已支持 argv 指定输出，避免覆盖上一轮被引用的证据）；
  `find backend/chroma_db -type f -newermt "2026-09-29 00:00"` → **0**（共 38 文件，本轮再量仍是 0）。
- **本轮未做**：未 push、未合并候选、未部署、未调用生成模型与真实 rerank、未运行两个 smoke 脚本、未改共享 venv 与其余 worktree、
  未 `git add -A`；**未改 T7 分案**（该文件由候选分支 `fbc29e8` 持有，在 master 上另改会造出两处真源，留待 D3 合并时一并改）。
- 三态结论仍为 **阶段仍未完成 / 候选受阻**，但阻因由"材料不全"收窄为"**D2 与 D4 两项 Owner 动作未落笔**"。

| 任务 | 状态 | 执行时填入的证据 |
|---|---|---|
| A | 已完成 | 远端/本地差异与保护对象基线见证据目录；最终 41 个保护文件大小、时间戳、SHA-256 均未变化：`protected-after-check.log` |
| B | 依赖安装与针对性兼容验证通过 | pypdf 6.16.1；PDF/DOCX/合同文件相关用例通过；`pip check=0`，见候选测试日志与 `pip-check-final.log` |
| C | 依赖安装与候选兼容门禁通过；安全风险未清零 | FastAPI 0.141.1 / Starlette 1.7.0；完整后端回归通过；requirements 审计有 47 条/8 包，实装环境审计有 57 条/10 包（含测试/开发工具），均未获接受；见 `candidate-requirements-pip-audit.json`、`candidate-installed-pip-audit.json` |
| D | 隔离语料导入、幂等、恢复已验证 | 三条语料去向和 26 组残余通报见证据目录；操作均在副本，不是实际库写入 |
| E | 提交后复验**已完成**；真实 rerank 仍暂缓 | 候选树 `fbc29e8`（无未提交改动）复跑九步：`pip check` 0、`ruff check`/`format` 0/0、`mypy .` 74 files 0、全量 `pytest -m 'not slow' --cov --cov-fail-under=70` = **1650 passed / 10 skipped / 18 deselected / cov 85.25%**（211.38s）、agent-quality `ruff` 0/0 + `test_budget_guard.py` 9 passed、`pip_audit -r requirements.txt` = **47 条/8 包/扫 132 包** rc=1。日志 `postcommit-gates.log`；41 个保护对象 41/41 未变（`protected-postcommit-check.log`）。真实 rerank 未调用（凭据待轮换），故无本阶段 24/24 新读数 |
| F | **本地交接已完成**（三态结论：阶段仍未完成 / 候选受阻） | 候选分支 4 笔 / 7 文件（`ca0eb5e`/`ecdc6b3`/`39f4266`/`fbc29e8`）+ master 2 笔（`725a207` 两份报告、`8ae321b` 计划与证据目录 24 文件）；只暂存本轮证据与本计划，未 `git add -A`、未 push、未部署、未合并分支 |
