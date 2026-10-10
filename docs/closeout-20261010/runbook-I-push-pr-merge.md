# I 执行卡：推送 → PR → 合并（2026-10-10，读数全为现量；**本会话未执行其中任何一步**）

状态：**未执行**。这张卡的用途是让"按回车"这件事变成一串有前置/后置读数的步骤，而不是一段口头承诺。
按你批准它之前，我不碰远端、不动 ref。

## 0. 现状读数（写卡之前当场量的）

| 项 | 现量 |
|---|---|
| 本地相关 ref（**03:2x 现量**） | `master=0b54396`(234 笔)、`codex/nondeploy-closeout-20261010=`**`fc7ebf6`**(241 笔；含 5 笔代码 + 2 笔 docs 入册)、`codex/local-candidate-closeout=fbc29e8`(193)、`refs/remotes/origin/master=15562fc`(192，**陈旧**)、`refs/closing/remote-master=985d53e`(204，**远端真实头**，我 fetch 后已把 origin/master 复原回 15562fc)、`refs/closing/orphan-snapshot-20261011=1b1c307…`(1 笔，无父)。旧行写的是 `3f605de`(238)，已过时两笔 |
| `merge-base master origin/master` | **NONE**（rc=1）⇒ 本地主线与远端跟踪的那支**无共同祖先** |
| 普通推候选分支的对象数 | **4301**（含 13 位历史裸值，`value_hits=1`） |
| `master` / `codex/local-candidate-closeout` 的对象数与值命中 | 4252 / 3815，各 `value_hits=1`（都含它 ⇒ 817e7d3 是共同祖先） |
| 无父快照（§7 那条腿） | 2581 对象，`value_hits=0`，树 == `HEAD^{tree}`，pack 已冷恢复读回 |
| `fbc29e8` | 可解析，但**不是 master 的祖先**；`git grep -o fbc29e8` 现量 **103 次引用 / 15 个文件** |
| 远端网络轴（**10-11 01:5x 已复测，覆盖 10-10 那句**） | **四条全通**：`api.github.com` 200、`github.com` 200、`ssh -p 443` 认证 OK、`git ls-remote --heads origin` rc=0。⇒ 昨天那句"远端读数今天一律读不到"**作废**，真实读数见下两行 |
| 远端真实头 / 可见性（10-11 现量） | 远端**只有 `master` 一支** = `985d53e4ee81efc066cc6915abcba98954e7d408`（2026-09-17 15:15，**该对象不在本地库**）；仓库 **public**（`private:false`，size 130,655 KB，star 1）。本地 `origin/master`=`15562fc`（08-25）**比远端旧**，且与候选 `merge-base` 空（rc=1，239 笔 vs 192 笔） |
| 远端 CI 现状（10-11 现量，`/actions/runs?per_page=40`） | `total_count=18`：**17 场 `push` 全 `failure` + 1 场 `dispatch` success**（#1，08-08）；**`pull_request` 0 场**。最新那场（#17）红在**唯一一步**：Backend job step 7 `ruff format --check .`（Frontend job 绿）。⇒ **主线自己就是红的，别把"CI 红"当候选的判决**；也⇒ **任何"CI 全绿"的说法在远端从未成立过** |
| ⚠️ 触发语义（**这条改变了"推了就验证了"的假设**） | 候选 `HEAD:.github/workflows/ci.yml` 的触发段 = `on: push: branches: [main, master]` + `pull_request:`。⇒ **普通推 `codex/nondeploy-closeout-20261010` 不触发任何 CI**。要远端读数只有：开 PR（历史 0 场，且无共同祖先时合成 merge ref **可能压根不调度**）、或事后 `workflow_dispatch`（只认**默认分支上那份**定义 ⇒ 量的不是我这棵树的改动）。三条硬前置里"拿远端读数"这一条现在必须写成**主动动作**，不会自己发生 |

## 1. 三条硬前置（缺一条就别往下走）

1. **D-5 的答案**（(a) 先轮换 / (b) 孤儿快照 / 先不推）。
2. **远端真实头未知**：TLS 不通 ⇒ 我没法确认远端 master 现在是哪枚、有没有分支保护、Actions 是否启用。
   ⇒ 卡里凡依赖这些的步骤都写成"需 Owner 在页面确认"，不写成我已完成。
3. **文档引用悬空这件事要先定策**：`fbc29e8` 不在 master 里，103 处引用指向的对象远端将不存在。
   合并不解决它，`--no-ff` 也不解决它——**要么把那 4 笔独联提交一起推，要么接受引用在远端不可解析并登记**。
   现量：`git rev-list --count codex/nondeploy-closeout-20261010..codex/local-candidate-closeout` = **4**。

