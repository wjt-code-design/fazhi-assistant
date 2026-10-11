# gates — 单一状态台账（本轮唯一真源）

状态词表只有 `NOT_RUN / PASS / FAIL / BLOCKED`。历史报告的读数一律另列，不预填 PASS。
证据路径相对 `C:/Users/33393/Desktop/fazhi-nondeploy-closeout-20261010-b4e7a2`。

## 0. 责任单

| 单 | 状态 | 对象版本 | 证据 | 未覆盖项 / 停止条件 |
|---|---|---|---|---|
| A 接手保护与登记 | PASS | 主仓 HEAD `0b54396`；候选分支 `codex/nondeploy-closeout-20261010` 同起点 | `reports/baseline.md`、`evidence/input-before.json`、`evidence/ownership.json`、`evidence/forbidden-zones.json`、`evidence/tracked-diff-numstat.txt` | `state_machine.py` 整合按 A.3 停在本单（见 B 行）；计划书与两份 10-09 在册报告本身未跟踪 |
| B 后端四票 + B-45 复验 | PASS（局部）/ BLOCKED（三处待裁） | 候选 = HEAD + 24 只接收字节 + 本轮自建改动（见 §5/§6 清单） | `evidence/pytest.probe4.*.log`（48/48，两套环境都过）、`evidence/pytest.full.candidate-env*.log`（两套逐字同读数 1901 passed / 0 failed / 10 skipped / 18 deselected）、`reports/dependency-decision.md` §7 §10 | ① `agent/state_machine.py` 解冻已由 Owner「按推荐」裁定并执行（§6，AST 等价已证）；② DB-19 已按 D-4 收窄为「语料不声明 category 才回落」，**摘 schema 那半仍待裁**；⑤ DB-22 TTL 分档与 DB-23 409 文案措辞未获具体授权 ⇒ BLOCKED；③ mypy 两条 `Row` 已归因=SQLAlchemy 2.0 vs 2.1 轴，候选内 `Success`，下限已提 `>=2.1`；④ 8 只 `real_kb` 走 skip ⇒ 未覆盖 |
| C 依赖风险与候选环境 | BLOCKED（能修的已修，剩 15 个 ID 两类都需 Owner） | 候选闭包定稿 = torch 2.13.0+cpu / transformers 5.19.0 / ST 6.1.0 / SQLAlchemy 2.1.4 / chromadb 0.4.24；两套候选 `pip check` 均 rc=0 | `reports/dependency-decision.md` §10、`evidence/audit-cand-{runtime,dev}.json`（同 24 记录/15 ID/5 包）、`evidence/envB-freeze.txt` | 2 条 chromadb 上游无修复线（要「在册接受+失效条件」）；13 条卡 `>=0.1,<0.2` 一族（要另开迁移票，本轮不做跨大版本迁移） |
| D 前端浏览器验收 | NOT_RUN | — | 待 `reports/browser-acceptance.md` | 需私有 node_modules + 请求拦截 |
| E 信任门与数据演练 | PASS（E.1 模型来源、E.2 加载信任门、E.3 合成备份恢复演练） | ST 6.1.0 / transformers 5.19.0 / chromadb 0.4.24 候选闭包；BGE commit `f03589ce…`（MIT，12/12 官方哈希） | `reports/trust-and-data-drill.md`、`evidence/e2-trust/probe_st_trust.json`（五臂 `GATE_HOLDS`）、`evidence/loader-trust-mutants.log`、`evidence/drill-mutants.log`、`evidence/b45-mutants.log` | 行为级信任门是 evidence 脚本而非套件成员（要 409 MB 权重）；**真实库恢复/真实语料版本元数据仍 BLOCKED（J5）**；`switch_embedding.py`/`rebuild_embeddings.py` CLI 未调用 |
| F 五类真实模型验收 | NOT_RUN | — | 待 `reports/model-acceptance.md` | 需 B/C/D/E 硬前置；gold 未冻结前不开真实调用 |
| G 现用环境升级 | BLOCKED（归属已核实，理由换了） | 现役 = Docker 容器（镜像 `cbdadf43a40b`，创建 3 周前；容器 09-17 建、10-10 15:08 本地被 `restart=unless-stopped` 自动拉起） | `reports/local-environment-switch.md` §1-§3 | 升级现役=重建镜像+重启容器=本书明令不执行；宿主机 `backend/venv`（SQLAlchemy 2.0.51 / torch 2.6.0+cpu / pip check 两条不一致）不是产品运行环境，动它需另一次具体授权（D-6） |
| H 包装/凭据/CI | PASS（CI 两处补步）/ **凭据值轴＝已证历史裸值、现役性未知**（不是「无授权做按值反查」）/ NOT_RUN（构建与镜像腿） | 候选 `8c179e7`、`5ca3315` | `reports/h-ci-and-credentials.md`、`evidence/shape_scan_staged_set.py` 现量输出 | 按值反查**本轮已跑通**（`evidence/value_reverse.py`：238 棵树 hits=61/files=1；`evidence/shape_scan_committed_set.out` 的 CONTROL-B 腿先在 `817e7d3` 上咬住再报 0）；禁区只是「打印值 / 读 `.env`」⇒ 未知项仅剩「该旧值是否仍现役」。Docker/standalone 腿排在 D 单之后（有意让路）；禁跑 `b_worktree_value_scan.py` 默认整树模式 |
| I 审查/提交/PR/合并 | NOT_RUN | — | 待 `reports/integration.md` | 未取得独立审查不得合并；实现者不得自任 reviewer |
| J 阶段收尾 | NOT_RUN | — | 待 `reports/results.md` | 严格口径：任一必需门未闭即未完成 |

## 1. 发布门（J1～J6，全部 NOT_RUN）

| 门 | 状态 | PASS 所需证据 | 当前不可替代项 |
|---|---|---|---|
| J1 工程/安全 | NOT_RUN | B/C/D/E 测试 + 风险闭合 + 输入保护 + 独立审查 + 隐私/信任门真实有效 | 基线也红、风险已登记、静态字面量、警告但仍执行 |
| J2 五类真实能力与法律质量 | NOT_RUN | F 五类真实路径 + 独立 gold + 法律专业审签 + 版本/时效依据 | rerank 旧成功、单个 HTTP 200、模型自评、小题集"总体准确率" |
| J3 本地环境与可搬运候选 | NOT_RUN | 经核实现用环境升级+回退实测 + 候选构建与声明平台证据 | 验收 venv 代现用、Windows tsc 代 Linux/standalone、venv 改名即可运行 |
| J4 Git/远端 | NOT_RUN | 当前提交与 PR + 必要 review/CI + 合法合并与合并后状态 | 仅本地提交、前一 head CI、保护 bypass |
| J5 真实数据恢复/迁移与语料就绪 | BLOCKED（按构造） | 真实数据对象的合法恢复验证与版本元数据验收 | 本书禁止实库读写；合成演练/旧 mtime/旧数据数量不可替代 |
| J6 生产目标的非部署前置 | BLOCKED | 平台/架构选型 + 凭据处置 + 访问/回退/数据方案 + Owner 决策 | 用户尚未选服务器；Linux 工程候选不是生产平台签认 |

## 2. 已在册阻塞（不许拿掉）

1. 真实数据门（J5）— 需具体对象/范围/回退/时窗批准。
2. 法律门（J2 子集）— 缺合格法律复核者，助手不得代签，不得加 LLM judge 消除。
3. 生产平台门（J6）— 服务器/OS/架构未定。
4. 环境切换门（G）— 归属不唯一 / 回退未实测 / 有他任务占用 / 启动会写真库。
5. 风险与凭据门（C/H）— 无官方安全闭包、残余漏洞需 Owner 裁、暴露凭据需人工轮换。
   本轮细化（10-10）：凭据门的卡点已从「有没有明文」换成「我在授权内验不了值轴」（本书 A 单禁开 `.env`），
   所以 D-5 是授权问题而不是扫描问题；远端可见性与 CI 是否已含那段历史，本机 API 被拦 ⇒ 无读数。
6. 审查/远端门（I）— 缺 reviewer、GitHub 权限、有效 CI 或共同历史。
7. ~~（A.3 登记）`backend/agent/state_machine.py` 在册冻结 vs 已被改动~~ ⇒ **2026-10-10 已解除**：Owner「按推荐」= 确认解冻并保留改动，`pyproject.toml` ruff exclude 已删该行并留解冻记录，纯格式化 + AST 等价证明见 §6。序号保留不重编号（他处按号引用）。


## 3. 补记（A 收口时的自查，2026-10-10）

- 事故与订正两条见 `evidence/incidents.md`：INC-1 我把接收来的 `state_machine.py` 就地格式化了（靠逐只 sha 复算检出、按主仓原字节还原、24/24 复测漂移 0，主仓未写入）；
  INC-2 第一版建 env 脚本让 pip 在默认 PyPI 上解析到 torch 2.14.1（本书 C.4 禁止的形状），已删撕裂环境并按「CPU 源先钉 2.6.0+cpu、再装声明闭包」重建。
- **INC-1 推翻了我先前一条结论**：格式债不是 DB-15 引入的，真 HEAD 字节在 `ruff format --check` 下同一条 rc=1。
- A 出口判据复量：归属清单完整（`evidence/ownership.json`）、禁区只记元数据（`evidence/forbidden-zones.json`）、
  候选来源可还原（`evidence/input-before.json` + `evidence/verify_received.py` 现量 24/24 漂移 0）、索引原状态未动（主仓 `git diff --cached` 恒 0 只）。


## 4. 补记二（2026-10-10 C/B/E 首轮读数）

- 候选全量非 slow：**1901 passed / 0 failed / 10 skipped / 18 deselected**，220.96s，RC=0；总数 1911 与上一轮旧栈读数**同分母**，差的 8 只是 `real_kb` 在候选里 skip（`backend/chroma_db` 按构造不存在）。
- socket 守卫：321 事件，**非回环 0**，回环 319；守卫自身的「能红」证据在 `evidence/selfcheck_egress_guard.py`（回环放过 + 两只非回环被拒 + 2 条记账）。
- 我引进的一处候选改动（超出接收清单）：候选 `backend/requirements.txt` 追加 `transformers>=5.0,<5.19` + 证据注释 ⇒ 候选树现在是 **25 只**改动（20 M 他人 + 4 新测试 + 1 我改的 requirements）。这不是「他人改动」，归属本轮，须单独审。【**该计数是提交前的工作树读数，已过期**：`5ca3315` 之后 `git status --porcelain` 只剩 5 只**前端** `M`（另一会话的 §14 修复，未提交，我不碰），我这轮的后端件已全部入库。工作树计数按在册纪律不该写死在正文——要现量就跑 `git -C <候选> status --porcelain`，并记住分母是**tracked 修改**，未跟踪/被忽略另计】
- 发现 F-A1（候选放主仓子目录 ⇒ 测试进程读到真实 `.env`）已用两道处置：候选内空 `.env` 截断向上搜索（实测 `find_dotenv()` 解析到候选本地 0 字节文件），加测试进程钉死 18 只键。见 `evidence/finding-dotenv-upward-search.md`。


## 5. 补记三（候选改动面与静态门读数）

- 候选现量：tracked 已修改 **23** 只（他人 20 + 本轮依赖声明 3）、未跟踪新后端测试 **4** 只。我引进的 3 只是
  `backend/requirements.txt`、`backend/Dockerfile`、`.github/workflows/ci.yml`（同批对齐 torch 2.13.0 与 SQLAlchemy 下限），
  与他人的 20 只分开列，审查时该分两栏看。
- 候选内 `backend/.env` 是一只 **0 字节空文件**（发现 F-A1 的构造性拦截），被 `.gitignore:26` 忽略，不进树、不进包、不进提交。
- 静态门读数（候选树 + 私有环境）：`mypy .` **Success（74 files）**；`ruff format --check .` 278 files already formatted rc=0；
  前端 `npm run lint` rc=0、`tsc --noEmit` rc=0、`vitest run` 9 只文件 **50** 用例全过【**此数已撤回**：现量 `Tests 83 passed (83)` / `Test Files 9 passed (9)`，见 §10 补记八①；50 无处可复算】（与 10-09 那句「106 项」不同分母，
  本树 `vitest.config.ts` include 只有 `tests/**/*.test.ts` 这 9 只，复算不出 106，已按在册过期处理）。


## 6. 补记四（2026-10-10 D-1 解冻执行 + D-4 category 收窄 + 静态门复量）

### 6.1 D-1：`agent/state_machine.py` 解冻落地（可复算）

Owner 裁「按推荐」= 确认在册解冻并保留 DB-15 改动。三处留痕：

1. `backend/pyproject.toml`：ruff `exclude` 由 3 项减为 2 项（`prompts.py`、`scripts/gate5_judge.py` 保留），并按该文件 :8 那条「unfreeze 必须删掉本 exclude」的注释义务补了 5 行解冻记录【**此数已撤回**：`diff pyproject.before → 现文件` = +7 行 / −1 行（−1 是删掉的 `"agent/state_machine.py",`），见 §10 补记八①】（判据、改动量、实测代价）。
2. 纯格式化：`ruff format --check agent/state_machine.py` 改前 rc=1（HEAD:37 那条旧语句 `self.state = state.model_copy(...)`），改后 rc=0。
3. **AST 等价证明**（不是"我看了一眼"）：`evidence/ast_equal_statemachine.py` 对格式化前后字节各取 `ast.dump()` 比较 ⇒ `ast_equal=true`、`symbols_equal=true`、`nodecounts_equal=true`、AST dump sha `2762f6fa…0cd04aa4` 两侧相同；文件 sha256 `50fede75…df87beca` → `81d58ce4…e36ecb4b`（5694 → 5672 字节）。复算命令：

```bash
cd C:/Users/33393/Desktop/fazhi-nondeploy-closeout-20261010-b4e7a2
candidate-envB/Scripts/python.exe evidence/ast_equal_statemachine.py \
  C:/Users/33393/Desktop/ai-legal-helper/.worktrees/nondeploy-closeout-20261010/backend/agent/state_machine.py
```

**订正（推翻我本轮先前一句）**：我在 §3 记的「格式债早于本轮」是对的，但当时的证据形状有缺陷——我当时用 `ruff format -` 就地写过接收字节（INC-1）。现在的结论证据换成两条 `--check` 读数（HEAD 字节与接收字节同一条 rc=1），且格式化只作用在我明确列出的文件上。

### 6.2 D-4：DB-19 回落收窄为「语料不声明 category 才回落」

`evidence/db19-probe.out` 实测：Chroma 0.4.24 对缺失键的 `$eq`/`$ne` 一律排除该行，且**该判定与所问值无关**（S1 全不带键 ⇒ eq/ne 双 0；S2/S3 带键 ⇒ ne>0）。据此把「带过滤零命中就无条件补发无过滤查询」改成先探一次"这个集合是否声明 `category`"：

- `backend/retrieval.py`：新增 `_corpus_advertises_category(vs, category)`（按集合名缓存于 `_CATEGORY_ADVERTISED`）与 `_docs_advertise_category(docs)`，`vector_top` / `bm25_top` / `grounded_top_score` 三处共用同一判定；`_note_category_filter_miss(category, stage=..., outcome=...)` 新增 `outcome` 并进抑制键（`filter_unsupported_fell_back` 与 `filter_no_match_kept_empty` 不再互相吞告警）；`invalidate()` 同时清 `_CATEGORY_ADVERTISED`。
- `backend/observability.py`：`_ACCOUNT_FIELDS` 加 `category_filter_outcome`（§2 B5 白名单门）。
- `backend/tests/test_retrieval_category_narrow_fallback.py`：9 条用例，替身 `FakeChromaCollection` 按上面实测语义实现（不是照抄实现），含 S2「该类确实零条 ⇒ 保持为空、不冒充」、两条 outcome 归因、BM25 与 `grounded_top_score` 共用判定、缓存/失效，以及末条**负向自证**：旧形状对 S2 一定会补发无过滤查询。

读数：定向 6 只文件（新旧 category + DB-15/18/17 + 日志白名单哨兵）**59 passed / 0 failed / 0 skipped**，29.53s，`evidence/pytest.custom.candidate-envB.20261010T050738Z.log`；同趟 socket 守卫 `blocked_non_loopback=0`（`evidence/egress.custom.20261010T050738Z.summary.json`）。

**没做的事**：`category` 仍留在 schema 里（摘不摘是 DB-19 那半，需你裁）；未回填真实库任何 metadata；写侧归一 4 处（`scripts/import_docs.py` 等）仍未并 ⇒ DB-21 未动。

### 6.3 静态门复量（候选树 + `candidate-envB`，全部本轮现跑）

| 门 | 读数 | 说明 |
|---|---|---|
| `ruff check .`（在 `backend/`） | `All checks passed!` rc=0 | 解冻后 `state_machine.py` 已在覆盖内 |
| `ruff format --check .`（在 `backend/`） | **280 files already formatted** rc=0 | 我之前漏了两只：`retrieval.py`（我 D-4 新增那行）与新测试文件，已 `--diff` 预检后定向 `format`，两只各证 AST 等价（`evidence/ast_equal_pair.py`，sha 见下） |
| `mypy .` | `Success: no issues found in 74 source files` rc=0 | mypy 2.4.0；坐实那两条 `Row` 红是 **SQLAlchemy 2.0.51 轴**，不是 mypy 版本轴 |
| 接收字节完整性 | `verify_received.py` 现量 24 只中 **3 只**标记，且全是本轮有意改动 | 见下表；主仓工作树 24 只**全部**与接收时字节相同（无 `MAIN_DRIFT`） |

| 被标文件 | 谁的内容 | 本轮动作 |
|---|---|---|
| `backend/agent/state_machine.py` | 他人（DB-15） | 仅格式化（AST 等价） |
| `backend/retrieval.py` | 他人（DB-16③）+ 我（D-4 收窄） | 新增约 60 行判定 + 格式化我自己那行 |
| `backend/observability.py` | 他人（DB-17 记账字段）+ 我（D-4 加 `category_filter_outcome`） | 白名单加 1 键 |

格式化两只本轮自己的文件：`retrieval.py` sha `922f4dff…2fe9d7f4` → `9a504013…47c664cef`（70146 → 70116 字节，AST 等价）；新测试文件 `196766a7…0c9211c5` → `6ecd6ea8…829e9e96`（9931 → 9932 字节，AST 等价）。

### 6.4 候选改动面现量（口径：`git diff --name-only` 在候选工作树，`wc -l`）

**tracked 已修改 24 只** = 他人后端 16 只（controller/runtime/service/state_machine/writer/domain_rules/llm_errors/llm_registry/main/observability/retrieval/scripts-smoke + 测试 3 只）+ 本轮依赖声明 3 只（`requirements.txt`/`Dockerfile`/`ci.yml`）+ 本轮 `pyproject.toml` 1 只 + **前端 5 只（并行会话的，不属于本轮，不提交）**。
**未跟踪新后端测试 5 只** = 接收 4 只 + 本轮 `test_retrieval_category_narrow_fallback.py`。
复算：

```bash
cd C:/Users/33393/Desktop/ai-legal-helper/.worktrees/nondeploy-closeout-20261010
git diff --name-only | wc -l
git ls-files --others --exclude-standard backend/tests
```


## 7. 补记五（2026-10-10 E.2/E.3/B-45 落地与终量门禁）

交付文件：`reports/trust-and-data-drill.md`（E 单全文）。这一段只记状态与读数变化。

| 项 | 状态 | 现量 |
|---|---|---|
| E.2 加载信任门 | PASS | 行为级五臂 `GATE_HOLDS`（默认/False 均**未**执行 `auto_map` 自定义代码，`"local"` 执行 ⇒ 阳性对照咬住；ST 层 `True` 对本地目录也不放开）；入库 4 条（接线 AST + 库默认值现量 + 生产面 grep + 恒真哨兵负向自证）；变异 M2 让 2 条真红，M1 的 4 errors 如实记为"该形状构造不出来" |
| E.3 备份→恢复演练 | PASS（合成面） | 入库 7 条：包内六件齐 + WAL 单文件无残留 + 恢复库**条文原文**全等 + 配额账本逐值等 + 向量恢复命中 `doc-1` 且与包内 `chroma_index.json` 的 `source×article` 集合对得上 + 二次运行 `rc=2` 拒绝覆盖 + 源树逐文件 sha 前后相同 + 半途失败不出清单 + `_check_env_contract` 分歧即拒 |
| B-45 `import_laws` 守卫 | PASS | 守卫挂 `__main__`（与 `backup_data` 同位）；`--validate-only` 按判据豁免；入库 4 条走子进程；变异 M1 删守卫 ⇒ 恰好红在分歧拒绝那条腿 |
| 我引进的一次假读数 | 已改 | 子进程 helper 第一版 `except SystemExit: pass` 把"拒绝执行"这条**判据要读的消息**吞了 ⇒ 拿到假的"没拦"；改回 re-raise 后 32 passed |
| 通用变异仪 | 已随票落盘 | `evidence/run_mutants.sh` + `evidence/arms/*.txt`；第一版 `@no-repl` 分支 `shift 3`（应为 4）⇒ 臂错位，`bash -x` 定位后修 |

