# 门禁修复验收、证据更新与本地候选收口执行书

> **给接手助手：** 用户会只给你本文件完整路径。本文包含任务、基线、命令、完成条件和授权边界。按 A → B → C → D → E 执行并逐项勾选；可用 `executing-plans` 记录进度。相关文件是核查输入，不要求用户另找一套任务书。本文是后续执行说明，编写本文件不表示任务已执行。

**Goal:** 验收当前门禁修复，重新取得可信的隔离运行证据，交付一个固定、可核查的本地候选对象及剩余决策材料。

**Architecture:** 复用现有三只门禁、B 档探针、候选环境和保护基线；先确认修复，再隔离更新读数，最后验收固定 Git 对象。生成最终结果记录，不新建审批、遥测或任务调度框架。

**Tech Stack:** Windows PowerShell、Git、Python 3.11、pytest、Ruff、python-dotenv、本地嵌入模型、Chroma 临时副本。

## 0. 执行边界与完成含义

本文件默认执行到“助手侧本地验证与准备完成”。允许：范围内必要兼容修复、临时副本、离线测试、本地 Git 对象构造、隔离证据落盘、只读远端核查、报告更新。**不授权实际 commit、移动已有分支引用、merge、push、PR、凭据轮换、风险代签、真实库写入、生成模型调用或部署。** 用户此前还没有选服务器。

真实 rerank 已有一次隔离验收的范围授权，但前置条件仍为：Owner 明确告知已撤销/轮换暴露凭据。未收到该确认时，登记受阻，继续其他任务。新值只进入本地受保护配置，不得发到聊天/日志/提交。本阶段不以新增供应商、替换模型、升级整套依赖来绕过阻塞。

“24 项门禁回归通过”只证明门禁修复；“探针复算通过”只证明对应运行窗口的主张；“离线候选测试通过”不代表风险被接受、法律质量已认证或可部署。最终必须分别给出这三个结论及 Owner 项状态。

出现范围、业务行为或权限上的新决策，用 `grilling` 一次问一个问题并给推荐方案；文件和代码里的事实自己查。普通实现细节在既定边界内自行解决。同一命令失败先分析，完全相同命令最多重试一次；同一缺陷连续三次修复不过，停止该项并复盘。

## 1. 接手基线、路径与当前已知事实

以下是 2026-09-30 写本文时的读数，不是要求回退到它们：

| 对象 | 当时状态 |
|---|---|
| 主工作区 | `C:/Users/33393/Desktop/ai-legal-helper`，master，`86628ba85ca6f240894ced21c28dfecf83be5c89` |
| 候选工作区 | `C:/Users/33393/.codex/worktrees/local-candidate-closeout/ai-legal-helper` |
| 候选分支 | `codex/local-candidate-closeout`，`fbc29e87c14e8e6a2c0744e98d86d426f6146ade`，未合入主线 |
| 旧快照引用 | `snapshot/ci-fbc29e8-20260930`，`fd5a8cf2e964a6f198f60a252c27b1fca203665d`，不含本轮未提交修复 |
| 独立 Python | `C:/Users/33393/AppData/Local/Temp/legal-closeout-20260928/venv/Scripts/python.exe` |
| 旧证据目录 | `C:/Users/33393/Desktop/ai-legal-helper/dispatch-output/local-candidate-closeout-20260928` |

本轮已有五个已跟踪文件修改及一个新增测试文件，均应保留并核对，不能当作脏文件清掉：

1. 旧证据目录下 `b_build_snapshot.py`、`b_probe_run_suite.py`、`b_snapshot_trim_diff.py`。
2. 同目录新增 `test_release_gates.py`。
3. `docs/process-archive/work-report-20260929-d2-signoff-round.md` 的顶部提示与 §12。
4. `docs/process-archive/superpowers/plans/2026-09-29-local-candidate-decision-and-release-prep.md` 的顶部提示。

这些修复的现有验证：候选 Python 跑 `test_release_gates.py` 为 24 项通过，Ruff 与 `git diff --check` 通过。**接手后重新核查，测试数以实际输出为准，不能凑到 24。** 旧项目全量日志曾为 1650 passed / 10 skipped / 18 deselected、覆盖率 85.25%；这不是当前修复后的项目重跑结果。

