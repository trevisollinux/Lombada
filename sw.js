/*
 * Lombada — Service Worker
 * Estratégia:
 *   App shell (/, CSS, JS)       → Cache First  (carrega instantâneo mesmo c/ Render dormindo)
 *   /api/prateleira               → Network First + fallback no cache (estante offline)
 *   /api/capa                    → Cache First  (capas não mudam)
 *   /api/buscar, /api/edicoes    → Network Only (precisa de rede mesmo)
 *   Google Fonts                 → Stale While Revalidate
 */

const VERSION   = 'lombada-v1';
const CACHE     = VERSION;

const SHELL = [
  '/',
  '/static/app.css',
  '/static/app.js',
  '/static/i18n.js',
];

// ── install: pré-cacheia o shell ───────────────────────────
self.addEventListener('install', evt => {
  evt.waitUntil(
    caches.open(CACHE)
      .then(c => c.addAll(SHELL))
      .then(() => self.skipWaiting())
  );
});

// ── activate: limpa versões antigas ───────────────────────
self.addEventListener('activate', evt => {
  evt.waitUntil(
    caches.keys()
      .then(keys => Promise.all(
        keys.filter(k => k !== CACHE).map(k => caches.delete(k))
      ))
      .then(() => self.clients.claim())
  );
});

// ── fetch ──────────────────────────────────────────────────
self.addEventListener('fetch', evt => {
  const { request } = evt;
  const url = new URL(request.url);

  // Só intercepta o próprio origin (+ fonts.gstatic)
  const isOwn   = url.origin === self.location.origin;
  const isFonts = url.hostname.includes('gstatic.com') ||
                  url.hostname.includes('googleapis.com');

  if (!isOwn && !isFonts) return;

  // Google Fonts — stale-while-revalidate
  if (isFonts) {
    evt.respondWith(swr(request));
    return;
  }

  const path = url.pathname;

  // App shell — cache first
  if (path === '/' || path.startsWith('/static/')) {
    evt.respondWith(cacheFirst(request));
    return;
  }

  // Prateleira — network first (funciona offline com cache)
  if (path === '/api/prateleira') {
    evt.respondWith(networkFirst(request, '[]'));
    return;
  }

  // Capas — cache first (imagens não mudam)
  if (path === '/api/capa') {
    evt.respondWith(cacheFirst(request));
    return;
  }

  // Dados do usuário (/api/eu, /api/u/*, /api/feed) — network first
  if (path.startsWith('/api/eu') || path.startsWith('/api/u/') ||
      path.startsWith('/api/feed')) {
    evt.respondWith(networkFirst(request, 'null'));
    return;
  }

  // Busca, edições, explore — network only (sem cache)
  // (deixa o browser tratar normalmente)
});

// ── estratégias ────────────────────────────────────────────
async function cacheFirst(req) {
  const cached = await caches.match(req);
  if (cached) return cached;
  try {
    const resp = await fetch(req);
    if (resp.ok) {
      const c = await caches.open(CACHE);
      c.put(req, resp.clone());
    }
    return resp;
  } catch {
    return new Response('', { status: 503 });
  }
}

async function networkFirst(req, fallbackJson) {
  try {
    const resp = await fetch(req);
    if (resp.ok) {
      const c = await caches.open(CACHE);
      c.put(req, resp.clone());
    }
    return resp;
  } catch {
    const cached = await caches.match(req);
    if (cached) return cached;
    return new Response(fallbackJson, {
      headers: { 'Content-Type': 'application/json' }
    });
  }
}

async function swr(req) {
  const c      = await caches.open(CACHE);
  const cached = await c.match(req);
  const fresh  = fetch(req)
    .then(resp => { if (resp.ok) c.put(req, resp.clone()); return resp; })
    .catch(() => null);
  return cached || fresh;
}