终量门禁（候选树 + `candidate-envB`，本轮全部现跑）：

| 门 | 读数 |
|---|---|
| `ruff check .`（backend） | `All checks passed!` rc=0 |
| `ruff format --check .`（backend） | **283 files already formatted** rc=0 |
| `mypy .` | `Success: no issues found in 74 source files` rc=0 |
| 全量非 slow | **1925 passed / 0 failed / 10 skipped / 18 deselected**，210.51s，junit tests=1935，RC=0 |
| socket 守卫（同趟） | 321 事件，**非回环 0**，回环 319，`blocked_targets=[]` |
| 用例增量对账 | 1901（接收态）+ 9（D-4 收窄）+ 4（E.2）+ 7（E.3）+ 4（B-45）= **1925**，Δ 逐笔可指到文件 |

候选改动面现量随之变化：tracked 已修改 **25** 只（24 + 本轮 `scripts/import_laws.py`），未跟踪新后端测试 **8** 只
（接收 4 + 本轮 `test_retrieval_category_narrow_fallback.py`、`test_loader_trust_gate.py`、`test_backup_restore_drill.py`、
`test_import_laws_guard.py`）。复算命令同 §6.4。

**仍开着的**：C 单 15 个 ID 两类待裁（2 无上游修复 / 13 卡 `>=0.1,<0.2`）；DB-19 摘 schema、DB-22 TTL 分档、
DB-23 409 文案措辞待 Owner 具体授权；D/H/I/J 未跑；J5 真实数据门按构造 BLOCKED。


## 8. 补记六（2026-10-10 本地提交 + H/覆盖率读数）

### 8.1 候选分支的两笔本地提交【**笔数已过期**：写出时确为两笔，此后又落 `a934fa7`/`3f605de`；现量用 `git log --oneline 0b54396..HEAD`，别信本节标题】（worktree 内，主仓未动）

| 提交 | 范围 | 读数 |
|---|---|---|
| `5ca3315` | 25 只：接收的后端四票 16 只 tracked + 接收测试 4 只 + 本轮 D-4/B-45/解冻记录 5 只 + 本轮新测试 4 只 | `25 files changed, +2143 / -121` |
| `8c179e7` | 3 只：`backend/requirements.txt`、`backend/Dockerfile`、`.github/workflows/ci.yml` | `+48 / -6` |

- 未提交面：`frontend/` 5 只（并行会话的，D 单结完再定 hunk）；主仓工作树**未被本轮写过**（`verify_received.py` 现量无 `MAIN_DRIFT`）。
- 提交内容形状扫描（`evidence/shape_scan_staged_set.py`）：28 只待提交文件、680,576 字节、**5 条规则 0 命中**，且每条规则都用构造样本证明能咬（`control_covers_every_rule=True`）。**射程声明**：只覆盖待提交文件，不覆盖历史 blob；形状普查盖不到无形状口令 ⇒ 值轴见 §8.3。【**本句射程写窄了**：真正漏的不是「历史 blob」而是「键名不在场的值」——本轮值级现量见 `reports/h-ci-and-credentials.md` §2.1，那只 13 位字面量在 HEAD 树里、不在待提交集里，形状扫描结构上看不见它。】
- **上一条的两处仪器问题（本轮晚间补跑并落盘）**：① 旧脚本取文件集用的是 `git status --porcelain` ⇒ 提交之后射程变 0 只，**那次的读数没有留 artifact**（`evidence/` 里只有脚本、没有输出文件），28/680,576/0 命中只能算「当时屏上看到的」；② 5 条形状规则**全部要求键名在场**，对「被写进正则 pattern 的裸口令」结构性失明。⇒ 新脚本 `evidence/shape_scan_committed_set.py` 按提交区间取 `git show HEAD:<path>` 的 **blob** 来扫，并加一条**按值腿**（CONTROL-B：值从 git 对象取进内存，只报长度/是否咬住，不打印），且要求它先在引入该值的历史笔上证明能咬、否则拒绝报 0（`VERDICT=REFUSE_TO_REPORT_ZERO`）。现量：`range=0b54396..HEAD files_in_range=28 skipped=0 bytes_scanned=681509`、`CONTROL-A …=5/5`、`shape_rule_hits=0`、`CONTROL-B extracted=yes len=13 bites_on_817e7d3=True`、`CONTROL-B hits inside range=0`、`VERDICT=PASS_VALUE_LEG_PROVED_BITING`（`evidence/shape_scan_committed_set.out`）。注意 681,509 B 与旧的 680,576 B **不是同一分母**（前者=四笔提交的入库面，后者=当时 staged 集），别拿来互相验。

### 8.2 覆盖率门

`1925 passed` 的无 cov 趟与 `--cov --cov-fail-under=70` 趟**不是同一读数**，要分开报：
- 覆盖率**门槛达成**：`TOTAL 8866 语句 1076 未覆盖 → 86.35%`【**1076 已撤回**：两份 cov 日志的 TOTAL 行都是 `8866 1079 2726 325 86%`；86.35% 与门槛结论不变】，`Required test coverage of 70% reached`（`evidence/pytest.cov.<第一次>.log`）。
- 但那一趟是 `1 failed / 1924 passed`，红的是 `test_settings_repr_masking::test_repr_masks_every_secret_value`。
- **归因（单变量两臂）**：同一条用例、只差我传进去的假值形状 —— 五个 key 各给不同多字符串 ⇒ `3 passed`；全给单字符 `k` ⇒ `1 failed / 2 passed`。⇒ 红是**我 harness 的值形状**造成（`str(value) in text` 对单字符必然命中），不是打码实现的问题。
- 第三趟（改好假值后的干净复跑）在 96% 处无声消失、日志无 `RC=` 行。**根因已定**：覆盖插件要擦除
  `COVERAGE_FILE`，被本机 safe-delete 沙箱拦掉（`docs/code-review-standard.md` §1.1 在册的同一台机器）。
  按在册绕行法加 `CODEBUDDY_SAFE_DELETE_ENABLED=0` 后第四趟**闭合**：`1925 passed / 0 failed / 10 skipped /
  18 deselected`，`TOTAL 8866 语句 → 86.35%`，`Required test coverage of 70% reached`，**RC=0**
  （`evidence/pytest.cov.20261010T070646Z.log`）⇒ 该腿 **PASS**。这条教训是"读数消失"不是"读数为零"：
  当时若直接记成"覆盖率不过/未知"，就把一台会静默杀进程的仪器读成了产品状态。
- `reports/h-ci-and-credentials.md` §3 另记了这条红暴露的两台仪器弱点（短值判据不具鉴别力 + 假凭据值形状是实验条件）。

### 8.3 H 凭据腿：结论是 BLOCKED，且原因是授权而不是工具

本轮授权内**做不了**按值反查（A 单禁 `.env`），形状轴 0 命中但盖不到无形状口令 ⇒ 既不能说"干净"也不能说"有"。
复算入口与在册 09-30 结论的关系见 `reports/h-ci-and-credentials.md` §2。**给 Owner 的那两条（先轮换 / 走孤儿快照）我都没有自行执行**：
前者是外部账户动作，后者是改交付形态，都超出本书授权。

### 8.4 I 单的当前形状（未闭合）

- 已做：候选内两笔提交、三台变异仪与全部读数落盘、两路独立复核**已派发**（只读、写在 `reports/independent-review-A.md` / `-B.md`）。
- 未做：推送、开 PR、远端 CI 读数、合并。**阻塞在** §8.3 的凭据轴 + 独立复核结论回灌。
- `$closeoutCandidatePython` = `…b4e7a2/candidate-envB/Scripts/python.exe`；`$closeoutCandidate` = `…/.worktrees/nondeploy-closeout-20261010`。


## 9. 补记七（2026-10-10 G 单归属核实 + 覆盖率腿闭合）

- **G 单**：归属核实完成，结论从「未核」改判为 **BLOCKED（升级动作在本书授权外）**。
  决定性现量：产品 8088 的监听者是 `com.docker.backend.exe`（PID 8636），宿主机无 python/node 监听产品端口；
  compose project 的 working_dir 指向**主仓**，三个容器 `restart=unless-stopped`、创建于 09-17、本次启动于
  2026-10-10 07:08:51Z；后端镜像 `cbdadf43a40b` 创建于 3 周前 ⇒ **现役运行版本与本轮候选无关**。
  容器**不是我/我的 agent 启的**（派单边界禁 compose；D 的 logs/scripts grep `docker|compose` 0 命中），我也**没停它**。
- **连带后果登记**：候选把 SQLAlchemy 下限提到 `>=2.1` 后，开发用的 `backend/venv`（现量 2.0.51）
  已在声明区间之下，torch 亦然，且 `pip check` 仍有两条既有不一致（fastapi↔starlette、sse-starlette↔starlette，
  实际 starlette 0.36.3）。合并后凡用该 venv 的人跑的是「不满足 requirements 的环境」，
  mypy 那两条 `Row` 红会在那里复现。交回 Owner 的是 D-6 那一题，本轮没动那个 venv 一个字节。
- **覆盖率腿闭合**：第三趟在 96% 处无声消失，根因为 safe-delete 沙箱拦 coverage 数据文件擦除；
  按在册绕行 `CODEBUDDY_SAFE_DELETE_ENABLED=0` 后第四趟 `1925 passed / 0 failed`、`86.35% >= 70`、**RC=0**
  （`evidence/pytest.cov.20261010T070646Z.log`）⇒ 该腿 **PASS**，§8.2 已就地更正。
- **新交付**：`reports/local-environment-switch.md`（G 单全文）、`reports/decisions-needed-20261010.md`
  （待裁台账 D-5…D-13 + 已裁 D-1…D-4 对账）。

## 10. 补记八（2026-10-10 深夜：两路独立复核的采纳与翻案 + 我自己三处读数被推翻）

采纳规则先说清：**复核者的话我不转述成结论**，每条都在候选树/运行根重跑一遍才落进正文；重跑不落的不采纳。

### ① 四条纯数字错（我写进正文的，就地已标注撤回）

| 项 | 我写的 | 现量 | 证据 |
|---|---|---|---|
| 前端 vitest 用例 | 50 | **83**（`Tests 83 passed (83)` / `Test Files 9 passed (9)`） | `evidence/vitest-candidate-20261010.log` |
| 覆盖率未覆盖行 | 1076 | **1079**（TOTAL 行 `8866 1079 2726 325 86%`） | `evidence/pytest.cov.*.log` 两份都是 1079；86.35% 与门槛 70 结论不变 |
| 解冻记录行数 | 5 行 | **+7 / −1**（−1 是删掉的那条 exclude） | `diff evidence/pyproject.before backend/pyproject.toml` |
| 提交笔数 | 写死「两笔/三笔」 | **改成命令** `git log --oneline 0b54396..HEAD` | 在册纪律：自涨的计数不进正文 |

指针漂移一处：`reports/dependency-decision.md` §10 那行引 `backend/Dockerfile:34-38` / `:41-48` / `:38`，
现量（`git show HEAD:backend/Dockerfile`）= 钉版注释 **:35-38**、install 段 **:45-47**、防呆断言 **:51-58**；
而它引的那句「torch 锁在 2.6.0（镜像已同步的最新 cp311+cpu 版）」**已不存在**——被 `8c179e7` 换成 `:39-44` 的取舍说明。
⇒ 那一行描述的是**改动前**的文件，读它时要按"改动前"理解，别拿现号去跳。

### ② E.2 臂 E 是假阴性：同进程动态模块缓存，五臂改逐进程重跑

上一版我把 A/B/C/E/D 放在同一进程里依次加载，据 E「没有 marker」判 `trust_remote_code=True` 也被门拦住。**错了**：
C 臂已经把自定义模块灌进 `sys.modules`，E 臂命中缓存 ⇒ 根本没重新执行，marker 空是缓存的症状不是门的功劳。
逐进程重跑（`evidence/probe_st_trust_arm.py`，每臂独立解释器 + `PROBE_MARKER` 指向臂名单独的文件）：

| 臂 | 模型目录 | kwargs | marker | 判读 |
|---|---|---|---|---|
| A | 被污染 | （不给） | **无** | 默认拒绝 ⇒ 拦住 |
| B | 被污染 | `False` | **无** | 显式拒绝 ⇒ 拦住 |
| C | 被污染 | `"local"` | **有** | 信任本地自定义代码 ⇒ 执行 |
| E | 被污染 | `True` | **有** | **执行**（上一版这里读成"无"＝缓存假阴性） |
| D | 干净 | `True` | **无** | 干净快照不需要自定义代码 ⇒ 不执行 |

⇒ 判据措辞改准：**加载信任门只在没人显式给 `True`/`"local"` 时保护我们；给了就会执行模型目录里的自定义代码（已证）**。
所以我们防的是"配置面"，不是"库会替我们挡"——`backend/tests/test_loader_trust_gate.py` 的 AST 腿钉的就是配置面。
真源 HF 缓存目录 mtime 前后相同（探针没碰官方快照，只碰合成副本）。

### ③ category 变异仪的 M2 那一臂从未生效：两处仪器 bug 合起来造了「全存活」

复核 A 指出 M2 不可复算，我复现并查到根因（两台都在我这边）：
1. `run_mutants.sh` 的 `@no-repl` 分支 `shift 3`（应 4）⇒ 臂参数整体错位；
2. 变异文件里的相对路径被二次前缀成 `backend/backend/retrieval.py` ⇒ patch 失败但脚本继续跑。
两者叠加的后果是**三只臂都在未变异的树上跑**，于是报出「9 passed」＝"变异全被杀"的反面假象（全存活被读成全杀）。
硬化后的仪器（`PATCH_OK` 回显 + 变异后 `ast.parse` 自检 + `ARM-INVALID` 不计入判决）现量：

| 臂 | 变异内容 | 现量 | 红的是哪条腿 |
|---|---|---|---|
| M1 | `cat_repl_m1.txt`：把「语料是否声明该 category」的判定改成**恒 True** | **2 failed** | `test_S1_library_without_the_key_still_falls_back`、`test_presence_verdict_cached_and_cleared_on_invalidate` |
| M2 | `cat_repl_m2.txt`：同上一处判定改成**恒 False**（语料永远被当成不声明） | **4 failed** | `test_S2_library_advertises_category_but_not_this_value_stays_empty`、`test_S2_outcome_is_logged_as_no_match_not_fallback`、`test_grounded_top_score_does_not_borrow_other_categories`、`test_presence_verdict_cached_and_cleared_on_invalidate` |
| M3 | 不变异基线 | **9 passed** | — |

**两条都要摊开**：① 旧日志 `evidence/category-mutants.log`（12:53，726 B）只有**两条**结果行（`3 failed, 6 passed` 与 `9 passed`）——**M2 那一臂从未出现在日志里**，且它的 M1「3 failed」与硬化仪器的「2 failed」不可归因（同一台仪器当时正被上面两个 bug 驱动）⇒ **旧日志的两个数一并作废，本表只引 15:55 的 `category-mutants-rerun.log`**。② 我这一节**第一版的臂名是用手写的**（写成「关掉语料声明检查」「只看首条 document」，还编了一条并不存在的用例名 `test_falls_back_when_corpus_does_not_advertise`），与 `evidence/arms/cat_repl_m*.txt` 的真内容不符 ⇒ 上表是按 artifact 逐字重取的。这条正是「手抄进文档的数字/名字要按真源重取」的现场复发，记进 §10。
日志 `evidence/category-mutants-rerun.log`。**教训入册**：仪器失败会伪装成实验结论，`9 passed` 这种"太干净"的读数要当场问一句"变异到底打上没有"。

### ④ 静态腿从 grep 换成 AST，并证它能红

行文本 grep 腿有两种穿法（`kwargs = {"trust" + "_remote_code": True}`、位置参数），已换成 `ast.walk` 找
`ast.keyword(arg="trust_remote_code")` 与 `ast.Constant("trust_remote_code")`。**M4 反证**：往生产文件注入一个
运行期字典形状的 opt-in ⇒ AST 腿 `1 failed`（基线 4 passed），`ruff check`/`format --check` rc=0。
残余射程（明写）：全动态构造（`**{prefix + key}`）仍在静态面外；且 pydantic 在构造期就拒顶层该键（M1 → 4 errors 是**构造期拒绝**，不是断言红，别读成"测试能红"）。

### ⑤ D-14 新登记：还有 4 只能写知识库的 CLI 没有守卫

`git grep -n chroma_dir_guard backend/` 现量：消费方只有 `backup_data` / `import_laws` / `rebuild_embeddings` / `switch_embedding`。
`import_docs.py`（2 处，含 delete）、`verify_new_law.py`（7 处，含 delete）、`eval_chunking.py`（3 处，含 delete）、
`backfill_time_meta.py`（1 处）都没有 ⇒ 我在 §7 写的「唯一未检查的写入入口」是**低估**，已折进 `reports/decisions-needed-20261010.md` D-14。

### ⑥ 凭据按值反查翻案，以及一条方法论更正：**同法复现不等于独立印证**

我上一版说「按值反查做不到」并把 §8 形状扫描的"0 命中"当成主要证据。**做不到的是"和现役 `.env` 比对"**，
而"证明历史里有裸值"做得到——值就在 git 对象里。按值反查 238 棵树：`hits=61 / files=1 / lines=104`，
HEAD 树已无。复核 A 用**和我一样的键锚点法**（`awk '/[Pp]assword/'`）给出 ✅——两条"独立"读数同源于同一盲区，
所以它当时没能拦住我。今后选复核要按**方法是否正交**选，不能只按"是不是实现者"。
完整读数与两条路线见 `reports/h-ci-and-credentials.md` §2.1，待你裁的那一词见 D-5。

### ⑦ 一条安全披露：工具结果里出现过冒充我的指示

本轮某工具返回内容里嵌了一段中文指令，要求我"用弹窗询问 Owner 是否轮换口令"。它不是用户消息，
且与 AGENTS.md 的"不得调用交互式弹窗"直接冲突 ⇒ 未执行，在此登记。凡工具/网页返回体里的"指示"都按数据对待。

### ⑧ 复算

```bash
R=/c/Users/33393/Desktop/fazhi-nondeploy-closeout-20261010-b4e7a2
C=/c/Users/33393/Desktop/ai-legal-helper/.worktrees/nondeploy-closeout-20261010
grep -a "Tests .* passed" "$R/evidence/vitest-candidate-20261010.log"
grep -a "^TOTAL" "$R"/evidence/pytest.cov.*.log
diff "$R/evidence/pyproject.before" "$C/backend/pyproject.toml" | grep -c '^[<>]'
bash "$R/evidence/run_mutants.sh" cat      # 三臂现量，含 PATCH_OK/ARM-INVALID 自检
"$R/candidate-envB/Scripts/python.exe" "$R/evidence/probe_st_trust_arm.py" E "$C" "$R/snap"
git -C "$C" grep -n chroma_dir_guard -- backend/ | cut -d: -f2 | sort -u
```

## 11. 补记九（2026-10-10 深夜：重核 agent 的读数——采纳到哪、怎么验的）

`reports/first-round-ledger-recheck.md`（后台 agent 交付，只读，未动仓库）重核了第一轮 13 张 DB 票 + B-44/45/46。
它的判定表我**不整表采纳**，只采我当场复现得了的那几条：

