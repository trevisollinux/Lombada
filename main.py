"""
Lombada — app FastAPI e rotas.
"""
import html
import ipaddress
import json
import os
import socket
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional
from uuid import uuid4
from datetime import datetime
from urllib.parse import urlparse

import httpx
from fastapi import FastAPI, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlmodel import SQLModel, Session, select, func
from starlette.middleware.sessions import SessionMiddleware

from models import SECRET_KEY, engine, Usuario, Obra, Edicao, Leitura, Follow, CatalogSuggestion, get_session, migrar
from auth import usuario_sessao, router as auth_router
from fontes import ol_edicoes, normalizar_isbn, TIMEOUT, _UA
from busca import _cache_get, _cache_set, buscar_titulo_v2, ol_buscar, _edicao_por_isbn
from publica import render_estante_publica, _leituras_de, _pagina, _esc, resumo_perfil_publico

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



ADMIN_EMAILS = {e.strip().lower() for e in os.getenv("ADMIN_EMAILS", "").split(",") if e.strip()}
SUGGESTION_TYPES = {"new_book", "new_edition", "correction", "cover"}


def _is_admin(u: Usuario) -> bool:
    return bool(u.email and u.email.lower().strip() in ADMIN_EMAILS)


def _require_admin(request: Request, s: Session) -> Usuario:
    u = usuario_sessao(request, s)
    if not _is_admin(u):
        raise HTTPException(403, "admin restrito")
    return u


def _clean_text(v, max_len: int = 240) -> str:
    if v is None:
        return ""
    v = str(v).replace("\x00", "").strip()
    v = html.escape(v, quote=False)
    return v[:max_len]


def _clean_url(v, max_len: int = 500) -> str:
    v = _clean_text(v, max_len)
    if not v:
        return ""
    p = urlparse(v)
    if p.scheme != "https" or not p.netloc:
        raise HTTPException(422, "URL da capa inválida")
    return v


def _entrada_payload(e: BaseModel) -> dict:
    d = e.model_dump()
    for k in ["titulo", "autor", "idioma_original", "titulo_edicao", "editora", "tradutor", "isbn", "idioma", "status", "relato", "data", "work_key"]:
        if k in d:
            d[k] = _clean_text(d.get(k), 500 if k == "relato" else 240)
    if "capa_url" in d:
        d["capa_url"] = _clean_url(d.get("capa_url"), 500) if d.get("capa_url") else ""
    return d


def _criar_sugestao(e: BaseModel, u: Usuario, s: Session, tipo: str = "new_book", target_type: str | None = None, target_id: int | None = None):
    if tipo not in SUGGESTION_TYPES:
        raise HTTPException(422, "tipo de sugestão inválido")
    payload = _entrada_payload(e)
    sug = CatalogSuggestion(
        tipo=tipo, status="pending", payload_json=json.dumps(payload, ensure_ascii=False),
        target_type=target_type, target_id=target_id, user_id=u.id, user_email=u.email or "",
    )
    s.add(sug); s.commit(); s.refresh(sug)
    return sug


def _buscar_catalogo_local(q: str, s: Session) -> list[dict]:
    termo = f"%{q.lower().strip()}%"
    rows = s.exec(
        select(Obra, Edicao)
        .join(Edicao, Edicao.obra_id == Obra.id)
        .where((func.lower(Obra.titulo).like(termo)) | (func.lower(Obra.autor).like(termo)) | (func.lower(Edicao.isbn).like(termo)))
        .limit(10)
    ).all()
    docs = []
    for obra, ed in rows:
        ed_doc = {
            "ol_edition_key": ed.ol_edition_key or f"local:{ed.id}", "titulo_edicao": obra.titulo,
            "editora": ed.editora, "tradutor": ed.tradutor, "isbn": ed.isbn, "idioma": ed.idioma,
            "ano": ed.ano, "capa_url": ed.capa_url,
        }
        docs.append({
            "work_key": obra.ol_work_key, "titulo": obra.titulo, "autor": obra.autor,
            "idioma_original": obra.idioma_original, "ano": obra.ano, "tem_pt": ed.idioma == "Português",
            "capa_url": ed.capa_url, "isbn_match": False, "edicao_isbn": ed_doc, "edicoes": [ed_doc], "_fonte": "local",
        })
    return docs


