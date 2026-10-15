# 深度代码审查报告（9 提交 + 未跟踪文件）

日期：2026-09-15 ｜ 审查者：助手（**实现者自查**，非独立第三方复核）
范围：`8d21a9d..f72a655`（9 提交 / 22 文件 / +1935 −42）+ **4 个未跟踪但属本次工作的文件**
方法：**5 轴并行独立子 agent**（正确性 / 安全 / 性能 / 可维护性 / 测试可信度）+ **我亲自复现全部 🔴 与关键 🟡**
状态：**只审不改**（按用户确认）——本报告不含任何代码修改

---

## 0. 方法与独立性声明

| 项 | 说明 |
|---|---|
| 独立性 | 5 个子 agent 各自**独立上下文**读代码，**未被告知我的结论**（避免自我合理化） |
| 我做了什么 | 亲自复现全部 🔴 + 关键 🟡（脚本 `dispatch-output/quality-review-verify-20260915/verify_findings.py`） |
| **我推翻了 1 条子 agent 结论** | 见 §3 的「不予采纳」——说明未盲信转述 |
| 报告性质 | **实现者自查**（代码由我编写）。**不构成独立复核**，更不构成法律质量认证 |
| 性能 | 子 agent 实测（脚本 `dispatch-output/quality-review-perf-20260915/bench.py`），数字见 §4 |

---

## 1. 🔴 Blocker（2 条，均已由我复现）

### B1｜`backend/agent/writer.py` 续引展开**只处理 2 条**（多连丢失）

**证据（我实测）**：

```
《民法典》第577条、第578条              -> [577, 578]   ✓
《民法典》第577条、第578条、第579条      -> [577, 578]   ✗ 579 丢失
《民法典》第577条、第578条、…、第580条   -> [577, 578]   ✗ 579/580 全丢
```

**根因**：`_CONTINUATION_CITATION_RE` 只匹配「《X法》A条 + 分隔符 + B条」**一对**，`finditer` 不重叠；
第 3 条起没有 `《》` 前缀 → 不匹配任何 pattern → 落空。

**为什么是 blocker（双向危害）**：
1. **幻觉漏检**：模型编造的第 3 条**既不进核验集、也不触发 `NON_CANONICAL`**（该判定已被我删掉续引分支）
   → 引用防线出现**盲区**，属 §4.2「引用关联到支持它的论断」的安全边界失效；
2. **误判**：真实存在且已绑定的第 3 条 → 被判 `UNSUPPORTED_CITATION` / `FABRICATED_CITATION`。

**为何我此前没发现**：量化采样里的 `continuation_form` 样本恰好都是**2 条**续引（`2→0` 的复测也基于此）
→ **我的验证覆盖不到 3 连**。这是「样本恰好覆盖不到缺陷」的典型。

**复现**：`python -c "from agent.writer import canonical_citations; print(canonical_citations('《民法典》第五百七十七条、第五百七十八条、第五百七十九条'))"`
**建议（不强制）**：把续引解析改为**逐条推进**（匹配一次后续接下一段）或放宽正则允许「、第X条」链式重复；
补 3 连/4 连单测（**该测试应先红**）。

---

### B2｜含密钥的 `.env` 备份**未被 `.gitignore` 覆盖**

**证据（我实测）**：

```
git check-ignore -v dispatch-output/config-backups-20260915/env.before-q38f-removal.bak
→ 返回码 1（= 未被忽略）；git status → "?? dispatch-output/config-backups-20260915/..."
该文件含 23 个键（ADMIN_PASSWORD / JWT_SECRET / LLM_API_KEY / SILICONFLOW_API_KEY / ZHIPUAI_API_KEY …）
```

**风险**：`.gitignore` 只匹配 `.env`（不含 `.bak`）→ **一次 `git add -A` 就会把明文密钥提交进版本库**
（且这是"备份"语义，容易被当成无害文件长期留在树里）。

**复现**：`git check-ignore -v <bak 路径>`（返回 1 即未忽略）
**建议**：① 把 `*.bak` / `*.before-*` 纳入 `.gitignore`（或该备份目录整体忽略）；
② 备份改用不含密钥的形式（只备份键名与结构差异）。

---

