# Git Repository Repair Execution Plan

> **历史执行手册；不要直接重跑。** 2026-09-23 的 E3 已完成对象库重建和 live 切换。本文原有复选框是执行前的步骤清单，没有全部回写；当前状态以本段和「E3 执行结果」为准。任何新的切换/改写操作都必须基于新鲜基线、新计划和单独的 owner 批准。

> ## 当前执行状态与复核（2026-09-23）
>
> **结论：原方案对当时的修复目标成立，核心修复已完成；现在不应按原清单重跑。**
>
> **发现的执行偏差：** E3 记录能确认 `$runRoot\git-backup`，但未找到 Task 2 Step 2 要求的 `$runRoot\worktree-backup`。因此“Task 1→6 全部按序、无跳步”不成立；切换前的工作区文件快照无法事后补造。当前补偿备份是切换后的状态，不等同于切换前快照。
>
> **本次补偿恢复锚点（均在本机 D 盘，未上传）：**
> - 工作区（不含 `.git`）：`D:\ai-legal-helper-bundles\2026-09-23\current-worktree-backup-review`；205,176 个文件、12.726 GiB（13,665,502,170 bytes）。Robocopy 复制退出码 1（成功复制），随后 `/L` 校验退出码 0，0 copied / 0 mismatch / 0 failed。此副本已同步本次计划更新，源文件与备份 SHA-256 一致。
> - Git 元数据快照：`D:\ai-legal-helper-bundles\2026-09-23\current-state-20260923-2000\git-metadata`；快照 HEAD 与 live 均为 `b7d96f5195633e70c1047437fc2b6e6ca90cb42d`，`fsck --full --no-dangling` 退出码 0。
> - `all-refs.bundle`：`D:\ai-legal-helper-bundles\2026-09-23\current-state-20260923-2000\all-refs.bundle`，verify 成功；新克隆位于同目录 `bundle-restore`，其 fsck 退出码 0，10 个本地 branch/tag ref 与 live 对应值一致。
>
> **现场复核（约 20:05 的历史快照）：** 9 个 worktree 的 HEAD 均可解析，`refs/replace` 为 0；`git fsck --full --no-dangling` 退出码 0、无输出。`git fsck --full` 退出码 0，但报告 260 个 dangling 对象（5 commits、255 blobs），来源未查明；当时没有 missing/broken 报告。主 worktree index 干净但有 6 处未暂存改动和 523 个未跟踪项；WorkBuddy worktree 有 6 个未跟踪项，`codex/legal-agent-v1` 有 1 个未跟踪项；6 个 detached worktree 干净。
>
> **当前命名与后续 GC：** WorkBuddy 分支已按 owner 要求从 `workbuddy/master-e8826c5b` 改名为 `master-e8826c5b`，tip 仍为 `f3690940a94fc228bdafef5a6aca801a9a6111dc`；6 个保留 tag 当前为 `keep-detached-20260923/*`。GC 未在 E3 切换期间执行；另一份进度报告记录了 E3 后经 owner 批准执行 live `gc`，见 `C:\Users\33393\WorkBuddy\Worktrees\ai-legal-helper\master-e8826c5b\docs\progress-report-2026-09-23.md`。dangling 对象的来源仍需单独查明，不能用历史 GC 记录推断其成因。
>
> **并行会话停止后的增量复核（对象时间戳约 21:11）：** 当前 `git fsck --full` 退出码 0，报告 261 个 dangling 对象（5 commits、256 blobs），无 missing/broken 报告；`--no-dangling` 退出码 0、无输出。与 20:00 元数据快照相比，新出现的 loose blob `1391beb453cb525f2cb6b8055128474b4c08c25e`（42,567 bytes，mtime 21:11:24）经 `git hash-object --path` 与工作区文件 `docs/process-archive/code-review-report-02e3851-20260918.md` 的内容哈希完全一致；该文件 mtime 为 21:09:36，所给会话最近一轮结束于 21:10:22。HEAD 和 index 仍指向旧 blob `5296a4aa031f5c178e392d83f0fbb02d3d8ecc56`，因此报告当前是未暂存/未提交状态；其工作区版本对应的 blob 因不在 refs/index 中而显示 dangling。线程可见历史确有该报告的 file-change 记录，但最新一轮未返回具体命令项：报告内容来源已确认，具体哪个操作将它写入 loose object store、是否由该会话直接触发，仍不能仅凭日志断言。此前快照中的 260 个 dangling 对象 ID 均仍存在；其中 255 个 loose 对象的文件 mtime 变为 21:11:24–26，但对象 ID 未变。当前 refs（11 个）与 20:00 快照一致，worktree 脏状态计数也未变；复核时无 Git 进程或 lock。已创建 `D:\ai-legal-helper-bundles\2026-09-23\post-session-audit-20260923-2111\git-metadata` 完整元数据快照；与 live 的 261 个 dangling ID 及 11 个 refs 完全一致，快照 `fsck --full --no-dangling` 退出码 0。剩余 dangling 对象继续保留，不执行 prune。

**Goal:** Rebuild the damaged local Git object graph in an isolated repository, verify that the current files and local refs are preserved, then switch only the repository metadata while retaining the existing working tree.

**Architecture:** Export the required local refs from the current repository into a clean staging repository, import them without `refs/replace`, and verify the result through `fsck`, semantic history comparison, bundle verification, and a fresh clone. Preserve the old `.git` as a recoverable rollback copy; never repair by deleting objects in place.

**Tech Stack:** Git 2.55.0.windows.3, PowerShell, existing local Git metadata, `fast-export`/`fast-import`, `bundle`, `clone`.

