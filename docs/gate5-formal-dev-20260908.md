# Gate 5 开发集正式验收报告（复杂法律咨询 Agent V1 第一阶段）

> 日期：2026-09-08 · 基线 commit：`03a2f14`（Gate 4 修复后）
> 模型：LongCat-2.0（.env LLM_MODELS_JSON 覆盖）· force_agent=true · no_cache=true
> 冻结尺子：`gate1-freeze-manifest.json`（frozen-cases-v1 / round-protocol-v1 / fact-ids-v1 / rubric-v1 SHA-256 已冻结）
> 原始会话：`release-evidence/legal-agent-v1-complex-v1-20260907/gate2-run-gate5-dev-run-{1,2}-sessions.json`

## 1. 结论

**开发集两次独立正式运行均未达 9/10 门槛（机械判定各 0/10）。按任务书 §Gate 4 纪律停止第三轮同类补丁，提交架构复评。**

- 会话/状态机工程层：全部通过（两轮会话 100% 完整走通、无 409、无第三轮追问红线、无安全红线）。
- 失败 100% 收敛于 LLM 生成/检索/验证质量层，与历史 010/011 结构性差距结论一致。

## 2. 两次正式运行逐题结果

| 题 | run1 追问 | run1 final | run1 失败码 | run2 追问 | run2 final | run2 失败码 |
|---|---|---|---|---|---|---|
| C01 绩效解除 | 2 | 0 | EVIDENCE_COVERAGE_DEFICIENT | 2 | 0 | EVIDENCE_COVERAGE_DEFICIENT |
| C02 加班 | 2 | 0 | EVIDENCE_COVERAGE_DEFICIENT | 2 | 0 | EVIDENCE_COVERAGE_DEFICIENT |
| C03 未签合同 | 2 | 1552* | PLANNER_PARSE_ERROR | 1 | 806* | PLANNER_PARSE_ERROR |
| C04 二手房定金 | 1 | 821* | PLANNER_PARSE_ERROR | 2 | 0 | EVIDENCE_COVERAGE_DEFICIENT |
| C05 租赁换锁 | 1 | 738* | PLANNER_PARSE_ERROR | 1 | 1583* | PLANNER_PARSE_ERROR |
| C06 装修延期 | 1 | 1211* | PLANNER_PARSE_ERROR | 1 | 927* | PLANNER_PARSE_ERROR |
| C07 诉讼时效 | 0 | 0 | ISSUE_DECOMPOSITION_INVALID | 1 | 818* | PLANNER_PARSE_ERROR |
| C08 保证期间 | 2 | 0 | EVIDENCE_COVERAGE_DEFICIENT | 2 | 0 | EVIDENCE_COVERAGE_DEFICIENT |
| C09 健身房 | 2 | 0 | EVIDENCE_COVERAGE_DEFICIENT | 2 | 0 | EVIDENCE_COVERAGE_DEFICIENT |
| C10 刑民边界 | 0 | 0 | ISSUE_DECOMPOSITION_INVALID | 2 | 0 | EVIDENCE_COVERAGE_DEFICIENT |

\* 带 * 的 final 为 **fallback RAG 回答**（planner 技术失败后显式降级，非 Agent 六段式），
经人工抽查确认（如 run1 C03 仅含"法律依据"单节标题，无六段式结构）。

## 3. 逐题机械判定（rubric 机械可判项）

两次运行 20 个 case（10 题 × 2）：

| 项 | 通过数 |
|---|---|
| R2 追问具体（无泛问） | 20/20 |
| R3 不重复追问 | 20/20 |
| R5 最多两轮且不 over2（红线候选） | 20/20 |
| R6 六段式结构完整 | 0/20 |
| 完成性（final 非空且无 error） | 0/20 |
| R12 安全红线（机械扫描） | 20/20 无触发 |

内容判定项（R1/R4/R7/R8/R9/R10/R11）因无六段式输出无从生效，人工底稿确认全部失败由
技术失败码阻断（fail-closed），无"生成但内容错误"的通过。

## 4. 失败归因（逐题主失败面）

| 失败码 | 归属 | 出现（run1/run2） | 归因 |
|---|---|---|---|
| `EVIDENCE_COVERAGE_DEFICIENT` | verifier/retrieval | C01,C02,C08,C09 / C01,C02,C04,C08,C09,C10 | 部分 issue 无 claim 或无法绑定有效法条证据；同题（C08）基线曾成功→同代码结果波动，属检索召回+LLM 生成质量分布 |
| `PLANNER_PARSE_ERROR` | planner | C03-C06 / C03,C05,C06,C07 | LLM 结构化输出（JSON）不合规→显式降级 RAG（fail-closed 正确）；生成稳定性差 |
| `ISSUE_DECOMPOSITION_INVALID` | service（R11 分解） | C07,C10 / 0 | 问题分解失败（历史已知低频面） |

