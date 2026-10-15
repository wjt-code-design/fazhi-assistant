# 独立复核 C（票 X 交付）：对 2026-10-10/11 收尾轮的证伪式复核

> 复核者：**独立会话**（非实现者）。铁规遵守声明：本报告每个判决附**我自己跑的命令 + 它的原样（截断）输出**；未用报告转述当判据；引用到的每个数字都在本机重算了。
> 复核窗口：**2026-10-11 02:29 – 02:54（+0800）**。被执行票版本：**02:29 读入**；票于 **02:41:49** 被更新（新增"构建类复算的额外要求"节 + §0/附改写）——经重读核对，**七颗钉子与硬约束两版一致**，新增节要求已补做（回执见 §4.6）。
> 被审件起点快照：`review-20261011/audited-files-at-start.sha256`（23 件，02:34:55）。复核期间有 3 件被改写（含票本体），处置见 §4.2。
> 复跑约定：下文 `R=` 运行根，`C=` 候选树。
> ```bash
> R=/c/Users/33393/Desktop/fazhi-nondeploy-closeout-20261010-b4e7a2
> C=/c/Users/33393/Desktop/ai-legal-helper/.worktrees/nondeploy-closeout-20261010
> M=/c/Users/33393/Desktop/ai-legal-helper
> ```

## §0 三行汇总

- **采纳 6 / 驳回 1 / 核不了 0**。
- 驳回的那条是**钉1**，且只驳回"**可直接引用的现量**"这一层：`4301` → 现量 **4315**、`238 棵树` → 现量 **239**、`树 == HEAD^{tree}` **现为假**（快照树 = 第四笔 `3f605de` 的树）。钉1 的三条核心事实（历史裸值存在 / 快照按值 0 命中 / 同仪器正对照咬住）**全部复现**——明细与修法在 §2.1，那是本复核最重的一条。
- §2 漏项 **3 条**；§3 你的更正本身的错 **3 条**。

## §1 逐条（钉子编号 + 我跑的命令 + 原样输出 + 判决）

### 1.1 钉子1 凭据轴 —— 判决：**驳回（仅"数字层"）+ 采纳（核心三事实）**

**① 13 位裸值在候选历史里**（复算器原样跑）：

```bash
"$R/candidate-envB/Scripts/python.exe" "$R/evidence/value_reverse.py" "$C"
```
```text
at 817e7d3 line104: len=13 alnum=True sha8=e32743f3
HEAD blob contains that literal? False
7eda4bb blob contains it? False
value-reverse: commits=239 hits=61 files=1
   dispatch-output/t12-frontend-sweep-20260920/apply_case_domain_gate.py  lines=104
```
**采纳**（值不落纸面；`commits=239` 与在册"238 棵树"差 1，见下）。

**② 快照按值 0 命中 + 正对照能命中 1**（含"0 是不是射程为空的假 0"这一攻击点——我用**同一仪器**跑**三套非空对象集**）：

```bash
"$R/candidate-envB/Scripts/python.exe" "$R/review-20261011/value_scan_sets.py" "$C"
```
```text
value: len=13 alnum=True sha8=e32743f3 (值不落纸面)
A: 在册快照 5df5a127                   objs=2581  value_hits=0  (rc=0)
C: origin/master..HEAD (普通推)       objs=4315  value_hits=1  (rc=0)
positive@817e7d3 blob contains value: True
B: 现HEAD等价新快照                      objs=2581  value_hits=0  (rc=0)
```
另有一遍在册复算器：`shape_scan_committed_set.py` ⇒ `CONTROL-A 5/5、CONTROL-B bites_on_817e7d3=True、hits inside 0b54396..HEAD=0、VERDICT=PASS_VALUE_LEG_PROVED_BITING`。
**采纳**：0 不是假 0——三套集合都非空（2581/2581/4315），同一批次仪器在 C 集咬住 1、在引入笔 blob 上咬住 True；快照 A 与**我自造的现 HEAD 等价快照 B** 都是 0 命中。

**③ 对象数**（逐笔现量 + 包内分类 + 冷恢复读回）：

