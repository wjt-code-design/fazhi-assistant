# 目录处置接手记录 + 远端可达集复核（2026-10-20）

> **先看这段再看表。**
> 我接的是 `2026-10-20-project-directory-disposition-inventory.md` 这条线。这一轮**只读**：没有移动、删除、改名、切换分支、写引用、跑产品/测试，也没读过 `.env`、私钥或任何数据库内容。
> **你要的答案在 §8**：44 只里能证明"**删了零损失、随时一条命令原样重建**"的有 **6 只**（`ai-legal-helper-005…009` 与 `-e9b0e17`，合计 **1.34 GiB**）；其余 38 只都不能用这条判据判掉，其中 1 只藏着一份向量库副本、2 只里面有从未进过 Git 的独有文档（明确别删），剩下 35 只的"能不能删"实质是"这些证据你还要不要回去看"。
> 另有三件事变了形状：① 撤工作树**不会丢提交**——11 个工作树的 HEAD 全被本地 ref 钉住了，而且钉它们的那批 `keep-detached-20260923/*` 标签是 09-23 就有人建好的（盘点报告只说"要保住提交"，没查这条前置其实已经完成）；② 真正能立刻搬走的是 **16 个没有任何在册文档指向的目录（逻辑 10.5 GiB）**，另 30 个搬了会把 `docs/` 里 handoff 的指针剪断，其中 `legal-agent-v1` 被 `CONTRIBUTING.md` 指着；③ 我在核"唯一副本在哪"时撞上一条**要推翻在册结论**的读数——含历史明文口令的那次提交，已经是远端分支 `origin/nondeploy-closeout-20261018` 可达集的一部分（见 §5）。这条不是我这轮能修的，只能你裁。
> 现在最紧的动机不是整洁，是 **C 盘只剩 27 GiB（95% 满）**——而 §8 那 6 只只换回 1.34 GiB，所以"删快照"本身解不了盘压。

## 0. 汇总（全部为本轮现量）

| 项 | 读数 | 怎么来的 |
|---|---:|---|
| C 盘可用 | 27 GiB（476 总量，已用 95%） | `df -h /c` |
| D 盘可用 | 849 GiB（932 总量，已用 9%） | `df -h /d` |
| 主仓 `.git` 真实占用 | 208 MB | `du -sh .git` |
| 主仓 `.worktrees` 真实占用 | 3.4 GB | `du -sh .worktrees` |
| 主仓工作树逻辑体积 | 8.60 GiB | 沿用盘点 JSON `logical_bytes_scanned` |
| 其余 46 个目录名逻辑体积合计 | 27.8 GiB | 同上 |
| 其中 B 档（无在册指针）逻辑体积 | **10.5 GiB** | §3 |
| 其中 A 档（有在册指针）逻辑体积 | 17.0 GiB | §3 |
| Git 工作树数 | 11（与报告一致） | `git worktree list` |
| 工作树 HEAD 被本地 ref 钉住 | **11／11** | §2 |
| 只在本地、不在 origin 的 ref | **13 条** | §2 |
| 主仓 M 脏条目 | 598（tracked 修改 21 ＋ 未跟踪 577） | `git status --porcelain \| wc -l`，与报告 21/577 相加一致 |
| **可证明"删了零损失"的快照目录** | **6 只／1.34 GiB** | §8：`status --porcelain --ignored` 输出 0 行 ＋ `diff --stat HEAD` 无输出 |

⚠️ 逻辑体积**不是**磁盘占用，也**不是**可释放容量。搬每一只之前要在移动现场单独量真实 `du`，本轮我主动中止了两条全量 `du`（见 §1 副作用）。

## 1. 接手边界：修复助手正在动什么，我不碰什么

本轮实测到的活体证据（不是推测）：

| 证据 | 读数 |
|---|---|
| 候选分支 tip 在盘点报告成文前后翻了一次 | `4ba4237`（18:07:56）→ `adf65d7`（18:39:05），ref 文件 mtime 18:39:07 |
| 盘点报告 §2 表里候选写的是 `4ba4237`，`git worktree list` 现在是 `adf65d7` | 报告自己承认"各目录不是同一瞬间的原子快照" |
| 修复助手 18:51 又落了一份新报告 | `docs/process-archive/reviews/2026-10-20-isolated-verification-and-residual-findings.md` |
| 远端新分支 ref 今天 18:49:47 落盘 | `.git/refs/remotes/origin/nondeploy-closeout-20261020` mtime |
| 本地 master 与 origin/master 是分叉不是落后 | 234 ahead ／ 204 behind（`git rev-list --count` 两个方向） |
| 候选 adf65d7 严格含本地 master | `git merge-base --is-ancestor 0b54396 adf65d7` rc=0；`--left-right --count` = `0 140` |

因此我这轮**自我约束**如下（写死，供别的会话核对）：

- 不编辑 `docs/**`、`reports/execution-runs/**`、`backend/**`、`frontend/**`——修复助手的写入面。
- 不动 `.worktrees/nondeploy-closeout-20261010`（候选树 C，18:39 还在产提交）。
- 不跑 `git gc`/`prune`/`repack`/`worktree prune`/`fetch`，不写任何 ref，不 `checkout`/`switch`，不暂存不提交。
- 所有只读 git 命令带 `GIT_OPTIONAL_LOCKS=0`。
- 不搬、不删、不改名任何一个目录（本报告只给分档和前置，执行等你点头）。

