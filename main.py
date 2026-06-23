"""
Lombada — arquivo único.
Open Library (busca + edições) + Google Books + MercadoEditorial (tradutor + capa BR).
Busca por título OU por ISBN (cruza ME + Google + OL). Proxy de capa (/api/capa).
Identidade anônima (handle fofo, sem login): 1ª visita cria usuário; prateleira por usuário;
o handle viaja estampado no card. email/senha ficam pra um "garantir conta" futuro (opcionais).
Front é o index.html ao lado.
"""
import os
import re
import socket
import random
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
from fastapi.responses import FileResponse, Response, HTMLResponse
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
    handle: str = Field(index=True, unique=True)
    email: Optional[str] = Field(default=None, index=True, unique=True)
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
# idioma vem em 3 letras (Open Library) OU 2 letras (Google Books) — cobrimos os dois.
LANG = {"por": "Português", "eng": "Inglês", "rus": "Russo", "fre": "Francês",
        "spa": "Espanhol", "ger": "Alemão", "ita": "Italiano", "jpn": "Japonês"}
LANG2 = {"pt": "Português", "en": "Inglês", "ru": "Russo", "fr": "Francês",
         "es": "Espanhol", "de": "Alemão", "it": "Italiano", "ja": "Japonês"}


def _lang(code):
    code = (code or "").lower().strip()
    return LANG.get(code) or LANG2.get(code) or code


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


def _me_texto(v):
    if isinstance(v, dict):
        return (v.get("nome") or v.get("name") or "").strip()
    if isinstance(v, str):
        return v.strip()
    return ""


def _me_nome_pessoa(item):
    """Monta 'Nome Sobrenome' a partir de um item de contribuição do ME."""
    if isinstance(item, str):
        return item.strip()
    if not isinstance(item, dict):
        return ""
    nome = (item.get("nome") or item.get("name") or "").strip()
    sobr = (item.get("sobrenome") or "").strip()
    junto = (nome + " " + sobr).strip()
    return junto or nome


# códigos ONIX/ME de tradutor: B06 (ONIX) e 5 (tabela numérica do ME v1.2)
_COD_TRADUTOR = {"b06", "5"}


def _me_contribuinte(livro, alvos_texto, alvos_codigo):
    """Extrai o nome de um contribuinte por papel, cobrindo os dois formatos do ME:
       - dict {papel: gente}  (formato antigo)
       - list [{nome, sobrenome, tipo_de_contribuicao, codigo_contribuicao}]  (v1.2)
       alvos_texto: substrings a procurar no papel (sem acento). ex: ('tradu',)
       alvos_codigo: códigos numéricos/ONIX aceitos. ex: {'b06','5'}
    """
    contrib = (livro.get("contribuicao") or livro.get("contribuicoes")
               or livro.get("contributors") or {})
    if isinstance(contrib, dict):
        for papel, gente in contrib.items():
            if any(a in _sem_acento(papel) for a in alvos_texto):
                return _me_nome_pessoa(gente if not isinstance(gente, list)
                                       else (gente[0] if gente else {}))
    elif isinstance(contrib, list):
        for item in contrib:
            if not isinstance(item, dict):
                continue
            papel = _sem_acento(str(item.get("tipo_de_contribuicao")
                                    or item.get("tipo") or item.get("papel") or ""))
            cod = str(item.get("codigo_contribuicao") or "").lower().strip()
            if any(a in papel for a in alvos_texto) or cod in alvos_codigo:
                return _me_nome_pessoa(item)
    return ""


def _me_autor(livro):
    """Autor a partir da contribuição (código 1 / 'Autor'), senão campo solto."""
    a = _me_contribuinte(livro, ("autor", "author"), {"a01", "1"})
    if a:
        return a
    return _me_texto(livro.get("autor") or livro.get("autores"))


def _ano_de_data(data):
    m = re.search(r"\b(\d{4})\b", str(data or ""))
    return int(m.group(1)) if m else None


def normalizar_isbn(q):
    """Devolve o ISBN-10/13 limpo se a query FOR um ISBN; '' caso contrário."""
    compactado = re.sub(r"[^0-9Xx]", "", (q or "").strip()).upper()
    if len(compactado) == 10 and re.fullmatch(r"[0-9]{9}[0-9X]", compactado):
        return compactado
    if len(compactado) == 13 and re.fullmatch(r"[0-9]{13}", compactado):
        return compactado
    return ""


