# 法智 Agent Harness 架构审查报告

| 项 | 值 |
|---|---|
| 审查对象 | `C:\Users\33393\Desktop\ai-legal-helper` 的 Agent 执行骨架：agent loop / 长短期记忆 / 工具与函数调用 / MCP / skill / 向用户提问 / 模型治理 / 观测与成本 / 评测 |
| 性质 | **只读**：未修改任何代码、未跑测试、未起服务、未发出任何 LLM 或外部网络请求（真实配额未被消费） |
| 基线 | master HEAD `5be6e05`；工作树新增本报告与两份评审件，均为未跟踪 |
| 取证纪律 | 每条结论带 `文件:行号` 或可复现命令；查不到的能力直接写"没有" |
| 复核 | 同日两轮正交独立只读复核（A 逐条复现证据 / B 挑战论点并补漏项），全部结论已在本机复跑；撤回与改判记录见 §5 |

---

## 0. 结论摘要

这套 harness 的**防错侧**高于一般 agent harness：模型被固定为"不可信提议者"，争点 ID、Claim ID、证据有效性、预算、终态全部服务端持有并拒收模型注入，校验 fail-closed，终稿走 CAS 幂等 + 二次独立验证。**能力侧**有三类真实问题：**决策者被自己的判据顺序挤出主路径**、**若干条链路写了契约但生产侧没有生产者或消费者**、**记忆与成本观测在 Agent 道整段断链**。

一个反直觉的定稿结论：**把 LLM Planner 挤出局的不是确定性扇出与终稿门，而是评估器的判据优先级**——`unknown_facts` 排在"每争点是否有生效成文法"之前，而分解器几乎总能产出 `unknown_facts`，于是 run 在 EVALUATING 入口就被拽进澄清循环，planner 拿不到回合。副作用比"planner 不行动"更难看：**系统在证据面还不完整时就把用户问满两轮**，`backfill_retrieval`（全库 37 次）正是给这个顺序打的补丁。

分级清单（★=本轮新发现，○=09-18 外部差距报告已列、今日核实仍未做；详细论证见 §3）：

| 编号 | 问题 | 档次 | 建议 |
|---|---|---|---|
| H-01 | Planner 在主路径基本不行动；根因是 `evaluator` 判据优先级。读数：含 planner 主动 `tool_call` 的 run 按日 09-10=68 → **09-13=1**；`evaluation_replan` 全库 **1** 次；`conditional_analysis` **161** vs `SUFFICIENT` **4** | P0 ★ | 先菜单收窄；要给回合就调优先级（顺带去掉 `backfill_retrieval` 补丁），必须配双集验收 |
| H-02 | 五条死链：`state.conflicts`、`AgentStatus.REFUSED`、`SourceType.CASE/TOOL`、`RESEARCH_MORE/REWRITE`、`ask_user` **工具注册**；附带 `verifier.py:483` 判据恒真 | P0 ★ | 逐条"接线或摘除"，并把"删了会红哪些夹具测试"写进裁决表 |
| H-03 | Agent 不读多轮历史；澄清问答不落 Message（⇒ user/assistant 不成对）；Agent 轮不触发滚动压缩；无任何长期记忆 | P0 ★ | ①澄清落 Message（bug 级）②Agent 轮补 compress ③给 planner 加 history（独立开票） |
| H-04 | 无整轮 wall-clock 预算；断连后线程跑完；取消路径不写终态；run 无回收 | P0 ★ | run 级 deadline（复用 `tool_deadline_monotonic` 通道）+ 取消落 STOPPED + 每日 sweep 标 ABANDONED |
| H-05 | Agent 道零成本观测：不 deduct、不记 token/模型名/LLM 耗时；**成功 LLM 调用完全不落日志** | P0 ★ | transport 层成功/失败统一记账，累加写进 `AgentRun`（注意字段白名单静默丢弃坑） |
| H-06 | 扇出串行（每次 submit 后立刻同步 join，4-worker 池从不并发）；planner 看不到检索内容 | P1 ★ | 批内并发提交、一次收齐（保持 fail-closed） |
| H-07 | 工具菜单 4 个真源，唯一闭合测试只钉其中 1 个（且用手抄清单） | P1 ★ | 加"注册表==提示词名单==schema 名单"等值断言 |
| H-08 | 采样参数不控不记（生产 `ChatOpenAI` 无 temperature/seed），而代码自陈"生成是采样的"并用重试兜抖动 | P1 ★ | 按角色绑温度 + 生效参数随 run 记录 |
| H-09 | 确定性计算器（受理费/时效）只做校验放行白名单，没做成模型可调用工具 | P1 ★ | 升为只读工具，返回可绑定证据 |
| H-10 | prompt 无运行期版本归属；CI 无端到端 Agent 门禁；评测无统计显著性；Agent 道绕过缓存与沉淀（**属合理取舍但未写明**） | P1 ○ | 把 `check_agent_release` 红线挂成门禁；每条 run 记 prompt bundle sha |
| H-11 | 网关纵深账本不持久（跨 resume 重置）；无 span/trace | P2 ★ | 只做记录，不优先 |
| H-12 | MCP：**运行期**无客户端；离线语料取数已裁元典 MCP 为工作源（两层不同）。判例缺位是 `COVERAGE.md:32` 写明过的范围决定 | P2 ★ | 维持"运行期不引 MCP"；补判例先立案号规范化 + 存在性谓词 |

**不建议动的资产（动了会掉防错等级）**：server-owned 字段拒收（`planner.py:15-36`、`runtime.py:35-60`、`gateway.py:48`+`:151-158`）、用户内容一律以 JSON 字段传（`runtime.py:546-564`）、writer 不能自签 support verdict（`verifier.py:452-454`）、PASS 绑 digest + `render_verified` 二次独立验证（`verifier.py:227-254`）、终稿 CAS 幂等（`chat_integration.py:163-324`）、确定性终稿门先于 LLM 决策（`controller.py:587`+`:820-838`）。

