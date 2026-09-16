"""Gate 1 冻结（第二部分）：计算题集/协议/rubric/法条核验表的 SHA-256，并生成稳定 fact_id 映射。

- fact_id 方案：<CASE>-r<轮次>-f<序号>（来自 frozen-round-protocol 的 fact_units；稳定、可审计）
- 输出：frozen-fact-ids-v1.json + gate1-freeze-manifest.json（含全部 hash + law_as_of + collection 边界）
用法：python scripts/gen_gate1_freeze.py
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DIR = REPO / "release-evidence/legal-agent-v1-complex-v1-20260907"

FILES = ["frozen-cases-v1.json", "frozen-round-protocol-v1.json", "rubric-v1.json"]
LAW_CHECK = REPO / "docs" / "agent-v1-taskbook-gate1-lawcheck-20260907.json"

COLLECTIONS = ["legal_provisions_cos", "qa_pairs"]
CORPUS_LOGICAL = "d76220e7460789382d5bf40ce45a559b1cf017b2b43842d6056a0117d42e9474"
LAW_AS_OF = "2026-08-01"  # 与 011 manifest 一致（任务书 §5：每次运行记录 law_as_of）


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main() -> int:
    hashes = {f: sha(DIR / f) for f in FILES}
    hashes["gate1-lawcheck"] = sha(LAW_CHECK)

    protocol = json.loads((DIR / "frozen-round-protocol-v1.json").read_text(encoding="utf-8"))
    fact_ids: dict[str, dict[str, list[str]]] = {}
    for case, rounds in protocol["fact_units"].items():
        per_round = {}
        for rname, facts in rounds.items():
            rn = rname.replace("round", "")
            per_round[rname] = [f"{case}-r{rn}-f{i}" for i in range(1, len(facts) + 1)]
        fact_ids[case] = per_round

    (DIR / "frozen-fact-ids-v1.json").write_text(
        json.dumps(
            {"schema_version": "agent-v1-complex-fact-ids/v1", "fact_ids": fact_ids}, ensure_ascii=False, indent=1
        ),
        encoding="utf-8",
    )
    hashes["frozen-fact-ids-v1.json"] = sha(DIR / "frozen-fact-ids-v1.json")

    manifest = {
        "schema_version": "gate1-freeze/v1",
        "status": "FROZEN",
        "law_as_of": LAW_AS_OF,
        "collections": COLLECTIONS,
        "corpus_logical_sha256": CORPUS_LOGICAL,
        "file_sha256": hashes,
        "note": "金标独立于当前实现与模型输出（转录自任务书 §7，未反向修改）；开发集冻结后只能新增版本，不得原地改题",
    }
    (DIR / "gate1-freeze-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    for k, v in hashes.items():
        print(f"{k}: {v[:16]}…")
    print("fact_ids:", sum(len(v) for v in fact_ids.values()), "units")
    return 0


if __name__ == "__main__":
    sys.exit(main())
