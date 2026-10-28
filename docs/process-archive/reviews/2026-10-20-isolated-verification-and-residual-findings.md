# 候选分支 R01–R25 的独立复核与残余发现（2026-10-20）

> 单一来源说明：本文是本次**独立复核**的正式记录。逐项确认表与执行台账在
> `reports/execution-runs/fazhi-full-closeout-20261018-af101aa9bca543b1a9c21fd0bace9780/tickets/audit-r01-r25-confirmation-20261020.md`
> （该目录在主仓 M 属**未跟踪**工作产物）。本文不重复台账内容，只记复核编排、发现与处置。

## 1. 复核对象与范围

- 候选工作树 C：`.worktrees/nondeploy-closeout-20261010`，分支 `codex/nondeploy-closeout-20261010`。
- 范围：`ee5bfef..HEAD`，共 **19 个提交**（标签 R01…R25；复核时 HEAD 为 R25 提交）。
- 复核时点：上述 19 个提交各自跑过 not-slow 全量套件后（作者自述读数 2529–2553 passed / 88.67%–88.79%），
  另加一轮「复核后修复」尚未提交。
- 硬约束（复核者独立核实，不由作者提供）：冻结件零改动、提交纪律（显式路径 / 无 `--no-verify` / 无 force-push）、
  主仓 M 的受保护脏文件不被本范围改动。

## 2. 复核编排

按项目既定纪律「1 主审 + 2 并行验证者，优先验证反证项」派三只**互不共享上下文**的子代理：

- **主审**：全范围通用审查（Standards 轴 + Spec 轴），首要任务是**证伪**作者结论。
- **验证者 A**：独立核实 R21/R22/R24「候选已防护」的三条断言，以及 R23「QA 侧无删除入口」不变式。
- **验证者 B**：独立核实冻结件零改动、主仓边界、提交纪律、并抽样复跑三条定向证据。

三者的 brief 均要求：结论必须附**自己读到或跑到的**命令与读数；明确写出「未能证伪」与「无法验证」的部分。

## 3. 发现与处置

### 3.1 已修（2 条）

**F1（主审，High→Medium）测试隔离缺陷 —— 已修。**
主审把 R15 的新用例与 R20 的新用例**一起跑**时复现 `1 failed`：报错为
`链只被调用 0 次 ⇒ 根本没触发重答，本条是空枪`。根因：两处用了**同一问句**，
而 R20 那条腿会把答案写进**进程级共享**的答案缓存 ⇒ R15 的旗舰腿第二次跑就命中缓存、
`make_chain` 一次都不被调用，断言沦为**空枪**（该缺陷只在跨文件同跑时暴露）。
处置：R15 用**独立问句**，并在请求前 `answer_cache.clear()`。修后把两文件按**两种顺序**各跑一次，
均 `3 passed`（复核者原报的失败已不复现）。

**F2（主审，Low）docstring 边界夸大 —— 已修。**
`llm_registry.calibrate` 的说明称「remaining=R ⇒ quota_left=R」，但 R>total 时 `initial_used` 取 0、
`quota_left` 实为 `total`（钳位）。处置：docstring 显式写出 `R` 被钳到 `[0, total]` 的边界，
并注明调用方应保证 R 在合法区间。

### 3.2 登记（3 条，不改代码，理由随附）

**F3（主审，Medium）R12 提交曾被本地重做 —— 主动披露。**
R12 最初提交为 `4deb507`，因该次提交**误夹带**了一个此前已 `git rm --cached` 暂存的前端文件删除
（`frontend/public/sw.js`），我用 `git reset --mixed HEAD~1` 撤销后以 `9448f26` 重提，使 R12 只含它自己的两个文件。
事实与边界：**本地单提交重做，非 force-push、分支当时无 upstream（未推送）、最终链线性单 parent**；
但它确实**触碰过**本项目「显式路径暂存 + 无历史重写」这两条约束一次 —— 故在此主动披露，
不靠 reflog 被人事后发现。后续提交已改为先查 `status` 再按显式路径暂存。

**F4（验证者 A，Medium）R23 的 AST 不变式只钉「直写」形状 —— 台账措辞已更正。**
验证者 A 实跑 `tests/test_qa_revocation_lifecycle.py`：`11 passed`，那条 AST 用例确实存在且在咬 delete
（真实树 `qa_deletes=[]`；注入 `ks._qa_store._collection.delete(...)` 或 `ks._qa_store.delete(...)` 均使其转红）。
但四种**别名/间接**写法（`store = ks._qa_store` 后再 delete、`from … import _qa_store as qs`、
`getattr(ks._qa_store._collection, "delete")`、把 `delete` 绑成局部变量再调）三断言**仍全绿** ⇒ 可绕过。
处置：台账中 R23 的措辞由「AST 穷举钉住」更正为「**仅钉直写形状，别名可绕过**」；
「加删除必打红不变式」的表述限定为**直写形式**。R23 本身仍裁定「本轮不改」（保留形状 P 的隔离不删语义，
且该文件已声明闭这一格须先有 C03 口径），但把「策略理由」与「技术阻断」分开写，不夸大成后者。

