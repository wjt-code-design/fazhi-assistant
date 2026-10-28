# 本地候选后续任务 Implementation Plan（2026-10-04）

> **For agentic workers:** REQUIRED SUB-SKILL: 使用 `executing-plans` 按任务及审批门执行；先读适用的 `AGENTS.md`。默认由收到本文件的助手单会话推进，不自行派发或创建其他会话；Owner另指定并发助手时才按本书分工。步骤复选框表示本轮待办，不重做旧删包／setuptools／联合验收。技术未知先查证；业务裁定用 grilling 一次一个问题，并提供推荐项。Owner 已要求普通范围选择按推荐方案推进，但这不代替下载许可、风险签署或提交授权。所需skill不可用时说明限制，以本书的权限、停点和证据纪律为准，不安装skill绕路。

> **接手方式：** 同一电脑能访问下列项目／冻结输入时，只收到本文件的完整路径即可开始T0及T1–T3只读准备。其他链接是证据，不是要求再执行的计划。收到文件本身不批准T4之后的下载／实验。本文不是可搬到另一台电脑直接运行的源码、环境或数据包；指定输入缺失时报告准确路径并停在相关任务，不用当前脏工作区或真实库顶替。

**Goal:** 补齐剩余依赖处置和应用验收材料，形成对象明确、风险可裁定的本地候选；不是发布上线或清零一切依赖的承诺。

**Architecture:** 保留已验联合候选。模型风险、Chroma 风险与启动验收准备分别只读推进，再由一个执行者冻结一致依赖集合；审批后分案实验，成立后联合验收。保持现有 RAG／agent 架构，不引入新框架、服务化数据库或额外测试平台。

**Tech Stack:** Windows／PowerShell、Python 3.11 CPU、FastAPI、LangChain 拆分包、Chroma、本地 BGE、Next.js／Vitest、pytest／Ruff／mypy／pip-audit、现有浏览器工具。

## 全局边界与固定输入

- 项目根 `C:/Users/33393/Desktop/ai-legal-helper`；本轮主线锚点 `902e2d161e67100ed6d267a08c393538a0abe109`。开工发现 HEAD／refs 或受保护对象变化，先判断新的已授权工作，不刷新旧证据、不回滚他人修改。
- 受保护联合候选 `C:/Users/33393/Desktop/fazhi-joint-candidate-20261003-ac701f4a880441b5a453b1b7cbb06f01`，以下称“联合根”。其 `source`／`venv`／`evidence` 不改写、不添新测试产物。Python 3.11.0／Windows amd64，162 实装分发／165 约束是上一轮状态，不是本轮新验收。
- 联合 requirements SHA-256 `594b9e664f1d63a22180ef6dbdf46ee73948a5d0a938d835e1939c9b86c48d4c`；约束 SHA-256 `e19cd1ef8ecb7c12397a1a72934c727d6c553467b60fc1859715c010b0ab249c`。精确对象见联合根 `evidence/environment-verification.json`、`joint-results.json`、`installed-audit.json`；已有完整执行见 [联合报告](C:/Users/33393/Desktop/ai-legal-helper/docs/work-report-20261003-joint-candidate.md)。
- **当前剩余项**：模型精确 revision 来源 PARTIAL；ST／TF／torch 风险证据及安全目标未齐；活跃 LangChain／Chroma 需成组处置；普通启动／浏览器流程未验；B setuptools 正式采纳、新对象 D2 未裁。旧后端测试、离线烟测、10月2日真实 rerank 不能顶替这些缺项。
- **2026-10-05 是 Owner 复审点，不自动延长。** 无签署不当作已经接受风险；不能为了赶日期强行升版或降低验收。可以继续只读准备，不代签或自动赋予使用／发布许可。
- 接手日期已到／超过10月5日时，T0先核对复审与最新许可记录；缺记录仍可只读准备，但不能推定旧用途／实验许可自动续期。不得事后补签、将日期改成“今天＋若干天”或把进度报告当Owner批准。
- 未选服务器，不部署。实际下载／安装实验按下列各自审批门；不修改共享 venv、真实 `backend/chroma_db`、任何真实业务／配额库、`.env` 或模型缓存。不开新真实 rerank／生成／云 embedding 轮次，不复用已经耗用的调用许可。
- 只用已批准的 1528 条公开法规副本、QA=0；未知／私有语料不纳入。模型固定 `BAAI/bge-base-zh-v1.5`、CPU、revision `f03589ceff5aac7111bd60cfc7d497ca17ecac65`；不改缓存 refs，不下载新权重。
- 他人未交付的五个前端文件：`frontend/app/admin/sections/KnowledgeSection.tsx`、`frontend/app/admin/sections/UploadSection.tsx`、`frontend/app/chat/page.tsx`、`frontend/app/globals.css`、`frontend/components/chat/InputBar.tsx`；还有原脏文档 `docs/process-archive/superpowers/plans/2026-09-29-local-candidate-decision-and-release-prep.md`。这些均相对项目根，只登记状态／hash，不修改、暂存或整合。后续前端验收默认使用联合冻结源码，不证明这五处并行修改通过。
- 同一命令失败先分析，完全相同命令最多重试一次；同一 bug 连修三次仍不过就停下来质疑。每条实验命令保存实际时间／退出码／完整脱敏日志，旧失败不覆盖。新包安装只用获准官方 wheel，禁 sdist／源码构建、`--no-deps` 和追 latest。
- 本书是后续任务入口；[10月4日依赖预检](C:/Users/33393/Desktop/ai-legal-helper/docs/process-archive/superpowers/plans/2026-10-04-remaining-dependency-preflight.md) 是已有调查证据，不是第二套待执行队列。已明确：TF 5.10.0 撤回；ST 5.6.0 公告／源码矛盾未消；所查新 core 适配集合联动 SDK／Chroma。后续查询仍须另存新的原始响应，不能把旧候选版本当安全锁。

