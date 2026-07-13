/* Reações literárias em críticas públicas.

   O módulo observa os cards já renderizados pelo app legado e adiciona uma
   camada independente. Totais são carregados em lote; nenhuma crítica, título,
   autor ou pessoa reagente é enviada ao analytics.
*/
(function literaryReactionsBootstrap(global) {
  'use strict';

  const TYPES = Object.freeze(['want_to_read', 'moved_me', 'good_reading']);
  const summaries = new Map();
  const pendingIds = new Set();
  let batchTimer = null;
  let inboxData = null;
  let inboxLoading = false;
  let inboxSeenSent = false;
  let scanTimer = null;

  function locale() {
    const raw = String(global.document.documentElement.lang || 'pt-BR').toLowerCase();
    if (raw.startsWith('en')) return 'en';
    if (raw.startsWith('es')) return 'es';
    return 'pt-BR';
  }

  function copy() {
    if (locale() === 'en') {
      return {
        heading: 'Literary reactions', want_to_read: 'I want to read it too',
        moved_me: 'This one stayed with me', good_reading: 'Good reading',
        connect: 'Connect Google to react', error: 'I could not update your reaction now.',
        inboxLabel: 'social return', inboxTitle: 'Reactions to your reviews',
        reactionsOne: '1 reaction', reactionsMany: '{count} reactions', unread: 'new'
      };
    }
    if (locale() === 'es') {
      return {
        heading: 'Reacciones literarias', want_to_read: 'Quiero leerlo también',
        moved_me: 'Este me marcó', good_reading: 'Buena lectura',
        connect: 'Conecta Google para reaccionar', error: 'No pude actualizar tu reacción ahora.',
        inboxLabel: 'retorno social', inboxTitle: 'Reacciones a tus reseñas',
        reactionsOne: '1 reacción', reactionsMany: '{count} reacciones', unread: 'nueva'
      };
    }
    return {
      heading: 'Reações literárias', want_to_read: 'Quero ler também',
      moved_me: 'Esse me marcou', good_reading: 'Boa leitura',
      connect: 'Conecte o Google para reagir', error: 'Não consegui atualizar sua reação agora.',
      inboxLabel: 'retorno social', inboxTitle: 'Reações às suas críticas',
      reactionsOne: '1 reação', reactionsMany: '{count} reações', unread: 'nova'
    };
  }

  function safe(value) {
    if (typeof global.esc === 'function') return global.esc(value);
    return String(value || '').replace(/[&<>"]/g, char => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[char]));
  }

  function format(template, values) {
    return String(template || '').replace(/\{(\w+)\}/g, (_, key) => String(values?.[key] ?? ''));
  }

  function connectedAccount() {
    try {
      return typeof minhaConta !== 'undefined' && minhaConta?.logado === true;
    } catch (_) {
      return false;
    }
  }

  function sourceFor(element) {
    if (element?.closest?.('#secFeed')) return 'feed';
    if (element?.closest?.('#secPerfil')) return 'profile';
    return 'work';
  }

  function track(action, reactionType, source) {
    try {
      if (!global.LombadaFeatures?.isEnabled?.('product_analytics')) return;
      global.LombadaAnalytics?.track?.('literary_reaction', {
        source: ['feed', 'work', 'profile'].includes(source) ? source : 'work',
        action,
        reaction_type: TYPES.includes(reactionType) ? reactionType : 'none'
      });
    } catch (_) {}
  }

  function requestConnection() {
    try {
      if (typeof conectarGoogle === 'function') {
        conectarGoogle('feed');
        return;
      }
    } catch (_) {}
    try { if (typeof toast === 'function') toast(copy().connect); } catch (_) {}
  }

  function iconFor(type) {
    if (type === 'want_to_read') return '＋';
    if (type === 'moved_me') return '✦';
    return '↗';
  }

  function normalizeSummary(raw, readingId) {
    const counts = raw?.counts && typeof raw.counts === 'object' ? raw.counts : {};
    return {
      reading_id: Number(raw?.reading_id || readingId),
      counts: Object.fromEntries(TYPES.map(type => [type, Math.max(0, Number(counts[type] || 0))])),
      total: Math.max(0, Number(raw?.total || 0)),
      mine: TYPES.includes(raw?.mine) ? raw.mine : null,
      is_owner: raw?.is_owner === true,
      connected: raw?.connected === true || connectedAccount(),
      can_react: raw?.can_react === true
    };
  }

  function reactionBarHTML(summary) {
    const c = copy();
    if (summary.is_owner && summary.total === 0) return '';
    const buttons = TYPES.map(type => {
      const count = Number(summary.counts[type] || 0);
      const active = summary.mine === type;
      const disabled = summary.is_owner;
      const label = c[type];
      return `<button type="button" class="literary-reaction-chip ${active ? 'active' : ''} ${disabled ? 'read-only' : ''}" data-literary-reaction="${type}" aria-pressed="${active}" ${disabled ? 'disabled' : ''} title="${safe(label)}"><span class="literary-reaction-icon" aria-hidden="true">${iconFor(type)}</span><span>${safe(label)}</span>${count ? `<b>${count}</b>` : ''}</button>`;
    }).join('');
    return `<div class="literary-reactions" data-literary-reading="${summary.reading_id}"><div class="literary-reactions-label">${safe(c.heading)}</div><div class="literary-reactions-chips">${buttons}</div></div>`;
  }

  function renderReading(readingId) {
    const summary = summaries.get(Number(readingId));
    if (!summary) return;
    global.document.querySelectorAll(`[data-like-btn="${Number(readingId)}"]`).forEach(likeButton => {
      const actions = likeButton.closest('.review-actions');
      if (!actions) return;
      const previous = actions.nextElementSibling;
      const existing = previous?.matches?.(`[data-literary-reading="${Number(readingId)}"]`) ? previous : null;
      const html = reactionBarHTML(summary);
      if (!html) {
        existing?.remove();
        return;
      }
      const signature = JSON.stringify(summary);
      if (existing?.dataset.signature === signature) return;
      const holder = global.document.createElement('div');
      holder.innerHTML = html;
      const next = holder.firstElementChild;
      next.dataset.signature = signature;
      if (existing) existing.replaceWith(next);
      else actions.insertAdjacentElement('afterend', next);
    });
  }

  async function loadBatch(ids) {
    const unique = [...new Set(ids.map(Number).filter(id => Number.isInteger(id) && id > 0))];
    if (!unique.length) return;
    try {
      const response = await global.fetch(`/api/reviews/reactions?ids=${encodeURIComponent(unique.join(','))}`, {
        credentials: 'same-origin', cache: 'no-store', headers: {Accept: 'application/json'}
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const payload = await response.json();
      const reviews = payload?.reviews && typeof payload.reviews === 'object' ? payload.reviews : {};
      unique.forEach(id => {
        if (reviews[String(id)]) summaries.set(id, normalizeSummary(reviews[String(id)], id));
      });
      unique.forEach(renderReading);
    } catch (_) {
      // A reação é complementar: falha silenciosa mantém curtidas/comentários.
    } finally {
      unique.forEach(id => pendingIds.delete(id));
    }
  }

  function scheduleBatch() {
    if (batchTimer !== null) return;
    batchTimer = global.setTimeout(() => {
      batchTimer = null;
      const ids = [...pendingIds];
      if (ids.length) void loadBatch(ids);
    }, 60);
  }

  function scanReviews() {
    global.document.querySelectorAll('.review-actions [data-like-btn]').forEach(button => {
      const id = Number(button.dataset.likeBtn);
      if (!Number.isInteger(id) || id <= 0) return;
      if (summaries.has(id)) renderReading(id);
      else pendingIds.add(id);
    });
    if (pendingIds.size) scheduleBatch();
  }

  function showBusy(bar, busy) {
    if (!bar) return;
    bar.setAttribute('aria-busy', busy ? 'true' : 'false');
    bar.querySelectorAll('button').forEach(button => { button.disabled = busy || button.classList.contains('read-only'); });
  }

  async function react(button) {
    const bar = button.closest('[data-literary-reading]');
    const readingId = Number(bar?.dataset.literaryReading);
    const type = button.dataset.literaryReaction;
    const current = summaries.get(readingId);
    if (!bar || !current || !TYPES.includes(type)) return;
    if (current.is_owner) return;
    if (!current.connected && !connectedAccount()) {
      requestConnection();
      return;
    }

    const removing = current.mine === type;
    showBusy(bar, true);
    try {
      const response = await global.fetch(`/api/reviews/${readingId}/reaction`, {
        method: removing ? 'DELETE' : 'PUT', credentials: 'same-origin', cache: 'no-store',
        headers: removing ? {Accept: 'application/json'} : {'Content-Type': 'application/json', Accept: 'application/json'},
        body: removing ? undefined : JSON.stringify({reaction_type: type})
      });
      if (response.status === 401 || response.status === 403) {
        requestConnection();
        return;
      }
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const payload = await response.json();
      summaries.set(readingId, normalizeSummary(payload, readingId));
      renderReading(readingId);
      track(removing ? 'removed' : (payload.action === 'changed' ? 'changed' : 'set'), removing ? 'none' : type, sourceFor(bar));
    } catch (_) {
      try { if (typeof toast === 'function') toast(copy().error); } catch (_) {}
    } finally {
      const fresh = global.document.querySelector(`[data-literary-reading="${readingId}"]`);
      showBusy(fresh, false);
    }
  }

  function inboxCountsText(group) {
    const c = copy();
    return TYPES
      .filter(type => Number(group?.counts?.[type] || 0) > 0)
      .map(type => `${c[type]} · ${Number(group.counts[type])}`)
      .join('  ·  ');
  }

  function inboxHTML(data) {
    const c = copy();
    const groups = Array.isArray(data?.groups) ? data.groups : [];
    if (!groups.length) return '';
    const items = groups.map(group => {
      const count = Number(group.total || 0);
      const countLabel = count === 1 ? c.reactionsOne : format(c.reactionsMany, {count});
      const cover = safe(group.cover_url || '');
      return `<article class="literary-inbox-item ${group.unread ? 'unread' : ''}"><div class="literary-inbox-cover">${cover ? `<img src="${cover}" alt="" loading="lazy" referrerpolicy="no-referrer" onerror="this.remove()">` : ''}<span>${safe(String(group.title || 'L').charAt(0).toUpperCase())}</span></div><div class="literary-inbox-copy"><div class="literary-inbox-title-row"><h4>${safe(group.title || '')}</h4>${group.unread ? `<em>${safe(c.unread)}</em>` : ''}</div><p>${safe(group.author || '')}</p><strong>${safe(countLabel)}</strong><small>${safe(inboxCountsText(group))}</small></div></article>`;
    }).join('');
    return `<div class="label">${safe(c.inboxLabel)}</div><div class="literary-inbox-head"><h3>${safe(c.inboxTitle)}</h3><span>${Number(data.unread_groups || 0) || ''}</span></div><div class="literary-inbox-list">${items}</div>`;
  }

  function profileRoot() {
    return global.document.querySelector('#perfil .pcard, #secPerfil .pcard');
  }

  function renderInbox() {
    const groups = Array.isArray(inboxData?.groups) ? inboxData.groups : [];
    if (!groups.length) return;
    const profile = profileRoot();
    if (!profile) return;
    let section = global.document.getElementById('literaryReactionInbox');
    if (!section) {
      section = global.document.createElement('section');
      section.id = 'literaryReactionInbox';
      section.className = 'account-box literary-inbox';
      const anchor = global.document.getElementById('periodRecapSection') || global.document.getElementById('essentialBooksSection') || profile.querySelector('.profile-metrics');
      if (anchor) anchor.insertAdjacentElement('afterend', section);
      else profile.prepend(section);
    }
    const signature = JSON.stringify(inboxData);
    if (section.dataset.signature !== signature) {
      section.innerHTML = inboxHTML(inboxData);
      section.dataset.signature = signature;
    }
    markInboxSeenWhenVisible(section);
  }

  async function loadInbox() {
    if (inboxLoading || inboxData) return;
    inboxLoading = true;
    try {
      const response = await global.fetch('/api/eu/reacoes-literarias?limit=20', {
        credentials: 'same-origin', cache: 'no-store', headers: {Accept: 'application/json'}
      });
      if (response.status === 401 || response.status === 403) return;
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      inboxData = await response.json();
      renderInbox();
    } catch (_) {
      inboxData = {groups: [], unread_groups: 0};
    } finally {
      inboxLoading = false;
    }
  }

  function markInboxSeenWhenVisible(section) {
    if (inboxSeenSent || !section || Number(inboxData?.unread_groups || 0) <= 0) return;
    global.setTimeout(async () => {
      if (inboxSeenSent || !section.isConnected || section.offsetParent === null) return;
      inboxSeenSent = true;
      try {
        const response = await global.fetch('/api/eu/reacoes-literarias/vistas', {
          method: 'POST', credentials: 'same-origin', cache: 'no-store', headers: {Accept: 'application/json'}
        });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        track('viewed', 'none', 'profile');
        inboxData.unread_groups = 0;
        inboxData.groups.forEach(group => { group.unread = false; });
        renderInbox();
      } catch (_) {
        inboxSeenSent = false;
      }
    }, 1200);
  }

  function ensureStyles() {
    if (global.document.querySelector('[data-literary-reactions-styles]')) return;
    const style = global.document.createElement('style');
    style.dataset.literaryReactionsStyles = '1';
    style.textContent = `
      .literary-reactions{padding:11px 0 13px;border-bottom:1px solid color-mix(in srgb,var(--ink),transparent 90%)}.literary-reactions-label{margin-bottom:8px;color:var(--dim);font:700 8px/1 "Space Mono",monospace;letter-spacing:.1em;text-transform:uppercase}.literary-reactions-chips{display:flex;flex-wrap:wrap;gap:7px}.literary-reaction-chip{display:inline-flex;align-items:center;gap:6px;min-height:34px;padding:7px 10px;border:1px solid color-mix(in srgb,var(--ink),transparent 80%);border-radius:999px;background:transparent;color:var(--dim);font:700 9px/1.15 "Space Mono",monospace}.literary-reaction-chip:hover,.literary-reaction-chip:focus-visible{border-color:var(--gold);color:var(--gold)}.literary-reaction-chip.active{border-color:var(--gold);background:color-mix(in srgb,var(--gold),transparent 88%);color:var(--gold)}.literary-reaction-chip.read-only{cursor:default;opacity:.82}.literary-reaction-chip b{min-width:16px;padding:2px 4px;border-radius:999px;background:color-mix(in srgb,var(--ink),transparent 91%);font-size:8px}.literary-reaction-icon{font-size:14px}.literary-reactions[aria-busy="true"]{opacity:.62}.literary-inbox-head{display:flex;align-items:end;justify-content:space-between;gap:12px;margin:6px 0 14px}.literary-inbox-head h3{margin:0;font:500 25px/1.1 "Fraunces",serif}.literary-inbox-head>span{display:grid;place-items:center;min-width:24px;height:24px;border-radius:50%;background:var(--gold);color:var(--paper);font:700 9px/1 "Space Mono",monospace}.literary-inbox-list{display:grid;gap:9px}.literary-inbox-item{display:grid;grid-template-columns:46px minmax(0,1fr);gap:11px;align-items:center;padding:10px;border:1px solid color-mix(in srgb,var(--ink),transparent 87%)}.literary-inbox-item.unread{border-color:color-mix(in srgb,var(--gold),transparent 48%);background:color-mix(in srgb,var(--gold),transparent 94%)}.literary-inbox-cover{position:relative;width:46px;aspect-ratio:2/3;overflow:hidden;background:color-mix(in srgb,var(--gold),transparent 87%)}.literary-inbox-cover img{position:absolute;z-index:1;inset:0;width:100%;height:100%;object-fit:cover}.literary-inbox-cover span{position:absolute;inset:0;display:grid;place-items:center;color:var(--gold);font:500 italic 20px/1 "Fraunces",serif}.literary-inbox-copy{min-width:0}.literary-inbox-title-row{display:flex;align-items:center;gap:7px}.literary-inbox-title-row h4{margin:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font:500 14px/1.15 "Fraunces",serif}.literary-inbox-title-row em{padding:3px 6px;border-radius:999px;background:var(--gold);color:var(--paper);font:700 normal 7px/1 "Space Mono",monospace;text-transform:uppercase}.literary-inbox-copy p{margin:3px 0;color:var(--dim);font-size:10px}.literary-inbox-copy strong{display:block;color:var(--ink);font:500 12px/1.25 "Fraunces",serif}.literary-inbox-copy small{display:block;margin-top:4px;color:var(--gold);font:700 8px/1.35 "Space Mono",monospace}.theme-dark .literary-inbox-item{background:rgba(255,255,255,.015)}
      @media(max-width:520px){.literary-reactions-chips{display:grid;grid-template-columns:1fr}.literary-reaction-chip{justify-content:flex-start;width:100%}.literary-reaction-chip b{margin-left:auto}}
      @media(prefers-reduced-motion:reduce){.literary-reactions *,.literary-inbox *{animation:none!important;transition:none!important}}
    `;
    global.document.head.appendChild(style);
  }

  function scheduleScan() {
    if (scanTimer !== null) return;
    scanTimer = global.setTimeout(() => {
      scanTimer = null;
      scanReviews();
      renderInbox();
    }, 40);
  }

  global.document.addEventListener('click', event => {
    const target = event.target instanceof Element ? event.target : event.target?.parentElement;
    const button = target?.closest?.('[data-literary-reaction]');
    if (!button) return;
    event.preventDefault();
    event.stopPropagation();
    void react(button);
  });

  ensureStyles();
  void loadInbox();
  scheduleScan();
  const observer = new MutationObserver(scheduleScan);
  observer.observe(global.document.body, {childList: true, subtree: true});
})(window);
