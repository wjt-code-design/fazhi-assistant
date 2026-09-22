"""修正 T12-A 报告的过度声称：把「现行部署是 Caddy 同源反代」降级为「仓内设计意图」，
并补一节"部署形态未定时的决策框架"（Owner 2026-09-22 明确：服务器还没定）。
"""

from __future__ import annotations

import pathlib

P = pathlib.Path(r"C:/Users/33393/Desktop/ai-legal-helper/dispatch-output/t12a-deploy-base-20260922/report.md")
s = P.read_text(encoding="utf-8")

old_head = """**现行部署是「Caddy 同源反代」；`frontend/.env` 里那套「直连公网 8000」是过时旁路**——
它的立论前提（"同源会被缓冲 SSE"）**当天就在 Caddy 层被修好**（`flush_interval -1`）。"""
new_head = """**仓内设计意图是「Caddy 同源反代」；`frontend/.env` 那套「直连公网 8000」与之并存且被烘进镜像**——
前者的立论（"同源会被缓冲 SSE"）**当天就在 Caddy 层被修好**（`flush_interval -1`）。

> ⚠️ **勘误（2026-09-22，Owner 告知"服务器还没定"）**：本节首版把"仓内设计"写成"**现行部署**"，
> 那是**过度声称**——线上跑的是哪套口径，仓内无法验证。可确证的只有两件事：
> ①**仓内三套机制并存**（Caddy 反代 / Next rewrites / .env 绝对地址）；②`.env` 的值**确实会被烘进镜像**。
> 至于**线上用哪套**，取决于尚未定下的部署形态（见 §4.5）。"""
assert s.count(old_head) == 1
s = s.replace(old_head, new_head, 1)

# 在"§5 本卡没做的"之前插入决策框架
anchor = "## 5. 本卡没做的"
frame = """## 4.5 部署形态未定时的决策框架（Owner 2026-09-22：服务器还没定）

**先分清"与选择无关"和"随选择而定"——前者现在就能做，后者等形态定了再动。**

| 项 | 是否取决于部署形态 | 说明 |
|---|---|---|
| 补 `frontend/.dockerignore`（至少 `.env` / `.env.*` / `.next` / `node_modules`） | **无关** | 无论最终形态如何，"`.env` 绝不进镜像"这条防护都应真正生效（当前对前端上下文空转） |
| 统一 `lib/api.ts:1-2` 注释与 `.env.example` 的口径 | **无关** | 现在注释说"同源反代"、`.env` 说"直连 8000"，二者必有一处是错的——**先改成"以部署形态为准"的中性表述** |
| 清掉 `frontend/.env` 的 `NEXT_PUBLIC_API_URL` | **取决于** | 选**同源反代**（Caddy 或 Next rewrites）⇒ 应当清掉；选**前后端异域/独立 API 域名**⇒ 保留，但要把域名写成**固定域名**而非裸 IP，并补 CORS/安全组前置 |
| 给 Caddyfile 的 `/api/*` 分支加"已废弃"注释或删除 | **取决于** | 同上（选错向会留下两套反代长期并存） |
| 用 openapi 生成客户端/文档时补 `responses` 声明 | **无关**（但优先级低） | 见 T12 主报告 §3.4 观察项 |

**三种候选形态与各自需要的设置**（供你定形态时对照）：

| 形态 | 前端基址 | 需要什么 | 风险 |
|---|---|---|---|
| **A. 单域名同源反代**（Caddy/Nginx，仓库现设计） | **不设** `NEXT_PUBLIC_API_URL`（走相对 `/api/*`） | 反代 `/api/*` 到后端 + SSE 必须 `flush_interval -1`（或等价不缓冲配置） | 反代配错 ⇒ SSE 变"一次性输出"（**已踩过**） |
| **B. 前端 + 后端异域（独立 API 域名）** | 设 `NEXT_PUBLIC_API_URL=https://api.<域名>` | 后端 CORS 白名单 + HTTPS 证书 + 域名（**别写裸 IP**） | 多一套 CORS/证书；HTTPS 站点下 http 后端会触发混合内容拦截 |
| **C. 内网/本机单机**（如内网部署） | 设 `http://<宿主>:8000` 或走同源 | 端口放通 | 换机/换网就失效（**基址写死是主要坑**） |

**我的推荐**：**A（同源反代）**——仓库已按 A 建好（Caddyfile + rewrites），选 A 只需"清掉 .env 的覆盖值"，
且天然免 CORS/混合内容问题；B/C 都要额外维护基址与跨域配置。**但无论选哪个，上表前两行（与选择无关）都建议先做。**

"""
assert s.count(anchor) == 1
s = s.replace(anchor, frame + anchor, 1)
P.write_text(s, encoding="utf-8", newline="")
print("T12-A 报告已修正：冠声称降级 + 新增 §4.5 决策框架；字节=", len(s.encode("utf-8")))
