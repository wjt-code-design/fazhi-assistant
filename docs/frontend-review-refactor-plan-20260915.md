# 法智前端审查与优化改造方案（v2 · 含问题清单 + 分批计划 + 待对齐决策点）

> 日期：2026-09-15 ｜ 前置：本日已完成两轮工作——审计建议书 `frontend-optimization-proposal-20260915.md`（462 行）
> 与 5 项确定性修复（commit `f0f9cc9`，已验收通过）。本方案**不重复已修内容**，聚焦剩余项
> 与本轮新覆盖的维度（组件设计 / 可维护性 / 工程化）。
> 现状基线：12 文件 / 4729 行；chat 1465 行、admin 893 行、globals.css 1021 行。

---

## 1. 问题清单（六维度 · 已标注修复状态）

严重度：🔴P0=会造成线上事故/功能错误　🟠P1=明显体验/性能/维护风险　🟡P2=打磨项
状态：✅=已修（f0f9cc9）｜⬜=待修（本轮范围）

> **状态列回填（2026-09-22，票 T12-B）**：本表原为 **2026-09-15 快照**，其后批次 0/1/2（护栏 + 速赢 + 结构）
> 已落地但未回填。本次按**代码事实**逐条核对：**14 条改判为 ✅/🟡部分**（A1–A4、B2、B3、B4、C1、D1、D2、F1、F2、F5、F7），
> 依据见 `dispatch-output/t12b-doc-status-20260922/report.md`。
> **仍为 ⬜ 的两类必须区分**：①**经核仍未做**——B1（内联 `<svg>` 17 处）、C3（`background-attachment:fixed` 仍在）、
> D4（6 处死样式 + `--stagger`/`--dur-med` 死变量仍在）、E1（`#ff8fa9`×5 / `#f56b8c`×2 / 裸 `rgba` 93 处）、
> E2（圆角仍 4 种）；②**本次未核（需人读或需算）**——C2、C4、E3、F3、F4、F6。**未核 ≠ 未做**，勿混读。

### A. 代码结构与组织

| # | 级 | 问题 | 影响范围 | 状态 |
|---|---|---|---|---|
| A1 | 🟠 | `chat/page.tsx` **1465 行单组件**：29 useState + 9 useEffect + 7 useRef + 25 个函数 + 2 个内联组件（ChatImage :167、MessageHtml :271） | 所有聊天功能改动都在巨石内进行，回归风险集中；Agent/人协作冲突面最大 | ✅（2026-09-22 核：`app/page.tsx` 27 行 / 0 useState；拆出 `components/chat/` 9 文件 + `lib/hooks/` 5 hook） |
| A2 | 🟠 | `admin/page.tsx` **893 行、6 个 section 堆叠**（28 useState + 12 函数），每个 section 的加载/空态/操作内联在一个组件 | 管理后台任何一栏改动都要理解全部 6 栏 | ✅（2026-09-22 核：`app/admin/page.tsx` 214 行；拆出 `app/admin/sections/` 6 段） |
| A3 | 🟡 | 组件定义在 page 文件内（MessageHtml/ChatImage），复用性为零、职责混合 | 组件无法独立测试/复用 | ✅（2026-09-22 核：`components/chat/MessageHtml.tsx`、`ChatImage.tsx` 已成独立组件文件） |
| A4 | 🟡 | SCENES/DAILY_LAWS/CODEX 等常量堆在 chat 页头（:52-149），与组件混杂 | 文件头 100 行与 UI 无关 | ✅（2026-09-22 核：`lib/constants.ts` 存在；chat 页内 `SCENES/DAILY_LAWS/CODEX` 命中 0） |

### B. 组件设计

| # | 级 | 问题 | 影响范围 | 状态 |
|---|---|---|---|---|
| B1 | 🟡 | 无图标组件：admin 10 处 + chat 5 处内联 `<svg>` | 换图标需全局搜改 | ⬜ |
| B2 | 🟡 | 日期格式化 `toLocaleString("zh-CN")` 在 admin 重复 3 次 | 改格式要找 3 处 | 🟡部分（2026-09-22 核：`lib/format.ts` 已建（T1.7）；`toLocaleString` 由 3 处收敛到 **1 处**残留 —— `admin/sections/AuditSection.tsx:23` 仍内联） |
| B3 | 🟠 | `api.ts` 泛型逃逸 `any`（conversations/admin/audit 无类型） | 契约漂移无门禁，后端改字段前端静默坏 | ✅（2026-09-22 核：`lib/api.ts` 382 行，`any` 命中 **0**） |
| B4 | 🟠 | chat 29 个**扁平 useState 相互耦合**（streaming/messages/fbDone/corrFor/expandedLaw/lawPanel…无分组） | 上一轮 fbDone 跨会话 bug 正是扁平状态的必然产物；同类风险还有 | ✅（2026-09-22 核：`app/page.tsx` 0 useState；状态进 `lib/hooks/useChatStream.ts`，**5 个 useState**） |

