#!/usr/bin/env bash
# 启动 003 隔离预检容器：密钥取自 git 忽略的根 .env（与 002 容器同源），不回显任何值。
# 隔离覆盖：隔离 SQLite/Chroma 卷 + 仅绑定 127.0.0.1。AGENT 开关由采集模式决定
# （existing_rag=false/0，agent=true/100），用后按需 sed 翻转。
set -euo pipefail

CID=legal-agent-preflight-004
ENVFILE="$(mktemp)"
trap 'rm -f "$ENVFILE"' EXIT

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
grep -v -E '^\s*#|^\s*$' "$REPO_ROOT/.env" | sed 's/^SELF_REGISTER=.*/SELF_REGISTER=false/' > "$ENVFILE"
cat >> "$ENVFILE" <<'EOF'
DATABASE_URL=sqlite:////data/app.db
QUOTA_DB=/data/quota_used.sqlite
AGENT_ENABLED=false
AGENT_TRAFFIC_PERCENT=0
FEATURE_SELF_REGISTER=true
ANONYMIZED_TELEMETRY=False
EOF

docker volume create legal_agent_eval004_data >/dev/null
docker volume create legal_agent_eval004_chroma >/dev/null

docker run -d --name "$CID" \
  --env-file "$ENVFILE" \
  -p 127.0.0.1:18003:8000 \
  -v legal_agent_eval004_data:/data \
  -v legal_agent_eval004_chroma:/app/chroma_db \
  ai-legal-helper-backend:009

echo "container $CID started"
