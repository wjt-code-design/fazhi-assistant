# 剩余风险表（交接 6.1 交付项，2026-09-06）

状态基线：候选 005（manifest `37fa80b6…`）；HEAD `ddf4a25`。
规则：只要存在 BLOCKED 项，交接结论就是"未全部完成"，本文档逐项列明风险与责任边界。

## R1 发布门禁未通过（已解除 2026-09-07：009 候选 v2 政策 allowed=true）
- 事实：`agent quality 0.275 < existing_rag 0.3583`（005，预注册 v1.1.0 口径），
  `allowed=false, AGENT_QUALITY_BELOW_EXISTING_RAG`。
- 定性（对抗性审查）：评估口径与 gate 路由的结构性产物，非 Agent 能力差距；
  安全项双方全 0。
- 缓解：部署安全位 `AGENT_ENABLED=false / AGENT_TRAFFIC_PERCENT=0` 保持不变；
  系统在 gate 下仅复杂题路由 Agent 且 fail-closed。
- 解除条件：数据所有者批准新一代评测设计（混合期望题集+按设计路由）后新候选周期；
  或修订发布政策定位。

## R2 审计独立性豁免（中，治理）
- 事实：数据所有者 2026-09-06 改派执行者本人审计（004/005 两代），自证风险自认
  并写入 STATUS；haimeng 原始要求被豁免。
- 缓解：全部审计依据（trace/绑定决策/报告）已打包可复核；换回独立审计人只需
  替换 agent-audit.json 重跑门禁。
- **恢复路径核验（2026-09-07）**：`check_agent_release.py` 对审计只校验
  `reviewer.role == "joint-independent-review"` + manifest sha + 逐 case trace_ref/decision
  （`agent_audit_evidence.py` schema 对 reviewer.id 仅约束格式不校验真实身份）。机制上
  「替换 haimeng 签署版 agent-audit.json → 重跑门禁」路径畅通。
- **纪律边界**：执行者不得代填 haimeng 签名（伪造独立审计声明）；须由 haimeng
  真实复核并签署后由所有者启用。

## R3 阶段 H 恢复演练未执行（已解除 2026-09-07：diag/drill-h-009/DRILL-RECORD.md 四场景+恢复+回滚全过）
- 事实：交接以门禁通过为前提——前提不满足，诚实未执行；备份/恢复工具链
  （backup_data.py 及其测试）存在且绿。
- 解除条件：R1 解除后按 deployment-v1.md §1 执行。

## R4 逐条法律复核未做（中，法律正确性）
- 事实：`law_as_of=2026-08-01` 仅为数据所有者确认的入库日边界，未做全量逐条
  人工复核（交接原样保留的限制）；月度治理程序已建（law-updates-monthly.md）。

## R5 评测口径深层设计问题（中，度量）
- 事实：全题"期望反问"的题集 vs 答题制评分 vs gate 路由三者的张力未解决；
  clarification_precision 0/0:=1.0 的语义对不能反问的系统有利。
- 缓解：v1.1.0 已修复逐字匹配的最严重偏差；进一步改动需预注册+数据所有者批准。

## R6 反问预算死路（低-中，产品）
- 事实：`agent_max_clarifications=2` 两轮反问后第 3 次 resume 返回 409；
  重叠反问未消解（004 实测）。产品决策项。

## R7 多模态质量未验证（低，范围）
- 事实：图片/语音链路端到端 PASS（合成样张）；合同截图逐字转写、真人语音
  质量未验证（矩阵标 BLOCKED，阶段 J 专项）。

## R8 供应链与运维缺口（低-中，2026-09-07 实扫 + Risk Accepted 批准更新）
- SBOM 为 pip freeze 替代（179 包）；**CVE 扫描已集成**（`requirements-dev.txt` 含
  pip-audit；`.github/workflows/ci.yml` 步骤 `pip-audit -r requirements.txt`，2026-08-02 落地，
  交接 4.4.4「未集成」描述已过时）。
- **实扫基线（2026-09-07，pip-audit + OSV，venv 全量）**：意外发现**82 漏洞 / 10 包**，
  比早前记录的 starlette/transformers 两条链更全。全量清单 `release-evidence/
  legal-agent-v1-grayscale-20260907/r8-audit-20260907.json`。
- 分类与处置（记录：`r8-disposition-20260907.json`）：
  - 真实可达（需 accept）：`pypdf 5.9.0`（41 条，用户上传 PDF 解析路径实证）、
    `starlette 0.37.2`（9 条，HTTP 框架面）、`langchain*`+`langsmith`+`text-splitters`（27 条，多组件未启用）；
  - 可论证 not-exploitable：`transformers 4.57.6`（6 条，固定权重本地推理无用户注入）、
    `chromadb 0.4.24`（2 条，未监听外部端口）；
  - **处置：数据所有者批准整体 Risk Accepted（2026-09-07）**，8 字段表单齐全
    （severity 保守高估、reachability 逐包、exploitability、compensating controls、
    rationale=修复均破坏性大版本升级需独立候选周期、**expiry=90 天或下一候选周期复审**）；
  - 复审动作：灰度期间持续 `pip-audit -r requirements.txt` 定时扫描（命令见 runbook 值守节）。
- 005 镜像含 mypy_cache 构建缓存（.dockerignore 修复晚于构建，无密钥）；
- 真 Shadow executor 不存在（交接已知）；
- LongCat key 曾在会话暴露（所有者决定暂不轮换，责任自担）。

## R9 性能/容量证据有限（低）
- 现有性能证据来自 40 次真实端到端采集（p50 47-50s / p90 62-63s，单 worker）；
- **并发冒烟（2026-09-07）已跑 PASS**：8 并发不同问题全 200、0 服务器异常/0 超时、
  healthz 绿（`docs/benchmark_results/concurrency_20260907-201231.json`）——并发下不崩/无死锁证实；
- 吞吐容量（压测）仍未做：单 worker + 60/min 限流 + 远端 LLM 使吞吐数字失真，留待目标环境容量规划。`bench_all.sh` 可在部署环境就绪后补跑。

## R11 分解器第二失败形态（低-中，工程遗留）
- 事实：contract-comparison-14 在 006/007 各失败一次（ISSUE_DECOMPOSITION_INVALID，
  非围栏类）；围栏修复后 15/15 采样通过（diag/contract14-sampling-20260906.json），
  009 未复现。结构化日志已就位，复现即可取证。

## R12 Agent 反问正确率观察项（低，质量观察）
- 事实：009 口径 v1.2.0 下 agent clarification_precision 0.3333（6 问 2 中）——
  v2 政策未对此设门（统计样本小+避免重复计分），但产品上反问质量可继续经
  acceptable_clarification_keywords 策展优化（逐条留痕）。

## R10 环境边界（低，事实声明）
- 本机为开发环境；无生产服务器访问凭据——阶段 M/N 的实际部署动作交付了
  预案（deployment-v1.md），未执行。
