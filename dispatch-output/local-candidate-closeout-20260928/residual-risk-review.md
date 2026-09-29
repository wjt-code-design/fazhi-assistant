# 剩余依赖风险复核（执行中，未获风险接受）

日期：2026-09-28（**2026-09-29 追加一节"运行时探针读数"附录，见文末；上表正文一字未改**）。对象：`aec8d5c` 的应用调用面及两项升级提案。
原始基线 `audit-baseline.json`：138 条记录、10 个命中包；ID/别名归并为 74 组。下表是其中非 pypdf/Starlette 的 47 条记录，归并后 26 组通报；**候选安装与最终扫描尚未完成，不把此数当升级后实测**。

每项的全部 ID、别名和审计库给出的修复版本保留在 `audit-baseline-summary.json` / 原始 JSON。修复版本只能作为选型线索，不证明新依赖集合兼容。没有 fix_versions 也不等于永久无补丁。

共同状态：**未接受、未忽略、未解除**。复审最迟日期为 2026-10-05，若提前发布、启用新入口或收到新公告则立即复审。助手的静态分析不是 Owner 签字；下面“未发现调用”不是“不可能可达”。

| CVE（别名见 JSON） | 组件与触发条件 | 当前应用证据与限制 | 后续处置方向 |
|---|---|---|---|
| CVE-2024-2965 | LangChain/Community：SitemapLoader 循环 sitemap | 应用导入面未发现该 loader；不接受外部 sitemap 配置 | 在 LangChain 分案核实传递调用；避免新增该入口 |
| CVE-2024-3095 | Community：WebResearchRetriever 任意地址请求 | 应用未发现该 retriever；当前检索为本地 Chroma | 迁移分案，维持无网页抓取入口 |
| CVE-2024-5998 | LangChain/Community：FAISS pickle 反序列化 | 本项目向量库存储使用 Chroma，未发现 FAISS 调用 | 不接收外部 FAISS/pickle 库，迁移分案 |
| CVE-2024-7774 | 审计映射至 Python langchain，但正文描述 langchainjs 文件路径操作 | **2026-09-29 已判定：上游 OSV 映射缺陷，对本项目 Python 依赖不适用**（详见文末「D6 结论」节；`getFullPath`/`setFileContent`/`getParsedFile` 在实装 `langchain==0.1.20` 内 0 命中，`mdelete` 同名但不构成本通报的汇） | 处置=「证实不适用」；**原始告警保留、未加 `--ignore-vuln`**，后续扫描仍会报它，引用时连 D6 节一起引 |
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
| CVE-2026-5241 | Transformers：LightGlue 模型配置越过 trust_remote_code | 未使用 LightGlue；旧版适用性**已由今日 `fix_versions` 现算**（在区间 `<5.5.0`，见 `scope-recount-20260929.md` 对应行），本行仍**无运行期入口证据** | 保持固定受信 BGE，模型加载升级另案 |
| CVE-2026-55443 | LangChain：路径/搜索模式未限制在根目录 | 无对应文件搜索代理或外部 prompt 配置入口 | 迁移分案，勿将库内置文件工具直接开放给用户 |
| CVE-2026-59152 | LangSmith TracingMiddleware：HTTP 头触发文件作为追踪附件上传 | `main.py` 未安装该中间件；环境自动追踪与该中间件不是同一机制 | 保持未启用，单独核实 SDK 适用版本；迁移分案 |
| CVE-2026-9856 | Transformers：save_pretrained 中 chat_template 文件路径遍历 | 应用未发现 save_pretrained 或用户可选 tokenizer 下载入口 | 审核模型维护脚本/缓存来源，升级另案 |

## 附录（2026-09-29）：B 档运行时探针补进来的可达性读数——**不改变本表任何一行的共同状态**

上表"当前应用证据"那一列写的是**静态**未发现调用。2026-09-29 的运行时探针把其中一部分升到
"运行期 0 调用 / 相关模块从未被导入"。逐条对应关系**不在这里手抄**（手抄必过期），由脚本现生：

