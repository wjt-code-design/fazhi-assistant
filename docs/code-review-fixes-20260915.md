# 代码审查修复报告（B1/B2/S1/S2/N5）

日期：2026-09-15 ｜ 依据：`docs/code-review-report-20260915.md`（含对抗审查附录）
原则：**每项先失败测试/watch-it-fail，再修复，再验证**；一项一提交

## 一、修复清单

| 项 | 级别 | 提交 | 状态 |
|---|---|---|---|
| **B2 + B2b** 密钥备份 / SQLite WAL 未忽略 | 🔴 | `b6594e6` | ✅ |
| **B1** 续引链 3+ 丢失（引用防线盲区） | 🔴 | `c6278c8` | ✅ |
| **S1 + S2** 端点入参绕过 Pydantic / `bool("false")` 误禁用 | 🟡 | `192ae66` | ✅ |
| **N5** 守卫代码违反 ruff（脱离门禁） | 🟡 | 未跟踪目录（无需提交） | ✅ |
| **S3** CI 门禁范围 | 🟡 | — | ⏸ **流程决策，待你拍板** |

## 二、逐项证据

### B2 + B2b（`.gitignore`）

- **问题**：`config-backups-20260915/env.before-q38f-removal.bak` 含 **23 个密钥键**，
  `git check-ignore` 返回 **1（未忽略）**；仓库**无 git hooks**（无自动拦截）→ 一次 `git add -A` 即泄密。
- **修复**：`dispatch-output/config-backups-*/` + `*.bak` + `*.sqlite-shm/-wal`、`*.db-shm/-wal`（B2b 同族）。
- **对抗性检查**：`*.before-*` **不加**——实测会误伤 3 个**被有意跟踪**的历史快照
  （`agent-quality-h3-20260912/*.before-h3`），已写入注释防后人踩坑。
- **验证**：4 个目标文件 `check-ignore` 全 **rc=0**；h3 目录剩余未跟踪项 **清零**；
  `.gitignore` 纯 CRLF（93 CRLF / 0 孤立 LF）。

### B1（`backend/agent/writer.py`）

- **问题**：3 连以上续引只提取前 2 条（实测 `第577、578、579条` → 只得 {577,578}）。
  **双向危害**：① 编造的后续条号**既不进核验集也不判非规范**（引用防线盲区）；
  ② 真实且已绑定的后续条号被判 `UNSUPPORTED_CITATION`/`FABRICATED_CITATION`。
- **可达性**：独立正则扫 **116 个历史 DB / 1034 行文本** → 链长 ≥3 出现 **16 次**。
- **修复**：`_ARTICLE_PATTERN`（条号模式唯一真源）+ `_CHAIN_TAIL_RE`；
  `canonical_citations` 改为「命名引用 + 贪心吃链」（条号归同一法名）；
  `numeric_tokens` 占位同步吃链；删除 A 项遗留的死代码 `_ARTICLE_NUMBER_RE`。
- **终止性预检**（loop-termination-preflight）：终止条件 = `pos` 严格单调递增（每轮 ≥1 条号）、
  上界 `len(text)`；无 IO/无重试 → 已写入 docstring。
- **watch-it-fail**：新增 7 条参数化用例，**修复前 5 failed / 2 passed**（失败原因全对）
  → 修复后 **17 passed**。
- **验证**：全量门禁 **1061 passed / 0 failed / 78.91% / exit 0**。

### S1 + S2（`backend/main.py` + `backend/schemas.py`）

- **问题**：`disabled = bool(body.get("disabled", True))` —— `bool("false") is True`
  → 字符串 `"false"`/`"0"` **误禁用**；且默认 True（只传 key 就静默禁用）；
  两处端点用裸 `body: dict` 绕过 Pydantic（与同文件 `LlmSwitchIn`/`LlmQuotaIn` 惯例相悖）。
- **修复**：`LlmPromoteIn`（key 长度 1–64）/ `LlmDisableIn`（key + `disabled: StrictBool` **必填**）；
  端点改用 schema；顺带修 import 排序（ruff I001）。
- **测试**：哑值 `"false"/"0"/"true"/1/0` **全部 422**；缺 `disabled` 422；
  `inspect.signature` 断言端点入参**就是** Pydantic schema（防回退）。
