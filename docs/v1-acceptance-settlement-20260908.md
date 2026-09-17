# V1 第一阶段验收结算与风险台账（2026-09-08）

> Owner 决策（2026-09-08）：结算 + 复评入台账。Agent V1 不进正式灰度，RAG 主链不受影响。
> 依据数据：开发集 run-1~6（见 docs/gate5-formal-dev-20260908.md）、隐藏集 run-a/b（dispatch-output/task1）。

## 一、验收结算

| 验收项 | 验收线 | 实际 | 结论 |
|---|---|---|---|
| 开发集（复杂咨询 10 题）机械通过 | 9/10 | **1/10**（run-6，C05） | **不通过** |
| 隐藏集 run-a | 4/5 | **0/5** | **不通过** |
| 隐藏集 run-b | 4/5 | **0/5** | **不通过** |
| 六段式完整输出 | 至少部分通过 | 1/10（C05，run-6） | 最早产出 |
| 安全红线/注入生效/伪造引用 | 0 | 0（全部 run） | **通过**（fail-closed 全拦截） |

**结算口径**：开发集+隐藏集均未达验收线，**Agent V1 第一阶段正式验收不通过**；按纪律停止候选补丁迭代，
本结果作为阶段性结构化验收结论固化，供灰度豁免 ADR 或 V2 决策引用。

## 二、剩余失败面归因（结构性，非工程修复可得）

| 失败面 | 表现 | 归属层 | 建议 |
|---|---|---|---|
| EVIDENCE_COVERAGE_DEFICIENT（4/10@run-6） | 检索/claim 证据绑定不足，reason 码太粗 | 检索+生成 | V2：召回质量 + 细粒度 reason 码 |
| PLANNER_PARSE_ERROR（3/10@run-6） | planner 结构化输出不合规，回喂仍败 | LLM 生成 | V2：分解器与生成器分离/更强模型 |
| UNSUPPORTED_NUMERIC_TOKEN（1/10） | LLM 输出数字逸出 | LLM 生成 | V2：数字受限生成或校验前归一 |
| ISSUE_DECOMPOSITION_INVALID（1/10） | 问题分解失败 | LLM 生成 | V2：分解重试+多样性采样 |

## 三、有效机制（保留并固化）

1. **错误回喂重试**：PLANNER_PARSE_ERROR 7/10（无回喂）→ 2-3/10（回喂），模型无关（qwen 与 LongCat 均验证）——确认有效，进入 V1 基线保留项。
2. **fail-closed 护栏**：全部 6 个正式 run 中不合规输出均被确定性校验拦截，0 红线——安全面达标。
3. **确定性机械判定**（gate5_judge）：独立于 LLM，判定可复算。

## 四、风险台账（V1 封存）

| # | 风险 | 级别 | 状态/处置 |
|---|---|---|---|
| 1 | 通过率远低于验收线（1/10） | High | 结转为已知限制；V1 不对外灰度 |
| 2 | 隐藏集 F1（用户更正）、F5（提示注入）运行层 0 次触达 | High | Owner 已批 1+3：如实声明，专项走语义匹配（决策件 decision-a1） |
| 3 | ~~服务端运行审计缺口~~（已澄清，非缺口）：run-4/5/6 会话**全部正常落库**（agent_runs/messages/conversations），created_at 存 UTC（utcnow），本地时区查询导致误判；例 run-6 C01 conv=2256 created 09:48 UTC=本地 17:48（与 runner 启动吻合）。**已关闭** | 已澄清 | 结转到审计说明：查询 DB 时间列须用 UTC |
| 4 | 采集 runner 双进程并发（venv+Python311） | P3 | 已核实 sessions 文件唯一无覆盖；观察无复发即可 |
| 5 | 双 uvicorn 残留（venv 败者不监听 8000；实际服务为 Python311 实例） | P3 | 清理尝试后**保持现状**：kill 败者会触发 job 进程树连坐误杀服务；方案为后续用独立进程启动原生服务后统一替换，或长期接受（无功能影响）。2026-09-08 服务重启事件：清理误伤后于 19:49 重启，现监听 PID 36812 |
| 6 | 平台账单不可得（LongCat 无编程接口） | P3 | **Owner 决策（2026-09-08）：不做平台侧核对**；成本核算以服务端 token_est 台账为准（gate5 §5），限制已知 |

## 五、遗留工程项（转 V2 候选）

- coverage reason 码细化（指明缺哪个 issue/证据）
- 回喂正向路径单测
- 运行前快照纪律（已制度化于 dispatch-output/run-discipline-checklist）
- manifest-v3（如需随代码演进更新 hash 基线）

## 六、引用

- 判定数据：docs/gate5-formal-dev-20260908.md（附 D/E）、dispatch-output/task1/verdict-a/b.md
- 证据锁定：release-evidence/…/gate1-freeze-manifest-v2.json（HEAD 88b7937）
- 安全复核：dispatch-output/task4/checklist-review.md + verifier-response（5/5 项闭环）