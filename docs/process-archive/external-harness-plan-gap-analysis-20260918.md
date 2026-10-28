# 外部 Harness 方案 × 法智现状 · 差距分析报告

> 生成时间：2026-09-18
> 被评方案：知识库文档《legal-agent-harness-review-optimization-plan》（外部人士编写，原作者对法智项目一无所知）
> 方案版本：新版（nodeId `PkpoxuSZgfdzex4EnAbWnQ`，2026-09-18 02:35 更新）；旧节点 `yxLdnVHGZhuk3NcSfMPfbq`（02:14）已过时
> 核验方式：方案侧压成 64 条可在仓库里查证的能力项，仓库侧逐条 grep/Read 取证；本报告结论**要求 file:line 证据**，找不到即记「未找到」

---

## 一、方案本身的更新过程（先交代清楚，避免版本混淆）

| 时间 | 动作 |
|---|---|
| 02:14 | 外部方案首版落库（旧节点 v4，227,557 字符） |
| 02:29 | 我拉快照 `_harness_doc.txt`（sha 前缀 `05e2012b…`） |
| 02:32 | 你问是否更新 → 重拉，字节完全一致，**当时确实没更新** |
| 02:35 | 你新增同名新 md（新节点 v4，279,056 字符，sha `3f04df7b…`） |
| 02:38 | 重新列出目录，发现新节点并做差分 |

**差分结论：新版 = 旧版全文 + 新增块，没有任何删改或推翻旧内容。**

- 纯文本级：删除 30 行（全是格式/项目符号噪音），新增 1,880 行，均为插入。
- 新增内容：
  1. **§2.5 中国大陆法域特化规则**（8 个小节，约 +1,500 行）——因你把待确认项 D2「法域=中国大陆」确认了，原本"法域无关"的部分被落成中国法域可编码硬规则。
  2. **附录 C：`legal_rules.cn.yaml` 红线检查配置**——可直接抄成代码。
  3. 红队条目 14 → **16 条**（新增 #15 法域规则过时+地域过度保守、#16 相似法条区分度/混合检索），"最致命三条"→"四条"，修复措施 6 → 8 项。
- 修改的只有几处：D2 状态从「默认假设」改「用户已确认」；待确认清单 D2~D6 → D3~D6；§9.1 汇总数字更新。

> 一句话：这个 02:35 版本是目前唯一有效的 analyzing 对象，旧节点可以无视。

---

## 二、盘点结论总览

按 64 条核验项统计：

| 状态 | 条数 | 含义 |
|---|---|---|
| ✅ 有且在用 | **16** | 代码里有实现，且有产物/默认开启 |
| 🟡 有雏形但未成体系/未启用 | **28** | 有一半：有nz吐槽查询、但缺 ××；或有脚本无产物；或默认关闭 |
| ❌ 完全未找到 | **20** | 全仓 grep 零命中 |

**法智的真实水平：工程与"防错"侧相当扎实，"评测体系 + 法律域语义（尤其是中国法域的时间/地域/效力层级）"侧明显薄。**
——这个分布和我知道的项目现状一致：过去两个月精力主要砸在引文精确率、实体精度、Hybrid 检索、发布快照冻结上；而"评测统计学""LLM-as-judge 偏差""用户信任校准"这类没有人问责的长期工程基本没动。

---

## 三、✅ 已经有的（16 项）——不要重复投资

