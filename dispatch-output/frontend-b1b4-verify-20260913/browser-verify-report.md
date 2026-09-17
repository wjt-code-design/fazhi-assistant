# 前端 B1-B4 浏览器级验证报告 — 2026-09-13

> 验证对象：`frontend/app/chat/page.tsx` 的 B1（范围选择卡片）/B2（澄清标签）/B3（失败态徽标）/B4（轮次 chip）真实浏览器渲染。
> 环境：真实服务（隔离宿主 serve.py @ 127.0.0.1:18124，AGENT_ENABLED=true，qwen3.8-flash，guard 19.82 元）+ next dev @ 3000。
> 过程：真实登录 → 发送 6 个不同类型问题 → DOM 取证（截图工具被节流，用 snapshot/evaluate 取证）。

## 结论速览

| 项 | 结果 | 证据 |
|---|---|---|
| 登录 + 页面渲染 + 配额横幅 | ✅ PASS | 登录成功转 /admin；chat 页渲染正常；**配额横幅显示**（P2-1 API_URL 修复在真实环境生效） |
| 普通问答回归（fast_path） | ✅ PASS | 借钱/欠薪/辞退/二手房 4 个请求均出完整六段式回答（《》引用正确） |
| B3 失败态渲染 | ✅ **发现真实 bug 并修复** | 两条真实超时错误 → 修复前徽标缺失 → 修复后徽标正确显示 |
| B1 范围选择卡片 | ⚠️ 未能端到端复现 | Agent 8 争点分解耗时 62-63s > 前端 60s 无数据看门狗 → 澄清事件被拦截 |
| B2 澄清标签 / B4 轮次 chip | ⚠️ 未能端到端复现 | 同上（澄清事件未及到达；渲染逻辑已静态审查 + tsc/build 绿） |

## 关键发现（真实 bug，浏览器验证抓到的静态审查漏项）

**B3 徽标条件用错**：修复前 [page.tsx] 徽标渲染条件是 `m.agentNote?.kind === "error"`，
但普通 RAG 失败路径（如连接超时）agentNote 为 undefined、仅 content 前缀「出错了：」——
`isErrorMsg`（用于边框）已覆盖两类，而徽标仍只认 agentNote error → **错误气泡有红边框但没徽标**。
修复：徽标条件改为 `isErrorMsg && (...)`，code 提示仍仅 agentNote error 时显示（`09c49e3`）。
复验：两条超时错误消息均显示「未能完成本次请求」徽标 ✅。

## 过程记录

1. 起隔离宿主（serve.py，18124，qwen3.8-flash）→ EVALUATION_READY，guard 19.82
2. 起前端（next dev 3000，API_URL 覆盖指向本地 → 登录页品牌页 → 登录）→ admin token 生效跳 /admin
3. 测试请求（全部真实模型调用，成本见下）：
   - 请求 1/2（8 争点辞退复杂案）：`agent_path` MULTI_ISSUE，**分解+修复耗时 62-63s** → 前端 60s 无数据看门狗先中断 → 前端显示「出错了：连接超时，已中断」→ B3 失败路径真实触发
   - 请求 3/4/5/6（单-多争点、信息量不等）：`fast_path` SINGLE_ISSUE_QUERY，19-30s 出完整回答 → 回归 PASS

## 防幻觉核验（show your work 五连问）

1. **数字怎么来的**：路由（agent_path/fast_path）与耗时来自后端日志（legal.chat 条目，ms 字段）；徽标存在性来自浏览器 evaluate DOM 查询（`innerText.includes('未能完成本次请求')`）；会话数来自页面 data-msg-index 计数。
2. **能复现吗**：是——独立宿主 + 真实模型可重跑；徽标修复前后差异在 DOM 查询中直接可对比。
3. **亲历红/绿**：是——修复前徽标 false（`hasBadge:false`），修复后 true；均为第一手 DOM 取证。
4. **期望独立**：徽标预期来自 spec B3 设计（两类错误统一失败态）；取证不做 LLM 判定，纯 DOM 断言。
5. **已知限制**：截图工具被节流（offscreen），未产出截图文件，以 DOM 文本快照代替；B1/B2/B4 端到端受前端 60s 无数据看门狗限制（Agent 分解慢），非渲染层缺陷（渲染逻辑经 tsc/build + 静态审查）。

## 成本

账本 `dispatch-output/frontend-b1b4-verify-20260913/cost-ledger.jsonl`：6 轮请求预估累计
约 0.02 元级（qwen3.8-flash 每轮 ~0.0039 元 + 免费 reranker），guard 余量充足。端口已关、服务已停。

## 附带发现（记录，不修——超出 B1-B4 范围）

- **前端 60s 无数据看门狗 vs Agent 长任务**：qwen3.8-flash 下 8 争点分解耗时可超 60s，且分解阶段无 SSE 帧 →
  前端提前中断。若真实部署也如此，用户会看到「连接超时」而非澄清流程（fail-closed 提示正确，
  但澄清可用性受影响）。该看门狗是历史对抗审计设计（防 SSE 挂死），建议留待部署体验评估时专项处理。
- 一条超时消息反馈区仍显示 👍👎（普通 RAG 错误保留反馈按钮）——符合「非 agent 路径保持原行为」的既有设计。

## 复验（r2，2026-09-13，grilling 后 A 方案落地）

**变更**：`IDLE_TIMEOUT` 60s→180s（提交 `f87375f`）。复验目的：确认 8 争点 Agent 长任务的澄清/范围卡片能在新窗口内到达。

**结果（首次端到端全绿）**：
- 发送 8 争点辞退案 → **「Agent 澄清 / 第 1 轮」标签渲染（B2/B4）**
- **「本次请求分解出 8 个争点」范围选择卡片渲染，8 张候选卡（B1）**
- 分步点击 3 张卡 → 「已选 3/5 个（1,2,3）」+ 输入框自动填「1,2,3」（方案 A，B1 交互验证通过）
- 30s 时仍在检索未被 60s 旧窗口打断（新 180s 生效的直接证据）

> 备注：同步循环点击 3 张卡只记录到 1 张，是同一 tick 内多次点击触发 React 闭包陈旧（测试手法），真实用户离散点击正确累计——非代码缺陷。

**成本（r2 独立账本 `frontend-b1b4-verify-r2-20260913/cost-ledger.jsonl`）**：1 次 8 争点 agent 请求，qwen3.8-flash，约 0.01-0.02 元级。端口已关、服务已停。

## 门禁

- `tsc --noEmit` exit 0；`next build` exit 0（B3 修复后重跑）
- `git diff HEAD -- backend/` 为空；`frontend/package.json` 未动
- 提交：`09c49e3`（B3 徽标修复，+2/-2）