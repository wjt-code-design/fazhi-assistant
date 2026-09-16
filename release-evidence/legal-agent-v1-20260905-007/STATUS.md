# BLOCKED — 连续三代（005/006/007）门禁一致：agent quality < existing_rag

## Boundary
- Release ID: `legal-agent-v1-20260905-007`
- Git revision: `ba8a5691fb3b30f511ce04a2621cb234b0aea400`（围栏剥离修复 + pre-run 失败日志）
- Backend image: `sha256:e7bb6a1a209cb39a33f2a125c0f33ce624a191da48ed17dcf4bf55cfda6f01ab`（tag `:007`）
- Case-set: 同 006（`86066616…`，v1.2 混合 30 题）
- Manifest: `eae35fc9b56a2b090dfdb7baa8d9ca3daec9b512cc18ffe7a8068eb234ca5016`
- Reviewer: 执行者本人（用户改派，豁免披露同前）

## 结果
- 采集：RAG 30/30；Agent 29/30（contract-comparison-14 仍 ISSUE_DECOMPOSITION_INVALID
  一次——存在**第二失败形态**：非围栏类校验失败，修复后该题也曾成功，属逐次方差）
- 指标：rag 0.4167（0.65/0.60），agent 0.3611（0.483/0.50）——修复使 agent 从 0.344↑
  且 prompt-injection-19 被救回；安全项双方全 0
- 门禁（release-check-20260906.json）：**allowed=false, AGENT_QUALITY_BELOW_EXISTING_RAG**

## 三代评测汇总（诚实结论）
005（全反问题集）0.275 vs 0.358 → 006（混合题集）0.344 vs 0.406 → 007（+围栏修复）
0.361 vs 0.417。agent 单调改善但 rag 同步采样上涨；差距稳定在 0.05-0.08。
构成：① 反问题在答题制评分下结构性吃亏（按 case 设计这恰是正确行为）；
② gate 路由 ~5/30 进 agent；③ 剩余 1 例第二失败形态；④ 采样方差。
**发布 BLOCKED 是冻结政策下的正确结论。**解禁需要数据所有者对"评测设计哲学"
做决策（反问该被奖励到什么程度），这不是工程问题而是产品定位问题。
- 部署安全位不变：AGENT_ENABLED=false / AGENT_TRAFFIC_PERCENT=0。
