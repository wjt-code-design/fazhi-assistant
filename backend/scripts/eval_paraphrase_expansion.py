"""改写问法验收（方案 A，2026-10-25）。

读取第三方回执 docs/reviews/paraphrase_receipt_20261025.csv，按预注册标准执行：
1. 触发命中：同主题 3 条中命中 ≥2 条才保留；
2. 检索收益：保留词条在 3 条问法上的 recall@4 命中数 ≥ 基线，且至少救回 1 条基线未命中；
3. 回归：通过者合并后，59 题回归零回归、@1/MRR 不下降。

只读实验，不写 query_expansions.json；达标的词条在结果里列出，由人工确认后合并。

用法：backend\\venv\\Scripts\\python.exe backend\\scripts\\eval_paraphrase_expansion.py
"""

import csv
import json
import os
import re
import sys
import time

os.environ["HF_HUB_OFFLINE"] = "0"
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")

HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.dirname(HERE)
sys.path.insert(0, BACKEND)
sys.path.insert(0, HERE)
os.chdir(BACKEND)

from dotenv import load_dotenv  # noqa: E402

# override=True 与 main.py 一致：防 Machine 作用域旧 RERANK_API_KEY 压过 backend/.env（2026-10-26）
load_dotenv(os.path.join(BACKEND, ".env"), override=True)

from shadow_query_expansion import CANDIDATES  # noqa: E402

import retrieval  # noqa: E402

CSV_PATH = os.path.join(BACKEND, "..", "docs", "reviews", "paraphrase_receipt_20261025.csv")
DATA = os.path.join(BACKEND, "..", "data", "eval_set_gen_all.json")
OUT_DIR = os.path.join(BACKEND, "..", "docs", "benchmark_results")
HAN = re.compile(r"[\u4e00-\u9fff]")


def rank_of(docs, arts):
    for i, d in enumerate(docs):
        if d.metadata.get("article") in arts:
            return i + 1
    return None


def metrics(ranks):
    n = len(ranks)
    return {
        "recall_1": round(sum(1 for r in ranks.values() if r and r <= 1) / n, 4),
        "recall_4": round(sum(1 for r in ranks.values() if r and r <= 4) / n, 4),
        "mrr_6": round(sum((1.0 / r) if r else 0 for r in ranks.values()) / n, 4),
    }


def load_receipt():
    rows = list(csv.DictReader(open(CSV_PATH, encoding="utf-8-sig")))
    problems = []
    if len(rows) != 27:
        problems.append(f"行数 {len(rows)} != 27")
    for r in rows:
        if not all((r.get(k) or "").strip() for k in ("topic_id", "variant", "paraphrase")):
            problems.append(f"空字段 {r}")
        n_han = len(HAN.findall(r.get("paraphrase") or ""))
        if not 10 <= n_han <= 40:
            problems.append(f"{r['topic_id']}-{r['variant']} 汉字数 {n_han} 越界")
    return rows, problems


