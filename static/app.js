const $ = s => document.querySelector(s);
const esc = s => (s||'').toString().replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const capaProxy = u => u ? '/api/capa?url='+encodeURIComponent(u) : '';

const SUGESTOES = ['Crime e Castigo','A Montanha Mágica','Ulisses','Orlando','O Aleph','O Morro dos Ventos Uivantes'];

let meuHandle='', escolha=null, edicaoSel=null, notaSel=0;
let resultadosArr=[], edicoesAtual=[], prateleira=[], cardAtual=null, notaEdit=0;
let navAtual={aba:'buscar',busca:'home'};
let restaurandoHistorico=false;

function estrelasStr(n){n=n||0;let o='';for(let i=1;i<=5;i++)o+=(i<=n?'★':(i-0.5===n?'⯪':'☆'));return o;}
function hue(t){let h=0;for(let i=0;i<(t||'?').length;i++)h=(h*31+t.charCodeAt(i))%360;return h;}

function coverHTML(titulo,autor,capa,extra){
  const h=hue(titulo);
  if(capa){
    return `<div class="cover">
      <img src="${esc(capa)}" alt="" loading="lazy"
        onerror="this.parentElement.classList.add('fallback');this.parentElement.innerHTML='<div class=ft>'+this.alt+'</div>';this.parentElement.style.background='hsl(${h},22%,72%)'">
      ${extra||''}</div>`;
  }
  return `<div class="cover fallback" style="background:hsl(${h},22%,72%)"><div class="ft">${esc(titulo)}</div>${extra||''}</div>`;
}

/* navegação entre abas */
function estadoNav(aba=navAtual.aba,busca=navAtual.busca){
  return {lombada:true,aba,busca};
}
function registrarHistorico(aba,busca,replace=false){
  navAtual={aba,busca};
  if(restaurandoHistorico)return;
  const estado=estadoNav(aba,busca);
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
  if(aba==='estante') carregarPrateleira();
  if(aba==='diario') renderDiario();
  if(aba==='perfil') renderPerfil();
  navAtual={aba,busca:aba==='buscar'?navAtual.busca:'home'};
  if(registrar) registrarHistorico(navAtual.aba,navAtual.busca);
  window.scrollTo({top:0,behavior:'smooth'});
}

/* pilha de telas DENTRO da aba buscar: home → resultados → edicoes → form.
   mostra exatamente uma de cada vez (mata o "carrega embaixo"). */
function mostrarBusca(tela,opcoes={}){
  const registrar=opcoes.registrar ?? tela!=='home';
  const telas={home:'#homeFeed',resultados:'#resultados',edicoes:'#edicoes',form:'#form'};
  for(const k in telas) $(telas[k]).style.display = (k===tela)?'':'none';
  navAtual={aba:'buscar',busca:tela};
  if(registrar) registrarHistorico('buscar',tela);
  window.scrollTo({top:0,behavior:'smooth'});
}
function aplicarHistorico(estado){
  const proximo=estado && estado.lombada ? estado : estadoNav('buscar','home');
  restaurandoHistorico=true;
  irPara(proximo.aba,{registrar:false,resetBusca:false});
  if(proximo.aba==='buscar') mostrarBusca(proximo.busca||'home',{registrar:false});
  navAtual={aba:proximo.aba,busca:proximo.busca||'home'};
  restaurandoHistorico=false;
}
window.onpopstate=e=>aplicarHistorico(e.state);


/* mostra/esconde feed da home conforme há busca */
function onQInput(){
  const v=$('#q').value.trim();
  if(!v){ limparBusca(); mostrarBusca('home',{registrar:false}); registrarHistorico('buscar','home'); }
}
function limparBusca(){ $('#resultados').innerHTML='';$('#edicoes').innerHTML='';$('#form').innerHTML=''; }

/* feed da home — obras populares como mini estante (lista curada) */
function renderChips(){
  $('#populares').innerHTML = SUGESTOES.map(s=>
    `<div class="book" onclick="buscarTermo('${esc(s).replace(/'/g,"\\'")}')">
       ${coverHTML(s,'','')}
       <div class="t">${esc(s)}</div></div>`).join('');
}
function renderLendoAgora(){
  const lendo = prateleira.filter(l=>l.status==='Lendo');
  const box=$('#lendoAgora');
  if(!lendo.length){ box.innerHTML=''; return; }
  box.innerHTML=`<div class="section-head"><div class="label">lendo agora</div><span class="more" onclick="irPara('estante')">ver estante →</span></div>
    <div class="rail">`+lendo.map((l,i)=>{
      const idx=prateleira.indexOf(l);
      const ov=l.nota?`<span class="stars-overlay"><span>${estrelasStr(l.nota)}</span><span>${l.nota.toLocaleString('pt-BR')}</span></span>`:'';
      return `<div class="book" onclick="abrirCard(${idx})">${coverHTML(l.titulo,l.autor,l.capa_url,ov)}
        <div class="t">${esc(l.titulo)}</div><div class="a">${esc(l.autor)}</div></div>`;
    }).join('')+`</div>`;
}

