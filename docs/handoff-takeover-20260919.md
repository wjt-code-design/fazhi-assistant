# 接手票：法智评测器/判据线（2026-09-19，交给执行助手）

写给**没有本会话记忆**的接手者。读完这一页你应当能：知道前面做了什么、能独立复证、知道接下来只有
一件事可以动手、其余必须回来问。

- 起票会话：三批收口全部完成，最后一笔提交 `4465080`（工作树无他人未提交改动，`git status` 干净）。
- 详细留痕（不必先读，出问题再查）：`docs/progress-and-backlog-20260919.md`（进度与待办）、
  `dispatch-output/ta5-arms-20260917/handover-20260918.md` §12/§13/§13.8（裁决点与失实台账）。

## 0′. 这张票怎么用（Owner 只转发本文件，剩下按本节走）

1. §0 是不可协商禁令；§1 是开工前置取证（**必须全跑完**）；§3 是**当前唯一可执行项 A1**；§4 是**不许你动**的清单。
2. 跑完 §1 先回一条消息：**P1–P7 的逐条读数 + 一句"是否开始 A1"**。Owner 没说"跑"之前**不要跑 A1**——
   它占 2–7 分钟 CPU，可能让另一条并行会话那一轮变红，时序归 Owner 定。
3. 环境（本票写就时实测，可直接用）：仓库根 `C:\Users\33393\Desktop\ai-legal-helper`；
   解释器 `backend\venv\Scripts\python.exe`；pytest 配置在 `backend/pyproject.toml:92`
   （`testpaths=["tests"]` 在 `:93`，marker `slow` 的定义在 `:95`）；前台 shell 是 Git Bash。
4. **本票里 16 处 `file:line` 指针已在 HEAD `4465080` 上逐条 grep 复量、全部对上内容。** 你接手时 HEAD 多半已经不是它 ⇒
   引用前一律先 `grep -n <符号名> <文件>` 复量（漂移实例见 §1 末尾汇总表）。

## 0. 三条不可协商（违反即停手问 Owner）

1. **不改生产开关、不改判据数值**。`CLARIFY_ROUND_LIMIT = 2`（`backend/scripts/gate2_runner.py:206`）冻结；
   判据本体在 `:588-590`（`tail_clarification` / `clar_requests` / `over_rounds`），执行预算 `FACT/SCOPE_CLARIFY_LIMIT = 2` 在 `:200-201`。
   该文件当前 sha256 = `ae2e412059ed68ac1514c62727cee61c50b8a2d6fe7e38a77c7e05631847e295`（与起票会话审计时钉住的同一版，实测一致）。
   R1 / R1-OB / T-A6 / 修正性重试 / R11 / R12 / R15-lite / `entity_precision_check` / `numeric_matching_v2` 全部默认关，别去开。
2. **不覆盖冻结资产**（路径均已实测存在）：`evals/frozen-cases-v2.json`（`status=FROZEN`）、`evals/probe-results.json`、
   `dispatch-output/r1-ob-offline-20260916/counterexamples.json`、任何 `*-sessions.json`、P5 复核材料。
3. **不推送、不部署**（Owner 令；远端历史链曾断，须走快照机制并先 `git ls-remote` 实测——这一条是**沿信上游**，本会话未复测）。

## 1. 开工前置取证：**先全跑一遍，任何一条不符就停下报告**（约 3 分钟）

| # | 命令 | 期望 | 为什么 |
|---|---|---|---|
| P1 | `pwd -W` | 路径以 `\ai-legal-helper` 结尾 | 本仓发生过一次"在 Desktop 上 grep 然后宣布某文件不存在"的假阴性 |
| P2 | `git log --oneline -3` | 记下游标；**别人可能已经又提交了几笔** | 多会话共享同一工作树并行改码 |
| P3 | `git hash-object backend/scripts/gate2_runner.py` vs `git rev-parse HEAD:backend/scripts/gate2_runner.py` | 两者相等 | 不等 ⇒ 有人正在改判据源文件，你的复证没有意义（**别用 mtime 判断，用 blob**） |
| P4 | `backend/venv/Scripts/python.exe dispatch-output/over2-replay-20260919/over2_replay.py --verify` | 末行 `VERIFY 幂等 = True`，**退出码 0** | 证明判据重放仍可复现；退出码**不许**在 `| tail` 之后取（管道吞码） |
| P5 | `backend/venv/Scripts/python.exe dispatch-output/over2-replay-20260919/_over2_tripwire.py` | 三道变异"全部拦住"，exit 0 | 证明那把尺子的门禁不是永远放行 |
| P6 | `git diff --name-only <上次全量绿的 HEAD>..HEAD -- backend/` 计数 | 只是**取当下真实值**，不期望 | 决定 §3 那一步的必要性 |
| P7 | 读 `docs/progress-and-backlog-20260919.md` §5 四类待办 | — | 明确哪些不许动 |

