"""S0-c 注记的变异跑：每个改动点至少一个变异体，逐条记录"新红的是哪些用例"。

跑法（cwd 任意，需 backend/venv）：
    backend/venv/Scripts/python.exe dispatch-output/s0c-note-20260926/mutate.py

判据（沿用票 C/S6 那套的形状，不另立）：
  · 每条变异必须产出**非空** `newly_red`（红集合 = 变异后红 − 基线红），否则记 `INSENSITIVE`（= 闸零敏感）；
  · 分母 = 三个端点级/登记表文件的 collected 数，跑前跑后必须相同（分母漂移的读数不算杀，票 C r1 的前科）；
  · 跑完必须 `diff` 还原成 SAME 才算这一轮干净。

⚠️ 每条变异都是**真行为变化**（删一个 yield / 删一个条件 / 摘掉锚点）。
   前科：T1 那条判据曾要求删 `[\\s\u3000]` 里的 `\u3000` —— Python `\\s` 本就含 U+3000，那是个恒等变异体。
"""

import json
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
MAIN = BACKEND / "main.py"
HERE = pathlib.Path(__file__).resolve().parent
PY = str(BACKEND / "venv" / "Scripts" / "python.exe")
TARGETS = ["tests/test_time_unverified_note.py", "tests/test_gate_exit_registry.py", "tests/test_stream_exit_law_version_gate.py"]

# 每条变异 = (名称, 期望杀掉它的用例至少有哪些, 原文片段, 替换片段)
MUTANTS = [
    (
        "M1-drop-e17-frame",
        ["test_e8_streaming_answer_carries_the_note", "test_e9_fallback_answer_carries_the_note"],
        '                yield f"data: {json.dumps({\'content\': NOTE_TIME_UNVERIFIED}, ensure_ascii=False)}\\n\\n"  # gate-exit: E17\n',
        "",
    ),
    (
        "M2-drop-e7-inline",
        ["test_e7_light_buffered_answer_carries_the_note_inline"],
        # ⚠️ 变异体必须**语法合法**：第一版 M2 直接把 `answer += ...` 那一行删掉，留下一个只剩注释的
        # if 块 ⇒ IndentationError ⇒ 整套 collected=0。分母漂移的读数不算杀（票 C r1 的同一条规矩），
        # 所以这里改成 `pass`：行为变了（不注记），语法没变。
        # ⚠️ 锚点必须带**行首换行**：`" "*20 + "answer += ..."` 会同时命中 24 空格那一处（E18）
        # ——24 个空格的前 20 个也是空格 ⇒ 计数 2 ⇒ 驱动按"锚点不唯一"拒跑。
        "\n                    answer += NOTE_TIME_UNVERIFIED\n",
        "\n                    pass  # 变异体 M2：E7 不注记\n",
    ),
    (
        "M3-drop-e18-frame",
        ["test_e5_contract_report_answer_carries_the_note"],
        '                        yield f"data: {json.dumps({\'content\': NOTE_TIME_UNVERIFIED}, ensure_ascii=False)}\\n\\n"  # gate-exit: E18\n',
        "",
    ),
    (
        "M4-judgement-ignores-basis",
        ["test_control_no_explicit_basis_produces_no_note", "test_judgement_requires_both_conditions"],
        '    if not pre.get("law_as_of"):\n        return False\n',
        "",
    ),
    (
        "M5-judgement-ignores-unknown",
        ["test_control_verified_evidence_produces_no_note", "test_judgement_requires_both_conditions"],
        '    return any(time_validity_state(s) == "unknown" for s in pre.get("sources") or ())\n',
        "    return True\n",
    ),
    (
        "M6-unanchor-e17",
        ["test_main_py_exits_are_all_registered"],
        '  # gate-exit: E17\n',
        "\n",
    ),
]


def run_suite() -> tuple[set[str], int]:
    """跑一轮，返回 (红集合, 本轮真跑了多少条)。

    分母轴先前错过两次：① 拿 `passed|failed` 之和当 collected（把 skipped 吞了）；
    ② 拿 `passed + skipped` 当分母 —— 一有失败它就**自己缩小**，于是每个变异体的"分母"都不一样。
    现在：真 collected 由 `--collect-only` 量一次作常量，本轮跑了多少 = passed+failed+skipped+errors。
    """
    p = subprocess.run(
        [PY, "-m", "pytest", *TARGETS, "-q", "-p", "no:cacheprovider"],
        cwd=str(BACKEND),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    out = (p.stdout or "") + (p.stderr or "")
    red = {m.group(1) for m in re.finditer(r"^FAILED tests/\S+::(\S+)", out, re.MULTILINE)}
    ran = 0
    for key in ("passed", "failed", "skipped", "error"):
        hit = re.search(rf"(\d+) {key}", out)
        if hit:
            ran += int(hit.group(1))
    return red, ran


def collected_total() -> int:
    """一次 `--collect-only` 拿到真正的 collected 轴（分母常量）。"""
    p = subprocess.run(
        [PY, "-m", "pytest", *TARGETS, "--collect-only", "-q", "-p", "no:cacheprovider"],
        cwd=str(BACKEND),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    out = (p.stdout or "") + (p.stderr or "")
    # `-q --collect-only` 的收尾行是 "N tests collected in Xs"，不是 verbose 的 "collected N items"
    hit = re.search(r"(\d+) tests? collected", out) or re.search(r"collected (\d+) items", out)
    if not hit:
        raise SystemExit("拿不到 collected 数 ⇒ 仪器坏在这里，别往下跑")
    return int(hit.group(1))


def main() -> int:
    only = set(sys.argv[1:])  # 传名字 ⇒ 只跑这些并并入既有产物（不传 ⇒ 全跑、覆盖）
    out_path = HERE / "mutation-verdicts.json"
    orig = MAIN.read_bytes()
    base_red, _ = run_suite()
    den0 = collected_total()
    verdicts = [{"mutant": "baseline", "newly_red": sorted(base_red), "collected": den0}]
    for name, want, old, new in MUTANTS:
        if only and name not in only:
            continue
        src = orig.decode("utf-8")
        if src.count(old) != 1:
            verdicts.append({"mutant": name, "error": f"锚点命中 {src.count(old)} 次（要求恰好 1 次）⇒ 该变异体不成立"})
            continue
        MAIN.write_bytes(src.replace(old, new, 1).encode("utf-8"))
        try:
            red, den = run_suite()
        finally:
            MAIN.write_bytes(orig)
        newly = sorted(red - base_red)
        restored = MAIN.read_bytes() == orig
        verdicts.append(
            {
                "mutant": name,
                "newly_red": newly,
                "collected": den,
                "denominator_drift": den != den0,
                "restored": restored,
                "expected_hit": sorted(set(want) & set(newly)),
                "killed": bool(newly) and den == den0 and restored,
            }
        )
        print(f"{name}: newly_red={len(newly)} collected={den} restored={restored}", flush=True)
    assert MAIN.read_bytes() == orig, "main.py 未还原 ⇒ 本轮结果作废"
    if only and out_path.exists():
        kept = [v for v in json.loads(out_path.read_bytes().decode("utf-8")) if v["mutant"] not in only and v["mutant"] != "baseline"]
        order = {"baseline": 0, **{m[0]: i + 1 for i, m in enumerate(MUTANTS)}}
        verdicts = sorted(kept + verdicts, key=lambda v: order.get(v["mutant"], 99))
    out_path.write_bytes(json.dumps(verdicts, ensure_ascii=False, indent=1).encode("utf-8"))
    print("wrote", out_path, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
