"""
Lombada — app FastAPI e rotas.
"""
import html
import ipaddress
import json
import logging
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
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import SQLModel, Session, select, func
from starlette.middleware.sessions import SessionMiddleware

from models import SECRET_KEY, engine, Usuario, Obra, Edicao, Leitura, Follow, ReviewLike, SavedReview, ReviewReport, CatalogSuggestion, UserEdition, ReadingJournalEntry, get_session, migrar
from auth import usuario_sessao, router as auth_router
from fontes import ol_edicoes, normalizar_isbn, TIMEOUT, _UA
from busca import _cache_get, _cache_set, buscar_titulo_v2, ol_buscar, _edicao_por_isbn
from publica import render_estante_publica, _leituras_de, _pagina, _esc, resumo_perfil_publico

AQUI = Path(__file__).resolve().parent
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "true").lower() == "true"
logger = logging.getLogger(__name__)


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
    session_cookie=os.getenv("SESSION_COOKIE_NAME", "lombada_session"),
    same_site="lax",
    https_only=COOKIE_SECURE,
)
SENSITIVE_NO_STORE_PREFIXES = (
    "/api/eu",
    "/api/prateleira",
    "/api/diario",
    "/api/leitura",
    "/api/feed",
    "/api/auth",
)


@app.middleware("http")
async def no_store_sensitive_routes(request: Request, call_next):
    response = await call_next(request)
    if request.url.path.startswith(SENSITIVE_NO_STORE_PREFIXES):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


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
        **_user_edition_counts(s, perfil.id),
        "is_following": _is_following(s, atual_id, perfil.id),
        "is_me": bool(atual_id and atual_id == perfil.id),
    }


def _require_google_user(request: Request, s: Session, message: str = "Entre com Google para seguir leitores.", status_code: int = 403) -> Usuario:
    u = usuario_sessao(request, s)
    if not u.google_sub:
        raise HTTPException(status_code, message)
    return u


def _is_public_review(l: Leitura | None) -> bool:
    return bool(l and l.publico and (l.relato or "").strip())


def _review_or_404(leitura_id: int, s: Session) -> Leitura:
    l = s.get(Leitura, leitura_id)
    if not _is_public_review(l):
        raise HTTPException(404, "crítica pública não encontrada")
    return l


def _likes_count(s: Session, leitura_id: int) -> int:
    return s.exec(select(func.count()).select_from(ReviewLike).where(ReviewLike.leitura_id == leitura_id)).one()


def _review_state(s: Session, leitura_id: int, usuario_id: int | None = None) -> dict:
    liked = saved = reported = False
    if usuario_id:
        liked = bool(s.exec(select(ReviewLike).where(ReviewLike.leitura_id == leitura_id, ReviewLike.usuario_id == usuario_id)).first())
        saved = bool(s.exec(select(SavedReview).where(SavedReview.leitura_id == leitura_id, SavedReview.usuario_id == usuario_id)).first())
        reported = bool(s.exec(select(ReviewReport).where(ReviewReport.leitura_id == leitura_id, ReviewReport.usuario_id == usuario_id)).first())
    return {"likes_count": _likes_count(s, leitura_id), "liked_by_me": liked, "saved_by_me": saved, "reported_by_me": reported}


def _assert_not_own_review(l: Leitura, u: Usuario, action: str = "interagir"):
    if l.usuario_id == u.id:
        raise HTTPException(400, f"você não pode {action} sua própria crítica")


class EditionStatePayload(BaseModel):
    tenho: Optional[bool] = None
    quero: Optional[bool] = None


def _edition_read_by_user(s: Session, edicao_id: int, usuario_id: int | None) -> bool:
    if not usuario_id:
        return False
    return bool(s.exec(select(Leitura).where(Leitura.edicao_id == edicao_id, Leitura.usuario_id == usuario_id)).first())


def _edition_state_payload(s: Session, edicao_id: int, usuario_id: int | None) -> dict:
    rel = None
    if usuario_id:
        rel = s.exec(select(UserEdition).where(UserEdition.edicao_id == edicao_id, UserEdition.usuario_id == usuario_id)).first()
    return {"edicao_id": edicao_id, "tenho": bool(rel and rel.tenho), "quero": bool(rel and rel.quero), "li": _edition_read_by_user(s, edicao_id, usuario_id)}