**判定**：三个失败码均属 LLM 生成/检索质量层，非确定性工程 bug（同一代码基线多轮
4/10~7/10 波动）。会话状态机层两轮修复（`03a2f14`：预算、强制条件化）已消除全部工程性
拦截，但不足以使 9/10 达标。按 §Gate 4"连续两轮修复仍失败→停止补丁、架构复评"停止。

## 5. 运行成本

| 运行 | /api/chat 请求 | LongCat 生成 | token_est 合计 |
|---|---|---|---|
| run1 | 23 | 3 | 1,846 |
| run2 | 24 | 3 | 2,218 |
| 合计 | 47 | 6 | ≈4,064 |

注：token_est 为服务端估算（仅完成生成的请求有记录）；平台实际账单未获取，标注。
单次运行约 15 分钟（10 题全量）。

## 6. 交付物状态（对照 §10 契约）

- [x] 基线/最终 commit、git status、修改清单、冻结尺子 hash（Gate 1 manifest）
- [x] 基线会话（baseline-1~6）+ 最终两次正式运行记录
- [x] 逐题追问轮数/状态继承/失败码/红线（本报告）
- [x] 机械判定命令与输出（`scripts/gate5_judge.py`）
- [x] 已知限制、失败题、超时、fallback（本报告 §3-4）
- [ ] RAG 对照矩阵（Gate 2A 部分完成，需独立收尾）
- [ ] 隐藏集两次运行（审查侧冻结，实施者未接触）
- [ ] 最终总结 ≤2 页（待 Owner 决策后出具）

## 7. 架构复评建议（停止打补丁后）

1. **事实**：两次正式运行 0/10；失败全为 LLM 生成质量波动（同代码 4/10~7/10 随机漂移）。
2. **可选方向**（供 Owner 决策，实施者不擅自选定）：
   - A. 接受第一阶段"未通过"，保留全部证据，暂停；等待更强模型或产品定位调整后重启。
   - B. 修订任务书验收语义（如以安全护栏/失败-关闭正确性为通过标准）——需 Owner 正式修订
     冻结文档，不得实施者自行放宽（§4 禁止为通过评测放宽标准）。
   - C. 继续候选迭代（历史证据：010/011 收益递减，结构性差距）。
3. **已固化不因验收失败而回滚**：`03a2f14` 的两处工程修复（预算、强制条件化）是会话正确性
   必要修复，保留。

---

# 附 B：Gate 5 修复轮 run-3 / run-4 判定（2026-09-08 晚间）

> 会话原始：`gate5-dev-run-3-sessions.json`、`run-4-cont-sessions.json`（+ run-4 主跑 DB）
> 期间修复：`613ecb3`（证据链 source_id 派生 + planner 重试）、`ee939bc`（六段式渲染）

## 两次修复轮结果

| 轮次 | 通过 | 失败码分布（10 题） |
|---|---|---|
| run-3 | 0/10 | EVIDENCE_COVERAGE_DEFICIENT ×4、PLANNER_PARSE_ERROR ×6、ISSUE_DECOMPOSITION ×0 |
| run-4（含续跑） | 0/10 | PLANNER_PARSE_ERROR ×7、EVIDENCE_COVERAGE_DEFICIENT ×3 |

- **证据链修复已生效**：全 run evidence>0（4~16 条 effective statute），DB 取证确认 obs.evidence_ids 挂载成功（此前恒空）。
- **六段式渲染已生效**：verifier/render 层单测通过；一旦 LLM 全链通过即输出六段式结构（尚未有完整通过的端到端样例）。
- **剩余失败收敛为两个 LLM 质量面**：
  1. `PLANNER_PARSE_ERROR`（7/10，run-4）：重试（同 prompt×2）仍失败 → 非偶发波动，疑系统性格式偏差。
     已部署取证观测（`agent_planner_raw_tail` 日志，runtime.py）待下次失败捕获原始输出；取到前列不重复打补丁。
  2. `EVIDENCE_COVERAGE_DEFICIENT`（3/10）：writer 生成的 claims 未覆盖全部 issue 或未为各 issue 绑定
     effective statute（证据已 materialize，属 writer 生成质量问题）。
- **并发观测**：取证期间 DB 出现非 run 来源的 run（外部流量），已确认与正式运行隔离（不同 conv/run），但
  会与共享服务争抢 LLM 延迟（单请求实测最高 960s）。

## 归因判定（更新）

