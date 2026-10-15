# 主仓本地整合工作报告（含历史失败与提交前封口）

时间：2026-10-08（Asia/Shanghai）。状态：**A 修补及最终 round-11/control-13 技术验收已闭合，双轴只读复核无剩余阻断；本文件是提交前封口内容，最终扫描与实际本地提交结果以本轮 `evidence/delivery-closure.json` 为准**。最新状态见末尾，早期轮次及暂停段落是保留的历史记录，不是当前授权或验收结论。

## 范围与工作区

主仓为 `C:/Users/33393/Desktop/ai-legal-helper`，基线 `902e2d161e67100ed6d267a08c393538a0abe109`，分支 master。用户已批准必要候选修补、本地验证后提交，要求保留原有六处修改，不推送、不部署、不改真实数据、不调用真实模型。

本轮隔离根为 `C:/Users/33393/Desktop/fazhi-main-integration-20261007`。只读旧候选为 `C:/Users/33393/Desktop/fazhi-closeout-auditfix-20261007`。共享 Python venv 未改；公开离线 BGE、Node 依赖、数据库、配额、临时目录和浏览器配置均使用本轮私有副本/路径。已有端口 3021 服务未操作。

25 个产品/测试路径已选择性暂存：原 24 路径的取消容量/流资源收尾、日期/PDF 输入校验、SDK 客户端关闭、既有依赖声明、前端停止生成与回归测试，以及新增 `test_chat_turn_persistence.py`。必要追加包括缓冲回答异步化、嵌套模型配置 repr 脱敏、异步测试夹具适配和生命周期夹具环境恢复；不修改法律判据、不增加业务架构。

六处原有修改仍未暂存：旧计划、管理知识/上传页面、globals.css，以及聊天页/InputBar 中原有图片/移动布局改动。两处重叠文件仅暂存本轮取消接线。未整树 add；大量既有未跟踪产物未纳入。后续提交前还须重复核对重叠文件残留差异。

## A 修补前的检查点证据（历史，不代表当前 main.py 已验收）

以下路径均位于上述本轮隔离根，而不是引用旧候选的通过结果。

| 检查 | 实际结果 | 证据位置 |
| --- | --- | --- |
| 后端全部非 slow 用例 | 1819 通过、10 跳过、18 slow 排除，退出 0；覆盖率 85.82% | `evidence/staged-backend-full-02/` |
| 执行集合核对 | 1829 项选中用例均有唯一终态，无遗漏、重复或失败 | `evidence/backend-execution-set-check-v2.json` |
| Ruff / format / mypy | 均退出 0；mypy 为 74 文件无报错，未检查的未标注函数体仍属其配置边界 | `evidence/staged-ruff-01/`、`staged-format-01/`、`staged-mypy-01/` |
| 暂存前端 | 83 测试通过；tsc、生产构建退出 0 | `evidence/staged-frontend-tests-02/`、`staged-frontend-tsc-02/`、`staged-frontend-build-01/` |
| 保留原有修改的前端视图 | 83 测试通过；tsc、构建退出 0 | `evidence/working-frontend-tests-01/`、`working-frontend-tsc-01/`、`working-frontend-build-01/` |
| 工具输入负控 | 123 测试和 3 子测试通过，退出 0 | `evidence/green-reference-input-02/` |
| 取消 SDK 机制定向回归 | 42 测试通过，真实 SDK 对接本机替身；证明 peer 断开而非关闭共享池 | `evidence/green-cancel-mechanisms-04/` |
| 正式输入绑定 | 两腿一致；379 源文件、53 工具、18 种子及固定 BGE 参考匹配 | `evidence/round-09/final-verification.json` 的 `run_inputs` |
| 正式取消/浏览器 | 2 API + 4 真实 Edge 交互，上游取消、输入恢复及同会话重问检查通过 | 同文件的 `cancellation`、`ui_evidence`、`conversation_checks` |
| 实际摘要压缩 | 独立普通对话 8 轮、16 条消息，最终 summary_upto=10，两个摘要请求完成 | `evidence/round-09/summary-leg.json` |
| 独立关闭控制 | 原生退出 0，所有 SDK async/sync 客户端关闭；无额外关闭干预、无强杀 | `evidence/shutdown-control-11/result.json` 和 `resources-after-lifespan-end.json` |

