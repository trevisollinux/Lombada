const $ = s => document.querySelector(s);
const esc = s => (s||'').toString().replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const capaProxy = u => u ? '/api/capa?url='+encodeURIComponent(u) : '';

const SUGESTOES = ['Crime e Castigo','A Montanha Mágica','Ulisses','Orlando','O Aleph','O Morro dos Ventos Uivantes'];

let meuHandle='', minhaConta={logado:false,provedor:'anonimo'}, escolha=null, edicaoSel=null, notaSel=0;
let resultadosArr=[], obrasAgrupadas=[], edicoesAtual=[], obraSocial=null, prateleira=[], cardAtual=null, notaEdit=0;
let filtroEstante='Todos';
let ultimoLivroSalvo=null;
let timerDestaqueLivro=null;
let visualizacaoEstante=localStorage.getItem('lombada_view_estante')==='lista'?'lista':'grade';
let navAtual={aba:'buscar',busca:'home'};
let restaurandoHistorico=false;
const LOGIN_HINT_KEY='lombada_login_hint_dismissed';

const THEME_KEY='lombada_theme';
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
function alternarTema(){
  const atual=document.body.getAttribute('data-theme')==='dark'?'dark':'light';
  definirTema(atual==='dark'?'light':'dark');
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
}
function conviteLoginHTML(){
  if(!deveMostrarConviteLogin()) return '';
  const texto=conviteLoginPendente
    ? 'sua leitura foi salva. conecte o Google para não perder sua estante.'
    : 'conecte o Google para não perder sua estante.';
  return `<div class="login-hint" role="status">
    <p>${texto}</p>
    <div class="login-hint-actions">
      <button class="login-hint-primary" onclick="conectarGoogle()">conectar Google</button>
      <button class="login-hint-secondary" onclick="continuarSemConta()">continuar sem conta</button>
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
function tratarMensagemConta(){
  const params=new URLSearchParams(location.search);
  const conta=params.get('conta');
  if(conta==='ok') toast('conta conectada com sucesso');
  if(conta==='erro') toast('não foi possível conectar sua conta');
  if(conta){
    params.delete('conta');
    const qs=params.toString();
    history.replaceState(history.state || estadoNav('buscar','home'), '', location.pathname+(qs?'?'+qs:'')+location.hash);
  }
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
function coverFallbackHTML(titulo,autor,extra='',variacao=0){
  const d=capaArteDados(titulo,autor,variacao);
  const meta=autor?`<div class="cover-art-author">${esc(autor).toUpperCase()}</div>`:'';
  return `<div class="cover cover-art ${d.layout}" data-initial="${esc((titulo||'?').charAt(0).toUpperCase())}" style="--cover-ink:${d.tinta};--cover-ink-2:${d.tinta2};--cover-paper:${d.papel}">
    <div class="cover-art-rule"></div>
    ${meta}
    <div class="cover-art-title">${esc(titulo)}</div>
    <div class="cover-art-meta">lombada · edição de leitor</div>
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
  if(capa){
    return `<div class="cover">
      <img src="${esc(capaProxy(capa))}" alt="" loading="lazy" data-title="${esc(titulo)}" data-author="${esc(autor)}" onerror="trocarParaCapaArte(this)">
      ${extra||''}</div>`;
  }
  return coverFallbackHTML(titulo,autor,extra);
}

/* navegação entre abas */
function estadoNav(aba=navAtual.aba,busca=navAtual.busca,modal=false){
  return {lombada:true,aba,busca,modal};
}
function modalAberto(){
  return $('#modal')?.classList.contains('open');
}
function fecharModalDireto(){
  $('#modal')?.classList.remove('open');
  const editPanel=$('#editPanel');
  if(editPanel) editPanel.style.display='none';
}
function fecharModalParaNavegacao(){
  if(!modalAberto())return;
  const estado=estadoNav(navAtual.aba,navAtual.busca,false);
  fecharModalDireto();
  if(history.state && history.state.lombada && history.state.modal) history.replaceState(estado,'');
}
function registrarHistorico(aba,busca,replace=false){
  if(!restaurandoHistorico) fecharModalParaNavegacao();
  navAtual={aba,busca};
  if(restaurandoHistorico)return;
  const estado=estadoNav(aba,busca,false);
  if(replace) history.replaceState(estado,'');
  else history.pushState(estado,'');
}
function irPara(aba,opcoes={}){
  const resetBusca=opcoes.resetBusca ?? aba==='buscar';
  const registrar=opcoes.registrar ?? true;
  const secs={buscar:'#secBuscar',estante:'#secEstante',diario:'#secDiario',perfil:'#secPerfil'};
  for(const k in secs) $(secs[k]).style.display = (k===aba)?'':'none';
  $('#tabBuscar').classList.toggle('active',aba==='buscar');
  $('#tabEstante').classList.toggle('active',aba==='estante');
  $('#tabDiario').classList.toggle('active',aba==='diario');
  $('#tabPerfil').classList.toggle('active',aba==='perfil');
  if(aba==='buscar' && resetBusca){ $('#q').value=''; limparBusca(); mostrarBusca('home',{registrar:false}); }
  const recarregarEstante=opcoes.recarregar ?? true;
  if(aba==='estante' && recarregarEstante) carregarPrateleira();
  if(aba==='diario') renderDiario();
  if(aba==='perfil') renderPerfil();
  navAtual={aba,busca:aba==='buscar'?navAtual.busca:'home'};
  if(registrar) registrarHistorico(navAtual.aba,navAtual.busca);
  if(opcoes.scrollTop !== false) window.scrollTo({top:0,behavior:'smooth'});
}

/* pilha de telas DENTRO da aba buscar: home → resultados → edicoes → form.
   mostra exatamente uma de cada vez (mata o "carrega embaixo"). */
function mostrarBusca(tela,opcoes={}){
  const registrar=opcoes.registrar ?? tela!=='home';
  const telas={home:'#homeFeed',resultados:'#resultados',edicoes:'#edicoes',form:'#form',manual:'#manual'};
  for(const k in telas) $(telas[k]).style.display = (k===tela)?'':'none';
  navAtual={aba:'buscar',busca:tela};
  if(registrar) registrarHistorico('buscar',tela);
  window.scrollTo({top:0,behavior:'smooth'});
}
function aplicarHistorico(estado){
  const proximo=estado && estado.lombada ? estado : estadoNav('buscar','home');
  const deveReabrirModal=!!proximo.modal;
  if(modalAberto() && !deveReabrirModal) fecharModalDireto();
  restaurandoHistorico=true;
  irPara(proximo.aba,{registrar:false,resetBusca:false});
  if(proximo.aba==='buscar') mostrarBusca(proximo.busca||'home',{registrar:false});
  navAtual={aba:proximo.aba,busca:proximo.busca||'home'};
  restaurandoHistorico=false;
  if(deveReabrirModal && Number.isInteger(proximo.card) && prateleira[proximo.card]) abrirCard(proximo.card,{registrar:false});
}
window.onpopstate=e=>aplicarHistorico(e.state);