/* busca */
function buscarTermo(t){$('#q').value=t;buscar();}
async function buscar(){
  const q=$('#q').value.trim(); if(q.length<2)return;
  $('#edicoes').innerHTML=''; $('#form').innerHTML='';
  $('#resultados').innerHTML='<div class="empty">buscando…</div>';
  mostrarBusca('resultados');
  let docs;
  try{ docs=await (await fetch('/api/buscar?q='+encodeURIComponent(q))).json(); }
  catch(e){ $('#resultados').innerHTML='<div class="empty">sem conexão. tenta de novo.</div>'; return; }
  resultadosArr=docs||[];
  if(!resultadosArr.length){$('#resultados').innerHTML='<div class="empty">nada encontrado pra "'+esc(q)+'".</div>';return;}
  $('#resultados').innerHTML='<div class="section-head"><h2 class="h-section">resultados</h2></div><div class="wall">'+
    resultadosArr.map((d,i)=>`<div class="book" onclick="verEdicoes(${i})">
      ${coverHTML(d.titulo,d.autor,d.capa_url,d.tem_pt?'<span class="pt">PT</span>':'')}
      <div class="t">${esc(d.titulo)}</div>
      <div class="a">${esc(d.autor)}</div>
      <div class="yr">${d.ano||''}${d.tem_pt?' · <span class="br">ed. BR</span>':''}</div></div>`).join('')+'</div>';
}

/* edições */
async function verEdicoes(i){
  escolha=resultadosArr[i];
  $('#form').innerHTML='';
  // GB já trouxe as edições embutidas → zero chamada extra
  if(escolha.edicoes && escolha.edicoes.length){
    edicoesAtual=escolha.edicoes; renderEdicoes(); mostrarBusca('edicoes'); return;
  }
  // busca por ISBN → edição única
  if(escolha.isbn_match && escolha.edicao_isbn){
    edicoesAtual=[escolha.edicao_isbn]; renderEdicoes(); mostrarBusca('edicoes'); return;
  }
  // fallback Open Library (obras sem edições embutidas)
  $('#edicoes').innerHTML='<div class="empty">carregando edições…</div>';
  mostrarBusca('edicoes');
  let eds;
  try{ eds=await (await fetch('/api/edicoes?work_key='+encodeURIComponent(escolha.work_key))).json(); }
  catch(e){ $('#edicoes').innerHTML='<div class="empty">não consegui carregar as edições.</div>'; return; }
  edicoesAtual=eds||[]; renderEdicoes();
}
function renderEdicoes(){
  if(!edicoesAtual.length){$('#edicoes').innerHTML='<div class="busca-back" onclick="mostrarBusca(\'resultados\')">‹ resultados</div><div class="empty">sem edições listadas.</div>';return;}
  const back=`<div class="busca-back" onclick="mostrarBusca('resultados')">‹ resultados</div>`;
  const cab=`<div class="work-head">${coverHTML(escolha.titulo,escolha.autor,escolha.capa_url,'')}
    <div class="wmeta"><div class="label">obra</div><h2>${esc(escolha.titulo)}</h2>
      <div class="a">${esc(escolha.autor)}</div>
      <div class="meta y">${[escolha.ano?'orig. '+escolha.ano:'',edicoesAtual.length+(edicoesAtual.length===1?' edição':' edições')].filter(Boolean).join(' · ')}</div>
    </div></div>`;
  $('#edicoes').innerHTML=back+cab+'<div class="label" style="margin-bottom:6px">escolha sua edição</div><ul class="editions">'+
    edicoesAtual.map((e,j)=>{
      const pt=e.idioma==='Português';
      const tr=e.tradutor?`trad. <b>${esc(e.tradutor)}</b>`:`<span class="none">tradutor não informado</span>`;
      return `<li class="edition" onclick="escolherEdicao(${j})">
        <div class="pub">${esc(e.editora||'editora não informada')}${pt?' · PT':''}</div>
        <div class="te">${esc(e.titulo_edicao||escolha.titulo)}</div>
        <div class="tr">${tr}</div>
        <div class="ln meta">${[e.ano,e.idioma,e.isbn].filter(Boolean).map(esc).join('  ·  ')}</div>
      </li>`;
    }).join('')+'</ul>';
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
      <div class="field"><label class="label">tradutor(a)</label>
        <input type="text" id="f_trad" value="${esc(edicaoSel.tradutor)}" placeholder="quem traduziu" /></div>
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
    ol_edition_key:edicaoSel.ol_edition_key||null, editora:edicaoSel.editora||'',
    tradutor:$('#f_trad').value.trim(), isbn:edicaoSel.isbn||'', idioma:edicaoSel.idioma||'',
    ano_edicao:edicaoSel.ano||null, capa_url:edicaoSel.capa_url||'',
    status:$('#f_status').value, nota:notaSel||null,
    relato:$('#f_relato').value.trim(), data:$('#f_data').value.trim()
  };
  try{ await fetch('/api/prateleira',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}); }
  catch(e){ alert('não consegui salvar. tenta de novo.'); return; }
  limparBusca(); $('#q').value=''; mostrarBusca('home',{registrar:false});
  await carregarPrateleira();
  irPara('estante');
}

