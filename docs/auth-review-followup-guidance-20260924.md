# 代码审查后续工作指导建议与优化方向

基准日期：2026-09-24

> **2026-09-25 接手更新**：以下各节保留其标注日期的审查记录，不应将旧反例状态当作当前代码状态。
> 最新窄修复与复现命令见[接手汇报 §8](./progress-handoff-report-20260925.md)：
> R15-4 已有提交；R15-2 再补同子句多日期歧义保护；QA 共享入口再补有效版本日期校验。
> 本轮相邻回归 224 passed，不代表全仓验收。W1 已证实高分直返重复查条，延迟未复测，暂不加缓存。
> 现有 `import_laws.py --validate-only` 已能在连接知识库前整批校验输入；下发产物生成、需读库的 `--dry-run` 验证与真实入库是后续不同步骤。业务日期时区不由 UTC 存储惯例决定。
> 真实库写入、部署、时区改动继续不在本轮范围；不清理他人工作，只按指定文件清单提交，不推送。

适用范围：接续 AUTH-2 / AUTH-3 本地修复、补齐历史法查询的未闭出口，并复核旧代码审查报告的全部非 AUTH 项（V1、S1、费用与时效、B1–B3、E1–E4、R15-1–5）。本轮非 AUTH 复核结果见第 8 节。
依据：[进度报告](./progress-auth-review-20260924.md)、[代码审查报告](./code-review-report-02e3851-20260918.md)。

> 本文是后续工作的路线建议和已注明边界的定向审查记录，不构成全仓或线上验收。服务器尚未选择；本阶段只在本地隔离环境做审查、测试和经确认后的实现，不做部署、迁移线上数据、发布、线上重启或服务器配置变更。

## 1. 当前状态与边界

- 当前分支为 master，核对时 HEAD 为 817e29b。进度报告记录 AUTH 代码变更在 065038c、974e3da；报告称未 push、未部署。不要由本地提交推断远端已同步。
- 用户已确认的是聊天请求的契约：普通用户可传 law_as_of 做历史查询，默认开启；配置显式关闭时，带日期的请求返回 503 和可理解提示，不得静默改用当日。当前历史查询审计字段为 user_id、conv_id、law_as_of，不记问题原文；这不代表其他日志均无敏感文本。case_domain 仍属于可信评测输入，默认关闭。两个法条 GET 端点是否也接收日期尚待单独决定（第 3 节）。
- 最近一次记录的定向 AUTH 套件为 237 passed / 10 skipped / 59 warnings，exit 0；筛选后的全量套件为 1409 passed / 12 failed / 25 skipped，exit 1。本指导文档第一版说这 12 项"只是有初步环境归因、尚无基线对照"——**该前提已在 09-25 被兑现**：同一容器、同一 `--ignore` 口径下把 22 个改动文件回退到父提交 `b7d96f5` 的字节再跑全量，12 条失败 node id 与改动后逐字节相同（diff 零字节），通过数 1378 → 1409。⇒ 可以称其为**既有失败**；但仍不得报成全绿，也不得据此声称线上可用。
- 最近的静态检查记录为 ruff、mypy 通过；这不替代全量测试或端点动态覆盖。本文第一版记的"Docker Linux daemon 不可用"已过期——09-25 实测 daemon 可用、隔离容器 `codex-auth-review-test` 只是 Exited 状态，`docker start` 后即可复现容器读数（本轮的基线对照就是这么补上的）。本轮非 AUTH 定向测试使用项目 conftest 的进程私有数据库与 Chroma 目录。不要为了补数字在宿主仓库直接跑可能触碰 .env、app.db 或 chroma_db 的全量测试。
- 当前工作树有大量已修改/未跟踪文件，本任务不推断其归属；可见路径包括 dispatch-output、.qoder、caddy_config、caddy_data、backend/.ptmp-s4-run2、outputs 等。它们不因本指导文档而获得清理授权；严禁 git clean、reset、批量 checkout、删除临时目录或把未确认的改动纳入提交。未跟踪的 git 修复 runbook 也先保留，不擅自 add。

## 2. 证据与报告口径（文档任务，不阻塞独立代码票）

更正报告时把“已实现、已验证、仍待决、未验证、未部署”分开，避免下一个执行者把勘误和未闭项读成完成状态。

