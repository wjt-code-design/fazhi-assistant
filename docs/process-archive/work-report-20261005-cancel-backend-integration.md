# 取消生成：受限真实后端联调报告

日期：2026-10-05（UTC+8）。结论：**本轮取证已完成，但候选未通过取消联调验收，整个阶段也未因此完成。** 未修复产品代码、未合并、未提交、未推送、未部署。

## 1. 本轮实际范围与输入

用户本轮“批准”授权：真实后端与前端联调、独立公开库副本、已有固定版本本地 BGE CPU、回环 LLM 替身。没有授权外部模型调用、下载/安装、真实库写入或产品缺陷修复。本轮不自动沿用为下一轮模型许可。

独立目录（非 Git worktree）：

`C:/Users/33393/Desktop/fazhi-cancel-backend-20261005-3d68d1547a1c47839266df465a7b6629`

- 后端：此前修复候选的 288 个冻结文件；前端：停止按钮修复候选的 72 个冻结文件。合计 360 文件前后 SHA-256 一致，本轮没有改动产品源码。
- 公开库：新副本，启动时 1528 块、4 部法律、QA=0；原公开库不动。会话与账户使用新建隔离 SQLite。
- BGE：已有缓存独立复制，`BAAI/bge-base-zh-v1.5`，revision `f03589ceff5aac7111bd60cfc7d497ca17ecac65`，CPU、768 维、离线。8 个冻结样本空间复验通过；这不是法律质量评测。
- LLM 27 个角色全部改为本机替身；合成配额为 0，故实际是配额降级到默认模型的路径。保留 `feature_router=true`，**不等于验证了正常可用的多模型池**。rerank 与 Agent 均关闭。
- Python audit hook 与 Node 拦截提供实验级边界，不是操作系统沙箱。环境白名单、禁用 .env 自动发现、合成登录凭据；不记录 JWT/Authorization。
- 本轮端口为前端 3041、后端 8041、替身 8791，均绑定回环，启动前确认空闲。原用户浏览器页面 3021 未动。

只修改了实验辅助脚本并新增本报告；原项目的 6 个已修改跟踪文件、暂存区、HEAD、引用、原库、配置与原模型缓存的 12 项保护检查前后均通过。

## 2. 验收结果

| 项目 | 结果 | 证据含义 |
|---|---|---|
| 前端测试 | PASS：64/64，8 文件 | 本轮真实执行；不能替代后端取消验收 |
| 实验测试 | PASS：14/14 | 12 个既有边界测试＋2 个替身当前问题识别测试 |
| Next 生产构建与 build-id | PASS，退出码均 0 | 后端代理目标为本轮 8041 |
| 首字前停止 | 页面 PASS；上游 FAIL | 确认替身已接到回答请求，尚无正文时点击；页面提示停止，但上游继续完成 |
| 部分正文后双击停止 | 页面 PASS；上游 FAIL | 页面保留未完成提示，没有多存一轮；上游仍生成完全部片段 |
| 已有会话取消与重问 | PASS（当前持久化契约） | 会话 1 共 6 条，user/assistant 交替；两次取消存失败占位，随后正常答案落库 |
| 历史重开 | PASS，但有限制 | UI 重开与真实 API/SQLite 一致；半截文字没有持久化 |
| 新对话取消后重问 | **FAIL** | 页面连续显示两轮，但首轮存会话 2，重问存会话 3 |
| 绕过 Next 直接断开后端请求 | **FAIL** | 上游仍完成；不能把问题全部归因于前端代理 |
| 轻量缓冲分支 | 未覆盖 | 名为“缓冲”的探针也不能作轻量证明：冻结 DEFAULT_ROLES 没有 text/light 角色，实际仍会走流式分支 |
| SQLite 一致性 | PASS | 最终 API/SQLite 18 条消息内容/归属一致；7 个会话计数匹配，integrity_check=ok，assistant coverage=unknown |
| 服务清理 | 已清理；正常退出 FAIL | 两轮后端退出码均为 3221225477（0xC0000005）；不能写成退出正常 |

