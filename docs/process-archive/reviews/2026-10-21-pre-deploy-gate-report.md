# 部署前门禁执行报告（2026-10-21）

> **性质：本地门禁执行记录，不是部署授权。** 本轮未启动或重启任何容器、未重建镜像、未读取 `.env`、未访问真实业务库与真实语料。
> 结论绑定本机 2026-10-21 的实际运行读数；CI 以干净检出运行，本机未跟踪目录不计入结论。

## 0. 结论摘要

| 项目 | 读数 |
| --- | --- |
| 已执行门禁 | 14 项（后端静态 3、后端测试 1、dispatch 3、前端 4、compose 2、依赖审计 1） |
| 通过 | 12 项（含本轮闭合的 format 项） |
| 未通过 | **1 项**：`pip-audit`（24 条告警 / 5 个包，既有钉版；Owner 授权后裁定**本轮不升级**，见 §8.10） |
| 工具版本相关 | **1 项**：mypy（2.3.0 报 2 条；2.4.0 为 0 条） |
| 未执行 | Docker 镜像构建（属于部署动作，本轮不做） |
| 后端测试 | **1909 passed / 2 skipped / 18 deselected**，覆盖率 **86.31%**（门槛 70%） |
| 前端 | lint、tsc、vitest（83/83）、生产构建全部通过 |

**净判定：除依赖审计按 Owner 裁决登记外，其余门禁全绿。** 格式项已在本轮按 `.gitattributes` 的 `eol=lf` 规范闭合且**不产生任何仓库 diff**；pip-audit 的 24 条告警来自未改动的既有钉版，已按 §8.10 裁定为本轮不升级、登记为接受风险。Docker 镜像构建仍属于后续部署动作，未执行。

## 1. 执行对象与环境

| 项 | 值 |
| --- | --- |
| 主仓 | `C:/Users/33393/Desktop/ai-legal-helper`，`master` HEAD `0b54396` |
| 本批改动 | 22 个 tracked 修改 + 4 个新增测试文件（均未提交） |
| 测试环境 | `backend/venv`：Python 3.11.0，langchain-core 0.1.53、langchain-openai 0.1.7、pydantic 2.13.4、SQLAlchemy 2.0.51 |
| 对照环境 | `backend/venv-new`：Python 3.11，langchain-core 1.6.9、pydantic 2.14.1、SQLAlchemy 2.1.4（工具版本对照用，不代表本仓依赖闭包） |
| 镜像入口 | `docker-compose.yml` 的 backend 服务从 `./backend` 构建，安装 `requirements.txt` 闭包 |

环境选择依据：`requirements.txt` 明确约束 `langchain-core>=0.1,<0.2`、`langchain-openai>=0.1,<0.2`、`pydantic>=2.6,<3.0`。`backend/venv` 与该约束一致；`backend/venv-new` 是更晚的闭包，**不能用于判定本仓测试门禁**。

## 2. 门禁读数

| # | 门禁 | 命令（工作目录） | 读数 | 判定 |
| --- | --- | --- | --- | --- |
| B1 | Ruff lint | `venv\Scripts\ruff.exe check --extend-exclude venv-new .`（backend） | `All checks passed!`，rc=0 | PASS |
| B2 | Ruff format | `venv\Scripts\ruff.exe format --check --extend-exclude venv-new .`（backend） | 初次 1 file would be reformatted（本地工作副本混行尾）；按 `.gitattributes` 规范化后 `278 files already formatted`，rc=0，`git diff` 为空 | PASS（本轮闭合） |
| B3 | mypy | `venv\Scripts\mypy.exe . --exclude "venv-new/"`（backend） | 2 errors，rc=1；换成 mypy 2.4.0 + SQLAlchemy 2.1.4 后 `Success: no issues found in 74 source files` | **工具版本相关，见 §4** |
| B4 | Pytest | `venv\Scripts\python.exe -m pytest -m "not slow" --cov=. --cov-fail-under=70 -q`（backend） | 1909 passed / 2 skipped / 18 deselected；coverage 86.31% | PASS |
| B5 | dispatch lint | `ruff check ../dispatch-output/agent-quality-20260911`（backend） | All checks passed，rc=0 | PASS |
| B6 | dispatch format | `ruff format --check ../dispatch-output/agent-quality-20260911`（backend） | 4 files already formatted，rc=0 | PASS |
| B7 | dispatch 守卫测试 | `python -m pytest -q ../dispatch-output/agent-quality-20260911/test_budget_guard.py` | 9 passed，rc=0 | PASS |
| F1 | 前端 lint | `npm run lint`（frontend） | No ESLint warnings or errors，rc=0 | PASS |
| F2 | 前端类型 | `npx tsc --noEmit`（frontend） | rc=0 | PASS |
| F3 | 前端单测 | `npm run test`（frontend） | 9 files / 83 tests passed，rc=0 | PASS |
| F4 | 前端构建 | `npm run build`（frontend） | Compiled successfully；7/7 静态页面；rc=0 | PASS |
| C1 | Compose 配置 | `docker compose -f docker-compose.yml config --quiet` | rc=0 | PASS |
| C2 | Compose 变量声明 | `docker compose config --format json` 仅提取键名 | `SILICONFLOW_API_KEY`、`SILICONFLOW_BASE_URL` 均在 backend 环境变量白名单内 | PASS |
| A1 | pip-audit | `venv-new\Scripts\python.exe -m pip_audit -r requirements.txt`（backend） | 24 条告警 / 5 个包，rc=1 | **FAIL（基线）** |

说明：本机 `backend/venv-new` 未被 `.gitignore` 排除且会被 `ruff check .` / `mypy .` 扫到；本轮用 `--extend-exclude` 仅排除该本地目录，未修改任何仓库配置。CI 是干净检出，不存在这个问题。

## 3. 一项红灯与一项已闭合项

### 3.1 Ruff format：本地工作副本行尾漂移（已闭合，零仓库 diff）

- 初次失败对象是 `schemas.py`，该文件不在本批 22 个修改内，索引侧也没有改动。
- 根因：`schemas.py` 的工作副本中有 9 行为 LF、265 行为 CRLF（本机 `core.autocrlf=true` 的 smudge 与工具写入叠加），而仓库已通过 `.gitattributes` 显式规定 `* text=auto eol=lf`；HEAD 的 blob 本身是 **276 行全 LF**。
- 闭合方式：仅把工作副本按 `.gitattributes` 规范为 LF。规范化后 `git diff --stat -- backend/schemas.py` 为空，说明**没有产生任何入库改动**；`ruff format --check` 变为 `278 files already formatted`，rc=0。
- 判定：这是本地工作副本形态问题，不是提交内容缺陷；CI 干净检出即为 LF，本来就会通过。无需为此单独提交。

