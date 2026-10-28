# 下一轮本地候选依赖风险执行书（2026-10-03）

> **最新防重复更新（2026-10-03，23:07+08）：** A／B单项、独立审核及随后新仓外A＋B联合技术验证均已完成。联合162实装／165约束，全量1680通过／10跳过／18不选、85.42%，烟测24/24；新审计34行／7包／21组仍有通报；v2实际50文件扫描通过。见 [联合报告](C:/Users/33393/Desktop/ai-legal-helper/docs/work-report-20261003-joint-candidate.md) 及 [联合续办记录](C:/Users/33393/Desktop/ai-legal-helper/docs/process-archive/superpowers/plans/2026-10-03-joint-candidate-continuation.md)。下文A→D与“联合尚未创建”是早期执行／审核记录，不是当前待执行清单。默认不重跑、不重复下载。当前仅继续模型精确revision补证、风险分案与最终对象裁定材料；正式采纳B／D2／提交等权限不变。

> **给执行助手：只需收到本文件的绝对路径即可接手状态。** 先读页首最新防重复更新；下文A→B→C→D保留复现流程，不要求默认再执行。读完适用的 `AGENTS.md` 后使用 `executing-plans` 逐项核对已有证据。遇到未知事实先核对，停点写入报告；不要因旧报告某个勾选项而重复操作。任务是仓外实验，不自动提交或改变主线。

**目标：** 验证两项疑似闲置依赖能否安全移除，单独验证 setuptools 升级，补齐能取得的模型来源证据，形成可供 Owner 裁定的本地候选材料。

**方法：** 保留原已验候选，使用新的仓外副本和独立 Python 3.11 环境；每项只变一个因素。失败保留原日志与目录，不借局部通过抵销失败。

**技术栈：** Windows PowerShell、Python 3.11、pip／pytest／Ruff／mypy／pip-audit、FastAPI、LangChain 拆分包、Chroma、本地 BGE、Git。

## 接手先看：执行状态与防重复（2026-10-03审核更新）

本书下文A→D是原实验的复现流程，不是要求从头再跑。已收到助手的运行根 `C:/Users/33393/Desktop/fazhi-risk-followup-75542ea22e9b4627a4e090cbc5c7f9aa`；该目录也冻结保留，不把新日志写回它。

| 项 | 已有结果 | 仍需区分的边界 |
|---|---|---|
| A | 独立环境162分发；两包确实移除；原1690 nodeid不变；1680通过／10跳过／18不选，85.42%；离线烟测24/24；审计42行／8包／25组 | 仅仓内受控路径；助手记录Owner已采纳方向，不等于已经整合 |
| B | 独立环境167分发，唯一版本变化setuptools 65.5.0→83.0.0；相同测试结果；审计49行／9包／28组 | 下载已完成，wheel见下；采纳新约束仍待裁；非任意sdist／第三方工具兼容承诺 |
| C | 默认11文件与历史本地SHA匹配；官方精确revision元数据尚缺 | PARTIAL；本机本轮元数据查询已失败，不再次发起相同联网尝试 |
| D | 原交付manifest列71个内容对象，实际73文件；9字段扫描无命中 | 是原执行时点材料，不能将报告副本冒充审核后的主仓文档；风险接受仍未签 |

审核新证据根为 `C:/Users/33393/Desktop/fazhi-risk-review-20261003-e30b720af8364e4c83ded98210868f7b`；单项审核见正式报告§9，后续新联合结果见§10。**下一位助手默认只核对状态并整理剩余项，不重复下载、安装、真实rerank或已通过门禁。** 联合结果来自实际新环境／验收／扫描，而非拼接A／B。联合技术步骤已完成；本书不授权正式采纳B、合并／提交或风险签字。

已下载wheel位于 `C:/Users/33393/Desktop/fazhi-risk-followup-75542ea22e9b4627a4e090cbc5c7f9aa/owner-wheels/setuptools-83.0.0-py3-none-any.whl`，大小1008090，SHA-256 `29b23c360f22f414dc7336bb39178cc7bcbf6021ed2733cde173f09dba19abb3`。新实验确需使用时只读核验并复制，不再索取／下载同一个包。

## 0. 固定事实与权限

