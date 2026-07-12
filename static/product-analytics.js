/* Cliente mínimo de eventos de produto do Lombada.

   Não é carregado pelo HTML atual. A instrumentação futura deverá carregar
   feature-flags.js antes deste arquivo. Nenhum método lança erro para o fluxo
   chamador e somente propriedades estruturais allowlisted entram na fila. */
(function productAnalyticsBootstrap(global) {
  'use strict';

  const EVENT_PROPERTIES = Object.freeze({
    app_opened: ['source', 'locale', 'standalone'],
    search_submitted: ['source', 'has_filters', 'result_state'],
    book_opened: ['source', 'has_cover'],
    reading_created: ['source', 'status', 'has_rating', 'public'],
    reading_updated: ['source', 'status', 'has_rating', 'public'],
    progress_logged: ['source', 'progress_type', 'public'],
    share_started: ['source', 'share_type', 'success'],
    profile_connected: ['provider', 'source', 'success']
  });

  const queue = [];
  let flushing = false;
  const MAX_BATCH_SIZE = 10;

  function enabled() {
    return Boolean(
      global.LombadaFeatures &&
      global.LombadaFeatures.isEnabled &&
      global.LombadaFeatures.isEnabled('product_analytics')
    );
  }

  function eventId() {
    try {
      if (global.crypto && typeof global.crypto.randomUUID === 'function') {
        return global.crypto.randomUUID();
      }
    } catch (_) {}
    return `evt_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 14)}`;
  }

  function sanitizeProperties(eventName, properties) {
    const allowed = EVENT_PROPERTIES[eventName];
    if (!allowed || !properties || typeof properties !== 'object' || Array.isArray(properties)) {
      return {};
    }
    const clean = {};
    allowed.forEach(key => {
      const value = properties[key];
      if (typeof value === 'boolean' || typeof value === 'string') clean[key] = value;
    });
    return clean;
  }

  function track(eventName, properties = {}) {
    try {
      if (!enabled() || !Object.prototype.hasOwnProperty.call(EVENT_PROPERTIES, eventName)) return false;
      queue.push({
        event: eventName,
        properties: sanitizeProperties(eventName, properties),
        client_event_id: eventId()
      });
      if (queue.length >= MAX_BATCH_SIZE) void flush();
      return true;
    } catch (_) {
      return false;
    }
  }

  async function flush() {
    if (flushing || !enabled() || queue.length === 0) return false;
    flushing = true;
    const events = queue.splice(0, MAX_BATCH_SIZE);
    try {
      const response = await global.fetch('/api/events', {
        method: 'POST',
        credentials: 'same-origin',
        cache: 'no-store',
        keepalive: true,
        headers: {
          Accept: 'application/json',
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ events })
      });
      if (!response.ok && response.status !== 429) throw new Error(`analytics HTTP ${response.status}`);
      return response.ok;
    } catch (_) {
      // Analytics nunca deve bloquear a ação principal nem criar retry infinito.
      return false;
    } finally {
      flushing = false;
      if (enabled() && queue.length >= MAX_BATCH_SIZE) void flush();
    }
  }

  function size() {
    return queue.length;
  }

  global.LombadaAnalytics = Object.freeze({ track, flush, size });
})(window);