- **验证**：全量门禁 **1063 passed / 0 failed / 79.01% / exit 0**。

### N5（`dispatch-output/agent-quality-20260911/`）

- **问题**：该目录 3 文件**不在 CI 四道门禁内**（`ci.yml` 全部 `working-directory: backend`），
  实测 `ruff check` 报 **18 项**（FURB157 ×17 + RUF100 ×1）、`ruff format --check` 不通过。
- **修复**：`ruff check --fix` + `ruff format`（18 → 0）。
- **⚠️ 高危自动修复已核验**：ruff 只把**整数值**改为 int 字面量（`Decimal(2/12/36)`），
  **浮点字符串原样保留**（`Decimal("0.8")/Decimal("2.7")`）→ **无浮点伪影**；
  金额语义逐项复核（reserve=2/26.16、in=0.8/12、out=2.7/36）**未变**。
- **验证**：守卫 9 条 `test_budget_guard.py` **9 passed**；mypy `Success`。

## 三、过程中额外发现并处理

| # | 发现 | 处理 |
|---|---|---|
| 1 | **Git 对象库缺失阻断提交**：`git commit` 报 `invalid object 01fa7f9b… for test_agent_prompt_contracts.py`（§1/§9 项 5 已记录的问题） | 写**有界非破坏修复脚本**（`repair_missing_blobs.py`）：仅 `git hash-object -w` 把工作区内容写回对象库（**校验 sha 一致才写，绝不伪造**；不删对象/不重写历史/不 gc）→ 写回 1 个对象后 `write-tree` rc=0，提交成功 |
| 2 | 另一助手在我工作期间提交 `f0f9cc9`（前端修复） | **未触碰**其改动；我的提交叠加其上 |
| 3 | `slow` 标记测试在**多文件同进程**时 31 个 setup ERROR（单跑 33 passed；CI 口径 `-m "not slow"` 为 113 passed） | 判定**与本次改动无关**（既有测试基建缺陷，CI 已排除 slow）→ 记录待办 |
| 4 | `main.py` / `.gitignore` 为 CRLF，heredoc 的 LF 模式不匹配（踩坑 2 次） | 改为**行级拼接 + 显式 CRLF**、写后校验"孤立 LF=0" |

## 四、S3 待你拍板（本轮未动）

`ci.yml` 的 backend job 全部 `working-directory: backend`，`pyproject.toml` 又规定
`testpaths = ["tests"]` ⇒ 验收宿主 3 文件（`budget_guard.py`/`serve.py`/`test_budget_guard.py`）
**不在 lint/format/type/test 任何一道门禁内**（N5 的具体后果已发生）。三个选项：

1. **移测试进 `backend/tests/`**（导入需加路径处理）——收益最高，但触及评测资产布局；
2. **CI 增加一步**（如 `ruff check ../dispatch-output`）——改动 CI，影响面可见但会拉长 CI；
3. **保持现状 + 文档标注**（每次改动手动跑静态三项）——零风险但依赖人自觉。

## 五、汇总

- **提交**：`b6594e6`（B2/B2b）→ `c6278c8`（B1）→ `192ae66`（S1/S2）；N5 在未跟踪目录。
- **门禁**：最终候选 **1063 passed / 18 deselected / 0 failed / 79.01% / exit 0**；
  静态 ruff check/format + mypy **全绿**。
- **未做**：S3（待拍板）；审查报告中的 💭 nit（N1 死分支 `unclassified`、N2 priority 无界负、
  N3 occupied 内存 8×、N4 Divergent Change）**未修**（低优先，且 N4 属重构范畴）。

---

# 附录：show-your-work 证据审计（对本报告的修复声明）

对"修复完成"的每一项过**证据五连问**，发现 **1 处实质缺口（已补）** 与 **2 处口径不精确（已更正）**。

## 一、实质缺口（已补证）

| 声明 | 原证据 | 缺口 | 补证动作 |
|---|---|---|---|
| S1/S2「哑值**全部 422**」 | 仅 **schema 层** `pytest.raises(ValidationError)` | 🚨 **422 是 HTTP 状态码**，schema 拒绝 → 422 只是**框架映射推断**，未做 HTTP 级实测 | 新增 `verify_s12_http.py`：TestClient + 覆盖 `require_admin`，**7 个非法体全 422**、合法体 404（证明未误杀）→ **升级为端到端实测** |

