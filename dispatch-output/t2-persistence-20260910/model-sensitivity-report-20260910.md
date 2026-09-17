# 模型敏感度实测报告 —— "换其他模型不会对 agent 有大影响" 是否成立

日期：2026-09-10 · 结论：**不成立，且有量化证据**

---

## 0. 直接回答

| 你的要求读法 | 判定 |
|---|---|
| 「换模型，agent 输出**质量**不受影响」 | ❌ 不成立（且**不可达**——LLM 段必然有质量方差） |
| 「换模型，**确定性防护**仍然生效、坏输出不静默通过」 | ✅ **已经成立**（本报告证实） |
| 「换模型，**失败分布**保持一致」 | ❌ **不成立**（本报告量化） |

第三个才是你现在实际缺的那块：**防护是稳的，但失败面是漂的**。而且漂移量比预期大得多——**同一平台、只差一个小版本号，失败码集几乎不重叠。**

---

## 1. 实验设计（控制变量）

| 变量 | 状态 |
|---|---|
| 代码候选 | **完全相同**（脏工作树 + 哈希锚定，`controller.py` SHA256 `35f8e9c2…` 未变） |
| 题集 | 完全相同（冻结题 C01–C10） |
| 端点 / 凭证 | 完全相同（dashscope compatible-mode，同一 key） |
| 请求参数 | 相同（`force_agent=true`、`no_cache=true`、`AGENT_MAX_STEPS=16`） |
| `disable_thinking` | 相同（两臂均 `true`） |
| **模型 id** | **唯一变量**：`qwen3.8-flash` vs `qwen3.6-flash` |

两臂各自独立成轮：`gate5-dev-run-13-qwen38`（07:22Z）、`gate5-dev-modelarm-qwen36`（07:34Z）。

---

## 2. 结果

### 2.1 题级对照（题号由"会话首条用户消息 ⨯ 冻结题 `initial_question` 逐字匹配"确定，非位置切分）

| case | 应有争点 | qwen3.6：issues/覆盖/backfill | qwen3.6 错码 | qwen3.8：issues/覆盖/backfill | qwen3.8 错码 |
|---|---|---|---|---|---|
| C01 | 4 | 3 / 3 / – | `NON_CANONICAL_CITATION` | 1 / 1 / – | – |
| C02 | 4 | 4 / 4 / **Y** | – | 4 / 4 / **Y** | `EVIDENCE_COVERAGE_DEFICIENT` |
| C03 | 5 | 4 / 4 / **Y** | – | 3 / 3 / – | – |
| C04 | 5 | 2 / 2 / – | `CROSS_ISSUE_EVIDENCE` | 1 / 1 / – | `UNSUPPORTED_NUMERIC_TOKEN` |
| C05 | 5 | 2 / 2 / – | `CROSS_ISSUE_EVIDENCE` | 1 / 1 / – | – |
| C06 | 5 | 3 / 3 / – | `NON_CANONICAL_CITATION` | 3 / 3 / – | – |
| C07 | 5 | **无 agent_run 记录**（预运行失败） | `ISSUE_DECOMPOSITION_INVALID` | 1 / 1 / – | – |
| C08 | 5 | 2 / 2 / – | `UNSUPPORTED_NUMERIC_TOKEN` | 1 / 1 / – | `UNSUPPORTED_NUMERIC_TOKEN` |
| C09 | 5 | 2 / 2 / – | – | 2 / 2 / – | – |
| C10 | 4 | 2 / 2 / – | – | 1 / 1 / – | – |

> `–` = 该次 run 无错误码。`backfill Y` = C01 修复分支被触发。

### 2.2 汇总

| 指标 | qwen3.6-flash | qwen3.8-flash | 差异 |
|---|---|---|---|
| `agent_completed` | **4/10** | **7/10** | **+3 题** |
| 争点总数（应有 47） | 24（**缺 49%**） | 18（**缺 62%**） | −6 个 |
| `backfill` 触发 | 2/10 | 1/10 | +1 |
| 两层 judge `mechanical_pass` | **4** | **7** | +3 |
| 两层 judge `full_closure` | **0/10** | **0/10** | 0 |
| `formal_gate_passed` | False | False | — |

### 2.3 错误码分布（题次）

