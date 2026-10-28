# 后端只读审查报告（2026-09-29）

> 审查对象：`C:\Users\33393\Desktop\ai-legal-helper` 的**后端**（`backend/*.py` + `backend/agent/` + `backend/tools/` + 部署面 `docker-compose.yml`/`Caddyfile`/`Dockerfile`/`.github/workflows/ci.yml`）。
> 审查性质：**只读**。第一轮（§0–§10）**未修改任何代码、未提交、未跑写操作、未执行项目模块**（没跑 pytest、没跑 `backend/scripts/*`）。唯一新增文件是本报告本身。〔**第二轮口径不同，见 §12**：按 Owner 批准的"副本树 + 定向用例"跑了 `pytest` 与三个探针脚本，但**代码全部跑在 `%TEMP%` 的 tracked-only 副本树里、写侧全指临时路径**；真实工作树与真实 `app.db`/`chroma_db`/配额库四读数跑前跑后逐字相同（§12 开头），**在册代码零改动、未提交**。〕〔**第三轮口径再变，见 §13**：Owner 一句「按推荐做」⇒ 本轮**动了在册代码**，范围只限 DB-15/DB-16/DB-17/DB-18 四票（15 只已跟踪文件 + 4 只新增测试文件，逐只清单与 `+/−` 在 §13.1，同一工作树里另有 6 只**不属于本轮**的前端/计划文档改动，我在归属表里点名了）。仍是**未 commit、未 push、未移 ref、未轮换凭据、未真实入库**；HEAD 两端相同（`.git/refs/heads/master` 两次都读到 `0b543960…`），真实 `backend/chroma_db` 与两处 `app.db` 在收尾复量中均为"零文件被改 + mtime 早于本轮"（两根轴读数见 §13.6 第 5 条）。〕
> 取证基线：master HEAD `5be6e05`（第一轮起点，见 §1 复现命令）。〔**第二轮重判基线 = `0b54396`**：其间并行会话插入 `902e2d1` + `0b54396`，动了 27 个后端文件（+4,519/−201，含约 3,800 行新测试），直接命中本报告三条结论 ⇒ 逐条重判见 **§11**，实测坐实见 **§12**。〕
> 审查维度：代码漏洞 / bug / 死代码 / 业务逻辑 / 函数调用正确性 / Agent 工作流 / 安全与配置。
> 方法：1 名主审（我）+ 4 个并行只读子 agent（API 层、Agent 工作流与工具网关、RAG 与检索业务、安全与配置数据层）；第 5 个"死代码专项"子 agent 交付前掉了，§4 由我自己重跑引用清查补齐（过程与覆盖面缺口见 §9 第 6 条）。报告成文后再派**两路正交的独立复核 agent**（A 路逐条复现行号与读数，B 路挑战论点并补漏），两路都已交付，结论逐条落在 §10，并把它们改判/新增的内容**就地折进了 §0 表与正文**（凡被订正处均标注"复核轮订正/新增"，不掩盖原判断）。
> 现状：**49 条** finding（B-01…B-46 + 第二轮实测新增 B-47/B-48/B-49，三条都在 §11 末表）。复核轮已就地生效的改动 = **5 条改档**（B-06 高→中、B-09 中→中低、B-10 中→高并与 B-11 并票、B-25 中→低、B-38 低→中）+ **8 处事实/机制订正**（B-21 丢失机制、B-34 撤回"zip 损坏→500"、B-41 异常有出口不是 `pass`、B-26 键数与键位、B-29 删用户已清两表的归因、B-14 的 72/73 口径、B-37 的 6→7 处计数、B-01/B-03/§4.3 的三处行号）。逐条台账见 §10。**第二轮（§11/§12）在此之上再改**：3 条已闭（B-08/B-25/B-41，被并行会话在新 HEAD 落地）、1 条降级（B-03 高→中，机理同时改述）、2 条改指针（B-37/B-06 行号漂移）、**B-01 与 B-05 由"待跑"升为全 A 实测坐实**。**第三轮（§13）不再改档**：49 条 finding 的档位与条数一字未动，改的是**处置状态**——DB-15/DB-16(①③)/DB-17/DB-18 已在本工作区实施并用同一批尺子复量（§13.2 给了改前/改后成对读数），DB-16 的第②处**未执行**、连同 `dept_guard` 那份第五实现一起转成两条新待裁 **DB-19／DB-20**（§13.7）。

---

## 0. 汇总

一句话：**后端的"防错骨架"（fail-closed、服务端持有真源、CAS 幂等、引用配对校验、日志字段白名单）比多数同类项目扎实；真正的问题集中在"边界上没有防线"和"防线声称存在但实际不生效"这两类——包括恰好在预算终点炸掉已验证终稿、近重复缓存把答案与证据清单解绑、一条已被文档登记为"已修"的锚点保底修正被证明是 no-op、以及沉淀闸门用的是"问句检索分"而不是"答案有没有据"。**

证据等级标注（每条 finding 都带）：
- **A** = 我在本机独立复核过（读了引用原文 + 自己跑了只读命令或正则实测）；
- **B** = 子 agent 单证，我核对了引用原文与行号，未独立复现其推理；
- **C** = 静态推断（触发路径的**可达性**或真实运行结果未实测，需一条定向用例坐实）。

| 编号 | 档次 | 一句话 | 证据 | 我的建议（一词可答：做/不做/改判） |
|---|---|---|---|---|
| B-01 | 高 | run 恰在步数预算终点进 DRAFTING 时，**已 PASS 验证的终稿**在落库瞬间被 `BudgetExceeded` 炸掉，并被误标 `AGENT_STORAGE_FAILURE`（不在降级白名单）→ 用户拿到硬错误、run 永卡 drafting | **A（§12.1 四腿实测全坐实：对照腿绿、判据腿钉 `budget_exceeded:steps`、后果腿查到 0 消息 + status 仍 drafting、可达腿证 `EVALUATING@cap-1 → DRAFTING` 落点恰为 cap；原"可达性 C"已消）** | 做：`persist_agent_final_once` 捕获 `BudgetExceeded` 并归 `AGENT_BUDGET_EXCEEDED`；〔**§12.2 扩成新条 B-47，同一根、建议并一票**——恢复边比终稿边更常撞到〕 |
| B-02 | 高 | 限流 key 无条件信任 `CF-Connecting-IP`，凡不经 Cloudflare 的入口逐请求伪造即可让**全站 `@limiter.limit` 归零**；compose 里 cloudflared 不在编排内、Caddy 不剥头 | A | 做：加 `TRUSTED_PROXY_MODE` 显式开关 + Caddy 剥头 |
| B-03 | 中（**§11.2 从高降：新 HEAD `0b54396` 加了 `CacheScope` 等值门**，跨天/换证据集/换意图那半边已结构性关掉——`answer_cache.py` 的 `if not q_embedding or scope is None: return None` 与 `if v.get("scope") != scope: continue`，scope 由 `main.py:1146-1155` 用 (source, article, effective_from, effective_to, status) 五元组产出） | 近重复缓存命中下发的是**本轮检索的 sources** + **上一轮检索的答案**，`hit["sources"]`/`hit["model"]` 全仓无读点 ⇒ 破"引用可溯源"底线，并把该轮漏召回率算错（原判据里的"不比 cutoff"这半边**已由 scope 门关掉**，剩余洞改述为"帧内容与答案不同源"） | A（两 agent 独立同判；§11.2 按新 HEAD 逐行重读后改述） | 做：命中时下发条目自身 sources，或把 cutoff 纳入命中判据〔后半句已由并行会话实现，别再按原样派单〕 |
| B-04 | 高 | Agent 引用防线**系统性盲区**：claim 里的**裸条号且前面没有任何"法/典/条例/规定/办法"尾词**时（例："依据第五百七十七条，对方应担责"、"依照第一千二百五十四条"），writer 的 `canonical_citations`（三种模式都要法名锚）、`numeric_tokens`（`_ASCII_NUMBER_RE` 只认 ASCII 数字，中文数字不成 token）、`has_noncanonical_citation`、终稿 `citation_verify`（`_ART_FULL_RE` 要《》）**四道门同时看不见**；同形态阿拉伯数字"第577条"反而因 `number:577` 无来源被拦 ⇒ 判定不对称。**复核轮把例形收窄**（"第五百七十七条规定"这种条号在前的写法并不匹配 `_UNBRACKETED_CITATION_RE` 的"名称+条号"顺序，故不构成误拦；真正的洞是**前无锚**那一形）；另：`entity_precision_check` 默认关（`settings.py:103`）且它消费的是同一套带锚提取，补不上这个洞；`phantom_check` 只管"声称检索过"类伪动作、`fact_consistency` 只管和解矛盾，都覆盖不到 | A（四道门的提取器本体我都读了；具体 claim 样本未跑 ⇒ 例形仍属静态判定） | 做：增设"无名条号"独立检测，fail-closed |
| B-05 | 高 | Agent 工具 `retrieve_laws(category=...)` 的过滤键在现网库里**根本不存在**（我实测两集合 10266 条的 metadata 键只有 8 个，无 `category`）→ LLM 一旦传它就"静默零结果"，Agent 记为证据缺失。**§12.3 把这半句从推断变成实测**：chromadb 0.4.24 现场跑生产同形状，**全集合无该键 ⇒ `{"category": X}` 返回 `[]`**（对照腿同集合无过滤返回全量），且 **`$ne` 也排除缺键行**（逃生门不存在）；链路读通到**提示词**：`agent/runtime.py:85` 的 Planner 系统提示词**明写「category 可选」**，即模型是被邀请传这个键的。唯一逃生口是条号直查（`retrieve()` 先 `parse_article_query`，不吃 category）⇒ 普通问句零证据、"《法名》第X条"形仍有证据 | A（§12.3 实测 + 逐段读通；**触发频率仍未知**——`agent_steps.normalized_input` 存的是 64 位 sha256 不是 JSON，历史是否真传过 `category` 本机读不出来，我第一次按 JSON 去 LIKE 得到的 0 是尺子空转、已作废） | 做：从 Planner 可选面摘掉 `category`（最便宜，改提示词一句 + 删字段），或检索侧对"过滤后为空且该键在库中零出现"回落无过滤并落 warning |
| B-06 | 中（**从"高"降**：复核轮证伪了"单请求扫 18 档 → 全站 503"这条杀伤链） | 一次由**用户内容**触发的 provider 4xx（超长上下文、内容审核 400）会把模型**永久**标耗尽且**零日志**：`stream_with_retry` 的 `configs` 只有 3 项、`on_model_failure` 仅在 `i < len(configs)-1` 时调 ⇒ **单请求最多标死 2 个模型**；而 `_safe_pick` 在 `QuotaExhausted` 时仍回落 `registry.get()`（`main.py:1062-1064`）⇒ **不会 503**，真实后果是：被标死的模型对本进程**永久退出自动路由**（`mark_depleted` 无 TTL、无日志、`reason` 参数被忽略），降级态 `flag_degraded` 又**禁止写缓存**（`main.py:2328`）⇒ 此后每次请求都吃"带 NOTE_QUOTA 的降级答复 + 零缓存复用"，运维无从归因。**更要紧的形状在配置里**：见新条 **B-43**（compose 那份 `.env` 只有 **1 个 text 角色**，即没有回退池，一次 400 就把文本档全占）；§12.4 实测补充：分类判据在真 SDK 形状下逐格对上（400/401/403/404 → 标死；408/429/5xx → 只排除；未监听端口 → `APIConnectionError` 判瞬时，F7 修复成立），且**同一 400 连打三次同判** ⇒ 请求形状类 4xx 会逐个把链上模型标死；分类本身是有意设计并已被 `test_llm_failover.py:167-170` 钉住，我不重开，**新增归因面见 B-48** | A（`configs` 三项、`_safe_pick` 回落、`mark_depleted` 函数体我逐行读过；状态码网格 §12.4 实跑）；**"provider 是否真返过 400"仍不可知**——`logs/` 在本工作区实测 0 文件（§12.7） | 做：payload 形状类 400 只排除不标记 + 冷却 TTL + `mark_depleted` 落结构化日志（与 B-48 同票） |
| B-07 | 高 | 受控沉淀用 `grounded_top_score(问句)`（问句与库的余弦）当"答案有据"，且 `self_check` FAIL 的答案照样进 `_post(curate=True)` 自动收录分支；读侧 `qa_citations_in_kb` 校验的是 evidence 而非正文引用 ⇒ 编造条号可入持久语料 | A（B07 判据链 B） | 做：沉淀入口前置 `sv.ok` + 正文引用 ⊆ evidence 断言 |
| B-08 | **已闭（§11.1，新 HEAD `0b54396`）** | `_post`/`_post_placeholder` 里"原子自增"紧跟 ORM 绝对赋值 ⇒ commit 时把原子结果覆盖掉，注释仍写"防读-改-写竞态"（在册修复 #21 三处只落对一处）。〔§11.1 复量：`main.py:996` 一带那行 `conv.message_count = …` **已删**，只剩原子 SQL ⇒ 建议的修法已由并行会话落地〕 | A | 做：删掉 ORM 赋值那一行（单一真源=原子 SQL）〔**已完成，勿再派单**〕 |
| B-09 | 中低（**从"中"降**） | 旗舰流式与合同分支在 async 生成器里**直连 Chroma** 跑 `citation_verify` + `quality.self_check`（后者内部再跑一遍）⇒ 每答复 2×引用数次同步库查询卡事件循环；同文件 `deduct` 都规规矩矩进了线程池（在册修复 #20 只落一半）。降档理由：`article_in_kb` 每条引用一次 `_collection.get(where=)` **无 per-article 缓存**（`_src_set_cache` 只服务 `source_in_kb`），但本地是 sqlite 毫秒级查询、部署形态 1-2 用户，受害者只有自己 | A | 做：两处包 `run_in_threadpool`（对齐在册修复 #20） |
| B-10 | 高（**从"中"升**，与 B-11 并票） | 锚点保底位不受 k 约束：`retrieve` 默认 `k=4`（`retrieval.py:1004`），而**单个**强锚点就产 `rankings[qi][:3] + b_rankings[qi][:3]` 至多 6 个 id 并无条件占头（`retrieval.py:950-974`）⇒ **不需要"多锚点"，一个强锚点即可把精排/rerank 结果整段挤到零进位**；而 ADR-011 称 rerank 是"准度主菜" | A（我读了 950-974 与 1004） | 做：与 B-11 同票修（保底总量 ≤ k，且补偿要真挤掉尾部） |
| B-11 | 高（与 B-10 **是同一段代码的两个面，建议并成一票**） | 号称"锚点不被 k 截断"的对抗审计 v2 #19 修正是**可证明的 no-op**：`docs=(docs+anchor_head)[:k]`，而进入该分支的充要条件恰是"锚点数 > k ⇒ 截断后 `len(docs)==k`"⇒ 追加再截等于没追加。复核轮独立复算同结论 | A（我独立复算 + 复核轮独立复算） | 做：`docs[:k-len(anchor_head)] + anchor_head`；并给在册 #19 补形状哨兵（§3 第 3 条） |
| B-12 | 中 | 条号直查短路：一条问句里两个《X》第Y条时只检索第一个（`parse_article_query` 用 `.search()` 且命中即 `return exact`）⇒ 后半句零证据下模型自由生成 | A | 做：`finditer` 取全部配对 + 整句 hybrid 合并 |
| B-13 | 中 | 同一条"什么算合法条号"的规则有 4 份实现 / 7 份字符类，**最窄的两份落在评测与沉淀代码里**：我实测 `《民法典》第一千二百五十四条` 对 `curation.has_citation`/`eval_metrics.citation_present` 均为 False，而 `retrieval._ART_FULL_RE` 能识别 ⇒ 高空抛物/继承/交强险等千级条号答案永不进待审队列（无日志），评测同步低报 | A（正则实测） | 做：收成 `domain_rules` 单一真源 |
| B-14 | 中 | 无书名号的引用只靠 28 部白名单法名补全，而库里实测 99 部 ⇒ **72 部法的裸名引用对三方校验完全隐形**；仓内已有 99 部全集（`_ensure_src_set`）却没和白名单对齐 | A（计数由我本机复算：白名单 28 / 其中 27 在库（`食品安全法`不在库）/ 归一化后库内 99 部源名有 **72** 部不在白名单。子 agent 报的是 73，差异在 `宪法（1982年）` 这类括注名的归一口径，我按 `retrieval._source_key` 同口径重算取 72）；后果链 B | 做：白名单运行时由库内源名派生 |
| B-15 | 中 | `TOOL_BUSY`（线程池容量满）判硬失败、用户零答复；同因的 `TOOL_TIMEOUT` 在白名单内可降级拿快车道答案 ⇒ 过载时刻最没兜底 | A | 待裁：白名单是冻结政策，需 Owner 确认容量类失败是否并入 |
| B-16 | 中 | 部分交付落库前的 `compare_and_save` 没有 try 包裹（同函数其它 CAS 都有映射）⇒ 版本冲突裸抛穿过 endpoint 变 500，且发生在"已验证答案即将交付"一刻 | B | 做：映射为 `AGENT_FINALIZATION_CONFLICT` |
| B-17 | 中 | 登录失败锁定的窗口锚在**第一次失败**时刻（`ts if cnt > 0 else now`），300 秒后该用户名**永不再被锁**；与 B-02 叠加后爆破只剩理论限速 | A | 做：改滑动窗口（每次失败刷新 ts） |
| B-18 | 中 | `/api/chat` 的 JSON 请求体（含 base64 图）**无真实字节上限**：中间件只看 Content-Length，`_read_capped` 只覆盖 multipart，`schemas.image` 无 max_length，尺寸判定发生在解码之后 ⇒ chunked 无长度头可打 OOM | A（OOM 后果 C） | 做：ASGI 层累积字节计数 + `image` 加 max_length |
| B-19 | 中 | E9 兜底整答用 `flag_llm`，两处面都不对：**①记账面**——扣减按 failover 后的 `current["key"]`（`main.py:2363-2366`），与紧邻注释写下的"按真正回答的模型扣减"口径正好相反（`flag_llm` 自 `:1843` 赋值后从不随 `_safe_pick` 更新，`make_chain_fn` 只改 `current["key"]` 与局部 `llm`）；**②执行面（复核轮补）**——兜底**不重 pick、不过 `stream_with_retry` 的轮换**，若 `flag_llm` 恰是本轮已被 4xx 标死的那个 key，这次同步 `_invoke_llm` 必然再次 4xx ⇒ E9 变成 error 帧，即"三条 config 都失败后，唯一没被换掉的是兜底用的模型"。触发条件：仅当流式换过模型且 E9 才跑 ⇒ 低频但正是最需要兜底的时刻 | A（`:1843/2188-2202/2247/2363-2366` 我逐行读过；`grep current["key"]` 无其它纠正点） | 做：兜底前先 `_safe_pick(modality, tier, exclude=_tried)` 重取一次，并把扣减 key 与被调模型绑成同一个变量 |
| B-20 | 中 | 三类真实 LLM 调用（视觉描述、多轮检索改写、历史压缩）**从不 deduct**；`pick` 只选不扣，扣减全靠调用方显式做 ⇒ 看门狗对这些模型整体失明，管理台"剩余"天然虚高 | A | 做：统一在 transport 层记账（与今日 harness 审计 H-05 同批） |
| B-21 | 中（**机制在复核轮被改写，我原判的丢失窗口是错的**） | embedding"换班"对 cloud→cloud 是**先删后写**（`rebuild_embeddings.py:166` 的目标与 `:130` 的数据源是**同一个** `COLLECTION_NAME`=`legal_provisions_te4`，`_ensure_new_collection` 里 `delete_collection` → `create_collection`）。~~丢失窗口是"换班后新增到 te4 的块"~~ ——**该说法错**：源库在删除前已被 `_read_old` 整库读进内存（`:131-137`），新增块随 `docs_main` 一起重嵌。真实丢形是 **① `:98-99` 删建之后 `_write_new`（62-88）中断**（6 次退避后 `:77` `raise`）⇒ te4 只剩半套新模型向量，而 `.env` 已被 `switch_embedding.py:208-211` 提前改过；**② 崩溃后重跑被放大**：半库使 `count()>0`，不再回落 `_COLLECTION_LOCAL` ⇒ 已丢的那部分**永久丢**。可救性：`backup_data.py:77-85` 用 sqlite backup API + `integrity_check` 的上一次快照可兜（限运维停库窗口内）。另半边成立：改 `EMBEDDING_MODEL` 不重建时后端拿新模型向量查旧 HNSW、**运行期零校验**，唯一维度绊线只覆盖 8 个模型里的 2 个（`MODEL_DIMENSIONS` 6 个为 `None`）⇒ 同维度不同模型完全无护栏 | A（`:166/130/98-99/77/216` 与 switch `208-214`、`MODEL_DIMENSIONS` 我都逐行读过；"读进内存先于删除"由复核轮指出、我复读确认 ⇒ **原措辞撤回**） | 做：先写 `-rebuild` 再原子换名（消掉 ①②）+ 把索引来源模型名写进 `.env` 做启动绊线 |
| B-22 | 中 | 快车道把"场景补充条文"（最多 24 条、兜底再推 20 条）**前置**在精排结果之前且不与检索结果去重 ⇒ prompt 前段是关键词表推出来的条文，真检索被压到中段（与"首尾放最强证据"相反） | B | 做：补充条目放尾/按 `_doc_id` 合并去重 |
| B-23 | 中 | 自检作用在**未归一**的答案上，归一只发生在落库前 ⇒ 校验输入 ≠ 交付文本 ≠ 库存文本；无书名号答案被误判 `no_citation_while_hit` 白烧一次旗舰，缓存里存的也是未归一文本（前端不标色） | A（行号）/B（后果链） | 做：把 `expand_*` 归一前移到 self_check/写缓存之前（幂等） |
| B-24 | 中 | docx 修订/域代码告警在**运行时上传路径被丢弃**（`text, _warnings = extract(...)`），而离线语料管线会打印 ⇒ 法务上传"开了修订且以原始视图保存"的合同，插入条款缺失且全程零提示 | A | 做：warnings 随响应返回并记审计 |
| B-25 | **已闭（§11.1：`902e2d1` 已把 `.env.bak*` 追加进 `.gitignore` 末尾——追加在末尾是因为 tests 按 `.gitignore:31/:45/:77` 行号引规则）**；原判 低（**从"中"降：我原判的"换机/新克隆一次 `git add -A` 即泄密"情景不成立**——那是个**未跟踪**文件，克隆里根本没有它） | `backend/.env.bak-20260910-pre-qwen38`（含 7 个凭据键）**只被 `.git/info/exclude:9` 的 `.env.bak*` 挡住**，`.gitignore` 任何规则都不匹配（`git check-ignore -v` 实测命中源只有 `info/exclude`），pre-commit 无密钥扫描钩子。**且这是有意裁决**：`info/exclude` 那行注释自陈"本地忽略，不进候选"，同族问题 09-15 已在册（`docs/process-archive/code-review-report-20260915.md` B2 项 → 产出 `.gitignore` 的 `*.bak` 规则与注释）。剩下真面只有两条：**整树拷贝给别的会话/工具**时该文件跟着走（本仓已有 `.git-backup-*` 被反复哈希成 697MB 垃圾的前科），以及有人手工 `git add -f` | A（check-ignore 我复跑；在册理由我读到原文） | 做：`.env.*` 一行平移进 `.gitignore`（配 `!.env.example`）即可，**detect-secrets 钩子单独立项**，别按"紧急泄密"派单 |
| B-26 | 中 | 配置面三处"改了不生效/漏传即静默降级"：①陈旧键名在 `backend/.env.example:17`（教 `SELF_REGISTER`，而字段名是 `feature_self_register` ⇒ pydantic-settings 按字段名匹配，这键读不到），根 `.env:8` 也带着同一个死键；②compose `environment` 只传 **13** 个变量，而根 `.env` 实有 **23** 键 ⇒ 未传的 `EMBEDDING_*`/`RERANK_*`/`DASHSCOPE_API_KEY`/`SILICONFLOW_API_KEY` 在容器里读不到；③缺 key 的 provider 在 `llm_registry._load` 被**无声** `continue`（`:423-429`）⇒ 视觉/语音/rerank 能力静默降级，`/api/health` 的 `image_chat` 布尔是唯一可见痕迹。〔**复核轮订正**：我原先写的"22 键""根 `.env.example` 教 SELF_REGISTER""`CORS_ORIGINS`/`FEATURE_*` 没传"三处指错——实测根 `.env` 是 23 键，`CORS_ORIGINS`/`FEATURE_*` 只在 `backend/.env` 而不在根 `.env`，`.env.example` 那份没有 SELF_REGISTER〕 | B（原列的键集有 3 处错，经复核订正后为 A：键数与位置我本机重数过） | 做：compose 环境变量覆盖哨兵测试（settings 字段 ∪ compose `environment` ∪ 两份 `.env.example` 三方对齐）+ skip 落 warning |
| B-27 | 中 | 无登出、无 jti、无吊销 ⇒ **重置管理员口令不会使攻击者已持有的 7 天 token 失效**（唯一有效驱逐是禁用账号或轮换 `JWT_SECRET` 重启，而 DEPLOYMENT.md 未写这条应急预案） | A（后端 grep 零命中） | 做：`token_epoch` 列 + 改密时 +1；事件响应写进文档 |
| B-28 | 中 | 模块级会话态（`_contract_convs`/`_clarified`/`_contract_reviewed_convs`）从不随会话/用户删除清理，而 `conversations.id` 是**无 AUTOINCREMENT 的 rowid 会被复用** ⇒ 新会话（甚至别人的新会话）继承上一任的"合同模式/已反问一次" | A | 做：删除路径清理 + 显式 AUTOINCREMENT |
| B-29 | 中低 | 删除语义有漏（**复核轮订正了我原先的归因**）：`admin_delete_user`（`main.py:2616-2631`）**确实已显式清** `Feedback` 与 `AnalysisRun`（`:2624-2626`，注释自陈"无级联需显式清理"）——所以问题不是"作者不知道要手工清"，而是**清单不全**：①`agent_runs`（其 `state_json` 内含用户法律争点/事实/证据 snippet）+ 随它的 `agent_steps/agent_evidence/agent_claim_checks` 没人清；②`media/` 里该会话消息指向的原图与缩略图不删（只在 `request_bootstrap.py:434` 的失败分支清）；③**删会话**这条路径（`main.py:2544-2550` 只有 `db.delete(conv)`）不清该会话的 `feedbacks` 快照；④`qa_candidates` 既无 `user_id` 列也无任何删除通道 ⇒ 无法响应"删掉我的数据"。底层同因：SQLite 全库**从未 `PRAGMA foreign_keys`**（`database.py` 无 connect handler，`grep foreign_keys backend/` 仅命中 `quota_store.py` 的 `journal_mode`）⇒ 上面这些 FK 连"孤儿行"都拦不住 | A（①②③④与"删用户已清两表"我都逐行读过） | 待裁：补清理清单 vs 明写"qa_candidates 不可按用户删除"的已知限制（见 DB-11） |
| B-30 | 低 | `analyze_contract` 的分析对象是**模型转述进 args 的合同文本**，服务端既不从 bootstrap 直取全文也不校验逐字一致，`ContractInput.text` 无上限 ⇒ "确定性分析"的输入保真度靠 LLM 抄写，抄错一字风险等级就变且仍算"有证据" | B | 待裁：是否列为在册限制 |
| B-31 | 低 | 空 body `PATCH /api/admin/users/{id}` 也会提交并写一条 `user.toggle is_active=None` 审计（审计轨迹出现从未发生的操作）；且 PATCH 侧没有"不能停用当前管理员"的等价防护 | A（形状） | 做：无变化即不写审计；禁自停用 |
| B-32 | 低 | 客户端 `X-Request-Id` 未做长度/字符校验，原样回写响应头并进入该请求**每一行**结构化日志；另 `auth.py:65` `int(payload["sub"])` 对缺 sub 的合法签名令牌抛 ValueError→500 而非 401 | A（500 需持有密钥，实际不可达） | 做：长度+白名单钳制 |
| B-33 | 低 | bcrypt 5.0 对 >72 **字节**口令抛 ValueError，而 `RegisterIn` 限的是 64 **字符** ⇒ 25 个汉字的强口令会让 `POST /api/admin/users` 返 500（`verify_password` 兜了 ValueError，`hash_password` 没兜，形状不对称） | B | 做：字段校验按 UTF-8 字节数 |
| B-34 | 低 | docx 内部实体展开与 PDF 页数无预算：`docx_utils.py:56` 用裸 `ET.fromstring`，无 DOCTYPE/实体防线（zip 炸弹那半边已治：`knowledge_service.py:88-93` 按中央目录声明值拒超限条目，且 stdlib 读取时也会截断）；pypdf 全量遍历无页数/时钟上限。〔**复核轮订正**：我原先"`BadZipFile` 不在 `except ValueError` 内 ⇒ 归 500 而非 400"**说反了**——`docx_utils.py:49-50` 与 `knowledge_service.py:94-95` 都把 zip 问题转成 `ValueError`，`main.py:1442-1443` 接住转 400；剩下的真缺口是 pypdf 自身的 `PdfReadError` 未被归一进 `ValueError`（**这一条我只读了 docx 那条链，pdf 侧未核异常类型**）＋无页数预算〕 | A（docx 那条链我逐行读过并据此撤回）；pdf 侧 B | 做：解析前断言无 `<!DOCTYPE`/`<!ENTITY` + `MAX_PDF_PAGES`；pdf 异常也归一进 400 家族 |
| B-35 | 低 | 关停 seam 未接线：`tools/gateway.shutdown_default_executor`/`wait_for_idle` 全仓无生产调用点，`main.py` lifespan 只 prewarm ⇒ 超时后仍在跑的检索线程无排空点 | A（grep） | 做：lifespan 关闭时调用 |
| B-36 | 低 | 状态机图与真实持久化漂移：`compare_and_save` 只校验 `status == state.status`（自洽而非合法），`ALLOWED` 里没有任何指向 `STOPPED` 的入边但 `STOPPED/FAILED` 由 `model_copy` 直写 ⇒ "终态不可回退"只靠 CAS 版本号 | A（在册设计，见 §6） | 待裁：补注释声明"机外终态"还是加合法入边断言 |
| B-37 | 中低 | **7 处**（原判行号 `main.py:1884 / 1915 / 1944 / 1973 / 2105 / 2181 / 2395`；**§11.3 按新 HEAD `0b54396` 重测为 `2073 / 2104 / 2133 / 2162 / 2304 / 2380 / 2599`，条数仍是 7、结论不变**）`_post` 落库失败只 `print(f"[chat-post] {e}")`，不发 error 帧不重试；且此时 `_posted` 仍为 False ⇒ `finally` 会用 `_post_placeholder` 补一条"服务暂时无响应"占位，而用户屏幕上看到的是完整答复（历史与所见相反）。另有 3 处同型 `print`：`2314 / 2404 / 2414`（`[chat-placeholder]`）与 `2407`（`[chat-stream]`），**全部走 stdout 不入结构化日志** ⇒ 无法按 `req/user_id` 归因。详解见 §3 第 2 条 | A（7 个行号我本机 grep 到；后果未注入实测 ⇒ C） | 待裁：占位补偿是否本就被当作正确行为；`print` 是否改 `logging` |
| B-38 | 中（**从"低"升：复核轮指出这不是"将来上公网才需要重估"，而是文档已经在教裸奔公网**） | 两半：①运行时硬化缺位——容器无 `USER`（root）+ bind-mount 用户数据目录 + `backups/` 同盘明文；②**`DEPLOYMENT.md` 主动给出明文公网剧本**：`:30-31` "启动（强制绑定 0.0.0.0，端口 8080）"、`:63` "安全组 **放行 22、8080**"、`:65` "内地用 `IP:8080` 这种非标准端口访问**不需要备案**"、`:101-111` 把 `NEXT_PUBLIC_API_URL` 改成 `http://<ECS公网IP>:8080` 并"前端 3000 需安全组放行"、`:71` `scp root@<ECS公网IP>`。⇒ 照文档做，`/api/auth/login` 与全部 `/api/admin/*` 走**明文 HTTP**、无 TLS、无隧道，再叠 B-02（CF 头可伪造 ⇒ 限速归零）与 B-17（锁定窗口一次性），口令可嗅探、爆破可续。正向确认：compose 的 backend/frontend **没有** `ports:` 段，8000/3000 未泄漏宿主（**Docker 路径是好的**，问题在文档推荐的裸跑路径） | A（DEPLOYMENT.md 那 6 处行号我逐条 grep 到原文） | 做：文档层先改（把"IP:8080 裸跑"标为**仅限内网**、公网路径只留 Caddy+tunnel/自签 TLS），再补 `USER`/`no-new-privileges`；与 B-02 同票做 |
| B-39 | 低 | 依赖与构建：`requirements.txt` 全区间制**无锁文件/无 hash** ⇒ CI 的 `pip-audit` 审的与镜像里跑的不是同一组字节；`langchain>=0.1,<0.2` 是停维护主版本线；Dockerfile 构建期从 `hf-mirror.com` 烘焙 BGE 权重**不钉 revision 不校验哈希**，而 compose 未设 `HF_HUB_OFFLINE` ⇒ 烘焙层丢失时运行期回源重下（`sentence-transformers` 的 `.bin` 走 pickle 反序列化，权重即代码） | B（我核对了 requirements 形状与 Dockerfile 那两行） | 待裁：是否值得引入 lock（CI 已有 pip-audit，方向是"审同一组字节"而非"多一个工具"） |
| B-40 | 低 | `backend/mcp_server.py` 的两个工具是"任意本地路径读取 + 原样外发第三方"原语：`image_path` 无目录约束、无扩展名白名单（音频侧反而有 `_AUDIO_EXTS`）、无字节上限 ⇒ 一次调用可把 `C:/.../.env` base64 后随 `Authorization` 发到 `LLM_BASE_URL`（当前配置为外部第三方）。非 HTTP 面（stdio 开发期工具），但它被 `COPY . .` 带进了生产镜像 | A（键名/形状）/B（外发链） | 待裁：加 allowlist 根目录，或标记"不进生产镜像"（与今日 harness 审计 H-12"维持不接 MCP"同批裁） |
| B-41 | **机制半边已闭（§11.1：`llm_guard.py` 现版说明与函数体都改成"取消窗口 D1 修复：不再经 `to_thread` 阻塞桥接"⇒ 我原报的"排队占 default executor 一个 worker，把占位落库挤到队列后面"这条链的承重柱被抽掉）；`print` 改 `logging` 那半边未闭，并入 B-37**；原判 低 | `llm_guard` 的 async 排队用 `asyncio.to_thread(self._sem.acquire, True, self._timeout)`（`llm_guard.py:35`，`_timeout` 默认 30s）**占用 default executor 一个 worker**，而客户端断连后的 `_post_placeholder` 也用同一个默认池（`main.py:2413-2414`）⇒ 并发突增时补偿落库可能排在队列后面不执行。〔**复核轮订正**：我原说"异常被 `except Exception: pass` 吞掉"是错的——那三处是 `except Exception as e: print(f"[chat-placeholder] {e}", flush=True)`，异常**有出口**，只是走 stdout 不入结构化日志、也不重试，与 B-37 同型〕 | A（`llm_guard.py:35` 与 `main.py:2404/2413-2414` 我读过原文；积压后果静态推断，未实测） | 做：占位落库用专用 executor（或把信号量等待从默认池里摘出来），print 改 `logging` |

