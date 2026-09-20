# W1a 试点派发记录（4 张）· 2026-09-20 22:4x

## 派发清单（trace_id ↔ 执行体）

| 卡 | trace_id | 交付目录 | 并发体 task_id | 状态 |
|---|---|---|---|---|
| T1 | `t1-flaky-20260920` | `dispatch-output\t1-flaky-20260920\` | `agent-a7501b95` | 运行中（重，5 轮全量） |
| T3 | `t3-appdb-20260920` | `dispatch-output\t3-appdb-20260920\` | `agent-eec7bd8f` | 运行中（只读） |
| T6 | `t6-sourcekey-survey-20260920` | `dispatch-output\t6-sourcekey-survey-20260920\` | `agent-f7428014` | 运行中（只读） |
| T9 | `t9-eval-credibility-20260920` | `dispatch-output\t9-eval-credibility-20260920\` | `agent-f0dfd6d9` | 运行中（只读） |

**未派发（按 W1a 顺序表）**：T4、T7、T8、T10（等试点验证"回报形状 + 验收闸"后再放量）；T12（W1b，须等 T1 收工）。

## 派发时的基线（第 3 次重锚，2026-09-20 22:37:15）

| 项 | 值 |
|---|---|
| HEAD | `beb4d5c09a7a28e2987488b86031780f6ed7d8c5`（票 I 的 `fix(票 I · I-6/I-3)`） |
| `backend/main.py` | **票 I 在途**（22:36 写入 `+18/-1`，size 134765→136165）⇒ 本波对它只读、且结论必须锚定哈希 |
| `backend/retrieval.py` | 已由票 I 在 `beb4d5c` 合入 I-6（稳定） |
| `backend/gate_exit_registry.py` + `docs/gate-exit-registry.md` | 票 I 已回表（本波无人回表 ⇒ 无冲突） |
| `backend/scripts/gate2_runner.py` | `ae2e4120…` 与 22:21 读数一致 ⇒ 冻结件全程未被触碰 |
| 未跟踪项 | 409（22:21 为 396） |
| T1 副本树 commit | `1e969f2`（21:49，早于票 I 的全部 backend 改动 ⇒ T1 读数天然干净） |

## 三条串行面（本波开工瞬间的状态）

| 串行面 | 状态 | 后果 |
|---|---|---|
| T2 / T11 vs 票 I | **关闭**（判据 0/3：`main.py` 正在被写、hij-i 目录仍在产出、无 report） | W2 不许开 |
| T7 补采实现 vs 票 I 的语料写入 | 本波无 T7 补采实现（T7 只算不写） | 无冲突 |
| 任何"回表"动作之间 | 本波无人回表 | 无冲突 |

## 派发前我确认过的事（"确认一遍"清单）

1. `1e969f2` 可取（`git cat-file -t` → `commit`）✅
2. 4 张卡的交付目录**均不存在**（不会覆盖既有产物）✅
3. 工具齐备：`make_copytree.py` / `run_mutations_full.py`（有 `failed_set:74`、`suite_stats:57`）/ `probe_real_db_readonly.py` / `backend\tests\_sse_harness.py` ✅
4. 磁盘余量：C 盘 87 GB 可用（T1 要搭副本树 + 5 份 junit）✅
5. 冻结件 `gate2_runner.py` 未被触碰（两次读数同哈希）✅
6. 禁令面已写进每张卡的提示（禁 git 写 / 禁改 `backend/**` / 禁碰票 I 在途物与另一会话在途文件）✅

## 派发后 5 分钟内的两条实测（**含一次追加约束**）

| 时刻 | 观察到什么 | 我做了什么 |
|---|---|---|
| 22:4x | 4 个试点交付目录**尚未出现**（并发体刚起，还在读必读文件）⇒ 不能说"已在产出" | 如实登记；等回报后用 `verify_deliverables.py` 做结构性验收 |
| 22:4x | 票 I 又动了 **`backend/knowledge_service.py`**（`M`），并新增 `backend/tests/test_qa_direct_return_version_guard.py`；`main.py` 仍在写 | ⚠️ **`knowledge_service.py` 正在 T6 的射程里** ⇒ 已给 T6 那条线追加约束：报告须额外锚定它的 sha256、标注"读数期间仍被外部会话修改中"、哈希前后不一致就把两次读数都记下 |

**为什么这条值得单独记**：T6 的普查对象"逐调用点"里正好含 `knowledge_service.py` ——
若不追加这条，T6 会给出**对着漂移版本的单点结论**，事后无人能发现（这正是 §3-C1 那类冲突的第二次实例）。

---

## 验收记录（滚动）

### T3 · 结构性 ✅ / 语义 **驳回 1 项**（2026-09-20 22:4x）

- 结构性验收闸：`T3 2/2 产物齐`、`sentinel alarm=0` ⇒ 落地没问题。
- 我**独立复核**（`probe_cc_independent.py`，自己实现、不复用 T3 脚本）：
  `backend/app.db` cc=10784/size=20205568/write_format=1；`backend/data/app.db` cc=10710/size=19939328/write_format=1；
  `quota_used.sqlite` cc=2/write_format=2 ⇒ **与 T3 读数逐字一致**。
- **主答案我认可**：两份 `app.db` 今天（09-20）都没有被写；cc 在非 WAL（write_format=1）下不变 ⇒ 无提交事务，
  这个判据比 size/mtime 硬，我接受。
- **驳回 1 项（归属）**：T3 把"生产真源"判成 `backend/app.db`（根）、把 `backend/data/app.db` 判成"停滞副本"。
  **反证三源**：`docker-compose.yml:43`（`DATABASE_URL=sqlite:////data/app.db` 写死）+ `:50`（`./backend/data:/data`）、
  `docs/handoff-takeover-20260918.md:139`（生产=Docker、容器 DB=`backend/data/app.db`）、
  S7 备份命名 `data_app.db`="容器侧 app.db"（size 19939328 = cc 10710 那份）；
  另核实根 `.env` 无 `DATABASE_URL` 覆盖、无 compose override 文件。
  ⇒ **正解**：生产真源 = `backend/data/app.db`（cc 10710，自 09-17 停滞，与"生产零流量"自洽）；
  `backend/app.db`（根，cc 10784，09-19 被写）= **宿主机本地进程的默认库**（`database.py:9` 回落），
  那次写入正是 T3 自己判定的"R15 三臂评测批"——**评测流量，不是生产流量**。
  **方法层教训**：T3 把"最近被写"当成了"谁是生产真源"的判据 ⇒ 判据选错了（该用配置/挂载，不是时间）。
- 处置：已退回 T3 那条线（第 1 次），要求只改 `report.md` 的归属列 + 结论 + 口径冲突段，**不重跑读数**。

**为什么这条值得记**：这正是"不盲信子 agent 声称"的价值 —— 读数层全对、叙述层错一格，
若直接转述给 Owner，**会把"生产库是哪份"这个长期事实记反**（而它已经被写错在 T3 卡与长期记忆里）。

---

### T6 · 结构性 ✅ / 语义 **通过**（1 处行号小瑕疵，不驳回）

- 交付：`t6-sourcekey-survey-20260920\`（`survey.md` 14241B、`call-sites.json` 10412B）；验收闸 `2/2`。
- **我逐个调用点回读代码核验**（不盲信报告），**行号与结论全部对上**：
  | 调用点 | 我读到的原文 | 与 T6 一致？ |
  |---|---|---|
  | KS-1 `knowledge_service.py:204` | `where={"$and": [{"source": source}, {"article": article}]}`（L204-207） | ✅ |
  | G1-2 `gen_gate1_law_check.py:92` | `col.get(where={"$and": [{"source": {"$eq": source}}, ...]}, limit=5)` | ✅ |
  | IL-3 `import_laws.py:74` | `_seed_conflict`: `where={"$and": [{"source": title}, {"article": article}]}` | ✅ |
  | IL-4 `import_laws.py` 主体 | `where=` 实测在 **L116**（T6 写 L115） | ⚠️ 差 1 行（cosmetic，不驳回） |
  | ID-5 `import_docs.py:64` | `ids = _col().get(where={"source": source})["ids"]` | ✅ |
  | ID-6 `import_docs.py:92` | `seed_hits = _col().get(where={"$and": [{"source": source}, {"origin": "seed"}]}, ...)` | ✅ |
- **T6 自陈"未独立复现"的那条，我给它补上了实证**（比它自己的依据更硬）：
  `data/laws_clean\中华人民共和国宪法（1982年）_19821204.txt` **确实存在**；
  而 `import_docs.py:35-55` 的 `short_source` 只剥 `_\d{8}$` 与**前缀**"中华人民共和国"、**不剥括号**
  ⇒ 库内 source 就是 `宪法（1982年）` ⇒ 短名"宪法"查不到它 = **KS-1/IL-4 的漏命中是真缺口，不是理论假设**。
  另：`data/eval_set.json` 里也出现 1982，可作旁证。
- **它自己标注为"推断未实证"的那条，我也关掉了**：`gen_gate1_law_check.py:19-33` 的 `TARGETS` 实测只有
  劳动法 / 劳动合同法 / 民法典（**无宪法**）⇒ G1-2"当前不需修"成立；但若日后把宪法加进去就会静默漏，
  T6 把它列为"防御性可加项"**判断正确**。
- **IL-3"不需修"由源码自证**：`import_docs.py:39-47` 的 `SEED_FRAGMENTS` 5 部种子法全是 clean 名
  （无宪法）⇒ 与 T6 结论一致。
- 结论采纳：**要修 2 处（KS-1、IL-4）、当前不需修 4 处**；修法一律指向复用既有 `_source_key`，
  **没有另写第二份"去括注"正则** ✅（卡里明令禁止的那条守住了）。

### 哨兵报警调查（22:48，`alarm=1`）——**已归因，不是本波的卡**

验收闸报 `backend/gate_exit_registry.py` SHA_DRIFT（baseline `62d43e9a…`）。我 1 分钟内连测两次，
它已经是 **`340ce56b…` → `1826d087…`**（还在变）⇒ **有进程正在写它**。

**归因结论：外部会话（票 I）**，不是本波任何一张卡。证据：
1. 同批脏文件 = `main.py` + `knowledge_service.py` + registry.py，并新增未跟踪
   `backend/tests/test_qa_direct_return_version_guard.py` —— 文件名直指"QA 直返的版本护栏"，
   正是票 I 票面（E2 缓存复用型答复的版本判定 + E1/E2 回表）的内容；
2. 本波 4 张卡全是只读（T1 只往副本树写、T3/T6/T9 只读），其中 T6 已收工、T3 已收工，
   它们的越界写声明都是"无"，且产物只落在自己的交付目录；
3. registry.py 是票 I 的既有领地（它已在 `beb4d5c` 里改过一次）。

**由此得到三条新事实（比告警本身更重要）**：
- **`docs/gate-exit-registry.md` 目前未同步**：`registry.py` 已改，而 md 的哈希仍是 `66cbc94c…`
  （与 22:37 相同）⇒ **代码真源与生成物当前不同步**；谁日后"回表"都必须先重新生成 md，否则会把旧内容写回去。
- **W2 判据①被进一步坐实失效**（`backend` 下已跟踪脏文件 3 个，且 registry 还在被改）⇒ T2/T11 继续关闭。
- **`drift_alarm` 语义需要细化**：registry 被判 alarm 是**设计正确**（本波无人回表 ⇒ 任何改动都该被看见），
  但归因必须人工做 —— 我把它记为"外部写入，已归因"，**不停手本波的卡**（它们没有写面）。
- 已同步给 T9 那条线：`main.py` 又一漂移（`a31b7b4c…` → `4807cc9e…`），要求它**现测锚定 + 按符号不按行号**。

---

### T3 ·（修订后）**通过** —— 修订已核实真落盘

- 我用 `grep` 核了修订结果：§① 已改判为 `backend/data/app.db` 是生产真源（并写入 `docker-compose.yml:43/50` 依据）、
  新增"⚠️ 修订记录"段、**旧的错判句已完全消失**；目录 mtime 显示**只有 `report.md`（22:50）变，
  其余 5 份读数产物仍是 22:40–22:41 未动** ⇒ 严格按"只改报告不重跑"执行 ✅
- 这正是必须核的理由：本仓有"**声称编辑成功 ≠ 落盘**"的前科（见长期记忆）。

### T9 · 结构性 ✅ / 符号层 **通过**，但**要求补一条漏掉的既有护栏**

- 交付：`t9-eval-credibility-20260920\`（`checklist.md`、`findings.json`）⇒ 验收闸 `2/2`。
- **我按符号核（不按行号，因为 `main.py`/`registry.py` 正在被外部会话改）**，逐条命中：
  `main.py:1740` `cache_key = None if body.no_cache else (...)` ✅ 逐字；
  `main.py:1792`（T9 写 1793）`None if body.no_cache else await run_in_threadpool(_qa_direct_return, ...)` ✅；
  `schemas.py:55` `no_cache: bool = False` ✅（连注释都对）；
  `answer_cache.py:17` `_cache = rc.LRU(maxsize=512)` ✅；
  `routing_metrics.py:143` `"cache_hit_rate": round(_cache_hit / total, 3) if total else 0.0` ✅。
- **它漏了一条我实测出来的既有护栏（已要求补进去）**：全仓 `no_cache` 普查显示
  **既有评测入口全部已显式传 `no_cache=True`**（`capture_eval.py:308`、`eval_contract.py:104`、
  `eval_exam.py:120`、`eval_exam_professional.py:69`、`gate2_probe.py:64`、`gate2_runner.py:80/542`、
  `acceptance.py:20`、`smoke_b1b5.py:16`），客户端默认是 False（`_client.py:57-59`）；
  且 **`tests/test_r15_runner_injection.py:40` 断言了 gate2_runner 的 payload 含 `no_cache: True`** ⇒
  那一处**有单测锁死**。登记表自己也写了要求（`gate_exit_registry.py:170`）。
  ⇒ C1/C2 的"今天是否已被防住"应从「否（不自动）」细化为
  「**默认不防 + 既有入口全部显式传 + 一处有单测锁 ⇒ 真实风险是"新写的评测入口漏传"**」，
  并要它新增一条可机械执行的新入口检查闸。**这改变了这条 check 的用法，不只是补个脚注。**
- 它给的 C4/C5/C6"否"我认可（方法论/版本护栏/题集重叠确实都没有代码强制）。

---

### ⚠️ 我在 T9 这张卡上犯过一个测量错误，已回撤（必须留痕）

**我上一条给 T9 的"证据"是错的**：我说"既有 7 处评测入口全部已显式传 `no_cache=True`"⇒ 要求它把
C1/C2 定性为"将来新增入口漏传的风险"。**实测推翻**。

- **错因（方法层）**：我是用 `grep -n 'no_cache'` 去"找护栏证据"——**那条命令只可能命中有该串的行，
  天然看不见漏传的调用点**。这是"用检索代替枚举"的选择偏差。**正确顺序是先枚举调用点全集、再逐条判**。
- **我怎么发现的**：**执行 T9 自己给的那条闸命令**（`grep -rnE "_client\.chat\(|chat_stream\(" … | grep -v no_cache=`），
  它当场吐出了 6 个没有 no_cache 的既有评测入口。
  ⇒ 一个执行者给的"可执行闸"，比自己写的"证据"更能纠正审阅者 —— 这条值得单独记住。
- **实测的准确口径**（`backend/scripts` 下经 `_client.chat(` / `chat_stream(` 的调用点，共 13 处）：
  - 传 `no_cache=True`：**4 处**（`capture_eval.py:308`、`eval_contract.py:104`、`eval_exam.py:120`、`eval_exam_professional.py:69`）
  - **漏传（= 默认 False ⇒ 缓存暴露）：6 个脚本 / 7 处**
    （`eval_consistency.py:67`、`:68`、`eval_hallucination.py:40`、`eval_negative_run.py:41`、
    `eval_quality.py:60`、`eval_redteam.py:58`、`eval_relevance.py:41`）
  - 另一类（**不进这 13 处口径**）：`gate2_probe.py:64`、`gate2_runner.py:80/542`、`acceptance.py:20`、
    `smoke_b1b5.py:16` 直接构造 payload，都传了 True。**两类不可混算分子分母。**
- **意义（比"补一条脚注"大得多）**：**当下就有 6 个既有评测入口处于缓存暴露状态**
  （一致性 / 幻觉 / 拒答 / 质量 / 红队 / 相关性），这才是登记表 E1/E2「评测可信度」至今 `BLOCKED` 的实锤之一 ——
  **不是"将来会漏"，而是"现在就是漏的"**。T9 原来的"否（不自动）"判断是对的，错的是我。
- 处置：已回撤我上一条指令，要求 T9 按实测改写 C1/C2（改成"当下暴露"+ 6 脚本即时风险清单），
  并修那条闸命令的两个缺陷（把 `def chat_stream(...)` 定义行当调用点的**假阳性**；
  单行 grep 看不见多行调用的**假阴性** ⇒ 补一条 **AST 版**检查，形态对齐本仓既有的 `observability._ACCOUNT_FIELDS` AST 哨兵）。

---

### AST 闸实跑（23:1x）——把 T9 的闸从"纸面"变成"验过"（结果又更准了一层）

我把 T9 嵌在 checklist.md 里的 AST 片段抽出来原样跑（`probe_no_cache_ast_gate.py`，含双向判定）：

- **22 处调用点 / 18 处 LEAK** —— 比 grep 口径（13/7）和 T9 正文（13/7）都多 ⇒ **正文与它自己推荐的闸数字对不上**，这就是必须实跑的理由。
- 多出的 11 处我逐个查了 wrapper 本体，**三类判读**：
  | 类 | 处数 | 判定 |
  |---|---|---|
  | wrapper 假阳性（本地 `def chat()` 内部已传 True：`acceptance.py:19`、`smoke_b1b5.py:15`） | 8 | 不漏（闸按裸名误抓 wrapper 的调用点） |
  | **新增真漏**（`smoke_citation_full.py:42` 的 wrapper 用**裸 urllib** 构造 body，连 no_cache 字段都没有） | 3（:109/:117/:131） | **真漏** |
  | 原有评测类真漏 | 7 | 真漏 |
- **最终口径：真漏 10 处 / 7 个脚本**（评测类 6 + smoke 类 1）。已按此给 T9 下终版修订令（第 2 次，也是最后一次）。
- **闸的双向验证**：4 处已传者全部正确落在 PASS、未进 LEAK（无假阳）✓；`capture_eval.py:183` 定义行未被误报（T9 点名的假阳性已消除）✓ —— 闸不是空枪。
- **AST 闸的残余缺陷（已要求写进文档第③条）**：按裸名匹配 ⇒ wrapper 调用点需人工解引用；
  进阶形态 = 沿 ast 找本文件同名 FunctionDef 递归查 no_cache（本次未实现，注明即可）。

### 会话中断与恢复（23:13）

- T1 / T3 / T6 / T9 四条线被运行时打断（paused）。**以磁盘产物盘点断点，不信状态字段**：
  - T1：`run-1/2/3` 完成（stdout 各 4682B）、`run-4` 完成（stdout 31250B，**有红**）、`bt5` 已建但 **run-5 缺失** ⇒ 已令其从第 5 轮继续；
  - T3：已收工+修订验收通过，无需恢复；
  - T6：已收工验收通过，无需恢复；
  - T9：已下发终版口径（10 处/7 脚本），等其回报。

---

### T9 ·（终版）**通过** —— 双口径并陈、数字一致（23:1x）

- checklist.md 与 findings.json 的 C1/C2 均改为"真漏 **10 处 / 7 个脚本**"（评测类 6 脚本 7 处 + smoke_citation_full 3 处，后者单列注明"smoke 类、裸 urllib、连 no_cache 字段都没有"）；旧口径"6 脚本/7 处"**零残留**（grep 实测）。
- AST 闸补了第 ③ 条已知缺陷（裸名匹配会误抓"内部已传 True 的本地 wrapper"），给了 a) 人工解引用（本次采用，附三类判读示例）/ b) 沿 ast 解引用（建议形态、未实现）两个处置。
- findings.json `json.load` 通过；C1/C2 字段含 10/7/smoke/wrapper 全部内容（实测抽查）。
- **这张卡的最终价值**：E1/E2「评测可信度」BLOCKED 的实锤从"方法论风险"升级为"**当下 10 处调用点读数不可信**"。

### W2 三判据重测（23:20）——**3/3 成立，门开**（但因 C5 排在 T1 之后起跑）

| 判据 | 读数 | 结果 |
|---|---|---|
| ① backend 无未提交已跟踪改动 | 空（票 I 已全部提交） | ✅ |
| ② hij-i 目录静默 ≥5 分钟 | 末次活动 23:06，现 23:20 ⇒ 静默 14 分钟 | ✅ |
| ③ 票 I report 落地 | `hij-i-20260920\report.md`（13598B）且已入库 `d10dea5` | ✅ |

**票 I 收工的外部证据**（这两条提交同时解释了哨兵 alarm=2）：
- `1fb8ef1`（22:49）feat(票 I · I-2(a))：给 QA 语料标版本基准日 + 第四道护栏；**E1/E2 回表收口**
  ⇒ **registry.py 与 `docs\gate-exit-registry.md` 同时被改并提交** ⇒ 之前"代码真源与生成物不同步"的状态已解除；
  alarm=2 归因为票 I 的回表，非本波的卡。
- `d10dea5`（23:05）票 I 报告入库（**变异 5/5 KILLED**）。
- **对本波的影响**：票 I 往真实 `qa_pairs` 写了版本基准日 ⇒ **T7 尚未派发，等它跑时必须按"语料已被票 I 写过"的新状态取证**（不能再按 60/279 旧读数假设）。

**W2 排程决定**：门虽开，但 **T1 的第 5 轮正在跑（重载）** ⇒ 按 C5（T1 期间不叠加第二个重载），
**T2 → T11 排在 T1 收工后立刻串行起跑**。

### T1 run-5 轮廓异常（23:21 体检）——已下分诊令

`run-5`：`1155 passed, 10 skipped, 18 deselected, 225 errors in 106.19s` —— **106 秒跑完**（前四轮每轮约 6 分钟）+ 225 个 error，形态不像真 flaky，像环境级断裂（本仓有 safe-delete 批量守卫造成"整轮假失败"的前科）。
已令 T1：先读 ERROR 块原文分诊 a) 环境断裂 / b) 真失败；若 a 则用**唯一允许的补跑轮**（第 6 轮 `bt6`），run-5 标 `INVALID` 留盘；矩阵必须带"轮次健康度"节（每轮耗时+计数+有效性）。

---

### T1 ·（复核后）**通过** —— "flaky 簇"实为沙箱 safe-delete 守卫假读数（23:3x）

- **独立复算（不读它的结论，直接从 5 份 junit 重算）**：run-1/2/3/5 = `1390 tests / 0 err / 0 failed`，
  run-4 = `1390 / 0 err / **6 failed**`，6 条与红名单逐字一致；matrix.json 的 `rounds=5` ✓。
  （探针：`probe_t1_matrix_check.py`；它自己还吃了一个路径 bug——`sys.path` 多写一层 `.parent`，已修，
  这条也记下来：**探针先打自己的脸，才配审别人**。）
- **根因证据直读产物**：`run-4.stdout.txt` 含 **12 处 `SAFE_DELETE_BULK_CONFIRM_REQUIRED` + 18 处 `SystemExit`**
  ⇒ 6 条红 = 守卫中止测试进程，不是产品缺陷。与长期记忆里那条"沙箱 safe-delete 批量守卫"前科吻合，
  并补齐了机制细节：**守卫 scope=turn、阈值 50；turn 内跨轮累计，第 4 轮跨过 50 ⇒ 只第 4 轮红；
  新会话=新 turn ⇒ 归零**。这同时解释了历史上 0/3/8 红的波动。
- **两条新环境坑（T1 实测，已入库长期记忆）**：
  1. `--basetemp`/`--junitxml` 必须 **`C:/...` 原生形态**；`/c/Users` 风格被 Python 当相对路径 ⇒ `C:\c\Users` 不存在 ⇒ **整轮 225 setup error 假读数**（正是我 23:21 体检到的 run-5 异常的根因之一）；
  2. 复用含残留的 `--basetemp` 目录会触发守卫（bt5 残留 421 文件 > 50）⇒ rename 旧目录让 pytest 重建空目录。
- **验收判据的一条修订（需 Owner 知情）**：卡上"我复跑 ≥3 次、矩阵逐格一致"在守卫语义下**不是正确判据**——
  守卫计数按 turn 归零/累计，逐格复刻既不可靠也不必要。替代判据（本次已执行）：**junit 独立复算对格 +
  traceback 直指守卫 + 机制能解释历史 0/3/8 波动**。若 Owner 坚持重跑，需先想清楚 turn 语义。
- 诚实登记核对：另 2 条红名单用例 0/5 复现 ⇒ 按"0 次复现不算"如实不列为 flaky（但指出同脆弱面）✅
- **T1 的附加建议值得上报 Owner**：全量门禁环境若不豁免该守卫，任何"全量红/绿"读数都可能被污染
  （含即将跑的 T11）⇒ 已把该风险写进 T11 的派发前置（见下）。

### W2 开跑（23:4x）

- 判据 3/3（23:41 复测：backend 干净、hij-i 静默 ~9 分钟、票 I report 已入库）。
- 23:34 又入一笔 `2a48f3e`（三票双轴审查整改：**只动 `backend/tests/**` 与文档，产品码未动**）⇒ 基线第 4 次重锚至 `2a48f3e`。
- **T2 已派发**（fresh agent `general-purpose-10`，trace `t2-slow-20260920`）：live 树跑 `-m slow` 18 条 + `-m "not slow"` 对照，判据含 `1408 = 1390 + 18` 分母对账、skip/failed 分列、T1 的两条新环境坑写入前置。
- **T11 排在 T2 之后**（串行纪律）；派发时将附 T1 的守卫风险前置：若门禁轮出现"批量 setup error"式假读数，按 T1 分诊法判 INVALID，不得报绿。

---

### T2 ·（复核后）**通过** —— 18 条 slow 能跑通但有 5 条真失败（23:5x）

- **独立复算两份 junit**（`probe_t2_check.py`，直接从 xml 重算）：slow `(18, 5, 0)`、notslow `(1399, 1, 0)`，5+1 红与回报逐字一致 ✅
- **分母对账修正**：卡写 `1408 = 1390 + 18`，实测 **`1417 = 1399 + 18`**（套件比写卡时多 9 条）⇒ 卡数字作废、按实测上报 —— 正确处理，未硬凑旧数。
- **skip/failed 严格分列** ✅：slow `skipped=0` 且 KB=10266 条 ⇒ 5 红**全是真失败**（`test_scenario_supplement.py`，真实 KB 未命中"补充组"条文），不是环境缺 KB；notslow `skipped=2`（FZ_DUMP_FRAMES 开关门控，合法）。
- **5 条 slow 红的性质**：KB 数据覆盖缺口 / source-key 匹配类（`公司法` 裸名仍查不到 ⇒ 与 T6/票 I-6 的括注问题**同源可疑**）；是否代码回归需 KB provenance 判定，T2 如实标"超只读范围"✅
- **额外卖点（超出卡射程但正确）**：notslow 另有 1 红 `test_phase3::test_chat_streams_persists_and_request_id`（`make_chain` 签名不同步）—— 我查了 `git log -S make_chain -- backend/main.py`，最近一次改动是老的 `76c1eea` ⇒ **这个 2 参调用的来源未定**，如实记"待查"，不臆断。
- **健康度自检方法被正确复用**：notslow 172s < 3min 触发告警 ⇒ 按 T1 的方法自检（分母完整/errors=0/与 slow 自洽）判有效 ✅ —— 前一张卡的产出成了后一张卡的工具，这正是编排想要的复利。

### W2 第二张 T11 开跑（23:5x）

- 前置确认：HEAD=2a48f3e、backend 无已跟踪脏项、hij-i 静默、票 I 报告入库 ⇒ 可独占 live 树。
- **T11 已派发**（fresh agent `general-purpose-11`，标签 `t11-2a48f3e-20260920`）：
  唯一命令 = `run_gate_full.py <标签>`（不许裸跑 pytest）；判据双轨（RUN_VALID 才认回归读数 / 隔离判据 RUN_VOID 也有效）；
  **期望值诚实前置**：已知 1 条 notslow 真失败会复现，如实记录就是交付，**不得为了让它变绿做任何事**；
  T1 的守卫坑写入前置自检（批量 setup error / SAFE_DELETE 字样 ⇒ INVALID 分诊，不许报绿，也不许绕守卫）。
- 交付：`gate-t11-2a48f3e-20260920.{log,-source-sha.json,-verdict.txt}` + report.md，落 `te-chroma-isolation-20260918\`。

---

### T11 · **通过（RUN_VALID）** —— 执行体 429 中断于写报告阶段，门禁轮本身完整跑完（23:5x）

- **失败报告的真相（必须记）**：执行体 `general-purpose-11` 收到平台 429 限流（00:02:39 重置）而 failed；
  但盘点磁盘发现**门禁轮已完整跑完**（三件套 23:56 落盘、log 静止不增长）——它死在"写报告"，不是死在跑。
  ⇒ **判成败看产物，不看执行体状态**——这条纪律又一次值回票价。
- **验收（全部独立复核）**：
  - `source-sha.json` 的 `changed = []` ⇒ 源码全程未变 ⇒ **verdict = RUN_VALID**，回归读数可用；
  - 隔离判据：chroma 指纹前==后（`f1459fda…`），`legal_provisions_cos: 10266`、`qa_pairs: 279`、`qa_pairs_te4: 21`；
    `app.db cc 10784→10784`、`quota cc 2→2` ⇒ **真实库零写入**；
  - 末行 `1 failed, 1396 passed, 2 skipped, 18 deselected in 159.59s` —— 唯一 failed 即 T2 已记录的
    `test_phase3::test_chat_streams_persists_and_request_id`（两卡互证）；
  - 健康度：159.59s/1399 条，与 T2 的 172s 同量级 ⇒ 非 T1 式假读数；`SAFE_DELETE`/`SystemExit` 0 命中 ⇒ 守卫本轮未触发。
- 报告由主会话代写（数字全部经独立复算）：`te-chroma-isolation-20260918\gate-t11-2a48f3e-20260920-report.md`。
- **HEAD 的真实状态（交 Owner）**：不全绿，构成 = ① `test_phase3` make_chain 签名不同步（来源未定）+
  ② `test_scenario_supplement` 5 条 KB 覆盖缺口（与源名括注同源可疑）。是否修、怎么修 = 产品侧决策。
- gate2_runner.py 冻结件 sha256 全程一致 ✅。

---

### 余量五卡放量（00:0x，限流重置后）

| 卡 | trace_id | 交付目录 | 并发体 task_id | 特记 |
|---|---|---|---|---|
| T4 | `t4-assets-20260920` | `t4-assets-20260920\` | `agent-06a8a89a` | 快照时刻 + 本波自产单列 + 外部在途物标"别动" |
| T7 | `t7-fingerprint-coverage-20260920` | `t7-fingerprint-coverage-20260920\` | `agent-d864c0d8` | **语料已被票 I 写过版本基准日** ⇒ 必须现点数，禁用 60/279 旧读数当现状 |
| T8 | `t8-e2-multi-20260920` | `t8-e2-multi-20260920\` | `agent-ac57daa5` | E2 段已被票 I 回表更新 ⇒ 以实测为准；须回答与"第四道护栏"是否正交 |
| T10 | `t10-disabled-taxonomy-20260920` | `t10-disabled-taxonomy-20260920\` | `agent-01623507` | 22:09 旧扫描可能过期 ⇒ 自己重扫 + 与旧数对账，两套数字并陈 |
| T12 | `t12-frontend-sweep-20260920` | `t12-frontend-sweep-20260920\` | `agent-5a0920e5` | T1 已收工 ⇒ 重载窗口空，可跑构建；构建写盘须报告 |

全部只读、写集互斥；T8 若跑探针用全新 basetemp（T1 坑）；T7 禁语料写入。

---

### T7 ·（复核后）**通过** —— 指纹缺口的写侧根因锁定 + 补采测算给数（00:1x）

- **写侧出处核验**：`gen_qa_corpus.py:177-178` 原文确认（`_options_fingerprint(q)` → `add_qa_pair(..., fingerprint=...)`）；
  全仓 grep 证实**唯一**：`knowledge_service.py:323/372`（create/decide_candidate）与 `qa_seeds.py:62` 三处
  `add_qa_pair` 调用**全都不传 fingerprint** ⇒ "其它写库路径从没算过指纹"成立。
- **读数独立复现**：跑它的探针前先过只读哨兵（`add/update/delete/upsert` 0 命中）⇒ 实跑输出
  **`total=279 stored_nonempty=60 recomp_nonempty=168`**，与回报逐字一致。
- **关键数字**：缺口 **108 条**（18 键在值空 + 90 无键）；补采回填后——全库 21.5%→**60.2%**、
  带选项题 **35.7%→100%**，堵上 `main.py:1138` 那道"stored_fp 非空才生效"的 C4 护栏缺口。
- 诚实登记合格：166→168 的 +2 未追因（如实标注）、108 条未逐条溯源（metadata 无法区分路径）、补采未执行（T7 只读 + 与票 I 串行）✅
- **给 Owner 的决策点**：补采是"回填 108 条现算指纹"，纯写语料、无 LLM 成本——但它写真实 `qa_pairs`，
  按纪律须 Owner 点头后才立项（票 I 的语料写入已收工，串行面已空）。

---

### T4 ·（抽查后）**通过** —— 附带一个**必须交 Owner 的新异常**（00:2x）

- **抽查实证**：① 26 个根级"中文句命名目录"**真实存在**——我亲眼列出 8 个，形如
  `**R1-OB**=判域输入扩展方案，三者独立开关、独立可回滚。`、`**本文件是唯一的后续任务执行入口。**`
  ——**是拿文档正文当路径建出来的目录**（连 Markdown 的 `**` 粗体符都在名字里）；② 快照时刻已钉（00:16:42）；
  ③ 分类/审计脚本齐（_gather/_probe/_final/_build/_validate 全程留痕）；④ 零删除 ✅
- **口径澄清**：基线"431"是 `git status --porcelain` 的**目录折叠**口径，T4 的 445 entry / 30331 file 是逐文件展开
  ⇒ 两套口径不矛盾（我实测当前 porcelain=446，+1 是快照后的自然漂移）。
- **主结论采纳**：存量主体 = 101 个 prior-wave `dispatch-output` 目录（26163 文件，多为可再生的
  copytree/bt*/mut* 副本 ⇒ "可清理"）；真正该入库的是**结论件**（docs/ 与各 report.md）；
  `outputs/`(54)、`evals/`、`backend/.ptmp-s4-run2`(≈2.2MB) 各归各类。
