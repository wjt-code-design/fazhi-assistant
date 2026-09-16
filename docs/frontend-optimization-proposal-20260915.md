# 法智前端优化建议书（只读审计 · 不含任何代码改动）

> 审计日期：2026-09-15　|　范围：`frontend/` 全量源码（12 个 .tsx/.ts/.css 文件，共 4705 行）
> 方式：静态精读 + 量化脚本（WCAG 对比度实测、CSS 类定义-引用交叉扫描、token 漂移统计）
> **全程只读**：未修改任何既有文件；为取证临时创建的 3 个脚本已在完成后删除。
> 未执行 `npm run build` / 未起 dev server / 未截图 —— **本报告不含运行时验证**，凡属推断均已显式标注，见 §10。

---

## 0. 一句话结论

项目前端的代码质量**明显高于平均水平**（契约层 TS 定义完整、前后端交互注释交代了取舍、对 iOS `safe-area` 与 `reduced-motion` 的处理都超过了大多数同类项目），但存在一组**「撞上了就会立刻伤害用户」的系统性缺口**：主行动按钮对比度 1.49（标准为 4.5）、参考条文数据收了却从不展示、Service Worker 会导致发版白屏、以及一处让后台按钮渲染成裸文字。这些问题都不是审美偏好，是**可测量的缺陷**。

分层看：**视觉层的问题是全局性的（色彩 token 不自洽），逻辑层的问题是点状的（4 个确定的 bug），架构层没有需要推倒重来的地方。**

---

## 1. 项目现状速览

| 维度 | 现状 | 评价 |
|---|---|---|
| 技术栈 | Next.js 14 App Router + React 18 + Tailwind 3.4 + TS | 干净、无冗余依赖（dependencies 仅 3 个） |
| 代码规模 | 12 文件 / 4705 行（chat 1441 / admin 893 / globals.css 1021） | 精悍，但 chat 页单组件 1441 行偏重 |
| 设计系统 | `:root` 定义 33 个 token + Tailwind 映射 + `--*-rgb` 三元组 | **骨架建得很好**，问题是执行层没守住（见 §2.3） |
| 类型严谨度 | 契约层 TS 完整，但 admin/会话多处逃逸为 `any` | 参差 |
| 无障碍 | 有 `aria-label`、`role="status"`、`prefers-reduced-motion` 全局兜底 | 有意识，**但缺关键三件套**（见 §4.1） |

**做得好的地方（明确列出，避免"只见树木"）**：
- `app-shell` 用 `100dvh` 处理移动端地址栏、`pb-safe` 处理 Home 条、`@media (max-width: 767px)` 把 input 提到 16px 防 iOS 自动缩放 —— 这三处都是真机上才会踩的坑，作者显然在手机上实测过。
- `usePointerGlow` 用 rAF 节流 + 直接写 CSS 变量（不触发 React 重渲染）+ 卸载时 `cancelAnimationFrame`/`removeEventListener` —— 教科书级别的正确实现。
- `MessageHtml` 自定义 memo 比较函数防止全量重标注，注释还写清了为什么浅比较会被对象引用击穿。
- 流式 fetch 用了 `decoder.decode(r.value, { stream: true })` —— 正确处理了跨 chunk 的 UTF-8 多字节截断，这是很多项目写错的。

---

## 2. 视觉审美

### 2.1 🔴 P0：主行动按钮上的白字对比度只有 1.49 —— 这是全站最严重的问题

不是"感觉偏淡"，是实测：

| 组合 | 对比度 | WCAG AA 要求 | 结论 |
|---|---|---|---|
| 白字 on `--grad` 浅端 `#f6c8d5` | **1.49** | 4.5 | ❌ 差 3 倍 |
| 白字 on `--grad` 深端 `#eba9bd` | **1.92** | 4.5 | ❌ |
| § 徽标白字 on 渐变浅端 | **1.49** | 3.0（图形） | ❌ |

证据：`app/globals.css:60-61` 定义 `--grad: linear-gradient(135deg, #f6c8d5, #eba9bd)`，
`app/globals.css:387-396` `.btn-primary { background: var(--grad); color: #fff; }`

**影响面（不是角落功能，是全部主要转化路径）**：发送、登录、创建账号、搜索、新对话、添加入库、采纳入库、应用切换、预览切分、测试。

一个刺眼的事实：**未选中态的次要按钮（`.btn-secondary`，墨蓝字/`5.03`）比主按钮（白字/`1.49`）清晰 3.4 倍** —— 视觉层级完全反了，用户会先看到次要按钮。

**三个可选修法（实测数据）**：