## 二、口径更正（原表述不精确）

| 原表述 | 更正后 |
|---|---|
| B1「修复后 **17 passed**」 | 精确为：`-k "expands_arbitrary_chain_length or continuation or noncanonical or citation"` 的**过滤子集** 17 passed；**同提交的全量门禁为 1061 passed**（两口径不可混比） |
| 「最终门禁 1063 passed」（S1/S2 后） | 该门禁**不覆盖** `dispatch-output/agent-quality-20260911/` 的 3 个文件（在 `pyproject.toml` 的 `testpaths=["tests"]` 之外）；守卫 9 条为**另测**，未计入 1063 |

## 三、逐项五连问结论

| 声明 | ①怎么来的 | ②可复现 | ③亲眼红过 | ④期望独立 | ⑤已知限制 |
|---|---|---|---|---|---|
| B1 修复 | `watch-it-fail` 实跑：**修复前 5 failed / 2 passed** → 修复后 17 passed | ✅ `pytest -k ...` | ✅ **是**（先红后绿，失败原因全对） | ✅ 期望由契约语义给出（1/2 连锚点 + 3/4 连应全取），非复算实现 | 新增 7 例中 2 例是**回归锚点**（修复前就通过），不构成新功能证据；已标注 |
| B2 修复 | `git check-ignore` rc=0；23 个密钥键为**键名统计**（不输出值） | ✅ 一条命令 | —（配置类，无红点） | ✅ 独立于实现（git 自身判定） | 触发条件需人工 `git add -A`；`*.before-*` 已排除以免误伤 |
| S1/S2 修复 | **HTTP 级实测**（本轮补）+ schema 测试 | ✅ `verify_s12_http.py` | ✅ schema 测试在实现前就失败（`LlmDisableIn` 不存在） | ✅ 期望来自"字符串不是布尔"这一确定性事实 | 仅覆盖 2 个端点；`disabled` 由**必填**带来的客户端兼容性影响未评估（若有前端调用方需同步） |
| N5 修复 | ruff 18→0；PRICING 值逐项对比 + 守卫 9 passed | ✅ 3 条命令 | —（lint 类） | ✅ 金额对比独立于实现 | **依赖 CVE 式风险**：`ruff --fix` 自动改写已人工核验（只改整数字面量），但**未来再跑 `--fix` 仍可能改浮点**，须保留人工复核 |
| Git 对象修复 | 写前校验 `hash-object` == 期望 sha（一致才写）；写后 `write-tree` rc=0 | ✅ `repair_missing_blobs.py` | — | ✅ 内容寻址（sha 一致 ⇒ 内容一致） | **仅覆盖索引可达对象**；**历史提交中的对象可能仍缺失**（未跑 `git fsck`）；§1 明确不要求修对象库，本次属"为完成提交的最小必要动作" |
| 门禁 1063 | `gate-s12.txt`（**提交后**在同一内容上运行） | ✅ 一条命令 | — | — | `slow` 18 条按项目约定未跑；覆盖率 79.01% 为行覆盖口径 |

## 四、审计结论

- 修复本身的**工程结论成立**（4 项均有本次实测证据，B1 含红→绿闭环，S1/S2 已补 HTTP 级实测）；
- **两处口径已在 §二 更正**，避免"过滤子集 17 passed"被误当成全量、避免"1063 passed"被误当成覆盖了守卫代码；
- **未验证项**：`git fsck`（历史对象完整性）、前端调用方对 `disabled` 必填的兼容性 —— 均已在表内标注。

---

# 第二批：grilling 后的四件收尾（含 B1 影响评估）

grilling 四项确认：Q1 先重测拿基线 / Q2 B 用离线 A/B 对照 / Q3 CI 加一步 / Q4 HTTP 测试进 CI + N1。

## 一、B1 影响评估（**零成本**，`b1_impact.py`）

- **复刻校验**：旧逻辑为独立复刻，先验证它复现已记录的旧行为（1/2/3/4 连）→ **4/4 PASS**
  （尺子可信才用于对比，避免"用错尺子"）。
- **扫描**：21 DB / **190 条文本** → **受 B1 影响 8 条（4.2%）**，**新增提取引用共 13 个**
  （典型：`第40条`、`第26/27条`、`第254/255条`）。
