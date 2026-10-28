# 第六、七轮 Q1 复核：条文有效但结论支持不足

日期：2026-10-23。对象：`writer-replay/salary`、`writer-support-fix/salary` 两份真实 Writer 输出，及现行 `DeterministicVerifier`。本轮只做只读取证与代码审查，**未改业务代码、未提交、未推送、未重跑模型**；原失败样本保持不可变。

## 0. 结论先行

1. **Q1 成立，保持未关闭。** 两份输出 writer 阶段均为 `READY / DRAFT_VALIDATED`；本轮另做**零模型**验证器复现，二者均为 **`PASS / VERIFIED`**，6 条 claim 全部 `supported=True`。但其中 4 类法律断言在**它实际绑定的条文原文里找不到依据**。
2. 根因不在提示词，也不在“引用 ID 是否有效”，而在**“支持”只有溯源层定义（provenance），没有命题层定义（entailment）**。验证器能证明“这句话引了第八十二条”，不能证明“第八十二条说了这句话”。
3. 三处结构性放行见 §3：条号集合包含、争点级“任一条 claim 绑到生效成文法即整题通过”、以及缺少“每个规范句须有规则依据”的判定。
4. 因此继续堆 writer 提示词或加关键词黑名单都不能闭合 Q1；需要新增独立判据。本轮给出三条候选路径与代价（§5），**尚未实现**，等待选定后再动代码。
5. 本文对“某结论是否另有法源支持”只做文本层判断，不新增法律正确性结论；涉及现行通说的部分标注为待专业签核。

## 1. 冻结样本

| 证据 | 路径（`fazhi-round67-live-20261023/`） | sha256 | 性质 |
|---|---|---|---|
| 源状态 | `scope-fix/salary/result.json` | `5f399c4ed21765feff20aac32370a78f7360a6c29d68f3b74a9a5c179b7c70dd` | 两轮重放共同的不可变输入 |
| 原 replay | `writer-replay/salary/writer-result.json` | `76381e3a3cd6d773cb5bd66901acaf109b47f1aac8be375605de63652efd7f52` | 旧规则 Writer |
| 新 replay | `writer-support-fix/salary/writer-result.json` | `97d00bcee80c7421b4cf23be174ee6fbf00d177aa3c833097204d923ecfc93ef` | 新规则 Writer（同状态、同证据） |

本轮只新增三个只读产物：`dispatch-output/round67-q1-20261023/extract_q1.py`、`verify_q1.py` 及对应 `.out`（逐 claim 对照与验证器复现读数）。未复制、未改写上述原始证据。

## 2. 逐句支持审计

绑定关系由 `derive_fact_id` 复原，与被测产品同一口径；下表“证据原文”即该 claim `evidence_ids` 对应 snippet。

### 2.1 原 replay（旧规则）

| claim | 绑定证据 / 事实 | 断言 | 条文原文是否含该规则 |
|---|---|---|---|
| `claim_cf3828…` conclusion | 第八十二条；事实“公司没有签订劳动合同”“工作已经满三年” | 首句逐字引第八十二条；第二句据事实适用；第三句“该主张可能受**一年节点及时效**等因素限制” | 规则句支持；**“时效”无任何绑定依据**（本条 snippet 无时效内容，全案也无时效类证据） |
| `claim_1075…` conclusion | 第八十二条；事实“我每月工资8000元” | “以**劳动者月工资标准为基数**”“未超过时效” | 条文只说“每月支付二倍的工资”，**未定义计算基数**；**“时效”无依据** |
| `claim_b8fcb2…` issue_analysis | 第十四条；事实“工作已经满三年”（**漏绑“公司没有签订劳动合同”**） | 首句逐字引第十四条；末句“超过该节点后**一般不再按未订立书面劳动合同主张二倍工资**” | 第十四条只规定“视为已订立无固定期限劳动合同”，**未规定二倍工资的终止**；该推论需另引法源 |
| `claim_9a5413…` risks | 第八十二条；事实“我每月工资8000元” | “**仲裁时效**可能对可主张期间产生影响” | **无依据** |