```bash
cd dispatch-output/local-candidate-closeout-20260928
python b_probe_matrix.py     # -> b-probe-verdict-matrix.md（末尾「公告视角」：26 条 = 有桩可答 17 + 答不上 9，闭合检查 PASS）
```

读数出自两个执行窗口（1660 条非 slow 测试 + 两条直调应用路径），判定与场次绑定。裁定时必须连下面三条限定一起读：

1. **探针答不上的 9 条不是"已排除"**：CVE-2024-3095、CVE-2024-7774、CVE-2025-6985、CVE-2026-1839、
   CVE-2026-41481、CVE-2026-45830、CVE-2026-45833、CVE-2026-55443、CVE-2026-9856
   —— 或因为没有可桩的运行期入口（Chroma HTTP 管理面、text-splitters 的 XSLT / URL splitter、
   Trainer / LightGlue / X-CLIP / `save_pretrained`），或因为问题本身不在调用点上（`CVE-2024-7774` 的包映射疑点，另立 **D6**）。
2. **应用有一个设计内的主动外联点**：`/healthz` 会取 `settings.llm_base_url` 的主机做 TCP 连通探测
   （`backend/main.py:337-342` 的 `socket.create_connection(..., timeout=3)`，软检查）。
   本轮全部网络事件逐键归类的读数是：环回 312 次 + 对假端点 `test.invalid:443` 的解析尝试 1 次（已归因到该探测，
   **无 `socket.connect`、连接未建立**）+ "键里没有主机字段"35 次（本地 DLL 加载与子进程）。
   ⇒ 所以本附录撑得起"这 22 个运行期入口不在路径上"，**撑不起"这个应用不会 outbound"**。
3. **本附录不减漏洞条数**：`pip-audit` 仍是解析集 47 条 / 8 包、实装集 57 条 / 10 包的**红**读数；
   本表共同状态仍为**未接受、未忽略、未解除**，复审最迟日期 **2026-10-05** 不变；助手的静态与运行时分析都不是 Owner 签字。

## D6 结论（2026-09-29 现查）：`CVE-2024-7774` 是**上游 OSV 映射缺陷**，不是本项目的 Python 依赖缺陷

三个一手来源对着读，结论一致：

| 来源 | 它怎么说 |
|---|---|
| GitHub 公告 `GHSA-hc5w-c9f8-9cc4` | 包 `langchain`，生态 **npm**，受影响 `< 0.2.19`，修补版 `0.2.19`， Moderate；描述为 `getFullPath` 方法的路径遍历 |
| PyPA  advisories `PYSEC-2024-111` | **登记在 PyPI / `langchain` 名下**，别名含 `CVE-2024-7774`，但正文自己写的是 "path traversal vulnerability exists in the `getFullPath` method of **langchain-ai/langchainjs** version 0.2.5"，且两条 reference 全部指向 **langchainjs** 的 huntr 赏金页与 commit `a0fad77d6b569e5872bd4a9d33be0c0785e538a9` |
| 我们实装的包 | `langchain==0.1.20`（PyPI 生态），由 `requirements.txt:5` 的 `langchain>=0.1,<0.2` 解析得到 |

⇒ `pip-audit` 之所以报它，是因为它读的 PyPA/OSV 源里有一条**把 langchainjs（JS）的缺陷挂到了 PyPI 的 `langchain` 名下**的记录；
GitHub 自家目录把同一条通报正确分类为 **npm**。这不是版本比对出来的真缺陷，是**数据源的包生态串了位**。

**符号级复核（不只靠"名字没搜到"）** —— 公告点名的方法在本项目实装的 Python `langchain` 包体内是否存在：

