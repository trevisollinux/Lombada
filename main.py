"""
Lombada — app FastAPI e rotas.
"""
import html
import hashlib
import ipaddress
import json
import logging
import os
import re
import socket
import unicodedata
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional
from uuid import uuid4
from datetime import datetime
from urllib.parse import parse_qs, urlparse

import httpx
from fastapi import FastAPI, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import SQLModel, Session, select, func
from starlette.middleware.sessions import SessionMiddleware

from models import SECRET_KEY, engine, Usuario, Obra, Edicao, Leitura, Follow, ReviewLike, SavedReview, ReviewReport, CatalogSuggestion, UserEdition, ReadingJournalEntry, EdicaoCapitulo, BuscaCache, get_session, migrar
from auth import usuario_sessao, router as auth_router
from fontes import ol_edicoes, normalizar_isbn, gbooks_buscar, chave_obra_canonica, ol_table_of_contents, TIMEOUT, _UA
from busca import _cache_get, _cache_set, buscar_titulo_v2, ol_buscar, _edicao_por_isbn, consolidar_resultados_busca_final
from publica import render_estante_publica, _leituras_de, _pagina, _esc, resumo_perfil_publico
from editoras import listar_editoras, dados_editora, render_pagina_editora, render_indice_editoras

AQUI = Path(__file__).resolve().parent
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "true").lower() == "true"
APP_VERSION = os.getenv("APP_VERSION", "dev")
RECON_TOKEN = os.getenv("RECON_TOKEN", "")
logger = logging.getLogger(__name__)


DEMO_CONTENT = [
    {"handle": "clara-lombada", "nome": "Clara Leitora", "titulo": "Dom Casmurro", "autor": "Machado de Assis", "ano": 1899, "nota": 4.5, "relato": "Reli devagar e gostei mais do silêncio entre as cenas do que da trama em si. É um livro que fica ecoando depois."},
    {"handle": "miguel-lombada", "nome": "Miguel Anota", "titulo": "Memórias Póstumas de Brás Cubas", "autor": "Machado de Assis", "ano": 1881, "nota": 5.0, "relato": "A força está menos no acontecimento e mais na forma como a linguagem organiza a dúvida, a culpa e a memória."},
    {"handle": "lia-lombada", "nome": "Lia Margem", "titulo": "O Alienista", "autor": "Machado de Assis", "ano": 1882, "nota": 4.0, "relato": "Leitura rápida, mas não simples. Tem frases que parecem pequenas e depois voltam maiores."},
    {"handle": "tomas-lombada", "nome": "Tomás Livros", "titulo": "Crime e Castigo", "autor": "Fiódor Dostoiévski", "ano": 1866, "nota": 4.5, "relato": "O estilo segura tudo: denso, preciso e com uma tensão moral que deixa a história mais incômoda."},
    {"handle": "nina-lombada", "nome": "Nina Página", "titulo": "A Metamorfose", "autor": "Franz Kafka", "ano": 1915, "nota": 3.5, "relato": "Gostei mais da atmosfera do que dos personagens. Ainda assim, terminei com vontade de discutir o livro."},
]


def _demo_work_key(titulo: str) -> str:
    return "demo:" + "-".join(titulo.lower().replace("ó", "o").replace("á", "a").replace("é", "e").replace("í", "i").replace("ã", "a").split())


def seed_demo_content() -> None:
    if os.getenv("DEMO_CONTENT_ENABLED", "").lower() not in {"1", "true", "yes", "on"}:
        return
    logger.info("[demo seed] iniciado")
    with Session(engine) as s:
        for idx, item in enumerate(DEMO_CONTENT):
            usuario = s.exec(select(Usuario).where(Usuario.handle == item["handle"])).first()
            if not usuario:
                usuario = Usuario(handle=item["handle"], nome=item["nome"], is_demo=True)
                s.add(usuario); s.commit(); s.refresh(usuario)
                logger.info("[demo seed] usuario criado handle=%s", item["handle"])
            else:
                usuario.is_demo = True
                if not usuario.nome:
                    usuario.nome = item["nome"]
                s.add(usuario); s.commit()
                logger.info("[demo seed] usuario reutilizado handle=%s", item["handle"])

            work_key = _demo_work_key(item["titulo"])
            obra = s.exec(select(Obra).where(Obra.ol_work_key == work_key)).first()
            if not obra:
                obra = Obra(ol_work_key=work_key, titulo=item["titulo"], autor=item["autor"], ano=item["ano"], idioma_original="")
                s.add(obra); s.commit(); s.refresh(obra)
            edicao = s.exec(select(Edicao).where(Edicao.obra_id == obra.id, Edicao.ol_edition_key == work_key)).first()
            if not edicao:
                edicao = Edicao(obra_id=obra.id, ol_edition_key=work_key, editora="Lombada Demo", idioma="pt", ano=item["ano"])
                s.add(edicao); s.commit(); s.refresh(edicao)

            leitura = s.exec(select(Leitura).where(Leitura.usuario_id == usuario.id, Leitura.edicao_id == edicao.id, Leitura.is_demo == True)).first()
            if not leitura:
                leitura = Leitura(
                    usuario_id=usuario.id, edicao_id=edicao.id, status="Lido", nota=item["nota"],
                    relato=item["relato"], publico=True, spoiler=False, is_demo=True, data="",
                    criado_em=datetime(2026, 1, 15, 12, 0, 0).replace(minute=idx),
                )
                s.add(leitura); s.commit()
                logger.info("[demo seed] critica criada handle=%s obra=%s", item["handle"], item["titulo"])
            else:
                logger.info("[demo seed] critica reutilizada handle=%s obra=%s", item["handle"], item["titulo"])


def _catalog_seed_enabled() -> bool:
    return os.getenv("CATALOG_SEED_ENABLED", "").lower() in {"1", "true", "yes", "on"}


def _clean_seed_value(value) -> str:
    return str(value or "").strip()


def _find_seed_edicao(s: Session, obra: Obra, edicao_data: dict) -> Edicao | None:
    ol_edition_key = _clean_seed_value(edicao_data.get("ol_edition_key"))
    isbn = normalizar_isbn(_clean_seed_value(edicao_data.get("isbn")))
    if ol_edition_key:
        edicao = s.exec(select(Edicao).where(Edicao.ol_edition_key == ol_edition_key)).first()
        if edicao:
            return edicao
    if isbn:
        edicao = s.exec(select(Edicao).where(Edicao.isbn == isbn)).first()
        if edicao:
            return edicao
    editora = _clean_seed_value(edicao_data.get("editora"))
    tradutor = _clean_seed_value(edicao_data.get("tradutor"))
    ano = edicao_data.get("ano_edicao")
    return s.exec(
        select(Edicao)
        .where(Edicao.obra_id == obra.id)
        .where(Edicao.editora == editora)
        .where(Edicao.tradutor == tradutor)
        .where(Edicao.ano == ano)
    ).first()