def _edition_stats(s: Session, edicao_id: int) -> dict:
    leituras = s.exec(select(Leitura).where(Leitura.edicao_id == edicao_id)).all()
    notas = [l.nota for l in leituras if l.nota is not None]
    tem = s.exec(select(func.count()).select_from(UserEdition).where(UserEdition.edicao_id == edicao_id, UserEdition.tenho == True)).one()
    querem = s.exec(select(func.count()).select_from(UserEdition).where(UserEdition.edicao_id == edicao_id, UserEdition.quero == True)).one()
    return {"leituras": len(leituras), "tem": tem, "querem": querem, "media": round(sum(notas) / len(notas), 2) if notas else None}


def _edition_relation_map(s: Session, usuario_id: int | None, edicao_ids: list[int]) -> dict[int, dict]:
    if not usuario_id or not edicao_ids:
        return {}
    rels = s.exec(select(UserEdition).where(UserEdition.usuario_id == usuario_id, UserEdition.edicao_id.in_(edicao_ids))).all()
    return {r.edicao_id: {"tenho": bool(r.tenho), "quero": bool(r.quero)} for r in rels}


def _user_edition_counts(s: Session, usuario_id: int) -> dict:
    return {
        "edicoes_possui": s.exec(select(func.count()).select_from(UserEdition).where(UserEdition.usuario_id == usuario_id, UserEdition.tenho == True)).one(),
        "edicoes_desejadas": s.exec(select(func.count()).select_from(UserEdition).where(UserEdition.usuario_id == usuario_id, UserEdition.quero == True)).one(),
    }

# ─── rotas ────────────────────────────────────────────────

EDITORIAL_POPULARES = [
    {"titulo": "Crime e Castigo", "autor": "Fiódor Dostoiévski"},
    {"titulo": "A Montanha Mágica", "autor": "Thomas Mann"},
    {"titulo": "Ulisses", "autor": "James Joyce"},
    {"titulo": "Orlando", "autor": "Virginia Woolf"},
    {"titulo": "O Aleph", "autor": "Jorge Luis Borges"},
    {"titulo": "O Morro dos Ventos Uivantes", "autor": "Emily Brontë"},
]


def _edicao_representativa(s: Session, obra_id: int) -> tuple[Edicao | None, int]:
    edicoes = s.exec(select(Edicao).where(Edicao.obra_id == obra_id)).all()
    if not edicoes:
        return None, 0
    contagens = {
        ed.id: s.exec(select(func.count()).select_from(Leitura).where(Leitura.edicao_id == ed.id)).one()
        for ed in edicoes
        if ed.id is not None
    }
    ed = sorted(edicoes, key=lambda e: (0 if e.capa_url else 1, -(contagens.get(e.id, 0)), e.id or 0))[0]
    return ed, contagens.get(ed.id, 0)


def _obra_popular_payload(s: Session, obra: Obra, leituras_count: int | None = None) -> dict:
    ed, ed_leituras = _edicao_representativa(s, obra.id)
    total = leituras_count if leituras_count is not None else s.exec(
        select(func.count()).select_from(Leitura).join(Edicao, Leitura.edicao_id == Edicao.id).where(Edicao.obra_id == obra.id)
    ).one()
    ed_doc = None
    edicoes = []
    if ed:
        ed_doc = {
            "id": ed.id, "ol_edition_key": ed.ol_edition_key or f"local:{ed.id}", "titulo_edicao": obra.titulo,
            "editora": ed.editora, "tradutor": ed.tradutor, "isbn": ed.isbn, "idioma": ed.idioma,
            "ano": ed.ano, "capa_url": ed.capa_url, "leituras_count": ed_leituras,
        }
        edicoes = [ed_doc]
    return {
        "obra_id": obra.id, "edicao_id": ed.id if ed else None, "work_key": obra.ol_work_key,
        "titulo": obra.titulo, "autor": obra.autor, "idioma_original": obra.idioma_original,
        "capa_url": ed.capa_url if ed else "", "editora": ed.editora if ed else "",
        "ano": ed.ano if ed and ed.ano else obra.ano, "leituras_count": total or 0,
        "tem_pt": bool(ed and ed.idioma == "Português"), "isbn_match": False,
        "edicao_isbn": ed_doc, "edicoes": edicoes, "_fonte": "local",
    }


