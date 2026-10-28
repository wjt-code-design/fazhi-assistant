# 主仓本地整合执行计划

**当前状态（2026-10-08）：旧失败保留；获批准 A 修补的 33 项定向、新非 slow 全量（1852 通过、10 跳过）及最终 round-11/control-13 总门均通过，双轴只读复核无剩余阻断。扫描器归档正控分类已用 bytes/SHA 独立负控复核；本文件为提交前封口快照，最终扫描/实际本地提交见 `C:/Users/33393/Desktop/fazhi-main-integration-20261007/evidence/delivery-closure.json`，缺该记录不得当作已提交。**

> **For agentic workers:** 使用已确认的范围逐项执行；本轮由当前会话负责整合，独立代码复核按仓库双轴要求开展。步骤用复选框跟踪，不擅自扩展到发布或部署。

**Goal:** 将独立候选中必要的产品修补整合进主仓，完成隔离回归和自审后本地提交，同时保留原有未提交修改。

**Architecture:** 不新增业务架构。复用已有请求级流资源归属、取消响应与 SDK 生命周期修补。以主仓 HEAD 为基线逐段应用差异；准备提交的版本和保留用户修改的工作区分别验证。

**Tech Stack:** Windows / PowerShell、Python 3.11、FastAPI、LangChain / OpenAI SDK、SQLite / Chroma、Next.js / React / Vitest。

## 已确认的范围与红线

- 用户通过四次 A 选择确认：推进主仓本地整合；验收通过后允许本地提交；原有六处修改不提交；执行可安全运行的全部非慢后端测试、前端测试/类型/构建和取消/摘要/退出集成。
- 不 push，不写真实库，不部署，不调用真实模型，不全面升级依赖，不修改共享 venv。
- 主仓：`C:/Users/33393/Desktop/ai-legal-helper`；起点 HEAD：`902e2d161e67100ed6d267a08c393538a0abe109`，分支 `master`，起点暂存区为空。
- 只读候选：`C:/Users/33393/Desktop/fazhi-closeout-auditfix-20261007`。不改它的源码、工具、报告及历史证据。
- 本轮隔离根：`C:/Users/33393/Desktop/fazhi-main-integration-20261007`。证据、备份、模型种子和运行数据均在此根；现有服务及端口 3021 不动。
- 共享解释器只读：`C:/Users/33393/Desktop/fazhi-next-local-20261004-356fb810b3144d158e5dd18b9e276499/joint/venv/Scripts/python.exe`。
- 禁止整树 `git add -A`。大量既有未跟踪产物不属于本轮提交。
- 同一失败命令先分析，完全相同的命令最多重试一次；重命令失败不自动循环重跑。同一 bug 连修三次仍失败即停下重新审视。

## 任务 1：保护与逐项审查

- [x] 运行 `powershell -NoProfile -File C:/Users/33393/Desktop/fazhi-main-integration-20261007/tools/protect-main.ps1 start`，验证六处未提交文件的逐字节备份。
- [x] 比较候选 369 文件与主仓：92 处字节差异中，70 处仅换行/编码差异不纳入；22 处内容差异/新增继续审查，不能直接整树覆盖。
- [x] 排除仅由现有用户修改造成的三个文件差异：`frontend/app/admin/sections/KnowledgeSection.tsx`、`frontend/app/admin/sections/UploadSection.tsx`、`frontend/app/globals.css`。本轮不改、不提交。
- [x] 原有计划书 `docs/process-archive/superpowers/plans/2026-09-29-local-candidate-decision-and-release-prep.md` 保持原样、不提交。
- [x] 另外两个重叠文件 `frontend/app/chat/page.tsx`、`frontend/components/chat/InputBar.tsx` 保留图片能力校验、移动布局等原有修改，只追加停止生成接线。
- [x] 将日期校验、PDF 错误处理、取消/占位、SDK 收尾和已验证依赖声明分别映射到回归测试，不把稳定性验收当作法律质量证明。

