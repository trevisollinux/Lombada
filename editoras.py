"""
Lombada — editoras: agregação do catálogo por editora (campo livre em
Edicao.editora — não existe uma entidade "editora" própria, então o
agrupamento usa nome normalizado como chave) e páginas HTML server-rendered
em /editora/{slug} e /editoras.
"""
import re
import unicodedata

from urllib.parse import urlencode

from sqlmodel import select, Session

from models import Edicao, Obra
from publica import _pagina, _esc


def _normalizar(valor: str) -> str:
    texto = unicodedata.normalize("NFKD", str(valor or ""))
    texto = "".join(ch for ch in texto if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", texto.lower().strip())


def slug_editora(nome: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", _normalizar(nome)).strip("-")
    return slug or "editora"


def _agregar(s: Session) -> dict[str, dict]:
    """chave normalizada -> {editora (nome canônico = grafia mais curta vista),
    slug, obras: {obra_id: {titulo, autor, capa_url}}, edicoes_count,
    com_capa_count, com_isbn_count}."""
    agregadas: dict[str, dict] = {}
    rows = s.exec(
        select(Edicao, Obra).join(Obra, Edicao.obra_id == Obra.id).where(Edicao.editora != "")
    ).all()
    for ed, obra in rows:
        nome = (ed.editora or "").strip()
        if not nome:
            continue
        chave = _normalizar(nome)
        item = agregadas.setdefault(chave, {
            "editora": nome, "slug": slug_editora(nome), "obras": {}, "edicoes_count": 0,
            "com_capa_count": 0, "com_isbn_count": 0,
        })
        if len(nome) < len(item["editora"]):
            item["editora"] = nome
            item["slug"] = slug_editora(nome)
        item["edicoes_count"] += 1
        item["com_capa_count"] += 1 if ed.capa_url else 0
        item["com_isbn_count"] += 1 if ed.isbn else 0
        obra_atual = item["obras"].get(obra.id)
        if obra_atual is None or (not obra_atual.get("capa_url") and ed.capa_url):
            item["obras"][obra.id] = {"titulo": obra.titulo, "autor": obra.autor, "capa_url": ed.capa_url, "work_key": obra.ol_work_key}
    return agregadas


def listar_editoras(s: Session) -> list[dict]:
    agregadas = _agregar(s)
    saida = [{
        "editora": item["editora"], "slug": item["slug"], "obras_count": len(item["obras"]),
        "edicoes_count": item["edicoes_count"], "com_capa_count": item["com_capa_count"],
        "com_isbn_count": item["com_isbn_count"],
    } for item in agregadas.values()]
    return sorted(saida, key=lambda item: (-item["obras_count"], item["editora"].lower()))


def dados_editora(s: Session, slug: str) -> dict | None:
    agregadas = _agregar(s)
    item = next((v for v in agregadas.values() if v["slug"] == slug), None)
    if not item:
        return None
    obras = sorted(
        [{"obra_id": obra_id, **dados} for obra_id, dados in item["obras"].items()],
        key=lambda o: o["titulo"] or "",
    )
    return {"slug": item["slug"], "nome": item["editora"], "obras": obras}


def _href_obra(o: dict) -> str:
    """Deep link da página da obra no app; cai na busca por título se não
    houver nem work_key nem título."""
    params = {}
    if (o.get("work_key") or "").strip():
        params["obra"] = o["work_key"].strip()
    if o.get("titulo"):
        params["t"] = o["titulo"]
    if o.get("autor"):
        params["a"] = o["autor"]
    if not params:
        return "/"
    return "/?" + urlencode(params)


def _card_obra(o: dict) -> str:
    cap = o.get("capa_url") or ""
    t = _esc(o.get("titulo"))
    a = _esc(o.get("autor"))
    href = _esc(_href_obra(o))
    if cap:
        cover = (
            f'<div class="cover"><img src="{_esc(cap)}" alt="" loading="lazy" '
            "onerror=\"this.style.display='none';this.nextElementSibling.style.display='flex'\">"
            f'<div class="fb" style="display:none">{t}</div></div>'
        )
    else:
        cover = f'<div class="cover"><div class="fb">{t}</div></div>'
    return f'<a class="book" style="display:block" href="{href}">{cover}<div class="t">{t}</div><div class="a">{a}</div></a>'


def _sanitizar_paginacao(page: int = 1, per_page: int = 20, view: str = "grade") -> tuple[int, int, str]:
    try:
        page = max(1, int(page))
    except (TypeError, ValueError):
        page = 1
    try:
        per_page = int(per_page)
    except (TypeError, ValueError):
        per_page = 20
    if per_page not in {10, 20, 50}:
        per_page = 20
    view = "lista" if str(view or "").lower().strip() == "lista" else "grade"
    return page, per_page, view


def _link_pagina(slug: str, page: int, per_page: int, view: str) -> str:
    return f"/editora/{_esc(slug)}?" + urlencode({"page": page, "per_page": per_page, "view": view})


def _linha_obra(o: dict) -> str:
    cap = o.get("capa_url") or ""
    t = _esc(o.get("titulo"))
    a = _esc(o.get("autor"))
    href = _esc(_href_obra(o))
    if cap:
        cover = (
            f'<div class="cover"><img src="{_esc(cap)}" alt="" loading="lazy" '
            "onerror=\"this.style.display='none';this.nextElementSibling.style.display='flex'\">"
            f'<div class="fb" style="display:none">{t}</div></div>'
        )
    else:
        cover = f'<div class="cover"><div class="fb">{t}</div></div>'
    return f'<a class="pub-book-row" href="{href}">{cover}<span><strong>{t}</strong><small>{a}</small></span></a>'


def _controles_editora(slug: str, page: int, per_page: int, view: str, total_pages: int, has_prev: bool, has_next: bool) -> str:
    prev = f'<a href="{_link_pagina(slug, page - 1, per_page, view)}">← anterior</a>' if has_prev else '<span class="disabled">← anterior</span>'
    prox = f'<a href="{_link_pagina(slug, page + 1, per_page, view)}">próximo →</a>' if has_next else '<span class="disabled">próximo →</span>'
    per_opts = "".join(
        f'<a class="per-page-option {"active" if n == per_page else ""}" href="{_link_pagina(slug, 1, n, view)}">{n}</a>'
        for n in (10, 20, 50)
    )
    grade_active = "active" if view == "grade" else ""
    lista_active = "active" if view == "lista" else ""
    return f'''<nav class="pager" aria-label="paginação da editora">
      <div class="pager-arrows">
        {prev}
        <span class="pager-current">página {page} de {total_pages}</span>
        {prox}
      </div>
      <div class="pager-tools">
        <div class="per-page-select" aria-label="obras por página"><span>por página</span>{per_opts}</div>
        <div class="view-toggle" aria-label="visualização">
          <a class="{grade_active}" href="{_link_pagina(slug, page, per_page, "grade")}">grade</a>
          <a class="{lista_active}" href="{_link_pagina(slug, page, per_page, "lista")}">lista</a>
        </div>
      </div>
    </nav>'''


def render_pagina_editora(dados: dict, page: int = 1, per_page: int = 20, view: str = "grade") -> str:
    nome = dados["nome"]
    obras = dados["obras"]
    n = len(obras)
    page, per_page, view = _sanitizar_paginacao(page, per_page, view)
    total_pages = max(1, (n + per_page - 1) // per_page)
    page = min(page, total_pages)
    has_prev = page > 1
    has_next = page < total_pages
    inicio = (page - 1) * per_page
    obras_pagina = obras[inicio:inicio + per_page]
    cont = "1 obra" if n == 1 else f"{n} obras"
    header = (
        f'<div class="head"><a class="wordmark" href="/">LOMBADA<span class="dot">.</span></a>'
        f'<div class="label">editora</div><h1>{_esc(nome)}</h1>'
        f'<div class="count">{cont} no catálogo</div></div>'
    )
    controles = _controles_editora(dados["slug"], page, per_page, view, total_pages, has_prev, has_next) if obras else ""
    if not obras:
        miolo = '<div class="empty">nenhuma obra encontrada.</div>'
    elif view == "lista":
        miolo = '<div class="pub-book-list">' + "".join(_linha_obra(o) for o in obras_pagina) + '</div>'
    else:
        miolo = '<div class="wall">' + "".join(_card_obra(o) for o in obras_pagina) + '</div>'
    corpo = header + f'<section class="section">{controles}{miolo}{controles}</section>' + '<a class="cta" href="/">explorar na Lombada →</a>'
    og = {"title": f"{nome} · editoras na Lombada", "type": "website", "description": f"{cont} de {nome} catalogadas na Lombada."}
    primeira = next((o.get("capa_url") for o in obras_pagina if o.get("capa_url")), "")
    if primeira:
        og["image"] = primeira
    return _pagina(f"{nome} · Lombada", corpo, og, scripts=f"<style>{_CSS_EXTRA}</style>")


def _linha_editora(e: dict) -> str:
    cont = "1 obra" if e["obras_count"] == 1 else f'{e["obras_count"]} obras'
    return f'<a class="pub-row" href="/editora/{_esc(e["slug"])}"><span class="pub-name">{_esc(e["editora"])}</span><span class="pub-count">{cont}</span></a>'


_CSS_EXTRA = """

.pager{display:grid;gap:12px;border:1px solid var(--rule);background:rgba(255,255,255,.12);padding:12px;margin:0 0 18px}
.pager:last-child{margin:18px 0 0}.pager-arrows,.pager-tools,.view-toggle,.per-page-select{display:flex;align-items:center;gap:8px;flex-wrap:wrap}.pager-arrows{justify-content:space-between}.pager a,.pager .disabled,.pager-current,.per-page-select span{font-family:"Space Mono",monospace;font-size:10px;letter-spacing:.08em;text-transform:uppercase}.pager a,.view-toggle a,.per-page-option{border:1px solid var(--rule);padding:7px 9px;background:rgba(255,255,255,.10)}.pager a.active,.view-toggle a.active,.per-page-option.active{background:var(--ink);border-color:var(--ink);color:var(--paper)}.pager .disabled{color:var(--dim);opacity:.55}.pager-current{color:var(--ink-2)}.pub-book-list{display:grid;gap:10px}.pub-book-row{display:grid;grid-template-columns:48px 1fr;gap:12px;align-items:center;border-top:1px solid var(--rule);padding-top:10px}.pub-book-row:first-child{border-top:0;padding-top:0}.pub-book-row .cover{width:48px;box-shadow:3px 4px 0 rgba(26,23,20,.10),1px 1px 0 rgba(26,23,20,.22)}.pub-book-row strong{display:block;font-family:"Fraunces",serif;font-style:italic;font-size:16px;line-height:1.15}.pub-book-row small{display:block;color:var(--dim);font-size:12px;margin-top:3px}
@media(min-width:520px){.pager{grid-template-columns:1fr auto}.pager-tools{justify-content:flex-end}.pager:last-child{grid-template-columns:1fr}.pager:last-child .pager-tools{justify-content:flex-start}.pub-book-row{grid-template-columns:56px 1fr}.pub-book-row .cover{width:56px}}
.pub-row{display:flex;justify-content:space-between;align-items:baseline;border-top:1px solid var(--rule);padding:12px 0;gap:12px}
.pub-row:first-child{border-top:0}
.pub-name{font-family:"Fraunces",serif;font-style:italic;font-size:17px}
.pub-count{font-family:"Space Mono",monospace;font-size:10px;color:var(--dim);text-transform:uppercase;letter-spacing:.06em;white-space:nowrap}
"""


def render_indice_editoras(editoras: list[dict]) -> str:
    n = len(editoras)
    cont = "1 editora" if n == 1 else f"{n} editoras"
    header = (
        f'<div class="head"><a class="wordmark" href="/">LOMBADA<span class="dot">.</span></a>'
        f'<div class="label">catálogo</div><h1>editoras</h1><div class="count">{cont}</div></div>'
    )
    lista = "".join(_linha_editora(e) for e in editoras) or '<div class="empty">nenhuma editora encontrada.</div>'
    corpo = header + f'<section class="section">{lista}</section>'
    og = {"title": "editoras · Lombada", "type": "website", "description": f"{cont} catalogadas na Lombada."}
    return _pagina("editoras · Lombada", corpo, og, scripts=f"<style>{_CSS_EXTRA}</style>")