| ID | 能力 | 证据 |
|---|---|---|
| R02 | 语料入库必填/日期格式/状态白名单强校验 | `backend/schemas.py:148-183` |
| R03 | 已废止法由 `status` + `effective_to` 自动判定（fail-closed） | `backend/retrieval_core.py:47-59` |
| R07 | 真 hybrid：BM25(jieba) + 向量 → RRF 融合 + 云 rerank 兜底 | `backend/retrieval.py:1-7` |
| R08 | 检索最小单元 = "条" | `backend/chunking.py:176` |
| R14 | 终止条件确定性（max_steps/预算）+ `completeness=partial` 标记 | `backend/agent/controller.py:701/945`、`chat_integration.py:71-72` |
| R16 | 追问轮次上限 2 | `backend/settings.py:63` |
| R18 | 提示词 bundle sha256 进发布清单 | `backend/scripts/release_manifest.py:97` + 12 个发布目录产物 |
| R20 | "无证据" vs "证据错误"两种原因码分离 | `agent/verifier.py:414` vs `:375-380` |
| R21 | 幻觉/越权/死循环/非法引用 >0 即 release BLOCK | `backend/scripts/check_agent_release.py:696-705` |
| R27 | 虚假确定性检测（禁止绝对化表述→重写） | `agent/verifier.py:59-80` |
| R33 | 纵深防御三层：输入过滤 + 输出校验 + 独立复核 | `llm_guard.py` / `verifier.py:380`（Writer 不能自己签 support verdict） |
| R42 | 评测统一关缓存 + token/工具调用上限 | `scripts/capture_protocol.py:15-24`、各 eval 脚本 `no_cache=True` |
| R48 | **快照冻结**：commit + 语料 + 索引 + 模型 + prompt + 工具策略 | `scripts/release_manifest.py:41-99`（17 个发布目录中 12 个全套） |
| R53 | 灰度百分比 + 一键回滚开关 | `settings.py:51-52`、`routing_metrics.py:43-60` |
| R57 | 跨会话隔离 + 会话删除通道 | `memory.py:29`、`main.py:2149` |
| R61 | 按 `cutoff` 的时效过滤（检索/BM25/打分共用唯一谓词） | `retrieval_core.py:41-59`、`retrieval.py:751-774` |

> 特别说明 R48：方案把它列为"必须先做的 Pre-flight"，法智是**全 64 条里完成度最高的一条**，12 份 release-evidence 产物齐全。这是真实资产，别谦虚。

---

## 四、❌ 完全缺失（20 项）

### 4.1 法律域语义层（这一块最致命，也是新版 §2.5 新增的重点）

| ID | 缺什么 | 为什么致命 |
|---|---|---|
| R11 | **诉讼时效常量未硬编码**：3年（民188）/20年最长（不适用中止中断）/劳动仲裁1年（劳调27） | 我在 `backend/scripts/` 里 grep "诉讼时效" 只命中**题库文本和语料正文**——也就是这条知识目前是"让 LLM 从语料里读出来的"，不是程序算出来的。这正是方案 T1「2021 民法典分水岭」要根治的坑：跨 2021-01-01 的事实，模型拿 today 当基准日就必然算错时效。而我们 `agent/repository.py:62` 默认 `law_as_of=date.today()`。 |
| R12 | **伪调用检测** | 🔴 与我们已知缺陷直接对上：deepseek-v4-flash 的"伪调用"（工具调用被渲染成 XML 文本而非真执行）至今只能靠肉眼发现。现有 `state_machine.py:57-70` 只检测"重复调用"，检测不了"声称调用但未真调"。 |
| R13 | 按意图暴露工具子集 | `runtime.py:83-90` 固定 4 工具全集暴露给所有意图。 |
| R17 | 声明式编排配置 | 流程转移表硬编码在 `state_machine.py:52-56`，backend 下无 yaml/json 编排文件。 |
| R38 | **评测样本不带 `fact_date` / `as_of_date`** | 已验证 `evals/frozen-cases-v2.json` 的 case 字段为 `id/domain/initial_question/round{1,2}_facts/required_issues/required_laws/critical_failures/deciding_facts`，**没有日期字段**；案情里的时间（如"2020年借款…2026年"）混在文本里，机器无法用于版本选择。这直接导致 R15「先抽事实日再选法律版本」做不了。 |
| R62 | 法律修订触发金标复审的机制 | 无钩子，全靠人记得。 |
| R63 | 未识别地域时的分级响应（上位法+提示+查询指引） | `backend/docs/COVERAGE.md:30` 明写"部门规章/地方性法规：未收录"——地域层是空的。 |
| R64 | 地域敏感类别清单（婚假/最低工资/社保/工伤/限购…） | `prompts.py:111` 仅出现"当地月最低工资标准"字样，无结构化清单，无"未识别地禁给数字"的判据。 |

### 4.2 评测方法论层