## 任务 2：最小整合与提交面

既有候选修补文件（以审查结果决定实际纳入，不复制行尾噪音）：

- 后端修改：`backend/knowledge_service.py`、`backend/llm_guard.py`、`backend/llm_registry.py`、`backend/main.py`、`backend/rag_chain.py`、`backend/requirements.txt`、`backend/schemas.py`。
- 后端新增测试：`backend/tests/test_cancel_boundaries.py`、`backend/tests/test_knowledge_calendar_dates.py`、`backend/tests/test_llm_lifecycle.py`、`backend/tests/test_pdf_upload.py`、`backend/tests/test_stream_cancellation.py`、`backend/tests/test_upload_rate_limit.py`。
- 前端修改：`frontend/app/chat/page.tsx`、`frontend/components/chat/InputBar.tsx`、`frontend/lib/api.ts`、`frontend/lib/hooks/useChatStream.ts`。
- 前端新增测试：`frontend/tests/chat-cancel.test.ts`、`frontend/tests/chat-conversation-cancel.test.ts`。

整合期间的必要追加：`backend/settings.py`、`backend/tests/test_settings_repr_masking.py` 修复嵌套模型配置在 repr 中暴露凭据；`backend/tests/_sse_harness.py`、`backend/tests/test_tiering.py`、`backend/tests/test_fast_path_law_version_gate.py` 仅适配异步调用，不改变法律判据。合计 24 个产品/测试路径，另有本轮文档。

- [x] 先把相应测试放到 HEAD 的隔离基线，定向复现有意义的失败；原候选已有红/绿证据可引用，但不能冒充本轮重跑。
- [x] 使用 `apply_patch` 在主仓逐项整合必要修改。已有修补不重新设计、不顺手格式化其他文件。
- [x] 仅暂存本轮清单；两个重叠文件以仅包含本轮差异的补丁暂存，保留原有修改未暂存。
- [x] 导出暂存版本到本轮 `source`，该树不含用户原有六处修改；另建 `working-view` 保存合并后前端视图用于验证，禁止从中提交原有修改。
- [x] 公开测试依赖本来已被主仓跟踪，不重复作为“新增产品功能”提交；不复制隐藏题集、真实配置或用户数据库。

## 任务 3：隔离验收

- [x] 复用候选的环境白名单及 Python / Node 守卫，将数据库、配额、向量库、临时目录、日志和缓存重定向到本轮根。只用公开种子及固定离线 BGE。
- [x] 为全部非慢后端用例记录收集列表、实际执行、JUnit 计数与真实退出码：1819 通过、10 跳过、18 slow 排除，覆盖率 85.82%；1829 项选中用例均有唯一终态。跳过不计作通过。
- [x] 网络、真实配置、外部写入或未授权子进程被守卫拦截时，保留原始失败并分类；只增加逐条批准 CLI 的守卫内执行入口及负控，不开放任意子进程。
- [x] 运行 `ruff check`、`ruff format --check`、`mypy`；退出码均为 0，mypy 检查 74 文件，不扩大为全仓重构。
- [x] 准备提交的前端及保留原有修改的工作视图各为 83 测试通过、TypeScript/构建退出 0。构建存在 Windows standalone 复制 EPERM 警告，不证明部署包完整。
- [x] 冻结新源码/工具/公开种子后，以新标签运行两项 API + 四项真实浏览器取消、同轮实际摘要压缩、API/SQLite 持久化一致性和原生自然退出控制。round-10/control-12 总门实际退出 0；不沿用旧轮通过状态。
- [x] 限定结论：替身模型验证接线和资源收尾，不证明真实模型质量或生产稳定性；round-09 总门禁失败，未豁免存储检查。

## 任务 4：双轴复核、自审与本地提交