def _follow_counts(s: Session, usuario_id: int) -> dict:
    return {
        "followers_count": s.exec(select(func.count()).select_from(Follow).where(Follow.following_id == usuario_id)).one(),
        "following_count": s.exec(select(func.count()).select_from(Follow).where(Follow.follower_id == usuario_id)).one(),
    }


def _is_following(s: Session, follower_id: int | None, following_id: int) -> bool:
    if not follower_id or follower_id == following_id:
        return False
    return bool(s.exec(select(Follow).where(Follow.follower_id == follower_id, Follow.following_id == following_id)).first())


def _profile_social_payload(s: Session, perfil: Usuario, atual: Usuario | None = None) -> dict:
    atual_id = atual.id if atual else None
    return {
        **_follow_counts(s, perfil.id),
        "is_following": _is_following(s, atual_id, perfil.id),
        "is_me": bool(atual_id and atual_id == perfil.id),
    }


def _require_google_user(request: Request, s: Session) -> Usuario:
    u = usuario_sessao(request, s)
    if not u.google_sub:
        raise HTTPException(403, "Entre com Google para seguir leitores.")
    return u

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
        **_follow_counts(s, u.id),
    }


@app.get("/api/buscar")
def buscar(q: str = Query(..., min_length=2), s: Session = Depends(get_session)):
    locais = _buscar_catalogo_local(q, s)
    isbn = normalizar_isbn(q)
    if isbn:
        try:
            achado = _edicao_por_isbn(isbn)
        except Exception:
            achado = None
        return ([achado] if achado else []) + locais

    cache = _cache_get(q, s)
    if cache:
        return locais + cache

    try:
        docs = buscar_titulo_v2(q)
        if docs:
            _cache_set(q, docs, s)
            return locais + docs
        docs = ol_buscar(q)
        _cache_set(q, docs, s)
        return locais + docs
    except Exception:
        try:
            docs = ol_buscar(q)
            _cache_set(q, docs, s)
            return locais + docs
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


def _obra_social_payload(obra: Obra, s: Session, usuario_id: int | None = None):
    rows = s.exec(
        select(Leitura, Edicao, Obra, Usuario)
        .join(Edicao, Leitura.edicao_id == Edicao.id)
        .join(Obra, Edicao.obra_id == Obra.id)
        .join(Usuario, Leitura.usuario_id == Usuario.id)
        .where(Obra.id == obra.id)
        .order_by(Leitura.criado_em.desc())
    ).all()
    leituras = [l for (l, _ed, _o, _u) in rows]
    notas = [l.nota for l in leituras if l.nota is not None]
    por_edicao: dict[int, dict] = {}
    criticas = []
    minha = None
    for l, ed, _o, u in rows:
        bucket = por_edicao.setdefault(ed.id, {"leituras": 0, "notas": []})
        bucket["leituras"] += 1
        if l.nota is not None:
            bucket["notas"].append(l.nota)
        if usuario_id and l.usuario_id == usuario_id and minha is None:
            minha = {"leitura_id": l.id, "edicao_id": ed.id, "status": l.status}
        relato = (l.relato or "").strip()
        if l.publico and relato:
            criticas.append({
                "leitura_id": l.id, "nota": l.nota, "relato": relato, "data": l.data,
                "status": l.status, "spoiler": bool(l.spoiler),
                "criado_em": l.criado_em.isoformat(), "usuario": u.handle,
                "edicao_id": ed.id, "edicao": {
                    "editora": ed.editora, "ano": ed.ano, "tradutor": ed.tradutor,
                    "isbn": ed.isbn, "idioma": ed.idioma, "capa_url": ed.capa_url,
                }
            })
    edicoes = []
    ed_por_id = {ed.id: ed for (_l, ed, _o, _u) in rows}
    for ed_id, st in por_edicao.items():
        ed = ed_por_id.get(ed_id)
        edicoes.append({
            "edicao_id": ed_id,
            "leituras": st["leituras"],
            "media": round(sum(st["notas"]) / len(st["notas"]), 2) if st["notas"] else None,
            "edicao": {
                "editora": ed.editora if ed else "", "ano": ed.ano if ed else None,
                "tradutor": ed.tradutor if ed else "", "isbn": ed.isbn if ed else "",
                "idioma": ed.idioma if ed else "", "capa_url": ed.capa_url if ed else "",
            },
        })
    return {
        "obra": {"id": obra.id, "work_key": obra.ol_work_key, "titulo": obra.titulo, "autor": obra.autor},
        "estatisticas": {
            "leituras": len(leituras),
            "criticas": len(criticas),
            "media": round(sum(notas) / len(notas), 2) if notas else None,
        },
        "edicoes": edicoes,
        "criticas": criticas[:8],
        "destaques": sorted(criticas, key=lambda c: ((c.get("nota") or 0), len(c.get("relato") or "")), reverse=True)[:3],
        "minha_leitura": minha,
    }


