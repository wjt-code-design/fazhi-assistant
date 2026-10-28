# 修复执行报告：法条覆盖、引用核验与输出卫生（2026-10-27）

> **状态：执行前基线。** 本报告记录问题定位、修复方案与验收标准，**不声称任何生产代码已修改**；每项完成后在 §七「执行记录」追加提交号与验证读数，未验证不写"已修复"。
>
> 触发事件：2026-10-27 故意伤害/教唆犯样例答案审计（张三欠债、李四教唆王五殴打致一级伤残）。
> 关联材料：`docs/process-archive/plans/grounding_fix_list_20261025.md`（G1–G4）、`docs/process-archive/reviews/legal_fact_review_20261025_receipt.md`、`docs/benchmark_results/citation_gen59_20261025b.json`。
>
> **现状核对（2026-10-27 16:58）**：事实以 `HEAD 3102200`（2026-10-27 14:44）为准；`backend/` 源码相对 HEAD 无未提交改动（工作区仅 `dispatch-output/…` 一处 modified，另有未跟踪测试/脚本）。行号随 HEAD 变化，实施前请以当次 `git rev-parse HEAD` 复核。已核对并纳入本报告的现行机制：`output_normalize.py`、`quality.py`、`gate_exit_registry.py`（E19/E20）、`prompts.py:46–54`、`agent/runtime._uncovered_fact_clauses`。

---

## 一、事故摘要

| 项 | 内容 |
|---|---|
| 问题 | 张三欠李四十万元不还，李四教唆王五把张三打致一级伤残，如何定罪？ |
| 答案结论 | 李四与王五均构成故意伤害罪（致人重伤），共同犯罪，李四为教唆犯 |
| 审计判定 | **结论方向正确，依据基本错**：核心分则条文（刑法第234条）与教唆犯条文（第29条）缺失，改用第2、13、14条"推导"罪名，并错误援引第289条作为"间接指引" |
| 事故类型 | A 核心条文缺失仍强行作答；B 错引第289条（条文存在但不对题）；C 伤残等级当伤情等级；D 内部话术泄漏与结论卡自相矛盾 |

### 1.1 问题清单（审计结论）

**实体法层**

1. 以总则第2、13、14条替代分则定罪，违反罪刑法定（第3条）；
2. 错误援引第289条（聚众"打砸抢"特别规定），实质是类推；
3. "一级伤残属于重伤范畴"混淆伤残等级（《人体损伤致残程度分级》）与伤情等级（《人体损伤程度鉴定标准》）；
4. 未引第29条、第25条、第26/27条，教唆犯依据缺失、主从犯未认定；
5. 第234条第二款两档量刑未落地（未分析"特别残忍手段+严重残疾"要件）；
6. 民事引用不精确（债务属借款合同，第1165条为侵权一般条款；刑诉法第55条与定罪无关）；
7. 未引第95条重伤定义。

**答案工程层**

8. 内部指令泄漏（"题目要求严格依据提供条文"）；
9. 过程话术进入正文（"存在引用缺失风险""未在提供条文中""补充依据（未在本次检索范围内…）"）；
10. 结论卡不"结论"，结论与自我怀疑混排；
11. 检索缺口未补救，未拒答；
12. 逻辑自相矛盾（"依据第234条"与"未列出234条全文"并存）；
13. 论述跑题（民事性质、证据标准占比过高）；
14. 罪名表述不严谨（"故意伤害罪（致人重伤）"——重伤是量刑情节）。

---

## 二、根因分层（与现有机制对照）

