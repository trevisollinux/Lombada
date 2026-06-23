"""
Lombada — clientes de fontes de dados.

Hierarquia ativa:
  busca por título → Google Books (espinha, colapsa em obras) + OL (fallback)
  busca por ISBN   → Google Books + OL em paralelo
  edições de obra  → OL + enriquecimento de capa via GB

MercadoEditorial: PRESERVADO, desativado (virou pago, jun/2026).
  Código _me_* e me_buscar existem aqui, curto-circuitados por ME_ATIVO.
  Para reativar: setar env ME_TOKEN. Nada foi apagado.

Wikidata / Hardcover: presentes mas fora do hot path.
"""
import re
import unicodedata
import concurrent.futures as _fut
from functools import lru_cache

import httpx

from models import GOOGLE_BOOKS_API_KEY, HARDCOVER_API_KEY, ME_ATIVO


# ─── constantes ───────────────────────────────────────────
BASE              = "https://openlibrary.org"
COVERS            = "https://covers.openlibrary.org"
GBOOKS            = "https://www.googleapis.com/books/v1/volumes"
MERCADOEDITORIAL  = "https://api.mercadoeditorial.org/api/v1.2/book"
WIKIDATA_SEARCH   = "https://www.wikidata.org/w/api.php"
HARDCOVER_API_URL = "https://api.hardcover.app/v1/graphql"
TIMEOUT = 12.0
_UA = {"User-Agent": "Lombada/2.0 (diario de leitura; github.com/trevisollinux/lombada)"}

LANG = {
    "por": "Português", "eng": "Inglês", "rus": "Russo", "fre": "Francês",
    "spa": "Espanhol", "ger": "Alemão", "ita": "Italiano", "jpn": "Japonês",
}
LANG2 = {
    "pt": "Português", "en": "Inglês", "ru": "Russo", "fr": "Francês",
    "es": "Espanhol", "de": "Alemão", "it": "Italiano", "ja": "Japonês",
}
EDITORAS_BR_FORTES = [
    "editora 34", "companhia das letras", "penguin", "martin claret",
    "todavia", "record", "rocco", "intrinseca", "autentica",
    "hedra", "carambaia", "cosac", "nova fronteira", "globo",
    "principis", "garnier", "l&pm", "lp&m", "lepm",
]


# ─── utils gerais ─────────────────────────────────────────
def _lang(code: str) -> str:
    code = (code or "").lower().strip()
    return LANG.get(code) or LANG2.get(code) or code


def _sem_acento(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s or "")
                   if unicodedata.category(c) != "Mn").lower().strip()


def _query_norm(q: str) -> str:
    return re.sub(r"\s+", " ", _sem_acento(q or "")).strip()


def _ano_de_data(data) -> int | None:
    m = re.search(r"\b(\d{4})\b", str(data or ""))
    return int(m.group(1)) if m else None


def normalizar_isbn(q: str) -> str:
    c = re.sub(r"[^0-9Xx]", "", (q or "").strip()).upper()
    if len(c) == 10 and re.fullmatch(r"[0-9]{9}[0-9X]", c):
        return c
    if len(c) == 13 and re.fullmatch(r"[0-9]{13}", c):
        return c
    return ""


def _isbn_exato(isbn: str, candidatos) -> bool:
    alvo = normalizar_isbn(isbn)
    return bool(alvo and alvo in {normalizar_isbn(c) for c in (candidatos or [])})


def _relevancia(titulo_resultado: str, titulo_busca: str) -> int:
    tr = _sem_acento(titulo_resultado)
    tb = _sem_acento(titulo_busca)
    if not tb:    return 2
    if tr == tb:  return 0
    if tr.startswith(tb): return 1
    if tb in tr:  return 2
    return 3


def _split_q(q: str) -> tuple[str, str]:
    if "," in q:
        a, b = q.split(",", 1)
        return a.strip(), b.strip()
    return q, ""


def _chave_obra(titulo: str, autor: str) -> str:
    """Chave de colapso: título normalizado + primeiro token do autor."""
    t = re.sub(r"[^a-z0-9]+", " ", _sem_acento(titulo)).strip()
    a_tok = (_sem_acento(autor).split() or [""])[0]
    return f"{t}|{a_tok}"


