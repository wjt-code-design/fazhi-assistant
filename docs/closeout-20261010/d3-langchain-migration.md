# D-3 langchain 族 1.x 迁移：B+ 路线执行报告（2026-10-11）

> 当前候选复核补记：本会话已对 HEAD 19e296e8 加 D-34/D-14 未提交快照做双栈隔离复验，补齐三处测试后每栈 2016 passed / 10 skipped / 18 deselected，cov 86.55%，前端三门与 83 单测通过。详见 [当前候选复核报告](C:/Users/33393/Desktop/fazhi-nondeploy-closeout-20261010-b4e7a2/reports/d3-current-candidate-review-20261011.md)。原 §4.5 撤回 variant_of 字段断言的理由不能证明判据有效，现已变异复现旧断言假绿；“生产不可达”仅限一次应用生命周期且关闭后不重建。另核干净解析 NumPy 2.x 与保留的 Chroma 0.4.24 不兼容，原 envC 的 NumPy 1.26.4 来自继承 freeze。最新审计仍红，CPU torch 未覆盖。补丁只在私有副本，D-29 未解除，不能由本报告推导已落候选、干净安装通过或整体安全门通过；以下原过程报告保留。

> 票：`tickets/dispatch-D3-langchain-migration-20261011.md`（过程登记：`tickets/D3-blocker-dependency-20261011.md`＝裁决前阻塞、`tickets/D3-smoke-breach-20261011.md`＝冒烟红回报与 R1–R5 清单）。
> Owner 已批两轮：①「按推荐」＝B+ 整包（含"冒烟红即停再裁"）；②冒烟红回报后「按推荐」＝放行 R1–R4 修复与复跑闭环。
> **本报告落盘时：候选树/主仓零字节改动、未 commit、未推送**；全部产物在运行根 `fazhi-nondeploy-closeout-20261010-b4e7a2/`（trees 在 `mig-20261011/`，证据在 `evidence/`）。落地方式见 §6 台账 1。
> 术语：envB=`candidate-envB`（旧窗对照，只读使用）；envC=`candidate-envC-1x`（B+ 新栈）；tree-old/tree-x1＝两棵副本树（`git archive HEAD`(9e3cfc5) 逐字节 + 手工补 ignored 面）。

## §0 汇总（三行）

1. **迁移面**：`backend/requirements.txt` 6 处——五窗抬 1.x（core`>=1,<2`、openai`>=1.1.14,<2`、chroma`==0.2.3`、hf`>=1,<2`、splitters`>=1,<2`）+ 新钉 `openai>=2.26,<3`；**chromadb 窗与 openai SDK 之外其余全部原地不动**（freeze 单变量：版本差仅 7 包、新增 7 包，见 §1.4）。另有 **3 个测试文件 5 处适配（R1–R5）**——产品源码（backend 非测试）**零改动**（`d3-requirements.diff` / `d3-tests-adaptation.diff`）。
2. **门禁**：同批尺子双树各跑一次——pytest 全量 **双树均 `1925 passed / 0 failed / 10 skipped / 18 deselected`、cov 86.35%、rc=0**（collected=1953、junit 1935+18 基线闸过）；ruff/format/mypy **双树 rc=0 且逐数相同**（`284 files` / `74 source files` checked）；冒烟 10 只 **19F→0F**；负向自证**断言级咬红 + 位级还原复绿**。
3. **审计（`-r` 轴＝在册同轴）**：langchain 族 **distinct 主 ID 13 → 0**（条目 22→0、主 ID+aliases 38→0，三口径全清）；全库 24→2 条（残余＝chromadb 2 条，fix_versions 为空、在册接受）；**三个新传递依赖（openai 2.54.0 / langsmith 0.14.7 / langchain-protocol 0.0.19）零新通报**。

## §1 前后门禁与审计读数

### 1.1 装出（envC；从 envB freeze 出发的「原地升级」口径；`d3-envC-build.log` / `d3-envC-freeze.txt`）