def seed_catalog_content() -> None:
    if not _catalog_seed_enabled():
        return
    seed_path = AQUI / "data" / "catalog_seed.json"
    if not seed_path.exists():
        logger.warning("[catalog seed] arquivo não encontrado path=%s", seed_path)
        return
    try:
        items = json.loads(seed_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        logger.exception("[catalog seed] falha ao carregar path=%s", seed_path)
        return

    obras_criadas = obras_reutilizadas = edicoes_criadas = edicoes_reutilizadas = 0
    with Session(engine) as s:
        for item in items:
            work_key = _clean_seed_value(item.get("work_key"))
            titulo = _clean_seed_value(item.get("titulo"))
            autor = _clean_seed_value(item.get("autor"))
            if not work_key or not titulo:
                continue
            obra = s.exec(select(Obra).where(Obra.ol_work_key == work_key)).first()
            if not obra:
                obra = s.exec(
                    select(Obra)
                    .where(func.lower(Obra.titulo) == titulo.lower())
                    .where(func.lower(Obra.autor) == autor.lower())
                ).first()
            if obra:
                obras_reutilizadas += 1
            else:
                obra = Obra(
                    ol_work_key=work_key,
                    titulo=titulo,
                    autor=autor,
                    ano=item.get("ano_obra"),
                    idioma_original=_clean_seed_value(item.get("idioma_original")),
                )
                s.add(obra); s.commit(); s.refresh(obra)
                obras_criadas += 1

            for edicao_data in item.get("edicoes", []):
                edicao = _find_seed_edicao(s, obra, edicao_data)
                if edicao:
                    edicoes_reutilizadas += 1
                    continue
                edicao = Edicao(
                    obra_id=obra.id,
                    ol_edition_key=_clean_seed_value(edicao_data.get("ol_edition_key")) or None,
                    editora=_clean_seed_value(edicao_data.get("editora")),
                    tradutor=_clean_seed_value(edicao_data.get("tradutor")),
                    isbn=normalizar_isbn(_clean_seed_value(edicao_data.get("isbn"))),
                    idioma=_clean_seed_value(edicao_data.get("idioma")),
                    ano=edicao_data.get("ano_edicao"),
                    capa_url=_clean_seed_value(edicao_data.get("capa_url")),
                )
                s.add(edicao); s.commit()
                edicoes_criadas += 1

    logger.info(
        "[catalog seed] obras criadas=%s reutilizadas=%s edições criadas=%s reutilizadas=%s",
        obras_criadas, obras_reutilizadas, edicoes_criadas, edicoes_reutilizadas,
    )


# ─── lifespan ─────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app):
    SQLModel.metadata.create_all(engine)
    migrar()
    seed_demo_content()
    seed_catalog_content()
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

@app.exception_handler(Exception)
async def friendly_unhandled_error_handler(request: Request, exc: Exception):
    logger.exception("unhandled_backend_error", extra={"path": request.url.path, "method": request.method})
    return JSONResponse({"detail": "Não consegui concluir essa ação agora."}, status_code=500)


@app.get("/healthz")
def healthz():
    return {"ok": True, "service": "lombada"}


@app.get("/readyz")
def readyz():
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"ok": True, "database": "ok"}
    except SQLAlchemyError:
        logger.exception("database_readiness_failed")
    except Exception:
        logger.exception("database_readiness_unexpected_error")
    return JSONResponse({"ok": False, "database": "error"}, status_code=503)


@app.get("/api/version")
def api_version():
    return {"version": APP_VERSION, "app": "Lombada"}


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


def _plain_text(v, max_len: int = 500) -> str:
    if v is None:
        return ""
    return str(v).replace("\x00", "").strip()[:max_len]


def _parse_int_optional(v) -> int | None:
    v = _plain_text(v, 20)
    if not v:
        return None
    try:
        return int(v)
    except ValueError:
        raise HTTPException(422, "ano de publicação inválido")


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
    try:
        s.add(sug); s.commit(); s.refresh(sug)
        logger.info("catalog_suggestion_created", extra={"tipo": tipo, "target_type": target_type or "", "user_id": u.id})
    except SQLAlchemyError:
        s.rollback()
        logger.exception("catalog_suggestion_failed", extra={"tipo": tipo, "target_type": target_type or "", "user_id": u.id})
        raise HTTPException(500, "não foi possível enviar a sugestão agora")
    return sug


