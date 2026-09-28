# 本地候选依赖下载工作报告（辅助助手）

日期：2026-09-28
执行者：独立辅助助手（仅执行下载）
任务来源：`download-brief-for-assistant.md`（同目录）
状态：**已完成，复核通过**

## 一、任务范围

按简报要求，只做下载与 wheel 构建，不做安装：

- 将 `resolve-pdf.json` 中的 156 个精确版本依赖下载为 wheel，保存到仓库外临时 wheelhouse；
- 额外下载 FastAPI 升级候选 `fastapi==0.141.1` 与其解析候选 `starlette==1.7.0`（与基线分开请求）；
- 不下载/不替换 torch，不运行 `pip install`，不修改候选工作树与任何项目文件。

## 二、执行时间线

### 第 1 次尝试（未产生下载）：脚本编码问题

按简报原文将 PowerShell 脚本写入 `Temp\legal-closeout-20260928\download-wheels.ps1`（UTF-8 无 BOM）。Windows PowerShell 5.1 对无 BOM 文件按系统 ANSI（GBK）读取，中文报错文本变乱码并破坏字符串终止符，触发**解析错误，脚本一行未执行**，无任何下载或写入。修复方式：报错文本改为纯 ASCII 后重写同一路径。

### 第 2 次尝试（失败于网络）：pypi.org 读取超时

前置校验通过（清单 156 项、无 torch），pip 开始收集元数据（大量命中本地缓存）。进行到 `jsonpatch==1.33` 时，pypi.org `/simple/jsonpatch/` 连续 5 次重试全部 `ReadTimeoutError`（read timeout=15），最终 `No matching distribution found for jsonpatch==1.33`，退出码 1。

失败后按简报要求未盲目重试，先做连通性诊断：

- `https://www.baidu.com` → 200（1.7s）
- `https://pypi.tuna.tsinghua.edu.cn/simple/jsonpatch/` → 200（8.8s）
- `https://pypi.org/simple/jsonpatch/` → 超时（15s 无响应）

用户确认：当时未开代理，国外源不可达，同意换国内源。结论为瞬时网络问题叠加无代理环境，与用户中断网络的时段吻合。

### 第 3 次尝试（成功）：改用清华镜像

脚本在两次 `pip wheel` 中加入 `-i https://pypi.tuna.tsinghua.edu.cn/simple --timeout 60`，其余逻辑不变，重跑一次：

- STEP 1（基线 156 pins）：**退出码 0**
- STEP 2（fastapi 0.141.1 + starlette 1.7.0）：**退出码 0**
- 时间：约 20:47 开始，20:58:37 最后一个 wheel 落盘，全程约 11 分钟（镜像速率约 200 kB/s）
- 已下载部分与 pip 下载缓存全程保留复用，未清理

## 三、结果

| 项目 | 值 |
|---|---|
| Wheelhouse 路径 | `C:\Users\33393\AppData\Local\Temp\legal-closeout-20260928\wheelhouse` |
| `.whl` 文件总数 | **158**（= 156 基线 + 2 升级候选） |
| 总大小 | 177 MB |
| jieba==0.42.1 | 源码包构建 wheel 成功（19,314,527 字节，sha256 `1ac106a2767bef143bfd3dc5827755812ad832b66be81a4276467925aaa41c69`） |
| torch | 无任何 torch wheel（清单校验与逐文件检查双重排除） |

### 逐 pin 复核（verify-wheelhouse.py）

不止核对数量，用清单逐条比对 wheel 文件名（PEP 503 名称归一化 + 版本精确匹配）：

- `pin_count = 156`，`missing_pins = 0`
- `unexpected_wheels = 0`（仅有的 2 个"额外"文件即必需的 fastapi 0.141.1 / starlette 1.7.0）
- `unparsed_filenames = 0`，`torch_wheels = []`
- 日志核对：`Saved` 行 157 条 + jieba 走 `Created wheel for jieba` 记录 1 条 = 158，全部有出处
- 日志中 `pip install` 出现次数：0

### 约束遵守情况

- 未执行 `pip install`；pip wheel 为 jieba 构建时在 pip 标准隔离临时环境中安装了构建依赖，未触碰候选 venv 的 site-packages。
- 所有产物（wheelhouse、脚本、日志、校验脚本）均在 `AppData\Local\Temp\legal-closeout-20260928\`，仓库目录零写入。
- 候选工作树的未提交改动（`backend/knowledge_service.py`、`backend/requirements.txt`、t7 简报、两个新测试文件）经 mtime 核实均为 19:18–19:58 产生，早于本会话（20:47 起），属候选自身既有内容，本任务未做任何修改。
- 未读取 `.env`，未输出凭据或环境变量。

## 四、产物清单

| 文件 | 用途 |
|---|---|
| `Temp\legal-closeout-20260928\wheelhouse\`（158 个 .whl） | 交付物：离线安装用 wheel 仓库 |
| `Temp\legal-closeout-20260928\download-wheels.ps1` | 实际执行的下载脚本（含 156/无 torch 前置校验） |
| `Temp\legal-closeout-20260928\download-wheels.log` | 完整下载日志（含每包下载记录、jieba 构建 sha256、两步退出码） |
| `Temp\legal-closeout-20260928\verify-wheelhouse.py` | 只读复核脚本，主任务可重跑验证 |

注：前两次尝试共用同一日志文件路径，最终日志内容为第 3 次成功运行的完整记录；第 1、2 次失败现象已如实记录于本报告。

## 五、交接备注（供主任务）

1. 本机无代理时 pypi.org 直连不可用；后续若需在线安装，建议同样指定清华镜像，或直接 `--no-index --find-links <wheelhouse>` 离线安装。
2. pip 下载缓存已保留（`AppData\Local\pip\cache`），未清理。
3. wheelhouse 同时含 fastapi 0.110.3/0.141.1 与 starlette 0.37.2/1.7.0 两个版本，属简报设计（基线与升级候选并存）；主任务安装时按各自清单选版即可。
4. 复核脚本首版曾把 2 个升级候选误判为多余文件而输出 FAIL，属校验脚本自身逻辑错误，已修正为 PASS；结果以现版脚本为准。
