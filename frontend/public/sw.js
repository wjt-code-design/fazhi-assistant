/* 法智 PWA service worker（2026-09-15 T1.1 构建号版本化）：缓存应用壳，API/SSE 网络优先不缓存。
 *
 * 策略：
 * - 缓存名 = fazhi-shell-<BUILD_ID>：install 时 fetch /build-id.txt（postbuild 由
 *   scripts/write-build-id.mjs 从 .next/BUILD_ID 复制生成）。每次发版构建号变化 →
 *   新缓存名 → activate 清旧缓存，杜绝"旧 HTML 引用已删 chunk"的白屏链（旧版 CACHE 名
 *   硬编码 fazhi-shell-v1 是 2026-09-15 审计确认的 P0 缺陷）。
 * - 应用壳（首页/静态资源/manifest/图标）：安装时预缓存 + 网络优先回退缓存（拿到新内容就更新缓存）
 * - /api/* 与写请求：一律网络直连，绝不缓存（含鉴权头/动态问答，缓存会串用户）
 * - 离线兜底：**只查当前版本缓存**，命中即保证 HTML 与其引用的 chunk 同版本
 */
let CACHE = "fazhi-shell-dev"; // 兜底名：build-id.txt 不可读时（如 next dev）使用
const SHELL = ["/", "/chat", "/manifest.webmanifest", "/icon-192.png", "/icon-512.png", "/apple-touch-icon.png"];

async function resolveCacheName() {
  try {
    const res = await fetch("/build-id.txt", { cache: "no-store" });
    if (res.ok) {
      const bid = (await res.text()).trim();
      if (bid) CACHE = `fazhi-shell-${bid}`;
    }
  } catch {
    /* dev 环境或文件缺失：保持兜底名 */
  }
  return CACHE;
}

self.addEventListener("install", (event) => {
  event.waitUntil(
    resolveCacheName()
      .then((name) => caches.open(name))
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
  if (url.pathname === "/build-id.txt") return; // 版本桥接文件永不缓存，保证每次拿到最新构建号

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