**我这轮的副作用（自报，不遮掩）：**

1. `git status --porcelain`（18:48）可能刷新了 M 的 index——它不改受版本控制的内容，但会让 index mtime 变。若别的会话拿 index mtime 当"树未变"的证据，会被我这一下干扰。
2. 起了两条磁盘遍历（44 目录 `du`、53111 只文本文件全文扫描）。`du` 在 95% 满的盘上和全文扫描互相抢 I/O，我把 `du` **中止**了，所以**真实磁盘占用没有逐目录数字**；全文扫描跑完了，结论见 §3。这两条都只读，但可能拖慢同时在跑的测试。
3. 本报告是 M 里**新增的一只未跟踪文件**。落盘后复量：`git status --porcelain` 仍是 **598 行（未跟踪条目 577）**——数字没变，因为 `docs/process-archive/reviews/` **整只目录本身就是未跟踪的**，git 把它折叠成一条 `?? docs/process-archive/reviews/`，我在里面加文件不增条目数。（我先前在草稿里写"577 变 578"，**此句作废**，以这条复量读数为准。）

## 2. 新事实一：提交保全轴——"保住提交"这条前置其实已经做完了

盘点报告 §2 给每个"归档代码候选"写的依据是"Git 当前干净；**保住提交及独有资料后**可撤掉完整副本"。它没查"提交现在保在哪"。我查了：

11 个工作树的 HEAD，**每一个都被本地 ref 指着**：

| 工作树 HEAD | 钉住它的 ref | 这条 ref 在 origin 上有吗 |
|---|---|---|
| `0b54396` 主仓 M | `refs/heads/master` | **没有** |
| `adf65d7` 候选 C | `refs/heads/codex/nondeploy-closeout-20261010` | 有（`origin/nondeploy-closeout-20261020`） |
| `fbc29e8` Codex 树 | `refs/heads/codex/local-candidate-closeout` | **没有** |
| `8aecf3e` legal-agent-v1 | `refs/heads/codex/legal-agent-v1` | **没有**（但是 keep 标签的祖先） |
| `3ba4aaf` −005 | `refs/tags/keep-detached-20260923/3ba4aaf` | **没有** |
| `b0c229d` −006 | `refs/tags/keep-detached-20260923/b0c229d` | **没有** |
| `ba8a569` −007 | `refs/tags/keep-detached-20260923/ba8a569` | **没有** |
| `dca9345` −008 | `refs/tags/keep-detached-20260923/dca9345` | **没有** |
| `30a865f` −009 | `refs/tags/keep-detached-20260923/30a865f` | **没有** |
| `e9b0e17` −e9b0e17 | `refs/tags/keep-detached-20260923/e9b0e17` | **没有** |
| `f369094` WorkBuddy | `refs/heads/master-e8826c5b` | **没有** |

两点结论：

- **撤掉那 8 只"归档代码候选"目录不会丢任何提交**——提交都在主仓 `.git` 的对象库里，被分支/标签钉着，而且钉它们的标签是 2026-09-23 就建好的（命名就叫 `keep-detached-*`，是前一轮有意做的）。报告里"保住提交后可撤"这句现在可以升级为"提交已保住"。
- **但这份保全只活在你这块盘上。** 13 条 ref 不在 origin（含 `master` 本身、全部 `keep-detached-*` 标签、`v1.0.0`）。`.git` 实测只有 **208 MB** ⇒ 做一次"全 ref 灾难副本"的成本是 200 MB 级、分钟级，不是我以为的大件。这条把 §6 的 C-1 从"要不要做"变成了"花 200 MB 就能关掉"。

## 3. 新事实二：指针轴——只有 16 个目录搬了不断链

盘点报告完全没有做这一步（它 §6 只说"未验证目录进程占用或任务归属"）。我按"谁在引用这只目录名"分了档。口径要先说清，因为这里我第一次的判断是**错的、后来被自己的第二次扫描推翻**：

- 第一次只扫 `master HEAD` 的受版本控制文件 ⇒ 得出"31 只无引用"。**这个结论作废**。
- 第二次把未跟踪、被 `.gitignore` 挡住的文本一起扫（`docs`、`reports`、`dispatch-output`、`diag`、`backend/scripts`、`scripts`、`tests`、`.qoder`，53111 只文本文件）⇒ **44 只目录全部被提到，零只无引用**。
- 第三次剔掉两类"假引用"：盘点报告自己（它把 44 只路径逐条抄了一遍，属于自引），和 `.workbuddy/memory/*`（会话记忆，不是 runbook）⇒ 才是下面这张能据以动手的分档。

口径：**46 个唯一目录名**（48 项去重，主仓自身除外）。A＝除了盘点报告外还有别的在册文档指向它；B＝没有任何在册文档指向它。

**B 档 16 只（逻辑合计 10.5 GiB）——搬之前不存在"剪断 runbook 指针"的问题：**