```bash
for h in 5ca3315 8c179e7 a934fa7 3f605de 9e3cfc5; do echo -n "$h: "; git -C "$C" rev-list --objects "origin/master..$h" | wc -l; done
git -C "$C" verify-pack -v "$R/evidence/orphan-snapshot.idx" | awk '$2=="commit"||$2=="tree"||$2=="blob"{c[$2]++}END{for(k in c)print k,c[k]}'
```
```text
5ca3315: 4283 / 8c179e7: 4291 / a934fa7: 4296 / 3f605de: 4301 / 9e3cfc5: 4315
快照 rev-list = 2581；verify-pack = commit 1 / tree 173 / blob 2407
冷恢复（临时裸仓 + 仅 HEAD 文件）：cat-file -t = commit，^{tree} = 04dd97ad6acbfc0ef4fcd23a966abe58b6c88618（原样跑通）
```
**驳回（数字层）**：`4301` 只在 **`3f605de`** 上成立（这正是快照的 `from_head`）；现 HEAD 是 **4315**，"少 1720"相应变"少 1734"。`2581 / 1+173+2407 / 按值 0 命中 / 冷恢复读回` 全部复现。**"树 == HEAD^{tree}"现为假**——快照树 `04dd97ad` = **第四笔 `3f605de` 的树**，而现 `HEAD^{tree}` = `1e91913c`。这条不是纸面问题，见 **§2.1**（它会让 D-5(b) 推出一棵不含第五笔的树）。

### 1.2 钉子2 J3 purge —— 判决：**采纳（既有缺陷成立；purge 机理我独立复证）**

**现 .next 上两条尺子**：

```bash
"$R/candidate-envB/Scripts/python.exe" "$R/evidence/check_badge_purge.py" "$C/frontend"; echo rc=$?
# 备一条我自己的：for p in badge-success badge-error badge-neutral badge-accent ".badge{"; do ... grep -o -F ...; done
```
```text
badge-success 0 / badge-error 0 / badge-neutral 0 / badge-accent 0；control .badge{ 1
VERDICT=DEFECT_PRESENT missing=[...]  rc=1
```

**攻击点（既有 vs §14 引入）——三臂构建，单变量 = 前端源码树**（同机器、同 node_modules（junction 只读复用）、同 next 14.1.0；**全部在我 scratch 里构建，候选 `.next` 未碰**）：

```bash
bash "$R/review-20261011/j3_builds.sh"    # head5=0b54396(=HEAD~5) 与 current=9e3cfc5 两臂
bash "$R/review-20261011/j3_mutant.sh"    # 第三臂：现树 + 在册 mutate_ui.py 逐字相同的静态映射替换
```
```text
head5   : build rc=0 → badge 4×0, control 1 → DEFECT_PRESENT (rc=1)
current : build rc=0 → badge 4×0, control 1 → DEFECT_PRESENT (rc=1)
mutant  : build rc=0 → badge-success/error/neutral/accent 各 = 1, control 1 → VERDICT=OK (rc=0)
```
**静态链**（各一条命令，输出从略）：`ui.tsx:39` 现拼 `` `badge badge-${kind}` ``；`tailwind.config.ts` content=`app/**+components/**`；四个类名在后端**全仓只有 `globals.css` 自己**（在 `@layer components`（:256 起）内的 :588–:602 定义）；`ui.tsx` 与 `tailwind.config.ts` 在 `0b54396..HEAD` **零改动**；`9e3cfc5` 对 `globals.css` 的 diff 不含 badge 段（只加 `.upload-zone:focus-visible` 与 `.answer-h4`）。
**采纳**：HEAD~5 上与现 HEAD 上**同一计数器同为 DEFECT_PRESENT**（两臂 build rc=0）⇒ **不是 §14 引入的，是既有生产形状缺陷**；且我的变异臂把"根因 = purge 扫不到动态类名"从"你的推断/你的日志"变成**我亲手的三臂因果对照**（同树只改那一行 ⇒ 四个类名各回 1 次）。
**未复算**：题面"浏览器计算样式六者相同"只由 D 的浏览器腿承载，我不重跑浏览器（§4.1）。

### 1.3 钉子3 第五笔字节等同性 —— 判决：**采纳（5/5）**

