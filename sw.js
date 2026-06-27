/* Lombada — service worker com cache seguro do app shell.
   Estratégia: navegação network-first com timeout curto; assets críticos sem timeout.
   Evita cache-first puro para não prender JS/CSS antigo. */

const CACHE_NAME = 'lombada-shell-v3';

const APP_SHELL = [
  '/',
  '/static/app.css',
  '/static/i18n.js',
  '/static/app.js',
  '/static/icons/icon.svg',
  '/static/icons/icon-maskable.svg'
];

const NETWORK_TIMEOUT_MS = 1800;
const CRITICAL_ASSETS = new Set(['/static/app.js', '/static/app.css', '/static/i18n.js']);

self.addEventListener('install', event => {
  event.waitUntil((async () => {
    const cache = await caches.open(CACHE_NAME);
    await cache.addAll(APP_SHELL);
    await self.skipWaiting();
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
      return new Response(
        '<!doctype html><html lang="pt-BR"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Lombada</title><body style="font-family:Georgia,serif;padding:24px;background:#ECE4D4;color:#1A1714"><h1>Lombada.</h1><p>Sem conexão no momento. Tente abrir novamente em alguns instantes.</p></body></html>',
        { headers: { 'Content-Type': 'text/html; charset=utf-8' } }
      );
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