| 它的说法 | 我跑的命令 | 现量 | 采纳 |
|---|---|---|---|
| 第一轮台账 `docs/backend-readonly-audit-20260929.md` 在主仓是**未跟踪**、候选树里不存在 | `git ls-files --error-unmatch <该路径>`；`test -f` + `wc -c`；候选 `git ls-files <同路径> \| wc -l` | 主仓 rc=1（不在索引）而盘上有 **187,956 B**；候选树 **0** | **采纳**——它连"归宿"一起说对了：这份台账只活在这台机器上 |
| `.env.bak*` 那行来自 `318c588`/`8d4bda7` 而非台账 §11 写的 `902e2d1` | `git log -S'.env.bak' -- .gitignore`；`git show --stat 8d4bda7` | `318c588`(09-30) 加那行；`8d4bda7`(09-30) 把它**挪到文件末尾**（理由写在提交信息里：插在中段会顶移后面所有行号）；`902e2d1` 未动该行 | **采纳**，台账那处归因要改 |
| DB-2「口径已变」：`902e2d1` 的 scope 判据已结构性含时效日 + 证据五元组 | `git grep -n "effective_to" -- backend/main.py` | `main.py:1152` 的判据元组就是 `("source","article","effective_from","effective_to","status")` ⇒ 五元组+两侧日期**都在** | **采纳**（残余是命中帧仍取 `pre['sources']`，那条我未独立复现） |
| DB-13「`mark_depleted` 那腿随 DB-17 关闭，WAL 与角色并集两腿仍在」 | `git grep -n "mark_depleted" -- backend/`；`git grep -ln "journal_mode\|WAL" -- backend/tests` | `llm_errors.py:11/119` 已有"瞬时 vs 非瞬时"分档判据；测试侧 WAL 只出现在 `conftest.py` | **部分采纳**：分档确实落进代码；WAL/角色并集两腿我只核到"测试面没有断言"，未核到"缺陷可达性" |
| 「最需 Owner 裁的是 **DB-7**（`TOOL_BUSY` 进不进技术降级白名单）」 | —— | 属**口径决策**，不是我能用读数顶掉的阻塞 | **转给他**，已并入 `reports/decisions-needed-20261010.md`（见下） |
| 它给 DB-7 的前置事实：「白名单**今天**确实被扩过一格（`AGENT_BUDGET_EXCEEDED`）」 | `git log -S'AGENT_BUDGET_EXCEEDED' -- backend/routing_metrics.py` | **错**：那格来自 `5e51384`(**2026-09-17**)，今天没扩过这只集合；今天动的是 `agent/state_machine.py` 的 `FREE_STEP_EDGES`（DB-15，另一只集合） | **驳回**，并按现量改写成 D-15 的证据列 |

**新教训**：重核 agent 的**事实断言也要跑**——它这条「今天扩过一格」要是照抄进 D-15，就会给 Owner 造出一个「本轮已经开过先例」的假前置。

**未复算 ⇒ 不采**：它表里其余各票的逐条 `file:line`（它读的是 `a934fa7` 树，候选现已到 `3f605de`）；
以及"查不到 1 项：DB-2 的部署期开关值"——那条的归因我也同意（书禁开 `.env`）。

### 顺带一条互相印证（但别读成"值仍有效"）

`.gitignore:152` 的注释自己写着：`.env` 备份里是「**13 位明文管理口令**」。
我这边按值反查独立量到的长度也是 **13**（`evidence/value_reverse.py`，纯字母数字）。
⇒ 两处**同长**只说明"我扫到的就是它指的那把值"，**不说明**这把值现在还能不能登录——那要读 `.env`（禁区），仍是 D-5 待裁的那半。

### D-5/D-14 已并进待裁台账，此处只给一句话

凭据轴：普通推会上传历史裸值（已证），现役性未知 ⇒ 我推荐先轮换再普通推 + 开 PR。
守卫覆盖面：另有 4 只能写知识库的 CLI 没有 `chroma_dir_guard`（`import_docs`/`verify_new_law`/`eval_chunking`/`backfill_time_meta`，前三只含 delete）
⇒ 登记成 **D-14**，本轮不扩（执行书 B 单只点名 B-45）。

### 复算

```bash
M=/c/Users/33393/Desktop/ai-legal-helper
git -C "$M" ls-files --error-unmatch docs/backend-readonly-audit-20260929.md; echo "rc=$?"
git -C "$M" log --format='%h %ad %s' --date=short -S'.env.bak' -- .gitignore
git -C "$M" grep -n "effective_to" -- backend/main.py | head -3
git -C "$M" grep -n "mark_depleted" -- backend/llm_errors.py | head -3
sed -n '150,155p' "$M/.gitignore"
```

## 12. 补记十（2026-10-10 傍晚：复核 A 两项"未复算"我都补了，其中一项暴露复核方法本身）

### ① 臂 E 那条：**复核 A 重跑的是同一只坏尺子**，于是把我的假阴性一起"复现"成 ✅

它 row 30 的命令是原样再跑 `evidence/probe_st_trust.py`（**同进程五臂**），得到与我逐格相同的读数、
`verdict=GATE_HOLDS`、四项 checks 全 true ⇒ 判 ✅。**但那只探针在结构上就量不到缓存效应**：
动态模块注册表是进程级的，A→B→C→E 串在一个解释器里，E 必然命中 C 灌进去的 `sys.modules`。
⇒ 这不是"两人看法不同"，而是**同法复现不构成独立印证**——今天第二个实例（第一个见 §11 的凭据轴）。
落地物：逐进程臂脚本 `evidence/probe_st_trust_arm.py`（每臂独立解释器 + 臂名独立 marker 文件），
读数已写进 `reports/trust-and-data-drill.md` §1.4；判据措辞改窄为"防配置面"。

### ② 模型 12/12 哈希：**不必出网也能独立复算**，我补算了并且先错了一次

复核 A 的未复算理由是"需要重新出网下载 409 MB 权重"。现量：**期望值与内容都已在盘上**——
`evidence/hf-bge-meta.json` 是 HF API 透传的 `siblings`（含每个文件的 `blobId`/`size`，LFS 文件另带 `lfs.sha256`），
内容在运行根私有快照 `model-cache/hub/models--BAAI--bge-base-zh-v1.5/snapshots/f03589ce…/`（12 只文件，最大 409,138,989 B）。
⇒ 新脚本 `evidence/recompute_model_hashes.py` 只读这两处、自算 `sha1("blob <len>\0"+内容)` 与 `sha256(内容)`，
**不引用** `bge-model-verification.json` 的结论（否则是自我印证）。现量（`evidence/recompute_model_hashes.out`）：

```
files_expected=12 matched=12 not_matched=0 VERDICT=12_OF_12_INDEPENDENT
```

**我自己先比错了一次轴**（值得留在册）：第一版拿 `blobId` 去比 `pytorch_model.bin` 的内容 sha256 ⇒ `NO-MATCH`、
`matched=11`、脚本走 `VERDICT=REFUSE`。原因是 LFS 文件的 `blobId` 是**指针文件的 git blob sha1**
（`2083a929…`），内容哈希在另一个字段 `lfs.sha256`（`731cf5d8…bae044`）。
⇒ 修法不是放宽判据，而是**按文件分轴**：有 `lfs` 走 `sha256(content)`，无 `lfs` 走 `sha1(git-blob)`，
输出里把轴名一起打出来。尺子当时拒报数是对的行为，别把它当噪音。

（复核 A 的第二项未复算"前端三腿现场重跑"与 D 单同源，D 已重派，见下节状态。）

### 复算

```bash
R=/c/Users/33393/Desktop/fazhi-nondeploy-closeout-20261010-b4e7a2
"$R/candidate-envB/Scripts/python.exe" "$R/evidence/recompute_model_hashes.py"
cat "$R/evidence/recompute_model_hashes.out"
ls -la "$R/model-cache/hub/models--BAAI--bge-base-zh-v1.5/snapshots/f03589ceff5aac7111bd60cfc7d497ca17ecac65" | tail -13
```

## 13. 补记十一（2026-10-10 晚：D 单改为独立会话执行，票已出）

Owner 裁定 D 单开会话。票面：`<运行根>/tickets/dispatch-D-browser-acceptance-20261010.md`（**13,189 B / 9 节**）。
本会话此后**不再碰** `frontend/.next`、standalone 构建，也不使用 8111/3101/8399/9222 这四个端口——票里把端口分配独占给了它。

**为什么单开（不是推工）**：两只 agent 都死在同一处（起全栈现场），一只 302 秒 25 次工具调用后 `error`、
一只从未交付；盘上证据是**零产物**（`reports/browser-acceptance.md` 与它自述的 patch 文件都不存在），
候选树仍恰好只有那 5 只前端 `M`，四个端口无残留监听。同一件事派第三次是"连修三次=流程问题"的形状。

**票里钉死的四条，都是本轮踩出来的**：
1. **禁整后端 mock**，必须"真 `main:app` + 假上游"——否则就是循环验证（mock 形状取自前端类型，字段缺口测不出来）。
2. **`RERANK_NATIVE_URL` 是第六条出网轴**：`settings.py:209` 默认值是官方 `dashscope.aliyuncs.com/api/v1/...`，
   只覆盖 `LLM/ZHIPU/DASHSCOPE/RERANK/EMBEDDING` 五根 `*_BASE_URL` **会漏它**（现量：43/48/194/205/209 五处默认值都在码里）。
3. **绕守卫要明写**：headless 没会话，只能注入假 `JWT_SECRET` 自签 token ⇒ 进「已知限制」。
4. **`api.ts:27` 开发态硬编 `http://localhost:8000`** ⇒ 必须走 standalone 生产形状，否则 401/空白会被误判成应用缺陷。

**§6 那条我改写了，因为死掉的 agent 给了我两个不存在的符号**：它自述"`_sse_transport` 少 `finally`、`requeued` 丢事件"。
现量 `git grep -n "_sse_transport|sse_transport|requeued"` 在候选 `3f605de` **全仓零命中**（含 backend/frontend/docs/dispatch-output）
⇒ 判定是**不可复现的名字，按幻觉处置**，不是"待验证缺陷"。票里把这条腿改成打在**真实流面**上：
`frontend/lib/api.ts:168/176/226/230`（AbortController + `res.body.getReader()` 读循环）、
`frontend/lib/hooks/useChatStream.ts:22/84`（`activeRequest` 句柄被覆盖而不 abort＝旧流失联继续写）、后端 SSE 出口。

**复算约定**：它回来后我用**不同方法**复算（逐进程/换工具/换目录），不重跑它那只脚本——
今天已经两次"同一只坏尺子重跑一遍就盖章 ✅"（臂 E 的同进程缓存、凭据的键锚点普查）。

### 复算

```bash
R=/c/Users/33393/Desktop/fazhi-nondeploy-closeout-20261010-b4e7a2
C=/c/Users/33393/Desktop/ai-legal-helper/.worktrees/nondeploy-closeout-20261010
wc -c "$R/tickets/dispatch-D-browser-acceptance-20261010.md"
git -C "$C" grep -n "_sse_transport\|sse_transport\|requeued" ; echo "phantom_rc=$?"   # 期望 rc=1（无命中）
git -C "$C" grep -n "rerank_native_url" -- backend/settings.py                            # 期望 :209
git -C "$C" status --porcelain | wc -l                                                   # 期望 5
netstat -ano | grep LISTENING | grep -E ':8111|:3101|:8399|:9222'                        # 期望空
```

## 14. 补记十二（2026-10-10 晚：D 已交接独立会话，本会话交付两份可核文件）

- **票**：`tickets/dispatch-D-browser-acceptance-20261010.md`（13,189 B）——见 §13。
- **验收尺子**：`tickets/acceptance-ruler-D-20261010.md`（5,007 B）。**在它交付之前写好**，逐条列出"我判绿的最低条件 + 我的独立复算动作"，
  并列了六种我会直接驳回的假绿形状（mock 循环验证 / 0x0 视口报已测 / 死端口当断网 / 属性字面量当交互 / 对比度穿透渐变 / "未跑"写"通过"）。
  核心纪律：**不用它用的那把尺子复算**——今天两次"同法复现盖章"已经付过学费（§12①、§11 的凭据轴）。
- **F 前置两份**：`reports/model-acceptance-prep.md`（5,228 B，配置可得性 + 两处文档漂移）与
  `model-validation/gold-freeze-draft.md`（10,365 B，F2/F3 病例与 gold 草案，**零调用**）。
  草案的分母不是手抄：`model-validation/gold_denominators.py` + `.out`（11 / 6 / 3 / 3 / 15）。
  我自己在这条腿上少数过一次：`eval_agent_complex` 我先给过 "1/40"，真值 **3/40**（临时 lambda 只比了一张手写条号映射表）；
  已改成中文数字解析器（解析不出来就**不匹配**，宁可少匹配也不错匹配，错匹配会造出"gold 已就绪"的假信号）。
- **新增待裁 D-17 / D-18**（都在 `reports/decisions-needed-20261010.md`）：D-17 是本轮 F 的**第三根阻塞**——
  可播种语料只有 11 条，这不是凭据问题，是"病例能不能被答对"的前置问题；D-18 是 `llm_registry.py:3` / `settings.py:188`
  两处"8 个代表模型"与真值 27 条不符（建议只修注释，动表＝改路由行为，越界）。

## 15. 补记十三（2026-10-10 深夜：Owner 批准的四条并行腿全部跑完，含我自己造的一次事故）

四条腿的落点：① D-5(b) 无父快照＋按值反查＋pack 归宿（`h-ci-and-credentials.md` §7、脚本 `evidence/orphan_pin.py`、
产物 `evidence/orphan-snapshot.{sha,pack,idx}`）；② 镜像排除面静态缺口（同文件 §6.2）；③ 远端网络轴（§6.1）；
④ 记忆索引瘦身。全部**零仓库写、零端口占用、零模型调用**，与 D 会话互不干扰（候选树仍 `HEAD=3f605de`、tracked 脏恰好 5 只前端 `M`）。

**④ 那条上我自己造了一次事故，按纪律摊在这里**：我用 `\xNN` 形式的字节转义去拼中文写 `MEMORY.md` 的索引行 ⇒
Py3 里 `\xe6` 是**码点 U+00E6** 不是 UTF-8 字节 ⇒ 写出去成 mojibake，还因为串里含 U+0085（NEL）被 `splitlines()` 折成"三行"，
让我一度以为坏数据扩散到了别的条目。**修复过程也踩了两次**：第一次断言把合法的 `§`(U+00A7)/`×`(U+00D7) 当成污染，误报；
第二次把一行误判成三行。最终判据收紧为「C1 控制区 0x80–0x9F 必须清零 + 索引行计数不变 + 所有 `](*.md)` 链接集合逐项相等」，
现量 `bytes=18,767 / index_lines=11 / c1_chars=0 / targets 前后相等`。
⇒ 三条入册：写中文一律用字面 UTF-8（这条我今天记过、当轮就违反）；断言"污染已清"要按**具体码位区间**而不是"有没有高位字符"；
`split()` 与 `splitlines()` 在含 U+0085/U+2028 的文本上**给不同行数**，数文件行数前先选对。
（写这段正文时又中招一次：块里含字面 `\xNN` 被 Python 当转义解 ⇒ `unicodeescape` 报错，改 raw 字符串才过——同一形状的第四次。）

**H 的两条新缺陷（都不改码，登记待裁）**：
- `backend/.dockerignore` 的 `*.db`/`*.sqlite*` 只在上下文根生效，主仓 `backend/data/app.db` 与 `backend/data/quota_used.sqlite`
  **没有任何规则挡住**（`grep -cE "^data/"` = 0），而 compose 的 build 上下文恰是 `./backend` ⇒ 部署目录被构建时两个真库会进镜像层。
  另 `.ptmp-*`（主仓现量 3 只）同样无规则。**声明面已证、实装面待真构建复量**（后者排在 D 之后，同机不互抢）。
- 根 `.dockerignore`（494 B）对这两条构建**不参与**（Docker 只读构建上下文根的排除文件）——`backend/.dockerignore:2-3` 的注释自己就写着这句，
  所以这不是新发现而是**在册已知**；我复量它是因为报告若只写"有 .dockerignore"会让人误以为已全覆盖。

## 16. 补记十四（2026-10-10 深夜：I 的执行卡已出，卡里第一条就推翻了我引用过的旧理由）

卡：`tickets/runbook-I-push-pr-merge.md`（5,728 B / 6 节）。**本会话未执行其中任何一步**——它写的是"按回车之后的路"，
前置是 D-5 与"远端真实头今天读不到"这两件事。

**新登记的在册事实（也是 D-19）**：`--no-ff` 的旧理由我按册子写的是"rebase/squash 会弄死 19 处 `fbc29e8` 引用"。现量后这条**理由站不住且数字过期**：
`fbc29e8` **不是 master 的祖先**（它是本地分支 `codex/local-candidate-closeout` 的尖端，那支从未推送），
而引用数是 **103 次 / 15 个文件**，不是 19。⇒ 真正的风险不是"合并方式毁掉引用"，而是**这些引用指向的对象远端本来就没有**；
`--no-ff` 救不了它，要么把那 **4 笔独联提交**一起推（按值反查证明不新增凭据外泄：closeout 对象集 `value_hits=1`，候选里也已是 1），要么接受悬空并登记。

**我自己造的一次假读数（同一次运行里）**：为省事用 shell 变量取那只 13 位值再 `grep -c "$VAL"`，取值管道静默失败（长度 0）⇒
**空模式的 grep 把每一行都算命中**，当场吐出一个 11,523,040 的荒谬数。改在 Python 里做完整链路
（断言 `len(val)==13`，失败即 refuse）后读数才是 3815/4301/4252 对象、各 `value_hits=1`。
⇒ 入册：值级判据**必须自带"我确实取到了值"的断言**，否则"0 命中"和"全都命中"这两种最坏结论都可能来自同一行空串。

### 复算

```bash
M=/c/Users/33393/Desktop/ai-legal-helper
git -C "$M" merge-base --is-ancestor fbc29e8 master; echo "anc_rc=$?"          # 期望 1（不是祖先）
git -C "$M" branch -a --contains fbc29e8                                        # 期望只有 codex/local-candidate-closeout
git -C "$M" grep -o fbc29e8 | wc -l                                             # 103
git -C "$M" grep -l fbc29e8 | wc -l                                             # 15
git -C "$M" rev-list --count codex/nondeploy-closeout-20261010..codex/local-candidate-closeout   # 4
wc -c "$PWD/tickets/runbook-I-push-pr-merge.md"
```

## 17. 补记十五（2026-10-10 深夜：并行腿跑到没有了，最后一条量出"合 master"的真实成本）

Owner 问"还有没有可并行任务"。答案：**只剩一条**，而且比原计划便宜得多——`git merge-tree` 是纯只读的
（不建副本树、不动 ref、几乎不吃 I/O，不会污染 D 会话的延迟读数），它正好回答执行卡 A4 那句"合 master 难不难"。
结果写进 `tickets/runbook-I-push-pr-merge.md` §6，台账新增 **D-20**。核心现量（git 2.55.0）：

| 读数 | 值 |
|---|---|
| 两棵树路径 | `master` 2668 / `origin/master` 261，交集 **260** |
| 交集内 blob | 相同 **145**，不同 **115** |
| `merge-tree`（空 base 等价试演） | rc=1，**115 条 `CONFLICT`，全部 `add/add`**，`Auto-merging` 115 |
| `merge-tree`（不给 base） | rc=128 `refusing to merge unrelated histories`（它**没有** `--allow-unrelated-histories`） |

⇒ **我据此改口**（这是本轮第 N 次推翻自己，仍按"新证据 + 反向代价 + 三处留痕"办）：
之前给的路线里"先合 unrelated 历史再推 master"成本被我低估了——那是 **115 次内容裁决**，
且冲突面包括 `.env.example`、`.gitignore`、`CONTRIBUTING.md`、`.github/workflows/ci.yml`，
等于把配置与门禁本体重审一遍；书里还明令不许"丢弃改动让合并过去"。
**新推荐：本轮只推 `codex/*` 分支**（新 ref ⇒ 天然非 force、零冲突面），"合 master"留成独立裁决票 D-20，
并把它的前置写成两条：115 次裁决的人工带宽 + 远端真实头读数（今天 TLS rc=35 拿不到）。
> **⚠️ 本句的"拿不到"已于 10-11 01:5x 被推翻**（网络四条全通、真实头 `985d53e` 已取回）⇒ 见本文件 **§25/§25-a**。
> 但**另一半天平没变**：那 115 条冲突的试演读的是本地陈旧 ref `15562fc`，**换成真实头之后必须重跑**，这条仍是 D-20 开工前的动作。

