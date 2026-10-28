# 聊天取消修复与候选收尾汇报

日期：2026-10-05。**本轮取消/会话归属修复已得到限定范围的真实验收；整个本地候选阶段尚未完成，未上线。** Windows后端退出故障未解决，整次验收控制器也未正常完成。

最新C3诊断：已取得两次控制崩溃与两次async SDK收尾后正常退出的有界对照，支持进入应用级生命周期修复；**目前只是实验干预，还没有改产品或改变C/D整体FAIL**。正文原round-03结果保留，当前新增工作见末尾C3记录。

2026-10-06收尾：诊断工具清理错误分支P2已修正，主控fresh13项与独立二审通过，诊断子任务完成。产品退出修复与综合验收仍未完成。

## 当前交付在哪里

独立候选ROOT：

`C:/Users/33393/Desktop/fazhi-cancel-repair-20261005-13137719e0d043d5ba17a9efc33d30ce`

产品在 `ROOT/source/backend`、`ROOT/source/frontend`；**不是Git仓库，未合入主仓，不可直接在这里提交**。固定基线是上一轮 `C:/Users/33393/Desktop/fazhi-cancel-backend-20261005-3d68d1547a1c47839266df465a7b6629/source`。本轮6个变化：

- backend/main.py、rag_chain.py、tests/test_stream_cancellation.py。
- frontend/lib/api.ts、lib/hooks/useChatStream.ts、tests/chat-conversation-cancel.test.ts。

结构最终版清单：`ROOT/evidence/backend-input-manifest-structural.json`、`frontend-input-manifest-structural.json`（289+73=362文件）；diff：`ROOT/reports/combined-review-structural-final.patch`。旧清单/round-01/02保留，代表结构修订前版；不能用旧版本PASS报告证明当前源码。

主仓仍为master、HEAD `902e2d161e67100ed6d267a08c393538a0abe109`。原有6个跟踪修改不动，暂存区不动；本轮主仓只新增本汇报、更新本轮新执行书，没有提交、合并、推送、部署、安装，真实库/共享venv/原模型缓存不动。

## 修了什么，为什么这样修

1. 普通SSE显式拥有body与内部生成器；真实Starlette blocked-send断开也能收尾，状态首帧纳入普通stream的try。模型SDK响应由每请求局部owner登记/关闭，不改共享池，取消不当模型故障重试。
2. 新页面首轮先用既有create API确认ID，同视图共享尚在进行的创建；停止回答不丢创建结果，换视图/卸载令旧结果失效。原生180秒有界超时、正整数ID校验、失败明确重试；不加新服务/schema。
3. 单元23曾通过但真实连接仍不关闭。对照复现Sequence路径“closed=true、连接继续”，SDK直接与同任务公开模型流均可及时EOF；因此缩减多余Sequence层，保留公开model.astream/config/模型回调、每块public parser.invoke/config。先加真实HTTP RED，再改产品，最终28项GREEN、主控独立重跑通过。未升级依赖、未调用私有模型生成接口、未关闭共享pool来凑通过。

这次brainstorming/vet-plan取舍是减少执行边界，不叠加取消系统。**兼容边界：**不保持Sequence聚合trace树/次数；parser改为逐片事件。异步handler/manager完成已验证，但同步invoke把其放进线程事件循环，不保证原循环绑定回调兼容/慢回调性能；实际ChatOpenAI async config追踪未完整验收。`async_client`是当前版可注入但标为private的接缝，升级须重验。具体哪个底层close await被打断尚未逐层证明，不宣称普遍库根因。

## 本轮证据与裁定

| 项目 | 本轮结果 | 证据/边界 |
| --- | --- | --- |
| 后端取消机制 | PASS：28项、主控fresh exit0 | `ROOT/evidence/task-A-structural-coordinator-green.log/json`；不是全后端套件 |
| 前端机制与构建 | PASS：19定向、完整83/9文件、Next build | `ROOT/evidence/round-03/frontend-tests.log`、`build.log`；没有把hook mock称React完整render |
| 实际上游取消 | PASS：正式6/6 | 直连2＋UI已有/新会话首字前/部分4；首字前0片段、部分1；本机断开约0.001～0.073秒，不保证云计费停止 |
| 会话归属/存储 | PASS | UI四例取消/重问同ID1、1、4、5；API/SQLite5会话32消息配对、计数/值一致、integrity ok |
| 取消持久化/重开 | PASS，限定原契约 | 8占位coverage unknown，半截不落库；新partial重开显示占位+正常替身回答，输入可用、console0 |
| 本地BGE/公开副本 | PASS | revision固定，CPU768维，8fresh样本cos≥0.99999；1528法律块/QA0/gold管理员API核对 |
| 后端真正退出 | **FAIL** | read子进程3221225477/0xC0000005，proactor GC堆栈；shutdown complete文字不证明exit0 |
| 整次控制器 | **FAIL** | 20分钟UI watchdog后exit1；证据此前取得但不能改称正常run |
| 独立源码复核 | PASS，0新增可行动问题 | `ROOT/reports/task-A-structural-review.md`、`task-B-review.md`、`combined-review-structural-final.md`；不是整个发布认证 |

