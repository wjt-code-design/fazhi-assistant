# 三票批次 · 双轴 fresh-eyes review（最终版，2026-09-20）

**定点**：`2693745` → `HEAD`（票 H/I/J 三票 + 过程文档，`git log 2693745..HEAD` 共 14 笔）
**方式**：Standards 与 Spec 两轴**各起一个独立 sub-agent**（互不共享上下文），主会话逐条**复核其事实基础**后汇总。
**为什么现在跑**：票面 §9-7 裁定「三票齐了才跑」；H 收口时提前跑过的那次只算临时读数，**本次才是正式的**。

---

## Standards（轴 1）

**（a）硬违规：无。** 逐条核对 `docs/code-review-standard.md` §2 与本仓硬规矩：
- **B1 冻结物**：diff 触及 `gate_exit_registry` / `main` / `retrieval` / `knowledge_service` / `observability` / `request_bootstrap`，均非冻结物（`state_machine` / `prompts` / `gate5_judge` 零触碰）✓
- **`newline=''`**：产品码无写文件；测试 diff 的 `open()` 已带 `newline=""` ✓
- **B5 日志字段**：`observability._ACCOUNT_FIELDS` 新增 `degraded`，已登记（与 `test_log_field_whitelist` 哨兵对齐）✓
- **单一真源**：分水岭 `_CIVIL_WATERSHED = limitation_calc.CIVIL_CODE_EFFECTIVE`（别名不另立）、
  源名归一复用 `retrieval._source_key`、题型判定复用 `quality.multi_incomplete`、
  多选/降级注记文案收敛为 `NOTE_MULTI_INCOMPLETE` / `NOTE_QUOTA` 唯一真源 —— **均无第二份实现** ✓

**（b）基线坏味道（判断题）**：
1. `test_light_exit_gates.py` 与 `test_contract_exit_gates.py` 各自定义了几乎逐字相同的
   `_payloads` / `_contents` / `_put_spy`（Duplicated Code）。⇒ **已整改**（见下）。
2. 轻量出口的六条件写缓存闸与流式 E8 同形状 —— 但 `project-quality-guide-20260914.md` §4.4
   明令"不为两处短小重复建通用框架"，**文档化仓规优先于基线** ⇒ 记为判断、不改。

**正向（符合 §4.4）**：`request_bootstrap.py` 订正误导注释；`retrieval.py` 抽出 `_valid_docs` 共用时效口径；
`_stub_quota_accounting` / `_payloads` 合并重复桩；E15/E16 遵循"每条 content 帧独立格子"铁律。

**事实订正（审查员抓到的）**：新增测试文件是 **4 个**（`test_contract_exit_gates` /
`test_exact_article_lookup_sourcekey` / `test_light_exit_gates` / `test_qa_direct_return_version_guard`）
+ 修改 `_sse_harness.py`，不是 3 个。

---

## Spec（轴 2）

**（b）scope creep：基本无。** E15/E16 新登记行（哨兵按 content 帧条数对账所强制）、
`search_qa` 透传 `law_as_of_basis`（第四道护栏的必要输入）、`_ACCOUNT_FIELDS` 加 `degraded`
（§0「日志新字段须先登记」）、`_sse_harness` 加 `light_buffered` 路由（J-3 端点判据所需）
—— 均在射程内。H-1 写闸扩成 `and not bad and not degraded` 属同一 `if` 块内 H-2 的自然延伸，
未触碰 H-3 禁区（缓存键构造 / `_build_contract_data` / `contract_verify.py`）。

**（a）缺失/部分实现 —— 两条，逐条复核：**

| 项 | 审查员的读法 | 主会话复核 |
|---|---|---|
| **I-5 未落地**（既未补采指纹，也未登记 `PARTIAL`） | 字面成立 | **实质已做、形式被裁掉**：①「写清覆盖比例 + 别按三道护栏叙述」**开票人已在 E2×版本绊线 格写好**（60/166/219 + 「三道要打折」），本票核对过；②`PARTIAL` 不在状态词表（capability-matrix 开篇「状态只有三种」+ 登记表「别造第三套词」）⇒ **Owner 裁定不加**。⇒ **残留**：该护栏的覆盖面**活在取证文本里，不是一个状态值** —— 若 Owner 要"一眼看出它是部分覆盖"，需要先给词表加一个合法状态词（这是一个口径决定，不是代码决定） |
| **H-2「静默空」尾支未受保护** | 如实登记的未覆盖，非硬违例 | ✓（已在 C 组等 Owner 裁：补 error 帧改用户可见行为） |

**（c）看似实现但可能不对 —— 三条，复核后均非缺陷：**
1. **I-2(a) 基准日是推断上界 2026-08-23 而非真实生成日** —— 属实，且已把两条防线写进代码与登记表：
   ① 出处字段 `law_as_of_basis_src="inferred-docstring-8-23"` 随数据走；② **承重点**：护栏只判
   「是否跨分水岭」，而 2026-08-23 与真实生成日（≤ 同一天）**必然同侧** ⇒ 对推断误差不敏感。
   审查员也确认了边界：「若真实生成日跨 `CIVIL_CODE_EFFECTIVE` 才失效（当前不可能）」。
2. **I-6 回退**：仅精确取空时触发、复用唯一归一规则 ⇒ 无错。
3. **J-2 `not res.degraded` 冗余**：与 J-M3 的 SURVIVED 读数一致，已登记为「承归因不承拦截」。

**§9-1 计数**：`grep -c '"GAP-TODO"'` = **1**（仅 `STATUSES` 词表字面量），修掉 7 格，符合 8−7=1 ✓。

---

## 据审查做的整改（本轮）

| # | 改什么 | 依据 |
|---|---|---|
| 1 | `backend/tests/_sse_harness.py` 新增共用件 `payload_frames` / `content_of` / `error_of` / `cache_put_spy`（并把票 H 那条「桩点必须是 `answer_cache.put`」的注记**搬进**共享 docstring，不丢知识） | Standards Duplicated Code |
| 2 | 两个测试文件删掉各自的本地副本，改 import（`as` 别名保持调用点不变） | 同上 |
| 3 | 删除 `test_contract_exit_gates.py` 里**后来又定义了一遍**的 `_put_spy`（收编后与 import 别名冲突，ruff F811 逮住） | 同上 |

**验证**：受影响 4 个测试文件 `26 passed / 1 skipped / 0 failed`；ruff check / format --check rc=0。
过程留痕：删重复代码时**两次**因为切分锚点选错而**脚本自己断言失败、没写盘**（第二次才找对锚点）
—— 这两次失败都是安全的（先断言、后写盘），但它们再次证明"盲改写"在本仓必须配断言。

---

## 留给 Owner（本审查不能替 Owner 决定的事）

1. **登记表要不要一个"部分覆盖"的状态词**（I-5 的残留）：现状是覆盖比例活在取证文本里。
2. **H-2「静默空」尾支**要不要补 error 帧（改用户可见行为）。
3. **R15 四项 P1**（另一会话产出，动 `agent/limitation_calc.py` + `main.py`）要不要立项 ——
   **与已派发的 T11 抢 live 树，也与本批改过的 `main.py` 相邻 ⇒ 必须排在本批之后**。