## 2. 🟡 Suggestion（6 条）

| # | 位置 | 问题 | 证据/复现 |
|---|---|---|---|
| **S1** | `backend/main.py` `admin_llm_disable` | `bool(body.get("disabled", True))`：**字符串 `"false"` 判为 True** → 前端传 `"false"` 会**误禁用**；且**默认 True**——只传 `{"key":...}` 即禁用 | 我实测：`bool("false")=True`、`bool("False")=True`、`bool("0")=True` |
| **S2** | `backend/main.py:2337,2358` | 新端点用**裸 `body: dict`**，绕过 Pydantic 校验（同文件 `admin_llm_switch` 用 `LlmSwitchIn`）→ **安全轴 + 气味轴双轴命中**（Primitive Obsession） | 与 `schemas.py:176` 既有惯例相悖 |
| **S3** | `dispatch-output/agent-quality-20260911/test_budget_guard.py` | `backend/pyproject.toml` 规定 `testpaths = ["tests"]` → **该文件的 9 条守卫测试不在 CI 收集范围**（`dispatch-output/` 下共 5 个 `test_*.py` 全部如此） | 我实测 `testpaths=["tests"]` |
| **S4** | `backend/agent/runtime.py`（新换模型路径调用既有 `mark_depleted`） | **爆破半径放大**：若某请求体缺陷让**所有**模型返回永久 4xx（且不含 schema 拒绝 marker）→ 全模型被标 depleted → **本进程后续所有请求立即 `QuotaExhausted`** | `mark_depleted` 仅内存态（docstring："重启即恢复默认"）→ 严重度降为 🟡（重启自愈） |
| **S5** | `dispatch-output/agent-quality-20260911/budget_guard.py` `reserve()` | 预约失败（预算/次数/已失败模型/未审批）时**账本零记录**——既无 `reserved` 也无拒绝原因 | 我复现：第二次调用抛 `RuntimeError: Model previously failed`，账本无对应条目 |
| **S6** | `backend/agent/schemas.py`（claim `text` 仅 `min_length=1`） | **无 `max_length`** → 实测 1M 字符时 `render_issue` **1177 ms**（>1s 阈值）。真实 claim <2K 字符 → <2ms，属**理论风险** | 子 agent 基准数字（§4） |

**关于 S3 的诚实更正**：我在进度汇报中写过"守卫测试 9 条全绿"——**该陈述为真但需限定**：
它们只在**显式指定路径**时运行，**不在 `testpaths` 门禁内**。今后引用须写"显式运行 9 passed，**未纳入 CI 门禁**"。

---

## 3. 💭 Nit（4 条）与「不予采纳」

| # | 位置 | 内容 |
|---|---|---|
| N1 | `backend/agent/writer.py` `citation_noncanonical_shape` | `unclassified` 分支**生产不可达**（唯一调用点已保证 `has_noncanonical_citation` 为真，而该函数现只判缺书名号）→ 死分支（我引入；仅单测直接调用会触发） |
| N2 | `backend/llm_registry.py` `promote` | `priority = min(peers)-1` 重复调用会**无界变负**（排序仍正确，仅数值发散、可读性差） |
| N3 | `backend/agent/writer.py` `numeric_tokens` | `occupied = [False]*len(text)`：1M 字符时 **8MB vs bytearray 1MB**（8×），但**时间差仅 12%** → 真实长度下无影响 |
| N4 | `backend/agent/writer.py` | **Divergent Change**：本窗口因 4 个无关因由被改（引用解析 331–447 / 形态分类 460–493 / 数字校验 540–626 / 编排 648–870） |

**不予采纳（我复现后推翻）**：

| 子 agent 结论 | 我的复现结果 |
|---|---|
| 🟡 `budget_guard.guarded_send` 中 `ticket` 未绑定 → `UnboundLocalError` | ❌ **不成立**：`ticket = self.reserve(request)` 位于 **`try` 之外**，`reserve` 抛异常不会进入 `except`，实际抛出的是原始 `RuntimeError`。**但**由此发现 S5（账本零记录） |

---

## 4. 性能专项（实测数字，用户特别要求）

**基准脚本**：`dispatch-output/quality-review-perf-20260915/bench.py`（中位数，ms）

