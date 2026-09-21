"""修复 report.md §3.4：把被 shell 命令替换吞掉的反引号内容整块重写。

背景：上一轮用 `python -c "..."` 内联写含反引号的文本 ⇒ bash 命令替换把 `...` 内容整体吃掉
（本仓既有教训：任何含反引号/`$` 的 Python 一律写 .py 文件执行）。本脚本按**行锚点**整块替换，
不依赖脆弱的精确匹配。
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
    "- **后端状态码全集**（`main.py` / `auth.py` 显式抛出）：**401**（登录失败 `main.py:389`；"
    "未登录 / 令牌无效 / 用户不存在 `auth.py:60/64/67`）、400×15、404×14、503×4、501×2、413×2、"
    "409×2、403×2、502×1；另 **422** 由 FastAPI 校验隐式产生。\n",
    "- **前端处理**（`lib/api.ts`）：**仅 401 特殊**（清 token + 跳 `/login` + `ApiError(401)`，"
    "`request()` 与流式路径各一处）；其余一律 `!res.ok` → 解析 FastAPI 的 `detail` 形状 → "
    "`ApiError(status, detail)`。\n",
    "- **判定：无不一致**。前端是**宽契约**（不逐码对齐，只锚 401 + `detail`）⇒ 后端新增/调整业务码"
    "**不会破坏前端**。\n",
    "- **附带观察（改进建议）**：openapi 只声明 `200×40 / 422×31`，**业务码未声明**（走运行时分支）"
    "⇒ 若将来要用 openapi 生成客户端或对外文档，关键端点应补 `responses={...}` 声明。\n",
    "\n",
]

new = lines[:start] + BLOCK + lines[end:]
P.write_text("".join(new), encoding="utf-8", newline="")
print("§3.4 已按行锚点重写；行数", len(lines), "→", len(new))
