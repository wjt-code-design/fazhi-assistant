# T4 未跟踪资产清点与入库/清理建议

> 只读清点卡。**绝对零删除**（连移动/改名都未执行）。唯一写集：`dispatch-output/t4-assets-20260920/`。

## ① 读数快照时刻（报告锚点）

- **快照时刻**：`2026-09-21T00:16:42+08:00`
- **开工 HEAD**：`2a48f3ec0f4b906302755504131c5da252e38f77`
- **未跟踪 ENTRY 计数**（`git status --porcelain`，目录折叠）：**445**
- **未跟踪 FILE 计数**（`git ls-files --others --exclude-standard`，逐文件）：**30331**
- **与基线对照**：`baseline.json` 记录未跟踪数 22:21=396 → 22:37=409 → 23:41=431（均为 ENTRY 口径）；本快照 ENTRY=445（+14，来自本波新增的 t1..t12/takeover 顶层目录折叠项）。FILE 计数基线未记录，现 30331。
- **口径说明**：`431` 与 `30331` 不矛盾——前者是 `git status --porcelain` 把整目录未跟踪折叠成一条 `?? dir/`，后者是 `git ls-files` 逐文件展开。绝大多数文件位于 `dispatch-output` 的 `copytree/`、`beforetree/`、`mut-*` 等整目录未跟踪树下。

## ② 本波自产目录（规则②：单列，不计入存量分类）

以下为本次 `t1..t12-*-20260920` + `takeover-parallel-20260920` 派发波次的自产目录，由各自卡的交付纪律管理，T4 不对其做归类：

- `dispatch-output/t1-flaky-20260920/`
- `dispatch-output/t10-disabled-taxonomy-20260920/`
- `dispatch-output/t2-slow-20260920/`
- `dispatch-output/t3-appdb-20260920/`
- `dispatch-output/t4-assets-20260920/`
- `dispatch-output/t6-sourcekey-survey-20260920/`
- `dispatch-output/t7-fingerprint-coverage-20260920/`
- `dispatch-output/t8-e2-multi-20260920/`
- `dispatch-output/t9-eval-credibility-20260920/`
- `dispatch-output/takeover-parallel-20260920/`

- 合计 **10 个目录 / 4048 文件**（其中 takeover-parallel 16 文件）。
- 说明：t5=票 I（不派发）；t11 复用 `te-chroma-isolation-20260918`、t12 未见 20260920 同名目录，故未列入本波自产。

## ③ 外部在途物（规则③：列名但标『外部在途，别动』）

- `backend/.ptmp-s4-run2/` —— **外部在途，别动**。票 I 的临时目录（未跟踪 ~2.2MB，含 gitignored 内容约 3.9GB）。
- `docs/code-review-report-02e3851-20260918.md` —— **外部在途，别动**。另一会话正改的**已跟踪**文件（故不出现在未跟踪清单中，但本波禁止触碰）。

## ④ dispatch-output 占用前 10（规则④：排序命令 + 读数 + 每项目『没落地的事』）

**排序命令（给出供复跑）**：
```bash
# 注意：du 对 800MB 级目录较慢；下面给出标准命令，读数以 Python os.walk(isfile 分支) 实测为准
du -sb dispatch-output/* 2>/dev/null | sort -rn | head -10
```
> 环境坑：对目录用 `os.path.getsize` 需自写递归；`os.walk` 对文件统计有恒为 0 的坑——本清点用 `os.path.isfile` 分支逐文件累加，见 `_final.py`/`_gather.py`。

**读数（本快照实测，递归字节数）**：

