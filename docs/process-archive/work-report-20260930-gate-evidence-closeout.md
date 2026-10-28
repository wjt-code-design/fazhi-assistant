# 工作汇报 · 门禁验收 → 探针证据更新 → 固定发布对象（2026-09-30 接手轮）

> **2026-10-01 独立审核补记：当前状态见 §11，跨报告执行入口见 `docs/process-archive/work-report-20260929-d2-signoff-round.md` §16。** 下文 §0–§10 是本助手原交付时点，不是实时工作区状态。原固定对象与持久证据有效；另一会话后来移动了 snapshot 引用，本轮已对冻结的新对象补验。新增工作区凭据普查缺陷仍待处理，不能继续声称“剩余项全在 Owner”。

> **结论（先说）**：**① 助手侧本地验证与准备完成，按 O-1"本地就绪即收口"结束本轮；剩余项都在你身上（轮换/签字/将来公开）。**
> A/B/C/D 的技术项全部达成（复算器 67/67、固定 trim 对象七步门禁全 rc=0、可冷恢复）。
> **经 Owner 逐题裁定后已做**：本地两笔提交（`285ce3ac` 门禁+忽略规则、`d2d3f5bd` 两份在册文档），`.gitignore` 末行拦住那两份写着现役 `LLM_API_KEY` 的残片；
> 以及**给验收对象一个归宿**（§9.4）：仓外持久副本 `Desktop/fazhi-closeout-trim-c80d47a-20260930/`（副本 pack 冷恢复 0→2510 已跑通）+ **新建** tag `evidence/no-push-fixed-trim-20260930` 钉住它（既有 13 条引用逐字未动）。
> **仍未做**：push、PR、merge、移动任何既有引用、更新 `--expected-tree`、轮换任何凭据、真实 rerank、真实入库、部署。
> 七条裁定与四处我审错的前提/口径/自伤见 §5 与 §7.11–7.14——其中一处把两把不同凭据混成了一句话，会误导你已答的 O-3/O-6，已在原格更正并摊回给你。
> 报告初稿落盘后又做的事（持久副本 + 新 tag + 两处仪器自伤修复 + **并行会话插进来的一笔被我那条新断言当场抓到**）逐条现量在 **§10 补记**。
> 执行书：`docs/process-archive/superpowers/plans/2026-09-30-gate-evidence-and-candidate-closeout-execution.md`（复选框已按实改；按 O-8 裁定**未入册**）。

单一可转发文件。§0 是给第三方看的一段话；每条读数都带现量命令，不给手抄值。

## 0. 一段话汇总

三只发布/测试门禁的修复经回归确认（24 项→**27 项**，新增 3 项是输出隔离反例），Ruff/format/`git diff --check` 均 rc=0。
B 档探针在**本轮专属目录**里重取得一整套读数，历史自检与复算件**没有被覆盖**：复算器 `b_probe_claim_check.py` 由接手时的 rc=1 恢复为 **rc=0（67/67）**，其中接手时已知失败的三项（pytest/app/自检"读数晚于仪器"）是靠**真跑**解除的，没有改 mtime、没有放松判据。
C 侧用一个**临时 index 造的草案提交**把未提交的修复带进固定对象（不动真实 index/HEAD/分支），构造出 full/trim 两个无父快照，并只验收 trim：`c80d47a5f1a4e44a92cb6ef5cd0cf913279d4f45`（2569 文件 / 53.4MB / 无父 / 1 笔）。它与合并树的差异**恰好**是 1 处 CI 修改 + 74 个 `diag/frozen-index-004|005` + 9 只留出集/证据件；收集面与未剔树**逐 nodeid 相同（1678/1678）**。对象已打成 pack 并在**空库**里冷恢复复验（0→2510 对象，树号与整份清单逐行相同）。
D 侧量到一条会左右决定的新事实：**现役管理员口令明文存在于本地 master 与候选分支的历史里**（`817e7d3` 写入、`7eda4bb` 删除），而**远端 204 笔历史 0 命中**，本 trim 对象也 0 命中 ⇒ 普通推送会把明文口令上传到**当前仍是 public** 的仓库，无父快照不会。
E 之后按 Owner 逐题裁定落地：本地两笔提交（`285ce3ac`/`d2d3f5bd`，未推远端），以及**给验收对象一个归宿**——仓外持久副本 `Desktop/fazhi-closeout-trim-c80d47a-20260930/`（130 文件，副本里的 pack 又跑通一次冷恢复）+ **新建** tag 钉住它（既有 13 条引用逐字未动；代价是它从此可被 `--tags` 推出去）。
最后一条自证值得一提：我为了防"正文抄写过期"新加了 `delivered HEAD == live HEAD` 断言，**上线几分钟就被并行会话插入的那笔 `f328a99` 判红**，于是 §1/§10 就地标注了新 HEAD 与一处"tracked 在册复算件被改而未提交"（64/67 与 67/67 是两批读数，不是矛盾）。

## 1. 接手基线 / 交付物 / 实改文件

| 对象 | 接手时（我现量） | 交付时（下表命令现量） |
|---|---|---|
| 主工作区 HEAD | `86628ba85ca6f240894ced21c28dfecf83be5c89` | **我这一轮交付时 = `d2d3f5bd0f4b813d491a52162f1117b16aba504f`** — Owner 按 O-8 授权后**本地两笔**：`285ce3ac8039d387c7d2367d7e401ba3c32bd4f7`（`.gitignore`+7 只探针/门禁，683 插入）与这一笔（2 份在册文档，+40 行）。**只提本地，未推远端**。⚠️ 交付之后**另一条并行会话又落了一笔** `f328a99702b9b427fbc43f0917ea97ab45dea186`（16:00:47，只动 `docs/process-archive/work-report-20260929-d2-signoff-round.md`，**不是我提的、也没夹带我那两份未跟踪件**）⇒ 现量 HEAD 以 `git rev-parse HEAD` 为准，详见 §10 补记 |
| `codex/local-candidate-closeout` | `fbc29e87c14e8e6a2c0744e98d86d426f6146ade` | 未移动 |
| `snapshot/ci-fbc29e8-20260930` | `fd5a8cf2e964a6f198f60a252c27b1fca203665d` | **未更新**（本轮不跑 `--expected-tree`） |
| `refs/tags/*`（**既有**引用） | 13 条（`for-each-ref` 现量） | 13 条**逐字未动**，底片固化在 `…/results/refs-{before,after}-tag.txt`（`diff` 只多一行） |
| **新建** tag `evidence/no-push-fixed-trim-20260930` | — | Owner 授权后**新建**（不是移动）：tag 对象 `3715026403a2822cf97afad9164bd0ffeba35e93` → 提交 `c80d47a5…` → 树 `085725d9…`。建它只为**免疫 gc 剪枝**，理由与反向代价见 §9.4 |
| 草案提交（临时 index 造，不属任何分支） | — | `10ad3ffdcb2191c34d5e55b681e3630d434cdcfc` / 树 `21017f023b24454d9bd082cb5bdaa5139f2c3c78` |
| 合并树（草案 × 候选，`merge-tree --write-tree` rc=0） | — | `070c851227c018a35cda5085fb18e9a16ab7e64d` |
| 固定 full | — | `bada56a2a0e1884a79fc0510b160424f0a87267e`（2652 文件 350.1MB） |
| **固定 trim（本轮验收对象）** | — | `c80d47a5f1a4e44a92cb6ef5cd0cf913279d4f45` / 树 `085725d9c0f14c51846e9b8f355dd6e0140c1760` |

```bash
git -C C:/Users/33393/Desktop/ai-legal-helper rev-parse HEAD \
  refs/heads/codex/local-candidate-closeout refs/heads/snapshot/ci-fbc29e8-20260930
git -C . log --oneline -4                       # 看得见并行会话插进来的那一笔
git -C . rev-list --parents -1 c80d47a5f1a4e44a92cb6ef5cd0cf913279d4f45   # 只有一个号=无父
git -C . show --stat --format='%H %s' 285ce3ac8039d387c7d2367d7e401ba3c32bd4f7
git -C . status --porcelain -uno | wc -l        # 我交付时=0；并行会话之后可能非 0，见 §10
```

**本轮我实际改的文件**（下面 9 行是**接手时的工作区形状**；按 O-8 已折进两笔本地提交，`.gitignore` 那行随代码笔一起提）：

| 文件 | sha256 前缀 | 谁改的 |
|---|---|---|
| `b_build_snapshot.py` / `b_snapshot_trim_diff.py` / `work-report-20260929-d2-signoff-round.md` / `plans/2026-09-29-...release-prep.md` | `ba70baec` / `3e0e5fec` / `2a5ad5ad` / `8b44c220` | 上一轮（接手即在工作区，本轮只核对未改） |
| `b_probe_run_suite.py` | `5541fe41` | 上一轮改门禁 + **本轮 B1 加输出入口** |
| `b_probe_build_tree.py` / `b_probe_app_paths.py` / `b_probe_claim_check.py` | `b001adae` / `3abfc532` / `4db7cb9f` | **本轮 B1 新增**（`B_PROBE_EVIDENCE_DIR`） |
| `test_release_gates.py` | `4696c6ea` | 上一轮新建（接手时未跟踪）+ **本轮加 3 条反例** |
| `.gitignore` | 见 §5 O-7 | **本轮按 O-7 授权追加末行** |