**F5（验证者 A，Low）R22 残余：复核点用 fresh 状态但另两处注入出口不是 —— 补记。**
QA 直返与缓存命中的复核点走 `fresh=True` 状态槽，而另两处注入出口用的是**非 fresh** 状态槽，
两处口径不一致 ⇒ 「在途请求的撤回传播」没有动态证据。台账原已承认该残余，此处补记**具体的不一致位置**（以符号锚点描述，不写行号）。
处置：不改（改它会变更撤回轴的行为，超出 R22「候选已修」的判据范围），登记为残余。

### 3.3 复核者确认成立、作者结论未被证伪的部分

- **R21/R22/R24 的防护点在现行代码中真实存在**（验证者 A）：`create_candidate` 的唯一写入即 `status="pending"`、
  不写 QA 向量、不签 `approval_source`；全仓非测试代码里 `QaCandidate(` 构造仅此一处；
  `decide_candidate` 拒绝分支置 `rejected` + `eligibility="revoked"` + 版本递增，**先 commit 后 invalidate**；
  `qa_eligibility` 拒 revoked/quarantined 与 `approval_source` 为 None/unknown；
  main 在缓存命中后复核依赖、QA 首正文前按 fresh 状态复核。
- **冻结件零改动**（验证者 B）：`backend/agent/evaluator.py`、`backend/agent/verifier.py` 在本范围 `diff --stat` **无输出**，
  全范围 44 个改动文件均不含这两个文件，无改名/删除。
- **提交纪律**（验证者 B）：`rev-list --count` = 19，每提交单 parent、链式线性；
  19 条消息首字节全为 `R`（无 BOM）；无签名绕过痕迹。
- **抽样定向证据全绿**（验证者 B）：`test_llm_failover.py` 44 passed、`test_restore_drill_script.py` 7 passed、
  `test_stream_restart_discards_partial.py` 2 passed；且该文件与 C 树同名文件 sha256 一致（绿反映候选）。
- **主审未能证伪**：R09 无双重记账、R11 的 `/app/data` 四方同源、R15/R19/R20 的「先红」是**功能红**而非桩红。

## 4. 诚实边界（复核本身也有限）

1. **未独立复跑全量**：复核者按 brief 只跑定向单测，故台账里 2529–2553 的全量读数**未被独立复现**；
   这正是本候选分支自己的验收门，由主线程另跑（见提交简报）。
2. **未跑 slow 车道**：沿用 `-m 'not slow'` 口径；范围内仅 `test_import_docs.py` 含 `@pytest.mark.slow` 用例。
3. **`--no-verify` 无法由历史判定**：git 历史无痕迹可查。
4. **前端 R10/R13/R14 的用例是源码级接线钉子**，真机 DOM 行为未验。
5. **R22 在途撤回传播、R25「轻量真的升级了旗舰」缺动态证据**：线上无任何帧暴露档位/升级。
6. **主仓 M 的既有脏文件是否会话前既有**：验证者 B 判定「无法判定」（无基线时间戳）；
   但已确认 `reports/execution-runs/` 在 M 属未跟踪目录，本范围不产生 M 的 tracked 改动。

## 5. 净结论

- 主审总判：**PASS-with-notes**。其反证**部分成功**：抓到 1 条可复现的测试隔离缺陷（F1）与 4 条笔记级问题。
- 处置：**2 条已修**（F1、F2）+ **3 条登记**（F3 披露、F4 措辞更正、F5 残余补记）。
- 核心声明未被推翻：R01–R25 的修复在现行代码中成立，冻结件未动，提交链线性。
  （推送状态见 §6：经 Owner 审批后已推至**新远端分支** `nondeploy-closeout-20261020`，远端 tip 与本地 HEAD 一致。）

## 6. 待办与提醒（需 Owner 决策）