### 3.2 pip-audit：24 条告警 / 5 个包

| 包 | 当前钉版 | 告警数（含重复别名） | 是否有修复版本 |
| --- | --- | --- | --- |
| langchain-core | 0.1.53 | 11 | 有（多条不同分支修复版本） |
| langchain-openai | 0.1.7 | 2 | 有（1.1.14） |
| langchain-text-splitters | 0.0.2 | 4 | 有（0.3.9 / 1.1.2） |
| chromadb | 0.4.24 | 2 | 无 |
| langsmith | 0.1.147 | 5 | 有（0.7.31 / 0.8.0 / 0.8.18） |

- 这些包来自 `requirements.txt` 的直接约束或其传递依赖（`langsmith` 由 `langchain-core` 0.1.x 引入，未在 `requirements.txt` 直接钉版）；本批未改依赖文件，属于既有基线。
- 按既有处置纪律：**本轮不自动升级任何钉版依赖**；有修复版的条目列清单交 Owner 裁决，无修复版的按历史先例登记。
- 升级会牵动 langchain 0.1 → 1.x、chromadb 0.4 → 0.5+ 等大版本，不能作为“顺手修”处理。

## 4. 工具/闭包差异造成的假红（不计入产品失败）

在 `backend/venv-new` 上跑同一套 not-slow 测试得到 **19 failed / 1890 passed**；把失败文件放到 `backend/venv` 重跑为 **66 passed**。差异来自环境而不是产品：

- `venv-new` 的 langchain-core 1.6.9 / langchain-openai 1.7.0 / pydantic 2.14.1，与本仓 `requirements.txt` 的 0.1.x / pydantic 2.x 约束不一致；
- 失败形态集中在 `FieldInfo` 属性、SDK 版本注入断言、未提供模块全局的 AST 提取函数，均为新版闭包与旧测试契约不匹配；
- mypy 2.3.0 + SQLAlchemy 2.0.51 报 2 条 `Row` 类型参数错误，mypy 2.4.0 + SQLAlchemy 2.1.4 为 0 error；两处代码均不在本批改动内。

因此本报告以 `backend/venv` 的测试读数为准，`venv-new` 仅用于静态工具版本对照。**不得**用 `venv-new` 的 19 条失败宣称产品回归，也不得用它通过来替代本仓闭包验收。

## 5. 部署残留登记

| 编号 | 事项 | 来源 | 状态 | 影响 |
| --- | --- | --- | --- | --- |
| R01 | DOCX 块级内容控件正文丢失 | 附件解析审查 A01 | **CLOSED**（提交 `9cd97b0`，见 §8.8） | 无 |
| R02 | 表格单元格段落/换行/制表符被拼接 | 附件解析审查 A02 | **CLOSED**（同上） | 无 |
| R03 | 嵌套表格重复提取 | 附件解析独立复核 N01 | **CLOSED**（同上） | 无 |
| R04 | 正文块级容器范围（`w:sdt` 含表格、`w:customXml`） | 附件解析独立复核 N02 | **CLOSED**（同上） | 无 |
| R05 | `schemas.py` 本地工作副本行尾漂移 | 本报告 §3.1 | **CLOSED**（按 `eol=lf` 规范化，零仓库 diff） | 无 |
| R06 | pip-audit 24 条告警 | 本报告 §3.2 | **ACCEPTED（本轮不升级）**：Owner 授权按推荐裁定，见 §8.10 | 依赖安全风险沿用既有基线，转下一轮依赖专项 |
| R07 | 映像构建与能力位实测未做 | 部署步骤 | **CLOSED**（§8.3/§8.4：镜像已构建，能力位 `true` 且三条链路真实调用 200） | 无 |
| R12 | 解析 warnings 在 `parse_uploaded` 内被丢弃（O01） | 附件解析独立复核 | **MITIGATED**（提交 `81e1744`：warnings 落 `legal.knowledge` 日志；用户侧提示按 §8.10 推迟，需与 R10 同批做前端契约） | 修订/域代码提示可由运维归因，用户界面尚未展示 |
| R13 | 删除会话不清理媒体文件（O02） | 附件解析独立复核 | **CLOSED**（提交 `81e1744`+`4159d85`，见 §8.9：会话与用户删除均回收无引用媒体；并发占用时文件可能留存并告警） | 无功能影响；极端并发下可能残留单个文件 |

R01–R04 的完整证据与复现方法见 `docs/process-archive/reviews/2026-10-20-attachment-parsing-and-media-lifecycle-review.md` 与 `docs/process-archive/reviews/2026-10-21-attachment-parsing-independent-review.md`。

## 6. 诚实边界

- 未执行 Docker 镜像构建，因此没有新镜像 ID/digest、没有镜像内 `.env` 缺失核验；
- 未启动应用、未做真实 HTTP 上传、浏览器或 Word 渲染验收；
- 未读取 `.env`，凭据存在性只通过 compose 的**变量名**声明确认，未验证值；
- 未访问真实数据库、真实媒体、真实语料；`frontend/coverage/` 为 2026-09-29 的既有未跟踪目录，本轮未删除；
- pytest 退出码在 PowerShell `Start-Process` 重定向下未回传，判定依据是汇总行无失败且覆盖率门槛满足；如需机器可读退出码，可补 `--junitxml` 重跑。

## 7. 下一步（按顺序）

1. 提交本批改动（显式路径、UTF-8 无 BOM 消息文件）；`schemas.py` 无仓库 diff，不进入提交；
2. 由 Owner 修改 `.env` 的两处模型配置后，授权重建 backend 容器；
3. 重建后执行 `image_chat` / `voice_transcribe` 能力位与真实图片/语音冒烟；
4. pip-audit 已按 §8.10 裁定（本轮不升级、登记接受风险）；前端镜像重建的解除条件见 §8.10。

## 8. 部署执行记录（2026-10-21，Owner 授权，因 Owner 无法操作电脑由本会话代执行）

### 8.1 提交

| 提交 | 内容 |
| --- | --- |
| `8580af4` | 本批 26 个文件：22 个 tracked 修改 + 4 个新增测试；显式路径暂存，未含 `.env`、`venv-new/`、dispatch 产物 |
| `4d267cd` | `backend/.dockerignore` 增加 `venv-new/`（1.43GB / 5.2 万文件的本地对照闭包，原会被 `COPY . .` 烘进镜像） |

提交消息经钩子（venv-new 的 ruff check + format）校验；`state_machine.py` 有一处既有代码在 ruff 0.16.1 下需折叠为单行，已按格式器输出落实。