```bash
sha256sum "$R/evidence/frontend-dirty-20261010.patch"   # 71cde8d4…5ba548c，167 行/7,973 B/CR=0（与 manifest 记录相符）
# manifest 两侧 blob：git rev-parse 9e3cfc5:5只 == working_blob 5/5；3f605de:5只 == committed_blob 5/5；5 只 working blob 都在对象库
# 重放（临时目录，未碰候选树）：
cd "$R/review-20261011/replay9e3" && patch -p1 --dry-run < "$R/evidence/frontend-dirty-20261010.patch" && patch -p1 < …patch
# 逐只：sha256sum 重放文件 vs git show 9e3cfc5:<path> | sha256sum
```
```text
dry-run rc=0（5 只 checking，无 fuzz）；apply rc=0（5 只 patching）
SAME ×5  ⇒ equals=5/5
```
**采纳**：重放产物与第五笔提交字节逐字节一致；manifest 的 working/committed 两侧 blob 全对。

### 1.4 钉子4 门禁四条现量 —— 判决：**采纳（含 collected/junit 一致与 skip 定性）**

```bash
cd "$C/backend"
COVERAGE_FILE="$R/review-20261011/.coverage-C" "$R/candidate-envB/Scripts/python.exe" -m pytest -m "not slow" --cov=. --cov-fail-under=70 -q --junitxml="$R/review-20261011/pytest-C-junit.xml"
"$R/candidate-envB/Scripts/python.exe" -m pytest -m "not slow" --collect-only -q | tail -1
PY="$R/candidate-envB/Scripts/python.exe"; "$PY" -m ruff check . ; "$PY" -m ruff format --check . ; "$PY" -m mypy .
cd "$C/frontend" && npx tsc --noEmit ; npm run lint ; npm run test
```
```text
1925 passed, 10 skipped, 18 deselected, 160 warnings in 292.35s ；cov 86.35%（门槛 70）；rc=0
--collect-only：1935/1953 tests collected (18 deselected)
junit：testcases=1935、skipped=10、failed/error=0（1935 = 1925+10 ⇒ collected 与 junit 用例数一致，无"收集期只剩一条伪用例"）
ruff：All checks passed!（rc=0）；283 files already formatted（rc=0）；mypy：Success: no issues found in 74 source files（rc=0）；ruff 0.16.10 / mypy 2.4.0
前端：tsc rc=0；lint rc=0（No ESLint warnings or errors）；vitest rc=0（Test Files 9 passed (9) / Tests 83 passed (83)）
```
**"两条 skip 是不是设计内采集口"——是，且我把全 10 条都分了类**：junit 里逐条读出来——`test_e6_dump_frames_for_zero_change_diff`（`未设 FZ_DUMP_FRAMES：本用例是 1a 改前/改后逐帧比对的采集口`）与 `test_dump_stream_frames_for_zero_change_diff`（`未设 S6_DUMP_FRAMES…采集口`）＝**2 条 env 门采集口**（tests 源里就是 `pytest.skip(...)`，平时不跑）；其余 **8 条**均为 `real_kb` 门（`conftest.py:155`：`真实语料不可用（…主库仅 0 条）——不得在空库上假绿`）⇒ 候选树无真实语料时的**设计内跳过**。
**时序归一**：我这次 292.35s > 你的 253.43s——因为跑的同时我在做 J3 三臂构建与 docker 探针（CPU 竞争）；读数本身逐字相同。
**采纳**：四条读数全部逐字复现，且两个攻击点都被挡住。

### 1.5 钉子5 依赖分母两根轴 —— 判决：**采纳（每个数，含我用第二实现复算）**

```bash
cd "$R/evidence" && node audit_axes.js audit-cand-runtime.json audit-cand-dev.json
# 我自己的独立复算（python，含每包 distinct 与跨包重叠检查）见 §1.5 输出
```
```text
条目(记录)=24  distinct主ID=15  包数=5 chromadb,langchain-core,langchain-openai,langchain-text-splitters,langsmith
族每包条目= {"langchain-core":11,"langchain-openai":2,"langchain-text-splitters":4,"langsmith":5}  族distinct主ID=13  族主ID+aliases=38
（dev 件与 runtime 件逐字同输出）
我的python复算：全库条目24 / distinct15 / 5包；每包条目 core11·langsmith5·splitters4·openai2·chromadb2（和=24）；
每包distinct core6·langsmith4·splitters2·openai1（+chromadb2，全库和=15）；跨包同ID重叠=0；withfix=13；aliases 合计38
```
**采纳**：两条轴上的每个数（24 / 15 / 5 / 11·5·4·2 / 6·4·2·1 / 和=并集=13 / 38 / withfix=13）都被复现，且 `6/4/2/1` 不是"不可复现"——它在 distinct 轴上就长这样。口径一注见 §3.3。

