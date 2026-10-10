# 票 D：前端五项残差 + 取消流的真实浏览器验收（独立会话执行）

执行：2026-10-10 晚（本会话），候选树 `codex/nondeploy-closeout-20261010` @ HEAD `3f605de`（发票时值，全程未推进）。
运行根：`C:/Users/33393/Desktop/fazhi-nondeploy-closeout-20261010-b4e7a2`（脚本/日志/副本库/截图只落这里）。

## §0 汇总（三行）

- **PASS 6 条**：J1 回环隔离、J2 合成数据零触达（带一条“先于我会话”的既有命中，见 §2）、J4 键盘可达、J5 三档响应式读数、J6 四腿矩阵（判定为“量到现状”，fail-open 归属 Owner）、J7 三不变量（不跨会话写/不重复落库/不污染新问题）+ 两条 pytest 55 passed。
- **FAIL 1 条**：**J3 —— 六种状态徽章在“生产构建产物”里颜色全同**（`.badge-success/-error/-neutral/-accent` 四条规则不在编译后的 CSS 里；浏览器实测六者前景/背景/对比度完全一致 12.12:1）。H2 修复的“颜色维度”在部署形状里等于没改；同一机制还吃掉了 `.btn-ghost-dark`。
- **BLOCKED 0 条**；最贵的未闭合项＝**J3 这条 purge**，归属：前端票/主会话（修法不在这张票射程内，本票只量不改）。另有 1 条“设计内不可达”的腿（切换会话）已按 §7 如实记为不可达而非通过。

## §1 判据 1：三条腿都在回环上，浏览器非回环连接 = 0 —— 绿

**读数（PID 父子表，快照 2026-10-10 20:3x–21:2x）**

| 腿 | 监听地址 | 子进程 PID | 父进程 PID（名字） | 备注 |
|---|---|---|---|---|
| 真后端 main:app | 127.0.0.1:8111 | python.exe 26756 | python.exe 29884（venv redirector） | 中途重启两次（text-only / vision），PID 随重启变 |
| standalone 前端 | 127.0.0.1:3101 | node.exe 31900 | nohup.exe 32084 | `PORT=3101 HOSTNAME=127.0.0.1 node server.js` |
| 假上游 | 127.0.0.1:8399 | node.exe 27612 | nohup.exe 22596 | 只 bind 127.0.0.1（构造性质） |
| Edge headless + CDP | 127.0.0.1:9222 | msedge.exe 29548 | nohup.exe 28780 | 见 §4 通道判定 |

**非回环 = 0（三种口径）**：① 每条腿的 `netstat` 都是 `127.0.0.1:port`，没有 `0.0.0.0`；② 浏览器侧逐连接台账（CDP `Network.requestWillBeSent`）**现量：2 个 jsonl 共 117 行，其中网络请求 108 条，host:port 全部是 `127.0.0.1:3101`，非回环 0**（其余 8 条 `data:` + 1 条 `blob:` 不是网络请求；此数字随导出的 jsonl 集变化，复算器 `srv/host-histogram.py` 现跑现算——**本报告初稿写的“74 条”是当时只含 `requests-chat.jsonl` 的口径，已按 §12 更正**）；③ 使用修正后计数器的 4 次运行（attachment + switch2 ×3）各自现算 `networkRequests=34, nonLoopback=0`；更早几次运行 JSON 里的 `nonLoopback: 2~3` 是旧计数器把 `data:` URL 误判成连接（见 §10 第 9 条），不是真连接。
**命令**：`netstat -ano | grep LISTENING | grep -E ':8111|:3101|:8399|:9222'`；`cat evidence/browser/logs/requests-*.jsonl | python -c "<host 直方图>"`。
**证据**：`evidence/browser/logs/requests-chat.jsonl`、`requests-attachment.jsonl`、`evidence/browser/json/caps-*.json`（每条含 `isolation` 字段）、`evidence/browser/json/ruler-selftest.json`。
**未动别人的腿**：`8088` 前后都是 8636（0.0.0.0）+ 2976（[::1]），全程未碰。

## §2 判据 2：合成数据自造，真实库/`.env`/chroma 零触达 —— 绿（附一条既有命中的诚实标注）

