"""Persistência do estado operacional mais recente de cada sync de editora.

O módulo não conhece os coletores. Ele apenas grava início/fim e métricas resumidas,
permitindo que workflows e futuras telas operacionais identifiquem fontes lentas,
quebradas ou com baixa cobertura.
"""
from __future__ import annotations

from typing import Any

from psycopg2.extras import Json

VALID_FINAL_STATUSES = {"success", "partial", "failed"}


def mark_sync_started(
    conn,
    source: str,
    platform: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Marca uma fonte como em execução e zera métricas da tentativa anterior."""
    if not source.strip():
        raise ValueError("source é obrigatório")

    sql = """
        INSERT INTO publisher_sync_state (
            source, platform, status, started_at, finished_at, duration_ms,
            records_collected, records_written, isbn_count, author_count,
            request_failures, error_message, metadata, updated_at
        ) VALUES (
            %(source)s, %(platform)s, 'running', NOW(), NULL, NULL,
            0, 0, 0, 0, '{}'::jsonb, NULL, %(metadata)s, NOW()
        )
        ON CONFLICT (source) DO UPDATE SET
            platform = EXCLUDED.platform,
            status = 'running',
            started_at = NOW(),
            finished_at = NULL,
            duration_ms = NULL,
            records_collected = 0,
            records_written = 0,
            isbn_count = 0,
            author_count = 0,
            request_failures = '{}'::jsonb,
            error_message = NULL,
            metadata = EXCLUDED.metadata,
            updated_at = NOW()
    """
    params = {
        "source": source.strip(),
        "platform": (platform or "").strip() or None,
        "metadata": Json(metadata or {}),
    }
    with conn.cursor() as cur:
        cur.execute(sql, params)
    conn.commit()


def mark_sync_finished(
    conn,
    source: str,
    *,
    status: str,
    duration_ms: int,
    records_collected: int = 0,
    records_written: int = 0,
    isbn_count: int = 0,
    author_count: int = 0,
    request_failures: dict[str, int] | None = None,
    error_message: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Finaliza uma execução preservando apenas métricas não negativas."""
    if not source.strip():
        raise ValueError("source é obrigatório")
    if status not in VALID_FINAL_STATUSES:
        raise ValueError(f"status inválido: {status}")

    sql = """
        UPDATE publisher_sync_state SET
            status = %(status)s,
            finished_at = NOW(),
            duration_ms = %(duration_ms)s,
            records_collected = %(records_collected)s,
            records_written = %(records_written)s,
            isbn_count = %(isbn_count)s,
            author_count = %(author_count)s,
            request_failures = %(request_failures)s,
            error_message = %(error_message)s,
            metadata = metadata || %(metadata)s::jsonb,
            updated_at = NOW()
        WHERE source = %(source)s
    """
    params = {
        "source": source.strip(),
        "status": status,
        "duration_ms": max(0, int(duration_ms)),
        "records_collected": max(0, int(records_collected)),
        "records_written": max(0, int(records_written)),
        "isbn_count": max(0, int(isbn_count)),
        "author_count": max(0, int(author_count)),
        "request_failures": Json(request_failures or {}),
        "error_message": (error_message or "").strip()[:2000] or None,
        "metadata": Json(metadata or {}),
    }
    with conn.cursor() as cur:
        cur.execute(sql, params)
        updated = cur.rowcount
    if updated != 1:
        conn.rollback()
        raise RuntimeError(
            f"publisher_sync_state não inicializado para {source!r}; "
            "chame mark_sync_started primeiro"
        )
    conn.commit()


def mark_sync_failed(
    conn,
    source: str,
    *,
    duration_ms: int,
    error: Exception | str,
    request_failures: dict[str, int] | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Atalho para encerrar uma execução com falha e mensagem normalizada."""
    mark_sync_finished(
        conn,
        source,
        status="failed",
        duration_ms=duration_ms,
        request_failures=request_failures,
        error_message=str(error),
        metadata=metadata,
    )