```bash
# 在候选 venv 里扫描已安装 langchain 包的全部 .py（本轮实测 1326 个文件）
python - <<'PY'
import importlib.metadata as m, pathlib
lp = pathlib.Path(m.distribution("langchain")._path).parent / "langchain"
for s in ("getFullPath","setFileContent","getParsedFile","mdelete"):
    print(s, sum(1 for f in lp.rglob("*.py")
                 if s in f.read_text(encoding="utf-8", errors="replace")))
PY
```

本轮读数：`getFullPath` **0**、`setFileContent` **0**、`getParsedFile` **0**、`mdelete` **2**（`storage/encoder_backed.py`、`storage/file_system.py`）。

**这条结论的边界，别把它写成"零风险"**：

1. 公告点名的**汇（sink）`getFullPath` 在 Python 包里根本不存在**，三个 JS 专有名 0 命中 ⇒ 通报描述的缺陷不在我们的依赖上。
2. ⚠️ 但 `mdelete` **同名存在于** Python 的 base-store API ⇒ 所以依据是"**汇不存在 + 生态归属是 JS**"，
   **不是**"公告点名的符号一个都没找到"。这句话只能证"该通报不适用"，**不能**当作 Python 侧文件存储没有路径处理风险的证明。
3. 我们的应用代码对 `langchain.storage` / `LocalFileStore` / `mdelete` **零引用**（直接引用与 `__import__`/`getattr` 动态引用都查过；
   唯一 `__import__` 命中是 `backend/docx_utils.py:49` 的 `__import__("io")`，与存储层无关）。
   这条是静态结论，**不是**不可达证明。
4. **处置**：判"**证实对本项目所用 Python 依赖不适用（上游映射缺陷）**"。
   **原始告警照旧保留**，本轮**未加** `--ignore-vuln`、未改 `requirements.txt`、未从 `pip-audit` 读数中抵扣 ——
   下一轮扫描仍会报它，这是预期的，引用时连本段一起引即可。
   真正的上游修复动作（若有）在 PyPA advisory-database 的条目分类，不在本仓。



## 2026-09-29 复扫对账与逐项处置补充（按 Owner 交下的执行计划 B 节）

### 1. 刷新后的实际读数（不是 47/8 与 57/10 那两个历史快照的复述）

| 范围 | 扫描件 | 通报数 | 记录行数 | 命中包数 | 相对 09-28 快照 |
|---|---|---|---|---|---|
| 候选 `requirements.txt` 解析集 | `B-candidate-requirements-pip-audit-refresh-20260929-164555.json` | 26 | 47 | 8 | **(包,ID/CVE) 三元组零新增、零消失、零版本漂移** |
| 候选 venv 实装集 | `B-installed-pip-audit-refresh-20260929-164325.json` | 31 | 57 | 10 | 同上，零漂移 |

复算命令（两份都在证据目录，判据是 (包, ID∪别名) 集合的对称差，**不是**比条数 —— 条数相同而别名换了位是看得见的）：

```bash
cd dispatch-output/local-candidate-closeout-20260928
python b_scope_recount.py --write    # -> scope-recount-20260929.md（闭合检查 26+5==31，自带 rc）
```

- **扫描器故障与"发现漏洞"这条轴仍然分开**：本次两刷 rc 均 = 1，stderr 只有一行 `Found N known vulnerabilities…`，**没有** `ReadTimeout`
  （09-28 那份 `postcommit-gates.log` 第 9 步的 rc=1 是网络失败，已在交接书 §4.1 更正，两者不可混为一种"红"）。
- ⚠️ **一条我自己踩过的坑，写下来防止复犯**：复扫第一次跑在**主工作区**（`master` 的 `requirements.txt`，仍是升级前的区间锁），
  解出 pypdf 5.9.0 / fastapi 0.110.3 / starlette 0.37.2 ⇒ 报 **138 条 / 10 包**，那正是**升级前的基线**，不是候选现状。
  复扫必须指向候选树 `fbc29e8` 的 `backend/requirements.txt`。
  这份误跑件 `B-requirements-pip-audit-refresh-20260929-164325.json` **保留不删**，它另有用途：见交接书"整合准备"节里
  **"合入候选 = 把解析集从 138 降到 47"** 这条依据（即 master 本身仍是 138 条的红）。
