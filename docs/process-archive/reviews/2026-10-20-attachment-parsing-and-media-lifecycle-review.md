# 法智：附件解析与图片生命周期补充审查（2026-10-20）

本轮新增 **2 项已在隔离副本上复现的 P2 缺陷**；另补充确认 **1 条历史静态线索**。新增问题均在模型接收材料之前发生，影响上传合同的事实完整性。当前只交付审查证据和修复提示词，业务代码未修改。

## 1. 审查对象与执行边界

- 主要对象：`C:/Users/33393/Desktop/ai-legal-helper/.worktrees/nondeploy-closeout-20261010`，快照时 HEAD 为 `69577e941eabaf4b1a38697f9b684ede1e2ff775`。结论绑定选定文件的实际字节，不仅绑定提交号。
- 范围：DOCX 上传解析、聊天/管理上传入口、图片鉴权及会话删除后的文件生命周期；不涉及目录搬移、Git 历史处置、QA 撤回策略或原 R01–R25 修复验收。
- 共复制 17 个选定源码、配置和现有测试文件到独立证据目录；没有复制数据库、媒体原件或任何 `.env`。复现只使用自行构造的不足 1 KB 的 DOCX 输入。
- 没有导入 `main`、`knowledge_service` 的完整模块，没有启动应用、调用模型、读写数据库、安装依赖、执行项目测试套件或改变候选工作树。唯一新增项目文件是本报告。
- 复现直接加载副本 `docx_utils.py`，再从副本 AST 提取 3 个解析函数和 `chat_file` 函数。端点装饰器、认证依赖和真实 HTTP 上传读取未执行；使用仅含内存字节的上传替身及既定默认值 `upload_max_mb=10`、`contract_max_chars=12000`。
- 因此，下面的 JSON 是**真实解析代码和端点函数体的函数级结果**，不是实际 HTTP 请求、浏览器、Word 渲染或生产性能验收。

证据根目录：

`C:/Users/33393/.codex/visualizations/2026/10/18/01a14fe1-dd41-7e83-a8f6-c4c2d27b6be7/fazhi-upload-media-review-20261020`

## 2. 发现总览

| 编号 | 级别 / 置信度 | 结论 | 与历史审查的关系 |
| --- | --- | --- | --- |
| A01 | P2 / 高 | Word 块级内容控件中的正文被整段丢弃 | 本轮新增；副本实际复现 |
| A02 | P2 / 高 | 表格单元格内的段落、换行、制表符被删除，数字会拼接 | 本轮新增；副本实际复现 |
| A03 | P2 / 高（调用位置） | 两个 async 上传入口同步执行文档解析 | 首轮报告 §4 的可选补查线索；本轮确认候选仍存在，未测实际阻塞时长 |

分级依据：A01/A02 会使用户提交的法律材料在正常解析成功的外观下缺失或改变事实；A03 的影响范围可能扩大到同一工作进程的其他请求。没有证据支持将这些问题定为已发生的生产事故或 P1。

## 3. A01：内容控件包住的条款被静默跳过

**位置**：[docx_utils.py:78](C:/Users/33393/Desktop/ai-legal-helper/.worktrees/nondeploy-closeout-20261010/backend/docx_utils.py:78)，关联 [knowledge_service.py:128](C:/Users/33393/Desktop/ai-legal-helper/.worktrees/nondeploy-closeout-20261010/backend/knowledge_service.py:128)。