### 指定资源和保护清单

以下均是**只读输入**；初始hash复核不导入应用、不通过Chroma客户端打开库。后续运行必须复制到新根。

| 输入 | 完整路径／用途 |
| --- | --- |
| 源码2658对象基线 | `C:/Users/33393/Desktop/fazhi-local-candidate-20261002-67944caf51ff48ce9432831cdd62f72b/evidence/final-rerank-after-candidate-source-manifest.json`；联合source只对requirements采用页首新SHA，其余按此manifest |
| 受保护41对象 | `C:/Users/33393/Desktop/fazhi-local-candidate-20261002-67944caf51ff48ce9432831cdd62f72b/evidence/protected-before.json`；逐条核对path／SHA |
| 原Chroma38文件 | `C:/Users/33393/Desktop/fazhi-local-candidate-20261002-67944caf51ff48ce9432831cdd62f72b/evidence/original-corpus-before.json`；只比较项目原目录的文件集合／bytes／SHA，不打开原库 |
| 真实配置基线 | `C:/Users/33393/Desktop/fazhi-local-candidate-20261002-67944caf51ff48ce9432831cdd62f72b/evidence/local-config-before.json`；只比整文件SHA，不复制或打印值 |
| refs及并行状态／模型／公开库指纹 | `C:/Users/33393/Desktop/fazhi-joint-candidate-20261003-ac701f4a880441b5a453b1b7cbb06f01/evidence/protection-final.json`；新开工还需登记当时并行文件状态，后续合法并行变化单列，不擅自回滚 |
| 1528公开库原件 | `C:/Users/33393/Desktop/fazhi-local-candidate-20261002-67944caf51ff48ce9432831cdd62f72b/public-kb`；只作复制源，不直接交客户端打开 |
| 公开记录／向量基线 | `C:/Users/33393/Desktop/fazhi-local-candidate-20261002-67944caf51ff48ce9432831cdd62f72b/evidence/public-corpus-review.json`、`public-copy-verification.json`、`reviewed-public-ids.json`，后三个文件均在该evidence目录；复制验收实现供阅读的 `verify-public-copy.py` 也在该目录，不直接运行旧脚本 |
| 默认模型原件 | `C:/Users/33393/.cache/huggingface/hub/models--BAAI--bge-base-zh-v1.5/snapshots/f03589ceff5aac7111bd60cfc7d497ca17ecac65`；11文件与上述protection-final指纹匹配；对应缓存refs/main不得更改 |
| 已有离线wheel入口 | `C:/Users/33393/AppData/Local/Temp/legal-closeout-20260928/wheelhouse`；旧候选根下 `cached-extras`、`cached-extras-2`、`cached-pdf-619`，旧候选根为 `C:/Users/33393/Desktop/fazhi-local-candidate-20261002-67944caf51ff48ce9432831cdd62f72b`；联合根下 `owner-wheels`。仅取与精确单匹配并实物校验的文件，不扫描整个用户目录 |

基线缺失、已有输入漂移、来源与用途不符则相关实验停止；不覆盖旧JSON“修正”基线。纯元数据研究可继续并报告实验停点。上表涉及DB和本机保护产物，不自动纳入交付包。

### 三类许可不能混用

1. **可直接执行：** T0、T1／T2／T3只读准备、公开小体积元数据／公告查询、新仓外报告、精确下载单草拟；不启动应用、运行模型或安装包。
2. **另行批准的实验：** 精确文件下载、独立wheel安装、必要兼容修复、本机替身服务及固定BGE CPU运行。写清获准分案、对象、风险、数据、期限；本地BGE是真实本地嵌入，不是外部模型API。若来源仍PARTIAL，Owner须明确是否允许这份已冻结缓存的受限实验；未知自定义代码仍不得执行，不能开启trust_remote_code=True过关。实验许可不等于正式B采纳／D2，也不顺延10月5日复审。
3. **正式接受与发布动作：** B采纳、新对象D2由Owner裁定；提交／合入／push／真实外部模型调用／真实库写入／部署各有独立授权。最终D2不作为T0–T3前置，也不与T6实验许可混成互相等待的循环；未签仍不声称候选已经接受。

