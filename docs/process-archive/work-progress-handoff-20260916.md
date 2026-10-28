# 工作进度交接（致指导书作者：`project-quality-guide-20260914.md`）

日期：2026-09-16 ｜ 交接人：本轮执行助手 ｜ 收件人：指导书编写助手
定位：本文是**给指导书作者的工作汇报与交接**；进度正本仍在指导书末尾（§8–§12 已追加），
本文不覆盖任何既有文档，只做**汇总与指路**。

---

## 0. 一句话状态

> 指导书 §9.2 的两条线（1c/1d）与 §4 第 1 优先级（item 2 关键法律适用错误）推进至：
> **C01 首次产出终稿**（1e7 r3，`agent_completed=True`，2191 字）；1e9（C01 ×2）全部 completed，
> 未复现 1e4–1e8 观测过的任一失败形态（UNKNOWN_FACT_ID / UNSUPPORTED_CITATION /
> OVERCONFIDENT_WORDING）。两列口径：有输出率 **2/2**；全争点覆盖率 **1/2**（部分交付按 §12 边界工作）。
> 剩余为**渲染层法条墙**（§4.3，修法已定）与**独立法律验收**（不可由助手替代）。
> 门禁 **1078 passed / 0 failed / 79.22%**（`gate-word.txt`，覆盖至 `604fa24`；其后 `fa150d4` 仅改
> 评测脚本 `scripts/gate2_runner.py`，不在门禁检查范围）。未 push（对象库历史缺失未完全修复，见 §10.2）。

---

## 1. 状态快照（截至 `fa150d4`）

| 项 | 值 | 证据 |
|---|---|---|
| HEAD | `fa150d4`（test(review): runner 登录重试加可观测日志） | `git log --oneline` |
| 全量门禁 | **1078 passed / 18 deselected / 0 failed / 79.22% / exit 0**（`-m "not slow"`；最新一次，覆盖至 `604fa24`） | `dispatch-output/quality-fix-20260915/gate-word.txt`（`gate-wall.txt` 为同数字较早一次，覆盖至 `fe96120`） |
| 静态 | ruff check/format + mypy 全绿（`agent/`、`prompts.py`、`schemas.py`、`main.py`） | 各轮提交前记录 |
| 模型链 | backend/.env：6 条 qwen3.7（主 `qwen3.7-max-2026-06-08`）；**两开关全开**：`AGENT_WRITER_DESENSITIZE_UNKNOWN_FACTS=true`、`AGENT_PARTIAL_DELIVERY_ENABLED=true` | `dispatch-output/config-backups-20260915/env.before-*.bak` |
| 工作树 | 干净；**未 push**（§1 不要求；对象库历史缺失未完全修复，见 §10.2） | `git status` |
| 端到端 | 1e9（C01 ×2）：**有输出率 2/2**；**全争点覆盖率 1/2**（终稿2 部分交付含未覆盖清单）；累计账本 0.5731 元 | `dispatch-output/agent-quality-1e9-20260916/` |

## 2. 提交栈（本轮新增，全部单独提交；验证方式见段末说明——行为类「先红后绿/契约」，配置类为等效检查）

