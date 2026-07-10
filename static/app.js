const $ = s => document.querySelector(s);
const esc = s => (s||'').toString().replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const capaProxy = u => u ? '/api/capa?url='+encodeURIComponent(u) : '';
const capaSrc = u => u || '';
function handleCoverError(img){
  const original=img?.dataset?.coverOriginal||'';
  const proxied=capaProxy(original);
  if(original && proxied && img.src!==new URL(proxied, location.href).href){
    img.src=proxied;
    return;
  }
  trocarParaCapaArte(img);
}
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
let appConfig={};
let resultadosArr=[], obrasAgrupadas=[], edicoesAtual=[], obraSocial=null, prateleira=[], diarioEntradas=[], cardAtual=null, notaEdit=0, diarioEditId=null, ultimaBuscaQ='';
let editorasHome=[], editorasBusca=[], filtroEditoraBusca='', filtroGeneroBusca='', filtroLiteraturaBusca='', editorasBuscaCarregadas=false;
const GENEROS_BUSCA=['romance','conto','poesia','teatro','ensaio','biografia','autobiografia','história','filosofia','crítica literária','fantasia','ficção científica','terror','policial','infantil','juvenil','crônica','quadrinhos'];
/* lista canônica inicial de literaturas/origens (espelha /api/literaturas) */
const LITERATURAS_BUSCA=[
  {slug:'brasileira',label:'brasileira'},{slug:'russa',label:'russa'},{slug:'francesa',label:'francesa'},
  {slug:'argentina',label:'argentina'},{slug:'japonesa',label:'japonesa'},{slug:'inglesa',label:'inglesa'},
  {slug:'norte-americana',label:'norte-americana'},{slug:'alema',label:'alemã'},{slug:'italiana',label:'italiana'},
  {slug:'portuguesa',label:'portuguesa'},{slug:'espanhola',label:'espanhola'},{slug:'latino-americana',label:'latino-americana'},
];
const ORDENACOES_BUSCA=[
  {valor:'',chave:'order_relevance'},{valor:'popular',chave:'order_popular'},
  {valor:'avaliacao',chave:'order_rating'},{valor:'recentes',chave:'order_recent'},
];
const FILTROS_SOCIAIS_DEF=[
  {chave:'com_capa',grupo:'catalogo',chaveLabel:'filter_with_cover'},
  {chave:'com_isbn',grupo:'catalogo',chaveLabel:'filter_with_isbn'},
  {chave:'idioma_pt',grupo:'catalogo',chaveLabel:'filter_in_portuguese'},
  {chave:'com_criticas',grupo:'comunidade',chaveLabel:'filter_with_reviews'},
  {chave:'lendo_agora',grupo:'comunidade',chaveLabel:'filter_reading_now'},
];
let filtrosSociaisBusca={com_capa:false,com_isbn:false,idioma_pt:false,com_criticas:false,lendo_agora:false};
let ordenacaoBusca='';
let filtroEditoraTermo='';
let filtrosBuscaDirty=false;
let cardCoverIndex=0, cardCoverAutoLowRes=false, cardCoverUserChanged=false;
const CARD_THEME_KEY='lombada_card_theme';
let cardTheme=localStorage.getItem(CARD_THEME_KEY)||'auto', cardIncludeExcerpt=false, cardContext={type:'leitura',source:null};
let filtroEstante='Todos';
let feedItems=[], feedFollowingCount=0, feedTab=localStorage.getItem('lombada_feed_tab')||'discover', discoverReaders=[];
let ultimoLivroSalvo=null;
let cardOpener=null;
let timerDestaqueLivro=null;
let visualizacaoEstante=localStorage.getItem('lombada_view_estante')==='lista'?'lista':'grade';
let visualizacaoBusca=localStorage.getItem('lombada_view_busca')==='grade'?'grade':'lista';
let visualizacaoHomePopulares=localStorage.getItem('lombada_view_home_populares')==='lista'?'lista':'grade';
let paginaBusca=1, porPaginaBusca=20;
let navAtual={aba:'buscar',busca:'home',estanteSub:'shelf'};
let restaurandoHistorico=false;
const LOGIN_HINT_KEY='lombada_login_hint_dismissed';
const NAV_STATE_KEY='lombada_nav_state';
const ONBOARDING_KEY='lombada_onboarding';
const DEBUG = localStorage.getItem('lombada_debug') === '1';
function debugLog(...args){ if(DEBUG) console.log(...args); }
const APP_JS_VERSION = new URL(document.currentScript?.src || location.href, location.href).searchParams.get('v') || 'dev';
let appVersion=APP_JS_VERSION || 'dev';
let activeSwCache='unknown';
let coldStartContentWatcher=null;
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
    if(event.key==='Escape' && $('#filterSheet') && !$('#filterSheet').hidden){ event.preventDefault(); fecharFiltrosBusca(); return; }
    if(event.key==='Escape' && $('#quickActions') && !$('#quickActions').hidden){ event.preventDefault(); fecharAcoesLeitura(); return; }
    if(event.key==='Escape' && posLeituraAberto()){ event.preventDefault(); fecharPosLeitura(); return; }
    if(event.key==='Escape' && $('#activityModal')?.classList.contains('open')){ event.preventDefault(); fecharAtividade(); return; }
    if(event.key==='Escape' && $('#readerModal')?.classList.contains('open')){ event.preventDefault(); fecharLeitor(); return; }
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

// o form do diário nasce no modo página; ao primeiro foco busca o total de
// páginas da edição (catálogo → pergunta única) pra mostrar "de N" e a barra
document.addEventListener('focusin',event=>{
  const form=event.target?.closest?.('[data-diary-form]');
  if(!form) return;
  const tipo=form.querySelector('[data-diary-input="tipo"]')?.value||'pagina';
  if(tipo==='pagina') carregarTotalPaginas(form);
});

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
  renderEditorasHome();
  renderLendoAgora();
  renderPrateleira();
  renderDiario();
  renderOnboarding();
  renderFiltroEditoraBusca();
  if(navAtual.aba==='buscar' && navAtual.busca==='edicoes') renderEdicoes();
  if(navAtual.aba==='buscar' && navAtual.busca==='form' && edicaoSel) escolherEdicao(edicoesAtual.indexOf(edicaoSel));
  if(navAtual.aba==='buscar' && navAtual.busca==='manual') abrirManual();
  if(cardAtual) renderDetalheLivro(cardAtual);
  if(navAtual.aba==='buscar' && navAtual.busca==='edicoes' && obraSocial) renderEdicoes();
  if(hasRenderedContent()) hideColdStartNotice();
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


function hasRenderedContent(){
  return !!(
    document.querySelector('#populares .book, #lendoAgora .book, #editorasHome .publisher-card, #prateleira .book, #diario .diary-entry, #feed .feed-card, #resultados .book, #perfil .pcard')
  );
}
function hideColdStartNotice(){
  const notice=$('#coldStartNotice');
  if(!notice) return;
  notice.hidden=true;
  notice.classList.remove('cold-start-error');
  if(coldStartContentWatcher){ clearInterval(coldStartContentWatcher); coldStartContentWatcher=null; }
}
function showColdStartNotice(){
  if(hasRenderedContent()){ hideColdStartNotice(); return; }
  $('#coldStartNotice')?.removeAttribute('hidden');
  if(!coldStartContentWatcher){
    coldStartContentWatcher=setInterval(()=>{ if(hasRenderedContent()) hideColdStartNotice(); },1000);
  }
}
function showColdStartFailure(message){
  if(hasRenderedContent()){ hideColdStartNotice(); return; }
  const notice=$('#coldStartNotice');
  if(!notice) return;
  notice.classList.add('cold-start-error');
  notice.removeAttribute('hidden');
  notice.innerHTML=`<div><strong>${esc(message||'Não consegui carregar agora.')}</strong><span>Tentar novamente</span></div><button type="button" class="cold-start-reload" onclick="location.reload()">recarregar</button>`;
}
function handleGlobalJsError(label,error){
  console.error(label,error);
  showColdStartFailure('Não consegui carregar agora.');
}
window.addEventListener('error', event => handleGlobalJsError('erro global de JavaScript', event.error || event.message));
window.addEventListener('unhandledrejection', event => handleGlobalJsError('promessa rejeitada sem tratamento', event.reason));
async function carregarDiagnosticoSw(){
  if(!('caches' in window)) return;
  try{
    const keys=await caches.keys();
    activeSwCache=keys.filter(k=>k.startsWith('lombada-shell-')).sort().pop() || 'none';
    if(DEBUG) console.info('lombada_debug',{APP_VERSION:appVersion,APP_JS_VERSION,service_worker_cache:activeSwCache});
  }catch(e){ activeSwCache='unavailable'; debugLog('sw_cache_diag_error',e); }
}

let conviteLoginPendente=false;

function estrelasStr(n){n=n||0;let o='';for(let i=1;i<=5;i++)o+=(i<=n?'★':(i-0.5===n?'⯪':'☆'));return o;}
function hue(t){let h=0;for(let i=0;i<(t||'?').length;i++)h=(h*31+t.charCodeAt(i))%360;return h;}

const LOGIN_HINT_RESURFACE_APOS=5;
function loginHintDispensadoEmLivros(){
  const v=localStorage.getItem(LOGIN_HINT_KEY);
  if(v===null) return null;
  // valor antigo era '1' (dispensa permanente) — trata como dispensado com 0 livros,
  // então o aviso volta assim que a estante crescer (risco de perda também cresce)
  const n=Number(v);
  return Number.isFinite(n)?n:0;
}
function loginHintDispensado(){
  const desde=loginHintDispensadoEmLivros();
  if(desde===null) return false;
  return (prateleira.length-desde) < LOGIN_HINT_RESURFACE_APOS;
}
function deveMostrarConviteLogin(){
  return !minhaConta.logado && prateleira.length > 0 && !loginHintDispensado();
}
function conectarGoogle(){
  try{ sessionStorage.setItem('lombada_after_google_login','perfil'); }catch(e){}
  location.href='/api/auth/google/login';
}
function continuarSemConta(){
  localStorage.setItem(LOGIN_HINT_KEY,String(prateleira.length));
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
  if(conta==='ok'){
    toast(t('account_connected_success'));
    try{
      if(sessionStorage.getItem('lombada_after_google_login')==='perfil'){
        sessionStorage.removeItem('lombada_after_google_login');
        const abaAtual=params.get('aba');
        if(!abaAtual) params.set('aba','perfil');
      }
    }catch(e){}
  }
  if(conta==='erro') toast(t('account_connected_error'));
  if(conta==='state_expirado') toast(t('account_state_expired'));
  if(conta){
    params.delete('conta');
    const qs=params.toString();
    history.replaceState(history.state || estadoNav('buscar','home'), '', location.pathname+(qs?'?'+qs:'')+location.hash);
  }
}

function extrairAbaDeepLink(){
  // páginas server-rendered (/u/{handle}, /editoras…) linkam pro app com
  // ?aba=feed|estante|perfil pra abrir direto na aba certa
  const params=new URLSearchParams(location.search);
  const aba=params.get('aba');
  const filtro=params.get('filtro');
  if(!aba && !filtro) return '';
  params.delete('aba'); params.delete('filtro');
  const qs=params.toString();
  history.replaceState(history.state || estadoNav('buscar','home'), '', location.pathname+(qs?'?'+qs:'')+location.hash);
  if(filtro){
    const mapa={'todos':'Todos','lido':'Lido','lendo':'Lendo','quero-ler':'Quero ler','quero ler':'Quero ler'};
    const f=mapa[filtro.toLowerCase()];
    if(f) filtroEstante=f;
  }
  if(['buscar','feed','estante','perfil','diario'].includes(aba)) return aba;
  return filtro?'estante':'';
}

function extrairObraDeepLink(){
  const params=new URLSearchParams(location.search);
  const wk=params.get('obra'), titulo=params.get('t'), autor=params.get('a');
  if(!wk && !titulo) return null;
  ['obra','t','a'].forEach(k=>params.delete(k));
  const qs=params.toString();
  history.replaceState(history.state || estadoNav('buscar','home'), '', location.pathname+(qs?'?'+qs:'')+location.hash);
  return {work_key:wk||'',titulo:titulo||'',autor:autor||''};
}

