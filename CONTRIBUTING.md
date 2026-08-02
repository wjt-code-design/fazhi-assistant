# 贡献指南

欢迎贡献。原则：**回归门禁先绿、诚实标注、法律文本零改动**。

## 开发流程

1. **装开发依赖**：`pip install -r backend/requirements-dev.txt`（含 ruff / mypy / pytest-cov / pre-commit）。
2. **安装 pre-commit**：`pre-commit install` —— 提交前自动跑 ruff + 文件卫生。
3. **改后端**：每个改动跑 `python -m pytest` + `ruff check .` + `mypy .`。
4. **改检索/引用**：额外跑 `python scripts/smoke_citation_fast.py`（17 项非 LLM 门禁）。
5. **发版前**：跑 `python scripts/smoke_citation_full.py`（10 场景含 LLM，需后端运行 + `.env` 有 key）。

## 门禁规则

- **提交前**：pre-commit（ruff + trailing-whitespace + end-of-file）+ 相关测试。
- **CI**：ruff / mypy / pytest（`-m "not slow"`）/ cov ≥70 / 前端 build。新增真实 KB 或嵌入相关测试请标 `@pytest.mark.slow`。
- **严禁**：把 `.env`、密钥、用户数据、`chroma_db/`、`*.db` 提交进仓库（`.gitignore` / `.dockerignore` 已拦，但请自检）。

## 法律文本铁律

- 清洗（`clean_law_text.py`）**绝不改写条文文字**，只做格式层；删除前用 `--dry-run` 审计。
- 知识库以用户上传文本为权威来源；不要手工「修正」条文内容。

## 代码风格

- 后端：ruff（line-length 120）+ ruff format；mypy（SQLAlchemy 密集模块有基线 override，见 `backend/pyproject.toml`）。
- 前端：Next.js 自带 ESLint + tsc（`npm run build` 会检查）。
- 新硬编码的条文映射放进 `backend/domain_rules.py`（单一来源），不要散落。

## 测试

- 纯逻辑（切分/检索/引用校验/意图）写无依赖单测；编排路径用 mock（`FakeChain` / monkeypatch）。
- 测试命名即规格：`test_<行为>`，期望值来自独立来源（已知条文/手算样例），不「复算实现」。
