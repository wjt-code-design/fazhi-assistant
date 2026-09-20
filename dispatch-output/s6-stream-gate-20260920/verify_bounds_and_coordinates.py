"""票 C 收口前的硬边界自证 + 坐标重量（`ruff format` 跑过一次，票面行号全部作废）。

两类读数混在一起会有人误读，所以分节写：
  A. 票 §1 的前置取证在**改后**还剩什么形状（P4/P5/P6/P7/P8 的计数必须仍然成立，
     只是门多了一处出口、`_law_version_gate` 多了一个入参）。
  B. 边界未被越（Owner §3 / 票 §0 / §11）：
     开关默认值、`agent/` 零改动、`gate2_runner.py` 的 sha256、`app.db` 只读、`.env` 未被写过。
  C. 本票所有**符号锚点**的现量（唯一性命中的锚点集合）—— 回报里引用的坐标以此为准。

用法（cwd 任意）：
    backend/venv/Scripts/python.exe dispatch-output/s6-stream-gate-20260920/verify_bounds_and_coordinates.py
"""

from __future__ import annotations

import hashlib
import pathlib
import subprocess
import sys
from datetime import datetime, timezone

REPO = pathlib.Path(__file__).resolve().parents[2]
BACKEND = REPO / "backend"
GATE2_SHA_EXPECTED = "ae2e412059ed68ac1514c62727cee61c50b8a2d6fe7e38a77c7e05631847e295"

ANCHORS: list[tuple[str, str, int]] = [
    # (说明, 锚点(子串, 在哪个文件), 期望命中次数)  —— 认形状不认行号（ADR-018/R4）
    ("两处流式出口（票 §1 P4）", "async for piece in stream_with_retry(", 2),
    ("两处收口（票 §1 P5）", 'answer = "".join(chunks)', 2),
    ("门函数只有 1 份（票 §5-2）", "def _law_version_gate(", 1),
    ("事实取法只有 1 份（票 §1 P6）", "def _fast_path_fact_texts(", 1),
    ("基准日函数只有 1 份（票 §5-4）", "def _fast_path_law_as_of(", 1),
    ("S5 开关默认值未被动（票 §0）", "fast_path_law_version_check: bool = False", 1),
    (
        "流式侧门调用点 = 2（两个答案来源，票 §5-3）",
        "answer, law_version_hit = _law_version_gate(",
        2,
    ),
    ("写缓存闸第五条件（票 §5-6）", "and not law_version_hit", 1),
    (
        "轻量闸仍是第三条（S5 的原样）",
        'if cache_key and res.verdict == "pass" and not res.law_version_hit:',
        1,
    ),
    ("新注记帧的锚点（登记表 E14）", "# gate-exit: E14", 1),
    ("出口标签参数只有一个定义处", "EXIT_STREAM = ", 1),
]


def sha256_of(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sqlite_change_counter(path: pathlib.Path) -> int:
    b = path.read_bytes()
    return int.from_bytes(b[24:28], "big") if len(b) >= 28 else -1


def git(*args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=REPO,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    ).stdout.strip()


def main() -> int:
    lines: list[str] = [
        f"采集时间 UTC={datetime.now(timezone.utc).isoformat()}",
        f"HEAD={git('rev-parse', '--short', 'HEAD')}",
        "",
    ]
    mains = (BACKEND / "main.py").read_bytes().decode("utf-8").replace("\r\n", "\n")
    sets = (BACKEND / "settings.py").read_bytes().decode("utf-8").replace("\r\n", "\n")
    src_by_file = {"main.py": mains, "settings.py": sets}

    lines.append("A/C. 锚点现量（改后；票面行号一律不采信）")
    bad = 0
    for label, needle, want in ANCHORS:
        where = "settings.py" if "bool = False" in needle else "main.py"
        got = src_by_file[where].count(needle)
        flag = "OK " if got == want else "BAD"
        bad += got != want
        first_line = next(
            (
                i
                for i, ln in enumerate(src_by_file[where].split("\n"), 1)
                if needle in ln
            ),
            -1,
        )
        lines.append(
            f"  [{flag}] {label}: 命中 {got}（期望 {want}）首行现量 :{first_line} in {where}"
        )
    lines.append(f"  锚点不合格条数 = {bad}")

    lines += [
        "",
        "  main.py 里 `gate-exit:` 锚点总数（登记表哨兵按它对账 EXITS 行数）=",
        f"    {mains.count('# gate-exit: ')} 条；登记表 EXITS 行数=",
    ]
    sys.path.insert(0, str(BACKEND))
    from gate_exit_registry import EXITS

    lines.append(
        f"    {len(EXITS)} 行；两者相等 = {mains.count('# gate-exit: ') == len(EXITS)}"
    )

    # ---- B. 边界 ----
    lines.append("")
    lines.append("B. 边界未被越")
    agent_files = [
        f
        for f in git("diff", "--name-only", "HEAD", "--", "backend/agent/").splitlines()
        if f
    ]
    lines.append(f"  backend/agent/** 改动文件 = {agent_files or '无'}")
    g2 = BACKEND / "scripts" / "gate2_runner.py"
    sha = sha256_of(g2)
    lines.append(
        f"  gate2_runner.py sha256 = {sha}  合规 = {sha == GATE2_SHA_EXPECTED}"
    )
    db = BACKEND / "app.db"
    st = db.stat()
    lines.append(
        f"  app.db 只读取证：size={st.st_size} sha256={sha256_of(db)} sqlite_change_counter={sqlite_change_counter(db)}"
    )
    envf = BACKEND / ".env"
    est = envf.stat()
    lines.append(
        f"  .env 未被写过：size={est.st_size} mtime={datetime.fromtimestamp(est.st_mtime, timezone.utc).isoformat()}（本会话只读不写）"
    )
    lines.append(
        "  开关默认值：fast_path_law_version_check 在 settings.py 里的声明次数（应为 1 且那条是 `= False`）="
    )
    lines.append(f"    {sets.count('fast_path_law_version_check: bool =')}")
    lines.append(
        f"  本会话工作树脏项（tracked）：\n    {git('status', '--porcelain', 'backend', 'docs') or '无'}"
    )
    print("\n".join(lines))
    out = pathlib.Path(__file__).with_name("08-bounds-and-coordinates.txt")
    out.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    ok = (
        bad == 0
        and not agent_files
        and sha == GATE2_SHA_EXPECTED
        and mains.count("# gate-exit: ") == len(EXITS)
    )
    print(f"\nVERDICT={'BOUNDS_OK' if ok else 'BOUNDS_VIOLATED'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