| B-42 | 中（**复核轮新增**） | 业务主库 `app.db` **从未设 WAL**，而同仓配额库专门设了：`quota_store.py:27` 有 `PRAGMA journal_mode=WAL`，`database.py:13-16` 只有 `check_same_thread/timeout=30`、无 connect handler ⇒ 默认 rollback journal，写锁全互斥。这不是"能不能跑"的问题，而是**与 B-37/B-41 串成组合**：`_post`/`_post_placeholder`/滚动压缩都跑在线程池里与请求 session 并发写同一库，`timeout=30` 耗尽后抛 `database is locked`，恰好掉进那 7 处 `[chat-post]` 的 stdout print 静默通道 ⇒ 用户看到完整答复、历史里没有它，且无结构化痕迹 | A（`journal_mode` 我全仓 grep：仅 `quota_store.py`；`database.py` 本体我读过；旁证：`backend/app.db` 旁无 `-wal/-shm` 伴随文件） | 做：与 B-37 同票——设 WAL（或至少把 `[chat-post]` 改 `logging`），别单独改 journal_mode 就收工（备份脚本需按 WAL 重新验一次，见 §9 的备份口径） |
| B-43 | 中（**复核轮新增**） | `LLM_MODELS_JSON` **整体替换** `DEFAULT_ROLES`（`llm_registry.py:368-372`：非空即 `return json.loads(raw)`），而两份配置的**能力面彼此不重叠**：根 `.env`（compose 用的那份）= 3 条角色 = `text×1 + vision×1 + voice×1` ⇒ **文本档没有回退池**（B-06 一次 400 就把唯一的文本模型标死）；`backend/.env`（本机裸跑用的那份）= 6 条**全是 text、无 vision/voice** ⇒ 同一份代码在本机走 `main.py:1666`/`:1472` 的 501 门，图片问答与语音转写**能力关闭**。而 `rag_chain.py:205-215` 的 F7 注释仍按"1 主 + 6 回退"叙述队列形状——**注释与两份真值都不符** | A（角色分布我用 stdlib 解析两份 `.env` 现数，DEFAULT_ROLES 内置为 text×19/vision×3/voice×5；501 门与替换语义逐行读过） | 做：把"角色并集/覆盖语义"写进 settings 校验并落日志（缺 vision 时 `/api/health` 已能看见，缺回退池现在看不见）；F7 注释按现值更正 |
| B-44 | 中低（**复核轮新增**） | 运维旁路上的**审计与口令卫生**：`scripts/reset_admin_password.py:29` 提供 `--password`（明文进 shell history 与 Linux 进程表），`:33` 虽有 `ADMIN_PASSWORD` 环境变量兜底、`:45` 直接改 hash 后**不写 `log_audit`** ⇒ 与 B-27（改密不吊销已签发 token）叠加，"管理员改密止血"这一事件在后端**完全无痕**（既无审计也没有效） | A（脚本本体我读过 29/33/45 三行；`log_audit` 命中为零） | 做：改密成功后补一条 `log_audit("admin.password_reset")` + 文档注明优先用环境变量 |
| B-45 | 低（**复核轮新增**） | 同族防呆**不对称**：`chroma_dir_guard.assert_matches` 只被 `backup_data.py:129-130` 与 `rebuild_embeddings.py:108` 消费（`switch_embedding` 经 subprocess 复用后者），而 `scripts/import_laws.py` 默认**实写生产库**（docstring `:10` 与 `:171` 的"确认后去掉 --dry-run 实跑"）、按 `file_hash` **替换已有 chunk**，却没有 CHROMA_DIR 一致性守卫 ⇒ 会改写生产索引的三类动作里，只有一类没被同一把锁检查 | A（消费点我 grep 齐；import_laws 默认行为读了 docstring 与 `:164/:171/:241`） | 做：`import_laws` 入口加同一句 `assert_matches`（一行），与它的 `--validate-only/--dry-run` 组成三段闸 |
| B-46 | 低（**复核轮新增**） | "当日"用了两个钟：`main.py:1111`（原判；**§11.4 按新 HEAD 复量 `_cutoff()` 已在 `main.py:1128`，`knowledge_service.py` 那侧本轮未复量**）`_cutoff()` 是 `datetime.now().date()`（**本地**），`knowledge_service.py:326` 的沉淀 `law_as_of_basis` 是 `datetime.now(UTC).date()`（**UTC**）⇒ UTC+8 下每天 00:00–08:00 产出的条目会被标成**前一天**的基准日。而 `knowledge_service.py:318-320` 的注释自称"与 `QaCandidate.created_at` 同一个钟"——那句只对 `created_at` 成立，对 `_cutoff` 不成立。跨分水岭 ±8 小时内还可让"历史/现行"直返判定反向（命中与不命中互换） | A（两侧行号与函数体我都读过；注释半真半假这点是复核轮点出的） | 做：统一取一个钟（建议本地日，因 `_cutoff` 面向用户展示），并把该注释改成可核的断言 |

另有 4 条低档项不单列编号，在 **§4.6** 展开（复核轮指出：我原先声称它们"折入 §4 与 §5"而实际两处都没有——措辞已订正）。

---

## 1. 方法、范围与读数（现量）

**范围与规模**（我自己量的，命令附后；口径=排除 `.*` 隐藏目录与 `__pycache__`）：

| 位置 | 文件数 | 行数 |
|---|---|---|
| `backend/*.py`（顶层，含 main/retrieval/…） | 45 | 12,690 |
| `backend/agent/` | 20 | 6,923 |
| `backend/tools/` | 8 | 804 |
| `backend/scripts/` | 73 | 11,570 |
| `backend/tests/` | 119 | 30,851 |

生产代码口径取前三行 = **20,417 行**（`main.py` 单文件 2,920 行是本轮最大单体）。本轮**未审**：`backend/scripts/*` 的评测/导入脚本内部逻辑（只读抽样了 `import_laws.py`/`import_docs.py`/`rebuild_embeddings.py`/`switch_embedding.py`/`backfill_time_meta.py` 的写侧与危险路径）、`backend/tests/` 全文（只用于反证检索）、`frontend/`。

**取证纪律**：
1. 每条结论带绝对路径:行号 + 原文引用；行号我自己在 Read 里看过。
2. 判"某键不存在"用的是**读文件/查库本体**，不是两段式 grep；`category`/`version_id` 的缺失由我在本机以只读 URI 打开 `backend/chroma_db/chroma.sqlite3` 复现（命令见 §8 附录 A）。
3. 判"正则窄"用的是把 pattern 逐字复制到 `/tmp` 的独立解释器里跑，不 import 项目模块（命令见 §8 附录 A）。
4. 未执行项目代码：没跑 pytest，没跑 `backend/scripts/*`（两个 smoke 脚本会 `os.chdir` + `load_dotenv(".env")` 打到真实配置与真实配额库）。因此**所有"运行时后果"都是静态判定**，凡我没能坐实可达性的都标了 C。
5. 工作树状态：本轮起点 HEAD `5be6e05`；工作树有大量未跟踪产物（`dispatch-output/`、`_diff_*.txt`、`.ptmp-*`、`backend/.ptmp-*` 等）。**我没有改动任何在册文件**，`git status` 的脏项全部来自并行会话与历史产物。〔**第二轮复量（`0b54396`）**：`git status --porcelain --untracked-files=no` 现 6 项，**backend 为 0 项**（脏项在 5 个前端文件 + 1 份 plans 文档，属别的会话），且 §12 跑完定向用例后这四个读数逐字未变：`backend/app.db` sha256、`backend/data/quota_used.sqlite` sha256、`backend/chroma_db` 38 文件/365,566,410 字节、dirty 计数 6（复现见 §12 开头）〕

**与今日另一份审查的关系**：`docs/process-archive/agent-harness-audit-20260929.md`（同日另一会话，Agent harness 专项，H-01…H-12 + D1…D8 待裁）与本报告在 agent 路径上有重叠。本报告**不重报**其 H-01/H-02/H-03/H-04/H-05/H-08/H-09/H-12 已登记的结论，只在 §6 给出交叉引用与差异点（差异：本报告的 B-01/B-04/B-05/B-16 是那份没有的）。

---

## 2. 重点缺陷详解（高档 + 复核后改判的条目）

### B-01 恰好在预算终点的"成功"会被自己的预算机制炸掉（高）

- 位置：`C:\Users\33393\Desktop\ai-legal-helper\backend\agent\chat_integration.py:223-229`、`...\backend\agent\service.py:212-215` 与 `:635-641`、`...\backend\agent\state_machine.py:34-58`、`...\backend\routing_metrics.py:13-20`（复核轮订正：白名单frozenset 收在 13-20，我原先写 13-21）
- 机制（我逐段读过）：`transition()` 每次转移做 `steps+1` 并 `_limit(...)`，越界抛 `BudgetExceeded`（它继承 `RuntimeError`，**不是** `InvalidTransition`）。终稿落库点做的是 `DRAFTING → COMPLETED` 这一跳，而它外层只 `except InvalidTransition`。于是这一步越界时异常裸抛，被 service 的兜底 `except Exception` 接住映射成 `AGENT_STORAGE_FAILURE`；该码不在 `TECHNICAL_FALLBACK_REASON_CODES`（白名单只有 PLANNER_PARSE_ERROR / TOOL_TIMEOUT / TOOL_UNAVAILABLE / AGENT_BUDGET_EXCEEDED / VERIFIER_TECHNICAL_FAILURE），所以 `_failure_or_fallback` 走 `"failed"` 分支 ⇒ SSE 发 `error` 而**不发** `restart`，用户既没有 Agent 终稿也没有快车道兜底答案，run 停在 `drafting`（resume 只认 `WAITING_USER`，API 上再也无法恢复）。
- 决定性证据（对称性）：同一个 service 里**失败**收尾路径 `:212-215` 明确写了

  ```python
  try:
      failed_state = transition(state, AgentStatus.FAILED)
  except BudgetExceeded:
      failed_state = state.model_copy(update={"status": AgentStatus.FAILED})
  ```

  说明作者知道"转移本身可能因预算越界"，唯独**成功**落库路径没有这层处理。`_persist_budget_stop`（controller）同理。
- 可达性（C，需坐实）：controller 的单工具与批量预检口径都是 `steps + 3 > max_steps`（`agent/controller.py:726`、`:970`），`agent_max_steps` 默认 20（`settings.py:94`，注释记载 8→16→20 两次上调就是被 `budget_exceeded:step_preflight` 逼的）⇒ 形如"预检时 steps=17 → EXECUTING 18 → EVALUATING 19 → 确定性终稿门 DRAFTING 20"的形状不被任何预检挡住，随后 COMPLETED 需要第 21 步。我**没有**跑起来实测这条序列。
- 反证检查：子 agent 报告 `tests/test_agent_chat_integration.py:1878` 起的两个预算回归只钉"不得提前 STOP、要走到起草"，其场景终态 steps≤19；`:1563-1620` 钉的是 OSError/版本冲突两类落库失败。我未独立复跑该文件，结论按 B 级采信其检索。
- 建议验证（不要执行，供派单）：定向用例 `test_finalize_when_steps_at_budget_limit_reports_budget_exceeded`——FakeRepository 把 state 置为 `status=DRAFTING, steps=budgets.max_steps`，直接调 `persist_agent_final_once`，断言**当前**抛 `BudgetExceeded`（红），修复后应产出 `outcome=fallback, reason_code=AGENT_BUDGET_EXCEEDED`。

> **§12.1 已按这段跑掉（副本树定向用例，4 腿 4 passed）**：这条建议用例的当前行为**确认为红**——抛的是 `BudgetExceeded`（reason 逐字 `budget_exceeded:steps`）而不是 `AgentFinalizationConflict`，`service.py:618-641` 的 `except Exception` 把它折成 `AGENT_STORAGE_FAILURE`，查库见"0 条 assistant 消息 + run 仍 drafting"。对照腿 `steps = max_steps-1` 返回 `True` 证明夹具非空转。"修复后应产出 `AGENT_BUDGET_EXCEEDED`"这条路是通的：该码在 `routing_metrics.py:13-21` 白名单里，而 `AGENT_STORAGE_FAILURE` 不在。可达性那一段（本行上方标 C 的）现由 L4 升 A：`EVALUATING@cap-1 → DRAFTING` 实测不报错且落点恰为 cap，两处 `steps + 3` 预检结构上挡不住 1 步边。**同一根的另一半（恢复边）比终稿边更常撞，已扩成 B-47，见 §12.2。**

### B-03 近重复缓存命中：答案与证据清单不同源（高）

- 位置：`C:\Users\33393\Desktop\ai-legal-helper\backend\answer_cache.py:22-26`（`make_key` 定义在 22、拼 key 的 `raw=` 在 **25**——复核轮订正我原先把该行标成 22）、`:39-69`、`:72-92`；`C:\Users\33393\Desktop\ai-legal-helper\backend\main.py:1859-1885`
- 我读到的原文：

  ```python
  # answer_cache.py:25  精确 key 含 cutoff 与证据集合
  raw = "|".join([text or "", intent or "", cutoff or "", ids])
  # answer_cache.py:72  近重复判据里既没有 cutoff 也没有证据集合
  def get_similar(q_embedding, *, polarity="", option_count=0, label_system="", options_fingerprint=""):
  # main.py:1863/1878   下发的是本轮检索的 sources
  ca = hit["answer"]
  yield f"data: {json.dumps({'conversation_id': pre['conv_id'], 'sources': pre['sources']}, ...)}\n\n"
  ```
- 为什么是缺陷（不是风格）：近重复命中**按定义**发生在"精确 key 不等"时，而精确 key 里已经钉了 `cutoff` 与 `(source|article)` 集合 ⇒ 命中时二者必然可以不同。`put` 存的 `sources` 与 `model` 两个键，我在 `main.py`/`answer_cache.py` 里找不到任何读点（`hit["sources"]`、`hit.get("model"` 全仓零命中）。后果两条：①前端法条卡片显示的条文与正文答案依据的条文可以完全不是同一集合——正是本产品"引用可溯源"的核心约束；②同一份 `pre["sources"]` 还被 `_post` 喂给 `citation_grounding(answer, pre["sources"], _grounding_stats)`，于是缓存复用轮的真实引用被判"在库未召回"，评测里报的漏召回率被系统性抬高。
- 补充读数：非选项题时 `polarity/option_count/label_system/options_fingerprint` 四道护栏全是默认值（空/0），实际只剩"余弦 ≥ 0.95"一道；TTL 6 小时可跨日。
- 反证检查：`docs/gate-exit-registry.md` 的 E1 行把"引用校验"记为 `GAP-ACCEPTED`，但理由只覆盖"读侧不复判引用存在性"，**没有**覆盖"sources 帧与答案不同源"。`tests/test_cache_similar.py` 测的是命中判定与选项指纹护栏，无 sources 一致性/跨日断言。两个子 agent（API 层与 RAG 层）独立给出同一结论。
- 建议验证：用例 `test_similar_hit_delivers_cached_sources`（预置 answer=《劳动合同法》第十九条，第二次请求把 `retrieve` 桩成返回另一条文，断言 sources 帧 = 条目自身 sources，或断言此时必须 miss）+ `test_similar_hit_must_not_cross_cutoff_day`。

### B-04 Agent 引用防线的"无名条号"盲区（高）

- 位置：`C:\Users\33393\Desktop\ai-legal-helper\backend\agent\writer.py:380-412`（四份引用模式全部要求法名锚）、`:424`、`:655-667`（数字兜底只认 ASCII）、`:973`；`backend\agent\verifier.py:429`；`backend\retrieval.py:243-247` + `:547-556` + `:559-568`
- 我读到的原文：

  ```python
  # writer.py:664  数字 token 兜底：只有 ASCII 数字会被收集
  for match in _ASCII_NUMBER_RE.finditer(normalized):
      if not any(occupied[match.start() : match.end()]):
          tokens.add(f"number:{_canonical_number(match.group(0))}")
  # writer.py:973  引用子集判据（提取两侧都需要法名锚）
  if not canonical_citations(proposed.text).issubset(canonical_citations(bound_evidence_text)):
  ```
