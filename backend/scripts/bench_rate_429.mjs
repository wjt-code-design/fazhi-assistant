// 限流 429 冒烟（node fetch，真实浏览器口径无 urllib 假象）。
// 前置：先预热确保该题命中答案缓存（200ms/次），61 次须在 60s 窗口内完成。
// 结果落盘 docs/benchmark_results/rate_limit_<ts>.json（PASS 的物证，供 BENCHMARK.md 引用）。
import { readFileSync, writeFileSync, mkdirSync } from "fs";
import { join, dirname } from "path";
import { fileURLToPath } from "url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const env = {};
for (const line of readFileSync(join(__dirname, "..", ".env"), "utf8").split("\n")) {
  if (line.includes("=")) {
    const i = line.indexOf("=");
    env[line.slice(0, i).trim()] = line.slice(i + 1).trim();
  }
}
const BASE = "http://localhost:8000";
const login = await fetch(BASE + "/api/auth/login", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ username: env.ADMIN_USERNAME || "admin", password: env.ADMIN_PASSWORD || "" }),
});
const token = (await login.json()).token;
const q = "网购七天无理由退货有法律依据吗？";
const body = JSON.stringify({ conversation_id: null, question: q, content: q });

async function one() {
  const resp = await fetch(BASE + "/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: "Bearer " + token },
    body,
  });
  // 读完整响应体（触发限流计数与缓存返回）
  await resp.arrayBuffer();
  return resp.status;
}

// 预热：确保缓存写入
console.log("预热 status =", await one());
const t0 = performance.now();
const codes = [];
for (let i = 0; i < 61; i++) {
  codes.push(await one());
  if (i % 10 === 0) console.log("#" + i, codes[i]);
}
const elapsed = (performance.now() - t0) / 1000;
const n429 = codes.filter((c) => c === 429).length;
const result = {
  ts: new Date().toISOString(),
  requests: codes.length,
  elapsed_s: Math.round(elapsed * 10) / 10,
  n_429: n429,
  first_429_at: codes.indexOf(429) + 1 || null,
  pass: n429 >= 1 && elapsed < 60,
  note: "node 口径（无 urllib 假象）；同题缓存命中零配额；限流 slowapi 按 IP 60/min",
};
const outDir = join(__dirname, "..", "..", "docs", "benchmark_results");
mkdirSync(outDir, { recursive: true });
const outFile = join(outDir, `rate_limit_${result.ts.replace(/[:.]/g, "-")}.json`);
writeFileSync(outFile, JSON.stringify(result, null, 1) + "\n");
console.log(`\n61 次耗时 ${elapsed.toFixed(0)}s | 429 出现 ${n429} 次 | 首次 429 在第 ${codes.indexOf(429) + 1 || "-"} 次`);
console.log(n429 >= 1 ? "限流触发 PASS" : "限流未触发 FAIL");
console.log(`落盘：${outFile}`);
