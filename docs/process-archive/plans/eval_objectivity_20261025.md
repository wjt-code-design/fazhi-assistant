# 评测客观性加固计划（2026-10-25，自主执行版）

## 背景与目标

昨晚的实测暴露两个问题：

1. **新题库可信度**：30 道题由我（非答题模型）根据库内条文改写，金标由抽样构造确定，
   但「题目是否真的只能由该条文回答」未经独立验证（已发现 3 条多义题并修正）。
2. **faithfulness = 0.310** 被单一 LLM judge 判出，抽查发现被误判为「不忠实」的答案
   实际引用了**真实存在、但未出现在检索上下文里**的条文。judge prompt 把
   「编造不存在的条文」与「引用真实条文但超出上下文」混为一类。

目标：**把主观指标拆成可机械验证的指标**，在不改生产逻辑的前提下，给出可信的现状画像。

## 对抗性审查（否决项）

| 方案 | 结论 | 理由 |
|---|---|---|
| 让 LLM 直接判「法律答案是否正确」 | 否决 | 无权威法源可核，模型自证；且与答题模型同源 |
| 装一个「法律 MCP」来校验条文 | 否决（当前不可行） | 已装插件中无中国法律权威数据源；context7/apifox 均不适用 |
| 改 `main.py` / `retrieval.py` 生产逻辑修 grounding | **否决（本轮）** | 用户不在场无法验收；本轮只做评测与诊断，修复方案只出文档 |
| 用本机 LLM 批量扩 150 题 | 否决 | 生成模型 = 答题模型（qwen3.8-flash），自证偏差最大 |
| 取双 judge 平均值 | 否决 | 平均会掩盖分歧；分歧必须逐条看原文裁定 |
| 只看 faithfulness 单指标 | 否决 | 口径混装，涨跌无法归因 |

## 执行方案（全部离线，不触碰生产代码）

### P1 机械引用核验器

新增 `backend/scripts/citation_check.py`：

- 正则从答案中抽 `《X法》第Y条`（中文数字 → 阿拉伯数字归一）
- 与两套集合做运算：
  - `ctx`：该题 `retrieve(q, k=6)` 命中的 `(source, article)`
  - `db`：`legal_provisions_te4` 全库 10824 个 `(source, article)`
- 产出三个**不依赖 LLM** 的指标：
  - `citation_precision` = 引用中落在 ctx 的比例
  - `grounding_leak_rate` = 引用真实存在但不在 ctx 的比例
  - `citation_hallucination_rate` = 引用在库中也不存在的比例
  - `citation_recall` = ctx 条文被答案引用的比例

### P2 judge 口径拆分

`backend/scripts/_judge.py` 新增 `grounding_verdict()`（不改动旧 `faithful()`，
保证历史结果可比）：

- `faithful`：全部主张可由 ctx 支持
- `extrapolated`：引用了真实条文但不在 ctx
- `fabricated`：引用了库中不存在的条文/数字

### P3 重跑与对比

1. `eval_set_gen_v1.json`（29 题）：机械指标 + 拆分后 judge
2. `eval_set.json`（28 题基线）：机械指标，用于对照
3. 落盘 `docs/benchmark_results/`，产出 `summary_<ts>.md`

### P4 题库扩充（视执行时间）

按同一规则人工补 30 题（总计 59），仍从条文池取样、去词化、机械校验；
**不使用本机 LLM 生成**。

## 验收标准

- 每个指标都能追溯到具体条号集合运算，可复现
- 拆分后 `fabricated` 与 `extrapolated` 分别有数，不再混为「幻觉」
- 生产代码零改动（`git status` 只应有新增评测脚本与数据文件）

## 红线

- 不 commit、不改 `.env`、不改 `main.py` / `retrieval.py` / prompts
- 任何结论必须附样本量与口径，禁止把估算当实测

## 执行结果（2026-10-25 完成）

| 计划项 | 状态 | 产出 |
|---|---|---|
| P1 机械引用核验器 | 完成 | `backend/scripts/citation_check.py` |
| P2 judge 口径拆分 | 完成 | `_judge.py` 新增 `grounding_verdict()`，旧 `faithful()` 保留 |
| P3 重跑与对比 | 完成 | 59 / 29 / 旧 28 三套题库结果均已落盘 |
| P4 题库扩充 | 完成（59 题库，超出原定 30） | `data/eval_set_gen_all.json` |

验收标准逐条核对：