1. 修订进度报告摘要：票面工作已本地完成，但 /api/feedback 和两个法条 GET 端点仍未收口；全量测试执行结果为 exit 1，不得标成全绿。删去与待办表不符的“仅三项待决”。更正 `04:0x` 时间戳；不能核实的时间直接标为未知。
2. ✅ 复现清单已改：进度报告附录那段 md5 对齐命令原先从 `git show --numstat HEAD` 取文件，而本文入库后 HEAD 是 docs-only 提交 ⇒ 该命令返回 0 个文件、循环一次不跑却"看起来无差异"（一台会产出假"已对齐"的空转仪器）。现改为按 `git diff --name-only <代码父提交> HEAD -- backend` 取范围，并加了 `test -s` 空清单即失败 + 本地缺文件即失败。
3. 12 个全量失败：✅ 基线对照已于 09-25 补做（`b7d96f5` 字节 vs 当前字节，失败 node id 逐字节相同）⇒ 现可称"既有失败"，条件已满足。
4. 未得到明确授权前，不 amend、不新建提交、不 push；不顺手 add 未跟踪的 runbook 或其他工作区内容。

完成标准：摘要、待办和测试状态一致；复现清单非空且可核对；未归因的失败不写成通过。更正文档不作为其他代码票的前置审批。

## 3. 需要产品 Owner 先决定的行为

下面两项会改变数据模型或公开 API，不应由执行助手自行猜测。建议仅供 Owner 决策，不等同于已获批准；两项互不依赖。

| 决策 | 可选方向 | **09-25 Owner 已裁决**（本文第一版的建议已作废，理由见右） |
|---|---|---|
| /api/feedback 来源候选如何避免错版直返 | A. 为可直返的反馈建立可信答案关联和版本来源；B. 暂不让 `feedback:` 来源答案走 QA 直返；C. 接受残余风险并明确告知 | **都不选，改为"按证据形状整类判定 + 写侧停发候选"**。本文第一版推荐 B，实测两处使它不成立：① B 只闭一个出口——同一条记录仍被 `main._build_messages` 以"此前已确认的问答（可优先参考）"注入模型，不经 `law_as_of_basis`、不经时效校验，那是第二个出口；② "覆盖已采纳条目"是**潜在**而非既成——真实库里 `feedback:` 前缀 0 条（`qa_pairs` 279、`qa_pairs_te4` 21、`qa_candidates` 759 行均为 0），所以既然没有历史包袱，按形状整类判定比按前缀点名更便宜也更稳。落地判据：`evidence` 含≥1 条 `source`+`article` 都非空的引用 **且** `law_as_of_basis` 非空 ⇒ 才可参与生成；挂在产生处 ⇒ 两个出口一起关。A 方案（改 schema）今天不需要——本文与进度报告原先都断言"闭它必须改数据模型"，那是错的 |
| /api/law 与 /api/law/search 是否支持历史基准日 | A. 增加可选 law_as_of 并复用同一 503 闸口；B. 仅对有 run 快照的 Agent 引用提供历史回查，其他路径明确不支持 | **暂缓，两案都不做**，前置改为一张**语料数据票**。理由：生效语料 10266 条 `effective_from`/`effective_to` 全空、`status` 全为"现行" ⇒ 现在加 `law_as_of` 不改变任何一个查询结果，也换不来一个 404 的消失（历史引用 404 的真因是库里没有已废止法律的文本，而不是没传日期）。在不改变任何行为的接口面上先扩公开 API，正是本文 §5 自己反对的那类事。废止法文本可从外部源取得（实测元典按 `validity_status=失效` 可检到《合同法》本体及其解释一/二） |

成本限额与 HMAC 暂不作为开工决策：现有请求频率上限先保持；只有观测到历史请求成本问题并与服务商账单校准后，才另开限额票。**09-25 补充事实供校准**：由于上表第 ② 条（真实语料无日期轴），"显式基准日把命中打成未命中"这条成本路径今天在检索层**不成立**——限额的紧迫性与"取数空转"绑定，先不动。SHA-256 + 长度不能称作匿名化；只有日志读者/用途扩大或发现具体成员判定风险时，才单独评估 HMAC。不为这两项预先新增框架、配置或指标系统。

## 4. 最小执行路线（独立票，不按字母串行）

### AUTH-A：反馈沉淀边界 ✅ 已落地（09-25），方式与本节第一版不同

本节的原推荐（在 `_qa_direct_return` 读侧拒绝 `feedback:` 来源）已被 §3 的裁决取代并已实现。落地形态：