# ─── helpers de capa ──────────────────────────────────────
_LANG_RANK = {"Português": 0, "Inglês": 1}


def _lang_rank(idioma: str) -> int:
    return _LANG_RANK.get(idioma, 2)


def _limpa_capa_gb(url: str) -> str:
    """Remove page-curl e normaliza zoom do thumbnail do Google Books."""
    if not url:
        return ""
    url = url.replace("http://", "https://")
    url = re.sub(r"&?edge=curl", "", url)
    url = re.sub(r"([?&])zoom=\d+", r"\g<1>zoom=1", url)
    return url


def _capa_ol_isbn(isbn: str) -> str:
    """default=false → OL devolve 404 quando não tem capa (mata placeholder cinza de 1px)."""
    return f"{COVERS}/b/isbn/{isbn}-L.jpg?default=false" if isbn else ""


def _capa_ol_id(cover_i) -> str:
    return f"{COVERS}/b/id/{cover_i}-L.jpg?default=false" if cover_i else ""


def _capa_br(isbn: str) -> str:
    return _gbooks_capa(isbn) or _capa_ol_isbn(isbn)


# ─── ME: utils de parsing (preservados) ───────────────────
def _me_texto(v) -> str:
    if isinstance(v, dict): return (v.get("nome") or v.get("name") or "").strip()
    if isinstance(v, str):  return v.strip()
    return ""


def _me_nome_pessoa(item) -> str:
    if isinstance(item, str): return item.strip()
    if not isinstance(item, dict): return ""
    nome = (item.get("nome") or item.get("name") or "").strip()
    sobr = (item.get("sobrenome") or "").strip()
    return (nome + " " + sobr).strip() or nome


_COD_TRADUTOR = {"b06", "5"}


def _me_contribuinte(livro: dict, alvos_texto, alvos_codigo) -> str:
    contrib = (livro.get("contribuicao") or livro.get("contribuicoes")
               or livro.get("contributors") or {})
    if isinstance(contrib, dict):
        for papel, gente in contrib.items():
            if any(a in _sem_acento(papel) for a in alvos_texto):
                return _me_nome_pessoa(gente if not isinstance(gente, list)
                                       else (gente[0] if gente else {}))
    elif isinstance(contrib, list):
        for item in contrib:
            if not isinstance(item, dict): continue
            papel = _sem_acento(str(item.get("tipo_de_contribuicao")
                                    or item.get("tipo") or item.get("papel") or ""))
            cod = str(item.get("codigo_contribuicao") or "").lower().strip()
            if any(a in papel for a in alvos_texto) or cod in alvos_codigo:
                return _me_nome_pessoa(item)
    return ""


def _me_autor(livro: dict) -> str:
    a = _me_contribuinte(livro, ("autor", "author"), {"a01", "1"})
    return a or _me_texto(livro.get("autor") or livro.get("autores"))


# ─── Google Books ──────────────────────────────────────────
def _gbooks_params(params: dict) -> dict:
    p = dict(params)
    if GOOGLE_BOOKS_API_KEY:
        p["key"] = GOOGLE_BOOKS_API_KEY
    return p


@lru_cache(maxsize=512)
def _gbooks_capa(isbn: str) -> str:
    info = _gbooks_info(isbn)
    return _limpa_capa_gb(info.get("capa", "")) if info else ""


@lru_cache(maxsize=512)
def _gbooks_info(isbn: str) -> dict:
    if not isbn:
        return {}
    try:
        with httpx.Client(timeout=TIMEOUT, headers=_UA) as c:
            r = c.get(GBOOKS, params=_gbooks_params({"q": f"isbn:{isbn}", "country": "BR"}))
            r.raise_for_status()
            items = r.json().get("items", []) or []
        if not items:
            return {}
        info = items[0].get("volumeInfo", {}) or {}
        img = info.get("imageLinks") or {}
        capa = (img.get("thumbnail") or img.get("smallThumbnail") or "").replace("http://", "https://")
        return {
            "titulo":  info.get("title", "") or "",
            "autor":   (info.get("authors") or [""])[0],
            "editora": info.get("publisher", "") or "",
            "ano":     _ano_de_data(info.get("publishedDate", "")),
            "idioma":  _lang(info.get("language") or ""),
            "capa":    capa,
        }
    except Exception:
        return {}