### 8.2 `.env` 变更（仅结构，不含密钥值）

- 仅 `LLM_MODELS_JSON` 所在行中的文本模型字段：`"model":"LongCat-2.0"` → `"model":"LongCat-2.5-Preview"`；整行恰 1 处匹配。
- 与备份逐行比对：49 行不变，仅 1 行差异；文件大小 3308 → 3316 字节；无 BOM 变化。
- 视觉 `Qwen/Qwen3.5-4B`、语音 `XingChenAGI/XingChenASR-V3.2-Ultra`（含 `transport: audio_transcriptions`）此前已在位，本轮未动。
- 备份：`%TEMP%\fazhi-env-backup-20261021.env`；全程未读取、未记录密钥值。

### 8.3 镜像与容器

| 项 | 读数 |
| --- | --- |
| 构建 | `docker compose build backend`，rc=0 |
| 新镜像 | `ai-legal-helper-backend:latest` = `1b897968f631`，3.88GB |
| 构建上下文 | 48MB（排除 `venv-new/` 前为 1.43GB 量级） |
| 镜像内核验 | `/app/.env` 不存在；`/app/venv-new` 不存在；`torch 2.6.0+cpu` 断言通过 |
| 回滚标签 | `ai-legal-helper-backend:pre-8580af4-20261021` → `cbdadf43a40b`（原现役镜像） |
| 容器 | `fazhi-backend` 重建，`healthy`；启动日志无异常（chromadb 遥测告警为既有噪声） |
| 能力位 | `/api/health`：`image_chat=true`、`voice_transcribe=true`（重建前均为 `false`） |
| Agent 开关 | `AGENT_ENABLED=false` / `AGENT_TRAFFIC_PERCENT=0`，与重建前一致 |

### 8.4 真实调用冒烟（容器内直连 provider，不经登录、不读业务库）

第一次冒烟（根 `.env` 的旧键）：文本 200；视觉与语音 401（`30014`）。同一键在 `api.siliconflow.cn` 与 `api.siliconflow.com` 的 `/models` 均 401 ⇒ 键值本身无效。

复核发现两处键值不一致，且存在一个覆盖源：

| 位置 | 状态 |
| --- | --- |
| `backend/.env` 的 `SILICONFLOW_API_KEY` | 有效（`/models` 200） |
| 根 `.env` 的 `SILICONFLOW_API_KEY` | 无效（`/models` 401） |
| **Windows 机器级环境变量** `SILICONFLOW_API_KEY` | 持有旧值；**优先级高于 `.env`**，故仅改文件重建无效 |

处置：把根 `.env` 的该变量替换为 `backend/.env` 中的有效值（仅 1 行变化，逐行比对 49 行不变，备份 `%TEMP%\fazhi-env-backup-20261021-r08.env`），重建时以文件值为准注入；容器内该变量的指纹已与文件值一致。

第二次冒烟（有效键）：

| 目标 | 模型 | 结果 |
| --- | --- | --- |
| 文本 | `LongCat-2.5-Preview` | HTTP 200，正常返回 |
| 视觉 | `Qwen/Qwen3.5-4B` | HTTP 200，返回“红色…”（64×64 纯色合成图） |
| 语音 | `XingChenAGI/XingChenASR-V3.2-Ultra` | HTTP 200，`duration=1.0`；1 秒正弦无语音，文本为空属预期 |

补充：初次视觉用例用 1×1 像素图，被 provider 以 `20015 height/width must be larger than 28` 拒绝，属用例尺寸问题，不是链路问题。

判定：能力位反映的是「注册表中存在该模态」，**不校验凭据有效性**；配置正确时三条链路均可用。

### 8.5 新增残留

| 编号 | 事项 | 状态 | 影响 |
| --- | --- | --- | --- |
| R08 | 根 `.env` 的 `SILICONFLOW_API_KEY` 无效 | **CLOSED**（已替换为 `backend/.env` 的有效值） | 无 |
| R11 | Windows 机器级环境变量 `SILICONFLOW_API_KEY` 仍持有旧无效值，且优先级高于 `.env` | **CLOSED（按 Owner 裁决：以流程约束替代清理）**；机器级变量本身未改（本会话无管理员权限），覆盖要求已写入部署 runbook §1 | 未按 runbook 覆盖宿主变量就重建时，仍会注入旧键 |
| R09 | 容器实际闭包 `pydantic 2.14.1 / SQLAlchemy 2.1.5 / langchain-core 0.1.53`，与门禁所用 `backend/venv`（2.13.4 / 2.0.51）不同 | **CLOSED**（容器内实测 1857 passed / 11 failed，失败均为镜像未携带仓库素材/目录结构所致，非版本冲突；详见 §8.7） | 无版本层面回归证据 |
| R10 | 前端镜像构建于 2026-08-07，本批前端改动（状态徽章、上传可达性）未上线 | **CLOSED**（2026-10-21 经镜像源拉取 `node:20-alpine` 后重建并上线，见 §8.11；此前 §8.10 的 BLOCKED 读数保留原貌） | 新镜像 `b7e57b1512b7` 已替换旧镜像 `8ab48027bfe2` |
| R13 | 前端**构建期**内联的 API 基址直连后端端口（本地机 `http://localhost:8000`；首次重建后为公网 `http://162.14.81.34:8000`），该端口在当前部署形态下不可达 ⇒ 浏览器 fetch 被拒，登录页报 “Failed to fetch” | **CLOSED（本机同源重建后修复）**，见 §8.13；§8.12 当时的“已同源”推断不成立，已在该节更正 | 属 C13「前端 API 基址」的具体化：构建期基址与部署形态不一致；**生产服务器侧同一问题未验证** |
| R15 | 语音转写生产路径被 provider 拒绝：`XingChenAGI/XingChenASR-V3.2-Ultra` 在 **chat/completions + `input_audio`** 通道返回 400 `Unsupported model` ⇒ `/api/chat/transcribe` 恒 502，前端回退浏览器识别 | **CLOSED（代码修复 + 镜像重建 + 端点复测 200）**，见 §8.14；根因实为**两处**：注册表缺 `siliconflow` provider 分支 + 代码只走 chat 通道 | 后端语音转写已恢复；§8.4 的直连 provider 冒烟未覆盖生产代码路径，已在本轮补上端点复测 |

### 8.6 本轮诚实边界

