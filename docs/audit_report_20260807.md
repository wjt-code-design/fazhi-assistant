# 法智项目 生成式对抗审计报告

> 日期：2026-08-07 · 方式：Workflow 多 agent（6 维度并行扫描 → 每候选对抗式验证 → 综合）

> 结果：22 条候选 → **21 条确认**（其中 20 confirmed + 1 likely）/ **1 条反驳**

> 严重度分布：high **6** 条 · medium **13** 条 · low **2** 条（critical 0）

## 目录

1. [high] 文件上传/转写端点先读完整文件入内存再校验大小，任意登录用户可致内存耗尽崩溃（verify:backend/main.py:828）
2. [high] add_text 删旧插新非原子：写入失败时旧知识已被删且无回滚，导致知识库文档/条文静默丢失（verify:backend/knowledge_service.py:175）
3. [high] 流式问答中断时 UI 永久卡死：doSend 无 try/finally，streamChat 网络错误未捕获，setStreaming(false) 永不执行（verify:frontend/app/chat/page.tsx:487）
4. [high] 首次真实合同评估在会话已有任一 assistant 消息时被误判为「追问」，跳过完整报告模板（verify:backend/main.py:353）
5. [high] 旗舰流式 failover 后配额扣减记到最初 flag_key，真正回答的后备模型从不扣减（verify:backend/main.py:1321）
6. [high] 流式中途异常后重试：已发出的半截答案与重试完整答案拼接成乱码并可能入缓存（verify:backend/rag_chain.py:223）
7. [medium] 管理员默认口令硬编码 admin12345 且随 .env.example 发布，登录仅靠 10/min 限流无锁定（verify:backend/settings.py:24）
8. [medium] /api/media 端点缺失按用户归属鉴权，任意登录用户可读取他人上传的合同/证件图片（verify:backend/main.py:266）
9. [medium] QA 直返的 evidence 时效校验只对种子格式生效：自动沉淀 qa_pairs 的 evidence 是 JSON 数组（无 | 分隔），校验被静默跳过（verify:backend/main.py:758）
10. [medium] SSE 流式中途异常/客户端断开时 _post 不执行：会话留下无答复的用户消息且 message_count 永久错位（verify:backend/main.py:1339）
11. [medium] 流式重试切到后备模型后，token 配额仍按初始 flag_key 扣减：后备模型用量从不记账，看门狗失明（verify:backend/main.py:1319）
12. [medium] admin 分页参数未钳制：limit 负数被 SQLite 当作“不限”全表导出，offset 负数触发 500（verify:backend/main.py:1508）
13. [medium] 流式期间切换/新建会话导致消息污染与 conversationId 错位（verify:frontend/app/chat/page.tsx:498）
14. [medium] token 过期（401）无统一处理：不重登不跳转，会话静默失效（verify:frontend/lib/api.ts:36）
15. [medium] 法条标注 gap 正则 `\s` 含换行，与『跨句（含\n）断开续接』设计意图矛盾 → 换行后的独立条号误归属上一书名（verify:frontend/lib/annotate.ts:83）
16. [medium] 合同模式无退出机制且追问被拼进合同文本重新切条款，污染证据块、误路由无关问题（verify:backend/main.py:463）
17. [medium] 合同评估流式分支不扣配额、失败不 mark_depleted、重试绕开模型队列固定回退默认 omni（verify:backend/main.py:1137）
18. [medium] 用户提问原文（前 200 字）被写入结构化日志（multi_incomplete 的 detail 字段）（verify:backend/main.py:1283）
19. [medium] search_qa 在本地 L2 qa_pairs 上取 k=1 的欧氏最近邻再算余弦，候选选错导致命中丢失/注入错误 QA（verify:backend/knowledge_service.py:254）
20. [medium] 轻量升级路径配额错位：被拒的轻量模型 token 全部记到旗舰 key，轻量模型从不计费（verify:backend/main.py:1192）
21. [low] /api/feedback 未校验 conversation_id 归属，可伪造他人会话反馈并灌入受控沉淀待审队列（verify:backend/main.py:1705）
22. [low] rerank 配额监控关闭（rerank_quota_total=0 默认）时失败模型无记忆，每个请求都对坏模型重试一次网络往返（verify:backend/retrieval.py:140）

---

## 1. [HIGH] 文件上传/转写端点先读完整文件入内存再校验大小，任意登录用户可致内存耗尽崩溃

- **位置**：verify:backend/main.py:828　**类别**：denial-of-service　**验证**：confirmed

**根因 / 证据链**：
代码证据链完整成立。(1) main.py:828 `raw = await file.read()` 在大小校验前把整个上传文件读成单一 bytes 对象；大小检查在 knowledge_service.py:69 `if len(raw) > _MAX_UPLOAD_BYTES`(10MB)，由 parse_upload_or_raise (knowledge_service.py:115-125) 在完整读取之后才调用，拒绝发生在内存已全量分配之后。chat_transcribe main.py:863 同样先 read()，main.py:870 才按 settings.audio_max_mb(=10, settings.py:72) 校验；admin_upload main.py:1548 同模式（仅 admin）。 (2) 全项目无请求体大小限制：main.py:153-160 只注册 CORSMiddleware 和 RequestIdMiddleware；docker-compose 直接映射 8000:8000，无 nginx/caddy 代理层，无 client_max_body_size；Starlette UploadFile.read() 无大小上限（form 的 max_part_size 仅控制 1MB 内存 spool 阈值，非硬拒绝）。 (3) 认证前提成立：auth.py:50-63 get_current_user 要求合法 JWT，main.py:222 注册开放，任意注册用户可拿 token。 (4) 限流不构成防御：limiter 以 get_remote_address 为键 (main.py:124)，20/min 仅限制请求次数，单次超大请求即可打满内存。 (5) 部署使其可落地：单 uvicorn worker (docker-compose.yml:10, docs/OPS.md:3) + mem_limit 4g (docker-compose.yml:36)，进程内常驻 BGE/torch/Chroma，file.read() 把整文件物化为 bytes 对象，单个 2-3GB 上传即可把容器推过 4g 被 OOM kill 后 restart，服务不可用。审计 agent 推断基本正确，唯一小误差是大小检查不在同一条语句而在 helper 内，但确实位于完整读取之后，结论不变。

**可复现场景**：
1) POST /api/auth/register（main.py:222）注册普通用户拿 JWT token。2) 生成大文件：dd if=/dev/zero of=/tmp/big.txt bs=1M count=3000（3GB，.txt 扩展名满足 validate_upload 的 ext 白名单，decode 失败也发生在内存分配之后）。3) curl -X POST http://localhost:8000/api/chat/file -H "Authorization: Bearer $TOKEN" -F "file=@/tmp/big.txt" —— 请求体边接收边 spool 到磁盘，随后 main.py:828 file.read() 一次性把 3GB 物化为 bytes 对象；docker stats fazhi-backend 内存冲上 4g → 容器被 OOM kill → restart 循环，/healthz 不可达。单请求即足够，无需并发；限流 20/min 只限制次数不限制单次体积。

**修复建议**：
把三处无界读取改为带容量上限的流式读取（防 Content-Length 伪造，按实际接收字节累计）。在 main.py 新增 helper：`async def _read_capped(file: UploadFile, max_bytes: int, detail: str) -> bytes:` 循环 `await file.read(1024*256)` 累计，超限立即 `raise HTTPException(status_code=413, detail=detail)`。然后：main.py:828 改为 `raw = await _read_capped(file, settings.upload_max_mb*1024*1024, f"文件过大（>{settings.upload_max_mb}MB）")`（在 settings.py 新增 `upload_max_mb: int = 10`，替代 knowledge_service._MAX_UPLOAD_BYTES 的硬编码并在 knowledge_service.py:26/69 复用同一常量）；main.py:863 改为 `raw = await _read_capped(file, settings.audio_max_mb*1024*1024, ...)`；main.py:1548 同样替换。兜底：main.py:153 附近再加一层 Content-Length 预检中间件，`content-length` 头超过上限（如 12MB）直接 413，避免超大请求体进入 spool。

---

## 2. [HIGH] add_text 删旧插新非原子：写入失败时旧知识已被删且无回滚，导致知识库文档/条文静默丢失

- **位置**：verify:backend/knowledge_service.py:175　**类别**：correctness　**验证**：confirmed

**根因 / 证据链**：
代码证据充分：knowledge_service.py:175（upload 路径 `_collection().delete(where={"file_hash": file_hash_value})`）与 :189（manual/import 按 (source,article) `delete(ids=stale)`）都在写入之前执行；:197 才调 add_chunks，其 :152 `vectorstore.add_documents(docs)` 会先嵌入（rag_chain.py:113-117 的 vectorstore embedding_function=QuotaTrackingEmbeddings，rag_chain.py:104）。QuotaTrackingEmbeddings.embed_documents（rag_chain.py:96-101）先调 _check()（rag_chain.py:76-82）：provider=aliyun 且 quota_utils.utility_depleted（quota_utils.py:124-130，used>=total 且 total>0）时抛 UtilityQuotaExhausted，此时 Chroma 未写任何新切片，而旧切片已删。_WRITE_LOCK（:32）只串行化无回滚；调用链 main.py:1570（admin_upload）与 main.py:1533（manual）均无嵌入/配额前置校验，主循环 main.py:144-149 只在事后把异常转 409（候选说"转500"是唯一小错，不影响漏洞成立）。删除的 try/except pass（:176-177,190-191）只吞删除自身失败，不构成对写入失败的防护。判定 confirmed。

**可复现场景**：
1) EMBEDDING_PROVIDER=aliyun 并配好 key/base_url，把 embedding 配额设到将耗尽（或经 quota_store 使 utility_depleted 为 True）。2) 先用 POST /api/admin/knowledge/upload 上传某法文文件 A，切片带 file_hash 入库。3) 用光 embedding 配额。4) 再次上传完全相同的文件 A（同内容→同 sha256 file_hash）→ add_text 在 :175 删除旧切片后，add_chunks 的 add_documents→embed_documents→_check() 抛 UtilityQuotaExhausted（main.py 转 409）。5) 查 GET /api/admin/knowledge?source=<文件名>：文件 A 的全部切片已消失。manual 同理：配额耗尽时对已存在的 (source,article) 调 POST /api/admin/knowledge，:189 删旧后写入失败，该条文丢失。

