# -*- coding: utf-8 -*-
"""evals/frozen-cases-v2.json 金标校验（防幻觉第一道：确定性核验）

检查项：
1. 结构：JSON 合法、id 唯一、判据字段类型正确、新案例 fact_reveal 自包含
2. 条号存在性：所有 required_laws / forbidden_articles 经 retrieval.article_in_kb 确定性核验
   （required 缺库 = 评测假红，必须 0；forbidden 缺库 = 判据无意义，报告但不致红）
3. 逐字复用：C01-C10 与 release-evidence v1 题集深度相等（v1 为真源，防双份分叉）

用法（backend venv）：
  backend\\venv\\Scripts\\python.exe evals\\validate_cases.py
退出码 0=全绿；非 0=有 FAIL。
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
BACKEND = REPO / "backend"
V1_PATH = REPO / "release-evidence" / "legal-agent-v1-complex-v1-20260907" / "frozen-cases-v1.json"
V2_PATH = REPO / "evals" / "frozen-cases-v2.json"

# 复刻后端环境（与探针一致：本地 embedding，不联网）
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
sys.path.insert(0, str(BACKEND))
os.chdir(BACKEND)
from dotenv import load_dotenv  # noqa: E402

load_dotenv(override=True)

from retrieval import article_in_kb  # noqa: E402

V1_FIELDS = [
    "id", "domain", "initial_question", "round1_facts", "round2_facts",
    "required_issues", "required_laws", "critical_failures", "deciding_facts",
]


def _art(source: str, n: int) -> str:
    """题集条号 int → article_in_kb 完整形式（后端 _normalize_article 归一口径）。"""
    return f"第{n}条"


def main() -> int:
    fails: list[str] = []
    warns: list[str] = []
    v2 = json.loads(V2_PATH.read_text(encoding="utf-8"))
    v1 = json.loads(V1_PATH.read_text(encoding="utf-8"))
    cases = v2["cases"]
    by_id = {c["id"]: c for c in cases}
    print(f"V2 cases: {len(cases)} (expect 20)")
    if len(cases) != 20:
        fails.append(f"案例数 {len(cases)} != 20")
    if len(by_id) != len(cases):
        fails.append("存在重复 id")

    # 1) 逐字复用校验（C01-C10 原 9 字段与 v1 深度相等）
    v1_by_id = {c["id"]: c for c in v1["cases"]}
    for cid, c1 in v1_by_id.items():
        c2 = by_id.get(cid)
        if c2 is None:
            fails.append(f"{cid}: v2 缺 v1 案例")
            continue
        for f in V1_FIELDS:
            if c1.get(f) != c2.get(f):
                fails.append(f"{cid}.{f}: 与 v1 不一致（真源为 v1，禁止改写字段）")

    # 2) 条号存在性（required 必须全在库；forbidden 在库=判据可测，缺库=仅告警）
    n_req = n_forb = 0
    for c in cases:
        for src, n in c.get("required_laws", []):
            n_req += 1
            if not article_in_kb(src, _art(src, n)):
                fails.append(f"{c['id']}: required {src}#{n} 不在知识库（评测将假红）")
        for src, n in c.get("forbidden_articles", []):
            n_forb += 1
            if not article_in_kb(src, _art(src, n)):
                warns.append(f"{c['id']}: forbidden {src}#{n} 不在库（混入不可能发生，判据空转）")

    # 3) 新案例结构契约
    for c in cases:
        if not c["id"].startswith("E"):
            continue
        if "forbidden_articles" not in c:
            fails.append(f"{c['id']}: 缺 forbidden_articles")
        if not isinstance(c.get("scope_trigger"), bool):
            fails.append(f"{c['id']}: scope_trigger 必须为 bool")
        fr = c.get("fact_reveal")
        if not fr or "r1" not in fr:
            fails.append(f"{c['id']}: fact_reveal 缺失或无 r1")
            continue
        for rnd, units in fr.items():
            for i, u in enumerate(units):
                if not u.get("text") or not u.get("keywords"):
                    fails.append(f"{c['id']}.{rnd}[{i}]: fact_reveal 单元缺 text/keywords")

    for w in warns:
        print("WARN:", w)
    for f in fails:
        print("FAIL:", f)
    print(f"checked: required_laws={n_req} forbidden_articles={n_forb} fails={len(fails)} warns={len(warns)}")
    print("VALIDATION " + ("PASS" if not fails else "FAIL"))
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