def _normalizar_busca(valor: str | None) -> str:
    texto = unicodedata.normalize("NFKD", str(valor or ""))
    texto = "".join(ch for ch in texto if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", texto.lower().strip())


_AUTORES_DOSTOIEVSKI = {
    "dostoievski", "dostoevsky", "dostoyevsky", "dostoiévski", "dostoievsky",
    "fiodor dostoievski", "fiodor dostoevsky", "fiodor dostoyevsky",
    "fiodor mikhailovitch dostoievski", "fiodor mikhailovich dostoevsky",
    "fedor dostoievski", "fyodor dostoevsky", "fyodor dostoyevsky",
    "feodor dostoievski", "feodor dostoevsky",
}
_TERMOS_RELACIONADOS_NAO_AGRUPAR = {
    "colecao", "ensaios", "sobre", "biografia", "vida de", "obra de", "romances de",
}


def _normalizar_autor_canonico(autor: str | None) -> str:
    norm = re.sub(r"[^a-z0-9]+", " ", _normalizar_busca(autor)).strip()
    if not norm:
        return ""
    if norm in _AUTORES_DOSTOIEVSKI or "dostoevsk" in norm or "dostoievsk" in norm or "dostoyevsk" in norm:
        return "dostoievski"
    return norm


def _titulo_tem_marcador_relacionado(titulo_norm: str) -> bool:
    return any(re.search(rf"\b{re.escape(termo)}\b", titulo_norm) for termo in _TERMOS_RELACIONADOS_NAO_AGRUPAR)


def _titulo_canonico_busca(titulo: str | None, autor: str | None = None) -> str:
    norm = _normalizar_busca(titulo)
    autor_norm = _normalizar_autor_canonico(autor)
    if ":" in norm and not _titulo_tem_marcador_relacionado(norm):
        norm = norm.split(":", 1)[0]
    if autor_norm:
        aliases = sorted(_AUTORES_DOSTOIEVSKI if autor_norm == "dostoievski" else {autor_norm}, key=len, reverse=True)
        for alias in aliases:
            alias_norm = re.sub(r"[^a-z0-9]+", " ", _normalizar_busca(alias)).strip()
            norm = re.sub(rf"\s*[,–—-]\s*{re.escape(alias_norm)}\s*$", "", norm)
    norm = re.sub(r"[^a-z0-9]+", " ", norm)
    norm = re.sub(r"\s+", " ", norm).strip()
    return norm


def _chave_canonica_obra_busca(obra: Obra) -> str:
    titulo = _titulo_canonico_busca(obra.titulo, obra.autor)
    autor = _normalizar_autor_canonico(obra.autor)
    if not titulo or _titulo_tem_marcador_relacionado(titulo):
        return f"obra:{obra.id}"
    return f"{titulo}|{autor or 'autor-desconhecido'}"


def _titulo_exibicao_score(titulo: str | None, autor: str | None) -> tuple[int, int]:
    norm = _normalizar_busca(titulo)
    autor_norm = _normalizar_autor_canonico(autor)
    penalidade = 0
    if not titulo:
        penalidade += 1000
    if norm.endswith("...") or "..." in norm:
        penalidade += 40
    if "," in (titulo or ""):
        penalidade += 15
    if autor_norm and autor_norm in _titulo_canonico_busca(titulo, None):
        penalidade += 80
    return (penalidade, len(titulo or ""))


def _idioma_portugues(idioma: str | None) -> bool:
    norm = _normalizar_busca(idioma)
    return norm in {"pt", "pt-br", "por", "portugues", "portuguese"}


def _edicao_doc(obra: Obra, ed: Edicao, leituras_count: int = 0) -> dict:
    return {
        "ol_edition_key": ed.ol_edition_key or f"local:{ed.id}", "titulo_edicao": obra.titulo,
        "editora": ed.editora, "tradutor": ed.tradutor, "isbn": ed.isbn, "idioma": ed.idioma,
        "ano": ed.ano, "capa_url": ed.capa_url, "leituras_count": leituras_count,
    }


def _score_local(obra: Obra, ed: Edicao, q_norm: str, isbn: str, editora_norm: str, leituras_count: int) -> tuple[int, dict]:
    titulo = _normalizar_busca(obra.titulo)
    autor = _normalizar_busca(obra.autor)
    editora = _normalizar_busca(ed.editora)
    tradutor = _normalizar_busca(ed.tradutor)
    ed_isbn = normalizar_isbn(ed.isbn or "")
    match = {
        "titulo": bool(q_norm and q_norm in titulo),
        "autor": bool(q_norm and q_norm in autor),
        "editora": bool(q_norm and q_norm in editora) or bool(editora_norm and editora_norm in editora),
        "isbn": bool(isbn and ed_isbn == isbn),
    }
    score = 0
    if match["isbn"]:
        score += 100
    if q_norm and titulo == q_norm:
        score += 80
    elif q_norm and titulo.startswith(q_norm):
        score += 60
    elif match["titulo"]:
        score += 45
    if match["autor"]:
        score += 35
    if q_norm and q_norm in editora:
        score += 30
    if editora_norm and editora_norm in editora:
        score += 25
    if ed_isbn:
        score += 20
    if ed.capa_url:
        score += 15
    if _idioma_portugues(ed.idioma):
        score += 10
    if ed.ano or obra.ano:
        score += 5
    if q_norm and q_norm in tradutor:
        score += 20
    return score + min(leituras_count, 50), match


def _buscar_catalogo_local(q: str, s: Session, editora: str = "") -> list[dict]:
    q_norm = _normalizar_busca(q)
    editora_norm = _normalizar_busca(editora)
    isbn = normalizar_isbn(q or "")
    if not q_norm and not editora_norm:
        return []

    rows = s.exec(select(Obra, Edicao).join(Edicao, Edicao.obra_id == Obra.id).limit(5000)).all()
    ed_ids = [ed.id for _, ed in rows if ed.id is not None]
    leituras = dict(s.exec(
        select(Leitura.edicao_id, func.count())
        .where(Leitura.edicao_id.in_(ed_ids))
        .group_by(Leitura.edicao_id)
    ).all()) if ed_ids else {}

    por_obra: dict[str, dict] = {}
    for obra, ed in rows:
        leituras_count = int(leituras.get(ed.id, 0))
        score, match = _score_local(obra, ed, q_norm, isbn, editora_norm, leituras_count)
        searchable = " ".join([_normalizar_busca(obra.titulo), _normalizar_busca(obra.autor), _normalizar_busca(ed.isbn), _normalizar_busca(ed.editora), _normalizar_busca(ed.tradutor)])
        if q_norm and q_norm not in searchable and not (isbn and normalizar_isbn(ed.isbn or "") == isbn):
            continue
        if editora_norm and editora_norm not in _normalizar_busca(ed.editora):
            continue
        if score <= 0:
            continue
        chave = _chave_canonica_obra_busca(obra)
        bucket = por_obra.setdefault(chave, {"obras": {}, "items": [], "score": 0, "match": {"titulo": False, "autor": False, "editora": False, "isbn": False}})
        bucket["obras"][obra.id] = obra
        bucket["items"].append((score, leituras_count, obra, ed, match))
        bucket["score"] = max(bucket["score"], score)
        for key, value in match.items():
            bucket["match"][key] = bucket["match"][key] or value

    docs = []
    for bucket in por_obra.values():
        def ed_sort(item):
            score, leituras_count, _obra, ed, _match = item
            editora_hit = editora_norm and editora_norm in _normalizar_busca(ed.editora)
            return (bool(editora_hit), bool(ed.capa_url), bool(ed.isbn), _idioma_portugues(ed.idioma), ed.ano or 0, ed.id or 0, score, leituras_count)
        items = sorted(bucket["items"], key=ed_sort, reverse=True)
        best_score, best_leituras, obra, ed, best_match = items[0]
        obras_stats = {
            item_obra.id: {
                "obra": item_obra,
                "edicoes": 0,
                "capas": 0,
                "isbns": 0,
                "leituras": 0,
                "score": 0,
            }
            for _score, _leituras, item_obra, _item_ed, _match in items
        }
        for item_score, item_leituras, item_obra, item_ed, _match in items:
            stats = obras_stats[item_obra.id]
            stats["edicoes"] += 1
            stats["capas"] += 1 if item_ed.capa_url else 0
            stats["isbns"] += 1 if item_ed.isbn else 0
            stats["leituras"] += item_leituras
            stats["score"] = max(stats["score"], item_score)

        def obra_principal_sort(stats):
            principal = stats["obra"]
            titulo_score = _titulo_exibicao_score(principal.titulo, principal.autor)
            return (
                titulo_score[0], titulo_score[1],
                0 if principal.autor else 1,
                -stats["edicoes"], -stats["capas"], -stats["isbns"], -stats["leituras"],
                -(principal.id or 0),
            )

        obra_principal = sorted(obras_stats.values(), key=obra_principal_sort)[0]["obra"]
        edicoes_docs = []
        assinaturas_edicoes = set()
        for _score, item_leituras, item_obra, item_ed, _match in items:
            assinatura = (
                _titulo_canonico_busca(item_obra.titulo, item_obra.autor),
                _normalizar_busca(item_ed.editora),
                item_ed.ano or "",
                normalizar_isbn(item_ed.isbn or ""),
                item_ed.ol_edition_key or "",
            )
            if assinatura in assinaturas_edicoes:
                continue
            assinaturas_edicoes.add(assinatura)
            edicoes_docs.append(_edicao_doc(item_obra, item_ed, item_leituras))

        edicoes = edicoes_docs[:5]
        ed_doc = _edicao_doc(obra, ed, best_leituras)
        docs.append({
            "work_key": obra_principal.ol_work_key, "titulo": obra_principal.titulo, "autor": obra_principal.autor,
            "descricao": getattr(obra_principal, "descricao", "") or "",
            "idioma_original": obra_principal.idioma_original, "ano": obra_principal.ano, "tem_pt": _idioma_portugues(ed.idioma),
            "capa_url": ed.capa_url, "isbn_match": best_match["isbn"], "edicao_isbn": ed_doc, "edicoes": edicoes,
            "edicoes_encontradas": len(edicoes_docs),
            "chave_obra": chave_obra_canonica(obra_principal.titulo, obra_principal.autor),
            "_fonte": "local", "_ranking_score": bucket["score"], "_match": bucket["match"],
        })
    return sorted(docs, key=lambda d: (d.get("_ranking_score") or 0, d.get("edicao_isbn", {}).get("leituras_count") or 0), reverse=True)[:10]


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


class PerfilPayload(BaseModel):
    nome: Optional[str] = None
    handle: Optional[str] = None
    bio: Optional[str] = None


HANDLE_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{1,22}[a-z0-9])$")