10 个 skip 是 8 个隔离空库下不可用的 real_kb 用例，以及 2 个未启用帧转储开关的可选用例；不记作通过。前端构建日志有 Windows standalone node_modules 复制 EPERM 警告，退出 0 不能证明部署包完整。

早期失败均保留：round-08 因缺少公共 BGE 参考文件启动失败，原 53 工具另存 `evidence/round-08-tool-inputs/` 并核验清单；补齐输入、增加缺失/漂移拒绝负控后才运行 round-09。未重写失败日志或复用旧通过标签。

## 总门禁仍失败：必须先修存储竞态

复核命令（已实际执行，退出 1）：

```powershell
& 'C:/Users/33393/Desktop/fazhi-next-local-20261004-356fb810b3144d158e5dd18b9e276499/joint/venv/Scripts/python.exe' -I -B 'C:/Users/33393/Desktop/fazhi-main-integration-20261007/verify_final.py' round-09
```

总结果 `bounded_integration_pass=false`；存储的 `counts_match=false` 和 `turns_paired=false`。其余输入绑定、取消、浏览器、摘要、SDK 收尾及原生退出轴通过，但不能覆盖存储失败。

- 会话 7：计数 3，实际 4 条消息。
- 会话 5/6/7：取消后立刻重问，出现 user、user、占位 assistant、正常 assistant，而非逐轮配对。
- 原始文件为 `C:/Users/33393/Desktop/fazhi-main-integration-20261007/evidence/round-09/final-persistence.json`。SQLite integrity 为 ok，API 与 SQLite 消息内容一致；这是产品竞态，不能通过重排证据或放宽判据处理。

两路只读复核确认：

1. `_post` / `_post_placeholder` 在 SQL 原子自增后，仍把旧 ORM 计数加一写回。工程审阅者用真实函数、双 Session、纯内存 SQLite 确定性复现覆盖并发增量；移除旧赋值的内存对照不再覆盖。这不是主仓修复通过证据。
2. 前端 abort 后立即解锁；entered-stream 的 finally 后台派发占位但不等待，新的 bootstrap 可以先写第二条 user。仅删除计数赋值或仅 await 补偿均不足以保证下一轮顺序。
3. 代码复核还发现 `_post` 已 commit 后，附带沉淀/压缩异常可能让调用方误判未落库并重复补偿；本轮尚未用独立产品测试验证这一分支。

## 已确认的修补边界（实施中，未闭合）

推荐：同会话的下一轮在 bootstrap 写入前，自动等待上一轮持久化终态；当前响应负责屏蔽取消地等待唯一占位 commit 后放行。不同会话可并行，排队期间取消不能落用户消息。删除旧计数写回，必要时刷新 ORM 读值；已提交答案不得因附带后处理失败再补占位。

保持现有前端即时停止体验，不新增取消 API、依赖、数据库字段、分布式锁或后台框架。保证范围限定为现有单 worker；不宣称多进程全局序列。

预留助手消息行是另一种选择，但会改变历史/上下文与 Agent 路径，影响面更大。仅修计数并登记乱序限制虽小，却不满足本阶段原配对门禁。

用户已回复 A 批准该边界。已开始确定性回归与修补，但尚未完成全部异常边界、全量和正式验收；旧 round-09 原样保留。恢复后按暂停断点继续，不直接跳到提交。

本地提交仍须：所有必需门禁通过、提交内容凭据扫描、实际测试源码与 Git index 一致、原有六处残留差异及保护清单复核。最终扫描、报告冻结和提交尚未执行。

## 限制与阶段结论

目前是“本地主仓整合完成、发现新存储阻断待修”的阶段，不是发布就绪。真实模型/法律质量、远端 CI、部署包和生产环境均未在本轮验证；T7 依赖风险不由本轮豁免。不 push、不部署，不修改真实库和密钥。