- 判据 = `retrieval_core.qa_provenance_verifiable`：`evidence` 含至少一条 `source` 与 `article` 都非空的条文引用，**且** `law_as_of_basis` 非空。
- 挂两处：产生处 `request_bootstrap.prepare_fast_path`（⇒ 直返与 `_build_messages` 的 prompt 注入一起关）+ 出口 `main._qa_direct_return`（有评测探针直接构造 `pre` 调它，那条路径绕过产生处）。
- 形状解析 `cited_articles` 与既有时效护栏共用，不留第二份形状知识。
- 写侧：`/api/feedback` 不再创建沉淀候选；`feedbacks` 表台账不变。
- **本节第一版没写、而实现时才发现的一条**：判据刻意**不**塞进 `knowledge_service.search_qa`——`qa_seeds.py` 与 `scripts/gen_qa_corpus.py` 拿 `search_qa(threshold=0.99)` 做幂等去重，塞进去会把策略外溢到写侧语义。

验收按"两个出口各自钉被比对象"执行：直返腿断言返回 `None`；prompt 腿断言最终 messages 里不含"此前已确认的问答"那一段（而不是断言 `qa_hit is None` 这类中间量）。真库判据读数：`qa_pairs` 279→277、`qa_pairs_te4` 21→0。

**AUTH-A-3 = 票 W1（09-25，Owner 裁"对称收口，判据上提到产生处"）补的是本节第一版只闭了一半的那一半**：
第五道判据只管**形状**（引用给不给得出），而"引用的那条文今天还在不在库"这步**时效**判定当时仍**只写在**
`main._qa_direct_return` 里 ⇒ 一条引用了已删条目的记录照样进 `pre["qa_hit"]`，被 `_build_messages`
以"此前已确认的问答（可优先参考）"递给模型。落地形态与"抄一份循环"的区别是裁决里点名要的：
判据本体抽成 **一个** 函数 `retrieval.qa_citations_in_kb`（住在 `retrieval`，因为它要碰库；
`retrieval_core` 是全仓唯一的纯谓词层），直返出口与产生处调**同一个对象**，
并由 `tests/test_qa_citation_gate_symmetry.py` 用 `main.qa_citations_in_kb is retrieval.qa_citations_in_kb`
+ `inspect.getsource` 双向钉住（内联第二份 ⇒ 红）。副作用是好的：替身现在只需打
`retrieval.exact_article_lookup` 一处就能同时决定两个出口的行为。
代价实测（真实库只读、n=9 中位）：每次核验 ~80 ms/条引用，**新增面只在 0.7≤score<0.92 的"仅注入"记录**
（直返那条本来就在付）。过程读数、七条变异与三条仪器自错记在 `docs/progress-auth-review-20260924.md` 第 11 节。

**AUTH-A-2（09-25 同日，Owner 裁 A 案"补写入口径"）补的是本节第一版没预见的一格**：判据上线时**全仓没有任何生产者**写 `law_as_of_basis`（存量值来自 09-20 一次性回填）⇒ 新沉淀的语料永久过不了这道门，零模型直返会静默衰减。修法落在写侧单一闸口 `add_qa_pair`：调用方未给基准日时落**当日（UTC，与 `QaCandidate.created_at` 同一个钟）**，人工采纳是唯一例外（`decide_candidate` 传候选产生日——**采纳≠产生**）。同一批还把"新拦截不可观测"补掉（`qa_provenance_refused` 结构化告警 + 白名单登记），并把三处与实测不符的注释读数改对。过程与踩坑（含那条被本地午夜撞出来的时钟差）记在进度汇报第 10 节 ⑧。

遗留（本票**不**声称已解）：人工纠错入库这条通道随写侧关闭而暂对消失。本仓不存在"管理员手工录入 QA"的端点（`/api/admin/qa/{cand_id}/decision` 只能对已有候选通过/驳回，`decide_candidate` 逐字透传 `evidence`），所以这不是"改走别的路"。要恢复须另开票：录入时要求条文引用**并**显式声明适用基准日。

### AUTH-B：两个法条 GET 端点 ⏸ 暂缓，前置改为语料数据票

本节第一版说"若 Owner 批准，两个 GET 端点增加可选日期并复用现有闸口"。09-25 实测改判：真实语料没有任何日期边界与废止版本（§3 第 ② 条），先加参数是往一个不会改变任何行为的面上扩公开 API。

语料数据票的范围与纪律（Owner 定的分工）：取数与填 `status`/`effective_from`/`effective_to` 归执行助手；**新旧法衔接日取发布日还是施行日、哪部法替代哪部**这类判断一律出成"待确认清单"交 Owner 或法务签字，**签过才入库**。第一步只做可行性验证：外部源的法规详情接口给不给逐条全文（本项**未验**，只验到检索侧能定位到失效的《合同法》本体）。本轮不对任何库做写操作——真实 `chroma_db` 正被运行中的 `fazhi-backend` 容器 bind mount，且 chroma 并发不安全。

数据到位后再回来评估本节：那时 `exact_article_lookup(source, article, cutoff)` 早已支持 cutoff，端点侧是十几行的事。

