# D-34 修复前检查点（2026-10-11）

> 2026-10-11 最终执行更新：Owner 选择 A（保持追问/补充 fact-only 旧契约）并批准响应归属收敛。下文“未修复/待选择”均为修复前历史。响应构造前异常漏记的 P1 已关闭，D-34 限定范围本地验收通过；最终同版 43 项定向与 168 项综合隔离回归通过，另 4 项排除，两轴复核无未关闭问题。证据见同目录 `d34-response-owner-closeout-20261011.md`；暂停时历史保留于 `d34-execution-and-review-20261011.md`。源码与测试仍未提交，HEAD 不变；候选整体仍 BLOCKED，不能据此发布。

## 已批准与当前状态

Owner 已选择上一轮 A：隔离修复 D-34，覆盖失败、取消、追问、防重复写；D-33 防御保留，真实库、凭据、推送、部署不动。当前完成了根因核查与隔离诊断，**尚未修复，尚未运行修复后回归**。

候选 HEAD：`19e296e879ac2ffbb0a862c2c9e595d3c81c8ded`。未修改候选源码、测试、依赖、索引或 refs。

## 新核实的旧契约

- `backend/tests/test_agent_chat_integration.py::test_real_agent_service_returns_clarification_without_assistant_message` 明确要求追问时 assistant 消息为零；范围选择测试也锁定此行为。
- `resume_with_user_fact` 和范围选择恢复使用版本 CAS 保存状态/事实/检查点，不写用户聊天 Message。
- 服务层恢复测试明确不新增用户 Message，最终成功才新增一条 assistant Message。
- `get_conversation` 按 Message 读取聊天历史；不会从未关联消息的 AgentRun 自动补出 pending_question。

因此“将追问及每次补充都落聊天历史”不是无需裁定的内部补丁。上一轮审查中的逐接受输入幂等原则仍是安全要求，但不能据此推导 Owner 已选择上述新的历史展示形态。

## 本次隔离复现

运行：

```powershell
& 'C:/Users/33393/Desktop/fazhi-nondeploy-closeout-20261010-b4e7a2/candidate-envB/Scripts/python.exe' -B -I 'C:/Users/33393/Desktop/fazhi-nondeploy-closeout-20261010-b4e7a2/evidence/d34-prechange-route-probe-20261011.py'
```

退出码 0。两例均产生真实 chat 路由和 serializer 的公开事件；Message 仅 user 一条，message_count=1。失败例事件为 agent_status/error，追问例为 agent_status/clarification。

仪器只读取候选 main.py 的 AST，执行完整 chat 函数及响应投影；使用内存 SQLite 和实际 ORM，替换 bootstrap/Agent 服务边界以输入确定失败/追问结果。没有导入 main 或启动服务，不读取 .env、模型缓存和真实库、不调用模型。**它证明入口缺少结果落消息的处理，不证明完整 Agent 服务、HTTP 生命周期或取消矩阵已通过**。脚本断言的是修复前现状，不是修复目标的绿测；修改前还需按最终选择加入目标红测。

message_count 与现存记录数一致；本问题不能泛称计数已经错位，主要是缺失结果记录及待选择的历史契约。

## 两种可选边界（待 Owner 选择）

### A 推荐：先保持追问旧契约，只修失败/取消记录

合法追问不写失败占位；补充回答继续由 Agent 状态和事实保存，不自动新增聊天 Message。围绕已接受输入的真实归属，处理硬失败和执行中断开的结果记录；保证重复清理不双写、技术 fallback 不双写、成功终稿不被覆盖、409/非法输入不产生新补偿。不能仅套 StreamingResponse 关闭回调；取消和响应前异常也要覆盖。

如果发现旧契约无法安全识别待补偿输入，应停止并重新裁定，不能凭 run_id 或“会话最后一条为 user”猜测。刷新后恢复追问的产品改进留独立任务，不将其称为已解决。

### B：同时改为完整多轮消息历史

合法追问保存为追问而非法律结论；被 CAS 接受的补充回答原子保存为 user 消息。每轮结果按对应输入幂等，维护实际计数；不得将追问/失败标为验证 PASS 或 full coverage。须另明确历史读取与恢复身份的公开字段/客户端兼容、旧数据处理和失败回退，不能只改测试以迎合实现。

此方案能改善刷新后的历史连续性，但改变旧业务契约，范围比 A 大。本轮未实施任一方案。

## 继续条件

Owner 选定 A/B 后，再根据真实入口写目标失败测试、修复及邻域回归；不删除旧有效测试，必要的契约变更需有选择依据。无提交/推送/真实库写入/凭据操作/部署授权。
