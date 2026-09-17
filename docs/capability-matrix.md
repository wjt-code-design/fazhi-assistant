# 产品能力矩阵（LongCat + 百炼全模态，2026-09-05 实测）

阶段 B 交付物。每行 = 产品能力 → 调用入口 → provider/model → 验证结果与证据。
状态只有三种：**PASS**（有真实验证证据）、**DISABLED**（显式停用、前后端一致）、**BLOCKED**（有阻断未解决）。
"代码检查"指静态读码 + 既有单测覆盖；"实测"指对本候选真实调用取证。

## 0. 模型与 Provider 注册表（部署态，`LLM_MODELS_JSON` + provider 分支）

| 角色 | provider | base_url | model | modality | 验证 |
|---|---|---|---|---|---|
| `longcat_text_flag` | longcat-openai-compatible | `https://api.longcat.chat/openai` | `LongCat-2.0` | text | PASS（002 Existing RAG 预检 + 003 Agent 预检 + 双探针） |
| `vision_omni` | dashscope | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `qwen3.5-omni-flash` | vision | PASS（64×64 图片 REST 识别"红色"，2026-09-05） |
| `voice_omni` | dashscope | 同上 | `qwen3.5-omni-flash` | voice | PASS（REST `input_audio` 转写 0.6s wav，2026-09-05） |

**模型 ID 诚实记录**：用户最初指定 `qwen3.5-omni-flash-realtime-2026-03-15`，实测返回
`400 "current user api does not support http call"`——realtime 变体只接受 WebSocket 会话，
与本项目 REST（chat/completions + input_audio）链路不兼容。改用同系非 realtime 的
`qwen3.5-omni-flash`（价格同档：输入文本/图片 3.3 元/M tokens、输入音频 27 元/M、
输出文本 20 元/M；配额上限 100 万 tokens，用户授权 2026-09-05）。key 经
`DASHSCOPE_API_KEY` 环境变量注入（复用既有账号），不进 Git/镜像。

## 1. 文本问答（主力链路）

| 能力 | 入口 | 模型 | 状态 | 证据 |
|---|---|---|---|---|
| 普通法律问答（非流式/流式） | `/api/chat` fast path | LongCat-2.0 | PASS | 002 隔离预检 858 字回答 + 引用关键词（48.6s）；003 候选单测 769 通过 |
| 多轮会话/改写/压缩/记忆 | `registry.get()` 各辅助点 | LongCat-2.0 | PASS | 代码检查：全部纯文本调用，无协议差异面 |
| 长回答/中文标点 | 同上 | LongCat-2.0 | PASS | 002 预检输出含规范《法律名》第X条引用与中文标点 |
| 引用输出 + 引用校验 | `citation_verify` 后端确定性 | 与模型无关 | PASS | 既有门禁（smoke_citation_fast 17 项）+ 单测 |
| 复杂度路由/缓存/配额记账 | 本地确定性组件 | 无 LLM | PASS | 既有单测（test_complexity/test_answer_cache/quota_*） |
| 法考题/学习模式 | `/api/chat` study_aid | LongCat-2.0 | PASS* | 纯文本链路与主问答同构；*最终以阶段 D/J 回归为准 |
| 合同/文书分析（粘贴） | `/api/chat` contract | LongCat-2.0 | PASS* | 纯文本；*阶段 J 需端到端复核 |
| 合同文件解析 | `/api/chat/file` | 无 LLM（本地解析） | PASS | 代码检查：魔数校验+解析零 LLM |

## 2. Agent（Legal Agent V1，默认关闭，仅灰度开启）

