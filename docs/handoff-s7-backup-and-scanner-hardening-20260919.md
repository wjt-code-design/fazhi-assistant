# 执行方案书 · S7：备份面与密钥扫描器的判据加固（2026-09-19，交给新会话）

写给**没有本会话记忆**的接手者。读完这一页你应当能：知道前面做了什么、能独立复证、知道只有两件事可以做、
其余必须回来问 Owner。本票是上一会话（单会话合并执行 S1–S6）收口后经两轴代码评审产出的**整改票**。

- 起票时 HEAD = `88bd167`（`feat(S4/备份): 备份面补上 quota 账本、容器侧 app.db 与 media`），已跟踪文件 **0 脏**。
- 起票会话的净结论：**S4 的票面 DoD 未达成**（见 §3 与 §4），S1 有一台仪器**永远放行**。两件事都可在本票修完。
- 详细留痕（不必先读，出问题再查）：`docs/superpowers/plans/2026-09-19-single-session-consolidation.md`
  （S1–S6 全部执行记录 + 「审计轮」A-1…A-7）、`.workbuddy/memory/2026-09-19.md`（当日逐时日志，含一起事故）。

## 0′. 这张票怎么用

1. §0 是不可协商禁令；§1 是开工前置取证（**必须全跑完**，任何一条不符先停下报告）；§4 是 Owner 已经拍定的
   七个决策（**不许重开**）；§5/§6 是本票唯二可执行项；§8 是收口纪律；§11 是不许动的清单。
2. 本票里所有 `file:line` 指针与所有钉住的哈希都在 HEAD `88bd167` 上逐条复量过（复量结果写在括号里）。
   你接手时 HEAD 多半已不是它 ⇒ **引用前先 `grep -n <符号名> <文件>` 复量**。本仓的交接文档里
   已有多处行号漂移导致错引用的实例（上游票 `docs/handoff-takeover-20260919.md` §0.4 列了四条，未复测）。
3. 环境（起票会话实测，可直接用）：仓库根 `C:\Users\33393\Desktop\ai-legal-helper`；
   解释器一律 `backend\venv\Scripts\python.exe`；pytest 配置 `backend/pyproject.toml:92`
   （`testpaths=["tests"]`，marker `slow`）；前台 shell 是 **Git Bash**，不是 PowerShell。

## 0. 四条不可协商（违反即停手问 Owner）

1. **不改生产开关、不改判据数值、不改任何 `*_check` 默认值**。`gate2_runner.py` 判据本体冻结
   （sha256 `ae2e412059ed68ac1514c62727cee61c50b8a2d6fe7e38a77c7e05631847e295`；起票会话 13:0x 复量**仍是这个值**，
   且实测该文件 **0 个 CRLF** ⇒ 这个哈希与换行口径无关，可直接比）。
2. **不覆盖冻结资产**：`evals/frozen-cases-v2.json`、`evals/probe-results.json`、任何 `*-sessions.json`、
   `dispatch-output/r1-ob-offline-20260916/counterexamples.json`。
3. **不推送、不部署**（Owner 令）。而且本仓从**活仓**做 `bundle`/`push`/`clone` 必 fatal（`.git` 缺父提交
   `0263bd56`）—— 起票会话 12:26 又一次亲眼复现：`error: Could not read 0263bd56… / Failed to traverse
   parents of commit 76c1eea…`。这不是你的错，别去"修"它，携带路径见 §10。
4. **`.git` 有洞 ⇒ 活仓不能做否证类取证**。凡"某文件历史上有没有进过提交"这类**否定式**结论，
   必须在图完整的救援仓（`Desktop/fazhi-rescue-88bd167-20260919/repo.git`）上问；
   在活仓问，输出里一旦夹了 `fatal:`，**该次调用所有读数全部作废**（起票会话就是这么抓到我自己的一条假绿）。

## 1. 开工前置取证（八条全跑完；任何一条不符就停下报告）

| # | 命令 | 期望 | 为什么 |
|---|---|---|---|
| P1 | `pwd -W` | 以 `\ai-legal-helper` 结尾 | 本仓发生过"在 Desktop 上 grep 然后宣布文件不存在"的假阴性 |
| P2 | `git log --oneline -3` | 记下游标，**别人可能又提交了几笔** | 多会话共享同一工作树 |
| P3 | `git hash-object backend/scripts/backup_data.py` vs `git rev-parse HEAD:backend/scripts/backup_data.py`（根目录下用这条；**在 `backend/` 里则要写 `HEAD:./scripts/…`**，否则报 outside repository） | **相等**（起票会话实测两侧同为 `d99f02c9…`） | 不等 ⇒ 有人正在改被测文件，你的复证没有意义。**别用 mtime 判断，用 blob** |
| P4 | `grep -n "EXTRA_SQLITE\|MEDIA_DIR\|def backup_extras\|def _check_env_contract" backend/scripts/backup_data.py` | 四个符号都在 | 本票要动的正是这几处 |
| P5 | `grep -n "QUOTA_DB" backend/quota_store.py docker-compose.yml` | `quota_store.py:17` 走 `os.getenv("QUOTA_DB", …)`；compose 注入 `QUOTA_DB=/data/quota_used.sqlite` | §6 那条 BLOCKER 的事实底座，**必须自己复量** |
| P6 | `grep -n "assert_matches\|不做重定向" backend/scripts/chroma_dir_guard.py` 再 `grep -n "CHROMA_DIR\|QUOTA_DB" backend/tests/conftest.py` | 前者命中守卫函数与判例原话；**后者必须看到 `conftest.py:23` 无条件设 `QUOTA_DB`、`:40` 无条件设 `CHROMA_DIR`** | §6 要照抄它的形状与**调用位置铁律**；而这两行"无条件赋值"正是 §6.2 那条假绿陷阱的成因 |
| P7 | `grep -n "exclude" backend/pyproject.toml`（看 `[tool.mypy]` 那节） | `exclude = ["(?x)^(tests/\|scripts/\|venv/)"]` | **`scripts/` 不参与 mypy** ⇒ `backup_data.py` 的类型注解没有任何门禁，全靠手 |
| P8 | 读 `dispatch-output/s4-backup-coverage-20260919/run_mutations.py` 的 `MUTATIONS` 列表（`:19-24`） | 现状**四条**替换串（本票 §6.5 要扩到七条） | 该跑者会**改写生产码再按字节还原**。不要拿它做 `--help` 空跑来"试试"——它没有未知参数守卫，直接起跑就是真改文件 |

### 1.1 现场变化（起票后追加，15:2x 实测——**这条比 P 表更重要，先读它**）

起票会话在 12:5x 写这张票时，"只有我一个会话在执行"是 Owner 当时的安排；**15:2x 实测该前提已不成立**：

- `git status --porcelain -uno` = **19 个已跟踪文件被改动**，`git diff --shortstat` = **176 insertions / 56 deletions**；
- 名单落在 `backend/agent/{fee_calc,limitation_calc,phantom_check,service,verifier,writer}.py`、
  `backend/{main,retrieval,schemas}.py`、`backend/knowledge_base/fee_formulas.json`、
  `backend/tests/{test_entity_precision,test_limitation_calc}.py` 与 `frontend/lib/*` 等 5 个前端文件；
