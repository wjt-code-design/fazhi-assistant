# 独立复核（第三轮）：10-12 接手轮 + 第二遍 —— 两路正交，只读

复核人：本会话（非实现者）。票：`tickets/dispatch-independent-review-20261012-round3.md`（仓内镜像同名）。
开工时刻的候选：分支 `codex/nondeploy-closeout-20261010`，HEAD 现读 `2b3210a`；**复核期间该分支被并行会话推进了三笔**（见 §1）。
统一解释器：运行根 `candidate-envB/Scripts/python.exe`（Python 3.11.0，当场 `-V` 复量）。
我的全部写动作只落在运行根新目录 `review-round3-20261012/` 与本文件；**没有改候选、没改主仓、没动 refs、没提交、没推送、没读 `.env` 值、没起现役栈**。

## 0. 先看这段（三句结论 + 一件现在就要知道的事）

1. **十颗钉子：A 路 1/2/3/4/6/7/8/9/10 全部复现成功**，第 5 颗复现了读数但抓出那把尺子的一条**恒真正对照**（它按构造不可能红）。2030 passed / 0 failed / 10 skipped / 18 deselected、cov 86.57%、collected 2040/2058、junit `tests=2040`——我在 `git archive HEAD` 的纯发布物树上逐字复现，不是引用我的转述。
2. **B 路（对抗）打穿 7 条主张**，其中最重的一条与"只 grep 了目录不全"这台机器同族：`gates.md:1129` 的「入口零文档指针」为假（修前的 `docs/closeout-20261010/` 里就有 3 处指针）。另外三条影响你怎么读已签/在册的东西：`D-39` 的「只有全局换 `JWT_SECRET` 才能作废会话」漏了按用户硬删的入口；`D-41` 已登记在正文但**档位审计对它天然瞎**（脚本只读表格行）；在册凭据扫描的 `url-auth` 那条规则**扫不到用户名或口令含字母 `s` 的凭据 URL**（真实形状 `postgresql://admin:Passw0rd@…` 直接 MISS），所以它的"命中 0"比看起来弱。
3. **本轮新增的两颗钉子各有实物**：第 8 颗我用**自拟形状**答了"口令还能不能从非终端通道进来"——**能**（脚本里没有 tty 前置检查，`getpass` 在拿不到终端时会退回读 stdin；我在私有临时库上实测把口令写了进去）；第 9 颗**不是台阶**：换一根变异（摘 `FREE_STEP_EDGES` 那条边、或把澄清上界错绑到 `max_steps`），那条"反向护栏"当场红，作者"谁合并计数器这条会红"的说法成立，但他自己没跑过这一臂。
4. **⚠️ 现在就要知道的事（04:33 起，不是我造成的，我没去复原）**：候选**工作树**被一次成型的降级覆盖——04:48 现量 `porcelain=1486`（全部 tracked 修改、0 只暂存、HEAD 仍 `074e8ba` 没有新笔）：1455 只差行尾（CRLF），**31 只差内容，且逐只都退回"本轮改之前"的那个对象**（`backend/.dockerignore` 盘上退回 `b2e2ccae`＝修前，没有 `**/*.db`/`.ptmp*` ⇒ H 那条缺口在**工作树**里重新打开，`HEAD` 里的修复仍在；`reset_admin_password.py` 退回 `cd2007e` 之前）。这条会让任何按 `porcelain=0` 判"树干净"的会话读到假绿，也使"验收对象＝交付对象"这格**此刻复算为 0/1486**（我 04:03 的通过读数是真的，见 §2 钉子 4）。证据、归因表与判别命令在 §1。

## 1. 现场与并发（每条都带时刻）

| 时刻 | 读数 | 我怎么取的 |
|---|---|---|
| 03:4x | HEAD `2b3210a`，porcelain 0 行；运行根 26 只 `reports/*.md` 与仓内镜像逐只 sha256 相同 | `rev-parse` + `status --porcelain` + 逐只 sha256 |
| 03:52:56 | 纯发布物树建立（2724 只文件），porcelain 前=0 | `run_nail1.sh collect` 日志头 |
| 03:54:11 | 全量腿启动，此时 HEAD 已是 `ff62986`（并行进了一笔） | `run_nail1.sh full` 日志头 |
| 04:00 | 全量结束，porcelain 后=0；我的树里多出 1 只 `backend/chroma_db/chroma.sqlite3`（跑测试自己建的空壳） | 同上日志尾 |
| 04:03 | blob==盘 29/29、CR=0、NUL=0（钉子 4 通过） | `nail4_delivery_equals_acceptance.py` |
| 04:05:36 | 钉子 2 结束时候选 porcelain 仍 0 行，HEAD `074e8ba` | `run_nail2.sh` 日志 |
| 04:33:04–08 | 候选文件 mtime 成片跳到这一刻（README/dockerignore/main.py 等） | `stat -c '%y %n'` |
| 04:34→04:37:39 | porcelain 45 → 118 → 801 → 1070 → **1486** | 同一命令重复取 |

**不是我造成的**，证据三条：① 我的写路径只有 `RR/review-round3-20261012/**` 与本文件；② 我对候选只跑过 `rev-parse / status / log / diff / ls-tree / ls-files / show / grep / archive / hash-object --stdin`（`hash-object` 我没带 `-w`，不往对象库写）；③ 04:03 我复量候选盘上 CR=0、blob 全等，04:33 的成片 mtime 晚于我最后一次候选侧读数。