旧 `b_probe_claim_check.py` 当前复算 rc=1，已知失败为 pytest、app、自检三项“读数晚于仪器/驱动修改时间”。不能改 mtime、改判据或抄旧 rc=0 消除红灯。其余新出现失败也必须分析。

初始化 PowerShell 变量；后文所有命令在同一个会话中执行：

```powershell
$Repo = 'C:/Users/33393/Desktop/ai-legal-helper'
$Candidate = 'C:/Users/33393/.codex/worktrees/local-candidate-closeout/ai-legal-helper'
$Evidence = Join-Path $Repo 'dispatch-output/local-candidate-closeout-20260928'
$Py = 'C:/Users/33393/AppData/Local/Temp/legal-closeout-20260928/venv/Scripts/python.exe'
$RunRoot = Join-Path $env:TEMP ('legal-closeout-followup-' + [guid]::NewGuid().ToString('N'))
$RunEvidence = Join-Path $RunRoot 'evidence'
New-Item -ItemType Directory -Path $RunEvidence | Out-Null
Set-Location $Repo
git status --short --branch -uno
git -C $Candidate status --short --branch -uno
git rev-parse HEAD refs/heads/codex/local-candidate-closeout refs/heads/snapshot/ci-fbc29e8-20260930
git worktree list
```

逐条检查原生命令的 `$LASTEXITCODE`，保存真实 rc，不把最后一个日志命令的成功当作前一步成功。Python 不存在时，核对旧目录的 `download-report-from-assistant-20260928.md` 和 wheelhouse；停止依赖该环境的任务，不能安装到共享 `backend/venv` 或换系统 Python。

辅助输入（都在本机，无需让用户另行提供）：工作汇报 §12；`docs/process-archive/handoff-local-candidate-closeout-20260929.md` §6；旧证据目录的 `README.md`、`residual-risk-review.md`、`residual-risk-review-devtools.md`、`residual-risk-review-torch.md`（若名称有变化，列出实际文件再定位）。旧计划和旧报告中的无参数快照构造、只等回车、自动风险接受等表述不作为当前指令。

## A. 验收已有修复，冻结本轮输入

**文件责任：** 第 1 节六个修复文件；必要时小修其中的缺陷。先读 diff，避免复写用户或并行助手的其他工作。

- [x] 检查上述文件是否存在、差异是否仍为同一任务；记录真实主线和候选 SHA。若别人已提交了这些修复，记录新 SHA 并使用它，不重复提交或回退。
- [x] 运行门禁回归和静态检查：

```powershell
& $Py -B (Join-Path $Evidence 'test_release_gates.py')
$GateRc = $LASTEXITCODE
& $Py -m ruff check (Join-Path $Evidence 'b_build_snapshot.py') (Join-Path $Evidence 'b_probe_run_suite.py') (Join-Path $Evidence 'b_snapshot_trim_diff.py') (Join-Path $Evidence 'test_release_gates.py')
$LintRc = $LASTEXITCODE
& $Py -m ruff format --check (Join-Path $Evidence 'b_build_snapshot.py') (Join-Path $Evidence 'b_probe_run_suite.py') (Join-Path $Evidence 'b_snapshot_trim_diff.py') (Join-Path $Evidence 'test_release_gates.py')
$FormatRc = $LASTEXITCODE
git diff --check
$DiffRc = $LASTEXITCODE
if ($GateRc -ne 0 -or $LintRc -ne 0 -or $FormatRc -ne 0 -or $DiffRc -ne 0) { throw 'A 未通过：先分析具体失败' }
```

- [x] 确认失败路径仍有保护：缺失凭据/扫描错误、行尾注释/引号、中文口令、未展开变量、删除失败、树号漂移、两侧同样收集失败、同数不同用例、pytest/JUnit/探针异常。
- [x] 确认快照脚本将八键视为本轮已登记的扫描输入，而非要求所有供应商永久启用。缺键不得填假值；如真实配置不使用某键，记录并请 Owner 对齐清单，C 停止，A/B/D 可继续。
- [x] 对参与运行的脚本、候选 requirements 和测试输入记录 SHA-256。A 后若又改驱动/仪器，B 必须重取得受影响读数，不能靠调时间恢复有效性。