**修复建议**：
把 knowledge_service.py:172-197 的 delete-then-add 改为 add-then-delete，且删除用"预先记录的旧 ids"而非共享元数据 where（避免新写入的 chunks 也带同 file_hash/(source,article) 而被误删）：{  with _WRITE_LOCK:      stale_ids=[]      if file_hash_value:          try: stale_ids=_collection().get(where={"file_hash":file_hash_value})["ids"]; except Exception: stale_ids=[]      # manual/import 分支同样先 get 旧 ids 存 stale_ids      n=add_chunks(pairs, ...)   # 先写新；失败则异常上抛，旧切片保留      if stale_ids:          try: _collection().delete(ids=stale_ids); except Exception: pass  # 删失败只留重复不丢数据      return n  }  即：删除移到 add_chunks 成功返回之后，用 :187 已记录的 id 列表精确删除；写入失败时不再先删旧。同时建议给 metadata 增加批次/version 标记便于清理"删除失败残留的旧重复切片"。

---

## 3. [HIGH] 流式问答中断时 UI 永久卡死：doSend 无 try/finally，streamChat 网络错误未捕获，setStreaming(false) 永不执行

- **位置**：verify:frontend/app/chat/page.tsx:487　**类别**：frontend　**验证**：confirmed

**根因 / 证据链**：
代码证据充分，漏洞真实成立。链路上每一环都核实过： (1) frontend/app/chat/page.tsx:484 `setStreaming(true)` 后，:487-534 `await streamChat(...)` 无 try/catch/finally，:535 `setStreaming(false)` 与 :536 `loadHistory()` 仅在正常完成时执行；调用方 :553 (`send`) 与 :560 (`quickSend`) 均裸调 `doSend` 不 await 不 catch，rejection 无人接。 (2) lib/api.ts:115-122 `fetch` 无守卫，:139-160 流循环 `while(true){ const {done,value}=await reader.read(); }` (:140) 无 try/catch；`onError` 只在 :132 (!res.ok) 和 :150 (p.error) 被调用，reader.read() 抛错时既不落错误文案也不置 false。 (3) UI 门控全依赖 `streaming`：textarea :1076、发送 :1080、图片 :1014、文件 :1029、语音 :1042 全部 `disabled={streaming}`，且 :476 `if ((!contentText && !image) || streaming) return;` 与 :558 `quickSend` 守卫彻底封死恢复发送。 (4) 无任何兜底：全前端 grep 无 AbortController/超时/signal；setStreaming 仅出现 :484/:535 两处；无 ErrorBoundary、无 window.onerror/unhandledrejection 处理器。因此服务端断连/重启/弱网 → reader.read() reject → promise 从 doSend 逃逸 → setStreaming(false) 永不执行，UI 永久卡在流式态。审计 agent 推断逐条准确，唯一正确排除的是 HTTP 错误路径（该路径被 onError 正常处理，与候选声称一致）。

**可复现场景**：
前置条件：本地起前后端。复现：(a) 在聊天框发一个会流式输出较久的法律问题（触发 /api/chat SSE）；(b) 输出进行中，在终端杀掉后端进程（或 Chrome DevTools → Network → Offline，或在 Network 面板 throttling 拉断）；(c) 观察：textarea、发送/上传图片/上传文件/语音按钮全部保持 disabled，最后一条 AI 消息停留在半截且无「出错了：…」文案，再点发送被 :476/:558 守卫拦截，只能刷新页面恢复。被动复现同样成立：后端 /api/chat 挂起（fetch 已 200、body 有流但迟迟不推 chunk），:140 `reader.read()` 永久 pending，无超时，UI 同样永久卡死。零代码验证：给 lib/api.ts:140 的 reader.read() 注入一次 reject，观察 doSend 内 :535 是否执行。

**修复建议**：
前端最小修复（page.tsx:487-536）：将 `await streamChat(...)` 包进 try/catch/finally，catch 中把最后一条消息置为「出错了：…」（复用现有 onError 的文案逻辑），finally 中保证 `setStreaming(false)` 与 `loadHistory()` 必然执行。例如：`setStreaming(true); try { await streamChat({...}, ..., onError, ...); } catch (err) { onError(err instanceof Error ? err.message : String(err)); } finally { setStreaming(false); loadHistory(); }`。根治修复（lib/api.ts:115-160）：为 fetch 传入 `AbortController` 的 signal 并设超时（如 60s 无数据即 abort），将整个 fetch+reader 循环包进 try/catch 并在 catch 里调用 `onError`（网络层失败时也给用户可见错误），从而让「挂起/断连」都有明确终点，不再依赖浏览器吞掉 rejection。两处可同时做，page.tsx 的 finally 是防止卡死的兜底，api.ts 的 catch/超时负责报错与终止。

---

## 4. [HIGH] 首次真实合同评估在会话已有任一 assistant 消息时被误判为「追问」，跳过完整报告模板

- **位置**：verify:backend/main.py:353　**类别**：contract　**验证**：confirmed

**根因 / 证据链**：
审计 agent 的推断链在代码中逐环成立，锚点全部准确：round1「帮我审合同」→ domain_rules.py:156/157 _REVIEW_VERBS含"帮我审"+_CONTRACT_NOUNS含"合同" → is_contract_review 命中（domain_rules.py:187）→ main.py:416 contract_mode True → main.py:442 _contract_convs.add(conv.id)；build_contract_data 的 need_clarify=len(t)<80（domain_rules.py:341）→ main.py:1105 反问 → main.py:1119 经 _post 以 role="assistant" 写库（main.py:597）。round2 粘贴合同全文：need_clarify=False，main.py:1123 调 _contract_messages，main.py:353 answered_before=any(role==assistant) 因历史含 round1 的 assistant 消息为 True，main.py:354 is_followup=True → 走 main.py:365 SYSTEM_CONTRACT_FOLLOWUP（prompts.py:136-141 明示"用户已在前面收到本合同的完整风险评估报告…不要重新输出完整风险评估报告"），但完整报告从未生成。反驳尝试均失败：缓存兜底不成立（main.py:674-676 _cacheable 要求 not pre["recent"]，round2 有历史）；通用 clarify 拦截不成立（main.py:1018-1022 contract 强制 strategy=direct）；_contract_convs 无移除路径；「先问候再审合同」同样成立（闲聊回复也是 assistant 消息）。即使 round1 intent 非 legal_query，round2 首次贴合同仍满足 _contract_convs+answered_before 双条件，同样误判——漏洞对两种 round1 行为都稳健。唯一未证实项是 classify_intent 对"帮我审合同"的归类，但该不确定性不影响结论成立。

**可复现场景**：
1) 启动后端，新建会话。2) 第1轮发「帮我审合同」（无合同全文）：走 main.py:1105 need_clarify 分支，SSE 返回 CONTRACT_CLARIFY_PROMPT，main.py:1119 _post 写一条 role="assistant" 消息（main.py:597），main.py:442 已把 conv.id 加入 _contract_convs。3) 第2轮在同一会话粘贴完整合同（≥80字）：is_contract_review 命中 → main.py:416 contract_mode=True → main.py:442 再次 add；need_clarify=False；main.py:1123 调 _contract_messages → main.py:353/354 is_followup=True → 模型收到 SYSTEM_CONTRACT_FOLLOWUP（prompts.py:136，含"用户已在前面收到完整风险评估报告…不要重新输出完整报告"），按追问模式回答，不输出 ①结论 ②风险清单 ③解读 的结构化模板。变体：先发「你好」闲聊（round1 回复为 assistant 消息），round2 贴合同，同样触发。可在 _contract_messages 调用处打日志打印 is_followup 值验证。

**修复建议**：
main.py:353-354：把"追问"判定从"历史中存在任何 assistant 消息"改为"该会话已真正输出过完整报告"。具体：(a) 在 main.py:335 `_contract_convs: set[int] = set()` 旁新增 `_contract_reviewed: set[int] = set()`；(b) 在 _contract_messages 的 non-followup 分支（main.py:373-379，返回 [SystemMessage(SYSTEM_REVIEW), HumanMessage] 前）插入 `_contract_reviewed.add(pre["conv_id"])`（与 main.py:442 的 _pre 副作用风格一致）；(c) 把 main.py:354 改为 `is_followup = pre.get("conv_id") in _contract_reviewed and answered_before`。这样 need_clarify 反问轮与闲聊轮都不会把首次真实合同评估误判为追问；只有真正输出过 SYSTEM_CONTRACT_REVIEW 报告的会话才走 FOLLOWUP。保留 _contract_convs 不变（main.py:416 仍用于续聊短句不脱离合同路径）。可选加固：round1 need_clarify 反问若以 assistant 落库（main.py:1119），可在 _post 时给该消息打标记，避免被误认作"已出报告"。

---

## 5. [HIGH] 旗舰流式 failover 后配额扣减记到最初 flag_key，真正回答的后备模型从不扣减

- **位置**：verify:backend/main.py:1321　**类别**：quota　**验证**：confirmed

**根因 / 证据链**：
代码证据完整闭合，审计 agent 的推断全部成立：

1) 初始 pick 与扣减 key 分离：main.py:1032 `flag_key, flag_llm, flag_degraded = _safe_pick(modality, tier or "flag")`；`flag_key` 是闭包内局部变量，从 1032 到函数结尾从未被重新赋值（grep 确认全文仅 1030 置 None、1032 赋值）。

2) failover 真正回答的模型记录在 current["key"]：main.py:1212 `current = {"key": flag_key}`；main.py:1214-1228 make_chain_fn 在重试（_i!=0）时调用 `_safe_pick` 并把 `current["key"] = key`（main.py:1223）。rag_chain.py:188-229 stream_with_retry 在 astream 抛异常时先调 on_model_failure 再重跑 make_chain_fn（line 224-228），因此异常 failover 后实际生成答案的模型确实切换为后备模型（如 text_ds_flash）。

3) 结尾扣减却固定用 flag_key：main.py:1319-1321 `if use_router and flag_key and answer: ... registry.deduct(flag_key, est * registry.thinking_mult(flag_key))`——只判 flag_key、只扣 flag_key，current["key"] 从未参与。llm_registry.py:278-287 deduct 对该 key 的 runtime_used 累加并经 quota_store.record_delta 持久化（quota_store.py:68-86）。

4) 失败仅内存标记不持久化：llm_registry.py:324-335 mark_depleted 只 `runtime_used += max(0, quota_left)`，不调 record_delta。llm_registry.py:99-115 quota_left 被 clamp 到 0、depleted/below_threshold→unavailable 决定 pick 是否选中。

结论：failover 成功后，答案来自 current["key"]（如 text_ds_flash），但配额全记到已 mark_depleted、quota_left 已钳 0 的 flag_key（text_flag）头上；text_ds_flash 的 quota_left 恒满、unavailable=False，pick（llm_registry.py:260-276 按 priority 选首个可用）会持续选中它，直到供应商侧真实配额耗尽返回 429/403 或成本超支；text_flag 被重复多记（持久化 record_delta 仍累加，但对 availability 无影响——多余扣减在钳位层面"丢失"）。锚点行号准确。

已排除的反驳路径：(a) 空答重试不触发 mark_depleted，_safe_pick 通常重选同一 text_flag，此时 current["key"]==flag_key，扣减恰好正确——但这只覆盖空答子路径，不影响异常 failover 的错记；(b) 分支2 内无其他对 current["key"] 的 deduct 调用（grep 仅 878 语音、1192 轻量、1321 旗舰三处）；(c) stream() 外层 try（main.py:1344-1350）只降级返回，不修正扣减。

