# 法智 · AI 法律咨询助手

基于 RAG 的本地部署法律咨询助手：法律条文知识库（99 部法律 · 10266 分片）+ 混合检索 + 引用校验 + 多模型配额路由。

核心能力：**引用真实性校验**（回答中的条文逐条核对知识库、杜绝编造）、**意图分流**（法考答题引导 / 作弊拒答 / 正常咨询）、**混合检索**（条号直查 + 向量 + BM25 融合）、**多模型配额路由**、**三级质量门禁**（fast / CI / full），支持 Docker 一键部署与增量导入管线（docx→清洗→切分→嵌入）。

---

## 功能

- 💬 多轮咨询 + 流式回答，回答底部不展示法条引用小字、不显示模型 badge
- 📚 RAG 检索：**条号直查路由**（精确命中零嵌入）+ 向量/BM25 混合检索（RRF 融合）
- ✅ **引用校验**：答案中的《法名》第X条逐条核对知识库，不存在即标注，杜绝编造
- 🧭 **意图分流**：法学生做题走学习引导、作弊索取走释法拒答、正常咨询走检索
- 🖼 图片咨询（omni 读图）、多轮上下文增量压缩、受控沉淀 QA 库
- 🔐 登录鉴权（JWT）、管理员后台（知识增删/QA 审核/用户管理/**模型配额面板**）
- 🔀 **多模型分级路由**：按复杂度/模态路由 + 轻量自检升级 + 相同问题回答缓存（零 token）+ 配额监控自动切换
- 🐳 Docker 一键部署（`docker compose up`）

## 快速开始

### 本地开发

```bash
# 后端（Python 3.11）
cd backend
python -m venv venv
venv\Scripts\activate            # Windows；Mac/Linux 用 source venv/bin/activate
pip install torch --index-url https://download.pytorch.org/whl/cpu   # CPU torch，避免 CUDA 数 GB
pip install -r requirements.txt
cp .env.example .env            # 填入 LLM_API_KEY / LLM_BASE_URL / JWT_SECRET
python manage.py start           # 启动后端（日志 backend/logs/backend.log）

# 前端（Node 18+）
cd frontend
npm install
npm run dev                      # 打开 http://localhost:3000
```

### Docker（推荐部署）

```bash
cp .env.example .env             # 填 LLM_API_KEY / JWT_SECRET / ADMIN_PASSWORD
docker compose up -d --build
# 前端 http://localhost:3000   后端健康检查 http://localhost:8000/healthz
```

> 后端镜像约 1.5GB（BGE 模型烘焙）；首次构建 10-20 分钟（国内镜像已配）。详见 `backend/docs/OPS.md`。

## 项目结构

```
├─ backend/                  # FastAPI 后端
│  ├─ main.py                # 入口 / 提示词组装 / 意图分流编排
│  ├─ retrieval*.py          # 混合检索 / 条号直查 / 引用校验
│  ├─ chunking.py            # 法律文档按条号结构化切分
│  ├─ domain_rules.py        # 条文映射与提示词规则单一来源
│  ├─ memory.py              # 多轮上下文 / 增量摘要压缩
│  ├─ scripts/               # 导入管线（convert/clean/import）+ 回归门禁 + backup
│  ├─ manage.py              # 运维：start/stop/status/test
│  ├─ docs/                  # OPS.md 运维手册
│  └─ tests/                 # pytest 325 个
├─ frontend/                 # Next.js 14（standalone 输出，Docker ~200MB）
├─ data/                     # 法律条文导入产物（laws_raw / laws_clean）
├─ docs/                     # ARCHITECTURE.md / ADR.md
├─ docker-compose.yml
└─ .env.example
```

## API 概览

| 端点 | 说明 |
|------|------|
| `POST /api/auth/register` `/login` | 注册 / 登录（JWT） |
| `POST /api/chat` | 流式问答（SSE） |
| `GET /api/conversations` `...` | 会话历史 / 详情 |
| `POST /api/knowledge/...` | 知识增删 / 测试（管理员） |
| `POST /api/feedback` | 回答反馈 / 纠错 |
| `GET /api/health` / `/healthz` | 存活 / 深度就绪（DB+向量库） |

## 质量保障与回归门禁

三级质量门禁（`docs/ARCHITECTURE.md` 有完整说明）：

| 级别 | 触发 | 内容 | 成本 |
|------|------|------|------|
| 快速 | pre-commit / CI | `smoke_citation_fast.py`（17 项：意图+检索+引用校验） | 零 token |
| 标准 | CI | pytest（跳 slow）+ ruff/mypy + cov≥70 + 前端 build | 零 token |
| 全量 | release 前 | `smoke_citation_full.py`（10 场景含 LLM） | 有 token |

```bash
cd backend
venv\Scripts\python -m pytest -q           # 325 tests
venv\Scripts\python scripts/smoke_citation_fast.py
venv\Scripts\python scripts/smoke_citation_full.py    # 需后端运行 + LLM key
```

## 兼容性说明

前端已适配移动端：聊天与后台页面内建响应式（侧栏折叠 / 无横向溢出 / 输入框 ≥16px 防 iOS 缩放）；登录页 Lighthouse 移动端均分 ≥95（Performance 100 / Accessibility 95 / Best Practices 96 / SEO 100，详见 `docs/BENCHMARK.md`）。

## 已知限制（诚实标注）

- **并发**：本地单 worker 是唯一安全配置（多 worker 撞 Chroma/SQLite 锁）；扩并发需托管向量库+DB，见 `docs/ADR.md#ADR-007`。
- **内存**：本地页面文件过小会触发 `OSError 1455` / torch 段错误——Windows 页面文件建议 8-16GB，见 `backend/docs/OPS.md`。
- **study_aid 边界后置**：法学生做题仅引导不代写，未做细粒度内嵌事实判定（见 ADR-009）。
- **部署形态**：单机 Docker；k8s/serverless、原生 App、复杂 PWA 未做（路径在）。
- **多模型路由**：按复杂度/模态在「文本旗舰 / 全模态旗舰(兜底)」间路由，配回答缓存与配额监控（管理员后台可见，普通用户不展示模型信息）。为引用准确，弱/不可控模型已剔除，text 暂无独立轻量档——省配额主要靠缓存命中与不升级。自检为纯函数，「引在库≠引对题」的语义正确性靠 full 门禁 + 人工沉淀兜底；流式 token 为估算值；路由指标进程内、重启清零。详见 `docs/ADR.md#ADR-010`。
- **full 门禁波动**：`smoke_citation_full` 含真实 LLM，受模型固有波动影响，为 release 前抽查、允许偶发重跑。

## 开发环境搭建

```bash
cp .env.example .env      # 根目录（Docker）与 backend/.env（本地）
# 后端
cd backend && python -m venv venv && venv\Scripts\activate
pip install -r requirements-dev.txt        # 含 ruff/mypy/pytest-cov/pip-audit/pre-commit
pre-commit install                          # 提交前门禁（ruff + 文件卫生）
python manage.py start
# 前端
cd frontend && npm install && npm run dev
```

## 文档

- [`DEPLOYMENT.md`](DEPLOYMENT.md) — 部署指南（本地启动 / 阿里云 ECS / 环境变量 / 端口放行）
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — 系统架构 + citation 数据流
- [`docs/ADR.md`](docs/ADR.md) — 架构决策记录（含并发模型）
- [`backend/docs/OPS.md`](backend/docs/OPS.md) — 运维手册（启停/备份/排查/WSL2）