- **分母不是 26**：登记表 26 条只覆盖**应用运行时**这一根轴。实装集另有 **5 条落在开发/构建工具**（pytest、setuptools），
  以及 **1 个包根本没被审计**（`torch 2.6.0+cpu` 带 `skip_reason`，PyPI 无该分发）⇒ 逐条与三轴归属见
  `scope-recount-20260929.md`（由上面那条命令现生，本页不抄它的数）。**D2 那笔签字的射程不含开发工具轴。**

### 2. "报告里有"≠"对本环境适用"——pip-audit 的判据只比本包版本

公告里若带**跨包前提**（例如某条要求 `torch < 2.6`），`pip-audit` **不评估**它，它只把**本包**版本对着 `fix_versions` 比。
⇒ 本表里凡是靠"别的包版本不满足前提"来判不适用的行，**Scanner 的命中不构成反证，我们的结论也需要另行举证**。
本轮据此需要单列核的一条：**`CVE-2026-1839`**（本表正文写的处置方向是"候选 torch 2.6.0+cpu，不满足公告中 torch<2.6 的条件"）。
原先这里写的是"**这条前提我没能一手核到**（`fix_versions` 只给了 transformers `5.0.0`/`5.0.0rc3`，跨包条件不在扫描读数里）"——
**那句话是错的**：跨包前提不在 `fix_versions` 里，但**在同一个 JSON 的 `description` 字段里**，我当时只查了前者。
2026-09-29 同日已证结（见下面「两条「待核」同日证结」节）：这条判**对本环境不适用**，依据是三条独立证据，不再是单靠 grep。
⚠️ 本节的一般性论点**不因此失效**：`pip-audit` 依旧不评估跨包前提，只是那条前提可以从扫描读数正文里读出来，不必外求。

### 3. 探针答不上的 9 条：逐项处置（不重抄整表，只补"暴露入口 / 限制 / 状态"）

| 通报 | 命中包与版本 | 版本适用性 | 为什么探针答不上 | 本轮处置状态 |
|---|---|---|---|---|
| CVE-2024-3095 | langchain-community==0.0.38 | 在区间（`<0.2.9`） | 无可桩的运行期入口（WebResearchRetriever 不在路径上） | **待处置**：只能靠"应用无网页抓取入口"这条限制由 Owner 显式接受；无运行期读数 |
| CVE-2024-7774 | langchain==0.1.20 | 无修复版本(未给) | 问题不在调用点，是映射 | ✅ **已判定不适用**（上游 OSV 映射缺陷，见「D6 结论」节）；原始告警保留 |
| CVE-2025-6985 | langchain-text-splitters==0.0.2 | 在区间（`<0.3.9`） | HTMLSectionSplitter 的 XSLT 面无运行期入口 | **待处置**：`chunking.py` 只用 `RecursiveCharacterTextSplitter`（静态），需 Owner 接受"不接受自定义 XSLT"限制 |
| CVE-2026-1839 | transformers==4.57.6 | 在区间（`<5.0.0`） | Trainer checkpoint 无入口 | ✅ **不适用（已证结）**：公告前提是 PyTorch **<2.6**，实装 **2.6.0+cpu** 不满足；汇 `Trainer` 应用侧 0 引用；并实测 torch 2.6 默认 `weights_only=True` 会拦住该利用。⚠️ 失效条件=torch 保持 ≥2.6。详见「两条待核同日证结」节 |
| CVE-2026-41481 | langchain-text-splitters==0.0.2 | 在区间（`<1.1.2`） | URL splitter 入口不存在 | **待处置**：同 6985，靠限制条款覆盖 |
| CVE-2026-45830 | chromadb==0.4.24 | **版本确实适用**（公告写 "0.4.17 or later"，0.4.24 ≥ 0.4.17） | 需多租户**已认证**用户越权 | **版本适用、靠部署形态不暴露**：compose 无 Chroma 服务/端口，`rag_chain.py:123` 走 `persist_directory` 嵌入式；应用侧 `HttpClient`/`start_api` 引用 **0**；`fix` 为空 ⇒ **无升级可消**。唯一支撑=第三栏那条限制，**删它即失效** |
| CVE-2026-45833 | chromadb==0.4.24 | **版本确实适用**（同上，"0.4.17 or later"） | 需向 `/api/v2/.../collections/{id}` 发请求 + 已认证 + `UPDATE_COLLECTION` 权限 | **同 45830**：核实结果与原先的猜测**方向相反**（版本适用），不暴露全靠不起服务；`fix` 为空 ⇒ 无补丁可升 |
| CVE-2026-55443 | langchain==0.1.20 | 在区间（`<1.3.9`） | 无文件搜索代理/外部 prompt 配置入口 | **待处置**：靠限制条款覆盖 |
| CVE-2026-9856 | transformers==4.57.6 | 在区间（`<5.10.0`） | 无 `save_pretrained` 入口 | **待处置**：靠限制条款覆盖；模型维护脚本另案 |