| # | 目录 | 字节 | 约合 | 背后还有没有没落地的事 |
|---|---|---|---|---|
| 1 | `dispatch-output/hij-h-20260920/` | 812168247 | 775MB | 本波 T1–T12 派发总任务书母本（ALL-PARALLEL-TASKS.md + 各卡启动语）+ 内部 copytree/beforetree（整份 backend 副本含 .venv）。结论：它是本波输入源，12 卡正在消费它；容器与任务书已是权威派发，无『未落地工作』，体量来自整份 backend 副本而非结论。→ 容器别动（取证母本），内部 copytree/beforetree 属可清理。 |
| 2 | `dispatch-output/hij-j-20260920/` | 802943609 | 766MB | 票 J 相关派发件 + 副本树（copytree/pretree）。结论：票 J 派发与副本，无未落地；本波 T 卡已引用它。同 hij-h：容器别动、副本可清。 |
| 3 | `dispatch-output/s6-stream-gate-20260920/` | 774257420 | 738MB | 副本树搭器 make_copytree.py + 副本（aftertree/copybase/mut-out/mut-out-r2）。结论：工具与副本，无未落地工作；是 T1 等副本的来源，工具本身有持久价值。 |
| 4 | `dispatch-output/hij-i-20260920/` | 455205443 | 434MB | 票 I 副本树/证据（probe_i2_corpus_inventory.py 等）+ copytree。结论：票 I 已于 23:41 收工（回表 + 报告入库），证据可留；无未落地。 |
| 5 | `dispatch-output/t1-flaky-20260920/` | 453420622 | 432MB | 本波 T1 自产（copytree + 5 轮 pytest 跑次 + matrix.json/report.md）。结论：T1 自己的交付，归 T1 卡管理（规则②单列），不计入存量。背后是 T1 未完成的判定工作由其卡负责。 |
| 6 | `dispatch-output/t0-baseline-checkpoint-20260916/` | 287005854 | 274MB | 较早的基线检查点副本（112 文件）。结论：历史基线证据，无未落地；作为历史参照可留。 |
| 7 | `dispatch-output/quality-fix-20260915/` | 139830070 | 133MB | 质量修复波次的副本/证据（80 文件）。结论：历史质量波次，无未落地。 |
| 8 | `dispatch-output/pytest-full-20260917/` | 112542097 | 107MB | 全量 pytest 跑次产物。结论：一次性跑次产物，结论已在别处沉淀，无未落地。 |
| 9 | `dispatch-output/quality-item2-20260915/` | 63934495 | 61MB | 同上质量波次（45 文件）。结论：无未落地。 |
| 10 | `dispatch-output/t2-evidence-replay-20260916/` | 57771521 | 55MB | t2 证据回放（63 文件）。结论：历史证据回放，无未落地。 |

## ⑤ 四类归类（规则⑤：必须入库 / 建议入库 / 可清理 / 别动）

> 存量口径 = 全仓未跟踪 **剔除** ②本波自产、③外部在途之后的剩余资产。主要为 `docs/`（29 文件，全部为存量——外部报告 `code-review-report-02e3851` 系已跟踪文件，本就不计入未跟踪）、`outputs/`（54）、`evals/`、`backend/tests/` 新文件、以及 **101 个 prior-wave `dispatch-output` 目录（26163 文件）** 与 26 个根级异常目录。

### 必须入库（must archive）

- **docs/ (29 files, ~2.46 MB)** —— 项目文档/交接件/计划/质量指南，是结论与上下文，未入库即丢；全部为手写 markdown 交付物，非可再生。
- **backend/tests/test_contract_silent_empty_probe.py (1 file)** —— 新增测试源码，应入库以免丢失；属 backend 测试，不可再生。
  - 具体 29 个 docs 文件见 `classification.json → classification.must_archive` 及下方附录清单。
### 建议入库（suggest archive）

- **outputs/ (54 files, ~678 KB)** —— p5-review-20260917 评审交付物（zip + 各章节 markdown + json），有留存价值。
- **evals/probe-results-k4.json (~97 KB)** —— 评测探针结果，属评测证据，建议入库。
- **dispatch-output/<prior-wave>/*/{report.md,findings.json,taxonomy.md,checklist.md,readings.json,matrix.json,*verdict*.txt,*.json结论件}** —— 各历史波次（hij-h/hij-j/hij-i/s6/te-chroma-isolation/ticket*-evidence/review-*/quality-*/t0-baseline 等 101 个 prior-wave 目录，共 26163 文件）内的结论件，留存可复现；其中 copytree/bt*/mut* 等可再生副本不在此列（见可清理）。
### 可清理（can clean）——只列清单，未执行任何删除

