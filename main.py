"""
Lombada — versão de arquivo único (pra colar fácil no celular).
Tudo aqui: modelo Obra/Edicao/Leitura + Open Library + API + serve o front.
O front é o index.html ao lado deste arquivo.
"""
import os
import unicodedata
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional

import httpx
from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlmodel import SQLModel, Field, create_engine, Session, select

# ───────────────────────── banco ─────────────────────────
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///lombada.db")
_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, echo=False, connect_args=_args)


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
    status: str = "Lido"
    nota: Optional[float] = None
    relato: str = ""
    data: str = ""
    criado_em: datetime = Field(default_factory=datetime.utcnow)


# ──────────────────── Open Library ────────────────────
BASE = "https://openlibrary.org"
COVERS = "https://covers.openlibrary.org"
TIMEOUT = 12.0
LANG = {"por": "Português", "eng": "Inglês", "rus": "Russo", "fre": "Francês",
        "spa": "Espanhol", "ger": "Alemão", "ita": "Italiano", "jpn": "Japonês"}


def _lang(code):
    return LANG.get(code, code)


def _sem_acento(s):
    return "".join(c for c in unicodedata.normalize("NFD", s)
                   if unicodedata.category(c) != "Mn").lower()


def ol_buscar(q, limite=8):
    fields = "key,title,author_name,first_publish_year,cover_i,language"
    with httpx.Client(timeout=TIMEOUT) as c:
        r = c.get(f"{BASE}/search.json",
                  params={"q": q, "fields": fields, "limit": limite})
        r.raise_for_status()
        docs = r.json().get("docs", [])
    out = []
    for d in docs:
        cover_i = d.get("cover_i")
        out.append({
            "work_key": d.get("key", ""),
            "titulo": d.get("title", ""),
            "autor": (d.get("author_name") or ["—"])[0],
            "ano": d.get("first_publish_year"),
            "idioma_original": _lang((d.get("language") or [""])[0]),
            "capa_url": f"{COVERS}/b/id/{cover_i}-M.jpg" if cover_i else "",
        })
    return out


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
    with httpx.Client(timeout=TIMEOUT) as c:
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
            "editora": (ed.get("publishers") or [""])[0],
            "tradutor": _tradutor(ed),
            "isbn": isbn,
            "idioma": _lang(lang_code),
            "ano": ano,
            "capa_url": f"{COVERS}/b/isbn/{isbn}-M.jpg" if isbn else "",
        })
    out.sort(key=lambda e: (e["editora"] == "", -(e["ano"] or 0)))
    return out


# ──────────────────────── app ────────────────────────
@asynccontextmanager
async def lifespan(app):
    SQLModel.metadata.create_all(engine)
    yield


app = FastAPI(title="Lombada", lifespan=lifespan)
AQUI = Path(__file__).resolve().parent


def get_session():
    with Session(engine) as s:
        yield s


@app.get("/api/buscar")
def buscar(q: str = Query(..., min_length=2)):
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
def adicionar(e: EntradaPrateleira, s: Session = Depends(get_session)):
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

    leitura = Leitura(edicao_id=edicao.id, status=e.status, nota=e.nota,
                      relato=e.relato, data=e.data)
    s.add(leitura); s.commit(); s.refresh(leitura)
    return {"leitura_id": leitura.id, "obra_id": obra.id, "edicao_id": edicao.id}


@app.get("/api/prateleira")
def listar(s: Session = Depends(get_session)):
    rows = s.exec(select(Leitura, Edicao, Obra)
                  .join(Edicao, Leitura.edicao_id == Edicao.id)
                  .join(Obra, Edicao.obra_id == Obra.id)
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
      