- 项目根：`C:/Users/33393/Desktop/ai-legal-helper`；主线基线 `902e2d161e67100ed6d267a08c393538a0abe109`。
- 已验候选根：`C:/Users/33393/Desktop/fazhi-local-candidate-20261002-67944caf51ff48ce9432831cdd62f72b`；`source` 是实验源码，`venv` 是已经通过验收的独立环境，`evidence` 是历史证据。**这三处不得就地改写。** 现有候选只有四文件增量：`backend/requirements.txt`、`backend/knowledge_service.py`、`backend/tests/test_pdf_upload.py`、`backend/tests/test_upload_rate_limit.py`；最终环境 FastAPI 0.141.1、pypdf 6.19.0、pytest 9.1.1。
- 已验旧交付集合 `checkpoint-closeout-20261003` 为 86 文件快照，不更新其 manifest。原项目 `backend/chroma_db`、真实 `.env`、主仓已有脏文档和所有其他助手的未提交内容须保留。
- 新增实验区用 `C:/Users/33393/Desktop/fazhi-risk-followup-<随机标识>`，必须先核对绝对路径不存在；只复制已验候选 `source`。新目录下分别放 `experiment-a`、`experiment-b`、`evidence`，不复制旧venv／DB／模型缓存。缺磁盘空间先停，不回退到共享环境。
- 本轮可做只读检查、仓外源码／环境实验、本地公开语料验证、脱敏报告。**未选服务器，不部署；不合并、提交、push、建PR、写原库、停止他人进程或进行新的真实rerank／生成API调用。** 第四轮 `rerank-round.started` 已存在，10月2日真实7次200许可已用完，不得删标记或重跑。
- 额外下载仍由Owner安排：先使用已有离线缓存，缺包列精确文件名、版本、官方出处和 SHA 给Owner；不要自动联网 `pip install`、隐式 pull 镜像、下载模型或换CPU torch为CUDA。只读官方元数据查询可以做，失败不无限重试。
- D2／Windows有限用途风险未签，复审日期为 **2026-10-05**。执行者整理材料，不能代签或顺延；即便本轮A／B全过，也不声称发布就绪。Linux／远端CI、正常应用完整启动、真实生成／浏览器仍是独立未验项。

以下为可选背景与指定证据输入，不是另一本必须遵循的执行书；本书已包含任务步骤、权限、停点与验收。不要遍历全部历史 `dispatch-output`：

| 目的 | 路径 |
|---|---|
| 当前进度、旧结果的时间边界 | `C:/Users/33393/Desktop/ai-legal-helper/docs/work-report-20261002-local-candidate-completion.md` §11–13 |
| 本轮技术分案与版本候选 | `C:/Users/33393/Desktop/ai-legal-helper/docs/process-archive/superpowers/plans/2026-10-03-dependency-risk-followup.md` |
| 当前风险签字材料 | `C:/Users/33393/Desktop/ai-legal-helper/docs/local-candidate-decision-20261003.md` |
| 失败探针与依赖图 | `C:/Users/33393/Desktop/fazhi-local-candidate-20261002-67944caf51ff48ce9432831cdd62f72b/evidence/dependency-removal-probe-20261003.json`、同目录 `dependency-followup-20261003.json` |
| 源码／原始审计 | 同目录 `final-rerank-after-candidate-source-manifest.json`、`pdf619-installed-audit.json` |
| 源码保护 | 同目录 `protected-before.json`、`original-corpus-before.json`、`risk-followup-protection-after.json` |

注意：旧 `pdf619-current-risks.md` 17时版本说“最终rerank未执行”，已经被当天23时结果取代；本轮以主报告§13为最新。旧审计 **57原始行／10包／32别名组** 只属10月2日实装环境，不能当新实验结果。`dependency-removal-probe-20261003.json` 的四项行为检查成立，但整体 `passed=false`，发生一次被拦截的 `socket.bind`。

## A. 诊断探针并验证最小去包实验

**本项唯一候选代码变化：** 新实验副本 `experiment-a/source/backend/requirements.txt`。其他业务源码沿用已验候选。直接引用 `langchain_text_splitters` 的 `backend/chunking.py` 与 `backend/scripts/eval_chunking.py` 保留。

复制源码时只按已验manifest复制文件，避免把旧实验运行产物当成源码带入；复制后先验hash。以下PowerShell函数在本轮A、B共用，文件已有／越界／hash不同则停止，不覆盖目标：

```powershell
$candidate = 'C:\Users\33393\Desktop\fazhi-local-candidate-20261002-67944caf51ff48ce9432831cdd62f72b'
$sourceManifest = @(Get-Content -LiteralPath (Join-Path $candidate 'evidence\final-rerank-after-candidate-source-manifest.json') -Raw | ConvertFrom-Json)
if ($sourceManifest.Count -eq 1 -and $sourceManifest[0] -is [Array]) { $sourceManifest = @($sourceManifest[0]) }
if (@($sourceManifest).Count -ne 2658) { throw 'Unexpected candidate source manifest' }
function Copy-VerifiedSource([string]$experiment) {
    $sourceRoot = [IO.Path]::GetFullPath((Join-Path $candidate 'source'))
    $destRoot = [IO.Path]::GetFullPath((Join-Path $experiment 'source'))
    if (Test-Path -LiteralPath $destRoot) { throw 'Experiment source already exists' }
    New-Item -ItemType Directory -Path $destRoot | Out-Null
    foreach ($row in $sourceManifest) {
        $sourcePath = [IO.Path]::GetFullPath((Join-Path $sourceRoot $row.path))
        $destPath = [IO.Path]::GetFullPath((Join-Path $destRoot $row.path))
        if (-not $sourcePath.StartsWith($sourceRoot + '\', [StringComparison]::OrdinalIgnoreCase) -or
            -not $destPath.StartsWith($destRoot + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Manifest path escapes source root' }
        if (-not (Test-Path -LiteralPath $sourcePath -PathType Leaf) -or
            (Get-FileHash -LiteralPath $sourcePath -Algorithm SHA256).Hash -ne $row.sha256) { throw 'Candidate source differs from frozen manifest' }
        $destDir = Split-Path -Parent $destPath
        if (-not (Test-Path -LiteralPath $destDir)) { New-Item -ItemType Directory -Path $destDir -Force | Out-Null }
        Copy-Item -LiteralPath $sourcePath -Destination $destPath
        if ((Get-FileHash -LiteralPath $destPath -Algorithm SHA256).Hash -ne $row.sha256) { throw 'Copied source differs from manifest' }
    }
}
```