/* mostra/esconde feed da home conforme há busca */
function onQInput(){
  const v=$('#q').value.trim();
  if(!v){ limparBusca(); mostrarBusca('home',{registrar:false}); registrarHistorico('buscar','home'); }
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

/* feed da home — obras populares como mini estante (lista curada) */
function renderChips(){
  const hint=$('#searchHint');
  if(hint) hint.remove();
  $('#populares').innerHTML = SUGESTOES.map(s=>
    `<div class="book" onclick="buscarTermo('${esc(s).replace(/'/g,"\\'")}')">
       ${coverHTML(s,'','')}
       <div class="t">${esc(s)}</div></div>`).join('');
}
function lendoAgoraCard(l,idx,compacto=false){
  const progresso=l.status==='Lendo'?(l.nota?Math.min(100,Math.round(Number(l.nota)*20)):62):0;
  return `<div class="reading-now-card ${compacto?'compact':''}" onclick="abrirCard(${idx})">
    <div class="reading-cover">${coverHTML(l.titulo,l.autor,l.capa_url,'')}</div>
    <div class="reading-copy">
      <div class="label">lendo agora</div>
      <h3>${esc(l.titulo)}</h3>
      <p>${esc(l.autor)}</p>
      <div class="reading-spacer"></div>
      <div class="reading-meta">${progresso}% concluído</div>
      <div class="reading-progress"><span style="width:${progresso}%"></span></div>
    </div>
  </div>`;
}
function renderLendoAgora(){
  const lendo = prateleira.filter(l=>l.status==='Lendo');
  const box=$('#lendoAgora');
  if(!lendo.length){ box.innerHTML=''; return; }
  const l=lendo[0], idx=prateleira.indexOf(l);
  box.innerHTML=`<div class="section-head"><h2 class="h-section">Continue sua leitura</h2><span class="more" onclick="irPara('estante')">ver estante →</span></div>${lendoAgoraCard(l,idx)}`;
}



const EDITORAS_BR = ['companhia das letras','editora 34','penguin companhia','martin claret','antofagica','nova fronteira','jose olympio','record','l&pm','l pm','todavia'];
const TERMOS_NAO_OBRA = ['tese','dissertacao','seminario','estudo critico','resumo','analise','biografia','correspondencia','ensaio sobre','thesis','dissertation','study','studies','essays','critique','analysis','biography','correspondence'];
function normalizarTextoBase(s){return (s||'').toString().normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase();}
function normalizarTituloObra(titulo){
  return normalizarTextoBase(titulo)
    .replace(/&/g,' e ')
    .split(':')[0]
    .replace(/[^a-z0-9\s]/g,' ')
    .replace(/\b(romance|novel|livro|volume|vol)\b/g,' ')
    .replace(/\s+/g,' ')
    .trim();
}
function autorPrincipal(autor){return (autor||'').toString().split(/[,;\/]|\be\b|\band\b/i)[0].trim();}
function normalizarAutorObra(autor){return normalizarTextoBase(autorPrincipal(autor)).replace(/[^a-z0-9\s]/g,' ').replace(/\s+/g,' ').trim();}
function chaveObra(doc){return `${normalizarTituloObra(doc?.titulo||doc?.titulo_edicao)}|${normalizarAutorObra(doc?.autor)}`;}
function dadosEdicaoDeDoc(doc){
  const ed=doc?.edicao_isbn||{};
  return {
    titulo_edicao:ed.titulo_edicao||doc?.titulo,
    editora:ed.editora||doc?.editora||'',
    ano:ed.ano||doc?.ano||'',
    tradutor:ed.tradutor||doc?.tradutor||'',
    isbn:ed.isbn||doc?.isbn||'',
    idioma:ed.idioma||doc?.idioma||doc?.idioma_original||'',
    capa_url:ed.capa_url||doc?.capa_url||'',
    ol_edition_key:ed.ol_edition_key||doc?.ol_edition_key||null,
    pais:ed.pais||doc?.pais||''
  };
}
function edicaoAssinatura(e){return [normalizarTituloObra(e?.titulo_edicao),normalizarTextoBase(e?.editora),e?.ano||'',normalizarTextoBase(e?.isbn)].join('|');}
function mesclarEdicoesUnicas(destino, edicoes){
  const vistos=new Set(destino.map(edicaoAssinatura));
  (edicoes||[]).forEach(e=>{ const sig=edicaoAssinatura(e); if(sig && !vistos.has(sig)){ vistos.add(sig); destino.push(e); } });
}
function agruparResultadosPorObra(docs,q){
  const mapa=new Map();
  (docs||[]).forEach((doc,idx)=>{
    const key=chaveObra(doc)||`sem-chave-${idx}`;
    const eds=Array.isArray(doc?.edicoes)&&doc.edicoes.length ? doc.edicoes : [dadosEdicaoDeDoc(doc)];
    if(!mapa.has(key)) mapa.set(key,{...doc, key, indices:[], edicoes:[], edicoesEncontradas:0, scoreAgrupamento:scoreResultadoBusca(doc,q)});
    const obra=mapa.get(key);
    obra.indices.push(idx);
    obra.scoreAgrupamento=Math.max(obra.scoreAgrupamento,scoreResultadoBusca(doc,q));
    if(!obra.capa_url && doc?.capa_url) obra.capa_url=doc.capa_url;
    if(!obra.autor && doc?.autor) obra.autor=doc.autor;
    if(!obra.titulo && doc?.titulo) obra.titulo=doc.titulo;
    if(doc?.tem_pt) obra.tem_pt=true;
    mesclarEdicoesUnicas(obra.edicoes, eds);
    obra.edicoesEncontradas=obra.edicoes.length;
  });
  return [...mapa.values()].sort((a,b)=>(b.scoreAgrupamento-a.scoreAgrupamento)||(b.edicoesEncontradas-a.edicoesEncontradas));
}
function edicaoTemCapa(e){return !!(e?.capa_url);}
function scoreEdicao(e){
  const texto=normalizarTextoBase([e?.titulo_edicao,e?.editora,e?.idioma,e?.pais,e?.tradutor].filter(Boolean).join(' '));
  let score=0;
  if(texto.includes('portugues')||texto.includes('pt-br')||texto.includes('brasil')) score+=120;
  if(EDITORAS_BR.some(ed=>texto.includes(ed))) score+=75;
  if(edicaoTemCapa(e)) score+=35;
  ['editora','tradutor','isbn','ano','idioma'].forEach(c=>{ if(e?.[c]) score+=12; });
  if(TERMOS_NAO_OBRA.some(t=>texto.includes(t))) score-=90;
  if(!(texto.includes('portugues')||texto.includes('brasil')) && /(english|ingles|french|frances|spanish|espanhol|german|alemao)/.test(texto)) score-=35;
  return score;
}
function ordenarEdicoesObra(edicoes){return (edicoes||[]).map((e,i)=>({e,i,s:scoreEdicao(e)})).sort((a,b)=>(b.s-a.s)||(a.i-b.i)).map(x=>x.e);}

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
  ['brasil','companhia das letras','editora 34','penguin companhia','martin claret','antofagica','nova fronteira','jose olympio','record','l&pm','l pm','todavia'].forEach(t=>{ if(texto.includes(t)) score+=26; });
  const estrangeiro=['frances','ingles','espanhol','allemand','french','english','spanish'];
  if(!buscaPedeIdiomaEstrangeiro(q) && estrangeiro.some(t=>texto.includes(t))) score-=45;
  ['thesis','dissertation','study','studies','essays','critique','analysis','biography','lettres','correspondance','etudes','resumo','analise','ensaio','tese','dissertacao','seminario','biografia'].forEach(t=>{ if(texto.includes(t)) score-=55; });
  const titulo=normBusca(doc?.titulo);
  if(titulo && qn && (titulo===qn || titulo.includes(qn) || qn.includes(titulo))) score+=35;
  return score;
}
function ordenarResultadosBusca(docs,q){
  return (docs||[]).map((d,i)=>({d,i,s:scoreResultadoBusca(d,q)})).sort((a,b)=>(b.s-a.s)||(a.i-b.i)).map(x=>x.d);
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
  $('#resultados').innerHTML=`<div class="section-head"><h2 class="h-section">buscando</h2></div><div class="wall busca-skeleton">${Array.from({length:4},item).join('')}</div>`;
}
function manualCtaHTML(destaque=false){
  return destaque
    ? `<div class="manual-cta prominent"><p>Não encontramos uma edição boa para essa busca.</p><button class="link-manual" onclick="abrirManual()">Cadastrar livro manualmente</button></div>`
    : `<div class="manual-cta"><p>Não encontrou o livro?</p><button class="link-manual" onclick="abrirManual()">Cadastrar manualmente</button></div>`;
}
async function buscar(){
  const q=$('#q').value.trim(); if(q.length<2)return;
  $('#edicoes').innerHTML=''; $('#form').innerHTML='';
  renderBuscaSkeleton();
  mostrarBusca('resultados');
  let docs;
  try{ docs=await (await fetch('/api/buscar?q='+encodeURIComponent(q))).json(); }
  catch(e){ $('#resultados').innerHTML='<div class="empty">sem conexão. tenta de novo.</div>'; return; }
  resultadosArr=ordenarResultadosBusca(docs||[], q);
  obrasAgrupadas=agruparResultadosPorObra(resultadosArr, q);
  if(!obrasAgrupadas.length){
    $('#resultados').innerHTML=manualCtaHTML(true);
    return;
  }
  const melhorScore=Math.max(...resultadosArr.map(d=>scoreResultadoBusca(d,q)));
  const precisaDestaque=melhorScore<40;
  $('#resultados').innerHTML='<div class="section-head"><h2 class="h-section">resultados</h2></div><div class="wall">'+
    resultadosArr.map((d,i)=>`<div class="book" onclick="verObraResultado(${i})">
      ${coverHTML(d.titulo,d.autor,d.capa_url,d.tem_pt?'<span class="pt">PT</span>':'')}
      <div class="t">${esc(d.titulo)}</div>
      <div class="a">${esc(d.autor)}</div>
      <div class="yr">${d.ano||''}${d.tem_pt?' · <span class="br">ed. BR</span>':''}</div></div>`).join('')+'</div>'+manualCtaHTML(precisaDestaque);
}