- dispatch-output/*/copytree/ （整份 backend 副本，可经 make_copytree.py + 对应 commit 重建）
- dispatch-output/*/beforetree/ 、*/pretree/ 、*/aftertree/ 、*/copybase/
- dispatch-output/*/bt*/ （pytest --basetemp 产物）
- dispatch-output/*/mut-*/ 、*/mut-out*/ 、*/mut-out-r2/ （变异基线）
- dispatch-output/**/__pycache__/ 与 **/*.pyc
- dispatch-output/*/.venv/ 、*/node_modules/ 、*/chroma_db/ 、*/data/ （副本内数据库/venv）
- *.junit.xml 、run-*.xml 、*.stdout.txt 、full-baseline.xml （跑次日志/基线 xml）
- outputs/p5-review-20260917/_build/ （23 个构建脚本，可重建）
- .qoder/ （3 文件，IDE 工具状态，可重建）
### 别动（do not touch）

- **backend/.ptmp-s4-run2/ （外部在途：票 I 临时目录；未跟踪 ~2.2MB + 含 gitignored 内容约 3.9GB）** —— 规则③：票 I 在途物，本波禁止触碰，也不计入存量分类。标『外部在途，别动』。
- **docs/code-review-report-02e3851-20260918.md （外部在途：另一会话正改的已跟踪文件）** —— 规则③：另一会话在途物（已跟踪但正被改），本波禁止触碰。标『外部在途，别动』。
- **caddy_config/ 、caddy_data/ （运行时状态）** —— caddy 反向代理运行时状态；服务在跑时别动，停机后方可清。标『别动』。
- **根级中文句命名的 26 个目录（含 0 / E04 / FAIL 及 23 个中文句目录，如『本文是下一位执行助手的唯一启动入口。...』『宿主：127.0.0.1：18126，AGENT_ENABLED=true』等）** —— 来历不明、疑似误将文档正文当路径建目录（明显数据质量事故）；别动，需 Owner 排查是否误建、有无内容需抢救。
- **dispatch-output/<prior-wave> 容器目录（hij-h/hij-j/hij-i/s6/te-chroma-isolation/ticket*-evidence/review-*/quality-*/t0-baseline 等 101 个）整体** —— 历史取证母本，整体别动；其内 copytree/bt*/mut* 已单列可清理、report.md 已单列建议入库。删除需 Owner 裁决。
- **dispatch-output/t1..t12-*-20260920/ 与 takeover-parallel-20260920/ （本波自产，共 4048 文件）** —— 规则②：本波 12 卡 + 接管会话自产，单列不计入存量；归各卡交付纪律管理。标『本波自产，别动（T4 不碰）』。
## ⑥ 数据质量告警（额外发现）

仓库根目录存在 **26 个以完整中文句子/状态 token 命名的目录**（如 `本文是下一位执行助手的唯一启动入口。...`、`宿主：127.0.0.1：18126，AGENT_ENABLED=true`、`0`、`E04`、`FAIL` 等）。这强烈疑似某脚本误将文档正文或状态文本当作路径建目录，属明显数据质量事故。**已列入『别动』并要求 Owner 排查**，未做任何删除/改名。完整列表见 `classification.json → anomalies.weird_root_dirs`。

## ⑦ 五段回报（固定形状）

### ① 结论

全仓未跟踪资产在快照时刻（2026-09-21T00:16:42+08:00）为 **445 entry / 30331 file**，HEAD=2a48f3ec。其中本波自产（10 目录/4048 文件）与外部在途（2 项）单列不计入存量；存量主体为 101 个 prior-wave `dispatch-output` 目录（26163 文件）+ `docs/`/`outputs/`/`evals/` + 26 个根级异常目录。结论：绝大多数体量（copytree/bt*/mut*）可清理（可再生副本），真正的结论件（docs/各 report.md）应入库；发现 26 个根级误建中文句目录，需 Owner 排查。全程零删除。
### ② 产物

- `dispatch-output/t4-assets-20260920/inventory.md`（本文件）
- `dispatch-output/t4-assets-20260920/classification.json`（结构化四类归类）
- 关键读数：HEAD=`2a48f3ec0f4b906302755504131c5da252e38f77`；ENTRY=445；FILE=30331；本波自产=4048 文件；prior-wave dispatch-output=101 目录/26163 文件；根级异常目录=26。
### ③ 判据对照