| 能力 | 入口 | 模型 | 状态 | 证据 |
|---|---|---|---|---|
| 争点分解（strict JSON） | `LLMIssueDecomposer` | LongCat-2.0 | PASS | 003/004 预检通过；5/5 直连探测干净；残留风险见 003 STATUS 已知限制 2 |
| Planner 决策（strict JSON + tool_call） | `LLMPlannerAdapter` | LongCat-2.0 | PASS | 003/004 预检 steps 含 `tool_call retrieve_laws → TOOL_SUCCEEDED`（deb65fc 修复后真实通过） |
| 工具调用（retrieve_laws 等 4 工具） | `ToolGateway`（服务端执行） | 无 LLM | PASS | 003/004 预检 `TOOL_SUCCEEDED` + test_tool_gateway。注：本项目 Agent **不使用 provider 原生 tool calls**（planner 输出 strict JSON，工具在服务端执行），故 spec 中"finish reason/流式增量"项不适用，由 strict JSON 契约测试覆盖 |
| 起草（claims strict JSON） | `EvidenceBoundedWriter` | LongCat-2.0 | PASS | **live 探针 PASS**（2026-09-05，004 容器内真实模型起草 `DRAFT_VALIDATED`：1 claim、规范《民法典》第675条引用、0 丢弃；diag/writer_live_probe.py）+ 提示词契约测试锁定 |
| 结构化反问/恢复 | clarification + resume | LongCat-2.0 | PASS | 003/004 预检：结构化 clarification，DB 与 SSE 一致 |
| 反问预算行为 | `agent_max_clarifications=2` | — | 记录（设计行为） | 实测：冻结题两轮反问后第 3 次 resume 返回 409（预算耗尽），且第 2 问与用户补充事实语义重叠时评估器未消解——**已知行为特征**，阶段 D 采集若遇相同模式按失败行保留，阶段 J 需产品判断是否优化 |
| 确定性校验/预算/防注入 | verifier/gateway | 无 LLM | PASS | 既有单测（controller/verifier/gate/state_machine） |

## 3. 多模态（阶段 B 决策：方案 1 = 已验证 provider 按 modality 路由）

| 能力 | 入口 | 模型 | 状态 | 证据 |
|---|---|---|---|---|
| 图片理解（对话附图） | `/api/chat` image | qwen3.5-omni-flash | PASS | **端到端 PASS**（004 隔离预检：64×64 图片经 bootstrap describe→omni→回答"红色"，HTTP 200 无 error，diag/preflight-004/sse-image.txt）；合成图验证链路，合同截图质量归阶段 J |
| 图片→描述桥接（bootstrap） | `_describe_image_for_bootstrap` | vision 角色显式 pick | PASS | 代码检查 + 端到端（同上链路即经此路径）；QuotaExhausted→显式 503（门禁测试） |
| 合同截图逐字转写 | describe_image 提示词路由 | qwen3.5-omni-flash | BLOCKED | 链路同上已通；**转写质量（条款完整性）需真实合同样张专项验证**（阶段 J） |
| 语音转写（REST） | `/api/chat/transcribe` | qwen3.5-omni-flash | PASS | **端到端 PASS**（004 预检：真实 wav 上传→HTTP 200 非空转写，diag/preflight-004/transcribe.json）；探针为正弦波只断言非空，真人语音质量归阶段 J |
| LongCat 视觉/语音 | — | LongCat-2.0 | DISABLED | 实测：图片内容块被静默忽略（"我暂时无法看到"）、realtime 系拒绝 HTTP——已由 `has_modality` + 501 门 + `/api/health` 能力位显式关断，前端按能力位隐藏入口 |

## 3.1 重排序（rerank，2026-09-06 切换 SiliconFlow）

| 能力 | 入口 | 模型 | 状态 | 证据 |
|---|---|---|---|---|
| 云 rerank（检索精排） | `_rerank_docs` | SiliconFlow `BAAI/bge-reranker-v2-m3` | PASS | 真实 probe：HTTP 200，语义判别正确（诉讼时效条文 0.66 vs 无关 0.0001）；容器内生产代码路径直调排序正确；离线单测 4 项。**现役决策（数据所有者 2026-09-06）**：与 Qwen/Qwen3-Reranker-0.6B 同平台对比 probe（后者相关条文 0.99 分更锐、公开基准亦优）后仍保持 bge——理由：已全链验证、生态成熟、限流（RPM2000/TPM50万）对单 worker 部署余量 5-10 倍；Qwen3 切换仅一行配置可随时重估 |
| DashScope qwen3-rerank（旧链路） | 同上 | qwen3-rerank 系 | DISABLED | `.env` 已切 SiliconFlow（旧 key 注释保留回滚）；代码三分支保留 |
| rerank 门禁 bug | `_get_rerank_client` | — | 已修复 | 只配 SILICONFLOW_API_KEY 时旧门禁静默跳过 rerank——`925b5f6` 修复+回归测试；007 镜像构建于修复前，下一镜像生效 |

