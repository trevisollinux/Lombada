const $ = s => document.querySelector(s);
const esc = s => (s||'').toString().replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const capaProxy = u => u ? '/api/capa?url='+encodeURIComponent(u) : '';
function slugEditora(nome){
  const semAcento=String(nome||'').normalize('NFKD').replace(new RegExp('[̀-ͯ]','g'),'').toLowerCase().trim();
  return semAcento.replace(/[^a-z0-9]+/g,'-').replace(/^-+|-+$/g,'')||'editora';
}
function linkEditoraHTML(nome){
  if(!(nome||'').trim()) return esc(nome);
  return `<a class="publisher-link" href="/editora/${slugEditora(nome)}" target="_blank" rel="noopener" onclick="event.stopPropagation()">${esc(nome)}</a>`;
}

const SUGESTOES = [
  {titulo:'Crime e Castigo',autor:'Fiódor Dostoiévski'},
  {titulo:'A Montanha Mágica',autor:'Thomas Mann'},
  {titulo:'Ulisses',autor:'James Joyce'},
  {titulo:'Orlando',autor:'Virginia Woolf'},
  {titulo:'O Aleph',autor:'Jorge Luis Borges'},
  {titulo:'O Morro dos Ventos Uivantes',autor:'Emily Brontë'},
];

let meuHandle='', minhaConta={logado:false,provedor:'anonimo'}, escolha=null, edicaoSel=null, notaSel=0;
let resultadosArr=[], obrasAgrupadas=[], edicoesAtual=[], obraSocial=null, prateleira=[], diarioEntradas=[], cardAtual=null, notaEdit=0, diarioEditId=null;
let cardCoverIndex=0, cardCoverAutoLowRes=false, cardCoverUserChanged=false;
const CARD_THEME_KEY='lombada_card_theme';
let cardTheme=localStorage.getItem(CARD_THEME_KEY)||'auto', cardIncludeExcerpt=false, cardContext={type:'leitura',source:null};
let filtroEstante='Todos';
let feedItems=[], feedFollowingCount=0, feedTab=localStorage.getItem('lombada_feed_tab')||'discover', discoverReaders=[];
let ultimoLivroSalvo=null;
let cardOpener=null;
let timerDestaqueLivro=null;
let visualizacaoEstante=localStorage.getItem('lombada_view_estante')==='lista'?'lista':'grade';
let navAtual={aba:'buscar',busca:'home',estanteSub:'shelf'};
let restaurandoHistorico=false;
const LOGIN_HINT_KEY='lombada_login_hint_dismissed';
const NAV_STATE_KEY='lombada_nav_state';
const DEBUG = localStorage.getItem('lombada_debug') === '1';
function debugLog(...args){ if(DEBUG) console.log(...args); }
let appVersion='dev';
const INSTALL_DISMISSED_KEY='lombada_install_dismissed_at';
let deferredInstallPrompt=null;
let installPromptConsumed=false;
let swRefreshing=false;
let swUpdateAccepted=false;

const THEME_KEY='lombada_theme';

function focarTelaBusca(id){
  const el = document.querySelector(id);
  requestAnimationFrame(() => {
    if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
    else window.scrollTo({ top: 0, behavior: 'smooth' });
  });
}

function setupWorkActionDelegation(){
  if(document.__lombadaWorkActionDelegation) return;
  document.__lombadaWorkActionDelegation=true;
  document.addEventListener('click', event => {
    const target = event.target instanceof Element ? event.target : event.target?.parentElement;
    const btn = target?.closest('[data-work-action]');
    if (!btn) return;

    event.preventDefault();
    event.stopPropagation();

    const action = btn.dataset.workAction;

    if (action === 'register-reading') {
      registrarLeituraObra(event);
      return;
    }

    if (action === 'see-editions') {
      const lista = document.querySelector('.editions');
      if (lista) {
        focarTelaBusca('.editions');
      } else {
        toast(t('no_editions_register_manual'));
      }
      return;
    }

    if (action === 'manual-edition') {
      abrirManual(event);
      return;
    }

    if (action === 'choose-edition') {
      escolherEdicao(Number(btn.dataset.editionIndex), event);
    }
  }, true);
}
setupWorkActionDelegation();

/* teclado global: ESC fecha o modal e Enter/Espaço ativam elementos role="button" */
function setupGlobalKeyboard(){
  if(document.__lombadaKeyboard) return;
  document.__lombadaKeyboard=true;
  document.addEventListener('keydown', event => {
    if(event.key==='Escape' && modalAberto()){ event.preventDefault(); fecharModal(); return; }
    if(event.key==='Enter' || event.key===' '){
      const el=event.target;
      if(el instanceof Element && el.getAttribute('role')==='button' && !el.matches('button,a,input,textarea,select')){
        event.preventDefault();
        el.click();
      }
    }
  });
}
setupGlobalKeyboard();

function temaInicial(){
  const salvo=localStorage.getItem(THEME_KEY);
  return salvo==='light'?'light':'dark';
}
function aplicarTema(tema){
  const t=tema==='dark'?'dark':'light';
  document.body.classList.toggle('theme-dark',t==='dark');
  document.body.classList.toggle('theme-light',t==='light');
  document.body.setAttribute('data-theme',t);
  document.querySelectorAll('[name=\"themeChoice\"]').forEach(input=>{ input.checked=input.value===t; });
}
function definirTema(tema){
  const prox=tema==='light'?'light':'dark';
  localStorage.setItem(THEME_KEY,prox);
  aplicarTema(prox);
}
function atualizarSeletorIdioma(){
  const locale=getLocale();
  document.querySelectorAll('[data-locale]').forEach(btn=>{
    const active=btn.getAttribute('data-locale')===locale;
    btn.classList.toggle('active',active);
    btn.setAttribute('aria-pressed',active?'true':'false');
  });
  document.querySelectorAll('[name=\"localeChoice\"]').forEach(input=>{ input.checked=input.value===locale; });
}
function mudarIdioma(locale){
  setLocale(locale);
  atualizarSeletorIdioma();
  renderChips();
  renderLendoAgora();
  renderPrateleira();
  renderDiario();
  if(navAtual.aba==='buscar' && navAtual.busca==='edicoes') renderEdicoes();
  if(navAtual.aba==='buscar' && navAtual.busca==='form' && edicaoSel) escolherEdicao(edicoesAtual.indexOf(edicaoSel));
  if(navAtual.aba==='buscar' && navAtual.busca==='manual') abrirManual();
  if(cardAtual) renderDetalheLivro(cardAtual);
  if(navAtual.aba==='buscar' && navAtual.busca==='edicoes' && obraSocial) renderEdicoes();
  if($('#secPerfil')?.style.display!=='none') renderPerfil();
  if($('#secFeed')?.style.display!=='none') renderFeed();
}
function statusLabel(status){
  if(status==='Lido') return t('status_read');
  if(status==='Lendo') return t('status_reading');
  if(status==='Quero ler') return t('status_want');
  if(status==='Todos') return t('filter_all');
  return status;
}
aplicarTema(temaInicial());

let conviteLoginPendente=false;

function estrelasStr(n){n=n||0;let o='';for(let i=1;i<=5;i++)o+=(i<=n?'★':(i-0.5===n?'⯪':'☆'));return o;}
function hue(t){let h=0;for(let i=0;i<(t||'?').length;i++)h=(h*31+t.charCodeAt(i))%360;return h;}

function loginHintDispensado(){
  return localStorage.getItem(LOGIN_HINT_KEY)==='1';
}
function deveMostrarConviteLogin(){
  return !minhaConta.logado && prateleira.length > 0 && !loginHintDispensado();
}
function conectarGoogle(){
  location.href='/api/auth/google/login';
}
function continuarSemConta(){
  localStorage.setItem(LOGIN_HINT_KEY,'1');
  conviteLoginPendente=false;
  renderPrateleira();
  renderDiario();
  aplicarSubabaEstante(navAtual.estanteSub||'shelf');
}

function conviteLoginHTML(){
  if(!deveMostrarConviteLogin()) return '';
  const texto=conviteLoginPendente
    ? t('login_saved_hint')
    : t('login_hint');
  return `<div class="login-hint" role="status">
    <p>${texto}</p>
    <div class="login-hint-actions">
      <button class="login-hint-primary" onclick="conectarGoogle()">${t('connect_google')}</button>
      <button class="login-hint-secondary" onclick="continuarSemConta()">${t('continue_without_account')}</button>
    </div>
  </div>`;
}
function marcarConviteLoginAposSalvar(){
  conviteLoginPendente=!minhaConta.logado && !loginHintDispensado();
}

function toast(msg){
  const antigo=$('#toast');
  if(antigo) antigo.remove();
  const el=document.createElement('div');
  el.id='toast';
  el.className='toast';
  el.textContent=msg;
  document.body.appendChild(el);
  requestAnimationFrame(()=>el.classList.add('show'));
  setTimeout(()=>{ el.classList.remove('show'); setTimeout(()=>el.remove(),300); },3600);
}

function mostrarBannerPwa({id, mensagem, acaoTexto, acao, secundarioTexto, secundario}={}){
  const antigo=document.getElementById(id||'pwaBanner');
  if(antigo) antigo.remove();
  const el=document.createElement('div');
  el.id=id||'pwaBanner';
  el.className='pwa-banner';
  el.setAttribute('role','status');
  el.innerHTML=`<span>${esc(mensagem||'')}</span><div class="pwa-banner-actions"></div>`;
  const actions=el.querySelector('.pwa-banner-actions');
  if(acaoTexto && acao){
    const btn=document.createElement('button');
    btn.type='button'; btn.textContent=acaoTexto;
    btn.addEventListener('click',acao);
    actions.appendChild(btn);
  }
  if(secundarioTexto && secundario){
    const btn=document.createElement('button');
    btn.type='button'; btn.className='ghost'; btn.textContent=secundarioTexto;
    btn.addEventListener('click',secundario);
    actions.appendChild(btn);
  }
  document.body.appendChild(el);
  requestAnimationFrame(()=>el.classList.add('show'));
  return el;
}

function isStandalonePwa(){
  return window.matchMedia?.('(display-mode: standalone)')?.matches || window.navigator.standalone === true;
}
function installDispensadoRecentemente(){
  const ts=Number(localStorage.getItem(INSTALL_DISMISSED_KEY)||0);
  return ts && Date.now()-ts < 14*24*60*60*1000;
}
function deveMostrarInstalar(){
  return !!deferredInstallPrompt && !installPromptConsumed && !isStandalonePwa() && !installDispensadoRecentemente();
}
function instalarLombada(){
  if(!deveMostrarInstalar()) return;
  const promptEvent=deferredInstallPrompt;
  installPromptConsumed=true;
  deferredInstallPrompt=null;
  document.getElementById('installCtaBox')?.remove();
  document.getElementById('installBanner')?.remove();
  promptEvent.prompt();
  promptEvent.userChoice.then(choice=>{
    if(choice.outcome !== 'accepted') localStorage.setItem(INSTALL_DISMISSED_KEY,String(Date.now()));
  }).catch(()=>localStorage.setItem(INSTALL_DISMISSED_KEY,String(Date.now())));
}
function dispensarInstalacao(){
  localStorage.setItem(INSTALL_DISMISSED_KEY,String(Date.now()));
  document.getElementById('installBanner')?.remove();
  renderPerfil();
}
function installCtaHTML(){
  if(!deveMostrarInstalar()) return '';
  return `<div id="installCtaBox" class="account-box install-box"><div class="label">${t('pwa_app_label')}</div><p>${t('pwa_install_message')}</p><div class="profile-actions"><button class="pbtn solid" type="button" onclick="instalarLombada()">${t('pwa_install_action')}</button><button class="pbtn" type="button" onclick="dispensarInstalacao()">${t('pwa_install_dismiss')}</button></div></div>`;
}
function talvezMostrarBannerInstalacao(){
  if(!deveMostrarInstalar() || document.getElementById('installBanner')) return;
  mostrarBannerPwa({
    id:'installBanner',
    mensagem:t('pwa_install_message'),
    acaoTexto:t('pwa_install_action'),
    acao:instalarLombada,
    secundarioTexto:t('pwa_install_dismiss'),
    secundario:dispensarInstalacao
  });
}
function registrarPwa(){
  window.addEventListener('beforeinstallprompt', event => {
    event.preventDefault();
    if(isStandalonePwa()) return;
    deferredInstallPrompt=event;
    if($('#secPerfil')?.style.display!=='none') renderPerfil();
    setTimeout(talvezMostrarBannerInstalacao,2400);
  });
  window.addEventListener('appinstalled', () => {
    installPromptConsumed=true;
    deferredInstallPrompt=null;
    localStorage.setItem(INSTALL_DISMISSED_KEY,String(Date.now()));
    document.getElementById('installBanner')?.remove();
    toast(t('pwa_installed'));
  });
  if(!('serviceWorker' in navigator)) return;
  window.addEventListener('load', async () => {
    try{
      const registration=await navigator.serviceWorker.register('/sw.js');
      const mostrarAtualizacao=worker=>{
        if(!worker) return;
        mostrarBannerPwa({id:'updateBanner',mensagem:t('pwa_update_available'),acaoTexto:t('pwa_update_action'),acao:()=>{ swUpdateAccepted=true; worker.postMessage({type:'SKIP_WAITING'}); }});
      };
      if(registration.waiting) mostrarAtualizacao(registration.waiting);
      registration.addEventListener('updatefound',()=>{
        const novo=registration.installing;
        novo?.addEventListener('statechange',()=>{
          if(novo.state==='installed' && navigator.serviceWorker.controller) mostrarAtualizacao(novo);
        });
      });
      navigator.serviceWorker.addEventListener('controllerchange',()=>{
        if(swRefreshing || !swUpdateAccepted) return;
        swRefreshing=true;
        toast(t('pwa_update_installed'));
        window.location.reload();
      });
    }catch(err){ console.warn('service worker não registrado',err); }
  });
}
registrarPwa();


function limparErroFormulario(form){
  if(!form) return;
  form.querySelectorAll('.form-error').forEach(el=>el.remove());
}
function mostrarErroFormulario(form,mensagem){
  if(!form){ toast(mensagem); return; }
  limparErroFormulario(form);
  const el=document.createElement('div');
  el.className='form-error';
  el.setAttribute('role','alert');
  el.textContent=mensagem;
  const botao=form.querySelector('.btn-primary, button[type="submit"], button');
  if(botao?.parentNode) botao.parentNode.insertBefore(el,botao);
  else form.appendChild(el);
  el.scrollIntoView({behavior:'smooth',block:'nearest'});
}
function confirmarEmDoisPassos(botao, chave, acao, texto=t('confirm_removal')){
  if(!botao) return acao();
  const agora=Date.now();
  const confirmado=botao.dataset.confirmKey===String(chave) && Number(botao.dataset.confirmUntil||0)>agora;
  if(confirmado){
    delete botao.dataset.confirmKey;
    delete botao.dataset.confirmUntil;
    return acao();
  }
  const original=botao.textContent;
  botao.dataset.confirmKey=String(chave);
  botao.dataset.confirmUntil=String(agora+4200);
  botao.dataset.confirmOriginal=original;
  botao.textContent=texto;
  botao.classList.add('needs-confirm');
  setTimeout(()=>{
    if(botao.dataset.confirmKey===String(chave)){
      botao.textContent=botao.dataset.confirmOriginal||original;
      botao.classList.remove('needs-confirm');
      delete botao.dataset.confirmKey;
      delete botao.dataset.confirmUntil;
      delete botao.dataset.confirmOriginal;
    }
  },4200);
}

function normalizarDuplicidade(v){ return (v||'').toString().trim().toLowerCase().replace(/\s+/g,' '); }
function normalizarIsbnLocal(v){ return (v||'').toString().replace(/[^0-9Xx]/g,'').toUpperCase(); }
function chaveFallbackLeitura(x){
  return [normalizarDuplicidade(x.work_key||x.titulo),normalizarDuplicidade(x.editora),x.ano||'',normalizarDuplicidade(x.tradutor)].join('|');
}
function encontrarLeituraDuplicada(body){
  const isbn=normalizarIsbnLocal(body.isbn);
  return prateleira.find(l=>
    (body.edicao_id&&l.edicao_id===body.edicao_id)||
    (body.ol_edition_key&&l.ol_edition_key===body.ol_edition_key)||
    (isbn&&normalizarIsbnLocal(l.isbn)===isbn)||
    (chaveFallbackLeitura(l)===chaveFallbackLeitura({work_key:body.work_key,titulo:body.titulo,editora:body.editora,ano:body.ano_edicao,tradutor:body.tradutor}))
  );
}
function avisarDuplicado(leituraId){
  toast(t('duplicate_book'));
  fecharModalParaNavegacao();
  limparBusca();
  mostrarBusca('home',{registrar:false});
  irPara('estante',{recarregar:false});
  setTimeout(()=>{
    const idx=prateleira.findIndex(l=>l.leitura_id===leituraId);
    if(idx>=0) abrirCard(idx,{registrar:false});
  },120);
}
async function payloadErro(r){
  try{ return await r.json(); }catch(e){ return null; }
}

function tratarMensagemConta(){
  const params=new URLSearchParams(location.search);
  const conta=params.get('conta');
  if(conta==='ok') toast(t('account_connected_success'));
  if(conta==='erro') toast(t('account_connected_error'));
  if(conta==='state_expirado') toast(t('account_state_expired'));
  if(conta){
    params.delete('conta');
    const qs=params.toString();
    history.replaceState(history.state || estadoNav('buscar','home'), '', location.pathname+(qs?'?'+qs:'')+location.hash);
  }
}

function extrairBuscaDeepLink(){
  const params=new URLSearchParams(location.search);
  const q=params.get('q');
  if(!q) return '';
  params.delete('q');
  const qs=params.toString();
  history.replaceState(history.state || estadoNav('buscar','home'), '', location.pathname+(qs?'?'+qs:'')+location.hash);
  return q;
}

const TINTAS_CAPA = ['#8B0E20','#11100E','#1E2F3F','#1F3A2E','#9A4A2F','#DCCEB6'];
const PAPEL_CAPA = '#F1E6D2';
function hashLivro(titulo,autor){
  const txt=`${titulo||''}|${autor||''}`.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g,'');
  let h=2166136261;
  for(let i=0;i<txt.length;i++){h^=txt.charCodeAt(i);h=Math.imul(h,16777619);}
  return h>>>0;
}
function capaArteDados(titulo,autor,variacao=0){
  const h=hashLivro(titulo,autor)+variacao;
  const layout=['classic','modern','minimal','bold','stripe'][h%5];
  const tinta=TINTAS_CAPA[h%TINTAS_CAPA.length];
  const tinta2=TINTAS_CAPA[Math.floor(h/7)%TINTAS_CAPA.length];
  return {hash:h,layout,tinta,tinta2,papel:PAPEL_CAPA};
}
function getSafeCoverUrl(item){
  if(!item)return null;
  const raw=item.capa_url||item.cover_url||item.capa||null;
  if(typeof raw!=='string')return null;
  const url=raw.trim();
  if(!url || url==='#' || /^javascript:/i.test(url) || /^data:/i.test(url))return null;
  return url;
}
function hasUsableCover(item){ return !!getSafeCoverUrl(item); }
function coverFallbackHTML(titulo,autor,extra='',variacao=0){
  const d=capaArteDados(titulo,autor,variacao);
  const tituloCurto=trechoTexto(titulo||t('untitled')||'',58);
  const autorCurto=trechoTexto(autor||'',34);
  const meta=autorCurto?`<div class="cover-art-author">${esc(autorCurto)}</div>`:'';
  return `<div class="cover cover-art ${d.layout}" data-initial="${esc((tituloCurto||'?').charAt(0).toUpperCase())}" style="--cover-ink:${d.tinta};--cover-ink-2:${d.tinta2};--cover-paper:${d.papel}">
    <div class="cover-art-rule"></div>
    <div class="cover-art-copy">
      <div class="cover-art-title">${esc(tituloCurto)}</div>
      ${meta}
    </div>
    <div class="cover-art-meta">Lombada</div>
    ${extra||''}</div>`;
}
function trocarParaCapaArte(img){
  const el=img?.parentElement;if(!el)return;
  const title=img.getAttribute('data-title')||'';
  const author=img.getAttribute('data-author')||'';
  const extra=el.querySelector('.pt,.stars-overlay')?.outerHTML||'';
  let html=coverFallbackHTML(title,author,extra);
  if(el.classList.contains('dcover')) html=html.replace('class="cover','class="dcover');
  if(el.classList.contains('shelf-cover')) html=html.replace('class="cover','class="shelf-cover');
  el.outerHTML=html;
}
function coverHTML(titulo,autor,capa,extra){
  const cover=getSafeCoverUrl({capa_url:capa});
  if(cover){
    return `<div class="cover">
      <img src="${esc(capaProxy(cover))}" alt="" loading="lazy" data-title="${esc(titulo)}" data-author="${esc(autor)}" onerror="trocarParaCapaArte(this)">
      ${extra||''}</div>`;
  }
  return coverFallbackHTML(titulo,autor,extra);
}