def _normalizar_handle(valor: str) -> str:
    texto = unicodedata.normalize("NFKD", str(valor or "").strip().lower())
    texto = "".join(ch for ch in texto if not unicodedata.combining(ch))
    texto = re.sub(r"\s+", "-", texto)
    texto = re.sub(r"[^a-z0-9-]", "", texto)
    texto = re.sub(r"-{2,}", "-", texto)
    return texto[:24].strip("-")


def _validar_nome_publico(nome: str, email: str | None = None) -> str:
    nome = " ".join(str(nome or "").replace("\x00", "").split())
    if not nome:
        raise HTTPException(422, "Nome exibido é obrigatório.")
    if len(nome) < 2 or len(nome) > 40:
        raise HTTPException(422, "Nome exibido deve ter entre 2 e 40 caracteres.")
    if "@" in nome or (email and nome.lower() == email.lower()):
        raise HTTPException(422, "Escolha um nome público que não seja seu e-mail.")
    return html.escape(nome, quote=False)


def _validar_bio_curta(bio: str | None) -> str:
    bio = " ".join(str(bio or "").replace("\x00", "").split())
    if len(bio) > 160:
        raise HTTPException(422, "Bio curta deve ter no máximo 160 caracteres.")
    return html.escape(bio, quote=False)


def _validar_handle_publico(handle: str) -> str:
    handle = _normalizar_handle(handle)
    if not handle:
        raise HTTPException(422, "Use apenas letras, números e hífen.")
    if len(handle) < 3 or len(handle) > 24 or not HANDLE_RE.match(handle) or "--" in handle:
        raise HTTPException(422, "Use apenas letras, números e hífen.")
    return handle


@app.patch("/api/eu/perfil")
def atualizar_perfil(payload: PerfilPayload, request: Request, s: Session = Depends(get_session)):
    u = _require_google_user(request, s, "Entre com Google para editar seu perfil.", 401)
    if getattr(u, "is_demo", False):
        raise HTTPException(403, "Perfis de demonstração não podem ser editados.")
    nome = _validar_nome_publico(payload.nome if payload.nome is not None else u.nome, u.email)
    handle = _validar_handle_publico(payload.handle if payload.handle is not None else u.handle)
    bio = _validar_bio_curta(payload.bio if payload.bio is not None else getattr(u, "bio", ""))
    dono_handle = s.exec(select(Usuario).where(Usuario.handle == handle, Usuario.id != u.id)).first()
    if dono_handle:
        raise HTTPException(409, "Esse nome de usuário já está em uso.")
    u.nome = nome
    u.handle = handle
    u.bio = bio
    s.add(u); s.commit(); s.refresh(u)
    return {"handle": u.handle, "nome": u.nome, "bio": u.bio, "message": "Perfil atualizado."}


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

@app.get("/api/buscas/populares")
def buscas_populares(s: Session = Depends(get_session)):
    """Termos mais buscados (agregados do cache de busca) — alimenta as sugestões."""
    rows = s.exec(
        select(BuscaCache.query, BuscaCache.query_norm, func.count(BuscaCache.id))
        .where(BuscaCache.query_norm != "")
        .group_by(BuscaCache.query, BuscaCache.query_norm)
    ).all()
    # agrega por forma normalizada; a grafia exibida é a mais frequente
    buckets: dict[str, dict] = {}
    for query, query_norm, total in rows:
        termo = (query or query_norm or "").strip()
        chave = _normalizar_busca(termo)
        if not termo or len(chave) < 3 or normalizar_isbn(termo):
            continue
        total = int(total or 0)
        b = buckets.setdefault(chave, {"total": 0, "termo": termo, "termo_freq": 0})
        b["total"] += total
        if total > b["termo_freq"]:
            b["termo_freq"], b["termo"] = total, termo
    melhores = sorted(buckets.values(), key=lambda b: b["total"], reverse=True)[:8]
    return [{"termo": b["termo"], "total": b["total"]} for b in melhores]


@app.get("/api/eu")
def eu(request: Request, s: Session = Depends(get_session)):
    u = usuario_sessao(request, s)
    logado = bool(u.google_sub)
    return {
        "handle": u.handle,
        "nome": u.nome,
        "bio": getattr(u, "bio", ""),
        "email": u.email,
        "logado": logado,
        "provedor": "google" if logado else "anonimo",
        **_follow_counts(s, u.id),
        **_user_edition_counts(s, u.id),
    }


def _recon_resumo(docs, limite: int = 6) -> list[dict]:
    out = []
    for d in (docs or [])[:limite]:
        ed = d.get("edicao_isbn") or {}
        out.append({
            "titulo": d.get("titulo", ""),
            "autor": d.get("autor", ""),
            "ano": d.get("ano") or ed.get("ano"),
            "idioma": d.get("idioma_original") or ed.get("idioma") or "",
            "isbn": ed.get("isbn") or "",
            "tem_capa": bool(d.get("capa_url")),
        })
    return out


def _recon_mercado_livre(q: str) -> list[dict]:
    with httpx.Client(timeout=TIMEOUT, headers=_UA) as c:
        r = c.get("https://api.mercadolibre.com/sites/MLB/search", params={"q": q, "limit": 8})
        r.raise_for_status()
        data = r.json()
    out = []
    for it in (data.get("results") or [])[:8]:
        attrs = {a.get("id"): a.get("value_name") for a in (it.get("attributes") or [])}
        out.append({
            "titulo": it.get("title", ""),
            "autor": attrs.get("AUTHOR") or attrs.get("BOOK_AUTHOR") or "",
            "isbn": attrs.get("ISBN") or attrs.get("GTIN") or "",
            "ano": attrs.get("PUBLICATION_YEAR") or "",
            "editora": attrs.get("PUBLISHER") or "",
            "tem_capa": bool(it.get("thumbnail")),
        })
    return out


def _recon_penguin(q: str) -> dict | list:
    key = os.getenv("PENGUIN_API_KEY", "")
    if not key:
        return {"erro": "defina PENGUIN_API_KEY no ambiente para testar a Penguin"}
    dominio = os.getenv("PENGUIN_DOMAIN", "PRH.US")
    url = f"https://api.penguinrandomhouse.com/resources/v2/title/domains/{dominio}/search/title"
    with httpx.Client(timeout=TIMEOUT, headers=_UA) as c:
        r = c.get(url, params={"q": q, "rows": 8, "start": 0, "api_key": key})
        r.raise_for_status()
        data = r.json()
    bloco = data.get("data") if isinstance(data, dict) else {}
    titulos = (bloco or {}).get("titles") or (bloco or {}).get("results") or []
    out = []
    for t in titulos[:8]:
        if not isinstance(t, dict):
            continue
        out.append({
            "titulo": t.get("title") or t.get("titleweb") or "",
            "autor": t.get("author") or t.get("authorweb") or "",
            "isbn": str(t.get("isbn") or ""),
            "ano": str(t.get("onsaledate") or t.get("pubdate") or "")[:4],
            "editora": t.get("imprint") or t.get("division") or "",
        })
    return out or {"info": f"sem resultados no domínio {dominio}", "amostra_chaves": list(data)[:8] if isinstance(data, dict) else None}


