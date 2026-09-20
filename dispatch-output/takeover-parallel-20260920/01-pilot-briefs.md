# W1a 试点派发包（4 张：T1 / T3 / T6 / T9）· 2026-09-20 22:3x

> **卡的正文在** `dispatch-output\hij-h-20260920\ALL-PARALLEL-TASKS.md` §1/§2/§3（**以那份为准**）。
> **本文只写卡之外的东西**：统一禁令、终止条件、回报形状、环境坑。两者冲突时，**禁令与终止条件以本文为准**。
> 开工前先读 `dispatch-output\takeover-parallel-20260920\baseline.json`（当前基线，HEAD = `beb4d5c`）。

---

## §0 全批统一（四条卡外加的硬约束）

**A. 禁写 git**：不得执行 `git add` / `commit` / `stash` / `checkout` / `restore` / `push` / `reset`。
只把产物落进自己的交付目录；**入库由主会话统一做**。
（本仓真实事故：并行会话把别人未提交的修改收编/抹掉；并发写 index 还会互锁。）

**B. 只写自己的交付目录**：越界写 = 立刻停手 + 在回报里声明写了哪些路径。
唯一例外：T12（不在本批）可跑既有构建命令。

**C. 绝不触碰**：
- `backend\` 下任何文件（本批全是只读诊断；**唯一允许的读**也要以只读方式做）；
- 票 I 的在途物：`backend\main.py`、`backend\retrieval.py`、`backend\tests\test_exact_article_lookup_sourcekey.py`、`backend\.ptmp-s4-run2\`；
- 另一会话在途物：`docs\code-review-report-02e3851-20260918.md`；
- 真实语料 `qa_pairs` 的**任何写入**（T7 卡同理，只算不写）；
- `backend\scripts\gate2_runner.py`（冻结件）、`backend\gate_exit_registry.py` 与 `docs\gate-exit-registry.md`（登记表真源，本波无人回表）。

**D. 终止条件（每条都要能一句话说出，且可判定）**

| 卡 | 终止条件 | 边界（无产出/超时怎么办） |
|---|---|---|
| T1 | **固定跑 N=1..5 共 5 轮**（不因红绿增减、不因"想再确认"加轮）；仅当某轮因**环境原因**（非测试失败）中断时补 1 轮，**总数 ≤ 6** | 若 90 分钟内 5 轮未跑完 ⇒ **停手**，交出已完成轮次的矩阵 + 未完成原因；**不许**为凑满 5 次而无界重跑 |
| T3 | 一次读数 + 一次**独立复核**读数，两者对齐即止 | 若容器那份读不到 ⇒ 报"读不到 + 需要什么才能读到"，**不许**对没读到的文件下结论 |
| T6 | 待判调用点**逐点**给出结论（上限 5 个文件、各 2 次读尝试） | 某点读不出 ⇒ 标 `UNVERIFIED`，**不许**用推测填空 |
| T9 | 逐条 checklist 项给出「文件 + 符号 + 今天是否已防住(+证据)」 | 无法证实 ⇒ 写"未能证实"，**不许**写"应该已经防住了" |

**通用止损**：同一条命令连续失败 2 次 ⇒ **不许**第 3 次重试，改为回报现状与错误原文。
单条命令前台超过 15 分钟无输出 ⇒ 视为被环境截断，回报现状（不要静默重试）。

---

## §1 环境坑（本机实测，逐条都会咬人）

1. **PATH 先补**，否则 `grep`/`wc`/`ls` 都不存在：
   `export PATH=/c/Users/33393/.workbuddy/binaries/PortableGit/versions/1.2.0/usr/bin:$PATH`
2. **解释器唯一可用**：`C:\Users\33393\Desktop\ai-legal-helper\backend\venv\Scripts\python.exe`
3. **pytest / lint 输出一律重定向到文件**：经管道（`| head` / `| grep`）会 SIGPIPE 杀掉 pytest，
   计数不要在 `| head` 之后做，退出码不要经管道取。
4. **Python 内联 `-c` 里出现反引号 / `$` 会被 shell 展开**（本仓被咬过：中文字符串里的 Markdown 反引号
   被当成命令执行）⇒ 任何含反引号 / `$` / Markdown 的 Python **写成 .py 文件再跑**。
5. **中文输出要 `-u`**（不加会缓冲区丢失，表现为 exit 1 且零输出）；更稳的是脚本自建日志文件并 flush。
6. **装 `\\` 路径**：Git Bash 下用正斜杠或加引号的绝对路径。
7. **判定"文件编码"不要靠肉眼读终端**（终端会把 UTF-8 中文显示成乱码）⇒ 用 Python 多编码 decode 探测。
8. `--basetemp` **每次必须不同**（共用会撞沙箱 safe-delete 批量守卫，产出"整轮瞬间全灭"的假读数）。

---

## §2 回报形状（**固定 5 段，缺段即打回**）

```
① 结论：一句话（要回答的那个问题，答案是什么）
② 产物：每份产物的绝对路径 + 关键读数（数字 / 计数 / 哈希）
③ 判据对照：把卡里的判据逐条抄出来，标 满足 / 不满足（不满足要写原因）
④ 我复跑的命令：确切命令行（我会照着跑，不许写"参见上面"）
⑤ 诚实登记：没做到的 / 读不到的 / 未证实的；以及**越界写声明**（若发生，列出写了哪些路径）
```

**基线锚定（T3/T6/T9 必做，T1 可选）**：报告首部写 `git rev-parse HEAD` +
`sha256(backend/retrieval.py)` + `sha256(backend/main.py)`。理由：票 I 正在写 `main.py`，
不锚定哈希的结论会对着旧版本、事后无人能发现。

---

## §3 四张卡的派发细节

### T1 · trace_id `t1-flaky-20260920`（P0，重，须轻载独占）

- **交付目录**：`dispatch-output\t1-flaky-20260920\`（必需：`matrix.json`、`report.md`、`run-1..5.stdout.txt`）
- **副本树**：用卡里的搭树命令，commit 用 **`1e969f2`**（实测可取；与已有 0/3/8 红三次读数同一棵树，
  可直接对账）。**不许** `--overlay` 票 I 的任何文件。
- **假 .env（只往副本里写）**：`JWT_SECRET=fake-for-copytree-only` / `LLM_API_KEY=fake-for-copytree-only` /
  `LLM_BASE_URL=http://127.0.0.1:9/v1`（端口 9 是 discard，顺手真调模型会当场失败而非静默烧额度）。
  **不要读写 live 的 `backend\.env`。**
