# 依赖风险最小处理分案（2026-10-03）

> **2026-10-04 更新：下面 A／B 未执行、167 实装和模型候选等描述是起草时快照，不再作为当前待办。** A、B 单项与新的 A＋B 联合验证均已完成；联合根实装 162 分发，正式采纳 B／新对象 D2 仍待 Owner，10月5日复审不顺延。C／D 下一步以 [剩余依赖预检与执行边界](C:/Users/33393/Desktop/ai-legal-helper/docs/process-archive/superpowers/plans/2026-10-04-remaining-dependency-preflight.md) 为准：TF 5.10.0 已撤回，禁止按下文调查线索下载；ST 5.6.0 的信任门禁未被源码证明关闭；langsmith 还须纳入 0.8.18 修复线。已查新 core 兼容的 Chroma 适配选项均联动 Chroma 本体升级，不能单换 core。保留以下原时点证据，不要求重跑旧联合门禁。实际完成记录见 [联合报告](C:/Users/33393/Desktop/ai-legal-helper/docs/work-report-20261003-joint-candidate.md)。

## 结论与执行边界

建议顺序：**A 验证精简闲置依赖 → B 独立升级 setuptools → C 模型依赖联合验证 → D LangChain 适配与 Chroma 分开处理**。模型来源查询可独立推进，连接失败不阻塞 A／B 的离线准备。

本文件交付的是已有证据、精确拟改项和验收条件。当前候选及167个实装分发未改；风险接受未签。现有已验候选根为 `C:/Users/33393/Desktop/fazhi-local-candidate-20261002-67944caf51ff48ce9432831cdd62f72b`，四文件增量／主线902e2d1保持。以下新增依赖变更须在另建实验环境验证，不能直接对该已验venv执行卸载或升级。下载仍沿用“精确清单交Owner”的边界；不自行拉大模型、CUDA或镜像。

## 本轮实际证据

证据文件均在候选根的 `evidence`。

- `dependency-followup-20261003.json`：解析候选后端268个Python文件的AST，并读取当前安装包的默认extras依赖关系；不导入应用、不改包。
- 没有找到 `langchain` 或 `langchain_community` 的直接import；`langchain_text_splitters`在`backend/chunking.py:19`和`scripts/eval_chunking.py:20`直接使用。
- 已安装包中，没有其他包以当前生效的默认依赖要求`langchain`；`langchain-community`只被`langchain`要求。元数据分析不覆盖所有可选extras和用户外部脚本。
- 两个动态导入位置已人工核对：`docx_utils.py:49`导入`io`；`scripts/eval_agent.py:349`由`--adapter MODULE:CALLABLE`指定。后者意味着不能推断所有外部评测adapter都不依赖这两个包，删除前应核对实际使用的adapter清单。
- `dependency-removal-probe-20261003.json`：模拟三个模块不可导入，阳性控制成立。条文切分、消息构造、ChatOpenAI离线构造、jieba字典回退读取四项均成立；但记录一次被守卫拒绝的`socket.bind`，**整体rc=1／passed=false**。没有实际删包，也不能将四项局部结果写成卸载验收通过。首次只有AssertionError输出；加上分项诊断后定位到该被拦截事件，未继续反复运行。

## A. 验证移除总包和 community，保留实际使用的拆分包

拟改仅为实验副本 `backend/requirements.txt` 的以下三行；FastAPI、pypdf和其他既有候选改动保留：

```diff
-langchain>=0.1,<0.2
-langchain-community>=0.0.38,<0.1
+langchain-text-splitters>=0.0.2,<0.1
```

这是基于当前0.0.2实装的保守约束，不表示该版本没有通报。必须显式声明text-splitters，因为目前它由将被去掉的总包间接带入；不能靠旧venv残留维持绿灯。不要同时删除core、openai、chroma、huggingface适配包、langsmith或其他传递包。

实际执行顺序：

1. 为上述`socket.bind`记录不含参数／凭据的调用栈，判断是否是本地事件循环初始化。仅在确认为所需本地行为后缩小网络守卫；仍禁止外部connect／DNS、子进程安装和真实模型调用。不得直接删掉守卫来凑通过。
2. 核对真实使用的`--adapter`入口、CI、运维脚本和外部评测使用方式。AST零引用是线索，不是全局未使用证明。
3. 从既有精确缓存建立新隔离环境，仅删除两个目标包的声明／约束，新增text-splitters直接声明。离线解析；缺包列清单，不在线补齐。不要在旧venv里卸载后测试。
4. 验收安装清单中两个包确实不存在、`pip check`通过；原非slow nodeid集合不得丢失。跑原定向和完整非slow测试／守卫，使用独立数据库和公开库；禁止用删测试、降pytest版本或更改引用判据过关。
5. 重扫新环境并与原始ID逐项对比。旧审计中两个包合计15条原始通报，仅说明可能减小依赖面，**不是已经修复15个独立漏洞**；不能凭减法宣称剩余安全。

