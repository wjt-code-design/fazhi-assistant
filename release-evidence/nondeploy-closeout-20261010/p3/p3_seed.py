"""P3-a seed the private index through the product's own indexer (knowledge_base.build).

Zero outbound is proven, not asserted: socket.connect is wrapped to raise for any
non-loopback target and the attempt count is printed. Model weights come from the
private HF cache copy (sha256 recorded in seed-manifest.json).
"""
from __future__ import annotations

import json
import os
import socket
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import p3_env  # noqa: E402

CAND = Path(sys.argv[1])
SEED = HERE / "seed-corpus-frozen.json"
MANIFEST = HERE / "seed-manifest.json"

ATTEMPTS: list[str] = []
_REAL_CONNECT = socket.socket.connect


def _guarded_connect(self, addr):  # noqa: ANN001
    host = addr[0] if isinstance(addr, tuple) else str(addr)
    if isinstance(addr, tuple) and str(host) in ("127.0.0.1", "::1", "localhost"):
        return _REAL_CONNECT(self, addr)
    ATTEMPTS.append(str(host))
    raise OSError("P3 seed leg is offline: refused connect to %s" % host)


def main() -> int:
    env = p3_env.bind_private_root(p3_env.read_env())
    os.environ.update({k: v for k, v in env.items() if k not in ("LLM_API_KEY", "RERANK_API_KEY", "DASHSCOPE_API_KEY", "ZHIPUAI_API_KEY", "SILICONFLOW_API_KEY", "EMBEDDING_API_KEY", "LLM_MODELS_JSON")})
    for name in ("CHROMA_DIR", "HF_HOME", "HF_HUB_CACHE", "HF_HUB_OFFLINE", "EMBEDDING_PROVIDER"):
        print("bind %-16s %s" % (name, os.environ.get(name)))
    sys.path.insert(0, str(CAND / "backend"))
    import rag_chain  # noqa: F401,E402  (loaded while HF offline is still 1)
    import knowledge_base  # noqa: E402  (this module flips HF_HUB_OFFLINE=0 at import)
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    socket.socket.connect = _guarded_connect
    knowledge_base.build(str(SEED))
    socket.socket.connect = _REAL_CONNECT
    coll = rag_chain.vectorstore._collection
    got = coll.get(where={"origin": "seed"}, include=["metadatas"])
    pairs = sorted("%s·%s" % (m["source"], m["article"]) for m in got["metadatas"])
    want = json.loads(MANIFEST.read_text(encoding="utf-8"))
    expect_real = set(want["real_pairs"])
    synth_titles = set(want["synthetic_titles"])
    got_pairs = set(pairs)
    real_in_got = {p for p in got_pairs if not p.split("·")[0].startswith("合成")}
    anchor_ok = real_in_got == expect_real
    count_ok = len(pairs) == want["real_count"] + 6
    print("G-a count=%d expect=%d ok=%s" % (len(pairs), want["real_count"] + 6, count_ok))
    print("G-a real-anchor set equal=%s (|%d| vs |%d|)" % (anchor_ok, len(real_in_got), len(expect_real)))
    if not anchor_ok:
        print("  missing:", sorted(expect_real - real_in_got))
        print("  extra:", sorted(real_in_got - expect_real))
    print("G-a synthetic titles present:", sorted({p.split(chr(183))[0] for p in got_pairs if "合成" in p}) == sorted(synth_titles))
    print("G-a non-ascii-safe metadata sample:", json.dumps(got["metadatas"][0], ensure_ascii=False)[:220])
    print("outbound attempts=%d VERDICT=%s" % (len(ATTEMPTS), "SEED_OK_OFFLINE" if (anchor_ok and count_ok and not ATTEMPTS) else "SEED_REFUSE"))
    Path(HERE / "logs" / "seed-report.json").write_text(json.dumps({
        "count": len(pairs), "pairs": pairs, "anchor_ok": anchor_ok, "count_ok": count_ok,
        "outbound_attempts": len(ATTEMPTS), "chroma_dir": os.environ.get("CHROMA_DIR"),
        "seed_corpus_sha256": want["seed_corpus_sha256"],
    }, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8", newline="\n")
    return 0 if (anchor_ok and count_ok and not ATTEMPTS) else 1


if __name__ == "__main__":
    sys.exit(main())