**这次事件是一次性的，不是"另一个会话正在连续编辑"**（这条改变你怎么判上面那两个解释）：`porcelain` 在我手里从 04:34 的 45 → 04:37:39 的 1486，**04:48 再取仍是 1486、HEAD 仍 `074e8ba`（没有新笔）**，而全部 1486 只的 mtime 都落在 `04:33:04–04:33:08` 这四秒里。增长的是 `git status` 逐段刷新 stat 缓存的**发现速度**，不是新的写入。形状因此更像 **(i) 一次整片重写**（一次写就把整棵树换成 CRLF + 31 只旧内容），而不像有人在这几分钟里连续改 31 只文件。

**两条互斥解释，请你自己判**（我不猜）：
- (i) 某个子助手把**整棵旧快照**写回候选（形状像：1455 只差行尾 + 31 只差内容 + `.dockerignore` 恰好退回修前）；
- (ii) 另一会话正在**有意改**这批文件（`requirements.txt`/`pyproject.toml`/`retrieval.py`/`llm_registry.py` 正是 D-3 迁移会碰的那几只）。

**这次重写不是随机损坏，是把候选换成了"本轮之前的内容"**（我把 15 只代表性文件盘上字节 LF 归一后 `git hash-object`，逐只去比 5 个参照对象）：

| 文件 | 盘上 LF 归一 blob | 等于哪个对象的 blob |
|---|---|---|
| `backend/.dockerignore` | `b2e2ccae` | `19e296e` / `master` / `3f605de`（＝修前那份，**不是** HEAD 的 `5374eb9`） |
| `backend/scripts/reset_admin_password.py` | `847aa711` | `19e296e` / `master`（＝`cd2007e` 之前） |
| `backend/main.py` | `b59e65a5` | `604fa24`（上一轮头族），不等于 HEAD 也不等于 master |
| `backend/requirements.txt`、`backend/pyproject.toml`、`.github/workflows/ci.yml`、`backend/Dockerfile`、`DEPLOYMENT.md`、`frontend/components/ui.tsx`、`frontend/package.json` | — | **等于 `master` 0b54396** |
| `backend/agent/state_machine.py`、`backend/retrieval.py`、`backend/agent/controller.py`、`backend/llm_registry.py`、`backend/tests/test_agent_resume.py` | — | 我探的 5 个对象**都不等**（说明还混进了第三个来源，可能是主仓那份带 21 只未提交修改的工作树） |

⇒ 形状是**一次成型的降级覆盖**：本轮与上一轮改过的文件，盘上退回各自"改之前"的那个对象；而 1455 只差 CRLF 的那批，字节内容与 HEAD 相同只是行尾被翻过。
一句可决定的话：`(i)` 要恢复是"从 `HEAD` 重刷工作树"，`(ii)` 要保住是"先让它提交"。判别命令（只读）：

```
git -C 候选 diff --ignore-cr-at-eol --name-only            # 31 只：内容真的变了
git -C 候选 diff --ignore-cr-at-eol -- backend/.dockerignore   # 看到的是退回修前，还是新规则
git -C 候选 log -1 --format=%s HEAD                         # 074e8ba 之后有没有新笔（04:48 现读：没有）
```

## 2. A 路：十颗钉子逐条（复现命令 + 当场读数 + 判定）

**钉子 1 全量门 —— 复现成功（逐字）。**
命令（纯发布物树，不在候选跑）：`git -C 候选 archive --format=tar HEAD | tar -x -C tree` 然后 `python -m pytest -q -m "not slow" --cov=. --cov-fail-under=70 -p no:cacheprovider --junitxml=...`，进程环境按在册配方（假凭据 + 六根上游 URL 指 `127.0.0.1:9`）。
读数：`2030 passed, 10 skipped, 18 deselected ... Total coverage: 86.57%`、`PYTEST_RC=0`、`junit tests=2040 failures=0 errors=0 skipped=10`；分母另取 `--collect-only -q` 单值 = `2040/2058 tests collected (18 deselected)`，且 `grep -c "::"` 独立数得 2040。候选 porcelain 前/后各 0 行。10 只 skip 的名字我逐只列了（8 只 `real_kb` + 2 只帧采集开关），与你 §48「8 条因候选真实语料不可用，2 条未启用帧采集」对上。
附带一条你没写的：跑完我的树**多出 1 只文件**（`backend/chroma_db/chroma.sqlite3`，空壳）⇒ `porcelain=0` 单独不构成"树未变"的证据，要配 `find -type f | wc -l`。
判定：**复现成功**。另：在册 pass1/pass2/pass3 三趟的日志头都写明 `cwd = 候选/backend`（pass1/pass2 还是打在未提交的补丁态）⇒ 这些数是**在候选直接跑**出来的，与本票"别在候选直接跑"相反；我在纯发布物树复算同值，所以结论可用，但取数形状与票面纪律不一致，记入 §3-B13。

