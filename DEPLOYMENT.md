# 法智 · 部署指南

> 简易部署文档：本地开发启动 → 阿里云 ECS 部署 → 环境变量 → 端口放行。
> 面向 2~3 人小规模使用，单机部署。详见 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)。
>
> **2026-10-27 更新**：按当前代码与实测数据校准——后端镜像体积、内存占用、Caddy 宿主端口
> 可配（`CADDY_HTTP_PORT`）、容器环境变量注入口径（根 `.env`）、数据目录必须随传。
> 旧的"镜像 1.5GB""改 compose 映射 8080"等说法已作废。

---

## 1. 服务与端口总览

端口分三套场景，别混用：

| 场景 | 服务 | 技术 | 端口 | 说明 |
|------|------|------|------|------|
| 本地裸跑 | 后端 | FastAPI + uvicorn | **8080** | `uvicorn main:app --port 8080` |
| 本地裸跑 | 前端 | Next.js | **3000** | `npm run dev` / `npm run start` |
| Docker（本机默认） | Caddy 反代 | Caddy 2 | 宿主 **8088** → 容器 80 | 本机 80/443 被其他服务占用，故默认 8088 |
| Docker（云服务器） | Caddy 反代 | Caddy 2 | 宿主 **8080** → 容器 80 | 在根 `.env` 设 `CADDY_HTTP_PORT=8080` |
| Docker（内网） | 后端 / 前端 | uvicorn / Next standalone | 8000 / 3000 | **不对宿主暴露**，仅 compose 内网互通 |

> Docker 场景统一从 Caddy 入口访问（`http://<IP>:<CADDY_HTTP_PORT>`），`/api/*` 由 Caddy 转发到
> 后端 8000，其余转发到前端 3000。不要直接暴露 8000/3000。

---

## 2. 本地开发启动

### 2.1 后端（Python 3.11）

```bash
cd backend
python -m venv venv
venv\Scripts\activate            # Windows；Mac/Linux: source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env             # 填写 LLM_API_KEY / LLM_BASE_URL / JWT_SECRET / ADMIN_PASSWORD

# 启动（强制绑定 0.0.0.0，端口 8080）
uvicorn main:app --host 0.0.0.0 --port 8080 --workers 1
```

验证：浏览器打开 `http://127.0.0.1:8080/healthz`，应返回 `{"status":"ok","db":true,"vector":true,"llm_host":true}`。

### 2.2 前端（Node 18+）

```bash
cd frontend
npm install

# 前端 .env：指向本机后端（生产环境改成 ECS 公网 IP）
#   NEXT_PUBLIC_API_URL=http://127.0.0.1:8080

npm run dev                      # 打开 http://localhost:3000
```

验证：用 `admin` 账号登录，发一条消息测试全链路。

> ⚠️ 家庭宽带是 NAT，外网无法直接访问本机 8080/3000，本地只能本机 + 局域网（同 WiFi 手机访问 `http://<电脑局域网IP>:3000`）。要外网访问必须用云服务器。

---

## 3. 阿里云 ECS 部署

### 3.1 购买服务器（关键选择）

| 项 | 建议 | 说明 |
|----|------|------|
| 地域 | **内地**：华北2（北京）/ 华东1（杭州）等 | 国内直连稳定。香港 IP 段对国内常被屏蔽（实测换多个 IP 均无法访问） |
| 规格 | **2核4G** 起步 | 实测：backend 629.8 MiB + frontend 23 MiB + caddy 14.5 MiB（本机 `docker stats`，空闲态），2核4G 有约 3GB 余量。**2核2G 不要用**（构建期必爆，运行期无余量） |
| 系统盘 | **≥60 GB** | 后端镜像 **3.92 GB** + 前端 ~200 MB + `chroma_db` 492 MB + 构建缓存。若只能拿到 40 GB（见下方算力包），**绝不能在服务器上 build** |
| 带宽 | **≥3 Mbps** 或按使用流量 | 1 Mbps = 128 KB/s，Next.js 首屏会慢到 10s+ |
| 镜像 | **Ubuntu 22.04 64位** | |
| 安全组 | 放行 **22**、**8080**（见第 5 节） | 8080 对应 `CADDY_HTTP_PORT` |