| 目录（在 `C:\Users\33393\Desktop\` 下） | 逻辑 | 盘点建议 | 是工作树 |
|---|---:|---|---|
| `fazhi-nondeploy-closeout-20261010-b4e7a2` | 7.24 GiB | 归档证据资料 | 否 |
| `fazhi-closeout-reviewfix-20261006` | 0.69 GiB | 归档证据资料 | 否 |
| `fazhi-local-closeout-20261006` | 0.50 GiB | 归档证据资料 | 否 |
| `fazhi-data-backup-20260919-b` | 0.38 GiB | 保留数据备份 | 否 |
| `fazhi-closeout-ui-profiles-20261007` | 0.37 GiB | 归档证据资料 | 否 |
| `ai-legal-helper-007` | 0.30 GiB | 归档代码候选 | **是**（只能 `git worktree move`） |
| `ai-legal-helper-009` | 0.30 GiB | 归档代码候选 | **是**（同上） |
| `fazhi-rescue-b820295-20260919` | 0.25 GiB | 保留历史包 | 否 |
| `fazhi-rescue-c362c91-20260919` | 0.25 GiB | 保留历史包 | 否 |
| `fazhi-rescue-dbc0f9b-20260919` | 0.25 GiB | 保留历史包 | 否 |
| `fazhi-closeout-scan-runlogs` | 0.00 | 归档证据资料 | 否 |
| `fazhi-dependency-preflight-20261004-…` | 0.00 | 归档证据资料 | 否 |
| `fazhi-next-plan-review-20261004-…` | 0.00 | 归档证据资料 | 否 |
| `fazhi-plan-handoff-review-20261004-…` | 0.00 | 归档证据资料 | 否 |
| `fazhi-project-closeout-20261008-…` | 0.00 | 归档代码候选 | 否 |
| `fazhi-release-preflight-20261008-…` | 0.00 | 归档证据资料 | 否 |

**A 档 30 只——搬了会剪断在册文档指针，本轮不该动。** 指针密度最高的四只（除盘点报告外的引用文件数）：

| 目录名 | 引用文件数 | 首个引用者 |
|---|---:|---|
| `legal-agent-v1` | 63 | `CONTRIBUTING.md`（受版本控制 ⇒ 改它要动 master 树，正撞修复助手） |
| `nondeploy-closeout-20261010` | 16 | `docs/process-archive/full-scope-decisions-20261018.md` |
| `fazhi-next-local-20261004-356f…` | 12 | `docs/process-archive/work-report-20261004-next-local-acceptance-review.md` |
| `fazhi-joint-candidate-20261003-ac70…`／`fazhi-local-candidate-20261002-6794…` | 各 10 | `docs/process-archive/dependency-model-chain-preflight-20261003.md` 等 |

`ai-legal-helper-bundles` 也在 A 档（8 只文件指着它，含 `dispatch-output/local-candidate-closeout-20260928/restore-candidate-ref.sh` 那条**恢复脚本**）——它是被当作恢复源来引用的，不是被当作历史记录。

## 4. 新事实三：历史包轴——6 只 bundle 里，只有 1 只是真自足副本

报告给"保留历史包"的依据是"含 Git bundle，集中保存并验证恢复"。我做了那一步"验证"：

| bundle | 大小 | head | `git bundle verify` | head 提交今天在本地可达吗 |
|---|---:|---|---|---|
| `fazhi-rescue-4465080-20260919/fazhi-master-4465080.bundle` | 129 MB | `ef214e57` | **okay，且"records a complete history"** | 可达（master／候选／origin 两条分支的祖先） |
| `fazhi-rescue-dbc0f9b-20260919/….bundle` | 129 MB | `09ed6800` | 未跑 | 可达 |
| `ai-legal-helper-bundles/local-candidate-closeout-fbc29e8.bundle` | 7.1 KB | `fbc29e8` | **需要前提 ref `aec8d5c2`** | 可达 |
| 其余 4 只 rescue bundle | 各 129 MB | 未逐一读 | 未跑 | 未测 |

三个后果：

1. 目录名里的 `4465080`／`dbc0f9b` 和 bundle 实际 head（`ef214e57`／`09ed6800`）**不是一回事**——按目录名去认"哪只包保哪个提交"会认错。
2. 那 7.1 KB 的小 bundle **不是灾难副本**：它带前提，脱离主仓 `.git` 打不开。要保 `fbc29e8` 得靠 §2 的本地 ref，或做一次全量重包。
3. 报告"验证恢复能力"这句对 6 只包整体仍未完成——我只跑通了 1 只。剩下 5 只要么补 verify，要么在搬之前先 verify。

## 5. 新事实四（要紧）：远端可达集里已经有那次明文写入

这是核"唯一副本在哪"时撞出来的，**会推翻一条在册概括结论**，所以先引原文再说读数。

在册断言原文（`docs/progress-handoff-report-20260925.md:444`）：

> **远端三重否证确认云端零存在**（tip 无此文件、引入它的 `817e7d3` 不可达 `origin/master`、blob 不在远端对象集）

其中"不可达 `origin/master`"这半句**到今天仍然成立**（我复测：该文件在 `origin/master` 的 tip 树里 ABSENT）。但"云端零存在"这个**概括**，用今天盘上的 remote-tracking ref 一测就不成立了：

| 现量 | 读数 |
|---|---|
| 明文所在 blob | `d59a7b614514445d617d55bb9e7dd581e2636805`（只取 id，**没读过内容**） |
| 引入提交 `817e7d3` 是 `origin/nondeploy-closeout-20261018`(=`17f0558`) 的祖先 | `git merge-base --is-ancestor` **rc=0** |
| 同一提交也是今天推的 `origin/nondeploy-closeout-20261020`(=`adf65d7`) 的祖先 | **rc=0** |
| 今天那次推送的增量 `ee5bfef..adf65d7` 里有没有再传它 | **0**（grep `^817e7d3`）⇒ 今天没新传，但也没挡住 |
| `origin/nondeploy-closeout-20261018` 这条 remote-tracking ref 怎么来的 | reflog：`17f0558 … fetch origin: storing head`，ref 文件 mtime **2026-10-19 18:36:44** ⇒ 服务端**当时已有**这条分支（不是本地自造） |
| 远端 tip 上那个文件还在不在 | **在**，但内容是改过的形状 `7ff65f0c…`；明文只在历史 blob `d59a7b61` 里 |

**我的判读（可驳）**：服务端存下 `17f0558` 这棵提交树时，`817e7d3` 的历史必然随之上去 ⇒ 明文 blob 应在那台远端的对象库内、可从该分支 `git log -p` 翻出。也就是说，"轮换排在推之前"这道闸，**已经被 10-19 之前那次推送越过去了**，不是被今天推的。

**我没跑成、因此不敢说死的部分**：服务器侧实测。**20:11 试过**：`GIT_TERMINAL_PROMPT=0 git ls-remote origin` → **rc=128 `Recv failure: Connection was reset`**；同分钟匿名 `curl` 到 `api.github.com/zen`（0.76s）与 `api.github.com/repos/wjt-code-design/fazhi-assistant`（1.40s）**都返回 200**，且不带 `--ssl-no-revoke` 也 200 ⇒ 这次不是 10-16 那条证书吊销老路，是 git 那条通道被重置。⚠️ 附带一条后果：**仓库能被匿名 API 读到** ⇒ 若它是 public，任何不需要凭据的人都能 clone 到那个历史明文。要钉死对象存在性，需要 `git clone --single-branch --bare --no-local <该分支> <空目录>` 后只查 blob id 在不在——**这条腿今天没通，按值反查也没做**；对远端可达集的值级反查仍是在册那句"已发布面从未值级反查"。

**为什么这条只能你动**：轮换口令、删/重建远端分支、或显式接受"已暴露"，都不在目录处置的授权面里，而且 §6 那条已裁顺序（`Q4 轮换 → 复扫 → Q6 一次性快照分支`）要改也得你改。

## 6. 决策台账（按"谁动"分档；每条一词可答）

推荐那列是我的意见，你回"按推荐"就是整包接受，包括各条写明的连带后果。

### 6.1 只能你动（我做不了）

| 编号 | 事项 | 一词可答的形式 | 我的推荐 |
|---|---|---|---|
| Y-1 | §5 那条远端明文。**反查那一问已答已执行**（20:11 选「先联网反查」，结果见本行末）；现在待你答的是**下一问**：要不要按"已暴露"轮换口令 | 答 `轮换`／`等通道通再钉死`／`先放` | **等通道通我再钉死一次**（一条 `clone --single-branch --bare` 到空目录即可判死；git 腿今天 rc=128 连接被重置，而匿名 HTTPS API 通＝仓库可被匿名读到，这条把严重性抬高一级），钉死后无论结果如何都轮换 |
| Y-2 | 桌面唯一法智入口选哪只 | 答 `M`／`C`／`等新候选` | **等新候选验收**，这条不改（报告的原意：不按目录名/分支名/提交日期替你定） |
| Y-3 | C 盘要不要继续腾 | 答 `腾`／`不腾` | `腾`，且只从 B 档腾——见 C-2 |

### 6.2 我能做，等你一个词

| 编号 | 动作 | 前置（写死） | 一词 | 推荐 |
|---|---|---|---|---|
| C-1 | 全 ref bundle → `D:\fazhi-big\`（约 200 MB，实测 `.git`=208 MB） | 只读 `.git`，不写任何 ref；产物含 §5 那个历史明文对象 ⇒ **落 D 不改变"未公开"状态，但盘上多一份明文副本**，这是你要的连带后果 | `做`／`不做` | **做**。它把 §2 那 13 条 local-only ref 的"盘死即丢"关掉，是本轮单位成本最低的一件事 |
| C-2 | B 档 16 只里**非工作树**的 14 只，复制到 `D:\fazhi-archive\`，逐只 `du` 实测＋字节核对后再删源 | 搬前逐只现量真实占用；`fazhi-data-backup-20260919-b` **先不碰**（它是"保留数据备份"，恢复能力未验证）；跨盘不是原子操作 ⇒ 一律"复制→校验→删源"，不用 `mv` 一把梭。**⚠️ 本节 §8 出来后，这 14 只的默认动作应是"先测独有性再决定删或搬"，不是搬了就算收口** | `开工`／`等` | **等**，且等的期间先跑 §8 第三类那把"独有性哈希"尺（只跑最大三只，单只超 8 分钟降级报未测） |
| C-3 | B 档 2 只工作树（−007／−009）用 `git worktree move` 迁到 D | 要写 `.git/worktrees` 管理文件＝共享状态；须先确认无进程占用 | `做`／`不做` | **改成直接删，不搬**（§8 已证 −007／−009 与 −005／−006／−008／−e9b0e17 同为零损失档，`git worktree remove` 一步撤掉，省 0.6 GiB 且不留悬空登记）。搬迁只对"还想留着现场"的目录才有意义 |
| C-4 | 给 A 档 30 只做一份"指针搬迁对照表"（哪只目录、被哪份文档、第几行引用） | 纯读，不动文件 | `要`／`不要` | **要**。这是解 Y-2 之后唯一能让 A 档也搬走的路径；等真要搬时就不用重扫 |

### 6.3 已转票／不在本轮

| 编号 | 事项 | 为什么不在我这轮 |
|---|---|---|
| N-1 | 4 只"保留工作副本"的未提交修改保存 | 修复助手正在写 M（598 条脏）和候选树 C（18:39 还在产提交）。现在采，采到的是中间态 |
| N-2 | 27 只"归档证据资料"的**独有资料**判定 | 报告说"选定源码相同不代表整目录重复"，但反过来"没比对过的部分是否独有"也没测。要测得逐只哈希，与 C-2 合并做更省 |
| N-3 | 前端真机验收、C03 口径、R22 在途撤回动态证据 | 那是修复/验收线的待办（`2026-10-20-isolated-verification…` §6 列的），不归处置线 |
| N-4 | 5 只未 verify 的 bundle | 并入 C-2 的搬前检查，不单独跑 |

## 7. 未跑的读数（不写进任何"已达标"）

- 真实磁盘占用：只测了 `.git`（208 MB）和 `.worktrees`（3.4 GB）。**44 只 Desktop 目录一只都没测到**（遍历被我中止）。所有体积数字都是盘点的逻辑大小。
- 进程占用／任务归属：未测。沿用报告原话——不把"没查到占用"当"没有占用"。
- 凭据：没读 `.env`、没读任何文件内容、**没做按值反查**（20:11 按你指示改跑"联网反查"那条腿，结果见 §5 末与 §6.1 Y-1：git 腿不通、API 腿通）。§5 只取 blob **id**。
- 远端：**没 fetch、没 clone 空库**；`git ls-remote` 跑过但 **rc=128 失败**，所以 §5 的存在性读数仍来自**本地 remote-tracking ref**＋协议性质推论，不是服务器侧实测。
- 恢复演练：除 `4465080` 那只 bundle 外没做过任何恢复验证；两只"保留数据备份"未验证可恢复。
- 测试／构建／产品／模型／迁移：一律未跑。M 的 598 脏条目里有多少是修复助手的在途改动，我没分类。

## 8. Owner 复问后补的一节：直接回答"哪些能安全删"

Owner 2026-10-20 19:5x 把诉求收窄为"这些快照有没有可以安全删除的"。**删除的判据比"搬到 D 盘"更硬**：上一节 A/B 分档回答的是"搬走会不会让文档指针指空"，本节回答的是"删掉会不会永久丢东西"。二者口径不同，本节只认一条：**这个目录的每一个字节，能不能从别处原样重建**。

判据（本轮实测，全部只读）：`git status --porcelain --ignored` 输出 **0 行** ＋ `git diff --stat HEAD` **无输出** ⇒ 该工作树里既无改动、也无未跟踪文件、**连被忽略的文件都没有** ⇒ 整个目录＝它 HEAD 那个提交的可重建视图；而那个提交被 ref 钉着（见 §2）。

⚠️ 与 §3 的口径关系要说明，两节不冲突但判的是不同的事：§3 的 A/B 回答"**搬走**会不会让在册文档的指针指空"，本节回答"**删掉**会不会永久丢字节"。所以 −005、−006、−008 虽属 A 档（现量引用者：−005 被 `docs/process-archive/progress-handoff-report-20260925.md` 等 2 份提到，−006 与 −008 各被 `diag/PROGRESS-20260905.md` 提到 1 份），删除仍是**零数据损失**——代价只是那份旧进度文档里那三行地址会指空。这一层要不要一并处理（在那份文档里补一句"已撤，可从 `keep-detached-*` 标签重建"），归 §6.2 的 C-4。

| 目录（`C:\Users\33393\Desktop\`） | HEAD | 钉住它的 ref | 逻辑 | 判定 |
|---|---|---|---:|---|
| `ai-legal-helper-005` | `3ba4aaf` | `refs/tags/keep-detached-20260923/3ba4aaf` | 152.2 MiB | **可安全删** |
| `ai-legal-helper-006` | `b0c229d` | 同上 `…/b0c229d` | 301.5 MiB | **可安全删** |
| `ai-legal-helper-007` | `ba8a569` | 同上 `…/ba8a569` | 302.9 MiB | **可安全删** |
| `ai-legal-helper-008` | `dca9345` | 同上 `…/dca9345` | 304.3 MiB | **可安全删** |
| `ai-legal-helper-009` | `30a865f` | 同上 `…/30a865f` | 304.4 MiB | **可安全删** |
| `ai-legal-helper-e9b0e17` | `e9b0e17` | 同上 `…/e9b0e17` | 2.3 MiB | **可安全删** |
| 合计 | | | **1.34 GiB** | 随时可用 `git worktree add` 从标签原样重建 |

三条必须一起交给你的限制，缺一条这条判定就不成立：

1. **撤的方式要走 Git**，不能当普通文件夹拖进回收站：这 6 只是**登记在册的工作树**（`git worktree list` 里有条目），硬删目录会在 `.git/worktrees/` 留下悬空登记。正确形状是先 `git worktree remove <路径>`（或先 `git worktree move`），**且不许顺手动 `keep-detached-*` 标签**——标签一删，"可重建"就没了。
2. **体积收益很小**。这只解决 1.34 GiB。C 盘现量剩 27 GiB，大头不在这些快照：主仓逻辑 8.6 GiB、`.worktrees` 真实 3.4 GB（本轮 `du` 实测）、27 只证据目录逻辑 27.8 GiB。⚠️ 快照目录的**真实**磁盘占用本轮仍未测到（两条全量 `du` 被我中止，见 §1 副作用与 §7）。
3. **剩下 38 只不能用这条判据**。分三类：

| 类别 | 数量 | 为什么判不了 / 怎么处理 |
|---|---:|---|
| 灰区：代码树干净但藏了未入册数据 | `C:\Users\33393\.codex\worktrees\local-candidate-closeout\ai-legal-helper` 1 只 | tracked 干净、未跟踪 **0**，但被忽略条目里有 `backend/chroma_db/`（向量库副本，**不在提交里**）＋ `frontend/node_modules/`、`.next/`、各级 `__pycache__/`、`build-id.txt`。删了不丢代码，**丢那份库副本**。要删先判它在别处有没有副本 |
| 明确**别删**：里面有从未进过 Git 的独有文档 | `legal-agent-v1`（`?? release-evidence/`）；`C:\Users\33393\WorkBuddy\Worktrees\ai-legal-helper\master-e8826c5b` | WorkBuddy 那 6 条未跟踪是 `docs/code-review-2026-09-22.md`、`docs/fix-baseline-2026-09-22.md`、`docs/git-repo-repair-runbook.md`、`docs/handover-2026-09-22.md`、`docs/progress-report-2026-09-23.md`、`docs/review-evidence-2026-09-22/` ⇒ **删了就没了**。先保存这几只再说删 |
| 27 只证据／评测目录 ＋ 2 只数据备份 ＋ bundle | 36 | 技术上都不可重建。"能不能删"＝"这些证据以后还要不要回去看"，是你的判断。要把它变成可判的数，只做一件事：**按文件哈希查独有性**（该文件在其余 43 只目录和 Git 对象里有没有同样字节的那份）。全跑估计 10–20 分钟读盘，会和修复助手的测试腿抢 I/O；建议只对最大的三只先跑（`fazhi-nondeploy-closeout-20261010-b4e7a2` 7.24 GiB、`fazhi-closeout-reviewfix-20261006` 0.69、`fazhi-local-closeout-20261006` 0.50），单只超过 8 分钟即降级报"未测"，不出"可删"结论 |

⚠️ 我这轮**没有删任何东西**。上面 6 只的删除动作要么我给你逐条命令、要么你点头我代做——两种都要在删之前现场再跑一次那条 `status --porcelain --ignored` 判据（会话之间会插进新改动，18:39 到现在候选 tip 已经翻过一次）。

§5 那条明文远端的事与"能不能删"**互不阻塞**，已按 Owner 指示停在"待联网反查"：20:11 实测 `git ls-remote origin` **rc=128 Recv failure: Connection was reset**，而同分钟匿名 `curl https://api.github.com/zen` 与 `…/repos/wjt-code-design/fazhi-assistant` **都返回 200**（不带 `--ssl-no-revoke` 也 200，所以这次不是证书吊销那条老路）⇒ **git 那条道今天不通，HTTPS API 通**；仓库可被匿名 API 读到这件事本身，已经把"暴露面"的严重性抬高一级。这条留给你，不在我这轮动手面里。