- [ ] **A1 基线与新源码。** 记录主仓 `git rev-parse HEAD`、`git status --short --untracked-files=no`、原库与旧保护清单；记录已验候选源码2658文件manifest与当前指纹。`backend/.env` 只比较整文件SHA，不输出值。记录候选requirements／约束与167分发清单。若受保护对象／HEAD／refs与历史不一致，停止使用旧结果并报具体差异，不刷新旧基线。并行助手新增的前端／文档脏项应单独登记当前路径与hash，不回滚，也不以旧“只有一个脏文档”的固定数量判断它们损坏。然后用下列命令建立唯一的新实验根并调用 `Copy-VerifiedSource $experimentA`；复制结果必须2658文件、全hash相符，且不带额外文件：

```powershell
$runRoot = Join-Path 'C:\Users\33393\Desktop' ('fazhi-risk-followup-' + [guid]::NewGuid().ToString('N'))
if (Test-Path -LiteralPath $runRoot) { throw 'New experiment root must not exist' }
$experimentA = Join-Path $runRoot 'experiment-a'
$newEvidence = Join-Path $runRoot 'evidence'
New-Item -ItemType Directory -Path $runRoot | Out-Null
New-Item -ItemType Directory -Path $experimentA, $newEvidence | Out-Null
New-Item -ItemType Directory -Path (Join-Path $experimentA 'evidence') | Out-Null
Copy-VerifiedSource $experimentA
```

- [ ] **A2 定位探针失败（已有定位，不默认重跑）。** 如确需复现，复制 `C:/Users/33393/Desktop/fazhi-local-candidate-20261002-67944caf51ff48ce9432831cdd62f72b/evidence/dependency-removal-probe-20261003.py` 到新 `experiment-a/evidence/diagnose-bind.py`，用原已验候选 `venv/Scripts/python.exe -I -B` 运行复制件；复制件的 `ROOT` 因所在目录而指向 `experiment-a`，其 `source` 已在A1建立。保留原失败JSON不变。对 `socket.bind` 的Python audit事件只记录调用栈中的文件名、函数名和行号，不记录绑定地址、端口、环境变量或请求头；先保持拒绝，运行一次确认栈。已证实际原因是urllib3导入期 `_has_ipv6` 探测，不是事件循环或应用监听。只可对已核对的这一调用点、内存检查host为loopback且port=0的绑定做探针内放行；其他bind、所有connect／DNS、`subprocess.Popen` 仍拒绝。新的调用点不能照搬放行。记录阳性拒绝检查与真实退出码；开放监听立即停止。同一命令失败先分析，完全相同命令最多重试一次，同一问题连续三次修复失败即停。

  可把旧探针的 audit 分支最小改成下列形状，生成新文件名／日志名，禁止把 `args` 直接写到输出：

```python
import traceback

if event == "socket.bind":
    bind_stack = [
        {"file": Path(frame.filename).name, "function": frame.name, "line": frame.lineno}
        for frame in traceback.extract_stack(limit=12)
    ]
    output = Path(__file__).resolve().parent / "bind-callstack.json"
    with output.open("x", encoding="utf-8") as stream:
        json.dump(bind_stack, stream, indent=2)
    raise RuntimeError("Bind blocked; sanitized stack recorded")
```

  决定是否放行时，先看实际 `args` 的结构；只在内存检查已证 `_has_ipv6` 调用点、host为IPv4/IPv6 loopback且port=0，解析失败保持拒绝，不把参数写出。该已证探测不需要配对连接，不再泛化到允许connect。第一次拒绝诊断是预期结果，不把它写成修复失败。
- [ ] **A3 核对引用。** 在业务、实际CI／运维入口及使用中的 `--adapter MODULE:CALLABLE` 清单搜索 `langchain`／`langchain_community` 的直接和字符串动态加载。现有AST核查覆盖268个Python文件，但外部adapter未覆盖。若发现必须保留的实际入口，记录调用方并取消本项删包；已用adapter清单无法取得时，把A限定为仓内受控路径实验，不声称对所有外部adapter兼容。不要以“没有import”为充分证明。
- [ ] **A4 创建独立实验。** 为 A 建新venv；使用原已验缓存路径和 `--no-index` 安装 CPU torch、`backend/requirements-dev.txt`。复制 `evidence/candidate-constraints.txt` 到实验目录，只从新约束中移除 `langchain==0.1.20`、`langchain-community==0.0.38`，保持其余精确项（含 `langchain-text-splitters==0.0.2`）不变。仅在新源码 requirements 作下面三行改动，不改旧候选或主仓：

