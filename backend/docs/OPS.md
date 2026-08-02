# 运维手册（OPS）

> 面向本地 / Docker 双模式部署。诚实标注：本项目**本地单进程**运行（uvicorn 单 worker），
> 多 worker 会撞本地 Chroma / SQLite 锁（见 docs/ADR.md 并发模型条目）。

---

## 0. 端口约定

| 服务 | 端口 | 说明 |
|------|------|------|
| 后端 API | 8000 | FastAPI（`/api/health` 存活、`/healthz` 深度就绪） |
| 前端 | 3000 | Next.js（Next dev 端口被占会自动 +1，后端 CORS 已用正则放行 localhost 任意端口） |

换端口：后端 `PORT=8001 python manage.py start`；前端 `npm run dev -- -p 3001`。

---

## 1. 本地启停（manage.py）

```bash
cd backend
python manage.py status                # 端口是否被监听 + healthz 是否响应
python manage.py start                 # 启动（日志 backend/logs/backend.log）
python manage.py stop                  # 停止（按端口找 PID 结束）
python manage.py test                  # 测试前检查：端口被占 → 提示退路
```

`test` 端口被占时**不无脑杀进程**——需 `--force`，或用 `PORT=8001` 换端口。

前端：`cd frontend && npm run dev`。

---

## 2. 备份 / 恢复

```bash
cd backend
python scripts/backup_data.py                         # 默认到 ../backups/<时间戳>/
python scripts/backup_data.py --out D:/my_backup      # 指定目录
```

备份内容：SQLite（`sqlite3 backup API`，WAL 安全）+ `chroma_db` 目录 + 可选条文元数据 JSON。
**备份后自动做恢复验证**：复制到临时库跑 `PRAGMA integrity_check`，FAIL 会标红——光备份不验证等于没备份。

恢复步骤：
1. `python manage.py stop`（后端停止，避免写竞争）
2. 备份文件放回：`app.db` → `backend/app.db`；`chroma_db/` → `backend/chroma_db/`
3. `python manage.py start`，发一个检索问题确认召回正常

---

## 3. 如何判断出问题了

| 症状 | 排查路径 |
|------|----------|
| 页面打不开 / API 拒绝 | `python manage.py status` → 未运行则 `start` 并看日志 |
| 后端日志报错 | `backend/logs/backend.log` 尾部；搜索 `Traceback` |
| `/healthz` 返回 503 | 看响应体 `{"db":bool,"vector":bool,"llm_host":bool}`：`db:false` 查 SQLite 权限/磁盘；`vector:false` 查 `chroma_db/` 是否损坏；`llm_host:false` 为软检查（主机可达≠key 有效） |
| 流式回复为空 / 卡住 | 检查 LLM_API_KEY / LLM_BASE_URL（`.env`）；`llm_registry` 构建失败会在启动日志 |
| 检索不到新导入条文 | 导入后需重启后端（Chroma 索引在进程内缓存） |
| 回答引用不存在条文 | 这是引用校验（`citation_verify`）的设计：校验失败会带注释；误报时核对知识库是否真有该条 |

---

## 4. 本地内存约束（Windows）

- 后端加载 BGE 模型约 400-500MB，Docker 也解决不了宿主页面文件问题。
- **页面文件过小会崩**：现象是 `OSError: [WinError 1455] 页面文件太小` 或 torch 段错误。
  建议把 Windows 页面文件调到 **8-16GB**（设置 → 系统 → 关于 → 高级系统设置 → 性能设置 → 虚拟内存）。
- 导入大批法律条文（嵌入）前先 `manage.py stop`，避免两个进程争内存。

---

## 5. Docker 部署

```bash
cp .env.example .env        # 填 LLM_API_KEY / JWT_SECRET / ADMIN_PASSWORD
docker compose up -d --build
```

- 后端镜像约 **1.5GB**（BGE 模型烘焙，启动不联网）。
- 首次构建 10-20 分钟（CPU torch + 模型，国内镜像已配）。
- 数据持久化在 `backend/chroma_db`、`backend/media`、`backend/data`（挂载卷）。
- `restart: unless-stopped`；前端 `depends_on` 后端健康才起。
- **已知限制**：`mem_limit` 只限容器内内存；Docker 不解决宿主页面文件；单 worker 并发模型不变。

### Docker Desktop on Windows：WSL2 内存上限

WSL2 默认可能吃光内存。建议 `C:\Users\<你>\.wslconfig`：

```ini
[wsl2]
memory=8GB
swap=4GB
processors=4
```

改后 `wsl --shutdown` 重启 WSL 生效。