⚠️ **文档里的行号指针会随他人提交漂移。** 起票会话 2026-09-19 复核出的四处（引用前先 grep，别照抄）：

| 谁写的 | 旧指针 | 现在实际在 |
|---|---|---|
| 本报告 §0/§2、进度报告 §3 | `gate2_runner.py:190` 是 `CLARIFY_ROUND_LIMIT` | **:206**（判据本体 `:588-590` 未漂） |
| handover §13.1 第 8 项 / 审计报告 §7 第 5 条 | 执行书 `:999-1001`「45 序列 25 分歧」 | `docs/execution-plan-entity-precision-20260917.md:1068-1071`（另见 `:1144`） |
| handover §13.1 第 1 项 | 执行书负面清单 `:269`、`:276-277` | **:360**、**:367-368** |
| handover §13.1 第 2 项 | `agent/service.py:488` 的"非 PASS 即终态"注释 | **:492** |

另：**`evals/frozen-cases-v2.json` 里 `scope_trigger` 的定义在 `:8`**（本次实测，含"只作记录"那句免责）。

⚠️ **文档里所有绝对数（375 条 / 84 文件 / 146 条 gate5 / 14 笔）都是当时的快照**，一律以你自己重测为准。
语料是活体：起票会话三次实跑得 371 → 373 → 375，增量全来自并行会话往 `dispatch-output/r15-watershed-20260918/` 追加真实 run。

## 2. 前面做了什么（净结论，一句话一条）

1. **第一批**（`afd3138`、`777e332`、`62bde3e`）：评测 harness 的 resume 归属去猜测、虚设上界钉成确切值、
   词表术语优先分支补覆盖（含一条**故意记录接受风险**的测试）、多 case 归属端到端覆盖；只动 `backend/tests/`。
2. **第二批**（`27d5363`、`d4b8d79`）：把"两轮"与"over2"的口径写成人话、scope 预算耗尽守卫补测试、
   假服务抽传输层基类（零行为变化）。**全量 `pytest -m "not slow"` 绿，证据锚在 `d4b8d79`。**
3. **第三批**（`e3c023a`、`b61bc08`、`105907b`、**`4465080`**）：把本机存着的真实评测产物按**三代 over2 判据**离线重放，
   量"该报没报"的案子。结论：**漏标 0 条**；旧判据"只看末尾是否澄清"确实与现行存在分叉（真实 1 条、合成 18 条），
   而那 1 条**判对了** ⇒ 票据 P2-2 提的"可能还有被末尾快照掩盖的"**被证伪**（不是"没测过"）。
   附带：`scope_trigger` 设计标记与运行时行为**双向不符**，所以它不能升格为判据。
4. **起票者犯过、并被自家仪器抓到的错**（你重犯的概率不低，故写明）：把旧判据的**意图等价式**
   `(n>=3) or (n>=2 and tail)` 当成它的**字面形状** `bool(末尾有澄清)`。等价式与现行判据恒等 ⇒
   算出"分歧 0"，那 0 是**尺子被调瞎**，不是被测对象干净。凡复刻历史判据，逐版按代码字面形状各写一条谓词，
   并给每条轴配一道期望值来自**重放之外**的 known-answer 门。

## 3. 唯一可执行项 A1：补一次全量测试门禁

