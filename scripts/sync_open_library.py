#!/usr/bin/env python3
"""
Sincroniza resultados de livros da Open Library para a tabela source_records.

Configuração por variáveis de ambiente:
- DATABASE_URL: conexão Postgres/Neon obrigatória.
- SYNC_TERMS: termos separados por vírgula.
- OPEN_LIBRARY_LIMIT: resultados por termo (default: 10).
"""
from __future__ import annotations

import os
import sys
from typing import Any
from urllib.parse import urlparse

import psycopg2
from psycopg2.extras import Json
import requests

OPEN_LIBRARY_SEARCH_URL = "https://openlibrary.org/search.json"
SOURCE = "open_library"
DEFAULT_LIMIT = 10
REQUEST_TIMEOUT_SECONDS = 20
OPEN_LIBRARY_FIELDS = (
    "key,title,author_name,first_publish_year,isbn,publisher,cover_i,edition_key,editions"
)
OPEN_LIBRARY_HEADERS = {
    "Accept": "application/json",
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
    "User-Agent": "LombadaOpenLibrarySync/0.1 (+https://lombada.onrender.com)",
}


def getenv_list(name: str, default: str = "") -> list[str]:
    value = os.getenv(name, default)
    return [item.strip() for item in value.split(",") if item.strip()]


def getenv_int(name: str, default: int, minimum: int = 1, maximum: int | None = None) -> int:
    raw_value = os.getenv(name, str(default)).strip()
    try:
        value = int(raw_value)
    except ValueError:
        value = default
    value = max(minimum, value)
    if maximum is not None:
        value = min(value, maximum)
    return value


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
        raise RuntimeError("DATABASE_URL deve apontar para Postgres/Neon.")
    return psycopg2.connect(normalized_url)


def first_item(value: Any) -> str:
    if isinstance(value, list):
        return str(value[0]).strip() if value else ""
    if value is None:
        return ""
    return str(value).strip()


def int_or_none(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def build_thumbnail(cover_i: Any) -> str:
    cover_id = int_or_none(cover_i)
    if cover_id is None:
        return ""
    return f"https://covers.openlibrary.org/b/id/{cover_id}-M.jpg"


def confidence_score(normalized: dict[str, Any]) -> float:
    score = 0.2
    if normalized["external_id"]:
        score += 0.1
    if normalized["title"]:
        score += 0.2
    if normalized["author"]:
        score += 0.15
    if normalized["isbn"]:
        score += 0.2
    if normalized["publisher"]:
        score += 0.05
    if normalized["publication_year"] is not None:
        score += 0.05
    if normalized["thumbnail"]:
        score += 0.03
    if normalized["permalink"]:
        score += 0.02
    return round(min(score, 1.0), 4)


def normalize_item(item: dict[str, Any], search_term: str) -> dict[str, Any]:
    key = str(item.get("key") or "").strip()
    normalized = {
        "source": SOURCE,
        "external_id": key,
        "status": "pending",
        "title": str(item.get("title") or "").strip(),
        "author": first_item(item.get("author_name")),
        "isbn": first_item(item.get("isbn")),
        "publisher": first_item(item.get("publisher")),
        "publication_year": int_or_none(item.get("first_publish_year")),
        "price": None,
        "currency_id": "",
        "permalink": f"https://openlibrary.org{key}" if key else "",
        "thumbnail": build_thumbnail(item.get("cover_i")),
        "category_id": "",
        "search_term": search_term,
    }
    normalized["confidence_score"] = confidence_score(normalized)
    return normalized


def fetch_results(term: str, limit: int) -> list[dict[str, Any]]:
    params = {
        "q": term,
        "limit": limit,
        "lang": "pt",
        "fields": OPEN_LIBRARY_FIELDS,
    }
    response = requests.get(
        OPEN_LIBRARY_SEARCH_URL,
        params=params,
        headers=OPEN_LIBRARY_HEADERS,
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    payload = response.json()
    return payload.get("docs") or []


def upsert_records(conn, records: list[tuple[dict[str, Any], dict[str, Any]]]) -> int:
    sql = """
        INSERT INTO source_records (
            source, external_id, status, title, author, isbn, publisher, publication_year,
            price, currency_id, permalink, thumbnail, category_id, search_term,
            confidence_score, normalized_json, raw_json, first_seen_at, last_seen_at,
            created_at, updated_at
        ) VALUES (
            %(source)s, %(external_id)s, %(status)s, %(title)s, %(author)s, %(isbn)s,
            %(publisher)s, %(publication_year)s, %(price)s, %(currency_id)s, %(permalink)s,
            %(thumbnail)s, %(category_id)s, %(search_term)s, %(confidence_score)s,
            %(normalized_json)s, %(raw_json)s, NOW(), NOW(), NOW(), NOW()
        )
        ON CONFLICT (source, external_id) DO UPDATE SET
            status = 'pending',
            title = EXCLUDED.title,
            author = EXCLUDED.author,
            isbn = EXCLUDED.isbn,
            publisher = EXCLUDED.publisher,
            publication_year = EXCLUDED.publication_year,
            price = EXCLUDED.price,
            currency_id = EXCLUDED.currency_id,
            permalink = EXCLUDED.permalink,
            thumbnail = EXCLUDED.thumbnail,
            category_id = EXCLUDED.category_id,
            search_term = EXCLUDED.search_term,
            confidence_score = EXCLUDED.confidence_score,
            normalized_json = EXCLUDED.normalized_json,
            raw_json = EXCLUDED.raw_json,
            last_seen_at = NOW(),
            updated_at = NOW()
    """
    written = 0
    with conn.cursor() as cur:
        for normalized, raw in records:
            if not normalized["external_id"]:
                continue
            params = dict(normalized)
            params["normalized_json"] = Json(normalized)
            params["raw_json"] = Json(raw)
            cur.execute(sql, params)
            written += 1
    conn.commit()
    return written


def main() -> int:
    terms = getenv_list("SYNC_TERMS")
    if not terms:
        raise RuntimeError("SYNC_TERMS não configurado.")
    limit = getenv_int("OPEN_LIBRARY_LIMIT", DEFAULT_LIMIT, minimum=1, maximum=100)

    records: list[tuple[dict[str, Any], dict[str, Any]]] = []
    seen: set[tuple[str, str]] = set()
    for term in terms:
        items = fetch_results(term, limit)
        print(f"term={term!r} results={len(items)}")
        for item in items:
            normalized = normalize_item(item, term)
            key = (normalized["source"], normalized["external_id"])
            if not normalized["external_id"] or key in seen:
                continue
            seen.add(key)
            records.append((normalized, item))

    with connect_database() as conn:
        written = upsert_records(conn, records)
    print(f"{written} registros Open Library enviados para source_records com status=pending.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except requests.HTTPError as exc:
        print(f"Erro HTTP Open Library: {exc}", file=sys.stderr)
        raise SystemExit(1)
    except Exception as exc:
        print(f"Erro na sincronização Open Library: {exc}", file=sys.stderr)
        raise SystemExit(1)