本分案完成条件：干净环境无两个包、依赖声明自洽、原回归无退化、更新审计原始JSON及精确增量。失败时保留新环境／日志，原候选仍可用。

## B. setuptools 单独升级

旧审计列出的最高修复版本为83.0.0。已通过[官方PyPI元数据](https://pypi.org/pypi/setuptools/83.0.0/json)核实该版本存在、未撤回、要求Python>=3.10；本地Python3.11满足该声明。该页面返回的漏洞列表为空，只是页面快照，不替代升级后审计。

供后续下载助手使用的精确候选，**本轮未下载／安装**：

- 文件：`setuptools-83.0.0-py3-none-any.whl`
- 大小：`1008090`字节。
- SHA-256：`29b23c360f22f414dc7336bb39178cc7bcbf6021ed2733cde173f09dba19abb3`。
- [官方wheel地址](https://files.pythonhosted.org/packages/5d/40/e1e72872c6354b306daef1703549e8e83b4d43cfea356311bf722a043752/setuptools-83.0.0-py3-none-any.whl)。只取wheel，不取sdist、不执行源码构建。
- 已检查既有 `C:/Users/33393/AppData/Local/Temp/legal-closeout-20260928/wheelhouse`，其中没有setuptools wheel；这不是全磁盘缓存搜索结论。

[Setuptools官方变更记录](https://setuptools.pypa.io/en/stable/history.html)说明新版已移除`pkg_resources`。当前jieba `_compat.py`会尝试使用它，缺失时回退到本地文件读取；本轮回退读取分项成立，整体探针仍因绑定守卫失败。不能只凭“无反向依赖”就判无运行风险。

在独立环境只变setuptools，先查其他实际使用包的`pkg_resources`路径，验证jieba资源读取／分词、安装元数据读取、应用导入，再跑对应回归与新审计。若目标版本另有新通报，重新选版；不要为兼容盲目降回旧漏洞版本。A与B分开记录，不混成一次难以归因的失败。

## C. 模型来源与模型依赖联合验证

来源：本次官方精确revision树页面可访问，能确认目录存在和文件列表；API树查询和权重指针页面不可用，本机curl连接8秒超时、退出28、未创建输出文件。没有下载权重或写模型缓存。不能用页面标记“Safe”、文件名／大小相同或当前main指针代替精确revision逐文件核验。[精确revision目录](https://huggingface.co/BAAI/bge-base-zh-v1.5/tree/f03589ceff5aac7111bd60cfc7d497ca17ecac65)

来源状态保持PARTIAL。后续只获取精确revision的Git blob ID／LFS SHA等小体积元数据，与现有文件的相应Git blob哈希／SHA-256逐项比较；不要直接下载409MB权重来解决元数据连接问题，也不要悄悄把缓存`refs/main`切到另一revision。当前需完整核验默认snapshot的11个本地文件；另一个snapshot只有safetensors，不是当前默认运行集合。

当前ST2.7.0要求`transformers>=4.34,<5`，而旧审计多个Transformers修复版本落在5.x。**只升级Transformers不可行**，需ST／Transformers／CPU torch一起做精确版本和兼容性预检。旧审计ST修复候选5.6.0、Transformers候选5.10.0仅作调查线索，尚未核对整组元数据与可用wheel，不能当成可直接安装的锁文件。

验收至少包括：声明可解析、pip check、官方模型字节来源、CPU加载、维度一致、既有八条嵌入空间抽核与原数值阈值、同一1528条公开法规检索回归。**768维相同不证明新旧向量空间相同**；如不兼容，先提出重建隔离索引分案，不覆盖原库。现有真实rerank许可已耗用，离线验证不自动增加真实请求。

## D. 活跃LangChain适配层与Chroma

当前core修复需要跨现有上界；已安装openai、huggingface、text-splitters等适配包对core有各自上界，不能只强装新core再用`--no-deps`绕过冲突。联合选出最小一致集合，保留现有Document／消息／ChatOpenAI／embedding接口和功能，不引入新agent框架或重写RAG。验收覆盖流式输出、token用量解析、缓存与检索、错误路径、全套回归。

Chroma0.4.24两条旧通报未给fix_versions；“空列表”不是永久无修复结论。先逐条读取上游公告与当前接口使用范围，再定是否升级。若升级涉及持久格式，先在可恢复公开副本验证恢复、记录数量、全文／metadata／向量与查询结果；不修改真实库。分案不扩成Chroma服务化迁移。

## 自审与交接

已按Ponytail比较“删未用依赖”和“整栈大升级”，优先前者但保留动态入口／干净安装验证；按vet-plan-new明确每案对象、最小改动和可测退出条件。没有以静态零引用、4个局部分项通过或官方文件存在冒充安全验收。

本轮没有实施A–D依赖变更，没有完成D2签署、应用完整启动、Linux／远端CI或发布。旧86文件交付集合仍是上一检查点，本文件和新增诊断不在该集合中；不要修改其旧manifest来冒充已纳入。当前工作入口以主仓最新报告§13和本文件为准。
