"""查询扩展影子实验 E0/E1（2026-10-25）。

只读实验：不写 query_expansions.json、不改生产代码。
- E0：不加候选词条，跑两遍 59 题，测 rerank 运行间波动；
- E1：把候选词条 patch 进 retrieval._QUERY_EXPANSIONS，再跑一遍；
- 逐题对比 rank，输出 JSON + Markdown，并按方案 DoD 自动判定。

用法：backend\\venv\\Scripts\\python.exe backend\\scripts\\shadow_query_expansion.py
"""

import argparse
import json
import os
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

load_dotenv(os.path.join(BACKEND, ".env"))

import retrieval  # noqa: E402

DATA = os.path.join(BACKEND, "..", "data", "eval_set_gen_all.json")
OUT_DIR = os.path.join(BACKEND, "..", "docs", "benchmark_results")
KS = (1, 4)

# (target_id, trigger, expand)
CANDIDATES = [
    (101, "答应送", "赠与合同 撤销赠与 权利转移前"),
    (103, "一审的裁定", "第二审 裁定 驳回上诉 撤销变更"),
    (108, "保险公司违法", "直接负责的主管人员 警告 罚款 撤销任职资格"),
    (113, "处置抵押物", "重整期间 担保权 暂停行使"),
    (117, "证人提问", "询问证人 审判人员许可 质证"),
    (133, "取保候审", "保证人义务 监督 报告 罚款"),
    (140, "犯罪记录", "密切接触未成年人 查询义务 招用 违法犯罪记录"),
    (141, "安全生产检查", "安全生产监督检查 配合 不得拒绝阻挠"),
    (153, "方便群众", "行政复议 信息化建设 便民 申请"),
]


def rank_of(docs, arts):
    for i, d in enumerate(docs):
        if d.metadata.get("article") in arts:
            return i + 1
    return None


def run(cases):
    retrieval._cache.clear()
    out = {}
    for c in cases:
        docs = retrieval.retrieve(c["question"], k=6)
        out[c["id"]] = rank_of(docs, set(c["expected_articles"]))
    return out