def _gbooks_volumes(q: str, maxr: int = 40) -> list:
    """Uma chamada ao Google Books → lista crua de volumes (edições)."""
    if not q:
        return []
    try:
        with httpx.Client(timeout=TIMEOUT, headers=_UA) as c:
            r = c.get(GBOOKS, params=_gbooks_params({
                "q": q, "country": "BR", "printType": "books",
                "maxResults": min(maxr, 40), "orderBy": "relevance",
            }))
            r.raise_for_status()
            items = r.json().get("items", []) or []
    except Exception:
        return []

    eds = []
    for it in items:
        info = it.get("volumeInfo", {}) or {}
        titulo = (info.get("title") or "").strip()
        if not titulo: continue
        sub = (info.get("subtitle") or "").strip()
        if sub and sub.lower() not in titulo.lower():
            titulo = f"{titulo}: {sub}"
        ids  = info.get("industryIdentifiers") or []
        isbn = ""
        for d in ids:
            if d.get("type") == "ISBN_13":
                isbn = d.get("identifier", "")
                break
        if not isbn and ids:
            isbn = ids[0].get("identifier", "")
        isbn = normalizar_isbn(isbn) or isbn
        img  = info.get("imageLinks") or {}
        capa = _limpa_capa_gb(img.get("thumbnail") or img.get("smallThumbnail") or "")
        eds.append({
            "ol_edition_key": ("isbn:" + isbn) if isbn else ("gb:" + (it.get("id") or "")),
            "titulo_edicao": titulo,
            "editora":  info.get("publisher", "") or "",
            "tradutor": "",
            "isbn":     isbn,
            "idioma":   _lang(info.get("language") or ""),
            "ano":      _ano_de_data(info.get("publishedDate", "")),
            "capa_url": capa,
            "_autor":   (info.get("authors") or [""])[0],
            "_autores": info.get("authors") or [],
        })
    return eds


def gbooks_buscar(q: str, limite: int = 18) -> list:
    """Busca espinha: volumes do GB colapsados em obras (sem segunda chamada à API)."""
    titulo_q, autor_q = _split_q(q)
    eds = _gbooks_volumes(q)
    if not eds and autor_q:
        eds = _gbooks_volumes(titulo_q)
    if not eds:
        return []

    grupos: dict[str, list] = {}
    for e in eds:
        grupos.setdefault(_chave_obra(e["titulo_edicao"], e["_autor"]), []).append(e)

    obras = []
    for k, lista in grupos.items():
        lista_disp = sorted(lista, key=lambda e: (
            _lang_rank(e["idioma"]),
            0 if e["capa_url"] else 1,
            0 if e["isbn"] else 1,
            -(e["ano"] or 0),
        ))
        disp = lista_disp[0]
        # capa desacoplada: tenta a edição de exibição; empresta irmã se vazia
        capa = disp["capa_url"]
        if not capa:
            com_capa = sorted(
                [e for e in lista if e["capa_url"]],
                key=lambda e: (_lang_rank(e["idioma"]), -(e["ano"] or 0)),
            )
            if com_capa:
                capa = com_capa[0]["capa_url"]
        edicoes = [{kk: vv for kk, vv in e.items() if not kk.startswith("_")}
                   for e in lista_disp]
        obras.append({
            "work_key":       "gb:" + k,
            "titulo":         disp["titulo_edicao"],
            "autor":          disp["_autor"] or "—",
            "_autores":       disp.get("_autores") or [],
            "ano":            disp["ano"],
            "idioma_original":disp["idioma"],
            "tem_pt":         any(e["idioma"] == "Português" for e in lista),
            "capa_url":       capa,
            "isbn_match":     False,
            "edicao_isbn":    edicoes[0],
            "edicoes":        edicoes,
            "_fonte":         "gb",
        })
        if len(obras) >= limite * 2:
            break
    return obras


# ─── MercadoEditorial (PRESERVADO, desativado por ME_ATIVO) ───
@lru_cache(maxsize=512)
def _me_full(isbn: str) -> dict:
    if not ME_ATIVO or not isbn:
        return {}
    try:
        with httpx.Client(timeout=TIMEOUT, headers=_UA) as c:
            r = c.get(MERCADOEDITORIAL, params={"isbn": isbn})
            r.raise_for_status()
            data = r.json()
        books = data.get("books") or data.get("book") or []
        if isinstance(books, dict): books = [books]
        if not books: return {}
        return _me_normaliza(books[0])
    except Exception:
        return {}