2026-10-08 01:15 的保护检查退出 0：四个非重叠原有文件、主仓真实配置/数据库保护项、旧候选清单和共享 venv distribution 列表无漂移。这不是对共享 venv 每个文件逐字节冻结的证明。后续提交前重叠文件仍须独立复核。

本报告已自审：没有将控制进程退出 0、单测通过、内存探针对照或替身回答等同于正式总门禁通过；未使用伪造完成勾选。

## 暂停断点（2026-10-08，用户要求“找时机暂停”）

暂停前已等正在运行的 `red-rejected-input-01` 隔离测试自然结束；未开始新的产品修改、全量验收、提交或发布操作。此次私有服务端口 8041/8791/3041 未发现监听；未操作原有 3021 服务。

当前 HEAD 仍为上述基线，26 个路径仍在先前暂存区。`backend/main.py` 的后续 A 修补、新增 `backend/tests/test_chat_turn_persistence.py` 及本报告/计划的最新更新尚未重新暂存；原有六处修改仍应保留，不允许整树 add。下一阶段规划尚未写出，因为本阶段仍有阻断。

已实施、尚待完整验收：移除两条旧 ORM 计数写回；答案/占位 commit 标记；取消占位 shield-await；认证用户＋实际会话编号的进程内锁、180 秒有界等待、直接 acquire＋asyncio.timeout；请求私有响应清理后释放所有权。普通缺省/失效/非本人编号复用现有会话 CRUD 新建，Agent resume 不自动重建。没有增加依赖、数据库字段或分布式锁。

定向证据的准确口径：

- `red-turn-persistence-02`：5 个目标断言失败，确定性复现旧计数覆盖、快速重问乱序、后处理异常重复占位；早先集合导入失败不算产品红证据。
- `green-turn-persistence-02`：首版修补 10 个用例通过，不覆盖后来发现的真实编号和获锁同拍取消边界。
- `red-turn-persistence-05`：4 失败、10 通过。其中仅同拍取消失败可作该边界有效红；另 3 项是测试把列表模型当 dict，不能算编号竞态的红证据。
- `green-turn-persistence-03`：实际 11 通过、3 失败、退出 1；不能因标签名叫 green 就报通过。该测试夹具已修正为属性访问。
- `red-identity-ownership-01`：明确移除实际编号解析的隔离负控，3 失败、11 通过；3 项均在“已公开编号没有持久化所有权”的目标断言失败。
- 暂停前最后的 `red-rejected-input-01`：18 通过、4 失败，退出 1。14 个核心/真实编号/同拍取消用例及 4 个空文本/不支持视觉拒绝用例通过；历史查询关闭的 2 项因残留空会话失败。坏图片的 2 项撞到测试夹具缺少视觉接线，不能作产品缺陷复现或验收通过。必须修正夹具，不得改变预期来抹掉失败。

恢复后的顺序：

1. 修正拒绝输入测试夹具，保留产品真实图片校验；把现有历史权限和纯图片输入校验放到新会话提交前，保持拒绝请求不留空会话的旧语义。无需新建验证框架。
2. 复核“编号解析后、等待锁期间并发删除会话”的剩余边界：bootstrap 可能再次新建编号而锁仍绑定旧编号。该项目前是源码推导、未复现；不能声称已经覆盖。若修补需要扩展到删除路由或改变 API 语义，先通过 grilling 对齐，不自行扩权。
3. 补用户消息 commit 后、response 构造前检索异常的确定性测试。现有路由异常测试只覆盖 bootstrap 前，不足以证明所有异常出口逐轮配对；按批准的最小补偿边界修补或明确登记未闭合，不能直接放行。
4. 所有定向及双轴审查闭合后，才选择性暂存、重新导出、运行新后端非 slow 全量/静态检查，再冻结并执行 round-10/control-12。不要引用旧全量结果作为当前 main.py 已通过证明。
5. 正式验收、凭据扫描、index 与测试输入一致性、六处原有差异及保护清单均通过后才本地提交；然后根据真实状态写并自审下一阶段计划。不 push、不部署、不动真实库、不调用真实模型。

