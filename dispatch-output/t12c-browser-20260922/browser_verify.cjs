/**
 * T12-C · 前端浏览器实机验收 v2（修正：登录页是「封面 → 钤印入典 → 表单」两步交互）
 *
 * 零 LLM：发问用命中 QA 语料的问句（QA 直返 = 零 token）；前端基址已覆盖为 localhost:8000。
 * 所有等待均为**有界轮询**并报告 boundedHit（撞上限=未收敛）。
 */
const PW = "C:/Users/33393/AppData/Local/npm-cache/_npx/0b9ff77863cb6e9f/node_modules/playwright-core";
const EXE = "C:/Users/33393/AppData/Local/ms-playwright/chromium-1234/chrome-win64/chrome.exe";
const OUT = "C:/Users/33393/Desktop/ai-legal-helper/dispatch-output/t12c-browser-20260922";
const { chromium } = require(PW);
const fs = require("fs");

const BASE = "http://localhost:3000";
const CORPUS_Q =
  "关于劳动合同的试用期，下列说法正确的是？A.劳动合同期限三年以上的，试用期不得超过六个月 " +
  "B.同一用人单位与同一劳动者只能约定一次试用期 C.试用期包含在劳动合同期限内 D.以上说法均正确";

const result = { steps: {}, apiRequests: [], apiErrors: [], nonApi404: [] };

async function pollUntil(fn, n = 20, gap = 1000) {
  for (let i = 1; i <= n; i++) {
    try { if (await fn()) return { ok: true, attempts: i, boundedHit: false }; } catch (e) {}
    await new Promise((r) => setTimeout(r, gap));
  }
  return { ok: false, attempts: n, boundedHit: true };
}

(async () => {
  const browser = await chromium.launch({ executablePath: EXE, headless: true });
  try {
    const page = await (await browser.newContext({ viewport: { width: 1280, height: 800 } })).newPage();
    page.on("request", (r) => { const u = r.url(); if (u.includes("/api/")) result.apiRequests.push(u); });
    page.on("response", (r) => {
      const u = r.url();
      if (u.includes("/api/") && r.status() >= 400) result.apiErrors.push(`${r.status()} ${u}`);
      else if (r.status() === 404 && !u.includes("/api/")) result.nonApi404.push(u);
    });

    // ── T1 封面页 ──
    await page.goto(`${BASE}/login`, { waitUntil: "load", timeout: 60000 });
    await page.waitForTimeout(3000);
    result.steps.T1_cover = {
      title: await page.title(),
      sealButtonText: (await page.locator("button").first().innerText()).replace(/\s+/g, "").slice(0, 20),
      inputCountBefore: await page.locator("input").count(),
    };
    await page.screenshot({ path: `${OUT}/shot-01-cover.png` });

    // ── T2 钤印 → 表单出现（有界）──
    await page.locator("button").first().click();
    const formAppear = await pollUntil(async () => (await page.locator("input").count()) > 0, 15, 800);
    result.steps.T2_seal_opens_form = {
      wait: formAppear,
      inputCountAfter: await page.locator("input").count(),
      inputs: await page.locator("input").evaluateAll((els) => els.map((e) => e.type || e.tagName)),
      buttons: await page.locator("button").evaluateAll((els) => els.map((b) => (b.innerText || "").replace(/\s+/g, "").slice(0, 12))),
    };
    await page.screenshot({ path: `${OUT}/shot-02-form.png` });

    // ── T3 未登录守卫（新上下文，避免被上面影响）──
    const ctx2 = await browser.newContext({ viewport: { width: 1280, height: 800 } });
    const p2 = await ctx2.newPage();
    await p2.goto(`${BASE}/admin`, { waitUntil: "load", timeout: 60000 });
    const guard = await pollUntil(async () => (await p2.url()).includes("/login"), 15, 800);
    result.steps.T3_admin_guard = { finalUrl: p2.url(), redirected: guard.ok, wait: guard };
    await ctx2.close();

    // ── T4 登录（隔离后端账号）──
    const user = page.locator('input[type="text"], input:not([type]):not([type="password"])').first();
    const pwd = page.locator('input[type="password"]').first();
    await user.fill("t12c_user");
    await pwd.fill("t12c-Verify-123");
    await page.locator('button[type="submit"]').first().click();
    const logged = await pollUntil(async () => !(await page.url()).includes("/login"), 20, 1000);
    result.steps.T4_login = { urlAfter: page.url(), ok: logged.ok, wait: logged };
    await page.waitForTimeout(3000);
    await page.screenshot({ path: `${OUT}/shot-03-chat.png` });

    // ── T5 发问（语料命中 ⇒ 零 LLM）→ 流式渲染 ──
    const before = await page.evaluate(() => document.body.innerText.length);
    await page.locator("textarea").first().fill(CORPUS_Q);
    await page.locator('button[type="submit"], [title*="发送"]').first().click();
    const grew = await pollUntil(async () => (await page.evaluate(() => document.body.innerText.length)) > before + 200, 25, 1500);
    const bodyText = await page.evaluate(() => document.body.innerText);
    result.steps.T5_ask = {
      bodyBefore: before,
      bodyAfter: bodyText.length,
      wait: grew,
      answerTail: bodyText.slice(-260),
    };
    await page.screenshot({ path: `${OUT}/shot-04-answer.png` });

    // ── T6 法条卡（有点击引用则验）──
    const cite = page.locator("text=/第[一二三四五六七八九十百零]+条/").first();
    const hasCite = (await cite.count()) > 0;
    let cardOpened = false;
    if (hasCite) {
      try {
        await cite.click({ timeout: 4000 });
        await page.waitForTimeout(2000);
        cardOpened = (await page.locator('[class*="law" i], [role="dialog"]').count()) > 0;
      } catch (e) {}
    }
    result.steps.T6_law_card = { citationFound: hasCite, cardAppeared: cardOpened };
    await page.screenshot({ path: `${OUT}/shot-05-lawcard.png` });

    // ── T7 移动端视口（400px）横向溢出 ──
    await page.setViewportSize({ width: 400, height: 800 });
    await page.waitForTimeout(2000);
    result.steps.T7_mobile = await page.evaluate(() => ({
      scrollWidth: document.documentElement.scrollWidth,
      clientWidth: document.documentElement.clientWidth,
      overflowPx: document.documentElement.scrollWidth - document.documentElement.clientWidth,
    }));
    await page.screenshot({ path: `${OUT}/shot-06-mobile.png` });

    // ── T8 基址核验（是否全部打 localhost:8000 ⇒ 零生产流量）──
    const offLocal = result.apiRequests.filter((u) => !u.startsWith("http://localhost:8000"));
    result.steps.T8_api_base = { total: result.apiRequests.length, offLocal: offLocal.length, sample: offLocal.slice(0, 3) };
  } catch (e) {
    result.error = String(e && e.message ? e.message : e);
  } finally {
    await browser.close();
    fs.writeFileSync(`${OUT}/browser-result.json`, JSON.stringify(result, null, 1), "utf-8");
    console.log(JSON.stringify({ steps: result.steps, apiErrors: result.apiErrors.slice(0, 5), nonApi404: result.nonApi404.slice(0, 5), error: result.error }, null, 1));
  }
})();