**钉子 2 归因 —— 复现成功（两腿都点名）。**
起点树 = `git archive 19e296e`；当前树 = `git archive HEAD` 后 `git apply -R baseline-test-compatibility.patch`。
读数：LEG A `rc=0`（两条用例在修前树上绿）。LEG B `rc=1`，红的**正是同名两条**（逐字取自 `evidence/nail2-attribution.log` 的 `FAILED` 行）：`tests/test_agent_resume.py::test_agent_fallback_on_resume_feeds_run_date_into_fast_path` 与 `tests/test_chat_turn_persistence.py::test_other_conversation_is_not_blocked_and_route_exception_releases_lock`。反向还原后的 blob：`test_chat_turn_persistence.py` = `f219ef5e`，与 `19e296e` 那只逐字相同；`test_agent_resume.py` = `4a174768`（**不等于** `19e296e` 的 `f0dae08`），因为 `c4cc6b3` 之后又往该文件追加了 D-33 四条——这是**正确的**差异，不是还原失败（patch 自己声明的前像在 `index f0dae08..1ead404`；`1ead404` 只在 `c15b775` 那一刻是终态，见 §3-B9）。
判定：**复现成功**，那两只红由 D-34 改接口造成，不是本来就红。

**钉子 3 `.dockerignore` —— 用另一种独立判据复现（没复用你的 10 格矩阵）。**
判据形状：真跑 `docker build`（`FROM scratch` + `COPY . .`），再 `docker create` + `docker export | tar -t` 直接读**镜像里到底有什么**。两套规则各建一遍：新规则取自 `HEAD:backend/.dockerignore`，旧规则取自 `19e296e:backend/.dockerignore`。上下文里放了真评测件（从 `HEAD` 抽取的 `git ls-files backend/data` 那两只）+ 根 `app.db` + `data/app.db` + `data/quota_used.sqlite` + `nested/deep/other.sqlite3` + `.ptmp-scratch.db`。
读数（`evidence/nail3-dockerignore/listing-{new,old}.txt`）：

| 目标 | 新规则 | 旧规则 |
|---|---|---|
| `app.db`（上下文根） | excluded | excluded |
| `data/app.db` | excluded | **IN-IMAGE** |
| `data/quota_used.sqlite` | excluded | **IN-IMAGE** |
| `nested/deep/other.sqlite3` | excluded | **IN-IMAGE** |
| `data/eval_agent_complex.json` / `.rubric.md` | present | present |
| `main.py` / `probe.txt` / `scripts/reset_admin_password.py` | present | present |

判定：**两问都是"是/没有"**。`**/*.db` 仍盖住上下文根的 `app.db`（moby 的 `**/` 可匹配零段）；运行时需要的两只评测件仍在。旧规则那列同时证明**我这把尺子能区分两种规则**（不是恒绿）。
我自己这条腿的限制：`.ptmp-scratch.db` 我放在根，旧规则也已经靠 `*.db` 挡住 ⇒ 我没 isolate 出 `.ptmp*` 这条新规则的增量（要 isolate 得放一只 `data/.ptmp-x`）。另附一条只读事实：`git ls-files backend` 里**没有任何一只**被这套规则命中 ⇒ 不存在"tracked 运行时文件被挡掉"。

**钉子 4 交付==验收 —— 04:03 复现成功；04:37 起被 §1 事件推翻（两个读数都给）。**
04:03 读数：`29b0488..HEAD` 8/8 blob 全等、`19e296e..HEAD` 29/29 全等、CR=0、NUL=0；镜像侧 26/26 与运行根相同、`docs/closeout-20261010/*.md` 盘上 43 只 = tracked 43 只。
04:37 读数（同一脚本重跑）：`porcelain=1486`，其中 1455 只**只差 CRLF**、**31 只差内容**（清单在 §1 与 `evidence/`），`backend/.dockerignore` 盘上已无 `**/*.db`。
判定：`交付==验收` 这笔**提交是对的**（HEAD 侧 29/29 全等），但**盘上态已经不是交付物**了。这条不是我造成的，但它使"现在这棵树＝刚跑绿那批字节"在今晚不成立。

**钉子 5 凭据轴 —— 读数复现，但你在册那把尺子的正对照是恒真的，且 `url-auth` 那条规则有别名盲区。**
我自己的五条形状规则各配一条**合成控制串**，逐条点名是哪条规则红（不写"红了"就算）：`sk-` / `AKIA`+16 / `eyJ….` / `PRIVATE KEY` 四道**各自单独咬得住**（`fired_rules` 恰为那一条）；**`url-auth` 那道的合成控制串不咬**——我没把它记成通过，而是去查它到底瞎在哪：把用户名或口令里换成含字母 `s` 的形状，五条测试全出结果（`evidence/nail5.jsonl` 的 `A2_urlauth_case`）：

| 控制串形状 | 匹配 |
|---|---|
| 用户名含 `s` | **MISS** |
| 口令含 `s` | **MISS** |
| 两者都不含 `s` | MATCH |
| 真实形状 `postgresql://admin:Pa**s**w0rd@db:5432/app` | **MISS** |
| `mongodb+srv://u1:abcd@cluster0…` | MATCH |

