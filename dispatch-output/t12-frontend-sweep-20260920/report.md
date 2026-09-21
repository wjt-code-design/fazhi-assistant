# T12 · 前端面普查报告（只读）

> 卡面出处：`dispatch-output/hij-h-20260920/ALL-PARALLEL-TASKS.md` §3 T12 卡。
> 规划书（执行前）：同目录 `plan.md`（grilling 五分枝已拍板）。
> 执行：主会话直接执行（限流窗口已过、只读、无并发写风险）。
> **本卡只读**：未改任何前端源码/配置；未 `npm install`；未递归读 `node_modules`。

---

## 0. 一句话结论

**前端三个面都健康**：15 个编号待办**逐条找得到代码事实**、`check` 与 `build` **今天都能跑通**（rc=0）、
前后端**未发现契约不一致**。真正的发现是**三类"文档与代码不同步"**（文档标"待修"的实现已完成）+
**一条环境隐患**（构建产物把后端地址写死成公网 IP）。

---

## 1. 轴① 有没有*可执行的*待办 —— 答：**没有新增的；但文档状态已落后于代码**

清单源 = `docs/frontend-execution-book-20260915.md`（15 个编号任务）+ `docs/frontend-review-refactor-plan-20260915.md` §1（自带 ✅/⬜ 状态）。
方法 = **每条按代码事实核**（`dispatch-output/t12-frontend-sweep-20260920/axis1_check.py` → `axis1-code-facts.json`），**不采信文档自述**。

### 1.1 execution-book 的 15 个任务：逐条已落地

| 任务 | 代码事实（怎么查的） | 判定 |
|---|---|---|
| T0.1 ESLint | `.eslintrc.json` 存在；`npm run lint` 跑通 | ✅ 已落地 |
| T0.2 Prettier | `.prettierrc` + `.prettierignore` 存在 | ✅ |
| T0.3 Vitest + 纯函数测试 | `vitest.config.ts` + **7 个测试文件**（`tests/*.test.ts`）；本次 `vitest` 54 测试全过 | ✅ |
| T1.1 SW 版本化（P0） | `scripts/write-build-id.mjs` 存在，且被 `package.json` 的 `build` 接线；本次构建实测输出 `public/build-id.txt = 0I8HyHI4943uDT6FZA9sP` | ✅ |
| T1.2 aria-live | `aria-live` 命中 1 处 | ✅ |
| T1.3 streaming 保护补漏 | `AbortController/abortSignal/isStreaming` 类命中 1 处（`api.ts` 的 `AbortController` + 180s 看门狗） | ✅ |
| T1.4 语义色临界微调 | `app/globals.css` 存在（`:root` 语义色） | ✅（观感项，机器只能证"文件在"） |
| T1.5 Enter 发送 | `onKeyDown`/`Enter` 类命中 3 处 | ✅ |
| T1.6 触达目标 | `min-h-`/`min-height`/`touch-action` 命中 8 处 | ✅ |
| T1.7 formatDate 工具 | `lib/format.ts` 存在 | ✅ |
| T2.1 常量抽取 | `lib/constants.ts` 存在 | ✅ |
| T2.2 chat 页拆分 | `components/chat/` 存在，**9 个组件**（ChatImage/InputBar/LawPanel/MessageBubble/MessageHtml/MessageList/QuotaBanner/Sidebar/lawCardHtml） | ✅ |
| T2.3 状态收敛 | `lib/hooks/` 存在，**5 个 hook**（useChatStream/useConversations/useFeedback/useLawCards/useVoice） | ✅ |
| T2.4 admin 拆分 | `app/admin/sections/` 存在，**6 个 section**（Audit/Conversations/Knowledge/Stats/Upload/Users） | ✅ |
| T2.5 api.ts 消灭 any | `lib/api.ts` 382 行，**`any` 命中 0** | ✅ |

### 1.2 review-plan 的 ⬜ 项：**至少 B4 已过期**（文档与代码不同步）

- 文档 §1 记 B4 =「chat 页 29 个**扁平 useState** 相互耦合」状态 **⬜ 待修**。
- **代码事实**：`app/page.tsx` 仅 **27 行、0 个 useState**；状态已搬进 `lib/hooks/useChatStream.ts`（187 行，**仅 5 个 useState**）。
- ⇒ **B4 实际已修**，文档的 ⬜ 是 2026-09-15 的快照。**这是本卡最有价值的一条发现**：文档说"没做"、代码已经做了。
  （其余 ⬜ 项如 C 性能/PWA、E 样式规范属"观感/性能"类，机器不易证伪，**未逐条下结论**；见 §4 局限。）

---

## 2. 轴② 构建今天能不能跑通 —— 答：**能，rc=0 / rc=0**

| 命令（仓库既有脚本，不自选） | 退出码 | 关键读数 |
|---|---|---|
| `npm run check`（= `lint` + `tsc --noEmit` + `vitest run`） | **0** | lint **2 warning / 0 error**（`@next/next/no-img-element` ×2：`components/chat/ChatImage.tsx:33`、`InputBar.tsx:53`）；tsc **0 error**；vitest **7 文件 / 54 测试全过**（1.88s） |
| `npm run build`（= `next build` + `write-build-id.mjs`） | **0** | 静态页预渲染完成；`[write-build-id] public/build-id.txt = 0I8HyHI4943uDT6FZA9sP` |

**报错性质**：无报错可判"缺依赖 vs 真失败"（`frontend/node_modules` 已存在，两条命令都 rc=0）。
两条 warning 属 ESLint 建议级（`<img>` 建议换 `next/image`），**不阻塞**。

