# 依赖风险执行报告：删包实验、setuptools、模型来源（2026-10-03）

执行入口：[执行书](C:/Users/33393/Desktop/ai-legal-helper/docs/process-archive/superpowers/plans/2026-10-03-next-local-candidate-execution.md)。本文件为本轮正式技术报告，另有 Owner 汇总；旧10月2日报告保持原时点，不覆盖失败记录。执行书在后续审核中补充了自包含指令与续办状态，不能把修订后的文本当成原执行时版本。

**一句话结论：A 删包实验在仓外干净环境全绿通过（限定仓内受控路径，不声称对外部 adapter 兼容）且 Owner 已采纳；B setuptools 升级初因缺 wheel 阻塞，Owner 批准单项下载后已续办执行并通过（见 §8）；C 模型来源仍 PARTIAL（本地稳定性已证，官方精确 revision 元数据不可达）；D 材料与交付集合就绪，D2 裁定仍留待 Owner，复审 2026-10-05 未延长。**

主仓基线 `902e2d161e67100ed6d267a08c393538a0abe109` 未改；未提交／合入／push／建PR／写原库／部署；真实 rerank／生成 API 调用 0（第四轮标记保留，10月2日7次200许可仍属已耗用状态）。本轮全部实际改动只在仓外新实验区：

- **运行根：`C:/Users/33393/Desktop/fazhi-risk-followup-75542ea22e9b4627a4e090cbc5c7f9aa`**（本轮新建，现含 `experiment-a`、`experiment-b`、`evidence`、`owner-wheels` 与交付集合；B 曾缺 wheel，随后已续办，见§8）。
- 已验候选根 `fazhi-local-candidate-20261002-67944caf…` 三处（source／venv／evidence）未改写，仅只读使用；主仓新增本报告。

## 1. 已完成（逐条证据路径；退出码与时间戳的记录边界见 §7 更正）

证据路径均相对运行根 `evidence`（标注"experiment-a/evidence"的在实验目录内）。

### 1.1 A1 基线与已验证源码复制

- 主仓保护复核 **passed=True**：41 保护对象、原 Chroma 38 文件整集合（path/bytes/sha256）、backend/.env 整文件 SHA、HEAD／refs、原脏文档 `2026-09-29-…md` SHA、跟踪代码状态全部不变。证据：`a1-baseline-protection.json`、`a1-original-corpus-after.json`。
- 已验候选源码 manifest 2658 文件 **逐文件 SHA 复核 0 漂移**；随后复制到 `experiment-a/source`：2658 文件、**0 缺失、0 多余、0 hash 不符**。证据：`a1-baseline.json`、`a1-copy-verification.json`。注：a1-baseline 初次运行的 extras 统计为脚本路径分隔符 bug，仅影响该统计项，逐文件 hash 核验始终通过，修正记录见 a1-copy-verification.json；运行日志 `a1-baseline-run.log` 保留全过程。
- 旧 venv 167 分发清单只读导出：`a1-old-venv-freeze.txt`。requirements／constraints 指纹：`BC54A2EB…69DEA`／`07311CF5…8C292`（见 a1-baseline.json）。

### 1.2 A2 探针 socket.bind 定位（脱敏）

- 第一次诊断**保持拒绝**：四项功能检查全 true、1 次 bind 被拦、0 次 connect／DNS／subprocess；脱敏栈（仅文件名/函数名/行号）证明被拦 bind 来自 **urllib3 导入期 IPv6 能力探测**（`urllib3/util/connection.py:137` `HAS_IPV6 = _has_ipv6("::1")` → line 127 `sock.bind((host, 0))`），绑定 `::1` 端口 0 后立即关闭，**不是应用或第三方开放监听**。只读 grep 旧 venv 证实该代码。证据：`experiment-a/evidence/diagnose-bind-result.json`、`bind-callstack.json`、结论 `experiment-a/evidence/a2-bind-diagnosis.md`。
- 按执行书授权的**严格回环放行**复跑：仅当 `ipaddress.ip_address(host).is_loopback` 内存核验通过才放行（地址/端口不落日志，只记布尔），1 次放行 bind 的 all_hosts_parsed／all_hosts_loopback／all_ports_zero 全 true，四项检查全 true，退出 0。证据：`diagnose-bind-loopback-result.json`、`bind-callstack-loopback.json`。
- 原失败 JSON `dependency-removal-probe-20261003.json` 未改动；诊断被拦是预期结果，不计修复失败。

