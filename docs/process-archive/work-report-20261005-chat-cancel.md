# 主动停止与停止后重问修复报告（2026-10-05）

## 结论

**本轮授权的前端修复已实现并通过定向测试、生产构建及实际浏览器补验；项目仍为T6部分完成，未发布、未合入主仓。**

“停止生成”会立即恢复输入，保留已有部分文字并标记为未完成；旧请求的回调和收尾不能释放或改写新请求。首字前停止、双击停止、同会话重问、HTTP错误恢复和离开页面取消均取得前端证据。浏览器连接关闭不等于真实后端计算或计费已终止，本轮没有运行后端、数据库、BGE或外部模型。

## 对象与授权

- 主仓：`C:/Users/33393/Desktop/ai-legal-helper`；HEAD仍为`902e2d161e67100ed6d267a08c393538a0abe109`，暂存区为空。
- 新独立候选ROOT：`C:/Users/33393/Desktop/fazhi-chat-cancel-20261005-eb0f87ebddb44cd6a133684cd65a27b8`，不是Git分支或已提交worktree。
- 冻结前端来源：`C:/Users/33393/Desktop/fazhi-next-local-repair-20261004-a6b8b40ac2f74c94b331eeda8a30072c/local-stage-20261004/source/frontend`。原71文件逐SHA验证后复制；node_modules从该来源独立复制，不安装、不下载。
- 只读复用解释器：`C:/Users/33393/Desktop/fazhi-next-local-20261004-356fb810b3144d158e5dd18b9e276499/joint/venv/Scripts/python.exe`。Node为`C:/Program Files/nodejs/node.exe`。
- 用户“允许”仅批准新候选中的主动停止＋取消后重问。没有续期10月5日复审点的模型许可；没有主仓代码覆盖、合入、提交、push、真实库写入或部署授权。主仓只新增本报告。
- 简化原则：复用现有AbortController/useRef/原生信号，不加依赖、状态框架、取消服务、美术或动画。既有超时、安全检查和异常提示保留。

## 产品改动

ROOT的`source/frontend`下只有以下4份原有文件改变，另新增1份测试；其他67份冻结文件及旧来源71份指纹未变：

| 文件 | 改动 |
| --- | --- |
| `lib/api.ts` | streamChat末尾增加可选AbortSignal，接到原AbortController；取消后丢弃迟到帧/HTTP错误；finally移除监听、清超时、释放reader，网络失败不遗留看门狗 |
| `lib/hooks/useChatStream.ts` | 当前请求ref及stop；停止立即恢复UI，清未完成Agent续跑状态，追加停止提示；回调与异步收尾按请求身份隔离；卸载中止请求 |
| `components/chat/InputBar.tsx` | 生成时同一按钮位置变为可用停止按钮，type=button、明确aria-label；非生成态保留原发送逻辑及样式 |
| `app/chat/page.tsx` | 将stream.stop接到InputBar，不改其他编排 |
| 新增`tests/chat-cancel.test.ts` | 原生信号/Response/ReadableStream＋网络边界fetch替身；不模拟React内部状态、不引入测试依赖 |

最终差异见ROOT的`evidence/product-changes-delivery.patch`；72份源码指纹见`evidence/final-source-manifest-delivery.json`。构建另生成原有postbuild要求的`public/build-id.txt`，不属于冻结71源码清单，不作为新的业务改动。

**不得整目录覆盖主仓。** 主仓的chat/page.tsx及InputBar.tsx已有未交付脏修改；将来整合必须先确认这些改动的归属与取舍，再做文件级三方核对。这个候选不包含主仓那5份前端脏改动。

## 验证结果与复现入口

已有54项前端基线通过。新增最初9项测试出现7失败／2通过，正确失败于缺少取消、迟到帧放行和清理；实现后9通过。自审补“取消后迟到HTTP错误”第10项，先1失败／9通过，再10通过。未把编译／运行环境错误当成功能红灯。

最后交付验证均退出0，完整输出在ROOT的`evidence`：

- `delivery-tests.log/.json`：8个测试文件、64项测试通过，0失败。
- `delivery-lint.log/.json`：无ESLint警告或错误。
- `delivery-types.log/.json`：tsc --noEmit退出0。
- `delivery-build.log/.json`：next build生产构建通过。
- `delivery-build-id.log/.json`：实际执行原write-build-id.mjs，而非只跑Next构建。

当前对象的日志为独占输出，**不要原样重复已用标签**。不下载的重新验证可用新标签复制run_frontend.py的同一命令定义，环境保留OS变量白名单并剔除provider凭据；Next禁遥测，Node网络守卫只允许回环，并包含发包前拒绝的正控。不是OS级全网络沙箱。

后端／真实模型／AUTH全回归／原real_kb完整回归没有重跑；64不是全项目测试总数。新的前端测试验证API取消，hook/UI通过实际浏览器验证；同一事件循环内的极限取消重问、真实Agent续跑取消和不同浏览器／移动端未作完整专项测试。

## 实际浏览器补验

内置浏览器实际加载独立候选`http://127.0.0.1:3031/chat`（桌面1280×720）；假API只监听`127.0.0.1:8031`，不导入产品后端、不读库或模型、不持久化真实数据，账号和口令均为合成测试输入。假API使用冻结真实/api/chat相同的SSE响应头，前端请求经过原Next同源反代。

