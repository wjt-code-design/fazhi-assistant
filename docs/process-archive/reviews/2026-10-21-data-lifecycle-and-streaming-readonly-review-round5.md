# 法智：数据生命周期、Agent 降级与流式显示只读审查（第 5 轮）

日期：2026-10-21（北京时间）。本文件是本轮独立新建报告。

## 1. 主要发现

| 编号 | 优先级 / 置信度 | 已确认行为 | 与旧报告的关系 |
| --- | --- | --- | --- |
| V5-01 | P2 / 高，函数与真实内存数据库复现 | 删除会话后遗留 Agent 任务；会话数字 ID 复用后，旧任务仍能被恢复 | 给旧 H-04“run 无回收”补充删除与身份复用的独立失败场景 |
| V5-02 | P2 / 高，生成输入复现 | Agent 澄清恢复后技术降级，原问题和前轮已确认事实未传给普通回答链路 | 新的降级边界；与 H-03 历史缺失相邻，建议关联处理 |
| V5-03 | P2 / 高，实际 TS 函数复现 | 金额范围中的“元 / 万元”被替换成字面 `$3` | 本轮新增发现 |
| V5-04 | P2 / 高，实际 TS 解析器及 hook 复现 | 合法正文包含 `[DONE]` 时，整帧被丢弃 | 本轮新增发现 |

另有一项**仅内部服务恢复可达**的覆盖状态不一致，以及两项边界观察，列在第 6 节，不与以上四项混计。

本轮发现明确的功能与数据边界缺陷，不能给出这些路径已正确的结论；本轮也不作全项目或部署验收结论。

## 2. 审查对象与方式

- 源目录：`C:/Users/33393/Desktop/ai-legal-helper`，主目录 HEAD 为 `e6abf681c0fecc82bbe4869dc0cdda64bfbecdc7`。上一轮使用的候选目录 HEAD 为 `69577e9…`，本轮证据以主目录新快照为准。
- 冻结时间：`2026-10-21T10:20:56.0774454Z`。复制 112 个 Python / TypeScript 源文件到外部证据目录，逐文件记录 SHA-256。
- 两名子代理分别审查 Agent 保存、恢复与终稿事务，以及前端 SSE、消息渲染与历史恢复；主审负责删除数据的生命周期、证据核对、去重和本报告。
- 动态观察使用冻结源码：Python AST 提取实际函数，接入 SQLAlchemy 内存 SQLite；TypeScript 在内存转译，配合合成 fetch 和轻量 React 状态替身。
- 未运行项目测试套件、启动服务、访问真实业务库、读取 `.env`、调用模型或修改业务源码。外部证据目录保存观察脚本与输出。本轮仓库交付物仅为本报告。

独立判据为：删除后的旧任务不能重新归属于新会话；技术降级必须保留已经获得的用户事实；显示不能改变金额单位；结束哨兵必须与合法正文区分。后两项直接比较输入文字和输出，不用模型评委判定。

## 3. V5-01：删除后残留的 Agent 任务会随会话编号复用重新接上

### 位置与原因

- [models.py](C:/Users/33393/Desktop/ai-legal-helper/backend/models.py:20)：`User → Conversation → Message` 有 ORM 级联；`Conversation` 与 `User` 都没有指向 `AgentRun` 的删除级联。
- [AgentRun](C:/Users/33393/Desktop/ai-legal-helper/backend/models.py:132)：run 指向用户、会话，但没有数据库 `ON DELETE` 行为。run 自己到 steps、evidence、claim_checks 的级联，仅在 run 被删除时生效。
- [删除会话](C:/Users/33393/Desktop/ai-legal-helper/backend/main.py:2808)与[删除账号](C:/Users/33393/Desktop/ai-legal-helper/backend/main.py:2890)：都未清理这些 run。账号删除明确清理 Feedback / AnalysisRun，却遗漏 Agent 表。
- [load_owned_run](C:/Users/33393/Desktop/ai-legal-helper/backend/agent/repository.py:84)：仅比较 run 上的 `run_id / user_id / conversation_id`，没有核验对应会话的稳定身份。
- [恢复入口](C:/Users/33393/Desktop/ai-legal-helper/backend/agent/controller.py:344)使用上述查询。[聊天包装器](C:/Users/33393/Desktop/ai-legal-helper/backend/main.py:1805)的 `created_at` 防编号复用检查仅用于非 Agent 恢复请求，不能封住此场景。

