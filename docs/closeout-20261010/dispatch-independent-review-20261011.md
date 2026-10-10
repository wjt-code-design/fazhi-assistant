# 票 X：对 2026-10-10/11 收尾轮的**证伪式独立复核**（只读，非实现者执行）

> 派单对象：**独立会话**（不是本会话派出的 agent——本会话已连续三只 agent 零产物，见 `decisions-needed` D-27）。
> 你是谁：你不是来确认我做得对的。你的任务是**试图推翻**下面每一条；推不翻的才写"采纳"。
> 铁规：**不许转述我的报告**；每个判决必须带**你自己跑的那条命令 + 它的输出**。引用我的数字而不复算 = 该条判"核不了"。

## 0 被审对象（绝对路径，全部只读）

交付根 `C:/Users/33393/Desktop/fazhi-nondeploy-closeout-20261010-b4e7a2/`：
`reports/gates.md`（**节数不钉在这里**——它是自指计数，写票之后还会加。现量两条命令：`grep -c '^## ' reports/gates.md` 与 `grep -a '^## ' reports/gates.md | tail -3`；**本轮新增的节从 §19 起一直到最后一个 H2**：§21=门禁转现量、§22=D-3 票与两处更正、§23=Docker 引擎已停、§24=主仓 WIP 与候选的字节关系、§25/25-a=远端读数与 CI 步骤归因、§26=读数过期扫描）、`reports/decisions-needed-20261010.md`（§A 3 行 D-5/6/7、§B 待答、§C 已裁；**三档相加应等于最大编号**，不等就是分档漏了，复量：`awk '/^## B\./{f=1;next}/^## C\./{f=0}f' <文件> | grep -c '^| \\*\\*D-'`）、
`reports/acceptance-of-D-20261010.md`、`reports/h-ci-and-credentials.md`、`reports/review-of-other-sessions-20261010.md`、
`reports/code-review-A-standards.md`（**注意：那是我自审，不算独立腿**）、`reports/closeout-final-J-draft.md`。
候选树 `C:/Users/33393/Desktop/ai-legal-helper/.worktrees/nondeploy-closeout-20261010`（HEAD 应为 `9e3cfc5`，`git status --porcelain` 应为空）。

## 1 必须逐条攻击的七颗钉子（按"最贵"排）

1. **凭据轴**：① 候选历史里那只 **13 位**裸值（`dispatch-output/t12-frontend-sweep-20260920/apply_case_domain_gate.py:104`，`hits=61/files=1`）；② 无父快照 `5df5a1277f…` 对象集**按值 0 命中**且正对照能命中 1；③ 普通推 **4301** 对象 vs 快照 **2581**。复算器：`evidence/value_reverse.py`、`evidence/shape_scan_committed_set.py`、`evidence/orphan_pin.py`。
   **攻击点**：0 命中是不是"射程为空"造成的假 0？（在册规则：按值腿必须先在**引入它的那笔**上咬住才允许报 0。）
2. **J3 生产构建 purge**：四个 `badge-*` 类名在 `.next/static/css/*.css` 里 grep 计数 = 0，而浏览器计算样式六者相同。复算器 `evidence/check_badge_purge.py`。
   **攻击点**：这是**既有缺陷**还是 §14 引入的？（去 `git show HEAD~5:` 的树上再跑一次同一计数器。）
   ⚠️ 若要重建：`next build` 在有进程持有 `.next` 时会**无报错无进度地卡死**（Windows 实测）；先确认没有活进程。
3. **第五笔 `9e3cfc5` 的字节等同性**：我声称"重放到纯净 HEAD 后与盘上被验收的字节 5/5 一致"。复算：`git show 9e3cfc5` + `evidence/frontend-dirty-20261010.patch` / `.manifest`，自己重放一次（临时目录，别碰候选树）。
4. **门禁四条现量**：`1925 passed / 0 failed / 10 skipped / 18 deselected / cov 86.35% / rc=0`、ruff check/format rc=0（283 files）、mypy rc=0（**74 source files**）、前端 tsc/lint/vitest rc=0（**9 files / 83 tests**）。
   你自己现跑：解释器用 `C:/Users/33393/Desktop/fazhi-nondeploy-closeout-20261010-b4e7a2/candidate-envB/Scripts/python.exe`（Py 3.11.0）。
   **攻击点**：`collected` 与 junit 用例数是否一致（收集期报错会只剩一条伪用例）；两条 skip 是不是设计内采集口。
5. **依赖分母两根轴**：`node evidence/audit_axes.js evidence/audit-cand-runtime.json` ⇒ 条目 24 / distinct 主 ID 15 / 5 包；族内每包条目 `11/5/4/2`、每包 distinct `6/4/2/1`（和=并集=13）。
   **攻击点**：我在这条上**错过一次并公开撤回过一次**（我曾把 `6/4/2/1` 误判为"不可复现"）——请独立确认现在两根轴的每个数。
