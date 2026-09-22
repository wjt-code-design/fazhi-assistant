"""T12 服务器无关项 1–3：只做**不改配置效果**的加固（Owner 2026-09-22 指示）。

1) `frontend/.dockerignore`：只加**构建卫生项**；**明确不排除 `.env`**（排除 .env 等价于清掉
   NEXT_PUBLIC_API_URL ⇒ 会静默把生产切到同源路径 —— 属"部署形态"决策，见 T12-A §4.5）。
2) `lib/api.ts` 注释中性化 + `.env.example` 中性化（消歧义；**不动 `.env` 的值**）。
3) 两处 `<img>` 加 `eslint-disable-next-line` + 理由注释（零行为变化，warning 2→0）。
"""

from __future__ import annotations

import pathlib

FE = pathlib.Path(r"C:/Users/33393/Desktop/ai-legal-helper/frontend")

# ── 1) .dockerignore（不含 .env）──
dockerignore = """# 构建上下文卫生（2026-09-22，票 T12-A 跟进）：缩小传给 docker 的上下文。
#
# ⚠️ 这里**故意不排除 `.env`**：排除它等价于清掉 NEXT_PUBLIC_API_URL（都让产物回归同源 /api/*），
#    会**静默切换生产路径** ⇒ 属"部署形态"决策，须与「清不清 .env 的值」同一批做。
#    详见 dispatch-output/t12a-deploy-base-20260922/report.md §4.5。
# ⚠️ 注意：根目录的 `.dockerignore` 对本服务**不生效**（compose 的 build context 是 ./frontend）。
node_modules
.next
.git
.gitignore
coverage
*.log
.DS_Store
"""
(FE / ".dockerignore").write_text(dockerignore, encoding="utf-8", newline="")
print("[1] 写入 .dockerignore（不含 .env）")

# ── 2a) api.ts 注释中性化（只改注释）──
api = FE / "lib" / "api.ts"
s = api.read_text(encoding="utf-8")
old_api = """// 同源部署（2026-08-08，手机端上线）：生产走相对路径 /api/*，由 Caddy 反代到 backend:8000
// （免跨域、免 CORS、免注入 NEXT_PUBLIC_API_URL）；开发（next dev）仍直连 localhost:8000。"""
new_api = """// 生产基址**取决于部署形态**（同源反代 / 前后端异域），以部署配置为准，勿以本注释为事实：
//   · 同源反代：不设 NEXT_PUBLIC_API_URL，走相对 /api/*（当前仓库按此设计：Caddyfile + next rewrites）
//   · 异域直连：设 NEXT_PUBLIC_API_URL 为**域名**（别写裸 IP），并在后端配 CORS
//   · 开发（next dev）：未设该变量时回落到 http://localhost:8000
// 线上跑哪套尚未定（2026-09-22），三种机制的并存与影响见
// dispatch-output/t12a-deploy-base-20260922/report.md。"""
assert s.count(old_api) == 1
api.write_text(s.replace(old_api, new_api, 1), encoding="utf-8", newline="")
print("[2a] api.ts 注释已中性化")

# ── 2b) .env.example 中性化（保留踩坑记录）──
envx = FE / ".env.example"
old_env = """# 后端接口地址（前端无需密钥）
# 2026-08-08 手机端上线：生产默认走同源相对路径（Next rewrites 反代 /api → 后端 8000），
# 因此【不要设置】NEXT_PUBLIC_API_URL——它会在 build 时内联成绝对地址，手机访问会请求
# localhost:8000（手机自己）导致登录/问答 failed to fetch（已踩坑）。
# 仅当刻意让前端/后端异域（如独立 API 域名）时才取消注释：
# NEXT_PUBLIC_API_URL=http://localhost:8000"""
new_env = """# 后端接口地址（前端无需密钥）
# 【按部署形态二选一，线上形态 2026-09-22 尚未定】
#   A) 同源反代：**不要设置** NEXT_PUBLIC_API_URL ⇒ 走相对 /api/*（需反代把 /api/* 转到后端，
#      且 SSE 必须不缓冲：Caddy 用 flush_interval -1）
#   B) 前后端异域：设为**域名**（如 https://api.example.com），并在后端配 CORS 白名单
#
# 历史踩坑（2026-08-08，勿重蹈）：把绝对地址（尤其裸 IP）内联进产物 ⇒ 手机访问会请求那个地址，
# 若它是 localhost 或不可达 ⇒ 登录/问答 failed to fetch；HTTPS 站点配 http 后端还会触发混合内容拦截。
# NEXT_PUBLIC_API_URL=https://api.example.com"""
s2 = envx.read_text(encoding="utf-8")
assert s2.count(old_env) == 1
envx.write_text(s2.replace(old_env, new_env, 1), encoding="utf-8", newline="")
print("[2b] .env.example 已中性化（未触碰 .env 的值）")

# ── 3) 两处 <img> 局部禁用该 lint 规则 + 理由 ──
ci = FE / "components" / "chat" / "ChatImage.tsx"
old_img1 = """  return (
    <img
      src={src}"""
new_img1 = """  return (
    // eslint-disable-next-line @next/next/no-img-element -- src 为 data:/blob: URL（本地预览或经 loadMediaSrc 带鉴权取的 blob），next/image 不支持且其服务端优化器不带令牌会 401。详见 T12-D 报告。
    <img
      src={src}"""
s3 = ci.read_text(encoding="utf-8")
assert s3.count(old_img1) == 1
ci.write_text(s3.replace(old_img1, new_img1, 1), encoding="utf-8", newline="")
print("[3a] ChatImage 已加局部 disable")

ib = FE / "components" / "chat" / "InputBar.tsx"
old_img2 = """            <img src={pendingImage} alt="待发送" className="h-12 w-12 rounded object-cover" />"""
new_img2 = """            {/* eslint-disable-next-line @next/next/no-img-element -- pendingImage 是本地 data:/blob: 预览，next/image 不支持该形态。详见 T12-D 报告。 */}
            <img src={pendingImage} alt="待发送" className="h-12 w-12 rounded object-cover" />"""
s4 = ib.read_text(encoding="utf-8")
assert s4.count(old_img2) == 1
ib.write_text(s4.replace(old_img2, new_img2, 1), encoding="utf-8", newline="")
print("[3b] InputBar 已加局部 disable")
