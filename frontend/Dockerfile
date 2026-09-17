# ===== 前端镜像：multi-stage + Next standalone（~200MB） =====
# 诚实标注：镜像体积以构建输出为准；本镜像只带运行所需，不含 node_modules 源码。

# ---------- 构建阶段 ----------
FROM node:20-alpine AS builder
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1

# 先装依赖（利用层缓存）
COPY package.json package-lock.json* ./
RUN npm ci

COPY . .
RUN npm run build

# ---------- 运行阶段 ----------
FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

# 非 root 运行
RUN addgroup --system --gid 1001 nodejs && adduser --system --uid 1001 nextjs

COPY --from=builder /app/public ./public
# standalone 输出：server.js + 依赖
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
# 静态资源
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs
EXPOSE 3000
ENV PORT=3000
ENV HOSTNAME=0.0.0.0
CMD ["node", "server.js"]
