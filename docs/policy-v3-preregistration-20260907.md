# policy v3 预注册（G-6 · 不阻塞 Phase 9 灰度）

> 状态：**预注册**（路线图，不阻塞早期小比例灰度）· 日期：2026-09-07
> 关联：规划书 §①.5 L3 · SSG 证据目录 `release-evidence/legal-agent-v1-grayscale-20260907/`

## 1. 目的

把本次灰度期使用的 **Supplemental Safety Gate（SSG，L2 附加阻断门禁）**在灰度验证成功后
升格为**正式 release policy v3**，使其从"附加检查层"变为之后所有候选的强制准入标准。

## 2. 与现有 policy 的关系

| 层 | 现状 | v3 目标 |
|---|---|---|
| v2（L1） | 正式政策：Agent ≥ RAG − 1/30 + 安全=0，**冻结** | 保持不动（历史语义不变更） |
| SSG（L2） | 附加阻断门禁（S1-S9 + Failure Matrix + Reuse Rule） | **并入 v3**，成为正式 policy 语义 |
| v3（L3） | 预注册 | 升格后：SSG 语义写死为正式 policy，runbook 脱离"附加"字样 |

## 3. v3 需包含的 SSG 语义（升格清单）

1. ASRG S1-S9 门槛（S1/S3/S6/S9 硬；S2/S5/S8 门；S7 运行时与 X/N ADR 定稿值）；
2. Historical Evidence Reuse Rule（§②.5）；
3. Evidence Invalidation Matrix（§⑦）；
4. `safety_readiness_check` 作为机械放行判定（非人工口头结论）；
5. fail-closed 与回滚条件（不含 policy refusal）。

## 4. validation candidate 预注册（material change 触发）

- **触发条件**：模型变更 / 知识库 material 变更 / 路由规则变更 / 安全规则新增等（见 §⑦ 全量失效项）。
- **流程**：走新候选周期（采集→评估→SSG 证据→safety_readiness_check）→ v3 语义下判 release。
- **不触发**：仅文档/观测代码/阈值 ADR 非行为变更（§⑦ 边界外）。

## 5. 状态

- **不阻塞 Phase 9 灰度**：灰度放行唯一条件=L1(v2) AND L2(SSG) AND ProdPrereq；
  v3 在灰度成功后、由数据所有者确认升格；
- 升格动作（新增 `release-policy-v3.json` + runbook 措辞剥离"附加"）留待灰度数据成熟后执行。

---
*本文件为 Phase 8 交付（预注册件）；实际升格需灰度后数据所有者拍板。*