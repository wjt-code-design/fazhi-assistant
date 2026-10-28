# 法智：固定提交的测试覆盖审查

日期：2026-10-20（Asia/Shanghai）。

## 1. 执行结果与范围

本轮已实际执行 Git 对象读取、测试源码检查和定向搜索，固定对象为：

- 仓库路径：C:/Users/33393/Desktop/ai-legal-helper/.worktrees/nondeploy-closeout-20261010。
- 提交：**30a767408f76a7fc90ff79a8547715f315a46ca4**。
- 提交标题：R15：模型失败即立刻作废半截，后续尝试全空时不再把半截当答案。
- 所有后续源码读取均显式使用该提交的 Git 对象，助手继续编辑或提交不改变本轮受审字节。
- 本轮没有运行测试、服务、构建、模型，没有导入应用模块，没有读取凭据或数据库；仅新增本报告。

审查问题是：现有测试能够证明哪些验收行为，还缺什么证据。没有对当前全部修复作成立性或通过判定。下列补验收项的优先顺序不等于新增产品漏洞分级；也不能把固定提交的覆盖缺口直接认定为助手最终交付遗漏。

依据：[验收矩阵](C:/Users/33393/Desktop/ai-legal-helper/docs/process-archive/reviews/2026-10-20-audit-acceptance-and-integration-checklist.md)。本轮重点抽查 R05/R06、R10、R13–R20、R25 的相关测试；没有逐项完成 R01–R25 全部审查。

## 2. 已见有效覆盖设计

以下评价仅基于测试源码，运行结果均未验证。

| 对象 | 已见测试设计 | 可以支持的证据范围 |
|---|---|---|
| R15 | test_stream_restart_discards_partial.py 两条用例通过 /api/chat，覆盖旗舰与合同，合成半截后失败、随后尝试全空；检查至少重试一次、出现 error，合同不进入 reviewed | 已有面向原触发路径的端点测试设计，比只测重试函数更接近调用方 |
| R16 | test_quota_switch.py 的 test_retry_after_unclosed_think_keeps_backup_body 和 test_each_attempt_strips_think_independently，直接调用 stream_with_retry | 覆盖前一尝试未闭合 think 后，后备正文应正常输出，以及完整 think 过滤 |
| R05 | conversation-view-guard.test.ts 调真实 useConversations，控制详情 Promise；覆盖新建、后选优先、旧失败及删除当前会话使 token 失效 | 覆盖 hook 内消费迟到详情结果的部分行为；React 运行时由测试替身提供 |
| R10 | sw-build-id.test.ts 在临时目录调用真实构建脚本，比较两个构建号产物，检查占位符被替换 | 覆盖生成脚本产物及版本字节变化；未实际运行浏览器 Worker |
| 基础设施 | conftest.py 在导入前设置临时 DATABASE_URL、QUOTA_DB、CHROMA_DIR；共享 SSE harness 建内存库 | 已有隔离设计可复用。仍需按用例核对其他依赖、真实语料 fixture 和模型替身，不据此保证任何测试均可安全并行 |

R15 的生产代码在本提交内已见两个失败回调清空 chunks；R16 的解析器在重试循环内创建。这里只记录源码变化，不声称修复通过；本轮未重现修前失败，也不把测试注释中的“改前失败”当作亲自观察结果。

## 3. 优先补充的验收证据

### T01：R15 仍缺持久化、缓存及完整重置链的断言

证据位置：[端点测试](C:/Users/33393/Desktop/ai-legal-helper/.worktrees/nondeploy-closeout-20261010/backend/tests/test_stream_restart_discards_partial.py)，提交内第 60、71 行起；[共享夹具](C:/Users/33393/Desktop/ai-legal-helper/.worktrees/nondeploy-closeout-20261010/backend/tests/_sse_harness.py)。

两条新用例实际断言 shared.n >= 2 和出现 error；合同用例另外断言 reviewed 为空。该文件没有查询失败请求后的消息记录，也没有答案缓存写入、QA 收录或客户端 restart 行为断言。