### 1.6 钉子6 `.dockerignore` 泄漏 —— 判决：**采纳，且现场重做（引擎在复核期间回来了）**

**状态翻转先说**：你说"引擎此刻不在运行"（写票时属实），**我复核期间它回来了（02:40:25 起）**——于是我不读旧日志，**现场重做**了三件事：探针对、容器内读数、§9 镜像抽查。

```bash
docker version --format '{{.Server.Version}}'                       # 29.6.2
grep -n "build:" "$C/docker-compose.yml" | head                        # 17: build: ./backend（两棵树都验过）
wc -l -c "$C/backend/.dockerignore" ; grep -cE "^data/|^\.ptmp" "$C/backend/.dockerignore"   # 20行/457B；0
diff <(tr -d '\r' < "$M/backend/.dockerignore") <(tr -d '\r' < "$C/backend/.dockerignore")   # 去CR后逐字相同（主仓 477B = CRLF 版）
docker build --network=none -f "$R/evidence/probe-df-env"    -t fazhi-probe-c-env:20261011   "$M/backend" ; echo rc=$?
docker build --network=none -f "$R/evidence/probe-df-appdb"  -t fazhi-probe-c-appdb:20261011 "$M/backend" ; echo rc=$?
docker run --rm --entrypoint sh fazhi-probe-c-appdb:20261011 -c 'ls -la /probe && head -c 16 /probe/appdb | od -c'
docker run --rm --entrypoint sh fazhi-closeout-probe:20261010-final -c 'ls -la /app/.env; ls /app/data; python -c "import torch;print(torch.__version(),torch.version.cuda)"'
docker rmi fazhi-probe-c-appdb:20261011      # 清场（env 探针构建本就失败、无 tag）
```
```text
负对照（.env）：rc=1，`ERROR: failed to build: failed to solve: failed to compute cache key: … "/.env": not found` ⇒ 排除机制在该上下文确实生效（尺子能红）
实验组（data/app.db）：rc=0；容器内 /probe/appdb = 19,939,328 B，头 16 字节 = `S Q L i t e   f o r m a t   3 \0`
§9 抽查：/app/.env 不存在；/app/data 只有 eval_agent_complex.json 与 .rubric.md；torch 2.13.0+cpu / cuda None —— 三项全复现
清场：probe-c 残留 0；compose 栈未碰（容器 StartedAt 02:40:25，全程未被本会话动过）
```
**三个攻击点逐条**：① 构建上下文 = `./backend`（compose 第 17 行，两棵树一致）⇒ 生效的就是 `backend/.dockerignore`；② `grep data` 0 命中、`*.db`/`*.sqlite*` 只在单段路径上匹配（**实测判决**：同样两条探针、同一上下文、同一天，一条失败一条成功——这就是"漏"的直接证据；机理= `*` 不跨 `/`，与在册语义一致）；③ 19,939,328 B 与主仓 `backend/data/app.db` **现量 size 逐字节相同**（mtime 09-23 14:51:15 ↔ 镜像内 06:51 UTC = 14:51+0800，同一份文件）⇒ "是那份真实库文件的副本"成立；**"内容性质"（生产行 vs 合成行）禁读不可判**——见 §4.1，但这对"镜像把 `data/app.db` 烘进去"这个结论不构成降级，被证明的是**文件本身在镜像里**。
**采纳**（并强化为现场复做 + §9 三项抽查）。

### 1.7 钉子7 取消/切换三腿与"只落一条" —— 判决：**采纳**

