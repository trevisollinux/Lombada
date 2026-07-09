#!/usr/bin/env python3
"""
Promove registros de source_records para o catálogo do app (obra/edicao).

A busca do app já lê obra/edicao (via _buscar_catalogo_local), então promover
faz os livros coletados (Record etc.) aparecerem na busca — fechando o circuito
ingestão -> catálogo -> busca.

Critério de elegibilidade (configurável por env):
- title e isbn não vazios
- confidence_score >= PROMOTE_MIN_CONFIDENCE (default 0.5)
- status em PROMOTE_STATUSES (default "pending,approved")

Idempotente: se já existe uma edicao com aquele ISBN, pula. Marca os promovidos
como status='approved' em source_records.

Env:
- DATABASE_URL            Postgres (obrigatório, exceto DRY_RUN)
- DRY_RUN                 true/1/yes -> só mostra, não grava
- PROMOTE_MIN_CONFIDENCE  default 0.5
- PROMOTE_STATUSES        default "pending,approved"
- PROMOTE_LIMIT           default 1000
"""
from __future__ import annotations

import hashlib
import os
import re
import sys
from urllib.parse import urlparse

import psycopg2

from init_ingestion_tables import ensure_source_records


def getenv_bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "y"}


def getenv_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)).strip())
    except ValueError:
        return default


def getenv_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)).strip())
    except ValueError:
        return default


def normalize_isbn(value: str) -> str:
    c = re.sub(r"[^0-9Xx]", "", str(value or "")).upper()
    if len(c) == 13 and c.isdigit():
        return c
    if len(c) == 10 and re.fullmatch(r"[0-9]{9}[0-9X]", c):
        return c
    return ""


def connect():
    url = os.getenv("DATABASE_URL", "").strip()
    if not url:
        raise RuntimeError("DATABASE_URL não configurado. Use DRY_RUN=true para simular sem banco.")
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    if urlparse(url).scheme not in {"postgresql", "postgres"}:
        raise RuntimeError("DATABASE_URL deve apontar para Postgres.")
    return psycopg2.connect(url)


def work_key(titulo: str, autor: str) -> str:
    base = (titulo or "").strip().lower() + "|" + (autor or "").strip().lower()
    return "src:" + hashlib.sha1(base.encode("utf-8")).hexdigest()[:24]


def find_obra(cur, titulo: str, autor: str):
    if autor.strip():
        cur.execute(
            "SELECT id FROM obra WHERE lower(titulo) = lower(%s) AND lower(autor) = lower(%s) LIMIT 1",
            (titulo, autor),
        )
    else:
        cur.execute("SELECT id FROM obra WHERE lower(titulo) = lower(%s) LIMIT 1", (titulo,))
    row = cur.fetchone()
    return row[0] if row else None


def _tem_coluna(cur, tabela: str, coluna: str) -> bool:
    cur.execute(
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_name=%s AND column_name=%s LIMIT 1",
        (tabela, coluna),
    )
    return cur.fetchone() is not None


_OBRA_TEXT_DEFAULT_COLUMNS = (
    "descricao",
    "generos_json",
    "autor_pais",
    "autor_nacionalidade",
    "literatura_pais",
    "literatura_regiao",
)


def _safe_descricao(descricao: str) -> str:
    return (descricao or "").strip()[:2000]


def ensure_catalog_schema(conn, dry_run: bool = False) -> None:
    """Normaliza colunas textuais obrigatórias de obra para o promote cru.

    O model SQLModel usa defaults Python, mas este script faz INSERT SQL direto.
    Bancos já criados podem ter as colunas NOT NULL sem server default; portanto
    backfillamos NULLs existentes e instalamos DEFAULT '' de forma idempotente.
    """
    with conn.cursor() as cur:
        for coluna in _OBRA_TEXT_DEFAULT_COLUMNS:
            if not _tem_coluna(cur, "obra", coluna):
                continue
            if dry_run:
                continue
            cur.execute(f"UPDATE obra SET {coluna}='' WHERE {coluna} IS NULL")
            cur.execute(f"ALTER TABLE obra ALTER COLUMN {coluna} SET DEFAULT ''")
    if not dry_run:
        conn.commit()