---

## 1. 审查方法与取证口径

**读过的文件（全文，非节选）**：`backend/agent/` 全部 19 个模块、`backend/tools/` 全部、`backend/{memory,clarify,complexity,intent,request_bootstrap,models,mcp_server,answer_cache,llm_guard,llm_errors,quota_store,observability,routing_metrics}.py` 关键段、`backend/main.py` 的 Agent/SSE/路由段（`748-862`、`956-1060`、`1640-1800`、`2350-2400`）、`backend/prompts.py`、`backend/settings.py`、`.github/workflows/ci.yml`、`docker-compose.yml`、`DEPLOYMENT.md`、`Caddyfile`、`backend/.env`、`frontend/{lib/api.ts,lib/coverage.ts,lib/hooks/useChatStream.ts,components/chat/MessageBubble.tsx}`。

**本地库读数**（全部 `sqlite3.connect('file:backend/app.db?mode=ro', uri=True)`，只读）：

| 读数 | 值 |
|---|---|
| `agent_runs` / `agent_steps` | 295 / 3018 行；`max(created_at)` = 2026-09-18 16:27 |
| tool_name 分布 | `retrieve_laws 1219` / `lookup_article 106` / `retrieve_memory 4` / `analyze_contract 0` / `ask_user 0` |
| 含 planner 主动 `tool_call` 的 run | 09-07=101、09-08=83、09-09=27、09-10=68、**09-13=1**（全库 280/295） |
| `evaluation_replan` / `replan` | 全库 **1** / **0**；09-12 后 12 个 run 内均为 0 |
| `conditional_analysis` vs `evaluation(ALL_ISSUES_GROUNDED)` | **161** vs **4** |
| `backfill_retrieval` | 37（涉及 27 个 run） |
| 终态分布 | failed 100 / drafting 83 / completed 48 / waiting_user 47 / stopped 14 / planning 3 |
| 非终态比例 | 133/295 = **45.1%**（`stopped` 已落终态，不计入分子） |
| 非终态的末检查点 | drafting 83 全是 `conditional_analysis`；waiting_user 47 全是 `clarification`；planning 3 全是 `user_fact` |
| `last_error_code` top | `PLANNER_PARSE_ERROR 66`、`AGENT_BUDGET_EXCEEDED 14`、`EVIDENCE_COVERAGE_DEFICIENT 11`、`UNSUPPORTED_NUMERIC_TOKEN 6`、`CROSS_ISSUE_EVIDENCE 5`、`NON_CANONICAL_CITATION 4`；`CLIENT_DISCONNECTED` = **0** |
| `duration_ms` | 非空 659 行（= 工具耗时已记） |

**样本边界（重要）**：这是评测/开发累积语料，不是线上流量；09-12 批量扇出改造之后只有 12 个 run。因此 §3 的量化结论一律改用**不依赖这 12 个样本**的读数（按日塌方、全库计数），且只作"形态指示"，不作当前质量结论。仓库内另有 `backend/data/app.db`：文件 mtime 更新（09-23）但 agent 数据更旧（09-13）——**文件新 ≠ 数据新**，本节选 `backend/app.db` 是刻意的。

**未验证 / 待线上确认**：① 线上 `AGENT_ENABLED` 真实值（本机 `.env` 未设 `AGENT_ENABLED/AGENT_TRAFFIC_PERCENT/AGENT_SHADOW_ENABLED`，`settings.py:83-85` 默认 False/0；`force_agent` 也打不开——`main.py:1725` 先短路，`forced_manual` 在 `:1765` 的 else 分支内）；② 现网向量索引能否同时存在同一 `(法名,条号)` 的两个版本（决定 D6 走向，需一条 chroma 只读查询）；③ 09-19 之后的任何运行期行为未复量。

---

## 2. 现状盘点：按维度说"有什么 / 没有"

**2.1 Agent loop** — 有：显式状态机 + 转移表（`schemas.py:22-32`、`state_machine.py:12-19`）、持久化检查点 + SQL CAS（`repository.py:97-179`）、六轴预算（`schemas.py:211-218`，生产由 `settings.py:94-98` 注入 20 步/10 工具/3 replan/2 澄清）、动作指纹去重（`state_machine.py:43-79`）、重复动作计数与止损（`:61-79`）、EXECUTING 崩溃禁自动重放（`controller.py:502-505`）、确定性终稿门前置于 LLM（`:587`）、逐争点串行起草 + 逐争点取消检查（`service.py:427-459`）、争点级部分交付（`service.py:439-471` + `verifier.py:468` 豁免 + `_with_uncovered_notice` 显式列出未覆盖争点）。
没有：**并行工具调用**（一次决策只出一个 tool_call）、**循环级 wall-clock 预算**、**反思/自我修订闭环**（见 H-02）、**多 Agent / 子 Agent 编排**。

**2.2 长短期记忆** — 短期有：会话滚动摘要 + 近 6 条原文（`memory.py:15-18` 常量、`:45-51` 双阈值触发、`summary_upto` 增量指针 `:54-98`）、指代消解查询改写（`:101-117`）。Agent 侧唯一入口是 `retrieve_memory` 只读工具（`tools/memory.py:34-62`，归属校验在 `:46-47`）。
没有：**Agent 主输入含历史**（`runtime.py:756-787` 的 planner payload 无 summary/recent，decomposer 只喂 `{"query": …}`）、**长期/跨会话/用户画像记忆**（后端与前端全仓扫 `user_profile|preference|long_term` 零命中）、**写记忆工具**（只有读）、**token 轴窗口管理**（只有字符阈值 6000/轮次 12）、**Agent 轮压缩**（`compress` 只被快车道 `_post` 调用，`main.py:1005-1007`；Agent 道 `:1714`/`:1786` 提前 return）。