| 函数/路径 | 1K 字符 | 10K | 100K |
|---|---|---|---|
| `canonical_citations` | 0.82 | 7.80 | 85.8 |
| `has_noncanonical_citation` | 0.15 | 1.29 | 13.4 |
| `numeric_tokens` | 0.69 | 6.65 | 61.8 |

- **线性、无超线性**：10K/1K = 9.5×、100K/10K = 11.0×（理想 ≈10×）→ 我担心的「多次全扫描」**只是常数倍（5 遍 finditer）**，非非线性。
- **ReDoS 实测安全**：恶意输入（`第零条零 × 2万` / `第一千条×2万` / `、第一千条×5000`）最坏 **0.09–0.73 ms**；`canonical_citations` 最坏 18.1 ms —— **无灾难回溯**（分隔符类与尾随「第X条」无重叠字符）。
- **超长 claim**：10K → 12ms；100K → 115ms；**1M → 1177ms**（S6）。
- **`include_usage` 全链注入**：启动期一次 O(模型数) 合并，**零逐请求开销**。

**结论**：**未观察到真实文本长度下的显著开销**。唯一建议落地的防御是给 claim `text` 加 `max_length`（S6）。

---

## 5. 各轴终态

| 轴 | 🔴 | 🟡 | 💭 | 备注 |
|---|---|---|---|---|
| 正确性 | **1**（B1） | 2（S4/S5） | 2（N2/N3 相关） | 换模型终止性、`pick(exclude)` 语义、锁一致性**已核实无问题** |
| 安全 | **1**（B2） | 2（S1/S2） | 1 | 日志无文本泄漏 ✓、`serve.py` JWT 无硬编码 ✓、`backend/.env` 已被忽略 ✓ |
| 性能 | 0 | 1（S6） | 2 | 未观察真实瓶颈；ReDoS 安全 |
| 可维护性 | 0 | 2（S2 复用/N4） | 2（N1/N2） | `_admin_disabled` 单一真源 ✓、`promote` 非 Speculative ✓ |
| 测试可信度 | 0 | 1（S3） | 0 | 期望独立性与断言强度总体良好；无真实网络/随机 → 无 flaky 隐患 |

**合计：2 🔴 / 6 🟡 / 4 💭（去重后）**

---

## 6. 已知限制（诚实标注）

1. **性质**：实现者自查。**无第三方独立复核**；不构成法律质量认证（§4.2）。
2. **覆盖边界**：审查基于**静态阅读 + 定点复现**，未做全量动态fuzzing；`slow` 标记测试未跑。
3. **B1 的重要性被低估的原因已记录**：量化样本恰好只含 2 连续引 → **验证的样本分布决定了缺陷可见性**；这说明"12 次采样"对**结构性缺陷**（非频率型）覆盖不足。
4. **未审**：`docs/`、`dispatch-output/` 下的证据与文档（非代码）；其他助手的 3 个 docs 文件。
5. **S3 影响面**：修复需在 `pyproject.toml` 或测试位置二选一，属流程决策（可能影响 CI 时长）。

---

# 附录：对抗式审查（自我攻击本报告结论）

日期：2026-09-15 晚 ｜ 目标：**推翻或修正**上文本报告的全部结论（不是复述）

## A. 攻击结果总表

| 被攻结论 | 攻击手段 | 结果 |
|---|---|---|
| **B1**（3+ 连丢失） | ①独立正则扫 **116 个真实 DB / 1034 行文本** 统计链长分布 | ✅ **成立且证据升级**：链长 ≥3 出现 **16 次**；「、第X条」形态 **32 次** → **真实可达**（原报告只证机制、未证可达） |
| **B2**（.bak 未忽略） | ①`git check-ignore` ②查非示例 git hooks ③查 `.gitignore` 全文 ④查 `backups/` 类规则 | ✅ **成立**：`check-ignore` 返回 1、**无 hooks**（无自动拦截）、`.gitignore` 的 `backups/` **不匹配** `config-backups-*/`。**限定**：需人工 `git add -A` 触发 |
| **S3**（守卫测试脱离门禁） | 读 `.github/workflows/ci.yml` | ⚠️ **成立但原报告低估** → 见 §B 升级 |
| **S1**（`bool("false")`） | 实测 7 个取值 | ✅ 成立 |
| **S4/S5/S6** | 静态复核 | ✅ 成立（S4 内存态重启自愈、S6 属理论风险，均已如实标注） |
| **性能结论**（无真实瓶颈 / ReDoS 安全） | 查基准脚本输入是否**真触发**续引路径 | ✅ **成立**：`bench.py` 真实感文本含 `第577、578、579条`**3 连** → 续引路径确被压测 |
| **我的推翻**（`UnboundLocalError` 不成立） | 打印 `budget_guard.py:135-145` 原始源码 | ✅ **我的推翻可靠**：`ticket = self.reserve(request)` 在 **137 行、`try`（138）之外** → 异常不进 except |
| N1–N4（nit） | 静态复核 | ✅ 成立（N1 死分支、N3 内存 8× 时间差 12% 均已注明量级） |

