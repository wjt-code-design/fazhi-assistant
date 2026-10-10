# 票 D（独立会话执行）：前端五项残差 + 取消流的真实浏览器验收

发出：2026-10-10 晚，主会话（Owner 已裁定 D 单开会话做）。
**这张票是自足的**：所有指针都写成命令，你跑一遍就知道真假，不必信我的转述。

## 0. 不可变输入（先逐条现量，任一条不符就停下来报 Owner）

| 项 | 值 | 你该跑的命令 |
|---|---|---|
| 候选工作树 | `C:/Users/33393/Desktop/ai-legal-helper/.worktrees/nondeploy-closeout-20261010` | `ls -d <该路径>` |
| 分支 | `codex/nondeploy-closeout-20261010` | `git -C <候选> rev-parse --abbrev-ref HEAD` |
| 发票时 HEAD | `3f605de`（**若已被主会话推进，按 `git log --oneline 0b54396..HEAD` 现量为准并在报告里写 sha**） | `git -C <候选> rev-parse --short HEAD` |
| 运行根（你的脚本/日志/截图/副本库只写这里） | `C:/Users/33393/Desktop/fazhi-nondeploy-closeout-20261010-b4e7a2` | `ls -d <该路径>` |
| 私有 venv | `<运行根>/candidate-envB/Scripts/python.exe`（torch 2.13.0+cpu / SQLAlchemy 2.1.4 / chromadb 0.4.24 / pytest 9.x） | `"$…/python.exe" -V` |
| 被测对象 | `frontend/` 下 **5 只未提交的已跟踪修改**（`app/admin/sections/KnowledgeSection.tsx`、`app/admin/sections/UploadSection.tsx`、`app/chat/page.tsx`、`app/globals.css`、`components/chat/InputBar.tsx`）——里面是前端审查报告 §14 的 6 条修复 **H2/D12/G1/G2/D6/G13** | `git -C <候选> status --porcelain` 应恰好这 5 行 ` M` |
| 交付 | `<运行根>/reports/browser-acceptance.md` + `<运行根>/evidence/browser/**` | — |

## 1. 红线（违反即作废，别"顺手"）

- **候选树只读**：不许改文件、不许 `git add/commit/push/checkout/restore/stash`、不许动 ref、不许 `git config`。唯一允许的写入是 Next/venv 自身产物（`frontend/.next/`、`node_modules/`）。
- **绝不读取或哈希**：`backend/.env` 及任何 `.env*`、`backend/app.db`、`backend/data/`、`backend/chroma_db/`、`backend/media/`、`backend/backups/`、`C:/Users/33393/.cache/huggingface/`。**合成数据自己造**，别从真实库导出。
- **日志与报告里永不出现凭据值**（键名、长度、命中数可以）。
- **不许发真实模型调用**：模型侧只允许 `127.0.0.1` 上的假上游。`HF_HUB_OFFLINE=1`。
- **不碰现有服务**：不跑 `docker` 任何子命令；不 kill 不是你起的进程。本机 8088 由 Docker 容器持有（现量 PID **8636**），另有一条 `[::1]:8088`（PID **2976**）——两只都不许动。**默认不占用也不重启 3021 / 8088**。
- 你的端口用：后端 `127.0.0.1:8111`、前端 standalone `127.0.0.1:3101`、假上游 `127.0.0.1:8399`、CDP `127.0.0.1:9222`。**开跑前逐条 `netstat -ano | grep LISTENING | grep -E ':8111|:3101|:8399|:9222'` 证明未占用**。

## 2. 两条必钉纪律（不钉就等于白做）

1. **禁整后端 mock**。必须跑仓库里真实的 `main:app`，只把**上游模型**换成假服务。理由（在册教训）：mock 整个后端时响应形状取自**前端自己的类型与消费点** ⇒ 凡"后端其实不返回、前端类型却声明了"的字段，这套方法**结构上测不出来**（循环验证）。
2. **绕守卫必须明写**。受守卫页面（`/chat`、`/admin`）在 headless 里没有会话，只能往 `localStorage` 注入用假 `JWT_SECRET` 自签的 token。这属于"绕过被测机制"，**必须进报告的「已知限制」**，否则读者会以为登录流程被验过。

## 3. 起服配方（前两只 agent 都死在这一步，所以写细）

