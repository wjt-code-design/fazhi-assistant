"""P3-a gates G-a / G-b / G-c before any paid call. Run once with rerank off, once on.

G-a  index count + (法名×条号) content anchor (not a size gate)
G-b  the same probe queries under RERANK_ENABLED=false vs true, two separate processes
G-c  self-query: every seeded article must recall itself (vector space sanity)
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import p3_env  # noqa: E402
import p3_transport_guard as tg  # noqa: E402

CAND = Path(sys.argv[1])
MODE = sys.argv[2]
MARK = "（合成条文，非官方原文，仅用于本轮验收）"
MARK2 = "（合成条文，非官方原文，干扰项）"
PROBES = [
    ("P1", "试用期是否包含在劳动合同期限内", {"劳动合同法·第十九条"}),
    ("P2", "申请劳动仲裁的时效期间是多久", {"劳动争议调解仲裁法·第二十七条", "合成乙法·第七条"}),
    ("P3", "犯罪概念 情节显著轻微危害不大 不认为是犯罪", {"刑法·第十三条"}),
]


def main() -> int:
    env = p3_env.bind_private_root(p3_env.read_env())
    env["RERANK_ENABLED"] = "true" if MODE == "on" else "false"
    os.environ.update(env)
    guard = tg.TransportGuard(allowed=dict(p3_env.MODEL_HOSTS), max_calls=40)
    tg.install(guard)
    sys.path.insert(0, str(CAND / "backend"))
    import rag_chain  # noqa: E402
    import retrieval  # noqa: E402
    from settings import settings  # noqa: E402

    coll = rag_chain.vectorstore._collection
    got = coll.get(where={"origin": "seed"}, include=["metadatas", "documents"])
    metas = got["metadatas"]
    want = json.loads((HERE / "seed-manifest.json").read_text(encoding="utf-8"))
    pairs = sorted("%s·%s" % (m["source"], m["article"]) for m in metas)
    ga = {"count": len(pairs), "expect": want["real_count"] + 6,
          "real_anchor_equal": {p for p in pairs if not p.split("·")[0].startswith("合成")} == set(want["real_pairs"]),
          "synthetic_equal": sorted({p.split("·")[0] for p in pairs if p.split("·")[0].startswith("合成")}) == sorted(want["synthetic_titles"])}

    selfq = []
    for meta, doc in zip(metas, got["documents"]):
        body = str(doc).split("\n", 1)[-1].replace(MARK, "").replace(MARK2, "").strip()
        hits = retrieval.vector_top(body[:120], 3)
        names = ["%s·%s" % (d.metadata.get("source"), d.metadata.get("article")) for d, _ in hits]
        target = "%s·%s" % (meta["source"], meta["article"])
        selfq.append({"pair": target, "in_top3": target in names, "top3": names})
    gc = {"total": len(selfq), "self_recall": sum(1 for r in selfq if r["in_top3"]),
          "failures": [r for r in selfq if not r["in_top3"]][:4]}

    import rag_chain as _rc  # 只用于绕开「同查询命中进程内缓存」这条假绿（G-b 两趟要真各发一次）
    probes = []
    for name, q, expects in PROBES:
        _rc._cache.invalidate() if hasattr(_rc, "_cache") else None
        retrieval.invalidate()
        docs = retrieval.hybrid_retrieve(q, k=4)
        order = ["%s·%s" % (d.metadata.get("source"), d.metadata.get("article")) for d in docs]
        probes.append({"id": name, "query": q, "order": order,
                       "expects_any_of": sorted(expects),
                       "hit": bool(set(order[:2]) & expects),
                       "changed_vs_cosine_baseline": None})
    out = {"mode": MODE,
           "settings": {"rerank_enabled": str(settings.rerank_enabled), "rerank_model": str(settings.rerank_model),
                        "rerank_base_host": str(settings.rerank_base_url).split("/")[2] if settings.rerank_base_url else "",
                        "embedding_provider": str(settings.embedding_provider)},
           "G-a": ga, "G-c": gc, "probes": probes,
           "guard_calls": len(guard.calls), "guard_hosts": sorted({c.split("/")[2] for c in guard.calls}),
           "guard_refused": guard.refused}
    (HERE / "logs" / ("gate-%s.json" % MODE)).write_text(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8", newline="\n")
    tg.uninstall()
    print(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True)[:1600])
    verdict = ga["count"] == ga["expect"] and ga["real_anchor_equal"] and ga["synthetic_equal"] and gc["self_recall"] == gc["total"] and not guard.refused
    print("VERDICT=" + ("GATES_HOLD" if verdict else "GATES_BROKEN"))
    return 0 if verdict else 1


if __name__ == "__main__":
    sys.exit(main())