**2.3 函数调用** — 有：`response_format=json_schema` 强制结构化 + 严格 pydantic（`extra=forbid, strict=True`）+ 服务端字段注入检测（`planner.py:77-88`）+ 最外层 markdown 围栏剥离（`runtime.py:178-193`，附 24/24 复现的预注册证据）+ schema 能力拒存的窄判定降级（`runtime.py:212-282`，只认"HTTP 400 且文本命中结构化关键词"）+ 校验错误回喂重试一次（`controller.py:621-655`、`runtime.py:831-841`）。
没有：**原生 function calling**（全仓 `bind_tools|tool_choice|function_call` 零命中）、**供应商侧 tool 约束**、**流式工具调用**。

**2.4 MCP** — **运行期没有**：生产唯一的 MCP 痕迹是 `backend/mcp_server.py:23` 的 FastMCP **server**（把 qwen3.5-omni 图像/语音包起来供开发期验收，docstring:1-8），无 client、无 ClientSession、无消费路径。
但**不等于项目不碰 MCP**：离线语料取数已由 Owner 裁为走元典 MCP（`docs/corpus-time-meta-ticket-20260925.md:95`；`:29` 记 20 次调用，`:3` 声明该计数属前任取数记录、本轮未重取）。

**2.5 Skill / 可扩展指令** — 没有。提示词是模块级字符串常量（`backend/prompts.py:12-188`），**无版本号、运行期不可归属**（`prompt_version|prompt_hash` 后端零命中）；发布清单里有**静态** `prompt_bundle_sha256`（`backend/scripts/release_manifest.py:97`），缺的是"这条 run 用了哪版提示词"那一半。工具 allowlist 是静态 dict（`gateway.py:124-148`），`wrapper_overrides` 只能替换已有工具、**不能注册新工具**（`:187-189`）。

**2.6 Agent 向用户提问** — 有且端到端闭环：WAITING_USER 持久化 `pending_question`（`repository.py:119-124`）、SSE `clarification` 事件带 `run_id + state_version`（`chat_integration.py:97-109`）、同端点带 `agent_run_id/agent_state_version` 恢复（`main.py:1670-1720`）、400/404/409/503 分类文案（`:1673`、`:1704-1709`）、CAS 乐观锁防重放（`controller.py:369-372`）、"不知道"显式承认转条件化（`:202-221`）、6–8 争点的**范围选择澄清**（确定性编号解析、绝不调 LLM 理解选择、不消耗澄清预算，`controller.py:890-930` + `:254-321`）、两轮后强制条件化分析（`:1090-1103`）、前端已接（`frontend/lib/api.ts:246-252`、`lib/hooks/useChatStream.ts:49-50,66-108`）。
缺陷见 H-01（提问时机）与 H-03（问答不进历史）。

**2.7 模型治理** — 有：全局并发门 `llm_guard` = `threading.BoundedSemaphore(4)` + 排队 30s 抛 `LLMBusyError`→503，async 与同步共用同一计数（`llm_guard.py:20-35`，docstring 明写"两套池子两套数"的坑）；瞬时/永久分类（`llm_errors.py:88-99`：传输类含异常链上溯，或状态码命中 `TRANSIENT_STATUS`，其余保守判永久）；失败即换模型 failover，每 key 最多一次、用"已尝试集合"保证必然终止（`runtime.py:285-364`）；配额按 **token** 记账、低于阈值判 unavailable 并跳过（`llm_registry.py:523-532` `deduct(key, tokens)`、`:320-332`）。
没有：**退避/jitter**（快车道重试是固定 0.5s sleep）、**熔断器与恢复探测**（全仓 `backoff|circuit|breaker|jitter` 只有 `eval_intent.py` 一个测试函数名命中）、**按任务的模型分档**（planner/decomposer/writer 共用同一 transport，`runtime.py:955-957`）、**可用的 light 档**（`llm_registry.py:289` 在 TIER_CHAIN 里声明了 `light`，但注册表 27 个条目全是 `flag`，`has_role("text","light")` 恒假 ⇒ `main.py:1818` 的轻量腿恒不触发；`.env` 实际部署只有 6 个 `text/flag`）。

**2.8 观测与成本** — 有：`request_id` contextvar + ASGI 中间件收发 `x-request-id`（`observability.py:14`、`:175-220`）、JSON formatter 字段白名单（`:153-156`，白名单外的 `extra` 键**静默丢弃**，哨兵测试 `backend/tests/test_log_field_whitelist.py` 守这条）、`agent_*` 记账字段、writer 逐次渲染摘要与数字/引用**分桶归因**（`writer.py:564-606`、`:686-718`）、覆盖率终态的逐争点事实（`service.py:125-154`）。
没有：**Agent 的 token/成本/模型归属/LLM 调用耗时**（`agent/` 下 `registry.deduct|estimate_tokens|token_est` 零命中；`AgentRun/AgentStep` 无相应列，`models.py:132-176`）、**成功调用的任何日志**（见 H-05）、**span/trace 层级**（后端 Python 无 `trace_id`；`span` 只作为前端 `<span>` 与测试访问器出现）、**per-run/per-conversation 成本上限**。日志只落 stdout（`observability.py:162-172`），compose 无 logging driver。