def _me_normaliza(livro: dict) -> dict:
    if not isinstance(livro, dict): return {}
    tradutor = _me_contribuinte(livro, ("tradu", "translat"), _COD_TRADUTOR)
    capa = (livro.get("imagem_primeira_capa") or livro.get("imagem") or "").replace("http://", "https://")
    ano = None
    for campo in ("ano_edicao", "ano", "data_publicacao", "data"):
        ano = _ano_de_data(livro.get(campo))
        if ano: break
    isbn = (livro.get("isbn") or livro.get("isbn13") or livro.get("codigo_de_barras") or "").strip()
    return {
        "tradutor": tradutor, "autor": _me_autor(livro), "capa": capa,
        "titulo":   _me_texto(livro.get("titulo")),
        "editora":  _me_texto(livro.get("editora")),
        "ano": ano, "idioma": "Português",
        "isbn": normalizar_isbn(isbn) or isbn,
        "paginas": livro.get("numero_paginas") or livro.get("paginas") or None,
        "sinopse": (_me_texto(livro.get("sinopse")) or "").strip(),
    }


def _mercadoeditorial(isbn: str) -> tuple[str, str]:
    f = _me_full(isbn)
    return (f.get("tradutor", ""), f.get("capa", "")) if f else ("", "")


def _doc_de_me(livro: dict) -> dict | None:
    n = _me_normaliza(livro)
    if not n.get("titulo"): return None
    isbn = n.get("isbn") or ""
    edicao = {
        "ol_edition_key": ("isbn:" + isbn) if isbn else None,
        "titulo_edicao": n["titulo"], "editora": n.get("editora", ""),
        "tradutor": n.get("tradutor", ""), "isbn": isbn,
        "idioma": "Português", "ano": n.get("ano"), "capa_url": n.get("capa", ""),
    }
    return {
        "work_key": ("isbn:" + isbn) if isbn else ("me:" + n["titulo"][:60]),
        "titulo": n["titulo"], "autor": n.get("autor") or "—",
        "ano": n.get("ano"), "idioma_original": "Português",
        "tem_pt": True, "capa_url": n.get("capa", ""),
        "isbn_match": bool(isbn), "edicao_isbn": edicao, "_fonte": "me",
    }


def me_buscar(titulo: str, limite: int = 12) -> list:
    if not ME_ATIVO or not titulo:
        return []
    try:
        with httpx.Client(timeout=TIMEOUT, headers=_UA) as c:
            r = c.get(MERCADOEDITORIAL, params={"titulo": titulo})
            r.raise_for_status()
            data = r.json()
    except Exception:
        return []
    books = data.get("books") or data.get("book") or []
    if isinstance(books, dict): books = [books]
    out, vistos = [], set()
    for livro in books:
        doc = _doc_de_me(livro)
        if not doc: continue
        chave = (doc.get("edicao_isbn") or {}).get("isbn") or _sem_acento(doc["titulo"])
        if chave in vistos: continue
        vistos.add(chave)
        out.append(doc)
        if len(out) >= limite: break
    out.sort(key=lambda o: _relevancia(o["titulo"], titulo))
    return out


# ─── Open Library ──────────────────────────────────────────
@lru_cache(maxsize=256)
def _melhor_edicao_pt(work_key: str) -> tuple[str, str]:
    if not work_key or not work_key.startswith("/works/"):
        return ("", "")
    try:
        with httpx.Client(timeout=TIMEOUT, headers=_UA) as c:
            r = c.get(f"{BASE}{work_key}/editions.json", params={"limit": 50})
            r.raise_for_status()
            entries = r.json().get("entries", [])
    except Exception:
        return ("", "")
    pt = []
    for ed in entries:
        langs = [l.get("key", "").rsplit("/", 1)[-1] for l in (ed.get("languages") or [])]
        if "por" not in langs: continue
        isbn = (ed.get("isbn_13") or ed.get("isbn_10") or [""])[0]
        pt.append({"titulo": ed.get("title", ""), "isbn": isbn,
                   "ano": _ano_de_data(ed.get("publish_date", ""))})
    if not pt: return ("", "")
    pt.sort(key=lambda e: (e["isbn"] == "", -(e["ano"] or 0)))
    best = pt[0]
    return (best["titulo"], _capa_br(best["isbn"]))


