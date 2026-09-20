"""票 H 变异执行器（**逐变异一次调用**版，R2）。

为什么要有 R2（R1 的读数为什么不能用）：
R1 用 `run_mutations_full.py` 的原编排，四个跑次共用同一个 `out_dir` ⇒ `--basetemp=<out>/bt`。
pytest 每次启动都会**整树删掉**已存在的 `--basetemp`。第一跑（baseline）时 `bt` 是空的 ⇒ 干净
（实测 `tests=1383 failures=0 errors=0`）；从那之后 `bt` 里躺着上一轮 1383 个用例的临时目录，
下一跑启动时那条**批量删除**撞上了 WorkBuddy 沙箱的 safe-delete 批量守卫
（`sitecustomize.py` 的 `_exit_bulk_guard_control` → `raise SystemExit(1)`）⇒ M1/M2/M3
**各报 225 条 setup error，且数字逐字相同**。判据口径要求"不是 KILLED 就是坏消息"，
所以 R1 的 `denominator-drift` 是真的坏消息，不能当噪声忽略。

R2 只改一处：**每个跑次用自己唯一的 `out_dir`**（⇒ 唯一 basetemp，不再整树删别人的目录），
其余判定逻辑（`run_suite` / `suite_stats` / `failed_set` / 分母比对 / anchor 唯一性）**一个字节不改**，
直接复用 `run_mutations_full` 的函数 ⇒ 不产生第二份判据实现（`[PL#13]`）。
baseline 只在 R2 的根目录里跑一次，之后的每个变异复用它做差分。

用法（一次一个变异，别串成一条命令——串起来又会把删量累积到同一个 tool_call 上）：
    py .../run_mutations_ticket_h2.py <副本树> <R2 根目录> <变异名|baseline> [基线 xml 出处]
"""

from __future__ import annotations

import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
sys.path.insert(
    0, str(pathlib.Path(__file__).resolve().parents[1] / "s5-followup-20260920")
)

import run_mutations_full as rmf

rmf.PYTEST_EXTRA = ["-m", "not slow"]

MUTANTS: dict[str, tuple[str, str]] = {
    "H-M1_write_gate_blind_to_bad": (
        "if cache_key and not bad and not degraded:",
        "if cache_key and not degraded:",
    ),
    "H-M2_write_gate_blind_to_degraded": (
        "if cache_key and not bad and not degraded:",
        "if cache_key and not bad:",
    ),
    "H-M3_degraded_note_not_emitted": (
        "                    if degraded:\n                        # 与流式出口同族的",
        "                    if degraded and False:\n                        # 与流式出口同族的",
    ),
}


def main() -> int:
    if len(sys.argv) not in (3, 4, 5):
        print(__doc__)
        return 2
    tree = pathlib.Path(sys.argv[1]).resolve()
    root = pathlib.Path(sys.argv[2]).resolve()
    tag = sys.argv[3]
    # 基线 xml 可以从 R1 的干净跑次复用（同一棵树、同一套选择器 ⇒ 差分基线等价）。
    baseline_src = pathlib.Path(sys.argv[4]).resolve() if len(sys.argv) == 5 else None
    out_dir = root / tag
    out_dir.mkdir(parents=True, exist_ok=True)

    # ---- 基线：R2 根目录只跑一次；之后每个变异直接读它的 junit ----
    root_baseline_xml = root / "full-baseline.xml"
    if tag == "baseline":
        rmf.run_suite(tree, out_dir, "baseline", sys.executable)
        xml = out_dir / "full-baseline.xml"
        btests, bfail, berr = rmf.suite_stats(xml)
        print(
            f"baseline 分母 tests={btests} failures={bfail} errors={berr}", flush=True
        )
        return 0 if (btests > 0 and berr == 0) else 2
    if not root_baseline_xml.exists():
        if baseline_src is None or not baseline_src.exists():
            print(
                f"缺基线 junit：{root_baseline_xml}（先跑 <root>/baseline，或用第 4 个参数给出处）"
            )
            return 2
        root_baseline_xml.write_bytes(baseline_src.read_bytes())
    btests, bfail, berr = rmf.suite_stats(root_baseline_xml)
    baseline = rmf.failed_set(root_baseline_xml)
    print(
        f"baseline(复用) 分母 tests={btests} failures={bfail} errors={berr}", flush=True
    )
    if btests <= 0 or berr > 0:
        print("VERDICT=RUN_VOID（基线分母不健全）", flush=True)
        return 2

    entry = MUTANTS[tag]
    # 变异目标文件：默认 `backend/main.py`（票 H/J 全是它）；三元组首元素可指定别的相对路径。
    # ⚠️ 为什么要这个：共用执行器 `run_mutations_full.main()` 只读写 `main.py`，
    # 票 I 有两个变异的锚点在 `backend/retrieval.py` ⇒ 会报 `ANCHOR-NOT-UNIQUE count=0`
    # **看起来像 SURVIVED，其实是"根本没执行"**（判据要求"不是 KILLED 就是坏消息"，
    # 所以这种读数是坏消息，必须修仪器重跑，不能记成存活）。
    if len(entry) == 3:
        rel, old, new = entry
    else:
        rel, (old, new) = "backend/main.py", entry
    target = tree / rel
    orig, nl = rmf.read_main(target)
    if orig.count(old) != 1:
        print(f"{tag}: ANCHOR-NOT-UNIQUE({rel}) count={orig.count(old)}", flush=True)
        return 1
    rmf.write_main(target, orig.replace(old, new, 1), nl)
    try:
        mutant = rmf.run_suite(tree, out_dir, tag, sys.executable)
    finally:
        rmf.write_main(target, orig, nl)
    restored, _ = rmf.read_main(target)
    mtests, mfail, merr = rmf.suite_stats(out_dir / f"full-{tag}.xml")
    table = {
        "tag": tag,
        "baseline_tests": btests,
        "mutant_tests": mtests,
        "mutant_failures": mfail,
        "mutant_errors": merr,
        "target_file": rel,
        # 字段名**改准**：原来叫 `main_py_restored_byte_exact`，但目标文件现在可能是
        # `backend/retrieval.py` 等任一文件 ⇒ 那个名字会对非 main.py 的变异说谎。
        # （票 H/J 的 verdict.json 是历史产物，仍用旧键名，不追改。）
        "target_restored_byte_exact": restored == orig,
    }
    if mtests != btests or merr > 0:
        table["status"] = "denominator-drift"
    else:
        killed = sorted(mutant - baseline)
        table["status"] = "KILLED" if killed else "SURVIVED"
        table["newly_red"] = killed
        table["newly_green"] = sorted(baseline - mutant)
        table["mutant_failed"] = len(mutant)
    (out_dir / "verdict.json").write_text(
        json.dumps(table, ensure_ascii=False, indent=1), encoding="utf-8", newline=""
    )
    print(json.dumps(table, ensure_ascii=False, indent=1), flush=True)
    return 0 if table["status"] == "KILLED" else 1


if __name__ == "__main__":
    sys.exit(main())
