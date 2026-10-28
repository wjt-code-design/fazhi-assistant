#!/usr/bin/env bash
# 法智 · 云服务器首次初始化（Ubuntu 22.04，Debian 系）
# 用法：sudo bash server-init.sh
#
# 事实依据（2026-10-27 核实）：
#   - 法智容器栈：backend(uvicorn 8000) + frontend(Next standalone 3000) + caddy(:80)，
#     Caddy 宿主端口由根 .env 的 CADDY_HTTP_PORT 决定（默认 8088，云上设 8080）。
#   - backend 实测常驻 629.8 MiB ⇒ 2核4G 起步够用；mem_limit 默认 2g。
#   - 后端镜像 3.95 GB ⇒ 40GB 系统盘的机型不要在服务器 build（构建缓存会撑爆盘）。
#   - 80/443 需要 ICP 备案；本方案走 8080 非标准端口，免备案。
set -euo pipefail

[ "$(id -u)" -eq 0 ] || { echo "请用 root 或 sudo 执行"; exit 1; }

echo "===== 1/5 环境检查 ====="
. /etc/os-release
echo "系统: $PRETTY_NAME  内核: $(uname -r)"
free -m | head -2
df -h / | tail -1

echo
echo "===== 2/5 Docker ====="
if ! command -v docker >/dev/null 2>&1; then
  echo "未检测到 docker，开始安装（阿里云镜像源）..."
  apt-get update -y
  apt-get install -y ca-certificates curl gnupg
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://mirrors.aliyun.com/docker-ce/linux/ubuntu/gpg \
    | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  chmod a+r /etc/apt/keyrings/docker.gpg
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://mirrors.aliyun.com/docker-ce/linux/ubuntu $(. /etc/os-release && echo "${VERSION_CODENAME}") stable" \
    > /etc/apt/sources.list.d/docker.list
  apt-get update -y
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
else
  echo "docker 已安装：$(docker --version)"
fi
systemctl enable --now docker

# 无论是否预装，都确保 compose v2 插件存在——本脚本全程用 `docker compose`（v2 语法），
# 预装镜像不一定带插件。阿里云预装 Docker 若缺插件，上面会跳过安装，这里补齐。
if ! docker compose version >/dev/null 2>&1; then
  echo "未检测到 docker compose 插件，开始补装..."
  apt-get update -y
  apt-get install -y docker-compose-plugin 2>/dev/null || true
  if ! docker compose version >/dev/null 2>&1; then
    echo "apt 装不上，改用二进制兜底..."
    mkdir -p /usr/local/lib/docker/cli-plugins
    curl -fsSL --connect-timeout 20 --max-time 300 \
      https://mirrors.aliyun.com/docker/cli-plugins/v2.29.7/docker-compose-linux-x86_64 \
      -o /usr/local/lib/docker/cli-plugins/docker-compose \
      || curl -fsSL --connect-timeout 20 --max-time 300 \
      https://github.com/docker/compose/releases/download/v2.29.7/docker-compose-linux-x86_64 \
      -o /usr/local/lib/docker/cli-plugins/docker-compose
    chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
  fi
fi
docker compose version

echo
echo "===== 3/5 镜像加速（可选）====="
# 阿里云控制台 → 容器镜像服务 → 镜像工具 → 镜像加速器，把专属 ID 传进来：
#   sudo DOCKER_MIRROR_ID=<你的ID> bash server-init.sh
if [ -n "${DOCKER_MIRROR_ID:-}" ]; then
  mkdir -p /etc/docker
  cat > /etc/docker/daemon.json <<JSON
{
  "registry-mirrors": ["https://${DOCKER_MIRROR_ID}.mirror.aliyuncs.com"]
}
JSON
  systemctl restart docker
  echo "已写入 /etc/docker/daemon.json"
else
  echo "未提供 DOCKER_MIRROR_ID，跳过镜像加速（不影响拉本地上传的镜像 tar）"
fi

echo
echo "===== 4/5 swap（2核4G 必备，防 OOM）====="
if [ ! -f /swapfile ]; then
  fallocate -l 4G /swapfile
  chmod 600 /swapfile
  mkswap /swapfile
  swapon /swapfile
  grep -q '^/swapfile ' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
  echo "已创建 4G swap"
else
  echo "swapfile 已存在"
fi
sysctl -w vm.swappiness=10 >/dev/null
grep -q '^vm.swappiness' /etc/sysctl.conf || echo 'vm.swappiness=10' >> /etc/sysctl.conf
free -m | head -3

echo
echo "===== 5/5 防火墙与目录 ====="
ufw allow 22/tcp   >/dev/null 2>&1 || true
ufw allow 8080/tcp >/dev/null 2>&1 || true
ufw --force enable >/dev/null 2>&1 || true
ufw status || true
mkdir -p /opt/fazhi/caddy_data /opt/fazhi/caddy_config
echo "已准备 /opt/fazhi（caddy_data / caddy_config 为 compose 挂载点，勿删）"

cat <<'EOF'

===== 完成 =====
下一步：
  1. 本地打包上传（见 deploy/package-and-upload.sh）
  2. 服务器上执行： cd /opt/fazhi && bash deploy/deploy.sh
  3. 访问：http://<公网IP>:8080
EOF