```bash
grep -n "streaming\|async function selectConv\|async function deleteConv\|function newChat" "$C/frontend/lib/hooks/useConversations.ts"
git -C "$C" rev-parse HEAD:frontend/lib/hooks/useConversations.ts       # 1124fc6a7294221f721df8e1008b42b44fc6005b
cd "$C/backend" && "$R/candidate-envB/Scripts/python.exe" -m pytest tests/test_cancel_boundaries.py tests/test_stream_cancellation.py --noconftest -q
grep -n "_post_placeholder\|assistant_committed\|服务暂时无响应" "$C/backend/main.py"
```
```text
守卫：:41（function newChat 内）/ :57（selectConv 内）/ :88（deleteConv 内）——**共三条**，D 报的"43/59 两条"确为漏读+偏移（blob 三方同为 1124fc6a…，无漂移轴）
pytest：55 passed in 20.54s（rc=0）
占位闸：main.py :1033（assistant_committed 早退）→ :1037（占位文案=服务暂时无响应，请稍后重试。）→ :1046（落库后置位）；_post 真答落库后 :1003 置位；
调用点 2538/2630/2640 后 `_posted=True` 互斥 finally :2648（`not _posted and not assistant_committed`）；compensate_unstarted :2660 由 stream_state（:2046/:2049）与正文流 finally 互斥
tests 断言：test_d2_disconnect_before_body_persists_exactly_one_placeholder 等 ——"exactly one assistant row"在用例层被钉住
```
**采纳**：三条守卫、55 passed、"只落一条"（代码闸 + 互斥 + 用例三层）全部复现；D-23 的前提（取消路径落的是"服务暂时无响应"）也随之复现（finally 兜底走同一个 `_post_placeholder`）。

## §2 你发现而我没登记的漏项（本报告最重的部分）

### 2.1 无父快照**早于第五笔**——D-5(b) 若按现文件执行，会推出一棵**不含 `9e3cfc5`** 的树

**事实链**（全部可复跑）：

```bash
cat "$R/evidence/orphan-snapshot.sha"                          # from_head=3f605de…（第四笔）；snapshot_objects=2581；normal_push_objects=4301
git -C "$C" rev-parse '5df5a1277f^{tree}' '3f605de^{tree}' 'HEAD^{tree}'
stat -c '%y %n' "$R/evidence/orphan-snapshot.pack"             # 2026-10-10 19:28
git -C "$C" log -1 --format='%cI' 9e3cfc5                      # 2026-10-10T21:47:06（第五笔晚于 pack 3 小时）
```
```text
5df5a127^{tree} = 04dd97ad… = 3f605de^{tree}    （快照 = 第四笔的树）
HEAD^{tree}     = 1e91913c…                     （现 HEAD 的树 ≠ 快照树）
```
**被这句话损坏的现役文字**（都还挂着）：`h-ci-and-credentials.md` §7 "树逐字等于 `git rev-parse HEAD^{tree}`（同一内容，零历史）"（该文件最后保存于 01:42，**晚于**第五笔）；`runbook-I-push-pr-merge.md` §0 "`codex/…=3f605de(238)`"与 A2 前置"本地该 ref 仍是 `3f605de`；工作树 tracked 脏仍 5 只"（保存于 01:41）；`decisions-needed` D-5 行"4301 / 238 棵树 / 树与 `HEAD^{tree}` 逐字相同"（02:31 重写后仍在）；`gates.md` §25"普通推上传的 4301 个对象里含那只历史裸值"（01:5x 写，数字当时已过期）。
**为什么重**：D-21 的教训是"验收对象 ≠ 交付对象"；D-5(b) 若照现文件执行，**交付对象（3f605de 树）会再缺一次第五笔**——恰恰是刚被浏览器验收、刚被重放进候选的那批 §14 修复字节。
**修法（我没代跑：它是写动作）**：重跑 `evidence/orphan_pin.py`（它按运行时 HEAD 生成 ⇒ 天然得到 `9e3cfc5` 的树；会覆写 pack/sha 并新建一枚无 ref 的 commit 对象）；或至少把这句加进 D-5(b) 的前置："快照必须晚于分支头"。
**修法可行性的现场验证（我跑了）**：`review-20261011/value_scan_sets.py` 的 B 腿用同法造了现 HEAD 的等价快照 ⇒ **2581 对象、按值 0 命中**（正对照在同一批次咬住）⇒ 重生成后"不外泄是构造性质"可以原样重建。

### 2.2 引擎回来了 + 主仓 `backend/data` **目录** mtime 被推进到 02:40:38（归因：容器启动，不是任何会话）