| 件 | envB（旧窗） | envC（B+） |
|---|---|---|
| langchain-core | 0.1.53 | **1.6.9** |
| langchain-openai | 0.1.7 | **1.7.0** |
| langchain-chroma | 0.1.4 | **0.2.3**（钉：唯一可配 core 1.x 且允许 chromadb 0.4.x 的版本） |
| langchain-huggingface | 0.0.3 | **1.2.3** |
| langchain-text-splitters | 0.0.2 | **1.1.3** |
| langsmith | 0.1.147 | **0.14.7**（传递） |
| openai SDK | 1.109.1 | **2.54.0**（新钉 `>=2.26,<3`） |
| chromadb | 0.4.24 | **0.4.24 不动** |
| torch / st / transformers / numpy / fastapi / pydantic | 2.13.0+cpu / 6.1.0 / 5.19.0 / 1.26.4 / 0.141.1 / 2.14.0 | **全部同版不动** |

`pip check`：**No broken requirements found**。构建序复刻 envB（先 CPU 源 torch，再 freeze 基装，再 B+ 新窗）；`python -V` / `sys.prefix` 每步打印并核（并发纪律 §1：未向 envB / backend/venv 装/卸任何包）。

### 1.2 同一批尺子双跑

| 尺子 | tree-old + envB | tree-x1 + envC | 在册（候选树 + envB） |
|---|---|---|---|
| `pytest -m "not slow" --cov=. --cov-fail-under=70` | **1925/0/10/18, cov 86.35%, rc=0**（`d3-gates-old.log`） | **1925/0/10/18, cov 86.35%, rc=0**（`d3-gates-x1.log`） | 1925/0/10/18, cov 86.35% |
| 基线闸 | junit 1935 + deselected 18 = collected 1953（`--collect-only` 单取）、0 failure/error | 同 | — |
| ruff check / format --check | rc=0 / 284 files already formatted | rc=0 / 284 files already formatted | rc=0 |
| mypy | rc=0 / **74 source files** | rc=0 / **74 source files** | rc=0 |
| 冒烟替代腿 10 只（引用三件套 + 流取消/边界/生命周期 + chunking/知识） | 258 passed / 3 skipped | **19F→（R1–R5 后）258 passed / 3 skipped**（`d3-smoke-pytest-*.log` 四份） | — |
| 冒烟探针 8 步（import/copy 适配点/Runnable/callbacks/parser/HF 构造/Chroma 端到端/splitter） | — | **8/8 OK**（`d3-smoke-probe-x1.log`） | — |
| 产品离线默认核 | — | **OK**（干净环境 import rag_chain ⇒ `HF_HUB_OFFLINE=1`、`HF_ENDPOINT=镜像`；`d3-defaultcheck.log`） | — |

19 条红的逐条归因与 R1–R5 修法/改前改后：见 `tickets/D3-smoke-breach-20261011.md` §2/§4（本报告不重复；⑤标注见 §4）。

**读数附注**：warnings 数——旧窗 **160**（与在册同）、B+ **198**（多出者为 1.x 的 DeprecationWarning 类）——不计入门禁判据、如实列。`backend/scripts/smoke_citation_fast.py` **按 Owner 更正不跑**（其 `os.chdir`+`load_dotenv` 会装载所在树真实配置/配额库；等价目的由上述 3 个经 conftest 三出口重定向的测试文件承担——票面 §2.3）。

### 1.3 审计三口径（两轴 × 前后）

**主轴 `-r requirements.txt`（＝在册同轴：128 包、不含 setuptools）**：

| 轴 | 条目 | distinct 主 ID | 主 ID+aliases | 族（条目/ID/aliases） |
|---|---|---|---|---|
| 在册（旧窗） | 24 | 15 | 44 | 22 / **13** / 38 |
| envC（B+） | **2** | **2** | **6** | 0 / **0** / **0** |

残余 2 条＝chromadb `PYSEC-2026-3813/3814`（fix_versions 为空，B 堆在册接受、D-2 域）。`openai>=1.1.14` 的由来：`langchain-openai PYSEC-2026-76` 的 fix 线＝1.1.14，且 1.1.14 起钉 `openai>=2.26`——该轴即 B+ 的"两处新钉"之一（四象限与 A/B/B+/C 取舍全程见 `tickets/D3-blocker-dependency-20261011.md` §2/§4）。`pip-audit` 在有通报时 rc=1（本行读数即如此），非脚本失败。

