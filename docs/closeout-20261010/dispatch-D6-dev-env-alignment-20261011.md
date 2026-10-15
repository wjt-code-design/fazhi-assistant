# 票 D-6：开发环境 `backend/venv` 与候选 requirements 对齐（2026-10-11 派发）

> 台账出处：`reports/decisions-needed-20261010.md` §B 的 **D-6**（Owner 2026-10-11 裁「本轮不动它，另开票」）。
> **这张票动的不是产品字节**：改的是宿主机上的开发环境。它不阻塞合并，但合并后必须告知所有用这个 venv 的人。
> 路径：主仓 = `C:/Users/33393/Desktop/ai-legal-helper`；候选树 = `…/ai-legal-helper/.worktrees/nondeploy-closeout-20261010`；运行根 = `C:/Users/33393/Desktop/fazhi-nondeploy-closeout-20261010-b4e7a2`。

## §0 三行汇总

1. **现量**（2026-10-11，Python 3.11.0，`pip freeze --all` = 181 行）：对**候选** `requirements.txt` 有 **6 条偏离** —— `fastapi 0.110.3`（声明 `==0.141.1`）、`uvicorn 0.52.1`（声明 `>=0.27,<0.28`，**高于上限**）、`sentence-transformers 2.7.0`（`>=6.0,<7.0`）、`sqlalchemy 2.0.51`（`>=2.1,<3.0`）、`pypdf 6.14.2`（`==6.19.0`）、`torch 2.6.0+cpu`（`==2.13.0`）。
2. **既有不一致**：`pip check` 两条红 —— `fastapi 0.110.3` 要 `starlette>=0.37.2,<0.38` 而现装 `0.36.3`；`sse-starlette 3.4.8` 要 `starlette>=0.49.1` 而同版本。这两条**与本轮无关**（在册既有形状）。
3. **轴要说清**：同一条命令对**主仓（旧 master）** 那份 requirements 跑出来是 **21 条声明 / 4 条偏离**（那份没有 `torch` 行、`sqlalchemy` 下限还是 `>=2.0`）⇒ 报"偏离几条"必须点名读的哪一份文件。

## §1 复算命令（开工前重跑，别引用本票数字）

```bash
R=/c/Users/33393/Desktop/fazhi-nondeploy-closeout-20261010-b4e7a2
M=/c/Users/33393/Desktop/ai-legal-helper
X="$(cygpath -w "$M/backend/venv/Scripts/python.exe")"
# 整表机械对账（尺子在运行根 evidence/，只读）
"$R/candidate-envB/Scripts/python.exe" "$(cygpath -w "$R/evidence/venv_vs_requirements_axis.py")" \
    "$X" "$(cygpath -w "$M/.worktrees/nondeploy-closeout-20261010/backend/requirements.txt")" | tail -2
"$M/backend/venv/Scripts/python.exe" -m pip freeze --all | sort > "$R/evidence/d6-venv-freeze-before.txt"
"$M/backend/venv/Scripts/python.exe" -m pip check
```

尺子自身的负向对照：故意把某行下限抬到现装之上（改**副本** requirements，不动真文件），偏离数必须 +1；不涨说明判定分支没走到。

## §2 任务范围

做：
1. **存证**：`pip freeze --all | sort` 前后各一份（比较用**排序后的行集合**，`pip freeze` 的原始顺序不稳，直接比 sha 会假红）。
2. **单变量逐包升**：每包一次 `pip install --no-deps "<pkg><声明区间>"`，装完立刻复跑 §1 的对账 + `pip check`，把每包的"改前/改后"两条读数落到 `evidence/d6-step-N-*.log`。**一次只动一只**，出现新红就还原这一只再看下一只。
3. `uvicorn 0.52.1` 是**高于上限**（`<0.28`）⇒ 这一条是**降级**，不是升级，要单独确认没有别的包在要求它。
4. 全部到位后跑候选树全量门禁（见 §4）一次，确认这个 venv 能过产品门禁。
5. 回报里给出"回退脚本"：按 freeze 存证重建同一套装出集的确切命令。

