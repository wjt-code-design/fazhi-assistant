// postbuild（T1.1 / R10）：把 Next 构建号写进两处产物。
//   1) public/build-id.txt：运行时桥接文件（历史保留；SW 已不再依赖它）。
//   2) public/sw.js：由 scripts/sw.template.js 把占位符 __BUILD_ID__ 替换成真实构建号后生成
//      —— 这样 service worker 模块一被求值 `CACHE` 就是正确名字，不再依赖 install 事件
//         或网络；Worker 被回收重启后也不会退回 dev 缓存名（R10 的病根）。
import { readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

const PLACEHOLDER = "__BUILD_ID__";
// 模板是**源码资产**，固定在脚本同目录；产物 public/sw.js 按 cwd 解析（与 build-id.txt 同款）。
const TEMPLATE = fileURLToPath(new URL("./sw.template.js", import.meta.url));

const bid = readFileSync(".next/BUILD_ID", "utf8").trim();
writeFileSync("public/build-id.txt", bid);
console.log(`[write-build-id] public/build-id.txt = ${bid}`);

const template = readFileSync(TEMPLATE, "utf8");
if (!template.includes(PLACEHOLDER)) {
  throw new Error(`[write-build-id] 模板缺占位符 ${PLACEHOLDER}：${TEMPLATE}`);
}
writeFileSync("public/sw.js", template.replaceAll(PLACEHOLDER, bid));
console.log(`[write-build-id] public/sw.js 已嵌入构建号 ${bid}`);