#### 备案（决定能不能用域名 / HTTPS）

- 用 `http://<公网IP>:<非80端口>` 访问 —— **不需要备案**。
- 用域名 + 80/443（HTTPS）—— **必须 ICP 备案**，且阿里云要求：ECS **包年包月 ≥3 个月** +
  **已购公网带宽** + **中国内地节点**，才发放备案服务码。**按量付费实例与免费试用实例不支持备案。**

#### 学生优惠（如你走高校计划，2026-10-27 核实）

价格与规则随时调整，**下单前一律以官网页面/结算页实际显示为准**：

| 渠道 | 额度 / 时长 | 能否备案 | 备注 |
|------|------------|---------|------|
| 免费试用（个人版） | 300 元额度 / 3 个月，最高 4核8G | ❌ | 限 ECS 产品新用户；每月 20 GB 内地免费流量 |
| 学生算力包 · 练手包 | 150 元额度 / 1 个月 | ❌ | |
| 学生算力包 · 毕设包 | 850 元额度 / 6 个月，最高 4核8G | ❌ | 页面明示可用 300 元学生券抵扣 |
| 学生算力包 · 科创包 | 2000 元额度 / 6 个月，最高 8核16G | ❌ | |
| ECS 包年包月 | 按配置付费 / 1 年 | ✅ | 唯一能走备案的路径 |

> ⚠️ 学生算力包的硬约束（官方 FAQ）：
> ① **只能创建按量付费实例 ⇒ 不支持 ICP 备案**；
> ② 系统盘**固定 40 GB ESSD Entry，不可改容量/类型**；
> ③ 地域限 华北2（北京）/ 华东1（杭州）/ 华北6（乌兰察布）/ 华南2（河源）；
> ④ 每月 20 GB 内地免费流量，超出按量计费；
> ⑤ 额度按小时抵扣，有每小时上限（练手 1.21 / 毕设 1.14 / 科创 2.69 元）。
> ⑥ 300 元学生券规则：**不可与产品折扣叠加**、不可用于 99 元学生机、同订单不可与其他券并用。
> 停机不收计算费（只收磁盘费）⇒ 按需启停可显著延长额度可用时长。

### 3.2 上传代码到服务器

> ⚠️ **不要 `scp -r` 整个仓库**。本仓库根目录有大量临时产物（`_pt_*`、`_*.txt`、`_pytest_*`）、
> `backend/venv-new`（1.43 GB）、`frontend/node_modules`、`.git`，整树传会多传好几个 GB 且极慢。

**必传**（少一个就会"起来但答不了题"）：

| 路径 | 体积 | 缺了会怎样 |
|------|------|-----------|
| `backend/chroma_db/` | 492 MB | **问答零召回**（向量库不在镜像里，靠挂载） |
| `backend/data/` | 20 MB | 空库 —— `app.db`（用户/会话真源）与 `quota_used.sqlite` 都在这 |
| `backend/media/`、`backend/backups/` | 数 MB | 上传文件丢失、无法回滚 |
| `backend/knowledge_base/` | 48 KB | 知识源缺失 |
| `backend/*.py`、`requirements.txt`、`Dockerfile`、`.dockerignore` | — | 后端本体 |
| `frontend/`（不含 `node_modules`） | — | 前端本体 |
| `docker-compose.yml`、`Caddyfile` | — | 编排与反代 |

**排除**：`.git/`、`backend/venv*/`、`frontend/node_modules/`、`_pt_*`、`_pytest_*`、`_*.txt`、`diag/`、`dispatch-output/`、`evals/`、`reports/`。

