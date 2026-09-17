# T7 验收报告 —— 集成验收 + 一轮候选验证

日期：2026-09-10 · 候选：脏工作树 + 哈希锚定（HEAD `ebe82e2`，`controller.py` SHA256 `35f8e9c2…`）

> **本报告是 T7 的 DoD 交付物**：产出**可解释、逐题留证的失败矩阵**（执行书 §T7 原文），**不是**宣布质量提升。
> 逐题原始证据见同目录 `t7-per-case-evidence-gate5-dev-run-13-qwen38.md`。

---

## 1. 验收对象与锚定（均已独立复算）

| 项 | 结果 |
|---|---|
| 候选锚定 | 17/17 文件 SHA256 零漂移 ✅ |
| 冻结物 | 16 一致 / 4 知情变化（`writer`/`service`/`runtime`/`controller`）/ 0 缺失 ✅ |
| 备份可还原 | `candidate-post-c01fix.patch` `git apply --reverse --check` 通过 ✅ |
| 全量测试（本次实跑） | **903 passed / 0 failed / 0 errors / 0 skipped**（239.22s，junit 机器可读）✅ |
| 未执行 git 写操作 | 无人 commit / stash / checkout / reset ✅ |
| run-12 残留 | claim + checkpoint 原样保留 ✅ |

---

## 2. 一轮候选验证：运行记录

| 项 | 值 |
|---|---|
| run | `gate5-dev-run-13-qwen38` |
| 模型 | **qwen3.8-flash**（dashscope / 阿里云百炼），单 entry 全链 |
| 题集 | 冻结题 C01–C10（10/10 完整，无缺题） |
| 服务 | `main:app` @ 8001，`AGENT_ENABLED=true`（非付费哨兵验证）、`AGENT_MAX_STEPS=16` |
| 耗时 | 5m40s |
| 两层 judge | `mechanical_pass_count=7`、**`full_closure=0/10`**、`formal_gate_passed=False` |

---

## 3. 逐题失败矩阵

| 题 | 应有争点 | 实测 issues | 检索 tool_calls | 覆盖 | backfill | 终态 | error_codes | 终稿字符 | judge `full_passed` | judge `missing` |
|---|---|---|---|---|---|---|---|---|---|---|
| C01 | 4 | **1** | 1 | 1 | – | completed | — | 404 | False | 劳动合同法:40/43/47/87 |
| C02 | 4 | 4 | 4 | 4 | **Y** | failed | `EVIDENCE_COVERAGE_DEFICIENT` | 0 | False | 劳动法:36/44；劳动争议调解仲裁法:27 |
| C03 | 5 | **3** | 3 | 3 | – | completed | — | 790 | False | 劳动合同法:10 |
| C04 | 5 | **1** | 1 | 1 | – | failed | `UNSUPPORTED_NUMERIC_TOKEN` | 0 | False | 民法典:586/587/588 |
| C05 | 5 | **1** | 2 | 1 | – | completed | — | 331 | False | 民法典:577 |
| C06 | 5 | **3** | 3 | 3 | – | completed | — | 667 | False | 民法典:509/543/577 |
| C07 | 5 | **1** | 2 | 1 | – | completed | — | 556 | False | 民法典:675 |
| C08 | 5 | **1** | 1 | 1 | – | failed | `UNSUPPORTED_NUMERIC_TOKEN` | 0 | False | 民法典:686/692/693/695 |
| C09 | 5 | **2** | 2 | 2 | – | completed | — | 529 | False | 消费者权益保护法:26；民法典:496/497/577 |
| C10 | 4 | **1** | 1 | 1 | – | completed | — | 293 | False | 民法典:577；刑法:266 |

**汇总**：争点 18/47（缺 **62%**）；`mechanical_completed` 7/10；**`full_passed` 0/10**。

---

## 4. 因果链（本报告最重要的一张图）

逐题证据显示：**检索次数 == 分解出的争点数**（扇出 G2 使然）。于是失败面不是并列的，而是**串联**的：

