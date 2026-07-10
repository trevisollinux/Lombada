"""
Lombada — modelos de banco e configuração global.
"""
import os
from datetime import datetime
from typing import Optional

from sqlalchemy import Column, LargeBinary, inspect, text
from sqlmodel import SQLModel, Field, UniqueConstraint, CheckConstraint, create_engine, Session

# ─── config ───────────────────────────────────────────────
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///lombada.db")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
def _int_env(nome: str, padrao: int) -> int:
    try:
        return max(1, int(os.getenv(nome, str(padrao))))
    except ValueError:
        return padrao

if DATABASE_URL.startswith("sqlite"):
    _args = {"check_same_thread": False}
else:
    # connect_timeout evita que o processo fique pendurado indefinidamente no
    # connect TCP quando o Postgres está inacessível: o connect falha rápido,
    # o startup segue e o app ainda sobe pra responder /healthz.
    _args = {"connect_timeout": _int_env("DB_CONNECT_TIMEOUT", 10)}
# Pool enxuto e saudável no Postgres do Render: conexões ociosas são recicladas
# (o Render derruba conexões paradas) e o tamanho fica alinhado ao teto de
# concorrência do app, pra não acumular conexões e memória num worker de 512 MB.
_engine_kwargs: dict = {"echo": False, "connect_args": _args}
if not DATABASE_URL.startswith("sqlite"):
    _engine_kwargs.update(
        pool_size=_int_env("DB_POOL_SIZE", 5),
        max_overflow=_int_env("DB_MAX_OVERFLOW", 5),
        pool_recycle=_int_env("DB_POOL_RECYCLE", 300),
        pool_pre_ping=True,
    )
engine = create_engine(DATABASE_URL, **_engine_kwargs)

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
    avatar_url: str           = ""          # URL efetiva (Google ou /api/avatar/{id})
    avatar_google: str        = ""          # última foto vinda do login Google
    avatar_custom: bool       = False       # True = foto enviada pelo usuário (não sobrescrever no login)
    avatar_blob: Optional[bytes] = Field(default=None, sa_column=Column(LargeBinary))
    avatar_mime: str          = ""
    is_demo:    bool          = Field(default=False, index=True)
    criado_em:  datetime      = Field(default_factory=datetime.utcnow)


class Obra(SQLModel, table=True):
    id:              Optional[int] = Field(default=None, primary_key=True)
    ol_work_key:     str           = Field(index=True, unique=True)
    titulo:          str
    autor:           str           = ""
    idioma_original: str           = ""
    ano:             Optional[int] = None
    descricao:       str           = ""
    generos_json:     str           = ""
    # Metadados opcionais de origem (nacionalidade é ambígua: só preencher com
    # dado confiável; busca e filtros funcionam mesmo com tudo vazio).
    autor_pais:          str = ""
    autor_nacionalidade: str = ""
    literatura_pais:     str = ""
    literatura_regiao:   str = ""


