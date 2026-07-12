/* Quatro essenciais — editor de identidade literária.

   Este módulo só é carregado quando a flag pública `favorite_books` está ativa.
   Ele reutiliza a estante já carregada pelo app e nunca envia títulos, autores ou
   posições para analytics; apenas ação e faixa de completude.
*/
(function essentialBooksBootstrap(global) {
  'use strict';

  const SECTION_ID = 'essentialBooksSection';
  const MODAL_ID = 'essentialBooksModal';
  const MAX_BOOKS = 4;
  let books = [];
  let canEdit = false;
  let loaded = false;
  let loading = false;
  let saving = false;
  let selectedKeys = [];
  let originalRenderProfile = null;

  function locale() {
    const raw = String(global.document.documentElement.lang || 'pt-BR').toLowerCase();
    if (raw.startsWith('en')) return 'en';
    if (raw.startsWith('es')) return 'es';
    return 'pt-BR';
  }

  function copy() {
    if (locale() === 'en') {
      return {
        label: 'literary identity', title: 'Four essentials',
        hint: 'Choose up to four books from your shelf that say something about you as a reader.',
        empty: 'Your literary portrait starts with one book.', edit: 'Edit essentials',
        connect: 'Connect Google to save', share: 'Share card', close: 'Close essentials editor',
        editorTitle: 'Choose your essentials', editorHint: 'Add, remove and reorder. You can leave empty slots.',
        selected: 'Selected', shelf: 'Your shelf', save: 'Save essentials', saving: 'Saving…',
        remove: 'Remove', left: 'Move left', right: 'Move right', add: 'Add', full: 'Four selected. Remove one to replace it.',
        noShelf: 'Add books to your shelf before choosing essentials.', saved: 'Your essentials were saved.',
        saveError: 'I could not save your essentials now.', cardTitle: 'MY FOUR ESSENTIALS',
        cardSubtitle: 'a literary portrait', download: 'Card downloaded.', shareError: 'I could not create the card now.'
      };
    }
    if (locale() === 'es') {
      return {
        label: 'identidad literaria', title: 'Cuatro esenciales',
        hint: 'Elige hasta cuatro libros de tu estantería que digan algo sobre ti como lector.',
        empty: 'Tu retrato literario empieza con un libro.', edit: 'Editar esenciales',
        connect: 'Conecta Google para guardar', share: 'Compartir tarjeta', close: 'Cerrar editor de esenciales',
        editorTitle: 'Elige tus esenciales', editorHint: 'Añade, elimina y ordena. Puedes dejar espacios vacíos.',
        selected: 'Seleccionados', shelf: 'Tu estantería', save: 'Guardar esenciales', saving: 'Guardando…',
        remove: 'Eliminar', left: 'Mover a la izquierda', right: 'Mover a la derecha', add: 'Añadir', full: 'Ya elegiste cuatro. Elimina uno para cambiarlo.',
        noShelf: 'Añade libros a tu estantería antes de elegir esenciales.', saved: 'Tus esenciales fueron guardados.',
        saveError: 'No pude guardar tus esenciales ahora.', cardTitle: 'MIS CUATRO ESENCIALES',
        cardSubtitle: 'un retrato literario', download: 'Tarjeta descargada.', shareError: 'No pude crear la tarjeta ahora.'
      };
    }
    return {
      label: 'identidade literária', title: 'Quatro essenciais',
      hint: 'Escolha até quatro livros da sua estante que dizem algo sobre você como leitor.',
      empty: 'Seu retrato literário começa com um livro.', edit: 'Editar essenciais',
      connect: 'Conectar Google para salvar', share: 'Compartilhar card', close: 'Fechar editor de essenciais',
      editorTitle: 'Escolha seus essenciais', editorHint: 'Adicione, remova e ordene. Você pode deixar posições vazias.',
      selected: 'Selecionados', shelf: 'Sua estante', save: 'Salvar essenciais', saving: 'Salvando…',
      remove: 'Remover', left: 'Mover para a esquerda', right: 'Mover para a direita', add: 'Adicionar', full: 'Você já escolheu quatro. Remova um para trocar.',
      noShelf: 'Adicione livros à estante antes de escolher seus essenciais.', saved: 'Seus essenciais foram salvos.',
      saveError: 'Não consegui salvar seus essenciais agora.', cardTitle: 'MEUS QUATRO ESSENCIAIS',
      cardSubtitle: 'um retrato literário', download: 'Card baixado.', shareError: 'Não consegui criar o card agora.'
    };
  }

  function safe(value) {
    if (typeof global.esc === 'function') return global.esc(value);
    return String(value || '').replace(/[&<>"]/g, char => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[char]));
  }

  function shelfBooks() {
    const seen = new Set();
    const list = [];
    try {
      for (const reading of Array.isArray(prateleira) ? prateleira : []) {
        const key = String(reading?.work_key || '').trim();
        if (!key || seen.has(key)) continue;
        seen.add(key);
        list.push({
          work_key: key,
          title: reading.titulo || '',
          author: reading.autor || '',
          cover_url: reading.capa_url || '',
        });
      }
    } catch (_) {}
    return list;
  }

  function completionFor(count) {
    if (!count) return 'empty';
    if (count >= MAX_BOOKS) return 'complete';
    return 'partial';
  }

  function eventId() {
    try { return global.crypto?.randomUUID?.() || `essential_${Date.now()}_${Math.random().toString(36).slice(2)}`; }
    catch (_) { return `essential_${Date.now()}_${Math.random().toString(36).slice(2)}`; }
  }

  function track(action, count = books.length) {
    try {
      if (!global.LombadaFeatures?.isEnabled?.('product_analytics')) return;
      global.fetch('/api/events', {
        method: 'POST', credentials: 'same-origin', cache: 'no-store', keepalive: true,
        headers: {'Content-Type': 'application/json', Accept: 'application/json'},
        body: JSON.stringify({events: [{
          event: 'essential_books',
          properties: {source: 'profile', action, completion: completionFor(count)},
          client_event_id: eventId()
        }]})
      }).catch(() => null);
    } catch (_) {}
  }

  function coverMarkup(book, className = '') {
    const title = safe(book?.title || '');
    const author = safe(book?.author || '');
    const cover = safe(book?.cover_url || '');
    const image = cover
      ? `<img src="${cover}" alt="" loading="lazy" referrerpolicy="no-referrer" onerror="this.remove()">`
      : '';
    return `<div class="essential-cover ${className}">${image}<span>${title.slice(0, 1).toUpperCase() || 'L'}</span></div><div class="essential-book-title">${title}</div><div class="essential-book-author">${author}</div>`;
  }

  function selectedBook(key) {
    return books.find(book => book.work_key === key) || shelfBooks().find(book => book.work_key === key) || null;
  }

  function sectionHTML() {
    const c = copy();
    const slots = Array.from({length: MAX_BOOKS}, (_, index) => {
      const book = books[index];
      if (!book) return `<div class="essential-slot empty" aria-hidden="true"><span>${index + 1}</span></div>`;
      return `<div class="essential-slot filled">${coverMarkup(book)}<span class="essential-position">${index + 1}</span></div>`;
    }).join('');
    const primary = canEdit
      ? `<button type="button" class="pbtn solid" data-essential-action="edit">${safe(c.edit)}</button>`
      : `<button type="button" class="pbtn solid" data-essential-action="connect">${safe(c.connect)}</button>`;
    return `<div class="label">${safe(c.label)}</div>
      <div class="essential-head"><div><h3>${safe(c.title)}</h3><p>${safe(books.length ? c.hint : c.empty)}</p></div><span>${books.length}/4</span></div>
      <div class="essential-slots">${slots}</div>
      <div class="profile-actions essential-actions">${primary}${books.length ? `<button type="button" class="pbtn" data-essential-action="share">${safe(c.share)}</button>` : ''}</div>`;
  }

  function bindSection(section) {
    section.querySelector('[data-essential-action="edit"]')?.addEventListener('click', openEditor);
    section.querySelector('[data-essential-action="connect"]')?.addEventListener('click', () => {
      try { if (typeof conectarGoogle === 'function') conectarGoogle(); }
      catch (_) {}
    });
    section.querySelector('[data-essential-action="share"]')?.addEventListener('click', shareCard);
  }

  function renderSection() {
    const profile = global.document.querySelector('#perfil .pcard');
    if (!profile) return;
    let section = global.document.getElementById(SECTION_ID);
    if (!section) {
      section = global.document.createElement('section');
      section.id = SECTION_ID;
      section.className = 'account-box essential-books-box';
      const anchor = profile.querySelector('.profile-metrics') || profile.querySelector('.profile-cta-row');
      if (anchor) anchor.insertAdjacentElement('afterend', section);
      else profile.prepend(section);
    }
    if (!loaded) {
      section.innerHTML = '<div class="essential-loading" aria-live="polite">•••</div>';
      return;
    }
    section.innerHTML = sectionHTML();
    bindSection(section);
  }

  async function loadBooks() {
    if (loading) return;
    loading = true;
    try {
      const response = await global.fetch('/api/eu/essenciais', {credentials: 'same-origin', cache: 'no-store'});
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const payload = await response.json();
      books = Array.isArray(payload.books) ? payload.books.slice(0, MAX_BOOKS) : [];
      canEdit = payload.can_edit === true;
    } catch (_) {
      books = [];
      canEdit = false;
    } finally {
      loaded = true;
      loading = false;
      renderSection();
    }
  }

  function ensureStyles() {
    if (global.document.querySelector('[data-essential-books-styles]')) return;
    const style = global.document.createElement('style');
    style.dataset.essentialBooksStyles = '1';
    style.textContent = `
      .essential-books-box{position:relative;overflow:hidden}.essential-head{display:flex;align-items:flex-end;justify-content:space-between;gap:18px;margin:8px 0 16px}.essential-head h3{margin:0 0 4px;font:500 25px/1.05 "Fraunces",serif}.essential-head p{margin:0;max-width:560px;color:var(--dim);font:400 14px/1.45 "Spectral",serif}.essential-head>span{color:var(--gold);font:700 11px/1 "Space Mono",monospace}.essential-slots{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px}.essential-slot{position:relative;min-width:0}.essential-slot.empty{aspect-ratio:2/3;border:1px dashed color-mix(in srgb,var(--ink),transparent 72%);display:grid;place-items:center;color:var(--dim);font:700 11px/1 "Space Mono",monospace}.essential-cover{position:relative;aspect-ratio:2/3;overflow:hidden;background:color-mix(in srgb,var(--paper),var(--gold) 8%);box-shadow:3px 4px 0 color-mix(in srgb,var(--ink),transparent 85%)}.essential-cover img{position:absolute;inset:0;width:100%;height:100%;object-fit:cover}.essential-cover>span{position:absolute;inset:0;display:grid;place-items:center;color:var(--gold);font:600 italic 28px/1 "Fraunces",serif}.essential-position{position:absolute;right:5px;top:5px;display:grid;place-items:center;width:22px;height:22px;border-radius:50%;background:var(--paper);color:var(--gold);border:1px solid var(--gold);font:700 9px/1 "Space Mono",monospace}.essential-book-title{margin-top:7px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font:500 13px/1.15 "Fraunces",serif}.essential-book-author{margin-top:2px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:var(--dim);font-size:10px}.essential-actions{margin-top:16px}.essential-loading{padding:30px;text-align:center;color:var(--gold);letter-spacing:.3em}
      .essential-modal{position:fixed;z-index:3300;inset:0;display:grid;place-items:end center;padding:18px;background:rgba(10,8,7,.7);backdrop-filter:blur(8px)}.essential-editor{width:min(760px,100%);max-height:min(88vh,850px);overflow:auto;border:1px solid color-mix(in srgb,var(--gold),transparent 45%);border-radius:22px 22px 8px 8px;background:var(--paper);color:var(--ink);padding:24px}.essential-editor-head{display:flex;justify-content:space-between;gap:20px;align-items:flex-start}.essential-editor-head h2{margin:4px 0 6px;font:500 30px/1.05 "Fraunces",serif}.essential-editor-head p{margin:0;color:var(--dim)}.essential-editor-close{border:0;background:transparent;color:var(--dim);font-size:28px;line-height:1;width:40px;height:40px;border-radius:50%}.essential-editor-close:hover,.essential-editor-close:focus-visible{background:color-mix(in srgb,var(--ink),transparent 93%)}.essential-editor-section{margin-top:24px}.essential-editor-label{display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;font:700 10px/1.3 "Space Mono",monospace;letter-spacing:.1em;text-transform:uppercase;color:var(--dim)}.essential-selected{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}.essential-selected-item{position:relative;min-width:0;border:1px solid color-mix(in srgb,var(--ink),transparent 82%);padding:8px;background:color-mix(in srgb,var(--paper),#fff 4%)}.essential-selected-item.empty{aspect-ratio:2/3;display:grid;place-items:center;border-style:dashed;color:var(--dim)}.essential-selected-controls{display:grid;grid-template-columns:repeat(3,1fr);gap:4px;margin-top:8px}.essential-selected-controls button{min-height:30px;border:1px solid color-mix(in srgb,var(--ink),transparent 78%);background:transparent;color:var(--dim);font-size:12px}.essential-shelf-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}.essential-candidate{min-width:0;text-align:left;border:1px solid transparent;background:transparent;color:var(--ink);padding:7px;border-radius:10px}.essential-candidate:hover,.essential-candidate:focus-visible{border-color:var(--gold);background:color-mix(in srgb,var(--gold),transparent 93%)}.essential-candidate.selected{opacity:.48}.essential-candidate .essential-book-title,.essential-candidate .essential-book-author{max-width:100%}.essential-editor-message{min-height:20px;margin-top:10px;color:var(--dim);font-size:12px}.essential-editor-footer{position:sticky;bottom:-24px;display:flex;justify-content:flex-end;gap:10px;margin:24px -24px -24px;padding:16px 24px calc(16px + env(safe-area-inset-bottom));border-top:1px solid color-mix(in srgb,var(--ink),transparent 84%);background:var(--paper)}.theme-dark .essential-editor{box-shadow:0 30px 90px rgba(0,0,0,.55)}
      @media(max-width:620px){.essential-slots,.essential-selected,.essential-shelf-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.essential-modal{padding:0;align-items:end}.essential-editor{border-radius:20px 20px 0 0;max-height:94vh;padding:20px}.essential-editor-footer{margin-left:-20px;margin-right:-20px;margin-bottom:-20px;padding-left:20px;padding-right:20px}.essential-head{align-items:flex-start}.essential-head p{font-size:13px}}
      @media(prefers-reduced-motion:reduce){.essential-modal,.essential-editor,.essential-books-box *{animation:none!important;transition:none!important;scroll-behavior:auto!important}}
    `;
    global.document.head.appendChild(style);
  }

  function modal() {
    return global.document.getElementById(MODAL_ID);
  }

  function closeEditor() {
    modal()?.remove();
    global.document.removeEventListener('keydown', editorKeydown);
  }

  function editorKeydown(event) {
    if (event.key === 'Escape') closeEditor();
  }

  function moveSelection(index, direction) {
    const target = index + direction;
    if (target < 0 || target >= selectedKeys.length) return;
    [selectedKeys[index], selectedKeys[target]] = [selectedKeys[target], selectedKeys[index]];
    renderEditor();
  }

  function removeSelection(index) {
    selectedKeys.splice(index, 1);
    renderEditor();
  }

  function addSelection(key) {
    const c = copy();
    if (selectedKeys.includes(key)) return;
    if (selectedKeys.length >= MAX_BOOKS) {
      const message = modal()?.querySelector('.essential-editor-message');
      if (message) message.textContent = c.full;
      return;
    }
    selectedKeys.push(key);
    renderEditor();
  }

  function renderEditor() {
    const root = modal();
    if (!root) return;
    const c = copy();
    const shelf = shelfBooks();
    const selected = Array.from({length: MAX_BOOKS}, (_, index) => {
      const key = selectedKeys[index];
      const book = key ? selectedBook(key) : null;
      if (!book) return `<div class="essential-selected-item empty"><span>${index + 1}</span></div>`;
      return `<div class="essential-selected-item" data-index="${index}">${coverMarkup(book)}<div class="essential-selected-controls">
        <button type="button" data-move="-1" aria-label="${safe(c.left)}" ${index === 0 ? 'disabled' : ''}>←</button>
        <button type="button" data-remove aria-label="${safe(c.remove)}">×</button>
        <button type="button" data-move="1" aria-label="${safe(c.right)}" ${index === selectedKeys.length - 1 ? 'disabled' : ''}>→</button>
      </div></div>`;
    }).join('');
    const candidates = shelf.length
      ? shelf.map(book => `<button type="button" class="essential-candidate ${selectedKeys.includes(book.work_key) ? 'selected' : ''}" data-work-key="${safe(book.work_key)}" ${selectedKeys.includes(book.work_key) ? 'disabled' : ''}>${coverMarkup(book)}</button>`).join('')
      : `<p class="muted">${safe(c.noShelf)}</p>`;

    root.innerHTML = `<section class="essential-editor" role="dialog" aria-modal="true" aria-labelledby="essentialEditorTitle">
      <div class="essential-editor-head"><div><div class="label">${safe(c.label)}</div><h2 id="essentialEditorTitle">${safe(c.editorTitle)}</h2><p>${safe(c.editorHint)}</p></div><button type="button" class="essential-editor-close" aria-label="${safe(c.close)}">×</button></div>
      <div class="essential-editor-section"><div class="essential-editor-label"><span>${safe(c.selected)}</span><span>${selectedKeys.length}/4</span></div><div class="essential-selected">${selected}</div><div class="essential-editor-message" aria-live="polite"></div></div>
      <div class="essential-editor-section"><div class="essential-editor-label"><span>${safe(c.shelf)}</span></div><div class="essential-shelf-grid">${candidates}</div></div>
      <div class="essential-editor-footer"><button type="button" class="pbtn" data-editor-close>${safe(c.close)}</button><button type="button" class="pbtn solid" data-editor-save ${saving ? 'disabled' : ''}>${safe(saving ? c.saving : c.save)}</button></div>
    </section>`;

    root.querySelector('.essential-editor-close')?.addEventListener('click', closeEditor);
    root.querySelector('[data-editor-close]')?.addEventListener('click', closeEditor);
    root.querySelector('[data-editor-save]')?.addEventListener('click', saveSelection);
    root.querySelectorAll('[data-work-key]').forEach(button => button.addEventListener('click', () => addSelection(button.dataset.workKey || '')));
    root.querySelectorAll('[data-remove]').forEach(button => button.addEventListener('click', () => removeSelection(Number(button.closest('[data-index]')?.dataset.index))));
    root.querySelectorAll('[data-move]').forEach(button => button.addEventListener('click', () => moveSelection(Number(button.closest('[data-index]')?.dataset.index), Number(button.dataset.move))));
  }

  function openEditor() {
    if (!canEdit) {
      try { if (typeof conectarGoogle === 'function') conectarGoogle(); }
      catch (_) {}
      return;
    }
    selectedKeys = books.map(book => book.work_key).filter(Boolean).slice(0, MAX_BOOKS);
    let root = modal();
    if (!root) {
      root = global.document.createElement('div');
      root.id = MODAL_ID;
      root.className = 'essential-modal';
      root.addEventListener('click', event => { if (event.target === root) closeEditor(); });
      global.document.body.appendChild(root);
    }
    global.document.addEventListener('keydown', editorKeydown);
    renderEditor();
    global.requestAnimationFrame(() => root.querySelector('.essential-editor-close')?.focus());
  }

  async function saveSelection() {
    if (saving) return;
    saving = true;
    renderEditor();
    try {
      const response = await global.fetch('/api/eu/essenciais', {
        method: 'PUT', credentials: 'same-origin', cache: 'no-store',
        headers: {'Content-Type': 'application/json', Accept: 'application/json'},
        body: JSON.stringify({work_keys: selectedKeys})
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(payload.detail || `HTTP ${response.status}`);
      books = Array.isArray(payload.books) ? payload.books.slice(0, MAX_BOOKS) : [];
      loaded = true;
      track(books.length ? 'saved' : 'cleared', books.length);
      closeEditor();
      renderSection();
      try { if (typeof toast === 'function') toast(copy().saved); }
      catch (_) {}
    } catch (_) {
      const message = modal()?.querySelector('.essential-editor-message');
      if (message) message.textContent = copy().saveError;
    } finally {
      saving = false;
      if (modal()) renderEditor();
    }
  }

  function roundedRect(ctx, x, y, width, height, radius) {
    ctx.beginPath();
    ctx.roundRect(x, y, width, height, radius);
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

  function wrapCanvasText(ctx, text, maxWidth, maxLines) {
    const words = String(text || '').split(/\s+/).filter(Boolean);
    const lines = [];
    let line = '';
    for (const word of words) {
      const candidate = line ? `${line} ${word}` : word;
      if (!line || ctx.measureText(candidate).width <= maxWidth) line = candidate;
      else { lines.push(line); line = word; }
      if (lines.length === maxLines) break;
    }
    if (lines.length < maxLines && line) lines.push(line);
    if (lines.join(' ').split(' ').length < words.length && lines.length) lines[lines.length - 1] = lines[lines.length - 1].replace(/[.,;:!?-]+$/, '') + '…';
    return lines;
  }

  async function renderCard() {
    const c = copy();
    const canvas = global.document.createElement('canvas');
    canvas.width = 1080;
    canvas.height = 1350;
    const ctx = canvas.getContext('2d');
    const gradient = ctx.createLinearGradient(0, 0, 0, canvas.height);
    gradient.addColorStop(0, '#421416');
    gradient.addColorStop(1, '#17090A');
    ctx.fillStyle = gradient;
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    ctx.fillStyle = '#D6A75B';
    ctx.font = "700 28px 'Space Mono', monospace";
    ctx.textAlign = 'center';
    ctx.fillText('LOMBADA.APP', 540, 86);
    ctx.fillStyle = '#F4EFE6';
    ctx.font = "500 italic 70px Fraunces, serif";
    ctx.fillText(c.cardTitle, 540, 170);
    ctx.fillStyle = 'rgba(244,239,230,.72)';
    ctx.font = "400 28px Spectral, serif";
    ctx.fillText(c.cardSubtitle, 540, 215);

    const positions = [
      [120, 285], [570, 285], [120, 790], [570, 790]
    ];
    const width = 390;
    const coverHeight = 405;
    for (let index = 0; index < MAX_BOOKS; index += 1) {
      const book = books[index];
      const [x, y] = positions[index];
      ctx.save();
      roundedRect(ctx, x, y, width, coverHeight, 12);
      ctx.clip();
      ctx.fillStyle = 'rgba(244,239,230,.08)';
      ctx.fillRect(x, y, width, coverHeight);
      if (book) {
        const image = await loadImage(book.cover_url);
        if (image) {
          const scale = Math.max(width / image.naturalWidth, coverHeight / image.naturalHeight);
          const imageWidth = image.naturalWidth * scale;
          const imageHeight = image.naturalHeight * scale;
          ctx.drawImage(image, x + (width - imageWidth) / 2, y + (coverHeight - imageHeight) / 2, imageWidth, imageHeight);
        } else {
          ctx.fillStyle = index % 2 ? '#6A2A2F' : '#8C5B35';
          ctx.fillRect(x, y, width, coverHeight);
          ctx.fillStyle = '#F4EFE6';
          ctx.font = "600 italic 120px Fraunces, serif";
          ctx.textAlign = 'center';
          ctx.fillText(String(book.title || 'L').charAt(0).toUpperCase(), x + width / 2, y + coverHeight / 2 + 35);
        }
      }
      ctx.restore();
      ctx.strokeStyle = 'rgba(214,167,91,.65)';
      ctx.lineWidth = 2;
      roundedRect(ctx, x, y, width, coverHeight, 12);
      ctx.stroke();
      ctx.fillStyle = '#D6A75B';
      ctx.beginPath();
      ctx.arc(x + 28, y + 28, 20, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = '#17090A';
      ctx.font = "700 18px 'Space Mono', monospace";
      ctx.textAlign = 'center';
      ctx.fillText(String(index + 1), x + 28, y + 34);

      if (book) {
        ctx.fillStyle = '#F4EFE6';
        ctx.font = "500 28px Fraunces, serif";
        ctx.textAlign = 'left';
        const titleLines = wrapCanvasText(ctx, book.title, width, 2);
        titleLines.forEach((line, lineIndex) => ctx.fillText(line, x, y + coverHeight + 42 + lineIndex * 31));
        ctx.fillStyle = 'rgba(244,239,230,.66)';
        ctx.font = "400 20px Spectral, serif";
        const authorLines = wrapCanvasText(ctx, book.author, width, 1);
        if (authorLines[0]) ctx.fillText(authorLines[0], x, y + coverHeight + 110);
      }
    }

    let handle = '';
    try { handle = String(meuHandle || '').trim(); } catch (_) {}
    ctx.textAlign = 'center';
    ctx.fillStyle = 'rgba(244,239,230,.72)';
    ctx.font = "400 22px 'Space Mono', monospace";
    ctx.fillText(handle ? `@${handle}` : 'LOMBADA', 540, 1310);
    return canvas;
  }

  function canvasBlob(canvas) {
    return new Promise(resolve => canvas.toBlob(resolve, 'image/png', 0.94));
  }

  async function shareCard() {
    try {
      const canvas = await renderCard();
      const blob = await canvasBlob(canvas);
      if (!blob) throw new Error('blob');
      const file = new File([blob], 'lombada-quatro-essenciais.png', {type: 'image/png'});
      if (global.navigator.share && global.navigator.canShare?.({files: [file]})) {
        await global.navigator.share({files: [file], title: copy().cardTitle});
      } else {
        const link = global.document.createElement('a');
        link.href = URL.createObjectURL(blob);
        link.download = file.name;
        link.click();
        global.setTimeout(() => URL.revokeObjectURL(link.href), 2000);
        try { if (typeof toast === 'function') toast(copy().download); } catch (_) {}
      }
      track('shared', books.length);
    } catch (error) {
      if (error?.name === 'AbortError') return;
      try { if (typeof toast === 'function') toast(copy().shareError); } catch (_) {}
    }
  }

  function installProfileHook() {
    if (originalRenderProfile || typeof global.renderPerfil !== 'function') return;
    originalRenderProfile = global.renderPerfil;
    global.renderPerfil = function renderProfileWithEssentials(...args) {
      const result = originalRenderProfile.apply(this, args);
      global.queueMicrotask(renderSection);
      return result;
    };
  }

  async function init() {
    ensureStyles();
    installProfileHook();
    renderSection();
    await loadBooks();
  }

  init();
})(window);