```
fa150d4 test(review): runner 登录重试加可观测日志
604fa24 fix(writer): 脱敏替换词避开违禁词表——修正 B 与 OVERCONFIDENT 检查的冲突回归
fe96120 fix(agent): 法律依据改为 claim 绑定条文（§4.3 部分口径，第 3 次修法待做）+ runner 登录有界重试
8178a64 fix(prompts): writer 禁用绝对化表述（当时归因文风；后经归因修正，见 §5.3）
13852e5 test(review): 补齐方案 A 三处测试缺口（G1 全失败分支 / G2 豁免单测 / G3 说明纯函数）
aa31014 feat(agent): 争点级部分交付（方案 A）
785391d feat(writer): 未决事实脱敏（B）
b6594e6 fix(git): 忽略密钥备份与 SQLite WAL（审查 B2/B2b）
192ae66 fix(api): admin llm 端点改 Pydantic schema（审查 S1/S2）
c6278c8 fix(writer): 续引链「命名引用+贪心吃链」（审查 B1）
```
以上为 git 实际时序（新→旧）。更早的本线提交（旧→新）：
`aca35b8`(观测) → `5e2e6b1`(A') → `e5c5392`(A) → `4dcc335`(管理面) → `0d75f37`(prompt 后果) →
`0fc87ca`(2a') → `32649ce`(1d) → `5cebcc4`(1c+1k+候选A)。再往前（R1 守卫等）见 `git log`；
§8 基线 HEAD 为 `8d21a9d`。各提交详情以提交信息为准。
**验证方式说明**：各提交均有验证记录——行为修复类为「先红后绿」或契约测试；
配置类（如 b6594e6）为 `git check-ignore` 等效检查，不适用红绿流程。

## 3. 指导书条目对照（详版见 `docs/process-archive/quality-guide-progress-audit-20260915.md`）

| 条目 | 状态 |
|---|---|
| §9.2 1c（失败换模型，F1–F8） | ✅ 完成（`5cebcc4`），端到端实测机制工作 |
| §9.1 四文件 / §10 待办②KB 抽检 | ✅ 完成（`32649ce`；16/16 硬缺口全在库） |
| §1「无金额上限」 | ✅ `limit="none"` 显式字面量 + 守卫三修（`25d1066` 补提交） |
| **§9 项 2 / §4.1 item 2（最高优先）** | 🔄 进行中：1e4–1e9 端到端失败形态逐层收敛（见 §4）；C01 已产出终稿；剩余=渲染法条墙（§6 待办 1）+ §4.2 独立验收 |
| §9 项 1j/1l/3/5、§9.1 工具层 | ⬜ 未做（理由见审计报告） |
| **新增待拍板** | 部署侧 root `.env` 切链；push 前对象库处置 |

## 4. 端到端演进（8 轮，全部预注册 + 账本 + 独立证据目录）

| 批次 | 结果 | 关键发现 |
|---|---|---|
| 1e/1e2 | 网络抖动 + guard halt 缺陷 / 事实认定型争点零 claim | guard `failed()` 无条件 halt 是真缺陷（已修） |
| 1e3 | `UNSUPPORTED_NUMERIC_TOKEN` | A' 补丁此前已提交（`5e2e6b1`）；本轮以 12 次采样量化确认数字复述为剩余主形态 |
| 1e4/1e5 | `UNKNOWN_FACT_ID` / `UNSUPPORTED_CITATION`（低频编造） | 暴露**串行复合成功率**问题（单点 90% ⇒ E2E ≈59%） |
| 1e6 | `OVERCONFIDENT_WORDING` ×2（r1 runner 崩） | 初判文风层；后经归因修正为脱敏替换词冲突（见 §5.3） |
| **1e7** | **r3 completed（首份终稿 2191 字）** | 该 run 未复现此前两类失败；渲染层暴露法条墙与 unknown 来源问题（§6 待办 1） |
| 1e8 | r1 **exit=0**（runner 重试后）✓；OVERCONFIDENT 复现 | G1 分支（全失败仍失败）按设计工作 |
| **1e9** | **r1/r2 全 completed，errors=[]**（n=2） | 替换词修正后 OVERCONFIDENT 未复现（机制层根因已消除，见 §5.3）；法条墙部分改善、仍有冗余（§6 待办 1） |

## 5. 关键发现（对指导书作者有用的结构性结论）

1. **串行复合成功率**：逐争点串行、首失败即停 ⇒ 单点 90% 在 5 争点下 E2E 仅 ≈59%。
   **单点率与端到端率口径不可混比**（本会话第三次同类口径教训）。
2. **部分交付 ≠ 降低覆盖率**（§12 边界，用户已确认）：交付形态改变、验收标准不变——
   未覆盖争点仍记 FAIL/REVIEW。实现时**必须同步改 verifier**（否则失败只是推后——B 项教训），
   且豁免须**随 `VerificationResult` 传递**到 `render_verified` 的 fresh 二次验证
   （否则二次验证把部分交付再次拦下——实测踩过）。
3. **跨模块词表冲突**：B 脱敏替换词（"一定期限"）与 verifier 违禁词表（含"一定"）冲突，
   1e6/1e8 两次端到端学费 ⇒ 已加**跨模块契约测试**（writer 输出 ∩ verifier 词表 == 空）。
4. **样本分布决定缺陷可见性**：量化样本恰好只含 2 连续引 ⇒ 3 连缺陷不可见。
   结构性（解析类）改动应做**形态枚举**而非频率采样。
5. **可达性用零成本独立证据**：116 个历史 DB 的终稿文本即可回答"模型是否会这样写"。

## 6. 待办（按优先级；均含判据）

| # | 项 | 判据 / 前置 |
|---|---|---|
| **1** | **法条墙第 3 次修**：法律依据按 `canonical_citations(正文文本)` 过滤（当前 `fe96120` 只做到"按绑定"，1e9 实测仍 8/13、4/5 条冗余） | 单测（未引用条文不得出现）；端到端 1 次（终稿法律依据 ⊆ 正文引用） |
| **2** | **§4.2 六维独立验收**：C01 终稿（1e9 或后续）交律师/用户复核 | 助手自查 ≠ 独立验收；REVIEW 不计 PASS |
| 3 | **runner 重试路径观测**：日志已加（`fa150d4`），下次批次运行看 `login retry` 是否出现 | 已有证据前不得声称"重试生效" |
| 4 | 部署侧 root `.env` 切链（6×qwen3.7 + 两开关） | **需拍板**；切 = 基线重验 |
| 5 | push | **前置：对象库缺失**（`01d9b1b2` 已修索引可达部分；`8b5ef939` 的 parent 仍缺 ⇒ gc 失败非阻塞） |
| 6 | nit N2/N3/N4；mypy 配置注释与行为不符（scripts 4 个**既有**错误，`mypy .` 实际不查 scripts） | 低优先 |

## 7. 环境事实与本会话踩坑（对后续执行者重要）

| 坑 | 处置 |
|---|---|
| `git stash` 两次触发 **SIGTERM** | 不用 stash；用文件复制备份 |
| **heredoc 未加引号** + 内容含反引号/`$` → bash 展开（3 次踩） | 一律写 `.py` 文件执行；CRLF 文件用**行级拼接**+写后校验"孤立 LF=0" |
| commit message 含引号被 bash 截断 | `git commit -F <消息文件>` |
| ruff **无根配置** ⇒ 同目标不同 CWD 结论不一致 | 目标目录已加 `ruff.toml`（评测宿主 ignore E402）；三向验证 |
| `mypy .` **不检查** `scripts/`（66 文件无它） | pyproject 注释与行为不符（待办 6）；gate2_runner 的 4 个既有错误不影响 CI |
| **对象库缺失**：索引可达已修（`repair_missing_blobs.py`，写前校验 sha 一致）；历史 parent 仍缺 ⇒ gc 失败非阻塞 | 修复脚本：`dispatch-output/quality-fix-20260915/repair_missing_blobs.py` |
| `dispatch-output/agent-quality-20260911/` **是被跟踪的**（曾误判未跟踪） | 守卫/宿主改动须提交；该目录不在 CI 四道门禁（ci.yml 已加步骤） |
| 探针用隔离配额库 ⇒ **无账本**，成本只能标"估算" | 验收轮走守卫有账本，两类成本分开报 |

## 8. 诚实标注（全链）

- 本轮所有"质量"结论均为**实现者自查**（工程口径）；**§4.2 六维独立法律验收未做**，REVIEW 不计 PASS；
- 端到端 n 小（1e7 n=3 / 1e9 n=2），统计口径按 §5/§12 两列报告，未下"可靠性改善"结论；
- B 的已知代价：脱敏文本进入用户可见的 missing_information（"法定期限"替代具体天数）——
  **渲染层 unknowns 用 state 原文**（信息量保留），仅 missing_information 段仍是脱敏文本（可接受性待产品确认）；
- 探针成本为估算、验收成本为实结（账本分列）。

## 9. 证据索引（本轮）

| 证据 | 路径 |
|---|---|
| 审查报告（含对抗审查附录） | `docs/process-archive/code-review-report-20260915.md` |
| 修复报告（含两批 + 审计附录） | `docs/process-archive/code-review-fixes-20260915.md` |
| 结构化分析（E2E ≈50% 推导 + 方案对比） | `docs/process-archive/quality-e2e-structural-plan-20260915.md` |
| 指导书进度审计 | `docs/process-archive/quality-guide-progress-audit-20260915.md` |
| 批次 1e4–1e9 | `dispatch-output/agent-quality-1e{4..9}-2026091{5,6}/` |
| 修复/验证脚本与消息 | `dispatch-output/quality-fix-20260915/` |
| 性能基准 | `dispatch-output/quality-review-perf-20260915/bench.py` |
| 审计复现脚本 | `dispatch-output/quality-review-verify-20260915/` |

---

# §10 指导书外工作（2026-09-16 补录；范围经用户 grilling 确认：A/B/C/D 四项全收）

指导书 §8–§12 只覆盖付费验收与质量防线；本章补录**不在指导书范围内但影响接手**的工作。
落点：扩充本文档（用户拍板：单一入口，不新建文件）。前端线为**占位指针**（非本执行者所做，
细节由执行助手自行记录，避免二手失真）。

## §10.1 前端线（**占位指针**——另一助手执行，本表仅列提交号）

以下 14 个提交由**前端执行助手**完成（T0 工具链 → T1 体验修复 → T2 重构三阶段），
**本交接不代写细节**，过程记录/验收状态以各提交信息与前端执行助手的自有文档为准：

| 阶段 | 提交 |
|---|---|
| T0 工具链 | `a39525d` ESLint 接入并修既有 error ｜ `645eeb3` Prettier(check-only) ｜ `15f3020` Vitest（33 用例） |
| T1 体验修复 | `f0f9cc9` 5 项审计确认缺陷（对比度 1.49→8.71 等） ｜ `17060da` SW 缓存构建号版本化 ｜ `0cadf1e` 侧栏跳转 streaming 保护 ｜ `f50c58e` aria-live ｜ `39f6feb` 触达目标 44px ｜ `93c6413` Enter/Shift+Enter ｜ `ecb27c1` 语义色 AA 微调 |
| T2 重构 | `3723a22` 类型/常量集中 ｜ `d485b16` api.ts 消灭 any ｜ `13594d8` chat 页拆分 ｜ `50444bc` 状态收敛 hooks |

> ⚠️ 交接盲区：上述提交的**测试覆盖状态、遗留 TODO、是否已过前端门禁**本执行者未核验，
> 接手者请向前端执行助手索取其执行记录。

## §10.2 仓库基础设施（**阻塞 push，影响所有人**）

- **Git 对象库缺失**（指导书 §1/§9 项 5 已记录，本轮实测影响面更大）：
  - 索引可达对象 `01d9b1b2…`（`test_agent_prompt_contracts.py`）已用**非破坏脚本**修复
    （`dispatch-output/quality-fix-20260915/repair_missing_blobs.py`：仅 `git hash-object -w`，
    **写前校验工作区 sha 与期望一致**，绝不伪造；不删对象/不重写历史/不 gc）；
  - **历史 parent 仍缺**（`8b5ef939…` 不可遍历）⇒ 每次提交触发 geometric-repack 失败
    （`error: Could not read 01d9b1b2…`）——**非阻塞但会反复出现**；
  - **push 前必须处置**（缺对象 push 可能被远端拒绝或产生不完整历史）；处置选项：
    `git fsck --full` 全量盘点 → 从有副本的机器/备份补对象 → 或按 §1 惯例本地续作不 push。
- **`.gitignore` 本轮新增**（提交 `b6594e6` + 后续）：`dispatch-output/config-backups-*/`、
  `*.bak`、`*.sqlite-shm/-wal`、`*.db-shm/-wal`、`agent-quality-20260911/*.before-*`；
  **显式未加** `*.before-*` 全局规则（会误伤被跟踪的 h3 快照证据，注释已写明）。

## §10.3 评测基建（**影响后续所有验收轮**）

- **gate2_runner 首跑时序崩**：EVALUATION_READY 打印时 uvicorn 可能未完成应用初始化，
  首连登录拿到空响应 → `json.loads("")` 崩（1e6/1e7 批次首个 run 均现）。
  已修：登录**有界重试**（3 次 ×2s，只重试"响应不可解析"；凭据类不重试）+
  **重试日志**（`login retry N/3` / `succeeded after N retry(ies)`，提交 `fa150d4`）。
  ⚠️ 重试路径**尚未被实测观测**（1e8 r1 的成功可能是首次就成）——下次批次运行看日志即证。
- **`scripts/gate2_runner.py` 有 4 个既有 mypy 错误**（400/429×2/471；HEAD 副本同报，
  非本轮引入；`mypy .` 实际**不检查** scripts ⇒ CI 不受影响，但单跑 `mypy scripts/…` 会报）。
- **pyproject `[tool.mypy]` 注释与行为不符**：注释声称已修复 scripts 排除问题，
  实际 `mypy .` 仍不检查（66 文件无它）——注释待更正或行为待修复（二选一，待办）。
- **评测宿主目录已纳入 CI**（`2deccb6`）：`dispatch-output/agent-quality-20260911/` 增
  lint/format/pytest 步骤；该目录自带 `ruff.toml`（ignore E402——serve.py 需先设环境再
  import main 的隔离设计；且仓库无根级 ruff 配置 ⇒ 不同 CWD 结论曾不一致，加配置后三向一致）。

## §10.4 工程纪律与环境坑（详版；§7 为速查表）

本节从执行者私有记忆**提升为仓库可见**（此前其他助手看不到）：

| # | 坑/纪律 | 正确做法 |
|---|---|---|
| 1 | `git stash` 两次触发 **SIGTERM**（无输出丢失改动风险） | 不用 stash；用文件复制备份 |
| 2 | heredoc **未加引号** + 内容含反引号/`$` → bash 命令替换（本会话踩 3 次，曾污染写入文件） | 含反引号/`$` 的内容一律**写 `.py` 文件**执行；heredoc 定界符加引号 |
| 3 | CRLF 仓库文件 + LF 模式 heredoc/字符串 → 锚点不匹配或 EOL 混入 | 先探测 EOL；改用**行级拼接**；写后校验"孤立 LF=0" |
| 4 | commit message 含引号被 bash 截断（余文被当 pathspec） | `git commit -F <消息文件>` |
| 5 | ruff **无根配置** ⇒ 同一目标不同 CWD 结论不一致（根目录过 / backend 报 12 项 E402） | 目标目录放 `ruff.toml` 显式声明；CI 步骤固定 CWD |
| 6 | **可观测性先于验证**：retry/fallback/降级路径若无日志，事后无法区分"修复生效"与"未触发"（1e8 r1 的"重试生效"声明在 show-your-work 审计中被判定为超出证据，已修正并补日志 `fa150d4`） | retry/兜底代码与日志**同一次提交** |
| 7 | **跨模块词表/常量联动**须有契约测试：writer 替换词（"一定期限"）与 verifier 违禁词（含"一定"）单测各自绿、组合即炸（1e6/1e8 学费） | 任一侧改词表，跨模块测试立即失败 |
| 8 | **结构（解析）类改动用形态枚举测试，频率采样会漏**（量化样本只有 2 连 ⇒ 3 连缺陷不可见） | 先枚举形态，再看频率 |
| 9 | 成本口径：隔离配额库的探针**无账本**=估算；验收轮走守卫有账本=实结。两类数字分列，不混比 | 报告里显式标注 |
| 10 | `dispatch-output/agent-quality-20260911/` **是被 git 跟踪的**（曾误判"未跟踪无需提交"导致守卫改动长期滞留工作区） | 改动后即提交；勿凭目录位置推断跟踪状态 |

## §10.5 文档状态

- 本文（handoff）与 `docs/` 下本轮全部新增文档**维持未跟踪**（项目惯例：评测相关文档不提交；
  协作双方本机共享文件）——如需跨机器共享由用户决定是否入库。

---

文档版本：v2（2026-09-16 审核修订：门禁覆盖表述精确化至 `604fa24`；提交栈按 git 实际时序重排；"0 类稳定阻断""重大推进"等主观/歧义表述客观化；标注 fe96120 实现口径与提交信息措辞的差异）。初版 v1 为同日早前版本。