- 未做登录态端点冒烟（`/api/chat` 带图、`/api/chat/transcribe`），也未跑浏览器验收；
- 未访问业务数据库、真实语料、真实媒体；
- 视觉用例是 64×64 合成纯色图，语音用例是 1 秒正弦音，只验「链路接受并返回」，不验识别质量；
- 容器内测试是临时安装 `pytest` / `pytest-cov` 后运行的，镜像本身不含测试工具；运行前后 `pip freeze` 差分仅新增 `pytest / pytest-cov / coverage / iniconfig / pluggy`，无既有运行时包版本变化；
- 前端镜像未能重建，旧镜像与新提交的界面差异未在浏览器验收。

### 8.7 收尾执行（R09 / R10 / R11）

#### R09 容器闭包实测

命令形态：以现役镜像 `ai-legal-helper-backend:latest` 起一次性 `--rm` 容器，传入 `backend/.env`，在 `/app` 内先安装测试工具再跑 `pytest -m "not slow"`；不碰现役容器。

| 读数 | 值 |
| --- | --- |
| 结果 | **1857 passed / 11 failed / 10 skipped / 18 deselected**，144.38s |
| 排除项 | `test_gate2_runner.py`、`test_gate5_judge_layers.py`、`test_harness_fact_reveal.py`、`test_r15_runner_injection.py`（这 4 个文件用 `Path(__file__).resolve().parents[2]` 当仓库根；用例装在 `/app/tests` 时该表达式指向 `/`，而镜像内只有 `/app`，收集期即报 `FileNotFoundError`） |
| 剩余 11 条失败 | 均为镜像内缺少仓库素材或仓库根路径所致，不涉版本：`test_chunking.py` 7 条找不到样例法条文本，`test_gate_exit_registry.py` 1 条找不到提交的 md，`test_init_release_evidence.py` 1 条需仓库目录结构，`test_smoke_citation_assertions.py` 1 条需 CONTRIBUTING，`test_chroma_isolation.py` 1 条是仓库根被解析为 `/` 的路径断言 |
| 依赖差分 | `pip freeze` 前后对比只有新增（`pytest 9.1.1`、`pytest-cov`、`coverage 7.16.2`、`iniconfig 2.3.1`、`pluggy 1.7.0`），无既有包版本变动 |
| 证据位置 | 运行日志 `%TEMP%\fazhi-r09-pytest-20261021c.log`；命令尾部带 `--ignore=tests/...` 四条与上述排除项一一对应 |

判定：容器闭包未出现版本层面的测试回归；11 条失败是「镜像不带仓库素材」的结构性差异，与 `pydantic 2.14.1 / SQLAlchemy 2.1.5` 无关。R09 由「未知」转为「有结论」，但**不等于**镜像内 100% 用例通过。

#### R10 前端镜像重建：BLOCKED

| 尝试 | 结果 |
| --- | --- |
| BuildKit `docker compose build frontend` | `failed to resolve reference docker.io/library/node:20-alpine`，`dial tcp 104.16.251.55:443` 超时 |
| `docker pull node:20-alpine` | 超时，`dial tcp 104.244.43.6:443` |
| `DOCKER_BUILDKIT=0` legacy builder | 同一步失败，`dial tcp 199.96.63.75:443` 超时 |
| npm registry 连通性（对照） | `HEAD https://registry.npmjs.org/next` → **200**，说明不是全网络中断，而是 Docker Hub 不可达 |

判定：不是代码或 Dockerfile 缺陷，是外部网络不可达；未修改 Dockerfile 绕过（避免产出不可复现的镜像）。旧前端镜像 `8ab48027bfe2` 继续运行，已打标签 `ai-legal-helper-frontend:pre-20261021` 留档。

#### R11 宿主变量覆盖约束

按 Owner 裁决「不动机器级变量、以流程约束替代」，已写入 `docs/runbooks/deployment-v1.md` §1 部署前置检查：明确 `${VAR}` 插值优先取宿主环境变量、仅改 `.env` 不生效、重建前须显式覆盖并在容器内比对指纹。

### 8.8 DOCX 解析修复（R01–R04，提交 `9cd97b0`）

修复内容：

| 缺陷 | 处理 |
| --- | --- |
| R01/R04 块级容器被跳过 | 新增块级递归：`w:sdt/w:sdtContent`、`w:customXml`、块级 `w:ins` 内的段落与表格按文档顺序提取；正文只有控件时不再误报“提取文本为空” |
| R02 单元格内边界粘连 | 单元格改用段落提取并按行拼接：同格两段落 → 换行，`w:br` → 换行，`w:tab` → 空格 |
| R03 嵌套表格重复 | 表格只取直接子 `tr`、行只取直接子 `tc`，内层表格只在外层单元格内出现一次 |

验证读数：

| 项 | 读数 |
| --- | --- |
| 新增用例 | 8 条（块级 sdt 段落/表格、customXml、块级 ins、单元格双段落、`w:br`/`w:tab`、嵌套表格计数、行内 sdt） |
| 定向测试 | `tests/test_docx.py` **21 passed** |
| 全量 not-slow | **1917 passed / 2 skipped / 18 deselected**，覆盖率 **86.36%**（380.99s） |
| 静态 | `ruff check` / `ruff format --check` 全绿；mypy 仍仅剩既有的 2 条 `Row` 类型参数（工具版本相关，非本次改动） |
| 部署 | 新镜像 `bb4d024c797c`，容器 `healthy`；容器内 `docx_utils.py` 的 sha256 与工作区一致（`9be03394…`）；凭据复核 `/v1/models` → 200 |
| 回滚 | `ai-legal-helper-backend:pre-docxfix-20261021` → `1b897968f631` |

边界：未做真实 Word 文件渲染/上传验收；解析保真以合成 DOCX 的单元断言为准，不代表任意真实合同已被覆盖。

### 8.9 媒体生命周期收尾（R12/R13，提交 `81e1744`）

#### 实现

| 项 | 处理 |
| --- | --- |
| R13 会话删除不回收媒体 | `delete_conversation` 先取该会话全部 `image_ref` / `thumb_ref`，删库提交后调用 `cleanup_orphaned_media`：路径必须落在 media 目录内，且库里已无任何 `Message` 引用该路径才删除；单文件失败只记 `legal.media` 警告，不阻断删除 |
| 同类场景：删用户 | `admin_delete_user` 会级联清空会话/消息，同样在提交前收集该用户全部媒体引用、提交后回收（`4159d85`） |
| 引用判定依据 | 媒体按请求 `uuid4` 命名（`persist_image`），正常不跨消息共享；引用检查以删除后的库为准，避免历史数据/换绑造成的共享被误删 |
| R12 解析告警被丢弃 | `parse_uploaded` 把 `extract()` 返回的 warnings 逐条写入 `legal.knowledge` 日志（`docx_parse_warning`）；返回签名不变，用户侧提示留待前端契约；日志只记扩展名与告警文本，不记文件名（可能含姓名/案号） |