def main():
    rows, problems = load_receipt()
    by_topic = {}
    for r in rows:
        by_topic.setdefault(int(r["topic_id"]), []).append((r["variant"], r["paraphrase"].strip()))
    cases = {c["id"]: c for c in json.load(open(DATA, encoding="utf-8"))}
    exp_by_topic = {t: (trig, exp) for t, trig, exp in CANDIDATES}

    audit = []
    for topic, trig, _exp in CANDIDATES:
        hits = [v for v, p in by_topic.get(topic, []) if trig in p]
        audit.append(
            {
                "topic": topic,
                "trigger": trig,
                "hit_variants": hits,
                "hit_count": len(hits),
                "retained": len(hits) >= 2,
            }
        )

    retained = [a for a in audit if a["retained"]]
    per_topic = []
    for a in retained:
        topic = a["topic"]
        trig, exp = exp_by_topic[topic]
        arts = set(cases[topic]["expected_articles"])
        base = {}
        for v, p in by_topic[topic]:
            retrieval._cache.clear()
            base[v] = rank_of(retrieval.retrieve(p, k=6), arts)
        retrieval._QUERY_EXPANSIONS = list(retrieval._QUERY_EXPANSIONS) + [(trig, exp)]
        var = {}
        for v, p in by_topic[topic]:
            retrieval._cache.clear()
            var[v] = rank_of(retrieval.retrieve(p, k=6), arts)
        retrieval._QUERY_EXPANSIONS = list(retrieval._QUERY_EXPANSIONS)[:-1]
        b_hit = sum(1 for r in base.values() if r and r <= 4)
        v_hit = sum(1 for r in var.values() if r and r <= 4)
        fixed = [v for v in base if not (base[v] and base[v] <= 4) and (var[v] and var[v] <= 4)]
        passed = v_hit >= b_hit and len(fixed) >= 1
        per_topic.append(
            {
                "topic": topic,
                "trigger": trig,
                "expand": exp,
                "baseline": base,
                "variant": var,
                "baseline_hits": b_hit,
                "variant_hits": v_hit,
                "fixed": fixed,
                "passed": passed,
            }
        )

    selected = [x for x in per_topic if x["passed"]]
    regression = {}
    if selected:
        reg_cases = [c for c in cases.values() if c.get("track", "regression") == "regression"]
        retrieval._cache.clear()
        b = {c["id"]: rank_of(retrieval.retrieve(c["question"], k=6), set(c["expected_articles"])) for c in reg_cases}
        retrieval._cache.clear()
        retrieval._QUERY_EXPANSIONS = list(retrieval._QUERY_EXPANSIONS) + [
            (x["trigger"], x["expand"]) for x in selected
        ]
        v = {c["id"]: rank_of(retrieval.retrieve(c["question"], k=6), set(c["expected_articles"])) for c in reg_cases}
        broken = [i for i in b if (b[i] and b[i] <= 4) and not (v[i] and v[i] <= 4)]
        regression = {
            "baseline": metrics(b),
            "variant": metrics(v),
            "broken": broken,
            "zero_regression": len(broken) == 0,
            "recall1_not_lower": metrics(v)["recall_1"] >= metrics(b)["recall_1"],
            "mrr_not_lower": metrics(v)["mrr_6"] >= metrics(b)["mrr_6"],
        }

    out = {
        "ts": time.strftime("%Y%m%d-%H%M%S"),
        "receipt_rows": len(rows),
        "receipt_problems": problems,
        "audit": audit,
        "per_topic": per_topic,
        "selected": [{"topic": x["topic"], "trigger": x["trigger"], "expand": x["expand"]} for x in selected],
        "regression": regression,
        "decision": {
            "stop_rule_lt3": len([a for a in audit if a["retained"]]) < 3,
            "merge": len(selected) >= 3
            and bool(regression)
            and regression["zero_regression"]
            and regression["recall1_not_lower"]
            and regression["mrr_not_lower"],
        },
    }
    os.makedirs(OUT_DIR, exist_ok=True)
    jp = os.path.join(OUT_DIR, f"paraphrase_expansion_{out['ts']}.json")
    with open(jp, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
        f.write("\n")

    md = []
    md.append("# 改写问法验收（方案 A，2026-10-25）\n\n")
    md.append(f"回执：`{os.path.basename(CSV_PATH)}`，{len(rows)} 行；校验问题：{problems or '无'}。\n\n")
    md.append("## 触发命中（预注册：≥2/3 才保留）\n\n")
    md.append("| 主题 | trigger | 命中变体 | 命中数 | 保留 |\n|---|---|---|---|---|\n")
    for a in audit:
        md.append(
            f"| {a['topic']} | {a['trigger']} | {a['hit_variants']} | {a['hit_count']}/3 | {'是' if a['retained'] else '否'} |\n"
        )
    md.append("\n## 保留词条的检索收益\n\n")
    md.append(
        "| 主题 | trigger | 基线 rank（v1/v2/v3） | 扩展 rank | @4 命中 | 救回 | 通过 |\n|---|---|---|---|---|---|---|\n"
    )
    for x in per_topic:
        b = "/".join(str(x["baseline"][v]) for v in ("v1", "v2", "v3"))
        v = "/".join(str(x["variant"][k]) for k in ("v1", "v2", "v3"))
        md.append(
            f"| {x['topic']} | {x['trigger']} | {b} | {v} | {x['baseline_hits']}→{x['variant_hits']} | {x['fixed'] or '无'} | {'是' if x['passed'] else '否'} |\n"
        )
    md.append("\n## 回归（合并选中词条后，59 题）\n\n")
    if regression:
        b, v = regression["baseline"], regression["variant"]
        md.append("| 运行 | recall@1 | recall@4 | MRR@6 |\n|---|---|---|---|\n")
        md.append(f"| 基线 | {b['recall_1']} | {b['recall_4']} | {b['mrr_6']} |\n")
        md.append(f"| 选中扩展 | {v['recall_1']} | {v['recall_4']} | {v['mrr_6']} |\n\n")
        md.append(f"- 回归题号：{regression['broken'] or '无'}\n")
    else:
        md.append("无通过词条，未跑回归。\n")
    md.append("\n## 裁决\n\n")
    md.append(f"- 保留（命中≥2/3）：{[a['topic'] for a in audit if a['retained']]}\n")
    md.append(f"- 通过检索收益：{[x['topic'] for x in selected]}\n")
    md.append(f"- 触发停止条件（保留<3）：{'是' if out['decision']['stop_rule_lt3'] else '否'}\n")
    md.append(f"- **合并：{'是' if out['decision']['merge'] else '否'}**\n")
    mp = os.path.join(OUT_DIR, f"paraphrase_expansion_{out['ts']}.md")
    open(mp, "w", encoding="utf-8").write("".join(md))
    print(json.dumps(out["decision"], ensure_ascii=False), json.dumps(regression, ensure_ascii=False))
    print("落盘", jp)
    print("落盘", mp)


if __name__ == "__main__":
    main()