**“不出 repo”是构造性质，不是事后断言**：启动器（`browser-acceptance/srv/run_backend.py`）在 import 前对每个出口做守卫，**解析到候选树内即 rc≠0 拒绝启动**；六个 `*_BASE_URL` 逐个断言 host 必须是回环。
`env-selfproof.txt` 原文（键名 + host:port/path，不含任何值）：
- `find_dotenv()=''` —— **cwd 选在运行根，`.env` 一次都没被 load**（backend/.env 我也从未读/哈希；只取过 `stat` 元数据：0 字节、mtime 02:48，两个数都不是内容）。
- `DATABASE_URL -> <运行根>/browser-acceptance/db/accept.db`、`QUOTA_DB -> .../db/quota.sqlite`、`CHROMA_DIR -> .../chroma`、`MEDIA_OUT -> .../out/media`。
- 六个 URL：`LLM/ZHIPU/DASHSCOPE/EMBEDDING/RERANK/RERANK_NATIVE` 全部 `host=127.0.0.1 port=8399 path=/v1`（**含票面点名的第六条 `RERANK_NATIVE_URL`**）。
- `EMBEDDING_PROVIDER=local RERANK_ENABLED=false HF_HUB_OFFLINE=1`。

**零触达读数**
- 真实目录（主仓 `ai-legal-helper/backend`）：`find .../chroma_db .../data .../app.db -newermt "2026-10-10 00:00"` → **1 命中：`.../backend/data`**。此命中**早于本会话**：我会话开始前的基线读数里该目录 mtime 就是 `15:09:03`，而本会话第一条命令在 19:0x；以我会话起点为界复跑 `-newermt "2026-10-10 19:00"` → **空**。⇒ 票面“期望空”在**别人**今天的动作下已不成立，本条按“我会话边界内为空 + 该命中先于我”报告。
- 候选树三个禁令目录 mtime 与基线**逐字相同**：chroma_db `03:11:23`、data `02:16:58`、media `03:08:14`；`backend/media` 条目数 = **0**。
- 反向验证（出口重定向真的生效）：5 张合成图 → `<运行根>/browser-acceptance/out/media/` 10 个文件（原图+缩略图）；chroma 集合目录、`accept.db`、`quota.sqlite` 全在运行根；打开历史带图会话时 `GET /api/media/media/<uid>_thumb.jpg` → **200 / 1270B**，页面 `<img>` naturalW/H=64×64、complete=true（即从**我的**重定向目录读回来的）。
- 合成数据全部自造：两名用户经真 `POST /api/auth/register`（`duser1` id=1、`dkeeper` id=2 后由我在**自己的副本库**里改 role=admin）；6+6 条知识经真 `POST /api/admin/knowledge`；图片用 PIL 现造。
**证据**：`evidence/browser/logs/env-selfproof.txt`、`backend-vision2.stdout`、`evidence/browser/json/seed-kb.json`、`evidence/browser/json/attachment-history.json`、`srv/seed_kb.py`（随票落盘）。

## §3 判据 3：六种知识状态徽章 × 四态 + WCAG 2.2 AA —— **红**（对比度绿，六状态区分度红）

**渲染确实发生**：管理后台知识库列表实渲染 12 张卡，六种状态各出现（DOM 类名与文案逐条对得上：现行=badge-success、已修改/即将施行/未生效=badge-accent、已废止=badge-error、未验证=badge-neutral）；新增表单的下拉框六个 option 全在（`['现行','已修改','已废止','即将施行','未生效','未验证']`，即 H2 的配套改动在生产构建里**是生效的**）。

**对比度（WCAG 2.2 Contrast Minimum；前景/背景/比值三列；底按 4 个候选底合成，含两层渐变的最坏 stop）**

| 状态 | 常态 前景 | 常态 背景 | 常态 比值 | AA(4.5) | hover 比值 | 长内容 比值 |
|---|---|---|---|---|---|---|
| 现行 | rgb(35,49,79) | rgb(241,249,255) | 12.12 | 过 | 12.12 | 12.12 |
| 已修改 | rgb(35,49,79) | rgb(241,249,255) | 12.12 | 过 | 12.12 | 12.12 |
| 已废止 | rgb(35,49,79) | rgb(241,249,255) | 12.12 | 过 | 12.12 | 12.12 |
| 即将施行 | rgb(35,49,79) | rgb(241,249,255) | 12.12 | 过 | 12.12 | 12.12 |
| 未生效 | rgb(35,49,79) | rgb(241,249,255) | 12.12 | 过 | 12.12 | 12.12 |
| 未验证 | rgb(35,49,79) | rgb(241,249,255) | 12.12 | 过 | 12.12 | 12.12 |