### 8.1 删前危害复核（Owner 要求"删之前再确认一遍有无危害"，20:15–20:2x 实测）

七项检查，全部只读。**没有执行任何删除。**

| # | 查什么 | 读数 | 排除了哪种危害 |
|---|---|---|---|
| 1 | 逐文件哈希对提交（**不信 git**，我自己 `sha1("blob "+len+NUL+bytes)`） | 六只全量 **4,045 个 blob**：`MISSING=0`、`content_diff=0`（−005 565／−006 674／−007 761／−008 848／−009 867／−e9b0e17 330） | 排除"文件被改过或已缺失，而 git 因索引陈旧说干净" |
| 2 | 会不会是**假绿尺子**：`assume-unchanged`／`skip-worktree` 标记、`status.showUntrackedFiles=no`、`core.fsmonitor` | 六只全部 `flagged=0`、两项配置为空 | 排除"git 被配置成看不见改动" |
| 3 | 尺子**能不能红**（负控） | 同一条哈希跑 WorkBuddy（2,446 blob）与 `legal-agent-v1`（324 blob）：`MISSING=0 content_diff=0`，但它们的 `status` 报出未跟踪件（前者 6 条独有文档、后者 `release-evidence/`）⇒ 哈希管"少/改"、`status` 管"多"，两把尺方向正交且都咬得住 | 排除"这条判据根本测不出问题" |
| 4 | 提交是否真被钉住、对象是否齐（浅克隆会让"可重建"落空） | `no .git/shallow`；六个 `keep-detached-20260923/*` 都能解析，`ls-tree -r` 文件数与盘上一致（565/674/761/848/867/330） | 排除"标签是空壳／历史被 graft 剪短" |
| 5 | 有没有别的会话**故意占着/锁着** | `git worktree list --porcelain` 六只都只有 `detached`，**无 `locked`、无 `prunable`**；六只目录内 `locks=0`；`HEAD` mtime 停在 **09-06**、`index` mtime 齐刷刷 **09-22 18:50–18:51**（一次脚本化操作留下的），目录 mtime 09-06 ⇒ 4 周没被碰 | 排除"某会话正在这里面干活" |
| 6 | 有没有**代码或清单**按路径依赖它们（删了会打红灯／让校验脚本失效） | 在 53,111 只文本文件（含未跟踪与被忽略）里，六只名字的引用**全部是 `.md` 散文**，机器可读件（`.json`/`.py`/`.sh`/`.ts`）**0 条**；tracked 侧只有 `diag/PROGRESS-20260905.md`、`docs/process-archive/progress-handoff-report-20260925.md` 两处散文 | 排除"删了会让某个测试／证据清单跑不起来" |
| 7 | 真实收益 | `du -sh` 逐只实测：154M＋304M＋305M＋307M＋307M＋3.1M ＝ **1.35 GiB**（与逻辑体积吻合，因为这六只里没有依赖目录）；C 盘现量仍 27 GiB／95% | 排除"搬了个寂寞还以为解了盘压"——它只回 1.35 GiB |

