"""
Lombada — app FastAPI e rotas.
"""
import html
import base64
import hashlib
import time
import ipaddress
import json
import logging
import os
import re
import socket
import threading
import unicodedata
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional
from uuid import uuid4
from datetime import datetime, timedelta
from math import ceil
from urllib.parse import parse_qs, urlparse

import httpx
from fastapi import FastAPI, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy import text, or_, and_
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import SQLModel, Session, select, func
from starlette.middleware.sessions import SessionMiddleware

from models import SECRET_KEY, engine, Usuario, Obra, Edicao, Leitura, Follow, ReviewLike, SavedReview, ReviewReport, ProfileReport, ReviewComment, CatalogSuggestion, UserEdition, ReadingJournalEntry, EdicaoCapitulo, BuscaCache, Notificacao, UserReadingStatus, TextoUsuario, get_session, migrar
from feature_flags import feature_enabled
from auth import usuario_sessao, router as auth_router
from api_publica import router as public_api_router
from fontes import ol_edicoes, normalizar_isbn, gbooks_buscar, chave_obra_canonica, ol_table_of_contents, paginas_por_isbn, TIMEOUT, _UA
from busca import _cache_get, _cache_set, buscar_titulo_v2, ol_buscar, _edicao_por_isbn, consolidar_resultados_busca_final
from publica import render_estante_publica, render_texto_publico, _leituras_de, _pagina, _esc, resumo_perfil_publico
from editoras import listar_editoras, dados_editora, render_pagina_editora, render_indice_editoras
from landing import (render_landing, render_quem_somos, render_blog_index,
                     render_blog_post, render_privacidade, render_api_docs)
import blog as blog_mod

AQUI = Path(__file__).resolve().parent
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "true").lower() == "true"
# Versão exposta em /api/version e usada como cache-buster (?v=) dos assets no
# index.html. O Railway não define APP_VERSION, mas injeta o SHA do commit de
# cada deploy — usá-lo garante que a URL do app.js/app.css muda a cada deploy
# e o Cloudflare/navegador não seguram JS antigo. "dev" só em ambiente local.
APP_VERSION = (
    os.getenv("APP_VERSION", "").strip()
    or os.getenv("RAILWAY_GIT_COMMIT_SHA", "").strip()[:12]
    or "dev"
)
RECON_TOKEN = os.getenv("RECON_TOKEN", "")
# Links externos da landing (/sobre). Vazios → botão/link some.
APOIO_URL = os.getenv("APOIO_URL", "").strip()          # ex.: https://apoia.se/lombada
PLAY_STORE_URL = os.getenv("PLAY_STORE_URL", "").strip()  # preencher quando publicar na Play
INSTAGRAM_URL = os.getenv("INSTAGRAM_URL", "").strip()
BLOG_URL = os.getenv("BLOG_URL", "").strip()             # link "blog" no menu (some se vazio)
# Amazon Associados: tag de afiliado (ex.: "lombada-20"). Vazio → botão de
# compra some. O link usa a busca por ISBN (mais robusto que /dp/{asin}).
AMAZON_ASSOC_TAG = os.getenv("AMAZON_ASSOC_TAG", "").strip()
# Contato exibido na política de privacidade (/privacidade).
CONTACT_EMAIL = os.getenv("CONTACT_EMAIL", "").strip()
# TWA (app Android via Trusted Web Activity): Digital Asset Links em
# /.well-known/assetlinks.json. Preencher com o package do app e a(s) impressão(ões)
# SHA-256 do certificado de assinatura (Play App Signing informa) — várias
# separadas por vírgula. Vazio → assetlinks devolve lista vazia (não verifica ainda).
ANDROID_PACKAGE_NAME = os.getenv("ANDROID_PACKAGE_NAME", "").strip()
ANDROID_CERT_SHA256 = os.getenv("ANDROID_CERT_SHA256", "").strip()
logger = logging.getLogger(__name__)