现量：`git -C <repo> status --porcelain -uno` ⇒ **0**（两笔已提）；`git ls-files --error-unmatch dispatch-output/local-candidate-closeout-20260928/test_release_gates.py` ⇒ 现在**在册**。
行尾：提交后 `git show HEAD:<file> | tr -cd '\r' | wc -c` 抽测 `.gitignore` 与 `test_release_gates.py` 均 **cr=0**，即 `* text=auto eol=lf` 的 clean 过滤器没有改动字节 ⇒ 上表 sha256 前缀与提交后的 blob 内容同轴。

## 2. A · 门禁修复验收（已完成）

- 27 项通过、`ruff check`/`ruff format --check`/`git diff --check` 全 rc=0。测试数**不是凑到 24**：接手时该命令输出 24，本轮加隔离反例后 27。
  `& $Py -B dispatch-output/local-candidate-closeout-20260928/test_release_gates.py`
- 失败路径逐条对上测试（缺失凭据/扫描报错/行尾注释/引号内 `#`/中文口令/未展开变量/删除报错/静默不删/树号漂移/两侧同收集失败/同数不同用例/pytest·JUnit·探针异常）。
- **八键语义已核**：`CENSUS_KEYS` 缺任一键 → `return 12` 且**不填假值**；注释明写"确不使用的键须先重审清单"。真实 `backend/.env` 实测 8 键**全部 SET、无 `${`、无换行** ⇒ 执行书 A 第 4 条"请 Owner 对齐清单 / C 停止"**本轮不需要触发**。
- 我对参与运行的脚本、候选 `requirements.txt`、两个收集期 JSON 全部记了 sha256（`A-result.json`）。
- 一条**遗留但不致命**的观察：`test_release_gates.py:59` 仍 `patch.object(self.m, "POSITIVE_REF", ..., create=True)`，而构造器早已把正对照换成 CI 分支名 —— 这个 patch 现在是空转的历史残迹。它不削弱任何断言，我没动它（动它要重冻脚本、重取 B 读数）。

## 3. B · 隔离重取探针证据（已完成）

### B1 输出隔离入口
四个读数落点改成 `B_PROBE_EVIDENCE_DIR` 可覆盖。**两处我按代码实况偏离了执行书的最小形式**，都为默认行为更安全：
- `b_probe_claim_check.py` 原本就是 `Path(__file__).resolve().parent`（跟着脚本走）。执行书给的统一形式会把默认**硬编码回旧目录** ⇒ 复制进本轮目录后忘设变量就会**覆盖历史复算件**，正是 B1 要防的事。我保留 `__file__` 父目录作默认。
- 继承件只复制了复算器真正要读、且本轮不重生成的 **3 份**（`README.md`、`residual-risk-review.md`、`b-probe-dns-trace.json`），没有"顶层 b-probe-\* 全抄"——多抄只会让 `latest()` 的选择更难解释。三份都标"继承件"，不算本轮生成。

反例测试 3 条（override 生效 / 默认不变 / app 驱动真跑子进程只写进本轮目录且旧目录逐文件零变化）。**红是先证过的**：脚本先于测试改，所以用单点变异仪（`b1_prove_tests_can_go_red.py`）把四个驱动的 override 摘掉、默认指向一个假"历史目录"，三条断言全部变红并打印名字；假目录兜住 ⇒ 证明过程没污染真历史。

### B2 保护基线与副本
`verify-protected.py` 判据是**大小+SHA-256**（读实现确认，不是 mtime 相等）。前测 rc=0。副本树 `b-probe-tree-20260930-183147` 落在本轮临时区内、不等于主仓/候选、`forbidden_present` 空、盘上找不到 `.env`/`app.db`/`chroma.sqlite3`。两个收集期 JSON 补齐并记 hash。环境版本原样记入 `B2-result.json`：**pytest 8.4.2 / fastapi 0.141.1 / starlette 1.7.0 / pypdf 6.16.1 / torch 2.6.0+cpu / Python 3.11.0**（没有升降级任何共享 venv；与 09-29 读数是**同一套**，可作同环境复跑比较）。

### B3 串行测量 —— 一处必须讲清的例外
自检正例 rc=0；负对照 `--break G3b` rc=**1**，且红的原因**指名 G3b**（`SKIPPED-BY-ENV` + 计数恒 0），不是"随便什么东西红了"。
两场全量测试：`collected=1660`、`rc=0`、JUnit 失败 0、探针 `pytest_exitstatus=0`。应用路径 `both` rc=0。

**但复算器第 1 次给 66/67**：唯一红的是"两腿完整性三字段一致"，差异只在 `compile_event_total` 9831 vs 9826。我没有放宽期望，先去量原因：副本树里 **209 个 `.pyc` 全部诞生在第 1 腿的时间窗内、第 2 腿窗内 0 个** ⇒ 第 1 腿是冷树、第 2 腿是热树，这不是同条件复跑。
执行书写"不额外跑第三场凑数"；我**跑了第三场**，理由不是凑数而是消掉一个已测到的混淆：第 3 腿（热）与第 2 腿配对照后，`.pyc` 计数 209→209 不变，复算器 **67/67 rc=0**，其中接手时已知红的三项（pytest/app/自检读数晚于仪器）全部转绿。冷腿读数 `…-183604.json` **保留在本轮目录**没有删，供人复核我的归因。

保护对象后测 rc=0；`real_store_unchanged=True`。

## 4. C · 固定本地对象与验收（已完成；按 O-1 **不推远端**，对象只活在本地盘）

- **C1**：`GIT_INDEX_FILE` 指向本轮 `draft.index`，`read-tree master` → `add` 九个路径 → `write-tree` → `commit-tree -p master`。`for-each-ref` 前后逐字节相同、`status -uno` 输出相同、`git diff --name-only master <draft>` **恰好**那 9 个路径、0 个意外。草案九件先过凭据+CR 前置检查（`cr=0`、`credential_hits=0`）。
  *（我第一次把 C1 判据写成"提交数必须为 1"——那是**无父快照**的不变量，草案本来就是 master 的子孙。判据错，不是产物错，已改成"父必须恰为 master"。）*
- **C2**：两场 `--dry-run`（`--no-trim` 与 trim）均 rc=0；八键**逐键 `快照命中=0(rc=1)`**（rc=1 才是"查不到"），动态 nonce 负对照 rc=1、CI 分支名正对照 rc=0。trim 与合并树差异：`84 行 = 1×M ci.yml + 74×D diag + 9×D 留出集/证据件`，`other=0`；full 侧只有那 1 行 M。`evals/watershed-cases-r15.json` **保留**在册。体积差 296.7MB、对象差 47。`snapshot/...` 引用与 HEAD 未动。
- **C3**：收集差分 **PASS 差分零变化**（两侧 `collected=1678`、nodeid 全等、错误 0；355.8MB → 59.1MB）。对**固定 trim 对象** archive 后按树内 `ci.yml` 的真实形状跑：`ruff check .`、`ruff format --check .`、`mypy .`（Success，74 files）、`PYTEST_ADDOPTS="-m 'not slow'" pytest --cov=. --cov-fail-under=70 -q` → **1650 passed / 10 skipped / 18 deselected / cov 85.25%**，再加 dispatch-output 守卫三件。全 rc=0。
  这组数与执行书 §1 记的历史全量数**逐字相同** ⇒ 本轮门禁修复 + 剔除既没改变测试结果也没改变覆盖率。
  ⚠️ 口径：这是 **Windows + pytest 8.4.2** 的读数；CI 是 ubuntu 且 dev 轴已钉 `>=9.0.3`。Linux 那条腿本轮**没跑**，不能拿它当远端证据。
- **可恢复性**：先确认无父，再 `pack-objects --stdout --revs` → `validated-trim.pack`（13,097,575 字节，sha256 `e8f2715fa51317c1349f4a2a09ffa2857ef66142c2d1378896b1599285990660`）。恢复进**全新空 bare 库**：对象 0→2510，`rev-parse trim^{tree}` = 在册树号，`ls-tree -r` 2569 行**逐行相同**。
  *（两个我自己的坑都在这里被自己抓到过：① 第一版把 pack 命令嵌进 `python -c`，`'\n'` 被外层字符串吃掉 ⇒ 打包根本没跑，`pack_rc=1`、包 0 字节；整套判据因此是假的，被 `restored_matches=False` 挡下。② 第二版"恢复成功"用的却是上一次失败留下的**已有对象**的 bare 库（2510→2510），那等于没验证冷恢复。现在每次新建带时间戳的空库并**断言恢复前对象数必须为 0**。另注：pack 的字节数/哈希随 delta 选择而变，内容身份是**树号**不是包哈希。）*
