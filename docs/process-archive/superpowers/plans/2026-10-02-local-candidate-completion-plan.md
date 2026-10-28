# 下一阶段：完整本地候选收口执行书（2026-10-02）

> **给执行助手：** 本文自包含，可作为本阶段唯一任务入口。先读适用的 `AGENTS.md`；执行时使用 `executing-plans`，逐项记录结果与停点。不要默认派发子助手；一名助手顺序执行即可。完整本地实验执行授权已记入§1，**最新进度和停点见§0.6；§0.1–0.5保留各自时点**。最终声明环境的真实rerank新许可已按§0.5执行完，不准再次调用。文中风险签字、未来真实新轮次、提交／合入等审批仍不能代答；单项pypdf下载已按§0.3完成，不准重复下载。恢复执行时先核对现有检查点，不重建覆盖已存在的目录／日志。

**Goal：** 基于已提交的安全／缓存修复，完成剩余 PDF 与两项依赖的最小整合、声明一致的隔离环境验收、公开法规副本的检索／真实 rerank 验收和风险材料收口，交付可复查、可恢复的本地候选。

**Architecture：** 沿用现有 FastAPI、检索、缓存和知识库架构；只提取旧候选中的必要增量，不整支合并。所有实验和数据库写操作只在仓外独立副本进行；正式提交或合入主线另等明确授权。

**Tech Stack：** Python 3.11、FastAPI、pypdf、SQLAlchemy、pytest、Ruff、mypy、Chroma、本地 BGE 嵌入、既有远端 rerank、Next.js／Vitest、Git、PowerShell。

## 0. Owner 已对齐的边界

- 本阶段选择 **A：完整本地候选收口**，不是扩大到远端发布执行。
- 验收语料选择 **A：现有知识库的隔离副本／公开法规子集**。读取原库获取副本，不向原库写入。
- 真实 rerank 只发送核对过的公开法规和固定测试问句，不发送私有上传件、聊天记录、用户资料或 QA 沉淀。
- 已有 rerank 调用许可不解除凭据撤销／轮换前置，也不允许新增生成模型或云端嵌入调用。
- 未选服务器，**不部署**。不 push、不建 PR、不写真实库、不改远端、不处理无关历史、不删除明文残片。
- 本书中的“候选”默认指仓外实验副本／本地交付包，**不是已经获准合入 master 或可以发布的版本**。

### 0.1 历史局部执行状态（第三轮结束，完整 A–F 执行前）

截至第三轮结束、尚未接手完整 A–F 时，只执行已授权的公开语料／真实rerank验证、配置来源排查及仓外验收入口调整，没有执行两项依赖移入、整套候选环境重建或主线合入。此段保留该时点，不代表下面的新候选现状。详见 `C:/Users/33393/Desktop/ai-legal-helper/docs/work-report-20261002-rerank-acceptance.md` §9；§2–8保留前两轮历史。

- Owner 以 **A** 确认暴露过的主／备用旧Key已撤销；前两轮文件凭据各一次401。随后只读核对发现系统级主值与文件主值不同、backend/.env未变，Owner明确“同意”第三轮只用Windows系统级主字段及一次真实验收。该许可已使用，不允许据此再开第四轮。
- 第三轮仓外入口仅内存读取系统级 `RERANK_API_KEY`，不改.env／业务配置／系统变量，不试文件或备用凭据；每次发送前核对实际鉴权头。缺失／访问拒绝／无效格式不回退，401后停止实际发送。新增15项测试在旧代码上失败，最终安全回归 **32 passed**；没有凭据原文／长度／Key哈希进入日志。
- 复用已审核四部完整法规 **1528条**；公开库独立恢复、验后记录指纹和本地BGE八条抽核通过。离线原烟测 **24/24**；**第三轮真实HTTP发送7次，全部200，有效重排7/7，真实轮次原烟测24/24，退出码0**。本次不是余弦降级假绿，`BLOCKED-RERANK-AUTH` 对限定验收已解除；三轮累计9次真实发送（2次401、7次200）。
- 文件值与系统值仍不同，已有进程可能继承旧环境。**普通应用启动入口／配置优先级尚未验，产品代码未改**；下一次候选集成先只读核对实际入口与凭据来源，再按Owner选择处理，不复制密钥到文件或自动改优先级。局部成功不证明所有运行入口已修复。
- 不需要为证明成功追加调用。下一次真实验收仍须新授权、新路径／新空账本，**不得删除三轮的 `rerank-round.started` 或覆盖失败日志**。完整A–F授权、最终声明环境、两项依赖整合和风险裁定仍按本文待办，不因这一轮通过而自动执行。
- 第一轮证据根为 `C:/Users/33393/Desktop/legal-rerank-acceptance-20261002-c9c0d7684b274afb9427f27a32638af8`，含受限私有快照；第二轮证据根为 `C:/Users/33393/Desktop/legal-rerank-round2-20261002-abc6d089a8a84bba90d7a87673936fae`，只复用已审核公开库，不新增私有副本。两目录／旧日志均保留，不整目录转发或提交Git；只有脱敏报告及单独筛选的非敏感证据可交付。
- 第三轮证据根为 `C:/Users/33393/Desktop/legal-rerank-round3-20261002-cebf70a641c549f9ad44c27cf27261a9`，仅含公开库与隔离源码／证据；保护指纹材料仍不自动视为可公开包。收尾确认原Chroma **38文件**、保护清单 **41对象**、.env、HEAD／refs、冻结文件、前轮公开目录／旧脚本和原脏文档均未变；未提交、合并、推送或部署。历史venv仍不是B／C要求的最终声明一致环境，局部PASS不等于完整候选完成。

### 0.2 历史6.16.1检查点（2026-10-02，新版执行前）

执行根：`C:/Users/33393/Desktop/fazhi-local-candidate-20261002-67944caf51ff48ce9432831cdd62f72b`。本轮报告：`C:/Users/33393/Desktop/ai-legal-helper/docs/work-report-20261002-local-candidate-completion.md`。以下保留6.16.1时点，**最新依赖版本以§0.3、最新真实验收／停点以§0.5为准**；不能重跑创建命令覆盖已有检查点。

- [x] 固定902e2d1，仓外四文件最小整合；独立新环境离线安装，pytest9.1.1，pip check=0，27项直接需求／167约束满足。此检查点 **pypdf仍是6.16.1**，不是修订后的最终目标。
- [x] PDF功能红绿：两坏PDF先500失败；最小PyPdfError转换后9/9通过，相关定向128/128。后端1680 passed／10 skipped／18 deselected，覆盖率85.42%；Ruff／format／mypy及守卫检查通过。原1681个非slow nodeid全保留，新增9个。前端54/54、lint／tsc／build通过。
- [x] 复用1528条已审公开法规，独立新进程恢复、八条BGE空间抽核、离线原烟测24/24和联合召回7/7通过；原库不打开写入。本轮不另开真实rerank；普通配置优先级仅用假值夹具检查4/4通过，不等于真实应用key入口已验。
- [x] 旧检查点实装审计65行／11包／40组；torch+cpu跳过另查上游24行／22组。当时拟用6.19.0仅精确元数据0通报、未安装／未回归；**现已安装复验，最新扫描见§0.3**。原始红灯保留，不减项／不代签D2。
- [x] 旧2658文件清单按9完整在册值内存比对0；5个JWT形状归因官方PyJWT文档。该清单是全测前快照，不能当作测试后全集合检查；新版后置发现／纠正见§0.3。范围不是暂存／历史／所有工作区，也不证明历史索引可公开。
- [x] **原BLOCKED-DOWNLOAD已解除，见§0.3：** 6.16.1历史审计命中8条后，目标修订6.19.0。Owner回复“做完自己审核”允许此前明确请求的唯一395480字节wheel；下载／官方SHA校验完成。下载单不再是新任务，不追加其他包。
- [x] 保留6.16.1检查点后，只改实验pypdf声明／约束、离线安装6.19.0；新版pip check、全项声明、PDF／限流、后端非slow覆盖率、lint／类型／新审计、后置源码指纹与恢复已另存复验。详细最新结果见§0.3。
- [ ] 最终同一源／环境／公开语料的真实rerank轮次、Linux或Owner限Windows用途裁定、D2签字、安全交付集合仍待处理；新轮次须单独许可，不能复用已消耗的第三轮许可。

**交付限制纠正：** 固定归档虽无实际`.env`和常见`.db/.sqlite`，仍含`diag/frozen-index-004`／`005`历史HNSW二进制。没有判为公开，也不打开它们来凑验收；归档只能留在受控仓外用于本地来源／恢复，**不进入可转发源码／证据包**。本轮生成的6.16.1四文件补丁／局部恢复只作检查点，最终无数据交付包待收口。不删除或改写这些历史产物，不把来源哈希或零key命中当隐私批准。

风险详情与全部ID／别名见执行根的 `evidence/B-current-risks.md`／`current-audit-summary.json`。新增sentence-transformers／Transformers通报和模型缓存完整性未验一并登记；不自动扩成整套模型依赖升级。D2最迟2026-10-05未续期。提交、合入、push、真实库写入和部署仍未执行。

### 0.3 最新6.19.0执行结果与自审（2026-10-02）

仍使用§0.2同一仓外根，不新建主仓分支；**本次单项升级及受影响技术复验完成，完整A–F阶段仍部分完成**。Owner“做完自己审核”是此前单项wheel下载／隔离升级／回归请求的执行确认，不是D2、提交／合入或新真实rerank许可。

- [x] 16:57:41–16:57:43只下载pypdf6.19.0通用wheel一个，395480字节，SHA-256 `7e5d6e730e7dae87d560a2cee218b852f6498c8be61966f3cd02ead971e48d14` 与当前官方精确元数据一致；下载退出0，独立venv离线安装退出0。未下载其他依赖、模型／CUDA或镜像；未碰共享venv。
- [x] FastAPI0.141.1、pypdf6.19.0、pytest9.1.1；27项直接需求和167条约束全满足，pip check=0。相对本轮6.16.1环境唯一实装版本变化是pypdf。最终源码仍只有四处白名单差异，2658文件，三冻结文件未变；同环境nodeid1681→1690，原项无删除。
- [x] 新版PDF／上传限流9/9、定向128/128；后端**1680 passed／10 skipped／18 deselected，161 warnings**，覆盖率门禁9552/11182=**85.42%**；纯行7429/8554=86.85%、分支2123/2628=80.78%。Ruff／270文件format／74文件mypy、守卫、预算9、值扫描14、发布27、包装器32、配置夹具4均通过；16个门禁实际退出码均0。前端未改，54项测试／build限定引用较早同根结果，不伪称本次重跑。
- [x] 新环境重新打开同一公开库1528条，ID／文本／metadata和输入向量指纹一致、QA=0，HNSW读回仍183条归一化微差且满足原阈值；BGE八条空间抽核、新版离线原烟测24/24／联合召回7/7通过，实际云端rerank／嵌入调用0。
- [x] 新实装审计为**57原始行／10包／32个别名归并组，rc=1**。pypdf、FastAPI、Starlette、pytest本次参与审计且0通报，不代表全环境安全。torch+cpu仍跳过；上游24行／22组为同日较早查询、有限适用。当前材料：`evidence/pdf619-current-risks.md`／`pdf619-current-audit-summary.json`；6.16.1的65/40保留为历史，不再当当前读数。
- [x] 主助手亲自复核代码、测试期望、红绿证据、范围和计数。后置源码检查曾发现既有real_kb夹具在空库上skip前创建了默认SQLite；只读证实0记录后，按原字节移到本执行根runtime隔离区，未删除／改夹具／扩大白名单。失败清单保留；**最终以 `pdf619-clean-candidate-source-verification.json`／manifest 为准**。旧6.16.1清单早于全测，只是当时快照，不能写成测试后已复核。自审文件为 `evidence/pdf619-self-review.md`。
- [x] 新空目录固定归档＋四文件补丁恢复**2658文件集合与全部SHA一致**，没有打开恢复库／应用。薄目录 `checkpoint-pdf619-lf` **72文件**（含清单），9字段内存值比对0、形状0、禁止文件0。它不含基线归档、库／索引、模型、wheel或环境目录；实际恢复和卫生结果分别为 `evidence/pdf619-checkpoint-restore.json`／`pdf619-checkpoint-hygiene.json`。首次恢复脚本局部变量重名失败已最小修正，原失败日志／两目录保留，不冒充产品失败。
- [x] 17:18和17:34最终保护复核：41对象、原Chroma38文件及全部指纹、backend/.env、HEAD／refs、原脏文档均未变；主仓跟踪业务代码未改。最终记录为 `evidence/pdf619-final-protection-after.json`；薄包保留17:18原记录，不改写已验包。未提交、合入、push、写真实库或部署。
- [ ] 最终声明环境的真实rerank：第三轮许可已耗用，本次不追加调用；先给出基于现有1528公开记录、固定7问、实际模型列表和≤21次HTTP上限的单轮请求，再由Owner确认。
- [ ] Owner D2风险用途／期限及Windows限定接受：助手只能交事实材料，不能代签；2026-10-05复审日不延长。Linux／远端CI未验。
- [ ] 最终候选接受／对外交付：薄证据集合技术卫生检查通过不等于公开批准；完整272MB基线／恢复目录仍含74历史HNSW文件，禁止整目录转发。风险及验收门未关前不标完整候选完成，不自动推进合入／发布。

