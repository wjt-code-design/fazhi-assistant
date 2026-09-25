# 下一阶段本地候选就绪 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `executing-plans` to implement this plan task-by-task; if the Owner later explicitly requests delegated execution, `subagent-driven-development` is an alternative. Use `- [ ]` to track steps and review each task before continuing.

**Goal:** 在不推送、不写真实库、不部署的边界内，把项目整理成可复验的本地交付候选，并明确尚未满足的发布条件。

**Architecture:** 先冻结当前 Git 与工作区事实，在隔离仓库核对真实远端；再对一个小而可追溯的法律语料批次做文件级和隔离库验证；最后对现有安全、版本规则和前后端运行门禁做回归。每张票独立验收，证据不足的优化只登记触发条件，不预先造框架。

**Tech Stack:** Git、PowerShell、Python 3.11、pytest/ruff/mypy、Chroma（仅隔离实例）、Next.js/Vitest。

## Global Constraints

- 本计划的完成边界由 Owner 于 2026-09-25 确认：**全项目下一阶段、本地候选就绪**；顺序为 Git/工作区核对 → 语料候选 → 安全与法律质量缺口 → 综合回归。Git 只读核对不阻塞其他只读工作。
- **不执行** `git push`、force-push、真实 `app.db`/`chroma_db`/配额库写入、容器或服务器部署；开启 Docker 和放开工具权限不等于授权上述动作。服务器尚未选定。
- 旧的 `docs/superpowers/plans/2026-09-22-git-repair-execution-runbook.md` 记录的是已完成的本地 Git 元数据修复，**不得重跑其中的 cutover、移动 `.git`、重写对象、gc/prune 步骤**。本阶段只做远端衔接调查。
- 当前工作区有他人/历史产物：5 个已跟踪的 `dispatch-output/` 文件被改，另有大量未跟踪文件。它们不属于本计划默认提交范围；不 `git add -A`、不清理、不移动、不改冻结评测文件。任何目标文件在执行时若已被他人修改，先停在该票并核对归属。
- 法律原文、效力日期和源侧状态必须逐条有独立来源；格式校验通过不代表法律内容正确。不得把模拟测试、空知识库通过或默认关闭的特性说成真实流量已验收。
- 每次改动先核可复现反例与正例，再做最小修复；同一 bug 连修 3 次仍不过就停下重审判据。相同失败命令先分析，最多原样重试 1 次。
- 每票仅提交经审阅的精确文件；本计划的撰写不等于授权执行或提交。任何外部发布、真实库入库、业务时区选择、法务签字均需单独决定。

## 执行时基线，不是永不过期的断言

2026-09-25 读数：本地 `master` 为 `1d306037971bcaddb6d44fdede377a229719519a`；本地 `origin/master` 为陈旧的 `15562fc9caa4c53ec89280b97d9be7488e064461`；`git ls-remote origin refs/heads/master` 返回 `985d53e4ee81efc066cc6915abcba98954e7d408`。5 个已跟踪修改均在 `dispatch-output/`，未跟踪文件按 `git ls-files --others --exclude-standard | Measure-Object -Line` 计为 34,091；这些数在执行时必须重新采集。现有本地 HEAD 可达对象检查无缺失标记、`git replace -l` 为空；这不证明远端与本地同源，也不等于远端可安全推送。

当前优先参考 `docs/progress-handoff-report-20260925.md` §8、`docs/corpus-time-meta-ticket-20260925.md` §3–5 和本计划。`docs/auth-review-followup-guidance-20260924.md` §8 是较早的非 AUTH 复核快照，其中 R15-2/R15-4 的“未解决”不能覆盖后续提交 `350752d` 与进度报告 §8。所有旧结论均以执行时 HEAD 复量为准。

## Task 1：固定工作区与本地 Git 基线（只读）

**Files:** Read `.git` 状态、`dispatch-output/` 目标差异；只在本计划末尾的执行记录区写核对结果。

- [x] 在仓库根执行以下命令，记录退出码、HEAD、分支、已跟踪改动路径和未跟踪数量；不要把 34,091 当成固定验收值。

```powershell
$Repo = 'C:\Users\33393\Desktop\ai-legal-helper'
Set-Location $Repo
git rev-parse HEAD
git status --short --branch -uno
git diff --name-only
git ls-files --others --exclude-standard | Measure-Object -Line
git worktree list
git replace -l
```

- [x] 核本地可达性：`git -c gc.auto=0 rev-list --objects --missing=print HEAD` 必须退出 0 且没有以 `?` 开头的缺失对象行；不运行 `gc`、`prune`、`reset`、`clean`。若失败，停止后续任何 Git 集成动作，记录原始错误。
- [x] 对 5 个已跟踪修改逐文件看 `git diff -- <path>` 与归属；对未跟踪只按目录/敏感性分类，不逐个批量纳管。若能提出提交候选，给出“来源、用途、是否含凭据/用户数据、是否被哈希冻结、独立测试”五项证据；未达到则继续留在工作区。不要因本计划存在就顺带提交它们。

**完成判据：** 一页基线记录能区分已提交代码、他人改动、运行产物和未知归属；没有任何现存文件被清理或自动暂存。

## Task 2：隔离核对远端历史，形成发布路线（不推送）

**Files:** Read 本地 `master` 与远端 `master`；临时审计仓库创建在系统临时目录，不改本仓 refs/工作树。输出为本计划执行记录中的“远端路线”小节。

- [x] 先重新运行 `git ls-remote origin refs/heads/master`。退出非 0、无返回值或远端 tip 在审计期间变化，都只记录并停止该票，不以陈旧的 `origin/master` 作结论。
- [x] 在全新临时目录做非浅克隆，再只把本地 `master` 抓进审计仓库。若目标目录已存在，不覆盖；重新生成新目录。示例：（执行时另加 `--filter=blob:none`，仍非浅克隆；理由见执行记录 Task 2）

```powershell
$Repo = 'C:\Users\33393\Desktop\ai-legal-helper'
$RemoteUrl = git -C $Repo remote get-url origin
$RemoteLine = git -C $Repo ls-remote origin refs/heads/master
if ($LASTEXITCODE -ne 0 -or -not $RemoteLine) { throw '远端 master 读取失败' }
$RemoteTip = ($RemoteLine -split '\s+')[0]
$Audit = Join-Path ([IO.Path]::GetTempPath()) ('fazhi-remote-audit-' + [guid]::NewGuid().ToString('N'))
git clone --no-checkout --single-branch --branch master $RemoteUrl $Audit
if ($LASTEXITCODE -ne 0) { throw '隔离克隆失败' }
git -C $Audit fetch --no-tags $Repo 'master:refs/remotes/local/master'
if ($LASTEXITCODE -ne 0) { throw '本地 master 导入审计仓库失败' }
$ClonedTip = git -C $Audit rev-parse refs/remotes/origin/master
if ($ClonedTip -ne $RemoteTip) { throw '远端在审计期间变化；重新取基线' }
```

- [x] 在 `$Audit` 内核对 `merge-base`、双向独有提交、树级差异和远端现行 CI 文件。`merge-base` 退出 1 表示没有共同祖先，不是“本地 147 笔都应推上去”。先查看是否同一产品历史、是否有远端独有功能/安全修复，再决定可行整合路线。不得自动合并不相关历史，也不得 `--force`。

```powershell
git -C $Audit merge-base refs/remotes/origin/master refs/remotes/local/master
git -C $Audit rev-list --left-right --count refs/remotes/origin/master...refs/remotes/local/master
git -C $Audit diff --stat refs/remotes/origin/master refs/remotes/local/master
git -C $Audit log --oneline --decorate -12 refs/remotes/origin/master
git -C $Audit log --oneline --decorate -12 refs/remotes/local/master
git -C $Audit ls-tree -r --name-only refs/remotes/origin/master .github/workflows
```

- [x] 给出三选一结论及证据：可快进；有共同祖先但已分叉；无共同祖先/历史重写。若后两者，列出需要 Owner 审核的整合方式和会丢失什么；只准备提议，不建远端分支。远端 CI 触发器以远端实际文件为准，本地 `.github/workflows/ci.yml` 不能代替。

**完成判据：** 有最新远端 SHA、祖先关系、双方独有内容摘要和一条安全发布建议；明确“还不能推”的原因或未来推送条件。临时仓库保留到 Owner 确认审计结论，无需自动删除。

## Task 3：小批量语料候选与隔离验证

**Files:** Read `docs/corpus-time-meta-ticket-20260925.md`、`backend/scripts/import_laws.py`、`backend/law_versions.py`、`data/laws_extra.example.json`；核源后可新增 `data/laws_extra.candidate-20260925.json`，并在原语料数据票记来源及核对结果。不要覆盖仍带占位符的 `data/laws_extra.json`，不要改真实 `backend/chroma_db/`。

- [x] 先核两处尚缺的原始材料：合同法第 428 条原文、法释〔2020〕16 号附件中解释（一）（二）的逐项归属。使用已授权的取数通道及可审计来源；拿不到原文或附件，就分别标为“待核”，不猜日期、不把对应条目放进候选批。源侧 `部分失效`/`尚未生效` 的映射仍待法务，不自动扩表。
- [x] 首批最多三条，核对顺序固定为《民法典》第 1260 条、《劳动争议调解仲裁法》第 27 条，以及**仅在原文核实后**的《合同法》第 428 条；各条都必须有可审计来源、逐条原文、法名/条号和适用日期。前两条的既有取数记录见语料数据票 §4c，但需重核而非直接复制。每条保留来源、检索日期、独立复核方式和原文哈希。现有 `version_metadata` 只贯通 `source_url`、`source_document_sha256`、`reviewed_at` 等键；`source_doc_id`/`retrieved_at`/`status_src` 尚未贯通，不能仅写进 JSON 就声称已入库。字段 F 在 Owner 定义前不扩 schema。
- [x] 若首批已具备上述证据，新增 `data/laws_extra.candidate-20260925.json`，保持现有 `import_laws.py` 接受的 `{"entries":[...]}` 形状，只放通过核对的条文。任何 `已修改`/`已废止` 记录必须有真实、含义明确的 `effective_to`；同法多版或条级不一致的记录留在研究清单，不混入首批。文件里不得含占位文本、密钥或用户数据。这个小批次**不能**证明真实库已覆盖历史同条号多版，R15-3 的真实语料缺口仍需另批解决。
- [x] 仅当候选文件实际生成后，在 `backend/` 运行文件级预检；若文件尚不能生成，记录阻断原因并跳过下列候选文件命令。预检失败时看具体条目，不改生产校验器去迁就有疑问的输入。

```powershell
Set-Location 'C:\Users\33393\Desktop\ai-legal-helper\backend'
$env:PYTHONDONTWRITEBYTECODE = '1'
& .\venv\Scripts\python.exe -B scripts/import_laws.py --input ..\data\laws_extra.candidate-20260925.json --validate-only
& .\venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider tests/test_import_laws_validation.py tests/test_effective_window_roundtrip.py
```

- [x] 候选文件已通过预检后，`--dry-run` 仅在显式设置新的临时 `CHROMA_DIR` 后运行；它可能初始化隔离目录，且空隔离库不证明真实库没有种子冲突。记录隔离路径与预览中的新增/跳过数。真实库预览、真实入库及恢复演练留待单独授权。

```powershell
$env:HF_HUB_OFFLINE = '1'
$env:TRANSFORMERS_OFFLINE = '1'
$env:LLM_API_KEY = 'test-key-not-for-real-calls'
$env:LLM_BASE_URL = 'https://test.invalid/v1'
$env:EMBEDDING_PROVIDER = 'local'
$env:RERANK_ENABLED = 'false'
$env:CHROMA_DIR = Join-Path ([IO.Path]::GetTempPath()) ('fazhi-corpus-preview-' + [guid]::NewGuid().ToString('N'))
& .\venv\Scripts\python.exe -B scripts/import_laws.py --input ..\data\laws_extra.candidate-20260925.json --dry-run
```

