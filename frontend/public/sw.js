/* Lombada (frontend React) — service worker do app shell.
   Navegações: network-first com fallback offline (nunca prende HTML antigo).
   Assets do Vite (assets/, nomes com hash): cache-first, imutáveis.
   APIs, login e o app legado ficam fora do escopo do worker. */

const CACHE_NAME = 'lombada-v2-shell-v2';

/* Ex.: '/app-v2/' ou '/v3-kimi/' — o mesmo sw.js serve qualquer base. */
const scopePath = new URL(self.registration.scope).pathname;

self.addEventListener('install', (event) => {
  event.waitUntil((async () => {
    try {
      const cache = await caches.open(CACHE_NAME);
      await cache.add(scopePath);
    } catch {
      /* sem rede no install: o cache enche no primeiro uso */
    }
    await self.skipWaiting();
  })());
});

self.addEventListener('activate', (event) => {
  event.waitUntil((async () => {
    const keys = await caches.keys();
    await Promise.all(
      keys
        .filter((key) => key.startsWith('lombada-v2-shell-') && key !== CACHE_NAME)
        .map((key) => caches.delete(key)),
    );
    await self.clients.claim();
  })());
});

self.addEventListener('fetch', (event) => {
  const request = event.request;
  if (request.method !== 'GET') return;

  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;
  if (!url.pathname.startsWith(scopePath)) return;

  if (request.mode === 'navigate') {
    event.respondWith(navigationNetworkFirst(request));
    return;
  }

  if (url.pathname.startsWith(`${scopePath}assets/`)) {
    event.respondWith(assetCacheFirst(request));
  }
});

async function navigationNetworkFirst(request) {
  const cache = await caches.open(CACHE_NAME);
  try {
    const response = await fetch(request);
    if (response && response.ok) cache.put(request, response.clone());
    return response;
  } catch (error) {
    const cached = (await cache.match(request)) || (await cache.match(scopePath));
    if (cached) return cached;
    return new Response(offlineHTML(), {
      headers: { 'Content-Type': 'text/html; charset=utf-8' },
    });
  }
}

async function assetCacheFirst(request) {
  const cache = await caches.open(CACHE_NAME);
  const cached = await cache.match(request);
  if (cached) return cached;
  const response = await fetch(request);
  if (response && response.ok) cache.put(request, response.clone());
  return response;
}

function offlineCopy() {
  const lang = ((self.navigator && self.navigator.language) || 'pt').toLowerCase();
  if (lang.startsWith('en')) {
    return {
      lang: 'en',
      title: 'Lombada offline',
      heading: 'You are offline.',
      body: 'Lombada needs a connection to search for books and sync your shelf. Try again when you are back online.',
      retry: 'Try again',
    };
  }
  return {
    lang: 'pt-BR',
    title: 'Lombada offline',
    heading: 'Você está offline.',
    body: 'A Lombada precisa de conexão para buscar livros e sincronizar sua estante. Tente novamente quando a internet voltar.',
    retry: 'Tentar novamente',
  };
}

function offlineHTML() {
  const copy = offlineCopy();
  return `<!doctype html>
<html lang="${copy.lang}">
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>${copy.title}</title>
<style>
  :root{--paper:#F4EFE6;--card:#F4EFE6;--ink:#1A1714;--muted:#6F6655;--rule:rgba(26,23,20,.18)}
  @media (prefers-color-scheme: dark){:root{--paper:#0D0B09;--card:#1A1714;--ink:#F4EFE6;--muted:#B7AA99;--rule:rgba(247,240,229,.20)}}
  body{margin:0;font-family:Georgia,serif;background:var(--paper);color:var(--ink);display:grid;min-height:100vh;place-items:center;padding:24px}
  main{max-width:36rem;border:1px solid var(--rule);background:var(--card);padding:28px;border-radius:18px}
  .eyebrow{font-family:monospace;text-transform:uppercase;letter-spacing:.14em;font-size:11px;color:var(--muted)}
  h1{font-size:32px;margin:.35rem 0 1rem}
  p{font-size:18px;line-height:1.45}
  button{margin-top:1.25rem;border:1px solid var(--ink);background:var(--ink);color:var(--paper);border-radius:999px;padding:12px 18px;font:700 11px monospace;text-transform:uppercase;letter-spacing:.12em;cursor:pointer}
</style>
<body>
  <main>
    <p class="eyebrow">Lombada</p>
    <h1>${copy.heading}</h1>
    <p>${copy.body}</p>
    <button type="button" onclick="location.reload()">${copy.retry}</button>
  </main>
</body>
</html>`;
}
