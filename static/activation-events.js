/* Instrumentação estrutural do funil de ativação e feedback pós-sessão.

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
  let progressFeedbackTimer = null;
  let suppressProgressToastUntil = 0;
  const pending = [];
  const MAX_PENDING = 20;
  const ONBOARDING_VALUE_MARKER = 'lombada_onboarding_value';
  const PROGRESS_FEEDBACK_ID = 'lombadaProgressFeedback';
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

  function onboardingValueActive() {
    try {
      return global.sessionStorage?.getItem(ONBOARDING_VALUE_MARKER) === 'active';
    } catch (_) {
      return false;
    }
  }

  function clearOnboardingValueMarker() {
    try { global.sessionStorage?.removeItem(ONBOARDING_VALUE_MARKER); } catch (_) {}
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

  function progressFeedbackEnabled() {
    return Boolean(features.isEnabled?.('progress_feedback'));
  }

  function finiteNumber(value) {
    const number = Number(value);
    return Number.isFinite(number) ? number : null;
  }

  function exactPage(entry) {
    const value = finiteNumber(entry?.pagina);
    return value !== null && Number.isInteger(value) && value > 0 ? value : null;
  }

  function exactPercent(entry) {
    const value = finiteNumber(entry?.porcentagem);
    return value !== null && value >= 0 && value <= 100 ? value : null;
  }

  function orderedEntriesForReading(readingId) {
    try {
      if (typeof diarioEntradas === 'undefined' || !Array.isArray(diarioEntradas)) return [];
      return diarioEntradas
        .filter(entry => String(entry?.leitura_id) === String(readingId))
        .slice()
        .sort((a, b) => {
          const timeA = new Date(a?.created_at || 0).getTime() || 0;
          const timeB = new Date(b?.created_at || 0).getTime() || 0;
          return timeA - timeB || (Number(a?.id) || 0) - (Number(b?.id) || 0);
        });
    } catch (_) {
      return [];
    }
  }

  function totalPagesForReading(readingId) {
    try {
      if (typeof prateleira === 'undefined' || !Array.isArray(prateleira)) return 0;
      const reading = prateleira.find(item => String(item?.leitura_id) === String(readingId));
      const total = Number(reading?.paginas);
      return Number.isInteger(total) && total > 0 ? total : 0;
    } catch (_) {
      return 0;
    }
  }

  function maxPositiveDelta(values) {
    let max = 0;
    for (let index = 1; index < values.length; index += 1) {
      const delta = values[index] - values[index - 1];
      if (delta > max) max = delta;
    }
    return max;
  }

  function progressSnapshot(method, path) {
    if (method !== 'POST') return null;
    const match = path.match(/^\/api\/leitura\/(\d+)\/diario$/);
    if (!match) return null;

    const readingId = match[1];
    const entries = orderedEntriesForReading(readingId);
    const pages = entries.map(exactPage).filter(value => value !== null);
    const percentages = entries.map(exactPercent).filter(value => value !== null);

    return {
      readingId,
      previousPage: pages.length ? pages[pages.length - 1] : null,
      previousPercent: percentages.length ? percentages[percentages.length - 1] : null,
      maxPageDelta: maxPositiveDelta(pages),
      maxPercentDelta: maxPositiveDelta(percentages),
      totalPages: totalPagesForReading(readingId)
    };
  }

  function progressSource(body) {
    if (onboardingValueActive()) return 'onboarding';
    return body.source === 'quick_action' ? 'quick_action' : 'diary';
  }

  function progressInsight(snapshot, body) {
    if (!snapshot || !progressFeedbackEnabled()) return null;
    const type = progressType(body);
    const source = progressSource(body);

    if (type === 'page') {
      const current = finiteNumber(body.pagina);
      if (current === null || !Number.isInteger(current) || current <= 0) return null;
      const previous = snapshot.previousPage;
      const delta = previous === null ? null : current - previous;
      const total = snapshot.totalPages;

      if (total > 0 && current >= total) {
        return { insightType: 'completed', metric: 'page', current, total, source };
      }
      if (delta !== null && delta > 0) {
        if (snapshot.maxPageDelta > 0 && delta > snapshot.maxPageDelta) {
          return { insightType: 'best_session', metric: 'page', current, delta, total, source };
        }
        return { insightType: 'page_delta', metric: 'page', current, delta, total, source };
      }
      if (delta !== null && delta <= 0) {
        return { insightType: 'correction', metric: 'page', current, total, source };
      }
      if (total > 0) {
        return {
          insightType: 'percent_reached',
          metric: 'page',
          current,
          percent: Math.max(0, Math.min(100, Math.round(current / total * 100))),
          total,
          source
        };
      }
      return { insightType: 'page_reached', metric: 'page', current, total, source };
    }

    if (type === 'percentage') {
      const current = finiteNumber(body.porcentagem);
      if (current === null || current < 0 || current > 100) return null;
      const previous = snapshot.previousPercent;
      const delta = previous === null ? null : current - previous;

      if (current >= 100) {
        return { insightType: 'completed', metric: 'percentage', current, source };
      }
      if (delta !== null && delta > 0) {
        if (snapshot.maxPercentDelta > 0 && delta > snapshot.maxPercentDelta) {
          return { insightType: 'best_session', metric: 'percentage', current, delta, source };
        }
        return { insightType: 'percent_delta', metric: 'percentage', current, delta, source };
      }
      if (delta !== null && delta <= 0) {
        return { insightType: 'correction', metric: 'percentage', current, source };
      }
      return { insightType: 'percent_reached', metric: 'percentage', current, percent: current, source };
    }

    if (type === 'chapter') {
      return { insightType: 'chapter', metric: 'chapter', source };
    }

    return { insightType: 'session', metric: 'free', source };
  }

  function localeCode() {
    const raw = String(global.document.documentElement.lang || 'pt-BR').toLowerCase();
    if (raw.startsWith('en')) return 'en';
    if (raw.startsWith('es')) return 'es';
    return 'pt-BR';
  }

  function numberText(value, locale) {
    try { return Number(value).toLocaleString(locale); }
    catch (_) { return String(value); }
  }

  function progressFeedbackCopy(insight) {
    const locale = localeCode();
    const number = value => numberText(value, locale);
    const isPage = insight.metric === 'page';

    if (locale === 'en') {
      const common = { kicker: 'progress saved', action: 'view diary', close: 'close progress feedback' };
      if (insight.insightType === 'completed') return { ...common, title: 'You reached 100%.', detail: 'Mark it as read whenever it feels right.' };
      if (insight.insightType === 'best_session') return { ...common, title: 'Your biggest session in this book.', detail: isPage ? `+${number(insight.delta)} pages — now on page ${number(insight.current)}.` : `+${number(insight.delta)} percentage points — now at ${number(insight.current)}%.` };
      if (insight.insightType === 'page_delta') return { ...common, title: `+${number(insight.delta)} pages in this session.`, detail: `You reached page ${number(insight.current)}.` };
      if (insight.insightType === 'percent_delta') return { ...common, title: `+${number(insight.delta)} percentage points.`, detail: `You are now at ${number(insight.current)}%.` };
      if (insight.insightType === 'percent_reached') return { ...common, title: `You reached ${number(insight.percent)}%.`, detail: isPage ? `Progress saved on page ${number(insight.current)}.` : 'Your reading history is up to date.' };
      if (insight.insightType === 'page_reached') return { ...common, title: `Progress saved on page ${number(insight.current)}.`, detail: 'Your reading history is up to date.' };
      if (insight.insightType === 'chapter') return { ...common, title: 'Chapter saved.', detail: 'Your reading history is up to date.' };
      if (insight.insightType === 'correction') return { ...common, title: 'Progress updated.', detail: 'The correction was saved to your history.' };
      return { ...common, title: 'Reading session saved.', detail: 'Another memory kept in your diary.' };
    }

    if (locale === 'es') {
      const common = { kicker: 'progreso guardado', action: 'ver diario', close: 'cerrar respuesta de progreso' };
      if (insight.insightType === 'completed') return { ...common, title: 'Llegaste al 100%.', detail: 'Márcalo como leído cuando tenga sentido para ti.' };
      if (insight.insightType === 'best_session') return { ...common, title: 'Tu mayor sesión en este libro.', detail: isPage ? `+${number(insight.delta)} páginas — llegaste a la página ${number(insight.current)}.` : `+${number(insight.delta)} puntos porcentuales — llegaste al ${number(insight.current)}%.` };
      if (insight.insightType === 'page_delta') return { ...common, title: `+${number(insight.delta)} páginas en esta sesión.`, detail: `Llegaste a la página ${number(insight.current)}.` };
      if (insight.insightType === 'percent_delta') return { ...common, title: `+${number(insight.delta)} puntos porcentuales.`, detail: `Ahora estás en el ${number(insight.current)}%.` };
      if (insight.insightType === 'percent_reached') return { ...common, title: `Llegaste al ${number(insight.percent)}%.`, detail: isPage ? `Progreso guardado en la página ${number(insight.current)}.` : 'Tu historial de lectura está actualizado.' };
      if (insight.insightType === 'page_reached') return { ...common, title: `Progreso guardado en la página ${number(insight.current)}.`, detail: 'Tu historial de lectura está actualizado.' };
      if (insight.insightType === 'chapter') return { ...common, title: 'Capítulo guardado.', detail: 'Tu historial de lectura está actualizado.' };
      if (insight.insightType === 'correction') return { ...common, title: 'Progreso actualizado.', detail: 'La corrección quedó guardada en tu historial.' };
      return { ...common, title: 'Sesión de lectura guardada.', detail: 'Otro recuerdo guardado en tu diario.' };
    }

    const common = { kicker: 'progresso registrado', action: 'ver diário', close: 'fechar retorno de progresso' };
    if (insight.insightType === 'completed') return { ...common, title: 'Você chegou a 100%.', detail: 'Marque como lido quando fizer sentido.' };
    if (insight.insightType === 'best_session') return { ...common, title: 'Sua maior sessão nesta leitura.', detail: isPage ? `+${number(insight.delta)} páginas — você chegou à página ${number(insight.current)}.` : `+${number(insight.delta)} pontos percentuais — você chegou a ${number(insight.current)}%.` };
    if (insight.insightType === 'page_delta') return { ...common, title: `+${number(insight.delta)} páginas nesta sessão.`, detail: `Você chegou à página ${number(insight.current)}.` };
    if (insight.insightType === 'percent_delta') return { ...common, title: `+${number(insight.delta)} pontos percentuais.`, detail: `Agora você está em ${number(insight.current)}%.` };
    if (insight.insightType === 'percent_reached') return { ...common, title: `Você chegou a ${number(insight.percent)}%.`, detail: isPage ? `Progresso salvo na página ${number(insight.current)}.` : 'Seu histórico de leitura está atualizado.' };
    if (insight.insightType === 'page_reached') return { ...common, title: `Progresso salvo na página ${number(insight.current)}.`, detail: 'Seu histórico de leitura está atualizado.' };
    if (insight.insightType === 'chapter') return { ...common, title: 'Capítulo registrado.', detail: 'Seu histórico de leitura foi atualizado.' };
    if (insight.insightType === 'correction') return { ...common, title: 'Progresso atualizado.', detail: 'A correção ficou salva no seu histórico.' };
    return { ...common, title: 'Sessão de leitura registrada.', detail: 'Mais uma memória guardada no seu diário.' };
  }

  function ensureProgressFeedbackStyles() {
    if (global.document.querySelector('[data-progress-feedback-styles]')) return;
    const style = global.document.createElement('style');
    style.dataset.progressFeedbackStyles = '1';
    style.textContent = `
      .progress-feedback{position:fixed;z-index:2800;left:max(12px,env(safe-area-inset-left));right:max(12px,env(safe-area-inset-right));bottom:calc(78px + env(safe-area-inset-bottom));max-width:560px;margin:0 auto;display:grid;grid-template-columns:auto minmax(0,1fr) auto;align-items:center;gap:14px;padding:16px 14px 16px 16px;border:1px solid color-mix(in srgb,var(--gold),transparent 48%);border-radius:18px;background:color-mix(in srgb,var(--paper),var(--gold) 5%);color:var(--ink);box-shadow:0 18px 55px rgba(20,17,14,.2);opacity:0;transform:translateY(18px);transition:opacity .2s ease,transform .2s ease}
      .progress-feedback.show{opacity:1;transform:translateY(0)}
      .progress-feedback-mark{display:grid;place-items:center;width:40px;height:40px;border-radius:50%;background:color-mix(in srgb,var(--gold),transparent 82%);color:var(--gold);font:700 20px/1 "Space Mono",monospace}
      .progress-feedback-copy{min-width:0}
      .progress-feedback-kicker{margin-bottom:3px;color:var(--gold);font:700 10px/1.3 "Space Mono",monospace;letter-spacing:.08em;text-transform:uppercase}
      .progress-feedback-title{font:500 18px/1.2 "Fraunces",serif;color:var(--ink)}
      .progress-feedback-detail{margin-top:3px;color:var(--dim);font:400 13px/1.35 "Spectral",serif}
      .progress-feedback-actions{display:flex;align-items:center;gap:4px}
      .progress-feedback-open,.progress-feedback-close{border:0;background:transparent;color:var(--dim);border-radius:999px}
      .progress-feedback-open{padding:9px 10px;color:var(--gold);font:700 10px/1.2 "Space Mono",monospace;text-transform:uppercase;white-space:nowrap}
      .progress-feedback-close{display:grid;place-items:center;width:34px;height:34px;font-size:22px;line-height:1}
      .progress-feedback-open:hover,.progress-feedback-open:focus-visible,.progress-feedback-close:hover,.progress-feedback-close:focus-visible{background:color-mix(in srgb,var(--ink),transparent 93%)}
      .theme-dark .progress-feedback{background:color-mix(in srgb,var(--paper),#fff 4%);box-shadow:0 20px 60px rgba(0,0,0,.38)}
      @media(max-width:520px){.progress-feedback{grid-template-columns:auto minmax(0,1fr);bottom:calc(72px + env(safe-area-inset-bottom));padding:14px}.progress-feedback-actions{grid-column:2;justify-content:flex-start}.progress-feedback-open{padding-left:0}.progress-feedback-close{position:absolute;right:7px;top:7px}.progress-feedback-copy{padding-right:24px}}
      @media(prefers-reduced-motion:reduce){.progress-feedback{transition:none;transform:none}.progress-feedback.show{transform:none}}
    `;
    global.document.head.appendChild(style);
  }

  function closeProgressFeedback(action = 'closed') {
    const element = global.document.getElementById(PROGRESS_FEEDBACK_ID);
    if (!element) return;
    if (progressFeedbackTimer !== null) {
      global.clearTimeout(progressFeedbackTimer);
      progressFeedbackTimer = null;
    }
    const properties = {
      source: element.dataset.source || 'unknown',
      insight_type: element.dataset.insightType || 'session',
      action
    };
    emit('progress_feedback', properties);
    element.classList.remove('show');
    global.setTimeout(() => element.remove(), 180);
  }

  function openProgressDiary() {
    closeProgressFeedback('open_diary');
    try {
      if (typeof global.irPara === 'function') global.irPara('estante', { subaba: 'diario' });
    } catch (_) {}
  }

  function showProgressFeedback(insight) {
    if (!insight || !progressFeedbackEnabled() || global.document.visibilityState === 'hidden') return false;
    ensureProgressFeedbackStyles();
    const old = global.document.getElementById(PROGRESS_FEEDBACK_ID);
    if (old) old.remove();
    if (progressFeedbackTimer !== null) global.clearTimeout(progressFeedbackTimer);

    const copy = progressFeedbackCopy(insight);
    const element = global.document.createElement('aside');
    element.id = PROGRESS_FEEDBACK_ID;
    element.className = 'progress-feedback';
    element.setAttribute('role', 'status');
    element.setAttribute('aria-live', 'polite');
    element.dataset.source = insight.source;
    element.dataset.insightType = insight.insightType;

    const mark = global.document.createElement('div');
    mark.className = 'progress-feedback-mark';
    mark.setAttribute('aria-hidden', 'true');
    mark.textContent = '↗';

    const copyBox = global.document.createElement('div');
    copyBox.className = 'progress-feedback-copy';
    const kicker = global.document.createElement('div');
    kicker.className = 'progress-feedback-kicker';
    kicker.textContent = copy.kicker;
    const title = global.document.createElement('div');
    title.className = 'progress-feedback-title';
    title.textContent = copy.title;
    const detail = global.document.createElement('div');
    detail.className = 'progress-feedback-detail';
    detail.textContent = copy.detail;
    copyBox.append(kicker, title, detail);

    const actions = global.document.createElement('div');
    actions.className = 'progress-feedback-actions';
    const open = global.document.createElement('button');
    open.type = 'button';
    open.className = 'progress-feedback-open';
    open.textContent = copy.action;
    open.addEventListener('click', openProgressDiary);
    const close = global.document.createElement('button');
    close.type = 'button';
    close.className = 'progress-feedback-close';
    close.setAttribute('aria-label', copy.close);
    close.textContent = '×';
    close.addEventListener('click', () => closeProgressFeedback('closed'));
    actions.append(open, close);

    element.append(mark, copyBox, actions);
    global.document.body.appendChild(element);
    global.requestAnimationFrame(() => element.classList.add('show'));
    emit('progress_feedback', {
      source: insight.source,
      insight_type: insight.insightType,
      action: 'viewed'
    });

    try {
      const reduceMotion = global.matchMedia?.('(prefers-reduced-motion: reduce)')?.matches;
      if (!reduceMotion && typeof global.navigator?.vibrate === 'function') global.navigator.vibrate(18);
    } catch (_) {}

    progressFeedbackTimer = global.setTimeout(() => closeProgressFeedback('auto_closed'), 6500);
    return true;
  }

  function scheduleProgressFeedback(snapshot, body) {
    const insight = progressInsight(snapshot, body);
    if (!insight) return;
    suppressProgressToastUntil = Date.now() + 5000;
    global.setTimeout(() => showProgressFeedback(insight), 100);
  }

  function translatedMessage(key) {
    try {
      if (typeof global.t === 'function') return global.t(key);
      if (typeof t === 'function') return t(key);
    } catch (_) {}
    return '';
  }

  function installProgressToastBridge() {
    const originalToast = global.toast;
    if (typeof originalToast !== 'function' || originalToast.__progressFeedbackWrapped) return;
    const wrapped = function progressFeedbackAwareToast(message, ...rest) {
      if (Date.now() < suppressProgressToastUntil) {
        const progressMessages = [translatedMessage('diary_entry_saved'), translatedMessage('reading_finished_hint')].filter(Boolean);
        if (progressMessages.includes(message)) {
          suppressProgressToastUntil = 0;
          return undefined;
        }
      }
      return originalToast.call(this, message, ...rest);
    };
    wrapped.__progressFeedbackWrapped = true;
    global.toast = wrapped;
  }

  if (global.document.readyState === 'loading') {
    global.document.addEventListener('DOMContentLoaded', installProgressToastBridge, { once: true });
  } else {
    global.setTimeout(installProgressToastBridge, 0);
  }

  const originalFetch = global.fetch.bind(global);
  global.fetch = async function instrumentedFetch(input, init = {}) {
    const requestUrl = typeof input === 'string' || input instanceof URL
      ? String(input)
      : String(input?.url || '');
    const method = String(init.method || input?.method || 'GET').toUpperCase();
    const body = safeJsonBody(init);
    let path = '';
    try { path = new URL(requestUrl, global.location.href).pathname; } catch (_) {}
    const snapshot = progressSnapshot(method, path);
    const response = await originalFetch(input, init);

    try {
      if (response.ok && path !== '/api/events') {
        if (method === 'POST' && path === '/api/prateleira') {
          const source = onboardingValueActive()
            ? 'onboarding'
            : (body.source === 'quick_action' ? 'quick_action' : 'search');
          emit('reading_created', readingProperties(body, source));
          if (source === 'onboarding') clearOnboardingValueMarker();
        } else if (method === 'PATCH' && /^\/api\/prateleira\/\d+$/.test(path)) {
          emit('reading_updated', readingProperties(body, body.source === 'quick_action' ? 'quick_action' : 'detail'));
        } else if (isDiaryWrite(method, path)) {
          const source = progressSource(body);
          emit('progress_logged', {
            source,
            progress_type: progressType(body),
            public: body.publico === true
          });
          // Edições de entradas antigas continuam com o toast normal: só um novo
          // registro de sessão recebe recompensa, evitando duplicar reconhecimento.
          if (method === 'POST') scheduleProgressFeedback(snapshot, body);
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
      source: onboardingValueActive() ? 'onboarding' : 'home',
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
      const elementSource = sourceFromElement(bookTarget);
      emit('book_opened', {
        source: onboardingValueActive() && elementSource === 'search' ? 'onboarding' : elementSource,
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
