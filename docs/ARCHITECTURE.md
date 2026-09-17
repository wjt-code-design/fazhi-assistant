# 系统架构

> 诚实标注：本项目**本地单进程**架构（uvicorn 单 worker）。扩展并发需要换托管向量库/数据库，
> 路径见文末「扩展路径」。不做「开箱即分布式」的过度宣称。

---

## 1. 总览

```
┌─────────────┐     HTTP/JSON     ┌──────────────────────────────────────────────┐
│  Next.js 14 │ ────────────────► │  FastAPI（uvicorn 单 worker）                 │
│  (frontend) │  ◄──────────────  │  ├─ auth / 会话 / 反馈（SQLite + SQLAlchemy）  │
└─────────────┘   SSE 流式回答    │  ├─ 意图分流（classify_intent）                │
                                 │  ├─ 检索编排（retrieval）                     │
                                 │  ├─ 引用校验（citation_verify）               │
                                 │  └─ LLM 网关（llm_registry → 多模型配额路由）  │
                                 └───────────────┬──────────────────────────────┘
                                                 │
                      ┌──────────────────────────┼──────────────────────────┐
                      ▼                          ▼                          ▼
               ┌─────────────┐          ┌──────────────┐          ┌────────────────┐
               │ Chroma 向量 │          │ SQLite       │          │ 本地嵌入模型    │
               │ 库           │          │ app.db       │          │ BGE-base-zh    │
               │ (条文分片)   │          │ (用户/会话)  │          │ (CPU)          │
               └─────────────┘          └──────────────┘          └────────────────┘
```

---

## 2. 知识库构建链路（用户上传 → 可检索条文）

```
.docx / .txt ──► convert_docx.py（docx→txt）──► clean_law_text.py（清洗+门禁）
   ──► chunking.split_law_document（按「第X条」边界切分，章节前缀注入）
   ──► BGE 嵌入 ──► Chroma（legal_provisions_cos 集合，hnsw:space=cosine——
       距离分=1-cos，检索精排免重复嵌入；旧 L2 集合 legal_provisions 已废弃删除）
```

- **清洗铁律**：只做格式层（空行/页码残留），**绝不改写条文文字**；`--dry-run` 先审计。
- **去重**：按清洗后全文 sha256（file_hash）幂等，重跑安全。
- **结构化切分**：条号正则行首锚定 + 目录页跳过 + 章节标题作为 chunk 前缀（不是边界）。
- 当前知识库：99 部法律、10266 个分片（2026-08-02 快照）。

---

## 3. 问答数据流（核心价值，citation 流高亮）

```
用户提问
  │
  ▼
意图分流 classify_intent
  ├─ study_aid（法学生做题）→ 学习引导提示，不检索
  ├─ cheating_request（作弊索取）→ 定向检索刑法284之一 + 治安法27，释法拒答
  └─ legal_query（正常法律咨询）───────────► 主路径 ↓
                                             │
                      条号直查路由 parse_article_query
                      ├─ 命中《法名》第X条 → exact_article_lookup（零嵌入精确查找）
                      └─ 未命中 → 混合检索 retrieve（向量 + BM25(jieba) RRF 融合）
                                             │
                      + 消费者格式条款场景 → 定向补充 民法典496/497 + 消保法26
                      + 多轮：rewrite_query 改写含指代的提问 + 增量摘要压缩
                                             │
                      ▼
                 上下文拼装 → LLM 流式回答
                                             │
                      ▼
                 引用校验 citation_verify ◄── 答案中抽取《法名》第X条
                 ├─ 命中知识库 → 保留（标注来源）
                 └─ 未命中 → 追加「(注：该条未在知识库中检索到，请核对原文)」
                                             │
                      ▼
               SSE 流式返回前端（含元数据：conversation_id）
```

**关键设计**：
- **条号直查路由**在前，混合检索在后——「《劳动法》第3条」这类精确查询零嵌入、零检索，快且准。
- **引用校验以知识库存在性为准**（`article_in_kb`，容忍源名差异如「宪法（1982年）」），
  不依赖本轮检索作用域——跨法编造（把民法典条文挂到电商法名下）会被判不在库。
- **受控沉淀**（curation）：高置信回答进 QA 库，低置信留给人工。

---

## 4. 组件清单

| 模块 | 职责 |
|------|------|
| `main.py` | FastAPI 入口、提示词组装、意图分流编排 |
| `intent.py` | 意图分类（作弊/学习/咨询） |
| `retrieval.py` / `retrieval_core.py` | 混合检索（向量+BM25 RRF）、条号直查、引用校验 |
| `chunking.py` | 法律文档结构化切分 |
| `clean_law_text.py` / `convert_docx.py` | 导入管线（清洗/转换） |
| `domain_rules.py` | 硬编码条文映射与提示词规则的单一来源 |
| `memory.py` | 多轮上下文、增量摘要压缩、查询改写 |
| `knowledge_service.py` | 知识增删、QA 库、上传 |
| `curation.py` | 受控沉淀（QA 候选） |
| `multimodal.py` | 图片校验/持久化/视觉内容构造 |
| `auth.py` / `database.py` / `models.py` | 鉴权、ORM、迁移 |

---

## 5. 测试与门禁

- **单元/集成测试**：pytest 114 个（含 mock LLM/向量库，CI 零 token 可跑）。
- **回归门禁**三档：
  - 快：`smoke_citation_fast.py`（17 项，非 LLM，pre-commit/CI）
  - 慢：CI（pytest 跳 slow + ruff/mypy/cov≥70 + 前端 build）
  - 全量：`smoke_citation_full.py`（10 场景，含 LLM，release 前跑）

---

## 6. 扩展路径（诚实：现在不做，路径在）

- **并发**：本地单 worker 是唯一安全配置。`--workers>1` 会撞 Chroma/SQLite 写锁。
  扩并发 = 换托管向量库（Qdrant/PGVector）+ 托管 PostgreSQL，再上多 worker/水平扩容。
- **LLM**：多模型配额路由已启用（`llm_registry.DEFAULT_ROLES` 27 条目：qwen3.5-omni-plus 旗舰 /
  qwen3.5-flash、deepseek-v4-flash 轻量；按 priority/failover 降级、thinking 开关、配额轮换与耗尽
  自动回落、轻量 tier 门禁）。总开关 `feature_router`，整体覆盖入口 `LLM_MODELS_JSON`（对抗审计 v2 #23 修正旧"单一模型"描述）。
- **部署**：Docker 单机已就绪；k8s/serverless 需先解决持久化与并发。
- **前端**：当前 SSR + 轻量 PWA 能力；复杂 SW/原生 App 未做。

## 7. 已知限制

- 本地页面文件过小会触发 OSError 1455 / torch 段错误（见 OPS.md）。
- study_aid 内嵌事实降级、检测收紧等边界后置（见 ADR）。
- 单 worker 并发上限受模型推理速度限制（CPU 嵌入 + 单 LLM 流式）。
