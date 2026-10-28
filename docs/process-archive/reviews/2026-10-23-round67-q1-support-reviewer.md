# Q1 方案 B 落地报告：离线支持审查器（evaluation-only）

日期：2026-10-23。性质：新增离线评测模块 + 契约测试 + 真实模型读数；**不改线上路径、不提交、不推送、不部署**。
输入仍是第六、七轮冻结工资样本（路径与 sha 见 [上一份复核](file:///c:/Users/33393/Desktop/ai-legal-helper/docs/process-archive/reviews/2026-10-23-round67-q1-support-gap-review.md)）。

## 0. 结论

方案 B 已实现并取得**可复现的红/绿/稳定性读数**，但**Q1 仍未关闭**：

| 判据 | 结果 | 证据 |
|---|---|---|
| 确定性契约（伪造 span / 自相矛盾 / 输入越界） | 满足：18 个用例全过，删掉逐字校验后 3 个用例立刻转红 | §3 |
| 红对照：四类缺口被判 `supported=false` | 满足：6 条缺口 claim 在成功产出结论的轮次里全部命中，span 逐字回到原文 | §4.2 |
| 绿对照：逐字引条文的正常句不误杀 | 满足：live 3/3 `supported=true` | §4.3 |
| 稳定性 | **不满足**：同一 claim 在 3 次调用中出现 1 次翻转；另有 1 次 JSON 解析失败、1 次 span 非逐字 | §4.4 |

→ 当前形态**只能进评测，不得接线上阻断**。稳定性缺口意味着"单次判定"不可作为发布门禁，若将来要用，至少需要多次投票/阈值与失败率的明确口径——那是另一次决策，本轮未做。

## 1. 边界（做了什么、刻意没做什么）

做：
- 逐 claim 调用一次模型，输入**证据封闭**：claim 原文 + 它绑定的证据（`source_ref`/`snippet`）+ 它绑定的已确认事实 + 该争点未决事实。不含问题、全量 state、其他争点证据。
- 输出 `{claim_id, supported, unsupported_spans, rationale}`；span 由本模块**确定性校验**必须是 claim 原文的连续子串（NFKC + 空白折叠归一，≥4 字）。
- `JUDGE_FAILURE` / `INVALID_JUDGE_OUTPUT` 与 `REVIEWED` 严格区分；模型异常或输出违约**不兜底成 supported=false**。

没做：
- 不接入 `agent/service.py` / `agent/runtime.py` / `main.py`（有测试钉住，见 §3.3）。
- 没新增 writer/verifier 开关，没改 prompt，没改冻结物。
- 没把 verdict 写入任何线上状态或阻断信号。

放置位置：`backend/scripts/support_review.py`。理由：`recompute_boundary_manifests.py` 的 `prompt-bundle` 边界 = `backend/agent/**` + `backend/prompts.py`；离线评测器不应改变发布边界哈希。

## 2. 实现契约

文件：[support_review.py](file:///c:/Users/33393/Desktop/ai-legal-helper/backend/scripts/support_review.py)

- `build_requests(state, draft)`：复用 `build_writer_payload` 的白名单视图（与 writer/verifier 同一真源），并校验：
  - `claim_id == derive_claim_id(issue_id, text, evidence_ids, fact_ids)`；
  - 证据/事实必须属于该争点且在白名单内。
  - 输入不满足 → `SupportReviewInputError`，错误码 `UNKNOWN_ISSUE_ID` / `CLAIM_ID_MISMATCH` / `EVIDENCE_NOT_BOUND` / `FACT_NOT_BOUND` / `STATE_INTEGRITY_FAILURE`。**这不是审查结论**。
- `review(requests, judge)`：逐 claim 调用；异常 → `JUDGE_FAILURE`；输出违约 → `INVALID_JUDGE_OUTPUT` 并保留已通过的逐 claim 记录。
- 模型输出复核错误码：`JUDGE_OUTPUT_CONTRACT_VIOLATION`、`JUDGE_SPANS_WITH_SUPPORTED_TRUE`、`JUDGE_SPANS_MISSING`、`JUDGE_SPAN_NOT_VERBATIM`。

## 3. 确定性验证（新鲜运行）

### 3.1 测试

命令（工作目录 `backend/`）：

```
python -m pytest tests/test_agent_support_review.py -q
```

读数：`18 passed`。覆盖：绿、红、伪造 span、过短 span、`supported=true` 带 span、`supported=false` 无 span、`claim_id` 串号、`supported` 非 bool、judge 抛异常、证据封闭、越界证据、越界事实、claim_id 篡改、未知争点、首个违约即停、线上路径未被引用。

### 3.2 一红一绿控制（防止"测试恒绿"）

把 `_validate_verdict` 的逐字校验临时改为 `if False and (...)`，只跑三个依赖它的用例：

- `test_forged_span_is_rejected_not_trusted`
- `test_short_span_is_rejected`
- `test_review_stops_at_first_invalid_output`

读数：`3 failed, 15 deselected`——三个用例都从"通过"变成"失败"（伪造 span 被当成 `REVIEWED`）。已还原，还原后 18 passed。说明这些断言确实在钉行为，不是装饰。

### 3.3 离线约束

- `ruff check scripts/support_review.py tests/test_agent_support_review.py` → `All checks passed!`
- 全仓搜索（排除 `backend/scripts/**`）`support_review` 只命中测试文件本身；`agent/service.py`、`agent/runtime.py`、`main.py` 零引用，并有参数化测试逐文件断言。

## 4. 真实模型读数（JUDGE 文本档，temperature=0）

### 4.1 复现命令

```
python dispatch-output/round67-q1-20261023/run_support_review.py            # 只构造请求，0 模型调用
python dispatch-output/round67-q1-20261023/run_support_review.py --live --repeat 2
python dispatch-output/round67-q1-20261023/inspect_support_review_raw.py    # 保留 raw 输出 + 单轮红对照
python dispatch-output/round67-q1-20261023/inspect_support_review_raw.py --green-only --green-repeat 3
```

产物：`support-review.out`（dry run）、`support-review-live.out`（2 轮）、`support-review-raw.out`（单轮 raw）、`support-review-green.out`（绿对照）。

### 4.2 红对照：缺口句命中

`support-review-live.out` 里成功产出结论的 8 个 verdict **全部 `supported=false`**，span 均能在 claim 原文中找到：

| claim | 缺口类别 | 判定 | span（节选） |
|---|---|---|---|
| `claim_cf3828` | 未签期间起止 / 时效 | false | `劳动者通常可就未订立书面劳动合同期间主张二倍工资差额` |
| `claim_1075` | 时效 / 计算基数 | false | `且未超过时效`（raw 轮另含 `以劳动者月工资标准为基数`） |
| `claim_b8fcb2` | 满一年后终止/上限 | false | `二倍工资差额的可主张期间通常以一年节点为界` |
| `claim_9a5413` | 仲裁时效 | false | `仲裁时效可能对可主张期间产生影响` |
| `claim_3fa72` | 计算基数 / 时效起算 | false（2/3 次） | `计算基数通常按劳动者每月工资标准确定` |
| `claim_d0510` | 满一年后终止/上限 | false | `满一年之后通常不再支持二倍工资差额` |

四类缺口（仲裁时效、满一年后终止/上限、计算基数、未签期间起止）在成功判定里**全覆盖**。

### 4.3 绿对照：逐字引条文不误杀

`support-review-green.out`：claim 逐字复述第八十二条第一句并绑定同一证据，**3/3 `supported=true`，spans 为空**。

> 控制样本的一次构造错误也已记录：最初把该 claim 绑到第十四条证据上，judge 判 false 并说明"绑定条文为第十四条，未规定二倍工资"。这不是误杀，而是审查器**以绑定证据为准、不信 claim 自己引的条号**的正向证据。已改为按条号匹配绑定证据后重跑，得到上述 3/3。

### 4.4 稳定性（本轮最重要的负面读数）

同一批请求共调用 18 次（live 2 轮 9 次 + raw 单轮 6 次 + 绿 3 次）：

| claim | 结果序列 | 结论 |
|---|---|---|
| `claim_cf3828` | false / false / **输出违约** | 1 次 span 非逐字（`JUDGE_SPAN_NOT_VERBATIM`） |
| `claim_3fa72` | false / false / **true** | 1/3 翻转成 supported=true ⇒ 单次判定会漏掉计算基数+时效缺口 |
| `claim_d0510` | false / false / **JSON 解析失败** | 模型输出不是合法 JSON（`Expecting ',' delimiter`） |
| 其余 3 条 | 全部 false | 2–3 次一致 |

失败率读数（按调用计）：18 次调用中 1 次输出违约、1 次 JSON 失败 ⇒ 约 **11%** 的调用拿不到可用结论；按 claim 计，`claim_3fa72` 有 **1/3** 概率漏判。

这些失败**没有**被兜底成 `supported=false`：要么是 `INVALID_JUDGE_OUTPUT`，要么是 `JUDGE_FAILURE`，在读数里可区分。这是设计目标，但也意味着当前形态的置信度不足以支撑阻断。

另有一个已修复的工程问题：第一次 live 运行 12 次全部 `JUDGE_FAILURE`。根因是 runner 在 import `settings` / `llm_registry` **之后**才 `load_dotenv`，judge 带着空 key 构造。把 `load_dotenv` 移到 import 之前后恢复（单请求实测 31 秒/次）。该细节已写进 runner 注释，避免下次静默复现。

## 5. 诚实边界

1. **Q1 未关闭**：B 只提供"离线可测量"的能力，线上 verifier 的行为逐字未变；两份冻结 draft 仍会被线上判 PASS。
2. **判定不稳定**：见 §4.4。当前证据只能说明"多数调用能命中缺口"，不能说明"每次都能命中"。
3. **成本与时延**：逐 claim 一次调用，单次约 31 秒（本机实测）；一份 6 claim 的答案约 3 分钟。不进线上，故不影响用户时延；但全量评测要按这个量级估预算。
4. **判据仍是模型判断**：逐字 span 只保证"定位可审计"，不保证"判定正确"。模型可能给出逐字但错误的 span，或漏判（`claim_3fa72` 已实证）。
5. **未做多次投票/阈值**：`--repeat` 只做读数，不产生聚合结论；任何"多少次判 false 才算 false"的门槛都未定义。

## 6. 建议的下一步（未执行）

- 若要继续收敛 Q1：先把 `claim_3fa72` 这类翻转样本做成固定回归集，规定"k 次中 ≥m 次判 false"的聚合口径，再谈是否进评测门禁。
- 若只是评测使用：按现状接入评测脚本即可，读数里必须同时报告 `JUDGE_FAILURE` / `INVALID_JUDGE_OUTPUT` 比例，禁止只报 `REVIEWED` 的通过率。

## 7. 本轮改动清单（全部未提交）

- 新增 `backend/scripts/support_review.py`
- 新增 `backend/tests/test_agent_support_review.py`
- 新增 `dispatch-output/round67-q1-20261023/run_support_review.py`、`inspect_support_review_raw.py`
- 新增产物 `support-review.out`、`support-review-live.out`、`support-review-raw.out`、`support-review-green.out`
- 本报告
