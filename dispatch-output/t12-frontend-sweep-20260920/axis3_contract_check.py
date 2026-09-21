"""T12 轴③：前端调用点 ↔ 后端 openapi 路径 逐项比对（只读）。

真源 = `axis3-backend-openapi.json`（进程内 `main.app.openapi()` 导出，确定性）。
口径 = **深**：路径 + 方法；不把模板字面量当错（做一次归一化，把 `${...}` 段替换成 `{x}` 再比）。
产出：`axis3-contract-diff.json`（三类：只前端有 / 只后端有 / 命中）。
"""

from __future__ import annotations

import json
import pathlib
import re

ROOT = pathlib.Path(r"C:/Users/33393/Desktop/ai-legal-helper")
FE = ROOT / "frontend"
OUT = ROOT / "dispatch-output" / "t12-frontend-sweep-20260920"
SKIP = {"node_modules", ".next", "coverage", ".git"}


def norm(path_or_tpl: str) -> str:
    """把模板字面量归一成 openapi 风格：/api/x/${id}/y → /api/x/{x}/y。"""
    s = re.sub(r"\$\{[^}]*\}", "{x}", path_or_tpl)
    s = re.sub(r"\{[^}]*\}", "{x}", s)
    return s.rstrip("/") or "/"


def main() -> int:
    backend = json.loads(
        (OUT / "axis3-backend-openapi.json").read_text(encoding="utf-8")
    )
    bpaths = [(norm(r["path"]), r["path"]) for r in backend["paths"]]
    bset = {p for p, _ in bpaths}

    # 前端调用点：找 /api/... 字面量与模板字面量
    hits: list[dict] = []
    for p in FE.rglob("*"):
        if not p.is_file() or any(part in SKIP for part in p.parts):
            continue
        if p.suffix not in (".ts", ".tsx", ".js", ".mjs", ".jsx"):
            continue
        try:
            txt = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for m in re.finditer(r"[\"'`](/api/[A-Za-z0-9_\-/{}$.:]*)[\"'`]", txt):
            raw = m.group(1)
            line = txt[: m.start()].count("\n") + 1
            hits.append(
                {
                    "file": str(p.relative_to(FE)),
                    "line": line,
                    "raw": raw,
                    "norm": norm(raw),
                }
            )
        # 第二条模式（首版漏掉的那类）：模板字面量带前缀 —— `${API_URL}/api/chat`
        # （首版只认紧跟引号的 /api… ⇒ `/api/chat` 被误判成"只后端有"；此为抽取侧假阴性）
        for m in re.finditer(r"\$\{[^}]{1,40}\}(/api/[A-Za-z0-9_\-/{}$.:]*)", txt):
            raw = m.group(1)
            line = txt[: m.start()].count("\n") + 1
            hits.append(
                {
                    "file": str(p.relative_to(FE)),
                    "line": line,
                    "raw": raw,
                    "norm": norm(raw),
                }
            )

    seen: dict[str, dict] = {}
    for h in hits:
        seen.setdefault(h["norm"], h)

    fe_only = sorted(p for p in seen if p not in bset)
    be_only = sorted(p for p in bset if p not in seen)
    matched = sorted(p for p in seen if p in bset)

    result = {
        "backend_path_count": len(bset),
        "frontend_call_sites": len(hits),
        "frontend_distinct_paths": len(seen),
        "matched": matched,
        "frontend_only": [seen[p] for p in fe_only],
        "backend_only": sorted(next(b for n, b in bpaths if n == p) for p in be_only),
    }
    (OUT / "axis3-contract-diff.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8", newline=""
    )
    print(
        json.dumps(
            {k: v for k, v in result.items() if not isinstance(v, list)},
            ensure_ascii=False,
            indent=1,
        )
    )
    print("只前端有:", json.dumps(result["frontend_only"], ensure_ascii=False)[:600])
    print("只后端有:", json.dumps(result["backend_only"], ensure_ascii=False)[:400])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
