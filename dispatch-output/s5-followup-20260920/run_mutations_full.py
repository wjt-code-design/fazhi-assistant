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


def suite_stats(xml_path: pathlib.Path) -> tuple[int, int, int]:
    """`(tests, failures, errors)` —— **分母**。没有它，"红了几条"这句话可以来自一次整轮崩盘。"""
    if not xml_path.exists():
        return (-1, 0, 0)
    root = ET.parse(xml_path).getroot()
    suite = root if root.tag == "testsuite" else root.find("testsuite")
    if suite is None:  # 只写了 <testsuites> 外壳的形状
        suite = next(root.iter("testsuite"), None)
    if suite is None:
        return (-1, 0, 0)
    return (
        int(suite.get("tests") or 0),
        int(suite.get("failures") or 0),
        int(suite.get("errors") or 0),
    )


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
    # check=False 是有意的：pytest 非零退出是**正常结果**（红几条正是我们要量的），
    # rc 被写进 stdout-<tag>.txt 供人核对。
    proc = subprocess.run(
        cmd,
        cwd=tree / "backend",
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
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
    btests, bfail, berr = suite_stats(out_dir / "full-baseline.xml")
    print(
        f"baseline_failed={len(baseline)} 分母 tests={btests} failures={bfail} errors={berr}",
        flush=True,
    )
    # 分母不健全 ⇒ 整轮作废。旧版这里什么都不查：基线若是"整体崩盘 → xml 空 → ∅"，
    # 那么任何一次红都会被判成 newly_red ⇒ 高高兴兴报出 ALL_KILLED。这是仪器层的假绿。
    if btests <= 0 or berr > 0:
        print("VERDICT=RUN_VOID（基线分母不健全：tests=0 或有 error 计数）", flush=True)
        return 2

    table = {}
    for name, (old, new) in MUTANTS.items():
        if orig.count(old) != 1:
            print(
                f"{name}: ANCHOR-NOT-UNIQUE count={orig.count(old)} —— 跳过并报错",
                flush=True,
            )
            table[name] = {"status": "anchor-error", "count": orig.count(old)}
            continue
        write_main(main_py, orig.replace(old, new, 1), nl)
        try:
            mutant = run_suite(tree, out_dir, name, sys.executable)
        finally:
            write_main(main_py, orig, nl)  # 无论成败都还原
        mtests, _mfail, merr = suite_stats(out_dir / f"full-{name}.xml")
        if mtests != btests or merr > 0:
            # 分母漂了 ⇒ 这一条的"红/不红"没有意义（少跑了测试 = 可能根本没跑到那条断言）
            print(
                f"{name}: DENOMINATOR-DRIFT tests={mtests} vs 基线 {btests}, errors={merr}",
                flush=True,
            )
            table[name] = {
                "status": "denominator-drift",
                "tests": mtests,
                "baseline_tests": btests,
                "errors": merr,
            }
            continue
        killed = sorted(mutant - baseline)
        newly_green = sorted(baseline - mutant)
        table[name] = {
            "status": "KILLED" if killed else "SURVIVED",
            "mutant_failed": len(mutant),
            "tests": mtests,
            "newly_red": killed,
            "newly_green": newly_green,
        }
        print(
            f"{name}: {table[name]['status']} mutant_failed={len(mutant)} newly_red={killed}",
            flush=True,
        )

    restored, _ = read_main(main_py)
    table["_self_check"] = {"main_py_restored_byte_exact": restored == orig}
    (out_dir / "mutation-report-full.json").write_text(
        json.dumps(table, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    survived = [
        k
        for k, v in table.items()
        if isinstance(v, dict) and v.get("status") == "SURVIVED"
    ]
    # 旧版只把 SURVIVED 当坏消息 ⇒ anchor-error / denominator-drift 会**绕过**判据，
    # 一条都没被真正执行过的变异也能让最后一行报 ALL_KILLED。改成：不是 KILLED 就是坏。
    not_killed = [
        k
        for k, v in table.items()
        if isinstance(v, dict) and v.get("status") != "KILLED"
    ]
    verdict = (
        "ALL_KILLED"
        if not not_killed
        else ",".join(f"{k}:{table[k]['status']}" for k in not_killed)
    )
    print(
        f"VERDICT={verdict}" + ("" if not survived else f"  SURVIVORS={survived}"),
        flush=True,
    )
    return 0 if not not_killed else 1


if __name__ == "__main__":
    sys.exit(main())