| 检查 | 观察及证据（ROOT/evidence） |
| --- | --- |
| 页面身份／非空／无框架错误页 | 标题为法智、URL为/chat，有完整聊天UI；截图`cancel-reask-final.png` |
| 首字前停止 | 实际按Enter停止；显示“已停止生成”，输入恢复；`ui-before-first-stop.txt`、`ui-first-stop.txt` |
| 部分文字＋重复停止 | 实际双击停止，部分文字保留且仅一次停止标注；`ui-partial-busy-final.txt`、`ui-partial-stop-final.txt` |
| 停止后同会话重问 | 新请求先生成、随后回答完成，旧回答仍为未完成，无迟到文字；`ui-partial-reask-busy.txt`、`ui-partial-reask-complete.txt` |
| 故障恢复 | 合成503正常显示错误，之后能发送下一问；完整`ui-before-unmount.txt`保留错误与新问题，`ui-requests.jsonl`证明后续请求 |
| 页面离开取消 | 挂起时点击退出进入/login；假服务观察连接未正常完成即关闭；`ui-before-unmount.txt`、`ui-after-unmount.txt`、`ui-requests.jsonl` |
| 控制台／连接 | 最终相关页面error/warn为空；全部测试chat请求conversation_id=7。首字前、部分文字和卸载请求均有未完成关闭记录；延迟窗口发现旧连接已关闭 |

完整判定见`ui-final-verdict-delivery.json`（pass=true），图片是实际页面，不是生成示意图。未改变浏览器尺寸或用户原标签；本轮新建测试标签已关闭。

自审确认：ref同步防重复发送；stop幂等；旧finally不复位新streaming；正常完成、超时及错误仍可恢复；React updater再次检查aborted，避免已排队的旧文字覆盖停止提示；取消不伪造coverage=full。清理未完成Agent续跑标记是避免重问误用已取消版本，**不是服务器Agent run已被撤销的证明**。

## 失败记录、保护与收尾

- 首次baseline早于依赖复制完成；baseline-ready实际测试退出0，但终端GBK不能打印勾号。修正验证脚本UTF-8显示。原日志均保留，这两次是仪器问题。
- lib/api.ts在既有Prettier债务排除表中，尝试范围格式化实际无变化；没有删除排除规则或全文件重排。仅手动整理新增try块缩进，之后重新运行交付验证。
- 第一假API漏了真实SSE的no-transform，直连34ms收到首帧，而Next反代5秒超时。核对真实main.py已有防缓冲头后只补假服务，反代13ms收到首帧；原`stream-transport-diagnostic.json`及修正后的`stream-transport-diagnostic-headers.json`都保留。不是为了过验收改产品反代。
- 两次UI等待失败保留：一次来自上项假服务缓冲；另一次等待窗口短于假服务4秒延迟。读取新状态后才确认完成，未重复发送问题。
- 初稿`ui-verdict.json`的error_recovered=false来自差分AX仅返回“无变化”，不是用户错误恢复失败。保留初稿；最终判据取之后完整快照和后续真实HTTP请求，并在`ui-final-verdict-delivery.json`记明来源。
- `protection-before.json`／`protection-delivery.json`的12项保护检查通过：HEAD、refs、空暂存区、6份原tracked脏文件、41保护对象、真实库38文件、配置整份指纹、公开原件、原模型及ref、此前依赖/约束均未变。不输出密钥值或key hash。
- 初步凭据复扫覆盖83份选定文字文件；加入交付资料后复扫101份，9个当前输入零命中、5类形状正控有效；只命中扫描器自己的合成私钥头正控，已分类。**更新执行清单后的最终交付复扫，以ROOT/candidate-delivery-scan.json为准**。不外发整根候选；DB、模型、node_modules、缓存和图片OCR不在文字扫描证明范围。
- 最后UI长执行会话的正常清理事件／退出码未取回，不补造退出0。`cleanup-recheck-delivery.json`新查确认本轮启动记录的PID已不存在，3031／8031无监听；目前已安全收尾。第一轮清理记录仍在。
- `closeout-verification-delivery.json`确认frontend_scope_pass=true，同时明确full_stage_acceptance=false、independent_reviewer_signed=false。本轮为执行者自审，不冒充新独立审查或Owner接受。

## 下一阶段边界

1. **先重新批准受限真实后端联调。** 使用新的公开数据库副本、固定revision已有本地BGE CPU及本机LLM替身、禁下载／外联，验证用户停止向真实后端的断连传播、未完成消息持久化与重问。旧模型许可已到复审点，不自动续期；本报告不构成新许可。
2. **随后处理主仓整合。** 审清原脏文件，按最终patch合并必要代码和测试，重跑整合后门禁。没有主仓覆盖／提交授权，本轮不代办。
3. **发布前仍有其他门禁。** 全项目回归输入缺口、依赖风险裁定、BGE来源PARTIAL及Owner接受／独立审核仍未关闭；真实rerank新调用另受授权/预算限制。push、真实库写入、服务器选择和部署各自审批，当前不安排部署。

此前公开副本检索／管理补验的结论仍见[公开副本验收报告](C:/Users/33393/Desktop/ai-legal-helper/docs/work-report-20261005-public-local-acceptance.md)；本轮只关闭其中主动停止的前端缺口，不将两个不同候选的局部通过相加为完整发布验收。
