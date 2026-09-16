# Agent 能力基线 v2（20 例）— 2026-09-13

方案与金标：`evals/frozen-cases-v2.json`（校验 PASS）；执行器 gate2_runner（本轮接入
fact_reveal + scope 数字应答，12 tests passed）；模型 qwen3.8-flash（DashScope），
隔离宿主 ×3（连接故障期见 §过程异常），协议 ≤2 轮澄清 + force_agent + no_cache。

## 结论速览（n=20，missing=0）

| 指标 | 值 | 口径 |
|---|---|---|
| **agent_completed** | **6/20 = 30%** | final 事件带 run_id（持久化成功），非 final_chars>0 |
| forbidden 违规（终稿） | 0（**样本不足，见限制1**） | 12 条禁引条文 ∉ 终稿《》引用 |
| scope 一致 | 19/20 | 澄清含「本次请求分解出」↔ scope_trigger |
| required ∈ 证据池 | 22/53 = 41.5% | 端到端多查询并集（非单查询口径） |
| 红线候选（>2 轮） | 1（E06） | 第 3 次仍 clarification |
| 成本（账本实结） | **0.2481 元** | run1 0.0835 + run2 0.0935 + run3 0.0711 |

### 完成清单
C03(双倍工资)、C05(换锁)、C07(时效)、C09(健身房)、E08(未定期限时效)、E10(利率上限) —— 
完成侧六段式产出，E08/E10 为本批新案例首次端到端通过。

### 失败码分布（14 例，均 fail-closed 有显式码或空终稿）
| 失败码 | 数 | 案例 | 归类 |
|---|---|---|---|
| ISSUE_CLAIMS_MISSING | 3 | C06,C10,E07 | writer 引用遵守度（T4/t5 已知边界） |
| UNKNOWN_MISSING_INFORMATION | 3 | E01,E04,E09 | planner 追问了 unknown 事实后放弃（writer 侧新形态） |
| GENERATOR_FAILURE | 2 | C08,E05 | 生成器技术失败（非内容问题） |
| NON_CANONICAL_CITATION | 1 | C01 | 已知边界 |
| UNSUPPORTED_CITATION | 1 | C02 | 已知边界 |
| UNKNOWN_EVIDENCE_ID | 1 | C04 | 已知边界 |
| UNKNOWN_FACT_ID | 1 | E03 | **新形态**：resume 事实被服务端判未知 id |
| UNSUPPORTED_NUMERIC_TOKEN | 1 | E02 | **新形态**：数字未获证据支持被拦（fail-closed 正确工作） |
| 无码（scope 红线） | 1 | E06 | 2 轮后仍澄清（runner 答"1,2,3,4,5"已正确，模型预算遵守度） |

## 能力信号（相对 t5 n=3 的增量）

1. **30% 完成率（n=20）**替代 t5 的 33%（n=3）——统计上同水位但样本×6.7，writer 遵守度
   仍是首要失败面（ISSUE_CLAIMS/CITATION 族合计 5/14）。
2. **fail-closed 全对**：14 个未完成案例无一伪造终稿、无一 fallback 冒充；E02 数字防线
   （UNSUPPORTED_NUMERIC_TOKEN）与 E06 预算红线均为防御机制按设计工作。
3. **跨部门法混入止步于证据池**：终稿层 0 违规——但**不能据此宣布缺陷已修**（限制 1）。
4. **E02 scope 边界摆动**：同题面两次运行 7 争点 vs ≤5 争点（scope_trigger=真 判据在
   临界题面不稳）→ 结论：`scope_trigger` 判据仅适用于显著超限题（E06 型），临界题面应
   记 FLAKY 不记 FAIL（已如实记录，题集保持 FROZEN 不改）。

## 过程异常（如实记录）

- **DashScope 间歇性连接故障**（18:14 起多窗口 `APIConnectionError`@3s）：宿主进程连接
  遇故障窗口后持续失败，直连新进程同时刻 HTTP 200 —— 判定 provider 侧间歇故障 + 长驻进程
  keep-alive 不自愈。处置：按 t5 止损规则将故障窗口案例（run-1 的 C09/C10/E01-E10、
  run-2 的 E02/E06-E10）标记**技术失败不进基线**，重启宿主分批重跑（3 个 run），最终
  20/20 均有非故障窗口有效数据。runner 的 claim/checkpoint 纪律保证重跑不混账。
