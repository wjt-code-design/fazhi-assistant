# 剩余依赖风险：预检结果与下一步执行边界（2026-10-04）

> 后续任务的统一入口为 [本地候选后续执行计划](C:/Users/33393/Desktop/ai-legal-helper/docs/process-archive/superpowers/plans/2026-10-04-local-candidate-next-execution-plan.md)。本文件保留预检事实与原始证据；不要把本文件§3与新计划重复执行。后续计划新增普通启动／界面准备和条件验收，仍无下载、安装、风险签署或发布的默认授权。此前 `final-review.json` 对应此次追加链接前的文档快照，保留不覆写。

## 1. 当前结论与对象

**本轮完成的是公开元数据／版本源码预检，不是依赖升级或安全验收。** A 删除闲置总包、B setuptools 83.0.0 及新的 A＋B 仓外联合验证已完成；不因本文件重复安装或重跑旧联合门禁。B 正式采纳、新对象 D2 仍待 Owner，复审 **2026-10-05 不顺延**。本项目未选服务器，本阶段不部署。

受保护联合候选：`C:/Users/33393/Desktop/fazhi-joint-candidate-20261003-ac701f4a880441b5a453b1b7cbb06f01`。Python 3.11.0／Windows amd64／CPU；162 实装分发，165 条候选约束。冻结主线 HEAD：`902e2d161e67100ed6d267a08c393538a0abe109`。requirements SHA-256：`594b9e664f1d63a22180ef6dbdf46ee73948a5d0a938d835e1939c9b86c48d4c`；约束 SHA-256：`e19cd1ef8ecb7c12397a1a72934c727d6c553467b60fc1859715c010b0ab249c`。这些是既有对象身份，不是本轮新安装结果；完整上一轮记录见 [联合报告](C:/Users/33393/Desktop/ai-legal-helper/docs/work-report-20261003-joint-candidate.md)。本文件不改变 [现有候选裁定书](C:/Users/33393/Desktop/ai-legal-helper/docs/local-candidate-decision-20261003.md) 的裁定对象或签署状态。

联合实装审计仍列模型链与活跃 LangChain／Chroma 风险；CPU torch 被扫描器跳过，不是零漏洞。模型精确 revision 的上游全文件来源仍 **PARTIAL**。本次不重新请求此前失败的 HF tree API，也不把依赖升版当作来源补证。

## 2. 本轮已核对的两个分案

### C：模型依赖，先排除错误目标