- 不对称后果：claim 写"依据第五百七十七条"（中文数字、无法名）⇒ `canonical_citations` 提取集为空（子集恒真）、`_ASCII_NUMBER_RE` 不认中文数字（零 token）、`has_noncanonical_citation` 也要法名（不判非规范）、终稿 `citation_verify` 用 `_ART_FULL_RE`（看不见）⇒ 四道门全绿，**编造的裸条号可整段交付**。反之写"依据第577条"会因 `number:577` 无来源被拦（连真实引用一起误杀）。唯一约束是提示词（`prompts.py` 要求《法律全称》第X条），提示词不是机械门。
- 归因层次：这是**防线覆盖**问题而非精度问题——我在 §3 把这条与 B-14 一起归为同族："校验通过的语义是'所有*能看见的*引用都在库'，不是'所有引用都在库'"。
- 反证检查：`test_agent_writer.py:948-1007`、`test_agent_verifier.py:729+`、`test_smoke_citation_assertions.py:167-205` 的样例全部带法名（按 B 级采信子 agent 的检索）；`test_smoke_citation_pairs` 明确记了"散文里隔开的裸条号不补（与生产同界）"——那是**快车道**的在册边界，不能读成"agent claim 里造裸条号可过全部门"是被接受的。
- 建议验证：纯函数用例：`canonical_citations("第五百七十七条规定")` 断言非空，或新增"无名条号"门并断言该形态 fail-closed；另需一条端到端（副本树）用例证明 writer→verifier→finalize 对该输入的红。

### B-05 `category` 过滤键在现网库里不存在（高，且"开 Agent 即炸"）

- 位置：`C:\Users\33393\Desktop\ai-legal-helper\backend\retrieval.py:733`（`filt = {"category": category} if category else None`）、`:903-904`、`retrieval_core.py:220`（BM25 侧同样按 category 剔除）、`backend\tools\contracts.py:89`（`RetrieveLawsInput.category` 是 100 字自由文本、无白名单）、`backend\agent\runtime.py:85`（planner 提示词明写"category 可选"）
- 我在本机实测（只读 URI，命令见附录 A）：

  ```
  legal_provisions_cos : n=10266 keys=[article, chapter, chroma:document, effective_from, effective_to, file_hash, origin, source, status]
  legal_provisions_te4 : n=10266 同上
  category: KEY ABSENT（rows_with_key=0）   version_id: KEY ABSENT
  status: [('现行', 10266])  origin: [('upload', 10266)]  effective_from/to: 全为空串  distinct sources: 99
  ```
  写侧也印证：`scripts/import_docs.py:108` → `knowledge_service.add_chunks` 不写 category，只有 `knowledge_base.py` 的 seed 路径写（现网 seed=0）。
- 后果链：Chroma 的 `$eq` 对不存在的键无法命中 ⇒ v 路 0 条、BM25 路 0 条 ⇒ `hybrid_retrieve` 返回 `[]` 并把空结果写进缓存 ⇒ 工具 `statement="未检索到匹配的法律资料。"`（`tools/legal_retrieval.py:69`），Agent 记为证据缺失/拒答。**看起来像"库里没有"，实际是键名假设错**（幻觉四类之 schema 字段编造 + RAG 五段之检索段）。
- 现状缓解：`agent_enabled` 默认 False（`settings.py:83`）⇒ 今天不是现网故障，是放量地雷。
- 反证检查：`tests/test_tool_gateway.py:574-584` 用假 `retrieve` 断言 category 被**透传**——恰好证明没人验过真库能否过滤出东西；`tests/test_phase2.py:64-72` 用的是自带 category 的合成 Document。
- **仓内已有这条规则、只是没落到 `category` 上**：`backend\knowledge_service.py:150-151` 的 `add_chunks` docstring 原文写着"时效三键归一化（阶段5）在此统一处理：空值写 `""`，status 缺省'未验证'（**Chroma where 对缺失键语义不可靠，缺键会破坏时效过滤**）"。也就是说"缺键 → where 失效"是本项目**已承认并已在时效三键上规避**的机制（时效键被无条件写成 `""` 而非省略），但 `category` 既从不被写入、又出现在 `where` 与 BM25 过滤里 ⇒ 这不是认知缺口而是覆盖面缺口，修法可以直接沿用时效三键的同一条纪律（要么补齐写侧、要么把键从可选面摘掉）。
- 建议验证：`test_retrieve_with_unknown_category_falls_back_to_no_filter`；或把 `category` 从提示词与 schema 同步摘除（注意 H-07"四个真源"的等值断言要一起改）。

> **§12.3 已按这段跑掉**：chromadb 0.4.24 现场九腿实测确认——**全集合缺该键时用生产形状 `{"category": X}` 返回 `[]`**（同集合无过滤返回全量作对照），且 **`$ne` 也排除缺键行**，所以"补齐写侧"或"摘掉可选面"两条里**没有第三条逃生门**（不能靠改成 `$ne` 或 `NotIn` 绕开）。上面那条"仓内已有这条规则"的 docstring（`knowledge_service.py:150-151` 承认"Chroma where 对缺失键语义不可靠，缺键会破坏时效过滤"）**本轮得到实证支持**——时效三键正是靠"缺省也无条件写空串"规避的，`category` 则从不写、又进 `where`。可达性也补硬了：`agent/runtime.py:85` 的 Planner 系统提示词**明写「category 可选」**，即模型被主动邀请传它。历史触发频率仍读不出来（`agent_steps.normalized_input` 是 64 位 sha256，不是 JSON——我第一次按 JSON 去 LIKE 得 0 是尺子空转，已在 §12.3 作废该读数）。

### B-06 provider 4xx 的永久耗尽 + 零日志（高，触发前提待坐实）

- 位置：`C:\Users\33393\Desktop\ai-legal-helper\backend\main.py:2205-2213`、`backend\llm_errors.py:25-27`（`TRANSIENT_STATUS = {408,429,500,502,503,504}`，其余 4xx 判永久）、`backend\llm_registry.py:569-580`（`mark_depleted` 函数体只有 5 行，`reason` 参数被完全忽略，**不打任何日志**）
- 我读到的原文：

  ```python
  # main.py:2210-2213
  _tried.add(current["key"])
  if not is_transient_error(_e):
      registry.mark_depleted(current["key"], "model_failure")
  # llm_registry.py:576-580
  e = self._entries.get(key)
  if not e or e.depleted: return
  e.runtime_used += max(0, e.quota_left)     # remaining → 0，本进程内永久 unavailable
  ```
- 攻击/触发路径：任意**已认证普通用户**发一条让供应商返 400 的请求即可（超长 content + 多轮历史撑爆上下文 → `context_length_exceeded`；中文案情触发 DashScope 内容审核 → 同样 400）。`stream_with_retry` 用**同一份 payload** 换下一个模型继续 400 ⇒ 逐个打死；DEFAULT_ROLES 有 18 个 text/flag 条目，一条请求可扫掉若干，扫完 `pick` 抛 `QuotaExhausted` ⇒ 全站 `/api/chat` 对所有人（含管理员）503。恢复只有两条路：重启进程，或管理员手工按控制台校准。
- 与在册结论的差别（重要，别误读成重报）：`llm_errors.py` 顶部 docstring 已登记 2026-09-17 的实证事故"SDK 包装的连接错误被判永久 → 6 模型全标死"，那条**已修**（类名 + 异常链上溯）。我报的是残余：*payload 形状导致的 400 仍按"模型坏了"*，且*停用无痕迹*。`tests/test_llm_failover.py:163-166` 是**故意**把 400/401/403/404/422 钉成永久的（模型名打错、鉴权失败该被摘），我不建议改成瞬时。
- 未坐实的部分（C）：我没有证据表明 DashScope/LongCat 兼容端点确实会因用户内容返 400。只读核法：Owner 可 `grep -a '"llm_error_status_code": 400' backend/logs/*.log` 看历史是否发生过；若发生过，本条从"可触发"升级为"已发生"。
- 建议验证：`test_400_from_oversized_payload_does_not_deplete_model`、`test_mark_depleted_emits_structured_log`（注意 `observability.py` 的字段白名单会静默丢新字段，动 `extra=` 必跑 `test_log_field_whitelist`）。

> **§12.4 已跑掉能跑的那一半**：真 `openai 1.109.1` 打 `127.0.0.1` 状态码 stub，逐格对上——`400/401/403/404 → is_transient_error=False → mark_depleted`；`408/429/500/502/503/504 → True → 只排除`；**未监听端口 → `APIConnectionError` → True**（`llm_errors.py` 顶部登记的 2026-09-17 包装形态事故，其修复在真 SDK 形状下成立）；**同一 400 连打三次同判** ⇒ "同一份 payload 换模型继续 400" 的逐个打死机制得到实证。**但本条上面那句"未坐实的部分"仍不能坐实**：预案里的 `grep -a '"llm_error_status_code": 400' backend/logs/*.log` 在本工作区**无物可 grep**——`find logs -type f` 实测 0 文件（目录不存在），所以"历史上是否真发生过"仍是未知，不升级为"已发生"。分类口径不动（`tests/test_llm_failover.py:167-170` 钉 permanent、`:160-164` 钉 transient，行号按 `0b54396` 复量）。**新增的是归因面 B-48（§12.4 末段）：`mark_depleted` 把"被判死"实现成 `runtime_used += quota_left`，且 `reason` 参数被丢弃 ⇒ 管理台与 `quota_store` 看到的是"这个模型积分用完了"，而真实成因是"请求被拒"——不是没记，是记成了另一种病。**

### B-07 沉淀闸门用错了判据对象（高，数据段污染）

- 位置：`C:\Users\33393\Desktop\ai-legal-helper\backend\main.py:996-1000`、`backend\knowledge_service.py:376-398`、`backend\retrieval.py:424-434`、`backend\main.py:2319-2347`
- 我读到的原文：

  ```python
  # main.py:996-1000  沉淀入口：分数取自"问句与库的 top-1 余弦"，与答案文本无关
  if curate and pre.get("intent") == "legal_query" and not pre.get("law_as_of"):
      grounded = grounded_top_score(pre["rewritten"])
      if q and should_curate(grounded, answer):
          ks.create_candidate(db, q, answer, grounded, json.dumps(pre["sources"], ensure_ascii=False))
  # knowledge_service.py:≥AUTO_CURATE_THRESHOLD(0.89) 直接 add_qa_pair 并标 approved（管理员看不到）
  ```
- 三条叠乘：①`self_check` FAIL（`cite_bad:N` = 答案里有**不在库**的引用）之后流程照样走到 `_post(pre, answer)`，`sv.ok` 不是沉淀的前置；②判据说的是"问句检索得好不好"，不是"这条答案有没有据"；③evidence 写的是 `pre["sources"]`（本轮检索，构造上必在库），而读侧 `retrieval.qa_citations_in_kb` 解析的正是 evidence ⇒ 该判据对自动沉淀条目**恒真**。净效果：一次 top-1 余弦 0.90 + 模型把条号写错一位的答案，可以既下发（带注记）又**进持久语料**，之后同问句 ≥0.92 命中即零模型、零校验复读。
- 反证检查：ADR-006 记的是"高置信进候选 + 管理员确认"，`AUTO_CURATE_THRESHOLD` 是 2026-08-07 Owner 要求的免审例外（在册）；`test_knowledge_service.py::test_create_candidate_auto_approve` 钉住"≥阈值自动收录"这件事本身。我**没有**找到任何用例把 `self_check` 结果与沉淀入口连起来，也没有"答案正文引用 ⊆ evidence"的断言。ADR-010 只承认"自检不能保证引对题"，未承认"FAIL 的答案也进沉淀"。
- 建议验证：`test_curate_requires_self_check_pass`、`test_qa_pair_evidence_covers_answer_citations`。

### B-02 / B-17 / B-25 三条"部署形态"高危的复现读数

这三条的说服力全在只读命令上，我在本机复跑过：

```bash
# B-02 限流 key：CF 头无条件优先（main.py:169-188），而 cloudflared 不在 compose 编排里
grep -n "CF-Connecting-IP\|_rate_key" backend/main.py
grep -n "ports:" -A2 docker-compose.yml           # "8088:80" ⇒ 绑 0.0.0.0
grep -n "header_up\|request_header" Caddyfile      # 无剥头配置
grep -rn "_rate_key\|CF-Connecting-IP" backend/tests/   # 零命中：无测试钉住优先级

# B-17 登录锁定窗口锚在首次失败（main.py:384-392），ts 在 cnt>0 时永不刷新
grep -n "_LOGIN_FAILURES" backend/main.py

# B-25 .env 备份的忽略来源是本地 exclude，不是 .gitignore
git check-ignore -v .env backend/.env "backend/.env.bak-20260910-pre-qwen38"
#   .gitignore:26:.env        .env
#   .gitignore:26:.env        backend/.env
#   .git/info/exclude:9:.env.bak*   backend/.env.bak-20260910-pre-qwen38   ← 唯一命中源
git log --all --oneline -- '.env' 'backend/.env' 'backend/.env.bak*'    # 空 ⇒ 历史干净，是未来风险
grep -n "repo\|detect-secrets\|gitleaks" .pre-commit-config.yaml         # 无密钥扫描钩子
```

B-25 的泄密面具体是：那个 `.bak` 文件里有 7 个凭据**键名**（`LLM_API_KEY / JWT_SECRET / ADMIN_PASSWORD / EMBEDDING_API_KEY / RERANK_API_KEY / ZHIPUAI_API_KEY / DASHSCOPE_API_KEY`，我只读键名未取值）。`info/exclude` 不随仓库走 ⇒ 新克隆 / 换机 / CI 工作树 / 把目录复制给别人 的场景里它不存在，一次 `git add -A` 就把真实密钥提交进有 GitHub 远端的仓库。修法注意：加 `.env.*` 要配 `!.env.example`，否则连模板一起忽略。

---

## 3. 跨模块系统性判断（四条，比单条 bug 更值得决策）

**1）引用防线的"覆盖"弱于"精度"。** 精度侧是全仓最扎实的：`article_in_kb` 做的是 `(source, article)` **配对**校验（`retrieval.py:499-509`，先按 `where={"article": art}` 取，再按 `_source_key` 比归一化源名，跨法编造判得掉），`_source_key` 去"中华人民共和国"前缀并去全角年份括注（`retrieval.py:443-449`；我实测库里确有 `宪法（1982年）`，该处理有真值支撑）。但覆盖侧有三处看不见：**B-04**（无名条号）、**B-14**（72 部库内法的裸名引用）、**B-13**（千级条号在沉淀/评测侧不可见）。净效果是"校验 PASS"的真实语义 = *所有被正则看见的引用都在库*，而不是*所有引用都在库*。这三条可以一次性收（把法名全集与条号字符类做成单一真源），收益远大于逐条打补丁。

**2）"沉默的降级"比"响的降级"多。** 我核到的四处都是"失败但不留痕"：`mark_depleted` 零日志（B-06）、缺 provider key 被 `llm_registry._load` 无声 `continue`（B-26）、docx 修订告警在运行时上传路径被丢弃（B-24）、`_post` 落库失败只 `print(f"[chat-post] {e}")` 既不发 error 帧也不重试（B-37，见下）。它们共同的后果是**运维无法归因**：模型为什么没了、能力为什么 501、报告为什么少了一段条款、历史为什么丢了这一答，全都没有可查的痕迹。这一类在本仓不是能力问题而是纪律问题——`observability.py` 已有字段白名单与哨兵测试，缺的是"每条失败路径都记一次"的习惯。

- **B-37**（已在 §0 表内，此处只补它与本条主线的关系）：`main.py` 里 **7 处** `[chat-post]` + 3 处 `[chat-placeholder]` + 1 处 `[chat-stream]` 的 `print(...)`（行号见 §0 B-37），全是"失败有出口、但不进结构化日志"的形状。子 agent 指出 `_post` 抛错时 `_posted` 保持 False ⇒ `finally` 会用 `_post_placeholder` 补一条"服务暂时无响应"，而屏幕上用户看到的是完整答复——历史与所见相反。我确认了代码顺序（`_posted = True` 只在 `_post` 成功后置位），但**没有**实测注入 `_post` 异常，故后果面按 C 处理，且需 Owner 判"占位补偿"是否本就被当作正确行为（在册修复 #5/#8 是把占位当正确补偿的）。**这一条与 B-41 是同根**：占位与补偿都挤在 default executor + stdout print 上。

**3）"原子/防竞态"类修复存在只落一半的形状。** 同一批对抗审计 v2 修复，#20（同步阻塞→线程池）与 #21（DB 原子自增）都只落了部分调用点：`deduct` 全进了 `run_in_threadpool` 而 `citation_verify`/`self_check` 没有（B-09）；`request_bootstrap.py:389-392` 的自增是纯 `query().update()` 而 `main.py` 两处是"原子 SQL + 紧随的 ORM 绝对赋值"（B-08）。这提示一条可执行的治理：**每个"已修"编号应配一条形状哨兵测试**（如"该函数内不得出现对 `conv.message_count` 的属性赋值"），否则文档上的已修与代码实际状态会长期背离。B-11 是同一问题的极端版本——一个已被文档登记为"已实现"的修正在数学上是恒等操作。

**4）进程内可变全局是这个架构的隐性天花板。** `_contract_convs`/`_clarified`/`_LOGIN_FAILURES`/`answer_cache`/`retrieval._cache`/`llm_registry` 的 depleted 标记**全部是进程级**（B-28、B-17、B-06）。`docker-compose.yml:11-13` 明写单 worker 是契约（多 worker 会撞本地 Chroma/SQLite 锁）——这条在册约束是**对的，不要有人手贱加 worker 数**；但正因如此，B-28 的 rowid 复用与 B-03 的跨用户缓存在今天就是活的，而不是"多 worker 才需要管"。

---

## 4. 死代码 / 在册残留 / 真源漂移

> 专责本节的第 5 个子 agent 在跑完前掉了（后台任务返回 empty result，未交付结论），所以本节是**我自己重跑的引用清查**，覆盖面比原计划窄（见 §9 第 6 条）。方法：用 stdlib 解析 `settings.py` 字段名与 `models.py` 列名，再对每个名字在**生产代码**（排除 `tests/`、`scripts/`、`venv`、`.ptmp-*`）里搜访问点，并对候选逐个回读文件本体确认"写入但无人读"还是"从未写也从未读"。
>
> **我踩到的一个假阳性，留在这里当方法警告**：`settings.agent_writer_corrective_retry_enabled` 按 `settings.<字段>` 静态搜索是**零命中**，但它其实被 `agent/service.py:413` 用 `getattr(settings, "agent_writer_corrective_retry_enabled", False)` 动态读着。任何"某字段/某符号没被用"的结论都必须再过一遍 `getattr(`/`__getattr__`/字符串键写入这三类动态引用，否则会误报死码。

### 4.1 真死码（生产与测试都零消费）

| 对象 | 位置 | 读数 | 分类 |
|---|---|---|---|
| `AgentRun.goal` / `AgentRun.task_type` | `backend\models.py:140-141` | `create_run`（`agent/repository.py:69-77`）不赋这两个字段，全仓（排除 venv/tests）无任何 `.goal` / `.task_type` 访问点 ⇒ 只有 ORM 列默认值 `""` / `"legal_research"` 在每次插行时写入 | **写默认值、零读**（真死列） |
| `AgentRun.budget_snapshot` / `AgentRun.verifier_verdict` / `AgentRun.updated_at` / `Message.token_est` | `models.py:173`、`:211`、`:150`、`:62` | 都有写入点（`chat_integration.py:302/313`、`repository.py:146`、`main.py:1901/1930/1959/2166/2380`），但**没有任何读点**（既不进响应，也不参与判定） | **写而不读**（审计噪音；`updated_at` 靠 `onupdate` 生效但无人取用） |
| `settings.admin_password` | `settings.py:54-56` | `settings.admin_password` 全仓零命中；真实取数走 `os.getenv("ADMIN_PASSWORD")`（`seed_admin.py:17`、`scripts/reset_admin_password.py:33`、`scripts/_client.py:47`） | **在册死字段**（注释已自陈，是 08-07 审计第 7 项的落地结果，**不建议顺手删**——留着是为了挡"看似已配置密码"的假象） |
| `tools/gateway.shutdown_default_executor` / `wait_for_idle` | `tools/gateway.py:107`、`:89-96` | 只有 `__all__`/懒导出与 `test_tool_gateway.py` 引用；`main.py:245-256` 的 lifespan 不调用 | B-35（链条死码：关停路径没接线） |
| `agent/limitation_calc.calc_limitation` | `agent/limitation_calc.py:22-31` | 仅 `tests/test_limitation_calc.py`、`tests/test_review_regressions.py` 引用；同文件的 `controlled_limitation_tokens` **有**生产接线（`writer.py:961`、`verifier.py:439`） | 测试型死码（docstring 自己写"由调用方（**未来的**）传入"） |
| `agent/writer.py` 的聚合版 `render()` | `writer.py:746-751` | 生产零调用，docstring 自陈"测试与对外便捷入口" | 在册便捷入口，不算缺陷 |

**跨会话重复提示**：`tools/clarification.py` 的 `ask_user` 生产不可达、`verifier.py:480-486` 的 `verifier_research_returns` 永不自增导致 `FAIL_SAFE` 分支不可达——这两条与今日 `docs/process-archive/agent-harness-audit-20260929.md` 的 **H-02（五条假器官）** + **D1/D7** 是同一件事，**本报告不重报、不重复派单**。注意那份报告的 D7（"接一次回炉"）与"RESEARCH_MORE 回喂是 Ticket 2 有意删除"的在册口径存在张力，清理前要一并裁。

### 4.2 requirements：这一项**没查出问题**（诚实结论）

21 个声明包按包名反查 import，只有 `python-dotenv` 与 `python-multipart` 匹配不上，而两者都是**真在用**：前者以 `from dotenv import load_dotenv` 形式使用，后者是 FastAPI 表单解析的隐式运行时依赖（不需要显式 import）。⇒ 本轮**未发现"声明但从不使用"的依赖**。真正的依赖侧缺口是 B-39（无锁文件导致 CI 审的字节 ≠ 镜像里的字节），不是死依赖。

### 4.3 真源漂移（同一概念多份实现，已经不同步）

| 概念 | 份数与位置 | 差异与真实后果 |
|---|---|---|
| 条号字符类（"什么算一条引用"） | **7 份**：`retrieval.py:243`（含 千/万/〇/○/全角）、`output_normalize._ART_CORE`、`chunking.ARTICLE_RE`、`clarify`（复用 `retrieval.extract_citations`）、`agent/writer.py:380-405`（含 两/亿）、`contract_verify.py:155-158`（**窄版，但有注释自陈取舍**）、`curation.py:8` + `eval_metrics.py:12`（**窄版，无自陈**） | 我在本机跑过：`依据《民法典》第一千二百五十四条` 对 `curation.has_citation`、`eval_metrics.citation_present` 都是 **False**，对 `retrieval._ART_FULL_RE` 是 **命中**。⇒ 千级条号（高空抛物 1254、过错责任 1165、继承 1127、交强险顺位 1213 —— 现网最大用法域）的答案**永不进待审队列**（无日志无告警，只有计数不涨），评测同步低报。= **B-13** |
| 中文条号 → 数字 | **4 份**：`retrieval.py:470`（复核轮订正：`def _cn_article_to_num` 在 470-471，注释自称同口径的那行在 452）、`agent/writer.py:444`、`scripts/capture_eval.py:94`、`contract_verify.py:165`（无 万/〇/全角/之X） | `retrieval.py:452` 的注释自称"与 capture_eval 的判定**共享同一口径**"——实为两份独立实现，"同口径"是靠人维护的断言不是机制。CONTRIBUTING.md 要求"新硬编码的条文映射放进 `domain_rules`"，这 4 处都在射程外 |
| 法名集合（哪些名字算"库里的法"） | `output_normalize._COMMON_LAW_NAMES`（**手抄 28 部**）vs `retrieval._ensure_src_set()`（**库内实测 99 部**） | 后者已在手但没与前者对齐 ⇒ 归一化后 72 部库内法的无书名号引用不进校验（计数复现见 §8 第 8 组命令）。= **B-14** |
| 有据分阈值 | `curation.DEFAULT_GROUNDED_THRESHOLD=0.7`（待审线）与 `knowledge_service.AUTO_CURATE_THRESHOLD=0.89`（免审线） | 两段是**刻意**的（免审线是 08-07 Owner 要求的例外），不算漂移；B-07 的问题不在"两份阈值"，而在**判据用错了对象** |
| 配置读取口径 | `retrieval.py:654` `HYBRID = settings.feature_hybrid`（import 期快照）vs `retrieval.py:889` 运行时读 `settings.query_rewrite_enabled`；另有 `multimodal.IMAGE_LIMITS` 也是 import 期快照 | 今天所有 flag 只在启动读 ⇒ 不构成缺陷；但两种口径并存，一旦将来加管理端热切换就会打架（与 B-26 的"改了不生效"同源） |

### 4.4 幽灵注释（注释/docstring 与代码事实不符，本轮我复核过的 7 条）