**A 验收：** 修复回归、lint/format/diff 均 rc=0；脚本边界与 §12 一致；六个文件归属明确。尚未 commit 不妨碍 A。

## B. 隔离更新探针证据，恢复可核查的复算

**文件责任：** 复用 `b_runtime_probe.py`、`b_probe_alias_canary.py`、`b_probe_build_tree.py`、`b_probe_run_suite.py`、`b_probe_app_paths.py`、`b_probe_claim_check.py`。必要修改仅限隔离输出入口与已证明的控制流缺陷，不重写探针体系。

### B1. 先解决输出隔离，再运行

现有 `b_probe_build_tree.py`、`b_probe_run_suite.py`、`b_probe_app_paths.py` 和 `b_probe_claim_check.py` 绑定旧证据目录；自检和复算还有固定文件名。**不得直接运行并覆盖旧自检/复算文件。** 用同一个可选环境变量将这四个脚本的 `EVIDENCE` 指到本轮目录，默认行为保留；其他脚本不为整齐而改造。

四处 `EVIDENCE` 赋值采用下列最小形式；`b_probe_claim_check.py` 如未 import os，补 `import os`。其他三个已有 os：

```python
EVIDENCE = Path(
    os.environ.get("B_PROBE_EVIDENCE_DIR")
    or "C:/Users/33393/Desktop/ai-legal-helper/dispatch-output/local-candidate-closeout-20260928"
)
```

- [x] 先在 `test_release_gates.py` 增加反例：临时目录 override 后，读取/输出路径确实落在该目录，原目录内容没有变化；清空变量后默认路径仍一致。应用驱动有顶层副作用，不可仅为检查常量就直接 import 它；用假后端子进程验证输出路径。
- 输出入口的基础反例可采用下面代码；同时在既有 `SuiteTests` 中保留真实临时文件输出断言，基础反例不能代替无共享写入验证：

```python
def test_evidence_override_is_used(self):
    with tempfile.TemporaryDirectory() as tmp:
        with patch.dict(os.environ, {"B_PROBE_EVIDENCE_DIR": tmp}):
            for name in ("b_probe_build_tree", "b_probe_run_suite", "b_probe_claim_check"):
                self.assertEqual(load(name).EVIDENCE, Path(tmp))
```

- [x] 测试先失败再小修，复跑 A。隔离入口改好后冻结脚本，B 后续不得继续改脚本而保留之前生成的读数。
- [x] 将本轮要运行的脚本复制到 `$RunEvidence`，保留源 mtime 并记录两边 SHA-256；Python 模块路径指向这些副本。同时复制 `README.md`、`residual-risk-review.md`、`b-probe-dns-trace.json` 和复算器需要的历史 JSON/log，只限旧证据目录顶层的 `b-probe-*` 文件；复制前检查不含凭据值。历史件维持原名/时间，注明“继承件”，不能记作本轮生成。
- [x] 复算器从 `$RunEvidence` 读取脚本和读数，`REPO` 保留主项目路径用于读文档。复制的 README 引用旧实测值，若新测不同，先解释新旧差异，再修改当前汇总，不能照旧值强行断言。

```powershell
$env:B_PROBE_EVIDENCE_DIR = $RunEvidence
$env:B_PROBE_PY = $Py
$env:PYTHONPATH = $RunEvidence
$SavedTaskTemp = $env:TEMP
$env:TEMP = $RunRoot
$env:HF_HUB_OFFLINE = '1'
$env:TRANSFORMERS_OFFLINE = '1'
$env:EMBEDDING_PROVIDER = 'local'
$env:RERANK_ENABLED = 'false'
$env:JWT_SECRET = 'test-jwt-secret-for-ci-only'
$env:LLM_API_KEY = 'test-key-not-for-real-calls'
$env:LLM_BASE_URL = 'https://test.invalid/v1'
$env:DATABASE_URL = 'sqlite:///' + (Join-Path $RunRoot 'iso-app.db').Replace('\', '/')
$env:QUOTA_DB = Join-Path $RunRoot 'iso-quota.db'
$env:CHROMA_DIR = Join-Path $RunRoot 'iso-chroma'
```