### 直接观察

使用真实模型定义和真实删除函数，建立一名合成用户、一个会话、一个待澄清 run，以及各一条 step / evidence / claimcheck。观测到内存 SQLite `PRAGMA foreign_keys = 0`；项目 [database.py](C:/Users/33393/Desktop/ai-legal-helper/backend/database.py:14) 没有启用外键执行的连接设置。

```text
删除会话后：conversations=0，messages=0
            agent_runs=1，agent_steps=1，agent_evidence=1，agent_claim_checks=1
新建会话： id=1，与被删会话相同
携带旧 run_id / version=0 / conversation_id=1 恢复：成功
结果：旧问题 SYNTHETIC_PRIVATE_OLD_CASE 仍在，新增本次事实，状态 planning / version=1
```

这些“1”来自人为建立的小样本，**不是生产数据库残留数量**。账号硬删除的另一独立样本同样留下四类 Agent 记录；Feedback / AnalysisRun 在该路径按现有实现被清除。

### 影响、条件与限制

同一账号在两个页面中使用时，旧页面可保留 SSE 已返回的 run 标识与版本；另一个页面删除最高编号会话并新建会话后，新请求仍可能把旧案件状态接到新会话。已执行的是实际恢复函数与存储层，未做浏览器或完整 HTTP 验收。

另观察到账号与会话数字 ID 都复用时，旧 run 能被新的 ID 组合加载。该情形仍要求调用方知道旧 run UUID；**没有证明新用户可以猜出 UUID 或看到其他用户数据**。旧 JWT 冒用属于之前 R01，本项不重复宣称为新的 JWT 漏洞。

Feedback 快照在“仅删除会话”路径仍保留，这是现有保留策略观察，需另定留存口径，未一并认定为必须删除的缺陷。核心问题是遗留 run 仍具有恢复资格。

### 最小修复方向

在会话、账号删除事务中明确处理所属 AgentRun 及子记录；若业务要求保留审计资料，应保留稳定的删除身份或终止标记，使其永久不能恢复到新会话。不要只用定时清理作为防复活边界，也不要单独打开 SQLite 外键就认为完成：现有外键没有级联策略，可能改成直接阻断删除。

验收至少覆盖：删除最高编号会话后再创建、旧页面带旧 run 恢复、账号删除及数字 ID 再利用、其他账号拒绝恢复。媒体回收的既有修复继续沿用。

## 4. V5-02：澄清恢复后的技术降级遗失已收集事实

### 位置与调用链

[main._resume_bootstrap](C:/Users/33393/Desktop/ai-legal-helper/backend/main.py:805)只把争点问句和**最新回答**拼成 query，同时把 `summary / recent / recent_messages` 设为空，未投影 `state.user_question` 或各争点的 `facts`。

[恢复请求](C:/Users/33393/Desktop/ai-legal-helper/backend/main.py:1864)先将最新事实保存进 run，随后继续执行 Agent；技术失败允许回退时，[main.py:1923](C:/Users/33393/Desktop/ai-legal-helper/backend/main.py:1923)把这个缺少事实的 bootstrap 交给 `fallback_to_fast_path`。后续实际 `prepare_fast_path → _build_messages` 消费的也是同一份不完整输入。

### 直接观察

合成持久状态包含：

```text
原问题：借款本金为10000元，能否要求偿还？
前轮确认事实：双方约定月利率百分之一
当前争点：借款是否应返还
最新回答：借条由借款人签名
```

通过实际 `_resume_bootstrap → fallback_to_fast_path → prepare_fast_path → _build_messages`，检索输入只剩：

```text
原法律争点：借款是否应返还
用户补充：借条由借款人签名
```

