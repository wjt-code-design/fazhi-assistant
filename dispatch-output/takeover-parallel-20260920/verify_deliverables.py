"""并行任务的结构性验收闸（只读；不跑 pytest）。

用法：
    backend/venv/Scripts/python.exe dispatch-output/takeover-parallel-20260920/verify_deliverables.py

它做四件事：
  ① 逐卡检查必需产物是否落地（支持 run-*.stdout.txt 这类通配 + 计数下限）；
  ② JSON 产物是否可解析、stdout 是否非空且含 pytest 计数行；
  ③ T1 的红绿矩阵跑次是否 >= 5；
  ④ **越界写哨兵**：五个单点资源的 sha256 是否仍与 baseline.json 一致，
     以及 `git status --porcelain backend` 里有没有未提交改动（backend/**/*.py 被改 = 报警）。

它**不判语义对错**（矩阵格数对不对、根因成立不成立，仍要人工复跑）。stdout 一律 ASCII，
中文细节写进 verify-<ts>.json —— 本机终端会把中文显示成乱码，别用肉眼读终端判断内容。
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
LEDGER = HERE / "task-ledger.json"
BASELINE = HERE / "baseline.json"

PYTEST_COUNT_RE = re.compile(r"\d+ (?:passed|failed|error|skipped|deselected)")


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def write_dir_of(card: dict) -> Path | None:
    """写集第一条里的目录（列表项可能带括号备注，只取前面的路径段）。"""
    if not card.get("write_set"):
        return None
    raw = card["write_set"][0]
    m = re.match(r"^([A-Za-z0-9_\-./\\]+)", raw)
    if not m:
        return None
    p = Path(m.group(1).replace("/", "\\"))
    return p if p.is_absolute() else REPO / p


def check_artifacts(card: dict) -> list[dict]:
    out: list[dict] = []
    write_dir = write_dir_of(card)
    if write_dir is not None and not write_dir.is_absolute():
        write_dir = REPO / write_dir
    for art in card.get("required_artifacts", []):
        pat = art
        minimum = 1
        m = re.search(r"\(N>=(\d+)\)", art)
        if m:
            minimum = int(m.group(1))
            pat = art[: m.start()].strip()
        if ".." in pat:  # 形如 run-1..N.stdout.txt -> run-*.stdout.txt
            pat = re.sub(r"\d+\.\.[A-Za-z]*", "*", pat)
        if write_dir is None or not write_dir.exists():
            out.append(
                {"artifact": art, "status": "MISSING_DIR", "found": 0, "need": minimum}
            )
            continue
        hits = sorted(p for p in write_dir.glob(pat) if p.is_file())
        entry = {
            "artifact": art,
            "status": "OK",
            "found": len(hits),
            "need": minimum,
            "files": [str(p) for p in hits],
        }
        if len(hits) < minimum:
            entry["status"] = "MISSING"
        elif pat.endswith(".json") and hits:
            bad = []
            for p in hits:
                try:
                    json.loads(p.read_text(encoding="utf-8"))
                except Exception as exc:  # noqa: BLE001 - 只报到报告里
                    bad.append(f"{p.name}: {exc}")
            if bad:
                entry["status"] = "BAD_JSON"
                entry["detail"] = bad
        out.append(entry)

    # stdout 类产物：非空 + 含计数行
    if write_dir is not None and write_dir.exists():
        for p in sorted(write_dir.glob("*.stdout.txt")):
            txt = p.read_text(encoding="utf-8", errors="replace")
            if not txt.strip():
                out.append(
                    {"artifact": p.name, "status": "EMPTY", "found": 0, "need": 1}
                )
            elif not PYTEST_COUNT_RE.search(txt):
                out.append(
                    {
                        "artifact": p.name,
                        "status": "NO_COUNT_LINE",
                        "found": 0,
                        "need": 1,
                    }
                )
    return out


def check_matrix() -> dict:
    p = REPO / "dispatch-output" / "t1-flaky-20260920" / "matrix.json"
    if not p.is_file():
        return {"status": "MISSING", "runs": 0}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        return {"status": "BAD_JSON", "detail": str(exc), "runs": 0}
    runs = 0
    if isinstance(data, dict):
        for key in ("runs", "run_count", "n_runs", "rounds"):
            if isinstance(data.get(key), int):
                runs = data[key]
                break
        if not runs:
            for v in data.values():
                if isinstance(v, list) and len(v) >= 5:
                    runs = len(v)
                    break
    return {"status": "OK" if runs >= 5 else "TOO_FEW_RUNS", "runs": runs}


def sentinel() -> dict:
    base = json.loads(BASELINE.read_text(encoding="utf-8"))
    alarm: list[dict] = []
    recorded: list[dict] = []
    for rel, info in base["single_writer_resources"].items():
        p = REPO / rel.replace("/", "\\")
        bucket = alarm if info.get("drift_alarm") else recorded
        if not p.is_file():
            bucket.append(
                {"path": rel, "why": "MISSING_FILE", "owner": info.get("owner")}
            )
            continue
        got = sha256_of(p)
        if got != info["sha256"]:
            bucket.append(
                {
                    "path": rel,
                    "why": "SHA_DRIFT",
                    "owner": info.get("owner"),
                    "baseline": info["sha256"],
                    "now": got,
                }
            )
    # backend 下在看**已跟踪**文件的改动：未跟踪项是各卡自己的产物，不是越界写
    try:
        proc = subprocess.run(
            ["git", "status", "--porcelain", "--", "backend"],
            cwd=REPO,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        lines = [ln for ln in proc.stdout.splitlines() if ln.strip()]
    except Exception as exc:  # noqa: BLE001
        lines = [f"<git 读取失败: {exc}>"]
    return {
        "alarm": alarm,
        "recorded_external_drift": recorded,
        "backend_dirty_tracked": [ln for ln in lines if not ln.startswith("??")],
        "backend_untracked": [ln for ln in lines if ln.startswith("??")],
    }


def main() -> int:
    ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
    rows = []
    for card in ledger["tasks"]:
        arts = check_artifacts(card)
        bad = [a for a in arts if a["status"] not in ("OK",)]
        rows.append(
            {
                "id": card["id"],
                "wave": card["wave"],
                "priority": card["priority"],
                "artifacts_ok": len(arts) - len(bad),
                "artifacts_total": len(arts),
                "problems": bad,
            }
        )
    matrix = check_matrix()
    sent = sentinel()

    print("task wave prio artifacts problem_count")
    for r in rows:
        print(
            f"{r['id']:>4} {r['wave']:>4} {r['priority']:>3} "
            f"{r['artifacts_ok']}/{r['artifacts_total']} {len(r['problems'])}"
        )
    print(f"T1 matrix: {matrix['status']} runs={matrix['runs']}")
    print(
        f"sentinel: alarm={len(sent['alarm'])} "
        f"external_drift_recorded={len(sent['recorded_external_drift'])} "
        f"backend_dirty_tracked={len(sent['backend_dirty_tracked'])} "
        f"backend_untracked={len(sent['backend_untracked'])}"
    )
    done = sum(1 for r in rows if r["artifacts_total"] and not r["problems"])
    print(f"cards_with_all_artifacts: {done}/{len(rows)}")

    ts = time.strftime("%Y%m%d-%H%M%S")
    out = HERE / f"verify-{ts}.json"
    out.write_text(
        json.dumps(
            {
                "verified_at": ts,
                "cards": rows,
                "t1_matrix": matrix,
                "sentinel": sent,
                "note": "结构性验收：只判产物落地/可解析/计数行。语义正确性仍需人工复跑。",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"verify json -> {out.name}")
    # 退出码：产物齐 + 无本波越界写 才 0（票 I 的漂移只记录，不阻断）
    ok = done == len(rows) and not sent["alarm"]
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