#### 验证读数

| 项 | 读数 |
| --- | --- |
| 新增用例 | 11 条：媒体回收 8 条（正常删除、共享引用保留、`thumb_ref` 单引用保留、路径穿越拒绝、文件缺失容忍、重复引用去重、引用查询失败保文件、`unlink` 失败保文件）、删除顺序 1 条、删用户回收 1 条、docx 告警日志与脱敏 1 条 |
| 红能力（真实失败） | 首批 8 条用例在 `a297b42` 的临时 worktree 内运行：`request_bootstrap` 收集期 `ImportError: cannot import name 'cleanup_orphaned_media'`；另两条行为用例 **2 failed**（日志为空、`main` 无该属性）；worktree 已删除，`git worktree list` 无残留。`4159d85` 追加的 3 条未做同款红跑 |
| 定向测试 | 三个测试文件 **111 passed** |
| 全量 not-slow | **1928 passed / 2 skipped / 18 deselected**，覆盖率 **86.51%**（355.24s） |
| 静态 | `ruff check` / `ruff format --check` 全绿；mypy 仍为既有的 2 条 `Row` 类型参数（工具版本相关，非本次改动） |
| 部署 | 新镜像 `1fa903691ecf`；容器 `healthy`；`/api/health` 返回 `image_chat=true`、`voice_transcribe=true`；容器内 `main.py` / `knowledge_service.py` sha256 与工作区一致（`77987df7…` / `8dde53c5…`） |
| 容器内冒烟 | 临时目录两个媒体文件经 `cleanup_orphaned_media` 后 `DELETED ['media/x.png','media/x_thumb.jpg']`、`REMAIN []` |
| 独立复核 | 1 名对抗式复核者 + 1 名证据核验者：9 条声明全部成立；对抗复核提出的删用户未回收、日志含文件名、顺序断言过弱、`unlink` 失败分支缺测四项已在 `4159d85` 处理 |
| 回滚 | `ai-legal-helper-backend:pre-reviewfix-20261021` → `815f802e8852`；上一级 `pre-o01o02-20261021` → `bb4d024c797c` |

边界：未做登录态删除会话/删除用户的端到端 HTTP 验收；媒体回收的正确性以单元测试与容器内函数级冒烟为准。Windows 下文件被并发读取占用时 `unlink` 会失败，本次删除保留该文件并告警，当前没有后台 sweeper，残留需后续人工或重试清理。R12 只是把告警从「丢弃」变为「服务端可见」，用户界面仍不会提示修订/域代码风险。

### 8.10 R06 / R10 / R12 用户侧收尾（2026-10-21，Owner 授权按推荐执行）

#### R06 pip-audit：本轮不升级，登记为接受风险

| 项 | 结论 |
| --- | --- |
| 决定 | 本轮部署窗口**不升级**任何钉版依赖；24 条告警维持既有基线，转入下一轮依赖升级专项 |
| 依据 | 5 个包中 4 个的修复版本跨大版本（langchain-core 0.1.53 → 0.3/1.x、langchain-openai 0.1.7 → 1.1.14、langchain-text-splitters 0.0.2 → 0.3.9/1.1.2、langsmith 0.1.147 → 0.7.31+），chromadb 0.4.24 无修复版；`requirements.txt` 的 `langchain-core>=0.1,<0.2` 与 0.1 生态绑定，单独替换会拆散已验证闭包 |
| 为何不在本轮做 | 升级会牵动 langchain 0.1 → 1.x、chromadb 0.4 → 0.5+ 与嵌入/索引兼容性，需重跑全量用例并独立复核；在部署窗口内把「已验证组合」换成「未验证组合」，风险高于既有告警的暴露面 |
| 补偿措施 | 服务经 Caddy 反代、不对外提供任意插件加载；告警清单在 §3.2 留档；依赖专项的前置清单固定为「先装 CPU 版 torch → 解析闭包 → 全量 not-slow + 覆盖率 → 独立复核」 |
| 失效条件 | 出现与现钉版兼容且可远程利用的修复版，或任一告警在 osv.dev 升级为已知在野利用 ⇒ 立即重开本项，不等专项排期 |
| 状态判定 | **ACCEPTED**：不是「已修好」，而是「已知、有失效条件、有责任位」的接受风险 |

#### R10 前端镜像重建：复核仍 BLOCKED

| 项 | 读数（2026-10-21 13:09:42 +08:00 新鲜复核） |
| --- | --- |
| `https://registry-1.docker.io/v2/` | 15s 超时（`The operation has timed out.`） |
| 本地基础镜像 | `docker image inspect node:20-alpine` → `No such image`；`hello-world` 同样不存在 ⇒ 无法离线构建 |
| 现役前端 | `fazhi-frontend` running，镜像仍为 `8ab48027bfe2`（2026-08-07 构建） |
| 后端 | `fazhi-backend` healthy；`/api/health` 返回 `image_chat=true`、`voice_transcribe=true` |

判定：与 §8.7 同因（Docker Hub 不可达），本轮未做任何绕过（不更换基础镜像、不改写 Dockerfile）。解除条件：任一环境能拉通 `node:20-alpine` 后执行 `docker compose build frontend && docker compose up -d frontend`；验收口径为新镜像 ID、`/` 返回 200、状态徽章与上传可达提示与新提交一致。

#### R12 用户侧提示：本轮不做

| 项 | 决定 |
| --- | --- |
| 结论 | 维持 MITIGATED：服务端日志可见，用户界面不提示 |
| 理由一 | 用户侧提示需要后端上传响应携带 warnings、前端展示，属接口契约变更；当前前端镜像无法重建（R10 BLOCKED），单改后端会让现役前端与新后端出现无展示的不一致 |
| 理由二 | 该提示是体验改进而非安全阻断：修订/域代码内容已按正文提取，缺口只是用户不知道文档含修订痕迹 |
| 解除条件 | R10 解除后，作为一批「上传契约向后兼容扩展 + 前端提示」提交，补契约测试与浏览器验收 |

### 8.11 R10 解除：前端镜像重建并上线（2026-10-21，Owner 授权「按推荐」）

前置：Docker Hub（`registry-1.docker.io` / `auth.docker.io`）仍不可达，本轮改用**镜像加速源**取基础镜像。所选域名 `docker.m.daocloud.io` 不在项目网络白名单内，由 Owner 以「按推荐」明确授权后访问。