### 1.3 A3 引用核对与删包边界

- 仓内业务代码／脚本／测试／CI（`.github/workflows/ci.yml`）／`evals/`／守卫目录：对 `langchain`／`langchain_community` 的直接与字符串动态加载 **0 处**；命中全为注释／docstring／审计处置数据。证据：`experiment-a/evidence/a3-reference-check.md`。
- `--adapter MODULE:CALLABLE` 外部入口无法从仓内取得实际使用清单（文档均为占位）→ **A 结论限定为仓内受控路径实验，不声称对所有外部 adapter 兼容**；未来外部 adapter 若依赖两包，将以可观察的 `ModuleNotFoundError` 失败。

### 1.4 A4 独立环境与离线安装（每条命令独立日志＋退出码）

- `pip==26.2.1`、`torch==2.6.0+cpu`、`requirements-dev.txt` 三段安装 **全部退出 0**（仅用四个既有只读缓存目录 + `--no-index`；未运行旧 install-candidate.ps1；未联网装包）。证据：`experiment-a/evidence/a4-venv-create.log`、`a4-pip-upgrade.log`、`a4-torch-install.log`、`a4-requirements-install.log`。
- 实验改动仅两文件且已复核 diff：`experiment-a/source/backend/requirements.txt`（执行书三行 diff，删除两包、新增 `langchain-text-splitters>=0.0.2,<0.1` 直接声明）与 `experiment-a/candidate-constraints.txt`（仅删 `langchain==0.1.20`、`langchain-community==0.0.38` 两行，其余 165 行含 `langchain-text-splitters==0.0.2` 不变）。源码相对已验候选 **精确差异=1 文件**（backend/requirements.txt）。

### 1.5 A5 实验验收（全绿）

- `pip check` 退出 0（`a5-pip-check.log`）；实装 162 分发（`a5-installed-freeze.txt`）：**langchain、langchain-community 确实不存在**，`langchain-text-splitters==0.0.2` 存在且满足直接声明；版本对照旧环境 **0 版本变化、0 新增**，仅随闭包收缩少装 5 个（两目标包＋`dataclasses-json`／`marshmallow`／`typing-inspect`，后者经元数据核实仅被两目标包及 dataclasses-json 依赖链需要；fastapi/pydantic 需要的是不同包 `typing-inspection`，仍在装）。
- 收集 `1690/1708（18 deselected）`，nodeid 集合与旧 `pdf619-collect-final.log` 逐条比对 **0 消失、0 新增**（`a5-collect.log`）。
- 定向三文件 **27 passed**（`a5-targeted.log`）；Ruff check／format **退出 0**（`a5-ruff-check.log`／`a5-ruff-format.log`）；mypy **74 文件 0 错误**（`a5-mypy.log`）。
- 全量非slow **1680 passed／10 skipped／18 deselected，覆盖率 85.42%（--cov-fail-under=70），退出 0**（`a5-full.log`）；测试隔离环境与旧候选同形状（独立 runtime／空库／本地 embedding／rerank 关闭／离线开关／fixture JWT／真实 key 与代理清空；未 dot-source 旧 environment.ps1）。
- 公开库烟测：旧候选 `public-kb` 指纹核验后复制到实验 runtime（6 文件，`a5-public-copy-before-open.json`），`smoke_citation_fast.py` **24/24 通过、退出 0**（`a5-smoke-citation-fast.log`），烟测后旧库指纹复核**不变**（`a5-public-original-after-smoke.json`）；随后测试路径恢复空库。
- 已知 conftest 副作用按 10-02 报告 §9.3 同例处置：源码默认位置出现 `backend/chroma_db/chroma.sqlite3`（1 空集合、0 文档/元数据/队列），只读验证后**移入** `experiment-a/runtime/isolated-conftest-kb`（移动前后 SHA 相同），未删除未覆盖（`a5-stray-chroma-isolation.json`）。源码树其余多余文件仅为 mypy/pytest/ruff 工具缓存。

### 1.6 A6 新实装审计（对象正确）

