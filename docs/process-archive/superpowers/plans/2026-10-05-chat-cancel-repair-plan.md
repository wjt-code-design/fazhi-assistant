# 取消生成与会话归属修复执行书

> 执行日期：2026-10-05。用户已要求“规划后续任务并执行”。本书只关闭上一轮取消联调发现的问题，不代表整个发布阶段完成。

## 目标、架构与边界

**目标：** 页面主动停止后及时释放后端拥有的回答流；新对话首轮取消后重问不分裂会话；复验并如实裁定 Windows 关闭异常。

**架构：** 保留现有 React hook、SSE、FastAPI、LangChain 和 SQLite。后端优先使用标准库显式关闭自己拥有的异步生成器；前端复用现有 `POST /api/conversations`，不在两处同时创建同一页面的新会话。创建请求与回答请求分开：停止回答不让已发送的会话创建结果丢失，同一视图内立即重问等待同一次创建；换视图/卸载使旧结果失效。不得另建任务平台、数据库状态字段或取消服务。

**技术栈：** Python 3.11、contextlib/asyncio、FastAPI/Starlette、LangChain/OpenAI HTTP 客户端；TypeScript/React、Vitest、Next.js。使用已有依赖，无安装或下载。

### 全局约束

- 只改新的独立文件候选；不改主仓六个既有跟踪修改，不改上一轮冻结候选。主仓只新增执行书/汇报。
- 不合并、不提交、不推送、不部署，不写真实库或共享 venv，不把真实密钥交给模型或写入日志。沿用此前批准的本机凭据复扫：扫描器仅在自身进程内读取当前9项用于比对，只输出字段名/命中计数与扫描文件指纹，不输出值、密钥指纹或命中片段；不得拿这些凭据发请求。
- 定向联调只用已许可公开库的新副本、既有固定版本 BGE CPU 和回环 LLM 替身；禁外部模型/rerank/Agent。不把替身结果称为云端停止或计费保证。
- 保留取消后的失败占位持久化契约，半截内容只保留当前页面；不扩展保存半截、修改法律校验或错误降级策略。
- 所有失败证据保留；新实验使用新目录。相同失败命令分析后最多原样重试一次；同一 bug 三次修复仍失败则停止质疑设计。
- 先 RED 后 GREEN；完整验证后再写结论。仅单元通过不能代替上游断开、同会话归属和子进程真实退出证据。

## 输入与可执行环境

问题报告：`C:/Users/33393/Desktop/ai-legal-helper/docs/work-report-20261005-cancel-backend-integration.md`。

冻结基线：`C:/Users/33393/Desktop/fazhi-cancel-backend-20261005-3d68d1547a1c47839266df465a7b6629/source`，后端 288 文件、前端 72 文件。上一轮回环日志/SQLite/API/故障退出在同目录 `evidence/round-02`，只读。

本轮独立根目录（下称 ROOT）：

`C:/Users/33393/Desktop/fazhi-cancel-repair-20261005-13137719e0d043d5ba17a9efc33d30ce`

产品候选在 `ROOT/source/backend`、`ROOT/source/frontend`。ROOT 不含 Git 仓库，不可假装在其中提交。本轮辅助工具、日志、测试数据库和副本均只写 ROOT。

已有 Python：`C:/Users/33393/Desktop/fazhi-next-local-20261004-356fb810b3144d158e5dd18b9e276499/joint/venv/Scripts/python.exe`。Node：`C:/Program Files/nodejs/node.exe`。

后端单元测试必须绕开会加载模型/Chroma 的全局 conftest：新生命周期测试以 AST 提取真实函数，在无数据库、无模型环境运行。集成复验另用真实应用和隔离副本。前端复用复制的 node_modules，直接执行现有 Vitest/Next，不调用安装器。

## A：回答流资源所有权

允许修改 `source/backend/main.py`、`source/backend/rag_chain.py`，新增 `source/backend/tests/test_stream_cancellation.py`。有证据表明相邻资源控制模块是根因时，先在记录中说明并限制为必要最小修改。

- [x] A1 核对 `_stream_with_status_preframe → chat.stream → stream_with_retry → chain.astream`，普通与合同两处调用都要检查；记录每层谁创建/关闭资源。
- [x] A2 写失败测试：关闭外层后内层 finally 必须执行；取消等待首 token、部分输出后关闭不能重试/标记耗尽，并发位释放；正常结束、失败重试不退化。保留真实失败输出。
- [x] A3 标准库优先，显式关闭各层自己拥有的生成器/流。关闭发生在取消上下文时也必须完成必要收尾，不吞掉业务异常，不把取消当模型失败。
- [x] A4 运行定向测试，并审查新增 await/yield、finally、异常传播与真实 LangChain 资源关闭链。AST 测试不得手写生产函数的第二份实现。