_AUTOR_LABEL_RE = re.compile(r"Autor(?:\(a\)|es)?\s*[:\-]\s*([A-ZÀ-Ý][^\n|·•]{2,60})")


def extract_author_from_text(text: str) -> str:
    """Mesma heurística de scripts/sync_publishers.py (duplicada aqui de
    propósito pra este script não depender de bs4/requests): reconhece um
    "Autor: Fulano" solto no texto da descrição."""
    match = _AUTOR_LABEL_RE.search(text or "")
    return match.group(1).strip() if match else ""


def backfill_source_record_authors(conn, dry_run: bool) -> int:
    """Re-deriva o autor de source_records de editora que ficaram sem autor
    porque o coletor usava um campo fraco (ex.: 'vendor' do Shopify, que é o
    selo/editora, não o autor — ver scripts/sync_publishers.py). Não bate
    rede: usa só a descrição já salva em raw_json na coleta original.

    Roda antes da promoção normal, então o autor re-derivado já entra no lote
    que o promote() abaixo processa — inclusive pra obras JÁ promovidas
    (branch 'ja_existiam' de promote(), que faz UPDATE obra SET autor=...)."""
    preenchidos = 0
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, raw_json->>'description' FROM source_records "
            "WHERE source LIKE %s AND btrim(coalesce(author, '')) = '' "
            "AND coalesce(raw_json->>'description', '') <> ''",
            ("publisher:%",),
        )
        rows = cur.fetchall()
        for sr_id, descricao in rows:
            autor = extract_author_from_text(descricao)
            if not autor:
                continue
            preenchidos += 1
            if not dry_run:
                cur.execute("UPDATE source_records SET author=%s, updated_at=NOW() WHERE id=%s", (autor, sr_id))
    if not dry_run:
        conn.commit()
    return preenchidos


def _preencher_descricao(cur, obra_id: int, descricao: str) -> bool:
    """Grava a descrição na obra só quando está vazia — nunca sobrescreve. Corta em
    2000 chars pra não guardar página inteira."""
    descricao = (descricao or "").strip()[:2000]
    if not descricao:
        return False
    cur.execute(
        "UPDATE obra SET descricao=%s WHERE id=%s AND (descricao IS NULL OR btrim(descricao)='')",
        (descricao, obra_id),
    )
    return bool(cur.rowcount)


def promote(conn, rows, dry_run: bool) -> dict:
    stats = {"candidatos": len(rows), "promovidos": 0, "ja_existiam": 0, "obras_criadas": 0,
             "autores_preenchidos": 0, "descricoes_preenchidas": 0}
    with conn.cursor() as cur:
        # A coluna obra.descricao é criada pelo migrar() do app (no deploy). Enquanto
        # não existir (janela entre merge e deploy), pulamos a escrita sem quebrar.
        tem_descricao = _tem_coluna(cur, "obra", "descricao")
        for r in rows:
            sr_id, titulo, autor, isbn_raw, editora, ano, capa, descricao = r
            isbn = normalize_isbn(isbn_raw)
            if not titulo or not isbn:
                continue

            cur.execute("SELECT id, obra_id FROM edicao WHERE isbn = %s LIMIT 1", (isbn,))
            edic = cur.fetchone()
            if edic:
                stats["ja_existiam"] += 1
                if not dry_run:
                    # Backfill: se a obra ligada está sem autor e agora temos um
                    # (ex.: Editora 34 re-scrapeada com o extrator de autor), preenche.
                    # Só preenche quando está vazio — nunca sobrescreve autor bom.
                    if autor.strip():
                        cur.execute(
                            "UPDATE obra SET autor=%s WHERE id=%s AND (autor IS NULL OR btrim(autor)='')",
                            (autor.strip(), edic[1]),
                        )
                        if cur.rowcount:
                            stats["autores_preenchidos"] += 1
                    if tem_descricao and _preencher_descricao(cur, edic[1], descricao):
                        stats["descricoes_preenchidas"] += 1
                    cur.execute("UPDATE source_records SET status='approved', updated_at=NOW() WHERE id=%s", (sr_id,))
                continue

            if dry_run:
                stats["promovidos"] += 1
                continue

            obra_id = find_obra(cur, titulo, autor)
            if obra_id is None:
                cur.execute(
                    "INSERT INTO obra ("
                    "ol_work_key, titulo, autor, idioma_original, ano, descricao, "
                    "generos_json, autor_pais, autor_nacionalidade, literatura_pais, literatura_regiao"
                    ") VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id",
                    (
                        work_key(titulo, autor), titulo, autor, "", ano,
                        _safe_descricao(descricao), "", "", "", "", "",
                    ),
                )
                obra_id = cur.fetchone()[0]
                stats["obras_criadas"] += 1

            cur.execute(
                "INSERT INTO edicao (obra_id, ol_edition_key, editora, tradutor, isbn, idioma, ano, capa_url) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                (obra_id, "isbn:" + isbn, editora or "", "", isbn, "Português", ano, capa or ""),
            )
            if tem_descricao and _preencher_descricao(cur, obra_id, descricao):
                stats["descricoes_preenchidas"] += 1
            cur.execute("UPDATE source_records SET status='approved', updated_at=NOW() WHERE id=%s", (sr_id,))
            stats["promovidos"] += 1
    if not dry_run:
        conn.commit()
    return stats


