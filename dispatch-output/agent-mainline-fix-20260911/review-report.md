Agent 主链路审查与修复交接 — 2026-09-11

本轮结论：已有反例支持的主要问题集中在运行时预算、重试分类、状态交接和失败持久化边界。保留现有模块划分可以完成修复，当前没有必要重建编排框架。本轮未新增依赖。

审查与修改限于 Agent 主链路及相关测试。基线为本目录中的 `.before` 快照；仓库原有大量未提交修改，因此本轮差异不能用整个 HEAD diff 代替。

| 问题 | 本轮处理 | 验收要点 |
|---|---|---|
| FAILED 保存异常被吞掉，公开结果仍像普通业务失败 | 统一失败返回；分别公开报告 `AGENT_STORAGE_FAILURE`、`AGENT_FINALIZATION_CONFLICT`；诊断保留原原因、阶段和异常类别 | 真实 SQLite CAS 赢家不被覆盖；无 assistant 消息；已消耗预算保留；新增日志不含异常原文 |
| controller 的旧状态被配上数据库新版本号继续使用 | service 重载后比较完整状态，不一致立即返回冲突 | 在 controller 返回与 service 重载之间插入真实写入，验证赢家状态保持原样且 writer 零调用 |
| 已保存回喂 attempt 后断连，仍调用 writer | 预约预算成功后、writer 外呼前再次检查取消 | 预算仍为已使用、版本正确、无重写调用和 assistant 消息 |
| writer 回喂拒绝非法证据后，原因阶段被覆盖 | 保留 `WRITER:UNKNOWN_EVIDENCE_ID` 供持久化诊断 | 公开覆盖不足原因维持兼容，失败步骤记录真实 writer 阶段 |
| 配置的预算上限被自动提高 | 删除自动抬预算函数，工厂原样快照 settings | 工厂入口验证 3/1、16/10、32/20，禁止隐式提高 |
| 事实修复改善了引用覆盖，却产生无法组装的候选 | 提取并复用同一状态组装校验，采纳前执行；不合格保留原提案 | 覆盖归一化重复问题、无可信来源、空白问题、空白未知事实四类反例 |
| 首轮空白字段经 trim 后抛出未归类验证异常 | 映射为 `IssueDecompositionError` | 保持拒绝无效输入，进入已有分解错误处理路径 |
| Planner 将超时等传输故障当成坏 JSON 重试 | 新增窄异常类型 `PlannerUnavailable`，controller 首次及反馈路径均落 FAILED | 传输失败单次调用；先格式错误再超时共两次；真正的格式错误修复能力保留 |

完整验证已完成，原始输出和退出码均保存在本目录：

| 检查 | 结果 | 证据文件 |
|---|---|---|
| 后端 CI 范围测试及覆盖率 | 933 passed；18 deselected；退出码 0；覆盖率 78.35%，高于原有 70% 门槛 | `full-tests.txt`、`full-tests.exit.txt`、`full-junit.xml` |
| 全后端 Ruff | 通过，退出码 0 | `lint.txt`、`lint.exit.txt` |
| 全后端格式检查 | 207 files already formatted，退出码 0 | `format.txt`、`format.exit.txt` |
| 全后端 mypy | 63 source files，无问题，退出码 0 | `mypy.txt`、`mypy.exit.txt` |

测试保留 50 条警告，来自依赖弃用提示及测试用 JWT 短密钥提示。没有将警告隐藏或修改测试门槛。18 项 slow 测试按仓库 CI 的 `not slow` 规则排除，不能声称它们通过。

复现最终验证：在项目根目录 PowerShell 执行 `& .\dispatch-output\agent-mainline-fix-20260911\verify.ps1`。脚本使用本目录内的测试数据库、假凭据、本机关闭端口和离线嵌入设置。它会重写本目录的最终测试输出，若要保留本轮证据，先复制该目录。静态检查从 `backend` 运行 `venv\Scripts\python.exe -m ruff check .`、`venv\Scripts\python.exe -m ruff format --check .`、`venv\Scripts\python.exe -m mypy .`。

反例证据保留在 `runtime-red.txt`、`service-red.txt`、`blank-red.txt` 和 `planner-red.txt`。最初的 Planner 测试错误地被确定性终稿门短路，因此 `boundary-red.txt` 中对应两条失败不算有效重试反例；该文件里的状态交接冲突反例有效。修正夹具后，`legacy_planner_probe.py` 从 `.before` 中加载原始 `decide` 方法，仅在测试进程中替换，重新证明旧逻辑有 4→1 和 3→2 的调用次数差异。最终测试不加载该插件。第一轮全量的两项夹具失败及中间检查失败均保留，没有把它们充当最终通过证据。

本轮涉及 4 个生产文件、3 个测试文件。生产文件共净减少 22 行，口径包含注释和空行，不代表运行速度提升。`candidate.diff` 只包含相对于本轮快照的修改；`candidate-manifest.json` 记录前后 SHA-256 与行数。最终测试结束后再次核对，7 个修改文件均匹配清单。回退时逐文件核对快照及后续修改，不要对整个脏工作区执行 reset。

接手时遵守以下约束：

1. 配置预算是硬上限。复杂任务可能因预算不足提前停止，这是明确的成本边界；需要提高预算时显式修改配置并验证，不恢复隐藏的预算扩张。
2. 不将 SDK 内置重试与本轮修复混为一谈。本轮去掉的是 adapter/controller 对传输异常叠加的格式修复重试；SDK 自身策略仍保留。若下一步要求金额硬上限，需单独审查各层实际调用及计费，steps/tool_calls 不等于人民币预算。
3. 优先用失败反例定义下一张小任务，再修改生产代码。不要为了压缩行数删除来源校验、CAS、预算预约、证据验证或错误处理。
4. 下一轮若验证法律回答质量，应使用冻结题集、可追溯依据及独立判定，并明确模型、配置和成本。本轮离线工程测试不能证明真实模型法律准确率，也不能替代生产部署验收。

本轮付费模型验证支出为 0 元，未使用授权的 20 元额度。未执行部署、Git 提交或推送。后续接手应以本报告和实际候选为准，历史规划书中“仍调用自动抬预算函数”等描述已成为历史状态。
