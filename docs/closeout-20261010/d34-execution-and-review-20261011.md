# D-34 A 边界修复执行记录（2026-10-11）

> 最终更新：Owner 已批准并执行响应归属收敛 A，前轮剩余 P1 关闭；D-34 限定范围本地验收通过。最终同版结果为 43 项定向通过、168 项综合通过/4 项排除，静态检查通过，两轴复核无未关闭问题。详见同目录 `d34-response-owner-closeout-20261011.md`。本页以下为暂停时历史，旧失败与 SHA 保留不回写；候选整体仍 BLOCKED，未提交/推送/部署。

历史状态：**当时 D-34 验收未通过，按三轮重试纪律暂停新增修复，等待 Owner 确认归属边界收敛方案**。本文件不替代全项目候选门禁，不表示可发布。

## 授权、位置与验收边界

- Owner 连续两次选择 A：隔离修复 D-34，保持追问不写 assistant Message、恢复补充事实不写 user Message 的旧契约。
- 候选：`C:/Users/33393/Desktop/ai-legal-helper/.worktrees/nondeploy-closeout-20261010`，分支 `codex/nondeploy-closeout-20261010`，基线 `19e296e879ac2ffbb0a862c2c9e595d3c81c8ded`。
- 仅改 `backend/main.py`、新增 `backend/tests/test_agent_turn_compensation.py`。D-33、数据库 schema、服务层验证、公开 SSE schema、依赖不改。
- 不读取凭据/真实库/模型缓存、不启动项目服务、不调用在线模型；不提交、推送或部署。主工作区不改。
- 目标：已接受请求失败/取消有明确结果；重复清理不双写；成功终稿不覆盖；合法追问不写失败；拒绝的恢复无补偿；技术 fallback 正常交给快车道且取消交接没有归属空档。
- 不承诺：进程崩溃修复、多 worker 幂等、刷新后自动恢复追问。后者仍是独立产品改进，不在 A 中。

## 根因与执行顺序

1. 保留修复前诊断脚本 `../evidence/d34-prechange-route-probe-20261011.py` 作为历史证据；它断言旧行为，不作为修复后绿测重跑。
2. 新测试先复现缺失结果/重复写/错误归属，再复用 `_post_placeholder` 写结果和原子计数。游标按已接受请求实际消息边界生成，不按 run_id 或末条 user 猜测。
3. 第一轮定向与邻域绿测后进行独立 Spec、Standards 复核；复核发现三处未覆盖的 P1：watcher-only 断开 fallback 双写、fallback 准备期取消漏记、resume CAS 提交后取消提前关闭 Session。
4. 停止局部补丁，重划同一准备任务的生命周期：首次 bootstrap/gate、恢复 CAS、Agent 执行、技术 fallback 准备全部在已有 owned-worker 中；父任务取消必须等待线程与存储清理结束，才关闭 Session/释放会话锁。
5. 快车道准备与响应清理共享请求游标/提交标记；已断开 fallback 不继续交接。成功/追问旧契约保留。补偿写失败保留异常类型标记与安全的会话/用户编号日志，不记录异常原文。
6. 三处真实入口目标测试先红后绿，再补首次提交取消、真实准备失败和响应关闭重入。完成邻域回归、静态检查及独立复验后，才更新最终结论。

## 本次证据（截至当前）

外部 Python：`C:/Users/33393/Desktop/fazhi-nondeploy-closeout-20261010-b4e7a2/candidate-envB/Scripts/python.exe`；工作目录为候选 `backend`。

- 初始目标：9 failed / 5 passed，断言失败符合缺失结果、防重和归属目标（历史工具输出）。
- 交接目标红测：`../evidence/d34-handoff-red-20261011.xml`，3 failed / 26 deselected，退出 1；不是导入失败。
- 交接修订绿测：`../evidence/d34-handoff-green-20261011.xml`，29 passed，退出 0。
- 扩展定向：`../evidence/d34-handoff-regression-20261011.xml`，33 passed，退出 0。
- 修订前邻域：`../evidence/d34-regression-final-20261011.xml`，112 passed，退出 0；此结果不能冒充结构性修订后的回归。
- 当前 mypy：74 个源码文件无错误；仍有既有未类型化函数体提示，不表示类型覆盖全仓。
- 结构性修订后的邻域：`../evidence/d34-owned-boundary-final-20261011.xml`，119 passed，退出 0。此后仅新增下一条已知缺口目标测试，生产源码未再修改。
- 扩展服务层：`../evidence/d34-service-expanded-20261011.xml`，39 passed / 4 deselected，退出 0；排除 4 个需要导入 main 启动路径的测试，不声称全量集成通过。
- Ruff check 通过、format check 为 284 个文件已格式化、git diff --check 通过。
- 当前仍有目标红测：`../evidence/d34-response-handoff-open-red-20261011.xml`，1 failed / 33 deselected，退出 1。正常恢复 CAS、技术 fallback 准备已完成后，注入 `_build_messages` 异常，真实 `_serialized_chat` 释放锁却未写结果；断言命中漏记，不是导入失败。33 项原绿测不覆盖此项。
- 暂停前同版完整定向复跑：`../evidence/d34-paused-state-20261011.xml`，**33 passed / 1 failed**，退出 1；唯一失败就是上述剩余 P1，不使用旧绿测代替当前结论。
- Standards 独立复核：前轮两项发现关闭；当前未发现需要框架或新增 schema 的硬违规。Spec 独立复核：原三项 P1 已关闭，但响应构造前异常的归属空档仍为 P1，故不能验收。
- 候选只有 `backend/main.py` 修改与新增测试未提交，索引为空，HEAD 未变化。主工作区本来存在大量未提交内容，本轮未写入主工作区，也没有整理/提交这些内容。

当前源码 SHA256：`main.py=542CA27EEABC427A0CBEB6DC554D03146D0E06D053115A1BB53E790750C064AC`；测试新增红测后的 SHA256：`3EAA14FC856EC43B4E1DECB53C4DE01EE64520E9A13F7CC586D6BA302B59A9C5`。独立 33 项复核使用的是增加该红测之前的测试版本，不混称完全同版。

复现定向测试：

```powershell
& 'C:/Users/33393/Desktop/fazhi-nondeploy-closeout-20261010-b4e7a2/candidate-envB/Scripts/python.exe' -B -m pytest --noconftest -p no:cacheprovider tests/test_agent_turn_compensation.py -q --tb=short
```

测试读取真实 main AST 并执行入口/清理函数、实际 CAS、真实线程派发和临时 SQLite ORM；仅在 Agent/检索边界注入合成结果，不导入 main 的启动路径。不是全项目 HTTP/模型/生产验收；禁止去掉 `--noconftest` 后直接套用此命令触发原启动路径。

## 阶段限制与后续

即使 D-34 本地通过，候选整体仍须独立裁定剩余依赖审计、管理员凭据/既存会话处置及最终门禁；旧 A–J 报告不是现版本的自动签收。保持 BLOCKED，不把“只剩 push”当结论。提交/推送/真实库写入/部署须另行授权。

剩余 P1 的推荐收敛方案见 `d34-response-ownership-replan-20261011.md`；当前只编写与复核方案，不继续第四次实现。新目标测试保持失败，不删除、不标 xfail、不把它排除后宣布全绿。