def _isbn_exato(isbn, candidatos):
    alvo = normalizar_isbn(isbn)
    return bool(alvo and alvo in {normalizar_isbn(c) for c in (candidatos or [])})


@lru_cache(maxsize=512)
def _gbooks_capa(isbn):
    info = _gbooks_info(isbn)
    return info.get("capa", "") if info else ""


@lru_cache(maxsize=512)
def _gbooks_info(isbn):
    """Metadados do Google Books por ISBN (sem cadastro). {} se não achar."""
    if not isbn:
        return {}
    try:
        with httpx.Client(timeout=TIMEOUT) as c:
            r = c.get(GBOOKS, params={"q": f"isbn:{isbn}", "country": "BR"})
            r.raise_for_status()
            items = r.json().get("items", []) or []
        if not items:
            return {}
        info = items[0].get("volumeInfo", {}) or {}
        img = info.get("imageLinks") or {}
        capa = (img.get("thumbnail") or img.get("smallThumbnail") or "").replace("http://", "https://")
        return {
            "titulo": info.get("title", "") or "",
            "autor": (info.get("authors") or [""])[0],
            "editora": info.get("publisher", "") or "",
            "ano": _ano_de_data(info.get("publishedDate", "")),
            "idioma": _lang(info.get("language") or ""),
            "capa": capa,
        }
    except Exception:
        return {}


@lru_cache(maxsize=512)
def _me_full(isbn):
    """Tudo que dá pra extrair do MercadoEditorial por ISBN (agência BR). {} se nada."""
    if not isbn:
        return {}
    try:
        with httpx.Client(timeout=TIMEOUT, headers=_UA) as c:
            r = c.get(MERCADOEDITORIAL, params={"isbn": isbn})
            r.raise_for_status()
            data = r.json()
        books = data.get("books") or data.get("book") or []
        if isinstance(books, dict):
            books = [books]
        if not books:
            return {}
        return _me_normaliza(books[0])
    except Exception:
        return {}


def _me_normaliza(livro):
    """Pega um registro cru do ME e devolve o dicionário padrão da Lombada."""
    if not isinstance(livro, dict):
        return {}
    tradutor = _me_contribuinte(livro, ("tradu", "translat"), _COD_TRADUTOR)
    capa = (livro.get("imagem_primeira_capa")
            or livro.get("imagem") or "").replace("http://", "https://")
    ano = None
    for campo in ("ano_edicao", "ano", "data_publicacao", "data"):
        ano = _ano_de_data(livro.get(campo))
        if ano:
            break
    isbn = (livro.get("isbn") or livro.get("isbn13")
            or livro.get("codigo_de_barras") or "").strip()
    return {
        "tradutor": tradutor,
        "autor": _me_autor(livro),
        "capa": capa,
        "titulo": _me_texto(livro.get("titulo")),
        "editora": _me_texto(livro.get("editora")),
        "ano": ano,
        "idioma": "Português",  # registro do ME = livro publicado no Brasil
        "isbn": normalizar_isbn(isbn) or isbn,
        "paginas": livro.get("numero_paginas") or livro.get("paginas") or None,
        "sinopse": (_me_texto(livro.get("sinopse")) or "").strip(),
    }


def _mercadoeditorial(isbn):
    """Compatibilidade: (tradutor, capa) a partir do registro completo do ME."""
    f = _me_full(isbn)
    return (f.get("tradutor", ""), f.get("capa", "")) if f else ("", "")


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


# ───────────── busca por título: ME (BR) primário, Google fallback ─────────────
def _doc_de_me(livro):
    """Converte um registro do ME numa 'obra' no formato que o front espera,
       já com a edição embutida (isbn_match) — porque ME já é a edição BR."""
    n = _me_normaliza(livro)
    if not n.get("titulo"):
        return None
    isbn = n.get("isbn") or ""
    edicao = {
        "ol_edition_key": ("isbn:" + isbn) if isbn else None,
        "titulo_edicao": n["titulo"],
        "editora": n.get("editora", ""),
        "tradutor": n.get("tradutor", ""),
        "isbn": isbn,
        "idioma": "Português",
        "ano": n.get("ano"),
        "capa_url": n.get("capa", ""),
    }
    return {
        "work_key": ("isbn:" + isbn) if isbn else ("me:" + n["titulo"][:60]),
        "titulo": n["titulo"],
        "autor": n.get("autor") or "—",
        "ano": n.get("ano"),
        "idioma_original": "Português",
        "tem_pt": True,
        "capa_url": n.get("capa", ""),
        "isbn_match": True,
        "edicao_isbn": edicao,
        "_fonte": "me",
    }