| 错误码 | qwen3.6 | qwen3.8 |
|---|---|---|
| （无错误码） | 4 | 7 |
| `NON_CANONICAL_CITATION` | **2** | **0** |
| `CROSS_ISSUE_EVIDENCE` | **2** | **0** |
| `ISSUE_DECOMPOSITION_INVALID` | **1** | **0** |
| `EVIDENCE_COVERAGE_DEFICIENT` | 0 | 1 |
| `UNSUPPORTED_NUMERIC_TOKEN` | 1 | 2 |

**三个错误码在一个臂出现、在另一个臂完全消失**（`NON_CANONICAL_CITATION`、`CROSS_ISSUE_EVIDENCE`、`ISSUE_DECOMPOSITION_INVALID`），只有 `UNSUPPORTED_NUMERIC_TOKEN` 两臂共有。

---

## 3. 三条推论

### 3.1 ❌ 失败分布高度模型敏感（要求不成立）

同一平台、同一 key、同一端点、只换一个小版本号 ⇒ 完成率 **4/10 ↔ 7/10**，失败码集**几乎不重叠**。
`full_closure` 两臂都是 0/10，但那是因为它被**必需要件法条未引用**（语义层）钉死，掩盖不了机械层的漂移。

**这意味着：`full_closure=0/10` 这个数字本身是模型无关的"底"，而"错在哪"完全不稳。** 只看单一数字会误以为模型无关。

### 3.2 ✅ 确定性防护层是模型无关的（唯一可依赖的部分）

两臂出现的错误码**全部来自确定性校验**（`NON_CANONICAL_CITATION` / `CROSS_ISSUE_EVIDENCE` / `UNSUPPORTED_NUMERIC_TOKEN` / `EVIDENCE_COVERAGE_DEFICIENT` 都是 verifier 判定）。
没有任何一条"不合规 draft 静默通过"的迹象——与 `docs/gate5-formal-dev-20260908.md` 附C 的结论一致（"qwen 生成的所有不合规 draft 均被确定性校验正确拦截"）。

⇒ **fail-closed 是稳的**。这是好消息，也是后续加固的立足点。

### 3.3 🔴 欠分解是**两臂共有的系统性弱点**（根因不是模型）

| 臂 | 争点缺口 |
|---|---|
| qwen3.6-flash | **49%** |
| qwen3.8-flash | **62%** |

**两个模型都大幅欠分解**（仅 C02 在 8-flash 臂达标）。所以这不是"qwen3.8 特别差"，而是**分解契约本身允许它差**：

- `backend/agent/runtime.py:61` `_ISSUE_SYSTEM_PROMPT` 原文：**「issues 为 `1` 到 `8` 个对象」**
- **无穷尽性要求、无下限、无完备性校验**——"该拆几个争点"完全交给模型的主动性先验；
- 确定性层**查不出**"少问了争点"（verifier 只查 claim↔证据绑定）；
- 因此欠分解**静默通过**，一路传导为窄答案 → 要件法条 `missing` → `full_closure=0/10`。

**这是"换模型影响大"的机制所在**：把质量押在模型的主动性先验上，而先验正是跨模型最不稳的东西。

---

### 3.4 「换了模型后能力变差了吗」的分层判定

**先说边界：严格判定"LongCat → qwen 是否变差"需要同候选的 LongCat 10 题臂，而它不存在**（Owner 于 15:16 指示暂停使用 LongCat）。因此下面分层作答，并标出哪一层能定论、哪一层不能。

**(a) 「整体端到端能力」——没有证据变差**
两臂完成率 4/10–7/10，且**达标率（`full_closure`）两臂同为 0/10**，与 LongCat 域历史结论（"0 达标未变"）同量级。
⇒ 没有"整体能力下滑"的证据。

**(b) 「分解」这一环——明显退化，且这是最可能被感知为"变差"的地方**
唯一同候选的 LongCat 证据是 C01 单题（`probe-c01-verify2`）：

| 模型（同候选、同题 C01） | 争点 | 终稿字符 | 结果 |
|---|---|---|---|
| LongCat-2.0 | **4**（= `required_issues`，达标） | 878 | completed |
| qwen3.8-flash | **1** | 404 | completed（**窄答案**） |
| qwen3.6-flash | 3 | 0 | failed |

⇒ 单题证据指向 **LongCat 在"分解召回"上明显更强**；但 **n=1，不能外推**，且 LongCat 在历史轮次也有 `ISSUE_DECOMPOSITION_INVALID`（run-9 2/10、run-11 1/10，**不同候选，不可并列**）。