| 层 | 根因 | 现有机制（截至 HEAD 3102200） | 缺口 |
|---|---|---|---|
| 检索层 | 第234、29条未召回 | `retrieval.py` 常规 top-k 检索；`exact_article_lookup`（`:560`）可定向取条（`main.py:138` 导入） | 无"**法条**覆盖"检查，缺失时无补检/拒答分支（注意：`agent/runtime._uncovered_fact_clauses` 是**事实**覆盖，不是法条覆盖，勿混） |
| 核验层 | 289条被错误当作依据 | 存在性三层已齐：`citation_verify`（`:948`）、`classify_citation`（`:970`）、`citation_grounding_status`（`:917`）；`quality.py` 回答自检（引用存在性/诚实拒答/含糊话），其 docstring 自述"**引在库≠引对条文**，靠 full 门禁+人工兜底" | 三层都只判"条文是否存在、是否在上下文/是否为空话"，不判"条文内容是否支持该断言"——289 属真实条文，故未被拦 |
| 输出层 | 内部话术、结论矛盾 | `output_normalize.py` 已做确定性输出归一（`strip_unprovided_notes` 删"未检索到/建议核对原文"矛盾句）；`prompts.py:46–54` 已有禁用表述清单与"条号只能取自上方检索条文"规则；`gate_exit_registry.py` 登记全部用户可见出口（`scan_content_yields` 唯一判定），E19/E20 已把库外法源/已废止法披露改为代码注入 | 禁用清单未覆盖"提供条文/未在提供/检索范围/补充依据/题目要求/本次检索"等变体；无后置过滤；结论与限定语无一致性校验 |
| 领域层 | 伤残等级当伤情等级 | 无 | 无要件/鉴定标准校验表 |
| 模型层 | — | 结论方向正确 | 非本次瓶颈（换模型/微调均不解决 A、D 类） |

**与既有 grounding 清单的关系**：G1（款项解析）保持离线回归守卫、不接生产；G2（标注而非拦截）已实施；G3/G4 维持原计划。本报告 **F5 与 G2 口径一致**——外部引用不删、不硬拦，只新增"未支撑"标注。

---

## 三、修复项

### P0（1–3 天量级，先做）

**F1 法条覆盖闸门**

- 目标：核心条文缺失时不得"推导"作答。
- 实现：新增 `backend/knowledge_base/required_articles.json`（首版 16 个高频罪名/制度，与 F6 同一批思路）；新增 `backend/coverage_gate.py`（纯函数 + 注入式 lookup，不 import retrieval），生成前检查 sources 覆盖度；缺失→用现有 `exact_article_lookup`（`retrieval.py:560`，按法名+条号、含时效过滤）逐条定向补检，**补检上限 8 次调用、超限条目计入缺口、补齐即结束**→仍缺→拒答或输出"无法完整回答"并标注缺口；接入点 `request_bootstrap.prepare_fast_path`（legal_query 且非考试），开关 `settings.coverage_gate_mode`（off/warn/enforce，默认 off）。
- 验收：构造"上下文缺 234"的回归用例，必须补检或拒答；答案中不得出现总则推导定罪。
- 风险：清单不全导致误拒——生产默认只告警，`enforce` 仅用于回放验收；清单版本化可配置。
- 状态：**已实现（2026-10-27）**——`coverage_gate.py` + `required_articles.json`（15 主题）+ `prepare_fast_path` 接入；默认 off，回放用 enforce。

**F2 提示词边界（给"尽力分析"加例外）**

- 目标：核心条文缺失时不得用总则"推导"定罪。
- 根因（现状核对）：`prompts.py:46–48` 明确要求"上方条文未涵盖……应基于上方条文中最相关的法律**尽力分析并回答**"——这是本次缺 234 仍作答的直接诱因；`:49–51` 的禁用表述清单未覆盖"提供条文/未在提供/检索范围/补充依据/题目要求/本次检索"等变体（事故答案恰好用了这些变体，绕过清单）；`:53–54` 虽规定"未在上方条文出现的法规不写其具体条号"，但无对应校验。
- 实现：为"尽力分析"加**定罪类例外**——"刑事定罪问题若分则条文缺失，不得以总则条文替代分则定罪，应说明缺失并给出条件性分析"；同步扩展 `:49–51` 禁用清单的变体；`:53–54` 保持不变，交由 F8 校验。
- 验收：事故答案回放，不再出现"推导定性"与绕过清单的话术。
- 说明：prompt 层"核对适用前提与所支持的具体结论"已存在（`tests/test_answer_quality_prompt_round7.py`），但 289 事故证明 prompt 约束不足，必须由 F5 语义核验兜底。
- 状态：**已实现（2026-10-27）**——`prompts.py` 第 9 条加"刑事定罪问题除外"、第 12 条新增定罪边界；禁用清单补"提供条文/检索范围/补充依据/题目要求/本次检索"。

**F3 输出卫生（扩展现有归一模块，不新建第二份规则）**

