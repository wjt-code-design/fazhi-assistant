# 法智前端改造 · 最终执行书

> 签发：2026-09-15 22:35 ｜ 执行者：前端实现助手 ｜ 验收者：审计方（本方案签发人）
> 基线 commit：**`f0f9cc9`**（fix(frontend): 修 5 项审计确认缺陷…）。开工前先 `git log --oneline -1` 确认在此基线或其之后，且 `git status --porcelain -- frontend/` 为空。
> 方案依据：`docs/frontend-review-refactor-plan-20260915.md`（§4 决策已由用户拍板，见 §1.2）。本执行书自包含，不需要读历史对话。

---

## 0. 执行者须知（先读）

1. **范围红线**：只改 `frontend/`。**严禁**触碰 `backend/`、`dispatch-output/`（尤其 `dispatch-output/agent-quality-20260911/` 的 3 个文件有另一条工作线的未提交修改）、`data/`、根 `.env`。
2. **提交纪律**：每个任务（T0.1…T2.5）至少一个独立 commit，格式 `<type>(frontend): <中文描述>`，type ∈ feat/refactor/chore/test。**禁止**一次性大提交；禁止 `git add -A`（用显式路径）。
3. **每步完成判据**：`npx tsc --noEmit` 0 错 + `npm run build` 成功 + §6 手测清单相关项通过，才允许 commit。
4. **禁止全仓 format**：Prettier 只添加配置与 check 脚本，**不运行 `--write` 于既有文件**（否则产生海量无关 diff，直接判验收失败）。
5. 本机 Bash 环境缺 `head/tail/ls/cat`，长命令用 `node`/`npx` 或显式路径；npm 走默认源即可（node_modules 已装好）。

## 1. 基线与已定决策

### 1.1 基线状态
- 12 个源文件 / ~4729 行：`app/{layout,page,SWRegister}.tsx`、`app/globals.css`(1021)、`app/chat/page.tsx`(1465)、`app/admin/page.tsx`(893)、`app/login/page.tsx`、`components/{ui,LawCard}.tsx`、`lib/{api,auth,annotate,recorder,scope,usePointerGlow}.ts(x)`、`public/sw.js`。
- 已修（勿重做）：`.btn-primary`/`.logo-seal` 文字改 `var(--ink)`；`.btn-ghost`/`.btn-outline` 已定义；`fbDone/corrFor/corrText` 三处切会话重置；sources 折叠渲染（chat 页 AI 气泡下方 `<details>`）。

### 1.2 用户已拍板的决策（不得更改）
| 决策 | 结论 |
|---|---|
| 范围 | 批次 0+1+2（护栏 → 速赢+SW → 结构重构）；批次 3/4 不做 |
| 测试 | 只测纯函数（Vitest）：`annotate.ts`、`scope.ts`、api.ts 的 SSE 帧解析 |
| Enter 键 | 改为 **Enter 发送 / Shift+Enter 换行**，placeholder 标注提示 |
| SW 修法 | **构建号版本化**：install 时 fetch `/_next/static/BUILD_ID` 生成缓存名，零新依赖 |

---

## 2. 批次 0 · 护栏（T0.1–T0.3）

### T0.1 ESLint
- 装：`npm i -D eslint eslint-config-next@14.1.0`
- 建 `.eslintrc.json`：`{ "extends": ["next/core-web-vitals"] }`（不要用 `next/typescript` 以避免与 `strict` 重复报错噪音，如确需可加）
- `package.json` scripts 增加 `"lint": "next lint --dir app --dir components --dir lib"`
- **注意**：先写好 `.eslintrc.json` 再跑 lint，避免 `next lint` 交互式提问卡住。
- 完成判据：`npm run lint` 可运行；对**既有代码**允许存在 warning，但 `--max-warnings 200` 内不失败；修复所有 **error**（预计主要是 `react-hooks/exhaustive-deps`，修不动的加行内 `// eslint-disable-next-line` 并留注释理由）。