| 方案 | 做法 | 对比度 | 代价 |
|---|---|---|---|
| **B（推荐）** | 保留粉渐变，按钮文字改 `--ink` | **8.71 / 6.74** | 改 1 行 `color`，品牌视觉零损失 |
| C | 渐变收紧为单色 `#b8506c` | 4.77 | 失去渐变层次，且仍是"重色块" |
| A | 保留白字，渐变加深到 `#625055` | 7.51 | 变成莓红/玫瑰木，**不再是樱花粉** |

> 推荐 **方案 B**：只把 `.btn-primary` 的 `color: #fff` 换成 `var(--ink)`。理由：既达到 AA，又**保留了"樱花海"的全部品牌语义**，还能顺便解决"主按钮不够突出"的问题（深墨蓝字在浅粉底上的可读性远好于白字）。
>
> 同理适用于 `.logo-seal`（`globals.css:798-809`），它的白 `§` 在同一渐变上也是 1.49。

### 2.2 🟠 P1：同一界面里有三套粉色，token 体系已经漂移

扫描 `globals.css` 中裸 hex 的出现频次：

```
#ff8fa9  x5    ← 第二套粉（流式能量条/扫描光/呼吸点/光晕/body光斑）
#f56b8c  x2    ← 第三套深粉
#e894ac  x2    ← --accent（真正的 token）
裸 rgba() 共 93 处
```

证据对照：`globals.css:19` 定义 `--accent: #e894ac`，而 `globals.css:768` 的流式能量条硬写 `linear-gradient(180deg, #ff8fa9, #f56b8c, #ff8fa9)`，`globals.css:1010` 法条卡竖线 `#3d9be9→#ff8fa9`。

**用户能感知到的后果**：AI 气泡左侧的流式能量条（`#ff8fa9`）和它紧挨着的左竖线 `border-left: 3px solid var(--accent)`（`#e894ac`）是**两个不同的粉**，并排显示时会产生一条细微的色阶断层。这正是"说不清哪里不对劲"的那类脏。

修法：把 7 处裸粉替换为 `var(--accent)`，或显式定义 `--accent-bright: #ff8fa9` 并把"发光类动效"统一走它。二选一，不要两种并存。

### 2.3 P2：`--radius` 声称"全局统一 6px"，实际用了 4 种圆角

`globals.css:63-64` 注释写「圆角基元 · 全局统一 6px」，`tailwind.config.ts:33-35` 设 `borderRadius.DEFAULT = 6px`。
但源文件里：`rounded-lg`(8px)、`rounded-xl`(12px)、`rounded-2xl`(16px)、`rounded-full` **混用**。

建议：既然已有 token 意图，就在 Tailwind 里显式定义一个 scale（`sm: 4px / DEFAULT: 6px / lg: 10px / xl: 14px`）并把 `rounded-*` 收敛进去。现在是"有 token 之名，无 token 之实"。

### 2.4 P2：几处小但确定的视觉瑕疵

| 问题 | 位置 | 说明 |
|---|---|---|
| 侧栏会话项两行重复 | `chat/page.tsx:926` vs `:928` | 第一行渲染 `h.title \|\| h.preview`，第二行又渲染 `h.preview` —— 当 title 为空时两行**完全一样** |
| 装饰 § 几乎不可见 | `components/ui.tsx:69` | `text-[11rem]` @ `opacity 0.05` @ 容器内 —— 付出了巨大尺寸，视觉回报≈0 |
| `StatCard` 图标看不见 | `components/ui.tsx:57` | `text-accent`（对比度 2.08）+ `bg-accent-tint`（透明度 0.14）——图标极度虚淡 |
| Windows 上衬线体退化为宋体 | `globals.css:71` `--font-serif` | 字体栈在 Windows 命中 `SimSun`；SimSun **无真正的 Bold 字面**，`font-weight: 600` 会触发合成粗体（faux bold）发糊。建议在前插入 `"Source Han Serif SC"`，或标题改用 `"Songti SC"`→不存在的回退链改一下 |

---

## 3. 交互体验

### 3.1 🔴 P0：参考条文数据已经拿到前端，但一个字都没渲染

这是本次审计**最有价值的一条**，也是唯一一条"产品级缺陷"。

`Msg` 接口明确定义了该字段并注明用途（`chat/page.tsx:19`）：
```ts
sources?: { source: string; article: string }[]; // 参考条文（ADR-012 阶段2C：回答下方折叠展示）
```
SSE 回调里也确实写入了 state（`chat/page.tsx:675`）：
```ts
if (meta.sources?.length) patch.sources = meta.sources;
```
但全仓 grep `sources` 的**渲染侧使用结果为 0 处**。

