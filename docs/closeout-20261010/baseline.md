# A. 接手基线（2026-10-10 现量）

运行根：`C:/Users/33393/Desktop/fazhi-nondeploy-closeout-20261010-b4e7a2`
候选工作树：`C:/Users/33393/Desktop/ai-legal-helper/.worktrees/nondeploy-closeout-20261010`（分支 `codex/nondeploy-closeout-20261010`，起点 `0b543960c7172ce1ffea57616952e4d5525190c4`）
主仓：`C:/Users/33393/Desktop/ai-legal-helper`（本书期间只读，未切分支、未 stash/reset、未提交）

## A.1 现量（不是写书时读数）

| 量 | 读数 | 复算命令 |
|---|---|---|
| HEAD | `0b543960c7172ce1ffea57616952e4d5525190c4` | `git -C <main> rev-parse HEAD` |
| 分支 | `master` | `git -C <main> rev-parse --abbrev-ref HEAD` |
| tracked 已修改 | 21 | `git -C <main> diff --name-only \| wc -l` |
| 暂存区 | 0 | `git -C <main> diff --cached --name-only \| wc -l` |
| 未跟踪（不忽略） | 34168 | `git -C <main> ls-files --others --exclude-standard \| wc -l` |
| 未跟踪分组 | dispatch-output 33961 / other_untracked 146 / docs 34 / outputs 23 / 本轮新测试 4 | `evidence/ownership.json` |
| 计划书本体 | 未跟踪（`docs/superpowers/plans/2026-10-10-...md`） | `git ls-files docs/superpowers/plans/2026-10-10-non-deployment-release-closeout-execution-plan.md` 为空 |

21 只 tracked = 后端 15 + 前端 5 + 旧文档残差 1，与本书 §0.2 逐只一致；4 只新增后端测试逐只一致。

## A.2 接收

`evidence/receive_inputs.py` 按显式清单接收 24 只（后端 15 + 新测试 4 + 前端 5）。
逐只记 `sha256_worktree_before` / `sha256_candidate_after` / `sha256_head_blob` / CRLF 与裸 LF 计数。
结果：**24/24 字节相等**，其中 20 只与 HEAD blob 不同（即他人未提交的改动），4 只 HEAD 无版本（新增）。

旧文档残差 `docs/superpowers/plans/2026-09-29-local-candidate-decision-and-release-prep.md` **不接收、不提交**（本书 A.3 默认保护）。

## A.3 冻结清单重核（🔴 需 Owner 一词可答）

- `backend/pyproject.toml:17-21` ruff `exclude` 现仍含 `agent/state_machine.py`、`prompts.py`、`scripts/gate5_judge.py`；`:16` 注释原文「state_machine/prompts/gate5_judge 仍冻结保留」。
- 本轮接收集合里 `backend/agent/state_machine.py` **已被改动**（`db diff` 计数 +22/−1，见审计书 §13.1 归 DB-15 `FREE_STEP_EDGES`）。`prompts.py`、`scripts/gate5_judge.py` 未被改动。
- 解冻判据（同文件 :9-16 自述 09-16 / 09-18 两次先例）= Owner 明确授权 + 从 exclude 删除 + 最新 `candidate-hashes.json` 不含该文件。
  - 实测最新锚定清单 `dispatch-output/agent-quality-1e9-20260916/candidate-hashes.json` 只含 `writer.py`、`verifier.py`、`switches`、`prior` ⇒ **不含 state_machine.py**（该条满足）。
  - 但 exclude **未删** ⇒ pyproject 仍在册声明其冻结，且 ruff 对该文件**零覆盖**（`mypy` 仍覆盖它，其 exclude 只有 `tests/|scripts/|venv/`）。
  - 在审计书与 10-09 工作汇报里 grep `冻结|解冻|frozen|unfreeze`：`state_machine` 相关只出现在改动位置，**无一条 Owner「解冻」原话**；DB-15 票面文字只裁修法，未提冻结状态。
- 结论：改动**位置必要**（修法本体就在该文件），但**在册解冻依据缺失**，且配置文件与其字节状态互相矛盾。
  ⇒ 按本书 A.4：`state_machine.py` 的整合**停止并请求具体确认**；文件按接收原样保留在候选，不覆盖、不回退、不提交。
- 旁证：`writer.py`/`verifier.py` 相对 1e9 锚定的漂移早于本轮（锚定记的是 HEAD `604fa240`，已被 master 取代），因此 1e9 清单是**历史快照**，不是当前 live 冻结闸；live 冻结闸只有 pyproject exclude + `docs/code-review-standard.md` §2 B1。

## A.4 禁区登记（仅元数据，未打开、未哈希）

`evidence/forbidden-zones.json`：`backend/app.db` 20,205,568B(09-19)、`backend/agent_runs.db` 0B、`backend/data` 4 文件、`backend/chroma_db` 38 文件、`backend/media` 58 文件、`backend/backups` 243 文件、`.env` 3,351B(09-06)、`C:/Users/33393/.cache/huggingface` 20 文件/781M、`backend/venv` 38284 文件。
`.env` 只取**变量名 23 个**（含 `ADMIN_PASSWORD`、`DASHSCOPE_API_KEY`、`EMBEDDING_API_KEY`、`LLM_API_KEY`、`SILICONFLOW_API_KEY` 等），未取值。
候选工作树按构造不含上述任何一只（均被 `.gitignore` 排除，故不在 HEAD 树内）。
**这些元数据相同不证明实库内容一致。**

## A.5 解释器事实

| 用途 | 路径 | 版本 |
|---|---|---|
| `backend/venv` 基座（pyvenv.cfg `home`/`executable`） | `C:\Users\33393\AppData\Local\Programs\Python\Python311\python.exe` | 3.11.0（venv 由 `-m venv --clear` 建） |
| `py -0p` 注册 | 3.14（默认 `*`）/ 3.12 / 3.11 | — |
| Node / npm | — | v24.18.0 / 10.9.7 |
| 本会话执行 shell | Git Bash 5.3.15（**不是本书 PowerShell 片段所设的 pwsh**） | 命令已逐条译为 bash 等价，语义不变 |

仓库内当前**只有 `backend/venv` 一套 venv**（`*/venv`、`*/.venv`、`venv`、`.venv` 全盘查找仅此一只）；旧账里「两套 venv 版本不同」的另一只在 %TEMP% 副本树，已不存在。它是否就是产品实际运行环境属 G.1，不能由目录名推断。

## A.6 隔离约定

每个进程用运行根下的独立绝对绑定（`data/app.db`、`data/quota.sqlite`、`chroma-*`、`model-cache`、`logs`），在任何 `main`/`rag_chain` 导入**之前**完成绑定（`main.py` import 触发初始化）。真实库在候选树中按构造不存在，因此合成绑定不是「绕行」而是唯一可用路径。
