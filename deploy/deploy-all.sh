#!/usr/bin/env bash
# 法智 · 一键部署到云服务器（本地执行）
# 用法：bash deploy/deploy-all.sh root@<公网IP>
#
# 前置条件（控制台已完成）：
#   1) 实例已绑定密钥对 fazhi-deploy 并重启生效
#   2) 安全组已放行 22 / 8080
#   3) 本地已备好：/d/_fazhi-deploy/{backend.tar,frontend.tar,fazhi-src.tar.gz}
#      （用 STAGE_DIR 环境变量可覆盖）
set -euo pipefail

HOST="${1:?用法: bash deploy/deploy-all.sh root@<公网IP>}"
KEY="${SSH_KEY:-$HOME/.ssh/fazhi_deploy}"
STAGE="${STAGE_DIR:-/d/_fazhi-deploy}"
REPO="$(cd "$(dirname "$0")/.." && pwd)"
SSH_OPTS=(-i "$KEY" -o StrictHostKeyChecking=no -o ConnectTimeout=20 -o ServerAliveInterval=30)

hr() { printf '\n\033[1m===== %s =====\033[0m\n' "$1"; }

hr "0/7 前置检查"
[ -f "$KEY" ] || { echo "❌ 找不到私钥 $KEY（可用 SSH_KEY=... 指定）"; exit 1; }
for f in backend.tar frontend.tar fazhi-src.tar.gz; do
  [ -f "$STAGE/$f" ] || { echo "❌ 缺少 $STAGE/$f"; exit 1; }
done
ls -lh "$STAGE" | awk '{print "   ", $5, $9}'
echo "目标: $HOST"

hr "1/7 连通性与系统信息"
ssh "${SSH_OPTS[@]}" "$HOST" 'echo SSH_OK; hostname; . /etc/os-release && echo "系统: $PRETTY_NAME"; echo "CPU: $(nproc) 核"; free -m | head -2; df -h / | tail -1'

hr "2/7 建立目录并上传安装脚本"
ssh "${SSH_OPTS[@]}" "$HOST" 'mkdir -p /opt/fazhi'
scp "${SSH_OPTS[@]}" "$REPO/deploy/server-init.sh" "$HOST:/opt/fazhi/"

hr "3/7 上传镜像与数据（1.39GB，100Mbps 约 3-6 分钟）"
time scp "${SSH_OPTS[@]}" "$STAGE/backend.tar" "$STAGE/frontend.tar" "$STAGE/fazhi-src.tar.gz" "$HOST:/opt/fazhi/"

hr "4/7 服务器初始化（Docker / swap / 防火墙）"
ssh "${SSH_OPTS[@]}" "$HOST" 'cd /opt/fazhi && bash server-init.sh'

hr "5/7 上传 .env（含明文密钥，落地即 chmod 600，不进 git/不进 tar）"
scp "${SSH_OPTS[@]}" "$REPO/.env" "$HOST:/opt/fazhi/.env"
ssh "${SSH_OPTS[@]}" "$HOST" 'chmod 600 /opt/fazhi/.env && ls -l /opt/fazhi/.env'

hr "6/7 解包 + 导入镜像（不在服务器 build，保护 40G 系统盘）"
ssh "${SSH_OPTS[@]}" "$HOST" 'cd /opt/fazhi && tar xzf fazhi-src.tar.gz && docker load -i backend.tar && docker load -i frontend.tar && rm -f backend.tar frontend.tar fazhi-src.tar.gz && ls -la /opt/fazhi && echo "--- 镜像 ---" && docker images | head -5'

hr "7/7 启动并验证"
ssh "${SSH_OPTS[@]}" "$HOST" 'cd /opt/fazhi && bash deploy/deploy.sh'

cat <<'EOF'

===== 全部完成 =====
浏览器打开： http://<公网IP>:8080
⚠️ 最后必做：用 admin 登录后发一条真实法律问题，
   确认能召回条文并给出引用（healthz 绿不代表召回正常）。
EOF
