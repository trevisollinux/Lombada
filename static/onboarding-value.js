/* Ajustes isolados do onboarding de primeiro valor.

   Carregado depois de app.js e ux-fixes.js. Só altera o valor inicial do status
   enquanto a navegação atual tiver sido iniciada pelo CTA do onboarding. */
(function onboardingValueStatusBootstrap(global) {
  'use strict';

  const MARKER = 'lombada_onboarding_value';
  const originalOptions = global.opcoesStatusHTML;
  if (typeof originalOptions !== 'function') return;

  function active() {
    try {
      return global.sessionStorage?.getItem(MARKER) === 'active' &&
        global.LombadaFeatures?.isEnabled?.('onboarding_value') === true;
    } catch (_) {
      return false;
    }
  }

  global.opcoesStatusHTML = function onboardingStatusOptions(selected) {
    const initial = active() && selected === 'Lido' ? 'Lendo' : selected;
    return originalOptions(initial);
  };
})(window);