**为什么要补**：起票会话的三批之后，HEAD 又走了不少笔、`backend/` 下含**生产码**被两条并行线（R15、T-E）改过
（起票时快照：`d4b8d79..HEAD` = **14 笔**、`backend/` 下 **23 个文件**变动、其中 **12 个是生产码**——你自己重测为准）
⇒ 当前 HEAD 上没有任何全量绿证。**这不是修 bug，是给"HEAD 是好的"这句话补仪器。**

**必须用带自证的跑者，不许裸跑 pytest**（裸跑出的红在多会话工作树里无法归因，本仓发生过整轮 ImportError 的假失败）：

```
cd backend && ./venv/Scripts/python.exe ../dispatch-output/te-chroma-isolation-20260918/run_gate_full.py <你起的标签>
```

它会：跑前后对 `backend/` 全部 `.py` 取 sha256、跑前后各做一次真实 chroma 清单、产出
`gate-<标签>.log` / `-source-sha.json` / `-verdict.txt` 三个文件。未知参数有守卫（本会话实测：
传 `--help` ⇒ 打文档、退出码 **2**、且目录下**没有**生成任何 `gate-help*` 产物 ⇒ 确未起跑）。

**判据（两类，别混）**：
- 回归判据：pytest 退出码 + 末行计数——**仅在 verdict = `RUN_VALID` 时有效**。
- 隔离判据：真实 `backend/chroma_db` 清单前后一致——**`RUN_VOID` 时依然有效**。

**分诊表**：

| 现象 | 含义 | 你该做什么 |
|---|---|---|
| `RUN_VOID` | 跑的过程中有人改了源码 | 这轮 passed/failed **作废**，重跑；不要报"全量绿" |
| `RUN_VALID` + 0 failed | 当前 HEAD 绿 | 报数：commit、verdict、passed/deselected 计数、三件产物路径 |
| `RUN_VALID` + 有 failed | 真红 | **先归因**：`git hash-object` 比对判据/被测文件是否等于 HEAD blob、失败用例是否落在别人刚改的模块；不许顺手改他人代码，把归因结论交回 Owner |
| 用例报 chroma/SQLite "database is locked" 之类 | **未归因**（本会话实测：该字符串在 `backend/` 下的 `.py` 里 0 命中，只在更早会话里作为"并发访问、非回归"的**推断**出现过，从未复现） | 当作真红处理并回报，不许照抄"已知 flake"这句话放行 |

顺带知道三件事，省得你误判：① **chroma 的 `data_level0.bin` 首次 upsert 一次性预分配 ⇒ 目录尺寸不能证明谁写了库**
（这一条是更早一次会话实测的结论，本会话未复测，要当判据用请自己验一遍）；
② 测试默认层已把 `CHROMA_DIR` 隔离到进程私有临时目录（`backend/tests/conftest.py:40`），需要真实语料的用例
显式 opt-in `real_kb` fixture（`:115`，真实库条数不足会 skip 而不是假绿——这两行本会话实测）；
③ 判据文件 sha256 不变 ⇒ 你的重放结论应与起票会话一致，若不一致**先怀疑自己接错了输入**（起票会话在此翻过车）。

**回给 Owner 的格式**（照抄填数，别自由发挥）：

```
P1–P7：<逐条 读数 / 是否符合期望>
HEAD=<hash>   verdict=RUN_VALID|RUN_VOID   pytest 末行=<passed/deselected/failed 计数>
产物=dispatch-output/te-chroma-isolation-20260918/gate-<标签>.log, -source-sha.json, -verdict.txt
本次改动=<无 | 文件清单>   未推送未部署=是
若要动 §4 任一项：<编号 + 你要什么授权>
```

## 4. 不许你动的（等 Owner 表态）