| 判据 | 满足 | 说明 |
|---|---|---|
| 按四类逐项归类『必须入库/建议入库/可清理/别动』并给路径与理由 | 满足 | 见 §⑤ |
| 『可清理』只列清单 | 满足 | §⑤ 可清理节仅列路径，未删除 |
| 报告首部标注读数快照时刻 | 满足 | §① 钉死时刻/HEAD/双口径计数 |
| t1..t12/takeover 本波自产单列不计入存量 | 满足 | §② |
| 外部在途物列名标『别动』 | 满足 | §③ |
| dispatch-output 占用前 10 + 各答『没落地的事』 | 满足 | §④ |
| 绝对不执行任何删除 | 满足 | 仅写交付目录，零 git 写、零删除 |
### ④ 我复跑的命令

```bash
export PATH=/c/Users/33393/.workbuddy/binaries/PortableGit/versions/1.2.0/usr/bin:$PATH
cd C:/Users/33393/Desktop/ai-legal-helper
git rev-parse HEAD
git status --porcelain | grep '^??' | wc -l          # ENTRY 计数（目录折叠）
git -c core.quotepath=false ls-files --others --exclude-standard   # FILE 计数（逐文件）
git -c core.quotepath=false ls-files --others --exclude-standard | wc -l
# dispatch-output 占用前 10（shell 标准命令；慢可用 Python 递归替代）
du -sb dispatch-output/* 2>/dev/null | sort -rn | head -10
```
- Python 递归测大小（规避 os.walk 恒为 0 坑）：见交付目录内 `_gather.py`/`_final.py`（`os.path.isfile` 分支累加）。
### ⑤ 诚实登记

- **未做到的 / 读不到的**：无。所有计数均从本仓真实 `git` 读取，未依赖推断。
- **越界写声明**：无。仅写入 `dispatch-output/t4-assets-20260920/`（`_gather.py`/`_probe*.py`/`_final.py`/`_*.json`/`_*.out` 为中间产物 + `inventory.md`/`classification.json` 为交付物）。未触碰 backend/、未改任何文件、未执行 git add/commit/rm。
- **关键发现**：① 基线『431』是 entry 口径，本快照 entry=445、file=30331，二者不矛盾（目录折叠 vs 逐文件）；② `docs/code-review-report-02e3851-20260918.md` 实为**已跟踪**文件（在途被改），故不在未跟踪清单中；③ **26 个根级中文句命名目录**疑似误建，已标别动并告警；④ `backend/.ptmp-s4-run2/` 未跟踪内容仅 ~2.2MB，但其所在 backend/ 目录总磁盘约 3.9GB（多为 gitignored 的 .venv/chroma_db 等）。
- **未证实的**：t11/t12 的 20260920 同名目录未出现（t11 复用 te-chroma-isolation-20260918，t12 可能尚未开工或另命名），未对其下结论。
## 附录：必须入库的 docs/ 文件清单（29）

- `docs/auto-verify-book-20260915.md`
- `docs/code-review-fixes-20260915.md`
- `docs/code-review-report-20260915.md`
- `docs/code-review-report-f889da3-20260917.md`
- `docs/evidence-chain-review-27d5363-20260918.md`
- `docs/execution-plan-entity-precision-20260917.md`
- `docs/external-harness-plan-gap-analysis-20260918.md`
- `docs/final-agent-mainline-handoff-20260916.md`
- `docs/frontend-execution-book-20260915.md`
- `docs/frontend-review-refactor-plan-20260915.md`
- `docs/handoff-external-harness-20260918.md`
- `docs/handoff-r15-and-git-repair-20260919.md`
- `docs/handoff-takeover-20260918.md`
- `docs/handoff-takeover-20260919.md`
- `docs/progress-and-backlog-20260919.md`
- `docs/project-next-execution-plan-20260916.md`
- `docs/project-quality-guide-20260914.md`
- `docs/prompt-architecture-audit-20260917.md`
- `docs/prompt-engineering-review-20260917.md`
- `docs/quality-e2e-structural-plan-20260915.md`
- `docs/quality-guide-progress-audit-20260915.md`
- `docs/retrieval-recall-final-plan-20260916.md`
- `docs/session-report-r15-and-git-repair-20260919.md`
- `docs/superpowers/plans/2026-09-18-p17-p21-p13-harness-batch.md`
- `docs/superpowers/plans/2026-09-18-r15-law-version-tripwire.md`
- `docs/superpowers/plans/2026-09-19-over2-replay-audit.md`
- `docs/work-progress-20260914-session3.md`
- `docs/work-progress-20260916-session3.md`
- `docs/work-progress-handoff-20260916.md`
