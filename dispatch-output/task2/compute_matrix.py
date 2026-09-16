"""RAG 对照矩阵机械列复算脚本（task2/rag-matrix.md 的数据来源）。
用法：python compute_matrix.py
"""
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
CASES = json.loads((REPO / "release-evidence/legal-agent-v1-complex-v1-20260907/frozen-cases-v1.json").read_text(encoding="utf-8"))["cases"]


def zh(num: int) -> str:
    u = ["", "十", "百", "千"]
    s = str(num)
    out = ""
    z = False
    for i, ch in enumerate(s):
        d = int(ch)
        pos = len(s) - i - 1
        if d == 0:
            z = True
            continue
        if z and out:
            out += "零"
        z = False
        if not (d == 1 and pos == 1 and not out):
            out += "一二三四五六七八九"[d - 1]
        out += u[pos]
    return out


def final_text(raw: str) -> str:
    txt = []
    for part in raw.split("\n\n"):
        line = part.strip()
        if line.startswith("data: ") and "[DONE]" not in line:
            try:
                e = json.loads(line[6:])
                if e.get("content"):
                    txt.append(str(e["content"]))
            except json.JSONDecodeError:
                pass
    return "".join(txt)


def main() -> None:
    for c in CASES:
        for mode in ["rag-initial", "rag-full-facts"]:
            p = HERE / f"{c['id']}-{mode}.raw"
            raw = p.read_text(encoding="utf-8").split("\n", 1)[1]
            t = final_text(raw)
            hits = 0
            for iss in c["required_issues"]:
                core = [w for w in re.split(r"[，、与和的/（）()]", iss) if len(w) >= 3]
                if core and any(w[:4] in t or w in t for w in core):
                    hits += 1
            law_hits = [f"{src}:{art}" for src, art in c["required_laws"] if f"《{src}》第{zh(art)}条" in t]
            gap = bool(re.search(r"(需要了解|请提供|建议补充|信息不足|无法确定|需要确认|视.{0,6}情况|分情形|取决于)", t))
            err = "restart" in raw or '"type": "error"' in raw
            print(f"{c['id']} | {mode} | {hits}/{len(c['required_issues'])} | {gap} | {len(law_hits)}/{len(c['required_laws'])} | {'有《》引用' if '《' in t else '无引用'} | {'ERR' if err else 'OK'}")


if __name__ == "__main__":
    main()
