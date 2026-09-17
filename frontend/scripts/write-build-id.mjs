// postbuild（T1.1 SW 构建号版本化）：把 Next 构建产物 .next/BUILD_ID 复制到 public/build-id.txt。
// next start 在运行时从磁盘读取 public/，因此该文件可在每次构建后刷新、被 SW fetch 到；
// BUILD_ID 端点本身不被 Next 对外服务（2026-09-15 实测 /_next/static/BUILD_ID → 404），故用此桥接。
import { readFileSync, writeFileSync } from "node:fs";

const bid = readFileSync(".next/BUILD_ID", "utf8").trim();
writeFileSync("public/build-id.txt", bid);
console.log(`[write-build-id] public/build-id.txt = ${bid}`);