## 执行顺序和并行边界

| 任务 | 优先级／前置 | 可并行范围 | 交付／停止点 |
| --- | --- | --- | --- |
| T0 基线与复审材料 | 最先 | 不依赖依赖升级完成 | 明确本轮对象及10月5日裁定输入 |
| T1 模型风险与来源 | 高；T0 后 | 可与 T2、T3 准备并行 | 有证据的目标或未关闭风险清单 |
| T2 Chroma 安全／迁移目标 | 高；T0 后 | 可与 T1、T3 准备并行 | 精确目标、迁移／回退判据，或阻塞结论 |
| T3 启动与界面准备 | 高；T0 后 | **只读准备**不等 T1／T2 | 路径、进程、mock 和验收场景冻结 |
| T4 一致集合与下载单 | T1／T2 的目标成立后 | 单一集成人负责，避免共同改约束 | 精确清单；**停在下载审批门** |
| T5 分案升级实验 | 精确单及实验获准后 | 可独立环境，但共享缓存只读；CPU／磁盘不足则串行 | 两案各自验收；不把一案通过当另一案成立 |
| T6 联合与启动／界面验收 | T5 所需分案通过，T3 准备完成，启动范围获准 | 测试、迁移、服务启动不共享可写库 | 指向同一新对象的新证据 |
| T7 独立复核与 Owner 裁定 | 相应技术材料齐备 | 不自动提交／签字 | 本地候选接受或具体不接受原因 |

这是可并行的职责划分，不是派发命令。单人执行也按此依赖顺序推进；不额外创建很多报告／脚本框架。T1／T2 无明确目标时仍可做 T3 准备和 T0 复审材料，但 **T4–T6 升级链不能强行继续**。

## T0：基线、保护与复审输入

**读取：** 联合根上述三个 JSON、`candidate-constraints.txt`、`source/backend/requirements.txt`；[现有裁定材料](C:/Users/33393/Desktop/ai-legal-helper/docs/local-candidate-decision-20261003.md)。该旧裁定书的正式对象仍是10月2日四文件候选，不直接套在新联合对象上。

- [ ] 使用只读命令核对当前主线／工作区，并核对联合 requirements／约束 SHA；不导入 `main` 或运行 pytest 收集作为“只读核对”。

```powershell
git -C 'C:/Users/33393/Desktop/ai-legal-helper' rev-parse HEAD
git -C 'C:/Users/33393/Desktop/ai-legal-helper' status --short --untracked-files=no
git -C 'C:/Users/33393/Desktop/ai-legal-helper' diff --name-only --cached
Get-FileHash -LiteralPath 'C:/Users/33393/Desktop/fazhi-joint-candidate-20261003-ac701f4a880441b5a453b1b7cbb06f01/source/backend/requirements.txt' -Algorithm SHA256
Get-FileHash -LiteralPath 'C:/Users/33393/Desktop/fazhi-joint-candidate-20261003-ac701f4a880441b5a453b1b7cbb06f01/candidate-constraints.txt' -Algorithm SHA256
```

输出要求：HEAD及两处SHA与页首锚点一致；缓存／数据库／配置与指定保护清单一致；暂存区仅记录，不替别人清理。全工作区不要求干净，新增未跟踪文档和他人合法修改不等于损坏。refs变化按指定protection-final对比并报告。T0准备报告必须包含这些比较结果，而不只贴git status。

- [ ] 新材料只进入新仓外根；采用下面唯一根创建方式，记录实际绝对路径。该根下 `reports/model-risk.md`、`chroma-risk.md`、`startup-checklist.md`、`dependency-order.md`、`results.md` 各有单一写者；所有原始响应／命令记录进入 `evidence`。不把它们写回任何已冻结运行根。

```powershell
$nextLocalRun = Join-Path 'C:/Users/33393/Desktop' ('fazhi-next-local-20261004-' + [guid]::NewGuid().ToString('N'))
if (Test-Path -LiteralPath $nextLocalRun) { throw 'New run root must not exist' }
New-Item -ItemType Directory -Path $nextLocalRun | Out-Null
New-Item -ItemType Directory -Path (Join-Path $nextLocalRun 'reports'), (Join-Path $nextLocalRun 'evidence') | Out-Null
```

已有续办运行根时先读取其 `reports/results.md` 与审批记录，确认属于本次任务再续用，不为普通“继续”反复创建新根。首次实际根路径、各任务状态、审批原话及证据位置写入results；不得只保存在助手内存。每个步骤验证成立后才打勾；受阻／未验保留未勾并注明理由。

- [ ] 在 `reports/results.md` 首先列明“旧四文件／当前联合／未来升级”三个对象及各自接受状态，给10月5日复审准备对象 SHA、未关闭风险、用途、未验范围、下一复审建议。**B 正式采纳与 D2 风险接受是不同决定；普通‘继续’不算签署。** 不等完整升级结束才整理复审输入。

