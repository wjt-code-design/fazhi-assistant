# S5 · 快车道版本判定最小可用（只做缓冲轻量那一条出口）

起票依据：R15「法律版本绊线」收口时量出的覆盖缺口 —— 版本判定只挂在 agent 路径上，而
`AGENT_ENABLED=False` 时线上流量走快车道，**快车道没有任何版本判定**。本票补这一格，且只补一格。

**⚠️ 排队条件（不满足就别领这张票，领了必返工）**
1. `git status --porcelain backend/main.py` 必须为空。→ **✅ 本条已于 21:22 满足**：原先挂着的
   **未提交 +34/−1**（hunk 在 `:1301`、`:1312(+29)`、`:2160`）由审查会话以 **`8734a8f`**
   （"fix(review): 修复审查确认的正确性问题"，26 文件）提交；21:4x 实测
   `git status --porcelain --untracked-files=no` 全仓 = **0 行** ⇒ **领票不再被车道挡住**。
   （原理由留着以便你判断它何时又成立：只要有人再在 `main.py` 上留未提交改动，`git add backend/main.py`
   就会把那批字节一起 stage 进本票的提交 ⇒ 署名错误 + 夹带他人工作。）
2. 满足 ① 之后**逐条重测本票所有行号**。**21:4x 已重测一次：六个坐标一字未变**
   （`1155`/`1164`/`1567`/`1569`/`1761`/`1831`/`1902`）。原因说清：票内坐标本来就是**在那份未提交的工作树上**
   量的，`8734a8f` 提交的是同一批字节 ⇒ 提交本身不改行号。⚠️ 但这**不是一次性结论**：
   `8734a8f` 之后任何人再动 `main.py` 就重新漂移，领票时仍要按 P4 现量，别引用本段。
   另记一条已实测的漂移史：上一代记的 `1729/1870` → 本票的 `1761/1902`（+32），**这一版就是那 34 行推出来的**。
3. **`8734a8f` 顺带改变的执行环境**（执行本票前必须知道）：它同时提交了
   `docs/code-review-report-02e3851-20260918.md`（本票 §11 明令"不读不采纳"的那份，现已在历史里）
   与 `backend/tests/test_review_regressions.py`（+202 行）等一套别人的回归测试
   ⇒ 全量门禁基线已与我起票时不同，**先只跑自己的定向测试**再比全量，红先做归因。

**本轮为起票花的成本记账**：派发的一次只读调查（27 分钟、46 次工具调用）**失败无交付**
（`The request could not be completed`）。下面所有读数都是本会话自己量的，不是那份失败的产物。

---

## 0. 授权边界（越界即停手回报）

- **不改任何开关默认值**。新开关按 §4 命名，默认 `False`。"把开关打开"是评测批的预登记事项，不是代码改动。
- **不动 agent 路径任何行为**（`backend/agent/**` 全部只读）。判定真源已存在，本票只**消费**它。
- **不重跑付费三臂**。R15 已跑完（关绊线的快车道臂与 agent 臂都放行了跨分水岭的错答、开绊线臂 FAIL_SAFE
  且不误伤），记忆里明确标了"别再重付"。本票所有断言一律**离线**、不调模型。
- **`evals/watershed-cases-r15.json` 标的是 `NOT_FROZEN`** ⇒ 可当对照样本，**不进冻结集、不拿它的分数当判据**。
- **不推送、不部署**。
- 冻结资产勿动：`backend/scripts/gate2_runner.py` sha256 须保持
  `ae2e412059ed68ac1514c62727cee61c50b8a2d6fe7e38a77c7e05631847e295`。

## 1. 开工前置取证（八条全跑完，任何一条不符就停下报告）