```diff
-langchain>=0.1,<0.2
-langchain-community>=0.0.38,<0.1
+langchain-text-splitters>=0.0.2,<0.1
```

  安装搜索目录为旧 `AppData/Local/Temp/legal-closeout-20260928/wheelhouse` 及已验候选的 `cached-extras`、`cached-extras-2`、`cached-pdf-619`。**不要直接运行旧 `install-candidate.ps1`**：它通过自身位置指向旧候选、旧venv和旧证据文件名。新实验命令须显式指向新解释器、复制的约束和四个已有缓存目录；先单独安装 `torch==2.6.0+cpu`，再 `-r experiment-a/source/backend/requirements-dev.txt`。如果任一精确wheel缺失，记录pip完整错误与缺包清单，停止安装，不用 `--no-deps`、在线补包或共享venv冒充新环境。

  以下只执行A的约束复制与离线安装；`$runRoot`／`$experimentA` 已在A1建立。先做A3引用核对，再改两个实验文件。日志与退出码逐条保存，不直接运行整块后只看最后一行退出码。每条外部命令可用下面函数代替裸调用；日志／JSON使用新名字，禁止覆盖历史结果。函数只记录命令参数，不用于任何带真实凭据的命令。

```powershell
function Invoke-Recorded([string]$label, [string]$program, [string[]]$commandArgs, [int[]]$allowedExitCodes = @(0)) {
    $log = Join-Path $newEvidence ($label + '.log')
    $record = Join-Path $newEvidence ($label + '-command.json')
    if ((Test-Path -LiteralPath $log) -or (Test-Path -LiteralPath $record)) { throw 'Preserve existing command evidence' }
    $started = [DateTimeOffset]::Now.ToString('o')
    & $program @commandArgs 2>&1 | Out-File -LiteralPath $log -Encoding utf8
    $rc = $LASTEXITCODE
    [ordered]@{command=@($program)+$commandArgs;cwd=(Get-Location).Path;started=$started;ended=[DateTimeOffset]::Now.ToString('o');exit_code=$rc} |
        ConvertTo-Json -Depth 4 | Out-File -LiteralPath $record -Encoding utf8
    if ($null -eq $rc -or $rc -notin $allowedExitCodes) { throw ('Command failed: ' + $label) }
}
```

  例如安装pip的裸命令换为 `Invoke-Recorded 'a4-pip' $pyA @('-m','pip','install','--no-index','--find-links',(Join-Path $candidate 'cached-extras'),'-c',(Join-Path $experimentA 'candidate-constraints.txt'),'pip==26.2.1')`。venv创建、其余安装、收集／门禁都各用一个label。原A的历史退出码缺口不靠事后补写填平；只有新执行可以留下新记录。

```powershell
Copy-Item -LiteralPath (Join-Path $candidate 'evidence\candidate-constraints.txt') -Destination (Join-Path $experimentA 'candidate-constraints.txt')
$bootstrapPy = 'C:\Users\33393\AppData\Local\Temp\legal-closeout-20260928\venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $bootstrapPy)) { throw 'Python 3.11 bootstrap missing; list installed Python 3.11 paths with py -0p before proceeding' }
& $bootstrapPy -m venv (Join-Path $experimentA 'venv')
$pyA = Join-Path $experimentA 'venv\Scripts\python.exe'
$wheelArgs = @('--no-index', '--find-links', 'C:\Users\33393\AppData\Local\Temp\legal-closeout-20260928\wheelhouse', '--find-links', (Join-Path $candidate 'cached-extras'), '--find-links', (Join-Path $candidate 'cached-extras-2'), '--find-links', (Join-Path $candidate 'cached-pdf-619'), '-c', (Join-Path $experimentA 'candidate-constraints.txt'))
# 先用 apply_patch 改实验副本 requirements 与 constraints，复核 diff 后才安装：
& $pyA -m pip install --no-index --find-links (Join-Path $candidate 'cached-extras') -c (Join-Path $experimentA 'candidate-constraints.txt') 'pip==26.2.1'
& $pyA -m pip install @wheelArgs 'torch==2.6.0+cpu'
& $pyA -m pip install @wheelArgs -r (Join-Path $experimentA 'source\backend\requirements-dev.txt')
```
- [ ] **A5 实验验收。** 新venv `python -m pip check` 退出0；实装清单里 `langchain` 和 `langchain-community`确实不存在，`langchain-text-splitters`确实存在且满足直接声明。用新解释器在新源码 `backend` 下运行 `python -m pytest --collect-only -m 'not slow' -q`，对照旧1690 nodeid清单：既有测试没有无解释消失。定向跑 `tests/test_chunking.py`、`tests/test_pdf_upload.py`、`tests/test_upload_rate_limit.py`，然后按旧入口运行 Ruff check／format、mypy、`pytest -m 'not slow' --cov=. --cov-fail-under=70 -q`。每条命令保存cwd、开始／结束、真实退出码和独立日志；出现失败先分析，不改测试或放松门槛。

  在任何项目模块导入／pytest前，把测试进程的 `CHROMA_DIR` 指向新实验根下独立空目录，`DATABASE_URL=sqlite:///<实验根>/runtime/test-app.db`，`QUOTA_DB=<实验根>/runtime/test-quota.sqlite`；创建runtime目录，使用本地embedding、`RERANK_ENABLED=false`、`HF_HUB_OFFLINE=1`、`TRANSFORMERS_OFFLINE=1`，禁用追踪，清空当前进程的所有真实API key及代理环境变量。沿用旧候选 `evidence/environment.ps1` 中的测试用 JWT／LLM fixture 值，但**不要 dot-source 该文件**，其路径变量指向旧候选。保持 `PYTHONOPTIMIZE` 空，防断言被跳过。若 `conftest` 在源码默认位置仍创建空Chroma，先只读验证0记录再移入新实验runtime，保留日志；非空则停止，不覆盖。

  在安装结束后，在本轮专用PowerShell进程中设 `$testRoot` 为本轮已经存在的 `$experimentA` 或 `$experimentB`，执行下列设置；不要在该进程夹带其他项目任务。若换了窗口，先重新设 `$candidate`、`$runRoot` 的实际绝对路径以及 `$experimentA/$experimentB/$pyA/$pyB/$newEvidence`，不能假定变量自动继承；不重新执行A1建目录。不要打印环境值。