原因在规则本身：`://[^s/]*:[^s/@]{3,}@` 用 `[^s/]` 是为了跳过 `https` 里的 `s`，代价是**凡用户名或口令含 `s` 的凭据 URL 都扫不到**。这条要进你 §D-12 那类"入库前三检"的更正里——它的"URL-in-creds 命中 0"比它看起来弱。
阴性控制件（普通散文 + 一只 13 位串）不触发任何一条规则，同时打印 `tok13=["1234567890123"]` ⇒ 证明值级扫描面**有东西可扫**，不是空集。
值级腿用两只我**自造**的 13 位合成串跑：命中文件 `tok13=1 equal=1`，未命中文件 `tok13=1 equal=0` ⇒ 比较机制本身能咬。
我在你的 `evidence/mirror_precheck.py` 上抓到的那台机器：`reference_tokens()` 已在 `len(refs)!=1` 处 `REFUSE`，于是 `refs` 恒为单元素集，随后那句
`if sha8(ref) not in {sha8(t) for t in refs}` **按构造不可能为假**——我用一个**故意填错**的参照值复跑同式，输出仍是 `CONTROL_HOLDS=True`。也就是说那句 "self-match control" 不证明任何东西，而它 docstring 承诺的"only allowed to report 0 equal after it has proven it can catch that value"落空。
本轮交付集扫描（`29b0488..HEAD` 的 8 只 ∪ `docs/closeout-20261010/*.md` 43 只 ⇒ 去重后 **46 只**）：五条形状 **0 命中**、CR 总 0、NUL 总 0、`tok13` 总 104（不打印任何值）。**这 46 只是从 `git show HEAD:path` 取的提交态字节**，不是我那棵被 04:33 事件污染的候选工作树（否则 `cr_total` 会被 §1 的事件假报成 BAD）。
在册 `mirror_precheck.py` 我也原样跑了一遍，同样喂这 46 只提交态字节：`VERDICT=PASS`、`files=46 bad=0 tok13_total=104 equal_to_reference=0 shape_hits=0`、rc=0，且它自己那句 control 打印 `sha8 e32743f3`。**没有读 `.env`、没有打印任何值**。
判定：**读数复现（46 只 0 命中）**；但你要的"自带咬得住的正对照"两条腿都有洞——形状腿的 `url-auth` 一条按构造扫不到含 `s` 的凭据，值腿的自对照是恒真式。修法各一句：`url-auth` 改成先剔 scheme 再匹配 userinfo（别用"排除 s"这种别名技巧）；值腿要往文件里注入参照值的**可匹配本体**并断言红的是 `equal` 那一列。

**钉子 6 台账一致性 —— 两条命令都复现，另外我挑战了 KEYS 与档位集本身。**
`ledger_row_audit.py`：§A=3 `[5,19,35]`、§B=1 `[39]`、§C=36、`max_number=40 distinct=40 gaps=[]`、`VERDICT=PASS_NO_DUPLICATE`（与票面"并集 1..40、D-39 在 §B、D-40/D-36/D-37 在 §C"逐字对上）。
`work_log_key_audit.py` 多文件：69 key、未落正文 = 无、rc=0。单文件口径脚本本身不支持（它没有单文件参数），我用 `audit_one_file.py`：`key 总数=69 缺=0`。
两处挑战成立：① **`D-41` 对档位审计不可见**——正文出现的 D 号是 1..41，脚本读到的只有 1..40，因为 `ledger_row_audit` 只解析 `|` 开头的表格行，而 D-41 写在 §H 的编号散文里（第 31 条）。所以"并集 1..40 无缺号"这句**不是**"全部编号都有档"。② **KEYS 保不住本轮最要命的读数**：`2030 passed`、`86.57`、`collected 2040`、Owner 现答那句「等我改完密码再推」——正文都有、**没有任何 key 引用它们**（在册 key 钉的是上一趟的 `2016 passed`）。这些句子被删掉，审计照旧绿。
判定：**两条命令复现成功；两句"完整性"式结论被降级**（一条档位盲区、一条 key 盲区）。
另核你说的那件：D-35 **没有**被写成已解决——§A 抬头是"只剩你手上的动作"，§C D-40 行内明写「你服务器上的那两步没做，所以 D-35 不算关闭」。唯一会让人误读的形状是 D-40 落在标题为"已裁过、已执行完"的 §C；行内自限已足够，我不判为假。

**钉子 7 未完成面 R1–R8 —— 派了独立腿逐条对，我抽查了它三处承重断言（都对）。**
结论：`对上` = R1、R5；`只对上半` = R2、R3、R4、R6、R7、R8。要点：R2 只在 runbook 顶部挂了"暂停直接执行"，正文 A4 仍是 `origin/<远端真实头>` 与"porcelain 仍只那 5 只"、A6/A7 仍留直推 master；R8 改了标题与出口两句，但 §3 仍叫"96 次裁决按面分组"、交付物 §7 仍写"§2 96 行裁决表"、分组表仍 72+15+5+4+2=98。**你点名要我核的那句成立**：R3 落成 §A D-35 + §C D-40，全档没有"已轮换/已关闭"，`decisions-needed:130` 仍是"未轮换任何凭据"。缺的那半是 R3 原文要求的"**先确定历史裸值的实际用途及复用范围**"与"核全部待推 refs"——本轮 §48/§49 没碰裸值。R6：`c15b775` 实动 4 只（`main.py` + 新 `test_agent_turn_compensation.py` 967 行 + 两条旧测试接线），六格矩阵覆盖 5 格、第 2 格（WAITING_USER）只断 SSE 帧不写消息、"追问展示"无前端腿。完整逐条在 `evidence/nail7.out`（独立腿原文）。