“页面 PASS”只指测试条件下停止显示、释放输入和屏蔽迟到内容有效，绝不代表模型已停止计算或计费。

## 3. 已确认问题与最小后续方向

### P1：停止未及时关闭上游回答流

第二轮 UI 首字前、已有会话部分正文、新对话部分正文三次取消，上游均继续生成完 72 个合成片段。绕过 Next 的直接后端取消也生成完 72 个片段，因此至少有后端资源生命周期缺口，不能只改代理后宣称解决。

已做无模型、无数据库的独立负向复现：从冻结 `backend/main.py:1662` 提取真实 `_stream_with_status_preframe`。外层 `aclose()` 后，内层生成器的 finally 没有执行；显式关闭内层后才执行。探针预期“外层关闭内层”，实际为 false，退出码 1（这是发现缺陷的证据，不是全绿测试）。

代码方向：逐层核对 `状态首帧包装 → chat.stream → stream_with_retry → chain.astream` 的资源所有权，在现有生成器范围内显式关闭自己拥有的内层流，并确保取消不进入业务重试、不泄漏并发位。`contextlib.aclosing` 等标准库方案优先。**仅修外层不能保证所有层已修好**；以真实上游断开日志与回环连接为验收依据，不靠 GC 或动画。

不要引入通用任务调度平台、独立取消服务、全新状态机或换模型。真实云端是否停止/如何计费，本轮没有证据。

### P1：新对话首轮取消导致后续会话分裂

已复现：同一页面先停首轮再正常重问，真实 API/SQLite 分别保存为会话 2 与 3。已有会话 1 没有这个问题。

明确原因：新对话前端的 `conversationId` 起初为 null；后端普通生成出口在末尾才发送 `conversation_id`，前端只在元数据回调同步编号。首轮取消发生在元数据到达之前，重问继续携带 null，后端再次创建会话。主线代码位置为 `backend/main.py` 普通 stream 末尾、前端 `lib/hooks/useChatStream.ts` 元数据回调以及 `lib/hooks/useConversations.ts` 的 newChat。

最小方向：先选定一个唯一的会话建立/确认时点，再做针对性修复。可评估复用已有 POST `/api/conversations`，或服务端提前确认编号；不要并行实现两套创建机制。仅在模型正文前加编号帧还必须检查“前置处理尚未完成就取消”的窗口，不能把它漏掉。DoD：新对话首轮首字前/部分文字后取消，直接重问仍是同一个 conversation_id；取消后重开、失败与重复发送不丢归属。

### P2：Windows 后端关闭阶段访问冲突

两轮后端均非零退出。第二轮 faulthandler 在 `Application shutdown complete` 之后记录 `Windows fatal exception: access violation`，堆栈落在垃圾回收中的 Python 3.11 `asyncio/proactor_events.py` 的 `__repr__`/`__del__`。

现有证据确认“本机关闭阶段异常”，但不能直接定性为 BGE 损坏、数据库损坏、云端故障或产品代码某一行必然致崩溃。先修流与 HTTP 资源收尾，再在本机新副本做少量关闭复验；若仍出现，再拆运行时依赖与 Windows 事件循环。不要直接换事件循环策略、屏蔽异常或升级整套依赖。

此外，第二轮守卫统计为 `open:6`、`subprocess.Popen:1`，具体拒绝来源尚未逐项归因。没有观测到正向控制之外的 Python 网络拒绝，但**不能声称没有意外守卫拒绝**。后续只补脱敏事件类别/调用栈，不放开原 .env、外部写入或子进程权限来消掉统计。

### 已知体验限制：取消后的半截内容只在当前页面

