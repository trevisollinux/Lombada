"""
Lombada — autenticação anônima por sessão de cookie.
"""
import random
from datetime import datetime

from sqlmodel import select, Session

from models import engine, Usuario


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
