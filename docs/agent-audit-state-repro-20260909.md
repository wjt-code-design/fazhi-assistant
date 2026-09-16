# 状态持久化审查：隔离复现（2026-09-09）

## 结论与边界

当前 `backend/agent/service.py:125` 在 coverage 回喂前直接修改内存中的 `verifier_research_returns`，没有保存 checkpoint；`backend/agent/chat_integration.py:190` 要求传入状态与 durable checkpoint 完全相等。因此回喂后即使 verifier 恢复 PASS，也会被 finalization equality guard 拒绝。

这是从当前生产文件 AST 提取两个原函数的**隔离复现，不是完整集成测试**：使用真实 `LegalAgentState`，DB、writer、verifier 使用替身。未调用外部 API、未访问业务数据库、未修改生产代码。直接导入 service 的首次尝试因当前全局 Python 缺少 `sqlalchemy` 失败，随后用 AST 隔离依赖复现；没有安装依赖或重跑整套测试。

## 可复现命令

在项目根目录以 PowerShell 运行：

```powershell
@'
import ast
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock
from enum import Enum
import sys
sys.path.insert(0,'backend')
from agent.schemas import LegalAgentState, AgentStatus
class Verdict(Enum): PASS='PASS'; RESEARCH_MORE='RESEARCH_MORE'
class WriterStatus(Enum): READY='READY'
class Conflict(Exception): pass
scope={'Any':object,'VerificationResult':object,'VerificationVerdict':Verdict,'WriterStatus':WriterStatus,'LegalAgentState':LegalAgentState,'AgentStatus':AgentStatus,'AgentFinalizationConflict':Conflict,'AgentRun':MagicMock(),'_answer_digest':lambda s:s,'coverage_feedback_payload':lambda s,d:'missing issue'}
for path,name in [('backend/agent/service.py','_coverage_research_loop'),('backend/agent/chat_integration.py','persist_agent_final_once')]:
    tree=ast.parse(Path(path).read_text(encoding='utf-8'))
    func=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==name)
    exec(compile(ast.Module(body=[func],type_ignores=[]),path,'exec'),scope)
state=LegalAgentState(status=AgentStatus.DRAFTING)
durable=state.model_dump_json()
passed=SimpleNamespace(verdict=Verdict.PASS,claim_checks=[object()])
runtime=SimpleNamespace(writer=SimpleNamespace(render_for_coverage=lambda s,f:SimpleNamespace(status=WriterStatus.READY,draft='fixed')),verifier=SimpleNamespace(verify=lambda s,d:passed))
result,draft=scope['_coverage_research_loop'](runtime,state,SimpleNamespace(verdict=Verdict.RESEARCH_MORE),'original')
db=MagicMock()
db.query.return_value.filter.return_value.one_or_none.return_value=SimpleNamespace(state_version=3,status=AgentStatus.DRAFTING.value,state_json=durable)
print('AST extracted production functions; fake DB and writer/verifier, real LegalAgentState')
print('verdict=',result.verdict.value,'memory_counter=',state.verifier_research_returns,'durable_counter=',LegalAgentState.model_validate_json(durable).verifier_research_returns)
try: scope['persist_agent_final_once'](db,user_id=1,conversation_id=1,run_id='test',expected_version=3,state=state,answer='fixed',verification=passed)
except Conflict as exc: print('AgentFinalizationConflict:',exc)
'@ | python -
```

本次实际输出（exit code 0）：

```text
AST extracted production functions; fake DB and writer/verifier, real LegalAgentState
verdict= PASS memory_counter= 1 durable_counter= 0
AgentFinalizationConflict: Finalization state does not match the durable checkpoint
```

## 其他静态发现

- `service.py:249–313` 的 writer/verifier/final gate 失败直接返回 public result，没有记录 FAILED、last_error_code 或失败 step。数据库仍停在 DRAFTING；这是代码路径证据，尚未在真实数据库集成环境中复现。
- `controller.py:410–422` 对 DRAFTING 返回已有状态，因此失败 run 被再次执行时会再次进入 writer；coverage 内存扣减丢失，跨恢复执行的预算不能由数据库约束。
- `service.py:126–128` 的 coverage 重渲染失败会保留前一轮 verification，丢失新 writer failure reason；需要同时保留最终业务结论和具体 attempt 失败原因。
- `backend/tests/test_agent_coverage_loop.py` 调用 `_coverage_research_loop` 验证 helper，不能证明 `execute_agent_request` 到最终数据库落盘的完整成功路径。

## 建议修复边界及验收

1. 保留 `chat_integration.py:190` 的状态相等守卫。coverage 外呼前通过已有 repository CAS 保存预算消耗与 attempt checkpoint，后续继续使用返回的新状态和新版本。CAS 失败不得继续外呼。
2. service 编排层收敛已有 run 的失败持久化，使用公开 repository 接口，不跨层调用 controller 私有方法。存储故障须明确报告无法持久化，不伪造成功状态。
3. 本 ticket 只修持久化与恢复契约，不另建研究框架；writer 重写和真正重新检索应分别定义语义与预算。
4. 用 `execute_agent_request`、真实内存 SQLite repository 与真实 final storage 覆盖：首稿缺覆盖→重写 PASS→恰好一个 assistant Message；重写失败→失败原因可重载；预算耗尽→无新增外呼；CAS 冲突→无新增外呼；恢复执行→预算不复原；存储异常→不返回 completed。
5. 失败记录不得破坏已有完成结果，也不得绕过 owner 校验、版本检查或 finalization 幂等性。CLIENT_DISCONNECTED 是否可恢复须单独定义，不机械改成不可重试 FAILED。

上述集成验收是后续执行助手的工作，本审查未声称它们已通过。
