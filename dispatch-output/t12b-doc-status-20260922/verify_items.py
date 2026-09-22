"""T12-B：把 review-plan §1 的问题清单**逐条按代码事实核对**（只读，为状态回填取证）。

清单源：`docs/frontend-review-refactor-plan-20260915.md` §1（A/B/C/D/E/F 六维度）。
原则：每条只认代码事实；机器判不了的（观感/体感）**不硬判**，标 `无法机判` 并给"要人看什么"。
"""

from __future__ import annotations

import json
import pathlib
import re

ROOT = pathlib.Path(r"C:/Users/33393/Desktop/ai-legal-helper")
FE = ROOT / "frontend"
SKIP = {"node_modules", ".next", "coverage"}


def files(*subs: str):
    for sub in subs:
        base = FE / sub
        if not base.exists():
            continue
        for p in base.rglob("*"):
            if p.is_file() and not any(part in SKIP for part in p.parts):
                yield p


def count(pattern: str, fs, flags: int = 0) -> int:
    rx = re.compile(pattern, flags)
    n = 0
    for p in fs:
        try:
            n += len(rx.findall(p.read_text(encoding="utf-8", errors="ignore")))
        except OSError:
            continue
    return n


def main() -> int:
    src = list(files("app", "components", "lib", "public", "scripts"))
    css = [p for p in files("app", "components") if p.suffix == ".css"]
    out: dict = {}

    # ---- A. 代码结构 ----
    page = FE / "app" / "page.tsx"
    out["A1_chat_page_lines"] = len(page.read_text(encoding="utf-8").splitlines()) if page.exists() else None
    out["A1_chat_page_useState"] = count(r"useState[<(]", [page]) if page.exists() else None
    out["A1_chat_components"] = sorted(p.name for p in (FE / "components" / "chat").glob("*.tsx")) if (FE / "components" / "chat").is_dir() else []
    out["A1_hooks"] = sorted(p.name for p in (FE / "lib" / "hooks").glob("*.ts")) if (FE / "lib" / "hooks").is_dir() else []
    admin = FE / "app" / "admin" / "page.tsx"
    out["A2_admin_page_lines"] = len(admin.read_text(encoding="utf-8").splitlines()) if admin.exists() else None
    out["A2_admin_sections"] = sorted(p.name for p in (FE / "app" / "admin" / "sections").glob("*.tsx")) if (FE / "app" / "admin" / "sections").is_dir() else []
    out["A/C3_MessageHtml_as_component_file"] = (FE / "components" / "chat" / "MessageHtml.tsx").exists()
    out["A/C3_ChatImage_as_component_file"] = (FE / "components" / "chat" / "ChatImage.tsx").exists()
    out["A4_constants_in_lib"] = (FE / "lib" / "constants.ts").exists()
    out["A4_SCENES_in_page"] = count(r"SCENES|DAILY_LAWS|CODEX", [page]) if page.exists() else None

    # ---- B. 组件设计 ----
    out["B1_inline_svg_total"] = count(r"<svg", src)
    out["B2_toLocaleString_total"] = count(r"toLocaleString", src)
    out["B2_format_ts_exists"] = (FE / "lib" / "format.ts").exists()
    api = FE / "lib" / "api.ts"
    out["B3_api_any_hits"] = count(r"\bany\b", [api]) if api.exists() else None
    out["B4_useChatStream_useState"] = count(r"useState[<(]", [FE / "lib" / "hooks" / "useChatStream.ts"])

    # ---- C. 性能 / PWA ----
    sw = FE / "public" / "sw.js"
    if sw.exists():
        t = sw.read_text(encoding="utf-8", errors="ignore")
        out["C1_sw_hardcoded_v1"] = len(re.findall(r"fazhi-shell-v\d", t))
        out["C1_sw_uses_build_id"] = ("build-id" in t)
    out["C3_bg_attachment_fixed"] = count(r"background-attachment\s*:\s*fixed", css)
    out["C4_throttle_or_debounce"] = count(r"throttle|debounce|requestAnimationFrame", src)
    out["C4_setInterval"] = count(r"setInterval", src)

    # ---- D. 工程化 ----
    out["D1_eslint"] = [p.name for p in FE.glob(".eslintrc*")]
    out["D1_prettier"] = [p.name for p in FE.glob(".prettier*")]
    out["D1_vitest"] = [p.name for p in FE.glob("vitest.config.*")]
    out["D2_test_files"] = [str(p.relative_to(FE)) for p in FE.rglob("*.test.*") if "node_modules" not in p.parts]
    out["D4_dead_styles_still_present"] = {
        k: count(re.escape(k), css)
        for k in ("glass-card-strong", "glow-line", "done-seal", "law-popup", "section-mark-float", "lineGrow")
    }
    out["D4_dead_vars_still_present"] = {k: count(re.escape(k), css) for k in ("--stagger", "--dur-med")}
    out["D4_register_branch_in_login"] = count(r"register", list(files("app")))

    # ---- E. 样式 ----
    out["E1_hex_ff8fa9"] = count(r"#ff8fa9", css)
    out["E1_hex_f56b8c"] = count(r"#f56b8c", css)
    out["E1_bare_rgba"] = count(r"rgba\(", css)
    out["E2_radius_values"] = sorted(set(re.findall(r"border-radius:\s*([0-9.]+(?:px|rem))", "".join(
        p.read_text(encoding="utf-8", errors="ignore") for p in css))))
    out["E3_semantic_colors"] = dict(
        re.findall(r"(--(?:law|time|money|accent))\s*:\s*(#[0-9a-fA-F]{3,8})", "".join(
            p.read_text(encoding="utf-8", errors="ignore") for p in css))
    )

    (ROOT / "dispatch-output" / "t12b-doc-status-20260922" / "code-facts.json").parent.mkdir(parents=True, exist_ok=True)
    (ROOT / "dispatch-output" / "t12b-doc-status-20260922" / "code-facts.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8", newline="")
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