本轮进程的凭据、LLM 端点全部使用脚本既有假值；其他继承的供应商/跟踪凭据在测试子进程中清除。所有 DB/QUOTA/CHROMA 落点指向 `$RunRoot`，先设好再 import 后端模块。尤其确认 **`CHROMA_DIR`**，不能只清理 CHROMA_PATH/CHROMA_DB_PATH。不读取真实 `.env` 来跑 B；本地模型缓存缺失则登记受阻，不启用在线下载兜底。

### B2. 保护基线与干净候选副本

- [x] 对 `verify-protected.py` 先读实现：它的通过判据是大小与 SHA-256，并非 mtime 相等。用新日志文件名执行前测：

```powershell
& $Py (Join-Path $Evidence 'verify-protected.py') (Join-Path $RunEvidence 'protected-before-check.log')
if ($LASTEXITCODE -ne 0) { throw '真实保护对象与历史基线不一致，停止会写数据的实验' }
& $Py (Join-Path $RunEvidence 'b_probe_build_tree.py')
if ($LASTEXITCODE -ne 0) { throw '副本建树失败' }
$Build = Get-Content -LiteralPath (Join-Path $RunEvidence 'b-probe-tree-build.json') -Raw | ConvertFrom-Json
$Tree = [string]$Build.tree
```

- [x] 验证 `$Tree` 位于本轮临时区域或建树器创建的明确临时目录；不等于 `$Repo`、`$Candidate`，没有真实 `.env`、venv、真实 Chroma/app.db。
- [x] 建树器明确列出的两个收集期文件为 `dispatch-output/task1/hidden-cases-v1.json` 与 `hidden-round-protocol-v1.json`。只补这两项并记录 hash，不复制整个未跟踪目录；缺失即停。它们只用于隔离实验，不因此自动获准公开或提交。
- [x] 保存环境版本（Python、pytest、FastAPI、Starlette、pypdf、torch）；不升级/降级共享或候选 venv。pytest 新旧版本读数不能混成同一环境下的复跑一致性。

### B3. 在同一副本上串行测量

脚本路径均为 `$RunEvidence` 中的冻结副本。各命令保存完整 stdout/stderr 和 Python 的真实退出码。禁止在共享树运行 `b_probe_claim_mutants.py`；复制该脚本/切 cwd 也不解除禁令。

```powershell
$env:PROBE_CAND = $Tree
$env:PROBE_OUT = Join-Path $RunEvidence 'b-probe-selfcheck.json'
& $Py (Join-Path $RunEvidence 'b_runtime_probe.py') selfcheck
# 必须 rc=0；随后负对照预计 rc=1，并核对失败原因确为撤去 G3b。
$env:PROBE_OUT = Join-Path $RunEvidence 'b-probe-selfcheck-break.json'
& $Py (Join-Path $RunEvidence 'b_runtime_probe.py') selfcheck --break G3b
Remove-Item Env:PROBE_OUT -ErrorAction SilentlyContinue
& $Py (Join-Path $RunEvidence 'b_probe_run_suite.py') $Tree
# 核对 pytest rc、JUnit 失败数、探针 pytest_exitstatus 都是 0。
& $Py (Join-Path $RunEvidence 'b_probe_run_suite.py') $Tree
# 第二场服务于复算器已有的两次复跑契约，不额外跑第三场凑数。
& $Py (Join-Path $RunEvidence 'b_probe_app_paths.py') both $Tree
# QA/上传只访问空临时 Chroma，允许本地嵌入与写临时库，不调用生成模型。
& $Py (Join-Path $RunEvidence 'b_probe_claim_check.py')
```

- [x] 每一步成功后再继续，不将负对照预期 rc=1 当成整批失败，也不将不明 rc=1 当成预期。
- [x] 复算失败逐条定位。新测分母/事件数量变化先核对源代码、版本、输入、探针加载顺序；不能直接放宽期望。合理变化可修正事实汇总并保留理由，既有安全门禁不可降级。 —— 状态：已做：唯一差异 compile_event_total 用 .pyc 出生窗口归因到冷/热树，未放宽任何期望
- [x] B 的三项新鲜度失败必须靠真正新运行解除；存在其他无法解释的失败时，保留“证据更新受阻”，继续不依赖它的 D。 —— 状态：已解除：三项新鲜度断言靠本轮真跑的读数转绿（复算器 67/67 rc=0）
- [x] 用新的 `protected-after-check.log` 后测，与前测及历史基线核对。保护对象大小/hash须一致；mtime若变化单列调查，不冒充该脚本已验证 mtime。