1. **推送候选分支 —— 已完成，且本会话末已补推对齐**：目标为**新远端分支** `nondeploy-closeout-20261020`
   （新 ref ⇒ 构造上不存在 force-push）；第一次推送 tip = `adf65d7a938030555cf5310a9859fbe38eef00fa`（经 Owner 明确「执行推送」后执行）。
   本会话末经 grilling 对齐（Q3=a）后补推：`adf65d7..3af5ac2`、`PUSH_RC=0`（HTTPS 直推、无 force-push）⇒
   远端 tip ＝ 本地 HEAD ＝ `3af5ac2b405af0410b8f5075a806a7105e9c4721`，本地领先 **0**。
   其余 4 条远端 ref 推送前后 SHA **逐条不变**（master `985d53e4…`、nondeploy-closeout-20261018 `ee5bfef…`、
   release/closeout-20261015 `30dd7af0…`、snapshot/candidate-product-20261016 `ea9990fe…`）；
   `git fsck` rc=0、error/missing/broken/corrupt **0 行**（另有既有 dangling 6432 行，未引用、未清理）。
   本地分支**刻意不设 upstream**（避免后续裸 `git push` 误推），推送一律走显式 refspec。
   **第三次推送（本轮，Owner「执行吧」后）**：`3af5ac2..0baf189`、`PUSH_RC=0`（快进、无 force-push），通道＝**SSH over 443**
   （HTTPS 直推本轮 3 次连接失败）；推后远端 tip ＝ 本地 HEAD ＝ `0baf1897f42a42dc929a9586bbd8565b19d25adf`，其余 4 条 ref 逐条不变，`fsck` rc=0 / error-like 0。
2. **R23 —— 已裁定 + 部分落码**：两条残余已被测试**特征化锁死**。C03 三问先固化为 `docs/ADR.md` 的 `ADR-020`
   （提交 `3af5ac2`），后经 Owner「按建议裁定」转为**已裁定**（`c18ea8a`），并落地**问 2 的可观测读数**（`cc3aace`）——
   问 1 无新增代码、问 3 **不实现删除路径**。④⑤ **仍不删** ⇒ 闭合的是**可见性**；仍未闭合项见 §10。
3. **R22 残余 —— 本轮已闭环**：补上了「在途撤回传播」的**动态证据**
   （`tests/test_qa_revocation_lifecycle.py::test_revocation_reaches_an_in_flight_request_at_the_fresh_boundary`，
   变异自证：把 `_p_recheck` 的 `fresh=True` 退化 ⇒ 该用例转红）；F5 的「fresh 口径不一致」经实验判定**不是缺陷**（见 §8.3）。
4. **前端真机验收 —— 已执行（2026-10-20 实测）：R10 ✅ / R13 ✅ / R14 ⏸**。逐条证据在 runbook **B9 执行结果**表。
   · **R10**：生产构建（`output: standalone`）连读两次 ⇒ 注册 **1/1**、`caches.keys()=["fazhi-shell-ub2IHfyD_EFVMbRqttdFp"]`（＝构建号）、
     页面被 SW 接管、Console 无 `[sw]`/error。**口径更正**：dev 模式**不注册 SW 是设计**（`SWRegister.tsx` 的 NODE_ENV 判据）⇒
     `next dev` 下 0 条注册**不是缺陷**，R10 必须在生产构建下验。
   · **R13**：后端访问日志出现**两条** `POST /api/admin/knowledge/upload`（均 400，空文件不入库）⇒ 失败后可重选**同一文件**，
     正是「只在成功分支清空」这一原缺陷的修复点。
   · **R14**：未验——现役后端 `capabilities.voice_transcribe=false`，验了只会把"后端能力未开"误判成前端缺陷。
   · **诚实标注**：R13 由 Owner 真实交互；R10 由助手在 Owner 授权「接管」后**只读**取值（未点击 / 未填表 / 未登录）。
5. **前端 `format:check` —— 已修（提交 `0baf189`）**：只对报出的 2 只跑 `prettier --write`（**不做全仓格式化**），
   改动**纯格式化**（JSX 属性换行 / 长行折行 / 单行 if-return 折行，**无语义改动**，diff 已逐块核对）；读数
   `All matched files use Prettier code style!` rc=0、`npm run check` **14 files / 103 tests passed** rc=0、`npm run build` rc=0。
   旧记「三只」为**陈旧读数**（第 3 只已在本批内被格式化）；这 2 只**不在 M 的 21 个受保护脏文件内**。
6. **范围诚实标注**：`cf78aa7`（R22 残余，含代码+测试）与 `3af5ac2`（ADR-020，docs-only）均在独立复核的取证范围
   （`ee5bfef..adf65d7`＝19 提交 + 复核修正）**之外**，故**未重开独立复核**：前者有主线程本轮四门与 not-slow 全量读数
   （`2554 passed / 88.81%`），后者**无任何代码/配置/测试变更**（仅改 `docs/ADR.md`，`1 file / 36 insertions`）。
   两者**均已推送**至远端 `nondeploy-closeout-20261020`（见本节第 1 项）。

## 7. 证据清单重冻结（本会话末，run 根）

按纪律「先跑对账脚本、后冻结清单」执行，并在冻结后做**独立复算**（自建临时脚本逐条重算 `sha256_raw` 与 `bytes`，脚本放系统 temp、不进仓库）：

- recon：`w15_old_roots_recon.py` rc=0；读数 `R_files=481 / R_manifest=True`、`LEGACY_files=312757 / LEGACY_manifest=False`、
  `NARROW md=15 cited=108 present=82 absent=26`。