**可复现场景**：
触发路径（需制造一次流式异常，这是程序明示支持的 failover 场景）：
1) 启动后端，确认 use_router 开启、走非 light 分支（tier=flag 或带 contract_data）。读取 quota_store（data/quota_used.sqlite 的 quota 表）记下 text_flag 与 text_ds_flash 的 used 基线。
2) 制造 text_flag 首次流式异常：临时把 text_flag 的 model 名改错（llm_registry.py:37 的 model 字段指向不存在的模型，使 ChatOpenAI 抛 404/400），或撤掉其 api_key。
3) 经 /api/chat 发一条 text 法律咨询（stream=true）：attempt 0 用 text_flag 抛异常 → rag_chain.py:224 调 on_model_failure → main.py:1234 mark_depleted("text_flag")；attempt 1 make_chain_fn(_i=1) → main.py:1222 _safe_pick 返回 text_ds_flash 且 current["key"]="text_ds_flash" → 答案由 text_ds_flash 生成。
4) 请求结束后读 quota 表：text_flag 的 used 增加（est×thinking_mult 被记到它头上，llm_registry.py:286-287），text_ds_flash 的 used 不变（其真实扣减丢失）。验证 mark_depleted 未持久化（llm_registry.py:335 只改内存 runtime_used）。重复多次 failover，text_ds_flash 配额永远不降、持续被 pick 选中。

**修复建议**：
main.py:1319-1321 改用实际回答模型 current["key"] 扣减：

    if use_router and current["key"] and answer:
        est = estimate_tokens(answer) + estimate_tokens(pre.get("context", "") + pre.get("user_text", ""))
        registry.deduct(current["key"], est * registry.thinking_mult(current["key"]))

同步修正日志/缓存埋点的模型标识，避免记录与实际回答不符：main.py:1327 log_account 的 model=registry.model_of(current["key"])；main.py:1303 缓存写入门处 model=registry.model_of(current["key"])（原来都写 registry.model_of(flag_key)，failover 后会把后备模型的答案记成 text_flag）。

边界说明：全部 3 次流式尝试失败后走 main.py:1249 `_invoke_llm(messages, flag_llm)` 兜底时，实际回答模型是 text_flag 而 current["key"] 可能是最后一次 _safe_pick 的结果。若要完全精确，可在 make_chain_fn（main.py:1214-1228）每次建链时记录实际所用 key（如 current["key"]=key 再额外在 `_i==0` 分支也同步），并在 1249 兜底路径显式用 flag_key 扣减。主修复（改用 current["key"]）已消除 dominant 的 failover 错记问题。

---

## 6. [HIGH] 流式中途异常后重试：已发出的半截答案与重试完整答案拼接成乱码并可能入缓存

- **位置**：verify:backend/rag_chain.py:223　**类别**：correctness　**验证**：confirmed

**根因 / 证据链**：
代码证据充分，漏洞真实。链路：main.py:1238-1246 的 `async for piece in stream_with_retry(...)` 中每个 piece 都 `chunks.append(piece)` 并立即 `yield` 给 SSE 客户端，`chunks` 无按 config 重置；rag_chain.py:223-228 的 `except Exception` 在 `i < len(configs)-1` 时仅 `on_model_failure(e)`+`sleep`+`continue`，不重置已流出内容，异常被 stream_with_retry 内部吞掉，main.py 的 async for 感知不到失败而继续接收下一 config 从零重答的整题流，逐 piece append 到同一 `chunks` → main.py:1246 `answer = "".join(chunks)` = 半截+整答拼接乱码。make_chain（rag_chain.py:126-128）仅为 `llm | StrOutputParser()`，无下层 with_retry 兜底；触发条件正是代码自身注释（rag_chain.py:194-199）设计要捕获的「配额耗尽/模型名错误/瞬时失败」，配额耗尽常发生于生成中途。缓存放大：main.py:1290-1304 对拼接 answer 跑 self_check，PASS 即写 answer_cache（TTL 6h，answer_cache.py:17），_cache_write_ok（main.py:685-699）仅拦 study_aid 引用子集、legal_query 直接放行；且即便自检拦缓存，SSE 端乱码也已无条件下发，核心缺陷不依赖缓存成立。审计 agent 的推断（锚点行号、拼接语义、缓存放大）全部与代码吻合，无前置守卫可反驳。

**可复现场景**：
复现路径：POST 流式 chat 接口（main.py 分支2旗舰/legacy 流式，line 1211 起），触发条件为 config 0 或 1 的 `chain.astream` 在已流出约 200 字后抛异常——例如该模型配额在生成中途耗尽（registry.mark_depleted 后 _safe_pick 落后备），或网络/供应商瞬时错误。此时（1）客户端已通过 SSE 收到 config 0 的半句；（2）rag_chain.py:224-228 吞掉异常并 continue 到 config 1，make_chain_fn（main.py:1214-1228）重新 pick 模型从零答整题；（3）config 1 的完整答案逐 piece append 进 main.py 的 chunks 并继续 SSE 下发 → 最终 `answer` 为拼接乱码，客户端先收半句又收全新整答。若该乱码通过 main.py:1291 self_check，则按 6h TTL 写入 answer_cache（answer_cache.py:17），近重复同 key 用户在 6h 内会命中该坏缓存。同样的拼接模式还存在于合同审查分支 main.py:1135-1146。可通过在测试中 mock chain.astream：yield 数个 piece 后 raise，再让下一 config yield 完整答案，断言最终 answer 为两者拼接来复现。

**修复建议**：
双层修复。根因是异常路径把"已流出半截"与"整题重答"静默拼接，且调用方感知不到中途失败。(1) rag_chain.py:206-229：为每个 config 增加 `emitted` 标志，仅在"本 attempt 尚未产出任何内容"时才允许自动重试，中途已流出则 `raise`，不再 continue 重答整题——即 `except Exception as e:` 分支条件改为 `if on_model_failure and i < len(configs) - 1 and not emitted:`，并在 `async for` 内 `piece` 有效时置 `emitted = True`；否则上抛。(2) main.py:1238-1246：用 try/except 包裹整个 `async for piece in stream_with_retry(...)`，异常时打印日志、置 `answer = ""`（半截不参与自检/缓存）、向 SSE yield `{"error": "生成中断，请稍后重试"}`，避免走后续自检/写缓存/审计"ok"路径；同模式修复合同审查分支 main.py:1135-1146。若需保留中途失败重试的体验，可另加显式 restart 哨兵让前端清空已收内容、并重置 main.py 的 chunks，但这是侵入式改动，`emitted` 门禁+上抛为最小安全修复。

---

## 7. [MEDIUM] 管理员默认口令硬编码 admin12345 且随 .env.example 发布，登录仅靠 10/min 限流无锁定

- **位置**：verify:backend/settings.py:24　**类别**：broken-authentication　**验证**：confirmed

**根因 / 证据链**：
漏洞链条在代码中完全成立，但审计 agent 的锚点有误。真实默认口令源是 seed_admin.py:17 `password = os.getenv("ADMIN_PASSWORD", "admin12345")`，而非 settings.py:24——grep 全后端无任何代码读取 settings.admin_password（该字段在鉴权路径上是死代码）。实际链条：backend/.env.example:33 明文发布 `ADMIN_PASSWORD=admin12345` 作为模板；README.md:43 / OPS.md:78 文档流程就是 `cp .env.example .env` 后原样保留；docker-compose.yml:25 `ADMIN_PASSWORD=${ADMIN_PASSWORD}` 在根 .env 未定义时展开为空串（compose 默认 blank），此时 os.getenv 因变量"已设置但为空"返回空串而非默认值，seed 会创建**空口令**管理员；seed_admin.py:22-26 用 hash_password 创建 role=admin 的账号。登录端点 main.py:241-252 仅 `@limiter.limit("10/minute")`（按 IP，fastapi-limiter 默认 key），无账号锁定/失败计数；对已知默认口令只需一次尝试即成功，限流形同虚设。成功登录后 create_token（auth.py:40-47，7 天有效）授予 admin 角色，require_admin（auth.py:66-69 仅校验 role=="admin"）保护的全部管理接口可直达：admin_delete_user main.py:1481、知识库上传 main.py:1547、LLM 切换 main.py:1627、QA 采纳 main.py:1609/1615。models.py User 无 must_change_password 字段，.env.example:31 与 seed_admin.py:29 的"请尽快修改"仅为注释，无强制改密。反证尝试均失败：Docker CMD 是纯 uvicorn（main.py:139 lifespan 不 seed，需手动跑 seed_admin.py），但文档部署流程正是如此，管理员账号必然经 seed_admin 以该默认口令创建。

**可复现场景**：
1) 按文档部署：`cd backend && cp .env.example .env`（保留第 33 行 `ADMIN_PASSWORD=admin12345`，填好 JWT_SECRET），`python seed_admin.py` 创建 admin（或 docker compose 时根 .env 未设 ADMIN_PASSWORD 则第 25 行展开为空串 → 空口令）。2) 攻击者 `POST /api/auth/login` body `{"username":"admin","password":"admin12345"}`（空口令场景 password 传 `""`）→ 返回 role=admin 的 JWT。3) 携带 token 调 `DELETE /api/admin/users/{user_id}`（main.py:1481）或 `POST /api/admin/knowledge/upload`、`POST /api/admin/llm/switch` 等，全部 200 成功。触发条件：管理员已通过 seed 创建且口令未被修改。

**修复建议**：
1) settings.py:24：删除硬编码默认值，改为必填或空串并校验非空（如 `admin_password: str = Field(..., min_length=8)`），消除"看似配置了密码"的假象（该字段当前本就未被读取，属死配置，可直接移除或改为启动时校验）；2) backend/.env.example:33：改为 `ADMIN_PASSWORD=`（留空）并注释说明 compose/seed 会强制要求非空，杜绝模板携带公知口令；3) docker-compose.yml:25：改为 `- ADMIN_PASSWORD=${ADMIN_PASSWORD:?请在根 .env 设置 ADMIN_PASSWORD}`，缺省即启动失败，堵住空口令路径（对应 root .env 未定义时的 blank 展开）；4) seed_admin.py:17-26：若 `os.getenv("ADMIN_PASSWORD")` 为空/未设，直接报错拒绝创建（或生成随机强口令并仅打印一次），不要回退 admin12345；5) main.py login（main.py:241-256）：在 IP 限流之外增加账号级锁定——对同一 username 累计失败次数（如 5 次失败 → 锁定 15 分钟，锁定状态存 DB/Redis），并新增首次登录强制改密（User 表加 must_change_password 字段，登录返回临时态）。

---

## 8. [MEDIUM] /api/media 端点缺失按用户归属鉴权，任意登录用户可读取他人上传的合同/证件图片

- **位置**：verify:backend/main.py:266　**类别**：idor　**验证**：confirmed

**根因 / 证据链**：
代码证据充分，锚点与推断均成立。main.py:265-274 `get_media` 仅 `Depends(get_current_user)`（auth.py:50-63 只校验 JWT 有效性与账号启用），无任何归属校验；main.py:270 的路径检查只保证 `full` 落在 MEDIA_DIR 内，main.py:274 直接 `FileResponse(full)` 返回。存盘路径 multimodal.py:78-94 为 `media/{uuid4hex}.{ext}` 与 `{uuid}_thumb.jpg`，uuid4().hex 为 128-bit 随机、不可枚举（审计 agent 对"不可枚举"的判断正确）。image_ref/thumb_ref 仅通过 /api/conversations/{conv_id} 返回，且该端点做了归属校验（main.py:1404 `conv.user_id != user.id` → 404），故 B 无法从 API 内正常枚举到 A 的路径，路径获取依赖带外泄露（前端 fetch `/api/media/${ref}` 带 Bearer，api.ts:245-247，URL 暴露于 A 自己的网络面板/DevTools/代理访问日志，可经截图、分享、日志泄露给 B）。因此"任意登录用户只要拿到路径即可读取他人媒体文件"在当前代码路径中真实成立：服务端对 media 目录内文件不做 per-user 授权，资源 ID（路径）与登录用户之间无绑定，属典型 BOLA/IDOR。审计 agent 的推断唯一偏弱点是"浏览器历史"——前端用 fetch+Blob 不走导航，一般不进历史，但 DevTools 网络面板/截图/共享链接/访问日志等泄露渠道已足以支撑该威胁模型。