**残留危害（这四条消不掉，只能在删的时候一并处理）：**

1. **两处散文指针会指空**：`diag/PROGRESS-20260905.md`（提到 −006／−008／−e9b0e17 等）与 `docs/process-archive/progress-handoff-report-20260925.md`（提到 −005）。它们是 **tracked 文件** ⇒ 补一句"已撤，可从 `keep-detached-*` 标签重建"就是改 master 树，正撞修复助手的提交窗口。**建议**：删的时候先不改文档，把这两处指针作废信息记进本轮台账，等他们交付后一笔补上（或你把这一笔算作可提交的小改动单独授权）。
2. **"重建出来字节完全一样"这句要打折**：盘上是 **CRLF**、提交里是 **LF**（`core.autocrlf`／`.gitattributes` 在起作用——哈希读数里 `crlf_only` 占九成即此）。同一台机、同一份配置重建结果一致；换机器或换 eol 配置重建，**内容等价但原始字节不同**。若将来要拿"当年那批字节"当证据，这条判据给不了。
3. **"可重建"只靠那六个轻量标签活着**：轻量标签一被 `git tag -d` 就断，而盘点报告 §5.4 恰恰写着清理前要"确认提交历史已经保存"——将来别的会话若把标签当垃圾清掉，这六只的提交就真的没了。**建议**：删之前先跑 §6.2 的 C-1（全 ref bundle → `D:\fazhi-big\`，208 MB 级），并把六个 SHA 落进本文件；这样锚点从"一个标签"变成"标签＋盘外副本＋书面记录"三重。
4. **`git worktree remove` 会写共享的 `.git/worktrees/`**：与修复助手正在进行的 git 操作可能抢锁。**建议执行形状**：逐只串行、每条带 `-c gc.auto=0`、每只删完立刻复跑判据 1 的那条哈希思路（改成对标签跑），**并且先只删 1 只（最小的 −e9b0e17，3.1 MB）做回退演练**——用 `git worktree add <临时路径> refs/tags/keep-detached-20260923/e9b0e17` 把它原样加回来、哈希比对通过，再动其余五只。演练失败就整批停手。

未测/测不到的：进程句柄级占用（无管理员权限，只能靠 mtime＋锁＋登记状态这三条间接证）；8 个 root 之外的未跟踪代码文件里是否有路径依赖（tracked 侧已全量扫过，测试代码是 tracked，风险低但没归零）。

### 8.2 回退演练已执行（Owner 令"先演练最小的那只"，20:3x–20:4x）

对象：最小的 `ai-legal-helper-e9b0e17`（330 blob／`du` 实测 3.1 MB）。形状是**完整回路**：删 → 用轻量标签在原路径重建 → 逐文件哈希比对，**净变化为零**（这只现在就在桌面上）。

| 步 | 动作／读数 | 结果 |
|---|---|---|
| 0 | 主仓 `.git` 在飞锁数 | **0**（避开了修复助手的提交窗口） |
| 1 | 删前判据 `status --porcelain --ignored` | **0 行**；`tag_sha=e9b0e17…ccaed` |
| 2 | 删前逐文件哈希（尺子＝先按原样比，不中再把 CRLF→LF 比） | 330 只＝`exact 4 ＋ crlf_only 326 ＋ DIFF 0`；清单指纹 `24f4a682c5ab864f` 存 `%TEMP%\e9b0e17_manifest_v2.json` |
| 3 | `git -c gc.auto=0 worktree remove <路径>`（**不带 `--force`**，脏就应被拒） | `rc=0` |
| 4 | 删后核对 | 目录 `NO`；`git worktree list` 不再含它；`.git/worktrees/ai-legal-helper-e9b0e17` **无残留登记**；`keep-detached-20260923` 标签数 **6/6 完好**、SHA 未变；M `porcelain=598` 未变；候选 tip `c18ea8a` 未被我碰到 |
| 5 | `git -c gc.auto=0 worktree add <同一路径> refs/tags/keep-detached-20260923/e9b0e17` | `rc=0`，自动进 **detached HEAD**（与原状态一致），`HEAD=e9b0e17…ccaed`，`du` 3.1M，工作树总数回到 **11** |
| 6 | 重建后逐文件哈希 ＋ 与删前清单对账 | `exact 4 ＋ crlf_only 326 ＋ DIFF 0`；`TREE_SAME_AS_PREDELETE=True`；`PER_FILE_MATCH_SAME=True`；`DIFF_FILES=[]`；**指纹一致 `24f4a682c5ab864f`**；`status --porcelain --ignored` 仍 **0 行** |

**演练中我自己造的一把假尺子（如实记）**：第 2 步之前我先建了另一版清单，逻辑是**无条件**把 CRLF 归一化后再哈希 ⇒ 报出 `327/330`，即"3 只文件对不上"，我当场据此怀疑"有人在两次测量之间改了这只目录"并**叫停了演练**。真相是：**那 3 只是 PNG 二进制**（`frontend/public/apple-touch-icon.png`、`icon-192.png`、`icon-512.png`），原样哈希与库里 blob **逐位相同**，`git hash-object` 第三方也一致；是二进制数据里碰巧出现的 `0D 0A` 字节对被我的归一化改坏了。⇒ 教训：**换行归一化只能作为失败后的回退支路，绝不能当第一选择，也不能施加在二进制上**；"两把尺读数不一致"时先归因再动手，我这次是靠第三个仪器（`git hash-object`）才把它判成假红。修尺后才是上面那条 `DIFF 0`。

演练还证实了两条：`worktree remove` 会连登记一起清干净（不会留悬空），`worktree add <路径> <轻量标签>` 复原出的正是"detached HEAD ＋ 零未跟踪 ＋ 零被忽略"这种形状。**没被复原**的只有该工作树 index 的 stat 缓存时间戳（内容无关）。

**df 粒度读不到收益**：删这 3.1 MB 前后 `df -h /c` 都显示 450G 已用／27G 可用——五只大的加起来 1.35 GB，在这个粒度上才会开始可见。



## 9. 复现命令（逐条可跑；请在 `C:\Users\33393\Desktop\ai-legal-helper` 下、先 `export GIT_OPTIONAL_LOCKS=0`）

```bash
df -h /c; df -h /d
du -sh .git .worktrees
git worktree list
git for-each-ref --format='%(objectname) %(refname)' refs/heads refs/tags refs/remotes | sort
git merge-base --is-ancestor 817e7d3 17f055843aa30b95bdfc33a7522b5c4ab3e47594; echo rc=$?
git rev-list --objects ee5bfef..adf65d7 | grep -c '^817e7d3'
git ls-tree 17f055843aa30b95bdfc33a7522b5c4ab3e47594 -- dispatch-output/t12-frontend-sweep-20260920/apply_case_domain_gate.py
git reflog show origin/nondeploy-closeout-20261018
git bundle verify "C:/Users/33393/Desktop/fazhi-rescue-4465080-20260919/fazhi-master-4465080.bundle"
git bundle list-heads "C:/Users/33393/Desktop/ai-legal-helper-bundles/local-candidate-closeout-fbc29e8.bundle"
# §8 的"可安全删"判据，逐只跑（输出必须是 0 行）＋ 树未被改动复核
for d in 005 006 007 008 009; do
  p="/c/Users/33393/Desktop/ai-legal-helper-$d"
  echo "$d status_lines=$(git -C "$p" status --porcelain --ignored | grep -c .) diff_empty=$(git -C "$p" diff --stat HEAD | grep -c .)"
done
# 网络腿（20:11 实测：git 不通、API 通）
GIT_TERMINAL_PROMPT=0 git ls-remote origin; echo rc=$?
curl -s -o /dev/null -w '%{http_code}\n' --ssl-no-revoke https://api.github.com/zen
```

分档证据（A/B 归类与逐目录引用者清单）落在本机：
`C:\Users\33393\AppData\Local\Temp\fazhi_pointer_split.json`（临时目录，会被清；要长存就得你点头我才能往 `D:\fazhi-big\` 复制）。

---

**这份文件本身是本轮唯一新增产物。** 我接手的是处置线，不是修复线；§5 那条越过了我的授权面，所以只报不动。