@app.get("/api/explore/populares")
def explore_populares(s: Session = Depends(get_session)):
    populares = s.exec(
        select(Obra.id, func.count(Leitura.id))
        .join(Edicao, Edicao.obra_id == Obra.id)
        .join(Leitura, Leitura.edicao_id == Edicao.id)
        .group_by(Obra.id)
        .order_by(func.count(Leitura.id).desc(), Obra.id.desc())
        .limit(12)
    ).all()
    obras = []
    usados = set()
    for obra_id, total in populares:
        obra = s.get(Obra, obra_id)
        if obra:
            obras.append(_obra_popular_payload(s, obra, total))
            usados.add(obra.id)
    if len(obras) < 12:
        recentes = s.exec(select(Obra).order_by(Obra.id.desc()).limit(24)).all()
        for obra in recentes:
            if obra.id in usados:
                continue
            obras.append(_obra_popular_payload(s, obra))
            usados.add(obra.id)
            if len(obras) >= 12:
                break
    return obras or EDITORIAL_POPULARES

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
        **_user_edition_counts(s, u.id),
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
        bucket = por_edicao.setdefault(ed.id, {"leituras": 0, "notas": [], "editora": ed.editora, "tradutor": ed.tradutor})
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
                "is_following": _is_following(s, usuario_id, u.id),
                "is_me": bool(usuario_id and usuario_id == u.id),
                "edicao_id": ed.id, **_review_state(s, l.id, usuario_id), "edicao": {
                    "editora": ed.editora, "ano": ed.ano, "tradutor": ed.tradutor,
                    "isbn": ed.isbn, "idioma": ed.idioma, "capa_url": ed.capa_url,
                }
            })
    edicoes = []
    ed_por_id = {ed.id: ed for (_l, ed, _o, _u) in rows}
    all_ed_ids = list(ed_por_id.keys())
    rel_map = _edition_relation_map(s, usuario_id, all_ed_ids)
    social_counts = {ed_id: _edition_stats(s, ed_id) for ed_id in all_ed_ids}
    for ed_id, st in por_edicao.items():
        ed = ed_por_id.get(ed_id)
        counts = social_counts.get(ed_id, {})
        edicoes.append({
            "edicao_id": ed_id,
            "leituras": st["leituras"],
            "tem": counts.get("tem", 0),
            "querem": counts.get("querem", 0),
            "media": round(sum(st["notas"]) / len(st["notas"]), 2) if st["notas"] else None,
            "estado": {**rel_map.get(ed_id, {"tenho": False, "quero": False}), "li": _edition_read_by_user(s, ed_id, usuario_id)},
            "edicao": {
                "editora": ed.editora if ed else "", "ano": ed.ano if ed else None,
                "tradutor": ed.tradutor if ed else "", "isbn": ed.isbn if ed else "",
                "idioma": ed.idioma if ed else "", "capa_url": ed.capa_url if ed else "",
            },
        })
    destaques_edicao = {
        "mais_lida": max(edicoes, key=lambda e: e.get("leituras") or 0) if any(e.get("leituras") for e in edicoes) else None,
        "mais_desejada": max(edicoes, key=lambda e: e.get("querem") or 0) if any(e.get("querem") for e in edicoes) else None,
        "mais_possuida": max(edicoes, key=lambda e: e.get("tem") or 0) if any(e.get("tem") for e in edicoes) else None,
    }
    trad_counts = {}
    pub_counts = {}
    for ed in edicoes:
        meta = ed.get("edicao") or {}
        if meta.get("tradutor") and ed.get("leituras"):
            trad_counts[meta["tradutor"]] = trad_counts.get(meta["tradutor"], 0) + ed.get("leituras", 0)
        if meta.get("editora") and ed.get("leituras"):
            pub_counts[meta["editora"]] = pub_counts.get(meta["editora"], 0) + ed.get("leituras", 0)
    destaques_edicao["traducao_mais_lida"] = max(trad_counts.items(), key=lambda x: x[1])[0] if trad_counts else None
    destaques_edicao["editora_mais_lida"] = max(pub_counts.items(), key=lambda x: x[1])[0] if pub_counts else None
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
        "destaques_edicao": destaques_edicao,
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
            "edicoes": [], "criticas": [], "destaques": [], "destaques_edicao": {}, "minha_leitura": None,
        }
    return _obra_social_payload(obra, s, u.id)