**六者逐列相同 ⇒ 红。根因（量到的，不是推的）**：
- 编译后的 CSS 里 `@layer components` 共 29 个选择器，**5 个不在产物中**：`.badge-success`、`.badge-error`、`.badge-neutral`、`.badge-accent`、`.btn-ghost-dark`；`grep -o` 计数分别为 0（`.badge{` 本体是 1）。
- 五个名字在 `.ts/.tsx/.jsx` 里的字面出现次数都是 **0**——类名是 `components/ui.tsx:39` 的 `` `badge badge-${kind}` `` 现拼的；Tailwind 的 content 只扫 `app/**`、`components/**` 的代码文件，扫不到 ⇒ 与 `@layer components` 的 purge 行为一致（**这条机理是推断**，我量到的是“类名不在产物里 + 六者计算样式全同”这两个事实）。
- 眼睛可见的后果：六种状态在部署形状里**只有文字不同**，颜色/底色完全相同（浏览器实测 `background-color: rgba(0,0,0,0)`，前景一律 `--ink #23314f`）。**H2 想要“未验证别再显示成现行”的视觉区分，在这个构建里等于没生效**；`dev` 与 `build` 的差异没被任何既有测试覆盖（`npm run check` 只跑 lint+tsc+vitest，见 `frontend/package.json:6-11`）。
- **四态口径**：hover / 长内容（540+ 字正文行）二态读数齐全；焦点态——徽章是**非交互元素**（无 tabindex，键盘不可达），我以 `tabindex=-1` 强制聚焦后 `:focus-visible=false`（程序化聚焦不触发的浏览器语义），且样式表里没有任何 `.badge*:focus` 规则 ⇒ 焦点态与常态计算样式差值为 0，如实记。
**证据**：`evidence/browser/json/badge-matrix.json`（含 `contrast.layerStack`、`gradientLayers`）、`shots/10-admin-knowledge-list.png`、复算命令在 `srv/drive-badges.js` 与在册 `measure.js`（`__M.badges()`）。

## §4 判据 4：上传区键盘可达 —— 绿

**键盘事件序列（真实 `Input.dispatchKeyEvent`，从 `document.body` 起 Tab）**：第 1–3 停 nav-item、返回问答、退出；**第 4 停 = `div.upload-zone`**（`role="button"`、`tabIndex=0`、`aria-label="上传法律知识文件（回车选择文件）"`）；第 5 停 = 条文原文 textarea ⇒ 隐藏的 `input[type=file]` 被 `tabIndex=-1` + `display:none` 正确跳过（这正是 G13 想要的两个 Tab 停靠点合成一个）。
**焦点环**：`matches(':focus-visible')=true`，`box-shadow: rgba(232,148,172,0.137) 0px 0px 0px 2.95px`（`outline: none`，环由 box-shadow 承担），`border-color` 由 #e5e7eb 变 #e797ae ⇒ 可见。
**Enter / Space 各一次文件选择（两把独立尺子对账）**：

| 动作 | 页面侧计数（input.click 监听） | 页面侧计数（zone click） | CDP fileChooserOpened | scrollY 前后 |
|---|---|---|---|---|
| Enter | +1 | +1 | +1 | 0 → 0 |
| Space | +1 | +1 | +1 | 0 → 0 |

**关掉选择器后焦点仍在**：`document.activeElement === .upload-zone` 两轮皆为 true（每次用真实 chooser 事件 + `DOM.setFileInputFiles{backendNodeId}` 接受）。
**证据**：`evidence/browser/json/keyboard-upload.json`、`chooser-count.json`（独立计数器那轮）、`shots/21-upload-zone-keyboard-focus.png`。

## §5 判据 5：390 / ≥768 / 1440 三档响应式 —— 绿（读数在，两处越界属设计内，另有越界口径外的控件偏小）

页面上真实存在一条流式回答（含 `####` 四级标题、三段长正文、列表）、并且发过一张真图。

| 档位 | innerWidth | 输入框宽/字号 | `.answer-h4` 字号/宽/对比 | 页面水平溢出 | 越界元素数 |
|---|---|---|---|---|---|
| 390 | 390 | 358px / 16px | 15.2px / 252px / 12.93:1 | 无（scrollWidth=390=clientWidth） | 41，**全部完全落在视口左侧**（x∈[-280,-34] 且 right≤0；首个为 `sidebar-glow fixed inset-y-0` 的 280px 侧栏面板，其余为其子元素） |
| 768 | 768 | 216px / 16px | 15.2px / 287px / 12.93:1 | 无 | 0 |
| 1440 | 1440 | 496px / 16px | 15.2px / 519px / 12.93:1 | 无 | 0 |