- **⇒ 交 Owner 的两件事**：① 26 个误建目录是谁/哪段脚本干的（嫌疑：某会话把文档逐行 `mkdir` 了），
  内容确认后可清理；② "可清理"清单只列不删，等你点头。
- T4 的诚实登记合格：`docs/code-review-report-02e3851-20260918.md` 实为**已跟踪**文件（在途被改），
  它如实把它从"未跟踪清单"挪到"别动"区 ✅

---

### T8 ·（复核后）**通过** —— 缺口确存，但"照搬票 J 补判定"被有据否决（00:2x）

- **结构性主张核验**：`_qa_direct_return`（`main.py:1107` 起）函数体内 `multi_incomplete` **0 命中**（awk 实测）
  ⇒ E2 不查多选完整性即直返，「代码路径=会命中」成立。
- **探针只读哨兵**（add/update/delete/upsert 0 命中）后**独立重跑**：52 条候选里 4 条是"点中全选项"（非缺口）、
  **48 条残留疑似下界**，且抽样显示多为**抽取器对 markdown 逐项判断（`### 选项X\n【判断】正确`）的漏识**
  ⇒ "真实缺口条数不可靠量化"这个诚实结论有据。
- **它的反直觉结论我采纳**：E2 确有结构性缺口，但**不建议照搬票 J 在 E2 加 `multi_incomplete` 判定**——
  ① 削弱零 token 卖点；② 对当前语料**零效果**（279 条命中 0，题干无"多选"关键词，加了是假接线）；
  ③ 要生效须先修 detector 召回（正交任务）。⇒ 建议：维持 E2 多选完整性=DISABLED，
  登记「扩 detector 召回 + 评估补判定」为独立 GAP-TODO。