**钉子 8 D-35 判据与我的自拟反证 —— 判据复现（10 passed/rc=0），反证给出两问的实物答案。**
① **口令还能不能从非终端通道进来：能。** 静态面：脚本里 `isatty` 出现 **0 次**、`getpass.getpass` 2 次、不读 `ADMIN_PASSWORD`、没有 `--password` 选项（`argv` 两形都被 argparse 挡在 rc=2，库哈希不动：`ea1bef8940a9` 保持）。但"只从终端进来"这条性质**不由脚本自己保证**，它由 `getpass` 的平台分支代劳：`getpass.py:97` Windows 版在 `sys.stdin is not sys.__stdin__` 时直接退回 `fallback_getpass`，`getpass.py:120` 那个 fallback 就是"读 stdin 并打印 Warning: Password input may be echoed"。我按票面做**我自己的形状**（不复用你那 9 臂）：把 stdin 换成非终端流、`--write`，对**私有临时 SQLite** 跑 ⇒ **rc=0、打出"已重置"、库哈希 `ea1bef8940a9` → `bd07b0085ee9`**（值级只打 sha8，不打口令）。
  诚实摊开这条腿的射程：这证明的是"脚本没有 tty 前置 ⇒ `getpass` 一退到 stdin 通道就开门"。**进程级管道**那一腿在本机（Windows）测不出来——`msvcrt` 走控制台、不吃重定向 stdin，我那两腿各挂 45 秒超时（已如实记成 `TIMEOUT-45s`，没记成通过）。生产是 Linux 容器，`unix_getpass` 打不开 `/dev/tty` 时正是退到 stdin（`getpass.py:48→62`），所以**服务器上用不带 `-t` 的 `docker exec` 跑这一步，口令可以从管道进去且可能被回显**。可决定的一句话：加一行 `if not sys.stdin.isatty(): refuse`（或在 runbook A1 把"必须 `-it`"从注释升格成前置），二者选一，成本一次提交。
② **`os.getenv("ADMIN_USERNAME")` 缺省：便利可接受，但它掩盖了真正那根隐式轴。** 用户名这一层确实可接受：预览会打印目标、`--username` 能覆盖、缺省值就是 `admin`。要点名的是另一件事：脚本 `load_dotenv()` + `database.py` 的 `DB_URL = os.getenv("DATABASE_URL", ...)` ⇒ **"写哪一个库"完全由现役 `.env` 决定，且没有任何显式目标开关**（我实测这棵纯发布物树往上六级都没有 `.env`，`find_dotenv()` 返回空 ⇒ 本轮无泄漏路径；生产那台有）。这与 D-14 刚立的"默认只预览、写入要显式目标"是**同一形状的第二遍**：预览默认已经做了，显式目标没做。
③ **"`--write` 从未对真实库执行过"有没有被写成已生效：没有。** `gates.md:1168` 原样保留该限制，`decisions-needed:245` 把它列进"本轮明确没跑的腿"，`§A D-35` 的措辞是"剩下两步只能你在服务器上动"。全档 grep「已生效 / 已在真实库 / 已重置」在台账与 gates 里 0 命中（只有我这轮的探针日志里有，已隔离在新目录）。

**钉子 9 D-33 负控与那条反向护栏 —— 你的读数复现；那句说法不是台阶，但你没跑过能红的那一臂。**
复跑你的 `d33-mutation-20261012.py` 的形状我**没照抄**：我把变异插件指到自己的纯发布物树、加了两臂。读数（`evidence/nail89.jsonl`）：
- 控制腿 `NONE`：`5 passed`，rc=0。
- 臂 L（摘掉 `transition()` 里的 `_limit`）：`3 failed` —— 恰是你 MUST_DIE 那三条，护栏腿**存活** ⇒ 复现 `NEGATIVE_CONTROL_HOLDS`。
- **臂 F（从 `FREE_STEP_EDGES` 摘掉 `WAITING_USER→PLANNING`）：`2 failed` = `test_clarification_exhaustion_stays_on_its_own_axis` + `test_resume_at_exact_step_cap_succeeds_...`** ⇒ 护栏腿会红。
- **臂 C（把 `register_clarification` 的上界错绑到 `max_steps`，即"两个计数器合并"的形状）：`1 failed` = 正是那条护栏腿** ⇒ 它 docstring 里那句"谁要是…合并，这条会红"**是真的**，但本轮从没被跑过。
- `agent/state_machine.py` 前后 sha `81d58ce416855453` 相同 —— 与你日志里的 `sha_before/sha_after` **同值**（磁盘产品一字未改，双向对上）。
判定：**那句话不是自我台阶**（arm L 下存活确实是预期，它量的不是 `_limit` 那根轴）。真正的缺口是**你没证明它能红**：我补的 F/C 两臂证明它敏感。建议在册的判据补一句"护栏腿的敏感臂 = F 或 C"，否则下一轮读到"存活是预期"的人无从分辨"量错轴"与"恒不咬"。