生成模型的消息输入同样不含本金或前轮利率事实。检索适配器使用空结果，避免用外部语料或模型推测来掩盖输入缺失。

触发采用 `PLANNER_PARSE_ERROR`：它在 [routing_metrics.py](C:/Users/33393/Desktop/ai-legal-helper/backend/routing_metrics.py:15) 的允许技术降级集合中，实际 controller 的格式解析失败分支可产生该原因。此处模拟降级原因，未执行真实 Planner 故障或真实模型回答。

### 影响与最小修复方向

用户已经提供的信息未传到降级后的检索与生成端。当前证据证明事实缺失，**不证明真实模型已经给出某个具体错误结论**；争点问句若碰巧重复了相关事实，个别事实也可能偶然保留。

从持久状态构造受控事实投影，保留原问题、已确认事实、仍未知事项及本次回答，并维持现有法律基准日。优先修复这个共享降级入口，不需要重构整个 Agent。不能把“未知”补写成已确认事实，也不应把内部工具原始载荷直接塞进提示词。

建议与旧 H-03 关联，但分别验收“历史恢复”和“同一请求技术降级”，避免只修历史 UI 后漏掉这条生成输入路径。

## 5. V5-03 与 V5-04：显示与协议处理改变了回答

### V5-03：金额区间单位丢失

位置：[annotate.ts:138](C:/Users/33393/Desktop/ai-legal-helper/frontend/lib/annotate.ts:138)，引号内同形于 [annotate.ts:37](C:/Users/33393/Desktop/ai-legal-helper/frontend/lib/annotate.ts:37)。金额范围正则只有两个捕获组，单位是非捕获组 `(?:万元|万|元)`，替换字符串却引用 `$3`。

实际 `renderAnswer` 输出去掉 HTML 标签后的文字为：

| 输入 | 可见输出 |
| --- | --- |
| `赔偿100至200万元。` | `赔偿100-200$3。` |
| `赔偿100-200元。` | `赔偿100-200$3。` |
| `「赔偿100-200元」` | `「赔偿100-200$3」` |

[MessageHtml](C:/Users/33393/Desktop/ai-legal-helper/frontend/components/chat/MessageHtml.tsx:23)调用同一渲染器，因此实时与历史回答均受影响；这是显示损坏，未发现原始数据库正文被同步改写。

最小修复是两处保留并正确引用单位；验收对比渲染后的文本语义，覆盖引号内外、元与万元、小数及不同连接符。现有 `frontend/tests/annotate.test.ts` 的金额用例主要检查高亮类是否出现，这不能证明单位未被改变。

### V5-04：正文里的 `[DONE]` 被当成结束标记

位置：[sse.ts:20](C:/Users/33393/Desktop/ai-legal-helper/frontend/lib/sse.ts:20)，条件 `line.includes("[DONE]")` 会过滤**任何包含该字符串的整帧**。

合法 JSON 帧：

```text
data: {"type":"token","content":"合同将 [DONE] 定义为验收完成标记，收到后仍须付款。"}
```

实际 `parseSSEFrames` 返回 `frames: []`。继续给实际 `streamChat / useChatStream` 输入合法 `final` 和独立结束帧后，观察到显示内容变成“服务暂时不可用，请稍后重试；紧急法律问题请咨询律师。”，覆盖状态仍为 `full`。

[Agent 事件序列化](C:/Users/33393/Desktop/ai-legal-helper/backend/agent/chat_integration.py:87)把完整答案放在单个 token 事件中，这使整答案丢失可由这一帧过滤造成。普通流也可能丢一个片段；含该字符串的澄清事件还可能连带丢失恢复标识。

最小修复：取出 `data:` 的帧体后，只有整个帧体严格等于 `[DONE]` 时才识别为结束哨兵。保留正文、JSON 字段内的同名字面量。现有 `frontend/tests/sse-frame.test.ts` 覆盖独立哨兵，未覆盖正文中的同形字符串。

协议输入为合成数据，hook 为轻量状态替身；证明解析和串行状态处理，不代表已经跑过浏览器或真实模型。

