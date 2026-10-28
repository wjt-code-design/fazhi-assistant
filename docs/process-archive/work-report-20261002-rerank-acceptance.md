# 公开语料与真实 rerank 验收记录（2026-10-02）

## 1. 结论与范围

**最新结论（第三轮）：限定真实 rerank 验收通过。** Owner 同意改用 Windows 系统级 `RERANK_API_KEY` 作为唯一凭据来源并授权新的一轮后，第三轮实际发送7次，全部HTTP200，有效重排7/7，原烟测24/24，退出码0；原库／受保护对象收尾通过。`BLOCKED-RERANK-AUTH` 对本次限定验收已解除，**不是完整本地候选或普通应用运行配置已完成**。前两轮各一次401仍保留为历史；三轮累计实际发送9次（2次401、7次200），没有自动追加轮次。

Owner 先以 **A** 确认主／备用暴露旧 key 已撤销、新 key 已在本机配置，再于第一轮失败后回复“已配好”“允许”。其后表示已配环境变量；只读核对确认系统级主值与文件主值不同，Owner 明确“同意”第三轮的系统值来源及一次真实验收。前两轮文件凭据被拒，第三轮系统值鉴权成功；没有据此断言未轮换、旧值当前状态或具体撤销原因，也没有保存或展示凭据、长度、key哈希、请求／响应正文。

三轮均只做公开语料隔离、本地 BGE 与烟测，以及各自已授权的一轮真实 rerank。第三轮只调整仓外验收脚本的凭据读取和保护，不改业务代码、`.env` 或系统环境变量；没有包安装／下载、共享 venv 变更、生成模型／云端嵌入调用、原库写入、提交、合并、推送或部署。

绑定源码：`902e2d161e67100ed6d267a08c393538a0abe109` 的 Git 归档，不复制脏工作区或实际 `.env`。解释器为既有隔离环境 `C:/Users/33393/AppData/Local/Temp/legal-closeout-20260928/venv/Scripts/python.exe`；Python 3.11.0、Chroma 0.4.24、OpenAI 1.109.1、httpx 0.28.1、pytest 8.4.2。**此环境不满足最终候选 pytest≥9.0.3 的声明要求，只能证明本轮限定实验，不替代完整 A–F 验收。**

§2–7保留第一轮历史，§8保留第二轮历史；**当前结果和后续边界见§9**，不把前两轮的停点和配置建议当成当前授权。

## 2. 第一轮路径与数据边界

轮次根：`C:/Users/33393/Desktop/legal-rerank-acceptance-20261002-c9c0d7684b274afb9427f27a32638af8`，下称 `ROOT`。

- `ROOT/source`：固定主线归档源码，无实际 `.env`／业务 DB／原 Chroma。
- `ROOT/private-kb/chroma_db`：完整原库副本，受限本机数据；只有该副本通过 Chroma 客户端打开。
- `ROOT/public-kb`：只含已审核法规的独立公开库，实际检索／外发唯一语料路径。
- `ROOT/evidence`：脚本、摘要、指纹、受控 ID 清单、脱敏调用记录及本轮启动标记。

**ROOT 含私有快照，不可整目录转发、打包交付或提交 Git。** 公开库也不提交 Git；需要交付时另筛选非敏感报告和证据。保护清单指纹及本机语料审查产物仅用于本机复验，不把它们自动视为可公开包。

## 3. 一致副本与公开语料审查

复制前未发现匹配项目／导入任务的 Python、Node 或 uvicorn 写入者；相关后端端口无监听，WSL 无运行发行版，配置的 Docker Desktop Linux 引擎不可用。没有停止任何服务。整目录复制前／复制后源文件／副本指纹一致，覆盖 **38 个文件，365566410 bytes**，无 reparse point；不是仅复制 SQLite 文件，也没有通过客户端打开原库。Docker 查询失败是引擎管道不存在，不计作测试通过，也未循环重试。

私有副本 SQLite `PRAGMA integrity_check=ok`；`legal_provisions_cos` 为 cosine，原集合 **10266 条**。筛选结果为四部法规的完整现有条文，共 **1528 条**，不是只抽取七个金标条文：