A 独立复核补充：真实安装版 Starlette 在 `send()` 阻塞期间处理 http.disconnect，不显式关闭 body iterator；已有 20 项机制通过没有覆盖该边界。一次无网络生产 AST 诊断已确认 provider/并发位/占位均未收尾。将普通聊天最终响应改为小型 owned StreamingResponse，以已有 ClosingStream 托管整个 __call__，只用于普通聊天，不改 Agent 响应；补实际 Starlette blocked-send 断开 RED/GREEN 后再放行 A。该改动不增加 middleware 或任务系统。

定向命令（在 ROOT）：Python `-I -B -m pytest --noconftest source/backend/tests/test_stream_cancellation.py -q -p no:cacheprovider`。输出分别保留 RED/GREEN。AST 范围测试是机制证据，真实上游连接仍必须在 D 验证。

A 开工取证补充：当前安装的 RunnableSequence/BaseChatModel 还有嵌套关闭缺口。允许在 `make_chain` 的现有流边界增加最小、请求局部的资源托管：通过 SDK 的 `create` 取得并登记返回的流，关闭时显式 `response.close()`；复制模型时必须保留完整字段/回调/配置并使用独立字段映射，不改共享模型或连接池。实际测试发现 plain Pydantic copy 省略 exclude=True 字段，stdlib copy.copy 在该版本共享字段映射；最终用 `model.copy(update={**dict(model), 'async_client': request_client})` 满足两条不变量，失败证据保留。这里所用 `ChatOpenAI.async_client` 是暴露的可注入字段，但库文档标记为 private，**不是稳定公开接口承诺**；应记录当前版本兼容边界并设定向契约测试。需证明 SDK 流资源关闭、正常完成/重试和并发隔离；禁止直接调用私有 `_astream`、绕过公开模型管线。该补充不授权依赖升级或整体客户端重构。

A 真实联调修订（2026-10-05）：round-01/02 仍失败，禁止叠加猜测补丁。先质疑组合边界并以无应用/无DB的真实 HTTP 实验定位：SDK 直接关闭与主动读取取消均能产生 peer EOF；相同资源托管经过当前 RunnableSequence 后，首 token 前/部分输出取消均表现为 response.is_closed=true、上游未断开；仅实验自身客户端池关闭后才 EOF。单变量对照去掉 RunnableSequence、直接在当前任务迭代公开 `ChatOpenAI.astream` 并以公开 StrOutputParser 解析，两例均即时 EOF。由此允许**缩减** `_OwnedChain` 内的组合层，不调用私有模型接口，不改共享池，不改业务重试/并发。需先增加实际 SDK/ChatOpenAI+本机 HTTP 的 RED 回归，再最小实现，验证模型 config/回调及解析器配置；RunnableSequence 专属的链级追踪层不保证原样保留，应明确记录，而非声称所有追踪树完全兼容。旧冻结输入和失败日志只读保留，新版本清单与新联调目录另命名；未经重测不得用对照结果判定产品修复。

本修订的设计裁定（brainstorming / vet-plan）：

- 推荐：同一拥有者任务直接读取公开模型流，逐片以公开解析器产生原字符串结果；取消仍传播，只 shield 关闭。以真实 peer EOF、原文本/config/模型回调及并发隔离为验收。现有 plan 同时承载设计，不另造重复规格书；按用户“自主规划、推荐路径执行”的授权推进，不增加提交授权。
- 不选：每请求关闭共享 SDK pool，会伤及同池其他请求，违反资源边界；另外创建整套 per-request 客户端则增加池/生命周期/配置负担，目前没有必要。
- 不选：整体升级依赖或改事件循环，变更面更大且当前没有定位证据，不能用于掩盖 Windows 退出故障。
- 事实边界：已复现 Sequence 与 inline-public-model 的连接关闭差异；“具体哪个 HTTPcore awaited close 被打断”的微观原因尚未通过逐 await 取证证明。不得将这一假设写成已确定的库缺陷。
- 自审：不增功能/schema/后台任务，不减少安全/错误处理；组合 trace 变化已显式声明；DoD 仍是实际产品联调而不是实验变体通过。若本次缩减仍未过真实回归/联调，停止继续补丁并交付失败证据。

## B：新会话建立与取消竞态