function extrairBuscaDeepLink(){
  const params=new URLSearchParams(location.search);
  const q=params.get('q');
  const editora=params.get('editora')||'';
  if(editora) filtroEditoraBusca=editora;
  if(!q) return '';
  params.delete('q'); params.delete('editora');
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
      <img src="${esc(capaSrc(cover))}" alt="" loading="lazy" decoding="async" data-cover-original="${esc(cover)}" data-title="${esc(titulo)}" data-author="${esc(autor)}" onerror="handleCoverError(this)" onload="if(this.naturalWidth<3)trocarParaCapaArte(this)">
      ${extra||''}</div>`;
  }
  return coverFallbackHTML(titulo,autor,extra);
}

/* navegação entre abas */
function estadoNav(aba=navAtual.aba,busca=navAtual.busca,modal=false,estanteSub=navAtual.estanteSub||'shelf'){
  return {lombada:true,aba,busca,modal,estanteSub,q:$('#q')?.value||'',editora:filtroEditoraBusca||'',work_key:escolha?.work_key||'',obraIndexAtual:Number.isInteger(obrasAgrupadas.indexOf(escolha))?obrasAgrupadas.indexOf(escolha):-1};
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
/* toque na aba já ativa: volta ao topo e reseta a pilha da aba, sem refetch
   (padrão de rede social). Usado só pelos botões da barra inferior. */
function tabTap(aba){
  if(aba===navAtual.aba && !modalAberto() && !leitorModalAberto() && !atividadeModalAberta()){
    if(aba==='buscar' && navAtual.busca!=='home'){ $('#q').value=''; limparTodosFiltrosBusca(false); limparBusca(); mostrarBusca('home'); return; }
    if(aba==='estante' && (navAtual.estanteSub||'shelf')!=='shelf'){ irPara('estante',{subaba:'shelf'}); return; }
    window.scrollTo({top:0,behavior:'smooth'});
    return;
  }
  irPara(aba);
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
  if(aba==='buscar' && resetBusca){ $('#q').value=''; limparTodosFiltrosBusca(false); limparBusca(); mostrarBusca('home',{registrar:false}); }
  const recarregarEstante=opcoes.recarregar ?? true;
  if(aba==='feed') carregarFeed();
  if(aba==='estante'){
    aplicarSubabaEstante(estanteSub);
    if(recarregarEstante) carregarPrateleira();
    else renderDiario();
  }
  if(aba==='perfil'){ renderPerfil(); marcarPerfilVisitado(); }
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
  if(atividadeModalAberta() && !proximo.activityOpen) fecharAtividadeDireto();
  if(leitorModalAberto() && !proximo.readerHandle) fecharLeitorDireto();
  if(modalAberto() && !deveReabrirModal) fecharModalDireto();
  restaurandoHistorico=true;
  irPara(proximo.aba,{registrar:false,resetBusca:false,subaba:proximo.estanteSub||'shelf'});
  if(proximo.aba==='buscar'){
    filtroEditoraBusca=proximo.editora||'';
    renderFiltroEditoraBusca();
    if(proximo.q) $('#q').value=proximo.q;
    mostrarBusca(proximo.busca||'home',{registrar:false});
    // já temos esses resultados renderizados em #resultados (só ficaram
    // escondidos ao navegar pra edições/form) — refazer a busca aqui
    // significa skeleton + fetch de novo por nada
    const jaTemResultadoCacheado=normBusca(proximo.q)===normBusca(ultimaBuscaQ) && $('#resultados').dataset.filtros===assinaturaFiltrosBusca() && $('#resultados').innerHTML.trim();
    if(proximo.busca==='resultados' && proximo.q && !jaTemResultadoCacheado) buscar();
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

function normalizarNomeEditora(e){
  return (typeof e==='string' ? e : (e&&(e.editora||e.nome||e.name||e.publisher)) || '').trim();
}
async function carregarEditorasBusca(){
  if(editorasBuscaCarregadas) return editorasBusca;
  editorasBuscaCarregadas=true;
  try{
    const r=await fetch('/api/editoras');
    if(!r.ok) throw new Error('publishers');
    const dados=await r.json();
    editorasBusca=(Array.isArray(dados)?dados:[]).map(normalizarNomeEditora).filter(Boolean);
  }catch(e){ editorasBusca=[]; }
  renderFiltroEditoraBusca();
  return editorasBusca;
}
function opcoesEditorasBusca(){
  return editorasBusca.filter((e,i,a)=>a.findIndex(x=>normBusca(x)===normBusca(e))===i);
}
/* ── filtros da busca: um único bottom sheet editorial (sem select nativo) ── */
function literaturaLabelBusca(slug){
  const lit=LITERATURAS_BUSCA.find(l=>l.slug===slug);
  return lit?lit.label:slug;
}
function ordenacaoLabelBusca(valor){
  const ord=ORDENACOES_BUSCA.find(o=>o.valor===valor);
  return t(ord?ord.chave:'order_relevance');
}
function filtrosBuscaAtivos(){
  const ativos=[];
  if(filtroEditoraBusca) ativos.push({label:t('publisher_filter_active',{publisher:filtroEditoraBusca}),aria:t('clear_publisher_filter'),onclear:'limparFiltroEditoraBusca(true)'});
  if(filtroGeneroBusca) ativos.push({label:t('genre_filter_active',{genre:filtroGeneroBusca}),aria:t('clear_genre_filter'),onclear:'limparFiltroGeneroBusca(true)'});
  if(filtroLiteraturaBusca) ativos.push({label:t('literature_filter_active',{literature:literaturaLabelBusca(filtroLiteraturaBusca)}),aria:t('clear_literature_filter'),onclear:'limparFiltroLiteraturaBusca(true)'});
  FILTROS_SOCIAIS_DEF.forEach(def=>{
    if(filtrosSociaisBusca[def.chave]) ativos.push({label:t(def.chaveLabel),aria:t('clear_filter_generic',{filter:t(def.chaveLabel)}),onclear:`limparFiltroSocialBusca('${def.chave}',true)`});
  });
  if(ordenacaoBusca) ativos.push({label:t('order_filter_active',{order:ordenacaoLabelBusca(ordenacaoBusca)}),aria:t('clear_order_filter'),onclear:'limparOrdenacaoBusca(true)'});
  return ativos;
}
function assinaturaFiltrosBusca(){
  return JSON.stringify([filtroEditoraBusca,filtroGeneroBusca,filtroLiteraturaBusca,ordenacaoBusca,filtrosSociaisBusca]);
}
function filtrosPesquisaAtivos(){
  return !!(filtroEditoraBusca || filtroGeneroBusca || filtroLiteraturaBusca || Object.values(filtrosSociaisBusca).some(Boolean));
}
function renderFiltrosBusca(){
  const ativos=filtrosBuscaAtivos();
  const active=$('#activeSearchFilters');
  if(active){
    const chips=ativos.map(a=>`<span class="search-filter-chip">${esc(a.label)}<button type="button" aria-label="${esc(a.aria)}" onclick="${a.onclear}">×</button></span>`);
    if(ativos.length>1) chips.push(`<button type="button" class="search-filter-clear-all" onclick="limparTodosFiltrosBusca(true)">${esc(t('clear_all_filters'))}</button>`);
    active.innerHTML=chips.join('');
  }
  const toggle=$('#searchFiltersButton');
  if(toggle){
    toggle.classList.toggle('has-active-filter', ativos.length>0);
    toggle.setAttribute('aria-expanded', $('#filterSheet') && !$('#filterSheet').hidden ? 'true' : 'false');
  }
  if($('#filterSheet') && !$('#filterSheet').hidden) renderFilterSheetBody();
}
/* compat: chamadas antigas continuam funcionando */
function renderFiltroEditoraBusca(){ renderFiltrosBusca(); }
function renderFiltroEditoraOpcoes(){
  const options=$('#filterPublisherOptions');
  if(!options) return;
  const termo=normBusca(filtroEditoraTermo);
  const lista=opcoesEditorasBusca().filter(nome=>!termo || normBusca(nome).includes(termo));
  const item=(nome)=>{
    const selecionada=normBusca(nome)===normBusca(filtroEditoraBusca);
    const label=nome || t('all_publishers');
    return `<button type="button" class="publisher-option${selecionada?' selected':''}" role="radio" aria-checked="${selecionada?'true':'false'}" data-publisher="${esc(nome)}" onclick="selecionarFiltroEditora(this.dataset.publisher)"><span class="publisher-option-mark" aria-hidden="true"></span><span>${esc(label)}</span></button>`;
  };
  options.innerHTML=item('') + lista.map(item).join('') + (!lista.length?`<p class="publisher-options-empty">${esc(t('publisher_filter_empty'))}</p>`:'');
}
function renderFilterSheetBody(){
  const body=$('#filterSheetBody');
  if(!body) return;
  const radioChip=(selecionado,onclick,label)=>`<button type="button" class="filter-chip-option${selecionado?' selected':''}" role="radio" aria-checked="${selecionado?'true':'false'}" ${onclick}>${esc(label)}</button>`;
  const generoChips=[radioChip(!filtroGeneroBusca,`onclick="selecionarFiltroGenero('')"`,t('all_genres'))]
    .concat(GENEROS_BUSCA.map(nome=>radioChip(nome===filtroGeneroBusca,`data-genre="${esc(nome)}" onclick="selecionarFiltroGenero(this.dataset.genre)"`,nome)));
  const litChips=[radioChip(!filtroLiteraturaBusca,`onclick="selecionarFiltroLiteratura('')"`,t('all_literatures'))]
    .concat(LITERATURAS_BUSCA.map(l=>radioChip(l.slug===filtroLiteraturaBusca,`onclick="selecionarFiltroLiteratura('${l.slug}')"`,l.label)));
  const socialChips=grupo=>FILTROS_SOCIAIS_DEF.filter(d=>d.grupo===grupo)
    .map(d=>`<button type="button" class="filter-chip-option${filtrosSociaisBusca[d.chave]?' selected':''}" role="switch" aria-checked="${filtrosSociaisBusca[d.chave]?'true':'false'}" onclick="toggleFiltroSocialBusca('${d.chave}')">${esc(t(d.chaveLabel))}</button>`).join('');
  const ordemChips=ORDENACOES_BUSCA.map(o=>radioChip(o.valor===ordenacaoBusca,`onclick="selecionarOrdenacaoBusca('${o.valor}')"`,t(o.chave))).join('');
  body.innerHTML=`
    <div class="filter-group">
      <div class="label">${esc(t('filter_group_publisher'))}</div>
      <label class="publisher-sheet-search">
        <span>${esc(t('search_publisher'))}</span>
        <input id="filterPublisherSearch" type="search" autocomplete="off" placeholder="${esc(t('search_publisher'))}" value="${esc(filtroEditoraTermo)}" oninput="filtroEditoraTermo=this.value;renderFiltroEditoraOpcoes()" />
      </label>
      <div id="filterPublisherOptions" class="publisher-sheet-options filter-publisher-options" role="radiogroup" aria-label="${esc(t('filter_by_publisher'))}"></div>
    </div>
    <div class="filter-group">
      <div class="label">${esc(t('filter_group_genre'))}</div>
      <div class="filter-chip-row" role="radiogroup" aria-label="${esc(t('filter_by_genre'))}">${generoChips.join('')}</div>
    </div>
    <div class="filter-group">
      <div class="label">${esc(t('filter_group_literature'))}</div>
      <div class="filter-chip-row" role="radiogroup" aria-label="${esc(t('filter_group_literature'))}">${litChips.join('')}</div>
    </div>
    <div class="filter-group">
      <div class="label">${esc(t('filter_group_more'))}</div>
      <div class="filter-subgroup"><span class="filter-subgroup-title">${esc(t('filter_group_catalog'))}</span><div class="filter-chip-row">${socialChips('catalogo')}</div></div>
      <div class="filter-subgroup"><span class="filter-subgroup-title">${esc(t('filter_group_community'))}</span><div class="filter-chip-row">${socialChips('comunidade')}</div></div>
      <div class="filter-subgroup"><span class="filter-subgroup-title">${esc(t('filter_group_order'))}</span><div class="filter-chip-row" role="radiogroup" aria-label="${esc(t('filter_group_order'))}">${ordemChips}</div></div>
    </div>`;
  renderFiltroEditoraOpcoes();
  const clear=$('#filterSheetClear');
  if(clear) clear.hidden=!filtrosBuscaAtivos().length;
}
async function toggleFiltrosBusca(){
  const sheet=$('#filterSheet');
  if(!sheet) return;
  if(sheet.hidden) await abrirFiltrosBusca();
  else fecharFiltrosBusca();
}
async function abrirFiltrosBusca(){
  const sheet=$('#filterSheet');
  if(!sheet) return;
  filtrosBuscaDirty=false;
  sheet.hidden=false;
  document.body.classList.add('sheet-open');
  renderFilterSheetBody();
  renderFiltrosBusca();
  await carregarEditorasBusca();
  renderFiltroEditoraOpcoes();
}
function fecharFiltrosBusca(){
  const sheet=$('#filterSheet');
  if(sheet) sheet.hidden=true;
  document.body.classList.remove('sheet-open');
  renderFiltrosBusca();
  $('#searchFiltersButton')?.focus();
  if(filtrosBuscaDirty){ filtrosBuscaDirty=false; refazerBuscaComFiltros(); }
}
function refazerBuscaComFiltros(){
  const q=($('#q')?.value.trim()||'');
  if(q.length>=2 || filtrosPesquisaAtivos()) buscar();
  else if($('#resultados')) $('#resultados').innerHTML=`<div class="empty">${t('empty_search_hint')}</div>`;
}
function aplicarMudancaFiltro(){
  filtrosBuscaDirty=true;
  renderFilterSheetBody();
  renderFiltrosBusca();
}
function selecionarFiltroEditora(nome){
  filtroEditoraBusca=(nome||'').trim();
  aplicarMudancaFiltro();
}
function selecionarFiltroGenero(nome){
  filtroGeneroBusca=(nome||'').trim();
  aplicarMudancaFiltro();
}
function selecionarFiltroLiteratura(slug){
  filtroLiteraturaBusca=(slug||'').trim();
  aplicarMudancaFiltro();
}
function toggleFiltroSocialBusca(chave){
  if(!(chave in filtrosSociaisBusca)) return;
  filtrosSociaisBusca[chave]=!filtrosSociaisBusca[chave];
  aplicarMudancaFiltro();
}
function selecionarOrdenacaoBusca(valor){
  ordenacaoBusca=ORDENACOES_BUSCA.some(o=>o.valor===valor)?valor:'';
  aplicarMudancaFiltro();
}
function limparFiltroEditoraBusca(refazer=false){
  const tinha=!!filtroEditoraBusca;
  filtroEditoraBusca='';
  renderFiltrosBusca();
  if(refazer && tinha) refazerBuscaComFiltros();
}
function limparFiltroGeneroBusca(refazer=false){
  const tinha=!!filtroGeneroBusca;
  filtroGeneroBusca='';
  renderFiltrosBusca();
  if(refazer && tinha) refazerBuscaComFiltros();
}
function limparFiltroLiteraturaBusca(refazer=false){
  const tinha=!!filtroLiteraturaBusca;
  filtroLiteraturaBusca='';
  renderFiltrosBusca();
  if(refazer && tinha) refazerBuscaComFiltros();
}
function limparFiltroSocialBusca(chave,refazer=false){
  const tinha=!!filtrosSociaisBusca[chave];
  filtrosSociaisBusca[chave]=false;
  renderFiltrosBusca();
  if(refazer && tinha) refazerBuscaComFiltros();
}
function limparOrdenacaoBusca(refazer=false){
  const tinha=!!ordenacaoBusca;
  ordenacaoBusca='';
  renderFiltrosBusca();
  if(refazer && tinha) refazerBuscaComFiltros();
}
function limparTodosFiltrosBusca(refazer=true){
  const tinha=filtrosBuscaAtivos().length>0;
  filtroEditoraBusca=''; filtroGeneroBusca=''; filtroLiteraturaBusca='';
  ordenacaoBusca='';
  Object.keys(filtrosSociaisBusca).forEach(k=>filtrosSociaisBusca[k]=false);
  if($('#filterSheet') && !$('#filterSheet').hidden){ filtrosBuscaDirty=filtrosBuscaDirty||tinha; renderFilterSheetBody(); }
  renderFiltrosBusca();
  if(refazer && tinha) refazerBuscaComFiltros();
}

/* editoras na home — caminhos curtos para explorar o catálogo editorial */
function normalizarEditoraHome(e){
  if(typeof e==='string') return {editora:e,nome:e,slug:slugEditora(e),obras_count:0};
  const nome=(e&& (e.editora||e.nome||e.name||e.publisher)) || '';
  return {
    ...e,
    editora:nome,
    slug:(e&&e.slug)||slugEditora(nome),
    obras_count:Number((e&& (e.obras_count ?? e.obrasCount ?? e.count ?? e.total_obras)) || 0)
  };
}
function editoraHomeCountLabel(total){
  if(!total) return '';
  return total===1 ? t('publisher_work_count_one') : t('publisher_work_count_many',{count:total});
}
function renderEditorasHome({loading=false}={}){
  const box=$('#editorasHome');
  if(!box) return;
  if(loading && !editorasHome.length){
    box.innerHTML=`<section class="publisher-strip publisher-strip-loading" aria-busy="true"><div class="section-head"><div class="label">${t('publishers_home_label')}</div></div><div class="publisher-chip-row"><span class="publisher-chip skeleton"></span><span class="publisher-chip skeleton"></span><span class="publisher-chip skeleton short"></span></div></section>`;
    return;
  }
  const lista=(editorasHome||[]).map(normalizarEditoraHome).filter(e=>e.editora&&e.slug).slice(0,10);
  if(!lista.length){
    box.innerHTML=`<section class="publisher-strip publisher-strip-empty"><div class="section-head publisher-strip-head"><div class="label">${t('publishers_home_label')}</div><a class="more" href="/editoras">${t('see_all_publishers')}</a></div><p class="publisher-empty-note">${t('publishers_empty_hint')}</p></section>`;
    return;
  }
  box.innerHTML=`<section class="publisher-strip">
    <div class="section-head publisher-strip-head"><div class="label">${t('publishers_home_label')}</div><a class="more" href="/editoras">${t('see_all_publishers')}</a></div>
    <div class="publisher-chip-row">
      ${lista.map(e=>`<a class="publisher-chip" href="/editora/${encodeURIComponent(e.slug)}" onclick="location.href=this.href; return false;"><span class="publisher-name">${esc(e.editora)}</span>${editoraHomeCountLabel(e.obras_count)?`<span class="publisher-count">${esc(editoraHomeCountLabel(e.obras_count))}</span>`:''}</a>`).join('')}
    </div>
  </section>`;
}
async function carregarEditorasHome(){
  renderEditorasHome({loading:true});
  try{
    const r=await fetch('/api/editoras');
    if(!r.ok) throw new Error('publishers');
    const dados=await r.json();
    editorasHome=Array.isArray(dados)?dados:[];
    if(!editorasBuscaCarregadas){ editorasBusca=editorasHome.map(normalizarNomeEditora).filter(Boolean); renderFiltroEditoraBusca(); }
    renderEditorasHome();
  }catch(e){
    editorasHome=[];
    renderEditorasHome();
  }
}

/* feed da home — obras populares como mini estante */

function viewIconHTML(modo){
  return modo==='lista'
    ? '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 7h14"/><path d="M5 12h14"/><path d="M5 17h14"/></svg>'
    : '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="4" y="4" width="6" height="6"/><rect x="14" y="4" width="6" height="6"/><rect x="4" y="14" width="6" height="6"/><rect x="14" y="14" width="6" height="6"/></svg>';
}
function viewToggleButtonHTML(contexto,modo,ativo,onClick){
  const aria=modo==='lista'?'visualização em lista':'visualização em grade';
  return `<button class="view-toggle-btn ${ativo?'active':''}" type="button" aria-label="${aria}" title="${aria}" onclick="${onClick}">${viewIconHTML(modo)}</button>`;
}

function normalizarObraPopular(o){
  return typeof o==='string' ? {titulo:o,autor:''} : (o||{});
}
function renderObrasPopulares(obras){
  const box=$('#populares');
  if(!box) return;
  const lista=(obras&&obras.length?obras:SUGESTOES).map(normalizarObraPopular).slice(0,8);
  const itens=visualizacaoHomePopulares==='lista'
    ? `<div class="catalog-list home-popular-list">${lista.map((o,i)=>`<div class="catalog-list-item" role="button" tabindex="0" onclick="abrirObraPopular(${i})" aria-label="${esc(o.titulo)}"><div class="catalog-list-title">${esc(o.titulo)}</div>${o.autor?`<div class="catalog-list-author">${esc(o.autor)}</div>`:''}</div>`).join('')}</div>`
    : lista.map((o,i)=>`<div class="book" role="button" tabindex="0" onclick="abrirObraPopular(${i})" aria-label="${esc(o.titulo)}">
    ${coverHTML(o.titulo,o.autor,o.capa_url,'')}
    <div class="t">${esc(o.titulo)}</div>
    ${o.autor?`<div class="a">${esc(o.autor)}</div>`:''}</div>`).join('');
  box.classList.toggle('catalog-list-host',visualizacaoHomePopulares==='lista');
  box.innerHTML=itens;
  box._obrasPopulares=lista;
}
function mudarVisualizacaoHomePopulares(modo){
  visualizacaoHomePopulares=modo==='lista'?'lista':'grade';
  localStorage.setItem('lombada_view_home_populares',visualizacaoHomePopulares);
  renderObrasPopulares($('#populares')?._obrasPopulares||SUGESTOES);
  atualizarToggleHomePopulares();
}
function atualizarToggleHomePopulares(){
  const box=$('#homePopularViewToggle');
  if(!box) return;
  box.innerHTML=viewToggleButtonHTML('home','grade',visualizacaoHomePopulares==='grade',"mudarVisualizacaoHomePopulares('grade')")+viewToggleButtonHTML('home','lista',visualizacaoHomePopulares==='lista',"mudarVisualizacaoHomePopulares('lista')");
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
function lendoAgoraCard(l,idx,compacto=false,mostrarLabel=true){
  const progresso=progressoLeitura(l);
  const previsaoTexto=previsaoTerminoTexto(l);
  const noFim=leituraNoFim(l);
  const acaoPrincipal=noFim
    ?`<button type="button" class="reading-diary-action" aria-label="${t('mark_as_read')}" onclick="event.stopPropagation();concluirLeitura(${idx},this)">${t('mark_as_read')}</button>`
    :`<button type="button" class="reading-diary-action" aria-label="${t('update_progress')}" onclick="event.stopPropagation();abrirDiarioLeitura(${idx})">${t('update_progress')}</button>`;
  return `<div class="reading-now-card ${compacto?'compact':''}" role="button" tabindex="0" onclick="abrirCard(${idx})" aria-label="${esc(l.titulo)}">
    <div class="reading-cover">${coverHTML(l.titulo,l.autor,l.capa_url,'')}</div>
    <div class="reading-copy">
      ${mostrarLabel?`<div class="label">${noFim?t('reading_finished_label'):t('continue_reading')}</div>`:''}
      <h3>${esc(l.titulo)}</h3>
      <p>${esc(l.autor)}</p>
      <div class="reading-spacer"></div>
      <div class="reading-meta">${progresso.texto||t('no_progress_yet')}</div>
      ${progresso.barra!==null?`<div class="reading-progress"><span style="width:${progresso.barra}%"></span></div>`:''}
      ${previsaoTexto?`<div class="reading-eta">${esc(previsaoTexto)}</div>`:''}
    </div>
    <div class="continue-reading-actions">
      ${reviewCardActionHTML(idx,'reading-review-card-action')}
      ${acaoPrincipal}
      ${noFim?`<button type="button" class="review-card-action reading-review-card-action" onclick="event.stopPropagation();abrirDiarioLeitura(${idx})">${t('update_progress')}</button>`:''}
    </div>
  </div>`;
}
function renderLendoAgora(){
  const lendo = prateleira.filter(l=>l.status==='Lendo');
  const box=$('#lendoAgora');
  const home=$('#homeFeed');
  home?.classList.toggle('has-current-reading',lendo.length>0);
  if(!lendo.length){ box.innerHTML=''; return; }
  const l=lendo[0], idx=prateleira.indexOf(l);
  box.innerHTML=`<div class="section-head"><h2 class="h-section">${leituraNoFim(l)?t('reading_finished_label'):t('continue_reading')}</h2><button type="button" class="more home-more-button" onclick="irPara('estante')">${t('see_shelf')}</button></div>${lendoAgoraCard(l,idx,false,false)}`;
}

/* onboarding: primeira visita, primeiros passos — some pra sempre depois de completar as 3 ações */
function estadoOnboarding(){
  try{ return JSON.parse(localStorage.getItem(ONBOARDING_KEY))||{}; }catch(e){ return {}; }
}
function salvarEstadoOnboarding(patch){
  const novo={...estadoOnboarding(),...patch};
  try{ localStorage.setItem(ONBOARDING_KEY,JSON.stringify(novo)); }catch(e){}
  return novo;
}
function marcarPerfilVisitado(){
  if(estadoOnboarding().perfilVisitado) return;
  salvarEstadoOnboarding({perfilVisitado:true});
  renderOnboarding();
}
function focarBuscaHero(){
  const input=$('#q');
  if(!input) return;
  input.focus({preventScroll:true});
  input.scrollIntoView({behavior:'smooth',block:'center'});
}
function onboardingHeroHTML(){
  return `<div class="onboarding-hero">
    <h2>${t('onboarding_hero_title')}</h2>
    <p>${t('onboarding_hero_text')}</p>
    <button class="btn-primary" type="button" onclick="focarBuscaHero()">${t('onboarding_hero_cta')}</button>
    <div class="onboarding-hero-sub">${t('onboarding_hero_cta_sub')}</div>
  </div>
  <div class="onboarding-example">
    <div class="onboarding-example-tag">${t('onboarding_example_tag')}</div>
    <div class="onboarding-example-card">
      <div class="onboarding-example-cover">${coverFallbackHTML(t('onboarding_example_title'),t('onboarding_example_author'))}</div>
      <div class="onboarding-example-copy">
        <h4>${esc(t('onboarding_example_title'))}</h4>
        <div class="a">${esc(t('onboarding_example_author'))}</div>
        <div class="onboarding-example-track"><span></span></div>
        <p>${esc(t('onboarding_example_note'))}</p>
      </div>
    </div>
  </div>`;
}
function onboardingChecklistHTML(passos){
  const {registrou,atualizouProgresso,conheceuPerfil}=passos;
  const doneCount=[registrou,atualizouProgresso,conheceuPerfil].filter(Boolean).length;
  const item=(done,titulo,dica)=>`<div class="onboarding-check-item ${done?'done':''}"><div class="onboarding-check-mark">${done?'✓':''}</div><div class="onboarding-check-copy"><b>${esc(titulo)}</b>${dica?`<span>${esc(dica)}</span>`:''}</div></div>`;
  return `<div class="onboarding-checklist-wrap">
    <div class="onboarding-progress">${t('onboarding_step_progress',{done:doneCount})}</div>
    <div class="onboarding-checklist">
      ${item(registrou,t('onboarding_step1_title'))}
      ${item(atualizouProgresso,t('onboarding_step2_title'),atualizouProgresso?'':t('onboarding_step2_hint'))}
      ${item(conheceuPerfil,t('onboarding_step3_title'),conheceuPerfil?'':t('onboarding_step3_hint'))}
    </div>
  </div>`;
}
function renderOnboarding(){
  const box=$('#onboardingBox');
  if(!box) return;
  const home=$('#homeFeed');
  const est=estadoOnboarding();
  if(est.concluido){
    box.innerHTML='';
    home?.classList.remove('has-onboarding');
    return;
  }
  home?.classList.add('has-onboarding');
  const registrou=prateleira.length>0;
  const atualizouProgresso=diarioEntradas.length>0;
  const conheceuPerfil=!!est.perfilVisitado;
  if(registrou&&atualizouProgresso&&conheceuPerfil){
    salvarEstadoOnboarding({concluido:true});
    box.innerHTML='';
    home?.classList.remove('has-onboarding');
    return;
  }
  box.innerHTML=registrou?onboardingChecklistHTML({registrou,atualizouProgresso,conheceuPerfil}):onboardingHeroHTML();
}

function handleLinkHTML(handle, cls='feed-user') {
  const h=esc(handle||'leitor');
  return `<button type="button" class="${cls}" onclick="abrirPerfilPublico('${h.replace(/'/g,"\'")}')" title="${t('view_profile')}">@${h}</button>`;
}
function avatarHTML(nome, handle, avatarUrl=''){
  const inicial=((nome||handle||'?').trim().charAt(0)||'?').toUpperCase();
  const url=(avatarUrl||'').trim();
  const foto=/^(https:\/\/|\/api\/avatar\/)/i.test(url)?`<img src="${esc(url)}" alt="" loading="lazy" referrerpolicy="no-referrer" onerror="this.remove()">`:'';
  return `<span class="avatar-chip${foto?' has-photo':''}" style="--av-h:${hue(handle||nome||'?')}" aria-hidden="true">${esc(inicial)}${foto}</span>`;
}
/* bloco "pessoa": avatar + nome legível + @handle (e ação opcional), tudo
   clicável pro perfil. Substitui o handle solto em caps nas superfícies
   sociais — pessoas têm nome e rosto, registros têm handle. */