⇒ **9 条里没有一条可以记成"已排除"**：2 条判**对本环境不适用**（7774 是上游映射缺陷、1839 是跨包前提不成立），
2 条判**版本适用但当前形态无暴露前提**（45830 / 45833，靠不起 Chroma 服务，非"不适用"），
5 条只能落到"由 Owner 明确接受某条使用限制"（3095 / 6985 / 41481 / 55443 / 9856）。**待核 0 条**——原先挂在这栏的
两条（1839、45833 的旧版适用性）已于同日按一手公告正文证结，见下面专节。
`fix_versions` 为空的 **4 条**（7774 / 14929 / 45830 / 45833）**一律不得**读成"无补丁即无风险"或"已修"。
判据这里踩过一次坑，写清楚免得下次再算错：同一通报在 JSON 里可能有**两条来源行**（例如 `CVE-2026-5241` 一条给
`['5.5.0']`、另一条给 `[]`；`CVE-2026-1839` 两条分别给 `5.0.0` 与 `5.0.0rc3`），**单行 `fix` 为空不构成"无补丁"**，
必须把**共享任一 ID 的来源行先聚成同一条通报**，再对组内 `fix_versions` **跨来源取并集**判空（用整组 ID 集合作键会
把别名不完全相同的两行拆开；本份读数里 47 行聚成 **26 条**，按整组键则会误拆成 33 组）。复算件：
**`b_no_fix_union.py`**（随本件入库，`python b_no_fix_union.py --selftest`；
输出 NOFIX = 4 条：7774 / 14929 / 45830 / 45833，并自带"单行判空会多出 `5241`"这条能红的对照）。
顺带一条独立核上了的分母：该件从原始读数现算出 **唯一通报 26 == 唯一 CVE 26**，与本表 26 行分母不是抄的、是各自算出来的。
本页原先写"3 条"却列了 4 个编号，是数错了，编号是对的。

### 4. Owner 可选的三种决定（逐项落笔才生效；助手不代签，也不自动续期）

1. **修复 / 升级**：按文末「可执行分案」三条走独立回归周期。**本计划不自动授权**新增依赖升级。
2. **限定本地用途并接受具体残余风险**：对上表每一行分别写"接受 / 不接受"，接受面 = 交接书 §6② 的三栏限制 + 五栏日期，
   复审最迟日期沿用在册的 **2026-10-05**，并保留"提前发布 / 启用新入口 / 收到新公告 ⇒ 立即复审"。
   ⚠️ 签这一项**不覆盖**开发工具轴那 5 条与 `torch` 那一轴（另一根轴，见 `scope-recount-20260929.md`；
   torch 轴的盲区同日已消除、**但没有清零**，见 `residual-risk-review-torch-20260929.md`）。