### 2.2 新 replay（新规则）

| claim | 绑定证据 / 事实 | 断言 | 条文原文是否含该规则 |
|---|---|---|---|
| `claim_3fa72…` conclusion | 第八十二条；事实“我每月工资8000元”“公司没有签订劳动合同” | “计算基数通常按劳动者每月工资标准确定”；“主张时间（**涉及仲裁时效起算**）” | 基数表述仍超出条文；**时效起算无依据** |
| `claim_d0510…` conclusion | 第八十二条 + 第十四条；事实“公司没有签订劳动合同”“工作已经满三年” | 引第十四条；“**满一年之后通常不再支持二倍工资差额**”“**一般限于**自用工之日起超过一个月不满一年的未签合同期间” | 事实绑定已补齐（相对旧 replay 的改进）；但第十四条不产生该效果，**“期间上限/终止”仍无绑定依据** |

### 2.3 缺口归纳

四类缺口互相独立，且都不是“条号写错”：

1. **仲裁时效规则**（起算、一年、中断）——全案没有《劳动争议调解仲裁法》类证据。
2. **二倍工资可主张期间的终止/上限**（满一年后不再支持、最长十一个月）——需要的规则不在第八十二条、第十四条文本内。
3. **计算基数**（以月工资标准为基数）——条文只规定“每月支付二倍的工资”。
4. **未签合同期间的起止界定**——旧 replay 漏绑关键事实，新 replay 已补，但仍以“待确认”处理。

这四类都是**规则命题**。验证器比对的是条号，所以全部放行。

## 3. 验证器为何放行（代码证据）