### AUTH-C：授权与日志的定向复核（票面已按 09-25 实测改写）

⚠️ **本节第一版有两条会让票跑空**，先改事实再开票：

1. **"导出/下载端点"和"独立 messages 端点"不存在**。全仓路由都挂在 `backend/main.py`，无 `APIRouter`/`include_router`；唯一的 `FileResponse` 是 `get_media`；消息只嵌在 `GET /api/conversations/{id}` 的响应里。按原票面去给它们造双用户探针就是"不存在的端点不造测试"这条纪律自己要破的例。
2. **`/api/chat` 的跨用户 `conversation_id` 不是 404**。归属不符时它**静默新建一条自己的会话并返 200**（`request_bootstrap` 里那一支），探针看到的行为是 200 + 新 `conv_id`。票面必须按这个真实契约写，否则会把正确行为判成缺陷。

改写后的真实覆盖面（已逐个核过归属核验，证据在进度报告第 10 节④）：`/api/conversations`（POST/GET）、`/api/conversations/{id}`（GET/PATCH/DELETE，三处都有 `user_id` 校验）、`/api/chat`、`/api/chat/file`、`/api/chat/transcribe`、`/api/media/{path}`（有路径穿越防护 + 归属校验）、`/api/law`（`run_id` 分支双端核验用户与会话）、`/api/law/search`、`/api/feedback`、以及 `/api/admin/*` 全量走 `require_admin`。结论是：**没发现"按 id 直取却不过滤归属"的用户级端点** ⇒ 这张票的价值在于用双用户跑一遍把结论钉成实测，而不是预期能查出漏洞。

日志侧本轮**只复核不改码**（Owner 裁决：改法要先把"这些日志谁会读"定下来）。除进度报告已记的 `fast_path_law_version_detail`（`answer[:200]`）之外，另发现 4 处落原文：`agent/runtime.py` 的 `detail`（**用户问句原文**，`[:300]`）、`agent/controller.py` 的 `agent_planner_raw_tail`（`[:500]`）、`agent/service.py` 的 `agent_claim_checks.claim`（`[:120]`）与 **`rationale`（无截断）**、以及 `agent_failure_detail`（异常文案是否含用户文本**未确认**）。全部受默认关闭的 `agent_enabled` 门控 ⇒ 是"启用后可触发"，不是现网故障。确认要改时单独开脱敏票，不把 AUTH-3 的 `query_sha256` 修复说成全应用日志脱敏完成。

**✅ 2026-09-25 探针已落地**（`backend/tests/test_auth_c_ownership_probes.py`，7 条 + 4 处"摘归属检查"变异各打死自己那条；静态面为 AST 扫 `main.py` 40 条路由，含 `AsyncFunctionDef`）。
本节第一版之外**又冒出两条只有真跑一遍才知道的契约**，票面若按直觉写就会产出假探针：

1. `PATCH /api/conversations/{id}` 的 `title` 是**查询参数**（FastAPI 对标量 `title: str` 的默认解释），
   发 JSON body 得 **422** ⇒ 夹具若不断言 200，后面两条改名/读取用例就是"别人根本不存在"的假绿。
2. `image_ref` 是**相对 `backend/`** 的存盘路径（`models.py:56`；`get_media` 用 `dirname(MEDIA_DIR)` 作 base），
   值形如 `media/xxx.png` ⇒ 探针写裸文件名会先撞上"非法路径 400"分支，**归属那一段根本没执行**。
   media 那条因此钉的是**执行顺序**（owned 检查先于 `isfile`），做法是让 `isfile` 一被调用就抛。

### 非 AUTH：仅处理第 8 节的未闭项（与 AUTH 票独立）

第 8 节已按当前 817e29b 对旧报告全部非 AUTH 项做代码核对和隔离定向测试。旧报告的早期固定快照结论不再直接充当当前状态；后续只对第 8 节列明的未闭项和验证缺口开票。

先确认相关开关在目标环境是否启用；当前代码默认关闭 Agent 与 R15 版本门，不能把条件性风险说成已发生的线上故障。E1 先定一个具体可测的事实关系，再决定是否扩展现有窄规则。R15-2 和 R15-4 可围绕已复现反例各开一张小票；R15-3 先核实真实语料有无所需旧法版本，再决定是否改检索。R15-1 的宽泛衔接词与 R15-5 的中文数字日期先记明示边界，是否修复由实际输入证据决定。已通过的旧反例不触发模块重设计。

## 5. 约束与不做事项