- 落盘全部改指运行根：`DATABASE_URL`（**新建空库**，让 app 自己建表）、`CHROMA_DIR`（空目录）、`QUOTA_DB`（独立文件）。出口位置现量：`quota_store.py:17` 读 `QUOTA_DB`；`rag_chain.py` 一带读 `CHROMA_DIR`。
- **所有** `*_BASE_URL` 指向假上游：`LLM_BASE_URL` / `ZHIPU_BASE_URL` / `DASHSCOPE_BASE_URL` / `RERANK_BASE_URL` / `EMBEDDING_BASE_URL`。再 `EMBEDDING_PROVIDER=local`、`RERANK_ENABLED=false`。
- 坑 1：`main.py` 的 `load_dotenv()` 是默认 `override=False` ⇒ **显式环境变量赢过 `.env`**。跑一遍把**非敏感项**打印出来自证（键名 + 解析到哪个 host:port，不印值）。
- 坑 2：`settings.py` 里 `zhipu_base_url` / `dashscope_base_url` / `embedding_base_url` / `rerank_base_url` / `rerank_native_url` **都带真实官方默认值**（现量见 `backend/settings.py:43/48/194/205/209`）⇒ 只覆盖前五个不够，**`RERANK_NATIVE_URL` 是第六条，漏它就是你自己的出网点**。别把"我没调它"当成"它不会外发"。
- 坑 3：Node 假上游里 `req.on('close')` 在 `'end'` 之后就触发，拿它 clear SSE 的 interval ⇒ 响应头都不发（curl 报 0 字节）。改成顺序 `await` 写。
- 坑 4：开发态前端可能**硬编后端端口、不走同源 rewrite**（现量：`frontend/lib/api.ts:27` 在 `NODE_ENV === "development"` 时回落 `http://localhost:8000`，注释在 `:4`）。所以走生产形状：`npm run build` 后 `node .next/standalone/server.js`；`next.config.js` 有 `output: "standalone"`，且 standalone 的 `BACKEND_URL` 是**构建期冻结**、运行时不再读 ⇒ 必须在 build 前就把后端地址定好。页面空白/401 先怀疑这根轴，别急着判应用缺陷。
- 坑 5：`frontend/.next` 被活进程持锁时，`next build` 会**无报错、无进度地卡死**（本仓在册）。build 前确认没有 `next dev`/`server.js` 在跑。
- 坑 6：Windows 上 venv 的 `python.exe` 是 redirector，**监听端口的是它派生的子进程 PID**；收尾记录所有权时要写**父子两个 PID**。
- 坑 7：**"把 `BACKEND_URL` 指向死端口"不等于断网**。必须在浏览器上下文装请求拦截并**逐连接记 host:port**，证明非回环=0；假上游那边也要记自己收到过几次（两边对账）。

## 4. 看现场用什么（先判通道，别默认它能用）

- 内置浏览器工具（`mcp__browser-use__*`）在本机经常**没有可见视口**：先跑一次
  `evaluate_script: () => ({w: innerWidth, h: innerHeight})`。若 `0x0` ⇒ 一切布局度量都是 0、截图不可得，**改走本机 Edge headless + CDP**：
  `"C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe" --headless=new --remote-debugging-port=9222 --user-data-dir=<运行根>/evidence/browser/profile about:blank`。
- **不需要 puppeteer/playwright**：Node 24 自带全局 `WebSocket`，直连 CDP 即可
  （`/json/version` 取 `webSocketDebuggerUrl` → `Target.createTarget` → `Target.attachToTarget{flatten:true}` → 带 `sessionId` 发
  `Emulation.setDeviceMetricsOverride` / `Page.navigate` / `Runtime.evaluate` / `Page.captureScreenshot`）。
- 度量在页内自采：`getBoundingClientRect` + `getComputedStyle`，比只看截图可靠（触控目标尺寸、`x<0` 离屏、字号、颜色一次拿全）。
- 这条通道**自己也有假阴性面**，两个必须防：① 动态拼类名/同文件内消费会让"某 CSS 没被用到"这类结论变假；② 对比度若按 `background-color` 回溯，会**穿透 `linear-gradient` 取错底色** ⇒ 先算出真实合成底色再比。

## 5. 七条判据（逐条要有读数；设施不可用就登记 BLOCKED 并写归因，**不许换成源码断言冒充交互通过**）

| # | 判据（可证伪的一句话） | 必留证据 |
|---|---|---|
| 1 | 后端、假上游、standalone 前端三条腿都在**回环**上起来，且浏览器侧非回环连接数 **= 0** | PID 父子表 + `netstat` 前后读数 + 拦截日志逐连接 host:port |
| 2 | 合成管理员/消息/图片全部由你自己造；真实库、真实 `.env`、真实 chroma **零触达**（`find <真实目录> -newermt "当天 00:00"` 必须空） | 该 `find` 的原样输出 |
| 3 | **六种知识状态**的徽章都渲染出来，且 正常/长内容/焦点/hover 四态的**计算样式**被量到；文字对比按 WCAG 2.2 AA（普通 ≥4.5:1、大字 ≥3:1），**记录前景/背景/比值三列**，不用观感替代 | 六状态 × 四态矩阵 + 截图路径 |
| 4 | 上传区用 **Tab** 获焦点，**Enter 与 Space 各触发一次**文件选择；可见焦点环存在、Space 不引起页面滚动、关掉选择器后焦点仍可用。只查 `role="button"` 字面量不算 | 键盘事件序列读数 + 焦点元素 id/class + `scrollY` 前后值 |
| 5 | 在 **390 / ≥768 / 1440** 三档量：输入栏字号、按钮尺寸、长文本与附件、`answer` 的 h4、**无水平溢出**（元素 `x<0` 或超出视口都算） | 每档的 JSON 度量 + 截图；不许把 tailwind 类名当排版结果 |
| 6 | 图片能力四腿（`true` / `false` / **缺失** / 健康接口**失败**）× 三种输入（选择 / 拖拽 / 粘贴）。能力明确 `false` 时**不得提交图片**且该腿零真实外发。**缺失目前是 fail-open 形状——只量现状，是否改 fail-closed 归 Owner 裁，你不许改默认业务行为** | 四腿矩阵 + 每腿的请求计数 |
| 7 | 新增会话 → 切换会话 → 取消流 → 快速重发：旧流**不得**跨会话写入、重复持久化或污染新问题；后端 `tests/test_cancel_boundaries.py`、`tests/test_stream_cancellation.py` 现跑并附读数。假流控要能证明"异常/延迟"与"模型没返回"是两回事 | 每个场景的消息/事件表（DB 侧自读你新建的合成库）+ 两条用例的 pytest 读数 |