- 新 venv 实装审计退出 1（有通报，预期红）、原始 JSON `experiment-a/evidence/a6-installed-audit.json`、命令记录 `a6-audit-command.json`：**42 原始行／8 包／25 全局别名组**（与旧"57 行／10 包／32 组"同法重算可比，重算核对见 `a6-audit-summary.json`）。
- 两目标包的 15 条原始通报随包不再安装而消失；其中 **14 条原始记录的 ID／别名不再被其他在装包命中，1 条（PYSEC-2026-2555／CVE-2026-45134／GHSA-3644-q5cj-c5c7）仍由 `langsmith 0.1.147` 命中（修复版 0.8.0）**。这些记录含别名重复，不能解释成移除了14个独立漏洞；全局别名组实际从32减到25，即减少7组。无新增 ID。**不是"修复了漏洞"**：两包从未修复，是不再安装；剩余通报面（chromadb 2、langchain-core 11、langchain-openai 2、text-splitters 4、langsmith 5、ST 1、setuptools 8、transformers 9）原样保留。
- `torch==2.6.0+cpu` 仍被扫描器跳过（审计输出中 version=None、0 通报），单列为审计限制；上游精确查询仍属 10-02 旧数据。

### 1.7 C 本地半程与一次联网尝试

- 本地核验：缓存 `refs/main=f03589ceff5aac7111bd60cfc7d497ca17ecac65` 未变；默认 snapshot 恰 11 文件，**全部与 10-02 记录 SHA 逐一相符**。证据：`c-cache-verify.json`。这只证明本地稳定，不是官方绑定。
- 本轮联网尝试按执行记录仅一次（python urllib 20 秒，方法与 10-03 00:41 的 curl 8 秒失败不同）请求官方 revision tree API：**URLError（WinError 10061 连接被拒）**，按执行书停止联网尝试。证据：`c-metadata-attempt.json`。
- 结论：**模型来源保持 PARTIAL**，缺项见 §3；未改 refs、未替换模型、未加载未核验文件、未下载权重、未重建索引、0 云端调用。

## 2. 失败／阻塞（不与通过项抵销）

- **B：BLOCKED-DOWNLOAD（批准前时点记录，已由 §8 续办取代）。** 按执行书先查本机缓存：wheelhouse、候选三缓存目录、pip HTTP 缓存及有界扩展搜索均无任何 setuptools wheel（更非全磁盘结论）。未自行下载、未联网。**experiment-b 当时未创建**（避免无 wheel 的半成品环境）；下载单已交 Owner：精确文件名/大小 1008090 字节/SHA-256 `29b23c36…19abb3`/官方 URL/元数据 URL 见 `b1-setuptools-download-order.json`。独立审查代理经官方 PyPI 元数据在线复核：该 wheel 存在、未撤回、大小与 SHA-256 与下载单一致。Owner 于同日批准下载后已续办执行并通过，见 §8。
- **C 联网失败**（见 §1.7）：保留 PARTIAL，不重试、不换镜像。

## 3. 原单项执行时点未验（后续联合结果见§10）

- B 的早期“全部未执行”已被§8续办结果取代。当前仍未验：任意第三方工具／外部 adapter 的所有 `pkg_resources` 条件分支、sdist 构建、Linux 环境；不能以应用回归通过宣称第三方所有分支都被执行。
- **原单项执行时A＋B 联合候选未创建／未验收；随后独立续办已完成，见§10。** 两个独立单因素结果不能拼成一个新实装环境的审计／验收结果；正式采纳与主线整合仍按审批边界另行进行。
- A 不声称：所有外部 `--adapter` 兼容；真实 rerank／生成质量；Linux／远端 CI；完整应用启动与浏览器；生产配额逻辑。旧"新环境已验真实 rerank"说法仍不成立——10月2日 7 次 200 只绑定当时环境。
- C 仍缺：10 个小文件（`1_Pooling/config.json`、`config.json`、`config_sentence_transformers.json`、`modules.json`、`README.md`、`sentence_bert_config.json`、`special_tokens_map.json`、`tokenizer.json`、`tokenizer_config.json`、`vocab.txt`）绑定到**精确 revision** 的官方 Git blob OID；`pytorch_model.bin` 的**精确 revision** LFS OID（现仅有 10-02 记录的 current-main 指针对照）。独立依据：官方 tree/raw 端点本机两法均不可达（`c-metadata-attempt.json`）。
- 来源即使补齐也不关闭 Torch／ST／Transformers 依赖通报；两事分开评估。

## 4. Owner 待裁