**B 验收：** 自检正/负例能区分、两次测试与应用路径场成功、复算器 rc=0、证据晚于冻结脚本且记录 hashes、保护对象未变。任一未满足，不写“B 完成”。新读数留在 `$RunEvidence`，先脱敏复核；不自动替换旧同名文件或批量加入仓库。

## C. 构造并验收固定本地对象，避免等待 commit 阻塞验证

**文件责任：** `b_build_snapshot.py`、`b_snapshot_trim_diff.py`；复用 Git 临时 index 和对象，不写真实分支引用。C 可核查对象内容不等于 Owner 已批准公开。

### C1. 合成包含已审修复的草案输入

直接 archive 当前 HEAD 会遗漏未提交修复。若 Owner 已另行允许并完成本轮提交，使用那个已核查提交作为输入；否则采用下面的**临时 index + commit-tree 草案对象**，不改真实 index/HEAD/master。

- [x] 明确 `$DraftPaths`：第 1 节六个文件，加上 B1 实际修改的 `b_probe_build_tree.py`、`b_probe_app_paths.py`、`b_probe_claim_check.py`；数组去重。只列实际存在且已审查归属的文件，不包含 `.env`、密钥文件、数据库、旧/新测试产物或本执行书的进度修改。
- [x] 先核对草案文件未包含凭据，再执行；任何 Git 非零即停止：

```powershell
$DraftPaths = @(
    'dispatch-output/local-candidate-closeout-20260928/b_build_snapshot.py',
    'dispatch-output/local-candidate-closeout-20260928/b_probe_run_suite.py',
    'dispatch-output/local-candidate-closeout-20260928/b_snapshot_trim_diff.py',
    'dispatch-output/local-candidate-closeout-20260928/test_release_gates.py',
    'docs/process-archive/work-report-20260929-d2-signoff-round.md',
    'docs/process-archive/superpowers/plans/2026-09-29-local-candidate-decision-and-release-prep.md',
    'dispatch-output/local-candidate-closeout-20260928/b_probe_build_tree.py',
    'dispatch-output/local-candidate-closeout-20260928/b_probe_app_paths.py',
    'dispatch-output/local-candidate-closeout-20260928/b_probe_claim_check.py'
)
$MainSha = (git -C $Repo rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0) { throw 'main ref unavailable' }
$CandSha = (git -C $Repo rev-parse refs/heads/codex/local-candidate-closeout).Trim()
if ($LASTEXITCODE -ne 0) { throw 'candidate ref unavailable' }
$DraftIndex = Join-Path $RunRoot 'draft.index'
$SavedIndex = $env:GIT_INDEX_FILE
try {
    $env:GIT_INDEX_FILE = $DraftIndex
    git -C $Repo read-tree $MainSha
    if ($LASTEXITCODE -ne 0) { throw 'read-tree failed' }
    git -C $Repo add -- $DraftPaths
    if ($LASTEXITCODE -ne 0) { throw 'draft add failed' }
    $DraftTree = (git -C $Repo write-tree).Trim()
    if ($LASTEXITCODE -ne 0) { throw 'write-tree failed' }
    $DraftSha = (git -C $Repo commit-tree $DraftTree -p $MainSha -m 'local validation draft; no branch update').Trim()
    if ($LASTEXITCODE -ne 0) { throw 'commit-tree failed' }
} finally {
    if ($null -eq $SavedIndex) { Remove-Item Env:GIT_INDEX_FILE -ErrorAction SilentlyContinue }
    else { $env:GIT_INDEX_FILE = $SavedIndex }
}
```

这会写 Git 对象，但不会产生主线上的新提交或移动分支。记录 `$DraftSha`/`$DraftTree`；临时对象未来可回收，交付前必须将对象及受测 archive 保存到本轮仓外材料中，否则只有字符串不是可恢复交付物。不要以定时改引用的方式保活。

### C2. 固定输入构造 full/trim

在独立 Python 进程加载构造器模块，将 `MASTER` 设为 `$DraftSha`、`CANDIDATE` 设为 `$CandSha`，只调用 `--dry-run`，分别生成 full/trim。示例命令从 `$Evidence` 执行，读取真实扫描输入仅限构造器内部；不得 print `.env`：