**可复现场景**：
1) 用户 A 注册登录，POST /api/chat 携带图片 data URL（main.py:980 → _pre main.py:398 `persist_image`），随后 GET /api/conversations/{id}（main.py:1401-1412）响应中拿到 `image_ref="media/<uuidA>.png"`。2) 路径经带外渠道泄露给登录用户 B（如 A 的 DevTools 网络面板截图、访问日志、或分享的链接/图片 src）。3) B 用自己的 Bearer token 请求 `GET /api/media/media/<uuidA>.png`：get_current_user 通过（B 已登录且启用）、main.py:270 路径检查通过（在 MEDIA_DIR 内）、文件存在，main.py:274 直接返回 A 的合同/证件原图；请求 `..._thumb.jpg` 同理。

**修复建议**：
在 main.py:265-274 的 `get_media` 中增加归属校验：文件路径必须命中当前用户自己的消息。改签名 `def get_media(filepath: str, user: User = Depends(get_current_user), db: Session = Depends(get_db))`，保留原路径穿越检查（main.py:270），随后查询 `db.query(Message).join(Conversation, Message.conversation_id == Conversation.id).filter(Conversation.user_id == user.id).filter(or_(Message.image_ref == filepath, Message.thumb_ref == filepath)).first()`，若为 None 则 raise HTTPException(404, "文件不存在")（与现有 404 语义一致，避免泄露存在性），最后再返回 FileResponse。需从 main.py 顶部相应导入 or_（或分别 filter 两次）。此改法将资源 ID 与登录用户绑定，使非归属请求一律 404，同时兼容缩略图（thumb_ref 路径与 image_ref 不同，须用 or_ 匹配两者）。

---

## 9. [MEDIUM] QA 直返的 evidence 时效校验只对种子格式生效：自动沉淀 qa_pairs 的 evidence 是 JSON 数组（无 | 分隔），校验被静默跳过

- **位置**：verify:backend/main.py:758　**类别**：correctness　**验证**：confirmed

**根因 / 证据链**：
逐行核对全部命中。时效护栏只在 main.py:758 `if "|" in evidence:` 时生效（759-764 split 后调 exact_article_lookup）。三种写入 evidence 的来源中，仅 qa_seeds.py:61 `f"{source}|{article}"` 含 "|"；自动沉淀 main.py:612 `json.dumps(pre["sources"], ensure_ascii=False)` 产出 JSON 数组（中文法名/条号无 "|"），feedback main.py:1717 `f"feedback:{body.rating}"` 也无 "|"。自动沉淀路径（knowledge_service.py:285-286，AUTO_CURATE_THRESHOLD=0.89）直接写 qa_pairs，main.py:478 search_qa + main.py:1061 `_qa_direct_return` 对 legal_query 全量可达且无 feature flag 门禁，命中即 main.py:1062-1078 零 LLM/零 self_check 直返。条文被删/改废时 retrieval.invalidate()（retrieval.py:387-397）只清 BM25/_src_set_cache/_cache/answer_cache，全仓无 `_qa_store.delete`，delete_doc（knowledge_service.py:200-203）也不碰 qa_pairs；exact_article_lookup（retrieval.py:230-246）经 is_valid_by_time 本来能拦住失效条文，只因 evidence 无 "|" 永不执行。审计 agent 推断全部正确；唯一轻微不精确处是 feedback 条目 grounded=0 先进 pending，需管理员采纳（knowledge_service.py:332）才入 qa_pairs，但采纳后 evidence 仍是 "feedback:xxx" 无 "|"，护栏同样被跳过，不影响结论。docstring main.py:747-748 声称护栏对全部直返生效，与实际行为相悖，进一步佐证。

**可复现场景**：
1) POST /api/chat 问一条 grounded 分 ≥0.89 的法律问题（有据分达标 → main.py:608-612 create_candidate → knowledge_service.py:285-286 直接写 qa_pairs，evidence=JSON 数组）；2) 管理员经 admin 接口删除或改废该条文（delete_doc，knowledge_service.py:200-203；invalidate 只清答案缓存，不清 qa_pairs）；3) 再 POST /api/chat 以同题/近同问法提问 → main.py:478 search_qa(rewritten) 余弦 ≥0.92 命中该 qa_pair → main.py:1061 _qa_direct_return 里 evidence 为 JSON 无 "|"（main.py:758 恒假）→ 跳过时效校验直接返回存库的旧答案（main.py:1062-1078），绕过 LLM 与 self_check。可用 tests/test_qa_direct_return.py 类比验证：把 evidence 换为 `[{"source":"民法典","article":"第一千二百六十条"}]` 且 exact_article_lookup 返回 []，当前代码仍返回旧答案（未触发 None）。

**修复建议**：
改 main.py:757-765：把时效校验改为同时兼容 seed 与 JSON 两种 evidence 格式。具体：`pairs=[]; if "|" in evidence: src,art=evidence.split("|",1); pairs=[(src,art)] else: try: arr=json.loads(evidence); pairs=[(s.get("source",""),s.get("article","")) for s in arr if isinstance(s,dict) and s.get("source") and s.get("article")] except Exception: pairs=[]`，然后对 pairs 逐个 `exact_article_lookup`，任一返回空（条文已删/失效）或抛异常则 return None（保持"任一失效即不直返"的既有语义）。feedback 条目 evidence="feedback:..." 解析不出条文对，pairs 为空自然跳过（行为不变）。同时更新 docstring（main.py:747-748）说明 JSON 数组形式也校验。可选加固：在写侧 main.py:612 把 sources 归一为 `"|".join(f"{s['source']}|{s['article']}")` 统一格式（需配套修改 759 行的单对 split 以支持多对）。

---

## 10. [MEDIUM] SSE 流式中途异常/客户端断开时 _post 不执行：会话留下无答复的用户消息且 message_count 永久错位

- **位置**：verify:backend/main.py:1339　**类别**：sse　**验证**：confirmed

**根因 / 证据链**：
代码证据链完整：(1) main.py:500-516 `_pre` 在 LLM 流式前即 `db.add(Message(role="user"...))` + `conv.message_count=(conv.message_count or 0)+1` + `db.commit()`，user 消息与计数先行落库；(2) assistant 消息唯一写入点是 `_post` 内 main.py:597，且 `_post` 仅在成功路径调用（流式 main.py:1339 `if answer:`、轻量 main.py:1204、合同 main.py:1174、缓存 main.py:1053）；(3) 失败路径全部跳过 `_post`：空答 main.py:1285-1286 只 yield error（1339 的 `if answer:` 为假），`except LLMBusyError` main.py:1344-1346 与 `except Exception` main.py:1347-1350 均 yield error 后 return；(4) 流式生成器 1034-1351 无 `finally`（全文件 finally 仅在 199/235/253/534/569/618/916），客户端断开 Starlette aclose() 注入 GeneratorExit（BaseException，不被 main.py:1347 `except Exception` 捕获），`_post` 同样不执行；(5) message_count 赋值点仅 388/510/599/1358，无按实际行数重算的对账逻辑，`role="assistant"` 无其它写入点，无孤儿清理。故失败/断开一轮后 DB 留下无答复 user 消息且 message_count 永久 +1。传导：memory.py:56 `window_start=max(0,message_count-RECENT_K)` 与 memory.py:96 `summary_upto` 依赖该计数，膨胀使窗口边界偏移、孤问题作为 recent 上下文发给 LLM（memory.py:26-34 recent_messages 取最近 RECENT_K 条含该孤消息）。审计 agent 推断正确；仅一处细化：孤消息是最新消息，落在 recent 窗口而非压缩窗口，计数 +1 使多压一条本应保留的旧消息——但"计数错位→memory.py 窗口计算失真"结论成立。

**可复现场景**：
1) 启动 backend（uvicorn main:app，配好 DB），打开一次会话取得 conversation_id；2) 触发失败路径任一即可：a) 调 POST /api/chat 带 SSE，制造 LLM 报错（如把上游 API key 改错使 stream_with_retry 中途抛异常，或并发触发 llm_guard 的 LLMBusyError），或 b) 流式进行中用 curl --max-time / 关闭浏览器标签页中断连接；3) 查 DB：SELECT count(*) FROM messages WHERE conversation_id=?，与 conv.message_count 对比——message_count 比实际消息条数多 1，且最后一条是 role='user' 的孤立消息、无 assistant 回复；4) 重开该会话可见孤立未答复问题；读 backend/memory.py:56、96 验证计数被用于窗口计算（RECENT_K=6、TURN_THRESHOLD=12）。

**修复建议**：
在 main.py 流式生成器（1034-1351）补一处补偿：引入 `posted` 标志，在所有成功调用 `_post` 的路径置位；在生成器加 `finally`（须在 GeneratorExit 下也能执行，内部禁止再 yield，补偿写成独立线程池 DB 调用并 try/except 包裹）。补偿逻辑：若一轮失败/断开且未 `_post`，则写入一条 assistant 占位消息（如"服务暂时无响应，请稍后重试"）使 user/assistant 成对、计数平衡；或删除刚落库的该 user 消息并对 `conv.message_count` 回退 -1。需覆盖的三处：`if not answer` 路径（main.py:1285-1286）、`except LLMBusyError`（main.py:1344-1346）、`except Exception`（main.py:1347-1350），以及轻量分支空答（main.py:1187-1188）。防御性加固：memory.py:56 与 memory.py:96 改用实际消息数 `db.query(func.count(Message.id)).filter(Message.conversation_id==conv.id).scalar()` 推导 window 边界，使窗口计算不再信任可能漂移的 message_count。

---

## 11. [MEDIUM] 流式重试切到后备模型后，token 配额仍按初始 flag_key 扣减：后备模型用量从不记账，看门狗失明

- **位置**：verify:backend/main.py:1319　**类别**：quota　**验证**：confirmed