- **D2／Windows 有限用途接受**：仍待签，复审 **2026-10-05 不延长**；本轮不代签、不顺延。裁定材料仍为 [local-candidate-decision-20261003.md](C:/Users/33393/Desktop/ai-legal-helper/docs/local-candidate-decision-20261003.md)，本轮结果可作补充输入。
- ~~**setuptools 83.0.0 wheel 单项下载**是否批准（`b1-setuptools-download-order.json`）~~：**Owner 已批准（"批准"），已按下载单执行并通过，见 §8。**
- ~~**删包是否采纳**为候选变更~~：**Owner 已采纳（"采纳"）**。候选四文件增量中的 `backend/requirements.txt` 内容按实验 A 版为既定方向；冻结候选根三处不就地改写，实际整合按裁定材料既定顺序另行进行（本地候选正式接受后再准备提交／合入审阅），见 §8。
- **逐包下一步**（不含 A／B 的依赖变化）：
  - 模型链：ST 2.7.0 声明 `transformers<5`，Transformers 多条修复落在 5.x → 必须做 ST／Transformers／CPU torch 整组精确版本与 wheel 可得性预检，不能只强装 Transformers 5；来源 PARTIAL 与依赖通报分开处理。
  - LangChain core／适配包：core 修复跨现有 `<0.2` 上界，openai/huggingface/chroma/text-splitters 各有上界 → 需最小一致集合联合选版，覆盖流式/用量/缓存/错误路径回归；`langsmith` 另按 0.8.0 修复线单独评估（本轮实证其仍命中 CVE-2026-45134 组）。
  - Chroma 0.4.24 两条旧通报 fix 列表为空 → 先读上游公告与当前接口使用面再定，"空列表"不当作永久无修复；若涉持久格式先在可恢复公开副本验证，不直接换格式。

## 5. 交付集合与卫生扫描

- 新集合：运行根下 **`delivery-risk-followup-20261003/`**，仅含拟交付补丁（三行 diff）、声明／安装记录（实验 requirements／constraints 副本、安装日志、新旧分发清单）、脱敏日志（A2/A3/A5）、风险原始 JSON（a1 保护与基线、a6 审计、b1 下载单、c 来源）、本报告副本与独立 manifest。
- 9 字段完整内存值／形状扫描：8 个 `.env` census 值 + Windows 机器级 `RERANK_API_KEY`，值扫描命中 0、形状扫描命中 0，**正控（值与形状）命中**，禁止文件 0。40／41文件扫描是早期时点，随后B材料和汇总加入；审核时 manifest 有**71条内容记录**，目录实际有**73文件**：71个列入对象＋manifest自身＋manifest生成后写入的 `delivery-hygiene-20261003-final2.json`。后者报告扫描72个先存对象，不包含自身；审核者另对实际73个文件复扫，结果见§9。旧72／86文件薄包不覆盖，不纳入272MB基线、`.env`、数据库、权重或旧受限快照。文件卫生只证明所选集合，不是全Git历史或发布许可；目录中的报告副本保留原执行时点，不冒充本次审核后的主仓文档。

## 6. 验后保护复核

- 交付前复核 **passed=True**（`evidence/d1-protection-predelivery.json`）：41 对象、38 文件原 Chroma、`.env`、HEAD/refs、原脏文档、跟踪代码全部不变。
- 交付后终复核 **passed=True**（`evidence/d1-protection-postdelivery.json`，报告与交付集合均不触碰受检对象；HEAD／refs／脏文档 SHA 不变）。
- 实验副本相对已验候选的精确差异：**源码 1 文件**（backend/requirements.txt）＋运行根内 constraints 副本 2 行删除；其余 2657 文件逐字节一致。

## 7. 独立审查与证据卫生更正（2026-10-03）

独立审查代理（只读、独立重算）复核本轮全部关键论断并成立：候选源码 2658 文件逐 hash 走查 0 漂移；实验副本精确差异 1 文件；freeze 差异恰为声明的 5 个删除、0 版本变化；新旧 nodeid 集合逐条比对一致；审计按同法重归并 42/8/25 对 57/10/32，langsmith 例外单列正确；交付集合 manifest 40/40 hash 核对相符；HF 缓存 11 文件独立重 hash 相符；git 状态、.env、原库不变；B 下载单经 PyPI 在线核实。以下为证据卫生缺陷的显式更正，不改变实质结论：

