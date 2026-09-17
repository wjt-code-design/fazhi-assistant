// 端到端时延测量（node fetch，真实浏览器口径——python urllib 读 SSE 首帧有 ~2s 假象）。
// 冷缓存：5 个不同问题（真实首问全链路）各 1 次 → 首帧/总时延 p50
// 热缓存：预热写入后同题二次问 → 对比
// 输出：docs/benchmark_results/latency_<ts>.json
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
// 随机 nonce 强制缓存 miss：缓存 key 含 rewritten（归一化问题文本）+ 条文 ids——
// 固定问题串首次运行后答案进进程内缓存，二次运行全命中（2026-08-04 实测 168ms 假象）。
// 每次运行生成随机后缀，保证真冷缓存（测真实首问全链路）。
const NONCE = Math.random().toString(36).slice(2, 8);
const QS = [
  `网购七天无理由退货有法律依据吗？（基准${NONCE}）`,
  `高空抛物致人损害，由谁承担责任？（基准${NONCE}）`,
  `用人单位违法解除劳动合同要赔多少钱？（基准${NONCE}）`,
  `民事权利的诉讼时效是几年？（基准${NONCE}）`,
  `注册商标的有效期是多少年？（基准${NONCE}）`,
];

const login = await fetch(BASE + "/api/auth/login", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ username: env.ADMIN_USERNAME || "admin", password: env.ADMIN_PASSWORD || "" }),
});
const token = (await login.json()).token;

async function chat(q) {
  const t0 = performance.now();
  const resp = await fetch(BASE + "/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: "Bearer " + token },
    body: JSON.stringify({ conversation_id: null, question: q, content: q }),
  });
  const head = performance.now() - t0;
  const reader = resp.body.getReader();
  const dec = new TextDecoder();
  let first = null;
  let buf = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    if (first === null && buf.includes("data: ")) {
      first = performance.now() - t0;
      break;
    }
  }
  return { status: resp.status, first, total: performance.now() - t0 };
}

function median(xs) {
  if (!xs.length) return 0;
  const s = [...xs].sort((a, b) => a - b);
  return s[Math.floor(s.length / 2)];
}

// 冷缓存：5 个不同问题各 1 次（真实首问）
const cold = [];
for (const q of QS) {
  const r = await chat(q);
  cold.push({ q: q.slice(0, 20), ...r, first_ms: Math.round(r.first), total_ms: Math.round(r.total) });
  console.log(`冷 ${q.slice(0, 20).padEnd(22)} status=${r.status} first=${Math.round(r.first)}ms total=${Math.round(r.total)}ms`);
}
// 429 防御：若请求被限流拒绝（如脚本紧跟限流冒烟跑），first 为 null → 显式 FAIL 而非记 0ms 假象
const rejected = cold.filter((r) => r.status === 429 || r.first === null);
if (rejected.length > 0) {
  console.log(`\n⚠ ${rejected.length} 个请求被限流/无首帧（status=429 或 first=null）——时延数字无效，请等待 60s 限流窗口滑出后重跑`);
  process.exit(1);
}
const firsts = cold.map((r) => r.first);
const totals = cold.map((r) => r.total);
console.log(`→ 首帧 p50 = ${Math.round(median(firsts))}ms  总时延 p50 = ${Math.round(median(totals))}ms`);

// 热缓存：预热写入后同题二次问
console.log("--- 热缓存对比 ---");
await chat(QS[0]); // 预热
const hot = [];
for (let i = 0; i < 2; i++) {
  const r = await chat(QS[0]);
  hot.push({ first_ms: Math.round(r.first), total_ms: Math.round(r.total) });
}
console.log(`→ 热缓存首帧 ≈ ${hot.map((h) => h.first_ms)}ms（命中应为几十 ms 级）`);

// 统一时间戳 %Y%m%d-%H%M%S（与 eval_* 脚本一致，benchmark_trend 按文件名排序）
const now = new Date();
const pad = (n) => String(n).padStart(2, "0");
const ts = `${now.getFullYear()}${pad(now.getMonth() + 1)}${pad(now.getDate())}-${pad(now.getHours())}${pad(now.getMinutes())}${pad(now.getSeconds())}`;
const outDir = join(__dirname, "..", "..", "docs", "benchmark_results");
mkdirSync(outDir, { recursive: true });
const outFile = join(outDir, `latency_${ts}.json`);
writeFileSync(outFile, JSON.stringify({ ts, cold, hot, summary: { first_p50_ms: Math.round(median(firsts)), total_p50_ms: Math.round(median(totals)) } }, null, 1));
console.log(`\n结果落盘：${outFile}`);
