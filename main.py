"""
Lombada — app FastAPI e rotas.
"""
import ipaddress
import os
import socket
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional
from uuid import uuid4
from urllib.parse import urlparse

import httpx
from fastapi import FastAPI, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlmodel import SQLModel, Session, select
from starlette.middleware.sessions import SessionMiddleware

from models import SECRET_KEY, engine, Usuario, Obra, Edicao, Leitura, get_session, migrar
from auth import usuario_sessao, router as auth_router
from fontes import ol_edicoes, normalizar_isbn, TIMEOUT, _UA
from busca import _cache_get, _cache_set, buscar_titulo_v2, ol_buscar, _edicao_por_isbn
from publica import render_estante_publica, _leituras_de, _pagina, _esc

AQUI = Path(__file__).resolve().parent
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "true").lower() == "true"


# ─── lifespan ─────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app):
    SQLModel.metadata.create_all(engine)
    migrar()
    yield


app = FastAPI(title="Lombada", lifespan=lifespan)
app.add_middleware(
    SessionMiddleware,
    secret_key=SECRET_KEY,
    same_site="lax",
    https_only=COOKIE_SECURE,
)
app.mount("/static", StaticFiles(directory=str(AQUI / "static")), name="static")
app.include_router(auth_router)


# ─── proxy de capa (anti-SSRF) ────────────────────────────
def _host_publico(host: str) -> bool:
    if not host:
        return False
    try:
        infos = socket.getaddrinfo(host, None)
    except Exception:
        return False
    for _, _, _, _, sockaddr in infos:
        try:
            ip = ipaddress.ip_address(sockaddr[0])
        except ValueError:
            return False
        if (ip.is_private or ip.is_loopback or ip.is_link_local
                or ip.is_reserved or ip.is_multicast or ip.is_unspecified):
            return False
    return True


def proxy_capa(url: str) -> Response:
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


# ─── rotas ────────────────────────────────────────────────
@app.get("/api/eu")
def eu(request: Request, s: Session = Depends(get_session)):
    u = usuario_sessao(request, s)
    logado = bool(u.google_sub)
    return {
        "handle": u.handle,
        "nome": u.nome,
        "email": u.email,
        "logado": logado,
        "provedor": "google" if logado else "anonimo",
    }


@app.get("/api/buscar")
def buscar(q: str = Query(..., min_length=2), s: Session = Depends(get_session)):
    isbn = normalizar_isbn(q)
    if isbn:
        try:
            achado = _edicao_por_isbn(isbn)
        except Exception:
            achado = None
        return [achado] if achado else []

    cache = _cache_get(q, s)
    if cache:
        return cache

    try:
        docs = buscar_titulo_v2(q)
        if docs:
            _cache_set(q, docs, s)
            return docs
        docs = ol_buscar(q)
        _cache_set(q, docs, s)
        return docs
    except Exception:
        try:
            docs = ol_buscar(q)
            _cache_set(q, docs, s)
            return docs
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


# ─── prateleira ───────────────────────────────────────────
class EntradaPrateleira(BaseModel):
    work_key:        str
    titulo:          str
    autor:           str           = ""
    idioma_original: str           = ""
    ano_obra:        Optional[int] = None
    ol_edition_key:  Optional[str] = None
    editora:         str           = ""
    tradutor:        str           = ""
    isbn:            str           = ""
    idioma:          str           = ""
    ano_edicao:      Optional[int] = None
    capa_url:        str           = ""
    status:          str           = "Lido"
    nota:            Optional[float] = None
    relato:          str           = ""
    data:            str           = ""


STATUS_LEITURA = {"Lido", "Lendo", "Quero ler"}


def _validar_entrada_leitura(e):
    if not e.titulo.strip() or not e.autor.strip():
        raise HTTPException(422, "título e autor são obrigatórios")
    if e.status not in STATUS_LEITURA:
        raise HTTPException(422, "status inválido")