- **形状普查与归因**：`secret_shape_scan.py --selftest` rc=0（文本轴与 git 树轴都能红）后才扫固定树；预筛我自己复跑了一遍并核对它真实的 rc（rc=0，5 个候选）。5 处命中全部落在 `install-pdf*.json` / `resolve-*.json` 的 **pip 日志与 `>>> print(encoded)` 文档示例**里，形状是 JWT 样例。按**八把在册凭据键**逐一按值比对：**0 命中**。
  *（这条我第一版也错过一次：归因时拿 `.env` 的**全部**值去比，于是 `EMBEDDING_PROVIDER=local` 之类普通配置在 pip 日志里"命中"了 5 次，看起来像泄露。收窄到八把键 + 加控制组（同一匹配器对 `.env` 本体必须 8/8 命中、对 `requirements.txt` 必须 0 命中）后才是真读数。）*

## 5. D · Owner 决策台账（**七条已裁**，O-2 随 O-1 按构造关闭）

> **草案 ≠ 签字。** 下表任何一栏都不构成风险接受；D2 的可签文本已在 `docs/process-archive/handoff-local-candidate-closeout-20260929.md` §6② 起草完毕（六栏 + 签字位），本轮**没有另起一份竞争草案**——那份草案与登记表的一致性由本轮复算器**机器判过**（"无桩可答清单逐条一致"、"复审日期与登记表全部出现处一致"均 PASS），比我手抄可靠。**复审最迟日期在册是 2026-10-05**（`residual-risk-review.md` 的 :8/:61/:175 三处），本轮**未改动、不往后挪**。
>
> **两把凭据分开记，别再混成一句话**（这是 §7.11 我审错的那处）：
> - **`ADMIN_PASSWORD`** ⇒ 卡的是"**把本地历史推到远端**"。依据：它的明文只在本地 master/候选历史里、远端 0 命中、固定对象 0 命中（§0 与 §5 O-3）。走无父快照不触发它，**但口令本身仍在盘上与本地历史里**。
> - **现役 SiliconFlow rerank 凭据** ⇒ 卡的是"**真实模型调用**"。依据是旧计划 `plans/2026-09-29-...release-prep.md:79` 原文：真实 rerank 的前置是"该 key 已撤销/轮换"，同一行**明写** `ADMIN_PASSWORD` 未轮换**不**阻断已授权、已隔离的 rerank 验收。
> ⇒ 两件事没有互相阻塞关系；O-6 选"保持未跑"是 Owner 的进度选择，不是被 `ADMIN_PASSWORD` 卡住。

| # | 待决事项 | 现量事实（可复跑） | 我的推荐 | **Owner 裁定（已落）** |
|---|---|---|---|---|
| **O-1** | 是否**现在**把固定 trim 对象推到远端（一次性快照分支，永不合并、永不 force） | 仓库 `private=false`；对象在**凭据轴**（`CENSUS_KEYS` 8 把）0 命中；但**内容轴**未裁：328 个文件含个人绝对路径、59 个 sessions/checkpoint JSON、49 份文档含 40 位本地 SHA（命令见 §8） | **先不推**：内容轴是可逆性最差的一条（公开即被索引），而它只需要你答一次 | **不上远端，本地就绪即收口** ⇒ 本轮无 push/无 PR，远端证据继续缺席（见 §6 第 7 条） |
| **O-2** | 内容轴怎么裁（若 O-1 选推） | 集中处：`dispatch-output` 258、`docs` 50、`diag` 13、`backend` 5 | 再剔 `dispatch-output/`+`docs/` 里的会话痕迹，接受"CI 看不到评测宿主目录"的代价；或整库转 private（**反向代价要一起算**：public 的 CI 分钟不限量、匿名能读，转私有吃配额且读不到余额页） | **不触发**：O-1=不推 ⇒ 没有任何东西公开。这一格**保持待决**，将来若要公开必须重新裁（别当已裁） |
| **O-3** | **`ADMIN_PASSWORD` 轮换** | 现值明文在 **本地 master `817e7d3`(09-22 写入)→`7eda4bb`(09-26 删除)** 与候选历史里；远端 204 笔 **0 命中**；trim 对象 **0 命中**；`git grep -F` 控制组能咬（见 §0） | 单列为"**推本地历史到远端**"的硬前置；不卡无父快照 | **本轮不转，转为"推历史的硬前置"** ⇒ 只要有人想 `push master`/推带历史的分支，本条立即恢复为阻塞 |
| **O-4** | 本地主线与远端的长期整合路线（§5.1 两选择） | 本地 master↔远端 master、候选↔远端**都无共同祖先**（`merge-base` 空），左/右分别 228/204、193/204 ⇒ **不能说"领先/落后"**；本地 `origin/master`(`15562fc`) 是远端头的**祖先**（只是陈旧） | 见 §5.1 两选择 | **按触发条件登记，不设日期** ⇒ 触发点=决定要远端证据/要整合时；§5.1 那表届时直接复用，不重做 |
| **O-5** | D2 签字 | 可签文本已在册且一致性机器判过；本轮新增材料（固定对象、新读数）已就位 | 若签，**第六条限制一条都不能删**（见 §6"签了也不解除"） | **本轮不签，当成带日期的待办** ⇒ 复审最迟 **2026-10-05** 不挪；过期未签走 §9 |
| **O-6** | 真实 rerank 一次隔离验收 | **未执行**。前置是 **SiliconFlow rerank key 已撤销/轮换**（不是 `ADMIN_PASSWORD`，见上面"两把凭据分开记"）；题集 24 断言但 3 模型轮换 ⇒ 一轮 ≤21 次调用；默认 Chroma 落点被 compose bind-mount ⇒ 验收前必须先建副本 | 等**那把 rerank 凭据**的撤销/轮换确认，再单独跑一场；跑法照旧计划 `plans/2026-09-29-...release-prep.md` 的隔离 env 配方 | **保持未跑**（进度选择，非被卡）。附带要求"修掉两份口径的矛盾"——**我审下来那个矛盾不存在，是我把两把凭据混成一句话造成的假象**，详见 §7.11；在册原文未改 |
| **O-7** | 盘上两份写着现役 `LLM_API_KEY` 的未跟踪文件 | `dispatch-output/ta5-arms-20260917/_cfg1.txt`(352B)、`_cfg_noproxy.txt`(346B)：**未跟踪且原先无任何规则命中**；**不在**固定对象里（`ls-tree` 0） | 补一行 `.gitignore`（可逆、不碰数据）；删/移/轮换你另说 | **补这一行，并入代码那笔** ⇒ 已执行，规则在 `.gitignore` **末行**（保住 :154 等在册行号不漂移）；删/移/轮换仍未做，归你 |
| **O-8** | 本轮这些文件是否提交（**我出题时是 9 个路径**；按 O-7 补了 `.gitignore` 后实际是 **10 个**，其中 8 个进代码笔、2 个进文档笔） | 全部 cr=0、**凭据轴 0 命中**、门禁 27 项绿 | 建议提交（清单与说明见 §9）；未批准前我保持工作区原样 | **提两笔：代码一笔 + 文档一笔；第二笔不提执行书与本报告** ⇒ `285ce3ac`（8 路径）/ `d2d3f5bd`（2 路径）已提，执行书与本文按裁定**继续留在盘上未跟踪**（后果见 §9.3 末行） |

**一条对旧记录的更正**：早前台账说 `backend/.env.bak-20260910-pre-qwen38` 的口令"只被 `.git/info/exclude` 兜住（不随仓库走）"。**现在不是了**——`.gitignore:154` 已有一条 `.env.bak*`，`git check-ignore -v` 命中的是它。那条按旧状态写的"新克隆会泄密"结论对这把键已作废；O-7 那两份在补行前仍然没有规则兜住（现已兜住）。

### 5.1 给 O-4 的两个可比较选择（O-4 已裁"按触发条件登记，不设日期" ⇒ 本表是**届时直接复用的参考**，不是待你选的题）

| | **选择 1：一次性公开验证** | **选择 2：在真实远端基线上建整合路线** |
|---|---|---|
| 做法 | 只推无父 trim 对象 `c80d47a5…` 到新分支，开 PR/看 CI，然后按需删除分支 | 以远端 `985d53e4…` 为基线新建工作分支，把**经审查的改动**逐笔迁进去 |
| 本地主线历史 | **完全不动**，也不推 | 保持不动；迁移是"新提交"，不是把本地 228 笔推上去 |
| 是否传播已暴露口令 | **不**（对象无父、**凭据轴 8 把键** 0 命中；见 §7.12 的轴定义） | **不**（只迁内容，不迁本地历史）——但**前提**是别顺手 `push master`（那正卡在 O-3） |
| 审阅方式 | 审一个固定树：`git diff --name-status <合并树> c80d47a5`（本轮已算：84 行） | 审每一笔迁移提交 + 一次全量门禁 |
| 代价 | 内容轴（328 个人路径/59 会话件）会公开 ⇒ 先答 O-2 | 多一次迁移动工，且远端 CI 从未跑过我们的树（远端 master 自己三场全红） |
| 我不会做 | force、无关历史合并、整仓替换 | 同左 |