因此，一旦未来回归为“发 error 同时仍保存半截为正常答案”或“失败答案写进缓存”，这两条用例本身未必能发现。这个判断来自断言范围，不代表固定提交已发生该行为。

建议最小补查：

1. 两个原场景保留，增加缓存写入 spy，断言失败残片没有成功答案资格；在临时数据库检查失败请求后的 assistant 记录及其状态。
2. 补“半截失败→后备完整成功”，检查最终保存、缓存的是后备正文，并检查 SSE restart 与用户最终视图。
3. 失败草稿若为既定设计可保留，但必须明确区分失败与成功，不能机械要求所有失败相关记录都删除。
4. 复用现有 cache_put_spy 和内存库夹具；该夹具会替换部分路由、引用检查及配额，因此不能用同一结果同时声称真实引用质量或记账已验证。

### T02：R06 的页面解析、发送请求没有随 hook 测试一起覆盖

证据位置：[会话视图测试](C:/Users/33393/Desktop/ai-legal-helper/.worktrees/nondeploy-closeout-20261010/frontend/tests/conversation-view-guard.test.ts)，提交内第 208 行附近的附件用例，以及 mount 中的 clearFile: vi.fn()。

该文件能证明 hook 调用了 clearFile、视图 token 发生变化；它不挂载 chat/page.tsx，也不执行页面的文档解析回调和最终发送。clearFile spy 被调用不证明页面真的清掉 fileContent，token 增加也不证明解析消费点实际比较了 token。

建议最小补查：在隔离页面中暂挂文档解析，切换/新建后让旧解析完成，输入 B 的新问题并发送，观察真实请求的文本、附件和 conversation_id；再测解析完成后切换。需要自动化时沿用已有环境，不为此先引入一套前端框架。

R05 已有真实 hook 的异步断言，应保留；补页面边界并不要求重写其测试。

### T03：R13、R14 目前是源码接线守卫，浏览器行为仍待证

证据位置：[上传重置测试](C:/Users/33393/Desktop/ai-legal-helper/.worktrees/nondeploy-closeout-20261010/frontend/tests/upload-input-reset-wiring.test.ts)、[语音停止测试](C:/Users/33393/Desktop/ai-legal-helper/.worktrees/nondeploy-closeout-20261010/frontend/tests/usevoice-unified-stop-wiring.test.ts)。两份文件注释已明确说明 node 环境及行为限制。

- 上传测试读取源码，检查清空 input 的字面量位于 finally 之后；没有让浏览器失败后重新选择同一文件。
- 语音测试读取源码，检查 cleanup 和 listening 分支出现 recRef/stop 字样；不执行识别器，不检查迟到回调、计时器或卸载后的输入。

建议最小补查：

1. 上传失败后选择原文件，实际请求计数应增加，busy 状态解除、错误可见。
2. WAV 与 Web Speech 分别开始、主动停止、卸载并派发迟到事件；检查真实活动识别器和输入。
3. 正常 WAV 停止后的预期转写保留，不能把“停止后不接收旧识别”误修成“所有停止后的转写都扔掉”。

现有接线守卫可以保留；其通过结果应明确标为接线层覆盖。

### T04：R10 构建产物有测试，Worker 生命周期仍缺运行证据

证据位置：[构建号测试](C:/Users/33393/Desktop/ai-legal-helper/.worktrees/nondeploy-closeout-20261010/frontend/tests/sw-build-id.test.ts)。

该文件运行生成脚本并读取 sw.js，覆盖构建号嵌入、版本产物变化、桥接文件。没有在浏览器安装、终止、唤醒或更新 Worker。

建议最小补查：独立生产模式浏览器完成首次安装→Worker 终止后唤醒→A/B 两构建更新→按既定承诺测试离线访问；记录实际缓存名称、响应来源与动态/API 排除边界。构建脚本用例不能替代这条生命周期证据，也无需为此新增离线功能。

### T05：R20 的升级测试关闭了扣账，无法证明用量归属

