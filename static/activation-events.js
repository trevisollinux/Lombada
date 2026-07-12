/* Instrumentação estrutural do funil de ativação.

   Não lê nem envia título, autor, ISBN, consulta, crítica, diário, bio ou outro
   texto do usuário. Todos os eventos continuam sujeitos à feature flag pública
   product_analytics e à allowlist do backend. */
(function activationEventsBootstrap(global) {
  'use strict';

  const analytics = global.LombadaAnalytics;
  const features = global.LombadaFeatures;
  if (!analytics || !features) return;

  let ready = false;
  let appOpenedSent = false;
  const pending = [];
  const MAX_PENDING = 20;
  const standalone = Boolean(
    global.matchMedia?.('(display-mode: standalone)')?.matches ||
    global.navigator?.standalone === true
  );
  const twa = /^android-app:/i.test(global.document.referrer || '');

  function emit(eventName, properties) {
    try {
      if (!ready) {
        if (pending.length < MAX_PENDING) pending.push([eventName, properties]);
        return;
      }
      analytics.track(eventName, properties || {});
    } catch (_) {}
  }

  function emitAppOpenedAfterSession() {
    if (appOpenedSent) return;
    appOpenedSent = true;
    const localeRaw = (global.document.documentElement.lang || 'pt-BR').trim();
    const locale = ['pt-BR', 'en', 'es'].includes(localeRaw) ? localeRaw : 'pt-BR';
    emit('app_opened', {
      source: twa ? 'twa' : (standalone ? 'pwa' : 'web'),
      locale,
      standalone
    });
  }

  Promise.resolve(features.ready).catch(() => null).then(() => {
    ready = true;
    pending.splice(0).forEach(([eventName, properties]) => analytics.track(eventName, properties || {}));
  });

  function sourceFromElement(element) {
    if (!element?.closest) return 'unknown';
    if (element.closest('#secEstante')) return 'shelf';
    if (element.closest('#secPerfil')) return 'profile';
    if (element.closest('#secFeed')) return 'explore';
    if (element.closest('#secBuscar')) return 'search';
    return 'unknown';
  }

  function normalizedStatus(value) {
    return ['Lido', 'Lendo', 'Quero ler'].includes(value) ? value : 'custom';
  }

  function safeJsonBody(init) {
    const raw = init && typeof init.body === 'string' ? init.body : '';
    if (!raw || raw.length > 20000) return {};
    try {
      const parsed = JSON.parse(raw);
      return parsed && typeof parsed === 'object' && !Array.isArray(parsed) ? parsed : {};
    } catch (_) {
      return {};
    }
  }

  function readingProperties(body, source) {
    return {
      source,
      status: normalizedStatus(String(body.status || 'custom')),
      has_rating: body.nota !== null && body.nota !== undefined && body.nota !== '',
      public: body.publico === true
    };
  }

  function progressType(body) {
    const raw = String(body.progresso_tipo || '').toLowerCase();
    if (raw === 'pagina' || body.pagina !== null && body.pagina !== undefined) return 'page';
    if (raw === 'porcentagem' || body.porcentagem !== null && body.porcentagem !== undefined) return 'percentage';
    if (raw === 'capitulo' || body.capitulo_ordem !== null && body.capitulo_ordem !== undefined) return 'chapter';
    return 'free';
  }

  function isDiaryWrite(method, path) {
    return (
      method === 'POST' && /^\/api\/leitura\/\d+\/diario$/.test(path)
    ) || (
      method === 'PATCH' && /^\/api\/diario\/\d+$/.test(path)
    );
  }

  const originalFetch = global.fetch.bind(global);
  global.fetch = async function instrumentedFetch(input, init = {}) {
    const requestUrl = typeof input === 'string' || input instanceof URL
      ? String(input)
      : String(input?.url || '');
    const method = String(init.method || input?.method || 'GET').toUpperCase();
    const body = safeJsonBody(init);
    const response = await originalFetch(input, init);

    try {
      const url = new URL(requestUrl, global.location.href);
      const path = url.pathname;
      if (response.ok && path !== '/api/events') {
        if (method === 'POST' && path === '/api/prateleira') {
          emit('reading_created', readingProperties(body, body.source === 'quick_action' ? 'quick_action' : 'search'));
        } else if (method === 'PATCH' && /^\/api\/prateleira\/\d+$/.test(path)) {
          emit('reading_updated', readingProperties(body, body.source === 'quick_action' ? 'quick_action' : 'detail'));
        } else if (isDiaryWrite(method, path)) {
          emit('progress_logged', {
            source: body.source === 'quick_action' ? 'quick_action' : 'diary',
            progress_type: progressType(body),
            public: body.publico === true
          });
        } else if (method === 'GET' && path === '/api/eu') {
          // /api/eu cria/recupera a sessão anônima. Emitir somente após sua resposta
          // garante que app_opened receba user_id no POST seguinte de analytics.
          emitAppOpenedAfterSession();
          const marker = global.sessionStorage?.getItem('lombada_after_google_login');
          if (marker) {
            response.clone().json().then(data => {
              if (data && data.logado) {
                emit('profile_connected', {
                  provider: 'google',
                  source: marker === 'perfil' ? 'profile' : 'unknown',
                  success: true
                });
                global.sessionStorage?.removeItem('lombada_after_google_login');
              }
            }).catch(() => null);
          }
        }
      }
    } catch (_) {}

    return response;
  };

  global.document.addEventListener('submit', event => {
    if (event.target?.id !== 'searchForm') return;
    const query = global.document.querySelector('#q')?.value?.trim() || '';
    const hasFilters = Boolean(
      global.document.querySelector('#activeSearchFilters')?.children.length ||
      global.document.querySelector('#searchFiltersButton')?.classList.contains('has-active-filter')
    );
    if (query.length < 2 && !hasFilters) return;
    emit('search_submitted', {
      source: 'home',
      has_filters: hasFilters,
      result_state: 'submitted'
    });
  }, true);

  global.document.addEventListener('click', event => {
    const target = event.target instanceof Element ? event.target : event.target?.parentElement;
    if (!target) return;

    const bookTarget = target.closest(
      '.book, .catalog-list-item, .shelf-row, .reading-now-card, .diary-book-row, .work-title-link, [data-work-action="choose-edition"]'
    );
    if (bookTarget) {
      emit('book_opened', {
        source: sourceFromElement(bookTarget),
        has_cover: Boolean(bookTarget.querySelector?.('img, .cover, .shelf-cover, .diary-book-cover'))
      });
    }

    const shareTarget = target.closest(
      '[onclick*="compartilhar"], [onclick*="baixarCard"], [onclick*="copiarLink"], .btn-share, .btn-share-card, .retro-share'
    );
    if (!shareTarget) return;
    const action = `${shareTarget.getAttribute('onclick') || ''} ${shareTarget.className || ''}`.toLowerCase();
    const shareType = action.includes('baixar') ? 'download' : (action.includes('copiar') ? 'copy_link' : 'native');
    let source = sourceFromElement(shareTarget);
    if (shareTarget.closest('#modal')) source = 'reading';
    else if (shareTarget.closest('#retroModal')) source = 'recap';
    else if (!['shelf', 'profile'].includes(source)) source = 'unknown';
    emit('share_started', { source, share_type: shareType });
  }, true);
})(window);