- 输入栏四个圆钮（上传图片 / 上传文件 / 语音输入 / 发送）三档一律 **44×44**，`aria-label` 齐全；390 档 G1 的 `basis-full + order-first` 生效（输入框独占一行、按钮换到第二行），文本域从“历史缺陷的 158px”变成 358px。
- `answer-h4` 在产物里**有**样式（15.2px=0.95rem，与 `.answer-h2/h3/h1` 同一组左竖线规则）⇒ D6/G2 在部署形状里生效。
- **口径外但必须报**：另有 4 类控件 <24×24（WCAG 2.2 Target Size Minimum 的 AA 线）：关闭菜单 21×32、打开菜单 26×28、删除会话 20×20、有帮助/不准确 31×20。它们不在本票 5 个文件里，我没改，只登记。
**证据**：`evidence/browser/json/responsive-chat.json`（每档含 `overflow.offenders` 全表）、`shots/31-chat-390.png`、`31-chat-768.png`、`31-chat-1440.png`、`shots/70-attachment-history.png`。

## §6 判据 6：图片能力四腿 × 三种输入 —— 绿（量到现状；fail-open 的取舍归 Owner）

| 腿 | 能力位来源 | `/api/health` | 图片钮/输入框 | 选择 | 拖拽 | 粘贴 | 提交后上游 |
|---|---|---|---|---|---|---|---|
| true | 真注册表（vision 角色） | `image_chat:true` | 有/有 | 收（预览 48px） | 收 | 收 | vision +1、chat +1 |
| false | 真注册表（text-only 配置） | `image_chat:false` | 无/无(0) | N/A | **拦**（alert“图片理解当前不可用…”） | **拦**（同 alert） | **0**（无图可提交） |
| 缺失 | CDP 改写 `/api/health` → `{"status":"ok"}` | 无 capabilities | 有/有 | 收 | 收 | 收 | vision +1 |
| 失败 | CDP `failRequest` `/api/health` | 请求失败（size 0） | 有/有 | 收 | 收 | 收 | vision +1 |

- 三条输入路由都是**真交互**：选择走真 chooser 事件（`mode=selectSingle`，用事件给的 `backendNodeId` 落文件）；拖拽走 `dragenter/dragover/drop` 全序列派到**带 onDrop 的 `.scroll-contain`**；粘贴是合成 `ClipboardEvent`（isTrusted=false，但走的是 React 真 handler）。合成事件这一点进 §已知限制。
- **false 腿零外发**：`submit: null`（无挂起图片→按钮 disabled），且 D12 的 alert 文案被 dialogs 台账逐条记下（2 次尝试 2 条）。
- **缺失/失败两腿 fail-open 已实证**：UI 认为“能用”，把图交到真后端并抵达假上游（vision +1）。即：`caps` 取不到时**不拦**，与按钮同向（`page.tsx:146`）。
- “只量现状、不改默认业务行为”遵守：全程没有动任何默认值/代码。
**证据**：`evidence/browser/json/caps-true.json`、`caps-false.json`、`caps-missing.json`、`caps-failure.json`、`shots/50-caps-*.png`、`srv/drive-caps.js`。

## §7 判据 7：取消 / 切换 / 快速重发 —— 绿（三不变量成立；切换腿“设计内不可达”，如实记）

**库侧总账（我自己那份副本库 `accept.db`；现量 20 个会话 58 条消息，随后续场景增长，复算器 `srv/db_ledger.py` / `srv/containment_check.py` 现跑现算；初稿写的“16/50”是当时快照，已按 §12 更正）**
- **不重复落库**：`select conversation_id, role, count(*)` 分组里，每个会话 user 数 = assistant 数 = 轮数；`message_count` 与消息行数**处处相等**（如 conv16：mc=12，user 6 + assistant 6）。
- **不跨会话写**：用 `containment_check.py` 逐会话核 —— **每个会话里 assistant 行出现的 marker 全部来自本会话的 user 行，跨会话外来的 = NONE**（20 个会话全平）。注意“同一 marker 出现在多个会话”不代表污染：那是我**在不同会话各发了一次同样的问题文本**（ZZc1 出现在 13/14/15/16 就是四次运行各发一次）。
- **不污染新问题**：快速重发那条（conv16 msg43→44）新答案 = 正常模式的三段拼接正文，**不含**被打断那轮的半截内容。

