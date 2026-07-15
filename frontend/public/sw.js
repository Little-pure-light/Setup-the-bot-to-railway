// Service Worker for 小宸光 PWA
const CACHE_NAME = 'xiaochenguang-v1';
const STATIC_ASSETS = [
  '/',
  '/index.html',
  '/manifest.json'
];

// 安裝：快取靜態資源
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(STATIC_ASSETS);
    })
  );
  self.skipWaiting();
});

// 啟動：清除舊快取
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames
          .filter((name) => name !== CACHE_NAME)
          .map((name) => caches.delete(name))
      );
    })
  );
  self.clients.claim();
});

// 攔截請求：API 請求直接走網路，靜態資源走快取優先
self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);

  // API 請求不快取，直接走網路
  if (url.hostname.includes('dreamground.net') && url.pathname.startsWith('/api')) {
    event.respondWith(fetch(event.request));
    return;
  }

  // 靜態資源：快取優先，失敗再走網路
  event.respondWith(
    caches.match(event.request).then((cached) => {
      return cached || fetch(event.request).then((response) => {
        // 只快取成功的 GET 請求
        if (event.request.method === 'GET' && response.status === 200) {
          const responseClone = response.clone();
          caches.open(CACHE_NAME).then((cache) => {
            cache.put(event.request, responseClone);
          });
        }
        return response;
      });
    }).catch(() => {
      // 離線時顯示首頁
      return caches.match('/');
    })
  );
});