- 这些文件的 mtime 分布在 **14:41:39 – 14:59:02**，而 HEAD **仍是 `88bd167`**（没人提交）⇒ 是**在途未提交的编辑**。

对你的三条直接影响：

1. **你这三个目标文件当时是干净的**（15:2x 实测 `git hash-object` == `git rev-parse HEAD:<path>` 三个全等），
   但这**只在那一刻成立** ⇒ P3 每次动手前重跑，不要复用上一条命令的结果。
2. **`run_gate_full.py` 很可能报 `RUN_VOID`**（它跑前后对 `backend/` 全部 `.py` 取 sha256，别人一改就 VOID）。
   VOID 时"0 failed"作废，但**隔离判据依然有效**（§6.6 末已写）。别把 VOID 当自己的回归，也别重跑到绿为止——
   报告给 Owner 定时序。
3. 冻结面**没被动**（15:2x 实测 `state_machine.py`/`prompts.py`/`gate2_runner.py`/`evals/` 四项 0 改动），
   `gate2_runner.py` 的 sha256 复量仍等于 §0.1 钉的值 ⇒ 你不需要为此停手，但**别顺手碰那批文件**。

## 2. 前面做了什么（净结论，一句话一条）

1. **S1**：写了一台**只报形状、永不打印值**的全仓密钥扫描器，扫 71,159 文件 / 29 文件命中 / 共 71 次命中；
   真键家族（51 位、`sha12=1ed4b9c74505`）21 次命中落在**恰好 6 个文件**，全部未跟踪且各有忽略规则。
2. **S2**：`.gitignore` 补 `/_*` 与 `dispatch-output/**/*auth-state*.json`，堵 `git add -A` 泄密路径；提交 `3c51879`。
3. **S4**：给备份工具补上 quota 账本 / 容器侧 `data/app.db` / `media/` 三件；提交 `88bd167`；红→绿→4 道变异→全量 1275。
4. **审计轮**：对上面每一句完成声明重测，能重测的都重测了；全量门禁本次新跑 `audit-20260919` =
   **RUN_VALID / rc=0 / 1275 passed, 18 deselected / 源码变动 0 / chroma 指纹前==后 / app.db cc 10784→10784 / quota cc 2→2**。
5. **两轴评审**（Standards / Spec 并行 sub-agent）的结论合并成 §3 那张表（12 行）。起票会话逐条复验：
   **11 条成立、1 条（#11 跳过清单的实际成本）未复验**。
   另有一条评审判断被我校正、**没有进 §3 表**：评审称"缺件断言是空枪"，实测 M1 变异能让它红
   （`mut-M1` 日志 3 failed 在案），真实问题是**精度不足**（只点名、不断言原因）——处置见 §6.4。

## 3. 评审结论（已复验，未复验的标了出来）

| # | 轴 | 判定 | 事实 | 起票会话是否亲眼复验 |
|---|---|---|---|---|
| 1 | Spec | **BLOCKER** | 附属库源路径**硬编码** `BACKEND/data/…`，而应用自己认 `QUOTA_DB` env；容器内跑 ⇒ 三件全"跳过"、仍打"备份完成"、rc=0 | ✅ 复量 `quota_store.py:17` + compose `:44` + `.dockerignore` 排除 `*.db`/`*.sqlite*` |
| 2 | Spec | **BLOCKER** | 票面 Step 3(b) 要求"把 `data/app.db` 路径写错 ⇒ 必须红"；实际 M2 做的是**丢掉目标名**。更根本：两份源库用同一个 `_seed_sqlite` 播种（都插 `v='x'`）、且**所有 extras 测试整份替换 `EXTRA_SQLITE`** ⇒ 源↔目标映射**原理上不可能变红** | ✅ 读 `test_backup_data.py:136-142` 与 `run_mutations.py:19-24` |
| 3 | Spec | **BLOCKER** | 扫描器 `main()` 无条件 `return 0`（`scan_trace_shape.py:150`），而票面判据是"真形态密钥出现在**受跟踪**文件 ⇒ 立即停手" ⇒ `tracked_with_hits` 从不影响退出码，"rc=0"无信息量 | ✅ 读全文件 |
| 4 | Standards | **HARD** | 附属库 `verify_sqlite(out_file)`（`:133`）未包 try，而主库同一调用（`:174-178`）包了 `(OSError, sqlite3.Error)` ⇒ fail-closed **不对称** | ✅ |
| 5 | Standards | **HARD** | 模块 docstring（`:1-16`）与恢复提示（`:216`）都没提新增三件；`media` 零验证，与文件自己写的不变式"光备份不验证等于没备份"冲突 | ✅ |
| 6 | Standards | **HARD** | `monkeypatch.setattr(..., raising=False)` 打在**确实存在**的属性上 ⇒ 改名后桩静默失效、测试转而读写**真实** `backend/data/`（隔离隐患） | ✅ |
| 7 | Standards | JUDGEMENT | `tracked_paths` 用 `check=False`（`:60`）⇒ git 失败时返回空集，把所有命中**误标为未跟踪** | ✅ |
| 8 | Standards | JUDGEMENT | `files_scanned += 1`（`:113`）在扫描**之前**；`scan_file` 对 0 字节 / >50MB / `OSError` 静默返回 `[]` ⇒ "71,159"不是覆盖数 | ✅ |
| 9 | Standards | JUDGEMENT | `OVERLAP=64` 使跨块命中**双计**；`offset` 写了从不读 ⇒ 去重是"想到没做" | ✅ |
| 10 | Spec | 口径 | 文档里"29 个命中"实为 `files_with_hits=29`，总命中 **71**（openai 17 / generic 46 / aws 4 / jwt 4） | ✅ 从 `scan-result.json` 重算 |
| 11 | Spec | CREEP | 扫描器跳过 `backups/` ⇒ **备份包自身永不扫**，而 S4 刚把包面扩大；`generic_assign_secret` 是票面"三条正则"之外的第 4 条（但载重：46/71） | 未复验跳过清单的实际后果（要扫一个包才知道成本） |
| 12 | Spec | GAP | `restore_drill.py` 只演练 `app.db` + `chroma_db` ⇒ 包里 5 件有 3 件从未演练 | ✅ grep 到只引用 `app.db`/`chroma_db` |

**评审给的正向结论**（起票会话复算过）：gitignore 语法经 `check-ignore` 实证；`/_*` 不误伤
`backend/tests/_r15_tripwire_probe.py`；四条正则重跑 `scan-result.json` **无任何原值外泄**；
`.gitignore` 与新增注释是 WHY 式。

## 4. Owner 已拍定的七个决策（不许重开，也不要"顺手做得更多"）

