"""T7 只读重算探针：对真实 qa_pairs 集合现算 options_fingerprint 覆盖。

只读：仅用 collection.get / .count；绝不 add/update/delete。
不写任何语料；唯一写盘 = 本目录的 recompute.json（交付物）。
复用的安全取集入口：dispatch-output/hij-i-20260920/_qa_corpus.py
（守卫：集合名含 qa_pairs 且条数==279，否则停手不返回）。
"""

import json
import os
import pathlib
import sys

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

REPO = pathlib.Path(r"C:/Users/33393/Desktop/ai-legal-helper")
DELIV = REPO / "dispatch-output" / "t7-fingerprint-coverage-20260920"
sys.path.insert(0, str(REPO / "backend"))
sys.path.insert(0, str(REPO / "dispatch-output" / "hij-i-20260920"))

from dotenv import load_dotenv

load_dotenv(REPO / "backend" / ".env")


# ---- 1. 主集合 qa_pairs（279）----
# 复用 _qa_corpus 的守卫逻辑，但把诊断直接落盘（避免 sys.exit 吞掉信息）
import chromadb  # noqa
import knowledge_service as KS  # _qa_store
import query_understand as qu  # 指纹函数 _options_fingerprint

log = []
try:
    col = KS._qa_store._collection
    name = str(getattr(col, "name", "") or "")
    data0 = col.get(include=["metadatas"])
    n_actual = len(data0.get("ids") or [])
    log.append(f"name={name!r} n_actual={n_actual}")
    if "qa_pairs" not in name:
        raise SystemExit("集合名不含 qa_pairs，取错对象，停手")
    if n_actual != 279:
        log.append(f"⚠️ 条数 {n_actual} != 279（语料已变？），仍按实际条数清点并标注")
    data = col.get(include=["metadatas", "documents"])
except Exception as e:
    (DELIV / "_probe.log").write_text(
        "GUARD-ERR: {!r}\n{}".format(e, "\n".join(log)), encoding="utf-8", newline=""
    )
    raise
N_guard_note = f"count={n_actual} (expect 279)"
data = col.get(include=["metadatas", "documents"])
ids = list(data.get("ids") or [])
metas = list(data.get("metadatas") or [])
docs = list(data.get("documents") or [])
N = len(ids)

stored_key = 0  # options_fingerprint 键存在
stored_nonempty = 0  # 键存在且值非空（= 旧 60 候选）
recomp_nonempty = 0  # 现算非空的条数（= 带选项、理论上可提取）
origin_dist = {}
keys_dist = {}
gap_examples = []

both_nonempty = 0  # 已正确指纹
stored_empty_recomp_has = 0  # 缺口：存空/无值但现算有选项（补采可补）
stored_nonempty_recomp_none = 0  # 异常：存了非空但现算无选项
both_empty = 0
no_key_recomp_has = 0
no_key_recomp_none = 0

for i in range(N):
    m = metas[i] or {}
    q = docs[i] or ""
    rfp = qu._options_fingerprint(q)  # 现算
    has_key = "options_fingerprint" in m
    sval = m.get("options_fingerprint")
    s_ne = bool(sval)
    r_ne = bool(rfp)
    if has_key:
        stored_key += 1
        if s_ne:
            stored_nonempty += 1
    if r_ne:
        recomp_nonempty += 1
    origin = m.get("origin", "<none>")
    origin_dist[origin] = origin_dist.get(origin, 0) + 1
    for k in m:
        keys_dist[k] = keys_dist.get(k, 0) + 1
    if has_key and s_ne and r_ne:
        both_nonempty += 1
    elif has_key and (not s_ne) and r_ne:
        stored_empty_recomp_has += 1
        if len(gap_examples) < 12:
            gap_examples.append(
                {
                    "id": ids[i],
                    "origin": origin,
                    "stored_fp": sval,
                    "recomp_fp_head": rfp[:40],
                    "q_head": q[:70],
                }
            )
    elif has_key and s_ne and (not r_ne):
        stored_nonempty_recomp_none += 1
    elif has_key and (not s_ne) and (not r_ne):
        both_empty += 1
    elif (not has_key) and r_ne:
        no_key_recomp_has += 1
    else:
        no_key_recomp_none += 1

