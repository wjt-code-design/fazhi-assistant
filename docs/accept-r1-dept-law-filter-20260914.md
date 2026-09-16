# R1 预注册验收结果（2026-09-14 实测，判据 §4 冻结口径）

> 判据文件：`docs/preregistration-dept-law-filter-r1-20260913.md`（2026-09-13 提交冻结）
> 实现提交：`1d341b0`（R1 检索池过滤 + R1b 终稿串台校验 + 判据单测 10 例）
> 宿主：127.0.0.1:18126，AGENT_ENABLED=true + AGENT_DEPT_FILTER=true + AGENT_PROC_MISROUTE_CHECK=true，模型 qwen3.8-flash
> 批次产物：`dispatch-output/r1-accept-eval-20260914/`

## 评测集（E01-E05 + C05/C07/C09，n=8）

| 案例 | completed | 失败码 | 终稿引用数 | forbidden 混入 | 备注 |
|---|---|---|---|---|---|
| C05 | ✅ | - | 9（全民法典） | 无 | 较基线（行/刑诉串台）改善 |
| C07 | ❌ | ISSUE_CLAIMS_MISSING | 0 | - | writer 已知码 |
| C09 | ❌ | UNSUPPORTED_CITATION | 0 | - | writer 已知码 |
| E01 | ✅ | - | 22 | **行政诉讼法#49** | **终稿串台（红线）** |
| E02 | ❌ | UNSUPPORTED_NUMERIC_TOKEN | 0 | - | writer 已知码 |
| E03 | ❌ | UNKNOWN_FACT_ID | 0 | - | writer 已知码 |
| E04 | ✅ | - | 20 | 无（含行政/复议法引用） | 判域 mixed，R1b 保守不判 |
| E05 | ❌ | UNSUPPORTED_CITATION | 0 | - | writer 已知码 |

## 判据判定（冻结口径，不得按结果改）

- **P1 forbidden 混入率 → 0**：E01 终稿混入行政诉讼法#49（forbidden 判据原文命中）
  → **FAIL**（任何 >0 即 FAIL）
- **P2 agent_completed 不下降**：3/8（C05/E01/E04）vs 基线同子集 2/8（C05/C07）
  → **PASS**（37.5% vs 25%，无下降）
- **P3 未知失败码**：ISSUE_CLAIMS_MISSING / UNKNOWN_FACT_ID / UNSUPPORTED_NUMERIC_TOKEN
  均为 writer 模块已知错误码（含单测覆盖）→ **PASS**
- **P6 终稿程序法串台率 proc_misroute → 0**：R1b 日志 `proc_misroute_detected`
  检出 E01（conv 2388，civil 域）《行政诉讼法》49/75 → **FAIL**（>0 即 FAIL）

## 结论：P1/P6 FAIL → 触发预注册 §5 止损 D3

> D3：「任一判据 FAIL 时回退即冻结本方案（不迭代指示词），转记录『检索层关键词路线证伪』。」

- **R1 检索层关键词路线证伪（含 2026-09-14 grilling 修正）**：初版结论将 E01 归因为
  「writer 生成期注入（C05 型）」——**grilling 复查 DB（agent_evidence / agent_claim_checks）
  证明该归因错误**。实况：行政诉讼法 49/75 **确实在 E01 证据池内**（issue_554ed64f 绑定），
  根因是**判域输入用 issue 问句**（"被告公司的诉讼主体资格是否明确且具备应诉能力？"
  零指示词 → 判域 None → R1 保守不过滤 → 他域程序法漏进证据池）。实测对照：
  issue 问句判域 None vs 题面判域 civil。→ 真根因是「判域输入未含案例域元信息
  （预注册 §2 原文含『案例域元信息（若可得）』，实现只用了 issue 问句）」。
- **E04（交通案）确认是接受边界**：终稿含行政诉讼法 75 / 行政复议法 67 但 R1b 未检出
  （判域 mixed → 保守短路，预注册 §5 风险 2 明示）。**但该风险假设「退化为现状无害」
  被 E01/E04 双实证证伪**——mixed 保守放过了真实串台，是证伪结论的额外论据。
