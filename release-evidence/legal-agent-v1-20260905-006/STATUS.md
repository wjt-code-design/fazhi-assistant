# BLOCKED — agent quality below existing_rag（差距已收窄至可工程化修复项）

## Frozen candidate boundary
- Release ID: `legal-agent-v1-20260905-006`
- Git revision: `b0c229d33c37261d3e79fde946d51c0e66c9d66b`（v1.2 混合题集预注册，经用户批准）
- Backend image: `sha256:a103d45954c4a6d88edbc7074e77e1634722435e9bca4d9c139b2044d79984ea`（tag `:006`）
- Frozen case-set SHA-256: `86066616d7bba2c7f3699523e8ae3766d7e6c52231136e22f5b9822833f07469`
  （30 题 = 20 期望反问 + 10 期望作答；10 题预期条文 10/10 在冻结知识库验证）
- Validated release-manifest SHA-256: `bb8a1b69de589e9e58a5df2156f9034b3f598584feedfb4b3f16cd3b6f479faa`
- Reviewer: 执行者本人（用户改派，独立性豁免披露同前）

## 采集与结果
- 双路径 60 请求：RAG 30/30 OK；Agent 28/30 OK + 2 失败
  （contract-comparison-14、prompt-injection-19 均 ISSUE_DECOMPOSITION_INVALID——
  003 STATUS 已知限制 2 的间歇性分解器风险首次在正式采集中成批显现，失败行保留）。
- 指标：existing_rag quality 0.4056（0.617/0.60/prec1.0），
  agent quality 0.3444（0.533/0.467/prec0.25）。安全项双方全 0。
- 混合题集验证成功：10 道作答题 9 道 fast path 直接高质量作答（284-1020 字符、
  零反问——事实完整时正确行为即作答 ✓）；1 道（guarantee-period-a4）被 gate
  路由进 Agent 后反问（事实已完整，反问属误路由）。

## 门禁（release-check-20260906.json）：allowed=false, AGENT_QUALITY_BELOW_EXISTING_RAG

## 剩余差距的精确归因（0.344 vs 0.406，差 0.061）
1. 2 例分解器间歇失败（2 题计 0）：**可工程化修复项**——评估器外的产品缺陷
   （候选 003 已知限制 2 的正式采集实证）。修复方向（预注册建议，006 不动）：
   分解器对传输级失败做一次有界重试，或对可确定解析的轻度偏差（如尾随文本）
   做显式宽松解析——均需先红后绿与新一候选周期。
2. 1 题误路由反问（guarantee-period-a4）：gate 复杂度判定与题集期望不一致。
3. 20 题共享 fast path 上的采样波动（温度 0.7）。

## 结论
混合期望评测设计（用户批准）使两系统对比公平化，差距从 0.083 收窄至 0.061，
且归因从"结构性口径问题"转变为"可修复的工程缺陷+采样噪声"。
发布保持 BLOCKED；建议下一候选（007）修复分解器间歇失败后重测。
部署安全位不变：AGENT_ENABLED=false / AGENT_TRAFFIC_PERCENT=0。