- [x] 按 `docs/code-review-standard.md` 分别检查规格与工程质量，由只读审阅者基于本轮原始差异/证据复核；正式集成新发现两项存储阻断，后续修复须重新复核。
- [ ] 确认暂存区仅包含本轮批准的源文件、测试和本轮文档；扫描提交内容中的凭据，扫描过程不输出真实值或片段。
- [x] 验证准备提交的源码与实际测试输入一致；380 index 导出文件与冻结源码逐字节相同，两个重叠文件原有变更内容/顺序不变，四个非重叠文件及保护项检查通过。共享环境仅核对 distribution 列表，不作整环境字节证明。
- [ ] 所有必需门禁通过且无阻断项后，本地 `git commit`，不 push。若门禁未通过，不提交，并如实报告阻塞。
- [x] 写本轮进度报告 `C:/Users/33393/Desktop/ai-legal-helper/docs/work-report-20261008-main-local-integration.md`，区分通过、失败、未验证和明确排除项；已自审，未写成完成报告。

## 计划自审

- 最小方案优于整树复制：不带入 70 处行尾噪音，不回退原有前端修改，不引入新框架。
- 主要风险：共享计数取消泄漏、响应未启动占位缺失、关闭失败、测试进程间全局状态污染、用户修改混入暂存区、真实凭据/数据被测试读取。
- 对应证据：取消容量/双气泡/失败占位/SDK 生命周期回归、独立进程测试集合核对、暂存树与工作视图分别验收、保护清单与提交内容扫描。
- 完成标准不是“用例收集成功”：必须有新鲜实际执行和退出码，且本轮批准的门禁闭合。无法安全执行的部分明确保留，不擅自豁免。

## 执行中复核发现（2026-10-07 的历史状态，不是当前结论）

- HEAD 的取消容量泄漏已定向复现：`evidence/red-capacity-01`，1 项有意义失败。
- 独立双轴审查发现新增测试不兼容常规 conftest 入口；已保留 2 项红证据并在隔离副本修正，`green-standard-pytest-01` 为 2 项实际通过。
- 独立规格审查发现轻量整答与空流兜底仍走屏蔽取消的同步线程池。异步化后，既有路由/版本测试实际 64 通过、2 跳过；不改法律判据，仅适配三个测试夹具的异步调用。
- 新增真实 SDK＋实际 ASGI 响应测试曾显示非流式 SDK 读体取消未断上游；`green-cancel-mechanisms-02` 的 34 通过、2 失败保留。之后通过请求级任务托管与单次取消后等待终态修复，`green-cancel-mechanisms-04` 为 42 通过，不关闭共享客户端制造通过。
- 修补从 `review-source` 验证后已整合及选择性暂存；旧冻结候选不改，尚未本地提交。

## 当前阻断与待确认修订（2026-10-08）

- round-08 缺少 BGE 公共参考输入而失败，证据和当时 53 份工具原样保留。补齐并绑定来源哈希后，新输入负控为 123 测试及 3 子测试通过。
- 正式 round-09/control-11 完成，379 源文件、53 工具、18 种子及 BGE 参考输入绑定通过；六项上游取消、四项浏览器交互、实际摘要和 SDK 关闭/自然退出通过。
- **总验收失败**：会话 7 的 `message_count=3`，实际消息 4；会话 5/6/7 有连续两条 user、后两条 assistant，严格配对失败。依据 `C:/Users/33393/Desktop/fazhi-main-integration-20261007/evidence/round-09/final-verification.json`，不能提交。
- 两路复核确认：`_post`/`_post_placeholder` 的 SQL 自增后旧 ORM 计数赋值可能覆盖并发更新；stream finally 未等待占位入库，前端快速重问可先提交第二 user。
- 还需用定向测试锁定：答案 commit 后沉淀/摘要异常不能误触发第二条 assistant 占位。该项为代码发现，尚未完成本轮实测。

修订 A（用户已确认）：仅在后端为同会话建立有界的串行收尾边界，下一轮在 bootstrap 写用户消息之前等待上轮持久化终态；取消占位由现有响应边界 shield-await，落库后才放行；删除两处旧计数写回并刷新必要的 ORM 读值；区分已 commit 与附带后处理失败。不同会话不互相阻塞，排队取消不得落用户消息。只保证现有单 worker，不引入分布式锁、数据库迁移、新取消 API 或新依赖。