**2.9 评测与发布门禁** — 有：冻结主集 20 条（`evals/frozen-cases-v2.json`）+ 留出 5 条（`evals/holdout-cases-r1.json`）+ 分水岭对照（`evals/watershed-cases-r15.json`）；`backend/scripts/{eval_agent,gate2_runner,gate5_judge,capture_protocol,check_agent_release,safety_readiness_check}.py`；发布快照冻结 commit+语料+索引+模型+工具策略（`release_manifest.py:41-99`）；红线 BLOCK（幻觉/死循环/预算 >0 即拦，`check_agent_release.py:696-705`）。
没有：**统计显著性**（无 bootstrap CI/两比例检验）、**CI 里的端到端 Agent 门禁**（`.github/workflows/ci.yml:25-46` 只有 ruff/format/mypy/pytest+coverage/pip-audit/前端 build）、**多厂商评委交叉**（judge 单一厂商 `backend/scripts/_judge.py:29-37`，同一厂家既生成又评分）。

---

## 3. 缺陷与可优化点

### H-01 · Planner 在主路径上基本不行动 · 根因是判据优先级（P0）

**机理**：`evaluator.evaluate` 的判定顺序是 integrity → conflicts → **unknown_facts** → 生效成文法 → SUFFICIENT（`evaluator.py:48-95`）。第三道用的是 `min(issue.unknown_facts, key=(statement, why_outcome_changes))`（`:61-72`），即只要分解器给出任何未决事实就先判 `MISSING_FACT`，**根本看不到"证据面还不完整"**。而 `_drive` 在 EVALUATING 入口（`controller.py:519-539`）就把 `MISSING_FACT` 变成澄清，于是 planner 的回合（`:583` 起的 `while True`）被排在澄清循环之后。扇出（`:575`）与确定性终稿门（`:587`，实现 `:820-838`）确实是"跳过 planner"的另外两处，但它们的触发条件比判据优先级温和。
**读数**：`conditional_analysis` 161 vs `SUFFICIENT` 4；09-12 后 12 个 run **全部**经 `conditional_analysis` 进 DRAFTING；`evaluation_replan` 全库 1 次（planner 的 replan 环在本语料几乎不转）；含 planner 主动 `tool_call` 的 run 从 09-10 的 68 塌到 09-13 的 1。
**副作用**：**用户在证据面还不完整时就被问满两轮**；`_handle_evaluation` 的 `backfill_retrieval` 分支（`controller.py:1058-1089`，全库 37 次）是后来加的保护——澄清耗尽后才发现某争点从未检索过，于是先回 PLANNING 补扇出。这个分支的存在本身就是顺序不自然的证据。
**代价**：①提示词花大量篇幅教四工具的 args（`runtime.py:80-100`）并为其注入 schema anyOf（`:367-410`）——教的是一个拿不到回合的角色；②评测里的"planner 能力"实际测的是扇出 + 澄清循环，**把代理目标当目标**。
**建议（分两步）**：先做低成本的诚实化——把 `analyze_contract`/`retrieve_memory` 从 planner 可见菜单摘掉或限定"仅 `MISSING_EVIDENCE` 且 observations 含相应 reason 时可用"，提示词与 `_planner_response_schema` 同步瘦身（与 H-07 一起做）。若要给 planner 真职责，动的是**评估器优先级**（先确认每争点有生效成文法，再提澄清），顺带能删掉 `backfill_retrieval` 补丁分支。
**回退成本**：菜单收窄＝改文案 + 契约测试；调优先级＝**中高**——它改变提问时机，直接牵动澄清/条件化分支与评测口径，必须按双集验收走。教训先例：`backend/tools/legal_retrieval.py:58-66` 记着"要件法条确定性补充"接线被**预登记回退**（评测集 completed 6/10→5/10、留出集 1/5，判过拟合；嫌疑是证据池膨胀改变 writer 校验面）。

### H-02 · 五条写了契约、生产侧无生产者/消费者的死链（P0）

| 链路 | 声明与读取处 | 生产侧写入/消费 | 实测形态 |
|---|---|---|---|
| 证据冲突 | `schemas.py:96-104`、`evaluator.py:53-59`+`:138-150`、`verifier.py:129-136`+`:475-478`、`writer.py:376` | **无写入点** | CONFLICT 判决生产恒不触发 |
| `REFUSED` 终态 | `schemas.py:31`、`state_machine.py:13`+`:17` | **无转移入口**（`controller.py:544` 只是读集合） | 不可达 |
| `SourceType.CASE` / `TOOL` | `schemas.py:35-42` | 证据物化两处恒写 STATUTE（`controller.py:1246`、`:1256`） | 判例/工具证据无生产者 |
| `RESEARCH_MORE` / `REWRITE` | `verifier.py:482-498`、预算 `settings.py:98` | `service.py:491-528` 非 PASS 一律终态失败 | 判决无消费方；`verifier_research_returns` 无自增点 |
| `ask_user` **工具** | `contracts.py:16`、`gateway.py:147`（1.0s/3 次）、`tools/clarification.py:6-7` | `planner.py:103` 显式拒收 `tool_name=="ask_user"`；`gateway.execute` 生产只有 `controller.py:779`/`:1009` 两处且都只送 `ToolCallDecision` | 工具恒不可执行（**决策 kind `ask_user` 可达**，两者不可混） |

