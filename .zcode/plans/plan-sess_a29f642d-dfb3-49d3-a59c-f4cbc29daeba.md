# 方案 B 执行计划 v2（经自审修订）：发布定位修订 + 009 周期

## 自审修订摘要（相对上版）
1. 容差 0.05→**0.033（单题容差 1/30）**：消除结果感知推导；依据=套件最小单位+实测同系统方差 0.011
2. **删除 clarification_precision 门**：n=4 统计不成立、与 v1.2.0 题级计分重复、可博弈
3. **Phase 1 升级为硬前提 + 决策树**：contract-14 修不好则 009 大概率失败，必须先行
4. 新增检查器改动不变量清单与治理链要求

## Phase 1（先行，硬前提）：contract-14 第二失败形态诊断
- 采样该 query 15 次，抓原始输出分类失败形状，决策树：
  a) 机械缺陷（围栏变体/JSON 尾巴）→ 证据化修复（先红后绿）
  b) 非逐字 quote 归一化差异 → 归一化包含比较（保留防编造事实目的）
  c) prompt 能力边界 → time-box 2 轮分解器提示词迭代（prompt-bundle 变更入候选）
  d) time-box 内不可修 → 如实执行 Phase 2，预期 BLOCKED，结论交还所有者
- 验收：失败题在修复后代码通过（红绿证据）；或 (d) 书面结论

## Phase 0：政策修订 v2（rubric v1.2.0 冻结不动）
- policy：complex_task_quality threshold 改 "agent >= existing_rag − 1/30"；
  safety_findings = 0 不变；**不新增 precision 门**（v1.2.0 已题目级计分）
- check_agent_release.py 三处同步：_REQUIRED_RELEASE_POLICY_METRICS 阈值语义、
  L701 容差比较、单测 fixtures；**不变量**：其余 ~38 失败码与四项安全硬门禁一字不动（全失败路径测试回归证明）
- 预注册文档 docs/release-policy-v2-rationale.md：四代证据表 + 容差推导 + 定位声明
  （Agent=诚实升级件而非质量升级件）+ 用户批准记录（本计划批准即签署）
- 回滚：政策+检查器单提交可整体 revert

## Phase 2：候选 009 周期
- 重建镜像（含 Phase 1 修复）→ 009 目录（题集 86066616 不变、rubric v1.2.0 不变）→
  30×2 采集 → 绑定（新题关键词补策展留痕）→ artifacts/双报告（worktree 009）→
  审计（豁免披露延续）→ 门禁

## Phase 3：门禁判定后
- allowed=true → 阶段 H 恢复演练+四场景 → deployment runbook 交付态 → 终报
- allowed=false → 如实终报（单题容差下仍败=采样不利或 Phase 1 (d) 路径），决策交还

## 验收结果
- 形式：release-check allowed=true 且原因列表空、全套检查链绿（非跳过）
- 实质：30×2 新鲜采集、失败行保留、绑定决策留痕、审计披露延续、索引边界快照一致
- 文档：rationale 文档、009 STATUS、矩阵/PROGRESS 更新入库

## 任务边界（不做）
- rubric 冻结（无 v1.3）；失败行保留；样本 ≥20；不碰生产与部署安全位；
  额外字段类"修复"不做；R 系列其他登记项不动；审计豁免每次显式披露

## 量化预期（诚实版）
008 实测 agent 0.5833 含可识别损失 contract-14(-0.033)+误路由(-0.033)；
修复前者 → ≈0.616 vs rag 0.625 → 单题容差内通过；采样不利则失败。
**两种结果都接受，无 v1.3。**