**根因 / 证据链**：
代码证据充分，候选成立。main.py:1212 初始化 `current={"key": flag_key}`；make_chain_fn 在重试 `_i>0` 时经 `_safe_pick` 重选模型并更新 `current["key"]`（main.py:1222-1223），随后 `stream_with_retry` 的 on_model_failure（main.py:1230-1234）对 `current["key"]` 调 `registry.mark_depleted`（llm_registry.py:324-335 置 quota_left=0 → depleted → pick 跳过）。但扣减 main.py:1319-1321 固定用初始 `flag_key`，而非实际生成答案的 `current["key"]`。全库仅 3 处 deduct：main.py:878（语音转写）、1192（轻量路径用正确的 res.key）、1321（用错 flag_key）——因此重试落到后备模型（如 text_ds_flash，priority 1）后，其后备用量从不写 quota_store（record_delta 未触发，get_used 恒为 0），llm_registry.py:100-111 的看门狗（quota_left = total - initial - runtime）对该模型完全失明，quota_left 恒满、below_threshold 永不触发。这与"用完即止"的配额设计意图直接违背；块2.2 自动换模型行为本身有测试覆盖（tests/test_quota_switch.py），证明重试换模型是可达且被设计支持的路径。附带效应：瞬时错误场景下 text_flag 被误标耗尽（代码注释也承认此代价）还背上本不该由它扣的 token。审计 agent 的推断正确，唯一小瑕疵是 `current={"key": flag_key}` 锚点应为 main.py:1212（其写的 1312 是笔误，不影响结论；1222-1223/1230-1234/1319-1321/llm_registry.py:100-111 锚点均准确）。

**可复现场景**：
1) 用默认 DEFAULT_ROLES（text_flag 现役旗舰 + text_ds_flash 后备，quota_total 均 100 万）。2) 构造一个使 text_flag 流式 astream 抛异常的请求：临时把 text_flag 的 model/base_url 改错（或对该模型 mark_depleted/在管理端清空配额），发 POST /api/chat 且 use_router=True、use_light=False（modality=text, tier=flag），绕过缓存与 clarify/refuse 分支。3) 观察：stream_with_retry i=0 用 text_flag 抛错 → on_model_failure 把 text_flag 标耗尽 → i=1 经 _safe_pick 落到 text_ds_flash 生成完整答案。4) 检查配额：quota_store.get_used("text_ds_flash") 恒为 0（后端 record_delta 只对 flag_key 调用，main.py:1321），text_ds_flash 的 quota_left 仍为满额、可被反复烧用且看门狗不切换/不报警；而 text_flag 的 runtime_used 反而被这次失败答案的估算扣减。最小可复现入口：直接对照 main.py:1214-1228（重试 re-pick 更新 current["key"]）与 main.py:1319-1321（扣减仍用 flag_key）。

**修复建议**：
main.py:1319-1321：把扣减目标从 flag_key 改为实际产生答案的 current["key"]（同函数作用域内可访问）——即 `charged = current["key"] if current.get("key") else flag_key`，然后 `registry.deduct(charged, est * registry.thinking_mult(charged))`（thinking_mult 也应按真实模型算，否则思考类后备模型的 ×3 系数也失效）。同步修正归因：main.py:1327 的 log_account `model=registry.model_of(flag_key)` 应改 `registry.model_of(charged)`；main.py:1303 缓存写入的 model 标记 `registry.model_of(flag_key)` 同样建议改用实际模型（低优先，仅影响缓存元数据）。改后需注意：分支2 仅 use_router 场景才进入，`current` 必然已定义，legacy 路径（use_router=False）不触达该扣减。建议补一条回归测试：模拟 i=0 抛错、i=1 由后备模型出答案后，断言 quota_store 中后备 key 的 used 增加而 text_flag 不增。

---

## 12. [MEDIUM] admin 分页参数未钳制：limit 负数被 SQLite 当作“不限”全表导出，offset 负数触发 500

- **位置**：verify:backend/main.py:1508　**类别**：pagination　**验证**：confirmed

**根因 / 证据链**：
核心漏洞真实：admin_conversations（main.py:1501-1502 仅声明 `limit:int=50, offset:int=0`，1508-1509 直接 `.offset(offset).limit(limit)`，无任何钳制）对 limit 完全放行。实机验证（本机 Python sqlite3，SQLite 3.53.2）：`LIMIT -1` 返回全表所有行（unlimited 语义），SQLAlchemy 会把 -1 作为绑定参数原样下推，故 `?limit=-1` 确实一次性导出全表 conversations；`?limit=1000000` 亦全量加载不截断。admin_analysis_runs（main.py:900 `limit(min(limit,200))`）对负数仍放行：min(-1,200)=-1，同样全表导出。审计 agent 的对照证据准确：admin_audit main.py:1684、admin_feedback main.py:1723 均用 `min(max(limit,1),500)` 钳制，list_docs knowledge_service.py:213-214 用 `max(1,min(int(limit),500)); offset=max(0,int(offset))` 钳制，唯独 admin_conversations 裸漏。但审计 agent 有一处推断错误：声称 `?offset=-1` 触发 SQLite '1st OFFSET argument out of range' 500——实机验证 SQLite 3.53.2 中 `LIMIT -1 OFFSET -1` 不报错，负数 OFFSET 被当作 0 处理（该错误仅存在于旧版 SQLite），因此 offset→500 这一失败模式在当前运行时被反驳，offset=-1 仅表现为等价于 offset=0。考虑 require_admin 前置（仅管理员可触发，非越权边界，属资源/健壮性缺陷），medium 定级可接受。

**可复现场景**：
前置条件：持有管理员 JWT（任一 admin 账号登录后取 token）。1) `GET /api/admin/conversations?limit=-1`（带 `Authorization: Bearer <admin_token>`）→ 返回全部会话记录（全表导出，行数 = conversations 表总行数），响应体/内存随表规模无界增长；`?limit=1000000` 同理全量加载。2) `GET /api/admin/analysis-runs?limit=-1` → 同样全表导出（min(-1,200)=-1）。3) `?offset=-1` → 当前 SQLite 3.53.x 下不报错，等价 offset=0（不会 500，与审计 claim 不符）。复现条件即"管理员 + 该参数直接透传"，无其他前置守卫。

**修复建议**：
main.py:1502 函数签名后、1504 查询前加钳制，与同文件既有模式保持一致：`limit = min(max(int(limit), 1), 500); offset = max(0, int(offset))`（参照 knowledge_service.py:213-214 的 list_docs 与 main.py:1684 的 admin_audit）。具体改法：在 `admin_conversations` 内 `rows = (...)` 之前插入这两行即可，改后 LIMIT 恒在 [1,500]、OFFSET 非负。同时修复 main.py:900 `admin_analysis_runs`：`limit(min(limit, 200))` → `limit(min(max(limit, 1), 200))`，堵住负数 LIMIT -1 的全表导出。若希望覆盖更大，可另在 auth.require_admin 或全局中间件统一钳制，但按本任务最小修复以上两处即足。

---

## 13. [MEDIUM] 流式期间切换/新建会话导致消息污染与 conversationId 错位

- **位置**：verify:frontend/app/chat/page.tsx:498　**类别**：race　**验证**：confirmed

**根因 / 证据链**：
全部关键点在代码中逐一验证成立：(1) page.tsx:494-501 chunk 回调 `copy[copy.length-1]={...copy[copy.length-1],content:acc}` 是函数式 setMessages，无条件覆盖当前 messages 最后一条，无会话归属校验；(2) selectConv(298-318) 绑定在侧栏历史项 onClick(page.tsx:693) 上且无 `if(streaming) return` 守卫，newChat(287-296)/deleteConv(321-335) 同样无守卫，侧栏在流式期间完全可点（输入区按钮 1014/1029/1076/1080 虽 disabled 但侧栏不禁用）；(3) 时序成立：selectConv 在 await convApi.detail(B) 之后才 setMessages(B.messages)（305-313），而 SSE 流式期间后续到达的 chunk（api.ts:151）会对 B 的数组做 `copy[length-1]=...` 覆盖，污染 B 的最后一条；(4) conversationId 翻转成立：后端首个 SSE 事件必带 conversation_id（main.py:1051/1072/1094 等 `{'conversation_id': pre['conv_id'],...}`），前端 onMeta(page.tsx:502-515) 无条件 setConversationId，selectConv 在点击瞬间已把 conversationId 置为 B(300)，后续 meta 会改回 A；streamChat 无 AbortController/取消令牌（api.ts:136-161），setStreaming(false)@535 与 loadHistory()@536 均不修复 conversationId/messages。审计 agent 的推断正确，锚点 498 正确。唯一外部依赖是"流式结束前至少一个 chunk 在 B 加载后到达"，对跨数秒、多 chunk 的 SSE 属常见必然，故判 confirmed。

**可复现场景**：
手动触发（无需改代码）：1) 打开 /chat，在会话 A 中提问，让回答处于流式输出中（看到法典速查/扫描光动画）；2) 桌面端直接点侧栏历史会话 B（移动端点 ☰ 后点 B）；3) 观察：B 加载完成后，其最后一条消息被 A 的流式文本逐帧覆盖（污染显示）；4) 等流式结束后输入新问题并发送——由于 onMeta 已把 conversationId/activeId 改回 A，该提问被发进会话 A 而非当前显示的 B。代码路径：chat/page.tsx 475 doSend→487 streamChat→494 chunk 回调 / 502 meta 回调；api.ts:101 streamChat 的 reader 循环 136-161。

**修复建议**：
两处配合修复，均位于 frontend/app/chat/page.tsx：(A) 增加流式会话失效令牌——在 195 行 streaming state 旁加 `const streamTokenRef = useRef(0)`；doSend 内 `await streamChat` 前取 `const tok = ++streamTokenRef.current`，chunk(494)/onMeta(502)/error(516)/steps(523) 四个回调首行加 `if (tok !== streamTokenRef.current) return;`；并把 `setStreaming(false)` 放入 `finally` 兜底。selectConv(298) 首行、newChat(287) 首行、deleteConv(321) 首行各加 `streamTokenRef.current++`（并 `if (streaming) setStreaming(false)`）使在途回调全部失效，杜绝向新会话数组写入旧流内容与 conversationId 回改。(B) 交互层拦截——侧栏历史项 onClick(page.tsx:693) 改为 `onClick={() => { if (!streaming) void selectConv(h); }}`，新对话按钮(682) 加 `disabled={streaming}`，从入口阻断流式期切换。若后端可改，最优解是给 streamChat 增加 AbortSignal 参数并在 api.ts:140 `reader.read()` 循环内检测 `signal.aborted` 提前 break，从源头终止在途 SSE。

---

## 14. [MEDIUM] token 过期（401）无统一处理：不重登不跳转，会话静默失效

- **位置**：verify:frontend/lib/api.ts:36　**类别**：frontend　**验证**：confirmed

**根因 / 证据链**：
代码证据完整，审计 agent 的每条推断都可核对为真：(1) lib/api.ts:36-46 `request()` 对非 2xx 仅 `throw new ApiError(res.status, detail)`，无任何 `res.status===401` 分支；全 frontend 源码 grep "401" 零命中，无 middleware（frontend 无 middleware.*）、无 fetch 拦截器、无全局跳转。(2) lib/auth.tsx:33-44 AuthProvider 只在挂载时校验一次 `/api/auth/me`；token 中途失效后 `user` state 仍非 null，admin/page.tsx:147-152 与 chat/page.tsx:240-244 的 `router.replace("/login")` 守卫只在 `user` 变 null 时触发，因此会话内 401 永不触发跳转。(3) admin/page.tsx:175-177 `loaders[section]().catch(()=>{})` 完全吞掉 401，setStats/setUsers 等不执行，区块渲染为误导性空态（admin/page.tsx:486 "暂无用户"、:802 "暂无对话记录"），与声称一致。(4) chat/page.tsx:516-522 onError 把 `出错了：${err}` 写入最后一条消息，对应 401 时 api.ts:124-133 的 "请求失败（HTTP 401）"。(5) 后端 auth.py:14/45（7 天过期）与 auth.py:56-62（过期/禁用用户一律 401）证明触发条件真实可达。无前置校验/守卫覆盖此路径，锚点行号均准确。唯一弱化点是实际触发需 token 在 SPA 保持挂载期间过期（≥7 天不刷新，或管理员中途禁用该用户），故属 medium 而非 high——这与"会话静默失效、无任何引导"的失败场景完全吻合。