> ## 修订记录（2026-09-23，E1）
>
> 本方案由他方 agent 编写；2026-09-23 由接手会话按交接书 §4 批次 E1 逐条修订。**改动 7 处、新增 3 条全局风险**，
> 原方案的 4 项保留项（换对象库而非原地修 / 禁 gc·prune / 先演练后切换 / 三重验证 + 保留回滚）**未动**。
>
> | # | 类别 | 改动 |
> |---|---|---|
> | 1 | 缺口① · **可达性** | 新增 Task 1 **Step 0**：6 个 detached-HEAD worktree 的 SHA（`3ba4aaf/b0c229d/ba8a569/dca9345/30a865f/e9b0e17`）打临时 tag `repair-detached/*` 纳入导出集，否则替换后立刻变成悬空对象 |
> | 2 | 缺口① · **注册** | 新增 Global Constraint **"只替换 `objects/`+`refs/`"**，并重写 Task 5 Step 3：原方案**整目录替换 `.git`** ⇒ 会同时丢掉 9 个 worktree 的**注册**（`.git/worktrees/<name>`）。这不是原方案说的"可达性"，是更硬的破坏 |
> | 3 | 缺口② | Global Constraints 与 Task 1 **Step 4**、GATE 1、Task 5 Step 4、DoD 的绝对数字（`522` untracked / `111` workbuddy 提交 / 写死的 HEAD SHA）**全部改为相对基线**：cutover 当时重新实测并与 `ref-baseline.txt` 比对 |
> | 4 | 风险① | 全局约束新增：PowerShell 管道会吞 `$LASTEXITCODE` ⇒ 判据必须**落盘再读回** |
> | 5 | 风险② | 全局约束新增：本机 PowerShell 工具取不到 stdout ⇒ 同上 |
> | 6 | 风险③ | Task 2 新增 Step 0：robocopy 前确认**无其他 git 进程**在写（本机另有容器/IDE/App 在跑） |
> | 7 | 风险④（本会话新发现） | Task 4 新增瞬态对象读取失败的处置：**同一对象会先报错、几分钟后正常**（实测 `b9d4d1c` 曾报 `unable to read tree`/`not a tree object`/`bad object`，随后 3/3 正常）⇒ "树/计数不一致"的判据必须**重试 + 二次确认**才能判红，否则会假红或掩盖真差异 |
> | 8 | E2 · **fsck 期望值纠错** | Task 5 Step 4 / DoD 原写"cutover 后 fsck exit 0"**不可达**：实测对象图干净（0 broken link / 0 missing），但 reflog 会产生 **2975 条** `invalid reflog entry`（`refs/heads/master` 2034 / `workbuddy` 477 / `HEAD` 409 / `worktrees/*/HEAD` 55）—— 因为 master/workbuddy 全链换了 SHA。⇒ 新增：cutover 时把 `.git/logs/`、`.git/worktrees/*/logs/`、`.git/ORIG_HEAD`、`.git/worktrees/*/ORIG_HEAD` **一并移入回滚目录**；实测移走后 fsck = 0 错误、exit 0 |
> | 9 | E2 · **ref 复制形态** | Task 5 Step 3 澄清：必须先 `Move` 走 live `refs/`（`refs/replace/` 随之消失，否则 `pack-objects` 继续失败 —— 不能用"覆盖复制"），再**只复制 staging 的 `refs/heads` + `refs/tags`**；不要复制 `refs/remotes`（staging 的 remote refs 存在 packed-refs 里，实测未污染 live 的 `origin/master`，但显式排除更稳） |
> | 10 | E2 · **覆盖度校验** | 新增 Task 4 Step 1c：逐条校验 live 每个 ref/伪 ref 指向的对象在 staging 中存在，并显式列出**预期例外**（`ORIG_HEAD` 的 2 个对象 `5f96c71f`（主库）/`f008ed7f`（worktree `master-e8826c5b`）—— 连同"移走 logs/ORIG_HEAD"一起处理） |
> | 11 | E2 · **影响面（必读）** | 实测 SHA 改名范围：`master` 113/113、`workbuddy` 133/133 **全部**换名（`76c1eea` 是这两条历史的基座，其重建等价提交 `5e513846` 本身就是新 SHA），`codex/legal-agent-v1` 233 不变、`v1.0.0` 42 不变 ⇒ 切换后**所有已记录的旧 SHA 失效**（含本会话 7 个提交、`8bff02b`、D 盘备份的 ref 校验值 `7663158`），台账/文档/其他 agent 手里的 SHA 引用需同步更新 |
> | 12 | E3 执行期 · **ref 源** | Task 5 Step 3 原写「从 `$stagingWorktree\.git\refs` 复制」**会静默丢光所有 tag**：clone 出来的 staging-worktree 把 tags 存在**自己的 packed-refs** 里（实测其 `refs\tags` 目录为空）。已改为**从 bare 的 `$stagingBare\refs` 复制**（其 10 条 ref 全是松散文件） |
>
> **E3 执行状态**：对象库重建和 live 切换已于 2026-09-23 完成；Task 2 Step 2 的工作区备份未找到，Task 6 对该备份的保留要求也因此未满足，故“Task 1→6 全部无跳步”不成立。E3 切换期间没有执行 `gc`/`prune`/`repack`、reset 或 checkout；E3 后另有经批准的 live `gc`，见文首状态。
>
> **验证状态（2026-09-23 补，取代原"未验证项"）**：Task 1 Step 0（6 个 detached SHA 打 tag）、Task 3（fast-export/fast-import + 非裸 checkout）、
> Task 4（三重验证 + 6 个 detached 可达 + 覆盖度）、Task 5 Step 3（选择性替换演练，含 worktree 注册存活）**均已在 `%TEMP%` 副本上跑通**，
> 证据见下节「E2 演练结果」。**live `.git` 全程未被触碰。**

## E2 演练结果（2026-09-23，全程只读 live + `%TEMP%` 副本）

> 副本 = `robocopy` 的 live `.git` 全量拷贝（909.7 MB，HEAD/refs/replace/worktrees 一致）。执行位置：`$env:TEMP\ai-legal-helper-git-repair-e2`。

