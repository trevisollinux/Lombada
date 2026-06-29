#!/usr/bin/env python3
"""
Varredura curta de livros no Mercado Livre para popular source_records.

Configuração por variáveis de ambiente:
- DATABASE_URL: conexão Postgres/Neon obrigatória, exceto em DRY_RUN.
- SYNC_TERMS: termos separados por vírgula.
- MELI_CATEGORY_IDS: categorias separadas por vírgula; use vazio para buscar sem categoria.
- MELI_LIMIT: resultados por página.
- MELI_PAGES: número de páginas por termo/categoria.
- SYNC_SLEEP_SECONDS: pausa entre chamadas.
- DRY_RUN: true/1/yes para imprimir sem gravar.
- MELI_ACCESS_TOKEN: token opcional para autenticar chamadas ao Mercado Livre.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.parse import urlparse

import psycopg2
from psycopg2.extras import Json
import requests

MELI_SEARCH_URL = "https://api.mercadolibre.com/sites/MLB/search"
SOURCE = "mercado_livre"
DEFAULT_TERMS = "livro romance,literatura brasileira,livro infantil"
DEFAULT_CATEGORY_IDS = "MLB1196"
REQUEST_TIMEOUT_SECONDS = 20
MELI_HEADERS = {
    "Accept": "application/json",
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
    "User-Agent": "LombadaBookSync/0.1 (+https://lombada.onrender.com)",
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


def getenv_float(name: str, default: float, minimum: float = 0.0) -> float:
    raw_value = os.getenv(name, str(default)).strip()
    try:
        value = float(raw_value)
    except ValueError:
        value = default
    return max(minimum, value)


def getenv_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "t", "yes", "y", "sim"}


def normalize_database_url(database_url: str) -> str:
    if database_url.startswith("postgres://"):
        return database_url.replace("postgres://", "postgresql://", 1)
    return database_url


def extract_attribute(item: dict[str, Any], names: set[str]) -> str:
    for attr in item.get("attributes") or []:
        attr_name = str(attr.get("name") or attr.get("id") or "").strip().lower()
        if attr_name in names:
            value = attr.get("value_name") or attr.get("value_id") or ""
            if value:
                return str(value).strip()
    return ""


def extract_isbn(item: dict[str, Any]) -> str:
    isbn = extract_attribute(item, {"isbn", "isbn 10", "isbn 13"})
    if isbn:
        return re.sub(r"[^0-9Xx]", "", isbn)
    title = str(item.get("title") or "")
    match = re.search(r"(?:97[89][\- ]?)?[0-9][0-9\- ]{8,}[0-9Xx]", title)
    return re.sub(r"[^0-9Xx]", "", match.group(0)) if match else ""


def extract_year(item: dict[str, Any]) -> int | None:
    value = extract_attribute(item, {"ano", "ano de publicação", "publication year", "year"})
    if value:
        match = re.search(r"\b(1[5-9]\d{2}|20\d{2})\b", value)
        if match:
            return int(match.group(1))
    return None


def decimal_or_none(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def confidence_score(item: dict[str, Any], normalized: dict[str, Any]) -> float:
    score = 0.35
    if normalized["title"]:
        score += 0.2
    if normalized["author"]:
        score += 0.15
    if normalized["isbn"]:
        score += 0.2
    if normalized["category_id"]:
        score += 0.05
    if item.get("permalink"):
        score += 0.05
    return round(min(score, 1.0), 4)


def normalize_item(item: dict[str, Any], search_term: str) -> dict[str, Any]:
    normalized = {
        "source": SOURCE,
        "external_id": str(item.get("id") or "").strip(),
        "status": "pending",
        "title": str(item.get("title") or "").strip(),
        "author": extract_attribute(item, {"autor", "author"}),
        "isbn": extract_isbn(item),
        "publisher": extract_attribute(item, {"editora", "publisher", "marca"}),
        "publication_year": extract_year(item),
        "price": decimal_or_none(item.get("price")),
        "currency_id": str(item.get("currency_id") or "").strip(),
        "permalink": str(item.get("permalink") or "").strip(),
        "thumbnail": str(item.get("thumbnail") or "").strip(),
        "category_id": str(item.get("category_id") or "").strip(),
        "search_term": search_term,
    }
    normalized["confidence_score"] = confidence_score(item, normalized)
    return normalized


def build_meli_headers() -> dict[str, str]:
    headers = dict(MELI_HEADERS)
    access_token = os.getenv("MELI_ACCESS_TOKEN", "").strip()
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"
    return headers


def request_meli_search(params: dict[str, Any]) -> requests.Response:
    return requests.get(
        MELI_SEARCH_URL,
        params=params,
        headers=build_meli_headers(),
        timeout=REQUEST_TIMEOUT_SECONDS,
    )


def raise_meli_forbidden() -> None:
    raise RuntimeError(
        "Mercado Livre recusou a requisição com HTTP 403. "
        "Verifique token, permissões da aplicação e possível bloqueio do endpoint de busca."
    )


def fetch_page(term: str, category_id: str, limit: int, page: int) -> list[dict[str, Any]]:
    params: dict[str, Any] = {"q": term, "limit": limit, "offset": page * limit}
    if category_id:
        params["category"] = category_id

    response = request_meli_search(params)
    if response.status_code == 403 and category_id:
        retry_params = dict(params)
        retry_params.pop("category", None)
        print(
            "Mercado Livre retornou HTTP 403 com category; tentando novamente sem category.",
            file=sys.stderr,
        )
        response = request_meli_search(retry_params)

    if response.status_code == 403:
        raise_meli_forbidden()

    response.raise_for_status()
    payload = response.json()
    return payload.get("results") or []


def connect_database():
    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url:
        raise RuntimeError("DATABASE_URL não configurado. Use DRY_RUN=true para testar sem gravar.")
    parsed = urlparse(normalize_database_url(database_url))
    if parsed.scheme not in {"postgresql", "postgres"}:
        raise RuntimeError("DATABASE_URL deve apontar para Postgres/Neon.")
    return psycopg2.connect(normalize_database_url(database_url))


def json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        return {key: json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_safe(item) for item in value]
    return value


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
    with conn.cursor() as cur:
        for normalized, raw in records:
            if not normalized["external_id"]:
                continue
            params = dict(normalized)
            params["normalized_json"] = Json(json_safe(normalized))
            params["raw_json"] = Json(raw)
            cur.execute(sql, params)
    conn.commit()
    return len(records)


def main() -> int:
    terms = getenv_list("SYNC_TERMS", DEFAULT_TERMS)
    category_ids = getenv_list("MELI_CATEGORY_IDS", DEFAULT_CATEGORY_IDS) or [""]
    limit = getenv_int("MELI_LIMIT", 10, minimum=1, maximum=50)
    pages = getenv_int("MELI_PAGES", 1, minimum=1, maximum=5)
    sleep_seconds = getenv_float("SYNC_SLEEP_SECONDS", 0.5)
    dry_run = getenv_bool("DRY_RUN", False)

    records: list[tuple[dict[str, Any], dict[str, Any]]] = []
    seen: set[tuple[str, str]] = set()

    for term in terms:
        for category_id in category_ids:
            for page in range(pages):
                items = fetch_page(term, category_id, limit, page)
                print(f"term={term!r} category={category_id or '-'} page={page + 1} results={len(items)}")
                for item in items:
                    normalized = normalize_item(item, term)
                    key = (normalized["source"], normalized["external_id"])
                    if not normalized["external_id"] or key in seen:
                        continue
                    seen.add(key)
                    records.append((normalized, item))
                if sleep_seconds:
                    time.sleep(sleep_seconds)

    if dry_run:
        print(json.dumps([record[0] for record in records], ensure_ascii=False, indent=2, default=str))
        print(f"DRY_RUN=true; {len(records)} registros normalizados e não gravados.")
        return 0

    with connect_database() as conn:
        written = upsert_records(conn, records)
    print(f"{written} registros enviados para source_records com status=pending.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except requests.HTTPError as exc:
        print(f"Erro HTTP Mercado Livre: {exc}", file=sys.stderr)
        raise SystemExit(1)
    except Exception as exc:
        print(f"Erro na sincronização: {exc}", file=sys.stderr)
        raise SystemExit(1)
