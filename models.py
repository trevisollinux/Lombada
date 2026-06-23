"""
Lombada — modelos de banco e configuração global.
"""
import os
from datetime import datetime
from typing import Optional

from sqlalchemy import text
from sqlmodel import SQLModel, Field, create_engine, Session

# ─── config ───────────────────────────────────────────────
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///lombada.db")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, echo=False, connect_args=_args)

SECRET_KEY          = os.getenv("SECRET_KEY", "troque-isto-em-producao")
GOOGLE_BOOKS_API_KEY = os.getenv("GOOGLE_BOOKS_API_KEY", "")
HARDCOVER_API_KEY   = os.getenv("HARDCOVER_API_KEY", "")

# MercadoEditorial DESATIVADO (jun/2026).
# Virou Bookinfo / Metadados B2B, pago com token. Código preservado em fontes.py.
# Para reativar: setar env ME_TOKEN e religar chamadas em busca.py / fontes.py.
ME_ATIVO = bool(os.getenv("ME_TOKEN"))


# ─── tabelas ──────────────────────────────────────────────
class Usuario(SQLModel, table=True):
    id:         Optional[int] = Field(default=None, primary_key=True)
    handle:     str           = Field(index=True, unique=True)
    email:      Optional[str] = Field(default=None, index=True, unique=True)
    senha_hash: Optional[str] = None
    nome:       str           = ""
    criado_em:  datetime      = Field(default_factory=datetime.utcnow)


class Obra(SQLModel, table=True):
    id:              Optional[int] = Field(default=None, primary_key=True)
    ol_work_key:     str           = Field(index=True, unique=True)
    titulo:          str
    autor:           str           = ""
    idioma_original: str           = ""
    ano:             Optional[int] = None


class Edicao(SQLModel, table=True):
    id:              Optional[int] = Field(default=None, primary_key=True)
    obra_id:         int           = Field(foreign_key="obra.id", index=True)
    ol_edition_key:  Optional[str] = Field(default=None, index=True)
    editora:         str           = ""
    tradutor:        str           = ""
    isbn:            str           = ""
    idioma:          str           = ""
    ano:             Optional[int] = None
    capa_url:        str           = ""


class Leitura(SQLModel, table=True):
    id:         Optional[int]   = Field(default=None, primary_key=True)
    edicao_id:  int             = Field(foreign_key="edicao.id", index=True)
    usuario_id: Optional[int]   = Field(default=None, foreign_key="usuario.id", index=True)
    status:     str             = "Lido"
    nota:       Optional[float] = None
    relato:     str             = ""
    data:       str             = ""
    criado_em:  datetime        = Field(default_factory=datetime.utcnow)


class BuscaCache(SQLModel, table=True):
    id:               Optional[int] = Field(default=None, primary_key=True)
    query:            str           = Field(index=True)
    query_norm:       str           = Field(index=True)
    resultados_json:  str           = ""
    criado_em:        datetime      = Field(default_factory=datetime.utcnow)


# ─── banco ────────────────────────────────────────────────
def get_session():
    with Session(engine) as s:
        yield s


def migrar():
    """Migrations retroativas (idempotentes — falharam silenciosamente se já existem)."""
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
