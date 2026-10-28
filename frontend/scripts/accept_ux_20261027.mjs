// 2026-10-27 UX 验收：错误态/重试、AI 信任行、复制、法条键盘属性、参考条目版本提示。
// 无头 Edge + CDP；浏览器会话统一带 X-Eval-No-Curate: 1（避免验收对话沉淀候选）。
// 用法：node scripts/accept_ux_20261027.mjs（需 8000 + 3000 在跑）
import { spawn } from "node:child_process";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const REPO = join(__dirname, "..", "..");
const OUT = join(REPO, "dispatch-output", "ux-review-20261027");
const mobile = process.env.UX_MOBILE === "1";
const suffix = mobile ? "-mobile" : "";
mkdirSync(OUT, { recursive: true });

const EDGE = "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe";
const PORT = 9224;
const PROFILE = "C:\\Users\\33393\\AppData\\Local\\Temp\\edge-ux-audit";

function readEnv(path) {
  const out = {};
  for (const line of readFileSync(path, "utf8").split("\n")) {
    if (line.includes("=") && !line.trim().startsWith("#")) {
      const i = line.indexOf("=");
      out[line.slice(0, i).trim()] = line.slice(i + 1).trim();
    }
  }
  return out;
}

const env = readEnv(join(REPO, "backend", ".env"));
const username = process.env.UX_AUDIT_USER || env.ADMIN_USERNAME || "admin";
const password = env.ADMIN_PASSWORD || "";
if (!password) {
  console.error("no ADMIN_PASSWORD in backend/.env");
  process.exit(2);
}

const edge = spawn(
  EDGE,
  [
    "--headless=new",
    `--remote-debugging-port=${PORT}`,
    `--user-data-dir=${PROFILE}`,
    "--disable-gpu",
    "--no-first-run",
    "--host-resolver-rules=MAP localhost 127.0.0.1",
    "about:blank",
  ],
  { stdio: "ignore" }
);

let targets;
for (let i = 0; i < 40; i++) {
  try {
    targets = await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json();
    if (targets.length) break;
  } catch {}
  await new Promise((r) => setTimeout(r, 500));
}
const page = targets.find((t) => t.type === "page");
const ws = new WebSocket(page.webSocketDebuggerUrl);
let id = 0;
const pending = new Map();
const exceptions = [];
const send = (method, params = {}) =>
  new Promise((res) => {
    const mid = ++id;
    pending.set(mid, res);
    ws.send(JSON.stringify({ id: mid, method, params }));
  });
ws.onmessage = (ev) => {
  const msg = JSON.parse(ev.data);
  if (msg.id && pending.has(msg.id)) {
    pending.get(msg.id)(msg);
    pending.delete(msg.id);
  } else if (msg.method === "Runtime.exceptionThrown") {
    exceptions.push(
      (msg.params.exceptionDetails?.exception?.description || msg.params.exceptionDetails?.text || "").slice(0, 300)
    );
  }
};
await new Promise((r) => (ws.onopen = r));
await send("Runtime.enable");
await send("Page.enable");
await send("Network.enable");
await send(
  "Emulation.setDeviceMetricsOverride",
  mobile
    ? { width: 390, height: 844, deviceScaleFactor: 2, mobile: true }
    : { width: 1280, height: 900, deviceScaleFactor: 1, mobile: false }
);
const evalJs = async (expression) =>
  (await send("Runtime.evaluate", { expression, returnByValue: true, awaitPromise: true })).result?.result?.value;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const login = await fetch("http://127.0.0.1:8000/api/auth/login", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ username, password }),
});
const token = (await login.json()).token;
if (!token) {
  console.error("admin login failed");
  edge.kill();
  process.exit(2);
}

await send("Page.navigate", { url: "http://localhost:3000/login" });
await sleep(2000);
await evalJs(`localStorage.setItem('alh_token', '${token}'); localStorage.setItem('alh_eval_no_curate','1'); 'ok'`);

const result = { ts: new Date().toISOString(), assertions: {}, screenshots: {} };