- **Transformers 5.10.0 已撤回，排除下载。** 5.10.1 未撤回，可作为待验证线索，不能直接判安全或可运行。[官方版本元数据](https://pypi.org/pypi/transformers/5.10.1/json)、[发行说明](https://github.com/huggingface/transformers/releases/tag/v5.10.1)
- **ST 5.6.0 不能认定信任门禁已修复。** 公告列 patched 5.6.0，但该标签源码仍有本地路径绕过信任开关、动态加载后才发警告的分支；上游发行说明也说显式信任要求从 v6.0 起实施。本轮没有运行攻击探针。须核对确切修复源码／发行文件，并用无害本地模块标记的否定测试验证拒绝执行，再讨论关闭；不据此自动选 ST 6.x。[公告](https://github.com/advisories/GHSA-jhr6-gm9c-rqjv)、[5.6.0 标签源码](https://github.com/huggingface/sentence-transformers/blob/v5.6.0/sentence_transformers/util/misc.py#L131)、[发行说明](https://github.com/huggingface/sentence-transformers/releases/tag/v5.6.0)
- TF 5.10.1 默认要求 `huggingface-hub>=1.5,<2`，现有 0.36.2 不满足；hub 精确版本、完整闭包和 0.x→1.x 接口／缓存影响未核对。tokenizers 0.22.2、numpy 1.26.4、CPU torch 2.6.0+cpu 形式满足已查相关直接声明，暂不为此增加换版。**声明兼容不等于运行兼容或安全关闭。**[TF 元数据](https://pypi.org/pypi/transformers/5.10.1/json)、[ST 元数据](https://pypi.org/pypi/sentence-transformers/5.6.0/json)

精确模型 wheel 公告值、直接约束、空 fix 与公告／源码矛盾、后续原数值门槛见 [模型链预检](C:/Users/33393/Desktop/ai-legal-helper/docs/dependency-model-chain-preflight-20261003.md)。模型 JSON／源码当时未另存原始文件，取证时间来自当轮工具输出；下一轮应另存新的原始响应及 hash，不能补造旧快照。

### D：活跃 LangChain，升级不能止于 core

以下是据联合审计修复线调查的 **候选元数据**，不是安装锁或下载单。均核对 Python 声明、未撤回与 Windows Python 3.11 可匹配 wheel；完整传递依赖、实际接口和安全性尚未验证。

| 包／调查版本 | 对下一步有影响的默认声明 | 官方来源 |
| --- | --- | --- |
| langchain-core 1.3.3 | langsmith `>=0.3.45,<1`；新增 langchain-protocol `>=0.0.10`、uuid-utils `>=0.12,<1` | [JSON](https://pypi.org/pypi/langchain-core/1.3.3/json) |
| langchain-openai 1.1.14 | core `>=1.2.31,<2`；OpenAI SDK `>=2.26,<3`，现有 1.109.1 不满足 | [JSON](https://pypi.org/pypi/langchain-openai/1.1.14/json) |
| langchain-text-splitters 1.1.2 | core `>=1.2.31,<2`，不能沿用现有 0.0.2 对 core 的 `<0.3` 上界 | [JSON](https://pypi.org/pypi/langchain-text-splitters/1.1.2/json) |
| langsmith 0.8.18 | 当前联合审计另列该修复线；新增必需 xxhash、zstandard、uuid-utils 等，不能只按旧 0.8.0 分案 | [JSON](https://pypi.org/pypi/langsmith/0.8.18/json) |
| langchain-huggingface 1.2.2 | core `>=1.2.31,<2`；hub `>=0.33.4,<2`；tokenizers `>=0.19.1,<1`。`[full]` 中的 ST／TF 不是默认必需分支 | [JSON](https://pypi.org/pypi/langchain-huggingface/1.2.2/json) |

已检查的 `langchain-chroma` 0.2.5、0.2.6、1.1.0 均在声明上容纳 core 1.3.3，但分别要求 Chroma 本体 `>=1.0.9`、`>=1.0.20`、`>=1.3.5,<2`；**这三个选项都不能保留现有 Chroma 0.4.24**。现有适配包 0.1.4 又对 core 要求 `<0.4`。只对这些已查版本作判断，不宣称遍历了所有历史发行；无上界也不证明实际 API 兼容。[0.2.5 元数据](https://pypi.org/pypi/langchain-chroma/0.2.5/json)、[0.2.6 元数据](https://pypi.org/pypi/langchain-chroma/0.2.6/json)、[1.1.0 元数据](https://pypi.org/pypi/langchain-chroma/1.1.0/json)

因此，把 D 拆成两个验收责任但保留依赖关系：**先核对 Chroma 安全目标／公开库格式迁移可行性，再冻结 LangChain＋SDK＋适配包的一致集合**。不是一次只换 core，也不是以 `--no-deps` 强行解决冲突；不另建 agent 框架、不重写 RAG。Chroma 两条通报没有确定修复发行，升到 1.x 不自动关闭风险，见 [Chroma 适用面核对](C:/Users/33393/Desktop/ai-legal-helper/docs/chroma-risk-triage-20261003.md)。

额外核对了 SDK 2.26.0、protocol 0.0.10、uuid-utils 0.12.0 的精确元数据；uuid-utils 的 `cp39-abi3-win_amd64` wheel 在本机标签集合中可匹配。未选定 xxhash、zstandard、hub、Chroma 本体的精确版本，**没有完整闭包**；不得将此表直接转换成 pip 安装指令。[SDK 元数据](https://pypi.org/pypi/openai/2.26.0/json)、[protocol 元数据](https://pypi.org/pypi/langchain-protocol/0.0.10/json)、[uuid-utils 元数据](https://pypi.org/pypi/uuid-utils/0.12.0/json)

## 3. 下一步最小任务和停止条件

本文件允许直接继续的范围仍是 **只读证据、公开小体积元数据、文档**。二进制下载和升级实验不在本轮；先提交精确下载单给 Owner。不开卡片；若范围／目标需裁定，用简短文字说明推荐项及代价。

1. **C1 信任门禁与空 fix 裁定证据。** 逐条核对 ST／TF 的公告、标签源码和项目调用面，区分未触达、受限制、已修复、未定；重复 ID 的不同 fix 记录保留。不凭公告版本数字接受本地自定义代码。找到可证明的精确版本才进入下一步；否则登记未关闭，停止此案安装准备。
2. **C2 模型链声明闭包。** 确定 hub 精确版本和必要传递包，检查撤回、Python／平台 wheel；CPU torch 单独核对上游公告和实际暴露面，扫描器跳过要保持可见。只启用项目必要默认依赖，不启用训练／all／dev extras，不因形式兼容调查无关 CUDA 包。不能将 CPU 等同风险豁免。
3. **D1 Chroma 和适配层一致集合。** 先核对 Chroma 精确目标的通报／发行记录与官方迁移说明，明确现有公开库是否能复制升级、恢复后重新打开；再确定最小 core／拆分包／SDK 集合及默认传递依赖。不要将 `langchain-chroma` 版本当成 `chromadb` 版本；不启用 Chroma 服务、多租户或远程配置。
4. **下载门。** C／D 分别交付精确包名、版本、官方 wheel URL、公告 size／SHA、Python／平台标签、下载总量、缺项与预期增量；不得留区间或让助手自行追 latest。只有 Owner 批准指定单后才能下载。元数据中 SHA 是公告值，下载后必须计算文件 SHA 比对；不取 sdist、不源码构建、不下载新模型权重。
5. **后续实验门（未执行）。** 下载与安装获准后，各案另建仓外源码／venv／公开库副本。C、D 先分案测，再在都成立时联合；绝不在已验旧环境升级。每个命令记录真实时间、退出码和新日志，失败先定位，完全相同命令最多重试一次，同一 bug 三次修复仍不过就停。

若 Chroma 没有可核查修复版或 ST 没有信任门禁修复证据，不无限换版本试绿；写清剩余风险和隔离措施，提交 Owner 决策。**风险接受是业务裁定，不是技术“已修复”。**

## 4. 后续实验的最低验收，不在本轮冒充完成

- 先冻结精确包集合、源码和测试集合；安装实物逐 SHA 复核，`pip check`、实际安装增量、逐条实装安全审计可追溯。不以 PyPI 页面 `vulnerabilities=[]` 代替审计；CPU torch 未覆盖须独立补证或明确未关闭。
- C：信任开关的无害否定测试先证明未知自定义代码未执行；既有固定 BGE revision 只读缓存、禁网 CPU 加载。官方来源若仍 PARTIAL，不声称已补齐；依赖测试不得接收未知模型代码。模型完整性或信任条件不成立时停止加载，不开启 `trust_remote_code=True` 凑过关。
- 只用 1528 条已批准公开法规副本、QA=0；新进程复开，逐条核对 ID／正文／metadata 和向量输入指纹。索引读回绝对差≤`1e-6`、余弦误差≤`1e-10`；BGE 每部法规原固定两条、共八条重算，逐条余弦≥`0.99999`。样本／阈值沿用[原空间验收 §4](C:/Users/33393/Desktop/ai-legal-helper/docs/work-report-20261002-rerank-acceptance.md:45)，不是本轮实测。768 维不代替空间一致；失败提出隔离索引重建分案，不覆盖原库。
- D：保持 Document、消息、ChatOpenAI、embedding／检索接口；核对 SDK 1→2 的流式输出、token 用量、异常映射和缓存路径。测试先用离线替身，不能将其记成真实模型验收。Chroma 迁移前保留未迁移公开副本；旧版本打开该独立副本验证回退，不降级打开已迁移目录、不只看数量一致。法规切分与原检索题集／判据不缩水。
- 定向、原非 slow nodeid 集合、完整非 slow 回归、公开库离线烟测和静态检查沿用现有入口；不删测试、不放宽阈值、不换 pytest／golden 凑通过。发生实质变更才重跑对应门禁，而不是重复本轮未变的旧联合候选。
- 前后指纹保护旧 source／venv／evidence、原库、`.env`、默认模型缓存、HEAD／refs 与他人并行工作；不输出凭据。真实 rerank／生成请求、真实库写入、提交／合入／push／PR、Linux CI 或部署均不自动授权。应用启动／浏览器端到端仍是另项待办，不能被依赖审计或旧 smoke 代替。

## 5. 本轮证据、失败与自审

主审只读元数据根：`C:/Users/33393/Desktop/fazhi-dependency-preflight-20261004-7264fb73e5e34d89b790cd77b10e6d73`。`metadata-records.json` 记录 00:05:20–00:05:22+08 的六次请求，`pinned-metadata-records.json` 记录 00:09:22–00:09:28+08 的七次请求；13 份原始 PyPI JSON 各有实际 size／SHA／取得时间，含两个 latest 发现响应，后续目标均另查精确版本。请求只取公开 JSON，不携带凭据、不走代理、不取包二进制。

00:21:35+08 离线运行 `verify_metadata.py`：13 份原始响应的 bytes／SHA／版本／默认 Requires-Dist 均相符，Python 3.11 和 wheel 标签匹配、已查 wheel 未撤回；同时比对冻结实装和当前默认直接声明。结果见 [metadata-verification.json](C:/Users/33393/Desktop/fazhi-dependency-preflight-20261004-7264fb73e5e34d89b790cd77b10e6d73/metadata-verification.json)。复核命令：

```powershell
& 'C:/Users/33393/Desktop/fazhi-joint-candidate-20261003-ac701f4a880441b5a453b1b7cbb06f01/venv/Scripts/python.exe' -I -B 'C:/Users/33393/Desktop/fazhi-dependency-preflight-20261004-7264fb73e5e34d89b790cd77b10e6d73/verify_metadata.py'
```

脚本以独占新建保存结果，原文件已存在时应改为新的结果名再复核，**不要覆盖历史 JSON**。此成功只证明元数据保存一致与直接声明／标签检查，**未运行解析器、未安装、未扫描新环境、未证明完整兼容或安全**。旧联合门禁本轮没有重跑。

失败保留：首次读取 PyPI JSON 用默认 GBK 遇到 UnicodeDecodeError，改用 UTF-8 读取已有快照，没有重复联网；见 `metadata-inspection-failure.json`。另一次证据定位命令误读不存在的 `installed-metadata.json`，仅文件定位失败；随后找到真正的 `environment-verification.json`，没有补造不存在的证据。

自审按 Ponytail 保留原架构与必要功能，按 vet-plan 明确 C／D 的真实依赖边界，按证据门禁不把声明兼容、fix 数字、空漏洞列表或旧测试结果当作本轮安全通过。最终文档／保护复核记录将在本根另存；不回填旧交付 manifest。