@app.get("/api/edicoes/{edicao_id}/estado")
def estado_edicao(edicao_id: int, request: Request, s: Session = Depends(get_session)):
    u = usuario_sessao(request, s)
    if not s.get(Edicao, edicao_id):
        raise HTTPException(404, "edição não encontrada")
    return _edition_state_payload(s, edicao_id, u.id)


@app.patch("/api/edicoes/{edicao_id}/estado")
def atualizar_estado_edicao(edicao_id: int, payload: EditionStatePayload, request: Request, s: Session = Depends(get_session)):
    u = _require_google_user(request, s, "Entre com Google para marcar edições.", 401)
    if not s.get(Edicao, edicao_id):
        raise HTTPException(404, "edição não encontrada")
    rel = s.exec(select(UserEdition).where(UserEdition.edicao_id == edicao_id, UserEdition.usuario_id == u.id)).first()
    if not rel:
        rel = UserEdition(edicao_id=edicao_id, usuario_id=u.id)
    data = payload.model_dump(exclude_unset=True)
    if "tenho" in data:
        rel.tenho = bool(data["tenho"])
        if rel.tenho:
            rel.quero = False
    if "quero" in data:
        rel.quero = bool(data["quero"])
    if rel.tenho and rel.quero:
        rel.quero = False
    rel.updated_at = datetime.utcnow()
    s.add(rel); s.commit()
    return _edition_state_payload(s, edicao_id, u.id)


@app.get("/api/edicoes/{edicao_id}/social")
def social_edicao(edicao_id: int, request: Request, s: Session = Depends(get_session)):
    u = usuario_sessao(request, s)
    ed = s.get(Edicao, edicao_id)
    if not ed:
        raise HTTPException(404, "edição não encontrada")
    return {
        "edicao_id": edicao_id,
        "estatisticas": _edition_stats(s, edicao_id),
        "estado": _edition_state_payload(s, edicao_id, u.id),
        "edicao": {"editora": ed.editora, "tradutor": ed.tradutor, "ano": ed.ano, "isbn": ed.isbn, "idioma": ed.idioma, "capa_url": ed.capa_url},
    }


class ReviewReportPayload(BaseModel):
    motivo: str = "other"
    detalhe: str = ""


@app.post("/api/reviews/{leitura_id}/like")
def like_review(leitura_id: int, request: Request, s: Session = Depends(get_session)):
    u = _require_google_user(request, s, "Entre com Google para interagir com críticas.", 401)
    l = _review_or_404(leitura_id, s)
    _assert_not_own_review(l, u, "curtir")
    like = s.exec(select(ReviewLike).where(ReviewLike.leitura_id == leitura_id, ReviewLike.usuario_id == u.id)).first()
    if not like:
        s.add(ReviewLike(leitura_id=leitura_id, usuario_id=u.id)); s.commit()
    return {"liked": True, "likes_count": _likes_count(s, leitura_id)}


@app.delete("/api/reviews/{leitura_id}/like")
def unlike_review(leitura_id: int, request: Request, s: Session = Depends(get_session)):
    u = _require_google_user(request, s, "Entre com Google para interagir com críticas.", 401)
    _review_or_404(leitura_id, s)
    like = s.exec(select(ReviewLike).where(ReviewLike.leitura_id == leitura_id, ReviewLike.usuario_id == u.id)).first()
    if like:
        s.delete(like); s.commit()
    return {"liked": False, "likes_count": _likes_count(s, leitura_id)}


@app.post("/api/reviews/{leitura_id}/save")
def save_review(leitura_id: int, request: Request, s: Session = Depends(get_session)):
    u = _require_google_user(request, s, "Entre com Google para interagir com críticas.", 401)
    l = _review_or_404(leitura_id, s)
    _assert_not_own_review(l, u, "salvar")
    saved = s.exec(select(SavedReview).where(SavedReview.leitura_id == leitura_id, SavedReview.usuario_id == u.id)).first()
    if not saved:
        s.add(SavedReview(leitura_id=leitura_id, usuario_id=u.id)); s.commit()
    return {"saved": True}