| 法规 | 本轮条文数 | 政府公开核对来源 |
|---|---:|---|
| 劳动合同法 | 98 | [上海市政府公布的 2012 修正全文](https://www.shanghai.gov.cn/rcjygj/20250606/658d064be68c46fc892530a8cde92258.html) |
| 劳动法 | 107 | [湖北省卫健委转载的 2018 修正全文](https://wjw.hubei.gov.cn/bmdt/ztzl/hbzyjk/fgbz__/202207/t20220701_4200438.shtml) |
| 民法典 | 1260 | [天津市通信管理局公布的全文](https://tjca.miit.gov.cn/zwgk/zcwj/flfg/art/2020/art_20cf1a2e1b854924b5caa744c8045d1f.html) |
| 消费者权益保护法 | 63 | [上海市市场监管局全文](https://fw.scjgj.sh.gov.cn/alc/law/11/1/20240117133417.html)、[北京市政府全文](https://www.beijing.gov.cn/zhengce/zhengcefagui/qtwj/201507/t20150706_780640.html) |

逐条验证完整正文包含条号、去已核对章节前缀后连续匹配公开原件；仅为比较归一空白和 NFKC 表示。上海劳动合同法 HTML 在条号后附 `【题注】`，阅读层显示为 `〖题注〗`，比对时只去政府网页的条后题注，不删除库内未知文本。消保法上海页面缺第一章标题、末条句号，额外核对北京政府原件解决来源不完整；没有放宽成相似度匹配，也没有改库内正文。

metadata 逐条限制为 `source/article/chapter/origin/file_hash/effective_from/effective_to/status`，验证法名、条号、公开章节、日期格式、枚举值与哈希形状；未投影或删除字段。1528 条均通过。原库的 `origin=upload` 并未被当成公开证明。QA、聊天和其他 8738 条不进入本轮公开集合；**不据此宣称全库召回率、所有法规版本或答案法律质量已审完。**

首次比对未通过及原因保留在 `public-corpus-review-first.json`，成功审查记录在 `public-corpus-review.json`。政府页获取失败也未当成功；SAMR 页面未取得可核对正文后使用上述已核对的政府转载原件，不重复盲试。

## 4. 复制、恢复与模型空间

完整 ID、正文和 metadata 的逐条指纹一致。复制时逐批传入原有向量，不调用嵌入生成器。公开库 SQLite 写入队列的 **1528 条 FLOAT32 输入向量逐字节 SHA-256** 均等于私有副本审查时记录的向量指纹。

初次恢复采用“所有读回向量字节必须相同”判据，退出码 1；加阶段诊断后确认只有向量指纹不同，ID／正文／metadata 均一致。实际是 cosine HNSW 重新归一化后的浮点表示差异；该行为见 [hnswlib 官方 README 和实现](https://github.com/nmslib/hnswlib)。没有为了匹配哈希改写向量。

新进程恢复分别检查严格输入字节和索引读回数值：全部 1528 条输入字节相同；183 条索引读回指纹不同，最大绝对差 **2.9802322387695312e-8**，最小余弦相似度 **0.9999999999999991**。索引另限定绝对差≤`1e-6`、余弦误差≤`1e-10`，输入字节核对不得豁免。SQLite integrity=ok、唯一集合 `legal_provisions_cos`、1528 个 ID、逐项指纹及向量查询可用性通过，恢复检查退出码 0。源码 smoke 与复制脚本未改写法条或索引配置。

本地 BGE `BAAI/bge-base-zh-v1.5`／CPU／768 维：每部法规按 ID 排序固定抽两条，共 **8 条**重新计算本地嵌入，最低余弦相似度 **0.9999999999998204**，判据≥0.99999。使用缓存并禁网；无模型下载／云嵌入。**这是模型空间抽核，不是1528条全量重算，也不只靠“维度相同”推断模型一致。**

## 5. 第一轮离线与真实结果必须分开

固定配置：hybrid=true、pool_k=0、原 smoke k=6、查询改写关闭、本地 BGE／同一公开库。原 `smoke_citation_fast.py` SHA-256：`d3735bb6d98ad08397034cbf88ac5a38c7b423e30d515db946b57a8ff85e41e3`。题集／法名×条号联合判据未改。

| 检查 | 实测结果 | 真实退出码 |
|---|---|---:|
| 包装器假传输自检 | 17 passed；预算、外发白名单、重试／重定向、重复启动等负例 | 0 |
| 关闭 rerank、禁网的原烟测 | 24/24，其中真实公开库检索 7/7 | 0 |
| 开启真实 rerank 的原烟测 | 烟测 24/24，实际有效重排 **0/7** | **1** |
| 原数据／引用收尾复验 | 原库38文件、保护41对象、HEAD／引用、冻结文件／原脏文档均未变 | 0 |

真实轮次：**2026-10-02 12:13:50 至 12:14:18（+08:00）**，`BAAI/bge-reranker-v2-m3`，实际发送 **1 次**，HTTP **401**，白名单拒发 0；没有隐式 SDK 重试或重定向发送。第一题发送16条已审核公开法条，未输出正文；后六题因产品 `mark_utility_depleted` 的进程内鉴权失败记忆跳过，回落本地余弦检索。全部题有效重排=false，因此 **24/24 不能用作真实 rerank 通过证据**。

实际 endpoint 为 `https://api.siliconflow.cn/v1/rerank`，已对照 [SiliconFlow 官方 API 文档](https://docs.siliconflow.cn/docs/api/rerank-post)的模型、地址和 Bearer 鉴权。只取得 HTTP 状态，未保存响应体；不推断凭据是否撤销、失效原因、控制台权限或剩余额度的具体情况。

调用预算为单模型七题理论7次、硬上限21次；本轮实际1次。离线候选池字符上界11946、估算token上界7933，只用于事前预算，**不是实际发送token、usage或账单**。[官方价格页](https://siliconflow.cn/pricing)本轮列非 Pro 的该模型免费；没有独立核对账户账单或余额，不宣称实际计费为某个确定值。

## 6. 第一轮只读鉴权排查与当时建议（历史记录）

实际只在内存读取 `C:/Users/33393/Desktop/ai-legal-helper/backend/.env` 中 rerank 所需字段。`RERANK_API_KEY` 优先，`SILICONFLOW_API_KEY` 仅在前者为空时回退；本机两者均非空且值相同，没有边界空白、换行或常见占位文本。仓根 `.env` 的有效值也相同，但本轮不从该文件读取。因此没有发现“两个不同 key 被优先级遮盖”或“根目录新 key 没同步”的证据；也不能据此证明凭据有效。

第一轮后的建议是 Owner 在本机核对 SiliconFlow 控制台有效 key 与 **backend/.env 的 RERANK_API_KEY**；若仅更新 SILICONFLOW_API_KEY，需显式清空旧 RERANK_API_KEY 才会使用回退字段。不要把值、截图明文或长度发到聊天／报告。

Owner 随后已回复“已配好”并另授权“允许”，第二轮按新路径／新空配额账本执行，见 §8；本段不是继续调用的授权。第一轮 `evidence/rerank-round.started` 和原日志保留，未删标记、未覆盖，也未把未发送的六题写成六次401。

其余 A–F 完整候选工作、D2风险接受、声明一致环境、依赖最新审计、前端与Linux／远端CI等，仍以执行书为准；本报告不改变这些任务的授权或未完成状态。未选服务器并不妨碍远端 API 验证，但部署仍未获准。

## 7. 第一轮关键证据与已执行命令

证据均在 `ROOT/evidence`：`isolation-summary.json`、`public-source-receipts.json`、`public-corpus-review.json`、`public-copy-verification.json`、`vector-copy-diagnosis.json`、`bge-space-verification.json`、`wrapper-tests.log`、`offline-smoke.log`／`offline-smoke-summary.json`、`real-rerank.log`、`offline-command.json`／`real-command.json`、`protected-after-summary.json`。脚本也留在该目录，不依赖诊断 TEMP；解释器和模型缓存仍依赖本机既有环境，不是独立安装交付包。

实际两条重型命令如下，cwd均为 `ROOT/source/backend`；此处记录已执行命令，**不是允许再次执行真实轮次**：

```powershell
& 'C:\Users\33393\Desktop\legal-rerank-acceptance-20261002-c9c0d7684b274afb9427f27a32638af8\evidence\run-scope.ps1' -Mode offline
& 'C:\Users\33393\Desktop\legal-rerank-acceptance-20261002-c9c0d7684b274afb9427f27a32638af8\evidence\run-scope.ps1' -Mode real
```

进程启动／结束时间和真实退出码记录在两份 `*-command.json`，未拿显示日志的命令退出码顶替测试码。准备副本脚本曾因误写 `backend/agent/prompts.py` 退出1；只修正一次性脚本路径为 `backend/prompts.py`，保留已比对成功的副本，完成归档冻结文件核验；未清理或反复重拷原库。失败与成功口径均在本报告分列。

## 8. 第二轮：文件凭据仍鉴权失败（历史记录）

### 8.1 授权、来源与隔离

Owner 的“已配好”只触发只读配置核对；其后明确回复“允许”，才执行这一轮。范围仍为原七题、同一公开语料／源码／模型，最多21次物理HTTP发送尝试，不试备用凭据或其他模型，不扩大到完整 A–F。两轮目录和账本独立，启动标记都保留。

第二轮根：`C:/Users/33393/Desktop/legal-rerank-round2-20261002-abc6d089a8a84bba90d7a87673936fae`，下称 `ROOT2`。复用第一轮已审核的 Git 归档、8项脚本／审查产物和完整公开库；不重新复制私有原库，不把私有快照搬入新轮次。`ROOT2/public-kb` 的6个文件、14425914 bytes整目录复制前后指纹相等，旧公开目录也未变化。

源码仍绑定 `902e2d161e67100ed6d267a08c393538a0abe109`，归档 SHA-256 为 `c4cd829f76ed85972d710dd2d8050aa7cfc4caf46fa45594c676c1f3bec31992`；冻结文件及原烟测哈希相符。没有实际 `.env`／业务数据库进入源码。新轮仍用 §1 的既有隔离解释器，不安装依赖；pytest 8.4.2 的声明不一致限制仍在。

### 8.2 本轮实测

| 检查 | 第二轮结果 | 真实退出码 |
|---|---|---:|
| 包装器假传输测试 | 17 passed | 0 |
| 新进程公开库恢复 | 1528条正文／metadata／ID及输入向量核对通过，唯一cosine法规集合，QA复制0条 | 0 |
| 本地 BGE 模型空间抽核 | 8条，最低余弦相似度0.9999999999998204 | 0（随离线入口） |
| 禁网、关闭 rerank 的原烟测 | 24/24；真实公开库检索7/7 | 0 |
| 真实 rerank 的原烟测 | 烟测24/24；实际发送1次、HTTP401，有效重排0/7 | **1** |
| 原库／受保护对象／引用收尾 | 原库38文件、保护41对象、本轮配置文件、冻结文件、原脏文档、HEAD／refs及旧公开目录均未变化 | 0 |
| 新公开库验后恢复检查 | 1528条记录集合指纹与验前相等，向量查询可用 | 0 |
| 禁网配置链路诊断 | 只读取配置、导入独立 settings，不发送HTTP | 0 |

真实入口开始 **2026-10-02 13:06:12**、结束 **13:06:39（+08:00）**；本轮仅第一题向 `https://api.siliconflow.cn/v1/rerank` 发送16条已审核法条，模型 `BAAI/bge-reranker-v2-m3`，返回401，白名单拒发0次。后六题在同一进程中因产品的鉴权失败记忆跳过，使用本地余弦精排；没有自动重试、重定向、另开一轮或补发请求。

第一轮和第二轮的结果一致，但**没有证据证明两轮实际 key 相同**。第一轮主／备值相同，第二轮不同；这是安全的配置状态差异，不是对旧／新 key 原文、长度或 key 哈希的记录。

新公开库的验前／验后记录集合 SHA-256 均为 `581dbbd83df721538dbf9df2f6e11e70c434e525a85d7f3d24f08a1d90b3b880`。全部1528条输入向量字节仍严格相同；183条HNSW读回字节差异及数值容差结果仍同 §4，不能改称全部读回字节完全相同。此次只重新核对原审查指纹，没有重新抓取、重审全部政府网页。

单模型七题理论7次，硬上限21次，第二轮实际1次。离线字符／token估算上界仍为11946／7933，不是计费usage。补充检索到的 [官方价格页](https://siliconflow.cn/pricing)索引列非Pro模型免费；该索引标记为5天前抓取，直接页面读取曾失败，因此不据此保证账户当前价格、余额或实际账单。

### 8.3 只读排查确认了什么

在禁网进程中读取实际 `backend/.env` 并导入 `ROOT2/source/backend/settings.py`，只输出以下安全状态：

- `RERANK_API_KEY` 非空并优先选中；配置对象的有效值等于检查的文件值。
- `SILICONFLOW_API_KEY` 也非空，但与主字段不同；它不是本轮选中的凭据，未追加测试它。
- 根目录 `.env` 的有效值与 backend 的有效值相同，不支持“只改了根目录、backend未同步”的解释。
- 已查字段没有重复定义；所选值没有空白、`Bearer `前缀或非ASCII字符；实验源码无实际 `.env`。
- 实际端点通过发送前白名单校验，等于上述 SiliconFlow 国内端点；本轮配置文件验前／验后指纹相等。

静态调用链为：包装器显式清掉终端旧配置 → 从 backend/.env 读六个 rerank 字段 → `Settings`读取进程变量 → `retrieval._rerank_docs` 的 SiliconFlow 分支用 `rerank_api_key or siliconflow_api_key` 构造 Bearer头。排查没有输出配置对象、实际Authorization头、请求／响应正文，也没有额外网络调用。

[官方接口文档](https://docs.siliconflow.cn/docs/api/rerank-post)将401列为无效token；本次仍只保存状态码，没有平台账户／控制台证据。**可以确认所选凭据的鉴权未通过，不能确认是错误平台的key、撤销状态、权限、复制问题或平台异常；也不能把它改判为配额不足、没有服务器或请求超时。** 不自动改业务代码、切端点、改模型、试备用key或反复轮换来掩盖未知根因。

### 8.4 当前停点与下一步

第二轮结束时仍为 `BLOCKED-RERANK-AUTH`。当时的建议是先由 Owner 在本机核对：**backend/.env 中 RERANK_API_KEY 是否确实为 SiliconFlow 国内控制台的当前有效凭据，且控制台状态正常**。不要把值、长度、含明文截图或完整控制台请求发给助手。主／备值不同不等于备用有效，也不构成改试备用的许可；之后来源核对和第三轮授权见§9。

建议先完成平台归属／控制台状态核对，再决定是否授权第三轮；本次“允许”已经用于第二轮，不延伸到第三轮。即使继续验收，也须另用新路径／新空账本，保留两轮启动标记／日志，继续限制原题集和21次上限。

完整 A–F、两项依赖的最终声明一致环境、D2风险裁定、综合本地候选验收仍未完成；此次未提交、合并、推送、部署或写原库。诊断脚本与报告是局部验收产物，不是业务修复交付。`systematic-debugging` 使本次在根因未确定时停于只读排查，没有以推测代替修复。

### 8.5 第二轮证据与已执行命令

证据在 `ROOT2/evidence`：`isolation-summary.json`、`reused-artifact-fingerprints.json`、`rerank-approved.json`、`wrapper-tests.log`、`public-copy-before-acceptance.json`／`public-copy-after-acceptance.json`、`bge-space-verification.json`、`offline-smoke.log`／`offline-smoke-summary.json`、`real-rerank.log`／`real-rerank-summary.json`、两份 `*-command.json`、`protected-after-summary.json`、`config-chain-summary.json`。保护／配置指纹只用于本机复验，不把目录自动视为可公开或可提交的包。

下列为已执行命令，不授权再次启动真实入口；两条cwd均为 `ROOT2/source/backend`：

```powershell
& 'C:\Users\33393\Desktop\legal-rerank-round2-20261002-abc6d089a8a84bba90d7a87673936fae\evidence\run-scope.ps1' -Mode offline
& 'C:\Users\33393\Desktop\legal-rerank-round2-20261002-abc6d089a8a84bba90d7a87673936fae\evidence\run-scope.ps1' -Mode real
```

所有真实HTTP统计来自包装器的实际发送记录，失败时也保留计数；没有用24项原烟测的总数代替7项真实重排判据。

## 9. 第三轮：系统级主凭据、真实重排通过（最新）

### 9.1 已授权的来源变更

Owner 表示“我已配置好环境变量”后，禁网只读核对发现：Windows系统级主字段非空，与 backend/.env 的主字段不同；backend/.env 全文件指纹与第二轮相同，用户级没有这两个凭据变量，当前Codex子进程也没有继承系统级主字段。原验收入口又会显式读文件值，所以“系统变量已配置”不等于该入口已使用它。

Owner 随后明确“同意”：新一轮**只取系统级 RERANK_API_KEY，仅内存读取，不复制到文件、不改.env；原七题，最多21次物理HTTP尝试，遇401停止后续真实发送，不试备用凭据**。该授权已经用于第三轮，不延伸到第四轮、普通应用配置修复或完整A–F执行。

第三轮根：`C:/Users/33393/Desktop/legal-rerank-round3-20261002-cebf70a641c549f9ad44c27cf27261a9`，下称 `ROOT3`。源码仍为902e2d1的同一Git归档；复用第二轮已核对的完整1528条公开库，整目录6文件、14425914 bytes复制前后字节一致，无新私有副本／QA记录／嵌入重建。使用同一既有隔离解释器，声明不一致限制仍同§1。

只有 `ROOT3/evidence/rerank-acceptance.py` 和其测试相对上一轮变化：用标准库 `winreg` 只读HKLM系统环境路径的唯一主字段，清除继承值／文件备用字段，只从.env取原有四个非敏感模型／端点设置；缺失、访问拒绝、无效类型或格式时拒绝运行，不回退。每次真实发送前在内存中核对实际Authorization头等于本轮所选凭据，仅记录布尔结果。401后设置显式停止标志，后续题降级但不得再发送。

没有增加通用凭据框架、改变产品配置优先级或写注册表。包装器与产品运行方式存在刻意差异，见§9.4；本轮不修复普通应用配置。

### 9.2 红绿验证与真实结果

新增15项安全测试先在旧包装器上失败，原因是旧入口继续选文件值、未拒绝系统字段异常、未核对实际鉴权头且假传输401后仍发送。初次实现后31项通过、1项旧原生假传输测试失败：其夹具缺少产品真实路径已有的Bearer头；仅补齐该夹具，不放松发送检查。失败日志保留，随后全部32项通过。测试只用假凭据、假注册表边界和本地假HTTP传输；不读／更改真实系统Key，不把这些请求算成真实验收。

| 检查 | 第三轮实测 | 真实退出码 |
|---|---|---:|
| 新增测试的旧代码红灯 | 15 failed、17 deselected，预期行为缺失 | 1（预期红灯） |
| 最终包装器安全回归 | 32 passed，无真实HTTP | 0 |
| 公开库独立恢复与验后复核 | 1528条完整指纹、输入向量字节和索引数值核对通过，QA0条 | 0 |
| 本地BGE模型空间抽核 | 8条，最低余弦0.9999999999998204 | 0（随离线入口） |
| 禁网／关闭rerank原烟测 | 24/24，真实公开库检索7/7 | 0 |
| 系统凭据预检 | 来源明确、格式通过、与文件主值不同，无HTTP | 0 |
| **真实rerank原烟测** | **实际7次HTTP，全部200；有效重排7/7，原烟测24/24** | **0** |
| 原库／保护对象／引用收尾 | 原库38文件、41保护对象、.env、冻结文件、原脏文档、HEAD／refs、第二轮公开库和旧脚本未变 | 0 |

真实入口 **2026-10-02 15:04:25 至15:04:41（+08:00）**；模型仍为 `BAAI/bge-reranker-v2-m3`，端点仍为 `https://api.siliconflow.cn/v1/rerank`。原七题逐题清缓存；发送文档数依次为16、13、13、14、12、12、12，正文逐项在D审核名单内。七次发送的 `authorization_matches_selected_credential=true`；拒发0次、401停止标志false、无隐式重试／重定向。每题有效排序均为完整原候选对象排列，不是None／余弦降级。本轮没有追加探测接口、其他模型或云嵌入调用。

预算仍为单模型理论7次、上限21次，本轮实际7次。离线候选池字符／估算token上界11946／7933仍只作事前预算，不是实际发送usage或账单。补充 [官方价格页](https://siliconflow.cn/pricing)检索索引仍列非Pro模型免费，索引标记6天前抓取；未核对账户账单，不宣称实际费用为确定值。接口地址／Bearer形式再次对照 [官方接口文档](https://docs.siliconflow.cn/docs/api/rerank-post)。

公开库验前／验后记录集合SHA-256仍为 `581dbbd83df721538dbf9df2f6e11e70c434e525a85d7f3d24f08a1d90b3b880`；向量输入与HNSW数值判据同§4，不改变为全部读回字节相同。所有旧轮次标记与日志保留。

### 9.3 判定能说明什么

本轮证明：**系统级主凭据在本轮端点／模型上鉴权成功，限定公开语料七题真实重排与原烟测通过**。前两轮走文件值返回401，本轮走系统值全部200，配置来源不一致得到明确定位并在仓外验收入口中纠正。

不能据此证明文件中的旧值今天仍无效、其平台归属／撤销原因、备用Key有效、全库召回率或全部法规版本质量；本轮没有再次测试文件值或备用值。也不能推断长时间稳定性、吞吐、生产默认SDK重试、用户隐私数据外发合规或完整生成答案质量已经验完。

### 9.4 当前剩余工作与执行边界

`BLOCKED-RERANK-AUTH` 对这次限定验收解除，**不需要为了证明成功自动再跑一轮**。后续真实请求仍须新授权和新路径／账本，不能删标记重跑。

`backend/.env` 与Windows系统值仍不同，现有已运行Codex／其他进程可能持有旧环境；普通应用的启动入口与所选凭据尚未验。本次不将系统Key复制到.env，也不更改业务配置或重启其他服务。下一次候选集成时，应先只读确认实际启动入口的配置优先级和环境继承，再按Owner选择保持一个明确来源；没有证据就不写“所有入口已修复”，也不默认修改或轮换凭据。

完整A–F、两项依赖最小整合、最终声明一致新环境与综合验收、D2风险裁定及Linux／远端CI仍按执行书待办。此次局部PASS不替代这些证据；未提交、合并、推送、部署或写真实库。本轮 `test-driven-development`／`pitfall-sweep-new` 使新增来源、失败关闭和401停止先有红绿证据，未扩成产品架构改造。

### 9.5 第三轮证据与已执行命令

`ROOT3/evidence` 保存：`isolation-summary.json`、`credential-tests-red.log`／`credential-tests-all-red.log`、`wrapper-tests-first-green-attempt.log`／`wrapper-tests-final.log`、`system-credential-preflight.json`、`wrapper-before-real.json`、`rerank-approved.json`、公开库验前／验后记录、`bge-space-verification.json`、离线／真实日志及摘要、两份 `*-command.json`、`protected-after-summary.json`。凭据值／长度／Key哈希不进入这些产物；本机保护文件指纹和路径材料仍不自动视为可公开包。

下列为已执行命令，不授权再次真实启动；cwd均为 `ROOT3/source/backend`：

```powershell
& 'C:\Users\33393\Desktop\legal-rerank-round3-20261002-cebf70a641c549f9ad44c27cf27261a9\evidence\run-scope.ps1' -Mode offline
& 'C:\Users\33393\Desktop\legal-rerank-round3-20261002-cebf70a641c549f9ad44c27cf27261a9\evidence\run-scope.ps1' -Mode real
```