后端当前 `_post_placeholder` 保存“服务暂时无响应，请稍后重试。”，coverage=unknown，不保存半截正文。重开会话会显示占位，原页面的“已停止生成”与未完成正文不再出现。避免误报成“半截已保存”。是否持久化半截是产品选择，建议先不扩展数据库 schema，优先解决以上两个 P1。

## 4. 证据、复现与失败记录

本报告所指文件均在上述独立目录中：

- `reports/verification-plan.md`：执行前冻结范围/判据。
- `evidence/round-02/final-verdict.json`：逐项判定、360 文件 SHA、库/模型副本指纹及精确请求 ID。`candidate_accepted=false`、`full_stage_accepted=false`。
- `evidence/round-02/first-stop-ui.json`、`partial-stop-ui.json`、`new-conversation-stop-ui.json` 与对应页面文本：停止时间及可见状态。
- `evidence/round-02/stub-requests.jsonl`：真实替身请求开始、首片段、完成/断开；只记录合成场景、模型标识与时间，不记录提示全文或鉴权。
- `evidence/round-02/direct-first-verified-client-close.json`：直接后端探针取消时间，与上游请求 ID 对齐。
- `evidence/round-02/after-known-reask-persistence.json`、`after-new-reask-persistence.json`、`final-persistence.json`：真实 API 与隔离 SQLite 交叉证据。
- `evidence/round-02/generator-close-negative.json`：关闭缺口的负向复现结果；`generator_close_probe.py` 是无模型复现脚本。
- `evidence/round-02/history-reopened.png`、`new-reask-page.png`：界面证据。
- `evidence/round-02/read.log`、`cleanup.json`：关闭阶段堆栈、实际退出码、端口空闲证据。
- `evidence/protection-before.json`、`protection-after.json`：主仓/原库/配置/缓存保护。

执行工具：已有 Python 为 `C:/Users/33393/Desktop/fazhi-next-local-20261004-356fb810b3144d158e5dd18b9e276499/joint/venv/Scripts/python.exe`；Node 为 `C:/Program Files/nodejs/node.exe`。本轮没有安装依赖。

本轮实际命令为 Python `-I -B orchestrate.py round-02`（内部跑 pytest、Vitest、Next build、build-id 与真实启动），Python `-I -B probe.py setup/snapshot/direct-first/buffer`，以及 CUA 页面操作。辅助脚本在独立目录顶层。证据均独占创建，**不要在已用目录盲目重跑或删除失败证据**；复跑先复制已冻结输入到新的目录，并核对仍有本轮范围的模型授权。无模型的负向探针也要求使用新证据目录，避免覆盖既有结果。

保留的无效/受限记录：第一轮替身将改写提示里的历史标记当成当前标记，首次首字前点击也过晚，不能作首字前通过证据；第二轮最初两个 API 探针丢弃了 body 迭代器，提前关闭连接，未到上游。修正替身识别、保留迭代器后得到带 `verified` 的有效记录。没有删除旧文件或把“未到上游”当作“上游成功取消”。

独立审阅者未签字。未重跑完整项目门禁/全量后端回归/依赖扫描；未测真实云端、Agent 取消、正常多模型池与独立轻量分支，不把本轮接线结果当法律正确率。

## 5. 下一步建议与授权边界

推荐下一轮仅处理：先显式释放流/HTTP 资源，再修新对话归属，最后复验 Windows 退出与守卫拒绝来源。每项先复现、后最小补丁、再真实回环联调；两项 P1 都不通过就不要合入停止按钮候选。

需要新的产品修复授权；不能把本轮联调“批准”扩成自动修改、提交或合并。正常多模型/轻量分支、真实 rerank/云端计费、半截持久化、其他阶段发布门禁均另列，不混入两个 P1 的修复。推送、真实库写入及部署仍不执行。

本轮结束时三项服务端口空闲，临时新标签页已关闭；不把服务停止等同于后端正常退出。主仓 Git、原数据与配置均保持不变；新增联调报告仍未提交。
