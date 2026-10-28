# 完整本地候选收口：主助手执行记录

执行日期：2026-10-02，续办2026-10-03。**最新：依赖精简线索和最小分案已整理，缺包模拟整体未通过，模型来源仍PARTIAL。启动配置6项离线检查通过；真实rerank沿用§11已通过结果。D2／Windows接受未签，完整A–F仍部分完成。** 最新风险续办见§13，启动配置见§12，真实结果见§11，预检见§10，依赖全测见§9；旧章节保留各自时点，不借旧结果签新版。

任务入口：[执行书](C:/Users/33393/Desktop/ai-legal-helper/docs/process-archive/superpowers/plans/2026-10-02-local-candidate-completion-plan.md)。Owner授权主助手继续执行整份计划，普通方案采用推荐，并对§11的精确新一轮rerank请求回复“批准”；该轮已使用完。风险签字、提交／合入、push、真实库写入和部署仍保留边界。

## 1. 本轮对象

- 固定源：`902e2d161e67100ed6d267a08c393538a0abe109`；旧候选仅提取PDF修复和两只测试，不整支合并。
- 仓外根：`C:/Users/33393/Desktop/fazhi-local-candidate-20261002-67944caf51ff48ce9432831cdd62f72b`。
- 源码：该根下 `source`；独立环境 `venv`；记录 `evidence`。不是日常或历史venv。
- 接手已有脏文档 `2026-09-29-local-candidate-decision-and-release-prep.md` 保留，SHA-256与计划一致；HEAD／引用未改。

## 2. 当前执行情况

| 项 | 当前状态 | 本轮证据与限制 |
|---|---|---|
| A 固定来源 | 来源／保护通过，交付限制见§9 | Git归档2656文件、最终源码2658文件、41保护对象；74历史HNSW文件未获公开判定；三冻结文件及nullable审计注解保留 |
| B 离线缓存／环境 | 新目标6.19.0实装／声明通过 | 原缓存加一个授权下载且官方SHA一致的pypdf wheel；独立venv167分发；27直接需求／167约束全满足、pip check=0；相比6.16.1环境只变pypdf |
| C PDF／依赖 | 新版功能验收通过 | 新9/9、定向128/128、四文件白名单；旧坏PDF两个500红例保留，不冒充本次攻击复现 |
| D 公开副本 | 新版环境复验通过 | 同一公开库1528条ID／文本／metadata和向量查询、本地BGE空间抽核、离线24/24／联合召回7/7通过；QA=0，无新增私有快照 |
| E 前端 | 未变，限定复用同根较早结果 | 离线npm ci、lint、tsc、7文件54测试、build退出均0；本次pypdf升级未重跑前端，不冒充浏览器／生成端到端 |
| E 后端／审计 | 新版后端绿，审计仍红 | 新1680 passed／10 skipped／18 deselected，85.42%；lint／类型／守卫通过；实装57行／10包／32组，torch跳过另审，没有漏洞豁免 |
| E2 真实rerank | 最终环境限定验收通过，许可已消耗 | §11实际7次200／有效重排7/7／快速门禁24/24；§12配置读取验证通过，完整应用启动和其他模型分支未验 |
| E3 Linux／远端 | 未验 | Docker本轮命名管道不可用，没有启动服务、pull镜像或触发远端CI |
| F 完整交付／裁定 | 新版恢复／薄集合技术检查通过，最终接受待裁 | 6.19.0恢复2658文件字节全一致；72文件薄补丁／证据集合9字段值0、形状0、禁止文件0；无完整基线归档，不是公开批准；D2未代签 |

前段缓存恢复只读取项目使用的pip HTTP缓存body，并核对官方精确版本wheel SHA-256；恢复件包括CPU torch依赖。随后Owner批准单项缺包，本次只下载一个pypdf6.19.0 wheel；没有下载其他wheel、模型、CUDA或镜像。pytest保留9.1.1，不降低主线安全下限，源缓存未删除或改写。

## 3. 失败及停点记录

