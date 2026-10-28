"""生成对外评测集（external track），2026-10-25。

external 集不是第二份手工题库：它从 `data/eval_set_gen_all.json` 派生，
只收录已完成第三方复核的题（`gold_provenance=expert_annotated` 且 `reviewed_by` 非空）。
源头改了，重跑本脚本即可，避免两份题库漂移。

准入规则见 `docs/process-archive/plans/eval_tracks_20261025.md`：
- 必须 `gold_provenance=expert_annotated`、`reviewed_by` 非空
- 输出统一 `track=external` 并补 `capability`
- 本集只用于对外汇报，不参与回归门禁

用法：backend\\venv\\Scripts\\python.exe backend\\scripts\\build_external_set.py
"""

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
SRC = os.path.join(REPO, "data", "eval_set_gen_all.json")
OUT = os.path.join(REPO, "data", "eval_external_v1.json")

# 能力标签：按题目性质机械归类（procedure=程序/机构，application=实体适用）
PROCEDURE = {103, 117, 142, 149, 153}


def main():
    items = json.load(open(SRC, encoding="utf-8"))
    out = []
    for it in items:
        if it.get("gold_provenance") != "expert_annotated" or not it.get("reviewed_by"):
            continue
        row = dict(it)
        row["track"] = "external"
        row["capability"] = "procedure" if it["id"] in PROCEDURE else "application"
        out.append(row)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print(f"external={len(out)} -> {OUT}")


if __name__ == "__main__":
    main()
