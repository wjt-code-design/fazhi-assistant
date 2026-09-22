# T12-A · 前端部署基址口径核对（只报告）

> 承接 `dispatch-output/t12-frontend-sweep-20260920/report.md` 的两处上下文：
> （1）构建产物实测内联 `http://162.14.81.34:8000`；（2）`lib/api.ts` 注释称"生产走同源 `/api/*`"。
> 本卡只读：**未改任何代码/配置**，只给结论与修正建议。

## 0. 一句话结论

**仓内设计意图是「Caddy 同源反代」；`frontend/.env` 那套「直连公网 8000」与之并存且被烘进镜像**——
前者的立论（"同源会被缓冲 SSE"）**当天就在 Caddy 层被修好**（`flush_interval -1`）。

> ⚠️ **勘误（2026-09-22，Owner 告知"服务器还没定"）**：本节首版把"仓内设计"写成"**现行部署**"，
> 那是**过度声称**——线上跑的是哪套口径，仓内无法验证。可确证的只有两件事：
> ①**仓内三套机制并存**（Caddy 反代 / Next rewrites / .env 绝对地址）；②`.env` 的值**确实会被烘进镜像**。
> 至于**线上用哪套**，取决于尚未定下的部署形态（见 §4.5）。
更关键的是：**它会被烘进生产镜像**，因为 `frontend/.dockerignore` 不存在、compose 构建上下文是
`./frontend`，**根 `.dockerignore` 那句「.env 绝不进镜像」对前端服务根本不生效**。

## 1. 三处口径互不一致（证据）

| 出处 | 日期 | 口径 |
|---|---|---|
| `frontend/.env` | **2026-08-22** | `NEXT_PUBLIC_API_URL=http://162.14.81.34:8000` —— "改为前端直连后端 8000，**绕过 Next 反代**" |
| `frontend/.env.example` | 2026-08-08 | 生产默认走**同源相对路径**；**【不要设置】`NEXT_PUBLIC_API_URL`**（会在 build 时内联绝对地址 ⇒ 手机请求 `localhost:8000` ⇒ failed to fetch，**已踩坑**） |
| `frontend/lib/api.ts:1-2` | 2026-08-08 | "生产走相对路径 `/api/*`，由 **Caddy** 反代到 `backend:8000`" |
| `frontend/next.config.js` | 2026-08-08 | `rewrites()` 把 `/api/:path*` 代理到 `BACKEND_URL`（默认 `localhost:8000`），注释称"无需 Caddy/CORS" |

## 2. 部署现实（`Caddyfile` + `docker-compose.yml`）

```
Caddyfile（:80，容器内监听，宿主映射 8088）：
  handle /api/*  { reverse_proxy backend:8000 { flush_interval -1 }  + Cache-Control no-transform / X-Accel-Buffering no }
  handle         { reverse_proxy frontend:3000 }
```
- **`/api/*` 明确反代到 backend:8000**；且 `# 【已修复 2026-08-22 SSE 流式】` 写明：
  Caddy `reverse_proxy` 默认攒批 ⇒ `flush_interval -1` = 收到即下发，逐帧流式。
- ⇒ **08-22 那次"改直连"想解决的问题（SSE 被缓冲），同一天已在 Caddy 层解决**；
  而 `.env` 的直连改动**只改了前端产物**，没同步回退 ⇒ **双轨并存**。

## 3. 双轨并存的真实后果（机制级）

1. **烘进镜像**：`frontend/Dockerfile` 是 `COPY . .` + `RUN npm run build`；
   `docker-compose.yml:61` 是 `build: ./frontend`（**无 `context:` 覆盖**）⇒ Docker 只读
   **`frontend/.dockerignore`**（**该文件不存在**）⇒ 根 `.dockerignore` 的 `.env` / `**/.env` 排除
   **对前端服务不生效** ⇒ `frontend/.env` 进入构建 ⇒ `NEXT_PUBLIC_API_URL` 被 Next 内联进产物。
2. **绕过 Caddy 的防护**：走绝对地址时，请求**不经** Caddy 的 `handle /api/*` ⇒ 拿不到它的
   `no-transform` / `X-Accel-Buffering: no`，也拿不到全局安全响应头（`nosniff` / `X-Frame-Options` / `Referrer-Policy`）。
3. **可访问性依赖**：手机端要能直连 `162.14.81.34:8000` ⇒ 依赖**安全组放通 + 后端 CORS**（`.env` 注释自己列了这两条前置），
   而走同源则**不需要**这两条。
4. **重定向/混合内容风险**：站点经 8088 同源访问时，页面为 http，直连 http 尚无混合内容问题；
   但一旦站点上 HTTPS，内联的 `http://…:8000` 会触发**混合内容拦截**（现在没有，属前瞻风险）。

**今日实际危害面**：`frontend/.env` 内只有**公开** URL（无密钥）⇒ **无泄密**；
但"`.env` 绝不进镜像"这条**防护机制对前端服务是失效的**，这才是要修的点。

## 4. 修正建议（供 Owner 决策；本卡未执行）

| # | 建议 | 理由 | 风险/前置 |
|---|---|---|---|
| **①（首选）** | 清掉/注释 `frontend/.env` 里的 `NEXT_PUBLIC_API_URL`，回到**同源相对路径** | 与 `.env.example` 08-08 指引一致；Caddy 08-22 已修 SSE；免 CORS/安全组依赖；保留 Caddy 安全头 | 需**重建镜像并部署**；须先确认线上 Caddyfile 就是仓库这份 |
| **②** | 同步 `lib/api.ts:1-2` 的注释口径（现为 08-08 同源，与 `.env` 08-22 冲突） | 注释与配置不一致会把后续维护者带偏 | 纯注释 |
| **③（防同类）** | 新建 `frontend/.dockerignore`（至少 `.env` / `.env.*` / `.next` / `node_modules`） | **根 `.dockerignore` 管不到 `./frontend` 上下文** ⇒ "防泄密"目前是空转 | 需重建镜像验证（应看到 `.env` 不再进层） |
| **④** | 若确要保留直连（如另有独立 API 域名）：在 Caddyfile 明确注释"`/api/*` 分支已废弃"并同步文档 | 避免两套反代口径长期并存 | 需 Owner 确认部署策略 |

**需 Owner/运维确认（我无法验证）**：仓库里的 `Caddyfile` 是否就是**线上正在跑的那份**；
线上是否已放通 `162.14.81.34:8000` 的安全组与后端 CORS。

## 4.5 部署形态未定时的决策框架（Owner 2026-09-22：服务器还没定）

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

## 5. 本卡没做的

- 未改 `.env` / `.dockerignore` / 注释（卡面：只报告）；
- 未构建镜像验证假设（`docker build` 会写镜像层，属改环境的动作，须先获授权）；
- 未核线上真实配置（只能在仓库侧读）。