1. `main.py:979`、`:1022`「原子自增（…防读-改-写竞态）」——紧随其后的 `conv.message_count = (conv.message_count or 0) + 1` 让这条 SQL 的原子性失去意义。= **B-08**。
2. `main.py:173`「CF-Connecting-IP（cloudflared 注入的真实 IP，**不可伪造**）」——把一个部署形态假设写成代码事实，而同文件 `:218` 对 Content-Length 恰恰写了"可被伪造，这只是第一层防御"。= **B-02**。
3. `retrieval.py:975-976`「截断后把被挤出的锚点保底条文补回（优先于尾部精排项）」+ `docs/process-archive/audit_report_20260807_v2.md` 把 #19 登记为已修——实为恒等操作。= **B-11**。
4. `answer_cache.py:53-54`「近重复命中所需元数据（embedding/护栏/指纹/**model**）由调用方提供」——提供了，但 `get_similar` 既不比 model 也不比 cutoff，`sources` 全仓无读点。= **B-03**。
5. `retrieval.py:452`「与 capture_eval 的判定共享同一数字口径」——两份实现，非共享。见 §4.3。
6. `auth.py:4-8` 是一段**已经修好**的反例：09-10 把"服务器为 3.10 需 `timezone.utc` 兼容"这句过期注释据实更正了。列为正例，说明这类漂移在本仓是可修的纪律。
7. `knowledge_service.py:150-151`「Chroma where 对**缺失键**语义不可靠，缺键会破坏时效过滤」——这条规则**是真的**，且现网时效三键确实因此被无条件写成 `""`；但同一个 `where` 机制上的 `category` 从不写入却参与过滤（`retrieval.py:733`）。= **B-05** 的根因层：**规则在册、覆盖面漏**。

### 4.5 若要清理，建议的顺序与风险（只给建议，本轮不做任何修改）

1. **先做零风险的两项标注**：给 `AgentRun.goal/task_type/updated_at/budget_snapshot/verifier_verdict` 与 `Message.token_est` 加"写而不读/仅默认值"的行内注释，或直接不进 INSERT——**不要删列**（删列触发迁移，且历史库里的值不可再生，与 D5 的新列一并做才划算）。
2. **再收 B-13/B-14 的真源**：把条号字符类与法名集合收进 `domain_rules`（法名从 `_ensure_src_set()` 派生），这一步同时消掉 §4.3 前三行与 B-14。
3. **然后补 B-11 这类"注释承诺但代码没做"的形状哨兵测试**：每条在册"已修"编号配一条断言（如"`_post` 内不得出现对 `conv.message_count` 的属性赋值"），否则文档与代码会长期背离。
4. **不许顺手动的承重件**：
   - `tools/contracts.py:235`「`status=='现行'` 且无生效日 ⇒ `legal_validity='effective'`」——我实测现网两集合 10266 条正是这形状（status 全 `现行`、`effective_from/to` 全空串），且 `tests/test_tool_gateway.py:301-325` 的对照组注释明写"存量块仍是 现行 + 无日期 ⇒ 行为逐字不变（动它的是 E7，不是本票）"。**动它 = Agent 道证据清零。**
   - `settings.admin_password`（§4.1 已说明保留理由）。
   - `retrieval.py:994-997` 的 `except Exception → 回落 RRF 且不写缓存`、`_rerank_docs` 超时不标记模型耗尽——都是**有意的**降级取舍，别按"吞异常"清理。
   - `agent/planner.py:15-36` 的 `_SERVER_OWNED_FIELDS` 与工具名白名单——最像过度设计、实际最有价值的注入防线，删一行就等于给模型开一个改 `user_id`/`law_as_of` 的口子。

### 4.6 四条低档项（§0 脚注指向这里）

| 位置 | 事实 | 判读 |
|---|---|---|
| `backend/agent/fee_calc.py:57-58` | `normal = int(fee.quantize(Decimal("1"), ROUND_HALF_UP))`、`simplified = normal // 2`（**整数地板除**） | 标的额使受理费出现角分时（如 13000 元标的 → 125 元、减半 62.5 元），白名单只放行整数与地板减半 ⇒ 模型写**正确值** 62.5 被 `UNSUPPORTED_NUMERIC_TOKEN` 拦（fail-closed、整轮失败），写 ±0.5 元的近似值反而"可溯源"通过。递进费率与锚点我逐项复算过（`knowledge_base/fee_formulas.json` 的 brackets、50/1050/2300/4300/8800/13800 均对），所以这是**舍入口径**问题不是算法错。`tests/test_review_regressions.py:35` 把地板除钉成既定口径 ⇒ 属"边界待裁"，不是 bug |
| `backend/agent/limitation_calc.py:22-31` | `calc_limitation` 只有 `tests/test_limitation_calc.py`、`tests/test_review_regressions.py` 引用；docstring 自陈"起算日语义由调用方（**未来的**）显式传入" | 整套届满日/中断/20 年上限计算**暂存未接线**（同文件的 `controlled_limitation_tokens` 确有接线：`writer.py:961`、`verifier.py:439`）。闰年 2/29 落 2/28（`_add_years:135-140`）与法释〔2018〕12 号衔接分支（`:205-230`）实现本身我复算过没问题——风险只在"看似存在、实则无面向用户的数字来自它"，与今日 harness 审计的 **H-09（确定性计算器没做成工具）** 同批裁 |
| `backend/clarify.py:111` | `_plausible_law` 的 `2 <= len(name) <= 8` | 名字 9+ 字且**库内无此法**时（例："上市公司信息披露管理办法"12 字）不触发拒答分支 ⇒ 用相近的库内法硬答，正是该模块注释里要防的"问库外法误答"。`:40-48` 的字尾黑名单注释说明长度上限是防误抽的取舍，但没登记这条失败模式。修法：改用 `_ensure_src_set` 的 99 部全集做包含/前缀匹配（与 B-14 同票） |
| `backend/query_understand.py:246` + `backend/memory.py:71` | 前者 `def decompose(query, concept_keywords: tuple = ())` 的形参在函数体与全部调用点都无引用，而模块 docstring `:17-21` 专门解释"为什么不用概念词表做锚点"；后者签名 `-> str` 但 `:84 return None`，失败语义靠 `compress` 里的 `is None` 分支承载 | 前者是"这条路还通着"的假象（死形参 + 注释反向），后者是类型注解与实现矛盾（mypy 是否豁免需看 `pyproject.toml` 的 exclude 口径，本轮未核）。都不影响运行正确性，影响的是"下一个读者会不会被误导" |

---

## 5. 不建议动（本轮确认为防错资产）

`agent/planner.py` 的 `_SERVER_OWNED_FIELDS` 黑名单 + 工具名白名单（模型想改 `user_id`/`law_as_of`/`budgets`/`steps` 直接 `PlannerPolicyViolation`）、ToolContext 一律取自 run 记录而非请求体（`retrieve_memory` 还二次校验会话归属）、writer 不能自签 support 且 claim_checks 由 verifier 单方签发、终稿 `persist_agent_final_once` 的 CAS 幂等 + `render_verified` 二次独立验证（含 HMAC digest 比对）、`auth.py:62` 固定 `algorithms=[JWT_ALGORITHM]`（算法混淆不可行）、`auth.py:22-27` 缺 `JWT_SECRET` 即 RuntimeError（无弱回退）、`observability.py` 的日志字段白名单 + AST 哨兵测试、`/api/media/{filepath:path}` 的"先 containment 后归属"顺序（有测试钉住）、`retrieval.py:994-997` 精排故障回退 RRF 且**不写缓存**、`_rerank_docs` 超时不标记模型耗尽、`hybrid_retrieve` 的配额异常 `raise` 不被兜底吞掉、`fallback_to_fast_path` 对非白名单 reason 抛 ValueError、compose `backend/frontend` 无 `ports:` 段（8000/3000 未泄漏到宿主）、`prompts.py` 的 `LEAK_FRAGMENTS` 与 SYSTEM_BASE 同源锁定（`test_prompts` 断言每片段仍在 SYSTEM_BASE）。

低档但可接受的取舍（不建议本轮处理）：bcrypt cost=12 与登录锁定"内存级、重启清零"（2 人场景，注释自陈）、备份不加密同盘存放（`backup_data.py` 已做 integrity_check）。〔**复核轮后删除的一项**：我原先把"容器 root 运行与 LAN 明文 HTTP"列为"单机形态可接受的取舍"，复核轮用 `DEPLOYMENT.md:30-31/63/65/94/101-111` 的原文证明**文档正在教人裸跑公网**，该取舍已改判为 **B-38 中档缺陷**，不再算"不建议动"。〕

---

## 6. 与今日 Agent harness 审计的交叉引用

| 本报告 | harness 审计 | 关系 |
|---|---|---|
| B-05（`category` 键不存在） | H-07（工具菜单四个真源） | 不同问题：H-07 是"名单不闭合"，B-05 是"传进去的键在库里不存在"。**派单可并票，但判据要两条** |
| B-01（预算终点炸终稿） | H-04（无 wall-clock 预算） | 无重叠，H-04 讲的是时限与孤儿 run；B-01 是 steps 预算与终态转移的冲突 |
| B-04 / B-14（引用覆盖盲区） | — | harness 审计未覆盖引用形态集，属本报告新增 |
| B-20（三类调用不 deduct） | H-05（Agent 道零成本观测） | 同族，可并票；B-20 的增量是**快车道侧**的视觉/改写/压缩三类 |
| B-30（合同文本靠模型转述） | H-09（确定性计算器没做成工具） | 相关但不同：H-09 建议升格工具，B-30 指出 `analyze_contract` 当前**输入**不可信 |
| §4（`verifier_research_returns` 残留、`ask_user` 不可达） | H-02 + D7 | **重叠，勿重复派单**；D7 与"回喂是 Ticket 2 有意删除"的张力需一并裁 |
| B-15（TOOL_BUSY 硬失败） | — | 新增；注意 docs 里"不扩大技术 fallback 白名单"是两条针对 **writer 内容失败** 的在册声明，未讨论容量类失败 |

---

## 7. 决策台账（待 Owner 一词可答；推荐项已给）

| 编号 | 待决 | 我的推荐 | 若不做，风险 |
|---|---|---|---|
| DB-1 | B-01 预算终点炸终稿：先补一条定向用例坐实可达性，还是直接按缺陷修？ | **直接修 + 同批补用例**（改动面只有 `chat_integration.py` 那一个 except，且 `AGENT_BUDGET_EXCEEDED` 已在白名单，不需要新政策） | 已验证的终稿在放量后被静默丢弃，且 run 不可恢复 |
| DB-2 | B-03 近重复缓存：改判据（纳入 cutoff/sources 一致性）还是先 `FEATURE_SIMILAR_CACHE=false` 关掉？ | **先关开关**（一行部署期值，零代码风险），把改判据独立开票 | 引用面板与正文不同源这件事会持续污染评测口径 |
| DB-3 | B-04 + B-14 + B-13 引用覆盖盲区是否并成一票"真源收口"？ | **并成一票**（法名全集派生自 `_ensure_src_set`、条号字符类进 `domain_rules`、无名条号补一道 fail-closed 门），一次做完才不会再漂 | 三条分别修会漂回；且"校验通过"的语义仍不等于"所有引用都在库" |
| DB-4 | B-05 `category`：摘掉可选面，还是给未知键回落无过滤？ | **两头都做**（提示词+schema 同步摘，`vector_top`/`bm25_top` 遇零命中且带 filter 时回落一次无 filter 并记日志）；注意与 H-07 的"四真源等值断言"并票 | 放量当天 Agent 道大面积"未检索到"，且被读成召回缺口（09-26 那次已走过弯路） |
| DB-5 | B-06 4xx 永久耗尽（**复核后由"高"改判为"中"，杀伤链已改写**）：加窄豁免还是加冷却 TTL？ | **两个都要**，豁免面只按错误文本（`context_length`/`data_inspection`）窄匹配，**不动** `test_llm_failover.py:163-166` 钉住的"400 归永久"总口径；但**优先级让给 B-43**（compose 那份只有 1 个 text 角色 ⇒ 本来就没有回退池，先补角色形状再谈冷却） | 被标死的模型对本进程永久退出自动路由、零日志；叠加 `flag_degraded` 禁止写缓存 ⇒ 长期"带注记的降级答复 + 零缓存复用"（**不是** 503，原说法撤回） |
| DB-6 | B-07 沉淀闸：是否把 `sv.ok` 变成硬前置？ | **是**，同时把 `AUTO_CURATE_THRESHOLD` 免审分支也过这道闸（免审≠免校验，管理员确认与判据正确是两件事） | 编造条号进持久语料，之后零模型复读 |
| DB-7 | B-15 `TOOL_BUSY` 是否并入技术降级白名单？ | **并入**（容量类失败与超时同根），但需你明确推翻"不扩大白名单"那句在册口径——那两条原文针对的是 writer 内容失败 | 过载时刻用户拿不到任何答案 |
| DB-8 | B-21 embedding 换班脚本：改"先写 `-rebuild` 再原子换名"，还是只在文档里加警告？ | **改脚本 + 加启动绊线**（`rag_chain` 抽样比对库内向量维度与 `settings.embedding_dimensions`，不符即 fail-fast）；文档警告挡不住"只改 .env 不重建" | 唯一真值可被删；向量空间混用不报错，只表现为答案质量悄悄变差 |
| DB-9 | B-25 + B-26 配置/密钥卫生（**B-25 复核后由"中"降为"低"**：那是个未跟踪文件，"新克隆即泄密"情景不成立） | **仍建议做 B-25**，但理由换成"整树拷贝会被别的会话/工具带走 + 无人工 `git add -f` 防线 + pre-commit 无密钥扫描"，一行 `.env.*`（配 `!.env.example`）+ 一条 `git check-ignore` 哨兵即可，**不按紧急泄密派单**；detect-secrets 钩子单独立项。B-26 的 compose 覆盖哨兵测试排在其后 | 剩余真面是"协作拷贝带走凭据"，不是"一次 `git add -A` 即公开" |
| DB-10 | B-27 令牌吊销：加 `token_epoch` 列（触发迁移），还是把"轮换 JWT_SECRET 是唯一全局吊销手段"写进 DEPLOYMENT 事件响应？ | **先写文档 + 记待办**，与 D5（harness 审计的新列）同批做迁移，避免两次改表 | 改口令止血无效，事件响应缺一条基本动作 |
| DB-11 | B-29 删除语义：`qa_candidates` 无 user_id 这件事，是补列还是明写"不可按用户删除"？ | **明写进已知限制**（补列要回填历史且历史行已不可归因），同时给删会话补 `feedbacks`/`media` 清理 | 法律案情的持久残余无法响应删除请求 |
| DB-12 | B-38（**复核后由"低"升为"中"**：`DEPLOYMENT.md` 已在教明文公网裸跑，不是"将来"问题）与 B-40（MCP 工具） | **拆两刀**：①文档刀（今天就能动，零代码风险）——把 `IP:8080` 剧本标为"仅限内网"、公网段只留 Caddy+tunnel 或自签 TLS，删掉"8080 必须放开/不需备案"这类鼓励句；②镜像刀——`USER` + `no-new-privileges` + 把 `mcp_server.py` 挡在生产镜像外。**不要**把它继续挂在"上公网前再评估" | 口令与案情在公网明文可嗅探；叠 B-02（限速可绕）与 B-17（锁定一次性）后爆破可续 |
| DB-13 | B-42（主库未设 WAL）+ B-43（`LLM_MODELS_JSON` 整体替换角色 ⇒ 两份 .env 能力面互不重叠）：是否与 B-37/B-41 同票做？ | **是，且这是本轮性价比最高的一票**：三处都是一行级（`connect` 事件里设 `journal_mode=WAL`、`mark_depleted`/`print` 改结构化日志、角色并集校验落 warning），互相放大（写锁冲突 → `database is locked` → stdout 静默）。**注意**：开 WAL 后 `backup_data.py` 的备份口径需重验（`iterdump` 与文件拷贝对 WAL 的含义不同） | "失败有出口但无人看得见"的三件套长期不闭合 |
| DB-14 | B-44（改密走 argv 且零审计）+ B-45（`import_laws` 未受 `chroma_dir_guard` 覆盖）+ B-46（`_cutoff` 本地日 vs 沉淀 `basis` UTC 日）这三条低档要不要本轮顺手做？ | **B-45 顺手做**（一行 `assert_matches`，防的是"错库改写生产索引"这类不可逆）；**B-44 顺手做**（补一条 `log_audit`）；**B-46 只做注释与统一钟**（改钟会影响缓存 key 与 QA 直返，需一条用例钉住，别裸改） | B-45 是唯一有不可逆后果的一条，另两条是审计与口径卫生 |
| DB-15 | **（§12 新增）** B-01 + B-47 同根：给"终稿边 + 恢复边"这两类 1 步边**预留步数或不计步**，还是继续抬 `AGENT_MAX_STEPS`？ | **并一票结构修**（推荐：`DRAFTING→COMPLETED` 不计步、resume 的同回合转换不计步；再给 §12.1 的 L1–L4 四腿与 §12.2 的 steps==cap 恢复各补一条用例入库）。**这两只用例请随修票一起入库**——本轮它们只活在 `%TEMP%\fazhi-audit2-20261009\`（见 §12 开头"脚本落点"），清掉后 §12.1/§12.2 的读数就不可复现。**不推荐再抬 cap**——8→16→20 三次已有原文可查，`le=32` 封顶后同一形状仍在 | 放量后每次把 cap 抬高只是把死锁推到更远；`test_agent_resume.py:675` 现在把 409 当**预期**钉住，等于用测试固化了缺陷 |
| DB-16 | **（§12 新增）** B-05 的修法面：只改提示词，还是提示词 + schema + 检索侧回落三处一起？ | **DB-4 的"两头都做"升级为"三处"**：①`agent/runtime.py:85` 删掉「category 可选」那半句；②`RetrieveLawsInput.category` 从 schema 摘除（`extra="forbid"` 已能挡未知键）；③检索侧"带 filter 且零命中 → 回落无 filter + 落 warning"。理由：本轮实测证明**光摘提示词不够**——字段还在 schema 里，模型仍可能自己想到它 | 静默零证据会被读成"召回缺口"，历史 09-26 已因此走过一次弯路（rerank 降权被误读成召回不足） |
| DB-17 | **（§12 新增）** B-48：`mark_depleted` 的记账通道是否拆分？ | **拆**（`exhausted` 走配额、`rejected` 走冷却 TTL 且 `reason` 进结构化日志）。**不动** `is_transient_error` 的分类口径（`test_llm_failover.py:167-170` 已钉），也不动 `TRANSIENT_STATUS` 集合 | 管理台把"请求被拒"读成"积分用完"，运维会去加积分或调 `calibrate`，反而把可用模型长期关在路由外 |
| DB-18 | **（§12 新增）** B-49：法名归一的正则是否扩到半角括注？ | **做**（一行 `[(（][^)）]*[)）]\s*$` + 单测同时放全角/半角两格）。若近期要接元典或任何外部权威源，这条**必须先做**——外部名就是"中华人民共和国X法(YYYY修正)"这个形状 | 10 个消费点会把权威名判成"库里没有"，表现为引用校验假阴性，比不过校验更难查 |

**本报告不向你索取的决定**：所有"证据不足"项（B-01 可达性、B-06 provider 是否真返 400、B-18 OOM、B-34 实体展开、B-37 占位是否算正确补偿）我都按 C 级标注并给了只读或定向用例的验证方式，**不劝你先跑再裁**——需要跑真实请求的（B-06 的历史日志 grep、B-34 的样本构造）请你在授权范围内决定。

〔**§12 就地更新这段**：B-01 可达性**已实测坐实**（§12.1 四腿），B-05 的 Chroma 语义**已实测坐实**（§12.3），B-06 里"真返 4xx 时判什么"这半**已实测**（§12.4，真 SDK 打回环 stub），所以这三条**不再是证据不足项**，裁决口径改由 DB-15/DB-16/DB-17 承担。仍属证据不足的只剩：**B-06 "provider 历史上是否真返过 400"**（`logs/` 在本工作区是空的，§12.7）、**B-18 OOM**、**B-34 实体展开**、**B-37 占位补偿是否被视为正确行为**（这条是口径问题不是证据问题）。另：B-05 的**触发频率**仍不可知——`normalized_input` 是 sha256，本机读不出历史是否真传过 `category`（§12.3 第 6 点，含我第一次读数读错的归因）。〕

---

## 8. 附录 A：本报告关键否证命题的复现命令（只读，Owner 可自行决定跑不跑）

```bash
cd C:/Users/33393/Desktop/ai-legal-helper

# 1) 现网库 metadata 键集里没有 category / version_id（B-05；我用只读 URI 跑过）
python - <<'PY'
import sqlite3, os
con = sqlite3.connect(f"file:{os.path.abspath('backend/chroma_db/chroma.sqlite3')}?mode=ro", uri=True)
c = con.cursor()
for cid, name in c.execute("select id,name from collections").fetchall():
    segs = [r[0] for r in c.execute("select id from segments where collection=?", (cid,)).fetchall()]
    if not segs: continue
    q = ",".join("?"*len(segs))
    n = c.execute(f"select count(*) from embeddings where segment_id in ({q})", segs).fetchone()[0]
    keys = c.execute(f"select distinct key from embedding_metadata where id in \
        (select id from embeddings where segment_id in ({q}))", segs).fetchall()
    print(name, n, sorted(k for (k,) in keys))
PY

# 2) 沉淀/评测侧的条号字符类看不见千级与全角（B-13；pattern 逐字复制，不 import 项目模块）
#    订正：原先这里把 retrieval 那份 pattern 写成"省略号仅为打印"，属不可执行命令（复核轮指出）。
#    现在改成从真源现取，复现者不必手抄：
python - <<'PY'
import re, pathlib
cur = re.compile(r"《[^》]+》\s*第[一二三四五六七八九十百零0-9]+条|根据《[^》]+》")     # curation.py:8
ev  = re.compile(r"《[^》]+》\s*第[一二三四五六七八九十百零0-9]+条")                    # eval_metrics.py:12
src = pathlib.Path('backend/retrieval.py').read_text(encoding='utf-8')
full = re.compile(re.search(r"_ART_FULL_RE = re\.compile\(\n?\s*(r\"(.*?)\")", src).group(2))  # 从真源取，不手抄
s = "依据《民法典》第一千二百五十四条，物业未尽安保义务"
print("curation.has_citation =", bool(cur.search(s)), "| eval.citation_present =", bool(ev.search(s)), "| retrieval._ART_FULL_RE =", bool(full.search(s)))
# 实测：False False True；另测 "《民法典》第１１６条"（全角）同样只有 retrieval 命中
PY

# 3) 精确 key 钉了证据集合而近重复判据没有（B-03）
grep -n "def make_key\|def get_similar" -A6 backend/answer_cache.py
grep -rn 'hit\["sources"\]\|hit.get("model' backend/ --include=*.py     # 零命中 = 无读点

# 4) "已修"的两处只落一半（B-08 / B-09）
grep -n "COALESCE(message_count" -A4 backend/main.py backend/request_bootstrap.py
grep -n "run_in_threadpool(registry.deduct\|= citation_verify(\|citation_verify(answer)\|quality.self_check(" backend/main.py

# 5) 锚点补回是恒等操作（B-11）
sed -n '974,987p' backend/retrieval.py

# 6) 白名单与耗尽标记（B-01 / B-06 / B-15）
sed -n '13,21p' backend/routing_metrics.py
sed -n '569,581p' backend/llm_registry.py
grep -n "TOOL_BUSY\|TOOL_TIMEOUT" backend/tools/gateway.py

# 7) compose 传了哪些 env vs 根 .env 有哪些键（B-26；只看键名）
grep -oE '^[A-Za-z_][A-Za-z0-9_]*=' .env | tr -d '='
sed -n '19,44p' docker-compose.yml

# 8) 法名白名单 vs 库内源名的覆盖率（B-14；两边都从真源现取，不抄数）
python - <<'PY'
import re, sqlite3, os, pathlib
src = pathlib.Path('backend/output_normalize.py').read_text(encoding='utf-8')
names = re.findall(r'"([^"]+)"', re.search(r"_COMMON_LAW_NAMES = \((.*?)\)", src, re.S).group(1))
con = sqlite3.connect(f"file:{os.path.abspath('backend/chroma_db/chroma.sqlite3')}?mode=ro", uri=True)
segs = [r[0] for r in con.execute("select id from segments where collection=(select id from collections where name='legal_provisions_cos')")]
rows = [r[0] for r in con.execute("select distinct string_value from embedding_metadata where key='source' and id in (select id from embeddings where segment_id in (%s))" % ",".join("?"*len(segs)), segs)]
key = lambda n: re.sub(r"（[^）]*）\s*$", "", n.replace("中华人民共和国", "")).strip()
kb = {key(r) for r in rows}
print("白名单", len(names), "其中不在库:", [n for n in names if n not in kb])
print("库内归一后", len(kb), "不在白名单的数量:", len([s for s in kb if s not in set(names)]))
PY
```

---

## 9. 本轮未做与限制（诚实标注）

1. **没有跑任何测试或真实请求**。因此凡"运行时会怎样"的判断都是静态的；B-01 的可达性、B-05 的 Chroma 过滤语义、B-06 的 provider 是否会因内容返 400、B-18 的 OOM、B-34 的实体展开，都需要一条定向用例或一次受控复现才能坐实。我把它们都标了 C 或写了"待坐实"。〔**第二轮已把这条的前三项做掉，见 §12**：B-01（§12.1 四腿）、B-05（§12.3 九腿，含 `$ne` 也排除缺键行这条意外发现）、B-06 的行为面（§12.4 真 SDK 状态码网格）；**B-18 与 B-34 仍未跑**（要的是端到端注入或真实上游，不是副本树定向用例能覆盖的形状）。B-06 的"历史上是否真返过 400"改判为**本机不可知**——`logs/` 在本工作区 `find logs -type f` 实测 0 文件，连目录都不存在，所以那条 grep 预案是空的。〕
2. **`backend/scripts/*` 与 `backend/tests/*` 未全文审**。scripts 只审了写侧与危险路径的抽样；tests 只用于反证检索（判"某条是否已被钉住"依赖 grep，可能漏）。
3. **未审前端消费侧**：B-03（sources 帧）与 B-23（书名号归一影响前端标色）的最终用户可见后果需要前端代码确认。
4. **未跑 pip-audit / CI**。依赖侧结论（B-39，已在 §0 表内）只基于版本号阅读与 CI 已有 `pip-audit` 步骤这一事实；本机 `pip check` 的历史红项（fastapi↔starlette、sse-starlette 区间）属另一会话在册事实，本轮未复测。
5. **与并行会话的写竞争**：本文件是唯一新增文件，未跟踪。若其它会话做"工作区快照"式提交，可能被一并带走（历史上发生过），需要时请先确认归属再提交。
6. **§4 的覆盖面比原计划窄（过程事故，如实记）**：专责"死代码/单一真源"的第 5 个子 agent 在即将交付时掉了（后台任务返回空结果，未拿回任何结论），§4 因此改由我自己用 stdlib 做字段/列/依赖三份扫描 + 逐候选回读本体完成，覆盖面比原计划少了两项：**`scripts/` 内的死码**、**"跨模块契约类注释"的更大抽样**（我只核了 7 条与本报告结论直接相关的）。复核两路则都出结果了，但 A 路前两启各报一次 `Sorry, something went wrong`、第三次才跑完（本轮共 3 次 agent 掉线）。
7. **我在 §4 踩到的假阳性已写进正文**：`settings.agent_writer_corrective_retry_enabled` 静态搜 `settings.<字段>` 是零命中，实际被 `agent/service.py:413` 的 `getattr(settings, ...)` 动态读着——任何"零消费者"类结论都必须过 `getattr` / `__getattr__` / 字符串键写入这三类动态引用这一关。§4.1 的每一行我都做了二次确认：`AgentRun(` 的构造点只有 `agent/repository.py:69` 一处且不传 `goal`/`task_type`（已排除 `**kwargs` 展开形态）、`getattr(settings, ...)` 的全部命中点是 `service.py:405/413/576` 与 `routing_metrics.py:49/51`（其中 `agent_partial_delivery_enabled`、`agent_dept_filter_r1ob` 均**在 `settings.py:172/150` 有声明**，故不是死开关）。
8. **报告内的数字都是现取的**：白名单/库内源名（B-14：28 / 27 在库 / 72 不在白名单）、Chroma 集合与 metadata 键集（B-05：两集合各 10266 条、9 个键、无 `category`）、生产代码行数（§1 表）都由我在本机现跑现取，命令在 §8 附录 A。子 agent 给的 73 与我算的 72 之差已写明归因（括注源名的归一口径）。〔**就地更正一处读数错**：这里的"**9 个键**"是错的，第二轮按**每行键数分布**复量 = 两个条文集合各 **10,266 行、每行 8 键**（`article/chapter/effective_from/effective_to/file_hash/origin/source/status`），与 §0 的 B-05 行原本写的 8 键一致——即**这是本报告内部的一处自相矛盾**，不是新代码变了形状。复量命令：`col.get(include=["metadatas"])` 后按行 Counter 键数（§12.6 末段）。同批复量还确认 `effective_from`/`effective_to` **非空行数 = 0**〕

---

## 10. 补记：两路独立复核对本审查的复核结果

派法与目的：报告正文成稿后，派两个**只读**子 agent 复核这份审查本身，两路正交——**A 路**逐条复现 46 条的行号、引用原文与 §8 附录命令的读数；**B 路**挑战论点、判"在册取舍被误报成缺陷"，并补我漏掉的角度。两路的结论我**没有照单接受**：凡改判/撤回/新增，都在本机重跑一遍才写进正文。下表逐条记处置，正文里对应位置都标了"复核轮订正/新增"。

过程如实记：A 路前两次启动各报 `Sorry, something went wrong`（连同第 5 个死代码 agent 一起，本轮共 3 次 agent 掉线），第三次跑完并交付；死代码那一路的成果没有回来，§4 是我自己重做的。

### 10.1 A 路（逐条复现）的判定与我怎么处置

A 路总判：约八成行号/原文可直接落位、七成读数可本机复现；**B-01/03/05/06/08/09/11/13/17/19/20/25/31/32/35/36/40 经它独立复跑或独立重推成立**；它同时独立重推了 B-08（SQLAlchemy `text()` 不失效 identity map ⇒ 绝对值 UPDATE 覆盖原子结果）与 B-11（三分支都把 `anchor_guaranteed` 全部前置 ⇒ `dropped_anchors` 非空 ⟹ `len(docs)==k` ⟹ 恒等），结论与我一致。它点出 6 条"会被一句『你自己数的吗』击穿"的：B-26、B-38、B-34、B-41、B-14、B-37 计数。

| A 路主张 | 我的处置 | 凭什么 |
|---|---|---|
| B-26 三处指错（根 `.env` 是 23 键不是 22；`.env.example` 里没有 `SELF_REGISTER`，在 `backend/.env.example:17` 与 `.env:8`；`CORS_ORIGINS`/`FEATURE_*` 不在根 `.env`） | **接受，已改**（该行证据等级由 A 降为"B 订正后 A"） | 我本机 `grep -cE '^[A-Za-z_]+=' .env` = 23；`grep -n '^SELF_REGISTER'` 命中 `.env:8` 与 `backend/.env.example:17`、不命中根 `.env.example`；`grep -cE '^(CORS_ORIGINS\|FEATURE_)' .env` = 0 |
| B-38 引错段（我原先写 `DEPLOYMENT.md:99-104` 是"裸跑推荐路径"，实际那是前端 npm 段；原文在 `:94` 与 `:152`） | **接受**；且我按 B 路的证据把整条升档为"中"，行号换成我逐条 grep 到的 `:30-31/:63/:65/:101-111/:71` | `grep -n "0.0.0.0\|8080\|安全组\|备案\|scp root@" DEPLOYMENT.md` 的命中行 |
| B-34 的"BadZipFile 不在 `except ValueError` 内 ⇒ 500"**与代码相反** | **撤回该子结论**，改述为"zip 损坏已被 ValueError 归一 → 400；剩余缺口是 pypdf 异常未归一（我未核其异常类型）+ 无页数预算" | `docx_utils.py:49-50` `except zipfile.BadZipFile ... raise ValueError`；`main.py:1442-1443` `except ValueError as ve: raise HTTPException(400)` |
| B-41 的"异常被 `except: pass` 吞掉"**说反**，实为 `print("[chat-placeholder]")` | **接受，已改**，并把它与 B-37 归为同根 | `main.py:2404/2413-2414` 原文 |
| B-37 应是 **7 处**不是 6 处 | **接受，已改**并列全行号 | `grep -n 'print(f"\[chat'` = `1884/1915/1944/1973/2105/2181/2395`（+ `2314/2404/2414` placeholder、`2407` stream） |
| B-29 归因不全（`admin_delete_user` **已**显式清 Feedback/AnalysisRun） | **接受，重写该条**：问题从"作者不知道要清"改成"清单不全（漏 agent_runs/media/删会话路径/qa_candidates）+ 全库未开 `PRAGMA foreign_keys`" | `main.py:2624-2626` 两行 `db.query(...).delete(...)` |
| B-14 的 73 应按下限口径改 72 | **接受**（我此前已自算 72，现补口径说明与复现命令 §8 第 8 组） | 白名单 28 / 其中 27 在库（`食品安全法` 不在库）/ 归一化后 72 不在白名单 |
| B-01 的 `routing_metrics.py:13-21` → `:13-20`；B-03 内联标号 `answer_cache.py:22` 实指 `:25`；§4.3 `retrieval.py:471` → `:470` | **接受，三处行号已订正** | — |
| B-21 行号 `:130` 应为 `:132-134`；`MODEL_DIMENSIONS` 要补路径 `scripts/switch_embedding.py:47-56` | **部分接受**：`MODEL_DIMENSIONS` 路径与"8 项 6 个 None"我复现属实并已并入正文；但 B-21 的**机制**被 B 路改写得更大（见 10.2），我按 B 路版本重写，行号一并带上 `:132-134` | `sed -n '130,137p'`、`switch_embedding.py:47-56` |
| 分级该改：B-16 由 B 升 A、B-22 的"前置+不去重"半边升 A、B-30 形状升 A；B-25 的"7 个凭据键名"应降 B/C（敏感文件不可由他人复现）、B-38 的"A（B）"双标要取消；**B-05 的 Chroma `$eq` 语义不可升 A**（验的是"键不存在"不是"过滤返回 0"） | **接受全部**（B-25 的键名读数已在我正文里标为只读键名；"键不存在"与"过滤返回 0"的区分我此前没写清，现已在 §9 第 1 条与本表明确：B-05 的 A 只覆盖"键不存在"那一半） | 我复跑的 metadata 读数 |
| §2 标题"高档缺陷详解"里混了中档条目、B-02 排在 B-07 之后；§0 脚注曾声称 4 条低档项"折入 §4/§5"而实际没有 | **接受**：标题改为"重点缺陷详解（高档 + 复核后改判的条目）"；4 条低档项真的写进了 **§4.6** | — |
| §8 附录第 2 组命令里我写了"省略号仅为打印"的 pattern，属把**不可执行命令**放进附录 | **接受**，这是复现性的硬伤：A 路只能改用 `retrieval.py:243` 原文粘贴复跑。已在正文保留订正说明（附录里那一行的修法：要么给完整 pattern，要么给"从文件里 sed 出来再跑"的命令） | — |

A 路一处我**不接受**：它说 §4 "自称先给两条、实际列了 5+ 条"——这是它读到的是**未补完的 §4**（我派它时 §4 还在写）；现 §4 已完整并有 §4.1-§4.6 结构，该判据对当前版本不适用。

### 10.2 B 路（挑战 + 补漏）的判定与我怎么处置

| B 路主张 | 我的处置 | 凭什么 |
|---|---|---|
| **B-06 的杀伤链夸大**：`configs` 只有 3 项、`on_model_failure` 仅当 `i < len(configs)-1` 才调 ⇒ 单请求最多标死 **2** 个；`_safe_pick` 在 `QuotaExhausted` 时回落 `registry.get()` ⇒ **不会 503** | **接受，高→中并重写整条**。真实危害改成"被标死者永久退出自动路由 + 无日志 + 降级态禁止写缓存" | `sed -n '2222,2228p' main.py`（`[(False,0.0),(True,0.5),(False,0.5)]`）、`rag_chain.py:238-243`、`main.py:1062-1064`、`:2328` |
| **B-10 该升档**：`retrieve` 默认 `k=4`，单个强锚点即产至多 6 个 id 无条件占头 ⇒ 不需要"多锚点"就能把 rerank 挤到零进位；建议与 B-11 并票 | **接受，中→高**，两条都重写成"同一段代码的两个面" | `retrieval.py:1004` 的 `k: int = 4` + `:950-974` |
| **B-21 的丢失窗口我说错了**：源库在删除前已整库读进内存（`_read_old`），新增块随 `docs_main` 一起重嵌；真丢形是"删建之间 `_write_new` 崩溃 + 崩溃后重跑因 `count()>0` 不再回落 cos 而放大"，且 `backup_data.py:77-85` 的上一次快照可兜 | **接受，撤回原说法并重写**（保留"运行期零校验 + 维度绊线只覆盖 2/8"那半边，B 路复现了 6/8 为 `None`） | `rebuild_embeddings.py:131-137/98-99/77`、`backup_data.py:77-85` |
| **B-25 情景错**：`.env.bak` 是**未跟踪**文件，克隆里根本没有 ⇒ "换机/新克隆一次 `git add -A` 即泄密"不成立；且 `info/exclude` 那行注释是**有意裁决**、同族 09-15 已在册 | **接受，中→低**，泄密面改窄为"整树拷贝 + 手工 `git add -f` + 无密钥扫描钩子" | `git ls-files --error-unmatch` 三路径均 not known to git；`code-review-report-20260915.md` 与 `.gitignore:88-90` 的在册注释 |
| **B-38 该升档**：`DEPLOYMENT.md` 不是"将来"而是**已经在教**明文公网裸跑（`:30-31` 强制绑 0.0.0.0:8080、`:63` 放行 22+8080、`:65` "IP:8080 不需备案"、`:101-111` 把 API/前端都指到公网 IP 并放行 3000、`:71` `scp root@`） | **接受，低→中**，并把 §5"可接受取舍"里那句删掉（留了删除说明） | 我用 grep 逐条命中上述行 |
| **B-04 例形要收窄**："第五百七十七条规定"不构成误拦（`_UNBRACKETED_CITATION_RE` 是"名称+条号"顺序），真正全盲的是**条号前无任何 法/典/条例/规定/办法 尾词**的形；`entity_precision_check` 默认关且消费同一套带锚提取，`phantom_check`/`fact_consistency` 也覆盖不到 | **接受**，例形与前缀条件已改写，并补了"三个我没展开的门为什么补不上这个洞" | `writer.py:401-405`、`phantom_check.py:9/54`、`settings.py:103` |
| **B-01 窗口比我说得窄**：`agent_max_tool_calls=10` 会先在 `register_action` 触发 BudgetExceeded → **优雅 STOPPED**；只有"tool_calls 未满而 steps 恰满"的形状才炸终稿。同时补一条**加强可达性**的旁路：controller `:587→1050` 的确定性终稿门从 PLANNING 直跳 DRAFTING **没有 step 预检** | **接受**（两个方向都记：一窄一宽），B-01 维持高档、可达性仍按 C | `settings.py:95`、`controller.py:710-726`、`:587/:1050` |
| **B-19 只报了记账面**，还有执行面：E9 用 `flag_llm` 不重 pick、不过轮换 ⇒ 若 `flag_llm` 正是本轮被标死的 key，兜底必再失败 | **接受**，B-19 改成"记账面 + 执行面"两面并写触发条件 | `main.py:2247`、`:2188-2202` |
| **B-09 该降中低**：`article_in_kb` 无 per-article 缓存属实，但本地 sqlite 毫秒级、部署 1-2 用户，受害者只有自己 | **接受，中→中低** | `retrieval.py:499-509` |
| **新增 5 条**：主库未设 WAL（配额库设了）、`LLM_MODELS_JSON` 整体替换 DEFAULT_ROLES 致两份 .env 能力面互不重叠、`reset_admin_password.py` 走 argv 且零审计、`import_laws.py` 未受 `chroma_dir_guard` 覆盖、`_cutoff()` 本地日 vs 沉淀 `basis` UTC 日 | **全部接受**，编号 B-42…B-46（WAL/角色形状/`_cutoff` 三条我本机复现到 A 级；`import_laws` 与脚本 argv 两条也读到原文）。其中 B-43 直接改变了 B-06 的现实意义（compose 那份只有 1 个 text 角色 ⇒ 没有回退池） | `quota_store.py:27` vs `database.py:13-16`；`llm_registry.py:368-372` + 我解析两份 `.env` 的角色分布；`scripts/reset_admin_password.py:29/33/45`；`import_laws.py:10/171/241`；`main.py:1111` vs `knowledge_service.py:326` |
| **框架问题**：我把未实测的推断写成 A（B-01/B-06）、且把 `agent_enabled=False` 的放量地雷与快车道现网问题混在同一档同一节，会误导派单顺序 | **接受**，这是本轮最该改的方法问题：§0 表新增"现网/放量"分列建议见 §10.3，B-06/B-01 的证据等级已按实况标注 | — |

B 路一处我**未采纳**：它建议把 B-10 与 B-11 合并成一条编号。我保留两个编号（便于对照既有引用），但在两行里互指并写明"同一段代码、建议并成一票修"。

### 10.3 两路共同的、以及仍未解的

- **两路都同意的原结论**（即最硬的一批）：B-03、B-05、B-07、B-08、B-13、B-17、B-19、B-25 的事实部分、B-28、B-31、B-32、B-35、B-36、B-40。
- **仍未解、必须靠跑**才能定的三件事（本轮只读约束下我没做）：① B-01 的步数序列是否真能在生产默认预算（`max_steps=20`、`max_tool_calls=10`）下走到"steps 恰满而 tool_calls 未满"；② provider 会不会因用户内容返回 4xx（可先 `grep -a '"llm_error_status_code": 400' backend/logs/*.log` 判历史）；③ B-05 我只能证"键不存在"，**"Chroma `$eq` 对缺失键返回空"这一语义我未实测**。派单时这三条应各配一条定向用例，不要当既成事实。〔**§12 已就地处置**：① 已实测坐实（§12.1，四腿）并由此扩出新条 B-47（§12.2）；③ 已实测坐实（§12.3，chromadb 0.4.24 现场九腿）；② **这条路在本机是空的**——`logs/` 目录 `find logs -type f` 实测 0 文件（连目录都不存在），历史 400 读数无从考古，我改测了它能测的那一半：真 SDK 打回环 stub 的 4xx 分类网格（§12.4），并由此扩出新条 B-48。〕
- **派单建议（按两路合成的新顺序）**：先做"现网现损 + 一行级"：B-42/B-37/B-41（日志与 WAL 同根）、B-08、B-17、B-25、B-26、B-43；再做"底线相关"：B-03、B-07、B-13/B-14（真源收口）、B-10+B-11；放量前做：B-01、B-04、B-05、B-15、B-16；公网化前做：B-38、B-02、B-18、B-27。〔**§11 更新**：其中 B-08/B-25/B-41 已在新 HEAD 落地、B-03 已降级，这一串顺序要按 §11 重排；§12 又把 B-01/B-05 从"待跑"变成"已坐实"，并新增 B-47（与 B-01 同根、射程更广）。〕

---

## 11. 第二轮：按新 HEAD `0b54396` 重判（基线位移后的逐条复核）

第二轮 Owner 指令是"现在实际审查一遍，先规划"，所以我先做了一件本轮无法回避的事：**基线在我脚下动过**。

**位移事实与复现**（本轮现跑）：

```bash
git rev-parse --short HEAD                          # 0b54396（起点是 5be6e05）
git log --oneline 5be6e05..HEAD                     # 902e2d1 fix: harden credential scanning and cache invalidation
                                                    # 0b54396 fix: integrate local candidate and serialize cancelled chat turns
git diff --stat 5be6e05..HEAD -- backend/ | tail -1  # 27 files changed, 4519 insertions(+), 201 deletions(-)
git status --porcelain --untracked-files=no         # 6 项，其中 backend/ 为 0 项（脏项全在 frontend/docs）
```

这两笔是**并行会话**提交的（含约 3,800 行新测试），不是我改的；我本轮同样**未改动任何在册代码**。位移直接命中我报告里的三条结论，所以必须逐条重判而不是加一句"可能已过期"。

### 11.1 已闭（3 条）

| 编号 | 关闭凭据（我读到原文，行号按 `0b54396`） |
|---|---|
| B-08 | `main.py:996` 一带：原"原子自增紧跟 ORM 绝对赋值"里的 `conv.message_count = …` 那行**已删**，只剩 `_post` 的原子 SQL ⇒ 单一真源回到 SQL 侧，正是我建议的修法 |
| B-25 | `902e2d1` 往 `.gitignore` 末尾追加了 `.env.bak*`（追加在文件末尾是因为 tests 按 `.gitignore:31/:45/:77` 行号引规则，这个手法本身值得记一笔）⇒ 原先"只被 `.git/info/exclude:9` 这个 per-clone 规则挡住"的判据不再成立。我不复述该备份文件里的口令值，只记键名与长度特征在册不变 |
| B-41 | `llm_guard.py` 改动说明与函数体都改了口径："取消窗口 D1 修复：不再经 `to_thread` 阻塞桥接" ⇒ 我原报的"排队占 default executor 一个 worker、把占位落库挤到队列后面"这条链的承重柱被抽掉 |

### 11.2 降级（1 条）：B-03 近重复缓存

新增的是 `CacheScope` 等值门，实测在盘上的形状：

- `answer_cache.py`：`CacheScope = tuple[str, str, tuple[str, ...]]`、`make_scope(intent, cutoff, context_ids)`（意图 + 时效日 + 排序去重后的证据 id 集），`get_similar` 里 `if not q_embedding or scope is None: return None`、`if v.get("scope") != scope: continue`；
- `main.py:1146-1155` `_cache_scope(pre)` 产出的证据 id 元素是 **(source, article, effective_from, effective_to, status) 五元组**，`:1207` 起 `_similar_cache_hit` 把它传进 `get_similar`。

⇒ 我原判的"跨天/换证据集合也能近重复命中"这半边**已经关上**（且是结构性的：不同意图/不同时效日/不同证据集一律 miss）。**剩下的洞不是判据松，而是帧内容与答案不同源**：命中后答案取 `hit["answer"]`（`main.py:2052`），而下发的 sources 取的是**本轮** `pre["sources"]`（`main.py:2067`）；条目自带的 `sources` 与 `model` 由 `put()` 写入却全仓无读点。所以 B-03 的"破引用可溯源"结论**保留**，但机理要改述，档级 **高→中**（触发面比原先窄：只有 scope 完全相同、即同一意图同一时效日同一证据集合下的近重复命中才会错配——而这恰恰是最常见的那一形，因为近重复题本就同证据集）。

### 11.3 行号漂移（不改结论，只改指针）

- B-37 的 7 处 `[chat-post]` print 现为 `main.py:2073 / 2104 / 2133 / 2162 / 2304 / 2380 / 2599`（原 `1884/1915/1944/1973/2105/2181/2395`）；
- B-06 的 `mark_depleted` 函数体现为 `llm_registry.py:626-639`；
- `retrieval.py` 的锚点块（`:951-986`，含 `anchor_guaranteed`、`dropped_anchors`、`(docs + anchor_head)[:k]`）与两处 `filt = {"category": category}`（`:733`、`:1205`）**字节未动** ⇒ B-10/B-11/B-05 的行号与判据照原样成立。
- `settings.py`：`agent_enabled` 原报 `:83` 现为 **`:85`**，且**默认仍是 `False`**、两份 `.env` 都没有 `AGENT_ENABLED`/`FEATURE_AGENT` 覆盖 ⇒ B-05/B-06 那句"今天不是现网故障，是放量地雷"**在新 HEAD 上照旧成立**（这句很关键，别被"Agent 已合进候选"读成"已放量"）。`agent_max_steps` 原报 `:94` 现为 **`:96`**（默认 20、`ge=1 le=32`）。
- `tests/test_llm_failover.py`：钉 permanent 的 parametrize 原报 `:163-166`，现复量为 **`:167-170`**（transient 在 `:160-164`）；另有一处 `:351` 也把 400/401/403/404 钉了一遍。

### 11.4 仍开、且我按新 HEAD 逐行重读确认（本轮亲读，非转抄）

B-02（`_rate_key` 里 `cf = request.headers.get("CF-Connecting-IP")` 仍无条件信任）、B-05、B-06、B-07（沉淀路径 `main.py:1012-1014` 仍无 `sv.ok` 门）、B-09、B-10/B-11、B-17（登录锁窗口仍是 `ts if cnt > 0 else now`，`main.py:402`）、B-19（`async def _invoke_llm` 在 `:1488`、E9 兜底调用在 `:2449`，仍用未重 pick 的 `flag_llm`）、B-20、B-28、B-42（`database.py` 仍无 `PRAGMA journal_mode`，全仓只有 `quota_store.py:27` 设 WAL）、B-46（`_cutoff()` 在 `main.py:1128` 仍是本地日）。

### 11.5 新增测试有没有把我的开放项钉住（只查在册测试，不臆测）

| 新测试 | 钉住了什么 | 对我的结论的影响 |
|---|---|---|
| `tests/test_upload_rate_limit.py`（28 行，真 limiter，`[400]*limit + [429]`） | 上传限流**本身**会 429 | **不测** `CF-Connecting-IP` 伪造 ⇒ B-02 仍裸 |
| `tests/test_cache_scope_invalidation.py`（364 行） | scope 不等 ⇒ miss、失效通路 | 支持 §11.2 的降级判断；**不**覆盖"答案与 sources 不同源" ⇒ B-03 的剩余洞仍开 |
| `tests/test_cancel_boundaries.py`(1051) / `test_stream_cancellation.py`(1270) / `test_chat_turn_persistence.py`(583) / `test_llm_lifecycle.py`(343) | 取消与回合持久化 | 里面**没有** `max_steps` 形状 ⇒ B-01 当时仍未被钉（直到我在 §12 跑定向用例） |
| `tests/test_agent_resume.py:675-730` | `max_steps=8` 且 `steps=8` 的 WAITING_USER，第二次 resume **必须** `ResumeRunConflict` | 它**把 §12.2 的死锁当预期行为钉住了**，docstring 自陈历次修复是"抬默认预算 8→16" ⇒ 不是新发现无人知，而是"边界没修、只推远" |

**§11 汇总**：46 条里 3 条已闭、1 条降级、2 条改指针、42 条在新 HEAD 上仍开；另有 3 条新增（B-47/B-48/B-49，见 §12 与下表）。

| 编号 | 档次 | 一句话 | 证据 | 我的建议（一词可答：做/不做/改判） |
|---|---|---|---|---|
| B-47 | 高（**§12 实测新增**，与 B-01 同一根） | 停在 WAITING_USER 且 `steps` 恰 = `max_steps` 的 run **永远恢复不了**：`transition(…, PLANNING)` 要 +1 步 ⇒ `BudgetExceeded` ⇒ `ResumeRunConflict` ⇒ HTTP 409，文案还是「Agent 任务已变化，无法恢复」（`controller.py:179`）——**任务没变，是预算没了**。真数据复算：语料 47 只 waiting_user 里 **16 只 steps==cap**，16 红 / 31 绿且闭合检查全对。修复史是 8→16→20 抬 cap（`test_agent_resume.py:675-`、`settings.py:96` 现默认 20），边界本身没动 | A（§12.2 逐 run 真数据复算 + 在册测试原文） | 做：与 B-01 并一票，给「终稿边 + 恢复边」这两类 1 步边预留步数或不计步，并把 409 文案按成因拆成三条；不要再用"抬 cap"当修复 |
| B-48 | 中低（**§12 实测新增**） | `mark_depleted(key, "model_failure")` 的实现是 `runtime_used += quota_left`（`llm_registry.py:626-639`）⇒ **一次 400/401/403/404 在记账面上等于"这个模型积分用完了"**，而 `reason` 参数被丢弃。4xx 判永久是有意设计且被 `test_llm_failover.py:167-170` 钉住，我不重开它；问题是**归因通道只有一个**：管理台、`quota_store`、看门狗看到的都是"配额耗尽"，真实成因是"请求被拒"，运维据此校准会去加积分而不是改 payload | A（§12.4 真 openai SDK 打回环 stub 的状态码网格） | 做：拆 exhausted / rejected 两条通道，rejected 走冷却 TTL 且落结构化日志（与 B-06 同票） |
| B-49 | 中低（**§12 实测新增**） | 法名归一只剥**全角**括注：`_source_key` 的正则是 `（[^）]*）\s*$`（`retrieval.py:443-449`），实测 `劳动合同法(2012修正)`（半角）原样返回、`中华人民共和国劳动合同法(2012修正)` 归一成 `劳动合同法(2012修正)` ⇒ 与库内裸名不匹配。元典的权威法规名**正是这个形状**（本轮 7 次返回里两部法都带半角修正括注），10 个消费点（`retrieval.py:394/396/507/509/521/534/551/634/640/792`、`main.py:1174/1181`）会判"库里没有" ⇒ 引用校验假阴性。另：`_norm_source` 剥前缀后不 strip（`中华人民共和国 民法典` → ` 民法典`），只有 `_source_key` 末尾 `.strip()` 兜住 | A（§12.5 跑的是真函数，六格表 4 绿 2 红） | 做：正则改 `[(（][^)）]*[)）]\s*$`，归一单测同时放全角与半角两格（只测一边等于没测） |

---

## 12. 第二轮实测：副本树定向用例 + 内容层（元典）核对

**方法与边界**（Owner 批准"允许，副本树 + 定向用例"）：

- 副本树 = `%TEMP%\fazhi-audit2-20261009\backend`，用 `git ls-files -z -- backend/` 建 **tracked-only** 树：**清单 292 项 / 实拷 292 项**（闭合检查通过，未跟踪文件不进面）；解释器用现役 `backend/venv/Scripts/python.exe`，`cwd=副本/backend`，被测代码是副本里的字节。
- 写侧全在 `%TEMP%`：副本自带 `tests/conftest.py` **无条件**把 `DATABASE_URL`/`QUOTA_DB`/`CHROMA_DIR` 指到进程私有临时路径（该文件注释自陈这三条是防"collection 期连真实库"）。
- **真实状态零改动**（跑前跑后各取一次，四读数逐字相同）：`backend/app.db` sha256 `3638b2e453ed73b7…`、`backend/data/quota_used.sqlite` sha256 `922dc764dee23263…`、`backend/chroma_db` 38 文件 / 365,566,410 字节、`git status --porcelain --untracked-files=no` 6 项（backend 0 项）。
- 元典侧按批准口径"抽查，控制在 10 次调用内"：实 used **10 / 10**。
- **脚本落点（本轮四个探针，全在 `%TEMP%`，未进仓库）**：`C:\Users\33393\AppData\Local\Temp\fazhi-audit2-20261009\backend\backend\tests\test_audit2_b01_finalize_budget_boundary.py`、同目录 `test_audit2_source_key_shapes.py`、`...\fazhi-audit2-20261009\probe\b05_chroma_eq_missing_key.py`、`...\probe\b06_llm_status_classify.py`。**这暴露一个我自己要摊开的限制**：按"只读审查、不新增在册文件"的边界，探针脚本没入库 ⇒ 本轮数字目前**只能靠这段路径 + §12 各小节的命令复现**，`%TEMP%` 会被清。要不要把这两个定向用例正式入库（它们本就是 §2 里我"建议验证"那两条的用例本体），是一个一词可答的决定，见 DB-15 末句。

### 12.1 B-01 的四条腿（`tests/test_audit2_b01_finalize_budget_boundary.py`，4 passed / 0 failed）

| 腿 | 内容 | 读数 |
|---|---|---|
| L1 对照（必须绿） | `steps = max_steps - 1` 的 DRAFTING 调 `persist_agent_final_once` | 返回 `True`，消息落库 ⇒ 夹具本身有效，红不是空转 |
| L2 判据 | `steps == max_steps` | 抛 **`BudgetExceeded`**，且 `decision.reason == "budget_exceeded:steps"`（钉死红的是哪条规则）；同时断言 `not issubclass(BudgetExceeded, AgentFinalizationConflict)` |
| L3 后果 | L2 之后查库 | assistant 消息 **0 条**、`AgentRun.status` 仍是 `drafting` ⇒ 已写好且 PASS 校验的终稿被丢弃 |
| L4 可达 | `EVALUATING @ steps=cap-1 → transition(DRAFTING)` | 不报错，落点 `steps == max_steps` ⇒ 这是预算内合法路径的产物；进 DRAFTING 只花 **1** 步，而两处预检都是 `steps + 3 > max_steps`（`controller.py:726` 工具侧、`:970` 扇出侧）⇒ **预检结构上挡不住这个落点** |

归因链闭合：`chat_integration.py:224-229` 的 `try` 只捕 `InvalidTransition`（`BudgetExceeded` 是 `RuntimeError`）→ `service.py:618-641` 的 `except Exception` 把它折成 **`AGENT_STORAGE_FAILURE`** → 该码**不在** `routing_metrics.py:13-21` 的 `TECHNICAL_FALLBACK_REASON_CODES`（白名单里有 `AGENT_BUDGET_EXCEEDED`、没有 `AGENT_STORAGE_FAILURE`）⇒ 换成正确标签本可换一条快车道答案，现在换不到，用户拿到硬错误。

**结论**：B-01 的证据等级由「A（可达性 C）」升为 **A 全坐实**。B 路上轮补的"窗口比我说得窄（`max_tool_calls=10` 会先触发优雅 STOPPED）"仍然成立——所以这条是"tool_calls 未满而 steps 恰满"的窄窗口，不是常态；本轮的 L4 证的是**窗口存在且合法**，不是它常见。

### 12.2 B-47：同一根，射程更广（真数据，不构造）

```bash
# 只读复算（真跑过；`mode=ro` URI + 只 import schemas/state_machine，不碰 chroma/不写库）
backend/venv/Scripts/python.exe - <<'PY'
import json, sqlite3, sys
sys.path.insert(0, "backend")
from agent.schemas import LegalAgentState, AgentStatus
from agent.state_machine import transition, BudgetExceeded
con = sqlite3.connect("file:backend/app.db?mode=ro", uri=True)
rows = [json.loads(s) for (s,) in con.execute("SELECT state_json FROM agent_runs WHERE status='waiting_user'")]
print("总数:", len(rows), "| steps==cap:", sum(1 for d in rows if d.get("steps") == (d.get("budgets") or {}).get("max_steps")))
red = green = 0
for d in rows:
    st = LegalAgentState.model_validate_json(json.dumps(d))
    try:
        transition(st, AgentStatus.PLANNING); green += 1
    except BudgetExceeded:
        red += 1
print("resume transition 红:", red, "绿:", green)
PY
```

实跑输出：`总数: 47 | steps==cap: 16` / `resume transition 红: 16 绿: 31`。闭合检查（另一次跑法逐只打印）：red ⟺ `steps==cap` 全对、green ⟺ `steps<cap` 全对；同语料 `degraded_reason` 分布 `None 215 / PLANNER_PARSE_ERROR 66 / AGENT_BUDGET_EXCEEDED 14`；样本时间轴 `2026-09-07 ~ 2026-09-18`（**评测语料，非线上**）。

三条必须一起读：**机制是活的**（16/47 卡死）、**它是已知且被当预期的**（`test_agent_resume.py:675-730` 用 `max_steps=8` + `pytest.raises(ResumeRunConflict)` 钉住，docstring 自陈"修复方式为提升默认预算至 16"）、**修复史就是不断推远边界**（8→16→20，`settings.py:96` 现默认 20，`ge=1 le=32` ⇒ 抬到 32 也只是把同一形状推到更远的地方）。用户可见的是 `RESUME_CONFLICT_DETAIL`（`controller.py:179`），同一串还被版本冲突与他人 run 复用（`:244`）⇒ 三种成因共用一句"任务已变化"，运维无法归因。

### 12.3 B-05：Chroma `$eq` 语义 + 可达性来自 prompt（`probe/b05_chroma_eq_missing_key.py`，chromadb 0.4.24 现跑）

| 腿 | where 形状 | 读数 | 意义 |
|---|---|---|---|
| 1 | `{"category": "民法"}`（集合内一条有该键） | `['c']` | 控制腿：过滤机制本身工作，非空转 |
| 2 | `{"category": {"$eq": "民法"}}` | `['c']` | 隐式与显式同判 |
| 3 | 无过滤 | `['a','c','b']` | 基线 |
| 4 | `{"category": "刑法"}` | `[]` | 值不匹配 → 空（预期） |
| 5 | `{"$ne": "民法"}` | `[]` | **缺键行同样被排除** ⇒ `$ne` 不是逃生门（这条我原先没想过） |
| 6 | `get(where={"category":"民法"})` | `['c']` | `get` 与 `query` 同语义 |
| **7** | **全集合都没有该键**，用生产形状 `{"category": "民法"}` | **`[]`** | ⇒ **静默零结果**，上轮 A 路要求补的那一半，现在补上了 |
| 8 | 同集合无过滤 | 3 条 | L7 的对照，证明红不是夹具坏 |

链路逐段读通（这一段是本轮最该被决策的部分，因为它不是"库里少个键"而是"prompt 教模型去用一个库里不存在的键"）：

1. `agent/runtime.py:85` Planner 系统提示词**明写**：`retrieve_laws {"query":"检索词","k":4}（k 可选 1-20，默认 4；category 可选）`；
2. `agent/planner.py:107` 用 `policy.input_model.model_validate(raw_args)` 校验，`RetrieveLawsInput`（`tools/contracts.py:85-89`）声明了 `category: str | None`，`extra="forbid"` 挡不住**已声明**字段；
3. `tools/legal_retrieval.py:22` 原样透传 `category` 进 `retrieval.retrieve`；
4. 向量侧 `retrieval.py:733` `filt = {"category": category}` → L7 的 `[]`；BM25 侧 `retrieval_core.py:228` `if category and d.metadata.get("category") != category: continue`，而 BM25 文档来自 `retrieval.py:686` **同一个** `_collection.get()` ⇒ **两个池一起清零**，`hybrid_retrieve` 返回 `[]`；
5. 无日志、无 error 帧，Agent 只看到 MISSING_EVIDENCE → 回落/降级。
6. 唯一逃生口：`retrieve()` 先走 `parse_article_query` 条号直查（不吃 category）⇒ 问句形如"《民法典》第577条"仍有证据，**普通问句零证据**。

历史触发率**读不出来**，且我一度读数错：`agent_steps.normalized_input` 存的是 **64 位 sha256**（不是 JSON）。我第一次按 JSON 去 `LIKE '%category%'` 得 0，控制腿 `LIKE '%"query"%'` 也 0 —— 那正是"尺子空转"的信号，该读数作废。所以 B-05 档位仍按高，但措辞要准：**判据链已 A，触发频率未知且本机不可测**。

### 12.4 B-06 / B-48：真 SDK 状态码网格（`probe/b06_llm_status_classify.py`，openai 1.109.1 打 127.0.0.1，不出网）

```
400 BadRequestError            status_of=400  is_transient=False → mark_depleted
401 AuthenticationError        status_of=401  is_transient=False → mark_depleted
403 PermissionDeniedError      status_of=403  is_transient=False → mark_depleted
404 NotFoundError              status_of=404  is_transient=False → mark_depleted
408 APIStatusError             status_of=408  is_transient=True  → 只排除
429 RateLimitError / 500 / 502 / 503 / 504      is_transient=True  → 只排除
未监听端口 → APIConnectionError  status_of=None is_transient=True（F7 包装形态在真 SDK 下成立）
同一 400 连打三次 → 三次同判（⇒ 请求形状类 400 会逐个把链上模型标死）
```

上轮那条"必须靠跑才能定"里的 ② 本来指望 `grep backend/logs/*.log` 找历史 400 —— **本轮实测：`logs/` 在本工作区 `find logs -type f` = 0 文件**（目录不存在），考古这条路是空的。所以我把它换成能定的那一半：**真返 4xx 时我们的代码判什么**。分类本身是有意设计且已被 `test_llm_failover.py:167-170` 钉住（400/401/403/404/422 → permanent），我不重开；新增的是 B-48 那条归因面（`mark_depleted` 把"被判死"记成"配额用完"、`reason` 丢弃）。

### 12.5 B-49：跑真函数的六格归一表

```
'中华人民共和国民法典'            → '民法典'                      ✓
'民法典'                          → '民法典'                      ✓
'劳动合同法（2012修正）'  全角     → '劳动合同法'                  ✓
'宪法（1982年）'          全角     → '宪法'                        ✓
'劳动合同法(2012修正)'    半角     → '劳动合同法(2012修正)'         ✗ 未剥
'中华人民共和国劳动合同法(2012修正)' → '劳动合同法(2012修正)'       ✗ 未剥
```

4 绿 2 红 ⇒ 尺子能分辨，不是恒红；红的正是元典返回的形状（见 12.6）。

### 12.6 内容层：元典抽查 7 条在册引用（`yuandian_get_legal_article_detail`）

抽查对象是 `domain_rules.py`（35 组唯一 (法名, 条号) / 7 部法，我抽 **7 组 ≈ 20%**）与 `agent/limitation_calc.py` 的数字断言：

| 我核对的在册断言 | 元典权威返回 | 判定 |
|---|---|---|
| `CIVIL_GENERAL_YEARS = 3`（民法典 188①） | "…诉讼时效期间为三年"，`effective_date 2021-01-01`、`现行有效` | 一致 |
| `CIVIL_MAXIMUM_YEARS = 20`（188②） | "…超过二十年的，人民法院不予保护" | 一致 |
| 民法典 497 = 格式条款无效情形 | 三种情形列举齐全 | 一致 |
| "普通时效自 2017-10-01 起为 3 年（民法总则 188）" | 民法总则 188：三年，`effective_date 2017-10-01`，**`validity_status 失效`**（用 `reference_date=2019-01-01` 取到旧版） | 一致，且分界日得到权威支持 |
| 劳动合同法 47 = 经济补偿计算标准 | 每满一年一个月 / 六个月以上按一年 / 不满六个月半个月 / 社平三倍封顶且年限 ≤ 12 年 | 一致 |
| 劳动合同法 87 = 违法解除赔偿 | "依照本法第四十七条规定的经济补偿标准的**二倍**" | 一致 |
| 消保法 55 = 欺诈退一赔三 | "**三倍**；增加赔偿的金额不足五百元的，为五百元"（2013修正，`effective_date 2014-03-15`） | 一致 |

配套两条**形状差**（对"接外部权威源"有直接决策意义，我方库侧只读复量、不额外花调用）：

- 我方同条正文与数字**逐字对得上**（read-only 按 (source, article) 精确取回：民法典 188/497、劳动合同法 47/87、消保法 55、调解仲裁法 27 各 1 命中），但我方 chunk **带章名**（如 `第九章　诉讼时效\n第一百八十八条　向人民法院…`），元典 `content` 从条身开始 ⇒ 任何"逐字一致"类校验要先剥章名（`　` 是 U+3000，删不得——`\s` 本来就含它）。
- 我方 `source` 是裸名（`民法典`/`劳动合同法`/`消费者权益保护法`/`劳动争议调解仲裁法`），元典是 `中华人民共和国劳动合同法(2012修正)` 这类**前缀 + 半角修正括注** ⇒ 撞 12.5 的 B-49。
- **时效字段对照**：元典每条都带 `effective_date` / `publication_date` / `validity_status`，并且**能返回已失效版本**；我方两个条文集合现量各 **10,266 行、每行 8 键**（`article/chapter/effective_from/effective_to/file_hash/origin/source/status`），`effective_from`/`effective_to` **非空行数 = 0**。这不改判语料时效数据票，但给它一个事实：缺的那三样在权威源侧有对应物可取。

**成本与诚实边界**：最对症的工具 `yuandian_hall_detect`（自动抽取正文引用并比对权威原文）按免费政策**仅 VIP 可用**（`countBalance = 0`），所以**没跑成**，改成逐条详情人工比对；调用与积分：`get_user_balance`×2 + `get_free_policy`×1（这三条按政策不扣积分）+ 法条详情×7 = **10 次调用**，积分 `4500 → 4493`（7 分，占每月赠送 3500 的 0.2%）。

### 12.7 本轮仍未做（就地更正 §9）

1. **§9 第 1 条作废一半**：那三条"必须靠跑才能定"里 B-01（§12.1）、B-05（§12.3）已用定向用例/探针**坐实**；B-06 的"provider 会不会因内容返 400"从"待跑历史日志"改成"已做行为面实测（§12.4）"，但**历史是否真发生过 400 仍不可知**——`logs/` 在本工作区是空的，不是"我没去翻"。
2. **§9 第 8 条有一处读数错**：那里写的"两集合各 10266 条、**9 个键**"应为 **8 个键**（本轮按行分布复量：10,266 行全部是 8 键，两集合一致）。§0 的 B-05 行原本写的就是 8，所以这是**我这份报告的内部不一致**，就地更正，不改结论。
3. 仍未跑：B-18 的 OOM、B-34 的实体展开、B-04 的具体 claim 样本、B-09/B-37 的运行时后果（这几条要的是端到端注入或真实上游，不是副本树定向用例能覆盖的形状）。
4. 内容层覆盖：`domain_rules.py` 35 组里我只抽了 7 组，其余 28 组**未核**；`qa_seeds.py`/`clarify.py`/`prompts.py` 里的硬编引用也未核。
5. 派单顺序按 §11 重排：B-08/B-25/B-41 从队列里摘掉（已闭），B-03 降到"底线相关"中段，B-47 并进 B-01 那一票，B-48 并进 B-06，B-49 单独一行级（正则 + 两格单测）。

### 12.8 本轮我自己造成的两次写事故（都已回滚，如实记）

写 §11/§12 的过程中我动了这份报告在册正文两次，都属"仪器/手法错"，不是"结论错"，但按本轮口径必须落进正文而不是只在对话里说：

1. **结构检查器本身错，导致我去"修"了一条正确的行**。我用 naive `split('|')` 数表格列数做收口检查，它把 **B-06 那行**（其 grep pattern 早已按 GFM 写成 `\|` 转义）判成列数不符，于是我做了一次"修形"替换——结果反而把那行挤成 **6 列**（真缺陷）。发现后用一次拼接把它改回 5 列，并按"分隔符只数前一个字符不是反斜杠的竖杠"重写检查器后复量：**16 个表格块、列数不一致 0 行**。同一次复跑里它还把 §9 第 7 条的 `` `**kwargs` `` 误报成加粗失配——那是 code span 里的字面量，不是标记。**教训：自查工具自己也要有阴性对照**，否则它会把对的判成错的，而"修"的动作是真会落进文件的。
2. **一次 Edit 打靶打错行，静默删掉了别人的半句**。我要给 B-46 那条加"行号已漂移到 `main.py:1128`"的行内注释，`old_string` 却写成了 **B-45** 的开头片段（`同族防呆**不对称**：` + `chroma_dir_guard.assert_matches`），替换后 B-45 少了那半句而 **Edit 返回成功**。是我改完按行 `awk` 复读该行才发现，并原样回滚；最终 B-46 的注释落在正确行、B-45 现量完整（回滚后重读该行确认它以「同族防呆**不对称**：chroma_dir_guard.assert_matches 只被…」开头，与误删前逐字一致——**这里不整段手抄，抄了就等于再造一个会过期的读数**）。**教训：往长文档里插行内注释，动手前 grep 锚点是否唯一落在目标行，动手后按行读回整句，不看工具回执。**
3. 一处**读数错在本报告内部存在过**并已就地更正：§9 第 8 条写"两集合各 10266 条、9 个键"与 §0 的 B-05 行写"8 个键"互相矛盾。我没有先猜"是代码变了"，而是换成**每行键数分布**这根轴复量（`Counter(len(metadatas[i]))`）⇒ 真值 8，错的是我手抄的那处；更正已落在 §9 第 8 条原格内并写明"这是本报告内部不一致"。
4. 还有一条**判据轴的教训值得记**：`agent_steps.normalized_input` 是 64 位 sha256 而不是 JSON，我第一次拿它 `LIKE '%category%'` 得 0 命中并几乎当成"从未有人传过"，是控制腿（`LIKE '%"query"%'` 也 0）当场把尺子量空暴露出来。**否证型 grep 必须自带阳性对照**，否则 0 命中既可能是"没有"也可能是"读不出"——这两件事在报告里的写法必须不同（本轮 §12.3 与 §7 尾都按"不可知"写，没写成"从未发生"）。

---

## 13. 实施轮补记（2026-10-09 第三轮）：DB-15 / DB-16 / DB-17 / DB-18 按推荐落地并复量

**触发**：Owner 一句「按推荐做」⇒ 本轮从"只读审查"切换为"在授权范围内实施这四票"。边界随票收窄：只动这四票指向的文件，**未 commit、未 push、未移 ref、未轮换凭据、未真实入库、未签 D2**。

### 13.0 顺序与前置（我自己声明的那条"先验证后动手"）

动第一行代码之前先取了**改前全量基线**，之后所有"改后"读数都对着它说话：

| 时刻 | 命令（在 `backend/` 下，用 `backend/venv` 解释器） | 读数 |
|---|---|---|
| 改前 | `venv/Scripts/python.exe -m pytest -q -m "not slow" -p no:cacheprovider --no-header -rs` | `1860 passed, 2 skipped, 18 deselected, 289 warnings in 322.68s`，0 failed（日志 `%TEMP%\fazhi-audit2-20261009\pytest_baseline_before.txt`） |
| 改后第一趟 | 同上 | `6 failed, 1900 passed, 2 skipped, 18 deselected ... in 322.18s`（6 只全在 `tests/test_llm_admin.py`，**两条不同的** `AttributeError`，见 13.4） |
| 改后终趟 | 同上 | `1906 passed, 2 skipped, 18 deselected, 289 warnings in 317.73s`，0 failed（日志 `%TEMP%\audit2-impl-20261009\full-post2.log`） |

**闭合核对**（防"用例数"对不上）：`1906 − 1860 = 46`；本轮新增用例的 collected 数 = 新四只文件 `10 + 7 + 22 + 6 = 45`（`--collect-only` 现量）＋ `test_llm_failover.py` 里新增的那 1 只控制腿 = **46**，两轴相等。
**两条 skip 的名字钉在终趟**（`-rs` 现量，都不是本轮改动面）：`tests/test_fast_path_law_version_gate.py:460`（未设 `FZ_DUMP_FRAMES` 的逐帧采集口）、`tests/test_stream_exit_law_version_gate.py:485`（未设 `S6_DUMP_FRAMES` 的票 C 采集口）。**但"改前也是这两只"这句是推断而非读数**：`grep -c SKIPPED "$TEMP/fazhi-audit2-20261009/pytest_baseline_before.txt"` = 0（基线那趟日志里没有 short summary 段），我只能给间接证据——本轮 `git diff --name-only` 与新增文件里都不含这两只测试文件，且基线与终趟的 skip **计数**同为 2 ⇒ skip 是设计内、不是被本轮放宽。
**HEAD 两端相同**：`0b543960c7172ce1ffea57616952e4d5525190c4`（基线与本轮收尾各读一次 `.git/refs/heads/master`），本轮**没有产生任何提交**，所以基线与终量读的是同一笔树。

### 13.1 改动清单与归属（现量 `git diff --numstat`；**B 路补码后于 §13.10 末尾再复量一次，表内已是终值**）

| 文件 | +/− | 哪一票 |
|---|---|---|
| `backend/domain_rules.py` | 35／0 | DB-18（新增**读侧**唯一真源 `norm_law_name` + `SOURCE_NAME_PREFIX`；未并清单在 §13.10 ④ 点名） |
| `backend/retrieval.py` | 83／21 | DB-18（`_source_key`/`parse_article_query` 接真源）＋ DB-16（三处零命中回落 + `_note_category_filter_miss`） |
| `backend/agent/writer.py` | 8／5 | DB-18（`_canonical_law_name` 接真源） |
| `backend/scripts/smoke_citation_full.py` | 1／10 | DB-18（强一档那一族四份字面量副本里的**最后一份**删除，改 import 真源） |
| `backend/agent/state_machine.py` | 22／1 | DB-15（`FREE_STEP_EDGES` 表 + 计费式改为 `charge`） |
| `backend/agent/service.py` | 20／0 | DB-15（`except BudgetExceeded` 抢在 `except Exception` 前，映射 `AGENT_BUDGET_EXCEEDED`） |
| `backend/agent/controller.py` | 25／17 | DB-15（`ResumeRunConflict` 带 `reason_code`，15 处 raise 各归其类；用户可见文案 `RESUME_CONFLICT_DETAIL` 一字未改） |
| `backend/main.py` | 30／5 | DB-15（resume 冲突落 `agent_resume_conflict` 日志）＋ DB-17（两处失败回调按病因分通道） |
| `backend/llm_errors.py` | 22／0 | DB-17（`REQUEST_SHAPE_STATUS` + `is_request_shape_rejection`；`is_transient_error` 与 `TRANSIENT_STATUS` **未动**） |
| `backend/llm_registry.py` | 68／0 | DB-17（`REJECT_COOLDOWN_S=300`、`rejected_until`/`rejected_now`、`pick` 跳过冷却、`mark_rejected`、`mark_depleted` 开始落日志并保留 `reason`、快照多 `rejected_remaining_s`） |
| `backend/agent/runtime.py` | 11／3 | DB-16（提示词删「category 可选」）＋ DB-17（failover 环按病因分通道） |
| `backend/observability.py` | 22／0 | **五条**新字段进 `_ACCOUNT_FIELDS`（`:111` `agent_resume_reason`、`:118-119` `category_filter_value`／`category_filter_stage`、`:126-127` `model_failure_channel`／`model_failure_reason`） |
| `backend/tests/test_agent_resume.py` | 82／33 | DB-15（两只钉死旧形状的断言改判，逐条见 13.3；CRLF 保持原样（盘上现量 923 只 CRLF、0 只裸 LF）） |
| `backend/tests/test_llm_failover.py` | 57／12 | DB-17（permanent 三只改钉"通道"，另加 1 只控制腿；替身改真类） |
| `backend/tests/test_llm_admin.py` | 11／10 | 仪器修复（entry 替身改真类，见 13.4） |

新增四只测试文件（**未跟踪**，`git ls-files --others --exclude-standard backend` 现量）：`tests/test_law_name_normalization.py`（7 collected）、`tests/test_agent_budget_terminal_edges.py`（10）、`tests/test_retrieval_category_fallback.py`（6）、`tests/test_llm_reject_channel.py`（22）。

**同一工作树里不属于本轮的改动**（并行会话的未提交面，我一行没碰）：`frontend/app/admin/sections/KnowledgeSection.tsx`、`frontend/app/admin/sections/UploadSection.tsx`、`frontend/app/chat/page.tsx`、`frontend/app/globals.css`、`frontend/components/chat/InputBar.tsx`、`docs/process-archive/superpowers/plans/2026-09-29-local-candidate-decision-and-release-prep.md`。**将来"把改动提交"这句话如果要下达，请按上面这张表点名**，否则会把这些一并带走。

### 13.2 用同一批尺子复量：改前那份不是手抄，是另一棵树真跑出来的

配方（本轮统一）：`%TEMP%\fazhi-audit2-20261009\backend\` 是**改前副本树**（§12 那轮建的，源码仍是 `0b54396` 的形状）；`%TEMP%\fazhi-audit2-20261009\patched\backend\` 是把本轮 12 只改动源文件 `cp` 进去、并清掉全部 `__pycache__` 的**改后副本树**。同一支脚本、同一个 venv 解释器、两棵树各跑一次，只差"源码是否打了补丁"这一根轴。

**DB-18（B-49 法名归一）—— §12.5 那六格原样复跑**

| 输入 | 改前 `_source_key` | 改后 `_source_key` |
|---|---|---|
| `中华人民共和国民法典` | `民法典` ✓ | `民法典` ✓ |
| `民法典` | `民法典` ✓ | `民法典` ✓ |
| `劳动合同法（2012修正）`（全角） | `劳动合同法` ✓ | `劳动合同法` ✓ |
| `宪法（1982年）`（全角） | `宪法` ✓ | `宪法` ✓ |
| `劳动合同法(2012修正)`（**半角**） | `劳动合同法(2012修正)` ✗ | `劳动合同法` ✓ |
| `中华人民共和国劳动合同法(2012修正)` | `劳动合同法(2012修正)` ✗ | `劳动合同法` ✓ |

`4 绿 2 红 ⇒ 6 绿 0 红`，红的那两格正是元典返回的形状（§12.6）。复量脚本 `%TEMP%\audit2-impl-20261009\ruler_norm.py`（同一份输入表 + 另打 `writer._canonical_law_name` 与 `parse_article_query` 两个消费点）。负向自证在册在 `tests/test_law_name_normalization.py::test_legacy_fullwidth_only_regex_cannot_pass_the_halfwidth_sample`——它先断言"只认全角的旧正则**过不了**半角样本"，否则这几条是恒真的。
一处**只涨不跌的连带变化**要说明：`scripts/smoke_citation_full.py` 与 `retrieval._source_key` 的真源合一后，在册用例 `tests/test_smoke_citation_assertions.py:250` 从"防两份实现分叉"降级成"两份真函数相等"的恒真哨兵（再分叉时仍会红）。我没改它——它属于 DB-3"引用真源收口"那一票的面。

**DB-15（B-01 + B-47 步数计费）—— §12.1 的 L1–L4 探针原样复跑**

| 腿 | 钉什么 | 改前树 | 改后树 |
|---|---|---|---|
| L1 | `steps = cap−1` 时终稿写入成功（对照腿，必须一直绿） | 绿 | 绿 |
| L2 | `steps = cap` 时 `persist_agent_final_once` 抛 `BudgetExceeded:steps` | **绿（缺陷形状成立）** | **红（不再抛 ⇒ 缺陷消失）** |
| L3 | L2 之后无 assistant 消息落库、run 停在 `drafting` | **绿（终稿确实被丢）** | **红（终稿写进去了）** |
| L4 | `EVALUATING(steps=cap−1) → DRAFTING` 落点恰为 `cap` | 绿 | 绿 |

改后两红正是本轮要的结果，改前两绿（L1/L4）没被顺手放宽 ⇒ 尺子两头都咬得住。入库版是 `tests/test_agent_budget_terminal_edges.py`（10 collected：4 只计费腿 + 4 只仍会计步的边 + 1 只 `FREE_STEP_EDGES` 逐字钉 + 1 只 AST 腿断言 `except BudgetExceeded` 排在 `except Exception` **之前**且映射到 `AGENT_BUDGET_EXCEEDED`，另含 `is_technical_fallback_reason` 正反两向）。

**这条豁免会不会开出一个新洞——我自己先三问自证（都在源码里读到，不是设想）**：
1. **"恢复边不计步"是否让 `PLANNING→…→WAITING_USER→PLANNING` 无限往复？** 不会。豁免只给**回**的那条边；**进** `WAITING_USER` 有两条路，都仍有界：`controller.py:926` 走普通 `transition` ⇒ 照旧计 1 步；`controller.py:1112-1113` 走 `register_clarification` ⇒ 由 `_limit(state, "clarifications", …, max_clarifications)` 挡（`agent/schemas.py:216` 默认 3）。⇒ 每一轮往返至少花 1 步或 1 次澄清额度，两者都有硬上限。
2. **恢复进来后是不是"立刻再炸一次、只是换个死法"？** 不是 409 那种死法。恢复后若某条**会计步**的边越界，落点是 `_persist_budget_stop`（`agent/controller.py:1181-1204`）：它以 `decision="stop"`、`reason_code="AGENT_BUDGET_EXCEEDED"` **把 STOPPED 状态持久化**并返回 `degraded=True`。改前的形状是"resume 自己在入口就被 409 挡死 ⇒ run 永卡 `waiting_user`，既不出答案也不落 stop 检查点"；改后"进得来，进不来下一步就留下一条可读的 stop 记录"。这两件事的运维差别是可归因性，不是把预算变多了。
3. **`steps` 的语义变了，谁在把它当工作量读？** 本轮**未**改任何以 `steps` 为口径的报表/评测算法；`FREE_STEP_EDGES` 生效后同一 run 的 `steps` 会比改前少 1–2。§12.2 那句"16/47 只永久不可恢复"是**改前**读数（按当时的计步规则），我不拿它当改后应复算的基线；若要复算，需要重跑那 47 只 run 的状态回放——本轮没跑，列进未做。

**DB-17（B-48 记账通道）—— 状态码网格改前/改后成对**

脚本 `%TEMP%\audit2-impl-20261009\b48_grid2.py`（两棵树各跑一次，只打 8 个状态码，不出网）：

| status | 改前 `transient` | 改前通道 | 改后 `transient` | 改后通道 |
|---|---|---|---|---|
| 400／401／403／404／422 | False | exhausted（**唯一通道**） | False | rejected（冷却 300s） |
| 408／429／500 | True | transient（只排除） | True | transient（只排除） |

`transient` 那一列改前改后**逐格相同** ⇒ 我在 DB-5/DB-17 承诺的"不动 `is_transient_error` 分类口径"是可核的，不是口头的。记账面另跑 `%TEMP%\audit2-impl-20261009\b48_channel_grid.py`：同一只 `quota_total=100` 的真 `ModelEntry`，`mark_depleted` ⇒ `quota_left 100 → 0`、`unavailable=True`（两棵树同读数，耗尽通道语义未动）；`mark_rejected` ⇒ `quota_left 100 → 100`、`unavailable=False`、`rejected_now=True`，且 `pick` 对它抛 `QuotaExhausted`（自动路由退出但配额账一字未动）。改前树打印 `B rejected : 通道不存在`——那正是 B-48 的原始形状。

**冷却的运行学（写清楚，免得被读成"更聪明的熔断器"）**：同一份持续被打回 400 的 payload，效果是**每次请求冷却链上一只模型 300 秒**，N 只之后该 payload 的请求会直接命中"`pick` 抛 `QuotaExhausted`→`_safe_pick` 回落 `registry.get()`"这条在册兜底路（§1/B-06 已核：不 503，走带注记的降级答复）。⇒ 与改前的差别是**可自愈 + 归因正确**（配额账不再被写满），不是"少烧钱"；〔这句里"回落……走带注记的降级答复"那半在 §13.10 ① 补码之后才成立——补码前 `_safe_pick` 的回落支绕过冷却且不标降级〕300 秒后同一模型会再被试一次，所以长期看这类 payload 每分钟仍会消耗 `N/5` 次上游调用——这是我把 TTL 定为常数而不是指数退避的**已知代价**，写在册上待裁（要更保守就把 TTL 做成随连续拒绝次数增长，那需要新增状态位，不在本票面）。
另两条刻意不做的事：`unavailable` **不含**冷却（含进去会让 `pick_by_key`——judge 等显式指定——在冷却期直接 KeyError，超出本票范围），代价是管理台会显示"配额健康且可用"而自动路由实际跳过它 ⇒ 我用快照新增的 `rejected_remaining_s`（`llm_registry.py` 的 snapshot 面）把冷却剩余时间显式暴露出来，运维看得见；但**该字段目前没有消费者**（管理台前端未读），这条列进未做。

**DB-16（B-05 category 静默清零）—— 回落可见化**

Chroma 语义本身未重测（§12.3 九腿已 A 级坐实：库内 10,266 条无 `category` 键，`$eq`／`$ne` 对缺失键都排除该行）。本轮的"改后"读数在 `tests/test_retrieval_category_fallback.py`（6 collected），替身 `_FakeVectorstore` 按**实测到的**语义写（带 `category` 取零、无过滤取全量），断言的是调用序列 `filters == [{"category": "民法"}, None]`——即"先带过滤、零命中、再回落一次"，并另配控制腿 `category=None` 时**只查一次**（防回落变成无条件重查）。日志腿钉"每个 category 值各记一次"（两值 ⇒ 2 条，不刷屏也不静默）。`grounded_top_score` 同一形状补了一腿：改前带 category 直接 0.0 ⇒ 该题**永不进待审队列**且无人知晓。
〔本小节的两个代价我最初没写：回落等于**同一句再嵌入一次**（`rag_chain.py:93-97` 成功即扣配额 ⇒ 双扣），且带 category 的结果进缓存后第二次同问句连 `vector_top` 都不进（既不再回落也不再留痕）。两条都在 §13.10 ⑥⑦ 摊开，其中"痕"那一半已当场补码。〕

### 13.3 被我改判的在册用例（逐条，原句先抄再改）

**这一节是本轮最贵的部分**：四票里有三票要动"已经把缺陷钉成预期"的用例。按在册纪律，先把原断言抄出来，再写改成了什么。

1. `tests/test_agent_resume.py::test_resume_when_steps_budget_exhausted_still_conflicts` → **改名并反判**为 `test_resume_at_exact_step_cap_succeeds_and_still_rejects_stale_version`。
   原 docstring 逐字：**「Gate 4 失败路径：steps 预算耗尽时第二次 resume 必须仍 409（budget 防护不被多轮会话绕过）」**，其"回归背景"段自己写着 `settings.agent_max_steps` 默认 8 时第二轮澄清必 409、**修复方式为提升默认预算至 16**。
   这两句合起来就是 B-47 的物证：这只用例把"恢复必死锁"当**预期结果**钉住，而历史上的"修法"是把数字抬大。
   改后：`steps == cap` 的 resume **返回 200**（恢复边不计步），同时把真正该 fail-closed 的那一轴留在原地——`expected_version` 陈旧仍 409。步数样本从 `steps=8/max=8` 改成 `steps=3/max=3`（与默认预算解耦，别再跟着 `AGENT_MAX_STEPS` 漂），并在用例里点名 DB-15。
   同文件另一只 `test_resume_law_as_of_...` 系列里 `steps == 4` 的期望随计费式改为 `steps == 3`。
2. `tests/test_llm_failover.py::test_permanent_400_switches_and_marks_depleted` → 改名 `test_permanent_400_switches_and_cools_down`，断言从 `reg.marked == [("k1", "model_failure")]` 改为 `reg.rejected == [("k1", "model_failure")]` **且** `reg.marked == []`。
   名字里的 `marks_depleted` 现在会撒谎，所以改名而不是保留旧名改内文。
   `test_permanent_statuses_all_mark_before_switching[400/401/403/404]` 同一改法（4 只参数格）。
   `test_plain_400_without_schema_marker_is_permanent` 保留原名（它钉的是 F3 反向守卫"未知 400 不是 schema 拒绝"，那句仍成立），只把通道断言补上。
   **未动**：`test_permanent_status_is_not_transient_in_both_sdk_shapes[400/401/403/404/422]` 与 `test_transient_status_is_transient_in_both_sdk_shapes[...]`——分类口径那两只逐字保留（报告 §12.4 那两个指针是 **HEAD 轴**的：`:167-170` 与 `:160-164`；本轮给同一文件加了腿，工作树轴上它们已经漂到 `:174-177` 与 `:167-170`——**行号漂移这台机器我在 §11 里批评过别人，本轮又落在我自己头上一次**，所以源码注释与本报告正文从今往后一律按**用例名**引），这正是 DB-5/DB-17 里"不重开分类"的兑现。
   新增 1 只控制腿 `test_permanent_without_status_code_stays_on_quota_channel`：**无状态码**的永久失败仍走 `mark_depleted`。少它则"把路由写成凡 permanent 都冷却"也能全绿。
3. `tests/test_llm_admin.py` 与 `tests/test_llm_failover.py` 的 entry 替身由手抄 `SimpleNamespace` 改为**真 `ModelEntry`**（见 13.4，属仪器修复，不改被钉语义）。

### 13.4 仪器侧发现：本轮 6 只红全是"尺子自己的问题"，而且有两种不同的坏法

改后第一趟 `6 failed`（全在 `tests/test_llm_admin.py`）加上中途 10 只红，都不是产品逻辑错，而是**替身追不上真类**。
六只红其实是**两种**漏法（`full-post.log` 里逐条数出来的）：5 只缺 `rejected_now`（`pick` 的过滤式读它，报在 `llm_registry.py:600`）、1 只缺 `rejected_until`（管理台快照那条用例读的是到期时刻本身，报在 `llm_registry.py:756`）⇒ 我新增的那一维在真类里其实是**两个面**（时刻 + 派生布尔），手抄桩一次漏了两样。

* **坏法一：手抄字段面的替身。** 本仓有两只 independently 写的"最小 entry 面"SimpleNamespace（`test_llm_failover.py::_entry`、`test_llm_admin.py::_entry`），把 `quota_left`/`depleted`/`below_threshold`/`unavailable` 这些**真类里是派生属性**的东西当字段抄了一份。`pick` 新增一维 ⇒ 两只桩同时过期。已都改为构造真 `ModelEntry`，"不可用"改由 `runtime_used` 反推。副产品：这类桩原本还**自证**自己的派生位（抄成 `unavailable=False` 就永远 False），现在这些位由真类算。
  `test_llm_admin.py::_entry` 的旧 docstring 写着「tests/test_tiering.py 同模式」——**这句对 entry 是错的**（`test_tiering.py` 的 SimpleNamespace 是假 LLM 消息，不是 entry），全仓只有这两处 entry 桩。
* **坏法二：补丁漏了新方法，于是调用打在真对象上。** `ScriptedRegistry` 只实现了 `mark_depleted`，`install_registry` 也只 `monkeypatch` 了 `pick` 与 `mark_depleted`。生产改调 `mark_rejected` 后，那次调用落到**未被打补丁的全局真 registry**上，因为里面没有 `k1` 而**静默无事**；断言于是读到 `marked == []`，看起来像"产品没标记"，实际上是"标记被我看不见的通道吞掉了"。修法是替身两条通道都记 + 补丁两个方法都打，并把这条归因写进注释。
  ⇒ 推广一句给后续票：**给一个对象加"第二条出口"时，必须检查所有脚本化替身是否只封了第一条**，否则新分支的测试是假绿而旧分支的测试是真红。

顺带一只我自己的错要摊开：`%TEMP%\fazhi-audit2-20261009\backend\backend\tests\test_audit2_source_key_shapes.py::test_audit2_norm_source_prefix_only` 在**两棵树都红**。红的原因是那只腿的期望写错了——它断言 `_norm_source("中华人民共和国 民法典") == "中华人民共和国 民法典"`，而真函数剥前缀后不 `strip`，实际返回 `" 民法典"`。报告 B-49 行记的是**对的事实**（`_norm_source` 剥前缀后不 strip，只有 `_source_key` 末尾 `.strip()` 兜住），所以这次是探针脚本自己漂移，不是新代码回归；本轮未修那根探针（它不在册、也不入库），改判后的形状已由 `tests/test_law_name_normalization.py` 的 10 格样本接管。

### 13.5 门禁复跑读数（四条 CI 腿 + 哪些不是本轮造成的）

| CI 腿（`.github/workflows/ci.yml` 的 backend job） | 本轮读数 | 归因 |
|---|---|---|
| `ruff check .` | `All checks passed!` | 我新写的 `tests/test_agent_budget_terminal_edges.py` 起初 3 条（I001 导入排序、F401 未用的 `AgentFinalizationConflict`、UP020 `io.open`），全部 `--fix` 修掉；fix 后 10 collected 仍全绿。除我自己的新文件外未跑过 `--fix` |
| `ruff format --check .` | 本地 `3 files would be reformatted` → 我把本轮新增两只测试文件格式化后**仍剩 1 只**：`backend/schemas.py` | **不是本轮改动面**：`git status --porcelain -- backend/schemas.py` 空（该文件未被修改），盘上是 265 CRLF + 11 bare LF 的**混合换行**，属这台 Windows 的 checkout 形状（`.gitattributes` 是 `* text=auto eol=lf`、`core.autocrlf=true`）。CI 检出的树是 LF ⇒ 这条腿"本地数≠CI 数"，我没有为了让本地绿而去重排一个不属于本票的文件 |
| `mypy .` | `Found 2 errors in 1 file (checked 74 source files)`，都是 `"Row" expects 1 type argument, but 2 given`（`main.py:2894`／`main.py:3105`） | **改前即红，且与本票无关**，两条证据：① 把 HEAD 的那份 `main.py` 取到临时目录单独跑 mypy（`git show HEAD:backend/main.py`，3150 行、不含本轮 26/4 改动），同样 2 错，落在 `:2872`／`:3083`（差 22 行正是本轮在 `main.py` 上方加的行数）；② 六行独立探针（`%TEMP%\audit2-impl-20261009\row_probe.py`，只有 `from sqlalchemy.engine import Row` + 一个 `Row[Fake, str]` 注解，零项目代码）复现同一条 `type-arg` ⇒ 病因是本机 `SQLAlchemy 2.0.51` 的 `Row` 是单参数泛型（`Generic[~_TP]`）而本机 mypy 2.3.0 不吃两参数写法。那两行 `Row[...]` 注解由**别的会话的 `902e2d1`** 引入。`requirements-dev.txt:6` 是 `mypy>=1.10`（无上界）⇒ 我不能替 CI 断言它同红；按在册"裁判选更强的那个"，这条交 CI 定，但**任何"CI 全绿"的说法要先看这条腿** |
| `pytest --cov=. --cov-fail-under=70 -q` | 我以同一命令族的 `-m "not slow"` 形状跑的：**`1906 passed, 2 skipped, 18 deselected`，0 failed**（317.73s）；覆盖率本轮**未采**（`--cov` 会另起 coverage 轨，与基线那趟不同形，为保持两趟可比我只加 `--cov` 于下一轮） | 未复跑 CI 的 `--cov` 形状 ⇒ 覆盖率数字本轮不报，别把 85.25%（09-30 在册）当本轮读数 |

### 13.6 本轮**没做**的事，以及没做的理由（不拿"未做"当"已完备"）

1. **DB-16 的第②处（把 `category` 从 schema 摘除）我没做**——这是本轮**两处**偏离之一（另一处是 B-47"做"列里的"409 文案按成因拆三条"只做到判据层，见 §13.10 ⑩），三条新量到的事实逼出来的：
   * 我那句"字段还在 schema 里，模型仍可能自己想到它"**成立**：planner 的 `response_format` 正是 `TypeAdapter(RetrieveLawsInput | …).json_schema()` 生成（`agent/runtime.py:396-416`，其中 `args_union.json_schema()` 在 396-399、把 `args` 换成 anyOf 引用在 405-416），所以 schema 是最强的邀请面，摘它才叫摘根。
   * 但摘掉之后**失败形状会变**：`RetrieveLawsInput` 是 `extra="forbid"`，而工具入口是 `tools/gateway.py:218` 的 `policy.input_model.model_validate(raw_args)`，模型若仍交 `category` 就落到 `agent/planner.py:115` 的 `PlannerParseError`——代价从"证据静默为零"变成"一次回喂重试、最坏走 technical fallback"（`PLANNER_PARSE_ERROR` 确在 `routing_metrics.py:15` 白名单内，这句是 grep 原文不是推断）。
   * 更要紧的是：生产面里**只有**这条 Agent 工具道会给 `retrieve(..., category=…)` 传非空值（`tools/legal_retrieval.py:22`；`main.py:1672` 是 `retrieve(q, k=8)` 不带 category）。⇒ 摘了字段，本轮刚加的回落③在结构上就变成**没人可达的死代码**——这正是我这几轮报告 B-1x 类缺陷时用的判据，不能对自己豁免。
   ⇒ 结论：②的完整形状比册子上写的"一行"大（要摘就 schema + 工具传参 + 检索侧参数一起摘）。我把它作为 **DB-19** 交回你裁，不顺手做半刀。
2. **DB-1（B-01）与 DB-5 的那半（B-06 归因）算已执行**，因为它们分别就是 DB-15、DB-17 的实现体：终稿边不计步 + `except BudgetExceeded` 显式映射到白名单内的 `AGENT_BUDGET_EXCEEDED`（DB-1 推荐的"直接修 + 同批补用例"两半都在 `tests/test_agent_budget_terminal_edges.py`）；4xx 不再记成积分用完（DB-5 推荐的"窄豁免 + `mark_depleted` 落结构化日志"两半都在 `mark_rejected`/`mark_depleted`）。**`is_transient_error` 与 `TRANSIENT_STATUS` 一字未动**，`test_permanent_status_is_not_transient_in_both_sdk_shapes` 那类"400 归永久"的分类钉也原样保留（按名字引；它 HEAD 轴是 `:167-170`，本轮工作树轴是 `:174-177`）。
3. **`dept_guard` 那份前缀剥离没并进来** → 见 DB-20。
4. CI/远端与其余门禁腿未跑，理由逐条：`pip-audit`（在册已知 rc=1，且 CI 只扫 `requirements.txt` ⇒ dev 轴 5 条永不出现在 CI 读数，本轮未动依赖）；`npm run build`（前端 5 只改动文件不属本票，见 13.1 归属表）；`dispatch-output` 守卫腿（未动该目录）；**覆盖率 `--cov` 形状未采**（见 13.5 那行）；**未 push ⇒ 无远端 CI 证据**，本轮所有绿都是本机 Windows 工作树 + 副本树读数。
5. 边界复量（**收尾时再取一次，窗口比开头更宽**）：HEAD 仍是完整的 `0b543960c7172ce1ffea57616952e4d5525190c4`、本轮无提交；真实库用两根轴读——`find chroma_db -type f -newermt "-6 hours"` = **0** 文件，且整个 `chroma_db/` 里**最新的一批**文件是 `2026-09-22 13:34`、同一时刻共 **4** 只（`9f605bf2…/` 下 `data_level0.bin`、`length.bin`、`header.bin`、`link_lists.bin`），再往前是 `chroma.sqlite3` 的 `2026-09-21 02:06` ⇒ 都早于本轮 17 天。〔我第一版把这句写成"最新的一只"，是因为用了 `sort -rn | head -2`——正是 §9 登记过的"head 截断当全集"那台机器，复核轮 A 路当场抓到〕；`backend/app.db` mtime `2026-09-19 00:28`、`backend/data/app.db` mtime `2026-09-23 14:51` 都没动。测试套件仍由 `tests/conftest.py` 无条件把 `DATABASE_URL`／`QUOTA_DB`／`CHROMA_DIR` 指到 `%TEMP%`——"0 文件被改"是这两根轴一起给的，不是只看目录时间戳。
   一条要披露的副作用：本轮两支独立探针在 `import` 期打出 `Failed to send telemetry event ClientStartEvent / ClientCreateCollectionEvent`（chromadb 的 posthog 埋点因签名不匹配而**发送失败**）。这是"有外联意图、未成功"，不是"已确认零外联"；目录级 0 文件只证真实索引未被写。

### 13.7 新增待裁（每条一词可答，推荐已给）

| 编号 | 待决 | 我的推荐 | 若不做 |
|---|---|---|---|
| DB-19 | `category` 的 schema 面（原 DB-16 的第②处）到底摘不摘？三个形状：**甲** 维持现状（提示词已关 + 回落可见 + 字段留着）；**乙** 整刀摘干净（schema + `tools/legal_retrieval.py` 传参 + `retrieval.py` 的 `category` 形参一起退，③随之删掉）；**丙** 等写侧给 10,266 条补上 `category` 后再让它成为真过滤器 | **丙，且丙之前保持甲**（乙会把一个"已经会自愈并留痕"的路径换成"要重试一次的硬失败"，而现在没有任何数据支撑这个过滤维度；写侧补齐后乙才是错的答案，甲反而是对的） | 挂着一个"看起来像功能"的可选参数；模型偶尔仍可能试它（现在最坏只是多一次无过滤取数 + 一条 warning） |
| DB-20 | `agent/dept_guard.py:42 与 :45-52` 是**弱一档那一族的第二份**前缀剥离（`_CN_PREFIX` + 只剥前缀、不剥括注；另一份是 `retrieval._norm_source:438-446`。本轮真源合一覆盖的是**强一档那一族的四份**，见 13.1；"第五份"那个序号是我先写错的，复核轮 A 路指出后改成本说法）。折进 `domain_rules.norm_law_name` 会**变宽**它的行为（尾部括注开始被剥），而它服务的是 R1b 终稿串台判域 | **随 DB-3"引用真源收口"那一票一起做**，并且必须同批补一条"判域不变"的对照用例（同一批法名，改前改后 `_norm_law_name` 的域判定逐字相同）；本轮不动 | 真源仍是两份（强一档 + 弱一档），串台判定与引用校验对同一个名字给出不同结论的可能性留在册外 |

〔**§7 就地更新**：DB-15／DB-16(①③)／DB-17／DB-18 已于 2026-10-09 实施轮在本工作区落地并复量，读数见 §13.2 与 §13.5；DB-16 的第②处**未执行**，改由 DB-19 承担；DB-1 与 DB-5 的"归因半"分别随 DB-15、DB-17 关闭。§7 表格"我的推荐"一列的文字**保持原样未回写**——那是你当时的决策语境，本轮的结果只以补记形式追加。〕

### 13.8 本节的复算命令（都在本机跑过，不是设想）

```bash
# 1) 改动清单与归属（13.1 那张表的来源）
git -C /c/Users/33393/Desktop/ai-legal-helper diff --numstat
git -C /c/Users/33393/Desktop/ai-legal-helper ls-files --others --exclude-standard backend/tests

# 2) 全量门禁（13.5 那行；改前基线同一命令，日志 pytest_baseline_before.txt）
cd /c/Users/33393/Desktop/ai-legal-helper/backend
venv/Scripts/python.exe -m pytest -q -m "not slow" -p no:cacheprovider --no-header -rs

# 3) 六格归一表（13.2 第一张表）
venv/Scripts/python.exe "$TEMP/audit2-impl-20261009/ruler_norm.py"

# 4) L1–L4 两树对照（13.2 第二张表）——同一支探针脚本，两棵树各跑一次
cd "$TEMP/fazhi-audit2-20261009/backend/backend"      # 改前树
PYTHONPATH="$PWD" /c/Users/33393/Desktop/ai-legal-helper/backend/venv/Scripts/python.exe \
  -m pytest -q -p no:cacheprovider -o addopts="" tests/test_audit2_b01_finalize_budget_boundary.py
cd "$TEMP/fazhi-audit2-20261009/patched/backend/backend"  # 改后树（本轮 12 只源文件 cp 进来 + 清 __pycache__）
# 读数：改前 `4 passed, 2 failed`（其中失败的是 §12.5 的半角表 + 那只想写错的 norm_source 腿）
#      改后 `3 passed, 3 failed`（L2/L3 翻红 = 缺陷消失；半角表翻绿）

# 5) 通道网格两树对照（13.2 第三张表）
PYTHONPATH="$PWD" venv/Scripts/python.exe "$TEMP/audit2-impl-20261009/b48_grid2.py"
PYTHONPATH="$PWD" venv/Scripts/python.exe "$TEMP/audit2-impl-20261009/b48_channel_grid.py"

# 6) mypy 那两条红的"改前即红"证明（13.5 第三行）
git -C /c/Users/33393/Desktop/ai-legal-helper show HEAD:backend/main.py > "$TEMP/audit2-impl-20261009/head/main.py"
cd /c/Users/33393/Desktop/ai-legal-helper/backend
venv/Scripts/python.exe -m mypy "$TEMP/audit2-impl-20261009/head/main.py"   # 同样 2 错，:2872 与 :3083
venv/Scripts/python.exe -m mypy "$TEMP/audit2-impl-20261009/row_probe.py"   # 六行、零项目代码，同一条 type-arg
venv/Scripts/python.exe -m mypy .                                          # 本轮工作树：2 errors (checked 74 files)
```

**本轮不新增 B-xx finding**（49 条那本册子的条数未变）；新增的是两条待裁（DB-19、DB-20）与一条"§7 已执行"的就地标注。

### 13.9 独立复核轮（A 路：只读复算）与就地改正的九处

按在册做法（第一轮起 Owner 就要求"再派一个独立 agent 审查你的审查"），本轮补派了**只读**复核者 A 路，任务只有一句：**复算 §13 里每一条可核事实**（行号、`+/−` 数字、原句、日志读数、mtime），不许执行项目代码、不许读密钥值、不许写文件。它交付后我**逐条自己复跑过**才落笔（下表"我复跑"列就是我自己的命令与结果，不是转述它）。

| # | 我原来写的 | A 路指出 | 我复跑得到的现量 | 处置 |
|---|---|---|---|---|
| 1 | `test_agent_resume.py` "CRLF 保持原样 **919** 只" | 真值 923 | 字节级 `read_bytes().count(CRLF)` = **923**，裸 LF = 0 | 已改成 923 并写明量法 |
| 2 | 第一趟 6 只是"**同一条** `AttributeError`" | 是**两条** | `grep -E "^E   AttributeError" full-post.log` ⇒ 5× `'...has no attribute 'rejected_now'`（报在 `llm_registry.py:600`）+ 1× `...rejected_until`（报在 `llm_registry.py:756`） | 已改写，并补一句"我加的那一维在真类里是两个面（时刻 + 派生布尔），手抄桩一次漏两样" |
| 3 | `test_llm_failover.py:167-170` 指"400 归永久" | 工作树轴上 167-170 现在是 **transient** 那只 | `grep -n` 现量：工作树 permanent 在 **:174-177**、transient 在 **:167-170**；HEAD 轴 permanent 确在 **:167-170** | 报告正文与**源码注释**（`llm_errors.py:104`、`llm_registry.py:35`）一律改成按**用例名**引，并就地写明两根轴——这台"行号漂移"机器我在 §11 批评过别人，本轮落在我头上 |
| 4 | `smoke_citation_full` 是"**第五份**"、`dept_guard` 也是"第五份" | 序号自相矛盾；且 `retrieval.py` 新 docstring 写"三份" | 强一档那一族 = **四份**（`_source_key`、`parse_article_query` 内联、`writer._canonical_law_name`、`smoke_citation_full.norm_law_name`）；弱一档那一族 = **两份**（`retrieval._norm_source:438-446`、`agent/dept_guard.py:42/:45-52`） | 三处措辞全部改成分族计数；`retrieval._source_key` 的 docstring 从"三份"补齐为"四份" |
| 5 | `chroma_db/` 里"最新的一只文件" | 同一时刻有 4 只 | `find chroma_db -type f -printf` 排序：`2026-09-22 13:34` 共 **4** 只（`data_level0.bin`/`length.bin`/`header.bin`/`link_lists.bin`），下一条是 `chroma.sqlite3` 的 `2026-09-21 02:06` | 已改为"最新的一批 4 只"，并写明我的错因是 `sort -rn \| head -2` ——正是 §9 登记过的"**head 截断当全集**"那台机器 |
| 6 | `agent/runtime.py:390-416` | 390 是 import 行 | `TypeAdapter(...).json_schema()` 在 **396-399**，anyOf 接线在 **405-416** | 指针改窄并分点 |
| 7 | "改前改后**同两只** skip" | 基线日志里没有 SKIPPED 段 | `grep -c SKIPPED pytest_baseline_before.txt` = **0**；终趟 `-rs` 的两只名字可核 | 已就地降级为**推断**，附间接证据（本轮未动那两只文件 + skip 计数同为 2） |
| 8 | "中途 10 只红" | 无在册证据 | 那次是前台跑的，**没落盘**（`full-post.log` 只有第一趟的 6 只） | 保留这句但标为"本会话读数，未落盘"；等价在册证据 = 修复后 `test_llm_failover.py` 单跑 42 passed |
| 9 | 13.1 表里 `llm_errors.py` 21／0、`llm_registry.py` 55／0、`retrieval.py` 78／21 | — | 本轮为消除 #3/#4 又改了**三处注释/docstring**，`git diff --numstat` 现量 **22／0、56／0、79／21** | 表已更新（见 13.1），并在此声明那三处改动**只动注释与 docstring、未动任何行为** |

**A 路"对上"的部分**（不逐条复述，只点名它核过且与我一致的）：13.1 十五行 `+/−` 全中且 backend 无表外被改文件、三趟 pytest 读数逐字对（含 `289 warnings` 三趟同）、`1906 − 1860 = 46` 与新增 45+1 的闭合式成立、两条被改判用例的原句逐字对（HEAD 的 docstring 与旧断言）、两棵副本树之差恰等于本轮补丁、`schemas.py` 未被修改且确为 265 CRLF + 11 裸 LF 的混合换行、`requirements-dev.txt:6` 的 mypy 无上界、`git log -1 -S "Row[Conversation, str]"` 指向 `902e2d1`、`dept_guard` 未并进真源。
**A 路"核不了"的部分**（它的只读约束挡住了，我这边有证据）：`--collect-only` 现量（13.0/13.2 那些数字是我本机跑的）、六格归一表与 L1–L4 与 b48 网格（§13.8 有命令与日志路径）、ruff/mypy/pytest 复跑（§13.5）。

**改正后复跑**（为兑现"改完用同一批尺子复量"，也为了不让"1906"这句只描述改注释之前的树）：
`ruff check llm_errors.py llm_registry.py retrieval.py` = All checks passed；`ruff format --check` 同三文件 = already formatted（行宽上限 120，最长 118）；`mypy .` 仍 `Found 2 errors`（同 `main.py:2894`／`:3105`，未新增）；受影响面单跑 `tests/test_llm_failover.py tests/test_llm_reject_channel.py tests/test_llm_admin.py tests/test_retrieval_category_fallback.py tests/test_law_name_normalization.py tests/test_agent_budget_terminal_edges.py tests/test_log_field_whitelist.py` = **101 passed**（闭合：42+22+12+6+7+10+2 = 101）；全量终趟（`full-post3.log`）= **`1906 passed, 2 skipped, 18 deselected, 289 warnings in 324.72s`，0 failed**，与改注释前的那一趟逐字同形（只耗时不同），两条 skip 的名字也仍是 §13.0 点名的两只采集口。

**这一节我自己要留的一句话**：本轮 6 只红、10 只红、以及 A 路抓到的 9 处里，有 **7 处是量法/抄写/序号问题**（923 抄成 919、head 截断当全集、行号按旧轴引、分族序号自相矛盾），只有 2 处是判断问题。⇒ 下一轮开工前该做的不是"更小心"，而是把"写进正文的每个数都来自一条刚跑过的命令"做成机械动作（§13.8 那批命令应升级为脚本随票入库，见 §12 开头"脚本落点"那条在册限制）。

### 13.10 独立复核轮 B 路（专挑论点与连带面）：接受 9 条、驳回 1 条半、修正 2 处原话

B 路的任务是**挑战论点**（不复算行号，那是 A 路）。它交回 11 条，我逐条回源码自证——**接受的 9 条里有 1 条要求现在就改代码**（不然 DB-17 等于只做了一半），另有 2 条把我前面写过的话钉回去就地修正。下面每条都给"它说的 / 我复核到的 / 处置"。

**① 接受并当场补码（本轮唯一的实现级漏洞）**：`_safe_pick` 在 `QuotaExceeded` 时直接 `registry.get()` 回落默认模型，而那条路**绕过了 `pick` 的冷却过滤**；`is_unavailable()` 又刻意不看冷却 ⇒ 整池冷却时每个请求仍会再打一次刚被打回的模型，且 `degraded` 读成 False。我复核：`main.py:1079-1081`（改前两行就是 `return dk, registry.get(), registry.is_unavailable(dk)`）。
补了什么：`llm_registry.is_rejected(key)`（只读拒绝轴，不碰配额语义）+ `_safe_pick` 的降级判定改成 `is_unavailable(dk) or is_rejected(dk)` + **两只新用例**（`test_safe_pick_marks_a_cooling_default_as_degraded` 用真 `ModelEntry`、零 patch 判定逻辑，另配 `test_reject_predicate_is_the_only_thing_that_moves_the_flag` 把冷却位摘掉证明上一步的红来自它）。这条不补，B-48 的"别打它"就只是"少选它"。
**连带读数要更正**：13.2 那句"N 只之后该 payload 会命中 `_safe_pick` 回落……不 503，走带注记的降级答复"——改前那半句是真的（回落照样发生），但"带注记"当时**不成立**（degraded 读 False）。现在成立。

**② 接受（论点级，不改码）**：把 401/403/404 和 400 放同一个 300 秒 TTL 是粗糙的——`llm_errors.py:102-103` 我自己写了这一族包含"模型名写错、key 失效、端点点错"，而那些是**配置故障**，300 秒后必然复现 ⇒ 每个请求白付一次死调用；真正会自愈的只有内容驱动的 400（超长上下文、审核拦截）。更难受的是：DB-5 当年给 B-06 的口径是"**豁免面只按错误文本**（`context_length`/`data_inspection`）窄匹配"，而我这轮按**状态码族**实现 ⇒ 两册本来就打架，我选了 DB-17 的写法却没摊开。列 **DB-22**（一词可答：要不要把 401/403/404 改成"直到人工校准"、只让 400/422 走 TTL；或按错误文本窄匹配回到 DB-5 口径）。**推荐后者按状态码分两档**（401/403/404 = 配置类，冷却拉长到 3600s 并在快照里单列；400/422 = 形状类，保持 300s），因为它不需要读上游的自由文本、判据仍是可读事实，而文本窄匹配会被上游改文案击穿。

**③ 接受（措辞）**：我在 13.2 写的是"可干净终止"，但 13.0/§7 别处仍把 DB-15 说成"run 可恢复"。准确说法：**resume 进得来**（不再 409 死锁），但 state 仍停在 `steps == cap`，下一条会计步的边（`controller.py:761-763` 的 `PLANNING→EXECUTING`，紧接 `except BudgetExceeded` 就落 stop）照样抛 ⇒ 落 `_persist_budget_stop`（`decision="stop"`）+ 快车道兜底。B-47 那半句"16/47 只永远恢复不了"从"永远卡住"变成"能终止且留下记录"，**不是**"多轮跑完了"；"多轮跑不完"的算术在 `settings.py` 那侧一字未改。旁注要写准：`settings.py:89` 那句"max_steps 默认 16"确实与 `:96` 的 `default=20` 不同步，但它被 `:92-93` 的"2026-09-12 用户批准 16→20（8→16 先例的同类上调）"自我更正了——所以这段注释同时是 **B-47"靠抬 cap 续命"的在册物证**（`8→16→20` 三步全写在里面），本票未动它。

**④ 接受并就地收窄原话（DB-18 的射程我说过头了）**：我说"四份收成一份/唯一真源"，实际只并了**生产读侧四份**。复核到还有：写侧 `scripts/import_docs.py:36` + `:53-54`（它决定库存 `source` 长什么样，是最要命的一份）、`scripts/capture_eval.py:56`、`scripts/gen_qwen_cases.py:61`；另有"弱一档那一族"两份（`retrieval._norm_source:438-446`、`agent/dept_guard.py:42` + `:45-52`），`scripts/gate5_judge.py:73-74` 还另立了一张法名别名表。⇒ `domain_rules.py` 的头注已改成"生产读侧四份合一 + 未并清单点名"，并在 13.2 把"唯一真源"限定为**读侧**。写侧那份要不要并 = **DB-21**（并进真源会让"文件名带半角括注"的新法在导入时被剥掉括注，改变库存 key；我推荐**并，但必须同批改 `import_docs` 的测试与一次 dry-run 比对**，因为写读两侧口径不一致本身就是 B-49 的温床）。

**⑤ 接受（方向要点名）**：归一放宽后，`article_in_kb`/`_source_key` 两侧同过真源且**不查时效**（`retrieval.py:509-547`）⇒ 任何尾部半角括注（哪怕"劳动合同法(2024修正)"这种库里不存在的版本）都判"在库"。方向是**漏检（false accept）**，不是误拦。现量风险面：`data/laws_clean/` 共 **99** 只文件，尾部带括注的 **1** 只（`中华人民共和国宪法（1982年）_19821204.txt`，全角），半角 **0** 只 ⇒ 今天没有可被并的真对；而 `tests/test_law_name_normalization.py:46-48` 把"（一）（二）→（一）"钉成了**预期**——那正是"两部不同文件被并成一个"的形状，所以这条判据钉住的是**边界**，不是安全性证明。要不要给归一加"只剥**四位年份/修正字样**形状的括注"（把 `(合同编)` 这类排除掉）列进 DB-21 同一票。

**⑥⑦ 接受（回落的两个代价，我原来只讲了收益）**：
* 留痕被自己消解的部分：`hybrid` 结果缓存的 key **含 `category`**（`retrieval.py:904-913`）⇒ 同一条带 category 的问句第二次命中缓存，连 `vector_top` 都不进，日志与回落都不再发生；`_CATEGORY_MISS_SEEN` 此前也不随 `invalidate()` 清（**这条我已补**：`invalidate()` 现在清 seen 集 + 一只新用例 `test_invalidate_resets_the_miss_log_suppression` 两半都钉——先证抑制器确实在抑制，再证清完后能重新出声）；日志里没有 run/request 维度（`observability.py:172` 的 `req` 恒 `-`），所以"哪个请求回落过"目前只能靠时间对齐。
* 成本：回落 = **同一句再嵌入一次**，而 `rag_chain.py:93-97` 是成功即 `_deduct` ⇒ 命中回落路径时 embedding 配额**双扣**；`hybrid_retrieve` 里 `vector_top` 与 `bm25_top` 各自可能回落 ⇒ 单请求的 Chroma 查询最多翻倍。抑制器只压日志不压开销。
* 判据面：`if not out and category` 分不清"**库里没这个键**"与"**该类目真的零条**"。今天靠 §12.3 的实测（10,266 条全无 `category`）它是安全的；**写侧一旦补上 key，这条回落就会静默废掉真过滤器**——这正是 B 路对 DB-19 的第四形状指摘。⇒ **DB-19 的措辞我已改**：原推荐里那句"写侧补齐后甲反而是对的"是错的，正确说法是**丙落地当天③必须删**（或改成"先探测库内是否存在该键再决定回落"）。

**⑧⑨ 接受（在册未做，别当已交付）**：`rejected_remaining_s` 只进 `registry.status()` 的 API 读数，前端**零消费**（全仓只有 `QuotaBanner.tsx` 与 `lib/types.ts` 两处类型/配额面引用，都不读这个字段）⇒ 13.2 写的"运维看得见"只在 API 层成立，已就地加限定。

**⑩ 接受（第二处偏离，且我漏报了）**：§13.6 开头我写"这是本轮**唯一一处**偏离我自己推荐的地方"——不成立。B-47 行的"做"列原文是"与 B-01 并一票，给「终稿边 + 恢复边」这两类 1 步边预留步数或不计步，**并把 409 文案按成因拆成三条**"。我只做到**判据层**：`ResumeRunConflict` 现在带 7 个 `reason_code`、`main.py` 落 `agent_resume_conflict` 结构化日志，但用户可见文案仍是同一句 `RESUME_CONFLICT_DETAIL`（定义在 `agent/controller.py:179`，唯一 raise 点在 `main.py:1907`）。这处偏离在代码里是**明写的**——本轮给 `ResumeRunConflict` 写的 docstring（`agent/controller.py:244-247`）里就有"**对外文案仍只有一句**（不把内部状态机细节泄漏给客户端），成因进结构化日志字段 `agent_resume_reason`"，所以不是暗改，只是没做完。为什么不顺手做完：那三句话是**给用户看的产品措辞**，我不替产品定文案。列 **DB-23**，推荐映射（你点头我就接上，只改 `agent/controller.py` 里那一处成因→文案映射与 `main.py:1907` 那一个 raise 点）：`state_stale`／`cas_conflict`／`issue_missing` → 维持现句；`step_budget` → "本次任务已达步数上限，无法继续，请重新提问"；`answer_invalid`／`pending_anchor_mismatch`／`state_unreadable` → "恢复所需的信息对不上，请重新提问"。§13.6 那句"唯一一处"已就地改成"两处之一"。

**⑪ 部分驳回**：B 说我把恢复边的上界写成 `max_clarifications` 是错的，因为范围选择两支"不消耗澄清预算"（`controller.py:288-291`、`:907` 的注释明写"不调用 register_clarification"）。我复核后：**它指的那句我的原文没有这么写**——13.2 三问自证①里我把 `:926` 归成"普通 `transition` ⇒ 照旧计 1 步"、把 `:1112-1113` 归成"澄清预算"，两支各给各的界；`pending_scope_issue_ids` 非空即不重入（`:914`）也是它没提的一环。但它逼我把话说得更死：**任意一轮 `PLANNING→…→WAITING_USER→PLANNING` 往返至少花 1 步**（进 `WAITING_USER` 不在 `FREE_STEP_EDGES` 里），所以封顶者是 `steps`，澄清额度只是事实澄清支的**额外**上界。这句已按此改写。

**驳回的那半**：B 说 `mark_rejected` 每次都落一条 WARNING 是"洪水"、与 retrieval 的"每进程一次"策略相反且无依据。我不同意把它们对齐：**模型被拒是一次"事件"**（有上游时间戳、要能数出频率），**检索零命中是一种"状态"**（同一条问句反复问只会淹日志）。而且拒绝的频率已被 300 秒冷却天然限流——同一模型在冷却期内不会再被 `pick` 选中，也就不会再被拒。真发生洪水时该做的是限流告警，不是把事件吃掉。


**B 路补码后的复跑与边界（全部现量，2026-10-09 深夜）**
* 新增代码面：`llm_registry.is_rejected`（+12 行）、`main.py:_safe_pick` 的降级判定（+4 行含注释）、`retrieval.invalidate()` 清 seen 集（+4 行）、`domain_rules` 头注改写（+6 行）；新增用例 3 只（2 只 `_safe_pick` + 1 只 `invalidate`），并把 `tests/test_retrieval_category_fallback.py` 过了一遍 `ruff format`（`assert` 那行超 120 列）。
* 受影响面单跑：`tests/test_llm_reject_channel.py`（24 collected）+ `tests/test_retrieval_category_fallback.py`（7）= **31 passed**；`tests/test_llm_failover.py` 42、`tests/test_llm_admin.py` 12 在补码前后都绿。
* 全量终趟（`full-final.log`，命令同 §13.0）：**`1909 passed, 2 skipped, 18 deselected, 289 warnings in 326.20s`，0 failed**。闭合核对：`1909 − 1860 = 49` = 新四只文件 45 ＋ failover 控制腿 1 ＋ B 路补的 3 腿 = **49**，两轴相等；两条 skip 仍是 §13.0 点名的那两只采集口。
* `ruff check .` = All checks passed；`ruff format --check .` 仍只 `backend/schemas.py` 一只（未被我改、Windows 换行形状，见 §13.5）；`mypy .` 仍是那**两条改前即红**的 `type-arg`，只是行号随我在 `main.py` 上方加的注释漂到 **`:2897`／`:3108`**（HEAD 轴 `:2872`／`:3083`）——同一台"行号会漂"的机器，所以本条只给命令与判据，不给行号当证据。
* 边界复量（收尾一次）：`.git/refs/heads/master` = `0b543960c7172ce1ffea57616952e4d5525190c4`（未提交）；`find chroma_db -type f -newermt "-8 hours"` = 0 文件且目录内最新 mtime 仍是 `2026-09-22 13:34`；`backend/app.db` = `2026-09-19 00:28`、`backend/data/app.db` = `2026-09-23 14:51`。仍未 push、未建 PR、未动 ref、未轮换凭据、未真实入库、未签任何字。

**§13.7 的台账要并入本节**：DB-19 的推荐措辞按 ⑥⑦⑧ 更正（丙落地当天③必须删）；另加三格待裁 —— **DB-21**（法名归一的未并清单：写侧 `import_docs` + 两份 eval 脚本 + 弱一档两份，是否随 DB-3 收口；括注形状要不要收窄）、**DB-22**（401/403/404 这类配置性拒绝的 TTL 分档；回到 DB-5 的"按错误文本窄匹配"口径？推荐"按状态码分两档：401/403/404 → 3600s 且快照单列，400/422 → 300s"）、**DB-23**（409 文案三条映射，推荐见 ⑩；我只缺你一句措辞授权，不缺判据）。

### 13.11 本轮我自己的两条写作事故（记在册，防复犯）

这两条都不影响代码与读数，但都是"静默型"事故，值得与 §12.8 那两条并列：

1. **转义折叠**：我在 §13.6 第 5 条补写路径时用了 Python 字符串写 Windows 路径，`\f` 被解释成换页符（U+000C）——正文里出现一个不可见控制符。抓法：写完后扫一遍全文控制字符（`python -c` 里数 `ord(c) < 32`），实测命中 1 个 formfeed，改成正斜杠写法修掉。
2. **Edit 吃掉粗体小标题**：为插入"冷却的运行学"整段，我把下一行的小节标题 `**DB-16（B-05 category 静默清零）—— 回落可见化**` 当作 `old_string` 的结尾、`new_string` 里忘了把它带回来 ⇒ 该小节标题静默消失（Edit 报 success，正文段落都在，肉眼几乎看不出）。抓法：改完立刻 `grep -c '**DB-16（B-05'`（应为 1 实得 0）+ 全文结构复查（H2/H3/粗体小标题条数、表块数与列数、围栏奇偶、CR 数）。

两台的共同点：**都是"写成功但内容少了/坏了"**，只能靠结构复查抓，不能靠"没报错"判断。规则句：**new_string 必须逐字带上 old_string 覆盖掉的任何标题或标记行，或改用"锚在上一段尾句"的插入写法；报告每次落盘后必跑一遍结构复查。**

> 本轮的面向人读的工作汇报另起了一份文件：`docs/process-archive/work-report-20261009-backend-implementation.md`（同一批事实的"30 秒版 + 台账"，不含 §11–§13 那些逐条证据）。两份文件的分工：本报告是**证据与判据的登录册**，那份是**可转发的工作汇报**。