**(c) 两臂之间：不是"变强/变弱"，而是**换了失败面**

| | qwen3.8-flash 胜 | qwen3.6-flash 胜 |
|---|---|---|
| 端到端完成 | **7 vs 4** | — |
| 结构化合规（硬拒绝次数） | **0 vs 4**（`NON_CANONICAL_CITATION`×2 + `CROSS_ISSUE_EVIDENCE`×2） | — |
| 分解召回 | — | **24 vs 18** 争点（缺口 49% vs 62%） |
| `full_closure` | 平（均 0/10） | 平 |

⇒ "哪个更好"取决于你看哪一步；**不存在单向的优劣**。

**(d) ⚠️ 一个被数据否掉的诱人解释（防误读）**
曾怀疑"qwen3.8 完成率高是因为拆得少、校验面小，所以是**退化的假象**"。按 issue 数分组**不支持**：

| 臂 | 完成组 issue 均值 | 未完成组 issue 均值 |
|---|---|---|
| qwen3.6 | 3.00（n=4） | 2.40（n=5） |
| qwen3.8 | 1.71（n=7） | 2.00（n=3） |

方向相反/不一致，且 n≤10 ⇒ **完成率差异不能用"欠分解换来的"解释**。
（但 C01 仍是明确的"退化被读成完成"**个案**：1 个争点、404 字符 vs LongCat 的 4 个争点、878 字符。**完成 ≠ 能力。**）

**(e) 定论所需**
要把 (a)(b) 从"无证据变差/单题退化"升级为定论，只需补 **LongCat 臂 10 题**（同候选、同题集）。
该实验成本低（单题 2m25s 量级），但需 Owner 恢复 LongCat 使用授权。

### 3.5 一个不受模型影响的结论

两臂 `full_closure` 均为 **0/10**，且 10 题**全部** `missing=[必需要件法条]`。
⇒ **换模型在这条墙上无效**：真正卡住端到端达标的是"writer 引用要件法条 / 检索面"这条**结构性**问题（执行书 F5/T8），不是模型选型。
**因此在本阶段，把"提升达标率"寄望于换模型是无效杠杆；有效杠杆是 (i) 分解契约加固（§5 P1）、(ii) 要件法条引用链路（§5 P2）。**

---

## 4. 与要求的距离：把要求翻译成可落地的形式

| 目标 | 可达性 | 落地方式 |
|---|---|---|
| 输出质量与模型无关 | ❌ 不可达 | 不要立这个目标 |
| **劣化可被检测、不静默通过、最终 fail-closed** | ✅ 可达 | 完善契约与确定性校验 |
| 失败分布一致 | ⚠️ 部分可达 | 只能压缩"合法但不完整"的静默空间，不能消除质量方差 |

要压缩的，正是 **3.3 的静默空间**：当前"合规但实质不完整"的输出**没有任何守卫**去识别。

---

## 5. 建议动作（按影响力）

**P1（核心）— 让分解器的不完整可被检测**
- 穷尽性契约：把「1 到 8 个」改成"列出该问题蕴含的**全部**独立争点"；
- **确定性完备性检查**：现在一条都没有，加最小完备性判据（如"每个 `required_laws` 主题是否有对应 issue"或以查询主体/请求项做覆盖检查）；
- **修复环**：分解失败/不完整现在是**终态**（`ISSUE_DECOMPOSITION_INVALID`），而 planner 早有"回喂修正"（`71e5f23`）——把同一模式接到分解器上。

**P2（独立线路，不要混做）— 起草段的要件法条引用**
`missing=[必需要件法条]` 在两臂 10/10 全中，属执行书 F5/T8 射程，与分解是两件事。

**不要做** — 把 decomposer 换成"最强模型"的角色分流（`gate5-formal-dev-20260908.md:144` 的历史做法）：那是**承认模型依赖**，与你的要求方向相反，只能当过渡缓解。

**代价**：P1 改 `runtime.py`（**候选文件**）⇒ 必须重采锚定 + 重跑 903 + 重验冻结物。

---

## 6. 口径与陷阱记录（供复算者，避免重踩）

1. `agent_runs.id` 是 **UUID 字符串**，`ORDER BY id` 是字典序、**无意义** → 必须用 `rowid` / `created_at`。
2. **预运行失败（`ISSUE_DECOMPOSITION_INVALID`）不产生 `agent_run` 记录**（handoff §7）
   ⇒ "按位置切 10 条"必然错位（qwen3.6 臂实际只有 9 条）。**必须按会话首条用户消息 ⨯ 冻结题文本匹配**定题号。
   本报告第一版对比表因此标签错位，已修正并复算（差异：争点总数 25→24、缺口 47%→49%）。