最终只读校验 `ROOT/verify_final.py round-03` 实际exit1：`cancel_flow_and_storage_pass=true`，`bounded_integration_pass=false`。原始证据主索引：`ROOT/evidence/round-03/final-verification.json`、`final-persistence.json`、`stub-requests.jsonl`、`cleanup.json`、`controller-result.json`、`read.log`。细节见 `ROOT/reports/task-C-D-report.md`。

### 不能藏掉的验收瑕疵

- 预备UI首字前被跨工具延迟拖成部分输出，保留排除；正式同次操作重新取得0片段。
- reask辅助函数一次错用旧case，写入因EEXIST未覆盖原证据；保留误操作消息，显式参数修正，受影响正式案例用唯一问题重做，SQL判据不放宽。
- 已有会话14消息触发既有摘要，fixture未识别摘要system，历史标签被归为取消answer，多跑72片段让收尾约57秒。该request未被停止且不在六正式ID中；源码/时序支持摘要归类解释，但没保存body逐字段证据。稍后输入恢复另存。不能据此称本轮解决了产品摘要收尾延迟。
- 以上额外消息解释32条与8占位，不能虚报仅24条/6占位。分类依据见 `ROOT/reports/round-03-fixture-classification.md`。

## 安全收尾和保护

本轮owned7子进程均停止，3041/8041/8791端口释放，本轮临时标签页已关闭；用户已有3021页面未动。frontend exit1为受控terminate，backend native失败单列。失败DB/日志/截图全部留存，无删除。

保护与凭据复扫最终结果由本汇报下方收尾记录更新：只检查已批准的当前9项精确值及5种已知形状，scanner自身读取值、仅输出字段/计数/文件SHA，不输出密钥值/指纹/片段、不拿真实凭据请求。形状正控属于scanner代码，须显式归类；不能把选定文件扫描说成全盘/历史无泄漏证明。

已知Vite CJS、Next standalone启动提示、Node util._extend、Chroma/Posthog capture参数告警保留。audit拒绝的devnull/platform与能力探测是受阻的工具/依赖动作，不是成功外写；未放宽网络/.env/ROOT写边界。

## 后续执行顺序与暂停线

1. **先C退出归因，不合入/发布。** 按 `ROOT/reports/task-C-D-report.md` 的同负载、无UI两个独占子进程控制实验，区分自身应用shutdown关闭SDK客户端的效果；27个open client只是线索。若证明必要，再设计registry/lifespan最小资源所有权修复并先RED后GREEN。不是每请求关闭共享pool；不force-exit/隐藏异常/盲目升级或改loop。对照无区分就保留FAIL并缩小SDK/BGE/native子集。
2. **先修验收工具再重跑综合门。** fixture明确识别摘要system，禁止把历史词当当前问题；浏览器helper只传显式case/tab参数；先证明控制器/状态判定/分类回归，再运行新目录的正式矩阵，所有旧失败保留。定时器不能只加长掩盖等待，finish marker应在页面/SQL证据完备后及时发出。
3. **再处理旧取消边界。** 排队llm_guard.acquire的线程取消可能占走并发位；`_pre`到body未启动的持久化未验证。本轮全部到过上游，不能说涵盖这两项。各自先定向RED，只有必要最小修复，不扩大成后台任务/持久化平台。
4. **待退出与整次门正常，再做候选整合/全门禁。** 新Git候选中核对六文件与主仓重叠，保留原六修改；不直接覆盖主仓或宣称这些独立目录文件已提交。本轮未复扫全部依赖风险、全部后端/法律质量门、真实Agent/text/light/云rerank。
5. **推送、真实库、部署仍独立阶段。** 当前不是上线验收，未选择服务器不能部署；本轮未执行任何发布动作。