**完成判据：** 有一份来源可追溯、无未定映射的最小候选文件且 `--validate-only` 通过，或有逐项说明为何当前**不能**生成可信候选的阻断清单；隔离测试结果注明“合成/隔离”，不称为真实语料验收。若候选无法形成，Task 4/5 仍可继续，但总体结论只能是“本地代码候选就绪，语料待决”。

## Task 4：只处理有证据的安全/法律质量缺口

**Files:** Read `docs/auth-review-followup-guidance-20260924.md`、`docs/progress-handoff-report-20260925.md`、`docs/retrieval-recall-final-plan-20260916.md`、`backend/tests/test_qa_provenance_guard.py`、`backend/tests/test_r15_version_tripwire.py` 及相邻测试；具体代码文件只在新反例成立且 Owner 已定行为时列入单独小票。

- [x] 在当前 HEAD 重新验证已修的 R15-2 多日期与 QA 非法日期，检查两出口和快车道/Agent 相关路径；不照旧报告重复修。复验 AUTH-C 双用户归属、W1 两出口时效校验的现有测试。缺口应写成“输入 → 期望 → 实际 → 生效开关”，不能只写标签。沿用 Task 3 的测试环境约束，定向命令为：

```powershell
Set-Location 'C:\Users\33393\Desktop\ai-legal-helper\backend'
$env:HF_HUB_OFFLINE = '1'
$env:TRANSFORMERS_OFFLINE = '1'
$env:LLM_API_KEY = 'test-key-not-for-real-calls'
$env:LLM_BASE_URL = 'https://test.invalid/v1'
& .\venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider tests/test_r15_version_tripwire.py tests/test_r15a_date_and_segments.py tests/test_fast_path_law_version_gate.py tests/test_qa_provenance_guard.py tests/test_qa_direct_return_version_guard.py tests/test_qa_citation_gate_symmetry.py tests/test_auth_c_ownership_probes.py
```
- [x] E1 事实结论一致性：先取得一个真实业务上**必须阻断**的事实关系样本和“应允许/无法自动判断”对照，才开窄域修复票。没有样本，不构建通用事实推理引擎。
- [x] R15-1 的单个“旧法”词豁免、R15-5 中文数字日期、业务日期本地/UTC 不一致：本阶段记录为启用前验收/Owner 口径项。没有目标路径输入证据或业务时区决定，不扩大词表或全局改钟。Agent/R15 默认开关关闭；测试通过不等于可直接开启。
- [x] W1 两次查库已测得是某些直返路径的结构性成本，但没有真实流量占比和延迟预算。先记录基线需求；只有观测到超预算，才单开“请求内复用”票，并覆盖直连、QA 变化和读库异常。暂不引入跨请求缓存。
- [x] AUTH-B 两个法条 GET 的时间参数继续等真实历史语料及业务日期契约；不以“接口有 cutoff”冒充“历史版本可召回”。若有安全反例在现有默认路径成立，优先于其他优化单独修复和回归。
- [x] 独立法律复核仍是外部验收：`outputs/p5-review-20260917-交付包/` 的交付文件/ZIP 先按 `outputs/p5-review-20260917/_build/交付校验清单.md` 逐项复核 SHA-256 和盲评隔离，再确认复核人是否已有有效回执；私有甲乙映射不得混进交付包或提前透露。无有效回执只记“待外部复核”，不由助手代判法律质量。检索召回沿用 `docs/retrieval-recall-final-plan-20260916.md` 的历史边界；新题集、新语料与旧百分比不可直接比较。

**完成判据：** 对每个开放项给出 `已验证通过 / 有可复现缺陷已开小票 / 等证据或 Owner 决策` 三种之一；本任务不凭猜测改生产行为。确需代码修复时，每个小票写明确文件、失败测试、最小改动、相邻正反例与独立提交，再执行，不把多个规则混在一个补丁中。

## Task 5：综合门禁与候选结论

**Files:** 只读前后端代码与 `.github/workflows/ci.yml`；把执行读数补入本计划执行记录或单独验收报告。测试产生的临时库与覆盖率文件须在隔离位置，不碰真实库。

- [x] 最后一次代码/数据改动之后，先运行与该票相关的定向测试，再按当前 CI 的形状跑后端 lint、format、mypy、非 slow 测试及前端构建；前端单测额外运行。用测试环境变量防真实模型调用；`backend/tests/conftest.py` 会把测试 DB/Chroma 指向进程私有临时位置，但需核对新测试没有绕开它。退出码、通过/失败/skip 和警告分别记录，不以旧报告数字代替新读数。

```powershell
Set-Location 'C:\Users\33393\Desktop\ai-legal-helper\backend'
$env:HF_HUB_OFFLINE = '1'
$env:TRANSFORMERS_OFFLINE = '1'
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:JWT_SECRET = 'test-jwt-secret-for-ci-only'
$env:LLM_API_KEY = 'test-key-not-for-real-calls'
$env:LLM_BASE_URL = 'https://test.invalid/v1'
$env:EMBEDDING_PROVIDER = 'local'
$env:RERANK_ENABLED = 'false'
$env:EMBEDDING_QUOTA_TOTAL = '0'
$env:RERANK_QUOTA_TOTAL = '0'
$env:COVERAGE_FILE = Join-Path ([IO.Path]::GetTempPath()) ('fazhi-coverage-' + [guid]::NewGuid().ToString('N'))
& .\venv\Scripts\ruff.exe check .
& .\venv\Scripts\ruff.exe format --check .
& .\venv\Scripts\mypy.exe .
& .\venv\Scripts\python.exe -B -m pytest -q -m 'not slow' -p no:cacheprovider --cov=. --cov-fail-under=70
Set-Location 'C:\Users\33393\Desktop\ai-legal-helper\frontend'
npm run build
npm run test
```

- [x] 对照 `.github/workflows/ci.yml` 另核其 `dispatch-output/agent-quality-20260911` 的 lint/guard 测试和 `pip-audit`。从 `backend/` 执行下列命令，要求退出 0；若本机无网络或依赖导致安全审计无法完成，记为“未验证”，不以业务测试绿替代。前端原文卡若本阶段未改 UI，不新增页面重做；若改了交互，再做一次受控浏览器复验。

```powershell
& .\venv\Scripts\ruff.exe check ..\dispatch-output\agent-quality-20260911
& .\venv\Scripts\ruff.exe format --check ..\dispatch-output\agent-quality-20260911
& .\venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider ..\dispatch-output\agent-quality-20260911\test_budget_guard.py
& .\venv\Scripts\pip-audit.exe -r requirements.txt
```

- [x] 对拟提交内容逐文件做 `git diff --check` 和 `git diff --cached --check`、敏感内容/大文件/冻结哈希审查和精确暂存；禁止纳入无关 `dispatch-output/`、`outputs/`、`.qoder/`、Caddy 运行态、测试临时目录。只有取得相应票的提交授权，才在测试后按票独立提交；计划文档是否提交也单独征询 Owner。提交后重看 `git status`，把未提交项列为“保留原因”，不强行清零。
- [x] 最终只给三态结论：①本地候选就绪（说明哪些功能/语料仍关闭、独立法律复核是否仍待回执）；②代码就绪但语料/法务/时区或远端衔接待决；③门禁失败，不就绪。结论附当次 HEAD、命令与退出码、候选文件哈希、远端审计 SHA、未提交内容分类和未执行事项。不得将“本地候选”写成“法律质量已获独立背书/可部署/已上线”。

**完成判据：** 当前 HEAD 的相关回归与 CI 同形门禁有可复现记录；失败没有被跳过、空库/默认关闭没有制造假绿；发布阻断项逐项可见。

## 后续优化与审批门（不计入本阶段必做）

| 方向 | 何时重开 | 最小下一步 / 禁止的捷径 |
|---|---|---|
| 远端协作发布 | Task 2 已证明整合路径，Owner 审核准确提交集和 CI 行为 | 新分支/PR 或经核准的整合；重核远端 SHA、扫描将推的精确对象；不 force-push `master` |
| 真实语料入库 | 候选条文与法源/状态映射经法务及 Owner 核准，明确写入窗口 | 先备份并验证恢复、隔离预演，再做真实库前后计数/抽样；Docker 可用不构成授权 |
| QA 直返成本 | 有该路径真实占比及延迟超预算证据 | 仅考虑请求内复用并保留直连护栏；不预建跨请求缓存 |
| E1 / R15-1 / R15-5 | 有目标路径真实反例和独立正反判据 | 一票一缺陷；不造通用语义引擎或无限扩词表 |
| 业务日期与 AUTH-B | Owner 选定业务日时区且历史语料可召回 | 只改日期派生入口/所需 API 契约，测日界；不迁移 UTC 存储或回填旧 QA |
| 归因与评测 | 有可用的受控流量/评测集 | 先冻结题集 hash、绕过缓存取基线，确定性金标核法律事实；不拿归因键存在当效果提升 |
| 检索召回改造 | 新的冻结题集与真实库复量确认既有召回缺口仍严重，且能量化候选方案收益 | 先做离线候选生成对照；不未经评测换 embedding，更不让 LLM 绕开检索直写法条 |

## 自审与执行记录

- **边界：** 这是跨工作包的阶段执行书；尚缺法务/产品契约的子问题只给停机条件，不伪造实现细节。若确需生产代码修改，先为那一张小票写最短可执行改动和测试，不扩大本书为全仓重构。
- **替代方案：** 直接推本地 `master` 或先做全量语料/缓存看似快，但分别绕过远端历史差异、法源缺口和真实成本判据；本计划保留小批次与可验证基线。
- **历史教训：** 不在受损仓库重跑 Git 修复或 gc；不让空库/缓存污染评测；不把脚本输入校验当真实数据验收；不让源状态推断冒充源字段；不在备份未恢复验证前写库。
- **证据：** 文首 SHA、文件数、测试数仅为 2026-09-25 快照，执行时一律重取。每次自称完成都必须能给出命令、退出码、被验证对象和未测范围。
- **代理目标：** `fsck` 绿不证明远端能快进，`--validate-only` 绿不证明法律正确，pytest 绿不证明真语料覆盖，CI 绿不证明默认关闭的功能可上线。

执行者在此追加当次基线、各 Task 结果与阻断项；不要改写上述边界或把“未执行”涂成完成。

---

## 执行记录 2026-09-26（Task 1、Task 2）

执行 shell 为 Git Bash（`BASH_VERSION=5.3.15`），非计划书写的 PowerShell；命令逐条等价改写，所有退出码单独取、不接管道尾程序。纯数字行在本机工具输出里会被吞掉，故所有读数带标签。

### Task 1 基线读数（本次实测）

| 项 | 命令 | 读数 |
|---|---|---|
| HEAD | `git rev-parse HEAD` | `1d306037971bcaddb6d44fdede377a229719519a`，rc=0 |
| 分支 | `git status --short --branch -uno` | `## master`，5 项 ` M` |
| 已跟踪改动 | `git diff --name-only` | 5 个，全在 `dispatch-output/`，rc=0 |
| 未跟踪文件数 | `git ls-files --others --exclude-standard` 再 `wc -l` | 34092（09-25 快照 34091，多 1） |
| 提交数 | `git rev-list --count HEAD` | 147，rc=0 |
| replace refs | `git replace -l` | 空，rc=0 |
| 可达性 | `git -c gc.auto=0 rev-list --objects --missing=print HEAD` | rc=0；`?` 前缀缺失行 0；可达对象 3389 |
| 对象库 | `git count-objects -v` | garbage 0 / size-garbage 0，`.git` 149M（09-20 记的 549MB 垃圾确认已无） |

**完成判据中“本地可达性”通过：rc=0 且无缺失对象标记。** 未运行 `gc`/`prune`/`reset`/`clean`。