- `law_as_of` 是本次检索/回答采用的知识基准日，不等于案件事实日或时效起算日；同一请求的取数、出口和反馈不得各自重新推导基准日。
- 显式历史查询失败不得静默切到当日；只对实际缓存结果的路径检查日期隔离。来源日期由可信服务端产生，不由客户端或采纳日补造。
- 测试与宿主 .env、app.db、chroma_db 隔离；环境失败如实报告，不宽泛忽略。每张实现票优先复用现有 gate、cutoff 和测试夹具；不预设新权限框架、审计服务、缓存层或通用语义引擎。

## 6. 阶段验收门槛

每张票只验收自己改动的行为；以下条件按适用性执行，不能把无关检查硬塞进每张小票：

1. 改 schema 或公开 API 前有 Owner 明确选择；仅 schema 票需要隔离迁移测试、旧记录解释。
2. 行为票有独立于实现的正反例，覆盖本票风险；涉及用户资源的票补双用户隔离用例。非代码的口径修订不强制跑业务测试。
3. 记录定向测试的命令、源码 SHA、原始输出、跳过/失败数和退出码；执行了全量套件就如实报告全量结果，不能把既有 12 个未判定失败写成通过。集成前再做全量基线复核，不要求每张窄票都重跑全仓。
4. 对改动文件运行适用的静态检查和 `git diff --check`；不能运行的项目明确标为未验证。复核实际差异，不用“AI 已审查”替代产品/安全签认。

达到本地门槛后仍不等于可上线。部署、数据库迁移、发布、线上重启和服务器配置必须等服务器选定、另行授权，并先完成部署检查、备份恢复验证和回滚方案。

## 7. 立即待办清单（09-25 第四轮核对后重写；第一版的四条有两条已做完、一条前提变了）

1. ✅ 报告口径与"空清单复现"问题已改：12 个全量失败**已补上基线对照**，现称"既有失败"；进度报告附录那段
   从 docs-only HEAD 推导代码文件的复现清单已改为按代码提交范围取文件、清单为空即失败。
2. ✅ Owner 两项决定已下达（见 §3），且都**不**落在原推荐选项上：反馈边界按证据形状整类判定 + 写侧停发候选
   （已实现，不需要 schema）；两个法条 GET 暂缓，前置改为语料数据票。
3. ⏳ 待做，按此顺序：
   - ✅（09-25 W1）**两出口对称收口**：时效判据抽成 `retrieval.qa_citations_in_kb`，直返与产生处调同一个对象。
   - ✅（09-25 AUTH-C）双用户权限探针 7 条已落地（含 `/api/chat` 带他人 conv_id 的真实契约是 200 + 新建会话）。
   - ⏳ **语料数据票（W2）**：取数通道已由 Owner 改定为**已授权的元典 MCP**（脚本对 flk.npc.gov.cn 出网这条被
     权限层拦下，不再重试）。第一步"详情接口给不给逐条全文"**已实测：给**；`status`/施行日也给，
     **废止日期三层都给不出** ⇒ 废止日一律留空附出处、待人工签字。本轮不写库。
   - **R15-4 先于 R15-2**（两者共用同一分句函数与分隔符表；顺序反了 R15-2 的相关性判据在逗号长句上只修一半）。
   - E1 等一个真实需要阻断的事实关系样本再动；R15-3 的下一步已在 §4 并入语料数据票。
4. 服务器未选定、未获另行授权前，不做部署或线上迁移。⚠️ 补一条环境事实：本机现有一组
   `fazhi-backend` / `fazhi-caddy` / `fazhi-frontend` 容器在运行，且 `fazhi-backend` 把真实 `chroma_db`
   bind mount 进去——那是其它会话的活动，本轮未触碰；在它运行期间任何对宿主 chroma 的写都是现网形状的写。

## 8. 旧报告非 AUTH 项的当前复核（2026-09-24）

### 范围、证据与口径

本轮按与 Owner 对齐的范围逐项复核旧报告中的全部非 AUTH 项，采用代码核对和隔离定向复现。源码固定在 master 的 817e29b；backend/frontend 受跟踪代码无未提交改动。没有修改业务代码或测试，也没有运行真实模型、真实知识库或部署流程。下表“原反例通过”只评价旧报告指出的具体问题及本轮证据，不等于该模块的所有法律场景正确。