### 收尾记录

- 保护复核实际exit0：`ROOT/evidence/protection-after.json`、交付前fresh `protection-delivery.json` 的12项均true；HEAD/refs/空暂存区、主仓原六跟踪修改、受保护41项、原语料38项、配置/公开seed/原模型及先前依赖文件均未变化。这不改变C退出FAIL和D综合FAIL。
- 凭据扫描两次实际exit0：`ROOT/final-scan.json` 为收尾前225文件；更新后 `ROOT/final-delivery-scan.json` 为226文件。当前9项精确值均0命中，无缺字段，9项精确匹配正控与5种形状正控通过；唯一形状命中是scanner自身private-key字面量正控，已归类，无未归类形状命中。增加1文件来自fresh保护记录，不是少扫旧证据；最终文档指纹以交付前唯一命名 `ROOT/final-confirmation-scan.json` 为准。旧扫描不覆盖，不把选定文件/当前输入结果当全历史安全证明。
- 独立组合源码及事实一致性复核已交付：`ROOT/reports/combined-review-structural-final.md`，新增矛盾/过早完成声明0；复核者没冒充重跑服务。其附录在复核时将保护/扫描记为待验证，本节以上后续真实记录更新该状态，未改写原审查时间线。
- 当前交付结论仍是**修复子门PASS、退出与综合门FAIL、阶段未完成**。本轮候选未合入、提交或发布；后续按上列顺序继续，所有旧失败与误操作证据保留。

## C3：Windows退出故障有界对照追加

本次不重做A/B，不改冻结362产品源文件，只新增独立诊断工具和新目录。两个新会话、四聊天（两取消+各自同ID正常重问）、固定公开1528块/QA0/CPU BGE revision/Proactor/合成零配额路由保持一致。stop前HTTP与Uvicorn请求task均0、并发slots4；没有UI或外部模型调用。

| 有效leg | 原生backend / shim退出 | 唯一变量与结果 |
| --- | --- | --- |
| control-03 | 3221225477 / 同码 | 没有SDK额外close；proactor GC访问违规 |
| intervention-01 | 0 / 0 | 真实lifespan结束后、loop内关闭registry可达async SDK |
| control-04 | 3221225477 / 同码 | 最终helper只读control，再次同位置访问违规 |
| intervention-02 | 0 / 0 | 同最终helper关闭同范围async SDK，再次自然正常退出 |

目录前缀均为 `ROOT/evidence/shutdown-`，实际exit见各 `result.json` / `cleanup.json` / `backend.log`。四个controller0只表示取证完整。01/02干预均unique27/attempt27/success27/errors[]，async open27→0、sync仍27；不在单请求取消时关闭共享池，不改loop/依赖，不force-GC/os._exit或隐藏异常。全部16个已保存进程身份在各自leg结束时自然退出，8041/8791空；不是说同一时刻有16个不同活进程，用户3021未动。

全部leg四聊天/两会话/八消息、两取消peer EOF及同ID重问/占位/integrity通过。最终control04/intervention02 source与工具指纹、完整SQL消息数组深等价，各leg前后指纹未变。主控直接读取原始证据，另独立重跑新增工具10项全部通过；工具TDD RED/GREEN和native结果分别记账，不加总成全后端测试。control01/02因Windows启动白名单错误在产品启动前失败，无child；失败目录保留，不计产品复现。原干预01的采样字段 `client_mutation` 只描述observer自身但有文案歧义，已披露；最终配对改为 `observation_mutation`，旧记录不改写。

主控交叉核对中一次把manifest的backend/frontend相对路径接到ROOT而不是ROOT/source，导致缺文件；那次末尾0 mismatch无效，未作为证据。随后启用遇错立即停止并修正前缀，实际逐文件hash362项全部相同。此为只读核对工具错误，无文件写入或产品失败，未原样重复命令。

**当前结论：固定fixture下的应用SDK退出收尾缺口已有正反向定位证据，可以设计最小产品修复；实验干预不是产品修复，不证明底层CPython根因、统计稳定性或临时variant/热重载旧client都受覆盖。** C3产品回归、无额外实验close的真实退出验收和D综合重跑仍未完成。本次没有修改产品、提交、合并、推送、部署、安装，不能用这四个结果把原C/D FAIL改成PASS。

