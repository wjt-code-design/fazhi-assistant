"""T12 轴①：待办逐条按代码事实核对（只读；不采信文档自述）。

清单源：`docs/frontend-execution-book-20260915.md` 的 15 个编号任务 +
`docs/frontend-review-refactor-plan-20260915.md` §1 的 ⬜ 待修项。

每条的判定只认**代码事实**（文件存在 / 符号出现 / 配置项），并给"怎么查的"。
三档：已落地 / 未落地 / 无法判定（第三档要写清判不了的原因）。
"""

from __future__ import annotations

import json
import pathlib
import re

ROOT = pathlib.Path(r"C:/Users/33393/Desktop/ai-legal-helper")
FE = ROOT / "frontend"
# 只读源码面：排除产物与依赖
SKIP = {"node_modules", ".next", "coverage", ".git"}


def walk_files(*subs: str):
    for sub in subs:
        base = FE / sub
        if not base.exists():
            continue
        for p in base.rglob("*"):
            if p.is_file() and not any(part in SKIP for part in p.parts):
                yield p


def grep_count(pattern: str, files) -> int:
    rx = re.compile(pattern)
    n = 0
    for p in files:
        try:
            txt = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        n += len(rx.findall(txt))
    return n


def main() -> int:
    src = list(walk_files("app", "components", "lib", "public", "scripts", "docs"))
    out: dict = {}

    # 配置文件与目录（存在性）
    out["T0.1_eslint_config"] = sorted(p.name for p in FE.glob(".eslintrc*")) + sorted(
        p.name for p in FE.glob("eslint.config.*")
    )
    out["T0.2_prettier_config"] = sorted(
        p.name for p in FE.glob(".prettier*")
    ) + sorted(p.name for p in FE.glob("prettier.config.*"))
    out["T0.3_vitest_config"] = sorted(
        p.name for p in FE.glob("vitest.config.*")
    ) + sorted(p.name for p in FE.glob("vite.config.*"))
    test_files = [
        str(p.relative_to(FE))
        for p in FE.rglob("*.test.*")
        if "node_modules" not in p.parts
    ]
    out["T0.3_test_files"] = test_files
    out["T0.3_test_count"] = len(test_files)

    # T1.x 的代码事实
    out["T1.1_write_build_id_mjs"] = (FE / "scripts" / "write-build-id.mjs").exists()
    out["T1.1_build_wires_it"] = "write-build-id" in (FE / "package.json").read_text(
        encoding="utf-8"
    )
    out["T1.2_aria_live_hits"] = grep_count(r"aria-live", src)
    out["T1.3_streaming_guard_hits"] = grep_count(
        r"AbortController|abortSignal|isStreaming|streamingGuard", src
    )
    out["T1.4_globals_css_root"] = (FE / "app" / "globals.css").exists()
    out["T1.5_enter_send_hits"] = grep_count(
        r"key === .['\"]Enter|keyCode === 13|onKeyDown", src
    )
    out["T1.6_touch_target_hits"] = grep_count(
        r"min-h-|min-height|touch-action|44px", src
    )
    out["T1.7_format_ts"] = (FE / "lib" / "format.ts").exists()

    # T2.x 的结构事实
    out["T2.1_constants_ts"] = (FE / "lib" / "constants.ts").exists()
    out["T2.2_components_chat_dir"] = (FE / "components" / "chat").is_dir()
    out["T2.2_chat_components"] = (
        sorted(p.name for p in (FE / "components" / "chat").glob("*"))
        if (FE / "components" / "chat").is_dir()
        else []
    )
    out["T2.3_lib_hooks_dir"] = (FE / "lib" / "hooks").is_dir()
    out["T2.3_hooks_files"] = (
        sorted(p.name for p in (FE / "lib" / "hooks").glob("*"))
        if (FE / "lib" / "hooks").is_dir()
        else []
    )
    out["T2.4_admin_sections_dir"] = (FE / "app" / "admin" / "sections").is_dir()
    out["T2.4_admin_sections"] = (
        sorted(p.name for p in (FE / "app" / "admin" / "sections").glob("*"))
        if (FE / "app" / "admin" / "sections").is_dir()
        else []
    )
    api_ts = FE / "lib" / "api.ts"
    out["T2.5_api_ts_exists"] = api_ts.exists()
    if api_ts.exists():
        txt = api_ts.read_text(encoding="utf-8", errors="ignore")
        out["T2.5_any_hits"] = len(re.findall(r"\bany\b", txt))
        out["T2.5_lines"] = len(txt.splitlines())

    # review-plan 的 ⬜ 项（挑可机器验证的）
    chat_pages = [
        p
        for p in FE.rglob("page.tsx")
        if "admin" not in str(p) and "node_modules" not in p.parts
    ]
    if chat_pages:
        p0 = chat_pages[0]
        t = p0.read_text(encoding="utf-8", errors="ignore")
        out["B4_chat_page"] = str(p0.relative_to(FE))
        out["B4_useState_count"] = len(re.findall(r"useState[<(]", t))
        out["B4_lines"] = len(t.splitlines())

    print(json.dumps(out, ensure_ascii=False, indent=1))
    (
        ROOT
        / "dispatch-output"
        / "t12-frontend-sweep-20260920"
        / "axis1-code-facts.json"
    ).write_text(
        json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8", newline=""
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
