# 前端 Agent 体验适配（B1-B4）实现计划 — 2026-09-13

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 纯前端实现 4 项 Agent 体验适配：B1 争点范围选择卡片、B2 澄清消息差异化、B3 失败态结构化、B4 澄清轮次指示。

**Architecture:** 新增纯函数模块 `frontend/lib/scope.ts`（解析/拼接，供组件引用，解析失败降级为现有纯文本行为）；`lib/api.ts` 仅透传 error 事件的 `code`（零行为变化）；`chat/page.tsx` 扩展 `Msg` 模型 + 事件接线 + 渲染分支；`globals.css` 增补少量主题样式。

**Tech Stack:** Next.js 14 / React 18 / Tailwind 3.4 / TypeScript 5.3。无测试框架 → 门禁 = `tsc --noEmit` 零错误 + `next build` exit 0。

## Global Constraints

- 后端契约零改动（git diff 不含 backend/）；frozen release-evidence 不动。
- 视觉只用现有主题色（accent 樱粉 / sea 海盐蓝 / ink 墨蓝 / mist 淡蓝灰 / jade 玉绿 / error 红）。
- 不引入新依赖、不加测试框架、不新增第二发送路径（所有回复经输入框 `doSend`）。
- "所有澄清回答仍走现有 `doSend(content)`，带 `pendingAgentRun`（run_id + state_version）"不变。
- 失败=本轮结束：收到 error 清空 pendingAgentRun（现有行为保持）。
- B4 不编造分母：后端未暴露澄清总轮数，轮次用"第 N 轮"计数 chip（无 total）。

---

### Task 1: `frontend/lib/scope.ts` 纯函数（解析 + 拼接）

**Files:**
- Create: `frontend/lib/scope.ts`

**Interfaces:**
- Produces: `ScopeCandidate { number:number; text:string }`、`parseScopeCandidates(prompt:string):ScopeCandidate[] | null`（失败回 null）、`buildScopeAnswer(selected:number[]):string`（升序、英文逗号分隔、1-5 个）。

- [ ] **Step 1: 新建文件**

```typescript
// 争点范围选择：解析后端澄清 prompt → 候选卡片数据；再把选中编号拼回后端接受的回答文本。
// 契约来自 backend/agent/controller.py _scope_selection_question（2026-09-13 固定）：
//   "本次请求分解出 N 个法律争点，超过单次可处理上限 5 个。请从中选择最多 5 个争点（输入编号，用逗号分隔，例如：1,3,5）：\n1. 争点甲\n2. 争点乙"
// 解析失败返回 null → 调用方降级为纯文本追问（不做卡片，行为不变）。

export interface ScopeCandidate {
  number: number;
  text: string;
}

export const SCOPE_MAX_SELECTION = 5;

/** 仅当 prompt 命中范围选择特征（前缀 + 至少一条 "N. " 行）时解析；否则返回 null。 */
export function parseScopeCandidates(prompt: string): ScopeCandidate[] | null {
  if (!prompt.includes("本次请求分解出")) return null;
  const lines = prompt.split("\n");
  const candidates: ScopeCandidate[] = [];
  for (const line of lines) {
    const m = line.match(/^\s*(\d+)\.\s*(.+?)\s*$/);
    if (!m) continue;
    const n = Number(m[1]);
    // 要求编号从 1 连续递增（防乱序行混入）
    if (candidates.length === 0 && n !== 1) return null;
    if (candidates.length > 0 && n !== candidates[candidates.length - 1].number + 1) return null;
    candidates.push({ number: n, text: m[2] });
  }
  if (candidates.length === 0) return null;
  return candidates;
}

/** 升序 + 英文逗号分隔；参数由调用方保证 1-5 个、均在候选范围内。 */
export function buildScopeAnswer(selected: number[]): string {
  return [...new Set(selected)].sort((a, b) => a - b).join(",");
}
```

- [ ] **Step 2: 校验**

Run: `tsc --noEmit`（在 `frontend/`）
Expected: exit 0

- [ ] **Step 3: Commit**

```bash
git add frontend/lib/scope.ts
git commit -m "feat(frontend): scope.ts 争点范围选择解析与拼接纯函数（B1）"
```

### Task 2: `lib/api.ts` 透传 error code

**Files:**
- Modify: `frontend/lib/api.ts`（`ChatMeta` 接口 + `streamChat` 的 error 分支）

**Interfaces:**
- Consumes: 现有 `ChatMeta`、`streamChat` 签名。
- Produces: `ChatMeta.error_code?: string`；error 事件带 `conversation_id`/`sources`/`agent_event:"error"`/`error_code`。