- **第 N 轮命令（N=1..5，`<N>` 逐轮递增，`bt<N>` 逐轮唯一）**：
  ```
  cd <交付目录>\copytree\backend
  C:\Users\33393\Desktop\ai-legal-helper\backend\venv\Scripts\python.exe -m pytest tests/ -q -p no:cacheprovider --basetemp=<交付目录>\bt<N> --junitxml=<交付目录>\run-<N>.xml -m "not slow" > <交付目录>\run-<N>.stdout.txt 2>&1
  ```
  `-m "not slow"` **必须带**（18 条 slow 要填充过的 KB，会混进恒定红）。
- **解析**：用 `dispatch-output\s5-followup-20260920\run_mutations_full.py` 的 `failed_set()` / `suite_stats()`，
  **别另写一份**（注意：该脚本有 `if __name__` 守卫，import 安全——但**只 import 函数，别碰它的 main**）。
- **判据要点**：≥5 轮红/绿矩阵；每条 flaky 给**最小复现 + 根因**；归类到「顺序依赖/共享状态/时间敏感/外部依赖」
  且逐条给证据；**≥5 次里 0 次复现的不算 flaky**。
- **追加纪律**：若要把"负载敏感"列为候选根因，**必须自己起一条受控负载腿**（同形状控制腿），
  不许写"当时别的活也在跑，所以可能是负载"。判成败看 junit/矩阵产物，**不看退出码**。

### T3 · trace_id `t3-appdb-20260920`（P2，绝对只读）

- **交付目录**：`dispatch-output\t3-appdb-20260920\`（`report.md`、`readings.json`）
- **要回答**：两份 `app.db` 各是谁；宿主那份**今天还在不在被写**。
- **禁**：开事务 / VACUUM / 改 schema / 任何写。**容器那份必须真读到**才许下结论。
- **已有取证**（别重做，只对账）：`dispatch-output\appdb-lastwrite-forensics-20260919\report.md`（第 179 行）
- **要给的**：一张「文件→路径→cc/size/mtime→谁在写→是不是生产真源」表 + 一条**可复跑**命令。
- **我不接受**：两份混在一句话里报；对容器那份没读到却下结论。

### T6 · trace_id `t6-sourcekey-survey-20260920`（P1，只读普查）

- **交付目录**：`dispatch-output\t6-sourcekey-survey-20260920\`（`survey.md`、`call-sites.json`）
- **射程（因票 I 已在 `beb4d5c` 合入 I-6 而收紧）**：`exact_article_lookup` **本体归票 I，不属本卡**；
  本卡只普查其余调用点：`backend\knowledge_service.py`、`backend\scripts\gen_gate1_law_check.py`、
  `backend\scripts\import_laws.py`（2 处）、`backend\scripts\import_docs.py`（2 处）。
- **参照实现**：`backend\retrieval.py` 的 `_source_key`；测试锚点 `backend\tests\test_citation.py`。
- **禁**：改码；另写一份"去括注"正则（那就是第二份规则）。
- **我不接受**：只说"建议统一"而不逐点给理由。

### T9 · trace_id `t9-eval-credibility-20260920`（P2，只读）

- **交付目录**：`dispatch-output\t9-eval-credibility-20260920\`（`checklist.md`、`findings.json`）
- **要回答**：跑评测时必须**绕开什么**，才能不重演 `qa_cache` 污染 judge 基线（0.43/0.57/0.64 三个数全失真）。
- **出处**：`backend\main.py`（`record("qa_cache", …)` 与 `body.no_cache`）、
  `backend\tests\test_light_exit_gates.py`、`dispatch-output\i1-e2-hitrate-20260920\`、
  `docs\project-quality-guide-20260914.md`
- **要给的**：逐条「绕开什么 + 代码出处（文件 + 符号）+ 今天是否已被防住（是/否 + 证据）」，
  能直接贴进评测批 checklist。
- **我不接受**：只说"要注意缓存"而不给"哪一行、哪个开关、哪条命令"。