def metrics(ranks):
    n = len(ranks)
    return {
        "recall_1": round(sum(1 for r in ranks.values() if r and r <= 1) / n, 4),
        "recall_4": round(sum(1 for r in ranks.values() if r and r <= 4) / n, 4),
        "mrr_6": round(sum((1.0 / r) if r else 0 for r in ranks.values()) / n, 4),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=DATA, help="题库路径；默认 59 题回归集")
    ap.add_argument("--external", action="store_true", help="对外集模式：只验零回归，不套 recall 门槛")
    args = ap.parse_args()
    cases = json.load(open(args.data, encoding="utf-8"))
    if not args.external:
        cases = [c for c in cases if c.get("track", "regression") == "regression"]
    ids = [c["id"] for c in cases]
    questions = {c["id"]: c["question"] for c in cases}

    b1 = run(cases)
    b2 = run(cases)
    noise = [i for i in ids if (b1[i] and b1[i] <= 4) != (b2[i] and b2[i] <= 4)]

    retrieval._QUERY_EXPANSIONS = list(retrieval._QUERY_EXPANSIONS) + [(t, e) for _, t, e in CANDIDATES]
    v = run(cases)

    m1, m2, mv = metrics(b1), metrics(b2), metrics(v)
    broken = [i for i in ids if (b2[i] and b2[i] <= 4) and not (v[i] and v[i] <= 4)]
    fixed = [i for i in ids if not (b2[i] and b2[i] <= 4) and (v[i] and v[i] <= 4)]
    changed = [{"id": i, "base": b2[i], "variant": v[i]} for i in ids if b2[i] != v[i]]

    trigger_audit = []
    for target, trig, exp in CANDIDATES:
        hit = [i for i in ids if trig in questions[i]]
        trigger_audit.append(
            {
                "target": target,
                "trigger": trig,
                "expand": exp,
                "hit_ids": hit,
                "non_target": [i for i in hit if i != target],
                "target_hit": target in hit,
            }
        )

    dod = {
        "zero_regression": len(broken) == 0,
        "baseline_noise_le_1": len(noise) <= 1,
    }
    if not args.external:
        dod.update(
            {
                "recall4_ge_0_90": mv["recall_4"] >= 0.90,
                "recall1_not_lower": mv["recall_1"] >= m2["recall_1"],
                "mrr_not_lower": mv["mrr_6"] >= m2["mrr_6"],
            }
        )
    out = {
        "ts": time.strftime("%Y%m%d-%H%M%S"),
        "n": len(cases),
        "candidates": [{"target": t, "trigger": tr, "expand": e} for t, tr, e in CANDIDATES],
        "trigger_audit": trigger_audit,
        "baseline1": m1,
        "baseline2": m2,
        "variant": mv,
        "baseline_noise_ids": noise,
        "broken": broken,
        "fixed": fixed,
        "changed": changed,
        "ranks": {str(i): {"b1": b1[i], "b2": b2[i], "v": v[i]} for i in ids},
        "dod": dod,
    }
    os.makedirs(OUT_DIR, exist_ok=True)
    prefix = "query_expansion_shadow_external" if args.external else "query_expansion_shadow"
    jp = os.path.join(OUT_DIR, f"{prefix}_{out['ts']}.json")
    with open(jp, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
        f.write("\n")

    md = []
    md.append(f"# 查询扩展影子实验 {'E3 对外集' if args.external else 'E0/E1'}（2026-10-25）\n\n")
    md.append(
        f"{len(cases)} 题（`{os.path.basename(args.data)}`）；候选词条 {len(CANDIDATES)} 条；同进程跑基线两遍 + 扩展一遍。\n\n"
    )
    md.append("## 指标\n\n")
    md.append("| 运行 | recall@1 | recall@4 | MRR@6 |\n|---|---|---|---|\n")
    md.append(f"| 基线第 1 遍 | {m1['recall_1']} | {m1['recall_4']} | {m1['mrr_6']} |\n")
    md.append(f"| 基线第 2 遍 | {m2['recall_1']} | {m2['recall_4']} | {m2['mrr_6']} |\n")
    md.append(f"| 扩展后 | {mv['recall_1']} | {mv['recall_4']} | {mv['mrr_6']} |\n\n")
    md.append(f"- 基线两遍 @4 翻转：{noise or '无'}（≤1 题才认为波动可接受）\n")
    md.append(f"- 救回：{fixed or '无'}\n")
    md.append(f"- 回归：{broken or '无'}\n\n")
    md.append("## DoD\n\n")
    md.append("| 条件 | 结果 |\n|---|---|\n")
    for k, ok in dod.items():
        md.append(f"| {k} | {'PASS' if ok else 'FAIL'} |\n")
    md.append("\n## 触发词审计\n\n")
    md.append("| 目标题 | trigger | 命中题号 | 非目标命中 | target 是否命中 |\n|---|---|---|---|---|\n")
    for a in trigger_audit:
        md.append(
            f"| {a['target']} | {a['trigger']} | {a['hit_ids']} | {a['non_target']} | {'是' if a['target_hit'] else '否'} |\n"
        )
    md.append("\n## 逐题变化\n\n")
    md.append("| id | 基线 rank | 扩展 rank |\n|---|---|---|\n")
    for c in changed:
        md.append(f"| {c['id']} | {c['base']} | {c['variant']} |\n")
    if not changed:
        md.append("| — | 无变化 | — |\n")
    md.append("\n## 说明\n\n")
    md.append("- 本实验不修改生产词表；只有 DoD 全 PASS 才考虑合并。\n")
    md.append("- rank 为期望条文在 top-6 中的位置，None 表示未命中。\n")
    md.append("- 基线两遍用于估计 rerank 波动；若翻转 >1 题，单次差异不可采信。\n")
    mp = os.path.join(OUT_DIR, f"{prefix}_{out['ts']}.md")
    open(mp, "w", encoding="utf-8").write("".join(md))

    print(
        json.dumps(
            {
                "baseline1": m1,
                "baseline2": m2,
                "variant": mv,
                "noise": noise,
                "fixed": fixed,
                "broken": broken,
                "dod": dod,
            },
            ensure_ascii=False,
        )
    )
    print("落盘", jp)
    print("落盘", mp)


if __name__ == "__main__":
    main()