- [ ] **Step 1: 扩展 ChatMeta**

```typescript
export interface ChatMeta {
  conversation_id?: number;
  sources?: { source: string; article: string }[];
  agent_run_id?: string;
  agent_state_version?: number;
  agent_event?: "clarification" | "final" | "error";
  error_code?: string; // 后端 `{type:"error", code}` 的 reason_code（B3 映射用）
}
```

- [ ] **Step 2: error 分支透传 code**

原文（lib/api.ts 约 L208-212）：
```typescript
        if (p.error) onError(p.error);
        else if (p.type === "error") {
          onError(p.message || "Agent 无法安全完成本次请求");
          onMeta({ agent_event: "error" });
        }
```
改为：
```typescript
        if (p.error) onError(p.error);
        else if (p.type === "error") {
          onError(p.message || "Agent 无法安全完成本次请求");
          onMeta({
            conversation_id: p.conversation_id,
            sources: p.sources,
            agent_event: "error",
            error_code: typeof p.code === "string" ? p.code : undefined,
          });
        }
```
> 说明：`conversation_id`/`sources` 补上是为了与既有 content 事件的 meta 一致；后续
> `if (p.conversation_id !== undefined || p.sources !== undefined)` 的合并 onMeta 保留不动
> （P3-2 不做合并——事件流零行为变化，防回归）。error 分支此时已带 meta，合并 onMeta 因其
> 无 `agent_event` 不影响 pending 逻辑（chat/page.tsx 分支判断 `agent_event` 值）。

- [ ] **Step 3: 校验**：`tsc --noEmit` exit 0

- [ ] **Step 4: Commit**：`git add frontend/lib/api.ts && git commit -m "feat(frontend): error 事件透传 reason_code（B3 输入）"`

### Task 3: `chat/page.tsx` 状态与事件接线

**Files:**
- Modify: `frontend/app/chat/page.tsx`（import、`Msg`、`ChatPage` 状态、`onMeta`/`onError` 回调、重置路径）

**Interfaces:**
- Consumes: `scope.ts` 的 `parseScopeCandidates`/`buildScopeAnswer`/`ScopeCandidate`；`ChatMeta.error_code`。
- Produces: `Msg.agentNote?: {kind:"clarification"; round:number} | {kind:"error"; code?:string}`、
  `Msg.scopeCandidates?: ScopeCandidate[]`；`clarifyRounds`（React state，本轮澄清计数）。

- [ ] **Step 1: 扩展 Msg 类型**

`Msg` 接口新增两个可选字段：
```typescript
  scopeCandidates?: ScopeCandidate[]; // 范围选择候选（卡片渲染用）；随消息存，天然随新会话/切换重置
  agentNote?: { kind: "clarification"; round: number } | { kind: "error"; code?: string };
```

- [ ] **Step 2: 状态与计数器**

`ChatPage` 内新增 state（放在 `const [pendingAgentRun, setPendingAgentRun]` 附近）：
```typescript
  // 本轮 Agent 澄清计数（B4：无分母，后端未暴露总轮数；newChat/selectConv 重置）
  const [clarifyRounds, setClarifyRounds] = useState(0);
```

- [ ] **Step 3: onMeta/onError 接线**

`streamChat` 的 `onMeta`（L613-637 附近）改为：
```typescript
          if (
            meta.agent_event === "clarification" &&
            meta.agent_run_id &&
            meta.agent_state_version !== undefined
          ) {
            setPendingAgentRun({ runId: meta.agent_run_id, stateVersion: meta.agent_state_version });
          } else if (meta.agent_event === "final" || meta.agent_event === "error") {
            setPendingAgentRun(null);
          }
```
在其**后**追加（同一次 onMeta 内串联）澄清/错误标注的补丁逻辑：
```typescript
  // 以下由外层调用处（新增）执行——见 Step 4 说明
```
（Step 3 实际无独立改动：pending 逻辑不动；见 Step 4 统一接线）

- [ ] **Step 4: 在新一轮消息创建时给最后一条 assistant 消息补 agentNote/scopeCandidates**