## T1：模型依赖目标与来源缺项

**负责输入：** [模型链预检](C:/Users/33393/Desktop/ai-legal-helper/docs/dependency-model-chain-preflight-20261003.md)；联合根下 `source/backend/rag_chain.py`、`source/backend/settings.py`；上游精确版本公告／源码。产出新根 `reports/model-risk.md`，不改产品代码。

- [ ] ST 公告和标签源码逐项对照；找真正实施信任拒绝的精确发行，不把5.6.0警告当拒绝、不自动选6.x。记录原始公告／源码、取得时间和 hash；发行标签不自动等于 wheel 内容。
- [ ] TF 空 fix、重复 ID 不同修复行逐条核对；5.10.0禁止下载，5.10.1仅线索。CPU torch 2.6.0+cpu 的扫描跳过保留，核对官方风险／CPU 构建范围，不能凭 CPU 或声明满足豁免。
- [ ] 有可信目标才查 hub 精确版及必要默认传递声明。分别记录“声明兼容”“风险修复证据”“项目调用面”，不合成一个绿色结论。
- [ ] 模型来源另列：默认 snapshot 11文件本地指纹是已有证据，完整精确 revision 上游核验仍缺。使用 [只读元数据补证说明](C:/Users/33393/Desktop/ai-legal-helper/docs/process-archive/assistant-briefs/bge-exact-revision-metadata-request-20261003.md)；Owner 在可达设备取得 JSON 时再比较 Git blob／LFS SHA。本机已有失败请求不重复，不下载权重或换镜像凑来源。

无需依赖额外执行书的补证判据：只收官方 `https://huggingface.co/api/models/BAAI/bge-base-zh-v1.5/tree/f03589ceff5aac7111bd60cfc7d497ca17ecac65?recursive=true` 的公开JSON，不带Authorization；每页≤1MiB、超时20秒，保留原URL／状态／时间／Link分页／bytes／SHA。仅跟随同一官方主机、同一精确revision API路径的下一页，直到next耗尽；失败即停，不重试已失败网络。核对11文件 `1_Pooling/config.json`、`config.json`、`config_sentence_transformers.json`、`modules.json`、`pytorch_model.bin`、`README.md`、`sentence_bert_config.json`、`special_tokens_map.json`、`tokenizer.json`、`tokenizer_config.json`、`vocab.txt`：10小文件按 `SHA1(b'blob '+str(len(content)).encode('ascii')+b'\0'+content)` 比Git blob OID，BIN按精确revision LFS SHA-256／size比较。缺OID、分页不全或revision不能确认仍PARTIAL；来源通过不关闭依赖风险。

**DoD：** 每条风险有源证据、项目触达判断、精确目标或清楚的未定原因；模型来源按实际 COMPLETE／PARTIAL 分类。信任门禁／来源缺项没有证明时不声明关闭，模型实际加载留到审批及安全前置成立之后。

## T2：Chroma 与 LangChain 适配边界

**负责输入：** [Chroma 核对](C:/Users/33393/Desktop/ai-legal-helper/docs/chroma-risk-triage-20261003.md)；联合根下 `source/backend/rag_chain.py`、`source/backend/knowledge_service.py`、`source/backend/retrieval.py`、`source/backend/tests/conftest.py`、`source/backend/requirements.txt`；已查适配元数据。产出 `reports/chroma-risk.md`，不打开原库、不改约束。

- [ ] 核对两条通报的正式修复发行和本项目暴露面；嵌入式／固定模型的限制不等于漏洞不适用，PR／空 fix 不等于正式修复或永久无解。
- [ ] 若有精确目标，核对其与 core／适配包／Python 的声明及官方持久格式迁移要求。现有 Chroma 0.4.24不能直接搭配所查新版适配集合；`langchain-chroma` 与 `chromadb` 版本分开写。
- [ ] 定义三份不同对象：未迁移公开输入副本、待迁移实验副本、供旧版本重新打开的回退副本。必须记录全过程，不能降级打开已迁移库，也不能只以数量相同验收。
- [ ] 若没有可核查修复发行，只给风险适用面／受限措施／未关闭结论；不提交盲升 latest 的安装单。不替换成其他向量库或启动Chroma服务。

**DoD：** 发布版本依据、适配依赖边界、公开库迁移／回退判据齐备，或准确登记阻塞。迁移相关执行阶段使用 `ops-check`，必须验证恢复；本任务仅准备，不实施迁移。

## T3：普通启动与界面验收的只读准备

**负责输入：** 联合根下 `source/backend/main.py`、`source/backend/rag_chain.py`、`source/backend/database.py`、`source/backend/settings.py`、`source/backend/llm_registry.py`；`source/frontend/package.json`、`source/frontend/next.config.js`；现有启动凭据说明见 [裁定材料](C:/Users/33393/Desktop/ai-legal-helper/docs/local-candidate-decision-20261003.md)。产出 `reports/startup-checklist.md`，不启动服务、不检查并行前端改动代码。

