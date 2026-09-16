# T0 候选 manifest（2026-09-09 20:50 前后采集）

任务：T2 回喂预算持久化及版本传递（依据 docs/agent-architecture-audit-and-execution-plan-20260909.md ⑤⑦）。
采集方式：Git Bash `git rev-parse HEAD` / `git status --porcelain` / Python hashlib SHA256。

## HEAD 与工作区

- HEAD：`ebe82e2bda26185236d50afd780cfb48c7c5e946`（与审查书一致）
- 分支：当前工作区（W1–W4 脏改动就地保留，未 commit、未 stash、未 reset）
- Tracked 修改（6）：`backend/agent/runtime.py`、`backend/agent/service.py`、`backend/agent/writer.py`、`backend/tests/test_agent_runtime.py`、`backend/tests/test_agent_writer.py`、`docs/v2-optimization-execution-taskbook-20260909.md`
- 关键未跟踪测试：`backend/tests/test_agent_coverage_loop.py`（T2 需同步更新签名）
- 未跟踪诊断/历史目录（diag/、dispatch-output/、release-evidence/ 等）：一律不清扫、不 git add

## 关键文件工作区 SHA256（前 16 位）

| 文件 | SHA256-16 | 角色 |
|---|---|---|
| backend/agent/service.py | 7588a65a80cb553f | T2 主编辑对象（W1-W4 已脏基线） |
| backend/agent/runtime.py | c73cefe93ad0fbd4 | 本轮不改（T4 范围） |
| backend/agent/writer.py | e0bc200ab3befd66 | 本轮不改（含 coverage_feedback_payload，W1-W4 已脏基线） |
| backend/agent/verifier.py | 47b37a0a421eaa2c | 冻结：判定逻辑一行不改 |
| backend/agent/chat_integration.py | f05c43c33b7d1e53 | 冻结：equality guard / CAS / ownership 不动 |
| backend/agent/state_machine.py | 9de7c35f3543e749 | 冻结：register_verifier_research_return 复用不改 |
| backend/agent/repository.py | 57c1c00dc00df76c | 冻结：compare_and_save 复用不改（T2 目标零改动） |
| backend/agent/controller.py | 3b2bf12f61162f19 | 本轮不改 |
| backend/agent/gate.py | c2a3844dc0f6f4a6 | 本轮不改 |
| backend/prompts.py | 65c5211c81109830 | 冻结：系统提示词常量 |
| backend/scripts/gate5_judge.py | 90487960771dd372 | 冻结判分器（F2） |
| backend/tests/test_agent_chat_integration.py | b8b636ebff6960e7 | T2 红测试宿主（本 manifest 采集后追加测试） |
| backend/tests/test_agent_coverage_loop.py | bbbb5e7aea3617ed | 未跟踪；helper 签名改造后同步更新 |
| backend/tests/conftest.py | 356286cf202988d4 | db fixture（tmp_path 迁移 SQLite） |

## 冻结产物 SHA256（前 16 位）

| 产物 | SHA256-16 |
|---|---|
| release-evidence/.../frozen-cases-v1.json | be281ab275024b2c |
| release-evidence/.../frozen-fact-ids-v1.json | 262456b6fd06d2fb |
| release-evidence/.../frozen-round-protocol-v1.json | 89d8d9167262ae83 |
| release-evidence/.../gate2-run-gate5-dev-run-9-sessions.json | 08181f2e6e17a6c2 |
| release-evidence/.../gate2-run-gate5-dev-run-10-sessions.json | e11c104bacf8bb82 |
| release-evidence/.../gate2-run-gate5-dev-run-11-sessions.json | bd56d3e18bad627c |
| dispatch-output/task1/hidden-cases-v1.json | d1f0b1f053b2f4b3 |
| dispatch-output/task1/hidden-round-protocol-v1.json | e4de149b4bf9eccf |
| dispatch-output/task1/hidden-commitment.json | 1ae1488c9e693b0e |
| dispatch-output/task1/salt.txt | 51157d68a830b3d5 |

## T2 编辑 allowlist

1. `backend/agent/service.py` — 重写分支持久化编排（唯一业务代码改动点）
2. `backend/tests/test_agent_chat_integration.py` — 追加集成红/绿与负例测试
3. `backend/tests/test_agent_coverage_loop.py` — helper 签名同步更新（未跟踪文件，随 service.py 改动必要更新）

其余文件零改动。repository.py / chat_integration.py / verifier.py / writer.py / state_machine.py / prompts.py / gate5_judge.py 目标零改动；若实现中证明必须触碰，先停下来在交付报告中说明原因。

## 测试执行环境（与审查书一致）

工作目录 backend；环境仅对执行进程设置（conftest.py setdefault 兜底）：
LLM_API_KEY=audit-offline，LLM_BASE_URL=http://127.0.0.1:9/v1，EMBEDDING_PROVIDER=local，
RERANK_ENABLED=false，EMBEDDING_QUOTA_TOTAL=0，RERANK_QUOTA_TOTAL=0，DATABASE_URL=sqlite:///:memory:。
解释器：`./venv/Scripts/python.exe`。

## 红线确认

- 不启动 run-12、不发起任何真实模型请求（LLM_BASE_URL 指向不可路由地址）
- 不修改冻结判分器 / rubric / 事实协议 / hidden 产物 / 历史 sessions / verifier / 系统提示词
- 不删除 equality guard、不把预算从比较中排除、不改内存计数欺骗保存层
- 不并行修改 service.py；T3 与 T2 串行
