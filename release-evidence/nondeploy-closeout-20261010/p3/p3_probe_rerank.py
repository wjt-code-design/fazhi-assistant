"""Why did RERANK_ENABLED=true send exactly one HTTP call and change no ordering?

Counts as rerank call 2/3 of the F2 rerank allowance. Prints only status code,
result count and index validity - never the response body, never the key.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import httpx
from langchain_core.documents import Document

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import p3_env  # noqa: E402
import p3_transport_guard as tg  # noqa: E402

CAND = Path(sys.argv[1])
QUERY = "试用期是否包含在劳动合同期限内"
DOCS = [
    "劳动合同法 第十九条 劳动合同期限三个月以上不满一年的，试用期不得超过一个月。",
    "劳动合同法 第二十条 劳动者在试用期的工资不得低于本单位相同岗位最低档工资。",
    "刑法 第十三条 一切危害社会的行为，依照法律应当受刑罚处罚的，都是犯罪。",
]


def main() -> int:
    env = p3_env.bind_private_root(p3_env.read_env())
    env["RERANK_ENABLED"] = "true"
    os.environ.update(env)
    guard = tg.TransportGuard(allowed=dict(p3_env.MODEL_HOSTS), max_calls=3)
    tg.install(guard)
    sys.path.insert(0, str(CAND / "backend"))
    import quota_utils  # noqa: E402
    import retrieval  # noqa: E402
    from settings import settings  # noqa: E402

    models = list(quota_utils.rerank_model_list())
    url = settings.rerank_base_url.rstrip("/") + "/rerank"
    print("model_list:", models)
    print("url host+path:", url.split("/")[2], "//" + "/".join(url.split("/")[3:]))
    print("siliconflow_branch:", models[0] in retrieval._SILICONFLOW_RERANK_MODELS if models else "EMPTY_LIST")
    key = settings.rerank_api_key or settings.siliconflow_api_key
    print("key present:", bool(key), "len:", len(key or ""))
    r = guard.post(url, json={"model": models[0], "query": QUERY, "documents": DOCS, "top_n": len(DOCS)},
                   headers={"Authorization": "Bearer " + (key or "")}, timeout=30.0)
    body = {} if not r.content else r.json()
    results = body.get("results") or []
    idx = [x.get("index") for x in results]
    print("status_code:", r.status_code)
    print("results_count:", len(results), "indices:", idx, "in_range:", all(isinstance(i, int) and 0 <= i < len(DOCS) for i in idx))
    print("unique_indices:", len(set(idx)) == len(idx))
    ordered = retrieval._rerank_docs(QUERY, [Document(page_content=d) for d in DOCS])
    print("_rerank_docs returned:", "None(degraded)" if ordered is None else [d.page_content[:14] for d in ordered])
    print("depleted_after:", sorted(quota_utils._depleted_mem))
    print("guard_calls:", len(guard.calls), "refused:", guard.refused)
    tg.uninstall()
    return 0


if __name__ == "__main__":
    sys.exit(main())
