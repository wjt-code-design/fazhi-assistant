# ===== 后端镜像：CPU torch + BGE 模型烘焙 + HEALTHCHECK =====
# 诚实标注：镜像约 3.92GB（2026-09-04 实测；早期注释写的 1.5GB 已过时——BGE-base 烘焙进镜像，
#   避免容器启动时联网下载）。
# Docker 不解决宿主页面文件 / 内存限制问题（本地仍受 Windows 内存约束）。

FROM python:3.11-slim AS base
WORKDIR /app

# 国内构建加速（也可由构建机自身 pip/hf 配置替代）
# 2026-08-08：tuna 镜像同步故障（fastapi 全系不可用），换阿里云源（已验证 0.110.3 可用）
ENV HF_ENDPOINT=https://hf-mirror.com
# 2026-09-04：huggingface_hub 0.36 默认启用 XET 传输协议，会把 model.safetensors 等大文件
#   直连 us.aws.cdn.hf.co（官方 CDN），绕过上面的 HF_ENDPOINT 镜像 → 国内 Read timed out。
#   实测该层靠断点续传自愈但极慢(~11min)且网络波动会红。禁用 XET 回退普通 HTTPS，使 BGE
#   模型下载走 hf-mirror.com 镜像（根治，非缓解）。代价：丧失 XET 增量续传，单次烘焙无影响。
ENV HF_HUB_DISABLE_XET=1
ENV PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple

# 先装 CPU 版 torch（避免 PyPI 默认拉取数 GB CUDA 包）
COPY requirements.txt .

# 2026-09-04 安装源切换（诚实标注原因与取舍）：
#   [失败根因] 原 --index-url https://download.pytorch.org/whl/cpu 在国内读取超时
#     （实测 download-r2.pytorch.org Read timed out）；且 --index-url 会覆盖上面的
#     PIP_INDEX_URL，使 torch 的传递依赖回落到 files.pythonhosted.org，触发
#     SSLError: UNEXPECTED_EOF_WHILE_READING 并耗尽重试。
#   [源候选实测] 在容器内实测各 pytorch-wheels 镜像的分段下载速度：
#     阿里云 ~739 kB/s（最快）> 官方 download.pytorch.org ~471 kB/s > SJTUG 61~72 kB/s（最慢）。
#     SJTUG 还出现 wheel hash 校验失败（下载被截断），已排除；清华 404、USTC 403、南大自环
#     重定向 302，均不可用。阿里云 pytorch-wheels 此前偶发 SSL 握手失败，靠下面 --retries 兜底。
#   [为什么用 --find-links 而非 --index-url] 阿里云 /pytorch-wheels/cpu/ 是一个含 3344 个 wheel
#     链接的 HTML 目录列表，并非 /cpu/torch/ 这样的 PEP 503 simple-index 子目录，--index-url
#     会让 pip 去访问不存在的 /torch/ 而 404。--find-links 直接解析该页面取 torch 本体，而
#     传递依赖仍走上面的 PIP_INDEX_URL(阿里云 PyPI)——此处不覆盖 index，正是修复原根因的关键。
#   [为什么必须钉死版本] 阿里云 PyPI 镜像上的 torch 是 2.14.0（CUDA 版，数 GB），与 find-links
#     上的 2.6.0+cpu 并存。按 PEP 440，2.14.0 > 2.6.0+cpu（本地版本标识符仅在主版本号相同时
#     才参与比较），若不钉死 pip 会选 CUDA 版。钉死 "torch==2.6.0+cpu" 后，阿里云 PyPI 上的
#     无后缀版本均不匹配该本地版本标识符，依赖混淆风险归零。
#   [已知取舍] torch 锁在 2.6.0（镜像已同步的最新 cp311+cpu 版，2025-01 发布），非最新。
#     若日后需升级：先确认镜像已同步更高 +cpu 版本，再同步修改此处与下方防呆断言。
RUN pip install --no-cache-dir --retries 10 --timeout 60 \
      "torch==2.6.0+cpu" \
      --find-links https://mirrors.aliyun.com/pytorch-wheels/cpu/

RUN pip install --no-cache-dir --retries 10 --timeout 60 -r requirements.txt

# 防呆（与下方 .env 防呆同一策略）：requirements 阶段仍可能把 torch 升级成 CUDA 版，故在此断言
# 宁可构建红，也不能带着 GPU 版 torch 静默出镜像（数 GB 体积 + 与 CPU-only 部署假设冲突）
RUN python -c "\
import importlib.metadata as md, torch; \
assert '+cpu' in torch.__version__, 'torch 非 CPU build: %s' % torch.__version__; \
assert torch.version.cuda is None, 'torch 含 CUDA: %s' % torch.version.cuda; \
nv = sorted({(d.metadata['Name'] or '') for d in md.distributions() if (d.metadata['Name'] or '').startswith('nvidia-')}); \
assert not nv, '检测到 nvidia-* CUDA 包: %s' % nv; \
print('torch CPU build 校验通过:', torch.__version__)"

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
