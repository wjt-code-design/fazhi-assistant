"""独立复核 T3 的两个关键读数（不复用 T3 的脚本，避免同源复算）。

只读 SQLite 头 100 字节：magic(0-15) / page_size(16-17) / write_format(18) / read_format(19) /
change_counter(24-27, 大端) / version_valid_for(92-95)。不开连接、不写字节。

用法：backend/venv/Scripts/python.exe probe_cc_independent.py
"""

from __future__ import annotations

import struct
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
TARGETS = (
    "backend/app.db",
    "backend/data/app.db",
    "backend/data/quota_used.sqlite",
)


def main() -> int:
    print(f"repo={REPO}")
    for rel in TARGETS:
        p = REPO / rel.replace("/", "\\")
        if not p.is_file():
            print(f"{rel} MISSING")
            continue
        with open(p, "rb") as fh:
            head = fh.read(100)
        st = p.stat()
        magic = head[:16].rstrip(b"\x00").decode("ascii", "replace")
        page_size = struct.unpack(">H", head[16:18])[0]
        write_format = head[18]
        read_format = head[19]
        cc = struct.unpack(">I", head[24:28])[0]
        vvf = struct.unpack(">I", head[92:96])[0]
        print(
            f"{rel}\n"
            f"  magic={magic!r} page_size={page_size} write_format={write_format} "
            f"read_format={read_format}\n"
            f"  change_counter={cc} version_valid_for={vvf} header_synced={cc == vvf}\n"
            f"  size={st.st_size} mtime={st.st_mtime:.3f}"
        )
    print("mode: read-only header bytes + os.stat; no sqlite3 connection, no writes.")
    print(
        "cc semantics: non-WAL (write_format=1) => every committed txn increments cc."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