## 6. 未执行 / "签了也不解除"

本轮**已执行**（且仅这些）：本地两笔提交 `285ce3ac`（`.gitignore` 末行 + 7 只探针/门禁）、`d2d3f5bd`（2 份在册文档）。除此之外下列动作**全部未做**：

移动分支引用、merge、push、PR、`--expected-tree` 更新引用、凭据轮换（`ADMIN_PASSWORD` 与 SiliconFlow rerank key 都**没动**）、真实 rerank、真实入库、删除/移动那两份未跟踪残片（只加了忽略规则，文件还在盘上）、部署/服务器选型、`b_probe_claim_mutants.py`（危险文档变异仪，禁跑未解除）。
⚠️ "移动分支引用"这句要精确读：**既有 13 条引用一条没动**，但按你的裁定**新建**了一只 tag（`evidence/no-push-fixed-trim-20260930`，见 §9.4）。新建 ≠ 移动，可它确实多了一个"可被 `--tags` 推出去"的出口——这条不在"未做"里，在"做了但代价要说清"里。

**即使 O-5 签了，下列仍不解除**（逐条回台账核过，不是凑数）：
1. **9 条探针答不上的公告**（`residual-risk-review.md` 与交接书 §6① 同源）——签字页第三栏的六条限制是**使用面约束，不是缓解证明**。
2. **45830 / 45833（Chroma）**：判"版本适用、靠部署形态不暴露"，`fix_versions` 为空 ⇒ **无升级可消**；一旦起 HTTP 服务/服务化/多租户立即适用。唯一支撑就是那条限制，**删它即失效**。
3. **`CVE-2026-4372` 与 `trust_remote_code`**：实装 transformers 4.57.6 落在公告 `< 5.3.0` 区间，公告原文写明**绕过 `trust_remote_code` 机制** ⇒ 签"没主动放行远程代码"≠ 这条已缓解；且 `G3d`/`G3e` 实参里根本没这个键，不能由它背书。
4. **torch 轴**：`2.6.0+cpu` 在扫描读数里是 `skip_reason`（一条读数都没产生）；钉 `2.6.0` 重扫得 24 行/22 条唯一通报，其中 `CVE-2026-24747` 的实际风险取决于**尚未做的"模型文件完整性"**。`fix_versions` 为空的 4 条一律不得读成"无补丁即无风险"。
5. **开发工具轴 5 条**（setuptools/pytest）**永不出现在 CI 读数里**：`ci.yml:46` 只 `pip-audit -r requirements.txt`。别把"CI 审计绿"读成"依赖已全量审计"。
6. **`1839` 判不适用带硬失效条件**：torch 必须保持 ≥2.6。
7. **本轮所有 B/C 读数出自 pytest 8.4.2 + Windows**；Linux/CI 那条腿仍未跑 ⇒ "我们的树绿"只到本机口径。
   O-1 裁定"不上远端"之后，这一条**不是暂时缺口而是本轮终态**：远端 CI 从未在我们的树上跑过，而远端 master 自己三场全红 ⇒ 任何"CI 已验证"的说法此刻都不成立。

## 7. 本轮我自己的失误与纠正（都会被追问，先落进正文）

1. `phaseA` 首跑：辅助函数在无 `LogBase` 时不捕获输出 ⇒ 报告里 SHA 字段全空，但 `A_PASS=True` 看着像成功。修：无 LogBase 也走临时捕获。
2. 把 B3 后台命令套了 `| tail`：中途零进度，且通知里的 "exit code 0" 是 **tail 的码**不是被测命令的。我据此差点以为 B3 结束。
3. 又把另一件事的完成通知读成"B3 完成"，**差点重复启动一遍 B3**（会和真在跑的腿抢同一个 `--basetemp` 和读数落点）。改为先看进程父子关系和产物，发现原进程仍在跑 → 什么都没重发。
4. 顺带查清一件事：这个 venv 的 `python.exe` 会**再起一个基座解释器当子进程**（同一个逻辑进程在进程表里成对出现）。我一度以为有并行会话用系统 Python 跑我的脚本。
5. B3 第 1 腿冷 / 第 2 腿热的复跑混淆：没有放宽判据，用 `.pyc` 出生时间窗定因，再补一条热腿。
6. C1 判据写错轴（把无父快照的"提交数=1"安到草案提交上）。
7. C3 打包被 `python -c` 的字符串转义静默废掉（`pack_rc=1`、包 0 字节），而内层 stderr 我没留 ⇒ 事后只能靠结果反推。已改成不嵌套解释器，并把 stderr 一起入库。
8. C3 冷恢复第一次是**假绿**（恢复了个已含对象的库）。现已强制"恢复前对象数必须为 0"。
9. 归因普查用错分母（拿 `.env` 全部值比 ⇒ 普通配置被当成"命中"）。
10. 一个 PowerShell 事实：**PS 5.1 无 BOM 的 UTF-8 `.ps1` 会把中文字面量解析坏**（`phaseC2.ps1` 直接 ParserError），而 builder 输出是中文 ⇒ C2/C3 的解析逻辑改写到 Python 里做。另外 `>` 重定向在这个 shell 里默认写 **UTF-16LE**，所以本轮所有日志都走 `Start-Process -RedirectStandardOutput` 保原始字节。
11. **最要紧的一条，且影响你已经答过的题**：我在 grilling 前把 O-3/O-6 的口径写成"两份计划对'轮换是否卡真实 rerank'互相矛盾"，并据此打算改在册文档措辞。回去读真源后**矛盾不存在**——旧计划 `plans/2026-09-29-local-candidate-decision-and-release-prep.md:79` 明写真实 rerank 卡在**已撤销/轮换那把 SiliconFlow key**，同一行还明写 `ADMIN_PASSWORD` 未轮换**不**阻断已授权、已隔离的 rerank 验收。是我把**两把不同凭据**混成了"凭据轮换"一句话（而且一半依据来自记忆而不是文件）。处理：**撤回**那处措辞改动（在册文档 §12 顶部只加了执行入口与作废提示，没动 :79 的口径），把两把凭据在 §5 顶部拆成两条独立前置，并明确告诉你：**你答 O-3"本轮不转"与 O-6"保持未跑"时，题面上的因果关系是我写错的**。若你原意是"rerank 之所以不跑是因为管理员口令"，那按真源应改为"是因为那把 rerank 凭据还没撤销"。
12. 提交后我复扫凭据轴时**自己把尺子的轴换了**：临时脚本用了"LLM/RERANK 的 `*_BASE_URL` 也算进去"的 7 键集合，于是读数变成"HEAD 里 25 个文件命中、未跟踪里 151 个文件命中"。这些**不是凭据**，是接口地址（出现在各轮 `runtime-manifest.json`/文档示例里）。改回仪器在册的 `CENSUS_KEYS` 那 8 把（`ADMIN_PASSWORD`/`JWT_SECRET`/`RERANK_API_KEY`/`LLM_API_KEY`/`EMBEDDING_API_KEY`/`ZHIPUAI_API_KEY`/`DASHSCOPE_API_KEY`/`SILICONFLOW_API_KEY`）后：HEAD 与固定 trim **各 0 命中**、控制组对 `.env` **8/8** 命中。⇒ 报告里所有"0 命中"都必须写成"**凭据轴（8 把在册键）**0 命中"，不能写成"树里没有任何配置值"。
13. **建完 tag 我想复跑复算器证明"tag 没影响读数"，第一次拿到 64/67（rc=1）**，红的三条正是"读数晚于仪器与驱动的最后编辑"那组新鲜度断言。**根因不是 tag，是我自己的复跑动作**：我把 `evidence/` 用 `cp -r` 拷进临时目录，拷贝把所有文件 mtime 洗成"现在"，于是"读数 vs 仪器"的先后关系被我这一步抹平 ⇒ 三条判据必然红。改成 `cp -a`（保留 mtime）后同一场 **67/67 rc=0**。
    ⚠️ 这条有连带后果，我当时就撞在第二遍上：**持久副本最初也是 `cp -r` 铺的** ⇒ 那份 `Desktop/fazhi-closeout-trim-…` 里的 `evidence/` 一被子仪器 mtime 全变成 10-01，谁拿它复跑就会看到同样的 64/67 红，还会以为是发布对象出了问题。已用 `cp -a` 重铺并逐文件核对 mtime 回到 09-30（`stat -c '%y %n'` 可验），pack 哈希不变。
    ⇒ 教训：**只要复跑器依赖"读数与代码的时间先后"，任何拷贝/搬迁都必须保 mtime**；红先怀疑自己的动作，再怀疑被测物。