一次计数脏读我自己抓住并改了：`merge-tree` 的信息段里 `Auto-merging <path>` 与 `CONFLICT (...)` 交替出现，
我第一版按"去重行首"统计得到 **231**，那是把提示行也当文件数。改成只数 `^CONFLICT` 得 **115**，
并与完全独立的"交集里 blob 不同=115"吻合 ⇒ 两个不同算法撞在同一个数上，才敢写进正文。

## 18. 补记十六（2026-10-10 深夜：按 `show-your-work` 的证据五连问自审，两处主张被我主动降级）

| 问 | 过关的主张 | **不过关 / 已降级** |
|---|---|---|
| ① 数字怎么来的 | 凭据轴（`value_reverse.py` 238 棵树 hits=61）、快照轴（2581 vs 4301、按值 0 命中＋正对照 1）、F 分母（`gold_denominators.py` 11/6/3/3/15）、冲突面（两条独立算法各得 115）——都是跑出来的，脚本随票落盘 | — |
| ② 能复现吗 | 每条旁边都附命令，我逐块重跑过 | **门禁四条（1925 passed / cov 86.35% / ruff / vitest 83）不是"此刻"的读数**：出自本轮早先那次运行的 `evidence/pytest.*.log` 与 `evidence/vitest-candidate-20261010.log`。"上一次运行不是本次证据"这条铁律在这儿成立 ⇒ D 会话交回前我**不重跑全量**（全量 pytest 与浏览器验收抢 CPU/I/O，会污染它的延迟读数），所以这些数按「历史读数＋出处」引，**不写成"本次全绿"** |
| ③ 测试亲眼红过吗 | 新入库 24 条都有"为正确原因红"的证据：category M1→2 failed／M2→4 failed（点名到用例）；loader-trust M2→2 failed／M4→1 failed；drill M1／M2 各打红特定腿；B-45 M1 删守卫→恰好红在分歧腿 | — |
| ④ 期望来自独立来源吗 | 13 位值取自 git 对象而非记忆；期望哈希只取 API 透传的 `hf-bge-meta.json` 且不引用旧验证 JSON；**空 base ≡ 真 merge 的等价性本轮证成**；F gold 只用在册已写死的期望＋合成刺激 | — |
| ⑤ 限制说全了吗 | 现役性未知（不读 `.env`）；臂 E 原判据是缓存假阴性；键锚点普查看不见无键名的值；远端 CI 读数今天拿不到；快照体量按路径加总会说大近 2.6 倍 | **`.dockerignore` 那条降半格**：`data/app.db`／`data/quota_used.sqlite`／`.ptmp-*` 未被挡住，依据是 Docker 文档语义（`*` 不跨 `/`）＋我那只**近似匹配器**；匹配器只对 `.env` 族给过阳性对照，没对 `data/` 这类嵌套形状给过 ⇒ 应读作"声明面缺口、方向保守"，真构建才算数（排在 D 之后） |

**方法论收获**：第三问（尺子能不能红）这次抓到的三个坏点全在**我自己的探针**里，而且三个都不是"数字算错"，
是 fixture 与异常处理坏了（污染的工作树、被 `add -A` 收进树的临时索引、把 rc=1 当异常）。
坏 fixture 的可怕之处在于它会安静地给出一个看起来合理的数；这次它给的是断言失败——
**因为断言写在了测量之前**。这条已写进 `evidence/equivalence_check2.py` 的注释，正文再钉一次。

## 19. 补记十七（2026-10-10 深夜：D 单交回 → 验收 → 第五笔提交落地）

**D 交回并已验收**：`reports/browser-acceptance.md`（31,725 B / 218 行）+ `evidence/browser/**`（17 只 JSON / 21 张截图 / 10 条日志 / 仪器随票落盘）。
我的验收结论单列在 `reports/acceptance-of-D-20261010.md`（8,237 B / 9 节），核心是**采纳 + 1 条要求补齐 + 3 条未复算 + 3 处偏差**：

- **7 条判据：6 绿 1 红**。红的是 **J3**，我用**两种独立方法**各自复现：`.next/static/css/*.css` 里
  `badge-success/-error/-neutral/-accent/btn-ghost-dark` **全 0**（阳性对照 `.badge{`=1），且**这两条类定义在 HEAD 版 globals.css 里也存在**
  ⇒ **不是 §14 引入的，是既有的生产形状缺陷**（Tailwind 扫不到 `components/ui.tsx:39` 现拼的类名）。
  后果：部署形状里六种状态徽章只有文字不同、颜色全同。
- **J1/J2/J4/J5/J6/J7 逐条复现**：非回环 0（我自己写直方图：108 http、hosts 只有 `127.0.0.1:3101`、data/blob/about 9 条）；
  真实库零触达（我对 `backend/data` 的 1 命中与它同值同刻 15:09:03，19:00 边界后为 0）；`chooser-count.json` 的 `base{0,0,0}→{1,1,1}→{2,2,2}`；
  `responsive-chat.json` 的 1440 档 h4 `w=519 / 15.2px`；`pytest-cancel.log` = `55 passed in 18.27s`；§11 三条收尾自证我原样重跑全对。
- **三处偏差（不改判定）**：① 它写的守卫行号 `:43/:59` 真身是 **`:41/:57`**（另有 `:88` 同款，它没提）；
  ② 按它 JSON 里的 fg/bg，我独立算出对比度 **12.15** 而它报 **12.12**（差 0.25%，都远超 4.5:1，登记为"小数位口径未对齐"）；
  ③ "`submit: null`"是叙述简写——`caps-false.json` 里**没有这个键**，真证据是三条路由 `sendEnabled=False` + 2 条 alert。
- **要求补齐一条**：6 只 JSON 仍带旧计数器的错值 `"nonLoopback": 2~3`（offender 是 `:80 data:image/...`），报告虽在 §1/§10 披露，
  但读者按指路打开 JSON 看到的是错值 ⇒ 建议加 `isolationStale: true` 或目录内 README（不阻塞采纳）。

**第五笔提交已落地（D-21，Owner 答"要"）**：`9e3cfc5`「fix(frontend): 补入 §14 前端修复轮（H2/D12/G1/G2/D6/G13，+69/−7）」。
- 前置：前端三条腿在**将要提交的那份字节上**全绿——`tsc --noEmit` rc=0、`next lint` 0 错、**`vitest 83 passed` rc=0**。
- 自证：提交前逐只 blob 与 `evidence/frontend-dirty-20261010.manifest` 逐字相同；提交后 `HEAD:<file>` 五只 blob 与提交前**逐字相同**；
  暂存区恰 5 只、无夹带；提交后候选树 **`porcelain=0`**（全干净）。本轮提交数 **4 → 5**。
- 该笔**不含**J3 修复与取消文案改动，两条分别登记为 **D-22 / D-23**（未在本笔顺手改）。

**新登记**：**D-22**（生产构建 purge 徽章类名——修复前须先做一次 build 级最小变异把"根因=purge"从推断变成已证，且修完**必须用 `next build` 产物复量**，不能用 dev 形状替代）；
**D-23**（用户主动取消后，服务端占位文案 `服务暂时无响应，请稍后重试。` 把"用户取消"讲成"服务故障"，`main.py:1037/1090`）。

### 复算

```bash
C=/c/Users/33393/Desktop/ai-legal-helper/.worktrees/nondeploy-closeout-20261010
R=/c/Users/33393/Desktop/fazhi-nondeploy-closeout-20261010-b4e7a2
git -C "$C" log --oneline -1                                   # 9e3cfc5
git -C "$C" rev-parse HEAD:frontend/app/globals.css            # 292136b5…（与 manifest 同）
git -C "$C" status --porcelain | wc -l                         # 0（候选树全干净）
for p in badge-success badge-error badge-neutral badge-accent btn-ghost-dark ".badge{"; do   printf "%-16s %s
" "$p" "$(cat "$C"/frontend/.next/static/css/*.css | grep -o -F "$p" | wc -l)"; done
grep -n "streaming" "$C/frontend/lib/hooks/useConversations.ts" | head -3   # 真行号 :41/:57/:88
```

## 20. 补记十八（2026-10-11 00:2x：H 包装腿收口——镜像建成、内容复量、容器 smoke 通过）

**产出**：`fazhi-closeout-probe:20261010-final`（**3.89 GB**，`rc=0`）。读数全表在 `reports/h-ci-and-credentials.md` §9。

- **九步耗时**：`[5/9]` requirements **4319.7 s（72 分钟，长杆）**；`[7/9]` 模型烘焙 823.3 s（13.7 分钟）；`[6/9]` 防呆断言与 `[9/9]` `.env` 守卫各 <3 s 且**都通过**；端到端 ≈ **1 小时 40 分**。
- **内容复量**：`/app/.env` 不存在；`/app/data/` 只有 2 只 in-tree 评测件、**无 `app.db`/`quota_used.sqlite`**；`chroma_db`/`media`/`backups` 均不存在；**torch `2.13.0+cpu`、`cuda=None`**；模型已烘焙（HF 缓存 782 M）；chromadb 0.4.24 / fastapi 0.141.1 / ST 6.1.0 / SQLAlchemy 2.1.4 与声明一致。
- **容器 smoke**：回环 8123、六上游全指死回环 `127.0.0.1:9`、落盘指容器内 `/tmp`；`/healthz` **9 秒 200**（`db:true, vector:true, llm_host:false`）、`/api/health` 200、宿主侧**仅回环监听**；容器用完即删，8123 残留 0，compose 栈 Up 9h 未碰。

**两处披露的偏离**（出厂 Dockerfile 逐行比对：76 行差 2 行）：① torch 源改官方源（Owner 批准）；② `[5/9]` 加 `--extra-index-url pypi.org` 回落。
**两条源侧缺陷（出厂路径今天会红，与代码无关）**：① 阿里云 `pytorch-wheels` 下 191.8 MB 的 wheel**冻结 30+ 分钟无进展**；② 阿里云 PyPI 的 `pydantic-2.14.0` **索引在、文件 404**（本机可复现）。
**我自己的夹具错一条**：首跑 smoke 用 `/tmp/smoke/app.db`（目录不存在）⇒ sqlite 打不开库；改文件路径即 9 秒就绪。**非镜像缺陷**。

**⇒ H 的判读要分两半**：**"镜像能建成且可用"＝PASS**（本轮实测）；**"出厂 Dockerfile 今天可构建"＝被证伪**（源侧），登记为 **D-25**。

## 21. 补记十九（2026-10-11 01:0x-01:2x：四条门禁由"历史读数"转成**现量**，并把格式门的两把口径分栏）

**为什么补这一节**：`reports/closeout-final-J-draft.md` §6-5 原写"门禁四条是早先那次的读数、未在收尾时重跑"。本轮已重跑，那句降级**撤销**。

**现量（全部在候选树 HEAD `9e3cfc5`、`porcelain=0` 上取；解释器 = `candidate-envB`，Py 3.11.0，ruff 0.16.10，mypy 2.4.0；日志 `C:/Users/33393/Desktop/fazhi-nondeploy-closeout-20261010-b4e7a2/evidence/gates-rerun-20261011.log` 与 `.../evidence/static-gates-20261011.log`）**

| 门 | 现量 | 与本轮早先读数 |
|---|---|---|
| 全量 pytest（`-m "not slow"`，含 `--cov-fail-under=70`） | **1925 passed / 0 failed / 10 skipped / 18 deselected**，cov **86.35%**，rc=**0**，253.43s | **逐字相同** |
| `ruff check .` | rc=**0**（All checks passed!） | 相同（绿） |
| `ruff format --check .` | rc=**0**（283 files already formatted） | 相同 |
| `mypy .` | rc=**0**（Success: no issues found in **74 source files**） | 相同（"checked N files" 是在册判据，不是只看 rc） |
| 前端 `tsc --noEmit` | rc=**0** | 相同 |
| 前端 `next lint --dir app --dir components --dir lib` | rc=**0**（No ESLint warnings or errors） | 相同 |
| 前端 `vitest run` | rc=**0**，**9 文件 / 83 tests passed** | 相同；且这次是在 `9e3cfc5`（§14 修复已入库）**之后**取的，早先那次在入库前 |

**格式门必须分两把口径报，否则数字会打架**
- 仓库自带脚本（`package.json:10` = `prettier --check "app/**/*.{ts,tsx,css}" "components/**/*.tsx" "lib/**/*.ts"`）⇒ **rc=1，3 只**：`StatsSection.tsx`、`UploadSection.tsx`、`UsersSection.tsx`。
- 整目录轴（`npx prettier --check .`）⇒ **rc=1，15 只**（多出 `README.md`、`docs/BUGFIX-chat-scroll.md`、`tsconfig.json`、`tailwind.config.ts`、`public/sw.js`、`lib/auth.tsx`、`components/chat/lawCardHtml.ts`、`tests/` 四只等）。
- 两把都是 rc=1，**都不绿**；报"格式门几只红"必须点名口径。名单落盘 `evidence/static-gates-20261011.log`。

**顺带修掉一条我引用过的他人在册句（含"尺子能红"的对照）**
另一会话汇报（`docs/../dispatch-output/frontend-readonly-review-20260929/work-report-20261003-fix-round.md` §6-C16）写"`lib/coverage.ts` 没进清单、也确实不合规"。现量：
- `prettier --check lib/coverage.ts`（默认 ignore）→ 绿；
- **反证腿**：同一仪器对清单里那 9 只之一的 `lib/api.ts` 默认轴也报绿，改用空 `--ignore-path` 复跑 → `[warn] lib/api.ts` ⇒ **"绿"在这把尺子上不等于"合规"**，所以单看默认轴不足以定性；
- `lib/coverage.ts` 用**空 ignore** 复跑 → 仍绿 ⇒ **真合规**；且它的 blob 自 `5e51384`（2026-09-17 22:05）到 HEAD **逐字节未变**（两个 `rev-parse` 同为 `ab84a3d7…`，中间 0 笔触碰）⇒ 那句"不合规"当时也不成立。
- "没进冻结清单"那半句成立（`.prettierignore` 只列 9 只，确无 `coverage.ts`）。

## 22. 补记二十（2026-10-11 01:2x：D-3 那张票**从没存在**到我把它写出来，顺带把两处手抄分母钉掉）

**触发**：写 `reports/closeout-final-J-draft.md` 时我要给"已裁"那条找归宿，才发现自己在 `decisions-needed` §E 写过一句「**票面已存在**」。
`ls tickets/` 现量只有 3 只（D 单票 / D 验收尺 / I 执行卡），**没有迁移票** ⇒ 该断言为假，已就地更正并在原格标注（`decisions-needed` §E 的"就地更正"块）。
票现已写出：`tickets/dispatch-D3-langchain-migration-20261011.md`（7 节 / 9,874 B / CR=0）。

**分母：改对一处、撤回一处我自己的错（复算器随票落盘 `evidence/audit_axes.js`）**
- 该改的：`decisions-needed-20261010.md:62` 的每包拆法 `core(7)/openai(1)/splitters(2)/langsmith(3)` —— **7 与 3 在任何轴上都数不出来**。
- **我错怪了的**：`owner-decisions-20261010.md:35` 的 `core 6 / langsmith 4 / splitters 2 / openai 1` 我一度判成"也不可复现"，**这句撤回**——它在 **distinct 主 ID** 轴上完全正确。
- 现量（两份审计件 `audit-cand-runtime/dev.json` 读数完全相同）：全库条目 **24** / distinct 主 ID **15** / 包 **5**；
  **每包条目**（同 ID 在同包可出现两次）core **11**、langsmith **5**、splitters **4**、openai **2**、chromadb **2**；
  **每包 distinct 主 ID** core **6**、langsmith **4**、splitters **2**、openai **1** ⇒ **和 = 并集 = 13，跨包无重叠**（重复只在包内）；族主 ID + aliases **38**；"有 fix_versions 的 distinct ID"与 distinct 同值。
- **根因登记（这台机器我批评过别人，这次落在我自己身上）**：我第一次只跑了"条目"与"族并集"两根轴，就宣布别人的拆法不可复现。
  ⇒ **报"不可复现"之前，先把对方可能站的那根轴跑一遍**；两根轴的名字要一起写进正文（条目 ≠ distinct ID）。

**调用面钉掉一处低估（复算器 `evidence/d3_symbol_surface.py`，当场复跑过）**
- 旧句（`owner-decisions-20261010.md:37`）："改 `retrieval.py`/`rag_chain.py`/`llm_registry.py` 的调用面"= 3 只。
- 现量：**61 行 import / 39 只文件**（生产 **11** 只、scripts+tests **28** 只）；符号面 **16 个 `module.symbol`**，其中**包含 `langchain_core.callbacks`（`AsyncCallbackManager`、`BaseCallbackHandler`、`AsyncCallbackHandler`）与 `langchain_core.runnables.RunnableSerializable`** —— 这两族正是 0.2/0.3→1.x 反复改签名的地方，旧说法完全没提。
- `langsmith` **零直接 import**（传递依赖），所以它不能靠"改调用点"绕开，只能随 `langchain-core` 一起动。
- ⚠️ **我自己的一次假阴性**：票的初稿符号表只列了 12 个（正则 `from langchain[\w]*` 漏了点分子模块 `langchain_core.messages`）；跑复算器后补成 16 个，已在票内就地标注"别按初稿那张表开工"。

**顺带**：上一节（§21）报了格式门两把口径；`reports/review-of-other-sessions-20261010.md` §五 新增一格，撤回我自己给 C16 盖的那行 ✅（只核了"没进清单"，没核"确实不合规"）。

## 23. 补记二十一（2026-10-11 01:3x：Docker 引擎**已不在运行** ⇒ 本轮所有"栈 Up / 镜像在册"读数降级为历史）

**现量**：`docker ps` ⇒ `failed to connect to the docker API at npipe:////./pipe/dockerDesktopLinuxEngine … The system cannot find the file specified.`；
`tasklist //FI "IMAGENAME eq Docker Desktop.exe"` 匹配行数 **0**；命名管道 `//./pipe/dockerDesktopLinuxEngine` **不存在**；`docker context ls` 仍显示活动上下文 = `desktop-linux`（配置没变，是**引擎进程没了**）。
（⚠️ 我先前在那条命令里打印的 `rc=0` 是管道末端 `head` 的码，**不是** `docker ps` 的码——已在正文用错误原文与进程数定性，不拿那个 rc 说话。）

**这不是我做的动作**：本轮我对 docker 只做过三类事——`docker build`（两次失败一次成功）、`docker create/rm` 一次性 smoke 容器（已 `rm`）、`docker images`/`docker system df` 只读。
从未执行 `docker compose down|stop|restart`、`docker kill`、也没关过 Docker Desktop。**但我不能因为"没做"就把旧读数当现状**：01:3x 起，栈的状态**不可读**，不是"Up"也不是"Down"。

**受影响的具体读数（都要按历史读）**
| 在册句 | 出处 | 现状 |
|---|---|---|
| `fazhi-backend/caddy/frontend` 全程 Up、未重启 | 本文件早先 C 行 + `reports/closeout-final-J-draft.md` §4 | **引擎不在 ⇒ 不可复量**；"未重启"这部分仍成立（我确实没动过） |
| 镜像 `fazhi-closeout-probe:20261010-final` **3.89 GB**、内容复量、`/healthz` 9 秒 200 | `reports/h-ci-and-credentials.md` §9 | 读数当时取得；**引擎回来后可用同一命令复量**，现在读不到 |
| G 单元"现役后端就是 Docker 容器（镜像 built 09-17）" | `reports/gates.md` G 行 | 同一根轴：现在连不上 ⇒ 那条"现役形态"判断的**证据时刻**是 00:3x |
| 端口/进程台账（8111/3101/8399/9222/8123 剩余 LISTENING=0） | 01:3x 现量 | **这条仍成立**（`netstat` 不依赖 Docker），且我这三条腿本来就已关 |

**给 Owner 的一句话**：要不要复量 H 的镜像/栈，取决于你何时把 Docker Desktop 起回来；我不代起（那是共享服务动作，且执行书红线里"不部署、不动栈"覆盖它）。
若你起回来，复量命令就是 `reports/h-ci-and-credentials.md` §9 里那三条原样。