`doSend` 内、`setStreaming(true)` 之后、`await streamChat` 之前，把回调逻辑扩展：
在 meta 回调（现有 L613-637 的 `(meta) => {...}`）内，替换为：
```typescript
        (meta: ChatMeta) => {
          setMessages((m) => {
            const copy = [...m];
            const last = copy[copy.length - 1];
            const patch: Partial<Msg> = {};
            if (meta.sources?.length) patch.sources = meta.sources;
            // B2/B4：澄清标注
            if (meta.agent_event === "clarification") {
              patch.agentNote = { kind: "clarification", round: clarifyRounds + 1 };
              setClarifyRounds(clarifyRounds + 1);
            } else if (meta.agent_event === "error") {
              patch.agentNote = { kind: "error", code: meta.error_code };
              // 失败=本轮结束（B3 决策）：pending 已在上方清空，轮次计数复位
              setClarifyRounds(0);
            } else if (meta.agent_event === "final") {
              patch.agentNote = undefined;
              setClarifyRounds(0);
            }
            if (last) copy[copy.length - 1] = { ...last, ...patch };
            return copy;
          });
          if (meta.conversation_id != null) {
            setConversationId(meta.conversation_id);
            setActiveId(meta.conversation_id);
          }
          if (
            meta.agent_event === "clarification" &&
            meta.agent_run_id &&
            meta.agent_state_version !== undefined
          ) {
            setPendingAgentRun({ runId: meta.agent_run_id, stateVersion: meta.agent_state_version });
          } else if (meta.agent_event === "final" || meta.agent_event === "error") {
            setPendingAgentRun(null);
          }
        },
```
> 作用域注意：`clarifyRounds` 的读写出现在 setMessages 回调内——React 闭包捕获的 `clarifyRounds`
> 是本次 render 的值；澄清是逐帧顺序事件，同一轮 render 内不会并发多次 clarification（SSE 单线程
> 顺序解析），round = clarifyRounds+1（自增语义）正确；`setClarifyRounds(c+1)` 后下一 render 生效。
> 极端流式下若一次性连续多个事件（同一 tick），React 18 批处理只取最后一次 state——但澄清事件
> 由后端单条发送且每 tick 一条，安全。

同时在 doSend 的 `onChunk`、`onError`、`onRestart`、`onSteps` 保持原样。**onError 回调**（L639-644）
中追加失败标注（因为 `{type:"error"}` 走 onError 分支，onMeta 独立触发）：
```typescript
        (err) => {
          setClarifyRounds(0);
          setMessages((m) => {
            const copy = [...m];
            copy[copy.length - 1] = {
              ...copy[copy.length - 1],
              agentNote: undefined,
              content: `出错了：${err}`,
            };
            return copy;
          });
        },
```
> `{p.error}`（普通 RAG 错误）也会走到这里：清轮次、去标注（回到普通错误气泡渲染），无 pending 残留（非 agent 路径本就没有）。

- [ ] **Step 5: 范围选择候选接入（B1 事件侧）**

在 meta 回调内、`agent_event === "clarification"` 分支中，补充候选解析：
```typescript
            if (meta.agent_event === "clarification") {
              patch.agentNote = { kind: "clarification", round: clarifyRounds + 1 };
              setClarifyRounds(clarifyRounds + 1);
              // B1：解析候选（失败降级纯文本，clearing 不做卡片，pending 逻辑不变）
              patch.scopeCandidates = parseScopeCandidates(meta.)
                || undefined;
            }
```
> 说明：`onChunk(p.prompt)` 会把 prompt 文本写进 content（api.ts 现逻辑）。**范围选择时将
> content 也保留为提示文本会被卡片+提示并存**——为防重复，Step 5 采用"卡片替代提示文本"：
> 见 Task 4 渲染决策（候选存在时省略 content 纯文本，只渲染卡片 + 引导文案）。

- [ ] **Step 6: 重置路径**：`newChat()`、`selectConv()`、`deleteConv` 中补 `setClarifyRounds(0)`
  （三处：newChat L388-399、selectConv L401-423、deleteConv 内 `if (activeId === id)` 分支）。

- [ ] **Step 7: 校验**：`tsc --noEmit` exit 0

- [ ] **Step 8: Commit**：`git add frontend/app/chat/page.tsx && git commit -m "feat(frontend): 澄清/错误事件接线与轮次计数（B2/B3/B4 状态）"`

### Task 4: 渲染（候选卡片 / 澄清气泡 / 错误气泡 / 轮次 chip）

**Files:**
- Modify: `frontend/app/chat/page.tsx`（assistant 渲染分支）+ `frontend/app/globals.css`（少量样式）

**Interfaces:**
- Consumes: Task 1 `parseScopeCandidates`…、Task 3 的 `Msg.agentNote/scopeCandidates`、`clarifyRounds`。
- Produces: 渲染语义——候选卡片（点击填输入框）、澄清气泡样式、错误气泡样式、轮次 chip。