- ⚠️ **口径声明**：本数字按**文本条数**计；此前 `check_reachability` 的「16 次 ≥3 连」
  是 116 DB / 1034 行、按**链**计数 —— **两者分母与计数单位不同，不可混比**。
- 结论：B1 变严属**有限量级**，非大面积。

## 二、B1 后 12 次采样（同协议同语料，`quant3.log`）

| 轮次 | READY | citation 侧 | numeric 侧 |
|---|---|---|---|
| A 前 | 6/12 | 2（continuation_form） | 4 |
| A 后 | 5/12 | 1（unbracketed） | 6 |
| **B1 后** | **7/12** | **0** | **5（100% `from_unknown_facts`）** |

- **B1 未引入新 citation 失败**（与影响评估"有限量级"一致）；
- **唯一剩余形态锁定 `from_unknown_facts`（5/12）** ⇒ **B（未决事实脱敏）是唯一杠杆**；
- READY 6→5→7 属**采样波动**（n=12），不构成趋势断言。

## 三、S3：把评测宿主纳入 CI（`2deccb6`）

`ci.yml` backend job 新增一步（沿用 `working-directory: backend`，路径用 `../`）：
`ruff check` / `ruff format --check` / `pytest` 于 `dispatch-output/agent-quality-20260911/`。
**YAML 解析已验证**（steps 含新步骤）。

## 四、HTTP 级验证进 CI + N1（`a96498b`）

- **HTTP 测试入库**：`test_admin_llm_endpoints_return_422_for_invalid_bodies`（7 非法体 422、
  合法体 404 证明未误杀）——把 show-your-work 审计中的临时脚本**固化为 CI 守护**。
- **N1**：删除常量包装 `citation_noncanonical_shape()`（恒返回同一值、`unclassified` 生产不可达），
  调用点内联 + 注释"引入第二类形态时必须恢复独立分类函数"；原测试改为钉住**不变量**。

## 五、❗ 本批纠正的一个错误认知（重要）

`dispatch-output/agent-quality-20260911/` 的文件**一直是 git 跟踪的**
（`budget_guard.py` / `serve.py` / `test_budget_guard.py` 均在 `git ls-files` 中）。
我此前在报告中写"未跟踪、无需提交"是**错的** ⇒ 守卫三修（无金额上限/定价表/失败不阻断换模型）
与宿主断言通用化**长期未提交**。本批以 `25d1066` 补提交（307+/54−）。

## 六、本批新增的两个环境事实

| 事实 | 证据 | 影响 |
|---|---|---|
| **仓库无 ruff 配置** ⇒ 同一目标在不同 CWD 下结论不一致 | 从仓库根跑通过；从 `backend/` 跑同路径报 **12 项 E402** | 已加该目录 `ruff.toml`（显式 `ignore=["E402"]`）→ 三向结论一致 |
| **Git 对象库缺失比索引更广** | `git commit` 触发后台 gc 报 `Could not read 01d9b1b2…` / `Failed to traverse parents of commit 8b5ef939…` | 我只修了**索引可达**对象（`write-tree` 成功）；**历史提交的 parent 仍缺失**，`gc`/`repack` 会失败（非阻塞） |

## 七、汇总（第二批）

- **提交**：`25d1066`（守卫/宿主，含此前遗漏的功能改动）→ `2deccb6`（CI 步骤）→ `a96498b`（HTTP 测试 + N1）
- **最终门禁**：**1064 passed / 18 deselected / 0 failed / 79.08% / exit 0**；
  三向 ruff/format 一致通过；守卫 9 passed。
- **未做**：💭 nit 中的 N2（priority 无界负）/ N3（occupied 内存 8×）/ N4（writer.py Divergent Change 重构）
- **下一步**：**B（未决事实脱敏）** —— 唯一剩余杠杆（`from_unknown_facts` 5/12），
  按已对齐方式做**离线 A/B 对照**后再落地。

---

# 第三批：B（未决事实脱敏）—— 唯一剩余杠杆已打通

提交 `785391d`。grilling 已对齐：**payload 层类型化改写**（不动 planner）+ **离线 A/B 对照**验证。

## 一、实现（最小面）