- 源码准备检查曾误要求main内存在3处相同的nullable审计注解；实际是1处该注解，另有不同类型注解。归档已完成、字节未改；纠正检查后核对通过，不重建或覆盖源码。
- 第二次缓存闭包预检发现torch的3个附加依赖；沿其依赖补查后从缓存恢复5个官方哈希一致wheel，闭包预检通过。前两份缺包结果保留。
- 第一次补查PyPI元数据遇传输EOF；分析为传输层故障，改HTTP/1.1后取得元数据；没有下载分发包。
- PyTorch官方索引当前链接到`download-r2.pytorch.org`；首次仅允许旧host的元数据预检拒绝该链接。核对官方索引后接受其确切CPU wheel及哈希，不接受任意下载域名。
- 公开库准备脚本首次因一个多余括号在解析阶段失败，一行未执行；只修正语法，随后指纹和复制检查通过。
- 全量测试首条命令组装时，PowerShell把覆盖率XML路径拆成单独参数，pytest退出4、没有执行测试；不是功能红灯。固定括号后只从全量门禁续跑，保留原失败日志，不重复已通过门禁。
- 从仓外副本运行发布工具单测时，26通过／1失败：默认历史目录断言绑定原目录，复制测试文件后`__file__`变了。没有弱化断言或改产品路径；先证明原7个工具／测试文件与固定副本字节相同，用本轮新解释器跑原路径的同一测试，27通过。原失败保留，**工具测试的导出位置可移植性未解决**。
- pypdf缓存补查入口曾误用不存在的PowerShell变量`$candidatePy`；Python未启动。读取隔离配置后改为既定`$py`，补查结果确认为缺包，不自动重试下载。
- 历史审计`.json`首行是固定的“Found 57…”横幅，直接JSON解析失败；归并工具只分离该已知首行并保留全部原JSON，历史文件没变。本轮审计由`--output`单独生成JSON，不存在该混写。
- 检查点首轮补丁应用成功但四文件字节不符：Git继承`core.autocrlf`，LF变CRLF。没有改系统／仓库配置、没有覆盖失败目录；新目录以单条命令`-c core.autocrlf=false -c core.eol=lf`应用，2658文件全匹配。没有用语义相同代替字节一致。

完整命令、实际时间和退出码保留在`evidence/*-command.json`；上述失败不是产品功能红灯。安装失败／收集失败也不会当作PDF回归红灯。

## 4. 历史6.16.1最小代码整合（新版见§9）

全测前采集的实验源快照只有两个原文件改变、两个测试新增；2656个基线对应2658个候选文件，三冻结文件未变。两只新增测试的Git blob与旧候选完全相同。**该旧清单采集早于全测，不能当作测试后集合核对；新增空库与新版后置核对纠正见§9。**

PDF修复只捕获pypdf的`PyPdfError`，转换为既有上传路由处理的`ValueError`；中文抽取、空文本拒绝、大小／magic校验、缓存失效、nullable类型与bootstrap日志安全代码均保留。FastAPI固定0.141.1，pypdf固定6.16.1；pytest实装9.1.1，未回退需求下限。

上面描述的是**历史已验检查点**。当时审计后最终pypdf目标修订为6.19.0，缺包期间实验声明／实装保持6.16.1；这项旧停点现已解除，当前实装与新版证据见§9。主仓代码仍未移入这些改动。

来源绑定见`candidate-source-verification.json`／`candidate-source-manifest.json`／`declaration-verification.json`。收集基线是在同一新环境忽略两只新增测试；另以基线归档逐文件哈希证明原测试未修改，不使用旧环境的通过数作比较。

定向测试有Starlette/httpx弃用警告，以及固定测试JWT的短密钥警告；没有因此关闭警告或升级SDK／httpx。这些不是实际凭据的长度记录，也不证明生产认证配置已验。

## 5. 历史6.16.1完整测试与检索证据（新版见§9）

所有下列结果属于本轮独立Python／pytest9.1.1、6.16.1源码检查点；解释器与需求、源码集合、nodeid集均有独立记录。不借历史1671通过或85.09%充本轮数值。

- 后端非slow：**1680 passed／10 skipped／18 deselected，161 warnings，coverage 85.42%，rc=0**。该覆盖率为既有门禁的行＋分支合计：9552／11182；XML的纯行覆盖率为7429／8554（86.85%），分支为2123／2628（80.78%），不能混用。收集1708项，其中1690非slow；原1681个非slow nodeid全部保留，只新增9个，原测试逐文件与归档核对未修改。见`E-backend-full-corrected.log`／`backend-junit.xml`／`coverage.xml`。
- Ruff check=0、format270文件=0；mypy按既有配置74文件无错误，未扩大已有豁免或放松规则。守卫Ruff／4文件format=0，预算单测9通过，值扫描单测14通过，发布单测原路径27通过。
- 真实轮次测量包装器假传输回归32通过；普通配置优先级假值夹具4通过：进程继承值包括显式空值不被dotenv覆盖，缺进程值时才读文件。**Settings不会自行取HKLM**；测试未读真实key来启动应用，所以“系统key已配好”仍不等于所有应用进程已经使用它。
- 前端独立离线npm ci、lint、tsc、7文件54测试、build全部rc=0；不等于浏览器交互或生成模型端到端验收。没有升级前端依赖或改manifest／lockfile。
- 公开副本实际新进程恢复：SQLite integrity=ok、唯一`legal_provisions_cos`、1528条ID／文本／metadata全部一致、可向量查询；四部法规为民法典／劳动合同法／劳动法／消费者权益保护法，QA=0。集合SHA-256为`581dbbd83df721538dbf9df2f6e11e70c434e525a85d7f3d24f08a1d90b3b880`。
- 写入向量1528条字节一致；HNSW读回183条出现float归一化微差，最大绝对差2.9802322387695312e-8，最小cosine0.9999999999999991，满足预设1e-6／1e-10阈值。没有隐去差异、改向量或声称读回字节全同。
- 本地BGE768维CPU八条空间抽核通过；离线烟测**24/24**、法规名＋条号联合召回**7/7**。联网socket守卫拒发，真实rerank／云嵌入调用=0。7933是测试输入token估算，不是账单或真实模型调用量。

