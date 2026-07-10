#!/usr/bin/env python3
"""Inicializa tabelas de ingestão usadas pelos syncs de catálogo.

Idempotente e seguro para bancos novos: executa o DDL existente de
sql/001_source_records.sql e cria as tabelas auxiliares sem apagar dados.
Usa somente DATABASE_URL.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from urllib.parse import urlparse

import psycopg2

ROOT = Path(__file__).resolve().parents[1]
SOURCE_RECORDS_SQL = ROOT / "sql" / "001_source_records.sql"


PUBLISHER_SYNC_STATE_SQL = """
CREATE TABLE IF NOT EXISTS publisher_sync_state (
    source text PRIMARY KEY,
    platform text,
    status text NOT NULL DEFAULT 'idle',
    started_at timestamptz,
    finished_at timestamptz,
    duration_ms bigint,
    records_collected integer NOT NULL DEFAULT 0,
    records_written integer NOT NULL DEFAULT 0,
    isbn_count integer NOT NULL DEFAULT 0,
    author_count integer NOT NULL DEFAULT 0,
    request_failures jsonb NOT NULL DEFAULT '{}'::jsonb,
    error_message text,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    updated_at timestamptz NOT NULL DEFAULT NOW(),
    CONSTRAINT publisher_sync_state_status_check
        CHECK (status IN ('idle', 'running', 'success', 'partial', 'failed'))
)
"""


def normalize_database_url(database_url: str) -> str:
    if database_url.startswith("postgres://"):
        return database_url.replace("postgres://", "postgresql://", 1)
    return database_url


def connect_database():
    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url:
        raise RuntimeError("DATABASE_URL não configurado.")
    normalized_url = normalize_database_url(database_url)
    parsed = urlparse(normalized_url)
    if parsed.scheme not in {"postgresql", "postgres"}:
        raise RuntimeError("DATABASE_URL deve apontar para Postgres.")
    conn = psycopg2.connect(normalized_url)
    with conn.cursor() as cur:
        cur.execute("SELECT 1")
        cur.fetchone()
    print("conexão OK")
    return conn


def _relation_exists(cur, table_name: str) -> bool:
    cur.execute("SELECT to_regclass(%s)", (f"public.{table_name}",))
    return cur.fetchone()[0] is not None


def ensure_source_records(conn) -> None:
    sql = SOURCE_RECORDS_SQL.read_text(encoding="utf-8")
    with conn.cursor() as cur:
        existed = _relation_exists(cur, "source_records")
        cur.execute(sql)
    conn.commit()
    print(f"source_records {'já existia' if existed else 'criada'}")


def ensure_publisher_dead_ids(conn) -> None:
    with conn.cursor() as cur:
        existed = _relation_exists(cur, "publisher_dead_ids")
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS publisher_dead_ids (
                source text NOT NULL,
                external_id text NOT NULL,
                first_seen_at timestamptz NOT NULL DEFAULT NOW(),
                PRIMARY KEY (source, external_id)
            )
            """
        )
    conn.commit()
    print(f"publisher_dead_ids {'já existia' if existed else 'criada'}")


def ensure_publisher_sync_state(conn) -> None:
    """Cria o resumo operacional mais recente de cada fonte/editora."""
    with conn.cursor() as cur:
        existed = _relation_exists(cur, "publisher_sync_state")
        cur.execute(PUBLISHER_SYNC_STATE_SQL)
    conn.commit()
    print(f"publisher_sync_state {'já existia' if existed else 'criada'}")


def init_ingestion_tables() -> None:
    conn = connect_database()
    try:
        ensure_source_records(conn)
        ensure_publisher_dead_ids(conn)
        ensure_publisher_sync_state(conn)
    finally:
        conn.close()


def main() -> int:
    try:
        init_ingestion_tables()
    except Exception as exc:  # noqa: BLE001 - script operacional deve logar erro claro no Actions
        print(f"erro ao inicializar tabelas de ingestão: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