`extract()` 只处理 `w:body` 的直接 `w:p`、`w:tbl` 子节点。块级内容控件的实际正文在 `w:sdt/w:sdtContent` 下面，因此整个容器被略过。这种结构可以合法承载段落和表格，不属于页眉、批注等已声明排除的内容。[Microsoft 的 SdtContentBlock 说明和示例](https://learn.microsoft.com/en-us/dotnet/api/documentformat.openxml.wordprocessing.sdtcontentblock?view=openxml-3.0.1)。

**实际复现**：同一句“乙方不得提前解除合同。”，直接放在正文段落时完整提取；放在块级内容控件里时：

| 合成输入 | 解析结果 | 端点函数结果 |
| --- | --- | --- |
| 普通标题 + 普通条款 | `合同正文\n乙方不得提前解除合同。` | 保留条款 |
| 普通标题 + 控件内条款 | `合同正文`，warnings 为 `[]` | 返回 text 仅含标题，`chars=4`、`truncated=false` |
| 只有控件内条款 | 抛出“提取文本为空（可能是扫描件或无文字内容）” | 转为 status_code=400 的端点异常 |

**后果**：混合文档比完全失败更隐蔽。用户得到可发送的文本，但关键条款已经丢失；后续模型无法补回未收到的事实。`truncated=false` 只说明没有触发字符上限，本身不能证明提取完整。

**最小修复方向**：扩展现有块级遍历，明确进入 `w:sdtContent` 并保持原文顺序；遇到段落、表格后由相应解析器处理，避免同时遍历其所有后代造成重复。不需要为此换一套文档框架。未支持且含正文的结构应明确提示，不应悄悄跳过。

**后续验收建议**：混合正文、全文控件、控件内表格、嵌套控件均保留各条款且仅出现一次；原有删除修订排除规则保持正确。

## 4. A02：表格中的不同数字被拼成一个数字

**位置**：[docx_utils.py:35](C:/Users/33393/Desktop/ai-legal-helper/.worktrees/nondeploy-closeout-20261010/backend/docx_utils.py:35)，重点是第 40 行直接对所有后代 `w:t` 做空串拼接。

普通段落使用 `_para_text()`，会保留 `w:br`、`w:tab` 的分隔语义；表格单元格走另一套提取逻辑，只收集文本节点，连不同段落之间也没有分隔。Word 中 `w:br` 和 `w:tab` 分别具有换行、制表作用，不能无条件删除。[Microsoft Break 说明](https://learn.microsoft.com/en-us/dotnet/api/documentformat.openxml.wordprocessing.break?view=openxml-3.0.1)、[TabChar 说明](https://learn.microsoft.com/en-us/dotnet/api/documentformat.openxml.wordprocessing.tabchar?view=openxml-3.0.1)。

**实际复现**：

| 内容结构 | 普通正文对照 | 放入单个表格单元格后的结果 |
| --- | --- | --- |
| 两个段落分别为 `1000`、`2000` | `1000\n2000` | `10002000` |
| 两段数字之间为 `w:br` | `1000\n2000` | `10002000` |
| 两段数字之间为 `w:tab` | `1000 2000` | `10002000` |

三个表格输入均无解析警告，端点函数均返回 text=`10002000`、`chars=8`、`truncated=false`。

**后果**：文本提取已经改变金额、日期或编号的边界。对合同审阅而言，这不是单纯的排版损失；即使模型严格按输入回答，也可能依据一个原文并不存在的数字进行分析。是否在真实用户合同中发生过，当前没有调查证据。

**最小修复方向**：复用已有 `_para_text()` 的换行/制表处理，按单元格内的段落或块顺序加入分隔，同时保留行、列边界。复核 `tbl.iter(tr)` / `tr.iter(tc)` 的递归范围，避免修复时把嵌套表格重复提取。不要把所有 run 都插空格，普通文字跨 run 分割本来可能属于同一个词或数字。

**后续验收建议**：同一单元格多个段落、显式换行、制表符、普通连续 run，以及多个单元格分别覆盖；确保数字不会被拼接，也不会因过度插空格而被拆坏。

## 5. A03：同步解析仍发生在事件循环中

**位置**：[main.py:1929](C:/Users/33393/Desktop/ai-legal-helper/.worktrees/nondeploy-closeout-20261010/backend/main.py:1929)、[main.py:3520](C:/Users/33393/Desktop/ai-legal-helper/.worktrees/nondeploy-closeout-20261010/backend/main.py:3520)。

两个入口 `chat_file()`、`admin_upload()` 都是 `async def`，在其函数体中直接同步调用 `ks.parse_upload_or_raise(...)`。之后才调用 `await run_in_threadpool(_do)`；耗时的 PDF/DOCX 解析没有进入线程池。解析函数中的 PDF 分支遍历全部页面提取文字，DOCX 分支读取压缩 XML 并构建整棵树；聊天字符截断也发生在解析完成后。

这条线索已记在 [首轮报告第 209 行](C:/Users/33393/Desktop/ai-legal-helper/docs/process-archive/reviews/2026-10-19-independent-readonly-audit.md:209)，本轮不是重新发现。此次 AST 检查确认了候选中的具体调用位置。候选 Dockerfile 的启动命令未指定多 worker，Compose 也声明单 worker 运行约束。

**后果与证据界限**：同步解析执行期间，同一事件循环不能调度其他协程；复杂材料可能拖慢聊天流、取消处理或健康检查。本轮没有启动应用、构造大文件或做负载实验，**不提供毫秒、吞吐量或故障概率数字**。

**最小修复方向**：把完整的解析工作放入项目已有的线程池边界，两个上传入口一致处理，并保留大小限制和 `ValueError → 400` 的行为。线程池只能解除事件循环上的直接同步执行，不能被当作解析 CPU/内存硬隔离或完整的恶意文档防护。

**后续验收建议**：在独立环境延迟解析操作，观察另一个轻量请求仍能被调度；同时验证正常解析结果和错误状态。不要在当前助手使用的服务、端口或数据目录上做此实验。

## 6. 两项观察：暂不作为独立缺陷计数

### O01：已有 DOCX 警告没有传给上传调用方

`docx_utils.extract()` 会对修订插入、简单域代码返回 warnings；`knowledge_service.parse_uploaded()` 将它绑定为 `_warnings` 后丢弃。合成修订文档中，底层有 1 条 warning，端点函数结果没有 warning 字段；现有 `ChatFileResult` 和页面也没有对应展示契约。

这是已确认的数据流事实。应先决定“上传后是否提示修订/域代码及其具体含义”，再决定是否扩展响应。没有把“存在修订”直接等同于“文本提取错误”，也没有证明这条提示能覆盖 A01/A02。

### O02：删除会话与物理删除图片是两件事

现有 `get_media()` 有登录鉴权及 Message→Conversation 归属检查，本轮**没有发现匿名读图入口**。会话删除函数只删除数据库会话并提交，没有发现其调用图片文件清理；已找到的 `cleanup_persisted_images()` 用于失败请求的回滚，不是成功会话删除后的回收。

因此，源码提示删除会话后可能留下失去消息引用的原图/缩略图。鉴权端点的消息归属检查会阻止通常的再次读取，不能据此声称图片会公开。保留期限、备份保留、磁盘回收策略尚未在本轮得到明确契约，故登记为待决策项；没有扫描或删除真实媒体文件，也没有测量残留数量。

## 7. 证据与可复现方法

| 证据文件 | 用途 |
| --- | --- |
| `snapshot-meta.json` | 候选根目录、HEAD、UTC 快照时间 |
| `source-manifest.json` | 17 个选定文件的 SHA-256 和字节数 |
| `source-drift.json` | 与候选实时文件的逐项比较；复现后检查为 0 个变化 |
| `observe_parsing.py` | 无第三方依赖的观察脚本，只调用复制出的纯解析函数及无装饰器端点函数体 |
| `observations.json` | 10 组小型输入的实际输出及两个直接解析调用的 AST 位置 |
| `fixtures/*.docx` | 合成输入，原始字节 SHA-256 记在 observations.json 中 |

运行观察脚本的本次命令退出码为 **0**；这是脚本成功运行并记录结果，**不是产品测试通过**。其中 A01/A02 记录的是缺陷输出。

```powershell
python -B 'C:\Users\33393\.codex\visualizations\2026\10\18\01a14fe1-dd41-7e83-a8f6-c4c2d27b6be7\fazhi-upload-media-review-20261020\observe_parsing.py'
```

命令会重新生成这个独立证据目录内的合成文档和结果，不需要访问产品服务。ZIP 默认时间戳可能使重生成后的 fixture 哈希变化，应比较重新生成的文件与同次 observations.json，不把跨次 ZIP 字节不同当作产品回归。

关键快照指纹：

| 文件 | SHA-256 |
| --- | --- |
| backend/docx_utils.py | `1EC3E4375B19C0C93C74E8A2616D8457DA4CB69147FF8B834DF2EC1ACC7C5983` |
| backend/knowledge_service.py | `9A99207AB80516028A1A1F0FF0E4D369C74B373D5588B9AAD8E7BCCB44139B35` |
| backend/main.py | `776EAB226DC05ED1E78C8304BD76B629E5DF6EE9A04964277208C3C79BA884B5` |

主仓 M 的 `docx_utils.py` 与该候选副本 SHA-256 相同，说明解析器缺陷形状也存在于 M；其余业务编排结论仍以本轮候选实际代码为准，不把主仓与候选混作一个版本。

现有测试仅作阅读：`test_docx.py` 覆盖直接段落、简单表格、删除修订、警告与非法 ZIP；其中的表格 fixture 每格只有一个简单段落。本轮未在这 3 个已读取测试文件中定位到内容控件、同格多段落/换行/制表符的对应断言，**不等于穷举全仓后证明没有其他覆盖**。

规格结论：本轮已证实支持的 DOCX 路径会改变或遗漏正文事实。工程结论：A01/A02 需要修复，A03 需处理调度边界；完整产品质量、真实 Word 兼容性、HTTP/浏览器集成和生产性能均未在本轮验收。

## 8. 可交给后续助手的提示词

```text
请独立确认并最小化修复本报告的 A01/A02；A03 是历史线索的候选复核，避免重复建票。

先确认实际工作树、当前 HEAD 和未提交修改，逐项重读相关代码。报告绑定
69577e941eabaf4b1a38697f9b684ede1e2ff775 时的选定文件字节；若代码变化，先检查问题是否仍存在。

A01：混合 DOCX 中的 w:sdt/w:sdtContent 正文不得静默消失；全文控件不应误判扫描件。
A02：同一表格单元格内的段落、w:br、w:tab 必须保留可辨别的边界，不能把 1000/2000 拼为 10002000。
优先扩展现有块遍历并复用 _para_text，不新增文档框架；保持原文顺序、删除修订排除和不重复提取。
A03：核对 chat_file/admin_upload 的解析是否已进入项目既有线程池；保留异常、上限及响应兼容性。

审查证据目录有合成输入和观察脚本，但其端点函数调用跳过了认证/装饰器，不能代替真实集成测试。
若获准修复，请为两个缺陷提供能在旧实现上失败的定向回归，并在隔离环境验证上传调用链。
不要用“只给模型加提示词”“只有 truncated=false”“单测数量/覆盖率增加”替代正文正确性的证据。

O01 警告如何展示、O02 图片保留与回收属于待定契约：先说明选项与影响，不自动删除媒体。
请逐项报告：当前是否成立、证据、最小改动、定向验证和仍未覆盖的边界。
```