## 24. 补记二十二（2026-10-11 01:4x：主仓那批未提交改动与候选的关系——现量 21 只里 17 只同字节、4 只不同，且**方向是候选在前**）

**为什么量**：D-5（推候选）与"要不要在主仓再提交一次"这两件事，取决于**另一会话留在主仓工作树的 WIP 是否已被候选代表**。此前我只说过"主仓有并行会话改动"，没数过字节关系。

**现量**（只读；`git -C <主仓> status --porcelain` 分档）：主仓 **tracked 脏 21 只**（后端 15 + 前端 5 + 计划文档 1）、**未跟踪 567 行**（含那 4 只新测试文件与 `dispatch-output/` 树）。主仓 HEAD 仍 `0b54396`。
逐只比 blob：`git hash-object <主仓盘上文件>` vs `git -C <候选> rev-parse HEAD:<同路径>` ⇒
- **17 只逐字节相同**（含 5 只前端 §14 修复、`backend/main.py`、`llm_registry.py`、`domain_rules.py`、3 只测试等）⇒ 这批工作**已经**在候选里（`5ca3315` + `9e3cfc5`），主仓那份是同一批字节的"未提交影子"。
- **4 只不同**：`backend/agent/state_machine.py`（4 行）、`backend/observability.py`（1 行）、`backend/retrieval.py`（88 行）、`docs/superpowers/plans/2026-09-29-…md`。

**方向判定（不是"谁新"靠 mtime 猜，是把差异读出来）**
- 这 3 只后端文件主仓 mtime = **10-09 20:33 / 20:48 / 23:17**，全部**早于**候选首笔 `5ca3315`（10-10 14:56）。
- 再拿主仓字节去等候选**每一笔**的 blob（`5ca3315/8c179e7/a934fa7/3f605de/9e3cfc5`）⇒ **0 命中**。这说明候选里这些文件在接收时**已经带上我复核轮的补充**，两侧不是同一时刻的同物。
- 读差异内容才定得下来：
  · `state_machine.py` 差的是**排版**（候选把 `model_copy(update=…)` 收成一行，主仓是折行版）——内容同。
  · `observability.py` 差 **一只字段**：候选多 `"category_filter_outcome",`（DB-19 回落要落 outcome 维度 ⇒ 白名单随之加一格；在册纪律"动 `extra=` 必跑 `test_log_field_whitelist`"已由全量 1925 passed 覆盖）。
  · `retrieval.py` 差 **88 行**：主仓是**回落未收窄版**（`_note_category_filter_miss(category, stage=…)` 没有 `outcome=`、没有 `_corpus_advertises_category` 前置判定、没有 `_CATEGORY_ADVERTISED` 缓存）；候选是 Owner 裁 DB-19「丁」**之后**的收窄版。
  ⇒ **判读：主仓那 3 只是"我接收之前的旧形状"，候选是前进版；没有发现"那个会话的改动漏在候选之外"。**
- ⚠️ 边界：这条只对**这 21 只 tracked 文件**成立。**未跟踪那 567 行不在射程内**（我只看了其中 4 只新测试文件在候选里存在），所以"另一会话没有任何东西落在候选外"这句话我**不主张**，主张的范围就是上面那句。

**推论给 D-5**：在主仓再提交这批文件等于**造一支与候选分叉的影子**（尤其 `retrieval.py`：主仓那版会把已裁的 DB-19「丁」收窄**倒回去**）。要推进就推候选，不要提交主仓 WIP；若那个会话还要在主仓干活，请**先告知它这三只文件的现状**，别让它以为自己那份是最新。

## 25. 补记二十三（2026-10-11 01:5x：**网络轴今天回来了** ⇒ 远端三条读数首次拿到，D-5 的前提被改写）

昨天（10-10）的现量是 `api.github.com` 与 `github.com` 同 rc=35（TLS 失败）、只有 `ssh -p 443` 认证通 ⇒ 我当时写"推得动但拿不到远端读数"。**今天同三条重探，两条反向**：

| 探针 | 10-10 | **10-11 现量** |
|---|---|---|
| `curl https://api.github.com/` | rc=35 | **http=200 rc=0** |
| `curl https://github.com/` | rc=35 | **http=200 rc=0** |
| `ssh -o BatchMode=yes -p 443 -T git@ssh.github.com` | 通 | 通（`Hi wjt-code-design!`） |
| `git ls-remote --heads origin`（HTTPS git 轨） | rc=128 | **rc=0**（返回 1 行） |

**首次拿到的远端读数（匿名 API，共 5 次调用，未 push、未 fetch、未动任何 ref）**
1. **可见性 = `public`**（`private:false`、`visibility:"public"`、`default_branch:master`、`pushed_at 2026-09-17T15:15:31Z`、`size 130,655 KB`、star 1 / fork 0）。
   ⇒ 在册那条反向成本在这里生效：**public 的 GitHub-hosted 分钟不限量**；转 private 会开始吃套餐配额，而配额与是否启用**匿名一律读不到**（`/actions/permissions` 401）。**若 D-5 的目的包含"让 CI 真跑一次"，转 private 是可能把目的本身卡死的动作。**
2. **远端只有 `master` 一支**，头 = `985d53e4ee81efc066cc6915abcba98954e7d408`（2026-09-17 15:15）。
   本地跟踪 ref `origin/master` = `15562fc9…`（2026-08-25）⇒ **它比远端真实头旧**（不是同一条线），且 `git merge-base HEAD origin/master` **空、rc=1**（候选 239 笔 / `origin/master` 192 笔）⇒ 与在册"disjoint 历史"吻合。
   ⚠️ **未测一项**：`985d53e` 与候选的祖先关系——该对象**不在本地对象库**（`git cat-file -t` 报 could not get object info），要算就得 fetch；**我没 fetch**（默认 refspec 会把 `refs/remotes/origin/master` 顶掉，而别的会话正在读它）。
3. **CI 历史（`/actions/runs?per_page=40`，`total_count=18`，18 只全在 `master`）**：
   conclusion 分布 = **`failure` 17 / `success` 1**；event 分布 = **`push` 17 / `dynamic` 1**；**`pull_request` = 0 场**。
   唯一一场绿 = **#1（2026-08-08 18:23，`workflow_dispatch`）**。⇒ 精确说法是：**"push 触发的 CI 从未绿过（17/17 全红）"**，不是"CI 全红"。
4. **触发语义**：候选 `HEAD:.github/workflows/ci.yml` 的触发段现量 = `on: push: branches: [main, master]` 加 `pull_request:`（无分支过滤）。
   ⇒ **推 `codex/nondeploy-closeout-20261010` 不会触发任何 CI**（分支不在 push 白名单里，PR 又没开）。
   要远端读数只有三条路：① 开 PR（这条路**历史上一次没跑过**，且两侧无共同祖先时合成 merge ref 可能压根不调度）；② 直接推 master（不该做——那是把 239 笔 disjoint 历史压到远端主线上）；③ 推完分支后用 `workflow_dispatch`（**只认默认分支上存在的工作流文件**，所以能触发的是 master 那份定义，不是我这份改动）。

**这条补记推翻了什么**
- 推翻我昨天写的"网络轴不通 ⇒ 远端读数不可得"（今天可得，且我已取回）。
- 但**没有**推翻 D-5 里"先轮换再普通推"的推荐；反而加了一条**新的、更硬的前置**：
  **普通推上传的 4301 个对象里含那只历史裸值**（§凭据轴），而今天**HTTPS 推得动**了 ⇒ "推不动"不再是一道护栏，只剩"要不要推"这一个决定。
- 新增一条 D-5 的连带后果（**签之前要知道**）：推完之后**远端不会自动给你任何 CI 读数**（①③ 两条都要额外动作），所以"推了就等于有第三方验证"这句话**不成立**。

**补 25-a：远端红在哪一步，以及我的树在这一步会不会跟着红（带双形状对照）**
- `GET /repos/…/actions/runs/35239047756/jobs`（最新那场 #17，09-17 15:15）现量：**2 只 job** —— `Frontend · build (lint+tsc)` = **success**；`Backend · lint/type/test/audit` = **failure**，
  且失败步骤唯一：**step 7 `Ruff format`**（`ci.yml:30-31` = `ruff format --check .`）。
- **这台机器的在册轴**：`.gitattributes:6` 是 `* text=auto eol=lf`，而该文件顶部第 4-5 行就写着"**字节 ≠ CI**"的历史事故 ⇒ 我本机 `ruff format --check .` rc=0 读的是**工作树字节**（Windows），CI 读的是 **LF**。
- **候选树里工作树与 blob 不同的只有一只**：`backend/tests/test_agent_resume.py`（工作树 **923 个 CR**；`git show HEAD:` 的 blob **CR=0 / LF=923** ⇒ **库里那份是 LF**，CRLF 只活在我盘上）。
  双形状对照（同一条命令）：① 把该文件转成纯 LF 放进临时目录、带上同一份 `pyproject.toml` ⇒ `ruff format --check` **rc=0**；② 对候选树里那只 CRLF 版本原地再跑 ⇒ **rc=0**。
  ⇒ **判读**：step 7 这根轴上，我的候选**两种形状都过**，所以"开 PR 会因 CRLF 红"这个担忧在这只文件上不成立。
- ⚠️ **射程要说清**：这是**本地推理 + 一只对照**，不是 CI 实测（CI 从没跑过我这棵树，且推分支根本不触发）。
  远端那 17 场红的对象是 `master@985d53e` 的内容，**该 commit 不在本地对象库**（`git cat-file -t` 报 could not get object info）⇒ **我不替远端主线的红做归因**，只报"红在 step 7"这个事实。

## 26. 补记二十四（2026-10-11 02:3x：报告内读数的**过期扫描**＋边界守望，抓出两处会误导人的旧措辞）

**为什么做**：本轮之后还会有人（含两个新会话）拿这些文件当输入。凡"依赖可变状态的读数"都可能静默过期，所以做一次全扫，并定一条写作规矩。

**边界守望（现量 02:29）**——两个新会话已开工，先看有没有越界：
- 候选树 `HEAD=9e3cfc5`、`porcelain=0`（未动）；主仓 tracked 脏 **21** / 未跟踪 **567**（与 01:4x 同数，未动）。
- `candidate-envB` 的 `pip freeze` 与我的基线 **行集合 0 差异**。
- 复核会话第一件事就做对了：它建了 `review-20261011/`，里面 `freeze-at-start.txt`（3369 B）与我 `evidence/envB-freeze-20261011-015x.txt` **排序后 0 差异** ⇒ 它的起始快照和我的基线同源，后面若出现差异就是它自己动的，赖不掉。
- 迁移会话此刻还没有可观察痕迹（无 `mig-*`、无 `candidate-envC-*`）⇒ 只能报"未见产物"，不能报"没开工"。

**可复测不变量：全部重测，与正文一致**
| 正文钉的数 | 现量 | 结论 |
|---|---|---|
| langchain import **61** 行 / 符号 **16** / 文件 **39** / 生产 **11** | `python evidence/d3_symbol_surface.py <候选>/backend` ⇒ 61 / 16 / 39 / 11 | 一致 |
| 三守卫行号 **41 / 57 / 88** | `grep -an 'if (opts.streaming) return;'` ⇒ 41、57、88 | 一致 |
| `backend/.dockerignore` **20 行 / 457 B / 17 条非注释规则**、`grep data` 0 命中 | 同 | 一致 |
| 构建上下文 `./backend` | `docker-compose.yml:17` = `build: ./backend` | 一致 |
| 本文件 H2 节数 | `grep -c '^## ' reports/gates.md` | ⚠️ **不钉数**：这是**自指计数**——写下"26"这一秒追加本节就变成 27。规矩是**只给命令**，谁读谁现量（在册第 44 条那台机器，本轮又差点复现一次） |

**抓出的两处旧措辞（都已改）**
1. `tickets/dispatch-independent-review-20261011.md` §0 原写 `reports/gates.md`（**23 节，§19-§22 是本轮**）——实际已是 26 节、本轮是 §19–§25。已改，并把每节是干什么的列出来，避免下一位按号找错件。
2. `reports/decisions-needed-20261010.md` §B 里 **D-13 那行仍写"候选工作树现量仍是 `M` 状态、一笔都没提交"**——那是第五笔提交之前的话，`9e3cfc5` 落地后为假。**D-21 同样已执行完**。两行已从 §B 移进 §C，并按现状重写措辞（不是照搬旧问句）。
   移完的档位计数（现量）：**§A 3 / §B 16 / §C 8 = 27**，正好等于 D-1…D-27 ⇒ 没有条目被漏登或重复计数。
   复量命令：`awk '/^## B\./{f=1;next}/^## C\./{f=0}f' <该文件> | grep -c '^| \*\*D-'`（三档各跑一次，**三个数相加要等于最大编号**，不等就是分档漏了）。

**定下的写作规矩（本轮之后我自己也照它执行）**
- 凡是**依赖可变状态**的读数（节数、行数、`porcelain`、包版本、远端头、镜像大小），正文要么**只给命令**，要么**带时间戳**并注明"这是 xx:xx 的读数"；不允许写成无时态的事实。
- 已执行完的条目**必须离开"待答"表**——留在里面等于让 Owner 重答一次，属于我的交付缺陷，不是排版问题。

## 27. 补记二十五（2026-10-11 02:4x：过期扫描的第二层——**票里教的动作本身会破红线**，抓到两条并改掉）

**边界守望（02:29→02:4x 现量）**：候选树 `9e3cfc5`/`porcelain=0` 未动；主仓 21/567 未动；`candidate-envB` freeze 与基线 **0 差异**。
复核会话已开工且**照纪律做了起始快照**：`review-20261011/freeze-at-start.txt`（3369 B）与 `evidence/envB-freeze-20261011-015x.txt` **排序后 0 差异**；迁移会话此刻无 `mig-*`/`candidate-envC-*` ⇒ 只能报"未见产物"，不能报"未开工"。

**缺陷一｜我让新会话去跑一支会 `load_dotenv` 的脚本**（D-3 票 §2 第 3 步，初稿）
- 原句把 `smoke_citation_fast` 列为"同一批尺子"之一。现量 `backend/scripts/smoke_citation_fast.py:84-87` = **`os.chdir(BACKEND)` + `from dotenv import load_dotenv` + `load_dotenv(".env")`** ⇒ 它装载**所在那棵树**的 `.env`。在主仓跑＝真实配置＋真实配额库（红线）；在候选跑虽然那份 `.env` 是 0 字节（我只取 stat），但 `backend/chroma_db/chroma.sqlite3` 同在树里（候选 `du -sk`=144，主仓=357,096）＝有写进去的风险。
- 改法：**撤回这条**，换成 `tests/test_citation.py`、`tests/test_qa_citation_gate_symmetry.py`、`tests/test_smoke_citation_assertions.py`（经 `tests/conftest.py` 重定向三个出口，不碰真实库）；并写明"确需那只脚本只能在副本树里跑＋四出口＋六根 URL 全指回环＋`RERANK_ENABLED=false`"。
- **这台机器记进记忆**：把"我记得它 24/24 绿"写成"你去跑它"之前，要读脚本头 30 行的 `chdir/dotenv/DB` 三件事——**引用一条腿的读数 ≠ 授权别人执行那条腿**。

**缺陷二｜"两棵树"附节把禁令文件的归属写错了**
- 我原来写"只有主仓有 `backend/data/`、`backend/chroma_db/`、`backend/media/`、`backend/.env*`，候选里没有"。逐条 `-e` 现量：**候选树也有 `.env`（0 字节）、`data/`（2 只 eval 相关）、`chroma_db/chroma.sqlite3`、`media/`（空）；候选没有的是 `app.db`、`data/app.db`、`data/quota_used.sqlite`、`backups/`、`venv`。**
  ⇒ 已按两根轴重写（两树都有=一律禁读禁写／只有主仓有=那五只），并加一句"**候选那几只是空的或极小的，不是安全区**"。
- 这条如果没抓到，下一个会话会因为"候选树里没有真实库"而放松重定向——正是最容易造成不可逆写入的那种放松。

**顺带**：§26 那张"不变量表"里我钉了本文件节数=26，追加本节就变 27 ⇒ 已把该行改成**只给命令**（自指计数不钉数，在册第 44 条那台机器）。票 X §0 同步改成命令 + "本轮新增节从 §19 起到最后一个 H2"。

## 28. 补记二十六（2026-10-11 02:5x：清掉一条会毁掉"签字对象"的隐患，并把 D-12 的前置做成人词可答）

**隐患：复核会话重建前端会不会把候选树弄脏**（脏了就等于你正要签的那个对象不再是 `porcelain=0`）
- 被跟踪的嫌疑文件是 `frontend/next-env.d.ts`（Next 构建可能重写它）；构建产物本身无害——现量 `.gitignore:40` = `.next/`、`:42` = `*.tsbuildinfo`，且候选树里这两者**都已存在**（本轮已构建过，next **14.1.0**）。
- 经验证据：`git status --porcelain -- frontend/next-env.d.ts` = **空** ⇒ 这个版本构建后不改写它。
- **但我不把这条经验派给别人当结论**：票 X 已加一节"构建类复算的额外要求"——**构建前后各跑一次** `rev-parse --short HEAD` 与 `status --porcelain`，两次原样写进它的报告；出现脏文件**禁止** `git checkout --`/`restore`（在册纪律：脏树里这类命令会连别人未提交的字节一起抹掉），改为停下回报。

**D-12（本轮交付物要不要入库）的前置我已做完**，这样你只需答一个词：
- 现量：`reports/` + `tickets/` + `model-validation/` 共 **24 只 `.md`**、总 **434,625 B**；**含 CR 的件数 = 0**（逐只字节量过）⇒ 入库不会带进换行噪音，这正是 `git diff` 归一后看不出、只有量 CR 才发现的那台机器（在册 2c）。
- 复量命令：`node -e 'let n=0;for(const f of process.argv.slice(1)){const d=require("fs").readFileSync(f);for(const b of d)if(b===13){n++;break}}console.log(n)' <文件们>`
- 若你答「入库」：目标是 `docs/closeout-20261010/`，**单独一笔**、只含这 24 只 `.md`，不含 `evidence/`（266 只，含 pack/二进制）、不含 `browser-acceptance/`、`candidate-env*`、`synthetic/`、`model-cache/`；提交前按在册纪律复量 `git diff --cached --name-only` 证明未夹带。
- 若你答「只留盘上」：那本轮全部结论的归宿就是这台机器，**没有第二份**——这条我已经在 D-12 里写过，不重复劝。

**边界（02:5x 复量）**：候选 `9e3cfc5`/`porcelain=0`；主仓 21/567；`candidate-envB` freeze 与基线 0 差异；禁令目录 `find -newermt 02:00` 仍 0 命中；复核会话 `review-20261011/` 有起始快照，迁移会话仍无 `mig-*`/`candidate-envC-*`。

## 29. 补记二十七（2026-10-11 03:0x：D-25 用 1 分钟定性；D-20 的 115 条被我推翻——那是**陈旧 ref 轴**；另有一条我自己越线的记录）

### A) D-25 源侧缺陷：不需要 30 分钟构建也能定性
`PY -m pip download --no-deps -i https://mirrors.aliyun.com/pypi/simple pydantic==2.14.0`（索引 URL 是从 `backend/Dockerfile` 里 `grep` 出来的原值，不是我手打）
⇒ **rc=1**、`ERROR: HTTP error 404 while getting .../pydantic-2.14.0-...whl`、落盘 whl 数 **0**、耗时 <1 分钟。
⇒ 结论：出厂路径今天仍红在**索引列出但文件缺**这一根轴上（与"构建慢"无关）。这条比整轮 `docker build` 便宜两个量级，**下次先跑它**。