| 项 | 状态 | 你要动之前必须先得到什么 |
|---|---|---|
| B1 `scope_trigger` 升格为判据 | 建议**不升格**；且"只作记录"这句**已经写在冻结文件 `evals/frozen-cases-v2.json:8`** ⇒ 无需再动，照字面去"降级"就是破冻结 | Owner 明说改什么、改哪份非冻结文件 |
| B2 词表收紧（专有名词白名单） | 改词表=改生产语义 | 授权；且先给误伤样本的 watch-it-fail 再谈收紧 |
| B3 T-K 跨域引用收紧 | 执行书 `docs/execution-plan-entity-precision-20260917.md:360` 明写"不再投入"，`:367-368` 明写"不因新证据自动重开；若要动须 Owner 明确推翻" | Owner 白纸推翻负面清单 |
| B4 T-H 过度保守修复 | 需付费额度 | 额度 |
| B5 P1-4 REWRITE 不触发第二轮 writer | 生产语义；注释在 `backend/agent/service.py:492`「非 PASS（RESEARCH_MORE/REWRITE/FAIL_SAFE）即终态失败（fail-closed），不触发第二轮 writer」 | 授权或否决 |
| C1 追「gate5 20/20」的 run 标签 / C2 给执行书加注 / C3 造预算=3 样本 | 起票者建议**不做**（理由见进度报告 §5-C） | Owner 不同意就照他说的做，并在此行追加"已改判"日期 |
| D 安全告警两条（CORS `main.py:944`、DEBUG `:1025`） | 起票会话实测：两条**与当时的树不符**（`:944` 是别的语句、CORS 实为 `:266-272` 读 `_CORS_ORIGINS`；全仓 `grep settings.DEBUG` 0 命中）。Owner 令"只记不修" | 若你在新版本里真看到，重新取证再报，别照抄本行 |

## 5. 收口纪律（本仓硬事实，不是风格偏好）

- `.git/hooks/pre-commit` **未安装**（本会话实测）⇒ 提交前必须手跑
  `backend/venv/Scripts/pre-commit.exe run --files <显式路径>`；可执行文件名是 `pre-commit.exe`（**不是** `pre_commit.exe`）。
- 提交只 `git add` **显式路径**，禁 `git add -A` / `.`；提交前 `git diff --cached --name-only` 核对；禁 `git stash` / `reset --hard` / `clean`。
- **永不 amend 已发布的提交**；出错就补一笔新提交（起票会话就是这么处理 `e3c023a` → `b61bc08` → `105907b` → `4465080` 的）。
- 交付说明类文档按 `docs/` **未跟踪**惯例留在工作树；产物目录 `dispatch-output/<票名-日期>/` 里被票要求的那几件才提交。
- 声称"通过/达标"之前，五问自答：数字怎么来、能否复现、测试**亲眼红过吗**、期望值**独立吗**、已知限制是什么。
  "删掉实现就变红"只证明实现缺席时会红，分不清断言锚的是数值还是代码形状 ⇒ 要做**定向变异**；
  pytest 只报第一条失败断言 ⇒ 后面没单独变红过的断言要如实降级为"未验证"。

## 6. 命令写法层面的四个坑（都会导致假结论）

1. 前台 shell 是 Git Bash（`bash.exe`），不是 PowerShell；`cd .. && grep …` 若 cwd 已在仓库根就会**扫到桌面**。
2. 计数**不得**在 `| head` 之后做（会被截断）；退出码不得经管道取。
3. here-doc 里 `\\` 会被折叠 ⇒ 路径用正斜杠或 `pathlib`；给已有文件打补丁用编辑工具，别用 `sed`。
4. **仪器一旦失效，那一整次调用的所有读数全部作废**，不许只重跑其中一部分（起票会话为此返工过一次）。

## 7. 文件索引

| 要看什么 | 路径 |
|---|---|
| 判据重放脚本 / 绊线探针 / 三件产物 | `dispatch-output/over2-replay-20260919/`（`over2_replay.py`、`_over2_tripwire.py`、`run-manifest.json`、`replay-results.json`、`over2-replay-report.md`） |
| 全量门禁跑者 | `dispatch-output/te-chroma-isolation-20260918/run_gate_full.py` |
| 前序交接与裁决台账 | `dispatch-output/ta5-arms-20260917/handover-20260918.md` §13.1/§13.3/§13.7/§13.8 |
| 计划与订正 | `docs/superpowers/plans/2026-09-19-over2-replay-audit.md`（含「结论订正」一节） |
| 当前进度与待办 | `docs/progress-and-backlog-20260919.md` |

**卡住就回问 Owner**，不要自行扩范围。提问时带上：你的 P1–P7 读数 + 你想动的那一项的编号。