// 1) 正常回答：先发一个会引法条的问题（新会话，不污染错误态测试会话）
await send("Page.navigate", { url: "http://localhost:3000/chat" });
await sleep(3500);
const diag = await evalJs(`(() => {
  const form = [...document.querySelectorAll('form')].find((f) => f.querySelector('textarea'));
  if (!form) return 'no-form';
  const ta = form.querySelector('textarea');
  const setter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value').set;
  setter.call(ta, '竞业限制期限最长多久？');
  ta.dispatchEvent(new Event('input', { bubbles: true }));
  form.requestSubmit();
  return 'sent';
})()`);
result.assertions.chatSent = diag === "sent";
for (let i = 0; i < 40; i++) {
  const hasTrust = await evalJs(`document.body.innerText.includes('AI 生成 · 仅供参考')`);
  if (hasTrust) break;
  await sleep(1000);
}
for (let i = 0; i < 40; i++) {
  const done = await evalJs(`!!document.querySelector('button[aria-label="发送"]')`);
  if (done) break;
  await sleep(1000);
}
await sleep(600);
const answerText = await evalJs(`document.body.innerText`);
result.assertions.trustLine = answerText.includes("AI 生成 · 仅供参考");
result.assertions.copyButton = await evalJs(
  `[...document.querySelectorAll('button')].some((b) => (b.innerText || '') === '复制')`
);
result.assertions.lawRefKeyboard = await evalJs(
  `!!document.querySelector('.law-ref[role="button"][tabindex="0"]')`
);
result.assertions.sourceVersionTitle = await evalJs(
  `[...document.querySelectorAll('[title]')].some((e) => /^(状态：|施行：|失效：)/.test(e.getAttribute('title') || ''))`
);
result.assertions.dateControl = await evalJs(
  `!!document.querySelector('input[type="date"][aria-label="法律基准日"]')`
);
result.assertions.exportButton = await evalJs(
  `[...document.querySelectorAll('button')].some((b) => (b.innerText || '') === '导出')`
);
result.assertions.historySearch = await evalJs(
  `!!document.querySelector('input[aria-label="搜索历史会话"]')`
);
result.assertions.renameButton = await evalJs(
  `!!document.querySelector('button[aria-label^="重命名会话"]')`
);
const ansShot = await send("Page.captureScreenshot", { format: "png" });
writeFileSync(join(OUT, `answer-state${suffix}.png`), Buffer.from(ansShot.result.data, "base64"));
result.screenshots.answerState = join(OUT, `answer-state${suffix}.png`);


// 法律基准日：设置日期 → 发第二个短问题 → 用户气泡显示基准日
const dateSet = await evalJs(`(() => {
  const el = document.querySelector('input[type="date"][aria-label="法律基准日"]');
  if (!el) return false;
  const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
  setter.call(el, '2020-01-01');
  el.dispatchEvent(new Event('input', { bubbles: true }));
  el.dispatchEvent(new Event('change', { bubbles: true }));
  return true;
})()`);
result.assertions.dateSet = dateSet === true;
await sleep(400);
const sent2 = await evalJs(`(() => {
  const form = [...document.querySelectorAll('form')].find((f) => f.querySelector('textarea'));
  if (!form) return 'no-form';
  const ta = form.querySelector('textarea');
  const setter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value').set;
  setter.call(ta, '民法典诉讼时效是几年？');
  ta.dispatchEvent(new Event('input', { bubbles: true }));
  form.requestSubmit();
  return 'sent';
})()`);
result.assertions.chatSent2 = sent2 === 'sent';
for (let i = 0; i < 20; i++) {
  const shown = await evalJs(`document.body.innerText.includes('法律基准日：2020-01-01')`);
  if (shown) break;
  await sleep(500);
}
result.assertions.lawAsOfBasis = await evalJs(
  `document.body.innerText.includes('法律基准日：2020-01-01')`
);
for (let i = 0; i < 40; i++) {
  const done = await evalJs(`!!document.querySelector('button[aria-label="发送"]')`);
  if (done) break;
  await sleep(1000);
}
// 3) 错误态：打开预置的“错误态验收-20261027”会话
const clicked = await evalJs(`(() => {
  const el = [...document.querySelectorAll('.chat-item, button')].find((x) =>
    (x.innerText || '').includes('错误态验收-20261027')
  );
  if (!el) return false;
  el.click();
  return true;
})()`);
result.assertions.errorConversationFound = clicked;
for (let i = 0; i < 12; i++) {
  const hasBadge = await evalJs(`document.body.innerText.includes('未能完成本次请求')`);
  if (hasBadge) break;
  await sleep(500);
}
await evalJs(`(() => {
  const el = document.querySelector('.scroll-contain');
  if (el) el.scrollTo(0, 0);
  window.scrollTo(0, 0);
  return true;
})()`);
await sleep(500);
const errText = await evalJs(`document.body.innerText`);
result.assertions.errorBadge = errText.includes("未能完成本次请求");
result.assertions.serviceHint = errText.includes("服务暂时中断");
result.assertions.retryButton = await evalJs(
  `[...document.querySelectorAll('button')].some((b) => (b.innerText || '').includes('重试本次提问'))`
);
result.assertions.errorBadgeInBubble = await evalJs(
  `[...document.querySelectorAll('[data-msg-index]')].some((el) => (el.innerText || '').includes('未能完成本次请求'))`
);
const errShot = await send("Page.captureScreenshot", { format: "png" });
writeFileSync(join(OUT, `error-state${suffix}.png`), Buffer.from(errShot.result.data, "base64"));
result.screenshots.errorState = join(OUT, `error-state${suffix}.png`);

result.assertions.exceptions = exceptions.length;
result.pass = Object.entries(result.assertions)
  .filter(([k]) => k !== "errorConversationFound" && k !== "exceptions")
  .every(([, v]) => v === true) && exceptions.length === 0;
writeFileSync(join(OUT, `audit${suffix}.json`), JSON.stringify(result, null, 1) + "\n");
console.log(JSON.stringify(result, null, 1));
edge.kill();
process.exit(result.pass ? 0 : 1);