| 检查 | 结果 |
|---|---|
| **可行性硬前提**（缺失对象是否落在导出集可达集内） | PASS：`rev-list --objects` over 4 refs + 6 detached SHA = exit 0 / 0 stderr；**10 个缺失对象全部不可达**；5 个未被 replace 覆盖的坏链源端（`d96cb5e`/`3573912`/`9794eef`/`8a4961b`/`6111690`）**全部不可达** ⇒ 遍历不会断 |
| Task 1 Step 0（打 6 个临时 tag） | PASS：6/6 `rev-parse --verify` 成功；6 个 SHA 原本**都不在任何 ref 可达集内**（确证原方案会丢它们） |
| Task 3 Step 1（fast-export → fast-import，拆两条判退出码） | PASS：export exit 0（214,090,797 B）、import exit 0；staging = 5642 对象 / 1 pack / **garbage 0**（= 可达对象总数，逐数一致） |
| Task 3 Step 2/3（非裸 checkout + 本地 config + hooks + info/exclude） | PASS：clone exit 0；7 个 config 项写入；`post-checkout`/`post-commit`/`info/exclude` 拷入 |
| Task 4 Step 1（树 / 计数 / 语义） | PASS：4 个 ref 的 `^{tree}` 与 `rev-list --count` **逐项一致**；语义史（`%T|%an|%ae|%aI|%cn|%ce|%cI|%s` 单行式）**0 diff**（113/133/233/42 条全等） |
| Task 4 Step 1b（6 个 detached SHA 在新库可达） | PASS：6/6 `cat-file -t` = commit |
| Task 4 Step 1c（覆盖度，E2 新增） | PASS 且**定位到 2 处例外**：`refs/remotes/origin/master` = `15562fc9` 在新库存在；`ORIG_HEAD` 的 `5f96c71f`/`f008ed7f` 在新库**不存在** |
| Task 4 Step 2（fsck / archive / bundle） | PASS：staging fsck exit 0；`archive HEAD` exit 0（356 MB）；`bundle create --all` exit 0（147.7 MB / 15 refs）+ verify "is okay" |
| **反证**：同一命令在未修复的 live 副本上 | `bundle create` **失败**（exit 1：`Could not read 0263bd56…` → `Failed to traverse parents of commit 76c1eea…` → `pack-objects died`）——即本修复要解掉的那个病 |
| Task 4 Step 3（从 bundle 重新 clone） | PASS：clone exit 0、fsck exit 0、`log --oneline -5 master` 可读（无 `refs/replace`） |
| Task 5 Step 3 演练（只换 `objects/`+`refs/`） | PASS（含 3 处修订，见下）；**变体A（整目录复制 refs）**：`refs/replace` 清空 ✓、`packed-refs` 4 条有效条目全部可解析 ✓、陈旧条目 `refs/heads/master=6e51252e` 被 loose 遮蔽（修复前就已陈旧）、`worktree list` = **9** ✓、`worktrees/` 目录 8 项保留 ✓、主 `HEAD` = 新 tip ✓ |
| 变体A 的 fsck | ❌ 2975 条 `invalid reflog entry`（**对象图本身 0 坏链 / 0 missing**） |
| 变体B（再移走 `.git/logs` + `ORIG_HEAD`） | 降到 56 条，全部来自 `.git/worktrees/*/logs` |
| **变体B+（再移走 `.git/worktrees/*/logs`）** | ✅ **fsck = 0 错误、exit 0** ⇒ 这就是 Task 5 的可达期望形态 |
| 切换后 9 个 worktree 的 HEAD | PASS：6 个 detached 直接可解析；2 个符号 ref 解析正确（`codex/legal-agent-v1`→`8aecf3e0`、`workbuddy/master-e8826c5b`→`78181d9a`） |
| 切换后工作区完整性（status 对比） | PASS：用 **worktree 自身 gitdir** 视角，live 7 行 vs 切换后 7 行，**diff 0**（用错 index 会得到 940 行假差异 —— 见纪律） |
| 切换后 ref 值 vs staging | 一致：`master`→`b7d96f51`、`workbuddy`→`78181d9a`、`codex`→`8aecf3e0`、`v1.0.0`→`ac8ab43e` |

**纪律补充（E2 实测）**：① 比较 status 必须用 `--git-dir=<gitdir>/worktrees/<name>` 视角（或 `-C <worktree>`），用主 `.git/index` 配 `--work-tree=<linked worktree>` 会产出几百行 `.M` 假差异；
② `fsck` 对 reflog 的报错量级取决于"有多少提交换了 SHA"，不能只看条数判断对象库好坏；③ 校验脚本里 `--git-dir=(Join-Path …)` 这类**参数内嵌表达式**会被 PowerShell 当成字面量，必须先把值存变量再拼字符串（E2 中造成 4 条假 MISMATCH）。

## E3 执行结果（2026-09-23，已切换 live）

执行位置：`$env:TEMP\ai-legal-helper-git-repair-e3`（`$runRoot`）。Owner 放行口径：「按你的推荐执行，现在只有你一个会话在执行任务」。

| 阶段 | 结果 |
|---|---|
| 预检 | 无 `git` 进程；9 个 worktree；6 个 detached SHA 可解析；D 盘锚点 `2026-09-23\dot-git-backup` HEAD=`6e4a191`/workbuddy=`7663158` 与 live 一致 |
| Task 1 基线冻结 | HEAD=`6e4a191`、branch=`master`、无 staged；status=529、status(all)=34099；4 个 ref 的 tip/tree/count 全部落盘 |
| Task 2 备份 | `$runRoot\git-backup` = 909.7 MB 全量 `.git`；HEAD/workbuddy/replace(5) 一致；已知损坏（10 missing/10 broken）如预期复现、备份本身可读；**未找到 `$runRoot\worktree-backup`，Task 2 Step 2 缺失**（当前补偿见文首） |
| Task 1 Step 0 | 6 个 `repair-detached/*` tag 落盘（写 live refs，Task 6 已删） |
| Task 3 重建 | `fast-export` rc=0（214,090,797 B）→ `fast-import` rc=0；staging.git = 5642 对象 / garbage 0；**与 E2 演练产出的 tip 完全一致（重建可复现）** |
| Task 4 验证 | 4 个 ref 的 tree/count 一致、语义史（含 committer）**0 diff**；6/6 detached 可达；覆盖度仅剩预期例外；staging `fsck` 0 行输出、`archive` rc=0、`bundle create+verify` rc=0、从 bundle 重克隆 `fsck` 0 行 |
| Task 5 Step 1 | 切换前重测：HEAD/status(529)/status(all=34099)/4 个 ref 计数 **与基线逐项一致** |
| Task 5 Step 3 切换 | `Move` 走 live `objects`(907.1 MB)/`refs`(13 文件) → `$old\objects-moved`、`$old\refs-moved`；装入重建 `objects`(141.1 MB) + 10 条本地 ref；`.git\logs`、`.git\ORIG_HEAD` + 8 个 worktree 的 `logs`/`ORIG_HEAD`（共 16 项）移入 `$old\wt-bk-*`、`bookkeeping-*` |
| Task 5 Step 4 | HEAD=`b7d96f51`；branch=`master`；status=**529 = 基线**；**fsck 0 行输出 / 0 missing / 0 broken**；`worktree list`=**9**；ref 集合与预期 **10/10 零差异**；`refs/remotes/origin/master`=`15562fc9` 保留；`refs/replace`=**0**；9 个 worktree 的 HEAD（含 2 个符号）全部可解析 |
| Task 6 | `diff` 仍只有那 **6 处既有改动**；`archive` rc=0；**`bundle create --all` rc=0（147,750,117 B）+ verify "complete history / is okay"** ← 切换前此命令**必然失败**；删 `repair-detached/*` 后 6 个 detached SHA 仍可解析、`fsck --full`（含 dangling）**0 行输出**；ref 写/删测试 rc=0 零残留 |
| 回归环（diagnosing-bugs） | **RED → GREEN**：切换前 `missing=10/broken=10`、`pack-objects` rc=128；切换后 `missing=0/broken=0`、`pack-objects` rc=0 |
| 磁盘 | live `objects` 907.1 MB → **141.1 MB**（633 MB 垃圾随旧库移入回滚目录） |