- 目标：用户侧不见内部流程语言；结论与过程说明分离。
- 实现：在 `output_normalize.py` 新增 `strip_internal_notes()`（复用该模块"确定性纯函数、零 LLM"范式与现有 `strip_unprovided_notes` 的写法，**不新建 `output_guard.py`**——该模块 docstring 明确"不写第二份规则"）；黑名单覆盖：提供条文/检索范围/未在提供/补充依据/需提供原文/本次检索/题目要求/引用缺失风险/未直接列出。**不新增出口/E 码**：本过滤与 `money_normalize` 同属内容前置归一，挂在既有出口（E7/E9/post/agent 终稿）之前；`gate_exit_registry.py` 顶部注释说明该豁免（未来新增出口仍按 §2 B1 登记）。过程原文只入日志（`kind=internal_notes`），不下发。
- 验收：事故答案回放，泄漏短语命中 0；`test_gate_exit_registry.py` 哨兵绿。
- 状态：**已实现（2026-10-27）**——`output_normalize.strip_internal_notes` / `has_internal_notes`；接入三处：agent 终稿归一链、`_post` 落库前、非流式兜底下发前；流式帧已发出不可回收，改为"检测→日志→拦缓存"。

**F4 结论一致性检查**

- 目标：结论与限定语不得互相矛盾。
- 实现：结论字段唯一；检测"依据 X 条"与"X 条未提供/缺失"类矛盾（条号归一为整数、否定句按相邻句窗口）；命中→**留痕**（warning）。自动改写/降级为待 Owner 决策项，不在本批强行实现（避免误伤正确结论）。
- 验收：事故答案回放，矛盾检测必须命中。
- 状态：**已实现（2026-10-27，检测 + 留痕）**——`output_normalize.detect_conclusion_contradiction`（跨句/中文-阿拉伯混写可判），`_post` 命中即 warning；不改写正文。

### P1（1–2 周）

**F5 claim 级引用核验**

- 目标：从"引用是否存在"升级为"条文是否支持该断言"，补上 `quality.py` 自述的"引在库≠引对条文"语义缺口。
- 实现：**新增** `retrieval.claim_support_check`（**不改 `citation_verify` 的既有契约**——其现有调用点 `main.py:2451/2715` 依赖"返回库外引用列表"的语义）：以句子/分句为 claim 单元→定位其所引条文原文（`exact_article_lookup`）→NLI/LLM judge 判支持→输出未支撑清单；与 G2 一致：外部引用不删不拦，只加"未支撑"标注；与 **E19/E20** 的单一提示原则协调（同一部法只说一次，不得与"全文没有/第X条没有"并存），新提示走 `gate_exit_registry` 新 E 码；G1 款项校验保持离线。
- 验收：289 条必须被标"未支撑"；59 题跑 citation precision 基线（存量 250 处引用、条级去重）。
- 参考：ALCE（citation precision/recall）、FActScore/VeriScore、DeBERTa-NLI/HHEM。

**F6 法律要件表**

- 目标：领域概念错可被确定性拦截。
- 实现：新增 `backend/knowledge_base/legal_elements.json`（先做 10–20 个高频罪名：构成要件/必备法条/鉴定标准/量刑档）；生成后校验，伤害类必须包含"伤情鉴定"前提，明确"伤残等级≠伤情等级"。
- 验收："一级伤残"题必须输出"需伤情鉴定"，不得直接等同重伤。

**F7 共同犯罪/教唆犯模板**

- 目标：教唆、共同犯罪、主从犯类问题不缺条、不漏认定。
- 实现：意图识别命中"教唆/共同/主从犯"→强制召回第25/26/27/29条；答案模板必须含主从犯认定与作用分析。
- 验收：本题回放，主从犯+法条齐全。

**F8 分则绑定校验**

- 目标：定罪结论必须绑定分则条号。
- 实现：规则校验——定罪类结论须出现分则条号；总则（第2/13/14条）不得单独作为定罪依据。
- 验收：规则命中，写入回归用例。

### P2（2–4 周）

**F9 评测扩充**

- 新增三类用例：该拒答（上下文缺核心条文）、引用错配（条文真实但不对题）、领域概念错（伤残/伤情、轻伤/重伤、定金/订金）；接入 RAGAS/DeepEval 指标（faithfulness、citation precision/recall、abstention quality）；与 `docs/process-archive/plans/eval_tracks_20261025.md`、`eval_objectivity_20261025.md` 口径对齐，外部集与回归集分开。

**F10 小模型微调（已取消：Owner 2026-10-27 决定"不动模型"）**