**D 出口**（执行书原文口径）：四组残差矩阵 + 取消/切换场景有**实际交互**证据、网络越界 **0**。静态那 106 项旧结果只作历史参考。
对比度依据：WCAG 2.2 Contrast (Minimum) `https://www.w3.org/TR/WCAG22/#contrast-minimum`。

## 6. 顺手要判真伪的两条断言（**只判真假，不许顺手修**）

前一只 D agent 在 error 前自述发现两个后端缺陷：(a) `_sse_transport` 少一层 `finally`；(b) `requeued` 会丢事件。
**主会话已现量：这两个符号全仓不存在**（2026-10-10，候选 `3f605de`）：

```bash
C=/c/Users/33393/Desktop/ai-legal-helper/.worktrees/nondeploy-closeout-20261010
git -C "$C" grep -n "_sse_transport\|sse_transport\|requeued"            # 现量：无任何命中（含 backend/frontend/docs/dispatch-output）
```

⇒ 判定不是"待验证的缺陷"，而是**不可复现的名字，按幻觉处置**。这条要写进你的报告，别去码里找它们。

**把那条腿改打在真实流上**。取消/流式的现役面（现量行号）：

| 位置 | 现役形状 | 你要判的问题 |
|---|---|---|
| `frontend/lib/api.ts:168` `new AbortController()`；`:176` `ReadableStreamDefaultReader`；`:226` `res.body.getReader()`；`:230` 读循环 | 前端消费流的地方 | 取消时 reader/controller 两侧是否都有终结路径？异常（假上游 500/半途断流）时 `reader.releaseLock()`/状态复位会不会漏？ |
| `frontend/lib/hooks/useChatStream.ts:22` `activeRequest` ref；`:84` `new AbortController()` | 单请求句柄 | 快速重发/切会话时**旧句柄是否被覆盖而不被 abort**（覆盖即失联＝旧流继续往新会话写） |
| 后端 SSE 出口（`backend/main.py` 里 chat/stream 那条，自己 `git grep -n "text/event-stream"` 定位） | 服务端发流 | 客户端断开后服务端是否继续生成/继续落库 |

这三处都用**假上游可控行为**（正常流 / 延迟 / 中途异常 / 空流）来判，判据仍是 §5 第 7 条（不跨会话写入、不重复持久化、不污染新问题）。
**不要写补丁**——修不修由主会话按证据另开票。

## 7. 报告形状（`<运行根>/reports/browser-acceptance.md`，中文，落 LF）

1. §0 三行汇总：PASS / FAIL / BLOCKED 各几条 + 最贵的未闭合项是谁的事。
2. §1–§7 按上面七条**逐条**：判据 → 现量读数（具体数字/颜色/比值/计数）→ 证据**绝对路径** → 红/绿判定。
3. 六状态 × 四态矩阵、图片四腿矩阵（表格单元里**禁裸 `|`**，竖线一律 `\|`）。
4. 「已知限制」：伪造 token 绕守卫、假上游与真实后端的差、任何没跑到的腿写"未跑"而不是"通过"。
5. 「我自己造出来的仪器问题」：如果某条腿红是**尺子坏**（端口/路径/形状喂错），与真缺陷分开写。这一节主会话会逐条复算。
6. 收尾自证（必须逐字打印，不许概述）：
   `git -C <候选> status --porcelain`（期望仍恰好 5 行 ` M`）；
   `netstat -ano | grep LISTENING | grep -E ':8111|:3101|:8399|:9222'`（期望空，并打印 rc）；
   `find <真实 backend/chroma_db、backend/data、backend/app.db 所在目录> -newermt "当天 00:00"`（期望空）。

## 8. 回来之后（主会话这边会做的事，你不必等）

主会话会**用不同方法**复算你的读数（逐进程/换工具/换目录），因为今天已经两次"同一只坏尺子重跑一遍就盖章 ✅"：
臂 E 的同进程缓存、凭据的键锚点普查。**同法复现不构成独立印证**。
所以你的报告里请保证：每条数字旁边就是那条能产出它的命令，路径写绝对路径。
