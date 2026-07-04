"""
Lombada — autenticação.

Dois modos, na mesma sessão de cookie:
  • anônimo  — 1ª visita já cria um Usuario com handle literário curto (sem cadastro).
  • Google   — OAuth 2.0 (Authorization Code), vincula o Google ao usuário
               anônimo atual; se aquele Google já existe noutro usuário,
               MIGRA as leituras e descarta o órfão (merge de estante).

Os dados de perfil vêm do endpoint userinfo do Google usando o access_token
retornado na troca server-to-server do authorization code.
"""
import logging
import os
import random
import re
import secrets
import unicodedata
from datetime import datetime
from urllib.parse import urlencode, urlparse

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import select, Session

from models import (
    CatalogSuggestion,
    Follow,
    Leitura,
    ReadingJournalEntry,
    ReviewLike,
    ReviewReport,
    SavedReview,
    UserEdition,
    Usuario,
    get_session,
)


# ─── config Google ────────────────────────────────────────
GOOGLE_CLIENT_ID     = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REDIRECT_URI  = os.getenv("GOOGLE_REDIRECT_URI", "").strip()
GOOGLE_AUTH  = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO = "https://www.googleapis.com/oauth2/v3/userinfo"
_TIMEOUT = 12.0
logger = logging.getLogger(__name__)


def google_redirect_uri(request: Request) -> str:
    configured = GOOGLE_REDIRECT_URI.strip()
    if configured:
        return configured

    forwarded_proto = (request.headers.get("x-forwarded-proto") or "").split(",", 1)[0].strip()
    forwarded_host = (request.headers.get("x-forwarded-host") or "").split(",", 1)[0].strip()
    fallback = urlparse(str(request.base_url))
    scheme = forwarded_proto or request.url.scheme or fallback.scheme
    host = forwarded_host or request.headers.get("host") or fallback.netloc

    if scheme == "http":
        hostname = (urlparse(f"//{host}").hostname or "").lower()
        local_hosts = {"localhost", "127.0.0.1", "0.0.0.0", "::1"}
        if hostname not in local_hosts and not hostname.endswith(".local"):
            scheme = "https"

    base = f"{scheme}://{host}".rstrip("/")
    return f"{base}/api/auth/google/callback"


# ─── usuário anônimo (handle literário curto) ──────────────
_FALLBACK_HANDLE_PREFIXES = ("leitor", "leitora", "pagina", "margem")
_BAD_OLD_HANDLE_WORDS = (
    "capivara", "coruja", "raposa", "tatu", "lontra", "perereca", "jaguatirica",
    "tucano", "sagui", "quati", "arara", "preguica", "tamandua", "bemtevi",
)
_HANDLE_RE = re.compile(r"[^a-z0-9]+")


def _slug_handle(valor: str, limite: int = 24) -> str:
    bruto = unicodedata.normalize("NFKD", valor or "").encode("ascii", "ignore").decode("ascii")
    slug = _HANDLE_RE.sub("-", bruto.lower()).strip("-")
    slug = re.sub(r"-{2,}", "-", slug).strip("-")
    partes = [p for p in slug.split("-") if p and p not in {"a", "o", "as", "os"}]
    slug = "-".join(partes)[:limite].strip("-")
    return slug or "leitor"


def _base_handle(nome: str = "", email: str = "") -> str:
    if nome and len(nome.strip()) >= 2:
        primeiro = nome.strip().split()[0]
        if len(_slug_handle(primeiro, 18)) >= 2:
            return _slug_handle(primeiro, 18)
    if email and "@" in email:
        return _slug_handle(email.split("@", 1)[0], 24)
    return f"{random.choice(_FALLBACK_HANDLE_PREFIXES)}-{random.randint(0, 9999):04d}"


def _handle_disponivel(s: Session, handle: str, exceto_id=None) -> bool:
    existente = s.exec(select(Usuario).where(Usuario.handle == handle)).first()
    return not existente or existente.id == exceto_id


def _gera_handle(s: Session, nome: str = "", email: str = "", exceto_id=None) -> str:
    base = _base_handle(nome, email)
    for candidato in [base, *[f"{base}-{i}" for i in range(2, 30)]]:
        if _handle_disponivel(s, candidato, exceto_id):
            logger.info("[handle gerado] base=%s handle=%s", base, candidato)
            return candidato
        logger.info("[handle colisao] candidato=%s", candidato)
    for _ in range(40):
        candidato = f"{random.choice(_FALLBACK_HANDLE_PREFIXES)}-{random.randint(0, 9999):04d}"
        if _handle_disponivel(s, candidato, exceto_id):
            logger.info("[handle gerado] base=fallback handle=%s", candidato)
            return candidato
    return f"leitor-{int(datetime.utcnow().timestamp())}"