| ID | 缺什么 | 备注 |
|---|---|---|
| R40 | Bootstrap 95% CI / 两比例检验 / BH 校正 | 评测脚本里 grep `bootstrap/置信区间/显著性` 零命中（`gen_phase1_audit.py:3` 的 bootstrap 指 Agent 引导阶段，同名不同义）。**→ 现在所有"提升 X 个百分点"的结论都不具备统计效力。** |
| R44 | LLM-as-judge 的抗偏设计：双向评测 / 引用剥离 / 跨厂商评委交叉 | `scripts/_judge.py:15-35` 单一 judge（默认 qwen3.7-plus）。同一厂家既生成又评分。 |
| R46 | 归因决策树 | 有原因码、有报告，没有把 badcase → "该改哪一层"固化的决策规则。 |
| R47 | 统一 trace schema | 全仓 grep `trace_id/turn_index/spans` 零命中；只有 `observability.py:13` 的 `request_id` ContextVar + 扁平记账字段。→ 不可复现的单次回答链路。 |
| R51 | CI 里自动跑主评测集 | `.github/workflows/ci.yml` 只有 lint/type/coverage/前端 build。**1155 个 pytest 是单元测试，不是端到端评测门禁**，二者不可混为一谈。 |
| R55 | 单会话成本上限与告警 | 只有全局 embedding/rerank 配额（`quota_utils.py:41-63`）。 |
| R56 | Goodhart 迹象监控（答案长度分布、去重率/熵） | 无 → 将来做指标优化时会被 propia 刷分反噬。 |
| R59 | 信任校准实验（过度信任率 / ECE） | `calibrate_confidence.py` 是检索阈值标定，同名不同义。 |
| R60 | 按用户角色分层出指标 | `models.py:16` role 仅 user/admin 权限字段。 |

### 4.3 合规/输出层

| ID | 缺什么 | 备注 |
|---|---|---|
| R28 | 拒答时的**转介路径** | 只说"请咨询律师"，没给"找谁/哪个机构/法律援助热线"的可执行路径。 |
| R29 | AI 生成内容标识 | 全文只有 `prompts.py:19` "仅供参考，不构成正式法律意见"，不构成《标识办法》意义上的合规。 |
| R32 | 集中式红线规则配置 | "红线"散落在 `dept_guard.py:124`、`service.py:546`、`gate2_runner.py:188`，无配置文件可审阅。 |

---

## 五、🟡 半成品（28 项）——已不小的部分，挑代表性的说

| ID | 状态 | 缺的那半 |
|---|---|---|
| R01 | 语料有 `effective_from/to`、`status`、版本链、`source_document_sha256` | **缺 `level`（效力层级）/ `issuing_body` / `jurisdiction` / `superseded_by` / `interprets`**。已验证 `data/laws.json` 只有 7 个字段：`article_number/category/content/effective_from/effective_to/status/title`。→ 这意味着「把司法解释冒充/降级为法律」这类错误**现在无法被程序检出**（方案把它列为 L2_fail）。 |
| R10 | 有确定性费用计算（`agent/fee_calc.py` + `fee_formulas.json`） | 只有"钱"这一类；时效、管辖无计算器。且相关开关默认关。 |
| R15 | 有 `law_as_of` 与 cutoff 过滤 | **无 fact_date 抽取环节**，基准日默认设为今天 → 跨法修订场景必然错。 |
| R19/R23 | 引用有程序化校验、条号越界分级 | 无 `verified`/`verification_method` 具名字段；**引用输出不带版本日期锚**。这与已知缺陷「study_aid（`sources=[]`）下 citation_verify 误判法条为杜撰」同源——根子都在"引用对象缺完整的版本/来源上下文"。 |
| R24 | 强制书名号格式 `《…》第X条` | 无「效力层级 + 截至日期」的统一模板。 |
| R25 | 禁"保证胜诉/100%"等高风险表述 | **但 `prompts.py:13/43` 系统提示词自己写"像资深律师一样"**，无 `must_refuse` 集合配置。自相矛盾。 |
| R34 | 评测数据多文件分置（frozen-cases-v2 `20 条 FROZEN` / holdout `5` / eval_set `28` / eval_agent_complex `20` / redteam 硬编码 `eval_redteam.py:31-40` 10 例） | **主集只有 20 条**（方案要求 S2 600–1000）；红队种子硬编码在脚本里，无 dev/probe/main/redteam 四层目录规范。 |
| R35/R36 | 有 `domain` 字段与 `forbidden_articles` 条目级禁引 | 无七类配额（跨法修订/地域/层级/前提错误/应拒/要素不全/多轮），无独立反事实层。 |
| R50 | CI 有 lint/type/coverage/pip-audit | **质量红线（`check_agent_release.py:696-705`、`safety_readiness_check.py`）未接入 CI**，靠人工跑。 |
| R52/R54 | 有预注册文档与验收留痕的**纪律** | 无工具强制单变量，无统一"假设-预期-实测-结论"模板文件。 |
| R58 | 有删除通道 | 无保留期策略（grep `retention/保留期` 零命中）。 |