**三条必须一起读的限定**：
1. **不是"零覆盖"**——这些分支被测试用手工构造的夹具覆盖并断言（`backend/tests/test_agent_evaluator.py:146-199`、`test_agent_verifier.py:156/430`、`test_agent_writer.py:128/610`）。所以"摘除枚举"会红一批测试，这个代价本身就是裁决信息；反过来，绿测试也不证明生产可达——这正是假器官能长期存活的原因。
2. **`verifier.py:483` 的 `verifier_research_returns < max_verifier_research_returns` 恒真**（左值生产永不递增=0，右值默认 1、`.env` 无覆盖）⇒ `:484` 的 `FAIL_SAFE` 腿恒不可达，覆盖率缺口永远出 `RESEARCH_MORE`，而 `RESEARCH_MORE` 又没人消费。
3. **"问句由服务端持有"是承重设计而非疏漏**：`run.pending_question` 恒等于所选 `unknown_fact.statement`，恢复时靠它精确定位锚点（`controller.py:224-237` + `:392-406`；对不上直接 409）。所以**不能**把"模型写的 question"接成用户所见文本——那会当场打断多轮澄清恢复。剩下的只是措辞问题（陈述句而非自然问句，P3）。
**建议**：出一张"接线/摘除"裁决表，每条只允许两个结局：(a) 摘除（删枚举/删预算字段/删 wrapper + 同步删提示词教学 + 明写会红哪些测试）；(b) 接线并配一条**走生产路径**（不是手工构造 state）的可达性测试。默认倾向：摘除 `ask_user` 工具注册、`REFUSED`、`CASE/TOOL` 与死配置；冲突与回炉见 D6/D7 的降级与撤回。
**冲突检测的边界**：语义上"按基准日版本的法答分水岭前事实"这类冲突，已由 R15 绊线承担（`agent/limitation_calc.py:313` `law_version_crosses_watershed` + `verifier.py:435-450` 消费，开关 `law_version_tripwire_check`）。再接一个 `EvidenceConflict` 检测器前要先回答两者的边界，否则违反本项目自己的单一真源纪律。

### H-03 · Agent 道不读多轮上下文，澄清问答不进历史（P0）

**三段证据**：① planner payload（`runtime.py:756-787`）只有 query/issues/observations/evidence；decomposer 只喂 `{"query": raw_query}`（`:546-564`）；`bootstrap.summary/recent`（`request_bootstrap.py:409-411`）在 Agent 侧无任何消费点——而 Gate 会把 `MULTI_TURN_CONTEXT` 判给 agent_path（`gate.py:153-154` 判据、`:171` 入 reason 集）：**路由判定"这轮需要上下文"，执行链却不看上下文**。
② 恢复分支用 `_resume_bootstrap`（`main.py:787-819`，docstring 自述 non-persisting），不调 `bootstrap_request`；`backend/agent/controller.py` 全文对 `Message` 零命中。用户补充的事实只进该 run 的 `state_json.Fact`（`controller.py:426-433`）。首轮 user 消息有写、终稿 assistant 也有写（`chat_integration.py:285-293`），所以**精确缺陷形状是：每个澄清回合净增 1 条 assistant、0 条 user ⇒ user/assistant 不成对**（快车道专设 `_post_placeholder` 防的就是这件事，`main.py:1012-1014`），并连带扭曲 `recent_messages`/`needs_compress` 的轮次口径；下一轮新 run 也看不到该事实 ⇒ 同一事实会被再问一遍。
③ `compress` 只在快车道 `_post` 里调用；Agent 道 `main.py:1714`/`1786` 提前 return ⇒ 长会话摘要长期落后，一旦技术性降级回快车道，用的就是陈旧 summary。
**建议**：按风险递增——① 澄清问答落 Message（纯加法，不动 Agent 语义，同时修配对与轮次口径；**bug 级**）；② Agent 轮结束复用同一 `needs_compress/compress`（不新造机制）；③ planner/decomposer 输入加 `history`（summary + 最近 N 条）——这一步必须走双集验收（理由同 H-01）。

### H-04 · 无整轮时限；取消不写终态；run 无回收（P0）

**证据**：`AgentBudgets` 无时间字段（`schemas.py:211-218`）。单次 LLM `timeout=120`、`max_retries=3`（`llm_registry.py:348-356`）；failover 可把 `.env` 里 6 个 text/flag 模型各试一遍（`runtime.py:325-364`）；`llm_guard` 排队 30s；工具 15/5/12/3s（`gateway.py:135-147`）。取消检查只在循环外 4 点（`service.py:335/428/529/561`），`agent/{controller,runtime,writer,verifier}.py` 内 `cancel|disconnect` 零命中。`main.py:852` 是 `await run_in_threadpool(execute_agent_request, …)`，`finally`（`:857-861`）只 cancel 断连监视 task，**不 cancel 线程池里那一轮** ⇒ 断连后仍跑完整轮。取消时 `_failure_or_fallback`（`service.py:97-110`）只造返回值、不碰 DB（对照 `_persist_drafting_failure:199-226` 会 CAS 落 FAILED）⇒ 该轮永不落终态。
**归因边界（不夸大）**：库里 133 条非终态**不能**记成取消造成——83 条 drafting 的末检查点全是 `conditional_analysis`、47 条 waiting_user 全是 `clarification`（合法驻留）、3 条 planning 全是 `user_fact`（恢复已提交、执行未跑），且 `last_error_code='CLIENT_DISCONNECTED'` = 0 条。形态更像评测单轮跑完即弃/进程中断。本条可证缺陷只有两条：**取消不写终态** + **无 run 回收**。
**回收的正面证据**（不用 `expire|sweep|ttl` 这类会假阴的 grep）：`delete(AgentRun)` / `abandon` 全仓零命中；`repository.py` 只有 create_run/load_owned_run/compare_and_save；lifespan（`main.py:246-254`）只做 prewarm；`create_run` 每次新建（`service.py:291`）。
**建议**：run 级 deadline（复用 `tools/contracts.py:44` 的 `tool_deadline_monotonic` 形状，把"外层已放弃等待就别再开新远程调用"的纪律从工具扩到 LLM 调用前）；取消也落终态（`STOPPED` + reason code）；每日 sweep 把超过 N 小时的 WAITING_USER/DRAFTING 标 `ABANDONED`（新枚举值，不进 SSE 公开面，只供历史/评测口径）。