下一步先核对registry的创建、variant与reload所有权，在**新**独立源码副本实现最小loop内收尾，避免私有字段散落或无限保留旧client列表；先产品RED/GREEN、错误/唯一对象/取消与共享客户端边界复核，再以真实lifespan、没有包装器额外close的固定负载取得native0。工具摘要识别/显式case/及时finish修复和新综合矩阵仍随后执行，旧失败不覆盖。

完整诊断报告：`ROOT/reports/task-C-shutdown-diagnostic-report.md`；全量新工具diff/独立Spec-Quality审查：`task-C-shutdown-diagnostic-review.patch` / `task-C-shutdown-diagnostic-review.md`（审查收尾待写）；主控fresh测试与配对事实：`ROOT/evidence/shutdown-coordinator-fresh-tests.log` / `shutdown-coordinator-paired-verification.json`。本次12项保护、当前9项选定文件凭据复扫等待审查/文档稳定后执行新标签；上一轮226文件扫描只证明当时manifest，不能覆盖新增C3内容。

独立审查另发现P2工具安全缺口：cleanup强停/等待一个saved handle失败会放弃余下owned，rows再次报错可能跳过result与句柄close。四leg均自然退出、不走该分支，退出对照仍有效，但工具质量暂不能全PASS。已交原实施者只补该错误处理和失败控制；无新服务/重模型实验。修后需单列新版工具hash及独立复核，不把旧四leg伪记为新版本的native回归。

### C3最终收尾记录（2026-10-06）

以上待办与首版REQUEST_CHANGES是审查时间线；当前状态由本节更新。原P2已局部修正：每个saved handle的终止/等待/查询错误独立保存并继续其余，未知退出不冒充已停；finally逐句柄/日志尝试关闭，普通关闭错误可见并阻止complete。资源关闭尝试先于结果保存，磁盘保存失败仍显式报错，不增加结果保存框架。

- 工具RED：13项、1failure+4errors，正确暴露原cleanup错误分支；GREEN同13项全通过，主控fresh13/13实际exit0。13是测试方法数（其中有故障子例），不是全后端套件。`ROOT/evidence/shutdown-coordinator-fresh-tests-v2.log`。
- 二审：`ROOT/reports/task-C-shutdown-diagnostic-review-v2.md` 的Spec与Quality均PASS，原P2关闭、0新增可行动问题；未冒称审查者重跑测试/native。首版review及已跑paired版本归档均保持原样。当前安全工具 `shutdown_diagnostic.py` SHA256为 `e8f4d89fa98da23341322f7d58cfa01192c55970e41fb31e8f971078ef8b8ec6`；**该版没有重跑服务/模型/native**，旧四leg仍按原版本裁定。
- 最终只读核验：362产品源0变化，旧工具归档匹配paired冻结，8041/8791空；记录 `ROOT/evidence/shutdown-coordinator-final-sources-and-ports.json`。用户3021未操作。
- 12项保护交付前fresh全true，actual exit0：`ROOT/evidence/protection-C3-delivery.json`；原HEAD/refs/空暂存区、六处跟踪修改、41项受保护文件/38项原语料、真实配置、公开seed、模型和旧依赖文件均未变化。
- 当前凭据复扫 actual exit0：`ROOT/C3-closeout-scan.json`，395选定文件、当前9项精确值均0命中、无缺字段，9值/5形状正控均通过。唯一形状命中为scanner自身private-key正控，已归类，无未归类命中。文档回填后的最终指纹另以唯一命名 `ROOT/C3-final-confirmation-scan.json` 确认；旧226文件扫描只保留历史意义，不覆盖新C3文件。当前扫描仍不证明未知/编码/历史密钥或全盘安全。

**当前里程碑是“C3有界诊断与诊断工具安全复核完成”，不是产品退出修复或阶段完成。** 下一最小产品方向是：在新独立源码副本核对variant/reload的cfg差异，优先测试复用本entry已有SDK客户端是否保持请求/思考参数语义，避免为应用退出维护无限旧client列表；让registry承担唯一client收尾、main真实lifespan在loop关闭前调用。先定向产品RED/GREEN与配置/共享客户端/错误边界复核，再在无实验额外close的真实进程上验证native0，随后修D工具并重跑综合矩阵。尚未证明的兼容性不得直接承诺；不扩大路由、数据schema或客户端管理平台。

本轮没有产品源码修改、提交、合并、推送、部署或安装，真实库和共享venv不动。本执行书C3总项仍未勾选，C/D整体FAIL仍保留。