- 不微调任何模型（含主生成模型、query 改写器、reranker），也不换主模型。
- 原由微调承接的收益，改由 F5（claim 级核验）、F6（要件表）、F8（分则绑定）与 F9（评测扩充）的确定性手段承接。

---

## 四、执行顺序与里程碑

| 里程碑 | 范围 | 出口条件 |
|---|---|---|
| M1（1–3 天） | F1–F4 | 4 条事故回放全部通过；现有 `pytest -m 'not slow'`、ruff、mypy 无退化 |
| M2（1–2 周） | F5–F8 | 289 被标"未支撑"；伤残题改对；59 题 citation precision 基线不降 |
| M3（2–4 周） | F9（F10 已取消） | 三类新用例入评测并可复现 |

依赖关系：F5 依赖 F1 的条文定位能力；F6/F7 可并行；F9 依赖 F1–F8 的开关可配置。

---

## 五、验证方案

1. **事故回放（4 条，硬门槛）**
   - A：上下文缺第234条 → 必须补检或拒答；
   - B：答案引用第289条 → 必须标"未支撑"；
   - C："一级伤残" → 必须输出"需伤情鉴定"；
   - D：输出不得含内部话术，结论与限定语不得矛盾。
2. **回归**：`pytest -m 'not slow'`、ruff、mypy；专项：`tests/test_gate_exit_registry.py`（出口×闸门哨兵）、`tests/test_answer_quality_prompt_round7.py`（prompt 合同）、`tests/test_citation_subdivision.py`（G1 离线守卫）；59 题引用基线（条级去重 250 处）对比；前端涉及时 `tsc --noEmit` + `vitest`。
3. **指标**：覆盖闸门命中率/误拒率、未支撑 claim 率、泄漏短语命中数、拒答正确率、citation precision/recall。
4. **灰度**：每项独立开关，默认关闭 → 影子/告警 → 抽样 → 全量；任何"已修复"声明必须附测试读数与提交号。

---

## 六、风险、回退与不做事项

**风险与回退**

- 覆盖清单不全→误拒：生产第一阶段默认只告警（`enforce` 开关仅用于回放验收），清单版本化可配置；
- 后置过滤误杀：白名单+命中日志，可单条回放；
- claim 核验成本：先离线抽样，暂不进入在线主链路；
- 每项独立开关，出问题单点回退，不影响其他修复。

**明确不做**

- 不换主模型（先修管线，错误类型仍集中于模型推理时再议）；
- 不微调任何模型、不换主模型（Owner 2026-10-27 决定"不动模型"）；
- 不引入 LangChain/LangGraph 全家桶（自研管线+现有门禁已足够）；
- 不扩大"越界引用"拦截（与 G2 已确认口径冲突）。

---

## 七、执行记录

**2026-10-27 第一批（P0：F1–F4）**

| 项 | 变更文件 | 验证读数 | 状态 |
|---|---|---|---|
| F1 | 新增 `backend/coverage_gate.py`、`backend/knowledge_base/required_articles.json`；改 `backend/request_bootstrap.py`、`backend/settings.py` | 单测 11 passed；事故回放：命中 2 主题 / 6 条必备条文，补检 6/6，unresolved 0；全缺失分支缺口提示非空 | 已实现（**2026-10-27 生产开 warn**） |
| F2 | 改 `backend/prompts.py` | prompt 合同测试 3 passed | 已实现 |
| F3 | 改 `backend/output_normalize.py`；`backend/main.py` 四处接入（agent 终稿 / `_post` 落库 / E7 轻量缓冲 / E9 非流式兜底）+ 两处缓存闸 | 单测 5 passed；事故回放残留元语言 0；E7/E9/post 命中均留痕（kind/detail） | 已实现（缓冲路径确定性删除；流式路径检测 + 日志 + 拦缓存） |
| F4 | 改 `backend/output_normalize.py`；`backend/main.py`（E7/E9/agent 加提示 + 3 处缓存闸 + `_post` 拦沉淀） | 单测 6 + 端点 2 + 沉淀 2 passed；事故答案命中 234；59 题存量 0 触发、20 条构造句 0 误报 | 已实现（提示 + 拦缓存/沉淀；流式只拦不提示） |
| F5 | 新增 `backend/claim_support.py`；离线 harness `dispatch-output/claim-support-eval-20261027/` | 6 单测；385 对全量 judge（375 判定 / 10 错误）：**pair 级支撑率 56.8%**；30 对 AI 复核：一致率 0.70、过严 8/15、过松 1/15；**56.8% 为下界** | 已实现（离线评测；在线仅标注待接） |
| F6–F9 | — | — | 未开始（F10 已取消） |

