# Owner ADR：Agent 定位变更下 L1 质量门对放行语义的豁免观察（方案 A）

> **权威版本：`docs/ADR-20260907-l1-exemption.json`（结构化，checker 机械校验依据）**
> 本 md 为人读摘要；两者不一致时以 JSON 为准。
> **决策人**：数据所有者（项目 owner）
> **决策日期**：2026-09-07
> **生效范围**：单候选 `legal-agent-v1-grayscale-20260907`（commit `4e6950a814…`）
> **ID**：ADR-20260907-L1-EXEMPTION

## 1. 现状（冲突事实）

1. 放行公式（规划书 §①.5）：`GRAYSCALE ALLOWED = L1(v2) AND L2(SSG) AND ProdPrereq`。
2. L1（policy v2 质量门）现实判定：009 allowed=true；010/011 allowed=false
   （011：agent 0.5167 < rag 0.6167 − 1/30）。最终候选代码基于 011 → L1 为 BLOCKED。
3. 但 008-011 期间 Agent 行为代码几乎无本质差异（仅引用格式/生成约束等小瑕疵），
   质量分在 0.49-0.62 区间随样本波动——质量门对"安全护栏"定位不稳定、不具区分力。
4. 同步的 SSG 安全门（L2）已全绿：`safety_readiness_check` RESULT=READY
   （S1-S9 全部机械验证 PASS，独立审核 haimeng 签署 PASS）。

## 2. 决策依据

- `docs/decision-agent-position-20260907.md`：8 代 440 次调用方向从未反超 RAG，
  但安全项全 0、反问诚实、引用精确 → 定位收敛为"高风险咨询安全护栏（宁不答、不错答、不编造）"；
- `docs/decision-checklist-agent-20260907.md`：9 项共识（含以安全为发布核心）；
- 规划书 §0.3 P1："用质量指标给安全增强件设准入 = 尺子量错"；
- 009 单题容差门禁曾通过（说明质量门在护栏定位下敏感于随机波动）；
- SSG 证据链路与本 ADR 同目录（G-1~G-5 + Freeze + 独立签署 PASS）。

## 3. 决策内容

1. **L1（policy v2 质量分门槛）对 Agent V1 放行语义豁免为"记录观察项"**：
   - 不再作为 Agent 放行的硬阻断；
   - v2 评估与质量分**继续照常运行并记录**（上线后质量追踪用），不复用为阻断门；
   - v2 文件与评估器 v1.2.0 **一字不改**（冻结红线保持）。
2. **Agent 放行真实准入 = L2(SSG) 全绿 + ProdPrereq（环境/授权/R8/回滚）**。
3. **RAG 快路径**继续受 v2 质量门约束（本豁免不波及）。
4. 豁免仅在规划书 §①.5 公式的 L1 判定节点生效；policy v3 升格（Phase 8 预注册）后，
   以 v3 正式语义取代本豁免。

## 4. 不作的事（红线确认）

- ✗ 不改 `release-policy.json` / v2 政策文件；
- ✗ 不改评估器 v1.2.0 或 rubric；
- ✗ 不伪造 011 的 allowed=true；L1 记录保持 BLOCKED（豁免记录在本 ADR，不篡改历史）；
- ✗ 不把质量分从运行追踪中移除。

## 5. 生效确认

本 ADR 由数据所有者确认（方案 A）后生效，作为 evidence-manifest 的 owner_decision 记录。
`readiness_checker` 对本 ADR 的校验**不是"文件存在即可"**，而是机械验证结构化 JSON 的字段
（schema / adr_id / decision=APPROVED / owner / scope.candidate_commit_sha / l1_original_result=BLOCKED /
exemption.type=QUALITY_GATE_ONLY / traffic_ceiling_percent / expiry_conditions 非空 / content hash 与
manifest 绑定一致）——文件存在不等于豁免有效。

### 5.1 豁免治理（防止"临时例外永久化"）

**失效条件（任一触发即自动失效）**：
1. policy v3 正式生效；
2. Agent 行为代码实质性变更；
3. 模型版本变更；
4. system/safety prompt 变更；
5. 工具权限变更；
6. 关键安全指标退化；
7. SSG 任一项 PASS→FAIL；
8. 超过规定灰度周期；
9. 灰度流量超过上限。

**灰度流量边界**：初始 1%，本 ADR 允许上限 **5%**；5%→25%→50%→100% 的任何进一步扩量
必须重新做 release decision，不得沿用本 ADR。

**最小功能性底线（utility floor，不恢复综合质量门槛）**：
catastrophic wrong=0、fabricated citation=0、unsafe confident answer=0、required clarification ≥100%、
unnecessary refusal 非阻断观测。

**回滚触发器（kill switch）**：fabricated citation>0 / critical safety failure>0 / unauthorized tool>0 /
high-risk confident hallucination>0 / SSG invariant violation>0 / P0/P1 生产事故>0 → 立即停止灰度回退 RAG；
普通质量问题连续 N 个窗口超阈 → 暂停扩量。