### T0.2 Prettier
- 装：`npm i -D prettier`
- 建 `.prettierrc`：`{ "printWidth": 100, "singleQuote": false, "semi": true, "trailingComma": "es5" }`（对齐现有风格，**不要**用 no-semi/单引号，否则全仓冲突）
- scripts 增加 `"format:check": "prettier --check \"app/**/*.{ts,tsx,css}\" \"components/**/*.tsx\" \"lib/**/*.ts\""`
- **红线**：不运行 `prettier --write`。若 check 报既有文件不符合，允许把 `--check` 改为仅对 `lib/` 生效并在 README 注明渐进策略。

### T0.3 Vitest + 纯函数测试
- 装：`npm i -D vitest @vitest/coverage-v8`
- 建 `vitest.config.ts`：`resolve.alias` 映射 `@` → 项目根（对齐 tsconfig paths）；`environment: "node"`（不需要 jsdom）。
- scripts：`"test": "vitest run"`、`"test:cov": "vitest run --coverage"`、`"check": "npm run lint && npx tsc --noEmit && npm run test"`。
- 测试文件放 `frontend/tests/`：
  - `tests/annotate.test.ts` —— 用例方向（直接照做）：
    1. `renderAnswer("《民法典》第五百七十七条")` 含 `class="law-ref"` 且 `data-source="民法典"`
    2. `renderAnswer("刑法第23条")` 补书名号渲染为 `《刑法》第23条`
    3. 跨句独立条号不标注：`renderAnswer("本案依据《劳动法》。第九条为合同条款。")` 第二个"第九条"无 `law-ref`
    4. 时限：`三年` → `hl-time`；金额：`2万元` → `hl-money`；倍数：`三倍` → `hl-num`
    5. Markdown：`# 标题`→`answer-h1`；`| a | b |` 表格 → `answer-table`；`- 项` → `answer-ul`
    6. **锁定现状**：`renderAnswer("0.05%*本金")` 中 `*` 被删除——这是已知缺陷（annotate.ts:278），断言现状并加注释 `// KNOWN-DEFECT 批次2后修复：全局删星号`，**本批次不修**
    7. XSS：`renderAnswer('<script>alert(1)</script>')` 输出不含 `<script>`
    8. 引号摘录：中文引号「」内的时间/金额同样高亮（`highlightInsideQuote` 路径）
  - `tests/scope.test.ts` —— `parseScopeCandidates`/`buildScopeAnswer`：正常解析、空输入、超选上限（SCOPE_MAX_SELECTION）边界
  - `tests/sse-frame.test.ts` —— 若 api.ts 的帧解析（按 `\n\n` 切分、`data: ` 前缀、`[DONE]` 判定）是内联在 `streamChat` 中的，**允许最小抽函数**（如 `parseSSEFrames(buffer): string[]`），行为零变更；用例：单帧、跨 chunk 残帧、末帧无换行、非 data 行忽略。
- 完成判据：`npm run test` 全绿；`annotate.ts` 与 `scope.ts` 语句覆盖率 **≥ 80%**（`--coverage` 报告为证）。

---

## 3. 批次 1 · 速赢 + SW 根除（T1.1–T1.7）

### T1.1 SW 版本化（P0）
改 `public/sw.js`：
1. install 事件里先 `const bid = await fetch('/_next/static/BUILD_ID').then(r => r.text()).catch(() => 'dev')`；`const CACHE = \`fazhi-shell-${bid}\``（BUILD_ID 是 Next build 产物，公开可访问）。
2. activate 清理**所有**不等于当前 CACHE 名的旧缓存（现有逻辑已按 `k !== CACHE` 过滤，保留即可——名字变了自然清旧）。
3. fetch 兜底 `caches.match(req)` 与 `caches.match("/")` 都改为**仅查当前 CACHE**：`caches.open(CACHE).then(c => c.match(...))`。这保证离线兜底命中的 HTML 一定引用当前版本 chunk。
- 判据：连续两次 `npm run build`，BUILD_ID 变化 → 新缓存名；浏览器 Application 面板确认旧缓存被清。手测：普通访问/刷新/断网刷新均不再出现旧壳白屏。