- 权衡合规：三条判据（实测/量化/权衡）逐条满足；三道既有护栏未动；票 I 第四道护栏（版本绊线，时间维度）
  与多选完整性（内容维度）**正交**的判断成立 ✅

---

### T10 · **数据层通过 + 语义层主会话代拟**（执行体 429 死于成文阶段，05:04 重置）

- **死前进度盘点**：`cells.json`（19 格非 PASS 全带证据原文）+ 自扫脚本已落盘，只差 `taxonomy.md` 成文。
  且其数据层质量高：连票 I 回表把 E1 版本绊线改判 GAP-ACCEPTED 的三段理由都抓全了。
- **读漂移第三实例（必须记）**：它 00:17 扫到的 registry=`30f58211…` 是另一会话**编辑中途的工作树态**；
  00:18 该会话提交 `a97082b`（票 H-2 尾支，产品码 +8/-1），registry 现值 `c60cb245…`。经 diff 核对：
  **a97082b 对登记表只改了 E2 指纹格的取证措辞**（"部分覆盖 60/279"，与 T7 对齐），**状态值零变化**
  ⇒ cells.json 的状态层仍有效，成文时补注差量即可。
- **主会话接管成文**：`taxonomy.md` 已写——19 格逐格判定：**结构性不适用 8 / 今天零流量 4 /
  已裁定接受 4 / 待修 2 / 待 Owner 判读 1（E5-自检证据不足，未强行归类）**；
  新发现：**E3/E4 的"版本绊线 GAP-ACCEPTED"登记词与语义错位**（实为结构性空门）——这正是卡里
  "两种语义不能混"的活例；建议不拆词，若收敛则改判 NA（须 Owner 裁决）。