```powershell
Push-Location $Evidence
try {
    & $Py -c 'import sys,b_build_snapshot as m; m.MASTER=sys.argv[1]; m.CANDIDATE=sys.argv[2]; sys.argv=["builder","--dry-run","--no-trim"]; raise SystemExit(m.main())' $DraftSha $CandSha
    # 保存输出的 full 完整提交号/树号及 rc。
    & $Py -c 'import sys,b_build_snapshot as m; m.MASTER=sys.argv[1]; m.CANDIDATE=sys.argv[2]; sys.argv=["builder","--dry-run"]; raise SystemExit(m.main())' $DraftSha $CandSha
    # 保存输出的 trim 完整提交号/树号及 rc。
} finally { Pop-Location }
```

- [x] 两场必须 rc=0；正/负对照有效，八键全部实际扫描，无敏感值输出。扫描只覆盖输入键值，不证明未知/轮换旧密钥不存在；形状扫描及内容审查仍要做。缺输入或变量引用时按真实阻塞处理。
- [x] 把真实输出号赋给 `$FullSha`、`$TrimSha`、`$TrimTree`，不得照抄本文旧编号。核查无父、提交数为一、与合并树的差异仅为准许剔除与 CI 修改。
- [x] 准许剔除为 `diag/frozen-index-004`、`diag/frozen-index-005` 两目录及构造器 `TRIM_FILES` 的九个文件。`evals/watershed-cases-r15.json` 保留，原因是当前测试运行期读取。不得临时多剔文件让扫描/CI好看。

### C3. 验收这个 trim 对象

- [x] 加载 `b_snapshot_trim_diff.py` 并将模块 `EVIDENCE` 指向 `$RunEvidence` 后，以固定 `$FullSha/$TrimSha` 执行；两侧成功、完整 nodeid 一致才通过。模块没有该环境变量入口，不能假定 B1 的变量对它生效。

```powershell
Push-Location $Evidence
try {
    & $Py -c 'import sys; from pathlib import Path; import b_snapshot_trim_diff as m; m.EVIDENCE=Path(sys.argv[1]); sys.argv=["diff","--full",sys.argv[2],"--trim",sys.argv[3]]; raise SystemExit(m.main())' $RunEvidence $FullSha $TrimSha
    if ($LASTEXITCODE -ne 0) { throw '固定对象收集差分未通过' }
} finally { Pop-Location }
```

- [x] 对**固定 trim 对象**安全 archive 到新的临时目录，执行同等离线 env 下的 `pytest -m 'not slow' --cov=. --cov-fail-under=70`、Ruff check/format、mypy 和质量守卫。依据实际树检查 CI 命令，不把只 collect 当全量运行。测试数如与历史变化，逐项解释；不得补回已批准剔除的留出集来悄悄改变发布对象。
- [x] 保存固定对象的内容审核：留出集、个人路径、日志/文档中的本地 SHA 是否可在快照解析、密钥形状命中及误报归因。`secret_shape_scan.py --selftest` 应能发现假密钥，再对固定树扫描；运行前核对 Git 预筛命令的真实 rc，命令失败不能作零命中。
- [x] 前后保护对象检查均通过；记录测试输入和运行环境 hashes、对象完整 SHA/树号。后续文档或分支发生变化，不重新构造来替换已经验收的对象。
- [x] 默认交付草案对象和验收材料，不运行 `--expected-tree` 更新旧引用。只有 Owner 后续批准更新引用，才对同一冻结输入使用已验收完整树号；Owner批准 push 还需另行确认实际远端对象。

固定 trim 对象用无父对象 pack 保活，避免仅交付未来会被回收的 SHA。此材料仅留仓外，不上传。先核对确实无父，再用二进制流保存：

