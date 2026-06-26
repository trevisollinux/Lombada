/* Lombada — service worker de limpeza emergencial.
   Não cacheia nada. Serve apenas para remover caches antigos
   e desregistrar o service worker quebrado. */

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

    const windows = await self.clients.matchAll({ type: 'window' });
    for (const client of windows) {
      client.navigate(client.url);
    }

    await self.registration.unregister();
  })());
});

// Não interceptar fetch. Deixa o navegador buscar tudo na rede normalmente.
