"""
Lombada — arquivo único.
Open Library (busca + edições) + Google Books (capa) + MercadoEditorial (tradutor + capa).
Busca BR-first + proxy de capa (/api/capa) + IDENTIDADE ANÔNIMA (handle fofo, sem login).
Primeira visita já cria um usuário com handle único; prateleira é por usuário; o handle
viaja estampado no card. email/senha ficam pra um "garantir conta" futuro (opcionais).
Front é o index.html ao lado.
"""
import os
import socket
import random
import re
import ipaddress
import unicodedata
import concurrent.futures as _fut
from contextlib import asynccontextmanager
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import httpx
from fastapi import FastAPI, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel
from sqlalchemy import text
from sqlmodel import SQLModel, Field, create_engine, Session, select
from starlette.middleware.sessions import SessionMiddleware

# ───────────────────────── banco ─────────────────────────
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///lombada.db")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, echo=False, connect_args=_args)

SECRET_KEY = os.getenv("SECRET_KEY", "troque-isto-em-producao-por-uma-string-aleatoria")


class Usuario(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    handle: str = Field(index=True, unique=True)        # nome fofo, sempre presente
    email: Optional[str] = Field(default=None, index=True, unique=True)  # só ao "garantir conta"
    senha_hash: Optional[str] = None
    nome: str = ""
    criado_em: datetime = Field(default_factory=datetime.utcnow)


class Obra(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    ol_work_key: str = Field(index=True, unique=True)
    titulo: str
    autor: str = ""
    idioma_original: str = ""
    ano: Optional[int] = None


class Edicao(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    obra_id: int = Field(foreign_key="obra.id", index=True)
    ol_edition_key: Optional[str] = Field(default=None, index=True)
    editora: str = ""
    tradutor: str = ""
    isbn: str = ""
    idioma: str = ""
    ano: Optional[int] = None
    capa_url: str = ""


class Leitura(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    edicao_id: int = Field(foreign_key="edicao.id", index=True)
    usuario_id: Optional[int] = Field(default=None, foreign_key="usuario.id", index=True)
    status: str = "Lido"
    nota: Optional[float] = None
    relato: str = ""
    data: str = ""
    criado_em: datetime = Field(default_factory=datetime.utcnow)


# ──────────────────── handle fofo ────────────────────
_BICHO = ["capivara", "coruja", "raposa", "tatu", "lontra", "perereca", "jaguatirica",
          "tucano", "sagui", "quati", "arara", "preguica", "tamandua", "bemtevi"]
_ADJ = ["sonolenta", "curiosa", "saudosa", "serena", "faminta", "valente", "distraida",
        "noturna", "errante", "teimosa", "sonhadora", "melancolica", "leitora", "vadia"]


def _gera_handle(s):
    for _ in range(40):
        h = f"{random.choice(_BICHO)}-{random.choice(_ADJ)}-{random.randint(10, 999)}"
        if not s.exec(select(Usuario).where(Usuario.handle == h)).first():
            return h
    return f"leitor-{int(datetime.utcnow().timestamp())}"


def criar_anonimo(s):
    u = Usuario(handle=_gera_handle(s))
    s.add(u); s.commit(); s.refresh(u)
    return u


def usuario_sessao(request, s):
    """Devolve o usuário da sessão; se não houver, cria um anônimo e guarda no cookie.
    Sem portão de login — todo visitante já é um usuário."""
    uid = request.session.get("uid")
    u = s.get(Usuario, uid) if uid else None
    if not u:
        u = criar_anonimo(s)
        request.session["uid"] = u.id
    return u


# ──────────────────── fontes de dados ────────────────────
BASE = "https://openlibrary.org"
COVERS = "https://covers.openlibrary.org"
GBOOKS = "https://www.googleapis.com/books/v1/volumes"
MERCADOEDITORIAL = "https://api.mercadoeditorial.org/api/v1.2/book"
TIMEOUT = 12.0
_UA = {"User-Agent": "Lombada/1.0 (diario de leitura; github.com/trevisollinux/lombada)"}
LANG = {"por": "Português", "eng": "Inglês", "rus": "Russo", "fre": "Francês",
        "spa": "Espanhol", "ger": "Alemão", "ita": "Italiano", "jpn": "Japonês"}



def normalizar_isbn(q):
    """Normaliza ISBN-10/13, preservando X final de ISBN-10 quando houver."""
    bruto = (q or "").strip()
    if not bruto:
        return ""
    compactado = re.sub(r"[^0-9Xx]", "", bruto).upper()
    if len(compactado) == 10 and re.fullmatch(r"[0-9]{9}[0-9X]", compactado):
        return compactado
    if len(compactado) == 13 and re.fullmatch(r"[0-9]{13}", compactado):
        return compactado
    return ""


def _isbn_exato(isbn, candidatos):
    alvo = normalizar_isbn(isbn)
    return bool(alvo and alvo in {normalizar_isbn(c) for c in (candidatos or [])})


def _ano_de_data(data):
    m = re.search(r"\b(\d{4})\b", data or "")
    return int(m.group(1)) if m else None

def _lang(code):
    return LANG.get(code, code)


def _sem_acento(s):
    return "".join(c for c in unicodedata.normalize("NFD", s or "")
                   if unicodedata.category(c) != "Mn").lower().strip()


def _nome_contrib(g):
    if isinstance(g, str):
        return g.strip()
    if isinstance(g, dict):
        return (g.get("nome") or g.get("name") or "").strip()
    if isinstance(g, list) and g:
        return _nome_contrib(g[0])
    return ""


@lru_cache(maxsize=512)
def _gbooks_capa(isbn):
    if not isbn:
        return ""
    try:
        with httpx.Client(timeout=TIMEOUT) as c:
            r = c.get(GBOOKS, params={"q": f"isbn:{isbn}", "country": "BR"})
            r.raise_for_status()
            items = r.json().get("items", [])
        if not items:
            return ""
        img = items[0].get("volumeInfo", {}).get("imageLinks") or {}
        url = img.get("thumbnail") or img.get("smallThumbnail") or ""
        return url.replace("http://", "https://")
    except Exception:
        return ""


@lru_cache(maxsize=512)
def _mercadoeditorial(isbn):
    if not isbn:
        return ("", "")
    try:
        with httpx.Client(timeout=TIMEOUT) as c:
            r = c.get(MERCADOEDITORIAL, params={"isbn": isbn})
            r.raise_for_status()
            data = r.json()
        books = data.get("books") or data.get("book") or []
        if isinstance(books, dict):
            books = [books]
        if not books:
            return ("", "")
        livro = books[0]

        tradutor = ""
        contrib = livro.get("contribuicao") or livro.get("contribuicoes") or {}
        if isinstance(contrib, dict):
            for papel, gente in contrib.items():
                if "tradu" in _sem_acento(papel):
                    tradutor = _nome_contrib(gente)
                    break
        elif isinstance(contrib, list):
            for item in contrib:
                papel = _sem_acento(str(item.get("codigo_contribuicao")
                                        or item.get("tipo") or item.get("papel") or ""))
                if "tradu" in papel or item.get("codigo_contribuicao") == "B06":
                    tradutor = _nome_contrib(item)
                    break

        capa = livro.get("imagem_primeira_capa") or ""
        if capa:
            capa = capa.replace("http://", "https://")
        return (tradutor, capa)
    except Exception:
        return ("", "")


def _capa_br(isbn):
    if not isbn:
        return ""
    _, capa_me = _mercadoeditorial(isbn)
    return capa_me or _gbooks_capa(isbn) or f"{COVERS}/b/isbn/{isbn}-L.jpg"


@lru_cache(maxsize=256)
def _melhor_edicao_pt(work_key):
    if not work_key:
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
        if "por" not in langs:
            continue
        isbn = (ed.get("isbn_13") or ed.get("isbn_10") or [""])[0]
        ano = None
        for tok in (ed.get("publish_date", "") or "").replace(",", " ").split():
            if tok.isdigit() and len(tok) == 4:
                ano = int(tok)
                break
        pt.append({"titulo": ed.get("title", ""), "isbn": isbn, "ano": ano})

    if not pt:
        return ("", "")
    pt.sort(key=lambda e: (e["isbn"] == "", -(e["ano"] or 0)))
    best = pt[0]
    return (best["titulo"], _capa_br(best["isbn"]))


def _relevancia(titulo_resultado, titulo_busca):
    tr = _sem_acento(titulo_resultado)
    tb = _sem_acento(titulo_busca)
    if not tb:
        return 2
    if tr == tb:
        return 0
    if tr.startswith(tb):
        return 1
    if tb in tr:
        return 2
    return 3


def ol_buscar(q, limite=10):
    fields = "key,title,author_name,first_publish_year,cover_i,language"

    titulo_q, autor_q = q, ""
    if "," in q:
        partes = q.split(",", 1)
        titulo_q = partes[0].strip()
        autor_q = partes[1].strip()

    def _query(termo):
        with httpx.Client(timeout=TIMEOUT, headers=_UA) as c:
            r = c.get(f"{BASE}/search.json",
                      params={"q": termo, "fields": fields, "limit": limite})
            r.raise_for_status()
            return r.json().get("docs", [])

    docs = _query(q)
    if not docs and autor_q:
        docs = _query(titulo_q)

    out = []
    for d in docs:
        cover_i = d.get("cover_i")
        langs = d.get("language") or []
        autores = d.get("author_name") or []
        out.append({
            "work_key": d.get("key", ""),
            "titulo": d.get("title", ""),
            "autor": (autores or ["—"])[0],
            "_autores": autores,
            "ano": d.get("first_publish_year"),
            "idioma_original": _lang((langs or [""])[0]),
            "tem_pt": "por" in langs,
            "capa_url": f"{COVERS}/b/id/{cover_i}-L.jpg" if cover_i else "",
        })

    if autor_q:
        tokens = [t for t in _sem_acento(autor_q).split() if len(t) >= 3]
        if tokens:
            filtrados = []
            for o in out:
                alvo = _sem_acento(" ".join(o["_autores"]))
                if any(t in alvo for t in tokens):
                    filtrados.append(o)
            if filtrados:
                out = filtrados

    out.sort(key=lambda o: (_relevancia(o["titulo"], titulo_q),
                            0 if o["tem_pt"] else 1,
                            -(o["ano"] or 0)))

    pt_idx = [i for i, o in enumerate(out) if o.get("tem_pt")]
    if pt_idx:
        def _br(i):
            titulo_pt, capa_br = _melhor_edicao_pt(out[i]["work_key"])
            if titulo_pt:
                out[i]["titulo"] = titulo_pt
            if capa_br:
                out[i]["capa_url"] = capa_br
        with _fut.ThreadPoolExecutor(max_workers=8) as ex:
            list(ex.map(_br, pt_idx))

    for o in out:
        o.pop("_autores", None)
    return out



def _edicao_por_isbn(isbn):
    isbn = normalizar_isbn(isbn)
    if not isbn:
        return None

    def _base_doc(titulo, autor, ano, capa_url, work_key, edition):
        return {
            "work_key": work_key,
            "titulo": titulo or "Edição sem título",
            "autor": autor or "—",
            "ano": ano,
            "idioma_original": edition.get("idioma", ""),
            "tem_pt": edition.get("idioma") == "Português",
            "capa_url": capa_url or edition.get("capa_url", ""),
            "isbn_match": True,
            "edicao_isbn": edition,
        }

    try:
        with httpx.Client(timeout=TIMEOUT) as c:
            r = c.get(GBOOKS, params={"q": f"isbn:{isbn}", "country": "BR"})
            r.raise_for_status()
            items = r.json().get("items", [])
    except Exception:
        items = []

    for item in items:
        info = item.get("volumeInfo", {}) or {}
        ids = [i.get("identifier", "") for i in (info.get("industryIdentifiers") or [])]
        if not _isbn_exato(isbn, ids):
            continue
        img = info.get("imageLinks") or {}
        capa = (img.get("thumbnail") or img.get("smallThumbnail") or "").replace("http://", "https://")
        autores = info.get("authors") or []
        lang = _lang(info.get("language") or "")
        edition = {
            "ol_edition_key": "google:" + (item.get("id") or isbn),
            "titulo_edicao": info.get("title", ""),
            "editora": info.get("publisher", ""),
            "tradutor": "",
            "isbn": isbn,
            "idioma": lang,
            "ano": _ano_de_data(info.get("publishedDate", "")),
            "capa_url": capa or _capa_br(isbn),
            "encontrada_por_isbn": True,
        }
        return _base_doc(info.get("title", ""), (autores or ["—"])[0], edition["ano"], edition["capa_url"], "isbn:" + isbn, edition)

    try:
        with httpx.Client(timeout=TIMEOUT, headers=_UA) as c:
            r = c.get(f"{BASE}/isbn/{isbn}.json")
            if r.status_code == 404:
                return None
            r.raise_for_status()
            ed = r.json()
    except Exception:
        return None

    isbns = (ed.get("isbn_13") or []) + (ed.get("isbn_10") or [])
    if isbns and not _isbn_exato(isbn, isbns):
        return None
    lang_code = ""
    if ed.get("languages"):
        lang_code = ed["languages"][0].get("key", "").rsplit("/", 1)[-1]
    edition = {
        "ol_edition_key": ed.get("key", ""),
        "titulo_edicao": ed.get("title", ""),
        "editora": (ed.get("publishers") or [""])[0],
        "tradutor": _tradutor(ed),
        "isbn": isbn,
        "idioma": _lang(lang_code),
        "ano": _ano_de_data(ed.get("publish_date", "")),
        "capa_url": _capa_br(isbn),
        "encontrada_por_isbn": True,
    }
    work_key = "isbn:" + isbn
    if ed.get("works"):
        work_key = ed["works"][0].get("key") or work_key
    return _base_doc(ed.get("title", ""), "—", edition["ano"], edition["capa_url"], work_key, edition)


def _tradutor(ed):
    for ctr in ed.get("contributors", []) or []:
        role = _sem_acento(ctr.get("role") or "")
        if "translat" in role or "tradu" in role:
            return ctr.get("name", "")
    by = ed.get("by_statement") or ""
    plano = _sem_acento(by)
    for marca in ("traducao de ", "translated by ", "trad. ", "traducao "):
        if marca in plano:
            i = plano.find(marca) + len(marca)
            return by[i:].strip(" .;,")
    return ""


def ol_edicoes(work_key, limite=20):
    with httpx.Client(timeout=TIMEOUT, headers=_UA) as c:
        r = c.get(f"{BASE}{work_key}/editions.json", params={"limit": limite})
        r.raise_for_status()
        entries = r.json().get("entries", [])
    out = []
    for ed in entries:
        isbn = (ed.get("isbn_13") or ed.get("isbn_10") or [""])[0]
        lang_code = ""
        if ed.get("languages"):
            lang_code = ed["languages"][0].get("key", "").rsplit("/", 1)[-1]
        ano = None
        for tok in (ed.get("publish_date", "") or "").replace(",", " ").split():
            if tok.isdigit() and len(tok) == 4:
                ano = int(tok)
                break
        out.append({
            "ol_edition_key": ed.get("key", ""),
            "titulo_edicao": ed.get("title", ""),
            "editora": (ed.get("publishers") or [""])[0],
            "tradutor": _tradutor(ed),
            "isbn": isbn,
            "idioma": _lang(lang_code),
            "ano": ano,
            "capa_url": f"{COVERS}/b/isbn/{isbn}-L.jpg" if isbn else "",
        })
    out.sort(key=lambda e: (e["idioma"] != "Português", e["editora"] == "", -(e["ano"] or 0)))

    alvo = [e for e in out if e["isbn"] and e["idioma"] == "Português"]
    if alvo:
        def _enriquecer(e):
            trad_me, capa_me = _mercadoeditorial(e["isbn"])
            if trad_me and not e["tradutor"]:
                e["tradutor"] = trad_me
            capa = capa_me or _gbooks_capa(e["isbn"])
            if capa:
                e["capa_url"] = capa
            return e

        with _fut.ThreadPoolExecutor(max_workers=6) as ex:
            list(ex.map(_enriquecer, alvo))

    return out


# ───────────── proxy de capa (same-origin pro card) ─────────────
def _host_publico(host):
    if not host:
        return False
    try:
        infos = socket.getaddrinfo(host, None)
    except Exception:
        return False
    for fam, _, _, _, sockaddr in infos:
        try:
            ip = ipaddress.ip_address(sockaddr[0])
        except ValueError:
            return False
        if (ip.is_private or ip.is_loopback or ip.is_link_local
                or ip.is_reserved or ip.is_multicast or ip.is_unspecified):
            return False
    return True


def proxy_capa(url):
    p = urlparse(url or "")
    if p.scheme != "https" or not _host_publico(p.hostname):
        raise HTTPException(400, "url de capa inválida")
    with httpx.Client(timeout=TIMEOUT, headers=_UA, follow_redirects=True) as c:
        r = c.get(url)
        r.raise_for_status()
    ct = r.headers.get("content-type", "")
    if not ct.startswith("image/"):
        raise HTTPException(415, "isso não é uma imagem")
    if len(r.content) > 6 * 1024 * 1024:
        raise HTTPException(413, "capa grande demais")
    return Response(content=r.content, media_type=ct,
                    headers={"Cache-Control": "public, max-age=86400"})


# ──────────────────────── app ────────────────────────
def _migrar():
    """Migração leve e idempotente. Cada DDL em transação própria; o que já existir,
    falha em silêncio. Cobre o upgrade do banco antigo (com login) pro modelo anônimo."""
    ddls = [
        "ALTER TABLE leitura ADD COLUMN usuario_id INTEGER",
        "ALTER TABLE usuario ADD COLUMN handle VARCHAR",
        "ALTER TABLE usuario ALTER COLUMN email DROP NOT NULL",
        "ALTER TABLE usuario ALTER COLUMN senha_hash DROP NOT NULL",
    ]
    for ddl in ddls:
        try:
            with engine.begin() as conn:
                conn.execute(text(ddl))
        except Exception:
            pass


@asynccontextmanager
async def lifespan(app):
    SQLModel.metadata.create_all(engine)
    _migrar()
    yield


app = FastAPI(title="Lombada", lifespan=lifespan)
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY, same_site="lax", https_only=False)
AQUI = Path(__file__).resolve().parent


def get_session():
    with Session(engine) as s:
        yield s


# ───────────── identidade ─────────────
@app.get("/api/eu")
def eu(request: Request, s: Session = Depends(get_session)):
    u = usuario_sessao(request, s)
    return {"handle": u.handle, "nome": u.nome, "email": u.email}


# ───────────── catálogo (público) ─────────────
@app.get("/api/buscar")
def buscar(q: str = Query(..., min_length=2)):
    isbn = normalizar_isbn(q)
    if isbn:
        try:
            achado = _edicao_por_isbn(isbn)
            return [achado] if achado else []
        except Exception as e:
            raise HTTPException(502, f"Busca por ISBN indisponível: {e}")
    try:
        return ol_buscar(q)
    except Exception as e:
        raise HTTPException(502, f"Open Library indisponível: {e}")


@app.get("/api/edicoes")
def edicoes(work_key: str):
    try:
        return ol_edicoes(work_key)
    except Exception as e:
        raise HTTPException(502, f"Open Library indisponível: {e}")


@app.get("/api/capa")
def capa(url: str = Query(..., min_length=8)):
    try:
        return proxy_capa(url)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(502, f"capa indisponível: {e}")


# ───────────── prateleira (por usuário, anônimo incluso) ─────────────
class EntradaPrateleira(BaseModel):
    work_key: str
    titulo: str
    autor: str = ""
    idioma_original: str = ""
    ano_obra: Optional[int] = None
    ol_edition_key: Optional[str] = None
    editora: str = ""
    tradutor: str = ""
    isbn: str = ""
    idioma: str = ""
    ano_edicao: Optional[int] = None
    capa_url: str = ""
    status: str = "Lido"
    nota: Optional[float] = None
    relato: str = ""
    data: str = ""


@app.post("/api/prateleira")
def adicionar(e: EntradaPrateleira, request: Request, s: Session = Depends(get_session)):
    u = usuario_sessao(request, s)

    obra = s.exec(select(Obra).where(Obra.ol_work_key == e.work_key)).first()
    if not obra:
        obra = Obra(ol_work_key=e.work_key, titulo=e.titulo, autor=e.autor,
                    idioma_original=e.idioma_original, ano=e.ano_obra)
        s.add(obra); s.commit(); s.refresh(obra)

    edicao = None
    if e.ol_edition_key:
        edicao = s.exec(select(Edicao).where(
            Edicao.ol_edition_key == e.ol_edition_key)).first()
    if not edicao:
        edicao = Edicao(obra_id=obra.id, ol_edition_key=e.ol_edition_key,
                        editora=e.editora, tradutor=e.tradutor, isbn=e.isbn,
                        idioma=e.idioma, ano=e.ano_edicao, capa_url=e.capa_url)
        s.add(edicao); s.commit(); s.refresh(edicao)

    leitura = Leitura(edicao_id=edicao.id, usuario_id=u.id, status=e.status,
                      nota=e.nota, relato=e.relato, data=e.data)
    s.add(leitura); s.commit(); s.refresh(leitura)
    return {"leitura_id": leitura.id, "obra_id": obra.id, "edicao_id": edicao.id}


@app.get("/api/prateleira")
def listar(request: Request, s: Session = Depends(get_session)):
    u = usuario_sessao(request, s)
    rows = s.exec(select(Leitura, Edicao, Obra)
                  .join(Edicao, Leitura.edicao_id == Edicao.id)
                  .join(Obra, Edicao.obra_id == Obra.id)
                  .where(Leitura.usuario_id == u.id)
                  .order_by(Leitura.criado_em.desc())).all()
    return [{
        "leitura_id": l.id, "status": l.status, "nota": l.nota,
        "relato": l.relato, "data": l.data,
        "titulo": o.titulo, "autor": o.autor,
        "editora": ed.editora, "tradutor": ed.tradutor,
        "ano": ed.ano, "isbn": ed.isbn, "capa_url": ed.capa_url,
    } for (l, ed, o) in rows]


@app.get("/")
def home():
    return FileResponse(AQUI / "index.html")