- freeze（**终态**，在台账记入「ADR-020 裁定 + 落码 + 告警 + 复裁 + 前端修复 + B9 实测 + 推送读数」之后重跑）：
  `ENTRIES=135 BYTES=2184739 FORBIDDEN=0 SKIPPED_DIRPARTS=6`（schema `fazhi.run-evidence-manifest/v1`）。
- 独立复算（主线程自建临时脚本、置系统 temp、**不进仓库**）：`DECLARED=135 OK=135 MISS=0 ABSENT=0 BYTES_MISMATCH=0`，
  与清单自述 counts 一致（逐条按 `sha256_raw` 与 `bytes` 两轴重算；脚本自报 `RECOMPUTED_BY=parent-thread-independent`）。
  （历史轮次：`2174978` → `2175482` → `2176906` → `2177892` → `2179394` → `2180705` → `2181718` → `2182507` → `2182904` → `2184766` → 终态 `2184739`；
  每轮都因先改了 run 根内的台账而按纪律重跑 recon→freeze；`2184766 → 2184739` 的小幅下降来自台账 §7 内文替换使该文件略短。
  本轮 recon 读数无变化：`R_files=481 / LEGACY_files=312757 / NARROW md=15 cited=108 present=82 absent=26`。）
- 旧读数（本会话之前）为 `ENTRIES=134 / BYTES=2148606 / FORBIDDEN=0 / SKIPPED_DIRPARTS=4`。
  本次增量来自：台账 §6/§6.1–§7 的追加、若干 `evidence/*.log` 新增，以及 run 根新增的
  `.ruff_cache` / `.pytest_cache` 两个**被排除**目录（故 `SKIPPED_DIRPARTS` 由 4 变 6，排除路径逐条记在清单的 `skipped_dirs` 里，非静默）。

### 7.1 本轮抓到并修掉的工具坑（自引用产物）

第一次冻结时用 `Tee-Object` 把冻结输出写进 **run 根内的** `evidence/w15-refreeze.log`：冻结脚本会连它自己这份日志一起哈希，
而 Tee 在脚本打印 `MANIFEST_WRITTEN=...` **之后**才把那行追加进去 ⇒ 该条目的磁盘字节永远比被哈希的版本多一行，
独立复算报 `MISS: evidence/w15-refreeze.log`（自引用假绿：清单自述「全 OK」，实测必失配）。
处置：把冻结日志改写到 **run 根之外**（系统 temp），并删掉 run 根内那份后重冻结 ⇒ 复算回到 `MISS=0`。
**教训（与既有「对账脚本刷新 generated_at 会让清单对它失效」同族）**：任何**在冻结过程中仍会被写入**的文件，
都不能位于被哈希根内；否则清单会带着一条无法自证的条目。

## 8. 按 Owner 指令处理 R23 / R22 残余的结果

Owner 指令：「先处理 R23 和 R22 残余问题」。本节记录处置与**为什么不越界**。

### 8.1 R22 残余 —— 已闭环（补动态证据 + 判定假告警）

原残余两条：

- **(a) 在途请求的撤回传播缺动态证据** → **已补**。新增
  `tests/test_qa_revocation_lifecycle.py::test_revocation_reaches_an_in_flight_request_at_the_fresh_boundary`：
  ① 在途先非 fresh 读一次（填请求内状态槽）→ ② 途中撤回提交 → ③ 非 fresh 仍读旧槽（记录"复用本身看不见撤回"这一事实）
  → ④ 阶段边界 `main._p_recheck` 的 fresh 复核必须丢弃该 QA，并配对照腿 `fresh=True` 直接判也要拒。
  变异自证：把 `_p_recheck` 的 `fresh=True` 退化成非 fresh ⇒ 该用例**功能红**（断言原文："在途撤回没有传播到阶段边界 ⇒ 已撤下的答案仍会被注入模型上下文"）。
- **(b) F5「复核点用 fresh、两处注入出口用非 fresh」口径不一致** → **判定不是缺陷**（证据见 8.3），**不改**。

### 8.2 R23 残余 —— 仍为「不做」，本轮交付**前置规格**（不动 `_qa_store`）

两条残余在仓库里**已被测试特征化锁死**（不是没被发现）：

- ④ 提交失败留**孤儿向量** → `tests/test_qa_revocation_lifecycle.py::test_sql_commit_failure_leaves_an_orphan_vector_record`
- ⑤ 重复批准留**重复向量** → 同文件 `test_approving_the_same_candidate_twice_writes_two_vector_records`

且 ③「QA 侧无删除入口」由同文件 `test_no_production_path_can_delete_a_written_qa_record` 用 AST 钉住；
该文件头明写：「要闭这一格必须先有 C03 的口径（审核来源/读取资格/撤回契约三问），所以本文件**只钉现状不改行为**」。