| # | 决策 | 结论 |
|---|---|---|
| Q1 | `backup_data.py` 对"附属源路径 vs `QUOTA_DB`"分歧的处置 | **照 T-E2 判例：分歧即拒绝执行**（不跟随 env、不只补文档） |
| Q2 | 票面 Step 3(b) 那道变异的补法 | **可区分播种 + 守卫测试**：两份附属库播不同哨兵值，断言目标内容来自其源；新增 M5/M6；守卫本身要有测试 |
| Q3 | 三条 Standards 硬伤 | **全修 + 上备份清单** `backup_manifest.json`（同时了结 media 无验证 / 映射无处查 / drill 无物可验） |
| Q4 | 扫描器"停手"判据 | **分级判停 + 口径拆清**（真凭据形状才算停手指征；generic 只报不判） |
| Q5 | 拆笔与顺序 | **两笔：先扫描器（S7-a，不碰 `backend/`），再生产码（S7-b）**；各自 show your work |
| Q6 | 自加的 auth-state 规则 + 过期数字 | **追认**，并把注释里"97 个"换成**复测命令** |
| Q7 | 两笔之后 | **停手回报**，等 Owner 裁决剩余四件（见 §11） |

## 5. 任务 A：S7-a 扫描器加固（先做）

**Files**：改 `dispatch-output/secrets-hygiene-20260919/scan_trace_shape.py`（该文件**已跟踪**，`git show --stat` 复量）。
**提交范围**：只提交这一个 `.py`。**`scan-result.json` 继续不提交**（现状即如此，别顺手 `add`）。
**pre-commit 范围**：`--files dispatch-output/secrets-hygiene-20260919/scan_trace_shape.py`。
**不新增 pytest 测试**（这台仪器在 `dispatch-output/` 下、不在 `backend/tests/` 的 `testpaths` 里），
标定读数写进计划文档与当日日志，**不新建第四个文件**。

**退出码契约（先定死，后面所有判据都引用它）**：

| rc | 含义 | 触发条件 |
|---|---|---|
| `0` | 正常且无停手指征 | 无"真凭据形状"命中受跟踪文件，且 git 列表成功 |
| `3` | **停手**（S1 票面定义的泄漏指征） | 存在 ≥1 条 `openai_style_sk` / `aws_akid` / `jwt_like` 命中落在 `tracked is True` 的文件 |
| `4` | **仪器失效**（尺子坏了，任何读数都不作数） | `git ls-files` 子进程 `returncode != 0` |

⚠️ `3` 与 `4` **必须分开**：把"尺子坏了"和"发现泄漏"混成同一个非零码，就是本票 §3#7 要修的那个毛病。
若两条件同时成立 ⇒ 取 `4`（仪器失效优先，因为它让 `3` 的判定不可信）。

0. **动手前先给证据上锁**：`sha256sum dispatch-output/secrets-hygiene-20260919/scan-result.json` 的值记进留痕，
   收口时复测**必须相等**（这份 JSON 未入库，被覆盖就救不回来）。

1. **分级判停**。"真凭据形状" = 三条正则 `openai_style_sk`、`aws_akid`、`jwt_like`；
   `generic_assign_secret` **不算**（它命中 46/71，绝大多数是占位值与第三方库源码）。
   实现要求：命中为真凭据形状**且**该文件 `tracked is True` ⇒ 打印一行
   `[STOP] 真凭据形状命中受跟踪文件：<rel> pattern=<name>`，并 `return 3`。
   （`[STOP]` 这个前缀是判据的一部分，标定测试要断言它。）
2. **`tracked_paths` 的 git 失败要显式化**。改成返回 `(paths, ok)` 或直接抛：`returncode != 0` 时
   打印 `[INSTRUMENT] git ls-files 失败 rc=<码> stderr=<前 200 字符>`，把**本次所有** `per_file[rel]["tracked"]`
   置为字符串 `"unknown"`（注意：这是**全局**置 unknown，不是逐文件判断——git 列表失败时无法区分），
   并 `return 4`。
   summary 字段随之定型（**只有这三个列表**，别再发明别名）：
   `tracked_with_hits` 收 `tracked is True`、`untracked_with_hits` 收 `tracked is False`、
   新增 `unknown_with_hits` 收 `tracked == "unknown"`。
3. **先加 `--out`，再加任何测试**。现状输出路径写死在 `scan_trace_shape.py:141`（脚本同目录 `scan-result.json`），
   而那份 JSON 是 S1 唯一的命中基线 ⇒ 不加 `--out` 就跑标定，第一件事就是把它盖掉。
   要求：`--out` 默认值 = 现在的 `scan-result.json` 路径（**保持向后一致**），标定时一律显式指向 temp。
4. **口径拆清**。summary 定型为这几个键（**不要同时保留 `scanned` 与 `files_scanned` 两个同义字段**）：
   - `files_scanned`：真正打开并读到结尾的文件数（不含下面三类）。
   - `skipped`：`{"zero_byte": <n>, "too_big": <n>, "oserror": <n>}` —— 0 字节与超 `--max-mb` 的
     **不再计入 `files_scanned`**（旧口径把它们算进去了，这就是"71,159 不是覆盖数"的成因）。
   - `skipped_dirs`：`{<目录名>: <本次 walk 中被剪掉的该名目录个数>}`，只含**实际出现过**的剪枝项。
   ⚠️ 新 `files_scanned` 与旧 `71159` **不可直接比较**。报告里两个都给，各注明口径与命令。
5. **去重**（消掉 `OVERLAP=64` 的跨块双计）。键 = **`(pattern, 绝对起始偏移, token 字节长)`** 三元组，
   同一键只计一次；绝对起始偏移 = `已读字节数 - len(prev_tail) + m.start()`（首次 `prev_tail` 为空，该式退化为
   `m.start()`）。⚠️ **必须含 `pattern`**：同一位置可能同时被 `openai_style_sk` 与 `generic_assign_secret` 命中
   （真键家族就是这样 15+6 的分布），含了 pattern 才不会把这两种命中误并成一条。
   去重后 `by_pattern.n` 会**变小**（现状 71）—— 这是修正不是回归，报告里写清去重前后两个数。

**判据（三个方向都要亲眼看到，缺一个就是空枪）**：造一个**种子仓库**当扫描根（扫描器已有 `--repo` 参数）。
下面 `<T>` 指一个 temp 目录，**不得**位于 `C:\Users\33393\Desktop\ai-legal-helper` 之内：

```
mkdir -p <T>/seed && cd <T>/seed && git init -q
printf 'KEY=sk-%s\n' "$(printf 'a%.0s' $(seq 1 48))" > <T>/seed/planted.txt    # sk- + 48 字符 = len 51
PY=C:/Users/33393/Desktop/ai-legal-helper/backend/venv/Scripts/python.exe
SC=C:/Users/33393/Desktop/ai-legal-helper/dispatch-output/secrets-hygiene-20260919/scan_trace_shape.py

情形 A（受跟踪 ⇒ 该停手）：
  cd <T>/seed && git add planted.txt
  "$PY" "$SC" --repo <T>/seed --out <T>/a.json ; echo rc=$?       期望 rc=**3**，stdout 含 `[STOP]` 且点名 planted.txt
情形 B（取消跟踪 ⇒ 不该停）：
  cd <T>/seed && git rm --cached -q planted.txt
  "$PY" "$SC" --repo <T>/seed --out <T>/b.json ; echo rc=$?       期望 rc=**0**，且 a.json/b.json 里 planted.txt 从
                                                                   tracked_with_hits 移到 untracked_with_hits
情形 C（仪器失效 ⇒ 读数不作数）：
  mkdir -p <T>/notarepo
  "$PY" "$SC" --repo <T>/notarepo --out <T>/c.json ; echo rc=$?   期望 rc=**4**，stdout 含 `[INSTRUMENT]`
收尾：rm -rf <T>
```

