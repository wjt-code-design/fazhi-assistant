// 限流 429 冒烟（node fetch，真实浏览器口径无 urllib 假象）。
// 前置：先预热确保该题命中答案缓存（200ms/次），61 次须在 60s 窗口内完成。
import { readFileSync } from "fs";
const env = {};
for (const line of readFileSync(".env", "utf8").split("\n")) {
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
console.log(`\n61 次耗时 ${elapsed.toFixed(0)}s | 429 出现 ${n429} 次 | 首次 429 在第 ${codes.indexOf(429) + 1 || "-"} 次`);
console.log(n429 >= 1 ? "限流触发 PASS" : "限流未触发 FAIL");
