#!/usr/bin/env bash
# 法智 · 服务器侧启动与验证（Ubuntu / Debian 系）
# 用法：cd /opt/fazhi && bash deploy/deploy.sh
#
# 设计原则：**宁可起不来，也不带病上线**
#   - 关键环境变量缺失 → 立刻退出，不进容器；
#   - /healthz 绿 ≠ 上线成功（健康检查不碰嵌入）⇒ 必须核对启动日志里的 embedding 配置，
#     否则会"健康上线但问答零召回"。
set -euo pipefail

cd /opt/fazhi
[ -f .env ] || { echo "❌ 缺少 /opt/fazhi/.env（参考 .env.example 填写）"; exit 1; }

echo "===== 1/6 环境变量自检 ====="
missing=()
for k in LLM_API_KEY LLM_BASE_URL EMBEDDING_PROVIDER EMBEDDING_API_KEY \
         EMBEDDING_BASE_URL EMBEDDING_MODEL JWT_SECRET ADMIN_PASSWORD; do
  grep -qE "^${k}=.+" .env || missing+=("$k")
done
if [ "${#missing[@]}" -gt 0 ]; then
  echo "❌ .env 缺少必填项：${missing[*]}"
  echo "   （EMBEDDING_* 为空会让容器回落 local 嵌入 ⇒ 加载本地 BGE 且集合名切 _LOCAL ⇒ 零召回）"
  exit 1
fi
echo "✅ 必填项齐全"
grep -E '^(EMBEDDING_PROVIDER|EMBEDDING_MODEL|EMBEDDING_DIMENSIONS|RERANK_ENABLED)=' .env || true

echo
echo "===== 2/6 端口与资源 ====="
if ! grep -q '^CADDY_HTTP_PORT=' .env; then
  echo 'CADDY_HTTP_PORT=8080' >> .env
  echo "已写入 CADDY_HTTP_PORT=8080"
fi
PORT="$(grep -E '^CADDY_HTTP_PORT=' .env | tail -1 | cut -d= -f2 | tr -d '\r')"
PORT="${PORT:-8080}"
echo "Caddy 宿主端口: $PORT"
# 2核4G 的机器上 backend 默认 mem_limit=2g 已够；4核8G 可在 .env 设 BACKEND_MEM_LIMIT=3g
grep -E '^BACKEND_MEM_LIMIT=' .env || echo "BACKEND_MEM_LIMIT 未设 → 使用默认 2g"

echo
echo "===== 3/6 compose 配置干跑 ====="
docker compose config >/dev/null && echo "✅ compose 配置合法"

echo
echo "===== 4/6 启动 ====="
docker compose up -d
docker compose ps

echo
echo "===== 5/6 等待健康检查（最多 5 分钟）====="
ok=0
for i in $(seq 1 60); do
  # 用 /api/health：它走 Caddy 的 /api/* → backend 规则，不依赖 /healthz 转发是否已配
  if curl -sf "http://127.0.0.1:${PORT}/api/health" >/tmp/hz.json 2>/dev/null; then
    echo "✅ healthz: $(cat /tmp/hz.json)"
    ok=1; break
  fi
  sleep 5
done
if [ "$ok" -ne 1 ]; then
  echo "❌ 5 分钟内未就绪，最近日志："
  docker compose logs --tail=60 backend
  exit 1
fi

echo
echo "===== 6/6 关键验证（healthz 绿不算上线成功）====="
echo "--- (a) 嵌入配置必须是 aliyun + 云端集合，不能是 local ---"
# ⚠️ 不用 grep 启动日志：容器的 log_level 不是 INFO，info 级日志不会输出（2026-10-28 实测）。
# 直接问容器里的实际生效值更可靠。
COLL="$(docker compose exec -T backend python -c 'import rag_chain; print(rag_chain.COLLECTION_NAME)' 2>/dev/null | tr -d '\r' | tail -1)"
echo "COLLECTION_NAME = ${COLL:-<读取失败>}"
case "$COLL" in
  *_LOCAL|"")
    echo "❌ 集合名为 _LOCAL 或读取失败 —— 嵌入配置回落到 local，会加载本地 BGE 且向量库对不上 ⇒ 零召回"
    echo "   查：docker compose logs backend | grep -i embedding；以及 .env 里 EMBEDDING_* 是否齐全"
    exit 1
    ;;
  *)
    echo "✅ 嵌入集合为云端集合（不是 _LOCAL）"
    ;;
esac

echo "--- (b) 内存实测 ---"
docker stats --no-stream --format "{{.Name}}\t{{.MemUsage}}"

cat <<EOF

===== 部署完成 =====
访问地址：http://<公网IP>:${PORT}
健康检查：http://<公网IP>:${PORT}/healthz

⚠️ 还要做最后一件事：**用真实问题测一次问答**。
   /healthz 只检查 DB 与向量库就绪，不检查召回质量；
   若答不出条文或引用错条 => 回到 (a) 看嵌入配置。

回滚：cd /opt/fazhi && docker compose down
EOF