⚠️ 情形 C 顺带把 §3#7 修没修好测出来了：`git ls-files` 在非仓库目录必然 `returncode=128`。
⚠️ `printf 'a%.0s'` 造的是 48 个小写字母 `aaaa…`——**故意全同**，任何真实密钥都不长这样；
形状仍走 `sk-[A-Za-z0-9]{20,}`，与真键家族同形状。期望值来自判据（"这个形状出现在受跟踪文件就该停"），
不是来自实现 ⇒ 这条标定同时是"期望独立于实现"的来源。

**收口前还有一道基线门**：改完后重扫**真仓库**一次（`--repo` 用默认值，`--out` 显式指到 temp，别指回原路径）：

```
backend/venv/Scripts/python.exe dispatch-output/secrets-hygiene-20260919/scan_trace_shape.py --out <T>/full.json
```

期望 **rc=0**（真凭据形状目前无一在受跟踪文件里，起票会话从 `scan-result.json` 逐条复算过：
`tracked_with_hits` 只有 `dispatch-output/agent-mainline-fix-20260911/verify.ps1` 与
`dispatch-output/agent-timeout-h1-20260912/verify-h1.sh` 两条，二者命中的都是 `generic_assign_secret`）。
⇒ 若这道门给你 **rc=3**，那是 S1 票面的停手条件**真的触发了**：立即停止、原样报告文件名与形状，
**不许**改判据让它变绿，也不许把泄漏写成"待后续"。给你 **rc=4** 则是仪器或 git 出问题，同样停手报告。

⚠️ **绝不要把伪造键写进真仓库的任何文件**，也不要写进 `dispatch-output/`；只在 temp，用完 `rm -rf`。

## 6. 任务 B：S7-b 备份面加固（后做，动生产码）

**Files**：`backend/scripts/backup_data.py`、`backend/tests/test_backup_data.py`、
`backend/tests/test_chroma_dir_guard.py`（§6.2 第 1 条接线断言落在这里）。
**DoD**：红→绿留痕 + **7 道变异全部拦住** + 全量门禁一次 RUN_VALID + pre-commit + 真跑一次备份 rc=0 且包内有清单。

**产物落点（先定，别随手放）**：新建 `dispatch-output/s7-backup-hardening-20260919/`，
本票的变异跑者与 7 份 `mut-*.log` 都放这里。
🚨 **不要改 `dispatch-output/s4-backup-coverage-20260919/run_mutations.py` 及其日志**——那是 S4 已交付的
证据（`88bd167` 的"4 道变异全部拦住"就是靠它撑的）；改了它，别人的收口记录就与磁盘上的东西不符。
复制一份过来改。**本票只提交 §6 顶部 Files 那三个文件**，`dispatch-output/s7-*` 目录整体不入库（与 S4 惯例一致）。

**提交信息（两笔，照抄格式）**：
第一笔 `fix(S7-a/扫描器): 真凭据形状命中受跟踪文件即停手，计数口径拆分并去重`；
第二笔 `fix(S7-b/备份): 附属库源路径与 QUOTA_DB 分歧即拒绝，备份包新增清单`。
两条都必须写进文件用 `git commit -F` 提交（英文双引号、反引号、`$` 不许出现在提交信息里）。

### 6.1 先改可测性：把 `EXTRA_SQLITE` 拆成"目录 + 映射"

现状（`backup_data.py:49-52`）：字典里**目录与文件名混在一起**，测试只能整份替换 ⇒ 映射不在测试范围内。
改成（**本票定这条，不再给替代方案**；任何等价写法都要满足 §6.5 的 M5/M6 判据）：

```python
DATA_DIR = os.path.join(BACKEND, "data")
EXTRA_SQLITE = {                      # 包内名 -> 源文件（名字即契约，restore 时放回 DATA_DIR/<value>）
    "quota_used.sqlite": "quota_used.sqlite",
    "data_app.db": "app.db",
}
```

配套 `backup_extras` 里源路径 = `os.path.join(DATA_DIR, fname)`。
**测试改为只 patch `DATA_DIR`**（不再 patch `EXTRA_SQLITE`）⇒ 名称↔文件的映射第一次进入被测面。

### 6.2 守卫（Q1 决策）

在 `_check_env_contract()` 里追加对 `QUOTA_DB` 的分歧检查，**复用现成的 `chroma_dir_guard.assert_matches`**
（签名实测为 `assert_matches(expected_dir, caller, env_name="CHROMA_DIR")`，传 `env_name="QUOTA_DB"` 即可）：
env 未设 ⇒ 放行；`os.path.abspath(env) == os.path.abspath(期望源)` ⇒ 放行；否则 `raise SystemExit`。

⚠️ **别写私有函数**（起票会话实测：`backend/tests/test_chroma_dir_guard.py:58` 有一条**源码级接线断言**，
它检查这三个脚本的源码里含字面量 `assert_matches(`。你另起一个 `_assert_quota_matches` 之类
**只要不含这个子串**，那条测试就红 —— 而它现在不在本票的改动清单里，你会以为是自己把谁改坏了）。
若你坚持要私有函数，就必须同批改 `test_chroma_dir_guard.py`，并在票里写清理由。

⚠️ 另两条实测出来的**同文件耦合**，动 `backup_data.py` 前先看一眼 `test_chroma_dir_guard.py`：
- `:48` 有一份写死的 `WIRED = ["backup_data.py", "rebuild_embeddings.py", "switch_embedding.py"]`；
- `:55` 的正则要求 `_check_env_contract()` 是 `if __name__ == "__main__":` 之后**第一条语句**
  （`\s*\n\s*` 只容得下空白，**插一行注释就会红**）。你要写的"调用位置是硬约束"那条注释，
  放进 `_check_env_contract()` 的函数体上方，**不要**插进 `__main__` 与那行调用之间。

🚨 **测试怎么放（这一节本票改过两次，按最终版做）**。本仓已有的做法是**源码级接线断言**
（`test_chroma_dir_guard.py:46-58` 的注释原话："用源码判而不是 import 模块"），照它做，别自己发明：

1. **接线（必做，且这条就够挡住 §3#1 那个容器 bug）**：在 `test_chroma_dir_guard.py` 里加一条断言 ——
   `backup_data.py` 的源码中 `assert_matches(` 那一支必须带 `env_name="QUOTA_DB"`（正则或子串判定都行，
   但要能区分"传了 env_name"与"没传"）。**期望值来自判据**：票面 Q1 说的是"`QUOTA_DB` 分歧即拒绝"。
