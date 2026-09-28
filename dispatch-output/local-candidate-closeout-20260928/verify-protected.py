# -*- coding: utf-8 -*-
"""Re-verify the A-baseline protected-file fingerprint (size/mtime/sha256)."""
import hashlib
import json
import sys
from pathlib import Path

BASELINE = Path(
    r"C:\Users\33393\Desktop\ai-legal-helper\dispatch-output"
    r"\local-candidate-closeout-20260928\protected-before.json"
)
OUT = Path(
    r"C:\Users\33393\Desktop\ai-legal-helper\dispatch-output"
    r"\local-candidate-closeout-20260928\protected-postcommit-check.log"
)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def main() -> int:
    entries = json.loads(BASELINE.read_text(encoding="utf-8"))
    lines = [f"baseline: {BASELINE.name} entries={len(entries)}"]
    same = 0
    diffs = []
    missing = []
    for e in entries:
        p = Path(e["path"])
        if not p.is_file():
            missing.append(e["path"])
            continue
        st = p.stat()
        cur_size = st.st_size
        cur_mtime = st.st_mtime
        base_size = e["bytes"]
        base_sha = e["sha256"]
        cur_sha = sha256(p)
        if cur_size == base_size and cur_sha == base_sha:
            same += 1
        else:
            diffs.append(
                {
                    "path": e["path"],
                    "size_base": base_size,
                    "size_now": cur_size,
                    "sha_base": base_sha,
                    "sha_now": cur_sha,
                    "mtime_now_epoch": round(cur_mtime, 3),
                    "mtime_base_utc": e.get("modified_utc"),
                }
            )
    lines.append(f"unchanged(size+sha256): {same}")
    lines.append(f"missing: {len(missing)}")
    for m in missing:
        lines.append(f"  MISSING {m}")
    lines.append(f"changed: {len(diffs)}")
    for d in diffs:
        lines.append("  CHANGED " + json.dumps(d, ensure_ascii=False))
    text = "\n".join(lines) + "\n"
    OUT.write_text(text, encoding="utf-8", newline="")
    print(text)
    return 0 if (not diffs and not missing) else 1


if __name__ == "__main__":
    sys.exit(main())
