# 公开副本本机补验与收尾报告（2026-10-05）

## 结论与边界

**真实管理端补验、固定BGE CPU空间复验、正文法条引用展开已取得通过证据；用户主动取消／取消后重问仍未满足。本阶段仍为T6部分完成，不是发布接受或上线完成。**

用户“按你的推荐执行”批准的对象：1528条公开语料的独立副本、固定revision本地BGE CPU、本机LLM替身、禁止外联、禁止下载／安装。未包含完整真实语料、真实外部模型、风险接受、主仓合入／提交／push或部署。本轮没有改变这条边界。

以下路径均可直接定位，不需要其他会话记忆：

- 主仓：`C:/Users/33393/Desktop/ai-legal-helper`，HEAD `902e2d161e67100ed6d267a08c393538a0abe109`。
- 实验根STAGE：`C:/Users/33393/Desktop/fazhi-next-local-repair-20261004-a6b8b40ac2f74c94b331eeda8a30072c/local-stage-20261004`。
- 上轮5行日期修订REPAIR：STAGE的父目录；原修订过程见[10月4日修订报告](C:/Users/33393/Desktop/ai-legal-helper/docs/work-report-20261004-next-local-repair.md)。
- 只读复用解释器：`C:/Users/33393/Desktop/fazhi-next-local-20261004-356fb810b3144d158e5dd18b9e276499/joint/venv/Scripts/python.exe`。
- 公开原件及独立金标：`C:/Users/33393/Desktop/fazhi-local-candidate-20261002-67944caf51ff48ce9432831cdd62f72b/public-kb`及其`evidence/public-corpus-review.json`。

STAGE含288份修订后端文件和71份冻结前端文件；未吸收主仓5份未交付前端脏改动。node_modules及11份模型文件使用已有本机副本复制，无安装／下载。读写两条验收路径使用不同公开副本与SQL库；写入腿结束后才起读取腿。合成写入只在`runtime/attempt-02/write-kb`，不进入读取腿／原真实库。

## 已取得的直接证据

以下业务执行发生于10月4日晚；10月5日只做只读证据复核、纯守卫测试和收尾检查，没有重新启动模型。

| 需求 | 直接结果 | STAGE内证据 |
| --- | --- | --- |
| 管理端真实路由／持久化 | 33项断言通过；四日期字段各3种非法日历值均422，缺生效日／反向区间422且总量不增；合法闰日200、增1块，正文／法名／条号／四日期逐值回读一致 | `evidence/attempt-02/write-acceptance.json`、`write.log` |
| 登录／管理权限／PDF | 真实登录200；未认证管理请求401，普通用户403；损坏PDF400且不新增块。真实limiter保持启用；不是AUTH全回归 | 同上及`write-startup.json` |
| 固定BGE CPU实际执行 | 1528法条、QA=0；原8个固定ID，768维，余弦均≥0.99999，最小值0.9999999999998204。不是重算旧记录，也不是零向量替身 | `evidence/attempt-05/bge-space-fresh.json` |
| 真实启动预热／公开检索 | 实际lifespan执行、BM25 1528条及4部法源预热；检索返回的劳动法44条及完整正文与独立金标配对 | `read-startup.json`、`public-retrieval.json`、`citation-gold.json` |
| 前端构建／登录／流式接线 | 隔离冻结前端`next build`退出0；浏览器真实登录进入后台，再进入聊天页，两次问题完成显示替身内容 | `evidence/attempt-02/build.log`及该轮`cleanup.json`的build退出码；`attempt-05/followup-completed-ui.txt` |
| 正文引用点击原文 | 实际点击回答正文《中华人民共和国劳动法》第四十四条，展开全文与公开记录`c72b1112-2b91-4e83-96ae-d9675e084089`逐全文空白归一比较相等；该记录正文SHA也与冻结公开审查金标匹配 | `attempt-05/citation-dom-verdict.json`、`citation-ui.jpg` |
| 慢流自然完成后恢复 | 第二次问题的替身慢流自然完成，显示2个反馈入口且输入可用。**不是用户取消恢复** | `attempt-05/followup-verdict.json`、`stub-requests.jsonl` |

表中未写全路径的后三项均在STAGE的`evidence/attempt-05`。预热／向量／具体检索只覆盖公开集合及单机样本，不给全库召回率、性能或法律回答正确率。LLM替身输出明确标记，不作为法律质量金标；日志中的qwen模型名仅沿用路由标识，所有27项路由实际重定向到本机替身。