function pessoaHTML(u, acao=''){
  const handle=esc(u?.handle||'leitor');
  const nome=(u?.nome||'').trim();
  const sub=[`@${handle}`, acao].filter(Boolean).join(' · ');
  return `<button type="button" class="person-block" onclick="abrirPerfilPublico('${handle.replace(/'/g,"\'")}')" title="${t('view_profile')}">
    ${avatarHTML(nome,u?.handle,u?.avatar_url)}
    <span class="person-copy"><b>${esc(nome||'@'+handle)}</b><span>${esc(sub)}</span></span>
  </button>`;
}
function followButtonHTML(u, extraClass='') {
  if(!u?.handle || u.is_me) return '';
  // perfis de exemplo não são pessoas reais pra seguir — sem botão pra quem ainda
  // não segue. Mas se por algum motivo já segue (ex.: follow de antes desta
  // regra existir), mantém o botão só pra permitir deixar de seguir.
  if(u.is_demo && !u.is_following) return '';
  return `<button type="button" class="follow-inline ${extraClass} ${u.is_following?'active':''}" onclick="toggleFollowHandle('${esc(u.handle).replace(/'/g,"\'")}')">${u.is_following?t('following'):t('follow')}</button>`;
}
function atualizarFollowLocal(handle, following, counts={}){
  const apply=u=>{ if(u?.handle===handle){ u.is_following=following; if('followers_count' in counts) u.followers_count=counts.followers_count; } };
  feedItems.forEach(it=>apply(it.usuario));
  discoverReaders.forEach(apply);
  (leitorLista||[]).forEach(apply);
  if(leitorAtual?.handle===handle){ leitorAtual.is_following=following; if('followers_count' in counts) leitorAtual.followers_count=counts.followers_count; }
  [obraSocial?.criticas, obraSocial?.destaques].filter(Boolean).forEach(list=>list.forEach(c=>{ if(c?.usuario===handle){ c.is_following=following; if('followers_count' in counts) c.followers_count=counts.followers_count; } }));
}
async function toggleFollowHandle(handle){
  if(!handle) return;
  const current=[...feedItems.map(it=>it.usuario), ...discoverReaders, ...(leitorLista||[]), ...(leitorAtual?[leitorAtual]:[]), ...(obraSocial?.criticas||[]).map(c=>({handle:c.usuario,is_following:c.is_following}))].find(u=>u?.handle===handle);
  const following=!!current?.is_following;
  try{
    const res=await fetch('/api/u/'+encodeURIComponent(handle)+'/follow',{method:following?'DELETE':'POST'});
    if(res.status===401 || res.status===403){ toast(t('follow_login_required')); return; }
    if(!res.ok) throw new Error(await res.text());
    const data=await res.json();
    atualizarFollowLocal(handle, !!data.following, data);
    renderFeed();
    if(leitorModalAberto()) renderLeitor();
    if(obraSocial?.criticas?.some(c=>c.usuario===handle)) renderEdicoes();
  }catch(e){ toast(t('interaction_error')); }
}
let feedLendo=[];
async function denunciarPerfil(handle){
  if(!confirm(t('report_profile_confirm'))) return;
  try{
    const r=await fetch('/api/u/'+encodeURIComponent(handle)+'/report',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({motivo:'profile'})});
    if(r.status===401||r.status===403){ toast(t('follow_login_required')); return; }
    if(!r.ok) throw new Error(await r.text());
    toast(t('report_sent'));
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
  const stories=storiesHTML();
  if(feedTab==='following' && !feedFollowingCount){ box.innerHTML=tabs+intro+`<div class="empty-rich"><h3>${t('empty_following_title')}</h3><p>${t('empty_following_hint')}</p><button class="btn-cta" onclick="mudarFeedTab('discover')">${t('explore_reviews')}</button></div>`; return; }
  if(feedTab==='following' && !feedItems.length){ box.innerHTML=tabs+intro+stories+`<div class="empty-rich"><p>${t('feed_empty_no_activity')}</p><button class="btn-cta" onclick="mudarFeedTab('discover')">${t('discover_readers')}</button></div>`; return; }
  if(feedTab==='discover' && !feedItems.length && !discoverReaders.length){ box.innerHTML=tabs+intro+stories+`<div class="empty-rich"><p>${t('feed_empty_no_activity')}</p></div>`; return; }
  const reviewCards=feedItems.map((it,i)=>{
    const u=it.usuario||{}, livro=it.livro||{}, l=it.leitura||{};
    const edition=[it.edicao?.editora,it.edicao?.tradutor,it.edicao?.ano].filter(Boolean).join(' · ');
    const meta=[livro.autor,edition,dataFeed(it.created_at)].filter(Boolean).join(' · ');
    const spoiler=l.publico&&l.spoiler;
    return `<article class="feed-card">
      <div class="feed-cover">${coverHTML(livro.titulo,livro.autor,livro.capa_url,'')}</div>
      <div class="feed-copy">
        <div class="feed-card-top">${pessoaHTML(u,feedAction(it.tipo,l.status))}${feedTab==='following'?'':followButtonHTML(u)}</div>
        <div class="feed-title-row"><button class="feed-title work-title-link" type="button" onclick="abrirPaginaObraDoFeed(${i})">${esc(livro.titulo)}</button>${l.nota?`<span class="feed-stars">${estrelasStr(l.nota)}</span>`:''}</div>
        <div class="feed-meta">${esc(meta)}</div>
        ${spoiler?`<button class="feed-spoiler" data-feed-spoiler="${i}" onclick="revelarFeedSpoiler(${i})">${t('spoiler_review')} — ${t('tap_to_reveal')}</button>`:(l.relato?`<div class="feed-quote">“${esc(l.relato)}”</div>`:'')}
        ${l.relato?reviewActionsHTML(l):''}
      </div></article>`;
  }).join('');
  const readers=feedTab==='discover'&&discoverReaders.length?`<section class="discover-readers"><div class="label">${t('discover_readers')}</div>${discoverReaders.map(r=>{
    const bio=(r.bio||'').trim();
    const contagem=[bio?`“${bio}”`:'',plural(r.reviews_count||0,'review_one','review_many')].filter(Boolean).join(' · ');
    const badge=(r.is_demo||/^demo-/i.test(r.handle||''))?`<span class="demo-badge">${t('sample_profile')}</span>`:'';
    return `<article><div class="discover-main">${pessoaHTML(r)}<small class="discover-sub">${esc(contagem)}${badge}</small></div>${followButtonHTML(r)}</article>`;
  }).join('')}</section>`:'';
  const title=feedTab==='discover'?`<div class="label community-label">${t('discover_reviews')}</div>`:'';
  box.innerHTML=tabs+intro+stories+readers+title+reviewCards;
}

/* carrossel "lendo agora": círculos com a capa do livro em leitura, estilo stories */
function storiesHTML(){
  if(!feedLendo.length) return '';
  const bolha=it=>{
    const cap=getSafeCoverUrl({capa_url:it.capa_url});
    const d=capaArteDados(it.titulo||'?',it.autor||'');
    const inicial=esc((it.titulo||'?').trim().charAt(0).toUpperCase());
    const fbVisivel=cap?'display:none;':'';
    const img=cap?`<img src="${esc(capaSrc(cap))}" alt="" loading="lazy" decoding="async" data-cover-original="${esc(cap)}" onerror="const p=capaProxy(this.dataset.coverOriginal||''); if(p && this.src!==new URL(p, location.href).href){this.src=p}else{this.style.display='none';this.nextElementSibling.style.display='grid'}">`:'';
    const fb=`<span class="story-fb" style="${fbVisivel}background:${d.papel};color:${d.tinta}">${inicial}</span>`;
    return `<button type="button" class="story" onclick="abrirPerfilPublico('${esc(it.handle).replace(/'/g,"\\'")}')" title="${esc(it.nome||'@'+it.handle)} · ${esc(it.titulo)}">
    <span class="story-ring">${img}${fb}</span>
    <span class="story-name">${esc((it.nome||'').split(' ')[0]||'@'+it.handle)}</span>
  </button>`;
  };
  return `<div class="stories" aria-label="${t('reading_now')}"><div class="label stories-label">${t('reading_now')}</div><div class="stories-strip">${feedLendo.map(bolha).join('')}</div></div>`;
}
async function carregarFeed(){
  const box=$('#feed'); if(box) box.innerHTML=`<div class="empty">${t('loading_activity')}</div>`;
  const lendoPromise=fetch('/api/feed/lendo?scope='+(feedTab==='discover'?'discover':'following')).then(r=>r.ok?r.json():{items:[]}).catch(()=>({items:[]}));
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
  feedLendo=(await lendoPromise).items||[];
  renderFeed();
}
/* ── perfil de leitor dentro do app ──
   clicar numa pessoa abre uma tela sobre o app, sem navegação completa;
   a página pública server-rendered (/u/handle) segue existindo pra links
   externos e compartilhamento. */