**佐证轴 `--local`（全环境）**：envB 28/17/52（含 setuptools 2）→ envC 6/4/14，族同为 13→0。
- **setuptools 2 条归因**：envB/envC 的 setuptools **同为 78.1.0**，envB `--local` 同样报——**与迁移无关**（`--local` 轴固有成分；在册轴不含它）。
- **新依赖零新炸**：两轴上 B+ 环境的通报都不含 openai 2.54.0 / langsmith 0.14.7 / langchain-protocol 0.0.19。

### 1.4 freeze 单变量清单（envB → envC）

- **版本变化仅 7 包**：langchain 族 5 + langsmith + openai（上表）。
- **新增仅 7 包**：`langchain-protocol`（core 1.x 的依赖）+ `httpx2/httpcore2/truststore/uuid_utils/xxhash/zstandard`（新依赖链带入）。其余 157 行 **逐字不动**（freeze 总行数 164→171，+7＝上列新增）。

### 1.5 负向自证（票面 §3 硬要求；`d3-mutation-*.log`）

| 步 | 动作 | 读数 |
|---|---|---|
| 1 | 测前 sha | `rag_chain.py = 18685348…`（`d3-mutation-sha-before.txt`） |
| 2 | 变异一处（rag_chain.py:193 迁移敏感点 `yield parser.invoke(chunk)` → 改坏返回形状 `yield [parser.invoke(chunk)]`，单 site） | 目标用例**咬红**：`assert ['first'] == 'first'`（断言级，非泛红） |
| 3 | 还原（反向 Edit） | **sha 位级相同**（`d3-mutation-sha-after.txt`） |
| 4 | 复跑同用例 | **1 passed**（rc=0） |

## §2 API 冻结表与迁移适配点

- **16/16 符号在 1.x 未改名**、现路径可 import（`evidence/d3_api_freeze.json`，生成器 `d3_api_freeze_gen.py`，行号与 import 均现扫）。生产 11 只调用文件的构造点全部保留（`ChatOpenAI(**kwargs)` / `OpenAIEmbeddings` / `HuggingFaceEmbeddings` / `Chroma` / `RecursiveCharacterTextSplitter` / `StrOutputParser`）。
- **实测新增迁移适配点 5 项**（1.x 行为面变化，全部已核到生产可达性）：
  1. **`llm.copy(update=…)`**（rag_chain.py:188 / llm_registry.py 共享 client 路径）：pydantic v2 下 **deprecated 但功能完整**（DeprecationWarning；v3 将移除——登记观察项，本轮不重构）。
  2. **`client` 语义重构 + 新增 `root_client`/`root_async_client`**（lc-openai 1.7.0 base.py:793-799/1500-1544）：`llm.client` 现为 Completions 访问器；**注入契约仍成立**（既有"版本契约"用例通过；`_client is root` 链保真）。
  3. **lru_cache 共享 httpx**（`langchain_openai/chat_models/_client_utils.py:481-530`）：进程级按参缓存；`aclose` 关池不令缓存失效 ⇒ 同参数下一个 llm"出生即 closed"。**生产不可达**（aclose 仅 main.lifespan 退出一次性；reload/variant 走 share 不 close；`_load` 重建不 close）。测试侧以 R4 隔离。
  4. **`metadata.lc_versions` 种子**（core 1.6.9 `language_models/base.py:222-251`）：ChatOpenAI 构造即写入 core(+openai) 版本。**生产零消费方**（全仓 grep：仅 Document.metadata 有消费）。
  5. **`extra_body` 提升为顶层字段**（构造告警"should be specified explicitly"，语义保留）+ **callbacks 事件 `serialized=None`**（kwargs 的 `name` 保真；`probe_cb_event.py` 双栈实证）。

## §3 语义对照（逐 query）