允许修改 `source/frontend/lib/hooks/useChatStream.ts`，必要时 `lib/api.ts`，新增定向 hook 测试；保持页面布局与既有停止按钮不变，不重写 useConversations。

- [x] B1 用现有 hook 接口确认 newChat/selectConv 的 setter 与首次发送关系，测试真实 hook，不仅测试 transport。
- [x] B2 RED：新对话首轮尚未收到 meta 就取消，重问必须复用已创建 id；创建尚未返回时停止+重问只能创建一次；创建失败不能发送 null chat；新对话/选择历史/卸载不能被旧创建结果或旧流污染；重复发送仍被拦截。
- [x] B3 复用 `convApi.create()`，首轮生成前确认 id。同视图共享一次尚在进行的创建结果，不用跨页面全局缓存。同步 ref/state 必须覆盖已有 setter 调用；创建失败要允许明确重试，不能永久悬挂或静默回落 null。
- [x] B4 定向 GREEN＋完整前端套件与生产构建。正常既有会话、meta/Agent 事件处理和停止后迟到回调屏蔽不退化。

B 勾选仅指声明的定向 hook/transport 与构建机制门：hook runner 使用受控 React，未模拟完整 React rendering/StrictMode；Agent 事件为替身，不代表真实 Agent 取消验收。真实页面四种取消/重问仍属于 D。

定向命令（在 ROOT/source/frontend）：Node `node_modules/vitest/vitest.mjs run tests/chat-conversation-cancel.test.ts`；完整 `node_modules/vitest/vitest.mjs run`；生产构建 `node_modules/next/dist/bin/next build`。均在环境白名单与 Node 回环守卫下由本轮控制器运行，构建的代理目标为本轮后端。

## C：关闭异常归因，禁止猜测式“修复”

- [x] C1 先在 A/B 后复验一次关闭，记录后端真实退出码及脱敏 faulthandler 堆栈；控制器退出 0 不算后端退出 0。
- [x] C2 补守卫拒绝的事件、路径类别与调用栈，不记录参数值/密钥，不放宽保护。区分产品资源泄漏、实验工具和运行时依赖问题。
- [ ] C3 若仍崩溃，用少量、单变量实验缩小范围；根因已证明才写产品回归测试和最小修复。禁止强制退出、压掉异常、换事件循环或批量升级来凑通过。
- [x] C4 如证据不足，标记 FAILED/UNVERIFIED 并写清证据、影响、下一项实验，不称三项都完成，也不阻止已经安全得到的修复候选保留。

勾选表示验证与记录工作已做，不表示退出门通过。round-03 后端真实退出仍为 3221225477（0xC0000005），C 门 FAIL；C3 的单变量归因与产品修复尚未完成。27 个 open SDK client 只是线索，下一最小实验见 `ROOT/reports/task-C-D-report.md`，不得直接认定它们就是崩溃原因。

### C3 有界诊断追加（2026-10-05）

只新增诊断工具与独占 evidence/runtime；冻结362产品文件没有修改。无UI、真实main lifespan、固定离线BGE/公开副本、每leg两个新会话和四次聊天，stop前HTTP/task均0、slots4。有效结果：

| leg | 应用寿命末尾额外处理 | backend实际Python / shim退出 |
| --- | --- | --- |
| shutdown-control-03 | 只读观察，不关闭SDK | 均0xC0000005 |
| shutdown-intervention-01 | 仅关闭27个本应用registry可达async SDK | 均0 |
| shutdown-control-04 | 同最终helper，只读观察 | 均0xC0000005 |
| shutdown-intervention-02 | 同最终helper，仅关闭同范围async SDK | 均0 |

两次干预均在真实original lifespan结束、loop仍运行时进行；async open27→0、关闭27/27无错误，sync open27保持不变。每leg两个取消均实际peer EOF，正常重问同ID、API/SQL8消息一致；全部自有进程自然退出、端口释放。controller四次exit0仅表示收集完整，不替代backend退出。control01/02为平台白名单工具启动前失败，无产品进程，保留INCOMPLETE且不计复现。

04/02共享最终helper/source/hash与SQL消息，主控直接核对原始结果；新增工具契约10/10及主控fresh10/10。这不是产品TDD、全后端测试或全UI重验。01旧采样 `client_mutation` 文案歧义保留解释，最终配对改为 `observation_mutation`，不重写旧证据。