证据位置：[升级测试](C:/Users/33393/Desktop/ai-legal-helper/.worktrees/nondeploy-closeout-20261010/backend/tests/test_tiering.py)，提交内第 57 行把 registry.deduct 替换为空函数；第 79 行起的升级用例仅检查 tier、escalated、verdict、key。[路由记账测试](C:/Users/33393/Desktop/ai-legal-helper/.worktrees/nondeploy-closeout-20261010/backend/tests/test_routing.py) 第 184 行起直接调用 deduct；其 store 是字典替身。

升级结果正确与 deduct 函数独立可累加，组合起来仍不能证明生产调用方把 L/F 用量记到正确 key；字典 store 的“持久”断言也不能证明 SQLite 重载。

建议最小补查：从支持 light 的真实入口开始，以 L=100、F=200 合成 usage，经过轻量失败升级，检查每 key 增量及临时配额库重载；再测不升级、同 key、usage 缺失。仅在合法配置提供 light 时适用。现有专注升级状态机的测试可继续关闭扣账，但应增加一条专门的集成记账用例。

### T06：R17 的现有导入用例验证成功替换，未验证写失败保留旧 seed

证据位置：[导入测试](C:/Users/33393/Desktop/ai-legal-helper/.worktrees/nondeploy-closeout-20261010/backend/tests/test_import_docs.py)，提交内第 75、108 行起。

已读用例使用临时 Chroma、假嵌入，验证成功替换 seed、条号及 file_hash 幂等；没有注入新写失败。成功后 seed 消失是正常预期，不能证明失败时 seed 可用。

建议最小补查：复用 tmp_collection，先放 seed；在实际新条文嵌入/写库边界抛错，再通过真实 collection.get 及适用的检索入口确认旧文仍在；随后恢复依赖成功重跑。不要把整个 import_one 替换成异常桩。部分批量写入后失败的场景在底层支持时单列。

本结论针对该测试文件的可见覆盖；没有宣称全仓不存在其他间接故障用例。

### T07：R19 尚未定位到校准与置尽组合的测试证据

已对固定提交的 backend/tests、frontend/tests 搜索 calibrat、llm-quota、校准；匹配主要为注释或无关合同描述。另读 test_quota_switch、test_llm_admin、test_routing；可见测试覆盖置尽不可选、管理禁用/恢复、直接 deduct 等，未定位到“mark_depleted→calibrate→重载→重新选择”的断言。

这是**待补证据项**：词法搜索不能证明所有动态、间接调用都不存在；接手助手可提供已有用例和准确断言来消除缺口。

建议最小补查：用真实 ModelEntry、临时 quota_store，从 total=1000 置尽后校准剩余 500，检查管理入口、内存、重载及模型选择；再覆盖估算过扣和明确的校准/扣减顺序。不要只检查状态码 200，也不要用与实现同一条公式生成预期。

### T08：R25 已有引用配对测试，但没有覆盖 chat 的终止及重置语义

证据位置：[冒烟断言测试](C:/Users/33393/Desktop/ai-legal-helper/.worktrees/nondeploy-closeout-20261010/backend/tests/test_smoke_citation_assertions.py) 与 [full 脚本](C:/Users/33393/Desktop/ai-legal-helper/.worktrees/nondeploy-closeout-20261010/backend/scripts/smoke_citation_full.py)；脚本提交内第 69–89 行。

已见测试重视法名与条号成对、main 调用判据、样本表和 import 副作用，具有独立预期。该文件未调用 chat 的合成 SSE 路径。脚本 chat 只累加 content；[DONE] 被跳过，error/restart 没有参与判定，请求体也未显式指定 no_cache。

建议最小补查：替换 urllib 响应迭代器，输入“正确引用半截→error”“旧正文→restart→新正文”“无正常终止”和正常完成；检查最终判定及实际请求体。声称新生成或升级验收时，另外证明缓存直返被排除和实际路由调用；内容冒烟仍可保留，但结论范围必须相符。无需真实模型调用来测这些确定性事件。

