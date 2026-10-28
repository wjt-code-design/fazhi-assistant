# BLOCKED — agent quality below existing_rag under pre-registered v1.1.0 rubric

## Frozen candidate boundary
- Release ID: `legal-agent-v1-20260905-005`
- Git revision: `3ba4aafb2ada244a8dc21621f5f2c9f1c8ee267b`（评估器 v1.1.0 预注册提交）
- Backend image: `sha256:f1ec2e001a2ac87d71917358adc3f61d817bb0de92d3c4351c5409d1c126360e`
- Frozen case-set SHA-256: `0202a54820d99b715f6ae6b28fdadcc62e9edec45d1203ae48fd305b0c4356ae`
  （v1.1 题集：新增 acceptable_clarification_keywords 人工策展，策展在重采集前完成）
- Validated release-manifest SHA-256: `37fa80b699e3dbab83f6d788aaadd10393ec84d024328c9d5ae94f7c1a30ab7e`
- Runtime provider/model: LongCat-2.0（文本）+ qwen3.5-omni-flash（vision/voice）
- Reviewer: 执行者本人（用户 2026-09-06 改派，独立性豁免披露同 004——自证风险自认）

## 预注册变更（先于任何新测量）
评估器 v1.1.0：clarification_correct = 逐字匹配 OR 题集策展关键词命中。
依据=004 对抗性审查（逐字匹配使合法改述性反问永不得分）。rubric_hash `6f258472…`。

## 采集与结果
- 双路径 40/40 OK（RAG 与 Agent 各 20，无失败行）；agent_routed 5/20（与 004 路由一致）。
- 指标：existing_rag quality 0.3583（0.525/0.55/prec1.0），agent quality 0.275
  （0.375/0.35/**prec 0.4**——v1.1.0 使 2/5 合法改述反问获得计分）。
- 门禁（release-check-20260906.json）：**allowed=false,
  AGENT_QUALITY_BELOW_EXISTING_RAG**。安全项双方全 0。

## 终局判定（不再做第二轮口径调整——避免结果驱动的阈值购物）
剩余差距的三要素均已量化：① gate 将 15/20 路由 fast path（agent 系统在该题集上
≈RAG+5 次反问）；② 全题"期望反问"的题集设计 vs 反问在答题制评分下天然吃亏；
③ 同路由采样波动。这三者都不是"改阈值"能诚实解决的——需要数据所有者批准
**新的评测设计**（混合期望题集 + 按设计路由）作为下一代评测，或接受
"Agent 与 RAG 同级、安全项全 0、按 gate 谨慎路由"的现状定位。
- 部署安全位保持：AGENT_ENABLED=false / AGENT_TRAFFIC_PERCENT=0。
- 阶段 H（恢复演练）按交接仍以门禁通过为前提——未执行。