```bash
docker inspect fazhi-backend --format '{{.State.StartedAt}}'      # 2026-10-10T18:40:25Z = 02:40:25+0800
find "$M/backend/.env" "$M/backend/app.db" "$M/backend/data" "$M/backend/chroma_db" "$M/backend/media" "$M/backend/backups" -newermt "2026-10-11 02:29"
ls -la --time-style=full-iso "$M/backend/data/"
```
```text
引擎：29.6.2，ps 有输出（你 01:3x 的"引擎不在运行"自此是**时点读数**，gates §23 整节按此更新）
find 命中 1 条：主仓 backend/data **目录节点** mtime=02:40:38（= 容器 StartedAt 后 13 秒）；目录内四条目 mtime/size 全部未变
（app.db 19,939,328 B / 09-23；quota_used.sqlite 12,288 B / 09-19；eval 两件 / 09-03；当前无 -wal/-shm 残留）
```
**归因**：容器启动窗口的瞬态动作（创建/删除了什么瞬时条目）；**两个新会话的纪律动作都不能解释它**，也不是本复核起的——我这边**第一条** docker 命令就是只读 `docker ps`，当时栈已 Up（"Up About a minute"）；本会话全部 docker 动作 = `version/images/ps` + 三次 build（只读上下文）+ 三只 `run --rm` + 两次 rmi。**我不能替别人认领也不能替别人开脱**：能钉住的是"不是我 + 时间窗口与容器启动精确重合 + 文件内容零变化"。
**连带**：§23 那张"受影响读数"表现在**整体恢复可复量**——我复量了 §9 的三项内容与 §8 的探针对（见 §1.6）；`fazhi-backend/caddy/frontend` 三容器现为 Up（自 02:40:25 起，我没有碰过）。

### 2.3 "禁令目录 `find -newermt 02:00` 仍 0 命中"要分两轴写

现行 §28 那半句在**目录轴**上已不再字面成立（上条那个 02:40:38 的目录节点）；**文件轴**仍 0。建议把该不变量写成两个读数：“文件级 0 命中 + 唯一目录级命中 = `backend/data`，归因容器启动（02:40:25+13s），非会话动作”。候选树两轴全 0（我的 find 同命令：候选 = 0）。

## §3 你的更正本身又错的地方

### 3.1 §26 的"§C 计数"命令不成立——数字对、命令错

你给的复量命令（`grep -c '^| \*\*D-'`，"三档各跑一次"）在 §C 上**恒为 0**，因为你把 D-13/D-21 移进 §C 时**没有加粗编号**：

```bash
awk '/^## C\./{f=1;next}/^## [DE]\./{f=0}f' "$R/reports/decisions-needed-20261010.md" | grep -c '^| \*\*D-'     # 0（≠8）
awk '/^## C\./{f=1;next}/^## [DE]\./{f=0}f' "$R/reports/decisions-needed-20261010.md" | grep -cE '^\| .*D-[0-9]+'  # 8
```
A=3、B=16 两种口径都一致；**3+16+8=27 的总和与"无漏登无重复"成立**（我另行核过 1..27 每个编号恰出现一次）。要修的只是命令（`grep -cE '^\| .*D-[0-9]+'`）或给 §C 行加粗。

### 3.2 §E 的复算块**本身跑不动**——SyntaxError（在册 3d 的同一台机器，这次是文档里就坏）

该块按字面照抄即报错（我按**原始字节**核对过，不是转写问题）：

```bash
sed -n '86p' "$R/reports/decisions-needed-20261010.md" | od -c | head -4     # …r e p l a c e ( ' \ ' , ' / ' )…
# 照抄运行 ⇒  SyntaxError: unterminated string literal
```
`'\'` 是未闭合字符串——单反斜杠。修法：用 `os.sep`，或直接 `glob.glob(R + "/evidence/audit-cand-*.json")`（无需 replace）。这条值得进册：**"复算命令"是交付物的一部分，它自己也会坏**。

### 3.3 §E 把"每包 distinct"归给了 `audit_axes.js`——该脚本不印这半轴

脚本实际输出 = 条目轴（全库 24 / 5 包）+ **族**每包条目 + **族** distinct 13 + aliases 38；**`core 6 / langsmith 4 / splitters 2 / openai 1` 不在它的打印面里**。数字我逐一对（用我自己第二实现）**全对**；要修的只是"复算器"指针——扩脚本印 per-package distinct，或把一条 python 复算也列进复算面。

## §4 已知限制（别把本报告读成"全验过了"）

