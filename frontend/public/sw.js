/* 法智 PWA service worker（2026-08-08）：缓存应用壳，API/SSE 网络优先不缓存。
 *
 * 策略：
 * - 应用壳（首页/静态资源/manifest/图标）：安装时预缓存 + 网络优先回退缓存（拿到新内容就更新缓存）
 * - /api/* 与写请求：一律网络直连，绝不缓存（含鉴权头/动态问答，缓存会串用户）
 * - 离线兜底：壳内已缓存页面可打开，API 失败自然报错（登录/问答需联网）
 */
const CACHE = "fazhi-shell-v1";
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

  // 应用壳/静态资源：网络优先，失败回退缓存
  event.respondWith(
    fetch(req)
      .then((res) => {
        if (res && res.ok) {
          const copy = res.clone();
          caches.open(CACHE).then((c) => c.put(req, copy));
        }
        return res;
      })
      .catch(() => caches.match(req).then((m) => m || caches.match("/")))
  );
});