6. **`.dockerignore` 泄漏**：我声称镜像里带着 `data/app.db`（**19,939,328 B**、头 4 字节 `SQLite format 3`），并用 `.env` 做了**阴性对照**（`.env` 被 ignore 拦住 ⇒ COPY 失败）。
   探针配方就在盘上两只文件（各 73 / 79 B，都是 `FROM ai-legal-helper-backend:latest` + 一条 `COPY`）：`evidence/probe-df-env` 与 `evidence/probe-df-appdb`；`.dockerignore` 有 **17 条规则、其中没有 `data/` 那条**（根目录那份 494 B **不参与**，因为构建上下文是 `./backend`）。
   ⚠️ **今天复量有一条硬障碍**：Docker Desktop 引擎此刻**不在运行**（`docker ps` 连不上命名管道、进程数 0），所以**重新 `docker build` 这条路今天走不通**；等 Owner 起引擎或改用离线复算——读我当时留下的日志 `evidence/h-backend-image-build-v3.log` 与 `reports/h-ci-and-credentials.md` §9（镜像内容复量那段）。
   **攻击点**：① 构建上下文到底是不是 `./backend`（**一行就能验**：`docker-compose.yml:17` 现量 = `build: ./backend`；若你读到的是根目录，那我那 17 行根本不生效、结论作废）；② `*` 这类规则**不跨 `/`** ⇒ `backend/.dockerignore:6` 的 `*.db` 漏掉 `data/app.db` 是我的机理还是别的（该文件现量：**20 行 / 457 B / 17 条非注释规则，`grep data` 0 命中**）；③ 那只 19,939,328 B 是不是**真实库的副本**（若是合成/空库，"泄漏"的定性就要降级）。
   **攻击点**：构建上下文是不是 `./backend`（若是根目录，则 `backend/.dockerignore` 那 17 行根本不生效，我的结论就废了）。
7. **取消/切换两条腿"设计内不可达"**：真指针是 `frontend/lib/hooks/useConversations.ts` 的 **41（`newChat`）/ 57（`selectConv`）/ 88（`deleteConv`）三条** `if (opts.streaming) return;`——
   ⚠️ **D 那份报告写的"43/59 两条"是错的**（行号偏 2、且漏了删除会话那条；两棵树 blob 同为 `1124fc6a…`，所以不是漂移而是当初就读错）。请独立确认到底几条、各在哪只函数里。
   复算：读源码 + 跑 `pytest tests/test_cancel_boundaries.py tests/test_stream_cancellation.py --noconftest`（应 55 passed）。
   **攻击点**：D 报的"占位文案与服务端成对落库"是否真的**只落一条**（`main.py` 的 `_post_placeholder` 与 `assistant_committed` 闸）。

## 2 现场约束（越界即判无效）

只读候选树与主仓；**不 commit / 不 push / 不动任何 ref / 不部署 / 不重启 docker compose 栈 / 不占端口 3021、8088**。
禁止打开或哈希 `backend/.env*`、`backend/app.db`、`backend/data/`、`backend/chroma_db/`、`backend/media/`、`backend/backups/`、`C:/Users/33393/.cache/huggingface/`。
不打印任何凭据值（键名/长度/计数可以）。要跑写入型测试：另建副本树 + 把 `DATABASE_URL`/`QUOTA_DB`/`CHROMA_DIR`/`MEDIA_OUT` 全指到运行根下自己的目录，六个 `*_BASE_URL`（**含 `RERANK_NATIVE_URL`，那是第六根出网轴**）必须是 `127.0.0.1`。

## 3 交付（一份可转发文件）

`C:/Users/33393/Desktop/fazhi-nondeploy-closeout-20261010-b4e7a2/reports/independent-review-C-20261011.md`
结构：§0 三行汇总（采纳 N / 驳回 M / 核不了 K）→ §1 逐条（钉子编号 + 你跑的命令 + 原样输出 + 判决）→ §2 **你发现而我没登记的漏项**（这部分最有价值，没有就明写"无"）→ §3 你复算时发现我的更正本身又错的地方 → §4 已知限制。
每条判决**必须能被我一行命令复跑**；只写"看起来对/不对"不给命令的，我按未交付处理。

## 并发纪律（Owner 说这两张票**各开一个新会话并行跑** ⇒ 这一节是硬约束，不是建议）

**唯一的共享可变物 = `C:/Users/33393/Desktop/fazhi-nondeploy-closeout-20261010-b4e7a2/candidate-envB`（那套 venv）。**
独立复核票要用它复跑门禁基线（1925 passed），迁移票天生要装 1.x 包 ⇒ **两个动作碰同一个目录就会互相污染**。