def ol_buscar(q: str, limite: int = 10) -> list:
    fields = "key,title,author_name,first_publish_year,cover_i,language"
    titulo_q, autor_q = _split_q(q)

    def _query(termo):
        with httpx.Client(timeout=TIMEOUT, headers=_UA) as c:
            r = c.get(f"{BASE}/search.json",
                      params={"q": termo, "fields": fields, "limit": limite})
            r.raise_for_status()
            return r.json().get("docs", [])

    docs = []
    try:
        docs = _query(q)
        if not docs and autor_q:
            docs = _query(titulo_q)
    except Exception:
        return []

    out = []
    for d in docs:
        cover_i = d.get("cover_i")
        langs   = d.get("language") or []
        autores = d.get("author_name") or []
        out.append({
            "work_key":       d.get("key", ""),
            "titulo":         d.get("title", ""),
            "autor":          (autores or ["—"])[0],
            "_autores":       autores,
            "ano":            d.get("first_publish_year"),
            "idioma_original":_lang((langs or [""])[0]),
            "tem_pt":         "por" in langs,
            "capa_url":       _capa_ol_id(cover_i),
            "isbn_match":     False,
            "edicao_isbn":    None,
            "_fonte":         "ol",
        })

    if autor_q:
        tokens = [t for t in _sem_acento(autor_q).split() if len(t) >= 3]
        if tokens:
            filtrados = [o for o in out
                         if any(t in _sem_acento(" ".join(o["_autores"])) for t in tokens)]
            if filtrados:
                out = filtrados

    out.sort(key=lambda o: (
        _relevancia(o["titulo"], titulo_q), 0 if o["tem_pt"] else 1, -(o["ano"] or 0)
    ))

    pt_idx = [i for i, o in enumerate(out) if o.get("tem_pt")]
    if pt_idx:
        def _br(i):
            titulo_pt, capa_br = _melhor_edicao_pt(out[i]["work_key"])
            if titulo_pt: out[i]["titulo"]   = titulo_pt
            if capa_br:   out[i]["capa_url"] = capa_br
        with _fut.ThreadPoolExecutor(max_workers=8) as ex:
            list(ex.map(_br, pt_idx))

    for o in out:
        o.pop("_autores", None)
    return out


def _tradutor(ed: dict) -> str:
    for ctr in ed.get("contributors", []) or []:
        role = _sem_acento(ctr.get("role") or "")
        if "translat" in role or "tradu" in role:
            return ctr.get("name", "")
    by    = ed.get("by_statement") or ""
    plano = _sem_acento(by)
    for marca in ("traducao de ", "translated by ", "trad. ", "traducao "):
        if marca in plano:
            i = plano.find(marca) + len(marca)
            return by[i:].strip(" .;,")
    return ""


def ol_edicoes(work_key: str, limite: int = 20) -> list:
    if not work_key.startswith("/works/"):
        return []
    with httpx.Client(timeout=TIMEOUT, headers=_UA) as c:
        r = c.get(f"{BASE}{work_key}/editions.json", params={"limit": limite})
        r.raise_for_status()
        entries = r.json().get("entries", [])
    out = []
    for ed in entries:
        isbn      = (ed.get("isbn_13") or ed.get("isbn_10") or [""])[0]
        lang_code = ""
        if ed.get("languages"):
            lang_code = ed["languages"][0].get("key", "").rsplit("/", 1)[-1]
        out.append({
            "ol_edition_key": ed.get("key", ""),
            "titulo_edicao":  ed.get("title", ""),
            "editora":  (ed.get("publishers") or [""])[0],
            "tradutor": _tradutor(ed),
            "isbn":     isbn,
            "idioma":   _lang(lang_code),
            "ano":      _ano_de_data(ed.get("publish_date", "")),
            "capa_url": _capa_ol_isbn(isbn),
        })
    out.sort(key=lambda e: (e["idioma"] != "Português", e["editora"] == "", -(e["ano"] or 0)))
    alvo = [e for e in out if e["isbn"] and e["idioma"] == "Português"]
    if alvo:
        def _enriquecer(e):
            capa = _gbooks_capa(e["isbn"])
            if capa: e["capa_url"] = capa
            return e
        with _fut.ThreadPoolExecutor(max_workers=6) as ex:
            list(ex.map(_enriquecer, alvo))
    return out


