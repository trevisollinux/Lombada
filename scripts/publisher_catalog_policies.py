"""Políticas específicas para fontes adicionadas pelo cadastro de editoras."""
from __future__ import annotations

import html
import os
import re
import sys
import time
import warnings
from typing import Any
from urllib.parse import urlparse

import urllib3

_INSECURE_TLS_HOSTS = {"globaleditora.com.br", "www.globaleditora.com.br"}
_GENERIC_PLANETA_TITLE_RE = re.compile(
    r"^(?:outros|mais)\s+livros\s+de\b|^livros\s+de\b|^produtos?\s+relacionados?\b",
    re.I,
)
_AUTHOR_PREFIX_RE = re.compile(r"^(?:autor(?:a|es)?|por)\s*[:\-]?\s*", re.I)
_AUTHOR_REJECT_RE = re.compile(
    r"^(?:outros livros|mais livros|todos os livros|conheça|veja também|saiba mais)\b",
    re.I,
)
_SOURCE_OVERRIDES: dict[str, dict[str, Any]] = {
    # O endpoint HTTPS raiz devolve AccessDenied no bucket; o host HTTP entrega
    # o shell da SPA e é o ponto de partida para a estratégia específica.
    "globo_livros": {"base_url": "http://globolivros.globo.com", "platform": "html"},
}


def decode_entities(value: Any) -> str:
    """Decodifica entidades HTML inclusive quando vieram escapadas duas vezes."""
    text = str(value or "")
    for _ in range(2):
        decoded = html.unescape(text)
        if decoded == text:
            break
        text = decoded
    return " ".join(text.split())


def apply_source_overrides(source: dict[str, Any]) -> dict[str, Any]:
    result = dict(source)
    result.update(_SOURCE_OVERRIDES.get(str(source.get("slug") or ""), {}))
    return result


def _clean_author_candidate(value: str) -> str:
    candidate = decode_entities(value)
    candidate = _AUTHOR_PREFIX_RE.sub("", candidate).strip(" -–—·|,;:")
    if not (2 <= len(candidate) <= 100):
        return ""
    if _AUTHOR_REJECT_RE.search(candidate):
        return ""
    if candidate.lower() in {"autor", "autora", "autores", "por"}:
        return ""
    return candidate


def _fetch_with_insecure_tls(sync_module: Any, url: str, accept: str | None, extra_headers: dict[str, str] | None):
    headers = dict(sync_module.HEADERS)
    if extra_headers:
        headers.update(extra_headers)
    if accept:
        headers["Accept"] = f"{accept}, */*;q=0.1"

    for attempt in range(sync_module.MAX_RETRIES):
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", urllib3.exceptions.InsecureRequestWarning)
                response = sync_module._session_for_fetch().get(
                    url,
                    headers=headers,
                    timeout=sync_module.REQUEST_TIMEOUT_SECONDS,
                    verify=False,
                )
        except sync_module.requests.RequestException as exc:
            print(f"Aviso: falha ao acessar {url} com TLS restrito à fonte: {exc}", file=sys.stderr)
            sync_module._record_fetch_failure(f"exception:{type(exc).__name__}", url)
            sync_module.LAST_FETCH_STATUS = 0
            return None
        if response.status_code in sync_module.RETRYABLE_STATUS and attempt < sync_module.MAX_RETRIES - 1:
            time.sleep(2 ** attempt)
            continue
        sync_module.LAST_FETCH_STATUS = response.status_code
        if response.status_code >= 400:
            sync_module._record_fetch_failure(f"status:{response.status_code}", url)
            return None
        return response
    return None


def install(sync_module: Any) -> None:
    """Instala correções conservadoras somente no processo do catálogo expandido."""
    if getattr(sync_module, "_publisher_catalog_policies_installed", False):
        return

    original_fetch_url = sync_module.fetch_url
    original_build_record = sync_module.build_record
    original_valid_record = sync_module.valid_extracted_record
    original_extract_author = sync_module.extract_author_from_soup
    original_select_sources = sync_module.select_sources

    def fetch_url(url: str, accept: str | None = None, extra_headers: dict[str, str] | None = None):
        host = (urlparse(url).hostname or "").lower()
        if host in _INSECURE_TLS_HOSTS:
            return _fetch_with_insecure_tls(sync_module, url, accept, extra_headers)
        return original_fetch_url(url, accept=accept, extra_headers=extra_headers)

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
    ):
        return original_build_record(
            publisher,
            url,
            title=decode_entities(title),
            author=decode_entities(author),
            isbn=isbn,
            year=year,
            thumbnail=thumbnail,
            description=decode_entities(description),
            structured=structured,
            raw_extra=raw_extra,
        )

    def extract_author_from_soup(soup: Any, bookish: dict[str, Any]) -> str:
        author = _clean_author_candidate(original_extract_author(soup, bookish))
        if author:
            return author
        selectors = (
            "[itemprop='author']",
            "[itemprop='creator']",
            "a[href*='/autor/']",
            "a[href*='/autores/']",
            "a[href*='/author/']",
            ".autor a",
            ".author a",
            ".product-author",
            ".book-author",
        )
        for selector in selectors:
            for node in soup.select(selector)[:6]:
                candidate = _clean_author_candidate(node.get_text(" ", strip=True))
                if candidate:
                    return candidate
        return ""

    def valid_extracted_record(extracted: Any) -> bool:
        if not original_valid_record(extracted):
            return False
        normalized, _raw = extracted
        source = str(normalized.get("source") or "")
        title = decode_entities(normalized.get("title"))
        permalink = str(normalized.get("permalink") or "").lower()
        if source == "publisher:planeta_livros_brasil":
            if _GENERIC_PLANETA_TITLE_RE.search(title):
                return False
            if "/autor/" in permalink or "/autores/" in permalink:
                return False
        return True

    def select_sources() -> list[dict[str, Any]]:
        # No scraper principal, um slug inexistente cai silenciosamente para TODAS
        # as fontes. No catálogo isso é perigoso (e mascara fonte desabilitada),
        # portanto um filtro explícito sempre devolve exatamente o que foi pedido.
        raw = os.getenv("PUBLISHER_SLUGS", "").strip()
        if raw:
            wanted = {item.strip().lower() for item in raw.split(",") if item.strip()}
            return [source for source in sync_module.SOURCES if source["slug"].lower() in wanted]
        return original_select_sources()

    sync_module.fetch_url = fetch_url
    sync_module.build_record = build_record
    sync_module.extract_author_from_soup = extract_author_from_soup
    sync_module.valid_extracted_record = valid_extracted_record
    sync_module.select_sources = select_sources
    sync_module._publisher_catalog_policies_installed = True
