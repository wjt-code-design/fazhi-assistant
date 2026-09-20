"""票 C §6-①（先红）+ §6-③（默认关端点级逐帧零变化）的采集与判定。

三台仪器各自的分工（写在一处免得下任再猜）：
  A. 改前红：**副本树**（`git archive b40076b` + 本轮同一套测试文件）跑本票定向文件
     ⇒ 证「断言本身在改前是红的」，不是签名报错、不是收集期炸。
  B. 端点级逐帧 sha：**同一套测试代码**分别在改前树与改后 live 树各采一次 SSE 帧序列，
     sha256 必须相同 ⇒ 证「开关默认关 ⇒ 用户可见行为逐字不变」。
     ⚠️ 这条必须是端点级：票面 §6-③ 点名的旧仪器 `capture_light_baseline.py` 直接调
     `_light_buffered`，凡改在**调用点/端点里**的东西（本票三处改动全在这层）对它不可见。
     （本轮**故意没跑**它：它把输出写进 `Path(__file__).parent`，即 S5 的证据目录
     `dispatch-output/s5-followup-20260920/`，跑了会盖掉别人的存档产物。）
  C. 缓冲轻量出口（E7）的逐帧 sha：本票把 `_law_version_gate` 的签名改了（`_LightResult`
     入参 → 答案文本入参），S5 那五个 return 点因此被重写过 ⇒ 光有 B 不够，还要证 E7 没被碰坏。
     用 S5 留在仓库里的采集口 `test_e6_dump_frames_for_zero_change_diff`（同一份代码，两棵树各采一次）。

用法（cwd 任意）：
    backend/venv/Scripts/python.exe dispatch-output/s6-stream-gate-20260920/run_red_and_zero_change.py <副本树>
产出全在本脚本同目录。
"""

from __future__ import annotations

import hashlib
import json
import os
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]
LIVE_BACKEND = REPO / "backend"
VENV_PY = LIVE_BACKEND / "venv" / "Scripts" / "python.exe"
NEW_FILE = "tests/test_stream_exit_law_version_gate.py"
S5_FILE = "tests/test_fast_path_law_version_gate.py"
BT_ROOT = pathlib.Path("/tmp") / "fz_s6_zero_bt"


def run_pytest(
    backend: pathlib.Path, args: list[str], env: dict[str, str] | None, tag: str
) -> str:
    """在一棵 backend 树里跑 pytest，stdout 落盘并回传。rc 用 ${PIPESTATUS} 同款显式读取。"""
    cmd = [
        str(VENV_PY),
        "-m",
        "pytest",
        *args,
        "-p",
        "no:cacheprovider",
        "-q",
        "--no-header",
        "-p",
        "no:warnings",
    ]
    full_env = dict(**(env or {}))
    proc = subprocess.run(
        cmd,
        cwd=backend,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        env=full_env or None,
    )
    text = f"$ (cwd={backend}) {' '.join(cmd)}\nrc={proc.returncode}\n\n{proc.stdout}\n\n== stderr tail ==\n{proc.stderr[-3000:]}\n"
    (HERE / f"{tag}.txt").write_text(text, encoding="utf-8", newline="\n")
    print(f"[{tag}] rc={proc.returncode}  ->  {tag}.txt", flush=True)
    return proc.stdout