1. **迁移票**：**禁止**向 `candidate-envB` 与主仓 `backend/venv` 安装/卸载任何包。
   新建自己的环境（建议 `运行根/candidate-envC-1x`），所有 1.x 安装只进那里；每次 `pip install` 前先打印 `python -V` 与 `sys.prefix` 证明前缀不是 envB/backend/venv。
2. **独立复核票**：**只读** `candidate-envB`。开跑前先做一次指纹核对，结束前再做一次：
   `python -m pip freeze --all | sort` 与 `evidence/envB-freeze.txt`（或 `evidence/envB-freeze-20261011-015x.txt`）比**行集合**（`diff <(sort A) <(sort B)`）。
   ⚠️ **别比原始 sha**：10-11 实测两份 freeze **164 行、3369 字节、排序后 0 差异，但 sha256 不同**（`fbf306dd…` vs `f6ee1ac0…`）——`pip freeze` 的顺序不稳定，比 sha 会造出假红。
   若行集合出现差异 ⇒ 立刻回报并**停止**门禁复跑（那条基线已经不属于本票）。
3. **两边都不许碰**：主仓工作树与候选工作树的任何写动作（含 `git stash|checkout|restore|clean`）、`backend/.env*`、真实 `app.db`/`data/`/`chroma_db/`/`media/`/`backups/`、docker compose 栈、端口 3021/8088。
4. **前端重建只允许一方**：`next build` 会整目录重写 `frontend/.next`。独立复核票若要复量 J3 purge **可以建**，但**必须先确认没有活进程持有 `.next`**（Windows 上有活进程时 `next build` 会**无报错无进度地卡死**）；迁移票**不许**碰前端构建。
5. **副本树各建各的**：两票的临时副本都落在**运行根下自己名字目录**（`运行根/mig-20261011/` 与 `运行根/review-20261011/`），不许互相读对方的中间产物来"印证"结论——同法复现不等于独立印证。

## 附：两棵树要分清（2026-10-11 现量，别默认候选树就是仓库根）
- **两棵树都有、一律禁读禁写**：`backend/.env`（候选那份只取 stat：**0 字节**、mtime 10-10 02:48，我没读内容）、`backend/data/`（候选 2 只：`eval_agent_complex.json` 与它的 `.rubric.md`）、`backend/chroma_db/`（候选只有 `chroma.sqlite3`，`du -sk` = **144**；主仓 = **357,096**）、`backend/media/`（候选 0 只文件）。
- **只有主仓有**：`backend/app.db`、`backend/data/app.db`、`backend/data/quota_used.sqlite`、`backend/backups/`、`backend/venv`。⇒ 「别在真实库上跑」这条在**两棵树上都成立**；候选那几只是空的/极小的，**不是安全区**。
- **主仓工作树** `C:/Users/33393/Desktop/ai-legal-helper`：HEAD `0b54396`，tracked 脏 **21**、未跟踪 **567**（02:29 现量，与 01:4x 同数）。**候选工作树** `.worktrees/nondeploy-closeout-20261010`：HEAD `9e3cfc5`、`porcelain=0`、5 笔提交。
- 副本树请建在运行根下自己名字的目录里；测试重定向用 `DATABASE_URL`/`QUOTA_DB`/`CHROMA_DIR`/`MEDIA_OUT` 四个出口 + 六根 `*_BASE_URL`（`settings.py` 现量：`llm_base_url` `zhipu_base_url` `dashscope_base_url` `embedding_base_url` `rerank_base_url` **`rerank_native_url`（:209）**），全部指 `127.0.0.1` ⇒ 不出网是构造性质。

## 构建类复算的额外要求（若你重建前端：构建不是禁区，但必须留两次 `git status` 读数）
- 现量（10-11 02:5x）：候选树 `frontend/.next` 与 `tsconfig.tsbuildinfo` **已存在**且被 `.gitignore:40`（`.next/`）与 `:42`（`*.tsbuildinfo`）忽略 ⇒ 构建产物不会脏树。
- 关键疑点是**被跟踪的** `frontend/next-env.d.ts`（Next 构建可能重写它）。经验证据：本轮已在同树构建过（`.next` 在场、next **14.1.0**），而 `git status --porcelain -- frontend/next-env.d.ts` **空** ⇒ 这个版本不改写它。
- 但我不许你拿我的经验当你的结论：**构建前、构建后各跑一次**并把两次原样输出写进你的报告：
  `git -C <候选> rev-parse --short HEAD` 与 `git -C <候选> status --porcelain`
  若构建后出现任何脏文件 ⇒ **不要 `git checkout --`／`restore`**（本仓在册纪律：脏树里这类命令会连别人未提交的字节一起抹掉），改为停下回报，由 Owner 裁。