`git worktree list` 返回 **9 个工作树**，这是 09-25 基线未记录的新事实：本仓 + `.worktrees/legal-agent-v1`（分支 `codex/legal-agent-v1` @ `8aecf3e`）+ 6 个 `ai-legal-helper-00x`/`-e9b0e17` 分离头指针副本 + `WorkBuddy/Worktrees/.../master-e8826c5b`（分支 `master-e8826c5b` @ `f369094`）。本地分支共 3 条：`master` `1d30603`、`codex/legal-agent-v1` `8aecf3e`、`master-e8826c5b` `f369094`。**本计划未动任何其它工作树或分支。**

### Task 1：5 个已跟踪改动的逐文件归属

前两个是 lint 修复，后三个是纯 EOF 换行，**五项均无证据值变化，也都不是本会话产物，不纳入提交**：

- `dispatch-output/t3-appdb-20260920/assemble_readings.py`（+3/−1）：`datetime.now()` 改为 `datetime.now(tz=utc).astimezone()`。改前改后 `.strftime` 产出的本地墙钟串逐字相同 ⇒ 记录值不变。属 ruff `DTZ` 自动修复形态。
- `dispatch-output/t3-appdb-20260920/probe_t3.py`（+5/−1）：`fromtimestamp(secs)` 同样改为显式 tz 再 `.astimezone()`，输出等价。
- 其余 3 个 JSON（`t4-assets-20260920/classification.json`、`t8-e2-multi-20260920/probe.json`、`te-chroma-isolation-20260918/gate-t11-2a48f3e-20260920-source-sha.json`）各 1/1：`git diff | cat -A` 显示旧侧带 `\ No newline at end of file`，唯一差异是文件末尾补了一个换行 ⇒ `pre-commit` 的 `end-of-file-fixer` 痕迹。`git ls-files --eol` 读数为 `i/lf w/crlf attr/text=auto eol=lf`，工作副本整体 CRLF 而 index 为 LF。

归因辅助：5 个文件 mtime 聚在 `2026-09-21 01:12:19 – 01:13:33` 一个约 74 秒窗口内 ⇒ 形状是**一次批量 lint/format 跑过的遗留**，不是当前有人在编辑。（mtime 按既有纪律只作支持证据，不作结论。）`git diff --check` rc=0，无空白错误。

**这些文件是否被哈希冻结：** `backend/` 全树 grep 这 4 个批次目录名，仅 `backend/tests/test_chroma_isolation.py:4` 以文档链接形式引用 `te-chroma-isolation-20260918/plan-te-chroma-isolation.md`，**没有任何测试按路径或哈希读取上述 5 个文件** ⇒ 补换行不会击穿任何校验器。含密钥/用户数据：5 个文件 diff 内容均为时间戳格式化与 EOF 换行，读数中无凭据形状。

### Task 1：未跟踪内容分类（不逐个纳管）

顶层读数：`dispatch-output/` 33915 + 引号转义路径 112（合计 34027，占 99.8%）；`outputs/` 54；`backend/` 3；`.qoder/` 3；`caddy_data/` + `caddy_config/` 4；`investigate.stdout.txt` 1；`docs/` 1。

- `dispatch-output/` 绝大多数是历次派发批次的运行产物（最大 6 项：`hij-h-20260920` 6238、`hij-j-20260920` 6217、`s6-stream-gate-20260920` 5183、`hij-i-20260920` 4046、`t1-flaky-20260920` 3979、`r15-proposal-20260921` 3797）。**运行产物，保留，不纳管。**
- `outputs/` 54 项含 `p5-review-20260917-交付包/`、`盲评粘贴包/`、`交接话术.md`、`.zip` 与 `.zip.old` —— 这是 Task 4 第 6 条的外部法律复核交付物，含盲评隔离材料。**敏感，禁止入库、禁止转发。**
- `backend/.ptmp-s4-run2/test_scope_clarification_repli0/` 3 个 json 是历次 pytest 失败后残留的 basetemp（Task 5 跑宽套件前需确认它不污染 `test_log_field_whitelist` 的递归扫描；本次读数为 JSON 而非 `.py` 哨兵，风险低但要在 Task 5 复量）。
- `.qoder/better-harness/2026-09-18/` 3 项、`caddy_data`/`caddy_config` 4 项为工具与反代运行态。**均不属于本计划提交范围。**

**Task 1 完成判据达成：** 本页可区分已提交代码 / 他人在途（实为 09-21 批量 lint 遗留）/ 运行产物 / 敏感交付物；执行期间无任何文件被清理、暂存或移动（`git diff --cached` 全程未使用，索引未动）。

### Task 2 远端路线

`git ls-remote origin refs/heads/master` rc=0 → 远端 tip `985d53e4ee81efc066cc6915abcba98954e7d408`，克隆前后各量一次**同值**（审计期间未变化）。本地 `master` = `1d30603`；跟踪 ref `refs/remotes/origin/master` 停在 `15562fc`（2026-08-25），比真远端陈旧 31 天，**不作为任何结论依据**。

审计仓库：`C:/Users/33393/AppData/Local/Temp/fazhi-remote-audit-ca4e8e2a0592458397b0fce63e716e9f`（保留，待 Owner 确认后再处置）。

**对计划书命令的一处偏离，需 Owner 知情：** 克隆加了 `--filter=blob:none`。原因是既有实测记录“远端 tip 的 `--depth=1` 克隆下过 90MB 仍未完成”，而本机 C 盘仅剩 79G，全量克隆有填盘风险。该过滤**不是浅克隆**：提交图完整（`.git/shallow` 不存在，`rev-list --count` = 204），`merge-base`/祖先关系/`--name-status`/`ls-tree` 全部按完整历史计算，只有真正要读的文件内容按需取（本次只取了 1 个 CI blob）。因此下述祖先结论不受影响。

| 判据 | 命令 | 读数 |
|---|---|---|
| 共同祖先 | `git merge-base origin/master local/master` | **rc=1，无共同祖先** |
| 双向独有 | `rev-list --left-right --count` | 204 / 147 |
| 共享 SHA 集合 | 两侧 `rev-list` 求 `comm -12` | common 0 |
| 本地根提交 | `rev-list --max-parents=0` | 唯一 1 个：`5e51384`（2026-09-17 22:05:40） |
| 远端根提交 | 同上 | `901ab60`（2026-07-30 “MVP 初始版本”） |
| 作者 | `log --pretty=%an` | 两侧全部 `wjt-code-design <3339394651@qq.com>` |
| 时间跨度 | `log --date=short` | 远端 07-30 → 09-17；本地 09-17 → 09-25 |
| 树级差异 tip↔tip | `diff --no-renames --name-status` | 348 A、63 M、**0 D**（总 411） |
| 远端独有路径 | `--diff-filter=D --name-only` 单独复量 | **0 条** |
| 反向对照 | 方向反过来数 D | 348（与 A 互为镜像，口径自洽） |
| 接缝 | `diff origin/master 5e51384` | **仅 1 个文件：`backend/tests/conftest.py`** |
| CI 文件 | 两侧 `ci.yml` sha256 | `b6242802af3bbc6f…9431dd` **逐字节相同**，各 64 行 |

**三选一结论：第 3 种 —— 无共同祖先 / 历史被重写。** 且证据把性质说得很具体：本地链是在 2026-09-17 22:05 把远端 tip `985d53e` 的树**整体快照成一棵新根**（唯一改动 `backend/tests/conftest.py`，即本地根提交信息“修复 test_create_candidate_auto_approve 写真实库”那次隔离下沉），之后 8 天 147 笔全部长在这棵新根上。远端链 204 笔从 07-30 MVP 走到同一时刻后停住。两侧同一作者、同一产品、**内容连续而血缘断裂**。

**远端是否有本地没有的东西：当前内容没有，历史版本有——两句要分开说（09-26 独立评审逼出的修正）。**
"远端独有功能/安全修复"这一项仍可排除：tip↔tip 全量比较 D=0，且远端最新提交的树与本地根树只差 1 个文件、
那个文件本地侧是**修复后**版本（`conftest.py` 的 `CHROMA_DIR` 隔离在本地根出现 4 次、远端 tip 只 1 次——方向是我原本写的那个方向，评审 agent 反过来主张的那条我已复测否掉）。
**但"文件内容为零丢失"过头了**：我把远端 204 笔的**全部历史**做了 blob 覆盖，
远端 3346 个 blob 里有 **40 个在本地 `.git` 对象库里根本不存在**，落在 **25 个路径**上
（`backend/settings.py`×3、`agent/runtime.py`×3、`agent/service.py×3`、`main.py`×2、`prompts.py`×2、`pyproject.toml`×2、`llm_errors.py`×2、`gate2_runner.py`×2、`frontend/app/admin/page.tsx` 等）。
再走一步定性：这 40 个 blob **0 个是远端 tip 的版本** ⇒ 丢的不是"现在的文件"，而是**那 25 条路径的中间历史版本**。
唯一的其他持有者实测在 `D:\ai-legal-helper-bundles\2026-09-2{2,3}\dot-git-backup`（两处各 **40/40 全在**）。

**顺带查出的一条结构性事实（09-26，Owner 裁 E4 前该知道）：** 那份 `dot-git-backup` 里有**第三条 master 线**——
根 `76c1eea`（09-17）、tip `6e4a191`（09-22），共 **113 笔**，而这 113 个 commit 对象**本地仓一个都没有**。
它不是"丢了 113 笔活"：`git log --format=%s` 比对显示 **113/113 条 subject 逐字出现在本地那 147 笔里**，
树级文件比对 **only_backup=0 / only_live=14** ⇒ 它是 09-22 那次 cutover **之前**的同一条叙事、换了 SHA，
本地线是它的后继且文件集是它的超集。意义有二：① 上一段那 40 个 blob 为什么在本地缺，到此有了机制解释（重写对象时按新树取物，旧中间版本不再被引用）；
② 任何"按历史 SHA 定位基线"的票面（含下面 E6 的 `b40076b`）都在这次重写里失去了可解析性，**只能靠 subject 反查**。

**为什么现在还不能推：** 无共同祖先 ⇒ `master` 上任何推送都只能是 force-push，代价是盖掉 07-30→09-17 那 204 笔提交，外加上一段那 40 个只在备份里存在的中间版本 —— **当前文件内容零丢失成立，历史版本零丢失不成立**。
远端 `ci.yml` 触发器是 `push: branches [main, master]` 加全体 `pull_request`，所以真推上去会即刻跑 CI，且它跑的形状与本地复量的形状一致（同一 sha256）。

**给 Owner 的三条路线（只提议，未建任何远端分支）：**