```powershell
$testRoot = $experimentA  # B则改为 $experimentB
$testRuntime = Join-Path $testRoot 'runtime'
New-Item -ItemType Directory -Path $testRuntime -Force | Out-Null
$testTmp = Join-Path $testRuntime 'tmp'
New-Item -ItemType Directory -Path $testTmp -Force | Out-Null
$env:TEMP = $testTmp
$env:TMP = $testTmp
$env:COVERAGE_FILE = Join-Path $testRuntime '.coverage'
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:PYTHONPATH = ''
$env:PYTHONOPTIMIZE = ''
$env:PYTEST_ADDOPTS = ''
$env:HF_HUB_OFFLINE = '1'
$env:TRANSFORMERS_OFFLINE = '1'
$env:ANONYMIZED_TELEMETRY = 'false'
$env:LANGCHAIN_TRACING_V2 = 'false'
$env:LANGSMITH_TRACING = 'false'
$env:OTEL_SDK_DISABLED = 'true'
$env:EMBEDDING_PROVIDER = 'local'
$env:RERANK_ENABLED = 'false'
$env:EMBEDDING_QUOTA_TOTAL = '0'
$env:RERANK_QUOTA_TOTAL = '0'
$env:JWT_SECRET = 'test-jwt-secret-for-ci-only'
$env:LLM_API_KEY = 'fixture-only-not-for-real-calls'
$env:LLM_BASE_URL = 'https://fixture.invalid/v1'
$env:CHROMA_DIR = Join-Path $testRuntime 'empty-kb'
$env:DATABASE_URL = 'sqlite:///' + ((Join-Path $testRuntime 'test-app.db') -replace '\\','/')
$env:QUOTA_DB = Join-Path $testRuntime 'test-quota.sqlite'
foreach ($keyName in @('ADMIN_PASSWORD','RERANK_API_KEY','RERANK_BASE_URL','RERANK_NATIVE_URL','RERANK_MODEL','RERANK_MODELS','EMBEDDING_API_KEY','ZHIPUAI_API_KEY','DASHSCOPE_API_KEY','SILICONFLOW_API_KEY','LLM_MODELS_JSON','LANGCHAIN_API_KEY','LANGSMITH_API_KEY','HTTP_PROXY','HTTPS_PROXY','ALL_PROXY')) {
    [Environment]::SetEnvironmentVariable($keyName, '', 'Process')
}
```

  使用新venv在 `$testRoot/source/backend` 执行下列命令，**逐条**留日志和即时退出码，失败即停下诊断：

```powershell
Set-Location (Join-Path $testRoot 'source\backend')
& $pyA -m pip check
& $pyA -m pytest --collect-only -m 'not slow' -q
& $pyA -m pytest -q tests/test_chunking.py tests/test_pdf_upload.py tests/test_upload_rate_limit.py
& $pyA -m ruff check .
& $pyA -m ruff format --check .
& $pyA -m mypy .
& $pyA -m pytest -m 'not slow' --cov=. --cov-fail-under=70 -q
```

  B运行时以上命令把 `$pyA` 全部换成 `$pyB`。B须先完成自己的配置／安装，再单独运行。离线真实公开库烟测也属于A、B受影响验证：从旧候选 `public-kb` 精确复制到各自实验 `runtime/public-kb`；复制前后比对旧库文件清单和SHA，烟测后再比对旧库不变。只将 `CHROMA_DIR` 指向各自的公开副本并继续保持rerank关闭，执行该实验源码 `backend/scripts/smoke_citation_fast.py`，预期24/24断言且退出0；若需修改golden或数据才通过，记失败而非变更判据。烟测后恢复空库路径，不能把公开副本目录交付为脱敏日志。
- [ ] **A6 新审计。** 仅审计新venv实装分发，保存原始JSON和退出码。在A的backend目录设 `$auditPath = Join-Path $experimentA 'evidence/installed-audit.json'`，确认不存在后执行 `Invoke-Recorded 'a6-audit' $pyA @('-m','pip_audit','--format=json','--output',$auditPath) @(0,1)`；B分别改成 `$experimentB/$pyB` 和新label。rc=1只有在JSON有效且包含非空通报时才是预期审计红；没有JSON、解析失败、服务查询失败不算“扫描完成”。不得加忽略ID或只扫描requirements。每条记录的ID与aliases形成图，以连通分量计全局组；不要按ID数量或每包分组之和冒充全局数。A的15行消失中14行无其他在装命中，但独立组只减少7；另1行仍由langsmith命中。`torch+cpu`继续被跳过时单列限制。旧快照不当新扫描。