**可复现场景**：
(1) 保持 /admin 或 /chat 页面打开且不刷新；把 localStorage 的 alh_token 改成已过期/伪造值（或后端 TOKEN_EXPIRE_DAYS 临时调小），或在后端把该登录用户 is_active 置 false。(2) 在 admin 页切换区块或点击"应用切换"，在 chat 页发送问题或加载历史。(3) 预期观察：admin 各区块显示空态/加载态且无报错、不跳 /login（因 user state 未变 null）；chat 最后一条消息显示"出错了：请求失败（HTTP 401）"或后端 detail"令牌无效或已过期"。(4) 手动刷新后，挂载时 /api/auth/me 401 → setToken(null) → 跳 /login，即"必须手动刷新才能重新登录"。

**修复建议**：
在 lib/api.ts 加统一 401 拦截并让 request()/streamChat 复用它：(a) 新增 `function handleUnauthorized(){ setToken(null); if (typeof window!=="undefined" && !location.pathname.startsWith("/login")) window.location.replace("/login"); }`；(b) request() 在 api.ts:36 的 `if (!res.ok)` 内、throw 之前加 `if (res.status===401) handleUnauthorized();`；(c) streamChat 非 ok 分支 api.ts:124 处同样加 `if (res.status===401) handleUnauthorized();`（注意 /api/auth/login 本身 401 是正常登录失败，可在 handleUnauthorized 或调用点按 path 排除）。这样 admin loaders 的 catch(()=>{}) 与 chat onError 无需逐个改也能自动清 token 并强制重登；可选加固：移除 admin/page.tsx:176 的静默吞错，改在 UI 层展示错误 toast，避免误导性空态。

---

## 15. [MEDIUM] 法条标注 gap 正则 `\s` 含换行，与『跨句（含\n）断开续接』设计意图矛盾 → 换行后的独立条号误归属上一书名

- **位置**：verify:frontend/lib/annotate.ts:83　**类别**：correctness　**验证**：confirmed

**根因 / 证据链**：
代码证据充分。1) annotate.ts:83 的 gap 正则 `/^(?:[、，,、\s]|（[^（）]*）|\([^()]*\))*$/` 中 `\s` 在 JS 里匹配 \n/\r/ / ，实测 `test("\n")===true`；对 `《民法典》第五百八十五条\n第一百一十六条` 跑完整 annotate 逻辑，第二条被判为 `data-source="民法典"` 的 law-ref。2) annotate.ts:62-65 注释明说「跨句（。！？\n）…一律不标注并断开书名延续」，且后端 output_normalize.py:50 用 `re.split(r"(?<=[。！？!?\n])")` 按 \n 断句并在每句重置 last（output_normalize.py:51,60），`expand_citations` 对换行后的独立条号同样不补书名——证明「\n 断开」是系统级真实意图，前端 \s 与之矛盾，非陈旧注释。3) 无前置守卫：流式路径只做 money_normalize（rag_chain.py:215），expand_citations 仅在异步写库 _post（main.py:592）运行；且 expand_citations 对换行后的独立条号故意不展开，故流式与历史回放两条路径文本都保留换行后的独立条号。4) 点击链 page.tsx:578 `lawApi.detail(src, article)` 会用误归的书名查法条，产生错误法条卡。审计 agent 的 file:line 锚点与推断均正确，只是未提及后端 expand_citations 进一步坐实设计意图。

**可复现场景**：
触发条件：LLM 回答中出现形如 `《民法典》第五百八十五条\n第一百一十六条` 的文本（两个条号各占一行、行间无句末标点、非列表项）。路径：前端 renderAnswer(content)（page.tsx:179）→ annotate（annotate.ts:50）→ LAW 全局正则（annotate.ts:67-68）先命中《民法典》第五百八十五条记 lastBook=民法典、lastLawEnd（annotate.ts:76-77），再命中独立第一百一十六条，gap=tmp.slice(lastLawEnd,offset)="\n"，annotate.ts:83 的 `\s` 使 test 通过（可 node -e 直接验证）→ 标注成 `data-source="民法典"`（annotate.ts:85）。点击该 span → toggleInlineLaw（page.tsx:587）→ fetchLawRefCached（page.tsx:566）→ lawApi.detail('民法典','第一百一十六条')（page.tsx:578），若 LLM 本意是别的法/合同条款则返回错误法条卡。单元复现：node 脚本对 annotate("《民法典》第五百八十五条\n第一百一十六条") 断言 第一百一十六条 不应产生 law-ref span，当前必失败。

**修复建议**：
annotate.ts:83 将 gap 正则中的 `\s` 改为不含换行的水平空白集，使 \n/\r/ /  真正断开书名延续。改后：`/^(?:[、，,、 \t　]|（[^（）]*）|\([^()]*\))*$/.test(gap)`（JS 无字符集差集，`[^\S\r\n  ]` 亦可表达"除换行外的空白"；或最直白：在 83 行前加 `if (/[\n\r  ]/.test(gap)) { lastBook=""; lastLawEnd=-1; return full; }`）。该改动与注释意图（62-65）及后端 expand_citations（output_normalize.py:50 按 `(?<=[。！？!?\n])` 断句重置 last）对齐；不影响同句合法续接如「《民法典》第715条、第716条」（gap 为顿号）。注意不要动 annotate.ts:67 的 LAW 正则里的 `第\s*`——那是条号内间距，与本次修复无关。

---

## 16. [MEDIUM] 合同模式无退出机制且追问被拼进合同文本重新切条款，污染证据块、误路由无关问题

- **位置**：verify:backend/main.py:463　**类别**：contract　**验证**：confirmed

**根因 / 证据链**：
代码证据充分，两处核心断言均成立，但有一处需修正。

①无退出机制（成立）：_contract_convs（main.py:335）全文件只有 main.py:442 一处 `.add`，Grep 证实无任何 remove/clear/discard/pop——会话一旦进入合同模式即永久生效（内存集，重启才清）。main.py:413-417 的 contract_mode 只要 `intent=="legal_query" and conv.id in _contract_convs` 即强制合同路径，不再校验当前问题是否合同相关。对"离婚冷静期是多久？"，classify_intent（intent.py:55-63）返回 "legal_query"（"离婚"命中 _LEGAL_MARK，非 chitchat/study/cheating），is_contract_review 为 False，于是走 main.py:449-463 追问分支：把当前问题拼进旧合同文本，用旧合同证据块 + SYSTEM_CONTRACT_FOLLOWUP（prompts.py:136-141）"合同追问"框架作答，且本次不检索与问题相关的法条（docs 全部来自旧合同条款 supplement）。误路由成立。

②证据污染（成立）：main.py:463 `contract_text = prev + "\n" + 当前问题`，main.py:464 build_contract_data → contract_split 重新切分。domain_rules.py:169-173 的 _CONTRACT_SPLIT_MARK 匹配行首"第[一二三四五六七八九十百千零〇0-9]+条"；追问"第三条的违约金比例是否过高？"以"第三条"开头位于独立行，被切成新条款块（_CONTRACT_LABEL_RE 标签"第三条"，含"违约金"命中风险词 mid）。该块进入 main.py:346-351 evidence_block，即用户自己的提问文本被当作"合同（分条款）"条款呈现给模型。锚点 main.py:463 准确。

修正：审计 agent 的"答非所问"表述夸大——追问分支 user_content 显式含"用户追问：{user_text}"（main.py:366-370），模型能看到真实问题，不会答成另一问题；真实危害是误路由（无对应法条检索、上下文被旧合同证据占据、SYSTEM_CONTRACT_FOLLOWUP 把无关问题框定为合同追问）导致答案质量下降，而非字面"答非所问"。severity=medium 合理。

**可复现场景**：
POST {host}/chat，两次调用（同一 conversation_id）：
① 首轮 text=一份含多条款的合同全文（含"第三条...违约金..."，长度>80 字，需触发 is_contract_review，如"帮我审查这份合同：第一条...第三条...违约金..."），得到完整评估报告；服务端 _contract_convs.add(conv.id)。
② 追问 text="第三条的违约金比例是否过高？"，携带同一 conversation_id。后端：intent=legal_query、is_contract_review=False、conv.id 在 _contract_convs → contract_mode=True → 追问分支（main.py:449-463），contract_text=旧合同全文+"\n"+该追问；build_contract_data 重新 contract_split，追问因行首"第三条"命中 _CONTRACT_SPLIT_MARK 成为独立条款块，进入 _contract_messages 的 evidence_block（main.py:346-351）→ SSE 流中模型上下文含"【合同（分条款）】... [N. 第三条] 风险标签：违约金\n第三条的违约金比例是否过高？..."。
另：改为追问"离婚冷静期是多久？"再走一轮，可见仍走合同路径（不检索离婚相关法条、旧合同证据入上下文、SYSTEM_CONTRACT_FOLLOWUP 框架）。

**修复建议**：
两处最小修复：

1. 追问问题文本不得拼进合同全文（修证据污染，main.py:463）：追问分支 `contract_text = prev.strip() if prev else (text or raw_query)`——build_contract_data 只基于旧合同文本，当前问题改由 _contract_messages 的"用户追问"字段单独携带（该字段已存在，main.py:368），避免问题被 contract_split 切成条款块。

2. 增加退出/守卫机制（修无退出，main.py:413-417 + 449-463）：追问分支入口先判相关性——若 `not is_contract_review(text or raw_query)` 且当前问题不含合同指代（如无"合同/条款/第X条/上述/它/违约金"等），则 `_contract_convs.discard(conv.id)` 并回落到普通检索分支（else 分支 main.py:471-485，走 retrieve/retrieve_exam），让无关法律问题恢复正常路由。同时把 exit 条件复用进 contract_mode 判定，避免已 discard 后仍被 conv.id 拉回。

建议补一条回归测试：合同评估后接无关法律问题断言不再走 contract_data 分支、evidence 不含用户提问文本。

---

## 17. [MEDIUM] 合同评估流式分支不扣配额、失败不 mark_depleted、重试绕开模型队列固定回退默认 omni

- **位置**：verify:backend/main.py:1137　**类别**：contract　**验证**：confirmed