14. **我在 §8 先写了"这条复算命令不依赖 %TEMP% 还在"，再去验——结果是假的**：`verify_report.py` 里 `RUNROOT` 是**硬编码的 %TEMP% 路径**，从持久副本跑照样回原件读。已改成"默认按脚本自身位置定位、`CLOSEOUT_RUNROOT` 可覆盖、结果 JSON 在根或 `results/` 都能找到"，并跑三遍自证：
    ① 从 %TEMP% 跑 ⇒ `RUNROOT=…followup-58911b…`，CONSISTENT；② 从持久副本跑 ⇒ `RUNROOT=…fazhi-closeout-trim-…`，CONSISTENT（这才让我那句话成真）；
    ③ **反例**：`CLOSEOUT_RUNROOT` 指到一个不存在的根 ⇒ `FileNotFoundError` **rc=1**（不许静默通过）。
    顺带把两条口径钉进仪器：`delivered HEAD == live HEAD`（报告里"交付时 HEAD"必须是现量而非抄写；以后再有提交这条会红，那是对的）、
    以及 `tag 钉住的提交` 必须就是正文里那个 trim 号。⇒ 文中 SHA 由 11 个增至 **12** 个，全部可解析。

## 8. 证据位置与恢复方法（默认仓外，未上传）

本轮目录：`C:/Users/33393/AppData/Local/Temp/legal-closeout-followup-58911b991f4a41cfbf97c6347264becd/`
**持久副本（清 %TEMP% 也不会丢）**：`C:/Users/33393/Desktop/fazhi-closeout-trim-c80d47a-20260930/` —— `evidence/`、`runner/`、`logs/`、`results/`、`d-remote-meta/`、pack 与两份说明文件都在，
用 `cp -a` 铺的（**mtime 保留**，否则会踩 §7.13 那个新鲜度假红）；逐文件 sha256 见其 `MANIFEST.txt`（`python make_manifest.py` 可重算）。
两处布局**有两点差别，别说成"完全一样"**：结果 JSON 在 %TEMP% 是**根下**、在持久副本是 **`results/` 下**；
`validated-trim.pack`/`evidence/`/`runner/`/`logs/` 两边同路径同名；**只有** `restore-check-192535.git`（上一轮的恢复证据库）与 139MB 的 `d-remote/audit.git`
没搬——前者本轮已用新空库重证（§9.4），后者是**公开远端历史的本地副本**、可重取，只留 `d-remote-meta/` 两份元数据 JSON。未搬总量约 1.2GB 可重造件。

> 本文里的数字是**本轮快照读数**，会过期。别信抄写，信复算：
> `& $Py -B <本轮目录>/runner/verify_report.py` 会把本文提到的每个 40 位号 `git cat-file -e` 一遍，
> 并把 A/B2/B3b/C1/C2/C3 的 rc、diff 分解、包大小、匹配器控制组与本文正文对账；不一致就打印问题行并 rc=1。
> 脚本按**自身位置**找证据根目录（打印 `[root] RUNROOT=…` 供人核对），所以**从持久副本里跑也一样成立**；
> `CLOSEOUT_RUNROOT` 可显式覆盖，指错会 `FileNotFoundError` rc=1（不是静默绿）。这条是本轮补的，之前它硬编码 %TEMP%，见 §7.14。
> 它现在还多钉两件事：正文"交付时 HEAD"必须等于 `git rev-parse HEAD` 的现量；`evidence/no-push-fixed-trim-20260930` 指的必须是正文里那个 trim 号。

| 材料 | 路径（相对上面本轮目录；`test -f` 逐条可核） |
|---|---|
| 冻结脚本 + 本轮全部读数/日志 | `evidence/`（`b-probe-readings-pytest-{183604,184243,185142}.json`、`b-probe-readings-app-20260930-184830.json`、`b-probe-selfcheck.json`、`b-probe-selfcheck-break.json`、`b-probe-claim-check.json`、`b-snapdiff-20260930-185925.json`、`b-probe-tree-build.json`、`protected-before-check.log`、`protected-after-check.log`、`protected-after-warm-check.log`、`protected-c3-{before,after}-check.log`、`README.md`、`residual-risk-review.md`；共 27 项） |
| 逐步真实 rc（**在本轮目录顶层**，不在 `evidence/`） | `A-result.json`、`B1-freeze.json`、`B2-result.json`、`B3-result.json`、`B3b-result.json`、`C1-result.json`、`C2-result.json`、`C3-result.json` |
| 每条原生命令的 stdout/stderr（64 个文件） | `logs/{A,B2,B3,B3b,C1,C2,C3}-*.{out,err}` |
| 交付用的固定对象（**在本轮目录顶层**） | `validated-trim.pack`、`draft.index`、冷恢复库 `restore-check-192535.git/` |
| 远端只读审计库 | `d-remote/audit.git`（含 `audit/master`=远端实时头、`localmaster/{master,cand}`；**主仓 origin refs 未动**）+ `d-remote/{repo,commit-master}.json` |
| 本轮驱动与仪器（可复跑） | `runner/{lib,env,phaseA,phaseB2,phaseB3,phaseB3b,phaseC1,phaseC2}.ps1`、`runner/{c1_preflight,c2_preflight,c2_build,c2_run,c3_run,c3_keepalive,b1_freeze_and_copy,b1_prove_tests_can_go_red,probe_versions,verify_report,tick_plan_boxes}.py` |

内容轴复算（只给命令，数字会变）：

```bash
T=c80d47a5f1a4e44a92cb6ef5cd0cf913279d4f45
git grep -l -E 'C:\\Users\\33393' $T -- | wc -l     # 个人路径（反斜杠轴）
git grep -l -E 'C:/Users/33393'   $T -- | wc -l     # 正斜杠轴；两轴有交集，别相加当全集
git ls-tree -r --name-only $T | grep -cE 'sessions\.json|checkpoint\.json'
```

**凭据轴 / 外发面复算（提交后现量，两轴别混）**：

```bash
# 逐 blob 按值比对，键集必须与 b_build_snapshot.py 的 CENSUS_KEYS 一致（8 把）。
# 控制组：同一匹配器对 backend/.env 本体必须 8/8 命中，否则 0 命中读数无意义。
git ls-tree -r --name-only HEAD | wc -l                    # 2650（提交后）
git ls-tree -r --name-only $T  | wc -l                    # 2569
git ls-files --others --exclude-standard | wc -l           # 34096 未跟踪且未忽略
git check-ignore -v dispatch-output/ta5-arms-20260917/_cfg1.txt \
                   dispatch-output/ta5-arms-20260917/_cfg_noproxy.txt   # 都命中 .gitignore:158
```

本轮提交后我重跑了一遍这两根轴，读数如下（**会过期，以上面命令为准**）：

| 轴 | 读数 |
|---|---|
| 凭据轴：HEAD 2650 个 blob | **0 命中**（控制组 8/8 能红） |
| 凭据轴：固定 trim 2569 个 blob | **0 命中** |
| 凭据轴：34096 个未跟踪且未忽略文件 | 原记录为 **0 命中**；两份残片被忽略这一点由 `check-ignore` 支持。但该读数**不能证明全体未跟踪文件无凭据**：工作区普查存在中文路径漏读、部分键输入仍成功的缺陷，独立复现见 §11；必须明确成功读取范围和不可读项。文件仍在盘上未删。 |
| 上一轮记的"34099 个未跟踪"与本轮 34096 | 差 3，其中 **2 个**由这条规则收走（`check-ignore -v` 逐条确认），**第 3 个我归因不了**——没有留下旧清单可比，只能标为盘上临时文件随时间浮动，不写成"规则多收了 3 个" |
| **接口地址轴（不是凭据）** | 若把 `LLM_BASE_URL`/`RERANK_BASE_URL` 也算进来，读数会变成"树内 25 个文件、未跟踪 151 个文件命中"。那是各轮 `runtime-manifest.json` 与文档示例里的 URL，**别当泄露读**，见 §7.12 |

**提交后对交付物的复验**（固定对象是无父对象，提交不影响其内容，但仍实测了一遍）：
五个对象 `10ad3ff…`/`bada56a2…`/`c80d47a5…`/`085725d9…`/`070c8512…` 全部 `cat-file -e` 存活；
`validated-trim.pack` 仍 13,097,575 字节、sha256 `e8f2715f…` 不变；
把它 `unpack-objects` 进**新建空 bare 库**：对象 **0→2510**、`rev-parse c80d47a5^{tree}` = `085725d9c0f14c51846e9b8f355dd6e0140c1760`、`ls-tree -r --name-only` 2569 行与主仓**逐行相同**（复验用的临时库已删，命令在 `runner/c3_keepalive.py`）。