### H-05 · Agent 道成本与延迟是盲区（P0）

**证据**：`backend/agent/` 下 `registry.deduct|estimate_tokens|token_est` 零命中（对照组 `main.py:1049/1492/2366` 有命中，证明扫描有效）。`AgentRun`/`AgentStep` 无 token、无模型名、无 LLM 调用耗时列（`models.py:132-176`；`AgentStep.duration_ms` 只记**工具**耗时，非空 659 行）。**成功路径不落日志**：`_log_adapter_invoke` 全仓仅 5 个调用点（`runtime.py:272/279/281/337/357`），全部位于失败/降级腿；`RegistryFailoverTransport.invoke` 在 `:349` 成功即 return，不记 stage、不记选中模型 key、不记耗时；`llm_guard.py` 全文无 logging，ChatOpenAI 未挂 callback。
**对比基线要说准**：快车道也**不是**"真实 usage 优先"——`_token_charge`（`main.py:1034-1049`）只被 light/非流式腿（`:1390/:1418`）调用，而 light 腿因 H-02 之外的注册表缺口恒不触发；主流式出口 `main.py:2358` 注释自陈"流式无真实 usage"，`:2364-2366` 纯 `estimate_tokens`。所以准确表述是"**快车道半有（估算为主），Agent 全无**"。
**影响**：一个 run 打 1 次 decomposer + N 次 planner/writer + 扇出检索，成本量级不可预测；failover 是否生效、哪个模型答的、P95 延迟只能从失败日志反推；与"light 档恒假 ⇒ 全链单档旗舰"叠加，等于每个 Agent 轮都按最贵档跑且无人知道跑了多少钱。
**建议**：在 `_invoke`/`_invoke_with_schema_fallback` 一处收口，成功也记（stage/mode/model_key/attempt/duration/usage tokens），run 结束把累加值写进 `AgentRun`（新增列走 `migrations.py`）；预算补 `max_total_tokens`/`max_wall_clock_ms`。**实现红线**：新字段必须登记进 `observability._ACCOUNT_FIELDS`，否则 JSON formatter 静默丢弃（`:153-156`；该坑已由 AST 哨兵测试守）。

### H-06 · 扇出串行 + planner 看不到检索内容（P1）

`_seed_issue_retrievals` 在 for 里逐个 `gateway.execute`（`controller.py:994-1027`），网关每次 `try_submit` 进池后立刻 `future.result(timeout)` 同步等待（`gateway.py:237`/`:252`）——**池被使用但从不被并发使用**，串行点在 `:252`。按 `gateway.py:125-129` 记录的实测（SiliconFlow rerank 单次 5.82s/11.86s），8 争点扇出段最坏约 120s。另一半：planner payload 只给 `evidence_id/source_ref/legal_validity`，不给 snippet/statement（`runtime.py:778-787`），模型无从基于"查到了什么"改写下一轮检索——它只能重复同类动作，进而被确定性扇出取代。
**建议**：批内并发提交、统一收齐后一次 EVALUATING（保持"任一失败整轮失败"的 fail-closed）；若给 planner 内容可见性，只给受控截断（statement + snippet 前 80 字），并按 H-03③ 的验收流程走。

### H-07 · 工具菜单四个真源，唯一闭合测试只钉一个（P1）

`ToolName` Literal（`tools/contracts.py:11-17`）、`_POLICIES`（`gateway.py:124-148`）、`_PLANNER_SYSTEM_PROMPT` 手写工具与 args 枚举（`runtime.py:84-88`）、`_planner_response_schema` 手写 anyOf 名单（`:396-409`）。契约测试用的是**第五份手抄清单**（`backend/tests/test_agent_prompt_contracts.py:25-30`，注释 `:21-23` 明说"故意不派生自生产函数"），它只断言"提示词含手抄清单里的字段"，不校验"提示词/schema 覆盖注册表"；只有 `test_tool_gateway.py:454` 钉了 `_POLICIES` 集合。⇒ 新增工具时四处可静默不同步，失败形态正是历史上第一名错误码 `PLANNER_PARSE_ERROR`（库内 66 条）。
**建议**：保留独立手抄清单（防自证是对的），补一条闭合断言 `set(policies) - {"ask_user"} == set(_TOOL_ARGS_FIELDS) == set(anyOf 名单)`。

### H-08 · 采样参数不控、不记（P1）

`_build` 未设 `temperature/top_p/seed`（`llm_registry.py:347-356`）；全仓只有评测 judge 显式 `bind(temperature=0)`（`backend/scripts/_judge.py:29-37`）。而代码明确知道生成是采样的——`service.py:406-412` 用"同分布输入两次结果不同"为修正性重试辩护，`:439-446` 记着"同输入 r1 写满 5 claim、r2 漏产 2/4 争点"。等于把本可用低温消除的抖动交给重试，并且评测波动与参数变化无法区分。
**建议**：decomposer/planner 绑低温（结构化决策不需要创造性），writer 保留适度温度；生效参数随 run 记录（配 H-05）。把"修正性重试触发率"做成指标——若低温后归零，`agent_writer_corrective_retry_enabled` 这套开关可以整体退场。

### H-09 · 确定性计算器没做成工具（P1）