---

## 六、我的判断：哪些该补、哪些别补（按收益/成本排序）

### P0 · 低成本、直接防事故（建议立刻做）

1. **R11 + R10：时效/管辖确定性工具 + 常量表**
   把 `民188=3年、最长20年(无中止中断)、劳动仲裁=1年(劳调27)` 写成常量，并让 writer 引用它们而不是从语料里"想"。方案附录 C 已给了 YAML 结构，照抄即可。
   *这一步单独能把"跨 2021-01-01 时效算错"这整类错误（T1，方案称最高频最致命）打掉。*
2. **R38 + R15：给评测样本加 `fact_date`，并把 `law_as_of` 默认从"今天"改成"抽到的事实日，抽不到就追问"**
   目前 `repository.py:72`（原文误记为 :62，2026-09-18 核实）写死 `date.today()`，是明确的行为 bug 级隐患。
   ~~改起来是一个函数的事。~~ **（2026-09-18 实施时订正：成本被低估）**① 抽取环节整条不存在
   （`fact_date` 仅出现在 `limitation_calc` 形参与其测试里，`calc_limitation` 的生产调用方为 0）；
   ② `law_as_of` 在 `create_run` 定值，早于任何文本理解，`LegalAgentState` 无该字段、writer/verifier
   都看不到它 ⇒ 改默认值等于改"基准日何时不可变"这条不变量；③ `VerificationVerdict` 只有 4 值且
   非 PASS 即终态 FAILED，"追问"通道挂在 controller 的 `(issue_id, UnknownFact)` 锚点上，
   基准日没有锚点。
   **本批已落地的部分（2026-09-18 R15 绊线批次）**：`verifier` 版本适用绊线
   （`settings.law_version_tripwire_check`，默认关）拦"按 law_as_of 版本的法答分水岭前事实"，
   含**不带年数 token 的引用型错答**（numeric/citation 两门对此类均无感——证据池本身按 cutoff 捞，
   永远只捞得到现行法）；`service` 从 `AgentRun.law_as_of` 透传，且基准日随 PASS 结果传给
   `render_verified` 的二次验证；评测注入出口 `gate2_runner --cases-file` + 案例 `as_of_date` +
   非冻结对照样本 `evals/watershed-cases-r15.json`。
   **仍缺**：事实日抽取环节、无锚点的澄清态、frozen 集加 `fact_date`（触 T0 冻结物，需 Owner 决策卡）。
3. **R12：伪调用检测**
   已有真实故障（deepseek-v4-flash XML 文本伪调用）。实现成本极低：工具实际调用计数 vs trace 中声明调用数比对，不等即告警。这是**方案中已经列为必做、而我们手上恰好有现成反例**的一条。
4. **R32：把散落的红线收成一份 `legal_rules.cn.yaml`**
   纯整理工作，但收益是"红线可审阅可扩展"——现在改一条红线要动 3 个文件。
5. **R24：引用输出模板加 `(效力层级，现行有效，截至 YYYY-MM-DD)`**
   用户可见，直接提升可信度，且与 P0-2 是同一套 `as_of` 基础设施。

### P1 · 中期、成体系才有用

6. **R34/R35/R36：评测集从 20 条扩到 ≥150 并按七类配额**（先做 40–50 条 + 配额，别一次上 1000）
7. **R40：给评测加 bootstrap CI**——否则目前所有"提升 X pp"的结论都不能写进对外材料
8. **R45/R46：taxonomy + badcase 双码归因账**——现在是"有原因码无分类法"，改完再谈"从 badcase 定位到层"
9. **R50：把质量红线接进 CI**（而不是只跑 pytest）
10. **R01：给语料补 `level`/`issuing_body`/`jurisdiction` 三个字段**——这是开启后续所有"层级混淆检出""地域分级响应"的前置条件