| # | 命令 | 期望 | 为什么 |
|---|---|---|---|
| P1 | `pwd -W` | 以 `\ai-legal-helper` 结尾 | 本仓发生过"在 Desktop 上 grep 然后宣布文件不存在" |
| P2 | `git status --porcelain backend/main.py` | **空** | 见上面排队条件 ① |
| P3 | `git diff --numstat HEAD -- backend/main.py` | 空输出 | 与 P2 双证；不等就是有人在途 |
| P4 | `grep -n "def _light_buffered\b\|def _light_buffered_locked\|use_light = \|stream_with_retry(" backend/main.py` | 四个符号都在（当前实测 `1155` / `1164` / `1567`+`1569` / `1761`+`1902`） | 本票要动的正是这几处 |
| P5 | `grep -n "def law_version_crosses_watershed" backend/agent/limitation_calc.py` | 在（当前 `:225`，签名 `(claim_text, fact_texts: Iterable[str], law_as_of: date\|None) -> bool`） | 判据单一真源，别手写第二份 |
| P6 | `grep -n "law_version_tripwire_check" backend/agent/verifier.py` | 三处（当前 `:296` 接线守卫、`:338`、`:438`） | 证明"agent 路径有、快车道没有"这个缺口成立 |
| P7 | `grep -n "_check: bool = False" backend/settings.py` | 四处（当前 `:69 :80 :88 :94`） | 新开关要落进同一命名族，别自造形状 |
| P8 | `grep -rn "LEGACY_KEYS" backend/tests/test_request_bootstrap.py` | 有 `assert set(result) == LEGACY_KEYS`（当前 `:601`） | **它决定了 §4-Q2 的取舍**：往 `pre` 字典塞新键会让它红 |

## 2. 事实底座（本轮实测，`file:line` 全部可在当前树复跑）

快车道的出口**不是一个，是三个**，且三条的"能不能便宜地插一门"完全不同：

| 出口 | 当前坐标 | 选择条件（原文可查） | 接入门的代价 | 测试覆盖 |
|---|---|---|---|---|
| 流式主链路 | `main.py:1761 async for piece in stream_with_retry(` | `use_light` 为假那一支 | 答案**分片在外**，版本判定要整段文本 ⇒ 必须先在流尾收口 = **改用户可见的流式行为** | `stream_with_retry` 本身有测（`test_phase2.py:112/:136`、`test_quota_switch.py`，用 FakeChain），**未见驱动 `:1761` 这条分支的用例** |
| 第二流式分支 | `main.py:1902 async for piece in stream_with_retry(` 同形状 | 同上，另一处 | 同上，且与 `:1761` 的降级口径不完全一致 | 同上（未找到覆盖） |
| **缓冲轻量路径** | 调用点 `main.py:1831 res = await run_in_threadpool(_light_buffered, pre, messages)` → `_light_buffered:1155` → `_light_buffered_locked:1164` | `use_light = use_router and tier == "light" and modality == "text" and registry.has_role("text","light")`（`:1567`），合同评估在 `:1569` 强制关掉 | **便宜**：文本已在手（`:1167`、`:1182` 已 `clean_answer`），且这条自带"明说降级"惯用法 `NOTE_QUOTA`(`:1177`)/`NOTE_COMPLEX`(`:1180`/`:1187`) 可复用 | 有：`tests/test_tiering.py:70/:78/:86/:94/:103` 直接调 `main._light_buffered`（**全是两参数调用**，见 §4-Q2） |

其余已核实事实：
- `main.py` 全文 `grep -n "tripwire"` = **0 命中** ⇒ 缺口在当前树上成立（不是记忆）。
- 快车道总开关：`settings.agent_enabled`（`settings.py:49`，默认 `False`），分支判定在 `main.py:1428`、`:1475`。
- `law_as_of` 的可达性：端点在 `main.py:1486-1494` 用 `_bootstrap_only(..., body.law_as_of)` 建 bootstrap，
  ⇒ **`body.law_as_of` 在 `:1831` 的作用域里本来就够得着**，不需要经 `pre` 字典中转。
  `RequestBootstrap.law_as_of` 定义在 `request_bootstrap.py:49`，由 `:396` 填入。
- `_pre()`（`main.py:703`，docstring 自称 "Compatibility coordinator"）在 `main.py` 内 **0 调用点**，
  只有 `tests/test_pre_rewrite_order.py:93`、`:149` 调它，它 `:713` 转发到 `_prepare_fast_path_only`。
  ⇒ **它既不是死码（删了会红那条测试），也不是可挂门的地方**。本票**不要碰它**。

**留白（必须执行才能确定，本会话未跑）**：默认配置（`agent_enabled=False`）下一次真实聊天请求，
在上面**两条流式出口**里实际走哪一条？`tests/test_agent_resume.py:497` 有一条打 `/api/chat` 的端点级测试，
但没读到它落进哪个分支。§8 要求开工第一天就把这条问清楚并留证。

## 3. 范围：本票只做缓冲轻量那一条

- **做**：`_light_buffered_locked` 这条出口的版本判定门 + 它的测试与变异。
- **不做**（各自另开票，别塞进本票"顺手"）：两条流式出口的收口策略、`_pre` 旧壳的处置、
  `_light_buffered` 之外任何降级口径的统一。
