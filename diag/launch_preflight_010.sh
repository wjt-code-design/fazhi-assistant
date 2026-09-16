#!/usr/bin/env bash
# 启动 010 隔离采集容器（引用精度修复候选，2026-09-07）。
# 铁律（CONTRIBUTING 2026-09-07）：绝对路径、辅助容器播种、容器内 count 预验证。
# 密钥取自 git 忽略的根 .env，不回显任何值。隔离卷 + 仅绑定 127.0.0.1。
set -euo pipefail

CID=legal-agent-preflight-010
DATA_VOL=legal_agent_eval010_data
CHROMA_VOL=legal_agent_eval010_chroma
ENVFILE="$(mktemp)"
trap 'rm -f "$ENVFILE"' EXIT

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# 1) 卷就绪（保留已播种数据，容器重建不丢）
docker volume create "$DATA_VOL" >/dev/null

# 2) 索引播种：辅助容器直写卷（MSYS 路径转换坑 → 用辅助容器 + 只读挂载）
#    磁盘 chroma_db 即 010 冻结索引（index-manifest sha 已按它计算，勿换 009 卷）。
if ! docker run --rm -v "$CHROMA_VOL":/target -v "$REPO_ROOT/backend/chroma_db":/src:ro \
  python:3.11-slim sh -c 'test -f /target/chroma.sqlite3 || cp -r /src/. /target/'; then
  echo "FAIL: 播种失败（卷未就绪）" >&2
  exit 1
fi

# 3) 播种后容器内 count 预验证（防空索引跑完整轮才发现）
if ! docker run --rm -v "$CHROMA_VOL":/app/chroma_db ai-legal-helper-backend:010 python -c \
  "import chromadb; c=chromadb.PersistentClient(path='/app/chroma_db');
   l=c.get_collection('legal_provisions_cos').count(); q=c.get_collection('qa_pairs').count();
   assert l==10266 and q==279, ('index not frozen', l, q); print('index count ok', l, q)"; then
  echo "FAIL: 索引 count 预验证未通过" >&2
  exit 1
fi

# 4) Env：复用根 .env + 隔离 DB/配额 + 采集模式开关（默认 AGENT off；agent 采集用 sed 翻）
grep -v -E '^\s*#|^\s*$' "$REPO_ROOT/.env" | sed 's/^SELF_REGISTER=.*/SELF_REGISTER=false/' > "$ENVFILE"
cat >> "$ENVFILE" <<'EOF'
DATABASE_URL=sqlite:////data/app.db
QUOTA_DB=/data/quota_used.sqlite
AGENT_ENABLED=false
AGENT_TRAFFIC_PERCENT=0
FEATURE_SELF_REGISTER=true
ANONYMIZED_TELEMETRY=False
EOF

# 5) 容器启动（010 新代码）
docker rm -f "$CID" >/dev/null 2>&1 || true
docker run -d --name "$CID" \
  --env-file "$ENVFILE" \
  -p 127.0.0.1:18010:8000 \
  -v "$DATA_VOL":/data \
  -v "$CHROMA_VOL":/app/chroma_db \
  ai-legal-helper-backend:010

echo "container $CID started on 127.0.0.1:18010 (image :010)"