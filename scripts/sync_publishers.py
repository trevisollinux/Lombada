#!/usr/bin/env python3
"""
Varredura curta de páginas oficiais de editoras brasileiras para popular source_records.

Configuração por variáveis de ambiente:
- DATABASE_URL: conexão Postgres/Neon obrigatória.
- PUBLISHER_MAX_URLS: máximo de páginas candidatas por editora (default: 20).
- PUBLISHER_SLEEP_SECONDS: pausa entre páginas HTML (default: 1.0).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import time
import xml.etree.ElementTree as ET
from typing import Any
from urllib.parse import urljoin, urlparse

import psycopg2
from psycopg2.extras import Json
import requests
from bs4 import BeautifulSoup

SITEMAP_PATHS = ("/sitemap.xml", "/sitemap_index.xml", "/wp-sitemap.xml")
BOOK_PATH_TERMS = ("livro", "produto", "obra", "catalogo", "detalhe", "product")
REQUEST_TIMEOUT_SECONDS = 20
HEADERS = {
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "pt-BR,pt;q=0.9",
    "User-Agent": "LombadaPublisherSync/0.1 (+https://lombada.onrender.com)",
}
SOURCES = [
    {
        "slug": "cia_das_letras",
        "name": "Cia das Letras",
        "base_url": "https://www.companhiadasletras.com.br",
    },
    {
        "slug": "editora_34",
        "name": "Editora 34",
        "base_url": "https://www.editora34.com.br",
    },
    {
        "slug": "record",
        "name": "Grupo Editorial Record",
        "base_url": "https://www.record.com.br",
    },
]
ISBN_RE = re.compile(r"(?:ISBN(?:-1[03])?[:\s]*)?((?:97[89][\-\s]?)?[0-9][0-9\-\s]{8,}[0-9Xx])")
YEAR_RE = re.compile(r"\b(1[5-9]\d{2}|20\d{2})\b")


def getenv_int(name: str, default: int, minimum: int = 1, maximum: int | None = None) -> int:
    try:
        value = int(os.getenv(name, str(default)).strip())
    except ValueError:
        value = default
    value = max(minimum, value)
    return min(value, maximum) if maximum is not None else value


def getenv_float(name: str, default: float, minimum: float = 0.0) -> float:
    try:
        value = float(os.getenv(name, str(default)).strip())
    except ValueError:
        value = default
    return max(minimum, value)


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


def fetch_url(url: str) -> requests.Response | None:
    try:
        response = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT_SECONDS)
        if response.status_code >= 400:
            return None
        return response
    except requests.RequestException as exc:
        print(f"Aviso: falha ao acessar {url}: {exc}", file=sys.stderr)
        return None


def parse_sitemap_urls(xml_text: str) -> tuple[list[str], list[str]]:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return [], []
    sitemap_urls: list[str] = []
    page_urls: list[str] = []
    for element in root:
        tag_name = element.tag.rsplit("}", 1)[-1]
        loc = next((child for child in element if child.tag.rsplit("}", 1)[-1] == "loc"), None)
        if loc is None or not loc.text:
            continue
        if tag_name == "sitemap":
            sitemap_urls.append(loc.text.strip())
        elif tag_name == "url":
            page_urls.append(loc.text.strip())
    return sitemap_urls, page_urls


def collect_sitemap_urls(base_url: str) -> list[str]:
    all_urls: list[str] = []
    seen_sitemaps: set[str] = set()

    def visit(sitemap_url: str, depth: int = 0) -> None:
        if sitemap_url in seen_sitemaps or depth > 2:
            return
        seen_sitemaps.add(sitemap_url)
        response = fetch_url(sitemap_url)
        if response is None:
            return
        child_sitemaps, page_urls = parse_sitemap_urls(response.text)
        all_urls.extend(page_urls)
        for child_url in child_sitemaps[:25]:
            visit(child_url, depth + 1)

    for path in SITEMAP_PATHS:
        visit(urljoin(base_url, path))
    return list(dict.fromkeys(all_urls))


def looks_like_book_url(url: str) -> bool:
    path = urlparse(url).path.lower()
    return any(term in path for term in BOOK_PATH_TERMS)


def load_json_ld(soup: BeautifulSoup) -> list[Any]:
    values: list[Any] = []
    for tag in soup.find_all("script", attrs={"type": "application/ld+json"}):
        text = tag.string or tag.get_text(" ", strip=True)
        if not text:
            continue
        try:
            values.append(json.loads(text))
        except json.JSONDecodeError:
            continue
    return values


def iter_json_objects(value: Any):
    if isinstance(value, dict):
        yield value
        graph = value.get("@graph")
        if isinstance(graph, list):
            for item in graph:
                yield from iter_json_objects(item)
    elif isinstance(value, list):
        for item in value:
            yield from iter_json_objects(item)


def first_text(value: Any) -> str:
    if isinstance(value, list):
        return first_text(value[0]) if value else ""
    if isinstance(value, dict):
        return str(value.get("name") or value.get("title") or "").strip()
    return str(value or "").strip()


def meta_content(soup: BeautifulSoup, property_name: str) -> str:
    tag = soup.find("meta", property=property_name) or soup.find("meta", attrs={"name": property_name})
    return str(tag.get("content") or "").strip() if tag else ""


def extract_isbn(text: str) -> str:
    match = ISBN_RE.search(text)
    if not match:
        return ""
    isbn = re.sub(r"[^0-9Xx]", "", match.group(1))
    return isbn if len(isbn) in {10, 13} else ""


def extract_year(text: str) -> int | None:
    match = YEAR_RE.search(text)
    return int(match.group(1)) if match else None


def stable_external_id(url: str) -> str:
    path_slug = urlparse(url).path.strip("/").replace("/", ":")
    if path_slug:
        return path_slug[:180]
    return hashlib.sha256(url.encode("utf-8")).hexdigest()


def extract_page(url: str, publisher: dict[str, str]) -> tuple[dict[str, Any], dict[str, Any]] | None:
    response = fetch_url(url)
    if response is None:
        return None
    soup = BeautifulSoup(response.text, "html.parser")
    json_ld = load_json_ld(soup)
    json_ld_objects = list(iter_json_objects(json_ld))
    bookish = next(
        (
            item
            for item in json_ld_objects
            if str(item.get("@type") or "").lower() in {"book", "product", "creativework"}
        ),
        json_ld_objects[0] if json_ld_objects else {},
    )

    title = first_text(bookish.get("name") or bookish.get("headline"))
    author = first_text(bookish.get("author") or bookish.get("creator"))
    thumbnail = first_text(bookish.get("image"))
    description = first_text(bookish.get("description"))

    if not title:
        title = meta_content(soup, "og:title")
    if not description:
        description = meta_content(soup, "og:description")
    if not thumbnail:
        thumbnail = meta_content(soup, "og:image")
    if not title and soup.title:
        title = soup.title.get_text(" ", strip=True)
    if not title:
        h1 = soup.find("h1")
        title = h1.get_text(" ", strip=True) if h1 else ""

    visible_text = soup.get_text(" ", strip=True)
    raw_text = " ".join(filter(None, [title, author, description, visible_text[:5000]]))
    isbn = first_text(bookish.get("isbn")) or extract_isbn(raw_text)
    year = extract_year(first_text(bookish.get("datePublished")) or raw_text)

    normalized = {
        "source": f"publisher:{publisher['slug']}",
        "external_id": stable_external_id(url),
        "status": "pending",
        "title": title,
        "author": author,
        "isbn": isbn,
        "publisher": publisher["name"],
        "publication_year": year,
        "price": None,
        "currency_id": "",
        "permalink": url,
        "thumbnail": thumbnail,
        "category_id": "",
        "search_term": publisher["name"],
    }
    score = 0.0
    score += 0.3 if title else 0.0
    score += 0.2 if author else 0.0
    score += 0.2 if isbn else 0.0
    score += 0.2 if thumbnail else 0.0
    score += 0.1 if json_ld else 0.0
    normalized["confidence_score"] = round(min(score, 1.0), 4)
    raw = {
        "url": url,
        "publisher": publisher,
        "json_ld": json_ld,
        "open_graph": {
            "title": meta_content(soup, "og:title"),
            "description": meta_content(soup, "og:description"),
            "image": meta_content(soup, "og:image"),
        },
        "html": {
            "title": soup.title.get_text(" ", strip=True) if soup.title else "",
            "h1": soup.find("h1").get_text(" ", strip=True) if soup.find("h1") else "",
            "isbn": isbn,
        },
    }
    return normalized, raw


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
            params = dict(normalized)
            params["normalized_json"] = Json(normalized)
            params["raw_json"] = Json(raw)
            cur.execute(sql, params)
            written += 1
    conn.commit()
    return written


def main() -> int:
    max_urls = getenv_int("PUBLISHER_MAX_URLS", 20, minimum=1, maximum=500)
    sleep_seconds = getenv_float("PUBLISHER_SLEEP_SECONDS", 1.0)
    all_records: list[tuple[dict[str, Any], dict[str, Any]]] = []

    for publisher in SOURCES:
        sitemap_urls = collect_sitemap_urls(publisher["base_url"])
        if not sitemap_urls:
            print(f"Aviso: nenhum sitemap acessível para {publisher['slug']} ({publisher['base_url']}).")
        print(f"publisher={publisher['slug']} sitemap_urls={len(sitemap_urls)}")
        book_urls = [url for url in sitemap_urls if looks_like_book_url(url)]
        print(f"publisher={publisher['slug']} candidate_book_urls={len(book_urls)}")

        records: list[tuple[dict[str, Any], dict[str, Any]]] = []
        seen: set[tuple[str, str]] = set()
        for url in book_urls[:max_urls]:
            extracted = extract_page(url, publisher)
            if extracted is None:
                continue
            normalized, raw = extracted
            key = (normalized["source"], normalized["external_id"])
            if key in seen:
                continue
            seen.add(key)
            records.append((normalized, raw))
            if sleep_seconds:
                time.sleep(sleep_seconds)
        print(f"publisher={publisher['slug']} records_ready={len(records)}")
        all_records.extend(records)

    with connect_database() as conn:
        written = upsert_records(conn, all_records)
    print(f"{written} registros salvos em source_records com status=pending.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"Erro na sincronização de editoras: {exc}", file=sys.stderr)
        raise SystemExit(1)