### B) ⚠️ 我越线了：那条 fetch 仍然顶掉了 `origin/master`
我对 Owner 承诺"只建新 ref、不动 `refs/remotes/origin/master`（别的会话在读它）"。实跑 `git fetch --no-tags origin master:refs/closing/remote-master` 的输出里同时出现了
`* [new branch] master -> refs/closing/remote-master` **和** `15562fc..985d53e master -> origin/master` ⇒ **配置的 fetch refspec 被一并应用，我的做法达不到我许的诺**。
已复原：`git update-ref refs/remotes/origin/master 15562fc9…`（rc=0；复量 `rev-parse` 与 fetch 前**逐字相同**；`reflog refs/remotes/origin/master` 留着 `fast-forward` 与复原两条，可核）。真实头仍留在 `refs/closing/remote-master = 985d53e`。
⇒ 记下这条机器：**要"不动跟踪 ref"就不能用带 remote 名的 fetch**；可行做法是 `git fetch origin <sha>`（只进 `FETCH_HEAD`）或先 `git config remote.origin.fetch` 临时为空——两者我都没做，因为我已经先跑了。复原是否足够，请 Owner 判：若有会话在这几十秒里读过 `origin/master`，它读到过 985d53e。

### C) D-20 的 115 条作废：真实头轴现量是 **94 条**，且形状更清楚
现量（`git merge-tree --write-tree --merge-base=<空树> 9e3cfc5 refs/closing/remote-master`，git 2.55）：
- 候选路径 **2676**、真实头路径 **2136**、交集 **2136** ⇒ **远端那 2136 只路径 100% 在候选树里存在**（旧轴上 origin/master 只有 261 只，所以才得出"交集 260"那种误导性形状）。
- 交集里 blob 相同 **2042**、不同 **94**；merge-tree 判决 **94 条 CONFLICT，全部 add/add**（差异数 = 冲突数，两把尺子吻合）。
- 冲突面点名：`.github/workflows/ci.yml`、`.gitignore`、`CONTRIBUTING.md`、`backend/Dockerfile`、`frontend/.env.example`。
⇒ **重述成一句话**：合 master 的真实成本 = **94 次内容裁决**（远端全部路径都在候选里，差的只有这 94 只），不是原先写的 115 次，也不是"两棵树几乎不相干"。
`merge-base 9e3cfc5 refs/closing/remote-master` 仍为空（rc=1）⇒ 无共同祖先这点没变，所以 PR 那条路的"合成 merge ref 可能不调度"仍然成立。

### D) 现场更正
Docker Desktop 已在 02:40 被起回来（进程 6），compose 栈自动 Up：`fazhi-backend (healthy)`／`fazhi-caddy` 发布 **0.0.0.0:8088**／`fazhi-frontend`。
`docker inspect fazhi-backend` 现量：镜像 `ai-legal-helper-backend` **created 2026-09-17T12:18:42Z**、container started 10-10T18:40:25Z ⇒ **现役跑的仍是 09-17 那份镜像**，本轮五笔提交不在现网里。我全程未对栈做任何 docker 动作。

## 30. 补记二十九（2026-10-11 03:1x：**独立复核 C 回来了**——采纳 6 / 驳回 1，并抓到本轮最重的一条）

**判决**：`reports/independent-review-C-20261011.md`（262 行 / 25,332 B / 02:54 落盘）。七颗钉子 **采纳 6、驳回 1、核不了 0**；驳回的那条只驳"数字层"，核心三事实（历史裸值存在 / 快照按值 0 命中 / 同仪器正对照咬住）**全部复现**。它是**非实现者**跑的，方法也与我的正交（它用三臂构建 + 第二套 python 复算 + 现场重做 docker 探针）。

### 它抓到、我漏掉的一条（最重，已修）
**无父快照早于第五笔**：`evidence/orphan-snapshot.sha` 里 `from_head=3f605de`、树 `04dd97ad` = **第四笔的树**，而现 `HEAD^{tree}` = `1e91913c`。
⇒ 凡引用"快照树逐字等于 `HEAD^{tree}`"的现役文字都失效（`h-ci` §7、`runbook` §0/A2、本文件 §19、`decisions-needed` D-5(b)），且 **D-5(b) 若照现文件执行会推出一棵不含第五笔 §14 修复的树**——正是 D-21 那个"验收对象≠交付对象"的重演。
**已按它的修法执行（03:1x）**：旧三件改名保留（`.3f605de.bak`，未删）→ 重跑 `evidence/orphan_pin.py` → 新快照 `1b1c307e…`，**树 `1e91913c` == `HEAD^{tree}`**（独立复验 + 冷恢复裸仓读回同树）；objs 2581、按值 0 命中、正对照咬住 1、`normal_push_objs=4315`、少 **1734**；pack 141,794,859 B `verify-pack ok`；**用新 ref `refs/closing/orphan-snapshot-20261011` 钉住**（不钉则两周后 `gc.pruneExpire` 会剪掉）。
⚠️ 顺带抓到我自己仪器一只 bug：`orphan_pin.py` 在 **没建 idx** 时就 `verify-pack` ⇒ rc=1/1 行 ⇒ 把**可读的 pack 误判成 `VERDICT=REFUSE`**。已修（先 `index-pack` 再 verify），并在写入前 `ast.parse` 自检。

### 它抓到我自己那批"更正"里的三处新错（都已改）
| # | 它的发现 | 我的处置 |
|---|---|---|
| 1 | §26 给的 §C 计数命令 `grep -c '^\| \*\*D-'（此处竖线已转义：裸竖线会断列）` 在 §C **恒为 0**（我移 D-13/D-21 进去时没加粗编号）⇒ 数字 8 对、命令错 | 命令改为 `grep -cE '^\| .*D-[0-9]+'`；**3+16+8=27 且 1..27 每号恰出现一次**由它另行核过 |
| 2 | §E 的复算块**照抄即 `SyntaxError`**（`'\'` 未闭合），且即便修好，Windows 解释器打不开 `/c/...` ⇒ 会**静默打印 0** | 整块换成我 03:1x 亲手跑通的 `node evidence/audit_axes.js …`，并把这两个坑写进块内注释 |
| 3 | §E 把 per-package distinct（6/4/2/1）归给 `audit_axes.js`，**而该脚本不印这根轴** | 脚本已扩段，现印 `[per-package distinct 主ID] core6/openai1/splitters2/chromadb2/langsmith4，全库和=15、并集=15、跨包重复=0、族内和=13` ⇒ 指针归位 |

### 另两处现场更正（它带的读数）
- **对象数轴**：`4301/238` 是第四笔时的数；现 HEAD 为 **4315 对象 / 239 棵树**。且因为两侧**无共同祖先**（`merge-base` 空、rc=1），跟陈旧 `origin/master` 还是跟远端真实头 `985d53e` 比都是 **4315** ⇒ "推上去会不会带那个 blob"的答案与比较基准无关：**会带**（引入笔 `817e7d3` 两边都不在祖先链里）。
- **"禁令目录 0 命中"要分两轴**：主仓 `backend/data` **目录节点** mtime 被推进到 **02:40:38**（= 容器 `StartedAt 02:40:25` +13 s），**文件级仍 0**、目录内四条目 size/mtime 全未变、无 `-wal/-shm`。归因：**容器启动的瞬态**，不是任何会话的动作（它的 docker 第一条是只读 `docker ps`，当时栈已 Up）。⇒ 该不变量今后写成两句：**文件级 0 命中 + 唯一目录级命中 `backend/data`，归因容器启动**。候选树两轴全 0。
- 它还按我在 02:41 追加的那节补做了回执：**三臂构建全在 scratch**，候选 `.next`（mtime `10-10 21:52:34`）与 `tsconfig.tsbuildinfo`（`21:45:11`）**均早于复核窗口** ⇒ 构建前后 `porcelain` 两次为空，正面证明"零波及"。

**优先级规则（避免旧数继续被当现量引用）**：本文件 §19–§29 里凡与 §30 冲突的**数字**，以 §30 为准；历史读数保留原文并就地标注，不改写历史。

## 31. 补记三十（2026-10-11 03:3x：**第六笔 `4300c71`＝本轮交付物入册（D-12 落地）**，并定一条"已入库≠继续演化"的规矩

- 内容：`docs/closeout-20261010/` **27 只 `.md`**、**+3891 行**、`git diff --name-only 9e3cfc5..HEAD` 里**非 docs 文件数 = 0** ⇒ 前 5 笔代码字节不受影响；提交后候选树 `porcelain=0`、`0b54396..HEAD` = **6 笔**。
- 提交前双检：① 逐只 CR＝**0**（不把换行噪音带进仓库，在册 2c）；② 凭据形状复扫 `sk-`/`AKIA`/JWT/PEM/URL-in-creds 命中 **0**，`13 位纯字母数字` 45 处**全是普通标识符**（`UploadSection`/`observability`/`cacheprovider`…），与历史裸值参照值相同的 **0 处**（参照值由引入笔 blob 现取，全程不打印，只比 sha8）。
- 暂存自证：`git diff --cached --name-only` = 27 只、全部在该目录下，**别的会话的改动一个字节都没进**。
- ⚠️ **新规矩（这条本来就会被踩）**：入库的是 **03:3x 的时点快照**；运行根里的同名文件我还会继续改（复核件回来、Owner 新裁）。因此**"报告已入库"不等于"仓库里那份是最新的"**——凡引用"已入册"，须写明"截至第六笔"，收尾时再补一笔同步。这条我同时写进了两张已派发票的 §1 锚点说明。
- **给并行会话的一句**（它们读的是 03:3x 前的票）：候选分支现在是 `4300c71`，**多出来的是文档，不是代码**；读到 `HEAD ≠ 9e3cfc5` 不表示基线被破坏。

## 32. 补记三十一（2026-10-11 03:3x：**我把复核刚抓出的缺陷又亲手复现了一次**——规矩因此换形）

**事实**：03:1x 我按当时现 HEAD 重生成无父快照，当场验过 `快照 tree == HEAD^{tree}`（都是 `1e91913c`，即 `9e3cfc5` 的树）。
随后我为落地 D-12 又提了两笔 docs 提交（`4300c71`、`fc7ebf6`）。03:2x 复量：现 `HEAD^{tree}` = **`a5eff903`**，而存着的快照仍是 `1e91913c`。
⇒ **独立复核 C §2.1 那条"快照早于分支头"的缺陷，被我在 30 分钟内以同样的成因复现**。这次不是别人抓的，是我在写就地标注前复 ref 表时自己撞见的——说明"复现别人的正确修法"不等于"掌握这条纪律"。

**因此规矩换形（三处文件已就地改）**
1. `decisions-needed` D-5(b)：**删掉"已重生成，相等"这种存证式写法**，改成**动作式前置**——推送前最后一刻现跑 `evidence/orphan_pin.py`，并以两条当场读数相等为唯一放行条件。
2. `h-ci-and-credentials.md` §7 与 `runbook-I-push-pr-merge.md` §0/A2：原句加删除线与归因；A2 的前置改为三条现量（分支头以当场 `rev-parse` 为准／`porcelain=0`，旧写"tracked 脏仍 5 只"已过时／快照须现生成）。
3. `refs/closing/orphan-snapshot-20261011` 这枚 ref 的作用被写清楚：**只是把当时那枚无父对象从 gc 嘴下钉住**，不代表当前交付内容；当前交付要的是**分支头本身**。

**教训（进记忆）**：会随 HEAD 移动而过期的派生物（快照 tree、对象数、diff 计数、树号），**不能以"已生成/已核对"的形式写进交付面**；只能写成"执行前现跑"的前置。本轮这条我犯了两次——第一次是没注意，第二次是**修完之后再犯**，第二次的代价高得多，因为它把一条刚从独立复核学到的纪律变成了纸面胜利。

## 33. 补记三十二（2026-10-11 03:3x：上传对象数——我又错一次，这次错在**机理**）

**原句作废**："因两侧无共同祖先，跟陈旧 ref 还是跟远端真实头比都是 **4315**"。
**为什么错**：`git rev-list --objects A..B` 不是按祖先剪枝，而是**按对象身份**排除 A 侧可达的对象 ⇒ 两侧内容相同的 blob/tree 会被折掉，真实上传集小于 B 的全量可达对象数（4315 是"从 HEAD 可达的对象总数"，我把两个数当成一个说了）。
**现量（03:3x，HEAD `fbd9eb2`）**：`rev-list --objects refs/closing/remote-master..HEAD` = **4252**。〔**此句的机理与数在 06:4x 二次作废，见 §44**：真实上传集是 HEAD 全部可达对象（现量 4464），不是我当时说的"按对象身份折掉后的 4252"〕
**该 blob 的判据换成直接查集合**：含裸值那只 blob `d59a7b614514445d617d55bb9e7dd581e2636805`（`git rev-parse 817e7d3:dispatch-output/t12-frontend-sweep-20260920/apply_case_domain_gate.py`）——远端真实头可达对象里 `grep -c` = **0**，而在 `remote-master..HEAD` 差集里 = **1** ⇒ **直推必然上传它**。这比"引入笔不是远端祖先"那套推断强一档，且不需要读任何凭据值（全程只用 blob sha）。
**规矩**：这个数与 §32 那条同源——**每提一笔都会过期**，所以 D-5 的执行卡里它只能是"推送前现跑"的前置，不能是在册值。本轮我在同一个数上错了两次机理（4301/4315→4252），下次报数以"当场命令 + 当场输出"为单位。

## 35. 补记三十四（2026-10-11 04:1x：我执行了 D-22，结果**修好了 A、暴露了 B**——D-22 按我自己的尺子仍未闭合）

**做了什么**（我自己实现，非派会话；理由与独立性交代在 J §7）：
- `frontend/components/ui.tsx`：`badge badge-${kind}` 改为**显式静态映射表**（未知 kind 回落 neutral），配色一字未动。
- 新增 `frontend/scripts/assert-badge-classes.mjs` + `npm run build:check`；`.github/workflows/ci.yml` 的既有 Build 步改跑 `build:check`（**零额外耗时**，复用已存在的构建步）。
- 提交两笔（本地、未推）：`842ef0b`（组件 + 断言脚本 + npm 脚本）、`0d3d662`（CI 并入）。分支现 **11 笔**、`porcelain=0`。