- **[更正] 退出码记录边界**：原A4/A5及后续 showwork 日志无逐命令持久化退出码JSON；B2的五项创建／安装和B3审计有显式记录，B3其他验收仅日志与汇总字段，没有逐项命令JSON。结果文件的 `passed` 布尔也不能替代真实退出码。原日志支持其结果，但不能反向补写历史退出码；本次审核另建新副本重跑，逐命令记录新执行的时间与退出码，见§9。
- **[披露] 时间戳**：六个JSON（`a6-audit-summary`、`b1-setuptools-download-order`、`delivery-hygiene-20261003`、`delivery-hygiene-20261003-final`、`delivery-manifest-20261003`、`a1-baseline`）内嵌时间为手工近似值。mtime只说明最后写入时间，可能因复制／编辑变化，**不能用它恢复精确执行时间或证明操作顺序**；这些项的准确历史时刻未获独立证实。原文件保留，不伪造精确时间；hash／计数另行重算。
- **[披露] a1-baseline.json**：初跑 extras 统计 bug 后曾就地更正该汇总 JSON（原值保留于 `evidence/a1-baseline-run.log`；独立复核件 `evidence/a1-copy-verification.json`；审查代理 2658 文件走查独立确认复制正确）。此做法不合"失败文件不覆写"精神，记录在此。
- **[披露] 行尾**：`experiment-a/candidate-constraints.txt` 为统一 CRLF，与原候选混排行尾在字节级不同但内容逐行一致；源码 requirements 差异不受影响。
## 8. Owner 裁定与 B 续办结果（2026-10-03）

Owner 对本轮三项待裁事项回复"**批准，采纳**"：批准 setuptools 83.0.0 wheel 单项下载、采纳删包为候选变更方向；**未提及 D2／Windows 用途签署，其仍待裁，复审 2026-10-05 不延长**。

### 8.1 裁定记录

| 事项 | Owner 回复 | 执行 |
|---|---|---|
| setuptools wheel 单项下载（`b1-setuptools-download-order.json`） | 批准 | 当日按下载单执行：官方 PyPI 元数据核验（83.0.0、未撤回、requires_python>=3.10）后单项下载，大小 1008090 与 SHA-256 双重相符，落运行根 `owner-wheels/`（`experiment-b` 同级）。记录：运行根 `evidence/b1b-download-record.json` |
| 删包采纳为候选变更 | 采纳 | 记录为既定方向；冻结候选根不就地改写，整合按裁定材料既定顺序另行进行 |
| D2／Windows 有限用途签署 | 未提及 | 仍待裁，未代签、未顺延 |

### 8.2 B 续办执行（单因素：仅 setuptools 65.5.0 → 83.0.0）

- **安装**：新建 `experiment-b`（2658 文件逐 hash 复制，`evidence/b2-copy-verification.json`）；约束仅将 `setuptools==65.5.0` 换为 `setuptools==83.0.0`（其余 166 行不变，LangChain 按单因素要求保留）；venv 五段安装（pip→83.0.0 wheel 显式安装→torch→requirements-dev）**逐命令退出码记录全 0**（`evidence/b2-cmd-*.json`），`pip show setuptools` = 83.0.0。
- **pkg_resources 缺失面**（`experiment-b/evidence/b3-pkg-resources-check.json`）：`import pkg_resources` 阳性缺失成立；**jieba 0.42.1 实测导入、中文分词（"中华人民共和国劳动合同法第十九条"）、`dict.txt` 字典回退读取全部成功**。原静态扫描是10个顶层位置的字符串命中，不是10个分发存在实际导入。审核用AST核对命中文件：真正裸导入见于pytest的条件分支、jieba的try/fallback、onnxruntime两份可选benchmark脚本；numpy/scipy/sklearn的相关命中是注释。全量套件通过不证明所有这些第三方分支都已触达。安装元数据读取有 `pip check`／`pip show`／pip-audit 证据；sdist与可选benchmark等仍不属于本轮验收。
- **验收**（与 A 同形状，B 自己的 runtime／空库／公开库副本）：pip check=0；collect 1690/1708；定向 27 通过；Ruff check／format=0；mypy 74 文件 0；**全量非 slow 1680 passed／10 skipped／18 deselected，85.42%，退出 0**；公开库烟测 **24/24**，原公开库指纹不变。
- **freeze 差异**：167→167，**恰好一处** `setuptools 65.5.0 → 83.0.0`（显式 URL 安装、SHA 已验）。
- **新实装审计**（`experiment-b/evidence/b3-installed-audit.json`，退出 1 预期红）：49行／9包／28全局别名组；**setuptools 83.0.0 自身0通报**，65.5.0时代的8行归为4个别名组，全部消失、无新增；langchain两包的15行按单因素设计仍在B环境，A实验结果不能关闭B中的通报。审计为时点快照，无通报不等于零未知风险。

