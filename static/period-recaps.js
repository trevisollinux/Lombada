/* Retrospectivas semanais e mensais.

   O módulo é carregado somente com `period_recaps`. Dados literários são usados
   apenas na tela privada e no canvas local; analytics recebe período, ação e
   estado, sem títulos, autores, páginas ou conteúdo do diário.
*/
(function periodRecapsBootstrap(global) {
  'use strict';

  const SECTION_ID = 'periodRecapSection';
  const MAX_OFFSET = 12;
  let period = 'week';
  let offset = 0;
  let recap = null;
  let loading = false;
  let error = false;
  let requestToken = 0;
  let originalRenderProfile = null;
  const viewedKeys = new Set();

  function locale() {
    const raw = String(global.document.documentElement.lang || 'pt-BR').toLowerCase();
    if (raw.startsWith('en')) return 'en';
    if (raw.startsWith('es')) return 'es';
    return 'pt-BR';
  }

  function copy() {
    if (locale() === 'en') {
      return {
        label: 'reading memory', title: 'Your reading recap', week: 'Week', month: 'Month',
        currentWeek: 'This week so far', currentMonth: 'This month so far', previous: 'Previous period', next: 'Next period',
        sessions: 'sessions', activeDays: 'active days', books: 'books touched', pages: 'pages advanced', updates: 'progress updates',
        emptyCurrent: 'This period is still blank. It begins when you register Read more.',
        emptyPast: 'No reading session was registered in this period — and that is all right.',
        loading: 'Gathering your reading memories…', error: 'I could not build this recap now.', retry: 'Try again',
        highlights: 'Books in this period', sessionOne: '1 session', sessionMany: '{count} sessions',
        pageOne: '+1 page', pageMany: '+{count} pages', lastPage: 'page {value}', lastPercent: '{value}%', lastChapter: 'chapter: {value}',
        share: 'Share recap', openDiary: 'Open diary', cardWeek: 'MY READING WEEK', cardMonth: 'MY READING MONTH',
        cardSubtitle: 'a reading memory', downloaded: 'Recap downloaded.', shareError: 'I could not create the recap card.',
        close: 'Close', periodInProgress: 'in progress', completedPeriod: 'completed period'
      };
    }
    if (locale() === 'es') {
      return {
        label: 'memoria de lectura', title: 'Tu retrospectiva de lectura', week: 'Semana', month: 'Mes',
        currentWeek: 'Tu semana hasta ahora', currentMonth: 'Tu mes hasta ahora', previous: 'Período anterior', next: 'Período siguiente',
        sessions: 'sesiones', activeDays: 'días activos', books: 'libros tocados', pages: 'páginas avanzadas', updates: 'actualizaciones',
        emptyCurrent: 'Este período todavía está en blanco. Empieza cuando registras Leí más.',
        emptyPast: 'No registraste sesiones en este período — y está bien.',
        loading: 'Reuniendo tus memorias de lectura…', error: 'No pude construir esta retrospectiva ahora.', retry: 'Intentar de nuevo',
        highlights: 'Libros de este período', sessionOne: '1 sesión', sessionMany: '{count} sesiones',
        pageOne: '+1 página', pageMany: '+{count} páginas', lastPage: 'página {value}', lastPercent: '{value}%', lastChapter: 'capítulo: {value}',
        share: 'Compartir retrospectiva', openDiary: 'Abrir diario', cardWeek: 'MI SEMANA DE LECTURA', cardMonth: 'MI MES DE LECTURA',
        cardSubtitle: 'una memoria de lectura', downloaded: 'Retrospectiva descargada.', shareError: 'No pude crear la tarjeta ahora.',
        close: 'Cerrar', periodInProgress: 'en curso', completedPeriod: 'período cerrado'
      };
    }
    return {
      label: 'memória de leitura', title: 'Sua retrospectiva de leitura', week: 'Semana', month: 'Mês',
      currentWeek: 'Sua semana até agora', currentMonth: 'Seu mês até agora', previous: 'Período anterior', next: 'Período seguinte',
      sessions: 'sessões', activeDays: 'dias ativos', books: 'livros tocados', pages: 'páginas avançadas', updates: 'atualizações',
      emptyCurrent: 'Este período ainda está em branco. Ele começa quando você registra Li mais.',
      emptyPast: 'Nenhuma sessão foi registrada neste período — e tudo bem.',
      loading: 'Reunindo suas memórias de leitura…', error: 'Não consegui montar esta retrospectiva agora.', retry: 'Tentar novamente',
      highlights: 'Livros deste período', sessionOne: '1 sessão', sessionMany: '{count} sessões',
      pageOne: '+1 página', pageMany: '+{count} páginas', lastPage: 'página {value}', lastPercent: '{value}%', lastChapter: 'capítulo: {value}',
      share: 'Compartilhar retrospectiva', openDiary: 'Abrir diário', cardWeek: 'MINHA SEMANA DE LEITURA', cardMonth: 'MEU MÊS DE LEITURA',
      cardSubtitle: 'uma memória de leitura', downloaded: 'Retrospectiva baixada.', shareError: 'Não consegui criar o card agora.',
      close: 'Fechar', periodInProgress: 'em andamento', completedPeriod: 'período fechado'
    };
  }

  function safe(value) {
    if (typeof global.esc === 'function') return global.esc(value);
    return String(value || '').replace(/[&<>"]/g, char => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[char]));
  }

  function format(template, values) {
    return String(template || '').replace(/\{(\w+)\}/g, (_, key) => String(values?.[key] ?? ''));
  }

  function parseDate(iso) {
    const [year, month, day] = String(iso || '').split('-').map(Number);
    return new Date(year, Math.max(0, month - 1), day || 1, 12, 0, 0);
  }

  function periodLabel(data) {
    if (!data) return '';
    const start = parseDate(data.start_date);
    const end = parseDate(data.end_date);
    const localeCode = locale();
    if (data.period === 'month') {
      return new Intl.DateTimeFormat(localeCode, {month: 'long', year: 'numeric'}).format(start);
    }
    const sameMonth = start.getMonth() === end.getMonth() && start.getFullYear() === end.getFullYear();
    const startText = new Intl.DateTimeFormat(localeCode, sameMonth ? {day: '2-digit'} : {day: '2-digit', month: 'short'}).format(start);
    const endText = new Intl.DateTimeFormat(localeCode, {day: '2-digit', month: 'short', year: 'numeric'}).format(end);
    return `${startText} – ${endText}`;
  }

  function number(value) {
    try { return Number(value || 0).toLocaleString(locale()); }
    catch (_) { return String(value || 0); }
  }

  function track(action, data = recap) {
    try {
      if (!data || !global.LombadaFeatures?.isEnabled?.('product_analytics')) return;
      global.LombadaAnalytics?.track?.('period_recap', {
        period: data.period === 'month' ? 'month' : 'week',
        action,
        state: data.state === 'active' ? 'active' : 'empty'
      });
    } catch (_) {}
  }

  function metric(value, label, emphasis = false) {
    return `<div class="period-recap-metric ${emphasis ? 'emphasis' : ''}"><strong>${safe(number(value))}</strong><span>${safe(label)}</span></div>`;
  }

  function progressText(progress) {
    const c = copy();
    if (!progress || progress.type === 'session') return '';
    if (progress.type === 'page') return format(c.lastPage, {value: number(progress.value)});
    if (progress.type === 'percentage') return format(c.lastPercent, {value: number(progress.value)});
    if (progress.type === 'chapter') return format(c.lastChapter, {value: String(progress.label || '').slice(0, 70)});
    return '';
  }

  function bookMarkup(book) {
    const c = copy();
    const cover = safe(book.cover_url || '');
    const image = cover ? `<img src="${cover}" alt="" loading="lazy" referrerpolicy="no-referrer" onerror="this.remove()">` : '';
    const sessions = Number(book.sessions || 0);
    const pages = Number(book.pages_advanced || 0);
    const details = [
      sessions === 1 ? c.sessionOne : format(c.sessionMany, {count: number(sessions)}),
      pages === 1 ? c.pageOne : (pages > 1 ? format(c.pageMany, {count: number(pages)}) : ''),
      progressText(book.last_progress)
    ].filter(Boolean).join(' · ');
    return `<article class="period-recap-book">
      <div class="period-recap-cover">${image}<span>${safe(String(book.title || 'L').charAt(0).toUpperCase())}</span></div>
      <div class="period-recap-book-copy"><h4>${safe(book.title || '')}</h4><p>${safe(book.author || '')}</p><small>${safe(details)}</small></div>
    </article>`;
  }

  function sectionHTML() {
    const c = copy();
    if (loading) {
      return `<div class="label">${safe(c.label)}</div><div class="period-recap-loading" role="status">${safe(c.loading)}</div>`;
    }
    if (error || !recap) {
      return `<div class="label">${safe(c.label)}</div><div class="period-recap-error"><p>${safe(c.error)}</p><button type="button" class="pbtn" data-recap-action="retry">${safe(c.retry)}</button></div>`;
    }

    const currentTitle = recap.is_current ? (period === 'week' ? c.currentWeek : c.currentMonth) : c.title;
    const pageMetric = Number(recap.page_sessions_calculable || 0) > 0
      ? metric(recap.pages_advanced, c.pages, true)
      : metric(recap.sessions, c.updates, true);
    const metrics = [
      metric(recap.sessions, c.sessions),
      metric(recap.active_days, c.activeDays),
      metric(recap.books_touched, c.books),
      pageMetric
    ].join('');
    const empty = recap.state !== 'active';
    const books = Array.isArray(recap.highlights) ? recap.highlights : [];
    const highlights = books.length
      ? `<div class="period-recap-books"><div class="period-recap-subtitle">${safe(c.highlights)}</div>${books.map(bookMarkup).join('')}</div>`
      : '';

    return `<div class="period-recap-top"><div><div class="label">${safe(c.label)}</div><h3>${safe(currentTitle)}</h3><p>${safe(periodLabel(recap))} · ${safe(recap.is_complete ? c.completedPeriod : c.periodInProgress)}</p></div>
      <div class="period-recap-tabs" role="tablist" aria-label="${safe(c.title)}"><button type="button" role="tab" data-recap-period="week" aria-selected="${period === 'week'}" class="${period === 'week' ? 'active' : ''}">${safe(c.week)}</button><button type="button" role="tab" data-recap-period="month" aria-selected="${period === 'month'}" class="${period === 'month' ? 'active' : ''}">${safe(c.month)}</button></div></div>
      <div class="period-recap-nav"><button type="button" data-recap-nav="older" ${recap.can_go_older ? '' : 'disabled'} aria-label="${safe(c.previous)}">←</button><strong>${safe(periodLabel(recap))}</strong><button type="button" data-recap-nav="newer" ${recap.can_go_newer ? '' : 'disabled'} aria-label="${safe(c.next)}">→</button></div>
      ${empty ? `<div class="period-recap-empty"><span aria-hidden="true">◌</span><p>${safe(recap.is_current ? c.emptyCurrent : c.emptyPast)}</p></div>` : `<div class="period-recap-metrics">${metrics}</div>${highlights}`}
      <div class="profile-actions period-recap-actions">${empty ? '' : `<button type="button" class="pbtn solid" data-recap-action="share">${safe(c.share)}</button>`}<button type="button" class="pbtn" data-recap-action="diary">${safe(c.openDiary)}</button></div>`;
  }

  function ensureSection() {
    const profile = global.document.querySelector('#perfil .pcard');
    if (!profile) return null;
    let section = global.document.getElementById(SECTION_ID);
    if (!section) {
      section = global.document.createElement('section');
      section.id = SECTION_ID;
      section.className = 'account-box period-recap-box';
      const essentials = global.document.getElementById('essentialBooksSection');
      const anchor = essentials || profile.querySelector('.profile-metrics') || profile.querySelector('.profile-cta-row');
      if (anchor) anchor.insertAdjacentElement('afterend', section);
      else profile.prepend(section);
    }
    return section;
  }

  function bindSection(section) {
    section.querySelectorAll('[data-recap-period]').forEach(button => button.addEventListener('click', () => {
      const next = button.dataset.recapPeriod === 'month' ? 'month' : 'week';
      if (next === period) return;
      period = next;
      offset = 0;
      void loadRecap();
    }));
    section.querySelector('[data-recap-nav="older"]')?.addEventListener('click', () => navigate(1));
    section.querySelector('[data-recap-nav="newer"]')?.addEventListener('click', () => navigate(-1));
    section.querySelector('[data-recap-action="retry"]')?.addEventListener('click', () => loadRecap());
    section.querySelector('[data-recap-action="share"]')?.addEventListener('click', shareRecap);
    section.querySelector('[data-recap-action="diary"]')?.addEventListener('click', () => {
      try { if (typeof global.irPara === 'function') global.irPara('estante', {subaba: 'diario'}); }
      catch (_) {}
    });
  }

  function renderSection() {
    const section = ensureSection();
    if (!section) return;
    section.innerHTML = sectionHTML();
    bindSection(section);
  }

  function navigate(delta) {
    const next = Math.max(0, Math.min(MAX_OFFSET, offset + delta));
    if (next === offset) return;
    offset = next;
    track('navigate');
    void loadRecap();
  }

  async function loadRecap() {
    const token = ++requestToken;
    loading = true;
    error = false;
    renderSection();
    try {
      const response = await global.fetch(`/api/eu/retrospectiva?period=${encodeURIComponent(period)}&offset=${offset}`, {
        credentials: 'same-origin', cache: 'no-store', headers: {Accept: 'application/json'}
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const payload = await response.json();
      if (token !== requestToken) return;
      recap = payload;
      const key = `${payload.period}:${payload.offset}:${payload.state}`;
      if (!viewedKeys.has(key)) {
        viewedKeys.add(key);
        track('viewed', payload);
      }
    } catch (_) {
      if (token !== requestToken) return;
      error = true;
      recap = null;
    } finally {
      if (token !== requestToken) return;
      loading = false;
      renderSection();
    }
  }

  function ensureStyles() {
    if (global.document.querySelector('[data-period-recap-styles]')) return;
    const style = global.document.createElement('style');
    style.dataset.periodRecapStyles = '1';
    style.textContent = `
      .period-recap-box{position:relative;overflow:hidden}.period-recap-top{display:flex;justify-content:space-between;align-items:flex-start;gap:18px}.period-recap-top h3{margin:6px 0 3px;font:500 26px/1.08 "Fraunces",serif}.period-recap-top p{margin:0;color:var(--dim);font-size:12px}.period-recap-tabs{display:flex;padding:3px;border:1px solid color-mix(in srgb,var(--ink),transparent 82%);border-radius:999px}.period-recap-tabs button{border:0;border-radius:999px;background:transparent;color:var(--dim);padding:7px 11px;font:700 9px/1 "Space Mono",monospace;text-transform:uppercase}.period-recap-tabs button.active{background:var(--gold);color:var(--paper)}.period-recap-nav{display:grid;grid-template-columns:36px minmax(0,1fr) 36px;align-items:center;gap:8px;margin:18px 0 14px}.period-recap-nav strong{text-align:center;font:500 15px/1.2 "Fraunces",serif}.period-recap-nav button{width:36px;height:36px;border:1px solid color-mix(in srgb,var(--ink),transparent 82%);border-radius:50%;background:transparent;color:var(--ink)}.period-recap-nav button:disabled{opacity:.25}.period-recap-metrics{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px}.period-recap-metric{min-width:0;padding:14px 10px;border:1px solid color-mix(in srgb,var(--ink),transparent 87%);background:color-mix(in srgb,var(--paper),#fff 3%)}.period-recap-metric.emphasis{border-color:color-mix(in srgb,var(--gold),transparent 45%);background:color-mix(in srgb,var(--gold),transparent 93%)}.period-recap-metric strong{display:block;font:500 26px/1 "Fraunces",serif;color:var(--ink)}.period-recap-metric span{display:block;margin-top:6px;color:var(--dim);font:700 8px/1.25 "Space Mono",monospace;text-transform:uppercase}.period-recap-subtitle{margin:20px 0 9px;color:var(--dim);font:700 9px/1 "Space Mono",monospace;text-transform:uppercase;letter-spacing:.08em}.period-recap-books{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:9px}.period-recap-subtitle{grid-column:1/-1}.period-recap-book{display:grid;grid-template-columns:52px minmax(0,1fr);gap:10px;align-items:center;padding:9px;border:1px solid color-mix(in srgb,var(--ink),transparent 87%)}.period-recap-cover{position:relative;width:52px;aspect-ratio:2/3;overflow:hidden;background:color-mix(in srgb,var(--gold),transparent 88%)}.period-recap-cover img{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;z-index:1}.period-recap-cover span{position:absolute;inset:0;display:grid;place-items:center;color:var(--gold);font:500 italic 22px/1 "Fraunces",serif}.period-recap-book-copy{min-width:0}.period-recap-book h4{margin:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font:500 14px/1.15 "Fraunces",serif}.period-recap-book p{margin:3px 0 0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:var(--dim);font-size:10px}.period-recap-book small{display:block;margin-top:6px;color:var(--gold);font:700 8px/1.35 "Space Mono",monospace}.period-recap-actions{margin-top:16px}.period-recap-empty{display:flex;align-items:center;gap:14px;padding:24px 16px;border:1px dashed color-mix(in srgb,var(--ink),transparent 75%);color:var(--dim)}.period-recap-empty>span{font:500 36px/1 "Fraunces",serif;color:var(--gold)}.period-recap-empty p,.period-recap-error p{margin:0;font:400 15px/1.45 "Spectral",serif}.period-recap-loading,.period-recap-error{padding:30px 12px;text-align:center;color:var(--dim)}.period-recap-error .pbtn{margin-top:12px}.theme-dark .period-recap-metric,.theme-dark .period-recap-book{background:rgba(255,255,255,.018)}
      @media(max-width:620px){.period-recap-top{display:block}.period-recap-tabs{width:max-content;margin-top:14px}.period-recap-metrics{grid-template-columns:repeat(2,minmax(0,1fr))}.period-recap-books{grid-template-columns:1fr}.period-recap-actions{display:grid;grid-template-columns:1fr}.period-recap-actions .pbtn{width:100%}}
      @media(prefers-reduced-motion:reduce){.period-recap-box,.period-recap-box *{animation:none!important;transition:none!important;scroll-behavior:auto!important}}
    `;
    global.document.head.appendChild(style);
  }

  function proxyCover(url) {
    if (!url) return '';
    if (url.startsWith('/')) return url;
    return `/api/capa?url=${encodeURIComponent(url)}`;
  }

  function loadImage(url) {
    return new Promise(resolve => {
      if (!url) { resolve(null); return; }
      const image = new Image();
      image.onload = () => resolve(image);
      image.onerror = () => resolve(null);
      image.src = proxyCover(url);
    });
  }

  function roundRect(ctx, x, y, width, height, radius) {
    ctx.beginPath();
    ctx.roundRect(x, y, width, height, radius);
  }

  function wrapText(ctx, text, maxWidth, maxLines) {
    const words = String(text || '').split(/\s+/).filter(Boolean);
    const lines = [];
    let line = '';
    for (const word of words) {
      const candidate = line ? `${line} ${word}` : word;
      if (!line || ctx.measureText(candidate).width <= maxWidth) line = candidate;
      else { lines.push(line); line = word; }
      if (lines.length >= maxLines) break;
    }
    if (lines.length < maxLines && line) lines.push(line);
    if (lines.join(' ').split(' ').length < words.length && lines.length) lines[lines.length - 1] = lines[lines.length - 1].replace(/[.,;:!?-]+$/, '') + '…';
    return lines;
  }

  async function renderShareCard(data) {
    const c = copy();
    const canvas = global.document.createElement('canvas');
    canvas.width = 1080;
    canvas.height = 1350;
    const ctx = canvas.getContext('2d');
    const gradient = ctx.createLinearGradient(0, 0, 1080, 1350);
    gradient.addColorStop(0, '#24110F');
    gradient.addColorStop(.58, '#4A191C');
    gradient.addColorStop(1, '#160A0A');
    ctx.fillStyle = gradient;
    ctx.fillRect(0, 0, 1080, 1350);

    ctx.textAlign = 'center';
    ctx.fillStyle = '#D6A75B';
    ctx.font = "700 25px 'Space Mono', monospace";
    ctx.fillText('LOMBADA.APP', 540, 78);
    ctx.fillStyle = '#F4EFE6';
    ctx.font = "500 italic 65px Fraunces, serif";
    ctx.fillText(data.period === 'month' ? c.cardMonth : c.cardWeek, 540, 166);
    ctx.fillStyle = 'rgba(244,239,230,.72)';
    ctx.font = "400 27px Spectral, serif";
    ctx.fillText(`${c.cardSubtitle} · ${periodLabel(data)}`, 540, 214);

    const values = [
      [data.sessions, c.sessions], [data.active_days, c.activeDays], [data.books_touched, c.books],
      [data.page_sessions_calculable > 0 ? data.pages_advanced : data.sessions, data.page_sessions_calculable > 0 ? c.pages : c.updates]
    ];
    values.forEach(([value, label], index) => {
      const x = 105 + index * 220;
      ctx.fillStyle = 'rgba(244,239,230,.055)';
      roundRect(ctx, x, 275, 190, 135, 13);
      ctx.fill();
      ctx.strokeStyle = index === 3 ? 'rgba(214,167,91,.75)' : 'rgba(244,239,230,.16)';
      ctx.lineWidth = 2;
      ctx.stroke();
      ctx.textAlign = 'left';
      ctx.fillStyle = '#F4EFE6';
      ctx.font = "500 48px Fraunces, serif";
      ctx.fillText(number(value), x + 18, 335);
      ctx.fillStyle = 'rgba(244,239,230,.62)';
      ctx.font = "700 13px 'Space Mono', monospace";
      wrapText(ctx, String(label).toUpperCase(), 155, 2).forEach((line, lineIndex) => ctx.fillText(line, x + 18, 371 + lineIndex * 17));
    });

    const books = Array.isArray(data.highlights) ? data.highlights.slice(0, 4) : [];
    const positions = [[110, 490], [570, 490], [110, 875], [570, 875]];
    for (let index = 0; index < 4; index += 1) {
      const book = books[index];
      const [x, y] = positions[index];
      const coverWidth = 150;
      const coverHeight = 225;
      ctx.fillStyle = 'rgba(244,239,230,.055)';
      roundRect(ctx, x, y, 400, 310, 14);
      ctx.fill();
      ctx.strokeStyle = 'rgba(244,239,230,.12)';
      ctx.stroke();
      ctx.save();
      roundRect(ctx, x + 18, y + 18, coverWidth, coverHeight, 7);
      ctx.clip();
      ctx.fillStyle = index % 2 ? '#6A2A2F' : '#8C5B35';
      ctx.fillRect(x + 18, y + 18, coverWidth, coverHeight);
      if (book) {
        const image = await loadImage(book.cover_url);
        if (image) {
          const scale = Math.max(coverWidth / image.naturalWidth, coverHeight / image.naturalHeight);
          const imageWidth = image.naturalWidth * scale;
          const imageHeight = image.naturalHeight * scale;
          ctx.drawImage(image, x + 18 + (coverWidth - imageWidth) / 2, y + 18 + (coverHeight - imageHeight) / 2, imageWidth, imageHeight);
        }
      }
      ctx.restore();
      if (!book) continue;
      ctx.textAlign = 'left';
      ctx.fillStyle = '#F4EFE6';
      ctx.font = "500 28px Fraunces, serif";
      wrapText(ctx, book.title, 200, 3).forEach((line, lineIndex) => ctx.fillText(line, x + 190, y + 48 + lineIndex * 32));
      ctx.fillStyle = 'rgba(244,239,230,.62)';
      ctx.font = "400 19px Spectral, serif";
      wrapText(ctx, book.author, 200, 2).forEach((line, lineIndex) => ctx.fillText(line, x + 190, y + 158 + lineIndex * 23));
      ctx.fillStyle = '#D6A75B';
      ctx.font = "700 14px 'Space Mono', monospace";
      const details = Number(book.pages_advanced || 0) > 0
        ? `${number(book.sessions)} ${c.sessions} · +${number(book.pages_advanced)} ${c.pages}`
        : `${number(book.sessions)} ${c.sessions}`;
      wrapText(ctx, details.toUpperCase(), 200, 2).forEach((line, lineIndex) => ctx.fillText(line, x + 190, y + 235 + lineIndex * 18));
    }

    let handle = '';
    try { handle = typeof meuHandle !== 'undefined' ? String(meuHandle || '').trim() : ''; } catch (_) {}
    ctx.textAlign = 'center';
    ctx.fillStyle = 'rgba(244,239,230,.65)';
    ctx.font = "400 20px 'Space Mono', monospace";
    ctx.fillText(handle ? `@${handle}` : 'LOMBADA', 540, 1310);
    return canvas;
  }

  function canvasBlob(canvas) {
    return new Promise(resolve => canvas.toBlob(resolve, 'image/png', .94));
  }

  async function shareRecap() {
    if (!recap || recap.state !== 'active') return;
    try {
      const canvas = await renderShareCard(recap);
      const blob = await canvasBlob(canvas);
      if (!blob) throw new Error('blob');
      const file = new File([blob], `lombada-retrospectiva-${recap.period}.png`, {type: 'image/png'});
      if (global.navigator.share && global.navigator.canShare?.({files: [file]})) {
        await global.navigator.share({files: [file], title: copy().title});
      } else {
        const link = global.document.createElement('a');
        link.href = URL.createObjectURL(blob);
        link.download = file.name;
        link.click();
        global.setTimeout(() => URL.revokeObjectURL(link.href), 2000);
        try { if (typeof toast === 'function') toast(copy().downloaded); } catch (_) {}
      }
      track('shared');
    } catch (shareError) {
      if (shareError?.name === 'AbortError') return;
      try { if (typeof toast === 'function') toast(copy().shareError); } catch (_) {}
    }
  }

  function installProfileHook() {
    if (originalRenderProfile || typeof global.renderPerfil !== 'function') return;
    originalRenderProfile = global.renderPerfil;
    global.renderPerfil = function renderProfileWithPeriodRecap(...args) {
      const result = originalRenderProfile.apply(this, args);
      global.queueMicrotask(renderSection);
      return result;
    };
  }

  function init() {
    ensureStyles();
    installProfileHook();
    renderSection();
    void loadRecap();
  }

  init();
})(window);