**钉子 10 交付==文档结构 —— 独立检查器复现：现在没有劈列，也没有留尾残留。**
我自己写的检查器（`nail10/nail10_mdcol.py`，纯 stdlib、CR=0、按节切段、`\|` 当字面量、跳过表头分隔行、不用 `startswith('|')` 粗分组）。覆盖：`decisions-needed`、`gates`、`tickets/*.md` 14 只、仓内镜像 43 只、外加 `reports/*.md` 其余 24 只 ⇒ **83 只，TOTAL VIOLATIONS = 0**。
两条自证腿：① **假阳性对照**——同一份 `decisions-needed` 两种设置：`\|` 当字面量 = 0 违例；`\|` 当分隔符（你的第一版） = **3 违例，正是 D-12/D-19/D-25 三条本来就正确的行** ⇒ 我的规则不会重犯你那版的老毛病。② **能红对照**——在副本里把一处 `\|` 改成裸 `|`（只删一个反斜杠，sha `787a1c23…`→`97f212d4…`，原件未动），同一把尺子立刻报 `27 行 期望 4 实际 5`，并点名溢出成第 3 列的 `wc -l…`；缩进表控制件里 `startswith('|')` 整张漏掉、我这把照样报出。③ **留尾对照**——把 `gates.md`「票面刷新」块的首行搬走、只留缩进续行做成变异副本，检查器报 `flag=True …INDENTED…L1176`，而原 `gates.md` 报 `False`。
判定：`9ed5544`（劈列）与 `752cdff`（整块移动只搬首行）两笔修复**在运行根与镜像两侧都生效，没留残留**。附一条我同意检查器口径的旁证：票自己第 180 行有裸 `| wc -l`，但它在**行内散文**不在表格单元 ⇒ 不算违例（这正是"按节按表"与"按行 grep"的分工）。

## 3. B 路：哪条主张的证据撑不住

（每条：原句 + 出处 → 我的完整范围命令 → 读数 → 定性。命令都在候选上只读跑。）

- **B1 `gates.md:1129`「入口 tracked，且零测试、零文档指针（`git grep -n reset_admin_password -- ':!dispatch-output'` 只命中本轮新写的两份汇报）」—— 半假。**
  命令：`git -C 候选 grep -l reset_admin_password 29b0488 -- ':!dispatch-output'`
  读数：**3 只** —— 脚本本身、`docs/closeout-20261010/first-round-ledger-recheck.md`（`:31`/`:60`/`:115` 三处点名脚本路径与 `--password` 行为，就是 B-44 在册条目）、`docs/closeout-20261010/owner-review-and-next-actions-20261011.md`。`git show --stat cd2007e` 只有 2 只 backend 文件 ⇒ 这些指针**早于**修复。
  定性：**「零文档指针」为假**（你漏的那一层是你自己上一轮建的 `docs/closeout-20261010/` 镜像），**「零测试」为真**（`git ls-tree -r --name-only 29b0488 -- backend/tests | grep -ci reset_admin` = 0）。同族句：`decisions-needed:13`、`:67`（"没人知道"）、`:199`。
  这条的意义：你为"全仓没有改口令入口"更正过一次，而**同一台机器的第二次命中就在你引用自己那台机器的句子里**——这次漏的不是 `backend/scripts/`，是 `docs/`。

- **B2 `gates.md:1151`「`admin12345` …（`git grep -c admin12345` 命中 1）」—— 口径没点名，字面读数不成立。**
  命令：`git -C 候选 grep -c admin12345 HEAD`
  读数：**9 只文件 / 18 行**（`seed_admin.py` 1、脚本 1、测试 1、`docs/audit_report_20260807.md` **5**、4 只 dispatch-output patch）。
  定性：**"命中 1" 只在"seed_admin.py 单文件轴"上对**。你要证的结论（不是新暴露）反而更硬，但这句话现在会把下一位引到错的分母上。

- **B3 `gates.md:412`「现量 `git grep -n "_sse_transport|sse_transport|requeued"` 在候选 `3f605de` 全仓零命中」—— 尺子坏的（结论不坏）。**
  命令原样复跑（HEAD 工作树）：返回 **1 行**，命中的是 `docs/closeout-20261010/gates.md:412` **这句引文自己**。原因：`git grep` 默认 BRE，裸 `|` 是字面量 ⇒ 这条模式**按构造不可能命中任何代码**，它是一把恒不咬的门。
  正确写法复跑：`git grep -nE "_sse_transport|sse_transport|requeued" 3f605de -- ':!docs'` ⇒ 0 命中（rc=1）。
  定性：**判据写法错、结论对**。在册纪律"负向自证要断言是哪条规则红了"这条腿，在这里是空的。

- **B4 `decisions-needed:34`（§B D-39）「现在能作废会话的**只有**全局换 `JWT_SECRET`，或把账号 `is_active=False` … ⇒ **做不到**只踢掉某个人的旧会话」—— 枚举不全。**
  命令：`grep -n "admin/users" 候选/backend/main.py` + 读 `auth.py:get_current_user` 本体
  读数：`main.py:3027 @app.delete("/api/admin/users/{user_id}")` 是**硬删**（`db.delete(user)`，防自删、级联会话/消息）；`auth.py:63-66` 每个请求都 `db.get(User, int(payload["sub"]))` 并在 `not user` 时 401。
  定性：**存在第三条形状 = 按单个用户作废其已签发 token**（代价是连账号与历史一起删，且不可逆）。你的"库里没有 token 版本/没有会话登记表"这两句**为真**（`models.py` 无 token/session 表，payload 只有 sub/username/role/exp），但**"只有"与"做不到"为假**。根因和 B1 同一族：证据轴只写了 `backend/auth.py:45-68`，而结论是关于整个能力面的。

