"""修正 report.md §3.4 的状态码计数（口径纠正：之前只扫 main.py，却声称含 auth.py）。

真实全量（main.py + auth.py）：400×15 / 404×14 / 503×4 / 401×4 / 403×3 / 501×2 / 413×2 / 409×2 / 502×1 / 429×1
（+ FastAPI 隐式 422）。修正同时补上 429 与本轮的口径说明。
"""

import pathlib

P = pathlib.Path(
    r"C:/Users/33393/Desktop/ai-legal-helper/dispatch-output/t12-frontend-sweep-20260920/report.md"
)
lines = P.read_text(encoding="utf-8").splitlines(keepends=True)
start = next(i for i, ln in enumerate(lines) if ln.startswith("### 3.4 错误码层"))
end = next(i for i, ln in enumerate(lines) if ln.startswith("### 3.3 抽取侧局限"))

BLOCK = [
    "### 3.4 错误码层（深口径第三层·续；**计划书 §1-③ 曾漏做，2026-09-22 复核时补上**）\n",
    "\n",
    "- **后端状态码全集**（`main.py` + `auth.py`，`status_code=NNN` 显式抛出；**全量重数、不截断**）：\n",
    "  `400×15 / 404×14 / 503×4 / 401×4 / 403×3 / 501×2 / 413×2 / 409×2 / 502×1 / 429×1`（+ FastAPI 隐式 **422**）。\n",
    "  *勘误（2026-09-22 复验时发现）*：本节首版把计数写成 `403×2` 且**漏了 429**——根因是当时只扫了 `main.py`，\n",
    "  却在正文里声称「`main.py` / `auth.py` 显式抛出」⇒ **口径与陈述不符**；已按两文件全量重数修正。\n",
    "  401 的四处出处：`main.py:389`（登录失败）、`auth.py:60/64/67`（未登录 / 令牌无效 / 用户不存在）。\n",
    "- **前端处理**（`lib/api.ts`）：**仅 401 特殊**（清 token + 跳 `/login` + `ApiError(401)`，"
    "`request()` 与流式路径各一处）；其余一律 `!res.ok` → 解析 FastAPI 的 `detail` 形状 → "
    "`ApiError(status, detail)`（**429 也落这条通用分支**，无需专门处理）。\n",
    "- **判定：无不一致**。前端是**宽契约**（不逐码对齐，只锚 401 + `detail`）⇒ 后端新增/调整业务码"
    "**不会破坏前端**。\n",
    "- **附带观察（改进建议）**：openapi 只声明 `200×40 / 422×31`，**业务码未声明**（走运行时分支）"
    "⇒ 若将来要用 openapi 生成客户端或对外文档，关键端点应补 `responses={...}` 声明。\n",
    "\n",
]

new = lines[:start] + BLOCK + lines[end:]
P.write_text("".join(new), encoding="utf-8", newline="")
print("§3.4 已修正（含勘误说明）；行数", len(lines), "→", len(new))