- [ ] **Step 1: 候选卡片交互（填输入框，方案 A）**

在 `ChatPage` 内新增 handler：
```typescript
  // B1 方案 A：点选卡片 → 编号列表填入输入框（可手改），仍走现有发送按钮
  const [selectedScope, setSelectedScope] = useState<number[]>([]);
  function toggleScope(n: number) {
    setSelectedScope((prev) => {
      const next = prev.includes(n) ? prev.filter((x) => x !== n) : [...prev, n];
      if (next.length > SCOPE_MAX_SELECTION) return prev; // 超过 5 个：拒绝本次切换
      setInput(next.length ? buildScopeAnswer(next) : input); // 填/清输入框
      return next;
    });
  }
```
> 边界：达 5 后再点 → 拒绝（不更新），输入框保持；"清空选择"链接 = 重置 selectedScope 且
> setInput("")。

- [ ] **Step 2: assistant 渲染分支改造**

原有 `m.content ? <MessageHtml/> : (streaming…检索期)` 之前，插入层级（在 `{m.content ? ... : ...}` 处
按优先级分派）：
```tsx
{/* B1：范围选择候选卡片（替代提示文本展示；失败时 m.scopeCandidates 为 undefined 走原逻辑） */}
{m.scopeCandidates && m.scopeCandidates.length > 0 ? (
  <div className="scope-pick space-y-2">
    <p className="text-xs text-slate">本次请求分解出 {m.scopeCandidates.length} 个争点，单次最多处理 {SCOPE_MAX_SELECTION} 个。点击选择（可多选），编号会自动填入输入框：</p>
    <div className="grid grid-cols-1 gap-1.5">
      {m.scopeCandidates.map((c) => (
        <button
          key={c.number}
          type="button"
          disabled={streaming}
          onClick={() => toggleScope(c.number)}
          className={`scope-item flex items-start gap-2.5 rounded-lg border px-3 py-2 text-left text-sm transition-colors ${
            selectedScope.includes(c.number)
              ? "border-sea bg-sea/10 text-ink"
              : "border-mist bg-white/60 text-ink hover:border-sea"
          } ${streaming ? "opacity-60" : ""}`}
        >
          <span className={`mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-xs font-semibold ${selectedScope.includes(c.number) ? "bg-ink text-white" : "bg-sea text-white"}`}>
            {c.number}
          </span>
          <span className="leading-snug">{c.text}</span>
        </button>
      ))}
    </div>
    <div className="flex items-center justify-between text-xs">
      <span className="text-slate">已选 {selectedScope.length}/{SCOPE_MAX_SELECTION} 个{selectedScope.length > 0 ? `（${buildScopeAnswer(selectedScope)}）` : ""}</span>
      {selectedScope.length > 0 && (
        <button type="button" onClick={() => { setSelectedScope([]); setInput(""); }} className="text-slate underline decoration-dotted hover:text-error">清空选择</button>
      )}
    </div>
  </div>
) : (
  <>
    {m.content ? <MessageHtml content={m.content} expanded={expandedLaw} i={i} /> : (…原检索期三态…)}
  </>
)}
```
> 原文 `m.content ? <MessageHtml/> : (streaming && i===last ? 检索期 : "")` 分支整体包进 `else`。

- [ ] **Step 3: 澄清气泡样式（B2）**

assistant 消息外层：当 `m.agentNote?.kind === "clarification"` 时，给气泡 div 加
`border-sea/50` 并插入顶部标签行：
```tsx
{m.agentNote?.kind === "clarification" && (
  <div className="mb-1.5 flex items-center gap-2">
    <span className="rounded-full border border-sea/60 px-2 py-0.5 text-xs font-medium text-sea">Agent 澄清</span>
    <span className="text-xs text-slate">第 {m.agentNote.round} 轮</span>
  </div>
)}
```
气泡类：`${m.agentNote?.kind === "clarification" ? "border border-sea/50" : ""}` 叠加到 `bubble-ai`。

- [ ] **Step 4: 错误气泡样式（B3）**

