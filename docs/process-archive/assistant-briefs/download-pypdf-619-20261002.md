# 单项下载任务：pypdf 6.19.0（不安装、不提交）

状态：**2026-10-02已完成，不再派发或重复下载。** Owner回复“做完自己审核”允许此前明确请求的这一个wheel；主助手16:57:41–16:57:43完成官方元数据／大小／SHA校验及单项下载，退出码均0。随后主助手在已有授权的独立候选venv离线安装并完成新版回归／自审；不是下载助手擅自扩成安装任务。最新结果见执行书§0.3及本轮报告§9；6.16.1测试与8条命中均保留历史，不当作当前结果。

## 唯一交付

- 文件：`pypdf-6.19.0-py3-none-any.whl`。
- 大小：**395480 字节**，约 386 KiB；纯 Python 通用 wheel，不是 CUDA 或模型。
- SHA-256：`7e5d6e730e7dae87d560a2cee218b852f6498c8be61966f3cd02ead971e48d14`。
- 官方精确元数据：[PyPI 6.19.0 JSON](https://pypi.org/pypi/pypdf/6.19.0/json)。如重新查到文件哈希、大小或 yanked 状态不一致，停下报告，不换版本／包源。
- 实际下载目标：`C:/Users/33393/Desktop/fazhi-local-candidate-20261002-67944caf51ff48ce9432831cdd62f72b/cached-pdf-619/pypdf-6.19.0-py3-none-any.whl`。该文件已存在且校验一致；不使用项目wheelhouse／共享venv，不覆盖或重新下载。

## 原下载任务边界（保留索引，当前不用重新执行）

只下载这一个文件并验证。**不 pip install、不改任何 requirements／约束、不下载传递依赖、模型、CUDA、镜像或其他升级包；不改 .env／系统变量，不读、记录或转发 key，不碰真实库／共享 venv，不提交／合并／推送／部署**。依赖安装、回归和候选恢复由主助手接着执行。

目标若已有同哈希文件，直接报“已存在且校验一致”；不同则停，不覆盖或删除。失败 `.part` 留下供核查，不当作 wheel；完全相同的失败命令最多重试一次，先分析原因。网络失败不得关闭 TLS、使用未经核验的镜像或改用 sdist。

## 原获准后逐条命令（PowerShell，现只读参考）

以下是命令索引，不是无条件重跑脚本。目标 `.whl` 或 `.part` 已存在时先按上面的规则处理，不覆盖。

```powershell
$downloadWheel = 'C:\Users\33393\Desktop\fazhi-local-candidate-20261002-67944caf51ff48ce9432831cdd62f72b\cached-pdf-619\pypdf-6.19.0-py3-none-any.whl'
$downloadPart = $downloadWheel + '.part'
$expectedWheelHash = '7e5d6e730e7dae87d560a2cee218b852f6498c8be61966f3cd02ead971e48d14'
if (Test-Path -LiteralPath $downloadWheel) { throw '已有 wheel；只读校验后报告，不重新下载' }
if (Test-Path -LiteralPath $downloadPart) { throw '已有 part；先分析上次结果，不覆盖' }
curl.exe --disable --fail --show-error --silent --http1.1 --proto '=https' --tlsv1.2 --connect-timeout 15 --max-time 120 --output $downloadPart 'https://files.pythonhosted.org/packages/3c/2c/c43c03eaf630435f023f1dc61ec4a4a78951ad5530a62c71cc89bde307b7/pypdf-6.19.0-py3-none-any.whl'
$downloadExit = $LASTEXITCODE
if ($downloadExit -ne 0) { throw "下载失败，退出码 $downloadExit；保留 part，不改包源" }
if ((Get-Item -LiteralPath $downloadPart).Length -ne 395480) { throw '大小不符；停，不使用该文件' }
if ((Get-FileHash -LiteralPath $downloadPart -Algorithm SHA256).Hash.ToLowerInvariant() -ne $expectedWheelHash) { throw '官方哈希不符；停，不使用该文件' }
if (Test-Path -LiteralPath $downloadWheel) { throw '下载期间目标出现；停，不覆盖' }
Move-Item -LiteralPath $downloadPart -Destination $downloadWheel
Get-Item -LiteralPath $downloadWheel | Select-Object FullName,Length
Get-FileHash -LiteralPath $downloadWheel -Algorithm SHA256
```

`--disable` 避免读取 curl 的自定义配置；不用 `-k`、额外 header、鉴权 URL 或 pip 自动解析。

## 汇报给主助手

仅报实际绝对路径、字节数、SHA-256、时间、真实退出码、是否只完成下载。报告不要附环境变量、.env、请求头、凭据或模型配置全文。完成记录在执行根 `evidence/download-pypdf-619-command.json`；其中installed=false仅表示下载结束那个时点，后续安装见 `pdf619-install-command.json`，不能据旧时点推断当前未安装。后续入口为 `C:/Users/33393/Desktop/ai-legal-helper/docs/process-archive/superpowers/plans/2026-10-02-local-candidate-completion-plan.md` §0.3；单项下载／技术复验完成仍不等于完整阶段已接受。