- [ ] 记录导入副作用：main 导入会调用 `init_db()`；rag_chain 导入加载嵌入并打开Chroma；lifespan预热失败会降级。**进程活着／health返回200都不单独证明模型、检索和预热正常。** 测试 conftest 不保护普通 uvicorn 启动。
- [ ] 在导入前固定新运行根下 DATABASE_URL、CHROMA_DIR、QUOTA_DB、临时／日志／上传目录；逐项核对所有可写路径，不可漏配后回落真实目录。进程配置不复制真实 `.env`；只设置实验专用凭据，真实 key 不打印／导出。
- [ ] 为将来运行准备独立模型缓存：只复制指定11文件及同revision布局到实验根，复制后逐SHA核对；不使用指向原件的symlink／hardlink，不复制其他snapshot。HF_HOME／HF_MODULES_CACHE等可写缓存路径固定在实验根，禁网；原缓存、权重及refs始终只读。若库尝试写原缓存、加载未知自定义模块或连接外部服务，先停止，不放宽守卫。
- [ ] 准备仅本机监听、关闭 rerank／追踪、外部连接拒绝、既有缓存禁网的启动方式。LLM 使用确定性本机替身，模型注册表全部路由到该替身，禁止未知备用端点；BGE真实CPU加载仍须T1安全前置／明确批准，替身不能冒充该加载验收。前端 BACKEND_URL 指向本轮后端，端口冲突换本轮端口，不停止他人进程。
- [ ] 读取联合根 `source/frontend/package-lock.json` 的冻结指纹，核对既有前端依赖审计是否对应同一锁文件；不对应或缺失就明确未验，并提出只读审计补证入口。后端pip审计不覆盖Node／Next依赖；不自行运行 `npm audit fix`、升级Next／React或安装工具。前端依赖风险同样进入T7裁定材料，不因build通过就判无风险。
- [ ] 冻结以下界面／HTTP判据，使用现有浏览器工具，不安装新Playwright框架：

| 场景 | 必须看到的行为与证据 |
| --- | --- |
| 启动／预热／检索 | 记录导入和lifespan日志；公开法规检索有指定法名＋条号，预热降级单独说明 |
| 登录和权限 | 登录后能读取自己会话；普通用户访问管理入口拒绝；用户B不能读取用户A会话 |
| SSE／错误／取消 | 本机替身的固定内容正确拼接；断流或500不显示成功；取消后可再次请求，无敏感错误泄漏 |
| 法规原文 | 引用入口打开对应法名＋条号原文；替身答案不作为法律质量金标 |
| 管理上传 | 必填生效日边界、非法日期和损坏PDF按既有契约拒绝；合法样本只写本轮可丢弃库，保持真实限流启用 |

**DoD：** 启动配置／写路径／网络与进程边界完整；每个场景有动作、期望和证据位置。先准备，实际运行另取得实验许可并满足T1模型安全条件，不以D2未签为理由阻塞只读准备，也不以实验许可冒充D2；需要本机测试用户／管理账号时只写实验库。

## T4：最小一致集合、精确下载单与审批

**产出：** `reports/dependency-order.md`；新根 `evidence` 中每个版本的原始PyPI响应及取证记录。仅一个集成人写集合和约束；消费T1／T2，不重复选择互相冲突的hub／core版本。

- [ ] 从联合162实装基线出发，只改变有证据必要的包；遍历所选默认声明、Python／Windows marker及新增传递依赖，已有满足的包保留。core、SDK、拆分包、hub、ST／TF、Chroma和新二进制包统一核对；不启用all／dev／训练 extras。
- [ ] 区分“元数据声明闭包可满足”和“实际解析／安装成立”；未经安装不能声称解析器验收成功。联网 `pip --dry-run` 可能下载，不作为只读替代路径。
- [ ] 下载单逐文件列包名／精确版／官方URL／size／公告SHA／Python和wheel标签／所在分案／是否已有缓存；汇总仅缺失文件的总字节。声明不留区间，不能让下载助手自行替换版本、使用sdist或下载CUDA／权重。
- [ ] **停止并提交Owner审批：精确下载范围、独立安装实验，以及有必要的最小兼容修复。** 下载批准不自动成为安全通过、实际调用许可或风险接受。未批准只保留材料，不启动安装。

审批记录最低字段：实际日期／原话来源、精确清单SHA、批准的分案、允许下载还是还允许安装／兼容修复、是否允许固定BGE CPU及PARTIAL来源的受限实验、许可期限；缺哪一项就停在对应门。可以一次明确批准所列多项实验，不要求每一步重复询问；范围未列明就不自动补足。不得把旧setuptools单项下载批准迁移到新整组包，也不得把“放开rerank”旧轮次许可记作本轮预算。

## T5：分案实验，不破坏已验候选

**前置：** T4审批明确成立；wheel实物size／SHA核对；新根中分案源码／venv／公开库各自独立。若只有一案成立，只执行获准案，不补造另一案成功。