/* navegação entre abas */
function estadoNav(aba=navAtual.aba,busca=navAtual.busca,modal=false,estanteSub=navAtual.estanteSub||'shelf'){
  return {lombada:true,aba,busca,modal,estanteSub,q:$('#q')?.value||'',work_key:escolha?.work_key||'',obraIndexAtual:Number.isInteger(obrasAgrupadas.indexOf(escolha))?obrasAgrupadas.indexOf(escolha):-1};
}
function salvarEstadoNav(estado=estadoNav()){
  try{ sessionStorage.setItem(NAV_STATE_KEY,JSON.stringify({...estado,timestamp:Date.now()})); }catch(e){}
}
function lerEstadoNavSalvo(){
  try{
    const raw=sessionStorage.getItem(NAV_STATE_KEY); if(!raw)return null;
    const st=JSON.parse(raw);
    if(!st || !st.lombada || (Date.now()-(st.timestamp||0)>24*60*60*1000))return null;
    return st;
  }catch(e){ return null; }
}
function modalAberto(){
  return $('#modal')?.classList.contains('open');
}
function fecharModalDireto(){
  $('#modal')?.classList.remove('open');
  const editPanel=$('#editPanel');
  if(editPanel) editPanel.style.display='none';
  if(cardOpener && typeof cardOpener.focus==='function'){ try{ cardOpener.focus(); }catch(e){} }
  cardOpener=null;
}
function fecharModalParaNavegacao(){
  if(!modalAberto())return;
  const estado=estadoNav(navAtual.aba,navAtual.busca,false);
  fecharModalDireto();
  if(history.state && history.state.lombada && history.state.modal) history.replaceState(estado,'');
}
function registrarHistorico(aba,busca,replace=false,estanteSub=navAtual.estanteSub||'shelf'){
  if(!restaurandoHistorico) fecharModalParaNavegacao();
  navAtual={aba,busca,estanteSub};
  if(restaurandoHistorico)return;
  const estado=estadoNav(aba,busca,false,estanteSub);
  salvarEstadoNav(estado);
  if(replace) history.replaceState(estado,'');
  else history.pushState(estado,'');
}
function aplicarSubabaEstante(subaba=navAtual.estanteSub||'shelf'){
  const ativa=subaba==='diario'?'diario':'shelf';
  navAtual.estanteSub=ativa;
  const prateleiraEl=$('#prateleira');
  const diarioEl=$('#diario');
  if(prateleiraEl) prateleiraEl.style.display=ativa==='shelf'?'':'none';
  if(diarioEl) diarioEl.style.display=ativa==='diario'?'':'none';
  $('#subtabShelf')?.classList.toggle('active',ativa==='shelf');
  $('#subtabDiario')?.classList.toggle('active',ativa==='diario');
  $('#subtabShelf')?.setAttribute('aria-selected',ativa==='shelf'?'true':'false');
  $('#subtabDiario')?.setAttribute('aria-selected',ativa==='diario'?'true':'false');
  const shareBtn=document.getElementById('shelfShareButton');
  if(shareBtn) shareBtn.hidden=ativa==='diario';
}
function irPara(aba,opcoes={}){
  if(aba==='diario'){ aba='estante'; opcoes={...opcoes,subaba:'diario'}; }
  const resetBusca=opcoes.resetBusca ?? aba==='buscar';
  const registrar=opcoes.registrar ?? true;
  const estanteSub=aba==='estante' ? (opcoes.subaba||navAtual.estanteSub||'shelf') : (navAtual.estanteSub||'shelf');
  const secs={buscar:'#secBuscar',feed:'#secFeed',estante:'#secEstante',perfil:'#secPerfil'};
  for(const k in secs) $(secs[k]).style.display = (k===aba)?'':'none';
  $('#tabBuscar').classList.toggle('active',aba==='buscar');
  $('#tabFeed')?.classList.toggle('active',aba==='feed');
  $('#tabEstante').classList.toggle('active',aba==='estante');
  $('#tabPerfil').classList.toggle('active',aba==='perfil');
  if(aba==='buscar' && resetBusca){ $('#q').value=''; limparBusca(); mostrarBusca('home',{registrar:false}); }
  const recarregarEstante=opcoes.recarregar ?? true;
  if(aba==='feed') carregarFeed();
  if(aba==='estante'){
    aplicarSubabaEstante(estanteSub);
    if(recarregarEstante) carregarPrateleira();
    else renderDiario();
  }
  if(aba==='perfil') renderPerfil();
  navAtual={aba,busca:aba==='buscar'?navAtual.busca:'home',estanteSub};
  if(registrar) registrarHistorico(navAtual.aba,navAtual.busca,false,navAtual.estanteSub);
  if(opcoes.scrollTop !== false) window.scrollTo({top:0,behavior:'smooth'});
}

/* pilha de telas DENTRO da aba buscar: home → resultados → edicoes → form.
   mostra exatamente uma de cada vez (mata o "carrega embaixo"). */
function mostrarBusca(tela,opcoes={}){
  const registrar=opcoes.registrar ?? tela!=='home';
  const telas={home:'#homeFeed',resultados:'#resultados',edicoes:'#edicoes',form:'#form',manual:'#manual'};
  for(const k in telas) $(telas[k]).style.display = (k===tela)?'':'none';
  navAtual={...navAtual,aba:'buscar',busca:tela};
  if(registrar) registrarHistorico('buscar',tela);
  salvarEstadoNav();
  window.scrollTo({top:0,behavior:'smooth'});
}
function aplicarHistorico(estado){
  const proximo=estado && estado.lombada ? estado : (lerEstadoNavSalvo() || estadoNav('buscar','home'));
  const deveReabrirModal=!!proximo.modal;
  if(modalAberto() && !deveReabrirModal) fecharModalDireto();
  restaurandoHistorico=true;
  irPara(proximo.aba,{registrar:false,resetBusca:false,subaba:proximo.estanteSub||'shelf'});
  if(proximo.aba==='buscar'){
    if(proximo.q) $('#q').value=proximo.q;
    mostrarBusca(proximo.busca||'home',{registrar:false});
    if(proximo.busca==='resultados' && proximo.q) buscar();
  }
  navAtual={aba:proximo.aba,busca:proximo.busca||'home',estanteSub:proximo.estanteSub||'shelf'};
  restaurandoHistorico=false;
  if(deveReabrirModal && Number.isInteger(proximo.card) && prateleira[proximo.card]) abrirCard(proximo.card,{registrar:false});
}
window.onpopstate=e=>aplicarHistorico(e.state);


/* ── sugestões de busca: recentes (localStorage) + mais buscadas (API) ── */
const RECENTES_KEY='lombada_buscas_recentes';
function buscasRecentes(){
  try{ const v=JSON.parse(localStorage.getItem(RECENTES_KEY)); return Array.isArray(v)?v:[]; }
  catch(e){ return []; }
}
function lembrarBuscaRecente(q){
  q=(q||'').trim();
  if(q.length<2) return;
  const lista=buscasRecentes().filter(x=>normBusca(x)!==normBusca(q));
  lista.unshift(q);
  try{ localStorage.setItem(RECENTES_KEY,JSON.stringify(lista.slice(0,8))); }catch(e){}
}
function limparBuscasRecentes(){
  try{ localStorage.removeItem(RECENTES_KEY); }catch(e){}
  onQFocus();
}
let buscasPopularesCache=null;
async function carregarBuscasPopulares(){
  if(buscasPopularesCache) return buscasPopularesCache;
  try{
    const r=await fetch('/api/buscas/populares');
    if(r.ok) buscasPopularesCache=await r.json();
  }catch(e){}
  return buscasPopularesCache||[];
}
function termoChipHTML(termo){
  return `<button type="button" class="chip" data-termo="${esc(termo)}" onclick="buscarSugestao(this)">${esc(termo)}</button>`;
}
async function renderSugestoesBusca(){
  const box=$('#searchSuggest');
  if(!box) return false;
  const recentes=buscasRecentes();
  const populares=await carregarBuscasPopulares();
  let html='';
  if(recentes.length){
    html+=`<div class="suggest-group"><div class="suggest-head"><div class="label">${t('recent_searches')}</div><button type="button" class="suggest-clear" onclick="limparBuscasRecentes()">${t('clear_recent_searches')}</button></div><div class="chips">${recentes.map(termoChipHTML).join('')}</div></div>`;
  }
  const pops=(populares||[]).map(p=>p&&p.termo).filter(Boolean).filter(termo=>!recentes.some(r=>normBusca(r)===normBusca(termo)));
  if(pops.length){
    html+=`<div class="suggest-group"><div class="label">${t('popular_searches')}</div><div class="chips">${pops.map(termoChipHTML).join('')}</div></div>`;
  }
  box.innerHTML=html;
  return !!html;
}
function buscarSugestao(el){
  const termo=el&&el.getAttribute('data-termo')||'';
  const box=$('#searchSuggest'); if(box) box.hidden=true;
  if(termo) buscarTermo(termo);
}
async function onQFocus(){
  if(($('#q').value||'').trim()) return;
  const tem=await renderSugestoesBusca();
  const box=$('#searchSuggest');
  if(box) box.hidden=!tem || document.activeElement!==$('#q');
}
function onQBlur(){
  setTimeout(()=>{ const box=$('#searchSuggest'); if(box) box.hidden=true; },150);
}

/* mostra/esconde feed da home conforme há busca */
function onQInput(){
  const v=$('#q').value.trim();
  const box=$('#searchSuggest');
  if(v){ if(box) box.hidden=true; return; }
  if(box) box.hidden=true;
  limparBusca(); mostrarBusca('home',{registrar:false}); registrarHistorico('buscar','home');
  if(box) renderSugestoesBusca().then(tem=>{ if(document.activeElement===$('#q')) box.hidden=!tem; });
}
function limparBusca(){
  resultadosArr=[];
  obrasAgrupadas=[];
  edicoesAtual=[];
  escolha=null;
  edicaoSel=null;
  obraSocial=null;
  $('#resultados').innerHTML='';
  $('#edicoes').innerHTML='';
  $('#form').innerHTML='';
  $('#manual').innerHTML='';
}

/* feed da home — obras populares como mini estante */
function normalizarObraPopular(o){
  return typeof o==='string' ? {titulo:o,autor:''} : (o||{});
}
function renderObrasPopulares(obras){
  const box=$('#populares');
  if(!box) return;
  const lista=(obras&&obras.length?obras:SUGESTOES).map(normalizarObraPopular);
  box.innerHTML=lista.map((o,i)=>`<div class="book" role="button" tabindex="0" onclick="abrirObraPopular(${i})" aria-label="${esc(o.titulo)}">
    ${coverHTML(o.titulo,o.autor,o.capa_url,'')}
    <div class="t">${esc(o.titulo)}</div>
    ${o.autor?`<div class="a">${esc(o.autor)}</div>`:''}</div>`).join('');
  box._obrasPopulares=lista;
}
function renderChips(){
  const hint=$('#searchHint');
  if(hint) hint.remove();
  renderObrasPopulares(SUGESTOES);
}
async function carregarObrasPopulares(){
  const box=$('#populares');
  if(box) box.innerHTML=`<div class="empty">${t('loading_popular_works')}</div>`;
  try{
    const r=await fetch('/api/explore/populares');
    if(!r.ok) throw new Error('popular works');
    const obras=await r.json();
    renderObrasPopulares(obras);
  }catch(e){
    renderObrasPopulares(SUGESTOES);
  }
}
function abrirObraPopular(i){
  const obras=$('#populares')?._obrasPopulares||SUGESTOES;
  const obra=normalizarObraPopular(obras[i]);
  if(obra.edicoes?.length || obra.edicao_isbn){
    escolha={...obra, edicoes:obra.edicoes||[], edicao_isbn:obra.edicao_isbn||null};
    obrasAgrupadas=[escolha];
    verEdicoes(0);
    return;
  }
  buscarTermo(obra.titulo||'');
}

function abrirDiarioLeitura(idx){
  if(idx<0) return;
  irPara('estante',{subaba:'diario'});
  abrirCard(idx,{registrar:false});
  setTimeout(()=>{
    const alvo=document.getElementById('diaryNewForm')||document.querySelector('[data-diary-form]');
    alvo?.scrollIntoView({behavior:'smooth',block:'start'});
    alvo?.querySelector('input, textarea, button')?.focus?.({preventScroll:true});
  },120);
}
function lendoAgoraCard(l,idx,compacto=false){
  const progresso=progressoLeitura(l);
  return `<div class="reading-now-card ${compacto?'compact':''}" role="button" tabindex="0" onclick="abrirCard(${idx})" aria-label="${esc(l.titulo)}">
    <div class="reading-cover">${coverHTML(l.titulo,l.autor,l.capa_url,'')}</div>
    <div class="reading-copy">
      <div class="label">${t('continue_reading')}</div>
      <h3>${esc(l.titulo)}</h3>
      <p>${esc(l.autor)}</p>
      <div class="reading-spacer"></div>
      <div class="reading-meta">${progresso.texto||t('no_progress_yet')}</div>
      ${progresso.barra!==null?`<div class="reading-progress"><span style="width:${progresso.barra}%"></span></div>`:''}
    </div>
    <div class="continue-reading-actions">
      ${reviewCardActionHTML(idx,'reading-review-card-action')}
      <button type="button" class="reading-diary-action" aria-label="${t('update_progress')}" onclick="event.stopPropagation();abrirDiarioLeitura(${idx})">${t('update_progress')}</button>
    </div>
  </div>`;
}
function renderLendoAgora(){
  const lendo = prateleira.filter(l=>l.status==='Lendo');
  const box=$('#lendoAgora');
  if(!lendo.length){ box.innerHTML=''; return; }
  const l=lendo[0], idx=prateleira.indexOf(l);
  box.innerHTML=`<div class="section-head"><h2 class="h-section">${t('continue_reading')}</h2><span class="more" onclick="irPara('estante')">${t('see_shelf')}</span></div>${lendoAgoraCard(l,idx)}`;
}



function handleLinkHTML(handle, cls='feed-user') {
  const h=esc(handle||'leitor');
  return `<button type="button" class="${cls}" onclick="abrirPerfilPublico('${h.replace(/'/g,"\'")}')" title="${t('view_profile')}">@${h}</button>`;
}
function followButtonHTML(u, extraClass='') {
  if(!u?.handle || u.is_me) return '';
  return `<button type="button" class="follow-inline ${extraClass} ${u.is_following?'active':''}" onclick="toggleFollowHandle('${esc(u.handle).replace(/'/g,"\'")}')">${u.is_following?t('following'):t('follow')}</button>`;
}
function atualizarFollowLocal(handle, following, counts={}){
  const apply=u=>{ if(u?.handle===handle){ u.is_following=following; if('followers_count' in counts) u.followers_count=counts.followers_count; } };
  feedItems.forEach(it=>apply(it.usuario));
  discoverReaders.forEach(apply);
  [obraSocial?.criticas, obraSocial?.destaques].filter(Boolean).forEach(list=>list.forEach(c=>{ if(c?.usuario===handle){ c.is_following=following; if('followers_count' in counts) c.followers_count=counts.followers_count; } }));
}
async function toggleFollowHandle(handle){
  if(!handle) return;
  const current=[...feedItems.map(it=>it.usuario), ...discoverReaders, ...(obraSocial?.criticas||[]).map(c=>({handle:c.usuario,is_following:c.is_following}))].find(u=>u?.handle===handle);
  const following=!!current?.is_following;
  try{
    const res=await fetch('/api/u/'+encodeURIComponent(handle)+'/follow',{method:following?'DELETE':'POST'});
    if(res.status===401 || res.status===403){ toast(t('follow_login_required')); return; }
    if(!res.ok) throw new Error(await res.text());
    const data=await res.json();
    atualizarFollowLocal(handle, !!data.following, data);
    renderFeed();
    if(obraSocial?.criticas?.some(c=>c.usuario===handle)) renderEdicoes();
  }catch(e){ toast(t('interaction_error')); }
}
function mudarFeedTab(tab){ feedTab=tab==='following'?'following':'discover'; localStorage.setItem('lombada_feed_tab',feedTab); carregarFeed(); }

function feedAction(tipo,status){
  if(tipo==='wrote_review') return t('wrote_review');
  if(tipo==='started_reading' || status==='Lendo') return t('started_reading');
  if(tipo==='wants_to_read' || status==='Quero ler') return t('wants_to_read');
  if(tipo==='finished_reading' || status==='Lido') return t('finished_reading');
  return t('activity');
}
function dataFeed(iso){
  if(!iso)return '';
  const d=new Date(iso); if(Number.isNaN(d.getTime()))return '';
  const diff=Math.round((Date.now()-d.getTime())/86400000);
  if(diff<=0)return t('today');
  if(diff===1)return t('yesterday');
  return d.toLocaleDateString(getLocale(),{day:'2-digit',month:'short'});
}
function revelarFeedSpoiler(i){
  const item=feedItems[i];
  const box=document.querySelector(`[data-feed-spoiler="${i}"]`);
  if(box && item?.leitura?.relato){ box.classList.add('revealed'); box.textContent='“'+item.leitura.relato+'”'; }
}
function renderFeed(){
  const box=$('#feed'); if(!box)return;
  const tabs=`<div class="feed-tabs"><button type="button" class="${feedTab==='discover'?'active':''}" onclick="mudarFeedTab('discover')">${t('feed_discover')}</button><button type="button" class="${feedTab==='following'?'active':''}" onclick="mudarFeedTab('following')">${t('feed_following')}</button></div>`;
  const intro=`<div class="feed-intro"><p class="screen-helper">${feedTab==='discover'?t('discover_hint'):t('following_hint')}</p></div>`;
  if(feedTab==='following' && !feedFollowingCount){ box.innerHTML=tabs+intro+`<div class="empty-rich"><h3>${t('empty_following_title')}</h3><p>${t('empty_following_hint')}</p><button class="btn-cta" onclick="mudarFeedTab('discover')">${t('explore_reviews')}</button></div>`; return; }
  if(feedTab==='following' && !feedItems.length){ box.innerHTML=tabs+intro+`<div class="empty-rich"><p>${t('feed_empty_no_activity')}</p><button class="btn-cta" onclick="mudarFeedTab('discover')">${t('discover_readers')}</button></div>`; return; }
  if(feedTab==='discover' && !feedItems.length && !discoverReaders.length){ box.innerHTML=tabs+intro+`<div class="empty-rich"><p>${t('feed_empty_no_activity')}</p></div>`; return; }
  const reviewCards=feedItems.map((it,i)=>{
    const u=it.usuario||{}, livro=it.livro||{}, l=it.leitura||{};
    const edition=[it.edicao?.editora,it.edicao?.tradutor,it.edicao?.ano].filter(Boolean).join(' · ');
    const meta=[livro.autor,edition,dataFeed(it.created_at)].filter(Boolean).join(' · ');
    const spoiler=l.publico&&l.spoiler;
    return `<article class="feed-card">
      <div class="feed-cover">${coverHTML(livro.titulo,livro.autor,livro.capa_url,'')}</div>
      <div class="feed-copy">
        <div class="feed-card-top"><span>${handleLinkHTML(u.handle)}<span class="feed-action">${esc(feedAction(it.tipo,l.status))}</span></span>${followButtonHTML(u)}</div>
        <div class="feed-title-row"><button class="feed-title work-title-link" type="button" onclick="abrirPaginaObraDoFeed(${i})">${esc(livro.titulo)}</button>${l.nota?`<span class="feed-stars">${estrelasStr(l.nota)}</span>`:''}</div>
        <div class="feed-meta">${esc(meta)}</div>
        ${spoiler?`<button class="feed-spoiler" data-feed-spoiler="${i}" onclick="revelarFeedSpoiler(${i})">${t('spoiler_review')} — ${t('tap_to_reveal')}</button>`:(l.relato?`<div class="feed-quote">“${esc(l.relato)}”</div>`:'')}
        ${l.relato?reviewActionsHTML(l):''}
      </div></article>`;
  }).join('');
  const readers=feedTab==='discover'&&discoverReaders.length?`<section class="discover-readers"><div class="label">${t('discover_readers')}</div>${discoverReaders.map(r=>`<article><div>${handleLinkHTML(r.handle)}<small>${plural(r.reviews_count||0,'review_one','review_many')} · ${t('followers_count',{count:r.followers_count||0})}</small></div>${followButtonHTML(r)}</article>`).join('')}</section>`:'';
  const title=feedTab==='discover'?`<div class="label community-label">${t('discover_reviews')}</div>`:'';
  box.innerHTML=tabs+intro+readers+title+reviewCards;
}
async function carregarFeed(){
  const box=$('#feed'); if(box) box.innerHTML=`<div class="empty">${t('loading_activity')}</div>`;
  try{
    if(feedTab==='discover'){
      const data=await (await fetch('/api/feed/discover')).json();
      feedFollowingCount=1; feedItems=data.reviews||[]; discoverReaders=data.readers||[];
    }else{
      const data=await (await fetch('/api/feed')).json();
      feedFollowingCount=data.following_count||0; feedItems=data.items||[]; discoverReaders=[];
    }
  }
  catch(e){ feedFollowingCount=1; feedItems=[]; discoverReaders=[]; }
  renderFeed();
}
function abrirPerfilPublico(handle){ if(handle) location.href='/u/'+encodeURIComponent(handle); }