| 位置 | 内容 |
|---|---|
| `settings.py` | `agent_writer_desensitize_unknown_facts: bool = False`（**默认关**，含动机与回滚说明） |
| `agent/writer.py` | `desensitize_unknown_fact()`（数字型 token → 中性表述）、`writer_unknown_facts(issue, *, desensitize)`（**开关收口**）、`build_writer_payload` 按开关决定 |
| 范围 | **只动 `unknown_facts`**；`facts`/`evidence` **永不脱敏**（已确认事实允许引用）——有测试守护 |

替换口径与 `numeric_tokens` **完全一致**（writer 的 numeric 校验用的就是它）：
日期→某日期 / 金额→一定金额 / 百分比→一定比例 / 期限→一定期限 / ASCII 数字→若干。
⇒ 「模型无从复述」有**确定性保证**：`numeric_tokens(脱敏(x)) & numeric_tokens(x) == ∅`（单测钉住，含幂等性与"无数字原样保留"）。

**为什么需要它**：12 次同协议采样里 numeric 失败的**唯一形态**是 `from_unknown_facts`（5/12）；
实测未决事实里只有 3 个 token，**全是 duration**（`三十日`/`一个月`/`十二个月`）——
模型在条件化论述里复述它们，而这些数字按纪律不可作为依据（不能绑 fact_id）。

## 二、⚠️ 实现中被自己单测抓到的真缺陷（已修）

初版开头做了整体 `NFKC` 归一化 → 会把**全角问号/括号**一并改成半角：
① 制造无谓 diff；② **破坏 `missing_information` 的逐字来源校验**（`_render_once` 要求模型输出的
缺失信息逐字来自 payload 的 `unknown_facts`；payload 若被改写，模型复述原文反倒不匹配
→ **反而制造新的失败形态**）。现改为**只替换 pattern 匹配到的片段**（非匹配部分逐字不变）。

## 三、A/B 离线对照（1e3 C01 真实 state，完整 writer 校验链，各 2 采样）

| 臂 | READY | 失败 | `from_unknown_facts` |
|---|---|---|---|
| **OFF（对照）** | **4/8** | `UNSUPPORTED_NUMERIC_TOKEN` ×4 | **4** |
| **ON（脱敏）** | **8/8** | 0 | **0（清零）** |

- 差异 **4 条（50%）** > 抖动阈值（≤2 条）；争点2/4 在 OFF **2/2 稳定失败**、ON **2/2 稳定成功**
  ⇒ **可下结论**（非噪声）。

## 四、质量抽查（ON 臂真实 draft，1 次调用）

**READY 只证明校验通过，不证明质量**，故另看文本：

- 脱敏前后对照：`…提前三十日…一个月工资…`（tokens 2 个）→ `…提前一定期限…一定期限工资…`（**tokens=[]**）
- 论述**条件化完整保留**（原文摘录）：
  > 「**若**公司依据《劳动合同法》第三十九条…**则需**证明"连续两次绩效不合格"已被合法有效的
  > 规章制度明确界定…；**若**公司系依据其他条款解除但未履行培训或调岗程序或未提前书面通知及
  > 支付代通知金，**则**当天通知解除可能不符合法定程序。」
- 未复述被脱敏数字；引用绑定 **4 条证据 + 2 个 fact_ids**
- `missing_information` **逐字匹配 ON 臂 payload** ⇒ 来源校验自洽（符合设计预判）

## 五、⚠️ 已知代价（诚实标注，需你定夺）

脱敏产物会进入**用户可见**的 `missing_information`（如「是否提前**一定期限**书面通知」）
⇒ **待确认项的精确度下降**：以"待确认项模糊化"换"整轮不失败"。

可选补偿（**未做，超本轮范围**）：终稿侧附**原始未知事实原文**（用户看到精确的待确认项，
而模型侧仍用脱敏文本）——需改 finalizer/渲染层。

## 六、汇总

- **提交**：`785391d`；最终门禁 **1071 passed / 18 deselected / 0 failed / 79.11% / exit 0**（+7 条新测试）
- **默认关** ⇒ 要生效需在 `.env` 设 `AGENT_WRITER_DESENSITIZE_UNKNOWN_FACTS=true`
- **下一步（建议）**：启用开关 → **重跑 C01 端到端**（新批次 1e4）——
  按 grilling 已定的判据：`final_chars>0 且 agent_completed=True` 为独立信号，
  然后按 §4.2 六维度人工复核（不得用工程指标替代法律质量结论）。