## 6. 有限制的发现与去重

### O5-01：部分交付失败后，内部重跑会残留旧覆盖状态

已执行实际服务函数与内存 SQLite：[service.py:603](C:/Users/33393/Desktop/ai-legal-helper/backend/agent/service.py:603)仅在本次 `uncovered` 非空时写覆盖检查点。首次 partial 的检查点成功后，注入终稿 Message flush 失败，run 保持 `drafting/v1/uncovered=b`。通过内部 `execute_agent_request(run_id=...)` 再执行，合成 writer 此次覆盖全部争点：

```text
实时结果 completed / coverage=full / uncovered=[]
持久状态 completed / v2 / uncovered=b
历史投影 coverage=partial
```

置信度高，但公开恢复入口要求 `WAITING_USER`，普通 UI 不能直接重启 `DRAFTING`，因此单列为**内部恢复契约缺陷 / P2 候选**。处理恢复能力时应让本次覆盖结果无论空或非空，都与持久状态一致；不要为消除这条观察而额外开放公开重跑入口。

### O5-02：待澄清会话切回后无法续跑——旧 H-03 的新证据

实际 TS 串行观察：收到澄清时保存 `pendingAgentRun={runId, stateVersion}`；选中同一历史会话后，[useConversations.ts:60](C:/Users/33393/Desktop/ai-legal-helper/frontend/lib/hooks/useConversations.ts:60)清空它，详情接口也没有返回待澄清任务；用户下一次补充仅发送 `content / conversation_id`，不带续跑字段。

此项与 [旧 Agent harness 审查 H-03](C:/Users/33393/Desktop/ai-legal-helper/docs/agent-harness-audit-20260929.md:124) 同源，保留为修复时可用的复现证据，不另计新增问题。

### O5-03：缺少结束帧的干净 EOF

合成“已有半截正文，随后 reader 干净 EOF”，客户端保留半截并结束 streaming。尚未证实现役代理实际产生此种无异常的提前 EOF，不列入已确认部署缺陷。它与旧 R15 的模型重试污染边界不同，可作为协议专项后续项。

### 同时观察到的有效防护

Agent 旧版本 CAS 被拒且不增加 step；相同终稿精确重放仅保留一条消息与一条 finalize step；外用户终稿提交被拒；终稿 flush 失败时状态、版本、step、会话计数共同回滚。这些结果只覆盖对应合成场景，不抵消本轮缺陷。

## 7. 证据与复现

统一证据目录：`C:/Users/33393/.codex/visualizations/2026/10/18/01a14fe1-dd41-7e83-a8f6-c4c2d27b6be7/fazhi-data-stream-review-round5`。

| 材料 | 内容 |
| --- | --- |
| `source-manifest.json` / `snapshot-meta.json` | 112 个冻结源文件指纹、HEAD、时间 |
| `source/` | 源文件快照，不含环境密钥或业务数据库 |
| [deletion-evidence/observations.json](C:/Users/33393/.codex/visualizations/2026/10/18/01a14fe1-dd41-7e83-a8f6-c4c2d27b6be7/fazhi-data-stream-review-round5/deletion-evidence/observations.json) | 删除前后计数、ID 复用与旧 run 恢复 |
| [agent-state-evidence/probe-output.json](C:/Users/33393/.codex/visualizations/2026/10/18/01a14fe1-dd41-7e83-a8f6-c4c2d27b6be7/fazhi-data-stream-review-round5/agent-state-evidence/probe-output.json) | 降级输入、内部覆盖重跑及事务正向控制 |
| [frontend-stream-evidence/observations.json](C:/Users/33393/.codex/visualizations/2026/10/18/01a14fe1-dd41-7e83-a8f6-c4c2d27b6be7/fazhi-data-stream-review-round5/frontend-stream-evidence/observations.json) | 正文哨兵、金额、历史恢复、EOF 和正常流对照 |
| `source-drift.json` / `completion-check.json` | 交付时源漂移与旧报告指纹核对 |

