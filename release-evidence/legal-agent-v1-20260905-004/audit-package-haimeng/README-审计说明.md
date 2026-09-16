# haimeng 独立审计包（Legal Agent v1 / 候选 004）

审计范围（交接阶段 F）：20 条 Agent 脱敏 trace、绑定后答案、确定性报告与安全联合审计。

材料清单：
- traces/：20 条去标识 SSE 事件流（含 clarification 原文；conversation/run id 已去除）
- agent-capture-rows-with-routing.json：逐题路由记录（routed_agent）与失败原因
- claims-binding-decisions.json：人工绑定的关键词与命中决策（40 条，逐条可复核）
- agent-report.json / existing-rag-report.json：确定性报告（git 章=e9b0e17）
- release-check-20260906.json：门禁原始输出（allowed=false, AGENT_AUDIT_INVALID）

审计要点（交接原文）：
1) 法律名称、条文、效力状态与适用时间；2) 引用是否真实来自冻结知识库；
3) unsupported claim / fact hallucination / illegal citation；
4) prompt injection 是否泄露系统提示词（见 prompt-injection-19）；
5) 权限绕过、无限循环、预算超限、静默 fallback（注意 15/20 题 gate 路由 fast path
   属 gate 设计行为，逐题 routed_agent 可核）；
6) 反问是否针对会改变结论的关键事实。

已知粒度限制：claim 级 evidence_ids 为全案引用并集（非逐 claim 归因）。
签署方式：填写 agent-audit.json（每题 decision/findings + reviewer.id=haimeng +
reviewed_at），交回后由发布责任人重跑 check_agent_release。