@app.delete("/api/reviews/{leitura_id}/save")
def unsave_review(leitura_id: int, request: Request, s: Session = Depends(get_session)):
    u = _require_google_user(request, s, "Entre com Google para interagir com críticas.", 401)
    _review_or_404(leitura_id, s)
    saved = s.exec(select(SavedReview).where(SavedReview.leitura_id == leitura_id, SavedReview.usuario_id == u.id)).first()
    if saved:
        s.delete(saved); s.commit()
    return {"saved": False}


@app.post("/api/reviews/{leitura_id}/report")
def report_review(leitura_id: int, payload: ReviewReportPayload, request: Request, s: Session = Depends(get_session)):
    u = _require_google_user(request, s, "Entre com Google para interagir com críticas.", 401)
    l = _review_or_404(leitura_id, s)
    _assert_not_own_review(l, u, "denunciar")
    motivo = _clean_text(payload.motivo, 80) or "other"
    detalhe = _clean_text(payload.detalhe, 500)
    report = s.exec(select(ReviewReport).where(ReviewReport.leitura_id == leitura_id, ReviewReport.usuario_id == u.id)).first()
    if not report:
        report = ReviewReport(leitura_id=leitura_id, usuario_id=u.id, motivo=motivo, detalhe=detalhe)
        s.add(report); s.commit()
    return {"reported": True}



PROGRESSO_TIPOS = {"pagina", "porcentagem", "capitulo", "livre"}


class DiarioPayload(BaseModel):
    progresso_tipo: str = "livre"
    pagina: Optional[int] = None
    porcentagem: Optional[float] = None
    capitulo: str = ""
    nota: str = ""
    publico: bool = False
    spoiler: bool = False


def _leitura_do_usuario(leitura_id: int, usuario_id: int, s: Session) -> Leitura:
    leitura = s.get(Leitura, leitura_id)
    if not leitura or leitura.usuario_id != usuario_id:
        raise HTTPException(404, "leitura não encontrada")
    return leitura


def _validar_diario(payload: DiarioPayload) -> dict:
    data = payload.model_dump(exclude_unset=True)
    tipo = (data.get("progresso_tipo") or "livre").strip().lower()
    if tipo not in PROGRESSO_TIPOS:
        raise HTTPException(422, "tipo de progresso inválido")
    pagina = data.get("pagina")
    porcentagem = data.get("porcentagem")
    nota = _clean_text(data.get("nota", ""), 2000)
    capitulo = _clean_text(data.get("capitulo", ""), 120)

    pagina_valida = pagina is not None and pagina > 0
    porcentagem_valida = porcentagem is not None and 0 <= porcentagem <= 100
    capitulo_valido = bool(capitulo)

    if pagina is not None and not pagina_valida:
        raise HTTPException(422, "informe um progresso ou uma anotação")
    if porcentagem is not None and not porcentagem_valida:
        raise HTTPException(422, "informe um progresso ou uma anotação")
    if not (pagina_valida or porcentagem_valida or capitulo_valido or nota):
        raise HTTPException(422, "informe um progresso ou uma anotação")

    return {
        "progresso_tipo": tipo,
        "pagina": pagina if tipo == "pagina" and pagina_valida else None,
        "porcentagem": porcentagem if tipo == "porcentagem" and porcentagem_valida else None,
        "capitulo": capitulo if tipo in {"capitulo", "livre"} and capitulo_valido else "",
        "nota": nota,
        "publico": bool(data.get("publico", False)),
        "spoiler": bool(data.get("spoiler", False))
    }

def _diario_payload(entry: ReadingJournalEntry, l: Leitura | None = None, ed: Edicao | None = None, o: Obra | None = None) -> dict:
    return {
        "id": entry.id, "leitura_id": entry.leitura_id, "progresso_tipo": entry.progresso_tipo,
        "pagina": entry.pagina, "porcentagem": entry.porcentagem, "capitulo": entry.capitulo,
        "nota": entry.nota, "publico": bool(entry.publico), "spoiler": bool(entry.spoiler),
        "created_at": entry.created_at.isoformat(), "updated_at": entry.updated_at.isoformat(),
        **({"status": l.status, "titulo": o.titulo, "autor": o.autor, "capa_url": ed.capa_url} if l and ed and o else {}),
    }