| 本轮命令范围 | 结果 | 证明范围 |
|---|---|---|
| backend/venv 的 pytest：test_review_regressions、test_limitation_calc、test_r15_version_tripwire、test_entity_precision、test_law_snapshot_review | 129 passed、3 warnings、exit 0 | 费用、时效、S1、B1–B3、E1–E4、R15 基础路径与快照回查的受控样例 |
| backend/venv 的 pytest：test_r15a_date_and_segments、test_r15b_cited_law | 18 passed、1 warning、exit 0 | R15-A/B 已写入的格式、分段与旧法引用样例；其中也有一条测试主动锁定宽泛衔接词造成的已知漏拦 |
| backend/venv 的 pytest：test_effective_window_roundtrip | 5 passed、1 warning、exit 0 | 临时 Chroma 中两版合成条文的写入、效力窗口与读取；不证明真实库含足够历史条文 |
| frontend 的 Vitest：law-card、law-card-state、law-card-api 三个文件 | 9 passed、exit 0 | hook/API 的请求复用、run 缓存隔离、失效和重试；本轮没有重跑真实 DOM/浏览器验收 |

后端命令均从 backend 目录用项目 venv 的 Python -B、pytest -q -p no:cacheprovider --tb=short 执行；显式设置 HF_HUB_OFFLINE、TRANSFORMERS_OFFLINE 为 1，LLM_API_KEY 为测试值，LLM_BASE_URL 为 test.invalid。conftest 在导入应用前把 DATABASE_URL、QUOTA_DB、CHROMA_DIR 指向进程私有临时位置。前端使用已安装的 Vitest。上述数值是本轮终端输出，原始 stdout 未另存持久文件；没有跑全量套件、现时浏览器 E2E、真实模型或真实语料验收。

复现命令（PowerShell；仅定向测试）：

    Set-Location 'C:\Users\33393\Desktop\ai-legal-helper\backend'
    $env:HF_HUB_OFFLINE='1'
    $env:TRANSFORMERS_OFFLINE='1'
    $env:LLM_API_KEY='test-key-not-for-real-calls'
    $env:LLM_BASE_URL='https://test.invalid/v1'
    $env:PYTHONDONTWRITEBYTECODE='1'
    & '.\venv\Scripts\python.exe' -B -m pytest -q -p no:cacheprovider tests/test_review_regressions.py tests/test_limitation_calc.py tests/test_r15_version_tripwire.py tests/test_entity_precision.py tests/test_law_snapshot_review.py --tb=short
    & '.\venv\Scripts\python.exe' -B -m pytest -q -p no:cacheprovider tests/test_r15a_date_and_segments.py tests/test_r15b_cited_law.py --tb=short
    & '.\venv\Scripts\python.exe' -B -m pytest -q -p no:cacheprovider tests/test_effective_window_roundtrip.py --tb=short
    Set-Location 'C:\Users\33393\Desktop\ai-legal-helper\frontend'
    node node_modules/vitest/vitest.mjs run tests/law-card-state.test.ts tests/law-card-api.test.ts tests/law-card.test.ts --reporter=dot

### 逐项结论