def main() -> int:
    dry_run = getenv_bool("DRY_RUN", False)
    min_conf = getenv_float("PROMOTE_MIN_CONFIDENCE", 0.5)
    limite = getenv_int("PROMOTE_LIMIT", 1000)
    statuses = [s.strip() for s in os.getenv("PROMOTE_STATUSES", "pending,approved").split(",") if s.strip()]

    print(f"DRY_RUN={dry_run}  min_confidence={min_conf}  statuses={statuses}  limite={limite}")

    if dry_run and not os.getenv("DATABASE_URL", "").strip():
        print("Sem DATABASE_URL e DRY_RUN: nada a fazer (configure DATABASE_URL para consultar).")
        return 0

    conn = connect()
    try:
        ensure_source_records(conn)
        ensure_catalog_schema(conn, dry_run)
        with conn.cursor() as cur:
            # Os workflows de sync rodam em PARALELO (grupos de concorrência
            # distintos no Actions) e todos chamam este script no fim. Dois
            # promotes simultâneos duplicariam obras: find_obra + INSERT não é
            # atômico. O advisory lock serializa no próprio Postgres — o
            # segundo processo espera o primeiro terminar (~2-3 min) e segue.
            # Lock de sessão: liberado automaticamente no conn.close()/queda.
            cur.execute("SELECT pg_advisory_lock(hashtext('lombada_promote_source_records'))")
        autores_rederivados = backfill_source_record_authors(conn, dry_run)
        print(f"autores re-derivados da descrição (sem rede): {autores_rederivados}")
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, title, author, isbn, publisher, publication_year, thumbnail,
                       btrim(coalesce(raw_json->>'description', '')) AS descricao
                FROM source_records
                WHERE title <> '' AND isbn <> ''
                  AND confidence_score >= %s
                  AND status = ANY(%s)
                -- Pendentes sempre antes de aprovados: aprovados nunca saem do pool
                -- (status permanece 'approved' pra sempre) e, sem isso, editoras com
                -- confidence_score mais baixo (ex.: sitemap sem thumbnail/autor) ficam
                -- pra sempre atrás dos aprovados de score maior no LIMIT, e nunca são
                -- promovidas (visto em Alta Books/L&PM/Boitempo/Edusp: 0 promovidos
                -- mesmo com boa cobertura de ISBN).
                ORDER BY (status = 'pending') DESC, confidence_score DESC, last_seen_at DESC
                LIMIT %s
                """,
                (min_conf, statuses, limite),
            )
            rows = cur.fetchall()
        stats = promote(conn, rows, dry_run)
    finally:
        conn.close()

    print(
        f"candidatos={stats['candidatos']} promovidos={stats['promovidos']} "
        f"ja_existiam={stats['ja_existiam']} obras_criadas={stats['obras_criadas']} "
        f"autores_preenchidos={stats['autores_preenchidos']} "
        f"descricoes_preenchidas={stats['descricoes_preenchidas']}"
    )
    if dry_run:
        print("DRY_RUN: nada gravado.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"Erro na promoção: {exc}", file=sys.stderr)
        raise SystemExit(1)