私有工具已将运行标记改为 round-10/control-12，但它们尚未运行、尚未重新冻结。`evidence/final-source-manifest.json`、`final-tools-manifest.json` 和 `product-changes-final.json` 仍描述 round-09，**不能直接用于当前新代码**。旧 379 源/53 工具输入已分别留存于 `evidence/round-09-source-inputs/`、`round-09-tools-inputs/`，并保存带 round-09 前缀的清单。恢复后须先保留旧清单，再生成新清单，禁止覆盖失败证据。

当前主仓新修补与 `review-source` 的 main.py 一致；最新测试亦已同步。`source/` 仍是旧正式输入，不是最新代码。无后台新全量任务，无已完成本阶段或已提交的声明。

## 恢复进展（2026-10-08）

用户回复“继续”后恢复。先核对暂停时的 HEAD、暂存/工作区差异，再修复图片回归接线。已有 `_route_namespace` 夹具只增加可选 `image_validator` 参数，原调用默认不变；新持久化回归传入产品 `validate_image`，仍使用真实 bootstrap、临时 SQLite 和事件控制，不通过伪造图片结果放行。

`red-rejected-input-02` 已自然结束：18 通过、4 失败、退出 1。历史查询关闭及坏图片各 2 项均在“拒绝请求不应残留空会话”的目标断言失败，已不是夹具 NameError。中途对旧会话进程 ID 的轮询返回 Unknown process id；随后读取完整 result/log 确认测试结束，未重复启动该红测试。

最小产品修补：普通聊天在创建新会话前复用 `_client_law_as_of` 的权限拒绝门；有图且支持视觉时先调用现有 `validate_image`，ValueError 仍转原 400。bootstrap 内原图片校验保留，未降低公开 bootstrap 的信任边界；没有新增校验框架或更改拒绝状态码。

新鲜定向结果：`evidence/green-rejected-input-01/` 为 **22 通过、0 失败、退出 0**。可复现命令如下（新运行需使用新的唯一 evidence 标签，不能覆盖该标签）：

```powershell
& 'C:/Users/33393/Desktop/fazhi-next-local-20261004-356fb810b3144d158e5dd18b9e276499/joint/venv/Scripts/python.exe' -I -B 'C:/Users/33393/Desktop/fazhi-main-integration-20261007/tools/verify-local.py' review-source turn-persistence green-rejected-input-01
```

这 22 项包含原计数/占位/快速重问、实际会话编号、获锁同拍取消及四类拒绝输入，限于隔离测试、真实 SQLite/真实产品函数配合受控检索与缓存边界，不是完整后端/正式浏览器验收或真实模型质量结论。新源码尚未重新导出到正式 `source/`，final 清单仍属 round-09，round-10/control-12 尚未运行。

下一步需 grilling 确认的行为：前端 `useConversations.deleteConv` 仅在 streaming 为 true 时禁止删除；停止生成后 streaming 已解除，但后端可能还在提交占位。当前 DELETE 路由不参与聊天门闩，因此“编号解析后、等待期间被删除”的竞态不能仅靠前端约束排除。

推荐 A：同会话删除参与现有串行边界，等正在执行的轮次收尾后删除；若删除已完成，先前排队的聊天请求返回 404，不静默重建会话。该选项涉及删除路由及排队聊天的 API 语义，**尚未获本次明确确认、尚未实施**。备选 B：本轮不改删除路由，将并发删除列为明确限制，不能声称此场景已被串行边界保护。没有为了让阶段通过而默认采用任一选项。

用户消息 commit 后、response 构造前检索异常的终态补偿仍未闭合；本轮没有借 22 项绿色将该项勾选完成。确认删除边界后，再补确定性测试与必要最小修补，随后双轴复核、全量/静态、正式验收、扫描及本地提交；不 push、不部署、不动真实库。

## A 边界实施及验收进展（2026-10-08 17:30）

上述“尚未确认”的描述是先前断点，不是当前授权状态。用户随后回复 A，批准同会话 DELETE 等待已有轮次收尾；已解析的会话在排队期间被删除时，聊天返回 404，不重新创建。现在已实施：聊天和删除共用现有单 worker 门闩，获锁后重新核对所有者及已有 `created_at`，拒绝 SQLite 编号复用；未新增表字段、依赖或分布式锁。初始缺省/不存在/非本人编号的普通聊天仍沿用既有新建语义。