[verifier.py](file:///c:/Users/33393/Desktop/ai-legal-helper/backend/agent/verifier.py)：

- 引用门只做集合包含：`canonical_citations(claim.text).issubset(canonical_citations(bound_evidence_text))`（[L429-L434](file:///c:/Users/33393/Desktop/ai-legal-helper/backend/agent/verifier.py#L429-L434)）。它回答“claim 提到的条号是否都在绑定证据里”，不回答“该条号是否支持这句话”。
- 数字门只比对数字 token（[L394-L407](file:///c:/Users/33393/Desktop/ai-legal-helper/backend/agent/verifier.py#L394-L407)）；本案没有可捕获的数字缺口。
- 争点覆盖门是**争点级**的：任一 claim 绑到任一“生效成文法”即 `has_effective_statute=True`，整题跳过（[L456-L473](file:///c:/Users/33393/Desktop/ai-legal-helper/backend/agent/verifier.py#L456-L473)）。同一争点内其余 claim 的命题内容不再过门。
- 逐 claim 只校验证据/事实存在、同争点归属、生效性（[L340-L387](file:///c:/Users/33393/Desktop/ai-legal-helper/backend/agent/verifier.py#L340-L387)）；没有“规则句须有逐字依据”的检查。
- 现有最接近的负例是 `test_verifier_does_not_accept_user_fact_as_statute_citation_authority`（[test_agent_verifier.py L747-L769](file:///c:/Users/33393/Desktop/ai-legal-helper/backend/tests/test_agent_verifier.py#L747-L769)）：它拦的是**条号根本不在绑定证据里**，与本轮“条号在、命题不在”不是同一个失败面。

### 3.1 零模型复现（本轮新鲜读数）

`verify_q1.py` 把冻结的 `state` 与两份 `draft` 直接喂给 `DeterministicVerifier`，不调用模型：

- 开关与 `backend/.env` 一致：`AGENT_WRITER_DESENSITIZE_UNKNOWN_FACTS=true`、`AGENT_PARTIAL_DELIVERY_ENABLED=true`；未覆盖的两个争点按 service 部分交付路径传入 `covered_issues_exempt`。
- 读数：两轮均 **`PASS / VERIFIED`**，`unsupported_claim_ids=[]`，共 6 条 claim 全部 `supported=True`（见 `verify-q1.out`）。
- 边界：`writer-result.json` 只证明 **writer 阶段** READY；probe 的 writer replay 只调用 `EvidenceBoundedWriter.render_issue`，**没有跑 verifier**，所以 PASS 是本轮补跑得到的，不是原产物自带。若不启用脱敏开关，同一 draft 会以 `FABRICATED_MISSING_INFORMATION` 失败（`missing_information` 用的是脱敏后文本），说明该 PASS 依赖生产开关组合——这一点另行记录，不并入 Q1 结论。

## 4. 能力边界（为什么不能靠调参关闭）

| 确定性验证器能判 | 不能判 |
|---|---|
| 证据/事实是否真实存在且归属正确 | 条文文本与法律推论之间是否构成蕴含 |
| 条号是否出现在绑定证据中 | 该条文的**适用范围**是否被外推（如用第十四条推二倍工资终止） |
| 数字是否越界、是否过度承诺措辞 | 一个规范句是否需要另一部法源 |
| 每个争点是否至少有一条生效成文法的 claim | 同一争点内其余 claim 的命题是否成立 |

结论：这是**判据定义缺失**，不是阈值或词表能补的。报告原文“不要继续只堆提示词或以关键字黑名单代替法律适用审查”成立。

## 5. 候选判据与代价（待选定）

| 方案 | 做法 | 能关到什么 | 代价 / 风险 |
|---|---|---|---|
| **A 结构化规则锚（推荐先做）** | 扩展 claim 契约：每条“规则句”必须给出 `{evidence_id, quote}`，`quote` 必须是该证据 snippet 的逐字子串；验证器确定性校验子串存在、条号一致 | 本案四类缺口全部无法锚定 ⇒ 必须删句或降为“待确认”，不能再以第八十二条作“通行证” | 改 writer schema/提示词契约与全部 writer 用例；只能证明“引了原文”，不能证明“推论正确”；误拒靠“允许省略无法支持的句子”兜底 |
| **B 独立支持审查器（离线先做）** | Writer 之外的第二判定，证据封闭，输出 `{supported, unsupported_spans}`；先只用于评测，不进线上阻断 | 能覆盖推论层 | 引入模型不确定性与成本/时延；与当前“确定性验证”架构假设冲突，需 Owner 决策；需一红一绿控制与稳定性证据 |
| **C 零依据规则断言阻断（词表）** | 维护“仲裁时效/期间上限”等词表，命中即要求对应法源 | 只能抓显式词，抓不住外推 | 报告已明确反对；换一批样本即失效 |
| **D 维持现状** | 不新增代码，Q1 记为已知限制 | 无 | 质量验收仍不通过；与“不得以 READY/pytest 宣布达标”冲突 |

推荐顺序：**A（确定性、可回归、与“事实必须逐字引用”的既有纪律同构）→ B 离线并行验证命题层 → C 不采用**。若 Owner 不接受契约变更，则退到 D，并在验收口径中如实写明。

## 6. 本轮边界与未闭合项

- 未改 `verifier.py`、`writer.py`、`prompts.py`、`runtime.py`；未新增测试；未跑模型。
- Q1 **未关闭**。本轮只冻结了反例并给出判据设计选项。
- 四类缺口是否另有法源支持，属法律正确性判断，**待专业签核**；本文只断言“在绑定 snippet 文本内不可见”。
- Q2 覆盖声明矛盾、Q3 剩余混合句边界、Q4 冗余追问均未在本轮处理。

## 7. 复现

```text
python dispatch-output/round67-q1-20261023/extract_q1.py   # 逐 claim 绑定对照
python dispatch-output/round67-q1-20261023/verify_q1.py   # 零模型验证器复现（PASS/VERIFIED）
```

输入为 §1 三个文件；`extract-q1.out` 与 `verify-q1.out` 保存了本次完整输出。