@app.get("/api/_recon")
def api_recon(q: str = Query(..., min_length=2), token: str = Query("")):
    """Diagnóstico de cobertura de fontes (gated por RECON_TOKEN).
    Use no navegador: /api/_recon?q=comporte-se&token=SEU_TOKEN
    Desativado (404) enquanto RECON_TOKEN não estiver definido no ambiente."""
    if not RECON_TOKEN or token != RECON_TOKEN:
        raise HTTPException(404, "not found")
    resultado: dict = {"query": q, "fontes": {}}

    def _safe(label, fn):
        try:
            resultado["fontes"][label] = fn()
        except Exception as e:
            resultado["fontes"][label] = {"erro": repr(e)[:200]}

    _safe("pipeline_app", lambda: _recon_resumo(buscar_titulo_v2(q)))
    _safe("google_books", lambda: _recon_resumo(gbooks_buscar(q)))
    _safe("open_library", lambda: _recon_resumo(ol_buscar(q)))
    _safe("mercado_livre", lambda: _recon_mercado_livre(q))
    _safe("penguin_rh", lambda: _recon_penguin(q))
    return Response(json.dumps(resultado, ensure_ascii=False, indent=2), media_type="application/json; charset=utf-8")


@app.get("/api/buscar")
def buscar(q: str = Query(..., min_length=2), editora: str = Query(""), s: Session = Depends(get_session)):
    inicio = datetime.utcnow()
    logger.info("search_started", extra={"query_len": len(q)})
    locais = _buscar_catalogo_local(q, s, editora=editora)
    def _resposta_final(externos: list[dict]) -> list[dict]:
        return consolidar_resultados_busca_final(q, locais + (externos or []))

    isbn = normalizar_isbn(q)
    if isbn:
        try:
            achado = _edicao_por_isbn(isbn)
        except Exception:
            logger.warning("external_search_failed", extra={"provider": "isbn"}, exc_info=True)
            achado = None
        externos = [achado] if achado else []
        logger.info("search_finished", extra={"query_len": len(q), "locais_count": len(locais), "externos_count": len(externos), "elapsed_ms": int((datetime.utcnow() - inicio).total_seconds() * 1000)})
        return _resposta_final(externos)

    cache = _cache_get(q, s)
    if cache:
        resposta = _resposta_final(cache)
        logger.info("search_cache_hit", extra={"query_len": len(q), "locais_count": len(locais), "externos_count": len(cache), "elapsed_ms": int((datetime.utcnow() - inicio).total_seconds() * 1000)})
        return resposta

    try:
        logger.info("external_search_started", extra={"provider": "google_books", "query_len": len(q)})
        docs = buscar_titulo_v2(q)
        if docs:
            docs = consolidar_resultados_busca_final(q, docs)
            _cache_set(q, docs, s)
            resposta = _resposta_final(docs)
            logger.info("search_finished", extra={"query_len": len(q), "locais_count": len(locais), "externos_count": len(docs), "elapsed_ms": int((datetime.utcnow() - inicio).total_seconds() * 1000)})
            return resposta
        logger.info("external_search_started", extra={"provider": "open_library", "query_len": len(q)})
        docs = ol_buscar(q)
        docs = consolidar_resultados_busca_final(q, docs)
        _cache_set(q, docs, s)
        resposta = _resposta_final(docs)
        logger.info("search_finished", extra={"query_len": len(q), "locais_count": len(locais), "externos_count": len(docs), "elapsed_ms": int((datetime.utcnow() - inicio).total_seconds() * 1000)})
        return resposta
    except Exception:
        logger.warning("external_search_failed", extra={"provider": "google_books", "query_len": len(q)}, exc_info=True)
        try:
            logger.info("external_search_started", extra={"provider": "open_library", "query_len": len(q)})
            docs = ol_buscar(q)
            docs = consolidar_resultados_busca_final(q, docs)
            _cache_set(q, docs, s)
            resposta = _resposta_final(docs)
            logger.info("search_finished", extra={"query_len": len(q), "locais_count": len(locais), "externos_count": len(docs), "elapsed_ms": int((datetime.utcnow() - inicio).total_seconds() * 1000)})
            return resposta
        except Exception:
            logger.error("external_search_failed", extra={"provider": "open_library", "query_len": len(q)}, exc_info=True)
            raise HTTPException(502, "busca indisponível")


@app.get("/api/editoras")
def api_listar_editoras(s: Session = Depends(get_session)):
    return listar_editoras(s)