后果：对一个法律 AI 而言，**"这条结论依据哪一法条"是产品的核心信任机制**。后端算出来了、网络传过来了、前端存进内存了，然后**丢在了半路**。用户只能依赖 AI 自称的引用，无法核对 —— 这恰好是法律场景最不能容忍的形态。

> 这是典型的"接了一半的线"。修复成本很低（在回答气泡下方加一组 `<details>` 折叠 chip 即可），价值极高。**建议列为第一优先处理项**，优先级甚至高于 P0 的按钮配色，因为它直接影响产品是否可信。

### 3.2 🟠 P1：`.btn-ghost` / `.btn-outline` 用了但从未定义 —— 按钮在裸奔

交叉扫描结果：

| 类名 | globals.css 定义 | 源码引用 | 后果 |
|---|---|---|---|
| `.btn-ghost` | ❌ 未定义 | `admin/page.tsx:523`（启用/禁用） | 只有 `.btn` 基座：无边框无背景，渲染成一段**认不出是按钮的裸文字** |
| `.btn-outline` | ❌ 未定义 | `admin/page.tsx:687, 690`（上一页/下一页） | 同上 |
| `.btn-ghost-dark` | ✅ 已定义 | **0 处引用** | 唯一的 ghost 变体是专为深色设计的，却没人用 |

证据：`globals.css:358-426` 只定义了 `.btn / .btn-primary / .btn-secondary / .btn-danger / .btn-ghost-dark`。

讽刺的是：团队为深色场景专门写了 ghost 变体却没用上，反而在白的 admin 后台用了两个**根本不存在**的变体。而且 `.btn-ghost` 挂的是**危险操作**（禁用他人账号）——一个看不出是按钮的控件承载了不可逆操作，这是可用性 + 安全双重问题。

### 3.3 🟠 P1：Enter/Ctrl+Enter 反直觉，且界面零提示

`chat/page.tsx:1360`：
```ts
if (e.key === "Enter" && e.ctrlKey) send();  // Enter 换行，Ctrl+Enter 发送
```

三个问题叠加：
1. **违背肌肉记忆**：ChatGPT / Claude / 微信 / Slack 全都是 Enter 发送、Shift+Enter 换行。这里是反的。
2. **零可见提示**：placeholder 是 `请输入法律问题…`，底部说明是免责声明，**没有任何一处告诉用户要按 Ctrl+Enter**。
3. **输入框在鼓励换行**：`rows={2}` + `resize-none`，视觉上明示"这是多行输入框"，进一步引导用户按 Enter。

建议：改成 **Enter 发送 / Shift+Enter 换行**，并在 placeholder 或按钮 title 里标注。若坚持保留 Ctrl+Enter，至少必须在 UI 上写出来。

### 3.4 🟠 P1：登录链路被 401 重定向打断成"点两次"

串联三个已知点得到一层 emergent bug：

1. `api.ts:43-45`：401 时 `window.location.href = "/login"` —— **整页硬跳转**，SPA 状态全丢。
2. `login/page.tsx:106-113`：未 `sealed` 时**只渲染一个印章**，表单在点击后才出现。
3. `login/page.tsx:44`：`handleSeal` 里 `await new Promise(r => setTimeout(r, 400))` —— 为看动画而设置的 **400ms 纯延迟**。

于是 token 过期的完整用户旅程是：**正在聊天 → 被整页踢到登录页 → 看到一个只有 § 和"钤 印 入 典"的屏幕 → 不知道发生了什么、也不知道要点它 → 猜着点一下 → 等 400ms 动画 → 才拿到登录表单**。

额外风险：`handleSeal` 判断用的 `user` 是闭包捕获值，而 `auth.tsx:33-44` 的会话恢复是**异步**的。若用户在 `/auth/me` 返回前点了印章，明明已有有效 token 也会被降级到表单（低概率 race，但真实存在）。

### 3.5 🟠 P1：流式期间可以点"管理后台"跳走，而其它三处都做了保护

代码里已有清晰的保护惯例 —— `newChat`(`:423`)、`selectConv`(`:438`)、`deleteConv`(`:465`) 全都有：
```ts
if (streaming) return; // 流式期间禁止切换会话，防消息污染/conversationId 错位
```
但侧栏的 `管理后台 →`（`chat/page.tsx:946`）—— **唯独它没有 `streaming` 保护**。

流式输出中点它 → 组件卸载 → `AbortController` 从未暴露给调用方（`api.ts:141-163`）无法取消 → 回来后对话处于半截状态。这是一致性缺口，补一个 `disabled={streaming}` 即可。