```powershell
$SnapshotPack = Join-Path $RunRoot 'validated-trim.pack'
& $Py -c 'import pathlib,subprocess,sys; p=subprocess.run(["git","-C",sys.argv[1],"pack-objects","--stdout","--revs"],input=(sys.argv[2]+"\n").encode("ascii"),capture_output=True,check=True); pathlib.Path(sys.argv[3]).write_bytes(p.stdout)' $Repo $TrimSha $SnapshotPack
if ($LASTEXITCODE -ne 0) { throw '固定对象保存失败' }
$RestoreRepo = Join-Path $RunRoot 'restore-check.git'
git init --bare $RestoreRepo
if ($LASTEXITCODE -ne 0) { throw '恢复验证库创建失败' }
& $Py -c 'import pathlib,subprocess,sys; subprocess.run(["git","-C",sys.argv[1],"unpack-objects"],input=pathlib.Path(sys.argv[2]).read_bytes(),check=True)' $RestoreRepo $SnapshotPack
if ($LASTEXITCODE -ne 0) { throw '对象恢复失败' }
git -C $RestoreRepo rev-parse ($TrimSha + '^{tree}')
# 必须与记录的 $TrimTree 相等；再保存 pack 的 SHA-256。
```

把受测 archive、pack、日志、输入清单/脚本 hashes留在本轮仓外目录。源草案及 full 对象仅作追溯输入，记录其生成文件 hashes；若希望之后完整复跑 full/trim 差分，还须保存 full archive，不把 trim pack说成能恢复所有历史输入。

**C 验收：** 固定 trim 对象可恢复、内容差异符合清单、收集面/完整测试/静态检查成功、输入扫描完整、保护对象不变。公开内容待裁项必须列出；存在待裁内容可写“技术验证通过、公开未批准”，不能写“只等回车”。

## D. 整理风险与远端材料，消除需要 Owner 猜测的部分

**文件责任：** 本轮最终结果记录、现有风险登记表及必要交接摘要。默认只核查/起草，不代签、不升级整套依赖。

- [x] D2草案逐项覆盖已登记风险、受限用途、残余风险、复审日期、失效条件、签署位。标明“草案未签”；复审日期从现有登记表查，不能随意顺延。探针未测/旧值泄漏/真实 rerank 未跑等不能被签字概括成“已排除”。 —— 状态：部分：本轮**未另起竞争草案**——可签文本已在 handoff §6②，其与登记表的一致性由本轮复算器机器判绿；报告 §5 标明草案≠签字
- [x] 盘上未跟踪敏感文件 `_cfg1.txt`、`_cfg_noproxy.txt` 及会话证据残留按路径列处置选项；不输出文件内容。忽略规则只防误提交，不撤销泄漏。删除/移动/轮换等由 Owner 决定，不批量清理未跟踪文件。
- [x] 在新建仓外 bare 审计库获取最新远端头，不修改主仓 origin refs。可复用已有 remote-audit.git 仅在确认无人写它时；不得为检查历史先 push。已知远端地址 `https://github.com/wjt-code-design/fazhi-assistant.git`，先核对实际 remote（输出须不含嵌入凭据）。
- [x] 对实时远端与本地主线判断共同祖先，记录远端头和检查时间；陈旧 origin/master 不作实时事实，无共同祖先时左右提交数不称“领先/落后”。
- [x] 给 Owner 两个可比较的后续选择：临时快照仅用于公开验证；或在真实远端基线上建立整合路线并迁入经审查改动。说明各自是否保留本地主线历史、如何审阅、如何避免传播旧凭据；不默认“主线永不推”，不执行 force/无关历史合并/整仓替换。
- [x] 真实 rerank 未获轮换确认就保持未执行。获确认后，先读 `docs/process-archive/superpowers/plans/2026-09-29-local-candidate-decision-and-release-prep.md` §2C/§5.3 的既有验收脚本与当前 retrieval 实现，核对一轮调用上限，再隔离执行一次。24条断言不等于24次API请求；失败不得自动无限重试，不调用生成模型。前后保护检查和 `(法名,条号)` 验证齐备才报告通过。 —— 状态：未执行，Owner 裁 O-6"保持未跑"。**此处原写"缺 O-3 轮换确认 ⇒ 保持未跑"是错的，已撤回**：O-3 是 `ADMIN_PASSWORD`，而真实 rerank 的前置在旧计划 :79 明写是那把**已暴露的 SiliconFlow key**，同一行还明写 `ADMIN_PASSWORD` 未轮换**不**阻断已授权、已隔离的 rerank 验收。两把凭据别混（报告 §5 顶部与 §7.11）。