# ---- 2. 另一个集合 qa_pairs_te4（21 条，口径隔离，绝不混算）----
te4 = {}
try:
    from langchain_chroma import Chroma
    from rag_chain import CHROMA_DIR, embeddings

    te4_store = Chroma(
        persist_directory=CHROMA_DIR,
        embedding_function=embeddings,
        collection_name="qa_pairs_te4",
    )
    te4_col = te4_store._collection
    te4_data = te4_col.get(include=["metadatas"])
    te4_ids = list(te4_data.get("ids") or [])
    te4_metas = list(te4_data.get("metadatas") or [])
    te4["count"] = len(te4_ids)
    te4["fp_key_present"] = sum(
        1 for mm in te4_metas if "options_fingerprint" in (mm or {})
    )
    te4["fp_nonempty"] = sum(
        1 for mm in te4_metas if (mm or {}).get("options_fingerprint")
    )
    te4["note"] = "与 qa_pairs 完全隔离，本卡不计入分母/分子"
except Exception as e:  # noqa: BLE001 - te4 探测失败不阻塞主清点
    te4 = {"error": repr(e)}

result = {
    "card": "T7",
    "counted_collection": "qa_pairs",
    "guard": N_guard_note,
    "denominator_clarification": "分母对谁：见 coverage 两档口径；qa_pairs_te4(21) 单独隔离不混入",
    "total_records_qa_pairs": N,
    "stored_state": {
        "options_fingerprint_key_present": stored_key,
        "options_fingerprint_nonempty": stored_nonempty,
        "options_fingerprint_empty_or_absent": N - stored_nonempty,
    },
    "recomputed_state": {
        "options_fingerprint_nonempty_now": recomp_nonempty,
        "meaning": "对当前 qa_pairs 全部记录用 _options_fingerprint 现算一遍，非空的条数 = 带真实选项、理论上可提取指纹的条数",
    },
    "crosstab": {
        "A_both_nonempty_already_fingerprinted": both_nonempty,
        "B_stored_empty_but_has_options_gap_fillable": stored_empty_recomp_has,
        "C_stored_nonempty_but_no_options_anomaly": stored_nonempty_recomp_none,
        "D_both_empty_no_options": both_empty,
        "E_no_key_but_has_options": no_key_recomp_has,
        "F_no_key_no_options": no_key_recomp_none,
    },
    "gap_examples": gap_examples,
    "origin_distribution": origin_dist,
    "metadata_keys_distribution": keys_dist,
    "qa_pairs_te4_separate": te4,
    "coverage": {
        "current_over_total_279": {
            "numerator": stored_nonempty,
            "denominator": N,
            "fraction": round(stored_nonempty / N, 4),
        },
        "current_over_option_records": {
            "numerator": stored_nonempty,
            "denominator": recomp_nonempty,
            "fraction": round(stored_nonempty / recomp_nonempty, 4)
            if recomp_nonempty
            else None,
            "note": "指纹只对带选项记录有意义，这是更公平的分母",
        },
        "after_backfill_over_total_279": {
            "numerator": recomp_nonempty,
            "denominator": N,
            "fraction": round(recomp_nonempty / N, 4),
            "gain_records": recomp_nonempty - stored_nonempty,
        },
        "after_backfill_over_option_records": {
            "numerator": recomp_nonempty,
            "denominator": recomp_nonempty,
            "fraction": 1.0,
            "note": "补采后带选项记录 100% 有指纹",
        },
    },
}

out = DELIV / "recompute.json"
out.write_text(
    json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8", newline=""
)
# 同时落一份到 _probe.log 便于审阅（交付物之外的过程留痕）
(DELIV / "_probe.log").write_text(
    json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8", newline=""
)
print("WROTE", out)
print(f"total={N} stored_nonempty={stored_nonempty} recomp_nonempty={recomp_nonempty}")