function normBusca(s){return (s||'').toString().normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase();}
function buscaPedeIdiomaEstrangeiro(q){
  const qn=normBusca(q);
  return ['frances','francais','french','ingles','english','espanhol','spanish','alemao','allemand','german','russo','russian','italiano'].some(t=>qn.includes(t));
}
function scoreResultadoBusca(doc,q){
  if(doc?.isbn_match) return 10000;
  const ed=doc?.edicao_isbn||{};
  const edicoes=Array.isArray(doc?.edicoes)?doc.edicoes:[];
  const texto=normBusca([doc?.titulo,doc?.autor,doc?.idioma_original,ed.titulo_edicao,ed.editora,ed.idioma,...edicoes.flatMap(e=>[e.titulo_edicao,e.editora,e.idioma])].filter(Boolean).join(' '));
  const qn=normBusca(q);
  let score=Number(doc?.quality_score||0);
  const ptSinais=[' portugues ',' portuguese ',' por ',' pt ',' pt-br '];
  const textoPad=` ${texto} `;
  const temPt=!!doc?.tem_pt || ptSinais.some(t=>textoPad.includes(t));
  if(temPt) score+=90;
  if(edicoes.some(e=>normBusca(e.idioma).includes('portugues'))) score+=55;
  ['brasil',...EDITORAS_BR].forEach(t=>{ if(texto.includes(t)) score+=26; });
  const estrangeiro=['frances','ingles','espanhol','allemand','french','english','spanish'];
  if(!buscaPedeIdiomaEstrangeiro(q) && estrangeiro.some(t=>texto.includes(t))) score-=45;
  TERMOS_PENALIZADOS.forEach(t=>{ if(texto.includes(t)) score-=55; });
  const titulo=normBusca(doc?.titulo);
  if(titulo && qn && (titulo===qn || titulo.includes(qn) || qn.includes(titulo))) score+=35;
  return score;
}
function ordenarResultadosBusca(docs,q){
  return (docs||[]).map((d,i)=>({d,i,s:scoreResultadoBusca(d,q)})).sort((a,b)=>(b.s-a.s)||(a.i-b.i)).map(x=>x.d);
}

const EDITORAS_BR = ['companhia das letras','editora 34','penguin companhia','martin claret','antofagica','nova fronteira','jose olympio','record','l&pm','l pm','todavia'];
const TERMOS_PENALIZADOS = ['tese','dissertacao','seminario','estudo critico','resumo','analise','biografia','correspondencia','ensaio sobre','thesis','dissertation','study','studies','essays','critique','analysis','biography','correspondance'];
function normalizarTextoObra(s){
  return (s||'').toString().normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/[–—-]/g,' ').replace(/[^\p{L}\p{N}\s:]/gu,' ').replace(/\s+/g,' ').trim();
}
const normalizarTextoBase = normalizarTextoObra;
function normalizarTituloObra(t){
  const semParens=(t||'').toString().replace(/\([^)]*\)/g,' ');
  const base=normalizarTextoObra(semParens);
  const partes=base.split(':').map(p=>p.trim()).filter(Boolean);
  return (partes[0]||base).replace(/\s+/g,' ').trim();
}
function autorPrincipal(a){
  return (a||'').toString().split(/,|;|\be\b|\band\b|&/i)[0].trim();
}
function normalizarAutorObra(a){ return normalizarTextoObra(autorPrincipal(a)); }
function chaveAgrupamentoObra(doc,idx=0){
  const backend=(doc?.chave_obra||'').trim();
  if(backend) return backend;   // chave canônica do servidor (mesma p/ local e externo)
  const titulo=normalizarTituloObra(doc?.titulo||doc?.titulo_edicao);
  const autor=normalizarAutorObra(doc?.autor);
  if(!titulo) return `sem-titulo|${idx}`;
  return autor ? `${titulo}|${autor}` : `${titulo}|sem-autor-${idx}`;
}
function edicaoDeDoc(doc){
  if(doc?.isbn_match && doc?.edicao_isbn) return {...doc.edicao_isbn, capa_url:doc.edicao_isbn.capa_url||doc.capa_url};
  return null;
}
function edicoesDoDoc(doc){
  const eds=Array.isArray(doc?.edicoes)?doc.edicoes.slice():[];
  const isbn=edicaoDeDoc(doc);
  if(isbn) eds.unshift(isbn);
  return eds.map(e=>({...e, capa_url:e.capa_url||doc?.capa_url}));
}
function temCapaEdicao(e){ return hasUsableCover(e); }
function textoEdicao(e,doc={}){ return normalizarTextoObra([e?.titulo_edicao,e?.editora,e?.tradutor,e?.isbn,e?.idioma,e?.pais,doc?.titulo,doc?.autor].filter(Boolean).join(' ')); }
function scoreEdicao(e,doc={}){
  const texto=textoEdicao(e,doc);
  let score=0;
  if(/\b(pt|pt br|pt-br|portugues|portuguese)\b/.test(texto)) score+=120;
  if(/\bbrasil\b|\bbrazil\b|\bbr\b/.test(texto)) score+=70;
  EDITORAS_BR.forEach(editora=>{ if(texto.includes(editora)) score+=55; });
  if(temCapaEdicao(e)) score+=35;
  ['editora','tradutor','isbn','ano','idioma'].forEach(campo=>{ if(e?.[campo]) score+=12; });
  if(!/\b(pt|pt br|pt-br|portugues|portuguese)\b/.test(texto) && /\b(english|ingles|french|frances|spanish|espanhol|german|alemao|russian|russo|italian|italiano)\b/.test(texto)) score-=35;
  TERMOS_PENALIZADOS.forEach(t=>{ if(texto.includes(t)) score-=70; });
  return score;
}
function ordenarEdicoesObra(edicoes,doc={}){
  return (edicoes||[]).map((e,i)=>({e,i,s:scoreEdicao(e,doc)})).sort((a,b)=>(b.s-a.s)||(a.i-b.i)).map(x=>x.e);
}
function assinaturaEdicaoObra(e){
  return [normalizarTituloObra(e?.titulo_edicao),normalizarTextoObra(e?.editora),e?.ano||'',normalizarTextoObra(e?.isbn)].join('|');
}
function adicionarEdicoesUnicas(destino, edicoes){
  const vistas=new Set(destino.map(assinaturaEdicaoObra));
  (edicoes||[]).forEach(e=>{
    const assinatura=assinaturaEdicaoObra(e);
    if(assinatura && !vistas.has(assinatura)){ vistas.add(assinatura); destino.push(e); }
  });
}
function edicoesLocaisDaObra(){
  return (obraSocial?.edicoes||[]).map(s=>({
    edicao_id:s.edicao_id, ol_edition_key:s.ol_edition_key, local:true, ...(s.edicao||{}),
    titulo_edicao:(s.edicao&&s.edicao.titulo_edicao)||escolha?.titulo, capa_url:s.edicao?.capa_url||escolha?.capa_url
  }));
}
function mesclarEdicoesLocais(edicoes){
  const locais=edicoesLocaisDaObra();
  const lista=locais.slice();
  adicionarEdicoesUnicas(lista, edicoes||[]);
  return lista;
}
function contagemEdicoesResultadoBusca(item, fallback=0){
  const total=Number(item?.edicoes_encontradas);
  if(Number.isFinite(total) && total>0) return total;
  const edicoes=item?.edicoes;
  if(Array.isArray(edicoes) && edicoes.length) return edicoes.length;
  return fallback;
}
function agruparResultadosPorObra(docs,q){
  const grupos=[]; const porChave=new Map();
  (docs||[]).forEach((doc,idx)=>{
    const chave=chaveAgrupamentoObra(doc,idx);
    let g=porChave.get(chave);
    if(!g){
      g={...doc, chave_obra:chave, docs:[], edicoes:[], edicoes_encontradas:0, score_obra:scoreResultadoBusca(doc,q)};
      grupos.push(g); porChave.set(chave,g);
    }
    const eds=edicoesDoDoc(doc);
    g.docs.push(doc);
    adicionarEdicoesUnicas(g.edicoes, eds);
    g.edicoes_encontradas=Math.max(g.edicoes_encontradas, contagemEdicoesResultadoBusca(doc), g.edicoes.length || g.docs.length);
    const s=scoreResultadoBusca(doc,q);
    if(s>g.score_obra || !g.capa_url){
      g.score_obra=s; g.titulo=doc.titulo||g.titulo; g.autor=doc.autor||g.autor; g.ano=doc.ano||g.ano; g.capa_url=doc.capa_url||g.capa_url; g.tem_pt=doc.tem_pt||g.tem_pt; g.work_key=doc.work_key||g.work_key; g.idioma_original=doc.idioma_original||g.idioma_original;
    }
  });
  return grupos.sort((a,b)=>(b.score_obra-a.score_obra)||(b.edicoes_encontradas-a.edicoes_encontradas));
}

/* busca */
function buscarTermo(t){$('#q').value=t;buscar();}
function renderBuscaSkeleton(){
  const item=()=>`<div class="book busca-skeleton-item" aria-hidden="true">
    <div class="cover busca-skeleton-cover"></div>
    <div class="busca-skeleton-line title"></div>
    <div class="busca-skeleton-line author"></div>
    <div class="busca-skeleton-line meta-line"></div>
  </div>`;
  $('#resultados').innerHTML=`<div class="section-head"><h2 class="h-section">${t('searching')}</h2></div><div class="wall busca-skeleton">${Array.from({length:4},item).join('')}</div>`;
}
function manualCtaHTML(destaque=false){
  return destaque
    ? `<div class="manual-cta prominent"><p>${t('manual_prominent_text')}</p><button class="link-manual" type="button" data-work-action="manual-edition">${t('manual_prominent_button')}</button></div>`
    : `<div class="manual-cta"><p>${t('manual_cta_text')}</p><button class="link-manual" type="button" data-work-action="manual-edition">${t('manual_cta_button')}</button></div>`;
}
async function buscar(event){
  if(event?.preventDefault) event.preventDefault();
  const q=$('#q').value.trim();
  if(q.length<2){
    $('#resultados').innerHTML=`<div class="empty">${t('empty_search_hint')}</div>${manualCtaHTML(false)}`;
    mostrarBusca('resultados');
    return;
  }
  lembrarBuscaRecente(q);
  const suggestBox=$('#searchSuggest'); if(suggestBox) suggestBox.hidden=true;
  $('#edicoes').innerHTML=''; $('#form').innerHTML='';
  renderBuscaSkeleton();
  mostrarBusca('resultados');
  const avisoBusca=setTimeout(()=>{
    const resultados=$('#resultados');
    const skeleton=resultados?.querySelector('.busca-skeleton');
    if(skeleton && !resultados.querySelector('.slow-search-note')){
      resultados.insertAdjacentHTML('afterbegin', `<div class="empty slow-search-note">${t('slow_external_search')}</div>`);
    }
  },4000);
  let docs;
  try{
    const res=await fetch('/api/buscar?q='+encodeURIComponent(q));
    if(!res.ok) throw new Error(`search http ${res.status}`);
    try{ docs=await res.json(); }catch(err){ throw new Error('search invalid json'); }
  }
  catch(err){
    console.warn('search failed', {query_len:q.length}, err);
    $('#resultados').innerHTML=`<div class="empty">${t('search_load_error')}</div>${manualCtaHTML(true)}`;
    return;
  }
  finally{ clearTimeout(avisoBusca); }
  resultadosArr=ordenarResultadosBusca(docs||[], q);
  obrasAgrupadas=agruparResultadosPorObra(resultadosArr, q);
  if(!obrasAgrupadas.length){
    $('#resultados').innerHTML=manualCtaHTML(true);
    return;
  }
  const melhorScore=Math.max(...resultadosArr.map(d=>scoreResultadoBusca(d,q)));
  const precisaDestaque=melhorScore<40;
  $('#resultados').innerHTML=`<div class="section-head"><h2 class="h-section">${t('works_found')}</h2></div><div class="wall">`+
    obrasAgrupadas.map((d,i)=>`<div class="book work-card" role="button" tabindex="0" onclick="verEdicoes(${i})" aria-label="${esc(d.titulo)}">
      ${coverHTML(d.titulo,d.autor,d.capa_url,d.tem_pt?'<span class="pt">PT</span>':'')}
      <div class="t">${esc(d.titulo)}</div>
      <div class="a">${esc(d.autor)}</div>
      <div class="yr">${plural(contagemEdicoesResultadoBusca(d,1),'edition_found_one','edition_found_many')}</div>
      <div class="e">${t('see_editions')}</div></div>`).join('')+'</div>'+manualCtaHTML(precisaDestaque);
}