### 3.6 P1：输入区"自动增高"的样式意图落空了

`chat/page.tsx:1355`：
```tsx
className="input ... resize-none max-h-[120px]"
```
写了 `max-h-[120px]` **但没有配套的 auto-grow 逻辑**（没有 `onInput` 改 `style.height`）。同时 `resize-none` 又禁止了用户手动拖拽。

净结果：**textarea 被永久钉死在 2 行**，输入超过 2 行就在小框里滚动。`max-h-[120px]` 是一条永不生效的死样式。三者组合起来 = "设计意图（可增长到 120px）明确存在，但三种实现途径全被堵死"。

### 3.7 P2：其它交互项

- **触达目标偏小**：发送/上传/语音按钮为 `h-9 w-9`(36px) / `md:h-10 md:w-10`(40px)。Apple HIG 建议 44pt、Material 建议 48dp。聊天应用的发送按钮应 ≥44px。
- **移动端无输入区 tips**：改了 Enter 行为后建议在桌面显示快捷键提示。
- **Emoji 按钮缺状态语义**：`👍/👎`（`:1228-1229`）有 `aria-label` ✅，但缺 `aria-pressed`，按钮语义不完整。

---

## 4. 无障碍（贯穿多维度，单独成节）

### 4.1 🟠 P1：缺三件套，且是本产品最该有的东西

全仓 grep 结果：**`aria-live` = 0 处、`aria-modal` = 0 处、`role="dialog"` = 0 处。**

| 缺口 | 影响 |
|---|---|
| 流式回答区无 `aria-live` | **屏幕阅读器用户完全感知不到 AI 有没有回答**。对一个逐字流式输出的产品，这等于把它变成盲盒 |
| 法条速查面板（`:1389`）无 `aria-modal`/focus trap/ESC 关闭/背景锁滚 | 键盘用户进入后无法优雅退出；打开后焦点不进输入框（缺 `autoFocus`） |
| 移动端侧栏抽屉（`:900`）同上 | 同上 |
| 历史会话项是 `<div onClick>`（`:919-923`）而非 `<button>` | **键盘完全不可达** —— 无法 Tab 聚焦、无法 Enter 打开 |
| 登录页禁用注册 tab 是 `<div className="tab flex-1 cursor-not-allowed">`（`login:131`） | 渲染成半个可用 tab 的样式却不可点，视觉暗示与实际能力冲突 |

修法优先级：**先给 AI 回答容器加 `aria-live="polite"`（一行）**，这是投入产出比最高的一条。

### 4.2 🟠 P1：每日法条 5 秒自动轮播且无暂停控件 —— WCAG 2.2.2 不合规

`chat/page.tsx:331-344`：`setInterval(..., 5000)` 无限循环切换内容，`h-[3.5rem]` + `line-clamp-2` 固定高度，到点内容突变。

WCAG 2.2.2（Pause, Stop, Hide）明确要求：**自动更新且持续超过 5 秒的内容，必须提供暂停/停止/隐藏机制**。此外在两个实用的层面也站不住：
- 这是一段**需要被阅读的法律条文**，5 秒大概率读不完就被换掉；
- `prefers-reduced-motion` 的 CSS 兜底（`globals.css:163-172`）**只作用于 CSS 动画，对这个 JS `setInterval` 完全无效** —— reduced-motion 用户照样被强制轮播。

建议：移除自动轮播改为静态展示，或至少加暂停控件并在 reduced-motion 时停掉。

---

## 5. 动效

### 5.1 做得对的地方（先说，因为这部分质量确实高）

- 全部关键帧只动 `transform`/`opacity`，注释也明确写了"不触发布局"（`globals.css:175`）—— 不触发重排，不会掉帧。
- `prefers-reduced-motion` 有全局抹平兜底（`globals.css:163-172`）。
- 自动滚动在流式期间切成 `behavior: "auto"`，注释解释是为了避免"追着文字跑"的平滑动画卡顿（`chat/page.tsx:412-418`）—— 这种细节考虑很到位。
- `usePointerGlow` 走 CSS 变量而非 setState，且触屏设备通过 `(hover: hover)` 直接禁用。

### 5.2 🟠 P1（`imeline` 已在 §4.2 列 WCAG 合规项）

**每帧收到 token 都对整个累积文本重跑 8 条正则 + Markdown 渲染 + 全量替换 DOM**（详见 §7.1）——这既是性能问题，也让长回答的流式输出越来越"顿"。

### 5.3 P2：逐条消息的入场动画在长对话里变拖沓

