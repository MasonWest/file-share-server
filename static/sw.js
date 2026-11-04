/* FileBox service worker —— 只做一件事：让静态壳子在断网时还能开。
 *
 * 三条铁律，改之前先读：
 * 1. 绝不缓存 /api/* 和 /s/*。前者带设备令牌、后者带分享令牌，缓存等于把凭证
 *    留在磁盘上，还会让用户看到别人/上一次的数据。
 * 2. HTML 走 network-first。这个项目是单文件 Vue，改一版换一次壳子，
 *    离线兜底只是"白屏变旧页面"，不能让旧壳子盖住新接口。
 * 3. 任何异常都要静默吞掉：SW 是增强，挂掉不能影响主流程。
 */
const VERSION = "v1";
const STATIC_CACHE = `filebox-static-${VERSION}`;
const SHELL_CACHE = `filebox-shell-${VERSION}`;

const PRECACHE = ["/vendor/vue.global.prod.js", "/static/icon.svg", "/static/icon-192.png"];

self.addEventListener("install", (event) => {
  event.waitUntil(
    (async () => {
      const cache = await caches.open(STATIC_CACHE);
      // 逐个 add：其中一个 404 不该让整次安装失败
      await Promise.allSettled(PRECACHE.map((url) => cache.add(url)));
      await self.skipWaiting();
    })()
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    (async () => {
      const keys = await caches.keys();
      await Promise.all(
        keys.filter((k) => k.startsWith("filebox-") && k !== STATIC_CACHE && k !== SHELL_CACHE).map((k) => caches.delete(k))
      );
      await self.clients.claim();
    })()
  );
});

function bypass(url) {
  // API 与分享下载一律不碰，连 cache.match 都不做
  return url.pathname.startsWith("/api/") || url.pathname.startsWith("/s/");
}

self.addEventListener("fetch", (event) => {
  const request = event.request;
  if (request.method !== "GET") return;

  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;
  if (bypass(url)) return;

  // 静态依赖：缓存优先，后台顺手更新
  if (url.pathname.startsWith("/vendor/") || url.pathname.startsWith("/static/")) {
    event.respondWith(
      (async () => {
        const cache = await caches.open(STATIC_CACHE);
        const hit = await cache.match(request);
        const network = fetch(request)
          .then((response) => {
            if (response && response.ok) cache.put(request, response.clone());
            return response;
          })
          .catch(() => null);
        return hit || (await network) || Response.error();
      })()
    );
    return;
  }

  // 页面导航：网络优先，4 秒没响应就用缓存的壳子
  if (request.mode === "navigate" || request.destination === "document") {
    event.respondWith(
      (async () => {
        const cache = await caches.open(SHELL_CACHE);
        try {
          const controller = new AbortController();
          const timer = setTimeout(() => controller.abort(), 4000);
          const response = await fetch(request, { signal: controller.signal });
          clearTimeout(timer);
          if (response && response.ok) cache.put("/", response.clone());
          return response;
        } catch (error) {
          const cached = await cache.match("/");
          if (cached) return cached;
          return new Response("服务器这会儿连不上，等它醒过来再刷新。", {
            status: 503,
            headers: { "Content-Type": "text/plain; charset=utf-8" },
          });
        }
      })()
    );
  }
});