**根因 / 证据链**：
三条核心主张全部在代码中成立。(1) 不扣配额：合同分支 main.py:1103-1178 全程无 registry.deduct；全后端 deduct 调用点仅 main.py:878(语音)、1192(轻量分支)、1321(主旗舰分支)，合同路径在 1178 行 return，均不可达；log_account 只写日志(observability.py:103-107)。主分支 1319-1321 明确 `registry.deduct(flag_key, est * thinking_mult)` 而合同分支零 deduct。(2) 失败不 mark_depleted：main.py:1140 `on_model_failure=lambda _e: None` 是空实现；stream_with_retry(rag_chain.py:224-228) 对前 N-1 个 config 的任何异常都会调用该回调，空实现导致坏模型永不被 mark_depleted(llm_registry.py:324-335)，其 unavailable 不变(llm_registry.py:105/111)，pick()(llm_registry.py:268-275) 每次合同请求仍选中同一坏模型——对比主分支 main.py:1230-1234。(3) 重试固定回退默认 omni：main.py:1137 `registry.variant(True)`(llm_registry.py:216-222) 从 _default_entry() 即 DEFAULT_KEY="vision_flag"(llm_registry.py:78, qwen3.5-omni-plus, line 56) 重建，不看配额/不看 unavailable/不重新 pick 队列，且忽略 _d 参数（configs[2]=(False,0.5) 也被强制关思考）——主分支用 _safe_pick 重新落后备(main.py:1214-1228)。后果链成立：quota_left=total-initial-runtime(llm_registry.py:340)，不扣减→runtime_used 低估→quota_left 高估→低于 5% 阈值切换延迟；坏模型不标记→持续误导路由。审计 agent 行号锚点全部准确。唯一小瑕疵：'重复 2 次 omni 兜底调用后才失败'，实际 omni 正常时 1 次兜底即可成功，2 次后才失败需 omni 也坏，不影响结论。

**可复现场景**：
(1) 不扣配额：生产(use_router 开)下上传/粘贴合同触发 is_contract_review→contract_data(main.py:416,464)→进入分支0.3(main.py:1103)。调 /api/admin/llm-quota 或读 quota_store 记 flag 模型 runtime_used，发一次长合同请求后该值不变（对比主分支 1319-1321 会扣）。(2) 失败不 mark_depleted：把 flag 模型(llm_registry.py:56) 的 cfg model 改成不存在的 id 或置 quota 耗尽后重启，发合同请求→configs[0] flag_llm astream 抛错→main.py:1140 空回调→不 mark_depleted→i=1/2 用 registry.variant(True)=vision_flag omni 兜底。之后每次合同请求 _safe_pick(main.py:1032→llm_registry.py:260-276) 仍选中同一坏模型，直到 omni 也失败才在 rag_chain.py:229 上抛。

**修复建议**：
三处修改均在 main.py 合同分支：(1) 在 main.py:1146-1156 之间（routing_metrics.record/log_account 附近）补扣减，与主分支 1319-1321 同构：`if use_router and flag_key and answer: est = estimate_tokens(answer) + estimate_tokens(pre.get('context','') + pre.get('user_text','')); registry.deduct(flag_key, est * registry.thinking_mult(flag_key))`。(2) main.py:1140 把 `on_model_failure=lambda _e: None` 换成仿 1230-1234 的处理器，如 `def _cf(_e): if use_router and flag_key: registry.mark_depleted(flag_key, 'model_failure')`，让坏模型即时失效落后备。(3) main.py:1137 重试 lambda 改为 i>0 时重新 pick 落后备并尊重 _d：`def _fn(_i, disabled): if use_router and _i > 0: key, llm, _ = _safe_pick(modality, tier or 'flag'); return make_chain(registry.variant_of(key, disabled) if disabled else llm); return make_chain(flag_llm)`（替换 registry.variant(True) 固定回退 omni 的逻辑）。

---

## 18. [MEDIUM] 用户提问原文（前 200 字）被写入结构化日志（multi_incomplete 的 detail 字段）

- **位置**：verify:backend/main.py:1283　**类别**：privacy　**验证**：confirmed

**根因 / 证据链**：
代码证据充分，漏洞真实成立。(1) 数据源：main.py:525 `user_text=text or ""`，text 为未经任何脱敏的原始用户提问。(2) 触发判定：main.py:1261 `multi_bad = bool(answer) and quality.multi_incomplete(pre.get("user_text") or "", answer)`；quality.py:81-90 中 question_type==\"multi\" 的关键词匹配（query_understand.py:228 含“哪些/正确的有/符合的有”）范围很宽，普通咨询题如“我需要收集哪些证据”也会命中，并非仅限正式法考题。(3) 落盘：main.py:1279-1284 `log_account(kind=\"multi_incomplete\", ..., detail=(pre.get(\"user_text\") or \"\")[:200])` → observability.py:103-107 经 extra 透传 → observability.py:18-21 `_ACCOUNT_FIELDS` 含 detail → observability.py:24-39 `_JsonFormatter` 将 detail 明文序列化进 legal.chat JSON 日志，走 StreamHandler(stdout)（observability.py:44），无任何 mask/脱敏/redact（全仓库 grep 零命中）。(4) 反驳关键点：主路径记账 main.py:1326-1336 刻意只记 q_len 长度而不记原文，说明“原文不进日志”是既有最小化约定，本分支是例外泄露，非正常设计。(5) 无前置守卫/异常分支可阻断该路径。审计 agent 的推断正确：触发后用户提问前 200 字原文永久进入结构化日志，供审计/运维明文读取，违反最小化采集。

**可复现场景**：
启动后端后向聊天 SSE 端点（chat 流式接口，main.py 中该函数所在路由）POST 一条含多选关键词与个人事实的提问，例如“我 2022 年与张某登记结婚，婚后共同购房，现拟离婚。以下哪些属于夫妻共同财产？A.婚后所购房产 B.婚前个人存款 C.婚后奖金 D.继承所得遗产”，并让模型回答只坚定声明 1 个正确项（如“应选 A”）。此时 quality.multi_incomplete 返回 True（题干含“哪些”→multi，option_count>=2，答案仅 1 项），main.py:1279-1284 触发 log_account(kind=\"multi_incomplete\", detail=提问前 200 字)。随后在进程 stdout / 采集到的日志流中搜索 legal.chat 行，可见 `\"kind\":\"multi_incomplete\"` 且 `\"detail\":\"我 2022 年与张某登记结婚……\"` 明文。也可直接读 main.py:1283 确认该行。

**修复建议**：
main.py:1279-1284：删除 log_account 调用中的 `detail=(pre.get(\"user_text\") or \"\")[:200]` 参数。kind=\"multi_incomplete\" 已表达触发原因，detail 无必要保留原文；如需留痕诊断，改为非敏感摘要（如 `detail=f\"q_len={len(text)}\"` 或 option_count/declared 计数）。同时可在 observability.py:18-21 将 _ACCOUNT_FIELDS 中的 \"detail\" 字段改为仅接受白名单/非自由文本，或在 _JsonFormatter 中对 detail 值做关键词/长度归一化，作为纵深防御，防止未来再次经 log_account 把用户原文带入日志。

---

## 19. [MEDIUM] search_qa 在本地 L2 qa_pairs 上取 k=1 的欧氏最近邻再算余弦，候选选错导致命中丢失/注入错误 QA

- **位置**：verify:backend/knowledge_service.py:254　**类别**：retrieval　**验证**：refuted

**根因 / 证据链**：
审计 agent 找对了一半事实、推错了关键因果。(1) L2 空间判断正确：chroma_db/chroma.sqlite3 的 collection_metadata 表中 qa_pairs 无任何 hnsw:space 记录（meta={}），而 legal_provisions_cos/te4、qa_pairs_te4 均为 cosine，故 retrieval_core.py:31 `(meta.get('hnsw:space') or 'l2')` 判为 L2 属实；knowledge_service.py:254 用 k=1、257-265 仅对该单候选重嵌算余弦也属实。(2) 但核心前提「BGE 向量未归一 → 欧氏最近邻≠余弦最近邻」被实测否定：`_qa_store._collection.get(include=['embeddings'])` 读出的全部 223 条 qa_pairs 存储向量范数均为 1.000000，且同一 embeddings 对象（rag_chain.py:38-41 + 104 的 QuotaTrackingEmbeddings 包装）的查询向量范数也是 1.0——BGE-base-zh-v1.5 经项目 HuggingFaceEmbeddings 输出即为 L2 归一化向量。对单位向量 ‖a−b‖²=2−2cos(a,b)，L2 最小 ⇔ 余弦最大，排序完全一致，因此 L2 空间 k=1 选出的就是余弦最近邻，候选声称的「E 余弦 0.94 却被 L2 更近的 F（余弦 0.66）顶掉」在数学上不可能发生：若 E 余弦更高则 E 的 L2 距离必然更小。所谓「命中丢失」与「错误注入无关答案」（main.py:306-309 注入路径属实，但 search_qa 返回的候选是正确的）两种危害场景均不成立。HNSW 近似检索的召回误差是向量库通用属性，非本候选所声称的度量失配机制。

**可复现场景**：
复现路径即否定路径：(1) sqlite3 查 collection_metadata：qa_pairs（id=a09bd7c3）无 hnsw:space 记录 → is_cosine_space 返回 False（确认 L2，但这是预期设计，非缺陷）。(2) 用项目 venv 运行：from knowledge_service import _qa_store; d=_qa_store._collection.get(include=['embeddings'], limit=300)；计算全部范数，结果均为 1.0——证明存储向量已归一。(3) 按候选场景构造 Q（E 的同义改写，与 E 余弦 0.94、与无关项 F 余弦 0.66）：由于所有向量单位化，F 不可能成为 L2 最近邻而 E 不是；调用 search_qa(Q) 会返回 E（score≈0.94），而非 None 或 F。即候选的触发条件在当前代码与数据下无法满足。

**修复建议**：
当前行为正确，无需必修；但代码对「嵌入向量非归一化」脆弱，若未来切换 embedding provider（如 aliyun text-embedding-v4，norm 未必为 1）会重新引入该缺陷。防御性加固建议：(1) knowledge_service.py:254 将 k=1 改为 k=16 取大池，257-265 非 cosine 分支改为对池内所有候选重嵌算余弦后取最大值（score=max cos）再与 threshold 比较——即使向量非归一也能选出余弦最优；(2) 更彻底：在 qa_pairs 创建时传 collection_metadata={"hnsw:space":"cosine"}（与 legal_provisions_cos 一致，参见 scripts/rebuild_embeddings.py:95 的做法），使 knowledge_service.py:257 走 `1.0-dist` 快路径且语义统一；新库已由 qa_pairs_te4（cosine）覆盖，本地 qa_pairs 如需可随 rebuild 脚本一并重建。

---

## 20. [MEDIUM] 轻量升级路径配额错位：被拒的轻量模型 token 全部记到旗舰 key，轻量模型从不计费

- **位置**：verify:backend/main.py:1192　**类别**：quota　**验证**：likely

**根因 / 证据链**：
审计 agent 对记账的推断在代码层完全正确：main.py:810 升级路径 `return _LightResult(fraw, fkey, modality, "flag", usage + fusage, True, "pass")` 中 res.key=fkey、res.usage=usage+fusage（轻量+旗舰 token 之和）；main.py:1191-1192 `if res.key: registry.deduct(res.key, res.usage)` 把两模型 token 全部记到旗舰 key；轻量 lkey 在升级路径中从不被扣减（main.py 内全部 deduct 仅 878/1192/1321 三处，升级路径只走 1192）。对比未升级路径 main.py:797/802/804 均正确返回 lkey+usage，可见记账意图是"谁烧记谁"，升级路径是与该意图不一致的缺陷。锚点 810/1192 行号准确。但审计 agent 漏掉了一个关键前置门：main.py:1009 `use_light = use_router and tier=="light" and modality=="text" and registry.has_role("text","light")`——而 DEFAULT_ROLES（llm_registry.py:37-67，27 个条目）全部为 tier "flag"，无任何 light 档模型；backend/.env 也未设置 LLM_MODELS_JSON（settings.py:35 默认空串）。因此 registry.has_role("text","light")=False，整个轻量路径（含 810 升级分支）在当前提交配置下被门禁关闭，属于潜伏缺陷。系统设计意图明确要跑轻量档（llm_registry.py:4 文档明示"轻量 deepseek-r1-distill-qwen-7b"、complexity.py 路由到 light、tests/test_tiering.py 用独立的 L/F 两档 mock 实测升级状态机），一旦通过 LLM_MODELS_JSON 配置轻量模型（或有人补 DEFAULT_ROLES），缺陷即实际触发。故判 likely（代码证据充分、真实性成立，但当前部署态触发依赖外部配置）。

**可复现场景**：
1) 先让轻量路径可用：在 backend/.env 设 LLM_MODELS_JSON（含一个 tier="light" 的 text 模型），或直接往 llm_registry.py DEFAULT_ROLES 加一条 {"key":"text_light","tier":"light",...}，重启后端使 registry.has_role("text","light")=True（main.py:1009 门放开）。2) 发一条被 complexity.assess 判为 light、且命中检索的 text 请求（main.py:1000-1009），使 _light_buffered_locked 先轻量 invoke（main.py:792-794，usage>0）→ quality.self_check 返回 not ok（main.py:795-796）→ 走升级（main.py:799-810）→ 旗舰自检 ok 命中 main.py:810。3) 触发后调 GET /api/admin/llm-quota 或 registry.status()（llm_registry.py:352-369）：可见旗舰 key 的 quota_left 一次掉 usage+fusage，轻量 key 的 quota_left 完全不变——轻量实际烧的 token 从未扣减。4) 也可直接跑 tests/test_tiering.py（其 _patch_pick 已模拟 L/F 两档，deduct 被 mock 为空所以测不出记账问题，需给 deduct 打桩断言扣减对象）。

