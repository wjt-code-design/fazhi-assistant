/**
 * T12-C 诊断：登录页为何没有输入框？（只读，取 DOM 级证据）
 * 有界等待：最多 N 次 × gap，报告 boundedHit。
 */
const PW = "C:/Users/33393/AppData/Local/npm-cache/_npx/0b9ff77863cb6e9f/node_modules/playwright-core";
const EXE = "C:/Users/33393/AppData/Local/ms-playwright/chromium-1234/chrome-win64/chrome.exe";
const OUT = "C:/Users/33393/Desktop/ai-legal-helper/dispatch-output/t12c-browser-20260922";
const { chromium } = require(PW);
const fs = require("fs");

(async () => {
  const browser = await chromium.launch({ executablePath: EXE, headless: true });
  const out = { consoleErrors: [], pageErrors: [], requests: [] };
  try {
    const page = await (await browser.newContext({ viewport: { width: 1280, height: 800 } })).newPage();
    page.on("console", (m) => { if (m.type() === "error") out.consoleErrors.push(m.text().slice(0, 300)); });
    page.on("pageerror", (e) => out.pageErrors.push(String(e).slice(0, 300)));
    page.on("request", (r) => { if (r.url().includes("/api/")) out.requests.push(r.url()); });

    await page.goto("http://localhost:3000/login", { waitUntil: "load", timeout: 60000 });
    await page.waitForTimeout(4000);

    out.dom = await page.evaluate(() => ({
      inputCount: document.querySelectorAll("input").length,
      buttonCount: document.querySelectorAll("button").length,
      formCount: document.querySelectorAll("form").length,
      inputs: Array.from(document.querySelectorAll("input")).map((i) => i.outerHTML.slice(0, 120)),
      buttons: Array.from(document.querySelectorAll("button")).map((b) => (b.innerText || "").trim().slice(0, 40) + " | " + b.className.slice(0, 60)),
      bodyText: document.body.innerText.slice(0, 400),
      docHeight: document.documentElement.scrollHeight,
      localStorageToken: localStorage.getItem("alh_token"),
    }));
    await page.screenshot({ path: `${OUT}/diag-login-fullpage.png`, fullPage: true });
    out.afterClickEffects = await page.evaluate(() => document.body.innerText.length);
  } catch (e) {
    out.error = String(e && e.message ? e.message : e);
  } finally {
    await browser.close();
    fs.writeFileSync(`${OUT}/diag-login.json`, JSON.stringify(out, null, 1), "utf-8");
    console.log(JSON.stringify(out, null, 1).slice(0, 3000));
  }
})();