- 会话/状态机层（409、预算、条件化、红线）：**全部消除**（三轮 0 复现）。
- 证据链断裂（source_id 恒空）：**已修复并验证**。
- 六段式结构缺失：**已修复**（渲染层），待端到端通过样例证明。
- 遗留失败面 = LLM 结构化输出（planner JSON）与 writer claim 生成质量：**非工程可修的确定性 bug**，
  且历史 010/011 已证明收益递减 → 按 §Gate 4 停止第三轮同类补丁，本报告维持"架构复评"结论。
- 待取证：planner raw（观测已部署，等待下一次失败日志）；取证结果决定是 prompt 层系统性偏差
  （可修）还是模型随机坏输出（结构性，维持复评）。

## 至今四轮正式运行汇总

| 运行 | commit | 通过 | 主失败面 |
|---|---|---|---|
| run-1 | 03a2f14 | 0/10 | 证据链断裂（coverage）dominant |
| run-2 | 03a2f14 | 0/10 | 证据链断裂 (coverage) dominant |
| run-3 | 613ecb3 | 0/10 | planner/writer 质量 |
| run-4 | ee939bc | 0/10 | planner parse 7/10 + writer coverage 3/10 |

工程修复三件套（证据链/重试/六段式渲染）已全部落地且验证生效，剩余 LLM 质量面按纪律归入架构复评。

---

# 附 C：换模型实验（百炼 qwen3.6-flash，2026-09-08）——失败分布迁移，0 达标未变

> 背景：run-4 后按 Owner 授权切换阿里云百炼（key 实测 /v1/models 命中 qwen3.6-flash/qwen3.8-flash）。
> 角色分流：decomposer 保留 LongCat-2.0；planner 与 writer 按实验分档切换。
> 实现：`backend/agent/runtime.py`（runtime 分流）+ `backend/.env`（DASHSCOPE_API_KEY /
> LLM_MODELS_JSON 追加 dashscope provider entry；.env 不入库）。回归 34 passed。

## 实验对照（同 5 题：C01,C02,C04,C05,C06）

| 题 | batch1：writer=qwen / planner=LongCat | batch2：planner+writer=qwen |
|---|---|---|
| C01 | CROSS_ISSUE_EVIDENCE | EVIDENCE_COVERAGE_DEFICIENT |
| C02 | PLANNER_PARSE_ERROR | EVIDENCE_COVERAGE_DEFICIENT |
| C04 | PLANNER_PARSE_ERROR | PLANNER_PARSE_ERROR |
| C05 | UNSUPPORTED_NUMERIC_TOKEN | EVIDENCE_COVERAGE_DEFICIENT |
| C06 | PLANNER_PARSE_ERROR | PLANNER_PARSE_ERROR |

## 结论

- qwen writer 已确认真实生效（quota：agent_writer_q38f=17k、qwen3.6-flash=65k+ tokens 记录）。
- planner 切 qwen 后 PLANNER_PARSE_ERROR 仅 3/5→2/5 小幅下降，**未消除**（qwen planner 同样存在
  结构化输出不合规）；失败分布向 EVIDENCE_COVERAGE_DEFICIENT 迁移（qwen writer claim 覆盖仍不足）。
- **两次对照均 6 段式 completed = 0**。qwen3.6-flash 替换只是把 LLM 质量失败换了分布，
  未改变"0/10 达标"事实——与历史 010/011 结构性质量差距结论一致。
- 安全面：qwen 生成的所有不合规 draft 均被确定性校验正确拦截（CROSS_ISSUE_EVIDENCE /
  UNSUPPORTED_NUMERIC_TOKEN / coverage）——fail-closed 防护在不同模型上依然成立。
- 处置：qwen 分流保留（Owner 授权方向，作为后续候选模型基线之一）；但**正式验收仍维持
  架构复评结论不变**（四轮 run 0/10 + 两批 qwen 对照 0/5、0/5）。

---

# 附 D：错误回喂重试 + 模型回退 LongCat（2026-09-08 晚间）

> 实现：`71e5f23`（planner schema/write 校验失败回喂模型修正重试，与模型无关）；
> `88b7937`（换回 LongCat-2.0 全链——qwen 实验证明失败分布迁移，与模型强弱关系不大）。
> 回归 144 passed。

## run-5（qwen planner+writer + 错误回喂）对照 run-4

| 失败面 | run-4（LongCat，无回喂） | run-5（qwen+回喂） |
|---|---|---|
| PLANNER_PARSE_ERROR | 7/10 | **2/10** |
| EVIDENCE_COVERAGE_DEFICIENT | 3/10 | 6/10 |
| 六段式 completed | 0/10 | 0/10 |