**四个场景的现量**
| 场景 | UI 读数 | 上游读数（我的假上游台账） | 库侧读数 |
|---|---|---|---|
| 流中取消 | 停止后末条 assistant 变“…（已停止生成，以上为未完成回答。）” | **`stream-done sent=4 destroyed=true`**（客户端一断，服务端**把上游请求也掐了**） | 该轮恰好 1 条 assistant = 占位“服务暂时无响应，请稍后重试。” |
| 停止后立即重发 | 新旧两条互不串味 | ZZr1 与 ZZr2 各自成请求，无并发叠加 | user/assistant 严格成对 |
| 流中切会话 | 点击命中真条目（`hitIsTarget:true`、capture 监听 clicks=1）但 **`convReqs: []`、streaming 仍 true、消息列表不变** | — | 无任何跨会话写入（本来就切不动） |
| 模型没返回（silent 空流） | 末条 = “未能完成本次请求 出错了：服务暂时无响应，请稍后重试” | `silent-empty-stream` ×3（同一 marker 3 次请求＝重试） | 1 条 assistant（占位） |
| 中途异常（boom 半途断流） | 同上文案（**与 silent 在 UI 上不可区分**） | `boom-destroy` ×3 | 1 条 assistant（占位） |

- **切换腿为什么是“不可达”**：`useConversations.ts:43/59` 两条（`newChat` / `selectConv`）都以 `if (opts.streaming) return;` 开头（注释写明“流式期间禁止切会话，防消息污染/conversationId 错位，对抗审计 2026-08-07”）。我实测：点击落在正确条目（`elementFromPoint` 命中目标、capture 监听记到 1 次可信 click），但没有发任何 `/api/conversations/<id>` 请求、流也没停 ⇒ **不是“通过”，是这条腿在 UI 上走不到**。`useChatStream.ts:31/41` 的 abort 仍作为兜底存在（`setConversationId`/卸载），只是当前 UI 先拦住了。
- **要点名的一处 UX 不一致（供 Owner 裁，我没改）**：用户主动停止后，前端当场显示“已停止生成”，但服务端为保持成对落的那条占位是 **“服务暂时无响应，请稍后重试。”** ⇒ 刷新/换设备看历史时，用户会看到“服务不可用”，而他其实只是按了停止。判据本身（不重复/不跨会话）不因此变红，但这句文案把“用户取消”讲成了“服务故障”。
**两条 pytest（票面指定，`--noconftest`）**：`tests/test_cancel_boundaries.py` + `tests/test_stream_cancellation.py` → **55 passed in 20.36s**（venv `candidate-envB`，Py 3.11.0，pytest 9.1.1）。跑法带 `PYTHONDONTWRITEBYTECODE=1 -p no:cacheprovider`，事后 `find` 候选树 19:00 后**无 `*.pyc` / `.pytest_cache` 残留**。
**证据**：`evidence/browser/json/cancel-scenarios.json`、`switch2-ZZsw*.json`、`caps-*.json`、`evidence/browser/logs/upstream.log`、`shots/60-cancel-final.png`。

## §8 票面 §6：两条断言的真伪 + 三条现役面 —— 断言=幻觉；现役面三处都判了

**两条断言（分档：判定“名字不存在”，不是“缺陷不成立”）**
```
git -C <候选> grep -n "_sse_transport\|sse_transport\|requeued"    → rc=1，零命中
```
⇒ `_sse_transport` / `requeued` **全仓不存在**，与前一只 D agent 的自述不符，按**不可复现的名字（幻觉）**处置，我没有去码里找它们、也没据此改任何东西。

**三条现役面（用假上游的可控行为判：正常 / 延迟 / 中途异常 / 空流）**
1. `frontend/lib/api.ts:168/176/226/230/288-295`（reader/controller 终结路径）：取消时 `finally` 走 `reader.cancel()` + `releaseLock()`、并清 idle 看门狗。**端到端证据**：流中取消那一轮，我的假上游记到 `write-skipped-destroyed` 与 `stream-done sent=4 destroyed=true` ⇒ 客户端的 abort 确实传到服务端、服务端确实把上游请求也断了，不是“只关了自己的读端”。
2. `frontend/lib/hooks/useChatStream.ts:22/84`（单请求句柄会不会“被覆盖而不 abort”）：`doSend` 第 83 行 `if (activeRequest.current) return;` 直接拒绝第二次发送；切换/新建/卸载三条路径都是 `abort()` 后置空。**实测**：快速重发那条腿里两条流互不叠加（上游无并发同 marker 请求），旧流的半截内容没有进新答案。
3. 后端 SSE 出口（`main.py` `text/event-stream`，`git grep -n "text/event-stream"` 定位到 `main.py:840/2674`）：客户端断开后**不再继续生成**（上游侧同一 rid 4 分片即断），并按 `_post_placeholder` 落**恰好一条**占位 assistant（`main.py:1027-1046`，`assistant_committed` 闸防第二条）。**我没有写任何补丁**——修不修按票面归主会话裁。