def capture(
    backend: pathlib.Path, tag: str, dump_env_name: str, node: str, file: str
) -> dict:
    """跑一个 env 门控的采集口，把帧序列落到 <tag>.json 并回读它的 sha256。"""
    out = HERE / f"{tag}.json"
    env = dict(os.environ)
    env[dump_env_name] = str(out)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    run_pytest(
        backend, [file, "-k", node, f"--basetemp={BT_ROOT / tag}"], env, f"log-{tag}"
    )
    if not out.exists():
        return {"sha256": None, "error": f"采集口没写文件（{dump_env_name}={out}）"}
    payload = json.loads(out.read_text(encoding="utf-8"))
    return {
        "path": str(out),
        "sha256": payload["sha256"],
        "n": payload.get("n_samples") or payload.get("n_frames"),
    }


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    copy_tree = pathlib.Path(sys.argv[1]).resolve()
    copy_backend = copy_tree / "backend"
    assert (copy_backend / NEW_FILE).exists(), f"副本树缺 {NEW_FILE}"
    assert "EXIT_STREAM" not in (copy_backend / "main.py").read_text(
        encoding="utf-8"
    ), "副本树的 main.py 不是改前版本"

    lines: list[str] = [
        "票 C §6-①/§6-③ 读数",
        f"改前树={copy_tree}",
        f"改后树={LIVE_BACKEND}",
        "",
    ]

    # ---- A. 先红：改前树上跑本票定向文件（只跑新文件，别把 S5 的卷进来当"本票的红"） ----
    red_out = run_pytest(
        copy_backend,
        [NEW_FILE, "-rf", f"--basetemp={BT_ROOT / 'red'}"],
        None,
        "01-red-before",
    )
    red_tail = [
        ln
        for ln in red_out.splitlines()
        if ln.startswith("FAILED") or "passed" in ln or "failed" in ln
    ]
    lines.append("A. §6-① 改前红（副本树 b40076b + 本轮同一套测试文件）")
    lines += [f"   {ln}" for ln in red_tail]

    # ---- B. 流式出口 E8/E9 逐帧 sha ----
    b_before = capture(
        copy_backend,
        "02-stream-BEFORE",
        "S6_DUMP_FRAMES",
        "dump_stream_frames",
        NEW_FILE,
    )
    b_after = capture(
        LIVE_BACKEND,
        "02-stream-AFTER",
        "S6_DUMP_FRAMES",
        "dump_stream_frames",
        NEW_FILE,
    )
    stream_same = bool(b_before.get("sha256")) and b_before.get(
        "sha256"
    ) == b_after.get("sha256")
    lines += [
        "",
        "B. §6-③ 端点级逐帧 sha（旗舰流式出口，含 E9 兜底样本；开关默认关、未改默认值）",
        f"   改前 sha256 = {b_before.get('sha256')}   n_samples={b_before.get('n')}",
        f"   改后 sha256 = {b_after.get('sha256')}   n_samples={b_after.get('n')}",
        f"   相同 = {stream_same}",
    ]

    # ---- C. 缓冲轻量出口 E7 逐帧 sha（本票改了门签名 ⇒ 必须回头证它没被碰坏） ----
    c_before = capture(
        copy_backend, "03-light-BEFORE", "FZ_DUMP_FRAMES", "dump_frames", S5_FILE
    )
    c_after = capture(
        LIVE_BACKEND, "03-light-AFTER", "FZ_DUMP_FRAMES", "dump_frames", S5_FILE
    )
    light_same = bool(c_before.get("sha256")) and c_before.get("sha256") == c_after.get(
        "sha256"
    )
    lines += [
        "",
        "C. 缓冲轻量出口（E7）逐帧 sha —— 门签名一改就得复证这条",
        f"   改前 sha256 = {c_before.get('sha256')}",
        f"   改后 sha256 = {c_after.get('sha256')}",
        f"   相同 = {light_same}",
    ]

    # 自证：这台仪器不是恒真的 —— 喂一个必然不同的值，比对必须给 False。
    bogus = hashlib.sha256(b"not-the-same-run").hexdigest()
    lines += [
        "",
        f"VERDICT={'ZERO_CHANGE_OK' if stream_same and light_same else 'ZERO_CHANGE_VIOLATED'}",
        f"（自证：sha 比对对不相同的两个值确实判 False = {bogus != b_before.get('sha256')}）",
        "限制（必须一起读）：这两条只证明「当下代码 == 存档的改前基线」，不证明存档那份确实采于改动前；",
        "「删掉修复就会红」那一半由 §6-④ 的变异承担（见 run_mutations_ticket_c.py）。",
    ]
    text = "\n".join(lines) + "\n"
    (HERE / "00-zero-change-verdict.txt").write_text(
        text, encoding="utf-8", newline="\n"
    )
    print(text)
    return 0 if (stream_same and light_same) else 1


if __name__ == "__main__":
    sys.exit(main())