不做：
- 不动 `candidate-envB` / `candidate-envC-1x`（D-3 那轮的对照环境，别的会话在读）。
- 不动生产容器、不重启 compose 栈、不碰端口 3021/8088。
- 不为了"绿"去放宽候选 `requirements.txt` 的区间（那是产品声明，要动得先回报）。
- 不 `pip uninstall` 整环境、不 `--force-reinstall` 全表。

## §3 硬约束（红线）

- **只读禁打**：`backend/.env` 及任何 `.env*`、`backend/app.db`、`backend/data/`、`backend/chroma_db/`、`backend/media/`、`backend/backups/`、`C:/Users/33393/.cache/huggingface/`；不打印任何凭据值。
- **真实库零读写**：不跑 `backend/scripts/smoke_*.py`（`os.chdir` + `load_dotenv` 会装真实配置与真实配额库）；测试走 conftest 的三个隔离出口（`tests/conftest.py:23,32,40`）。
- **不装进别的解释器**：每条 `pip install` 前打印 `python -V` 与 `sys.prefix` 并核对是 `backend/venv`（PATH 上的 `python` 不是这个 venv，这是在册判例）。
- **不动 ref**：不 commit / 不 push / 不 merge / 不改分支。产品字节改动不在本票范围（若为对齐需要改 `requirements.txt` ⇒ 停，回报）。
- **可还原性优先**：任何一步失败 ⇒ 先用存证还原，再回报；不要在半成品状态上继续升第二只。

## §4 判据

1. 对账尺：候选 requirements 的偏离数从 **6 → 0**（读的是候选那份，见 §0 第 3 行）。
2. `pip check`：从 **2 条红 → 0 条**（`No broken requirements found`）。这条是硬门：它证明装出来的集合自洽，而不只是"每只都在区间里"。
3. 全量门禁四腿 rc=0，且与在册基线**同数**（`--collect-only` 取 collected、junit 用例数配平；见 `reports/gates.md` 的轴纪律）。⚠️ 这一步要在**候选树**里跑、用升级后的 venv 当解释器；跑前先记一次基线，因为基线会随别的会话提交漂。
4. freeze 差集：逐包列出"改了哪几只 + 各自动了什么"，与 §2.2 的步骤日志一一对应；**新增/删除的传递依赖要单独点名**（D-3 那轮的口径：版本变化 N 只、新增 M 只，其余逐字不动）。

## §5 交付物

- `<运行根>/reports/d6-venv-alignment-20261011.md`：§0 三行 → §1 前后读数（对账尺 + `pip check` + 四腿门禁）→ §2 逐包步骤表（改前/改后/rc）→ §3 我自己犯的错 → §4 已知限制 → §5 回退脚本 → §6 待裁台账（每条一词可答 + 推荐）→ §7 证据指针。
- `<运行根>/evidence/d6-*`：freeze 前/后（排序后的行集合）、每步 `pip` 日志、门禁日志、对账尺输出。
- 所有新写文件落 **LF** 并自量 `tr -dc '\r' | wc -c` = 0。

## §6 停止条件

1. 逐包升完仍无法让 `pip check` 归零（两只以上互相咬）⇒ **停**，改提案："新建一个 venv 从候选 requirements 装，旧 venv 原样保留"，把两轮的取舍摊给 Owner。理由：现集合里有 2 条既有不一致，逐包 `--no-deps` 有可能把它焊死。
2. 需要改 `requirements.txt` 才能自洽 ⇒ 停，回报（那是产品声明面，不是开发环境面）。
3. 升级后全量门禁出现**开工前没有**的红 ⇒ 先单变量归因（`pip install --no-deps` 还原那一只再看红是否消失），归因不清就停。
4. 任何一步要动 §3 禁打路径才能继续 ⇒ 停。