- [ ] 从联合 source 复制并逐文件核对，源清单来自旧2658对象但联合requirements有上述唯一追加差异，不能直接把旧requirements hash当联合hash；复制时排除venv、运行产物、真实库和真实`.env`。各分案保留源码／依赖／数据输入指纹。
- [ ] 各案只改实验源码 `backend/requirements.txt` 和该案精确约束；离线wheel安装，实际分发增量和pip report逐项记录。若需兼容修复，只在已证明失败的调用点最小改动，先写并看到正确失败的回归，再修复；没有失败依据不重构产品接口或扩大业务行为。
- [ ] 模型案先验证未知自定义模块没有执行的无害否定测试，再限定CPU离线加载；固定BGE的原八条空间抽核逐条余弦≥0.99999。768维相同不算空间通过。
- [ ] 数据案只迁移公开副本；1528条、QA=0，逐条ID／正文／metadata／向量输入指纹，新进程重开。向量索引读回绝对差≤1e-6、余弦误差≤1e-10；阈值和原八条采样规则见[原验收](C:/Users/33393/Desktop/ai-legal-helper/docs/work-report-20261002-rerank-acceptance.md:45)。失败先提出隔离重建分案，不改阈值、不覆盖原库。

八条规则固定为四部公开法规（劳动合同法98条、劳动法107条、民法典1260条、消费者权益保护法63条）各按ID排序固定抽两条，总数1528、抽核八条；实际使用 `C:/Users/33393/Desktop/fazhi-local-candidate-20261002-67944caf51ff48ce9432831cdd62f72b/evidence/bge-space-verification.json` 的sample_ids，不另创选样算法、不能运行后换样本。八个ID为 `002a5f6c-116e-4b43-9578-c79e8e3441aa`、`003a16a8-ac81-451a-8f0b-010de92d90e4`、`0062a963-3c55-488c-9b91-126b083a3b5f`、`0163fbe6-bea2-4eb1-a1f8-729dbe117704`、`01846d3b-b154-49a1-8fb0-6b7bbb30756f`、`01904885-794f-459b-bfc3-bd28f625ff0e`、`01b33ca5-586a-4697-aae6-ace900dc3f05`、`01ec23d7-5504-4073-a66e-567174dc7a29`。旧公开记录集合SHA为 `581dbbd83df721538dbf9df2f6e11e70c434e525a85d7f3d24f08a1d90b3b880`。内容指纹及向量输入SHA按指定public-corpus-review／public-copy证据的同一算法复核；不得用新算法不同序列化结果冒充数据漂移，也不得把容差用到应严格相等的ID／正文／metadata／输入向量上。
- [ ] 各案pip check、适配接口／SSE／异常／缓存／检索定向回归、新实装审计与恢复验证成立才汇合。审计exit1若代表有效通报须登记，不能当命令损坏或删除ID；torch扫描跳过保留独立说明。

### T5离线安装参数（只在该分案获准并完成复制／精确约束后）

模型案目录为新根下 `experiment-model`，数据／适配案为 `experiment-data`。下面以模型案为例；数据案只换这一个目录名，源码复制和数据保护规则不变。T0先保存实际新根路径，续接会话不可重新生成GUID让下列变量指向空目录。

```powershell
$oneExperiment = Join-Path $nextLocalRun 'experiment-model'
$oneExperimentPy = Join-Path $oneExperiment 'venv/Scripts/python.exe'
$oneExperimentBackend = Join-Path $oneExperiment 'source/backend'
$oneExperimentConstraints = Join-Path $oneExperiment 'candidate-constraints.txt'
$oneExperimentWheelhouse = Join-Path $oneExperiment 'wheelhouse'
```

`source` 和精确约束已经按本书准备，`wheelhouse` 只包含精确单所需的已验证官方wheel（已有缓存也逐实物SHA核对后复制）。要求不存在既有venv，原件无额外安装产物；解释器引导为只读联合根的 `C:/Users/33393/Desktop/fazhi-joint-candidate-20261003-ac701f4a880441b5a453b1b7cbb06f01/venv/Scripts/python.exe`，仅运行 `-I -B -m venv "$oneExperiment/venv"` 创建新环境。成功后在受控新子进程执行：

```powershell
& $oneExperimentPy -B -m pip install --no-index --only-binary=:all: --find-links $oneExperimentWheelhouse -c $oneExperimentConstraints pip==26.2.1 setuptools==83.0.0 --report "$oneExperiment/evidence/install-tools-report.json"
& $oneExperimentPy -B -m pip install --no-index --only-binary=:all: --find-links $oneExperimentWheelhouse -c $oneExperimentConstraints -r "$oneExperimentBackend/requirements-dev.txt" --report "$oneExperiment/evidence/install-requirements-report.json"
& $oneExperimentPy -B -m pip check
```