**华宇元典核实（2026-10-27，`dispatch-output/yuandian-verify-20261027/report.md`）**：抽样 20 条引用（跨 15 部法）**20/20 命中、20/20 现行有效、正文与库内一致**；版本敏感条文（治安2025修订、仲裁2025修订、未保2024修正、行政复议2023修订、刑法2023修正）均核对为现行。召回：**金标召回@10（当次检索）= 18/20（90%）**；历史 ctx 口径 15/20 已过时、不可作现状读数；当前未召回为 101（民法典658，赠与）、112（宪法12）。

**F1 评测批（2026-10-27，阶段 0）**：v2 清单（16 主题）下，主集 70 题触发 2 题（2.9%）、缺失 5 / 补入 5（**命中率 100%**）、未取得 0；探针 64 条（16 主题 × 2 正 + 2 负）**召回 1.00 / 特异度 1.00 / 误触发 0**。首轮 15 主题版曾暴露"行政复议宽主题"误触发（1/3），已通过收紧触发器、`exclude`、交通主题拆分修复。结论：**达到开 warn 门槛，建议预发观察 1–2 周**。详见 `dispatch-output/coverage-gate-eval-20261027/report.md`。

**生产开启（2026-10-27 19:50）**：`COVERAGE_GATE_MODE=warn` 写入根 `.env` / `backend/.env`，compose 增加显式透传；`docker compose up -d --build backend` 重建镜像后，容器内核对 `coverage_gate_mode = warn`、`MAX_LOOKUP = 8`、`load_catalog()` 16 主题，`/api/health` 200、启动日志无错误。**部署中发现重建前容器为旧镜像（不含本批代码），已在本轮重建修正。** 预登记见 `docs/process-archive/preregistration-coverage-gate-warn-20261027.md`。

**代码审查复核修正（2026-10-27 20:10，code-review 两轴 + systematic-debugging）**

- **R1 未知 mode 不再 500**：`ensure_coverage` 归一大小写/空格，枚举外值退化为 `off` + warning（日志字段 `kind=coverage_gate_mode`）；新增 2 用例（`WARN` 归一、`loud` 退化）。
- **R2 F4 跨句/混写可判**：条号统一归一为整数，否定句按相邻句窗口取条号；新增 2 用例（先红后绿，跨句与"第二百三十四条/234条"混写）。
- **R2' F4 误报收紧（并行分析发现）**：`根据《民法典》第584条，可得利益损失未包含精神损害` 曾被误判矛盾；改为"否定只在同小句取条号，仅代词（该条/本条）才回看依据句"，新增正常否定与代词指代 2 用例。
- **R3 F3 补 E7 轻量缓冲路径**：下发前 `strip_internal_notes`，命中即 warning（E7/E9/post 三处留痕）；此前该路径原样 yield。
- **R4 18/20 可复算**：新增 `live_gold_recall.py` + `live_gold_recall.jsonl`（逐题证据），`local_metrics.json` 并列"当次检索 18/20 / 历史 ctx 15/20"。
- **R5 prepared 形状保持不变**：移除无消费方的 `coverage_report` 键（诊断只走日志）；`tests/conftest.py` 无条件固定 `COVERAGE_GATE_MODE=off` 作为测试隔离。修复首轮全量 2 failed（`test_request_bootstrap` 的 legacy-keys 断言）。
- **watch-it-fail（本轮）**：R1/R2 的 3 个用例先红后绿（unknown-mode、跨句矛盾、中文-阿拉伯混写）；F1/F2/F3 的历史用例仍未逐条做变异回放（遗留）。
- **规范冲突待裁**：`required_articles.json` 与 `CONTRIBUTING.md:29`「条文映射放 `domain_rules.py`」冲突未处置；本批按"数据清单"处理，是否迁移或修改规范待 Owner 决定。
- **文档漂移**：§三"15 个"→16；`settings.py` 注释删"无新增即停止"；`run_eval.py` docstring 改 `.jsonl`；预登记移除部署核验（执行留痕回归本节）。