**方法**：`semantic_compare.py` 一器三腿（A=`vector_top` 20 取 8 的分数榜；B=`hybrid_retrieve(k=4, cutoff=2026-10-11)`；C=引用配对链三态探针 `ok/article_missing/source_missing`；D=切分）。**离线、零 LLM、零真实库**：六根 `*_BASE_URL` 全指 127.0.0.1、`RERANK_ENABLED=false`、`EMBEDDING_PROVIDER=local`、`CHROMA_DIR/QUOTA_DB/DATABASE_URL` 全隔离、`HF_HUB_OFFLINE=1`。
**语料**：`data/laws.json` 7 条 + `laws_extra.candidate-20260925.json` 3 条（`laws_extra.json` 全占位符，按 import_laws 同款护栏跳过；两树同口径）＝10 条。**query**：`data/eval_set.json` 28 条。
**已知口径差**：候选树 KB（`backend/chroma_db`）实为**空壳（embeddings=0）** ⇒ `retrieval_probe.py`（需真实 KB 语料）**未采用**；语义对照如上自建同批语料完成。

### 3.1 复跑矩阵（六跑）+ 终拍

| 对比 | 全 28 条 identical |
|---|---|
| old↔old2（同栈两跑） | 27/28 |
| x1↔x1-2（同栈两跑） | 27/28 |
| old↔x1 / old↔x1-2 / old2↔x1 | 27/28（每次差在 id=4 的 hybrid 第 4 位） |
| old2↔x1-2 | 28/28 |
| **PYTHONHASHSEED=0：old3↔x1-3（终拍）** | **28/28 全同**、切分全同 |

**id=4（"刑法第十三条讲了什么？"）专项**：hybrid 第 4 位出现四个取值（一百八十八/二十条/二十五条/道路交通安全法第九十一条），**同栈复跑亦变** ⇒ **进程级非确定性（Python hash 随机化）**，非迁移引入。**结论：停止条件 2 不成立——受控条件下零漂移。**
分数逐位一致性（抽样，BGE 余弦）：两树完全相同（如 `0.3952403059400056`）。

### 3.2 逐 query 表（终拍 old3↔x1-3；明细数据=`evidence/d3-sem-tree-{old3,x1-3}.json`）

表见 `evidence/d3-sem-per-query-table.md`（28 行，vector/hybrid/citation 三列全"同"；id=4 标注首跑抖动）。切分腿：`split_law_document(sample_law.txt)` 11 段与 10 条 `split_article_text` 的 (meta,len,sha1) **两树全部相同**。

## §4 我自己犯的错与更正（累计登记）

1. **探针自伤 5 例**（全部已改并以双栈重跑收口）：`__version__` 属性不存在×2；`-z` 参数次序错致 git 静默失败；极简探针缺抽象方法；对 `_LLM` 的第一次解释方向错误（先以为旧栈坏——实为探针用 v2 Field 而测试用 v1 Field，两世界对照后翻正）。
2. **`env -u` 被 `~/.local/bin/env` 劫持**吞输出 ⇒ 一度误判"命令没跑"（`which env` 查出）。
3. **首版 Chroma 探针用 `TemporaryDirectory`**，Windows 文件锁使**清理阶段**抛 `NotADirectoryError`，险误报"API 断裂"（功能段实为通过；改固定目录复跑 8/8）。
4. **id=4 一度被当"停止条件 2 漂移候选"**，经同栈复跑 + seed 终拍翻案为 hash 随机（口径以复跑矩阵为准）。
5. **D3-smoke-breach §4 的 R3 误列** `test_llm_lifecycle.py:326`（该行是 `assert not …`，1.x 下本就真）——执行时**只改 295-297 三行**，就地修正。
6. **R5 为闭环中新发现**（callbacks 事件 `serialized→name`，2 处）——探针 `probe_cb_event.py` 双栈证 `name` 两栈同真后施工；已在本报告与 smoke-breach 补记留痕。
7. 更早的扫描器自伤（`latest` 排序错误、自检正则两次写窄）已在 `D3-blocker-dependency-20261011.md` §5 登记，不重复。
8. **测试文件改动的边界**：R1–R5 全为"断言/夹具对新行为的等价适配"，**无一处放宽断言/删用例/加 skip**；逐处"改前/改后+理由"在 smoke-breach §4（R5 见本报告 §6-3 与 diff）。
9. **「B 条（is_closed 单跑红）」一度被我判为"真行为差异"**（推理"del 会关共享根"），P2 逐段复刻探针后翻案为"A 前序 aclose 的 lru_cache 连坐"——先停后翻完整链见 `tickets/D3-smoke-breach-20261011.md` §2 簇5。
10. **建树期发现票面 §2.2「hidden_runner.py 不在 git 里、必须手工带」为过期断言**：现量该文件**已被跟踪**（`git ls-files` 列出、`git check-ignore` 无命中 exit=1、`git archive HEAD` 自带；树完整性 2676/2676）——更正已落 `tickets/D3-blocker-dependency-20261011.md` §7，并已给 Owner 可转发更正话（供独立复核票同改）。

