# Owner 裁定登记与执行状态（2026-10-10）

裁定来源：Owner 于本轮回复「按推荐」，即接受下列四条各自的**我给出的推荐项**。
文本由助手起草；除注明"可签"外，本文件不构成签字页。

## D-1 `agent/state_machine.py` 的在册解冻并保留改动 —— 已执行

- 已做：`backend/pyproject.toml` 的 ruff `exclude` 从 3 条减到 2 条（删 `agent/state_machine.py`），
  并按该文件自己的注释义务补了 2026-10-10 解冻记录（判据同 09-16/09-18 两例：最新 1e9 锚定不含该文件）。
- DB-15 的改动（`FREE_STEP_EDGES` + `charge` 查表，+22/−1）**原样保留**，未回退、未重写他人字节。
- 已做：随解冻对该文件做过一次纯格式化，并**用 AST 断言证明语义不变** —— `evidence/ast_equal_statemachine.py`
  对格式化前后各取 `ast.dump()`：`ast_equal=true` 且 AST dump sha 两侧同为 `2762f6fa…0cd04aa4`，符号表/节点数/语句数三项相同；
  文件 sha256 `50fede75…df87beca` → `81d58ce4…e36ecb4b`（5694 → 5672 字节），机器可读结果留 `evidence/state_machine-format-ast.json`。
  现量依据：`ruff check` 该文件 HEAD 与接收字节均 rc=0；`ruff format --check` 两者**同一条 rc=1** ⇒ 格式债早于本轮
  （这条结论的证据形状已换：先前那条靠一次就地 `ruff format -`，那是 INC-1 事故；现在是两条 `--check` 读数）。
  解冻后候选静态门复量：`ruff check .` rc=0、`ruff format --check .` 280 files already formatted rc=0、`mypy .` Success（74 files）。

## D-2 chromadb 两条残余风险「在册接受 + 失效条件」—— 复用既有的册，不写第二份

- 关键发现：**这条决策在册物证早就存在**——`docs/chroma-risk-triage-20261003.md`（2026-10-03）已逐条写明
  CVE-2026-45830／GHSA-2wm9 与 CVE-2026-45833／GHSA-36p7、上游未列修复版本、本项目是嵌入式持久库无 HTTP 服务无多租户，
  并且第 4 条明写「D2 是否接受这些受限条件仍由 Owner 决定，本文件不代签」。
  ⇒ 本轮不新建第二份风险册（那是 `code-review-standard` §5 与 ponytail「单一真源」禁止的形状）。
- 本轮复核增量（现量，2026-10-10，候选闭包）：`pip-audit --no-deps` chromadb==0.4.24 → **2 条 / 2 ID，`fix_versions` 为空**；
  `chromadb==1.5.0` → **5 条 / 4 ID**（多出 PYSEC-2026-311、-3815）⇒ 升级不关闭反而扩面，与 10-03 的告诫一致；
  backend 内 grep `HttpClient|chromadb.Server|chroma run` **0 命中**（`rag_chain.py:127` 走 `Chroma(persist_directory=...)`）。
- Owner「按推荐」= 接受该受限条件继续在册。三条失效条件沿用 10-03 文件的第 2 条原文（新增 HttpClient／Chroma server／多 tenant／
  动态 embedding 配置 ⇒ 立即重评，旧受限用途结论不沿用），**并明写：签了也不解除 J6（生产平台与访问面未定）**。
- ⚠️ 要 Owner 一词可答的**新缺口**：那份在册文件是**未跟踪文件**（`git ls-files` 现量 0），不随任何分支走 ⇒
  "在册接受"目前只活在这台机器上。要不要把它纳入版本控制（推荐：**纳入**，作为 `docs/` 的一只风险册，随本轮文档提交）。

## D-3 langchain 族 13 个 ID：本轮 BLOCKED，另开跨大版本迁移票 —— 已登记，不动代码