class PublisherGroup(SQLModel, table=True):
    """Grupo empresarial que pode reunir várias editoras."""
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    slug: str = Field(index=True, unique=True)
    website_url: str = ""
    country_code: str = Field(default="BR", index=True)
    active: bool = Field(default=True, index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Publisher(SQLModel, table=True):
    """Editora editorial; pode pertencer a um grupo empresarial."""
    id: Optional[int] = Field(default=None, primary_key=True)
    group_id: Optional[int] = Field(default=None, foreign_key="publishergroup.id", index=True)
    name: str
    normalized_name: str = Field(index=True)
    slug: str = Field(index=True, unique=True)
    website_url: str = ""
    country_code: str = Field(default="BR", index=True)
    active: bool = Field(default=True, index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Imprint(SQLModel, table=True):
    """Selo editorial pertencente a uma editora."""
    __table_args__ = (
        UniqueConstraint("publisher_id", "normalized_name", name="uq_imprint_publisher_name"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    publisher_id: int = Field(foreign_key="publisher.id", index=True)
    name: str
    normalized_name: str = Field(index=True)
    slug: str = Field(index=True)
    website_url: str = ""
    active: bool = Field(default=True, index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class PublisherAlias(SQLModel, table=True):
    """Grafia alternativa encontrada em APIs, sites ou registros antigos."""
    __table_args__ = (
        UniqueConstraint("normalized_alias", name="uq_publisheralias_normalized"),
        CheckConstraint(
            "(publisher_id IS NOT NULL) <> (imprint_id IS NOT NULL)",
            name="ck_publisheralias_one_target",
        ),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    alias: str
    normalized_alias: str = Field(index=True)
    publisher_id: Optional[int] = Field(default=None, foreign_key="publisher.id", index=True)
    imprint_id: Optional[int] = Field(default=None, foreign_key="imprint.id", index=True)
    source: str = Field(default="manual", index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class PublisherSource(SQLModel, table=True):
    """Liga um slug de coleta à editora e, opcionalmente, a um selo."""
    id: Optional[int] = Field(default=None, primary_key=True)
    source: str = Field(index=True, unique=True)
    publisher_id: int = Field(foreign_key="publisher.id", index=True)
    imprint_id: Optional[int] = Field(default=None, foreign_key="imprint.id", index=True)
    base_url: str = ""
    platform: str = ""
    active: bool = Field(default=True, index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Edicao(SQLModel, table=True):
    id:              Optional[int] = Field(default=None, primary_key=True)
    obra_id:         int           = Field(foreign_key="obra.id", index=True)
    ol_edition_key:  Optional[str] = Field(default=None, index=True)
    editora:         str           = ""  # compatibilidade/exibição atual
    editora_raw:     str           = ""  # valor original recebido da fonte
    publisher_id:    Optional[int] = Field(default=None, foreign_key="publisher.id", index=True)
    imprint_id:      Optional[int] = Field(default=None, foreign_key="imprint.id", index=True)
    tradutor:        str           = ""
    isbn:            str           = ""
    idioma:          str           = ""
    ano:             Optional[int] = None
    capa_url:        str           = ""
    paginas:         Optional[int] = None


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
    capitulo_ordem: Optional[int] = None
    nota: str = ""
    publico: bool = Field(default=False, index=True)
    spoiler: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class EdicaoCapitulo(SQLModel, table=True):
    """Sumário (tabela de capítulos) de uma edição — construído aos poucos, seja
    por leitores registrando progresso com posição (fonte='comunidade'), seja por
    sincronização de metadado externo (fonte='openlibrary'). Alimenta o
    autocomplete/seletor de capítulo no diário de leitura."""
    id: Optional[int] = Field(default=None, primary_key=True)
    edicao_id: int = Field(foreign_key="edicao.id", index=True)
    ordem: int
    titulo: str
    fonte: str = Field(default="comunidade")
    pagina_inicio: Optional[int] = None
    criado_em: datetime = Field(default_factory=datetime.utcnow)


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


class ProfileReport(SQLModel, table=True):
    """Denúncia de perfil (foto/nome/bio impróprios). Dedupe de pendentes é
    feito no endpoint — sem unique constraint pra permitir re-denúncia após
    uma dispensada."""
    id: Optional[int] = Field(default=None, primary_key=True)
    target_id: int = Field(foreign_key="usuario.id", index=True)
    reporter_id: int = Field(foreign_key="usuario.id", index=True)
    motivo: str = Field(default="other", index=True)
    detalhe: str = ""
    status: str = Field(default="pending", index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    reviewed_at: Optional[datetime] = None
    reviewed_by: Optional[str] = None


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


class Notificacao(SQLModel, table=True):
    """Atividade recebida por um usuário: alguém te seguiu, curtiu ou
    comentou sua crítica. usuario_id é quem recebe; ator_id é quem fez a
    ação. Nunca criada pra alvo/ator com is_demo=True (perfil de exemplo
    não recebe nem gera notificação -- ninguém vai ler)."""
    id: Optional[int] = Field(default=None, primary_key=True)
    usuario_id: int = Field(foreign_key="usuario.id", index=True)
    ator_id: int = Field(foreign_key="usuario.id", index=True)
    tipo: str = Field(index=True)  # "follow" | "like" | "comment"
    leitura_id: Optional[int] = Field(default=None, foreign_key="leitura.id", index=True)
    lida: bool = Field(default=False, index=True)
    criado_em: datetime = Field(default_factory=datetime.utcnow, index=True)


class ReviewComment(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    leitura_id: int = Field(foreign_key="leitura.id", index=True)
    usuario_id: int = Field(foreign_key="usuario.id", index=True)
    texto: str
    criado_em: datetime = Field(default_factory=datetime.utcnow, index=True)


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

    _add_column_if_missing("obra", "descricao", "ALTER TABLE obra ADD COLUMN descricao VARCHAR DEFAULT ''")
    _add_column_if_missing("obra", "generos_json", "ALTER TABLE obra ADD COLUMN generos_json TEXT DEFAULT '[]'")
    _add_column_if_missing("obra", "autor_pais", "ALTER TABLE obra ADD COLUMN autor_pais VARCHAR DEFAULT ''")
    _add_column_if_missing("obra", "autor_nacionalidade", "ALTER TABLE obra ADD COLUMN autor_nacionalidade VARCHAR DEFAULT ''")
    _add_column_if_missing("obra", "literatura_pais", "ALTER TABLE obra ADD COLUMN literatura_pais VARCHAR DEFAULT ''")
    _add_column_if_missing("obra", "literatura_regiao", "ALTER TABLE obra ADD COLUMN literatura_regiao VARCHAR DEFAULT ''")
    _add_column_if_missing("readingjournalentry", "capitulo_ordem", "ALTER TABLE readingjournalentry ADD COLUMN capitulo_ordem INTEGER")
    _add_column_if_missing("edicao", "paginas", "ALTER TABLE edicao ADD COLUMN paginas INTEGER")
    _add_column_if_missing("edicao", "editora_raw", "ALTER TABLE edicao ADD COLUMN editora_raw VARCHAR DEFAULT ''")
    _add_column_if_missing("edicao", "publisher_id", "ALTER TABLE edicao ADD COLUMN publisher_id INTEGER")
    _add_column_if_missing("edicao", "imprint_id", "ALTER TABLE edicao ADD COLUMN imprint_id INTEGER")
    _run_ddl(
        "backfill edicao.editora_raw",
        "UPDATE edicao SET editora_raw = editora WHERE (editora_raw IS NULL OR editora_raw = '') AND editora IS NOT NULL",
    )
    _add_column_if_missing("edicaocapitulo", "pagina_inicio", "ALTER TABLE edicaocapitulo ADD COLUMN pagina_inicio INTEGER")

    _add_column_if_missing("usuario", "handle", "ALTER TABLE usuario ADD COLUMN handle VARCHAR")
    _add_column_if_missing("usuario", "google_sub", "ALTER TABLE usuario ADD COLUMN google_sub VARCHAR")
    _add_column_if_missing("usuario", "nome", "ALTER TABLE usuario ADD COLUMN nome VARCHAR DEFAULT ''")
    _add_column_if_missing("usuario", "bio", "ALTER TABLE usuario ADD COLUMN bio VARCHAR DEFAULT ''")
    _add_column_if_missing("usuario", "avatar_url", "ALTER TABLE usuario ADD COLUMN avatar_url VARCHAR DEFAULT ''")
    _add_column_if_missing("usuario", "avatar_google", "ALTER TABLE usuario ADD COLUMN avatar_google VARCHAR DEFAULT ''")
    _add_column_if_missing("usuario", "avatar_mime", "ALTER TABLE usuario ADD COLUMN avatar_mime VARCHAR DEFAULT ''")
    if postgres:
        _add_column_if_missing("usuario", "avatar_custom", "ALTER TABLE usuario ADD COLUMN IF NOT EXISTS avatar_custom BOOLEAN NOT NULL DEFAULT false")
        _add_column_if_missing("usuario", "avatar_blob", "ALTER TABLE usuario ADD COLUMN IF NOT EXISTS avatar_blob BYTEA")
    else:
        _add_column_if_missing("usuario", "avatar_custom", "ALTER TABLE usuario ADD COLUMN avatar_custom BOOLEAN NOT NULL DEFAULT 0")
        _add_column_if_missing("usuario", "avatar_blob", "ALTER TABLE usuario ADD COLUMN avatar_blob BLOB")
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
        "CREATE INDEX IF NOT EXISTS ix_publisher_group_id ON publisher (group_id)",
        "CREATE INDEX IF NOT EXISTS ix_imprint_publisher_id ON imprint (publisher_id)",
        "CREATE INDEX IF NOT EXISTS ix_publisheralias_publisher_id ON publisheralias (publisher_id)",
        "CREATE INDEX IF NOT EXISTS ix_publisheralias_imprint_id ON publisheralias (imprint_id)",
        "CREATE INDEX IF NOT EXISTS ix_publishersource_publisher_id ON publishersource (publisher_id)",
        "CREATE INDEX IF NOT EXISTS ix_publishersource_imprint_id ON publishersource (imprint_id)",
        "CREATE INDEX IF NOT EXISTS ix_edicao_publisher_id ON edicao (publisher_id)",
        "CREATE INDEX IF NOT EXISTS ix_edicao_imprint_id ON edicao (imprint_id)",
        "CREATE INDEX IF NOT EXISTS ix_reviewreport_status ON reviewreport (status)",
        "CREATE INDEX IF NOT EXISTS ix_readingjournalentry_leitura_id ON readingjournalentry (leitura_id)",
        "CREATE INDEX IF NOT EXISTS ix_readingjournalentry_usuario_id ON readingjournalentry (usuario_id)",
        "CREATE INDEX IF NOT EXISTS ix_readingjournalentry_created_at ON readingjournalentry (created_at)",
        "CREATE INDEX IF NOT EXISTS ix_edicaocapitulo_edicao_id ON edicaocapitulo (edicao_id)",
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_edicaocapitulo_pos ON edicaocapitulo (edicao_id, ordem)",
    ]
    for ddl in ddls:
        _run_ddl("index/social", ddl)

    if postgres:
        # Inclui as tabelas CENTRAIS (usuario/obra/edicao/leitura/buscacache): se o
        # `id` delas ficou sem sequence/identity (tabela criada sem default), todo
        # INSERT estoura com "null value in column id" — é o que quebra o salvar na
        # estante. O DO-block só age quando realmente falta o default, então é
        # idempotente e não toca tabelas já saudáveis.
        core_tables = ("usuario", "obra", "edicao", "leitura", "buscacache")
        social_tables = ("catalogsuggestion", "useredition", "follow", "reviewlike", "savedreview", "reviewreport", "readingjournalentry")
        catalog_tables = ("publishergroup", "publisher", "imprint", "publisheralias", "publishersource")
        for table in core_tables + social_tables + catalog_tables:
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
