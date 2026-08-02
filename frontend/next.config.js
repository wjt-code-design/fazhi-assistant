/** @type {import('next').NextConfig} */
const nextConfig = {
  // standalone 输出：Docker 镜像只需 ~200MB（只带运行所需文件，见 frontend/Dockerfile）
  output: "standalone",
};
module.exports = nextConfig;