```bash
# 推荐 rsync（可续传、可排除）。Windows 端可用 WinSCP 手动挑目录，或 Git Bash 自带 rsync
rsync -avz --progress \
  --exclude '.git/' --exclude 'backend/venv*/' --exclude 'frontend/node_modules/' \
  --exclude '_pt_*' --exclude '_pytest_*' --exclude '_*.txt' \
  --exclude 'diag/' --exclude 'dispatch-output/' --exclude 'evals/' --exclude 'reports/' \
  /path/to/ai-legal-helper/ root@<ECS公网IP>:/opt/fazhi/

# 空目录需先建（compose 会挂载它们）
ssh root@<ECS公网IP> 'mkdir -p /opt/fazhi/caddy_data /opt/fazhi/caddy_config'
```

> `.env` 含全部密钥，**不要走 git**，用 `scp` 单独传并确认权限 `chmod 600`。

### 3.3 方式 A：Docker 部署（推荐）

> **现成脚本（2026-10-28 新增，优先用脚本，别照着文档手敲）**：
> | 脚本 | 在哪跑 | 作用 |
> |------|--------|------|
> | `deploy/server-init.sh` | 服务器（root） | 装 Docker、4G swap、ufw 放行 22/8080、建 `/opt/fazhi` |
> | `deploy/package-and-upload.sh` | 本地 | 构建镜像 → `docker save` → 打包代码与数据 → scp 上传 |
> | `deploy/deploy.sh` | 服务器 | 变量自检 → `compose config` 干跑 → `up -d` → 等 healthz → **核对嵌入配置** |
>
> `deploy/deploy.sh` 内置了"宁可起不来也不带病上线"的 fail-fast：环境变量缺失直接退出；
> healthz 通过后还会核对启动日志里的 `[startup] embedding provider=aliyun`，
> 不符则判失败退出（防的就是"healthz 全绿但问答零召回"）。

```bash
cd /opt/fazhi
cp .env.example .env             # 填 LLM_API_KEY / JWT_SECRET / ADMIN_PASSWORD / EMBEDDING_* 等
# 云服务器场景：在 .env 里加一行 CADDY_HTTP_PORT=8080（默认 8088 是本机口径）
echo 'CADDY_HTTP_PORT=8080' >> .env
docker compose config           # 先干跑：校验变量是否齐全（缺必填项会在此处报错）
docker compose up -d --build
```

#### ⛔ 不要在服务器上 build 后端镜像

后端镜像 **3.92 GB**（CPU torch 2.6.0 + BGE 模型烘焙，早期写的 1.5 GB 已过时），build 时要拉
torch wheel（~800 MB）并下载 BGE 模型（~400 MB）：

- 40 GB 系统盘（学生算力包固定值）**会被构建缓存撑爆**；
- 2 核小规格实例上构建会非常慢（torch/BGE 都是 CPU 密集，经验估计 30~60 分钟量级）。

正确做法二选一：

1. **本地 build → 推阿里云 ACR（个人版免费）→ 服务器 pull**（推荐，可重复部署）；
2. 服务器 build 时先加 swap，并在成功后立刻 `docker builder prune -af` 清缓存。

#### 关于 `mem_limit`

`docker-compose.yml` 里 backend 默认 `${BACKEND_MEM_LIMIT:-2g}`。实测常驻 629.8 MiB，2g 有余量；
4核8G 机型可在 `.env` 设 `BACKEND_MEM_LIMIT=3g`；本机跑批量评测可设 `4g`。

### 3.4 方式 B：裸跑（uvicorn + next）

后端：

```bash
cd /opt/fazhi/backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn main:app --host 0.0.0.0 --port 8080 --workers 1
```

前端：

```bash
cd /opt/fazhi/frontend
# 把 frontend/.env 改成 ECS 真实公网 IP：
#   NEXT_PUBLIC_API_URL=http://<ECS公网IP>:8080
npm install
npm run build
npm run start                    # 监听 0.0.0.0:3000
```

### 3.5 外网访问

Docker 场景统一走 Caddy 入口（假设 `CADDY_HTTP_PORT=8080`）：

- 健康检查：`http://<ECS公网IP>:8080/healthz`
- 网页界面：`http://<ECS公网IP>:8080`

裸跑场景才各自暴露：后端 `http://<ECS公网IP>:8080`、前端 `http://<ECS公网IP>:3000`（需放行 3000）。