@app.get("/api/obra/social")
def obra_social(work_key: str = "", titulo: str = "", autor: str = "", request: Request = None,
                s: Session = Depends(get_session)):
    u = usuario_sessao(request, s)
    obra = None
    if work_key:
        obra = s.exec(select(Obra).where(Obra.ol_work_key == work_key)).first()
    if not obra and titulo:
        stmt = select(Obra).where(func.lower(Obra.titulo) == titulo.lower().strip())
        if autor:
            stmt = stmt.where(func.lower(Obra.autor) == autor.lower().strip())
        obra = s.exec(stmt).first()
    if not obra:
        return {
            "obra": {"work_key": work_key, "titulo": titulo, "autor": autor},
            "estatisticas": {"leituras": 0, "criticas": 0, "media": None},
            "edicoes": [], "criticas": [], "destaques": [], "minha_leitura": None,
        }
    return _obra_social_payload(obra, s, u.id)


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
    publico:         bool          = False
    spoiler:         bool          = False
    data:            str           = ""


STATUS_LEITURA = {"Lido", "Lendo", "Quero ler"}


def _validar_entrada_leitura(e):
    if not e.titulo.strip() or not e.autor.strip():
        raise HTTPException(422, "título e autor são obrigatórios")
    if e.status not in STATUS_LEITURA:
        raise HTTPException(422, "status inválido")




def _norm_texto(valor):
    return " ".join((valor or "").strip().casefold().split())


def _isbn_norm(valor):
    return normalizar_isbn(valor or "")


def _fallback_edicao_match(obra_id: int, e):
    return (
        Edicao.obra_id == obra_id,
        func.lower(func.trim(Edicao.editora)) == _norm_texto(e.editora),
        Edicao.ano == e.ano_edicao,
        func.lower(func.trim(Edicao.tradutor)) == _norm_texto(e.tradutor),
    )


def _buscar_edicao_existente(e, obra: Obra, s: Session):
    if e.ol_edition_key:
        edicao = s.exec(select(Edicao).where(Edicao.ol_edition_key == e.ol_edition_key)).first()
        if edicao:
            return edicao
    isbn = _isbn_norm(e.isbn)
    if isbn:
        edicao = s.exec(select(Edicao).where(Edicao.isbn == isbn)).first()
        if edicao:
            return edicao
    return s.exec(select(Edicao).where(*_fallback_edicao_match(obra.id, e))).first()


