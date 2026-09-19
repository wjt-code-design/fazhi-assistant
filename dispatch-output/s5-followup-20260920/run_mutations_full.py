"""全量变异复审（S5 后续 · 计划 R5 / 步骤 1d）。

为什么必须跑**全量**：S5 那轮四个变异每个只跑 `tests/test_fast_path_law_version_gate.py` 一个文件，
结构上看不见别处 ⇒ `main.py` 里"命中不进缓存"那道 load-bearing 闸被删掉后全量零反应（票 G F5 存活）。
本脚本把每个变异跑整套 `tests/`，用 junit 差分归因：只有"基线绿 → 变异红"的集合非空才算被杀。

用法：python run_mutations_full.py <副本树根> <输出目录>
边界：只在**副本树**跑（live 树禁止 —— 花钱 + 抢 app.db/chroma）。
"""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys
import xml.etree.ElementTree as ET

MUTANTS: dict[str, tuple[str, str]] = {
    # 票 G G-M1：删掉"命中不进缓存"那道闸（S5 提交信息里写明"否则门再也走不到"）
    "M1_cache_guard_off": (
        'if cache_key and res.verdict == "pass" and not res.law_version_hit:',
        'if cache_key and res.verdict == "pass":',
    ),
    # 本轮 1a 的反向保险：把调用点退回"直接传 body.law_as_of"（漏搬第①半）
    "M2_callsite_half1_removed": (
        "_light_buffered, pre, messages, _fast_path_law_as_of(body))",
        "_light_buffered, pre, messages, body.law_as_of)",
    ),
    # 票 G G-M4：空答案也追加注记（本轮 1c 重写的用例应当能杀它）
    "M3_empty_answer_note_appended": (
        'answer=(res.answer + NOTE_LAW_VERSION) if res.answer else "",',
        "answer=res.answer + NOTE_LAW_VERSION,",
    ),
    # 票 G G-M3：缺基准日改为放行（fail-open）
    "M4_missing_date_passes": (
        '        reason = "LAW_TRIPWIRE_NOT_WIRED"',
        "        return res",
    ),
}


def read_main(p: pathlib.Path) -> tuple[str, str]:
    raw = p.read_bytes().decode("utf-8")
    nl = "\r\n" if "\r\n" in raw else "\n"
    return raw.replace("\r\n", "\n"), nl


def write_main(p: pathlib.Path, text: str, nl: str) -> None:
    p.write_bytes(text.replace("\n", nl).encode("utf-8"))


def failed_set(xml_path: pathlib.Path) -> set[str]:
    if not xml_path.exists():
        return set()
    out: set[str] = set()
    for tc in ET.parse(xml_path).getroot().iter("testcase"):
        if tc.find("failure") is not None or tc.find("error") is not None:
            out.add(f"{tc.get('classname')}::{tc.get('name')}")
    return out


def run_suite(tree: pathlib.Path, out_dir: pathlib.Path, tag: str, py: str) -> set[str]:
    xml = out_dir / f"full-{tag}.xml"
    cmd = [
        py,
        "-m",
        "pytest",
        "tests/",
        "-q",
        "-p",
        "no:cacheprovider",
        f"--basetemp={out_dir / 'bt'}",
        f"--junitxml={xml}",
    ]
    proc = subprocess.run(cmd, cwd=tree / "backend", capture_output=True, text=True, encoding="utf-8", errors="replace")
    (out_dir / f"stdout-{tag}.txt").write_text(
        f"$ {' '.join(cmd)}\nrc={proc.returncode}\n\n{proc.stdout}\n\n== stderr tail ==\n{proc.stderr[-4000:]}\n",
        encoding="utf-8",
    )
    return failed_set(xml)


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__)
        return 2
    tree = pathlib.Path(sys.argv[1]).resolve()
    out_dir = pathlib.Path(sys.argv[2]).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    main_py = tree / "backend" / "main.py"
    orig, nl = read_main(main_py)

    baseline = run_suite(tree, out_dir, "baseline", sys.executable)
    print(f"baseline_failed={len(baseline)}", flush=True)

    table = {}
    for name, (old, new) in MUTANTS.items():
        if orig.count(old) != 1:
            print(f"{name}: ANCHOR-NOT-UNIQUE count={orig.count(old)} —— 跳过并报错", flush=True)
            table[name] = {"status": "anchor-error", "count": orig.count(old)}
            continue
        write_main(main_py, orig.replace(old, new, 1), nl)
        try:
            mutant = run_suite(tree, out_dir, name, sys.executable)
        finally:
            write_main(main_py, orig, nl)  # 无论成败都还原
        killed = sorted(mutant - baseline)
        newly_green = sorted(baseline - mutant)
        table[name] = {
            "status": "KILLED" if killed else "SURVIVED",
            "mutant_failed": len(mutant),
            "newly_red": killed,
            "newly_green": newly_green,
        }
        print(f"{name}: {table[name]['status']} mutant_failed={len(mutant)} newly_red={killed}", flush=True)

    restored, _ = read_main(main_py)
    table["_self_check"] = {"main_py_restored_byte_exact": restored == orig}
    (out_dir / "mutation-report-full.json").write_text(json.dumps(table, ensure_ascii=False, indent=1), encoding="utf-8")
    survived = [k for k, v in table.items() if isinstance(v, dict) and v.get("status") == "SURVIVED"]
    print(f"VERDICT={'ALL_KILLED' if not survived else 'SURVIVORS:' + ','.join(survived)}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
