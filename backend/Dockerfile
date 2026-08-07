# ===== 后端镜像：CPU torch + BGE 模型烘焙 + HEALTHCHECK =====
# 诚实标注：镜像约 1.5GB（BGE-base 烘焙进镜像，避免容器启动时联网下载）。
# Docker 不解决宿主页面文件 / 内存限制问题（本地仍受 Windows 内存约束）。

FROM python:3.11-slim AS base
WORKDIR /app

# 国内构建加速（也可由构建机自身 pip/hf 配置替代）
# 2026-08-08：tuna 镜像同步故障（fastapi 全系不可用），换阿里云源（已验证 0.110.3 可用）
ENV HF_ENDPOINT=https://hf-mirror.com
ENV PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple

# 先装 CPU 版 torch（避免 PyPI 默认拉取数 GB CUDA 包）
COPY requirements.txt .
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir -r requirements.txt

# 烘焙 BGE 嵌入模型（构建期下载一次，运行时零联网）
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('BAAI/bge-base-zh-v1.5')"

COPY . .

# 防呆（对抗审计 v2 #3）：若 .dockerignore 失效导致 backend/.env 被 COPY 进镜像，构建必须失败——
# 镜像层含真实 LLM_API_KEY/JWT_SECRET 属机密泄漏，宁可构建红也不带病上线
RUN test ! -f /app/.env || (echo "ERROR: backend/.env 被复制进镜像，密钥泄漏风险；请检查 backend/.dockerignore" && exit 1)

# 健康检查：/healthz（DB + 向量库就绪即 200；不发起真实 LLM 调用）
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/healthz', timeout=5).close()"

EXPOSE 8000
# 配置经环境变量注入（docker-compose environment / .env），不在镜像内
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
