"""T-C 只读探针：定位「周末加班，加班费怎么算？」题里《劳动法》第四十四条的检索丢失点。

问题：丢失发生在 召回 / 重排 / 后处理 哪一步？
做法：同一题、同一库副本、同一代码版本、同一真实 rerank 配置，记录三张表
  1) 重排前进入 `retrieval._rerank_docs` 的完整候选清单（含逐条身份 + 原始序/分）
  2) 重排后顺序（含 rerank relevance_score）
  3) 最终截取给下游的 top-k

隔离（全部在 import retrieval 之前完成，本脚本不写仓库内任何文件，只读真库）：
  CHROMA_DIR   → %TEMP% 下的**真库整目录副本**
  QUOTA_DB     → %TEMP% 新文件（不带入真实配额账本）
  DATABASE_URL → %TEMP% 临时库
  LLM_BASE_URL → http://127.0.0.1:9（任何答案生成调用必失败；本脚本也不调生成）
  只从 .env 取 rerank 段（key 不落盘、不打印，只报 SET(n chars)）

用法：backend/venv/Scripts/python.exe probe_trace_44.py
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
import time

BACKEND = r"C:\Users\33393\Desktop\ai-legal-helper\backend"
OUT_DIR = r"C:\Users\33393\Desktop\ai-legal-helper\dispatch-output\c-retrieval-trace-20260927"
TMP = tempfile.gettempdir()
CHROMA_COPY = os.path.join(TMP, "ctrace", "chroma_db_copy")
REAL_CHROMA = os.path.join(BACKEND, "chroma_db")
QUERY = "周末加班，加班费怎么算？"
K = 6  # 与 smoke_citation_fast.py 的 retrieve(q, k=6) 一致
# 运行标签（文件名后缀）与「对照跑」开关：对照跑=关 rerank（仅用于归因，不是主读数）
OUT_TAG = sys.argv[1] if len(sys.argv) > 1 else "run"
COUNTERFACTUAL_NO_RERANK = os.environ.get("CTRACE_RERANK", "").lower() == "off"

# ---------------------------------------------------------------- 1. 环境隔离
os.environ["CHROMA_DIR"] = CHROMA_COPY
os.environ["QUOTA_DB"] = os.path.join(TMP, "ctrace_quota.sqlite")
os.environ["DATABASE_URL"] = "sqlite:///" + os.path.join(TMP, "ctrace_app.db")
os.environ["LLM_BASE_URL"] = "http://127.0.0.1:9"
os.environ.pop("RERANK_QUOTA_TOTALS", None)

sys.path.insert(0, BACKEND)

# 只取 rerank 段 + embedding 段（其余 .env 键一律不进：LLM_* 保持死端口/缺省）
from dotenv import dotenv_values  # noqa: E402

_env = dotenv_values(os.path.join(BACKEND, ".env"))
ALLOWED = (
    "RERANK_ENABLED",
    "RERANK_MODEL",
    "RERANK_MODELS",
    "RERANK_API_KEY",
    "RERANK_BASE_URL",
    "RERANK_QUOTA_TOTAL",
    "RERANK_QUOTA_TOTALS",
    "SILICONFLOW_API_KEY",
    "EMBEDDING_PROVIDER",
    "EMBEDDING_MODEL",
)
secret_report: dict[str, str] = {}
for _key in ALLOWED:
    _val = _env.get(_key)
    if _val:
        os.environ[_key] = _val
        if "KEY" in _key:
            secret_report[_key] = f"SET({len(_val)} chars)"
        else:
            secret_report[_key] = _val
    elif "KEY" in _key:
        secret_report[_key] = "UNSET"

from langchain_core.documents import Document  # noqa: E402

if COUNTERFACTUAL_NO_RERANK:
    os.environ["RERANK_ENABLED"] = "false"  # 仅对照跑：验证「同一候选池 + 不重排」是否进 top-k

import query_understand  # noqa: E402
import quota_utils  # noqa: E402
import retrieval  # noqa: E402
from rag_chain import COLLECTION_NAME, vectorstore  # noqa: E402
from settings import settings  # noqa: E402

# ---------------------------------------------------------------- 2. 记录容器
rec: dict = {
    "query": QUERY,
    "k": K,
    "env": {},
    "spies": {"vector_top": [], "bm25_top": [], "append_unique": [], "rerank": []},
    "http_rerank_calls": [],
    "quota": {"deduct": [], "depleted_marked": []},
    "real_kb_fingerprint": {},
}


def fingerprint(path: str) -> dict:
    """真库指纹（只读）：size/mtime/md5。跑前跑后各一次，证明真库未被写。"""
    h = hashlib.md5()
    with open(path, "rb") as fh:
        while True:
            b = fh.read(1024 * 1024)
            if not b:
                break
            h.update(b)
    st = os.stat(path)
    return {"path": path, "size": st.st_size, "mtime": round(st.st_mtime, 3), "md5": h.hexdigest()}


def brief(d: Document, extra: dict | None = None) -> dict:
    m = d.metadata or {}
    out = {
        "source": m.get("source"),
        "article": m.get("article"),
        "category": m.get("category"),
        "effective_from": m.get("effective_from"),
        "effective_to": m.get("effective_to"),
        "origin": m.get("origin"),
        "cid": hashlib.sha1((d.page_content or "").encode("utf-8")).hexdigest()[:10],
        "head": (d.page_content or "").replace("\n", "")[:26],
    }
    if extra:
        out.update(extra)
    return out


def is_target(d: Document) -> bool:
    """判据本体与 smoke_citation_fast.recall_hit 同口径（法名×条号 联合，走同一归一函数）。"""
    m = d.metadata or {}
    return retrieval._source_key(str(m.get("source") or "")) == retrieval._source_key("劳动法") and retrieval._normalize_article(
        str(m.get("article") or "")
    ) == retrieval._normalize_article("第四十四条")


# ---------------------------------------------------------------- 3. 库副本体检
_coll = vectorstore._collection
target_rows = _coll.get(
    where={"$and": [{"source": {"$eq": "劳动法"}}, {"article": {"$eq": "第四十四条"}}]},
    include=["documents", "metadatas"],
)
competing = _coll.get(where={"article": {"$eq": "第四十四条"}}, include=[])
rec["kb"] = {
    "chroma_dir": CHROMA_COPY,
    "collection": COLLECTION_NAME,
    "total_vectors": _coll.count(),
    "target_rows": len(target_rows.get("ids") or []),
    "target_meta": (target_rows.get("metadatas") or [None])[0],
    "target_text": ((target_rows.get("documents") or [""])[0] or "").replace("\n", "")[:200],
    "competing_第四十四条": len(competing.get("ids") or []),
}

# ---------------------------------------------------------------- 4. 埋点
_orig_decompose = query_understand.decompose
_orig_vector_top = retrieval.vector_top
_orig_bm25_top = retrieval.bm25_top
_orig_append_unique = retrieval._append_unique
_orig_rerank = retrieval._rerank_docs


def decompose_spy(query, concept_keywords=()):
    out = _orig_decompose(query, concept_keywords)
    rec["units"] = [{"text": t, "kind": kind} for t, kind in out]
    return out


def vector_spy(query, n, category=None, valid=None):
    res = _orig_vector_top(query, n, category, valid=valid)
    rec["spies"]["vector_top"].append(
        {
            "query": query,
            "n": n,
            "rows": [brief(d, {"score": round(float(s), 6), "is_target": is_target(d)}) for d, s in res],
        }
    )
    return res


def bm25_spy(query, n, category=None, valid=None):
    res = _orig_bm25_top(query, n, category, valid=valid)
    rec["spies"]["bm25_top"].append(
        {
            "query": query,
            "n": n,
            "rows": [brief(d, {"score": round(float(s), 6), "is_target": is_target(d)}) for d, s in res],
        }
    )
    return res


def append_unique_spy(dst, seen, dids):
    _orig_append_unique(dst, seen, dids)
    idx = len(rec["spies"]["append_unique"])
    rec["spies"]["append_unique"].append(
        {
            "call": idx,
            "label": ("vector_pool" if idx == 0 else "bm25_pool" if idx == 1 else "rrf_top"),
            "incoming": len(list(dids)),
            "dst_after": len(dst),
        }
    )


def rerank_spy(query, docs, *, deadline_monotonic=None):
    docs_in = list(docs)
    t0 = time.monotonic()
    out = _orig_rerank(query, docs, deadline_monotonic=deadline_monotonic)
    elapsed = round(time.monotonic() - t0, 3)
    call = {
        "rerank_query": query,
        "n_in": len(docs_in),
        "elapsed_s": elapsed,
        "remote_result": "SUCCESS" if out is not None else "DEGRADED(返 None → 回落余弦精排)",
        "in": [brief(d, {"pos": i + 1, "is_target": is_target(d)}) for i, d in enumerate(docs_in)],
        "out": None,
    }
    if out is not None:
        pos_in = {d.page_content: i + 1 for i, d in enumerate(docs_in)}
        call["out"] = [brief(d, {"pos": i + 1, "in_pos": pos_in.get(d.page_content), "is_target": is_target(d)}) for i, d in enumerate(out)]
    rec["spies"]["rerank"].append(call)
    return out


def http_post_spy(url, **kw):
    t0 = time.monotonic()
    payload = kw.get("json") or {}
    docs_sent = payload.get("documents") or (payload.get("input") or {}).get("documents") or []
    entry = {"url": url, "model": payload.get("model"), "n_docs_sent": len(docs_sent), "ok": None}
    try:
        resp = _orig_post(url, **kw)
    except Exception as exc:  # 网络/HTTP 层失败
        entry.update({"ok": False, "error": f"{type(exc).__name__}"})
        rec["http_rerank_calls"].append(entry)
        raise
    body = {}
    try:
        body = resp.json()
    except Exception:
        pass
    results = body.get("results") or (body.get("output") or {}).get("results") or []
    entry.update(
        {
            "ok": True,
            "status": getattr(resp, "status_code", None),
            "elapsed_s": round(time.monotonic() - t0, 3),
            "n_results": len(results),
            "results": [
                {"index": r.get("index"), "relevance_score": r.get("relevance_score")} for r in results
            ],
        }
    )
    rec["http_rerank_calls"].append(entry)
    return resp


_orig_deduct = quota_utils.deduct_utility
_orig_mark = quota_utils.mark_utility_depleted


def deduct_spy(name, tokens):
    rec["quota"]["deduct"].append({"model": name, "tokens": tokens})
    return _orig_deduct(name, tokens)


def mark_spy(name):
    rec["quota"]["depleted_marked"].append(name)
    return _orig_mark(name)


import httpx  # noqa: E402

_orig_post = httpx.post
httpx.post = http_post_spy
query_understand.decompose = decompose_spy
retrieval.vector_top = vector_spy
retrieval.bm25_top = bm25_spy
retrieval._append_unique = append_unique_spy
retrieval._rerank_docs = rerank_spy
quota_utils.deduct_utility = deduct_spy
quota_utils.mark_utility_depleted = mark_spy

rec["env"] = {
    "CHROMA_DIR": os.environ["CHROMA_DIR"],
    "QUOTA_DB": os.environ["QUOTA_DB"],
    "DATABASE_URL": os.environ["DATABASE_URL"],
    "LLM_BASE_URL": os.environ["LLM_BASE_URL"],
    "dotenv_selected": secret_report,
    "rerank_enabled": settings.rerank_enabled,
    "rerank_models": quota_utils.rerank_model_list(),
    "rerank_base_url": settings.rerank_base_url,
    "rerank_quota_total": settings.rerank_quota_total,
    "rerank_hard_threshold": settings.rerank_hard_threshold,
    "retrieval_pool_k": settings.retrieval_pool_k,
    "query_rewrite_enabled": settings.query_rewrite_enabled,
    "feature_hybrid": settings.feature_hybrid,
    "embedding_provider": settings.embedding_provider,
    "rerank_client_built": retrieval._get_rerank_client() is not None,
}

# ---------------------------------------------------------------- 5. 跑一次真实 retrieve
rec["real_kb_fingerprint"]["before"] = fingerprint(os.path.join(REAL_CHROMA, "chroma.sqlite3"))
t0 = time.monotonic()
docs = retrieval.retrieve(QUERY, k=K)
rec["elapsed_s"] = round(time.monotonic() - t0, 3)
rec["real_kb_fingerprint"]["after"] = fingerprint(os.path.join(REAL_CHROMA, "chroma.sqlite3"))

rec["routing"] = {
    "parse_article_query": retrieval.parse_article_query(QUERY),  # None ⇒ 不走条号直查
    "bridge_query": retrieval._bridge_query(QUERY),
    "rerank_query": retrieval._rerank_query(QUERY, [(u["text"], u["kind"]) for u in rec.get("units", [])]),
    "cache_hit": False,
}

call = rec["spies"]["rerank"][0] if rec["spies"]["rerank"] else None
rec["final_topk"] = [brief(d, {"pos": i + 1, "is_target": is_target(d)}) for i, d in enumerate(docs)]
rec["gate"] = {
    "expected": "(劳动法, 第四十四条)",
    "hit": any(is_target(d) for d in docs),
    "target_in_pool(重排前候选)": bool(call and any(r["is_target"] for r in call["in"])),
    "target_in_reranked(重排后)": bool(call and call["out"] and any(r["is_target"] for r in call["out"])),
}
# 召回路原序里目标条的位置（"召回有没有丢"的直接证据）
v_rows = (rec["spies"]["vector_top"][0]["rows"] if rec["spies"]["vector_top"] else [])
b_rows = (rec["spies"]["bm25_top"][0]["rows"] if rec["spies"]["bm25_top"] else [])
rec["gate"]["target_pos_in_vector_recall"] = next((i + 1 for i, r in enumerate(v_rows) if r["is_target"]), None)
rec["gate"]["target_vector_score"] = next((r["score"] for r in v_rows if r["is_target"]), None)
rec["gate"]["target_pos_in_bm25_recall"] = next((i + 1 for i, r in enumerate(b_rows) if r["is_target"]), None)
rec["gate"]["vector_recall_len"] = len(v_rows)
rec["gate"]["bm25_recall_len"] = len(b_rows)
if call:
    rec["gate"]["pool_size"] = call["n_in"]
    rec["gate"]["target_pos_in_pool"] = next((r["pos"] for r in call["in"] if r["is_target"]), None)
    rec["gate"]["target_pos_after_rerank"] = (
        next((r["pos"] for r in (call["out"] or []) if r["is_target"]), None)
    )
    rec["gate"]["target_rerank_score"] = None
    http_ok = bool(rec["http_rerank_calls"]) and rec["http_rerank_calls"][0].get("ok")
    if http_ok and call["out"]:
        res = rec["http_rerank_calls"][0].get("results") or []
        ranked = sorted(res, key=lambda r: r.get("relevance_score") or 0.0, reverse=True)
        score_by_in_pos = {r.get("index", -1) + 1: r.get("relevance_score") for r in res}
        for row in call["out"]:
            row["relevance_score"] = score_by_in_pos.get(row.get("in_pos"))
        for pos, r in enumerate(ranked, 1):
            i = r.get("index") or 0
            if 0 <= i < call["n_in"] and call["in"][i].get("is_target"):
                rec["gate"]["target_rerank_score"] = r.get("relevance_score")
                rec["gate"]["target_pos_in_rerank_response"] = pos
                break
        rec["gate"]["rerank_top6_scores"] = [
            {
                "pos": p,
                "source": (call["in"][r["index"]]["source"] if 0 <= (r.get("index") or 0) < call["n_in"] else None),
                "article": (call["in"][r["index"]]["article"] if 0 <= (r.get("index") or 0) < call["n_in"] else None),
                "relevance_score": r.get("relevance_score"),
            }
            for p, r in enumerate(ranked[:6], 1)
        ]

# ---------------------------------------------------------------- 6. 落盘
os.makedirs(OUT_DIR, exist_ok=True)
rec["mode"] = "COUNTERFACTUAL_rerank_off" if COUNTERFACTUAL_NO_RERANK else "REAL_rerank_on"
with open(os.path.join(OUT_DIR, f"trace-output-{OUT_TAG}.json"), "w", encoding="utf-8") as fh:
    json.dump(rec, fh, ensure_ascii=False, indent=1)


def line(rows, tag):
    return "\n".join(
        f"  {tag} {r['pos']:>2}. {r['source']}/{r['article']}  cid={r['cid']}"
        + (f" score={r.get('score')}" if r.get("score") is not None else "")
        + (f" rel={r.get('relevance_score')}" if r.get("relevance_score") is not None else "")
        + ("   <== 目标" if r.get("is_target") else "")
        for r in rows
    )


txt = [
    "=== T-C 探针读数：周末加班 → 劳动法第四十四条 ===",
    f"mode={rec['mode']}  query={QUERY}  k={K}  elapsed={rec['elapsed_s']}s",
    f"collection={rec['kb']['collection']}  total={rec['kb']['total_vectors']}  "
    f"劳动法/第四十四条={rec['kb']['target_rows']} 块  全库第四十四条={rec['kb']['competing_第四十四条']} 块",
    f"target_text={rec['kb']['target_text']}",
    "",
    f"[0] units={rec.get('units')}  rerank_query={rec['routing']['rerank_query']!r}  "
    f"pool_k={rec['env']['retrieval_pool_k']}  rerank_client={rec['env']['rerank_client_built']}",
    "",
    f"[1] 重排前进入 _rerank_docs 的候选（{call['n_in'] if call else 0} 条）:",
    line(call["in"], "(in)") if call else "  <未调用>",
    "",
    f"[2] 重排后（remote={call['remote_result'] if call else 'n/a'}）:",
    line(call["out"] or [], "(out)") if call and call["out"] else "  <降级：无重排输出>",
    "",
    f"[3] 最终截取 top-k（{len(rec['final_topk'])} 条）:",
    line(rec["final_topk"], "(fin)"),
    "",
    f"召回路原序里的目标条：vector top{rec['gate']['vector_recall_len']} 内第 {rec['gate']['target_pos_in_vector_recall']} 位 "
    f"(score={rec['gate']['target_vector_score']})；bm25 top{rec['gate']['bm25_recall_len']} 内第 {rec['gate']['target_pos_in_bm25_recall']} 位",
    f"HTTP rerank 调用：{[{k: v for k, v in c.items() if k != 'results'} for c in rec['http_rerank_calls']]}",
    f"quota deduct={rec['quota']['deduct']}  depleted_marked={rec['quota']['depleted_marked']}",
    f"真库指纹 before={rec['real_kb_fingerprint']['before']['md5'][:12]} "
    f"after={rec['real_kb_fingerprint']['after']['md5'][:12]} "
    f"unchanged={rec['real_kb_fingerprint']['before'] == rec['real_kb_fingerprint']['after']}",
    "",
    f"GATE {rec['gate']}",
]
with open(os.path.join(OUT_DIR, f"trace-readout-{OUT_TAG}.txt"), "w", encoding="utf-8") as fh:
    fh.write("\n".join(txt) + "\n")

print("\n".join(txt))