def _rss_mb() -> float | None:
    try:
        with open("/proc/self/status", "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    kb = int(line.split()[1])
                    return round(kb / 1024, 1)
    except Exception:
        return None
    return None


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


# Teto de handlers síncronos rodando ao mesmo tempo. FastAPI executa cada rota
# `def` num pool de threads (padrão 40). Num único worker em 512 MB, 40 buscas/
# proxies simultâneos (crawler + usuários) somam picos de memória e conexões que
# derrubam o processo por OOM. Serializar um pouco troca latência por sobreviver.
try:
    MAX_SYNC_CONCURRENCY = max(1, int(os.getenv("MAX_SYNC_CONCURRENCY", "12")))
except ValueError:
    MAX_SYNC_CONCURRENCY = 12


# ─── lifespan ─────────────────────────────────────────────
def _preparar_banco():
    # A preparação do banco não pode derrubar nem travar o processo: se o banco
    # estiver indisponível no boot, o app ainda precisa subir e responder
    # /healthz para o deploy ficar saudável. Fazemos um preflight único — assim
    # não gastamos minutos em timeouts de connect encadeados dentro de migrar()
    # — e só rodamos create_all/migração/seed quando o banco responde.
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception:
        logger.exception("startup_db_unreachable_skipping_setup")
        return

    for etapa, acao in (
        ("create_all", lambda: SQLModel.metadata.create_all(engine)),
        ("migrar", migrar),
        ("seed_demo_content", seed_demo_content),
        ("seed_catalog_content", seed_catalog_content),
    ):
        try:
            acao()
        except Exception:
            logger.exception("startup_step_failed", extra={"step": etapa})
    logger.info("startup_db_setup_finished")


@asynccontextmanager
async def lifespan(app):
    try:
        import anyio
        anyio.to_thread.current_default_thread_limiter().total_tokens = MAX_SYNC_CONCURRENCY
        logger.info("sync_concurrency_limit_set", extra={"tokens": MAX_SYNC_CONCURRENCY})
    except Exception:
        logger.warning("sync_concurrency_limit_failed", exc_info=True)

    # O setup do banco roda fora do caminho do boot quando o banco é remoto:
    # tudo que acontece antes do yield segura o uvicorn de aceitar conexões, e
    # com Postgres as dezenas de round-trips de migrar()/seeds já estouraram o
    # healthcheck do deploy (300s) em dias de rede lenta. Numa thread, o
    # /healthz responde em segundos e as migrações terminam em paralelo —
    # servir antes do setup completo já era um estado aceito (banco fora no
    # boot pula o setup todo). Com SQLite (testes, dev local) não há rede e o
    # setup é imediato, então roda síncrono pra manter o boot determinístico.
    if engine.dialect.name == "sqlite":
        _preparar_banco()
    else:
        threading.Thread(target=_preparar_banco, name="db-setup", daemon=True).start()

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
    rss_inicio = _rss_mb() if request.url.path == "/api/capa" else None
    started = time.monotonic()
    response = await call_next(request)
    if request.url.path.startswith(SENSITIVE_NO_STORE_PREFIXES):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    if request.url.path == "/api/capa":
        logger.info(
            "cover_proxy_request_finished",
            extra={
                "status_code": response.status_code,
                "elapsed_ms": int((time.monotonic() - started) * 1000),
                "rss_start_mb": rss_inicio,
                "rss_end_mb": _rss_mb(),
            },
        )
    return response


app.mount("/static", StaticFiles(directory=str(AQUI / "static")), name="static")
app.include_router(auth_router)
app.include_router(public_api_router)

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


@app.get("/api/config")
def api_config():
    # config pública consumida pelo frontend. Campos vazios → recurso desligado
    # (ex.: sem tag da Amazon, o botão "Comprar" não é renderizado).
    return {"amazon_tag": AMAZON_ASSOC_TAG}


# ─── proxy de capa (anti-SSRF) ────────────────────────────
CAPA_MAX_BYTES = 5 * 1024 * 1024
CAPA_TIMEOUT = httpx.Timeout(4.0, connect=2.0, read=3.0, write=3.0, pool=2.0)
CAPA_CHUNK_SIZE = 64 * 1024
CAPA_CACHE_CONTROL = "public, max-age=86400, stale-while-revalidate=604800"
CAPA_CONTENT_TYPES = {"image/jpeg", "image/jpg", "image/png", "image/webp", "image/avif"}


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


async def proxy_capa(url: str) -> Response:
    p = urlparse(url or "")
    hostname = p.hostname
    if p.scheme != "https" or not _host_publico(hostname):
        logger.warning("cover_proxy_invalid_url", extra={"scheme": p.scheme, "host": hostname or ""})
        raise HTTPException(400, "url de capa inválida")

    bytes_read = 0
    chunks: list[bytes] = []
    try:
        async with httpx.AsyncClient(timeout=CAPA_TIMEOUT, headers=_UA, follow_redirects=True) as c:
            async with c.stream("GET", url) as r:
                if r.status_code >= 400:
                    logger.warning("cover_proxy_upstream_status", extra={"host": hostname, "status_code": r.status_code})
                    raise HTTPException(502, "capa indisponível")

                raw_ct = r.headers.get("content-type", "")
                media_type = raw_ct.split(";", 1)[0].strip().lower()
                if media_type not in CAPA_CONTENT_TYPES:
                    logger.warning("cover_proxy_invalid_content_type", extra={"host": hostname, "content_type": media_type or "missing"})
                    raise HTTPException(415, "isso não é uma imagem")

                content_length = r.headers.get("content-length")
                if content_length:
                    try:
                        if int(content_length) > CAPA_MAX_BYTES:
                            logger.warning("cover_proxy_content_length_too_large", extra={"host": hostname, "content_length": int(content_length), "limit": CAPA_MAX_BYTES})
                            raise HTTPException(413, "capa grande demais")
                    except ValueError:
                        logger.info("cover_proxy_invalid_content_length", extra={"host": hostname})

                async for chunk in r.aiter_bytes(CAPA_CHUNK_SIZE):
                    if not chunk:
                        continue
                    bytes_read += len(chunk)
                    if bytes_read > CAPA_MAX_BYTES:
                        logger.warning("cover_proxy_stream_too_large", extra={"host": hostname, "bytes_read": bytes_read, "limit": CAPA_MAX_BYTES})
                        raise HTTPException(413, "capa grande demais")
                    chunks.append(chunk)
    except HTTPException:
        raise
    except (httpx.TimeoutException, httpx.NetworkError, httpx.HTTPError) as e:
        logger.warning("cover_proxy_upstream_error", extra={"host": hostname, "error": e.__class__.__name__})
        raise HTTPException(502, "capa indisponível")

    logger.info("cover_proxy_ok", extra={"host": hostname, "content_type": media_type, "bytes_read": bytes_read})
    return Response(
        content=b"".join(chunks),
        media_type=media_type,
        headers={"Cache-Control": CAPA_CACHE_CONTROL},
    )



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
            d[k] = _clean_text(d.get(k), RELATO_MAX if k == "relato" else 240)
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


GENEROS_CANONICOS = [
    "romance", "conto", "poesia", "teatro", "ensaio", "biografia", "autobiografia",
    "história", "filosofia", "crítica literária", "fantasia", "ficção científica",
    "terror", "policial", "infantil", "juvenil", "crônica", "quadrinhos",
]
_GENEROS_NORM = {_normalizar_busca(g): g for g in GENEROS_CANONICOS}
_GENERO_ALIASES = {
    "ficcao cientifica": "ficção científica", "sci fi": "ficção científica", "science fiction": "ficção científica",
    "critica literaria": "crítica literária", "literary criticism": "crítica literária",
    "historia": "história", "history": "história", "novel": "romance",
    "short stories": "conto", "poetry": "poesia", "drama": "teatro", "plays": "teatro",
    "essays": "ensaio", "biography": "biografia", "autobiography": "autobiografia",
    "fantasy": "fantasia", "horror": "terror", "detective": "policial", "mystery": "policial",
    "crime": "policial", "children": "infantil", "juvenile": "juvenil", "young adult": "juvenil",
    "comics": "quadrinhos", "graphic novels": "quadrinhos", "chronicles": "crônica", "cronica": "crônica",
}

def normalizar_genero(valor: str | None) -> str:
    norm = _normalizar_busca(valor)
    if not norm:
        return ""
    return _GENEROS_NORM.get(norm) or _GENERO_ALIASES.get(norm, "")

def generos_obra(obra: Obra | None) -> list[str]:
    raw = getattr(obra, "generos_json", "") or ""
    try:
        valores = json.loads(raw) if raw else []
    except Exception:
        valores = re.split(r"[,;]", raw)
    out = []
    for valor in valores if isinstance(valores, list) else []:
        genero = normalizar_genero(str(valor))
        if genero and genero not in out:
            out.append(genero)
    return out

def _doc_generos(doc: dict) -> list[str]:
    valores = []
    for campo in ("generos", "tags", "categorias", "categories", "subjects"):
        v = doc.get(campo)
        if isinstance(v, list): valores.extend(v)
        elif isinstance(v, str): valores.extend(re.split(r"[,;/]", v))
    for ed in (doc.get("edicoes") or []) + ([doc.get("edicao_isbn")] if doc.get("edicao_isbn") else []):
        if not isinstance(ed, dict): continue
        v = ed.get("categorias") or ed.get("generos")
        if isinstance(v, list): valores.extend(v)
    out = []
    for valor in valores:
        texto = str(valor)
        genero = normalizar_genero(texto)
        if not genero:
            texto_norm = _normalizar_busca(texto)
            for alias, canonico in _GENERO_ALIASES.items():
                if alias in texto_norm:
                    genero = canonico; break
            if not genero:
                for canonico_norm, canonico in _GENEROS_NORM.items():
                    if canonico_norm in texto_norm:
                        genero = canonico; break
        if genero and genero not in out:
            out.append(genero)
    return out

def _doc_compativel_genero(doc: dict, genero: str) -> bool:
    # Estrito, como o filtro local: doc externo sem estilo catalogado sai.
    # Manter o tolerante aqui reintroduzia resultados idênticos entre estilos.
    generos = _doc_generos(doc)
    if generos:
        doc["generos"] = generos
    doc["_genero_match"] = genero in generos
    return doc["_genero_match"]

# ─── literatura / nacionalidade ───────────────────────────
# Base extensível: cada literatura aponta pra um país e/ou região. O metadado
# na Obra é opcional — obra sem origem catalogada nunca é escondida da busca
# (nacionalidade de autor é ambígua; não inventamos dado).
LITERATURAS_CANONICAS = [
    {"slug": "brasileira",       "label": "brasileira",       "pais": "Brasil",         "regiao": "América Latina"},
    {"slug": "russa",            "label": "russa",            "pais": "Rússia",         "regiao": ""},
    {"slug": "francesa",         "label": "francesa",         "pais": "França",         "regiao": ""},
    {"slug": "argentina",        "label": "argentina",        "pais": "Argentina",      "regiao": "América Latina"},
    {"slug": "japonesa",         "label": "japonesa",         "pais": "Japão",          "regiao": ""},
    {"slug": "inglesa",          "label": "inglesa",          "pais": "Reino Unido",    "regiao": ""},
    {"slug": "norte-americana",  "label": "norte-americana",  "pais": "Estados Unidos", "regiao": ""},
    {"slug": "alema",            "label": "alemã",            "pais": "Alemanha",       "regiao": ""},
    {"slug": "italiana",         "label": "italiana",         "pais": "Itália",         "regiao": ""},
    {"slug": "portuguesa",       "label": "portuguesa",       "pais": "Portugal",       "regiao": ""},
    {"slug": "espanhola",        "label": "espanhola",        "pais": "Espanha",        "regiao": ""},
    {"slug": "latino-americana", "label": "latino-americana", "pais": "",               "regiao": "América Latina"},
]
_LITERATURA_ALIASES = {
    "inglaterra": "inglesa", "reino unido": "inglesa", "uk": "inglesa",
    "estados unidos": "norte-americana", "eua": "norte-americana", "americana": "norte-americana", "estadunidense": "norte-americana",
    "america latina": "latino-americana", "latinoamericana": "latino-americana",
    "alemanha": "alema", "alema": "alema",
}

def normalizar_literatura(valor: str | None) -> dict | None:
    norm = _normalizar_busca(valor).replace("_", "-")
    if not norm:
        return None
    norm = _LITERATURA_ALIASES.get(norm, norm)
    for lit in LITERATURAS_CANONICAS:
        chaves = {_normalizar_busca(lit["slug"]), _normalizar_busca(lit["label"]), _normalizar_busca(lit["pais"])} - {""}
        if norm in chaves or norm.replace("-", " ") in chaves:
            return lit
    return None

def _literatura_paises(lit: dict) -> set[str]:
    if lit.get("pais"):
        return {_normalizar_busca(lit["pais"])}
    return {_normalizar_busca(l["pais"]) for l in LITERATURAS_CANONICAS if l["pais"] and l["regiao"] == lit["regiao"]}


def _formas_texto_sql(valores) -> set[str]:
    """Formas equivalentes de um texto pra casar no banco sem depender de acento.
    Devolve a versão minúscula com acento E a sem acento — o prefiltro SQL é só
    um funil (o julgamento final é do _compat_literatura, insensível a acento),
    então incluir as duas formas evita falso-negativo qualquer que seja o formato
    gravado no catálogo."""
    formas: set[str] = set()
    for valor in valores:
        texto = (valor or "").strip()
        if not texto:
            continue
        formas.add(texto.lower())
        formas.add(_normalizar_busca(texto))
    return {f for f in formas if f}


def _literatura_paises_raw(lit: dict) -> list[str]:
    if lit.get("pais"):
        return [lit["pais"]]
    return [l["pais"] for l in LITERATURAS_CANONICAS if l["pais"] and l["regiao"] == lit.get("regiao")]

def _compat_literatura(lit: dict, pais: str, regiao: str, autor_pais: str = "") -> bool | None:
    """True/False quando a obra tem metadado de origem; None quando não tem
    (obra sem o dado não pode ser julgada — quem decide o que fazer é quem filtra)."""
    pais_n, regiao_n, autor_n = _normalizar_busca(pais), _normalizar_busca(regiao), _normalizar_busca(autor_pais)
    if not (pais_n or regiao_n or autor_n):
        return None
    paises = _literatura_paises(lit)
    # Filtro por país (ex.: argentina) casa só a obra daquele país. A região só
    # é critério quando o filtro é regional (ex.: latino-americana, sem país) —
    # senão "argentina" acabava trazendo todo livro marcado "América Latina".
    regiao_alvo = _normalizar_busca(lit.get("regiao") or "") if not lit.get("pais") else ""
    if pais_n and pais_n in paises:
        return True
    if autor_n and autor_n in paises:
        return True
    if regiao_alvo and regiao_n == regiao_alvo:
        return True
    return False

def _doc_compativel_literatura(doc: dict, lit: dict | None) -> bool:
    """Filtro tolerante: exclui só quem tem metadado incompatível. Doc sem o
    dado (todo resultado externo hoje) continua na resposta — o front avisa."""
    if not lit:
        return True
    compat = _compat_literatura(
        lit,
        doc.get("literatura_pais") or "",
        doc.get("literatura_regiao") or "",
        doc.get("autor_pais") or "",
    )
    if compat is None:
        return True
    doc["_literatura_match"] = compat
    return compat

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


def _buscar_catalogo_local(q: str, s: Session, editora: str = "", genero: str = "", literatura: dict | None = None) -> list[dict]:
    q_norm = _normalizar_busca(q)
    editora_norm = _normalizar_busca(editora)
    isbn = normalizar_isbn(q or "")
    genero = normalizar_genero(genero)
    if not q_norm and not editora_norm and not genero and not literatura:
        return []

    # A origem é sempre um refino tolerante — tanto na busca por texto quanto na
    # navegação só por filtro (ex.: "livros da Argentina"): obra de outro país
    # catalogado fica de fora, mas obra sem metadado de origem continua na
    # vitrine (o catálogo ainda tem poucos países preenchidos, e escondê-la
    # deixava o filtro-só sem nenhum resultado). A origem confirmada ganha bônus
    # de score e sobe no ranking; o front avisa quando mostra obras sem o dado.
    busca_textual = bool(q_norm or isbn)
    candidato_limit = 500
    stmt = select(Obra, Edicao).join(Edicao, Edicao.obra_id == Obra.id)

    filtros = []
    if isbn:
        # Filtro simples no banco antes do refinamento em Python. Não tenta
        # normalizar pontuação do ISBN no SQL para manter compatibilidade SQLite/Postgres.
        filtros.append(func.lower(Edicao.isbn).like(f"%{isbn.lower()}%"))
    elif q_norm:
        like = f"%{q_norm.lower()}%"
        filtros.append(
            func.lower(Obra.titulo).like(like)
            | func.lower(Obra.autor).like(like)
            | func.lower(Edicao.editora).like(like)
            | func.lower(Edicao.tradutor).like(like)
            | func.lower(Edicao.isbn).like(like)
        )
    if editora_norm:
        # Funil no banco; o julgamento final (igualdade normalizada, como a
        # agregação do explorar) é feito em Python. Tenta a grafia recebida e a
        # sem acento pra não depender do formato gravado no catálogo.
        formas_editora = _formas_texto_sql([editora])
        filtros.append(or_(*[func.lower(Edicao.editora).like(f"%{f}%") for f in formas_editora]))
    if literatura:
        # O dict canônico usa "pais"/"regiao" (singular). Filtro por país afunila
        # pelo país (literatura_pais/autor_pais); filtro regional (sem país, ex.:
        # latino-americana) afunila pela região e pelos países dela.
        formas_pais = _formas_texto_sql(_literatura_paises_raw(literatura))
        regiao_raw = literatura.get("regiao") if not literatura.get("pais") else ""
        formas_regiao = _formas_texto_sql([regiao_raw]) if regiao_raw else set()
        lit_filtros = []
        if formas_pais:
            lit_filtros.append(func.lower(Obra.literatura_pais).in_(formas_pais))
            lit_filtros.append(func.lower(Obra.autor_pais).in_(formas_pais))
        if formas_regiao:
            lit_filtros.append(func.lower(Obra.literatura_regiao).in_(formas_regiao))
        if lit_filtros:
            # Obra sem origem catalogada entra no funil tanto na busca por texto
            # quanto na navegação só por filtro — senão o filtro-só voltava vazio.
            sem_origem_catalogada = and_(
                or_(Obra.literatura_pais.is_(None), Obra.literatura_pais == ""),
                or_(Obra.literatura_regiao.is_(None), Obra.literatura_regiao == ""),
                or_(Obra.autor_pais.is_(None), Obra.autor_pais == ""),
            )
            filtros.append(or_(or_(*lit_filtros), sem_origem_catalogada))
    for filtro in filtros:
        stmt = stmt.where(filtro)
    stmt = stmt.order_by(Edicao.id.desc()).limit(candidato_limit)
    rows = s.exec(stmt).all()
    ed_ids = [ed.id for _, ed in rows if ed.id is not None]
    social_por_edicao: dict[int, dict] = {}
    if ed_ids:
        leituras_rows = s.exec(
            select(Leitura.edicao_id, Leitura.status, Leitura.nota, Leitura.publico, Leitura.relato)
            .where(Leitura.edicao_id.in_(ed_ids))
        ).all()
        for ed_id, status, nota, publico, relato in leituras_rows:
            stats = social_por_edicao.setdefault(ed_id, {"leituras": 0, "criticas": 0, "lendo": 0, "notas": []})
            stats["leituras"] += 1
            if publico and (relato or "").strip():
                stats["criticas"] += 1
            if status == "Lendo":
                stats["lendo"] += 1
            if nota is not None:
                stats["notas"].append(float(nota))
    leituras = {ed_id: stats["leituras"] for ed_id, stats in social_por_edicao.items()}

    por_obra: dict[str, dict] = {}
    for obra, ed in rows:
        leituras_count = int(leituras.get(ed.id, 0))
        score, match = _score_local(obra, ed, q_norm, isbn, editora_norm, leituras_count)
        searchable = " ".join([_normalizar_busca(obra.titulo), _normalizar_busca(obra.autor), _normalizar_busca(ed.isbn), _normalizar_busca(ed.editora), _normalizar_busca(ed.tradutor)])
        if q_norm and q_norm not in searchable and not (isbn and normalizar_isbn(ed.isbn or "") == isbn):
            continue
        # Igualdade exata (normalizada) — mesma semântica da agregação do
        # explorar. Substring deixava vazar edição de outra editora cujo campo
        # livre só CONTÉM o nome buscado (ex.: kits/lotes vindos de sync).
        if editora_norm and _normalizar_busca(ed.editora) != editora_norm:
            continue
        genero_compat = None
        if genero:
            # Filtro de estilo é ESTRITO: só entra obra com o estilo confirmado.
            # A versão tolerante (obra sem metadado permanecia) fazia qualquer
            # estilo devolver o catálogo inteiro — buscas por estilos diferentes
            # retornavam resultados idênticos. Vazio honesto (com aviso e CTA no
            # front) é melhor que um filtro que não filtra.
            genero_compat = genero in generos_obra(obra)
            if not genero_compat:
                continue
            score += 40
        lit_compat = None
        if literatura:
            lit_compat = _compat_literatura(
                literatura,
                getattr(obra, "literatura_pais", "") or "",
                getattr(obra, "literatura_regiao", "") or "",
                getattr(obra, "autor_pais", "") or "",
            )
            # obra com origem catalogada incompatível sai sempre. Obra sem
            # metadado permanece (na busca por texto e no filtro-só): o catálogo
            # tem poucos países preenchidos e escondê-la deixava o filtro vazio.
            # A origem confirmada ganha bônus e sobe no ranking; o front avisa.
            # (obra sem nenhum sinal de qualidade ainda cai no piso `score <= 0`.)
            if lit_compat is False:
                continue
            if lit_compat:
                score += 40
        if score <= 0:
            continue
        chave = _chave_canonica_obra_busca(obra)
        bucket = por_obra.setdefault(chave, {"obras": {}, "items": [], "score": 0, "match": {"titulo": False, "autor": False, "editora": False, "isbn": False}, "literatura_match": False, "genero_match": False})
        bucket["obras"][obra.id] = obra
        bucket["items"].append((score, leituras_count, obra, ed, match))
        bucket["score"] = max(bucket["score"], score)
        bucket["literatura_match"] = bucket["literatura_match"] or bool(lit_compat)
        bucket["genero_match"] = bucket["genero_match"] or bool(genero_compat)
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
        social = {"leituras": 0, "criticas": 0, "lendo": 0, "notas": []}
        for ed_id in {item_ed.id for _s, _l, _o, item_ed, _m in items if item_ed.id is not None}:
            stats = social_por_edicao.get(ed_id)
            if not stats:
                continue
            social["leituras"] += stats["leituras"]
            social["criticas"] += stats["criticas"]
            social["lendo"] += stats["lendo"]
            social["notas"].extend(stats["notas"])
        doc = {
            "work_key": obra_principal.ol_work_key, "titulo": obra_principal.titulo, "autor": obra_principal.autor,
            "descricao": getattr(obra_principal, "descricao", "") or "",
            "generos": generos_obra(obra_principal),
            "idioma_original": obra_principal.idioma_original, "ano": obra_principal.ano, "tem_pt": _idioma_portugues(ed.idioma),
            "capa_url": ed.capa_url, "isbn_match": best_match["isbn"], "edicao_isbn": ed_doc, "edicoes": edicoes,
            "edicoes_encontradas": len(edicoes_docs),
            "chave_obra": chave_obra_canonica(obra_principal.titulo, obra_principal.autor),
            "leituras_count": social["leituras"],
            "criticas_publicas": social["criticas"],
            "lendo_agora_count": social["lendo"],
            "nota_media": round(sum(social["notas"]) / len(social["notas"]), 2) if social["notas"] else None,
            "_fonte": "local", "_ranking_score": bucket["score"], "_match": bucket["match"],
        }
        # metadados de origem só entram no payload quando existem de verdade
        for campo in ("autor_pais", "autor_nacionalidade", "literatura_pais", "literatura_regiao"):
            valor = (getattr(obra_principal, campo, "") or "").strip()
            if valor:
                doc[campo] = valor
        if literatura:
            doc["_literatura_match"] = bucket["literatura_match"]
        if genero:
            doc["_genero_match"] = bucket["genero_match"]
        docs.append(doc)
    # Busca por texto entrega o topo (mistura com resultados externos depois).
    # Navegação só por filtro é uma vitrine do catálogo — devolve mais itens.
    limite_local = 30 if not busca_textual else 10
    return sorted(docs, key=lambda d: (d.get("_ranking_score") or 0, d.get("edicao_isbn", {}).get("leituras_count") or 0), reverse=True)[:limite_local]


def _follow_counts(s: Session, usuario_id: int) -> dict:
    return {
        "followers_count": s.exec(select(func.count()).select_from(Follow).where(Follow.following_id == usuario_id)).one(),
        "following_count": s.exec(select(func.count()).select_from(Follow).where(Follow.follower_id == usuario_id)).one(),
    }


def _is_following(s: Session, follower_id: int | None, following_id: int) -> bool:
    if not follower_id or follower_id == following_id:
        return False
    return bool(s.exec(select(Follow).where(Follow.follower_id == follower_id, Follow.following_id == following_id)).first())


def _criar_notificacao(s: Session, usuario_id: int, ator_id: int, tipo: str, leitura_id: int | None = None) -> None:
    if usuario_id == ator_id:
        return
    alvo = s.get(Usuario, usuario_id)
    if not alvo or getattr(alvo, "is_demo", False):
        return
    s.add(Notificacao(usuario_id=usuario_id, ator_id=ator_id, tipo=tipo, leitura_id=leitura_id))
    s.commit()


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


def _comments_count(s: Session, leitura_id: int) -> int:
    return s.exec(select(func.count()).select_from(ReviewComment).where(ReviewComment.leitura_id == leitura_id)).one()


def _review_state(s: Session, leitura_id: int, usuario_id: int | None = None) -> dict:
    liked = saved = reported = False
    if usuario_id:
        liked = bool(s.exec(select(ReviewLike).where(ReviewLike.leitura_id == leitura_id, ReviewLike.usuario_id == usuario_id)).first())
        saved = bool(s.exec(select(SavedReview).where(SavedReview.leitura_id == leitura_id, SavedReview.usuario_id == usuario_id)).first())
        reported = bool(s.exec(select(ReviewReport).where(ReviewReport.leitura_id == leitura_id, ReviewReport.usuario_id == usuario_id)).first())
    return {
        "likes_count": _likes_count(s, leitura_id), "liked_by_me": liked, "saved_by_me": saved, "reported_by_me": reported,
        "comments_count": _comments_count(s, leitura_id),
    }


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
    return bio


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


# ─── foto de perfil enviada pelo usuário ──────────────────
# O disco do Render free é efêmero, então a foto (pequena, já recortada no
# cliente) vive no banco e é servida por /api/avatar/{id} com cache.
_AVATAR_MAX_BYTES = 400_000


class AvatarPayload(BaseModel):
    data: str  # base64 (sem prefixo data:)


def _sniff_imagem(raw: bytes) -> str:
    if raw[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if raw[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if raw[:4] == b"RIFF" and raw[8:12] == b"WEBP":
        return "image/webp"
    return ""


@app.post("/api/eu/avatar")
def subir_avatar(payload: AvatarPayload, request: Request, s: Session = Depends(get_session)):
    u = _require_google_user(request, s, "Entre com Google para mudar sua foto.", 401)
    if getattr(u, "is_demo", False):
        raise HTTPException(403, "Perfis de demonstração não podem ser editados.")
    try:
        raw = base64.b64decode(payload.data or "", validate=True)
    except Exception:
        raise HTTPException(400, "imagem inválida")
    if not raw:
        raise HTTPException(400, "imagem vazia")
    if len(raw) > _AVATAR_MAX_BYTES:
        raise HTTPException(400, "imagem muito grande")
    mime = _sniff_imagem(raw)
    if not mime:
        raise HTTPException(400, "formato não suportado (use JPEG, PNG ou WebP)")
    u.avatar_blob = raw
    u.avatar_mime = mime
    u.avatar_custom = True
    u.avatar_url = f"/api/avatar/{u.id}?v={int(time.time())}"
    s.add(u); s.commit()
    return {"avatar_url": u.avatar_url, "avatar_custom": True}


@app.delete("/api/eu/avatar")
def remover_avatar(request: Request, s: Session = Depends(get_session)):
    u = _require_google_user(request, s, "Entre com Google para mudar sua foto.", 401)
    if getattr(u, "is_demo", False):
        raise HTTPException(403, "Perfis de demonstração não podem ser editados.")
    u.avatar_blob = None
    u.avatar_mime = ""
    u.avatar_custom = False
    u.avatar_url = getattr(u, "avatar_google", "") or ""
    s.add(u); s.commit()
    return {"avatar_url": u.avatar_url, "avatar_custom": False}


@app.get("/api/avatar/{usuario_id}")
def servir_avatar(usuario_id: int, s: Session = Depends(get_session)):
    u = s.get(Usuario, usuario_id)
    blob = getattr(u, "avatar_blob", None) if u else None
    if not u or not blob:
        raise HTTPException(404, "sem foto")
    return Response(content=blob, media_type=u.avatar_mime or "image/jpeg",
                    headers={"Cache-Control": "public, max-age=86400"})


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
        "avatar_url": getattr(u, "avatar_url", "") or "",
        "avatar_custom": bool(getattr(u, "avatar_custom", False)),
        "email": u.email,
        "logado": logado,
        "provedor": "google" if logado else "anonimo",
        "admin": _is_admin(u),
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


def _doc_tem_editora(doc: dict, editora_norm: str) -> bool:
    if not editora_norm:
        return True
    candidatos = [doc.get("editora"), (doc.get("edicao_isbn") or {}).get("editora")]
    candidatos.extend((e or {}).get("editora") for e in (doc.get("edicoes") or []))
    return any(editora_norm in _normalizar_busca(c) for c in candidatos if c)


def _edicoes_todas_doc(doc: dict) -> list[dict]:
    eds = [doc.get("edicao_isbn")] if doc.get("edicao_isbn") else []
    eds.extend(doc.get("edicoes") or [])
    return [e for e in eds if isinstance(e, dict)]


def _doc_tem_capa(doc: dict) -> bool:
    return bool(doc.get("capa_url") or any(e.get("capa_url") for e in _edicoes_todas_doc(doc)))


def _doc_tem_isbn(doc: dict) -> bool:
    return bool(any(e.get("isbn") for e in _edicoes_todas_doc(doc)))


def _doc_em_portugues(doc: dict) -> bool | None:
    """True/False quando há dado de idioma; None quando o doc não traz idioma
    nenhum (filtro só se aplica quando o dado existe)."""
    if doc.get("tem_pt"):
        return True
    idiomas = [doc.get("idioma_original")] + [e.get("idioma") for e in _edicoes_todas_doc(doc)]
    idiomas = [i for i in idiomas if i]
    if not idiomas:
        return None
    return any(_idioma_portugues(i) for i in idiomas)


def _doc_ano_recente(doc: dict) -> int:
    anos = [doc.get("ano")] + [e.get("ano") for e in _edicoes_todas_doc(doc)]
    anos = [int(a) for a in anos if isinstance(a, (int, float)) and a]
    return max(anos) if anos else 0


ORDENACOES_BUSCA = {"popular", "avaliacao", "recentes"}


def _aplicar_filtros_extras(docs: list[dict], *, com_criticas: bool, lendo_agora: bool,
                            com_capa: bool, com_isbn: bool, idioma_pt: bool) -> list[dict]:
    """Filtros sociais/de qualidade. Dados sociais só existem nos docs locais;
    resultados externos passam nesses filtros (aplicar só quando o dado existir)."""
    saida = []
    for doc in docs:
        if com_capa and not _doc_tem_capa(doc):
            continue
        if com_isbn and not _doc_tem_isbn(doc):
            continue
        if idioma_pt and _doc_em_portugues(doc) is False:
            continue
        if com_criticas and "criticas_publicas" in doc and not doc["criticas_publicas"]:
            continue
        if lendo_agora and "lendo_agora_count" in doc and not doc["lendo_agora_count"]:
            continue
        saida.append(doc)
    return saida


def _ordenar_resultados_busca(docs: list[dict], ordenar: str, literatura_ativa: bool,
                              genero_ativo: bool = False) -> list[dict]:
    # sorts estáveis: a ordenação escolhida decide, quality_score desempata
    if ordenar == "popular":
        docs.sort(key=lambda d: (d.get("leituras_count") or 0), reverse=True)
    elif ordenar == "avaliacao":
        docs.sort(key=lambda d: (d.get("nota_media") is not None, d.get("nota_media") or 0), reverse=True)
    elif ordenar == "recentes":
        docs.sort(key=lambda d: _doc_ano_recente(d), reverse=True)
    if genero_ativo:
        # com o filtro estrito todo doc já tem o estilo confirmado; o sort fica
        # como cinto de segurança pra doc que chegue sem a flag (ex.: cache antigo)
        docs.sort(key=lambda d: 0 if d.get("_genero_match") else 1)
    if literatura_ativa:
        # prioriza obras com origem compatível confirmada, sem excluir as demais
        docs.sort(key=lambda d: 0 if d.get("_literatura_match") else 1)
    return docs


@app.get("/api/buscar")
def buscar(q: str = Query(""), editora: str = Query(""), genero: str = Query(""),
           literatura: str = Query(""), ordenar: str = Query(""),
           com_criticas: bool = Query(False), lendo_agora: bool = Query(False),
           com_capa: bool = Query(False), com_isbn: bool = Query(False),
           idioma: str = Query(""), s: Session = Depends(get_session)):
    inicio = datetime.utcnow()
    rss_inicio = _rss_mb()
    q = (q or "").strip()
    q_valido = len(q) >= 2
    logger.info("search_started", extra={"query_len": len(q), "rss_mb": rss_inicio})
    editora_norm = _normalizar_busca(editora)
    genero_canonico = normalizar_genero(genero)
    lit = normalizar_literatura(literatura)
    ordenar = ordenar if ordenar in ORDENACOES_BUSCA else ""
    idioma_pt = _idioma_portugues(idioma)
    filtros_ativos = bool(editora_norm or genero_canonico or lit or com_criticas or lendo_agora or com_capa or com_isbn or idioma_pt)
    if not q_valido and not filtros_ativos:
        return []
    termo_busca = q if q_valido else ""
    locais = _buscar_catalogo_local(termo_busca, s, editora=editora, genero=genero_canonico, literatura=lit)
    def _resposta_final(externos: list[dict]) -> list[dict]:
        externos_filtrados = [d for d in (externos or []) if _doc_tem_editora(d, editora_norm) and (not genero_canonico or _doc_compativel_genero(d, genero_canonico)) and _doc_compativel_literatura(d, lit)]
        docs = consolidar_resultados_busca_final(termo_busca, locais + externos_filtrados)
        docs = _aplicar_filtros_extras(docs, com_criticas=com_criticas, lendo_agora=lendo_agora,
                                       com_capa=com_capa, com_isbn=com_isbn, idioma_pt=bool(idioma_pt))
        return _ordenar_resultados_busca(docs, ordenar, literatura_ativa=bool(lit),
                                         genero_ativo=bool(genero_canonico))[:30]

    if not q_valido:
        resposta = _resposta_final([])
        logger.info("search_finished", extra={"query_len": len(q), "locais_count": len(locais), "externos_count": 0, "elapsed_ms": int((datetime.utcnow() - inicio).total_seconds() * 1000), "rss_mb": _rss_mb()})
        return resposta

    isbn = normalizar_isbn(q)
    if isbn:
        try:
            achado = _edicao_por_isbn(isbn)
        except Exception:
            logger.warning("external_search_failed", extra={"provider": "isbn"}, exc_info=True)
            achado = None
        externos = [achado] if achado else []
        logger.info("search_finished", extra={"query_len": len(q), "locais_count": len(locais), "externos_count": len(externos), "elapsed_ms": int((datetime.utcnow() - inicio).total_seconds() * 1000), "rss_mb": _rss_mb()})
        return _resposta_final(externos)

    cache = _cache_get(q, s)
    if cache:
        resposta = _resposta_final(cache)
        logger.info("search_cache_hit", extra={"query_len": len(q), "locais_count": len(locais), "externos_count": len(cache), "elapsed_ms": int((datetime.utcnow() - inicio).total_seconds() * 1000), "rss_mb": _rss_mb()})
        return resposta

    try:
        logger.info("external_search_started", extra={"provider": "google_books", "query_len": len(q)})
        docs = buscar_titulo_v2(q)
        if docs:
            docs = consolidar_resultados_busca_final(q, docs)
            _cache_set(q, docs, s)
            resposta = _resposta_final(docs)
            logger.info("search_finished", extra={"query_len": len(q), "locais_count": len(locais), "externos_count": len(docs), "elapsed_ms": int((datetime.utcnow() - inicio).total_seconds() * 1000), "rss_mb": _rss_mb()})
            return resposta
        logger.info("external_search_started", extra={"provider": "open_library", "query_len": len(q)})
        docs = ol_buscar(q)
        docs = consolidar_resultados_busca_final(q, docs)
        _cache_set(q, docs, s)
        resposta = _resposta_final(docs)
        logger.info("search_finished", extra={"query_len": len(q), "locais_count": len(locais), "externos_count": len(docs), "elapsed_ms": int((datetime.utcnow() - inicio).total_seconds() * 1000), "rss_mb": _rss_mb()})
        return resposta
    except Exception:
        logger.warning("external_search_failed", extra={"provider": "google_books", "query_len": len(q)}, exc_info=True)
        try:
            logger.info("external_search_started", extra={"provider": "open_library", "query_len": len(q)})
            docs = ol_buscar(q)
            docs = consolidar_resultados_busca_final(q, docs)
            _cache_set(q, docs, s)
            resposta = _resposta_final(docs)
            logger.info("search_finished", extra={"query_len": len(q), "locais_count": len(locais), "externos_count": len(docs), "elapsed_ms": int((datetime.utcnow() - inicio).total_seconds() * 1000), "rss_mb": _rss_mb()})
            return resposta
        except Exception:
            logger.error("external_search_failed", extra={"provider": "open_library", "query_len": len(q)}, exc_info=True)
            raise HTTPException(502, "busca indisponível")


@app.get("/api/editoras")
def api_listar_editoras(s: Session = Depends(get_session)):
    return listar_editoras(s)


@app.get("/api/literaturas")
def api_listar_literaturas():
    """Lista canônica de literaturas/origens disponíveis pro filtro da busca."""
    return LITERATURAS_CANONICAS


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
async def capa(url: str = Query(..., min_length=8)):
    try:
        return await proxy_capa(url)
    except HTTPException:
        raise
    except Exception as e:
        logger.warning("cover_proxy_unexpected_error", extra={"error": e.__class__.__name__})
        raise HTTPException(502, "capa indisponível")


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
    # quem eu sigo que leu/está lendo esta obra — um set só, pra não virar
    # uma query de follow por leitura
    following_ids = set(s.exec(select(Follow.following_id).where(Follow.follower_id == usuario_id)).all()) if usuario_id else set()
    seguidos_leram: dict[int, dict] = {}
    for l, ed, _o, u in rows:
        bucket = por_edicao.setdefault(ed.id, {"leituras": 0, "notas": [], "editora": ed.editora, "tradutor": ed.tradutor})
        bucket["leituras"] += 1
        if l.nota is not None:
            bucket["notas"].append(l.nota)
        if usuario_id and l.usuario_id == usuario_id and minha is None:
            minha = {"leitura_id": l.id, "edicao_id": ed.id, "status": l.status}
        if u.id in following_ids and u.id not in seguidos_leram and (l.status or "") in {"Lido", "Lendo"}:
            seguidos_leram[u.id] = {"handle": u.handle, "nome": u.nome, "avatar_url": getattr(u, "avatar_url", "") or "", "status": l.status}
        relato = (l.relato or "").strip()
        if l.publico and relato:
            criticas.append({
                "leitura_id": l.id, "nota": l.nota, "relato": relato, "data": l.data,
                "status": l.status, "spoiler": bool(l.spoiler),
                "criado_em": l.criado_em.isoformat(), "usuario": u.handle,
                "nome": u.nome,
                "is_following": _is_following(s, usuario_id, u.id),
                "is_me": bool(usuario_id and usuario_id == u.id),
                "is_demo": bool(getattr(u, "is_demo", False)),
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
                "paginas": ed.paginas,
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
        "seguidos_leram": list(seguidos_leram.values())[:8],
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
        _criar_notificacao(s, l.usuario_id, u.id, "like", leitura_id)
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


class ReviewCommentPayload(BaseModel):
    texto: str


def _comment_payload(c: ReviewComment, autor: Usuario, atual: Usuario | None) -> dict:
    return {
        "id": c.id, "texto": c.texto, "criado_em": c.criado_em.isoformat(),
        "usuario": {"handle": autor.handle, "nome": autor.nome, "avatar_url": getattr(autor, "avatar_url", "") or "", "is_demo": bool(getattr(autor, "is_demo", False))},
        "is_me": bool(atual and atual.id == c.usuario_id),
    }


@app.get("/api/reviews/{leitura_id}/comments")
def listar_comentarios(leitura_id: int, request: Request, s: Session = Depends(get_session)):
    _review_or_404(leitura_id, s)
    atual = usuario_sessao(request, s)
    rows = s.exec(
        select(ReviewComment, Usuario)
        .join(Usuario, ReviewComment.usuario_id == Usuario.id)
        .where(ReviewComment.leitura_id == leitura_id)
        .order_by(ReviewComment.criado_em.asc())
    ).all()
    return [_comment_payload(c, autor, atual) for c, autor in rows]


@app.post("/api/reviews/{leitura_id}/comments")
def criar_comentario(leitura_id: int, payload: ReviewCommentPayload, request: Request, s: Session = Depends(get_session)):
    u = _require_google_user(request, s, "Entre com Google para comentar.", 401)
    l = _review_or_404(leitura_id, s)
    texto = _clean_text(payload.texto, 500)
    if not texto:
        raise HTTPException(422, "escreva um comentário.")
    c = ReviewComment(leitura_id=leitura_id, usuario_id=u.id, texto=texto)
    s.add(c); s.commit(); s.refresh(c)
    _criar_notificacao(s, l.usuario_id, u.id, "comment", leitura_id)
    return _comment_payload(c, u, u)


@app.delete("/api/comments/{comment_id}")
def remover_comentario(comment_id: int, request: Request, s: Session = Depends(get_session)):
    u = _require_google_user(request, s, "Entre com Google para comentar.", 401)
    c = s.get(ReviewComment, comment_id)
    if not c or c.usuario_id != u.id:
        raise HTTPException(404, "comentário não encontrado")
    s.delete(c); s.commit()
    return {"ok": True}


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
    # total de páginas da edição, respondido uma única vez quando o catálogo
    # não tem o dado — vai pra Edicao, não pra entrada do diário
    paginas_total: Optional[int] = None
    # por onde a entrada foi criada ("diario" ou "li_mais"); só vale no create —
    # editar uma entrada não muda a origem dela
    origem: Optional[str] = None


def _backfill_paginas_edicao(edicao_id: int, paginas_total: Optional[int], s: Session) -> None:
    if not paginas_total or paginas_total <= 0 or paginas_total > 20000:
        return
    edicao = s.get(Edicao, edicao_id)
    if not edicao or edicao.paginas:
        return
    try:
        edicao.paginas = int(paginas_total)
        s.add(edicao); s.commit()
    except SQLAlchemyError:
        s.rollback()


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

    # numa entrada tipo "capitulo", a página é opcional — quando o leitor sabe
    # a página em que aquele capítulo começou, ela alimenta o mapa
    # capítulo→página da edição (ver _registrar_capitulo_sumario) sem virar a
    # "posição oficial" da entrada, que continua sendo o capítulo.
    pagina_permitida = tipo == "pagina" or (tipo == "capitulo" and capitulo_valido)
    return {
        "progresso_tipo": tipo,
        "pagina": pagina if pagina_permitida and pagina_valida else None,
        "porcentagem": porcentagem if tipo == "porcentagem" and porcentagem_valida else None,
        "capitulo": capitulo if tipo in {"capitulo", "livre"} and capitulo_valido else "",
        "capitulo_ordem": capitulo_ordem if tipo == "capitulo" and capitulo_valido and capitulo_ordem_valida else None,
        "nota": nota,
        "publico": bool(data.get("publico", False)),
        "spoiler": bool(data.get("spoiler", False))
    }

def _diario_payload(entry: ReadingJournalEntry, l: Leitura | None = None, ed: Edicao | None = None, o: Obra | None = None, pagina_estimada: int | None = None) -> dict:
    return {
        "id": entry.id, "leitura_id": entry.leitura_id, "progresso_tipo": entry.progresso_tipo,
        "pagina": entry.pagina, "porcentagem": entry.porcentagem, "capitulo": entry.capitulo,
        "capitulo_ordem": entry.capitulo_ordem, "pagina_estimada": pagina_estimada,
        "origem": getattr(entry, "origem", "diario") or "diario", "paginas_delta": getattr(entry, "paginas_delta", None),
        "nota": entry.nota, "publico": bool(entry.publico), "spoiler": bool(entry.spoiler),
        "created_at": entry.created_at.isoformat(), "updated_at": entry.updated_at.isoformat(),
        **({"status": l.status, "titulo": o.titulo, "autor": o.autor, "capa_url": ed.capa_url} if l and ed and o else {}),
    }


def _registrar_capitulo_sumario(edicao_id: int, ordem: int | None, titulo: str, s: Session, fonte: str = "comunidade", pagina: int | None = None) -> None:
    """Registra uma posição no sumário da edição (primeira vez escreve, não sobrescreve
    contribuição já existente na mesma posição — sem moderação ainda, então evita
    disputa de edição; a leitura de /capitulos já cai pro fallback por popularidade
    onde o sumário estruturado estiver incompleto).

    Quando o leitor também informou a página em que o capítulo começa, essa
    posição alimenta o mapa capítulo→página (`pagina_inicio`) usado pra
    sincronizar os modos de progresso — completa o dado se estiver faltando,
    mas não sobrescreve uma posição já conhecida."""
    if not ordem or not titulo:
        return
    ja_existe = s.exec(
        select(EdicaoCapitulo).where(EdicaoCapitulo.edicao_id == edicao_id, EdicaoCapitulo.ordem == ordem)
    ).first()
    if ja_existe:
        if pagina and not ja_existe.pagina_inicio:
            try:
                ja_existe.pagina_inicio = pagina
                s.add(ja_existe); s.commit()
            except SQLAlchemyError:
                s.rollback()
        return
    try:
        s.add(EdicaoCapitulo(edicao_id=edicao_id, ordem=ordem, titulo=titulo, fonte=fonte, pagina_inicio=pagina))
        s.commit()
    except SQLAlchemyError:
        s.rollback()


def _mapa_pagina_capitulos(edicao_id: int, s: Session) -> dict[int, int]:
    linhas = s.exec(
        select(EdicaoCapitulo.ordem, EdicaoCapitulo.pagina_inicio)
        .where(EdicaoCapitulo.edicao_id == edicao_id, EdicaoCapitulo.pagina_inicio.is_not(None))
    ).all()
    return {ordem: pagina for ordem, pagina in linhas}


def _interpolar_pagina(mapa: dict[int, int], ordem: int) -> int | None:
    """Estima a página de um capítulo a partir de pontos conhecidos (comunidade).

    Só interpola dentro do intervalo já observado (entre o ponto conhecido
    anterior e o seguinte) — fora dele seria extrapolação, que erra fácil
    com poucos dados, então prefere não sugerir nada a sugerir errado."""
    if ordem in mapa:
        return mapa[ordem]
    pontos = sorted(mapa.items())
    antes = [p for p in pontos if p[0] < ordem]
    depois = [p for p in pontos if p[0] > ordem]
    if not antes or not depois:
        return None
    o1, p1 = antes[-1]
    o2, p2 = depois[0]
    if o2 == o1:
        return None
    return round(p1 + (p2 - p1) * (ordem - o1) / (o2 - o1))


def _pagina_estimada_da_entrada(entry: ReadingJournalEntry, mapa: dict[int, int]) -> int | None:
    if entry.progresso_tipo != "capitulo" or entry.pagina is not None or not entry.capitulo_ordem:
        return None
    return _interpolar_pagina(mapa, entry.capitulo_ordem)


ORIGENS_DIARIO = {"diario", "li_mais"}


def _pagina_efetiva_sessao(entry: ReadingJournalEntry, mapa: dict[int, int], paginas_total: int | None) -> int | None:
    """Melhor estimativa da página em que uma entrada deixou a leitura, na mesma
    ordem de preferência que o front usa: página explícita, capítulo→página do
    sumário, porcentagem sobre o total conhecido."""
    if entry.pagina:
        return entry.pagina
    estimada = _pagina_estimada_da_entrada(entry, mapa)
    if estimada:
        return estimada
    if entry.porcentagem is not None and paginas_total:
        return round(paginas_total * entry.porcentagem / 100)
    return None


def _delta_sessao(nova: ReadingJournalEntry, anterior: ReadingJournalEntry | None, mapa: dict[int, int], paginas_total: int | None) -> int | None:
    if anterior is None:
        return None
    pagina_nova = _pagina_efetiva_sessao(nova, mapa, paginas_total)
    pagina_anterior = _pagina_efetiva_sessao(anterior, mapa, paginas_total)
    if pagina_nova is None or pagina_anterior is None:
        return None
    return pagina_nova - pagina_anterior


@app.get("/api/leitura/{leitura_id}/diario")
def listar_diario_leitura(leitura_id: int, request: Request, s: Session = Depends(get_session)):
    u = usuario_sessao(request, s)
    leitura = _leitura_do_usuario(leitura_id, u.id, s)
    entries = s.exec(select(ReadingJournalEntry).where(ReadingJournalEntry.leitura_id == leitura_id, ReadingJournalEntry.usuario_id == u.id).order_by(ReadingJournalEntry.created_at.desc())).all()
    mapa = _mapa_pagina_capitulos(leitura.edicao_id, s)
    return [_diario_payload(e, pagina_estimada=_pagina_estimada_da_entrada(e, mapa)) for e in entries]


@app.get("/api/edicoes/{edicao_id}/paginas")
def paginas_edicao(edicao_id: int, s: Session = Depends(get_session)):
    """Total de páginas da edição pro progresso 'p. X de Y'.

    Se a edição ainda não tem o dado, tenta descobrir pelo ISBN (Open
    Library → Google Books) e grava — a partir daí ninguém mais espera
    essa busca. Sem ISBN ou sem resultado, devolve null e o front faz a
    pergunta única pro leitor (que também alimenta a edição)."""
    edicao = s.get(Edicao, edicao_id)
    if not edicao:
        raise HTTPException(404, "edição não encontrada")
    if edicao.paginas:
        return {"paginas": edicao.paginas, "fonte": "edicao"}
    if edicao.isbn:
        n = paginas_por_isbn(edicao.isbn)
        if n:
            try:
                edicao.paginas = n
                s.add(edicao); s.commit()
            except SQLAlchemyError:
                s.rollback()
            return {"paginas": n, "fonte": "catalogo"}
    return {"paginas": None, "fonte": None}


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


class ColarSumarioPayload(BaseModel):
    texto: str


_RE_NUMERACAO_SUMARIO = re.compile(r"^\s*(?:cap[íi]tulo\s+)?(?:[ivxlcdm]+|\d+)[\s.:\)\-–—]*", re.IGNORECASE)
_RE_PAGINA_FINAL_SUMARIO = re.compile(r"[\s.…\-–—]{1,}(\d{1,5})\s*$")


def _parsear_sumario_colado(texto: str) -> list[dict]:
    """Um capítulo por linha. Tenta reconhecer um número de página no fim da
    linha (comum em sumários digitados com pontilhado, ex. "Capítulo 3 .... 45")
    e remove numeração de abertura (ex. "3.", "III -") do título. A ordem final
    é sempre a posição da linha no texto colado, não o número que a linha
    eventualmente cita — evita furos se o leitor pular ou repetir um número."""
    resultado = []
    ordem = 0
    for linha in texto.splitlines():
        linha = linha.strip()
        if not linha:
            continue
        pagina = None
        m = _RE_PAGINA_FINAL_SUMARIO.search(linha)
        resto = linha
        if m:
            candidato = resto[: m.start()].strip()
            if candidato:
                pagina = int(m.group(1))
                resto = candidato
        titulo = _RE_NUMERACAO_SUMARIO.sub("", resto).strip() or resto
        titulo = _clean_text(titulo, 120)
        if not titulo:
            continue
        ordem += 1
        resultado.append({"ordem": ordem, "titulo": titulo, "pagina": pagina})
    return resultado


@app.post("/api/edicoes/{edicao_id}/capitulos/colar")
def colar_sumario_edicao(edicao_id: int, payload: ColarSumarioPayload, request: Request, s: Session = Depends(get_session)):
    usuario_sessao(request, s)
    edicao = s.get(Edicao, edicao_id)
    if not edicao:
        raise HTTPException(404, "edição não encontrada")
    itens = _parsear_sumario_colado((payload.texto or "")[:20000])[:300]
    if not itens:
        raise HTTPException(422, "não consegui reconhecer capítulos nesse texto")
    for item in itens:
        existente = s.exec(
            select(EdicaoCapitulo).where(EdicaoCapitulo.edicao_id == edicao_id, EdicaoCapitulo.ordem == item["ordem"])
        ).first()
        try:
            if existente:
                existente.titulo = item["titulo"]
                if item["pagina"] and not existente.pagina_inicio:
                    existente.pagina_inicio = item["pagina"]
                s.add(existente)
            else:
                s.add(EdicaoCapitulo(edicao_id=edicao_id, ordem=item["ordem"], titulo=item["titulo"], fonte="comunidade", pagina_inicio=item["pagina"]))
            s.commit()
        except SQLAlchemyError:
            s.rollback()
    estruturado = s.exec(
        select(EdicaoCapitulo).where(EdicaoCapitulo.edicao_id == edicao_id).order_by(EdicaoCapitulo.ordem)
    ).all()
    return [{"titulo": c.titulo, "ordem": c.ordem, "fonte": c.fonte} for c in estruturado]


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
    mapas_por_edicao: dict[int, dict[int, int]] = {}
    resultado = []
    for e, l, ed, o in rows:
        if e.progresso_tipo == "capitulo" and e.pagina is None and e.capitulo_ordem:
            if ed.id not in mapas_por_edicao:
                mapas_por_edicao[ed.id] = _mapa_pagina_capitulos(ed.id, s)
            estimada = _interpolar_pagina(mapas_por_edicao[ed.id], e.capitulo_ordem)
        else:
            estimada = None
        resultado.append(_diario_payload(e, l, ed, o, pagina_estimada=estimada))
    return resultado


@app.post("/api/leitura/{leitura_id}/diario")
def criar_diario(leitura_id: int, payload: DiarioPayload, request: Request, s: Session = Depends(get_session)):
    u = usuario_sessao(request, s)
    leitura = _leitura_do_usuario(leitura_id, u.id, s)
    data = _validar_diario(payload)
    origem = (payload.origem or "diario").strip().lower()
    entry = ReadingJournalEntry(
        leitura_id=leitura_id, usuario_id=u.id,
        origem=origem if origem in ORIGENS_DIARIO else "diario",
        **data,
    )
    # delta de páginas da sessão em relação à entrada anterior — dado aditivo:
    # se não dá pra estimar (progresso livre, sem total de páginas), fica nulo
    anterior = s.exec(
        select(ReadingJournalEntry)
        .where(ReadingJournalEntry.leitura_id == leitura_id)
        .order_by(ReadingJournalEntry.created_at.desc())
    ).first()
    ed = s.get(Edicao, leitura.edicao_id)
    paginas_total = payload.paginas_total or (ed.paginas if ed else None)
    mapa = _mapa_pagina_capitulos(leitura.edicao_id, s)
    entry.paginas_delta = _delta_sessao(entry, anterior, mapa, paginas_total)
    try:
        s.add(entry); s.commit(); s.refresh(entry)
    except SQLAlchemyError:
        s.rollback()
        logger.exception("diary_create_failed", extra={"leitura_id": leitura_id, "usuario_id": u.id})
        raise HTTPException(500, "não foi possível salvar a entrada do diário")
    _registrar_capitulo_sumario(leitura.edicao_id, data.get("capitulo_ordem"), data.get("capitulo", ""), s, pagina=data.get("pagina"))
    _backfill_paginas_edicao(leitura.edicao_id, payload.paginas_total, s)
    return _diario_payload(entry)


@app.get("/api/leitura/{leitura_id}/progresso")
def resumo_progresso(leitura_id: int, request: Request, s: Session = Depends(get_session)):
    """Resumo de progresso de uma leitura (Lombada 2.0, atrás de flag).

    Com a flag desligada devolve 404 e o app segue exatamente como antes."""
    if not feature_enabled("progress_sessions"):
        raise HTTPException(404, "recurso indisponível")
    u = usuario_sessao(request, s)
    leitura = _leitura_do_usuario(leitura_id, u.id, s)
    ed = s.get(Edicao, leitura.edicao_id)
    paginas_total = ed.paginas if ed else None
    mapa = _mapa_pagina_capitulos(leitura.edicao_id, s)
    entradas = s.exec(
        select(ReadingJournalEntry)
        .where(ReadingJournalEntry.leitura_id == leitura_id)
        .order_by(ReadingJournalEntry.created_at.desc())
    ).all()
    pagina_atual = None
    for e in entradas:
        pagina_atual = _pagina_efetiva_sessao(e, mapa, paginas_total)
        if pagina_atual is not None:
            break
    porcentagem = None
    for e in entradas:
        if e.porcentagem is not None:
            porcentagem = e.porcentagem
            break
    if porcentagem is None and pagina_atual and paginas_total:
        porcentagem = max(0, min(100, round(pagina_atual / paginas_total * 100)))
    delta_ultima = _delta_sessao(entradas[0], entradas[1], mapa, paginas_total) if len(entradas) >= 2 else None
    corte_7d = datetime.utcnow() - timedelta(days=7)
    paginas_7d = sum(
        e.paginas_delta for e in entradas
        if e.paginas_delta and e.paginas_delta > 0 and e.created_at >= corte_7d
    ) or None
    paginas_restantes = max(0, paginas_total - pagina_atual) if paginas_total and pagina_atual else None
    previsao_dias = None
    if paginas_restantes and paginas_7d:
        previsao_dias = max(1, ceil(paginas_restantes / (paginas_7d / 7)))
    return {
        "leitura_id": leitura_id,
        "paginas_total": paginas_total,
        "pagina_atual": pagina_atual,
        "porcentagem": porcentagem,
        "paginas_restantes": paginas_restantes,
        "sessoes": len(entradas),
        "delta_ultima": delta_ultima,
        "paginas_7d": paginas_7d,
        "previsao_dias": previsao_dias,
        "ultima_sessao_em": entradas[0].created_at.isoformat() if entradas else None,
    }


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
        _registrar_capitulo_sumario(leitura.edicao_id, data.get("capitulo_ordem"), data.get("capitulo", ""), s, pagina=data.get("pagina"))
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
    paginas:         Optional[int] = None
    status:          str           = "Lido"
    nota:            Optional[float] = None
    relato:          str           = ""
    publico:         bool          = False
    spoiler:         bool          = False
    data:            str           = ""
    tenho_edicao:    bool          = False
    quero_edicao:    bool          = False


STATUS_LEITURA = {"Lido", "Lendo", "Quero ler"}
# Teto do relato/crítica — precisa acompanhar o maxlength dos textareas no app.js.
RELATO_MAX = 2000
# Status personalizados por usuário: limites de quantidade e de nome.
STATUS_CUSTOM_MAX = 12
STATUS_NOME_MAX = 30


def _status_customizados(s: Session, usuario_id) -> list[UserReadingStatus]:
    if not usuario_id:
        return []
    return list(s.exec(
        select(UserReadingStatus)
        .where(UserReadingStatus.usuario_id == usuario_id)
        .order_by(UserReadingStatus.criado_em)
    ).all())


def _status_validos(s: Session, usuario_id) -> set[str]:
    return STATUS_LEITURA | {st.nome for st in _status_customizados(s, usuario_id)}


def _validar_entrada_leitura(e, exigir_autor: bool = True, status_validos: set[str] | None = None):
    if not e.titulo.strip():
        raise HTTPException(422, "título é obrigatório")
    # Livros vindos do catálogo podem estar sem autor (ex.: Editora 34, cujo scraper
    # ainda não extrai autor) — não dá pra travar o registro de leitura por causa
    # disso. O cadastro manual continua exigindo autor (pelo próprio formulário).
    if exigir_autor and not e.autor.strip():
        raise HTTPException(422, "título e autor são obrigatórios")
    if e.status not in (status_validos or STATUS_LEITURA):
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
    _validar_entrada_leitura(e, exigir_autor=False, status_validos=_status_validos(s, usuario_id))
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
    paginas = e.paginas if e.paginas and e.paginas > 0 else None
    edicao = _buscar_edicao_existente(e, obra, s)
    if not edicao:
        edicao = Edicao(obra_id=obra.id, ol_edition_key=e.ol_edition_key,
                        editora=e.editora.strip(), tradutor=e.tradutor.strip(), isbn=_isbn_norm(e.isbn),
                        idioma=e.idioma.strip(), ano=e.ano_edicao, capa_url=e.capa_url.strip(),
                        paginas=paginas)
        s.add(edicao); s.commit(); s.refresh(edicao)
    elif paginas and not edicao.paginas:
        edicao.paginas = paginas
        s.add(edicao); s.commit()
    leitura_existente, edicao_existente = _buscar_leitura_duplicada(usuario_id, e, obra, edicao, s)
    if leitura_existente:
        raise HTTPException(409, {"duplicado": True, "leitura_id": leitura_existente.id, "edicao_id": edicao_existente.id})
    leitura = Leitura(edicao_id=edicao.id, usuario_id=usuario_id, status=e.status,
                      nota=e.nota, relato=e.relato.strip()[:RELATO_MAX], publico=bool(e.publico),
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
    _validar_entrada_leitura(e, status_validos=_status_validos(s, u.id))
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
        "ano": ed.ano, "ano_obra": o.ano, "isbn": ed.isbn, "capa_url": ed.capa_url, "paginas": ed.paginas,
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
    status_ok = _status_validos(s, u.id)
    for campo, valor in patch.model_dump(exclude_unset=True).items():
        if campo == "status" and valor not in status_ok:
            raise HTTPException(422, "status inválido")
        if campo in {"relato", "data"} and valor is not None:
            valor = valor.strip()
            if campo == "relato":
                valor = valor[:RELATO_MAX]
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


# ─── status de leitura personalizados ─────────────────────
class NovoStatusLeitura(BaseModel):
    nome: str = ""


@app.get("/api/eu/status")
def listar_status_leitura(request: Request, s: Session = Depends(get_session)):
    u = usuario_sessao(request, s)
    return {"padrao": ["Lido", "Lendo", "Quero ler"],
            "custom": [{"id": st.id, "nome": st.nome} for st in _status_customizados(s, u.id)]}


@app.post("/api/eu/status")
def criar_status_leitura(body: NovoStatusLeitura, request: Request, s: Session = Depends(get_session)):
    u = usuario_sessao(request, s)
    nome = " ".join((body.nome or "").split())[:STATUS_NOME_MAX].strip()
    if not nome:
        raise HTTPException(422, "nome do status é obrigatório")
    existentes = _status_customizados(s, u.id)
    if len(existentes) >= STATUS_CUSTOM_MAX:
        raise HTTPException(422, "limite de status personalizados atingido")
    # "Todos" é palavra reservada do filtro da estante.
    reservados = {x.casefold() for x in STATUS_LEITURA} | {st.nome.casefold() for st in existentes} | {"todos"}
    if nome.casefold() in reservados:
        raise HTTPException(409, "esse status já existe")
    st = UserReadingStatus(usuario_id=u.id, nome=nome)
    s.add(st); s.commit(); s.refresh(st)
    return {"id": st.id, "nome": st.nome}


@app.delete("/api/eu/status/{status_id}")
def remover_status_leitura(status_id: int, request: Request, s: Session = Depends(get_session)):
    u = usuario_sessao(request, s)
    st = s.get(UserReadingStatus, status_id)
    if not st or st.usuario_id != u.id:
        raise HTTPException(404, "status não encontrado")
    em_uso = s.exec(
        select(func.count()).select_from(Leitura)
        .where(Leitura.usuario_id == u.id, Leitura.status == st.nome)
    ).one()
    if em_uso:
        raise HTTPException(409, {"em_uso": int(em_uso), "detail": "status em uso por leituras da estante"})
    s.delete(st); s.commit()
    return {"ok": True}


# ─── área de escritores: textos livres ────────────────────
TEXTO_TITULO_MAX = 160
TEXTO_CONTEUDO_MAX = 20000


class EntradaTexto(BaseModel):
    titulo:   str           = ""
    conteudo: str           = ""
    work_key: Optional[str] = None
    publico:  bool          = True


class PatchTexto(BaseModel):
    titulo:   Optional[str]  = None
    conteudo: Optional[str]  = None
    work_key: Optional[str]  = None
    publico:  Optional[bool] = None


def _obra_do_texto(s: Session, work_key) -> Obra | None:
    if not (work_key or "").strip():
        return None
    obra = s.exec(select(Obra).where(Obra.ol_work_key == work_key.strip())).first()
    if not obra:
        raise HTTPException(422, "obra não encontrada")
    return obra


def _texto_payload(s: Session, tx: TextoUsuario, autor: Usuario | None = None, trecho: bool = False) -> dict:
    obra = s.get(Obra, tx.obra_id) if tx.obra_id else None
    d = {
        "texto_id": tx.id, "titulo": tx.titulo,
        "conteudo": _trecho_relato(tx.conteudo, 280) if trecho else tx.conteudo,
        "trecho": bool(trecho), "publico": bool(tx.publico),
        "criado_em": tx.criado_em.isoformat(),
        "obra": ({"titulo": obra.titulo, "autor": obra.autor, "work_key": obra.ol_work_key} if obra else None),
    }
    if autor is not None:
        d["usuario"] = {"handle": autor.handle, "nome": autor.nome,
                        "avatar_url": getattr(autor, "avatar_url", "") or "",
                        "is_demo": bool(getattr(autor, "is_demo", False))}
    return d


def _validar_corpo_texto(titulo, conteudo) -> tuple[str, str]:
    titulo = " ".join((titulo or "").split())[:TEXTO_TITULO_MAX].strip()
    conteudo = (conteudo or "").strip()[:TEXTO_CONTEUDO_MAX]
    if not titulo or not conteudo:
        raise HTTPException(422, "título e conteúdo são obrigatórios")
    return titulo, conteudo


@app.get("/api/eu/textos")
def meus_textos(request: Request, s: Session = Depends(get_session)):
    u = usuario_sessao(request, s)
    rows = s.exec(
        select(TextoUsuario).where(TextoUsuario.usuario_id == u.id)
        .order_by(TextoUsuario.criado_em.desc())
    ).all()
    return [_texto_payload(s, tx) for tx in rows]


@app.post("/api/eu/textos")
def criar_texto(body: EntradaTexto, request: Request, s: Session = Depends(get_session)):
    u = usuario_sessao(request, s)
    titulo, conteudo = _validar_corpo_texto(body.titulo, body.conteudo)
    obra = _obra_do_texto(s, body.work_key)
    tx = TextoUsuario(usuario_id=u.id, obra_id=obra.id if obra else None,
                      titulo=titulo, conteudo=conteudo, publico=bool(body.publico))
    s.add(tx); s.commit(); s.refresh(tx)
    return _texto_payload(s, tx)


@app.patch("/api/eu/textos/{texto_id}")
def editar_texto(texto_id: int, patch: PatchTexto, request: Request, s: Session = Depends(get_session)):
    u = usuario_sessao(request, s)
    tx = s.get(TextoUsuario, texto_id)
    if not tx or tx.usuario_id != u.id:
        raise HTTPException(404, "texto não encontrado")
    dados = patch.model_dump(exclude_unset=True)
    if "titulo" in dados or "conteudo" in dados:
        titulo, conteudo = _validar_corpo_texto(
            dados.get("titulo", tx.titulo), dados.get("conteudo", tx.conteudo))
        tx.titulo, tx.conteudo = titulo, conteudo
    if "work_key" in dados:
        obra = _obra_do_texto(s, dados.get("work_key"))
        tx.obra_id = obra.id if obra else None
    if dados.get("publico") is not None:
        tx.publico = bool(dados["publico"])
    tx.atualizado_em = datetime.utcnow()
    s.add(tx); s.commit(); s.refresh(tx)
    return _texto_payload(s, tx)


@app.delete("/api/eu/textos/{texto_id}")
def remover_texto(texto_id: int, request: Request, s: Session = Depends(get_session)):
    u = usuario_sessao(request, s)
    tx = s.get(TextoUsuario, texto_id)
    if not tx or tx.usuario_id != u.id:
        raise HTTPException(404, "texto não encontrado")
    s.delete(tx); s.commit()
    return {"ok": True}


@app.get("/api/textos/{texto_id}")
def ver_texto(texto_id: int, request: Request, s: Session = Depends(get_session)):
    tx = s.get(TextoUsuario, texto_id)
    atual = usuario_sessao(request, s)
    if not tx or (not tx.publico and tx.usuario_id != atual.id):
        raise HTTPException(404, "texto não encontrado")
    autor = s.get(Usuario, tx.usuario_id)
    return _texto_payload(s, tx, autor=autor)


@app.get("/api/u/{handle}/textos")
def textos_publicos_de(handle: str, request: Request, s: Session = Depends(get_session)):
    u = s.exec(select(Usuario).where(Usuario.handle == handle.lower().strip())).first()
    if not u:
        raise HTTPException(404, "perfil não encontrado")
    rows = s.exec(
        select(TextoUsuario)
        .where(TextoUsuario.usuario_id == u.id, TextoUsuario.publico == True)
        .order_by(TextoUsuario.criado_em.desc())
        .limit(50)
    ).all()
    return [_texto_payload(s, tx, trecho=True) for tx in rows]


def _feed_texto_item(s: Session, tx: TextoUsuario, autor: Usuario, atual: Usuario | None) -> dict:
    atual_id = atual.id if atual else None
    return {
        "tipo": "wrote_text",
        "usuario": {
            "handle": autor.handle, "nome": autor.nome, "avatar_url": getattr(autor, "avatar_url", "") or "",
            "is_demo": bool(getattr(autor, "is_demo", False)),
            "is_following": _is_following(s, atual_id, autor.id),
            "is_me": bool(atual_id and atual_id == autor.id),
        },
        "texto": _texto_payload(s, tx, trecho=True),
        "created_at": tx.criado_em.isoformat(),
    }


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


def _trecho_relato(texto: str, lim: int = 220) -> str:
    """Corta o relato para exibição em trecho terminando com reticências,
    em vez do corte seco no meio da frase."""
    if len(texto) <= lim:
        return texto
    corte = texto[:lim - 1]
    espaco = corte.rfind(" ")
    if espaco > lim // 2:
        corte = corte[:espaco]
    return corte.rstrip(" ,;:.!?-–—") + "…"


def _feed_review_item(s: Session, l: Leitura, ed: Edicao, o: Obra, autor: Usuario, atual: Usuario | None, trecho: bool = True) -> dict:
    relato = (l.relato or "").strip()
    atual_id = atual.id if atual else None
    return {
        "tipo": _feed_tipo(l),
        "usuario": {
            "handle": autor.handle, "nome": autor.nome, "avatar_url": getattr(autor, "avatar_url", "") or "", "is_demo": bool(getattr(autor, "is_demo", False)),
            "is_following": _is_following(s, atual_id, autor.id),
            "is_me": bool(atual_id and atual_id == autor.id),
        },
        "livro": {"titulo": o.titulo, "autor": o.autor, "work_key": o.ol_work_key, "capa_url": ed.capa_url},
        "edicao": {"editora": ed.editora, "tradutor": ed.tradutor, "ano": ed.ano},
        "leitura": {
            "leitura_id": l.id, "status": l.status, "nota": l.nota, "publico": bool(l.publico),
            "is_demo": bool(getattr(l, "is_demo", False)), "spoiler": bool(l.spoiler), "relato": (_trecho_relato(relato) if trecho else relato),
            **(_review_state(s, l.id, atual_id) if l.publico and relato else {"likes_count": 0, "liked_by_me": False, "saved_by_me": False, "reported_by_me": False, "comments_count": 0}),
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
    textos = s.exec(
        select(TextoUsuario, Usuario)
        .join(Usuario, TextoUsuario.usuario_id == Usuario.id)
        .where(TextoUsuario.usuario_id.in_(following_ids), TextoUsuario.publico == True)
        .order_by(TextoUsuario.criado_em.desc())
        .limit(limit)
    ).all()
    items += [_feed_texto_item(s, tx, autor, u) for tx, autor in textos]
    items = sorted(items, key=lambda i: i.get("created_at") or "", reverse=True)[:limit]
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
    # conteúdo demo só preenche o feed enquanto não há atividade real
    rows_reais = [r for r in rows if not r[0].is_demo]
    if rows_reais:
        rows = rows_reais
    reviews = [_feed_review_item(s, l, ed, o, autor, atual, trecho=False) for l, ed, o, autor in rows if (l.relato or "").strip()]
    textos = s.exec(
        select(TextoUsuario, Usuario)
        .join(Usuario, TextoUsuario.usuario_id == Usuario.id)
        .where(TextoUsuario.publico == True)
        .order_by(TextoUsuario.criado_em.desc())
        .limit(10)
    ).all()
    reviews += [_feed_texto_item(s, tx, autor, atual) for tx, autor in textos
                if not (atual.id and tx.usuario_id == atual.id)]
    reviews = sorted(reviews, key=lambda i: i.get("created_at") or "", reverse=True)[:limit]

    active_rows = s.exec(
        select(Usuario, func.count(Leitura.id).label("reviews_count"))
        .join(Leitura, Leitura.usuario_id == Usuario.id)
        .where(Leitura.publico == True, Leitura.relato != "")
        .group_by(Usuario.id)
        .order_by(Usuario.is_demo.asc(), func.count(Leitura.id).desc())
        .limit(20)
    ).all()
    leitores_reais = [r for r in active_rows if not bool(getattr(r[0], "is_demo", False))]
    if leitores_reais:
        active_rows = leitores_reais
    readers = []
    for leitor, reviews_count in active_rows:
        if atual.id and leitor.id == atual.id:
            continue
        readers.append({
            "handle": leitor.handle, "nome": leitor.nome, "bio": getattr(leitor, "bio", ""),
            "avatar_url": getattr(leitor, "avatar_url", "") or "",
            "is_demo": bool(getattr(leitor, "is_demo", False)), "reviews_count": reviews_count,
            "followers_count": _follow_counts(s, leitor.id)["followers_count"],
            "is_following": _is_following(s, atual.id, leitor.id), "is_me": False,
        })
        if len(readers) >= 10:
            break
    return {"reviews": reviews, "readers": readers}


@app.get("/api/feed/lendo")
def feed_lendo(request: Request, s: Session = Depends(get_session), scope: str = Query("following"), limit: int = Query(12, ge=1, le=20)):
    """Carrossel "lendo agora" do topo do feed: um item por leitor, com o
    livro em leitura mais recente. scope=following usa quem você segue;
    scope=discover mostra leitores ativos (demo só preenche na ausência de
    gente real, mesmo padrão do discover)."""
    atual = usuario_sessao(request, s)
    q = (
        select(Leitura, Edicao, Obra, Usuario)
        .join(Edicao, Leitura.edicao_id == Edicao.id)
        .join(Obra, Edicao.obra_id == Obra.id)
        .join(Usuario, Leitura.usuario_id == Usuario.id)
        .where(Leitura.status == "Lendo")
    )
    if scope == "following":
        following_ids = s.exec(select(Follow.following_id).where(Follow.follower_id == atual.id)).all()
        if not following_ids:
            return {"items": []}
        q = q.where(Leitura.usuario_id.in_(following_ids)).order_by(Leitura.criado_em.desc())
    else:
        if atual.id:
            q = q.where(Leitura.usuario_id != atual.id)
        q = q.order_by(Leitura.is_demo.asc(), Leitura.criado_em.desc())
    rows = s.exec(q.limit(80)).all()
    vistos: set[int] = set()
    items = []
    for l, ed, o, u in rows:
        if u.id in vistos:
            continue
        vistos.add(u.id)
        items.append({
            "handle": u.handle, "nome": u.nome,
            "avatar_url": getattr(u, "avatar_url", "") or "",
            "is_demo": bool(getattr(u, "is_demo", False)),
            "titulo": o.titulo, "autor": o.autor, "capa_url": ed.capa_url,
            "work_key": o.ol_work_key,
        })
    reais = [i for i in items if not i["is_demo"]]
    if reais and scope != "following":
        items = reais
    return {"items": items[:limit]}

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
    textos = [_texto_payload(s, tx, trecho=True) for tx in s.exec(
        select(TextoUsuario).where(TextoUsuario.usuario_id == u.id, TextoUsuario.publico == True)
        .order_by(TextoUsuario.criado_em.desc()).limit(20)
    ).all()]
    return {"handle": u.handle, "nome": u.nome, "bio": getattr(u, "bio", ""), "avatar_url": getattr(u, "avatar_url", "") or "", "is_demo": bool(getattr(u, "is_demo", False)), "leituras": leituras, "textos": textos, **perfil, **_profile_social_payload(s, u, atual)}


@app.post("/api/u/{handle}/follow")
def seguir_usuario(handle: str, request: Request, s: Session = Depends(get_session)):
    atual = _require_google_user(request, s)
    alvo = s.exec(select(Usuario).where(Usuario.handle == handle.lower().strip())).first()
    if not alvo:
        raise HTTPException(404, "perfil não encontrado")
    if atual.id == alvo.id:
        raise HTTPException(400, "você não pode seguir a si mesmo")
    if getattr(alvo, "is_demo", False):
        raise HTTPException(400, "perfis de exemplo não podem ser seguidos")
    follow = s.exec(select(Follow).where(Follow.follower_id == atual.id, Follow.following_id == alvo.id)).first()
    if not follow:
        s.add(Follow(follower_id=atual.id, following_id=alvo.id)); s.commit()
        _criar_notificacao(s, alvo.id, atual.id, "follow")
    return {"following": True, **_follow_counts(s, alvo.id)}


def _lista_follows(handle: str, direcao: str, request: Request, s: Session) -> list[dict]:
    alvo = s.exec(select(Usuario).where(Usuario.handle == handle.lower().strip())).first()
    if not alvo:
        raise HTTPException(404, "perfil não encontrado")
    atual = usuario_sessao(request, s)
    if direcao == "followers":
        ids = s.exec(select(Follow.follower_id).where(Follow.following_id == alvo.id)).all()
    else:
        ids = s.exec(select(Follow.following_id).where(Follow.follower_id == alvo.id)).all()
    if not ids:
        return []
    meus_follows = set(s.exec(select(Follow.following_id).where(Follow.follower_id == atual.id)).all()) if atual.id else set()
    usuarios = s.exec(select(Usuario).where(Usuario.id.in_(ids[:200])).order_by(Usuario.nome, Usuario.handle)).all()
    return [{
        "handle": u.handle, "nome": u.nome, "bio": getattr(u, "bio", ""),
        "avatar_url": getattr(u, "avatar_url", "") or "",
        "is_demo": bool(getattr(u, "is_demo", False)),
        "is_following": u.id in meus_follows,
        "is_me": bool(atual.id and atual.id == u.id),
    } for u in usuarios]


class ProfileReportPayload(BaseModel):
    motivo: Optional[str] = None
    detalhe: Optional[str] = None


@app.post("/api/u/{handle}/report")
def report_profile(handle: str, payload: ProfileReportPayload, request: Request, s: Session = Depends(get_session)):
    u = _require_google_user(request, s, "Entre com Google para denunciar perfis.", 401)
    alvo = s.exec(select(Usuario).where(Usuario.handle == handle.lower().strip())).first()
    if not alvo:
        raise HTTPException(404, "perfil não encontrado")
    if alvo.id == u.id:
        raise HTTPException(400, "você não pode denunciar o próprio perfil")
    pendente = s.exec(select(ProfileReport).where(
        ProfileReport.target_id == alvo.id, ProfileReport.reporter_id == u.id,
        ProfileReport.status == "pending")).first()
    if not pendente:
        s.add(ProfileReport(target_id=alvo.id, reporter_id=u.id,
                            motivo=_clean_text(payload.motivo, 80) or "other",
                            detalhe=_clean_text(payload.detalhe, 500)))
        s.commit()
    return {"reported": True}


@app.get("/api/u/{handle}/followers")
def listar_seguidores(handle: str, request: Request, s: Session = Depends(get_session)):
    return _lista_follows(handle, "followers", request, s)


@app.get("/api/u/{handle}/following")
def listar_seguindo(handle: str, request: Request, s: Session = Depends(get_session)):
    return _lista_follows(handle, "following", request, s)


@app.get("/api/notificacoes/nao-lidas")
def contar_notificacoes_nao_lidas(request: Request, s: Session = Depends(get_session)):
    u = usuario_sessao(request, s)
    if not u.google_sub:
        return {"count": 0}
    count = s.exec(
        select(func.count()).select_from(Notificacao).where(Notificacao.usuario_id == u.id, Notificacao.lida == False)
    ).one()
    return {"count": count}


@app.get("/api/notificacoes")
def listar_notificacoes(request: Request, s: Session = Depends(get_session), limit: int = Query(30, ge=1, le=50)):
    u = _require_google_user(request, s, "Entre com Google para ver sua atividade.", 401)
    rows = s.exec(
        select(Notificacao, Usuario)
        .join(Usuario, Notificacao.ator_id == Usuario.id)
        .where(Notificacao.usuario_id == u.id)
        .order_by(Notificacao.criado_em.desc())
        .limit(limit)
    ).all()
    leitura_ids = [n.leitura_id for n, _ in rows if n.leitura_id]
    obras_por_leitura: dict[int, dict] = {}
    if leitura_ids:
        obra_rows = s.exec(
            select(Leitura.id, Obra.titulo, Obra.autor)
            .join(Edicao, Leitura.edicao_id == Edicao.id)
            .join(Obra, Edicao.obra_id == Obra.id)
            .where(Leitura.id.in_(leitura_ids))
        ).all()
        obras_por_leitura = {lid: {"titulo": titulo, "autor": autor} for lid, titulo, autor in obra_rows}
    payload = [{
        "id": n.id, "tipo": n.tipo, "lida": bool(n.lida), "criado_em": n.criado_em.isoformat(),
        "ator": {"handle": ator.handle, "nome": ator.nome, "avatar_url": getattr(ator, "avatar_url", "") or "", "is_demo": bool(getattr(ator, "is_demo", False))},
        "leitura_id": n.leitura_id,
        "obra": obras_por_leitura.get(n.leitura_id) if n.leitura_id else None,
    } for n, ator in rows]
    # abrir o painel já marca como lida -- é o gesto que zera a bolinha
    nao_lidas = [n for n, _ in rows if not n.lida]
    if nao_lidas:
        for n in nao_lidas:
            n.lida = True
            s.add(n)
        s.commit()
    return payload


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
    textos = [_texto_payload(s, tx, trecho=True) for tx in s.exec(
        select(TextoUsuario).where(TextoUsuario.usuario_id == u.id, TextoUsuario.publico == True)
        .order_by(TextoUsuario.criado_em.desc()).limit(8)
    ).all()]
    return HTMLResponse(render_estante_publica(u, _leituras_de(s, u.id), _profile_social_payload(s, u, atual), textos=textos))


@app.get("/u/{handle}/texto/{texto_id}")
def texto_publico(handle: str, texto_id: int, request: Request, s: Session = Depends(get_session)):
    u = s.exec(select(Usuario).where(Usuario.handle == handle.lower().strip())).first()
    tx = s.get(TextoUsuario, texto_id) if u else None
    atual = usuario_sessao(request, s)
    if not u or not tx or tx.usuario_id != u.id or (not tx.publico and tx.usuario_id != atual.id):
        corpo = (
            '<div class="wordmark">LOMBADA<span class="dot">.</span></div>'
            '<div class="empty">esse texto não existe (ou o link veio torto).</div>'
            '<a class="cta" href="/">conhecer a Lombada →</a>'
        )
        return HTMLResponse(_pagina("texto não encontrado · Lombada", corpo), status_code=404)
    return HTMLResponse(render_texto_publico(u, _texto_payload(s, tx)))


# ─── páginas das editoras ─────────────────────────────────
@app.get("/editoras")
def indice_editoras(s: Session = Depends(get_session)):
    return HTMLResponse(render_indice_editoras(listar_editoras(s)))


@app.get("/editora/{slug}")
def pagina_editora(slug: str, page: int = Query(1, ge=1), per_page: int = Query(20), view: str = Query("grade"), s: Session = Depends(get_session)):
    dados = dados_editora(s, slug.lower().strip())
    if not dados:
        corpo = (
            '<div class="wordmark">LOMBADA<span class="dot">.</span></div>'
            '<div class="empty">essa editora ainda não está no catálogo.</div>'
            '<a class="cta" href="/editoras">ver todas as editoras →</a>'
        )
        return HTMLResponse(_pagina("editora não encontrada · Lombada", corpo), status_code=404)
    per_page = per_page if per_page in {10, 20, 50} else 20
    view = "lista" if (view or "").lower().strip() == "lista" else "grade"
    return HTMLResponse(render_pagina_editora(dados, page=page, per_page=per_page, view=view))



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
    profile_reports = s.exec(
        select(ProfileReport, Usuario)
        .join(Usuario, ProfileReport.target_id == Usuario.id)
        .where(ProfileReport.status == "pending")
        .order_by(ProfileReport.created_at.desc())
    ).all()
    profile_report_items = []
    for prep, alvo in profile_reports:
        avatar = getattr(alvo, "avatar_url", "") or ""
        avatar_html = f'<img src="{_esc(avatar)}" alt="" style="width:48px;height:48px;border-radius:50%;object-fit:cover;vertical-align:middle;margin-right:8px">' if avatar else ""
        profile_report_items.append(
            f'<article class="card-form" style="margin:16px 0">'
            f'<div class="meta">#{prep.id} · perfil · {_esc(prep.motivo)} · {prep.created_at.isoformat()}</div>'
            f'<p>{avatar_html}<a href="/u/{_esc(alvo.handle)}" target="_blank" rel="noopener"><strong>@{_esc(alvo.handle)}</strong></a> · {_esc(alvo.nome)}</p>'
            f'<p>{_esc((getattr(alvo, "bio", "") or "")[:300])}</p>'
            f'<p>{_esc(prep.detalhe)}</p>'
            f'<form method="post" action="/admin/profile-reports/{prep.id}/reviewed" style="display:inline"><button>Marcar revisada</button></form> '
            f'<form method="post" action="/admin/profile-reports/{prep.id}/dismissed" style="display:inline"><button>Dispensar</button></form>'
            f'</article>'
        )
    resumo = _resumo_usuarios(s)
    usuarios_html = (
        '<h2>Usuários</h2>'
        f'<p><strong>{resumo["total"]}</strong> usuários · {resumo["com_google"]} com Google · '
        f'{resumo["anonimos"]} anônimos · {resumo["novos_30d"]} novos e {resumo["ativos_30d"]} ativos nos últimos 30 dias · '
        '<a href="/admin/usuarios">ver relatório completo</a></p>'
    )
    corpo = '<div class="app"><div class="wordmark">LOMBADA<span class="dot">.</span></div><h1>Admin</h1><p><a href="/admin/source-records">Revisar source_records de editoras</a></p>' + usuarios_html + '<h2>Denúncias pendentes</h2>' + (''.join(report_items) or '<p>Nenhuma denúncia pendente.</p>') + '<h2>Denúncias de perfil</h2>' + (''.join(profile_report_items) or '<p>Nenhuma denúncia de perfil pendente.</p>') + '<h2>Sugestões pendentes</h2>' + (''.join(items) or '<p>Nenhuma sugestão pendente.</p>') + '</div>'
    return HTMLResponse(_pagina("Admin · Lombada", corpo))


# ─── admin: relatório de usuários ─────────────────────────
def _resumo_usuarios(s: Session) -> dict:
    corte_30d = datetime.utcnow() - timedelta(days=30)
    total = s.exec(select(func.count(Usuario.id))).one()
    com_google = s.exec(select(func.count(Usuario.id)).where(Usuario.google_sub.is_not(None))).one()
    demo = s.exec(select(func.count(Usuario.id)).where(Usuario.is_demo == True)).one()  # noqa: E712
    novos_30d = s.exec(select(func.count(Usuario.id)).where(Usuario.criado_em >= corte_30d)).one()
    ativos_30d = s.exec(
        select(func.count(func.distinct(Leitura.usuario_id))).where(
            Leitura.usuario_id.is_not(None), Leitura.criado_em >= corte_30d
        )
    ).one()
    return {
        "total": int(total or 0),
        "com_google": int(com_google or 0),
        "anonimos": int(total or 0) - int(com_google or 0) - int(demo or 0),
        "demo": int(demo or 0),
        "novos_30d": int(novos_30d or 0),
        "ativos_30d": int(ativos_30d or 0),
    }


def _contagens_por_usuario(s: Session, modelo, coluna_usuario, ids: list[int]) -> dict[int, int]:
    if not ids:
        return {}
    rows = s.exec(
        select(coluna_usuario, func.count(modelo.id))
        .where(coluna_usuario.in_(ids))
        .group_by(coluna_usuario)
    ).all()
    return {int(uid): int(qtd) for uid, qtd in rows}


ADMIN_USUARIOS_FILTROS = {"todos": "todos", "google": "com Google", "anonimos": "anônimos", "demo": "demo"}
ADMIN_USUARIOS_ORDENS = {"recentes": "mais recentes", "antigos": "mais antigos", "uso": "mais leituras"}


@app.get("/admin/usuarios")
def admin_usuarios(request: Request, page: int = Query(1, ge=1), filtro: str = Query("todos"),
                   ordem: str = Query("recentes"), s: Session = Depends(get_session)):
    _require_admin(request, s)
    per_page = 50
    filtro = filtro if filtro in ADMIN_USUARIOS_FILTROS else "todos"
    ordem = ordem if ordem in ADMIN_USUARIOS_ORDENS else "recentes"

    leit_sq = (
        select(
            Leitura.usuario_id.label("uid"),
            func.count(Leitura.id).label("leituras"),
            func.max(Leitura.criado_em).label("ultima_leitura"),
        )
        .where(Leitura.usuario_id.is_not(None))
        .group_by(Leitura.usuario_id)
        .subquery()
    )
    q = select(Usuario, leit_sq.c.leituras, leit_sq.c.ultima_leitura).outerjoin(
        leit_sq, leit_sq.c.uid == Usuario.id
    )
    q_total = select(func.count(Usuario.id))
    if filtro == "google":
        cond = Usuario.google_sub.is_not(None)
    elif filtro == "anonimos":
        cond = and_(Usuario.google_sub.is_(None), Usuario.is_demo == False)  # noqa: E712
    elif filtro == "demo":
        cond = Usuario.is_demo == True  # noqa: E712
    else:
        cond = None
    if cond is not None:
        q = q.where(cond)
        q_total = q_total.where(cond)

    if ordem == "uso":
        q = q.order_by(func.coalesce(leit_sq.c.leituras, 0).desc(), Usuario.criado_em.desc())
    elif ordem == "antigos":
        q = q.order_by(Usuario.criado_em.asc())
    else:
        q = q.order_by(Usuario.criado_em.desc())

    total_filtro = int(s.exec(q_total).one() or 0)
    rows = s.exec(q.offset((page - 1) * per_page).limit(per_page)).all()

    ids = [u.id for u, _, _ in rows]
    textos = _contagens_por_usuario(s, TextoUsuario, TextoUsuario.usuario_id, ids)
    diario = _contagens_por_usuario(s, ReadingJournalEntry, ReadingJournalEntry.usuario_id, ids)
    seguidores = _contagens_por_usuario(s, Follow, Follow.following_id, ids)
    seguindo = _contagens_por_usuario(s, Follow, Follow.follower_id, ids)

    resumo = _resumo_usuarios(s)
    cards = (
        '<div class="profile-metrics" style="margin:16px 0">'
        f'<div><strong>{resumo["total"]}</strong><span>usuários</span></div>'
        f'<div><strong>{resumo["com_google"]}</strong><span>com Google</span></div>'
        f'<div><strong>{resumo["anonimos"]}</strong><span>anônimos</span></div>'
        f'<div><strong>{resumo["demo"]}</strong><span>demo</span></div>'
        f'<div><strong>{resumo["novos_30d"]}</strong><span>novos 30d</span></div>'
        f'<div><strong>{resumo["ativos_30d"]}</strong><span>ativos 30d</span></div>'
        '</div>'
    )

    def _link_filtro(chave: str, rotulo: str, ativo: str, param: str) -> str:
        params = {"filtro": filtro, "ordem": ordem}
        params[param] = chave
        marca = " <strong>✓</strong>" if chave == ativo else ""
        return f'<a href="/admin/usuarios?filtro={params["filtro"]}&ordem={params["ordem"]}">{_esc(rotulo)}</a>{marca}'

    filtros_html = " · ".join(_link_filtro(k, v, filtro, "filtro") for k, v in ADMIN_USUARIOS_FILTROS.items())
    ordens_html = " · ".join(_link_filtro(k, v, ordem, "ordem") for k, v in ADMIN_USUARIOS_ORDENS.items())

    def _td(valor, num: bool = False) -> str:
        alinh = ";text-align:right" if num else ""
        return f'<td style="padding:6px 8px;border-bottom:1px solid rgba(128,128,128,.25){alinh}">{valor}</td>'

    linhas = []
    for u, leituras, ultima in rows:
        tipo = "demo" if getattr(u, "is_demo", False) else ("google" if u.google_sub else "anônimo")
        criado = u.criado_em.strftime("%Y-%m-%d") if u.criado_em else "—"
        ultima_str = ultima.strftime("%Y-%m-%d") if ultima else "—"
        linhas.append(
            "<tr>"
            + _td(u.id)
            + _td(f'<a href="/u/{_esc(u.handle)}" target="_blank" rel="noopener">@{_esc(u.handle)}</a>')
            + _td(_esc(u.nome or ""))
            + _td(_esc(u.email or ""))
            + _td(tipo)
            + _td(criado)
            + _td(int(leituras or 0), num=True)
            + _td(ultima_str)
            + _td(diario.get(u.id, 0), num=True)
            + _td(textos.get(u.id, 0), num=True)
            + _td(seguidores.get(u.id, 0), num=True)
            + _td(seguindo.get(u.id, 0), num=True)
            + "</tr>"
        )

    paginas = max(1, (total_filtro + per_page - 1) // per_page)
    nav = []
    if page > 1:
        nav.append(f'<a href="/admin/usuarios?filtro={filtro}&ordem={ordem}&page={page - 1}">← anterior</a>')
    nav.append(f"página {page} de {paginas}")
    if page < paginas:
        nav.append(f'<a href="/admin/usuarios?filtro={filtro}&ordem={ordem}&page={page + 1}">próxima →</a>')

    tabela = (
        '<div style="overflow-x:auto"><table style="width:100%;border-collapse:collapse;font-size:14px">'
        "<thead><tr>"
        + "".join(
            f'<th style="text-align:left;padding:6px 8px;border-bottom:1px solid currentColor">{h}</th>'
            for h in ("id", "handle", "nome", "email", "conta", "criado em", "leituras",
                      "última leitura", "diário", "textos", "seguidores", "seguindo")
        )
        + "</tr></thead><tbody>"
        + "".join(linhas)
        + "</tbody></table></div>"
    )

    corpo = (
        '<div class="app"><div class="wordmark">LOMBADA<span class="dot">.</span></div>'
        '<h1>Usuários</h1><p><a href="/admin">← voltar ao admin</a></p>'
        + cards
        + f"<p>Filtro: {filtros_html}</p><p>Ordem: {ordens_html}</p>"
        + f"<p>{total_filtro} usuário(s) no filtro atual.</p>"
        + (tabela if linhas else "<p>Nenhum usuário neste filtro.</p>")
        + "<p>" + " · ".join(nav) + "</p></div>"
    )
    return HTMLResponse(_pagina("Usuários · Admin · Lombada", corpo))


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



@app.post("/admin/profile-reports/{report_id}/{action}")
def admin_profile_report_review(report_id: int, action: str, request: Request, s: Session = Depends(get_session)):
    admin = _require_admin(request, s)
    rep = s.get(ProfileReport, report_id)
    if not rep:
        raise HTTPException(404, "denúncia não encontrada")
    if action not in {"reviewed", "dismissed"}:
        raise HTTPException(404, "ação inválida")
    rep.status = action
    rep.reviewed_at = datetime.utcnow()
    rep.reviewed_by = admin.email or admin.handle
    s.add(rep); s.commit()
    return HTMLResponse('<meta http-equiv="refresh" content="0; url=/admin">')


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
        paginas_sug = payload.get("paginas")
        edicao = Edicao(obra_id=obra.id, ol_edition_key=payload.get("ol_edition_key"), editora=_clean_text(payload.get("editora"), 160),
                        tradutor=_clean_text(payload.get("tradutor"), 160), isbn=_clean_text(payload.get("isbn"), 32),
                        idioma=_clean_text(payload.get("idioma"), 80), ano=payload.get("ano_edicao"), capa_url=_clean_url(payload.get("capa_url"), 500) if payload.get("capa_url") else "",
                        paginas=paginas_sug if isinstance(paginas_sug, int) and 0 < paginas_sug <= 20000 else None)
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

def _public_base_url(request: Request) -> str:
    configured = os.getenv("PUBLIC_BASE_URL", "").strip().rstrip("/")
    if configured:
        return configured
    proto = request.headers.get("x-forwarded-proto") or request.url.scheme
    host = request.headers.get("x-forwarded-host") or request.headers.get("host") or request.url.netloc
    proto = proto.split(",", 1)[0].strip() or "https"
    host = host.split(",", 1)[0].strip()
    if proto == "http" and host.endswith(".railway.app"):
        proto = "https"
    return f"{proto}://{host}".rstrip("/")


@app.get("/api-docs")
@app.get("/api")
def api_docs(request: Request):
    return HTMLResponse(render_api_docs(base_url=_public_base_url(request), app_url="/", instagram_url=INSTAGRAM_URL))


@app.get("/contribua")
def contribua():
    return HTMLResponse(render_landing(
        app_url="/",
        play_store_url=PLAY_STORE_URL,
        apoio_url=APOIO_URL,
        instagram_url=INSTAGRAM_URL,
        blog_url=BLOG_URL,
    ))


@app.get("/sobre")
def sobre():
    return HTMLResponse(render_landing(
        app_url="/",
        play_store_url=PLAY_STORE_URL,
        apoio_url=APOIO_URL,
        instagram_url=INSTAGRAM_URL,
        blog_url=BLOG_URL,
    ))


@app.get("/quem-somos")
def quem_somos():
    return HTMLResponse(render_quem_somos(app_url="/", instagram_url=INSTAGRAM_URL))


@app.get("/blog")
def blog_index():
    return HTMLResponse(render_blog_index(blog_mod.listar_posts(), app_url="/", instagram_url=INSTAGRAM_URL))


@app.get("/blog/{slug}")
def blog_post(slug: str):
    post = blog_mod.carregar_post(slug)
    if not post:
        return HTMLResponse(_pagina("post não encontrado · Lombada",
                                    '<p class="empty">Esse post não existe (ou saiu do ar). '
                                    '<a href="/blog">Ver todos os posts</a>.</p>'), status_code=404)
    return HTMLResponse(render_blog_post(post, app_url="/", instagram_url=INSTAGRAM_URL))


@app.get("/privacidade")
def privacidade():
    return HTMLResponse(render_privacidade(app_url="/", instagram_url=INSTAGRAM_URL,
                                           contact_email=CONTACT_EMAIL))


@app.get("/.well-known/assetlinks.json")
def assetlinks():
    # Digital Asset Links: verifica o domínio pra a TWA (app Android) abrir sem
    # a barra de navegador. Enquanto package/fingerprint não estiverem
    # configurados, devolve lista vazia (arquivo válido, ainda sem verificar).
    fingerprints = [f.strip() for f in ANDROID_CERT_SHA256.split(",") if f.strip()]
    if ANDROID_PACKAGE_NAME and fingerprints:
        statements = [{
            "relation": ["delegate_permission/common.handle_all_urls"],
            "target": {
                "namespace": "android_app",
                "package_name": ANDROID_PACKAGE_NAME,
                "sha256_cert_fingerprints": fingerprints,
            },
        }]
    else:
        statements = []
    return JSONResponse(statements, media_type="application/json")


def render_index() -> HTMLResponse:
    html = (AQUI / "index.html").read_text(encoding="utf-8")
    asset_version = APP_VERSION if APP_VERSION and APP_VERSION != "dev" else "20260712b"
    html = html.replace("{{APP_VERSION}}", asset_version)
    return HTMLResponse(
        html,
        headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"},
    )


@app.get("/")
def home():
    return render_index()


@app.get("/index.html")
def index_html():
    return render_index()


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