@app.get("/api/leitura/{leitura_id}/diario")
def listar_diario_leitura(leitura_id: int, request: Request, s: Session = Depends(get_session)):
    u = usuario_sessao(request, s)
    _leitura_do_usuario(leitura_id, u.id, s)
    entries = s.exec(select(ReadingJournalEntry).where(ReadingJournalEntry.leitura_id == leitura_id, ReadingJournalEntry.usuario_id == u.id).order_by(ReadingJournalEntry.created_at.desc())).all()
    return [_diario_payload(e) for e in entries]


@app.get("/api/diario")
def listar_diario_usuario(request: Request, s: Session = Depends(get_session)):
    u = usuario_sessao(request, s)
    rows = s.exec(
        select(ReadingJournalEntry, Leitura, Edicao, Obra)
        .join(Leitura, ReadingJournalEntry.leitura_id == Leitura.id)
        .join(Edicao, Leitura.edicao_id == Edicao.id)
        .join(Obra, Edicao.obra_id == Obra.id)
        .where(ReadingJournalEntry.usuario_id == u.id, Leitura.usuario_id == u.id)
        .order_by(ReadingJournalEntry.created_at.desc())
    ).all()
    return [_diario_payload(e, l, ed, o) for e, l, ed, o in rows]


@app.post("/api/leitura/{leitura_id}/diario")
def criar_diario(leitura_id: int, payload: DiarioPayload, request: Request, s: Session = Depends(get_session)):
    u = usuario_sessao(request, s)
    _leitura_do_usuario(leitura_id, u.id, s)
    data = _validar_diario(payload)
    entry = ReadingJournalEntry(leitura_id=leitura_id, usuario_id=u.id, **data)
    try:
        s.add(entry); s.commit(); s.refresh(entry)
    except SQLAlchemyError:
        s.rollback()
        logger.exception("erro inesperado ao criar entrada de diário", extra={"leitura_id": leitura_id, "usuario_id": u.id})
        raise HTTPException(500, "não foi possível salvar a entrada do diário")
    return _diario_payload(entry)


@app.patch("/api/diario/{entrada_id}")
def editar_diario(entrada_id: int, payload: DiarioPayload, request: Request, s: Session = Depends(get_session)):
    u = usuario_sessao(request, s)
    entry = s.get(ReadingJournalEntry, entrada_id)
    if not entry or entry.usuario_id != u.id:
        raise HTTPException(404, "entrada de diário não encontrada")
    data = _validar_diario(payload)
    for k, v in data.items():
        setattr(entry, k, v)
    entry.updated_at = datetime.utcnow()
    try:
        s.add(entry); s.commit(); s.refresh(entry)
    except SQLAlchemyError:
        s.rollback()
        logger.exception("erro inesperado ao editar entrada de diário", extra={"entrada_id": entrada_id, "usuario_id": u.id})
        raise HTTPException(500, "não foi possível salvar a entrada do diário")
    return _diario_payload(entry)


@app.delete("/api/diario/{entrada_id}")
def remover_diario(entrada_id: int, request: Request, s: Session = Depends(get_session)):
    u = usuario_sessao(request, s)
    entry = s.get(ReadingJournalEntry, entrada_id)
    if not entry or entry.usuario_id != u.id:
        raise HTTPException(404, "entrada de diário não encontrada")
    s.delete(entry); s.commit()
    return {"ok": True}

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
    tenho_edicao:    bool          = False
    quero_edicao:    bool          = False


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
    s.add(leitura)
    rel = s.exec(select(UserEdition).where(UserEdition.usuario_id == usuario_id, UserEdition.edicao_id == edicao.id)).first()
    if not rel and (getattr(e, "tenho_edicao", False) or getattr(e, "quero_edicao", False)):
        rel = UserEdition(usuario_id=usuario_id, edicao_id=edicao.id)
    if rel:
        if getattr(e, "tenho_edicao", False):
            rel.tenho = True; rel.quero = False
        elif getattr(e, "quero_edicao", False):
            rel.quero = True
        rel.updated_at = datetime.utcnow()
        s.add(rel)
    s.commit(); s.refresh(leitura)
    return leitura, obra, edicao


