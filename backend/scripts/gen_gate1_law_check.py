"""Gate 1 法条存在性核验（只读）：对任务书 §5.1 的 10 个待核标识在 legal_provisions_cos 逐项定位。

- 条号格式为中文大写数字（如"第三十六条"），标识"劳动法:36"→source=劳动法, article=第三十六条。
- 输出 evidence id（chroma id）以支撑"稳定 evidence ID 定位"（任务书 §5/§6.9）。
输出：release-evidence/... 或 docs 下（见 --out）——本脚本不写任何业务代码。

用法：python scripts/gen_gate1_law_check.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

TARGETS = [
    # 任务书 §5.1 显式待核（10）
    ("劳动法", 36),
    ("劳动法", 44),
    ("劳动合同法", 10),
    ("劳动合同法", 40),
    ("劳动合同法", 47),
    ("劳动合同法", 82),
    ("民法典", 195),
    ("民法典", 497),
    ("民法典", 686),
    ("民法典", 695),
    # 追加：各题其余必需依据候选（§7 各 C0x 列出的必需依据）
    ("劳动合同法", 43),
    ("劳动合同法", 87),
    ("民法典", 586),
    ("民法典", 587),
    ("民法典", 588),
    ("民法典", 577),
    ("民法典", 722),
    ("民法典", 509),
    ("民法典", 543),
    ("民法典", 188),
    ("民法典", 675),
    ("民法典", 692),
    ("民法典", 693),
    ("民法典", 496),
    ("消费者权益保护法", 26),
    ("刑法", 266),
    # C02 时效争点候选：劳动仲裁时效（任务书"时效依据按实际收录确认"）
    ("劳动争议调解仲裁法", 27),
]

_UNITS = ["", "十", "百", "千"]


def _zh(num: int) -> str:
    if num == 0:
        return "零"
    s = str(num)
    out = ""
    n = len(s)
    zero_pending = False
    for i, ch in enumerate(s):
        d = int(ch)
        pos = n - i - 1
        if d == 0:
            zero_pending = True
            continue
        if zero_pending and out:
            out += "零"
        zero_pending = False
        if not (d == 1 and pos == 1 and not out):
            out += "一二三四五六七八九"[d - 1]
        out += _UNITS[pos]
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="docs/agent-v1-taskbook-gate1-lawcheck-20260907.json")
    args = ap.parse_args()

    import chromadb  # noqa: PLC0415

    client = chromadb.PersistentClient(path=str(REPO / "backend" / "chroma_db"))
    col = client.get_collection("legal_provisions_cos")

    rows = []
    for source, art in TARGETS:
        zh = _zh(art)
        article = f"第{zh}条"
        try:
            got = col.get(where={"$and": [{"source": {"$eq": source}}, {"article": {"$eq": article}}]}, limit=5)
            ids = got["ids"]
        except Exception as exc:  # noqa: BLE001
            rows.append({"id": f"{source}:{art}", "found": False, "note": f"query error: {exc}"})
            continue
        if ids:
            meta = got["metadatas"][0]
            rows.append(
                {
                    "id": f"{source}:{art}",
                    "found": True,
                    "article_actual": article,
                    "evidence_id": ids[0],
                    "count": len(ids),
                    "status": meta.get("status"),
                    "source_actual": meta.get("source"),
                }
            )
        else:
            rows.append(
                {
                    "id": f"{source}:{art}",
                    "found": False,
                    "article_queried": article,
                    "note": "not found in legal_provisions_cos",
                }
            )

    out = REPO / args.out
    out.write_text(
        json.dumps(
            {"schema": "gate1-law-existence/v1", "collection": "legal_provisions_cos", "rows": rows},
            ensure_ascii=False,
            indent=1,
        ),
        encoding="utf-8",
    )
    for r in rows:
        print(
            ("FOUND  " if r.get("found") else "MISS   ")
            + r["id"]
            + (
                f" -> {r.get('evidence_id', '')[:8]} status={r.get('status')}"
                if r.get("found")
                else " " + r.get("note", "")
            )
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