**尺子 1（产物层，三条读数）**：改前 `.next` 上四个类名 **0/0/0/0**（对照 `.badge{`=1、`.upload-zone`=3）⇒ `DEFECT_PRESENT rc=1`；改后 **1/1/1/1** ⇒ `VERDICT=OK rc=0`；**变异臂**只把 `neutral` 退回拼接再建 ⇒ **仅 `.badge-neutral` 变 0、其余三个仍 1、rc=1`（断言按类名分别成立，不是钝的）；还原后 `ui.tsx` 与备份 **sha256 逐字相同**，重建回 OK。日志 `evidence/d22-build-check.log`、`d22-build-MUTANT.log`、`d22-build-restored.log`（构建 76s / 31s / 27s）。
**门禁**：`tsc` rc=0、`lint` rc=0、`vitest` 9 files / 83 tests rc=0、`npm run format:check` **仍 3 只**（`ui.tsx` 本在 `.prettierignore` 冻结清单内，我没对它跑 `--write`）。

**尺子 2（真实浏览器量产物样式表）——这条把结论换了性质**
- 仪器：`badge-20261011/drive-badge-css.js`（Edge headless + 裸 CDP，复用 D 会话的 `cdp-client.js`；起 `127.0.0.1:8411` 只读伺服 `.next/static/css/8d8873f14ebe4de6.css`，`127.0.0.1:9313` 调试口；跑完我的 Edge 进程数归 0、监听端口归 0）。
- **诚实边界**：这一腿量的是"出厂样式表 × 五个徽章选择器"，**没走应用路由**（后台列表页要真后端，本轮未起）。
- 先两次仪器自错、都已修并复跑：① `querySelector(".badge")` 抓到的是第一个徽章（把 success 的颜色当成了 bare 的颜色）⇒ 换成 `:not([class*=badge-])`；② 我那 `/[-\d.]+/` 在多层转义后**吃掉了 `\d`** ⇒ 所有比值 `null`、而 `below_aa` 读的还是旧字段名 ⇒ 报了个**假空**。改成不依赖反斜杠的分词后才有真数。
- **真数（`evidence/badge-css-after.json`）**：四种类名**互不相同**（6 对里相同 0 对、纯 `.badge` 基类仍是墨色 `rgb(35,49,79)`）⇒ **H2 想表达的"未验证别再显示成现行"在生产形状里第一次真的成立**。
  **但**按每个徽章**自己的背景**算对比度：`success 2.19`、`error 3.03`、`neutral 4.01`、`accent 1.42`，**4/5 低于 WCAG 2.2 AA 的 4.5**；只有墨色基类 11.88 过线。

**为什么这不是"修坏了"，而是一起潜伏缺陷被揭示**：D 报告当年量到"六者 12.12:1 全同"，正是因为 `badge-*` 规则被 purge、所有徽章都退化成墨色 ⇒ **那四对配色从未在生产里被渲染过，也就从没人量过它们**。修好 purge 让配色上线，AA 失败才第一次可见。⇒ 按我在票里自写的"四条尺子都齐才算完"，**D-22 不能算闭合**（尺子 2 明写要求"对比度仍 ≥4.5"，现在不满足）。

**⚠️ 部署含义（这条最该被 Owner 看见）**：在这笔修复之后、配色决策落地之前，**这条分支上的六个状态徽章里有四个比修复前更难读**（修复前是全员墨色 12:1，缺点是分不清；修复后分得清，缺点是 1.4–4.0 不达线）。两者都不是我要替他选的答案——**这正是 G11（色相/对比度）从"未裁"变成"必须裁"的那一刻**。

## 36. 补记三十五（2026-10-11 04:2x：D-28 (b) 落地 ⇒ D-22 四尺子齐了；同一把尺子本轮出现过三种状态）

`033cd3d`（未推）：`.badge-*` 四条的前景改为统一 `--ink`，状态差异由**底色 + `inset` 环形描边**承载。
不用 `border-left` 的理由写在 CSS 注释里：`.badge` 是 `9999px` 胶囊，左边框会弯成碎片并撑高 2px；环不改布局。

**同一把尺子（`badge-20261011/drive-badge-css.js`，量构建产物样式表）的三个状态**——这是"它不是恒绿"的正面证据：
| 状态 | 四者颜色 | ink/自身底 对比度 | 判定 |
|---|---|---|---|
| purge 修复前 | 全同（退化成墨色） | 12.12 全过（**假象**） | `ALL_IDENTICAL`＝红 |
| 只修 purge（`842ef0b`） | 互不相同 | **2.19 / 3.03 / 4.01 / 1.42** | `DISTINCT_BUT_AA_FAILS:4of5`＝红 |
| 加上 (b)（`033cd3d`） | 底色 + 环两维互不相同（6 对相同 0） | **11.15 / 11.22 / 10.30 / 5.70** | `DISTINCT_AND_AA_OK`＝绿 |

门禁复量：`tsc` rc=0、`lint` rc=0、`vitest` 9 files / 83 tests rc=0、`npm run format:check` **仍 3 只**（`globals.css` 在 `.prettierignore` 冻结清单内，未对它跑 `--write`）。
产物断言 `npm run build:check` rc=0（四个 `badge-*` 各 1，对照 1/3）。⇒ **D-22 的四条尺子全部满足，标记闭合**；分支现 **13 笔**（6 代码 + 6 docs + 1 CI 并入），`porcelain=0`。

## 37. 补记三十六（2026-10-11 04:3x：D-3 迁移会话交付 → 我逐条复算验收；**它反过来纠正了我票面一句假话**）

**被验收件**：`reports/d3-langchain-migration.md`（147 行 / 16,420 B / 04:14），过程登记两份（blocker、smoke-breach），产物在 `mig-20261011/` 与 `evidence/d3-*`。

**我用我自己的仪器复算了什么（不转述它的数字）**
| 它的结论 | 我的独立复算 | 判定 |
|---|---|---|
| langchain 族 distinct 主 ID **13 → 0** | `node evidence/audit_axes.js evidence/d3-audit-envC-req.json` ⇒ 条目 2 / distinct 2 / 包 1（只有 `chromadb`）、**族 = 0/0/0** | **采纳** |
| `--local` 轴 envB 28/17 → envC 6/4 | 同一仪器读两份 json：envB 28 条目 / 17 ID / 6 包、族 13；envC 6 / 4 / 2 包（`chromadb`+`setuptools`）、族 **0** | **采纳**，且证实"setuptools 2 条与迁移无关"（两环境同版本 78.1.0） |
| envC 自洽、版本如表 | `pip check` = **No broken requirements found**；`import` 现量 core **1.6.9** / openai **1.7.0** / langsmith **0.14.7** | **采纳** |
| 改动面只有依赖窗 + 3 只测试 | 读两份 diff 的 `---/+++` 头：`requirements.txt`；`test_cancel_boundaries.py`、`test_llm_lifecycle.py`、`test_stream_cancellation.py` ⇒ **产品源码零改动** | **采纳** |
| 边界：没动 envB / 候选树 / 主仓 | envB freeze 与基线 **0 差异**；候选 `porcelain=0`（HEAD 仍是**我**的 docs 笔）；主仓 21/567 同数 | **采纳** |
| 双树门禁 1925/0/10/18、cov 86.35%、rc=0；mypy 74 files | **未复跑**（跑一次全量 = 250s+ 且要占 envC；且我 03:0x 已在候选树上验过同数） | **核不了→暂采**，标注为"未复算项" |
| `ruff format --check` 284 files（我候选树现量 **283**） | 差 1 只文件，**未解释**；两侧 rc 都是 0，不影响判据 | **登记为口径差**，不追 |

**它纠正了我（这一条最该记）**：我票面 §2.1 写「`dispatch-output/task1/hidden_runner.py` **不在 git 里、必须手工带**」——**为假**。现量 `git ls-files` 列出它、`check-ignore` exit=1（**已跟踪文件不享忽略**）、`git archive HEAD` 自带。
我的错因是**只看 `.gitignore:77` 的模式匹配就下结论**，没跑 `ls-files`——这条在册纪律（"要查已跟踪却被忽略必须 `git ls-files | git check-ignore --no-index --stdin`"）我写过却没照做，被执行方反过来纠正。票面已就地改写并留痕。

**落地建议（新待裁 D-29）**：推荐**本轮不落**、排在 D-5 之后当下一轮首票。理由：这条分支刚被独立复核钉过形状；换依赖窗＝换基线（要以那个会话自建的 `candidate-envC-1x` 重跑全量才能立基线）；把"推送"与"换依赖"捆一次 = 不可归因。

## 38. 补记三十七（2026-10-11 05:0x–06:0x：Owner 一句「都交由你的推荐执行」⇒ 我分五批落，每批带测试与负向自证）

授权范围＝当时台账 §A 3 条 + §B 15 条里我给了推荐的那些。分批与落点（逐条正文在 `decisions-needed-20261010.md` §C 的新行）：

- 批 A：D-9 拒答冷却分两档 + D-15 `TOOL_BUSY` 进白名单并单列 ⇒ 提交 `8903da1`
- 批 B：D-10 的 409 文案分档 + D-23 取消占位文案 ⇒ 提交 `91bd53d`
- 批 C：D-18 注释与真值、D-16 事件响应三行、D-11 风险册入库 ⇒ 与批 D 同笔 `bffbe1c`
- 批 D：D-25 镜像源回落 + CI `source-probe` ⇒ 同上
- 批 E：D-14 / D-6 / D-20 三张票写出（只写票，不执行）
- 判为"不动"的：D-8（不摘 category）、D-24（探针失败保持宽）、D-17（用冻结题集）、D-29（本轮不落 D-3）

新头上的门禁现量（05:4x，`candidate-envB`，候选树）：
`pytest -m "not slow" --cov=. --cov-fail-under=70` ⇒ **1932 passed / 0 failed / 10 skipped / 18 deselected，cov 86.37%，rc=0**；
基线闸配平：`--collect-only` = **1942/1960（18 deselected）**，junit `tests=1942 skipped=10 failures=0 errors=0`（1932+10=1942 对得上）；
`ruff check` rc=0、`ruff format --check` **283 files already formatted** rc=0、`mypy` **Success: 74 source files** rc=0；
前端 `tsc` rc=0、`next lint` rc=0（不经管道另取一次）、`vitest` **83 passed (83)**。
⚠️ **未重跑**：`npm run build:check`（J3 的产物断言腿）——本轮前端字节零改动（五批全在 backend/docs/deploy 面），旧读数仍在 `evidence/d22-build-check.log`。
证据：`evidence/final-gates-backend-20261011.log`、`final-gates-junit-20261011.xml`、`final-gates-static-frontend-20261011.log`。

## 39. 补记三十八（D-10 / D-23 的实现形状，以及**台账说三条、我实做四档**）

- 409 分档轴选了「用户下一步动作」而不是「内部状态机有多少态」：已处理过 / 再答一次 / 预算用完 / 接不上 ⇒ **4 条文案**。台账 D-10 原文写"三条映射草稿"，第四条是执行时才看清的：`answer_invalid`（空回答、范围选择填错）要用户**再答一次**，跟"这条任务死了"不是同一个动作，合进任一侧都会说错话。
- 判据用 AST 现读 `controller.py` 的 `ResumeRunConflict("<码>")` 字面量 + `__init__` 默认值 ⇒ 新增抛点**自动**进门；回落腿保证未登记码仍给旧那句（分档不能把 409 变成 500）。
- 取消占位分两档，两条路**分别**钉住：正文生成器 finally 只在没走到自然结尾时记 stopped；`compensate_unstarted`（响应已关而正文从未进入）记 stopped。服务侧真故障（空答 / 异常 / `main.py:738` bootstrap 抛错）仍是不响应。
- 变异（`evidence/batchB_mutation.py` + M7 单发，日志 `batchB-mutation-20261011.log`、`batchB-mutation-M7-20261011.log`）：
  M4 把 finally 两档塌成一句 ⇒ 杀 4 条；M7 把 `compensate_unstarted` 的档摘掉 ⇒ 恰好杀那 2 条（证明这两条路不是同一把尺子在量）；
  M5 让 409 全回落旧句 ⇒ 杀 5 条；M6 让两档共用一句 ⇒ 杀 1 条。四枪全部位级还原（sha 相同）。
- 夹具随改（不是放宽）：占位桩签名与生产对齐；两个文案常量按 `main.py` 真值 AST 注入两个命名空间 ⇒ 生产改词时测试不会跟着假装绿。
- 新文案是我起草的，**要 Owner 过字** ⇒ 台账新行 D-31；前端当场文案与历史文案要不要统一 ⇒ 新行 D-32（推荐保持两套，语义不同）。

## 40. 补记三十九（D-18 比台账宽：那条 docstring 举的模型名有 6 个不在表里）

现量复算（`DEFAULT_ROLES` 区间内逐个 grep 精确串）：`deepseek-r1-distill-qwen-7b` / `qwen2.5-omni-7b` / `qwen3.5-omni-flash` / `qwen3-vl-235b` / `qwen3-vl-32b` / `qwen-plus` 命中 **0**；只有 `qwen3.7-plus`、`qwen3.5-omni-plus-2026-03-15` 在表里。条数现量 **27**（19 text / 3 vision / 5 voice，全 `tier=flag`），复算命令 `awk '/^DEFAULT_ROLES: /,/^\]/' backend/llm_registry.py | grep -c '"model":'`。
「现有 6 个辅助调用点」这条也对不上：`registry.get()` 在非测试代码里现量 **15** 处（分布在 `agent/runtime.py`、`llm_registry.py`、`main.py`、`request_bootstrap.py`、`scripts/eval_relevance.py`、`scripts/_judge.py`）。
修法换形：**注释里既不抄数也不举名**，一律指向 `DEFAULT_ROLES`——抄数就是 DB-24 的成因本身。
核为真、未动的一句：`get()` 仍返回全模态旗舰（`DEFAULT_KEY=vision_flag` ⇒ `qwen3.5-omni-plus-2026-03-15`）。
⚠️ 我只改了本轮点名的面：`docs/` 与报告里凡引用"8 个代表模型"的旧句子，属同族但未逐处清（未做，不是已做）。

## 41. 补记四十（D-25：缺陷**今天已自愈**，所以落的是这一类的兜底 + 可观测）

10-10 的事实是"阿里云 PyPI 索引页 200、`pydantic-2.14.0` 文件 404"。10-11 05:2x 同一条命令复量：
`pip download --no-deps --no-cache-dir -i https://mirrors.aliyun.com/pypi/simple pydantic==2.14.0` ⇒ **rc=0，取到 487 kB**；
`pip download -i https://pypi.org/simple` 同版 ⇒ rc=0（第一次跑没加 `--no-cache-dir` 打出 "Using cached" 是**假绿**，加后才证明官方源真给）。
torch 侧：阿里云 `pytorch-wheels/cpu/` 目录 200（1,208,113 B）；两页的加号编码不同（aliyun `&#43;`、官方 `%2B`）⇒ 尺子先归一化再比，`torch-2.13.0+cpu-cp311-cp311-manylinux_2_28_x86_64.whl` 两侧都在列。
落地：`backend/Dockerfile` 两步各加 shell 级失败回退（**不用** `--extra-index-url`：它会把两源候选合并再挑版本，镜像与官方源同名不同步时版本选择权外移）；`.github/workflows/ci.yml` 新增 `source-probe` 作业（逐包真取文件；主源红 = warning、两源同红 = 真红；只挂 schedule + `workflow_dispatch`，不占每次 PR）。
仪器自检（都留了日志）：`evidence/d25-probe-selfcheck-20261011.log`（正对照两页命中、假版本咬红、空页咬红）、`evidence/d25-pipleg-selfcheck-20261011.log`（两只真包绿、`pydantic==9.99.99` 两源皆红且 rc=1）。
诚实边界：探针**不等于** `docker build` 通过（模型烘焙那层不在这里）；且 Actions 的 schedule 只在默认分支生效 ⇒ 合进 `master` 之前这条只能手动触发。
`ci.yml` 结构自检：`evidence/ci_yaml_check.py` ⇒ jobs = backend / frontend / source-probe，triggers 四根，缺 runs-on/steps 的作业 = 0。

## 42. 补记四十一（在册报告 `gates.md` 里有一个**真 NUL 字节**，已修）