### T1.2 aria-live
- chat 页消息列表：**仅对"流式中的最后一条 assistant 气泡"** 的内容容器加 `aria-live="polite"`（勿加在整个列表，否则每次全量朗读）。

### T1.3 streaming 保护补漏
- 侧栏"管理后台"跳转按钮（chat 页，其余三处 newChat/selectConv/deleteConv 已有同款保护）加 `disabled={streaming}` 与禁用态样式。

### T1.4 语义色临界微调（globals.css `:root`，观感不可辨）
`--law: #2f7bc4 → #2e79c0`；`--time: #b9621a → #b56019`；`--money: #1f8a63 → #1e8660`（均达 WCAG AA 4.5）。**禁止**用其它方案（暴力加深会摧毁"色相即语义"）。

### T1.5 Enter 发送
- 输入区 onKeyDown 改为：`Enter && !shiftKey` → 发送；Shift+Enter 保留换行；删除 Ctrl+Enter 分支。
- placeholder 与按钮 `title` 标注「Enter 发送 · Shift+Enter 换行」。

### T1.6 触达目标
- 发送/上传图片/语音三个 `h-9 w-9` 图标按钮 → `h-11 w-11`（44px），图标视觉尺寸不变（内层 svg 加 `h-5 w-5` 之类收着）。

### T1.7 formatDate 工具
- 新建 `lib/format.ts`：`export function formatDateTime(iso?: string): string`（内部 `toLocaleString("zh-CN")`，空值返回 "-"）。
- admin 页 3 处 `new Date(x).toLocaleString("zh-CN")` 全部替换。

---

## 4. 批次 2 · 结构重构（T2.1–T2.5，**纯搬移不改行为**）

### 总则
- 每个子任务独立 commit；搬移后 `npm run check` + §6 手测通过才提交。
- 行为锁定锚点：T0.3 的测试必须全程绿；`annotate.ts` 一行不改。
- 类型定义集中：各 page 里的 interface（Msg/ConvItem/HistoryMsg/Stats/UserRow/…）迁往 `lib/types.ts`，page 从那里 import。

### T2.1 常量抽取
- `lib/constants.ts`：`MAX_IMAGE_MB/ACCEPT_IMAGE/MAX_FILE_MB/ACCEPT_FILE/SCENES/DAILY_LAWS(含 _shuffleBySeed 与 _dailySeed)/CODEX/LAW_CACHE_MAX`。chat 页改为 import。

### T2.2 chat 页拆分 → `components/chat/`
| 新文件 | 搬入内容（以现状代码为准） |
|---|---|
| `ChatImage.tsx` | 顶层组件 ChatImage（chat/page.tsx :167 起） |
| `MessageHtml.tsx` | MessageHtml memo 组件 |
| `MessageBubble.tsx` | 单条消息渲染（气泡/图标/来源折叠/sources `<details>`/👍👎/纠错入口），props 走显式接口 |
| `MessageList.tsx` | 消息循环 + 空态（SCENES 卡片）+ 自动滚动锚点 |
| `InputBar.tsx` | 输入区（textarea/发送/图片/语音/文件/scope 选择条） |
| `Sidebar.tsx` | 历史会话列表 + 新对话 + 管理后台入口（含移动抽屉） |
| `LawPanel.tsx` | 法条速查面板 |
| `QuotaBanner.tsx` | 配额预警横幅（现内联 style 那段） |
- `app/chat/page.tsx` 收敛为 <400 行：只保留页面组装 + 数据编排。