def me_buscar(titulo, limite=12):
    """Busca por título no MercadoEditorial (catálogo BR). Lista de 'obras' ou []."""
    if not titulo:
        return []
    try:
        with httpx.Client(timeout=TIMEOUT, headers=_UA) as c:
            r = c.get(MERCADOEDITORIAL, params={"titulo": titulo})
            r.raise_for_status()
            data = r.json()
    except Exception:
        return []
    books = data.get("books") or data.get("book") or []
    if isinstance(books, dict):
        books = [books]
    out = []
    vistos = set()
    for livro in books:
        doc = _doc_de_me(livro)
        if not doc:
            continue
        chave = (doc["isbn_match"] and doc["edicao_isbn"]["isbn"]) or _sem_acento(doc["titulo"])
        if chave in vistos:
            continue
        vistos.add(chave)
        out.append(doc)
        if len(out) >= limite:
            break
    # relevância: título que bate com a busca sobe
    out.sort(key=lambda o: _relevancia(o["titulo"], titulo))
    return out


def gbooks_buscar(q, limite=12):
    """Busca por texto no Google Books. Lista de 'obras' no formato do front, ou []."""
    if not q:
        return []
    try:
        with httpx.Client(timeout=TIMEOUT, headers=_UA) as c:
            r = c.get(GBOOKS, params={"q": q, "country": "BR",
                                      "maxResults": min(limite, 40), "langRestrict": "pt"})
            r.raise_for_status()
            items = r.json().get("items", []) or []
    except Exception:
        return []
    out = []
    vistos = set()
    for it in items:
        info = it.get("volumeInfo", {}) or {}
        titulo = (info.get("title") or "").strip()
        if not titulo:
            continue
        ids = info.get("industryIdentifiers") or []
        isbn = ""
        for d in ids:
            if d.get("type") == "ISBN_13":
                isbn = d.get("identifier", ""); break
        if not isbn and ids:
            isbn = ids[0].get("identifier", "")
        isbn = normalizar_isbn(isbn) or isbn
        chave = isbn or _sem_acento(titulo)
        if chave in vistos:
            continue
        vistos.add(chave)
        img = info.get("imageLinks") or {}
        capa = (img.get("thumbnail") or img.get("smallThumbnail") or "").replace("http://", "https://")
        idioma = _lang(info.get("language") or "")
        out.append({
            "work_key": ("isbn:" + isbn) if isbn else ("gb:" + (it.get("id") or titulo[:40])),
            "titulo": titulo,
            "autor": (info.get("authors") or ["—"])[0],
            "ano": _ano_de_data(info.get("publishedDate", "")),
            "idioma_original": idioma,
            "tem_pt": idioma == "Português",
            "capa_url": capa,
            "isbn_match": bool(isbn),
            "edicao_isbn": ({
                "ol_edition_key": ("isbn:" + isbn) if isbn else None,
                "titulo_edicao": titulo,
                "editora": info.get("publisher", "") or "",
                "tradutor": "",
                "isbn": isbn,
                "idioma": idioma,
                "ano": _ano_de_data(info.get("publishedDate", "")),
                "capa_url": capa,
            } if isbn else None),
            "_fonte": "gb",
        })
        if len(out) >= limite:
            break
    out.sort(key=lambda o: (_relevancia(o["titulo"], q),
                            0 if o["tem_pt"] else 1,
                            -(o["ano"] or 0)))
    return out


# Quantos resultados consideramos "suficiente" no ME antes de completar com Google.
# Ajuste este número se a busca vier curta demais ou misturada demais.
ME_MIN_RESULTADOS = 5


def buscar_titulo(q):
    """Busca por título BR-first: ME primário; completa/cai pro Google Books se vier pouco."""
    docs_me = me_buscar(q)
    if len(docs_me) >= ME_MIN_RESULTADOS:
        return docs_me

    # ME veio fraco — completa com Google Books, sem duplicar por ISBN/título
    docs_gb = gbooks_buscar(q)
    if not docs_me:
        return docs_gb if docs_gb else ol_buscar(q)

    vistos = set()
    for d in docs_me:
        isbn = d.get("edicao_isbn", {}) and d["edicao_isbn"].get("isbn")
        vistos.add(isbn or _sem_acento(d["titulo"]))
    combinado = list(docs_me)
    for d in docs_gb:
        isbn = d.get("edicao_isbn", {}) and (d["edicao_isbn"] or {}).get("isbn")
        chave = isbn or _sem_acento(d["titulo"])
        if chave not in vistos:
            vistos.add(chave)
            combinado.append(d)
    return combinado


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


