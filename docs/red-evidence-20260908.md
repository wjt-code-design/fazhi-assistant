# P2-1：新测试 red→green 梯度证据（2026-09-08）

> 对应：task4（审核清单复核）P2-1「red 证据缺失：§11.5 要求新测试有正确原因的 red 证据，全仓未找到」
> 交付物：本文件 + `dispatch-output/red-evidence-runs/*.log`（每级 pytest 原始输出，可复跑）
> 纪律：不修改主工作区（临时 git worktree，跑完已移除）；不触及运行中服务（uvicorn 16:23:04 进程未重启）。

## 方法

1. `git worktree add --detach <tmp> b7ab04f`（b7ab04f = 6e43042 父代 = Gate-4 修复前基线）。
2. 固定测试文件为 **HEAD（88b7937）版本**（5 个测试文件 + conftest + `_fake_embeddings`），从主工作区复制；
   `.env` 一并复制（worktree 是 gitignore 产物，缺 .env 会引入环境性红，已排除）。
3. 沿提交链顺次 `git checkout <commit> -- backend`（只换被测代码），每级重覆盖 HEAD 测试后运行：
   `venv\Scripts\python.exe -m pytest tests/test_agent_resume.py tests/test_agent_controller.py tests/test_tool_gateway.py tests/test_agent_runtime.py tests/test_agent_verifier.py -q --tb=line`
4. 记录每级 failed 数与失败用例 → 还原"测试先红、修复转绿"全过程。

## 梯度结果

| 级别（被测代码） | 结果 | 相对上一步转绿的修复 |
|---|---|---|
| b7ab04f（Gate-4 修复前） | **8 failed, 121 passed** | —（含全部新测试的红） |
| 6e43042（resume 锚点/F1） | **6 failed**, 123 passed | -2：显式未知 acknowledge、pending_question 锚点 |
| 03a2f14（max_steps 预算/强制条件化门） | **4 failed**, 125 passed | -2：预算耗尽不再第二轮 409 的强制条件化门 |
| 613ecb3（证据链 source_id + planner 坏输出一次重试） | **1 failed**, 128 passed | -3：source_id 派生、planner 两处重试 |
| ee939bc（六段式渲染） | **129 passed** | -1：六段式章节标题 |
| 71e5f23（错误回喂） | 129 passed | 见下"回喂的测试说明" |
| 88b7937（HEAD，LongCat 全链） | 129 passed | 最终态全绿 |

## 各级 red 用例与"正确原因"

基线（b7ab04f）8 个红，均可在修复 commit + 断言堆栈中定位失效行为：

| 用例 | 失效断言（红因） | 对应修复 |
|---|---|---|
| test_agent_resume.py::test_resume_explicit_unknown_is_acknowledged_not_conflict | `assert False`（显式未知未应答为 acknowledgement） | 6e43042 |
| test_agent_resume.py::test_resume_uses_pending_anchor_even_when_evaluator_prefers_another_issue | `ResumeRunConflict: Agent 任务已变化`（第二轮 resume 409） | 6e43042 |
| test_agent_controller.py::test_ask_user_forced_to_conditional_analysis_when_clarify_budget_exhausted | `expected DRAFTING, got stopped`（澄清预算耗尽后停住而非转条件化） | 03a2f14 |
| test_agent_controller.py::test_finish_research_forced_to_conditional_analysis_when_clarify_budget_exhausted | 同上（got stopped） | 03a2f14 |
| test_tool_gateway.py::test_map_document_derives_stable_source_id_when_chunk_id_missing | `assert (None is not None)`（source_id 恒 None → 证据被丢弃） | 613ecb3 |
| test_agent_runtime.py::test_planner_adapter_retries_once_then_recovers_when_first_output_malformed | `PlannerParseError: planner output is unavailable or malformed`（无坏输出重试） | 613ecb3 |
| test_agent_runtime.py::test_planner_adapter_retry_exhausted_still_raises_parse_error | `assert 1 == 2`（重试计数不符） | 613ecb3 |
| test_agent_verifier.py::test_pass_renders_six_sections_without_internal_ids | `缺少六段式标题: 已确认事实`（writer 四节式） | ee939bc |

## 错误回喂（71e5f23）的测试说明（诚实标注）

- 71e5f23 未新增独立"回喂成功后转绿"的正向用例；它对既有用例 `test_parse_error_is_explicit_degraded_failure_and_never_calls_gateway`
  的修改是把坏决策改成一个（首轮 parse 失败→触发回喂→二次失败→fail-closed），**保护的是"回喂后仍失败也必须 fail-closed"的底线语义**，
  不证明"回喂能让坏输出转好"。
- 该层级的工程有效性证据来自 run-5 实测（PLANNER_PARSE_ERROR 7/10→2/10，见 gate5-formal-dev 附 D），测试层仅守住失败面。
- 若需补"回喂正向路径"单测（首坏→带反馈重试→好输出→READY），已列入后续候选（可在 run-6 结论后决定是否补，不属本次 red 证据缺口）。

## 环境声明

- 单测全为 mock 编排（httpx WSGITransport 本地、无真实 LLM 外呼），梯度复现未触达与影响 run-6。
- 501 参数化用例（图片理解不可用）在缺 .env 时因模型配置解析不同报 400==501 红，属环境性红，复制 .env 后消失，未计入 8 个真实红。
- worktree 为临时目录，已删除；复算方式：重建 worktree 后按上方命令逐级重跑（脚本 `dispatch-output/red_evidence_gradient.py` 可一键重放）。