2. **行为（三态）**：`assert_matches` 本体的三态已被 `:21`（未设）/`:26`（不同写法同指）/`:38`（分歧即拒）
   三条覆盖，**不必重写**。你只需再加一条"backup_data 侧算出的期望源确实是 `DATA_DIR/quota_used.sqlite`"
   的小测试（读模块常量即可，不执行守卫），挡住"接线接对了但期望路径算错"这条缝。
3. 🚨 **不要写"直接调 `backup_data._check_env_contract()` 看它抛不抛"这种测试**。
   实测 `conftest.py:40` **无条件**设 `CHROMA_DIR=<temp>`，而 `backup_data.CHROMA_DIR` 写死 `backend/chroma_db`
   ⇒ 该函数**第一行的 chroma 守卫在测试里永远抛 SystemExit**：你的"该抛"用例会因为**错误的分支**通过、
   "不该抛"用例永远红，两个方向都测不到 `QUOTA_DB`。（若确有理由要真调它：先
   `monkeypatch.setattr(backup_data, "CHROMA_DIR", os.environ["CHROMA_DIR"])` 把第一道守卫对齐，
   并在 docstring 里写明为什么。）

### 6.3 备份清单（Q3 决策）

`main()` 末尾（`extras` 判定通过之后、打"备份完成"之前）写 `out/backup_manifest.json`。
**任何失败返回路径都不写清单**（清单 = "这个包可用"的凭证，坏包里放一份看起来完整的清单正是本票要防的形状）。

**顶层形状定死**（字段名逐字照抄，别改名、别加同义字段）：

```json
{
  "version": 1,
  "created_at": "<time.strftime('%Y-%m-%dT%H:%M:%S')>",
  "entries": [ ... ]
}
```

`entries` 是**列表**，每条按 `dest` 排序，且**只来自你显式创建的目标名清单**——🚨 **不许 `walk(out)`**：
`verify_sqlite` 会在备份文件旁留 `.verify.tmp`（它 `finally` 里会 `os.remove`，但一旦它抛异常就残留），
walk 会把残留当产物记进清单。四类条目的形状：

| `kind` | 覆盖的 `dest` | 必带字段 |
|---|---|---|
| `sqlite` | `app.db`、`quota_used.sqlite`、`data_app.db` | `source`（绝对路径）、`bytes`、`sha256`、`integrity_check`（`verify_sqlite` 那句 msg） |
| `file` | `chroma_index.json`（`--skip-chroma-export` 时**不出现**） | `source`、`bytes`、`sha256` |
| `dir` | `chroma_db`（`--skip-chroma` 时**不出现**） | `files`、`bytes` —— **不哈希**（真实库 362MB，哈希会把备份 I/O 翻倍） |
| `dir` | `media` | `files`、`bytes`、`items`（每个文件一条 `{path, bytes, sha256}`）；超过 5,000 个文件时**退化为**只记 `files`/`bytes` 并打一行 `[Manifest] media 文件过多，仅记计数` |

- **哈希对象一律是包内文件**（不是源），因为它要回答的是"这个包里到底有什么"。
- `--skip-chroma` / `--skip-chroma-export` 的既有语义**不许改**（跳过就不进 entries）。
- 恢复提示那两行（`:216-217`）同步改写，把"包里有什么、放回哪儿"写清（§3#5 的另一半），
  并**指向清单文件本身**（`backup_manifest.json`）。

### 6.4 对称性与桩

- 附属库 `verify_sqlite` 包 `try/except (OSError, sqlite3.Error)`（`:133` 现无守卫），
  打印格式**定死**为 `[Extras] ERROR <name> 恢复验证执行失败：<exc>`、状态置 `failed`
  （测试要断言这整串，不能只断言 `failed`）。
- 测试里 `monkeypatch.setattr(..., raising=False)` 实测 **6 处**：`test_backup_data.py:165 :167 :194 :196 :219 :220`，
  **全去**（起票会话实测这些属性在模块上都存在：`DB_PATH`/`CHROMA_DIR`/`EXTRA_SQLITE`/`MEDIA_DIR` 皆 `True`）。
  §6.1 落地后的分布是确定的：`EXTRA_SQLITE` 那 **3 处**（`:165 :194 :220`）被 patch `DATA_DIR` 取代，
  `MEDIA_DIR` 那 **3 处**（`:167 :196 :219`）只删 `raising=False` 这个参数本身。**改完 `grep -c raising=False` 必须是 0**。
- 缺件跳过那条断言（`test:207` `assert "media" in printed`）**改成断言原因+名字同现**，
  例如 `"跳过（源不存在）：media" in printed`。⚠️ 注意：现状**不是**空枪（M1 变异能让它红，日志在案），
  改它是提高精度；不要因为"评审说它是假绿"就顺手删掉重来 —— 那句判断起票会话已校正过（见计划 A-2）。

### 6.5 变异：7 道，全部必须拦住

下表 M1–M4 的"从"串是 §6.1 改造**之前**的现状字面量（起票会话在 `88bd167` 上逐条 `count==1` 复量）。
🚨 **M1–M4 的"从"串在 §6.1 之后也要重新定位**（循环变量、调用形状都会变），七道一律按"新串唯一命中"重写。

| 代号 | 替换（从 → 到） | 期望被击中 |
|---|---|---|
| M1 | `for name, src in EXTRA_SQLITE.items():` → `for name, src in []:` | 三条附属测试全红（现状实测 3 failed） |
| M2 | `out_file = backup_sqlite(src, dest_dir, name)` → `out_file = backup_sqlite(src, dest_dir)` | 覆盖 + fail-closed（实测 2 failed） |
| M3 | `if os.path.isdir(MEDIA_DIR):` → `if False and os.path.isdir(MEDIA_DIR):` | 仅覆盖测试（实测 1 failed） |
| M4 | `if any(status == "failed" for _, status in extras):` → `if False and any(status == "failed" for _, status in extras):`（**整串照抄，不许写 `any(...)` 省略号**） | 仅 fail-closed 测试（实测 1 failed） |
| **M5** | `EXTRA_SQLITE` 两个 value 互换：`"app.db"` ↔ `"quota_used.sqlite"` | **新**：击中"内容 marker"那条 |
| **M6** | `"data_app.db": "app.db"` → `"data_app.db": "../app.db"`（源指向主库，即票面 Step 3(b)） | **新**：击中 marker 那条，且**必须是因为内容不对而红** |
| **M7** | 删掉 `_check_env_contract()` 里那句 `env_name="QUOTA_DB"`（退回默认 `CHROMA_DIR`） | **新**：击中 §6.2 第 1 条接线断言 |

改造**前**的对应字面量（起票会话 13:3x 实测每条在 `backup_data.py` 里唯一命中 `1` 次，可直接当 §6.1 的起点）：
`for name, src in EXTRA_SQLITE.items():` / `out_file = backup_sqlite(src, dest_dir, name)` /
`if os.path.isdir(MEDIA_DIR):` / `if any(status == "failed" for _, status in extras):` /
`"data_app.db": os.path.join(BACKEND, "data", "app.db"),`（M5/M6 就是改这最后一条所在的字典）。