### 3.6 部署后必做的三项验证

**不要只看 `/healthz` 就认为上线成功** —— 健康检查不碰嵌入，配置错了它照样 200。

```bash
# 1) 健康检查
curl -s http://<ECS公网IP>:8080/healthz        # 期望 db:true, vector:true

# 2) 核对实际生效的嵌入配置（最关键：必须是 aliyun + 云端集合名，不是 local）
docker compose logs backend 2>&1 | grep '\[startup\] embedding'
# 期望：provider=aliyun model=qwen3.7-text-embedding-flash dims=1024 collection=<云端集合名>
# 若出现 provider=local ⇒ EMBEDDING_* 没注入 ⇒ 会加载本地 BGE 并切到 _LOCAL 集合 ⇒ 零召回

# 3) 实测内存
docker stats --no-stream
```

**然后必须发一条真实问题**，确认能召回条文并给出引用。零召回/答非所问 = 嵌入配置回落，见第 6 节。

---

## 4. 环境变量说明

### 4.0 先搞清楚：配置从哪个文件读（容器场景最容易踩）

| 部署方式 | 配置来源 | 说明 |
|---------|---------|------|
| **Docker（compose）** | **仓库根 `.env`** | compose 自动加载根 `.env`，但**只有列进 `docker-compose.yml` 的 `environment:` 白名单的变量才会真正传进容器**。当前白名单：`LLM_*`、`SILICONFLOW_*`、`EMBEDDING_*`、`RERANK_*`、`AGENT_*`、`JWT_SECRET`、`ADMIN_*`、`HF_ENDPOINT`、`COVERAGE_GATE_MODE`。**新增变量必须同步加白名单，否则容器内读不到。** |
| Docker | ~~`backend/.env`~~ | **容器内不存在**：`backend/.dockerignore` 明确排除 `.env`（防密钥进镜像）。别指望它生效。 |
| 裸跑 | `backend/.env` | `main.py` 的 `load_dotenv()` 直接读它 |

> 历史教训（2026-10-27 修）：`EMBEDDING_*` 曾漏在白名单外 ⇒ 容器里 `embedding_provider` 静默
> 回落 `local` ⇒ 加载本地 BGE（+1 GB）+ 切到 `_LOCAL` 集合（与云端 1024 维库对不上）⇒ **零召回**，
> 而 `/healthz` 仍 200。现已补白名单，并在 `main.py` 启动期加了 fail-fast 校验。

### 4.1 后端环境变量

| 变量 | 必填 | 说明 |
|------|------|------|
| `LLM_API_KEY` | ✅ | 大模型 API Key |
| `LLM_BASE_URL` | ✅ | OpenAI 兼容接口地址（可配千问/DeepSeek/智谱等） |
| `JWT_SECRET` | ✅ | 登录令牌签名密钥，部署前务必改成随机长字符串 |
| `ADMIN_USERNAME` | ✅ | 管理员用户名（默认 admin） |
| `ADMIN_PASSWORD` | ✅ | 管理员密码（务必修改默认值） |
| `SELF_REGISTER` | ❌ | 公开注册开关（`true`=允许，默认 `false` 关闭，只管理员开户） |
| `EMBEDDING_PROVIDER` | ⚠️ | `aliyun`（云嵌入）/ `local`（本地 BGE CPU）。**代码默认 `local`，compose 默认注入 `aliyun`** —— 两边不一致是事故源，部署后按 3.6 节核对 |
| `EMBEDDING_API_KEY` | provider=aliyun 时 ✅ | 云嵌入 key。缺失会导致启动期 fail-fast（不会带病上线） |
| `EMBEDDING_BASE_URL` | provider=aliyun 时 ✅ | 云嵌入 OpenAI 兼容地址 |
| `EMBEDDING_MODEL` | ❌ | 云嵌入模型名，如 `qwen3.7-text-embedding-flash` |
| `EMBEDDING_DIMENSIONS` | ⚠️ | **必须与已建向量库一致（当前 1024）**。改了就必须 `scripts/rebuild_embeddings.py` 重建库，否则维度不匹配 |
| `BACKEND_MEM_LIMIT` | ❌ | 容器内存上限，默认 `2g`（实测常驻 629.8 MiB） |
| `CADDY_HTTP_PORT` | ❌ | Caddy 宿主端口，默认 `8088`；云服务器设 `8080` |
| `RERANK_ENABLED` | ❌ | 是否启用重排（`true`/`false`） |
| `RERANK_API_KEY` | ❌ | 重排服务 key |
| `RERANK_MODEL` | ❌ | 重排模型名 |
| `ZHIPUAI_API_KEY` | ❌ | 智谱模型 key（用智谱模型时填） |

