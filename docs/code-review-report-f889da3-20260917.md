# 代码审查报告：f889da3（基准 f4d908c）

- **日期**：2026-09-17
- **范围**：`git diff f4d908c...HEAD`，区间内唯一提交 `f889da3 fix(prompts): SYSTEM_BASE 编号错序与拒答指令冲突裁决，Planner ask_user 三段摇摆消除`
- **变更**：`backend/prompts.py`（+33/-32，提示词字符串）、`backend/agent/runtime.py`（+2/-1，Planner ask_user 边界一句）
- **方式**：双轴并行审查（Standards 轴 + Spec 轴），两轴独立子代理产出后经主审逐条复核（关键主张均亲自验证）
- **规格来源**：`docs/prompt-architecture-audit-20260917.md` §六 S2/S3/S4 + §7.1 短期建议 #1-#5
- **规范来源**：`docs/code-review-standard.md` + `CONTRIBUTING.md`

---

## Standards（规范轴）

### 通过项
| 检查 | 结果 | 证据 |
|---|---|---|
| ruff check（限改动文件） | ✅ exit 0 | `./venv/Scripts/python.exe -m ruff check prompts.py agent/runtime.py` |
| ruff format --check（限改动文件） | ✅ exit 0 | 2 files already formatted（既有的 2 处失败在 test 文件，不属本次改动，勿归因） |
| mypy（限改动文件） | ✅ exit 0 | no issues found in 2 source files |
| 编译/导入 | ✅ | `import prompts; import agent.runtime` OK，SYSTEM_BASE 1084 字符 |
| 契约测试 | ✅ 9 passed | test_prompts.py + test_agent_prompt_contracts.py，全新 basetemp |
| SYSTEM_BASE 终态 | ✅ | 编号严格 1..9 连续，每条 `\n` 分隔正确（prompts.py:15-36） |
| LEAK_FRAGMENTS 同源 | ✅ | 剩余 3 片段均仍存在于 SYSTEM_BASE |
| 夹带/密钥/调试残留 | ✅ 无 | 仅引号样式（中文引号 `\u201c\u201d` 约定一致）与注释更新 |

### 发现项
**P1（本次提交引入）｜prompts.py:27-28 条号错例两侧相同，教学示例失效**

```text
根因：本次用 Write 工具重排提示词时，把刻意设计的错例当笔误"改正"了。
现状：如把『第一百零三条』写成『第一百零三条』——两侧一致，无法演示"错位"。
旧版（f4d908c）：如把『第一百零三条』写成『第一百零十三条』——故意错例（103 误作 1013）。
修复（一行，prompts.py:28）：『第一百零三条』→『第一百零十三条』，第 27 行正确形保持不变。
验证：改后跑 test_prompts.py + test_agent_prompt_contracts.py；
      并人工确认 SYSTEM_BASE 中该句两侧不再相同。
```

**P2（流程）｜prompts.py 属 B1 冻结物，须补豁免留痕**

`docs/code-review-standard.md:80`：B1 阻断条目含 `prompts`，判定方式为"冻结物哈希复算，漂移非零"。本次改动使 prompts.py 相对候选锚定态漂移。按 §2 豁免条款，Owner 可豁免但**必须在决策留痕写明理由与影响**。本次授权链完整（审计 → grilling 裁决 → 用户明示"继续执行任务"），且 Agent Path 零流量、提示词改动不触线上；缺的只是把豁免记录落到决策留痕文件（建议记入 `docs/execution-plan-entity-precision-20260917.md`，一行即可）。

**P2（测试缺口）｜四类新内容无断言**

1. SYSTEM_BASE 编号连续性（1..9 无重复无跳号）；
2. "严禁断言"已从 LEAK_FRAGMENTS 移除（现有 `test_leak_fragments_are_in_system_base` 只遍历剩余片段，对移除不可见）；
3. OUTPUT_FORMAT_RULE 不再含字面 `$` 与 `**`；
4. runtime.py ask_user 形态边界句的存在性。
均为低成本子串断言，可防回归（对应审计 §7.2 #9 的最小先行版）。

---

## Spec（规格轴）