/* edições */
async function carregarSocialObra(){
  obraSocial={estatisticas:{leituras:0,criticas:0,media:null},edicoes:[],criticas:[],destaques:[],destaques_edicao:{},minha_leitura:null};
  if(!escolha) return obraSocial;
  const params=new URLSearchParams({work_key:escolha.work_key||'',titulo:escolha.titulo||'',autor:escolha.autor||''});
  try{ obraSocial=await (await fetch('/api/obra/social?'+params.toString())).json(); }catch(e){}
  return obraSocial;
}
async function abrirPaginaObra(obra){
  if(obra) escolha=obra;
  await verEdicoes();
}
function obraDeLeitura(l){
  if(!l) return null;
  const edicao={edicao_id:l.edicao_id,titulo_edicao:l.titulo,editora:l.editora,ano:l.ano_edicao||l.ano,tradutor:l.tradutor,isbn:l.isbn,idioma:l.idioma,capa_url:l.capa_url};
  return {work_key:l.work_key||'',titulo:l.titulo,autor:l.autor,ano:l.ano_obra||l.ano,idioma_original:l.idioma_original,capa_url:l.capa_url,edicoes:[edicao]};
}
async function abrirPaginaObraDaLeitura(i){
  const obra=obraDeLeitura(prateleira[i]);
  if(!obra) return;
  irPara('buscar',{resetBusca:false});
  await abrirPaginaObra(obra);
}
async function abrirPaginaObraDoFeed(i){
  const it=feedItems[i];
  const livro=it?.livro||{};
  const ed=it?.edicao||{};
  const obra={work_key:livro.work_key||'',titulo:livro.titulo,autor:livro.autor,capa_url:livro.capa_url,edicoes:[{...ed,titulo_edicao:livro.titulo,capa_url:ed.capa_url||livro.capa_url}]};
  irPara('buscar',{resetBusca:false});
  await abrirPaginaObra(obra);
}
async function verEdicoes(i){
  if(Number.isInteger(i)) escolha=obrasAgrupadas[i]||resultadosArr[i];
  if(!escolha){
    $('#edicoes').innerHTML=`<div class="busca-back" role="button" tabindex="0" onclick="mostrarBusca('resultados')">${t('back_results')}</div><div class="empty">${t('work_not_found')}</div>`;
    mostrarBusca('edicoes');
    return;
  }
  $('#form').innerHTML='';
  const edicoesEmbutidas=Array.isArray(escolha.edicoes)?escolha.edicoes:[];
  if(!escolha.work_key && !edicoesEmbutidas.length && !(escolha.isbn_match && escolha.edicao_isbn)){
    edicoesAtual=[];
    await carregarSocialObra();
    renderEdicoes();
    mostrarBusca('edicoes');
    return;
  }
  // GB já trouxe as edições embutidas → zero chamada extra
  if(edicoesEmbutidas.length){
    await carregarSocialObra(); edicoesAtual=ordenarEdicoesObra(mesclarEdicoesLocais(edicoesEmbutidas)); renderEdicoes(); mostrarBusca('edicoes'); return;
  }
  // busca por ISBN → edição única
  if(escolha.isbn_match && escolha.edicao_isbn){
    await carregarSocialObra(); edicoesAtual=ordenarEdicoesObra(mesclarEdicoesLocais([escolha.edicao_isbn])); renderEdicoes(); mostrarBusca('edicoes'); return;
  }
  // fallback Open Library (obras sem edições embutidas)
  $('#edicoes').innerHTML=`<div class="empty">${t('loading_editions')}</div>`;
  mostrarBusca('edicoes');
  let eds;
  try{
    const res=await fetch('/api/edicoes?work_key='+encodeURIComponent(escolha.work_key));
    if(!res.ok) throw new Error(`editions http ${res.status}`);
    try{ eds=await res.json(); }catch(err){ throw new Error('editions invalid json'); }
  }
  catch(err){
    console.warn('editions failed', {work_key_len:(escolha?.work_key||'').length}, err);
    $('#edicoes').innerHTML=`<div class="busca-back" role="button" tabindex="0" onclick="mostrarBusca('resultados')">${t('back_results')}</div><div class="empty">${t('editions_load_error_now')}</div><div class="manual-cta prominent"><button class="link-manual" onclick="verEdicoes()">${t('try_again')}</button><button class="link-manual" type="button" data-work-action="manual-edition">${t('register_edition_manually')}</button></div>`;
    return;
  }
  await carregarSocialObra(); edicoesAtual=ordenarEdicoesObra(mesclarEdicoesLocais(eds||[])); renderEdicoes();
}
function fmtMedia(n){return n?Number(n).toLocaleString(getLocale(),{minimumFractionDigits:1,maximumFractionDigits:1})+' ★':t('no_average');}
function countLabel(n,oneKey,manyKey){ return plural(Number(n)||0,oneKey,manyKey); }
function editionSocialCountsHTML(social){
  const leituras=social?.leituras||0, tem=social?.tem||0, querem=social?.querem||0;
  const media=social?.media?' · '+fmtMedia(social.media):'';
  return `<div class="edition-stats"><span>${countLabel(leituras,'reading_one','reading_many')}</span><span>${social?.media?fmtMedia(social.media):t('no_average_yet')}</span><span>${t('readers_have_this_edition',{count:tem})}</span><span>${t('readers_want_this_edition',{count:querem})}</span></div>`;
}
function editionRelationHTML(social){
  if(!social?.edicao_id) return '';
  const estado=social.estado||{};
  return `<div class="edition-social-actions" onclick="event.stopPropagation()">
    <button type="button" class="edition-social-btn ${estado.tenho?'active':''}" onclick="toggleEditionState(${social.edicao_id},'tenho',${estado.tenho?'false':'true'})">${t('have_this_edition')}</button>
    <button type="button" class="edition-social-btn ${estado.quero?'active':''}" onclick="toggleEditionState(${social.edicao_id},'quero',${estado.quero?'false':'true'})">${t('want_this_edition')}</button>
  </div>${estado.li?`<div class="edition-relation-note">${t('you_read_this_edition')}</div>`:''}`;
}
async function toggleEditionState(edicaoId,campo,valor){
  const body={}; body[campo]=valor;
  try{
    const r=await fetch(`/api/edicoes/${edicaoId}/estado`,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    if(r.status===401){ toast(t('login_to_interact')); return; }
    if(!r.ok) throw new Error(await r.text());
    await carregarSocialObra(); renderEdicoes(); carregarPrateleira();
  }catch(e){ console.error('erro ao atualizar edição',e); toast(t('interaction_error')); }
}
function edicaoSocial(e){
  const stats=(obraSocial?.edicoes||[]);
  const sig=normalizarTextoBase([e.editora,e.ano,e.isbn,e.idioma].filter(Boolean).join('|'));
  return stats.find(st=>st.edicao_id && e.edicao_id===st.edicao_id) || stats.find(st=>{
    const ed=st.edicao||{};
    const s2=normalizarTextoBase([ed.editora,ed.ano,ed.isbn,ed.idioma].filter(Boolean).join('|'));
    return sig && s2 && sig===s2;
  }) || null;
}

function atualizarReviewLocal(leituraId, patch){
  const listas=[obraSocial?.criticas,obraSocial?.destaques,feedItems.map(it=>it.leitura)].filter(Boolean);
  listas.forEach(list=>list.forEach(c=>{ if(c&&c.leitura_id===leituraId) Object.assign(c,patch); }));
}
async function acaoReview(leituraId,acao){
  if(!leituraId) return;
  const metodo=(acao==='unlike'||acao==='unsave')?'DELETE':'POST';
  const rota=acao==='like'||acao==='unlike'?'like':acao==='save'||acao==='unsave'?'save':'report';
  let body=null;
  if(acao==='report'){
    body=JSON.stringify({motivo:t('report_other'),detalhe:''});
  }
  try{
    const res=await fetch(`/api/reviews/${leituraId}/${rota}`,{method:metodo,headers:body?{'Content-Type':'application/json'}:{},body});
    if(res.status===401){ toast(t('login_to_interact')); return; }
    if(!res.ok) throw new Error(await res.text());
    const data=await res.json();
    const patch={};
    if('liked' in data){ patch.liked_by_me=data.liked; patch.likes_count=data.likes_count; }
    if('saved' in data) patch.saved_by_me=data.saved;
    if('reported' in data){ patch.reported_by_me=true; toast(t('report_sent')); }
    atualizarReviewLocal(leituraId,patch);
    renderFeed();
    if(obraSocial?.criticas?.some(c=>c.leitura_id===leituraId)) renderEdicoes();
  }catch(e){ toast(t('interaction_error')||'não foi possível atualizar agora.'); }
}
function reviewActionsHTML(c){
  if(!c||!c.leitura_id) return '';
  const liked=!!c.liked_by_me, saved=!!c.saved_by_me;
  const likes=Number(c.likes_count||0);
  return `<div class="review-actions">
    <button type="button" class="${liked?'active':''}" onclick="acaoReview(${c.leitura_id},'${liked?'unlike':'like'}')">${liked?'♥':'♡'} ${likes}</button>
    <button type="button" class="${saved?'active':''}" onclick="acaoReview(${c.leitura_id},'${saved?'unsave':'save'}')">${saved?t('saved_review'):t('save_review')}</button>
    <button type="button" onclick="acaoReview(${c.leitura_id},'report')">${c.reported_by_me?t('reported_review'):t('report')}</button>
  </div>`;
}

function revelarSpoiler(btn){
  const card=btn.closest('.review-card');
  if(card) card.classList.add('spoiler-open');
}
function criticasHTML(){
  const recentes=obraSocial?.criticas||[];
  const destaques=obraSocial?.destaques||[];
  if(!recentes.length) return `<section class="community-section work-section"><div class="section-head"><h2 class="h-section">${t('community_reviews')}</h2></div><div class="empty-rich work-empty"><div class="ei">✍️</div><p>${t('no_public_reviews_html')}</p><button class="btn-cta" type="button" data-work-action="register-reading">${t('register_my_reading')}</button></div></section>`;
  const edicaoMeta=c=>[c.status&&statusLabel(c.status),c.edicao?.editora&&`${t('publisher_abbr')} ${c.edicao.editora}`,c.edicao?.tradutor&&`${t('translator_abbr')} ${c.edicao.tradutor}`,c.edicao?.ano,c.data||dataFeed(c.criado_em)].filter(Boolean).map(esc).join(' · ');
  const trecho=c=>{ const txt=(c.relato||'').trim(); return txt.length>180?txt.slice(0,177)+'…':txt; };
  const corpo=c=>c.spoiler
    ? `<div class="spoiler-box"><strong>${t('spoiler_warning')}</strong>${trecho(c)?`<button type="button" onclick="revelarSpoiler(this)">${t('tap_to_reveal_spoiler')}</button><p>${esc(trecho(c))}</p>`:''}</div>`
    : (trecho(c)?`<p>${esc(trecho(c))}</p>`:'');
  const card=c=>`<article class="review-card ${c.spoiler?'has-spoiler':''}"><div class="review-top"><strong>${handleLinkHTML(c.usuario||'leitor','review-user')}</strong><span>${c.nota?fmtMedia(c.nota):t('no_rating')}</span></div>${corpo(c)}${followButtonHTML({handle:c.usuario,is_following:c.is_following,is_me:c.is_me},'review-follow')}<div class="review-meta">${edicaoMeta(c)}</div>${reviewActionsHTML(c)}</article>`;
  return `<section class="community-section work-section"><div class="section-head"><h2 class="h-section">${t('community_reviews')}</h2></div>${destaques.length?`<div class="label community-label">${t('featured')}</div><div class="reviews-list featured">${destaques.map(card).join('')}</div>`:''}<div class="label community-label">${t('recent')}</div><div class="reviews-list">${recentes.map(card).join('')}</div></section>`;
}
function setButtonBusy(btn,text){
  if(!btn) return;
  if(!btn.dataset.originalText) btn.dataset.originalText=btn.textContent;
  btn.textContent=text;
  btn.disabled=true;
  btn.classList.add('is-busy');
}
function clearButtonBusy(btn){
  if(!btn) return;
  btn.textContent=btn.dataset.originalText||btn.textContent;
  btn.disabled=false;
  btn.classList.remove('is-busy');
  delete btn.dataset.originalText;
}
function registrarLeituraObra(event){
  const trigger=event?.target?.closest?.('button');
  setButtonBusy(trigger,t('loading_editions'));
  setTimeout(()=>clearButtonBusy(trigger),900);
  const edicoesAtualLength=edicoesAtual?.length||0;
  debugLog('registrarLeituraObra', {
    escolha,
    edicoesAtualLength,
    edicoesAtual
  });
  if(edicoesAtualLength===1){ escolherEdicao(0, event); return; }
  if(edicoesAtualLength>1){
    toast(t('choose_edition_to_register'));
    focarTelaBusca('.editions');
    return;
  }
  toast(t('no_editions_register_manual'));
  abrirManual(event);
  return;
}
function verMinhaLeitura(){
  const idx=prateleira.findIndex(l=>l.leitura_id===obraSocial?.minha_leitura?.leitura_id);
  if(idx>=0) abrirCard(idx); else irPara('estante');
}
function renderPaginaObra(){
  return renderEdicoes();
}
function toggleAboutWork(btn){
  const sec=btn.closest('.about-work'); if(!sec) return;
  const clamped=sec.classList.toggle('clamp');   // true = recolhido, false = expandido
  btn.textContent=clamped?t('see_more'):t('see_less');
}
function renderEdicoes(){
  const st=obraSocial?.estatisticas||{};
  const media=st.media?fmtMedia(st.media):t('no_average_yet');
  const leituras=st.leituras||0, criticas=st.criticas||0, lendo=st.lendo||0, querem=st.querem||0;
  const back=`<div class="busca-back" role="button" tabindex="0" onclick="mostrarBusca('resultados')">${t('back_results')}</div>`;
  const obraLocal=obraSocial?.obra||{};
  const anoIdioma=[obraLocal.ano||escolha.ano, obraLocal.idioma_original||escolha.idioma_original].filter(Boolean).map(esc).join(' · ');
  const acaoPrincipal=obraSocial?.minha_leitura
    ? `<button class="primary" type="button" onclick="verMinhaLeitura()">${t('see_my_reading')}</button>`
    : `<button class="primary" type="button" data-work-action="register-reading">${t('register_reading')}</button>`;
  const cab=`<div class="work-head social-work-head work-hero">${coverHTML(escolha.titulo,escolha.autor,escolha.capa_url,'')}
    <div class="wmeta"><div class="label">${t('work_page')}</div><h2>${esc(escolha.titulo)}</h2>
      <div class="a">${esc(escolha.autor||t('unknown_author'))}</div>
      ${anoIdioma?`<div class="y">${anoIdioma}</div>`:''}
      <div class="community-score"><strong>${media}</strong><span>${plural(leituras,'reading_one','reading_many')} · ${plural(criticas,'review_one','review_many')}</span></div>
      <div class="work-actions">${acaoPrincipal}<button class="secondary" type="button" data-work-action="see-editions">${t('see_editions')}</button></div><button class="link-tertiary" type="button" data-work-action="manual-edition">${t('register_edition_manually')}</button>
    </div></div>`;
  const descricao=(escolha.descricao||escolha.description||obraSocial?.obra?.descricao||'').trim();
  const descLonga=descricao.length>320;
  const tituloAutorBusca=[escolha.titulo,escolha.autor].filter(Boolean).join(' ');
  const linkSaibaMais=tituloAutorBusca?`<a class="linklike about-work-external" href="https://www.google.com/search?q=${encodeURIComponent('livro '+tituloAutorBusca+' sinopse')}" target="_blank" rel="noopener">${t('learn_more_external')}</a>`:'';
  const sobreObra=`<section class="about-work work-section${descLonga?' clamp':''}"><div class="label">${t('about_work')}</div>${descricao?`<p class="about-work-text">${esc(descricao)}</p><div class="about-work-actions">${descLonga?`<button class="linklike about-work-toggle" type="button" onclick="toggleAboutWork(this)">${t('see_more')}</button>`:''}${linkSaibaMais}</div>`:`<p class="muted">${t('no_work_description')}</p><div class="about-work-actions"><button class="linklike" type="button" onclick="toast(t('description_suggestions_soon'))">${t('suggest_description')}</button>${linkSaibaMais}</div>`}</section>`;
  const poucosDados=(!edicoesAtual.length&&!leituras&&!criticas)||(!escolha.capa_url&&!escolha.ano&&!escolha.idioma_original&&!criticas);
  const estadoPoucosDados=poucosDados?`<section class="work-section work-low-data"><p>${t('work_low_data')}</p><div class="work-actions"><button class="primary" type="button" data-work-action="register-reading">${t('register_reading')}</button><button class="secondary" type="button" data-work-action="manual-edition">${t('register_edition_manually')}</button></div></section>`:'';
  const minhas='';
  const destaquesEd=obraSocial?.destaques_edicao||{};
  const maisLida=destaquesEd.mais_lida||(obraSocial?.edicoes||[]).slice().sort((a,b)=>(b.leituras||0)-(a.leituras||0))[0];
  const destaqueObraHTML=[
    destaquesEd.mais_lida&&`${t('most_read_edition')}: ${esc(destaquesEd.mais_lida.edicao?.editora||t('publisher_missing'))}`,
    destaquesEd.mais_desejada&&`${t('most_wanted_edition')}: ${esc(destaquesEd.mais_desejada.edicao?.editora||t('publisher_missing'))}`,
    destaquesEd.mais_possuida&&`${t('most_owned_edition')}: ${esc(destaquesEd.mais_possuida.edicao?.editora||t('publisher_missing'))}`,
    destaquesEd.traducao_mais_lida&&`${t('most_read_translation')}: ${esc(destaquesEd.traducao_mais_lida)}`,
    destaquesEd.editora_mais_lida&&`${t('most_read_publisher')}: ${esc(destaquesEd.editora_mais_lida)}`
  ].filter(Boolean);
  const temEstatisticas=!!(leituras||st.media||lendo||querem);
  const estatisticasHTML=temEstatisticas
    ? `<section class="community-summary work-stats"><div><span>${leituras}</span><small>${t('readings_on_lombada')}</small></div><div><span>${media}</span><small>${t('average_rating')}</small></div><div><span>${lendo}</span><small>${t('people_reading')}</small></div><div><span>${querem}</span><small>${t('people_want_to_read')}</small></div></section>`
    : `<section class="work-section work-stats-empty"><p>${t('edition_stats')}</p></section>`;
  const cards=edicoesAtual.map((e,j)=>{
    const pt=normalizarTextoBase(e.idioma).includes('portugues')||normalizarTextoBase(e.pais).includes('brasil');
    const social=edicaoSocial(e);
    const isMaisLida=social&&maisLida&&social.edicao_id===maisLida.edicao_id;
    const grupo=isMaisLida?t('most_read'):(pt?t('portuguese_brazil'):t('other_editions'));
    const tr=e.tradutor?`${t('translator_abbr')} <b>${esc(e.tradutor)}</b>`:'';
    const stats=social?editionSocialCountsHTML(social):'<div class="edition-stats">'+t('edition_stats')+'</div>';
    const relation=editionRelationHTML(social);
    return `<li class="edition ${isMaisLida?'most-read':''}" onclick="escolherEdicao(${j})"><div class="edition-group">${grupo}</div>
      <div class="edition-cover">${coverHTML(e.titulo_edicao||escolha.titulo,escolha.autor,e.capa_url,'')}</div>
      <div class="edition-body"><div class="pub">${e.editora?linkEditoraHTML(e.editora):esc(t('publisher_missing'))}${pt?' · PT/BR':''}</div><div class="te">${esc(e.titulo_edicao||escolha.titulo)}</div><div class="tr">${tr}</div><div class="ln meta edition-meta-pills">${[e.ano,e.idioma,e.pais,e.isbn&&`${t('isbn')} ${e.isbn}`].filter(Boolean).map(x=>`<span>${esc(x)}</span>`).join('')}</div>${stats}${relation}<button class="edition-action" type="button" data-work-action="choose-edition" data-edition-index="${j}">${t('register_this_edition')}</button></div></li>`;
  }).join('');
  $('#edicoes').innerHTML=back+`<main class="work-page">${cab}${estatisticasHTML}${estadoPoucosDados}${sobreObra}${destaqueObraHTML.length?`<section class="work-edition-highlights work-section"><div class="label">${t('edition_social')}</div>${destaqueObraHTML.map(x=>`<p>${x}</p>`).join('')}</section>`:''}<section class="work-section"><div class="section-head"><h2 class="h-section">${t('editions')}</h2></div>${cards?`<ul class="editions work-editions">${cards}</ul>`:`<div class="empty-rich work-empty"><p>${t('no_editions_register_manual')}</p><button class="btn-cta" type="button" data-work-action="manual-edition">${t('register_edition_manually')}</button></div>`}</section>${criticasHTML()}</main>`;
}

/* registrar */
function escolherEdicao(j,event){
  const trigger=event?.target?.closest?.('button,.edition');
  setButtonBusy(trigger,t('opening_form'));
  const edicao=edicoesAtual?.[j];
  if(!edicao){
    clearButtonBusy(trigger);
    debugLog('invalid edition selected', j, edicoesAtual);
    toast(t('invalid_edition_selected'));
    abrirManual();
    return;
  }
  edicaoSel={
    ...edicao,
    titulo_edicao: edicao.titulo_edicao || escolha?.titulo || '',
    capa_url: edicao.capa_url || escolha?.capa_url || '',
    autor: escolha?.autor || ''
  };
  notaSel=0;
  const social=edicaoSocial(edicaoSel);
  const estado=social?.estado||{};
  const titulo=edicaoSel.titulo_edicao||escolha.titulo;
  const autor=edicaoSel.autor||escolha?.autor||'';
  const metaLinha1=[edicaoSel.editora, edicaoSel.ano, edicaoSel.tradutor&&`${t('translator_abbr')} ${edicaoSel.tradutor}`].filter(Boolean);
  const metaLinha2=[edicaoSel.isbn&&`${t('isbn')} ${edicaoSel.isbn}`, edicaoSel.idioma].filter(Boolean);
  const metaHTML=[metaLinha1,metaLinha2].filter(linha=>linha.length).map(linha=>`<div>${linha.map(esc).join(' · ')}</div>`).join('');
  const edicaoHTML=`<div class="selected-edition-summary">
      <div class="selected-edition-cover">${coverHTML(titulo,autor,edicaoSel.capa_url,'')}</div>
      <div class="selected-edition-copy">
        <h3>${esc(titulo||t('book'))}</h3>
        ${autor?`<p class="selected-edition-author">${esc(autor)}</p>`:''}
        ${metaHTML?`<div class="selected-edition-meta">${metaHTML}</div>`:`<p class="selected-edition-meta muted">${t('catalog_data_missing')}</p>`}
        ${escolha?.descricao?`<p class="selected-edition-desc">${esc(escolha.descricao)}</p>`:''}
      </div>
    </div>`;
  clearButtonBusy(trigger);
  $('#form').innerHTML=`
    <div class="busca-back" role="button" tabindex="0" onclick="mostrarBusca('edicoes')">${t('back_editions')}</div>
    <div class="section-head"><h2 class="h-section">${t('register_reading')}</h2></div>
    <div class="card-form reading-form simple-reading-form">
      <section class="reading-form-block selected-edition-block"><div class="label">${t('selected_edition')}</div>${edicaoHTML}<button class="link-btn subtle" type="button" onclick="sugerirCorrecaoCatalogo()">${t('suggest_correction')}</button></section>
      <section class="reading-form-block reading-status-block"><div class="label">${t('your_reading')}</div><div class="field status-field"><label class="label">${t('status')}</label><select id="f_status" onchange="atualizarFormularioLeituraPorStatus('f')"><option value="Lido">${t('status_read')}</option><option value="Lendo">${t('status_reading')}</option><option value="Quero ler">${t('status_want')}</option></select></div><div class="reading-secondary-fields"><div class="field"><label class="label">${t('when')}</label><input type="text" id="f_data" placeholder="${t('date_placeholder')}" /></div><div class="field rating-field" data-rating-field="f"><label class="label">${t('your_rating')}</label><div class="stars" id="f_stars"></div></div></div></section>
      <section class="reading-form-block reading-text-block"><div class="field review-field"><label class="label" id="f_relato_label">${t('your_review')}</label><textarea id="f_relato" maxlength="160" placeholder="${t('your_review_placeholder')}"></textarea></div></section>
      <section class="reading-form-block reading-options-block light-options"><div class="label">${t('options')}</div><label class="check-line"><input type="checkbox" id="f_publico"> <span id="f_publico_label">${t('show_on_public_profile')}</span></label><p class="form-helper option-helper">${t('private_shelf_hint')}</p><label class="check-line"><input type="checkbox" id="f_spoiler"> <span>${t('contains_spoiler')}</span></label></section>
      <section class="reading-form-block edition-relation-block light-options"><div class="label">${t('relation_with_edition')}</div><p class="form-helper option-helper">${t('edition_relation_hint')}</p><label class="check-line"><input type="checkbox" id="f_tenho" ${estado.tenho?'checked':''}> <span>${t('have_this_edition_full')}</span></label><label class="check-line"><input type="checkbox" id="f_quero" ${estado.quero?'checked':''}> <span>${t('want_this_edition_full')}</span></label></section>
      <button class="btn-primary reading-submit" type="button" onclick="salvar(event)">${t('save_to_shelf')}</button>
    </div>`;
  mostrarBusca('form');
  focarTelaBusca('#form');
  toast(t('fill_reading_below'));
  montarStars('f_stars',()=>notaSel,v=>notaSel=v);
  atualizarFormularioLeituraPorStatus('f');
  const statusSelect = $('#f_status');
  if (statusSelect) {
    ['change', 'input', 'blur'].forEach(evt => {
      statusSelect.addEventListener(evt, () => atualizarFormularioLeituraPorStatus('f'));
    });
  }
}

function sugerirCorrecaoCatalogo(){
  toast(t('catalog_correction_soon'));
}

function copyRelatoPorStatus(status){
  if(status === 'Lido') {
    return {
      label: t('your_review'),
      placeholder: t('your_review_placeholder'),
      publico: t('make_review_public')
    };
  }

  if(status === 'Lendo') {
    return {
      label: t('reading_impression'),
      placeholder: t('reading_impression_placeholder'),
      publico: t('show_on_public_profile')
    };
  }

  return {
    label: t('reading_expectation'),
    placeholder: t('reading_expectation_placeholder'),
    publico: t('show_on_public_profile')
  };
}

function atualizarFormularioLeituraPorStatus(prefix='f'){
  const statusEl = document.querySelector(`#${prefix}_status`);
  if (!statusEl) return;

  const status = statusEl.value;
  const copy = copyRelatoPorStatus(status);

  const label = document.querySelector(`#${prefix}_relato_label`);
  const textarea = document.querySelector(`#${prefix}_relato`);
  const publico = document.querySelector(`#${prefix}_publico_label`);
  const ratingField = document.querySelector(`[data-rating-field="${prefix}"]`);

  if (label) label.textContent = copy.label;
  if (textarea) {
    textarea.placeholder = copy.placeholder;
    textarea.setAttribute('aria-label', copy.placeholder);
  }
  if (publico) publico.textContent = copy.publico;

  if (ratingField) {
    const isWant = status === 'Quero ler';
    ratingField.style.display = isWant ? 'none' : '';
    ratingField.setAttribute('aria-hidden', isWant ? 'true' : 'false');
  }

  debugLog('reading form status copy', { status, copy });
}

function atualizarCopyRelato(prefix){
  atualizarFormularioLeituraPorStatus(prefix);
}

function montarStars(id,get,set){
  const w=$('#'+id);
  function paint(){
    const n=get(); w.innerHTML='';
    for(let i=1;i<=5;i++){
      const s=document.createElement('span');
      s.className='st'+(i<=n?' on':''); s.textContent='★';
      s.style.opacity=(i<=n?1:(i-0.5===n?.6:.28));
      s.onclick=()=>{ set(get()===i?i-0.5:i); paint(); };
      w.appendChild(s);
    }
    const txt=document.createElement('span');
    txt.className='stxt'; txt.textContent=n?n.toLocaleString(getLocale())+'★':t('no_rating');
    w.appendChild(txt);
  }
  paint();
}

async function salvar(event){
  if(!escolha || !edicaoSel){
    debugLog('save without selected work/edition', { escolha, edicaoSel, edicoesAtual });
    toast(t('invalid_edition_selected'));
    abrirManual();
    return;
  }
  const form=$('#f_status')?.closest('.card-form');
  const saveBtn=event?.target?.closest?.('button');
  limparErroFormulario(form);
  setButtonBusy(saveBtn,t('saving'));
  const body={
    work_key:escolha.work_key, titulo:escolha.titulo, autor:escolha.autor||'',
    idioma_original:escolha.idioma_original||'', ano_obra:escolha.ano||null,
    ol_edition_key:edicaoSel.ol_edition_key||null, editora:edicaoSel.editora||'',
    tradutor:edicaoSel.tradutor||'', isbn:edicaoSel.isbn||'', idioma:edicaoSel.idioma||'',
    ano_edicao:edicaoSel.ano||null, capa_url:edicaoSel.capa_url||escolha.capa_url||'',
    status:$('#f_status').value, nota:$('#f_status').value==='Quero ler'?null:(notaSel||null),
    relato:$('#f_relato').value.trim(), publico:$('#f_publico').checked, spoiler:$('#f_spoiler').checked, data:$('#f_data').value.trim(),
    tenho_edicao:$('#f_tenho')?.checked||false, quero_edicao:$('#f_quero')?.checked||false
  };
  const duplicadoLocal=encontrarLeituraDuplicada(body);
  if(duplicadoLocal){ clearButtonBusy(saveBtn); avisarDuplicado(duplicadoLocal.leitura_id); return; }
  let motivoServidor='';
  try{
    const r=await fetch('/api/prateleira',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    if(!r.ok){
      const erro=await payloadErro(r);
      const detalhe=erro?.detail||erro||{};
      if(r.status===409&&(detalhe.duplicado||erro?.duplicado)){
        clearButtonBusy(saveBtn);
        avisarDuplicado(detalhe.leitura_id||erro.leitura_id);
        return;
      }
      // guarda o motivo real do servidor (string) pra mostrar ao usuário
      motivoServidor=typeof detalhe==='string'?detalhe:(detalhe?.mensagem||detalhe?.detail||'');
      throw new Error(motivoServidor||JSON.stringify(erro)||r.statusText);
    }
  }
  catch(e){ console.error('erro ao salvar leitura', e); clearButtonBusy(saveBtn); mostrarErroFormulario(form,motivoServidor||t('save_error')||'não consegui salvar. tenta de novo.'); return; }
fecharModalParaNavegacao();

limparBusca(); $('#q').value=''; mostrarBusca('home',
{registrar:false});
marcarConviteLoginAposSalvar();
marcarLivroSalvo(body);
toast(t('saved_to_shelf'));
await carregarPrateleira();
irPara('estante',{recarregar:false});
}
function abrirManual(event){
  const trigger=event?.target?.closest?.('button');
  setButtonBusy(trigger,t('opening_form'));
  setTimeout(()=>clearButtonBusy(trigger),700);
  debugLog('abrirManual', { escolha, q: $('#q')?.value });
  notaSel=0;
  if($('#secBuscar')?.style.display==='none') irPara('buscar',{resetBusca:false,registrar:false,scrollTop:false});
  const q=$('#q')?.value.trim()||'';
  const tituloManual=escolha?.titulo || q;
  const autorManual=escolha?.autor || '';
  const anoObraManual=escolha?.ano || '';
  const idiomaOriginalManual=escolha?.idioma_original || '';
  const capaManual=escolha?.capa_url || '';
  const manual=$('#manual');
  if(!manual){
    console.warn('manual container missing');
    toast(t('save_error') || 'Não consegui abrir o cadastro manual.');
    mostrarBusca('manual');
    focarTelaBusca('#manual');
    return;
  }
  manual.innerHTML=`
    <div class="busca-back" role="button" tabindex="0" onclick="history.back()">${t('back')}</div>
    <div class="section-head"><h2 class="h-section">${t('manual_registration')}</h2></div>
    <div class="card-form">
      <div class="form-block"><div class="label">${t('book')}</div>
        <div class="field"><label class="label">${t('work_title_required')}</label><input type="text" id="m_titulo" value="${esc(tituloManual)}" /></div>
        <div class="field"><label class="label">${t('author_required')}</label><input type="text" id="m_autor" value="${esc(autorManual)}" /></div>
        <div class="row"><div class="field"><label class="label">${t('work_year')}</label><input type="text" id="m_ano_obra" value="${esc(anoObraManual)}" /></div>
        <div class="field"><label class="label">${t('original_language')}</label><input type="text" id="m_idioma_original" value="${esc(idiomaOriginalManual)}" /></div></div>
      </div>
      <div class="form-block"><div class="label">${t('edition')}</div>
        <div class="field"><label class="label">${t('edition_title')}</label><input type="text" id="m_titulo_edicao" /></div>
        <div class="field"><label class="label">${t('publisher')}</label><input type="text" id="m_editora" /></div>
        <div class="field"><label class="label">${t('translator')}</label><input type="text" id="m_tradutor" /></div>
        <div class="row"><div class="field"><label class="label">${t('isbn')}</label><input type="text" id="m_isbn" /></div>
        <div class="field"><label class="label">${t('language_field')}</label><input type="text" id="m_idioma" /></div></div>
        <div class="row"><div class="field"><label class="label">${t('edition_year')}</label><input type="text" id="m_ano_edicao" /></div>
        <div class="field"><label class="label">${t('cover_url')}</label><input type="text" id="m_capa_url" value="${esc(capaManual)}" /></div></div>
      </div>
      <div class="form-block"><div class="label">${t('your_reading')}</div>
        <div class="row"><div class="field"><label class="label">${t('status')}</label><select id="m_status"><option value="Lido">${t('status_read')}</option><option value="Lendo">${t('status_reading')}</option><option value="Quero ler">${t('status_want')}</option></select></div>
        <div class="field"><label class="label">${t('date')}</label><input type="text" id="m_data" placeholder="${t('date_placeholder')}" /></div></div>
        <div class="field"><label class="label">${t('rating')}</label><div class="stars" id="m_stars"></div></div>
        <div class="field"><label class="label">${t('reading_note')}</label><textarea id="m_relato" maxlength="160"></textarea></div>
      </div>
      <button class="btn-primary" type="button" onclick="salvarManual(event)">${t('submit_for_review')}</button>
    </div>`;
  mostrarBusca('manual');
  focarTelaBusca('#manual');
  montarStars('m_stars',()=>notaSel,v=>notaSel=v);
}

async function salvarManual(event){
  const saveBtn=event?.target?.closest?.('button');
  const titulo=$('#m_titulo').value.trim(), autor=$('#m_autor').value.trim();
  const form=$('#m_titulo')?.closest('.card-form');
  limparErroFormulario(form);
  if(!titulo||!autor){ mostrarErroFormulario(form,t('required_title_author')); return; }
  setButtonBusy(saveBtn,t('saving'));
  const body={
    titulo, autor, ano_obra:parseInt($('#m_ano_obra').value,10)||null, idioma_original:$('#m_idioma_original').value.trim(),
    titulo_edicao:$('#m_titulo_edicao').value.trim(), editora:$('#m_editora').value.trim(), tradutor:$('#m_tradutor').value.trim(),
    isbn:$('#m_isbn').value.trim(), idioma:$('#m_idioma').value.trim(), ano_edicao:parseInt($('#m_ano_edicao').value,10)||null,
    capa_url:$('#m_capa_url').value.trim(), status:$('#m_status').value, nota:notaSel||null, relato:$('#m_relato').value.trim(), data:$('#m_data').value.trim()
  };
  try{ const r=await fetch('/api/manual',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}); if(!r.ok) throw new Error(await r.text()); }
  catch(e){ console.error('erro ao salvar leitura', e); clearButtonBusy(saveBtn); mostrarErroFormulario(form,t('save_error') || 'não consegui salvar. tenta de novo.'); return; }
  fecharModalParaNavegacao(); limparBusca(); $('#q').value=''; mostrarBusca('home',{registrar:false});
  marcarConviteLoginAposSalvar(); marcarLivroSalvo(body); toast(t('manual_success')); irPara('perfil',{recarregar:false});
}

/* estante */
function chaveLivro(l){
  return `${(l?.titulo||'').trim().toLowerCase()}|${(l?.autor||'').trim().toLowerCase()}`;
}
function marcarLivroSalvo(l){
  ultimoLivroSalvo=chaveLivro(l);
  if(timerDestaqueLivro) clearTimeout(timerDestaqueLivro);
  timerDestaqueLivro=setTimeout(()=>{ ultimoLivroSalvo=null; timerDestaqueLivro=null; renderPrateleira(); },4200);
}
function livroEstaDestacado(l){
  return ultimoLivroSalvo && chaveLivro(l)===ultimoLivroSalvo;
}
function mudarFiltroEstante(status){
  filtroEstante=status;
  renderPrateleira();
}
function mudarVisualizacaoEstante(modo){
  visualizacaoEstante=modo==='lista'?'lista':'grade';
  localStorage.setItem('lombada_view_estante',visualizacaoEstante);
  renderPrateleira();
}
function controlesEstante(){
  const filtros=['Todos','Lido','Lendo','Quero ler'];
  return `<div class="shelf-tools">
    <div class="shelf-filters" aria-label="${t('filter_shelf_status')}">${filtros.map(f=>
      `<button class="shelf-pill ${filtroEstante===f?'active':''}" onclick="mudarFiltroEstante('${f}')">${esc(statusLabel(f))}</button>`
    ).join('')}</div>
    <div class="shelf-view" aria-label="${t('shelf_view')}">
      <button class="shelf-view-btn ${visualizacaoEstante==='grade'?'active':''}" onclick="mudarVisualizacaoEstante('grade')">${t('view_grid')}</button>
      <button class="shelf-view-btn ${visualizacaoEstante==='lista'?'active':''}" onclick="mudarVisualizacaoEstante('lista')">${t('view_list')}</button>
    </div>
  </div>`;
}
function metaListaEstante(l){
  return [l.editora?`${t('publisher_abbr')} ${esc(l.editora)}`:'',l.tradutor?`${t('translator_abbr')} ${esc(l.tradutor)}`:'',l.isbn?`${t('isbn')} ${esc(l.isbn)}`:''].filter(Boolean).join(' · ');
}
function resumoEstante(){
  const total=prateleira.length;
  const lidos=prateleira.filter(l=>l.status==='Lido').length;
  const lendo=prateleira.filter(l=>l.status==='Lendo').length;
  const quero=prateleira.filter(l=>l.status==='Quero ler').length;
  return t('shelf_summary',{total:plural(total,'book_count_one','book_count_many'),read:lidos,reading:lendo,want:quero});
}
function blocoLendoEstante(){
  const l=prateleira.find(x=>x.status==='Lendo');
  if(!l) return '';
  return `<section class="shelf-now"><div class="label">${t('reading_now')}</div>${lendoAgoraCard(l,prateleira.indexOf(l),true)}</section>`;
}
function renderPrateleira(){
  if(!prateleira.length){
    $('#prateleira').innerHTML=`<div class="empty-rich"><div class="ei">📚</div>
      <h3>${t('empty_shelf_title')}</h3><p>${t('empty_shelf_hint')}</p>
      <button class="btn-cta" onclick="irPara('buscar')">${t('search_button')}</button></div>`;
    return;
  }
  const itens=prateleira.map((l,i)=>({l,i})).filter(({l})=>filtroEstante==='Todos'||l.status===filtroEstante);
  const vazio=`<div class="empty shelf-empty">${t('shelf_filter_empty',{filter:esc(filtroEstante)})}</div>`;
  const corpo=visualizacaoEstante==='lista'
    ? `<ul class="shelf-list">${itens.map(({l,i})=>{
        const cap=coverHTML(l.titulo,l.autor,l.capa_url,'').replace('class="cover','class="shelf-cover');
        const statusNota=[statusLabel(l.status),l.nota?`${estrelasStr(l.nota)} ${l.nota.toLocaleString(getLocale())}`:t('no_rating')].filter(Boolean).join(' · ');
        const dataAno=[l.data,l.ano_edicao||l.ano_obra].filter(Boolean).join(' · ');
        return `<li class="shelf-row ${livroEstaDestacado(l)?'saved-highlight':''}" role="button" tabindex="0" onclick="abrirCard(${i})" aria-label="${esc(l.titulo)}">${cap}
          <div class="shelf-row-body">
            <button class="shelf-row-title work-title-link" type="button" onclick="event.stopPropagation(); abrirPaginaObraDaLeitura(${i})">${esc(l.titulo)}</button>
            <div class="shelf-row-author">${esc(l.autor)}</div>
            <div class="shelf-row-status">${esc(statusNota)}</div>
            ${metaListaEstante(l)?`<div class="shelf-row-meta">${metaListaEstante(l)}</div>`:''}
            ${dataAno?`<div class="shelf-row-date">${esc(dataAno)}</div>`:''}${reviewCardActionHTML(i,'shelf-row-review-card')}${(l.tenho_edicao||l.quero_edicao)?`<div class="shelf-edition-flags">${l.tenho_edicao?t('you_have_this_edition'):''}${l.tenho_edicao&&l.quero_edicao?' · ':''}${l.quero_edicao?t('you_want_this_edition'):''}</div>`:''}
          </div></li>`;
      }).join('')}</ul>`
    : `<div class="wall shelf-wall">${itens.map(({l,i})=>`
        <div class="book ${livroEstaDestacado(l)?'saved-highlight':''}" role="button" tabindex="0" onclick="abrirCard(${i})" aria-label="${esc(l.titulo)}">
          ${coverHTML(l.titulo,l.autor,l.capa_url,l.nota?`<span class="stars-overlay"><span>${estrelasStr(l.nota)}</span><span>${l.nota.toLocaleString(getLocale())}</span></span>`:'').replace('class="cover','class="shelf-cover')}
          <button class="t work-title-link" type="button" onclick="event.stopPropagation(); abrirPaginaObraDaLeitura(${i})">${esc(l.titulo)}</button>
          <div class="a">${esc(l.autor)}</div>
          ${l.tradutor?`<div class="e">${t('translator_abbr')} ${esc(l.tradutor)}</div>`:''}${reviewCardActionHTML(i,'book-review-card')}${(l.tenho_edicao||l.quero_edicao)?`<div class="e shelf-edition-flags">${l.tenho_edicao?t('you_have_this_edition'):t('you_want_this_edition')}</div>`:''}
        </div>`).join('')}</div>`;
  $('#prateleira').innerHTML=`<p class="shelf-summary">${resumoEstante()}</p>`+conviteLoginHTML()+blocoLendoEstante()+controlesEstante()+(itens.length?corpo:vazio);
}
async function carregarPrateleira(){
  try{ prateleira=await (await fetch('/api/prateleira')).json(); diarioEntradas=await (await fetch('/api/diario')).json(); }catch(e){ return; }
  renderLendoAgora();
  renderPrateleira();
  renderDiario();
  aplicarSubabaEstante(navAtual.estanteSub||'shelf');
}

/* diário — linha do tempo */
function progressoDiario(e){
  const partes=[];
  if(e.pagina!==null&&e.pagina!==undefined) partes.push(t('page_short',{count:esc(e.pagina)}));
  if(e.porcentagem!==null&&e.porcentagem!==undefined) partes.push(t('percent_complete_short',{count:esc(e.porcentagem)}));
  if(e.capitulo) partes.push(e.progresso_tipo==='livre'?esc(e.capitulo):`${t('chapter')} ${esc(e.capitulo)}`);
  return partes.join(' · ') || (e.nota?t('entry_note'):t('free_progress'));
}
function progressoLeitura(l){
  const entradas=diarioEntradas.filter(e=>e.leitura_id===l.leitura_id).sort((a,b)=>new Date(b.created_at||0)-new Date(a.created_at||0));
  const pct=entradas.find(e=>e.porcentagem!==null&&e.porcentagem!==undefined);
  if(pct) return {texto:t('percent_complete',{count:esc(pct.porcentagem)}),barra:Number(pct.porcentagem)};
  const pag=entradas.find(e=>e.pagina!==null&&e.pagina!==undefined);
  if(pag) return {texto:t('page_short',{count:esc(pag.pagina)}),barra:null};
  const cap=entradas.find(e=>e.capitulo);
  if(cap) return {texto:cap.progresso_tipo==='livre'?esc(cap.capitulo):`${t('chapter')} ${esc(cap.capitulo)}`,barra:null};
  if(l.status==='Lido') return {texto:t('percent_complete',{count:100}),barra:100};
  return {texto:'',barra:null};
}
function dataDiario(e){
  try{return new Date(e.created_at).toLocaleDateString(getLocale(),{day:'2-digit',month:'short'});}catch(_){return '';}
}
async function carregarCapitulosEdicao(form){
  const edicaoId=form?.dataset?.edicaoId;
  const datalist=form?.querySelector('[data-diary-chapter-list]');
  if(!edicaoId||!datalist||datalist.dataset.loaded) return;
  datalist.dataset.loaded='1';
  try{
    const res=await fetch(`/api/edicoes/${edicaoId}/capitulos`);
    if(!res.ok) return;
    const capitulos=await res.json();
    datalist.innerHTML=(capitulos||[]).map(c=>`<option value="${esc(c.titulo)}">`).join('');
  }catch(_){ datalist.dataset.loaded=''; }
}
function configurarInputProgressoDiario(form,tipoSeguro){
  const valorInput=form?.querySelector('[data-diary-input="valor"]');
  const label=form?.querySelector('[data-diary-progress-label]');
  const suffix=form?.querySelector('[data-diary-progress-suffix]');
  if(!valorInput) return;
  const datalist=form.querySelector('[data-diary-chapter-list]');
  const ordemField=form.querySelector('[data-diary-chapter-order-field]');
  if(tipoSeguro==='capitulo'){
    if(datalist) valorInput.setAttribute('list',datalist.id);
    carregarCapitulosEdicao(form);
    if(ordemField) ordemField.hidden=false;
  } else {
    valorInput.removeAttribute('list');
    if(ordemField) ordemField.hidden=true;
  }
  const config={
    pagina:{type:'number',inputmode:'numeric',min:'1',max:'',placeholder:t('diary_page_placeholder'),label:t('diary_page_label'),suffix:''},
    porcentagem:{type:'number',inputmode:'numeric',min:'0',max:'100',placeholder:t('diary_percent_placeholder'),label:t('diary_percent_label'),suffix:'%'},
    capitulo:{type:'text',inputmode:'text',min:'',max:'',placeholder:t('chapter_placeholder'),label:t('diary_chapter_label'),suffix:''}
  }[tipoSeguro];
  const valorAtual=String(valorInput.value||'').trim();
  valorInput.type=config.type;
  valorInput.setAttribute('inputmode',config.inputmode);
  valorInput.placeholder=config.placeholder;
  valorInput.step=tipoSeguro==='capitulo'?'':'1';
  if(config.min==='') valorInput.removeAttribute('min'); else valorInput.min=config.min;
  if(config.max==='') valorInput.removeAttribute('max'); else valorInput.max=config.max;
  if(label) label.textContent=config.label;
  if(suffix){
    suffix.textContent=config.suffix;
    suffix.hidden=!config.suffix;
  }
  if(tipoSeguro==='pagina'||tipoSeguro==='porcentagem'){
    const numero=Number(valorAtual);
    const valido=valorAtual===''||(Number.isFinite(numero)&&Number.isInteger(numero)&&(tipoSeguro==='pagina'?numero>0:(numero>=0&&numero<=100)));
    if(!valido) valorInput.value='';
  }
}
function selecionarTipoDiario(id='',tipo='pagina',el=null){
  const tiposValidos=['pagina','porcentagem','capitulo'];
  const tipoSeguro=tiposValidos.includes(String(tipo||'').trim().toLowerCase())?String(tipo||'').trim().toLowerCase():'pagina';
  let form=el?.closest?.('[data-diary-form]')||null;
  if(!form&&id) form=document.querySelector(`[data-diary-form="${CSS.escape(String(id))}"]`);
  if(!form) return;
  const input=form.querySelector('[data-diary-input="tipo"]');
  if(input) input.value=tipoSeguro;
  form.querySelectorAll('[data-progress-chip]').forEach(btn=>{
    const ativo=btn.dataset.progressChip===tipoSeguro;
    btn.classList.toggle('active',ativo);
    btn.setAttribute('aria-pressed',ativo?'true':'false');
  });
  configurarInputProgressoDiario(form,tipoSeguro);
}
function atualizarCamposDiario(id=''){
  const form=id?document.querySelector(`[data-diary-form="${CSS.escape(String(id))}"]`):null;
  const tipo=form?.querySelector('[data-diary-input="tipo"]')?.value||'pagina';
  selecionarTipoDiario(id,tipo,form);
}
function formDiarioHTML(leituraId, entry=null, edicaoId=null){
  const id=entry?.id||'';
  const formKey=entry?.id?`edit_${entry.id}`:`new_${leituraId}`;
  const chapterListId=`diaryChapterList_${formKey}`;
  const tipoEntrada=String(entry?.progresso_tipo||'').trim().toLowerCase();
  const tipoInicial=tipoEntrada==='pagina'||tipoEntrada==='porcentagem'||tipoEntrada==='capitulo'?tipoEntrada:(entry?.pagina!==null&&entry?.pagina!==undefined?'pagina':(entry?.porcentagem!==null&&entry?.porcentagem!==undefined?'porcentagem':(entry?.capitulo?'capitulo':'pagina')));
  const tipo=tipoInicial==='pagina'||tipoInicial==='porcentagem'||tipoInicial==='capitulo'?tipoInicial:'pagina';
  const valorInicial=tipo==='pagina'?(entry?.pagina??''):(tipo==='porcentagem'?(entry?.porcentagem??''):(entry?.capitulo||''));
  const inputType=tipo==='capitulo'?'text':'number';
  const inputMode=tipo==='capitulo'?'text':'numeric';
  const minAttr=tipo==='pagina'?' min="1"':(tipo==='porcentagem'?' min="0"':'');
  const maxAttr=tipo==='porcentagem'?' max="100"':'';
  const placeholder=tipo==='pagina'?t('diary_page_placeholder'):(tipo==='porcentagem'?t('diary_percent_placeholder'):t('chapter_placeholder'));
  const label=tipo==='pagina'?t('diary_page_label'):(tipo==='porcentagem'?t('diary_percent_label'):t('diary_chapter_label'));
  const chip=(valor,label)=>`<button type="button" class="progress-unit ${tipo===valor?'active':''}" data-progress-chip="${valor}" aria-pressed="${tipo===valor?'true':'false'}" onclick="selecionarTipoDiario('${formKey}','${valor}',this)">${label}</button>`;
  return `<div class="diary-form" data-diary-form="${formKey}"${edicaoId?` data-edicao-id="${edicaoId}"`:''}>
    <div class="label diary-form-title">${t('update_progress')}</div>
    <p class="form-helper diary-form-helper">${t('new_diary_subtitle')} · ${t('private_by_default')}</p>
    <input type="hidden" id="diaryProgressType_${formKey}" data-diary-input="tipo" value="${tipo}">
    <div class="field diary-progress-field"><label class="label" for="diaryProgressInput_${formKey}" data-diary-progress-label>${label}</label><div class="diary-progress-row"><div class="suffix-field diary-progress-value"><input id="diaryProgressInput_${formKey}" data-diary-input="valor" type="${inputType}" inputmode="${inputMode}"${minAttr}${maxAttr} step="1" value="${esc(valorInicial)}" placeholder="${placeholder}"${tipo==='capitulo'?` list="${chapterListId}"`:''}><span data-diary-progress-suffix${tipo==='porcentagem'?'':' hidden'}>%</span></div><div class="progress-units" aria-label="${t('how_track_progress')}">${chip('pagina',t('unit_page_short'))}${chip('porcentagem',t('unit_percent_short'))}${chip('capitulo',t('unit_chapter_short'))}</div></div><datalist id="${chapterListId}" data-diary-chapter-list></datalist></div>
    <div class="field diary-chapter-order-field" data-diary-chapter-order-field${tipo==='capitulo'?'':' hidden'}><label class="label" for="diaryChapterOrderInput_${formKey}">${t('diary_chapter_order_label')}</label><input id="diaryChapterOrderInput_${formKey}" data-diary-input="capitulo_ordem" type="number" inputmode="numeric" min="1" step="1" value="${esc(entry?.capitulo_ordem??'')}" placeholder="${t('diary_chapter_order_placeholder')}"></div>
    <div class="field"><label class="label" for="diaryNoteInput_${formKey}">${t('entry_note')}</label><textarea id="diaryNoteInput_${formKey}" data-diary-input="nota" maxlength="2000" placeholder="${t('entry_note_placeholder')}">${esc(entry?.nota||'')}</textarea></div>
    <div class="visibility-box"><label class="check-line"><input type="checkbox" id="diarySpoilerInput_${formKey}" data-diary-input="spoiler" ${entry?.spoiler?'checked':''}> <span>${t('contains_spoiler')}</span></label><label class="check-line"><input type="checkbox" id="diaryPublicInput_${formKey}" data-diary-input="publico" ${entry?.publico?'checked':''}> <span>${t('show_on_public_profile')}</span></label></div>
    <button class="btn-primary" onclick="salvarDiario(${leituraId},'${id}',this)">${t('save_diary')}</button>
  </div>`;
}
function buildDiaryPayload(form){
  if(!form) return null;
  const tiposValidos=['pagina','porcentagem','capitulo'];
  const normalizarTipo=valor=>{
    const tipo=String(valor||'').trim().toLowerCase();
    return tiposValidos.includes(tipo)?tipo:'';
  };
  const campo=nome=>form.querySelector(`[data-diary-input="${nome}"]`);
  const tipoHidden=normalizarTipo(campo('tipo')?.value);
  const tipoChip=normalizarTipo(form.querySelector('[data-progress-chip].active')?.dataset?.progressChip);
  const progresso_tipo=tipoHidden||tipoChip||'pagina';
  const valorRaw=(campo('valor')?.value||'').trim();
  const valorNumber=Number(valorRaw);
  const pagina=progresso_tipo==='pagina'&&valorRaw!==''&&Number.isInteger(valorNumber)&&valorNumber>0?valorNumber:null;
  const porcentagem=progresso_tipo==='porcentagem'&&valorRaw!==''&&Number.isFinite(valorNumber)&&valorNumber>=0&&valorNumber<=100?valorNumber:null;
  const capitulo=progresso_tipo==='capitulo'?valorRaw:'';
  const ordemRaw=(campo('capitulo_ordem')?.value||'').trim();
  const ordemNumber=Number(ordemRaw);
  const capitulo_ordem=progresso_tipo==='capitulo'&&ordemRaw!==''&&Number.isInteger(ordemNumber)&&ordemNumber>0?ordemNumber:null;
  return {
    progresso_tipo,
    pagina,
    porcentagem,
    capitulo,
    capitulo_ordem,
    nota:(campo('nota')?.value||'').trim(),
    publico:!!campo('publico')?.checked,
    spoiler:!!campo('spoiler')?.checked
  };
}
function payloadDiario(id='',el=null){
  const form=el?.closest?.('[data-diary-form]')||null;
  if(!form) return null;
  return buildDiaryPayload(form);
}
function validarPayloadDiario(payload){
  const paginaValida=Number.isInteger(payload.pagina)&&payload.pagina>0;
  const pctValida=Number.isFinite(payload.porcentagem)&&payload.porcentagem>=0&&payload.porcentagem<=100;
  const capValido=!!payload.capitulo;
  const notaValida=!!payload.nota;
  if(paginaValida||pctValida||capValido||notaValida) return '';
  return t('inform_progress_or_note');
}
async function salvarDiario(leituraId,id='',el=null){
  const payload=payloadDiario(id,el);
  const form=el?.closest?.('[data-diary-form]')||null;
  limparErroFormulario(form);
  if(!payload){ mostrarErroFormulario(form,t('diary_save_error')); return; }
  debugLog('diary payload',payload);
  const erro=validarPayloadDiario(payload);
  if(erro){ console.warn('invalid diary payload',payload,erro); mostrarErroFormulario(form,erro); return; }
  const url=id?`/api/diario/${id}`:`/api/leitura/${leituraId}/diario`;
  const method=id?'PATCH':'POST';
  try{
    const r=await fetch(url,{method,headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
    if(!r.ok){
      let body='';
      try{ body=await r.text(); }catch(_){ body=''; }
      console.error('[diario save error]',r.status,body);
      const mensagem=r.status===401||r.status===403?t('diary_login_error'):r.status===422?t('inform_progress_or_note'):t('diary_save_error');
      mostrarErroFormulario(form,mensagem);
      toast(mensagem);
      return;
    }
    diarioEditId=null; await carregarPrateleira(); if(cardAtual) renderDetalheLivro(cardAtual); else renderDiario(); toast(t('diary_entry_saved'));
  }catch(e){ console.error('[diario save error]',0,e); mostrarErroFormulario(form,t('diary_save_error')); toast(t('diary_save_error')); }
}
async function excluirDiario(id,el=null){
  confirmarEmDoisPassos(el,`diario_${id}`,async()=>{
    const r=await fetch(`/api/diario/${id}`,{method:'DELETE'});
    if(r.ok) await carregarPrateleira();
    else toast(t('diary_save_error'));
  });
}
async function prepararCardCritica(idx){
  const l=prateleira[idx];
  if(!l){ toast(t('card_generation_error')); return; }
  if(!(l.relato||'').trim()){ toast(t('review_card_empty')); return; }
  await abrirCard(idx,{registrar:true,cardType:'critica'});
  document.getElementById('shareCardPreview')?.scrollIntoView({behavior:'smooth',block:'center'});
}
function reviewCardActionHTML(i,extraClass=''){
  const l=prateleira[i];
  if(!l || !(l.relato||'').trim()) return '';
  return `<button type="button" class="review-card-action ${extraClass}" onclick="event.stopPropagation();prepararCardCritica(${i})">${t('review_card_cta')}</button>`;
}

async function prepararCardDiario(id){
  const e=diarioEntradas.find(x=>String(x.id)===String(id));
  if(!e){ toast(t('card_generation_error')); return; }
  const idx=prateleira.findIndex(l=>String(l.leitura_id)===String(e.leitura_id));
  if(idx<0){ toast(t('diary_card_missing_reading')); return; }
  if(cardAtual!==prateleira[idx]){
    await abrirCard(idx,{registrar:true});
  }
  cardContext={type:'diario',source:e};
  cardIncludeExcerpt=!!((e.nota||'').trim()&&!e.spoiler);
  renderDetalheLivro(cardAtual);
  await updateShareCardPreview(cardAtual);
  document.getElementById('shareCardPreview')?.scrollIntoView({behavior:'smooth',block:'center'});
}

function cardEntradaDiario(e, opts={}){
  const nota=e.nota? (e.spoiler?`<details class="drelato spoiler-note"><summary>${t('contains_spoiler')}</summary><div>“${esc(e.nota)}”</div></details>`:`<div class="drelato">“${esc(e.nota)}”</div>`):'';
  const vis=e.publico?t('public_note'):'';
  return `<article class="diary-entry-card">
    <div class="dtop"><span class="dt entry-date">${dataDiario(e)}</span></div>
    <div class="dmeta">${[vis,e.spoiler?t('contains_spoiler'):'' ].filter(Boolean).join(' · ')}</div>
    <div class="diary-progress">${progressoDiario(e)}</div>
    ${nota}
    <div class="diary-actions"><button onclick="diarioEditId=${e.id}; ${opts.inDetail?'renderDetalheLivro(cardAtual)':'renderDiario()'}">${t('edit_diary_entry')}</button><button onclick="prepararCardDiario(${e.id})">${t('diary_card')}</button><button onclick="excluirDiario(${e.id},this)">${t('delete_diary_entry')}</button></div>
    ${diarioEditId===e.id?formDiarioHTML(e.leitura_id,e,prateleira.find(l=>l.leitura_id===e.leitura_id)?.edicao_id):''}
  </article>`;
}
function agruparEntradasDiario(){
  const grupos=new Map();
  diarioEntradas.forEach(e=>{
    const chave=e.leitura_id!==null&&e.leitura_id!==undefined?String(e.leitura_id):`entry_${e.id}`;
    if(!grupos.has(chave)) grupos.set(chave,[]);
    grupos.get(chave).push(e);
  });
  return [...grupos.values()].map(entradas=>entradas.sort((a,b)=>new Date(b.created_at||0)-new Date(a.created_at||0))).sort((a,b)=>new Date(b[0]?.created_at||0)-new Date(a[0]?.created_at||0));
}
function diarioGrupoHTML(entradas){
  const primeira=entradas[0]||{};
  const i=prateleira.findIndex(l=>String(l.leitura_id)===String(primeira.leitura_id));
  const l=i>=0?prateleira[i]:null;
  const titulo=l?.titulo||primeira.titulo||t('untitled_book');
  const autor=l?.autor||primeira.autor||'';
  const capa=l?.capa_url||primeira.capa_url||'';
  const cover=coverHTML(titulo,autor,capa,'').replace('class="cover','class="diary-book-cover');
  const count=entradas.length===1?t('diary_entry_count_one') : t('diary_entry_count_many',{count:entradas.length});
  const meta=[progressoDiario(primeira), count, dataDiario(primeira)].filter(Boolean).map(esc).join(' · ');
  const openAttrs=i>=0?` role="button" tabindex="0" onclick="abrirCard(${i})" onkeydown="if(event.key==='Enter'||event.key===' '){event.preventDefault();abrirCard(${i})}"`:'';
  return `<section class="diary-group diary-book-row"${openAttrs}>
    <div class="diary-book-cover-wrap">${cover}</div>
    <div class="diary-group-copy"><div class="diary-group-title">${esc(titulo)}</div><div class="diary-group-author">${esc(autor)}</div><div class="diary-group-meta">${meta}</div></div>
    <div class="diary-group-arrow" aria-hidden="true">▾</div>
  </section>`;
}

function renderDiario(){
  const lendo=prateleira.find(l=>l.status==='Lendo');
  const lendoIdx=lendo?prateleira.indexOf(lendo):-1;
  const cta=lendo?`<button class="btn-cta" onclick="abrirDiarioLeitura(${lendoIdx})">${t('update_progress')}</button>`:`<button class="btn-cta" onclick="irPara('buscar')">${t('search_books')} →</button>`;
  if(!diarioEntradas.length){ $('#diario').innerHTML=`<div class="empty-rich"><div class="ei">📖</div><h3>${t('empty_diary_title')}</h3><p>${t('empty_diary_hint')}</p>${cta}</div>`; return; }
  $('#diario').innerHTML=`<div class="diary-head">${lendo?`<div class="diary-continue">${lendoAgoraCard(lendo,lendoIdx,true)}</div>`:''}<p class="diary-helper">${t('diary_hint')}</p></div><div class="diary diary-grouped">${agruparEntradasDiario().map(diarioGrupoHTML).join('')}</div>`;
}
/* perfil */
function abrirMinhaEstantePerfil(){
  filtroEstante='Todos';
  irPara('estante',{subaba:'shelf'});
}
function estatisticasPerfilHTML(total,lendo,lidos,quero){
  if(!total){
    return `<section class="account-box profile-stats-box profile-stats-empty"><div class="label">${t('your_lombada')}</div><p>${t('profile_shelf_empty')}</p><button class="pbtn solid" type="button" onclick="irPara('buscar')">${t('search_books')}</button></section>`;
  }
  const stats=[
    [total,t('profile_stat_readings')],
    [lendo,t('currently_reading')],
    [lidos,t('status_read')],
    [quero,t('want_to_read')]
  ];
  return `<section class="account-box profile-stats-box"><div class="label">${t('your_lombada')}</div><div class="profile-quick-stats">${stats.map(([valor,label])=>`<div><strong>${valor}</strong><span>${label}</span></div>`).join('')}</div><button class="pbtn solid profile-shelf-cta" type="button" onclick="abrirMinhaEstantePerfil()">${t('view_my_shelf')}</button></section>`;
}
function normalizarHandlePerfil(valor){
  return (valor||'').toString().trim().toLowerCase()
    .normalize('NFD').replace(/[\u0300-\u036f]/g,'')
    .replace(/\s+/g,'-').replace(/[^a-z0-9-]/g,'').replace(/-+/g,'-')
    .slice(0,24).replace(/^-+|-+$/g,'');
}
function atualizarPreviewHandlePerfil(){
  const input=$('#profileHandleInput');
  const preview=$('#profileHandlePreview');
  if(!input||!preview) return;
  const handle=normalizarHandlePerfil(input.value);
  preview.textContent=handle?`${t('profile_preview')} /u/${handle}`:t('profile_preview_empty');
}
function atualizarContadorBioPerfil(){
  const input=$('#profileBioInput');
  const counter=$('#profileBioCounter');
  if(!input||!counter) return;
  counter.textContent=t('profile_bio_count',{count:(input.value||'').length});
}
function validarPerfilPayload(payload){
  if(!payload.nome) return t('profile_name_required');
  if(payload.nome.length<2||payload.nome.length>40) return t('profile_name_length');
  if(payload.nome.includes('@')) return t('profile_name_no_email');
  if(!/^[a-z0-9](?:[a-z0-9-]{1,22}[a-z0-9])$/.test(payload.handle)||payload.handle.includes('--')) return t('profile_handle_invalid');
  if((payload.bio||'').length>160) return t('profile_bio_length');
  return '';
}
async function salvarPerfil(el=null){
  const form=el?.closest?.('.profile-edit-form')||$('#profileEditForm');
  limparErroFormulario(form);
  const handleInput=$('#profileHandleInput');
  const normalizedHandle=normalizarHandlePerfil(handleInput?.value||'');
  if(handleInput) handleInput.value=normalizedHandle;
  atualizarPreviewHandlePerfil();
  atualizarContadorBioPerfil();
  const payload={
    nome:($('#profileNameInput')?.value||'').trim().replace(/\s+/g,' '),
    handle:normalizedHandle,
    bio:($('#profileBioInput')?.value||'').trim().replace(/\s+/g,' ')
  };
  const erro=validarPerfilPayload(payload);
  if(erro){ mostrarErroFormulario(form,erro); return; }
  try{
    const res=await fetch('/api/eu/perfil',{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
    const body=await res.json().catch(()=>({}));
    if(!res.ok){ mostrarErroFormulario(form,res.status===409?t('profile_handle_taken'):(body.detail||t('profile_save_error'))); return; }
    minhaConta={...minhaConta,...body};
    meuHandle=body.handle||payload.handle;
    const crumb=$('#meuhandle'); if(crumb) crumb.textContent='@'+meuHandle;
    toast(body.message||t('profile_updated'));
    renderPerfil();
  }catch(e){ mostrarErroFormulario(form,t('profile_save_error')); }
}
function renderPerfil(){
  const url=location.origin+'/u/'+meuHandle;
  const n=prateleira.length;
  const logado=!!minhaConta.logado;
  const nome=(minhaConta.nome||'').trim();
  const email=(minhaConta.email||'').trim();
  const bio=(minhaConta.bio||'').trim();
  const lidos=prateleira.filter(l=>l.status==='Lido').length, lendo=prateleira.filter(l=>l.status==='Lendo').length, quero=prateleira.filter(l=>l.status==='Quero ler').length;
  const edicoesPossui=minhaConta.edicoes_possui ?? prateleira.filter(l=>l.tenho_edicao).length;
  const edicoesDesejadas=minhaConta.edicoes_desejadas ?? prateleira.filter(l=>l.quero_edicao).length;
  const inicial=(nome||meuHandle||'L').trim().charAt(0).toUpperCase();
  const temConteudoPublico=prateleira.some(l=>l.publico);
  const previewHTML=`
    <div class="account-box public-profile-card public-preview-box">
      <div class="label">${t('public_profile')}</div>
      <p>${t('public_profile_hint')}</p>
      ${temConteudoPublico?'':`<p class="muted public-profile-empty">${t('public_profile_empty')}</p>`}
      <div class="profile-public-actions profile-actions">
        <a class="pbtn solid" href="${esc(url)}" target="_blank" rel="noopener" onclick="toast(t('public_profile_opened'))">${t('view_public_profile')}</a>
        <button class="pbtn" type="button" onclick="copiarLinkPerfil()">${t('copy_profile_link')}</button>
        <button class="pbtn" type="button" onclick="compartilharPerfil()">${t('share_profile')}</button>
      </div>
    </div>
  `;
  const contaHTML=logado
    ? `<div class="account-box connected">
        <div class="label">${t('account')}</div>
        <p>${t('account_connected')}</p>
        ${nome?`<div class="account-line">${esc(nome)}</div>`:''}
        ${email?`<div class="account-line muted">${esc(email)}</div>`:''}
        <a class="account-logout" href="/api/auth/logout">${t('logout')}</a>
      </div>`
    : `<div class="account-box">
        <div class="label">${t('account')}</div>
        <p>${t('account_anon')}</p>
        <p class="muted">${t('account_login_hint')}</p>
        <a class="pbtn solid" href="/api/auth/google/login">${t('login_google')}</a>
      </div>`;
  const editarPerfilHTML=logado?`
      <form id="profileEditForm" class="account-box profile-edit-form" onsubmit="event.preventDefault();salvarPerfil(this.querySelector('button[type=submit]'))">
        <div class="label">${t('edit_profile')}</div>
        <div class="profile-edit-field">
          <label for="profileNameInput">${t('profile_display_name')}</label>
          <input id="profileNameInput" type="text" minlength="2" maxlength="40" autocomplete="name" value="${esc(nome)}" placeholder="${t('profile_display_name')}">
        </div>
        <div class="profile-edit-field">
          <label for="profileHandleInput">${t('profile_username')}</label>
          <div class="profile-handle-input"><span>@</span><input id="profileHandleInput" type="text" minlength="3" maxlength="24" autocapitalize="none" spellcheck="false" value="${esc(meuHandle)}" oninput="this.value=normalizarHandlePerfil(this.value);atualizarPreviewHandlePerfil()"></div>
          <p id="profileHandlePreview" class="profile-handle-preview">${t('profile_preview')} /u/${esc(meuHandle)}</p>
        </div>
        <div class="profile-edit-field">
          <label for="profileBioInput">${t('profile_short_bio')}</label>
          <textarea id="profileBioInput" maxlength="160" placeholder="${t('profile_bio_placeholder')}" oninput="atualizarContadorBioPerfil()">${esc(bio)}</textarea>
          <p id="profileBioCounter" class="profile-handle-preview">${t('profile_bio_count',{count:bio.length})}</p>
        </div>
        <button class="btn-primary" type="submit">${t('save_changes')}</button>
      </form>`:'';
  $('#perfil').innerHTML=`
    <div class="pcard">
      <div class="profile-avatar">${esc(inicial)}</div>
      <div class="phandle">${nome?esc(nome):t('lombada_reader')}</div>
      <div class="pcount">@${esc(meuHandle)} · ${plural(n,'book_count_one','book_count_many')} · ${t('followers_count',{count:minhaConta.followers_count||0})} · ${t('following_count',{count:minhaConta.following_count||0})}</div>
      ${bio?`<p class="profile-bio">${esc(bio)}</p>`:''}
      <div class="profile-metrics"><div><strong>${lidos}</strong><span>${t('status_read')}</span></div><div><strong>${edicoesPossui}</strong><span>${t('owned_editions')}</span></div><div><strong>${edicoesDesejadas}</strong><span>${t('wanted_editions')}</span></div></div>
      ${editarPerfilHTML}
      <div class="account-box theme-box">
        <div class="label">${t('appearance')}</div>
        <p>${t('appearance_hint')}</p>
        <div class="theme-options" role="radiogroup" aria-label="${t('theme')}">
          <label class="theme-option"><input type="radio" name="themeChoice" value="light" onchange="definirTema(this.value)" ${document.body.getAttribute('data-theme')==='light'?'checked':''}><span>${t('theme_light')}</span></label>
          <label class="theme-option"><input type="radio" name="themeChoice" value="dark" onchange="definirTema(this.value)" ${document.body.getAttribute('data-theme')==='dark'?'checked':''}><span>${t('theme_dark')}</span></label>
        </div>
      </div>
      <div class="account-box language-box">
        <div class="label">${t('language')}</div>
        <p>${t('language_hint')}</p>
        <div class="theme-options" role="radiogroup" aria-label="${t('language')}">
          ${['pt-BR','en','es'].map(locale=>`<label class="theme-option"><input type="radio" name="localeChoice" value="${locale}" onchange="mudarIdioma(this.value)" ${getLocale()===locale?'checked':''}><span>${t(locale==='pt-BR'?'language_pt_br':locale==='en'?'language_en':'language_es')}</span></label>`).join('')}
        </div>
      </div>
      ${previewHTML}
      ${estatisticasPerfilHTML(n,lendo,lidos,quero)}
      <div class="account-box library-box">
        <div class="label">${t('library')}</div>
        <p>${t('library_hint')}</p>
        <button class="pbtn" onclick="abrirManual()">${t('manual_prominent_button')}</button>
      </div>
      ${contaHTML}
      ${installCtaHTML()}
      ${(appVersion&&appVersion!=='dev')?`<div class="app-version">${/^\d/.test(appVersion.replace(/\.0$/,''))?'Lombada v':'Lombada · '}${esc(appVersion.replace(/\.0$/,''))}</div>`:''}
      <div class="plink">${esc(url)}</div>
    </div>`;
}

function urlPerfilPublico(){
  const handle=(meuHandle||'').trim();
  return handle ? `${window.location.origin}/u/${encodeURIComponent(handle)}` : '';
}
function textoCompartilhamentoLeitura(l){
  const title=l?.titulo || '';
  const payload=cardSharePayload();
  let txt=t(payload.shareKey,{title});
  if(cardIncludeExcerpt && payload.excerpt) txt+=' “'+payload.excerpt+'”';
  return txt;
}
async function copiarLink(url, promptKey='copy_profile_link_prompt'){
  if(!url){ toast(t('link_copy_failed')); return false; }
  try{
    await navigator.clipboard.writeText(url);
    toast(t('link_copied'));
    return true;
  }catch(e){
    console.warn(t(promptKey),url);
    toast(`${t('link_copy_failed')} ${url}`);
    return false;
  }
}
async function copiarLinkPerfil(){ await copiarLink(urlPerfilPublico(),'copy_profile_link_prompt'); }
async function compartilharPerfil(){
  const url=urlPerfilPublico();
  if(!url){ toast(t('link_copy_failed')); return; }
  if(navigator.share){ try{ await navigator.share({title:t('profile_share_title'),url}); return; }catch(e){} }
  const copied=await copiarLinkPerfil();
  if(copied) toast(t('share_unavailable_copied'));
}
async function compartilharEstante(){
  await compartilharPerfil();
}

/* ---------- card / modal ---------- */

function nomeCapaCard(){
  if(cardCoverIndex===0) return t('original_cover');
  return t(cardCoverIndex===1?'lombada_cover_title_page':'lombada_cover_dark_collection');
}
function atualizarControleCapaCard(){
  const label=$('#cardCoverModeLabel');
  if(label) label.textContent=nomeCapaCard();
}
function trocarCapaCard(){
  if(!cardAtual)return;
  cardCoverAutoLowRes=false;
  cardCoverUserChanged=true;
  cardCoverIndex=(cardCoverIndex+1)%3;
  atualizarControleCapaCard();
  updateShareCardPreview(cardAtual);
  toast(nomeCapaCard());
}
function usarCapaGeradaPorBaixaResolucao(){
  if(cardCoverIndex!==0 || cardCoverAutoLowRes || cardCoverUserChanged)return;
  cardCoverAutoLowRes=true;
  cardCoverIndex=1;
  atualizarControleCapaCard();
  toast(t('low_res_cover_toast'));
}

function trechoTexto(s,lim=220){
  const txt=(s||'').toString().replace(/\s+/g,' ').trim();
  return txt.length>lim ? txt.slice(0,lim-1).trimEnd()+'…' : txt;
}
function progressoDiarioCard(e){ return progressoDiario(e).replace(/<[^>]+>/g,'').trim(); }
function cardSharePayload(){
  const l=cardAtual||{}; const src=cardContext.source;
  const isDiary=cardContext.type==='diario'&&src;
  const isReview=cardContext.type==='critica'||(!isDiary && (l.relato||'').trim());
  const raw=isDiary?(src.nota||''):(isReview?(l.relato||''):'');
  const spoiler=!!(isDiary?src.spoiler:l.spoiler);
  const type=isDiary?'diario':(isReview?'critica':'leitura');
  return {type, excerpt:cardIncludeExcerpt?trechoTexto(raw,isDiary?180:220):'', hasText:!!raw.trim(), spoiler, spoilerLabel:t(isDiary?'diary_with_spoiler':'review_with_spoiler'), progress:isDiary?progressoDiarioCard(src):'', shareKey:isDiary?'share_diary_text':(isReview?'share_review_text':'share_reading_text')};
}
function setCardTheme(v){ cardTheme=['auto','light','dark'].includes(v)?v:'auto'; localStorage.setItem(CARD_THEME_KEY,cardTheme); updateShareCardPreview(cardAtual); }
function setCardIncludeExcerpt(v){ cardIncludeExcerpt=!!v; updateShareCardPreview(cardAtual); }

function diaryCardActive(){ return cardContext.type==='diario' && cardContext.source; }
function reviewCardActive(){ return cardContext.type==='critica' && (cardAtual?.relato||'').trim(); }
function shareCardSize(){ return (diaryCardActive()||reviewCardActive())?{w:1080,h:1350}:{w:1080,h:1920}; }
function configurarCanvasCard(cv){
  if(!cv)return;
  const size=shareCardSize();
  if(cv.width!==size.w) cv.width=size.w;
  if(cv.height!==size.h) cv.height=size.h;
}
function cardPreviewMicrocopy(){
  const partes=[];
  if(!diaryCardActive()){
    const l=cardAtual||{};
    if(l.spoiler && (l.relato||'').trim()) partes.push(t('review_card_spoiler_safe'));
    if(l.publico===false && (l.relato||'').trim()) partes.push(t('review_private_share_notice'));
    return partes.length?`<div class="diary-card-notice">${partes.map(x=>`<p>${esc(x)}</p>`).join('')}</div>`:'';
  }
  const e=cardContext.source;
  if(e.spoiler) partes.push(t('diary_card_spoiler_safe'));
  if(e.publico===false) partes.push(t('diary_private_share_notice'));
  return partes.length?`<div class="diary-card-notice">${partes.map(x=>`<p>${esc(x)}</p>`).join('')}</div>`:'';
}
function cardPreviewActionsHTML(){
  return `<div class="card-export-actions"><button class="btn-share-card" type="button" onclick="compartilharCard()">${t('share_image')}</button><button class="btn-secondary" type="button" onclick="baixarCard()">${t('download_image')}</button><button class="btn-secondary" type="button" onclick="copiarLinkPerfil()">${t('copy_link')}</button></div>`;
}
function renderDetalheLivro(l){
  const campos=[
    [t('publisher'),l.editora,'editora'],
    [t('translator'),l.tradutor],
    [t('edition_year'),l.ano_edicao||l.ano],
    [t('language_field'),l.idioma],
    [t('isbn'),l.isbn]
  ].filter(([,v])=>v);
  const nota=Number(l.nota)||0;
  const notaTxt=nota ? `<span class="detail-rating-number">${nota.toLocaleString(getLocale())}</span>` : `<span class="detail-muted">${t('no_rating')}</span>`;
  const relato=l.relato ? `<blockquote>${esc(l.relato)}</blockquote>` : `<p class="detail-empty">${t('reading_note_placeholder')}</p>`;
  const dados=campos.length
    ? `<dl class="edition-data">${campos.map(([k,v,campo])=>`<div><dt>${esc(k)}</dt><dd>${campo==='editora'?linkEditoraHTML(v):esc(v)}</dd></div>`).join('')}</dl>${campos.length<3?`<p class="detail-empty edition-note">${t('edition_data_incomplete')}</p>`:''}`
    : `<p class="detail-empty edition-note">${t('edition_data_incomplete')}</p>`;
  if(cardContext.type!=='diario'){
    cardContext={type:(l.relato||'').trim()?'critica':'leitura',source:null};
    cardIncludeExcerpt=!!((l.relato||'').trim() && !l.spoiler);
  }
  $('#bookDetail').innerHTML=`
    <section class="detail-head">
      <div class="detail-cover">
        ${coverHTML(l.titulo,l.autor,l.capa_url,'')}
      </div>
      <div class="detail-titleblock">
        <div class="label">${t('book_detail')}</div>
        <h2 id="bookDetailTitle">${esc(l.titulo)}</h2>
        <p class="detail-author">${esc(l.autor)}</p>
        <span class="status-tag">${esc(statusLabel(l.status||'Lido'))}</span>
      </div>
    </section>
    <section class="detail-section card-cover-control">
      <div class="label">${t('card_visual')}</div>
      <p>${t('card_visual_hint')}</p>
      <button class="btn-cover-card" type="button" onclick="trocarCapaCard()">${t('change_card_cover')} · <span id="cardCoverModeLabel">${nomeCapaCard()}</span></button>
      <div class="card-options"><div class="label">${t('card_theme')}</div><label><input type="radio" name="cardTheme" value="auto" onchange="setCardTheme(this.value)" ${cardTheme==='auto'?'checked':''}> ${t('card_theme_auto')}</label><label><input type="radio" name="cardTheme" value="light" onchange="setCardTheme(this.value)" ${cardTheme==='light'?'checked':''}> ${t('card_theme_light')}</label><label><input type="radio" name="cardTheme" value="dark" onchange="setCardTheme(this.value)" ${cardTheme==='dark'?'checked':''}> ${t('card_theme_dark')}</label><label class="check-line"><input type="checkbox" onchange="setCardIncludeExcerpt(this.checked)" ${cardIncludeExcerpt?'checked':''}> <span>${cardSharePayload().spoiler?t('include_spoiler_excerpt'):t('include_excerpt')}</span></label>${cardSharePayload().spoiler&&cardSharePayload().hasText?`<p class="detail-empty">${t('excerpt_contains_spoiler')}</p>`:''}</div>
      <canvas id="shareCardPreview" class="share-card-preview" width="1080" height="1920" aria-label="${t('share_card')}"></canvas>
      ${cardPreviewMicrocopy()}
      ${cardPreviewActionsHTML()}
    </section>
    <section class="detail-section detail-rating">
      <div class="detail-stars" aria-label="${t('rating')}">${estrelasStr(nota)}</div>
      ${notaTxt}
    </section>
    <section class="detail-section">
      <div class="label">${t('reading_note')}</div>
      <div class="detail-quote">${relato}</div>
    </section>
    <section class="detail-section">
      <div class="label">${t('visibility')}</div>
      <p class="detail-empty">${l.publico?t('public_review'):t('private_review')}${l.spoiler?' · '+t('contains_spoiler'):''}</p>
    </section>
    <section class="detail-section" id="readingDiarySection">
      <div class="label">${t('reading_diary')}</div>
      <p class="detail-empty">${t('diary_hint')}</p>
      <div id="diaryNewForm">${formDiarioHTML(l.leitura_id,null,l.edicao_id)}</div>
      <div class="diary detail-diary">${diarioEntradas.filter(e=>e.leitura_id===l.leitura_id).map(e=>cardEntradaDiario(e,{inDetail:true})).join('') || `<p class="detail-empty">${t('no_diary_entries')}</p>`}</div>
    </section>
    <section class="detail-section">
      <div class="label">${t('edition')}</div>
      ${dados}
      <p class="detail-empty shelf-edition-flags">${t('you_read_this_edition')}${l.tenho_edicao?' · '+t('you_have_this_edition'):''}${l.quero_edicao?' · '+t('you_want_this_edition'):''}</p>
    </section>`;
}
async function abrirCard(i,opcoes={}){
  const registrar=opcoes.registrar ?? true;
  cardAtual=prateleira[i];
  cardCoverIndex=0;
  cardCoverAutoLowRes=false;
  cardCoverUserChanged=false;
  cardContext={type:opcoes.cardType||((cardAtual?.relato||'').trim()?'critica':'leitura'),source:null};
  cardIncludeExcerpt=!!((cardAtual?.relato||'').trim() && !cardAtual?.spoiler);
  $('#editPanel').style.display='none';
  if(!restaurandoHistorico && document.activeElement instanceof HTMLElement) cardOpener=document.activeElement;
  renderDetalheLivro(cardAtual);
  $('#modal').classList.add('open');
  requestAnimationFrame(()=>$('.modal-x')?.focus());
 if(registrar && !restaurandoHistorico){
  const estadoModal={...estadoNav(navAtual.aba,navAtual.busca,true),card:i};
  if(history.state && history.state.lombada && history.state.modal){
    history.replaceState(estadoModal,'');
  }else{
    history.pushState(estadoModal,'');
  }
}
  try{ await document.fonts.ready; }catch(e){}
  updateShareCardPreview(cardAtual);
}
function fecharModal(){
  if(history.state && history.state.lombada && history.state.modal){
    history.back();
    return;
  }
  fecharModalDireto();
}

function starPath(cx,cy,r){const p=new Path2D();let rot=-Math.PI/2;const st=Math.PI/5;
  p.moveTo(cx+Math.cos(rot)*r,cy+Math.sin(rot)*r);
  for(let i=0;i<5;i++){rot+=st;p.lineTo(cx+Math.cos(rot)*r*.42,cy+Math.sin(rot)*r*.42);rot+=st;p.lineTo(cx+Math.cos(rot)*r,cy+Math.sin(rot)*r);}
  p.closePath();return p;}
function drawStars(ctx,x,y,nota,r,gap,color){
  for(let i=0;i<5;i++){const cx=x+r+i*(2*r+gap);const f=Math.max(0,Math.min(1,(nota||0)-i));const p=starPath(cx,y,r);
    ctx.save();ctx.strokeStyle=color;ctx.lineWidth=3;ctx.stroke(p);
    if(f>0){if(f<1){ctx.clip(p);ctx.fillStyle=color;ctx.fillRect(cx-r,y-r,r*2*f,r*2);}else{ctx.fillStyle=color;ctx.fill(p);}}ctx.restore();}
}
function wrapLeft(ctx,text,x,y,maxW,lh,maxL){
  const words=(text||'').split(' ');let line='';const lines=[];
  for(const w of words){const t=line?line+' '+w:w;if(ctx.measureText(t).width>maxW&&line){lines.push(line);line=w;if(lines.length===maxL-1)break;}else line=t;}
  if(line)lines.push(line);const out=lines.slice(0,maxL);
  out.forEach((ln,i)=>ctx.fillText(ln,x,y+i*lh));return y+(out.length-1)*lh;
}
function wrapCenter(ctx,text,cx,cy,maxW,lh,maxL){
  const words=(text||'').split(' ');let line='';const lines=[];
  for(const w of words){const t=line?line+' '+w:w;if(ctx.measureText(t).width>maxW&&line){lines.push(line);line=w;}else line=t;}
  if(line)lines.push(line);const out=lines.slice(0,maxL);
  const y0=cy-(out.length-1)*lh/2;out.forEach((ln,i)=>ctx.fillText(ln,cx,y0+i*lh));
}

function drawCanvasTextLines(ctx,text,x,y,maxW,lh,maxL,align='left'){
  const words=(text||'').toString().trim().split(/\s+/).filter(Boolean);
  const lines=[];let line='';
  for(const word of words.length?words:['']){
    const test=line?line+' '+word:word;
    if(ctx.measureText(test).width>maxW && line){lines.push(line);line=word;if(lines.length>=maxL-1)break;}
    else line=test;
  }
  if(line && lines.length<maxL)lines.push(line);
  const out=lines.length?lines:[''];
  ctx.textAlign=align;
  out.forEach((ln,i)=>ctx.fillText(ln,x,y+i*lh));
  return y+(out.length-1)*lh;
}
function drawPaperTexture(ctx,x,y,w,h,color='rgba(26,23,20,.035)',step=26){
  ctx.save();ctx.beginPath();ctx.rect(x,y,w,h);ctx.clip();ctx.fillStyle=color;
  for(let i=-h;i<w;i+=step){ctx.fillRect(x+i,y,1,h);ctx.fillRect(x,y+i, w,1);}
  ctx.restore();
}
function effectiveCardTheme(){ return cardTheme==='auto'?(document.body.getAttribute('data-theme')==='dark'?'dark':'light'):cardTheme; }
function cardPalette(){ return effectiveCardTheme()==='dark'?{bg1:'#15110E',bg2:'#251B16',text:'#F3EBDD',muted:'#CDBFA9',rule:'rgba(243,235,221,.26)',gold:'#C6A24A',texture:'rgba(255,255,255,.035)'}:{bg1:'#F4EDDF',bg2:'#E5DAC6',text:'#3A322A',muted:'#6F6655',rule:'rgba(26,23,20,.25)',gold:'#A8842F',texture:'rgba(58,50,42,.025)'}; }
function bookHue(title,author){
  const text=`${title||''} ${author||''}`;
  let hash=0;
  for(let i=0;i<text.length;i++) hash=(hash*31+text.charCodeAt(i))%360;
  return hash;
}
function coverAccent(title,author,light=true){
  const hue=bookHue(title,author);
  return `hsl(${hue} ${light?'48% 36%':'44% 58%'})`;
}
function drawShareCardBackground(ctx,l,W,H){
  const p=cardPalette(); ctx.clearRect(0,0,W,H);
  const g=ctx.createLinearGradient(0,0,W,H);
  g.addColorStop(0,p.bg1);g.addColorStop(1,p.bg2);
  ctx.fillStyle=g;ctx.fillRect(0,0,W,H);
  drawPaperTexture(ctx,0,0,W,H,p.texture,34);
}
function fitFontSize(ctx,text,fontFactory,maxW,maxSize,minSize){
  let size=maxSize;
  while(size>minSize){
    ctx.font=fontFactory(size);
    if(ctx.measureText(text||'').width<=maxW)break;
    size-=2;
  }
  ctx.font=fontFactory(size);
  return size;
}
function drawEditorialCoverFrame(ctx,x,y,w,h,{paper,ink,accent,dark=false}){
  ctx.fillStyle=paper;ctx.fillRect(x,y,w,h);
  drawPaperTexture(ctx,x,y,w,h,dark?'rgba(255,255,255,.028)':'rgba(70,54,36,.04)',28);
  ctx.strokeStyle=dark?'rgba(234,224,205,.52)':'rgba(60,44,34,.68)';
  ctx.lineWidth=5;ctx.strokeRect(x+44,y+44,w-88,h-88);
  ctx.lineWidth=1.5;ctx.strokeRect(x+66,y+66,w-132,h-132);
  ctx.fillStyle=accent;ctx.fillRect(x+w*.27,y+126,w*.46,7);
  ctx.fillRect(x+w*.39,y+h-166,w*.22,4);
  ctx.fillStyle=ink;
}
function drawGeneratedLombadaCover(ctx,l,x,y,w,h,style=0){
  ctx.fillStyle='rgba(26,23,20,.20)';ctx.fillRect(x+16,y+20,w,h);
  ctx.save();ctx.beginPath();ctx.rect(x,y,w,h);ctx.clip();
  const title=trechoTexto(l.titulo||t('untitled')||'',54);
  const author=trechoTexto(l.autor||'',34);
  const dark=style===1;
  const accent=coverAccent(title,author,!dark);
  const paper=dark?'#12100E':'#EFE2C8';
  const ink=dark?'#EAE0CD':'#3C2C22';
  drawEditorialCoverFrame(ctx,x,y,w,h,{paper,ink,accent,dark});
  ctx.textBaseline='alphabetic';
  ctx.textAlign='center';

  const safeW=w-116;
  ctx.fillStyle=ink;
  fitFontSize(ctx,title,s=>`700 italic ${s}px Fraunces, serif`,safeW,Math.min(54,w*.16),30);
  const titleEnd=drawCanvasTextLines(ctx,title,x+w/2,y+h*.42,safeW,58,3,'center');

  if(author){
    ctx.fillStyle=dark?'rgba(234,224,205,.78)':'rgba(60,44,34,.72)';
    fitFontSize(ctx,author,s=>`400 ${s}px 'Space Mono', monospace`,safeW,24,16);
    drawCanvasTextLines(ctx,author,x+w/2,Math.min(titleEnd+44,y+h-155),safeW,30,2,'center');
  }

  ctx.fillStyle=accent;
  ctx.font="600 italic 28px Fraunces, serif";
  ctx.fillText('Lombada',x+w/2,y+h-82);
  ctx.restore();ctx.strokeStyle='rgba(26,23,20,.28)';ctx.lineWidth=2;ctx.strokeRect(x,y,w,h);
}
function drawOriginalShareCover(ctx,im,x,y,w,h){
  ctx.fillStyle='rgba(26,23,20,.20)';ctx.fillRect(x+16,y+20,w,h);
  ctx.save();ctx.beginPath();ctx.rect(x,y,w,h);ctx.clip();
  const p=cardPalette();
  ctx.fillStyle=p.bg2||'#EFE6D6';ctx.fillRect(x,y,w,h);
  drawPaperTexture(ctx,x,y,w,h,p.texture||'rgba(58,50,42,.025)',30);
  const ir=im.width/im.height,wr=w/h;let dw,dh,dx,dy;
  if(ir>wr){dw=w;dh=w/ir;dx=x;dy=y+(h-dh)/2;}
  else{dh=h;dw=h*ir;dx=x+(w-dw)/2;dy=y;}
  ctx.drawImage(im,dx,dy,dw,dh);
  ctx.restore();ctx.strokeStyle='rgba(26,23,20,.25)';ctx.lineWidth=2;ctx.strokeRect(x,y,w,h);
}
function drawShareCover(ctx,l,x,y,w,h,selected){
  return (async()=>{
    if(selected.type==='original' && selected.url){
      const im=await loadShareCardImage(capaProxy(selected.url));
      if(im){ drawOriginalShareCover(ctx,im,x,y,w,h); return; }
    }
    drawGeneratedLombadaCover(ctx,l,x,y,w,h,selected.type==='lombada'?selected.variacao:0);
  })();
}
function drawBookInfo(ctx,l,W,H,cy,ch){
  const p=cardPalette(); let y=cy+ch+118;ctx.textAlign='left';ctx.textBaseline='alphabetic';
  ctx.fillStyle=p.text;ctx.font="500 italic 80px Fraunces, serif";
  y=wrapLeft(ctx,l.titulo||'',110,y,W-220,88,2);
  y+=68;ctx.fillStyle=p.muted;ctx.font="italic 46px Spectral, serif";
  ctx.fillText(l.autor||'',110,y);
  return y;
}
function drawShareStars(ctx,l,y){drawStars(ctx,110,y,l.nota||0,44,20,cardPalette().gold);}
function drawFooter(ctx,l,W,H){
  const p=cardPalette(); const yc=H-160;ctx.strokeStyle=p.rule;ctx.lineWidth=1.5;
  ctx.beginPath();ctx.moveTo(110,yc-46);ctx.lineTo(W-110,yc-46);ctx.stroke();
  ctx.fillStyle=p.muted;ctx.font="400 28px 'Space Mono', monospace";
  const col=[l.tradutor?`${t('translator_abbr')} ${l.tradutor}`:null,l.editora||null,l.ano_edicao||l.ano||null].filter(Boolean).join('   ·   ');
  ctx.fillText(col,110,yc);ctx.fillText('@'+(meuHandle||''),110,yc+44);
  ctx.fillStyle=p.gold;ctx.font="600 italic 40px Fraunces, serif";ctx.fillText('lombada.',110,yc+98);
}


function drawReviewShareCardText(ctx,l,W,H,cy,ch){
  const p=cardPalette(), payload=cardSharePayload();
  let x=96, y=110;
  ctx.textBaseline='alphabetic';ctx.textAlign='left';
  ctx.fillStyle=p.gold;ctx.font="700 28px 'Space Mono', monospace";ctx.fillText('LOMBADA',x,y);
  y+=52;ctx.fillStyle=p.muted;ctx.font="400 24px 'Space Mono', monospace";ctx.fillText(t('review_card_eyebrow'),x,y);
  y+=78;ctx.fillStyle=p.text;ctx.font="500 italic 62px Fraunces, serif";
  y=wrapLeft(ctx,l.titulo||'',x,y,W-450,70,3)+52;
  ctx.fillStyle=p.muted;ctx.font="italic 34px Spectral, serif";wrapLeft(ctx,l.autor||'',x,y,W-450,42,2);
  y+=76;
  if(l.nota){drawStars(ctx,x,y,l.nota||0,28,14,p.gold);y+=84;}
  const meta=[statusLabel(l.status||''),l.data||l.ano_edicao||l.ano_obra||l.ano].filter(Boolean).join(' · ');
  if(meta){ctx.fillStyle=p.muted;ctx.font="400 24px 'Space Mono', monospace";wrapLeft(ctx,meta,x,y,W-190,34,2);y+=62;}
  if(payload.excerpt){ctx.fillStyle=p.text;ctx.font="italic 40px Spectral, serif";wrapLeft(ctx,'“'+payload.excerpt+'”',x,y,W-190,52,4);}
  else if(payload.spoiler&&payload.hasText){ctx.fillStyle=p.muted;ctx.font="italic 40px Spectral, serif";wrapLeft(ctx,t('review_with_spoiler'),x,y,W-190,50,2);}
  ctx.fillStyle=p.muted;ctx.font="400 24px 'Space Mono', monospace";ctx.fillText('@'+(meuHandle||''),x,H-94);
  ctx.fillStyle=p.gold;ctx.font="600 italic 36px Fraunces, serif";ctx.fillText('lombada.',x,H-48);
}

function drawDiaryShareCardText(ctx,l,W,H,cy,ch){
  const p=cardPalette(), payload=cardSharePayload(), e=cardContext.source||{};
  let x=96, y=110;
  ctx.textBaseline='alphabetic';ctx.textAlign='left';
  ctx.fillStyle=p.gold;ctx.font="700 28px 'Space Mono', monospace";ctx.fillText('LOMBADA',x,y);
  y+=52;ctx.fillStyle=p.muted;ctx.font="400 24px 'Space Mono', monospace";ctx.fillText(t('reading_diary'),x,y);
  y+=76;ctx.fillStyle=p.text;ctx.font="500 italic 62px Fraunces, serif";
  y=wrapLeft(ctx,l.titulo||e.titulo||'',x,y,W-420,70,3)+52;
  ctx.fillStyle=p.muted;ctx.font="italic 34px Spectral, serif";wrapLeft(ctx,l.autor||e.autor||'',x,y,W-420,42,2);
  const meta=[payload.progress,dataDiario(e)].filter(Boolean).join(' · ');
  y+=70;if(meta){ctx.fillStyle=p.muted;ctx.font="400 28px 'Space Mono', monospace";wrapLeft(ctx,meta,x,y,W-190,38,2);y+=70;}
  if(payload.excerpt){ctx.fillStyle=p.text;ctx.font="italic 38px Spectral, serif";wrapLeft(ctx,'“'+payload.excerpt+'”',x,y,W-190,50,4);}
  else if(payload.spoiler&&payload.hasText){ctx.fillStyle=p.muted;ctx.font="italic 38px Spectral, serif";wrapLeft(ctx,t('diary_card_spoiler_label'),x,y,W-190,48,2);}
  ctx.fillStyle=p.muted;ctx.font="400 24px 'Space Mono', monospace";ctx.fillText('@'+(meuHandle||''),x,H-94);
  ctx.fillStyle=p.gold;ctx.font="600 italic 36px Fraunces, serif";ctx.fillText('lombada.',x,H-48);
}
function drawShareCardText(ctx,l,W,H,cy,ch){
  const p=cardPalette(), payload=cardSharePayload();
  let y=drawBookInfo(ctx,l,W,H,cy,ch)+86;
  if(payload.progress){ctx.fillStyle=p.muted;ctx.font="400 36px 'Space Mono', monospace";wrapLeft(ctx,payload.progress,110,y,W-220,46,1);y+=62;}
  else {drawShareStars(ctx,l,y);y+=110;}
  if(payload.excerpt){ctx.fillStyle=p.text;ctx.font="italic 44px Spectral, serif";wrapLeft(ctx,'"'+payload.excerpt+'"',110,y,W-220,56,3);}
  else if(payload.spoiler&&payload.hasText){ctx.fillStyle=p.muted;ctx.font="italic 42px Spectral, serif";wrapLeft(ctx,payload.spoilerLabel,110,y,W-220,54,2);}
  drawFooter(ctx,l,W,H);
}
function getSelectedShareCover(l){
  const index=Math.max(0,Math.min(2,Number(cardCoverIndex)||0));
  const originalUrl=index===0?getSafeCoverUrl(l):null;
  return {
    index,
    type:originalUrl?'original':'lombada',
    url:originalUrl||'',
    variacao:index===2?1:0
  };
}
function loadShareCardImage(src){
  return new Promise(resolve=>{
    if(!src){resolve(null);return;}
    const im=new Image();
    im.crossOrigin='anonymous';
    im.onload=()=>resolve(im.naturalWidth>=5?im:null);
    im.onerror=()=>resolve(null);
    im.src=src;
  });
}
async function renderShareCardCanvas(l,options={}){
  const cv=options.canvas || $('#cardCanvas');
  if(!cv || !l)return null;
  configurarCanvasCard(cv);
  const ctx=cv.getContext('2d'),W=cv.width,H=cv.height;
  const selected=options.selectedCover || getSelectedShareCover(l);
  drawShareCardBackground(ctx,l,W,H);
  if(diaryCardActive()){
    const cw=250,ch=380,cx=W-cw-96,cy=120;
    await drawShareCover(ctx,l,cx,cy,cw,ch,selected);
    drawDiaryShareCardText(ctx,l,W,H,cy,ch);
  }else if(reviewCardActive()){
    const cw=280,ch=420,cx=W-cw-96,cy=120;
    await drawShareCover(ctx,l,cx,cy,cw,ch,selected);
    drawReviewShareCardText(ctx,l,W,H,cy,ch);
  }else{
    const cx=110,cy=120,cw=W-220,ch=1120;
    await drawShareCover(ctx,l,cx,cy,cw,ch,selected);
    drawShareCardText(ctx,l,W,H,cy,ch);
  }
  return cv;
}
async function updateShareCardPreview(l){
  const preview=$('#shareCardPreview');
  configurarCanvasCard(preview); configurarCanvasCard($('#cardCanvas'));
  if(!preview || !l)return;
  const selected=getSelectedShareCover(l);
  await renderShareCardCanvas(l,{canvas:preview,selectedCover:selected});
  await renderShareCardCanvas(l,{canvas:$('#cardCanvas'),selectedCover:selected});
}
function drawCard(l){
  updateShareCardPreview(l);
}

function canvasToPngBlob(cv){
  return new Promise(resolve=>cv.toBlob(resolve,'image/png'));
}
async function gerarBlobCard(){
  const cv=await renderShareCardCanvas(cardAtual,{canvas:$('#cardCanvas'),selectedCover:getSelectedShareCover(cardAtual)});
  const blob=cv ? await canvasToPngBlob(cv) : null;
  if(!blob) toast(t('card_generation_error'));
  return blob;
}
async function baixarCard(){
  const blob=await gerarBlobCard();
  if(!blob)return;
  const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download=diaryCardActive()?'lombada-diario.png':'lombada.png';a.click();
  setTimeout(()=>URL.revokeObjectURL(a.href),1500);
  toast(t('card_download_ready'));
}
async function compartilharCard(){
  const blob=await gerarBlobCard();
  if(!blob)return;
  const file=new File([blob],'lombada.png',{type:'image/png'});
  const url=urlPerfilPublico();
  const shareData={title:cardAtual?.titulo||t('profile_share_title'),text:textoCompartilhamentoLeitura(cardAtual)};
  if(url) shareData.url=url;
  if(navigator.canShare && navigator.canShare({files:[file]})){
    try{
      await navigator.share({...shareData,files:[file]});
      if(url) await copiarLink(url,'copy_profile_link_prompt');
      return;
    }catch(e){}
  }
  toast(t('share_image_unavailable'));
  await baixarCard();
  if(url) await copiarLink(url,'copy_profile_link_prompt');
}

/* editar / remover */
function abrirEditar(){
  const l=cardAtual; notaEdit=l.nota||0;
  const p=$('#editPanel');
  p.innerHTML=`
    <h3>${t('edit_title',{title:esc(l.titulo)})}</h3>
    <div class="field"><label class="label">${t('rating')}</label><div class="stars" id="e_stars"></div></div>
    <div class="row">
      <div class="field"><label class="label">${t('status')}</label>
        <select id="e_status">
          <option value="Lido"${l.status==='Lido'?' selected':''}>${t('status_read')}</option>
          <option value="Lendo"${l.status==='Lendo'?' selected':''}>${t('status_reading')}</option>
          <option value="Quero ler"${l.status==='Quero ler'?' selected':''}>${t('status_want')}</option>
        </select></div>
      <div class="field"><label class="label">${t('when')}</label>
        <input type="text" id="e_data" value="${esc(l.data)}" placeholder="${t('date_placeholder')}" /></div>
    </div>
    <div class="field"><label class="label" id="e_relato_label">${t('reading_note')}</label>
      <textarea id="e_relato" maxlength="160">${esc(l.relato)}</textarea></div>
    <div class="visibility-box"><div class="label">${t('visibility')}</div>
      <label class="check-line"><input type="checkbox" id="e_publico" ${l.publico?'checked':''}> <span id="e_publico_label">${t('make_review_public')}</span></label>
      <p class="muted">${t('public_text_hint')}</p>
      <label class="check-line"><input type="checkbox" id="e_spoiler" ${l.spoiler?'checked':''}> <span>${t('contains_spoiler')}</span></label>
    </div>
    <button class="btn-primary" onclick="salvarEdicao()">${t('save_changes')}</button>`;
  p.style.display='';
  montarStars('e_stars',()=>notaEdit,v=>notaEdit=v);
  atualizarCopyRelato('e');
  $('#e_status')?.addEventListener('change',()=>atualizarCopyRelato('e'));
  p.scrollIntoView({behavior:'smooth',block:'center'});
}
async function salvarEdicao(){
  const body={ status:$('#e_status').value, nota:notaEdit||null,
    relato:$('#e_relato').value.trim(), publico:$('#e_publico').checked, spoiler:$('#e_spoiler').checked, data:$('#e_data').value.trim() };
  try{ await fetch('/api/prateleira/'+cardAtual.leitura_id,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}); }
  catch(e){ toast(t('edit_save_error')); return; }
  fecharModalParaNavegacao(); await carregarPrateleira();
}
async function removerLeitura(el=null){
  const botao=el||document.querySelector('.btn-danger[onclick^="removerLeitura"]');
  confirmarEmDoisPassos(botao,`leitura_${cardAtual?.leitura_id||''}`,async()=>{
    try{ await fetch('/api/prateleira/'+cardAtual.leitura_id,{method:'DELETE'}); }
    catch(e){ toast(t('remove_error')); return; }
    fecharModalParaNavegacao(); await carregarPrateleira();
  });
}

/* init */
async function carregarVersaoApp(){
  try{
    const res=await fetch('/api/version',{cache:'no-store'});
    const body=await res.json().catch(()=>({}));
    appVersion=(body.version||'dev').toString();
    debugLog('app_version_loaded',{app:body.app,version_len:appVersion.length});
  }catch(e){ appVersion='dev'; }
}

async function init(){
  const estadoInicial=lerEstadoNavSalvo() || estadoNav('buscar','home');
  history.replaceState(estadoInicial,'');
  tratarMensagemConta();
  const buscaDeepLink=extrairBuscaDeepLink();
  renderChips();
  atualizarSeletorIdioma();
  carregarObrasPopulares();
  await carregarVersaoApp();
  try{
    const me=await (await fetch('/api/eu')).json();
    minhaConta=me||{logado:false,provedor:'anonimo'};
    meuHandle=me.handle||'';
    $('#meuhandle').textContent='@'+meuHandle;
    $('#crumb').classList.add('visible');
  }catch(e){}
  await carregarPrateleira();
  aplicarHistorico(estadoInicial);
  if(buscaDeepLink){ $('#q').value=buscaDeepLink; buscar(); }
}
init();