def _criar_leitura(e, usuario_id: int, s: Session, reutilizar_obra_manual: bool = False):
    _validar_entrada_leitura(e)
    obra = None
    if e.work_key:
        obra = s.exec(select(Obra).where(Obra.ol_work_key == e.work_key)).first()
    if not obra and reutilizar_obra_manual:
        obra = s.exec(
            select(Obra).where(Obra.titulo == e.titulo.strip(), Obra.autor == e.autor.strip())
        ).first()
    if not obra:
        obra = Obra(ol_work_key=e.work_key or f"manual:{uuid4().hex}",
                    titulo=e.titulo.strip(), autor=e.autor.strip(),
                    idioma_original=e.idioma_original.strip(), ano=e.ano_obra)
        s.add(obra); s.commit(); s.refresh(obra)
    edicao = None
    if e.ol_edition_key:
        edicao = s.exec(select(Edicao).where(Edicao.ol_edition_key == e.ol_edition_key)).first()
    if not edicao:
        edicao = Edicao(obra_id=obra.id, ol_edition_key=e.ol_edition_key,
                        editora=e.editora.strip(), tradutor=e.tradutor.strip(), isbn=e.isbn.strip(),
                        idioma=e.idioma.strip(), ano=e.ano_edicao, capa_url=e.capa_url.strip())
        s.add(edicao); s.commit(); s.refresh(edicao)
    leitura = Leitura(edicao_id=edicao.id, usuario_id=usuario_id, status=e.status,
                      nota=e.nota, relato=e.relato.strip(), data=e.data.strip())
    s.add(leitura); s.commit(); s.refresh(leitura)
    return leitura, obra, edicao


@app.post("/api/prateleira")
def adicionar(e: EntradaPrateleira, request: Request, s: Session = Depends(get_session)):
    u = usuario_sessao(request, s)
    leitura, obra, edicao = _criar_leitura(e, u.id, s)
    return {"leitura_id": leitura.id, "obra_id": obra.id, "edicao_id": edicao.id}


class EntradaManual(EntradaPrateleira):
    work_key: str = ""
    titulo_edicao: str = ""


@app.post("/api/manual")
def adicionar_manual(e: EntradaManual, request: Request, s: Session = Depends(get_session)):
    u = usuario_sessao(request, s)
    leitura, obra, edicao = _criar_leitura(e, u.id, s, reutilizar_obra_manual=True)
    return {"leitura_id": leitura.id, "obra_id": obra.id, "edicao_id": edicao.id}


@app.get("/api/prateleira")
def listar(request: Request, s: Session = Depends(get_session)):
    u = usuario_sessao(request, s)
    rows = s.exec(
        select(Leitura, Edicao, Obra)
        .join(Edicao, Leitura.edicao_id == Edicao.id)
        .join(Obra, Edicao.obra_id == Obra.id)
        .where(Leitura.usuario_id == u.id)
        .order_by(Leitura.criado_em.desc())
    ).all()
    return [{
        "leitura_id": l.id, "status": l.status, "nota": l.nota,
        "relato": l.relato, "data": l.data,
        "titulo": o.titulo, "autor": o.autor,
        "editora": ed.editora, "tradutor": ed.tradutor,
        "ano": ed.ano, "isbn": ed.isbn, "capa_url": ed.capa_url,
    } for (l, ed, o) in rows]


class PatchLeitura(BaseModel):
    status:  Optional[str]   = None
    nota:    Optional[float] = None
    relato:  Optional[str]   = None
    data:    Optional[str]   = None


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
def remover_leitura(leitura_id: int, request: Request, s: Session = Depends(get_session)):
    u = usuario_sessao(request, s)
    l = s.get(Leitura, leitura_id)
    if not l or l.usuario_id != u.id:
        raise HTTPException(404, "leitura não encontrada")
    s.delete(l); s.commit()
    return {"ok": True}


# ─── estante pública ──────────────────────────────────────
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
        corpo = (
            '<div class="wordmark">LOMBADA<span class="dot">.</span></div>'
            '<div class="empty">essa estante não existe (ou o link veio torto).</div>'
            '<a class="cta" href="/">criar a minha estante →</a>'
        )
        return HTMLResponse(_pagina("estante não encontrada · Lombada", corpo), status_code=404)
    return HTMLResponse(render_estante_publica(u, _leituras_de(s, u.id)))


@app.get("/")
def home():
    return FileResponse(AQUI / "index.html")