执行过的最终命令如下，均退出 `0`，表示观察脚本执行完成，**不是产品测试通过**：

```powershell
$evidenceRoot = 'C:/Users/33393/.codex/visualizations/2026/10/18/01a14fe1-dd41-7e83-a8f6-c4c2d27b6be7/fazhi-data-stream-review-round5'
$pythonRuntime = 'C:/Users/33393/Desktop/ai-legal-helper/backend/venv/Scripts/python.exe'
& $pythonRuntime -B "$evidenceRoot/deletion-evidence/observe.py"
& $pythonRuntime -B "$evidenceRoot/agent-state-evidence/probe.py"
node "$evidenceRoot/frontend-stream-evidence/observe.cjs"
```

Python `3.11.0`、SQLAlchemy `2.0.51`、Pydantic `2.13.4`、SQLite `3.38.4`；Node `v24.18.0`，使用项目已安装的 TypeScript。它们不等于当前生产容器的完整依赖闭包。

Python 两份证据脚本首次运行都曾遇到 AST 隔离环境中的 Pydantic 前向类型未重建，补充 `_types_namespace` 后成功；这是证据脚本问题，不列为产品缺陷。未为本轮安装依赖。

关键 SHA-256：

| 源文件 | SHA-256 |
| --- | --- |
| `backend/main.py` | `f3f6d6ec9793f43d9c3f05c02630f5f69f827f99e00bc5cd8a6ee69800cde993` |
| `backend/models.py` | `2808937f67b61c0a1d66f1d34c905f741297d83849fcde91d102a240b586f5d4` |
| `backend/agent/repository.py` | `cb76fb560b9e0bdd8ceca7db6e97ee76f4af9454074df88936942120ca7457a5` |
| `backend/agent/service.py` | `8df840f54a4bece93b2a7969eb9f7cffe358423af7967416cc9a7afa60b02c54` |
| `frontend/lib/annotate.ts` | `36ef661f7ed87a4a40ca1811cc5b9505a069616c41a0b4061de6c21dd59f06a0` |
| `frontend/lib/sse.ts` | `791cc56ab4d450b47a594016e8ea39c210117b44a1bb7f91bac139b45092c29c` |

修复助手应先对照当前文件指纹与快照。证据脚本消费冻结副本；修改正式源码不会自动改变这些观察脚本的结果。

## 8. 可直接转交修复助手的提示词

```text
请先独立复核本文件 V5-01～V5-04，再实施必要的最小修复。报告针对主目录
e6abf681c0fecc82bbe4869dc0cdda64bfbecdc7 的冻结源码；先核对当前分支、他人改动和文件指纹。
不要回退其他助手已完成的改动，不要机械地把旧快照覆盖回项目。

优先确认 V5-01：删除会话或账号后，旧 Agent run 不能因数字 ID 复用而恢复到新身份。
级联、软删除或稳定身份校验应服从现有留存规则，并在同一事务保证一致性。
仅加定时清理或仅开启 SQLite 外键均不能作为完整修复。

V5-02：在 Agent 恢复后技术降级的真实入口检查最终检索和模型输入，确保保留原问题、
既有确认事实、未知事项、本次回答及法律基准日。不要把未知事实改写成确定事实。

V5-03：检查两个金额范围替换分支，渲染后的数字及单位要与原文等义。
V5-04：只识别完整独立的结束哨兵；正文 JSON 内的 [DONE] 必须保留。

O5-01 目前仅内部服务恢复可达，请如实标明范围；O5-02 关联旧 H-03，避免重复建票；
O5-03 尚缺真实提前 EOF 的入口证据。不要把这些边界改写成已发生的生产故障。

验证使用隔离数据和针对性的行为用例；冻结证据脚本只证明旧快照，需让验收真正执行
修复后的代码。分别记录复现前后输出、涉及文件、限制与未关闭项。
不顺带重构 Agent 架构、不换依赖、不部署；如另有用户明确授权则按其范围执行。
结果另开修复记录文件，不改写本报告或历史审查报告。
```