## B. 攻击带出的**新发现**（原报告漏报）

### 🟡 S3-升级｜不止测试——**验收宿主 3 文件脱离 CI 的「四道门禁」**

`ci.yml` 的 backend job **全部 `working-directory: backend`**：
`ruff check .` / `ruff format --check .` / `mypy .` / `pytest --cov=. --cov-fail-under=70`。
`backend/pyproject.toml` 又规定 `testpaths = ["tests"]`。

⇒ `dispatch-output/agent-quality-20260911/{budget_guard.py, serve.py, test_budget_guard.py}`
**不在 lint、不在 format、不在 type、不在 test 的任何一道门禁内**。
原报告只写了"9 条守卫测试脱离 CI"，**低估了范围**。

### 🟡 N5（新）｜我新增的守卫代码**实际违反仓库 lint**

对该目录跑静态三项（首次）：

```
ruff check      → budget_guard.py:17 FURB157 Verbose expression in `Decimal` constructor（我在新增 PRICING 表里沿用 Decimal("2") 风格）
ruff format --check → budget_guard.py:2 "File would be reformatted"
mypy            → Success（2 files）
```

**归因诚实说明**：`FURB157` 与格式问题**部分在原文件里就存在**（该文件从未被 lint），
但**我在新增行里沿用了同款写法** → 属"新代码延续未受检风格"。
⇒ 这是 S3 的**具体后果**：不是理论风险，**已经发生了**。

## C. 方法论教训（写给我自己）

1. **职责分离有代价**：性能 agent 用的正是 B1 的触发输入（3 连），却**只测耗时、未验正确性**
   → 同一输入跨轴交叉检查是缺口。**下轮改进**：性能轴要求"对每个压测输入同时报正确性断言"。
2. **样本分布决定缺陷可见性**（已在正文 §1 记录）：量化样本恰好只含 2 连 → 结构性缺陷不可见。
   **通用做法**：结构性（解析/格式化类）改动应做**形态枚举**（2 连/3 连/4 连/嵌套/异常）而非频率采样。
3. **可达性可用零成本独立证据**：116 个历史 DB 的终稿文本足以回答"模型是否会这样写"，
   **不必花付费探针**——先找既有证据，再考虑付费。

## D. 对抗后**仍未**被证伪、但证据类型需限定的项

| 项 | 限定 |
|---|---|
| B1 可达性 | 证据来自"全部文本类型"（含 state_json 与 assistant 消息），**未逐条确认那 16 次都发生在 writer 的 claim 文本里** → 标注为**间接证据**（方向一致，量级足够触发重视） |
| B2 风险 | 触发需人工 `git add -A`；仓库当前无自动化提交流程 → 属**潜在**风险而非已发生 |
| S4 爆破半径 | 仅内存态（重启自愈），**未构造端到端复现**（需 mock 全模型永久 4xx）→ 标注为**推理结论**，非实测 |

## E. 修正后的结论（替换正文汇总）

**2 🔴 / 8 🟡（含新增 S3-升级、N5）/ 4 💭**，其中：
- 🔴 两条**均经独立验证**（B1 机制+可达性；B2 忽略规则+hooks+文件内容）；
- **最该先修**：B2（不可逆、成本极低，`.gitignore` 一行）→ 次之 B1（引用防线盲区 + 16 次真实可达）。