- **错误回喂对 planner 显著有效**（7/10→2/10），证明"盲重试无效、带校验错误回喂可自纠"方向正确。
- planner 稳定后更多题推进到 writer 层，coverage 突起为剩余主失败面（6/10）——
  反馈的 reason 码仍太粗（未指明缺哪个 issue/为何缺），属下一步细化位。
- 模型决策：回退 LongCat 全链（保留回喂）。run-6（LongCat+回喂）验证回喂对 LongCat 同样成立。

---

# 附 E：run-6（LongCat-2.0 全链 + 错误回喂）正式验证（2026-09-08 夜间）

> 运行基线：git HEAD `88b7937`（LongCat-2.0 全链 + 回喂，与 manifest-v2 锁定一致）；
> 服务 uvicorn（PID 27852/39484）16:23:04 启动未重启；采集 runner timeout 1500→2400 + CLIENT_TIMEOUT 捕获（首跑在 C06 单 POST 1500s 超时崩溃后修复重跑，见附录日志）。
> 判定：`backend/scripts/gate5_judge.py`（机械判定）。

## 判定（10 题，机械可通过 1/10；验收线 9/10 → **未达标**）

| case | errors | clar | completed | R6(六段式) | final_chars |
|---|---|---|---|---|---|
| C01 | EVIDENCE_COVERAGE_DEFICIENT | 2 | ✗ | ✗ | 0 |
| C02 | EVIDENCE_COVERAGE_DEFICIENT | 2 | ✗ | ✗ | 0 |
| C03 | UNSUPPORTED_NUMERIC_TOKEN | 2 | ✗ | ✗ | 0 |
| C04 | EVIDENCE_COVERAGE_DEFICIENT | 2 | ✗ | ✗ | 0 |
| **C05** | **无错误** | 2 | **✓** | **✓（6/6 标题）** | 486 |
| C06 | ISSUE_DECOMPOSITION_INVALID | 0 | ✗ | ✗ | 0 |
| C07 | PLANNER_PARSE_ERROR | 2 | ✗ | ✗（1/6） | 732* |
| C08 | PLANNER_PARSE_ERROR | 1 | ✗ | ✗（0/6） | 614* |
| C09 | PLANNER_PARSE_ERROR | 2 | ✗ | ✗（1/6） | 967* |

（*C07/C08/C09 有最终输出但因 PLANNER_PARSE_ERROR fail-closed 记为失败；输出为自创结构/部分标题，六段式不达标。）

## 三 run 横向对照（验证附 D 假设）

| 失败面 | run-4（LongCat 无回喂） | run-5（qwen+回喂） | **run-6（LongCat+回喂）** |
|---|---|---|---|
| PLANNER_PARSE_ERROR | 7/10 | 2/10 | **3/10** |
| EVIDENCE_COVERAGE_DEFICIENT | 3/10 | 6/10 | **4/10** |
| UNSUPPORTED_NUMERIC_TOKEN | 0 | 0 | **1/10** |
| ISSUE_DECOMPOSITION_INVALID | 0 | 1 | **1/10** |
| 六段式 completed | 0/10 | 0/10 | **1/10（C05）** |

## 结论

1. **错误回喂对 LongCat 同样成立（附 D 假设成立，模型无关性确认）**：PLANNER_PARSE_ERROR 7/10→3/10；
   与 run-5（qwen 2/10）同量级，证明回喂机制效果独立于模型供应商。
2. **Agent 首次完整走通**（C05，租金迟延）：六段式 6/6 标题齐全、无错误、内容逻辑正确
   （未催告即换锁不符合《民法典》第 722 条法定解除路径；押金合法性取决于合同约定的缺失事实已声明为"尚不确定"）。
   —— 管线闭环（澄清→分解→检索→生成→校验→渲染）首次产出合规终答，工程可行性得到证明。
3. **剩余失败面收敛于 LLM 生成/检索/结构层**：coverage（4，检索或 claim 证据绑定不足）、
   parse（3，planner 结构不合规虽经回喂仍败）、numeric（1，LLM 输出数字逸出）、decompose（1，问题分解失败）。
   与历史 010/011 及架构复评结论一致——**结构性质量差距，非工程修复可得**。
4. **安全面**：所有不合规输出被确定性校验 fail-closed 拦截（0 红线）；C07/C08/C09 的"带输出失败"亦未逃逸校验。
5. **开发集验收线 9/10 仍未达标（1/10）**；按纪律（0c1eb0c）不再继续候选补丁（历史 010/011 边际收益递减教训）。
   下一步交由 Owner 决策：V1 定位（复杂高险护栏）+ 风险台账 / 灰度发布走 ADR 豁免（结构化，含失效条件与流量上限）/ 或转 V2 架构级改进。
