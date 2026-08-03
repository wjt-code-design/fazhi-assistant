"""基准趋势对比（组3-4）：扫描 docs/benchmark_results/*.json，逐类型对比 latest vs previous。

- 按文件名前缀分组（quality/robustness/consistency/redteam/hallucination/retrieval/
  relevance/latency_log/rate_limit/latency），时间戳统一 %Y%m%d-%H%M%S（2026-08-03 统一，
  旧 ISO 文件名仍可解析）。
- 数值方向感知：时延类指标（first_ms_* / total_ms_*）越低越好，其余数值越高越好。
- 输出 delta 表 + 回归标记（worse），落盘 docs/benchmark_results/trend_<ts>.json。

用法：cd backend && python scripts/benchmark_trend.py [--all]（--all 列出每组全部版本；默认 latest vs previous）
"""

import argparse
import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(os.path.dirname(HERE), "..", "docs", "benchmark_results")

# 时延类字段：越低越好（其余数值字段越高越好）
_LOWER_BETTER_KEYS = ("first_ms", "total_ms", "ms", "elapsed_s")

_TS_RE = re.compile(r"^(?P<y>\d{4})(?P<m>\d{2})(?P<d>\d{2})[-T](?P<H>\d{2})[-:]?(?P<M>\d{2})[-:]?(?P<S>\d{2})")


def _normalize_ts(s: str) -> str:
    """文件名时间戳归一为可排序 'YYYYMMDD-HHMMSS'。兼容 ISO 与紧凑两种格式。"""
    m = _TS_RE.match(s)
    if not m:
        return s
    g = m.groupdict()
    return f"{g['y']}{g['m']}{g['d']}-{g['H']}{g['M']}{g['S']}"


def _type_and_ts(fname: str) -> tuple[str, str]:
    base = fname[:-5]  # 去 .json
    parts = base.split("_", 1)
    typ = parts[0]
    ts = parts[1] if len(parts) > 1 else ""
    return typ, _normalize_ts(ts)


def _flatten_summary(summary) -> dict[str, float | str | bool]:
    """把 summary 展开成 {指标: 值}（嵌套 dict 拍平，非数值跳过）。"""
    out: dict[str, float | str | bool] = {}

    def walk(prefix, v):
        if isinstance(v, dict):
            for k, vv in v.items():
                walk(f"{prefix}.{k}" if prefix else k, vv)
        elif isinstance(v, (int, float)) and not isinstance(v, bool):
            out[prefix] = float(v)
        elif isinstance(v, bool) or isinstance(v, str):
            out[prefix] = v

    walk("", summary)
    return out


def _direction(key: str) -> int:
    return -1 if any(k in key for k in _LOWER_BETTER_KEYS) else 1  # -1=越低越好, 1=越高越好


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true", help="列出每组全部版本（默认只 latest vs previous）")
    args = ap.parse_args()

    groups: dict[str, dict[str, str]] = {}
    if not os.path.isdir(OUT_DIR):
        print(f"目录不存在：{OUT_DIR}")
        sys.exit(1)
    for fname in sorted(os.listdir(OUT_DIR)):
        if not fname.endswith(".json"):
            continue
        typ, ts = _type_and_ts(fname)
        groups.setdefault(typ, {})[ts] = fname

    lines: list[str] = []
    for typ in sorted(groups):
        versions = sorted(groups[typ])
        if len(versions) < 2:
            continue
        latest_ts, prev_ts = versions[-1], versions[-2]
        latest = json.load(open(os.path.join(OUT_DIR, groups[typ][latest_ts]), encoding="utf-8"))
        prev = json.load(open(os.path.join(OUT_DIR, groups[typ][prev_ts]), encoding="utf-8"))
        lsum, psum = _flatten_summary(latest.get("summary", latest)), _flatten_summary(prev.get("summary", prev))
        lines.append(f"\n== {typ}（{latest_ts} vs {prev_ts}）==")
        for key in sorted(set(lsum) | set(psum)):
            if key not in lsum or key not in psum:
                continue
            lv, pv = lsum[key], psum[key]
            if isinstance(lv, str) or isinstance(pv, str):
                lines.append(f"  {key}: {pv} → {lv}")
                continue
            d = lv - pv
            reg = "  ⚠ REGRESSION" if d * _direction(key) < 0 else ""
            lines.append(f"  {key}: {pv:>8} → {lv:>8}  (Δ {d:+.4f}){reg}")
        if args.all:
            for ts in versions[:-2]:
                j = json.load(open(os.path.join(OUT_DIR, groups[typ][ts]), encoding="utf-8"))
                lines.append(f"  · 旧版本 {ts}: {json.dumps(j.get('summary', {}), ensure_ascii=False)[:100]}")

    print("\n".join(lines) if lines else "无 ≥2 版本的指标组")
    os.makedirs(OUT_DIR, exist_ok=True)
    out = os.path.join(OUT_DIR, f"trend_{time.strftime('%Y%m%d-%H%M%S')}.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"report": lines}, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print(f"\n趋势报告落盘：{out}")


if __name__ == "__main__":
    main()