续跑不重复下载、安装或全测已验对象；源码／环境改变才按影响复验。后续需新权限的是上述真实轮次和Owner裁定，不需要现在选择服务器。已发现的发布测试导出路径可移植性、real_kb默认建库和兼容rerank裸dict分支另案记录，不能顺手扩成重构。

### 0.4 模型来源与最终rerank调用前检查（2026-10-02 23:06）

沿用同一仓外执行根；本次只读核验并更新材料，**没有加载模型、真实模型调用、权重下载、凭据／缓存修改或业务代码变更**。依赖全测结果仍见§0.3，不冒充本轮重跑全量测试。新增证据放在原evidence目录，已验`checkpoint-pdf619-lf`及三轮失败／成功记录不改写。

- [x] 默认HF缓存`refs/main`为`f03589ceff5aac7111bd60cfc7d497ca17ecac65`，该快照只有BIN权重；另一个`b034223b74fa1f0984ea672da37ef94e92c0ef2a`快照缓存了safetensors。以离线缓存解析及已装加载器分支核对，**不能把“另有safetensors缓存”写成默认使用safetensors**；本次没有反序列化权重作证明。
- [x] 两快照现存12文件做本地SHA-256指纹。BIN的409138989字节／SHA与官方**当前main**LFS指针一致；safetensors的409097104字节／SHA与其**精确提交**官方指针一致。精确旧提交API在本机连接超时，退出28并保留命令记录；配置／tokenizer等小文件尚缺逐文件官方证明，故来源核验仍为**PARTIAL**，不是“全部可信／模型依赖风险清零”。见`evidence/bge-provenance-preflight.json`，官方指针分别为[当前BIN](https://huggingface.co/BAAI/bge-base-zh-v1.5/raw/main/pytorch_model.bin)、[固定safetensors](https://huggingface.co/BAAI/bge-base-zh-v1.5/raw/b034223b74fa1f0984ea672da37ef94e92c0ef2a/model.safetensors)。不为了收口修改缓存引用、混合快照或追加下载。
- [x] 最终声明环境的静态rerank预检通过：1528公开记录及正文SHA白名单、固定烟测SHA、7问、单模型`BAAI/bge-reranker-v2-m3`、`https://api.siliconflow.cn/v1/rerank`均与既有审查一致。理论发送7次；现有包装器硬上限21次；11946字符／7933 token仅复用§0.3同源离线池估算，不是新实测账单。平台当前余额未验，不能据本地空账本宣称额度充足。端点／模型有[官方接口依据](https://docs.siliconflow.cn/docs/api/rerank-post)。
- [x] 系统级主key只在内存读取／格式校验；未写key、长度或key哈希。**当前进程没有继承该字段，普通dotenv优先级会取文件值，且该值不同于系统值**。这是只读值选择核验，不是实际启动／鉴权请求；系统值存在也不证明旧主备已撤销。后续真实轮次只用系统主key内存注入，不能回退文件／备用。正式启动入口的受控注入和实际鉴权另待授权验证，不能把包装器结果推广成所有应用入口已修好。
- [x] 本次重新执行包装器32＋假值配置4，共**36 passed**；两脚本与第三轮原文件SHA一致。新源码清单2658文件仍只含四处白名单差异；nodeid比对限定引用§0.3收集日志，没有重新收集／全测。23:06保护复核41对象、原Chroma38文件、.env、HEAD／refs、原脏文档全不变。证据：`final-rerank-preflight.json`、`post-model-guard-tests-command.json`／JUnit、`post-model-candidate-source-verification.json`／manifest、`post-model-protection-after.json`。
- [ ] 新一轮真实rerank授权仍未取得。本轮先申请**固定7问／预计7次、硬上限≤21次HTTP**；沿用现有已测守卫，SDK重试0、不跟随重定向、逐问清缓存、401后拒发、不加外层重试或追加轮次。预检JSON的`recommended_new_round_cap=7`只是可另行收紧的建议，**不是已经实现的守卫上限**，不以它冒充当前限额。获准后先复核冻结指纹和保护对象，再在本执行根尚未使用的轮次入口独占创建标记／新空账本；原三轮许可不能复用。失败保存并报告，不删标记重跑。
- [ ] D2／Windows本地接受仍须Owner裁定，复审日2026-10-05不变；模型来源PARTIAL和普通启动凭据差异纳入未决项。Linux／远端CI、真实生成／浏览器、当前目标环境、合入／提交／push、真实库写入和部署均未执行或批准。**本地阶段仍部分完成，不能将本次预检写成发布通过。**

### 0.5 最终声明环境真实rerank已执行（2026-10-02 23:25）

Owner对§0.4／上一条回复中的精确单轮请求明确回复**“批准”**。授权仅为本次公开语料／固定7问／单模型／≤21次HTTP，**不是D2风险接受、普通应用启动验证、提交／合入或部署授权**。在同一候选根使用之前未启动的入口，不新建源码副本／venv，不改包装器业务逻辑、不追加下载。

- [x] 前置新复核：27直接需求／167约束满足，167实装版本／声明指纹与§0.3一致；2658源码文件与已验manifest全相同、四处白名单和冻结文件不变；12个模型缓存文件／默认引用未变，模型来源PARTIAL仍保留；公开库1528条全文／metadata／输入向量及数值读回指纹与先前相同。23:22原41对象／38原库文件／.env／HEAD／refs／原脏文档保护通过。
- [x] **23:24:51–23:25:08单次执行退出0：实际HTTP 7次，全部200，逐次鉴权头与内存所选系统主key一致；有效重排7/7，固定法名×条号召回7/7，原快速烟测24/24。** 24是意图7＋召回7＋引用3＋复杂度4＋自检3，只有7个真实检索问句；不是24题生成回答。本轮是SiliconFlow原生路径，不是余弦降级；未验证裸`cast_to=dict`兼容分支／生产默认重试。SDK重试0、不跟随重定向、逐问清缓存，守卫拒绝数0。发送的每个正文SHA列表与同源离线池一致，未发送QA／私有上传件。
- [x] 授权／绑定为`evidence/final-rerank-authorization-and-binding.json`，精确白名单为`evidence/rerank-approved.json`；真实原日志／命令／独立聚合分别为`final-rerank-real.log`、`final-rerank-real-command.json`、`final-rerank-real-summary.json`。原`final-rerank-preflight.json`中的零调用／未授权字段只描述23:05预检，不改成事后结果。
- [x] 验后新进程复核1528公开条文及向量、QA=0、集合SHA全不变，2658源码manifest及167实装版本不变；23:25原保护复核通过。前／后公开证据分别为`final-rerank-before-public-copy-verification.json`／`final-rerank-after-public-copy-verification.json`；源码验后为`final-rerank-after-candidate-source-verification.json`／manifest，保护为`final-rerank-after-protection-after.json`。
- [x] 三个旧轮次标记和本根第四个`evidence/rerank-round.started`均保留。配额监控total=0，正常扣减不创建`rerank-quota.sqlite`；只读列文件命令曾误假定它存在，已按源码／存在性核对纠正，不把该命令错误当实际调用失败，也没有因此重跑真实轮次。**防重跑依据是独占标记，不是账本文件是否存在**；本次许可已消耗。
- [ ] 剩余边界：D2／Windows本地接受仍未签，复审2026-10-05不变；模型来源PARTIAL、普通启动凭据入口差异、Linux／远端CI、真实生成／浏览器均未解除。已验72文件薄包不改写，也不冒充包含本轮新证据的最终交付包；后续整合新增证据须新清单／卫生复核，不传含历史HNSW的完整来源根。**E2限定验收完成，完整本地阶段仍部分完成，发布未启动。**

### 0.6 启动配置与裁定材料续办（2026-10-03）

后续风险补查最新见主报告§13及 `C:/Users/33393/Desktop/ai-legal-helper/docs/process-archive/superpowers/plans/2026-10-03-dependency-risk-followup.md`：新增依赖分案、缺包模拟整体未通过，模型来源仍PARTIAL；未改变本候选依赖或风险签署状态。

Owner继续授权本地收口。最新材料见 `C:/Users/33393/Desktop/ai-legal-helper/docs/local-candidate-decision-20261003.md`，主报告§12；§0.1–0.5为历史时点。此轮不消耗新的真实调用，不修改四文件候选范围或业务配置优先级。

- 已用最终候选真实Settings／dotenv做6项离线配置检查：当前工具子进程已继承与系统主值一致的key；`.env`仍不同。启动前将系统主值显式注入目标进程即可保持现有优先级。无需把key写文件或给产品加入注册表逻辑。已有Settings实例不会自动刷新；完整服务启动仍未验。
- 初版探针因清空Windows运行时环境导致导入OSError，保留失败记录；v2仅隔离应用字段后通过。未启动应用／加载模型／调用API。
- D2材料已按当前对象整理成可选择的A／B，风险仍待Owner裁定，2026-10-05不延长；模型来源PARTIAL、依赖通报、Linux／CI、生成／浏览器待办保留。
- 最终本地评审集合使用新路径 `checkpoint-closeout-20261003`，旧72文件薄包原样保留。新增集合的精确清单和卫生结果以 `evidence/closeout-delivery-20261003.json` 为准；不是发布批准或完整运行包。

## 1. 接手基线与事实

执行补记：Owner 最新明确授权“后续你来执行，包括计划书的内容”，普通方案对齐采用助手推荐，不逐项重复提问。本轮由主助手顺序执行；风险接受、提交／合入／推送、部署及另设审批的操作仍不代答。仓外执行根为 `C:/Users/33393/Desktop/fazhi-local-candidate-20261002-67944caf51ff48ce9432831cdd62f72b`，进度及停点见 `C:/Users/33393/Desktop/ai-legal-helper/docs/work-report-20261002-local-candidate-completion.md`；该授权不改变§0.1中已消耗的真实rerank轮次许可。

所有路径以仓根 `C:/Users/33393/Desktop/ai-legal-helper` 为基准；后续命令中的路径变量必须由本文初始化为绝对路径。

| 对象 | 2026-10-02 核对结果 | 执行含义 |
|---|---|---|
| 已提交主线 | `902e2d161e67100ed6d267a08c393538a0abe109`，13 个文件，提交信息 `fix: harden credential scanning and cache invalidation` | A／B／C 安全缓存修复、三处类型注解及两项日志测试已提交，不重复实现 |
| 旧候选 | `fbc29e87c14e8e6a2c0744e98d86d426f6146ade`，分支 `codex/local-candidate-closeout` | 仅作为剩余增量来源，禁止直接覆盖当前文件或整支合并 |
| 两者共同祖先 | `aec8d5c22a202c2b7b711d169096777d316f2932` | 用于解释候选原始增量，不代表新候选应从这个旧基线起步 |
| 主线未提交内容 | `docs/process-archive/superpowers/plans/2026-09-29-local-candidate-decision-and-release-prep.md` | 接手前已有修改；文件 SHA-256 为 `ebf24251daaabae4c619b558ff521247288fcbcbec6e5212149d68c5577f2b09`，本轮保留，不夹带提交 |
| 其他未跟踪／忽略产物 | 存在历史诊断、数据及残片 | 不据此清理，不用 `git add -A`，不宣称工作区全干净 |
| 现有隔离解释器 | `C:/Users/33393/AppData/Local/Temp/legal-closeout-20260928/venv/Scripts/python.exe` | 只读对照、创建新环境的引导入口；不得安装或更改它 |
| 该环境实装 | Python 3.11.0、FastAPI 0.141.1、pypdf 6.16.1、pytest 8.4.2、SQLAlchemy 2.1.1、Chroma 0.4.24、torch 2.6.0+cpu | 与主线声明不一致，不能用旧绿灯证明按最终清单全新安装也通过 |
| 主线声明 | FastAPI `>=0.110,<0.111`、pypdf `>=4.0,<6.0`、pytest `>=9.0.3,<10` | 前两项待最小移入；pytest 安全下限必须保留 |

历史证据：902e2d1 提交前的 Windows 隔离非 slow 测试为 **1671 passed／10 skipped／18 deselected，覆盖率 85.09%**；mypy 按现有配置检查 74 文件无错误。这些只是历史基线，**不是本书完成证据**；未覆盖新依赖清单、前端、真实 KB 烟测、最新审计或 Linux／远端 CI。

重要增量纠正：现在知识服务、main 和缓存相关文件已与旧候选交叉，旧“候选七文件零重叠”描述失效。`git diff 主线 旧候选` 里缓存的倒退、删除 `test_cache_scope_invalidation.py` 和 pytest 降级都不是待办。

### 1.1 冻结文件

| 文件 | 主仓工作文件 SHA-256 | 固定 Git blob／归档副本 SHA-256 |
|---|---|---|
| `backend/agent/state_machine.py` | `97ac10735419cbce39930793aa634d6f9f5a0be7cb0682008e2f93bddfc60882` | `efc21342b5e3ef8c75a1c27d8c86ce527be23d98d7457f1e2d7cb7216a86a5ac` |
| `backend/prompts.py` | `683950f4e0103fb6f3fd1ba32320cf6567c506e15332ae3afec57913e426ed86` | 同左 |
| `backend/scripts/gate5_judge.py` | `90487960771dd372b14de2b1cd19bc25048f9baa639e217627ad8242a340b5db` | 同左 |

`state_machine.py` 的主仓工作文件是 CRLF，固定 Git blob 是 LF，已核对差异仅为换行。主仓保护用中列，`git archive` 的实验／恢复副本用右列；不能把二者混比，也不能为了凑哈希改写冻结文件的换行。这是字节表示区别，不是新增业务差异。

不得改文件、格式化它们、删既有测试、放松 lint／类型／覆盖率／引用判据。确有必要扩大范围时，用中文纯文本 grilling 对齐后再做。

## 2. 权限与停点：避免签字／验收互相等待

| 操作 | 本书获准执行后可做的边界 | 不满足时怎么办 |
|---|---|---|
| 只读核对、风险材料、隔离实验 | A–E 的实验副本和新环境，不改变主仓代码／引用或共享环境 | 环境／文件缺失则记录，不改用真实库或日常 venv |
| D2 风险接受 | 助手整理事实，Owner 决定是否接受、用途和期限 | 不代签。可继续离线实验，但不得把未裁风险的实验提升为正式接受候选／准备主线合并 |
| 凭据 | Owner 确认已撤销暴露的 SiliconFlow rerank 主／备凭据，并仅在本机安全位置配置新值 | E2 真实调用暂停；E1 离线检查继续。新值不发聊天、不打印、不记长度 |
| 本地提交／主线合入 | 需要另一次明确的对象、范围和动作确认 | 交付补丁与指纹即可，不擅自提交、建／移动分支或 tag、merge、cherry-pick |
| 下载 | 优先用已存在且验证过的缓存；缺包列精确下载清单交 Owner | 不自动在线装包、不拉镜像、不下载大模型／CUDA |
| 原库运行状态 | 只有在确认没有写入者的一致窗口内才复制 Chroma | 若需要停服务／容器，先请 Owner 允许；哈希相同不代替一致窗口确认 |

D2 在册最迟复审日期是 **2026-10-05**，截至本书编写仍未签。过期后只能报告“需要重新裁定”，不能自行续期。Owner 可在看到实验结果后作本地用途裁定，不要求先取得远端 CI 才能开展离线实验；但若 Owner 坚持远端 CI 后才接受，本文结论就保持“实验材料就绪，候选接受待裁”，不为收口而绕过。

两把凭据分开：**rerank 暴露凭据卡真实 rerank；ADMIN_PASSWORD 的历史暴露卡将来带本地历史的推送，不卡已隔离且符合前置的 rerank**。无父快照也不是删除历史泄漏或完成凭据处置，本阶段不重建发布快照。

## 3. 路径、交付物和最小执行顺序

建议顺序：**A → B → C → D → E → F**。B 的资料核对和 D 的副本准备可以独立开展，但不要并行修改 C 的代码、安装同一环境或运行共享库验收。没有必要为六项任务开六个会话。

**配置前置不随章节顺序后移：** 初始化路径变量后，在创建／安装实验环境及导入任何项目模块前先执行 E0；每次新终端／新进程都要确认这些设置仍有效。C 的红绿测试和 D 的副本工具同样受 E0 约束，不能等到 E 才隔离。临时环境变量只在执行终端生效，不写入主仓或系统环境。

初始化仅在收到执行授权后运行；当前写规划不运行：

```powershell
$repo = 'C:\Users\33393\Desktop\ai-legal-helper'
$base = '902e2d161e67100ed6d267a08c393538a0abe109'
$oldCandidate = 'fbc29e87c14e8e6a2c0744e98d86d426f6146ade'
$bootstrapPy = 'C:\Users\33393\AppData\Local\Temp\legal-closeout-20260928\venv\Scripts\python.exe'
$wheelhouse = 'C:\Users\33393\AppData\Local\Temp\legal-closeout-20260928\wheelhouse'
$runId = 'local-candidate-20261002-' + [guid]::NewGuid().ToString('N')
$taskRoot = Join-Path 'C:\Users\33393\Desktop' ('fazhi-' + $runId)
$sourceRoot = Join-Path $taskRoot 'source'
$evidence = Join-Path $taskRoot 'evidence'
$py = Join-Path $taskRoot 'venv\Scripts\python.exe'
New-Item -ItemType Directory -Path $taskRoot, $evidence | Out-Null
```

`$taskRoot` 是新的仓外持久目录，不用 TEMP 作为唯一交付，不覆盖 `C:/Users/33393/Desktop/fazhi-closeout-trim-c80d47a-20260930`。首次创建后记下实际绝对路径，各次重试用新日志名，不覆盖失败读数。

若 `$bootstrapPy` 已失效，先用 `py -0p` 只读定位已安装的 Python 3.11 绝对路径，记录版本后重新给 `$bootstrapPy` 赋值，再创建新 venv；不激活或改日常 venv。无可用 Python 3.11 时列下载前置，不临时换成不同大版本。已有 wheelhouse 失效同样走 B 的缺包清单。

允许修改的实验源码白名单：

- `$sourceRoot/backend/requirements.txt`：FastAPI、pypdf 两个精确版本。
- `$sourceRoot/backend/knowledge_service.py`：只改 `parse_uploaded` 的 PDF 错误转换。
- 新增 `$sourceRoot/backend/tests/test_pdf_upload.py`、`test_upload_rate_limit.py`：旧候选的两只测试。
- 只在新依赖实际暴露兼容错误时，提出具体最小修复；新增修改路径先向 Owner 对齐，不自行扩成架构重构。

本轮报告落点：`C:/Users/33393/Desktop/ai-legal-helper/docs/work-report-20261002-local-candidate-completion.md`。报告记录实际执行日期；不把本书编写日当测试日。不覆盖旧报告的历史数字。`backend/requirements-dev.txt`、main、bootstrap 日志测试、检索和缓存源码默认保持 902e2d1 内容。

原始日志、包清单、环境指纹、语料审查记录、风险原始 JSON、补丁、恢复结果放 `$evidence`。原库副本和真实凭据不进入报告、Git、源码包或可转发的证据包。

### 3.1 命令纪律

- 一条重型命令完成后才开始下一条；记录完整命令、cwd、开始／结束时间、**真实退出码**及输出位置。即时保存 `$LASTEXITCODE`，不要把 `tail`／搜索命令的码当测试码。
- 工具运行可分段等待，期间给 Owner 简短进度；不要因为首次输出为空而重新启动。
- 同一失败命令先分析；完全相同的命令最多重试一次。同一 bug 连修三次不过，停止质疑假设／边界。
- 手工编辑用 `apply_patch`。日志和 pip 自带 JSON 报告属于生成产物；避免 PowerShell 5.1 `>` 的 UTF-16LE 输出被误当 UTF-8 JSON。用工具捕获原始输出或 `Start-Process` 的输出重定向，后台进程必须 `-WindowStyle Hidden`。
- 不安装主仓 pre-commit hook、不用共享 venv、不复制 site-packages 拼环境、不启用 `--system-site-packages`、不以 `--no-deps` 安装项目来掩盖依赖冲突。
- 文中代码块是逐条命令索引，不是可整块无条件运行的脚本。除 C 明确预期的功能性红灯、E1 有内容可判读的漏洞审计非零外，任何非零／缺失输出都先停下分析；前测失败不得继续真实调用。

## A. 锁定来源与待做增量

**产物：** `$evidence/A-baseline.md`，包含基线、引用指纹、未提交内容保护和增量分类。

- [ ] 先只读核对：

```powershell
git -C $repo rev-parse HEAD refs/heads/codex/local-candidate-closeout
git -C $repo status --short --untracked-files=no
git -C $repo for-each-ref '--format=%(refname) %(objectname)'
git -C $repo merge-base $base $oldCandidate
git -C $repo diff $base $oldCandidate -- backend/requirements.txt backend/requirements-dev.txt backend/knowledge_service.py backend/main.py backend/tests/test_cache_scope_invalidation.py
Get-FileHash -LiteralPath (Join-Path $repo 'docs\superpowers\plans\2026-09-29-local-candidate-decision-and-release-prep.md') -Algorithm SHA256
```

预期主线／旧候选号和 §1 一致；旧候选中 pytest 退到 `>=7.4,<9` 的差异必须排除。若基线变化，先查是哪一会话改动并重列增量，不能自动 reset 回本文号码。

- [ ] 从固定主线生成实验源码，不复制整个脏工作区：

```powershell
$baseZip = Join-Path $taskRoot 'base-902e2d1.zip'
git -C $repo archive --format=zip --output=$baseZip $base
# 确认 git 退出码为 0 后才解包。
Expand-Archive -LiteralPath $baseZip -DestinationPath $sourceRoot
```

- [ ] 确认实验目录没有实际 `.env`／`.env.local`、业务 DB、真实 Chroma 库；文件名类似 `.env.example` 的示例与真实配置分开判断。若归档意外含真实数据／凭据，停止并记录，不导入应用。原始诊断文件无需全读，不开启真实全工作区扫描。
- [ ] 分别按 §1.1 的主仓列和归档列核对三个冻结文件的字节哈希；确认缓存／失效测试及主线 nullable 审计注解 `list[Row[AuditLog, str | None]]` 都存在。后续不能复制旧候选 main 的 `str` 注解覆盖它。

**A 验收：** 来源明确、四项实验改动白名单成立、用户未提交内容未混入、主仓引用未动。代码差异若超出白名单，不能用“旧候选已经验过”放行。

## B. 依赖、缓存和最新风险准备

**输入：** A 的固定源码；已有 wheelhouse 和风险登记。**产物：** `$evidence/B-dependency-preflight.md`、`candidate-constraints.txt`，必要时 `download-needed.md`。

- [ ] 只读核对已有下载报告 `C:/Users/33393/Desktop/ai-legal-helper/dispatch-output/local-candidate-closeout-20260928/download-report-from-assistant-20260928.md`。报告的 158 wheels 是 **2026-09-28 历史读数**，其中没有 torch，不代表现在缓存完整或适配 Linux。
- [ ] 读取现有隔离环境的分发版本／`pip list --format=json` 作对照，不读或复制日常 venv。将已审核的包名与版本机械生成为 `name==version` 约束，不使用可能含鉴权 URL 的未过滤 freeze 输出。为实验生成精确约束文件：沿用已测试的传递依赖版本，FastAPI **0.141.1**、pypdf **6.19.0**（最新审计修订目标；原6.16.1实测只作检查点，见§0.2），pytest采用 **9.1.1**（满足主线 `>=9.0.3,<10`）；这是实验约束，不另建项目锁包体系。torch保持既有 **2.6.0+cpu** 实验基线，风险另外审，不自动升级。
- [ ] 核对约束与主线直接需求兼容、wheel 文件名／SHA-256／平台标签和来源；遇到缺失或冲突，区分网络缺包、版本冲突、Win／Linux 标签问题。缺包下载单写精确版本、平台、原用途、目标仓外目录、来源／校验、是否大包；交 Owner 后暂停安装。禁止自动下载 CUDA、模型权重或用共享安装绕过。
- [ ] 预读以下三份登记，只把它们当历史线索；用当前官方公告／包元数据核查受影响版本、修复版、利用前提和 CPU 变体，不沿用旧告警数：
  - `C:/Users/33393/Desktop/ai-legal-helper/dispatch-output/local-candidate-closeout-20260928/residual-risk-review.md`
  - `C:/Users/33393/Desktop/ai-legal-helper/dispatch-output/local-candidate-closeout-20260928/residual-risk-review-devtools-20260929.md`
  - `C:/Users/33393/Desktop/ai-legal-helper/dispatch-output/local-candidate-closeout-20260928/residual-risk-review-torch-20260929.md`
- [ ] 标注哪些是本地实验风险、开发工具风险、未来运行／发布风险；默认不升级 Chroma／torch／Transformers、整套 LangChain、Next.js。不加 `--ignore-vuln`、审计豁免或降级安全下限。

**复核新增兼容线索（不是已修）：** 2026-10-02 在现有隔离环境 OpenAI SDK **1.109.1**／httpx **0.28.1**，只用 `MockTransport` 的 200 JSON 响应复现 `client.post(..., cast_to=dict)` 抛 `ValueError`。当前 `retrieval.py` 的 OpenAI 兼容 `/reranks` 分支正使用裸 `dict`；SiliconFlow／DashScope 原生 httpx 分支不使用此解析方式。先按 B 的最终环境和实际模型／端点确认适用性，不把假传输包装器测试当产品兼容分支已验。若本轮实际需要修该分支，先向 Owner 对齐加入 `backend/retrieval.py` 的最小修复及定向回归；不借此整套升级 SDK，也不自动改模型名单来绕开。

**B 验收：** 安装所需缓存能证明满足约束，或给出明确缺包清单；风险输入有来源和日期。B 只是准备，最终实装审计在 E1 进行，不能先写“漏洞已清零”。

## C. 在隔离副本最小移入 PDF／依赖改动

**产物：** 只含白名单的候选增量；独立 venv 与完整安装记录。

- [ ] 先提取两只测试，在应用修复前观察正确的失败原因：

```powershell
git -C $repo show 'fbc29e87c14e8e6a2c0744e98d86d426f6146ade:backend/tests/test_pdf_upload.py'
git -C $repo show 'fbc29e87c14e8e6a2c0744e98d86d426f6146ade:backend/tests/test_upload_rate_limit.py'
```

用 `apply_patch` 把读取的完整内容加入实验副本，不用旧候选覆盖其他文件。固定测试 blob 分别是 `fbcd80c64c8d6901f71d5fbf166a577103bddaa7`、`25934958e3dada3cc497b1a2b50651237d2d63f7`。PDF 的中文期望来自固定 PDF 语法／UTF-16BE 字节，不是 pypdf 生成器自证；两上传路由分别应把空 PDF 和坏 PDF 返回受控 400。限流测试必须真的启用 limiter，验证 20／10 次允许校验后第 21／11 次为 429，结束恢复计数。

- [ ] `requirements.txt` 只替换两行：

```diff
-fastapi>=0.110,<0.111
+fastapi==0.141.1
-pypdf>=4.0,<6.0
+pypdf==6.19.0
```

不手工钉一个未经验证的 Starlette；让已审核约束和解析器满足 FastAPI 元数据。**不复制候选 requirements-dev，不回退 pytest 下限。**

- [ ] 从 B 的已校验缓存创建独立环境；每一行成功后才执行下一行：

```powershell
$constraints = Join-Path $evidence 'candidate-constraints.txt'
& $bootstrapPy -m venv (Join-Path $taskRoot 'venv')
& $py -m pip install --no-index --find-links $wheelhouse -c $constraints 'torch==2.6.0+cpu'
& $py -m pip install --no-index --find-links $wheelhouse -c $constraints -r (Join-Path $sourceRoot 'backend\requirements-dev.txt') --report (Join-Path $evidence 'install.json')
& $py -m pip check
```

`pip check` 预期 rc=0 且无冲突；安装报告、实装版本和两份 requirements 的 hash 一起存。核对每一项直接需求都被实装满足，不能只看 `pip check`——它不替你检查项目文本里遗漏／未满足的要求。

- [ ] 在 §E 的离线安全环境下，先运行下面两只测试；坏 PDF 的 500／未捕获异常应为修复前的功能性红灯，不能把安装失败或测试收集失败叫红灯。限流原本通过无需人为破坏。

```powershell
Set-Location (Join-Path $sourceRoot 'backend')
& $py -m pytest -q (Join-Path $sourceRoot 'backend\tests\test_pdf_upload.py') (Join-Path $sourceRoot 'backend\tests\test_upload_rate_limit.py')
```

- [ ] 只将 `knowledge_service.parse_uploaded` 的 `.pdf` 分支改为：

```python
    if ext == ".pdf":
        from pypdf import PdfReader
        from pypdf.errors import PyPdfError

        try:
            reader = PdfReader(io.BytesIO(raw))
            text = "\n".join((page.extract_text() or "") for page in reader.pages)
        except PyPdfError:
            raise ValueError("PDF 文件损坏或无法解析") from None
```

保留文件 magic／大小／编码检查、空文字拒绝、其他分支和知识写后缓存失效的所有已提交逻辑；不扩大成吞掉所有异常。
- [ ] 同命令复验两只测试为绿，再定向复验已修范围：

```powershell
& $py -m pytest -q (Join-Path $sourceRoot 'backend\tests\test_cache_scope_invalidation.py') (Join-Path $sourceRoot 'backend\tests\test_cache_similar.py') (Join-Path $sourceRoot 'backend\tests\test_light_exit_gates.py') (Join-Path $sourceRoot 'backend\tests\test_request_bootstrap.py') (Join-Path $sourceRoot 'backend\tests\test_smoke_citation_assertions.py') (Join-Path $sourceRoot 'backend\tests\test_chroma_isolation.py')
```

**C 验收：** 测试保持独立判据，增量只含上述两源码文件和两新测试，冻结文件与已提交缓存／类型／日志修复未倒退。新环境是 Windows 实验环境，不据此宣称 Linux 已验。

## D. 一致副本与公开法规语料

**输入：** 原路径 `C:/Users/33393/Desktop/ai-legal-helper/backend/chroma_db`。**产物：** 受限私有快照、独立公开法规库和 `$evidence/D-corpus-review.md`。

本轮最小执行选择：复用第三轮已有一致快照的审核结果及完整公开库，不再重复复制私有数据。前置是当前原库全目录38文件指纹严格等于该轮记录、无已发现写入进程、公开库6文件复制前／后严格一致、1528条审查清单及复验脚本指纹一致；仍需在本轮新环境独立恢复、逐条核对和离线烟测。前置不成立则停下重新判断，不能以“复用”跳过校验；本轮不宣称新建了私有快照。

- [ ] 先确认实际源路径、所有可能写库的后端／容器／导入任务和复制窗口。源不是本文路径时先核对配置，不 import 原库上的 `rag_chain`／应用。需要停止服务则请 Owner 明确允许；未确认一致窗口就不复制。
- [ ] 记录原目录文件清单、相对路径、大小和 SHA-256；拒绝 reparse point／链接及逃出目标根的路径。用全新仓外目标完整复制 Chroma 目录，在打开副本前验证副本指纹等于复制前源指纹，并复验源未变。不得只复制 SQLite 主文件、漏掉 WAL 或 HNSW；源变化则本次副本无效，先分析而非循环重拷。

```powershell
$kbSource = Join-Path $repo 'backend\chroma_db'
$privateParent = Join-Path $taskRoot 'private-kb'
$privateKb = Join-Path $privateParent 'chroma_db'
$publicKb = Join-Path $taskRoot 'public-kb'
# 仅在上一项一致窗口与指纹校验已完成后执行；目标必须不存在。
New-Item -ItemType Directory -Path $privateParent | Out-Null
Copy-Item -LiteralPath $kbSource -Destination $privateKb -Recurse
```

指纹必须覆盖整目录，不拿旧 41 对象保护清单代替一致性判据。副本根禁止放入主仓／原库下面。

- [ ] 只在 **私有副本** 打开 Chroma，记录集合名、数量、距离空间、向量维度和嵌入配置。打开副本可能写副本，允许；原库绝不通过 Chroma 客户端打开。使用副本 SQLite 的 `mode=ro` 做 `PRAGMA integrity_check`，预期 `ok`；在副本验证集合可计数、可按 ID 获取。
- [ ] 从副本筛选完整、已核对的公开法规，不只保留七个金标条文。按来源批次／版本核对条文正文与可信公开原件；“source 看起来像法名”或“origin=seed”单独都不证明公开。未能核对的、正文或 metadata 含私有用户信息的、私有上传件和 QA 集合一律不入公开库。不得改写条文或伪造版本元数据。若只有带私有 metadata 的来源可用，先请 Owner 裁定安全的 metadata 投影范围，不自动删字段后当已批准公开。
- [ ] 记录获准的完整 ID 清单及每条正文、metadata、embedding 指纹；原始正文只留受控本地语料，不进入聊天／日志。公开库 `legal_provisions_cos` 保留已验证的 cosine 配置，逐批复制 **原有 ID／正文／metadata／向量**，不触发云端嵌入。审核后的 ID JSON 存 `$evidence/reviewed-public-ids.json`，结构是无重复的字符串数组。一次性复制代码如下，可通过 `apply_patch` 保存到 `$evidence/copy-public-corpus.py`，只在审核完成后执行：

```python
import json
import logging
import sys
from pathlib import Path

import chromadb


def require(ok, reason):
    if not ok:
        raise RuntimeError(reason)


def main():
    logging.disable(logging.CRITICAL)  # 私有副本的正文／metadata 不进入异常日志。
    require(len(sys.argv) == 4, "invalid argument count")
    source_path, target_path, ids_path = [Path(arg).resolve() for arg in sys.argv[1:]]
    task_root = Path(__file__).resolve().parent.parent
    require(source_path == task_root / "private-kb" / "chroma_db" and source_path.is_dir(), "source is not the private snapshot")
    require(target_path == task_root / "public-kb" and not target_path.exists(), "invalid copy target")
    require(ids_path == task_root / "evidence" / "reviewed-public-ids.json", "invalid approved IDs path")
    ids = json.loads(ids_path.read_text(encoding="utf-8"))
    require(isinstance(ids, list) and ids and all(isinstance(i, str) and i for i in ids), "invalid approved IDs")
    require(len(ids) == len(set(ids)), "duplicate approved IDs")
    source_client = chromadb.PersistentClient(path=str(source_path))
    source = source_client.get_collection("legal_provisions_cos")
    require(source.metadata and source.metadata.get("hnsw:space") == "cosine", "unexpected distance space")
    target_client = chromadb.PersistentClient(path=str(target_path))
    target = target_client.create_collection("legal_provisions_cos", metadata=source.metadata)
    for offset in range(0, len(ids), 1000):
        batch = ids[offset : offset + 1000]
        rows = source.get(ids=batch, include=["documents", "metadatas", "embeddings"])
        require(set(rows["ids"]) == set(batch), "approved IDs missing")
        require(all(rows[field] is not None and len(rows[field]) == len(batch) for field in ("documents", "metadatas", "embeddings")), "incomplete source rows")
        require(all(isinstance(d, str) and d for d in rows["documents"]), "invalid source document")
        require(all(e is not None and len(e) > 0 for e in rows["embeddings"]), "source embedding missing")
        target.add(ids=rows["ids"], documents=rows["documents"], metadatas=rows["metadatas"], embeddings=rows["embeddings"])
    require(target.count() == len(ids), "copy count mismatch")
    print(f"copied_public_records={target.count()}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print("FATAL: " + type(exc).__name__)
        raise SystemExit(1) from None
```

```powershell
& $py (Join-Path $evidence 'copy-public-corpus.py') $privateKb $publicKb (Join-Path $evidence 'reviewed-public-ids.json')
```

执行前验证传入源只能为 `$privateKb`、目标只能为 `$publicKb`，不能传原库。复制脚本的计数不能替代下一项逐条指纹和独立恢复检查；失败时不沿用半成品目录为成功结果。
- [ ] 确认源向量与本地 `BAAI/bge-base-zh-v1.5` 同语义空间／维度且缓存可离线加载；维度相同不等于模型相同。只有云端集合、无法确定模型或缺权重时，登记阻塞；不自动重嵌、下载模型、切供应商或用零向量替代。
- [ ] 在新进程重新打开公开库，用 ID 集合、逐条指纹、数量、集合配置和查询可用性验证可恢复。私有快照不作为远端调用路径；公开库不得包含 QA 沉淀。单独记录过滤范围：子集验收不能声称全原库召回率达标。

2026-10-02 已实测的一项必要口径：ID／正文／metadata 和**复制输入向量**逐项严格一致；cosine HNSW 重建后读取的归一化向量不一定字节一致。该轮在私有副本审查时记录源返回向量 SHA-256，再用公开库 SQLite `mode=ro` 的 `embeddings_queue` 核对全部 1528 条复制输入向量 bytes 完全一致；新进程返回的 HNSW 向量另保留实际指纹并验证有限值、维度、绝对差 ≤`1e-6`、余弦误差 ≤`1e-10`。观察到 183 条读回向量指纹不同，最大绝对差 `2.9802322387695312e-8`，最小余弦相似度 `0.9999999999999991`；未改写任何向量以凑哈希。[hnswlib 官方说明与实现](https://github.com/nmslib/hnswlib)确认 cosine 读取返回归一化向量。未来不能仅放宽容差：输入 bytes 核对必须先通过，也不能静默使用重复／缺失／不同编码的输入记录。这是数据复制与索引浮点表示的区分，不是语义差异的豁免。

七组固定召回期望必须存在于公开库，法名和条号在**同一条文档**联合命中：劳动合同法 87／47／19、劳动法 44、民法典 1213、民法典 586 或 587、消费者权益保护法 25。具体问句／判据冻结于 `$sourceRoot/backend/scripts/smoke_citation_fast.py` 的 `RETRIEVAL_CASES`，不要重写题集；缺法条先查来源／副本／版本，不手工塞答案凑绿灯。

**D 验收：** 一致窗口已确认、原库指纹未变、公开语料有审查记录和独立恢复读数、模型空间匹配。禁止直接运行现有 `backup_data.py`／`restore_drill.py`：前者可能打开原 Chroma，后者输出固定历史证据路径且 Chroma 失败仍可能返回 0。本轮复用其检查思想，不修改这些工具或覆盖历史输出。

## E. 综合验收与真实 rerank 的条件执行

### E0. 每个进程启动前隔离配置

离线测试不继承真实服务配置。使用无实际 `.env` 的源码副本，初始化以下变量，其他供应商 key 清空：

```powershell
$env:PYTHONUTF8 = '1'
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:PYTHONOPTIMIZE = ''
$env:HF_HUB_OFFLINE = '1'
$env:TRANSFORMERS_OFFLINE = '1'
$env:ANONYMIZED_TELEMETRY = 'false'
$env:EMBEDDING_PROVIDER = 'local'
$env:EMBEDDING_QUOTA_TOTAL = '0'
$env:FEATURE_HYBRID = 'true'
$env:RETRIEVAL_POOL_K = '0'
$env:RERANK_ENABLED = 'false'
$env:RERANK_QUOTA_TOTAL = '0'
$env:RERANK_QUOTA_TOTALS = ''
$env:RERANK_QUOTA_INITIAL = '0'
$env:EMBEDDING_QUOTA_INITIAL = '0'
$env:QUERY_REWRITE_ENABLED = 'false'
$env:JWT_SECRET = 'test-jwt-secret-for-ci-only'
$env:LLM_API_KEY = 'fixture-only-not-for-real-calls'
$env:LLM_BASE_URL = 'https://fixture.invalid/v1'
foreach ($keyName in @('ADMIN_PASSWORD','RERANK_API_KEY','RERANK_BASE_URL','RERANK_NATIVE_URL','RERANK_MODEL','RERANK_MODELS','EMBEDDING_API_KEY','ZHIPUAI_API_KEY','DASHSCOPE_API_KEY','SILICONFLOW_API_KEY','LLM_MODELS_JSON')) {
    [Environment]::SetEnvironmentVariable($keyName, '', 'Process')
}
$env:DATABASE_URL = 'sqlite:///' + ((Join-Path $taskRoot 'test-app.db') -replace '\\','/')
$env:QUOTA_DB = Join-Path $taskRoot 'test-quota.sqlite'
$env:CHROMA_DIR = Join-Path $taskRoot 'unit-test-kb'
$env:COVERAGE_FILE = Join-Path $evidence '.coverage'
$env:PYTEST_ADDOPTS = ''
$env:NEXT_TELEMETRY_DISABLED = '1'
```

pytest 的 conftest 会再次隔离业务／配额／向量库；不能把它当未隔离脚本的保护。所有非 pytest 脚本也必须显式设置三个库路径。真实 KB 的 slow fixture 会指向源码目录下默认库，本阶段不运行 `-m slow` 来代替 D／E2。

本书两个一次性执行脚本的输入／路径检查使用显式异常，不能用可能被 `python -O`／`PYTHONOPTIMIZE` 删除的 `assert` 充当安全措施。测试中的 `assert` 保留；E0 清空优化开关，保证测试判据不被跳过。

本轮使用显式固定的本地验收配置：hybrid=true、pool_k=0、查询改写关闭、原烟测k=6、本地BGE和D的公开库。离线与真实rerank两轮保留同一配置，差别仅为rerank开启、批准的真实rerank配置及SDK无重试测量约束；不通过扩大候选池／改时效筛选来修烟测。该配置不宣称等于尚未确定的生产配置；若需要验其他既有配置，先固定配置及预算，另做可比较的结果，不混成一轮。

### E1. 离线、本地及审计

- [ ] 冻结最终源码、直接需求、约束、实装清单、测试 nodeid 集和工具版本；测试后继续改源码／环境就只重跑受影响门禁并更新证据，不拿旧源绿灯签新源。
- [ ] 从 `$sourceRoot/backend` 串行运行，每项保存自己的输出和退出码：

```powershell
Set-Location (Join-Path $sourceRoot 'backend')
& $py -m pip check
& $py -m ruff check .
& $py -m ruff format --check .
& $py -m mypy .
& $py -m pytest --collect-only -m 'not slow' -q
$junitPath = Join-Path $evidence 'backend-junit.xml'
& $py -m pytest -m 'not slow' --cov=. --cov-fail-under=70 --junitxml $junitPath -q
& $py -m ruff check (Join-Path $sourceRoot 'dispatch-output\agent-quality-20260911')
& $py -m ruff format --check (Join-Path $sourceRoot 'dispatch-output\agent-quality-20260911')
& $py -m pytest -q (Join-Path $sourceRoot 'dispatch-output\agent-quality-20260911\test_budget_guard.py')
& $py -B (Join-Path $sourceRoot 'dispatch-output\local-candidate-closeout-20260928\test_worktree_value_scan.py')
& $py -B (Join-Path $sourceRoot 'dispatch-output\local-candidate-closeout-20260928\test_release_gates.py')
```

预期以上均 rc=0、测试无失败、覆盖率至少 70%。比较 902e2d1 的用例集合与最终集合：允许两只新增测试，既有 nodeid 不得无解释消失；不把通过数“必须等于 1671”当新候选判据。mypy 保留现有 override／排除和 `check_untyped_defs=false` 的限制，不宣称全代码严格类型无误。

- [ ] 前端在源码副本使用现有 lockfile／已验证 npm 缓存独立安装，缺包走 B 下载单，不复制真实 `.env.local`／node_modules，不修改 lockfile来绕过冲突：

```powershell
Set-Location (Join-Path $sourceRoot 'frontend')
npm ci --offline --no-audit --no-fund
npm run lint
npm exec --offline -- tsc --noEmit
npm run test
npm run build
```

预期各项 rc=0。Vitest 覆盖 `frontend/tests` 的 SSE、scope、原文卡状态／API 和标注等既有测试；这不等于浏览器真实交互、无障碍和生成回答端到端已验。本轮不设计新 UI 或补一整套浏览器测试平台。

- [ ] 在新的候选环境中取新依赖审计；实际读取输出内容，区分“有漏洞”“依赖收集失败”“无可审计分发”和“查询故障”：

```powershell
Set-Location (Join-Path $sourceRoot 'backend')
& $py -m pip_audit --format=json --output (Join-Path $evidence 'installed-audit.json')
# 下行会通过 pip 建临时解析环境并可能下载分发包；只有 Owner 已明确允许该解析取包时才执行。
& $py -m pip_audit -r (Join-Path $sourceRoot 'backend\requirements.txt') --format=json --output (Join-Path $evidence 'runtime-resolution-audit.json')
```

第二条按范围解析出的树可能与实装约束树不同，必须分别登记，不能混分母。只读查询漏洞数据库／官方公告可以进行；**下载或在线安装包仍受 B 的边界约束，不能借审计命令绕过**。未获解析取包许可时，第一条照做，第二条登记为“声明需求解析审计待验”，不得把它报成已通过远端 CI；本地限定接受时一并交 Owner 裁定。`torch==2.6.0+cpu` 若被跳过，另以精确 `torch==2.6.0` 单行审计输入执行 `pip_audit -r 输入文件 --no-deps --disable-pip --format=json --output 输出文件`（输入为 `$evidence/torch-upstream.txt`，输出为 `torch-upstream-audit.json`），并用官方公告核对 CPU 变体适用性。跳过不是零漏洞；独立通报按 alias 归并，原始条目和漏洞包数量分别报告。

- [ ] 用最终环境更新风险材料：包／版本、官方出处和查询日期、实际可达路径、利用前提、未验证面、最小处置、Owner 接受用途与失效条件。不能用“离线／本地”一词把所有模型文件反序列化风险判为不存在。未解除风险可以申请限定本地接受，但 **CI 审计仍红就明确红，不改 CI 成绿**。
- [ ] 跑一次 rerank 关闭的真实公开库快速烟测：

```powershell
$env:CHROMA_DIR = $publicKb
$env:RERANK_ENABLED = 'false'
& $py (Join-Path $sourceRoot 'backend\scripts\smoke_citation_fast.py')
```

预期 **24 项断言＝意图 7＋召回 7＋引用校验 3＋复杂度 4＋自检 3**，rc=0。只有 7 个实际检索问句，不是 24 个真实模型题。记录语料和脚本 hash，空库／伪造召回不算。

### E2. 轮换确认后的一轮真实 rerank

**最新补记：最终声明环境新授权已按§0.5执行完，E2限定验收通过。** 下方保留前置流程和历史代码供审查，不是允许重跑的入口；第四轮标记保留，未来追加真实轮次仍需另授权。

**第三轮局部授权已执行完毕，非新的执行许可。** Owner批准的系统级主凭据入口及32项安全测试在 `C:/Users/33393/Desktop/legal-rerank-round3-20261002-cebf70a641c549f9ad44c27cf27261a9/evidence`；实际结果见§0.1／报告§9。下方及附录的文件凭据入口是原始基线，不会选中系统新值，**不得原样再次执行真实调用，也不得把第三轮结果当成该旧入口通过**。未来完整候选若需要真实复验，先明确凭据唯一来源和新一轮授权，在最终声明环境复验对应包装器，不复制系统密钥到.env。其余预算／公开白名单／新账本／日志保护要求仍适用。

- [ ] 先取得 Owner 对暴露的主／备 rerank 凭据撤销／轮换的本机确认。仅内存读取新 rerank 所需 key 和非敏感 endpoint／模型配置；不把原 `.env` 复制到源码，不解开 LLM／云端嵌入 key。无确认则标 **BLOCKED-CREDENTIAL**，E1 可交付。
- [ ] 在 `$evidence/rerank-approved.json` 记录 **D 审核后的** 正文 SHA-256 数组 `documents_sha256`、已核对的 HTTPS rerank 完整 URL 数组 `urls`、实际模型序列数组 `models` 和原快速烟测 `script_sha256`。它不含正文、key或长度。URL 不准含 userinfo／query；与官方／既有配置不符先 grilling，不接受任意自定义收集端点。审核项来自 D 与配置核对，不能从即将发送的请求反向生成白名单。
- [ ] 用附录代码创建 `$evidence/rerank-acceptance.py` 这个仅用于本轮的薄包装，不改产品代码、不新建评测框架。包装调用原烟测 `main()`；题集不变。使用全新进程、D 的公开库、本地嵌入、独立空配额账本，并逐问清检索缓存；不能用热缓存顶替实际调用。
- [ ] 真实调用前，用假 key／本地假传输验证包装器：预算超限会拒发、非白名单 endpoint 不发、私有正文不发、SDK 重试关闭、异常不会输出请求／响应全文或凭据。至少包含附录的负例；向假传输接通实际 `Client.send` 包装，确认拒发时底层发送次数为0。只在隔离测试副本撤掉预算／正文拒绝来观察对应断言真红，再复原复验，禁止变异测试使用真实配置；不要把假传输结果列为真实 rerank 成绩。
- [ ] **上限约束真实 HTTP 请求数 ≤21，一轮、无外层重试。** 执行前按固定 7 检索问句及实际模型列表计算理论尝试数，超过 21 则请 Owner 重新定预算，不能静默截成另一套模型策略。公开文档池总字符／估算 token 和平台剩余额度只用于预算预检；估算不当作真实账单，不猜当前价格。

关键补正：当前 `retrieval._get_rerank_client()` 未显式设 `max_retries`，2026-10-02 用无联网假配置读取现有 SDK 得到默认 **2**。因此“脚本无重试、7×3 模型”不能证明最多 21 个 HTTP 请求。包装器对实际 SDK client 使用 `client.with_options(max_retries=0)` 并交回同一 rerank 路径；原生 httpx 和 SDK 路径都要在实际发送边界计数、限域、检查即将发送的 query／documents。拦截时拒发而不是伪造响应；预算被拒或出现降级要写未通过。本轮不更改产品默认重试策略，报告明示该差异，不能据此宣称生产重试／超时策略已验。

- [ ] 包装器仅允许已核对的 rerank POST endpoint；逐次记录问句序号、公开正文 SHA-256（可由 D 的清单追溯 ID）、模型、真实发送数和 HTTP 状态／异常类型；逐问记录有效重排或未通过。不要记录 header、key、请求／响应正文，也不要原样转储可能携带响应体的异常。禁止把真实配置 `model_dump()` 写日志。
- [ ] 每个检索问句都须证实走到真实 rerank、获得有效排序而非 `None`／余弦降级；另外保留原脚本的 24/24、7/7 联合召回判据。即便 24/24，零真实调用、429／超时／坏 key 降级、无有效 results 都不能叫“rerank 验收通过”。一次出现阻塞／失败后先报告原因，不自动多轮凑通过。
- [ ] 调用前后复核原保护对象，使用本轮新日志路径：

```powershell
& $py (Join-Path $repo 'dispatch-output\local-candidate-closeout-20260928\verify-protected.py') (Join-Path $evidence 'protected-rerank-before.log')
# 仅执行一次已通过假传输自检且获准联网的包装器。
& $py (Join-Path $evidence 'rerank-acceptance.py') $sourceRoot $publicKb (Join-Path $evidence 'rerank-approved.json') (Join-Path $repo 'backend\.env')
& $py (Join-Path $repo 'dispatch-output\local-candidate-closeout-20260928\verify-protected.py') (Join-Path $evidence 'protected-rerank-after.log')
```

先确认旧保护清单仍完整、前测无缺失／改变；若原库已有合法新状态则先重新对齐保护基线，不覆盖历史清单。调用后源 Chroma 整目录指纹也必须和 D 的原源指纹一致。

包装器用 `$evidence/rerank-round.started` 的独占创建标记本轮已启动，不依赖可能根本未创建的配额库。成功／失败都保留标记，不删除它来重跑；确需下一轮须先取得 Owner 新授权并使用新轮次路径。原烟测 `main()` 成功返回 `None`，失败抛 `SystemExit(1)`；包装器必须遵循这个真实接口，而不是只在返回 `0` 的假脚本上自证。

### E3. Linux／远端 CI 的诚实边界

- [ ] 核对本机是否有已下载的 Linux CPU 依赖／Python 3.11 镜像和离线 BGE 缓存。若具备，可在**新临时容器**复验 E1 的后端 lint／类型／非 slow 覆盖率；只挂实验源码、已审公共模型缓存和 Linux wheelhouse，不用 compose、不挂原库／`.env`／日常 venv，测试时网络关闭。先按实际可用镜像 ID 和 mount 绝对路径写命令再执行，不隐式 pull；容器内新库由容器自身创建。
- [ ] 仅有 Windows wheels 不足以跑 Linux。资源不具备则列下载前置，并报告 **Linux 未验**；不把 Windows 结果当 CI。不要新增 CI 工作流、触发远端执行或为此 push。
- [ ] 本地 Linux 测试也不等于远端 CI，尤其依赖审计仍有风险时。Owner 可以明示接受“仅本地 Windows 用途，Linux／远端待验”的限制；没有该裁定不能把缺腿的材料写成完整候选已接受。

## F. 主代理复核、风险裁定材料与可恢复交付

**产物：** 主仓的新报告、仓外候选包／指纹／复验索引；不自动提交。

- [ ] 主代理自查白名单差异：与 902e2d1 比较整个实验源码，确认没有缓存倒退、旧 pytest pin、nullable 类型丢失、测试删减、冻结哈希改变或未批准改动。不要只按 diff 文件数判断相同。核对集合以基线归档的源文件清单加两只新增测试为准；mypy／Ruff 缓存、frontend 的 node_modules／`.next` 等安装／运行生成物另列并排除交付，不能把它们当源码差异，也不能借排除生成物漏查其他新增业务文件。
- [ ] 重新核对实装版本满足两份直接需求及实验约束；最终源码 hash、依赖／工具版本、公开语料 hash、脚本和 nodeid 集必须绑定到同一验收轮。覆盖率、召回率和风险计数各自注明分母。
- [ ] 为准备用于本地交付的精确文件集合做凭据／文件卫生检查：当前八个在册 key 按值只在内存比对，缺键／读取不全即无结论；另做形状检查并逐项归因。值、长度、匹配片段不输出。`b_worktree_value_scan.py` 的全工作区 rc=0 仅表示扫描完整，**不是交付集合零凭据**；不运行它冒充暂存／历史扫描。只查本轮交付范围，不趁机全盘审计。
- [ ] 组织新包：最小补丁、变更／冻结文件指纹、requirements／约束／实装元数据、脱敏日志、独立公开语料的复验指纹、风险原始 JSON 和命令索引。固定基线归档含历史HNSW数据，按§0.2只留受控本地来源，不直接打进转发包；安全且可恢复的最终文件集合单列验收。实际 DB及索引数据、模型权重、私有快照、真实 `.env`／key、node_modules、运行生成文件不入源码／可转发证据包；公开法规库另存仓外受控路径，不提交 Git。
- [ ] 在新空目录验证基线归档解包、最小补丁应用以及源码文件清单／hash与已验对象一致；证据路径相对包根解析，不依赖还存在的 TEMP。保留证据所需 mtime，不用复制时间伪造“日志晚于代码”；不要求重跑所有重型测试来证明解包成功。
- [ ] 将 B／E 的当前风险和 Linux 限制交 Owner 作 D2 本地用途裁定：接受／不接受、实际包范围、期限、限制、失效条件、未解决事项。签字栏只写 Owner 的真实答复出处，草案不算签字，不自动改 2026-10-05。
- [ ] 在新报告分列已做、未做、阻塞、Owner 待答；原报告的 §20 及旧计划保留历史。不宣称生成回答法律质量、完整用户交互或生产就绪已通过。本轮不跑 `smoke_citation_full.py`、生成语料、真实入库、服务器部署或发布操作。
- [ ] 结束时重取主仓 HEAD／所有引用／原脏文件和冻结文件指纹，与 A 比较：没有额外授权时主仓代码与引用应未变，只新增本书执行报告；用户未提交内容保留。不要因本地包完整就提交全部仓内产物。

### F1. 完成判据与结论模板

完成项必须有本次日志与对象指纹，不能勾选“尝试过”代替通过。

| 必需项 | 合格标准 |
|---|---|
| 最小整合 | 两个版本／PDF 错误处理和两只测试，未批准差异 0；已提交缓存安全修复保留 |
| 环境一致 | 独立安装成功、pip check=0；直接需求与实装一致，pytest≥9.0.3且<10，CPU torch 变体明确 |
| 离线门禁 | 后端／守卫／前端命令均通过，覆盖率≥70%，既有用例不无故减少 |
| 语料安全 | 一致副本可恢复、公开子集审查完成、源库整目录指纹未变、无私有数据外发 |
| 检索／rerank | 同一冻结语料的离线烟测24/24；条件实际满足后真实一轮24/24，7个检索均有有效真实重排，实际HTTP≤21，无凑数重试 |
| 风险裁定 | 新审计无查询／收集伪绿；残余风险、跳过项、Linux限制明列，Owner已裁本地用途且未失效 |
| 证据交付 | 可恢复到已验源码、依赖／语料／日志可追溯、交付内容不含凭据／私有数据；不依赖 TEMP |

只允许以下三种结论：

1. **本地候选收口完成**：上表满足，Owner 的本地用途风险限制随包附上。若依赖残余风险被限定接受，明确写“有条件接受”，**不是安全零风险，也不是可以上线**；Linux／远端缺口不能隐藏。
2. **实验技术材料完成，候选接受待裁**：技术项完成，但 D2／限定用途或期限未决。不是整个阶段完成。
3. **部分完成，明确阻塞**：凭据、语料一致窗口、依赖缓存／兼容性、真实 rerank 或其他必需项未通过；逐项写哪个任务可继续、需要 Owner 做什么。

本地提交、合 master、远端 CI、push 和部署不是上表的默认完成条件。若 Owner 另批准本地提交／合入，须先给出精确来源、文件／提交集合、前置门禁、与旧候选区别，重新检验当前主仓并仅处理批准对象。

## 4. 本阶段之后：只列入口，不执行

- **远端／发布准备与发布：** 再裁公开内容、留出集／会话痕迹、历史或无父快照路线、本地／远端历史关系、当前／旧凭据复扫和精确 push 对象。历史原本无共同祖先的结论需新核对，不 force、不合并无关历史，不用本书授权推送。
- **真实知识库变更：** 另批准写入范围、一致备份、恢复验证和回退；本阶段的副本验收不是原库写权限。
- **生成回答与真实交互验收：** 若要进发布阶段，再批准含生成调用的 12 场景 `smoke_citation_full.py`、成本／隐私边界及关键浏览器流程。当前24项快速烟测不替代它们。
- **部署：** Owner 选好服务器后再定系统资源、域名／TLS、凭据、备份、监控与回滚；现在不选云商、不购机器、不启动生产部署。

## 附录：E2 的一次性测量代码

这里只给测量脚本，**现在不创建／运行它**。执行时通过 `apply_patch` 保存到 §E2 的仓外路径；不放入产品目录。不因这里提供了代码就省略假传输自检。

`rerank-acceptance.py`：

```python
import hashlib
import importlib.util
import json
import logging
import os
import sys
from pathlib import Path
from urllib.parse import urlsplit


def require(ok, reason):
    if not ok:
        raise RuntimeError(reason)


def text_sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class RerankGate:
    def __init__(self, approved):
        self.urls = set(approved["urls"])
        self.models = set(approved["models"])
        self.hashes = set(approved["documents_sha256"])
        self.calls = 0
        self.rejected = 0
        self.query = None
        self.documents = None

    def reject(self):
        self.rejected += 1
        raise RuntimeError("rerank request rejected")

    def context(self, query, documents):
        self.query, self.documents = None, None
        if not isinstance(query, str) or not query or not documents:
            self.reject()
        if any(not isinstance(d, str) or text_sha(d) not in self.hashes for d in documents):
            self.reject()
        self.query, self.documents = query, list(documents)

    def allow(self, request):
        if request.method != "POST" or str(request.url) not in self.urls or self.calls >= 21:
            self.reject()
        try:
            body = json.loads(request.read())
            data = body.get("input", body)
            valid = (
                self.query is not None and body.get("model") in self.models
                and data.get("query") == self.query and data.get("documents") == self.documents
            )
        except Exception:
            self.reject()
        if not valid:
            self.reject()
        self.calls += 1
        return body["model"]


def main():
    # 此入口只在 Owner 轮换确认、批准名单和假传输自检之后调用。
    logging.disable(logging.CRITICAL)  # 不让 SDK／降级异常原文进入本轮输出。
    require(len(sys.argv) == 5, "invalid argument count")
    source, public_kb, approval_path, env_path = [Path(a).resolve() for a in sys.argv[1:]]
    task_root = Path(__file__).resolve().parent.parent
    require(source == task_root / "source" and public_kb == task_root / "public-kb", "invalid isolated paths")
    require(public_kb.is_dir() and not (source / "backend" / ".env").exists(), "unsafe source directory")
    require(approval_path == task_root / "evidence" / "rerank-approved.json", "invalid approval path")
    round_marker = task_root / "evidence" / "rerank-round.started"
    require(not round_marker.exists(), "round already started")
    approved = json.loads(approval_path.read_text(encoding="utf-8"))
    require(isinstance(approved, dict), "invalid approval format")
    for field in ("urls", "models", "documents_sha256"):
        values = approved.get(field)
        require(isinstance(values, list) and values and all(isinstance(v, str) and v for v in values), "invalid approval entries")
        require(len(values) == len(set(values)), "duplicate approval entries")
    for url in approved["urls"]:
        parsed = urlsplit(url)
        require(parsed.scheme == "https" and parsed.hostname, "invalid endpoint scheme")
        require(not parsed.username and not parsed.password and not parsed.query and not parsed.fragment, "unsafe endpoint components")
    smoke_path = source / "backend" / "scripts" / "smoke_citation_fast.py"
    require(hashlib.sha256(smoke_path.read_bytes()).hexdigest() == approved.get("script_sha256"), "smoke script changed")
    from dotenv import dotenv_values

    config = dotenv_values(env_path, interpolate=False)
    for key in ("RERANK_API_KEY", "SILICONFLOW_API_KEY", "RERANK_BASE_URL", "RERANK_NATIVE_URL", "RERANK_MODEL", "RERANK_MODELS"):
        os.environ.pop(key, None)  # 不让终端旧值补齐／覆盖本次核对的配置。
        value = config.get(key)
        if value is not None:
            require(isinstance(value, str) and "${" not in value and "\n" not in value and "\r" not in value, "invalid rerank config")
            os.environ[key] = value  # 保留明确的空值，例如只用单模型时的 RERANK_MODELS。
    require(os.environ.get("RERANK_API_KEY") or os.environ.get("SILICONFLOW_API_KEY"), "missing rerank credential")
    os.environ.update(
        RERANK_ENABLED="true", CHROMA_DIR=str(public_kb), EMBEDDING_PROVIDER="local",
        QUERY_REWRITE_ENABLED="false", RERANK_QUOTA_TOTAL="0", RERANK_QUOTA_TOTALS="",
        RERANK_QUOTA_INITIAL="0", EMBEDDING_QUOTA_TOTAL="0", EMBEDDING_QUOTA_INITIAL="0",
        DATABASE_URL="sqlite:///" + (task_root / "rerank-app.db").as_posix(),
        QUOTA_DB=str(task_root / "rerank-quota.sqlite"),
    )
    require(not (task_root / "rerank-quota.sqlite").exists(), "quota ledger is not fresh")
    sys.path.insert(0, str(source / "backend"))
    import httpx
    import quota_utils
    import retrieval

    require(quota_utils.rerank_model_list() == approved["models"], "model sequence changed")
    require(7 * len(approved["models"]) <= 21, "theoretical budget exceeded")
    sdk = retrieval._get_rerank_client()
    require(sdk is not None, "rerank client unavailable")
    retrieval._rerank_client = sdk.with_options(max_retries=0)
    require(retrieval._rerank_client.max_retries == 0, "SDK retries remain enabled")
    spec = importlib.util.spec_from_file_location("candidate_fast_smoke", smoke_path)
    smoke = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(smoke)
    questions = [case[0] for case in smoke.RETRIEVAL_CASES]
    require(len(questions) == 7 and len(set(questions)) == 7, "unexpected question set")
    gate = RerankGate(approved)
    original_send = httpx.Client.send
    original_retrieve, original_rerank = retrieval.retrieve, retrieval._rerank_docs
    state = {"index": None}
    seen, outcomes, sends = set(), {}, []

    def guarded_send(client, request, **kwargs):
        model = gate.allow(request)
        kwargs["follow_redirects"] = False  # 一个 send 不跟随重定向追加请求。
        row = {
            "case": state["index"], "model": model, "attempt": gate.calls,
            "documents_sha256": [text_sha(d) for d in gate.documents],
        }
        sends.append(row)
        try:
            response = original_send(client, request, **kwargs)
            row["status"] = response.status_code
            return response
        except Exception as exc:
            row["error_type"] = type(exc).__name__
            raise

    def traced_retrieve(query, *args, **kwargs):
        require(query in questions and query not in seen, "unexpected retrieval")
        seen.add(query)
        state["index"] = questions.index(query)
        retrieval.invalidate()
        return original_retrieve(query, *args, **kwargs)

    def traced_rerank(query, docs, **kwargs):
        require(state["index"] is not None, "rerank outside a test case")
        gate.context(query, [d.page_content for d in docs])
        before = gate.calls
        result = original_rerank(query, docs, **kwargs)
        valid = (
            gate.calls > before and isinstance(result, list) and len(result) == len(docs)
            and {id(d) for d in result} == {id(d) for d in docs}
        )
        outcomes.setdefault(state["index"], []).append(valid)
        return result

    with round_marker.open("x"):  # 原子创建；任何第二次启动都不能再进入实际发送。
        pass
    httpx.Client.send = guarded_send
    retrieval.retrieve, retrieval._rerank_docs = traced_retrieve, traced_rerank
    run_error_type = None
    try:
        try:
            smoke_rc = smoke.main()
        except SystemExit as exc:
            smoke_rc = exc.code
        except Exception as exc:
            smoke_rc = 1
            run_error_type = type(exc).__name__  # 保留发送计数，不输出异常参数。
    finally:
        httpx.Client.send = original_send
        retrieval.retrieve, retrieval._rerank_docs = original_retrieve, original_rerank
        retrieval._rerank_client.close()
    passed = (
        smoke_rc in (None, 0) and len(seen) == 7 and set(outcomes) == set(range(7))
        and all(outcomes[i] == [True] for i in range(7)) and gate.rejected == 0
        and 0 < gate.calls <= 21
    )
    cases = [{"case": i, "valid_rerank": outcomes.get(i) == [True]} for i in range(7)]
    print(json.dumps({"http_attempts": gate.calls, "rejected": gate.rejected, "valid_rerank_cases": sum(v == [True] for v in outcomes.values()), "passed": passed, "error_type": run_error_type, "cases": cases, "sends": sends}))
    return 0 if passed else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print("FATAL: " + type(exc).__name__)  # 不转储异常参数、请求、响应或配置。
        raise SystemExit(1) from None
```

前置 E0 仍须运行；此脚本只追加所需 rerank 配置，不接收口令／key命令行参数。HTTP 计数在禁止 SDK 重试、禁止 redirect 的实际发送边界进行，连接失败也作为一次尝试保守计数；底层传输不得另启 retry。若新环境／代理改变该假设，先在假传输自检中明确约束为0；无法证明则暂停实际调用，不能宣称预算受控。

`test_rerank_acceptance.py` 的判据代码（下一段也加入同文件，连接实际包装入口与假传输）：

```python
import importlib.util
from pathlib import Path

import httpx
import pytest

spec = importlib.util.spec_from_file_location("rerank_acceptance", Path(__file__).with_name("rerank-acceptance.py"))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
URL = "https://fixture.invalid/rerank"


def make_gate():
    gate = module.RerankGate({"urls": [URL], "models": ["fixture-model"], "documents_sha256": [module.text_sha("public-law")]})
    gate.context("fixed-query", ["public-law"])
    return gate


def request(url=URL, query="fixed-query", documents=None):
    return httpx.Request("POST", url, json={"model": "fixture-model", "query": query, "documents": ["public-law"] if documents is None else documents})


def test_exact_budget():
    gate = make_gate()
    for _ in range(21):
        assert gate.allow(request()) == "fixture-model"
    with pytest.raises(RuntimeError):
        gate.allow(request())
    assert gate.calls == 21 and gate.rejected == 1


@pytest.mark.parametrize("url,query,documents", [("https://private.invalid/rerank", "fixed-query", ["public-law"]), (URL, "private-query", ["public-law"]), (URL, "fixed-query", ["private-document"])])
def test_unapproved_payload_never_allowed(url, query, documents):
    gate = make_gate()
    with pytest.raises(RuntimeError):
        gate.allow(request(url, query, documents))
    assert gate.calls == 0 and gate.rejected == 1


def test_private_context_is_rejected():
    gate = make_gate()
    with pytest.raises(RuntimeError):
        gate.context("fixed-query", ["private-document"])
    assert gate.calls == 0


def test_native_nested_body_is_allowed():
    gate = make_gate()
    nested = httpx.Request("POST", URL, json={"model": "fixture-model", "input": {"query": "fixed-query", "documents": ["public-law"]}})
    assert gate.allow(nested) == "fixture-model"


def test_rejected_context_cannot_reuse_old_public_context():
    gate = make_gate()
    with pytest.raises(RuntimeError):
        gate.context("fixed-query", ["private-document"])
    with pytest.raises(RuntimeError):
        gate.allow(request())
    assert gate.calls == 0
```

同文件追加：

```python
import json
import sys
from types import SimpleNamespace

from openai import OpenAI


def fake_round(tmp_path, monkeypatch, *, status=200, document="public-law", endpoint="https://fixture.invalid/v1", native=False, smoke_exit=None):
    evidence = tmp_path / "evidence"
    backend = tmp_path / "source" / "backend"
    scripts = backend / "scripts"
    public_kb = tmp_path / "public-kb"
    for directory in (evidence, scripts, public_kb):
        directory.mkdir(parents=True)
    smoke = scripts / "smoke_citation_fast.py"
    smoke.write_text(
        'RETRIEVAL_CASES = [(f"q{i}",) for i in range(7)]\n'
        'def main():\n'
        '    from retrieval import retrieve\n'
        '    for case in RETRIEVAL_CASES:\n'
        '        retrieve(case[0], k=6)\n'
        + ('    return None\n' if smoke_exit is None else f'    raise SystemExit({smoke_exit})\n'), encoding="utf-8",
    )
    env = tmp_path / "fixture.env"
    env.write_text("RERANK_API_KEY=fixture-only-key\nRERANK_MODELS=fixture-model\n", encoding="utf-8")
    approval = evidence / "rerank-approved.json"
    approval.write_text(json.dumps({
        "urls": ["https://fixture.invalid/v1/rerank"], "models": ["fixture-model"],
        "documents_sha256": [module.text_sha("public-law")],
        "script_sha256": module.hashlib.sha256(smoke.read_bytes()).hexdigest(),
    }), encoding="utf-8")
    physical = []

    def transport(request):
        physical.append(request)
        headers = {"Location": "https://private.invalid/redirect-target"} if status == 301 else {}
        return httpx.Response(status, headers=headers, json={"ok": True, "error": "fixture-response-body"})

    client = httpx.Client(transport=httpx.MockTransport(transport))
    sdk = OpenAI(api_key="fixture-only-key", base_url=endpoint, http_client=client)
    retrieval = SimpleNamespace(_rerank_client=sdk, invalidate=lambda: None, _get_rerank_client=lambda: sdk)

    def rerank(query, docs, **kwargs):
        try:
            data = {"query": query, "documents": [d.page_content for d in docs]}
            if native:
                received = client.post(endpoint + "/rerank", json={"model": "fixture-model", "input": data})
                received.raise_for_status()
                response = received.json()
            else:
                response = retrieval._rerank_client.post("/rerank", body={"model": "fixture-model", **data}, cast_to=dict[str, object])
            return docs if response.get("ok") else None
        except Exception:
            return None

    retrieval._rerank_docs = rerank
    retrieval.retrieve = lambda query, **kwargs: retrieval._rerank_docs(query, [SimpleNamespace(page_content=document)])
    monkeypatch.setitem(sys.modules, "retrieval", retrieval)
    monkeypatch.setitem(sys.modules, "quota_utils", SimpleNamespace(rerank_model_list=lambda: ["fixture-model"]))
    monkeypatch.setattr(module, "__file__", str(evidence / "rerank-acceptance.py"))
    monkeypatch.setattr(module.logging, "disable", lambda level: None)
    monkeypatch.setattr(sys, "argv", [module.__file__, str(tmp_path / "source"), str(public_kb), str(approval), str(env)])
    return physical


@pytest.mark.parametrize("native", [False, True])
def test_real_wrapper_reaches_only_fake_transport(tmp_path, monkeypatch, capsys, native):
    physical = fake_round(tmp_path, monkeypatch, native=native)
    assert module.main() == 0
    assert len(physical) == 7
    output = capsys.readouterr().out
    assert '"valid_rerank_cases": 7' in output
    assert '"documents_sha256":' in output
    assert "fixture-only-key" not in output and "fixture-response-body" not in output


@pytest.mark.parametrize("status", [301, 429, 500])
def test_real_wrapper_no_sdk_retry_and_no_false_pass(tmp_path, monkeypatch, capsys, status):
    physical = fake_round(tmp_path, monkeypatch, status=status)
    assert module.main() == 1
    assert len(physical) == 7  # actual SDK max_retries=0; not 21 mock requests
    output = capsys.readouterr().out
    assert '"passed": false' in output
    assert '"rejected": 0' in output
    assert "fixture-only-key" not in output and "fixture-response-body" not in output


def test_real_wrapper_rejects_private_document_before_send(tmp_path, monkeypatch):
    physical = fake_round(tmp_path, monkeypatch, document="private-document")
    assert module.main() == 1
    assert len(physical) == 0


def test_real_wrapper_rejects_other_endpoint_before_send(tmp_path, monkeypatch):
    physical = fake_round(tmp_path, monkeypatch, endpoint="https://private.invalid/v1")
    assert module.main() == 1
    assert len(physical) == 0


def test_existing_round_marker_prevents_send(tmp_path, monkeypatch):
    physical = fake_round(tmp_path, monkeypatch)
    (tmp_path / "evidence" / "rerank-round.started").touch()
    with pytest.raises(RuntimeError, match="round already started"):
        module.main()
    assert len(physical) == 0


def test_smoke_system_exit_is_failure_with_summary(tmp_path, monkeypatch, capsys):
    physical = fake_round(tmp_path, monkeypatch, smoke_exit=1)
    assert module.main() == 1 and len(physical) == 7
    assert '"passed": false' in capsys.readouterr().out


def test_wrong_source_is_rejected_even_with_python_optimization(tmp_path, monkeypatch):
    code = Path(module.__file__).read_text(encoding="utf-8")
    physical = fake_round(tmp_path, monkeypatch)
    namespace = {"__file__": module.__file__, "__name__": "optimized_plan_check"}
    exec(compile(code, module.__file__, "exec", optimize=1), namespace)
    arguments = list(sys.argv)
    arguments[1] = str(tmp_path / "wrong-source")
    monkeypatch.setattr(sys, "argv", arguments)
    with pytest.raises(RuntimeError, match="invalid isolated paths"):
        namespace["main"]()
    assert len(physical) == 0
```

自检命令：`& $py -m pytest -q (Join-Path $evidence 'test_rerank_acceptance.py')`。测试只用假数据，不读取真实配置；该命令不能替代 E2 的真实结果。新 helper 的自检、预算预检或日志／过滤器有任何一项不足时，交付“零真实调用”的阻塞说明，不让助手自行拿真实请求试探。

夹具使用带类型参数的 `dict[str, object]` 来构造可解析的 SDK 假成功，只证明包装器的计数／过滤／接线。它**没有改动或验证产品中的裸 `cast_to=dict`**；该兼容风险仍按 B 登记和处理。真实验收只证明本轮实际走到的有效路径，不证明批准名单中每个模型都成功，更不证明生产默认重试配置已验。

## 5. 编写者自查（2026-10-02，非执行成绩）

- [x] 已覆盖 Owner 的两个 A 决策；正文不包含 push／真实库写入／部署执行。
- [x] 将已提交13文件修复与未移入候选分开，排除旧候选缓存／pytest倒退。
- [x] 核对现有实装版本，识别 pytest8.4.2 与主线≥9.0.3不一致，要求新环境绑定最终需求。
- [x] 核对快速烟测是24断言／7检索；补上真实HTTP预算和SDK默认重试差异。
- [x] 明列 D2／凭据／一致窗口／缺缓存／Linux 停点，不代签、不延期限、不制造签字与离线实验死锁。
- [x] 采用四个实验源码文件的最小改动、既有门禁和一次性薄包装；不新增业务模块、部署系统或评测框架。
- [x] 文中15个PowerShell代码块通过语法解析，5个Python代码块通过静态语法解析；无尾随空白。另做附录假传输行为复核，结果与限制见下节；不计为项目门禁成绩。

以上复选框只表示本书编写检查完成；A–F最新实际执行见§0.5和本轮报告。pypdf6.19.0技术复验和最终环境E2限定真实验收已完成；风险／其他未验面／最终接受停点仍开放，不能因技术检查点通过而自动勾选。

## 6. 二次复核记录（2026-10-02，仅计划及假传输）

结论：范围和 A–F 主线保持成立；本次修订执行细节，不授权实施。没有新增业务模块、锁包体系、CI 工作流或部署任务，仍可由一名助手顺序执行。

- 隔离配置前置至 C／D 之前，清除继承的优化开关与 per-model 配额；命令失败先停，不把多行代码块无条件整块执行。
- 两个执行脚本改用显式异常及固定隔离路径检查，原库不能误传为复制源；这些检查不能被 Python 优化开关移除。
- 修正真实烟测成功返回 `None` 的接线；烟测退出失败也保留脱敏计数。用独占轮次标记防止重复调用，不靠空配额库存在性判断。
- 记录每次公开正文 hash 和逐问结果，补 SDK／原生 httpx、重定向、重复启动、优化模式等假传输判据。
- 明确 `pip_audit -r` 可能取包，未经下载授权不运行该解析审计；已实装审计与声明解析审计分别报告。
- 将 OpenAI SDK 的裸 `cast_to=dict` 兼容问题列为 B 的已复现线索，**未修产品代码**；需要扩大源码白名单时仍先向 Owner 对齐。
- 将 CRLF 主仓工作文件和 LF Git 归档的冻结 hash 分列，避免未修改的 `state_machine.py` 被误报为变更；不改写文件来对齐 hash。

**本轮证据与限制：** 附录脚本和测试按文档原文提取至仓外诊断目录 `C:/Users/33393/AppData/Local/Temp/legal-plan-review-20261002-66eb583194d541188ded2852cae99792`。用 §1 的现有隔离 Python 执行 `-B -m pytest -q --noconftest -p no:cacheprovider` 加该目录下 `after/test_rerank_acceptance.py`，结果 **17 passed，rc=0**；同一夹具对初稿包装器定向运行 `-k 'reaches_only_fake_transport or existing_round_marker'`，观察到 **3 个功能性失败**：SDK／原生的成功误判两例，以及已启动标记未阻止发送一例。期望为独立固定 fixture；HTTP 仅到 `MockTransport`，不读真实 `.env`、不导入真实检索／知识库模块。包装器的错源拒发测试包含优化编译；原始输出保留在该目录的 `before-tests.log`／`after-tests.log`。

这只证明附录的特定测量行为；工具环境仍是历史 pytest8.4.2／OpenAI1.109.1，不证明新候选声明环境、PDF 整合、真实检索／rerank、最新依赖审计或 A–F 完成。后续执行须在 B／C 的最终环境重跑附录自检；测试代码已完整保留在本文，不依赖诊断 TEMP 继续存在。

复制工具另用标准库与假 Chroma client 做路径负例：普通／优化编译两种模式各检查错源、错目标、错 ID 清单，共 **6 个拒绝，Chroma client 调用 0**；未导入实际 Chroma 库、未执行语料复制或恢复。命令为 §1 的 Python 加诊断目录的 `copy-path-check.py`、本文绝对路径、诊断目录绝对路径，输出保留在 `copy-path-check.log`。这仅验证输入边界，不替代 D 的实际一致性／逐条指纹验收。