**D 验收：** 需要 Owner 决定的每项都有事实、推荐、影响及验证动作，未批准项保持未执行。风险未接受不妨碍整理材料，仍阻止“候选最终就绪”结论。

## E. 最终交付与下一次动作

- [x] 新建唯一结果记录：`C:/Users/33393/Desktop/ai-legal-helper/docs/work-report-20260930-gate-evidence-closeout.md`。各任务只记录状态、对象、命令、实际 rc、证据位置、失败原因；不复制大量原始日志。证据默认仓外，列出绝对路径、hash及恢复方法。
- [x] 报告必须含：接手/交付主线与候选 SHA；实际修改文件；A/B/C/D逐项状态；新旧证据区别；冻结对象可恢复性；保护对象比较；Owner待办；哪些操作未执行。 —— 状态：已由 runner/verify_report.py 机器核过（全部 40 位号可解析、rc 与 JSON 一致）
- [x] 结论只能按事实选择：①“助手侧本地验证与准备完成，仍有Owner决策/审批项”；②“本地验证受阻，准备材料已交付”；③在 Owner 已真实签署、rerank已验收且其他定义满足时才写“候选有条件/最终就绪”。不要因这份文档写完就判阶段完成。
- [x] 更新本文件复选框和结果记录。此时仅文档变化，不使先前固定 trim 对象的业务测试自动失效；若要把新报告加入另一公开快照，那是新对象，要另行核查公开内容和受影响门禁。 —— 状态：本轮完成：报告 docs/work-report-20260930-gate-evidence-closeout.md；固定 trim 对象不因文档改动而失效
- [x] 结束测试会话前恢复 `$env:TEMP = $SavedTaskTemp`；隔离变量只影响本任务进程，不写机器级环境配置。保留本轮仓外证据供审查，不在交付前删除临时目录。 —— 状态：已满足：隔离变量只存在于各次 powershell 子进程内，进程退出即回原值；未写机器级环境；本轮仓外目录保留未删
- [x] 如本轮没有独立 commit 授权，给出精确文件清单和建议提交说明，保留修改。经 Owner另行批准后才按文件逐个暂存；先核对 staged diff，不用 `git add -A`。commit 后复验受影响检查并记录真正SHA；不得把工作区验证冒充提交后验证。 —— 状态：**已按 O-8 执行**（"提两笔，第二笔不提执行书与本报告"）：`285ce3ac8039d387c7d2367d7e401ba3c32bd4f7`（`.gitignore`+7 只探针/门禁）与 `d2d3f5bd0f4b813d491a52162f1117b16aba504f`（2 份在册文档）。逐路径暂存、提前核过 `git diff --cached --name-only`、未用 `git add -A`。**提交后复验**：`status -uno`=0、两个分支引用未动、27 项门禁 OK、复算器 67/67 rc=0、pack 冷恢复 0→2510 且清单逐行相同。⇒ 这一格的"提交后复验"已做，不是拿工作区验证冒充（报告 §9.1）。

**交付终点：** 本文任务中所有可执行项均有结果，受阻项注明“缺什么、谁负责、补齐后复验哪一步”。用户只需作实质决定，不需要再为助手整理上下文。没有新授权时，结束于本地可核查材料，部署仍不执行。

## 2. 执行建议与计划复核

优先串行执行：这些任务共享脚本、证据和固定对象，直接多会话同时运行会混入 latest 选择和输出覆盖。可以并行只读审查 D 或安排独立临时目录的审查；每个写文件/证据目录只有一个负责人。既有并行会话有写入时，暂停重叠文件操作，不回滚它们。

选择隔离输出并复用脚本，而非重建一套验证器：前者补四个输出入口，能保留历史文件；后者增加维护和证据歧义。临时 Git 对象使未提交修复也可被固定验证，无需将 commit 审批作为所有只读工作的前置。不要为维护数字墙而反复跑重型测试；本轮两次探针测试服务已有复跑契约，C完整测试服务不同发布树。

验收真实目标是“失败不会放行、证据对应冻结代码和对象、写入仅在副本、最终结论不越过Owner决定”。测试数量、覆盖率、文件体积或复算条数都不能代替这些目标。写方案所用基线来自本机状态与工作汇报§12；远端、环境和运行结果由接手助手现量，不照抄历史数字。