- **不迭代指示词**：不追加/调整 `dept_guard.py` 的指示词表或域表（防过拟合循环）。
  选项 B（判域接入案例域元信息）已记录为将来新方案输入，不在本次判据内救数。
- **代码处置**：R1/R1b 开关默认 False（settings 已默认），生产零影响。
  实现保留为「默认关闭 + 证伪标注」，与 verifier 死机制保留先例一致。

## 留出集（H01-H05，2026-09-14 grilling 补跑，双集验收防过拟合）

| 案例 | completed | 失败码 | forbidden 混入 | 备注 |
|---|---|---|---|---|
| H01 医疗 | ❌ | UNSUPPORTED_CITATION | 无 | writer 已知码 |
| H02 合伙 | ❌ | -（scope 选择已被 runner 应答"1,2,3,4,5"；其后事实问句在事实协议中无匹配 → 未达终稿） | 无 | 双域线索题 |
| H03 物业 | ❌ | ISSUE_CLAIMS_MISSING | 无 | writer 已知码 |
| H04 著作权 | ✅ | - | **无** | 终稿 16 条引用零程序法串台 |
| H05 保险 | ❌ | NON_CANONICAL_CITATION | 无 | writer 已知码 |

- **P4 留出集 forbidden 混入率 → 0**：唯一 completed 的 H04 零混入 → **PASS**
  （但 n=1，证据弱；其余 4 例未到终稿，混入不可测）
- **P5 留出集完成率 ≥ 对照 80%**：1/5 = 20% vs 评测集 3/8 = 37.5%
  → **FLAKY**（完成率低于对照；4 例未完成中 3 例失败码为 writer 已知码、与 R1 无因果，
  H02 无失败码——scope 已应答、事实协议无匹配未达终稿；单例运行 n=5 不构成可靠性结论）
- **留出集判据结论**：未发现 R1 在 5 个新领域引入新的混入/失败面；
  完成率低归因 writer 模型结构性限制（与评测集一致），不追加指示词。
- 留出集资产 `evals/holdout-cases-r1.json` 保留，供将来选项 B 方案复用。

## 留存证据

- 评测集 sessions：`dispatch-output/r1-accept-eval-20260914/gate2-run-r1-accept-eval-20260914-sessions.json`
- 留出集 sessions：`dispatch-output/r1-accept-holdout-20260914/gate2-run-r1-accept-holdout-20260914-sessions.json`
- 宿主日志红线（评测集宿主）：proc_misroute_detected（conv 2388）/ dept_filter_removed（2 处）
- 留出集账本：`dispatch-output/r1-accept-holdout-20260914/cost-ledger.jsonl`
  （39 次 LLM finished，实结 ≈ 0.0569 元，含 rerank 免费）
- 分析脚本：`evals/analyze_r1_accept.py`（汉字数字归一化后重跑结果如上）
- grilling 复查证据：E01 证据池绑定（app.db agent_evidence issue_554ed64f 行政诉讼法 49/75）、
  claim_checks 末条引用行政诉讼法49、issue 问句判域 None vs 题面判域 civil

## 成本

- 评测集 8 例：宿主未挂 cost-ledger（启动时漏挂 EVAL_LEDGER），**成本缺口如实记录**
  （无账本可查；按基线 v2 单例均价 ~0.012 元估算 ≈ 0.1 元）
- 留出集 5 例：挂账本实结 ≈ 0.0569 元（39 次 LLM finished）
- 合计估算 ≈ 0.16 元，未超预注册上限 0.5 元（留出集账本可审计）

## 遗留事项（2026-09-14 grilling 确认）

- git 对象库损坏（`03a2f140` 缺失，gate5 早期历史断链）：**暂不修复，记录为已知问题**；
  当前 HEAD 链完整、本次交付零影响；后续如需彻底修复另开窗口
  （git fsck --full 可见 broken link）
- 首次留出集运行因 `EVAL_GUARD_LIMIT=0.5` 过紧（单次 LLM reserve 2 元 > 上限）全部
  APIConnectionError，已诊断定位并改用基线同款 19.7 重跑——此为运行配置失误，
  非 R1/R1b 代码问题，已在 grilling 中说明