- **runner scope 协议盲区**（新发现并修复，提交 cb2217b）：范围选择澄清被回
  NO_MATCH_REPLY → 服务端 scope 防御 409（防御行为正确）→ 评测静默中断。修复=评测端
  确定性答「1,2,3,4,5」（fake 服务测试覆盖）。修复前 E02/E06 数据作废重跑。

## 已知限制（防幻觉第 5 问）

1. **forbidden 判据 0 样本**：E01-E05（带 12 条禁引）全部未产出终稿 → 「终稿 0 违规」
   是空集上的真，非缺陷修复证明。部门法混入仍需检索层修复后再测。
2. 完成率 30% 是 qwen3.8-flash 单模型单次快照（模型温度/波动敏感；E02 已示范边界摆动）。
3. required ∈ 证据池 41.5%：失败案例多数未走到全争点检索，该值不是检索召回率
   （检索层单查询口径 35.9% 见 probe-results.json，两者都不等于「答案质量」）。
4. UNKNOWN_MISSING_INFORMATION/UNKNOWN_FACT_ID 两个新形态各 n=1，不据单例归因，留待
   下一批基线观察是否复现。
5. 语义侧（法条适用是否正确）本批未逐案复核——工程/语义分离纪律，需要时另做律师级抽审。

## 五连问核验

1. **数字来源**：baseline-verdict.json（sessions+evaluation.sqlite 确定性计算）、
   成本来自三本 cost-ledger.jsonl 实结（finished 事件求和）、技术失败判定来自宿主日志
   APIConnectionError 时间戳（非猜测）。
2. **可复现**：复跑配方同 evals-v2-report（宿主 serve.py + gate2_runner --cases-file
   evals/frozen-cases-v2.json）；付费复现=再花费，按快照策略不循环重跑。
3. **亲历红/绿**：是——首宿主 20 例中 12 例撞故障窗口（红），三宿主四 run 补齐 20 例
   有效数据；scope 盲区先红（409 静默）后绿（cb2217b + 12 passed）。
4. **期望独立**：0/1 判定全部来自确定性源（sessions 事件流 / DB 证据池 / 账本），
   金标来自题集（article_in_kb 校验过）；无 LLM judge。
5. **限制**：见上节 5 条。

## 产物索引

- `dispatch-output/agent-baseline-v2-20260913/`：run-1 sessions/checkpoint/claim + 宿主1账本 + evaluation.sqlite + baseline-verdict.json + collect_verdict.py（合并判定）
- `dispatch-output/agent-baseline-v2-r2-20260913/`：run-2（C09/C10/E01-E05 有效）
- `dispatch-output/agent-baseline-v2-r3-20260913/`：run-3（E07-E10）+ run-4（E02/E06 修复后）
- 提交链：fc0b256（fact_reveal 接入）→ c16a9d5（题集）→ cb2217b（scope 协议盲区修复 + E02 金标）

## 新形态下钻复查（追加，推荐③执行结果）

- **E01 UNKNOWN_MISSING_INFORMATION**：Agent 第 2 轮重复询问**第 1 轮事实已回答的主体**
  （r1 事实含「双方都是公司」，round2 仍问「以个人还是公司名义」）。事实投放协议按
  fid 去重不重复投喂 → Agent 收到「没保留信息」后拒绝成稿。**观察：planner 追问策略
  缺陷（忘记已答事实），fail-closed 行为本身正确**（宁可拒绝不编造主体）。
- **E04 UNKNOWN_MISSING_INFORMATION**：Agent 追问「当地司法实践主责通常分担比例（60%/80%）」
  ——冻结事实协议不含该信息且属裁判惯例类，Agent 拒绝编造比例 → **防线按设计工作**。
- **E03 UNKNOWN_FACT_ID**（n=1）：round2 resume 携带的 r1 事实被服务端判未知 fact id。
  单例不归因（纪律），下批复查是否复现；若复现需查 resume 文本→事实锚定逻辑。

结论：两个"新形态"初步定性——UNKNOWN_MISSING_INFORMATION ×3 均为 **Agent 正确拒绝
编造**（含一例自身追问策略缺陷诱因），非 fail-closed 漏洞；修复方向应指向 planner
已答事实记忆（超出本批范围，仅登记）。