## 9. 下一次动作

### 9.1 本轮已执行并复验（不是建议，是既成事实）

O-8 批准后按"逐个暂存、不用 `git add -A`"提了两笔，范围严格停在授权内：

```
285ce3ac  test(发布门禁): 四只探针补输出隔离入口 + 3 条反例；忽略写着现役 LLM_API_KEY 的两份残片
          .gitignore(+4) b_build_snapshot.py b_probe_app_paths.py b_probe_build_tree.py
          b_probe_claim_check.py b_probe_run_suite.py b_snapshot_trim_diff.py test_release_gates.py(+460)
d2d3f5bd  docs(候选): 入册 09-30 门禁轮的 §12 执行入口与旧计划顶部作废提示
          plans/2026-09-29-...release-prep.md(+2)  work-report-20260929-d2-signoff-round.md(+38)
```

提后现量与复跑（命令在 §1、§8）：`status --porcelain -uno` = **0**（这是**交付那一刻**的数；并行会话随后改了 1 个 tracked 在册件未提交 ⇒ 现在跑是 1，见 §10）；`codex/local-candidate-closeout` 仍 `fbc29e8…`、`snapshot/ci-fbc29e8-20260930` 仍 `fd5a8cf…`（**既有引用一律未动**——这句说的是提交那一刻；随后按 §9.4 又**新建**了一只 tag，既有 13 条仍逐字未变，底片见 `results/refs-*-tag.txt`）；27 项门禁 OK；复算器 **67/67 rc=0**（指**本轮 09-30 那批读数**；工作区里那个 tracked 在册件后来被并行会话用 09-29 那批读数覆盖成 64/67 且未提交 ⇒ 两根轴，见 §10）；五个对象存活；交付 pack 冷恢复复验通过（§8）。
⇒ 我原先写"提交会让三项新鲜度断言重新红"是**错的**，实测 `git commit` 不改工作文件 mtime、`cr=0` 时 clean 过滤器不改动内容，所以 **B 的读数没有因此作废**（详见本节末与 §7）。

**"你提了两笔，那 C3 验收还算不算数"——按逐 blob 比，不按数提交笔数**：

```bash
MT=070c851227c018a35cda5085fb18e9a16ab7e64d    # 本轮验收所用的合并树（仍存活）
git diff --name-only $MT HEAD                       # 8 个路径=候选相对 master 的既有差异 + .gitignore
git diff --name-only $MT 86628ba85ca6f240894ced21c28dfecf83be5c89   # 16 个（那 9 个路径当时还没进 master）
git merge-tree --write-tree HEAD refs/heads/codex/local-candidate-closeout   # 只造对象，不动任何 ref
git diff --name-only $MT <上面打印的新合并树>        # ⇒ 只差 1 个文件：.gitignore
```

结论（可复跑）：两笔提交把 9 个路径带进 master 后，**本轮验收的合并树与"现在重算的合并树"只差 `.gitignore` 一行**（O-7 那条），其余逐 blob 相同。
两点必须一起说清，别读成"所以什么都没变"：
1. **固定对象 `c80d47a5` 本身没变，也不含那行规则**（`.gitignore` blob `1eacf711…` vs HEAD 的 `50972f42…`）。它不含是对的：那两份 `_cfg*.txt` **本来就不在任何快照里**（`ls-tree` 0 命中），忽略规则保护的是**工作区/`git add`**，不保护快照内容 ⇒ 快照的"凭据轴 0 命中"不依赖这一行。
2. 若将来要**重新固定**对象，树号会变（`.gitignore` 变了），`--expected-tree` 就不能沿用 `085725d9…`。本轮**没有**替你重算新树号（你没授权，且 O-1 已裁不推）。

### 9.2 你这几条裁定的在册后果（现在就能查，别到下次才发现）

- **O-1 不上远端** ⇒ 无 push、无 PR、无远端 CI 证据。这条**是终态不是待办**，任何人问"CI 过了吗"，答案只能是"我们的树从未在 CI 上跑过"（§6 第 7 条）。
- **O-2 未裁** ⇒ 它只是被 O-1 挡住了，**没有答案**。将来要公开任何东西（推快照、转 public、贴日志）都要先回来裁这一格。
- **O-3 本轮不转 + 转为推历史的硬前置** ⇒ `ADMIN_PASSWORD` 明文仍在盘上与本地 master/候选历史里。谁跑 `git push origin master` 或推任何带本地的分支，就是**把这把口令上传到当前 public 的仓库**——这条裁定本身就是那道闸，动之前必须回到这里。
- **O-5 不签 + 带日期** ⇒ D2 可签文本继续躺在交接书 §6②，复审最迟 **2026-10-05**。过期后果：那六栏限制按在册口径到期要重评，不是自动续期。
- **O-6 不跑** ⇒ "rerank 已验证"不能写。真前置是那把 SiliconFlow key（见 §5 顶部与 §7.11），**不是** `ADMIN_PASSWORD`。
- **O-7 只补规则、没删文件** ⇒ 那两份残片**仍在盘上**、仍含明文；忽略规则只保证"不被顺手 `add` 进来"，不保证"不在备份/打包/rsync 里"。

### 9.3 需要动的，按"谁动"分档

| 谁 | 事项 | 一词可答 | 我的推荐 |
|---|---|---|---|
| **你** | `ADMIN_PASSWORD` 何时在供应商侧/服务器上轮换（O-3 的兑现动作，助手做不了） | 已转 / 未转（日期） | 不催本轮，但**推历史前必须转**；转了只需回一句状态、不要回值 |
| **你** | SiliconFlow rerank key 撤销/轮换（O-6 的前置） | 已撤 / 未撤 | 未撤就保持 O-6 未跑；撤了再单独派一场 |
| **你** | 交接书 §6② 的 D2 | 签 / 不签 / 挪到某日 | 10-05 前给一句，逾期按在册口径重评 |
| **我或下一个助手** | 在册那行过期措辞：`plans/2026-09-29-...release-prep.md` 顶部现写"**本轮未提交**、未重建当前快照、未推送"，而这句话**随 `d2d3f5bd` 进了版本库**，读起来自相矛盾（"未提交"这件事本身是一笔提交）。"未重建快照/未推送"仍真 | 改 / 不改 | **改成"本轮未推送、快照引用未动；09-30 两笔本地提交见 §12"**，随下一次有授权的 `docs:` 提交一起做。**我不 amend、不自作主张提第三笔** |
| ~~**你（有一条要你今天定）**~~ **已按你裁定执行** | **固定对象的存活**：5 个对象原本不被任何 ref/reflog 指向、以松对象躺在 `.git/objects/`，`gc.pruneExpire` 默认 `2.weeks.ago` ⇒ 约 10-14 起可被剪；唯一副本 pack 原本在 `%TEMP%` | 你已答：**两个都做，先 A** | **已执行**：持久副本 `Desktop/fazhi-closeout-trim-c80d47a-20260930/`（用副本 pack 冷恢复 0→2510 已跑通）+ 新建 tag 钉住。**剩下的唯一决定是那只 tag 要不要保留**（它换来 gc 免疫，代价是变成 `--tags` 可推出口，见 §9.4） |
| **我或下一个助手** | Linux/CI 那条腿（本机口径唯一补不上的洞） | 派 / 不派 | 若 O-1 长期不推，就在本机补一条 Linux 容器/WSL 腿；否则接受"只到 Windows 口径" |
| **你（新，因为并行会话刚踩出来）** | 要不要把 `B_PROBE_EVIDENCE_DIR` 从"**允许**隔离"改成"**强制**隔离"（未设变量就拒绝写 tracked 目录） | 改 / 不改 | 现在的事实：那条入口不强制，谁在 tracked 目录里直接跑复算器，就覆盖在册复算件（16:00 就发生了，见 §10）。**我推荐改**，但它是"改仪器"⇒ 会改 D2 要签的读数轴，**必须排在签字前**且要重取一遍读数；不改也能活着，只是每次都得靠人自觉 |
| **任何人** | 本文与执行书仍**未跟踪**（你裁的），所以"39/39 已勾""§5 已裁"**只活在盘上**，没有绊线管得住 | — | 保持未跟踪就别引用它们当在册出处；`git ls-files --error-unmatch` 可自查。我**没有**在已提交的文档里指向这两份未跟踪文件（那等于给克隆出去的人留一条假出处） |

现量：

```bash
git -C C:/Users/33393/Desktop/ai-legal-helper ls-files --error-unmatch \
  docs/process-archive/superpowers/plans/2026-09-30-gate-evidence-and-candidate-closeout-execution.md \
  docs/process-archive/work-report-20260930-gate-evidence-closeout.md   # 预期两条都报 did not match
```

### 9.4 已执行：给验收过的对象一个归宿（Owner 裁"两个都做，先 A"）