/* edições */
function verObraResultado(i){
  const doc=resultadosArr[i];
  escolha=obrasAgrupadas.find(o=>o.indices?.includes(i))||doc;
  verEdicoes();
}
async function carregarSocialObra(){
  obraSocial={estatisticas:{leituras:0,criticas:0,media:null},edicoes:[],criticas:[],destaques:[],minha_leitura:null};
  if(!escolha) return obraSocial;
  const params=new URLSearchParams({work_key:escolha.work_key||'',titulo:escolha.titulo||'',autor:escolha.autor||''});
  try{ obraSocial=await (await fetch('/api/obra/social?'+params.toString())).json(); }catch(e){}
  return obraSocial;
}
async function verEdicoes(i){
  if(Number.isInteger(i)) escolha=obrasAgrupadas[i]||resultadosArr[i];
  if(!escolha){
    $('#edicoes').innerHTML='<div class="busca-back" onclick="mostrarBusca(\'resultados\')">‹ resultados</div><div class="empty">não encontrei essa obra. tente buscar de novo.</div>';
    mostrarBusca('edicoes');
    return;
  }
  $('#form').innerHTML='';
  // GB já trouxe as edições embutidas → zero chamada extra
  if(escolha.edicoes && escolha.edicoes.length){
    await carregarSocialObra(); edicoesAtual=ordenarEdicoesObra(escolha.edicoes); renderEdicoes(); mostrarBusca('edicoes'); return;
  }
  // busca por ISBN → edição única
  if(escolha.isbn_match && escolha.edicao_isbn){
    await carregarSocialObra(); edicoesAtual=ordenarEdicoesObra([escolha.edicao_isbn]); renderEdicoes(); mostrarBusca('edicoes'); return;
  }
  // fallback Open Library (obras sem edições embutidas)
  $('#edicoes').innerHTML='<div class="empty">carregando edições…</div>';
  mostrarBusca('edicoes');
  let eds;
  try{ eds=await (await fetch('/api/edicoes?work_key='+encodeURIComponent(escolha.work_key))).json(); }
  catch(e){ $('#edicoes').innerHTML='<div class="empty">não consegui carregar as edições.</div>'; return; }
  await carregarSocialObra(); edicoesAtual=ordenarEdicoesObra(eds||[]); renderEdicoes();
}
function fmtMedia(n){return n?Number(n).toLocaleString('pt-BR',{minimumFractionDigits:1,maximumFractionDigits:1})+' ★':'sem média';}
function edicaoSocial(e){
  const stats=(obraSocial?.edicoes||[]);
  const sig=normalizarTextoBase([e.editora,e.ano,e.isbn,e.idioma].filter(Boolean).join('|'));
  return stats.find(st=>st.edicao_id && e.edicao_id===st.edicao_id) || stats.find(st=>{
    const ed=st.edicao||{};
    const s2=normalizarTextoBase([ed.editora,ed.ano,ed.isbn,ed.idioma].filter(Boolean).join('|'));
    return sig && s2 && sig===s2;
  }) || null;
}
function criticasHTML(){
  const recentes=obraSocial?.criticas||[];
  const destaques=obraSocial?.destaques||[];
  if(!recentes.length) return `<section class="community-section"><div class="section-head"><h2 class="h-section">Críticas da comunidade</h2></div><div class="empty-rich work-empty"><div class="ei">✍️</div><p>Ainda não há críticas públicas para esta obra.<br>Seja a primeira pessoa a registrar uma leitura.</p><button class="btn-cta" onclick="registrarLeituraObra()">Registrar minha leitura</button></div></section>`;
  const card=c=>`<article class="review-card"><div class="review-top"><strong>@${esc(c.usuario||'leitor')}</strong><span>${c.nota?fmtMedia(c.nota):'sem nota'}</span></div><p>${esc(c.relato)}</p><div class="review-meta">${[c.edicao?.editora,c.edicao?.ano,c.data].filter(Boolean).map(esc).join(' · ')}</div></article>`;
  return `<section class="community-section"><div class="section-head"><h2 class="h-section">Críticas da comunidade</h2></div>${destaques.length?`<div class="label community-label">mais destacadas</div><div class="reviews-list featured">${destaques.map(card).join('')}</div>`:''}<div class="label community-label">recentes</div><div class="reviews-list">${recentes.map(card).join('')}</div></section>`;
}
function registrarLeituraObra(){
  if(edicoesAtual.length===1){ escolherEdicao(0); return; }
  toast('escolha uma edição para registrar sua leitura');
  document.querySelector('.editions')?.scrollIntoView({behavior:'smooth',block:'start'});
}
function verMinhaLeitura(){
  const idx=prateleira.findIndex(l=>l.leitura_id===obraSocial?.minha_leitura?.leitura_id);
  if(idx>=0) abrirCard(idx); else irPara('estante');
}
function renderEdicoes(){
  if(!edicoesAtual.length){$('#edicoes').innerHTML='<div class="busca-back" onclick="mostrarBusca(\'resultados\')">‹ resultados</div><div class="empty">sem edições listadas.</div>';return;}
  const st=obraSocial?.estatisticas||{};
  const media=st.media?fmtMedia(st.media):'sem média ainda';
  const leituras=st.leituras||0, criticas=st.criticas||0;
  const back=`<div class="busca-back" onclick="mostrarBusca('resultados')">‹ resultados</div>`;
  const cab=`<div class="work-head social-work-head">${coverHTML(escolha.titulo,escolha.autor,escolha.capa_url,'')}
    <div class="wmeta"><div class="label">obra</div><h2>${esc(escolha.titulo)}</h2>
      <div class="a">${esc(escolha.autor)}</div>
      <div class="community-score"><strong>${media}</strong><span>${leituras} ${leituras===1?'leitura':'leituras'} · ${criticas} ${criticas===1?'crítica':'críticas'}</span></div>
      <div class="work-actions"><button onclick="registrarLeituraObra()">Registrar leitura</button><button onclick="document.querySelector('.editions')?.scrollIntoView({behavior:'smooth'})">Ver edições</button><button onclick="abrirManual()">Cadastrar edição manualmente</button></div>
    </div></div>`;
  const minhas=obraSocial?.minha_leitura?`<button class="work-my-reading" onclick="verMinhaLeitura()">Ver minha leitura</button>`:`<button class="work-my-reading" onclick="registrarLeituraObra()">Registrar minha leitura</button>`;
  const maisLida=(obraSocial?.edicoes||[]).slice().sort((a,b)=>(b.leituras||0)-(a.leituras||0))[0];
  const cards=edicoesAtual.map((e,j)=>{
    const pt=normalizarTextoBase(e.idioma).includes('portugues')||normalizarTextoBase(e.pais).includes('brasil');
    const social=edicaoSocial(e);
    const isMaisLida=social&&maisLida&&social.edicao_id===maisLida.edicao_id;
    const grupo=isMaisLida?'mais lida':(pt?'português/Brasil':'outras edições');
    const tr=e.tradutor?`trad. <b>${esc(e.tradutor)}</b>`:`<span class="none">tradutor não informado</span>`;
    const stats=social?`<div class="edition-stats">${social.leituras||0} leituras${social.media?' · '+fmtMedia(social.media):''}</div>`:'';
    return `<li class="edition ${isMaisLida?'most-read':''}" onclick="escolherEdicao(${j})"><div class="edition-group">${grupo}</div>
      <div class="edition-cover">${coverHTML(e.titulo_edicao||escolha.titulo,escolha.autor,e.capa_url,'')}</div>
      <div class="edition-body"><div class="pub">${esc(e.editora||'editora não informada')}${pt?' · PT/BR':''}</div><div class="te">${esc(e.titulo_edicao||escolha.titulo)}</div><div class="tr">${tr}</div><div class="ln meta">${[e.ano,e.idioma,e.pais,e.isbn].filter(Boolean).map(esc).join('  ·  ')}</div>${stats}<button class="edition-action" type="button">Adicionar esta edição</button></div></li>`;
  }).join('');
  $('#edicoes').innerHTML=back+cab+`<section class="community-summary"><div><span>${media}</span><small>média da comunidade</small></div><div><span>${leituras}</span><small>leituras</small></div><div><span>${criticas}</span><small>críticas públicas</small></div></section>${minhas}<div class="section-head"><h2 class="h-section">Edições</h2></div><ul class="editions work-editions">${cards}</ul>`+criticasHTML();
}