- 现量归属（候选 runtime 与 dev 两份读数同为 24 记录 / 15 ID / 5 包）：
  langchain-core 0.1.53 → 6 ID（修复线 0.3.80 起，1.3.3 复算 0 条）；langsmith 0.1.147 → 4 ID（被 core 的 `langsmith<0.2` 钉住）；
  langchain-text-splitters 0.0.2 → 2 ID（需 0.3.9/1.1.2）；langchain-openai 0.1.7 → 1 ID（需 1.1.14）。
- 全族都被 `>=0.1,<0.2` 这类窗挡住 ⇒ 关闭它需要 0.1→1.x 的跨大版本迁移（改 `retrieval.py`/`rag_chain.py`/`llm_registry.py` 的调用面）。
  收尾轮里顺手做这种迁移＝制造不可审的巨大 diff，本轮**不做**；该轴在 `reports/gates.md` 记 BLOCKED。
- 迁移票的票面要点（供你派单）：先冻结"哪些 API 被产品真正调用"的清单，再按 langchain-core 1.3.3 逐个换；
  测试必须**同一批尺子两棵树各跑一次**（旧 0.1 树 / 新 1.x 树），因为召回与引用校验的语义会跟着 `Runnable` 接口动。

## D-4 DB-19 `category` 回落收窄成"仅在语料无该键时发生" —— 代码已改，判据已红过再绿

- 先红（同一实现未改时）：6 failed / 3 passed，其中正身那条的失败信息就是缺陷本体——
  `库里确实没有该类时应返回零，实际拿到了：['民法典第六百七十五条 借款期限', '劳动合同法第四十七条 经济补偿']`。
- 改后：新判据 9 只 + 上一轮的 `test_retrieval_category_fallback.py` 7 只 + `test_log_field_whitelist.py` = **18 passed / 0 failed**。
- 收口复量（格式化 + 解冻落地后同树重跑，`evidence/pytest.custom.candidate-envB.20261010T050738Z.log`）：
  把 DB-15/17/18 三只入库用例与白名单哨兵一起挂上 ⇒ **59 passed / 0 failed / 0 skipped**，29.53s，RC=0；
  同趟 socket 守卫 `blocked_non_loopback=0`。全量非 slow 复跑读数见 `reports/gates.md` §6。
- 变异仪（副本树，跑完删除；`evidence/category-mutants.log`）：
  M1「判定恒 True」→ 3 只命名用例红（S1 回落、缓存/invalidate、探针缺失保旧形状）；
  M2「判定恒 False」→ S2 两只红，红回同一条跨类冒充断言；M3「不变异基线」→ 9 passed。
  【**这两行按旧仪器写，已作废**：仪器有两个 bug（`@no-repl` 分支 `shift 3` 应为 4；变异相对路径被二次前缀成
  `backend/backend/retrieval.py`），后果是臂根本没打上。硬化后重跑（`evidence/category-mutants-rerun.log`，15:55）现量：
  M1 → **2 failed**（`test_S1_library_without_the_key_still_falls_back`、`test_presence_verdict_cached_and_cleared_on_invalidate`）；
  M2 → **4 failed**（S2 两只 + `test_grounded_top_score_does_not_borrow_other_categories` + 上面那条缓存腿）；M3 → 9 passed。
  「两个方向都承重」这个结论**照旧成立且更强**（M1 红 S1 侧、M2 红 S2 侧，方向相反各自命中）。细节见 `reports/gates.md` §10③。
  ⇒ 判据的**两个方向都是承重的**，不是恒真。
- 判定的实测依据不是我希望的语义：chromadb 0.4.24 缺键行在 `$eq` 与 `$ne` 下一并被排除
  （`evidence/probe_chroma_key_presence.py`：S1 eq/ne 全 0；S2/S3 ne>0）⇒ 「双探针皆零而 count>0」⇔「没有文档带这个键」，
  且与所问值无关 ⇒ 可按集合名缓存；`invalidate()` 已加清缓存（写侧补上 category 的那天行为必须跟着变）。
- 动 `extra=` 的规矩：新字段 `category_filter_outcome` 已加进 `observability._ACCOUNT_FIELDS`，
  并由 `test_log_field_whitelist.py` 的 AST 哨兵一起跑过 ✓；抑制键现在含 outcome，
  免得写侧补齐那天新结局被上一轮的旧记录静默顶掉。