@app.post("/api/prateleira")
def adicionar(e: EntradaPrateleira, request: Request, s: Session = Depends(get_session)):
    u = usuario_sessao(request, s)
    try:
        leitura, obra, edicao = _criar_leitura(e, u.id, s)
    except HTTPException:
        raise
    except SQLAlchemyError as exc:
        s.rollback()
        print(f"[api/prateleira POST error] {exc}")
        raise HTTPException(500, "erro ao salvar leitura; verifique as migrações do banco")
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
    try:
        rows = s.exec(
            select(Leitura, Edicao, Obra)
            .join(Edicao, Leitura.edicao_id == Edicao.id)
            .join(Obra, Edicao.obra_id == Obra.id)
            .where(Leitura.usuario_id == u.id)
            .order_by(Leitura.criado_em.desc())
        ).all()
    except SQLAlchemyError as exc:
        print(f"[api/prateleira GET error] {exc}")
        raise HTTPException(500, "erro ao carregar estante; verifique as migrações do banco")
    ed_ids = [ed.id for (_l, ed, _o) in rows]
    rel_map = _edition_relation_map(s, u.id, ed_ids)
    return [{
        "leitura_id": l.id, "status": l.status, "nota": l.nota,
        "relato": l.relato, "publico": bool(l.publico), "spoiler": bool(l.spoiler), "data": l.data,
        "titulo": o.titulo, "autor": o.autor, "work_key": o.ol_work_key,
        "edicao_id": ed.id, "ol_edition_key": ed.ol_edition_key,
        "editora": ed.editora, "tradutor": ed.tradutor,
        "ano": ed.ano, "isbn": ed.isbn, "capa_url": ed.capa_url,
        "tenho_edicao": rel_map.get(ed.id, {}).get("tenho", False),
        "quero_edicao": rel_map.get(ed.id, {}).get("quero", False),
        "li_edicao": True,
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
    for entry in s.exec(select(ReadingJournalEntry).where(ReadingJournalEntry.leitura_id == leitura_id, ReadingJournalEntry.usuario_id == u.id)).all():
        s.delete(entry)
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


def _feed_review_item(s: Session, l: Leitura, ed: Edicao, o: Obra, autor: Usuario, atual: Usuario | None, trecho: bool = True) -> dict:
    relato = (l.relato or "").strip()
    atual_id = atual.id if atual else None
    return {
        "tipo": _feed_tipo(l),
        "usuario": {
            "handle": autor.handle, "nome": autor.nome,
            "is_following": _is_following(s, atual_id, autor.id),
            "is_me": bool(atual_id and atual_id == autor.id),
        },
        "livro": {"titulo": o.titulo, "autor": o.autor, "work_key": o.ol_work_key, "capa_url": ed.capa_url},
        "edicao": {"editora": ed.editora, "tradutor": ed.tradutor, "ano": ed.ano},
        "leitura": {
            "leitura_id": l.id, "status": l.status, "nota": l.nota, "publico": bool(l.publico),
            "spoiler": bool(l.spoiler), "relato": (relato[:220] if trecho else relato),
            **(_review_state(s, l.id, atual_id) if l.publico and relato else {"likes_count": 0, "liked_by_me": False, "saved_by_me": False, "reported_by_me": False}),
        },
        "created_at": l.criado_em.isoformat(),
    }


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
    items = [_feed_review_item(s, l, ed, o, autor, u) for l, ed, o, autor in rows]
    return {"following_count": len(following_ids), "items": items}


@app.get("/api/feed/discover")
def feed_discover(request: Request, s: Session = Depends(get_session), limit: int = Query(20, ge=1, le=50)):
    atual = usuario_sessao(request, s)
    rows = s.exec(
        select(Leitura, Edicao, Obra, Usuario)
        .join(Edicao, Leitura.edicao_id == Edicao.id)
        .join(Obra, Edicao.obra_id == Obra.id)
        .join(Usuario, Leitura.usuario_id == Usuario.id)
        .where(Leitura.publico == True, Leitura.relato != "")
        .order_by(Leitura.criado_em.desc())
        .limit(limit)
    ).all()
    reviews = [_feed_review_item(s, l, ed, o, autor, atual, trecho=False) for l, ed, o, autor in rows if (l.relato or "").strip()]

    active_rows = s.exec(
        select(Usuario, func.count(Leitura.id).label("reviews_count"))
        .join(Leitura, Leitura.usuario_id == Usuario.id)
        .where(Leitura.publico == True, Leitura.relato != "")
        .group_by(Usuario.id)
        .order_by(func.count(Leitura.id).desc())
        .limit(20)
    ).all()
    readers = []
    for leitor, reviews_count in active_rows:
        if atual.id and leitor.id == atual.id:
            continue
        readers.append({
            "handle": leitor.handle, "nome": leitor.nome, "reviews_count": reviews_count,
            "followers_count": _follow_counts(s, leitor.id)["followers_count"],
            "is_following": _is_following(s, atual.id, leitor.id), "is_me": False,
        })
        if len(readers) >= 10:
            break
    return {"reviews": reviews, "readers": readers}

# ─── estante pública ──────────────────────────────────────
@app.get("/api/u/{handle}")
def estante_json(handle: str, request: Request, s: Session = Depends(get_session)):
    u = s.exec(select(Usuario).where(Usuario.handle == handle.lower().strip())).first()
    if not u:
        raise HTTPException(404, "estante não encontrada")
    atual = usuario_sessao(request, s)
    leituras = _leituras_de(s, u.id)
    for l in leituras:
        if l.get("publico") and (l.get("relato") or "").strip():
            l.update(_review_state(s, l.get("leitura_id"), atual.id))
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
    reports = s.exec(
        select(ReviewReport, Leitura, Edicao, Obra, Usuario)
        .join(Leitura, ReviewReport.leitura_id == Leitura.id)
        .join(Edicao, Leitura.edicao_id == Edicao.id)
        .join(Obra, Edicao.obra_id == Obra.id)
        .join(Usuario, Leitura.usuario_id == Usuario.id)
        .where(ReviewReport.status == "pending")
        .order_by(ReviewReport.created_at.desc())
    ).all()
    report_items = []
    for rep, leitura, ed, obra, autor in reports:
        report_items.append(
            f'<article class="card-form" style="margin:16px 0">'
            f'<div class="meta">#{rep.id} · crítica #{leitura.id} · @{_esc(autor.handle)} · {_esc(rep.motivo)} · {rep.created_at.isoformat()}</div>'
            f'<strong>{_esc(obra.titulo)}</strong><p>{_esc((leitura.relato or "")[:500])}</p>'
            f'<p>{_esc(rep.detalhe)}</p>'
            f'<form method="post" action="/admin/reports/{rep.id}/reviewed" style="display:inline"><button>Marcar revisada</button></form> '
            f'<form method="post" action="/admin/reports/{rep.id}/dismissed" style="display:inline"><button>Dispensar</button></form>'
            f'</article>'
        )
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
    corpo = '<div class="app"><div class="wordmark">LOMBADA<span class="dot">.</span></div><h1>Admin</h1><h2>Denúncias pendentes</h2>' + (''.join(report_items) or '<p>Nenhuma denúncia pendente.</p>') + '<h2>Sugestões pendentes</h2>' + (''.join(items) or '<p>Nenhuma sugestão pendente.</p>') + '</div>'
    return HTMLResponse(_pagina("Admin · Lombada", corpo))



@app.post("/admin/reports/{report_id}/{action}")
def admin_report_review(report_id: int, action: str, request: Request, s: Session = Depends(get_session)):
    admin = _require_admin(request, s)
    rep = s.get(ReviewReport, report_id)
    if not rep:
        raise HTTPException(404, "denúncia não encontrada")
    if action not in {"reviewed", "dismissed"}:
        raise HTTPException(404, "ação inválida")
    rep.status = action
    rep.reviewed_at = datetime.utcnow()
    rep.reviewed_by = admin.email or admin.handle
    s.add(rep); s.commit()
    return HTMLResponse('<meta http-equiv="refresh" content="0; url=/admin">')

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


@app.get("/sw.js")
def service_worker():
    return FileResponse(
        AQUI / "sw.js",
        media_type="application/javascript",
        headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"},
    )


@app.get("/manifest.json")
def manifest():
    return FileResponse(
        AQUI / "manifest.json",
        media_type="application/manifest+json",
        headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"},
    )
