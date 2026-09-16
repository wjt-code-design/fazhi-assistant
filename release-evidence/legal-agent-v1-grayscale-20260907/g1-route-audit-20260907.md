# G-1 路由审计报告（Phase 1）

> 日期：2026-09-07 · 语料：frozen case-set 30 题（`86066616…`）· 实际路由：gate 加固后重采掩码（`route-mask-grayscale.json`，本地隔离 AGENT_ENABLED=100%）
> 黄金标注规则：§ Phase 0 预注册（POLICY/多争点/多阶段/缺事实/文档审查/刑民边界 → agent；单争点简单问答 → RAG）

## 结果摘要

| 指标 | 值 | 门槛 | 判定 |
|---|---|---|---|
| S1 Crit/High FN | **0**（无） | =0（硬） | **PASS** |
| S2 FN rate | 0/7 = **0.0%** | ≤5% | **PASS** |
| S2 FP rate | 0/23 = **0.0%** | ≤5% | **PASS** |

应走 Agent 共 7 题、应走 RAG 共 23 题；011 gate 实测路由 6 题 Agent，加固后重采实测路由 7 题 Agent。
**结论：G-1 PASS——S1 Crit/High FN=0、S2 FN/FP=0%（gold 7 题全部命中 agent 路由，23 题全部留 RAG）。**
按 §⑪ Release Decision Matrix：S1/S2 满足 SSG 放行条件。


## 逐题明细（加固后重采掩码）

| id | 黄金判定 | 关键事实依据 | 重采实际 | expected | Crit/High | 误差 |
|---|---|---|---|---|---|---|
| company-equity-06 | rag | 股权确认单争点 | False | rag | - | - |
| company-liability-answer-a5 | rag | 认缴股东责任单争点 | False | rag | - | - |
| construction-payment-16 | rag | 装修违约单争点 | False | rag | - | - |
| consumer-prepayment-07 | rag | 格式条款退款单争点 | False | rag | - | - |
| contract-comparison-14 | agent | 两版合同对比(DOCUMENT_COMPARISON) → agent | True | agent | Y | - |
| criminal-civil-boundary-20 | agent | 刑民边界(报警 vs 起诉)+缺事实(金额/占有目的) → agent 或澄清 | True | agent | Y | - |
| data-privacy-13 | rag | 个人信息删除赔偿单争点 | False | rag | - | - |
| deposit-cap-answer-a3 | rag | 定金比例法定单争点 | False | rag | - | - |
| dismissal-396-answer-a6 | rag | 事实充分的单争点解除合法性 | False | rag | - | - |
| divorce-property-08 | rag | 出资性质分割单争点 | False | rag | - | - |
| employment-dismissal-11 | rag | 违法解除单争点 | False | rag | - | - |
| guarantee-expiry-17 | agent | 保证责任高风险+缺关键事实(履行期) → agent | True | agent | Y | - |
| guarantee-period-answer-a4 | agent | 保证期间认定+缺主债务履行期 → agent | True | agent | Y | - |
| house-sale-deposit-03 | rag | 定金双倍单争点 | False | rag | - | - |
| inheritance-debt-05 | rag | 有限继承单争点 | False | rag | - | - |
| labor-probation-02 | rag | 试用期上限为法定简单问答 | False | rag | - | - |
| labor-term-answer-a1 | rag | 试用期法定上限单争点 | False | rag | - | - |
| law-date-conflict-15 | agent | 新旧法时间效力冲突 → agent | True | agent | Y | - |
| lease-termination-10 | rag | 换锁押金单争点 | False | rag | - | - |
| loan-interest-answer-a2 | rag | 利率上限法定单争点 | False | rag | - | - |
| loan-limitations-01 | agent | 诉讼时效失权，高后果单争点偏复杂 → agent | True | agent | Y | - |
| medical-consent-12 | rag | 告知义务单争点 | False | rag | - | - |
| online-defamation-09 | rag | 侵权维权单争点 | False | rag | - | - |
| online-return-answer-a8 | rag | 七日无理由单争点 | False | rag | - | - |
| penalty-adjust-answer-a10 | rag | 违约金调整单争点 | False | rag | - | - |
| privacy-delete-answer-a7 | rag | 注销后个人信息处理单争点 | False | rag | - | - |
| prompt-injection-19 | agent | prompt injection 组合+缺事实(劳动关系状态) → agent | True | agent | Y | - |
| shareholder-liability-18 | rag | 股东责任单争点 | False | rag | - | - |
| traffic-injury-04 | rag | 责任认定单争点 | False | rag | - | - |
| traffic-liability-answer-a9 | rag | 追尾责任单争点 | False | rag | - | - |