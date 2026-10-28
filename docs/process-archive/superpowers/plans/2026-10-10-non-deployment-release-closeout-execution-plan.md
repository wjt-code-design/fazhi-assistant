# 非部署发布收尾执行书（2026-10-10）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: 使用 `executing-plans` 逐项执行并在关口复核。步骤使用复选框记录。默认由收到本文件的一个助手顺序执行；独立复核必须由不同实现会话完成，不能把自审冒充独立复核。缺少可用复核者时交付待复核材料，不自行豁免。

**Goal:** 修复、验收并交付本项目所有非部署发布准备事项；只有全部必需的非部署发布门禁确实通过，才宣布本阶段完成。

**Architecture:** 保留主工作区和其他助手的成果，在独立候选中接收、修复和验证。先完成离线安全控制，再做受控真实模型验收；随后在可回退维护窗口升级经确认的现用依赖环境，并经独立审查、远端 CI 和分支保护完成 PR 合并。真实数据验收及专业审签缺失时保留阻塞，不用合成测试填补证据。

**Tech Stack:** Windows / PowerShell；Python 3.11 候选环境；FastAPI / SQLAlchemy / SQLite / Chroma / LangChain / 本地 BGE；Next.js / React / TypeScript / Vitest；Git / GitHub Actions。现用解释器、精确依赖版本与云模型由执行前事实核实决定，不把源码默认值当作实配。

## Global Constraints：本书的授权与红线

本书依据用户已完成的纯文本 grilling 对齐及“写执行书但交给助手执行”。收到本文件的助手可在下列边界内执行，无须重新询问已经明确的同一选择；本文不是任意操作许可。

| 项目 | 已确认边界 |
|---|---|
| 总范围 | 所有非部署收尾项：接收复验、缺陷修复、依赖风险处理、浏览器验收、信任门、真实模型/法律质量验收、合成数据迁移恢复、包装与 Git 交付 |
| 执行方式 | 交给收到本书的助手执行；原作者本次只写、复核本书，未开始这些实际操作 |
| 模型能力 | 文本 RAG、rerank、Agent、图片理解/带图问答、语音转写五类；不是新增图像生成或语音合成功能 |
| 模型数量 | 每类一个代表模型；文本 RAG 与 Agent 可共用文本模型。备用模型未实测必须明列，不做全注册表遍历 |
| 费用 | **不设金额上限**；原 30 元上限已取消。保留执行前简要估算、官方价格来源、实际用量记录，估算不冒充账单 |
| 调用范围 | 按 F 的有限清单、请求数、输出长度和超时执行；不无限重试，不静默扩大模型/供应商/样本/轮次 |
| 样本 | 公开官方法条和合成问题、图片、音频。不得使用真实库、真实对话、用户上传件、私有文档或真实身份信息 |
| 真实数据 | 不读取或写入真实业务库、向量库、配额库、媒体及其备份；不为哈希而读字节，也不执行实库 dry-run。合成库演练不等于实库恢复验收 |
| 本地环境 | 隔离验收通过后，可更新**经事实确认的现用本地依赖环境**。不能猜 `backend/venv` 就是产品正在使用的环境 |
| 维护窗口 | 可短暂停止确实使用目标环境的本项目进程；先确认归属、无其他任务依赖、记录启动方式与回退。不能关闭其他助手或任意容器 |
| Git | 独立 `codex/` 分支提交、推送、PR；审查/门禁/保护规则满足后合并已核实的主分支。不得强推、改写历史、绕过保护或混入未确认改动 |
| 阶段完成 | 采用严格口径：全部必需的非部署发布门禁通过才完成；预算/授权/人员/环境/证据缺口均保持未完成，不靠登记风险变绿 |
| 部署 | 明确不执行：选服务器、生产启动/切流、域名/TLS/公网开放、生产数据迁移、运行原 compose 栈、部署工作流或发布到生产 |

执行中产生新的业务语义、数据格式、能力默认开关、降级白名单或授权边界决策时，用 `grilling` 纯文本逐问对齐；不能把本书、旧报告的“推荐”当成用户对具体产品决策的批准。下载依赖、创建私有候选、合成测试是正常实现步骤；操作外部账户、撤销凭据、接受残余漏洞或突破实库禁令不是。

## 0. 单文件接手说明

### 0.1 路径与入口

