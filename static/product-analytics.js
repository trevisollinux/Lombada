/* Cliente mínimo de eventos de produto do Lombada.

   Carregado somente pela instrumentação oficial. Nenhum método lança erro para
   o fluxo chamador e somente propriedades estruturais allowlisted entram na fila. */
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
  let flushTimer = null;
  const MAX_BATCH_SIZE = 10;
  const FLUSH_DELAY_MS = 1200;

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

  function scheduleFlush() {
    if (flushTimer !== null || !enabled()) return;
    flushTimer = global.setTimeout(() => {
      flushTimer = null;
      void flush();
    }, FLUSH_DELAY_MS);
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
      else scheduleFlush();
      return true;
    } catch (_) {
      return false;
    }
  }

  async function flush() {
    if (flushTimer !== null) {
      global.clearTimeout(flushTimer);
      flushTimer = null;
    }
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
      else if (enabled() && queue.length > 0) scheduleFlush();
    }
  }

  function size() {
    return queue.length;
  }

  global.document?.addEventListener('visibilitychange', () => {
    if (global.document.visibilityState === 'hidden') void flush();
  });
  global.addEventListener?.('pagehide', () => { void flush(); });

  global.LombadaAnalytics = Object.freeze({ track, flush, size });
})(window);
