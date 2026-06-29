#!/usr/bin/env python3
"""
Varredura de catálogos de editoras brasileiras para popular source_records.

Estratégia (da mais robusta para a mais frágil), por editora:
  1) Shopify  -> {base}/products.json            (dados estruturados, com ISBN)
  2) VTEX     -> {base}/api/catalog_system/...    (dados estruturados, com EAN)
  3) Sitemap + JSON-LD / Open Graph nas páginas dos livros

Descoberta de sitemap: tenta a diretiva `Sitemap:` do robots.txt e, em seguida,
caminhos conhecidos (/sitemap.xml, /sitemap_index.xml, /wp-sitemap.xml).

Para escapar de bloqueio de bot (403/429) usamos User-Agent de navegador e
retry com backoff exponencial.

Configuração por variáveis de ambiente:
- DATABASE_URL: conexão Postgres/Neon obrigatória.
- PUBLISHER_MAX_URLS: máximo de livros por editora (default: 20).
- PUBLISHER_SLEEP_SECONDS: pausa entre páginas HTML (default: 1.0).
- PUBLISHER_SLUGS: lista separada por vírgula para filtrar editoras (default: todas).
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

SITEMAP_PATHS = ("/sitemap.xml", "/sitemap_index.xml", "/wp-sitemap.xml", "/sitemap-index.xml")
BOOK_PATH_TERMS = ("livro", "produto", "obra", "detalhe", "product", "/p/", "book")
# Páginas de listagem para alargar o crawl quando o sitemap não serve.
LISTING_TERMS = (
    "livros", "catalogo", "categoria", "categorias", "colecao", "colecoes",
    "genero", "generos", "assunto", "autor", "autores", "lancamento",
    "lancamentos", "mais-vendidos", "selo", "selos",
)
# (connect, read): connect curto evita ficar minutos preso em host que não responde.
REQUEST_TIMEOUT_SECONDS = (6, 15)
MAX_RETRIES = 2
RETRYABLE_STATUS = {403, 429, 500, 502, 503, 504}
# UA de navegador real reduz bloqueio por WAF/Cloudflare; mantemos contato no header.
HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "X-Contact": "https://github.com/trevisollinux/lombada (LombadaPublisherSync)",
}
# platform: "auto" tenta shopify -> vtex -> sitemap. Pode forçar uma só.
SOURCES = [
    {
        # Plataforma custom (Communiplex): sem sitemap/JSON de catálogo, mas a home
        # lista /livro/{ISBN}/{slug} — crawl de HTML resolve e o ISBN vem da URL.
        "slug": "cia_das_letras",
        "name": "Companhia das Letras",
        "base_url": "https://www.companhiadasletras.com.br",
        "platform": "html",
    },
    {
        "slug": "editora_34",
        "name": "Editora 34",
        "base_url": "https://www.editora34.com.br",
        "platform": "auto",
    },
    {
        "slug": "record",
        "name": "Grupo Editorial Record",
        "base_url": "https://www.record.com.br",
        "platform": "auto",
    },
    {
        "slug": "intrinseca",
        "name": "Intrínseca",
        "base_url": "https://www.intrinseca.com.br",
        "platform": "auto",
    },
    {
        "slug": "todavia",
        "name": "Todavia",
        "base_url": "https://todavialivros.com.br",
        "platform": "auto",
    },
    {
        "slug": "sextante",
        "name": "Sextante",
        "base_url": "https://www.sextante.com.br",
        "platform": "auto",
    },
    {
        "slug": "autentica",
        "name": "Autêntica",
        "base_url": "https://grupoautentica.com.br",
        "platform": "auto",
    },
]
ISBN_RE = re.compile(r"((?:97[89][\-\s]?)?[0-9][0-9\-\s]{8,}[0-9Xx])")
LABELED_ISBN_RE = re.compile(r"ISBN(?:-1[03])?[:\s]*((?:97[89][\-\s]?)?[0-9][0-9\-\s]{8,}[0-9Xx])", re.I)
YEAR_RE = re.compile(r"\b(1[5-9]\d{2}|20\d{2})\b")


def getenv_bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "y"}


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


def fetch_url(url: str, accept: str | None = None) -> requests.Response | None:
    """GET com retry e backoff. Retorna None em falha definitiva (>=400 não-retryável)."""
    headers = dict(HEADERS)
    if accept:
        # Mantém a preferência (json/xml) mas aceita qualquer coisa: alguns servidores
        # (ex.: IIS) devolvem 404/406 a um Accept restritivo e escondem o sitemap.
        headers["Accept"] = f"{accept}, */*;q=0.1"
    for attempt in range(MAX_RETRIES):
        try:
            response = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT_SECONDS)
        except requests.RequestException as exc:
            # Host pendurado/inacessível não se recupera em 1s: não insiste (evita
            # acumular minutos de tempo morto × várias URLs por editora).
            print(f"Aviso: falha ao acessar {url}: {exc}", file=sys.stderr)
            return None
        if response.status_code in RETRYABLE_STATUS and attempt < MAX_RETRIES - 1:
            time.sleep(2 ** attempt)
            continue
        if response.status_code >= 400:
            return None
        return response
    return None


def fetch_json(url: str) -> Any:
    response = fetch_url(url, accept="application/json")
    if response is None:
        return None
    try:
        return response.json()
    except ValueError:
        return None


# ─── sitemap ──────────────────────────────────────────────
def discover_sitemaps_from_robots(base_url: str) -> list[str]:
    response = fetch_url(urljoin(base_url, "/robots.txt"), accept="text/plain")
    if response is None:
        return []
    sitemaps: list[str] = []
    for line in response.text.splitlines():
        if line.lower().startswith("sitemap:"):
            url = line.split(":", 1)[1].strip()
            if url:
                sitemaps.append(url)
    return sitemaps


def parse_sitemap_urls(xml_text: str) -> tuple[list[str], list[str]]:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return [], []
    sitemap_urls: list[str] = []
    page_urls: list[str] = []
    for element in root.iter():
        tag_name = element.tag.rsplit("}", 1)[-1]
        if tag_name not in {"sitemap", "url"}:
            continue
        loc = next((child for child in element if child.tag.rsplit("}", 1)[-1] == "loc"), None)
        if loc is None or not loc.text:
            continue
        if tag_name == "sitemap":
            sitemap_urls.append(loc.text.strip())
        else:
            page_urls.append(loc.text.strip())
    return sitemap_urls, page_urls


def collect_sitemap_urls(base_url: str) -> list[str]:
    all_urls: list[str] = []
    seen_sitemaps: set[str] = set()

    def visit(sitemap_url: str, depth: int = 0) -> None:
        if sitemap_url in seen_sitemaps or depth > 2:
            return
        seen_sitemaps.add(sitemap_url)
        response = fetch_url(sitemap_url, accept="application/xml")
        if response is None:
            return
        child_sitemaps, page_urls = parse_sitemap_urls(response.text)
        all_urls.extend(page_urls)
        for child_url in child_sitemaps[:25]:
            visit(child_url, depth + 1)

    # 1) sitemaps anunciados no robots.txt; 2) caminhos conhecidos.
    candidates = discover_sitemaps_from_robots(base_url)
    candidates += [urljoin(base_url, path) for path in SITEMAP_PATHS]
    for sitemap_url in dict.fromkeys(candidates):
        visit(sitemap_url)
    return list(dict.fromkeys(all_urls))


def looks_like_book_url(url: str) -> bool:
    path = urlparse(url).path.lower()
    return any(term in path for term in BOOK_PATH_TERMS)


# ─── extração genérica (JSON-LD / Open Graph) ─────────────
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


def extract_author_from_soup(soup: BeautifulSoup, bookish: dict[str, Any]) -> str:
    author = first_text(bookish.get("author") or bookish.get("creator"))
    if author:
        return author
    for prop in ("book:author", "author", "og:author", "article:author"):
        value = meta_content(soup, prop)
        if value and not value.lower().startswith("http"):
            return value
    # padrão comum em e-commerce de livro: "Autor: Fulano"
    text = soup.get_text(" ", strip=True)
    match = re.search(r"Autor(?:\(a\)|es)?\s*[:\-]\s*([A-ZÀ-Ý][^\n|·•]{2,60})", text)
    return match.group(1).strip() if match else ""


def clean_title(title: str, publisher_name: str) -> str:
    """Remove segmentos finais com o nome/branding da editora (og:title/<title>)."""
    title = " ".join((title or "").split())
    parts = re.split(r"\s+[\-|–—]\s+", title)
    if len(parts) <= 1:
        return title
    brand_words = {w for w in re.findall(r"\w+", publisher_name.lower()) if len(w) > 2}
    brand_words |= {"grupo", "editora", "livraria", "loja"}
    kept: list[str] = []
    for index, part in enumerate(parts):
        words = set(re.findall(r"\w+", part.lower()))
        if index > 0 and words and words <= brand_words:
            continue  # segmento que é só branding da editora
        kept.append(part)
    return " - ".join(kept).strip() or title


def isbn_from_jsonld(objects: list[dict[str, Any]]) -> str:
    for obj in objects:
        for key in ("isbn", "gtin13", "gtin", "gtin14", "productID"):
            value = obj.get(key)
            if value:
                isbn = extract_isbn(str(value if not isinstance(value, list) else (value[0] if value else "")))
                if isbn:
                    return isbn
    return ""


def _valid_isbn(raw: str) -> str:
    """Validação estrita: o trecho limpo precisa ter exatamente 10 ou 13 dígitos."""
    isbn = re.sub(r"[^0-9Xx]", "", raw).upper()
    if len(isbn) == 13 and isbn.isdigit():
        return isbn
    if len(isbn) == 10 and re.fullmatch(r"[0-9]{9}[0-9X]", isbn):
        return isbn
    return ""


def _isbn_prefix(raw: str) -> str:
    """Para trechos já rotulados como ISBN: tolera lixo no fim pegando o prefixo
    válido (o regex às vezes engole o ano seguinte: 'ISBN 978-...-1 2025')."""
    digits = re.sub(r"[^0-9Xx]", "", raw).upper()
    if len(digits) >= 13 and digits[:3] in {"978", "979"} and digits[:13].isdigit():
        return digits[:13]
    if len(digits) >= 10 and re.fullmatch(r"[0-9]{9}[0-9X]", digits[:10]):
        return digits[:10]
    return ""


def extract_isbn(text: str) -> str:
    """ISBN rotulado tem prioridade (e tolera ruído à direita); senão varre todos os
    candidatos exatos (não só o 1º, que costuma ser falso positivo: telefone/CNPJ)."""
    text = text or ""
    for match in LABELED_ISBN_RE.finditer(text):
        isbn = _isbn_prefix(match.group(1))
        if isbn:
            return isbn
    for match in ISBN_RE.finditer(text):
        isbn = _valid_isbn(match.group(1))
        if isbn:
            return isbn
    return ""


def extract_year(text: str) -> int | None:
    match = YEAR_RE.search(text)
    return int(match.group(1)) if match else None


def isbn_from_url(url: str) -> str:
    """Vários e-commerces embutem o ISBN no caminho (ex.: /livro/9788535947847/slug)."""
    for segment in urlparse(url).path.split("/"):
        candidate = norm_isbn(segment)
        if candidate:
            return candidate
    return ""


def stable_external_id(url: str) -> str:
    path_slug = urlparse(url).path.strip("/").replace("/", ":")
    if path_slug:
        return path_slug[:180]
    return hashlib.sha256(url.encode("utf-8")).hexdigest()


def build_record(
    publisher: dict[str, str],
    url: str,
    *,
    title: str,
    author: str = "",
    isbn: str = "",
    year: int | None = None,
    thumbnail: str = "",
    description: str = "",
    structured: bool = False,
    raw_extra: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]] | None:
    title = (title or "").strip()
    if not title:
        return None
    normalized = {
        "source": f"publisher:{publisher['slug']}",
        "external_id": stable_external_id(url),
        "status": "pending",
        "title": title,
        "author": (author or "").strip(),
        "isbn": isbn or "",
        "publisher": publisher["name"],
        "publication_year": year,
        "price": None,
        "currency_id": "",
        "permalink": url,
        "thumbnail": (thumbnail or "").strip(),
        "category_id": "",
        "search_term": publisher["name"],
    }
    score = 0.0
    score += 0.3 if normalized["title"] else 0.0
    score += 0.2 if normalized["author"] else 0.0
    score += 0.2 if normalized["isbn"] else 0.0
    score += 0.2 if normalized["thumbnail"] else 0.0
    score += 0.1 if structured else 0.0
    normalized["confidence_score"] = round(min(score, 1.0), 4)
    raw = {"url": url, "publisher": publisher, "description": description}
    if raw_extra:
        raw.update(raw_extra)
    return normalized, raw


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
    author = extract_author_from_soup(soup, bookish)
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

    title = clean_title(title, publisher["name"])

    visible_text = soup.get_text(" ", strip=True)
    raw_text = " ".join(filter(None, [author, description, visible_text]))
    isbn = (
        isbn_from_url(url)
        or isbn_from_url(thumbnail)  # muitos sites nomeiam a capa pelo ISBN (/livros/<isbn>.jpg)
        or isbn_from_jsonld(json_ld_objects)
        or extract_isbn(meta_content(soup, "book:isbn"))
        or extract_isbn(raw_text)
    )
    year = extract_year(first_text(bookish.get("datePublished")) or raw_text)

    return build_record(
        publisher,
        url,
        title=title,
        author=author,
        isbn=isbn,
        year=year,
        thumbnail=thumbnail,
        description=description,
        structured=bool(json_ld),
        raw_extra={
            "json_ld": json_ld,
            "open_graph": {
                "title": meta_content(soup, "og:title"),
                "description": meta_content(soup, "og:description"),
                "image": meta_content(soup, "og:image"),
            },
        },
    )


# ─── plataformas estruturadas ─────────────────────────────
def norm_isbn(value: Any) -> str:
    c = re.sub(r"[^0-9Xx]", "", str(value or "")).upper()
    if len(c) == 13 and c.isdigit():
        return c
    if len(c) == 10 and re.fullmatch(r"[0-9]{9}[0-9X]", c):
        return c
    return ""


def collect_via_shopify(
    publisher: dict[str, str], max_urls: int, sleep_seconds: float
) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    base_url = publisher["base_url"].rstrip("/")
    records: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for page in range(1, 11):
        data = fetch_json(f"{base_url}/products.json?limit=250&page={page}")
        if not isinstance(data, dict):
            break
        products = data.get("products") or []
        if not products:
            break
        for product in products:
            variants = product.get("variants") or []
            isbn = next((norm_isbn(v.get("barcode")) for v in variants if norm_isbn(v.get("barcode"))), "")
            images = product.get("images") or []
            thumbnail = (images[0].get("src") if images else "") or ""
            year = extract_year(str(product.get("published_at") or ""))
            url = f"{base_url}/products/{product.get('handle', '')}"
            record = build_record(
                publisher,
                url,
                title=product.get("title") or "",
                author=(product.get("vendor") or "").strip(),
                isbn=isbn,
                year=year,
                thumbnail=thumbnail,
                description=BeautifulSoup(product.get("body_html") or "", "html.parser").get_text(" ", strip=True)[:600],
                structured=True,
                raw_extra={"platform": "shopify", "product_id": product.get("id")},
            )
            if record:
                records.append(record)
            if len(records) >= max_urls:
                return records
        if sleep_seconds:
            time.sleep(sleep_seconds)
    return records


def vtex_author(product: dict[str, Any]) -> str:
    for key, value in product.items():
        if "autor" in key.lower() and isinstance(value, list) and value:
            return str(value[0]).strip()
    return str(product.get("brand") or "").strip()


def collect_via_vtex(
    publisher: dict[str, str], max_urls: int, sleep_seconds: float
) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    base_url = publisher["base_url"].rstrip("/")
    records: list[tuple[dict[str, Any], dict[str, Any]]] = []
    step = 50
    for start in range(0, 2500, step):
        url = f"{base_url}/api/catalog_system/pub/products/search?_from={start}&_to={start + step - 1}"
        data = fetch_json(url)
        if not isinstance(data, list) or not data:
            break
        for product in data:
            items = product.get("items") or []
            isbn = ""
            thumbnail = ""
            for item in items:
                isbn = isbn or norm_isbn(item.get("ean"))
                images = item.get("images") or []
                thumbnail = thumbnail or (images[0].get("imageUrl") if images else "")
            link = product.get("link") or (
                f"{base_url}/{product['linkText']}/p" if product.get("linkText") else base_url
            )
            year = extract_year(str(product.get("releaseDate") or ""))
            record = build_record(
                publisher,
                link,
                title=product.get("productName") or "",
                author=vtex_author(product),
                isbn=isbn,
                year=year,
                thumbnail=thumbnail or "",
                description=BeautifulSoup(product.get("description") or "", "html.parser").get_text(" ", strip=True)[:600],
                structured=True,
                raw_extra={"platform": "vtex", "product_id": product.get("productId")},
            )
            if record:
                records.append(record)
            if len(records) >= max_urls:
                return records
        if sleep_seconds:
            time.sleep(sleep_seconds)
    return records


def collect_via_sitemap(
    publisher: dict[str, str], max_urls: int, sleep_seconds: float
) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    sitemap_urls = collect_sitemap_urls(publisher["base_url"])
    if not sitemap_urls:
        print(f"  [sitemap] nenhum sitemap acessível para {publisher['slug']} ({publisher['base_url']}).")
        return []
    book_urls = [url for url in sitemap_urls if looks_like_book_url(url)]
    print(f"  [sitemap] urls={len(sitemap_urls)} candidatos_livro={len(book_urls)}")
    records: list[tuple[dict[str, Any], dict[str, Any]]] = []
    seen: set[str] = set()
    for url in book_urls:
        if len(records) >= max_urls:
            break
        extracted = extract_page(url, publisher)
        if extracted is None:
            continue
        normalized, _ = extracted
        if normalized["external_id"] in seen:
            continue
        seen.add(normalized["external_id"])
        records.append(extracted)
        if sleep_seconds:
            time.sleep(sleep_seconds)
    return records


def harvest_links(html: str, base_url: str) -> tuple[list[str], list[str]]:
    """Separa links internos em (urls_de_livro, urls_de_listagem)."""
    host = urlparse(base_url).netloc.replace("www.", "")
    soup = BeautifulSoup(html, "html.parser")
    book_urls: list[str] = []
    listing_urls: list[str] = []
    for anchor in soup.find_all("a", href=True):
        full = urljoin(base_url, anchor["href"])
        parsed = urlparse(full)
        if parsed.scheme not in {"http", "https"} or parsed.netloc.replace("www.", "") != host:
            continue
        clean = full.split("#", 1)[0]
        path = parsed.path.lower()
        if looks_like_book_url(clean):
            book_urls.append(clean)
        elif any(term in path for term in LISTING_TERMS):
            listing_urls.append(clean)
    return list(dict.fromkeys(book_urls)), list(dict.fromkeys(listing_urls))


def collect_via_html_crawl(
    publisher: dict[str, str], max_urls: int, sleep_seconds: float
) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    """Fallback p/ sites sem sitemap/JSON: parte da home e segue páginas de listagem."""
    base_url = publisher["base_url"].rstrip("/")
    home = fetch_url(base_url + "/")
    if home is None:
        print(f"  [html] home inacessível para {publisher['slug']}.")
        return []
    book_urls, listing_urls = harvest_links(home.text, base_url)
    # Alarga o conjunto visitando algumas páginas de listagem (catálogo/coleções).
    for listing_url in listing_urls[:12]:
        if len(book_urls) >= max_urls * 4:
            break
        resp = fetch_url(listing_url)
        if resp is not None:
            more_books, _ = harvest_links(resp.text, base_url)
            book_urls.extend(more_books)
        if sleep_seconds:
            time.sleep(sleep_seconds)
    book_urls = list(dict.fromkeys(book_urls))
    print(f"  [html] urls_livro={len(book_urls)} (de {len(listing_urls)} listagens)")

    records: list[tuple[dict[str, Any], dict[str, Any]]] = []
    seen: set[str] = set()
    for url in book_urls:
        if len(records) >= max_urls:
            break
        extracted = extract_page(url, publisher)
        if extracted is None:
            continue
        normalized, _ = extracted
        if normalized["external_id"] in seen:
            continue
        seen.add(normalized["external_id"])
        records.append(extracted)
        if sleep_seconds:
            time.sleep(sleep_seconds)
    return records


PLATFORM_COLLECTORS = {
    "shopify": collect_via_shopify,
    "vtex": collect_via_vtex,
    "sitemap": collect_via_sitemap,
    "html": collect_via_html_crawl,
}
AUTO_ORDER = ["shopify", "vtex", "sitemap", "html"]


def collect_publisher(
    publisher: dict[str, str], max_urls: int, sleep_seconds: float
) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    platform = publisher.get("platform", "auto")
    order = [platform] if platform in PLATFORM_COLLECTORS else AUTO_ORDER
    for name in order:
        collector = PLATFORM_COLLECTORS[name]
        try:
            records = collector(publisher, max_urls, sleep_seconds)
        except Exception as exc:  # noqa: BLE001 — uma plataforma falhar não derruba as outras
            print(f"  [{name}] erro: {exc!r}", file=sys.stderr)
            continue
        if records:
            print(f"  método={name} registros={len(records)}")
            return records
    print(f"  nenhum método retornou registros para {publisher['slug']}.")
    return []


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


def select_sources() -> list[dict[str, str]]:
    raw = os.getenv("PUBLISHER_SLUGS", "").strip()
    if not raw:
        return SOURCES
    wanted = {s.strip().lower() for s in raw.split(",") if s.strip()}
    return [s for s in SOURCES if s["slug"].lower() in wanted] or SOURCES


def diagnose(publisher: dict[str, str]) -> None:
    """Mostra status/content-type de cada endpoint candidato — revela a plataforma."""
    base_url = publisher["base_url"].rstrip("/")
    probes = [
        ("home", base_url + "/"),
        ("robots", base_url + "/robots.txt"),
        ("shopify", base_url + "/products.json?limit=1"),
        ("vtex", base_url + "/api/catalog_system/pub/products/search?_from=0&_to=1"),
        ("sitemap.xml", base_url + "/sitemap.xml"),
        ("sitemap_index", base_url + "/sitemap_index.xml"),
        ("wp-sitemap", base_url + "/wp-sitemap.xml"),
    ]
    for label, url in probes:
        try:
            r = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT_SECONDS, allow_redirects=True)
            ct = r.headers.get("content-type", "")
            server = r.headers.get("server", "") or r.headers.get("x-powered-by", "")
            snippet = " ".join(r.text[:180].split())
            print(f"  [{label}] {r.status_code} ct={ct} server={server} final={r.url}")
            print(f"       {snippet}")
        except Exception as exc:  # noqa: BLE001
            print(f"  [{label}] ERRO {exc!r}")

    # Amostra de links internos da home (revela o padrão de URL de livro)
    host = urlparse(base_url).netloc.replace("www.", "")
    try:
        home = requests.get(base_url + "/", headers=HEADERS, timeout=REQUEST_TIMEOUT_SECONDS)
        soup = BeautifulSoup(home.text, "html.parser")
        paths: list[str] = []
        for a in soup.find_all("a", href=True):
            full = urljoin(base_url, a["href"])
            if urlparse(full).netloc.replace("www.", "") == host:
                p = urlparse(full).path
                if p and p != "/":
                    paths.append(p)
        uniq = list(dict.fromkeys(paths))
        bookish = [p for p in uniq if looks_like_book_url(base_url + p)]
        print(f"  home: {len(uniq)} links internos; {len(bookish)} parecem livro")
        for p in (bookish or uniq)[:15]:
            print(f"       {p}")
    except Exception as exc:  # noqa: BLE001
        print(f"  home: ERRO {exc!r}")

    # Amostra de URLs do sitemap anunciado no robots (confirma parsing/padrão)
    for sm in discover_sitemaps_from_robots(base_url) + [base_url + "/sitemap.xml"]:
        resp = fetch_url(sm, accept="application/xml")
        if resp is None:
            continue
        children, pages = parse_sitemap_urls(resp.text)
        print(f"  sitemap {sm}: filhos={len(children)} paginas={len(pages)}")
        for u in (pages or children)[:10]:
            print(f"       {u}")
        break


def dump_url(url: str) -> None:
    """Despeja JSON-LD, metatags e trechos de uma página — para entender a extração."""
    response = fetch_url(url)
    if response is None:
        print(f"  inacessível: {url}")
        return
    soup = BeautifulSoup(response.text, "html.parser")
    print(f"  URL {url} ({len(response.text)} bytes)")
    json_ld = load_json_ld(soup)
    print(f"  JSON-LD blocos={len(json_ld)}")
    for obj in list(iter_json_objects(json_ld))[:8]:
        keys = sorted(obj.keys())
        print(f"    @type={obj.get('@type')} keys={keys}")
    for prop in ("og:title", "og:image", "author", "book:author", "book:isbn", "twitter:title"):
        value = meta_content(soup, prop)
        if value:
            print(f"    meta[{prop}]={value[:120]}")
    text = soup.get_text(" ", strip=True)
    for label in ("ISBN", "Autor", "Tradu", "Editora", "Ano"):
        idx = text.find(label)
        if idx != -1:
            print(f"    txt~{label}: {text[idx:idx+80]!r}")


def main() -> int:
    dump = os.getenv("PUBLISHER_DUMP_URL", "").strip()
    if dump:
        print(f"DUMP {dump}")
        dump_url(dump)
        return 0

    if getenv_bool("PUBLISHER_DIAGNOSE", False):
        for publisher in select_sources():
            print("=" * 60)
            print(f"{publisher['slug']} — {publisher['name']} ({publisher['base_url']})")
            diagnose(publisher)
            print()
        return 0

    max_urls = getenv_int("PUBLISHER_MAX_URLS", 20, minimum=1, maximum=2000)
    sleep_seconds = getenv_float("PUBLISHER_SLEEP_SECONDS", 1.0)
    dry_run = getenv_bool("PUBLISHER_DRY_RUN", False)
    sources = select_sources()
    modo = "DRY_RUN (não grava)" if dry_run else "gravando no banco"
    print(f"max_urls={max_urls}/editora sleep={sleep_seconds}s editoras={len(sources)} — {modo}\n")

    all_records: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for publisher in sources:
        print("=" * 60)
        print(f"{publisher['slug']} — {publisher['name']} ({publisher['base_url']})")
        records = collect_publisher(publisher, max_urls, sleep_seconds)
        with_isbn = sum(1 for normalized, _ in records if normalized["isbn"])
        with_author = sum(1 for normalized, _ in records if normalized["author"])
        print(f"  cobertura: ISBN {with_isbn}/{len(records)} · autor {with_author}/{len(records)}")
        for normalized, _ in records[:5]:
            print(
                f"   - {normalized['title'][:44]:44} | {normalized['author'][:20]:20} "
                f"| isbn={normalized['isbn'] or '-'}"
            )
        all_records.extend(records)
        print()

    if not all_records:
        print("Nenhum registro coletado.")
        return 0

    if dry_run:
        print(f"DRY_RUN: {len(all_records)} registros coletados, nada gravado.")
        return 0

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