/* registrar */
function escolherEdicao(j){
  edicaoSel=edicoesAtual[j]; notaSel=0;
  const titulo=edicaoSel.titulo_edicao||escolha.titulo;
  $('#form').innerHTML=`
    <div class="busca-back" onclick="mostrarBusca('edicoes')">‹ edições</div>
    <div class="section-head"><h2 class="h-section">registrar leitura</h2></div>
    <div class="card-form">
      <div style="font-family:'Fraunces',serif;font-style:italic;font-size:19px">${esc(titulo)}</div>
      <div class="meta" style="margin:4px 0 16px">${[edicaoSel.editora,edicaoSel.ano].filter(Boolean).map(esc).join(' · ')}</div>
      <div class="field"><label class="label">editora</label>
        <input type="text" id="f_editora" value="${esc(edicaoSel.editora)}" placeholder="editora" /></div>
      <div class="field"><label class="label">tradutor(a)</label>
        <input type="text" id="f_trad" value="${esc(edicaoSel.tradutor)}" placeholder="quem traduziu" /></div>
      <div class="row">
        <div class="field"><label class="label">ISBN</label>
          <input type="text" id="f_isbn" value="${esc(edicaoSel.isbn)}" placeholder="ISBN" /></div>
        <div class="field"><label class="label">idioma</label>
          <input type="text" id="f_idioma" value="${esc(edicaoSel.idioma)}" placeholder="ex: Português" /></div>
      </div>
      <div class="row">
        <div class="field"><label class="label">ano da edição</label>
          <input type="text" id="f_ano_edicao" value="${esc(edicaoSel.ano)}" placeholder="ex: 2019" /></div>
        <div class="field"><label class="label">URL da capa</label>
          <input type="text" id="f_capa_url" value="${esc(edicaoSel.capa_url)}" placeholder="https://..." /></div>
      </div>
      <div class="field"><label class="label">sua nota</label><div class="stars" id="f_stars"></div></div>
      <div class="row">
        <div class="field"><label class="label">status</label>
          <select id="f_status"><option>Lido</option><option>Lendo</option><option>Quero ler</option></select></div>
        <div class="field"><label class="label">quando</label>
          <input type="text" id="f_data" placeholder="ex: jun 2026" /></div>
      </div>
      <div class="field"><label class="label">relato</label>
        <textarea id="f_relato" maxlength="160" placeholder="o que ficou dessa leitura…"></textarea></div>
      <button class="btn-primary" onclick="salvar()">salvar na estante</button>
    </div>`;
  mostrarBusca('form');
  montarStars('f_stars',()=>notaSel,v=>notaSel=v);
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
    const t=document.createElement('span');
    t.className='stxt'; t.textContent=n?n.toLocaleString('pt-BR')+'★':'sem nota';
    w.appendChild(t);
  }
  paint();
}