### T09：R18 的候选池测试未构造同正文不同身份

证据位置：[候选池测试](C:/Users/33393/Desktop/ai-legal-helper/.worktrees/nondeploy-closeout-20261010/backend/tests/test_retrieval_pool_k.py)。

其 _mk_docs 使用 v-i、b-i 不同正文，断言召回深度、返回条数、缓存键。这能验证池深契约，不能辨别“正文相同，法名/版本不同”的身份丢失，也不能证明同身份双路合并。

建议最小补查：复用该文件已有 pipeline 替身，仅更换向量与 BM25 输出数据，保留真实 hybrid_retrieve 融合。放入同正文不同 source/version 的两个片段及同片段双路副本，断言最终身份和元数据集合；交换召回顺序。不要只断言数量。

本项只评价已读候选池用例；未完成全仓检索身份测试的穷尽分析。

## 4. 覆盖率数字的口径

[Vitest 配置](C:/Users/33393/Desktop/ai-legal-helper/.worktrees/nondeploy-closeout-20261010/frontend/vitest.config.ts) 的 coverage.include 仅包含 lib/annotate.ts、lib/scope.ts、lib/sse.ts，并设置 all:false；运行环境为 node。

因此，现有 test:cov 的数字应按这三个模块的配置口径解释。不能把它当作 chat 页面、语音 hook、上传组件或整个前端的覆盖率。本轮没有运行 coverage，没有给覆盖率百分比，也不建议为制造数字机械扩大分母。

## 5. 交给正在修复的助手

~~~text
这是一份固定在 30a767408f76a7fc90ff79a8547715f315a46ca4 的测试覆盖审查。请在现有任务交付阶段对照 T01–T09；不用中断正在进行的修复，也不要把报告当作当前工作树仍缺测试的断言。

先检查之后的提交是否已补齐，已有证据直接给出；缺口成立且属于本次修复范围时，再按原任务授权补最小验收。优先 T01 的失败结果落库/缓存、T05 的逐模型记账、T06 的导入失败保旧文；T02–T04 需要页面或浏览器生命周期证据。T07 是尚未定位到证据，不据此断言全仓不存在测试。

保留已有有效测试。hook 调用清理回调不等于页面发送正确，字面量接线不等于浏览器行为，直接 deduct 能累加不等于路由归属正确，引用配对正确不等于 SSE 完整成功。

所有执行使用隔离数据及替身，沿用已有授权，不读取真实凭据或库，不调用付费模型，不复用共享服务。交付时分别写明源码已见覆盖、实际运行结果和未覆盖环境；不要以旧日志或测试注释代替本次证据。
~~~

## 6. 可复核读取方法与限制

本轮使用 git rev-parse 确定快照，随后使用 git ls-tree、git show、git grep 读取固定对象；没有切换分支或创建工作树。示例（在 PowerShell 中执行，仅列读取命令）：

~~~powershell
$reviewRepo = 'C:/Users/33393/Desktop/ai-legal-helper/.worktrees/nondeploy-closeout-20261010'
git -C $reviewRepo show '30a767408f76a7fc90ff79a8547715f315a46ca4:backend/tests/test_stream_restart_discards_partial.py'
git -C $reviewRepo show '30a767408f76a7fc90ff79a8547715f315a46ca4:backend/tests/test_tiering.py'
git -C $reviewRepo grep -n -i -E 'calibrat|llm-quota|校准' 30a767408f76a7fc90ff79a8547715f315a46ca4 -- backend/tests frontend/tests
~~~

上面的本地文件链接便于导航；助手修改后，本地字节和行号可能已变化，复核必须使用固定提交命令。未读取未提交测试，未检查本提交之后的修复，未收集或采信其他助手的旧测试日志。

**结论：已完成静态测试覆盖审查；产品动态验收未执行。**需求轴已建立本轮样本与既有验收项的对应；工程质量轴发现若干接线、持久化与生命周期证据缺口。两轴均不支持“全部修复已通过”的结论。
