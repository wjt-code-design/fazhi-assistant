# 票据：mypy `Row[...]` 泛型形状（2 条既有错误）

- 状态：**DONE（2026-10-27 已修）**
- 影响面：`backend/main.py` 两个管理员读接口的类型注解；不影响运行时
- 触发命令：`cd backend && .\venv\Scripts\python.exe -m mypy .`
- 修前读数：**2 errors in 1 file (checked 74 source files)**；修后 **0 errors**（`Success: no issues found in 74 source files`）

## 1. 现象

```
main.py:3149: error: "Row" expects 1 type argument, but 2 given  [type-arg]
main.py:3360: error: "Row" expects 1 type argument, but 2 given  [type-arg]
```

对应两处（行号会随改动漂移，按符号锚定）：

- `admin_conversations`：`rows: list[Row[Conversation, str]]`
- `admin_audit`：`rows: list[Row[AuditLog, str | None]]`

两条都是**既有错误**：2026-10-27 的评测隔离改动只让行号漂移（当前 **3149/3360**，以后还会随改动漂），不是本次引入。

## 2. 根因

当前验收解释器（`backend/venv`）装的是 **SQLAlchemy 2.0.51**，其 `Row` 的类型参数已变成**单个**（`Row[tuple[A, B]]` 形状）；代码写于旧形状 `Row[A, B]` 可用的时期。`scripts/` 整体在 mypy `exclude` 内，所以这个问题只在 `main.py` 暴露。

环境读数（2026-10-27）：

| 解释器 | SQLAlchemy | mypy |
|---|---|---|
| `backend/venv`（验收轴） | 2.0.51 | 2.3.0 |
| `backend/venv-new` | 2.1.4 | 2.4.0 |

## 3. 两条修法（建议 A）

### A. 改注解为新形状（已采用）

```python
rows: list[Row[tuple[Conversation, str]]] = (...)
rows: list[Row[tuple[AuditLog, str | None]]] = (...)
```

- 已用临时文件实测：`Row[tuple[int, str]]` 在 mypy 2.3.0 + SQLAlchemy 2.0.51 下 **0 error**，且运行时 `Row[tuple[int, str]]` 可正常求值（Python 3.11）。
- 只动两行注解，不改查询、不改返回结构，运行时不产生行为变化。
- 代价：注解与 `Row` 的新泛型形状绑定；未来 SQLAlchemy 再改形状时还要跟一次。

### B. 钉 SQLAlchemy 版本

把 `requirements.txt` 的 `sqlalchemy>=2.0,<3.0` 收窄到仍接受 `Row[A, B]` 的版本。

- 优点：不动代码。
- 代价：依赖面变动，需要重跑依赖闭包/CI/全量测试；且会与 C08「四包固定闭包」的边界产生新的口径讨论。**不建议为 2 条类型注解付这个成本。**

### C. `# type: ignore[type-arg]`

- 最快，但把依赖漂移藏起来，和本仓「证据先于声明」的口径相反。不建议。

## 4. 验收判据（修 A 时）

1. `cd backend && .\venv\Scripts\python.exe -m mypy .` ⇒ **0 errors**，`checked 74 source files`；
2. `.\venv\Scripts\python.exe -m pytest -q` ⇒ **0 failed**（基线 2139 passed / 2 skipped，以实跑为准）；
3. `ruff check` / `ruff format --check` 全绿（钩子用 `venv-new` + 仓库根配置）；
4. `admin_conversations` / `admin_audit` 的返回字段不变（可加一条端点级冒烟或直接比对 JSON 键）；
5. 不改 `scripts/` 的 mypy 排除、不顺手改其他 `Row` 用法。

## 5. 复跑与证据

```powershell
cd c:\Users\33393\Desktop\ai-legal-helper\backend
.\venv\Scripts\python.exe -m mypy .
```

2026-10-27 的 mypy 读数来自本轮收口实测；pytest 证据在 `docs/benchmark_results/_pytest_*_nocurate.log`（`*.log` 被忽略，本机可读）。修完后把本票状态改为 DONE，并在交接 §6 删掉对应缺口。

## 6. 修复记录（2026-10-27）

- 采用 A：`admin_conversations` / `admin_audit` 两处注解放宽为 `Row[tuple[...]]`。
- `mypy .`：**Success: no issues found in 74 source files**。
- 全量 pytest：**2141 passed / 2 skipped / 0 failed（647.60s）**。
- 运行时：注解在导入时求值，`Row[tuple[...]]` 可正常构造；查询与返回结构未变。
- 行号：修复后错误消失；本票保留原 3149/3360 作为历史锚点（行号会随改动漂移）。