**M5/M6 的判读规则（不写清就会被误当"拦住了"）**：
- 0 条测试红 ⇒ **逃逸**，说明 §6.1 的映射改造没到位（跑者会因 rc=0 报"逃过 🚨"，别把这道当通过）。
- 只让 marker 那条红 ⇒ ✅ 正是设计意图（证明钉的是"哪个文件"，不是"多一个文件"）。
- 把三条附属测试**全**点红 ⇒ 多半是 M5/M6 让文件**消失**了（源路径不存在⇒skipped），
  那是"红错原因"。看 `FAILED` 用例名与断言消息确认；若是这种，回到下面的摆位表修测试。

🚨 **测试摆位必须与真仓库同构，否则 M6 必然"红错原因"**（起票会话审自己票时抓到）：

```
tmp_path/app.db                    <- 主库（patch DB_PATH），marker = "main"
tmp_path/data/quota_used.sqlite    marker = "quota"     } 只 patch DATA_DIR = tmp_path/data
tmp_path/data/app.db               marker = "dataapp"   } 让 EXTRA_SQLITE 的 value 自动落位
```

只有把**主库放在 `tmp_path/app.db`**（正是 M6 的 `"../app.db"` 从 `DATA_DIR` 往上一级的落点），
M6 才会产出一个**能打开、内容却是主库**的 `out/data_app.db` ⇒ 逼你按内容判红（对的原因）。
若主库起名 `tmp_path/main.db`，M6 会因"源不存在"被跳过 ⇒ **这道变异什么都没证明**，而你可能以为拦住了。
断言方向：包内三个库各自读出那行 `v`，分别等于 `"main"` / `"quota"` / `"dataapp"`；**不许**只断言"文件在"。

跑者：复制到 `dispatch-output/s7-backup-hardening-20260919/run_mutations.py`，
改写 → 跑测试 → **按字节还原** → 校验 sha256 回基线；每道留 `mut-<tag>.log`。
🚨 **跑者的测试目标必须一次带上两个文件**：
`-m pytest tests/test_backup_data.py tests/test_chroma_dir_guard.py -q`。
原因很具体：S4 那份跑者写死了 `TEST = "tests/test_backup_data.py"`，而 **M7 命中的是另一个文件里的接线断言**
⇒ 不改这里，M7 必然被误报成"逃过 🚨"（pytest 根本没跑到那条），你会白花一轮时间去"修"一个没坏的测试。
⚠️ 目标文件是**三个**（生产码 + 两份测试），基线 sha 要**分别记**；
**跑前记、跑后必须逐一相等**，不等就是没还原干净，立刻报告、别继续。
替换串必须**在各自文件里唯一命中**（跑者已有"命中次数≠1 就判失败"的守卫，别绕过它）。

### 6.6 门禁顺序（不许省任何一步）

```
# ---- 以下 4 步在 backend/ 内跑 ----
cd backend
./venv/Scripts/python.exe -m pytest tests/test_backup_data.py tests/test_chroma_dir_guard.py -q \
    --basetemp=<系统 temp 里的目录>                                        # basetemp 严禁落在 backend/ 内
./venv/Scripts/ruff.exe check . && ./venv/Scripts/ruff.exe format --check .
./venv/Scripts/python.exe -m mypy .          # 注意 scripts/ 在 exclude 内，这里绿不代表备份脚本有类型门禁
./venv/Scripts/python.exe ../dispatch-output/te-chroma-isolation-20260918/run_gate_full.py <你的标签>

# ---- 以下 3 步必须回到仓库根跑 ----
cd ..                                        # 实测 .pre-commit-config.yaml 在仓库根，backend/ 下没有
backend/venv/Scripts/pre-commit.exe run --files backend/scripts/backup_data.py \
    backend/tests/test_backup_data.py backend/tests/test_chroma_dir_guard.py
git add backend/scripts/backup_data.py backend/tests/test_backup_data.py \
    backend/tests/test_chroma_dir_guard.py && git diff --cached --name-only
git commit -F <把提交信息写成文件>
```

⚠️ 钩子未接进 git，`pre-commit` 那一步必须手跑；可执行文件名是 **`pre-commit.exe`**（不是 `pre_commit.exe`）。
`git add` 的路径是**相对当前 cwd** 的 —— 上面按"在仓库根"写，你在别的目录就要相应改，
且**永远显式列文件名**（禁 `git add -A` / `git add .`）。提交信息里不要出现英文双引号、反引号、`$`。

⚠️ `pre-commit` **首跑常因 `end-of-file-fixer` / `ruff format` 改写文件而 Failed**——那是钩子在正常修复。
处置：复跑一次要拿到 rc=0，并 `git status` 比对**它顺手改了哪些文件**；改到不属于本票的文件就还原，别提交。

⚠️ 全量门禁那一步：`--basetemp` 由 `run_gate_full.py` 自己管（起票会话实测落在系统 temp 的
`fazhi_gate_<标签>`），**不要**自己另设到 `backend/` 内（§8 那条自反馈红坑）。

`run_gate_full.py` 会：跑前后对 `backend/` 全部 `.py` 取 sha256、前后各做一次真实 chroma 清单，
产出 `gate-<标签>.log` / `-source-sha.json` / `-verdict.txt` 三件。
判据分两类：**回归判据**（pytest 退出码与计数）**仅在 verdict=RUN_VALID 时有效**；
**隔离判据**（真实 `backend/chroma_db` 指纹前后一致）在 `RUN_VOID` 时**依然有效**。
`RUN_VOID` ⇒ 有人（可能就是你自己在还原变异时）改了源码，那轮 passed/failed 作废、重跑。

## 7. 随两笔落地的文档订正（只往这两个地方写）

1. 计划 `docs/superpowers/plans/2026-09-19-single-session-consolidation.md`：
   - 收口状态表里 **S4 的 ✅ 先降为"票面 DoD 未达成（Step 3b）"**，S7-b 落地后升回并写明依据是哪道变异；
   - `执行记录` 里"29 个命中"订正为"**29 个文件命中 / 共 71 次命中**"；
   - 追加 S7-a / S7-b 结果块（红→绿→7 道变异各自的 FAILED 用例名→门禁读数→三件产物路径）。
2. 当日日志 `.workbuddy/memory/2026-09-19.md`：**只用 append 原语**（见 §8）。补一条"评审抓出的 BLOCKER 中
   有一条正是我自己票面写的未做项"。