**裁定：固定本机fixture已两次正反向区分“是否执行应用自有async SDK收尾”；可进入最小产品生命周期设计，但尚无产品修复，C3仍不勾选，C/D整体裁定仍FAIL。** 不声称统计复现率、底层CPython根因或所有temporary variant/热重载旧client都已覆盖。产品下一步先在新独立源码副本核对registry创建/variant/reload的所有权，选择可证明的最小收尾；测试必须覆盖loop内关闭、唯一对象、错误可见、共享流不被单请求关闭，再用没有实验额外close的真实应用验证native exit0。不能直接复制诊断的私有字段访问或新增一个无限保留旧客户端的列表。

诊断规格/报告：`ROOT/reports/task-C-shutdown-diagnostic-brief.md`、`task-C-shutdown-diagnostic-report.md`；完整新工具diff与独立审查：`task-C-shutdown-diagnostic-review.patch` / `task-C-shutdown-diagnostic-review.md`（审查结论由后续收尾记录裁定）。主控原始配对核验：`ROOT/evidence/shutdown-coordinator-paired-verification.json`，fresh工具测试：`shutdown-coordinator-fresh-tests.log`。保护/当前凭据复扫待本次文档与审查落定后用新标签记录，不复用上一轮扫描给新内容背书。

独立复核发现P2：诊断工具强清理某个saved handle失败/超时后会短路，不尝试剩余owned；rows状态查询再次失败可能跳过结果和句柄关闭。四leg全部自然退出，因此不影响已取得退出区分，但不满足工具错误路径契约。原实施者仅补每handle错误可见/继续尝试/INCOMPLETE/finally close及负控RED/GREEN；不重跑native实验，不动产品。旧pair冻结版本保留，安全修订版另列hash/diff与未native重跑限制；修订后独立复核通过才裁定C3诊断完成。

#### C3诊断收尾（2026-10-06）

- [x] 固定fixture的有界正反向退出区分取证。
- [x] 诊断工具P2修正与独立复核：RED13项1failure+4errors，GREEN13/13，主控fresh13/13；`ROOT/reports/task-C-shutdown-diagnostic-review-v2.md` 的Spec/Quality均PASS、原P2关闭，首版REQUEST_CHANGES原样保留。
- [x] 新旧工具版本分离：已跑pair版本按字节保存在 `ROOT/evidence/shutdown-cleanup-repair-paired-original`，对应旧冻结hash；当前安全修订版diff为 `ROOT/reports/task-C-shutdown-diagnostic-review-v2.patch`，未重跑native，不用旧结果冒充新版执行。
- [x] 主控最终source/归档/端口核验：362源0变化、旧归档全部匹配、8041/8791空；`ROOT/evidence/shutdown-coordinator-final-sources-and-ports.json`。12项保护fresh全true：`ROOT/evidence/protection-C3-delivery.json`。
- [x] 选定文件当前凭据复扫：`ROOT/C3-closeout-scan.json` 实际exit0，395文件、9项精确值0命中，无缺字段；9项值正控和5形状正控通过，唯一形状命中为scanner自身private-key正控，已归类。文档回填后最终指纹另以 `ROOT/C3-final-confirmation-scan.json` 确认，不覆盖旧记录；扫描不证明未知/编码/历史密钥或全盘安全。
- [ ] 产品SDK生命周期修复、没有包装器额外close的真实退出验收和D综合正常收尾。

**诊断子任务完成，不等于C3产品修复完成；C/D整体仍FAIL。** 全局禁提交/合入/推送/部署等边界未变。下一步优先检查variant/reload仅改变模型请求参数时是否可复用本entry已有SDK客户端，减少新池与旧client保留负担；以当前安装版构造/字段契约测试证明，不提前承诺兼容。registry负责唯一对象收尾，main真实lifespan在loop仍运行时调用；不要在单请求取消时关闭共享池。范围建议限于新副本中的main、llm_registry与一个定向测试文件，必要工具适配另记；不扩展路由、schema或新的管理框架。

## D：受限真实联调、最终复核与交付

ROOT 已复制上一轮实验脚本作为起点；开始前逐一读取并适配路径、输入指纹和断言，不能直接沿用上一轮硬编码的失败裁定。

