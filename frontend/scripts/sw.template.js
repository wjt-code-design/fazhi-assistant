/* 法智 PWA service worker 模板（R10：构建号**构建期嵌入**，产出 public/sw.js）。
 *
 * 为什么改成模板 + 构建期替换：
 * 改前 `public/sw.js` 的 `CACHE` 顶层默认 `fazhi-shell-dev`，只有 `install` 事件里才
 * fetch `/build-id.txt` 去改它。但浏览器回收 Worker 后再启动时**不会重跑 install**，
 * 模块重新求值 ⇒ `CACHE` 又回到 dev 名，于是 fetch 处理器把资源写进 dev 缓存、离线兜底
 * 也查 dev 缓存 —— 版本化失效，"旧 HTML 引用已删 chunk"的白屏链会复现。
 * 现在由 `scripts/write-build-id.mjs` 在构建期把 `__BUILD_ID__` 换成真实构建号：
 * 模块一被求值 `CACHE` 就是对的，不再依赖任何事件或网络。
 *
 * 策略：
 * - 缓存名 = fazhi-shell-<BUILD_ID>：构建号变化 → 新缓存名 → activate 清旧缓存。
 * - 应用壳（首页/静态资源/manifest/图标）：安装时预缓存 + 网络优先回退缓存。
 * - /api/* 与写请求：网络直连，绝不缓存（含鉴权头/动态问答，缓存会串用户）。
 * - 离线兜底：**只查当前版本缓存**，命中即保证 HTML 与其引用的 chunk 同版本。
 */
// 构建期由 scripts/write-build-id.mjs 把 __BUILD_ID__ 替换成真实构建号。
// 直接写进字面量：产物里 `CACHE` 一眼可见是哪个版本，且不需要任何运行时求值。
const CACHE = "fazhi-shell-__BUILD_ID__";
const SHELL = ["/", "/chat", "/manifest.webmanifest", "/icon-192.png", "/icon-512.png", "/apple-touch-icon.png"];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(CACHE)
      .then((c) => c.addAll(SHELL))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      // 名字含当前构建号，k !== CACHE 即"非本次发版"——旧壳缓存全清
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return; // 写请求直连
  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return; // 跨域（含后端 API 独立域名时）不拦截
  if (url.pathname.startsWith("/api/")) return; // API/SSE 网络优先
  if (url.pathname === "/build-id.txt") return; // 版本桥接文件永不缓存

  // 应用壳/静态资源：网络优先，失败回退**仅当前版本**缓存
  event.respondWith(
    fetch(req)
      .then((res) => {
        if (res && res.ok) {
          const copy = res.clone();
          caches.open(CACHE).then((c) => c.put(req, copy));
        }
        return res;
      })
      .catch(async () => {
        const c = await caches.open(CACHE);
        return (await c.match(req)) || (await c.match("/"));
      })
  );
});
