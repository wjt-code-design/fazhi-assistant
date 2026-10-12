"""F2 rerank R-1/R-2/R-3, three calls total (the allowance Owner signed on 10-12).

Request body and response parsing mirror retrieval.py:163-180 / 216-221 verbatim, and the
expectations below are written BEFORE the call (they are the literals in GROUPS).
R-3 uses a relative criterion (its top score must be below R-1 and R-2 positives) because
an absolute threshold would be picked after seeing the numbers.
"""
from __future__ import annotations

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

GROUPS = [
    {"id": "R-1", "query": "试用期是否包含在劳动合同期限内，最长能约定多久",
     "docs": ["劳动合同法 第十九条 劳动合同期限三个月以上不满一年的，试用期不得超过一个月；一年以上不满三年的，试用期不得超过二个月；三年以上固定期限和无固定期限的劳动合同，试用期不得超过六个月。试用期包含在劳动合同期限内。",
              "劳动合同法 第二十条 劳动者在试用期的工资不得低于本单位相同岗位最低档工资或者劳动合同约定工资的百分之八十，并不得低于用人单位所在地的最低工资标准。",
              "民法典 第一百四十三条 具备下列条件的民事法律行为有效：行为人具有相应的民事行为能力；意思表示真实；不违反法律、行政法规的强制性规定，不违背公序良俗。"],
     "positive": 0, "distractor": 1, "expect": "positive must be rank 1 and ahead of distractor"},
    {"id": "R-2", "query": "什么是犯罪，情节显著轻微危害不大的是不是犯罪",
     "docs": ["刑法 第十三条 一切危害国家主权……以及其他危害社会的行为，依照法律应当受刑罚处罚的，都是犯罪，但是情节显著轻微危害不大的，不认为是犯罪。",
              "合成戊法 第十三条 （合成条文，非官方原文，干扰项）本法所称犯罪，是指危害社会的行为，一律应当受刑罚处罚，不存在情节显著轻微危害不大不认为是犯罪的情形。",
              "道路交通安全法 第九十一条 饮酒后驾驶机动车的，处暂扣六个月机动车驾驶证，并处一千元以上二千元以下罚款。"],
     "positive": 0, "distractor": 1, "expect": "official article with the proviso must outrank the synthetic absolute version"},
    {"id": "R-3", "query": "个人信息处理者向其他个人信息处理者提供个人信息应当取得单独同意吗",
     "docs": ["劳动合同法 第十九条 劳动合同期限三个月以上不满一年的，试用期不得超过一个月。",
              "刑法 第十三条 一切危害社会的行为，依照法律应当受刑罚处罚的，都是犯罪，但是情节显著轻微危害不大的，不认为是犯罪。",
              "道路交通安全法 第九十一条 饮酒后驾驶机动车的，处暂扣六个月机动车驾驶证。"],
     "positive": None, "distractor": None, "expect": "no positive exists; top score must stay below R-1 and R-2 positive scores"},
]


def main() -> int:
    env = p3_env.bind_private_root(p3_env.read_env())
    env["RERANK_ENABLED"] = "true"
    os.environ.update(env)
    guard = tg.TransportGuard(allowed=dict(p3_env.MODEL_HOSTS), max_calls=3)
    tg.install(guard)
    key = os.environ.get("RERANK_API_KEY") or os.environ.get("SILICONFLOW_API_KEY") or ""
    url = env_url = os.environ.get("RERANK_BASE_URL", "https://api.siliconflow.cn/v1").rstrip("/") + "/rerank"
    model = os.environ.get("RERANK_MODEL", "BAAI/bge-reranker-v2-m3")
    out = []
    for g in GROUPS:
        r = httpx.post(url, json={"model": model, "query": g["query"], "documents": g["docs"], "top_n": len(g["docs"])},
                       headers={"Authorization": "Bearer " + key}, timeout=30.0)
        data = r.json() if r.content else {}
        results = data.get("results") or []
        idx = [x.get("index", 0) for x in results]
        scores = {x.get("index"): round(float(x.get("relevance_score", 0.0)), 4) for x in results}
        rec = {"id": g["id"], "status": r.status_code, "model_echo": data.get("model"), "model_requested": model,
               "indices": idx, "unique_in_range": len(set(idx)) == len(idx) and all(0 <= i < len(g["docs"]) for i in idx),
               "rank_of_positive": (idx.index(g["positive"]) + 1) if g["positive"] is not None else None,
               "rank_of_distractor": (idx.index(g["distractor"]) + 1) if g["distractor"] is not None else None,
               "scores": scores, "top_score": max(scores.values()) if scores else None,
               "expect": g["expect"]}
        out.append(rec)
        print(json.dumps(rec, ensure_ascii=False, sort_keys=True))
    tg.uninstall()
    top = {r["id"]: r["top_score"] for r in out}
    verdict1 = out[0]["status"] == 200 and out[0]["rank_of_positive"] == 1 and out[0]["rank_of_distractor"] is not None and out[0]["rank_of_positive"] < out[0]["rank_of_distractor"]
    verdict2 = out[1]["status"] == 200 and out[1]["rank_of_positive"] == 1 and out[1]["rank_of_positive"] < out[1]["rank_of_distractor"]
    verdict3 = out[2]["status"] == 200 and top["R-3"] is not None and top["R-3"] < top["R-1"] and top["R-3"] < top["R-2"]
    allok = verdict1 and verdict2 and verdict3 and all(r["unique_in_range"] for r in out) and all(r["model_echo"] == r["model_requested"] or r["model_echo"] is None for r in out)
    print("R-1=%s R-2=%s R-3(rel)=%s" % (verdict1, verdict2, verdict3))
    print("sends=%d VERDICT=%s" % (len(guard.calls), "RERANK_GROUPS_PASS" if allok else "RERANK_GROUPS_FAIL"))
    (HERE / "logs" / "rerank-groups.json").write_text(json.dumps({"groups": out, "verdict": {"R-1": verdict1, "R-2": verdict2, "R-3_relative": verdict3, "all": allok}, "sends": len(guard.calls)}, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8", newline="\n")
    return 0 if allok else 1


if __name__ == "__main__":
    sys.exit(main())