let leitorAtual=null, leitorListaTipo=null, leitorLista=[];
function leitorModalAberto(){ return $('#readerModal')?.classList.contains('open'); }
function abrirPerfilPublico(handle){
  if(!handle) return;
  if(meuHandle && handle===meuHandle){ fecharLeitorDireto(); irPara('perfil'); return; }
  abrirLeitor(handle);
}
async function abrirLeitor(handle,opcoes={}){
  const registrar=opcoes.registrar ?? true;
  leitorListaTipo=null; leitorLista=[];
  $('#readerDetail').innerHTML=`<div class="empty">${t('reader_loading')}</div>`;
  $('#readerModal').classList.add('open');
  requestAnimationFrame(()=>$('#readerModal .modal-x')?.focus());
  if(registrar && !restaurandoHistorico){
    const estado={...estadoNav(navAtual.aba,navAtual.busca,false),readerHandle:handle};
    if(history.state && history.state.lombada && history.state.readerHandle) history.replaceState(estado,'');
    else history.pushState(estado,'');
  }
  try{
    const res=await fetch('/api/u/'+encodeURIComponent(handle));
    if(!res.ok) throw new Error(`reader http ${res.status}`);
    leitorAtual=await res.json();
  }catch(e){
    $('#readerDetail').innerHTML=`<div class="empty">${t('reader_load_error')}</div>`;
    return;
  }
  renderLeitor();
}
function fecharLeitorDireto(){
  $('#readerModal')?.classList.remove('open');
  leitorAtual=null; leitorListaTipo=null; leitorLista=[];
}
function fecharLeitor(){
  if(history.state && history.state.lombada && history.state.readerHandle){ history.back(); return; }
  fecharLeitorDireto();
}
async function abrirListaLeitor(tipo){
  if(!leitorAtual?.handle) return;
  leitorListaTipo=tipo==='following'?'following':'followers';
  leitorLista=[];
  renderLeitor();
  try{
    const res=await fetch(`/api/u/${encodeURIComponent(leitorAtual.handle)}/${leitorListaTipo}`);
    if(res.ok) leitorLista=await res.json();
  }catch(e){}
  renderLeitor();
}
function voltarPerfilLeitor(){ leitorListaTipo=null; leitorLista=[]; renderLeitor(); }
async function abrirMinhasConexoes(tipo){ if(!meuHandle) return; await abrirLeitor(meuHandle); abrirListaLeitor(tipo); }
function renderLeitor(){
  const box=$('#readerDetail'); if(!box||!leitorAtual) return;
  const d=leitorAtual;
  if(leitorListaTipo){
    const vazio=leitorListaTipo==='followers'?t('no_followers_yet'):t('no_following_yet');
    const titulo=leitorListaTipo==='followers'?t('followers_count',{count:d.followers_count||0}):t('following_count',{count:d.following_count||0});
    box.innerHTML=`<button class="busca-back" type="button" onclick="voltarPerfilLeitor()">${t('back_to_profile')}</button>
      <div class="label reader-list-title">${esc(titulo)}</div>
      ${leitorLista.length?`<div class="reader-follow-list">${leitorLista.map(u=>`<div class="reader-follow-row">${pessoaHTML(u)}${followButtonHTML(u,'reader-list-follow')}</div>`).join('')}</div>`:`<div class="empty">${vazio}</div>`}`;
    return;
  }
  const stats=d.stats||{};
  const bio=(d.bio||'').trim();
  const lendo=(d.lendo_agora||[]).slice(0,3);
  const ultimas=(d.ultimas_leituras||[]).slice(0,6);
  const criticas=(d.criticas_publicas||[]).slice(0,2);
  const covers=(lst,tipo)=>lst.map((l,i)=>`<button class="reader-shelf-item reader-shelf-link" type="button" onclick="event.stopPropagation(); abrirPaginaObraDoLeitor('${tipo}',${i})" aria-label="${esc('Abrir obra '+(l.titulo||''))}">${coverHTML(l.titulo,l.autor,l.capa_url,'')}<span class="reader-shelf-title">${esc(l.titulo)}</span></button>`).join('');
  box.innerHTML=`
    <div class="reader-head">
      ${avatarHTML(d.nome,d.handle,d.avatar_url).replace('avatar-chip','avatar-chip avatar-lg')}
      <div class="reader-who">
        <h2>${esc((d.nome||'').trim()||'@'+esc(d.handle))}</h2>
        <div class="reader-handle">@${esc(d.handle)}${d.is_demo?` · <span class="demo-badge">${t('sample_profile')}</span>`:''}</div>
        ${bio?`<p class="reader-bio">${esc(bio)}</p>`:''}
      </div>
    </div>
    <div class="reader-actions-row">${followButtonHTML({handle:d.handle,is_following:d.is_following,is_me:d.is_me,is_demo:d.is_demo},'reader-follow-main')}<a class="linklike reader-external" href="/u/${encodeURIComponent(d.handle)}" target="_blank" rel="noopener">${t('open_public_page')}</a></div>
    <div class="reader-counts">
      <button type="button" onclick="abrirListaLeitor('followers')">${t('followers_count',{count:d.followers_count||0})}</button>
      <span>·</span>
      <button type="button" onclick="abrirListaLeitor('following')">${t('following_count',{count:d.following_count||0})}</button>
      <span>·</span>
      <span class="reader-books">${plural(stats.total||0,'book_count_one','book_count_many')}</span>
    </div>
    ${lendo.length?`<div class="label reader-sec">${t('reading_now')}</div><div class="reader-shelf">${covers(lendo,'lendo_agora')}</div>`:''}
    ${ultimas.length?`<div class="label reader-sec">${t('reader_last_readings')}</div><div class="reader-shelf">${covers(ultimas,'ultimas_leituras')}</div>`:''}
    ${criticas.length?`<div class="label reader-sec">${t('reader_public_reviews')}</div>${criticas.map(c=>`<div class="reader-review"><b>${esc(c.titulo)}</b>${c.nota?` <span class="feed-stars">${estrelasStr(c.nota)}</span>`:''}${(c.relato||'').trim()&&!c.spoiler?`<p>“${esc(trechoTexto(c.relato,180))}”</p>`:''}</div>`).join('')}`:''}
    ${d.is_me?'':`<button type="button" class="report-profile-link" onclick="denunciarPerfil('${esc(d.handle).replace(/'/g,"\\'")}')">${t('report_profile')}</button>`}`;
}

/* ── atividade: "fulano te seguiu/curtiu/comentou" ── */
async function atualizarBadgeAtividade(){
  const dot=$('#activityDot'); if(!dot) return;
  try{
    const data=await (await fetch('/api/notificacoes/nao-lidas')).json();
    dot.hidden=!(data?.count>0);
  }catch(e){}
}
function atividadeModalAberta(){ return $('#activityModal')?.classList.contains('open'); }
async function abrirAtividade(opcoes={}){
  const registrar=opcoes.registrar ?? true;
  $('#activityDetail').innerHTML=`<div class="empty">${t('reader_loading')}</div>`;
  $('#activityModal').classList.add('open');
  requestAnimationFrame(()=>$('#activityModal .modal-x')?.focus());
  if(registrar && !restaurandoHistorico){
    const estado={...estadoNav(navAtual.aba,navAtual.busca,false),activityOpen:true};
    if(history.state && history.state.lombada && history.state.activityOpen) history.replaceState(estado,'');
    else history.pushState(estado,'');
  }
  let lista=[];
  try{
    const res=await fetch('/api/notificacoes');
    if(res.status===401){ $('#activityDetail').innerHTML=`<div class="empty">${t('activity_login_required')}</div>`; return; }
    lista=await res.json();
  }catch(e){
    $('#activityDetail').innerHTML=`<div class="empty">${t('reader_load_error')}</div>`;
    return;
  }
  $('#activityDot').hidden=true;
  renderAtividade(lista);
}
function fecharAtividadeDireto(){ $('#activityModal')?.classList.remove('open'); }
function fecharAtividade(){
  if(history.state && history.state.lombada && history.state.activityOpen){ history.back(); return; }
  fecharAtividadeDireto();
}
function itemAtividadeTexto(n){
  const quem=(n.ator?.nome||'').trim()||('@'+(n.ator?.handle||''));
  const titulo=n.obra?.titulo||'';
  if(n.tipo==='follow') return t('activity_follow',{nome:quem});
  if(n.tipo==='like') return titulo?t('activity_like_book',{nome:quem,titulo}):t('activity_like',{nome:quem});
  if(n.tipo==='comment') return titulo?t('activity_comment_book',{nome:quem,titulo}):t('activity_comment',{nome:quem});
  return quem;
}
function renderAtividade(lista){
  const box=$('#activityDetail'); if(!box) return;
  if(!lista.length){ box.innerHTML=`<div class="empty-rich activity-empty"><div class="ei">🔔</div><p>${t('activity_empty')}</p></div>`; return; }
  box.innerHTML=`<div class="activity-list">${lista.map(n=>`<div class="activity-item ${n.lida?'':'unread'}">
    <button type="button" class="activity-item-main" onclick="abrirPerfilPublico('${esc(n.ator?.handle||'').replace(/'/g,"\'")}')">
      ${avatarHTML(n.ator?.nome,n.ator?.handle,n.ator?.avatar_url)}
      <span class="activity-item-copy"><span>${esc(itemAtividadeTexto(n))}</span><small>${esc(dataFeed(n.criado_em))}</small></span>
    </button>
  </div>`).join('')}</div>`;
}


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
function agruparResultadosPorObra(docs,q,opcoes={}){
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
  if(opcoes.manterOrdem) return grupos;   // ordem do servidor (ordenar=/literatura=)
  return grupos.sort((a,b)=>(b.score_obra-a.score_obra)||(b.edicoes_encontradas-a.edicoes_encontradas));
}


function normalizarRespostaBusca(payload){
  if(Array.isArray(payload)) return payload;
  if(payload && Array.isArray(payload.items)) return payload.items;
  if(payload && Array.isArray(payload.resultados)) return payload.resultados;
  return [];
}
function mudarVisualizacaoBusca(modo){
  visualizacaoBusca=modo==='lista'?'lista':'grade';
  localStorage.setItem('lombada_view_busca',visualizacaoBusca);
  paginaBusca=1;
  renderResultadosBusca();
}
function mudarPorPaginaBusca(n){
  porPaginaBusca=[10,20,50].includes(Number(n))?Number(n):20;
  paginaBusca=1;
  renderResultadosBusca();
}
function mudarPaginaBusca(delta){
  const totalPages=Math.max(1,Math.ceil((obrasAgrupadas.length||0)/porPaginaBusca));
  paginaBusca=Math.min(totalPages,Math.max(1,paginaBusca+delta));
  renderResultadosBusca();
}
function controlesBusca(totalPages){
  const total=obrasAgrupadas.length||0;
  return `<div class="search-controls">
    <div class="view-toggle" aria-label="visualização da busca">
      ${viewToggleButtonHTML('busca','grade',visualizacaoBusca==='grade',"mudarVisualizacaoBusca('grade')")}
      ${viewToggleButtonHTML('busca','lista',visualizacaoBusca==='lista',"mudarVisualizacaoBusca('lista')")}
    </div>
    <div class="per-page-select" aria-label="resultados por página"><span>por página</span>${[10,20,50].map(n=>`<button class="${porPaginaBusca===n?'active':''}" type="button" onclick="mudarPorPaginaBusca(${n})">${n}</button>`).join('')}</div>
    <div class="pager" aria-label="paginação da busca">
      <button type="button" ${paginaBusca<=1?'disabled':''} onclick="mudarPaginaBusca(-1)">← anterior</button>
      <span>página ${paginaBusca} de ${totalPages}</span>
      <button type="button" ${paginaBusca>=totalPages?'disabled':''} onclick="mudarPaginaBusca(1)">próximo →</button>
    </div>
    <div class="search-total">${total} ${total===1?'resultado':'resultados'}</div>
  </div>`;
}
function cardResultadoBusca(d,i){
  return `<div class="book work-card" role="button" tabindex="0" onclick="verEdicoes(${i})" aria-label="${esc(d.titulo)}">
    ${coverHTML(d.titulo,d.autor,d.capa_url,d.tem_pt?'<span class="pt">PT</span>':'')}
    <div class="t">${esc(d.titulo)}</div>
    <div class="a">${esc(d.autor)}</div>
    <div class="yr">${plural(contagemEdicoesResultadoBusca(d,1),'edition_found_one','edition_found_many')}</div>
    <div class="e">${t('see_editions')}</div></div>`;
}
function linhaResultadoBusca(d,i){
  return `<div class="catalog-list-item search-result-row" role="button" tabindex="0" onclick="verEdicoes(${i})" aria-label="${esc(d.titulo)}"><div class="search-result-body">
    <div class="catalog-list-title search-result-title">${esc(d.titulo)}</div><div class="catalog-list-author search-result-author">${esc(d.autor)}</div>
    <div class="catalog-list-meta search-result-meta">${plural(contagemEdicoesResultadoBusca(d,1),'edition_found_one','edition_found_many')} · ${t('see_editions')}</div>
  </div></div>`;
}
function renderResultadosBusca(extraHTML=''){
  const totalPages=Math.max(1,Math.ceil((obrasAgrupadas.length||0)/porPaginaBusca));
  paginaBusca=Math.min(Math.max(1,paginaBusca),totalPages);
  const inicio=(paginaBusca-1)*porPaginaBusca;
  const itens=obrasAgrupadas.slice(inicio,inicio+porPaginaBusca);
  const lista=visualizacaoBusca==='lista'
    ? `<div class="catalog-list search-result-list">${itens.map((d,idx)=>linhaResultadoBusca(d,inicio+idx)).join('')}</div>`
    : `<div class="wall">${itens.map((d,idx)=>cardResultadoBusca(d,inicio+idx)).join('')}</div>`;
  const melhorScore=resultadosArr.length?Math.max(...resultadosArr.map(d=>scoreResultadoBusca(d,ultimaBuscaQ))):100;
  const precisaDestaque=melhorScore<40;
  $('#resultados').innerHTML=`<div class="section-head"><h2 class="h-section">${t('works_found')}</h2></div>`+extraHTML+controlesBusca(totalPages)+lista+controlesBusca(totalPages)+manualCtaHTML(precisaDestaque);
}

/* busca */
function buscarTermo(t){$('#q').value=t;buscar();}
function renderBuscaSkeleton(mensagem=''){
  const item=()=>`<div class="book busca-skeleton-item" aria-hidden="true">
    <div class="cover busca-skeleton-cover"></div>
    <div class="busca-skeleton-line title"></div>
    <div class="busca-skeleton-line author"></div>
    <div class="busca-skeleton-line meta-line"></div>
  </div>`;
  const aviso=mensagem?`<div class="empty search-filter-status">${esc(mensagem)}</div>`:'';
  $('#resultados').innerHTML=`${aviso}<div class="section-head"><h2 class="h-section">${t('searching')}</h2></div><div class="wall busca-skeleton">${Array.from({length:4},item).join('')}</div>`;
}
function manualCtaHTML(destaque=false){
  return destaque
    ? `<div class="manual-cta prominent"><p>${t('manual_prominent_text')}</p><button class="link-manual" type="button" data-work-action="manual-edition">${t('manual_prominent_button')}</button></div>`
    : `<div class="manual-cta"><p>${t('manual_cta_text')}</p><button class="link-manual" type="button" data-work-action="manual-edition">${t('manual_cta_button')}</button></div>`;
}
async function buscar(event){
  if(event?.preventDefault) event.preventDefault();
  const q=$('#q').value.trim();
  const temFiltroPesquisa=filtrosPesquisaAtivos();
  if(q.length<2 && !temFiltroPesquisa){
    $('#resultados').innerHTML=`<div class="empty">${t('empty_search_hint')}</div>`;
    mostrarBusca('resultados');
    return;
  }
  if(q.length>=2) lembrarBuscaRecente(q);
  const suggestBox=$('#searchSuggest'); if(suggestBox) suggestBox.hidden=true;
  $('#edicoes').innerHTML=''; $('#form').innerHTML='';
  renderBuscaSkeleton(q.length<2 && temFiltroPesquisa ? t('searching_with_filters') : '');
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
    const params=new URLSearchParams();
    if(q.length>=2) params.set('q', q);
    if(filtroEditoraBusca) params.set('editora', filtroEditoraBusca);
    if(filtroGeneroBusca) params.set('genero', filtroGeneroBusca);
    if(filtroLiteraturaBusca) params.set('literatura', filtroLiteraturaBusca);
    if(ordenacaoBusca) params.set('ordenar', ordenacaoBusca);
    if(filtrosSociaisBusca.com_capa) params.set('com_capa','true');
    if(filtrosSociaisBusca.com_isbn) params.set('com_isbn','true');
    if(filtrosSociaisBusca.com_criticas) params.set('com_criticas','true');
    if(filtrosSociaisBusca.lendo_agora) params.set('lendo_agora','true');
    if(filtrosSociaisBusca.idioma_pt) params.set('idioma','pt');
    const res=await fetch('/api/buscar?'+params.toString());
    if(!res.ok) throw new Error(`search http ${res.status}`);
    try{ docs=normalizarRespostaBusca(await res.json()); }catch(err){ throw new Error('search invalid json'); }
  }
  catch(err){
    console.warn('search failed', {query_len:q.length}, err);
    $('#resultados').innerHTML=`<div class="empty">${t('search_load_error')}</div>${manualCtaHTML(true)}`;
    return;
  }
  finally{ clearTimeout(avisoBusca); }
  ultimaBuscaQ=q;
  $('#resultados').dataset.editora=filtroEditoraBusca||'';
  $('#resultados').dataset.genero=filtroGeneroBusca||'';
  $('#resultados').dataset.filtros=assinaturaFiltrosBusca();
  // com ordenação/literatura ativa o servidor já decidiu a ordem — não re-ranquear no cliente
  const manterOrdemServidor=!!(ordenacaoBusca||filtroLiteraturaBusca);
  docs=normalizarRespostaBusca(docs);
  resultadosArr=manterOrdemServidor?(docs||[]):ordenarResultadosBusca(docs||[], q);
  obrasAgrupadas=agruparResultadosPorObra(resultadosArr, q, {manterOrdem:manterOrdemServidor});
  if(!obrasAgrupadas.length){
    const temFiltro=filtrosBuscaAtivos().length>0;
    const msg=temFiltro ? `<div class="empty-rich search-filter-empty"><p>${t('no_results_with_filters')}</p><button class="link-manual" type="button" onclick="limparTodosFiltrosBusca(true)">${t('clear_filters')}</button></div>` : '';
    $('#resultados').innerHTML=msg ? msg+manualCtaHTML(false) : manualCtaHTML(true);
    return;
  }
  paginaBusca=1;
  const avisoLiteratura=(filtroLiteraturaBusca && !resultadosArr.some(d=>d._literatura_match))
    ? `<div class="empty literatura-fallback-note">${t('literature_no_metadata_note',{literature:esc(literaturaLabelBusca(filtroLiteraturaBusca))})}</div>` : '';
  renderResultadosBusca(avisoLiteratura);
}

/* edições */
async function carregarSocialObra(){
  obraSocial={estatisticas:{leituras:0,criticas:0,media:null},edicoes:[],criticas:[],destaques:[],destaques_edicao:{},minha_leitura:null};
  if(!escolha) return obraSocial;
  const params=new URLSearchParams({work_key:escolha.work_key||'',titulo:escolha.titulo||'',autor:escolha.autor||''});
  try{ obraSocial=await (await fetch('/api/obra/social?'+params.toString())).json(); }catch(e){}
  return obraSocial;
}
/* link compartilhável da obra: /?obra=<work_key>&t=<título>&a=<autor>
   (t/a servem de fallback pra obras sem work_key e alimentam o cabeçalho) */