# ───────────── busca por ISBN (cruza ME + Google + OL) ─────────────
@lru_cache(maxsize=256)
def _ol_isbn(isbn):
    """Edição pela Open Library via /isbn/{isbn}.json. {} se não achar/não bater."""
    if not isbn:
        return {}
    try:
        with httpx.Client(timeout=TIMEOUT, headers=_UA, follow_redirects=True) as c:
            r = c.get(f"{BASE}/isbn/{isbn}.json")
            if r.status_code == 404:
                return {}
            r.raise_for_status()
            ed = r.json()
    except Exception:
        return {}

    isbns = (ed.get("isbn_13") or []) + (ed.get("isbn_10") or [])
    if isbns and not _isbn_exato(isbn, isbns):
        return {}

    lang_code = ""
    if ed.get("languages"):
        lang_code = ed["languages"][0].get("key", "").rsplit("/", 1)[-1]
    work_key = ""
    if ed.get("works"):
        work_key = ed["works"][0].get("key") or ""

    return {
        "ol_edition_key": ed.get("key", ""),
        "titulo": ed.get("title", "") or "",
        "editora": (ed.get("publishers") or [""])[0],
        "tradutor": _tradutor(ed),
        "idioma": _lang(lang_code),
        "ano": _ano_de_data(ed.get("publish_date", "")),
        "work_key": work_key,
    }


def _edicao_por_isbn(isbn):
    """Acha UMA edição pelo ISBN cruzando as três fontes (BR-first na fusão).
    Devolve o doc no formato que o front espera (com isbn_match + edicao_isbn), ou None."""
    isbn = normalizar_isbn(isbn)
    if not isbn:
        return None

    with _fut.ThreadPoolExecutor(max_workers=3) as ex:
        f_me = ex.submit(_me_full, isbn)
        f_gb = ex.submit(_gbooks_info, isbn)
        f_ol = ex.submit(_ol_isbn, isbn)
        me, gb, ol = f_me.result(), f_gb.result(), f_ol.result()

    if not me and not gb and not ol:
        return None

    titulo = (me.get("titulo") or gb.get("titulo") or ol.get("titulo") or "").strip()
    autor = gb.get("autor") or "—"
    editora = me.get("editora") or ol.get("editora") or gb.get("editora") or ""
    tradutor = me.get("tradutor") or ol.get("tradutor") or ""   # ME primeiro (é o dado BR)
    ano = me.get("ano") or gb.get("ano") or ol.get("ano")
    idioma = me.get("idioma") or ol.get("idioma") or gb.get("idioma") or ""
    capa = me.get("capa") or gb.get("capa") or ol.get("capa_url") or f"{COVERS}/b/isbn/{isbn}-L.jpg"
    work_key = ol.get("work_key") or ("isbn:" + isbn)
    if not titulo:
        titulo = "Edição " + isbn

    edicao = {
        "ol_edition_key": ol.get("ol_edition_key") or ("isbn:" + isbn),
        "titulo_edicao": titulo,
        "editora": editora,
        "tradutor": tradutor,
        "isbn": isbn,
        "idioma": idioma,
        "ano": ano,
        "capa_url": capa,
    }
    return {
        "work_key": work_key,
        "titulo": titulo,
        "autor": autor,
        "ano": ano,
        "idioma_original": idioma,
        "tem_pt": idioma == "Português",
        "capa_url": capa,
        "isbn_match": True,
        "edicao_isbn": edicao,
    }


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


@app.get("/api/eu")
def eu(request: Request, s: Session = Depends(get_session)):
    u = usuario_sessao(request, s)
    return {"handle": u.handle, "nome": u.nome, "email": u.email}


@app.get("/api/buscar")
def buscar(q: str = Query(..., min_length=2)):
    isbn = normalizar_isbn(q)
    if isbn:
        try:
            achado = _edicao_por_isbn(isbn)
        except Exception:
            achado = None
        return [achado] if achado else []
    try:
        docs = buscar_titulo(q)
        if docs:
            return docs
        # último recurso: Open Library direto
        return ol_buscar(q)
    except Exception:
        try:
            return ol_buscar(q)
        except Exception as e:
            raise HTTPException(502, f"busca indisponível: {e}")


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