新候选的真实rerank没有跑。此前第三轮7次200／7次有效重排的PASS只绑定此前旧环境与该轮来源，仍保留有效历史证据，**不能当作本轮6.19.0候选的最终绑定**。Docker的LinuxEngine管道本次不可用，没有启动Docker、pull镜像、运行compose或触发远端CI。

## 6. 历史6.16.1审计带来的计划修订（当前审计见§9）

本轮实装`pip-audit`实际返回**65原始行／11包／40个ID别名归并组**，rc=1；有有效JSON，不是查询故障。torch2.6.0+cpu仍被扫描器跳过，单独精确查询torch2.6.0上游返回24行／22组；不是断言所有通报都适用CPU。完整输入与各包命中、所有ID／别名／修复版本见仓外 `evidence/current-audit-summary.json`／`B-current-risks.md`；不运行会自动取包的声明解析审计、不加ignore、不减原始通报。

**最先处理pypdf。** 6.16.1本次命中8条，其中解析间接对象、ToUnicode／字体和FlateDecode通报与当前`PdfReader`＋抽文本调用面有关；这是条件分析，不是攻击复现。另几条需访问page labels、附件或flatten表单，当前上传函数未直接调用，不能把全部8条说成已证实可达。`PyPdfError`转换修的是受控400，不修解析器资源耗尽。[官方文本抽取公告](https://github.com/py-pdf/pypdf/security/advisories/GHSA-fp3h-c4fm-7vvf)、[官方解压公告](https://github.com/py-pdf/pypdf/security/advisories/GHSA-jw7q-gvrg-4vj3)。

当时推荐目标**6.19.0**、精确元数据0通报、rc=0，但缓存缺包尚未安装。**这段保留提出单项下载的理由，不是当前阻塞**；Owner批准后下载、离线安装与新版回归已完成，见§9。[单项下载记录](C:/Users/33393/Desktop/ai-legal-helper/docs/process-archive/assistant-briefs/download-pypdf-619-20261002.md)、[官方发行](https://github.com/py-pdf/pypdf/releases/tag/6.19.0)。

相对历史快照，本轮另新增sentence-transformers的CVE-2026-68770和Transformers的CVE-2026-80047；pytest旧通报不再返回。固定模型名、离线、CPU或trust_remote_code=False都不能代替模型目录完整性核验；本轮未复现旧版sentence-transformers绕过，也未核验所有模型缓存官方哈希。torch的weights_only本身已有绕过通报，默认开启不能写成已缓解。整套LangChain／Chroma／torch／Transformers升级仍另案，不能为消警自动扩范围。[sentence-transformers上游问题](https://github.com/huggingface/sentence-transformers/issues/3801)、[PyTorch官方通报](https://github.com/pytorch/pytorch/security/advisories/GHSA-63cw-57p8-fm3p)。

风险签字仍留白。**执行授权不是风险接受**，在册最迟复审2026-10-05未延长；新公告和新增调用面也要求重审。

## 7. 历史6.16.1恢复／交付与保护结果（新版见§9）

固定272MB归档留在受控仓外，是来源证据，不是可直接发给助手的“干净代码包”。其中有`diag/frozen-index-004`／`005`下74个历史索引数据文件；未打开其库／pickle，未做内容公开判定。原A-summary的“无真实config/db”布尔仅按常见文件名检查，**不足以证明没有索引／私有数据**。归档和两个本地还原目录不转发、不打入源码／证据包、不删除；这项限制已同步计划。

已完成检查点恢复：固定归档＋四文件补丁在新空目录还原，2658文件集合和每个SHA-256与已验源码全一致；没有打开恢复库／导入应用，不需要为解包验证重跑全部重型测试。恢复结果为`evidence/checkpoint-restore.json`，原失败为`checkpoint-restore-first-failure.json`。

薄检查点目录是执行根下`checkpoint-pdf616-lf`，含最小补丁和选定证据，不含基线归档、库、索引、模型、wheel、venv或node_modules；47文件精确清单单独复核，9字段内存值比对0、形状0、禁止文件0。原源码集合另有5个JWT形状，均对应官方PyJWT2.15.0描述中的公开示例，原发现没有删除。**这些检查都不等于发布／全工作区／暂存／历史零凭据，也不意味着薄检查点已获公开批准或最终无数据包已完成**。

本轮16:46收尾复核：**41保护对象全未变，原Chroma38文件整集合及每个字节指纹未变，backend/.env全文件未变，HEAD／所有refs未变，原脏文档SHA未变、主仓跟踪代码未改**。没有修理或覆盖可能属于其他助手的工作；本轮主仓只新增／修订计划、报告与单项下载文档，未提交或发布。

## 8. 由主助手续跑的最短路径（更新）

1. **单项下载、6.19.0离线安装、受影响回归、恢复和自审已完成，见§9。** 不需要再挑版本或重复下载，不需要现在选择服务器。
2. **最终环境真实rerank已完成，见§11；不得再调用证明一次。** 默认缓存不是已确认的safetensors路径，模型来源仍PARTIAL；普通启动值不同于系统新key。这些未决项保留，不把实验包装器成功当作正式启动通过。
3. 当前风险／用途／失效条件已有材料，Owner仍需裁定D2及Windows限制，复审2026-10-05不自动续期。薄补丁集合卫生通过不等于公开批准、完整来源归档可转发或最终候选已接受。
4. 只有这些验收／接受门关上后才考虑主线整合；提交／合入、push、真实库写入和部署均未做，也不因“继续／自己审核”自动执行。

按最小方案执行：没有添加锁包体系、CI工作流、业务模块、模型升级工程或PDF隔离架构。当前停点是已有审批／接受边界，不是缺少执行方案选择。

## 9. pypdf6.19.0完成结果与主助手自审

Owner回复“做完自己审核”批准此前明确请求的单项wheel与隔离升级／回归。我使用同一执行根完成，不另派助手，不改主仓代码／引用，不延伸到真实模型新轮次、风险签字、提交／合入或部署。

### 9.1 实际变更与新证据

- 16:57:41–16:57:43官方精确元数据、单个395480字节wheel下载均退出0；SHA-256 `7e5d6e730e7dae87d560a2cee218b852f6498c8be61966f3cd02ead971e48d14` 与官方一致。文件在 `cached-pdf-619/pypdf-6.19.0-py3-none-any.whl`，不是CUDA／模型；不会重复下载。`download-pypdf-619-command.json` 中installed=false只描述下载结束时点，随后安装退出0见 `pdf619-install-command.json`。
- 保存原声明和约束为 `source-requirements-pdf616.txt`／`candidate-constraints-pdf616.txt`，旧日志／包／恢复目录不覆盖；只在实验source和独立venv将pypdf6.16.1→6.19.0。167实装分发的版本比较只有pypdf改变，27直接需求／167约束全满足，pip check=0。
- 新16项门禁退出均0：PDF／限流9、定向128、Ruff、270文件format、74文件mypy、收集、后端非slow全量、守卫、预算9、扫描14、原路径发布27、假传输包装器32、假值配置4。**后端1680通过、10跳过、18排除、161警告**；新JUnit无failure／error，新XML9552/11182=85.42%，纯行86.85%、分支80.78%。真实模型调用0；32/4不冒充产品真实rerank／真实认证。
- 新后置源码核对2658文件，只有requirements、knowledge_service和两只新增测试四处白名单差异，冻结文件不变。同环境原1681非slow nodeid全部保留，新增9项；主线缓存安全修复、nullable注解、bootstrap日志及pytest安全下限保留。当前依据为 `pdf619-clean-candidate-source-verification.json`／manifest。
- 新环境复开同一公开库：1528条ID／文本／metadata及输入向量字节一致、QA=0、向量查询通过；集合SHA仍 `581dbbd83df721538dbf9df2f6e11e70c434e525a85d7f3d24f08a1d90b3b880`。HNSW读回183条微差仍满足原阈值，不声称全字节相同。本地BGE768维CPU八条抽核、离线24/24、法规名＋条号联合召回7/7通过。联网socket守卫拒发，7933 token仅估算，不是账单。
- 前端没有变化，本次不重跑前端；同根较早54项／lint／tsc／build证据限定复用，不假装每条日志都属于pypdf6.19.0重新执行。

交叉汇总从新JUnit／XML／审计JSON及命令记录计算，见 `evidence/pdf619-evidence-summary.json`；没有用旧85.09%、旧1671或6.16.1日志冒充当前结果。

### 9.2 审计与剩余风险

17:06:43–17:07:04新实装审计 **57行／10包／32个别名归并组**、rc=1有效JSON。pypdf6.19.0、FastAPI0.141.1、Starlette1.7.0、pytest9.1.1均正常审计且0通报；pypdf历史8条本次不再返回。**没有据此声称全环境安全或在本轮重放漏洞攻击**。

torch+cpu仍被跳过，上游torch2.6.0的24行／22组沿用同日较早查询、有限适用，未冒充CPU逐条验证。其他模型／LangChain／Chroma／setuptools风险仍在；模型缓存官方完整性未验、裸cast_to=dict兼容rerank缺口未修。当前风险表和全部ID／别名见 `pdf619-current-risks.md`／`pdf619-current-audit-summary.json`；旧65行／40组明确是6.16.1历史。D2仍未签，2026-10-05复审日未延长，审计红灯没有ignore。

### 9.3 自审发现、恢复与保护

自审实际阅读PDF共用解析、输入校验、两上传路由和完整新增测试。中文期望来自手写PDF／确定UTF16BE文本，不使用被测解析器生成；成功上传仅隔离存库／审计写边界，不mock PDF解析。限流测试打开真实Limiter、验证累计400后429并finally清理。只捕获PyPdfError，不吞任意异常，不把400转换说成资源耗尽修复。没有新增架构、放松门禁、删除测试或整支旧候选合并。

后置核对拦下一个SQLite额外文件：既有conftest.real_kb会先打开默认库，再检查记录数量而skip；该文件创建于15:55的6.16.1全测期间，新版测试复用它。只读检查1集合、0文档／0metadata／0队列，随后**只把这个实验根内空库移到runtime隔离区，原字节SHA一致，可恢复、未删除**，不改真实库／测试夹具、不加忽略规则。保留第一次源码失败记录，再取新版最终2658文件清单。旧6.16.1清单15:54采集早于全测，旧恢复是该快照的匹配，不能读成测试后集合已核对；本报告已纠正。

新版恢复首轮在解包／补丁／2658文件比对后，辅助脚本因命令列表覆盖argparse局部变量而失败；只改局部命令变量名。原日志与两目录移到同根first-failure路径保留，修正后新空目录恢复2658文件全部SHA一致、没有打开恢复库或应用。失败属交付辅助脚本，不冒充业务测试红灯或隐去。

最终薄检查点为执行根下 **`checkpoint-pdf619-lf`，72文件（含清单）**：9完整字段内存值比对0、形状0、禁止文件0。它只含四文件补丁、指纹、选定脱敏证据，不含272MB基线zip、数据库／索引、模型、wheel、venv或node_modules。恢复与卫生证据为 `pdf619-checkpoint-restore.json`／`pdf619-checkpoint-hygiene.json`。完整基线与本地恢复仍含74未公开判定历史HNSW产物，严禁整目录转发；薄集合通过也不等于公开批准或全工作区／暂存／历史零凭据。

17:18保护复核及17:34最终复核均通过：**41对象、原Chroma38文件整集合及逐文件SHA、backend/.env、HEAD／refs、原脏文档均未变；主仓跟踪业务代码未改**。最终记录为 `pdf619-final-protection-after.json`；薄包保留17:18时点记录，不改写已验包内证据。本轮主仓只新增／更新计划、报告和下载说明。未提交／合入／push、写真实库或部署。

### 9.4 结论

**本次pypdf6.19.0最小升级及受影响技术复验、自审完成，未发现新增阻断性业务缺陷。完整阶段仍部分完成：最终候选真实rerank需新轮次许可；D2／Windows用途需Owner裁定，Linux／远端CI未验，最终候选接受和对外交付未批准。** 自审是主助手复核，不冒充独立第三方审查。无需重复下载或为此新增服务器任务。

## 10. 续跑：模型来源与最终rerank预检（2026-10-02）

本轮按“继续执行”完成现有范围内的只读核验。沿用同一隔离根，只增加仓外证据辅助脚本、给既有源码／保护检查器增加新输出前缀，并修订这两份报告／计划；业务源码、依赖环境、共享缓存和`.env`没有修改。未再下载wheel、模型或镜像；未加载模型或发送真实rerank。

### 10.1 模型证据与限制

23:05实际读取默认HF缓存：`refs/main=f03589ceff5aac7111bd60cfc7d497ca17ecac65`。其11个文件中权重为409138989字节`pytorch_model.bin`；另一个`b034223b74fa1f0984ea672da37ef94e92c0ef2a`快照仅有409097104字节safetensors。两快照现存12文件均记录本地SHA；BIN为`731cf5d88ed555a21ff2f2d9fa4db43b10489173ddd9178db3eecfd7a2bae044`、safetensors为`eccb1d9474c3fc136f990876f96cc3636fa49c782281e0f41c080b3f07cc8c62`。前者仅与[官方当前main指针](https://huggingface.co/BAAI/bge-base-zh-v1.5/raw/main/pytorch_model.bin)比较，后者与[官方精确提交指针](https://huggingface.co/BAAI/bge-base-zh-v1.5/raw/b034223b74fa1f0984ea672da37ef94e92c0ef2a/model.safetensors)比较，大小／SHA均相等；不偷换两种证明范围。

本机精确旧提交API连接在10秒超时，rc=28，命令记录保留为`bge-official-f03589ceff5aac7111bd60cfc7d497ca17ecac65-command.json`，没有自动重试或改用镜像下载。配置／tokenizer等只做本地指纹，没有取得全部精确上游指纹，结论仍**PARTIAL**。缓存解析加已装Transformers的fallback源码表明默认main缺safetensors而有BIN；这是不加载权重的静态路径核验，不假称本次动态追踪了torch.load。已有另一快照safetensors也不证明应用会用它。module类型为既有Transformer／Pooling／Normalize、config未见auto_map，不足以判定模型链全部安全，§9.2中的模型依赖风险仍在。

命令为独立venv执行`evidence/model-rerank-preflight.py`，rc=0；该脚本禁联网、不启动应用，不反序列化或修改缓存。输出`bge-provenance-preflight.json`明确记录全部上游文件未验、模型加载0和来源PARTIAL。实际执行版本已保存为`model-rerank-preflight-executed.py`，SHA为`1157f5dfcb8c09bd87119028fbb45ea528e83b6972ed89ea2e349cea1e734f60`；随后只调整导入排序，并给防异常泄密的CLI捕获加单行规则说明。原lint两项失败保留，修正后Ruff退出0，原JSON未覆盖、不伪称预检再执行。新旧辅助脚本绑定见`post-model-self-review-bindings.json`；业务源码及已测包装器未改。脚本位于既有执行根的evidence，不能把这个新证据自动夹入已验薄包或修改包内旧清单。

### 10.2 最终rerank条件与凭据入口

`final-rerank-preflight.json`核对固定烟测SHA、1528公开记录正文SHA白名单、7问、当前单模型`BAAI/bge-reranker-v2-m3`和`https://api.siliconflow.cn/v1/rerank`一致，端点／模型与[SiliconFlow官方接口](https://docs.siliconflow.cn/docs/api/rerank-post)相符。理论7次HTTP；现有包装器硬上限21。11946字符／7933 token限定复用同源离线池估算，不是重新检索／平台计费值；平台剩余配额未验。

系统主key仅在内存读取／格式验证，日志没有原文、长度或key哈希；本次没有请求测试其有效性。**当前进程未继承RERANK_API_KEY，按普通dotenv规则会取文件字段，且文件字段不同于系统字段。** 这是值选择模拟核对，不是实际启动成功证据，也不能据此推断正在运行的别的进程使用何值。后续验收入口只读系统主key、内存注入、禁文件／备用回退；正式应用启动入口另需受控验证，不写回.env或改变产品配置优先级。仅看到新key存在不证明暴露的旧主备已经撤销。

本次在最终venv重新执行假传输包装器32＋假值配置4，共**36 passed，rc=0**，新JUnit无失败。包装器和测试SHA分别为`b2b018165d89dfcc87d8e8af667611dd36e668dbb67b3e512b91e8aa7831ba20`／`873caa7a510c49975668af846f68c349bd705a5954781a009251b6dd12bc1799`，与第三轮逐字节一致；它们只证明守卫与假值优先级，不证明产品真实认证／SDK兼容分支。后端1680等全测读数仍明确引用§9，本次没有伪称重跑。

### 10.3 保护、自审与下一停点

重新生成源码2658文件清单，仍仅四处授权差异、冻结文件不变；其中nodeid比较复用§9收集日志，不是本轮新collect。23:06保护复核：41对象、原Chroma38文件整集合／SHA、.env、HEAD／refs、原脏文档和主仓跟踪代码全部不变。证据是`post-model-candidate-source-verification.json`／manifest、`post-model-protection-after.json`。没有修改已验72文件薄检查点，也未提交、合入、push、写真实库或部署。

自审确认：官方期望SHA来自独立指针、不是从本地文件反推；本地BIN相同不能填补旧提交及配置证明缺口；另缓存safetensors不自动降低当前BIN风险；密钥比较仅输出布尔值，不能被当作有效性或撤销证明；36项假测试不能冒充7次真实调用。未新增业务模块、模型升级、锁包体系或评测框架。

**下一步申请新一轮最终候选真实rerank：仍是上述1528公开记录／固定7问／单模型，预计7次，沿用已测硬上限≤21；只读系统主key内存注入，SDK重试0、不跟随重定向、逐问清缓存、401后拒发、无外层重试或追加轮次。** 使用本执行根此前未启动的evidence轮次标记和新空账本／新日志，不能删前三轮标记或复用其授权。预检JSON中的建议上限7尚未实现，不与现有21硬上限混写；若Owner要求硬上限7，再作最小守卫修改和假传输复验后调用。

新轮次、D2／Windows接受仍待Owner；2026-10-05复审日不延长。模型来源PARTIAL、普通启动凭据入口差异、Linux／CI和真实生成／浏览器未验都是未关闭事项。**本轮预检完成，完整本地阶段仍部分完成，发布阶段未启动。**

## 11. 最终声明环境真实rerank与自审（2026-10-02 23:25）

Owner对前一条精确请求回复“批准”，只授权1528公开记录／固定7问／当前单模型／≤21次HTTP。继续使用本报告同一候选root、Python3.11.0独立venv，FastAPI0.141.1、pypdf6.19.0、pytest9.1.1等167实装分发未变；不借旧venv结果替代当前环境。包装器逐字节保持第三轮已审版本；§10的32＋4假测试是23:06结果，本次没有伪称再跑一次或重跑1680项全测。

### 11.1 调用前绑定与实际结果

23:22新保护检查通过：41对象、38原Chroma文件、整份.env、HEAD／refs和原脏文档未变。重新验证27项直接需求／167条精确约束，实装、需求和约束指纹与§9一致；2658源码文件全部与最终已验manifest相同；12模型文件／默认引用未变，模型来源PARTIAL没有被改成通过。新进程核对公开库1528记录、正文／metadata／输入向量和数值读回、QA=0；集合SHA仍`581dbbd83df721538dbf9df2f6e11e70c434e525a85d7f3d24f08a1d90b3b880`。

**23:24:51–23:25:08实际单次执行rc=0：HTTP共7次且全部200，有效真实重排7/7，法名×条号联合召回7/7，原快速烟测24/24。** 24项由意图7／召回7／引用3／复杂度4／自检3组成，仅7个实际检索问句，不是24题LLM生成回答。`final-rerank-real.log`记录逐项PASS与脱敏发送清单；`final-rerank-real-command.json`记录完整非敏感命令、解释器和时间；`final-rerank-real-summary.json`独立重算日志、退出码、7个case／序号／状态／正文SHA白名单，不直接采信包装器一个passed字段。

实际仍走`BAAI/bge-reranker-v2-m3`和已核对的SiliconFlow原生端点；每次发送鉴权头与本轮所选系统主key相符。SDK重试0、禁止跟随重定向、逐问清检索缓存、没有外层重试或追加轮次；守卫拒绝0。7个发送正文SHA列表与§9同源离线池逐项相等，不含QA或私有上传件。系统key仅内存读取／注入，未写.env／注册表、未保存key原文／长度／key哈希；本轮未调用生成模型或云端嵌入，嵌入仍本地CPU。平台余额／账单未查询，7933 token仍只是旧离线输入估算，不当作实际消费。

### 11.2 验后保护与自审

23:25原保护检查再次通过；验后新进程公开库仍1528条／QA=0，全部审核指纹、输入向量和集合SHA与前测一致；HNSW读回183条FLOAT32归一化微差仍在原阈值内，不伪称索引字节全相等。验后源码manifest仍2658文件且全部SHA与前测相同，167实装分发未变。证据分别为`final-rerank-after-protection-after.json`、前／后`final-rerank-*-public-copy-verification.json`、`final-rerank-after-candidate-source-verification.json`／manifest。

三旧轮次标记及当前第四个`evidence/rerank-round.started`均保留，没有删除失败日志／标记。配额监控total=0时`deduct_utility`正常no-op，不创建`rerank-quota.sqlite`；验后一个`Get-Item`命令误假定它会存在而报错，发生在公开库验证已成功之后。按源码及存在性纠正这个读取假设，原真实轮次rc=0、公开helper rc=0不变；没有修产品、造空账本、删除标记或重新联网。防重复执行依靠独占标记，而非账本存在性。

主助手自审确认：真实HTTP状态／数量、case有效排序、黄金法名×条号和24项原判据同时成立；没有用缓存、200状态单独、fake结果或余弦降级当rerank通过。该结果只覆盖本次Windows／公开语料／原生单模型路径，不证明其他模型、裸cast_to=dict兼容分支、产品默认重试、真实生成答案质量、浏览器／Linux／远端CI或生产配额逻辑。§10的零调用预检JSON继续保留其原时间语义，授权和本轮结果另记，不覆盖旧证据。

### 11.3 当前剩余事项

**E2最终声明环境的限定真实验收已关闭，当前许可已耗用，不再追加调用。** 仍需Owner裁定D2／Windows本地用途及期限（2026-10-05复审日不延长），模型来源PARTIAL和正式启动凭据入口差异仍保留；Linux／CI、真实生成／浏览器等也未验。当前已验72文件薄包没有改写，也不含本轮新增材料；最终交付若整合新增证据，需要另建精确薄集合清单并重新做卫生核验，不能转发完整272MB基线或恢复根。

本轮没有提交／合入、push、真实库写入或部署。**完整本地阶段仍部分完成，发布阶段未启动；本次“批准”不代替风险签字或后续授权。**

## 12. 启动凭据与裁定材料续办（2026-10-03）

本轮沿用Owner“继续”的本地收口授权。新增裁定材料为 `C:/Users/33393/Desktop/ai-legal-helper/docs/local-candidate-decision-20261003.md`；没有修改产品源码、配置文件或依赖，没有新的真实模型调用。

00:16实际执行最终候选venv的 `python -I -B evidence/startup-credential-check-20261003-v2.py`，退出0，`startup-credential-check-20261003.json`记录6项检查均通过。真实Settings／dotenv证实进程值优先于文件、空字符串不被文件补齐、已有Settings实例不会自动刷新，以及真实系统主值在加载真实.env后保留。源码／配置文件指纹未变，网络尝试0、main未导入。初版探针清空Windows运行时变量导致OSError，原文件和脱敏失败JSON均保留；v2仅隔离应用配置字段，未修改产品。

**本日当前子进程已经继承正确系统key**，不同于§10前测时“进程缺值”；`.env`值仍不同。最小处理是启动前在目标进程中注入系统主值，材料已给可审阅命令。未自动改变其他进程、写.env或加入注册表配置逻辑。此结论仅关闭配置读取原因和处理方式，不宣称完整服务启动、数据库初始化或浏览器验收通过。§11的7次真实请求仍是上一日证据，本日没有重跑。

D2材料列明当前57行／10包／32组历史审计、torch扫描缺口、模型来源PARTIAL和未验范围，给出限定本地接受／暂不接受两项；待Owner裁定，2026-10-05复审期限不变。未代签、未提交／合入或推送部署。

交付集合新建于同候选根的 `checkpoint-closeout-20261003`，从旧薄集合的精确清单复制并加入真实rerank／模型来源／配置检查和最新报告；旧72文件集合原样保留。独立manifest逐字节核对、完整凭据字段值／形状扫描和原保护结果分别以 `evidence/closeout-delivery-20261003.json`、`evidence/startup-closeout-protection-after.json` 为准。文件缺失或passed不为true时，不得宣布交付完成。该集合仅用于本地评审，不含完整来源归档、模型、环境或数据库，不是公开发布许可。

## 13. 模型来源补查与依赖最小分案（2026-10-03）

Owner再次“继续”后，执行只读来源补查、安装依赖图／源码AST核查和离线缺包模拟。详细任务与验收条件见 `docs/process-archive/superpowers/plans/2026-10-03-dependency-risk-followup.md`，没有实际删包／升级／下载wheel或权重。

`dependency-followup-20261003.json`记录268个Python文件AST与实装默认依赖关系：未见langchain总包／community直接import，community只被总包要求；实际使用text-splitters需补为直接声明。外部`--adapter`动态入口仍需核对。该结论只支持开展去包实验，不是已经证明可删除。

`dependency-removal-probe-20261003.json`整体rc=1／passed=false：三模块不可导入阳性控制成立，切分／消息／ChatOpenAI构造／jieba字典回退四项分项成立，但发生一次被守卫拦截的socket.bind。未用分项通过覆盖整体失败；保留记录，后续先定位绑定调用栈，再判断所需隔离方式。源码／venv未改，未发送HTTP。

官方精确模型revision目录可访问，但元数据API／指针取证未完成，本机curl8秒连接超时退出28，未创建输出文件，来源保持PARTIAL。setuptools83.0.0官方wheel元数据已核对，精确下载候选／SHA写入分案，尚未下载；该版本对pkg_resources的兼容面已列为必验项。旧57行／10包／32组审计仍为10月2日快照，本日没有新安全扫描。

新增文件不在旧86文件交付集合中；旧集合及manifest保留，不覆盖上一检查点。D2仍待Owner裁定，复审2026-10-05不延长；普通完整启动、Linux／CI、生成／浏览器和发布仍未完成。
