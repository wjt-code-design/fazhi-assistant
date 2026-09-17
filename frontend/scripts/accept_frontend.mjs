// 前端多段验收（CDP 无头 Edge，2026-08-07）：
// 1) /chat 认证加载无客户端异常
// 2) 实际发一条消息 → 回答渲染（含 .law-ref 语义标注 / 无"建议核对" / 无 $）
// 用法：node scripts/accept_frontend.mjs
import { spawn } from "node:child_process";

const EDGE = "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe";
const PORT = 9223;
const PROFILE = "C:\\Users\\33393\\AppData\\Local\\Temp\\edge-accept";

async function main() {
  const edge = spawn(EDGE, [
    "--headless=new", `--remote-debugging-port=${PORT}`, `--user-data-dir=${PROFILE}`,
    "--disable-gpu", "--no-first-run", "--host-resolver-rules=MAP localhost 127.0.0.1", "about:blank",
  ], { stdio: "ignore" });

  let targets;
  for (let i = 0; i < 40; i++) {
    try { targets = await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json(); if (targets.length) break; } catch {}
    await new Promise((r) => setTimeout(r, 500));
  }
  const page = targets.find((t) => t.type === "page");
  const ws = new WebSocket(page.webSocketDebuggerUrl);
  let id = 0; const pending = new Map(); const exceptions = [];
  const send = (m, p = {}) => new Promise((res) => { const mid = ++id; pending.set(mid, res); ws.send(JSON.stringify({ id: mid, method: m, params: p })); });
  ws.onmessage = (ev) => {
    const msg = JSON.parse(ev.data);
    if (msg.id && pending.has(msg.id)) { pending.get(msg.id)(msg); pending.delete(msg.id); }
    else if (msg.method === "Runtime.exceptionThrown") {
      exceptions.push((msg.params.exceptionDetails?.exception?.description || msg.params.exceptionDetails?.text || "").slice(0, 300));
    } else if (msg.method === "Runtime.consoleAPICalled" && msg.params.type === "error") {
      exceptions.push((msg.params.args || []).map((a) => a.value ?? a.description).join(" ").slice(0, 300));
    }
  };
  await new Promise((r) => (ws.onopen = r));
  await send("Runtime.enable"); await send("Page.enable");
  const evalJs = async (expression) => (await send("Runtime.evaluate", { expression, returnByValue: true, awaitPromise: true })).result?.result?.value;

  // 注入 token
  await send("Page.navigate", { url: "http://localhost:3000/login" });
  await new Promise((r) => setTimeout(r, 2500));
  const tok = (await (await fetch("http://127.0.0.1:8000/api/auth/login", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ username: "vtest", password: "test1234" }) })).json()).token;
  await evalJs(`localStorage.setItem('alh_token', '${tok}'); 'ok'`);

  // 1) /chat 加载
  exceptions.length = 0;
  await send("Page.navigate", { url: "http://localhost:3000/chat" });
  await new Promise((r) => setTimeout(r, 6000));
  const title = await evalJs(`document.body.innerText.slice(0, 60)`);
  console.log("1) /chat 加载:", JSON.stringify(title), "| 异常:", exceptions.length);
  if (exceptions.length) { console.log("   FAIL 异常:", exceptions); edge.kill(); process.exit(1); }

  // 2) 发消息：精确主输入 textarea（表单内），原生 setter + input 事件，再 requestSubmit
  const diag = await evalJs(`(() => {
    const forms = Array.from(document.querySelectorAll('form'));
    const form = forms.find(f => f.querySelector('textarea')) || null;
    if (!form) return 'no-form';
    const ta = form.querySelector('textarea');
    const setter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value').set;
    setter.call(ta, '公司拖欠工资怎么维权？依据什么法律');
    ta.dispatchEvent(new Event('input', { bubbles: true }));
    return { value: ta.value, btnCount: form.querySelectorAll('button').length, hasSubmit: !!form.querySelector('button[type=submit]') };
  })()`);
  console.log("2) 输入:", JSON.stringify(diag));
  await new Promise((r) => setTimeout(r, 600));
  const sent = await evalJs(`(() => {
    const forms = Array.from(document.querySelectorAll('form'));
    const form = forms.find(f => f.querySelector('textarea'));
    if (!form) return 'no-form';
    try { form.requestSubmit(); return 'submitted'; } catch (e) { return 'submit-err:' + e.message; }
  })()`);
  console.log("   发送:", sent);
  // 等待回答渲染（最长 90s）
  let html = "";
  for (let i = 0; i < 45; i++) {
    await new Promise((r) => setTimeout(r, 2000));
    html = await evalJs(`document.querySelector('[data-msg-index]') ? document.querySelector('[data-msg-index]').outerHTML.slice(0, 2000) : ''`) || "";
    if (html.length > 300) break;
  }
  const hasLawRef = html.includes("law-ref");
  const hasContradiction = /建议核对|未在本次检索/.test(html);
  const hasDollar = /\$/.test(html.replace(/&amp;/g, "").replace(/&#36;/g, ""));
  console.log("3) 回答渲染: len", html.length, "| law-ref:", hasLawRef, "| 矛盾句:", hasContradiction, "| $:", hasDollar, "| 异常:", exceptions.length);
  console.log("   回答片段:", html.slice(0, 150).replace(/<[^>]+>/g, ""));

  const ok = html.length > 300 && !hasContradiction && !hasDollar && exceptions.length === 0;
  console.log("\n前端验收:", ok ? "PASS" : "FAIL");
  edge.kill();
  process.exit(ok ? 0 : 1);
}
main().catch((e) => { console.error("ERR", e); process.exit(1); });