用户消息已 commit 后、响应构造前的共享检索准备异常，已在既有准备边界增加最小补偿。三类异常的回归使用真实产品函数及 SQLite，确认 user 后紧接唯一失败占位；这不代表所有数据库故障或所有可能异常出口都已被证明可恢复。

独立红/绿证据保留如下：

- `red-delete-ownership-01`：3 失败、22 通过；删除过早完成及两项排队聊天未拒绝已删除会话。
- `red-delete-incarnation-01`：1 失败、29 通过；排队删除未拒绝被重新创建的同编号会话。
- `red-prepare-failure-01`：4 失败、29 通过；其中 3 项为已提交 user 后检索异常缺少占位，另 1 项是上一条尚未修复的删除边界。
- `green-turn-final-01`：33 通过、退出 0。覆盖上述边界及原计数、快速重问、拒绝输入和获锁同拍取消；不替代正式验收。

最新源码已选择性暂存并导出到 `source/`（380 路径），不再是旧 round-09 输入。但当前 final 清单仍属 round-09，尚不能据此运行正式新轮次。

完整后端 `staged-backend-full-03` 实际为 12 失败、1840 通过、10 跳过、18 slow 排除，退出 1。12 项都记录 `[chat-cancel-compensate] failed: NameError`：AST 提取测试的公共命名空间漏接新产品代码使用的 `run_in_threadpool`。已只补现成的真实 Starlette 函数接线，保留原占位/SDK 收尾断言；`turn-mechanisms-02` 为 42 通过、退出 0。工具 `turn-tools-01` 为 1 失败、122 通过（另 3 subtests），原因是测试写死旧 control-11；现改用本轮常量并新增旧失败轮次不可复用的断言，`turn-tools-02` 为 123 通过（另 3 subtests）、退出 0。

静态检查 `staged-ruff-02`、`staged-format-02`、`staged-mypy-02` 均退出 0；mypy 为 74 源文件，日志仍明确提示未标注函数体默认不检查，不能当作全覆盖类型证明。补接线后的全量 `staged-backend-full-04` 正在运行；两轴只读复核及正式 round-10/control-12、最终扫描/保护/提交仍待完成。旧失败证据没有改名为成功、没有覆盖或删除。

## 新全量及双轴复核完成（2026-10-08，正式集成尚未裁定）

`staged-backend-full-04` 已自然结束，退出 0：**1852 通过、10 跳过、18 slow 排除**，综合行/分支覆盖率 86.11%。1862 个选中项逐一与原始报告/JUnit 核对：1862 个唯一终态，0 遗漏、0 重复、0 failure/error。coverage XML 单独的行覆盖率为 87.58%（7684/8774），不与综合覆盖率混用。集合复算材料见 `evidence/backend-execution-set-check-v3.json` 及该标签下 collection/report/JUnit/coverage 原始文件。

跳过条件沿用上述历史口径，不当作通过；唯一警告是 FastAPI TestClient 所用 httpx 的弃用提示。守卫记录 10 次子进程拒绝，属于依赖 CPU 特性探测降级及既有工具负控，未扩大为任意子进程许可；批准 CLI 在守卫内独立执行记录仍在该标签下。

最新夹具源码的 `staged-ruff-03`、`staged-format-03` 退出 0（274 Python 文件符合格式）。产品源码未再变化，mypy 使用 `staged-mypy-02` 的 74 文件退出 0 结果；没有把测试夹具接线假称为产品重测之外的类型全覆盖。

不同子会话的 Spec 与 Standards 复核均无已确认阻断；各自范围和限制保存在 `reports/a-boundary-independent-review-20261008.md`。属于同工具链/仓库的替代性独立，只读复核者未亲自运行测试，正常保护用例逐例等价代理未全部审计；不冒充外部独立认证。