@app.get("/api/edicoes")
def edicoes(work_key: str = Query(..., min_length=1)):
    logger.info("[editions start] work_key=%r", work_key)
    if not work_key.strip():
        raise HTTPException(422, "work_key é obrigatório")
    try:
        return ol_edicoes(work_key)
    except Exception:
        logger.warning("[editions error] work_key=%r", work_key, exc_info=True)
        raise HTTPException(502, "Open Library indisponível")


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
    edicoes_locais = s.exec(select(Edicao).where(Edicao.obra_id == obra.id)).all()
    ed_por_id = {ed.id: ed for ed in edicoes_locais}
    all_ed_ids = list(ed_por_id.keys())
    rel_map = _edition_relation_map(s, usuario_id, all_ed_ids)
    social_counts = {ed_id: _edition_stats(s, ed_id) for ed_id in all_ed_ids}
    for ed_id, ed in ed_por_id.items():
        st = por_edicao.get(ed_id, {"leituras": 0, "notas": []})
        counts = social_counts.get(ed_id, {})
        edicoes.append({
            "edicao_id": ed_id,
            "ol_edition_key": ed.ol_edition_key,
            "leituras": st["leituras"],
            "tem": counts.get("tem", 0),
            "querem": counts.get("querem", 0),
            "media": round(sum(st["notas"]) / len(st["notas"]), 2) if st["notas"] else None,
            "estado": {**rel_map.get(ed_id, {"tenho": False, "quero": False}), "li": _edition_read_by_user(s, ed_id, usuario_id)},
            "edicao": {
                "editora": ed.editora, "ano": ed.ano,
                "tradutor": ed.tradutor, "isbn": ed.isbn,
                "idioma": ed.idioma, "capa_url": ed.capa_url,
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
        "obra": {"id": obra.id, "work_key": obra.ol_work_key, "titulo": obra.titulo, "autor": obra.autor, "ano": obra.ano, "idioma_original": obra.idioma_original, "descricao": obra.descricao or ""},
        "estatisticas": {
            "leituras": len(leituras),
            "criticas": len(criticas),
            "media": round(sum(notas) / len(notas), 2) if notas else None,
            "lendo": sum(1 for l in leituras if (l.status or "").lower() == "lendo"),
            "querem": sum(e.get("querem", 0) for e in edicoes),
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
            "estatisticas": {"leituras": 0, "criticas": 0, "media": None, "lendo": 0, "querem": 0},
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
    capitulo_ordem: Optional[int] = None
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
    capitulo_ordem = data.get("capitulo_ordem")

    pagina_valida = pagina is not None and pagina > 0
    porcentagem_valida = porcentagem is not None and 0 <= porcentagem <= 100
    capitulo_valido = bool(capitulo)
    capitulo_ordem_valida = capitulo_ordem is not None and capitulo_ordem > 0

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
        "capitulo_ordem": capitulo_ordem if tipo == "capitulo" and capitulo_valido and capitulo_ordem_valida else None,
        "nota": nota,
        "publico": bool(data.get("publico", False)),
        "spoiler": bool(data.get("spoiler", False))
    }

def _diario_payload(entry: ReadingJournalEntry, l: Leitura | None = None, ed: Edicao | None = None, o: Obra | None = None) -> dict:
    return {
        "id": entry.id, "leitura_id": entry.leitura_id, "progresso_tipo": entry.progresso_tipo,
        "pagina": entry.pagina, "porcentagem": entry.porcentagem, "capitulo": entry.capitulo,
        "capitulo_ordem": entry.capitulo_ordem,
        "nota": entry.nota, "publico": bool(entry.publico), "spoiler": bool(entry.spoiler),
        "created_at": entry.created_at.isoformat(), "updated_at": entry.updated_at.isoformat(),
        **({"status": l.status, "titulo": o.titulo, "autor": o.autor, "capa_url": ed.capa_url} if l and ed and o else {}),
    }


def _registrar_capitulo_sumario(edicao_id: int, ordem: int | None, titulo: str, s: Session, fonte: str = "comunidade") -> None:
    """Registra uma posição no sumário da edição (primeira vez escreve, não sobrescreve
    contribuição já existente na mesma posição — sem moderação ainda, então evita
    disputa de edição; a leitura de /capitulos já cai pro fallback por popularidade
    onde o sumário estruturado estiver incompleto)."""
    if not ordem or not titulo:
        return
    ja_existe = s.exec(
        select(EdicaoCapitulo).where(EdicaoCapitulo.edicao_id == edicao_id, EdicaoCapitulo.ordem == ordem)
    ).first()
    if ja_existe:
        return
    try:
        s.add(EdicaoCapitulo(edicao_id=edicao_id, ordem=ordem, titulo=titulo, fonte=fonte))
        s.commit()
    except SQLAlchemyError:
        s.rollback()


@app.get("/api/leitura/{leitura_id}/diario")
def listar_diario_leitura(leitura_id: int, request: Request, s: Session = Depends(get_session)):
    u = usuario_sessao(request, s)
    _leitura_do_usuario(leitura_id, u.id, s)
    entries = s.exec(select(ReadingJournalEntry).where(ReadingJournalEntry.leitura_id == leitura_id, ReadingJournalEntry.usuario_id == u.id).order_by(ReadingJournalEntry.created_at.desc())).all()
    return [_diario_payload(e) for e in entries]


@app.get("/api/edicoes/{edicao_id}/capitulos")
def listar_capitulos_edicao(edicao_id: int, s: Session = Depends(get_session)):
    """Sumário da edição pro autocomplete/seletor de capítulo no diário.

    Prioridade: sumário estruturado (EdicaoCapitulo, ordenado — comunidade ou
    Open Library) e, só onde a posição ainda não foi preenchida, cai pro
    fallback antigo (capítulos que leitores digitaram sem posição, por
    popularidade). Cresce sozinho com o uso; não depende de a editora publicar
    um sumário (a maioria não publica)."""
    estruturado = s.exec(
        select(EdicaoCapitulo).where(EdicaoCapitulo.edicao_id == edicao_id).order_by(EdicaoCapitulo.ordem)
    ).all()
    if estruturado:
        return [{"titulo": c.titulo, "ordem": c.ordem, "fonte": c.fonte} for c in estruturado]
    edicao = s.get(Edicao, edicao_id)
    if edicao and edicao.ol_edition_key:
        for item in ol_table_of_contents(edicao.ol_edition_key):
            _registrar_capitulo_sumario(edicao_id, item["ordem"], item["titulo"], s, fonte="openlibrary")
        estruturado = s.exec(
            select(EdicaoCapitulo).where(EdicaoCapitulo.edicao_id == edicao_id).order_by(EdicaoCapitulo.ordem)
        ).all()
        if estruturado:
            return [{"titulo": c.titulo, "ordem": c.ordem, "fonte": c.fonte} for c in estruturado]
    rows = s.exec(
        select(ReadingJournalEntry.capitulo, func.count())
        .join(Leitura, ReadingJournalEntry.leitura_id == Leitura.id)
        .where(
            Leitura.edicao_id == edicao_id,
            ReadingJournalEntry.progresso_tipo == "capitulo",
            ReadingJournalEntry.capitulo != "",
        )
        .group_by(ReadingJournalEntry.capitulo)
        .order_by(func.count().desc())
        .limit(50)
    ).all()
    return [{"titulo": capitulo, "ordem": None, "fonte": "comunidade"} for capitulo, _contagem in rows]


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
    leitura = _leitura_do_usuario(leitura_id, u.id, s)
    data = _validar_diario(payload)
    entry = ReadingJournalEntry(leitura_id=leitura_id, usuario_id=u.id, **data)
    try:
        s.add(entry); s.commit(); s.refresh(entry)
    except SQLAlchemyError:
        s.rollback()
        logger.exception("diary_create_failed", extra={"leitura_id": leitura_id, "usuario_id": u.id})
        raise HTTPException(500, "não foi possível salvar a entrada do diário")
    _registrar_capitulo_sumario(leitura.edicao_id, data.get("capitulo_ordem"), data.get("capitulo", ""), s)
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
        logger.exception("diary_update_failed", extra={"entrada_id": entrada_id, "usuario_id": u.id})
        raise HTTPException(500, "não foi possível salvar a entrada do diário")
    leitura = s.get(Leitura, entry.leitura_id)
    if leitura:
        _registrar_capitulo_sumario(leitura.edicao_id, data.get("capitulo_ordem"), data.get("capitulo", ""), s)
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


def _validar_entrada_leitura(e, exigir_autor: bool = True):
    if not e.titulo.strip():
        raise HTTPException(422, "título é obrigatório")
    # Livros vindos do catálogo podem estar sem autor (ex.: Editora 34, cujo scraper
    # ainda não extrai autor) — não dá pra travar o registro de leitura por causa
    # disso. O cadastro manual continua exigindo autor (pelo próprio formulário).
    if exigir_autor and not e.autor.strip():
        raise HTTPException(422, "título e autor são obrigatórios")
    if e.status not in STATUS_LEITURA:
        raise HTTPException(422, "status inválido")


def _motivo_db_erro(exc: Exception) -> str:
    """Resumo curto e legível de um erro do banco (o driver anexa detalhes em .orig)."""
    origem = getattr(exc, "orig", None) or exc
    texto = " ".join(str(origem).split())
    return texto[:180] if texto else exc.__class__.__name__




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
    # Registro a partir do catálogo: autor pode faltar na edição, então não exigimos.
    _validar_entrada_leitura(e, exigir_autor=False)
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
        logger.exception("reading_save_failed", extra={"usuario_id": u.id})
        # Devolve o motivo real (curto) além de logar: sem acesso aos logs, era
        # impossível saber se é tabela faltando, sequence do id, etc.
        motivo = _motivo_db_erro(exc)
        raise HTTPException(500, f"erro ao salvar leitura ({motivo}); verifique as migrações do banco")
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
        logger.exception("shelf_load_failed", extra={"usuario_id": u.id})
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
            "handle": autor.handle, "nome": autor.nome, "is_demo": bool(getattr(autor, "is_demo", False)),
            "is_following": _is_following(s, atual_id, autor.id),
            "is_me": bool(atual_id and atual_id == autor.id),
        },
        "livro": {"titulo": o.titulo, "autor": o.autor, "work_key": o.ol_work_key, "capa_url": ed.capa_url},
        "edicao": {"editora": ed.editora, "tradutor": ed.tradutor, "ano": ed.ano},
        "leitura": {
            "leitura_id": l.id, "status": l.status, "nota": l.nota, "publico": bool(l.publico),
            "is_demo": bool(getattr(l, "is_demo", False)), "spoiler": bool(l.spoiler), "relato": (relato[:220] if trecho else relato),
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
        .order_by(Leitura.is_demo.asc(), Leitura.criado_em.desc())
        .limit(limit)
    ).all()
    reviews = [_feed_review_item(s, l, ed, o, autor, atual, trecho=False) for l, ed, o, autor in rows if (l.relato or "").strip()]

    active_rows = s.exec(
        select(Usuario, func.count(Leitura.id).label("reviews_count"))
        .join(Leitura, Leitura.usuario_id == Usuario.id)
        .where(Leitura.publico == True, Leitura.relato != "")
        .group_by(Usuario.id)
        .order_by(Usuario.is_demo.asc(), func.count(Leitura.id).desc())
        .limit(20)
    ).all()
    readers = []
    for leitor, reviews_count in active_rows:
        if atual.id and leitor.id == atual.id:
            continue
        readers.append({
            "handle": leitor.handle, "nome": leitor.nome, "is_demo": bool(getattr(leitor, "is_demo", False)), "reviews_count": reviews_count,
            "followers_count": _follow_counts(s, leitor.id)["followers_count"],
            "is_following": _is_following(s, atual.id, leitor.id), "is_me": False,
        })
        if len(readers) >= 10:
            break
    return {"reviews": reviews, "readers": readers}

# ─── estante pública ──────────────────────────────────────
@app.get("/api/u/{handle}")
def estante_json(handle: str, request: Request, s: Session = Depends(get_session)):
    logger.info("public_profile_payload_started", extra={"handle_len": len(handle or "")})
    u = s.exec(select(Usuario).where(Usuario.handle == handle.lower().strip())).first()
    if not u:
        raise HTTPException(404, "estante não encontrada")
    atual = usuario_sessao(request, s)
    leituras = _leituras_de(s, u.id)
    for l in leituras:
        if l.get("publico") and (l.get("relato") or "").strip():
            l.update(_review_state(s, l.get("leitura_id"), atual.id))
    perfil = resumo_perfil_publico(leituras)
    return {"handle": u.handle, "nome": u.nome, "bio": getattr(u, "bio", ""), "leituras": leituras, **perfil, **_profile_social_payload(s, u, atual)}


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
    logger.info("public_profile_render_started", extra={"handle_len": len(handle or "")})
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


# ─── páginas das editoras ─────────────────────────────────
@app.get("/editoras")
def indice_editoras(s: Session = Depends(get_session)):
    return HTMLResponse(render_indice_editoras(listar_editoras(s)))


@app.get("/editora/{slug}")
def pagina_editora(slug: str, s: Session = Depends(get_session)):
    dados = dados_editora(s, slug.lower().strip())
    if not dados:
        corpo = (
            '<div class="wordmark">LOMBADA<span class="dot">.</span></div>'
            '<div class="empty">essa editora ainda não está no catálogo.</div>'
            '<a class="cta" href="/editoras">ver todas as editoras →</a>'
        )
        return HTMLResponse(_pagina("editora não encontrada · Lombada", corpo), status_code=404)
    return HTMLResponse(render_pagina_editora(dados))



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
    corpo = '<div class="app"><div class="wordmark">LOMBADA<span class="dot">.</span></div><h1>Admin</h1><p><a href="/admin/source-records">Revisar source_records de editoras</a></p><h2>Denúncias pendentes</h2>' + (''.join(report_items) or '<p>Nenhuma denúncia pendente.</p>') + '<h2>Sugestões pendentes</h2>' + (''.join(items) or '<p>Nenhuma sugestão pendente.</p>') + '</div>'
    return HTMLResponse(_pagina("Admin · Lombada", corpo))


SOURCE_RECORD_FILTERS = {
    "pending": "status = 'pending'",
    "missing_isbn": "trim(coalesce(isbn, '')) = ''",
    "missing_author": "trim(coalesce(author, '')) = ''",
    "missing_thumbnail": "trim(coalesce(thumbnail, '')) = ''",
    "low_confidence": "confidence_score < 0.5",
    "approved": "status = 'approved'",
    "rejected": "status = 'rejected'",
}


def _source_record_work_key(titulo: str, autor: str) -> str:
    base = (titulo or "").strip().lower() + "|" + (autor or "").strip().lower()
    return "src:" + hashlib.sha1(base.encode("utf-8")).hexdigest()[:24]


def _promote_source_record(s: Session, sr_id: int) -> None:
    sr = s.exec(text("SELECT id, title, author, isbn, publisher, publication_year, thumbnail FROM source_records WHERE id = :id"), {"id": sr_id}).mappings().first()
    if not sr:
        raise HTTPException(404, "source_record não encontrado")
    titulo = _plain_text(sr["title"], 240)
    autor = _plain_text(sr["author"], 240)
    isbn = normalizar_isbn(_plain_text(sr["isbn"], 32))
    if not titulo or not isbn:
        raise HTTPException(422, "só é possível aprovar/promover registros com title e isbn válidos")

    edicao = s.exec(select(Edicao).where(Edicao.isbn == isbn)).first()
    if edicao:
        s.exec(text("UPDATE source_records SET status = 'approved', updated_at = CURRENT_TIMESTAMP WHERE id = :id"), {"id": sr_id})
        s.commit()
        return

    obra = None
    if autor:
        obra = s.exec(select(Obra).where(func.lower(Obra.titulo) == titulo.lower(), func.lower(Obra.autor) == autor.lower())).first()
    if not obra:
        obra = s.exec(select(Obra).where(func.lower(Obra.titulo) == titulo.lower())).first()
    if not obra:
        obra = Obra(
            ol_work_key=_source_record_work_key(titulo, autor),
            titulo=titulo,
            autor=autor,
            idioma_original="",
            ano=sr["publication_year"],
        )
        s.add(obra); s.commit(); s.refresh(obra)

    s.add(Edicao(
        obra_id=obra.id,
        ol_edition_key="isbn:" + isbn,
        editora=_plain_text(sr["publisher"], 160),
        tradutor="",
        isbn=isbn,
        idioma="Português",
        ano=sr["publication_year"],
        capa_url=_plain_text(sr["thumbnail"], 500),
    ))
    s.exec(text("UPDATE source_records SET status = 'approved', updated_at = CURRENT_TIMESTAMP WHERE id = :id"), {"id": sr_id})
    s.commit()


@app.get("/admin/source-records")
def admin_source_records(request: Request, filter: str = Query("pending"), source: str = Query(""), s: Session = Depends(get_session)):
    _require_admin(request, s)
    where = SOURCE_RECORD_FILTERS.get(filter, "1=1")
    params = {}
    if source:
        where += " AND source = :source"
        params["source"] = source

    counts = s.exec(text("""
        SELECT
          count(*) AS total,
          count(*) FILTER (WHERE status = 'pending') AS pending,
          count(*) FILTER (WHERE status = 'approved') AS approved,
          count(*) FILTER (WHERE status = 'rejected') AS rejected,
          count(*) FILTER (WHERE trim(coalesce(isbn, '')) = '') AS missing_isbn,
          count(*) FILTER (WHERE trim(coalesce(author, '')) = '') AS missing_author,
          count(*) FILTER (WHERE confidence_score < 0.5) AS low_confidence
        FROM source_records
    """)).mappings().first()
    by_source = s.exec(text("SELECT source, count(*) AS total FROM source_records GROUP BY source ORDER BY total DESC, source")).mappings().all()
    sources = [r["source"] for r in by_source]

    rows = s.exec(text(f"""
        SELECT sr.*,
          EXISTS (
            SELECT 1 FROM source_records dup
            WHERE dup.id <> sr.id
              AND trim(coalesce(dup.isbn, '')) <> ''
              AND dup.isbn = sr.isbn
              AND lower(trim(coalesce(dup.title, ''))) <> lower(trim(coalesce(sr.title, '')))
          ) AS duplicate_isbn_title,
          EXISTS (
            SELECT 1 FROM obra o
            WHERE trim(coalesce(sr.author, '')) = ''
              AND lower(o.titulo) LIKE '%' || lower(trim(coalesce(sr.title, ''))) || '%'
          ) AS similar_existing_missing_author
        FROM source_records sr
        WHERE {where}
        ORDER BY updated_at DESC
        LIMIT 100
    """), params).mappings().all()

    filter_links = " ".join(
        f'<a href="/admin/source-records?filter={_esc(k)}">{_esc(label)}</a>'
        for k, label in {
            "all": "todos",
            "pending": "todos pendentes",
            "missing_isbn": "sem ISBN",
            "missing_author": "sem autor",
            "missing_thumbnail": "sem capa",
            "low_confidence": "baixa confiança",
            "approved": "já aprovados",
            "rejected": "rejeitados",
        }.items()
    )
    source_options = ''.join(f'<option value="{_esc(src)}" {"selected" if src == source else ""}>{_esc(src)}</option>' for src in sources)
    summary = (
        f'<p class="meta">total={counts["total"]} · pendentes={counts["pending"]} · aprovados={counts["approved"]} · '
        f'rejeitados={counts["rejected"]} · sem ISBN={counts["missing_isbn"]} · sem autor={counts["missing_author"]} · '
        f'baixa confiança={counts["low_confidence"]}</p>'
        '<h3>Por editora/source</h3><ul>' + ''.join(f'<li>{_esc(r["source"])}: {r["total"]}</li>' for r in by_source) + '</ul>'
    )
    items = []
    for r in rows:
        badges = []
        if r["duplicate_isbn_title"]:
            badges.append("ISBN repetido com título diferente")
        if r["similar_existing_missing_author"]:
            badges.append("título parecido com obra existente e autor ausente")
        thumb = f'<img src="{_esc(r["thumbnail"])}" alt="" style="max-width:72px;max-height:110px;float:right;margin-left:12px">' if r["thumbnail"] else ""
        permalink = f'<a href="{_esc(r["permalink"])}" rel="noopener noreferrer" target="_blank">abrir original</a>' if r["permalink"] else "sem permalink"
        items.append(f'''
          <article class="card-form" style="margin:16px 0;overflow:auto">{thumb}
            <div class="meta">#{r["id"]} · {_esc(r["source"])} · status={_esc(r["status"])} · confiança={r["confidence_score"]} · criado={r["created_at"]} · atualizado={r["updated_at"]}</div>
            <p><strong>{_esc(r["title"]) or "(sem título)"}</strong> — {_esc(r["author"]) or "(sem autor)"}</p>
            <p>ISBN: {_esc(r["isbn"]) or "(sem ISBN)"} · editora: {_esc(r["publisher"])} · ano: {_esc(r["publication_year"])}</p>
            <p>{permalink}</p>
            <p class="meta">{_esc(" · ".join(badges))}</p>
            <form method="post" action="/admin/source-records/{r["id"]}/edit">
              <input name="title" value="{_esc(r["title"])}" placeholder="title">
              <input name="author" value="{_esc(r["author"])}" placeholder="author">
              <input name="isbn" value="{_esc(r["isbn"])}" placeholder="isbn">
              <input name="publisher" value="{_esc(r["publisher"])}" placeholder="publisher">
              <input name="publication_year" value="{_esc(r["publication_year"])}" placeholder="ano">
              <input name="thumbnail" value="{_esc(r["thumbnail"])}" placeholder="thumbnail">
              <button>Salvar</button>
            </form>
            <form method="post" action="/admin/source-records/{r["id"]}/pending" style="display:inline"><button>Marcar pending</button></form>
            <form method="post" action="/admin/source-records/{r["id"]}/rejected" style="display:inline"><button>Rejeitar</button></form>
            <form method="post" action="/admin/source-records/{r["id"]}/approve" style="display:inline"><button>Aprovar/promover</button></form>
          </article>
        ''')
    corpo = (
        '<div class="app"><div class="wordmark">LOMBADA<span class="dot">.</span></div>'
        '<h1>Revisão de source_records</h1><p><a href="/admin">voltar ao admin</a></p>'
        + summary + '<h2>Filtros</h2><p>' + filter_links + '</p>'
        f'<form method="get"><input type="hidden" name="filter" value="{_esc(filter)}"><select name="source"><option value="">todas as sources</option>{source_options}</select><button>Filtrar source</button></form>'
        + (''.join(items) or '<p>Nenhum registro para este filtro.</p>') + '</div>'
    )
    return HTMLResponse(_pagina("Source records · Admin · Lombada", corpo))


@app.post("/admin/source-records/{source_record_id}/edit")
async def admin_source_record_edit(source_record_id: int, request: Request, s: Session = Depends(get_session)):
    _require_admin(request, s)
    raw_body = (await request.body()).decode("utf-8", errors="replace")
    parsed_form = parse_qs(raw_body, keep_blank_values=True)
    form = {key: values[-1] if values else "" for key, values in parsed_form.items()}
    isbn = normalizar_isbn(_plain_text(form.get("isbn"), 32))
    s.exec(text("""
        UPDATE source_records
        SET title = :title, author = :author, isbn = :isbn, publisher = :publisher,
            publication_year = :publication_year, thumbnail = :thumbnail, updated_at = CURRENT_TIMESTAMP
        WHERE id = :id
    """), {
        "id": source_record_id,
        "title": _plain_text(form.get("title"), 240),
        "author": _plain_text(form.get("author"), 240),
        "isbn": isbn,
        "publisher": _plain_text(form.get("publisher"), 160),
        "publication_year": _parse_int_optional(form.get("publication_year")),
        "thumbnail": _plain_text(form.get("thumbnail"), 500),
    })
    s.commit()
    return HTMLResponse('<meta http-equiv="refresh" content="0; url=/admin/source-records">')


@app.post("/admin/source-records/{source_record_id}/{action}")
def admin_source_record_action(source_record_id: int, action: str, request: Request, s: Session = Depends(get_session)):
    _require_admin(request, s)
    if action == "approve":
        _promote_source_record(s, source_record_id)
    elif action in {"pending", "rejected"}:
        s.exec(text("UPDATE source_records SET status = :status, updated_at = CURRENT_TIMESTAMP WHERE id = :id"), {"id": source_record_id, "status": action})
        s.commit()
    else:
        raise HTTPException(404, "ação inválida")
    return HTMLResponse('<meta http-equiv="refresh" content="0; url=/admin/source-records">')



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