实际命令入口为解释器`-I -B STAGE/orchestrate.py attempt-02`（管理端及构建），以及`attempt-05`（续办读取／浏览器服务）。该入口包含独占新建输出和一次性目录，**不能直接原样重跑**；现在已到10月5日复审点，也不能凭本报告重启模型。复验应先取得新许可，另建独立对象，复用冻结源码与已有依赖。

## 未通过项：主动取消／取消后重问

中等影响，高置信度：冻结前端流式期间仅显示禁用的发送按钮，没有“停止生成”或对应用户取消回调。`source/frontend/components/chat/InputBar.tsx:206`禁用发送；`source/frontend/lib/api.ts:166`的AbortController是内部闲置看门狗，不是暴露给用户的停止入口。`app/chat/page.tsx`和`lib/hooks/useChatStream.ts`也尚未完成停止接线。

浏览器慢流状态保存于`evidence/attempt-05/slow-stream-ui.txt`／`.jpg`；`cancel-ui-verdict.json`明确`pass=false`、`cancellation_performed=false`、`reask_after_cancellation_verified=false`。自然完成的两次回答、HTTP断开或180秒超时均不能代替该要求。参考列表的法名徽章本来是静态标签；真正验证通过的是正文内的法条点击，不将两者混淆为缺陷。

最小后续方向（建议，尚未实施）：在**新独立候选副本**中复用既有AbortController，通过现有useChatStream和页面接线向输入栏提供停止按钮；保留超时、安全校验及finally收尾。补“尚未出首字”和“已出部分文字”两类停止、连续点击停止、停止后同会话重问的定向测试及实际UI补验。不加状态框架／新依赖，不改页面美术，不直接覆盖主仓脏文件。UI停止不自动证明上游已停止生成或停止计费，须分开观察。

## 仪器失误、保护与自审

- 所有失败轮保留：根`evidence`为首次错误健康路径`/health`；attempt-02的读取腿错误使用长法名精确过滤；attempt-03续办遇到默认GBK解码UTF-8；attempt-04仍受默认50条分页影响。只修验收仪器，不改变产品来迁就断言。SQLite只读诊断证实劳动法107条、44条确实存在；attempt-05采用正确短法名和完整分页并与独立金标匹配。不是无解释反复重跑直到绿。
- Python审计守卫纯测试先7失败／5通过，修正后12通过；10月5日同套定向测试再运行12通过。后端实际进程的四个正控均在发包／读取配置／外部写入之前拒绝；Next进程有网络正控。守卫是Python审计／Node网络拦截，加HF离线及禁XET配置，**不是OS级全网络沙箱**，不据此声称覆盖原生代码的每种网络路径。
- `evidence/protection-before.json`／`protection-after.json`均通过：主仓HEAD、refs、空暂存区、原6个tracked脏文件、41个保护对象、真实库38文件、整份配置、公开原件、原模型及revision均未变。10月5日`closeout-verification-20261005.json`进一步复核288+71源码和11个模型副本指纹一致。
- attempt-01至04保存了当时清理记录。最终attempt-05会话已中断，**未取回正常清理事件／退出码**，不补造“正常退出0”。10月5日`cleanup-recheck-20261005.json`新查确认没有本轮相关Python／Node进程，3021／8021／8022／8781无监听。当前安全收尾成立，但历史最后退出方式证据不完整。
- 凭据复扫入口`STAGE/scan_records.py`，以新标签输出九个当前输入的值扫描／五类形状正控及选定交付文件manifest。首次扫描80个选定文字文件，九值均零命中、五类正控有效，仅扫描器自己的一份合成私钥头正控命中；分类规则原先误用规则ID，修正后另存`stage-closeout-scan.json`作为最终结果，保留首次`stage-final-scan.json`。不输出凭据值、长度或key hash；未分类形状命中必须使最终扫描失败。图片仅人工核看，不冒充OCR；模型、DB、依赖和运行缓存不在文字扫描范围。**不外发整根实验目录。**
- 本轮是执行者自审，没有新的独立审查者签署，也没有Owner风险接受。完整回归没有重跑；刑法／宪法等原real_kb测试所需输入仍不在授权公开集合。既有依赖风险及BGE上游来源PARTIAL未关闭，本轮没有用旧扫描冒充新审计。

## 下一停点

继续开发前先对齐“仅补主动停止”的小范围，再复审是否允许**新一轮同等受限BGE CPU本机实验**。10月5日复审点不自动顺延；本报告不是新许可。主仓合入／提交／push、真实库写入和部署仍待各自授权；没有选服务器，不安排部署。