- [x] 每个指标可追溯到条号集合运算（`citation_check.py` 输出含 `cited / in_ctx / leak / fabricated / ctx`）
- [x] `fabricated` 与 `extrapolated` 分别有数：59 题为 `0 / 94`，旧口径混装问题已拆开
- [x] 本轮未改动生产链路：新增文件仅 `backend/scripts/citation_check.py`、
  `eval_pool_sample.py` 与 `data/` 下题库；`_judge.py` 只追加 `grounding_verdict()`
  （旧 `faithful()` 保留以保历史可比）。工作区中 `main.py` / `retrieval.py` 的
  modified 状态来自更早的网关改造，非本轮产生
- [x] 结论均附样本量与口径（见 `docs/benchmark_results/summary_20261025.md`）

关键数字（详见 summary）：

- 59 题：precision 0.607 / leak 0.393 / hallucination **0.000** / recall 0.246
- 检索 59 题：recall@4 0.848、source@4 0.966、MRR@6 0.770
- 新发现缺陷：4/59（6.8%）口语化问题被 clarify 误拒（id 101/109/152/158）

执行中修正的测量缺陷：引用解析器两次（跨书名号误归属 8 条假幻觉、嵌套书名号 1 条假幻觉），
修正后 59 题 fabricated 归零。题库侧修正 3 处标注歧义。

**未做**（按对抗性审查否决项）：未改动生产 grounding 逻辑、未引入外部法律 MCP、
未用本机 LLM 批量生成题目、未 commit。

## 后续执行（2026-10-25 白天，承接用户「继续」指令）

- [x] **修 clarify 误拒（P0 前半）**：`clarify.py` `_UNDERSPEC_RE` 移除过宽的
  「怎么办 / 怎么处理」结尾信号；指代词组分词改为必须出现动词，避免「这种情况」误判。
  新增回归单测，`backend/tests/test_clarify.py` **25 passed**。
- [x] **生成第三方法律事实核实包**：`docs/process-archive/reviews/legal_fact_review_20261025.md`，
  含 18 题金标有效性 + 5 题答案合规性，附条文原文与回传格式。
- [x] 第三方回传已处理（2026-10-25）：回执 `docs/process-archive/reviews/legal_fact_review_20261025_receipt.md`
  —— 18 题金标充分；110/154 补条文并已更新题库；113 款项定位错误入
  `docs/process-archive/plans/grounding_fix_list_20261025.md`；对外集 `data/eval_external_v1.json` 已建立（20 题）。
- [x] grounding G2 引用标注（2026-10-25）：后端 `citation_grounding_status` + 前端
  「检索依据 / 补充依据 / 未收录」三组；后端单测 4 passed、前端 91 tests 全绿，真实 API 验收通过。
- [x] grounding G1 决策（2026-10-25）：**不接生产**；保留参考实现与 12 项单测，
  作为评测链路回归守卫。G3/G4 见修复清单。

### Track 1 已完成（不需要拍板、零用户可见影响）

- [x] **题库分轨方案**：`docs/process-archive/plans/eval_tracks_20261025.md`
  —— 单库 + `track`（regression / external）+ 金标来源字段；回归集管门禁、对外集管汇报，
  冲突以回归集为准。146 条题记录已补字段，两个 runner 支持 `EVAL_TRACK`。
- [x] **grounding 影子模拟**：`docs/benchmark_results/grounding_shadow_20261025.md`
  —— 白名单会拦 94/239（39.3%）引用，影响 39/59 个答案；**没有任何答案会被拦到零引用**。
  被拦引用是否法律上正确，仍需第三方判断。
- [x] **回归门槛检查器**：`backend/scripts/check_regression.py`
  —— 默认只报告，`--strict` 才阻断；已用 59 题两份结果验证（leak 项 FAIL 属预期）。
- [x] **查询改写原型**：`backend/scripts/proto_query_rewrite.py`
  —— 5 个失败样例首轮救回 3 题（101/113/117）；全量 59 题 recall@4 由 0.8475 → 0.8814
  （修 6 破 4）。但复测出现改写词漂移，同一题结果不一致 → **结论：暂不接入生产**，
  详见 `docs/benchmark_results/query_rewrite_20261025.md`。
- [x] **clarify 端到端复验**：单测 25 项通过；已重启后端加载修复，4 题（101/109/152/158）
  全部正常作答并给出引用（25 处，fabricated=0），不再命中澄清模板。
- [x] **G1/G2 单测 + 影子对比**：`backend/tests/test_citation_subdivision.py` 12 passed；
  `docs/benchmark_results/subdivision_shadow_20261025.md` 重放 59 题，69 处款项级引用
  valid 68 / invalid 1（113），与第三方复核独立一致；未接生产。