备选：预留助手消息行可固定顺序，但会改变历史/上下文和 Agent 路径，影响面更大；仅修计数并登记乱序限制虽改动小，但不能满足当前配对门禁，不能据此宣称本阶段完成。

- [x] 用户回复 A，确认同会话等待语义及修补边界；按下列步骤实施，不扩展到多 worker。
- [x] 用事件屏障确定性复现快速重问、双 Session 交错计数、commit 后后处理异常；不得依赖延长 sleep 或排序快照制造通过。正确原因红与 33 项新绿的标签见工作报告。
- [x] 最小修补后定向回归、双轴复核、重新导出与冻结；以新轮次重复正式验收，round-10/control-12 通过，不改写 round-09 失败。
- [ ] 通过后执行提交内容扫描、原有残留差异核对、保护清单检查，再本地提交；仍不 push、不部署。

### A 修补实施步骤与验收尺子

产品修补涉及 `C:/Users/33393/Desktop/ai-legal-helper/backend/main.py`、新增 `C:/Users/33393/Desktop/ai-legal-helper/backend/tests/test_chat_turn_persistence.py`，以及本轮隔离工具的目标/新轮次标记。已有 `backend/tests/test_cancel_boundaries.py` 夹具仅增加可选图片校验回调，以便新回归接入真实校验，原调用默认行为不变。原有六处修改不再改动。

1. 以当前 main.py 的真实函数配合双 Session、临时 SQLite 重现两条 assistant 写入路径的旧计数覆盖；事件屏障阻塞首轮补偿，再同时调用真实路由/响应和第二轮 bootstrap，要求第二条 user 尚未入库。另模拟已 commit 后压缩异常，要求仍只有一个 assistant。这些测试必须先红。
2. 在现有响应边界增加请求级同会话所有权。使用标准库 asyncio.Lock，以认证用户及真实会话编号为键、只保留被活跃请求引用的锁；从 bootstrap 写用户消息前持有到响应清理后。普通请求先解析本人会话，缺省/失效/非本人编号沿用既有新建语义，复用会话 CRUD；不得等检索或响应返回后才登记，因为列表 API 已能公开新编号。Agent resume 不自动重建。已有 Agent controller 的线程 RLock 不可直接跨 await 复用。
3. 等待期限采用前端既有 180 秒无帧预算；等待期间检查断开，超时 503、断开 499，均不得进入 bootstrap。直接 await acquire 配合 asyncio.timeout，不用 wait_for 子任务交接。回归必须覆盖锁授予与 task.cancel 同拍，取消不得被吞；不同会话可并行；所有异常/取消出口归还已取得的锁。
4. 将 entered-stream 的后台补偿改为 shield-await；答案和占位 commit 后在请求私有 pre 中记录持久化完成，任何后处理错误不得重复补偿。删除两条 ORM 旧计数赋值，保留 SQL 原子自增；生产 Session commit 后自动过期的读值保持摘要阈值正确。
5. 定向测试增加正常完成/路由异常/等待取消/超时/不同会话并行/新建后立即重问及锁释放；使用事件建立交错，不拉长睡眠制造通过。运行后端全部非慢用例、静态检查，前端沿用未改变输入的已执行结果并在正式轮中再次检查。
6. 留存 round-09 实际 379 源/53 工具输入和失败报告，再重新导出批准的暂存树；新轮次 round-10/control-12 冻结后执行两 API、四浏览器、实际摘要和自然退出。最终计数/严格配对/无半答/不重复占位/上游 EOF/容量归还必须全部通过。
7. 无阻断后扫描提交面、核对保护边界、双轴复核及自审，再本地提交。完成报告更新后，根据实际剩余项写下一阶段计划；后续计划本身不授权 push、真实库操作或部署。