⇒ 本轮**不动代码**：改 ④⑤ 必须同时改写上述两条特征化用例，而"改成什么才算对"正是 C03 要定的东西；
绕过 C03 自行决定等于**替产品做撤回契约**。故交付下列前置规格，供决策：

**C03 决策必须回答的三个契约**

1. **审批来源（谁有权让一条 QA 可服务）**：人工批准 / 机器批准 / 两者并存时，读侧如何区分与表达？
   现状：`approval_source` ∈ {human, auto_by_score_inferred, unknown}，读侧对 None/unknown 一律拒。
   **需定**：`auto_by_score_inferred` 是否仍允许存在（W06-P0 后已无生产者）？存量这批如何处置（保留/降级/重签）？
2. **读取资格（什么条件下一条 QA 可被读出口使用）**：状态轴 + 来源可校验 + 引用在库三者的**合取顺序**与**唯一真源**。
   现状：状态轴在 `qa_eligibility`，来源/引用在 `retrieval_core`/`retrieval`，`main` 两出口各自咨询（顺序已统一，见 `test_qa_citation_gate_symmetry`）。
   **需定**：撤回后**是否允许**"隔离不删"（当前形状 P）长期作为策略？若允许，孤儿/重复向量的**可接受上限**是多少、由谁观测？
3. **撤回机制（撤回如何生效、生效到什么粒度）**：SQL 行状态 + 回答缓存 + 进程缓存三者的一致性契约。
   现状：`decide_candidate` 拒绝 = 置 `rejected`/`eligibility="revoked"` + commit 后 `invalidate()`；读侧按 fresh 边界复核。
   **需定**：撤回是否需要**物理删除向量**（而非仅隔离）？若需要，删除的**授权边界**（谁能触发）与**补偿语义**（提交失败时如何回滚）是什么？

**若将来允许 `_qa_store.delete()`，那条 AST 守卫如何改**（本轮不改，先写清）：

- 现守卫：穷举 `knowledge_service` 里对 `_qa_store` 的属性访问，**只允许** `_collection` / `add_documents` / `similarity_search_with_score`，并钉住"删点数为 0"；
  另有阳性对照（若出现 delete 形状必须能被认出）。
- 允许删除后，守卫需从"**零删点**"改成"**删点白名单 + 每个删点必须带补偿/授权凭据**"：
  即把"哪些函数允许删、删之前必须已 `commit`、失败如何回滚、被删 id 必须来自已登记的撤回决策"写成可机检形状；
  并保留阳性对照（否则新守卫会退化成恒真）。**注意**：本轮已实测该守卫**只钉直写形状**，别名/间接写法可绕过（F4）⇒ 升级守卫时须一并收口别名形式。

**严重度与取舍（诚实标注）**

- ④ 孤儿向量：只在"提交失败"时产生，**不可被读出口服务**（SQL 无 `vector_doc_id` 指回它）⇒ 危害是**存储垃圾 + 审计不可见**，不是错答。
- ⑤ 重复向量：只在"同一候选被批准两次"时产生，两条都指向同一 `cand_id` 且资格 `ok` ⇒ 危害是**同一答案在检索里占两个名额**（召回冗余），不是错答；
  且第二次批准是很不常见的运维动作。
- 结论：两者都**不影响答案正确性**，按"隔离不删（形状 P）"作为**已记录的、可接受的权衡**保留；
  但**不可**在没有 C03 口径时用"加一个 delete"来消掉它们——那会同时改动读侧契约与守卫判据。

**本轮已把上述三问固化为 ADR-020（提议态）**：`docs/ADR.md` 的
`ADR-020 QA 撤回契约三问（审核来源 / 读取资格 / 撤回机制）——提议待裁定`（提交 `3af5ac2`，docs-only，`1 file changed, 36 insertions`）。
该条把三问、每问的选项与**建议**、备选与否决理由、代价与诚实标注、以及失效条件写成**可裁决文本**；
它**不关闭任何残余项**（④⑤③ 在裁定前仍为未闭合），也**不落一行代码**。裁定后由 Owner 指定人把「待裁定三问」段替换为定稿「决策」段并补失效条件。

**grilling 对齐（Q1=a / Q2=A）后的处置**：R23 的 ④⑤③ **不入本批验收范围**（本批以「特征化 + ADR-020 提议态」结项）；
`ADR-020` 文本**一字不动**，裁决入口登记为 `docs/process-archive/handoff/topic-20261020-owner-action-runbook.md` 的 **B8 · C03 三问裁决**
（含三条失效条件、观测责任人位、裁决人 + 日期位）；**时点＝下一候选版本冻结前**必须裁决或显式延期，逾期须在收口台账中**显式标为未闭合**。