- **B5 `gates.md:55`「`backend/chroma_db` **按构造不存在**」—— 现在是假的，且不是 skip 的真判据。**
  命令：`stat -c '%s %y' 候选/backend/chroma_db/chroma.sqlite3` + `git check-ignore -v` + 读 `tests/conftest.py`
  读数：文件**存在**，147,456 B，被 `.gitignore:32 chroma_db/` 忽略；skip 的真判据是 `conftest.py` 里 `n < 1000 → pytest.skip(...)`。
  定性：**"按构造不存在"应改成"tracked 里没有它，盘上有空壳，判据是行数阈值"**。这条正是你 10-04 那次尺寸闸翻车的同一根轴（尺寸不证明写入、也不证明存在）。

- **B6 `decisions-needed:248` 新登记 D-41 —— 有文字、没档位；`ledger_row_audit.py` 对它天然瞎。**
  命令：`python -B evidence/ledger_row_audit.py 运行根` vs 正则扫正文全部 `D-\d+`
  读数：审计看到 1..40；正文出现 1..**41**；`git grep -nE "^\|.*D-41"` 全仓 **0 命中**。
  定性：**"并集 1..40 无缺号" ≠ "所有编号都有档"**。§H 用的是编号散文，脚本只读 `|` 行。要么给 D-41 落一格（它现在属"已裁待执行"，形状像 §C 的一行），要么把脚本改成"表格行 ∪ §H 编号行"，并在票面写清这把尺子的分母。

- **B7 票自己的形状：第 5 颗钉子要求的"自带咬得住的正对照"，在册件里那半条是恒真的**（详见 §2 钉子 5）。**同一个错你在 §E 已经自曝过一次**（"恒真三元断言"），这次它藏在"控制腿"位置上，所以更危险——它**看起来**像反证。

- **B8 `gates.md:1114` 抬头写「现场读数（本轮本机跑，cwd＝候选 `backend`）」** —— 与票第 15 行"请在副本树或 `git archive HEAD` 的纯发布物树上跑，别在候选直接跑"直接矛盾。我在纯发布物树复算同值，所以**读数是好的**，但**取数过程违反了票面纪律**，而 §48 那三趟里 pass1/pass2 还是打在未提交的补丁态（`patched-in-tree: ...=1ead4040 / b132d6ec`）。这条要记成"下一轮的取数前置"，不是"本轮结论作废"。

- **B9 `gates §48:1084`「两只被 patch 的文件落盘 blob 恰为 `1ead4040`、`b132d6ec`」—— 真，但只对 `c15b775` 那一刻。**
  现读 `HEAD:...test_agent_resume.py` = `f18de259`（`c4cc6b3` 追加了 D-33 四条），`HEAD:...test_chat_turn_persistence.py` = `b132d6ec` 未变。这句因为点名了 `c15b775` 而**诚实**，但谁按 HEAD 复算会以为自己错了。

- **B10 凭据扫描的 `url-auth` 规则有别名盲区（在册 D-12「入库前三检」用它）。**
  命令：把 `mirror_precheck.py` 里那条 `://[^s/]*:[^s/@]{3,}@` 原样取出来，对五只控制串跑（`evidence/nail5.jsonl` 的 `A2_urlauth_case`）。
  读数：用户名含 `s` MISS、口令含 `s` MISS、真实形状 `postgresql://admin:Passw0rd@db:5432/app` **MISS**；只有两处都不含 `s` 时才 MATCH。
  定性：**"URL-in-creds 命中 0"这句的分母比它看起来小**——`[^s/]` 这个"跳过 https 里的 s"的技巧，把最常见的一类含 `s` 的口令挡在射程外。修法不是排除 `s`，是先剥 scheme 再匹配 userinfo 段。

## 4. B 路：已经随头过期的数与指针（一条命令各自复算）

| 在册写法 | 现量 | 说明 |
|---|---|---|
| 票 6 行「写票时 `9ed5544`…`29b0488..HEAD` 8 笔」 | `rev-list --count 29b0488..9ed5544` = **7**；现头 = **11** | "8 笔"只在 `a05f8b2` 成立 |
| 票 6 行「其中只有两笔动产品/测试字节，其余 **5 笔**是文档」 | 7 笔时是 2+5；**8 笔时是 2+6** | 同一句里 8 ≠ 2+5 |
| 票 18 行「清单现读 `29b0488..HEAD`（写票时 7 只：脚本 1、测试 2、文档 4）」 | 在 `9ed5544` = **8 只（文档 5）**；现头 = 8 只 | "8 笔 ∧ 7 只"这一组读数**在任何头上没有同时成立过** |
| 票 6 行「起点 `19e296e` 是上一轮头」+「本轮范围 = `29b0488..HEAD`」 | `git log --oneline 19e296e..29b0488` = **7 笔**，其中含 `c15b775`（D-34）、`87f58c0`（D-14）、`a9ef432`（`.dockerignore`） | **两个基线互相矛盾**：钉子 2/3 要打的那三笔在 `29b0488..HEAD` **之外**，钉子 4 按票面清单会少覆盖 21 只（我两个区间都跑了：8/8 与 29/29） |
| `gates:1163` 票「扩到**九颗**钉子」 | 票面现在是**十颗** | `a05f8b2` 之后未回刷 |
| `gates:1174`「单文件对账对台账 **68** 个 key 缺 0」 | `audit_one_file.py` 现量 **69** 个 key、缺 0 | 加 key 后没回刷 |
| `gates:1173`/票 20「§C=36、max=40」 | 复现 = 3/1/36、max=40 | 但见 B6：分母不含 D-41 |
| `decisions:196`「交付镜像从 34 增到 **42** 只」 | `docs/closeout-20261010/*.md` 现量 **43** 只（tracked 也是 43） | 第 43 只是这张复核票自己的镜像 |
| 票 6 行「终点现读 `git rev-parse HEAD`（写票时 `9ed5544`）」 | 我复核期间走到 `2b3210a`→`ff62986`→`074e8ba` | 三笔全是 docs；`git diff --name-only c4cc6b3..HEAD` 只有 `docs/…` ⇒ **产品字节自 `c4cc6b3` 未变**，2030/86.57% 因此仍逐字有效 |