### 用户暂停断点（2026-10-08）

用户要求“找时机暂停”，已在当前隔离测试自然结束后暂停；不再开始新修改、全量、提交、push 或部署。最新接续顺序和证据解释记录于 `C:/Users/33393/Desktop/ai-legal-helper/docs/work-report-20261008-main-local-integration.md` 的“暂停断点”。A 修补未验收通过，以上未完成勾选不变。

剩余阻断：新会话先 commit 导致历史查询拒绝后残留空行；坏图片拒绝回归的测试夹具接线尚需修正；解析编号与获锁之间并发删除导致换编号的边界尚未复现/裁定；bootstrap 用户消息 commit 后、response 前检索异常的终态补偿尚需验证。不得将旧全量结果、测试名称 green 或局部 18 通过替代本阶段总门禁。

私有工具标记已更新为 round-10/control-12，但正式轮未启动、当前 final 清单仍是 round-09。恢复后先闭合上列问题，再重新导出/冻结并执行；遇到需要改变删除路由/API 语义的扩围先 grilling。保留原有六处修改及所有旧失败证据，禁止整树暂存。

### 恢复检查点（2026-10-08）

用户回复“继续”后恢复。拒绝输入问题已有正确原因的红证据 `red-rejected-input-02`（18 通过、4 目标断言失败），复用现有权限/图片校验并前置到新会话创建前后，`green-rejected-input-01` 定向 22 项通过、退出 0。该结果不代替全量或正式验收；旧暂停记录保留为历史，拒绝输入及夹具阻断已闭合。

仍需确认并发删除语义，推荐让删除参与同会话串行边界，删除先完成时已排队聊天返回 404、不静默重建。该变更尚未实施，不把泛称“继续”当作删除 API 语义变更确认。用户消息 commit 后、response 前检索异常补偿仍待测试/修补。最新证据与待选范围详见上述工作报告“恢复进展”。

### 删除边界 A（用户已确认）

用户回复 A，明确批准修改同会话删除与已排队聊天的语义。复用现有门闩：DELETE 等当前轮持久化收尾；聊天获取门闩后重核会话仍存在、属于本人且仍是解析时那一会话。排队期间已删除则 404，不进入 bootstrap；请求初始缺省/失效/非本人编号仍沿用旧的新建行为。使用既有 created_at 区分数据库复用编号，不新增字段或状态机。仅保证当前单 worker，不扩大到外部直写数据库或多进程。

- [x] 先用真实 SQLite、真实删除函数和事件屏障复现删除抢先及排队静默重建；另覆盖删除后编号被复用的交错。
- [x] 最小修补后定向、不同会话/认证边界、等待断开和异常释放回归；已处理已记录的检索异常收尾。`green-turn-final-01` 为 33 项，新 full-04 为 1852 通过/10 跳过/18 slow 排除；两轴无已确认阻断，不等于正式总门禁通过。
- [ ] 双轴复核、全量和正式新轮验收通过后，按原提交门禁本地提交；不 push、不部署。

### 技术验收后的接续

正式总门已通过，剩余提交门与实际 commit 只查上述 delivery-closure；本文件未勾的提交前条目不用于启动重复验收或替代该记录。新下一阶段执行书为 `C:/Users/33393/Desktop/ai-legal-helper/docs/process-archive/superpowers/plans/2026-10-08-release-readiness-preflight-plan.md`，仅含只读预检和独立报告；不是升级、真实调用或发布授权。

最终轮为 round-11/control-13：round-10 后的扫描真实退出 1，九当前值零命中但未分类旧 scanner 正控。已保留旧 380 源/53 工具/6 报告及失败扫描；仅扩充冻结哈希匹配的已知正控，正确原因红和单独削弱 bytes/SHA 均能被测试捕获，新工具 125+3 通过。因工具变化而重新冻结并执行新正式轮，实际总门退出 0；产品源码与 full-04 完全相同。最终扫描仍必须成功，不能拿旧九值为零豁免新交付扫描。