### 7.1 五项建议逐项对照
| # | 建议 | 状态 | 证据 |
|---|---|---|---|
| 1 | 修编号错序 | ✓ | prompts.py 编号 1..9 连续 |
| 2 | 删第7条末段与第9条重复 | ✓ | 旧 7/9 合并为新第 9 条 |
| 3 | 裁决拒答冲突 | ✓ | 第1条改"如实说明哪些部分缺乏依据"；第9条保留操作性禁令；"严禁断言/严禁拒答"删除，LEAK 同步 |
| 4 | 修 OUTPUT_FORMAT_RULE 自指 | ✓ | `$`/`**` 改描述式禁令（"美元符号""星号"） |
| 5 | 修 Planner ask_user 三段摇摆 | ✓ | runtime.py 统一为"独立 kind 可用、作 tool_name 被拒、仅补关键事实、最多两轮" |

**编号 1..9 vs 规格"1..10"的偏差判定**：规格内部矛盾，非实现偏差——§7.1 #1 写"→1..10"时未扣除 #2 要求的删除（7/9 合并少一条），先删重复再顺排必为 1..9。实现忠实于"顺排去重"意图。

### 事实性验证（Spec 轴主张，主审已复核）
- runtime.py 新文案"ask_user 作 tool_name 会被校验器直接拒绝"：**属实**（planner.py:103 抛 PlannerParseError；schemas.py:172 AskUserDecision 为独立 kind）。
- LEAK_FRAGMENTS 移除"严禁断言"安全性：检测逻辑（eval_redteam.py:61）是对输出做无条件子串匹配，但 test_prompts.py:30 要求片段必须 ⊆ SYSTEM_BASE——该句已随重写删除，不移除反而测试失败；且短语在提示词中已无来源，**不放大漏报**。
- 第1条"如实说明缺乏依据" vs 第9条"不输出未检索到/未提供…"残余张力：**可控**——第9条禁的是检索覆盖措辞，模型有合法表达路径（如"就 XX 部分尚缺乏条文依据"）。

### 残余缺口（旧状态遗留，非本次引入，列为后续项）
1. prompts.py:74 OUTPUT_FORMAT_RULE 仍写出字面 `¥`（`$` 已描述化，`¥` 漏改）——自指悖论未修净，severity 低。
2. prompts.py:20（第3条）与 :33（第9条）提示词正文含 `**…**` 星号强调，与 OUTPUT_FORMAT_RULE 星号禁令存在示范张力——severity 低~中，建议下批提示词清理时一并处理（牵涉 baseline markdown_star 34.61% 的归因）。

### 范围完整性
S1（采样参数）/S5（版本管理）/S6（集中注册）属 §7.2 中期，本提交未越权处理。✓

---

## 结论

**有条件通过**。提交忠实于规格（5/5 落地、裁决方向与 grilling 结论一致、无越权），门禁绿、无夹带；但存在 1 项本次引入的 P1（错例失效，一行可修）与 1 项流程留痕（B1 豁免）。

**建议动作（按优先级）**：
1. 【P1，一行】修 prompts.py:28 错例 → 新提交（不 amend）。
2. 【P2，留痕】B1 豁免理由记入 `docs/execution-plan-entity-precision-20260917.md`。
3. 【P2，防回归】补 4 类最小契约断言。
4. 【遗留，下批】`¥` 描述化 + 提示词正文星号清理（与 markdown_star 基线复测合并考虑）。

---

## 修复记录（2026-09-17 追加）

- 建议 1 已执行：`f5900b5`（3 files, +48/-1）——P1 错例一行修复 + 4 类契约断言（同提交）。
- 建议 2 已执行：B1 豁免留痕已记入 `docs/execution-plan-entity-precision-20260917.md` §8
  （授权链、影响与义务：下次候选冻结前重算哈希重锚定，完成前不开付费轮）。
- 建议 3 已执行：即 f5900b5 的 4 断言。watch-it-fail 证据：
  `dispatch-output/rev-watchitfail-20260917/`——四断言对缺陷版 f4d908c 全红且为正确原因红；
  其中编号断言额外实证旧版第 10 条因缺 `\n` 拼接在行内不可见（旧编号正则只提得
  [1..7,9,8]），错序比审计记录的"1..6,7,9,8,10"更严重。
- 验证：ruff check / format --check / mypy 限改动文件全绿；契约测试 13 passed（全新 basetemp）。
  顺带实测：基线记录的 2 处既有 format 失败（test_agent_prompt_contracts.py:102、
  test_agent_verifier.py:443）已消失，工作区基线记忆已同步更新。
- 建议 4（¥ 描述化 + 星号清理）：未动，留待与 markdown_star 基线复测合并考虑。