- 当前对账：DISABLED 11 / GAP-ACCEPTED **6** / BLOCKED **2**（卡上的"11+5"过期，+1 来自票 I 回表）。
- 执行体 05:04 重置后可恢复做终审（其上下文里有完整分析过程）；不恢复也不阻塞批次收口。

---

## 我（主会话）接下来要做的验收动作

1. 4 张卡回报后跑结构性验收：
   ```
   cd C:\Users\33393\Desktop\ai-legal-helper\backend
   .\venv\Scripts\python.exe ..\dispatch-output\takeover-parallel-20260920\verify_deliverables.py
   ```
   期望：`cards_with_all_artifacts` 里 T1/T3/T6/T9 齐；`sentinel: alarm=0`（票 I 的漂移只记录）。
2. 逐卡按 `00-takeover-plan.md` §2 的「我复核什么」**亲自复跑**：
   - T1：复跑卡里那条命令 ≥3 次，矩阵逐格比对；
   - T3：用同一脚本独立读一遍，cc/size/mtime 三列对齐；
   - T6：逐点回读代码核对行号，确认没有第二份规则实现；
   - T9：抽查每条 `文件:符号` 是否真存在 + 核对 `main.py` sha256 基线。
3. 复核通过后**串行入库**：`git add <4 个 report.md / 结构化产物>` + 手跑 pre-commit；
   junit / copytree / bt* 大件不入库。