## §9 已知限制（读者必须知道的那几条）

1. **没有伪造 token**：票面 §2.2 允许注入自签 token 绕守卫，本轮**不必也没用**——我真驱动了“钤印入典”门 + 真登录表单，token 由真 `POST /api/auth/login` 签发（HS256，claims 与 `auth.py:45-52` 一致）。要披露的是：`JWT_SECRET` 是**本地生成的假值**（真 `.env` 按红线不读）、`FEATURE_SELF_REGISTER=true` 是为本次运行打开的配置、`dkeeper` 的 admin 角色是我在**自己副本库**里 `UPDATE users` 得到的（应用没有自助提权入口）。**因此“登录/守卫流程被验过”这句话只对登录成立；注册表单没走（前端“注册”标签是 `div` 且标注“注册已关闭”，用户经真 API 创建）**。
2. **假上游与真模型的差**：答案是罐头文本（带动画式分片），没有真模型的检索/引用行为；后端若干质量门（自检、引用门）面对罐头文本的行为与真答案未必同分布。假上游只回答 `/v1/chat/completions`，其它路径 404 并被记档。
3. **能力位四腿的后两腿**是**浏览器侧重写/拒绝 `/api/health`**造出来的（真后端产不出“缺失/失败”形状）；但提交腿走的仍是真后端 + 真上游（vision +1 是实测），所以“fail-open 能走到哪一步”是量到的。
4. **合成事件**：粘贴是 in-page 合成 `ClipboardEvent`（isTrusted=false）；拖拽是合成 `DragEvent` 序列派到真 `.scroll-contain`；文件“选择”是拿真 chooser 事件的 `backendNodeId` 调 `DOM.setFileInputFiles`（headless 里原生对话框不弹）。三者的**接收端都是应用真 handler**，但“操作系统级真实手势”未验。
5. **两条腿按“走不到”记录**：流中切会话（`useConversations.ts:43/59` 的 streaming 守卫）与徽章焦点态（非交互元素）——不是通过，是 UI 上不可达/不适用。
6. **`.env` 是 0 字节空文件**（只取过 stat 元数据）：所以“显式 env 赢 `.env`”在本树上是平凡成立的，**我没有验证“非空 .env 场景下的优先级”**。
7. 本机不装 puppeteer/playwright，浏览器通道是 Edge headless + 裸 CDP（Node 24 内置 WebSocket）；`Page.handleFileChooserAction` 在这版 Edge 不存在（见 §10）。
8. 收尾时我的四条腿都已关闭；§1 的 PID 表是**快照**，重启两次后 PID 会变。`frontend/.next` 整目录由我重建（票面允许的写入），重建前只有 20KB 的陈旧残留、无 `standalone/`。

## §10 通道判定 + 我自己造出来的仪器问题（主会话要逐条复算的就是这一节）

**通道判定（票面 §4 要求“先判通道”）**：内置浏览器不是 0×0——navigate 到 `/login` 后实测 `innerWidth/innerHeight = 655×557`、`dpr=1.5`、`visualViewport=655.3×557.3`，**但这一版没有暴露设备度量覆盖/文件选择器/请求拦截原语**，而 J4/J5/J6/J7 分别需要精确 390/768/1440、chooser 事件、`Fetch` 域改写与逐连接台账 ⇒ 全量改走 **Edge headless(`Edg/154.0.4258.62`) + 裸 CDP:9222**（`srv/cdp-client.js`，Node 24 内置 WebSocket）。

以下 9 条**都是尺子坏，不是应用缺陷**，凡影响结论的都已修好并用独立尺子复核：