async function salvar(){
  const body={
    work_key:escolha.work_key, titulo:escolha.titulo, autor:escolha.autor||'',
    idioma_original:escolha.idioma_original||'', ano_obra:escolha.ano||null,
    ol_edition_key:edicaoSel.ol_edition_key||null, editora:$('#f_editora').value.trim(),
    tradutor:$('#f_trad').value.trim(), isbn:$('#f_isbn').value.trim(), idioma:$('#f_idioma').value.trim(),
    ano_edicao:parseInt($('#f_ano_edicao').value,10)||null, capa_url:$('#f_capa_url').value.trim(),
    status:$('#f_status').value, nota:notaSel||null,
    relato:$('#f_relato').value.trim(), data:$('#f_data').value.trim()
  };
  try{ const r=await fetch('/api/prateleira',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}); if(!r.ok) throw new Error(await r.text()); }
  catch(e){ alert('não consegui salvar. tenta de novo.'); return; }
fecharModalParaNavegacao();

limparBusca(); $('#q').value=''; mostrarBusca('home',
{registrar:false});
marcarConviteLoginAposSalvar();
marcarLivroSalvo(body);
toast('salvo na sua estante');
await carregarPrateleira();
irPara('estante',{recarregar:false});
}
function abrirManual(){
  notaSel=0;
  if($('#secBuscar')?.style.display==='none') irPara('buscar',{resetBusca:false,registrar:false,scrollTop:false});
  const q=$('#q')?.value.trim()||'';
  $('#manual').innerHTML=`
    <div class="busca-back" onclick="history.back()">‹ voltar</div>
    <div class="section-head"><h2 class="h-section">cadastro manual</h2></div>
    <div class="card-form">
      <div class="form-block"><div class="label">livro</div>
        <div class="field"><label class="label">título da obra *</label><input type="text" id="m_titulo" value="${esc(q)}" /></div>
        <div class="field"><label class="label">autor *</label><input type="text" id="m_autor" /></div>
        <div class="row"><div class="field"><label class="label">ano da obra</label><input type="text" id="m_ano_obra" /></div>
        <div class="field"><label class="label">idioma original</label><input type="text" id="m_idioma_original" /></div></div>
      </div>
      <div class="form-block"><div class="label">edição</div>
        <div class="field"><label class="label">título da edição</label><input type="text" id="m_titulo_edicao" /></div>
        <div class="field"><label class="label">editora</label><input type="text" id="m_editora" /></div>
        <div class="field"><label class="label">tradutor(a)</label><input type="text" id="m_tradutor" /></div>
        <div class="row"><div class="field"><label class="label">ISBN</label><input type="text" id="m_isbn" /></div>
        <div class="field"><label class="label">idioma</label><input type="text" id="m_idioma" /></div></div>
        <div class="row"><div class="field"><label class="label">ano da edição</label><input type="text" id="m_ano_edicao" /></div>
        <div class="field"><label class="label">URL da capa</label><input type="text" id="m_capa_url" /></div></div>
      </div>
      <div class="form-block"><div class="label">sua leitura</div>
        <div class="row"><div class="field"><label class="label">status</label><select id="m_status"><option>Lido</option><option>Lendo</option><option>Quero ler</option></select></div>
        <div class="field"><label class="label">data</label><input type="text" id="m_data" placeholder="ex: jun 2026" /></div></div>
        <div class="field"><label class="label">nota</label><div class="stars" id="m_stars"></div></div>
        <div class="field"><label class="label">relato</label><textarea id="m_relato" maxlength="160"></textarea></div>
      </div>
      <button class="btn-primary" onclick="salvarManual()">salvar na estante</button>
    </div>`;
  mostrarBusca('manual');
  montarStars('m_stars',()=>notaSel,v=>notaSel=v);
}

