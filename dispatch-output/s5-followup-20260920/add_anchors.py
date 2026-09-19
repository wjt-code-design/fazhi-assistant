"""一次性给 13 条 content-yield 加 `# gate-exit: E<n>` 锚点（R7，零行为改动）。

行号不手写：从 `gate_exit_registry.scan_content_yields()` 现算（那才是「什么算一个出口」的唯一定义），
按源码升序配 E1..E13 ⇒ 与登记表行序天然一致，不存在"我数错一条"这种错法。
CRLF 感知：读字节→折叠成 LF 处理→按原风格写回（本仓 `core.autocrlf=true`）。
幂等：已有锚点的行跳过，可重复执行。
"""

from __future__ import annotations

import pathlib
import re
import sys

BACKEND = pathlib.Path(__file__).resolve().parents[2] / "backend"
sys.path.insert(0, str(BACKEND))

from gate_exit_registry import EXITS, scan_content_yields  # noqa: E402

MARKER = re.compile(r"#\s*gate-exit:\s*(E\d+)\b")


def main() -> int:
    target = BACKEND / "main.py"
    raw = target.read_bytes().decode("utf-8")
    nl = "\r\n" if "\r\n" in raw else "\n"
    lines = raw.replace("\r\n", "\n").split("\n")

    yields = scan_content_yields(raw)
    if len(yields) != len(EXITS):
        print(f"ABORT: 扫到 {len(yields)} 条 content-yield，登记表有 {len(EXITS)} 行 ⇒ 先对齐再插锚点")
        return 2

    rows = []
    for (lineno, expr), row in zip(yields, EXITS):
        i = lineno - 1
        old = lines[i]
        found = MARKER.search(old)
        if found:
            rows.append((lineno, expr, row["id"], found.group(1), "已有锚点" + ("（一致）" if found.group(1) == row["id"] else " ⇒ 不一致!")))
            if found.group(1) != row["id"]:
                return 3
            continue
        lines[i] = f"{old}  # gate-exit: {row['id']}"
        rows.append((lineno, expr, row["id"], row["id"], "新插入"))
    target.write_bytes(nl.join(lines).encode("utf-8"))

    print(f"{'行号':<6}{'正文表达式':<28}{'锚点':<6}动作")
    for a, b, c, d, e in rows:
        print(f"{a:<6}{b[:26]:<28}{c:<6}{e}")
    print(f"wrote={target}  nl={'CRLF' if nl == chr(13)+chr(10) else 'LF'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