function linkDaObra(o=escolha){
  if(!o) return '';
  const p=new URLSearchParams();
  if(o.work_key) p.set('obra',o.work_key);
  if(o.titulo) p.set('t',o.titulo);
  if(o.autor) p.set('a',o.autor);
  if(!p.get('obra')&&!p.get('t')) return '';
  return location.origin+'/?'+p.toString();
}
async function copiarLinkObra(){
  const url=linkDaObra();
  if(!url){ toast(t('link_copy_failed')); return; }
  await copiarLink(url);
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
function obraDeLeituraPublica(l){
  if(!l) return null;
  const edicao={
    edicao_id:l.edicao_id, titulo_edicao:l.titulo, editora:l.editora, tradutor:l.tradutor,
    ano:l.ano_edicao||l.ano, isbn:l.isbn, idioma:l.idioma, capa_url:l.capa_url
  };
  return {
    work_key:l.work_key||'', titulo:l.titulo||'', autor:l.autor||'', ano:l.ano_obra||l.ano,
    idioma_original:l.idioma_original, capa_url:l.capa_url, edicoes:[edicao].filter(e=>Object.values(e).some(Boolean))
  };
}
async function abrirPaginaObraDoLeitor(tipo,index){
  const chave=tipo==='lendo_agora'?'lendo_agora':'ultimas_leituras';
  const item=(leitorAtual?.[chave]||[])[index];
  const obra=obraDeLeituraPublica(item);
  if(!obra) return;
  fecharLeitorDireto();
  if(history.state && history.state.lombada && history.state.readerHandle){
    history.replaceState(estadoNav(navAtual.aba,navAtual.busca,false),'');
  }
  irPara('buscar',{resetBusca:false});
  await abrirPaginaObra(obra);
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
    // Open Library fora do ar (ou obra só do catálogo local): se o social
    // conhece a obra, renderiza a página com as edições locais mesmo assim
    await carregarSocialObra();
    if(obraSocial?.edicoes?.length){
      edicoesAtual=ordenarEdicoesObra(mesclarEdicoesLocais([]));
      renderEdicoes();
      return;
    }
    $('#edicoes').innerHTML=`<div class="busca-back" role="button" tabindex="0" onclick="mostrarBusca('resultados')">${t('back_results')}</div><div class="empty">${t('editions_load_error_now')}</div><div class="manual-cta prominent"><button class="link-manual" onclick="verEdicoes()">${t('try_again')}</button><button class="link-manual" type="button" data-work-action="manual-edition">${t('register_edition_manually')}</button></div>`;
    return;
  }
  await carregarSocialObra(); edicoesAtual=ordenarEdicoesObra(mesclarEdicoesLocais(eds||[])); renderEdicoes();
}
function fmtMedia(n){return n?Number(n).toLocaleString(getLocale(),{minimumFractionDigits:1,maximumFractionDigits:1})+' ★':t('no_average');}
function countLabel(n,oneKey,manyKey){ return plural(Number(n)||0,oneKey,manyKey); }
function editionSocialCountsHTML(social){
  const leituras=social?.leituras||0, tem=social?.tem||0, querem=social?.querem||0;
  const posse=(tem||querem)
    ? `<span>${t('readers_have_this_edition',{count:tem})}</span><span>${t('readers_want_this_edition',{count:querem})}</span>`
    : `<span class="edition-stats-muted">${t('no_readers_have_or_want_edition')}</span>`;
  return `<div class="edition-stats"><span>${countLabel(leituras,'reading_one','reading_many')}</span><span>${social?.media?fmtMedia(social.media):t('no_average_yet')}</span>${posse}</div>`;
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
  const comentarios=Number(c.comments_count||0);
  // curtir/guardar são ações leves e frequentes; denunciar é rara e negativa —
  // vai atrás do ⋯ pra action row não parecer formulário
  return `<div class="review-actions">
    <button type="button" class="ra-like ${liked?'active':''}" aria-pressed="${liked}" onclick="acaoReview(${c.leitura_id},'${liked?'unlike':'like'}')">${liked?'♥':'♡'}${likes?` ${likes}`:''}</button>
    <button type="button" class="ra-comment ${comentariosAbertos[c.leitura_id]?'active':''}" aria-expanded="${!!comentariosAbertos[c.leitura_id]}" onclick="alternarComentarios(${c.leitura_id})">💬${comentarios?` ${comentarios}`:''}</button>
    <button type="button" class="ra-save ${saved?'active':''}" aria-pressed="${saved}" onclick="acaoReview(${c.leitura_id},'${saved?'unsave':'save'}')">${saved?t('saved_review'):t('save_review')}</button>
    <span class="ra-more-wrap"><button type="button" class="ra-more" aria-label="${t('more_options')}" aria-haspopup="true" aria-expanded="false" onclick="alternarMenuReview(this,event)">⋯</button>
      <span class="ra-menu" hidden><button type="button" onclick="acaoReview(${c.leitura_id},'report')">${c.reported_by_me?t('reported_review'):t('report')}</button></span>
    </span>
  </div>${comentariosPainelHTML(c.leitura_id)}`;
}