| 旧报告项 | 当前判定 | 当前证据和剩余边界 |
|---|---|---|
| V1 前端原文卡快速双击 | 原反例通过 | useLawCards 对同一 pending 目标复用版本，两次函数式状态切换；本轮前端 9 测通过。旧报告有修复后的受控 Edge 浏览器记录，但本轮未重跑浏览器，mock 测试本身只数状态更新次数。 |
| S1 “零误杀”测试缺真实正例 | 原测试缺口已补 | test_entity_precision 现有主体匹配、责任方向正确时必须 READY 的正例，本轮定向测试通过；原 23 条缺主体信息用例仍只能证明 fail-open，不能当成全面零误杀率。 |
| Spec P1 口语金额归一 | 原反例通过 | largest_amount_yuan 复用 numeric_tokens；5万块、五万元、50000元及 writer/verifier 受控费用样例通过。numeric_matching_v2 默认关闭。 |
| Spec P2 劳动仲裁中断日期 | 原反例通过 | calc_limitation 对有效中断重算一年，排除起算前、届满后和观察日之后的中断；本轮样例通过。该函数目前没有生产调用点。 |
| B1 100 万元以上受理费档位 | 原反例通过 | fee_formulas.json 已有 0.9%、0.8%、0.7%、0.6% 四档；200 万元普通程序 22800 元及各档边界的独立数值测试通过，档位与[最高人民法院公布的办法第 13 条](https://gongbao.court.gov.cn/Details/d0faf211b7a8b0c57e4fc3daa78c36.html)一致。 |
| B2 民法总则时期三年时效 | 原反例通过 | calc_limitation 已区分 2017-10-01 前后的普通期间；2019-01-01 起算到 2022-01-01 的样例通过，与[法释〔2018〕12 号](https://gongbao.court.gov.cn/Details/175e3fc022e01ce147ae5e39044d68.html)的衔接口径一致。该函数目前没有生产调用点。 |
| B3 否定历史访问被误判伪调用 | 原反例通过 | phantom_action_categories 的 memory 模式和当前分句否定检查区分“无法读取”与“历史会话显示”；正反例通过。phantom_tool_check 默认关闭。 |
| E1 绑定事实与结论相反 | 仅部分收敛 | writer 与 verifier 都调用 settlement_conflicts。直接复现：“该借款已经全部清偿”与“借款尚未清偿”返回冲突；加“因此”后的自然表述返回不冲突。规则只处理独立清偿短句，通用事实一致性仍未通过验收；本轮未对这个变体执行完整生成链。 |
| E2 精确查条未归一条号 | 原反例通过 | exact_article_lookup 在共享入口归一阿拉伯/全角/中文条号，工具侧传入 cutoff；定向等价条号样例通过。 |
| E3 聊天引用卡显示错误版本 | 原 Agent-run 反例通过 | /api/law 的 run_id 路径核验用户与会话归属，读取保存的证据快照，缺失时 404；前端按 run 缓存且切会话丢弃旧响应。无 run 的公开历史回查仍是第 3 节待决的另一出口。 |
| E4 snippet 引文未显示于法律依据 | 原反例通过 | render_verified 的依据区取 claim 引文与绑定证据 source_ref、snippet 的交集；snippet-only 引文用例通过。 |
| R15-1 正确旧法/衔接说明被误拦 | 原误拦反例通过；有已知漏拦 | 旧法引用与明确“不直接适用”当前返回不冲突，R15-B 测试通过。但“按民法典答三年（旧法规定二年）”会因单个“旧法”词被豁免，现有测试主动锁定了这一宽泛标记行为。 |
| R15-2 最早事实日冒充时效起算日 | 未解决，已复现（**本行反例字面已于 09-25 更正，旧字面不可复现**） | `law_version_crosses_watershed` 仍比较 `dates[0]`（全事实串里最早日，与 claim 句段无绑定）。⚠️ 本节第一版把反例写成"事实含**1980 年出生**和 2023 年借款到期"——那**复现不出来**：`extract_dates` 只认 `YYYY年M月D日` 与 ISO/斜杠形状，"1980年"这种裸年份解析结果为空，照旧字面跑会得到"不冲突"，从而误判成本项不存在。可复现的字面是：事实 `["甲1980年3月5日出生", "2023年4月1日借款到期并知损"]` + claim"诉讼时效适用《民法典》第 188 条，为三年" ⇒ 冲突=True（取到 1980-03-05）。相邻正例：只给 2023 到期日 ⇒ False；真冲突对照：只给 2019 到期日 ⇒ True。出生日期与该请求权起算无关；[民法典第 188 条](https://www.cac.gov.cn/2020-06/01/c_1592561777268319.htm)要求看权利受损、义务人知悉等事实。 |
| R15-3 当前快照日取不到跨期旧法证据 | 结构性残余，**覆盖率已核 = 0** | Agent 检索工具只用 context.law_as_of 作为 cutoff。合成旧法元数据在 2019-01-01 有效、2026-09-24 无效；5 条写读测试证明窗口过滤正常，但不能为“2026 年回看 2019 年事实”同时取得当时适用的旧法。**09-25 补的实核**：生效集合 `legal_provisions_cos` 10266 条 `status` 全为"现行"、`effective_from` 与 `effective_to` **全为空** ⇒ 历史法文本覆盖率是 0，不是"未核"。连带结论：`is_valid_by_time` 对空日期视为无限制 ⇒ **任何 cutoff 今天在真实语料上不改变任何一个召回结果**（该谓词是唯一日期判据，另三处调用见 `retrieval.py` 向量池/BM25/grounded 与 `request_bootstrap.py` 末尾复筛）。⇒ 按本节自己的判据"不齐备时记录数据缺口，不写双日期检索来伪装可用"：本项的下一步是**语料数据票**，不是检索代码。 |
| R15-4 劳动关键词掩护民事错答 | 部分修复，仍可复现 | 现按句号/分号等拆段：民事错答与劳动句分成两句时返回冲突=True；同一句逗号连接时劳动关键词让整段跳过，返回 False。快车道把整段答案传入此函数，故该形状仍有漏拦。 |
| R15-5 常见日期格式漏判 | ISO/斜杠已修，中文数字仍是明示限制 | extract_dates 现在识别 2019-03-05、2019/3/5 与数字年月日；R15-A 测试通过。二〇一九年三月五日仍不解析并 fail-open，这是当前测试写明的输入边界。 |

Agent 主开关以及 R15 的 Agent、快车道开关当前都默认关闭；上表中的误拦/漏拦是在启用相应路径后可触发的风险，不据此声称默认线上请求已发生这些错误。E1 的窄域规则虽已接入两道防线，其“通用事实一致性”目标仍未成立。

未闭项的严重度沿用旧报告的 P1（以相关路径启用为前提）。R15-2、R15-4 的纯函数反例与快车道调用链均已直接核实，置信度高；R15-3 的“单一 cutoff 排除已失效旧法”有直接证据，但真实语料覆盖和实际用户结果未测，用户影响置信度中；E1 的自然表述绕过窄域规则已直接复现，完整输出链对该变体未运行，用户影响置信度中。关键定位分别是 backend/agent/limitation_calc.py 的 law_version_crosses_watershed、backend/tools/legal_retrieval.py 与 backend/tools/exact_article.py 的 cutoff、backend/agent/fact_consistency.py 的 settlement_conflicts，以及 backend/main.py 的 _law_version_gate。

### 后续优先级和最小优化方向

1. **E1：限定下一步目标。** 先选一个真实需要阻断的事实关系，给出独立正反例和不应自动判定的边界；现有清偿短句规则不能冒充通用事实一致性。无验收样本前不造语义引擎。
2. **R15-2：先去除无关日期误拦——但排在 R15-4 之后做**（09-25 改序：两者共用 `limitation_calc.law_version_crosses_watershed` 里同一张分隔符表，先修本条会在逗号长句上只修一半）。验收用**可复现的**反例字面：事实 `["甲1980年3月5日出生", "2023年4月1日借款到期并知损"]`（裸"1980年"解析不出，见 §8 表格该行的更正），加相邻正例；只有能从现有事实识别相关日期时才自动拦截，否则维持当前布尔接口的"不拦"结果，不为本票新造三态返回值或起算日解析框架。核对 Agent 与快车道调用点。
3. **R15-3：先查语料，再决定代码。** ✅ 语料已查完（覆盖率 0，见 §8 表格该行）⇒ 结论就是"记录数据缺口、不写双日期检索"。下一步动作已并入 §4 的语料数据票，本条不再单列代码工作。
4. **R15-4：缩小劳动排除范围（先于 R15-2 做）。** 用逗号连接的民事错答/劳动说明反例，加上纯劳动、正常民事对照样例；只调整现有判定函数的局部分段或匹配，不新增第二道门，也不无条件按所有逗号切句（要配"按逗号切了会不会把一句正常劳动咨询切碎致误判"的对照腿）。
5. **R15-1 与 R15-5：先标边界。** 单个“旧法”词可让错误结论免拦，中文数字日期不解析；只有确认这些输入在目标路径出现、并有独立反例时才开修复票。开关默认关闭不等于启用后安全，启用前必须完成对应验收。

法律规则核对使用公开原文：[诉讼费用交纳办法](https://gongbao.court.gov.cn/Details/d0faf211b7a8b0c57e4fc3daa78c36.html)、[民法总则时效衔接解释](https://gongbao.court.gov.cn/Details/175e3fc022e01ce147ae5e39044d68.html)、[劳动争议调解仲裁法第 27 条](https://www.npc.gov.cn/WZWSREL3pncmR3L25wYy8vLy94aW53ZW4vbGZnei96eGZsLzIwMDctMTIvMjkvY29udGVudF8xMzg3ODA5Lmh0bQ%3D%3D)、[民法典第 188 条](https://www.cac.gov.cn/2020-06/01/c_1592561777268319.htm)。这些来源只用于核对本轮讨论的明确规则；复杂案件的适用法、起算与中断仍需事实和法律判断。

## 9. 给执行助手的交接提示

1. 接一张票先只读核对 HEAD、目标文件状态和第 8 节反例是否仍成立；源码或开关已变化时先更新判断，不照旧报告机械修复。其他未提交文件一律视为他人工作，不清理、不顺带提交。
2. 把“查证事实”“等 Owner 选契约”“获批后实现”写成不同状态。待决 schema/API 不先做；审查票不顺手改业务代码。每票只改其行为边界，先复用已有入口与测试夹具，不加通用框架。
3. 对目标反例留一条能失败的检查，再验证修复后的正例和不应触发的对照例；安全/法律版本路径不能只测放行或只测拦截。测试与真实模型、宿主数据库和知识库隔离，不能用 mock 通过代替真实语料覆盖结论。
4. 同一命令失败先查原因，完全相同命令最多再试一次；同一 bug 连修三次仍不过就停止局部补丁，回到事实、调用链和验收判据重新审视。
5. 交付只报实际证据：改了哪些文件、命令与退出码、哪些反例通过、还有什么没测。全量失败、历史语料缺失、开关默认关闭与未部署都明确标注；未经授权不 commit、push、部署或迁移线上数据。