`chat/page.tsx:1099, 1109`：每一条消息都挂 `.page-enter`（`fadeInUp 0.45s`）。
每次提问都会同时挂载用户消息和 AI 空消息，**各自播放 0.45s 动画**。累积到第 20 轮对话时，用户已经看了 40 次同样的动画 —— 这类"首次 helpful、重复 annoying"的动效应按 [frontend-flow 的 Gate 四问] 过滤：高频操作不该有动效。

建议：只给首屏/区块切换用，新消息即时出现或改 ≤150ms 的极短淡入。

### 5.4 P2：一批明确的死样式 / 死变量

| 类型 | 名称 | 位置 |
|---|---|---|
| 定义了未使用 | `.glass-card-strong` | `globals.css:271` |
| | `.glow-line` | `globals.css:280` |
| | `.done-seal` | `globals.css:960` |
| | `.law-popup` | `globals.css:318`（注释说"悬浮浮层"，但已改为内联展开，样式没删） |
| | `.section-mark-float` | `globals.css:595` |
| | `.btn-ghost-dark` | `globals.css:417` |
| | `@keyframes lineGrow` | `globals.css:228` |
| 提供支持但从未设置 | `--stagger` | `globals.css:309`（`.page-enter` 支持逐条延迟，全仓 0 处赋值） |
| | `--dur-med` | `globals.css:347-349`（`.card-hover` 用它，从未定义，永远走 fallback 250ms） |
| 永不可达的分支 | login 的 register 模式 | `login/page.tsx:64, 70-71, 121, 124, 148-153, 161`（注册 tab 是 div，无任何入口能切到 register） |

> `--stagger` 这条特别值得注意：它被**精心设计支持**（页面「支持逐条延迟」），但一次都没配上值 —— 是一个明确存在但未兑现的设计意图。要么补上，要么删掉，留着会让人误以为生效了。

---

## 6. 逻辑与正确性（确定的 bug）

### 6.1 🔴 P0：反馈状态跨会话错配

`chat/page.tsx:320` 定义、` :884` 写入：
```ts
setFbDone((s) => ({ ...s, [i]: rating }));   // i = 消息在 messages 数组中的下标
```
而 `newChat`(`:422-435`)、`selectConv`(`:437-461`)、`deleteConv`(`:464-482`) **三处都没有重置 `fbDone`**（它们重置了 `messages`/`conversationId`/`expandedLaw`/`selectedScope` 等几乎所有其它状态）。

**确定的复现路径**：
会话 A 第 3 条消息点 👍 → 切到会话 B → 会话 B 的第 3 条消息（内容完全不同）显示 **「已记录，谢谢反馈」且两个按钮被禁用**。

用数组下标作为跨状态的持久化 key，必然在数组重建时错位。`corrFor`/`corrText` 同源问题。

修法：改为按消息唯一 id 索引（后端 message 有 id），或在 `selectConv`/`newChat` 里一并清空。**后者一行改完，是止血做法**。

### 6.2 🟠 P1：`renderAnswer` 会把正文里所有星号静默删掉

`lib/annotate.ts:278`：
```ts
return out.join("\n").replace(/\*/g, "");
```
意图是清理 Markdown 残留符号，但手法是**全局无差别删除**。任何未被前面的 Markdown 分支消费的 `*` 都会被吃掉。

可被用户感知的损失例子：`违约金按日 0.05%*本金计算` → 渲染成 `违约金按日 0.05%本金计算`（乘号消失，语义变了）。
在法律/金额场景里，这是一个会改变语义的缺陷。

修法：只在行首 `#`、列表标记等**特定位置**清理，不要用全局 replace。

### 6.3 🟠 P1：英文双引号的"原文摘录"保护是死代码

`lib/annotate.ts:7` 定义 `QUOTE_RE = /"[^"]*"|「[^」]*」|“[^”]*”|'[^']*'/g`，
但 `lib/annotate.ts:51` 先执行 `const text = escapeHtml(raw)`，而 `escapeHtml`（`:17`）已把 `"` 转成 `&quot;`。

**结论：`QUOTE_RE` 的第一个分支在同一个函数内永远不可能命中。** 中文引号「」/“”分支和单引号分支不受影响。

后果：模型若输出 `"原文摘录"`（英文双引号），这段内容得不到占位保护，会被外层的高亮正则污染。
> 诚标注：**影响程度取决于实际模型是否输出英文双引号**，需运行时抓一段真实回答确认。但"这段正则必然不命中"是静态可证的。

### 6.4 P1：交互节点不一致

