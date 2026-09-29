# B 轮复扫运行记录（2026-09-29）

本件是**已跟踪**的运行记录。扫描器的 stderr 汇总行（`Found N known vulnerabilities in M packages`）
原本只落在同目录的 `*.err.log` 里，而 `.gitignore:45` 全仓忽略 `*.log` ⇒ 那些汇总行**只在执行过的这台机器上**。
所以把它们抄进本件，让三笔读数在仓库内可核。**原始 `.err.log` 未删、未改，仍留在本机**（本件是抄件，不是替代）。

| # | 对象 | 工作目录 / 目标文件 | rc | stderr 汇总行 | 读数 | 性质 |
|---|---|---|---|---|---|---|
| 1 | 主工作区解析集（**我的误跑**） | `backend/requirements.txt` @ `master` | 1 | `Found 138 known vulnerabilities in 10 packages` | 138 行 / 10 包 | **漏洞非零**（不是扫描器故障）；解出 pypdf 5.9.0 / fastapi 0.110.3 / starlette 0.37.2 ⇒ 这是**升级前**的形态 |
| 2 | 候选 venv 实装集 | `pip_audit`（无 `-r`，读实装环境） | 1 | `Found 57 known vulnerabilities in 10 packages` | 57 行 / 10 包 | 同上性质 |
| 3 | 候选解析集 | `fbc29e8` 树的 `backend/requirements.txt` | 1 | `Found 47 known vulnerabilities in 8 packages` | 47 行 / 8 包 | 同上性质 |

- 解释器：`C:\Users\33393\AppData\Local\Temp\legal-closeout-20260928\venv\Scripts\python.exe`（Python 3.11.0）
- 命令形态：`python -m pip_audit [-r <requirements.txt>] --format json --timeout 90`（stdout→`.json`，stderr→`.err.log`，**分开重定向**，
  所以三份 `.json` 是**纯 JSON**、头部没有横幅；这与 09-28 那两份 `candidate-*-pip-audit.json` 的形状不同 —— 那两份把横幅混进了文件头，
  直接 `json.load` 会炸，必须从第一个 `{` 起读。**引用它们的脚本要记得这一点**。）
- 三条 rc 都是 1，且三条的 stderr **都没有 `ReadTimeout`/ traceback** ⇒ 与 09-28 `postcommit-gates.log` 第 9 步那次
  `pypi.org` 网络失败的 rc=1 **是两种红**，不可混记（那条更正见交接书 §4.1）。
- 第 1 笔是我读错目标树跑出来的（`master` 不是候选树），**故意留盘不删**：它顺手证了 `master` 今天仍是 138 条的红，
  于是"合入候选才把解析集降到 47"这条有了两侧读数。引用时**不要**把它当候选现状。

## 与 09-28 快照的漂移比对（判据不是比条数）

比的是 `(包名, ID ∪ CVE 别名)` 集合的**对称差** —— 只比条数会放过"条数相同但别名换位"那种变化。

```bash
cd dispatch-output/local-candidate-closeout-20260928
python b_scope_recount.py --write   # 现算三轴 + 闭合检查（26+5==31），对不上就 rc=1
```

结果：解析集、实装集两轴 **零新增 / 零消失 / 零版本漂移**；登记表 26 条与今日解析集**闭合**，
实装集多出的 5 条全部落在**开发/构建工具**（`pytest`、`setuptools`，`requirements.txt` 里没有它们）。

## 本地件清单（`.log` 未入库，交接时须连目录拷或按上面命令复跑）

- `B-requirements-pip-audit-refresh-20260929-164325.json` / `.err.log`
- `B-installed-pip-audit-refresh-20260929-164325.json` / `.err.log`
- `B-candidate-requirements-pip-audit-refresh-20260929-164555.json` / `.err.log`
- `B-refresh-exitcodes-20260929-164325.txt`、`B-refresh-exitcodes-20260929-164555.txt`（早期随手记，内容以本件为准）
- `protected-takeover-20260929.log`（接手时保护对象复验，**新日志名**，未覆盖 09-28/09-29 任何旧证据）
