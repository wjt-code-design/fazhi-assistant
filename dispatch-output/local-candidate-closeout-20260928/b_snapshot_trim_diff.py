"""判定"从一次性发布快照里剔掉 diag/frozen-index-004|005"会不会改变测试的可收集面。

为什么用差分而不是单跑：只看剔过的树"能收集"不能证明"没剔坏"。
同一套解释器、同一份 env、同一个命令，在未剔树与剔过的树上各跑一次 --collect-only，
两侧都成功且完整 nodeid 集合一致，才支持删除不改变收集面；不代表运行通过。

用法：
    <venv python> b_snapshot_trim_diff.py --full <sha> --trim <sha>
"""

from __future__ import annotations

import argparse
import io
import json
import os
import re
import subprocess
import sys
import tarfile
import tempfile
from datetime import datetime
from pathlib import Path

REPO = Path(r"C:/Users/33393/Desktop/ai-legal-helper")
EVIDENCE = REPO / "dispatch-output/local-candidate-closeout-20260928"
PY = Path(
    os.environ.get("B_PROBE_PY")
    or r"C:/Users/33393/AppData/Local/Temp/legal-closeout-20260928/venv/Scripts/python.exe"
)

COLLECTED_RE = re.compile(r"(\d+)\s+tests?\s+collected")
ERROR_LINE_RE = re.compile(r"^ERROR\s+\S+", re.MULTILINE)


def expand(commit: str, dest: Path) -> None:
    proc = subprocess.run(
        ["git", "-C", str(REPO), "archive", "--format=tar", commit],
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        raise SystemExit(
            f"FATAL: git archive {commit} rc={proc.returncode} {proc.stderr[:200]}"
        )
    dest.mkdir(parents=True, exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(proc.stdout)) as tf:
        # 配方抄在册建树器 b_probe_build_tree.py：副本树那套 venv 是 3.11.0，没有 filter= 参数，
        # 所以旧版本走"手工校验同一件事再解压"，而不是静默无过滤解压。
        if sys.version_info >= (3, 12) or (3, 11, 4) <= sys.version_info:
            tf.extractall(str(dest), filter="data")
            return
        for member in tf.getmembers():
            name = member.name.replace("\\", "/")
            if (
                name.startswith("/")
                or ".." in Path(name).parts
                or not (member.isfile() or member.isdir())
            ):
                print(f"FATAL: archive 里有越界成员 {name}，拒绝解压")
                raise SystemExit(2)
        tf.extractall(str(dest))


def env_for(tree: Path, run_dir: Path) -> dict[str, str]:
    env = dict(os.environ)
    env.update(
        {
            "JWT_SECRET": "test-jwt-secret-for-ci-only",
            "LLM_API_KEY": "test-key-not-for-real-calls",
            "LLM_BASE_URL": "https://test.invalid/v1",
            "EMBEDDING_PROVIDER": "local",
            "RERANK_ENABLED": "false",
            "EMBEDDING_QUOTA_TOTAL": "0",
            "RERANK_QUOTA_TOTAL": "0",
            "HF_HUB_OFFLINE": "1",
            "TRANSFORMERS_OFFLINE": "1",
            "LANGCHAIN_TRACING_V2": "false",
            "LANGSMITH_TRACING": "false",
            "DATABASE_URL": "sqlite:///"
            + str(run_dir / "iso-app.db").replace("\\", "/"),
            "QUOTA_DB": str(run_dir / "iso-quota.db"),
        }
    )
    for key in ("CHROMA_PATH", "CHROMA_DB_PATH", "KB_PATH", "PYTHONPATH"):
        env.pop(key, None)
    return env


def collect(tree: Path, run_dir: Path) -> dict[str, object]:
    backend = tree / "backend"
    proc = subprocess.run(
        [
            str(PY),
            "-m",
            "pytest",
            "--collect-only",
            "-q",
            "-p",
            "no:cacheprovider",
        ],
        cwd=str(backend),
        env=env_for(tree, run_dir),
        capture_output=True,
        text=True,
        timeout=1800,
        check=False,
    )
    text = (proc.stdout or "") + "\n" + (proc.stderr or "")
    m = COLLECTED_RE.search(text)
    errors = sorted(set(ERROR_LINE_RE.findall(text)))
    return {
        "rc": proc.returncode,
        "collected": int(m.group(1)) if m else None,
        "errors": errors[:40],
        "error_total": len(errors),
        "nodeids": sorted(
            line.strip()
            for line in proc.stdout.splitlines()
            if "::" in line and ".py::" in line and not line.startswith(" ")
        ),
        "tail": text[-400:],
    }


def size_of(tree: Path) -> float:
    return sum(f.stat().st_size for f in tree.rglob("*") if f.is_file()) / 1048576.0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--full", required=True, help="未剔快照的提交号")
    ap.add_argument("--trim", required=True, help="剔过的快照提交号")
    args = ap.parse_args()

    for ref in (args.full, args.trim):
        probe = subprocess.run(
            ["git", "-C", str(REPO), "cat-file", "-e", f"{ref}^{{commit}}"], check=False
        )
        if probe.returncode != 0:
            print(f"FATAL: 提交 {ref} 不可解析（对象可能已被回收，重建快照后再跑）")
            return 2

    stamp = datetime.now().astimezone().strftime("%Y%m%d-%H%M%S")
    root = Path(tempfile.gettempdir()) / f"b-snapdiff-{stamp}"
    root.mkdir(parents=True, exist_ok=True)
    print(f"解释器={PY}")

    out: dict[str, object] = {
        "stamp": stamp,
        "interpreter": str(PY),
        "full": args.full,
        "trim": args.trim,
    }
    runs: dict[str, dict[str, object]] = {}
    trees: dict[str, Path] = {}
    for label, sha in (("full", args.full), ("trim", args.trim)):
        tree = root / label
        expand(sha, tree)
        trees[label] = tree
        runs[label] = collect(tree, root)
        runs[label]["tree_mb"] = round(size_of(tree), 1)
        print(
            f"[{label}] rc={runs[label]['rc']} collected={runs[label]['collected']} "
            f"错误行={runs[label]['error_total']} 树={runs[label]['tree_mb']}MB"
        )

    same = (
        all(
            r["rc"] == 0
            and r["error_total"] == 0
            and not r["errors"]
            and r["collected"]
            and len(r.get("nodeids", [])) == r["collected"]
            for r in runs.values()
        )
        and runs["full"]["nodeids"] == runs["trim"]["nodeids"]
    )
    verdict = "PASS 差分零变化" if same else "FAIL 收集失败、标识不完整或用例集合不同"
    if runs["full"]["collected"] is None or runs["trim"]["collected"] is None:
        verdict = "FAIL 有一侧没读到 collected 数（别把'没报数'读成'没变化'）"
    out["runs"] = runs
    out["verdict"] = verdict
    print(verdict)
    print(f"体积差={round(runs['full']['tree_mb'] - runs['trim']['tree_mb'], 1)} MB")

    target = EVIDENCE / f"b-snapdiff-{stamp}.json"
    target.write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n"
    )
    print(f"EVIDENCE={target}")
    return 0 if verdict.startswith("PASS") else 1


if __name__ == "__main__":
    sys.exit(main())