- [x] D1 冻结本轮源码/副本 SHA，保护快照；端口 3041/8041/8791 必须启动前空闲，冲突则另选空闲回环端口并重新构建，不能杀其他服务。
- [x] D2 使用同一公开库与 BGE 空间校验（8 冻结样本），禁网/禁 .env/外写的正向控制继续生效。当前 DEFAULT_ROLES 无 text/light，不得宣称缓冲分支已覆盖；配额 0 是降级默认路径，不假称正常多模型池。
- [x] D3 真实 UI 与直接后端分别取消首字前/部分正文后；替身 request_id、客户端停止时间与实际 disconnect 对齐，断开后不应完成全部 72 片段。目标：每个已到上游的取消案例在 3 秒内记录上游断开，fixture 单次写间隔≤0.5秒；没到上游的不算断开成功。
- [x] D4 真实新对话首字前与部分正文取消后直接重问，API 与 SQLite 必须同一 conversation_id，消息顺序、归属、计数匹配，integrity_check=ok；已有会话同样验证。取消助手消息仍为失败占位、coverage unknown，不误报半截已持久化。
- [x] D5 测试/构建完整输出、源码实际 diff、全部 owned 服务清理与退出码、主仓/原资源保护、选定文本凭据复扫。关掉本轮临时标签页，不动用户已有 3021 页面。
- [x] D6 执行任务级和组合只读复核；未证实的内容明确列出。候选是否通过和整个发布阶段是否通过分开裁定。

上述勾选只表示执行/记录完成：D3/D4 的限定取消与存储子门 PASS，但整次控制器在 UI watchdog 后 exit1，且 C 退出失败，因此 D 综合门仍 FAIL。预备首字前、旧 case 重问工具失误与未停止的摘要额外请求均保留并单列，不计入正式六例；不能通过删数据、缩小 SQL 判据或放宽超时伪造整次通过。

交付：ROOT/reports 下任务报告、审查报告与综合结果；主仓新增 `docs/process-archive/work-report-20261005-cancel-repair.md`，同时回填本执行书状态。交付的是独立候选和证据，不是自动合入主仓。

## 开工前复核

1. 模块边界：关闭资源留在创建它的已有流层；会话建立留在发送 hook，沿用已有 API。
2. 备选比较：只加早期 conversation meta 仍漏前置处理窗口；前端确认现有创建接口覆盖该窗口，但需测试创建期间取消/换页竞态，因此采用后者，不叠加两套机制。
3. 历史风险：未完成内容不能被标 full；取消不能触发故障换模型；重复发送/旧回调要有身份隔离；库/缓存始终隔离；守卫拒绝不能静默忽略。
4. 事实依据：全部基于上一轮真实代码、请求日志和 SQL；不存在 text/light 覆盖或真实云端计费承诺。
5. DoD：上游真实 disconnect、同会话 SQL/API、退出码与保护指纹是验收；“按钮不转了”与“单元测试全绿”不是替代判据。

执行顺序：A → A 复核 → B → B 复核 → C/D 联调 → 组合复核。主控负责隔离、集成和真实证据；实施文件单一归属，不在同一文件并行写入。

## 执行状态

2026-10-05 收尾：结构版源码冻结362文件，实际变化6个；A真实HTTP RED 2fail/24pass，最终A28 GREEN，主控独立28/28；B19定向、完整前端83/9文件和生产构建通过。A/B任务复核、组合源码及 round-03 事实一致性复核通过，新增可行动问题0。此前 round-01/02 的真实取消和退出 FAIL 原样保留，不覆盖旧清单/日志。

round-03 正式直连2＋UI4取消全部到过上游、0/1片段及时 peer EOF（均<3秒），四UI取消/重问同ID，API/SQLite5会话32消息、8占位配对/计数/值/integrity通过；362源文件与冻结输入一致。`cancel_flow_and_storage_pass=true`，但后端native退出0xC0000005、控制器UI watchdog exit1，`bounded_integration_pass=false`；本阶段未整体完成。全部7个owned进程与临时页面已清理，原3021不动。

收尾12项保护再次通过；文档回填前225文件、回填后226文件的9项当前凭据精确匹配均0命中，5种形状正控通过，唯一形状命中是scanner自身的private-key正控，已归类。只覆盖选定文件与当前输入，不代表全盘/历史无泄漏。保护/扫描明细在 `ROOT/evidence/protection-delivery.json`、`ROOT/final-scan.json`、`ROOT/final-delivery-scan.json`；最终文档指纹以交付前唯一命名 `ROOT/final-confirmation-scan.json` 为准，旧扫描不覆盖。

最终汇报：`C:/Users/33393/Desktop/ai-legal-helper/docs/work-report-20261005-cancel-repair.md`；C下一实验与D综合重跑边界：`ROOT/reports/task-C-D-report.md`。先做无UI同负载的C单变量诊断，再修fixture摘要识别/显式case/及时finish的工具回归，最后在新目录重跑综合门。不得凭本轮子门PASS合入或发布。B响应丢失仍可能留下空会话，非跨网络exactly-once；queued acquire、pre-body、Agent/text/light/云模型等未纳入本轮证明。