3. `.gitignore`（规则行实测 `:107 /_*`、`:112 dispatch-output/**/*auth-state*.json`）：
   - 把注释 `:101` 里"实测根目录有 97 个这样的条目"换成复测命令
     `git status --porcelain --ignored | grep -c '^!! _'`（起票会话 12:5x 实测给 **108**）。
     ⚠️ **别把 108 当成"97 变了"** —— 两个数不是同一个量："97"是规则生效**前**用
     `git status --porcelain`（默认 `-u`，未跟踪目录折叠）数的未跟踪条目；规则生效后同一批文件
     改从 `!!` 出现，且 `--ignored` 的折叠语义不同。注释里要写的是**命令**，并补一句"原命令现在返回 0"。
   - 同一条注释里的"写成 `_*` 会命中 **9 个**已跟踪文件"（`:103-104`）起票会话复算**仍然精确成立**
     （`git ls-files | awk -F/ '{print $NF}' | grep -c '^_'` = 9，含 `__init__.py` 与三个探针）。
     ⇒ 一个会过期、一个不过期，差别只在**有没有把命令写进注释**。这就是上面要换命令的理由。
   - auth-state 那条注明"执行者自加 → Owner 已追认 2026-09-19"。
   - 🚨 **只准加规则，不准删/放宽任何既有规则**：`*.log`、`*.bak`、`*.env`、`.env`、`*.db`、
     `dispatch-output/config-backups-*/` 一律不许动（Owner 长期禁令）。改完必须跑
     `git ls-files -i -c --exclude-standard | wc -l`，期望仍是 **72**（起票会话两轮实测值）——
     这个数字变了就是你把某个已跟踪文件卷进了忽略集，属回归。

## 8. 收口纪律（本仓硬事实，不是风格偏好）

- `.git/hooks/pre-commit` **未安装** ⇒ 提交前必须手跑，可执行文件名 `pre-commit.exe`。
- 只 `git add` **显式路径**；提交前 `git diff --cached --name-only` 核对；禁 `git stash` / `reset --hard` / `clean` / `gc`。
- **永不 amend 已发布的提交**；出错就补一笔新提交。
- 交付/说明类文档按 `docs/` **未跟踪**惯例留在工作树；`dispatch-output/<票名-日期>/` 里被票要求的产物才提交。
- ⚠️ **向共享追加式文件写内容只允许 `open(path,'ab')` 或 `>>`**。`>`、`Path.write_text()`、整段 Edit
  在这种文件上一律禁止 —— 起票会话 12:3x 把 `>>` 写成 `>`，**整文件覆盖了当日日志 232 行 / 21,691 B**，
  里面含另一会话的 4 个块。恢复过程与配方在计划 A-7，误覆盖是可救的（转录里有每次 Bash 原文），
  但**别赌**。写完立刻复测字节数与行数。
- 声称"通过/达标"之前五问自答：数字怎么来、能否复现、测试**亲眼红过吗**、期望值**独立吗**、已知限制是什么。
  "删掉实现就变红"只证明实现缺席时会红 ⇒ 必须做**定向变异**；pytest 只报第一条失败断言 ⇒
  后面没单独变红过的断言要如实降级为"未验证"。

## 9. 命令写法层面的九个坑（每个都导致过假结论）

1. 前台是 Git Bash；`cd .. && grep …` 若 cwd 已在仓库根会**扫到桌面**。
2. 计数**不得**在 `| head`/`| tail` 之后做；**退出码不得经管道取**。
3. `ls -l | cut -c30-` 会把尺寸列切掉（曾让 19.9MB 看起来像 39KB）。
4. 比 HEAD 用 `git status`，**别**拿 `git show HEAD:path | sha256sum` 比工作树 —— 本机 `core.autocrlf=true`，
   工作树 CRLF、blob LF，会 62 个文件"全错"。git 对象号是 **sha1**，永远不要拿去和 sha256 比。
5. `git check-ignore -v -q` 对**已知被忽略**的文件也返回 1 ⇒ 去掉 `-q`、用字面量路径逐条测；
   把 `$(python -c …)` 灌进 `for` 会带进 `\r`，路径全部失真。
6. Windows 上 `Path.write_text()` 会把 `\n` 静默转成 `\r\n`（实测一次凭空多 231 B）⇒ **按字节写**。
7. **拿"改参数"的方式做标定之前，先确认仪器的输出落点**。本票 §5.3 的 `--out` 就是这么来的：
   扫描器把 JSON 写在**脚本自己旁边**，一次 `--repo <temp>` 标定就会覆盖唯一的证据基线。
8. **测试里调"生产守卫函数"之前，先去读 `backend/tests/conftest.py` 无条件设了哪些 env**。
   它把 `QUOTA_DB`/`DATABASE_URL`/`CHROMA_DIR` 全指向临时目录 ⇒ 任何"env 分歧即拒绝"的守卫
   在测试里都会**恒抛**，你的"不该抛"用例永远红、"该抛"用例为错误原因永远绿（§6.2 详述）。
9. **含反引号或 `$` 的中文正文，绝不要塞进 `bash -c "…"` / `python -c "…"` 的双引号参数里**：
   bash 会把每对反引号当**命令替换先执行一遍**。起票会话 13:3x 就这么把一段留痕文本喂进去，
   结果是一串 `xxx: command not found` + 一个 `sed` usage 输出 + python `SyntaxError`；
   当天日志因异常发生在 `open(...,'ab')` **之前**才没被写坏（实测前后均 298 行 / 28,884 B）。
   ⇒ 规矩：**这类正文一律先用编辑工具写成文件，再由程序读取后二进制追加**。

## 10. 回给 Owner 的格式（照抄填数，别自由发挥）

```
P1–P8：<逐条 读数 / 是否符合期望>
HEAD=<hash>
S7-a：种子仓三面 rc=A=<码> B=<码> C=<码>（期望 3 / 0 / 4）   全仓重扫 rc=<码>（期望 0）
      summary 新字段读数：files_scanned=<n>（旧口径 71159，注明不可比）skipped=<…>skipped_dirs=<…>
      去重前 by_pattern.n 合计=<A>  去重后=<B>
      证据安全：dispatch-output/secrets-hygiene-20260919/scan-result.json 的 sha256 与开工前是否相同=<是/否>
      （它未入库，覆盖了就救不回 ⇒ 本票要求所有标定一律带 --out <temp>）
S7-b：红=<亲眼看到的失败用例名>   绿=<passed 计数>   变异 M1..M7 各自的 FAILED 用例名=<逐条列>
      run_gate_full 标签=<标签> verdict=RUN_VALID|RUN_VOID  pytest 末行=<计数>
      三件产物=dispatch-output/te-chroma-isolation-20260918/gate-<标签>.{log,json,txt}
      真跑一次备份：包内清单=<backup_manifest.json 条目数>，chroma 是否只记计数=<是/否>
本次改动=<文件清单>   未推送未部署=是   已跟踪文件脏项=<0 或清单>
若要动 §11 任一项：<编号 + 你要什么授权>
```

携带路径（若 Owner 让你刷新救援仓）：`Desktop/fazhi-rescue-88bd167-20260919/repo.git` 内
`git bundle create <out> master` 实测 **691 ms**、产物 135,496,420 B 且**逐字节可复现**
（sha256 `8b59d2e5cbad…ddf42702`）。⚠️ 该仓 tip 哈希是 **`2fdba83`**，不是 `88bd167`
（graft 自 `0263bd56` 重写祖先 ⇒ 其上每笔换哈希；tree `c4949fe…` 与 30 提交数两侧全等）。
比对式必须用 `%T|%an|%ae|%ad|%s`，**不要带 `%H`**（带了立刻假红）。

## 11. 不许你动的（等 Owner 表态）

