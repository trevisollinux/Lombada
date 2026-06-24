"""
Lombada — autenticação.

Dois modos, na mesma sessão de cookie:
  • anônimo  — 1ª visita já cria um Usuario com handle fofo (sem cadastro).
  • Google   — OAuth 2.0 (Authorization Code), vincula o Google ao usuário
               anônimo atual; se aquele Google já existe noutro usuário,
               MIGRA as leituras e descarta o órfão (merge de estante).

O id_token vem direto do token endpoint do Google por canal TLS server-to-server,
então validamos aud/iss/exp (sem precisar de verificação de assinatura/JWKS).
"""
import os
import json
import time
import base64
import random
import secrets
from datetime import datetime
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlmodel import select, Session

from models import Usuario, Leitura, get_session


# ─── config Google ────────────────────────────────────────
GOOGLE_CLIENT_ID     = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REDIRECT_URI  = os.getenv(
    "GOOGLE_REDIRECT_URI",
    "https://lombada.onrender.com/api/auth/google/callback",
)
GOOGLE_AUTH  = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN = "https://oauth2.googleapis.com/token"
_TIMEOUT = 12.0


# ─── usuário anônimo (handle fofo) ────────────────────────
_BICHO = [
    "capivara", "coruja", "raposa", "tatu", "lontra", "perereca", "jaguatirica",
    "tucano", "sagui", "quati", "arara", "preguica", "tamandua", "bemtevi",
]
_ADJ = [
    "sonolenta", "curiosa", "saudosa", "serena", "faminta", "valente", "distraida",
    "noturna", "errante", "teimosa", "sonhadora", "melancolica", "leitora",
    "perdida", "silenciosa", "boemia", "antiga",
]


def _gera_handle(s: Session) -> str:
    for _ in range(40):
        h = f"{random.choice(_BICHO)}-{random.choice(_ADJ)}-{random.randint(10, 999)}"
        if not s.exec(select(Usuario).where(Usuario.handle == h)).first():
            return h
    return f"leitor-{int(datetime.utcnow().timestamp())}"


def criar_anonimo(s: Session) -> Usuario:
    u = Usuario(handle=_gera_handle(s))
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
def _decode_jwt_payload(token: str) -> dict:
    """Decodifica o payload do JWT (sem verificar assinatura — canal TLS confiável)."""
    parts = (token or "").split(".")
    if len(parts) != 3:
        raise HTTPException(400, "id_token malformado")
    seg = parts[1] + "=" * (-len(parts[1]) % 4)
    try:
        return json.loads(base64.urlsafe_b64decode(seg))
    except Exception:
        raise HTTPException(400, "id_token ilegível")


def _claims_validas(id_token: str) -> dict:
    claims = _decode_jwt_payload(id_token)
    if claims.get("aud") != GOOGLE_CLIENT_ID:
        raise HTTPException(400, "id_token: aud não confere")
    if claims.get("iss") not in ("accounts.google.com", "https://accounts.google.com"):
        raise HTTPException(400, "id_token: iss inválido")
    try:
        exp = float(claims.get("exp", 0))
    except (TypeError, ValueError):
        exp = 0
    if exp < time.time():
        raise HTTPException(400, "id_token expirado")
    if not claims.get("sub"):
        raise HTTPException(400, "id_token sem sub")
    return claims


def _email_em_uso(s: Session, email: str, exceto_id) -> bool:
    if not email:
        return False
    outro = s.exec(select(Usuario).where(Usuario.email == email)).first()
    return bool(outro and outro.id != exceto_id)


def _mover_leituras(s: Session, de: int, para: int) -> int:
    if de == para:
        return 0
    rows = s.exec(select(Leitura).where(Leitura.usuario_id == de)).all()
    for l in rows:
        l.usuario_id = para
        s.add(l)
    if rows:
        s.commit()
    return len(rows)


# ─── rotas Google OAuth ───────────────────────────────────
router = APIRouter()


@router.get("/api/auth/google/login")
def google_login(request: Request):
    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        raise HTTPException(503, "SSO do Google não configurado")
    state = secrets.token_urlsafe(24)
    request.session["oauth_state"] = state
    params = {
        "client_id":     GOOGLE_CLIENT_ID,
        "redirect_uri":  GOOGLE_REDIRECT_URI,
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
        raise HTTPException(400, "state inválido (possível CSRF)")
    if not code:
        raise HTTPException(400, "código de autorização ausente")

    # troca o code por tokens (server-to-server)
    try:
        with httpx.Client(timeout=_TIMEOUT) as c:
            r = c.post(GOOGLE_TOKEN, data={
                "code":          code,
                "client_id":     GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "redirect_uri":  GOOGLE_REDIRECT_URI,
                "grant_type":    "authorization_code",
            })
            r.raise_for_status()
            tok = r.json()
    except Exception as e:
        raise HTTPException(502, f"falha ao trocar token com o Google: {e}")

    claims = _claims_validas(tok.get("id_token") or "")
    sub   = claims["sub"]
    email = (claims.get("email") or "").strip()
    nome  = (claims.get("name") or "").strip()

    # ─── merge de estante ───
    canonico = s.exec(select(Usuario).where(Usuario.google_sub == sub)).first()
    atual = usuario_sessao(request, s)

    if canonico is None:
        if atual.google_sub is None:
            # 1º login deste Google → carimba no anônimo atual
            atual.google_sub = sub
            if email and not _email_em_uso(s, email, atual.id):
                atual.email = email
            if nome and not atual.nome:
                atual.nome = nome
            s.add(atual); s.commit()
            destino = atual
        else:
            # a sessão já é de OUTRA conta Google → cria conta nova p/ este sub
            novo = Usuario(handle=_gera_handle(s), google_sub=sub)
            if email and not _email_em_uso(s, email, None):
                novo.email = email
            if nome:
                novo.nome = nome
            s.add(novo); s.commit(); s.refresh(novo)
            destino = novo
    elif canonico.id == atual.id:
        destino = canonico  # já vinculado, nada a fazer
    else:
        # Google já existe noutro usuário → migra leituras do atual e descarta o órfão
        _mover_leituras(s, atual.id, canonico.id)
        if email and not canonico.email and not _email_em_uso(s, email, canonico.id):
            canonico.email = email
            s.add(canonico); s.commit()
        s.delete(atual); s.commit()
        destino = canonico

    request.session["uid"] = destino.id
    return RedirectResponse("/?conta=ok", status_code=303)


@router.get("/api/auth/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/", status_code=303)