**2026-10-20 裁定落地结果**：Owner 指令「按建议裁定，执行 B8 三问结论并推进代码修改」⇒ `ADR-020` 转**已裁定**（`c18ea8a`），
并落地**问 2 的可观测读数**（`cc3aace`：`knowledge_service.qa_vector_integrity_counts` + `/api/admin/stats` 的
`qa_orphan_vector_records` / `qa_duplicate_candidate_ids`，admin-only、只出计数与候选 id）。
问 1 **无新增代码**（「不再新增」已成立；「存量重签 `human`」属人工流程），**读轴未收紧**——收紧会推翻设计卡 §5
并打红 `tests/test_backfill_qa_link.py` 的**正面判据**，故列为**须另裁**的未做项；问 3 **不实现任何删除路径**
（`_qa_store.delete()` 仍不存在 ⇒ ③ 的 AST 守卫原样有效）。**④⑤ 仍不删** ⇒ 本轮闭合的是**可见性**，不是**消除**。

### 8.3 F5 的实验裁决（为什么"把两处出口也改成 fresh"是错的）

在隔离树上做了决定性实验：把 `main` 里两处非 fresh 的状态轴调用（`_build_messages` 的注入出口、
`_qa_direct_return` 的资格出口）都改成 `fresh=True`，然后跑 QA 相关六件套：

```
tests/test_qa_selection_adapter.py  tests/test_qa_read_eligibility.py  tests/test_qa_chain_by_doc_id.py
tests/test_qa_cache_read_guard.py   tests/test_qa_revocation_lifecycle.py  tests/test_qa_approval_read_eligibility.py
⇒ 1 failed, 114 passed
FAILED tests/test_qa_read_eligibility.py::test_one_sql_state_session_per_qa_bearing_request
       AssertionError: 一次请求开了 3 条 session（期望 1 条）⇒ 状态装载没有请求内复用…（票 W06-FIX F9）
```

⇒ "两处出口非 fresh"是**被锁定的请求内复用设计**（票 W06-FIX F9/V8），`fresh=True` 刻意只放阶段边界与缓存命中后复核；
统一成 fresh 会**回退该优化并打红其判据**。故 F5 记为**假告警**（表述不精确），不是缺陷；**不做代码改动**。
（与此并行，R22 的"在途传播"证据见 8.1 —— 它证明的正是**fresh 边界足以拦住在途撤回**，不需要动非 fresh 出口。）

## 9. 2026-10-20 grilling 对齐（Q1–Q4）与执行结果

按 Owner 指令「通过 grilling 和我对齐」，以**一次一问、每问附推荐答案**的方式走完决策树；4 问 4 答及随后执行结果：

| 问 | 议题 | 结论 | 执行结果 |
|---|---|---|---|
| Q1 | R23 的 ④⑤③ 是否为本批验收项 | **(a) 不是** —— 本批以「特征化锁死 + ADR-020 提议态」结项 | 不落码；C03 三问本轮不答 |
| Q2 | ADR-020 提议态如何不「漂着」 | **(A) 登记进 runbook B8**（ADR-020 文本不动） | 已写入 `docs/process-archive/handoff/topic-20261020-owner-action-runbook.md` 的 **B8**（三条失效条件 + 观测责任人位 + 裁决人 / 日期位；时点＝下一 freeze 前） |
| Q3 | 是否补推 2 个提交 | **(a) 推** | `adf65d7..3af5ac2`、`PUSH_RC=0`；远端 tip ＝ 本地 HEAD；其余 4 条 ref 零变化；`fsck` rc=0 |
| Q4 | 前端两项残余如何处置 | **(a) 留本批之外 + 更正陈旧读数 + 出人工清单** | 计数更正（「三只」→ 实测 **2 只**）已写入台账与本文 §6；人工清单已写入 runbook **B9** |

**grilling 期间抓出的自身错误（已修）**：本文与台账原记「**三只**未格式化文件」为**陈旧读数**——本会话末实测
`npm run format:check` 为红但**只有 2 只**，第 3 只已在本批内被格式化（计数下降 ≠ 新引入）。两处均已更正。

**对齐后本批原定不再产生新 C 提交**；随后 Owner 指令「按建议裁定，执行 B8 三问结论并推进代码修改」⇒ 再追加 2 个提交（见 §10），
候选分支共 **24 个提交**（基线 `ee5bfef`）。

**随后的范围反转（诚实登记）**：本表 Q4=(a) 原裁「前端两项留本批之外」；本轮 Owner 指令「先不推送，帮我修复前端 format:check 报错」
⇒ 改为修复（提交 `0baf189`，见 §11）——**Q4 的结论以该指令为准**。

**尚未闭合（不得宣称已修）**：④孤儿向量 / ⑤重复向量 / ③QA 侧无删除入口（裁决入口＝runbook **B8**）；
R10/R13/R14 **真机 DOM 行为**未验（清单＝runbook **B9**）。（前端 `format:check` 原为红，**本轮已修**——见 §11。）

## 10. 2026-10-20 ADR-020 裁定落地（本轮）

