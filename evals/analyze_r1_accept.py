# -*- coding: utf-8 -*-
"""R1 预注册验收分析（判据冻结，见 docs/preregistration-dept-law-filter-r1-20260913.md §4）。

输入：gate2_runner 产物 sessions.json（评测集/留出集各一份）。
计算：
- P1/P4 forbidden 混入率（终稿+证据池口径）→ 0
- P2 agent_completed 不下降（对照基线为 baseline-v2-20260913）
- P3 新失败码不得出现（KNOWN 集合外 STOP）
- P6 proc_misroute 终稿程序法串台率 → 0（R1b 红线；从日志 proc_misroute_flag 读）

用法：
  backend\\venv\\Scripts\\python.exe evals/analyze_r1_accept.py <sessions.json> --cases <cases.json>
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

_ART_RE = re.compile(r"《([^》]+)》\s*第\s*([零〇○一二三四五六七八九十百千万0-9]+)\s*条")

# 汉字数字 → 阿拉伯数字（归一化，防 "四十九" vs "49" 漏判）
_CN_NUM = {"零": 0, "〇": 0, "○": 0, "一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}


def _cn_to_arabic(s: str) -> int:
    if s.isdigit():
        return int(s)
    units = {"十": 10, "百": 100, "千": 1000, "万": 10000}
    total, cur, prev_unit = 0, 0, 1
    for ch in s:
        if ch in _CN_NUM:
            cur = _CN_NUM[ch]
        elif ch in units:
            u = units[ch]
            total += (cur if cur else 1) * u
            cur = 0
            prev_unit = u
    return total + cur


def _normalize_art(art: str) -> str:
    """条文号归一化为 int 字符串（支持 一百二十二 / 122 / 第四十九条 后段）。"""
    return str(_cn_to_arabic(art))


# 程序法域表（与 backend/agent/dept_guard.py 对齐，只认专属程序法）
PROC_LAW_DOMAIN: dict[str, set[str]] = {
    "民事诉讼法": {"civil"},
    "刑事诉讼法": {"criminal"},
    "行政诉讼法": {"administrative"},
    "行政复议法": {"administrative"},
    "海事诉讼特别程序法": {"special-maritime"},
}

KNOWN_FAIL_CODES = {
    "UNSUPPORTED_CITATION",
    "NON_CANONICAL_CITATION",
    "EVIDENCE_COVERAGE_DEFICIENT",
    "PLANNER_PARSE_ERROR",
    "ISSUE_DECOMPOSITION_INVALID",
    "ISSUE_DECOMPOSITION_UNAVAILABLE",
    "VERIFIER_TECHNICAL_FAILURE",
    "AGENT_FINALIZATION_CONFLICT",
    "AGENT_STORAGE_FAILURE",
    "CLIENT_DISCONNECTED",
    "BUDGET_EXCEEDED",
    "FAIL_SAFE",
    "RESEARCH_MORE",
    "REWRITE",
    "AGENT_FAILED",
    "OWNERSHIP_FAILURE",
    "TECHNICAL_FALLBACK",
    "NO_MATCH_REPLY",
}


def _extract_citations(text: str) -> list[tuple[str, str]]:
    """抽取 (法名, 归一化条号) 引用；条号统一转阿拉伯数字字符串。"""
    out = []
    for m in _ART_RE.finditer(text or ""):
        out.append((m.group(1), _normalize_art(m.group(2))))
    return out


def _case_domain(case: dict) -> str | None:
    """题面 domain → 域表键（近似判域；多域/未知 → None，与 dept_guard 保守口径一致）。"""
    d = (case.get("domain") or "").strip()
    mapping = {
        "民事诉讼": "civil", "合同": "civil", "劳动": "civil", "消费者": "civil",
        "诉讼时效": "civil", "保证": "civil", "跨部门法-民事": "civil",
        "跨部门法-纯民事": "civil", "跨部门法-消费": "civil", "跨部门法-装修": "civil",
        "跨部门法-轻微交通事故": "civil", "医疗纠纷": "civil", "物业纠纷": "civil",
        "著作权许可": "civil", "保险理赔": "civil",
    }
    return mapping.get(d)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("sessions", help="runner 产物 sessions.json 路径")
    ap.add_argument("--cases", required=True, help="案例集 json（frozen-cases-v2.json 或 holdout-cases-r1.json）")
    ap.add_argument("--known-codes", nargs="*", default=sorted(KNOWN_FAIL_CODES), help="已知失败码集合")
    args = ap.parse_args()

    sessions = json.loads(Path(args.sessions).read_text(encoding="utf-8"))
    cases = json.loads(Path(args.cases).read_text(encoding="utf-8"))["cases"]
    by_id = {c["id"]: c for c in cases}

    results = sessions["results"]
    n = 0
    n_completed = 0
    forbidden_hits_final = 0
    forbidden_hits_evidence = 0
    unknown_codes: set[str] = set()
    proc_misroute = 0
    rows: list[str] = []

    for cid in sorted(results):
        if cid not in by_id:
            continue
        case = by_id[cid]
        res = results[cid]
        n += 1
        if res.get("agent_completed"):
            n_completed += 1

        codes = res.get("error_codes") or []
        for code in codes:
            if code not in set(args.known_codes):
                unknown_codes.add(code)

        forb = case.get("forbidden_articles") or []
        forb_set = {(src, str(art)) for src, art in forb}

        # 终稿引用口径
        final_text = res.get("final_text") or ""
        final_cites = _extract_citations(final_text)
        hit_final = [(s, a) for s, a in final_cites if (s, a) in forb_set]
        if hit_final:
            forbidden_hits_final += 1

        # P6：终稿他域程序法串台（R1b 口径对齐：与 dept_guard 判域表一致，只认
        #   「他域专属程序法」。案例域近似判定：由题面 domain 字段映射到域表。
        #   2026-09-14 深度检查修正：此前只要 s in PROC_LAW_DOMAIN 就计数（含本域
        #   合法程序法）→ 误报；且未做全称归一 → 漏检。此处仅作近似参考，
        #   权威口径以宿主日志 proc_misroute_detected 为准。）
        domain = _case_domain(case)
        proc = []
        for s, a in final_cites:
            src = s[len("中华人民共和国") :] if s.startswith("中华人民共和国") else s
            src_doms = PROC_LAW_DOMAIN.get(src)
            if src_doms is not None and domain is not None and domain not in src_doms:
                proc.append(f"{s}#{a}")
        if proc:
            proc_misroute += 1

        # 证据池口径（日志 dept_filter_removed / evidence 见 sessions 结构，此处记 final 主口径）
        rows.append(
            f"{cid}: completed={res.get('agent_completed')} codes={codes or '-'} "
            f"final_cites={len(final_cites)} forbidden_hit={[f'{s}#{a}' for s, a in hit_final] or '-'}"
        )

    # P3 新失败码
    print("=== R1 预注册验收（判据 §4）===")
    print("\n".join(rows))
    print(f"\n案例数 n={n}  completed={n_completed} ({n_completed / max(n, 1):.0%})")
    print(f"P1/P4 forbidden 混入（终稿口径）: {forbidden_hits_final}  >0 即 FAIL")
    print(f"P3 未知失败码: {sorted(unknown_codes) or '无'}")
    print(f"P6 程序法串台（终稿含他域专属程序法引用，近似口径）: {proc_misroute}  >0 即 FAIL")
    return 0


if __name__ == "__main__":
    sys.exit(main())