**A的完成标准：** 新环境真正缺这两包、全量非slow和工具门禁通过、实装与声明自洽、审计对象正确、原候选及原库保护通过。任一条件不满足，结论写“删包实验未通过”，可继续做C／D的只读工作；B在干净独立环境另案，不从失败A环境继承包状态。

## B. setuptools 单因素升级

- [ ] **B1 精确来源。** 再查本机现有缓存有无 `setuptools-83.0.0-py3-none-any.whl`，找到后校验大小 **1008090字节**及SHA-256 `29b23c360f22f414dc7336bb39178cc7bcbf6021ed2733cde173f09dba19abb3`。不存在时给Owner下载单：[官方wheel](https://files.pythonhosted.org/packages/5d/40/e1e72872c6354b306daef1703549e8e83b4d43cfea356311bf722a043752/setuptools-83.0.0-py3-none-any.whl)。缓存命中或Owner下载后，核验通过再复制到本轮新目录 `owner-wheels`，原件不删除。缺包不阻止C／D只读工作，不自行下载。版本来自[官方PyPI元数据](https://pypi.org/pypi/setuptools/83.0.0/json)，并不保证该版本与应用兼容。
- [ ] **B2 新建与A独立的环境。** 原源码和依赖从已验候选拷贝，新约束只将 `setuptools==65.5.0` 替换成 `setuptools==83.0.0`；不同时删LangChain或升级模型栈。严格离线安装CPU torch及原需求／dev需求。保留安装报告、`pip check`和实装清单，不能在旧venv执行 `pip install --upgrade`。约束本身不会安装或升级包，必须先把已校验的83.0.0 wheel作为显式安装对象，再检查 `pip show setuptools` 为83.0.0。实验B可沿用A4的旧四个只读缓存目录，但**必须拥有独立的source／constraints／venv／runtime／日志**。示例：

```powershell
$experimentB = Join-Path $runRoot 'experiment-b'
if (Test-Path -LiteralPath $experimentB) { throw 'Experiment B must start fresh' }
New-Item -ItemType Directory -Path $experimentB | Out-Null
Copy-VerifiedSource $experimentB
Copy-Item -LiteralPath (Join-Path $candidate 'evidence\candidate-constraints.txt') -Destination (Join-Path $experimentB 'candidate-constraints.txt')
# 先用 apply_patch 只替换实验B约束中的 setuptools==65.5.0 为 setuptools==83.0.0。
& $bootstrapPy -m venv (Join-Path $experimentB 'venv')
$pyB = Join-Path $experimentB 'venv\Scripts\python.exe'
$constraintsB = Join-Path $experimentB 'candidate-constraints.txt'
$wheelB = Join-Path $runRoot 'owner-wheels\setuptools-83.0.0-py3-none-any.whl'
if (-not (Test-Path -LiteralPath $wheelB)) { throw 'Verified Owner wheel missing; BLOCKED-DOWNLOAD' }
if ((Get-FileHash -LiteralPath $wheelB -Algorithm SHA256).Hash -ne '29B23C360F22F414DC7336BB39178CC7BCB6021ED2733CDE173F09DBA19ABB3') { throw 'Wheel hash mismatch' }
& $pyB -m pip install --no-index --find-links (Join-Path $candidate 'cached-extras') -c $constraintsB 'pip==26.2.1'
& $pyB -m pip install --no-index -c $constraintsB $wheelB
$wheelArgsB = @('--no-index', '--find-links', 'C:\Users\33393\AppData\Local\Temp\legal-closeout-20260928\wheelhouse', '--find-links', (Join-Path $candidate 'cached-extras'), '--find-links', (Join-Path $candidate 'cached-extras-2'), '--find-links', (Join-Path $candidate 'cached-pdf-619'), '-c', $constraintsB)
& $pyB -m pip install @wheelArgsB 'torch==2.6.0+cpu'
& $pyB -m pip install @wheelArgsB -r (Join-Path $experimentB 'source\backend\requirements-dev.txt')
```

  wheel进入 `owner-wheels` 前先核对文件大小和SHA；每个安装命令即时保存 `$LASTEXITCODE`，失败不得跳到下一行继续。B的测试隔离变量与A5相同，但路径指向B自己的runtime；不能借A的状态或日志。
- [ ] **B3 兼容验证。** 重点检查当前 `jieba/_compat.py` 中 `pkg_resources` 缺失时的字典资源回退，做实字典读取／中文分词；核对其他已安装包中的实际 `pkg_resources` 导入路径与运行结果。随后跑与A相同的定向／全量非slow、Ruff／mypy、当前实装审计。setuptools新版本使既有行为失败时，记录首个根因，保留失败环境，不补一个全局假 `pkg_resources` 模块。

**B的完成标准：** 只有setuptools实装版本变化，验收与新审计证据同源，受影响功能和全量非slow通过。审计无公告不等于零未知风险。B若因wheel缺失未执行，结论必须写“BLOCKED-DOWNLOAD”，不得写“升级通过”。

## C. 模型来源只读核验

- [ ] 固定当前本地BGE默认revision `f03589ceff5aac7111bd60cfc7d497ca17ecac65`，缓存根为 `C:/Users/33393/.cache/huggingface/hub/models--BAAI--bge-base-zh-v1.5`。历史逐文件SHA输入是已验候选 `evidence/bge-provenance-preflight.json` 的 `files`，仅选相同revision；核对 `refs/main`、文件集合／大小／SHA。默认11文件为 `1_Pooling/config.json`、`config.json`、`config_sentence_transformers.json`、`modules.json`、`pytorch_model.bin`、`README.md`、`sentence_bert_config.json`、`special_tokens_map.json`、`tokenizer.json`、`tokenizer_config.json`、`vocab.txt`。不改refs、不替换模型。
- [ ] 优先取得该**精确revision**的小体积官方Git blob ID／LFS SHA元数据。官方[tree API](https://huggingface.co/api/models/BAAI/bge-base-zh-v1.5/tree/f03589ceff5aac7111bd60cfc7d497ca17ecac65?recursive=true)只要文件元数据，不要权重。此前curl超时，本轮不同方式urllib也WinError10061失败；本轮额度已使用，不再自动请求。Owner可从另一可达设备提供完整原始JSON及官方URL／查询时间：按分页继续到没有下一页；只提供文件名／大小或截图不足。10个小文件的Git blob OID用 `SHA1(b'blob ' + str(len(content)).encode('ascii') + b'\0' + content)` 比；BIN用LFS字段的完整SHA-256与实际大小比。缺任何一项／不是同一revision，保持PARTIAL。查询成功也不加载新文件或改refs。
- [ ] 严禁为弥补元数据缺口直接下载约409MB权重；`model.safetensors`在另一个缓存revision，不是当前默认加载路径。权重哈希与依赖漏洞分开评估。此任务不重建1528条公开向量索引，不增加云端调用。

**C的完成标准：** 11个默认文件都能绑定到相同官方精确revision且字节匹配，才可把“来源逐文件”从PARTIAL提升；否则仍为PARTIAL，写明确缺项。来源通过也不能宣称Torch／ST／Transformers漏洞关闭。

## D. 风险整合与交付

- [ ] 将A／B各自新审计、版本／测试／限制和C来源状态写入正式技术报告 `C:/Users/33393/Desktop/ai-legal-helper/docs/work-report-20261003-dependency-risk-execution.md` 的新增带日期小节；同步 Owner 汇总 `C:/Users/33393/Desktop/ai-legal-helper/docs/work-report-20261003-owner-summary-20261003.md`。四分法写清：已完成、失败、未验、Owner待裁。10月2日历史报告和冻结证据不改；纠正本轮报告措辞时指出旧时点／新依据，不事后补造日志或时间。手工近似时间和mtime不能证明精确执行顺序。
- [ ] 对剩余模型链、LangChain core／适配包、Chroma通报逐包写下一步；不要混进A／B的依赖变化。当前ST2.7.0声明 `transformers<5`，不能只强装Transformers5；core与适配包也要先解约束。Chroma公告的空fix列表需查官方条件与隔离副本兼容，不据此直接换持久格式。
- [ ] 在本轮新交付集合做精确文件清单和9字段完整内存值／形状扫描；正控必须命中，负控0命中。只纳入拟交付的补丁、声明／安装、脱敏日志、风险原始JSON和报告；不要复制含74历史HNSW产物的272MB基线、`.env`、数据库、权重或旧受限快照。新清单不能覆盖旧72／86文件薄包。

  对**新集合**使用下面完整扫描器（以apply_patch保存到新 `$runRoot/evidence/check-delivery.py`），只复用冻结源码中的凭据读取函数与形状规则，不运行旧脚本main／整盘扫描。将扫描结果放集合外；先生成内容manifest，再将内容与manifest一并扫描，避免“终扫JSON自己未进清单”的计数歧义。执行命令为 `Invoke-Recorded 'd-hygiene' $pyA @('-I','-B',(Join-Path $runRoot 'evidence/check-delivery.py'),$deliveryRoot,(Join-Path $runRoot 'evidence/delivery-hygiene.json'))`，其中 `$deliveryRoot` 是新建拟交付目录的完整绝对路径。原71项／73文件集合保留，不为了补本次审核改其旧manifest。

```python
import importlib.util
import json
import re
import sys
import winreg
from datetime import datetime
from pathlib import Path

helpers = Path('C:/Users/33393/Desktop/fazhi-local-candidate-20261002-67944caf51ff48ce9432831cdd62f72b/source/dispatch-output/local-candidate-closeout-20260928')
def load_module(name, filename):
    spec = importlib.util.spec_from_file_location(name, helpers / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
reader = load_module('value_reader', 'b_worktree_value_scan.py')
rules = load_module('shape_rules', 'secret_shape_scan.py')
values = reader.load_values()
with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r'SYSTEM\CurrentControlSet\Control\Session Manager\Environment') as key:
    values['WINDOWS_MACHINE_RERANK_API_KEY'] = winreg.QueryValueEx(key, 'RERANK_API_KEY')[0].encode('utf-8')
assert set(values) == set(reader.CENSUS_KEYS) | {'WINDOWS_MACHINE_RERANK_API_KEY'}
assert all(value.strip() for value in values.values()), 'Incomplete credential census'
def value_hits(content):
    return {name for name, value in values.items() if value in content}
patterns = [re.compile(pattern) for pattern in rules.PATTERNS.values()]
positive_value = value_hits(b'|'.join(values.values())) == set(values)
positive_shape = all(pattern.search(sample) for pattern, sample in zip(patterns, [
    'sk-' + 'Z'*32, 'AKIA' + 'A'*16, 'LTAI' + 'A'*12,
    '-----BEGIN ' + 'PRIVATE KEY-----', 'eyJ' + 'A'*12 + '.eyJ' + 'B'*8]))
bundle = Path(sys.argv[1]).resolve()
output = Path(sys.argv[2]).resolve()
assert bundle.is_dir() and not output.is_relative_to(bundle) and not output.exists()
files = sorted(path for path in bundle.rglob('*') if path.is_file())
value_files = shape_files = forbidden_files = 0
for path in files:
    content = path.read_bytes()  # unreadable file raises; no clean conclusion
    value_files += bool(value_hits(content))
    shape_files += any(pattern.search(content.decode('utf-8', errors='replace')) for pattern in patterns)
    forbidden_files += (path.name == '.env' or (path.name.startswith('.env.') and path.name != '.env.example')
                        or path.suffix.lower() in {'.db','.sqlite','.sqlite3','.bin','.safetensors','.zip','.pickle'})
passed = positive_value and positive_shape and bool(files) and not (value_files or shape_files or forbidden_files)
result = dict(checked_at=datetime.now().astimezone().isoformat(), files=len(files), fields=9,
              value_positive=positive_value, shape_positive=positive_shape, value_hit_files=value_files,
              shape_hit_files=shape_files, forbidden_files=forbidden_files, passed=passed)
with output.open('x', encoding='utf-8') as stream:
    json.dump(result, stream, indent=2)
raise SystemExit(0 if passed else 1)
```

  输入／规则脚本缺失、任一凭据为空、正控不命中、文件不可读都判扫描无效。命中只记数量或脱敏路径／字段名；不调用旧 `scan_text()` 输出长度、前后缀或上下文。0命中不是“0误报”或证明所有未知凭据都被检出。manifest须逐对象核对相对path／bytes／SHA、无漏列／多列（manifest自身明确排除）；这里只生成文件卫生读数，不替代manifest校验。
- [ ] 验后再次检查主仓HEAD／refs、原脏文档SHA、冻结文件、原Chroma38文件与保护清单41对象；核对新实验副本相对已验候选的精确差异。具体输入均在已验候选 `evidence`：`protected-before.json`（绝对path与SHA）、`original-corpus-before.json`（原库完整相对path／bytes／SHA）、`local-config-before.json`（整.env SHA）、`refs-before.txt`。主仓HEAD应为902e2d1完整值；逐对象用 `Get-FileHash -Algorithm SHA256` 比，原库须同时核对集合无增减。禁止调用旧 `verify-protection-after.ps1` 写回冻结 evidence；它的“一个脏项”断言也已不适用于并行工作区。把本轮开始与结束快照写入新目录，其他助手的变化只登记，不回滚。文件卫生不是全Git历史或发布许可。D2仍由Owner决定，本报告不能代签或延长10月5日复审期限。

**本轮完成口径：** A／B分别通过或如实标阻塞／失败，C给出“精确核验”或“PARTIAL＋缺项”，D提供可追溯材料和有效保护检查。只要新环境发生实质变更，旧86文件交付集合与10月2日7次200结果不能被说成“新环境已验真实rerank”；新的真实请求需另有精确授权。

**当前剩余路径（不自动扩成整栈升级）：** 先由Owner提供C的官方精确revision元数据，或明确将PARTIAL纳入具体风险裁定；再明确是否采纳B。A＋B合用只能在新仓外目录验证：从A requirements与原候选源码起步，约束删两包并换setuptools一行，干净离线安装，跑A5整套＋公开库烟测＋同源实装审计，保留失败。这个联合实验不在本书已完成结果内，需获得明确续办范围后才开始。模型链／LangChain活跃适配／Chroma仍按分案先解约束、查公告，不借本书自动升级。最终D2裁定必须指向最终选定的源码、约束、实装与证据，不能把旧四文件候选的裁定直接转嫁到新依赖集合。通过后仍不授权提交、push、真实库写入或部署。

## 执行纪律与自审

每项开始前确认其输入和输出路径；日志一轮一个新文件名，失败文件不覆写。命令失败先分析再决定是否重试，完全相同的命令最多重试一次；同一bug连续三次修复失败时停止并报告架构假设。秘密不打印、不记长度／哈希／请求头。测试正负例独立于被测实现，不能靠删除守卫、修改金标或放宽范围凑通过。

交付时自审这五点：实际改动是否只在本轮新实验区；每个“通过”是否有退出码和对象指纹；新审计是否确实针对新实装；失败／跳过是否在报告显眼处；D2与发布边界是否仍准确。将**这份执行书、唯一新报告、精确新证据目录路径**交给Owner即可，不需要派发另一个任务去复述进度。