### C. 性能 / PWA（均出自上午审计，未修）

| # | 级 | 问题 | 影响范围 | 状态 |
|---|---|---|---|---|
| C1 | 🔴 | Service Worker：CACHE 名硬编码 `fazhi-shell-v1` + 离线兜底旧 HTML → **每次发版可能白屏** | 所有手机 PWA 用户；本地 dev 不注册 SW，极易漏测 | ✅（2026-09-22 核：`public/sw.js` 缓存名 = `fazhi-shell-<BUILD_ID>`（install 时 fetch `/build-id.txt`）；硬编码 v1 仅存于**记录该缺陷的注释**里） |
| C2 | 🟠 | 流式渲染 O(n²)：每 token 对全量累积文本重跑 8 条正则 + Markdown + 全量替换 DOM | 长回答（合同审查报告）后期明显卡顿 | ⬜ |
| C3 | 🟠 | `background-attachment: fixed`（globals.css:97）+ 双固定伪元素 | 移动端滚动性能（本项目主打手机端） | ⬜ |
| C4 | 🟡 | onScroll 无节流 / 260ms interval / 每 rAF getBoundingClientRect | 中低端手机帧率 | ⬜ |

### D. 可维护性 / 工程化（本轮新维度）

| # | 级 | 问题 | 影响范围 | 状态 |
|---|---|---|---|---|
| D1 | 🟠 | **零门禁：无 ESLint、无 Prettier、无任何测试、package.json 无 test script**（已实测确认） | 今天 5 项修复只靠手工 tsc+build 兜底；任何人/Agent 的改动无自动护栏——这是所有后续重构的**前置缺失** | ✅（2026-09-22 核：`.eslintrc.json` / `.prettierrc` / `vitest.config.ts` + `test` script 齐备） |
| D2 | 🟠 | 前端零测试。`annotate.ts`（286 行正则渲染）、`scope.ts`、api.ts SSE 解析都是**纯函数**，可测性极好却零覆盖 | 重构 A1/A2 无安全网 | ✅（2026-09-22 核：**7 个测试文件 / 54 用例**，本次 `npm run check` 全过） |
| D3 | ✅ | tsconfig `strict: true` 已开启（好消息，无需动） | — | ✅ |
| D4 | 🟡 | 上轮已定位的死代码未清：6 处死样式（glass-card-strong/glow-line/done-seal/law-popup/section-mark-float/lineGrow）+ login 的 register 死分支（~20 行）+ `--stagger`/`--dur-med` 死变量 | 误导后续维护者 | ⬜ |

### E. 样式规范（上轮已列，未修）

| # | 级 | 问题 | 状态 |
|---|---|---|---|
| E1 | 🟠 | 三套粉色并存：`#ff8fa9`×5、`#f56b8c`×2 与 `--accent #e894ac`，93 处裸 rgba | ⬜ |
| E2 | 🟡 | 圆角 4 种混用，`--radius` "统一 6px" 名存实亡 | ⬜ |
| E3 | 🟡 | 语义色临界不达标：`--law` 4.42 / `--time` 4.35 / `--money` 4.31（各深 2% 即达标，观感不变） | ⬜ |

### F. 用户体验（上轮已列，未修）

| # | 级 | 问题 | 状态 |
|---|---|---|---|
| F1 | 🟠 | 无 `aria-live`——屏幕阅读器读不到流式回答（**一行**） | ✅（2026-09-22 核：`components/chat/MessageBubble.tsx:141` `aria-live={streaming && isLast ? "polite" : undefined}`） |
| F2 | 🟠 | Enter=换行 / Ctrl+Enter=发送，反直觉且 UI 零提示 | ✅（2026-09-22 核：`InputBar.tsx:194` Enter 发送 / Shift+Enter 换行 + 占位符与 title 均有 UI 提示；含中文输入法 isComposing 保护） |
| F3 | 🟠 | 法条面板/移动抽屉缺 modal 三件套（ESC/focus trap/锁滚动） | ⬜ |
| F4 | 🟠 | 每日法条 5s 自动轮播无暂停（WCAG 2.2.2 不合规；reduced-motion 对 JS interval 无效） | ⬜ |
| F5 | 🟡 | 流式期间"管理后台"无 `disabled={streaming}` 保护（**一行**；其余三处都有） | ✅（2026-09-22 核：`components/chat/Sidebar.tsx:96` 管理后台入口 `disabled={streaming}`） |
| F6 | 🟡 | 历史会话项 `<div onClick>` 键盘不可达；注册 tab 用 `<div>` 假 tab | ⬜ |
| F7 | 🟡 | 发送/上传按钮 36px < 44px 触达标准 | ✅（2026-09-22 核：`InputBar.tsx` 发送/上传等按钮为 `h-11 w-11`（44px）） |