## 2. 路线 A（对应 D-5(a)：先轮换，再普通推 + 开 PR）

| 步 | 命令（形状） | 前置读数 | 后置读数（必须打印） |
|---|---|---|---|
| A0 | 三条网络探测：`curl api.github.com/meta`、`curl github.com`、`ssh -p 443 -T git@ssh.github.com` | — | 三条各自 rc；若仍 rc=35 ⇒ 后续"远端读数"步骤全标"需 Owner 页面确认" |
| A1 | **你**在供应商控制台轮换 `ADMIN_PASSWORD`（我不碰外部账户） | 现役值长度/来源不进日志 | 你口头确认"已轮换"；我不读 `.env` 去核 |
| A2 | `git push ssh://git@ssh.github.com:443/wjt-code-design/fazhi-assistant.git codex/nondeploy-closeout-20261010:codex/nondeploy-closeout-20261010`（HTTPS 轨今日同样可用：`git ls-remote` rc=0） | 前置三条现量：① 分支头**不再是 `3f605de`**，以当场 `rev-parse` 为准；② 工作树 `porcelain=0`（旧写「tracked 脏仍 5 只」已过时，那 5 只已进第 5 笔）；③ **若走 D-5(b) 无父快照路线，推送前必须先重跑 `evidence/orphan_pin.py` 并当场比对 `HEAD^{tree}` == 新快照 tree**（03:2x 实测：存放着的旧快照会被后续任何提交打破，这条正是独立复核 C §2.1 抓出的缺陷） | `git ls-remote` 同一内联 URL ⇒ 新 ref 出现且 sha 一致；**新分支创建，天然非 force** |
| A3 | （可选，解 A1 前置 3）`git push … codex/local-candidate-closeout:codex/local-candidate-closeout` | 现量 4 笔独联提交 | `ls-remote` 该 ref；**不新增凭据外泄**（值命中在候选里已是 1） |
| A4 | 定 PR base：远端 master 与本地 disjoint ⇒ 直接对远端 master 开 PR＝整树级 diff 且 checks 可能不调度。正路是先合一次 unrelated 历史：`git merge --allow-unrelated-histories origin/<远端真实头>`（**内容冲突要逐个解，不许 discard**） | 远端真实头 sha（需 Owner 页面提供，我今天读不到） | merge 后 `git rev-list --count` 增量、`git status --porcelain` 仍只那 5 只、全量门禁重跑 |
| A5 | 开 PR（base＝远端 master） | A4 完成或 Owner 选择不做 A4 | PR 号/URL 由 Owner 给；**PR 的 checks 跑在合成 merge ref 上**，无共同祖先时可能压根不调度（在册） |
| A6 | 合并用 **`--no-ff`**（禁止 rebase/squash） | 门禁复跑读数 | 合并提交 sha；`git log --oneline -5`；文档引用链保持（A3 若做了） |
| A7 | 推 master：`git push … master:master` | **必须是 fast-forward**；若被拒 ⇒ **停**，不 force（红线） | `ls-remote` master sha == 合并提交 |

## 3. 路线 B（对应 D-5(b)：无父快照）

已做完的准备：快照 `5df5a1277f…`（2581 对象、树等于 `HEAD^{tree}`、**按值 0 命中**、pack 冷恢复读回）。
它**按构造**把凭据外泄变成不可能，但三件事不解决，必须在决策时一起看：
1. **PR 路按构造关闭**（无父对象不与任何 base 共享祖先）——**这条不变**。但**今天新读到的两件事改写了另一半推理**（原句"今天 (a) 也拿不到（TLS）"**作废**）：
   ① 网络四条全通 ⇒ 普通推 (a) **推得动**；② 但**推 `codex/*` 分支不触发 CI**（`ci.yml` 的 push 白名单只有 `[main, master]`），而远端 `pull_request` 历史 **0 场**。
   ⇒ **两条路线今天都"拿不到第三方 CI 读数"，但原因换了**：不再是"网络不通"，而是"触发语义不覆盖我"。
   要拿到读数必须**额外做一个主动动作**（开 PR 或 dispatch），而开 PR 对 (b) 无父快照这条路仍然按构造不可能 ⇒ **(a) 与 (b) 的相对代价基本没变，(b) 依旧小**；变的是"想验证就得先花一次 PR/dispatch 动作"这件事，两边都要花。
2. `ci.yml` 触发要按 compare 分流/偏离 ⇒ 推上去的 CI 形状与主线不完全一致，D2 若引用它必须加注。
3. **文档 103 处引用仍悬空**（B 不含任何历史）。