| 步骤 | 命令 → 读数 |
| --- | --- |
| 拉取基础镜像 | `docker pull docker.m.daocloud.io/library/node:20-alpine` → `Status: Downloaded newer image`，digest `sha256:fb4cd12c…372293`，194 MB |
| 打本地标签 | `docker tag docker.m.daocloud.io/library/node:20-alpine node:20-alpine` → `node:20-alpine|fb4cd12c85ee|194MB` |
| 重建前端 | `docker compose build frontend` → `Image ai-legal-helper-frontend Built`（builder 解析到的仍是同一 digest `fb4cd12c…`，未再走 Docker Hub） |
| 上线 | `docker compose up -d frontend` → 新镜像 ID **`b7e57b1512b7`**；因 `frontend` 依赖 `backend: service_healthy`，`backend` 亦被重建并回到 **healthy** |
| 入口验收 | `http://localhost:8088/` → **200**，内容 6607 字节，`<title>` = 「法智 · AI 法律咨询小助手」 |
| 后端能力位 | `http://localhost:8088/api/health` → **200**，`{"status":"ok","capabilities":{"image_chat":true,"voice_transcribe":true}}` |
| 容器内监听 | `docker exec … wget http://127.0.0.1:3000/` → **200**；用 `localhost` 则 `Connection refused`（Alpine 先解析 `::1`，Next 只监听 IPv4），属解析差异**非缺陷** |
| 构建号机制 | 新镜像 `/app/public/build-id.txt` = `sWFu7WsRG6yA1yFMZpF0Y`；旧镜像 `8ab48027bfe2` 中**无该文件**（早于构建号机制）⇒ 确为新构建；`sw.js` 缓存名 `fazhi-shell-<BUILD_ID>`，构建号变化后 activate 会清旧缓存 |
| 容器日志 | `docker logs fazhi-frontend` → `Ready in 91ms`，无报错 |

未做的事（与既有纪律一致）：**未改 `frontend/Dockerfile`**（两个 `FROM node:20-alpine` 原样保留）、**未改 `daemon.json`**、**未重启 Docker daemon**（三个现役容器未因改配置被打断，`fazhi-caddy` 已连续运行 38 小时）。

诚实边界：

- 只做了 HTTP/镜像层验收，**未做浏览器人工验收**（状态徽章、上传可达性提示、语音「统一停止」的视觉与交互一致性仍需 Owner 在页面上确认，对应 runbook B9-R14）；
- 拉取使用的是白名单外域名，已取得 Owner 授权；该授权只覆盖本次拉取，不改动白名单本身；
- 旧镜像 `8ab48027bfe2` 保留不删（沿用 `ai-legal-helper-frontend:pre-20261021` 留档 tag），可随时回退；
- §8.10 中 R12 的延期理由之一（「当前前端镜像无法重建」）**已不成立**，但 R12 本身仍为未做，需另行排期，不因本节自动转 CLOSED。

### 8.12 R13 前端 API 基址错配导致登录失败（2026-10-21，Owner 页面报错 “Failed to fetch”）

现象：登录页提交后报 `Failed to fetch`（浏览器网络层失败，不是 401，故与口令无关）。

| 判据 | 读数 |
| --- | --- |
| 后端是否活着 | `POST /api/auth/login`（8088 与 3000 服务端 rewrite 两条路径）→ 均 **HTTP 401**（说明接口通、只是口令不对）；宿主直连 `http://localhost:8000` → **连接被拒**（后端未向宿主发布 8000 端口，对外只有 Caddy 8088） |
| 请求是否到达后端 | 后端访问日志中该时段**没有**任何 `/api/auth/login` 记录 ⇒ 请求根本没出浏览器 |
| 旧镜像里的基址 | 旧镜像 `8ab48027bfe2` 的 `/app/.next/static` 中 `localhost:8000` 命中 **5** 处 |
| 新镜像里的基址 | 新镜像 `b7e57b1512b7` 命中 **0** 处 ⇒ 生产构建走相对 `/api/*`（同源），由 Caddy 转 `backend:8000` |
| dev 模式 | `lib/api.ts` 在未设 `NEXT_PUBLIC_API_URL` 时回落到 `http://localhost:8000` ⇒ `next dev` 下浏览器同样打到宿主 8000（被拒） |
| dev 修正后 | 重启 dev 并显式设 `NEXT_PUBLIC_API_URL=http://localhost:8088`，编译产物为 `const API_URL = "http://localhost:8088"`；跨域预检 `OPTIONS` → **200**，`Access-Control-Allow-Origin: http://localhost:3000`（后端 CORS 正则放行任意 localhost 端口） |
| 生产页面分片 | `http://localhost:8088/login` 的 8 个 JS 分片全部 **200**，`localhost:8000` 命中 **0** |

根因：旧构建期把 `http://localhost:8000` 固化进浏览器 bundle，而部署形态是「宿主只有 8088 同源入口」，浏览器侧无从访问 8000 ⇒ fetch 直接被拒。这是台账 C13「前端 API 基址」的具体化，不是后端故障、不是 Caddy 故障、不是口令问题。

处置：

1. 生产侧：§8.11 的新镜像已替换旧镜像，生产构建不再含绝对基址；
2. dev 侧：dev 服务已以 `NEXT_PUBLIC_API_URL=http://localhost:8088` 重启，3000 端口同样可用；
3. Owner 侧动作：旧标签页仍持有旧 bundle，需**硬刷新**（或无痕窗口）后再登录；如仍失败，清 Service Worker 与站点缓存再刷新。

诚实边界：

- 未用真实口令完成一次成功登录（凭据红线，未读 `.env`），接口可达性以 401 与预检 200 证明；**成功登录与后续主链路仍待 Owner 人工确认**；
- 未在本节复现浏览器端 SW/缓存状态机的每一种组合（只核对了产物与网络路径）；
- 未修改 `lib/api.ts`、`next.config.js`、`Caddyfile`、`docker-compose.yml` 任何产品字节。

> **更正（2026-10-21，见 §8.13）**：本节据「新镜像中 `localhost:8000` 命中 0 处」推断「生产构建走相对 `/api/*` 同源」，**该推断不成立**。新镜像实际内联的是 `http://162.14.81.34:8000`（命中 2 处），只查 `localhost:8000` 不足以判定同源。R13 在 §8.11 之后**仍然存在**，直至 §8.13 的同源重建。

### 8.13 R13 修正：构建期 API 基址指向不可达端口（2026-10-21，Owner 控制台截图）

现象：Owner 浏览器控制台显示 `Failed to load resource: net::ERR_CONNECTION_TIMED_OUT  162.14.81.34:8000/api/auth/login`，页面仍报 “Failed to fetch”。另有一条 `analysis.chatglm.cn` 超时与一条 `favicon.ico` 404。

