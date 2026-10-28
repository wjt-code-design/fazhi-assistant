"""回归门槛检查（2026-10-25）。

读取一次评测落盘结果（retrieval_*.json 或 citation_*.json），按阈值打印 PASS/FAIL。
默认**只报告不阻断**；加 `--strict` 才以非零退出码失败（供 CI 接入）。

阈值是「当前基线 + 安全边际」的临时值，等第三方金标复核完成后冻结。

用法：
  backend\\venv\\Scripts\\python.exe backend\\scripts\\check_regression.py ^
    docs\\benchmark_results\\citation_gen59_20261025.json --strict
"""

import argparse
import json
import sys


def detect_kind(data: dict) -> str | None:
    if "recall_article" in data:
        return "retrieval"
    if "citation_precision" in (data.get("summary") or {}):
        return "citation"
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("result", help="评测结果 JSON 路径")
    ap.add_argument("--strict", action="store_true", help="有 FAIL 时以退出码 1 结束")
    ap.add_argument("--max-hallucination", type=float, default=0.0)
    ap.add_argument("--max-leak", type=float, default=0.15)
    ap.add_argument("--min-precision", type=float, default=0.60)
    ap.add_argument("--min-recall4", type=float, default=0.84)  # 基线 0.8475，留 0.0075 波动余量
    ap.add_argument("--min-source4", type=float, default=0.95)
    ap.add_argument("--min-mrr6", type=float, default=0.75)
    a = ap.parse_args()

    data = json.load(open(a.result, encoding="utf-8"))
    kind = detect_kind(data)
    if kind is None:
        print(f"无法识别结果类型：{a.result}")
        return 2

    checks: list[tuple[str, float, str, float]] = []
    if kind == "citation":
        s = data["summary"]
        checks = [
            ("citation_hallucination_rate", s["citation_hallucination_rate"], "<=", a.max_hallucination),
            ("grounding_leak_rate", s["grounding_leak_rate"], "<=", a.max_leak),
            ("citation_precision", s["citation_precision"], ">=", a.min_precision),
        ]
    else:
        checks = [
            ("recall_article@4", data["recall_article"]["4"], ">=", a.min_recall4),
            ("recall_source@4", data["recall_source_4"], ">=", a.min_source4),
            ("MRR@6", data["mrr_at_6"], ">=", a.min_mrr6),
        ]

    failed = 0
    print(f"{a.result}  [{kind}]  n={data.get('n', (data.get('summary') or {}).get('n'))}")
    for name, actual, op, limit in checks:
        ok = actual <= limit if op == "<=" else actual >= limit
        failed += 0 if ok else 1
        print(f"  {'PASS' if ok else 'FAIL'}  {name} = {actual}  (要求 {op} {limit})")

    if failed:
        print(f"\n{failed} 项未达标（{'严格模式，退出 1' if a.strict else '仅报告，不阻断'}）")
        return 1 if a.strict else 0
    print("\n全部达标")
    return 0


if __name__ == "__main__":
    sys.exit(main())
