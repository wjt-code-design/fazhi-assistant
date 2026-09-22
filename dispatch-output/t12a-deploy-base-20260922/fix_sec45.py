"""修正 §4.5 的一处**我自己的错**：把「补 .dockerignore」笼统列为"与形态无关"是错的——
排除 `.env` 的 .dockerignore 在**效果上等价于**清掉 NEXT_PUBLIC_API_URL（都会被烘进/不烘进产物），
会静默把生产切到同源路径。必须按"纯构建卫生"与"改配置效果"拆开。
"""

from __future__ import annotations

import pathlib

P = pathlib.Path(r"C:/Users/33393/Desktop/ai-legal-helper/dispatch-output/t12a-deploy-base-20260922/report.md")
s = P.read_text(encoding="utf-8")

old = """| 补 `frontend/.dockerignore`（至少 `.env` / `.env.*` / `.next` / `node_modules`） | **无关** | 无论最终形态如何，"`.env` 绝不进镜像"这条防护都应真正生效（当前对前端上下文空转） |"""
new = """| 补 `frontend/.dockerignore` 的**构建卫生项**（`node_modules` / `.next` / `.git`） | **无关** | 纯构建上下文卫生，**不改任何配置效果** |
| 补 `frontend/.dockerignore` 的 **`.env` 排除项** | ⚠️ **取决于**（首版误列为"无关"） | 排除 `.env` 在**效果上等同于**清掉 `NEXT_PUBLIC_API_URL`：都会让产物回归同源 `/api/*`。**在部署形态未定前做它 = 静默切换生产路径**（选 A 才做，且应与清值**同一批**做） |"""
assert s.count(old) == 1
s = s.replace(old, new, 1)

old2 = """**我的推荐**：**A（同源反代）**——仓库已按 A 建好（Caddyfile + rewrites），选 A 只需"清掉 .env 的覆盖值"，"""
new2 = """⚠️ **在形态定下来之前，"什么都不改"是最安全的**：当前镜像的直连口径虽不理想但**能跑**；
贸然动 `.env` 或 `.dockerignore(.env)` 会**静默切换**生产路径——那正是本仓反复踩过的"降级静默改路径"。
**能做的是不改效果的两件**：①`.dockerignore` 加构建卫生项；②`api.ts` 注释/`.env.example` 改中性表述。

**我的推荐**：**A（同源反代）**——仓库已按 A 建好（Caddyfile + rewrites），选 A 只需"清掉 .env 的覆盖值"，"""
assert s.count(old2) == 1
s = s.replace(old2, new2, 1)

P.write_text(s, encoding="utf-8", newline="")
print("§4.5 已修正；字节=", len(s.encode("utf-8")))