/* ── comentários em críticas ── */
let comentariosAbertos={}; // leituraId -> {carregando, lista}
function rerenderCardsComReview(){
  renderFeed();
  if(obraSocial?.criticas?.length || obraSocial?.destaques?.length) renderEdicoes();
}
async function alternarComentarios(leituraId){
  if(!leituraId) return;
  if(comentariosAbertos[leituraId]){ delete comentariosAbertos[leituraId]; rerenderCardsComReview(); return; }
  comentariosAbertos[leituraId]={carregando:true,lista:[]};
  rerenderCardsComReview();
  try{
    const res=await fetch(`/api/reviews/${leituraId}/comments`);
    const lista=res.ok?await res.json():[];
    comentariosAbertos[leituraId]={carregando:false,lista};
  }catch(e){
    comentariosAbertos[leituraId]={carregando:false,lista:[]};
  }
  rerenderCardsComReview();
}
async function enviarComentario(event,leituraId){
  event.preventDefault();
  const form=event.target;
  const input=form.querySelector('input');
  const texto=(input?.value||'').trim();
  if(!texto) return false;
  const btn=form.querySelector('button[type=submit]');
  setButtonBusy(btn,t('sending'));
  try{
    const res=await fetch(`/api/reviews/${leituraId}/comments`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({texto})});
    if(res.status===401){ toast(t('login_to_interact')); return false; }
    if(!res.ok) throw new Error(await res.text());
    const novo=await res.json();
    const st=comentariosAbertos[leituraId]||{carregando:false,lista:[]};
    st.lista=[...(st.lista||[]),novo];
    comentariosAbertos[leituraId]=st;
    atualizarReviewLocal(leituraId,{comments_count:st.lista.length});
    rerenderCardsComReview();
  }catch(e){ toast(t('interaction_error')||'não foi possível atualizar agora.'); }
  finally{ clearButtonBusy(btn); }
  return false;
}
async function removerComentario(leituraId,commentId){
  try{
    const res=await fetch(`/api/comments/${commentId}`,{method:'DELETE'});
    if(!res.ok) throw new Error(await res.text());
    const st=comentariosAbertos[leituraId];
    if(st){ st.lista=(st.lista||[]).filter(cm=>cm.id!==commentId); atualizarReviewLocal(leituraId,{comments_count:st.lista.length}); }
    rerenderCardsComReview();
  }catch(e){ toast(t('interaction_error')||'não foi possível atualizar agora.'); }
}
function comentariosPainelHTML(leituraId){
  const st=comentariosAbertos[leituraId];
  if(!st) return '';
  if(st.carregando) return `<div class="review-comments"><div class="empty">${t('reader_loading')}</div></div>`;
  const lista=st.lista||[];
  const itens=lista.length?lista.map(cm=>`<div class="comment-item">
      ${avatarHTML(cm.usuario?.nome,cm.usuario?.handle,cm.usuario?.avatar_url)}
      <div class="comment-copy"><div class="comment-head"><b>${esc(cm.usuario?.nome||('@'+(cm.usuario?.handle||'')))}</b><small>${esc(dataFeed(cm.criado_em))}</small></div><p>${esc(cm.texto)}</p></div>
      ${cm.is_me?`<button type="button" class="comment-del" aria-label="${t('delete_comment')}" onclick="removerComentario(${leituraId},${cm.id})">×</button>`:''}
    </div>`).join(''):`<p class="comment-empty">${t('no_comments_yet')}</p>`;
  const composer=minhaConta?.logado
    ?`<form class="comment-form" onsubmit="return enviarComentario(event,${leituraId})"><input type="text" maxlength="500" placeholder="${t('write_a_comment')}" /><button type="submit">${t('send')}</button></form>`
    :`<p class="comment-login-hint">${t('login_to_comment')}</p>`;
  return `<div class="review-comments">${itens}${composer}</div>`;
}
function fecharMenusReview(exceto=null){
  document.querySelectorAll('.ra-menu:not([hidden])').forEach(m=>{
    if(m===exceto) return;
    m.hidden=true;
    m.closest('.ra-more-wrap')?.querySelector('.ra-more')?.setAttribute('aria-expanded','false');
  });
}
function alternarMenuReview(btn,event){
  event?.stopPropagation?.();
  const menu=btn?.closest('.ra-more-wrap')?.querySelector('.ra-menu');
  if(!menu) return;
  const abrir=menu.hidden;
  fecharMenusReview();
  menu.hidden=!abrir;
  btn.setAttribute('aria-expanded',abrir?'true':'false');
}
document.addEventListener('click',e=>{ if(!e.target.closest?.('.ra-more-wrap')) fecharMenusReview(); });

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
  const card=c=>`<article class="review-card ${c.spoiler?'has-spoiler':''}"><div class="review-top">${pessoaHTML({handle:c.usuario,nome:c.nome})}<span>${c.nota?fmtMedia(c.nota):t('no_rating')}</span></div>${corpo(c)}${followButtonHTML({handle:c.usuario,is_following:c.is_following,is_me:c.is_me,is_demo:c.is_demo},'review-follow')}<div class="review-meta">${edicaoMeta(c)}</div>${reviewActionsHTML(c)}</article>`;
  // não repete em "recentes" as críticas já mostradas em destaque
  const idsDestaque=new Set(destaques.map(c=>c.leitura_id).filter(Boolean));
  const recentesSemDestaque=recentes.filter(c=>!idsDestaque.has(c.leitura_id));
  const blocos=[];
  if(destaques.length) blocos.push([t('featured'),destaques,' featured']);
  if(recentesSemDestaque.length) blocos.push([t('recent'),recentesSemDestaque,'']);
  const listas=blocos.map(([rotulo,lista,cls])=>`${blocos.length>1?`<div class="label community-label">${rotulo}</div>`:''}<div class="reviews-list${cls}">${lista.map(card).join('')}</div>`).join('');
  return `<section class="community-section work-section"><div class="section-head"><h2 class="h-section">${t('community_reviews')}</h2></div>${listas}</section>`;
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
function seguidosLeramHTML(){
  const lista=obraSocial?.seguidos_leram||[];
  if(!lista.length) return '';
  const nome=u=>(u.nome||'').trim()||('@'+u.handle);
  let texto;
  if(lista.length===1) texto=t('friends_read_one',{nome:nome(lista[0])});
  else if(lista.length===2) texto=t('friends_read_two',{a:nome(lista[0]),b:nome(lista[1])});
  else texto=t('friends_read_many',{nome:nome(lista[0]),count:lista.length-1});
  const avatares=lista.slice(0,4).map(u=>`<button type="button" class="friends-read-av" onclick="abrirPerfilPublico('${esc(u.handle).replace(/'/g,"\'")}')" title="@${esc(u.handle)}">${avatarHTML(u.nome,u.handle,u.avatar_url)}</button>`).join('');
  return `<section class="friends-read work-section"><span class="friends-read-avs">${avatares}</span><span class="friends-read-text">${esc(texto)}</span></section>`;
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
      ${escolha.autor?`<div class="a">${esc(escolha.autor)}</div>`:''}
      ${anoIdioma?`<div class="y">${anoIdioma}</div>`:''}
      <div class="community-score"><strong>${media}</strong><span>${plural(leituras,'reading_one','reading_many')} · ${plural(criticas,'review_one','review_many')}</span></div>
      <div class="work-actions">${acaoPrincipal}<button class="secondary" type="button" data-work-action="see-editions">${t('see_editions')}</button></div>
      <button class="linklike work-share-link" type="button" onclick="copiarLinkObra()">${t('copy_work_link')}</button>${edicoesAtual.length?'':`<button class="link-tertiary" type="button" data-work-action="manual-edition">${t('register_edition_manually')}</button>`}
    </div></div>`;
  const descricao=(escolha.descricao||escolha.description||obraSocial?.obra?.descricao||'').trim();
  const descLonga=descricao.length>320;
  const tituloAutorBusca=[escolha.titulo,escolha.autor].filter(Boolean).join(' ');
  const linkSaibaMais=tituloAutorBusca?`<a class="linklike about-work-external" href="https://www.google.com/search?q=${encodeURIComponent('livro '+tituloAutorBusca+' sinopse')}" target="_blank" rel="noopener">${t('learn_more_external')}</a>`:'';
  const sobreObra=`<section class="about-work work-section${descLonga?' clamp':''}"><div class="label">${t('about_work')}</div>${descricao?`<p class="about-work-text">${esc(descricao)}</p><div class="about-work-actions">${descLonga?`<button class="linklike about-work-toggle" type="button" onclick="toggleAboutWork(this)">${t('see_more')}</button>`:''}${linkSaibaMais}</div>`:`<p class="muted">${t('no_work_description')}</p><div class="about-work-actions">${linkSaibaMais}</div>`}</section>`;
  const poucosDados=(!edicoesAtual.length&&!leituras&&!criticas)||(!escolha.capa_url&&!escolha.ano&&!escolha.idioma_original&&!criticas);
  const estadoPoucosDados=poucosDados?`<section class="work-section work-low-data"><p>${t('work_low_data')}</p><div class="work-actions"><button class="primary" type="button" data-work-action="register-reading">${t('register_reading')}</button><button class="secondary" type="button" data-work-action="manual-edition">${t('register_edition_manually')}</button></div></section>`:'';
  const minhas='';
  const destaquesEd=obraSocial?.destaques_edicao||{};
  const maisLida=destaquesEd.mais_lida||(obraSocial?.edicoes||[]).slice().sort((a,b)=>(b.leituras||0)-(a.leituras||0))[0];
  const paresDestaque=[
    destaquesEd.mais_lida&&[t('most_read_edition'),destaquesEd.mais_lida.edicao?.editora||t('publisher_missing')],
    destaquesEd.mais_desejada&&[t('most_wanted_edition'),destaquesEd.mais_desejada.edicao?.editora||t('publisher_missing')],
    destaquesEd.mais_possuida&&[t('most_owned_edition'),destaquesEd.mais_possuida.edicao?.editora||t('publisher_missing')],
    destaquesEd.traducao_mais_lida&&[t('most_read_translation'),destaquesEd.traducao_mais_lida],
    destaquesEd.editora_mais_lida&&[t('most_read_publisher'),destaquesEd.editora_mais_lida]
  ].filter(Boolean);
  // com 1 edição (ou destaques todos iguais) a seção só repete a mesma editora — vira ruído
  const destaquesUteis=edicoesAtual.length>1&&new Set(paresDestaque.map(p=>normalizarTextoBase(p[1]))).size>1;
  const destaqueObraHTML=destaquesUteis?paresDestaque.map(([rotulo,valor])=>`${rotulo}: ${esc(valor)}`):[];
  const temEstatisticas=!!(leituras||st.media||lendo||querem);
  const estatisticasHTML=temEstatisticas
    ? `<section class="community-summary work-stats"><div><span>${leituras}</span><small>${t(leituras===1?'reading_on_lombada_one':'readings_on_lombada')}</small></div><div><span>${st.media?fmtMedia(st.media):'—'}</span><small>${t('average_rating')}</small></div><div><span>${lendo}</span><small>${t('people_reading')}</small></div><div><span>${querem}</span><small>${t(querem===1?'person_wants_to_read':'people_want_to_read')}</small></div></section>`
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
      <div class="edition-body"><div class="pub">${e.editora?linkEditoraHTML(e.editora):esc(t('publisher_missing'))}${pt?' · PT/BR':''}</div><div class="te">${esc(e.titulo_edicao||escolha.titulo)}</div><div class="tr">${tr}</div><div class="ln meta edition-meta-pills">${[e.ano,e.idioma,e.pais,e.isbn&&`${t('isbn')} ${e.isbn}`].filter(Boolean).map(x=>`<span>${esc(x)}</span>`).join('')}</div>${stats}${relation}<div class="edition-actions"><button class="edition-action" type="button" data-work-action="choose-edition" data-edition-index="${j}">${t('register_this_edition')}</button>${botaoAmazon(e.isbn)}</div></div></li>`;
  }).join('');
  $('#edicoes').innerHTML=back+`<main class="work-page">${cab}${seguidosLeramHTML()}${estatisticasHTML}${estadoPoucosDados}${sobreObra}${destaqueObraHTML.length?`<section class="work-edition-highlights work-section"><div class="label">${t('edition_social')}</div>${destaqueObraHTML.map(x=>`<p>${x}</p>`).join('')}</section>`:''}<section class="work-section"><div class="section-head"><h2 class="h-section">${t('editions')}</h2></div>${cards?`<ul class="editions work-editions">${cards}</ul><button class="link-tertiary" type="button" data-work-action="manual-edition">${t('register_edition_manually')}</button>`:`<div class="empty-rich work-empty"><p>${t('no_editions_register_manual')}</p><button class="btn-cta" type="button" data-work-action="manual-edition">${t('register_edition_manually')}</button></div>`}</section>${criticasHTML()}</main>`;
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
        ${botaoAmazon(edicaoSel.isbn)}
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
    paginas:Number(edicaoSel.paginas)>0?Number(edicaoSel.paginas):null,
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
        <div class="row"><div class="field"><label class="label">${t('edition_pages_label')}</label><input type="number" inputmode="numeric" min="1" step="1" id="m_paginas" /></div><div class="field"></div></div>
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
    capa_url:$('#m_capa_url').value.trim(), paginas:parseInt($('#m_paginas').value,10)||null,
    status:$('#m_status').value, nota:notaSel||null, relato:$('#m_relato').value.trim(), data:$('#m_data').value.trim()
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
  return `<section class="shelf-now"><div class="label">${t('reading_now')}</div>${lendoAgoraCard(l,prateleira.indexOf(l),true,false)}</section>`;
}
function renderPrateleira(){
  if(!prateleira.length){
    $('#prateleira').innerHTML=`<div class="empty-rich"><div class="ei">📚</div>
      <h3>${t('empty_shelf_title')}</h3><p>${t('empty_shelf_hint')}</p>
      <div class="empty-actions"><button class="btn-cta" onclick="irPara('buscar')">${t('search_button')}</button>${!minhaConta.logado?`<button class="btn-secondary" onclick="conectarGoogle()">${t('profile_login_cta_button')}</button>`:''}</div></div>`;
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
  renderOnboarding();
}

/* diário — linha do tempo */
function progressoDiario(e){
  const partes=[];
  if(e.pagina!==null&&e.pagina!==undefined) partes.push(t('page_short',{count:esc(e.pagina)}));
  if(e.porcentagem!==null&&e.porcentagem!==undefined) partes.push(t('percent_complete_short',{count:esc(e.porcentagem)}));
  if(e.capitulo) partes.push(e.progresso_tipo==='livre'?esc(e.capitulo):`${t('chapter')} ${esc(e.capitulo)}`);
  return partes.join(' · ') || (e.nota?t('entry_note'):t('free_progress'));
}
function paginaEfetiva(e){
  if(e.pagina!==null&&e.pagina!==undefined) return {valor:Number(e.pagina),estimada:false};
  if(e.pagina_estimada!==null&&e.pagina_estimada!==undefined) return {valor:Number(e.pagina_estimada),estimada:true};
  return null;
}
function progressoLeitura(l){
  const entradas=diarioEntradas.filter(e=>e.leitura_id===l.leitura_id).sort((a,b)=>new Date(b.created_at||0)-new Date(a.created_at||0));
  const pct=entradas.find(e=>e.porcentagem!==null&&e.porcentagem!==undefined);
  if(pct) return {texto:t('percent_complete',{count:esc(pct.porcentagem)}),barra:Number(pct.porcentagem)};
  let pag=null;
  for(const e of entradas){ pag=paginaEfetiva(e); if(pag){ break; } }
  if(pag){
    const total=Number(l.paginas)||0;
    const prefixo=pag.estimada?'~':'';
    if(total>0&&pag.valor<=total){
      const pct=Math.max(0,Math.min(100,Math.round(pag.valor/total*100)));
      return {texto:`${prefixo}${t('page_of_total',{count:esc(pag.valor),total})} · ${pct}%`,barra:pct};
    }
    return {texto:`${prefixo}${t('page_short',{count:esc(pag.valor)})}`,barra:null};
  }
  const cap=entradas.find(e=>e.capitulo);
  if(cap) return {texto:cap.progresso_tipo==='livre'?esc(cap.capitulo):`${t('chapter')} ${esc(cap.capitulo)}`,barra:null};
  if(l.status==='Lido') return {texto:t('percent_complete',{count:100}),barra:100};
  return {texto:'',barra:null};
}
function dataDiario(e){
  try{return new Date(e.created_at).toLocaleDateString(getLocale(),{day:'2-digit',month:'short'});}catch(_){return '';}
}
function leituraNoFim(l){
  if(!l||l.status!=='Lendo') return false;
  const entradas=diarioEntradas.filter(e=>e.leitura_id===l.leitura_id).sort((a,b)=>new Date(b.created_at||0)-new Date(a.created_at||0));
  const pct=entradas.find(e=>e.porcentagem!==null&&e.porcentagem!==undefined);
  if(pct&&Number(pct.porcentagem)>=100) return true;
  let pag=null;
  for(const e of entradas){ pag=paginaEfetiva(e); if(pag) break; }
  const total=Number(l.paginas)||0;
  return !!(pag&&total>0&&pag.valor>=total);
}
async function concluirLeitura(idx,el=null){
  const l=prateleira[idx];
  if(!l) return;
  if(el) el.disabled=true;
  const body={status:'Lido'};
  if(!(l.data||'').trim()){
    try{ body.data=new Date().toLocaleDateString(getLocale(),{month:'short',year:'numeric'}); }catch(_){}
  }
  try{
    const r=await fetch('/api/prateleira/'+l.leitura_id,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    if(!r.ok) throw new Error('patch status '+r.status);
  }catch(e){ if(el) el.disabled=false; toast(t('edit_save_error')); return; }
  await carregarPrateleira();
  abrirPosLeitura(leituraPosAcao(l));
}
function progressoDetalhado(l){
  if(!l) return null;
  const entradas=diarioEntradas.filter(e=>e.leitura_id===l.leitura_id&&paginaEfetiva(e)).sort((a,b)=>new Date(b.created_at||0)-new Date(a.created_at||0));
  if(!entradas.length) return null;
  const total=Number(l.paginas)||0;
  const atualEf=paginaEfetiva(entradas[0]);
  const atual=atualEf.valor;
  const pct=total>0?Math.max(0,Math.min(100,Math.round(atual/total*100))):null;
  let deltaTexto='';
  if(entradas.length>1){
    const anterior=paginaEfetiva(entradas[1]).valor;
    const diff=atual-anterior;
    const dataAnterior=dataDiario(entradas[1]);
    if(diff>0) deltaTexto=t('diary_delta_since',{count:diff,date:dataAnterior});
    else if(diff===0) deltaTexto=t('diary_delta_same',{date:dataAnterior});
    else deltaTexto=t('diary_delta_back',{count:Math.abs(diff),date:dataAnterior});
  }
  return {atual,total,pct,deltaTexto,estimada:atualEf.estimada};
}
function previsaoTermino(l){
  if(!l) return null;
  const total=Number(l.paginas)||0;
  if(total<=0) return null;
  const pontos=diarioEntradas.filter(e=>e.leitura_id===l.leitura_id).map(e=>({data:new Date(e.created_at||0),ef:paginaEfetiva(e)})).filter(p=>p.ef&&Number.isFinite(p.data.getTime())).sort((a,b)=>a.data-b.data);
  if(pontos.length<2) return null;
  const primeiro=pontos[0], ultimo=pontos[pontos.length-1];
  if(ultimo.ef.valor>=total) return null;
  const dias=(ultimo.data-primeiro.data)/86400000;
  const paginasLidas=ultimo.ef.valor-primeiro.ef.valor;
  if(dias<=0||paginasLidas<=0) return null;
  const ritmo=paginasLidas/dias;
  const diasRestantes=(total-ultimo.ef.valor)/ritmo;
  if(!Number.isFinite(diasRestantes)||diasRestantes<=0) return null;
  return new Date(Date.now()+diasRestantes*86400000);
}
function previsaoTerminoTexto(l){
  const data=previsaoTermino(l);
  if(!data) return '';
  return t('reading_pace_eta',{date:data.toLocaleDateString(getLocale(),{day:'2-digit',month:'long'})});
}
function progressoHeroFormHTML(l){
  const det=progressoDetalhado(l);
  if(!det) return '';
  const of=det.total>0?`<span class="progress-hero-of">${t('pages_suffix_of',{total:det.total})}</span>`:'';
  const pctTxt=det.pct!==null?`<span class="progress-hero-pct">${det.pct}%</span>`:'';
  const previsaoTexto=previsaoTerminoTexto(l);
  return `<div class="progress-hero">
    <div class="progress-hero-num">${det.estimada?'~':''}${det.atual}${of}${pctTxt}</div>
    ${det.pct!==null?`<div class="reading-progress progress-hero-track"><span style="width:${det.pct}%"></span></div>`:''}
    ${det.deltaTexto?`<div class="progress-hero-delta">${esc(det.deltaTexto)}</div>`:''}
    ${previsaoTexto?`<div class="progress-hero-eta">${esc(previsaoTexto)}</div>`:''}
  </div>`;
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
async function carregarTotalPaginas(form){
  if(!form||form.dataset.paginasLoaded==='1'||form.dataset.paginasLoading==='1') return;
  const edicaoId=form.dataset.edicaoId;
  if(!edicaoId){ form.dataset.paginasLoaded='1'; return; }
  const local=prateleira.find(l=>String(l.edicao_id)===String(edicaoId));
  if(Number(local?.paginas)>0){
    form.dataset.paginasTotal=String(local.paginas);
    form.dataset.paginasLoaded='1';
    aplicarTotalPaginas(form);
    return;
  }
  form.dataset.paginasLoading='1';
  try{
    const res=await fetch(`/api/edicoes/${edicaoId}/paginas`);
    if(res.ok){
      const data=await res.json();
      if(Number(data?.paginas)>0){
        form.dataset.paginasTotal=String(data.paginas);
        if(local) local.paginas=data.paginas;
      }
    }
  }catch(_){}
  delete form.dataset.paginasLoading;
  form.dataset.paginasLoaded='1';
  aplicarTotalPaginas(form);
}
function aplicarTotalPaginas(form){
  if(!form) return;
  const tipo=form.querySelector('[data-diary-input="tipo"]')?.value||'pagina';
  const pergunta=form.querySelector('[data-diary-total-field]');
  const slider=form.querySelector('[data-diary-progress-slider]');
  const chips=form.querySelector('[data-progress-quick-chips]');
  if(tipo!=='pagina'){
    if(pergunta) pergunta.hidden=true;
    if(slider) slider.hidden=true;
    if(chips) chips.hidden=true;
    return;
  }
  if(chips) chips.hidden=false;
  const total=Number(form.dataset.paginasTotal)||0;
  const suffix=form.querySelector('[data-diary-progress-suffix]');
  const valorInput=form.querySelector('[data-diary-input="valor"]');
  if(total){
    if(suffix){ suffix.textContent=t('pages_suffix_of',{total}); suffix.hidden=false; }
    if(valorInput) valorInput.max=String(total);
    if(pergunta) pergunta.hidden=true;
    if(slider){
      slider.max=String(total);
      slider.hidden=false;
      const n=Number(valorInput?.value);
      slider.value=String(Number.isFinite(n)?Math.max(0,Math.min(total,n)):0);
    }
  } else {
    if(slider) slider.hidden=true;
    if(pergunta) pergunta.hidden=form.dataset.paginasLoaded!=='1'; // só pergunta depois que a busca automática falhou — uma vez por edição
  }
}
function configurarInputProgressoDiario(form,tipoSeguro){
  const valorInput=form?.querySelector('[data-diary-input="valor"]');
  const label=form?.querySelector('[data-diary-progress-label]');
  const suffix=form?.querySelector('[data-diary-progress-suffix]');
  if(!valorInput) return;
  const datalist=form.querySelector('[data-diary-chapter-list]');
  const ordemField=form.querySelector('[data-diary-chapter-order-field]');
  const pageField=form.querySelector('[data-diary-chapter-page-field]');
  const pasteBox=form.querySelector('[data-diary-chapter-paste]');
  if(tipoSeguro==='capitulo'){
    if(datalist) valorInput.setAttribute('list',datalist.id);
    carregarCapitulosEdicao(form);
    if(ordemField) ordemField.hidden=false;
    if(pageField) pageField.hidden=false;
    if(pasteBox) pasteBox.hidden=!form.dataset.edicaoId;
  } else {
    valorInput.removeAttribute('list');
    if(ordemField) ordemField.hidden=true;
    if(pageField) pageField.hidden=true;
    if(pasteBox) pasteBox.hidden=true;
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
  if(tipoSeguro==='pagina'){ carregarTotalPaginas(form); }
  aplicarTotalPaginas(form);
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
  const leituraAtual=prateleira.find(x=>x.leitura_id===leituraId);
  // pra entrada nova em modo página, começa da última posição conhecida — os
  // chips de atalho (+10/+25/+50) e o slider partem de onde o leitor parou,
  // não de zero
  const ultimaPagina=!entry&&tipo==='pagina'?progressoDetalhado(leituraAtual)?.atual:null;
  const valorInicial=tipo==='pagina'?(entry?.pagina??(ultimaPagina??'')):(tipo==='porcentagem'?(entry?.porcentagem??''):(entry?.capitulo||''));
  const inputType=tipo==='capitulo'?'text':'number';
  const inputMode=tipo==='capitulo'?'text':'numeric';
  const minAttr=tipo==='pagina'?' min="1"':(tipo==='porcentagem'?' min="0"':'');
  const maxAttr=tipo==='porcentagem'?' max="100"':'';
  const placeholder=tipo==='pagina'?t('diary_page_placeholder'):(tipo==='porcentagem'?t('diary_percent_placeholder'):t('chapter_placeholder'));
  const label=tipo==='pagina'?t('diary_page_label'):(tipo==='porcentagem'?t('diary_percent_label'):t('diary_chapter_label'));
  const chip=(valor,label)=>`<button type="button" class="progress-unit ${tipo===valor?'active':''}" data-progress-chip="${valor}" aria-pressed="${tipo===valor?'true':'false'}" onclick="selecionarTipoDiario('${formKey}','${valor}',this)">${label}</button>`;
  const quickChip=(delta)=>`<button type="button" class="progress-quick-chip" data-progress-quick-chip onclick="ajustarPaginaChip('${formKey}',${delta})">+${delta} ${t('unit_page_short')}</button>`;
  const temNotaExistente=!!(entry&&(entry.nota||entry.publico||entry.spoiler));
  const totalConhecido=Number(leituraAtual?.paginas)||0;
  const sliderEscondido=!(tipo==='pagina'&&totalConhecido>0);
  const sliderValorInicial=Math.max(0,Math.min(totalConhecido,Number(valorInicial)||0));
  return `<div class="diary-form" data-diary-form="${formKey}"${edicaoId?` data-edicao-id="${edicaoId}"`:''}${totalConhecido?` data-paginas-total="${totalConhecido}" data-paginas-loaded="1"`:''}>
    <div class="label diary-form-title">${t('update_progress')}</div>
    <p class="form-helper diary-form-helper">${t('new_diary_subtitle')} · ${t('private_by_default')}</p>
    ${progressoHeroFormHTML(leituraAtual)}
    <input type="hidden" id="diaryProgressType_${formKey}" data-diary-input="tipo" value="${tipo}">
    <div class="field diary-progress-field"><label class="label" for="diaryProgressInput_${formKey}" data-diary-progress-label>${label}</label><div class="diary-progress-row"><div class="suffix-field diary-progress-value"><input id="diaryProgressInput_${formKey}" data-diary-input="valor" type="${inputType}" inputmode="${inputMode}"${minAttr}${maxAttr} step="1" value="${esc(valorInicial)}" placeholder="${placeholder}"${tipo==='capitulo'?` list="${chapterListId}"`:''} oninput="sincronizarSliderProgresso('${formKey}')"><span data-diary-progress-suffix${tipo==='porcentagem'?'':' hidden'}>%</span></div><div class="progress-units" aria-label="${t('how_track_progress')}">${chip('pagina',t('unit_page_short'))}${chip('porcentagem',t('unit_percent_short'))}${chip('capitulo',t('unit_chapter_short'))}</div></div>
      <input type="range" class="diary-progress-slider" data-diary-progress-slider min="0" max="${totalConhecido}" step="1" value="${sliderValorInicial}"${sliderEscondido?' hidden':''} aria-label="${label}" oninput="onSliderProgresso('${formKey}',this.value)">
      <div class="progress-quick-chips" data-progress-quick-chips${tipo==='pagina'?'':' hidden'}>${quickChip(10)}${quickChip(25)}${quickChip(50)}</div>
    <datalist id="${chapterListId}" data-diary-chapter-list></datalist></div>
    <div class="field diary-total-field" data-diary-total-field hidden><label class="label" for="diaryTotalInput_${formKey}">${t('edition_pages_question')}</label><input id="diaryTotalInput_${formKey}" data-diary-input="paginas_total" type="number" inputmode="numeric" min="1" step="1" placeholder="${t('diary_page_placeholder')}"><p class="form-helper">${t('edition_pages_hint')}</p></div>
    <div class="field diary-chapter-order-field" data-diary-chapter-order-field${tipo==='capitulo'?'':' hidden'}><label class="label" for="diaryChapterOrderInput_${formKey}">${t('diary_chapter_order_label')}</label><input id="diaryChapterOrderInput_${formKey}" data-diary-input="capitulo_ordem" type="number" inputmode="numeric" min="1" step="1" value="${esc(entry?.capitulo_ordem??'')}" placeholder="${t('diary_chapter_order_placeholder')}"></div>
    <div class="field diary-chapter-page-field" data-diary-chapter-page-field${tipo==='capitulo'?'':' hidden'}><label class="label" for="diaryChapterPageInput_${formKey}">${t('diary_chapter_page_label')}</label><input id="diaryChapterPageInput_${formKey}" data-diary-input="pagina_capitulo" type="number" inputmode="numeric" min="1" step="1" value="${esc(tipo==='capitulo'?(entry?.pagina??''):'')}" placeholder="${t('diary_chapter_page_placeholder')}"><p class="form-helper">${t('diary_chapter_page_hint')}</p></div>
    <div class="diary-chapter-paste" data-diary-chapter-paste${tipo==='capitulo'&&edicaoId?'':' hidden'}>
      <button type="button" class="linklike" data-paste-summary-toggle onclick="alternarColarSumario('${formKey}')">${t('paste_summary_toggle')}</button>
      <div class="diary-paste-summary-box" data-paste-summary-box hidden>
        <p class="form-helper">${t('paste_summary_hint')}</p>
        <textarea data-paste-summary-input rows="6" maxlength="20000" placeholder="${t('paste_summary_placeholder')}"></textarea>
        <button type="button" class="btn-secondary btn-small" onclick="salvarSumarioColado('${formKey}',this)">${t('paste_summary_save')}</button>
      </div>
    </div>
    <button type="button" class="linklike diary-extra-toggle" data-diary-extra-toggle onclick="alternarNotaDiario('${formKey}')">${t(temNotaExistente?'hide_note_toggle':'add_note_toggle')}</button>
    <div class="diary-extra" data-diary-extra${temNotaExistente?'':' hidden'}>
      <div class="field"><label class="label" for="diaryNoteInput_${formKey}">${t('entry_note')}</label><textarea id="diaryNoteInput_${formKey}" data-diary-input="nota" maxlength="2000" placeholder="${t('entry_note_placeholder')}">${esc(entry?.nota||'')}</textarea></div>
      <div class="visibility-box"><label class="check-line"><input type="checkbox" id="diarySpoilerInput_${formKey}" data-diary-input="spoiler" ${entry?.spoiler?'checked':''}> <span>${t('contains_spoiler')}</span></label><label class="check-line"><input type="checkbox" id="diaryPublicInput_${formKey}" data-diary-input="publico" ${entry?.publico?'checked':''}> <span>${t('show_on_public_profile')}</span></label></div>
    </div>
    <button class="btn-primary" onclick="salvarDiario(${leituraId},'${id}',this)">${t('save_diary')}</button>
  </div>`;
}
function alternarNotaDiario(formKey){
  const form=document.querySelector(`[data-diary-form="${CSS.escape(String(formKey))}"]`);
  const extra=form?.querySelector('[data-diary-extra]');
  const btn=form?.querySelector('[data-diary-extra-toggle]');
  if(!extra||!btn) return;
  const abrir=extra.hidden;
  extra.hidden=!abrir;
  btn.textContent=t(abrir?'hide_note_toggle':'add_note_toggle');
  if(abrir) extra.querySelector('textarea')?.focus({preventScroll:true});
}
function alternarColarSumario(formKey){
  const form=document.querySelector(`[data-diary-form="${CSS.escape(String(formKey))}"]`);
  const box=form?.querySelector('[data-paste-summary-box]');
  if(!box) return;
  box.hidden=!box.hidden;
  if(!box.hidden) box.querySelector('textarea')?.focus({preventScroll:true});
}
async function salvarSumarioColado(formKey,el){
  const form=document.querySelector(`[data-diary-form="${CSS.escape(String(formKey))}"]`);
  const edicaoId=form?.dataset?.edicaoId;
  const textarea=form?.querySelector('[data-paste-summary-input]');
  const texto=(textarea?.value||'').trim();
  if(!edicaoId||!texto) return;
  if(el) el.disabled=true;
  try{
    const r=await fetch(`/api/edicoes/${edicaoId}/capitulos/colar`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({texto})});
    if(!r.ok){
      toast(r.status===401||r.status===403?t('diary_login_error'):t('paste_summary_error'));
      return;
    }
    const datalist=form.querySelector('[data-diary-chapter-list]');
    if(datalist){ datalist.dataset.loaded=''; await carregarCapitulosEdicao(form); }
    if(textarea) textarea.value='';
    const box=form.querySelector('[data-paste-summary-box]');
    if(box) box.hidden=true;
    toast(t('paste_summary_saved'));
  }catch(_){ toast(t('paste_summary_error')); }
  finally{ if(el) el.disabled=false; }
}
function sincronizarSliderProgresso(formKey){
  const form=document.querySelector(`[data-diary-form="${CSS.escape(String(formKey))}"]`);
  const valorInput=form?.querySelector('[data-diary-input="valor"]');
  const slider=form?.querySelector('[data-diary-progress-slider]');
  if(!valorInput||!slider||slider.hidden) return;
  const n=Number(valorInput.value);
  if(Number.isFinite(n)) slider.value=String(Math.max(0,Math.min(Number(slider.max)||0,n)));
}
function onSliderProgresso(formKey,valor){
  const form=document.querySelector(`[data-diary-form="${CSS.escape(String(formKey))}"]`);
  const valorInput=form?.querySelector('[data-diary-input="valor"]');
  if(valorInput) valorInput.value=valor;
}
function ajustarPaginaChip(formKey,delta){
  const form=document.querySelector(`[data-diary-form="${CSS.escape(String(formKey))}"]`);
  const valorInput=form?.querySelector('[data-diary-input="valor"]');
  if(!valorInput) return;
  const total=Number(form.dataset.paginasTotal)||0;
  const atual=Number(valorInput.value)||0;
  const proximo=Math.max(1,total>0?Math.min(total,atual+delta):atual+delta);
  valorInput.value=String(proximo);
  sincronizarSliderProgresso(formKey);
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
  const paginaCapituloRaw=(campo('pagina_capitulo')?.value||'').trim();
  const paginaCapituloNumber=Number(paginaCapituloRaw);
  const paginaCapitulo=progresso_tipo==='capitulo'&&paginaCapituloRaw!==''&&Number.isInteger(paginaCapituloNumber)&&paginaCapituloNumber>0?paginaCapituloNumber:null;
  const pagina=progresso_tipo==='pagina'&&valorRaw!==''&&Number.isInteger(valorNumber)&&valorNumber>0?valorNumber:paginaCapitulo;
  const porcentagem=progresso_tipo==='porcentagem'&&valorRaw!==''&&Number.isFinite(valorNumber)&&valorNumber>=0&&valorNumber<=100?valorNumber:null;
  const capitulo=progresso_tipo==='capitulo'?valorRaw:'';
  const ordemRaw=(campo('capitulo_ordem')?.value||'').trim();
  const ordemNumber=Number(ordemRaw);
  const capitulo_ordem=progresso_tipo==='capitulo'&&ordemRaw!==''&&Number.isInteger(ordemNumber)&&ordemNumber>0?ordemNumber:null;
  const totalRaw=(campo('paginas_total')?.value||'').trim();
  const totalNumber=Number(totalRaw);
  const paginas_total=progresso_tipo==='pagina'&&totalRaw!==''&&Number.isInteger(totalNumber)&&totalNumber>0?totalNumber:null;
  return {
    progresso_tipo,
    pagina,
    porcentagem,
    capitulo,
    capitulo_ordem,
    paginas_total,
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
    diarioEditId=null; await carregarPrateleira(); if(cardAtual) renderDetalheLivro(cardAtual); else renderDiario();
    const leituraSalva=prateleira.find(x=>String(x.leitura_id)===String(leituraId));
    toast(leituraNoFim(leituraSalva)?t('reading_finished_hint'):t('diary_entry_saved'));
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
function abrirEstanteFiltrada(f){
  filtroEstante=['Todos','Lido','Lendo','Quero ler'].includes(f)?f:'Todos';
  irPara('estante',{subaba:'shelf'});
}
function abrirMinhaEstantePerfil(){
  filtroEstante='Todos';
  irPara('estante',{subaba:'shelf'});
}
function perfilLoginCTAHTML(extraClass=''){
  if(minhaConta.logado) return '';
  return `<section class="account-box profile-login-cta ${extraClass}" aria-labelledby="profileLoginCtaTitle">
    <div class="label">${t('account')}</div>
    <h3 id="profileLoginCtaTitle">${t('profile_login_cta_title')}</h3>
    <p>${t('profile_login_cta_text')}</p>
    <button class="pbtn solid" type="button" onclick="conectarGoogle()">${t('profile_login_cta_button')}</button>
  </section>`;
}
function estatisticasPerfilHTML(total,lendo,lidos,quero){
  if(!total){
    return `<section class="account-box profile-stats-box profile-stats-empty"><div class="label">${t('your_lombada')}</div><p>${t('profile_shelf_empty')}</p><div class="profile-empty-actions"><button class="pbtn solid" type="button" onclick="irPara('buscar')">${t('search_books')}</button>${!minhaConta.logado?`<button class="pbtn" type="button" onclick="conectarGoogle()">${t('profile_login_cta_button')}</button>`:''}</div></section>`;
  }
  const stats=[
    [total,t('profile_stat_readings'),'Todos'],
    [lendo,t('currently_reading'),'Lendo'],
    [lidos,t('status_read'),'Lido'],
    [quero,t('want_to_read'),'Quero ler']
  ];
  return `<section class="account-box profile-stats-box"><div class="label">${t('your_lombada')}</div><div class="profile-quick-stats">${stats.map(([valor,label,filtro])=>`<button type="button" class="metric-link" onclick="abrirEstanteFiltrada('${filtro}')"><strong>${valor}</strong><span>${label}</span></button>`).join('')}</div><button class="pbtn solid profile-shelf-cta" type="button" onclick="abrirMinhaEstantePerfil()">${t('view_my_shelf')}</button></section>`;
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
        <button class="pbtn solid" type="button" onclick="conectarGoogle()">${t('login_google')}</button>
      </div>`;
  const editarPerfilHTML=logado?`
      <form id="profileEditForm" class="account-box profile-edit-form" onsubmit="event.preventDefault();salvarPerfil(this.querySelector('button[type=submit]'))">
        <div class="label">${t('edit_profile')}</div>
        <div class="profile-edit-field profile-photo-field">
          <label>${t('profile_photo')}</label>
          <div class="photo-row">
            ${avatarHTML(nome,meuHandle,minhaConta.avatar_url).replace('avatar-chip','avatar-chip avatar-lg')}
            <div class="photo-actions">
              <button type="button" class="pbtn" onclick="$('#avatarFileInput').click()">${t('change_photo')}</button>
              ${minhaConta.avatar_custom?`<button type="button" class="pbtn" onclick="removerFotoPerfil(this)">${t('remove_photo')}</button>`:''}
            </div>
            <input id="avatarFileInput" type="file" accept="image/jpeg,image/png,image/webp,image/*" hidden onchange="enviarFotoPerfil(this)">
          </div>
        </div>
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
      <button type="button" class="profile-gear" onclick="alternarConfigPerfil()" aria-label="${t('profile_settings')}" title="${t('profile_settings')}">
        <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .34 1.87l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.7 1.7 0 0 0-1.87-.34 1.7 1.7 0 0 0-1.03 1.56V21a2 2 0 1 1-4 0v-.09a1.7 1.7 0 0 0-1.11-1.56 1.7 1.7 0 0 0-1.87.34l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.7 1.7 0 0 0 .34-1.87 1.7 1.7 0 0 0-1.56-1.03H3a2 2 0 1 1 0-4h.09a1.7 1.7 0 0 0 1.56-1.11 1.7 1.7 0 0 0-.34-1.87l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.7 1.7 0 0 0 1.87.34h.09a1.7 1.7 0 0 0 1.03-1.56V3a2 2 0 1 1 4 0v.09a1.7 1.7 0 0 0 1.03 1.56 1.7 1.7 0 0 0 1.87-.34l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.7 1.7 0 0 0-.34 1.87v.09a1.7 1.7 0 0 0 1.56 1.03H21a2 2 0 1 1 0 4h-.09a1.7 1.7 0 0 0-1.56 1.03z"/></svg>
      </button>
      <div class="profile-top">
        <div class="profile-avatar">${esc(inicial)}${minhaConta.avatar_url?`<img src="${esc(minhaConta.avatar_url)}" alt="" referrerpolicy="no-referrer" onerror="this.remove()">`:''}</div>
        <div class="profile-stats-row">
          <button type="button" class="profile-stat" onclick="abrirMinhaEstantePerfil()"><strong>${n}</strong><span>${t('stat_books')}</span></button>
          <button type="button" class="profile-stat" onclick="abrirMinhasConexoes('followers')"><strong>${minhaConta.followers_count||0}</strong><span>${t('stat_followers')}</span></button>
          <button type="button" class="profile-stat" onclick="abrirMinhasConexoes('following')"><strong>${minhaConta.following_count||0}</strong><span>${t('stat_following')}</span></button>
        </div>
      </div>
      <div class="profile-id">
        <div class="phandle">${nome?esc(nome):t('lombada_reader')}</div>
        <div class="pcount">@${esc(meuHandle)}</div>
        ${bio?`<p class="profile-bio">${esc(bio)}</p>`:''}
      </div>
      <div class="profile-cta-row">
        ${logado?`<button class="pbtn" type="button" onclick="alternarEditarPerfil()">${t('edit_profile')}</button>`:''}
        <button class="pbtn" type="button" onclick="compartilharPerfil()">${t('share_profile')}</button>
      </div>
      <div class="profile-metrics"><button type="button" class="metric-link" onclick="abrirEstanteFiltrada('Lido')"><strong>${lidos}</strong><span>${t('status_read')}</span></button><div><strong>${edicoesPossui}</strong><span>${t('owned_editions')}</span></div><div><strong>${edicoesDesejadas}</strong><span>${t('wanted_editions')}</span></div></div>
      ${logado?`<div id="profileEditWrap" hidden>${editarPerfilHTML}</div>`:''}
      ${!logado?perfilLoginCTAHTML():''}
      ${n?grelhaPerfilHTML():estatisticasPerfilHTML(0,0,0,0)}
      <div id="profileSettings" class="profile-settings" hidden>
      <div class="label settings-title">${t('profile_settings')}</div>
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
      ${n?estatisticasPerfilHTML(n,lendo,lidos,quero):''}
      <div class="account-box library-box">
        <div class="label">${t('library')}</div>
        <p>${t('library_hint')}</p>
        <button class="pbtn" onclick="abrirManual()">${t('manual_prominent_button')}</button>
      </div>
      ${contaHTML}
      ${installCtaHTML()}
      ${(appVersion&&appVersion!=='dev')?`<div class="app-version">${/^\d/.test(appVersion.replace(/\.0$/,''))?'Lombada v':'Lombada · '}${esc(appVersion.replace(/\.0$/,''))}</div>`:''}
      ${DEBUG?`<div class="app-version">APP_VERSION ${esc(appVersion)} · app.js ${esc(APP_JS_VERSION)} · cache ${esc(activeSwCache)}</div>`:''}
      </div>
    </div>`;
}

/* vitrine do perfil: grade de capas das últimas leituras, estilo grid de posts */
function grelhaPerfilHTML(){
  if(!prateleira.length) return '';
  const itens=prateleira.slice(0,12);
  return `<section class="profile-shelf">
    <div class="section-head"><div class="label">${t('profile_recent_readings')}</div><span class="more" onclick="abrirMinhaEstantePerfil()">${t('view_my_shelf')}</span></div>
    <div class="wall profile-wall">${itens.map((l,i)=>`<div class="book" role="button" tabindex="0" onclick="abrirCard(${i})" aria-label="${esc(l.titulo)}">${coverHTML(l.titulo,l.autor,l.capa_url,l.nota?`<span class="stars-overlay"><span>${estrelasStr(l.nota)}</span></span>`:'')}</div>`).join('')}</div>
  </section>`;
}

/* foto de perfil: recorte quadrado no cliente (256px JPEG) e envio em base64;
   o servidor guarda no banco (disco do Render free é efêmero) */
async function enviarFotoPerfil(input){
  const file=input.files?.[0];
  input.value='';
  if(!file) return;
  const objUrl=URL.createObjectURL(file);
  const img=new Image();
  img.onload=()=>abrirRecorteAvatar(img,objUrl);
  img.onerror=()=>{ URL.revokeObjectURL(objUrl); toast(t('photo_error')); };
  img.src=objUrl;
}

/* editor de recorte: arrastar pra posicionar + controle de zoom; exporta
   512px JPEG e envia em base64 (o servidor guarda no banco) */
let cropCtx=null;
function abrirRecorteAvatar(img,objUrl){
  let modal=$('#cropModal');
  if(!modal){
    modal=document.createElement('div');
    modal.id='cropModal';
    modal.className='modal crop-modal';
    modal.onclick=e=>{ if(e.target===modal) fecharRecorteAvatar(); };
    modal.innerHTML=`<div class="modal-card crop-card" role="dialog" aria-modal="true" aria-label="${t('adjust_photo')}">
      <div class="label">${t('adjust_photo')}</div>
      <p class="crop-hint">${t('crop_hint')}</p>
      <div class="crop-viewport" id="cropViewport"></div>
      <input type="range" id="cropZoom" min="100" max="300" value="100" aria-label="zoom">
      <div class="modal-actions">
        <button type="button" class="btn-share-card" onclick="confirmarRecorteAvatar(this)">${t('use_photo')}</button>
        <button type="button" class="btn-secondary" onclick="fecharRecorteAvatar()">${t('cancel_action')}</button>
      </div></div>`;
    document.body.appendChild(modal);
  }
  const vp=modal.querySelector('#cropViewport');
  vp.innerHTML='';
  vp.appendChild(img);
  modal.classList.add('open');
  const V=vp.clientWidth||280;
  const s0=V/Math.min(img.naturalWidth,img.naturalHeight);
  cropCtx={img,objUrl,V,s0,z:1,ox:(V-img.naturalWidth*s0)/2,oy:(V-img.naturalHeight*s0)/2,drag:null};
  const zoom=modal.querySelector('#cropZoom');
  zoom.value=100;
  zoom.oninput=()=>ajustarZoomRecorte(Number(zoom.value)/100);
  vp.onpointerdown=e=>{ e.preventDefault(); vp.setPointerCapture(e.pointerId); cropCtx.drag={x:e.clientX,y:e.clientY,ox:cropCtx.ox,oy:cropCtx.oy}; };
  vp.onpointermove=e=>{ if(!cropCtx?.drag) return; cropCtx.ox=cropCtx.drag.ox+(e.clientX-cropCtx.drag.x); cropCtx.oy=cropCtx.drag.oy+(e.clientY-cropCtx.drag.y); aplicarTransfRecorte(); };
  vp.onpointerup=vp.onpointercancel=()=>{ if(cropCtx) cropCtx.drag=null; };
  aplicarTransfRecorte();
}
function aplicarTransfRecorte(){
  const c=cropCtx; if(!c) return;
  const s=c.s0*c.z, w=c.img.naturalWidth*s, h=c.img.naturalHeight*s;
  c.ox=Math.min(0,Math.max(c.V-w,c.ox));
  c.oy=Math.min(0,Math.max(c.V-h,c.oy));
  Object.assign(c.img.style,{width:w+'px',height:h+'px',transform:`translate(${c.ox}px,${c.oy}px)`,maxWidth:'none',maxHeight:'none'});
}
function ajustarZoomRecorte(z){
  const c=cropCtx; if(!c) return;
  const sOld=c.s0*c.z, sNew=c.s0*z;
  const cx=(c.V/2-c.ox)/sOld, cy=(c.V/2-c.oy)/sOld;
  c.z=z;
  c.ox=c.V/2-cx*sNew;
  c.oy=c.V/2-cy*sNew;
  aplicarTransfRecorte();
}
function fecharRecorteAvatar(){
  $('#cropModal')?.classList.remove('open');
  if(cropCtx?.objUrl){ try{ URL.revokeObjectURL(cropCtx.objUrl); }catch(e){} }
  cropCtx=null;
}
async function confirmarRecorteAvatar(btn){
  const c=cropCtx; if(!c) return;
  btn.disabled=true;
  try{
    const s=c.s0*c.z, out=512;
    const canvas=document.createElement('canvas');
    canvas.width=canvas.height=out;
    const cx=canvas.getContext('2d');
    cx.imageSmoothingQuality='high';
    cx.drawImage(c.img,-c.ox/s,-c.oy/s,c.V/s,c.V/s,0,0,out,out);
    const blob=await new Promise(r=>canvas.toBlob(r,'image/jpeg',.85));
    if(!blob) throw new Error('canvas');
    const b64=await new Promise((res,rej)=>{ const fr=new FileReader(); fr.onload=()=>res(String(fr.result).split(',')[1]||''); fr.onerror=rej; fr.readAsDataURL(blob); });
    if(!b64) throw new Error('b64');
    const r=await fetch('/api/eu/avatar',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({data:b64})});
    if(!r.ok) throw new Error(await r.text());
    const body=await r.json();
    minhaConta={...minhaConta,avatar_url:body.avatar_url,avatar_custom:true};
    fecharRecorteAvatar();
    toast(t('photo_updated'));
    renderPerfil();
    const wrap=$('#profileEditWrap'); if(wrap) wrap.hidden=false;
  }catch(e){ toast(t('photo_error')); btn.disabled=false; }
}

async function removerFotoPerfil(btn){
  if(btn) btn.disabled=true;
  try{
    const r=await fetch('/api/eu/avatar',{method:'DELETE'});
    if(!r.ok) throw new Error(await r.text());
    const body=await r.json();
    minhaConta={...minhaConta,avatar_url:body.avatar_url||'',avatar_custom:false};
    toast(t('photo_removed'));
    renderPerfil();
    const wrap=$('#profileEditWrap'); if(wrap) wrap.hidden=false;
  }catch(e){ toast(t('photo_error')); if(btn) btn.disabled=false; }
}

function alternarConfigPerfil(){
  const box=$('#profileSettings'); if(!box) return;
  box.hidden=!box.hidden;
  if(!box.hidden) box.scrollIntoView({behavior:'smooth',block:'nearest'});
}

function alternarEditarPerfil(){
  const wrap=$('#profileEditWrap'); if(!wrap) return;
  wrap.hidden=!wrap.hidden;
  if(!wrap.hidden){ wrap.scrollIntoView({behavior:'smooth',block:'nearest'}); $('#profileNameInput')?.focus(); }
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

function posLeituraAberto(){
  return $('#postReadModal')?.classList.contains('open');
}
function leituraPosAcao(l){
  if(!l) return null;
  return prateleira.find(x=>x.leitura_id===l.leitura_id) || prateleira.find(x=>chaveLivro(x)===chaveLivro(l)) || l;
}
function fecharPosLeitura(){
  $('#postReadModal')?.classList.remove('open');
}
function abrirPosLeitura(livro){
  const modal=$('#postReadModal');
  const body=$('#postReadBody');
  if(!modal||!body||!livro) return;
  body.innerHTML=`
    <div class="post-read-kicker">${t('post_read_kicker')}</div>
    <h2 id="postReadTitle">${t('post_read_title')}</h2>
    <p>${t('post_read_message',{title:esc(livro.titulo||t('untitled_book'))})}</p>
    <div class="post-read-actions">
      <button type="button" class="post-read-primary" onclick="compartilharLeituraRegistrada()">${t('post_read_share')}</button>
      <button type="button" class="post-read-secondary" onclick="escreverDiarioLeituraRegistrada()">${t('post_read_diary')}</button>
      <button type="button" class="post-read-secondary" onclick="verEstanteLidos()">${t('post_read_shelf')}</button>
    </div>
    <button type="button" class="post-read-later" onclick="fecharPosLeitura()">${t('post_read_later')}</button>`;
  modal.dataset.leituraId=livro.leitura_id||'';
  modal.classList.add('open');
  requestAnimationFrame(()=>modal.querySelector('.post-read-primary')?.focus());
}
function livroPosLeituraAtual(){
  const id=Number($('#postReadModal')?.dataset?.leituraId||0);
  return prateleira.find(l=>Number(l.leitura_id)===id) || null;
}
async function compartilharLeituraRegistrada(){
  await compartilharEstante();
}
function escreverDiarioLeituraRegistrada(){
  const livro=livroPosLeituraAtual();
  fecharPosLeitura();
  const idx=prateleira.findIndex(l=>l.leitura_id===livro?.leitura_id);
  if(idx>=0) abrirDiarioLeitura(idx);
  else irPara('estante',{subaba:'diario'});
}
function verEstanteLidos(){
  fecharPosLeitura();
  filtroEstante='Lido';
  irPara('estante',{subaba:'shelf',recarregar:false});
  renderPrateleira();
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
function shareCardSize(){
  return {w:1080,h:1920};
}
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
function fitContainRect(iw,ih,x,y,w,h,inset=0){
  const safeX=x+inset,safeY=y+inset;
  const safeW=Math.max(1,w-inset*2),safeH=Math.max(1,h-inset*2);
  const ir=iw/ih,wr=safeW/safeH;
  let dw,dh;
  if(ir>wr){dw=safeW;dh=safeW/ir;}
  else{dh=safeH;dw=safeH*ir;}
  return {x:safeX+(safeW-dw)/2,y:safeY+(safeH-dh)/2,w:dw,h:dh};
}
function drawOriginalShareCover(ctx,im,x,y,w,h){
  const inset=Math.max(0,Math.min(14,Math.min(w,h)*0.018));
  const r=fitContainRect(im.width,im.height,x,y,w,h,inset);
  ctx.save();
  ctx.imageSmoothingEnabled=true;
  ctx.imageSmoothingQuality='high';
  ctx.fillStyle='rgba(26,23,20,.18)';
  ctx.fillRect(r.x+14,r.y+18,r.w,r.h);
  ctx.drawImage(im,r.x,r.y,r.w,r.h);
  ctx.strokeStyle=effectiveCardTheme()==='dark'?'rgba(243,235,221,.22)':'rgba(26,23,20,.22)';
  ctx.lineWidth=2;
  ctx.strokeRect(r.x,r.y,r.w,r.h);
  ctx.restore();
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
  if(payload.excerpt){ctx.fillStyle=p.text;ctx.font="italic 44px Spectral, serif";wrapLeft(ctx,'"'+payload.excerpt+'"',110,y,W-220,56,(reviewCardActive()||diaryCardActive())?2:3);}
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
  const cx=110,cy=120,cw=W-220;
  const ch=(reviewCardActive()||diaryCardActive())?860:1120;
  await drawShareCover(ctx,l,cx,cy,cw,ch,selected);
  drawShareCardText(ctx,l,W,H,cy,ch);
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
  const statusAnterior=cardAtual?.status;
  const body={ status:$('#e_status').value, nota:notaEdit||null,
    relato:$('#e_relato').value.trim(), publico:$('#e_publico').checked, spoiler:$('#e_spoiler').checked, data:$('#e_data').value.trim() };
  const leituraEditada=cardAtual ? {...cardAtual,status:body.status} : null;
  try{
    const r=await fetch('/api/prateleira/'+cardAtual.leitura_id,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    if(!r.ok) throw new Error('patch status '+r.status);
  }
  catch(e){ toast(t('edit_save_error')); return; }
  fecharModalParaNavegacao(); await carregarPrateleira();
  if(statusAnterior!=='Lido' && body.status==='Lido') abrirPosLeitura(leituraPosAcao(leituraEditada));
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
function leiturasEmAndamento(){
  return prateleira.map((l,idx)=>({l,idx})).filter(item=>item.l?.status==='Lendo');
}
function registrarLeituraRapida(){
  fecharAcoesLeitura();
  irPara('buscar');
  setTimeout(()=>{ $('#q')?.focus(); },120);
}
function atualizarProgressoRapido(idx=null){
  const lendo=leiturasEmAndamento();
  const alvo=Number.isInteger(idx)?idx:(lendo.length===1?lendo[0].idx:null);
  if(alvo===null){ renderAcoesLeitura(true); return; }
  fecharAcoesLeitura();
  abrirDiarioLeitura(alvo);
}
function renderAcoesLeitura(mostrarAviso=false){
  const body=$('#quickActionsBody'); if(!body) return;
  const lendo=leiturasEmAndamento();
  const hint=$('#quickActionsHint');
  if(hint) hint.textContent=t(lendo.length?'quick_actions_hint_active':'quick_actions_hint_empty');
  const lista=lendo.slice(0,4).map(({l,idx})=>`<button class="quick-reading-row" type="button" onclick="atualizarProgressoRapido(${idx})"><span>${esc(l.titulo)}</span><small>${esc(l.autor||'')}</small></button>`).join('');
  const progresso=lendo.length===0
    ? ''
    : lendo.length===1
      ? `<button class="quick-action primary" type="button" onclick="atualizarProgressoRapido()"><strong>${t('update_progress')}</strong><span>${t('quick_update_hint')}</span></button>`
      : `<div class="quick-action-group primary"><div class="quick-action-title">${t('update_progress')}</div><div class="quick-action-sub">${t('quick_update_hint')}</div><div class="quick-reading-list">${lista}</div></div>`;
  const registrarLabel=lendo.length?t('quick_register_new_reading'):t('quick_register_reading');
  const registrarHint=lendo.length?t('quick_register_new_hint'):t('quick_register_hint_empty');
  body.innerHTML=`${progresso}${mostrarAviso?`<p class="quick-actions-note">${t('quick_no_reading')}</p>`:''}<button class="quick-action" type="button" onclick="registrarLeituraRapida()"><strong>${registrarLabel}</strong><span>${registrarHint}</span></button>`;
}
function abrirAcoesLeitura(){
  renderAcoesLeitura();
  const panel=$('#quickActions'); if(!panel) return;
  panel.hidden=false;
  $('#tabAdd')?.setAttribute('aria-expanded','true');
  document.body.classList.add('quick-actions-open');
  setTimeout(()=>panel.querySelector('button:not([disabled])')?.focus?.({preventScroll:true}),30);
}
function fecharAcoesLeitura(){
  const panel=$('#quickActions'); if(!panel) return;
  panel.hidden=true;
  $('#tabAdd')?.setAttribute('aria-expanded','false');
  document.body.classList.remove('quick-actions-open');
}
/* botão central "+": abre ações rápidas de leitura */
function abrirRegistro(event){
  event?.preventDefault?.();
  const panel=$('#quickActions');
  if(panel && !panel.hidden) fecharAcoesLeitura(); else abrirAcoesLeitura();
}

/* swipe horizontal alterna subabas (feed: descobrir/seguindo · estante: estante/diário) */
function configurarSwipeAbas(){
  let sx=0,sy=0,ok=false;
  const ignora=el=>!!el.closest?.('.stories-strip,.shelf-filters,.reader-shelf,input,textarea,.modal,.share-canvas');
  document.addEventListener('touchstart',e=>{
    if(e.touches.length!==1||ignora(e.target)){ ok=false; return; }
    ok=true; sx=e.touches[0].clientX; sy=e.touches[0].clientY;
  },{passive:true});
  document.addEventListener('touchend',e=>{
    if(!ok) return; ok=false;
    const dx=e.changedTouches[0].clientX-sx, dy=e.changedTouches[0].clientY-sy;
    if(Math.abs(dx)<70||Math.abs(dx)<Math.abs(dy)*1.6) return;
    const esq=dx<0;
    if(navAtual.aba==='feed'){ mudarFeedTab(esq?'following':'discover'); }
    else if(navAtual.aba==='estante'){ irPara('estante',{subaba:esq?'diario':'shelf'}); }
  },{passive:true});
}

/* pull-to-refresh no feed (o PWA instalado não tem botão de recarregar) */
function configurarPullToRefresh(){
  const sec=$('#secFeed'); if(!sec) return;
  const ind=document.createElement('div');
  ind.className='ptr-indicator';
  ind.innerHTML='<span class="ptr-spin"></span>';
  sec.prepend(ind);
  let startY=0,pulling=false,dist=0;
  document.addEventListener('touchstart',e=>{
    if(navAtual.aba!=='feed'||window.scrollY>4||e.touches.length!==1||modalAberto()||leitorModalAberto()){ pulling=false; return; }
    pulling=true; dist=0; startY=e.touches[0].clientY;
  },{passive:true});
  document.addEventListener('touchmove',e=>{
    if(!pulling) return;
    dist=e.touches[0].clientY-startY;
    if(dist>0&&window.scrollY<=0){ ind.style.height=Math.min(64,dist*0.4)+'px'; ind.classList.toggle('ready',dist>150); }
  },{passive:true});
  document.addEventListener('touchend',async()=>{
    if(!pulling) return; pulling=false;
    const vai=dist>150;
    if(vai){ ind.classList.add('loading'); ind.style.height='52px'; await carregarFeed(); }
    ind.classList.remove('loading','ready');
    ind.style.height='0px';
  });
}

async function carregarVersaoApp(){
  try{
    const res=await fetch('/api/version',{cache:'no-store'});
    const body=await res.json().catch(()=>({}));
    appVersion=(body.version||APP_JS_VERSION||'dev').toString();
    debugLog('app_version_loaded',{app:body.app,version:appVersion,APP_JS_VERSION});
  }catch(e){ appVersion=APP_JS_VERSION||'dev'; }
}

async function carregarConfig(){
  try{
    appConfig=await (await fetch('/api/config',{cache:'no-store'})).json()||{};
  }catch(e){ appConfig={}; }
}

// Link de afiliado da Amazon a partir do ISBN. Usa a busca (mais robusta que
// /dp/{asin}: nem todo ISBN mapeia num ASIN). '' quando não há tag ou ISBN.
function linkAmazon(isbn){
  const tag=(appConfig&&appConfig.amazon_tag)||'';
  const cod=(isbn||'').toString().replace(/[^0-9Xx]/g,'');
  if(!tag||!cod) return '';
  return 'https://www.amazon.com.br/s?k='+encodeURIComponent(cod)+'&tag='+encodeURIComponent(tag);
}

// Botão "Comprar na Amazon" (ou '' se sem tag/ISBN). stopPropagation evita
// disparar o onclick do <li> da edição quando o botão vive dentro dele.
function botaoAmazon(isbn,cls){
  const url=linkAmazon(isbn);
  if(!url) return '';
  return `<a class="buy-amazon ${cls||''}" href="${esc(url)}" target="_blank" rel="noopener nofollow sponsored" onclick="event.stopPropagation()">${t('buy_amazon')}</a>`;
}

async function init(){
  // servidor grátis (Render free tier) hiberna após inatividade — a primeira
  // requisição pode levar até ~30s pra "acordar". Sem isso, a tela fica em
  // branco tempo suficiente pra parecer que o app quebrou.
  const coldStartTimer=setTimeout(showColdStartNotice,2500);
  const coldStartMaxTimer=setTimeout(()=>showColdStartFailure('Não consegui carregar agora.'),40000);
  tratarMensagemConta();
  const abaDeepLink=extrairAbaDeepLink();
  const estadoInicial=abaDeepLink?estadoNav(abaDeepLink,'home'):(lerEstadoNavSalvo() || estadoNav('buscar','home'));
  history.replaceState(estadoInicial,'');
  const buscaDeepLink=extrairBuscaDeepLink();
  const obraDeepLink=extrairObraDeepLink();
  renderChips();
  atualizarSeletorIdioma();
  configurarSwipeAbas();
  configurarPullToRefresh();
  carregarObrasPopulares();
  carregarEditorasHome();
  carregarEditorasBusca();
  await carregarVersaoApp();
  await carregarDiagnosticoSw();
  await carregarConfig();
  try{
    const me=await (await fetch('/api/eu')).json();
    minhaConta=me||{logado:false,provedor:'anonimo'};
    meuHandle=me.handle||'';
    $('#meuhandle').textContent='@'+meuHandle;
    $('#crumb').classList.add('visible');
    if(minhaConta.logado){ $('#activityBell').hidden=false; atualizarBadgeAtividade(); }
  }catch(e){}
  await carregarPrateleira();
  clearTimeout(coldStartTimer);
  clearTimeout(coldStartMaxTimer);
  hideColdStartNotice();
  aplicarHistorico(estadoInicial);
  if(buscaDeepLink){ $('#q').value=buscaDeepLink; buscar(); }
  atualizarToggleHomePopulares();
  if(obraDeepLink){ irPara('buscar',{resetBusca:false,registrar:false}); await abrirPaginaObra(obraDeepLink); }
}
init();
