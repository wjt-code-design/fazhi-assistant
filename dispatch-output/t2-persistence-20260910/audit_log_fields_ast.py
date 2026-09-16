"""自审哨兵（AST）：找出所有"会被 JSON formatter 静默丢弃"的日志字段。

原理：`observability._ACCOUNT_FIELDS` 是白名单，`_JsonFormatter` **只**拷贝白名单内的键。
任何日志调用传入白名单外的字段，都会**无声消失**——§12.3 的 `agent_pre_run_*` 就是这么丢了 6 天。

覆盖两种传参形态：
  (a) `logger.xxx(..., extra={"k": v})` 的字面键
  (b) `log_account(k=v, ...)` 的关键字实参
只读 AST，不执行、不导入被测模块（避免副作用）。
"""

from __future__ import annotations

import ast
import pathlib
import sys

BACKEND = pathlib.Path(__file__).resolve().parents[2] / "backend"
sys.path.insert(0, str(BACKEND))

from observability import _ACCOUNT_FIELDS  # noqa: E402  （只读常量）

whitelist = set(_ACCOUNT_FIELDS)
# formatter 还会写这几个内置键，不应被误报
builtin = {"request_id", "ts", "level", "logger", "req", "msg", "exc"}

findings: list[tuple[str, int, str, str]] = []   # (file, line, kind, key)
seen: set[str] = set()

for path in sorted(BACKEND.rglob("*.py")):
    parts = set(path.parts)
    if "venv" in parts or "__pycache__" in parts or "site-packages" in parts or "tests" in parts:
        continue
    rel = path.relative_to(BACKEND.parent).as_posix()
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except SyntaxError:
        continue
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        name = fn.attr if isinstance(fn, ast.Attribute) else (fn.id if isinstance(fn, ast.Name) else "")

        # (a) extra={...}
        for kw in node.keywords:
            if kw.arg == "extra" and isinstance(kw.value, ast.Dict):
                for k in kw.value.keys:
                    if isinstance(k, ast.Constant) and isinstance(k.value, str):
                        seen.add(k.value)
                        if k.value not in whitelist and k.value not in builtin:
                            findings.append((rel, node.lineno, "extra", k.value))
        # (b) log_account(**kw) —— 只查直接以关键字传入的形态
        if name == "log_account":
            for kw in node.keywords:
                if kw.arg:
                    seen.add(kw.arg)
                    if kw.arg not in whitelist and kw.arg not in builtin:
                        findings.append((rel, node.lineno, "log_account", kw.arg))

print(f"扫描到日志字段名 {len(seen)} 个（含白名单内外）")
print(f"白名单 _ACCOUNT_FIELDS 共 {len(whitelist)} 项")
print()
if findings:
    print(f"❌ 发现 {len(findings)} 处**会被静默丢弃**的字段：")
    for rel, line, kind, key in findings:
        print(f"  {rel}:{line}  [{kind}]  {key}")
else:
    print("✅ 未发现白名单外字段：所有日志字段都能落进结构化日志")

unused = sorted(whitelist - seen)
print()
print(f"白名单中未被任何静态调用点使用的字段（{len(unused)} 项，仅供参考，动态传参不计）：")
print("  " + ", ".join(unused))
