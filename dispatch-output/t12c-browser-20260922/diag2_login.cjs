/**
 * T12-C 诊断 2：登录表单点了没反应？——取按钮级证据 + 尝试正确的提交按钮。
 * 有界：请求等待最多 N 次 × gap，报告 boundedHit。
 */
const PW = "C:/Users/33393/AppData/Local/npm-cache/_npx/0b9ff77863cb6e9f/node_modules/playwright-core";
const EXE = "C:/Users/33393/AppData/Local/ms-playwright/chromium-1234/chrome-win64/chrome.exe";
const OUT = "C:/Users/33393/Desktop/ai-legal-helper/dispatch-output/t12c-browser-20260922";
const { chromium } = require(PW);
const fs = require("fs");

(async () => {
  const browser = await chromium.launch({ executablePath: EXE, headless: true });
  const out = { apiCalls: [], consoleErrors: [], pageErrors: [] };
  try {
    const page = await (await browser.newContext({ viewport: { width: 1280, height: 800 } })).newPage();
    page.on("request", (r) => { if (r.url().includes("/api/") || r.url().includes("8000")) out.apiCalls.push(r.method() + " " + r.url()); });
    page.on("console", (m) => { if (m.type() === "error") out.consoleErrors.push(m.text().slice(0, 200)); });
    page.on("pageerror", (e) => out.pageErrors.push(String(e).slice(0, 200)));

    await page.goto("http://localhost:3000/login", { waitUntil: "load", timeout: 60000 });
    await page.waitForTimeout(2500);
    await page.locator("button").first().click(); // 钤印入典
    await page.waitForTimeout(1500);

    out.buttons = await page.locator("button").evaluateAll((els) =>
      els.map((b) => ({ text: (b.innerText || "").replace(/\s+/g, "").slice(0, 10), type: b.type, cls: b.className.slice(0, 50), disabled: b.disabled }))
    );
    // 填表（用第 1 个 text 与第 1 个 password）
    await page.locator('input[type="text"], input:not([type])').first().fill("t12c_user");
    await page.locator('input[type="password"]').first().fill("t12c-Verify-123");
    // 点**第 2 个**「登录」按钮（第一个疑为 tab）
    const btn = page.locator('button:has-text("登录")');
    out.loginBtnCount = await btn.count();
    await btn.nth(out.loginBtnCount - 1).click();

    for (let i = 1; i <= 12; i++) {
      if (out.apiCalls.length > 0 || !page.url().includes("/login")) break;
      await page.waitForTimeout(1000);
      out.waitedAttempts = i;
    }
    out.apiCalls = out.apiCalls.slice(0, 8);
    out.urlAfter = page.url();
    out.storageToken = await page.evaluate(() => (localStorage.getItem("alh_token") ? "SET" : "null"));
    out.bodyTail = (await page.evaluate(() => document.body.innerText)).slice(-200);
    await page.screenshot({ path: `${OUT}/diag2-after-submit.png` });
  } catch (e) {
    out.error = String(e && e.message ? e.message : e);
  } finally {
    await browser.close();
    fs.writeFileSync(`${OUT}/diag2-login.json`, JSON.stringify(out, null, 1), "utf-8");
    console.log(JSON.stringify(out, null, 1).slice(0, 2500));
  }
})();
