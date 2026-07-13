/* Ajuste de posição do feedback pós-`Li mais`.

   O componente continua sendo criado por activation-events.js. Este módulo é
   carregado somente com `progress_feedback` e aplica a posição de notificação
   no topo, respeitando a área segura do aparelho. `!important` é intencional:
   os estilos-base do feedback só são injetados quando a primeira sessão é
   salva e, portanto, podem entrar no DOM depois deste override.
*/
(function progressFeedbackTopBootstrap(global) {
  'use strict';

  if (global.document.querySelector('[data-progress-feedback-top-styles]')) return;

  const style = global.document.createElement('style');
  style.dataset.progressFeedbackTopStyles = '1';
  style.textContent = `
    .progress-feedback{
      top:calc(12px + env(safe-area-inset-top))!important;
      bottom:auto!important;
      transform:translateY(-18px)!important;
    }
    .progress-feedback.show{
      transform:translateY(0)!important;
    }
    @media(max-width:520px){
      .progress-feedback{
        top:calc(10px + env(safe-area-inset-top))!important;
        bottom:auto!important;
      }
    }
    @media(prefers-reduced-motion:reduce){
      .progress-feedback,
      .progress-feedback.show{
        transform:none!important;
      }
    }
  `;
  global.document.head.appendChild(style);
})(window);