# ───────────── editar / remover leitura ─────────────
class PatchLeitura(BaseModel):
    status: Optional[str] = None
    nota: Optional[float] = None
    relato: Optional[str] = None
    data: Optional[str] = None


@app.patch("/api/prateleira/{leitura_id}")
def editar_leitura(leitura_id: int, patch: PatchLeitura, request: Request,
                   s: Session = Depends(get_session)):
    u = usuario_sessao(request, s)
    l = s.get(Leitura, leitura_id)
    if not l or l.usuario_id != u.id:
        raise HTTPException(404, "leitura não encontrada")
    for campo, valor in patch.model_dump(exclude_unset=True).items():
        setattr(l, campo, valor)
    s.add(l); s.commit(); s.refresh(l)
    return {"leitura_id": l.id, "status": l.status, "nota": l.nota,
            "relato": l.relato, "data": l.data}


@app.delete("/api/prateleira/{leitura_id}")
def remover_leitura(leitura_id: int, request: Request,
                    s: Session = Depends(get_session)):
    u = usuario_sessao(request, s)
    l = s.get(Leitura, leitura_id)
    if not l or l.usuario_id != u.id:
        raise HTTPException(404, "leitura não encontrada")
    s.delete(l); s.commit()
    return {"ok": True}


# ───────────── estante pública (/u/handle) ─────────────
def _esc(s):
    return (str(s if s is not None else "")
            .replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def _estrelas(n):
    n = n or 0
    out = ""
    for i in range(1, 6):
        out += "★" if i <= n else ("⯪" if i - 0.5 == n else "☆")
    return out


def _leituras_de(s, usuario_id):
    rows = s.exec(select(Leitura, Edicao, Obra)
                  .join(Edicao, Leitura.edicao_id == Edicao.id)
                  .join(Obra, Edicao.obra_id == Obra.id)
                  .where(Leitura.usuario_id == usuario_id)
                  .order_by(Leitura.criado_em.desc())).all()
    return [{
        "status": l.status, "nota": l.nota, "relato": l.relato, "data": l.data,
        "titulo": o.titulo, "autor": o.autor,
        "editora": ed.editora, "tradutor": ed.tradutor,
        "ano": ed.ano, "isbn": ed.isbn, "capa_url": ed.capa_url,
    } for (l, ed, o) in rows]


_FONTES = ('<link rel="preconnect" href="https://fonts.googleapis.com">'
           '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
           '<link href="https://fonts.googleapis.com/css2?'
           'family=Fraunces:ital,opsz,wght@0,9..144,400;0,9..144,600;1,9..144,400;1,9..144,600'
           '&family=Spectral:ital,wght@0,400;1,400&family=Space+Mono:wght@400;700&display=swap" '
           'rel="stylesheet">')

_CSS = """
:root{--paper:#ECE4D4;--paper-3:#D6CBB3;--ink:#1A1714;--ink-2:#3A322A;--dim:#6F6655;--gold:#A8842F;
--rule:rgba(26,23,20,.18);--shadow:6px 8px 0 rgba(26,23,20,.12),1px 2px 0 rgba(26,23,20,.25)}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--paper);color:var(--ink);font-family:"Spectral",Georgia,serif;-webkit-font-smoothing:antialiased}
a{color:inherit;text-decoration:none}
.wrap{max-width:560px;margin:0 auto;padding:26px 16px 60px}
.wordmark{font-family:"Fraunces",serif;font-style:italic;font-weight:600;font-size:22px}
.wordmark .dot{color:var(--gold)}
.head{border-bottom:1px solid var(--rule);padding-bottom:18px;margin-bottom:22px}
.label{font-family:"Space Mono",monospace;font-size:10px;letter-spacing:.16em;text-transform:uppercase;color:var(--dim)}
h1{font-family:"Fraunces",serif;font-style:italic;font-weight:400;font-size:30px;line-height:1.05;margin:14px 0 4px}
.count{font-family:"Space Mono",monospace;font-size:11px;color:var(--ink-2);letter-spacing:.04em}
.wall{display:grid;grid-template-columns:repeat(2,1fr);gap:18px 14px}
@media(min-width:420px){.wall{grid-template-columns:repeat(3,1fr)}}
.cover{position:relative;aspect-ratio:2/3;background:var(--paper-3);box-shadow:var(--shadow);overflow:hidden}
.cover img{width:100%;height:100%;object-fit:cover;display:block}
.cover .fb{position:absolute;inset:0;display:flex;align-items:flex-end;padding:12px;font-family:"Fraunces",serif;font-style:italic;font-size:18px;line-height:1.1;color:rgba(26,23,20,.75)}
.cover .stars{position:absolute;left:6px;bottom:6px;font-family:"Space Mono",monospace;font-size:11px;color:var(--paper);background:rgba(26,23,20,.78);padding:3px 6px;letter-spacing:.05em}
.t{font-family:"Fraunces",serif;font-style:italic;font-size:15px;line-height:1.15;margin-top:8px}
.a{font-size:12px;color:var(--dim);margin-top:2px}
.cta{display:block;text-align:center;margin:34px auto 0;max-width:360px;background:var(--ink);color:var(--paper);padding:16px;font-family:"Space Mono",monospace;font-size:12px;letter-spacing:.18em;text-transform:uppercase}
.empty{padding:40px 6px;text-align:center;color:var(--dim);font-style:italic}
"""


def _pagina(titulo, corpo, og=None):
    og_tags = ""
    if og:
        for k, v in og.items():
            og_tags += f'<meta property="og:{k}" content="{_esc(v)}">'
        og_tags += '<meta name="twitter:card" content="summary_large_image">'
    return ("<!DOCTYPE html><html lang=\"pt-BR\"><head><meta charset=\"utf-8\">"
            "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
            f"<title>{_esc(titulo)}</title>{og_tags}{_FONTES}"
            f"<style>{_CSS}</style></head><body><div class=\"wrap\">{corpo}</div></body></html>")


def _card_publico(l):
    cap = l.get("capa_url") or ""
    t = _esc(l.get("titulo"))
    a = _esc(l.get("autor"))
    stars = f'<div class="stars">{_estrelas(l.get("nota"))}</div>' if l.get("nota") else ""
    if cap:
        cover = (f'<div class="cover"><img src="{_esc(cap)}" alt="" loading="lazy" '
                 "onerror=\"this.style.display='none';this.nextElementSibling.style.display='flex'\">"
                 f'<div class="fb" style="display:none">{t}</div>{stars}</div>')
    else:
        cover = f'<div class="cover"><div class="fb">{t}</div>{stars}</div>'
    return f'<div class="book">{cover}<div class="t">{t}</div><div class="a">{a}</div></div>'


def render_estante_publica(u, leituras):
    n = len(leituras)
    cont = "1 livro" if n == 1 else f"{n} livros"
    grid = ('<div class="wall">' + "".join(_card_publico(l) for l in leituras) + "</div>"
            if leituras else '<div class="empty">estante ainda vazia.</div>')
    corpo = (f'<div class="head"><div class="wordmark">LOMBADA<span class="dot">.</span></div>'
             f'<div class="label" style="margin-top:14px">a estante de</div>'
             f'<h1>@{_esc(u.handle)}</h1><div class="count">{cont}</div></div>'
             f'{grid}<a class="cta" href="/">criar a minha estante →</a>')
    og = {"title": f"a estante de @{u.handle}", "type": "website",
          "description": f"{cont} · veja o que @{u.handle} anda lendo na Lombada"}
    primeira = next((l.get("capa_url") for l in leituras if l.get("capa_url")), "")
    if primeira:
        og["image"] = primeira
    return _pagina(f"@{u.handle} · Lombada", corpo, og)


@app.get("/api/u/{handle}")
def estante_json(handle: str, s: Session = Depends(get_session)):
    u = s.exec(select(Usuario).where(Usuario.handle == handle.lower().strip())).first()
    if not u:
        raise HTTPException(404, "estante não encontrada")
    return {"handle": u.handle, "nome": u.nome, "leituras": _leituras_de(s, u.id)}


@app.get("/u/{handle}")
def estante_publica(handle: str, s: Session = Depends(get_session)):
    u = s.exec(select(Usuario).where(Usuario.handle == handle.lower().strip())).first()
    if not u:
        corpo = ('<div class="wordmark">LOMBADA<span class="dot">.</span></div>'
                 '<div class="empty">essa estante não existe (ou o link veio torto).</div>'
                 '<a class="cta" href="/">criar a minha estante →</a>')
        return HTMLResponse(_pagina("estante não encontrada · Lombada", corpo), status_code=404)
    return HTMLResponse(render_estante_publica(u, _leituras_de(s, u.id)))


@app.get("/")
def home():
    return FileResponse(AQUI / "index.html")