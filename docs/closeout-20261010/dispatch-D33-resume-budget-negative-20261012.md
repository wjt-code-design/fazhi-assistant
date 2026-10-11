# 票 D-33：恢复 API 的越界与预算下降负例（只加测试，不动产品语义）

> **10-12 已由 Owner 会话自己执行，不必再派**：四条里缺的三条落在 `backend/tests/test_agent_resume.py`（提交 `c4cc6b3`），第 1 条由既有 `test_resume_at_exact_step_cap_succeeds_...` 钉住未重复。负控读数 `evidence/d33-mutation-20261012.log` VERDICT=NEGATIVE_CONTROL_HOLDS。下面的票面保留作验收口径与复现入口。
**背景与已裁结论**：Owner 10-12 按推荐裁定「保留越界防御」。当前在册事实是 `WAITING_USER→PLANNING` 这条边免计步
（`FREE_STEP_EDGES`），但 `transition()` 仍然执行 `_limit(next_steps, max_steps)`，schema 也不禁止 steps 超过 budgets。
Owner 会话复核件 R5 的纯状态机复现给出两个读数：steps 等于上限时可恢复（`AT_CAP_RESUME_ALLOWED`），超过上限时仍抛
`BudgetExceeded`，两个恢复 catch 把它转成 409 的 `step_budget` 档。本票的任务是**把这两个读数钉成测试**，
并补一条「预算下降后恢复旧 run」的负例。不实现新语义。

**现场定位（指针一律现读，别引用行号）**
```bash
C=C:/Users/33393/Desktop/ai-legal-helper/.worktrees/nondeploy-closeout-20261010
grep -n '_limit(' "$C/backend/agent/state_machine.py"
grep -n 'FREE_STEP_EDGES' "$C/backend/agent/state_machine.py"
grep -n 'step_budget' "$C/backend/agent/controller.py"
grep -n 'CLARIFY_BUDGET_EXHAUSTED' "$C/backend/agent/"*.py
```
候选头现读 `git -C "$C" rev-parse HEAD`；开工前先 `git -C "$C" status --porcelain` 记下起点并保留原样。

**要交付的用例（四条，期望值各自独立来源，不许由被测值现算）**
1. `steps == max_steps` 时恢复成功：断言真的走到恢复后的下一步，而不是只断言没抛。
2. `steps > max_steps` 时恢复被拒：断言异常类型与最终 409 的 `step_budget` 成因码，两条分开写。
3. 预算下降（同一 run 用更小的 `max_steps` 恢复）仍被拒：断言它走的是同一条拒绝路径，而不是"看起来绿"的空断言。
4. `max_clarifications` 耗尽**仍**走 `CLARIFY_BUDGET_EXHAUSTED`、**不落 409**：这条是反向护栏，
   防止有人为了让 `step_budget` 档"更可达"把两个不同计数器合并。

**负控（尺子必须能红）**：临时把 `transition()` 里的 `_limit(next_steps, max_steps)` 摘掉 ⇒ 用例 2 与 3 必须红，
且要点名是哪两条红（只断言"有失败"会被别的用例蒙过去）。变异只在内存源码上做、磁盘产品不许改，跑完还原并复量 sha 未变。

**边界与禁令**
- 只加测试文件（或既有用例的新增腿），**不改产品代码、不改 schema、不改 SSE 契约、不动文案常量**。
- 统一解释器：`C:/Users/33393/Desktop/fazhi-nondeploy-closeout-20261010-b4e7a2/candidate-envB/Scripts/python.exe`（Python 3.11.0），cwd 为候选 `backend`。
- 不许跑 `backend/scripts/smoke_citation_fast.py` 或 `smoke_citation_full.py`（二者 `os.chdir` 加 `load_dotenv(".env")`，会装真实配置与真实配额库）。
- 不许碰主仓 `backend/app.db`、`backend/data/`、`backend/chroma_db/`、媒体与备份；不许读写 `.env`；不许起现役栈、不许占 3021/8088。
- 测试进程内把六根出网轴（五根 `*_BASE_URL` 加 `RERANK_NATIVE_URL`，见 `backend/settings.py`）指向死回环，`EMBEDDING_PROVIDER=local`、`HF_HUB_OFFLINE=1`。
- 注意本机坑：PATH 上 `~/.local/bin/env` 会吞掉 `env VAR=x cmd` 整条命令并返回 0；用 shell 内 `export` 起进程，并证明命令真的跑了。

**验收（交付时要给的读数）**
四条用例名 + 各自断言的是什么；变异前后两条腿的 collected/passed 数；还原后 `git status --porcelain` 与起点一致（除你新增的测试文件）；
一条复算命令。报告写在运行根新文件里，不覆盖既有日志。
