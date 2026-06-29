/* Lombada — service worker com cache seguro do app shell.
   Estratégia: navegação network-first com timeout curto; assets críticos sem timeout.
   Evita cache-first puro para não prender JS/CSS antigo. */

const CACHE_NAME = 'lombada-shell-v5';

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

function offlineCopy() {
  const lang = (self.navigator && self.navigator.language || 'pt').toLowerCase();
  if (lang.startsWith('en')) {
    return { lang: 'en', title: 'Lombada offline', heading: 'You are offline.', body: 'Lombada needs a connection to search for books and sync your shelf. Try again when you are back online.', retry: 'Try again' };
  }
  if (lang.startsWith('es')) {
    return { lang: 'es', title: 'Lombada sin conexión', heading: 'Estás sin conexión.', body: 'Lombada necesita conexión para buscar libros y sincronizar tu estante. Inténtalo de nuevo cuando vuelva internet.', retry: 'Reintentar' };
  }
  return { lang: 'pt-BR', title: 'Lombada offline', heading: 'Você está offline.', body: 'A Lombada precisa de conexão para buscar livros e sincronizar sua estante. Tente novamente quando a internet voltar.', retry: 'Tentar novamente' };
}

function offlineHTML() {
  const c = offlineCopy();
  return `<!doctype html>
<html lang="${c.lang}">
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>${c.title}</title>
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
    <h1>${c.heading}</h1>
    <p>${c.body}</p>
    <button type="button" onclick="location.reload()">${c.retry}</button>
  </main>
</body>
</html>`;
}
