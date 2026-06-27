/* Lombada — service worker com cache seguro do app shell.
   Estratégia: navegação network-first com timeout curto; assets críticos sem timeout.
   Evita cache-first puro para não prender JS/CSS antigo. */

const CACHE_NAME = 'lombada-shell-v4';

const APP_SHELL = [
  '/',
  '/static/app.css',
  '/static/i18n.js',
  '/static/app.js',
  '/static/icons/icon.svg',
  '/static/icons/icon-maskable.svg',
  '/manifest.json'
];

const NETWORK_TIMEOUT_MS = 1800;
const CRITICAL_ASSETS = new Set(['/static/app.js', '/static/app.css', '/static/i18n.js']);

self.addEventListener('install', event => {
  event.waitUntil((async () => {
    const cache = await caches.open(CACHE_NAME);
    await cache.addAll(APP_SHELL);
  })());
});

self.addEventListener('activate', event => {
  event.waitUntil((async () => {
    const keys = await caches.keys();

    await Promise.all(
      keys
        .filter(key => key.toLowerCase().includes('lombada') && key !== CACHE_NAME)
        .map(key => caches.delete(key))
    );


    await self.clients.claim();
  })());
});


self.addEventListener('message', event => {
  if (event.data && event.data.type === 'SKIP_WAITING') {
    self.skipWaiting();
  }
});

self.addEventListener('fetch', event => {
  const request = event.request;

  if (request.method !== 'GET') return;

  const url = new URL(request.url);
  const sameOrigin = url.origin === self.location.origin;

  if (!sameOrigin) return;

  const path = url.pathname;

  if (path.startsWith('/api/')) return;

  const isRootNavigation = request.mode === 'navigate' && path === '/';
  const isCriticalAsset = CRITICAL_ASSETS.has(path);
  const isShellAsset = APP_SHELL.includes(path);

  if (isRootNavigation) {
    event.respondWith(networkFirstWithTimeout(request));
    return;
  }

  if (isCriticalAsset) {
    event.respondWith(networkFirst(request));
    return;
  }

  if (isShellAsset) {
    event.respondWith(networkFirstWithTimeout(request));
    return;
  }

  // Não intercepta APIs, login, capas, feed, perfil público ou dados pessoais neste PR.
});

async function networkFirstWithTimeout(request) {
  const cache = await caches.open(CACHE_NAME);

  const networkPromise = fetch(request).then(response => {
    if (response && response.ok) {
      cache.put(request, response.clone());
    }
    return response;
  });

  const timeoutPromise = new Promise(resolve => {
    setTimeout(async () => {
      const cached = await cache.match(request);
      resolve(cached || null);
    }, NETWORK_TIMEOUT_MS);
  });

  try {
    return await Promise.race([networkPromise, timeoutPromise]) || await networkPromise;
  } catch (error) {
    const cached = await cache.match(request);
    if (cached) return cached;

    if (request.mode === 'navigate') {
      return new Response(offlineHTML(), { headers: { 'Content-Type': 'text/html; charset=utf-8' } });
    }

    throw error;
  }
}

async function networkFirst(request) {
  const cache = await caches.open(CACHE_NAME);

  try {
    const response = await fetch(request);
    if (response && response.ok) {
      cache.put(request, response.clone());
    }
    return response;
  } catch (error) {
    const cached = await cache.match(request);
    if (cached) return cached;
    throw error;
  }
}

function offlineHTML() {
  return `<!doctype html>
<html lang="pt-BR">
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Lombada offline</title>
<body style="margin:0;font-family:Georgia,serif;background:#ECE4D4;color:#1A1714;display:grid;min-height:100vh;place-items:center;padding:24px">
  <main style="max-width:36rem;border:1px solid rgba(26,23,20,.18);background:#F4EFE6;padding:28px;border-radius:18px">
    <p style="font-family:monospace;text-transform:uppercase;letter-spacing:.14em;font-size:11px;color:#6F6655">Lombada</p>
    <h1 style="font-size:32px;margin:.35rem 0 1rem">Você está offline.</h1>
    <p style="font-size:18px;line-height:1.45">A Lombada precisa de conexão para buscar livros e sincronizar sua estante. Tente novamente quando a internet voltar.</p>
    <button type="button" onclick="location.reload()" style="margin-top:1.25rem;border:1px solid #1A1714;background:#1A1714;color:#ECE4D4;border-radius:999px;padding:12px 18px;font:700 11px monospace;text-transform:uppercase;letter-spacing:.12em">Tentar novamente</button>
  </main>
</body>
</html>`;
}
