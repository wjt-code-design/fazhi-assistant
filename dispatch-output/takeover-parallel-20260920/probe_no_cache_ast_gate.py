"""我（主会话）把 T9 嵌在 checklist.md 里的 AST 闸原样抽出来跑 —— 闸未被执行过就不算闸。

同时验证两个方向（一次跑出双向证据）：
  ① 能抓：漏传 no_cache 的调用点必须被打印；
  ② 不空枪/不误报：已传 no_cache=True 的 4 处调用点、以及 capture_eval.py:183 的**方法定义**，
     都不应出现在输出里（后者是 T9 自己点名的单行 grep 假阳性）。

用法：backend/venv/Scripts/python.exe probe_no_cache_ast_gate.py
"""

from __future__ import annotations

import ast
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
ROOT = REPO / "backend" / "scripts"

leaks: list[str] = []
ok: list[str] = []
DEF_LINE = "capture_eval.py:183"


def main() -> int:
    for p in ROOT.rglob("*.py"):
        try:
            tree = ast.parse(p.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for n in ast.walk(tree):
            if isinstance(n, ast.Call):
                name = getattr(n.func, "attr", getattr(n.func, "id", ""))
                if name in ("chat", "chat_stream"):
                    has = any(
                        kw.arg == "no_cache"
                        and isinstance(kw.value, ast.Constant)
                        and kw.value.value is True
                        for kw in n.keywords
                    )
                    rec = f"{p.relative_to(ROOT).as_posix()}:{n.lineno} {name}"
                    (ok if has else leaks).append(rec)

    print("== LEAK（漏传 no_cache，批前打回）==")
    for rec in leaks:
        print(f"  LEAK {rec}")
    print(f"leak_count={len(leaks)}")
    print("== PASS（已传 no_cache=True，闸应沉默）==")
    for rec in ok:
        print(f"  PASS {rec}")
    print(f"pass_count={len(ok)}")

    # 控制腿：闸不能把方法定义当调用点
    print("== 控制腿 ==")
    print(
        f"def_line_flagged={'YES(BUG)' if any(DEF_LINE.split(':')[1] in r for r in leaks) else 'NO(ok)'}"
    )
    print(f"total_call_sites={len(leaks) + len(ok)}")
    print("note: 判定标准 = leak 应恰为漏传点；4 处已传者不得进 leak（否则闸假阳）。")
    return 0 if leaks else 1


if __name__ == "__main__":
    sys.exit(main())