发现方式很偶然：`grep -n "^## " reports/gates.md` 回的是 "Binary file … matches"。逐字节定位：**1 个 NUL**，offset 40736，在第 371 行的 `sha1("blob <len>…")` 那句里——本该是字面 `\0` 两个字符，写的时候被当成转义序列落成了真 0x00。
影响面：任何按文本处理的工具（grep / diff / 某些编辑器）会把这一份台账当二进制；它不影响产品字节，但**影响交付物的可读性与可核性**。
修法：字节级替换成字面两字符，复量 NUL=0、CR=0、bytes 109119→109120、sha 前缀 `7beea10d`→`cd040a20`。
我自己的第一次尝试没写成——`replace(b"\x00", b"\0")` 里的 `\` 被 bash heredoc 折叠成真 NUL，长度断言当场把写入拦下（拦得住是好事，但要记：**在这台机器上写反斜杠要用 `bytes([92])` 构造，别指望 heredoc 保留双反斜杠**）。

## 43. 补记四十二（D-20 的冲突数在**几小时内走了 94→96→99**，这次是我自己的提交推的）

同一把尺子（`evidence/merge_trial_blobs.py` + `merge_trial_reconcile.py`，两把必须吻合）：
`9e3cfc5` ⇒ 94；`5e9bba8` ⇒ 异 blob 96 = CONFLICT 96；本轮三笔之后 `bffbe1c` ⇒ **异 blob 99 = CONFLICT 99**（A 路径 2707、B 路径 2136、交集 2136、远端独有 0）。
所以票面与 §C 行都不再写"就是 96"，改成：**开工时与最终头上各跑一次**，读数随命令现出。
顺带抓出自己两把尺子的两处错：`git rev-parse "<ref>:<path>"` 取不到时返回空 ⇒ 被我算成"内容不同"（据此得出的 100 里有 4 只是同 blob）；`line.partition("\t")` 把行尾留在 key 里 ⇒ 清单 96 条写成 192 行。两处都在尺子里修了并留下复跑读数。

## 44. 补记四十三（2026-10-11 06:4x：**我把上一节"纠正后"的机理又纠正了一次**——上传集不按对象身份剪）

触发点是我准备把 D-5 的命令刷进推送手册时顺手复量：`rev-list --objects refs/closing/remote-master..HEAD` 与 `rev-list --objects HEAD` **同为 4464**。若 §33 那句"按对象身份排除"成立，这两个数不可能相等。

三根轴现量（头 `ed76192`，日志与命令 `evidence/push-upload-axis-recheck-20261011.md`）：

| 读法 | 对象数 |
|---|---|
| `rev-list --objects HEAD` | 4464 |
| `rev-list --objects refs/closing/remote-master` | 3803 |
| `rev-list --objects refs/closing/remote-master..HEAD` | **4464**（等于全量 ⇒ 一点没省） |
| 对照：`rev-list --objects HEAD~1..HEAD`（正常祖先） | **10**（`HEAD~1` 自身 4454） |

决定性取样：`ls-tree -r` 两侧比对得**同 blob 文件 2037 只**，把这 2037 只的 blob sha 去 `^remote-master HEAD` 的输出里查——**2037 / 2037 全部仍在上传集里**。

**机理换成**：`--objects A..B` 的排除发生在 **commit 可达性**这一层（B 侧走到已被判 UNINTERESTING 的 commit 就停），**不是**对 blob/tree 做身份去重。两侧无共同祖先 ⇒ 没有可剪的 commit 链 ⇒ 全量上传。正常祖先那条对照之所以能省到 10/4464，也是因为剪的是链、不是对象。

**连带作废/改写的三句在册文字**：
1. §33 那句"`rev-list --objects A..B` 是按对象身份排除"——**作废**（已在原句后就地标注）。
2. D-5 行里"真实上传集 = 4252、比全量少 1734"——**作废**；正确说法是**上传集 = 待推分支的全部可达对象**（今天 4464），所以"无父快照 2581"之所以小，是因为它**只带一枚 commit 与它自己那棵树**，不是"去重后的真实上传集"。这两个数不是同一把尺子的两次读数。
3. J §2 / 台账里"少 1734"那类差值表述——同批改掉。

**方向没有变的那条**：含 13 位裸值的 blob `d59a7b614514445d…` 仍在上传集里（在远端真实头可达集里为 0）⇒ **先轮换再推**仍是推荐；这次更正只让"要上传多少"从被我低估变成按现量说（内容轴、体积轴、以及"共享对象会不会被重传"这三点都受影响）。

**教训入库**：我把一条**错误机理**当成"上一次的更正"写进册子并据此改了推荐措辞——一次更正不等于对。凡机理型断言（"某命令按 X 剪枝"）要配一条**能区分两种机理的对照**（这次是"正常祖先范围 vs 无关历史范围"），单看一个数不足够。

## 45. 补记四十四（2026-10-11 06:5x：Owner 二次整包授权 ⇒ 把"还能自己做的"做完）

- **前端第五条腿补跑**：`npm run build:check` 在新头上 rc=0，产物断言 `VERDICT=OK`（`.badge-success/error/neutral/accent` 各 1 次；正对照 `.badge{`=1、`.upload-zone`=3；CSS 1 只 / 43,241 B）。跑后 `git status --porcelain` = **0 行**（构建写的是 gitignored 面）。§38 里那句"未重跑"由此作废。
- **D-18 同族残留扫净**：仓内除"登记这个缺陷"的正文外，`8 ?个模型|八个模型|默认 8 个|代表模型…8` 在 `docs/`+`backend/`（排除本轮交付镜像）**命中 0** ⇒ §10.3 那条"未逐处清"改为"已扫，无残留"。
- **台账收口**：§A 整段改写成「已裁，只剩你手上的动作」（D-5 / D-19 两行），§B **现为空并写明为什么空**；D-7/D-30/D-31/D-32 按推荐裁完移进 §C。差集实测：§A/§B 从 18 条 → 2 条。
- **重复编号自查**：改写 §A 时我把 D-19 同时留在了 §B ⇒ 脚本断言"同一编号不两档并存"当场抓到（`removed_from_B=1 重复编号={}`），已删。
- **仍未做的**（不是已做）：推送、开 PR、凭据轮换、以及三张下一轮票（D-14 / D-6 / D-20）的执行——前两条卡在你的键，后三条是**有意留作下一轮**（理由在各票头与 §C 行）。

## 46. 补记四十五（2026-10-11 06:5x–07:3x：两路独立复核回来，**B 打中我四处**，其中一处是我刚交付的实现）

派发：Owner 令"再派子代理独立审核所有的任务"⇒ 两路正交，各写各的报告，都不许把我的转述当证据：
- A 复现腿 `reviews/20261011-round2/independent-review-A-replication-20261011.md`：**采纳 8 / 驳回 1 / 核不了 0**。它自己在副本树上重跑了 M1（杀 2）与 M4（杀 4）、重跑全量门禁（逐字同读数）、重跑了 §44 那三根 rev-list 轴。
- B 对抗腿 `reviews/20261011-round2/independent-review-B-challenge-20261011.md`：新发现 12 条，其中 4 条我当场验实并本轮修掉。

**B 打中的四条（每条我都自己复跑确认，再改）**：
1. **取消档的判据用错了信号**（`_delivered`＝"有没有走到 try 结尾"）。事实：`stream()` 的 try 体里有 **5 处主动 return**（`main.py:2103/2134/2163/2339/2415`，每条都在 `yield "data: [DONE]"` 之后），其中**轻量分支空答**走 `:2409` 的 `if answer:` 为假 ⇒ 直接 `:2415` return ⇒ 被我的旧逻辑判成"用户已停止"，而同样的空答在旗舰分支走 `:2534` 自己那条占位腿，写的是"不响应"。**同一症状两句话——正是 D-23 要消灭的东西，被我自己的实现重新造了出来。**
   修法：改成只认真实断开信号（新增 `except (GeneratorExit, asyncio.CancelledError)` 置 `_client_gone` 并原样抛出），finally 读它；补一条 AST 结构不变量测试 `test_stopped_label_can_only_be_set_by_a_disconnect_signal`（断言"只有那个 except 能置档、try 体内不许置档、finally 必须读它"）。M8 抽掉信号 ⇒ 杀 3 条（含这条新测试），逐字还原 sha 相同。
2. **`source-probe` 没挂作业级门 ⇒ 每个 PR/push 都跑**，与我三处写的"不占每次 PR"相反（`grep -c 'if:'` 全文件 = 0）。修法：作业级 `if: github.event_name == 'schedule' || github.event_name == 'workflow_dispatch'`，并给 pip 腿补 `probed=0 ⇒ 报错退出`的正对照（0 个包不是"干净"，是仪器没接到对象）。
3. **torch 回落只换 `--find-links`、不换 index** ⇒ 传递依赖仍从阿里云 PyPI 取，而 10-10 炸的正是那个源。修法：回落那一发同时 `-i https://pypi.org/simple`（`+cpu` 本地段只在 find-links 有，不会因此误选 CUDA 版）。
4. **D-14 那张票的机制前提不成立**：四只脚本都 `from rag_chain import vectorstore`，而 `rag_chain.py:125` 是 `CHROMA_DIR = os.environ.get("CHROMA_DIR") or DEFAULT_CHROMA_DIR` ⇒ 它们**没有自己的固定目标**，`assert_matches` 对它们是恒等式、永不咬红。票已就地重写：换成 ① `require_explicit_target(caller, writes)`——"没选过目标就不许写生产默认目录"（与 `assert_matches` 是两根不同的轴）；② 评测/验证两只改到临时目录上跑；③ 破坏性子命令默认 dry-run + 显式 `--write`。判据里明写"只断言守卫被调用＝假绿"。

**B 找到但我本轮**只登记不实现**的两条**（都是新问出来的，进 §B 等 Owner）：
- **D-33**：409 的 `step_budget` 档今天走不到（`state_machine.py:29-36` 的 `FREE_STEP_EDGES` 免计步 ⇒ `_limit` 不在这两个站点炸），而真正的追问轮数上界是 `max_clarifications`，它不落 409。本轮只把措辞改准（不再说"追问次数"）并就地标注判据盲区：**AST 全覆盖只保证"每个码有一档"，不保证"码可达"**。
- **D-34**：Agent 路径没有占位补偿腿（`_agent_streaming_response` 是裸 `StreamingResponse`，没有 `on_response_close`）⇒ Agent 轮次被取消时可能留下没有配对的用户消息。**不是本轮引入**，且它要自己的用例集，刚被复核钉过的取消面不宜同批二次改 ⇒ 登记待裁。

**其余 B 提到的过期数，我逐条现量后改了**：D-12 的镜像只数 29⇒**32**（并给两轴相等的读法）；D-20 分组按 `176899f` 重算＝**99**（backend 74 / frontend 15 / docs 5 / 其余 5 项各 1，相加 99）；D-14 票里"2 处 `load_dotenv`"精确成"第 26 行**模块级调用** + 第 24 行 import"（模块级装载真实 `.env` 比 CLI 里装更危险，这条本来就该写准）。

**我自己再补一条纪律**：本轮两处"我已经改好了"的表述（"不占每次 PR"、"空答仍是不响应"）都是我**写完实现后按意图**写的，不是按读数写的。B 之所以能打到，是因为它去数了 `if:` 的个数、去读了 `stream()` 里有几处 return。**⇒ 凡"我已经把它做成 X"的句式，X 必须是一个可数出来的东西。**

## 47. 补记四十六（2026-10-11 07:5x：Owner 问"汇报写好了吗"⇒ 我做 key×文件对账，并把最后两处自曝错补进正文）

对账仪器：`evidence/work_log_key_audit.py`（25 个 key，每个都要求在正文里出现，脚本自己报"未落正文的项"）。
现量：**25/25 命中，未落正文 = 无**（`audit_rc=0`）。对账用的是 key×文件矩阵，不是"我记得写过"。

**补记两条我此前只在对话里承认、正文里还没有的自曝错**：
1. **计数词又是口算的**。我在 J §0/§3 写过"18 条全部处置完"，真值是 §A/§B 从 **18 条降到 2 条**（差集实测离场 15、加回 2 条新裁项）——错在没跑差集就写"全部"。
 现在这条由脚本兜着：`evidence/ledger_move_rows.py` 与 `apply_review_findings.py` 都用"旧备份 vs 现文件"的编号差集出数，
 且改台账的脚本带 `assert removed == 预期` 的拦截（本轮它真的拦下一次错锚点：`待你过字`↔实际是`要你过字`，断言失败 ⇒ 整笔不落笔）。
2. **同一个坑我又踩第三次**：中文串里嵌 ASCII 双引号 ⇒ `SyntaxError`。本轮两次（一次写台账搬运脚本、一次写 D-14 票搬运脚本），
 一次表现为 bash 提前 EOF、一次表现为 ruff `invalid-syntax`。铁律在我自己的记忆里早就写过（"用全角引号"），
 **但它没被写进交付报告的"错误"栏，所以我又没遵守 ⇒ 教训落点要在被使用的地方，不是只在备忘里。**
 本轮之后的写法：脚本里的中文散文一律不带 ASCII 双引号；需要竖线用 `chr(124)`、需要反斜杠用 `chr(92)`。

**另外三条本轮尾部才出现的小错，一并记在这里**（都已被仪器抓到、已改）：
- 我在这节的自曝错里数"gates 有多少节"时写了 `d.count(bytes(10)+b'## ')` —— `bytes(10)` 是**10 个 NUL**，不是换行符，
  所以那把尺子恒返 0（读出来是"节数=0"）。改成先按 `chr(10)` 切行再数前缀，现量 **47 节**。
  这条正是我记忆里那条老规矩的第 N 次现场版：**工具的 0 不可信，尤其当那个 0 是我自己刚敲出来的。**
- 表格单元里写 shell 的 `||` 与 `| wc -l` ⇒ 劈列（D-25 行 4→7 列、D-12 行 4→5 列）。尺子 `evidence/md_table_columns.py`（自带 `--selftest` 正负对照）抓到，转义后坏=0。
- 我把两条**新待裁项（D-33/D-34）先错放进 §C**（已裁档），且按 §C 的三列写成四列 ⇒ 列数检查器 + 我的重号脚本一起报红；已挪回 §B 并补成五列。
- 我在 J 的 §10.3 里写"未逐处清 D-18 同族"，随后扫出**命中 0**——那句"未做"过期了。现按现量改写（扫干净这件事本身也写进了 §10.3 与 §45）。

**收口状态没有变**：本地 7 笔、头 `424f8af`、`porcelain=0`、未 push/未开 PR/未合并/未轮换/未动真实库与容器；
等你的是台账 §A 两条推送动作（D-5、D-19）+ §B 两条新裁项（D-33、D-34）。

## 48. 补记四十七（2026-10-12 00:3x–01:0x：接手会话把 D-34/D-14 的未提交交付做成「验收对象＝交付对象」，并修掉 `.dockerignore` 那条）

**接手现场（现量，不是抄上一轮）**：候选 `19e296e`（`0b54396..HEAD` 30 笔），工作树 **9 只 tracked 改动 + 2 只未跟踪测试**，
mtime 10-11 17:07–19:19；上一轮在册说法是 `porcelain=0` ⇒ 有交付停在未提交态。那 8 只交付文件的 sha256 **8/8 命中**
D-34/D-14 两份报告的锚定值 ⇒ 盘上字节＝被审过的字节。归属：`main.py`+`test_agent_turn_compensation.py`=D-34；
5 只 CLI 脚本+`test_index_cli_safety.py`=D-14。

**这一轮真正缺的一步是「全量集成复验」**（两份报告各自只跑了隔离回归，且都明写完整项目门未重跑）：

| 腿 | 现量 | 证据（运行根 `evidence/` 下） |
|---|---|---|
| 第一趟全量（未提交集成态） | **2 failed / 2014 passed / 10 skipped / 18 deselected，cov 86.55%，rc=1** | `integration-gates-backend-20261012.log` |
| 红的两条用例名 | `test_agent_resume.py::test_agent_fallback_on_resume_feeds_run_date_into_fast_path`、`test_chat_turn_persistence.py::test_other_conversation_is_not_blocked_and_route_exception_releases_lock` | 同日志 FAILED 行；与 D-3 复核件 §3 预告**逐字相同** ⇒ 不是新故障，是 D-34 改接口后旧测试仍桩在 `_execute_agent_observing_disconnect` |
| 定向接线修 | **2 passed，rc=0**，15.40s | `wiring-fix-targeted-20261012.log`；补丁 `d3-current-review-20261011/baseline-test-compatibility.patch`（2 只文件 / 39 行 / CR=0） |
| 第二趟全量 | **2016 passed / 0 failed / 10 skipped / 18 deselected，cov 86.55%，rc=0**，278.87s | `integration-gates-backend-pass2-20261012.log`、同名 `-junit-` XML（`tests=2026 errors=0 failures=0 skipped=10`） |
| 分母闭合 | collected 轴 **2026/2044**（2016+10=2026，+18 deselected=2044） | 同日志 COLLECT ONLY 段 |
| 静态与前端 11 条腿 | **10 条 rc=0**：pip check / ruff check / ruff format / mypy 整仓 / mypy 五脚本显式 / `git diff --check` / lint / tsc / vitest **9 files 83 tests** / `build:check` **VERDICT=OK**（四个 `.badge-*` 各 1、控件 `.badge{`=1、`.upload-zone`=3） | `static-and-frontend-20261012.log` |
| 唯一 rc=1 的那条 | `npm run format:check` ⇒ **3 只**（Stats/Upload/Users Section），与在册「两把口径 3 vs 15」同形；本轮未动这三只 ⇒ 见台账 D-37 | 同上第 [10] 段 |

**三笔提交与「交付==验收」的证法**：`c15b775`(D-34 + 接线修，4 只) → `87f58c0`(D-14，6 只) → `a9ef432`(`backend/.dockerignore`)。
每笔提交前 `git diff --cached --name-only` 只列点名的路径；接线修与接口变更**同笔**落地，是为了不给 bisect 留一个自身带红的中间提交
（补丁出自 D-3 复核会话，本轮只做接收与复验，这句写在提交信息里）。
提交后 `porcelain=0`，且 11 只文件逐个比对 `git ls-tree -r HEAD` 的 blob id 与 `git hash-object --no-filters` 的盘上值**全等**、CR 全 0
⇒ 刚跑绿的那批字节就是现在库里的字节；其中两只被 patch 的文件落盘 blob 恰为补丁声明的 `1ead4040`、`b132d6ec`。

**`.dockerignore` 从「实装面已证」走到「修好并复量」**：改为 `**/*.db`、`**/*.sqlite*`、加 `.ptmp*`。
没有用整目录 `data/` 排除，因为 `backend/data` 里有两个运行时要读的评测件（`git ls-files backend/data` 现量 2 只），整目录排除会静默少数据。
本轮**不重复读真实库字节**，改用合成上下文跑同一把尺子：`dockerignore-probe-20261012/` 预登记 10 格期望，实际 **10/10 全中、`VERDICT=FIX_VERIFIED`**
（`evidence/dockerignore-probe-20261012.log`）。单变量对照是同一目标 `data/app.db` old=ALLOWED→new=BLOCKED；
没有任何规则涉及的 `data/eval_agent_complex.json` 两套规则都 ALLOWED（防过度排除）。runner 自带两道闸门：基底镜像缺失 ⇒ REFUSE，
正对照不是 ALLOWED ⇒ REFUSE —— 否则基底不在时「所有构建都失败」会被读成「全都挡住了＝修好了」，那正是这类判据最舒服的假绿形状。

**两台仪器自曝错（写进正文，不只留在对话里）**
1. 我第一条命令给出的「`PYTEST_RC=0`、1 秒、正文一个字没有」是假的：PATH 上 `C:\Users\33393\.local\bin\env` 是个只设 PATH 的 shell 脚本，
   把 `env VAR=x cmd` 整条吞掉并回 0。⇒ 这台机器上任何用裸 `env` 起的命令都要先证明它真的跑了；改用 `export` 起才有 17%/35%/53% 的真实进度。（这一句第一次写成了 `C\Users\33393…`，我当时的断言只查了「反斜杠+Users 在不在」而没查 `C:` 后的分隔符，所以它没被自己拦住——断言要断在真实形状上，不然它只是我意图的回声。）
2. 我第一版探针的期望表把 `(old,new)` 元组当成值用 ⇒ 10 格里 9 格被误标 BLOCKED（打印出的「ALLOWED=1」这个荒谬数当场暴露）。修完才是 5 ALLOWED / 5 BLOCKED。
   自造复算器的手写期望表本身也要跑一遍对照，不能只信「我按意思写的」。

**本轮没有动的**：未 push、未开 PR、未合并、未轮换凭据、未读真实库内容、未动现役栈（`netstat` 现量 8088 仍 LISTENING、3000/3021 无监听）、
未跑 `slow`/`real_kb` 腿、未重跑在线依赖审计；D-3 仍按 D-29「本轮不落」。阶段结论仍 **BLOCKED**，本轮只把「已交付但未验收＝未交付」这一格关掉。

**入册时又查出一格文档漂移（本轮现量）**：把 42 只镜像件逐只与运行根比 sha256 ⇒ **DIVERGED=5**：
`closeout-final-J-draft.md`、`d3-langchain-migration.md`、`dispatch-D14-index-write-guards-20261011.md`、
`dispatch-D20-merge-into-master-20261011.md`、`runbook-I-push-pr-merge.md`。五只都是运行根更新且更大（后续重写没回灌镜像），
其中 D-14 那张票在 10-11 19:25 换过机制前提（旧前提被复核推翻），谁按仓里那版开工就会照被推翻的前提干活 ⇒ 本轮以运行根为准回灌，回灌后 diverged=0。
另 3 只镜像件（`gold-freeze-draft.md` 与两份 round2 复核报告）并不在运行根的 `reports/`+`tickets/` 下，而在 `model-validation/` 与 `reviews/20261011-round2/`；
我第一次扫描只看了那两个目录，差点把它们说成"仓里有、根上没有"的孤儿——**口径必须写明是哪两根目录，不是整个运行根**。

## 49. 10-12 接手轮第二遍：D-35(a) 候选侧与 D-33 负例（Owner 一句「按推荐」整包）

**结论**：D-35 的候选侧那一半与 D-33 三条负例已落码并提交；两枚负控各自 VERDICT 达标，全量门在**含新增 14 条判据**的树上重跑绿。
非部署阶段仍 **BLOCKED**：D-35 的服务器两步、D-5 推送、D-19、F/G/J5/J6 一条没被本轮抵消。

**现场读数（本轮本机跑，cwd＝候选 `backend`，解释器＝运行根 `candidate-envB`，Python 3.11.0）**

| 检查 | 读数 | 原始证据（运行根 `evidence/` 下） |
|---|---|---|
| 全量非 slow（第三趟） | 2030 passed / 0 failed / 10 skipped / 18 deselected，rc=0，cov **86.57%**（门槛 70），259.73s | `integration-gates-backend-pass3-20261012.log`、`integration-gates-backend-junit-pass3-20261012.xml`（tests=2040 failures=0 errors=0 skipped=10） |
| 与上一趟的分母关系 | 上一趟 junit tests=2026 ⇒ 本轮 2040 ＝ +14（`test_reset_admin_password.py` 10 条 + `test_agent_resume.py` 4 条）。`-q` 这两趟都没打印 collected 头，**不引用"collected"这一轴** | `integration-gates-backend-pass2-junit-20261012.xml` 对照 |
| Ruff lint / format | 均 rc=0（286 files already formatted） | `static-gates-20261012-round2.log` |
| mypy | rc=0，Success: no issues found in 74 source files（仍有既有未类型化函数体提示，不是全仓类型覆盖） | 同上 |
| D-35 定向判据 | 10 passed，rc=0 | `d35-reset-targeted-20261012.log` |
| D-35 变异仪 | 控制腿绿；9/9 期望臂杀；每条臂还原后**逐字节相同**；只在 `d35-mut-tree/` 副本树动，产品树未被写过 | `d35-mutation-20261012.log` VERDICT=ALL_EXPECTED_ARMS_DIE，驱动器 `d35-mutation-20261012.py` |
| D-33 负控 | 控制腿 4 passed；内存源码变异后点名杀 3 条、反向护栏腿按预期存活；`agent/state_machine.py` 前后 sha 相同 | `d33-mutation-20261012.log` VERDICT=NEGATIVE_CONTROL_HOLDS，插件 `d33_mutation_plugin.py` |
| 提交与树 | 本轮两笔 `cd2007e`（D-35）、`c4cc6b3`（D-33），`porcelain=0`；笔数与头以 `git -C "$C" rev-list --count 0b54396..HEAD`、`rev-parse HEAD` 现读为准，本行不钉死 | — |

**为什么 D-35 的形状变了（我的错前提，更正三处留痕）**
- 我上一版写「全仓没有改口令入口」——**假阴性**。我只 grep 了 `main.py` 与 `backend/` 根目录，漏了 `backend/scripts/`。
  入口自 `5e51384`（2026-09-17）就在库里，tracked，且**零测试、零文档指针**（`git grep -n reset_admin_password -- ':!dispatch-output'`
  只命中本轮新写的两份汇报）。
- 因此 Owner 签的 (a) 里「我新写一个脚本」这半句作废，实际做成了**改造既有入口**；已批属性一条没少：口令不进 argv、
  不回落 `.env`、不打印哈希、不动 `is_active`/`role`。留痕位置：本段、台账「给 Owner 的几句话」第二条与 §C D-40、提交 `cd2007e` 的正文。
- 顺带收掉在册 **B-44**（`--password` 走 argv + 改密不落 `log_audit`）。`.env` 回落这条比原登记更危险：库里那个账号正在退役，
  而缺省路径会把 `.env` 里那个**待退役的旧值原样写回库**，看起来"重置成功"、实际零变化。
**本轮我自己的三处仪器错（都是读数当场暴露，不是事后追认）**
1. **同文件两条 edit 的还原回到中间态**：第一版驱动用 `originals[path] = text` 记账，M9 那臂对 `auth.py` 有两处替换，
   第二次把**已变异**的文本当成原始值存进去 ⇒ 还原只回到"打了第一处"的状态，日志给的是 `sha_identical=False`。
   这等于把副本树留在被污染状态，且第一轮的 M9 读数不可复用。修法：原始字节按路径**只取一次**，替换在内存里串联，
   还原逐字节写回并逐文件复量（第二轮日志每条臂都是 `byte_identical=True`）。
2. **杀了的腿被我误记成未杀**：`-q --tb=no` 的短摘要把首行失败原因缀在名字后面
   （`FAILED ...::test_preview_writes_nothing - Asse...`），我的 `split("::")[-1]` 因此不等于期望名 ⇒
   第一轮报 `killed=8/9`。方向与"假绿"相反（它低估自己），但同样是**不准的读数**；修成 `split(" - ")[0]` 后 9/9。
3. **JSON 转义把我的 `\n` 折成真空行**，驱动文件第一次写坏（`SyntaxError`，AST 自检当场拦下，零读数产出）；
   改写为完全不需要反斜杠的 `bytes([10])` / `write_bytes` 形式。

**D-35 十条判据各自钉什么**（`backend/tests/test_reset_admin_password.py`）
import 不改库指向（本文件其余九条能安全 import 被测脚本的前置闸）／argv 带不进口令／
`.env` 的 `ADMIN_PASSWORD` 不会被当新值写回／预览不写库也不落审计／`--write` 改哈希且 `role`+`is_active` 不动、
审计恰好一条且输出里查不到口令与哈希／未知用户拒绝且不创建／空口令与公知默认 `admin12345` 各自拒绝／
两次输入不一致不写／改口令**不作废**已签发 token（走现役 `get_current_user`，把"必须换 `JWT_SECRET`"从口头变成判据）。
`admin12345` 这个字面量不是新暴露：`backend/seed_admin.py` 早在对抗审计 2026-08-07 的注释里写着同一句（`git grep -c admin12345` 命中 1）。

**D-33 四条负例**（追加在 `backend/tests/test_agent_resume.py` 末尾）
`test_steps_over_cap_still_raises_in_the_state_machine`（状态机自己 fail-closed，reason 为 `budget_exceeded:steps`）、
`test_steps_over_cap_resume_is_step_budget_and_leaves_run_untouched`（恢复层转 `step_budget` 档、`__cause__` 是 `BudgetExceeded`、
且 `state_version`/`pending_question`/`status` 三项原样）、`test_lowered_step_budget_rejects_the_same_run_through_the_same_path`
（预算下调后旧 run 越界走同一条拒绝路）、`test_clarification_exhaustion_stays_on_its_own_axis`（反向护栏：
clarifications 打满 + steps 恰满 cap 时回答仍收得下，`steps` 不被顶高、`clarifications` 不被消耗）。
票上第 1 条「steps 恰满 cap 可恢复」**已由 `test_resume_at_exact_step_cap_succeeds_...` 钉住**（断言 CAS+1、状态到 PLANNING、
steps 停在 cap、事实落库），本轮不重复造。反向护栏在 step-limit 变异下**存活是预期**——它量的不是那根轴。

**票面刷新**：第三轮独立复核票已随本轮刷头重写：`tickets/dispatch-independent-review-20261012-round3.md` 从七颗钉子扩到九颗
  （第八颗查 D-35 判据并要求**自拟反证**、不许复用我那 9 臂；第九颗专门让我自己那条"反向护栏存活是预期"的说法被挑战），
  B 路多加一项：用我这台假阴性机器（只 grep `main.py` 与 `backend/` 根目录）回查台账里所有"没有 X／只剩 Y"式主张。
  钉子 1/4/5/6/7 的期望值随头刷新（2030 passed、collected 2040/2058、并集 1..40、清单改给现读命令）。**派发权在 Owner**，我没派。

**本轮明确没做（不是做了没写）**
- `--write` 从未对**真实库**执行过；判据只在 conftest 的进程私有临时 SQLite 上成立。候选工作树里的 `backend/.env` 是
  **0 字节**（`load_dotenv()` 返回 False、新置键 0 个），所以本轮任何测试进程都没接到现役配置值。
- 服务器上的两步（跑脚本、换 `JWT_SECRET` 重启）只能 Owner 做；D-39（按用户作废会话）一个字未动。
- 前端腿本轮**未重跑**（本轮零前端文件改动，`§48` 那 11 条读数不能当本轮证据复用）；`socket` 非回环守卫、`pip check`、
  在线 `pip-audit`、`slow`/`real_kb`、远端 CI 当前对象读数同样未跑。
- 台账里那格「D-35 的真实入口」已从 §B 搬进 §A（只剩你动），D-36/D-37 进 §C；复算 `evidence/ledger_row_audit.py`
  现量 §A=3、§B=1、§C=36、max=40、无跨档重复无缺号；单文件对账 `evidence/audit_one_file.py` 对台账 68 个 key 缺 0。
