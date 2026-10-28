# 法智助手全范围整改收尾：接手期工作汇报（2026-10-16—2026-10-24）

> 汇报范围：自 2026-10-15《全范围修复与非部署收尾执行书》交付后至 2026-10-24 的全部工作，含随后插入的任务、并行会话与独立审核人的工作。**§0–§11 保留 2026-10-22 口径**；10-23—10-24 的增量集中见 §12，原表与历史读数不回改。
> 对象：主工作区 master 与候选工作树 `.worktrees/nondeploy-closeout-20261010`（两线自 `0b543960` 分叉，提交互不重叠）。
> 证据层级：源码/提交、门禁日志、独立审查报告、容器实测。本报告只引用有落盘证据的读数；未复算的历史数字标注为“历史口径”。
> 结论先行：**工程收尾的大部分子项已落地并可复核，但“非部署阶段全部完成”（J1–J6 全绿）尚未达到；W08 已跑齐 19 题双树并完成补跑闭合，P0 书名号拒答闸已修复（`070f45a4`）且 3 题重跑通过，仪器两项已裁定，但仍有 Agent 仅 1/3 完成、Q19·B 三格实红与专业签核未闭合；W14 现役切换、W11 完整浏览器清单仍开放。**
>
> 10-24 增量结论：**Q1 方案 B（离线支持审查器）与账号边界 B01–B05 已落地**——评测口径固定 2-of-5，缺口/绿/难绿三组 live 读数与失败归因、重试边界均有落盘证据，干净误杀为 0，但**仍不接线上**；账号边界 B01/B02/B03/B05 已修并回归，B04 仍待生产入口拓扑决策；容器 F3 已由并行会话按 A 方案统一重建（对方回执，本报告未复验容器）。

## 0. 一页摘要

| 维度 | 结果 |
| --- | --- |
| 提交规模 | 自 10-15 起两线合计 **114 笔**（候选线 63 笔，10-16—10-20；主线 51 笔，10-21—10-22；候选线自分叉点 `0b543960` 以来共 147 笔） |
| 任务卡 | W00/W10/W15 已达 PASS；W01/W02/W04/W06/W07/W09/W13 为 FIXED_PENDING_REVIEW；W03/W05/W11/W12 部分；W08 部分（19 题双树已跑齐、方案 C 补跑闭合、P0 已修复 `070f45a4`、仪器两项已裁定、Agent 仅 1/3 完成）；W14 BLOCKED_OWNER |
| 阶段门 | J1 IN_PROGRESS；J2/J3/J4/J6 NOT_STARTED；J5 BLOCKED_EXTERNAL |
| 工程门 | 候选线：57/57 语义控制、2498 passed/11 skipped、coverage 88.67%、ruff/mypy 绿；主线：1963 passed/2 skipped（V5 时点 1940）、ruff/mypy（改动文件）绿 |
| 依赖与包体 | 传递依赖锁 136 条 `name==version`（两遍差分 0）；镜像 `fazhi-backend-w12q3:20261020` 3.97GB；`.env` 未入镜像 |
| 部署 | Docker 镜像重建、R10/R13/R15 三事件闭合；后端容器代码与 HEAD 一致（按 LF 规范化），`/api/health` 200，问答/转写冒烟 200 |
| 质量 | 调优集必引召回 52/52、泛化 17/19；质量分 246/256 = 96.09%（混合效应，不可作纯检索效果） |
| 未闭合 | W08 的 E2-b 声明帧、Agent C01/H01、Q19·B 实红与专业签核；W14 现役切换/凭据、J2–J6、A6-01/A6-02、Owner 侧 B 系列 |
| 10-23—10-24 增量 | 6 笔提交；Q1 方案 B 五组 live 读数（缺口 90、绿 60、cf3828 探针 12、难绿 60 + 修正 15）与 1 次故障注入；账号边界 B01/B02/B03/B05 已修、B04 待入口决策；后端全量 **19 failed / 2033 passed**，与基线失败集合一致（0 新增）。并行会话另有产品侧 P0-1/P0-2 与 W08 复签（§13）。详见 §12–§13 |

## 1. 接手、基线与工作区保护（10-16—10-18）