| 判据 | 读数 |
| --- | --- |
| 浏览器实际请求目标 | `162.14.81.34:8000/api/auth/login`（**超时**）⇒ 请求确实出了浏览器，但目标不可达 |
| 基址来源 | `frontend/.env`（**未入库**，`.gitignore` 命中）第 5 行 `NEXT_PUBLIC_API_URL=http://162.14.81.34:8000`；Next.js 在**构建期**把 `NEXT_PUBLIC_*` 内联进浏览器 bundle |
| 产物证据 | 首次重建的镜像 `b7e57b1512b7` 的 chunk 中该公网基址命中 **2** 处；更早的镜像 `8ab48027bfe2` 内联的是 `localhost:8000`（命中 **5** 处）⇒ 两个镜像都把绝对基址烤进了前端 |
| 部署形态核对 | `docker-compose.yml` **未向宿主发布** backend 的 8000（2026-08-08 端口收紧，仅 Caddy 对外 80/443）；直连 `:8000` 绕过 Caddy 的 `/api` 转发与安全响应头 |
| 网络实测 | 本机到 `162.14.81.34` 的 **:8000 / :80 / :443 三个端口全部 TCP 超时** ⇒ 本机网络无法连通该公网主机（故本机只能验证本机实例） |
| 仓内先例 | `docs/process-archive/project-next-execution-plan-20260916.md` 已记录同一坑：本地 build 内联生产 IP，浏览器把登录请求发去腾讯云生产 |
| `chatglm` 超时 | 全仓检索 `chatglm` **零命中** ⇒ 非本应用发出（浏览器扩展或其它站点），不计入本项 |
| `favicon.ico` 404 | 前端 `public/` 只有 `icon-192/512` 与 `apple-touch-icon`，无 `favicon.ico` ⇒ 外观级噪声，非阻断 |

处置（本机）：把 `frontend/.env` 的 `NEXT_PUBLIC_API_URL` **置空** ⇒ 编译为 `API_URL=""` ⇒ 走**同源相对 `/api/*`**，由 Caddy 转到 compose 内网 8000（与仓库既定的「同源反代」设计一致），随后重建并上线镜像 `fe298901d089`。

修复后验证：`http://localhost:8088/login` → **200**，其 **8** 个 JS 分片全部 **200**、绝对基址命中 **0**（`162.14.81.34` / `localhost:8000` 均无）；`POST http://localhost:8088/api/auth/login` → **HTTP 401**（接口通、仅口令不对）；`fazhi-backend` 本轮**未被重建**、保持 healthy；`fazhi-caddy` 连续运行。

与既有决策的关系：`frontend/.dockerignore` 明确**不排除 `.env`**，并写明「排除 `.env` ≡ 清空 `NEXT_PUBLIC_API_URL` ≡ 切换到同源路径 ⇒ 属部署形态决策」。本轮**只改本机未入库的 `frontend/.env`**，未动 `.dockerignore`、`Dockerfile`、`next.config.js`、`lib/api.ts`、`Caddyfile`、`docker-compose.yml`；原值已备份到 `TEMP/fazhi-frontend-env-backup-20261021.txt`。

残余（需 Owner 在服务器侧处理，本机无法代做）：

1. **生产服务器侧的 `frontend/.env` 很可能仍是直连 `:8000` 的部署值**；本机到该主机的三个端口全部超时，**无法验证其可达性**，也无法在本机复现或修复；
2. 若服务器确未对外发布 8000，则生产 UI 对外用户同样会 “Failed to fetch”，处置二选一：把服务器侧 `frontend/.env` 改为同源并重建前端镜像，或由 Caddy/防火墙把 8000 暴露出去（后者与 2026-08-08 端口收紧相反，需另行审批）；
3. 在服务器侧实测前，不应宣称生产 UI 可用。

诚实边界：

- 未用真实口令完成一次成功登录（凭据红线，未读 `.env` 中的凭据），接口可达性以 401 与页面分片读数证明；**成功登录与主链路仍待 Owner 人工确认**；
- 未对生产服务器做任何写操作或验证动作（不可达）；
- 本节只覆盖「构建期基址 → 浏览器请求目标」这一条因果链，未审计生产服务器其余配置。

> **复核（2026-10-21 09:12–09:16，同源重建后由 Owner 在页面上真实操作）**：后端访问日志显示 `POST /api/auth/login` → **200**（208 ms）、`GET /api/auth/me` → **200**、`POST /api/chat/file` → **200**（20.8 ms）、`POST /api/chat` → **200**（**123 908 ms**）。即：同源修复后登录与主链路在真实浏览器里已打通，本节此前的「未用真实口令完成一次成功登录」已被实际事件覆盖（助手仍未读任何凭据）。
>
> 同批控制台另有 3 条 `analysis.chatglm.cn/…` 超时与 1 条 `favicon.ico` 404，来源脚本名为 `stadlum.js`：该脚本名与域名在全仓**零命中**，本应用也不含任何外部 `<script>` 注入与智谱端点（智谱走 `open.bigmodel.cn`，非 `analysis.chatglm.cn`）⇒ 判为**浏览器扩展注入的第三方请求**，与本应用缺陷无关。
>
> 待观察（非缺陷判定）：`/api/chat` 单次耗时 124 s，页面在「正在检索法律条文」停留较久。与台账既有的 LongCat 外部调用延迟（单请求最长约 960 s）同源，属性能体验项，需在 W08 真实验收里量化，不由本节下结论。

### 8.14 R15 语音转写生产通道被 provider 拒绝（2026-10-21，Owner 页面弹窗）

现象：Owner 在对话页点麦克风（未说话）→ 页面弹 `语音转写失败（语音识别服务暂时不可用，请稍后重试），已回退浏览器识别`。

| 判据 | 读数 |
| --- | --- |
| 请求是否到达后端 | `POST /api/chat/transcribe` **两次**：09:19:26 与 09:19:48，均 **502**（12.0 s / 4.9 s） |
| provider 原始错误 | 后端 WARNING：`transcribe failed: Error code: 400 - {'error': {'code': 'invalid_parameter', 'message': 'Unsupported model (model=XingChenAGI/XingChenASR-V3.2-Ultra)'}}` |
| 生产代码通道 | `multimodal.transcribe_audio` 用 `voice_llm.invoke([HumanMessage(input_audio …)])` ⇒ **chat/completions + `input_audio`**；模型不接受该通道 |
| 前端行为 | `useVoice.ts` 的 `transcribeAndFill` 捕获后 `alert(...)` 并 `legacyWebSpeech()` ⇒ **回退浏览器识别是设计行为**，不是新缺陷 |
| 未说话为何仍发起转写 | 点开始录音即进入采集，点停止就把这段音频（哪怕静音）上传；`/api/chat/transcribe` 仅在 `len(raw) < 1024` 时以 400 拒绝空文件，本次音频长度过阈，故走到了 provider |
| 与 §8.4 冒烟的差异 | §8.4 明写「容器内直连 provider，不经登录」；其语音读数 `duration=1.0` 是 **`/audio/transcriptions` 响应形态**，而 `/api/chat/transcribe` 只返回 `{"text": …}` ⇒ 该冒烟**未走生产代码路径**，因此「HTTP 200」不能证明应用内语音可用 |