`fee_calc.controlled_fee_tokens`、`limitation_calc.controlled_limitation_tokens` 只在校验侧当放行白名单（`writer.py:889`、`:961`；`verifier.py:271`、`:401`）。模型必须自己算对才过闸：writer 腿判 `UNSUPPORTED_NUMERIC_TOKEN`（`writer.py:965`，库内 6 例），verifier 腿判 `FABRICATED_NUMERIC_TOKEN`（`verifier.py:406`，库内 **0** 例）——两闸码不同名不可混。而正确的公式实现已经住在仓库里（`backend/knowledge_base/fee_formulas.json`、`backend/agent/limitation_calc.py`）。
**建议**：升为只读工具（`calc_fee`、`calc_limitation`），返回**可绑定证据**，让数字来源从"白名单赦免"变成"工具观察"。这比继续扩白名单更符合"数字必须可溯源"的既有纪律，也顺带给 planner 一个确定性扇出替代不了的职责。

### H-10 · prompt 无运行期归属、CI 无端到端门禁、评测无显著性（P1，部分在册）

Agent 道 `main.py:1771-1786` 提前 return，缓存查找在 `:1840` ⇒ 不享受精确/近重复缓存（`backend/answer_cache.py:17-26`：进程内 LRU 512 + TTL 6h + key 含 cutoff 与语料 id 集），也不做 QA 沉淀（`main.py:996`）。**这是合理取舍**（Agent 答复带 coverage/partial 语义，不宜跨请求复用），但没在文档里写明，容易被读成漏接。CI 只有 lint/type/pytest+coverage/pip-audit（`.github/workflows/ci.yml:25-46`），`check_agent_release.py:696-705` 的幻觉/死循环/预算红线不在 CI。主集仍 20 条 + 留出 5 条，无 bootstrap CI。
**建议**：把 `check_agent_release` 以夜间/手动门禁形式挂起来并把结果入 release-evidence（比扩 CI 省）；每条 run 记 prompt bundle sha；在文档里明写"Agent 道不走缓存/沉淀"的取舍与理由。

### H-11 · 纵深账本不持久、无 trace 层级（P2）

`ToolGateway` 的 `_fingerprints/_call_counts` 是进程内且注释自认"durable 由 `LegalAgentState` 负责"（`gateway.py:173-178`、`:200-202`）——跨 resume/重放会重置 `max_calls_per_run`；因为状态层的 `tool_calls` 预算与 `action_fingerprints` 是持久化的（`schemas.py:229-234`），这是纵深减弱而非失控。观测无 span 树，一次 run 内多次 LLM 调用无法串联；目前靠"原因码 + 分桶计数"补齐归因（`writer.py:564-606`、`service.py:125-154` 做得好），但延迟/成本的层级归因仍缺。列 P2 备查。

### H-12 · MCP 与判例：范围决定，不是缺陷（P2）

运行期不消费 MCP（见 §2.4）。**结论**：Agent **运行期**不引 MCP 客户端——现有安全资产是"静态 allowlist + 严格 typed 校验 + 服务端持有标识"，运行期动态工具面会绕过 `_POLICIES` 与 prompt 契约（让 H-07 的四处真源变成不可控）。离线语料取数继续走已裁的元典 MCP，两层不冲突。
**补判例的前置判据（别跳过）**：`SourceType.CASE` 空槽是 `backend/docs/COVERAGE.md:32` 写明过的范围决定（"本库是条文库，不含判例"），属范围缺口而非隐瞒能力。真要补判例，顺序固定为：**案号规范化 + 存在性核验谓词 → 再写 `backend/tools/*.py` typed wrapper 进 allowlist → 最后才谈 `SourceType.CASE` 的证据消费与渲染**。因为现核验面只认《法名》第X条（`writer.py:380-405` 的四条引用正则里没有案号形状），判例一旦进答复就无人核验，且案号里的数字还会撞上数字闸（`writer.py:954`）。

---

## 4. 决策台账（每条一词可答；推荐已给）

| 编号 | 待决 | 推荐 | 若不做 |
|---|---|---|---|
| D1 | `ask_user` 工具注册：摘除 or 接成真工具 | **摘除注册**（`_POLICIES["ask_user"]` + `tools/clarification.py` + 出 `ToolOutput` 联合），**保留**决策 kind 与服务端持有问句；问句自然化只做措辞层 | 死配置继续占提示词与 schema 注意力；接成真工具会打断恢复锚点（`controller.py:224-237`+`:392-406`） |
| D2 | planner：菜单收窄 or 改评估器优先级 | **先菜单收窄**；优先级调整单独立项并配双集验收 | 为不参与的角色付维护成本；"证据不全先问两轮"的顺序不变 |
| D3 | 历史注入三步怎么走 | **做 ①②，③ 独立开票**（① 澄清落 Message 属 bug 级，同时修 user/assistant 配对与轮次口径） | 重复追问、摘要陈旧、历史配对长期破坏 |
| D4 | run deadline 数值 + 过期时长 | deadline 5 分钟、过期 24 小时落 `ABANDONED`；归因口径按本报告的修订版写 | 僵尸 run 累积，评测口径含脏样本 |
| D5 | `AgentRun` 加 token/模型名/耗时列（触发迁移） | **要**，与 D4 同批一次迁移 | 放量后成本不可知、模型归属无法复盘 |
| D6 | 冲突检测（`state.conflicts`）接线 or 摘除 | **默认摘枚举**；除非先跑一条只读查询证明现网能同时捞出同一 `(法名,条号)` 两版。R15 绊线已承担新旧法适用冲突 | 与绊线重叠的第二套判定 = 违反单一真源，且多一条死链要维护 |
| D7 | `RESEARCH_MORE` 回炉接不接 | **撤回接通建议**，保持"非 PASS 即终态失败"。若将来重开，前置是：撤销 4 条 `coverage_rewrite_attempt == 0` 断言（`test_agent_chat_integration.py:1022/1423/1548/1607`）+ 书面说明为何推翻 Ticket 2 决策 4 + 双集验收 | 重开被实测否决并有意删除的闭环 = 把回归风险重新买入 |
| D8 | 红线门禁挂夜间 or 进 CI | 先夜间/手动挂 release-evidence，CI 待评测集扩容 | 质量回归靠人记得跑 |
| D9 | 判例能力是否进范围 | 这是**产品范围票**而非 harness 缺陷；若要进，按 H-12 的三步前置顺序 | 直接接判例 = 在引用防线上留无人核验的口子 |