### 🚫 明确不建议现在做（诚实标注我的主见）

| ID | 方案要求 | 为什么现在别做 |
|---|---|---|
| R37 | 标注手册 ≥20 页 + 双盲标注 + Cohen's κ ≥ 0.7 | 单人+AIng 干活，没有第二个标注者，κ 在数学上算不出来。退而求其次：留"分歧裁决记录"，我们已有 `dispatch-output/ta1-annotation-*` 的 `disagreement-verdicts.md` 惯例，够用。 |
| R34(S2) | 主集 600–1000 条 | 按当前迭代节奏不现实。先到 150 条并保住质量，比凑 600 条水题有用。 |
| R59 | 信任校准真人实验 n≥20 | 需要真实外部用户。线上目前零 Agent 流量（`AGENT_ENABLED` 未开、`TRAFFIC_PERCENT=0`），没有样本来源。 |
| R53 | 1%→5%→20%→50%→100%，每档 ≥3 天 | 同上，零流量的灰度是形式主义。开关和分桶机制已有（`settings.py:51-52`），真放量时再用。 |
| R17 | 声明式编排 DSL | 当前只有一种编排路径，抽象无收益，反而增加理解成本。等有第二套编排时再说。 |
| R36/R44 部分 | 跨厂商评委交叉 | 一次 end-to-end 评测要烧钱。先把 R43（单一 judge 的一致率门槛）常态化，比跨厂商交叉性价比高一个量级。 |

### ⚠️ 对方案本身的一处保留

方案 §2.5 声称其法条内容"均于 2026-09-18 通过最高法/地方法院官网一手核验"，但附录 B 里给的多是地方法院官网的文章页（如宣城中院、济南中院这类**案例/普法页**，不是法源发布页）。
**这些条文的数字本身我没有独立核实**，要把 §2.5 的表 1/表 2 直接写成代码常量前，应当以全国人大网 / 最高法发布的现行文本复核一遍——方案自己也在 T2 里承认"条号可能因修法错位"，这个警告对方案本文同样适用。

---

## 附：这份方案最值得抄的两块（可直接使用）

1. **附录 C 的 `legal_rules.cn.yaml` 骨架**——`red_lines`（含 abolished_law_blacklist / article_index_out_of_range / article_no_drift / level_mislabel / jurisdiction_missing_but_numeric_answer / judicial_interpretation_missing）+ `deterministic_tools` + `version_anchors` + `retrieval` + `citation_output_format` 五段，几乎可以 1:1 落成配置。
2. **§9 红队 #15/#16 的修复动作**——"地域响应改分级、规则由数据生成""增加相似法条区分度探针 + 混合检索"。前者我们没做（R63），后者正好命中我们已知的真实口径召回基线 43.4% 的痛点。

---

## 实施进度（2026-09-18 晚更新）

| 项 | 状态 | 说明 |
|---|---|---|
| R11 时效确定性 | ✅ 已实现 | `agent/limitation_calc.py`（23 测试）+ writer/verifier 双防线；开关默认关 |
| R12 伪调用检测 | ✅ 已实现 | `agent/phantom_check.py`（12 测试）+ PHANTOM_TOOL_CLAIM 纠正性重试码；开关默认关 |
| R15-lite law_as_of 注入 | ✅ 已实现 | ChatIn→端点→bootstrap→service→create_run 全链（5 测试 + 三重 watch-it-fail）；缺省 None=当日，行为逐字不变 |
| 冻结物处理 | ⚠️ 已闭环 | R15-lite 须触碰 repository.py（T0 冻结物）→ 取证（不在 1e9 锚定）→ Owner 授权解冻并留痕（pyproject 注释 + 提交 8479a5b） |
| R38 fact_date / R32 红线 YAML / R24 引用格式 | ⬜ 未开始 | 下一批候选；gate2_runner 发送 law_as_of 随 R38 一并加 |

门禁基线：全量 **1233 passed / 18 deselected / 0 failed**（2026-09-18 晚，含 R11/R12/R15-lite 与并行 P1 测试）。
详情：`dispatch-output/r15lite-20260918/report.md`。
