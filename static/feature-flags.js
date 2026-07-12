/* Feature flags públicas do Lombada.

   Falhas de rede mantêm todas as flags desligadas e nunca bloqueiam o app. */
(function featureFlagsBootstrap(global) {
  'use strict';

  const NAMES = Object.freeze([
    'home_ritual',
    'product_analytics',
    'progress_sessions',
    'progress_feedback',
    'onboarding_value',
    'favorite_books',
    'period_recaps',
    'literary_reactions',
    'progress_comments',
    'weekly_rhythm',
    'editorial_achievements',
    'reading_twin',
    'push_notifications'
  ]);

  const state = Object.create(null);
  NAMES.forEach(name => { state[name] = false; });

  function snapshot() {
    return Object.freeze(Object.fromEntries(NAMES.map(name => [name, state[name] === true])));
  }

  function isEnabled(name) {
    return NAMES.includes(name) && state[name] === true;
  }

  async function refresh() {
    try {
      const response = await global.fetch('/api/features', {
        method: 'GET',
        credentials: 'same-origin',
        cache: 'no-store',
        headers: { Accept: 'application/json' }
      });
      if (!response.ok) throw new Error(`feature flags HTTP ${response.status}`);

      const payload = await response.json();
      const received = payload && typeof payload.features === 'object'
        ? payload.features
        : {};

      NAMES.forEach(name => {
        state[name] = received[name] === true;
      });
    } catch (_) {
      NAMES.forEach(name => { state[name] = false; });
    }
    return snapshot();
  }

  function installOnboardingStatusDefault() {
    const originalOptions = global.opcoesStatusHTML;
    if (typeof originalOptions !== 'function') return;
    const marker = 'lombada_onboarding_value';

    global.opcoesStatusHTML = function onboardingStatusOptions(selected) {
      let onboardingActive = false;
      try {
        onboardingActive = global.sessionStorage?.getItem(marker) === 'active' &&
          isEnabled('onboarding_value');
      } catch (_) {}
      const initial = onboardingActive && selected === 'Lido' ? 'Lendo' : selected;
      return originalOptions(initial);
    };
  }

  const api = Object.freeze({
    names: NAMES,
    isEnabled,
    snapshot,
    refresh,
    ready: refresh()
  });

  global.LombadaFeatures = api;
  global.document.addEventListener('DOMContentLoaded', installOnboardingStatusDefault, { once: true });
})(window);