1. 推荐 —— **本地链推到新分支并存**（例如 `master-local-20260926`），`master` 与那 204 笔原封不动。非破坏、可回退、能立刻拿远端 CI 的独立读数。代价：远端从此有两条根，`master` 仍是 09-17 旧内容，看代码的人会被误导。
2. **重新接根**（把 `5e51384` graft 到 `985d53e` 后重写）：能得到真快进、204 笔全保住。代价是本地 147 个 SHA 全部改变 —— 而 `docs/progress-handoff-report-20260925.md`、本计划及多份票据里成文引用了 `350752d`、`f2bab45`、`e68a0cf` 等号，重写会让这些指针全部悬空。既有裁定已为此付过一次代价（09-19 那次 graft 使 `0263bd56` 之后每笔换哈希，救援包 tip 从 `88bd167` 变成 `2fdba83`），**不建议**。
3. **暂不衔接**：远端按归档留着，交付走既有救援包路径（`Desktop/fazhi-rescue-*`、`D:\ai-legal-helper-bundles\`）。零风险，代价是远端持续陈旧。

**Task 2 完成判据达成：** 有最新远端 SHA 与审计期不变证明、祖先关系（无共同祖先 + 快照接缝定位到单个文件）、双方独有内容摘要（远端仅独有历史、无独有文件）、一条安全发布建议（路线 1），以及“还不能推”的具体原因（推 `master` 必为 force-push 并毁掉 204 笔）。临时审计仓库按判据要求保留未删。

### Task 3 语料候选（已生成并通过隔离验证）

两处原缺材料**都已核到**，因此候选批成形，走的是"能生成"这一支而不是阻断清单那一支：

- **合同法第 428 条原文已取得**（元典 `?text=428`，`regulation_id` `2457b893a860eb13576a458cffe83d48` 与数据票 §4a 逐位吻合），并逐字列出被废止的 经济合同法 / 涉外经济合同法 / 技术合同法三部 ⇒ §4a 括号那一格从"候选"升级为"原文实测"。
- **法释〔2020〕16 号附件归属已核**：09-25 说"网页正文未列出附件"只对最高法网页成立，元典侧该决定的 `content` 自带完整目录表（`<tr>` 117 行 = 表头 1 + 数据 116，与正文"116件"自洽）。解释（一）= **序号 16**、解释（二）= **序号 17**，均确定在废止清单内 ⇒ 按 §3-B 已裁口径二者 `effective_to` = `2020-12-31`。这两条**没有**进首批（首批被票面钉死为三条）。
- 详细凭证与一处对 §1e.4 的事实更正见 `docs/corpus-time-meta-ticket-20260925.md` §7。

**产出：** `data/laws_extra.candidate-20260925.json`，3 条，4035 字节，形状为 `{"entries":[...]}`，未改 `data/laws_extra.json`（其占位符原样保留），未碰真实 `backend/chroma_db/`。

| 读数 | 值 |
|---|---|
| `--validate-only` | rc=0，`文件校验通过：3 条；未连接知识库` |
| 定向 pytest | `tests/test_import_laws_validation.py` + `tests/test_effective_window_roundtrip.py` = **15 passed**，rc=0，33.97s，1 warning（starlette `multipart` 弃用告警，非本批引入） |
| 隔离 `--dry-run` | rc=0，`将删除 0 旧片段，新增 3 条，跳过 0 条` |
| 隔离 CHROMA_DIR | `C:/Users/33393/AppData/Local/Temp/fazhi-corpus-preview-df2ca840c7c249268578a65ca6960927`（新建，内含 1 个 `chroma.sqlite3`） |
| 候选文件 sha256 | `f32f585259c9a3816f34bab12558caad878185538d90da943f611a83eb3631b1` |
| 密钥/占位符形状扫描 | AKIA、sk-、JWT、PRIVATE KEY、URL 内嵌凭据、generic 赋值密钥、占位文本 —— **七类各 0 命中** |

**"绿"是有对照的绿，不是自证的绿。** 同一把生产校验器 `import_laws.validate_entry` 上跑了 6 条变异，全部被拒且理由正确：`已废止` 缺 `effective_to`、正文换回占位符、`effective_to` 早于 `effective_from`、不存在的日历日 `2021-02-30`、源侧未映射状态 `部分失效`、非 HTTPS 源 URL。⇒ 正例通过不是因为没有牙。

两处仪器自错先记下，免得下一个人当成被测结论：① 我第一版负对照把**条目列表**整个传给了 `validate_entry`，于是六条全部以 `条目必须是对象` "通过"——那是假拒绝，改成传单条 entry 后才是上面那六条理由；② 首轮"还原源侧原样串"的断言我把方向写反（拿 `前缀+存储串` 去等于 `存储串`），报告的 False 其实是断言自己错，逐字符差异定位后确认存储正文相对源侧**只少了前导 U+3000**（428 再少 11 字题注，共 12 字符），正文零改动。

**真实库面未动，是量出来的不是声称的：** `backend/app.db` 与 `data/quota_used.sqlite` 跑前跑后 size / mtime / 首 100 字节 sha256 / SQLite `change_counter` 四项全等（app.db `change_counter=10784`，与另一会话 09-20 独立取过的同值一致），`backend/chroma_db` 文件数 38→38、最大 mtime 未变，且无 `-wal`/`-shm` 残留。前后两份 JSON 读数的 `diff` 非空**只因为**我第二版脚本少写了一个 `version_valid_for` 键，重叠字段逐项相等 —— 这一点要说满，否则就成了拿仪器差异冒充数据差异。

**凭证强度不对称，因此这批只能叫候选：** 1260 条是**双源**（本轮取数 + 数据票 §4c 另一会话取数，141 字**逐字相同**，比对式已跑）；27 条只有第一款有旧记录可校，其余三款单源；428 条整体单源（09-25 明确没取过）。

**两个需要 Owner 知情的判断，都不是技术难题而是口径：**
1. **`title` 用简称**（`民法典`/`合同法`/`劳动争议调解仲裁法`），与 `data/laws.json` 种子及 `SOURCE_ALIAS` 注释"库内 source 存全称（民事诉讼法）"一致 —— 目的是让 `exact_article_lookup` 走**主路径**命中而不依赖 `_source_key` 回退腿。若 Owner 要的是权威全称 `中华人民共和国民法典`，这三条的 `title` 与 `version_id` 都要重算（`version_id` 由 title+条号+生效日派生）。
2. **`source_url` 指向元典智库**（Owner §3-D 已裁的工作源），**不是** Owner 指定的法源站点 `flk.npc.gov.cn`（该站出网仍待放行）。若要求入库溯源 URL 必须是 flk，这三条的 `source_url` 需在放行后重取。

**本批证明不了什么：** 隔离库是**空**的，`跳过 0 条` 只说明"没有和这个空库冲突"，**不**证明真实库里 `民法典 第一千二百六十条` 等三条没有种子或历史版本冲突。R15-3 的"真实语料同条号多版"缺口原样存在，本批不覆盖。真实库预览、真实入库、批次恢复演练**全部未执行**（票面要求单独授权）。`status` 落 `已废止` 用的是"失效 → 已废止"这一有实测支撑的映射；源侧 `部分失效`/`尚未生效` 无实例、待法务，本批不含。

**Task 3 完成判据达成（"能生成"那一支）：** 有一份来源可追溯、无未定映射、通过 `--validate-only` 的最小候选文件；隔离结果全程标注为**合成/隔离**，未称真实语料验收。

### Task 4 缺口逐项复验与三态结论

**定向回归（计划书原命令，7 个文件）：** rc=0，`95 passed, 1 skipped`，19.60s。收集数逐文件为 16 / 26 / 16 / 19 / 5 / 7 / 7 = **96**，与"95 通过 + 1 跳过"相加自洽（不是从通过数反推的）。

那 1 条 skip 我没有留在"合理跳过"就收工 —— 它是 `test_fast_path_law_version_gate.py:446 test_e6_dump_frames_for_zero_change_diff`，只在设了 `FZ_DUMP_FRAMES` 时才跑，而这正是"默认关闭 ⇒ 逐帧零变化"那条腿。补设环境变量单独跑：**1 passed**，rc=0，产出 **8 帧**、帧序列 sha256 `9744dbb78164177f96233669e681ad201c499373dca2e6a3890d73d174da59e4`（默认态 `fast_path_law_version_check is False` 由用例内断言自守，被改过就红）。⇒ 本轮实到 **96 条全部执行**，无一条以 skip 充数。

**已修项在当前 HEAD 复验通过（不是照抄旧报告）：**

- **R15-2 多日期 / 快车道**：`test_independent_expectation_table`（判据取自独立手算表，非自算自证）、`test_every_return_point_passes_the_gate`（出口齐备）、`test_switch_off_leaves_hitting_answer_untouched`、`test_gate_uses_the_single_truth_source_and_not_a_copy`、`test_fast_path_law_as_of_uses_server_today_not_a_constant`、`test_e6_missing_client_date_does_not_degrade_every_answer`、`test_e6_pre_watershed_fact_hits_by_version_rule_not_by_missing_date`。
- **W1 两出口时效**：`test_qa_citation_gate_symmetry.py::test_both_exits_call_the_same_function_object`（钉的是**同一个函数对象**，不是"两处行为像"）、`test_no_exit_keeps_its_own_copy_of_the_lookup_loop`；配 `test_qa_direct_return_version_guard.py` 里三条**对照腿**（同侧仍直返、缺 `law_as_of` 仍直返）与三条**拒绝腿**（无标注被拒、脏 basis 被拒、分水岭前不命中）⇒ 这组同时守住了"不过度拒绝"，不是单边收紧的自我表扬。
- **AUTH-C 双用户归属**：`test_auth_c_ownership_probes.py` 7 条通过。
- 34 条 warning 均为既有第三方弃用告警（starlette `multipart`、httpx `app` 快捷方式、PyJWT 27 字节 HMAC 弱密钥），非本批引入；其中 **HMAC 密钥 27 字节** 是本仓自带弱开发密钥这一**已知弱点**的第二次独立命中（与 09-19 那次同值），属既有事实、不在本阶段修。

**开放项三态结论（按票面要求写成"输入 → 期望 → 实际 → 生效开关"）：**

| 项 | 态 | 依据 / 停在哪 |
|---|---|---|
| E1 事实结论一致性 | **等证据** | 无反例输入 ⇒ 无期望可写。没有"业务上必须阻断"的真实事实关系样本 + "应允许/无法自动判断"对照，不开票、不造通用推理引擎 |
| R15-1 单词豁免、R15-5 中文数字日期 | **等 Owner 口径** | 开关 `LAW_VERSION_TRIPWIRE_CHECK` 默认关；无目标路径输入证据即不扩词表。测绿 ≠ 可开启 |
| 业务日期本地/UTC 两把钟 | **等 Owner 决策** | 输入=跨本地午夜的查询；期望=与写侧 `law_as_of_basis`(UTC) 同钟；实际=`exact_article_lookup` 默认 `date.today()`(本地)；开关=无。分水岭不敏感、对"即将施行"是真差一天 |
| W1 两次查库成本 | **等观测基线** | 无真实流量占比与延迟预算 ⇒ 不建"请求内复用"票，不引跨请求缓存 |
| AUTH-B 法条 GET 时间参数 | **等语料 + 契约** | 候选批仍未入库；接口有 `cutoff` 不等于历史版本可召回 |
| 独立法律复核 | **仍待外部复核**（见下） | 交付包完整性可核，回执有效性不成立 |

**独立法律复核这一格是本轮最需要注意的一处 —— 有一件"看起来已完成"的东西不能算数：**

- 交付包完整性：`p5-review-20260917-交付包.zip` sha256 = `d8b04ad4c3e45376f896da6fc7cabc2ee53e5f5c07569073d465cf607d14ebf5`，**与清单逐字符相同**；大小 21103 B ✓、成员数 5 ✓。清单登记了哈希的 3 个文件（`01`/`02`/`03`）字节数与 sha256 **逐项全等**。
- ⚠️ **清单本身不完备**：5 个成员里 `00-作业说明-给复核助手.md`(6166 B) 与 `04-交付清单与覆盖说明.md`(2733 B) **在清单中没有基线哈希** ⇒ 票面要求的"逐项复核 SHA-256"客观上只能覆盖 **3/5**。这不是我少做了，是清单少记了；补齐要动 `_build/`（未跟踪的构建侧），留待 Owner。
- 盲评隔离：`p5-private/` 的 `mapping.json`、`extraction-manifest.json`、`validation.json` **确认未进包** ✓。包内出现"甲/乙"标签**不是泄漏** —— 已填卷第 8 行「版本甲 / 乙为**随机编号**，不代表优劣或来源；编号与来源的对应关系不在本文件内，也不会提供」、第 75 行「不同案例里的"甲"不代表同一来源」、第 76 行「对应关系**不在本包内**，也不会提供。**请勿尝试推测**来源」；标签本来就是发给复核人的作答轴。
- ⚠️ 我第一版用"任意 ≥2 字符私有串"做的探针在 `01-第一阶段` 里命中 2 个 31/40 字符长串，**性质我判不了**：分类必须读 restricted mapping 的取值，而权限层正确拦下了那次读取（判为触碰盲评私密记录）。⇒ 这一格**留给持有 `mapping.json` 的协调人复跑同一探针**，命令形状：把 `mapping.json` 递归取出的字符串与交付目录 5 个文件做子串匹配，只看命中的**键路径**不看值。我不把它涂成"已通过"，也不涂成"已泄漏"。
- **回执有效性不成立：** 唯一填妥的复核作业 `outputs/法律咨询回答复核作业-已填-20260918.md`(100059 B) 抬头与回执 JSON 双处署名 `法律合规专家（WorkBuddy AI）`、`frozen_at 2026-09-18T00:25:00+08:00`。**复核人是 AI**。三方对照确认该字段本应留空：交付包 `03-匿名回执模板.json` 为 `"reviewer": ""`、空白卷 `最终版` 为 `复核人：________`。⇒ 这是"生成方自己当自己的独立复核方"的形状，正是票面禁止由助手代判法律质量的那一类。**独立法律背书 = 未取得**，该文件不得被引用为"外部复核已回"。
- 附带打掉我自己一处误读：我一度记"该文件还剩 2 处 `待填写` 未填"，`grep -n` 复量后确认那两处在第 48 / 1010 行的**指令文字**里（"只替换 `待填写` 与空字符串"），不是未填槽位。已填文件其实填满了。

**Task 4 完成判据达成：** 每个开放项落到三态之一，没有一条凭猜测改生产行为；本轮**未新增**代码修复票（无成立反例），因此也不存在"多个规则混一个补丁"的风险。

### Task 5 综合门禁读数（全部在本轮最后一次代码/数据改动之后跑）

每条命令**单独取退出码**、绝对路径、不接管道尾程序（`| tail` 之后 `$?` 是 tail 的）；`-p no:cacheprovider` 全程带。

| CI 同步的步骤 | 命令（工作目录） | 退出码 | 读数 |
|---|---|---|---|
| 后端 lint | `ruff check .`（backend） | **0** | All checks passed |
| 后端格式 | `ruff format --check .` | **0** | `261 files already formatted` |
| 后端类型 | `mypy .` | **0** | `Success: no issues found in 73 source files`；另 2 条 note：`main.py:1968/2149` 未标注函数体默认不检 ⇒ 是盲区不是通过 |
| 后端测试+覆盖率 | `pytest -q -m 'not slow' --cov=. --cov-fail-under=70` | **0** | **1544 passed / 2 skipped / 18 deselected**，185 warnings，207.40s；覆盖率 **84.47%**（门槛 70）；TOTAL 8427 stmts |
| 同上复跑（无 cov，带 `-rs`） | 同范围重跑一次 | **0** | **1544 / 2 / 18 完全相同**，169.45s ⇒ 两次独立复量一致，不是单轮运气 |
| dispatch-output lint | `ruff check ../dispatch-output/agent-quality-20260911` | **0** | All checks passed |
| 同上格式 | `ruff format --check …` | **0** | 4 files already formatted |
| 同上守卫测试 | `pytest …/test_budget_guard.py` | **0** | 9 passed |
| **依赖安全审计** | `pip-audit -r requirements.txt` | **1** | `Found 138 known vulnerabilities in 10 packages`（工具原文；**138 是行数**，按公告 ID 去重 = **80 个不同 ID**，同一 ID 因多个可选修复版本重复成行） |
| 前端构建 | `npm run build`（frontend） | **0** | 7 静态页、5 路由全部产出 |
| 前端单测（计划额外要求） | `npm run test` = `vitest run` | **0** | **7 test files / 54 tests passed**，1.48s |
| 空白/暂存卫生 | `git diff --check` / `git diff --cached --check` | 0 / 0 | 无空白错误；**索引里 0 个文件**（本轮从未 `git add`） |

**那 2 条 skip 我逐条点名并跑掉了，没有拿"合理跳过"糊过去。** 两条同型，都是"改前/改后逐帧比对"的采集口，平时 skip 以免给套件加时长：

- `test_fast_path_law_version_gate.py::test_e6_dump_frames_for_zero_change_diff` → 补 `FZ_DUMP_FRAMES` 单独跑 **1 passed**，默认态 **8 帧**、sha256 `9744dbb78164177f96233669e681ad201c499373dca2e6a3890d73d174da59e4`。
- `test_stream_exit_law_version_gate.py::test_dump_stream_frames_for_zero_change_diff` → 补 `S6_DUMP_FRAMES` 单独跑 **1 passed**，**4 个样本**（`stream_join` / `fallback_invoke_llm` / `no_baseline_date_sent` / `neutral_answer`），聚合 sha256 `a44e7539e8ff130d5d8c61a5b1e281a3008bb44145e57cd5f777c801ca830c9e`。
  ⚠️ 两条用例的 docstring 自己写明：**"改前侧要在 `b40076b` 副本树里跑、改后侧在 live 树里跑，两份 sha256 必须相同"**。本轮只产出了 **live 侧一份**基线 ⇒ 这只证明"采集口是活的、默认态可复现"，**不**构成"零变化已证"。要证零变化得补对侧 —— 那是票 C 的验收，不在本计划范围，已列为未执行事项。
  ⚠️ **该指针现已失效（09-26 评审复测）**：`git cat-file -t b40076b` 在本仓与远端克隆均 fatal；subject 反查得到本仓等价提交 `c25fbd6`，两者 **tree 同为 `cfa6cab27d236b9bff932ce0e6b881d0b0c89932`**（同一份内容的两个 SHA，09-22 cutover 换写所致）。也就是说 `gate_exit_registry.py:549/553` 与 `tests/test_stream_exit_law_version_gate.py:471` 里那三处引用中，**至少测试 docstring 那处是按字面可执行的指令**（"在 `b40076b` 副本树里跑"），今天照抄会直接失败 —— 见文末补丁清单 T4。

**真实库面全程未动（收口复量）：** 所有套件跑完后，`backend/app.db` 与 `data/quota_used.sqlite` 的 size / mtime / 首 100 字节 sha256 / SQLite `change_counter` 与 Task 3 跑前读数**逐项相等**（`change_counter` 前后都是 **10784**，跨约 40 分钟、两轮 1544 用例），`backend/chroma_db` 文件数 38→38、最大 mtime 未变，无 `-wal`/`-shm` 残留。`conftest.py:23/32/40` 对 `QUOTA_DB`/`DATABASE_URL`/`CHROMA_DIR` 是**无条件赋值**（不是 `setdefault`），所以进程私有临时库这条隔离通道经核对确实生效、未被本轮任何用例绕开（本轮未新增测试文件）。

### 本轮需要记在案上的仪器自错（三次，都是我看错，不是被测对象红）

1. **`npm run test` 我一度判成"脚本不存在"**：用 `node -e` 打印 `package.json.scripts` 只回显了 `dev`/`build` 两项，据此写下"计划假设了一个不存在的 test 脚本"。`npm run test` 实跑 rc=0 并打出 `> vitest run`，直接 `grep '"scripts"'` 复量确认 `test`/`test:cov`/`check` 三项**都在**。⇒ 结论已撤回。**教训**：读结构化文件别经"我自己再写一个打印器"这一手，直接 grep 原文。
2. **负对照传错参数类型**（Task 3）：把条目列表整体传给 `validate_entry`，六条变异全部以 `条目必须是对象` 假装"被拒"。改传单条后才拿到真实拒绝理由。
3. **仓库级 `glob('**/frozen-hashes.json')` 递归扫全盘超时**（34k 未跟踪文件 + venv）被移到后台。改用索引化检索工具即得。同轮 `laws_extra` 引用面复量：**除我自己写的两处文档外，无任何代码或清单按路径/哈希引用候选文件** ⇒ "未被哈希冻结"这一格现在是复量过的，不是推断。

### 与 CI 的等价性缺口（不许把"本地全绿"说成"CI 会过"）

- **`pip-audit` 红就是 CI 红**：Task 5 明列该步“要求退出 0”，实测 rc=1。**计数口径先说清**：138 = 审计表**行数**，按公告 ID 去重是 **80 个不同 ID**，跨 10 个包；每包去重后为 pypdf 41 / starlette 7 / langchain-core 6 / langchain-community 6 / langchain 6 / transformers 5 / langsmith 4 / langchain-text-splitters 2 / chromadb 2 / langchain-openai 1（41+7+6+6+6+5+4+2+2+1=80，两轴别混用）。**本轮零改动与此无关** —— 是公开漏洞库的累积。多数编号为 2026 年新发 ⇒ **推断**远端 CI 今天对任何人都是红的；但**未验证**（看远端 Actions 要 `gh`/GitHub API，本机 `gh` 不存在、`api.github.com` 实测 `code=000` 不可达）。
- **前端依赖安装步骤未复现**：CI 走 `npm ci`（按 lockfile 全新安装），我在既有 `node_modules` 上直接 `npm run build`。⇒ 构建绿灯不覆盖"lockfile 与实际安装树是否一致"这一面。
- CI 的 frontend job 本身**不跑单测**（只有 `npm ci` + `npm run build`），上面的 54 passed 是本计划额外要求的读数，不是 CI 门禁项。
- 网络面：`pypi.org/simple` 实测 200、`api.osv.dev` 实测 405（可达、需 POST）⇒ pip-audit 的 rc=1 是**审完得出的结论**，不是"跑不动所以记未验证"。这条区别要说清，否则就成了用环境借口掩盖失败。
- 工作副本 CRLF 噪声这次没有制造假象：`ruff format --check` 本地即 rc=0，而 09-25 已知的偏差方向是"本地比 CI 多报"，所以本地干净 ⇒ CI 侧也干净，这个推断方向是成立的。

### 最终三态结论

**按票面严格读法：③ 不就绪 —— 但失败面窄且单一。** 唯一未过的**门禁**项是 `pip-audit`（rc=1，138 行命中 = 80 个不同公告 ID / 10 包），它是 Task 5 明确要求退出 0 的一项，因此**不能**声明"本地候选就绪"或"CI 同形门禁全绿"。（⚠️ 09-26 评审补：门禁面确实只有这一条红，但**发布阻塞**另有 H-1 —— 它不体现在任何门禁里，见文末 §独立评审。）

**业务代码面是 ② 的形状**：lint / format / mypy / 1544 条测试 / 84.47% 覆盖率 / dispatch-output 三项 / 前端构建与单测 **全部 rc=0**，且 1544/2/18 在两次独立复跑中逐字相同。

所以准确的表述是：**代码门禁就绪；依赖安全门禁红；语料、法务、时区、远端衔接四项待决。**

附当次锚点（全部为 2026-09-26 现量，非引用旧数）：

| 锚点 | 值 |
|---|---|
| HEAD | `1d306037971bcaddb6d44fdede377a229719519a` |
| 远端 `master` tip（审计前后各一次） | `985d53e4ee81efc066cc6915abcba98954e7d408` |
| 远端审计仓库 | `C:/Users/33393/AppData/Local/Temp/fazhi-remote-audit-ca4e8e2a0592458397b0fce63e716e9f`（保留待 Owner 确认） |
| 祖先关系 | `merge-base` rc=1，common SHA 0，204 远端独有 / 147 本地独有 |
| 候选文件 sha256 | `f32f585259c9a3816f34bab12558caad878185538d90da943f611a83eb3631b1`（4035 字节，3 条） |
| 本轮执行读数 | 后端 1544 passed / 2 skipped / 18 deselected，cov 84.47%；守卫 9 passed；前端 54 passed |
| 未过项 | `pip-audit` rc=1（138 行 = 80 个不同公告 ID / 10 包）；**已有一份 09-07 Owner 批准的风险接受待复审**，见 E3 归因 |
| 工作区 | 已跟踪改动 6 个 = 5 个 09-21 批量 lint 遗留（非本轮）+ 1 个本轮 `docs/corpus-time-meta-ticket-20260925.md`；未跟踪 34093（本轮 +1 个候选 json）；**索引内 0 个暂存文件** |

**未提交任何内容。** 本轮改动全部留在工作区：1 个新数据文件 + 1 个跟踪文档的 §7 追加 + 本计划（未被 git 跟踪）的执行记录。**⚠️ 顺带一条风险：本计划文件自身 `git ls-files --error-unmatch` 报未跟踪** —— 它现在承载着全部执行记录与远端审计结论，一次 `git checkout -- .` 或全新克隆就会丢掉。是否入库需 Owner 单独裁定（票面第 3 条明写"计划文档是否提交也单独征询 Owner"）。

**本轮明确未做的事（不留模糊空间）：** 未 `git add`、未 commit、未 push、未建远端分支；未对真实 `app.db`/`chroma_db`/配额库**做任何写**（`change_counter=10784`、chroma 38 文件、mtime 仍 09-21 已复量）。
⚠️ **09-26 评审复测把"未读写真实库"这半句作废了**：为验 H-1，我**读**了真实 `chroma_db` 的元数据，并取了**整目录副本**在副本上做 dry-run 与"实跑导入 + 删旧块"的 A/B（三份临时副本在 `%TEMP%\fazhi-chroma-*`，均可 7 秒重建，未动原件）。
未做真实入库（真实库那份仍是 10266 条）；未做恢复演练；未改生产校验器（含 `clean_law_text.py` 的标记缺口只记录不修）；未代判法律质量；未处置 `pip-audit` 命中的依赖（升降级属需授权动作）；对侧逐帧基线未取（指针见 E6）。
**"未开代码修复小票（无成立反例）"这一条现已不成立** —— H-1 是一个成立反例，补丁清单见文末，票尚未开。

### 本轮新增待裁项（E1-E7，含推荐与回退）

E1-E6 均已按推荐值执行到"可回退"的位置，未越界落地；**E7 是评审后新增、未执行任何动作**，只需一句话定向。Owner 一句话即可翻案。

| # | 待决 | 推荐（已按此做） | 翻案代价 / 回退 |
|---|---|---|---|
| E1 | 候选批 `title` 用简称还是权威全称 | 简称（`民法典`/`合同法`/`劳动争议调解仲裁法`）：与 `data/laws.json` 种子及 `SOURCE_ALIAS` 注释"库内 source 存全称（民事诉讼法）"同形，使 `exact_article_lookup` 走主路径而非 `_source_key` 回退腿 | 换全称要重算 3 条 `version_id`（由 title+条号+生效日派生）并重跑 `--validate-only`；未入库，删掉重写即可 |
| E2 | `source_url` 存元典还是 flk | 元典（§3-D 已裁工作源，本轮实测可用） | 若须 flk：`flk.npc.gov.cn` 出网仍待放行，放行后只重取 3 条 URL，其余字段不动 |
| E3 | `pip-audit` rc=1 怎么处置 | **不用新开治理票**：已存在 09-07 Owner 批准的 Risk Accepted （`release-evidence/legal-agent-v1-grayscale-20260907/r8-disposition-20260907.json`），其到期条款是“90 天**或 Agent 下一候选周期**，先到为准”⇒ **本轮就是这个触发点**，动作应是**复跑并重新签署**，不是另开票。归因见下方“E3 归因”小节。⚠️ **09-26 开票时改口**：**"复跑"不等于"跑那个生成器"** —— `gen_r8_disposition.py` 把 `APPROVED` 与日期写死了，跑它会覆盖已签原件并铸出一份无批准的"已批准"件 ⇒ 见新增 **T6** 与上文补丁清单段落 | 回退成本 0（未改依赖）。若 Owner 认为“下一候选周期”不指本轮，则该接受书按条款**已过期待补签** |
| E4 | 远端衔接走哪条路线 | 路线 1：本地链推**新分支并存**，`master` 与那 204 笔不动 | 需授权 + 定分支名；路线 2（重接根）使 147 个 SHA 全变、文档引用悬空，**不建议**；路线 3（暂不衔接）零风险但远端持续陈旧 |
| E5 | 本计划文件是否入库 | 建议入库：它带执行记录与远端审计结论，未跟踪等于可被一次 `git checkout -- .` 抹掉 | 维持未跟踪则须把执行记录另抄进一份已跟踪文件，否则下代会话拿不到 |
| E6 | 逐帧"零变化"要不要补对侧 | 建议补，但**指针要换**：`b40076b` 在本仓和远端克隆都**不是有效对象**（`cat-file -t` fatal）；按 subject 反查到本仓同一提交 `c25fbd6`（2026-09-20，同 subject，**tree 逐字相同 `cfa6cab2…`**）⇒ 对侧基线改用它即可在本仓内做，不需外部备份 | 属票 C 验收面；不补则这条只能停在"默认态基线可复现"，不得写成"零变化已证"。⚠️ 照原句写 `b40076b` 必失败（评审 agent 指出，已复核） |
| E7 | 现网 10266 条"无日期 `upload` 旧块"要不要批量处置（09-26 评审后新增） | **先只修 T1/T2 止血**（新导入不再制造双胞胎），存量处置**建议另立数据治理票**并排在独立法律复核回来之后：给整法碎片补 `effective_from/promulgated_at` 需要逐部法查公布/施行日，属法务密集题，不该由助手批量代判 | 不动存量 ⇒ H-1 的"历史查询仍命中后施行法"这个失真面**继续存在**（今日实测 `cutoff=2020-06-01` 仍返回民法典 1260）；动存量 ⇒ 一次影响 10266 条、需备份+恢复演练（当前"不动库"边界未撤）。回退成本：T1/T2 只做增量拦截，可单独回滚代码 |

**另两条只登记、不需 Owner 动作：** ① `p5-private/mapping.json` 取值与交付文的子串碰撞，只有持 restricted 记录的协调人能判（权限层会拦助手读，本轮即被拦、未绕）；② `_build/交付校验清单.md` 缺 `00`/`04` 两个成员的基线哈希，补齐要动未跟踪的构建侧。

### E3 归因：`pip-audit` 红并不是一个"新发现"，而是一份**到期该重签的风险接受书**

本轮先查有没有真源，再决定要不要分析 —— 结果是有：
`release-evidence/legal-agent-v1-grayscale-20260907/r8-disposition-20260907.json`（schema `phase9-r8-disposition/v1`，
原始扫描同目录 `r8-audit-20260907.json`，生成器 `backend/scripts/gen_r8_disposition.py`，随本地根提交 `5e51384` 入库）。
其 `owner_approval` = **APPROVED**、批准人 = 数据所有者（项目 owner）、批准日 2026-09-07、
`total_vulns=82`、`packages_affected=10`，处置 = `risk_accept_required: pypdf（41）/ starlette（9）`。

**到期条款被本轮触发**：`risk_accept_form.expiry` 原文是"**90 天** 或 **Agent 下一候选周期**（以先到为准）复审"。
90 天那把钟要到 2026-12-06；而本计划的定位就是"本地交付候选"⇒ **后先到者已经到**。
所以正确动作是**复跑 + 重新签署**，不是我原先建议的"另开一张治理票"。下面就是这次复审的读数。

**① 覆盖面：同一批包、同一批解析版本。** 逐包比对 09-07 与本轮（按公告 ID 去重，不用行数）：

| 包 | 09-07 → 本轮（版本未变） | ID 数 09-07 → 本轮 | 新增 / 撤销 |
|---|---|---|---|
| pypdf | 5.9.0 → 5.9.0 | 41 → 41 | +5 / −5 |
| starlette | 0.37.2 → 0.37.2 | 7 → 7 | 0 / 0 |
| langchain-core | 0.1.53 → 0.1.53 | 6 → 6 | 0 / 0 |
| langchain-community | 0.0.38 → 0.0.38 | 4 → 6 | +2 / 0 |
| langchain | 0.1.20 → 0.1.20 | 6 → 6 | 0 / 0 |
| transformers | 4.57.6 → 4.57.6 | 5 → 5 | +1 / −1 |
| langsmith | 0.1.147 → 0.1.147 | 3 → 4 | +2 / −1 |
| langchain-text-splitters | 0.0.2 → 0.0.2 | 2 → 2 | 0 / 0 |
| chromadb | 0.4.24 → 0.4.24 | 2 → 2 | +2 / −2（同数换号） |
| langchain-openai | 0.1.7 → 0.1.7 | 1 → 1 | 0 / 0 |
| 合计 | 10 包，**无一例版本漂移** | **77 → 80** | 净 +3 |

⇒ 结论：**09-07 的受理范围到今天仍然完整覆盖**（10 包同集合、解析版本逐字相同），变动只是公告库的进出，
不是"冒出了一批没被审过的东西"。

**② "修不了"这句话本轮复核成立，且是结构性的**：`requirements.txt` 是**区间锁**，而最低可用修复版本普遍越界 ——
pypdf 修复要 **6.0.0**，本仓钉 `>=4.0,<6.0`（**上限就是墙**）；langchain 系修复要 0.2/0.3/1.x，钉 `>=0.1,<0.2`；
`starlette` / `transformers` / `langsmith` / `langchain-text-splitters` 都是**传递依赖**，不在本仓直接钉里。
⇒ 摘掉最大那块（pypdf 41/80 = 一半）**只需要放宽 pypdf 上限**，且本仓 pypdf 只有 **1 个调用点**
（`knowledge_service.parse_uploaded`）；其余都要破坏性大版本升级 + 独立回归周期。这正是 09-07 给的受理理由，本轮复核仍成立。

**③ 缓解措施逐条回到代码里核（没有照抄旧结论）**：

- pypdf **仅文本提取**：`knowledge_service.py:108-111` 只有 `PdfReader(...)` + `page.extract_text()`，不渲染、不执行、不取附件 ✓
- **10MB 上限**：`knowledge_service.py:28 _MAX_UPLOAD_BYTES = 10 * 1024 * 1024`，:71-72 强制 ✓
- ⚠️ **一处比 09-07 变好了**：`knowledge_service.py:85` 现有**解压炸弹防护**（注释点名"raw 10MB 上限只限压缩体积"），
  是受理书之后才加的 ⇒ 补偿控制强度**高于**当初签署时。
- **langchain 漏洞相关能力未启用**：全仓 `backend/**/*.py` 扫 `SitemapLoader / GraphCypherQAChain / WebBaseLoader /
  CSVLoader / PyPDFLoader / RecallLoader / unstructured`，**生产码零命中**（唯一命中在受理书生成脚本自己的字符串里）✓
- **chromadb 无监听面**：compose 无独立 chroma 服务，只有 `./backend/chroma_db` 挂进后端容器（compose:47），
  `rag_chain.py:123` 走 `persist_directory` 嵌入式 ⇒ 进程内访问 ✓
- **uvicorn 是对外 ASGI 入口**：`backend/Dockerfile:72 CMD uvicorn main:app --host 0.0.0.0 --port 8000`（Caddy 反代在前）。
  uvicorn 本轮 **0 条命中**，所以它只是下面那条漂移的放大器，不是漏洞项。

**④ 本轮新查出来的一条（与漏洞无关，但影响"绿"的可信范围）**：本机 venv 有 **2 个包违反自己的区间锁** ——

| 包 | 本机装着 | `requirements.txt` 钉的 |
|---|---|---|
| uvicorn | **0.52.1** | `>=0.27,<0.28` |
| pypdf | **6.14.2** | `>=4.0,<6.0` |

其余 19 个在锁内。**且 `requirements-dev.txt:1` 就是 `-r requirements.txt`、`backend/Dockerfile:45` 也装同一份** ⇒
CI 与生产镜像拿到的是 uvicorn 0.27.x / pypdf 5.9.0，**都不是本机这套**。两个后果要分开说：

1. 本轮那份 1544 passed / mypy / ruff / 前端构建的绿灯，是在**发布物不会构建出的依赖集**上取得的
   ⇒ 这是 Task 5"CI 等价性"里比 `npm ci` 更硬的一条缺口（已补入下方清单）。
2. 反向看，pypdf 本机 6.14.2 大概率**已修掉**审计点名的那批（审计按 5.9.0 报）⇒
   **本机测 pdf 路径通过，不代表生产的 5.9.0 通过**。这不是把风险说小，而是说本机读数对 pypdf 面**没有代表性**。

**⑤ 因此对 `pip-audit` rc=1 的处置建议（改口）**：**不新开治理票**，改为
"按原 schema 复跑生成一次 `r8-disposition-2026xxxx.json` 并重新签署到期条款"。
要 Owner 拍的只有两件：**(a) 确认本轮算不算那个"下一候选周期"**（算 ⇒ 补签即可；不算 ⇒ 受理书已逾期，需要补签动作）；
**(b) 要不要单独放宽 `pypdf` 上限** —— 这是唯一一处性价比明确的小改动（1 个调用点 + 41/80 个 ID 的降幅），
但它仍要过一遍上传/合同评估回归，且属改依赖，我不动。

**补入 Task 5 等价性缺口的两条**：
- 本机依赖集 ≠ CI/镜像依赖集（uvicorn、pypdf 越锁），所以"业务门禁全绿"只在**本机树**意义上成立。
- `pip-audit` 的 rc=1 有**在册的 Owner 批准风险接受**（2026-09-07，条款到期触发于本轮）⇒ 它是"待重签"，
  不是"未知缺陷"。三态结论的措辞相应保持"不就绪"（该步确实没到退出 0），但**不得**把它写成"发现 138 个新漏洞"。

---

## bug-review（2026-09-26 自审）：本轮产出的缺陷清单与订正

被审对象 = 本轮全部产出：**1 个 JSON 数据文件、2 份 Markdown 记录、2 条记忆、0 处生产代码改动**。
宿主语言 Python 3.11（`pyproject.toml target-version=py311`）+ TypeScript/Next.js 14。静态面复跑：
`ruff check` rc=0、`ruff format --check` rc=0、`mypy .` rc=0、校验器正例 3/3 + 负例 6/6、谓词实跑 4 个 cutoff。

### D1 — Medium｜我把"CI 作用面"当成"项目作用面"写了（口径缺陷）

实测出来的真实作用面（三条互相印证的数）：

- `pyproject.toml:60` mypy `exclude = ["(?x)^(tests/|scripts/|venv/)"]` ⇒ 被类型检查的只有 **73 / 260** 个 `.py`（28%），
  `tests/` 114 个与 `scripts/` 73 个**完全不查**。
- `[tool.coverage.run] omit = tests/*, scripts/*, knowledge_base.py, seed_admin.py`，且 `branch = true`
  ⇒ 被测面积 **71 个文件 = 73 − 2**（与 mypy 数交叉一致）。
- **我原本怀疑"84.47% 被测试文件灌水"，量下来方向是反的**：测试码根本不在覆盖统计里，
  84.47% 是**生产码的 branch-aware** 覆盖率。（另注：按纯行比算是 85.85%，与工具数不同式，别混用两式。）
- 真实缺口在别处：**`scripts/import_laws.py` 既不在 mypy 作用面、也不在 coverage 作用面** —— 它是我候选批的守门校验器。
  所以"校验器可信"这句话的支撑**不是** CI 覆盖率，而是 `test_import_laws_validation.py` 15 条 + 我补的 6 条变异正/负例。

**订正**：Task 5 门禁表里 `mypy .` 那行读数是 CI 同形的，但**任何把"mypy 73 files / cov 84.47%"外推成
"全仓类型安全 / 校验器已被 CI 覆盖"的说法都不成立**。本条即该缺口的显式登记。

### D2 — High｜`pip-audit`：先建议开票，后才发现在册批准（流程缺陷，非读数缺陷）

顺序错了：我先按"138 条已知漏洞"报了数并建议"另开一张依赖治理票"，**没先查有没有在册处置**；
查到 `r8-disposition-20260907.json` 里 `owner_approval.status = APPROVED` 后才改口为"到期重签"。
危害不是数字错，而是**差点发起一次推翻已批决定的重复评审**。同时"138"是**行数**、去重 **80 个公告 ID**，
我第一版把两轴混成一轴。

**订正**：已在门禁表、等价性清单、三态结论、台账 E3 四处统一改为"138 行 = 80 个不同 ID"，
并把 E3 的建议换成"复跑 + 重签"。可复用规矩：**报漏洞数之前先查 `release-evidence/**/r8-disposition-*.json`**。

### D3 — Low｜"文件内容为零丢失"这句话有两种读法

我实际证的是：① tip↔tip `D=0` ⇒ 无远端独有**路径**；② 远端 tip 树 与本地根 `5e51384` 树只差 1 文件
⇒ 远端那份内容作为**历史对象**仍留在本地历史里。我**没有**证也不需要证"本地 tip 逐文件包含远端 tip 内容"
（63 个 M 文件内容本来就在 8 天里被改过）。按第二种读法原句会被读成过强主张。

**订正**：应读作"**没有远端独有的文件；远端独有的是那 204 笔提交本身**"。

### D4 — Low｜"两出口"的测试归属写窄了

我把 W1 两出口的证据记在 `test_both_exits_call_the_same_function_object` 一条名下。实测：
该条断的是 `main.qa_citations_in_kb is retrieval.qa_citations_in_kb`（`:106`，对象同一性）
加 `prepare_fast_path` 体内出现该名（`:110`）；**直返出口**那半边在
`test_no_exit_keeps_its_own_copy_of_the_lookup_loop:122-124`（断 `exact_article_lookup(`/`cited_articles(` 不再内联、
且必须调 `qa_citations_in_kb(`）。两条合力才成"两出口"。

顺带一个**否证成功**的好消息：这两条不是我担心的"立即绿的哨兵"—— 它们钉的是被比对象本身，
且 `test_direct_return_follows_the_shared_predicate:143` 的替身打在 **`retrieval.exact_article_lookup`**
（判据本体模块）上，正是本仓记忆里"打在 import 处是自我安慰"那条坑的正确形态。

### D5 — Medium｜候选批的"就绪"漏了一句最要紧的推论（本轮新跑出来的）

用真谓词 `retrieval_core.is_valid_by_time` 对本批三条实跑 4 个查询日：

| cutoff | 民法典 1260 | 调解仲裁法 27 | 合同法 428 | 命中数 |
|---|---|---|---|---|
| 2026-09-26（今天，默认） | 有效 | 有效 | **无效** | 2/3 |
| 2020-12-31（废止日含当日） | 无效 | 有效 | **有效** | 2/3 |
| 2021-01-01（民法典施行日） | 有效 | 有效 | 无效 | 2/3 |
| 2020-06-01 | 无效 | 有效 | 有效 | 2/3 |

⇒ 正面：分水岭**两侧边界日语义都对**（`et == today` 当日仍有效、`ef > today` 尚未施行）。
⚠️ 但"新旧两版不重叠也不留空档"**不由这批语料证明**（09-26 评审纠出，我复核成立）：批内 3 条分属 3 部法，
**没有任何一对是同一（法名, 条号）的两个版本** ⇒ 该性质只能指向 `tests/test_phase5.py:25-29`
（用劳动合同法 2013-06-30 / 07-01 那条真实分水岭钉住的用例），不能指向本候选文件。
⇒ 而我这一句"直接收益是 0"**归因归错了**（09-26 拿真实库副本 A/B 实跑后重写，见文末 §独立评审）：
今天召不回 428 是真的，但**净效果不是 0** —— 无日期的旧 `upload` 双胞胎使 1260/27 时间语义失效，
同时新的干净带日期块在向量排序上**确实更强**（民法典 1260 从"不在 top-4"进到第 3 名）。
所以正确说法是：**+1 命中 / −2 被同一条文占两格挤出去的相邻相关条文**，代价与收益都来自同一个 H-1 根因。
（另：428 只在显式历史 cutoff 那条路兑现，而 AUTH-B 仍卡着。）
"候选就绪"**不等于**"召回改善"，也不等于"零改善"——两句都不许说，这正是 §2 那张票警告过的失效形状。

### D6 — Low｜仓库里一个不是我造的化石目录（登记，未处置）

`backend/chroma_db;C/` —— **空目录**，`dir_mtime = 2026-09-07 08:22:52`（早于本轮 19 天，非我产生），
形状是 MSYS 路径转换把 `;C:` 拼进目录名的那一族事故。

- 已查不会被误用：全仓 `*.py` 里对 `chroma_db` 无 `glob/listdir/walk/rglob/fnmatch`；
  `backup_data.py:44` 与 `docker-compose.yml:47` 都用**精确名**，且另有 `scripts/chroma_dir_guard` 把关。
- 我本轮"真实库未动"的指纹也是按精确名取的 ⇒ 读数不受它影响。
- **我没有删它**：不是我建的，且空目录的存留含义无人认领，删除属不可逆动作。留作 Owner 一行命令的卫生项。

### D7 — 仪器自错累计 6 次（全部当场抓到并复量，无一进入结论）

① 负对照把条目**列表**传给 `validate_entry` ⇒ 六条以 `条目必须是对象` 假"拒绝"；
② 还原源侧串的断言**方向写反** ⇒ 报出两个假 False；
③ `node -e` 打印 `package.json.scripts` **被截断** ⇒ 我据而下判断言"没有 test 脚本"（实跑证有）；
④ 仓库级 `glob('**/frozen-hashes.json')` **超时**（34k 未跟踪文件）；
⑤ 取数命令前后两版**键集不同**（少写 `version_valid_for`）⇒ 未动的库 diff 出两条假差异；
⑥ 本轮新的一条：`chroma_db;C` 第一次枚举**没出现**，我据此几乎判"不存在"，
   改 `os.path.exists` 直查才定案 —— 与 ③ 同族：**别拿一次遍历的空结果当否证**（本仓记忆 1l 的老坑，又复发了）。

### 结论（自审后是否改变三态判定）

**不变：仍是 ③ 不就绪**，阻断项仍只有 `pip-audit` rc=1（且已澄清为"在册风险接受到期待重签"）。
⚠️ **本段已被文末 §独立评审 修订**：那条"未发现任何生产代码缺陷"作废，阻断项由 1 条变 2 条（加 H-1）。
本轮**未发现任何生产代码缺陷**，因此维持"不开修复票"。
本轮**发现 3 处我自己的表述会误导下一代读者**（D1 作用面、D3 过强措辞、D5 漏写零收益推论），
均已在上文订正；D5 那句需要一并进语料数据票，避免只活在这里。

---

## 独立评审（2026-09-26，两路并行 agent + 执行者逐条复测）

两路评审互相不知情、独立出题。**下面每一条都由我在本机复测过**，"成立/打掉/改口径"是复测结论，不是转述。

| 路 | 覆盖对象 | 评分 | 报告绝对路径 |
|---|---|---|---|
| 语料 / 安全 | 候选批、批导入校验器、依赖处置 | 8.4/10（完成 9 · 质量 8 · 沟通 9 · 效率 8 · 可维护 8） | `C:/Users/33393/AppData/Local/Temp/review-result-fazhi-corpus.md` |
| Git / 门禁 | Task 1-2 全部指针、五道门禁 | 7.5/10（完成 8 · 质量 9 · 沟通 7 · 效率 8 · 可维护 6） | `C:/Users/33393/AppData/Local/Temp/review-result-fazhi-git-gates.md` |

Git 路自己复量 30 项读数：**21 项逐字成立、8 项表述过宽、1 项不成立**；门禁它全部重跑命中
（`ruff check` 0、`ruff format --check` 261 files、`mypy` 73 source files、全量 **1544 passed / 2 skipped / 18 deselected / 84.47%**、
守卫 9、前端 build + 54 passed、`pip-audit` rc=1 **如实上报未涂绿**），并复量真实库面 `app.db` 仍 10784 / chroma 38→38。
它另披露了自己的副作用：复跑采集口命令时把 env 值当输出路径，在 `backend/` 生成文件 `1`，已删并复量工作区恢复为 34093/6/0/`1d30603`（我复测 `backend/1` 确不存在）。

### 复测裁定表

| # | 评审主张 | 复测 | 证据（本机实跑） |
|---|---|---|---|
| V1 | **H-1** 真入库会造出"带日期新块 + 无日期旧块"并存 | **成立，且比它说的更严重** | 见下节三条读数；补充：现网 `origin='seed'` 是 **0 条** |
| V2 | **H-2** `source_document_sha256` 永不重算、落库正文与哈希脱钩 | **一半成立一半打掉** | 格式口成立：`"0"×64` 通过 `validate_entry`；但本批 **3/3** `sha256(落库 chunk)==sha256(content)==声明值`（各 1 chunk）。它给的 `d38db470…/2d8c76c5…` 是**含条号前缀的源侧原文**，与本字段语义（存储正文）不是同一串，两者都对 |
| V3 | 省略 `status` 会绕开"已修改/已废止必带 `effective_to`" | **成立** | `{title,article,content}` 无 status ⇒ `errors=[]`；同一内容显式写 `status=已废止` ⇒ 报必填 |
| V4 | 占位符正则放行 `待核`/`TBD`/`XXX` | **成立** | 三条负例全部 `errors=[]` |
| V5 | 同批内重复 `(title,article,effective_from)` 未拦 | **成立，但后果要说清** | 校验层 `errors=[]`；`derive_version_id` 相同（`lv-00adc359…`）⇒ 后一条**静默替换**前一条（是数据丢失，不是并存） |
| V6 | 远端 204 笔里 40 个 blob / 25 路径本地 `.git` 根本没有 | **成立，定性改掉它的用法** | 远端 3346 blob、本地 3933 blob、gap **40**；**这 40 个 0 个是远端 tip 版本**；`D:\…\dot-git-backup` 两处 **40/40 全在** ⇒ 缺的是中间历史版本，不是当前文件 |
| V7 | 接缝方向我写反了（"远端 tip 才有隔离"） | **不成立（评审方反了）** | `CHROMA_DIR` 命中数 远端 tip **1** / 本地根 **4**；两版本 diff 显示 `+ os.environ["CHROMA_DIR"] = _TEST_CHROMA` 在本地侧 ⇒ 原文"本地侧是修复后版"正确，保留 |
| V8 | `b40076b` 在本仓不是有效对象，E6 照写必失败 | **成立，并给出可用替身** | `cat-file -t` 本仓与远端克隆均 fatal；subject 反查 ⇒ `c25fbd6`，两者 **tree 同为 `cfa6cab27d236b9bff932ce0e6b881d0b0c89932`** |
| V9 | 守门校验器带一个 CI 永远看不见的类型错 | **成立** | 与 CI 同 cwd（`backend/`）单跑 `mypy scripts/import_laws.py` ⇒ **1 error**：`:48 Need type annotation for "errors"`；`pyproject.toml` mypy `exclude` 掉 `scripts/` ⇒ CI 结构上不可能看见 |
| V10 | "代码门禁就绪"这句过头（类型门只覆盖 28% 文件、6 个核心模块 `disable_error_code`、3 文件被 ruff 排除、1544 绿取自发布物构建不出的依赖集） | **成立，采纳** | 与 3b（`uvicorn 0.52.1`/`pypdf 6.14.2` 越锁）同源，措辞降为"CI 形状的门禁在我这台依赖集上全绿" |
| V11 | 远端我只查了 `refs/heads/master` 一条 ref，结论侥幸成立 | **成立** | 补查审计克隆 `for-each-ref` 共 3 条（含我自己 fetch 的 `local/master`）、远端侧仅 master、0 tag ⇒ 结论不变，但过程要记成"覆盖面被补过" |

### H-1 的实测影响面（三条读数，全部在真实库副本上）

副本做法：`cp -r backend/chroma_db → %TEMP%\fazhi-chroma-{copy,h1repro,fixed}-20260926`（原件 mtime 仍 09-21、38 文件、未写）。

1. **谓词层（时间语义被旧块抹掉）**。`origin='upload'` 旧块元数据实测为
   `status=现行 / effective_from='' / effective_to='' / 无 version_id`，
   `is_valid_by_time` 对它在 **2020-01-01、2021-01-01、2026-09-26** 三个查询日**全为 True**（矩阵 `tests/test_phase5.py:34-35` 本就钉着这个 fail-open）。
   于是 `exact_article_lookup('民法典','第一千二百六十条', cutoff='2020-06-01')` 返回 **n=1，且那 1 条就是无日期旧块**
   —— 民法典施行前的历史查询照样能召回到它。带日期的新块被正确判为未施行，**但它的正确性被旧块完全遮蔽**。
2. **排序层（k=4 预算里的得失）**。三棵副本树各跑同一 5 题：

| 查询（截断） | 只旧块（对照） | 新旧并存 | 删掉旧块 |
|---|---|---|---|
| 劳动争议仲裁时效多久 | 27·劳82·43·劳83 | **27(import)·27(upload)**·劳82·43 | 27·劳82·43·劳83 |
| 民法典何时施行/废止哪些 | 民诉306·民办67·破产136·民法59 | 民诉306·民办67·**1260(import)**·破产136 | 同左（1260 保住第 3 名） |
| 试用期最长多久 | 劳21·劳动19·民法637·劳动83 | 不变 | 不变 |
| 合同法428规定了什么 | 专利82·道交124·国籍18·民法428 | 不变（新 428 今日判无效，正确） | 不变 |
| 仲裁时效一年还是两年 | 27·民法198·农包仲18·仲裁90 | **27(import)·27(upload)**·民法198·农包仲18 | 27·民法198·农包仲18·仲裁90 |

   读数：**+1 命中**（1260 从"不在 top-4"进到第 3 名，且删掉旧块后仍保住）／**−2 挤出**（`劳动法83`、`仲裁法90` 因同一条文占两格而掉出 top-4）。
   ⇒ 净效果为**负**，且**收益与代价同源于 H-1**：旧块不处置，就同时背着代价、拿不到完整收益。
3. **修复反证**。在第三棵副本上按 (source, article, `origin='upload'`, 无日期) 删掉 2 个旧块
   （ids `bbc1ca29…`、`6739b37f…`，集合 10269→10267），5 题复跑：两题的挤出项**全部回来**，1260 的提升**保留** ⇒ 处置旧块是"只留收益去掉代价"的那一步。
   ⚠️ 顺带打掉一个想当然的修法：**"正文相同才删旧块"在本库永远不触发** ——
   两对旧/新块 `exact_equal=False`（旧块带章节行与条号前缀，165/141、290/275 字），
   只有**去空白后的包含关系**成立（`new ⊆ old` 两对皆 True、`old ⊆ new` 皆 False）。任何 T1 方案的比对都必须先做空白/全角归一。

### 法律复核状态（两路都碰了这条，取更硬的证据）

`outputs/法律咨询回答复核作业-已填-20260918.md` 除 AI 自签（第 202/1015 行 `法律合规专家（WorkBuddy AI）`）之外，
**第 1267 行自带一条流程违规声明**："因材料为单文件版，第四、五部分在第一阶段开始前已随原文一并读入，
'意见冻结前不读第四、五部分'的防锚定流程无法严格执行，特此声明"，并称存疑条文"已逐一联网核验"但未给可核对来源。
⇒ 结论从"是 AI 签的"加强为"**既非人类、也未按盲评流程执行**"。独立法律复核**仍未取得**。

### 必须改的补丁清单（本轮仍未动任何生产码，逐条待开票）

**✅ 09-26 已开票（Owner 定 B 档：只写判据、不动码）**：本表五条已展开成可派发票据，含 §0 复现凭证、每条的
可测判据与变异要求 ⇒ **`docs/h1-law-version-collision-tickets-20260926.md`**。下表保留作索引。
两处开票时补上的实测修正：① T3② 的七个占位词在现网 10266 条正文**命中 0**（不必收窄词形）；
② T3③ 只涉及 `version_metadata` 的三个生产者（`knowledge_base.py:38`、`knowledge_service.py:183`、
`scripts/import_laws.py:153`），**整法上传路径根本不经过它** ⇒ 我原先"要小心整法 content"那句是错的，已在票里改口。

⚠️ **开票当日新增 T6，并因此改掉 E3 的执行方式**（读 `backend/scripts/gen_r8_disposition.py` 读出来的，不是猜的）：
该脚本把 `:69 scan_date="2026-09-07"` 与 `:106-110 owner_approval={"status":"APPROVED", "approved_at":"2026-09-07"}`
**连结论一起写死**，输出路径 `:17-18/:113` 也是固定的 09-07 文件名、`:48` 原地覆盖。⇒
**"复跑生成器来重签"这个动作今天会 ① 覆盖已签的 09-07 证据件，② 铸出一份"看着像 Owner 批过"而实际无人批准的新记录。**
所以 E3 改按：复扫只取读数（落 `dispatch-output/` 一类工作目录），新处置件**手写日期 + Owner 亲签 `owner_approval`**、
09-07 两份原件一字不改地并列保留；T6 落地前不许任何人跑这个脚本。这与我 §法律复核状态 里那条"AI 已填卷"是同一族失效。

| 票 | 改什么 | 判据（怎么算修好） | 为什么要它 |
|---|---|---|---|
| **T1** | `law_versions.replaceable_version_ids` 的 legacy 分支：从"`无 version_id` 且 `effective_from` 相等"扩到"`无 version_id` 且**两个日期皆空**"，并按上面第 3 点做**归一化包含**比对后才决定删旧块 | 新增/扩展用例：无日期旧块 + 带日期新块 ⇒ 替换后该 (source,article) **只剩 1 块**；文本不一致时必须**报警不删**；`origin` 非 upload/manual 的不动 | H-1 根因。不修则任何带时效的导入都只是在无日期块旁边加一份 |
| **T2** | `import_laws.py` 预检加一条**并存检测**：同 (source,article) 已有块且其时效字段为空 ⇒ 打印并**整批不出** | 拿真实库副本跑 `--dry-run`，输出必须从"将替换 0 旧片段 + 新增"变成点名报警；补一条断言该分支可达的用例 | 现在的 dry-run 对此**静默**（实测），是本轮最危险的一处假绿面 |
| **T3** | 校验器三口：`status` 缺省不得静默按 `现行`（要么必填、要么显式确认）；占位符正则补 `待核/待定/TBD/XXX/（略）`；`source_document_sha256` 与正文**复核一致**才收（或干脆不接受外部值） | 三条负例（V3/V4/V2）由 `errors=[]` 变红；且既有 3 条真候选仍须全绿 | 已签口径"已修改必带 effective_to"目前**触发不了**；哈希声明目前可无成本失真 |
| **T4** | 三处 `b40076b` 指针改 `c25fbd6`（或写明"按 subject 反查"） | 测试 docstring 里那条指令能照抄执行 | 现指针 fatal（V8），会坑下一个照做的人 |
| **T5** | `scripts/import_laws.py:48` 补 `errors: list[str] = []`，并评估把 `scripts/` 纳入 mypy 或加一条"守门器必须过类型"的门 | 单跑 mypy 该文件 0 error | V9：守门器落在所有静态门的作用面之外 |

**旧块处置本身是另一笔账**：全库 10266 条都属"无日期 upload"形态，T1/T2 只保证**新导入不再制造双胞胎**，
不改已存在的 10266 条。是否批量补日期、要不要重跑 `import_docs.py`，属数据治理决策（新增待裁 **E7**）。

### 结论修订

三态**仍为 ③ 不就绪**（评审方也独立认可，并肯定我没被风险接受书勾去升格）。但阻塞项从 1 条变 2 条：

1. `pip-audit` rc=1 —— 在册已批的风险接受**到期**，待 E3 重签；
2. **H-1 —— 候选批不得真实入库**，先修 T1/T2（语料候选的状态由"待入库窗口"改判为"**阻塞**"）。

上文自审那句"**本轮未发现任何生产代码缺陷**"**作废**：H-1 是生产代码与现网数据交互产生的成立反例，
V3/V4/V2/V9 是守门器的成立缺口。本轮改口为"**未发现会当场崩的缺陷，但发现 1 个静默失真面 + 4 个不拦的校验口**"。

