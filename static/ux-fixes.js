/* Ajustes pontuais de UX carregados depois de app.js.
   Mantidos isolados para evitar uma substituição integral do arquivo principal. */
(() => {
  function normalizarAutorCard(valor) {
    let texto = String(valor || '').replace(/\s+/g, ' ').trim();
    texto = texto.replace(/^\s*(?:autor(?:a)?|author)\s*:\s*/i, '');

    // Algumas fontes devolvem autor + outros campos catalográficos na mesma string.
    // No card, esses campos já aparecem no rodapé; portanto, mantemos apenas o autor.
    const marcador = texto.search(/\s+(?:autor(?:a)?|author|tradutor(?:a)?|translator|editora|publisher|ano(?:\s+da\s+edi[cç][aã]o)?|year)\s*:/i);
    if (marcador > 0) texto = texto.slice(0, marcador).trim();
    return texto;
  }

  function linhasCanvas(ctx, valor, larguraMaxima, limite) {
    const texto = String(valor || '').replace(/\s+/g, ' ').trim();
    if (!texto) return [];

    const palavras = texto.split(' ');
    const linhas = [];
    let atual = '';
    let truncado = false;

    for (let i = 0; i < palavras.length; i += 1) {
      const palavra = palavras[i];
      const teste = atual ? `${atual} ${palavra}` : palavra;

      if (!atual || ctx.measureText(teste).width <= larguraMaxima) {
        atual = teste;
        continue;
      }

      linhas.push(atual);
      atual = palavra;
      if (linhas.length === limite) {
        truncado = true;
        break;
      }
    }

    if (linhas.length < limite && atual) linhas.push(atual);
    if (linhas.length > limite) linhas.length = limite;

    const consumido = linhas.join(' ').split(' ').length;
    if (consumido < palavras.length) truncado = true;

    if (truncado && linhas.length) {
      let ultima = linhas[linhas.length - 1].replace(/[\s.,;:!?-]+$/g, '');
      while (ultima && ctx.measureText(`${ultima}…`).width > larguraMaxima) {
        ultima = ultima.slice(0, -1).trimEnd();
      }
      linhas[linhas.length - 1] = `${ultima || ''}…`;
    }

    return linhas;
  }

  function desenharLinhas(ctx, linhas, x, y, alturaLinha) {
    linhas.forEach((linha, indice) => ctx.fillText(linha, x, y + indice * alturaLinha));
    return linhas.length ? y + (linhas.length - 1) * alturaLinha : y;
  }

  function desenharDominioCard(ctx, largura, y, margem = 110, tamanho = 40) {
    const paleta = cardPalette();
    ctx.save();
    ctx.textAlign = 'right';
    ctx.textBaseline = 'alphabetic';
    ctx.fillStyle = paleta.gold;
    ctx.font = `600 italic ${tamanho}px Fraunces, serif`;
    ctx.fillText('lombada.app', largura - margem, y);
    ctx.restore();
  }

  const renderShareCardCanvasOriginal = window.renderShareCardCanvas;
  if (typeof renderShareCardCanvasOriginal === 'function') {
    window.renderShareCardCanvas = function renderShareCardCanvasComAutorLimpo(livro, opcoes = {}) {
      const livroCard = livro ? { ...livro, autor: normalizarAutorCard(livro.autor) } : livro;
      return renderShareCardCanvasOriginal(livroCard, opcoes);
    };
  }

  // Evita que título/autor ultrapassem a largura do card. O autor pode ocupar
  // duas linhas, e textos maiores recebem reticências em vez de serem cortados.
  window.drawBookInfo = function drawBookInfoAjustado(ctx, livro, largura, altura, capaY, capaAltura) {
    const paleta = cardPalette();
    let y = capaY + capaAltura + 118;
    ctx.textAlign = 'left';
    ctx.textBaseline = 'alphabetic';

    ctx.fillStyle = paleta.text;
    ctx.font = '500 italic 80px Fraunces, serif';
    const titulo = linhasCanvas(ctx, livro.titulo || '', largura - 220, 2);
    y = desenharLinhas(ctx, titulo, 110, y, 88);

    y += 68;
    ctx.fillStyle = paleta.muted;
    ctx.font = 'italic 46px Spectral, serif';
    const autor = linhasCanvas(ctx, normalizarAutorCard(livro.autor), largura - 220, 2);
    y = desenharLinhas(ctx, autor, 110, y, 56);
    return y;
  };

  // O rodapé também passa a quebrar em até duas linhas, sem escapar da imagem.
  // A assinatura fixa do produto fica à direita; handles pessoais não entram no card.
  window.drawFooter = function drawFooterAjustado(ctx, livro, largura, altura) {
    const paleta = cardPalette();
    const metadados = [
      livro.tradutor ? `${t('translator_abbr')} ${livro.tradutor}` : null,
      livro.editora || null,
      livro.ano_edicao || livro.ano || null,
    ].filter(Boolean).join('   ·   ');

    ctx.textAlign = 'left';
    ctx.textBaseline = 'alphabetic';
    ctx.fillStyle = paleta.muted;
    ctx.font = "400 28px 'Space Mono', monospace";

    const linhas = linhasCanvas(ctx, metadados, largura - 220, 2);
    const marcaY = altura - 52;
    const metaUltimaY = marcaY - 64;
    const metaPrimeiraY = metaUltimaY - Math.max(0, linhas.length - 1) * 34;
    const regraY = metaPrimeiraY - 44;

    ctx.strokeStyle = paleta.rule;
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.moveTo(110, regraY);
    ctx.lineTo(largura - 110, regraY);
    ctx.stroke();

    desenharLinhas(ctx, linhas, 110, metaPrimeiraY, 34);
    desenharDominioCard(ctx, largura, marcaY, 110, 40);
  };

  // Críticas e entradas de diário usam layouts próprios no app.js, então também
  // substituímos apenas a assinatura final nesses dois formatos.
  const drawReviewShareCardTextOriginal = window.drawReviewShareCardText;
  if (typeof drawReviewShareCardTextOriginal === 'function') {
    window.drawReviewShareCardText = function drawReviewShareCardTextComDominio(ctx, livro, largura, altura, capaY, capaAltura) {
      drawReviewShareCardTextOriginal(ctx, livro, largura, altura, capaY, capaAltura);
      const paleta = cardPalette();
      ctx.save();
      ctx.fillStyle = paleta.bg;
      ctx.fillRect(70, altura - 125, largura - 140, 110);
      ctx.restore();
      desenharDominioCard(ctx, largura, altura - 48, 96, 36);
    };
  }

  const drawDiaryShareCardTextOriginal = window.drawDiaryShareCardText;
  if (typeof drawDiaryShareCardTextOriginal === 'function') {
    window.drawDiaryShareCardText = function drawDiaryShareCardTextComDominio(ctx, livro, largura, altura, capaY, capaAltura) {
      drawDiaryShareCardTextOriginal(ctx, livro, largura, altura, capaY, capaAltura);
      const paleta = cardPalette();
      ctx.save();
      ctx.fillStyle = paleta.bg;
      ctx.fillRect(70, altura - 125, largura - 140, 110);
      ctx.restore();
      desenharDominioCard(ctx, largura, altura - 48, 96, 36);
    };
  }

  window.abrirPassoProgressoOnboarding = function abrirPassoProgressoOnboarding() {
    const lendo = typeof leiturasEmAndamento === 'function' ? leiturasEmAndamento() : [];

    if (lendo.length === 1) {
      abrirDiarioLeitura(lendo[0].idx);
      return;
    }

    if (lendo.length > 1) {
      abrirAcoesLeitura();
      setTimeout(() => document.querySelector('#quickReadingSelect')?.focus?.(), 60);
      return;
    }

    irPara('buscar');
    setTimeout(() => document.querySelector('#q')?.focus?.(), 120);
    if (typeof toast === 'function') toast(t('quick_actions_hint_empty'));
  };

  window.onboardingChecklistHTML = function onboardingChecklistInterativo(passos) {
    const { registrou, atualizouProgresso, conheceuPerfil } = passos;
    const concluidos = [registrou, atualizouProgresso, conheceuPerfil].filter(Boolean).length;

    const item = (feito, titulo, dica, acao = '') => {
      const interativo = !feito && acao;
      const tag = interativo ? 'button' : 'div';
      const atributos = interativo ? ` type="button" onclick="${acao}"` : '';
      const seta = interativo ? '<span class="onboarding-check-arrow" aria-hidden="true">›</span>' : '';
      return `<${tag} class="onboarding-check-item ${feito ? 'done' : ''} ${interativo ? 'is-actionable' : ''}"${atributos}>
        <div class="onboarding-check-mark">${feito ? '✓' : ''}</div>
        <div class="onboarding-check-copy"><b>${esc(titulo)}</b>${dica ? `<span>${esc(dica)}</span>` : ''}</div>
        ${seta}
      </${tag}>`;
    };

    return `<div class="onboarding-checklist-wrap">
      <div class="onboarding-checklist-head">
        <div class="onboarding-progress">${t('onboarding_step_progress', { done: concluidos })}</div>
        <button type="button" class="onboarding-close" onclick="dispensarOnboarding()" title="${esc(t('onboarding_dismiss'))}" aria-label="${esc(t('onboarding_dismiss'))}">&times;</button>
      </div>
      <div class="onboarding-checklist">
        ${item(registrou, t('onboarding_step1_title'))}
        ${item(atualizouProgresso, t('onboarding_step2_title'), atualizouProgresso ? '' : t('onboarding_step2_hint'), 'abrirPassoProgressoOnboarding()')}
        ${item(conheceuPerfil, t('onboarding_step3_title'), conheceuPerfil ? '' : t('onboarding_step3_hint'), "irPara('perfil')")}
      </div>
    </div>`;
  };

  const estilo = document.createElement('style');
  estilo.dataset.lombadaUxFixes = '1';
  estilo.textContent = `
    .onboarding-check-item.is-actionable{
      width:100%;text-align:left;display:grid;grid-template-columns:auto minmax(0,1fr) auto;
      align-items:center;column-gap:14px;border-radius:12px;transition:background .15s ease,transform .15s ease;
    }
    .onboarding-check-item.is-actionable:hover,
    .onboarding-check-item.is-actionable:focus-visible{background:color-mix(in srgb,var(--ink),transparent 94%)}
    .onboarding-check-item.is-actionable:active{transform:translateY(1px)}
    .onboarding-check-arrow{font-family:"Fraunces",serif;font-size:31px;line-height:1;color:var(--dim);padding-left:8px}
    .theme-dark .onboarding-check-item.is-actionable:hover,
    .theme-dark .onboarding-check-item.is-actionable:focus-visible{background:rgba(255,255,255,.045)}
  `;
  document.head.appendChild(estilo);

  try { if (typeof renderOnboarding === 'function') renderOnboarding(); } catch (_) {}
})();