判定：**这不是“因为你没说话”导致的失败**，而是生产路径本身被 provider 拒绝（模型只认 transcriptions 通道，代码走 chat 通道）。失败后回退浏览器识别符合设计；但后端语音转写在该配置下**实际不可用**。

处置建议（未执行，需先确认 provider 侧模型与通道）：

1. 首选：为 `transport: audio_transcriptions` 的语音条目实现 **multipart `/v1/audio/transcriptions`** 调用（`multimodal.transcribe_audio` 分支），保留 chat 通道作为备选；补一条契约测试区分两条通道；
2. 备选：改用 provider 明确支持的语音模型 ID（需 Owner 确认，不允许助手臆断替换）；
3. 无论哪条，落地后必须**经应用端点**复测（不是直连 provider），并把 502→200 作为判据。

诚实边界：本轮未调用 provider 的 `/models` 或 transcriptions 端点做在线核验（该域名不在项目网络白名单，需 Owner 授权）；上述通道结论由 provider 返回的错误文本与本地代码路径推出，未做线上复测。

#### 8.14.1 核验与修复（2026-10-21，Owner 授权「按第 1 条执行，先核验模型可用性」）

在线核验（一次性容器 + `--env-file backend/.env`，脚本不打印任何密钥值；访问 `api.siliconflow.cn`，Owner 已授权）：

| 目标 | 读数 |
| --- | --- |
| `/models`（有效键） | **200**；98 个模型中含 `XingChenAGI/XingChenASR-V3.2-Ultra`（`TARGET_IN_LIST=True`），另有 `Qwen/Qwen3-ASR-1.7B`、`FunAudioLLM/SenseVoiceSmall` 等 6 个音频类模型 |
| `/audio/transcriptions`（同模型、1 s 正弦） | **200**，`{"duration":1.0,"text":""}`（无语音 → 空文本，符合预期） |
| `/chat/completions` + `input_audio`（同模型） | **400**，`{"code":20012,"message":"Model does not exist…"}` |
| 修前现役容器里的 `SILICONFLOW_API_KEY` | **无效**（同端点 `/models` 401 `Token is invalid`），指纹 `1ed4b9c74505` = **Windows 机器级变量**（R11 覆盖再现） |
| `backend/.env` / 根 `.env` 的值指纹 | 均为 `e6e7547bbfa5`（有效）；Docker `--env-file` 与容器内实测一致 |

修前注册表实测（容器内、脱敏）：`vision_sf` / `voice_sf` 的 `base_host` 都是 **`api.longcat.chat`** —— 因为 `llm_registry._load` 只认 `zhipu` / `dashscope` 两个专用 provider，`siliconflow` 落到通用分支拿 LongCat 的 base_url/key。即根因是两处叠加：**provider 分支缺失** + **代码只走 chat 通道**。

修复（提交 `a19b6e9`）：

1. `settings.py`：新增 `siliconflow_base_url`（此前只有 key，compose 传入的 `SILICONFLOW_BASE_URL` 实际被忽略）；
2. `llm_registry.py`：新增 `provider == "siliconflow"` 分支；`ModelEntry` 增加 `transport`；新增 `pick_entry()`，`pick()` 改为其薄封装（路由/冷却/配额规则逐字不变）；
3. `multimodal.py`：新增 `transcribe_audio_transcriptions()`（multipart，含 MIME 映射，httpx 120 s 超时）；
4. `main.py`：`/api/chat/transcribe` 按 `entry.transport` 分派，缺省仍走原 chat 通道；
5. `tests/test_capability_gates.py`：新增 5 条（provider 路由到硅基流动、缺 key 跳过、两条通道分派、multipart 请求形状），**12 passed**。

部署与复测：

| 步骤 | 读数 |
| --- | --- |
| 重建后端镜像 | `docker compose build backend` → `Built` |
| 重建容器（**先在当前 shell 清除机器级变量**，让 compose 读 `.env`） | `Remove-Item Env:SILICONFLOW_API_KEY` → `up -d backend` → **healthy** |
| 容器内凭据指纹 | `e6e7547bbfa5`（= `.env` 有效值；R11 覆盖问题在本轮操作中被显式绕开） |
| 容器内注册表 | `voice_sf transport=audio_transcriptions base_host=api.siliconflow.cn`；`vision_sf base_host=api.siliconflow.cn` |
| **经应用端点**复测 | `POST /api/chat/transcribe` → **200**，`{"text":""}`，**1 283 ms**（对比修前两次 502：12.0 s / 4.9 s） |
| 回归 | `pytest -m "not slow"`（`backend/venv`，生产同栈）→ **1933 passed, 2 skipped, 18 deselected**，rc=0，396.66 s；同命令在 `backend/venv-new` 下 **19 failed**，用 `HEAD~1` 做同环境对照（`test_stream_cancellation.py`：**15 failed / 27 passed**）⇒ 失败为**既有环境口径问题**，与本提交无关 |

诚实边界：

- 复测音频是 1 s 正弦，只证明**通道与端点可用**（200、空文本），**不证明真实语音识别准确率**；真实语音需 Owner 在页面上说话复测；
- 令牌由容器自身 `JWT_SECRET` 现签，仅用于本次容器内调用，未落盘、未打印；
- `mypy .` 全树仍有 **4 条既有错误**（`main.py` 媒体清理处的 `image_ref/thumb_ref` 注解缺失，位于本轮未改动的行），另在 `backend/venv`（mypy 2.3.0）下表现为 2 条 `Row` 泛型错误——**均非本次改动引入**，本轮未顺手修，避免扩大 diff；
- 机器级 `SILICONFLOW_API_KEY` 旧值**仍在系统里**（无管理员权限），只在本轮重建时被 shell 作用域绕开；后续任何重建都必须继续显式清除或覆盖，否则容器会重新拿到无效键（R11 的流程约束仍然有效）。