def _handle_antigo_automatico(handle: str) -> bool:
    return any(palavra in (handle or "") for palavra in _BAD_OLD_HANDLE_WORDS)

def criar_anonimo(s: Session) -> Usuario:
    u = Usuario(handle=_gera_handle(s), nome="Leitor Lombada")
    s.add(u)
    s.commit()
    s.refresh(u)
    return u


def usuario_sessao(request, s: Session) -> Usuario:
    uid = request.session.get("uid")
    u = s.get(Usuario, uid) if uid else None
    if not u:
        u = criar_anonimo(s)
        request.session["uid"] = u.id
    return u


# ─── helpers OAuth ────────────────────────────────────────
def _userinfo_google(access_token: str) -> dict:
    if not access_token:
        raise HTTPException(400, "access_token ausente na resposta do Google")
    try:
        with httpx.Client(timeout=_TIMEOUT) as c:
            r = c.get(
                GOOGLE_USERINFO,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            r.raise_for_status()
            info = r.json()
    except httpx.HTTPStatusError as e:
        detalhe = e.response.text[:200] if e.response is not None else str(e)
        raise HTTPException(502, f"falha ao buscar perfil no Google: {detalhe}")
    except Exception as e:
        raise HTTPException(502, f"falha ao buscar perfil no Google: {e}")
    if not info.get("sub"):
        raise HTTPException(400, "perfil do Google sem sub")
    return info


def _email_em_uso(s: Session, email: str, exceto_id) -> bool:
    if not email:
        return False
    outro = s.exec(select(Usuario).where(Usuario.email == email)).first()
    return bool(outro and outro.id != exceto_id)


def _score_leitura(l: Leitura) -> tuple[int, datetime]:
    preenchidos = sum(
        1
        for valor in (l.status, l.nota, l.relato, l.data)
        if valor not in (None, "")
    )
    return (preenchidos, l.criado_em or datetime.min)


def _copiar_leitura(origem: Leitura, destino: Leitura) -> None:
    for campo in ("status", "nota", "relato", "publico", "spoiler", "data", "criado_em"):
        setattr(destino, campo, getattr(origem, campo))


def _migrar_diario_leitura(s: Session, leitura_de: int, leitura_para: int, usuario_para: int) -> None:
    rows = s.exec(
        select(ReadingJournalEntry).where(ReadingJournalEntry.leitura_id == leitura_de)
    ).all()
    for row in rows:
        row.leitura_id = leitura_para
        row.usuario_id = usuario_para
        row.updated_at = datetime.utcnow()
        s.add(row)


def _mover_diario_usuario(s: Session, de: int, para: int) -> None:
    rows = s.exec(
        select(ReadingJournalEntry).where(ReadingJournalEntry.usuario_id == de)
    ).all()
    for row in rows:
        row.usuario_id = para
        row.updated_at = datetime.utcnow()
        s.add(row)


def _migrar_interacoes_leitura(s: Session, leitura_de: int, leitura_para: int) -> None:
    if leitura_de == leitura_para:
        return
    for modelo in (ReviewLike, SavedReview, ReviewReport):
        rows = s.exec(select(modelo).where(modelo.leitura_id == leitura_de)).all()
        for row in rows:
            duplicado = s.exec(
                select(modelo).where(
                    modelo.leitura_id == leitura_para,
                    modelo.usuario_id == row.usuario_id,
                )
            ).first()
            if duplicado:
                s.delete(row)
            else:
                row.leitura_id = leitura_para
                s.add(row)


def _mover_leituras(s: Session, de: int, para: int) -> int:
    if de == para:
        return 0
    rows = s.exec(select(Leitura).where(Leitura.usuario_id == de)).all()
    movidas = 0
    for l in rows:
        existente = s.exec(
            select(Leitura).where(
                Leitura.usuario_id == para,
                Leitura.edicao_id == l.edicao_id,
            )
        ).first()
        if existente:
            if _score_leitura(l) > _score_leitura(existente):
                _copiar_leitura(l, existente)
                s.add(existente)
            _migrar_interacoes_leitura(s, l.id, existente.id)
            _migrar_diario_leitura(s, l.id, existente.id, para)
            s.delete(l)
        else:
            l.usuario_id = para
            s.add(l)
            _migrar_diario_leitura(s, l.id, l.id, para)
            movidas += 1
    return movidas


def _mover_user_editions(s: Session, de: int, para: int) -> None:
    rows = s.exec(select(UserEdition).where(UserEdition.usuario_id == de)).all()
    for rel in rows:
        destino = s.exec(
            select(UserEdition).where(
                UserEdition.usuario_id == para,
                UserEdition.edicao_id == rel.edicao_id,
            )
        ).first()
        if not destino:
            rel.usuario_id = para
            rel.updated_at = datetime.utcnow()
            s.add(rel)
            continue
        destino.tenho = bool(destino.tenho or rel.tenho)
        destino.quero = bool(destino.quero or rel.quero)
        if destino.tenho:
            destino.quero = False
        destino.updated_at = datetime.utcnow()
        s.add(destino)
        s.delete(rel)


def _mover_catalog_suggestions(s: Session, de: int, para: int, email_destino: str = "") -> None:
    rows = s.exec(select(CatalogSuggestion).where(CatalogSuggestion.user_id == de)).all()
    for sug in rows:
        sug.user_id = para
        if not sug.user_email and email_destino:
            sug.user_email = email_destino
        s.add(sug)


def _mover_relacao_unica_por_usuario(s: Session, modelo, de: int, para: int) -> None:
    rows = s.exec(select(modelo).where(modelo.usuario_id == de)).all()
    for row in rows:
        duplicado = s.exec(
            select(modelo).where(
                modelo.leitura_id == row.leitura_id,
                modelo.usuario_id == para,
            )
        ).first()
        if duplicado:
            s.delete(row)
        else:
            row.usuario_id = para
            s.add(row)


def _mover_follows(s: Session, de: int, para: int) -> None:
    seguindo = s.exec(select(Follow).where(Follow.follower_id == de)).all()
    for follow in seguindo:
        if follow.following_id == para:
            s.delete(follow)
            continue
        duplicado = s.exec(
            select(Follow).where(
                Follow.follower_id == para,
                Follow.following_id == follow.following_id,
            )
        ).first()
        if duplicado:
            s.delete(follow)
        else:
            follow.follower_id = para
            s.add(follow)

    seguidores = s.exec(select(Follow).where(Follow.following_id == de)).all()
    for follow in seguidores:
        if follow.follower_id == para:
            s.delete(follow)
            continue
        duplicado = s.exec(
            select(Follow).where(
                Follow.follower_id == follow.follower_id,
                Follow.following_id == para,
            )
        ).first()
        if duplicado:
            s.delete(follow)
        else:
            follow.following_id = para
            s.add(follow)


def _merge_usuario_orfao(s: Session, de_id: int, para_id: int) -> None:
    if de_id == para_id:
        return
    destino = s.get(Usuario, para_id)
    if not destino:
        raise ValueError(f"usuário destino inexistente no merge: {para_id}")

    _mover_leituras(s, de_id, para_id)
    _mover_diario_usuario(s, de_id, para_id)
    _mover_user_editions(s, de_id, para_id)
    _mover_catalog_suggestions(s, de_id, para_id, destino.email or "")
    for modelo in (ReviewLike, SavedReview, ReviewReport):
        _mover_relacao_unica_por_usuario(s, modelo, de_id, para_id)
    _mover_follows(s, de_id, para_id)


# ─── rotas Google OAuth ───────────────────────────────────
router = APIRouter()


@router.get("/api/auth/google/config")
def google_config(request: Request):
    return {
        "google_client_id_configured": bool(GOOGLE_CLIENT_ID),
        "google_client_secret_configured": bool(GOOGLE_CLIENT_SECRET),
        "google_redirect_uri": google_redirect_uri(request),
        "cookie_secure": os.getenv("COOKIE_SECURE", "true").lower() == "true",
    }


@router.get("/api/auth/google/login")
def google_login(request: Request):
    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        logger.error(
            "[google oauth config error] client_id_configured=%s client_secret_configured=%s redirect_uri=%s",
            bool(GOOGLE_CLIENT_ID),
            bool(GOOGLE_CLIENT_SECRET),
            google_redirect_uri(request),
        )
        return RedirectResponse("/?conta=erro", status_code=303)
    state = secrets.token_urlsafe(24)
    request.session["oauth_state"] = state
    redirect_uri = google_redirect_uri(request)
    params = {
        "client_id":     GOOGLE_CLIENT_ID,
        "redirect_uri":  redirect_uri,
        "response_type": "code",
        "scope":         "openid email profile",
        "state":         state,
        "access_type":   "online",
        "prompt":        "select_account",
    }
    return RedirectResponse(GOOGLE_AUTH + "?" + urlencode(params), status_code=303)


@router.get("/api/auth/google/callback")
def google_callback(request: Request, code: str = "", state: str = "",
                    error: str = "", s: Session = Depends(get_session)):
    if error:
        return RedirectResponse("/?conta=erro", status_code=303)

    # CSRF: o state tem que bater com o que guardamos na sessão.
    esperado = request.session.pop("oauth_state", None)
    if not state or not esperado or state != esperado:
        logger.warning(
            "[google oauth state invalid] has_state=%s has_expected=%s",
            bool(state),
            bool(esperado),
        )
        request.session.clear()
        return RedirectResponse("/?conta=state_expirado", status_code=303)
    if not code:
        logger.warning("[google oauth callback missing code] has_state=%s", bool(state))
        return RedirectResponse("/?conta=erro", status_code=303)

    redirect_uri = google_redirect_uri(request)

    # troca o code por tokens (server-to-server)
    try:
        with httpx.Client(timeout=_TIMEOUT) as c:
            r = c.post(GOOGLE_TOKEN, data={
                "code":          code,
                "client_id":     GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "redirect_uri":  redirect_uri,
                "grant_type":    "authorization_code",
            })
            r.raise_for_status()
            tok = r.json()
    except httpx.HTTPStatusError as e:
        status_code = e.response.status_code if e.response is not None else "sem-status"
        body = e.response.text if e.response is not None else "sem-resposta"
        logger.error(
            "[google oauth token error] status=%s redirect_uri=%s client_id_configured=%s body=%s",
            status_code,
            redirect_uri,
            bool(GOOGLE_CLIENT_ID),
            body,
        )
        return RedirectResponse("/?conta=erro", status_code=303)
    except httpx.HTTPError as e:
        logger.error(
            "[google oauth token error] status=request-error redirect_uri=%s client_id_configured=%s body=%s",
            redirect_uri,
            bool(GOOGLE_CLIENT_ID),
            str(e),
        )
        return RedirectResponse("/?conta=erro", status_code=303)

    try:
        info = _userinfo_google(tok.get("access_token") or "")
        sub   = info["sub"]
        email = (info.get("email") or "").strip()
        nome  = (info.get("name") or "").strip()

        # ─── merge de estante ───
        canonico = s.exec(select(Usuario).where(Usuario.google_sub == sub)).first()
        atual = usuario_sessao(request, s)

        if canonico is None:
            if not atual.google_sub:
                # 1º login deste Google → carimba no anônimo atual
                atual.google_sub = sub
                if email and not _email_em_uso(s, email, atual.id):
                    atual.email = email
                if nome:
                    atual.nome = nome
                if _handle_antigo_automatico(atual.handle):
                    atual.handle = _gera_handle(s, nome=nome, email=email, exceto_id=atual.id)
                s.add(atual); s.commit()
                destino = atual
            else:
                # a sessão já é de OUTRA conta Google → cria conta nova p/ este sub
                novo = Usuario(handle=_gera_handle(s, nome=nome, email=email), google_sub=sub)
                if email and not _email_em_uso(s, email, None):
                    novo.email = email
                if nome:
                    novo.nome = nome
                s.add(novo); s.commit(); s.refresh(novo)
                destino = novo
        elif canonico.id == atual.id:
            if nome and not canonico.nome:
                canonico.nome = nome
                s.add(canonico); s.commit()
            destino = canonico  # já vinculado, nada a fazer
        else:
            if atual.google_sub:
                if atual.google_sub != sub:
                    logger.warning(
                        "[google account switch without merge] atual_id=%s destino_id=%s",
                        atual.id,
                        canonico.id,
                    )
                destino = canonico
            else:
                # Google já existe noutro usuário e o atual é anônimo/órfão → migra vínculos antes de deletar.
                try:
                    _merge_usuario_orfao(s, atual.id, canonico.id)
                    mudou = False
                    if email and not canonico.email and not _email_em_uso(s, email, canonico.id):
                        canonico.email = email
                        mudou = True
                    if nome and not canonico.nome:
                        canonico.nome = nome
                        mudou = True
                    if mudou:
                        s.add(canonico)
                    s.delete(atual)
                    s.commit()
                except SQLAlchemyError:
                    s.rollback()
                    logger.exception(
                        "[google account merge error] falha ao migrar usuario_orfao=%s para usuario_destino=%s",
                        atual.id,
                        canonico.id,
                    )
                    return RedirectResponse("/?conta=erro", status_code=303)
                destino = canonico

        # foto de perfil do Google: atualiza sempre que mudar (URLs do
        # googleusercontent expiram/rotacionam entre logins)
        picture = (info.get("picture") or "").strip()[:500]
        if picture.startswith("https://") and getattr(destino, "avatar_url", "") != picture:
            destino.avatar_url = picture
            s.add(destino); s.commit()

        request.session["uid"] = destino.id
        return RedirectResponse("/?conta=ok", status_code=303)
    except HTTPException:
        logger.exception("[google oauth callback error] falha ao concluir callback do Google")
        return RedirectResponse("/?conta=erro", status_code=303)
    except Exception:
        s.rollback()
        logger.exception("[google oauth callback error] erro inesperado após token do Google")
        return RedirectResponse("/?conta=erro", status_code=303)


@router.get("/api/auth/logout")
def logout(request: Request):
    request.session.clear()
    response = RedirectResponse("/", status_code=303)
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response