---

## 2. 优化方案（分 4 批 · 每批可独立叫停）

> 排序理由：**先护栏、再速赢、后动刀**。没有 D1/D2 的门禁与测试就做 A1/A2 拆分 = 裸奔重构；
> 批次 1 全是一行级改动，先让用户立刻受益；批次 3/4 与批次 2 无依赖可并行。

### 批次 0 · 护栏先行（约 0.5 天）
1. ESLint（`next/core-web-vitals` + `@typescript-eslint`）+ Prettier + `npm run check`（lint+tsc+test 一键）
2. Vitest 脚手架，**只测纯函数**：`annotate.ts`（高亮正则——今天发现的双引号死分支就是它）、`scope.ts`、api.ts SSE 解析器。不碰组件、零 DOM 依赖，半天可写 ~30 个用例
- 理由：D1 是全部改造的前置；纯函数测试性价比全项目最高

### 批次 1 · 一行级速赢 + SW 白屏根除（约 0.5~1 天）
F1 aria-live、F5 streaming 保护、E3 三色微调 2%、B2 formatDate 工具、F2 Enter 行为（✅已拍板：Enter 发送/Shift+Enter 换行+提示）、F7 触达 44px、
**C1 SW 版本化（✅已拍板：构建号版本化，从批次 3 提前至此——P0 不应等）**
- 理由：成本最低、感知最快，且不依赖任何结构调整

### 批次 2 · 结构重构（约 2~3 天，每步一提交）
1. chat 拆分：`components/chat/{MessageList,MessageBubble,InputBar,Sidebar,LawPanel,QuotaBanner}` + `hooks/{useChatStream,useFeedback,useConversations}` + `lib/constants.ts`
2. 状态分组：29 个扁平 useState 按域收敛为 3 个自定义 hook（流式会话/反馈/法条面板）
3. admin 拆分：`admin/sections/` 六个子组件 + 统一 loader 模式
4. B3：api.ts 补全 TS 接口消灭 `any`
- 理由：A1/A2 是最大的维护债；有批次 0 的网后才动。**纯移动代码不改逻辑**，每步 tsc+build+关键路径手测

### 批次 3 · 性能与 PWA（约 1~2 天，可与批次 2 并行）
C3 移除 background-attachment:fixed 迁移到伪元素、C2 流式增量渲染（先只渲染未完成块，final 后全量渲染一次）、C4 rAF 节流
（C1 SW 版本化已提前至批次 1）

### 批次 4 · 设计系统收敛（约 1 天）
E1 三粉归一（7 处替换）、E2 圆角 scale、B1 Icon 组件、D4 死代码清理、F3/F4/F6（modal 三件套、轮播改手动、键盘可达）

---

## 3. 不破坏现有功能的保障

1. **批次即依赖序**：0→1 任意做，2 必须在 0 之后，3/4 与 2 无耦合
2. 批次 2 为**纯结构搬移**：不改 api 调用参数、不改 annotate 正则、每步提交可回滚
3. `f0f9cc9`（5 项已验收修复）为基线，重构后可逐项对照验证：发送/流式/图片/语音/法条卡/反馈/会话切换 7 条关键路径
4. 纯函数测试先行覆盖 annotate/scope——重构时它们是"锚点"

## 4. 决策对齐结果（grilling · 2026-09-15 22:18 拍板）

| # | 决策点 | 结论 |
|---|---|---|
| ① | 改造范围 | **批次 0+1+2**（护栏 + 速赢 + 结构重构，约 3.5 天）；批次 3/4 视结果另议 |
| ② | 测试策略 | **只测纯函数**（Vitest + ~30 用例：annotate/scope/SSE 解析） |
| ③ | Enter 键 | **改为 Enter 发送 / Shift+Enter 换行**，placeholder 标注提示 |
| ④ | SW 修法 | **构建号版本化**（CACHE 名注入构建 hash + 离线兜底版本匹配，零新依赖）；已提前至批次 1 |

执行顺序即批次序 0→1→2，每步一提交、可独立叫停。关键路径验证清单：发送/流式/图片/语音/法条卡/反馈/会话切换 7 条。