def _buscar_leitura_duplicada(usuario_id: int, e, obra: Obra, edicao: Edicao, s: Session):
    leitura = s.exec(select(Leitura).where(Leitura.usuario_id == usuario_id, Leitura.edicao_id == edicao.id)).first()
    if leitura:
        return leitura, edicao
    if e.ol_edition_key:
        row = s.exec(
            select(Leitura, Edicao)
            .join(Edicao, Leitura.edicao_id == Edicao.id)
            .where(Leitura.usuario_id == usuario_id, Edicao.ol_edition_key == e.ol_edition_key)
        ).first()
        if row:
            return row
    isbn = _isbn_norm(e.isbn)
    if isbn:
        row = s.exec(
            select(Leitura, Edicao)
            .join(Edicao, Leitura.edicao_id == Edicao.id)
            .where(Leitura.usuario_id == usuario_id, Edicao.isbn == isbn)
        ).first()
        if row:
            return row
    row = s.exec(
        select(Leitura, Edicao)
        .join(Edicao, Leitura.edicao_id == Edicao.id)
        .where(Leitura.usuario_id == usuario_id, *_fallback_edicao_match(obra.id, e))
    ).first()
    return row or (None, None)

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
    edicao = _buscar_edicao_existente(e, obra, s)
    if not edicao:
        edicao = Edicao(obra_id=obra.id, ol_edition_key=e.ol_edition_key,
                        editora=e.editora.strip(), tradutor=e.tradutor.strip(), isbn=_isbn_norm(e.isbn),
                        idioma=e.idioma.strip(), ano=e.ano_edicao, capa_url=e.capa_url.strip())
        s.add(edicao); s.commit(); s.refresh(edicao)
    leitura_existente, edicao_existente = _buscar_leitura_duplicada(usuario_id, e, obra, edicao, s)
    if leitura_existente:
        raise HTTPException(409, {"duplicado": True, "leitura_id": leitura_existente.id, "edicao_id": edicao_existente.id})
    leitura = Leitura(edicao_id=edicao.id, usuario_id=usuario_id, status=e.status,
                      nota=e.nota, relato=e.relato.strip(), publico=bool(e.publico),
                      spoiler=bool(e.spoiler), data=e.data.strip())
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
    _validar_entrada_leitura(e)
    sug = _criar_sugestao(e, u, s, tipo="new_book")
    return {"suggestion_id": sug.id, "status": sug.status, "message": "Cadastro enviado para revisão. Se aprovado, aparecerá na Lombada."}


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
        "relato": l.relato, "publico": bool(l.publico), "spoiler": bool(l.spoiler), "data": l.data,
        "titulo": o.titulo, "autor": o.autor, "work_key": o.ol_work_key,
        "edicao_id": ed.id, "ol_edition_key": ed.ol_edition_key,
        "editora": ed.editora, "tradutor": ed.tradutor,
        "ano": ed.ano, "isbn": ed.isbn, "capa_url": ed.capa_url,
    } for (l, ed, o) in rows]


class PatchLeitura(BaseModel):
    status:  Optional[str]   = None
    nota:    Optional[float] = None
    relato:  Optional[str]   = None
    data:    Optional[str]   = None
    publico: Optional[bool]  = None
    spoiler: Optional[bool]  = None


@app.patch("/api/prateleira/{leitura_id}")
def editar_leitura(leitura_id: int, patch: PatchLeitura, request: Request,
                   s: Session = Depends(get_session)):
    u = usuario_sessao(request, s)
    l = s.get(Leitura, leitura_id)
    if not l or l.usuario_id != u.id:
        raise HTTPException(404, "leitura não encontrada")
    for campo, valor in patch.model_dump(exclude_unset=True).items():
        if campo == "status" and valor not in STATUS_LEITURA:
            raise HTTPException(422, "status inválido")
        if campo in {"relato", "data"} and valor is not None:
            valor = valor.strip()
        setattr(l, campo, valor)
    s.add(l); s.commit(); s.refresh(l)
    return {"leitura_id": l.id, "status": l.status, "nota": l.nota,
            "relato": l.relato, "publico": bool(l.publico), "spoiler": bool(l.spoiler), "data": l.data}


@app.delete("/api/prateleira/{leitura_id}")
def remover_leitura(leitura_id: int, request: Request, s: Session = Depends(get_session)):
    u = usuario_sessao(request, s)
    l = s.get(Leitura, leitura_id)
    if not l or l.usuario_id != u.id:
        raise HTTPException(404, "leitura não encontrada")
    s.delete(l); s.commit()
    return {"ok": True}



def _feed_tipo(l: Leitura) -> str:
    relato = (l.relato or "").strip()
    if l.publico and relato:
        return "wrote_review"
    if l.status == "Lendo":
        return "started_reading"
    if l.status == "Quero ler":
        return "wants_to_read"
    if l.status == "Lido":
        return "finished_reading"
    return "leitura_criada"