**修复建议**：
在 main.py:790 的 _light_buffered_locked 内，升级分支（main.py:810-811）返回前先按"谁烧记谁"拆分：轻量探针已真实烧掉 usage token，应立即 `registry.deduct(lkey, usage)`（lkey 即函数参数，天然在作用域内；deduct 在 llm_registry.py:278 为线程安全、tokens<=0 忽略，重复调用安全），并把返回值从 `usage + fusage` 改为仅 `fusage`：`return _LightResult(fraw, fkey, modality, "flag", fusage, True, "pass")` 与 `_LightResult((fraw+NOTE_COMPLEX) if fraw else "", fkey, modality, "flag", fusage, True, fv.reason)`。这样调用方 main.py:1192 只对旗舰扣 fusage，轻量 lkey 扣到自己的 usage，看门狗（llm_registry.py:104-115 below_threshold/unavailable 及 main.py:1197 token_est 日志）与真实消耗对齐。未升级路径 main.py:797/802/804 无需改动（已正确记 lkey）。若不想改动函数返回值语义，也可改为在 _LightResult 增加第二个可选的 (extra_key, extra_usage) 字段由 1192 处一并扣减，但单函数内 deduct 更简。改后跑 tests/test_tiering.py 与 test_routing.py 回归（需给 deduct 加断言覆盖升级记账）。

---

## 21. [LOW] /api/feedback 未校验 conversation_id 归属，可伪造他人会话反馈并灌入受控沉淀待审队列

- **位置**：verify:backend/main.py:1705　**类别**：broken-access-control　**验证**：confirmed

**根因 / 证据链**：
代码证据充分。main.py:1705 post_feedback 直接写 `conversation_id=body.conversation_id`，全程无 `db.get(Conversation,...).user_id == user.id` 归属校验；而同文件会话接口 main.py:1404/1420/1430 均有该守卫，确认此端点遗漏。main.py:1715-1717 对 down/correction 无条件 `ks.create_candidate(db, body.question, propose, 0.0, "feedback:...")`，knowledge_service.py:282-305 中 0.0 < AUTO_CURATE_THRESHOLD(=0.89, knowledge_service.py:279) 必进 status=pending 待审队列且无去重。限流方面：limiter = Limiter(key_func=get_remote_address)（main.py:124）未设 default_limits，post_feedback 无 @limiter.limit 装饰器（对比 main.py:223/1546/1650 均有），批量提交无速率阻碍。Feedback.conversation_id 有 ForeignKey（models.py:100）：提交不存在的 ID 会 500，但提交他人名下已存在的会话 ID 可通过 FK 被接受，伪造他人会话归属成立。审计 agent 的推断（缺失归属校验、无条件入候选、污染 /api/admin/feedback 即 main.py:1721-1736）均正确；唯一未提的细节是 FK 使"任意不存在 conversation_id"会报 500 而非成功，但不影响利用。

**可复现场景**：
1) 以任意普通用户登录拿到 JWT。2) 以另一用户（或自己）名下任意已存在的 conversation_id 为目标（整型会话 ID 可枚举/猜测，会话列表接口不校验他人归属之外的 ID 分布）。3) 直接 POST /api/feedback，Authorization: Bearer <token>，body 形如 {"conversation_id": <他人会话ID>, "question": "<任意文本>", "answer": "<任意文本>", "rating": "down", "correction": "<任意文本>"}——绕过前端，curl 即可。4) 循环执行该请求（端点无限流）：每次插入一条 Feedback（main.py:1711）+ 一条 status=pending 的 QaCandidate（knowledge_service.py:299-304），灌爆待审队列、污染管理员 /api/admin/feedback 列表并抬高 /api/admin/stats 的 qa_pending。5) 管理员若误采纳灌入的纠错候选，其内容进入 qa_pairs 影响后续用户检索。

**修复建议**：
main.py:1701-1718：在 db.add(fb) 前增加会话归属校验——若 body.conversation_id 非空则 `conv = db.get(Conversation, body.conversation_id); if not conv or conv.user_id != user.id: raise HTTPException(status_code=404, detail="会话不存在")`（与 main.py:1404 同一守卫模式）。同时为 post_feedback 加上 `@limiter.limit("10/minute")`（参照 main.py:1546 风格），封堵无差别灌队列。可选加固：knowledge_service.create_candidate（knowledge_service.py:282-305）对 (question, answer) 做去重或对单用户每日 pending 提交设上限，避免待审队列被批量污染。另建议为 Feedback.conversation_id 的 FK 违约补异常处理，避免不存在的 conversation_id 抛 500。

---

## 22. [LOW] rerank 配额监控关闭（rerank_quota_total=0 默认）时失败模型无记忆，每个请求都对坏模型重试一次网络往返

- **位置**：verify:backend/retrieval.py:140　**类别**：robustness　**验证**：confirmed

**根因 / 证据链**：
代码证据充分，链路逐环可证。(1) retrieval.py:138-141 真实 API 失败后仅调 quota_utils.mark_utility_depleted(model) 并 continue；(2) quota_utils.py:94-96 mark_utility_depleted 在 `total <= 0` 时直接 return——total 来自 utility_quota_total_for(name)（quota_utils.py:41-58），当 rerank_quota_totals 为空且 rerank_quota_total 默认 0（settings.py:56）时，三个队列模型 total 全为 0，标记必为 no-op；(3) 同时 utility_pct_left 在 total<=0 时返回 1.0（quota_utils.py:80-81），故 retrieval.py:94-95 的 utility_quota_ok 守卫恒 True，坏模型永不被跳过。因此「失败→记忆→下次跳过」的机制（docstring retrieval.py:81-82 明示的设计契约）在默认配额关闭配置下整体失效。全库 grep（circuit/cooldown/blacklist/depleted）确认无其他熔断或内存记忆，仅此配额机制一条；测试 test_rerank_docs_switches_model_on_failure（tests/test_retrieval_rerank.py:140-180）也刻意把 rerank_quota_totals 设为 "100,100" 才验证成功，反证配额关闭时该路径不被覆盖。额外佐证：quota_utils.py:113-114 rerank_active_model 在配额全关时恒返回 models[0]，管理端 rerank_degraded 也永远不亮（main.py:185），连状态展示都无法暴露坏模型。审计 agent 两处小偏差：①「重启也不恢复」表述不准——配额关闭时本就从未记忆，无所谓恢复；②「~90s」是网络挂起的最坏情形（三个 30s timeout，retrieval.py:48/109），4xx 快速失败时仅多几次往返。但核心断言（坏模型无记忆、每新查询重试）与代码完全一致。严重度 low 恰当：最终仍回退本地余弦精排（retrieval.py:594-596），不产生错误答案，仅空耗网络往返与延迟，且需 rerank_enabled=True 才触发。

**可复现场景**：
触发条件：RERANK_ENABLED=true、RERANK_API_KEY 配错或某模型名/key 失效，且不配 RERANK_QUOTA_TOTAL（默认 0）与 RERANK_QUOTA_TOTALS（默认空）。复现：python -c 直接调 retrieval._rerank_docs("某问题", [doc1, doc2])，前置把 settings.rerank_enabled=True、rerank_api_key 设为无效；观察循环对 qwen3-rerank 发 httpx.post/client.post（retrieval.py:100/114），失败进入 except（:138）调 mark_utility_depleted 后 continue；用两个不同 query 调两次（避免 hybrid_retrieve 结果缓存 :608 命中），第二次仍对同一坏模型发起网络请求——quota_store.get_used(model) 始终为 0（标记从未落库），utility_quota_ok 恒 True（quota_utils.py:88）。对照：把 RERANK_QUOTA_TOTALS 配成 "100000,100000,100000" 后再跑，第二次调用即跳过已标记模型，可复现差异。

**修复建议**：
把「失败记忆」与「配额监控」解耦，加进程内失败黑名单（独立于 quota 机制），两个方案二选一或叠加：(方案A，推荐) retrieval.py 顶层加模块级 `_failed_rerank_models: dict[str, float] = {}` 及 TTL 常量（如 `_FAIL_COOLDOWN = 300`，可用新 settings 项 rerank_fail_cooldown_secs）；在 _rerank_docs 循环体（retrieval.py:93-95）之前先 `if model in _failed_rerank_models and time.monotonic() < _failed_rerank_models[model]: continue`；在 :140 except 分支旁追加 `_failed_rerank_models[model] = time.monotonic() + _FAIL_COOLDOWN`（保留原 mark_utility_depleted，配额开启时仍双写）。该改法不依赖 total>0，默认配置下同样生效。(方案B) quota_utils 层：模块级 `_failed: set[str]`，mark_utility_depleted（:91）在 total<=0 时也记入 _failed，utility_quota_ok（:86-88）先判 `if name in _failed: return False`——一处修复同时惠及 rerank_active_model（:101-121）与主流程，但需注意 main.py:182-185 状态语义。二者皆不改默认行为、不影响配额开启场景，仅补上配额关闭时的失败记忆。

---
