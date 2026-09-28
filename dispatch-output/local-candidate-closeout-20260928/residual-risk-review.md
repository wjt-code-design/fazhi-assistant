# 剩余依赖风险复核（执行中，未获风险接受）

日期：2026-09-28。对象：`aec8d5c` 的应用调用面及两项升级提案。
原始基线 `audit-baseline.json`：138 条记录、10 个命中包；ID/别名归并为 74 组。下表是其中非 pypdf/Starlette 的 47 条记录，归并后 26 组通报；**候选安装与最终扫描尚未完成，不把此数当升级后实测**。

每项的全部 ID、别名和审计库给出的修复版本保留在 `audit-baseline-summary.json` / 原始 JSON。修复版本只能作为选型线索，不证明新依赖集合兼容。没有 fix_versions 也不等于永久无补丁。

共同状态：**未接受、未忽略、未解除**。复审最迟日期为 2026-10-05，若提前发布、启用新入口或收到新公告则立即复审。助手的静态分析不是 Owner 签字；下面“未发现调用”不是“不可能可达”。

| CVE（别名见 JSON） | 组件与触发条件 | 当前应用证据与限制 | 后续处置方向 |
|---|---|---|---|
| CVE-2024-2965 | LangChain/Community：SitemapLoader 循环 sitemap | 应用导入面未发现该 loader；不接受外部 sitemap 配置 | 在 LangChain 分案核实传递调用；避免新增该入口 |
| CVE-2024-3095 | Community：WebResearchRetriever 任意地址请求 | 应用未发现该 retriever；当前检索为本地 Chroma | 迁移分案，维持无网页抓取入口 |
| CVE-2024-5998 | LangChain/Community：FAISS pickle 反序列化 | 本项目向量库存储使用 Chroma，未发现 FAISS 调用 | 不接收外部 FAISS/pickle 库，迁移分案 |
| CVE-2024-7774 | 审计映射至 Python langchain，但正文描述 langchainjs 文件路径操作 | 存在生态映射疑点；不能直接宣布误报或忽略 | 独立核实公告/包映射，再决定是否申报误报 |
| CVE-2024-8309 | LangChain：GraphCypherQAChain 注入 | 未发现 GraphCypher/图数据库链路 | 迁移分案，勿把模型输出直接当数据库查询执行 |
| CVE-2025-14929 | Transformers：X-CLIP checkpoint 转换不可信反序列化 | `rag_chain.py` 固定 BGE 本地 CPU，未发现 X-CLIP 转换入口 | 保持受信模型缓存；复核离线工具及模型供应链 |
| CVE-2025-65106 | Core：不可信 prompt template 模板注入 | 应用组装消息对象；未发现用户控制的模板定义入口 | 核实传递路径；禁止将用户内容当模板定义，迁移分案 |
| CVE-2025-68664 | Core：含 lc 字典的序列化/反序列化注入 | 应用未直接调用 core.load；Runnable/追踪内部仍需核实 | 不加载用户提供的序列化 LangChain 对象；迁移分案 |
| CVE-2025-6984 | Community：EverNoteLoader XXE | 未发现 EverNoteLoader；上传解析直接走 txt/PDF/DOCX | 不新增该 loader，迁移分案 |
| CVE-2025-6985 | Text-splitters：HTMLSectionSplitter 不可信 XSLT | `chunking.py` 用 RecursiveCharacterTextSplitter，不接受自定义 XSLT | 保持现有切片入口，迁移分案 |
| CVE-2026-1839 | Transformers Trainer checkpoint RNG 反序列化 | 未发现 Trainer；候选 torch 2.6.0+cpu，不满足公告中 torch<2.6 的条件 | 保留原始告警，核实适用版本后处置 |
| CVE-2026-26013 | Core：图片 token 计数抓取 URL，SSRF | `ChatOpenAI` 被实际使用，但应用未直接调用 get_num_tokens_from_messages | 不能仅凭 grep 判安全；核对计数的传递调用与图片输入边界 |
| CVE-2026-34070 | Core：外部 prompt 配置中的文件路径读取 | 未发现 load_prompt/load_prompt_from_config 入口 | 禁止外部模板配置，迁移分案 |
| CVE-2026-40087 | Core：Dict/Image prompt template 访问属性或索引 | 未发现对应模板类；应用使用消息结构 | 仍核对传递构造路径，迁移分案 |
| CVE-2026-41182 | LangSmith：流式 token 绕过输出脱敏 | 流式链真实存在；没有显式 LangSmith 调用不保证关闭自动追踪 | 候选验证进程显式关闭追踪；未来运行环境须单独核实 |
| CVE-2026-41481 | Text-splitters：HTML URL splitter 重定向 SSRF | 当前未发现该 URL splitter 入口 | 不新增网页 splitter；与 Core 兼容升级一起评估 |
| CVE-2026-41488 | OpenAI adapter：图片计数 URL 的 DNS 重绑定 | adapter 使用中，未发现直接调用计数函数；与 26013 不能混成一个通报 | 核对 adapter 内部调用后决定缓解/升级；不真实请求内网探测 |
| CVE-2026-4372 | Transformers：恶意模型 config 导致任意代码执行 | 固定本地 BGE；候选进程 HF_HUB_OFFLINE=1。但固定模型名不等于模型文件已校验 | 单独评估模型缓存完整性与 Transformers 升级兼容性 |
| CVE-2026-44843 | Core：运行时过宽的对象反序列化允许列表 | 应用无直接 load 调用；Runnable/序列化内部未做完整动态证明 | 不接收外部序列化对象；迁移分案 |
| CVE-2026-45134 | LangChain/LangSmith：不可信 Hub prompt manifest | 应用未发现 hub.pull/pull_prompt；无公共 prompt Hub 入口 | 不启用公共 prompt 加载，迁移分案 |
| CVE-2026-45830 | Chroma：服务端多租户授权隔离 | 应用为嵌入式持久库；compose 无独立 Chroma HTTP 服务 | 不暴露 Chroma API；未来服务化/多租户前重新评估 |
| CVE-2026-45833 | Chroma：服务端 collection 更新允许不可信模型代码 | 当前无 Chroma HTTP 管理接口；公告涉及 /api/v2，旧版适用性仍需核实 | 核实公告版本与实际 API；不改库格式来强行消警 |
| CVE-2026-5241 | Transformers：LightGlue 模型配置越过 trust_remote_code | 未使用 LightGlue，旧版适用性仍需公告核对 | 保持固定受信 BGE，模型加载升级另案 |
| CVE-2026-55443 | LangChain：路径/搜索模式未限制在根目录 | 无对应文件搜索代理或外部 prompt 配置入口 | 迁移分案，勿将库内置文件工具直接开放给用户 |
| CVE-2026-59152 | LangSmith TracingMiddleware：HTTP 头触发文件作为追踪附件上传 | `main.py` 未安装该中间件；环境自动追踪与该中间件不是同一机制 | 保持未启用，单独核实 SDK 适用版本；迁移分案 |
| CVE-2026-9856 | Transformers：save_pretrained 中 chat_template 文件路径遍历 | 应用未发现 save_pretrained 或用户可选 tokenizer 下载入口 | 审核模型维护脚本/缓存来源，升级另案 |

## 可执行分案，不在本轮直接实施

1. LangChain 族：从当前实际使用面（消息、ChatOpenAI/OpenAIEmbeddings、Chroma 适配器、HuggingFaceEmbeddings、RecursiveCharacterTextSplitter）开始，先找可兼容且消除目标通报的版本组合；不预设一定要整套重写 Agent。覆盖流式响应、工具调用、嵌入输出及引用门禁。删除未使用的依赖也须先查传递依赖，不能只查直接 import。
2. Transformers：固定 BGE 模型文件和测试语料，比较升级前后向量维度、归一化、确定性和检索结果；仅有实证表明语义空间改变时才提出重嵌，不预先重建真实库。
3. Chroma：先核实通报对嵌入式 0.4.24 的适用性；若需版本升级，使用副本做读取、写入与恢复试验，明确存储格式回退边界，不直接打开真实库迁移。

本地候选阶段若要在这些风险尚未解除时结账，必须由 Owner 对具体本地用途和限制作出明确接受；本文件不作代签，发布 CI 也不因这份说明自动转绿。
