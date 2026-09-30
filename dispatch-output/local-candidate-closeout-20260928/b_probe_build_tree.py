"""B 档探针副本树建树器：从候选 HEAD 的 git archive 建纯发布物树，补齐收集期未入库依赖。

为什么用 archive 而不是复制工作区：候选工作区带着 .env / venv / 真实 chroma_db 的风险，
archive 只含 tracked 文件，天然缺席这三样 —— 这正是「副本树内允许跑全量」的前提。
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tarfile
from datetime import datetime
from pathlib import Path

REPO = Path(r"C:/Users/33393/Desktop/ai-legal-helper")
CAND = Path(r"C:/Users/33393/.codex/worktrees/local-candidate-closeout/ai-legal-helper")
# B_PROBE_EVIDENCE_DIR 只改**读数落点**；REPO/CAND 仍指真实仓库，因为收集期依赖文件从那里读。
EVIDENCE = Path(
    os.environ.get("B_PROBE_EVIDENCE_DIR")
    or "C:/Users/33393/Desktop/ai-legal-helper/dispatch-output/local-candidate-closeout-20260928"
)
# 未入库但收集期被读的文件（历史实测：缺任一都会在 collection 期中断整场，读数退化成 1 条伪用例）
EXTRA_UNTRACKED = [
    "dispatch-output/task1/hidden-cases-v1.json",
    "dispatch-output/task1/hidden-round-protocol-v1.json",
]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def forbidden_hit(path: Path) -> bool:
    """精确匹配，别让 .env.example 冒充 .env（tracked 的示例文件本来就该在树里）。"""
    if path.name == ".env" or path.name in ("app.db", "chroma.sqlite3") or path.name.startswith(".ptmp"):
        return True
    return any(part in ("venv", "chroma_db", "__pycache__") for part in path.parts)


def main() -> int:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    tree = Path(os.environ.get("TEMP", r"C:/Users/33393/AppData/Local/Temp")) / f"b-probe-tree-{stamp}"
    tree.mkdir(parents=True, exist_ok=True)

    head = subprocess.run(
        ["git", "-C", str(CAND), "rev-parse", "HEAD"], capture_output=True, text=True, check=False
    ).stdout.strip()
    status = subprocess.run(
        ["git", "-C", str(CAND), "status", "--porcelain", "-uno"], capture_output=True, text=True, check=False
    ).stdout.strip()
    if not head:
        print("FATAL: 候选 HEAD 解析失败（引用可能被外部进程删除，先跑 restore-candidate-ref.sh）")
        return 2
    if status:
        print(f"FATAL: 候选工作树不干净，archive 无法代表提交树：\n{status[:400]}")
        return 2

    proc = subprocess.run(["git", "-C", str(CAND), "archive", "--format=tar", head], capture_output=True, check=False)
    if proc.returncode != 0:
        print(f"FATAL: git archive rc={proc.returncode} {proc.stderr[:300]}")
        return 2
    with tarfile.open(fileobj=io.BytesIO(proc.stdout)) as tf:
        if sys.version_info >= (3, 12) or (3, 11, 4) <= sys.version_info:
            tf.extractall(str(tree), filter="data")  # 拒绝绝对路径/越界链接
        else:  # 本机 3.11.0 没有 filter 参数，手工校验同一件事
            for member in tf.getmembers():
                name = member.name.replace("\\", "/")
                if name.startswith("/") or ".." in Path(name).parts or not (member.isfile() or member.isdir()):
                    print(f"FATAL: archive 里有越界成员 {name}，拒绝建树")
                    return 5
            tf.extractall(str(tree))

    extracted = [p for p in tree.rglob("*") if p.is_file()]

    for rel in EXTRA_UNTRACKED:
        src = REPO / rel
        if not src.is_file():
            print(f"FATAL: 收集期依赖缺失 {src} —— 补进来再跑，否则读数会退化成伪用例")
            return 3
        dst = tree / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(src), str(dst))
        extracted.append(dst)

    offenders = [str(p.relative_to(tree)) for p in tree.rglob("*") if forbidden_hit(p)]
    req = tree / "backend/requirements.txt"
    req_text = req.read_text(encoding="utf-8") if req.is_file() else ""
    has_pypdf_pin = "pypdf==6.16.1" in req_text
    has_fastapi_pin = "fastapi==0.141.1" in req_text

    report = {
        "tree": str(tree),
        "candidate_head": head,
        "archive_bytes": len(proc.stdout),
        "files": len(extracted),
        "backend_py": len([p for p in extracted if p.suffix == ".py" and "backend" in p.parts]),
        "forbidden_present": offenders,
        "requirements_has_pypdf_pin": has_pypdf_pin,
        "requirements_has_fastapi_pin": has_fastapi_pin,
        "extras_added": EXTRA_UNTRACKED,
        "tree_requirements_sha256": sha256(req) if req.is_file() else "",
    }
    with open(str(EVIDENCE / "b-probe-tree-build.json"), "w", encoding="utf-8", newline="\n") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2, sort_keys=True)

    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    if offenders or not has_pypdf_pin or not has_fastapi_pin:
        print("FATAL: 副本树含禁止对象或 requirements 固定不符，拒绝在此树上出读数")
        return 4
    print(f"\nTREE={tree}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