## 4. 红线（任何一条被触发就停，不许"顺手绕"）

不 force push、不改写历史、不 `--no-verify`、不绕分支保护、不把 `master` 推成需要 force 的形状、
不在未确认远端真实头时假设 fast-forward、不为了让某步绿而删引用或改文档来掩盖悬空。
被拒即停 + 保留原读数 + 回报 Owner。

## 5. 我现在就能替你做、且零风险的准备

- 把 A2/A3 的 `--dry-run` 版跑成"只算不推"的对象体量读数（`git bundle` / `rev-list --objects`，已具备）。
- 把 A4 的 unrelated merge 在**副本树**里试演一次，把冲突面量出来给你看（不碰候选树、不碰 ref）。
  这条是唯一能提前回答"合并会不会很难"的仪器。要我做我就做。

## 6. A4 的冲突面**已量出来**（纯只读，零副本、零 ref、零 I/O 压力）

`git merge-tree` 没有 `--allow-unrelated-histories`（直接 rc=128 `refusing to merge unrelated histories`），
但它接受 `--merge-base=<空树>` ⇒ 用空 base 试演 disjoint 合并。
**「空 base ≡ 真 merge」这个等价性已证**（`evidence/equivalence_check2.py`，`VERDICT=EQUIVALENCE_PROVEN`）：
两枚无父根 + 三文件 fixture（`f_same` 同内容 / `f_diff` 异内容 / 各自独有文件），预登记期望冲突 **1**；
空 base `merge-tree` = **1**，**全新克隆**里真 `merge --allow-unrelated-histories --no-commit` 的未合并文件（`git ls-files -u` 去重）= **1**，两法一致。
⚠️ 走到这一步之前我的 fixture **错过三次**，每次都靠**前置于测量的断言**挡住而不是吐数：
① 把第二支建在同一工作树 ⇒ 索引/盘被污染，真 merge rc=2「local changes would be overwritten」；
② 临时索引文件放在工作目录内，被 `add -A` 收进树 ⇒ 交集形状断言拒掉；
③ 助手把 `merge-tree` 的 rc=1（有冲突＝预期读数）当异常抛。
⇒ 所以下面那个 115 不是"推断等价"下的数，而是**方法已验证的读数**。现量（git 2.55.0）：

| 读数 | 值 | 独立性 |
|---|---|---|
| 两棵树路径 | `master` 2668 / `origin/master` 261 | `git ls-tree -r` |
| 交集 | **260**（其中 blob 相同 **145**、blob 不同 **115**） | 逐路径比 blob sha |
| merge-tree 判决 | rc=1，`CONFLICT` 行 **115**，全部 `add/add`；`Auto-merging` 行 115 | 独立于上一行的算法 |
| 结果树 | `b97a6ab03c35…`（可写出来但**我没写**，`--write-tree` 只产对象，不动任何 ref） | — |

⇒ **"合 master 难不难"有答案了：115 只文件要逐个解，且全是 add/add（两边各自新增同一路径）**。
这不是"跑一遍就好"的量级，而且本书禁止"丢弃改动来让合并过去"（`resolving-merge-conflicts` 的红线同一条）。
两条后果要摊开：
1. **A4 的真实成本 = 115 次内容裁决**，其中包含 `.env.example`、`.gitignore`、`CONTRIBUTING.md`、`.github/workflows/ci.yml` 这类**门禁与配置本体**——把它们和远端那 261 只文件对上，等价于重做一轮配置审查，不属于本会话边界。
2. 因此我改口：**推荐路线从"先合 unrelated 历史再推 master"改成"先只推 `codex/*` 分支"**（新分支创建天然非 force，零冲突面），
   把"合 master"留成一个**独立裁决项**（它需要 115 次内容裁决 + 远端真实头读数，两者今天都不具备）。
   ⚠️ 这与我在 D-19 之前给的 `--no-ff` 建议**方向一致但不等价**：`--no-ff` 管的是"怎么合"，这条管的是"今天能不能合"。

### 复算

```bash
M=/c/Users/33393/Desktop/ai-legal-helper
E=4b825dc642cb6eb9a060e54bf8d69288fbee4904    # git hash-object -t tree /dev/null
git -C "$M" merge-tree --write-tree --merge-base=$E master origin/master | grep -c '^CONFLICT'      # 115
git -C "$M" merge-tree --write-tree --merge-base=$E master origin/master | grep '^CONFLICT' | sed 's/CONFLICT (\([^)]*\)).*/\1/' | sort | uniq -c   # 115 add/add
git -C "$M" merge-tree --write-tree master origin/master; echo "rc=$?"                              # 128 refusing
```
