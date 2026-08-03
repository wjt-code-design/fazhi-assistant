// 并发冒烟测试（非吞吐压测）：验证「并发下不崩/无死锁/检索读安全」。
//
// 为什么不是压测：单 worker + 60/min 限流 + 远端 LLM 生成 3-8s，吞吐数字会被
// 缓存/限流双重污染（BENCHMARK 方法学已声明）。本脚本验的是正确性：
//   N 个【不同问题】并行发（避免命中答案缓存——缓存 key 含问题文本），断言：
//   1) 全部请求返回（200 或 503 繁忙——都算「未崩」；5xx 服务器错误算失败）
//   2) /healthz 之后仍绿（db+vector+llm_host 全 true）
//   3) 无进程崩溃（请求全部有响应而非超时挂死）
//
// 默认 N=8（并发度低于默认 LLM_MAX_CONCURRENCY=4 时会排队，但都应完成）。
// 可 env: CONCURRENCY=12 提高并发观察排队/繁忙路径；结果落盘 benchmark_results/concurrency_<ts>.json。
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
const N = parseInt(process.env.CONCURRENCY || "8", 10);
// 每个问题带唯一编号 → 缓存 miss，测到真实并行 LLM 路径（与前缀 QS 同理）
const QS = Array.from({ length: N }, (_, i) => `网络购物遇纠纷如何维权？这是并发冒烟第${i + 1}号问题。`);

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
  let content = "";
  if (resp.body) {
    const dec = new TextDecoder();
    for await (const chunk of resp.body) content += dec.decode(chunk, { stream: true });
  }
  return { status: resp.status, ms: Math.round(performance.now() - t0), len: content.length, error: content.includes('"error"') };
}

// 并发发起（Promise.all 全并行）
const t0 = performance.now();
const results = await Promise.all(QS.map(chat));
const elapsed = (performance.now() - t0) / 1000;

// /healthz 之后仍绿
let healthz = null;
try {
  healthz = await (await fetch(BASE + "/healthz")).json();
} catch (e) {
  healthz = { fetch_failed: String(e) };
}
const healthy = healthz.db === true && healthz.vector === true && healthz.llm_host === true;

const ok = results.filter((r) => r.status >= 200 && r.status < 500).length; // 200 或 503 繁忙都算存活
const serverErr = results.filter((r) => r.status >= 500).length;           // 500/502 等 = 服务器异常 = 失败
const timeout = results.filter((r) => r.status === 0).length;
const pass = serverErr === 0 && timeout === 0 && healthy;

const now = new Date();
const pad = (n) => String(n).padStart(2, "0");
const ts = `${now.getFullYear()}${pad(now.getMonth() + 1)}${pad(now.getDate())}-${pad(now.getHours())}${pad(now.getMinutes())}${pad(now.getSeconds())}`;
const result = {
  ts,
  n: N,
  elapsed_s: Math.round(elapsed * 10) / 10,
  status_dist: results.reduce((m, r) => ((m[r.status] = (m[r.status] || 0) + 1), m), {}),
  ok_responses: ok,
  server_errors: serverErr,
  timeouts: timeout,
  healthz_after: healthy ? "ok" : JSON.stringify(healthz),
  pass,
  note: `并发冒烟（非压测）：${N} 个不同问题并行，验并发下不崩/健康检查仍绿；503=并发门控繁忙属预期降级`,
};
const outDir = join(__dirname, "..", "..", "docs", "benchmark_results");
mkdirSync(outDir, { recursive: true });
const outFile = join(outDir, `concurrency_${ts}.json`);
writeFileSync(outFile, JSON.stringify(result, null, 1) + "\n");
console.log(`\n并发 ${N} 请求耗时 ${elapsed.toFixed(1)}s`);
console.log("状态分布:", JSON.stringify(result.status_dist));
console.log(`服务器异常 ${serverErr} | 超时 ${timeout} | 存活响应 ${ok} | /healthz ${healthy ? "绿" : "异常"}`);
console.log(pass ? "并发冒烟 PASS" : "并发冒烟 FAIL");
console.log(`落盘：${outFile}`);
process.exit(pass ? 0 : 1);