async function salvarManual(){
  const titulo=$('#m_titulo').value.trim(), autor=$('#m_autor').value.trim();
  if(!titulo||!autor){ alert('título e autor são obrigatórios.'); return; }
  const body={
    titulo, autor, ano_obra:parseInt($('#m_ano_obra').value,10)||null, idioma_original:$('#m_idioma_original').value.trim(),
    titulo_edicao:$('#m_titulo_edicao').value.trim(), editora:$('#m_editora').value.trim(), tradutor:$('#m_tradutor').value.trim(),
    isbn:$('#m_isbn').value.trim(), idioma:$('#m_idioma').value.trim(), ano_edicao:parseInt($('#m_ano_edicao').value,10)||null,
    capa_url:$('#m_capa_url').value.trim(), status:$('#m_status').value, nota:notaSel||null, relato:$('#m_relato').value.trim(), data:$('#m_data').value.trim()
  };
  try{ const r=await fetch('/api/manual',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}); if(!r.ok) throw new Error(await r.text()); }
  catch(e){ alert('não consegui salvar. tenta de novo.'); return; }
  fecharModalParaNavegacao(); limparBusca(); $('#q').value=''; mostrarBusca('home',{registrar:false});
  marcarConviteLoginAposSalvar(); marcarLivroSalvo(body); toast('salvo na sua estante'); await carregarPrateleira(); irPara('estante',{recarregar:false});
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
    <div class="shelf-filters" aria-label="filtrar estante por status">${filtros.map(f=>
      `<button class="shelf-pill ${filtroEstante===f?'active':''}" onclick="mudarFiltroEstante('${f}')">${esc(f)}</button>`
    ).join('')}</div>
    <div class="shelf-view" aria-label="visualização da estante">
      <button class="shelf-view-btn ${visualizacaoEstante==='grade'?'active':''}" onclick="mudarVisualizacaoEstante('grade')">grade</button>
      <button class="shelf-view-btn ${visualizacaoEstante==='lista'?'active':''}" onclick="mudarVisualizacaoEstante('lista')">lista</button>
    </div>
  </div>`;
}
function metaListaEstante(l){
  return [l.editora?`ed. ${esc(l.editora)}`:'',l.tradutor?`trad. ${esc(l.tradutor)}`:'',l.isbn?`ISBN ${esc(l.isbn)}`:''].filter(Boolean).join(' · ');
}
function resumoEstante(){
  const total=prateleira.length;
  const lidos=prateleira.filter(l=>l.status==='Lido').length;
  const lendo=prateleira.filter(l=>l.status==='Lendo').length;
  const quero=prateleira.filter(l=>l.status==='Quero ler').length;
  return `${total} ${total===1?'livro':'livros'} · ${lidos} lidos · ${lendo} lendo · ${quero} quero ler`;
}
function blocoLendoEstante(){
  const l=prateleira.find(x=>x.status==='Lendo');
  if(!l) return '';
  return `<section class="shelf-now"><div class="label">lendo agora</div>${lendoAgoraCard(l,prateleira.indexOf(l),true)}</section>`;
}
function renderPrateleira(){
  if(!prateleira.length){
    $('#prateleira').innerHTML=`<div class="empty-rich"><div class="ei">📚</div>
      <p>sua estante ainda está vazia.<br>busque um livro, escolha a edição e registre sua primeira leitura.</p>
      <button class="btn-cta" onclick="irPara('buscar')">buscar meu primeiro livro →</button></div>`;
    return;
  }
  const itens=prateleira.map((l,i)=>({l,i})).filter(({l})=>filtroEstante==='Todos'||l.status===filtroEstante);
  const vazio=`<div class="empty shelf-empty">nenhum livro em “${esc(filtroEstante)}” por enquanto.</div>`;
  const corpo=visualizacaoEstante==='lista'
    ? `<ul class="shelf-list">${itens.map(({l,i})=>{
        const cap=coverHTML(l.titulo,l.autor,l.capa_url,'').replace('class="cover','class="shelf-cover');
        const statusNota=[l.status,l.nota?`${estrelasStr(l.nota)} ${l.nota.toLocaleString('pt-BR')}`:'sem nota'].filter(Boolean).join(' · ');
        const dataAno=[l.data,l.ano_edicao||l.ano_obra].filter(Boolean).join(' · ');
        return `<li class="shelf-row ${livroEstaDestacado(l)?'saved-highlight':''}" onclick="abrirCard(${i})">${cap}
          <div class="shelf-row-body">
            <div class="shelf-row-title">${esc(l.titulo)}</div>
            <div class="shelf-row-author">${esc(l.autor)}</div>
            <div class="shelf-row-status">${esc(statusNota)}</div>
            ${metaListaEstante(l)?`<div class="shelf-row-meta">${metaListaEstante(l)}</div>`:''}
            ${dataAno?`<div class="shelf-row-date">${esc(dataAno)}</div>`:''}
          </div></li>`;
      }).join('')}</ul>`
    : `<div class="wall">${itens.map(({l,i})=>`
        <div class="book ${livroEstaDestacado(l)?'saved-highlight':''}" onclick="abrirCard(${i})">
          ${coverHTML(l.titulo,l.autor,l.capa_url,l.nota?`<span class="stars-overlay"><span>${estrelasStr(l.nota)}</span><span>${l.nota.toLocaleString('pt-BR')}</span></span>`:'')}
          <div class="t">${esc(l.titulo)}</div>
          <div class="a">${esc(l.autor)}</div>
          ${l.tradutor?`<div class="e">trad. ${esc(l.tradutor)}</div>`:''}
        </div>`).join('')}</div>`;
  $('#prateleira').innerHTML=`<p class="shelf-summary">${resumoEstante()}</p>`+conviteLoginHTML()+blocoLendoEstante()+controlesEstante()+(itens.length?corpo:vazio);
}
async function carregarPrateleira(){
  try{ prateleira=await (await fetch('/api/prateleira')).json(); }catch(e){ return; }
  renderLendoAgora();
  renderPrateleira();
}

/* diário — linha do tempo */
function renderDiario(){
  if(!prateleira.length){
    $('#diario').innerHTML=`<div class="empty-rich"><div class="ei">📖</div>
      <p>seu diário começa quando você registra uma leitura.<br>adicione nota, status ou relato para lembrar do que ficou.</p>
      <button class="btn-cta" onclick="irPara('buscar')">registrar leitura →</button></div>`;
    return;
  }
  $('#diario').innerHTML='<ul class="diary">'+prateleira.map((l,i)=>{
    const cap=coverHTML(l.titulo,l.autor,l.capa_url,'').replace('class="cover','class="dcover');
    return `<li onclick="abrirCard(${i})">
      ${cap}
      <div class="dbody">
        <div class="dmeta"><span>${esc(l.status||'Lido')}</span>${l.autor?` · ${esc(l.autor)}`:''}</div>
        <div class="dtop"><span class="dt">${esc(l.titulo)}</span><span class="dwhen">${esc(l.data||'')}</span></div>
        ${l.nota?`<div class="dstars">${estrelasStr(l.nota)} ${l.nota.toLocaleString('pt-BR')}</div>`:''}
        ${l.tradutor?`<div class="dtr">trad. ${esc(l.tradutor)}</div>`:''}
        ${l.relato?`<div class="drelato">${esc(l.relato)}</div>`:''}
      </div></li>`;
  }).join('')+'</ul>';
}

/* perfil */
function renderPerfil(){
  const url=location.origin+'/u/'+meuHandle;
  const n=prateleira.length;
  const logado=!!minhaConta.logado;
  const nome=(minhaConta.nome||'').trim();
  const email=(minhaConta.email||'').trim();
  const lidos=prateleira.filter(l=>l.status==='Lido').length, lendo=prateleira.filter(l=>l.status==='Lendo').length, quero=prateleira.filter(l=>l.status==='Quero ler').length;
  const inicial=(nome||meuHandle||'L').trim().charAt(0).toUpperCase();
  const contaHTML=logado
    ? `<div class="account-box connected">
        <div class="label">conta</div>
        <p>sua estante está vinculada ao Google</p>
        ${nome?`<div class="account-line">${esc(nome)}</div>`:''}
        ${email?`<div class="account-line muted">${esc(email)}</div>`:''}
        <a class="account-logout" href="/api/auth/logout">sair</a>
      </div>`
    : `<div class="account-box">
        <div class="label">conta</div>
        <p>você está usando a Lombada sem conta</p>
        <p class="muted">entre com Google para guardar sua estante e recuperá-la depois</p>
        <a class="pbtn solid" href="/api/auth/google/login">entrar com Google</a>
      </div>`;
  $('#perfil').innerHTML=`
    <div class="pcard">
      <div class="profile-avatar">${esc(inicial)}</div>
      <div class="phandle">${nome?esc(nome):'Leitor Lombada'}</div>
      <div class="pcount">@${esc(meuHandle)} · ${n} ${n===1?'livro':'livros'}</div>
      <div class="profile-metrics"><div><strong>${lidos}</strong><span>lidos</span></div><div><strong>${lendo}</strong><span>lendo</span></div><div><strong>${quero}</strong><span>quero ler</span></div></div>
      ${contaHTML}
      <div class="account-box theme-box">
        <div class="label">aparência</div>
        <p>escolha como a Lombada aparece neste dispositivo</p>
        <div class="theme-options" role="radiogroup" aria-label="tema">
          <label class="theme-option"><input type="radio" name="themeChoice" value="light" onchange="definirTema(this.value)" ${document.body.getAttribute('data-theme')==='light'?'checked':''}><span>Claro</span></label>
          <label class="theme-option"><input type="radio" name="themeChoice" value="dark" onchange="definirTema(this.value)" ${document.body.getAttribute('data-theme')==='dark'?'checked':''}><span>Escuro</span></label>
        </div>
      </div>
      <div class="account-box library-box">
        <div class="label">biblioteca</div>
        <p>adicione uma obra que não apareceu na busca</p>
        <button class="pbtn" onclick="abrirManual()">Cadastrar livro manualmente</button>
      </div>
      <div class="pactions">
        <button class="pbtn solid" onclick="compartilharEstante()">compartilhar estante</button>
        <a class="pbtn" href="${esc(url)}" target="_blank">abrir estante pública</a>
      </div>
      <div class="plink">${esc(url)}</div>
    </div>`;
}

async function compartilharEstante(){
  const url=location.origin+'/u/'+meuHandle;
  if(navigator.share){ try{ await navigator.share({title:'Minha estante na Lombada',url}); return; }catch(e){} }
  try{ await navigator.clipboard.writeText(url); alert('link copiado:\n'+url); }
  catch(e){ prompt('copie o link da sua estante:',url); }
}

/* ---------- card / modal ---------- */

function renderDetalheLivro(l){
  const campos=[
    ['editora',l.editora],
    ['tradutor',l.tradutor],
    ['ano',l.ano_edicao||l.ano],
    ['idioma',l.idioma],
    ['ISBN',l.isbn]
  ].filter(([,v])=>v);
  const nota=Number(l.nota)||0;
  const notaTxt=nota ? `<span class="detail-rating-number">${nota.toLocaleString('pt-BR')}</span>` : '<span class="detail-muted">sem nota</span>';
  const relato=l.relato ? `<blockquote>${esc(l.relato)}</blockquote>` : '<p class="detail-empty">sem relato ainda</p>';
  const dados=campos.length
    ? `<dl class="edition-data">${campos.map(([k,v])=>`<div><dt>${esc(k)}</dt><dd>${esc(v)}</dd></div>`).join('')}</dl>${campos.length<3?'<p class="detail-empty edition-note">dados da edição incompletos</p>':''}`
    : '<p class="detail-empty edition-note">dados da edição incompletos</p>';
  $('#bookDetail').innerHTML=`
    <section class="detail-head">
      <div class="detail-cover">${coverHTML(l.titulo,l.autor,l.capa_url,'')}</div>
      <div class="detail-titleblock">
        <div class="label">detalhe do livro</div>
        <h2>${esc(l.titulo)}</h2>
        <p class="detail-author">${esc(l.autor)}</p>
        <span class="status-tag">${esc(l.status||'Lido')}</span>
      </div>
    </section>
    <section class="detail-section detail-rating">
      <div class="detail-stars" aria-label="nota">${estrelasStr(nota)}</div>
      ${notaTxt}
    </section>
    <section class="detail-section">
      <div class="label">relato</div>
      <div class="detail-quote">${relato}</div>
    </section>
    <section class="detail-section">
      <div class="label">dados da edição</div>
      ${dados}
    </section>`;
}
async function abrirCard(i,opcoes={}){
  const registrar=opcoes.registrar ?? true;
  cardAtual=prateleira[i];
  $('#editPanel').style.display='none';
  renderDetalheLivro(cardAtual);
  $('#modal').classList.add('open');
 if(registrar && !restaurandoHistorico){
  const estadoModal={...estadoNav(navAtual.aba,navAtual.busca,true),card:i};
  if(history.state && history.state.lombada && history.state.modal){
    history.replaceState(estadoModal,'');
  }else{
    history.pushState(estadoModal,'');
  }
}
  try{ await document.fonts.ready; }catch(e){}
  drawCard(cardAtual);
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

function drawCoverArt(ctx,l,x,y,w,h,variacao=0){
  const d=capaArteDados(l.titulo,l.autor,variacao);
  ctx.fillStyle='rgba(26,23,20,.18)';ctx.fillRect(x+16,y+20,w,h);
  ctx.save();ctx.beginPath();ctx.rect(x,y,w,h);ctx.clip();
  ctx.fillStyle=d.layout==='classic'?d.papel:d.tinta;ctx.fillRect(x,y,w,h);
  ctx.fillStyle=d.layout==='split'?d.tinta:(d.layout==='block'?d.tinta2:d.tinta);
  if(d.layout==='split')ctx.fillRect(x,y,w*.30,h);
  else if(d.layout==='classic'){ctx.strokeStyle=d.tinta;ctx.lineWidth=10;ctx.strokeRect(x+26,y+26,w-52,h-52);ctx.fillRect(x+w*.22,y+88,w*.56,5);}
  else ctx.fillRect(x+70,y+86,w*.62,18);
  const dark=d.layout!=='block';
  ctx.textAlign=d.layout==='classic'?'center':'left';ctx.textBaseline='alphabetic';
  ctx.fillStyle=dark?d.tinta:d.papel;
  if(l.autor){ctx.font="700 28px 'Space Mono', monospace";ctx.letterSpacing='2px';
    const ax=d.layout==='classic'?x+w/2:x+(d.layout==='split'?w*.36:70);
    ctx.fillText((l.autor||'').toUpperCase().slice(0,34),ax,y+170);
    ctx.letterSpacing='0px';}
  ctx.font=`700 italic ${d.layout==='block'?72:68}px Fraunces, serif`;
  const tx=d.layout==='classic'?x+w/2:x+(d.layout==='split'?w*.36:70);
  const maxW=d.layout==='split'?w*.56:w-140;
  if(d.layout==='classic')wrapCenter(ctx,l.titulo||'',x+w/2,y+h/2,maxW,78,5);
  else wrapLeft(ctx,l.titulo||'',tx,y+h*.46,maxW,78,5);
  ctx.font="400 24px 'Space Mono', monospace";ctx.fillStyle=dark?'rgba(26,23,20,.66)':'rgba(241,230,210,.72)';
  ctx.textAlign=d.layout==='classic'?'center':'left';
  ctx.fillText('lombada · edição de leitor',d.layout==='classic'?x+w/2:tx,y+h-74);
  ctx.restore();
  ctx.strokeStyle='rgba(26,23,20,.25)';ctx.lineWidth=2;ctx.strokeRect(x,y,w,h);
}

function drawCard(l){
  const cv=$('#cardCanvas'),ctx=cv.getContext('2d'),W=1080,H=1920;
  ctx.clearRect(0,0,W,H);
  ctx.fillStyle='#ECE4D4';ctx.fillRect(0,0,W,H);
  const cx=110,cy=120,cw=W-220,ch=1120;
  const txt=()=>{
    let y=cy+ch+118;ctx.textAlign='left';
    ctx.fillStyle='#3A322A';ctx.font="500 italic 80px Fraunces, serif";
    y=wrapLeft(ctx,l.titulo||'',110,y,W-220,88,2);
    y+=68;ctx.fillStyle='#6F6655';ctx.font="italic 46px Spectral, serif";
    ctx.fillText(l.autor||'',110,y);
    y+=86;drawStars(ctx,110,y,l.nota||0,44,20,'#A8842F');
    if(l.relato){y+=110;ctx.fillStyle='#3A322A';ctx.font="italic 44px Spectral, serif";
      y=wrapLeft(ctx,'"'+l.relato+'"',110,y,W-220,56,3);}
    const yc=H-160;ctx.strokeStyle='rgba(26,23,20,.25)';ctx.lineWidth=1.5;
    ctx.beginPath();ctx.moveTo(110,yc-46);ctx.lineTo(W-110,yc-46);ctx.stroke();
    ctx.fillStyle='#6F6655';ctx.font="400 28px 'Space Mono', monospace";
    const col=[l.tradutor?'trad. '+l.tradutor:null,l.editora||null,l.ano||null].filter(Boolean).join('   ·   ');
    ctx.fillText(col,110,yc);
    ctx.fillText('@'+(meuHandle||''),110,yc+44);
    ctx.fillStyle='#A8842F';ctx.font="600 italic 40px Fraunces, serif";
    ctx.fillText('lombada.',110,yc+98);
  };
  const fb=()=>{drawCoverArt(ctx,l,cx,cy,cw,ch);ctx.textAlign='left';txt();};
  if(l.capa_url){
    const im=new Image();im.crossOrigin='anonymous';
    im.onload=()=>{ if(im.naturalWidth<5){fb();return;}
      ctx.fillStyle='rgba(26,23,20,.20)';ctx.fillRect(cx+16,cy+20,cw,ch);
      ctx.save();ctx.beginPath();ctx.rect(cx,cy,cw,ch);ctx.clip();
      const ir=im.width/im.height,wr=cw/ch;let dw,dh,dx,dy;
      if(ir>wr){dh=ch;dw=ch*ir;dx=cx-(dw-cw)/2;dy=cy;}else{dw=cw;dh=cw/ir;dx=cx;dy=cy-(dh-ch)/2;}
      ctx.drawImage(im,dx,dy,dw,dh);ctx.restore();
      ctx.strokeStyle='rgba(26,23,20,.25)';ctx.lineWidth=2;ctx.strokeRect(cx,cy,cw,ch);
      txt();
    };
    im.onerror=fb;
    im.src=capaProxy(l.capa_url);
  } else { fb(); }
}

async function compartilharCard(){
  const cv=$('#cardCanvas');
  cv.toBlob(async blob=>{
    if(!blob){alert('não consegui gerar o card.');return;}
    const file=new File([blob],'lombada.png',{type:'image/png'});
    if(navigator.canShare && navigator.canShare({files:[file]})){
      try{ await navigator.share({files:[file],text:'minha leitura na Lombada'}); return; }catch(e){}
    }
    const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='lombada.png';a.click();
  },'image/png');
}

/* editar / remover */
function abrirEditar(){
  const l=cardAtual; notaEdit=l.nota||0;
  const p=$('#editPanel');
  p.innerHTML=`
    <h3>editar "${esc(l.titulo)}"</h3>
    <div class="field"><label class="label">nota</label><div class="stars" id="e_stars"></div></div>
    <div class="row">
      <div class="field"><label class="label">status</label>
        <select id="e_status">
          <option${l.status==='Lido'?' selected':''}>Lido</option>
          <option${l.status==='Lendo'?' selected':''}>Lendo</option>
          <option${l.status==='Quero ler'?' selected':''}>Quero ler</option>
        </select></div>
      <div class="field"><label class="label">quando</label>
        <input type="text" id="e_data" value="${esc(l.data)}" placeholder="ex: jun 2026" /></div>
    </div>
    <div class="field"><label class="label">relato</label>
      <textarea id="e_relato" maxlength="160">${esc(l.relato)}</textarea></div>
    <button class="btn-primary" onclick="salvarEdicao()">salvar alterações</button>`;
  p.style.display='';
  montarStars('e_stars',()=>notaEdit,v=>notaEdit=v);
  p.scrollIntoView({behavior:'smooth',block:'center'});
}
async function salvarEdicao(){
  const body={ status:$('#e_status').value, nota:notaEdit||null,
    relato:$('#e_relato').value.trim(), data:$('#e_data').value.trim() };
  try{ await fetch('/api/prateleira/'+cardAtual.leitura_id,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}); }
  catch(e){ alert('não consegui salvar a edição.'); return; }
  fecharModalParaNavegacao(); await carregarPrateleira();
}
async function removerLeitura(){
  if(!confirm('Remover "'+(cardAtual.titulo||'')+'" da estante?'))return;
  try{ await fetch('/api/prateleira/'+cardAtual.leitura_id,{method:'DELETE'}); }
  catch(e){ alert('não consegui remover.'); return; }
  fecharModalParaNavegacao(); await carregarPrateleira();
}

/* init */
async function init(){
  registrarHistorico('buscar','home',true);
  tratarMensagemConta();
  renderChips();
  try{
    const me=await (await fetch('/api/eu')).json();
    minhaConta=me||{logado:false,provedor:'anonimo'};
    meuHandle=me.handle||'';
    $('#meuhandle').textContent='@'+meuHandle;
    $('#crumb').classList.add('visible');
  }catch(e){}
  await carregarPrateleira();
}
init();