3. **继续阻塞**：维持"未接受、未忽略、未解除"，阶段判定停在「候选受阻」。

**Owner 未落笔时，本表共同状态仍是「未接受、未忽略、未解除」**；上表"处置状态"列写的是助手能证到的边界，不是签字。



## 两条「待核」同日证结（不花凭据的取证）

**`CVE-2026-1839`（GHSA-69w3-r845-3855，transformers `Trainer`）⇒ 判：对本环境不适用**

一手正文就在我们自己的扫描读数里（`PYSEC-2026-2288` 的 `description`），它把前提写全了：
汇是 `src/transformers/trainer.py` 的 `_load_rng_state()` 调 `torch.load()` **没传 `weights_only=True`**，
而受影响范围是"支持 `torch>=2.2` 的所有版本，**当配合 PyTorch 2.6 以下使用时**"。三条独立证据：

| # | 证据 | 现量 |
|---|---|---|
| 1 | 跨包前提不成立 | 实装 `torch` = **2.6.0+cpu**；`packaging.Version('2.6.0') < Version('2.6')` → **False** |
| 2 | 汇不在使用面 | 应用代码 **0 个文件**引用 `Trainer`（不训练，只推理） |
| 3 | 为什么恰好划在 2.6 | 我实测本机 `torch.load(p, map_location="cpu")`（不显式传 `weights_only`）对一枚 `__reduce__→os.system` 的 pickle **抛 `UnpicklingError`**、副作用没发生 ⇒ **torch 2.6 起默认就是 `weights_only=True`**，而这条通报依赖的正是"默认不安全"的那个窗口 |

⇒ 这条**不是**"靠 grep 或不调用读数"判的：第 1 条是可复算的版本判据、第 3 条是实测行为。
⚠️ **失效条件要一起签**：它成立**依赖 torch 保持 ≥ 2.6**。若因别的原因把 torch 降到 2.6 以下（或换用更旧的构建），
这条立刻重新适用。**升级 transformers 到 5.0.0/5.0.0rc3 不是本阶段动作**（会牵动 BGE 向量空间，属 C 档）。

**`CVE-2026-45830` / `CVE-2026-45833`（chromadb）⇒ 判：版本适用，但当前形态无暴露前提**

先前这行写的是"旧版适用性仍需核实"。**核实的结果是反过来的**：公告正文写的是
"**version 0.4.17 or later**"，而我们实装 **0.4.24 ≥ 0.4.17** ⇒ **按版本确实适用**，不能再当"可能不适用"。
真正的依据在部署形态上，而不在版本上：

| 通报 | 公告要求的攻击前提 | 本机/本部署的现量 |
|---|---|---|
| `CVE-2026-45833` | 向 `/api/v2/tenants/.../collections/{id}` 发请求，且攻击者**已认证**并持 `UPDATE_COLLECTION` 权限 | `docker-compose.yml` 只有 `backend`/`frontend`/`caddy` 三个服务，**没有 Chroma 服务、没有 Chroma 端口映射**；chroma 只以 `compose:47` 的**目录 bind mount** 出现 |
| `CVE-2026-45830` | 多租户**已认证**用户越权读写他人 collection | 同上；`rag_chain.py:123` 走的是 `persist_directory=CHROMA_DIR`（**嵌入式持久库**，无监听进程） |

应用侧 `HttpClient` / `chromadb.app` / `start_api` 引用数 = **0**（实测）。
⇒ 所以这两条的正确处置**不是"不适用"**，而是"**版本在范围内，靠不服务化不暴露**"。
`fix_versions` 两条都是**空** ⇒ **没有可升的修复版本**，也就没有"升级即消"这条路。
⚠️ **失效条件是硬的**：一旦起 Chroma HTTP 服务、服务化或多租户化，这两条**立即适用且无补丁** ⇒ 签字页第三栏
"不暴露 Chroma HTTP、不做服务化与多租户"那条限制**是这两条的唯一支撑**，不能删。