隔离全量生成的空 Chroma 目录已移到本轮 `runtime/staged-full-04-generated-empty-chroma` 保存，未删除主库或旧证据。旧三份 final 清单已保留为 `evidence/pre-round-10-*`；新源码清单为 380 路径，工具 53 路径。相对 364 路径测试基线的 32 差异包括 25 个本轮产品/测试路径和 7 个原已被主仓跟踪的公开测试支撑文件，后者不作为新增提交。新 round-10 已验证输入快照（另有 18 公开种子）并启动，正式结果尚待结束及总裁定；不提前写通过或提交。

## 正式验收闭合与交付边界（2026-10-08）

新命令 `PY -I -B verify_final.py round-10` 实际退出 0，`bounded_integration_pass=true`、`cancel_flow_and_storage_pass=true`。两腿记录的 380 源/53 工具/18 种子及 BGE 参考与冻结字节一致；没有修改判据或重排消息来放行 round-09 失败。

| 本轮检查 | 已观察结果 | 原始证据（隔离根的 evidence/ 下） |
| --- | --- | --- |
| 存储 | SQLite integrity ok，8 会话/44 消息；计数、API/SQL id/正文一致，严格 user/assistant 配对；6 个失败占位，部分正文未持久化 | `round-10/final-persistence.json`、`round-10/final-verification.json.storage` |
| 取消/浏览器 | 2 API + 4 Edge 案例各自有唯一上游 client_disconnect；首字前/部分输出阶段、输入恢复、同编号重问及新会话重开历史通过 | `round-10/api-cancel-summary.json`、`round-10/ui-observations/`、`round-10/final-verification.json` |
| 摘要 | 8 轮/16 消息，summary_upto=10；2 个摘要请求均完成 | `round-10/summary-leg.json`、`round-10/stub-requests.jsonl` |
| SDK/退出 | control-12 无额外 SDK close 干预，async/sync 最终打开数 0/0；后端/stub 原生自然退出 0，保存身份/句柄且端口释放 | `shutdown-control-12/result.json`、`resources-after-lifespan-end.json`、`round-10/cleanup.json` |
| 前端/工具 | 本轮 83 前端测试、tsc/build 退出 0，控制器 guard 测试 108 通过；根级 cleanup 契约另由 turn-tools-02 的 123+3 覆盖 | `round-10/frontend-tests.log`、各 result/log、`turn-tools-02.log` |
| Git 输入/保护 | 380 路径再次从 index 导出，逐 bytes/SHA 与正式冻结源码相同；重叠两文件的原有 6/9 条变更内容及顺序不变，且当前工作区字节等于已验 working-view | `main-index-and-residual-proof-round-10.json` |

占位的 `coverage_status` 保持 unknown，表中的占位不是“有法律依据的完整回答”。Windows standalone 复制 EPERM 仍属部署包缺口；前端由控制器终止单列，退出 1 不冒充自然退出。对话串行仅限当前单 worker，也不保证数据库不可用时能够补偿。正式替身/离线 BGE 不证明真实模型、法律结论或生产安全。

2026-10-08 17:44 保护检查退出 0：四处非重叠原有文件、真实配置/数据库保护项、旧候选 369 源/53 工具/5 报告与共享 distribution 列表未漂移。它不包含整个 venv 逐字节冻结；六处残留均不进入本轮提交。没有 push、真实库写入、服务器选择或部署动作，已有 3021 服务未操作。

下一阶段计划为主仓 `docs/superpowers/plans/2026-10-08-release-readiness-preflight-plan.md`：只读整理原有六处修改、当前对象风险及发布前置，并将真实模型/升级/push/CI/数据库/部署分别留作授权门。不通过本轮本地验收续签旧风险或将模型来源 PARTIAL 写成关闭。

### 封口与提交记录

为避免“报告写完扫描通过、再改报告导致扫描对象不同”的自引用，本文件固定为**提交前技术验收报告**。本轮报告镜像和 manifest 先冻结，随后批准扫描器生成 `evidence/delivery-final-scan.json`；扫描只能证明所列当前九值/五形态/选定交付文件，不能证明所有 Git 历史安全。扫描与最后提交摘要是独立 sidecar，不声称它们被自身扫描。