- **W00 接手台账**：建立新执行根，冻结可信候选 C（`042f8090`，tree `0372f139`）、主工作区 M（当时 HEAD `0b543960`，含 21 项 tracked 修改），逐项登记归属，未回退任何他人改动。
- **证据分层**：源码核实、历史日志、本轮新鲜检查三者分开；旧 RUN 账本存在截断与过期字段，不作为实时真源。
- **决策对齐**：Owner 于 2026-10-18 确认以本地代码历史为开发主线、在候选工作区继续、保护主仓 dirty（C18）；C21 采用“有界寻找合格项、找不到退出直返、只合并可验证重复”的原则。
- **交付入口**：[交接与复核版](file:///c:/Users/33393/Desktop/ai-legal-helper/docs/handoff-full-scope-20261016.md)、[决策记录](file:///c:/Users/33393/Desktop/ai-legal-helper/docs/full-scope-decisions-20261018.md)。
- **诚实边界**：接手轮只核实源码与文档，未重跑产品门、未读真实库/`.env`、未访问现用服务。

## 2. 执行书 W00–W15 逐票状态

状态口径：以 10-18 task-status 为基线，叠加 10-19 至 10-22 的新鲜证据；未重新签核的票保持“待审”。

| 票 | 状态 | 已做 | 关键证据/读数 | 仍缺 |
| --- | --- | --- | --- | --- |
| W00 接手与台账 | PASS | 对象冻结、归属表、执行根 | run/task-status/decisions | D-55 副本/hook 对象最终指认 |
| W01 初始化与隔离 | FIXED_PENDING_REVIEW | 惰性初始化、写围栏、两 lane 区分 | 真权重 lane B 实跑 7 passed/15 skipped | 外部签核；15 条语料类仍受禁读边界 |
| W02 token 观测 | FIXED_PENDING_REVIEW | token 字段修复与边界测试 | 历史门 | Q15/Q17 四腿同快照复测 |
| W03 质量基线 | 部分 | 冻结锚、四次探索、独立判读与提示词修复 | 第 7 轮 24 passed；质量分见 §7 | 最终 19 题回归、专业签核 |
| W04 明确条号未命中 | FIXED_PENDING_REVIEW | 三态区分 + 检索/出口补丁 | 反例先红 | 真实入口复验 |
| W05 检索融合 | 部分 | 容量融合、主锚填满时选项补充 | 检索收益见 §7 | 正式同池对照与签核 |
| W06 受控沉淀 | FIXED_PENDING_REVIEW | P0 暂停自动批准、C21-A 有界选择、B 缓存依赖、C 来源追踪 | 57/57 语义控制、136 passed | 外部签核；真实库迁移另授权 |
| W07 多模态与输出 | FIXED_PENDING_REVIEW | transport 四段贯穿、识图失败可见、语音传输形状 | 反例与跨面判据 | C04 markdown 后半未落 |
| W08 五类真实能力 | 部分 | 双树 19 题同窗口跑齐（旧 `69577e94` / 新 `0b9b4dcc`）、方案 C 5 题各补 2 轮、多模态正样本探针、Agent 三 run、W14 离线演练、P0 修复 `070f45a4` 并重跑 3 题、仪器两项裁定 | 双树单轮 + 三轮中位数读数见专报；12/12 补跑 rc=0 且守卫拒绝 0；文本（19/19 可评；Q2/Q7/Q17 修复后重跑 4/0、5/0、9/1；Q18·B/Q19·B 裁定后 8/0、5/3）/合同/多模态 3 类 PASS，Agent FAIL（1/3 完成）、安全 FAIL（Q19·B P2/P3/C1 实红） | E2-b 声明帧、Agent C01/H01 复跑、Q19·B 三格实红改进、专业签核 |
| W09 安全与 CLI | FIXED_PENDING_REVIEW | 公知占位口令拒斥、重置入口加宽、首启链特征化 | 红转绿、独立复核 Medium 已修 | 外部签核；C06/C07 延期 |
| W10 依赖闭包与风险门 | PASS（带残留） | 三轴 pip-audit、136 条锁、D-45 审计、Linux 闭包解析 | torch 2.13.0 审计 0 条；锁差分 0；haimeng 10-21 签核 | Linux 真装真跑仍缺 |
| W11 前端浏览器集成 | 部分 | 真实浏览器端到端 1 轮、部署后登录/上传/问答实测 | R10/R13 真机读数 | 完整 W11 清单（六状态、宽度、断网等） |
| W12 工程门与包体 | 大部分闭合（账本仍 IN_PROGRESS） | 纯树门、合成恢复、coverage、镜像构建 | 2498 passed、88.67%、3.97GB 镜像 | Linux/真 CI 结构性不可行（ADR-019） |
| W13 独立 review 与发布 | FIXED_PENDING_REVIEW | 本地提交、SSH443 发布、公开范围裁定、C14 维持存量 | 远端 ref 当前 `ee5bfefe`；本地候选 `69577e94` 领先 **27 笔**未全部推送 | 独立签核；PR 因无共同祖先不可行 |
| W14 现役环境与凭据 | BLOCKED_OWNER | 安全操作方案与前置核对 | 交接材料 | Owner 目标环境、凭据、切流授权 |
| W15 总账与证据清单 | PASS | 五层结果、gates、manifest、历史欠账对账 | 清单 **135 条**（10-20 重冻结）独立复算 0 miss；113 为更早口径 | 独立签核；旧 R/legacy 欠账保持 BLOCKED |

阶段门：**J1 IN_PROGRESS**（W06 子集全绿，但其余工程门与最终签核未齐）；**J2/J3/J4/J6 NOT_STARTED**；**J5 BLOCKED_EXTERNAL**。

## 3. 插入批一：QA 选择/撤回与工程闭环（10-18—10-19）

- **W06-P0**：`create_candidate` 改为一律 `pending`，高分不再自动批准写向量。
- **C21-A 有界选择**：新增 `qa_selection.py`、资格优先、同分稳定 tie-break、无合格项直返，S01–S18 控制。
- **W06-B/C**：缓存依赖 P/O/W 复核、历史/摘要/派生 QA 来源追踪与投影、摘要 CAS，B01–B17、H01–H17。
- **Task 10**：57/57 语义控制逐条对账，136 passed；全量非 slow **2498 passed / 11 skipped**；独立复核 1 主审 + 2 验证者。
- **W10 网络批**：pip-audit 三轴分级；chromadb 两项无修复版沿 D-2；torch 2.13.0 审计 0 条；传递依赖锁 136 条、两遍差分 0，落 `constraints.txt` + CI/Dockerfile `-c`。
- **W12 工程门**：coverage 88.67%（W12 门时点；同日全量重跑口径 88.58%）、ruff/mypy 76 文件绿、合成恢复 28 passed、前端四门 rc=0。
- **W13 发布**：6 笔本地提交，SSH over 443 推送，远端分支 `nondeploy-closeout-20261018`；Owner 裁定以分支为交付物、不做 PR。
- **W15 总账**：五层结果、门读数、work-report、manifest（10-20 重冻结 **135 条**，独立 Get-FileHash 全相符）、旧清单对账（R 自闭合、legacy 无清单 BLOCKED）。
- **独立复核抓错并修正**：对账产物硬编码数字、读取声明不符、manifest 缺路径、walk 无异常处理共 4 条；另修正陈旧 manifest 数字。
- 证据：[10-19 交接](file:///c:/Users/33393/Desktop/ai-legal-helper/docs/process-archive/handoff/topic-20261019-w06-w10-w12-network-closeout.md)、[W10 独立验收](file:///c:/Users/33393/Desktop/ai-legal-helper/docs/process-archive/reviews/2026-10-19-w10-lock-landing-independent-verification.md)。

## 4. 插入批二：R01–R25 与 ADR-020（10-20，候选线）

10-20 在候选线落地 R01–R25 系列（其中 R21/R24 经复核为既有防护、无代码改动）与 ADR-020（5 笔 docs/告警）：

| 编号 | 修复内容 |
| --- | --- |
| R01 | 对外身份改随机不可复用 `public_id`，旧数字主体令牌 fail-closed |
| R02 | 保留用户已答“不知道”的未决事实，禁止同一事实重复追问 |
| R03/R04 | 限流转发头只在可信代理采信；登录失败锁定改滚动窗口 |
| R05/R06 | 会话切换视图版本号；作废在途异步结果并清理页面级附件 |
| R07 | 摘要压缩把空响应并入失败信号，不推进 `summary_upto` |
| R08 | Agent 入口与控制器驱动前补取消检查 |
| R09 | Agent 主链路成功调用计配额 |
| R10 | Service Worker 构建号构建期嵌入，缓存名不再依赖 install 事件 |
| R11 | compose 容器挂载点归位 `/app/data` |
| R12 | `restore_drill` 失败映射非零退出，改在备份副本演练 |
| R13 | 上传失败后清空 file input，可重选同一文件 |
| R14 | `useVoice` 统一停止两路录音 |
| R15 | 模型失败即作废半截，后续全空不把半截当答案 |
| R16 | 剥 think 的解析状态按尝试独立 |
| R17 | `import_docs` 先写成功再清旧 seed |
| R18 | 检索融合键纳入来源/条号/版本 |
| R19/R20 | 配额校准基线完整；逐调用按实际 key 记账 |
| R22/R25 | 在途撤回传播动态证据；选引冒烟带 `no_cache`（提交自述“升级为真实生成”，动态收益待补） |
| R23/ADR-020 | QA 撤回契约三问裁定；孤儿向量非零即告警、重复仅记数、维持无删除入口 |

另完成前端纯格式化两文件（`StatsSection`、`UsersSection`），使该批 `format:check` 转绿。

## 5. 插入批三：附件解析、媒体生命周期与部署（10-21，主线）

- **附件解析 A01–A03**：块级 `w:sdt`/`w:customXml` 正文丢失、单元格边界拼接、解析未进线程池。修复提交 `9cd97b0`，新增嵌套表格与 `w:br`/`w:tab` 边界判据；解析告警只落 `legal.knowledge` 日志且不记文件名。
- **媒体生命周期**：删除会话先收集 `image_ref`/`thumb_ref`，库删除后回收无引用媒体；新增 `cleanup_orphaned_media`，仅媒体目录内且无引用时删除，失败只告警。提交 `81e1744`、`4159d85`。
- **部署执行**：后端/前端镜像重建并上线；新增 `docs/runbooks/deployment-v1.md`。
- **R10 解除**：Docker Hub 不可达期间改用 DaoCloud 镜像源拉取 `node:20-alpine`，本地打标签重建前端镜像，未改 daemon；caddy 未重启，backend 因依赖健康检查被重建。
- **R13 两次更正**：首次误判“已同源”，Owner 控制台截图证明浏览器仍请求 `162.14.81.34:8000`；根因是构建期 `NEXT_PUBLIC_API_URL` 被烤进 bundle。将 `frontend/.env` 置空后同源重建，登录页 8 个分片 0 处绝对基址，`POST /api/auth/login` 可达。
- **R15 语音通道**：在线实测 `/models` 200、`/audio/transcriptions` 200、`chat/completions` 返回 400；注册表缺 `siliconflow` 分支，语音/视觉误走 LongCat。新增 provider 分支、`transport` 字段与 `transcribe_audio_transcriptions`，容器内端点复测 200（1.28 s）。
- 证据：[部署前门禁报告](file:///c:/Users/33393/Desktop/ai-legal-helper/docs/process-archive/reviews/2026-10-21-pre-deploy-gate-report.md)、[附件解析独立复核](file:///c:/Users/33393/Desktop/ai-legal-helper/docs/process-archive/reviews/2026-10-21-attachment-parsing-independent-review.md)。

## 6. 插入批四：第 5 轮数据生命周期/流式修复（10-21—10-22）

独立审查 V5-01～V5-04 全部成立，按最小修复落地：

| 编号 | 问题 | 修复 |
| --- | --- | --- |
| V5-01 | 删除会话/账号不清 `AgentRun`，SQLite 主键复用使孤儿 run 被新会话认领 | 删除时同事务清 run 与级联子记录；`load_owned_run` 增加“run 不早于会话”身份守卫 |
| V5-02 | 技术降级只拼争点与回答，丢原问题/事实/未知项 | 新增 `_resume_query_projection` 投影 |
| V5-03 | 金额区间单位被非捕获组替换成 `$3` | 两处改捕获组，断言去标签文本等义 |
| V5-04 | `includes("[DONE]")` 误杀正文 | 仅当帧体严格等于 `[DONE]` |

- 新增/追加用例：`test_agent_run_delete_lifecycle.py`（4）、`test_agent_resume.py`（3）、`test_annotate.ts`（1 组）、`test_sse-frame.test.ts`（2）。
- 门禁：后端全量非 slow **1940 passed / 2 skipped**；前端 vitest **86 passed**；ruff/mypy（改动文件）绿。
- 上线后核验：容器三文件哈希与 HEAD 一致、健康 200、转写 200、孤儿 run 实测 **0**。
- 证据：[修复记录](file:///c:/Users/33393/Desktop/ai-legal-helper/docs/process-archive/reviews/2026-10-21-data-lifecycle-streaming-fix-record.md)。

## 7. 质量优化专题（并行助手主做，我复核）

### 7.1 检索层

| 阶段 | 调优集召回 | 泛化集召回 |
| --- | --- | --- |
| 基线 | 36.5%（19/52） | 57.9%（11/19） |
| 四轮补组后 | 78.8% | 68.4% |
| 体检+通则+邻近 | 82.7% | 68.4% |
| rerank 真正生效 | 82.7% | 68.4% |
| 同域补全后 | **100%（52/52）** | **89.5%（17/19）** |

> 表中中间轮数字为历史口径，未逐轮复算；可独立复现的是最终 52/52 与 17/19。

- 关键根因：compose 从未注入 `RERANK_*`，容器内 rerank 默认关闭；评测又被根 `.env` 空 key 覆盖；配额监控使 bge 被判耗尽。修复后容器 `RERANK_ENABLED=true`、配额改为纯开关。
- 独立复算：从 `ctx_final4/` 按法名+条号重算，13 道 JSON 金标题 42/42，N01–N03 合计 10/10，泛化 17/19，缺口恰为 G01 510、G05 1198。
- 金标修正三处并核原文：著作权法 24→29、民法典 977→978、E03 806→770。

### 7.2 质量分与审核

- 质量分逐题表 16 项求和为 **246/256 = 96.09%**；原稿 240/93.75% 系算术错误，已撤回。
- 关键限制：最终答复生成时工作区 `prompts.py` 已被并行会话改为未提交版本，质量分是“检索+提示词”混合效应。用冻结提示词重跑 6 题：**92/96 vs 90/96**，净 +2（2 题 +1、4 题持平、无负向）；C04 冻结版丢失结论卡标题属质量反向信号，整体仍属样品量级。
- 我对其工作报告做了三轮独立审核，F1–F6 全部闭合：
  - F1 总分与逐维底稿、下游两张表的传播已修正；
  - F2 混合效应已披露、冻结对照已留痕；
  - F3 三份未提交 WIP 已按方案 A 提交并以 HEAD 重建；
  - F4 缺条口径统一为“4 次匹配 / 3 个问题”（我首轮正则过窄，已在审核记录中更正）；
  - F5 分母标注；F6 文档同步。
- 证据：[第 5 轮只读审查](file:///c:/Users/33393/Desktop/ai-legal-helper/docs/process-archive/reviews/2026-10-21-data-lifecycle-and-streaming-readonly-review-round5.md)、[第 7 轮质量测评](file:///c:/Users/33393/Desktop/ai-legal-helper/docs/process-archive/reviews/2026-10-22-answer-quality-readonly-evaluation-round7.md)、[我的审核记录](file:///c:/Users/33393/Desktop/ai-legal-helper/docs/process-archive/reviews/2026-10-22-quality-eval-work-report-audit.md)。

## 8. Agent 延迟与断连（第 6 轮审查 + 修复）

| 编号 | 问题 | 处置 |
| --- | --- | --- |
| A6-01 | 短关键词被判定覆盖整句事实，金额/工龄可能未进写作输入 | **未修**（代码级判定，待专项） |
| A6-02 | Agent 完成后才返回 SSE，长任务可能触发前端 180s 无数据超时 | **未修**（需流式改造，待专项） |
| A6-03 | 已取消请求仍先执行分解与控制器 | **已修**：`controller/service` 全程 `cancelled` 检查，`CLIENT_DISCONNECTED` 持久化失败（提交 `7c9ecee`） |
| O6-01/02/03 | 同轮争点检索串行、超时线程占槽、调用次数不封顶秒数 | 记录为容量边界，未改 |

说明：本机容器实测（2026-10-22）`AGENT_ENABLED=false`、流量比例 0，本项当前不影响线上普通问答。

## 9. 当前运行状态与门禁（10-22 晚）

| 项 | 读数 |
| --- | --- |
| 后端全量非 slow | **1963 passed / 2 skipped / 19 deselected**，rc=0（10-22 收尾，含新增用例；V5 门禁时点为 1940 / 2 / 18） |
| 后端静态 | ruff check/format 全过；`mypy .` 仍 **2 条** `Row` type-arg（venv 2.3.0 口径；新版 mypy 全树另报 4 条，均既有） |
| 前端 | vitest 86 passed（历史）；`format:check` 仍 **4 文件**红（既有） |
| 容器代码 | `prompts.py 7b7fd761`、`controller.py 25955d88`、`service.py 172ec7fa`，按 `.gitattributes` 的 LF 规范化后三者均 == HEAD（容器工作副本为 CRLF，原始字节哈希不同） |
| 健康 | `/api/health` 200；模型 `LongCat-2.5-Preview`；`RERANK_ENABLED=true` |
| 冒烟 | 语音转写 200（2.01 s）；普通问答 200（87.19 s，3 帧/3318 字节） |
| 工作区 | 主工作区 tracked 零改动；候选工作树另有 5 个 tracked 修改（`llm_registry.py`、`settings.py`、`test_llm_registry_boot_impl.py`、`docker-compose.yml`、`docs/ADR.md`）；主线 HEAD `dad4a7dd`（报告落盘后推进），候选线 HEAD `69577e94` |

> 本节为 10-22 晚口径。10-24 最新门禁读数（后端 19 failed / 2033 passed、前端 91 passed、ruff/pre-commit）见 §12.4；容器基线为 F3 重建时的 HEAD（`e713480`），不含其后的 `5bae84c1`、`b752a11b`、`e7394b85`、`ce4ac382`。

## 10. 未闭合项与解除条件

### P0 需决策/需真实环境

1. **W08 专业签核与 Q19·B 实红**：P0 书名号拒答闸已修复（`070f45a4`）并重跑 Q2/Q7/Q17；仪器两项（Q18·P6/C1、Q19·P1）已按冻结文本裁定（Q18·B 8/0、Q19·B 5/3）。仍需 Q19·B P2/P3/C1 三格真实模型失败的改进，以及法律专业签核人逐题签核（见 W08 专报）。
2. **W14 现役切换/凭据**：目标环境、切流授权、13 字符凭据现役性核验。
3. **W11 完整浏览器清单**：六状态徽章、390/768 宽度、断网/空答等尚未逐项留证。
4. **B 系列 Owner 动作**：Docker data-root 迁 D（C 盘余 19.9GB）、C13 生产基址、D-55 Chroma 对账、R14 真机验收。

### P1 质量/协议遗留

1. **A6-01/A6-02**：事实覆盖判定与 SSE 首事件延迟，需专项设计与真实耗时测量。
2. **W07 C04 后半**：markdown 白名单定点清理与三出口一致性未落地。
3. **质量分混合效应**：96.09% 不可作纯检索效果对外引用；需冻结提示词重跑全量后才能宣称生成侧收益。
4. **基线历史数字**：36.5%/78.8% 等缺完整基线 ctx 快照，未独立复算。

### P2 门禁与依赖

1. `mypy .` 2 条、前端 `format:check` 4 文件：既有红，未混入功能批。
2. R06 pip-audit：24 条/5 包待依赖专项；无修复版沿 D-2 登记。
3. W10 Linux 真装真跑、真 CI：结构性不可行（ADR-019），仅本地等效验证。

### P3 历史总账

1. 旧 R/legacy 证据欠账保持 BLOCKED，不用新清单销旧账。
2. QA 请求/记录对账（277→140/141、154/279）需授权样本。

### 10-23—10-24 新增未闭合项

1. **B04（账号边界）**：Caddy → 后端 CF 头信任链未修，需先确认生产入口是直连 Caddy 还是 Tunnel-only；决策与两个可选方向见 §12.3。
2. **19 个后端基线失败**：`test_stream_cancellation` 15、`test_cancel_boundaries` 1、`test_llm_lifecycle` 3；HEAD 干净树同样红，按技术债另立，不归本批账号边界修复。
3. **pre-commit `--all-files` 空白债**：ruff rev 升到 v0.17.0 后首跑命中 1387 个既有文件的尾随空白/末尾换行（含 `release-evidence/`、`diag/` 冻结产物），已回滚未回填，待定“冻结目录 excludes + 分批修”策略。

## 11. 诚实边界与教训

- 本轮汇报的事实来自落盘文档、提交与新鲜门禁读数；W08 在本报告定稿前已补跑真实模型双树、方案 C 与 P0 修复后的 3 题重跑，读数见 [W08 质量评测专报](file:///c:/Users/33393/Desktop/ai-legal-helper/docs/process-archive/reviews/2026-10-23-w08-quality-eval-summary.md)；**其余 16 题仍为修复前新树读数（混合口径），未读 `.env` 原件、未访问真实业务库、未做现网切流**。
- 历史数字（36.5%、78.8%、82.7% 等）为历史口径，未逐项复算。
- 质量分与法律结论的机器复核不等于专业签核。
- 本周期重复出现的错误类型及处置：
  1. **凭记忆写数字、不回加**（240 vs 246）→ 撤回并以逐维底稿为准；
  2. **不核时间戳就下结论**（prompts 混合效应）→ 补披露与冻结对照；
  3. **漏报并行改动**（controller/service）→ 补报并纳入发布基线；
  4. **口径不定义**（自曝缺条 4 处）→ 给出正则与“问题数”双口径；
  5. **修正不传播**（底稿改了、下游表没改）→ 三轮审核后同步，并约定收尾做全仓数字一致性扫描。
- 工具教训：长 Markdown 不用 bash heredoc（反引号会被吞）；PowerShell 5.1 注意无 BOM 中文乱码与 `@()` 绑定崩溃。

## 12. 增量更新（2026-10-23—2026-10-24）

### 12.1 提交与基线

| 提交 | 内容 | 读数 |
| --- | --- | --- |
| `8652a005` | 代提交归属不明的第三方 WIP（10 文件，prompts/main/runtime/5 测试/前端取消测试） | 差分门禁：HEAD 同口径 23 failed → 19 failed，**0 新增、4 修复**；提交信息已注明归属与复核要求 |
| `e7134804` | ruff-pre-commit 升 `v0.17.0`，与工作区 0.17.0 对齐 | 10 个代提交文件在新 rev 下全绿；`--all-files` 首跑命中 1387 个既有文件空白/EOF（未回填，见 §10 新增未闭合项） |
| `5bae84c1` | 离线支持审查器（方案 B）本体 + 34 单测 + 两套回归集 + runner + 4 份报告 | 21 文件、+3178；`agent/service.py`/`agent/runtime.py`/`main.py` 零引用，评测边界有测试钉住 |
| `b752a11b` | 难绿样本（多跳/保留意见）与重试故障注入读数 | 难绿 60 次 9/12；修正 15 次 15/15；注入三场景见 §12.2 |
| `e7394b85` | 账号边界 B01/B02/B03/B05 修复 + 定向测试 | 6 文件、+307/−22；定向 14 passed；全量 19 failed / 2033 passed，失败集合与基线一致 |
| `ce4ac382` | [账号边界第 4 轮修复回执](file:///c:/Users/33393/Desktop/ai-legal-helper/docs/process-archive/reviews/account-boundaries-round4-fix-receipt.md) | 逐项状态、证据与未覆盖边界 |

- 代码提交止于 `e7394b85`；其后 `ce4ac382`、`e385f1f8`、`976bbee`、`a9be0514` 均为文档提交（回执、本报告更新、复核修正、回执存档）。工作区 tracked 零改动，未推送。
- 容器 F3：并行会话按 A 方案统一重建并回执（`/api/health` 200、P0-1/P0-2/纪律/取消边界在容器内确认、K01 回归正常）。**该读数来自对方会话回执，本报告未复验容器**；容器基线为 `e713480`，不含上表后三笔提交。
- 期间并行会话另有 `022fb67e`、`0d25cd67`、`7ca28631`、`27d880a4` 等提示词/W08 文档提交，不在本会话改动范围内，未回退。

### 12.2 Q1 方案 B 评测读数

对象：[support_review.py](file:///c:/Users/33393/Desktop/ai-legal-helper/backend/scripts/support_review.py)——逐 claim、证据封闭的离线支持审查器；**只进评测，不接线上**。判据与完整过程见 [稳定性报告 §8–§13](file:///c:/Users/33393/Desktop/ai-legal-helper/docs/process-archive/reviews/2026-10-23-round67-q1-support-review-stability.md)。

| 样本 | 调用 | 结果 | 关键读数 |
| --- | --- | --- | --- |
| 缺口回归（工资 6 claim） | 90 | 2-of-5 聚合全 PASS | 未产出 verdict 5 次 = **5.56%**（Wilson 95% CI 2.40%–12.36%）；§8 两组各 6/6（合计 12/12）、§9 6/6，回归全 PASS |
| 正常答案绿对照 | 60 | 12/12 `SUPPORTED` | 单次 true 59/60 = 98.33%；单次误杀 1/60 = **1.67%**（CI 0.29%–8.85%）；case 级误杀 0/12 |
| `claim_cf3828` raw 探针 | 12 | — | false 7、true 2、span 过短 2、不可解析 1；无 verdict **25%**，与历史 26.7% 同量级 |
| 难绿样本（多跳 6 + 保留意见 6） | 60 | 9/12 | 3 条失败均为**出题问题**：692 与证据第三款（宽限期起算）矛盾、686 未绑 688、82 含法条外元陈述 |
| 难绿修正版（3 条） | 15 | 3/3 | 三条均 5/5 判 true，反向确认失败来自出题而非误杀 |
| 重试故障注入 | 3 场景 | 全部符合预期 | S1 首次坏→第二次真实 judge：`attempts=2`、`REVIEWED`；S2 连续坏：`attempts=2`、`INVALID`；S3 契约违约：`attempts=1`、不重试 |

**口径固定为 2-of-5**：按实测概率估计，2-of-3 在 `claim_d0510d` 上的漏判约 35.2%，2-of-5 约 8.7%；1-of-3 的绿样本聚合误杀约 4.9%，不可接受。此前 18 次「6/6 PASS」用的是 2-of-3，读数偏乐观。

结论与边界：
- **干净的误杀为 0**：在「断言与所绑条文一致」的前提下，没有一条正常 claim 被聚合为 `UNSUPPORTED`；但 case 级样本量小（0/12 的 95% 上界约 26.5%），不能写“误杀率已量化”。
- 难样本上契约违约 3/60 = 5%，失败票只进 `INSUFFICIENT_EVIDENCE`，不会变成 true/false。
- 失败归因已能区分 `JUDGE_FAILURE:<异常类名>`、不可解析 JSON、span 过短/非逐字；90 次缺口复跑中调用异常与不可解析均未再出现，§11 的 12 次探针有 1 次不可解析（但探针绕过 `review()`），网络 vs 坏 JSON 的完整链路归因仍无新样本。
- **仍不接线上**：缺“更大绿样本 + 人工仲裁流程 + 监控口径”，线上阻断未启动。

### 12.3 账号边界 B01–B05

依据：[第 4 轮只读审查](file:///c:/Users/33393/Desktop/ai-legal-helper/docs/process-archive/reviews/account-boundaries-readonly-review-round4.md)（候选 HEAD `69577e94`）；本章按当前 master 复核。

| 编号 | 状态 | 修复与证据 |
| --- | --- | --- |
| B01 密码字节边界 | **已修复** | `RegisterIn` 按 UTF-8 字节拒绝 >72；注册接口 422（原 500）；`hash_password` 对 CLI 入口同样拒绝；覆盖 72/75/76 字节与 emoji |
| B02 并发失败计数 | **已修复** | 失败计数读改写加锁；16×100 并发计数精确 1600；**一红控制**去掉锁后只记 649/1600 |
| B03 未知用户名无界增长 | **已修复** | 登录用户名限长 32；未知用户名不落失败状态；过期记录阈值回收 |
| B04 Caddy CF 头信任链 | **未修复（阻塞）** | 需先定入口拓扑：直连 Caddy 则删 CF 并重建 XFF；Tunnel-only 则停发 8088；两者并存需按 cloudflared 来源白名单。盲目删 CF 会把 Tunnel 用户聚成一个 10/min 共享桶 |
| B05 迟到 401 清掉新会话 | **已修复** | 普通/流式 401 均只在“请求发出时的 token 仍是当前 token”时失效；4 个前端用例覆盖两种请求 |

回归：
- 定向 `pytest tests/test_account_boundaries_b01_b03.py` → **14 passed**。
- 后端全量 `pytest -q -m "not slow"` → **19 failed / 2033 passed / 2 skipped / 19 deselected**，失败集合与修复前基线逐条一致（**0 新增、0 修复**）；19 个均为既有基线失败。
- 前端 `vitest run` → **10 files / 91 tests passed**；`tsc --noEmit` 通过。
- 未跑真实 HTTP、浏览器、Caddy、容器；B04 的运行时可利用性仍取决于生产入口。

### 12.4 门禁与诚实边界

- 后端全量非 slow：**19 failed / 2033 passed / 2 skipped**，402.85 秒；19 个失败为 `test_stream_cancellation` 15、`test_cancel_boundaries` 1、`test_llm_lifecycle` 3，HEAD 干净树同样红。
- 前端：91 passed、`tsc --noEmit` 通过；**全量 `format:check` 未在本轮重跑**，历史 4 文件红仍按既有债处理。
- ruff 0.17 / pre-commit：本批改动文件全绿；`--all-files` 仍因 1387 个既有文件空白债而红（§10 新增未闭合项）。
- 本增量没有做：真实模型生成质量重评、容器内复验、Caddy/隧道实测、人工法律签核；Q1 审查器与账号边界修复均不改变“非部署阶段全部完成”未达成的结论。

## 13. 并行会话增量（10-22—10-24，另一助手汇报）

> 本节按委托方提供的另一助手工作汇报整理。本会话只核对了文中 8 个提交在 `git log` 中存在、报告文件已落盘；**未重跑其测试，也未复验其线上实测**。凡“其口径”均指该汇报原文。

### 13.1 产品侧：真实用户反馈驱动的两处修复

用户反馈“民事诉讼举证责任”答复慢、参考法条 26 条多无关。实测归因：展示层未按答复实际引用过滤、检索层无法域限定。

| 事项 | 提交 | 读数（其口径） |
| --- | --- | --- |
| P0-1 参考条文按答复实际引用过滤，7 处下发点全覆盖 | `0b9b4dcc` | 线上实测该题参考条文 **26 条 → 2 条**；跨域噪音清零；答复质量保持 |
| P0-2 程序法域限定：点名诉讼法域时排除跨域程序法 | `91c9504d` | 同题跨域程序法不再混入 |
| 概念题评测集 6 题（K01–K06，金标经元典核实） | `93ed1cbd` | 召回 **9/9** |
| 上线后暴露的重复下发修复 | `f819cf4f` | 场景组+检索同时命中时只保留首次 |
| 产品侧回归 | — | 22 题回归零损失 |

产品侧主报告：`dispatch-output/quality-eval-20261021/report.md`。

### 13.2 W08 法律质量签核（19 题全链路）

| 阶段 | 结果（其口径） | 证据 |
| --- | --- | --- |
| 预确认（10-22） | 17 题同意；Q2 判据硬伤；90+ 条金标经华宇元典逐条核实 | `docs/process-archive/reviews/2026-10-22-w08-precheck-signback.md` |
| 终签（10-24） | 按题 **14 过 / 3 不过 / 2 存疑**；两例高危：Q5 用户可能少主张 **72000 元**、Q19 变相协助考试作弊 | `2026-10-24-w08-final-signback.md` |
| 归因诊断 | Q4=KB 缺《城镇房屋租赁合同解释》正源；Q5/Q19=生成层 | `2026-10-24-w08-failure-attribution.md` |
| 修复 | KB 补入该解释全 16 条 `a81c8b26`；提示词纪律 `931a6f58`/`0d25cd67` | 提交见左 |
| 复签 | Q19 已闭环通过；Q5 高危数值全修复；Q4 引用四处硬伤全清；两题各余 2–3 处低成本待补 | `2026-10-24-w08-resign-q4q5q19.md` |
| 总结收口 | 链路/终态/发现/决策清单 | `2026-10-24-w08-acceptance-summary.md`（`7ca28631`） |

报告副本：桌面 `C:\Users\33393\Desktop\answer-quality-eval-20261013\` 下有 5 份 W08- 报告 + 3 份复签答案；仓库版为 `docs/process-archive/reviews/` 下 6 份去前缀版（多一份 `2026-10-23-w08-quality-eval-summary.md`）。

### 13.3 工程基线（与本报告 §12.1 互证）

- 并行会话解除“容器跑未提交代码”状态：`8652a005` 代提交 10 个第三方 WIP（差分 0 新增 / 4 修复）、`e7134804` 升级 ruff 门禁，随后完成 A 方案统一重建。
- 容器验证：健康检查、P0 系列/纪律/取消边界功能、K01 回归全部通过（对方回执；本报告未复验）。
- 与 §12.1 是同一组事实，本节不重复读数。

### 13.4 复盘发现与剩余项

三个技术发现（其口径）：
1. 金标“模型对、金标错”已累计 **4 例**——金标必须过元典核实；
2. 修复存在“注意力转移”效应（复签实证）——后续修复须全格回归；
3. 提示词规则常量与提示词文件解耦，可作为提示词类修复绕开并发 WIP 的标准路径。

剩余 7 项（其验收总结报告第五节；口述把 Q4/Q5 合并为一条，故看似 6 项）：Q5 补充修订（低）、Q4 补充修订（低）、Q10 条号修订后复检（低）、Q17 人工律师复核（中）、19 个 HEAD 既有测试失败立项（中）、C0-1 产品注记改纯文本（极低）、Q13·R2·P3/P4 尺子扩形（低）。其建议：前三项（Q5/Q4/Q10）加 Q17 完成后申请发布。

> 与本会话 §12 的关系：§12 是代码/评测/账号边界的本会话读数，§13 是另一助手的汇报整理；两者共同构成 10-22—10-24 的总账，证据强度按各自标注使用。

## 附录 A：提交索引（按主题，节选非全量）

### 候选线（10-16—10-20，63 笔，HEAD `69577e94`）

- 初始化/隔离/多模态：`4c8c3ca3`、`b6dac95c`、`0180cbd8`、`14febe65`、`b06af587`、`4c7a07ed`、`0a0ec986`
- W06 QA 选择/撤回：`88f774a9`、`f98fda78`、`06da7cca`、`10d1dc06`、`e3f4f5ac`、`bf2a44c6`、`17f05584`、`8617dd55`
- W10 依赖/闭包：`cc160dae`、`21972ff4`、`c7a381fb`、`b406ab80`、`187174ff`、`b1bfe919`、`ee5bfefe`
- W12 工程门：`8b83da4d`、`eef885f8`、`34118be2`
- R 系列：`73289643`、`3b56dee8`、`91420592`、`db995d3b`、`a9c70d21`、`4001e1cb`、`e821a1c2`、`d5eaf2cd`、`9448f266`、`7bc424c9`、`6b998620`、`4426767a`、`0b9243c7`、`30a76740`、`68d3bbfc`、`aa3aabdb`、`820fe3c2`、`7be601e5`、`4ba42379`、`cf78aa73`、`adf65d7a`
- ADR-020：`3af5ac2b`、`c18ea8aa`、`cc3aace7`、`7f16b596`、`69577e94`；前端格式 `0baf1897`
- W09 加固：`8b2e79f1`、`1d36c91d`

### 主线（10-21—10-22，51 笔；报告落盘前 HEAD `bb5b9dd4`，当前 `dad4a7dd`）

- 附件解析/媒体：`9cd97b0c`、`81e17441`、`4159d856`、`a297b428`、`a290eba2`、`8584a429`、`ac6f0ad8`、`6322afb5`、`4d267cd4`
- 部署与线上事件：`b57ffd7a`、`a0039da6`、`26e82925`、`16b79831`、`e5e69fb8`、`a19b6e9a`、`e6abf681`
- 第 5 轮修复：`105e240c`、`90abb054`、`ca03a044`、`acb6ed01`
- 质量优化：`af35d1d5`、`a014d72d`、`6e86ec26`、`59782cc2`、`d5c5c428`、`b12ba51b`、`44870649`、`51e47de9`、`ddfe47a9`、`e150836e`、`26b13f67`、`233d97ff`、`21bdc8cd`
- 审核与收尾：`bd229194`、`30ace93e`、`fd06d0e1`、`edc02a29`、`5d1e4138`、`7d88111e`、`de548077`、`7c9ecee7`、`27aeeb29`、`bb5b9dd4`

### 主线增量（10-23—10-24，6 笔）

- 代提交/门禁/评测/账号边界：`8652a005`、`e7134804`、`5bae84c1`、`b752a11b`、`e7394b85`、`ce4ac382`

> 以上为按主题节选，非全量索引。两线自 10-15 起共 114 笔，未列出的提交（如 `042f8090`、`c9a4b4f4`、`a5f268db`、`ef741851`、`4321672b`、`8580af43` 等）可直接用 `git log` 复核，不应把本附录当作提交总数证明。

## 附录 B：主要证据文档

| 主题 | 文档 |
| --- | --- |
| 接手与交接 | `docs/process-archive/handoff-full-scope-20261016.md`、`docs/process-archive/handoff/topic-20261019-w06-w10-w12-network-closeout.md` |
| 决策 | `docs/process-archive/full-scope-decisions-20261018.md`、`docs/ADR.md`（ADR-019/020/021） |
| 独立审查 | `docs/process-archive/reviews/2026-10-19-*`、`2026-10-20-*`、`2026-10-21-*`、`2026-10-22-*` |
| 部署门禁 | `docs/process-archive/reviews/2026-10-21-pre-deploy-gate-report.md`、`docs/runbooks/deployment-v1.md` |
| 质量评测 | `dispatch-output/quality-eval-20261021/report.md` 与 `2026-10-22-会话工作报告.md` |
| W08 质量评测专报 | `docs/process-archive/reviews/2026-10-23-w08-quality-eval-summary.md`（台账 `dispatch-output/w08-20261022/setup-log.md`） |
| 审核记录 | `docs/process-archive/reviews/2026-10-22-quality-eval-work-report-audit.md` |
| Q1 支持审查器稳定性 | `docs/process-archive/reviews/2026-10-23-round67-q1-support-review-stability.md`（§8–§13） |
| 账号边界第 4 轮 | `docs/process-archive/reviews/account-boundaries-readonly-review-round4.md`、`docs/process-archive/reviews/account-boundaries-round4-fix-receipt.md` |