### T2.3 状态收敛 → `lib/hooks/`（或 `hooks/`，二选一保持一致）
- `useChatStream.ts`：messages/streaming/doSend/SSE onMeta（sources/steps/agentNote/clarifyRounds）
- `useFeedback.ts`：fbDone/corrFor/corrText + submitFeedback/corrText 提交
- `useConversations.ts`：history/activeId/selectConv/newChat/deleteConv（含三个入口的状态重置——**保留现有重置逻辑，勿"顺手优化"**）
- 29 个 useState 允许保留少量页面级 UI 态（sidebarOpen/expandedLaw/lawPanel）在 page 内，不强求 useReducer。

### T2.4 admin 拆分 → `app/admin/sections/`
- `StatsSection/UsersSection/KnowledgeSection/UploadSection/ConversationsSection/AuditSection` 六个文件；`AdminPage` 保留侧导航 + loader switch（现有 `loaders` 模式）+ 组装。
- 每个 section 自带子状态（现有 useState 按所属 section 归位，如 newUser/userMsg/creating 归 Users）。

### T2.5 api.ts 消灭 any
- 为以下端点补 interface（字段以现有 page 内定义为准迁入 types.ts）：`convApi.list/detail`（ConversationItem）、`adminApi.stats/users/qaCandidates/audit`、`lawApi.*` 已有则不动。
- 同时修复既有 P2：`adminApi.qaCandidates/audit` 的查询参数补 `encodeURIComponent`（与 lawApi 对齐）。
- **禁止**改变请求路径、方法与响应处理逻辑。

---

## 5. 验收门禁（验收方按此逐项核验，缺一即打回）

| # | 门禁 | 通过标准 |
|---|---|---|
| V1 | `npm run check` | lint 0 error（warning ≤200）/ tsc 0 错 / test 全绿 |
| V2 | `npm run build` | 成功，5 条路由全出，/chat 首载体积不高于基线 104kB 的 +10% |
| V3 | 覆盖率 | annotate.ts 与 scope.ts 语句覆盖 ≥80%（coverage 报告截图/输出为证） |
| V4 | 提交历史 | 每个 Tx.y 至少一个 commit；无 `git add -A` 痕迹；`backend/`、`dispatch-output/` 零改动（`git diff f0f9cc9..HEAD --stat -- backend dispatch-output` 为空） |
| V5 | 行为锁定 | tests 全绿且 annotate.ts 相对基线 `git diff f0f9cc9..HEAD -- frontend/lib/annotate.ts` 为空 |
| V6 | 结构 | chat/page.tsx ≤400 行；admin/page.tsx ≤250 行；无 page 内定义的组件（ChatImage/MessageHtml 已迁出） |
| V7 | SW | 连续两次 build 缓存名变化；离线兜底仅查当前版本缓存 |
| V8 | 手测 | §6 清单 7 条路径全部通过（执行者自测记录贴在 PR/汇报中） |

## 6. 关键路径手测清单（每批次收尾跑一遍）
1. 发送消息 → 流式逐字输出 → 完成后出现「参考条文(N)」折叠 → 展开见药丸标签
2. Enter 直接发送；Shift+Enter 换行；流式期间发送/切换会话/删会话被禁
3. 图片发送（选图/预览/发送后显示）；文件上传入口；语音按钮按下不报错
4. 法条引用点击 → 内联展开法条卡 → 关闭；§ 速查面板打开/ESC 或遮罩关闭
5. 👍/👎 反馈：点按后禁用；切换会话 A→B 反馈状态**不**串位；新建对话同理
6. 会话切换/新建/删除后消息与输入区干净（无残留草稿态、无上一会话内容）
7. 手机宽度（≤400px 视口）下：抽屉开关、输入区、消息气泡、法条卡无横向溢出；`npm run build && npm start` 后走一次 1–6（生产模式验证 SW）

## 7. 已知不做（避免执行者越界）
- 不修 annotate 全局删星号（KNOWN-DEFECT 测试锁定即可）；不做流式增量渲染；不动三套粉色 token；不清理死样式；不改后端任何文件与接口；不引入 Serwist/next-pwa 等新运行时依赖（Vitest/ESLint/Prettier 三个 devDep 除外）。