| 项 | 状态 | 动手前必须先得到 |
|---|---|---|
| G2-续：`app.db` 写者归因 | 抓 00:11–00:41 那 +53 条写事务需要**并发评测批**做搭子；起票会话 12:5x 时 Owner 只放行一个会话 ⇒ 无窗口，但 15:2x 实测已有另一会话在改码（见 §1.1）⇒ 问 Owner 当前是否有评测批。（本仓各会话的任务列表**互不可见**，别引用别人会话的 `#编号`） | Owner 安排并发批；探针 `dispatch-output/probe-openers-20260919/probe_openers.py`（只读，绝不 `sqlite3.connect` 真实库） |
| S5 快车道版本判定 | seam 已测绘（三个出口，见计划 S5 块），**未接线**；DoD 要 `AGENT_ENABLED` 两态 + 真实模型对照臂 | 付费额度授权 |
| `tmp_pack_*` 去留 | `.git/objects/pack` 两个原件在案（起票会话 sha256 复验仍在）；桌面另有 63.6MB 副本 `Desktop/fazhi-tmppack-probe-20260919/` | Owner 决定删谁、留谁 |
| 27 字节弱 JWT 开发密钥 | 扫描器两个 27 位形状由 pytest 日志里 PyJWT 自己报 `InsecureKeyLengthWarning: HMAC key is 27 bytes long` **独立对上** ⇒ 是本仓自带弱密钥，非泄漏。换长会动测试期望值 | Owner 裁决要不要换、谁动 |
| 推送 | origin 曾是**公开可读**（起票会话记录，未复测）；且 §0.3 使活仓推不动 | Owner 确认目标仓 private + 走救援仓 |
| `restore_drill.py` 读 manifest | 本票**不做**（§6.3 只产出清单）。把它接上 drill 是另一票 | Owner 另开授权 |
| 别的助手产出的审查报告 `docs/code-review-report-02e3851-20260918.md` | Owner 15:3x 令：**本票不读它、不采纳其结论、不替它收尾**。（它与 §1.1 那 19 个在途改动是否同一条线，起票会话**未证**——报告名指向 `02e3851`，别自行连线） | Owner 明确改口才动 |

## 12. 文件索引

| 要看什么 | 路径 |
|---|---|
| 本票整改对象的执行记录与审计轮 | `docs/superpowers/plans/2026-09-19-single-session-consolidation.md`（§「审计轮」A-1…A-7） |
| 当日逐时日志（含误覆盖事故与恢复配方） | `.workbuddy/memory/2026-09-19.md` |
| 备份脚本 / 其测试 / 变异跑者 | `backend/scripts/backup_data.py`、`backend/tests/test_backup_data.py`、`dispatch-output/s4-backup-coverage-20260919/` |
| 守卫判例（照抄形状与调用位置） | `backend/scripts/chroma_dir_guard.py` |
| 守卫的**既有测试**（§6.2 的接线断言加在这里；含 `WIRED` 名单与 `__main__` 正则） | `backend/tests/test_chroma_dir_guard.py` |
| 扫描器与它的形状结果 | `dispatch-output/secrets-hygiene-20260919/scan_trace_shape.py`、`scan-result.json`（**后者刻意不入库**） |
| 全量门禁跑者 | `dispatch-output/te-chroma-isolation-20260918/run_gate_full.py` |
| 上游两票（判据与待办分级） | `docs/handoff-takeover-20260919.md`、`docs/handoff-r15-and-git-repair-20260919.md` |

## 13. 收口验收清单（逐项打勾；缺一项就不许说"完成"）

每一条都能指回本票某一节的命令——**指不回的那条就是你在自造判据**。

### S7-a（扫描器）

- [ ] 种子仓**三面**各自的 rc 亲眼看到：**A=3 / B=0 / C=4**，且 A 的 stdout 含 `[STOP]`、C 含 `[INSTRUMENT]`（§5 判据）
- [ ] B 面里那颗伪造串从 `tracked_with_hits` 移到了 `untracked_with_hits`（不是"没命中"，是"命中但未跟踪"）
- [ ] summary 字段名与 §5.4 逐字一致，且**没有** `scanned` 与 `files_scanned` 并存
- [ ] 去重前后 `by_pattern.n` 合计**两个数都报**（去重前现状 71）
- [ ] 全仓重扫 rc=0；若给你 3 或 4 ⇒ **停手报告**，不许改判据让它变绿
- [ ] `scan-result.json` 的 sha256 与 §5.0 记下的值相同（证明标定没覆盖证据）
- [ ] `pre-commit --files <那一个文件>` 复跑 rc=0，且 `git status` 确认它没顺手改别的
- [ ] 提交**只含** `scan_trace_shape.py`；`git show --stat HEAD` 复核文件清单

### S7-b（备份面）

- [ ] "源写错/源互换"两条测试**先亲眼红**，红因（哪条断言、消息原文）写进留痕（§6.1/§6.5）
- [ ] 7 道变异每道有 `mut-*.log`，且**各自的 FAILED 用例名逐条列出**；M5/M6 的判读符合 §6.5 三条规则
- [ ] 变异跑者的 pytest 目标**带上两个测试文件**（否则 M7 假报"逃过"）
- [ ] 三个目标文件 sha256 跑前 = 跑后（还原干净）；`grep -c raising=False tests/test_backup_data.py` = **0**
- [ ] 接线断言（§6.2 第 1 条）落地，且 `test_chroma_dir_guard.py` 原有 4 条**仍然全绿**（你没碰坏 `WIRED`/`__main__` 正则）
- [ ] 真跑一次备份 rc=0，包内有 `backup_manifest.json`；entries ≥ `app.db` + 两个附属 + `media`
- [ ] manifest 里 `chroma_db` 只有 `files`/`bytes`（**没被哈希**），且没有 `.verify.tmp` 之类的残留混进 entries
- [ ] `pytest tests/test_backup_data.py tests/test_chroma_dir_guard.py` 定向 0 failed；`ruff` 两项 rc=0
- [ ] `run_gate_full` verdict=**RUN_VALID** 且 0 failed；**隔离判据单独报**（chroma 指纹、`app.db` cc、`quota` cc 前后各值）
      ⇒ 若 §1.1 那个在途会话还在改码，VOID 是**别人的时序**，如实报，不许重跑到绿为止再报
- [ ] 提交**且仅提交** §6 顶部 Files 那三个文件

### 两笔共同

- [ ] 未推送、未部署；HEAD 前进了几笔都写进回报
- [ ] `.gitignore` 未放宽：`git ls-files -i -c --exclude-standard | wc -l` 仍是 **72**
- [ ] §7 三处文档订正已落（计划、当日日志用 append 原语并复测字节/行数、`.gitignore` 注释）
- [ ] 按 §10 格式回报，**每个数字都能指到一条命令**；凡"未验证/未复测"的字样照实写

---

**卡住就回问 Owner**，不要自行扩范围。提问时带上：你的 P1–P8 读数 + 你想动的那一项
（用 §11 的**行名**或 §4 的**决策号 Q1–Q7** 指代；别引用别的会话的任务列表编号，那些在你的会话里看不见）。
