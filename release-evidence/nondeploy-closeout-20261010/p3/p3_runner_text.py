"""P3-b text-RAG runner: the product's own /api/chat over ASGI, streaming, LongCat-2.5-Preview.

Only three things are runner-side (nothing in the product is edited): the private outlet
bindings, one injected registry entry for the representative model, and a local-only JWT
secret for the private database. Assertions are read from cases-frozen.json.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import sys
from pathlib import Path

import httpx

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import p3_env  # noqa: E402
import p3_transport_guard as tg  # noqa: E402

CAND = Path(sys.argv[1])
RUN = sys.argv[2] if len(sys.argv) > 2 else "all"
ONLY = [c for c in sys.argv[3:]]
MODEL = "LongCat-2.5-Preview"


def boot_env() -> dict:
    env = p3_env.bind_private_root(p3_env.read_env())
    env["LLM_MODELS_JSON"] = json.dumps([{
        "key": "p3_longcat_text", "model": MODEL, "modality": "text", "tier": "flag",
        "priority": 0, "capabilities": ["text"], "timeout": 120,
    }], ensure_ascii=False)
    env["JWT_SECRET"] = "p3-runner-local-only-not-a-real-credential"
    env["RERANK_ENABLED"] = "true"
    os.environ.update(env)
    return env


def make_user():
    import auth
    import database
    import models

    models.Base.metadata.create_all(bind=database.engine)
    db = database.SessionLocal()
    u = db.query(models.User).filter_by(username="p3-runner").first()
    if u is None:
        u = models.User(username="p3-runner", password_hash=auth.hash_password("local-only"), role="admin", is_active=True)
        db.add(u)
        db.commit()
        db.refresh(u)
    token = auth.create_token(u)
    db.close()
    return token


async def ask(client: httpx.AsyncClient, token: str, question: str) -> dict:
    buf, sources, frames, non_json = [], None, {}, []
    async with client.stream("POST", "/api/chat", headers={"Authorization": "Bearer " + token},
                             json={"content": question, "no_cache": True}) as r:
        status = r.status_code
        body = ""
        if status != 200:
            body = (await r.aread()).decode("utf-8", "replace")[:200]
        else:
            async for line in r.aiter_lines():
                if not line.startswith("data: "):
                    continue
                try:
                    d = json.loads(line[6:])
                except json.JSONDecodeError:
                    non_json.append(line[6:][:20])   # 例如终止帧 [DONE]；记下来不静默吞
                    continue
                t = d.get("type")
                frames[t if t else "content"] = frames.get(t if t else "content", 0) + 1
                if "content" in d and not t:
                    buf.append(str(d["content"]))
                if d.get("sources") is not None:
                    sources = d["sources"]
    return {"http": status, "answer": "".join(buf), "sources": sources, "frame_types": frames, "non_json_frames": non_json, "error_body": body}


def check(case: dict, res: dict) -> list[str]:
    import retrieval

    fails: list[str] = []
    ans = res["answer"]
    raw_cites = [list(c)[:2] for c in retrieval.extract_citations(ans)]  # (法名, 条号, 原文匹配) 三元
    norm = retrieval._norm_source
    cites = [[norm(str(a)), str(b)] for a, b in raw_cites]
    diag = {"but_shorthand": ("情节显著轻微" in ans) and ("不认为是犯罪" in ans), "refuse_words": [w for w in ("库内", "未收录", "没有", "不在", "无此条") if w in ans]}
    for rule in case["assert"]:
        kind = rule["type"]
        if kind == "citation_pair":
            if [str(x) for x in rule["expect"]] not in cites:
                fails.append("citation_pair missing %s (got %s)" % (rule["expect"], cites))
        elif kind == "must_contain_any":
            if not any(t in ans for t in rule["tokens"]):
                fails.append("must_contain_any %s" % rule["tokens"])
        elif kind == "forbid_phrase":
            if any(t in ans for t in rule["tokens"]):
                fails.append("forbid_phrase hit %s" % rule["tokens"])
        elif kind == "forbid_output":
            if any(t in ans for t in rule["tokens"]):
                fails.append("forbid_output hit %s" % rule["tokens"])
        elif kind == "must_cover_elements":
            missing = [t for t in rule["tokens"] if t not in ans]
            if missing:
                fails.append("elements missing %s" % missing)
        elif kind == "quote_verbatim_from_seed_DISABLED_BY_GOLD_AMENDMENT":
            import rag_chain
            got = rag_chain.vectorstore._collection.get(where={"origin": "seed"}, include=["metadatas", "documents"])
            hit = [d for m, d in zip(got["metadatas"], got["documents"]) if m["source"] == rule["pair"][0] and m["article"] == rule["pair"][1]]
            core = hit[0].split("\n", 1)[-1] if hit else ""
            frag = core.replace(" ", "")[10:40]
            if core and frag not in ans.replace(" ", ""):
                fails.append("quote not verbatim (%s)" % rule["pair"])
        elif kind in ("no_single_date_commitment", "forbid_silent_pick"):
            picked = [t for t in rule["tokens"] if t in ans]
            if len(picked) == 1:
                fails.append("%s committed to a single value %s" % (kind, picked))
        elif kind == "must_present_both_conflicting":
            if not all(any(p[0] in c for c in cites) for p in rule["pairs"]):
                fails.append("both conflicting sources not cited: %s vs %s" % (rule["pairs"], cites))
        elif kind == "must_refuse_or_flag_gap":
            if not any(t in ans for t in ("库内", "未收录", "没有", "无法确认", "不在", "未能找到", "无此条")):
                fails.append("no refusal/gap flag in answer")
    return fails, diag


async def main() -> int:
    boot_env()
    guard = tg.TransportGuard(allowed=dict(p3_env.MODEL_HOSTS), max_calls=48)
    tg.install(guard)
    sys.path.insert(0, str(CAND / "backend"))
    import main as app_main  # noqa: N816
    import rag_chain  # noqa: F401,E402
    import retrieval  # noqa: E402

    cases = json.loads((HERE / "cases-frozen.json").read_text(encoding="utf-8"))["cases"]
    if ONLY:
        cases = [c for c in cases if c["id"] in ONLY]
    token = make_user()
    rows = []
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app_main.app), base_url="http://svc", timeout=180.0) as client:
        for c in cases:
            before = len(guard.calls)
            res = await ask(client, token, c["q"])
            fails, diag = check(c, res) if res["http"] == 200 else (["http"], {})
            diag = {k: v for k, v in diag.items() if v}
            rec = {"id": c["id"], "tier": c["tier"], "http": res["http"], "answer_chars": len(res["answer"]),
                   "answer_sha8": hashlib.sha256(res["answer"].encode()).hexdigest()[:8],
                   "sends_this_case": [x.split("/")[2] + "//" + "/".join(x.split("/")[3:]) for x in guard.calls[before:]],
                   "frame_types": res["frame_types"], "non_json_frames": res["non_json_frames"][:3], "citations_raw": [list(x) for x in retrieval.extract_citations(res["answer"])], "diag": diag,
                   "verdict": "PASS" if not fails else "FAIL", "fails": fails,
                   "guard_sends_so_far": len(guard.calls), "guard_refused": len(guard.refused)}
            rows.append(rec)
            print(json.dumps(rec, ensure_ascii=False, sort_keys=True))
    tg.uninstall()
    out = HERE / "logs" / ("runner-text-%s.json" % RUN)
    out.write_text(json.dumps(rows, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8", newline="\n")
    print("sends=%d refused=%d verdicts=%s" % (len(guard.calls), len(guard.refused), [r["verdict"] for r in rows]))
    return 0 if all(r["verdict"] == "PASS" for r in rows) else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