### 4.2 前端 `frontend/.env`

| 变量 | 必填 | 说明 |
|------|------|------|
| `NEXT_PUBLIC_API_URL` | 视场景 | 前端访问后端的绝对地址：本地 `http://127.0.0.1:8080`；生产 `http://<ECS公网IP>:8080`。用 Docker 同源反代时**不要设置**（走相对路径 `/api`） |

> ⚠️ 敏感凭据（LLM_API_KEY / JWT_SECRET / ADMIN_PASSWORD）**绝不能提交进 git**，`.env` 已在 `.gitignore` 中。

---

## 5. 端口放行清单

### 5.1 云服务器安全组（阿里云控制台 → 安全组）

| 端口 | 协议 | 用途 | 必须放行？ |
|------|------|------|-----------|
| **8080** | TCP | Caddy 入口（= `.env` 里的 `CADDY_HTTP_PORT`） | ✅ 必须 |
| **3000** | TCP | 前端界面（**仅裸跑方式**；Docker 走 Caddy，不放行） | 看部署方式 |
| **22** | TCP | SSH 远程维护 | ✅ 建议 |
| 80 / 443 | TCP | Caddy 改用域名 + 自动 HTTPS | 用域名/备案时 |

> 端口改了要同步三处：安全组、系统防火墙（`ufw`/`firewalld`）、`.env` 的 `CADDY_HTTP_PORT`。

> 安全组放行后还需确认系统防火墙（`ufw`/`firewalld`）没拦截，以及 Docker `ports` 映射了对应宿主端口。

### 5.2 本地 Windows 防火墙

局域网手机要访问 `http://<电脑IP>:3000` 时，需在 Windows 防火墙入站规则放行 **3000**（和 8080）。

---

## 6. 常见问题

| 问题 | 排查 |
|------|------|
| 服务器自测通、外网打不开 | 检查安全组是否放行 8080（= `CADDY_HTTP_PORT`）；香港服务器需换内地地域 |
| 手机 `failed to fetch` | 前端 `NEXT_PUBLIC_API_URL` 是否指向可访问的后端地址；是否 build 时内联了 `localhost` |
| 健康检查 `db:false` | 检查数据卷权限、SQLite 路径；`backend/data/app.db` 是否随代码上传（3.2 节） |
| 回答 500 | 检查 `.env` 里 LLM 配置是否完整（缺 key 的 provider 会被跳过） |
| **`/healthz` 全绿但问答零召回 / 答非所问** | 十有八九是嵌入配置回落：`docker compose logs backend \| grep '\[startup\] embedding'`，若为 `provider=local` ⇒ `EMBEDDING_*` 没进容器（见 4.0 节），或本地库与云端库维度不一致。另确认 `chroma_db/` 已上传 |
| build 时磁盘写满 / 极慢 | 别在服务器上 build（3.3 节）：镜像 3.92 GB + 构建缓存，40 GB 盘必爆。改本地 build 推 ACR |
| 容器被 OOM kill | `docker stats` 看实测；上调 `.env` 的 `BACKEND_MEM_LIMIT`（默认 2g），或给 ECS 加 swap |
| `docker compose up` 报 "EMBEDDING_API_KEY required" | 根 `.env` 缺该项（compose 白名单用 `:?` 强制）。裸跑场景不受影响 |