@app.get("/api/feed")
def feed(request: Request, s: Session = Depends(get_session), limit: int = Query(30, ge=1, le=50)):
    u = usuario_sessao(request, s)
    following_ids = s.exec(select(Follow.following_id).where(Follow.follower_id == u.id)).all()
    if not following_ids:
        return {"following_count": 0, "items": []}
    rows = s.exec(
        select(Leitura, Edicao, Obra, Usuario)
        .join(Edicao, Leitura.edicao_id == Edicao.id)
        .join(Obra, Edicao.obra_id == Obra.id)
        .join(Usuario, Leitura.usuario_id == Usuario.id)
        .where(Leitura.usuario_id.in_(following_ids))
        .order_by(Leitura.criado_em.desc())
        .limit(limit)
    ).all()
    items = []
    for l, ed, o, autor in rows:
        relato = (l.relato or "").strip()
        relato_feed = ""
        if l.publico and relato:
            relato_feed = relato[:220]
        items.append({
            "tipo": _feed_tipo(l),
            "usuario": {"handle": autor.handle, "nome": autor.nome},
            "livro": {"titulo": o.titulo, "autor": o.autor, "work_key": o.ol_work_key, "capa_url": ed.capa_url},
            "edicao": {"editora": ed.editora, "tradutor": ed.tradutor, "ano": ed.ano},
            "leitura": {
                "status": l.status, "nota": l.nota, "publico": bool(l.publico),
                "spoiler": bool(l.spoiler), "relato": relato_feed,
            },
            "created_at": l.criado_em.isoformat(),
        })
    return {"following_count": len(following_ids), "items": items}

# ─── estante pública ──────────────────────────────────────
@app.get("/api/u/{handle}")
def estante_json(handle: str, request: Request, s: Session = Depends(get_session)):
    u = s.exec(select(Usuario).where(Usuario.handle == handle.lower().strip())).first()
    if not u:
        raise HTTPException(404, "estante não encontrada")
    atual = usuario_sessao(request, s)
    leituras = _leituras_de(s, u.id)
    perfil = resumo_perfil_publico(leituras)
    return {"handle": u.handle, "nome": u.nome, "leituras": leituras, **perfil, **_profile_social_payload(s, u, atual)}


@app.post("/api/u/{handle}/follow")
def seguir_usuario(handle: str, request: Request, s: Session = Depends(get_session)):
    atual = _require_google_user(request, s)
    alvo = s.exec(select(Usuario).where(Usuario.handle == handle.lower().strip())).first()
    if not alvo:
        raise HTTPException(404, "perfil não encontrado")
    if atual.id == alvo.id:
        raise HTTPException(400, "você não pode seguir a si mesmo")
    follow = s.exec(select(Follow).where(Follow.follower_id == atual.id, Follow.following_id == alvo.id)).first()
    if not follow:
        s.add(Follow(follower_id=atual.id, following_id=alvo.id)); s.commit()
    return {"following": True, **_follow_counts(s, alvo.id)}


@app.delete("/api/u/{handle}/follow")
def deixar_de_seguir_usuario(handle: str, request: Request, s: Session = Depends(get_session)):
    atual = _require_google_user(request, s)
    alvo = s.exec(select(Usuario).where(Usuario.handle == handle.lower().strip())).first()
    if not alvo:
        raise HTTPException(404, "perfil não encontrado")
    follow = s.exec(select(Follow).where(Follow.follower_id == atual.id, Follow.following_id == alvo.id)).first()
    if follow:
        s.delete(follow); s.commit()
    return {"following": False, **_follow_counts(s, alvo.id)}


@app.get("/u/{handle}")
def estante_publica(handle: str, request: Request, s: Session = Depends(get_session)):
    u = s.exec(select(Usuario).where(Usuario.handle == handle.lower().strip())).first()
    if not u:
        corpo = (
            '<div class="wordmark">LOMBADA<span class="dot">.</span></div>'
            '<div class="empty">essa estante não existe (ou o link veio torto).</div>'
            '<a class="cta" href="/">criar a minha estante →</a>'
        )
        return HTMLResponse(_pagina("estante não encontrada · Lombada", corpo), status_code=404)
    atual = usuario_sessao(request, s)
    return HTMLResponse(render_estante_publica(u, _leituras_de(s, u.id), _profile_social_payload(s, u, atual)))