**4.1 未复算清单**（如实列出）：① J3 的**浏览器**半句（六状态计算样式全同）——只由 D 的浏览器腿与你的复现承载，我没有浏览器腿；② D 单 390 档 41 个越界元素全表与浏览器库逐行（我只到代码级+`exactly one` 用例级）；③ §9.3 容器 smoke 未重跑（只抽查了内容三项）；④ `data/app.db` 的**内容性质**（生产行 vs 合成行）——禁读不可判；⑤ 远端 CI/推送相关（无 push，不适用）；⑥ pack 的**生成过程**未重跑（`orphan_pin.py` 有写动作）——我只读复现了它的全部读数面（对象数/无父/树/按值/冷恢复）。
**4.2 被审件在复核期间被改写**：`gates.md`（新增 §26–§28）、`tickets/dispatch-D3-langchain-migration-20261011.md`、**票 X 本体**（02:41:49）。我以 02:29–02:34 读入的字节执行、02:34:55 落 sha256 快照；改写后我**重读了相关节**并核对"七钉与硬约束未变"；本报告的判决以"我读到的版本 + 现量"为准，若再有人改，以字节与 sha 快照为凭。
**4.3 方法注记（两台会骗人的表）**：npm 包装的 prettier 输出带 **ANSI 转义**且落盘晚于进程退出——naive `^\[warn\]` grep 会得假 0；我按去 ANSI 的字节重数：仓库轴 **3 只**、整目录轴 **15 只**（与 §21 一致，多出的排头脚本是 `scripts/accept_frontend.mjs`）。管道后的 `$?` 不是被测码——本报告所有 rc 均为直接捕获（docker 探针 rc 单独重取过一遍）。
**4.4 边界声明（逐条）**：两树只读（终检候选 `porcelain=0`、HEAD `9e3cfc5`；主仓 `21/567` 与票面同数）；未 commit/push/动 ref；**envB 只读**（起/止 `pip freeze --all|sort` 行集合 **0 差异、164 行**）；两棵树禁令面（§2.2/2.3）；未占 3021/8088；未重启 compose 栈（容器未被本会话碰过）；**不打印任何凭据值**（仅 len/sha8/计数）。
**4.5 本会话唯一的写类动作**（全部在 scratch / 一次性）：`review-20261011/**`（三臂构建树 j3/*、replay9e3、cold-restore、各日志与脚本）；pytest 缓存（候选树 gitignored）+ `COVERAGE_FILE` 显式重定向到 scratch；docker build×3 + `run --rm`×3 + rmi×2（探针 tag 已清、残留 0）。构建期的 junction 实路径解析曾把 34 个桩文件写到 `review-20261011/ai-legal-helper/.worktrees/…`（**全部在 scratch 内**）——已清；候选/主仓零波及。
**（03:05 证据门禁自查补记）** "零波及"的正面证据：候选 `frontend/.next` mtime `10-10 21:52:34`、`tsconfig.tsbuildinfo` mtime `10-10 21:45:11`——**均早于本复核窗口**（02:29 起）；`node_modules/.cache` 不存在、无 `.eslintcache` ⇒ 可检的忽略面零改动。复量：`stat -c '%y %n' "$C/frontend/.next" "$C/frontend/tsconfig.tsbuildinfo"`。
**4.6 构建类复算回执（按票新增节）**：三臂构建**全在 scratch**，候选树 `.next` 未重建。构建前（02:33）与构建后（收尾）各一次原样输出：`rev-parse --short` = `9e3cfc5` / `9e3cfc5`；`status --porcelain` = **两次均为空**；`status --porcelain -- frontend/next-env.d.ts` = 空。若出现脏文件我会停下回报——没有出现。
**4.7 复跑索引**：钉1 → `value_scan_sets.py` + 两复算器；钉2 → `j3_builds.sh` + `j3_mutant.sh`（现 .next 一条：`check_badge_purge.py "$C/frontend"`）；钉3 → §1.3 的四行；钉4 → §1.4 的六行；钉5 → §1.5 两行；钉6 → §1.6 的 build/run 五行；钉7 → §1.7 四行。原始输出全在 `review-20261011/*.log` 与 `*.out`。

---
*落盘：2026-10-11 02:54。本文件为独立复核 C 的正式交付；判决与命令一一对应，任何一条都可按 §4.7 在本机原样复跑。*