每条单独留命令／退出码，前条非0立即停止，不能顺着执行。候选锁、需求和wheel默认Requires-Dist不得包含VCS／外部直接URL或额外索引；禁继承PIP_INDEX_URL／PIP_EXTRA_INDEX_URL／PIP_FIND_LINKS等安装配置，外联守卫保持拒绝。torch基线暂保留2.6.0+cpu；只有T1查到必要换版证据且T4另明确批准精确CPU构建才换，不能因找不到本地wheel改成PyPI无后缀构建或CUDA。pip／setuptools上述版是复用基线，不自动重新下载；若另发现新通报，先重新分案，不擅自换版。缺文件只列精确缺项，不运行联网pip补齐。证据输出已存在时用新的受控文件名，不重装已经完成且可核查的环境。

## T6：新联合对象和普通启动／界面验收

- [ ] 当所需分案均通过时，另建联合环境，冻结源码、精确依赖、公开库和题集；不拼接两份分案结果冒充联合结果。若一案受阻，暂不把半套升级认定完整候选。
- [ ] 在新副本执行下表现有门禁，环境／cache／coverage输出全部指向新根；确切参数已放在本书，不必从旧run.py猜测。不要直接执行旧根脚本或把它整段搬过来覆写原对象。
- [ ] 原1690个非slow nodeid不得漏失，允许登记新增测试；skip／deselect变化逐条解释，禁止新skip掩盖失败。覆盖率执行既有配置70%门槛并解释相对旧85.42%的变化，不能以覆盖率代替行为正确。旧数字均来自10月3日联合轮，本轮必须有新命令结果。
- [ ] 单独核对启动范围授权及T3写路径／T1加载条件后才启动本轮服务；只本机、单worker、不启用reload，**不调用真实外部模型服务**。获准固定BGE CPU加载须实际验证；它与本机LLM替身分开记录。完成T3场景，收集脱敏日志／截图／HTTP结果。冻结前端目录内仅在缓存够用、无安装下载时执行下表已有命令；缺依赖列单，不用会自动下载的npx填缺包。
- [ ] 冻结前端验收不覆盖主仓五处未交付修改。收到其正式交付、完成审阅并明确纳入后，才另冻结新对象和重测受影响流程；不擅自合入。不为执行浏览器测试改动产品视觉设计。
- [ ] 清理只限本轮自建进程，按PID／启动时间／命令和运行根确认所有权；不杀占端口的其他进程。保留实验目录和失败证据，不递归删库／缓存。前后保护指纹不变，任何真实库／凭据／旧对象变化立即停止。

### T6 的确定性命令表（仅审批／隔离前置通过后使用）

新联合目录固定为T0实际新根下 `joint`，包含 `source`、`venv`、`runtime`、`evidence`。下表中的变量按此定义，目录／解释器缺失则停止，不指向旧联合根：

```powershell
$experimentJoint = Join-Path $nextLocalRun 'joint'
$experimentPy = Join-Path $experimentJoint 'venv/Scripts/python.exe'
$experimentRuntime = Join-Path $experimentJoint 'runtime'
$experimentBackend = Join-Path $experimentJoint 'source/backend'
$experimentFrontend = Join-Path $experimentJoint 'source/frontend'
```

命令交给本轮受控执行器，**不是跳过环境准备直接在主仓运行的脚本**。新子进程在任何应用导入前移除继承的真实API_KEY／TOKEN／PASSWORD／SECRET、代理和LLM_MODELS_JSON等应用配置，再显式设置实验JWT／LLM值、本机替身端点、EMBEDDING_PROVIDER=local、RERANK_ENABLED=false、配额总额0、隔离DATABASE_URL／CHROMA_DIR／QUOTA_DB、TEMP／TMP／COVERAGE_FILE／MYPY_CACHE_DIR／HF缓存及禁网／关闭追踪。dotenv及模型注册表不得从父目录重引入真实凭据／端点。拒绝外部连接并检查所有写路径；测试conftest会覆盖库路径，TEMP也必须在实验根。定向／全量使用空实验库，烟测另用完整公开库副本；管理上传再用可写副本，不能污染随后数量／内容验收用的输入。