## 5. B 路：我明确没跑的腿（不写成跑过）

- **远端轴全部未核**：`ls-remote`、GitHub API、`push 17 场全红`、`value_hits=1`、`objs 4464`、"这支从未推送"。我没有独立渠道复现，一律按"未核"处理，不据此改判。
- **在线 `pip-audit` 两轴未跑**（票第 34 行本来就把它排除在本轮门禁外）。
- **前端 11 条腿未重跑**（本轮零前端字节改动；我没跑 `npm run format:check`，所以 B1 报的"第三把口径 16 只"我**没有采纳**，只标为待你自己现量：`node_modules/.bin/prettier --check .`）。
- **钉子 8 的进程级 POSIX 管道腿**本机测不了（Windows `msvcrt` 不吃重定向 stdin）；我给的是 stdlib 源码轴 + 我在同机器能跑的 in-process 腿，两者都标注了射程。
- **`--write` 对真实库**、现役栈、`slow`/`real_kb`、真实模型：一律未跑（红线）。我所有写库动作只发生在 `review-round3-20261012/nail8-temp.db`（跑完已删）。
- 候选工作树 04:33 事件**我没有去复原**（`git checkout --`/`restore` 按在册纪律禁用）。

## 6. 建议新登记的（编号由你占，我不写进台账）

1. D-41 没有档位行 / `ledger_row_audit` 分母不含 §H 编号 —— 二选一：补一行进 §C，或把尺子改成"表格行 ∪ §H 编号行"并写明口径。
2. `mirror_precheck.py` 的 13 位值腿自对照是恒真式 —— 换成正对照：注入合成本体、断言红的是 `equal` 那一列。
3. `gates.md:1129`「零文档指针」按 B1 就地撤回（"零测试"保留）。
4. `gates.md:1151` 的"命中 1"补上轴名（单文件轴）或改现量。
5. `gates.md:412` 那条 BRE 写法改成 `-E`，或撤掉"零命中"这句改用正确读数。
6. D-39 那句"只有 / 做不到"按 B4 降级为"没有非破坏性的按用户作废入口"。
7. `gates.md:55` "按构造不存在" 改成"tracked 里没有；盘上有空壳；skip 判据是 `count()<1000`"。
8. D-35 的"只从终端进来"补一条 `isatty` 前置（或把 `docker exec -it` 从注释升格成 A1 前置），并按 B 路②补"写哪个库没有显式目标开关"这一条限制。
9. 本轮三趟全量的取数形状（`cwd=候选`）与票面纪律冲突 —— 下一轮门禁票里把"纯发布物树/副本树 + 前后 `find -type f | wc -l`"写成前置，而不是只写 `porcelain=0`。
10. **04:33 候选工作树被整片重写**（1486 只脏、31 只含内容差异、`.dockerignore` 退回修前）—— 这条要你裁：谁在做、要不要停、恢复方向。

## 7. 我的交付物（全部新文件名，绝对路径）

- 本报告：`C:/Users/33393/Desktop/fazhi-nondeploy-closeout-20261010-b4e7a2/reports/independent-review-20261012-round3.md`
- 钉子 1：`.../review-round3-20261012/run_nail1.sh`、`.../evidence/pytest.full.20261011T195411Z.log`、`.../evidence/pytest.collect.20261011T195256Z.log`、`.../evidence/junit.full.*.xml`
- 钉子 2：`.../run_nail2.sh`、`.../evidence/nail2-attribution.log`、`.../evidence/nail2-runner.out`
- 钉子 3：`.../run_nail3.sh`、`.../evidence/nail3-dockerignore/listing-{new,old}.txt`、`.../evidence/nail3-dockerignore/probe.*.log`
- 钉子 4：`.../nail4_delivery_equals_acceptance.py`、`.../evidence/nail4.out`
- 钉子 5：`.../run_nail5.py`、`.../evidence/nail5.jsonl`
- 钉子 6：`.../run_nail6_keys.py`、`.../evidence/nail6-keys.out`、`.../evidence/r3-keyaudit-multi.txt`
- 钉子 7：独立腿原文 `.../evidence/nail7.out`
- 钉子 8/9：`.../run_nail89.py`、`.../r3_state_mut_plugin.py`、`.../evidence/nail89.jsonl`
- 钉子 10：`.../nail10/nail10_mdcol.py`、`.../nail10/reading.md`、`.../nail10/mutation_target.md`、`.../nail10/control_indented.md`