- 收口定义里必须**如实登记**"另两条流式出口仍未覆盖" —— 本票完成后"快车道已受保护"这句话仍然**不成立**，
  只有"快车道轻量分支已受保护"成立。这是上一代 `[PL#14]` 假接线的直接教训。

## 4. 三个设计决策（**已定稿**：2026-09-19 Owner 令"按你的建议执行" = Q1/Q2/Q3 全按执行者建议采纳）

- **Q1 命中之后对用户呈现什么？** 建议：复用这条路径已有的"明说降级"惯用法（同 `NOTE_QUOTA`/`NOTE_COMPLEX`
  形状）新增一个版本冲突注记，**而不是**静默替换答案 —— 理由：R15 的三臂实测里，"放行错答"是要防的失败模式，
  而"整轮不交付"在快车道上没有 agent 路径那套 FAIL_SAFE 落点可继承。备选（更保守）：命中即走 `:1837`
  那条错误帧。**不许选**：只写日志不改输出（那等于没门）。
- **Q2 `law_as_of` 怎么传进来？** 建议：**给 `_light_buffered` / `_light_buffered_locked` 各加一个带默认值的
  尾参**（`law_as_of: date | None = None`），在 `:1831` 传 `body.law_as_of`。这样 §2 表里那 5 处
  `main._light_buffered(_pre(), [])` 两参数调用**不用改**。
  **不建议**走 `pre` 字典：`tests/test_request_bootstrap.py:601` 钉死了 `set(result) == LEGACY_KEYS`，
  加键必红，而那红是本票不需要的改动面。
- **Q3 开关命名**：`fast_path_law_version_check: bool = False`，放在 `settings.py:88` 那条
  `law_version_tripwire_check` 旁边，同族同形（`*_check: bool = False`）。
  开而未拿到 `law_as_of` 时的语义**必须照抄 agent 路径的 fail-closed**（`verifier.py:296-297`：
  开关开 + 基准日缺失 = 判定不可信 ⇒ 走保守分支），不要写成"缺就当作不拦"。

  ⇒ 上面三条里的"建议/备选"字样**均已作废为定稿**（保留原文是为了留下"为什么这么定"的痕迹）：
  Q1 = 新增版本冲突注记；Q2 = 带默认值尾参、不动 `LEGACY_KEYS`；Q3 = `fast_path_law_version_check` 默认 `False`
  且缺基准日 fail-closed。本票**没有待 Owner 勾的悬空项**；执行中发现某条不成立 ⇒ 停手回报并带上当时 P 读数，
  不要自行改设计。

## 5. 实现要求

1. 判定只调 `limitation_calc.law_version_crosses_watershed(claim_text, fact_texts, law_as_of)`，
   **不在 `main.py` 里重写任何版本规则**（单一真源，`verifier.py:295` 那条注释就是这个意思）。
2. 插入点在 `clean_answer` 之后、`_LightResult` 返回之前，且**这条函数里所有 return 点都要过同一道门**。
   当前实测 **5 个** return，逐个点名（开工时重数一遍，别信本表）：
   `:1171`（自检通过直接返回）、`:1176-1178`（配额耗尽不升级）、`:1180`（轻量即旗舰，无更强者）、
   `:1186`（升级后自检通过）、`:1187`（升级后仍不过）。漏一个就是"门在但走不到"。
3. 命中落日志时**必须带被判定原文**（沿用 `5afc8d0` 的可归因教训）；日志字段名要先过
   `tests/test_log_field_whitelist.py`（它会递归扫 `backend/` 全树找未登记字段 ⇒ **basetemp 别设在 `backend/` 内**）。
4. 开关关 ⇒ 行为逐字不变（§6-③ 要实证，不是口号）。

## 6. 测试与证据（每张判据都要"亲眼红过"）

- ① **先红**：新测试断言"开关开 + 轻量答案引用了跨分水岭的版本法条 ⇒ 命中降级口径"。
  它必须在**生产码未改时**跑成 FAILED，且红的原因是"没有这道门"，不是笔误/fixture 报错。红一次留完整输出。
- ② **期望值来自独立来源**：正/负样本从 `evals/watershed-cases-r15.json` 取形状，但**期望由手算给出**
  （分水岭 = 2021-01-01《民法典》1260 条），不许用被测实现反推期望。
