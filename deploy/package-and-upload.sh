#!/usr/bin/env bash
# 法智 · 本地侧打包与上传（Git Bash / WSL / Linux 均可跑）
# 用法：
#   bash deploy/package-and-upload.sh <user@host> [tar|acr]
#
#   tar  = docker save 成 tar 后 scp（默认；不依赖 ACR）
#   acr  = 推到阿里云容器镜像服务 ACR，服务器侧 pull（适合重复部署）
#
# 关键事实（2026-10-27 实测）：
#   - 后端镜像 3.95 GB；前端 223 MB。tar 上传受家宽上行限制，约 3.9GB 可能要 10~30 分钟。
#   - 服务器若只有 40GB 系统盘（学生算力包固定值），**绝不能在那里 build**。
#   - 必须上传的数据目录：backend/chroma_db(492MB，向量库) / backend/data(生产库+配额)
#     / backend/media / backend/backups / backend/knowledge_base —— 少一个就是"起来了但答不了题"。
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
HOST="${1:?用法: bash package-and-upload.sh <user@host> [tar|acr]}"
MODE="${2:-tar}"
STAGE="${STAGE_DIR:-$HOME/fazhi-deploy}"
mkdir -p "$STAGE"
cd "$REPO"

echo "===== 1/5 构建镜像（层缓存命中，通常几分钟）====="
docker compose build backend frontend
docker images --format "{{.Repository}}:{{.Tag}} {{.Size}}" | grep -E 'ai-legal-helper-(backend|frontend)' | head -4

if [ "$MODE" = "acr" ]; then
  echo
  echo "===== [ACR 模式] 推送镜像 ====="
  REG="${ACR_REGISTRY:-}"   # 例：registry.cn-beijing.aliyuncs.com/<命名空间>
  NS="${ACR_NAMESPACE:-}"
  [ -n "$REG" ] || { echo "❌ 请先设置 ACR_REGISTRY（ACR 登录后 docker info 里可见）"; exit 1; }
  NS="${NS:-fazhi}"
  docker tag ai-legal-helper-backend:latest "$REG/$NS/backend:latest"
  docker tag ai-legal-helper-frontend:latest "$REG/$NS/frontend:latest"
  docker push "$REG/$NS/backend:latest"
  docker push "$REG/$NS/frontend:latest"
  echo "已推送。服务器侧改用 docker-compose 的 image: 字段或自行 pull + tag。"
  echo "  docker pull $REG/$NS/backend:latest && docker tag $REG/$NS/backend:latest ai-legal-helper-backend:latest"
  echo "  docker pull $REG/$NS/frontend:latest && docker tag $REG/$NS/frontend:latest ai-legal-helper-frontend:latest"
else
  echo
  echo "===== [TAR 模式] 导出镜像 ====="
  echo "导出后端镜像（3.95GB，耗时较长，请耐心）..."
  docker save ai-legal-helper-backend:latest -o "$STAGE/backend.tar"
  docker save ai-legal-helper-frontend:latest -o "$STAGE/frontend.tar"
  ls -lh "$STAGE"/*.tar
fi

echo
echo "===== 2/5 打包代码与数据 ====="
# 只打包部署必需的部分；排除 venv / node_modules / .git / 临时产物
PKG="$STAGE/fazhi-src.tar.gz"
tar czf "$PKG" \
  --exclude='./.git' --exclude='./backend/venv' --exclude='./backend/venv-new' \
  --exclude='./frontend/node_modules' --exclude='./frontend/.next' \
  --exclude='./_pt_*' --exclude='./_pytest_*' --exclude='./.worktrees' \
  --exclude='./backend/__pycache__' --exclude='./**/__pycache__' \
  --exclude='./dispatch-output' --exclude='./reports' --exclude='./diag' \
  --exclude='./outputs' --exclude='./evals' --exclude='./.workbuddy' \
  .env.example docker-compose.yml Caddyfile \
  backend frontend deploy 2>/dev/null || {
    echo "⚠️ 部分可选文件缺失，按实际存在的继续"
    tar czf "$PKG" .env.example docker-compose.yml Caddyfile backend frontend deploy
  }
# ⚠️ 刻意**不**打包 .env：它含明文密钥，不该躺在本地 tar 里。单独 scp（见末尾提示）。
ls -lh "$PKG"

echo
echo "===== 3/5 上传到服务器 ====="
ssh "$HOST" 'mkdir -p /opt/fazhi'
for f in "$STAGE/fazhi-src.tar.gz" "$STAGE"/*.tar; do
  [ -f "$f" ] || continue
  echo "--> 传 $(basename "$f") ($(du -h "$f" | cut -f1))"
  scp "$f" "$HOST:/opt/fazhi/"
done

echo
echo "===== 4/5 服务器侧解包 ====="
ssh "$HOST" 'cd /opt/fazhi && tar xzf fazhi-src.tar.gz && rm -f fazhi-src.tar.gz && ls -la /opt/fazhi | head -20'

if [ "$MODE" != "acr" ]; then
  echo "===== 5/5 服务器侧导入镜像 ====="
  for t in backend frontend; do
    [ -f "$STAGE/$t.tar" ] || continue
    echo "--> docker load $t.tar"
    ssh "$HOST" "docker load -i /opt/fazhi/$t.tar && rm -f /opt/fazhi/$t.tar"
  done
fi

cat <<EOF

===== 上传完成 =====
服务器上执行：
  cd /opt/fazhi
  # 1) 先放好密钥（.env 含全部凭据，别走 git）
  #    scp <你的根 .env> root@<host>:/opt/fazhi/.env && ssh root@<host> 'chmod 600 /opt/fazhi/.env'
  # 2) 起服务
  bash deploy/deploy.sh

若服务器还没初始化过，先跑：sudo bash deploy/server-init.sh
EOF