## §5 已知限制（诚实边界）

1. **real_kb 语义**：两树 `backend/chroma_db` 均无真实语料（候选树为空壳 0 条；副本树未带，跑测时 conftest 在树内新建空壳）⇒ `real_kb` 用例全走 skip；`10 skipped` 与在册同数但**构成未逐条列**。**"门禁全绿"的边界＝这套语料形态下的绿**。
2. **语义对照的语料面小**（10 条条文 × 28 query）且含 3 条"未核准候选"条文（仅用于**临时测量库**，未入任何产品库）；对照结论是"两树一致"，不是"检索质量达标"。
3. **id=4 非确定点**是旧栈既有性质；若未来要"逐位可复现"升级为正式判据，需固定 `PYTHONHASHSEED` 口径。
4. **未跑前端腿**（票面：本票不该动前端，只作对照——无改动面，故省略）。
5. **未 commit / 未推送 / 未部署 / 未动候选树与主仓 / 未碰端口 3021/8088**；tree-x1 的改动＝待落地补丁（diff 两份在 `evidence/`）。sensitivity：本报告未含任何凭据值。
6. **DeprecationWarning 面**：`.copy(update=)` 在 pydantic v3 前有效；`extra_body` 经 model_kwargs 传入有告警但语义保留——两者登记为观察项，**本轮不重构**。

## §6 待裁台账（每条一词可答 + 推荐）

1. **落地方式**：把 `d3-requirements.diff`（6 处）与 `d3-tests-adaptation.diff`（3 文件 5 处）落到候选树？——**推荐：落**（作为 D-3 收口笔；落前按并发纪律核工作树归属，防夹带并行会话改动）。
2. **残余通报**：chromadb `PYSEC-2026-3813/3814` 照旧在册；`setuptools 2`（`--local` 轴成分、与迁移无关）——**推荐：照旧在册 / setuptools 并入 D-2 观察**。
3. **R5 追认**：callbacks `name` 断言适配（2 处，两栈等价证据在案）——**推荐：追认**（不追认则 3 条红复现）。
4. **lru_cache 共享传输**（生产不可达但为 1.x 设计面）：**推荐：登记为 D-2/后续观察项**（若未来引入"运行期热重载 aclose/重建"场景，此点立即现役）。

## §7 证据指针与复算入口

- 门禁：`evidence/d3-gates-{x1,old}.log`、`d3-junit-{x1,old}.xml`、`d3-lint-*.log`、`d3-mypy-*.log`
- 审计：`d3-audit-envC-{local,req}.json`、`d3-audit-envB-local.json`（复算：`node evidence/audit_axes.js <json>`；全库三口径一行式见本节脚本区）
- 语义：`d3-sem-tree-{old,old2,old3,x1,x1-2,x1-3}.json`、`d3-sem-per-query-table.md`；复跑=`semantic_compare.py <tree> <out> <tmp>`（seed 口径加 `PYTHONHASHSEED=0` 前缀）
- 冒烟/修复：`d3-smoke-*.log` ×4、`d3-probe-*.log` ×4（fake-llm/aclose-sequence/cb-event/fieldinfo 各含双栈或流程）、`d3-mutation-*` ×4
- 环境：`d3-envC-build.log`、`d3-envC-freeze.txt`（对照 `evidence/envB-freeze.txt`）
- 改动面：`d3-requirements.diff`、`d3-tests-adaptation.diff`
- 能重跑的一切脚本：`evidence/{smoke_probe.py, defaultcheck.py, semantic_compare.py, probe_fake_llm.py, probe_aclose_sequence.py, probe_root.py, probe_sdk_shared.py, probe_cb_event.py, probe_fieldinfo.py, probe_isclosed.py, build_envC.sh, d3_api_freeze_gen.py, d3_dependency_matrix_gen.py, audit_axes.js}`
