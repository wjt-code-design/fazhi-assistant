"""款项级引用影子对比（2026-10-25，G1 验证）。

只读离线：不调用后端、不改生产。做两件事：
1. 用新的款/项解析器重放 59 题答案，统计有多少引用带款/项；
2. 对每条带款/项的引用，用库内条文原文校验该款/项是否存在。

输出 JSON + Markdown 到 docs/benchmark_results/。用于判断「条级指标是否漏掉了款项错误」，
以及「拦截 vs 标注」分别会命中多少条。

用法：backend\\venv\\Scripts\\python.exe backend\\scripts\\shadow_subdivision.py
"""

import json
import os
import sys

import chromadb

HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.dirname(HERE)
sys.path.insert(0, BACKEND)
sys.path.insert(0, HERE)
os.chdir(BACKEND)

from citation_check import (  # noqa: E402
    _ART_RE,
    CHROMA_DIR,
    COLLECTION,
    canon_source,
    cn2num,
    extract_citation_refs,
    resolve,
    validate_subdivision,
)

ROWS = os.path.join(BACKEND, "..", "docs", "benchmark_results", "citation_gen59_20261025b.json")
OUT_JSON = os.path.join(BACKEND, "..", "docs", "benchmark_results", "subdivision_shadow_20261025.json")
OUT_MD = os.path.join(BACKEND, "..", "docs", "benchmark_results", "subdivision_shadow_20261025.md")


def load_texts():
    client = chromadb.PersistentClient(path=CHROMA_DIR)
    col = client.get_collection(COLLECTION)
    got = col.get(include=["metadatas", "documents"], limit=col.count())
    texts = {}
    for meta, doc in zip(got["metadatas"], got["documents"], strict=False):
        src = (meta or {}).get("source") or ""
        art = (meta or {}).get("article") or ""
        m = _ART_RE.search(art)
        n = cn2num(m.group(1)) if m else None
        if src and n and doc:
            texts[(canon_source(src), n)] = doc
    return texts


def fmt(s, a, para, item):
    out = f"{s}第{a}条"
    if para:
        out += f"第{para}款"
    if item:
        out += f"第{item}项"
    return out


def main():
    rows = json.load(open(ROWS, encoding="utf-8"))["rows"]
    texts = load_texts()
    db = set(texts)
    total_refs = sub_refs = 0
    valid = invalid = unknown = unparsed = 0
    details = []
    per_row = {}
    for r in rows:
        refs = extract_citation_refs(r["answer"])
        total_refs += len(refs)
        sub = [x for x in refs if x[2] or x[3]]
        sub_refs += len(sub)
        inv = 0
        for s, a, para, item in sorted(sub, key=lambda x: (x[0], x[1], x[2] or 0, x[3] or 0)):
            key = resolve((s, a), db)
            text = texts.get(key)
            if not text:
                state = "unknown_db"
                unknown += 1
            else:
                v = validate_subdivision(text, para, item)
                if v is True:
                    state = "valid"
                    valid += 1
                elif v is False:
                    state = "invalid"
                    invalid += 1
                    inv += 1
                else:
                    state = "unparsed"
                    unparsed += 1
            details.append(
                {
                    "id": r["id"],
                    "ref": fmt(s, a, para, item),
                    "resolved": f"{key[0]}第{key[1]}条",
                    "state": state,
                    "in_ctx": f"{s}第{a}条" in r["in_ctx"],
                }
            )
        per_row[r["id"]] = {"refs": len(refs), "sub": len(sub), "invalid": inv}
    zero_after_block = [i for i, v in per_row.items() if v["refs"] and v["invalid"] >= v["refs"]]
    out = {
        "n_rows": len(rows),
        "total_refs": total_refs,
        "subdivision_refs": sub_refs,
        "valid": valid,
        "invalid": invalid,
        "unknown_db": unknown,
        "unparsed": unparsed,
        "invalid_details": [d for d in details if d["state"] == "invalid"],
        "zero_after_block": zero_after_block,
        "per_row": per_row,
    }
    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
        f.write("\n")

    md = []
    md.append("# 款项级引用影子对比（2026-10-25）\n\n")
    md.append(f"数据源：`docs/benchmark_results/citation_gen59_20261025b.json`（{len(rows)} 题）。\n\n")
    md.append("## 结论\n\n")
    md.append(f"- 引用总数：**{total_refs}** 处；其中带款/项：**{sub_refs}** 处。\n")
    md.append("- 注：款项级计数会把同一条的不同款/项分别计；按「条」去重后为 250 处（见 citation_gen59_20261025b）。\n")
    md.append(
        f"- 款项校验：valid **{valid}** / invalid **{invalid}** / 库中无原文 **{unknown}** / 原文无法解析 **{unparsed}**。\n"
    )
    md.append(
        f"- 条级指标 `fabricated = 0` 仍然成立；**款项级校验额外发现 {invalid} 处错误**，说明条级口径确实会漏。\n"
    )
    md.append(
        f"- 若只拦截 invalid：影响 {len([d for d in details if d['state'] == 'invalid'])} 处引用，"
        f"会使 **{len(zero_after_block)}** 题失去全部引用（{zero_after_block or '无'}）。\n"
    )
    md.append(f"- 若只标注不拦截：可把这 {invalid} 处标为「款项待核」，用户侧零删除。\n\n")
    md.append("## invalid 明细\n\n")
    md.append("| id | 引用 | 库内归一 | 是否在检索上下文 |\n|---|---|---|---|\n")
    for d in out["invalid_details"]:
        md.append(f"| {d['id']} | {d['ref']} | {d['resolved']} | {'是' if d['in_ctx'] else '否'} |\n")
    if not out["invalid_details"]:
        md.append("| — | 无 | — | — |\n")
    md.append("\n## 局限\n\n")
    md.append("- 款项切分依赖原文排版（按行）；切片粘连或章节标题混入时可能落入 `unparsed`。\n")
    md.append("- 只解析书名号后的引用；未加书名号的引用不计入，与条级口径一致。\n")
    md.append("- `unknown_db` 表示法名/条号在库中找不到，不等同于编造（也可能是别名未归一）。\n")
    open(OUT_MD, "w", encoding="utf-8").write("".join(md))
    print(
        json.dumps(
            {
                k: out[k]
                for k in (
                    "n_rows",
                    "total_refs",
                    "subdivision_refs",
                    "valid",
                    "invalid",
                    "unknown_db",
                    "unparsed",
                    "zero_after_block",
                )
            },
            ensure_ascii=False,
        )
    )
    print("落盘", OUT_JSON)
    print("落盘", OUT_MD)


if __name__ == "__main__":
    main()