```
分解器契约「issues 为 1 到 8 个」（runtime.py:61，无下限、无穷尽性要求、无完备性校验）
        │
        ├─ 太少（9/10 题，实测 1–3 个 vs 需求 4–5）
        │        ↓
        │   检索 tool_calls 少 → 证据面窄
        │        ↓
        │   终稿必需要件法条 missing（judge: 10/10 题都有 missing）
        │        ↓
        │   full_closure = 0/10
        │
        └─ 太多（LongCat 臂 C02 实测 8 个）
                 ↓
            扇出检索吃光 max_steps=16 → AGENT_BUDGET_EXCEEDED
```

**两个方向都由同一句开放式契约导致，且都没有守卫。** 这把"分解"从"一个环节"升格为**主失败面的上游根因**。

**跨模型确认（LongCat 臂 PARTIAL，4/10）**：`检索次数 == 争点数` 同样成立 —— C01 3/3、C03 3/3、C04 3/3；
C02 过度分解到 **8** 个 → `backfill_retrieval` 触发**两次**后 `stop` / `AGENT_BUDGET_EXCEEDED`（仅 5 次 tool_call 就用尽预算）。
⇒ **该因果链不依赖模型**，属契约层属性。逐题证据见 `t7-per-case-evidence-gate5-dev-modelarm-longcat.md`（PARTIAL 标注）。

### 4.1 主失败面排序（按证据）

| # | 失败面 | 题数 | 机制 | 证据 |
|---|---|---|---|---|
| 1 | **要件法条未引用** | **10/10** | `full_closure` 的直接原因 | judge `missing=[...]` 每题非空 |
| 2 | **分解不足**（上游） | **9/10** | issue 数 < `required_issues` → 检索面窄 | 本报告 §3 |
| 3 | writer 数字不受支持 | 2/10（C04/C08） | 产出数字无输入依据 → verifier 拦下 | `UNSUPPORTED_NUMERIC_TOKEN` |
| 4 | writer 引用不足（**检索面已够**） | 1/10（C02） | 4/4 覆盖 + backfill 已触发，仍被拒 | `EVIDENCE_COVERAGE_DEFICIENT` |
| 5 | 预运行失败 | 0/10（本臂） | — | — |

### 4.2 ⚠️ 一个必须写进验收的度量可信度问题

**7/10 题 `agent_completed=True`，但 `full_passed` = 0/10。**

⇒ `agent_completed` / `has_final` / `final_chars>0` 这组系统自报的成功信号，与真实目标**不相关**，且方向是**误导性的**：
分解越少 → 校验面越窄 → 越容易"完成"（C01 拆 1 个争点、产出 404 字符窄答案、被判 `completed`）。
**任何只用 `agent_completed` 汇报的验收都会把退化读成改进。** 已在 handoff §12.7 记录。

---

## 5. C01 修复的验证结论

| 项 | 结论 |
|---|---|
| 验证载体 | `probe-c01-verify2-20260910`（**LongCat 域**，同候选） |
| 结果 | ✅ **通过**：issues=4、4/4 覆盖、`backfill_retrieval` 指纹在案（`agent_steps` v=12，`CLARIFY_BUDGET_EXHAUSTED_PENDING_RETRIEVAL`） |
| 同候选 pre-fix 对照 | rowid=222：issues 同为 4、clar 同为 2 轮，tool_calls 3→4、未覆盖 1→0、终态 drafting→completed |
| 修正在本轮的独立表现 | **C02**（唯一分解达标的题）：`backfill=Y`、4/4 覆盖 ⇒ 修复分支在 qwen 域同样被触发且生效 |
| 修复**不覆盖**的 | writer 引用轴（C02 检索已够仍失败）、分解契约缺口、`UNSUPPORTED_NUMERIC_TOKEN` |

⇒ **修复本身有效且跨模型可触发**；但它只切断了"尾部 issue 漏检 → 整轮失败"这一条链路，**不改变本轮 0/10 的结果**。

---

## 6. DoD 自检清单（逐项核对，含未达成项）