| cwd | 命令 | 成功判据 |
| --- | --- | --- |
| `$experimentBackend` | `& $experimentPy -B -m pip check` | exit0，无依赖冲突 |
| 同上 | `& $experimentPy -B -m pytest --collect-only -m 'not slow' -q -o "cache_dir=$experimentRuntime/pytest-cache"` | exit0，保存完整nodeid并逐项比较 |
| 同上 | `& $experimentPy -B -m pytest -q tests/test_chunking.py tests/test_pdf_upload.py tests/test_upload_rate_limit.py -o "cache_dir=$experimentRuntime/pytest-cache"` | exit0；升级新增回归另外逐条列命令，不跳过 |
| 同上 | `& $experimentPy -B -m ruff check . --cache-dir "$experimentRuntime/ruff-cache"` | exit0，不自动修复 |
| 同上 | `& $experimentPy -B -m ruff format --check . --cache-dir "$experimentRuntime/ruff-cache"` | exit0，不自动格式化 |
| 同上 | `& $experimentPy -B -m mypy .` | exit0，配置覆盖范围不缩减 |
| 同上 | `& $experimentPy -B -m pytest -m 'not slow' --cov=. --cov-fail-under=70 -q -o "cache_dir=$experimentRuntime/pytest-cache" --basetemp "$experimentRuntime/pytest-temp"` | exit0，nodeid／skip／覆盖率差异可解释 |
| 同上，CHROMA_DIR换为新公开副本 | `& $experimentPy -B scripts/smoke_citation_fast.py` | exit0，原24项判据均通过；rerank仍关闭，不证明真实服务认证 |
| 同上，独立审计子进程 | `& $experimentPy -B -m pip_audit --format=json --output "$experimentJoint/evidence/installed-audit.json" --timeout 20` | exit0或1均须解析有效dependencies；1为有效通报时记风险，不写安全通过；允许的联网只限公开审计元数据服务 |
| `$experimentFrontend` | `npm run lint`；`& './node_modules/.bin/tsc.cmd' --noEmit`；`npm run test`；`npm run build` | 分别exit0，依赖与冻结锁一致、产物只写新根；缺可用Node、依赖或离线构建字体等资源就停，不自行安装／联网补齐，不以当前主仓未核对的node_modules冒充冻结依赖 |

每个命令单独保存JSON（command／cwd／started_at／ended_at／exit_code／log_path）及完整脱敏日志；读取真实退出码后再执行下一条，不能把显示日志的命令码当测试码。每次结果文件名新建，禁止覆写；pip-audit和其他脚本输出路径已存在则先换新名。pytest已知会在收集期生成隔离空Chroma，验后确认其内容和所在路径，不能写成“完全无副作用”。

**DoD：** 同一新对象的静态、单元／定向／完整回归、公开检索、迁移恢复、实际启动及浏览器证据可追溯；离线替身只能证明接线／交互，不证明真实生成、rerank认证或法律回答质量。

## T7：独立复核、有限接受与后续发布准备

- [ ] 执行者完成自审，核对实际diff／安装集合／原始通报／题集／日志，不只审汇报文字；独立复核方式由Owner或当前执行流程安排，不自动创建其他会话。新日志与文档交付做完整字段值／形状扫描并有阳性对照，禁止真实凭据、DB或权重混入。

自审不记为独立复核。Owner未安排复核者时，报告写“自审完成、独立复核待办”，不能由同一助手换名签署。值扫描在本机内存读取项目backend/.env八个在册输入（ADMIN_PASSWORD、JWT_SECRET、RERANK_API_KEY、LLM_API_KEY、EMBEDDING_API_KEY、ZHIPUAI_API_KEY、DASHSCOPE_API_KEY、SILICONFLOW_API_KEY）及Windows机器级RERANK_API_KEY，共九字段；dotenv读取禁插值，只输出字段名／命中统计、不输出值、长度或key hash。任一缺失或空值则该扫描无效，报告停点；不得把当前用户级／进程级值冒充机器级主值。形状扫描也须阳性对照，参考只读联合源码中已有的 `dispatch-output/local-candidate-closeout-20260928/b_worktree_value_scan.py`、`secret_shape_scan.py` 的纯扫描定义，不运行其可能另建Git对象的整套selftest。只外发明确筛选的报告／命令记录／公共元数据／必要patch，逐文件manifest注明实际集合；不整目录打包新根，不把公开DB或模型权重混入，失败集合保留但不当成功交付。
- [ ] `reports/results.md` 汇总每项“通过／未验／受阻”、对象SHA、风险未关闭理由和实际权限边界；补全新的裁定对象说明，不沿用旧四文件选项代签。Owner明确决定B采纳、D2有限用途及新复审安排；无风险接受则保持未接受，发布结论不得写通过。
- [ ] 正式本地接受后再**准备**增量审阅和提交清单。真正提交／合入／push另获授权；不使用git add -A，不带走他人未交付内容。
- [ ] 后续阶段只登记前置：历史凭据处置与待推对象复扫、远端历史对齐／CI、Linux同源验收、真实模型预算及法律质量验证、服务器选型／备份恢复／部署回滚。**本书不执行推送、Linux CI触发、真实库迁移或部署。**

## 范围自审与完成口径

本轮选择“证据目标→最小精确集合→分案→联合→实际应用验收”，而不是直接整栈升级；慢的是尚未确定的安全目标，不用加框架解决。沿用原样本／判据及现有工具，不添加大规模评测平台，也不为启动另造一套产品配置系统。

任务拆分按可独立否决的结果：T1可以不成立而T2成立，T3只读准备不被二者卡住；但T4共享依赖必须单一集成，T5/T6不共享可写数据库。这避免并行写约束、缓存串味、假接线和仅数量通过的假绿。

**本阶段完成**仅指获准对象的本地验收与Owner裁定材料齐备。若安全目标不存在、来源未补齐、实验未获准或D2未签，明确留下未完成项，不用报告写完替代技术完成／接受。2026-10-05先完成实际复审，不承诺当天必定完成跨代升级。当前所有复选框均未执行；本次只交付后续计划。