@lru_cache(maxsize=256)
def _ol_isbn(isbn: str) -> dict:
    if not isbn: return {}
    try:
        with httpx.Client(timeout=TIMEOUT, headers=_UA, follow_redirects=True) as c:
            r = c.get(f"{BASE}/isbn/{isbn}.json")
            if r.status_code == 404: return {}
            r.raise_for_status()
            ed = r.json()
    except Exception:
        return {}
    isbns = (ed.get("isbn_13") or []) + (ed.get("isbn_10") or [])
    if isbns and not _isbn_exato(isbn, isbns): return {}
    lang_code = ""
    if ed.get("languages"):
        lang_code = ed["languages"][0].get("key", "").rsplit("/", 1)[-1]
    work_key = ""
    if ed.get("works"):
        work_key = ed["works"][0].get("key") or ""
    return {
        "ol_edition_key": ed.get("key", ""),
        "titulo":   ed.get("title", "") or "",
        "editora":  (ed.get("publishers") or [""])[0],
        "tradutor": _tradutor(ed),
        "idioma":   _lang(lang_code),
        "ano":      _ano_de_data(ed.get("publish_date", "")),
        "work_key": work_key,
    }


# ─── Wikidata (preservado, fora do hot path) ───────────────
@lru_cache(maxsize=256)
def wikidata_buscar_obra(q: str) -> dict:
    if not q: return {}
    try:
        with httpx.Client(timeout=TIMEOUT, headers=_UA) as c:
            r = c.get(WIKIDATA_SEARCH, params={
                "action": "wbsearchentities", "search": q,
                "language": "pt", "format": "json", "limit": 5,
            })
            r.raise_for_status()
            data = r.json()
    except Exception:
        return {}
    results = data.get("search") or []
    if not results: return {}
    item = results[0]
    return {
        "wikidata_id":      item.get("id", ""),
        "titulo_original":  item.get("label", ""),
        "descricao":        item.get("description", ""),
        "wikidata_url":     item.get("concepturi", ""),
    }


# ─── Hardcover (preservado, fora do hot path) ──────────────
@lru_cache(maxsize=128)
def hardcover_buscar(q: str, limite: int = 10) -> list:
    if not HARDCOVER_API_KEY or not q: return []
    graphql = """
    query SearchBooks($query: String!, $limit: Int!) {
      search(query: $query, query_type: "Book", per_page: $limit, page: 1) {
        results
      }
    }
    """
    try:
        with httpx.Client(timeout=TIMEOUT, headers={
            **_UA, "authorization": HARDCOVER_API_KEY, "content-type": "application/json",
        }) as c:
            r = c.post(HARDCOVER_API_URL,
                       json={"query": graphql, "variables": {"query": q, "limit": limite}})
            r.raise_for_status()
            data = r.json()
    except Exception:
        return []
    resultados = (((data.get("data") or {}).get("search") or {}).get("results") or [])
    out = []
    for item in resultados:
        book = item.get("document") or item.get("book") or item
        if not isinstance(book, dict): continue
        titulo = book.get("title") or book.get("title_canonical") or ""
        if not titulo: continue
        capa = ""
        image = book.get("image") or book.get("cached_image") or {}
        if isinstance(image, dict):
            capa = image.get("url") or image.get("image_url") or ""
        elif isinstance(image, str):
            capa = image
        autor = ""
        contribs = book.get("contributions") or []
        if contribs and isinstance(contribs, list):
            first  = contribs[0]
            author = first.get("author") if isinstance(first, dict) else {}
            if isinstance(author, dict):
                autor = author.get("name") or ""
        out.append({
            "work_key": "hc:" + str(book.get("id") or titulo[:40]),
            "titulo": titulo, "autor": autor or "—",
            "ano": _ano_de_data(book.get("release_date") or book.get("published_date") or ""),
            "idioma_original": "", "tem_pt": False,
            "capa_url": capa.replace("http://", "https://") if capa else "",
            "isbn_match": False, "edicao_isbn": None,
            "_fonte": "hardcover", "hardcover_id": book.get("id"),
        })
    return out