- 主仓：`C:/Users/33393/Desktop/ai-legal-helper`。
- 目标 GitHub 仓库：[wjt-code-design/fazhi-assistant](https://github.com/wjt-code-design/fazhi-assistant)。不能只按本机 origin 名称判断目标。
- 当前工作汇报：`C:/Users/33393/Desktop/ai-legal-helper/docs/work-report-20261009-backend-implementation.md`。
- 后端问题台账：`C:/Users/33393/Desktop/ai-legal-helper/docs/backend-readonly-audit-20260929.md`，重点是 §13 和 DB-19～DB-23。
- 已修订的收尾审查：`C:/Users/33393/Desktop/fazhi-project-closeout-20261008-7e20048efb4e46068a9ecf1a54c6b527/reports/work-report.md`。
- 该轮证据：`C:/Users/33393/Desktop/fazhi-project-closeout-20261008-7e20048efb4e46068a9ecf1a54c6b527/evidence/review-20261009-01/`；属于历史证据，不回填、不覆盖。
- 项目规则：`C:/Users/33393/AGENTS.md`、本仓 `CONTRIBUTING.md`、`docs/code-review-standard.md`；沿目录另有 AGENTS 时也须读取。

任务、边界、验收与停止条件已在本文件展开。上述报告供追溯；某份报告缺失不能被伪造补齐，应登记影响。需要它支撑的具体历史结论暂不采信，其他独立任务可继续。

本书取代 10-08/10-09 旧计划中的“仅准备、不得产品修复/安装/模型调用/推送”默认授权范围；不撤销冻结物、安全与证据保护规则，不追认此前越界。历史报告里的“调用上限 0”“本轮不提交”是当时状态，不是本轮新限制，也不能改写为当时已经获准。

### 0.2 写书时只读核实的起点，不是接手时现量

2026-10-10 写书时：分支 `master`，HEAD `0b543960c7172ce1ffea57616952e4d5525190c4`，暂存区为空；21 个 tracked 文件有修改，另有以下 4 个未跟踪后端测试。执行者必须重新量，不能要求并行环境永久保持这些数字。

| 集合 | 精确文件（相对于主仓） | 接手处置 |
|---|---|---|
| 后端 tracked 15 项 | `backend/agent/controller.py`、`backend/agent/runtime.py`、`backend/agent/service.py`、`backend/agent/state_machine.py`、`backend/agent/writer.py`；`backend/domain_rules.py`、`backend/llm_errors.py`、`backend/llm_registry.py`、`backend/main.py`、`backend/observability.py`、`backend/retrieval.py`；`backend/scripts/smoke_citation_full.py`；`backend/tests/test_agent_resume.py`、`backend/tests/test_llm_admin.py`、`backend/tests/test_llm_failover.py` | 作为另一助手的候选成果接收复验，不重做、回退或直接提交 |
| 新增后端测试 4 项 | `backend/tests/test_agent_budget_terminal_edges.py`、`backend/tests/test_law_name_normalization.py`、`backend/tests/test_llm_reject_channel.py`、`backend/tests/test_retrieval_category_fallback.py` | 纳入候选清单，不能只拷 tracked 差异 |
| 前端 tracked 5 项 | `frontend/app/admin/sections/KnowledgeSection.tsx`、`frontend/app/admin/sections/UploadSection.tsx`；`frontend/app/chat/page.tsx`、`frontend/app/globals.css`、`frontend/components/chat/InputBar.tsx` | 浏览器补证后决定可整合 hunk，不拿静态测试替代交互验收 |
| 旧文档残差 1 项 | `docs/process-archive/superpowers/plans/2026-09-29-local-candidate-decision-and-release-prep.md` | 默认保护，不顺手改写或提交；确需纳入时单独审内容与归属 |

新后端汇报自报：四票 DB-15/16①③/17/18、49 条新增用例、`1909 passed / 2 skipped / 18 deselected`；mypy 两处 Row 类型错误及 `backend/schemas.py` 格式问题未绿。**这些是助手报告，不是本书作者重跑结果，更不能预填本轮 PASS。**

10-09 复审曾实测：前端隔离离线套件 106 项通过、工具 13 过 1 跳过；它们不是生产构建、浏览器、真实模型或全项目安全验收。历史 `incident-01` 是为哈希读取真实数据库字节的越界，不能因补保护而抹去；新的阶段验收和历史完整符合性分开记录。

### 0.3 不过度设计的执行约定

- 先问是否需要修，再看已有代码/标准库/平台/已有依赖；不新增通用验收平台、插件式调度或新 Agent 框架。
- Ponytail 指“最小可靠完整方案”，不是最少行数。安全、正确性、无障碍、数据保护及已确认功能不能裁掉。
- 一单一次根因修复、一组有区分力测试、一次审查；结构性根因立即重规划。同一 bug 连修三次仍不过必须停止质疑。
- 同一命令失败先分析；完全相同命令最多再试一次。重命令不循环跑，负控的预期失败与产品失败分别标记。
- 人工改文件用 `apply_patch`；格式化工具只作用于明确文件。命令下面给的变量由 A 真实建立，未建立就不运行后续命令。
- 每个原始日志都是新文件：命令、cwd、解释器/版本、开始结束时刻、退出码、完整性、样本/源码摘要必须可核。工具输出截断不得称完整日志。

### 0.4 实际依赖顺序

字母表示责任单，不表示可以跳过前置强行按页运行。先 A；B 先做只读接收/根因核对，运行测试需 C 的私有环境以及 E 的路径、模型来源/信任控制就绪。D 同样需私有前端依赖与网络拦截。B/C/D/E 对应的硬前置、候选自审和独立复核通过后才开 F。H 的包装/CI准备可以提前做；I 推送前须满足 H 的历史/凭据/工作流检查。

G 只有运行源码与依赖配套、回退及维护前置满足才执行；若需 I 先完成代码整合才能安全升级，可先 I 再 G，不为强守字母顺序使现用环境变成“新依赖＋旧源码”。最后 J 汇总，任何必需单未过不能收阶段。

## A. 接手保护、候选与执行登记

**文件责任：** 本仓所有输入仅保护；在新运行根生成 `$closeoutRunRoot/reports/baseline.md`、`$closeoutRunRoot/evidence/input-before.json`、`$closeoutRunRoot/evidence/ownership.json`、`$closeoutRunRoot/reports/gates.md`。生产代码暂不修改。

- [ ] 读适用规则，并用以下只读命令重取 HEAD、索引与受影响集合。新出现的差异先判归属；只有相关文件/hunk 冲突才阻塞该单，不把无关助手的变动统一当越界。

```powershell
$closeoutMain = 'C:\Users\33393\Desktop\ai-legal-helper'
git -C $closeoutMain rev-parse HEAD
git -C $closeoutMain status --short --branch --untracked-files=no
git -C $closeoutMain diff --cached --name-only
git -C $closeoutMain ls-files --others --exclude-standard backend/tests
$closeoutRunRoot = Join-Path 'C:\Users\33393\Desktop' ('fazhi-nondeploy-closeout-20261010-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $closeoutRunRoot -ErrorAction Stop
New-Item -ItemType Directory -Path (Join-Path $closeoutRunRoot 'reports'), (Join-Path $closeoutRunRoot 'evidence') -ErrorAction Stop
```

- [ ] 通过 `using-git-worktrees` 和当前宿主的工作树工具，优先复用本任务合适的已附加工作树；没有则从**本次已核实的本地 HEAD**创建独立 `codex/` 候选，不默认从远端默认分支起步丢掉本地整合史。记录实际路径为 `$closeoutCandidate`。注册失败不自行删目录，应按工具要求重新附加。主仓不切分支、不 stash/reset。
- [ ] 从公开受影响文件与新增测试的显式清单接收字节到候选；每项记主仓 before 摘要、候选摘要、来源与用途。先查清单中是否有密钥/实库/私有文件，不能整树 `copytree`/`robocopy /MIR`，不能复制 `.env`、旧备份、数据目录或凭据留痕。计划书本身可作为本轮文档候选。
- [ ] 单独登记主仓已知禁区：`backend/app.db`、`backend/data/`、`backend/chroma_db/`、媒体、backups、`.env` 族、现役 HF 缓存。最多用文件存在性/mtime 作警报，不打开、不哈希；这类元数据相同**不证明**实库内容一致。
- [ ] 重核冻结清单：`backend/pyproject.toml` 尚排除 `backend/agent/state_machine.py`、`backend/prompts.py`、`backend/scripts/gate5_judge.py`。已存在的 state_machine 改动只作为待核候选接收；核实 DB-15 的具体授权/新冻结基线，不能用“全项目收尾”擅自解冻。查不到有效依据就停止该项整合，向 Owner 请求具体确认；不得恢复覆盖别人的改动。已公开旧冻结源码可以哈希，私有题集/历史 sessions 不读。
- [ ] 每个进程都有独立工作目录、合成 DB/配额/Chroma、缓存、媒体和日志。任何 `main`/`rag_chain`/导入脚本 import 之前完成绑定；`main.py` import 会触发初始化，不能先 import 后隔离。
- [ ] `$closeoutRunRoot/reports/gates.md` 建立 B～I 任务行和 J 的门禁行；每行状态只用 `NOT_RUN / PASS / FAIL / BLOCKED`，附证据路径、对象版本、未覆盖项。历史报告另列，不预填 PASS。

**A 出口：** 归属和禁区清单完整、候选来源可还原、索引原状态受保护；否则不得进入修改/安装。不得以未跟踪总数“大约没变”作为保护判据。

## B. 接收后端四票，清掉阻断型检查与已复现缺陷

**文件责任：** 0.2 后端 19 项；必要时定向修改候选 `backend/main.py`、`backend/schemas.py` 及新增相关测试。新增问题只改已追踪到的共同根因，不扩成全仓格式化。

- [ ] 读新增四票真实调用链和测试，不把“同两份真函数相等”当独立期望。用私有环境复算：步数终止/恢复边、category 回落可见性、拒绝与配额通道、法名归一。每个新增判据需以旧源码/同形坏样本为负控，且失败原因应是断言，不是缺依赖或导入失败。
- [ ] 先在候选运行四个新测试文件，再全量非 slow；统计参数化后的 collected 数，不能把函数数当用例数。核对报告的 49 条增量，差异写明，不硬凑 1909。
- [ ] 定向复现 mypy 的 Row 泛型错误。修类型注解与实际 SQLAlchemy 返回形状一致，不降 mypy、不新增 broad ignore；仅候选 `backend/schemas.py` 确有格式失败时定向格式化，并验证无语义改动。
- [ ] DB-19～DB-23 与第一轮剩余票采用下表，明确“调查/修复”和“需要产品裁定”分开。推荐不是已批准的具体行为。

| 对象 | 本轮执行要求与停止点 |
|---|---|
| DB-19 category | 用合成库分别测试“缺键”“存在该类且零条”“有正确命中”。已存在回落不是通用正确性证明；不得用无过滤结果伪装满足真实 category。不得为此回填真实库。摘 schema/改变过滤语义前用 grilling 裁定 |
| DB-3/20/21 引用与法名 | 排查 `backend/domain_rules.py`、`backend/retrieval.py`、`backend/agent/dept_guard.py`、`backend/agent/writer.py`、`backend/scripts/import_docs.py`、`backend/scripts/capture_eval.py`、`backend/scripts/gen_qwen_cases.py` 的生产/写侧/评测边界。括注版本、章节名不得误合并；别宣称法名归一等于时效校验。写侧 key 变化/判域变化先裁定；仅用合成文件 dry-run，不读现有语料 |
| DB-22 拒绝冷却 | 用 fake 时钟、400/401/403/404/422/429/5xx 网格验证配额与选择/管理快照。报告建议两档 TTL 尚不是批准；具体 TTL、人工解锁与配置恢复语义先裁定，不直接照抄 3600 秒 |
| DB-23 409 文案 | 保留 ownership/并发状态/预算/非法恢复数据的差异且不泄内部状态。用户可见映射措辞先用纯文本给推荐并确认；不能把成功 HTTP 当正确文案 |
| DB-6 / QA 沉淀 | 核 `knowledge_service.py`、`main.py` 的普通用户自动沉淀、管理员确认、版本/引用门。用合成库证明非法日期/无据条号不能通过免审分支；若存在安全放行缺陷，先给失败证据和具体收紧行为再裁定 |
| DB-7 / 降级 | 既有“不扩大技术降级白名单”保持有效；不得为“回答总能产出”把内容验证失败或 TOOL_BUSY 静默改为普通成功 |
| DB-8 / 换嵌入 | 修复方案必须使用新索引验证后再切换、维度/来源校验和失败保留旧索引；所有实验仅合成库，不调用默认会读真库/改 `.env`/杀进程的 `backend/scripts/switch_embedding.py` CLI |
| B-45 / 导入防错库 | `backend/scripts/import_laws.py` 的 CLI 守卫须在与 `backend/scripts/backup_data.py` 同族的入口位置生效，不能 import 时拒绝测试临时路径。测试 `--validate-only` 不加载模型，错路径在读取/改库前拒绝。不要把 `--dry-run` 当不读库 |
| DB-10/11/12 / 安全文档 | 据源码更正令牌吊销、不可按用户清除的 QA 数据、明文公网启动教程。已知限制登记不等于满足隐私删除门；实际清理逻辑仅合成库验证。不得添加“改口令即可吊销旧 JWT”或“无 TLS 可公网使用”建议 |
| DB-13 / WAL | 先在合成数据库验证 WAL、并发和 backup API 恢复；主库启动行为变更/模式切换先明确裁定，不运行真库 PRAGMA |

**B 出口：** 已接收修改的相关正常/边界/失败路径通过，定向类型/格式问题关闭；未裁定项保留 BLOCKED。旧 bug 红在基线里也不是新候选的通行证。

## C. 依赖风险、精确候选环境与索引兼容

**文件责任：** 候选 `backend/requirements.txt`、`backend/requirements-dev.txt`、`backend/pyproject.toml`，必要兼容修复和相关测试；候选 `frontend/package.json`、`frontend/package-lock.json` 的安全升级如确有适用问题；输出 `$closeoutRunRoot/reports/dependency-decision.md` 和精确候选/回退依赖清单。

- [ ] 接收报告中不同环境的风险对象，执行时重查官方公告/发布说明及当前包源：torch CPU、ST/transformers、LangChain 家族、Chroma、LangSmith、FastAPI/Starlette、pypdf、运行与开发工具、Next/React 及前端锁文件。**当前版本可变，不在本书虚构安全目标版本。**
- [ ] 优先验证 torch-only 与 LangChain/Chroma 分案；它们不互斥，不因一个失败就跳过另一个。精确规范化包名、解析版本区间/extra/marker，声明依赖、安装依赖、实际走到的脆弱路径分别记录。
- [ ] 存档中的 torch 某条 `>=2.10` 修复线不等于全部风险关闭；2.13 也不是未经验证的万能目标。`first_patched` 空不等于永无修复。不得自动代签 Chroma 风险接受。
- [ ] 使用 A 的已核基础 Python 新建候选 venv，不修改共享环境；只从官方发布源或可对官方 SHA256 的镜像下载。CPU torch 单独从官方 CPU 源安装，不盲拉 CUDA 包。取得完整解析结果后固定精确版本；不用 `--no-deps`、删除依赖或缩审计范围凑绿。
- [ ] 已核基础 Python 的完整路径登记为 `$closeoutBasePython`（3.11 不可用则该候选/CI一致性腿 BLOCKED，不猜系统 python）。随后运行下列创建命令，后续 Python 一律用这里产生的绝对路径；解析/安装按本单官方核验结果进行，不把本书未知版本填成 latest：

```powershell
$closeoutCandidateEnv = Join-Path $closeoutRunRoot 'candidate-env'
& $closeoutBasePython -m venv $closeoutCandidateEnv
$closeoutCandidatePython = Join-Path $closeoutCandidateEnv 'Scripts\python.exe'
& $closeoutCandidatePython -c "import sys; print(sys.executable); print(sys.version)"
```

- [ ] 配套执行 `pip check`、运行与 dev 双轴审计、导入/序列化/API 回归、合成 Chroma cosine/维度/元数据与查询兼容测试。解析成功不等于行为兼容；新版本空库通过不等于旧格式可迁移。
- [ ] 前端如需依赖安全升级：先复现适用风险、在候选修锁文件、重新安装私有 node_modules，再做完整 lint/类型/测试/build。不得同时重做 UI 或用安装成功代替回归。
- [ ] 源码/依赖变更后重新登记候选摘要。旧环境、升级候选、回退重建三套读数独立，不能用 joint 环境替 backend、镜像或 CI 背书。

**C 出口：** 选定的候选闭包 `pip check` 通过，风险逐对象有现时官方依据与兼容证据。风险未修复/适用性无法证明/安全版本无闭包就 FAIL 或 BLOCKED；不能以“升级困难”默认接受。

## D. 前端五项残差与取消流程的真实浏览器验收

**文件责任：** 0.2 前端五项、`frontend/tests/chat-cancel.test.ts`、`frontend/tests/chat-conversation-cancel.test.ts`、相关现有测试；必要时定向补浏览器可复现用例。输出 `$closeoutRunRoot/reports/browser-acceptance.md`、截图与请求/事件计数。

- [ ] 在候选副本、私有依赖和未占用的回环端口运行页面。事先在浏览器上下文建立请求拦截：只准自己的页面/假 API/本地静态资源，外部 API、真实后端、WebSocket 和非许可资源全部拦截并计数。不能把 BACKEND_URL 指向死端口当完整断网。
- [ ] 使用本地 fake API 和合成管理员/消息/图片；不登录真实服务。默认不占用或重启 3021/8088；G 的维护权限不是 D 可随意复用原服务的授权。
- [ ] 核六种知识状态的徽章、正常/长内容/焦点/hover 计算样式。文字对比按 WCAG AA：普通文本至少 4.5:1，大文本至少 3:1；记录实际前景/背景和比值，不用截图观感替代。阈值来源见本节末链接。
- [ ] 上传区域用 Tab 获得焦点，Enter/Space 各触发一次文件选择；验证可见焦点、Space 不导致页面滚动、关闭选择后焦点可用，不能只查 `role="button"` 字面量。
- [ ] 390px 与至少 768px 宽度测输入栏字号、按钮与长文本/附件、answer-h4、无水平溢出。宽度和计算尺寸留证；不把源码 tailwind 类名当实际排版。
- [ ] 图片能力 true/false/缺失/健康接口失败分支：分别测试选择、拖拽、粘贴；能力明确 false 时不能提交图片，且零真实外发。缺失目前属于 fail-open 形状，是否改成 fail-closed 必须先裁定，不擅改默认业务行为。
- [ ] 新增会话、切换会话、取消流、快速重发：旧流不得跨会话写入、重复持久化或污染新问题；保留 `test_cancel_boundaries.py`、`test_stream_cancellation.py` 后端回归。假流控制证明异常/延迟不是“模型没返回”的混淆。
- [ ] 修复须先有浏览器复现或断言红，再最小根因补丁、相关回归、完整前端门禁。只关闭自己创建的服务，并记录 PID/监听结束；不要执行现有服务的管理脚本顺手 kill。

**D 出口：** 四组残差矩阵及取消/切换场景有实际交互证据，网络越界为 0。静态 106 项旧结果只作历史参考。

对比度依据：[WCAG 2.2 Contrast (Minimum)](https://www.w3.org/TR/WCAG22/#contrast-minimum)。浏览器工具/测试设施不可用时登记 BLOCKED，不临时换成源码断言宣称交互通过。

## E. 模型来源、加载信任门与合成数据演练

**文件责任：** 候选 `backend/rag_chain.py`、`backend/scripts/backup_data.py`、`backend/scripts/chroma_dir_guard.py`、`backend/scripts/import_laws.py`、`backend/scripts/rebuild_embeddings.py`、`backend/scripts/switch_embedding.py`、迁移模块及相关测试；仅在确实需要时修改。输出 `$closeoutRunRoot/reports/trust-and-data-drill.md`。

- [ ] 核实本地 embedding 是配置与源码实际选择的 BGE；rerank 是否云端看实际非敏感路由，不沿用“rerank 本地”的印象。共享缓存 `refs/main` 不能证明官方精确 revision。查 BAAI 官方仓库的小元数据与 commit，下载所需公开权重到本轮私有缓存，版本/哈希/许可证留证，不扫描或复用现役缓存的私有载荷。
- [ ] Loader 信任门使用合成模型目录与无害 marker：阳性对照必须实际创建本轮 marker；默认加载路径应在执行前拒绝不可信自定义代码。警告后仍执行是失败。禁止网/超时/路径护栏需由父进程约束，Windows 无 SIGALRM 不能成为“不测”的理由，也不能绕行批准执行危险代码。
- [ ] 在合成 SQLite/配额/Chroma/媒体目录跑备份→恢复→完整性/行内容/引用/查询检查；测试 WAL、已有目标拒绝、损坏备份、缺额外库、路径分歧、半途失败、不覆盖原输入。只算行数一致不足，须有合成 sentinel 内容与查询结果比对。
- [ ] `backup_data.py` 固定 Chroma/额外库目标不是靠 `DATABASE_URL` 一项就隔离的。调用前逐个核绑定，或按现有测试方式在私有进程 monkeypatch 所有常量；CLI 守卫不许被取消。错绑定实验必须在首次打开源路径之前拒绝。
- [ ] Chroma 升级/embedding 切换：合成旧格式→新候选→查询对照→切换失败保持旧索引。不得调用原路径 CLI 的 `--dry-run`；它仍会读现有库，换班脚本还可能改配置/杀进程。
- [ ] 真实库恢复、真实语料版本元数据仍单列 BLOCKED。公开小语料具有版本元数据只能证明该小语料上的逻辑，不能据此声称已有实库已具备时效能力。

**E 出口：** 信任门有阳性/拒绝对照、合成数据恢复和回退实测；官方来源不足或实验不可观测保持 BLOCKED，不加载未知对象碰运气。

## F. 五类真实模型验收：有限清单、真实路由、独立 gold

**文件责任：** 复用候选 `backend/llm_registry.py`、`backend/multimodal.py`、`backend/retrieval.py`、Agent 与服务端真实入口；新增本轮私有 runner/gold/transport controls 时放 `$closeoutRunRoot/model-validation/`。输出 `$closeoutRunRoot/reports/model-acceptance.md`。不要把临时编排框架塞进产品。

### F1. 路由、隔离与记录

- [ ] 从执行助手**已配置的进程环境变量**安全读取所需配置，API 密钥仅就地认证。若当前助手拿不到配置，报告所缺变量名，要求本机配置；不让用户发聊天，不擅自打开 `.env`/历史备份找 key，不打印配置 JSON、auth 头、首尾片段或密钥摘要。
- [ ] 在允许 import 前，以 `$closeoutRunRoot/model-validation/` 为根建立 `data/app.db`（DATABASE_URL）、`data/quota.sqlite`（QUOTA_DB）、`chroma-public`（CHROMA_DIR）、`model-cache`、日志的绝对绑定。`HF_HOME/HF_HUB_CACHE/HF_MODULES_CACHE` 都在该私有根。媒体当前没有 MEDIA_DIR 环境变量出口：`backend/multimodal.py` 的 `MEDIA_DIR` 与 `_abs` 依赖源码 `BASE`，允许它们在**私有源码副本 backend/media**内运行并登记该绝对路径；不臆造配置、不把副本路径绑定回主仓。进程内答案缓存用独立冷进程/明确失效控制，不发明不存在的磁盘缓存配置。
- [ ] 每类从当前有效配置中选一个满足官方能力/schema 的代表模型，冻结精确 provider/model/非敏感 endpoint/客户端版本/公开输入摘要。不能把 registry 默认第一项、默认 rerank URL 或旧 10-02 路由当本轮实配；不能从一个成功 HTTP 外推全部角色。
- [ ] 先查各已选供应商**当前官方价格/API 文档**，记录文本输入/输出/推理、rerank计费单位、图片和音频计费方式。给简要估算及无法估算项，不虚构单价；失败调用/流式中断可能仍计费。按官方账单可核时校准，否则标“用量/费用估算、实际账单未核”。不设金额停止阈值。
- [ ] 假传输先证明：白名单、未知端点拒绝、调用/重试计数、响应脱敏、缓存命中与真正发送区分、限次/限长/超时拒绝可红。模型 HTTP 只放行冻结的供应商 host/path，重定向须匹配白名单，否则拒绝；假 API 测试与真实验收分进程。
- [ ] 当前 registry 的 SDK `max_retries=3` 可能隐式放大请求。本轮测试客户端关闭隐式重试，并在最外层计实际发送；仅改隔离 runner，不擅自改产品重试默认值。可用既有依赖 transport/event hooks，不新建代理平台。若无法可靠计数/阻止备用路由，停止该类真实验收。

### F2. 一次登记的初始验收清单

以下是**最大请求授权，不是必须花完的数量**；请求包含生成、改写、预处理、重排、planner、verifier、writer，不能只计顶层调用。某病例规则拦截发送 0 次，保留为规则证据，不能计入目标模型调用成功。每类至少有一个正向病例证明目标真实发送及响应。

| 能力 | 初始病例与独立判据 | 首轮模型 HTTP 上限 |
|---|---|---:|
| 文本 RAG | 12 题：4 条公开条文摘录/引用；2 条公开版本元数据场景；2 条同句多日期不能可靠绑定的澄清；2 条缺证据/不存在条号；2 条来源冲突/检索内容提示注入。逐题核 `法名×条号×版本`、答案与证据、拒答/澄清行为；实质法律结论未审的不预设正确答案 | 每题最多 3 次，共 36 |
| rerank | 3 组独立标注的相关/同名误导/缺证据排序；核目标模型、返回索引唯一且在范围内、相关目标进入预登记位置。HTTP 200 和分数有值不是正确排序 | 每组 1 次，共 3 |
| 图片理解 | 2 张合成图：固定虚构文本卡、固定两色/位置图。独立保存原文本/色块答案；走真实带图路径，不能仅以 describe_image 脱离产品问答冒充端到端 | 每张最多 2 次，共 4 |
| 语音转写 | 2 段短合成语音，包含预写虚构句子与数字/日期。逐段人工/独立规则核转写关键字段；优先本机语音合成产生无真人身份音频，不额外付费调用 TTS。不可用时缺样本 BLOCKED；纯音/静音只作负控，不能证明可转写 | 每段 1 次，共 2 |
| Agent | 3 个合成任务：简单检索且引用；两步检索整合；澄清→一次恢复。核真实工具/证据/终稿、状态转移、无重复持久化；step budget 终止另用 fake 边界验证 | 每 run 最多 12 次，共 36 |
| 合计 | 全部辅助调用也在上述额度内 | 首轮最多 81 次 |

每个失败病例分析后至多一次**定向复测**，只重跑该病例，不能自动全套再跑。含复测本轮模型 HTTP 最多 162 次；上限修改/追加轮次/换代表模型先重新对齐。用户取消的是金额上限，不是测试边界。重试必须符合“完全相同命令最多再试一次”；出现重大法律错/越界不适用自动复测。

运行限制：单次模型请求总超时最多 120 秒；每个 Agent run 最多 300 秒、计费状态步数 8、工具调用 4、replan 1、clarification 1。文本输入每次最多 12,000 token、输出最多 2,048 token（包括供应商可控的 reasoning）；图片每题 1 张/1 MB，语音每题 15 秒/1 MB。这些只用于本轮小型合成验收进程，不缩产品的默认预算/最大争点契约。所选模型若 schema 不支持对应约束或推理量无法受控，先报告并登记适配策略，不能忽略限制。计费步骤不等于调用数，两者独立护栏；终止/恢复免费边不得绕过请求护栏。

### F3. gold 和验收边界

- [ ] 运行前冻结病例、公开语料、元数据与期望摘要。官方条文原文零改写；可以有纯格式清洗，但保留原件/官方 URL/发布日期/生效日/版本来源。虚构图文、音频答案来自生成前的固定内容，不来自被测模型。
- [ ] `CONTRIBUTING.md` 的原 `smoke_citation_fast.py/full.py` 默认语料/端点不能直接运行；如复用其断言，应改用本轮公开病例、私有真实入口，并把模型请求计入 F2。同一完整 smoke 不可在表外额外跑一轮。
- [ ] 条文摘录/结构/日期解析等工程 gold 可由官方原文和不同会话独立复算；跨版本法律适用、起算点和争议结论需有能力的法律审查人及有效审查记录。缺审签的法律子集保持 BLOCKED，可先执行不依赖它的工程/拒答子集，但不能宣布 G1 发布法律质量通过。
- [ ] fake 控制覆盖非法日期、形状/API拒绝、耗尽/冷却、连续空结果、流式失败、提示注入及无证据拒答；它们不替代真实模型质量。模型输出自评或另一同源 LLM “觉得对”不是确定性 gold。
- [ ] 通过条件：已执行工程病例预登记的硬断言全部通过，真实供应商/模型/路径有脱敏发送证据，零越界/零误持久化/零把无据答案标 verified。每类能力单列 PASS/FAIL/BLOCKED；12 题不外推总体准确率或照抄 97%/95% 等未证统计门槛。
- [ ] 任一重大法律错、非白名单外发、实库触达、认证异常、计数失真、gold污染，立即停止相关真实运行，保留原证据。不要换备用模型、增轮或放宽期望来“救绿”。修复后须重新登记和复核，超出上述复测需 Owner 再确认。

**F 出口：** 五类有逐项真实验收结果和用量记录；完整法律发布门单独判。10-02 rerank 的有限成功记录保留，但本轮不能直接继承 PASS。

## G. 现用本地依赖环境升级与回退

**文件责任：** 经核实的目标 venv（不是任意两套环境）；必要的本地启动配置变更需先明确路径，不能改 `.env` 或生产配置代替授权。输出 `$closeoutRunRoot/reports/local-environment-switch.md`。

- [ ] 用公开启动脚本、目标进程的可脱敏解释器/路径信息和包元数据确定 `$closeoutCurrentPython` 与基础 Python。不能以目录名、`VIRTUAL_ENV`、某助手跑过 pytest 或签字推断实际服务归属。命令行可能含 secret，先脱敏再记录，不 dump 环境/完整进程命令。
- [ ] 若多套环境/多会话共同使用，目标不能唯一证实，或升级需改启动配置/凭据/触达真库而未获具体授权，则停在切换前，给具体目标选择问题。用户已准短维护，但未准关闭其他任务。
- [ ] 在新根保存现用环境的完整包版本清单（`pip list --format=json` 不含凭据 URL）、Python 构建与安装源可核信息；准备**原版本可重建的完整离线包集合或同绝对路径可恢复的环境快照**。先在私有回退环境实测重建、依赖检查和核心导入/合成测试。只有文件备份存在不算回退通过。
- [ ] 不把新 venv 随意重命名/移动来当现用环境；入口脚本通常绑定绝对解释器路径。优先按已验证候选精确清单在确认目标更新；若需重建，保留旧目录为可恢复备份，所有递归移动/删除前核实绝对目标仅为选定 venv，不得触及仓库根/数据目录，不串 cmd/PowerShell 拼删路径。[Python 3.11 venv 官方说明](https://docs.python.org/3.11/library/venv.html#how-venvs-work)
- [ ] 确认待恢复服务实际使用的**源码版本**与新依赖兼容。若依赖兼容修复只在候选、主工作区尚无安全整合条件，则先完成 I 的工程交付，G 暂停；主工作区有他人差异时不自动 pull/reset 或整树覆盖。需要把已审补丁接入本机时仅做无冲突的明确 hunk，并在接入前后复核归属/摘要；存在冲突回交 Owner，不以升级环境为由吞并其他修改。
- [ ] 维护前列明受影响的 PID/监听端口、启动方式、原健康状态、停止方法、预计步骤和失败回退命令。先读启动源码：若恢复会 import 触发迁移、初始化 QA/配额或其他实库写，**停止并报告**。当前不读写真库授权优先于“恢复服务”。不能先停服务再发现没权安全重启。
- [ ] 通过 G 前置后，停止仅相关本项目服务，确认无占用，按 C 的验证清单升级，运行 pip check、版本/导入检查及重定向到合成库的回归。不允许其他会话同时在该 venv 安装。
- [ ] 只有恢复无需越过真实库边界时才用原方式恢复，核健康与版本。不具备这一条件就保持目标环境不变并 BLOCKED；不能把测试服务换成合成库后冒充原服务恢复。
- [ ] 失败回退至原版本/原绝对路径，实测恢复检查，报告实际中断和残余。回退的原版本若有漏洞，只证明恢复原状态，不作为安全验收 PASS。旧依赖回退材料保留到 Owner 允许清理。

**G 出口：** 现用环境确实更新且可核、可恢复，无实库越界与其他任务中断。若由于真实启动副作用无法安全完成，明确环境未升级，不拿私有候选成功替代。

## H. 包装、凭据/历史安全与远端 CI

**文件责任：** 候选 `frontend/next.config.js`、`backend/Dockerfile`、`backend/.dockerignore`、`frontend/Dockerfile`、`frontend/.dockerignore`、根 `.dockerignore`、根 `.gitignore`、`.github/workflows/ci.yml`、`DEPLOYMENT.md`/相关部署说明，及必要测试；只做本地发布准备，不运行现用 compose 或生产发布。

- [ ] 本地包验证以已有 Python/Node 版本与 Linux CI/Docker 构建目标为工程候选，不替用户选择服务器/架构。Windows build、standalone 可运行性、Linux CI/镜像各列证据；旧 Windows EPERM 不能只因 tsc 通过就关闭。Docker 不可用时该腿 BLOCKED，不自行安装系统级组件。
- [ ] 候选构建不挂载真实数据、不包含 `.env`/备份/模型缓存/媒体，不暴露公网端口。若需要 smoke，独占 127.0.0.1 端口＋合成数据＋无模型外发。实际构建上下文和最终产物检查有无私有文件，镜像声明不等于内部实装。
- [ ] 凭据检查范围为本轮候选的 Git 提交内容、待推送提交范围和当前本地可核相关历史；排除实库、私有数据和凭据文件。环境变量中的当前值只能在内存作为比对输入，日志只出变量名/计数/相对公开路径；旧值缺失不等于历史已洁净。不能用“.gitignore 覆盖”替代 index/blob 检查。
- [ ] **不要直接运行** `b_worktree_value_scan.py` 的默认整树模式：它会从主仓 `.env` 取值并读包括实库在内的全部文件，越过本书范围。旧 `secret_shape_scan.py` 还输出首尾形态，本轮也不能直接当安全出口。复用其可审纯函数或做最小受限包装：先验证公开文本清单，再读取；假 key 阳性/红控、无匹配、不可读输入、异常 stderr、路径夹带秘密分别验证。完整读取失败不得出“干净”。
- [ ] 发现现役凭据曾暴露时，记录键名/受影响范围/所需 Owner 轮换，不输出值、不替用户登录供应商撤销 key。已有 rerank 轮换记录不能推广为 ADMIN_PASSWORD/JWT/其他模型已轮换。仅凭形状扫描无法证明任意口令历史洁净，门禁缺证就 BLOCKED。
- [ ] CI 本地等价门禁包含 runtime/dev、dispatch 守卫、覆盖率和前端；必要时修 `.github/workflows/ci.yml` 的不足，不能降覆盖率/删 audit/扩大 ignore/用 continue-on-error 凑绿。现 CI frontend 只有 build，需要把本轮测试纳入有效关口；dev 审计不能只写报告却从 CI 永久缺失。
- [ ] 推送前检查候选及实际 base 的 workflows：若会部署、发布镜像/包或请求生产环境 secret，本书不授权触发，停止给出隔离 CI 方案。不修改仓库 secret、环境审批或保护规则。公共 PR 的不受信内容不得拿写权限和密钥执行。

**H 出口：** 包范围清洁、门禁有效、待推送历史可达且凭据处置有证据。包装通过仍不是生产平台/访问安全通过。

## I. 独立审查、本地提交、PR 与主分支合并

**文件责任：** 仅 A～H 的明确候选文件/hunk；输出 `$closeoutRunRoot/reports/integration.md`。主仓旧文档残差、其他助手新增未确认项不自动纳入。

- [ ] 修改期间每单先红后绿；在候选做下列 fresh 关口。`$closeoutCandidatePython` 是 C 中实际创建的 venv 的绝对 python.exe，`$closeoutCandidate` 是 A 实际记录路径；不是临时填的占位路径。每条命令独立记录退出码，测试在网络护栏及合成库绑定之后运行。

```powershell
Set-Location (Join-Path $closeoutCandidate 'backend')
$env:COVERAGE_FILE = Join-Path $closeoutRunRoot 'evidence\.coverage'
$env:PYTEST_ADDOPTS = ''
& $closeoutCandidatePython -m pip check
& $closeoutCandidatePython -m ruff check .
& $closeoutCandidatePython -m ruff format --check .
& $closeoutCandidatePython -m mypy .
& $closeoutCandidatePython -m pytest -q -m 'not slow' -p no:cacheprovider --junitxml "$closeoutRunRoot\evidence\backend-junit.xml"
& $closeoutCandidatePython -m pytest -q -m 'not slow' --cov=. --cov-fail-under=70 --junitxml "$closeoutRunRoot\evidence\backend-cov-junit.xml"
$closeoutHarness = Join-Path $closeoutMain 'dispatch-output\agent-quality-20260911'
& $closeoutCandidatePython -m ruff check $closeoutHarness
& $closeoutCandidatePython -m ruff format --check $closeoutHarness
& $closeoutCandidatePython -m pytest -q (Join-Path $closeoutHarness 'test_budget_guard.py')
& $closeoutCandidatePython -m pip_audit -r requirements.txt
& $closeoutCandidatePython -m pip_audit -r requirements-dev.txt
Set-Location (Join-Path $closeoutCandidate 'frontend')
npm run lint
node node_modules/typescript/bin/tsc --noEmit --incremental false
npm run test
npm run test:cov
npm run build
```

命令在新建的专用测试进程中运行；不要把上面的环境设置留在用户/其他助手的共享 shell。每条结束后立即取 `$LASTEXITCODE` 记录，非零分析后决定后续，不能用最后一条绿覆盖前面红。审计使用允许的官方服务出口，与离线产品测试分开。已有 `real_kb`/`slow` 会碰真实语料，不能运行；非 slow 集也须确认无真实路径/fallback。conftest 有 `setdefault`，不保证覆盖外部真 key：测试进程强制测试凭据和无外发拦截。覆盖率文件只能在新根/候选，不为绕旧 safe-delete 问题关闭全局安全工具。没跑的 slow/实库腿明确保留，不改分母称全量全项目。

- [ ] 独立会话从候选 diff、原始新日志和冻结清单复算需求与工程轴，不提供实现者结论让其盖章。记录 reviewer、审查提交/摘要、发现与处置；实现者可解释/复验，不可担任 reviewer。未取得审查不能合并。
- [ ] 按“后端接收与必要修复 / 依赖兼容与清单 / 前端 / CI与文档”拆最少可审提交，不要求一文件一提交。显式 `git add -- <逐项确认的实际路径>`，审 index 文件列表和私有内容检查；禁止 `git add -A/.`、强加忽略文件、以所有 dirty 都属本任务为由收进去。
- [ ] 确认认证可用、远端仓库和默认分支、共同祖先、ahead/behind/缺失对象/保护规则。可使用以下非部署查询；原始 remote URL 若带凭据，不打印。

```powershell
gh repo view wjt-code-design/fazhi-assistant --json nameWithOwner,defaultBranchRef
git -C $closeoutCandidate ls-remote --symref https://github.com/wjt-code-design/fazhi-assistant.git HEAD
```

获取远端 refs 后只做正常 fetch/比较。若远端分叉/缺共同祖先/对象损坏，需要新的具体整合方案；不得 force、拼孤儿历史、把主仓 reset 到远端。新远端基线带来相关变化就重新审差异、重跑受影响门禁。

- [ ] 在 verified 独立分支正常 push，创建指向 verified 默认分支的 PR；PR 说明逐项列验收、未测备用模型、真实数据/法律门残余。不写“ready for production”。若宿主提供 PR 附件工具，创建后附加 PR URL。
- [ ] 获取当前 PR head SHA 的 CI/status/review。创建 PR 不等于 CI 跑过；旧 commit 的绿不等于当前 head 绿。失败先取日志定位并修，不循环 rerun；CI 跳过/取消/所需检查 absent 不是 PASS。
- [ ] 只有当前 PR 的必需检查、相关安全/功能门禁、独立审查全部满足才普通合并。不得管理员 bypass、改变保护/审批以通过；合并前 head/base 变化则核影响并重新验证。GitHub 的必要审查/状态检查受保护分支约束：[官方规则说明](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches)。
- [ ] 合并后记录 PR URL、合并 SHA、主分支最新 CI，复查是否触发新任务并按非部署边界等待结果。PR CI 绿不自动证明合并后 CI 绿。[查看实际工作流记录](https://docs.github.com/en/actions/how-tos/monitor-workflows/view-workflow-run-history)
- [ ] 未读写实库/未选生产平台的门禁可以保持 BLOCKED，而与之独立且安全的工程 PR 可交付；但具体修改依赖这些缺失证据时，该修改不得合并。**允许工程 PR 合并不等于允许 J 把阶段判完成。**

**I 出口：** 可核提交/PR/审查/CI/合并证据齐备，其他助手主工作区与索引不被覆盖。不删除未获清理授权的分支/候选/回退材料。

## J. 严格阶段收尾、阻塞项与下一步

**文件责任：** `$closeoutRunRoot/reports/results.md`、`$closeoutRunRoot/reports/work-report.md`、`$closeoutRunRoot/reports/gates.md`、`$closeoutRunRoot/evidence/manifest.json`。可另给仓库内简要脱敏进度文档；不得回填旧原始日志或旧 PASS。

| 发布门 | PASS 的必需证据 | 目前不能替代的东西 |
|---|---|---|
| J1 工程/安全 | B/C/D/E 对应测试、风险闭合、输入保护、独立审查、相关隐私/信任门真实有效 | 基线也红、风险已登记、静态字面量、警告但仍执行 |
| J2 五类真实能力与法律质量 | F 五类目标真实路径；独立 gold、复杂法律结论专业审查、版本/时效依据；无重大错误 | rerank 旧成功、一个 HTTP 200、模型自评、小题集“总体准确率” |
| J3 本地环境与可搬运候选 | 经核实现用环境完成升级/回退验证；候选构建与声明平台证据 | 验收 venv 代现用、Windows tsc 代 Linux/standalone、venv 改名即可运行 |
| J4 Git/远端 | I 当前提交与 PR、必要 review/CI、合法合并及合并后状态 | 仅本地提交、前一 head CI、保护 bypass |
| J5 真实数据恢复/迁移与语料就绪 | 对真实数据对象的合法恢复验证及版本元数据验收，或符合该门具体标准的有效独立证据 | 本书禁止直接做；合成演练/旧 mtime/旧数据数量不能替代 |
| J6 生产目标的非部署前置 | 具体平台/架构兼容、凭据处置、访问/回退/数据方案及所需 Owner 决策 | 用户尚未选服务器；Linux 工程候选不是生产平台签认 |

部署上线自身在本书范围外，不把“没部署”计为本书执行失败；但生产平台/实数据/专业审查这些非部署必需条件若未齐，严格阶段结论仍是未完成。

- [ ] 每项状态绑定实际对象/时间/命令/退出码/分母/证据路径；测试失败、不可读输入、跳过的项原样保留。历史 incident 单独记录，不因为新候选绿就称历史全程符合性绿。
- [ ] 区分“已修复未复核”“已提交未推送”“PR CI通过未合并”“工程已合并但发布门未闭合”“本阶段完成”。真实库一直禁止时，J5 通常只能 BLOCKED，必须如实报告。
- [ ] 自审五问：责任边界自然；为什么不是直接升级共享环境/只做报告；缓存/同源 gold/静默降级/路径污染有没有对照；数字和官方事实能否核；DoD 是真目标还是 proxy。核每条授权选择均有任务，不用“代码少”替代可靠完整。
- [ ] 对照 A before 和本轮白名单核输入变化；并行助手合法变动单列归属，不擅自恢复。候选、环境、公共证据可以哈希，真库/私有资料始终不哈希。
- [ ] 交付实际运行根完整路径、提交/PR、已完成单、剩余单与失败、费用估算/实际用量边界、维护/回退状态，以及下一步**具体需要谁提供什么**。不只写“继续等审批”。

### 必须预先列出的阻塞，不允许拿掉

1. **真实数据门**：当前禁止实库读取/写入，尚未授权真实恢复验证；要关闭必须另有具体数据对象/范围/回退/时窗批准，或真实对象有效独立验收证据。不要请求笼统“允许所有库”。
2. **法律门**：涉及实质结论的 gold/审签缺合格法律复核者时，助手不能代签，也不能增加 LLM judge 消除它。
3. **生产平台门**：服务器/OS/架构尚未决定。本书可以做本地/Linux工程候选，不能补造选型或开始部署。
4. **环境切换门**：归属不唯一、没有实测回退、存在其他任务占用，或启动会写真库时，不能执行 G。
5. **风险与凭据门**：无官方安全闭包、残余漏洞需要 Owner 裁定、现役暴露凭据需人工轮换/历史无法完整取证时保持阻塞；不因“不设金额上限”扩大账户操作。
6. **审查/远端门**：缺 reviewer、GitHub 权限/必要 approvals、有效 CI 或共同历史时，不合并。给精确失败对象和最小解除条件。

遇到阻塞先完成不依赖它且安全的其他单；同一外部状态不变不要反复重跑。没有安全可推进单时交付部分结果并停止，不能把“坚持执行”理解成无限尝试。

## 作者复核与给助手的建议

- 本书把旧六项残差与新增后端 19 项拆开接收，避免漏掉未跟踪测试；报告自报的测试数字不当现量。
- 选择一个候选顺序推进，而不是共享 venv 并发安装或搭通用验收平台；B/C/D 可以调查互不阻塞，但共享环境切换、stage、push、merge 必须串行。你不是唯一助手，不回退他人编辑。
- 方案对比已明确：隔离候选＋新运行根＋合成库/受控模型验收的方案保留归属、回退和证据边界，代价是需要复制白名单、创建 venv 和维护证据；直接升级共享 venv 的方案较快，但会污染其他会话、无法可靠归因并破坏回退，所以不采用；只写报告不修复/不复验的方案最省操作，却不能关闭本书的工程、模型或交付门禁，也不采用。
- 验收前先冻结尺子，失败先问“产品错、样本错、环境错还是观察器错”，不直接加 if 或换模型。确定性断言有独立来源和真正负控。
- 候选依赖版本和模型路由不拍脑袋固定；该核的执行输入写明核法与无法核实的停止条件，这不是授权助手随便选“最新”。
- 金额上限已取消，F 仍明确有限请求与辅助调用计数；旧 SDK 重试、答案缓存、规则拦截和备用模型不能隐藏真实调用路径。
- 严格阶段完成与工程 PR 合并分开，J5/J6 和专业审签不被测试替代；历史越界不被新验收抹去。
- 建议每完成一单更新进度和下一单的前置，不连续安装多个大升级再回头找根因；每完成五个小目标做一次范围/证据对抗复核。

**接手助手的第一条进度回复应说明：已读本书、实际核得 HEAD/候选路径、其他助手改动如何保护、首先执行 A→B/C 的哪一个有明确条件的步骤。不要宣称“已全面接管并可以直接上线”。**

## 执行交接与书稿自审

本书已按用户已确认的范围保存。默认执行方式是：收到本书的一个助手在独立候选中使用 `executing-plans` 逐项执行，按 A→B/C/D/E→F→G/H→I→J 的依赖顺序推进；每项完成后写入新证据和门禁状态，再进入下一项。用户已经授权“交给助手执行”，因此不需要再次询问同一范围；出现新的产品语义、真实数据授权、残余风险接受或外部账户操作时，仍必须停在本书规定的人工关口。

如果后续明确选择分派多个独立实现者，必须改用 `subagent-driven-development`，为每个任务指定唯一文件/责任边界，并在集成前执行独立复核；不能把并行工作直接视为本书的完成证据。无论采用哪种方式，执行者都不能跳过 A 的保护登记、把历史报告当作本轮 PASS，或把 BLOCKED 改写成“已登记”。

本次书稿自审记录：

- 范围覆盖：A～J 均有责任边界、输入/输出、出口条件和停止条件；真实数据、法律审签、生产平台、环境切换、凭据/风险、远端审查六类已知阻塞均在 J 中单列。
- 占位扫描：未发现 `TBD`、`TODO`、`implement later` 等未完成占位；“占位”一词仅用于描述产品取消文案或禁止把占位路径当真实路径。
- 一致性检查：A 中创建的 `$closeoutRunRoot`、`$closeoutCandidate`、`$closeoutCandidatePython` 在 C、F、G、H、I 的命令和证据要求中保持同名；每条路径均要求执行时以实际登记值替换，不能凭空填值。
- 证据纪律：命令失败、跳过、缺少工具或权限不足均保留原状态；文中的历史数字和历史报告只作来源线索，不预填本轮结果。

计划完成并保存于 `docs/process-archive/superpowers/plans/2026-10-10-non-deployment-release-closeout-execution-plan.md`。执行者从 A 开始；本次写书会话不执行计划中的修复、安装、模型调用、环境切换、推送或合并。
