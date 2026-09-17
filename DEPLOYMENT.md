# 法智 · 部署指南

> 简易部署文档：本地开发启动 → 阿里云 ECS 部署 → 环境变量 → 端口放行。
> 面向 2~3 人小规模使用，单机部署。详见 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)。

---

## 1. 服务与端口总览

| 服务 | 技术 | 默认端口 | 说明 |
|------|------|---------|------|
| 后端 | FastAPI + uvicorn | **8080** | API / 登录 / 问答 / 管理 |
| 前端 | Next.js 14 | **3000** | 网页界面（dev 模式） |
| 生产（可选） | Docker + Caddy | 80/443 或 8080 | 反代同源，前端/后端容器内网互通 |

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

| 项 | 建议 |
|----|------|
| 地域 | **内地**（北京/上海/杭州/成都）——国内直连稳定，不受 GFW 干扰 |
| 规格 | 经济型 e，2核4G（RAG + 模型推理够用） |
| 镜像 | **Ubuntu 22.04 64位** |
| 安全组 | **放行 22、8080**（见第 5 节） |

> 为什么选内地：香港 IP 段对国内常被屏蔽（实测换多个 IP 均无法访问）。内地用 `IP:8080` 这种非标准端口访问**不需要备案**（只有 80/443 才要求备案）。

### 3.2 上传代码到服务器

```bash
# 把本地项目传到服务器 /opt/fazhi（WinSCP / scp / Workbench 上传均可）
scp -r /path/to/ai-legal-helper root@<ECS公网IP>:/opt/fazhi
```

### 3.3 方式 A：Docker 部署（推荐，一条命令）

```bash
cd /opt/fazhi
cp .env.example .env             # 填 LLM_API_KEY / JWT_SECRET / ADMIN_PASSWORD 等
docker compose up -d --build
```

- 后端镜像约 1.5GB（BGE 模型烘焙），首次构建 10~20 分钟
- Caddy 统一入口：把 `docker-compose.yml` 里 caddy 的 `ports` 映射为 `"8080:80"`（服务器场景），即通过 `http://<ECS公网IP>:8080` 访问

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

- 后端 API：`http://<ECS公网IP>:8080/healthz`
- 前端界面：`http://<ECS公网IP>:3000`（需安全组放行 3000）

---

## 4. 环境变量说明

### 4.1 后端 `backend/.env`

| 变量 | 必填 | 说明 |
|------|------|------|
| `LLM_API_KEY` | ✅ | 大模型 API Key |
| `LLM_BASE_URL` | ✅ | OpenAI 兼容接口地址（可配千问/DeepSeek/智谱等） |
| `JWT_SECRET` | ✅ | 登录令牌签名密钥，部署前务必改成随机长字符串 |
| `ADMIN_USERNAME` | ✅ | 管理员用户名（默认 admin） |
| `ADMIN_PASSWORD` | ✅ | 管理员密码（务必修改默认值） |
| `SELF_REGISTER` | ❌ | 公开注册开关（`true`=允许，默认 `false` 关闭，只管理员开户） |
| `EMBEDDING_PROVIDER` | ❌ | 嵌入模型来源（默认本地 BGE，无需 key） |
| `EMBEDDING_MODEL` | ❌ | 嵌入模型名（本地 BGE 模型） |
| `EMBEDDING_API_KEY` | ❌ | 云嵌入服务 key（仅用云端嵌入时填） |
| `EMBEDDING_BASE_URL` | ❌ | 云嵌入服务地址 |
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
| **8080** | TCP | 后端 API（外网访问核心） | ✅ 必须 |
| **3000** | TCP | 前端界面（裸跑方式） | 看部署方式 |
| **22** | TCP | SSH 远程维护 | ✅ 建议 |
| 80 / 443 | TCP | Caddy 生产反代 | 用域名/备案时 |

> 安全组放行后还需确认系统防火墙（`ufw`/`firewalld`）没拦截，以及 Docker `ports` 映射了对应宿主端口。

### 5.2 本地 Windows 防火墙

局域网手机要访问 `http://<电脑IP>:3000` 时，需在 Windows 防火墙入站规则放行 **3000**（和 8080）。

---

## 6. 常见问题

| 问题 | 排查 |
|------|------|
| 服务器自测通、外网打不开 | 检查安全组是否放行 8080；香港服务器需换内地地域 |
| 手机 `failed to fetch` | 前端 `NEXT_PUBLIC_API_URL` 是否指向可访问的后端地址；是否 build 时内联了 `localhost` |
| 健康检查 `db:false` | 检查数据卷权限、SQLite 路径 |
| 回答 500 | 检查 `.env` 里 LLM 配置是否完整（缺 key 的 provider 会被跳过） |