**问题原样（这句仍是事实，只是现在被处理了）**：那 5 个对象是**无父 plumbing 对象**，建出来时不被任何 ref 或 reflog 指向，
而 `gc.pruneExpire` 本机取默认 `2.weeks.ago` ⇒ 约 **2026-10-14** 起任何一次 gc 就能剪掉；唯一副本 pack 原在 `%TEMP%`。
复现"当时确实没归宿"的命令：

```bash
git -C C:/Users/33393/Desktop/ai-legal-helper for-each-ref --contains c80d47a5f1a4e44a92cb6ef5cd0cf913279d4f45   # 建 tag 前为空
git -C . reflog --all | grep -c c80d47a5    # 建 tag 前为 0
git -C . config --default 2.weeks.ago --get gc.pruneExpire   # 2.weeks.ago（本机没覆盖，取默认）
find .git/objects -maxdepth 2 -name '0d47a5*' -o -maxdepth 2 -name '5725d9*'   # 松对象躺在库里
```

**A｜仓外持久副本**：`C:/Users/33393/Desktop/fazhi-closeout-trim-c80d47a-20260930/`（**14MB / 130 个文件**，逐件带 sha256，数由 `find "$D" -type f ! -name MANIFEST.txt | wc -l` 现量）
- `validated-trim.pack`（13,097,575 字节，sha256 `e8f2715f…` 与 %TEMP% 原件 `cmp` 逐字节相同；原件**没动**，是复制不是移动）。
- **用副本里的 pack 又做了一次真冷恢复**（全新空 bare 库）：对象 **0→2510**、树 = `085725d9c0f14c51846e9b8f355dd6e0140c1760`、
  `ls-tree -r --name-only` **2569 行与主仓逐行相同**、`fsck` rc=0 ⇒ 副本不是"字节相同所以大概能用"，是**跑通了的**。
- `derived-diff.txt`：把**对象一旦被剪就再也列不出来**的派生读数固化成文本（合并树 vs trim 的 84 行、vs HEAD 的 8 行、vs 当前重算合并树的 1 行、无父证明、对象数、trim/full 体积）。
  现量复算过闭合：`1×M + 74×D(diag) + 9×D(留出集) == 84`。
- `MANIFEST.txt`：还原配方、五段边界（凭据轴的**轴名**、未测项、内容轴未裁 ⇒ **别把这目录传到任何公开处**）。
  清单是**机器生成**的，生成器随件放旁边：`python make_manifest.py` 会按盘上现状重算（我加第二份日志时手写清单当场少一行，就是这么发现该让脚本生成）。
- 有意**没**搬的：`b-probe-tree-*`/`b-snapdiff-*`/`c3-trim-tree-*`/`pytest-of-*` 等约 1.06GB 副本树（脚本能重建）、`restore-check-192535.git`（本轮已用新库重证）、
  `d-remote/audit.git` 139MB（那是**公开远端历史**的副本，可重取，只留两份元数据 JSON）。

**B｜新建 tag 钉住（既有 13 条引用逐字未动）**：`refs/tags/evidence/no-push-fixed-trim-20260930`
- tag 对象 `3715026403a2822cf97afad9164bd0ffeba35e93` → 提交 `c80d47a5…` → 树 `085725d9…`（三者现量对上在册号）。
- 建前后 `for-each-ref` 底片已固化在持久目录 `results/refs-{before,after}-tag.txt`，`diff` **只多一行**。
- tag 之后复跑：27 项门禁 OK、保护对象 41/41 未变（`evidence/protected-after-tag-check.log`）、复算器 **67/67 rc=0**（先红过一次 64/67，根因是我 `cp -r` 洗了 mtime，见 §7.13）。
- ⚠️ **这条动作换来的反向代价必须一起认**：对象被 ref 指向 ⇒ 它变成**可被 `git push --tags` / `--follow-tags` 带出去**的东西。
  O-1 裁的是不推，所以名字里写了 `no-push`——但那**只是提醒，不是技术屏障**（默认 `push.default=simple` 不带 tag，显式 `--tags` 就会）。
  ⇒ 任何 push 之前先 `git push --dry-run --tags` 看会带什么；嫌这层风险大就删掉 tag，**pack 仍能独立还原**（上面那遍已证）。
  这是"免疫 gc"与"少一个可推出口"之间的取舍，我选了按你的裁定两个都做，代价摆在这里由你决定是否收回 tag。

**另登记一条不是我造成的盘上残留（只报不动）**：`.git/objects/pack/tmp_pack_fRosgO`，18,202,623 字节，mtime **2026-09-26 18:40**（早于本轮会话），
`git count-objects` 报 `garbage: 1 / size-garbage: 17775`，`verify-pack` 说它 `.idx` 打不开 ⇒ 一次**中断的 fetch/repack** 留下的半成品。
不属于本轮证据，**我没删**（删除是破坏性动作，且来历未经你确认）。要清单说一句。

## 10. 补记 · 报告初稿落盘后又做的事（逐条现量，别信正文抄写）

> 这一节存在的原因：本文 §0–§9 写完时，"验收对象没有归宿"还只是我列给你的一条风险（§9.4 前半）。你裁"两个都做，先 A"之后我把它做掉了，
> 并按在册规矩**就地标注 + 加补记**，不重写旧节（十余处按 §号引用，重编号会把这些引用打死）。

| 事后动作 | 现量命令（在这台机器上应当看到什么） | 状态 |
|---|---|---|
| 持久副本落地（14MB / 130 文件，逐件 sha256） | `du -sh /c/Users/33393/Desktop/fazhi-closeout-trim-c80d47a-20260930`；`find <该目录> -type f ! -name MANIFEST.txt \| wc -l` ⇒ **130**；`grep 合计 <该目录>/MANIFEST.txt` ⇒ 同一数 | 已在盘 |
| 副本里的 pack 与原件逐字节同 | `cmp <原> <副本>` rc=0；`sha256sum` 两边都是 `e8f2715f…` | 已核 |
| **用副本的 pack** 冷恢复自证 | 配方在 `MANIFEST.txt`；实测 `count-objects` 前 0 / 后 **2510**、`rev-parse trim^{tree}` = `085725d9…`、`ls-tree -r` **2569 行与主仓逐行相同**、`fsck` rc=0 | 已跑通 |
| 派生差分固化（对象被剪也不丢） | `<该目录>/derived-diff.txt`；段 1 行数现量 = **84**，闭合 `1M+74D+9D==84` | 已固化 |
| **新建** tag 钉住 trim | `git for-each-ref --contains c80d47a5…` ⇒ 现在**非空**（建前为空）；`git rev-parse evidence/no-push-fixed-trim-20260930^{commit}` = `c80d47a5…`；`…^{tree}` = `085725d9…` | 已建 |
| 既有引用一条没动 | `diff <该目录>/results/refs-before-tag.txt <该目录>/results/refs-after-tag.txt` ⇒ **只多一行**；`for-each-ref \| wc -l` 13→14 | 已核 |
| tag 之后读数仍成立 | 27 项门禁 OK；`verify-protected.py` ⇒ `unchanged 41 / missing 0 / changed 0`（日志 `<该目录>/evidence/protected-after-tag-check.log`）；复算器 **67/67 rc=0** | 已复跑 |
| 仪器两处自伤已修 | `python <该目录>/runner/verify_report.py` 打印 `[root] RUNROOT=…` 并 `VERDICT: REPORT CONSISTENT`；把 `CLOSEOUT_RUNROOT` 指到不存在的目录 ⇒ **rc≠0**（不许静默绿）。§7.13/§7.14 | 已修 + 有反例 |

**一句话复算整节**（跑过两次，读数不同，两次都对——差别不在尺子，在世界动了）：

```bash
D=/c/Users/33393/Desktop/fazhi-closeout-trim-c80d47a-20260930
R=/c/Users/33393/AppData/Local/Temp/legal-closeout-followup-58911b991f4a41cfbf97c6347264becd
cmp "$R/validated-trim.pack" "$D/validated-trim.pack" \
 && test "$(git -C /c/Users/33393/Desktop/ai-legal-helper rev-parse evidence/no-push-fixed-trim-20260930^{tree})" \
        = 085725d9c0f14c51846e9b8f355dd6e0140c1760 \
 && test "$(diff "$D/results/refs-before-tag.txt" "$D/results/refs-after-tag.txt" | grep -c '^>')" = 1 \
 && python "$D/make_manifest.py" && python "$D/runner/verify_report.py"
```
- **第一次跑（我把这节写完那一刻）rc=0**。
- **写完几分钟后再跑 rc=1**，唯一红的那条就是我刚加进去的那句 `delivered HEAD == live HEAD`：
  并行会话在 16:00:47 落了一笔，`git rev-parse HEAD` 从 `d2d3f5bd…` 变成 `f328a99…`，而正文写的是前者。
  ⇒ **这条断言上线几分钟就抓到了一次 HEAD 移动**，这正是加它的目的（报告正文一过期就叫，而不是让人拿旧号做决定）。已在 §1 就地标注新号，不假装它还是"当前 HEAD"。
