/** @type {import('next').NextConfig} */
const nextConfig = {
  // standalone 输出：Docker 镜像只需 ~200MB（只带运行所需文件，见 frontend/Dockerfile）
  output: "standalone",
  // 同源反代（2026-08-08 手机端上线）：前端服务器把 /api/* 代理到后端 8000。
  // 生产（next start / standalone server.js）下前端相对路径 /api 经此到后端，无需 Caddy/CORS。
  async rewrites() {
    const backend = process.env.BACKEND_URL || "http://localhost:8000";
    return [{ source: "/api/:path*", destination: `${backend}/api/:path*` }];
  },
};
module.exports = nextConfig;