- **用展示文案判定状态的耦合**：`chat/page.tsx:1097` 用 `m.content.startsWith("出错了：")` 判断是否错误态 —— **用展示字符串做状态机**。任何以「出错了：」开头的正常回答都会被套红框 + 显示"未能完成本次请求"。应改用 `agentNote.kind === "error"` 这类结构化字段。
- **`clarifyRounds` 闭包自增**：`chat/page.tsx:660` `setClarifyRounds(clarifyRounds + 1)`，注释自己也承认"假设每轮一次"。
- **SSE 末帧残留**：`api.ts` 流结束时未调用 `decoder.decode()` 收尾，也未 flush `buffer`。若后端最后一帧不带 `\n\n`，该帧内容会被静默丢弃。

---

## 7. 性能

### 7.1 🟠 P1：流式渲染是 O(n²)

链路（`chat/page.tsx:645-651` → `:266` → `:270`）：
```
每个 SSE chunk
  → setMessages 整份拷贝
  → MessageHtml 重新执行 renderAnswer(累积全文)
      → annotate(): 从头跑 8 条正则
      → formatMarkdown(): 重新切行/解析标题/表格/列表
  → dangerouslySetInnerHTML 全量替换 DOM 子树
```

对一次 3000 字回答、按 ~20 chars/chunk 计约 150 帧，累计要处理约 **22.5 万字符**的正则 + Markdown + HTML 重建。长合同审查报告会更糟。

可行的低成本修法（按性价比排）：
1. **增量 append**：只对"最后一个未完成块"做渲染，已完成段落缓存其 HTML 片段（block-level memo）。
2. **抑制滚动锚定抖动**：给消息容器加 `overflow-anchor: none`（真实的 CSS 属性），或在滚动容器上加 `contain: content`（注意后者会影响 `position: fixed` 子元素的包含块，需实测确认无副作用）。
3. 流式期间暂停 `renderAnswer` 的正则阶段，改成追加纯文本，待 `final` 事件后再统一渲染一次 —— **用户几乎感知不到损失，收益是数量级的**。

### 7.2 🟠 P1：`background-attachment: fixed` 在移动端是已知性能陷阱

`globals.css:97`：`background-attachment: fixed`

在 iOS Safari 上这个值会被部分忽略或触发昂贵的逐帧重绘。而项目是**明确面向手机浏览器**的（PWA manifest + `apple-touch-icon` + FRP 公网访问 + `100dvh`/`pb-safe` 一堆移动端适配）。

同时 `body` 上叠了三层固定绘制：背景渐变 + `body::before` 光斑 + `body::after` 噪点（`mix-blend-mode: overlay`）。

建议：删掉 `background-attachment: fixed`，把渐变挪到已有的固定伪元素 `body::before` 里（它已经是 `position: fixed`，效果等同但走合成层，代价低得多）。

### 7.3 P1：滚动处理未节流

`chat/page.tsx:1001-1004`：每个 scroll 事件都 `setIsNearBottom(...)` → 整个 ChatPage（1441 行组件的完整子树）重渲染。
应加 rAF 节流，或改为只在跨越阈值时才 setState（布尔值本身已是天然去重，但仍会触发 reconciler）。

### 7.4 P2：其它

- `usePointerGlow` 每个 rAF 内 `getBoundingClientRect()` 强制同步布局（可用 `ResizeObserver` 缓存 rect）。
- 流式期 260ms 的 `codexIdx` setInterval 同样触发全树重渲染。
- 历史会话的每张图都独立 `loadMediaSrc` → blob URL，无懒加载/无 `loading="lazy"`。

### 7.5 🔴 P0：Service Worker 会在每次发版后造成白屏

`public/sw.js` 三个硬伤叠加：
```
:8   const CACHE = "fazhi-shell-v1";        // 缓存名硬编码，与构建产物无关 → 永不失效
:44  caches.open(CACHE).then(c => c.put(req, copy));  // 对每个 GET 都写缓存
:46  .catch(() => caches.match(req).then(m => m || caches.match("/")))  // 离线兜底返回旧 HTML
```
失效链：
1. 每次发版，`/_next/static/chunks/<新hash>.js` 被不断 put 进**同一个永不过期的 CACHE** → 缓存无界膨胀。
2. 一旦网络抖动/离线，Navigation 请求回退到 `caches.match("/")` → 返回**旧版本 HTML**，其中引用的旧 chunk 已在 CDN 上被删除 → **白屏**。
3. `install` 时预缓存的 `"/chat"` 同样锁定了当时的 chunk hash。

这是**最容易被漏测、上线后代价最大的一类问题**（本地 dev 从不注册 SW，测试环境也常常不复现）。