---

## 5. 复核轮记录（撤回与改判留痕）

第一版报告落盘后派了两轮正交只读复核：**A 逐条复现证据**（`dispatch-output/harness-audit-review-20260929/A-evidence-verification.md`，机抽 115 处行号断言逐条打印 ±2 行、负向主张扩面重搜、DB 读数独立重跑）与 **B 挑战论点并补漏项**（同目录 `B-judgment-and-gaps.md`）。两份均自量 `count(b'\r')==0`。**采信原则**：评审主张不直接采信，逐条在我这台机器上复跑后才写进正文；复跑不支撑的不采纳。

第一版被改掉的主张（现正文即为修订后版本，本节只留痕）：

| # | 第一版 | 定稿 | 本机定案证据 |
|---|---|---|---|
| 1 | 断连后"还会再跑一遍快车道检索" | **撤回，不成立** | `routing_metrics.py:13-21` 技术 fallback 白名单无 `CLIENT_DISCONNECTED` ⇒ `main.py:1785` 直接返回不重跑 |
| 2 | "44% 非终态由取消造成" | **机理保留、归因撤回**；比例改 45.1% | 见 H-04 的末检查点读数与 `CLIENT_DISCONNECTED` = 0 |
| 3 | 快车道"真实 usage 优先" | **改"估算为主"** | `main.py:2358` 注释自陈无真实 usage、`:2364-2366` 纯估算 |
| 4 | `AgentRun/AgentStep` 无耗时列 | **加限定**：工具耗时有记 | `duration_ms` 非空 659 行 |
| 5 | 死链"实际是零覆盖" | **改"生产不可达，夹具覆盖并断言"** | `test_agent_evaluator.py:146-199` 等三处手工构造 `EvidenceConflict` |
| 6 | ask_user"守的是一个不存在的调用面"、建议把问句选择权交回模型 | **两处撤回**，工具行降 P2 | `controller.py:224-237`+`:392-406` 的恢复锚点不变量 |
| 7 | D7 建议接通 `RESEARCH_MORE` 回炉 | **撤回** | `service.py:492-493` Ticket 2 有意删除 + 4 条 `== 0` 断言 + 历史实现 `docs/handoff-t7-c01-20260910.md:58` |
| 8 | D6 建议接冲突检测 | **降级并给判据** | 第一版通篇漏引 R15 绊线（`limitation_calc.py:313`+`verifier.py:435-450`） |
| 9 | `SourceType.CASE` 是"假器官" | **改判范围缺口** | `backend/docs/COVERAGE.md:32` 明文 |
| 10 | "MCP 现在不要接" | **限定为"运行期不接"** | `docs/corpus-time-meta-ticket-20260925.md:95`/`:29`/`:3`（评审说 21 次调用，文档写 20 次 ⇒ 采信文档） |
| 11 | 举证用"全仓 grep `spans`/`expire|sweep|ttl` 零命中" | **换正面证据** | 前者反例＝前端 `<span>`、测试 `accessor.span()`；后者反例＝`main.py:116/683/1140/2560/2617`（均与 agent run 无关） |
| 12 | 数字闸码名混用 | **分闸写清** | `writer.py:965` UNSUPPORTED（6 例）vs `verifier.py:406` FABRICATED（0 例） |
| 13 | 失败码漏第二名、路径/行号口径 | **补齐** | 漏 `AGENT_BUDGET_EXCEEDED 14`；`release_manifest.py:97` 确有 `prompt_bundle_sha256`（第一版"清单只冻结工具策略与语料"为错）；裸 `:44`→`tools/contracts.py:44`；`legal_retrieval.py:58-66`；`controller.py:1246` 并列 `:1256` |

**评审补强我的三条读数**（第一版没引，现已入正文）：`verifier.py:483` 恒真判据；`evaluation_replan` 全库 1 次 + planner `tool_call` 按日塌方；`conditional_analysis` 161 vs `SUFFICIENT` 4 ⇒ **H-01 的根因从"扇出/闸门"改判为"评估器判据优先级"**。

**我拒绝的一次降级**：B 建议把 H-01 降到 P1，理由是"n=12 撑不起 P0"。样本批评接受（已换证据），降级不接受——定稿用的是三条不依赖该样本的全库读数。B 另一条"planner 在三重预算内有 3–5 回合"属代码可能性，被实测 `evaluation_replan`=1 反驳。

---

## 6. 后续取证建议（本轮未做，成本很低）

1. **定 D6**：一条 chroma 只读查询，按 `(法名,条号)` 分组数 `version_id`/`effective_to` 组合，看是否存在同条两版并存。查不出来 ⇒ 冲突检测按构造不可达，直接摘枚举。
2. **定 H-05 的量级**：`AgentStep` 已有 659 行工具耗时，可先把扇出段 P95 算出来（不用新代码），再决定 deadline 数值是否真是 5 分钟。
3. **定 H-08**：把 `temperature` 显式绑到 decomposer/planner 后跑一轮 gate2，看 `PLANNER_PARSE_ERROR`（66）与修正性重试触发率是否下降——这是唯一能证明"抖动本该由参数消除而非重试消除"的实验。