**F4 实施（2026-10-27 22:15，Owner 对齐后）**：整答出口（E7/E9/agent 终稿）在 `strip_internal_notes` 之后检测矛盾，命中追加 `提示：结论与所引条文不一致，请以条文原文为准`；三处答案缓存闸 + `_post` 的 QA 沉淀条件均加 `not contradictions`；流式路径（已发帧不可回收）只拦缓存、不补提示。误报门槛：59 题存量答案 **0 触发**（该集合不含此形态，属弱证据）、20 条构造边界句 **0 误报**、事故答案命中 **['234']**（按"否定短语最近条号"收紧后不再误伤第 14 条）；提示文案经 `strip_internal_notes` 与 `strip_unprovided_notes` 后仍保留（有用例钉住）。校准表：`dispatch-output/f5-calibration-20261027/calibration.md`（30 对，15 支持 + 15 未支撑，含条文原文与人工判定空列）。

**F4 端点/沉淀证据（2026-10-27 23:00）**：`tests/test_f4_endpoint_20261027.py` 2 passed——矛盾答案 SSE 文本含提示且 `answer_cache.put` 未调用；正常答案无提示且缓存被调用（对照，证明闸门有区分度）。`tests/test_f4_curation_20261027.py` 2 passed——矛盾答案 `ks.create_candidate` **未被调用**、正常答案调用 **1 次**（对照，证明沉淀拦截生效）。语义回滚脚本 `dispatch-output/watch-it-fail-20261027/run_f4_mutations.py` 三处（cache_gate / note_append / curation_gate）均 rc=1、按正确原因红；两次还原后 sha256 与基线一致。

**F5 周报（2026-10-27 23:15）**：`dispatch-output/f5-weekly-20261027/run_weekly.py` 正式跑 20 条线上抽样（`qa_candidates`、去标识）：84 对、84 判定、47 支持 / 37 未支撑，**pair 级支撑率 0.560**；与固定集 0.568 接近。样本来自已采纳候选（偏高有据）、judge 未校准，故只作趋势读数，不作"引用错误率"。校准任务书：`dispatch-output/f5-calibration-20261027/校准任务报告.md`（30 对实质断言；已剔除空断言，1179/289 在列；含判读标准与交付方式）。盲判版：`dispatch-output/f5-calibration-20261027/blind/calibration-blind.md`（隐藏 judge 两列、顺序打乱、独立目录）；合并脚本 `merge_blind.py`（一致率 / 过严 / 过松，已用合成 4 判自测：0.75、1、0）。

**F5 校准回填（2026-10-27 23:55）**：判读者为 AI 法律研究专家（非执业律师），盲判 30/30（支持 22 / 不支持 8 / 不确定 0），与 judge 一致率 **0.70**（κ=0.40，95% CI 0.52–0.83）；judge 支持精确率 93.3%、未支撑精确率 **46.7%**；过严 **8/15（53.3%）**、过松 1/15（6.7%）。8 条过严集中在"省略例外/条件但核心成立"（5 条）、解释性范围（1 条）与"措辞/模态严格度"（2 条）；1 条过松为排除式引用。结论：**56.8% 是下界**；示意校正 ≈76%，但样本平衡富集、判读者非人类、n=30，不得作精确值。报告 `dispatch-output/f5-calibration-20261027/calibration-report.md`。下一步：judge 口径 v2（核心命题 + 排除句规则）+ 随机 30 对独立人类复核后再更新基线。

**judge v2 同集调参（2026-10-28 00:05）**：候选 `JUDGE_SYSTEM_PROMPT_V2`（核心命题/排除句/总则条文规则，生产默认仍 v1）在 30 对上把过严从 8 降到 0–2，但同集调参 + #5/#12 两轮翻转（2/30）⇒ **不采纳为默认**；#9（"情节严重…甚至吊销" vs "造成严重后果"）为持续口径分歧，需人定。报告 `dispatch-output/f5-calibration-20261027/v2-diagnostic-report.md`。下一步：随机 30 对 + K=3 多数 + 独立人类复核。

**F5 独立验证集（2026-10-28 00:30）**：`dispatch-output/f5-validation-20261028/`——随机 30 对（按 v1 支持/未支撑分层各 15，排除校准 30 对与事故答案，seed=20261028）；judge K=3 已预跑：v1 自一致 27/30、**v2 26/30**；v2 把 v1 的 15 条"未支撑"中 **9 条翻成支持、0 条反向**，正确性待独立盲判。判读者只拿 `blind/` 目录，不给 `validation.jsonl`。

