# 本地候选依赖下载任务

日期：2026-09-28  
用途：供另一位助手单独执行候选依赖下载，完成后由主任务继续安装与验证。

## 任务目标

将本地候选 Python 依赖准备为可复用 wheel 文件，保存到仓库之外的临时目录。当前主要等待公开 PyPI 下载；前端检查已完成，不需要下载前端依赖。

## 已知状态

- 候选工作树：`C:\Users\33393\.codex\worktrees\local-candidate-closeout\ai-legal-helper`
- 本轮证据目录：`C:\Users\33393\Desktop\ai-legal-helper\dispatch-output\local-candidate-closeout-20260928`
- 候选 Python：`C:\Users\33393\AppData\Local\Temp\legal-closeout-20260928\venv\Scripts\python.exe`
- 目标 wheelhouse：`C:\Users\33393\AppData\Local\Temp\legal-closeout-20260928\wheelhouse`
- 临时环境已经安装 `torch==2.6.0+cpu`，本任务不下载或替换 torch。
- 基线依赖解析清单 `resolve-pdf.json` 有 156 个精确包版本，不含 torch；其中 pypdf 为 `6.16.1`、FastAPI 为 `0.110.3`、Starlette 为 `0.37.2`。
- 额外需要准备 FastAPI 升级候选 `fastapi==0.141.1` 和其解析候选 `starlette==1.7.0`。后续主任务会依次在隔离环境安装和测试。
- 原先的下载进程已经停止。未完成的 `pip install` 不算安装成功；pip 下载缓存予以保留。

## 执行步骤

在 PowerShell 中执行以下命令。它从既有解析报告提取 156 个精确版本，检查清单形状后下载 wheel；随后单独下载 FastAPI 升级候选，避免把两个 FastAPI 版本放进同一个安装请求。

```powershell
$candidatePython = 'C:\Users\33393\AppData\Local\Temp\legal-closeout-20260928\venv\Scripts\python.exe'
$reportPath = 'C:\Users\33393\Desktop\ai-legal-helper\dispatch-output\local-candidate-closeout-20260928\resolve-pdf.json'
$bundleDir = 'C:\Users\33393\AppData\Local\Temp\legal-closeout-20260928\wheelhouse'

if (-not (Test-Path -LiteralPath $candidatePython)) { throw "候选 Python 不存在：$candidatePython" }
if (-not (Test-Path -LiteralPath $reportPath)) { throw "依赖解析报告不存在：$reportPath" }

$resolution = Get-Content -LiteralPath $reportPath -Raw | ConvertFrom-Json
if ($resolution.install.Count -ne 156) { throw "解析清单数量不是预期的 156；停止并报告实际数量。" }
if ($resolution.install | Where-Object { $_.metadata.name -eq 'torch' }) { throw '解析清单意外包含 torch；停止，避免下载错误的 CPU/CUDA 包。' }

$pins = $resolution.install | ForEach-Object { '{0}=={1}' -f $_.metadata.name, $_.metadata.version }
New-Item -ItemType Directory -Path $bundleDir -Force | Out-Null

& $candidatePython -m pip wheel --no-deps --wheel-dir $bundleDir @pins
$baseExitCode = $LASTEXITCODE
if ($baseExitCode -ne 0) { throw "基线候选 wheel 下载/构建失败，退出码 $baseExitCode；先检查错误，不要原样反复重试。" }

& $candidatePython -m pip wheel --no-deps --wheel-dir $bundleDir 'fastapi==0.141.1' 'starlette==1.7.0'
$upgradeExitCode = $LASTEXITCODE
if ($upgradeExitCode -ne 0) { throw "FastAPI 升级候选 wheel 下载失败，退出码 $upgradeExitCode；先检查错误，不要原样反复重试。" }

$wheelFiles = Get-ChildItem -LiteralPath $bundleDir -Filter '*.whl' -File
[pscustomobject]@{
    BasePinCount = $pins.Count
    BaseExitCode = $baseExitCode
    UpgradeExitCode = $upgradeExitCode
    WheelCount = $wheelFiles.Count
    Wheelhouse = $bundleDir
}
```

`jieba==0.42.1` 在解析报告中是源码包，`pip wheel` 会为它构建 wheel。若编译/构建失败，保留完整错误，不要改项目依赖或另装编译器。

## 注意事项

- 只做下载和 wheel 构建。本任务**不要运行 `pip install`**；安装、`pip check`、测试和审计由主任务继续执行。
- 所有输出保存在 `AppData\Local\Temp\legal-closeout-20260928\wheelhouse`，不要把下载文件放入仓库，也不要提交 wheelhouse。
- 不修改候选工作树、requirements、共享 Python 环境、真实数据库、`.env` 或 Git 历史；不运行模型、服务、部署或推送。
- 不下载 CUDA 版 torch，不升级或重建 Torch，也不下载嵌入/重排模型。当前清单明确排除了 torch。
- 下载若失败，先记录失败包名、pip 错误末尾和退出码；分析网络、PyPI 响应或构建原因后再决定下一步。相同命令不要盲目重复执行。
- 不要输出凭据或整个环境变量。该任务不应读取 `.env`。

## 完成后回报

请回复：

1. 两步命令的退出码（基线包与 FastAPI/Starlette 候选）。
2. wheelhouse 的绝对路径和最终 `.whl` 文件数量。
3. 若任一步失败，提供失败包名、错误末尾及是否已生成部分 wheel；不要清理缓存或部分文件。

主任务收到回报后会离线安装并完成依赖自洽、PDF/FastAPI 兼容性、整套门禁和隔离 rerank 验证。
