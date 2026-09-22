# T12-B · 文档状态回填（只改 docs，不改代码）

> 对象：`docs/frontend-review-refactor-plan-20260915.md` §1「问题清单（六维度 · 已标注修复状态）」
> 问题：该表是 **2026-09-15 快照**；其后**批次 0/1/2 已落地**（护栏 + 速赢 + 结构），但状态列**从未回填**
> ⇒ 表里大量 ⬜ 与代码现状相反（T12 主卡已发现 B4 即属此类）。
> 本卡动作：**按代码事实逐条核对 → 回填状态列（14 条改判）→ 未核项的区分写清楚**。

## 0. 一句话结论

**14 条从 ⬜ 改判**（13 条 ✅ + 1 条 🟡部分）；**5 条经核仍未做维持 ⬜**；
**6 条本次未核**（保持 ⬜ 但**明确标注"未核 ≠ 未做"**，避免把"没核实"混进"已核实未修"）。

## 1. 改判明细（前 → 后，含代码事实）

| # | 原 | 现 | 代码事实（2026-09-22 实测） |
|---|---|---|---|
| A1 | ⬜ | **✅** | `app/page.tsx` **27 行 / 0 useState**；拆出 `components/chat/` **9 文件** + `lib/hooks/` **5 hook** |
| A2 | ⬜ | **✅** | `app/admin/page.tsx` **214 行**；拆出 `app/admin/sections/` **6 段** |
| A3 | ⬜ | **✅** | `components/chat/MessageHtml.tsx`、`ChatImage.tsx` 已成独立组件文件 |
| A4 | ⬜ | **✅** | `lib/constants.ts` 存在；chat 页内 `SCENES/DAILY_LAWS/CODEX` 命中 **0** |
| B2 | ⬜ | **🟡部分** | `lib/format.ts` 已建（T1.7），但 `toLocaleString` 仅从 3 处收敛到 **1 处残留**（`admin/sections/AuditSection.tsx:23`） |
| B3 | ⬜ | **✅** | `lib/api.ts` 382 行，`any` 命中 **0** |
| B4 | ⬜ | **✅** | `app/page.tsx` 0 useState；状态进 `lib/hooks/useChatStream.ts`（**5 个 useState**，原 29 个扁平） |
| C1 | ⬜ | **✅** | `public/sw.js` 缓存名 = `fazhi-shell-<BUILD_ID>`（install 时 fetch `/build-id.txt`）；"硬编码 v1"只存在于**记录该缺陷的注释**中 |
| D1 | ⬜ | **✅** | `.eslintrc.json` / `.prettierrc` / `.vitest.config.ts` + `test` script 齐备 |
| D2 | ⬜ | **✅** | **7 个测试文件 / 54 用例**；本次 `npm run check` 全过 |
| F1 | ⬜ | **✅** | `components/chat/MessageBubble.tsx:141` `aria-live={streaming && isLast ? "polite" : undefined}` |
| F2 | ⬜ | **✅** | `InputBar.tsx:194` Enter 发送 / Shift+Enter 换行（含 `isComposing` 中文输入法保护）+ 占位符与 `title` 均有 UI 提示 |
| F5 | ⬜ | **✅** | `components/chat/Sidebar.tsx:96` 管理后台入口 `disabled={streaming}` |
| F7 | ⬜ | **✅** | `InputBar.tsx` 发送/上传等按钮 `h-11 w-11`（44px） |

## 2. 经核仍未做（维持 ⬜，带读数）

| # | 读数 |
|---|---|
| B1（无图标组件，内联 `<svg>`） | `app/components/lib/public/scripts` 内 `<svg>` **17 处**（原记 admin 10 + chat 5） |
| C3（`background-attachment: fixed`） | CSS 内命中 **1**（仍在） |
| D4（死样式/死变量） | `glass-card-strong`/`glow-line`/`done-seal`/`law-popup`/`section-mark-float`/`lineGrow` 各 **1 处仍在**；`--stagger`×2、`--dur-med`×3 仍在 |
| E1（三套粉色 + 裸 rgba） | `#ff8fa9`×**5**、`#f56b8c`×**2**、裸 `rgba(`×**93** |
| E2（圆角混用） | 实测 `border-radius` 值：**2px / 6px / 8px / 9999px**（4 种） |

## 3. 本次未核（保持 ⬜，**未核 ≠ 未做**）

`C2`（流式 O(n²)：需读渲染路径）、`C4`（节流/interval：实测 `throttle|debounce|rAF` 命中 1、`setInterval` 2，**不足以下结论**）、
`E3`（语义色对比度 4.42/4.35/4.31 是否已深 2%：**需按背景色算 WCAG 对比度**，本轮未算）、
`F3`（modal 三件套）、`F4`（每日法条轮播暂停）、`F6`（`<div onClick>` 键盘可达）。

## 4. 一处必须说清的边界

- 该文档是**未跟踪文件**（T12 卡原文亦标注"多份未跟踪文档"）⇒ `git diff --stat` 对它为空；
  本次修改**落在文件本身**（UTF-8 完好，已用 Python 解码验证；终端乱码纯属显示层）。
- **风险**：未跟踪文档不进 git 历史 ⇒ 若被清理（T4 曾清"可再生副本"）回填成果会丢。
  故本报告把**改判明细与读数**完整抄录在案（上表），保证可复现。
- **建议（供 Owner）**：把 `docs/frontend-*.md` 三份**纳入版本控制**——它们承载了前端决策与状态，
  长期未跟踪正是"状态漂移无人发现"的制度原因。本卡**未**擅自 `git add`（改跟踪状态属仓库策略）。

## 5. 本卡没做的

- 未改任何前端代码/配置（卡面禁令）；未新增/删除文档条目，只改**状态列**与顶部口径说明；
- 未判定 §3「优化方案（分 4 批）」的批次完成度（那是另一件事，需逐批核对）。
