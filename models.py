"""
Lombada — modelos de banco e configuração global.
"""
import os
from datetime import datetime
from typing import Optional

from sqlalchemy import text
from sqlmodel import SQLModel, Field, UniqueConstraint, CheckConstraint, create_engine, Session

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
    google_sub: Optional[str] = Field(default=None, index=True, unique=True)
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
    publico:    bool            = False
    spoiler:    bool            = False
    data:       str             = ""
    criado_em:  datetime        = Field(default_factory=datetime.utcnow)


class CatalogSuggestion(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    tipo: str = Field(default="new_book", index=True)
    status: str = Field(default="pending", index=True)
    payload_json: str = ""
    target_type: Optional[str] = Field(default=None, index=True)
    target_id: Optional[int] = Field(default=None, index=True)
    user_id: Optional[int] = Field(default=None, foreign_key="usuario.id", index=True)
    user_email: Optional[str] = Field(default=None, index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    reviewed_at: Optional[datetime] = None
    reviewed_by: Optional[str] = None
    review_note: str = ""


class Follow(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint("follower_id", "following_id", name="uq_follow_pair"),
        CheckConstraint("follower_id <> following_id", name="ck_follow_not_self"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    follower_id: int = Field(foreign_key="usuario.id", index=True)
    following_id: int = Field(foreign_key="usuario.id", index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ReviewLike(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("leitura_id", "usuario_id", name="uq_reviewlike_pair"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    leitura_id: int = Field(foreign_key="leitura.id", index=True)
    usuario_id: int = Field(foreign_key="usuario.id", index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class SavedReview(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("leitura_id", "usuario_id", name="uq_savedreview_pair"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    leitura_id: int = Field(foreign_key="leitura.id", index=True)
    usuario_id: int = Field(foreign_key="usuario.id", index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ReviewReport(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("leitura_id", "usuario_id", name="uq_reviewreport_pair"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    leitura_id: int = Field(foreign_key="leitura.id", index=True)
    usuario_id: int = Field(foreign_key="usuario.id", index=True)
    motivo: str = Field(default="other", index=True)
    detalhe: str = ""
    status: str = Field(default="pending", index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    reviewed_at: Optional[datetime] = None
    reviewed_by: Optional[str] = None


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
    """Migrations retroativas (idempotentes — falham em silêncio se já aplicadas)."""
    ddls = [
        "ALTER TABLE leitura ADD COLUMN usuario_id INTEGER",
        "ALTER TABLE leitura ADD COLUMN publico BOOLEAN NOT NULL DEFAULT 0",
        "ALTER TABLE leitura ADD COLUMN spoiler BOOLEAN NOT NULL DEFAULT 0",
        "ALTER TABLE usuario ADD COLUMN handle VARCHAR",
        "ALTER TABLE usuario ADD COLUMN google_sub VARCHAR",
        "ALTER TABLE usuario ADD COLUMN nome VARCHAR DEFAULT ''",
        "ALTER TABLE usuario ALTER COLUMN email DROP NOT NULL",
        "ALTER TABLE usuario ALTER COLUMN senha_hash DROP NOT NULL",
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_usuario_google_sub ON usuario (google_sub)",
        "CREATE TABLE IF NOT EXISTS catalogsuggestion (id INTEGER PRIMARY KEY, tipo VARCHAR NOT NULL DEFAULT 'new_book', status VARCHAR NOT NULL DEFAULT 'pending', payload_json VARCHAR NOT NULL DEFAULT '', target_type VARCHAR, target_id INTEGER, user_id INTEGER, user_email VARCHAR, created_at TIMESTAMP NOT NULL, reviewed_at TIMESTAMP, reviewed_by VARCHAR, review_note VARCHAR NOT NULL DEFAULT '')",
        "CREATE INDEX IF NOT EXISTS ix_catalogsuggestion_status ON catalogsuggestion (status)",
        "CREATE INDEX IF NOT EXISTS ix_catalogsuggestion_tipo ON catalogsuggestion (tipo)",
        "CREATE INDEX IF NOT EXISTS ix_catalogsuggestion_user_id ON catalogsuggestion (user_id)",
        "CREATE TABLE IF NOT EXISTS follow (id INTEGER PRIMARY KEY, follower_id INTEGER NOT NULL, following_id INTEGER NOT NULL, created_at TIMESTAMP NOT NULL, FOREIGN KEY(follower_id) REFERENCES usuario(id), FOREIGN KEY(following_id) REFERENCES usuario(id), CONSTRAINT ck_follow_not_self CHECK (follower_id <> following_id))",
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_follow_pair ON follow (follower_id, following_id)",
        "CREATE INDEX IF NOT EXISTS ix_follow_follower_id ON follow (follower_id)",
        "CREATE INDEX IF NOT EXISTS ix_follow_following_id ON follow (following_id)",
        "CREATE TABLE IF NOT EXISTS reviewlike (id INTEGER PRIMARY KEY, leitura_id INTEGER NOT NULL, usuario_id INTEGER NOT NULL, created_at TIMESTAMP NOT NULL, FOREIGN KEY(leitura_id) REFERENCES leitura(id), FOREIGN KEY(usuario_id) REFERENCES usuario(id))",
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_reviewlike_pair ON reviewlike (leitura_id, usuario_id)",
        "CREATE INDEX IF NOT EXISTS ix_reviewlike_leitura_id ON reviewlike (leitura_id)",
        "CREATE INDEX IF NOT EXISTS ix_reviewlike_usuario_id ON reviewlike (usuario_id)",
        "CREATE TABLE IF NOT EXISTS savedreview (id INTEGER PRIMARY KEY, leitura_id INTEGER NOT NULL, usuario_id INTEGER NOT NULL, created_at TIMESTAMP NOT NULL, FOREIGN KEY(leitura_id) REFERENCES leitura(id), FOREIGN KEY(usuario_id) REFERENCES usuario(id))",
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_savedreview_pair ON savedreview (leitura_id, usuario_id)",
        "CREATE INDEX IF NOT EXISTS ix_savedreview_leitura_id ON savedreview (leitura_id)",
        "CREATE INDEX IF NOT EXISTS ix_savedreview_usuario_id ON savedreview (usuario_id)",
        "CREATE TABLE IF NOT EXISTS reviewreport (id INTEGER PRIMARY KEY, leitura_id INTEGER NOT NULL, usuario_id INTEGER NOT NULL, motivo VARCHAR NOT NULL DEFAULT 'other', detalhe VARCHAR NOT NULL DEFAULT '', status VARCHAR NOT NULL DEFAULT 'pending', created_at TIMESTAMP NOT NULL, reviewed_at TIMESTAMP, reviewed_by VARCHAR, FOREIGN KEY(leitura_id) REFERENCES leitura(id), FOREIGN KEY(usuario_id) REFERENCES usuario(id))",
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_reviewreport_pair ON reviewreport (leitura_id, usuario_id)",
        "CREATE INDEX IF NOT EXISTS ix_reviewreport_leitura_id ON reviewreport (leitura_id)",
        "CREATE INDEX IF NOT EXISTS ix_reviewreport_usuario_id ON reviewreport (usuario_id)",
        "CREATE INDEX IF NOT EXISTS ix_reviewreport_status ON reviewreport (status)",
    ]
    for ddl in ddls:
        try:
            with engine.begin() as conn:
                conn.execute(text(ddl))
        except Exception:
            pass
