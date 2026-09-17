# 前端 chat 链路八维审查报告 — 2026-09-13

> 范围：`frontend/app/chat/page.tsx`、`frontend/lib/api.ts`、`frontend/lib/scope.ts`、`frontend/lib/annotate.ts`、`frontend/lib/usePointerGlow.ts`（全读）；`frontend/app/admin/page.tsx`（扫读）。
> 基线：`tsc --noEmit` exit 0 ✅；`npx next build` exit 0 ✅。
> 对照计划：`docs/superpowers/plans/2026-09-13-agent-frontend-b.md`（B1-B4 实现中）。

## 结论汇总

| 维度 | 结论 |
|---|---|
| 质量 | 整体扎实（memo/缓存上限/卸载清理等历史对抗项保留良好）；2 处类型放宽、1 处注释与行为矛盾 |
| 逻辑 | SSE 事件分支正确；B1 解析契约与后端 `_scope_selection_question` 对齐；1 处 dev/prod 路径不一致 |
| 优化 | 无新增冗余；既有 nocache 上限（lawCache/mediaCache=40）+ 淘汰正确 |
| 矛盾 | quota 拉取路径与健康检查不一致；annotate 头部注释「引号内永不标注」与还原逻辑（引号内也高亮）矛盾 |
| 死代码 | `bottomRef` 仅声明+渲染、从未参与逻辑 → 冗余 |
| 耦合 | chat/page.tsx 1300+ 行单文件聚合度高（属历史已知，不在本轮拆分）；B1-B4 增量未新增耦合 |
| 性能/渲染 | MessageHtml memo 自定义比较正确（点法条卡不触发全量重标注）；流式回退正确处理 |
| 可访问性 | 按钮均有 aria-label；B1 候选卡为 button 有文本内容；无阻塞项 |

## P1（0 个，本轮无）

无运行时正确性/安全级缺陷。

## P2（1 个，本轮修复）

- **P2-1 [chat/page.tsx:344-349] quota 拉取用相对路径**：
  `fetch("/api/utility/quota")` 与健康检查 `fetch(\`${API_URL}/api/health\`)`（L295）不一致。开发环境
  `NEXT_PUBLIC_API_URL` 未配置 → API_URL=localhost:8000，而相对路径会打到 Next dev 端口（3000）→ 404 →
  `setQuotaWarn(null)` 静默失败 → **配额警告横幅在开发环境永不显示**，且与后端真实状态脱节。
  修复：统一加 `API_URL` 前缀。

## P3（记录 + 合并进 B1-B4 实现）

- **P3-1 [chat/page.tsx:278,1109] `bottomRef` 死代码**：仅 `useRef` + 渲染空 div，从未被任何逻辑引用
  （自动滚动走 `scrollRef.scrollHeight`）。删除声明与空 div（高度 0，不影响布局）。→ 本轮一并清理。
- **P3-2 [annotate.ts:54] 注释与行为矛盾**：头部「引号内永不标注」与 L152 还原逻辑
  （引号内原文摘录也做金额/时限/倍数高亮）矛盾；L2-3 的说明才是当前真实行为。
  修复注释文案（零行为变化）。→ 本轮一并清理。
- **P3-3 [api.ts:208-236] agent error 事件双 onMeta**：error 分支调用 onMeta 后，尾部
  `if (conversation_id/sources) onMeta(...)` 合并分支会再触发一次（第二次无 agent_event，无行为影响）。
  **决策：不合并**——事件流零行为变化防回归（沿用计划 P3-2 决策）。仅记录。
- **P3-4 [chat/page.tsx:414,531,546] 类型放宽 `any`**：历史消息映射 + Web Speech 回调。
  历史消息映射可定义 `HistoryMsg` 收紧；Web Speech 无类型声明维持 `any`。→ bottomRef 清理时顺手收紧第 414 处。
- **P3-5 单文件聚合**：chat/page.tsx 1300+ 行（语音/图片/文件/法条面板/流式/反馈/场景卡全在一个组件），
  属历史已知状态，本轮不拆分（防回归）；记录备查。
- **P3-6 [admin/page.tsx]** 扫读无新缺陷：权限守卫（L151-156）、分区懒加载（L159-182）正确。
- **P3-7 [scope.ts] B1 契约**：`parseScopeCandidates` 的「编号从 1 连续递增」校验与后端生成格式
  （`1. 争点甲\n2. 争点乙`）精确对齐；跨行/乱序/前缀缺失均回退 null → 纯文本降级（符合 spec）。
  风险已收敛：解析失败不影响行为。

## 与 B1-B4 计划（Task 3/4）的偏差修正

- **Task 4 Step 1 `toggleScope` 反模式（P2-2，实现时修正）**：计划的 updater 内嵌
  `setSelectedScope((prev)=>{... setInput(...); return next;})` 在 updater 内执行 setState
  （StrictMode 双执行 + 闭包读旧 `input`，且依赖副作用次序）。改为从组件作用域读 `selectedScope`
  先算 `next`，两个 setState 平级顺序调用。已并入 Task 4 实现。
- **Task 3 Step 4 轮次计数**：`clarifyRounds+1` 的闭包语义在「每轮 doSend 最多一条澄清事件」前提下成立
  （SSE 单线程顺序 + 每条 SSE 内单澄清），实现保持计划语义。

## 门禁证据

- `npx tsc --noEmit` → exit 0
- `npx next build` → Compiled successfully，全 route 静态生成（/chat 18 kB ✅）