建议：CACHE 名注入构建 hash，或直接改用 Next 生态成熟的 `serwist` / `@ducanh2912/next-pwa`。若暂不换库，最低限度要让 navigation 请求的版本与静态资源版本绑定。

---

## 8. 其它 / 安全

| 级别 | 项 | 位置 |
|---|---|---|
| P1 | JWT 存 `localStorage`，任意 XSS 可直接读取 | `api.ts:7, 11, 16` |
| P2 | `dangerouslySetInnerHTML` 依赖自研转义（非 allowlist 消毒器）；`escapeHtml` 未转义 `'` | `chat/page.tsx:270` / `annotate.ts:12-18` |
| ✅ | **无正则注入 / 无 ReDoS**：`new RegExp` 只拼常量，用户输入从不进正则 | `annotate.ts:79, 150` |
| ✅ | **用户输入进 URL 均有 `encodeURIComponent`**（URL 注入面已封堵） | `api.ts:255, 320, 321` |
| P1 | 所有请求无超时、无 AbortController 外露 | `api.ts:39` |
| P2 | `logout` 只清本地，未调用后端吊销 | `auth.tsx:68-71` |

---

## 9. 分优先级落地路线（建议分批，不要一次全铺）

### 第 1 批 · 止血（半天，且几乎全是 1 行改动）
1. `.btn-primary` 与 `.logo-seal` 白字 → `var(--ink)`　　　　　`globals.css:388, 803`
2. `selectConv`/`newChat` 里 `setFbDone({})`　　　　　　　　　`chat/page.tsx:437, 422`
3. 给 AI 回答容器加 `aria-live="polite"`　　　　　　　　　　`chat/page.tsx:1144`
4. 侧栏"管理后台"加 `disabled={streaming}`　　　　　　　　`chat/page.tsx:946`
5. 补 `.btn-ghost` / `.btn-outline` 的定义（或改挂 `.btn-secondary`）　`globals.css`
6. `--law`/`--time`/`--money` 各加深 2~3% 到 AA 达标（观感不变，见 §10.2）

### 第 2 批 · 补完核心能力（1~2 天）
7. **把 `sources` 渲染出来**（回答下方折叠 `《法名》第X条` chip）　← 产品价值最高
8. Enter 发送 / Shift+Enter 换行 + UI 提示
9. Service Worker 缓存版本化
10. 拆掉 `replace(/\*/g, "")` 全局删星号
11. `background-attachment: fixed` 迁移到伪元素
12. 补 modal 三件套（ESC / focus trap / `aria-modal`）+ 历史会话项改 `<button>`

### 第 3 批 · 打磨（按需）
13. 流式渲染增量化（O(n²) → O(n)）
14. 输入区真正实现 auto-grow 到 120px
15. token 收敛：三套粉 → 一套 + 显式 `--accent-bright`
16. 清理 §5.4 的死样式/死变量/永不可达分支
17. 登录页：弱化"钤印"二次门禁，去掉 400ms 人为延迟
18. 删除每日法条自动轮播（或加暂停控件 + reduced-motion 停播）

---

## 10. 对抗性自审（写完方案后的自我质疑）

按你的要求做的审查。**我不信任自己的第一版结论**，以下是我主动找出的、可能推翻上述部分主张的地方。

### 10.1 本报告最大的局限：没有运行时证据

我没有执行 `npm run build`，没有起 dev server，没有截图，没有在真实浏览器里点过一次。**本报告 100% 基于静态阅读 + 色度计算**。因此：

- **凡我描述为"视觉效果"的，实际观感可能与计算不同**。对比度是数学事实，但"多层半透明玻璃叠加后的实际呈现色"我用的是近似实底 —— 例如 `bubble-ai` 是 `rgba(255,255,255,0.55)` 叠在海盐蓝渐变上，我按白色保守估算，**实际底色偏蓝，对比度会比 1.49 略好，但仍远低于 4.5**，结论方向不变。
- **§6.3（双引号正则失效）的实际影响未知** —— 取决于模型是否输出英文双引号。要确认需抓一段真实 SSE 输出。
- **§7.1（O(n²)）我没有实测过帧率**。22.5 万字符是静态推算。是否"用户可感知地卡"取决于设备。**这是我报告里最需要被实测修正的一条。**

### 10.2 我在 §9 里差点给了一个糟糕的建议 —— 值得单独说