**B 完成标准核对：只有 setuptools 实装版本变化（freeze 恰一处）＋验收与新审计同源＋受影响功能与全量非 slow 通过 → B 通过。** B 的采纳（是否把 setuptools==83.0.0 写入候选约束）为新的独立裁定事项，本报告不代决。conftest 副作用同例隔离（`experiment-b/evidence/b3-stray-chroma-isolation.json`）。

## 9. 后续独立审核（2026-10-03）

审核根：`C:/Users/33393/Desktop/fazhi-risk-review-20261003-e30b720af8364e4c83ded98210868f7b`。原助手运行根与旧候选不覆写；审核用新source／runtime副本、原A／B独立venv只读运行，保留新的日志和逐命令记录。

- `independent-evidence-review.json`：旧源码2658对象无漂移，A只变requirements，B源码无变化；A实装仅少5包，B仅setuptools换版；原A／B nodeid都与1690基线相同。原审计重算为57／10／32、42／8／25、49／9／28（原始行／包／全局组）。这是旧快照重算，不是新公告扫描。
- `a-*-command.json`、`b-*-command.json`：每侧pip check、collect、Ruff check／format、mypy、全量非slow、公开副本烟测，共14条新命令。真实退出码全0；两侧各1680通过／10跳过／18不选、覆盖率85.42%、烟测24/24。数据库、临时文件、覆盖率与工具缓存放各侧独立runtime；不借原执行的口头退出码。
- `independent-pkg-resources-review.json`：AST剔除注释／字符串误报，实际验证pkg_resources缺失、jieba的分词结果与字典读取；不承诺可选benchmark／第三方所有条件分支。
- 交付71条内容记录的bytes／SHA相符，实际73文件另扫，9字段输入完整、正控成立、值与形状均0命中；原报告副本保留，修订主仓文档不回填旧集合。
- 原41保护对象、原Chroma38文件、整.env、HEAD／refs与原脏文档，模型默认11文件及旧公开库另做验后检查；完整输出保存在 `independent-final-review.json`，详见 [独立审核报告](C:/Users/33393/Desktop/ai-legal-helper/docs/work-report-20261003-independent-review.md)。当前前端5项并行改动不在本轮修改范围。

更正的是报告口径与证据缺口，没有在主仓应用A／B依赖变更。此审核时仍未做联合候选；随后联合技术验证见§10。完整启动／浏览器、Linux／CI、真实生成、额外rerank、提交／合入／push、原库写入或部署仍未做。C仍PARTIAL，D2仍待Owner具体裁定，10月5日不顺延。

## 10. 后续仓外联合验证（2026-10-03，23:07+08）

用户要求继续接手后，独立新根 `C:/Users/33393/Desktop/fazhi-joint-candidate-20261003-ac701f4a880441b5a453b1b7cbb06f01` 从冻结源码及既有wheel重新离线安装，联合A requirements与B setuptools83约束。162实装／165约束；源码仅requirements相对原候选不同，相对A仅setuptools实装版本变化。27定向、1690 nodeid一致、Ruff／mypy、1680通过／10跳过／18不选、85.42%、公开库烟测24/24均通过。

本次不是重算原A／B审计：新实装联网公告扫描JSON为 **34行／7包／21组**，退出1，有通报；torch+cpu跳过仍单列。14条安装／门禁／审计命令有真实时间及退出码。v2交付49个manifest内容对象／实际50文件、9字段正控成立、0命中，原失败集合和失败原因保留。详情与对象SHA见 [联合报告](C:/Users/33393/Desktop/ai-legal-helper/docs/work-report-20261003-joint-candidate.md)。本节是新检查点，不覆盖旧73文件集合中的历史副本，不代签正式依赖采纳／D2或扩大真实调用／提交／部署许可。