3. 换模型后**原闸门结论不适用**；运行时"合法但欠分解"的 run（如 qwen 臂 C01 = 1 个 issue）
   必须判为**非验证样本**，不得计为通过（handoff §12.2 硬判据）。
4. 服务进程缓存 `.env`：改模型必须**重启服务**，并用 `GET /api/admin/stats → llm_model` 确认**进程内**实际模型。

---

## 7. 不得声称 / 未做

- **不声称**任何一臂的质量更好；两臂 `full_closure` 均为 0/10，均属未达标。
- **不声称**本报告已证明"改进有效"——P1 尚未实施。
- 未做：LongCat 臂（Owner 暂停使用）；§5.5 第三方独立验收；6 项待办修复。
- 数据来源：`gate2-run-gate5-dev-run-13-qwen38-sessions.json`、`gate2-run-gate5-dev-modelarm-qwen36-sessions.json`、
  `backend/app.db`（`agent_runs` / `agent_steps` / `messages`）、`model_arm_comparison_20260910.txt`（本报告表格的生成产物）。

---

## 8. 附：LongCat 臂**中止记录（PARTIAL 4/10）**

**状态：Owner 于 2026-09-10 16:18 指示「停止跑，停止使用 longcat」，运行中途终止（已跑 33m37s）。**

- **不得作为整轮结果使用**：本轮 **缺 6 题（C05–C10）**，按纪律标 **PARTIAL**，
  **不得换分母、不得与 qwen 两臂（各 10/10 完整）做完整对照**，**不得据此对 LongCat 下完整判定**。
- 已终止进程：runner（33m37s）+ uvicorn 服务；端口 8001 已释放。
- `.env` 已回到 `qwen3.8-flash`（单 entry）；LongCat 单 entry 配置已撤下。
- **残留数据原样保留，不得删除/改名/覆盖**：`gate2-run-gate5-dev-modelarm-longcat.claim.json`、
  `gate2-run-gate5-dev-modelarm-longcat-checkpoint.json`（**无 `-sessions.json`**，即该轮未收尾）。

**已落盘的部分结果（PARTIAL，仅供参考，不作结论）**：

| 题 | errors | final_chars | completed | 应有争点 | 实测 issues | 覆盖 | backfill |
|---|---|---|---|---|---|---|---|
| C01 | `EVIDENCE_COVERAGE_DEFICIENT` | 0 | ❌ | 4 | 3 | 3 | – |
| C02 | `AGENT_BUDGET_EXCEEDED` | 804 | ❌ | 4 | **8** | 4 | **Y** |
| C03 | — | 726 | ✅ | 5 | 3 | 3 | – |
| C04 | — | 765 | ✅ | 5 | 3 | 3 | – |
| C05 | （run 已创建、**未落盘**，随中止丢失） | — | — | 5 | 3 | 3 | – |

**这份部分数据支持的两条观察（作为"待全量确认"的线索，不是结论）**：

1. **LongCat 同样欠分解** —— C01/C03/C04 均只给 **3 个** issue（应有 4/5/5）。
   ⇒ **欠分解不是 qwen 特有，而是跨模型共有的契约问题**（与 §3.3 的根因判断一致，由第 3 个模型交叉印证）。
   因此 §3.4(b) 中"LongCat 分解明显更强"的表述**应再修正为**：「LongCat 下限略高（3–4 vs qwen 1–2），但同样不稳定」。
2. **同一个分解器在两个方向都失控** —— C02 拆到 **8 个**（提示词上限「1 到 8 个」），扇出检索吃光 `max_steps=16`
   ⇒ `AGENT_BUDGET_EXCEEDED`。**太少 → 静默丢质量；太多 → 爆预算**，两个方向都无守卫。
3. 附带：C02 的 `backfill=Y` ⇒ C01 修复分支在 **LongCat 域第二次被触发**（除 `probe-c01-verify2` 外），且同候选。

**要补齐该臂**：Owner 恢复 LongCat 授权后，用 `--resume` 续跑（claim/checkpoint 已在位，runner 会跳过已记录案例），
或换 run 名重跑全 10 题。