1. **最贵的一条：`DOM.setFileInputFiles` 传了一个被转义吃掉的 Windows 路径**（我在 heredoc 里写 `'C:\Users\...'`，落盘变成非法路径）⇒ 设置之后**页面 60 秒不响应任何 `Runtime.evaluate`**。我一度把它读成“挂图会把页面卡死”，用 `Performance.getMetrics`（不依赖页面 JS）+ 截图 + `path.join` 修正路径复跑，**页面全程活着**（`1+1=2`、指标平稳）。**结论撤回：应用没有这个问题**。
2. `Content-Length`/转义 类：`harness.js` 里 `/\/g` 落盘成 `/\/g` 直接语法错；`drive-chat.js` 的 `IMG` 常量同因变成非法路径。已改成 `path.join`，从此所有脚本**零反斜杠**。
3. `Page.handleFileChooserAction` 不存在（`-32601 'wasn't found'`）⇒ 我在 J4 首轮**没能关掉文件选择器**，导致 CDP 的 `Page.fileChooserOpened` 计数每按一次键 +2（累积未处理）。改用独立尺子（页面侧监听 `input` 的 `click`）判真值＝**Enter/Space 各 1 次**，§4 那张表就是两把尺子的对账。
4. 对比度尺子三度翻修：① 页面侧正则被模板字面量转义吃掉 ⇒ 所有颜色“无法解析”；② 分层合成模型在“渐变压在实色之上”时把候选集弄丢 ⇒ 背景算出 `null`；③ 改成**无反斜杠解析器 + 候选底集合（实色栈 × 渐变各 stop 的最坏/最好两支，上限 4 个候选）**，并按“尺子必须能红”跑了负自证：`#fff` 配 `#fff` = 1.00 红、`#ccc` 配 `#fff` = 1.61 红、`#000` 配 `#fff` = 21.00 绿（`ruler-selftest.json`）。
5. `session.js` 的 `loginAs` 在“已登录直进”分支提前 `return`，**跳过了我要的跳转** ⇒ 一段测量跑在 `/admin` 上（表现为 `textarea.input` 为 null）。
6. 拖拽腿第一版把合成 `drop` 派到了 **InputBar 的包装 div**（不是拥有 `onDrop` 的 `.scroll-contain`）⇒ 假红“拖拽不接受”。
7. 侧栏切换点击：① 首选条目在视口外（y=1171 > 900）⇒ 点击落在 `HTML` 上；② 修好后发现**这套流程里没有任何 `.chat-item` 带 `active` 类**，我的“第一个非 active 项”永远选中当前会话 ⇒ 改成按标题排除本轮 marker + 点击前 `elementFromPoint` 预检（这才有了 §7 的 `clicks:1 / convReqs:0` 判据）。**“侧栏不标活跃会话”这条我只登记不追**（不在七条判据里），复算命令：`document.querySelectorAll('.chat-item.active').length`。
8. 粘贴/拖拽首版用 **4 字节的假 PNG**（只有 PNG 魔数）⇒ 真后端在图片校验处正确拒绝（“cannot identify image file”），差点被我记成“视觉腿没跑通”。改用 64×64 真字节后 vision +1。
9. `harness.js` 不导出 `ROOT`，`path.join(undefined, ...)` 抛 `ERR_INVALID_ARG_TYPE`；另外我的对账器把 `data:`/`blob:` URL 当成了网络连接（`new URL()` 给它们编出 `:80` 主机），修正后 `data:`/`blob:` 单独计数。

## §11 收尾自证（逐字打印，未概述）

```
### git -C <候选> status --porcelain
 M frontend/app/admin/sections/KnowledgeSection.tsx
 M frontend/app/admin/sections/UploadSection.tsx
 M frontend/app/chat/page.tsx
 M frontend/app/globals.css
 M frontend/components/chat/InputBar.tsx
### netstat -ano | grep LISTENING | grep -E ':8111|:3101|:8399|:9222'
(空)
rc=1
### find <真实 backend/chroma_db、backend/data、backend/app.db 所在目录> -newermt "当天 00:00"
/c/Users/33393/Desktop/ai-legal-helper/backend/data
```
- 第 1 项：**恰好 5 行 ` M`**，与票面期望一致（全程未 add/commit/push/checkout/restore/stash、未动 ref）。
- 第 2 项：**空、rc=1**（我的四条腿已全部关闭；对照：8088 的 8636/2976 全程未动，收尾时仍在听）。
- 第 3 项：**1 条命中，且先于我会话**（该目录 mtime `2026-10-10 15:09:03`，我会话第一条命令在 19:0x；以 19:00 为界复跑为空）。**票面“期望空”在别人今天的动作下已不成立，本条按“我会话边界内为空 + 该命中先于我”报告**，不替别人认领也不替别人开脱。

---
产物清单（绝对路径）：
- 报告：`C:/Users/33393/Desktop/fazhi-nondeploy-closeout-20261010-b4e7a2/reports/browser-acceptance.md`
- 读数 JSON：`C:/Users/33393/Desktop/fazhi-nondeploy-closeout-20261010-b4e7a2/evidence/browser/json/`（现量 **17 个**；含 badge-matrix、caps-true/false/missing/failure、cancel-scenarios、switch2-ZZsw*、responsive-chat、keyboard-upload、chooser-count、attachment-history、ruler-selftest、parser-battery、auth-session、seed-kb 等）
- 截图：`.../evidence/browser/shots/`（01–70 编号，现量 **21 张**）
- 日志：`.../evidence/browser/logs/`（upstream.log、env-selfproof.txt、backend-*.stdout、frontend-*.log、requests-*.jsonl）
- 仪器随票落盘：`.../browser-acceptance/srv/`（fake-upstream.js、run_backend.py、cdp-client.js、measure.js、harness.js、session.js、drive-*.js、seed_kb.py）