| 项 | 结果 |
|---|---|
| 状态 | `ADR-020` 由**提议态**转为**已裁定（Accepted，「按建议裁定」）**（提交 `c18ea8a`，docs-only，`1 file / +26 −7`） |
| 问 1（审核来源） | **无新增代码**：「不再新增」已成立（`tests/test_qa_pending_only_creation.py` 钉住）；「存量重签 `human`」属人工流程。**未做**：收紧读轴——理由＝会推翻设计卡 §5 并打红 `tests/test_backfill_qa_link.py` 的正面判据 ⇒ 须**另起一次裁决** |
| 问 2（读取资格） | **已落码**（`cc3aace`，`3 files / +105`）：`knowledge_service.qa_vector_integrity_counts(db)` + `/api/admin/stats` 的 `qa_orphan_vector_records` / `qa_duplicate_candidate_ids`（admin-only，只出计数与候选 id，不判资格）。**未做**：阈值与告警接线、观测责任人 |
| 问 3（撤回机制） | **无改动**：不实现删除路径；`_qa_store.delete()` 仍不存在 ⇒ ③ 的 AST 守卫（零删点）原样有效 |
| 判据 | 新增 `tests/test_qa_revocation_lifecycle.py::test_orphan_and_duplicate_vectors_are_observable_now`：孤儿计数**与自身基线比 +1**、本条候选进入重复列表、`/api/admin/stats` DTO 与进程读数**同源**（两个键分别对照）；上面两条特征化用例的断言**一字未改** |
| 红能力 | **只在 dev-tree 副本变异**：停掉孤儿计数 ⇒ **功能红**（原文「孤儿向量没被读到（0 → 0）」）；两键接反 ⇒ **功能红**（原文「管理面 DTO 与进程读数不同源（孤儿键）」） |
| 四门 | ruff check `All checks passed`；ruff format `330 files already formatted`；mypy `Success: no issues found in 76 source files`；not-slow 全量 **2555 passed, 11 skipped, 22 deselected**、`Total coverage: 88.81%` |
| 仍未闭合 | ① 问 1 是否**收紧读轴**（须另裁）；② 阈值 / 观测责任人 / 裁决人姓名（runbook **B8** 空位）；③ ④⑤③ 本身（**可见性**已闭合，**消除**未做） |

**本轮新抓出的自身问题（已修）**：新增判据原本带一条非空转断言「观察对象本来不在重复列表里」——**整文件同跑**时被判据自己打红：
本文件的向量集合**跨用例共享**（conftest 只隔离目录、**不清空集合** ⇒ 别的用例写过同一候选，id 复用）。
已改为**只钉与自身基线的增量**，并补**独立探针**（直接数集合里属于本条候选的带链记录）以保证不空转。
这一条也说明：**单跑一条绿、整文件跑红**——门禁必须按文件/全量跑，不能只看单点。

## 11. 2026-10-20 前端 `format:check` 修复（范围反转，本轮）

- **范围反转（诚实登记）**：§9 的 Q4=(a) 原裁定「前端两项**留本批之外**、只更正陈旧读数」；本轮 Owner 明确指令
  「先不推送，帮我修复前端 format:check 报错」⇒ 改为**修复**。**Q4 的结论以该指令为准**，§9 表内那一行不改写（保留原裁与反转轨迹）。
- **改动**：只对 `prettier --check` 报出的 2 只跑 `prettier --write`（**不做全仓格式化**）——
  `frontend/app/admin/sections/StatsSection.tsx`、`frontend/app/admin/sections/UsersSection.tsx`；
  共 `2 files / +43 −7`，diff **逐块核对为纯格式化**（JSX 属性换行、长行折行、单行 if-return 折行），**无语义改动**。
- **提交**：`0baf189`（显式路径暂存，仅这 2 只；message 无 BOM）。
- **前端三门**：`format:check` → `All matched files use Prettier code style!` rc=0；
  `npm run check`（lint + tsc + vitest）→ **14 files / 103 tests passed** rc=0；`npm run build` → rc=0
  （构建输出含 SW 构建号 `cFnjNR992S-_jN10nm5nH`，`public/build-id.txt` / `public/sw.js` 为**构建产物、已被忽略**，未入提交）。
  后端四门**不重复跑**（本提交未触碰后端代码/配置/测试）。
- **边界**：这 2 只文件**不在** M 的 21 个受保护脏文件内（M 的脏前端为 `KnowledgeSection.tsx` / `UploadSection.tsx` /
  `chat/page.tsx` / `globals.css` / `InputBar.tsx`）⇒ **主仓受保护面零改动**。
- **仍未闭合**：R10/R13/R14 的**真机 DOM 行为**仍未验（清单＝runbook **B9**）——
  `format:check` 只是「格式门」，**不构成**真机证据。