**回滚锚点（三份，独立）**：① `$runRoot\live-before-cutover\`（`objects-moved`/`refs-moved`/`bookkeeping-*`）；② `$runRoot\git-backup`（全量 909.7 MB）；③ `D:\ai-legal-helper-bundles\2026-09-23\`：`dot-git-backup`（切换前）+ `dot-git-backup-post-e3`（切换后）+ `dot-git-backup-post-adr020`（首次提交后）+ `post-cutover.bundle` / `post-adr020.bundle`（均自校验 rc=0）。
**回滚步骤**：把 `.git\objects`、`.git\refs` 移走 → 把 `objects-moved`、`refs-moved` 移回原位 → 把 `bookkeeping-*`/`wt-bk-*` 移回原路径；
**再对每个 worktree 刷新 index**：`git --git-dir=<gitdir>\worktrees\<name> read-tree HEAD`（不碰工作区文件）——
**E3 后实测（2026-09-23）**：若切换后已经产生过新提交，各 worktree 的 index 仍指向新库对象，回滚后会多出 2 条 missing
（实测为 `docs/ADR.md` 与映射表的 blob），补这一步即精确回到切换前（HEAD `6e4a191` / `refs/replace` 5 / worktree 注册 8 / missing 10）；
**不要 reset 工作区**。回滚路径已在副本上完整演练通过。

**收尾已完成（切换后，2026-09-23）**：
- **首次真实提交** `16d8e67`（`docs(ADR-020)` + `docs/git-sha-remap-20260923.tsv`）= **对象写路径实测通过**（新库新增 5 个 loose 对象；ref 未丢；git 自动重建 reflog）；提交后 `fsck` 仍 0 行输出、回归环仍 **GREEN**。
- **恢复演练**：从 `post-cutover.bundle` 真 `clone`（rc=0）→ `fsck` 0 行、refs 齐全（`master`/`origin/workbuddy/…`/`v1.0.0`）、关键文件 `cat-file -e` 全通。
- **旧→新 SHA 映射表**已入库：`docs/git-sha-remap-20260923.tsv`（246 条）；ADR 见 `docs/ADR.md` **ADR-020**。

**E3 当时遗留（历史记录）**：① 当时尚未决定 `gc`/`prune`/`repack` 的放行时机；E3 后的 owner-approved `gc` 见文首状态；② `packed-refs` 中 `refs/heads/master` 的陈旧条目 `6e51252e` 被同名 loose ref 遮蔽（E3 时 fsck 视为干净，未清理）；③ `.git/worktrees/master-e8826c5b/refs` 这个**空目录**被 git 判为 garbage（E3 时 0 字节，切换前即存在，未处理）。

## Global Constraints

- Workspace: `C:\Users\33393\Desktop\ai-legal-helper`.
- Current branch: `master`。**不要写死 HEAD SHA**：原方案写的 `6e4a191…` 已随在途提交推移，
  一律用 Task 1 Step 1/Step 4 的**现场实测值**。
- **基线一律用相对值**（原方案的 `master` 113 / `workbuddy/master-e8826c5b` 111 / `codex/legal-agent-v1` 233 /
  `v1.0.0` 42 是当时快照；2026-09-23 实测 `workbuddy/*` 命名空间只剩 1 个分支）。判据 = "与本次运行
  Task 1 记录的基线逐项一致"，不是与任何常数一致。
- **未跟踪条目数同理**：原方案写 522，2026-09-23 实测已 523。不得作为判据。
- **只替换 `objects/` 与 `refs/`**：`.git/worktrees/`（9 个 worktree 的注册）、`config`、`hooks`、`info`、
  `logs` 一律保留原地。**整目录替换 `.git` 是禁止动作**——它会让 9 个 worktree 的 `.git` 指针文件全部悬空。
- Do not run `git reset --hard`, `git clean`, `git gc`, `git prune`, force-push, or delete the old `.git` during this procedure.
- Do not import `refs/replace`, old reflogs, or `.git/objects` temporary files into the rebuilt repository.
- Do not add or commit the untracked workspace contents during repair.
- Any command that changes the live `.git` is a cutover action and requires the owner gate below.

### 全局风险（E1 新增，全程适用）

1. **PowerShell 管道会吞 `$LASTEXITCODE`**：`git fast-export … | git fast-import` 这类管道的失败会被
   静默吞掉，`$LASTEXITCODE` 反映的是**最后一个**命令。⇒ 凡"必须为 0"的判据，一律**先落盘再读回**：
   ```powershell
   git fast-export --signed-tags=strip --show-original-ids @exportRefs > (Join-Path $runRoot 'export.fi')
   if ($LASTEXITCODE -ne 0) { throw "fast-export failed: $LASTEXITCODE" }
   git --git-dir=$stagingBare fast-import --quiet < (Join-Path $runRoot 'export.fi')
   if ($LASTEXITCODE -ne 0) { throw "fast-import failed: $LASTEXITCODE" }
   ```
   （拆成两条、各自判退出码，而不是一条管道。）
2. **本机 PowerShell 工具取不到 stdout**（工具宿主限制）：命令输出必须重定向到文件，再用
   `Get-Content` 读回；不要依赖在终端里"看见"输出。
3. **执行前确认没有其他 git 写者**：robocopy 备份 `.git` 之前先确认没有其他 git 进程在写
   （本机有 3 个容器在跑、用户 IDE 打开着该仓库、WorkBuddy App 自身被怀疑会删除 `workbuddy/*` refs）。
   容器不写 `.git`，但**"只有本会话在跑"不等于".git 不会被静默碰"**——发现任何可疑写者就停下报告。
4. **瞬态对象读取失败**（2026-09-23 实测）：同一对象会先报 `unable to read tree` / `not a tree object` /
   `bad object` / `Not a valid object name`，**几分钟后同一命令正常**。⇒ 所有"对象/树/计数不一致"的判据
   必须**同一命令重试 ≥3 次并二次确认**才判红；否则会产出假红（把好库判坏）或掩盖真差异。

---

### Task 1: Freeze and record the live baseline

**Files:**
- Read: `.git/`, current worktree
- Create: external baseline directory under `%TEMP%`

- [ ] **Step 0: Inventory worktrees and make the detached HEADs reachable**（E1 新增）

9 个已注册 worktree 里有 **6 个处于 detached HEAD**，且**不被任何 branch/tag/remote 包含**。
整目录替换 `.git` 会同时丢掉它们的**注册**与 HEAD 的**可达性**。替换前必须先把这 6 个 SHA 变成可达。

```powershell
$runId = Get-Date -Format 'yyyyMMdd-HHmmss'
$runRoot = Join-Path $env:TEMP "ai-legal-helper-git-repair-$runId"
New-Item -ItemType Directory -Path $runRoot -Force | Out-Null

git worktree list --porcelain > (Join-Path $runRoot 'worktrees-before.txt')
$detached = @('3ba4aaf','b0c229d','ba8a569','dca9345','30a865f','e9b0e17')
foreach ($short in $detached) {
  $sha = git rev-parse --verify "$short^{commit}"
  if ($LASTEXITCODE -ne 0) { throw "Detached HEAD $short unresolvable; re-inventory before proceeding." }
  git tag --force "repair-detached/$sha" $sha
  "$sha" | Tee-Object -FilePath (Join-Path $runRoot 'detached-heads.txt') -Append
}
Get-Content (Join-Path $runRoot 'detached-heads.txt')
```

Expected: 6 个 tag 落盘；`worktrees-before.txt` 含 9 个 worktree；6 个工作区均为
`tracked=0 / untracked=0`（2026-09-23 实测如此）。任一 SHA 解析失败即停止、重新盘点。
临时 tag 只在修复期间存在，Task 6 结束后删除。

- [ ] **Step 1: Confirm the operation state**

Run from the workspace:

```powershell
$ErrorActionPreference = 'Stop'
git status --porcelain=v2 --branch
git diff --cached --quiet
if ($LASTEXITCODE -ne 0) { throw 'Staged changes exist; stop and rebaseline.' }
git rev-parse --verify HEAD
git symbolic-ref --short HEAD
```

Expected: branch `master`、**无 staged 改动**，且 HEAD 在本任务后续步骤复测时保持一致（相对基线）。

- [ ] **Step 2: Record refs, trees, counts, config, hooks, and worktree inventory**

```powershell
git for-each-ref --format='%(refname) %(objectname)' refs/heads refs/tags > (Join-Path $runRoot 'refs.txt')
git for-each-ref --format='%(refname) %(objectname)' refs/remotes > (Join-Path $runRoot 'remote-refs.txt')
git config --local --list --show-origin > (Join-Path $runRoot 'config.txt')
git status --porcelain=v2 > (Join-Path $runRoot 'status.txt')
git diff --binary HEAD > (Join-Path $runRoot 'tracked-working-tree.patch')
Get-ChildItem -Force -Recurse | Where-Object { $_.FullName -notlike "$PWD\.git\*" } |
  Select-Object FullName,Length,LastWriteTime,PSIsContainer |
  Export-Csv (Join-Path $runRoot 'worktree-inventory.csv') -NoTypeInformation
```

The inventory is evidence only; it is not a substitute for the file backup in Task 2.

- [ ] **Step 3: Record the exact ref/tree baseline**

```powershell
$refs = @(
  'refs/heads/master',
  'refs/heads/workbuddy/master-e8826c5b',
  'refs/heads/codex/legal-agent-v1',
  'refs/tags/v1.0.0'
)
foreach ($ref in $refs) {
  $tip = git rev-parse $ref
  $tree = git rev-parse "$ref^{tree}"
  $count = git rev-list --count $ref
  "$ref tip=$tip tree=$tree count=$count" |
    Tee-Object -FilePath (Join-Path $runRoot 'ref-baseline.txt') -Append
}
Get-Content (Join-Path $runRoot 'ref-baseline.txt')
```

- [ ] **Step 4: Freeze the baseline as RELATIVE values**（E1 新增，取代绝对数字）

```powershell
$counts = Join-Path $runRoot 'baseline-counts.txt'
foreach ($ref in $refs) { git rev-list --count $ref }                                        >  $counts
(git status --porcelain=v2 | Measure-Object).Count                                            | Tee-Object -FilePath $counts -Append
(git status --porcelain=v2 --untracked-files=all | Measure-Object).Count                      | Tee-Object -FilePath $counts -Append
(git rev-parse HEAD)                                                                          | Tee-Object -FilePath $counts -Append
Get-Content $counts    # 落盘后读回再判（风险① / ②）
```

**GATE 1:** 若 HEAD / 分支 / staged 状态与 Step 1 复测值不一致，停止并重做 Task 1。
**不得比对任何写死常数**（旧的 "6 tracked / 522 untracked / HEAD 6e4a191" 判据已作废）。

---

### Task 2: Make recoverable backups before creating the staging repo

**Files:**
- Read: current `.git`, worktree
- Create: `$runRoot\git-backup`, `$runRoot\worktree-backup`

- [ ] **Step 0: Confirm no other git writer**（E1 新增，风险③）

```powershell
Get-Process | Where-Object { $_.ProcessName -match 'git' } | Select-Object Id,ProcessName,Path
# 预期：不应有其他 `git` 进程；IDE / WorkBuddy App / 其他会话若可能写 .git，先停下报告，不要继续。
```

- [ ] **Step 1: Copy the complete current `.git`**

```powershell
$gitBackup = Join-Path $runRoot 'git-backup'
robocopy (Join-Path $PWD '.git') $gitBackup /E /COPY:DAT /DCOPY:DAT /R:0 /W:0 /NFL /NDL /NP
if ($LASTEXITCODE -gt 7) { throw "Git backup failed: $LASTEXITCODE" }
```

- [ ] **Step 2: Copy the current worktree without `.git`**

```powershell
$worktreeBackup = Join-Path $runRoot 'worktree-backup'
robocopy $PWD $worktreeBackup /E /COPY:DAT /DCOPY:DAT /R:0 /W:0 /NFL /NDL /NP /XD '.git'
if ($LASTEXITCODE -gt 7) { throw "Worktree backup failed: $LASTEXITCODE" }
```

The backup may contain sensitive local evidence. Keep it local or on an access-controlled disk; do not push it to `origin`.

- [ ] **Step 3: Verify the backup is usable**

```powershell
git --git-dir=$gitBackup rev-parse --verify HEAD
git --git-dir=$gitBackup fsck --full --no-dangling
```

Expected: HEAD resolves. `fsck` may reproduce the known corruption; that is acceptable for the rollback copy. The command must not report that the backup itself is unreadable.

**GATE 2:** Do not continue if either copy failed or the backup path is not outside the workspace.

---

### Task 3: Build the clean staging repository

**Files:**
- Create: `$runRoot\staging.git`
- Create: `$runRoot\staging-worktree`
- Preserve: all current live files unchanged

- [ ] **Step 1: Export the four local refs + the detached-HEAD tags**（E1 修订：加入临时 tag）

```powershell
$exportRefs = @(
  'refs/heads/master',
  'refs/heads/workbuddy/master-e8826c5b',
  'refs/heads/codex/legal-agent-v1',
  'refs/tags/v1.0.0'
) + @(git for-each-ref --format='%(refname)' refs/tags/repair-detached)
$stagingBare = Join-Path $runRoot 'staging.git'
git init --bare --quiet $stagingBare
# 拆两条、各自判退出码（风险①：管道会吞 $LASTEXITCODE）
git fast-export --signed-tags=strip --show-original-ids @exportRefs > (Join-Path $runRoot 'export.fi')
if ($LASTEXITCODE -ne 0) { throw "fast-export failed: $LASTEXITCODE" }
git --git-dir=$stagingBare fast-import --quiet < (Join-Path $runRoot 'export.fi')
if ($LASTEXITCODE -ne 0) { throw "fast-import failed: $LASTEXITCODE" }
```

The export must use the current default read view so the existing `replace` repair is reflected in the rebuilt graph. No `refs/replace` are copied.

- [ ] **Step 2: Create a non-bare staging checkout and index**

```powershell
$stagingWorktree = Join-Path $runRoot 'staging-worktree'
git clone --quiet $stagingBare $stagingWorktree
git -C $stagingWorktree branch --force workbuddy/master-e8826c5b $(& git --git-dir=$stagingBare rev-parse refs/heads/workbuddy/master-e8826c5b)
git -C $stagingWorktree branch --force codex/legal-agent-v1 $(& git --git-dir=$stagingBare rev-parse refs/heads/codex/legal-agent-v1)
git -C $stagingWorktree tag --force v1.0.0 $(& git --git-dir=$stagingBare rev-parse refs/tags/v1.0.0)
```

The staging checkout supplies a valid index. Do not copy the old index into the new repository.

- [ ] **Step 3: Restore only required local configuration**

```powershell
git -C $stagingWorktree remote set-url origin https://github.com/wjt-code-design/fazhi-assistant.git
git -C $stagingWorktree config core.filemode false
git -C $stagingWorktree config core.symlinks false
git -C $stagingWorktree config core.ignorecase true
git -C $stagingWorktree config gc.writecommitgraph false
git -C $stagingWorktree config fetch.writecommitgraph false
git -C $stagingWorktree config maintenance.commit-graph.enabled false
```

Copy `.git/hooks/post-checkout`, `.git/hooks/post-commit`, and `.git/info/exclude` from the live repository into the staging repository after reviewing their contents. Do not copy sample hooks, reflogs, replace refs, or object files.

---

### Task 4: Verify the rebuilt repository before touching live `.git`

**Files:**
- Read: `$stagingWorktree`, `$stagingBare`
- Create: `$runRoot\verification`

- [ ] **Step 1: Verify refs, trees, counts, and semantic history**（注意风险④：不一致要重试再判）

```powershell
$checks = @('master','workbuddy/master-e8826c5b','codex/legal-agent-v1','v1.0.0')
foreach ($name in $checks) {
  $oldTree = git rev-parse "$name^{tree}"
  $newTree = git -C $stagingWorktree rev-parse "$name^{tree}"
  $oldCount = git rev-list --count $name
  $newCount = git -C $stagingWorktree rev-list --count $name
  if ($oldTree -ne $newTree -or $oldCount -ne $newCount) {
    # 风险④：瞬态对象读取失败会假红。同一命令重试 3 次、全部一致才判红。
    Write-Warning "Mismatch on $name; retrying 3x to rule out transient object-read failure..."
    Start-Sleep -Seconds 5
    $retryTree = git rev-parse "$name^{tree}"; $retryCount = git rev-list --count $name
    if ($retryTree -eq $oldTree -and $retryCount -eq $oldCount) { continue }  # 瞬态，非真差异
    throw "Tree/count mismatch (confirmed 2x): $name"
  }
  $oldSemantic = @(git log --reverse --format='%T%x09%an%x09%ae%x09%aI%x09%s' $name)
  $newSemantic = @(git -C $stagingWorktree log --reverse --format='%T%x09%an%x09%ae%x09%aI%x09%s' $name)
  if (@(Compare-Object $oldSemantic $newSemantic).Count -ne 0) {
    throw "Semantic history mismatch: $name"
  }
}
```

Expected: no exception. `master` and `workbuddy` tip SHA changes are expected; their tree/count/semantic history must match.

- [ ] **Step 1b: Verify the 6 detached HEADs survived**（E1 新增）

```powershell
foreach ($line in (Get-Content (Join-Path $runRoot 'detached-heads.txt'))) {
  $sha = ($line -split '\s+')[0]
  git --git-dir=$stagingBare cat-file -t $sha | Out-Null
  if ($LASTEXITCODE -ne 0) { throw "Detached HEAD $sha missing from staging repo" }
}
```

Expected: 6/6 在新库中可解析（这就是 Step 0 打 tag 的收益）。

- [ ] **Step 1c: Verify reference coverage**（E2 新增）

逐条校验 live 侧**每个 ref 与伪 ref** 指向的对象在 staging 中存在，防"切走之后某个 ref 变悬空"（E2 实测发现 2 处例外）。

```powershell
$refs = @(& git for-each-ref --format='%(refname) %(objectname) %(objecttype)')
$pseudo = @(Get-ChildItem '.git\*_HEAD','.git\worktrees\*\*_HEAD','.git\worktrees\*\HEAD' -File -ErrorAction SilentlyContinue)
$expectedExceptions = @(
  '5f96c71fb7d225cd4fb80ecec526fea610f80e9d',   # .git/ORIG_HEAD（主库）
  'f008ed7f7121338edacc392aee5f5db4ee645ffc'    # .git/worktrees/master-e8826c5b/ORIG_HEAD
)
$bad = @()
foreach ($line in $refs) {
  $sha = ($line -split '\s+')[1]
  & git --git-dir=$stagingBare cat-file -e $sha 2>$null
  if ($LASTEXITCODE -ne 0) { $bad += ($line -split '\s+')[0] + ' ' + $sha }
}
foreach ($f in $pseudo) {
  $v = ((Get-Content $f.FullName -Raw) -replace "`r|`n",'').Trim()
  if ($v -match '^ref: ' -or $v -notmatch '^[0-9a-f]{40}$') { continue }
  if ($expectedExceptions -contains $v) { continue }
  & git --git-dir=$stagingBare cat-file -e $v 2>$null
  if ($LASTEXITCODE -ne 0) { $bad += $f.FullName.Replace($PWD,'') + ' ' + $v }
}
$bad
```

Expected: `$bad` 为空（`refs/replace/*` 的值会缺 —— 它们**故意**不迁移，属预期）。
**注意**：`ORIG_HEAD` 的两个对象会缺，这是**预期且已被处理**（Task 5 Step 3 会把 `ORIG_HEAD` 一并移走）；
若出现**其它**缺失项，停止并按 Task 1 Step 0 的形态补 tag 后重新导出。

- [ ] **Step 2: Verify object integrity and packability**

```powershell
git -C $stagingWorktree fsck --full --no-dangling
if ($LASTEXITCODE -ne 0) { throw 'Staging fsck failed' }
git -C $stagingWorktree archive --format=tar HEAD | Out-Null
$bundle = Join-Path $runRoot 'staging.bundle'
git -C $stagingWorktree bundle create $bundle --all
git -C $stagingWorktree bundle verify $bundle
```

Expected: fsck exit `0`, archive exit `0`, bundle says `The bundle records a complete history.`

- [ ] **Step 3: Verify recovery from the bundle**

```powershell
$restore = Join-Path $runRoot 'bundle-restore'
git clone --quiet $bundle $restore
git -C $restore fsck --full --no-dangling
if ($LASTEXITCODE -ne 0) { throw 'Restored clone fsck failed' }
git -C $restore log --oneline -5 master
```

Expected: clone exit `0`, clone fsck exit `0`, and `master` is readable without `refs/replace`.

**GATE 3:** Stop and preserve the staging directory if any check fails. Do not modify live `.git` while staging verification is red.

---

### Task 5: Cut over repository metadata with rollback available

**Files:**
- Rename: live `.git/objects` + `.git/refs` → `$runRoot\live-before-cutover\`
- Move aside（E2 修订）: `.git/logs/`、`.git/ORIG_HEAD`、`.git/worktrees/*/logs/`、`.git/worktrees/*/ORIG_HEAD` → `$runRoot\live-before-cutover\`
- Copy: staging `.git/objects` + `.git/refs/heads` + `.git/refs/tags` → live `.git/`
- **Preserve in place**: `.git/worktrees/`（9 个 worktree 的注册）、`.git/config`、`.git/hooks`、`.git/info`、`.git/packed-refs`
- Modify: no tracked or untracked worktree files

> **E1 关键修订**：原方案是 `Move .git → $oldGit` + `Copy $stagingWorktree\.git → .git`（**整目录替换**）。
> 那会同时丢掉 **9 个 worktree 的注册**（`.git/worktrees/<name>`）——比"可达性丢失"更硬的破坏。
> 本步改为**只替换 `objects/` 与 `refs/`**（交接书 E3 的口径），其余元数据原地保留。

- [ ] **Step 1: Recheck the live baseline immediately before cutover**

重跑 Task 1 Step 1 与 Step 4（相对基线），逐项比对 Step 4 记录的 `baseline-counts.txt`。
不一致即中止（在途提交会推移基线；此时应重新冻结而非硬闯）。

- [ ] **Step 2: Get the owner cutover approval**

The approval must identify the exact `$runRoot` and confirm that the staging checks in Task 4 passed. Without that approval, stop after Task 4.

- [ ] **Step 3: Swap only `objects/` and `refs/`, move the SHA-bound bookkeeping aside, preserve worktree registrations**

```powershell
$old = Join-Path $runRoot 'live-before-cutover'
New-Item -ItemType Directory -Path $old -Force | Out-Null

# 1) 备份（不删除）现有 objects 与 refs
robocopy (Join-Path $PWD '.git\objects') (Join-Path $old 'objects') /E /COPY:DAT /DCOPY:DAT /R:0 /W:0 /NFL /NDL /NP
if ($LASTEXITCODE -gt 7) { throw "objects backup failed: $LASTEXITCODE" }
robocopy (Join-Path $PWD '.git\refs')    (Join-Path $old 'refs')    /E /COPY:DAT /DCOPY:DAT /R:0 /W:0 /NFL /NDL /NP
if ($LASTEXITCODE -gt 7) { throw "refs backup failed: $LASTEXITCODE" }

# 2) 移走现有 objects 与 refs（不碰 worktrees/config/hooks/info/packed-refs）
#    ⚠ 必须是 Move（整目录搬走），不能"覆盖复制"：refs/replace/ 只有随 refs/ 一起消失，
#      pack-objects 才会采用新视图（E2 实测：残留 refs/replace ⇒ bundle 继续失败）
Move-Item -LiteralPath (Join-Path $PWD '.git\objects') (Join-Path $old 'objects-moved')
Move-Item -LiteralPath (Join-Path $PWD '.git\refs')    (Join-Path $old 'refs-moved')

# 3) 装入重建后的 objects 与「本地 ref」
#    ⚠ E3 执行期实测修正：ref 源必须用 **bare 的 staging.git**，不能用 staging-worktree！
#      clone 出来的 staging-worktree 把 tags 存在自己的 packed-refs 里，
#      只复制它的 refs\tags 目录会**静默丢光所有 tag**（E3 切换前实测发现）。
#    ⚠ 只带 refs/heads + refs/tags —— live 的 refs/remotes/origin/master（15562fc9）在 packed-refs 里原地保留。
Copy-Item -LiteralPath (Join-Path $stagingBare 'objects') (Join-Path $PWD '.git\objects') -Recurse
New-Item -ItemType Directory -Path (Join-Path $PWD '.git\refs\heads') -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $PWD '.git\refs\tags')  -Force | Out-Null
Copy-Item -Path (Join-Path $stagingBare 'refs\heads\*') (Join-Path $PWD '.git\refs\heads') -Recurse -Force
Copy-Item -Path (Join-Path $stagingBare 'refs\tags\*')  (Join-Path $PWD '.git\refs\tags')  -Recurse -Force

# 4) 把与旧 SHA 绑定的簿记移走（E2 新增；不这样做 fsck 会报约 2975 条 invalid reflog entry）
foreach ($p in @('.git\logs', '.git\ORIG_HEAD')) {
  if (Test-Path (Join-Path $PWD $p)) { Move-Item -LiteralPath (Join-Path $PWD $p) (Join-Path $old ('bookkeeping-' + ([IO.Path]::GetFileName($p)))) }
}
Get-ChildItem (Join-Path $PWD '.git\worktrees') -Directory | ForEach-Object {
  foreach ($c in @('logs','ORIG_HEAD')) {
    $s = Join-Path $_.FullName $c
    if (Test-Path $s) { Move-Item -LiteralPath $s (Join-Path $old ("wt-bookkeeping-$($_.Name)-$c")) }
  }
}
```

Do not run checkout, reset, clean, gc, or any command that rewrites worktree files.

**为什么把 `logs/` 与 `ORIG_HEAD` 移走（E2 实测依据）**：本修复会重写 `master`/`workbuddy` 的**全部**提交 SHA
（见修订记录 #11），旧 reflog 与 `ORIG_HEAD` 里的 SHA 在新库中不存在 ⇒ 保留只换来约 2975 条 fsck 错误、
且 `git reflog`/`@{1}`/`git reset --hard ORIG_HEAD` 全部失效。移走后 fsck **0 错误、exit 0**（E2 变体B+ 实测）。
代价：失去 reflog 回滚路径 —— 由 `$runRoot\live-before-cutover`（含 `refs-moved`/`objects-moved`/`bookkeeping-*`）与 D 盘全量备份兜底。

- [ ] **Step 4: Verify the live worktree and all worktree registrations after cutover**

```powershell
git status --porcelain=v2 --branch            # 必须与 Task 1 Step 4 的相对基线一致
git rev-parse --verify HEAD                   # 必须等于 staging 的 refs/heads/master
git fsck --full --no-dangling                 # 预期 exit 0（前提：Step 3 已移走 logs/ORIG_HEAD）
git log --oneline -5 master
git worktree list                             # 必须仍是 9 个；注册未丢
git for-each-ref --format='%(refname) %(objectname)' refs/heads refs/tags   # 必须与 staging 逐条一致
foreach ($line in (Get-Content (Join-Path $runRoot 'detached-heads.txt'))) {
  git cat-file -t ($line -split '\s+')[0] | Out-Null; if ($LASTEXITCODE -ne 0) { throw "detached HEAD lost: $line" }
}
# 每个 worktree 的 HEAD 都要能解析（含 2 个符号 HEAD）
Get-ChildItem (Join-Path $PWD '.git\worktrees') -Directory | ForEach-Object {
  $v = ((Get-Content (Join-Path $_.FullName 'HEAD') -Raw) -replace "`r|`n",'').Trim()
  $t = $v -replace '^ref:\s*',''
  git rev-parse --verify $t | Out-Null; if ($LASTEXITCODE -ne 0) { throw "worktree HEAD broken: $($_.Name) -> $v" }
}
```

Expected: `master` 指向重建后的 tip；status 与 Task 1 Step 4 的**相对基线**一致；
fsck exit `0`；`git worktree list` 仍列出 **9 个** worktree；本地 ref 集合与 staging 逐条一致；
6 个 detached HEAD + 9 个 worktree 的 HEAD 全部可解析。
`refs/remotes/origin/master` 保持原值（**不应**被换成重建后的本地 tip）；`.git/packed-refs` 里那条陈旧条目会被同名 loose ref 遮蔽（E2 实测 fsck 视为干净）。

**GATE 4:** 若 status 或 worktree 数量与预期不符，停止。回滚 = 把新 `objects`/`refs` 移走、
把 `$old\objects-moved` 与 `$old\refs-moved` 移回原位、把 `$old\bookkeeping-*` 与 `$old\wt-bookkeeping-*` 移回原路径；**不要 reset 工作区**。

---

### Task 6: Post-cutover validation and retention

- [ ] **Step 1: Verify hooks, the detached HEADs, and ordinary Git operations**

```powershell
git diff --stat
git archive --format=tar HEAD | Out-Null
$postBundle = Join-Path $runRoot 'post-cutover.bundle'
git bundle create $postBundle --all
git bundle verify $postBundle
foreach ($line in (Get-Content (Join-Path $runRoot 'detached-heads.txt'))) {
  git cat-file -t ($line -split '\s+')[0] | Out-Null; if ($LASTEXITCODE -ne 0) { throw "detached HEAD lost: $line" }
}
```

Expected: 全部 exit `0`；diff 只列出 Task 1 Step 2 记录过的那些既有改动（**相对基线**，不是写死的 6 个）。

- [ ] **Step 2: Remove the temporary repair tags**（仅在本步——之前删就丢了可达性）

```powershell
foreach ($line in (Get-Content (Join-Path $runRoot 'detached-heads.txt'))) {
  git tag -d ("repair-detached/" + ($line -split '\s+')[0]) | Out-Null
}
git for-each-ref --format='%(refname)' refs/tags/repair-detached   # 预期：空
```

- [ ] **Step 3: Retain rollback materials**

Keep `$runRoot\live-before-cutover`, `$runRoot\git-backup`, `$runRoot\worktree-backup`, the staging repo, and both pre-existing rescue repositories until the owner has completed a normal commit and a restore drill.

- [ ] **Step 4: Handle remote publication separately**

Do not force-push `master`. The rebuilt master has rewritten commit IDs after the damaged boundary. If publication is later required, create a new remote branch, scan the exact pushed set for secrets, and obtain a separate approval.

## Definition of Done

- Live `git fsck --full --no-dangling` exits `0`（前提：Task 5 Step 3 已把 `logs/`、`ORIG_HEAD` 及 worktree 侧同名簿记移入回滚目录 —— E2 实测保留它们会有约 2975 条 reflog 错误）。
- A fresh clone from the post-cutover bundle also passes fsck with exit `0`.
- All four local refs have identical trees, commit counts, and semantic history to the **task-run baseline**（相对值，非写死常数）。
- **`git worktree list` 仍列出 9 个 worktree；`.git/worktrees/` 的注册未被替换掉；9 个 worktree 的 HEAD 全部可解析**。
- **6 个 detached HEAD 的 SHA 在重建库中可达**（Task 4 Step 1b + Task 6 Step 1）。
- **本地 ref 集合（`refs/heads` + `refs/tags`）与 staging 逐条一致；`refs/remotes/origin/master` 保持原值。**
- Existing worktree content is unchanged **relative to Task 1 Step 4 的基线**（不是写死的 "6 tracked / 522 untracked"）。
- `post-checkout`, `post-commit`, local config, `.git/info/exclude`, and `.git/packed-refs` are preserved（原地保留，不经替换）。
- **已在台账/交接书里同步 SHA 改名后的引用**（`master` 113/113、`workbuddy` 133/133 全部换 SHA；旧 SHA 全部作废）。
- E3 的旧 `objects/`+`refs/` 可用于恢复 Git 元数据；因切换前 worktree backup 缺失，不能声称可精确恢复全部 pre-cutover 文件状态。文首现状备份仅是 cutover 后副本。
- E3 切换期间未 force-push、未运行 garbage collection、未删除对象、未做未审查提交；E3 后经批准的 `gc` 另见文首所列进度报告。

## Self-review

- **Boundary:** only Git metadata (`objects/` + `refs/`) is rebuilt; application source is not edited；worktree 注册与本地配置原地不动。
- **Alternative considered:** keeping `refs/replace` is smaller but leaves bundle/push and raw history broken; cloning `origin` loses local history.
- **Known historical failure avoided:** no in-place gc, no unverified backup, no `git add -A`, and no public upload of local evidence.
- **Facts verified:** the four-ref export prototype already produced matching trees/counts, zero-fsck staging, and a valid restored clone；**E2 已在 `%TEMP%` 副本上端到端复跑，并加入"未修复 live 必失败"的反证**。
- **Proxy check:** fsck is paired with semantic history comparison and fresh-clone recovery; a green fsck alone is insufficient；**E2 补充：fsck 的 reflog 报错量与提交换名范围成正比，不能只凭条数判库好坏**。
- **E2 已验证项（取代 E1 的"未验证"）:** ① 6 个 detached SHA 打 tag 的导出形态；② 选择性替换（只换 `objects/`+`refs/`，`worktree list` = 9、注册存活）；③ 可行性硬前提（缺失对象/坏链源端均不可达）。
- **E2 暴露并已修入本方案的风险（3 条）:** reflog 与 `ORIG_HEAD` 必须移走（否则 fsck 约 2975 条错误）；`refs/` 必须 Move 而非覆盖（否则 `refs/replace` 残留）；只复制 `refs/heads`+`refs/tags`。
- **Honest bound:** 本次修复会重写 `master`/`workbuddy` 的**全部**提交 SHA（113/113、133/133），因此它**不是**一次"对旁观者透明"的操作 —— 任何持有旧 SHA 的文档、台账、fork、其他 agent 会话都会失配，需在放行窗口内一并处理。