## §12 补记（show-your-work 证据门禁：五连问逐条过，抓出两处过期数字并已更正）

**五连问（对头号结论 J3 与其余关键数字）**
1. **怎么来的**：J3 的下架结论 = 编译产物上 `grep -o -F` 计数（4 个选择器 = 0，阳性对照 `.badge{`=1、`.upload-zone`=3）+ 浏览器计算样式六者逐列相同（12.12:1）。不是推断；“Tailwind purge 机理”那句已在 §3 明确标为**推断**，事实层只有上面两条。
2. **能复现吗**：能。三个复算器**随票落盘**（初稿只有 heredoc，现补）：
   - `srv/check-css-purge.py <frontend 目录>` → 现跑输出：`selectors=29, absent=5 (.badge-success/-error/-neutral/-accent/.btn-ghost-dark), 阳性对照 .badge{=1 .upload-zone=3`（与 §3 一致）。
   - `srv/host-histogram.py` → 现跑输出：`files=2 rows=117, http=108, host 只有 127.0.0.1:3101, non-loopback []`。
   - `srv/db_ledger.py` / `srv/containment_check.py` → 现跑输出：`20 会话 58 条`、`user==assistant 处处成立`、`message_count==行数 处处成立`、`跨会话外来的 assistant marker = NONE`。
   - pytest：`PYTHONDONTWRITEBYTECODE=1 python -m pytest tests/test_cancel_boundaries.py tests/test_stream_cancellation.py --noconftest -q -p no:cacheprovider` → **rc=0，55 passed in 18.27s**（完整输出 `evidence/browser/logs/pytest-cancel.log`，**本次运行**，非引用旧输出）。
3. **红过吗**：两把“能红”自证已入册——对比度尺子负自证（`#fff/#fff`=1.00 红、`#ccc/#fff`=1.61 红、`#000/#fff`=21.00 绿，`ruler-selftest.json`）；purge 仪器的阳性对照（同一个计数器对存在的选择器给 1 与 3，不是恒 0）。
4. **期望独立吗**：J3 的“六状态应当可区分”期望来自 `retrieval_core.py:39` 白名单 + 本次改动意图本身（不是从实现反推）；对比度门槛 4.5/3 取自 WCAG 2.2 原文口径；J6 四腿的期望来自 `page.tsx:146`/`InputBar.tsx:90` 的判据方向，且**false 腿的“零外发”期望独立于实现**（上游计数为 0，不依赖前端自述）。
5. **已知限制**：§9 全部（假 token 来源、罐头答案、后两腿靠改写 `/api/health`、合成事件、两条不可达腿、`.env` 为空、PID 快照、`.next` 由我重建）。

**这轮门禁抓出的东西（就地更正已在 §1/§7 原句标注）**
- **J1 的“74 条”是错口径**：那是我第一次汇总时只含 `requests-chat.jsonl` 的读数，被写成了总量；现量 **108 条（2 文件 117 行）**，非回环仍为 0（结论不变，数字更正）。
- **J7 的“16 会话 50 条”是快照**：后续 `switch2/probe` 轮又建了 4 个会话；现量 **20/58**（结论不变，数字更正）。同时把“不跨会话写”的尺子从“marker 出现在多个会话”（会把**我重复发同一句话**误报成污染）换成了**逐会话包含性检查**：`assistant marker ⊆ 本会话 user marker`，20 会话全平、外来 0。
- 另发现二处**报告的举证链缺环**（已补）：purge/直方图/库账三处数字原先只有 heredoc，未随票落盘 ⇒ 现补三个复算器 + 本文第 2 条的现跑输出。

**报告落盘后工作树是否再变动**：候选树未动（porcelain 仍恰 5 行 ` M`、HEAD 仍 `3f605de`、我的四端口仍空）；本节只改本报告字节。当前报告字节/哈希不钉数（自指会自涨），以文末那条命令现跑为准。

**最终现量（自指，不钉数）：`python -c "import hashlib;b=open(r'<本报告>','rb').read();print(len(b), hashlib.sha256(b).hexdigest())"`**