我最初的自动化脚本对"不达标的语义色"给出的修法是**暴力加深到 4.5**，结果是：
```
--law   #2f7bc4  →  #0e253b  (15.60)   ← 近黑色
--time  #b9621a  →  #381d08  (15.59)   ← 近黑色
```
**这组值是错的，不能采用。** 它会直接摧毁 `globals.css:31-34` 明确建立的「色相即语义」设计（蓝=法条权威/橙=时限/绿=金额/粉=关键数字）——把四种语义色全部压成黑色，等于让最能帮助法律场景快速扫读的那套视觉编码彻底失效。

正确的做法是求**刚好过线的临界值**：
```
--law    #2f7bc4 (4.42) → #2e79c0 (4.55)   仅深 2%，肉眼不可辨
--time   #b9621a (4.35) → #b56019 (4.51)   仅深 2%
--money  #1f8a63 (4.31) → #1e8660 (4.53)   仅深 3%
```
这三个是**临界不达标**，微调零成本。

但另三个是**本质问题**：`--num`(2.27)、`--accent`(2.27)、`--jade`(2.54) 要达到 AA 需加深 27~31%，那已经是另一个颜色了。**所以它们不能靠"调深"修，必须换形态** —— 而这个项目自己就给出了现成答案：同一个文件里 `.hl-time`（`:940-943`）用的就是 `浅底 + 深字` 的 chip 形式，而 `.hl-num`（`:945-947`）只用了 `color`。**把 hl-num 对齐成 hl-time 的形式即可，"关键数字"的高亮反而会更醒目。** 这比我第一版的建议好得多。

### 10.3 有几条我可能过度主张了

- **§2.1 我把按钮配色列为 P0**：如果产品团队刻意追求"极轻的樱花粉"作为品牌签名，那么改为深墨蓝字（方案 B）确实会把"轻盈感"变成"稳重感"。**这是真实的品牌取舍，不是纯技术问题。** 我的推荐理由是：在 CTA 上，可点击性 > 氛围感。但这个判断权应该在产品owner手里。折中方案是用方案 C（`#b8506c` 单色实底，白字 4.77），既达标又保留重色块的 CTA 重量。
- **§3.3 Enter/Ctrl+Enter**：这不是客观 bug，是**约定 vs 直觉**之争。若目标用户群是已经在用某个固定工具的用户，改反而会造成新的不适。但"界面上零提示"这一点无论如何是缺陷。
- **§5.3 逐条消息入场动画**：纯主观。"0.45s 的仪式感"可能是刻意追求的。我把它降到 P2 就是这个原因。
- **§7.2 `background-attachment: fixed`**：修法的收益依赖真机。在桌面 Chrome 上几乎无差别。**这条应标注为"移动端优先因而重要"，而不是普适缺陷。**

### 10.4 反过来：有哪些我可能没找到的问题

诚实列出本报告的盲区，避免"没提到 = 没问题"的错觉：

1. **没有评论区/详情页**：我审的是 `/`（重定向）、`/login`、`/chat`、`/admin` 四个路由。若有其它页面不在本次范围。
2. **没有审查加载态与错误态的完整矩阵**：`chat/page.tsx:420` 的 `if (loading || !user) return null` 会有一段纯空白（无骨架屏），我只在 §3.4 间接提到，没有系统评估各页面的 loading/empty/error 三态是否齐全。
3. **没有后端契约对齐**：我只看了前端怎么用，**没有比对 FastAPI 实际返回的字段**。例如返回的 `sources` 结构与前端定义是否一致、SSE 帧格式是否有额外事件未被消费 —— 这些我无法在不跑服务的情况下确认。
4. **没有量化真实 bundle 体积 / FCP / LCP**：61% 的性能断言（§7）缺少度量基线。**建议真正动手前先埋一次 Lighthouse**，用真实数字替换我的推算。
5. **没有评估 Tailwind purge 是否漏 scanning**：我已确认 `content` 覆盖了 `app/` 与 `components/`（`tailwind.config.ts:12`），这没问题，但动态拼接的类名是否有遗漏未逐一验证。

### 10.5 一句话总结自审

> **我最有把握、不依赖运行时验证的，是这五条**、§3.1(sources 未渲染)、§3.2(btn-ghost 未定义)、§6.1(fbDone 错位)、§7.5(SW 白屏) 这五条 —— 它们全部是可在源码中逐行验证的事实，且都有明确的最小修法。其余各条的可信度随"是否需要真机观测"递减，动手前值得先花一次 Lighthouse + 一次真机点查把它们坐实。**

---

*本报告为只读审计，未修改项目任何既有文件。取证用的 3 个临时脚本（`scripts/_audit_contrast.py`、`_audit_deadcss.py`、`_audit_fix*.py`）已在生成后删除，工作树保持干净。*
