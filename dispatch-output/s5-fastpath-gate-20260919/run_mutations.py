"""S5 §6-④：变异执行器。规格是数据（JSON），本脚本只负责 打补丁 → 跑测试 → 逐字还原 → 自证还原。

设计约束（票面 §12 环境坑）：
- 变异窗口内读到的 sha256 无意义 ⇒ 只有**还原之后**自报的 `sha_after == sha_before` 才算证据；
- 等子进程用副作用哨兵（本脚本自己同步等，且要求 pytest 输出里出现 `rc=`），不看 pgrep；
- 落盘写字节，绕开 core.autocrlf 与 Windows 文本模式的 \\r\\n 转换。

用法（cwd 必须是 backend/）：
    ./venv/Scripts/python.exe ../dispatch-output/s5-fastpath-gate-20260919/run_mutations.py mutants.json

mutants.json 形状：
    [{"name":"M1","desc":"摘掉整道门","target":"main.py",
      "snippet":"<必须恰好出现一次的原文>","replacement":"<替换文本>",
      "expect_failed_test":"test_...","pytest_args":["tests/test_fast_path_law_version_gate.py","-q"]}]
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2] / "backend"
OUT = Path(__file__).resolve().parent


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def apply_one(target: Path, snippet: str, replacement: str) -> bytes:
    """返回原文件字节；替换失败（命中 0 次或 >1 次）直接抛错，不写盘。

    ⚠️ 票面坑①：`core.autocrlf=true` ⇒ 本仓落盘是 CRLF（实测 main.py：CRLF 2643 / 裸 LF 0）。
    规格 JSON 里的锚点按习惯写 \\n，直接匹配必然 0 命中 —— 这里按目标文件的实际换行归一，
    避免"变异没生效"被误读成"测试抓不到"。
    """
    original = target.read_bytes()
    text = original.decode("utf-8")
    nl = "\r\n" if "\r\n" in text else "\n"

    def fold(s: str) -> str:
        return s.replace("\r\n", "\n").replace("\n", nl)

    sn, rep = fold(snippet), fold(replacement)
    n = text.count(sn)
    if n != 1:
        raise SystemExit(f"变异锚点命中 {n} 次（必须恰好 1 次）：{snippet[:80]!r}")
    mutated = text.replace(sn, rep, 1)
    target.write_bytes(mutated.encode("utf-8"))
    return original


FAILED_RE = re.compile(r"^(?:FAILED|ERROR) \S*::([A-Za-z0-9_]+)", re.M)


def run_pytest(args: list[str]) -> tuple[int, str]:
    proc = subprocess.run(
        [str(BACKEND / "venv" / "Scripts" / "python.exe"), "-m", "pytest", *args, "-p", "no:cacheprovider"],
        cwd=str(BACKEND),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return proc.returncode, proc.stdout + proc.stderr


def main(spec_path: str) -> int:
    specs = json.loads(Path(spec_path).read_text(encoding="utf-8"))
    report = []
    for spec in specs:
        target = BACKEND / spec.get("target", "main.py")
        sha_before = sha(target)
        try:
            original = apply_one(target, spec["snippet"], spec["replacement"])
        except SystemExit as exc:  # 锚点命中次数不对 ⇒ 规格写错。记一条继续跑，别让一条拖垮整批。
            report.append({"name": spec["name"], "desc": spec.get("desc", ""), "spec_error": str(exc), "verdict": "SPEC-ERROR"})
            print(f"[{spec['name']}] SPEC-ERROR {exc}", flush=True)
            continue
        try:
            rc, out = run_pytest(spec["pytest_args"])
        finally:
            target.write_bytes(original)  # 字节级还原，不走任何文本编码转换
        sha_after = sha(target)
        restored = sha_after == sha_before
        failed = sorted(set(FAILED_RE.findall(out)))
        # 断言定位：pytest 的输出里失败断言所在行以 `> ` 开头，紧随其后的 E 行是断言内容
        m = re.search(r"^(> .*?)\n(E\s+.*)$", out, re.M | re.S)
        entry = {
            "name": spec["name"],
            "desc": spec.get("desc", ""),
            "rc": rc,
            "restored": restored,
            "sha_before": sha_before,
            "sha_after": sha_after,
            "failed_tests": failed,
            "expect_failed_test": spec.get("expect_failed_test", ""),
            "red_on_assertion": (m.group(1)[:300] + " || " + m.group(2)[:300]) if m else "",
        }
        entry["verdict"] = (
            "OK"
            if restored and rc != 0 and entry["expect_failed_test"] in failed
            else "SUSPECT"  # 没红 / 红的不是期望那条 / 没还原成功
        )
        report.append(entry)
        print(f"[{entry['name']}] rc={rc} restored={restored} verdict={entry['verdict']} failed={failed}", flush=True)

    out_path = OUT / "mutation-report.json"
    out_path.write_bytes(json.dumps(report, ensure_ascii=False, indent=1).encode("utf-8"))
    print(f"report={out_path}", flush=True)
    print(f"all_restored={all(r.get('restored', True) for r in report)}", flush=True)
    print(f"suspect={[r['name'] for r in report if r.get('verdict') not in ('OK', 'SPEC-ERROR')]}", flush=True)
    print(f"spec_errors={[r['name'] for r in report if r.get('verdict') == 'SPEC-ERROR']}", flush=True)
    print("rc=0", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