**这一小节没有改变的东西**：登记表的分母仍是 **26 条**（这三条本来就在册，没有新增编号）；
`pip-audit` 的 47/8 与 57/10 红读数**一条没少**；共同状态仍是**未接受、未忽略、未解除**。

## 开发/构建工具那一轴（A-3，2026-09-29 已给出处置建议）

表外那 **5 条**（两个包，只在实装集命中）的逐条触发前提、平台条件、修复版本与"要不要动 pin"，
另立一件：**`residual-risk-review-devtools-20260929.md`**（不进本页 26 行分母，也不在 D2 射程内；
对账件仍是 `b_scope_recount.py` 的 `26 + 5 == 31` 闭合）。
**这一节不新增任何编号**，只把结论摆在这儿：其中 4 条的前提落在没人走的构建下载路径上且**都有可升版本**；
剩下 1 条**不能记成"构建期专用 ⇒ 无风险"**——它要求的两个前提（UNIX 平台 + 真的跑该工具）在本仓 CI 上**都成立**，
而它的修复版本恰好在在册版本上限**之外**。
✅ **同日 Owner 授权后按"升级"处置完毕**（先在隔离环境——候选依赖 + 只换测试框架版本——跑全量 rc=0、cov 85.25%，
再把 `requirements-dev.txt` 的下限钉到修复版本；钉住新范围重跑 `pip-audit --no-deps` 得 rc=0，旧范围 rc=1）。
⚠️ **这不等于该条解除**：Linux 那条腿本机没跑过，CI 才是决定性证据（要 O-5 先动）；且 dev 轴**不在** D2 射程内，
本页 26 行的共同状态**不因它改变**。

## torch 那一轴的盲区（2026-09-29 已消除）

实装 `torch 2.6.0+cpu` 原先被扫描器跳过（读数带 `skip_reason`）。本轮摘掉本地构建标签、按实装的上游版本本体补审出
22 条唯一通报，逐条判据与实测结论另立一件：**`residual-risk-review-torch-20260929.md`**
（重算命令：`python -m pip_audit -r <pin torch==2.6.0> --no-deps --format json`，读数 `C-torch-2.6.0-pinned-pip-audit.json`）。
**该轴不在本页 26 行「应用运行时」的分母内，也不在 D2 那笔签字的射程内**；其中一条与实际暴露面直接挂钩，
所以本页的共同状态不因它而改变。

## 可执行分案，不在本轮直接实施

1. LangChain 族：从当前实际使用面（消息、ChatOpenAI/OpenAIEmbeddings、Chroma 适配器、HuggingFaceEmbeddings、RecursiveCharacterTextSplitter）开始，先找可兼容且消除目标通报的版本组合；不预设一定要整套重写 Agent。覆盖流式响应、工具调用、嵌入输出及引用门禁。删除未使用的依赖也须先查传递依赖，不能只查直接 import。
2. Transformers：固定 BGE 模型文件和测试语料，比较升级前后向量维度、归一化、确定性和检索结果；仅有实证表明语义空间改变时才提出重嵌，不预先重建真实库。
3. Chroma：~~先核实通报对嵌入式 0.4.24 的适用性~~——**该核实已于 2026-09-29 做完**（结论：版本确实适用，见上面专节），
   剩下的分案是"若需版本升级，使用副本做读取、写入与恢复试验，明确存储格式回退边界，不直接打开真实库迁移"；
   但因两条通报 `fix_versions` 皆空，**当前无"升级即消"的目标版本可选**，此分案在拿到修复发行版之前不启动。

本地候选阶段若要在这些风险尚未解除时结账，必须由 Owner 对具体本地用途和限制作出明确接受；本文件不作代签，发布 CI 也不因这份说明自动转绿。