`onError` 写入的 content 以 `"出错了："` 开头且 `agentNote` 被清空 → 需在渲染层区分：
增加 `const isErrorMsg = !m.agentNote && m.content.startsWith("出错了：");`，气泡类加
`border border-error/40`；顶部插 `error` 徽标"未能完成"；并将 `error_code` 映射提示
（B3 表格）渲染在尾部。映射函数（模块级）：
```typescript
// B3：reason_code → 可读提示（chat_integration error code；无 code 用通用文案）
function agentErrorHint(code?: string): string {
  switch (code) {
    case "ISSUE_CLAIMS_MISSING":
      return "模型未能生成可引用的法律依据，请换一种问法或简化问题。";
    case "UNKNOWN_MISSING_INFORMATION":
    case "MISSING_FACT":
      return "信息不足，建议补充时间、金额、主体等关键事实后重发。";
    case "UNSUPPORTED_CITATION":
    case "NON_CANONICAL_CITATION":
      return "未能从法律库引用到准确条文，建议换个表述重新提问。";
    default:
      return "";
  }
}
```
> 注意：`agentNote.kind==="error"` 在 Task 3 Step 4 中被 onError 清掉了——为保证错误码可展示，
> onError 回调里改为**保留** `agentNote:{kind:"error", code}` 或单独存 `lastErrorCode`。
> 决策：保留 `agentNote = { kind: "error", code: lastErrorCode }`（onMeta 先写、onError 后执行会覆盖
> ——onMeta 与 onError 都触发时：onMeta 写 error agentNote，onError(L639) 又把它覆盖为 undefined）。
> **修正**：onError 回调不再清 agentNote，改为合并保留 error 标注；普通 RAG `{p.error}` 路径
> 无 onMeta，此时 agentNote 为 undefined → isErrorMsg 依 content 前缀即可。onError 改：
> ```typescript
> (err) => {
>   setClarifyRounds(0);
>   setMessages((m) => {
>     const copy = [...m];
>     const last = copy[copy.length - 1];
>     if (last) copy[copy.length - 1] = { ...last, content: `出错了：${err}` };
>     return copy;
>   });
> }
> ```
> 保留 `last.agentNote`（error code 已在其中，普通路径 undefined）。

- [ ] **Step 5: globals.css 样式**

在文件末尾追加：
```css
/* B1/B2/B3/B4：范围选择卡片 / 澄清轮次 / 错误提示（全主题变量） */
.scope-pick .backdrop { backdrop-filter: none; } /* 兼容占位，无实际作用，可省 */
```
> 实际只需少量：现有 glass-card/btn 系列已够；如需可省。计划标注：**若 tailwind 内联类已覆盖
> 所有样式，则不追加任何 css（留空提交）**——保持零死样式。

- [ ] **Step 6: 校验**：`tsc --noEmit` exit 0；`next build` exit 0

- [ ] **Step 7: Commit**：`git add frontend/app/chat/page.tsx frontend/app/globals.css && git commit -m "feat(frontend): 渲染——范围选择卡片/澄清标签/失败态/轮次指示（B1-B4）"`

### Task 5: 全量验证 + 自查 + 最终提交

- [ ] **Step 1: 回归验证**

Run:
- `frontend> .\node_modules\.bin\tsc.cmd --noEmit` → exit 0
- `frontend> npx next build` → exit 0

- [ ] **Step 2: 自查清单（核对代码）**

1. 范围选择降级：`parseScopeCandidates` 非范围 prompt → null → 无卡片、原纯文本追问不变。
2. 澄清标签不误伤普通回答：只有 agentNote.kind==="clarification" 才渲染标签。
3. streaming 期间候选卡片 disabled；达 5 个拒绝切换。
4. newChat/selectConv/deleteConv 均 `setClarifyRounds(0)`。
5. 后端契约未动：`git diff HEAD -- backend/` 为空。
6. 无新依赖：`git diff HEAD -- frontend/package.json` 为空。

- [ ] **Step 3: Commit（如有 css/遗漏）**：说明合并进 Task 4 提交，最终无独立提交。

---

## Self-Review 记录

1. **Spec 覆盖**：B1（Task1/3/4）、B2（Task3/4）、B3（Task2/3/4）、B4（Task3/4）全部有对应任务；spec §5 映射表在 Task4 Step4；§10 边界（零后端/零依赖/单发送路径）在 Constraint 与 Task5 Step2 落实。
2. **占位符扫描**：无 TBD；Task4 Step5 明确"若不需要样式则留空"（不是占位而是显式门控）。
3. **类型一致**：`ScopeCandidate/parseScopeCandidates/buildScopeAnswer`（Task1）在 Task3/4 引用名称一致；`Msg.agentNote` 两种 kind 与渲染分支一致；`ChatMeta.error_code`（Task2）在 Task3 消费。
4. **修订**：B4 由分数进度条改为无分母轮次 chip（后端未暴露 total，防编造）；P3-2（SSE 双 onMeta 合并）明确不做，防回归。