# ─── admin de catálogo ────────────────────────────────────
@app.get("/admin")
def admin_page(request: Request, s: Session = Depends(get_session)):
    _require_admin(request, s)
    rows = s.exec(select(CatalogSuggestion).where(CatalogSuggestion.status == "pending").order_by(CatalogSuggestion.created_at.desc())).all()
    items = []
    for sug in rows:
        payload = _esc(sug.payload_json or "{}")
        items.append(
            f'<article class="card-form" style="margin:16px 0">'
            f'<div class="meta">#{sug.id} · {_esc(sug.tipo)} · {_esc(sug.user_email or str(sug.user_id or ""))} · {sug.created_at.isoformat()}</div>'
            f'<pre style="white-space:pre-wrap;overflow:auto">{payload}</pre>'
            f'<form method="post" action="/admin/suggestions/{sug.id}/approve" style="display:inline"><button>Aprovar</button></form> '
            f'<form method="post" action="/admin/suggestions/{sug.id}/reject" style="display:inline"><button>Rejeitar</button></form> '
            f'<form method="post" action="/admin/suggestions/{sug.id}/duplicate" style="display:inline"><button>Marcar duplicado</button></form>'
            f'</article>'
        )
    corpo = '<div class="app"><div class="wordmark">LOMBADA<span class="dot">.</span></div><h1>Admin</h1><h2>Sugestões pendentes</h2>' + (''.join(items) or '<p>Nenhuma sugestão pendente.</p>') + '</div>'
    return HTMLResponse(_pagina("Admin · Lombada", corpo))


def _aprovar_sugestao(sug: CatalogSuggestion, admin: Usuario, s: Session):
    if sug.status != "pending":
        return
    payload = json.loads(sug.payload_json or "{}")
    if sug.tipo in {"new_book", "new_edition"}:
        titulo = _clean_text(payload.get("titulo"), 240)
        autor = _clean_text(payload.get("autor"), 240)
        if not titulo or not autor:
            raise HTTPException(422, "sugestão sem título/autor")
        obra = s.exec(select(Obra).where(Obra.titulo == titulo, Obra.autor == autor)).first()
        if not obra:
            obra = Obra(ol_work_key=payload.get("work_key") or f"manual:{uuid4().hex}", titulo=titulo, autor=autor,
                        idioma_original=_clean_text(payload.get("idioma_original"), 80), ano=payload.get("ano_obra"))
            s.add(obra); s.commit(); s.refresh(obra)
        edicao = Edicao(obra_id=obra.id, ol_edition_key=payload.get("ol_edition_key"), editora=_clean_text(payload.get("editora"), 160),
                        tradutor=_clean_text(payload.get("tradutor"), 160), isbn=_clean_text(payload.get("isbn"), 32),
                        idioma=_clean_text(payload.get("idioma"), 80), ano=payload.get("ano_edicao"), capa_url=_clean_url(payload.get("capa_url"), 500) if payload.get("capa_url") else "")
        s.add(edicao); s.commit()
    sug.status = "approved"; sug.reviewed_at = datetime.utcnow(); sug.reviewed_by = admin.email or admin.handle
    s.add(sug); s.commit()


@app.post("/admin/suggestions/{suggestion_id}/{action}")
def admin_review(suggestion_id: int, action: str, request: Request, s: Session = Depends(get_session)):
    admin = _require_admin(request, s)
    sug = s.get(CatalogSuggestion, suggestion_id)
    if not sug:
        raise HTTPException(404, "sugestão não encontrada")
    if action == "approve":
        _aprovar_sugestao(sug, admin, s)
    elif action in {"reject", "duplicate"}:
        sug.status = "rejected" if action == "reject" else "duplicate"
        sug.reviewed_at = datetime.utcnow(); sug.reviewed_by = admin.email or admin.handle
        s.add(sug); s.commit()
    else:
        raise HTTPException(404, "ação inválida")
    return HTMLResponse('<meta http-equiv="refresh" content="0; url=/admin">')

@app.get("/")
def home():
    return FileResponse(AQUI / "index.html")