| 项 | 状态 | 证据 |
|---|---|---|
| `git log` / `status` 已确认 | ✅ | HEAD `ebe82e2`，脏改动在位 |
| 候选备份在位 | ✅ | patch `--reverse --check` 通过 |
| **未执行** commit / stash / checkout / reset | ✅ | — |
| 候选锚定与工作树一致 | ✅ | 17/17 零漂移 |
| 冻结物已复核 | ✅ | 16/4/0 |
| 服务已启动且 `/healthz` 就绪（agent_enabled=true，8001） | ✅ | 已跑过；**当前已按 Owner 指示停止** |
| 全量 `pytest tests/` **本次运行** 0 failed | ✅ | 903/0/0/0 |
| C01 探针已跑 | ✅ | 首次 `ISSUE_DECOMPOSITION_INVALID`（波动），第二次通过 |
| 新 run 未跑 `gate2-run-12` | ✅ | — |
| run-12 claim/checkpoint 原样保留 | ✅ | — |
| 失败/unknown 题全部保留 | ✅ | 0 题 unknown；失败题原样留档 |
| 报告完整无缺题 | ✅ | 本臂 10/10；LongCat 臂单独标 PARTIAL |
| 未宣布生产级质量或统计显著提升 | ✅ | 见 §10 |
| 每个判定有 sessions / DB / 日志可复算 | ✅ | 逐题证据文件 |
| **独立验收者检查已完成或已豁免** | ❌ **未达成** | 只有替代性核查单（已标注"非真正第三方"，handoff §5.5 / §12.6） |

---

## 7. 模型域声明（不可比性）

- 本矩阵在 **qwen3.8-flash 域**取得；handoff §6.6 的判定基线表（run-8/9/10/11）是 **LongCat 域**。
- 依据 `docs/gate5-formal-dev-20260908.md:163`（"qwen 替换只是把失败**换了分布**"）与本次双臂实测（同平台只差小版本号即换掉三个错误码），**两者不得并列对照**。
- 因此：**本报告不与历史基线比较，也不宣称改善或恶化。**

---

## 8. 缺项（不隐藏）

| 缺项 | 原因 | 影响 |
|---|---|---|
| LongCat 域全量 10 题臂 | Owner 于 15:44 授权补跑、16:18 指示停止 ⇒ 仅 4/10（**PARTIAL**，见模型敏感度报告 §8） | 无法给出"LongCat vs qwen"完整对照与"是否变差"的定论 |
| §5.5 第三方独立验收 | 执行书 §222 前置；本次只有替代性核查单 | T7 流程前置未满足 |
| 6 项待办修复 | 均未修（修则须重采锚定）：诊断白名单、F1 注释失真、谓词重复、`service.py` catch-all、§5.5、`master` 历史缺失对象 | 不影响本矩阵可复算性 |

---

## 9. T8 建议（按新证据，**指向被修正**）

执行书对 T8 的表述是「**仅在新证据证明必要时启动真检索修复**」。本轮新证据**不支持**把 T8 指向"真检索"：

- **检索器本身不是瓶颈**：C02 是唯一分解达标的题，检索 **4/4 全部命中**；`retrieve_laws` 无失败、无空命中导致的缺证（`tool_result` 全为 `TOOL_SUCCEEDED`）。
- **真正卡住的是上游的分解契约**：9/10 题因分解不足而检索面窄。**检索面窄是"没问"，不是"问了没给"。**

⇒ **建议把 T8 的目标从"真检索修复"改为"分解契约加固"（P1）**，具体三项：
1. **穷尽性契约**：把「issues 为 1 到 8 个对象」改为"列出该问题蕴含的全部独立争点"；
2. **确定性完备性检查**：当前对"合规但不完整"零守卫（太少静默丢质量；太多爆预算）；
3. **修复环**：分解失败/不完整现为终态（`ISSUE_DECOMPOSITION_INVALID`），而 planner 早有回喂修正（`71e5f23`）——同一模式接上。

**代价**：改动 `runtime.py`（候选文件）⇒ 重采锚定 + 重跑 903 + 重验冻结物。
**验证设计**：改完后同候选、同题集、同模型重跑 10 题，判据用本报告 §3 的表做前后对照（争点缺口 62% 应显著下降），并用 F5/T8 的 writer 引用轴作为**下一堵墙**单独跟踪。

---

## 10. 不得声称

- 不声称质量提升、不声称 `full_closure` 改善（**实为 0/10**）。
- 不声称与 LongCat 基线可比、不声称统计显著。
- 不声称 T7 已全部完成——**§5.5 独立验收与 LongCat 全量臂两项缺**（见 §8）。
- 不声称生产级质量。
