# Q1 方案 B 稳定性读数：k-of-m 聚合 + 冻结工资回归集

日期：2026-10-23（§1–§11）；§12–§13 于 2026-10-24 追加。性质：评测侧新增聚合口径与回归集，并做 live 复跑；**不改线上路径**。本文写作时的“未提交”状态已由后续提交 `5bae84c1`、`b752a11b` 收口。
前置：[B 落地报告](file:///c:/Users/33393/Desktop/ai-legal-helper/docs/process-archive/reviews/2026-10-23-round67-q1-support-reviewer.md)、[Q1 缺口复核](file:///c:/Users/33393/Desktop/ai-legal-helper/docs/process-archive/reviews/2026-10-23-round67-q1-support-gap-review.md)。

## 0. 结论

- 聚合口径已固定并有测试钉住：**k 轮中 ≥m 轮判 false 才判 `UNSUPPORTED`**；失败票既不算 true 也不算 false，凑不够阈值就是 `INSUFFICIENT_EVIDENCE`。
- 冻结工资回归集 6 条 claim，本轮 3 轮 live 复跑：**18/18 调用成功、18/18 判 false、聚合 6/6 `UNSUPPORTED`、回归 6/6 PASS**。
- 但这是 18 次调用的样本，**不能据此宣称"稳定性问题已解决"**：上一轮已实测过 1 次翻转、1 次非逐字 span、1 次 JSON 解析失败（见 §4）。本轮零失败只是"本轮零失败"。

## 1. 聚合口径（代码与规则）

实现：[support_review.py](file:///c:/Users/33393/Desktop/ai-legal-helper/backend/scripts/support_review.py) 的 `aggregate_rounds(requests, rounds, required_false=2)`。

| 条件 | 结论 |
|---|---|
| `unsupported_votes >= required_false` | `UNSUPPORTED` |
| `support_votes > rounds - required_false` | `SUPPORTED` |
| 其余（失败票过多） | `INSUFFICIENT_EVIDENCE` |

关键约束：
- 失败票（`JUDGE_FAILURE` / `INVALID_JUDGE_OUTPUT` / 该轮未跑到该 claim）**不计入支持票**，也不折算成 false；
- `unsupported_spans` 取所有 false 轮的并集去重（保序），不是单轮抽样；
- `required_false` 必须在 `1..rounds`；重复 claim_id、轮内未知 claim_id 直接 `ValueError`。

runner 已改为**逐 claim 单独调用**（`review((request,), judge)`），一条 claim 的输出违约不再让同轮其他 claim 变成"未判"。

## 2. 回归集

文件：`dispatch-output/round67-q1-20261023/regression-salary.json`（schema `support-review-regression/v1`）。

6 条冻结 claim 全部标 `UNSUPPORTED`，覆盖四类缺口：未签期间起止、仲裁时效、满一年后终止与上限、计算基数。索引与 draft 内顺序一致，避免长哈希手抄错误。

## 3. 本轮读数

命令：

```
python dispatch-output/round67-q1-20261023/run_support_review.py --live --repeat 3 --regression
```

输出：`support-review-regression.out`（sha256 `5A11D47482A1F1E23E072D2075769BCF9A7C14762C00A7AE7087BA611E018857`）。耗时 602 秒（18 次调用，约 33 秒/次）。

| draft | claim | 3 轮投票 (true/false/fail) | 聚合 |
|---|---|---|---|
| writer-replay | `claim_cf3828` | 0 / 3 / 0 | UNSUPPORTED |
| writer-replay | `claim_1075b4` | 0 / 3 / 0 | UNSUPPORTED |
| writer-replay | `claim_b8fcb2` | 0 / 3 / 0 | UNSUPPORTED |
| writer-replay | `claim_9a5413` | 0 / 3 / 0 | UNSUPPORTED |
| writer-support-fix | `claim_3fa721` | 0 / 3 / 0 | UNSUPPORTED |
| writer-support-fix | `claim_d0510d` | 0 / 3 / 0 | UNSUPPORTED |

`REGRESSION_RESULT: 6/6 PASS`。span 均逐字出现在 claim 原文；同一 claim 不同轮给出的 span 粒度不同（例如 `claim_cf3828` 分别命中「受时效限制」与「未签期间外推」），聚合后取并集去重。

## 4. 与上一轮读数的对照（不隐藏负面）

上一轮（批式 `review(requests)`、2 轮 + 单轮 raw 探针）的失败面：

| 现象 | 次数 |
|---|---|
| span 非逐字（`JUDGE_SPAN_NOT_VERBATIM`） | 1 |
| 模型输出 JSON 解析失败 | 1 |
| 同一 claim 翻转成 supported=true（`claim_3fa721`） | 1 |

本轮（逐 claim 调用、3 轮）这些现象**一次都没出现**。差异可能来自：
1. 逐 claim 调用降低了单次输入长度与指令干扰；
2. 样本量小（18 次），失败形态本来就是低频。

因此当前只能写"本轮 6/6 PASS"，**不能写"失败率 0"**。要给出可信的失败率，需要把重复轮数拉到能算出置信区间的量级（例如 30–50 轮或跨日复跑），这属于后续待办，不在本轮范围。

## 5. 控制与验证

- 单元测试：`pytest tests/test_agent_support_review.py -q` → **25 passed**；`ruff check` → All checks passed。
- 聚合一红控制：把 `if unsupported_votes >= required_false` 临时短路后，`test_aggregate_two_false_of_three_is_unsupported` **failed**（返回 `INSUFFICIENT_EVIDENCE`）；还原后 25 passed。说明阈值行为不是装饰。
- 运行参数守护：`--required-false` 越界（如 repeat=3 时传 0 或 4）由 argparse 直接拒绝；`--regression` 以 JSON 内的 `required_false` 为准，避免命令行与文件口径分叉。

## 6. 剩余边界

1. **样本量**：本条写作时为 18 次调用，不足以估计失败率；§8 已扩到 60 次、§13 补了难绿样本。
2. **阈值仍是人为选择**：本条写作时为 2-of-3；§10 已固定为 2-of-5 并做敏感性复核，但它仍是口径选择，不是法律判据。
3. **只覆盖工资样本**：回归集只有 6 条 claim，未覆盖其他法律领域与正常答案（正常答案的绿对照仍是独立探针，3/3 supported=true，见 B 落地报告）。
4. **仍不接线上**：聚合结果只写评测文件，`agent/service.py` / `agent/runtime.py` / `main.py` 零引用（有测试钉住）。

## 7. 本轮改动（写作时全部未提交；后续已入库 `5bae84c1` / `b752a11b`）

- `backend/scripts/support_review.py`：新增 `AggregateStatus` / `AggregatedVerdict` / `aggregate_rounds`
- `backend/tests/test_agent_support_review.py`：新增 7 个聚合用例（25 passed）
- `dispatch-output/round67-q1-20261023/run_support_review.py`：逐 claim 调用 + 聚合输出 + `--regression`
- 新增 `regression-salary.json`、`support-review-regression.out`
- 本报告

## 8. 大样本复跑（2 × 5 轮，60 次调用）

第 6 项待办：把样本量从 18 次扩到 60 次，量化失败率与漏判率。

命令（两条并行，产物分开）：

```
python dispatch-output/round67-q1-20261023/run_support_review.py --live --repeat 5 --regression --out .../support-review-r5a.out
python dispatch-output/round67-q1-20261023/run_support_review.py --live --repeat 5 --regression --out .../support-review-r5b.out
```

产物 sha256：`r5a = B7A14A3F…CAA9`、`r5b = A1E6330B…0B15`；两次共耗时约 18 分钟（每组 30 次调用，约 36 秒/次）。

### 8.1 总体

| 指标 | 读数 |
|---|---|
| 调用次数 | 60（2 组 × 5 轮 × 6 claim） |
| 成功产出 verdict | 56 |
| 未产出 verdict | 4（**6.67%**，Wilson 95% CI **2.62%–15.93%**） |
| 其中 `JUDGE_FAILURE` | 3（原因未细分） |
| 其中 `JUDGE_SPAN_NOT_VERBATIM` | 1 |
| 回归 PASS | 每组 6/6，合计 **12/12** |

### 8.2 逐 claim 投票（10 轮）

| claim | true / false / 失败 | 单次判 false 比例 | 2-of-5 聚合 |
|---|---|---|---|
| `claim_cf3828` | 0 / 7 / 3 | 70% | UNSUPPORTED |
| `claim_1075b4` | 1 / 8 / 1 | 80% | UNSUPPORTED |
| `claim_b8fcb2` | 0 / 10 / 0 | 100% | UNSUPPORTED |
| `claim_9a5413` | 0 / 10 / 0 | 100% | UNSUPPORTED |
| `claim_3fa721` | 0 / 10 / 0 | 100% | UNSUPPORTED |
| `claim_d0510d` | 4 / 6 / 0 | **60%** | UNSUPPORTED |

### 8.3 这组读数改变了什么

1. **阈值能过，但会掩盖单条 claim 的低灵敏度**：`claim_d0510d` 单次只有 60% 判 false（4/10 判 true），2-of-5 聚合成 `UNSUPPORTED` 看似通过；若把口径收紧到"≥8/10 判 false"，它就会失败。也就是说"回归 12/12 PASS"只证明当前 2-of-5 口径下能过，不等于该 claim 被稳定识别。
2. **失败不是均匀噪声**：4 次未产出结论里 3 次落在 `claim_cf3828`，1 次在 `claim_1075b4`；其余 4 条 claim 10/10 全部成功。这更像 claim 级敏感性（文本长度/结构），而不是全局限流。
3. **失败率区间仍宽**：60 次里 4 次失败，95% CI 上界约 16%。上一轮 18 次零失败与"真实失败率 6.7%"并不矛盾——18 次零失败的概率约 29%。
4. **`JUDGE_FAILURE` 仍不可归因**：3 次只有状态码，没有异常类型/解析错误信息。要区分"网络抖动"与"模型输出坏 JSON"，需要第 3 项（输出容错与可观测）落地。

### 8.4 结论

- 大样本支持"聚合口径可复现地判出这 6 条缺口 claim"，**不支持**"审查器已稳定"。
- 下一步优先级应从"继续加样本"转为**第 3 项：失败归因 + JSON 容错策略**；否则再加 100 次调用也只能得到"失败率 6%±5%"，无法定位。

## 9. 失败归因与 JSON 容错（第 3 项）

### 9.1 改动

实现：[support_review.py](file:///c:/Users/33393/Desktop/ai-legal-helper/backend/scripts/support_review.py)

| 机制 | 行为 |
|---|---|
| 调用层异常归因 | `reason_code = JUDGE_FAILURE:<异常类名>`（如 `JUDGE_FAILURE:TimeoutError`）。只记类名，不记异常文本（可能含 URL/key/prompt） |
| 输出不可解析 | `LLMSupportJudge` 无 JSON 对象或 `json.JSONDecodeError` → 新增 `JudgeOutputUnparseable`（可重试类） |
| 输出非对象 | 顶层不是 dict → `JUDGE_OUTPUT_NOT_OBJECT`（与"内容违约"分开归因） |
| 重试策略 | 仅 `JUDGE_OUTPUT_UNPARSEABLE` / `JUDGE_OUTPUT_NOT_OBJECT` 在**同一证据封闭请求**上重试一次；契约违约（span 非逐字、spans 自相矛盾、claim_id 串号、supported 非 bool）**不重试** |
| 重试后仍坏 | 保持 `INVALID_JUDGE_OUTPUT`（不可解析）或 `JUDGE_FAILURE:<类型>`（调用异常），**不兜底成 false** |
| 可观测 | `SupportReviewResult.attempts` = 本次调用总次数（含重试）；runner 的 `NO_VERDICT` 行同时打印 `attempts` |

### 9.2 测试读数

- `pytest tests/test_agent_support_review.py -q` → **34 passed**（25 + 9 个新用例：异常类型归因 ×3、不可解析重试成功、非 dict 重试成功、重试后仍坏、契约违约不重试、`LLMSupportJudge` 两类解析路径）。
- `ruff check scripts/support_review.py tests/test_agent_support_review.py` → All checks passed。
- **一红控制**：把 `_MAX_JUDGE_ATTEMPTS` 临时改为 1 后，`test_unparseable_output_is_retried_once_then_succeeds`、`test_non_object_output_is_retried_once_then_succeeds`、`test_unparseable_output_after_retry_stays_invalid` **3 个用例 failed**；还原为 2 后 34 passed。重试不是装饰。

### 9.3 live 归因样本（5 轮 × 6 claim = 30 次调用）

```
python dispatch-output/round67-q1-20261023/run_support_review.py --live --repeat 5 --regression --out .../support-review-r5c-attributed.out
```

产物 sha256 `CECB42B3F9599E3B95B31A1D34A6D8751BDF701AF8B011F11776EA6E2C51EEAD`。

| 指标 | 读数 |
|---|---|
| 调用次数 | 30 |
| 未产出 verdict | 1（**3.33%**，Wilson 95% CI **0.59%–16.67%**） |
| `JUDGE_FAILURE:<类型>` | **0** |
| `JUDGE_OUTPUT_UNPARSEABLE` / `NOT_OBJECT` | **0** |
| `JUDGE_SPAN_NOT_VERBATIM` | 1（`claim_cf3828`，round 2，`attempts=1`） |
| 2-of-5 聚合 | 6/6 `UNSUPPORTED`，`REGRESSION_RESULT: 6/6 PASS` |

这次唯一的失败落在 `claim_cf3828`，且 `attempts=1`——按策略，span 非逐字属于内容违约，**没有**触发重试，符合预期。

逐 claim（5 轮）：

| claim | true / false / 失败 | 聚合 |
|---|---|---|
| `claim_cf3828` | 1 / 3 / 1 | UNSUPPORTED |
| `claim_1075b4` | 1 / 4 / 0 | UNSUPPORTED |
| `claim_b8fcb2` | 0 / 5 / 0 | UNSUPPORTED |
| `claim_9a5413` | 0 / 5 / 0 | UNSUPPORTED |
| `claim_3fa721` | 0 / 5 / 0 | UNSUPPORTED |
| `claim_d0510d` | 2 / 3 / 0 | UNSUPPORTED |

### 9.4 与 §8 的合并读数

三次 live 复跑合计 **90 次调用**：失败 5 次（**5.56%**，Wilson 95% CI **2.40%–12.36%**），其中 `JUDGE_FAILURE` 3 次（**均发生在引入归因之前**，无类型信息）、span 违约 2 次。

| claim | 15 次调用中的失败 | 失败率 | 说明 |
|---|---|---|---|
| `claim_cf3828` | 4 | **26.7%** | §8 的 3 次 `JUDGE_FAILURE` + §9 的 1 次 span 违约 |
| `claim_1075b4` | 1 | 6.7% | §8 的 1 次 `JUDGE_FAILURE` |
| 其余 4 条 | 0 | 0% | 60/60 成功 |

`claim_d0510d` 的漏判（判 true）两次样本合并后为 6/15 ≈ 40%，即单次判 false 仅 **60%**，与 §8.3 的结论一致：2-of-5 能把它聚合为 `UNSUPPORTED`，但这条 claim 的识别灵敏度确实低。

### 9.5 这次读数**没有**证明什么

1. **归因路径没被 live 触发**：30 次里没有一次 `JUDGE_FAILURE:<类型>`。§8 的 3 次调用异常仍无法回溯归类，"网络抖动 vs 坏 JSON"这个问题在 live 上**仍未回答**；只能说"归因能力已就绪，等下一次失败样本"。
2. **重试策略没被 live 触发**：30 次里没有不可解析输出，`attempts` 全为 1。重试对失败率的影响**未测**（只有单测与一红控制证明其行为）。
3. **归因粒度只到异常类名**：若上游把超时/限流/鉴权包装成同一异常类型，同类内仍不可细分。
4. **样本量**：30 次、1 次失败，CI 上界仍到 16.7%；两次样本合并后 CI 上界 12.4%。不能写"失败率已降到 3%"。
5. **只覆盖工资域**，且仍**不接线上**（`agent/service.py` / `agent/runtime.py` / `main.py` 零引用，有测试钉住）。

## 10. 正常答案绿对照与阈值敏感性（第 4、5 项）

### 10.1 绿对照设计

文件：[regression-green.json](file:///c:/Users/33393/Desktop/ai-legal-helper/dispatch-output/round67-q1-20261023/regression-green.json)（schema `support-review-green/v1`）。

- 12 条正常 claim：工资域 6 条（《劳动合同法》第十四条 / 第八十二条）× 保证域 6 条（《民法典》第六百八十六条 / 六百八十八条 / 六百九十二条 / 六百九十三条）；
- 构造方式：逐字引用 7 条、事实适用/条文转述 4 条、多条条文合并 1 条；
- 每条 case 单独一个证据封闭请求，fact 只用 `fact_indices` 索引、证据只用 `source_ref` 解析，claim_id / fact_id 全部由服务端重算，避免手抄哈希；
- runner 新增 `--green`（[run_support_review.py](file:///c:/Users/33393/Desktop/ai-legal-helper/dispatch-output/round67-q1-20261023/run_support_review.py)），先 `--green` 做 dry-run 确认 12 条请求全部构造成功，再 `--green --live --repeat 5`。

### 10.2 读数

产物：`support-review-green-live.out`，sha256 `FBFE3A65E6028A198DA114375D07740A01115A0B5F91BAC14BBE03773134D55C`。

| 指标 | 读数 |
|---|---|
| 调用次数 | 60（12 case × 5 轮） |
| 单次判 true | **59/60 = 98.33%** |
| 单次判 false（单次误杀） | **1/60 = 1.67%**（Wilson 95% CI **0.29%–8.85%**） |
| 调用失败 | 0 |
| 2-of-5 聚合 `SUPPORTED` | **12/12 PASS** |
| case 级聚合误杀 | **0/12**（n 太小，Clopper–Pearson 95% 上界约 **26.5%**） |

唯一的单次 false 出现在 `guarantee-apply-692` 第 3 轮：span `保证期间为主债务履行期限届满之日起六个月`，rationale 为「主债务履行期限是否明确未决，法条规定不明确时保证期间自宽限期届满起算，claim 未区分」。这条 objection 是**可辩护的**：该争点的未决事实正是「主债务履行期限是否明确及其届满之日」，而第六百九十二条后半段另有宽限期起算规则。因此它更像「绿样本的边界情形 / 判据口径分歧」，而不是输出故障或纯噪声。保留在样本里，不通过改 prompt 掩盖。

### 10.3 红绿分离度

| 样本 | 调用 | true | false | 未判 |
|---|---|---|---|---|
| 绿对照（§10.2） | 60 | 59（98.3%） | 1（1.7%） | 0 |
| 缺口回归（§8 + §9） | 90 | 9（10.0%） | 76（84.4%） | 5（5.6%） |

两端分离明显，但必须注明：绿样本以逐字引用/直接转述为主，属于**最容易的绿**；真正的误杀风险在「多跳转述、事实组合、正常但表述不精确」的答案上，本样本没有覆盖。

### 10.4 阈值敏感性（基于实测概率的估计）

参数：绿样本单次误判概率 `p_false = 1/60 ≈ 1.67%`（另给保守值 5%）；`claim_d0510d` 单次判 true 概率 `p_true = 6/15 = 40%`。假设各轮独立（**不严格成立**：同一模型、同一 prompt，存在相关性，故本表只作口径选择的量级参考）。

| 口径 | 绿样本聚合误杀（p_false=1.67%） | 绿样本聚合误杀（保守 p_false=5%） | d0510d 漏判（p_true=40%） |
|---|---|---|---|
| 1-of-3 | 4.9% | 14.3% | 6.4% |
| 2-of-3 | 0.08% | 0.73% | **35.2%** |
| **2-of-5** | **0.27%** | **2.26%** | **8.7%** |
| 3-of-5 | <0.01% | 0.12% | 31.7% |

**结论：把评测口径固定为 2-of-5。**
- 2-of-3 在 `claim_d0510d` 上的漏判估计高达 35%——之前 18 次「6/6 PASS」正是 2-of-3，读数偏乐观；
- 1-of-3 虽然对 d0510d 更敏感，但绿样本聚合误杀 4.9%（保守 14.3%），对评测器不可接受；
- 3-of-5 把 d0510d 漏判拉回 31.7%，等于用灵敏度换纯度；
- 2-of-5 是唯一同时把两类错误压在约 10% 以内的组合，代价是每次判定 5 倍调用（离线评测可接受）。

### 10.5 用已有投票做经验复核（零新增调用）

上面的表是独立二项假设下的估计。为减少假设，直接把 r5a / r5b / r5c（缺口，各 5 轮）与绿对照（5 轮）的**逐轮投票**按滑动窗口重算。缺口集 6 claim × 3 次运行、绿集 12 case × 1 次运行；3 轮窗口有 3 个起点，5 轮窗口 1 个，窗口**互相重叠**，因此是"窗口数"不是独立试验数。

| 口径 | 缺口漏判（期望 UNSUPPORTED） | 绿样本误杀（期望 SUPPORTED） | 其中 d0510d 漏判 |
|---|---|---|---|
| 1-of-3 | 0/54 | **3/36（8.3%）** | 0/9 |
| 2-of-3 | **6/54（11.1%）** | 0/36 | **6/9（66.7%）** |
| **2-of-5** | **0/18** | **0/12** | **0/3** |
| 3-of-5 | 0/18 | 0/12 | 0/3 |

与估计表的对照：
- 方向一致：2-of-3 的缺口漏判全部落在 `claim_d0510d`，且经验值（6/9 窗口）比二项估计（35%）更差；1-of-3 的绿样本误杀集中在 `guarantee-apply-692` 的那 1 次 false（含该轮的 3 个窗口全部翻成 UNSUPPORTED）。
- 数值不能直接比：窗口重叠、d0510d 只有 9 个窗口、绿集只有 1 次运行，经验频率的方差很大。
- 2-of-5 与 3-of-5 在本批数据上都没有出错；但 3-of-5 对边界缺口更保守（估计漏判 31.7%），不因这批"零漏判"就选它。

### 10.6 边界

1. **绿样本仍是「容易的绿」**：12 条里 7 条逐字引用，且全部单条文/双条文短句；不含多跳推理、含保留意见、含"无法确定"表述的正常答案。
2. **case 级样本量不足**：0/12 误杀的 95% 上界约 26.5%，不能写"聚合无误杀"。
3. **敏感性复核来自重叠窗口**（§10.5），不是同一批样本按不同口径各独立复跑；窗口不独立，只能作方向性证据。
4. **仍只覆盖两个域、且不接线上**；线上阻断的前置条件（绿样本扩样 + 人工仲裁流程）仍未满足。

## 11. `claim_cf3828` 失败归因（第 6 项遗留）

§9 留了一个空白：那次 live 没触发调用异常与不可解析输出，所以"旧 3 次 `JUDGE_FAILURE` 到底是什么"没有 live 答案。本次用 raw 探针对历史失败率最高的 `claim_cf3828` 单独跑 12 次（其余 claim 不动）。

命令：

```
python dispatch-output/round67-q1-20261023/inspect_support_review_raw.py --claims claim_cf3828 --repeat 12 --out cf3828-raw-12.out
```

产物 sha256 `2812B58F1E127EF7CECE5057598E126C04623966BFF7DE88E8F7F2A65C5F3197`。

### 11.1 读数

| 结果 | 次数 | 占比 |
|---|---|---|
| 有效 verdict：supported=false | 7 | 58.3% |
| 有效 verdict：supported=true | 2 | 16.7% |
| `INVALID`：span 过短 | 2 | 16.7% |
| `JUDGE_RAISED: JudgeOutputUnparseable` | 1 | 8.3% |

3/12 无 verdict = 25%，与历史 4/15 = 26.7% 同量级，说明该 claim 的失败不是一次性抖动。

### 11.2 两个新发现

1. **"span 非逐字"其实是"span 过短"**：两次 `INVALID` 的 span 都是 `"时效"`——它**逐字出现在** claim 原文里（`in_claim=True`），只是只有 2 个字，被 `<4 字` 的可定位性下限拒绝。旧代码把两种情况合并成同一个 `JUDGE_SPAN_NOT_VERBATIM`，归因是错的。已拆开：
   - `<4 字` → `JUDGE_SPAN_TOO_SHORT`
   - 长度够但不在原文 → `JUDGE_SPAN_NOT_VERBATIM`
   - 判定结果不变（仍是 `INVALID_JUDGE_OUTPUT`，不兜底），只是失败原因可区分；`test_short_span_is_rejected` 改断言，34 passed，ruff 全过。
2. **不可解析输出有 live 证据了**：12 次里 1 次 `JudgeOutputUnparseable: invalid JSON`。这证实 §9 的"仅由单测证明"重试路径在真实流量里确实会被触发。注意本探针直接调 `judge.judge`、绕过了 `review()` 的重试，所以这 1 次只证明"触发条件存在"，不证明重试后一定成功。

### 11.3 对判定的影响

- `claim_cf3828` 本身是**边界 claim**（原文含"通常""可能受……限制"），judge 有时接受（2/12）。合并历史 15 次：3/27 判 true（11.1%）。2-of-5 能把这类偶发接受压下去；2-of-3 不行。
- 失败票不会变成 true，也不会变成 false：`claim_cf3828` 若 5 轮里出现 2 次失败，剩余 3 轮仍要给出 2 票 false 才聚合为 `UNSUPPORTED`，否则是 `INSUFFICIENT_EVIDENCE`。这是如实记账，不是静默通过。
- **未做**：没有为了让 `claim_cf3828` 通过而放宽 4 字下限或改写 claim；没有改 prompt；没有接线上。

## 12. 重试边界 live 验证（第 4 项）

§9 的重试只有单测证据，§11 的探针又绕过了 `review()`。本次用故障注入补上这一段。

命令：

```
python dispatch-output/round67-q1-20261023/inject_retry_live.py
```

产物 `retry-injection.out`，sha256 `4C8094CD2382AF8F0BE61CB3F7BCB743784DB47B52CBC6825EFE666C58022CDA`。

| 场景 | 注入 | 期望 | 实测 |
|---|---|---|---|
| S1 | 第 1 次抛 `JudgeOutputUnparseable`，第 2 次交给真实 judge | attempts=2、`REVIEWED` | attempts=2、`REVIEWED`、supported=true |
| S2 | 连续 2 次抛不可解析 | attempts=2、`INVALID_JUDGE_OUTPUT` | attempts=2、`JUDGE_OUTPUT_UNPARSEABLE`、reviews=0 |
| S3 | 第 1 次返回伪造 span（契约违约） | attempts=1、不重试 | attempts=1、`JUDGE_SPAN_NOT_VERBATIM`、reviews=0 |

结论：重试**只发生一次**，且只对"没按 JSON 格式回"生效；契约违约不重试；失败票不会被兜底成 true/false。S1 的第 2 次是真实模型调用（supported=true），说明恢复路径能接回真实 judge。

边界：注入点在 `SupportJudge.judge` 接口层，模拟的是 `LLMSupportJudge` 已抛出的不可解析异常，不是"真实模型这次返回了坏 JSON"；后者在 §11 有过 1 次 live 证据，但没有经过 `review()` 的重试链路。因此本节的结论是"重试逻辑在真实 judge 下按预期执行"，不是"重试后成功率 100%"。

## 13. 难绿样本：多跳与保留意见（第 3 项）

§10 的边界 1 指出"绿样本仍是容易的绿"。本节补 12 条：多跳转述 6 条（条文组合、事实适用、条件式），带保留意见 6 条（未决事实、限制性表述）。文件 `regression-green-hard.json`，判据不变（2-of-5、零误杀）。

命令：

```
python dispatch-output/round67-q1-20261023/run_support_review.py --live --repeat 5 --green \
  --green-file dispatch-output/round67-q1-20261023/regression-green-hard.json \
  --out .../support-review-green-hard-live.out
```

60 次调用，产物 sha256 `30CF6C71E09D4C4E7DA4C682A16B18E4018D1BDEBE796F7A406E6A6D9BE7F4A2`。

### 13.1 读数：9/12 PASS

| case | 真/假/失败 | 聚合 |
|---|---|---|
| salary-82-period | 5/0/0 | SUPPORTED |
| salary-82-two-prongs | 5/0/0 | SUPPORTED |
| salary-14-deemed | 5/0/0 | SUPPORTED |
| salary-82-unknown-caveat | 2/1/2 | **INSUFFICIENT_EVIDENCE** |
| salary-82-fact-apply | 5/0/0 | SUPPORTED |
| salary-14-conditional | 5/0/0 | SUPPORTED |
| guarantee-692-unknown-start | 0/5/0 | **UNSUPPORTED** |
| guarantee-692-no-extension | 5/0/0 | SUPPORTED |
| guarantee-686-method | 2/3/0 | **UNSUPPORTED** |
| guarantee-688-creditor-choice | 4/1/0 | SUPPORTED |
| guarantee-693-precondition | 4/0/1 | SUPPORTED |
| guarantee-period-vs-method | 5/0/0 | SUPPORTED |

60 次里 3 次无 verdict（5%），全部是 `JUDGE_OUTPUT_CONTRACT_VIOLATION`，`attempts=1`——符合"契约违约不重试"。

### 13.2 三条失败逐条归因

1. **`guarantee-692-unknown-start`（0/5 判 false）：出题错误，judge 是对的。**
   证据里第六百九十二条第三款明写"主债务履行期限没有约定或者约定不明确的，保证期间自债权人请求债务人履行债务的宽限期届满之日起计算"。我的 claim 却写"六个月的保证期间尚无法起算"，与条文相反；judge 每次都在 rationale 里指出了这一点。这不是误杀。
2. **`guarantee-686-method`（2/3 判 false）：证据绑定不全，judge 拒收有据。**
   claim 只绑了第六百八十六条，却断言"明确约定连带责任保证的，按连带责任保证承担责任"。686 只列明两种保证方式与"约定不明按一般保证"，"按连带责任保证承担责任"的依据在第六百八十八条。judge 的 rationale 正是"条文未明确规定约定连带责任时的处理规则"。
3. **`salary-82-unknown-caveat`（2/1/2）：唯一真正值得记的样本。**
   后半句"不影响该期间规则本身的适用"是法条外的元陈述：r1/r4 接受，r3 判 false 并给出 span，r2/r5 输出契约违约（无 verdict）。聚合为 `INSUFFICIENT_EVIDENCE`——既没有被误判成 false，也没有被静默算成 true。

### 13.3 修正后复跑：3/3 PASS

只改 claim 文本与证据绑定，不放宽任何判据：692 改为条文的宽限期起算句；686 补绑 688；82 的保留意见句删掉法条外的元陈述。文件 `regression-green-hard-fix2.json`，5 轮 15 次调用，产物 sha256 `17F19BCECBE6A97985F5E69B45334D89CF8E69DEA491DCBA1F3C379E994EC3C5`。

三条全部 5/5 判 true，`GREEN_RESULT: 3/3 PASS`。这反向确认了 §13.2 的归因：失败来自出题，不是 judge 把正确句子判错。

### 13.4 结论与边界

- **干净的误杀仍是 0**：9 条一次通过的难绿样本 + 3 条修正后通过的样本，没有一条在"断言与所绑条文一致"的前提下被聚合为 `UNSUPPORTED`。
- 新教训：**难绿样本必须"断言什么就绑什么条文"**；元陈述（"不影响规则适用"）会引入法条外命题，判据本身无法稳定覆盖。
- 边界：仍只有工资/保证两域，case 级 12 条不足以给出误杀率上界；契约违约率在这批难样本上是 3/60 = 5%，高于容易绿的 0/60，说明输入越靠近条文边界，输出契约越容易坏；这类失败票不会变成 true/false，但会消耗聚合票数。
- 未接线上；线上阻断的前置条件仍未满足。
