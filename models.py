"""
Lombada — modelos de banco e configuração global.
"""
import os
from datetime import datetime
from typing import Optional

from sqlalchemy import inspect, text
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
    bio:        str           = ""
    is_demo:    bool          = Field(default=False, index=True)
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
    is_demo:    bool            = Field(default=False, index=True)
    data:       str             = ""
    criado_em:  datetime        = Field(default_factory=datetime.utcnow)


class ReadingJournalEntry(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    leitura_id: int = Field(foreign_key="leitura.id", index=True)
    usuario_id: int = Field(foreign_key="usuario.id", index=True)
    progresso_tipo: str = Field(default="livre", index=True)
    pagina: Optional[int] = None
    porcentagem: Optional[int] = None
    capitulo: str = ""
    nota: str = ""
    publico: bool = Field(default=False, index=True)
    spoiler: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class UserEdition(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("usuario_id", "edicao_id", name="uq_useredition_pair"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    usuario_id: int = Field(foreign_key="usuario.id", index=True)
    edicao_id: int = Field(foreign_key="edicao.id", index=True)
    tenho: bool = Field(default=False)
    quero: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


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


def _is_postgres() -> bool:
    return engine.dialect.name.startswith("postgres")


def _has_column(table: str, column: str) -> bool:
    try:
        return column in {c["name"] for c in inspect(engine).get_columns(table)}
    except Exception as exc:
        print(f"[migration inspect/error] {table}.{column} -> {exc}")
        return False


def _run_ddl(label: str, ddl: str, *, ignore_existing: bool = False):
    try:
        with engine.begin() as conn:
            conn.execute(text(ddl))
    except Exception as exc:
        msg = str(exc).lower()
        expected_existing = (
            "duplicate column" in msg
            or "already exists" in msg
            or "duplicate_object" in msg
            or "duplicate_table" in msg
        )
        if ignore_existing and expected_existing:
            print(f"[migration skipped] {label} -> {exc}")
            return
        print(f"[migration error] {label}: {ddl[:120]} -> {exc}")


def _add_column_if_missing(table: str, column: str, ddl: str):
    if _has_column(table, column):
        return
    _run_ddl(f"add {table}.{column}", ddl, ignore_existing=True)


def migrar():
    """Migrações retroativas idempotentes com log de diagnóstico."""
    postgres = _is_postgres()

    _add_column_if_missing("leitura", "usuario_id", "ALTER TABLE leitura ADD COLUMN usuario_id INTEGER")
    if postgres:
        _add_column_if_missing("leitura", "publico", "ALTER TABLE leitura ADD COLUMN IF NOT EXISTS publico BOOLEAN NOT NULL DEFAULT false")
        _add_column_if_missing("leitura", "spoiler", "ALTER TABLE leitura ADD COLUMN IF NOT EXISTS spoiler BOOLEAN NOT NULL DEFAULT false")
    else:
        _add_column_if_missing("leitura", "publico", "ALTER TABLE leitura ADD COLUMN publico BOOLEAN NOT NULL DEFAULT 0")
        _add_column_if_missing("leitura", "spoiler", "ALTER TABLE leitura ADD COLUMN spoiler BOOLEAN NOT NULL DEFAULT 0")

    _add_column_if_missing("usuario", "handle", "ALTER TABLE usuario ADD COLUMN handle VARCHAR")
    _add_column_if_missing("usuario", "google_sub", "ALTER TABLE usuario ADD COLUMN google_sub VARCHAR")
    _add_column_if_missing("usuario", "nome", "ALTER TABLE usuario ADD COLUMN nome VARCHAR DEFAULT ''")
    _add_column_if_missing("usuario", "bio", "ALTER TABLE usuario ADD COLUMN bio VARCHAR DEFAULT ''")
    if postgres:
        _add_column_if_missing("usuario", "is_demo", "ALTER TABLE usuario ADD COLUMN IF NOT EXISTS is_demo BOOLEAN NOT NULL DEFAULT false")
        _add_column_if_missing("leitura", "is_demo", "ALTER TABLE leitura ADD COLUMN IF NOT EXISTS is_demo BOOLEAN NOT NULL DEFAULT false")
    else:
        _add_column_if_missing("usuario", "is_demo", "ALTER TABLE usuario ADD COLUMN is_demo BOOLEAN NOT NULL DEFAULT 0")
        _add_column_if_missing("leitura", "is_demo", "ALTER TABLE leitura ADD COLUMN is_demo BOOLEAN NOT NULL DEFAULT 0")

    if postgres:
        _run_ddl("usuario.email nullable", "ALTER TABLE usuario ALTER COLUMN email DROP NOT NULL")
        _run_ddl("usuario.senha_hash nullable", "ALTER TABLE usuario ALTER COLUMN senha_hash DROP NOT NULL")

    ddls = [
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_usuario_google_sub ON usuario (google_sub)",
        "CREATE INDEX IF NOT EXISTS ix_usuario_is_demo ON usuario (is_demo)",
        "CREATE INDEX IF NOT EXISTS ix_leitura_is_demo ON leitura (is_demo)",
        "CREATE INDEX IF NOT EXISTS ix_catalogsuggestion_status ON catalogsuggestion (status)",
        "CREATE INDEX IF NOT EXISTS ix_catalogsuggestion_tipo ON catalogsuggestion (tipo)",
        "CREATE INDEX IF NOT EXISTS ix_catalogsuggestion_user_id ON catalogsuggestion (user_id)",
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_follow_pair ON follow (follower_id, following_id)",
        "CREATE INDEX IF NOT EXISTS ix_follow_follower_id ON follow (follower_id)",
        "CREATE INDEX IF NOT EXISTS ix_follow_following_id ON follow (following_id)",
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_reviewlike_pair ON reviewlike (leitura_id, usuario_id)",
        "CREATE INDEX IF NOT EXISTS ix_reviewlike_leitura_id ON reviewlike (leitura_id)",
        "CREATE INDEX IF NOT EXISTS ix_reviewlike_usuario_id ON reviewlike (usuario_id)",
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_savedreview_pair ON savedreview (leitura_id, usuario_id)",
        "CREATE INDEX IF NOT EXISTS ix_savedreview_leitura_id ON savedreview (leitura_id)",
        "CREATE INDEX IF NOT EXISTS ix_savedreview_usuario_id ON savedreview (usuario_id)",
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_reviewreport_pair ON reviewreport (leitura_id, usuario_id)",
        "CREATE INDEX IF NOT EXISTS ix_reviewreport_leitura_id ON reviewreport (leitura_id)",
        "CREATE INDEX IF NOT EXISTS ix_reviewreport_usuario_id ON reviewreport (usuario_id)",
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_useredition_pair ON useredition (usuario_id, edicao_id)",
        "CREATE INDEX IF NOT EXISTS ix_useredition_usuario_id ON useredition (usuario_id)",
        "CREATE INDEX IF NOT EXISTS ix_useredition_edicao_id ON useredition (edicao_id)",
        "CREATE INDEX IF NOT EXISTS ix_reviewreport_status ON reviewreport (status)",
        "CREATE INDEX IF NOT EXISTS ix_readingjournalentry_leitura_id ON readingjournalentry (leitura_id)",
        "CREATE INDEX IF NOT EXISTS ix_readingjournalentry_usuario_id ON readingjournalentry (usuario_id)",
        "CREATE INDEX IF NOT EXISTS ix_readingjournalentry_created_at ON readingjournalentry (created_at)",
    ]
    for ddl in ddls:
        _run_ddl("index/social", ddl)

    if postgres:
        for table in ("catalogsuggestion", "useredition", "follow", "reviewlike", "savedreview", "reviewreport", "readingjournalentry"):
            _run_ddl(
                f"{table}.id identity",
                f"""
                DO $$
                BEGIN
                  IF EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema = current_schema()
                      AND table_name = '{table}'
                      AND column_name = 'id'
                      AND column_default IS NULL
                      AND identity_generation IS NULL
                  ) THEN
                    ALTER TABLE {table} ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY;
                  END IF;
                END $$;
                """,
            )