- ③ **默认关 ⇒ 零变化**：同一批输入，改前/改后的输出**逐字比对**（不是"看起来一样"），比对脚本与差异条数留档。
- ④ **变异 ≥2**，且每道都要指出"红在哪一条断言"（pytest 只报第一条失败断言，写清才能判断有没有红错原因）：
  M1 摘掉整道门 ⇒ 期望 ① 红；M2 把"缺 `law_as_of`"从保守分支改成放行 ⇒ 期望 §4-Q3 那条测试红；
  M3 只给其中一个 return 点接门 ⇒ 期望"漏点"测试红（这条专门防 §5-2 那个漏）。
- ⑤ 两态都跑：`agent_enabled` True / False 各一次全量定向。
- ⑥ `run_gate_full` 一次 **RUN_VALID**（判据分两类：`0 failed` 只在 RUN_VALID 时有效；真实库零写入这类
  隔离判据在 RUN_VOID 时依然有效 —— 别混）。

## 7. DoD

①+②+③+④ 全绿留痕 + §6-⑤⑥ + `ruff`/`mypy` rc=0（⚠️ `scripts/` 与 `tests/` 在 mypy exclude 内，
`main.py` 受检 ⇒ 新增参数的类型注解要自己负责）+ pre-commit 手跑 rc=0（钩子未接进 git）+
**提交前 `git diff --cached --name-only` 逐行核对没夹带他人文件** + 回报按 §10 格式。

## 8. 必答留白项（开工第一天）

用**执行**而不是读码回答："默认配置下一次真实聊天请求走 `:1761` 还是 `:1902`？"
可复现做法建议：起本地服务（先 `curl --noproxy "*"` 探活，别抢别人端口），发一条会被判成 light-text 的请求，
看命中哪一条 `stream_with_retry`；或用 `pytest` 端点级用例 + 一次性打印分支标记（用完删掉打印）。
答不出就在报告里写"未证"，**不许把读码推断写成执行证据**。这条答案决定后续流式收口那张票的量级，比本票本身值钱。

## 9. 会被哪条历史教训击穿（按危险度排）

1. `[PL#14]` **假接线**：接了一条线上走不到的出口 ⇒ "快车道已受保护"成假话。防线 = §5-2 逐 return 点 + §8 执行证据。
2. **`main.py` 车道冲突**：在有他人 34 行未提交的工作上改同一文件。防线 = 排队条件 ①。
3. **指针会漂**：本票行号来自含在途改动的一次快照，实测过一次 +32 漂移。防线 = P4/P5/P7 重测、按符号锚定。
4. **全绿有保质期**：并行提交落在相邻文件后，你那次全量通过就不再归属当前 HEAD。防线 = 收口前在合并后的 HEAD 上重跑定向。
5. **索引裹他人工作**：提交的是整个索引。防线 = `git commit -- <显式路径>` + 提交后 `git show --stat HEAD` 复核。

## 10. 回给 Owner 的格式（照抄填数，别自由发挥）

```
P1–P8：<逐条 读数 / 是否符合期望>
HEAD=<hash>   main.py 开工前脏项=<必须为"无">
§8 留白：<走 1761 / 走 1902 / 未证>   证据=<命令 + 输出行>
实现：新开关名=<…> 默认值=<必须 False>   过门的 return 点数=<n>/<总数>（逐条列行号）
      law_as_of 传法=<§4-Q2 哪一路>
测试：红=<亲眼看到的失败用例名 + 红在哪一行断言>   绿=<passed 计数>
      默认关零变化：比对输入 <n> 条、差异条数=<必须 0>、方法=<脚本名>
      变异 M1/M2/M3 各自 FAILED 用例名=<逐条列> + 各红在哪条断言
门禁：run_gate_full 标签=<…> verdict=RUN_VALID|RUN_VOID  末行=<计数>
      两态：<agent_enabled True 轮计数> / <False 轮计数>
三件产物=dispatch-output/te-chroma-isolation-20260918/gate-<标签>.{log,json,txt}
本次改动=<文件清单，逐条自证是本会话写的>   未推送未部署=是
如实登记的未覆盖面=<必须包含"两条流式出口未受保护"这一句>
```

## 11. 不许你动的

`backend/agent/**`（含 `verifier.py`/`limitation_calc.py` 的任何一行）、任何开关默认值、
`evals/` 冻结资产、`gate2_runner.py`、`_pre()` 旧壳、`:1761`/`:1902` 两条流式出口、
`tests/test_request_bootstrap.py` 的 `LEGACY_KEYS`、推送与部署。卡住就回问 Owner，
提问时带上你的 P1–P8 读数与你想动的那一项。
