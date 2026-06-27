/* Lombada — service worker mínimo.
   Este PR NÃO cacheia app shell.
   Objetivo: habilitar base PWA sem risco de servir JS/CSS antigo. */

self.addEventListener('install', event => {
  self.skipWaiting();
});

self.addEventListener('activate', event => {
  event.waitUntil((async () => {
    const keys = await caches.keys();

    await Promise.all(
      keys
        .filter(key => key.toLowerCase().includes('lombada'))
        .map(key => caches.delete(key))
    );

    await self.clients.claim();
  })());
});

self.addEventListener('fetch', event => {
  // Intencionalmente não intercepta.
  // O navegador segue para rede/cache HTTP normal.
});