/* estante */
async function carregarPrateleira(){
  try{ prateleira=await (await fetch('/api/prateleira')).json(); }catch(e){ return; }
  renderLendoAgora();
  if(!prateleira.length){
    $('#prateleira').innerHTML=`<div class="empty-rich"><div class="ei">📚</div>
      <p>sua estante está vazia.<br>busca um livro pra começar.</p>
      <button class="btn-cta" onclick="irPara('buscar')">buscar livros →</button></div>`;
    return;
  }
  $('#prateleira').innerHTML='<div class="wall">'+prateleira.map((l,i)=>`
    <div class="book" onclick="abrirCard(${i})">
      ${coverHTML(l.titulo,l.autor,l.capa_url,l.nota?`<span class="stars-overlay"><span>${estrelasStr(l.nota)}</span><span>${l.nota.toLocaleString('pt-BR')}</span></span>`:'')}
      <div class="t">${esc(l.titulo)}</div>
      <div class="a">${esc(l.autor)}</div>
      ${l.tradutor?`<div class="e">trad. ${esc(l.tradutor)}</div>`:''}
    </div>`).join('')+'</div>';
}

/* diário — linha do tempo */
function renderDiario(){
  if(!prateleira.length){
    $('#diario').innerHTML=`<div class="empty-rich"><div class="ei">📖</div>
      <p>nenhuma leitura registrada ainda.</p>
      <button class="btn-cta" onclick="irPara('buscar')">registrar leitura →</button></div>`;
    return;
  }
  $('#diario').innerHTML='<ul class="diary">'+prateleira.map((l,i)=>{
    const h=hue(l.titulo);
    const cap=l.capa_url
      ? `<div class="dcover"><img src="${esc(capaProxy(l.capa_url))}" alt="" onerror="this.parentElement.classList.add('fallback');this.parentElement.innerHTML='<div class=ft>'+'${esc(l.titulo).replace(/'/g,'')}'+'</div>';this.parentElement.style.background='hsl(${h},22%,72%)'"></div>`
      : `<div class="dcover fallback" style="background:hsl(${h},22%,72%)"><div class="ft">${esc(l.titulo)}</div></div>`;
    return `<li onclick="abrirCard(${i})">
      ${cap}
      <div class="dbody">
        <div class="dtop"><span class="dt">${esc(l.titulo)}</span><span class="dwhen">${esc(l.data||l.status||'')}</span></div>
        ${l.nota?`<div class="dstars">${estrelasStr(l.nota)} ${l.nota.toLocaleString('pt-BR')}</div>`:''}
        ${l.tradutor?`<div class="dtr">trad. ${esc(l.tradutor)}</div>`:''}
        ${l.relato?`<div class="drelato">"${esc(l.relato)}"</div>`:''}
      </div></li>`;
  }).join('')+'</ul>';
}

/* perfil */
function renderPerfil(){
  const url=location.origin+'/u/'+meuHandle;
  const n=prateleira.length;
  $('#perfil').innerHTML=`
    <div class="pcard">
      <div class="label">sua estante pública</div>
      <div class="phandle">@${esc(meuHandle)}</div>
      <div class="pcount">${n} ${n===1?'livro':'livros'}</div>
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
async function abrirCard(i){
  cardAtual=prateleira[i];
  $('#editPanel').style.display='none';
  $('#modal').classList.add('open');
  try{ await document.fonts.ready; }catch(e){}
  drawCard(cardAtual);
}
function fecharModal(){ $('#modal').classList.remove('open'); }

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
  const fb=()=>{
    const h=hue(l.titulo);
    ctx.fillStyle='rgba(26,23,20,.18)';ctx.fillRect(cx+16,cy+20,cw,ch);
    ctx.fillStyle=`hsl(${h},22%,70%)`;ctx.fillRect(cx,cy,cw,ch);
    ctx.fillStyle='rgba(26,23,20,.72)';ctx.textAlign='center';ctx.font="600 italic 92px Fraunces, serif";
    wrapCenter(ctx,l.titulo||'',cx+cw/2,cy+ch/2,cw-150,108,4);
    ctx.textAlign='left';txt();
  };
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
  fecharModal(); await carregarPrateleira();
}
async function removerLeitura(){
  if(!confirm('Remover "'+(cardAtual.titulo||'')+'" da estante?'))return;
  try{ await fetch('/api/prateleira/'+cardAtual.leitura_id,{method:'DELETE'}); }
  catch(e){ alert('não consegui remover.'); return; }
  fecharModal(); await carregarPrateleira();
}

/* init */
async function init(){
  registrarHistorico('buscar','home',true);
  renderChips();
  try{
    const me=await (await fetch('/api/eu')).json();
    meuHandle=me.handle||'';
    $('#meuhandle').textContent='@'+meuHandle;
    $('#crumb').classList.add('visible');
  }catch(e){}
  await carregarPrateleira();
}
init();