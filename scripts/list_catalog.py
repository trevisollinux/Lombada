#!/usr/bin/env python3
"""
Lista o que já foi coletado/promovido — visão rápida da base de livros.

Mostra:
  1) Resumo por editora em source_records (total, com ISBN, promovidos).
  2) Resumo do catálogo da busca (obra/edicao).
  3) Lista dos livros (filtrável por editora e limite).

Env:
- DATABASE_URL   Postgres/Neon (obrigatório).
- LIST_SLUGS     filtra por slug(s) da fonte, separados por vírgula (ex.: "todavia,record"). Vazio = todas.
- LIST_LIMIT     máx. de livros na listagem (default 500).
- LIST_ONLY_ISBN "true" lista só os que têm ISBN (default false).
"""
from __future__ import annotations

import os
import sys
from urllib.parse import urlparse

import psycopg2


def getenv_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)).strip())
    except ValueError:
        return default


def getenv_bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "y"}


def connect():
    url = os.getenv("DATABASE_URL", "").strip()
    if not url:
        raise RuntimeError("DATABASE_URL não configurado.")
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    if urlparse(url).scheme not in {"postgresql", "postgres"}:
        raise RuntimeError("DATABASE_URL deve apontar para Postgres/Neon.")
    return psycopg2.connect(url)


def main() -> int:
    slugs = [s.strip().lower() for s in os.getenv("LIST_SLUGS", "").split(",") if s.strip()]
    limit = getenv_int("LIST_LIMIT", 500)
    only_isbn = getenv_bool("LIST_ONLY_ISBN", False)
    sources = [f"publisher:{s}" for s in slugs]

    conn = connect()
    try:
        with conn.cursor() as cur:
            # 1) Resumo por editora (source_records)
            print("=" * 70)
            print("RESUMO POR EDITORA (source_records)")
            print("=" * 70)
            where = "WHERE source = ANY(%s)" if sources else ""
            params = (sources,) if sources else ()
            cur.execute(
                f"""
                SELECT source,
                       COUNT(*) AS total,
                       COUNT(*) FILTER (WHERE isbn <> '') AS com_isbn,
                       COUNT(*) FILTER (WHERE status = 'approved') AS promovidos
                FROM source_records
                {where}
                GROUP BY source
                ORDER BY total DESC
                """,
                params,
            )
            rows = cur.fetchall()
            grand = 0
            for source, total, com_isbn, promovidos in rows:
                grand += total
                print(f"  {source:28} total={total:5}  com_ISBN={com_isbn:5}  promovidos={promovidos:5}")
            print(f"  {'TOTAL':28} {grand}")

            # 2) Catálogo da busca (obra/edicao)
            print("\n" + "=" * 70)
            print("CATÁLOGO DA BUSCA (obra/edicao)")
            print("=" * 70)
            cur.execute("SELECT COUNT(*) FROM obra")
            obras = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM edicao")
            edicoes = cur.fetchone()[0]
            print(f"  obras={obras}  edicoes={edicoes}")

            # 3) Lista dos livros
            print("\n" + "=" * 70)
            print(f"LIVROS (até {limit}{', só com ISBN' if only_isbn else ''})")
            print("=" * 70)
            conds = []
            params = []
            if sources:
                conds.append("source = ANY(%s)")
                params.append(sources)
            if only_isbn:
                conds.append("isbn <> ''")
            where = ("WHERE " + " AND ".join(conds)) if conds else ""
            params.append(limit)
            cur.execute(
                f"""
                SELECT title, author, isbn, publisher, status
                FROM source_records
                {where}
                ORDER BY publisher, title
                LIMIT %s
                """,
                tuple(params),
            )
            listed = 0
            for title, author, isbn, publisher, status in cur.fetchall():
                listed += 1
                marca = "✓" if status == "approved" else " "
                print(f"  [{marca}] {(title or '')[:50]:50} | {(author or '')[:22]:22} | {isbn or '-':13} | {publisher or ''}")
            print(f"\n({listed} livros listados)")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"Erro ao listar catálogo: {exc}", file=sys.stderr)
        raise SystemExit(1)
