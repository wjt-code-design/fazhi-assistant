"""AST 哨兵：所有日志字段必须登记在 `observability._ACCOUNT_FIELDS` 白名单内。

理由：`_JsonFormatter` **只**拷贝白名单内的键 ⇒ 白名单外的字段会被**静默丢弃**。
该缺陷在本项目已真实发生两次：
  - handoff §12.3：`agent_pre_run_*` 三个字段被丢掉，导致预运行失败的唯一诊断点失明（7 种抛错文案
    坍缩成一个"未知"），存活约 6 天；
  - V2-T8 自审：AST 哨兵又扫出 4 处同族（`agent_run_id` / `agent_planner_raw_tail` /
    `agent_actual_route` / `agent_fallback_reason`）。

用 AST 静态扫描而非运行时断言，故能覆盖**未被测试执行到**的分支。
"""

from __future__ import annotations

import ast
import pathlib

from observability import _ACCOUNT_FIELDS

BACKEND = pathlib.Path(__file__).resolve().parents[1]
_SKIP_PARTS = {"venv", "__pycache__", "site-packages", "tests"}
# formatter 自身写入的键，不属于业务 extra
_BUILTIN = {"request_id", "ts", "level", "logger", "req", "msg", "exc"}


def iter_log_fields(root: pathlib.Path) -> list[tuple[str, int, str, str]]:
    """扫描 (文件, 行, 形态, 字段名)：`extra={...}` 的字面键 与 `log_account(k=v)` 的关键字。"""
    findings: list[tuple[str, int, str, str]] = []
    for path in sorted(root.rglob("*.py")):
        if _SKIP_PARTS & set(path.parts):
            continue
        rel = path.relative_to(root.parent).as_posix()
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            fn = node.func
            name = fn.attr if isinstance(fn, ast.Attribute) else (fn.id if isinstance(fn, ast.Name) else "")
            for kw in node.keywords:
                if kw.arg == "extra" and isinstance(kw.value, ast.Dict):
                    for key in kw.value.keys:
                        if isinstance(key, ast.Constant) and isinstance(key.value, str):
                            findings.append((rel, node.lineno, "extra", key.value))
            if name == "log_account":
                for kw in node.keywords:
                    if kw.arg:
                        findings.append((rel, node.lineno, "log_account", kw.arg))
    return findings


def test_log_field_whitelist_sentinel_detects_violation(tmp_path):
    """watch-it-fail：哨兵必须**真的能**抓到违规字段，否则它只是个恒真断言。"""
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "sample.py").write_text(
        "import logging\nlogging.getLogger('legal.agent').info('x', extra={'deliberately_missing_field': 1})\n",
        encoding="utf-8",
    )
    found = iter_log_fields(pkg)
    assert [f[3] for f in found] == ["deliberately_missing_field"], "哨兵未能识别白名单外字段"


def test_log_fields_are_all_registered_in_whitelist():
    """主断言：全仓所有日志字段都必须能被 JSON formatter 落进结构化日志。"""
    allowed = set(_ACCOUNT_FIELDS) | _BUILTIN
    offenders = [
        f"{rel}:{line} [{kind}] {key}" for rel, line, kind, key in iter_log_fields(BACKEND) if key not in allowed
    ]
    assert not offenders, (
        "以下日志字段会被 JSON formatter **静默丢弃**，请登记进 observability._ACCOUNT_FIELDS：\n  "
        + "\n  ".join(offenders)
    )