所有提交门继续有效：最后扫描必须退出 0、暂存路径仅为 25 个产品/测试和本轮三份文档、原有六处保留、`git diff --cached --check` 通过，才执行此前明确批准的本地 commit。**实际 commit 编号、扫描结果、最终保护和阶段状态**只以 `C:/Users/33393/Desktop/fazhi-main-integration-20261007/evidence/delivery-closure.json` 为准；若它不存在、失败或与当前 HEAD 不符，本文件不构成已提交证明。后续助手只读查封口，不重用已有独占运行标签。

自审结论：正确原因红/绿、实际执行集合、独立期望、双轴复核、当前输入绑定及已知限制均已记录；新技术通过未覆盖旧失败、不等同上线。提交记录留在 sidecar，避免在提交后修改本报告制造新的未提交内容。

## 最后扫描的正控分类修补（2026-10-08，提交仍未执行）

首次最终扫描实际退出 1，保存在 `evidence/pre-round-11-delivery-final-scan.json`：2697 选定文件、九项当前值全部零命中且无缺失，五形态正控有效；唯一未分类项为已保存的 round-08/09 旧 scanner 各一条合成私钥头正控。没有把这次退出 1 改报为 0。

最小工具修补只扩充已知正控分类：明确 round-08/09/10 归档路径，指定形态且一次命中，完整 bytes/SHA 必须匹配其原冻结清单；未知路径、其他形态、多次命中、缺清单或漂移均不获豁免。没有忽略整个 evidence 目录，没有减少扫描目标或真实值判据。

`red-scanner-archive-01` 正确原因 1 失败、124 通过、3 subtests；新 `green-scanner-archive-02` 为 125 通过、3 subtests、退出 0。复核曾指出同时错长度/哈希的负控不够：现分别等长改一字节、正确哈希但错长度；内存 AST 分别移除对应条件时，实际目标各 1 失败/0 error，证明两判据都可被测试捕获。细节与原始 JUnit 在 `evidence/scanner-archive-mutation-proof.json`；没有在磁盘留削弱版工具。

Spec/Standards 两路都重新核对，测试意见已闭合，补充 0 剩余阻断，记录在 `reports/a-boundary-independent-review-20261008.md`。由于工具字节发生变化，为保持执行条件唯一来源，保存并逐字核验 round-10 的 380 源/53 工具/6 报告和清单，再以 round-11/control-13 新冻复验。归档报告首次复制碰到 singular/plural 清单名错误，已单独修正并核验实际 6 份，不把第一次空集合当成功。

当前 380 源路径与 full-04/round-10 完全相同，后端全量未重复运行，不冒充新跑；新 53 工具已冻结。round-11 正在执行，最终扫描与提交仍须在新正式验收和报告再封口后完成。

## 最终新轮技术裁定（2026-10-08，提交前）

`PY -I -B verify_final.py round-11` 已实际退出 0，`bounded_integration_pass=true`；当前 380 源/53 工具/18 种子与 round-11/control-13 两腿快照一致。8 会话/44 消息、6 占位的 API/SQL 一致、计数及严格配对全通过；两 API/四浏览器取消、8 轮/16 消息的实际摘要及 2 个摘要请求完成均通过。control-13 原生自然退出 0，async/sync SDK 最终打开数为 0/0，无额外 close 干预。

最新前端为 83 测试、tsc/build 退出 0，guard 为 110 测试通过；根级收尾契约包括在独立工具 `green-scanner-archive-02` 的 125+3 结果中。full-04 的 1852/10/18 仍适用于字节完全相同的产品源码；未把新的正式轮当作后端全量重跑。原有六处残留、原配置/库、只读候选及共享 distribution 保护再次在 18:17 检查通过。

旧 round-10 通过状态与扫描退出 1 原样保存，不重命名作新结果。可还原的最终暂存差异将保存为 `evidence/local-commit.patch`，旧文档版 patch 另留。报告先冻结、最终扫描后本地提交；最后裁定及实际 commit 仍由独立 delivery-closure 记录，本文不预写未执行的扫描或提交成功。