## 4. 失败路径（错误处理矩阵）

| 场景 | 行为 | 状态 | 证据 |
|---|---|---|---|
| 模态无注册模型 | 显式 `501`（能力未配置），前端隐藏入口 | PASS | test_capability_gates.py（7 项：501×2、dashscope 分支×2、describe pick×2、health 能力位×1） |
| 视觉配额耗尽 | 显式 `503`（配额不足），不静默降级为无图回答 | PASS | test_describe_image_quota_exhausted_is_explicit_503 |
| 语音配额耗尽 | 显式 `503` | PASS | 既有 transcribe except 分支 + 门禁测试 |
| 429/超时/连接失败 | ChatOpenAI `max_retries=3, timeout=120`；转写兜底 502；聊天侧既有降级提示 | PASS（代码检查） | llm_registry._build + main.py 既有 except 链 |
| malformed JSON（Agent） | fail-closed：分解器/Planner/Writer 严格校验拒绝 | PASS | 实测（002 失败样本）+ 单测 + 提示词契约测试 |
| 空 content/超长输出 | `_response_text` 非空校验；Agent max_output/预算上限 | PASS（代码检查） | runtime.py + capture protocol 上限 |
| Provider 余额不足 | 抛错→显式失败/降级提示，不静默换模型 | PASS（代码检查） | stream_with_retry on_model_failure 链 + test_quota_switch |

## 5. 禁止事项执行记录

- 未把 LongCat 的文本 PASS 扩张成"图片/语音已支持"（先实测、后按模态路由）。
- 未仅改模型名让旧协议悄悄失败（vision/voice 在无已验证 provider 期间保持显式 501）。
- `qwen3.5-omni-flash-realtime-2026-03-15` 未被假装可用（400 实测记录在案，改用非 realtime 变体）。
- key 只进 git 忽略的 `.env`，不进 Git/镜像/日志/证据。

## 6. 待办（由后续阶段关闭）

1. ~~图片/语音端到端验证~~ 已完成（004 预检，本矩阵 §3 已升级为正式 PASS）。
2. 合同截图逐字转写质量专项样张（阶段 J 合同回归一并覆盖）。
3. 阶段 D 前重测：`LLM_MODELS_JSON` 变更后文本链路回归（Candidate 冻结含双路径 smoke）。
4. 反问预算死路行为（两轮反问后 409）是否优化——阶段 J 产品决策项。

## 7. 成本与限流（2026-09-07 补位，交接 4.4.2）

> 目的：灰度上线前决策所需「成本/限流/安全裕度」一眼表。标注 TBD = 待控制台导出或
> 实测确认，不臆造数字。安全裕度口径：实际峰值/限额至少留 5x。

| 角色 | 模型 | 计费口径 | 限额 | 实测/已知峰值 | 安全裕度 | 备注 |
|---|---|---|---|---|---|---|
| 文本代 | LongCat-2.0 | RPM/TPM | **TBD**（待 LongCat 控制台导出） | 采集单 worker p50 37-50s、请求间隔≈串行 | TBD | 4096 并发放灰需先确认 |
| 视觉代 | qwen3.5-omni-flash | 输入文本/图 3.3 元/M、输入音频 27 元/M、输出 20 元/M | 配额上限 100 万 tokens（2026-09-05 确认） | 单图 REST 一次消耗极小 | 高 | key 复用既有 DASHSCOPE 账号 |
| 重排代 | BAAI/bge-reranker-v2-m3 | token 计费（q+r×pool） | RPM 2000 / TPM 50 万（控制台确认） | 单 worker 检索每问 1 次、池 12-17 条 | ~5-10x（矩阵 §3.1 记录） | 现役决策保持 |
| 嵌入代（本地） | BAAI/bge-base-zh-v1.5 | 零成本（烘焙镜像内） | 无 | 本地 CPU compute | — | 非云端 |

**灰度前必做**：补 LongCat RPM/TPM 实测值（§7 首行 TBD）；SLO 基线建议从 005-009
p50/p90 反推（文本 p50 ≤50s / p90 ≤65s、4xx/5xx ≤0.1%，灰度后冻结，见 runbooks/deployment-v1.md）。