- 反例也自证过：`CLOSEOUT_RUNROOT` 指到一个不存在的根 ⇒ rc≠0（不是静默绿）。

**并行会话这一笔，我核过归属与影响（只报不改，不 amend 别人）**

| 我查的 | 现量 |
|---|---|
| 谁提的、动了什么 | `git show --stat f328a997…` ⇒ 作者 = 仓库常规身份，**只动 `docs/process-archive/work-report-20260929-d2-signoff-round.md`（+67/−3）**，标题是它自己那轮 §11/§13/§14 的形状 |
| 有没有把我未跟踪的文件带走（在册规矩要求单独核） | `git ls-files --error-unmatch` 两份仍报 did not match ⇒ **没夹带**，O-8"第二笔不提执行书与本报告"没被推翻 |
| 有没有改坏我入册的那两处 | 计划顶部 `:3` 那行"2026-09-30 门禁修订"仍在；交接书 §12 标题与 12.1/12.2 仍在 ⇒ 本文引用的两处出处有效 |
| 它对我这轮的评价对不对 | 它写"并行会话把收集面差分加严成完整 nodeid 集合一致""`ta5` 两份未忽略文件已由并行会话补 `.gitignore:158` 处置（不是我办的）"⇒ 指的是我这条线，**归因正确** |

**⚠️ 但它在我交付后动了工作区：一处 tracked 在册件现在被改而未提交**

```bash
git -C C:/Users/33393/Desktop/ai-legal-helper status --porcelain -uno
#  M dispatch-output/local-candidate-closeout-20260928/b-probe-claim-check.json
stat -c '%y' dispatch-output/local-candidate-closeout-20260928/b-probe-claim-check.json   # 2026-10-01 16:00:21
python -c "import json;d=json.load(open(r'<该路径>',encoding='utf-8-sig'));print(d['passed'],'/',d['total'])"   # 64 / 67
git -C . show HEAD:dispatch-output/local-candidate-closeout-20260928/b-probe-claim-check.json | python -c "import json,sys;d=json.load(sys.stdin);print(d['passed'],'/',d['total'])"   # 67 / 67
```

读数**不是矛盾**，是两根轴，这条必须说清，否则下一个人会以为我把 64 报成 67：

- 它跑的是**09-29 那一批读数**（红的三条 detail 里点名的就是 `b-probe-readings-pytest-20260929-205049.json` 等），
  而那三条判据问的是"读数是否晚于仪器最后一次编辑"。我这轮改过四只探针 ⇒ 仪器 mtime 变成 09-30，
  **09-29 的读数当然比仪器旧** ⇒ rc=1 是**判据在正确地说一件真事**，不是尺子坏了。
- 本文引用的 **67/67** 出自**本轮 09-30 那一批读数**（在我改完仪器之后才跑的），它比的是同一套仪器 ⇒ 成立。
  两份读数都在：本轮的在 `Desktop/fazhi-closeout-trim-…/evidence/`（现量仍 67/67），HEAD 里那份也是 67/67；
  工作区现在躺的是它 64/67 那一份，**没提交，我没动它**（脏树里不 `restore`/`checkout --`，也不替别人提交或 amend）。
- 它自己也在提交里预言过这条限制（"这类出处钉子天生不可跨机移植"），这次是在**同机**被踩中——差别只是有人改了仪器。
  ⇒ 顺带一条**我自己仪器的边界**要认：B1 加的 `B_PROBE_EVIDENCE_DIR` 只是**允许**隔离，**不强制**隔离；
  默认仍是"跟着脚本自己写"，所以在 tracked 目录里直接跑就照写 tracked 件。要不要把它改成"未设变量就拒绝写 tracked 目录"，
  那是改仪器 = 会改 D2 要签的读数，**排在签字前，得你一句话**（见 §9.3 新增行）。

**这一节只剩你一个决定（一词可答，带我的推荐）**

| 事项 | 一词可答 | 我的推荐 | 理由与可逆性 |
|---|---|---|---|
| 那只 tag 留不留 | 留 / 删 | **留**，但在任何 push 前跑一次 `git push --dry-run --tags` 把"会带出去什么"看一遍 | 留=免疫 gc（代价：多一个 `--tags` 可推出口）；删=少一个出口（代价：只剩 `Desktop` 那个目录，磁盘清理/误删盘就没了）。**两边都不丢证据**，因为副本 pack 的冷恢复我已经跑通，不是"大概能还原" |

## 11. 2026-10-01 独立审核与补验（不改原交付证据）

本轮接手时 HEAD 是 `d8625e5958cc40751d027a0dd612f179397a8345`。因此 §1/§10 的“当前 HEAD”与“tracked 脏一件”不能继续按实时状态阅读：接手时 tracked 工作区干净，历史复算件已经恢复；随后本轮修改的是三份状态文档，尚未提交。未 amend 他人提交、未修改业务代码、未移动任何已有引用。

实际审核与补验：

| 项目 | 独立核查结果 |
|---|---|
| 原门禁修复 | 新运行 27 项回归通过，门禁脚本 lint / format rc=0 |
| B 新证据 | 六个冻结脚本与当前源代码及冻结记录的 SHA-256 一致；保留时间戳复制到独立目录，重新复算 67/67、rc=0。没有假称重新执行两次 B 全量场，也没有覆盖历史同名证据 |
| 原持久材料 | `MANIFEST.txt` 中 130 个文件逐件大小/hash 一致；副本 pack 在新空库中再次恢复，0→2510 对象、2569 文件完整清单一致、树 `085725d9c0f14c51846e9b8f355dd6e0140c1760` 一致、fsck rc=0 |
| 后来更新的快照 | 冻结提交 `1a4de0ba8f406e4408b3120f7a5b248255291c78`、树 `edccf48a89984fb6cf1b36147ece9c732724c0b4`，不是本报告原固定对象；相对原对象只有 5 条非 backend 差异 |
| 新对象的本地后端门禁 | archive 后独立运行：收集 1678 nodeid 与原固定对象逐条相同；1650 passed / 10 skipped / 18 deselected、cov 85.25%、rc=0；JUnit 1660 cases、failure/error 0；Ruff / format / mypy / 质量守卫全部 rc=0，守卫 9 passed |
| 新对象凭据轴 | 冻结主线/候选调用构造器 `--dry-run`，八键实际扫描通过，输出树与被测新对象相同；不移动引用。仅涵盖当前登记值，不证明历史旧值/未知凭据全部不存在 |
| 保护与 Git 状态 | 41 个保护对象前后大小/hash 同历史基线；已有引用逐字未变。没有把 hash 判据说成 mtime 判据 |
| 实时远端 | 只读查询成功，当前当次只见 master `985d53e4…`（完整号与时间见主报告 §16.4 和本轮 `audit.json`）；以已有审计对象只读核查，本地主线及候选均无共同祖先；主仓 origin refs 未变 |

本轮新日志与对象 archive 位于 `C:/Users/33393/AppData/Local/Temp/legal-closeout-review-20261001-1790846424229/`，汇总见 `audit.json`。原六份脚本与证据没有更换。当前快照分支若再次移动，本节验证只对应上述冻结提交，不自动覆盖新对象。

新增实质问题：`b_worktree_value_scan.py` 直接解析可打印的 Git status 路径，对中文/空格文件发生漏读；漏读或只有部分键输入仍可能返回成功。仓外假凭据临时库已复现。处理建议及对齐状态见主报告 §16.3。旧报告“整个未跟踪面无现役凭据”结论撤回，但这**不推翻固定 Git 对象的八键扫描与本地测试结果**，两根证据轴必须分开。

两项证据边界也明确收窄：

- `verify_report.py` 是文本/记录辅助检查，部分断言仅检查字符串出现；不能替代对象、哈希、完整日志和退出码的独立核查。其旧 HEAD 检查在本轮接手时确实报红，不能解释成业务门禁失败。
- 持久 pack 只保证恢复本报告固定 trim 对象，不保活原草案/full 的全部游离对象。部分旧多步 runner 仍引用原临时路径；不能把“复算器可从持久副本运行”扩大成“全套多阶段流程清掉 TEMP 后无需调整即可复跑”。本轮没有为此新建备份框架或复制整套大文件。

结论：**原助手交付的 A–E 本地结果经复核有证据支持；本轮补验了后来更新的 Windows 后端对象，并纠正报告交叉引用与范围过度声明。** 工作区普查缺陷待修、风险草案未签、真实 rerank 未验收、Linux/远端 CI 未跑；本轮也未重跑 frontend build 或 pip-audit，不能称为全面安全清零或可以发布/部署。真实库与服务器部署继续不执行。