**F5 独立验证结论（2026-10-28 00:55）**：随机 30 对（判读者为 AI 法律研究专家，非人类）：v1 一致率 0.815、过严 5（占真实支持 25%）、过松 0、**真实错误召回 100%**；v2 一致率 0.885、过严 0、**过松 3（占真实不支持 43%）**、K3 自一致 92.9%。⇒ **v2 不采纳**，生产默认继续 v1。v3 提案 = v2 口径 + 恢复「无命题→不支持」「必须支撑主要法律后果」两条，需新随机 30 对验证。采纳标准修订为：过严 ≤10% 且 过松 ≤20% 且 K3 ≥90%。随机样本校正：v1 未支撑精确率 58.3% ⇒ 支撑率约 **75%**（区间 65–85%），56.8% 为下界。报告 `dispatch-output/f5-validation-20261028/validation-report.md`。

**知识库版本票据（2026-10-28）**：本地《宪法》为 **1999 年前版本**（第 5 条无"依法治国"、第 33 条无"尊重和保障人权"、第 67 条仍"戒严"且 21 项无监察委员会）⇒ 引用与核验基准陈旧；票据 `dispatch-output/kb-version-issue-20261028.md`，建议单独一批重新导入 2018 修正版并用元典逐条核验，同时抽查高频法是否系统性漂移。

**通用门禁（本批执行后）**

- `ruff check` / `ruff format --check`：changed files 全部通过；
- `mypy`：`coverage_gate.py`、`output_normalize.py` 0 issues；
- 定向回归：141 passed（含 `test_output_normalize` / `test_request_bootstrap` / `test_agent_gate` / `test_answer_quality_prompt_round7`）；
- 全量 `pytest -m "not slow"`（首跑）：**2140 passed / 2 failed / 2 skipped**；两处失败均与本批相关，已修复：
  - `test_log_field_whitelist`：新增 5 个 `extra` 日志字段未登记 → 已加入 `observability._ACCOUNT_FIELDS`（`coverage_*` 4 个 + `contradiction_articles`）；
  - `test_cancel_boundaries::test_d2`：测试桩替换 `retrieval` 时 `exact_article_lookup` 导入失败 → 改为惰性 import，异常由闸门记为缺口；
- 全量复跑（独立 `--basetemp`）：**2142 passed / 2 skipped / 19 deselected / 0 failed**（250.43s，RC=0）。注：第二次复跑跑到 100% 无失败，但收尾被沙箱 safe-delete 守卫打断（garbage 目录 554 文件，无 summary）；改用独立 basetemp 的第三次复跑取得上述读数。

**变更清单（已提交 `ec6a97e`）**

- 修改：`backend/main.py`、`backend/prompts.py`、`backend/request_bootstrap.py`、`backend/settings.py`、`backend/output_normalize.py`、`backend/observability.py`；
- 新增：`backend/coverage_gate.py`、`backend/knowledge_base/required_articles.json`、`backend/tests/test_coverage_gate_20261027.py`、`backend/tests/test_output_hygiene_20261027.py`、`backend/tests/test_prompt_boundary_20261027.py`、`dispatch-output/p0-replay-20261027/run_replay.py`。

**已知边界**

- 流式路径（E5/E8）帧已逐段下发、无法回收：F3 在该路径只能"检测 → 日志 → 拦缓存"，正文脱敏依赖 F2 的 prompt 预防；非流式兜底（E9）、agent 终稿、落库三条缓冲路径为确定性删除。
- F1 默认 off（项目纪律：默认关 = 行为逐字不变），开启属评测批预登记；事故回放以 enforce 模式验证。

---

## 八、附：本次事故答案的逐项改法（对照）

| 原答案写法 | 应改为 |
|---|---|
| 依据第2、13、14条"推导"故意伤害罪 | 直接适用第234条第2款；总则仅用于故意/共同犯罪的解释 |
| 用第289条作为"间接指引" | 删除；289条仅适用于聚众"打砸抢" |
| "一级伤残属于重伤范畴" | "须经伤情鉴定确认重伤；伤残等级与伤情等级分属两套标准" |
| "共同犯罪理论"替代第29条 | 引第29条第1款；并引第25条、第26/27条认定主从犯 |
| 结论卡夹带"存在引用缺失风险" | 结论与限定语分字段；缺失即拒答或标注，不进结论卡 |
| 引用刑诉法第55条说明定罪 | 删除；改引第95条重伤定义与第234条量刑档 |