**实际写入了哪些目录**（卡面强制要求写明）：
- `frontend/.next/**`（构建产物，**被 .gitignore 忽略** ⇒ 不出现在 `git status`）；
- **`frontend/public/build-id.txt`**（`write-build-id.mjs` 覆写；本次**内容未变**——同源码 BUILD_ID 确定性 ⇒ `git status` 亦为空）。
- 实测：`git status --porcelain frontend/` **为空** ⇒ 构建**幂等**，无意外写入。这条修正了规划书 §4 的担心（原以为 build-id 必变）。

**发现项（环境隐患，非本卡缺陷）**：构建产物把后端基址**内联为公网 IP**
（`.next/static/**` 内实测命中 `http://162.14.81.34:8000`，来源 `frontend/.env` 的 `NEXT_PUBLIC_API_URL`）。
⇒ 本地/CI 起这套前端产物会**打到公网后端**；任何"本地前端 ↔ 本地后端"的验证都必须先覆盖该变量。
（`lib/api.ts` 的注释称生产走同源 `/api/*` 由 Caddy 反代，与此处 `.env` 的公网直连口径**并存**，值得核对哪套是当前部署口径。）

---

## 3. 轴③ 有没有与后端契约不一致的证据 —— 答：**未发现不一致**（深口径）

方法：①后端真源 = **进程内** `main.app.openapi()` 导出（`axis3-backend-openapi.json`，**40 条路径**）；
②前端调用点抽取（`axis3_contract_check.py` → `axis3-contract-diff.json`）；③**逐条 grep 复核**（因②有已知盲区）。

### 3.1 路径层面
- **前端调用的每条路径都能在后端找到**（无真实"只前端有"）。
  两条例外均为**假阳性**，已逐条读原文排除：`public/sw.js:52` 是 SW 的 `startsWith("/api/")` **前缀判断**（防缓存 API/SSE）；`next.config.js:9` 是 dev **代理规则**。
- **后端有 6 条端点前端未调用**：`/api/admin/analysis-runs`、`/api/admin/llm-disable`、`/api/admin/llm-promote`、`/api/admin/llm-quota`、`/api/admin/feedback`、`/healthz`
  （另有 `/api/media/{filepath}` 供 `<img>` 直取，**不属调用点**）。
  ⇒ 属"后端能力集 ⊃ 前端用法"，**不是契约错误**；若其中有运维刚需（如 llm 配额调整），则是**前端缺功能**，可作为候选待办。

### 3.2 SSE 帧类型（深口径第三层）
后端产出 `content`（无 type 主帧）/`clarification`/`step`/`status`/`restart`/`error`；
前端解析器（`lib/api.ts:225-266`）处理 `error`/`clarification`/`final`/`step`/`restart` + `content` 兜底。
**两个候选不一致经核实均为设计如此**：
1. `final` —— 由 **agent 路径** `agent/chat_integration.py:89` 发出（不在 `main.py`）⇒ 前端分支是**活的**；
2. `status` —— `main.py` docstring 明写「**前端对未知 type 帧自动忽略**」⇒ 前端不处理是**有意为之**。

### 3.3 抽取侧局限（诚实登记，防"看起来对过了"）
正则抽取**三类已知假阴性**，均由逐条 grep 补足：
① 带前缀的模板字面量 `` `${API_URL}/api/chat` ``；② 带查询串 ``` `/api/law/search?q=${…}` ```；
③ 嵌套模板 ``` `/api/admin/qa/candidates${status ? `?status=…` : ""}` ```。
⇒ **"只后端有"的清单以 grep 复核为准**，不以正则差分为准。

---

## 4. 局限（本报告没做到的）

1. **轴①的 C/E 类（性能、PWA、样式规范）未逐条证伪**——它们是观感/性能类，机器不易判定；本报告只给"配置文件/结构已就位"的事实，**不下"已达成"结论**。
2. **未做视觉/浏览器验收**（卡面没要求；`local-playwright-verify` 可另开一票）。
3. **未核 admin 端点的运行期可用性**（只核了"路径存在/前端是否调用"）。
4. **`.env` 与 `lib/api.ts` 注释的部署口径并存**已标注，但**哪套是当前部署**需 Owner/运维确认（本地无部署配置可查）。
5. 两条 ESLint warning 未修（卡面禁改源码）。

---

## 5. 可派发卡草案（供 Owner 决定，本卡不执行）

| 草案 | 判据 | 交付路径 |
|---|---|---|
| **T12-A · 前端部署基址口径核对** | 明确".env 公网直连"与"同源 /api 反代"哪套是现行部署；给出 `.env.example` 与文档的修正建议（**只报告**） | `dispatch-output/t12a-deploy-base-20260922/` |
| **T12-B · 文档状态回填** | 把 review-plan §1 的 ⬜ 与实际代码逐条对齐（至少 B4 → ✅），更新文档状态列；**不改代码** | `dispatch-output/t12b-doc-status-20260922/` |
| **T12-C · 前端浏览器验收** | 用 `local-playwright-verify` 实机跑：登录/发问/流式渲染/法条卡/移动端视口，出截图与失败点 | `dispatch-output/t12c-browser-20260922/` |
| **T12-D · 两条 ESLint warning 处置** | 评估 `<img>` → `next/image` 的迁移（含 PWA/离线影响），**先报告后改** | `dispatch-output/t12d-img-migration-20260922/` |

---

## 6. 证据清单（同目录）

`plan.md`（执行前规划书）｜`axis1_check.py` + `axis1-code-facts.json`（轴①）｜
`evidence-check.txt`、`evidence-build.txt`（轴② 命令原文与退出码）｜
`axis3_contract_check.py` + `axis3-backend-openapi.json` + `axis3-contract-diff.json`（轴③）