## 12. 2026-10-20 grilling 第二轮对齐（Q1–Q4）与执行结果

以「一次一问、每问附推荐」走完 4 问（Owner 中途反馈「听不懂」⇒ 我把 Q1 从实现术语改写为业务口径后复述，Owner 选择不变）：

| 问 | 议题 | 结论 | 落地 |
|---|---|---|---|
| Q1 | 存量 `auto_by_score_inferred` 是否**收紧读轴**（立即不可服务） | **(a) 不收紧**，走人工复核 | **无代码改动**；已在 `ADR-020`「落地映射·问 1」按「不收紧」定案，并保留日后反向改判的连带改写面 |
| Q2 | ④孤儿 / ⑤重复 是否**清理** | **(a) 不清理**，只隔离 | **无代码改动**；「系统内无删除入口」红线保留，③ 的 AST 守卫原样有效 |
| Q3 | 阈值与责任人 | **(a)** 孤儿**非零即告警**；重复**只记数不告警**；责任人＝Owner（暂兼） | **已落码 `7f16b59`**：`_warn_if_orphans` + 归因键 `qa_orphan_vector_detected`（已登记白名单）+ 三段判据 |
| Q4 | 三处交互是否真机验 | **(a)** Owner 本人按 **B9** 清单在浏览器点一遍 | 待 Owner 执行；**本助手不做、不代验** |

**Q3 的诚实边界**：本仓只有**日志键**，**没有外部监控接收方** —— 即"非零即告警"当前的含义是
「日志里会出现一条带 `qa_orphan_vector_detected=True` 的 warning」，**不是**「会有人收到通知」。
谁消费该键（接告警系统 / 人工巡检）仍是 runbook **B8** 的空位。

**本轮判据的三段设计**（每段各自可红，已实测）：
① 反腿——`_warn_if_orphans(0)` **不许**落告警（否则每次打开管理面刷噪声，真告警被淹）；
② 正腿——非零必落、正文带 `count=N`、**不含**题干/答案（AUTH-3）；
③ 端到端——造一条真孤儿后走 `qa_vector_integrity_counts` 必落告警（**只测函数、不测调用点会漏接线**）。

**本轮四门（`7f16b59`）**：ruff check `All checks passed`、ruff format `330 files already formatted`、
mypy `Success: no issues found in 76 source files`、not-slow 全量 **2556 passed, 11 skipped, 22 deselected**、`Total coverage: 88.82%`。

**仍未闭合**：④⑤③ 的**消除**（本轮闭合的是「可见性 + 告警」，仍不删、③ 守卫未升级）；存量 `auto_by_score_inferred` 的**人工复核**属运营动作；
告警键的**外部接收方**与裁决人姓名（runbook **B8**）；R14 真机（runbook **B9**，需先开后端语音能力）。

## 13. 2026-10-20 真机验收期间的两项附带核查

### 13.1 《刑法》第二十四条「暂未收录」——**误报，且非本批代码问题**

- **现象**：在候选前端提问后，法条卡显示「知识库暂未收录该条文原文」。
- **实测（经 Owner 同意，容器内 Chroma 只读查询，未取用/未输出条文正文）**：
  `article=第二十四条` 共 **96** 条，其中 `source=刑法` **1** 条（`status=现行`，`effective_from/effective_to` 为空）⇒ **该条在库**。
- **根因**：**现役容器仍是旧代码**——它用全称「中华人民共和国刑法」做精确匹配，而库内 `source` 存的是简称「刑法」；
  旧代码实测 `exact_article_lookup('中华人民共和国刑法','第二十四条') = 0`、`('刑法','第二十四条') = 1`。
- **候选侧已修**：基线 `ee5bfef` 即含票 I-6 的源名回退（引入于 `8ed9a02`）；
  实跑 `norm_law_name('中华人民共和国刑法')` **= `刑法`**，两侧归一相等；时效亦不挡（`status=现行` + 日期空 ⇒ `is_valid_by_time` 为真）。
  ⇒ **候选代码会命中，部署候选后端后误报自然消失；本批不改一行代码。**
- **诚实边界**：**未在候选代码上实跑该查询**（本机跑的是现役旧代码；候选代码连真实库需 embedding 配置）。
  结论由「静态读码 + 纯函数实跑 + 库内实测」三方一致得出，不等同于候选代码实跑。

### 13.2 候选前端跑生产构建时暴露的两处环境事实（非缺陷）

- **`next start` 与 `output: standalone` 不兼容**（Next 14 会告警且 rewrites 不生效）⇒ 必须用 `node .next/standalone/server.js`；
  且 `rewrites()` 的 `BACKEND_URL` 在**构建期**求值，运行时再设无效（本轮实测：未设时 `/api/health` 为 500，设后重建即 200）。
- **dev 与生产行为差异**：SW 仅在生产注册；因此前端真机验收**不能**只在 `next dev` 下做。
