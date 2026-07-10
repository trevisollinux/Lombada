#!/usr/bin/env python3
"""
Varredura de catálogos de editoras brasileiras para popular source_records.

Estratégia (da mais robusta para a mais frágil), por editora:
  1) Shopify  -> {base}/products.json            (dados estruturados, com ISBN)
  2) VTEX     -> {base}/api/catalog_system/...    (dados estruturados, com EAN)
  3) id_range -> enumera páginas /livro/{id}      (catálogos custom/JS)
  4) Sitemap  -> URLs anunciadas + extração das páginas dos livros
  5) HTML     -> crawl de listagens/categorias como fallback

Descoberta de sitemap: tenta a diretiva `Sitemap:` do robots.txt e, em seguida,
caminhos conhecidos (/sitemap.xml, /sitemap_index.xml, /wp-sitemap.xml).

Para escapar de bloqueio de bot (403/429) usamos User-Agent de navegador e
retry com backoff exponencial.

Configuração por variáveis de ambiente:
- DATABASE_URL: conexão Postgres obrigatória.
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
import unicodedata
import xml.etree.ElementTree as ET
from collections import deque
from datetime import datetime
from typing import Any
from urllib.parse import parse_qs, urljoin, urlparse

import psycopg2
from psycopg2.extras import Json, execute_batch

from init_ingestion_tables import ensure_publisher_dead_ids, ensure_source_records
import requests
from bs4 import BeautifulSoup

SITEMAP_PATHS = ("/sitemap.xml", "/sitemap_index.xml", "/wp-sitemap.xml", "/sitemap-index.xml")
BOOK_PATH_TERMS = ("livro", "produto", "obra", "detalhe", "product", "/p/", "book")
# Segmento de caminho que indica uma PÁGINA de livro (precisa ter um slug/id depois):
# /livro/9788.../slug, /livro/1292, /produto/abc, /products/handle. Já /livros (índice)
# ou /produtos (categoria) NÃO são livro — viram listagem (pra seguir a paginação).
BOOK_SEGMENTS = {
    "livro", "livros", "produto", "produtos", "product", "products",
    "obra", "obras", "book", "books", "detalhe", "p",
}
# Extensão de asset estático (imagem/css/js/fonte/doc): Magento e afins guardam esses
# arquivos sob caminhos como /pub/media/catalog/product/cache/.../capa.jpg, que TEM o
# segmento "product" mas não é página de livro nenhuma — sem este filtro, o crawler
# (ubu, e qualquer loja Magento) enche o candidato de imagens, extrai 0 título de cada
# uma e nunca sobra orçamento (max_urls/max_attempts) pra achar a página de produto real.
_ASSET_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".ico", ".bmp",
    ".css", ".js", ".json", ".xml", ".woff", ".woff2", ".ttf", ".eot",
    ".pdf", ".zip", ".mp4", ".mp3",
}


def _is_static_asset(path: str) -> bool:
    dot = path.rfind(".")
    slash = path.rfind("/")
    if dot <= slash:
        return False
    return path[dot:] in _ASSET_EXTENSIONS
# Links de paginação (?page=2, /pagina/3 ...): sempre tratados como listagem a seguir.
PAGINATION_RE = re.compile(r"[?&](?:page|pagina|pg|start|offset)=\d+|/(?:page|pagina)/\d+", re.I)
# Caminhos que parecem livro mas são editorial/institucional (geram registros-lixo
# sem ISBN). Ex.: /blog/.../novo-livro..., /imprensa, /autor-detalhe.
EXCLUDE_PATH_TERMS = (
    "/blog", "noticia", "/news", "/tag/", "/categoria", "imprensa", "autor-detalhe",
    "/agenda", "/evento", "/release", "lancamentos", "/colecao", "/serie",
)
# Páginas de listagem para alargar o crawl quando o sitemap não serve.
LISTING_TERMS = (
    "livros", "catalogo", "catalogos", "categoria", "categorias", "colecao",
    "colecoes", "genero", "generos", "assunto", "assuntos", "autor", "autores",
    "lancamento", "lancamentos", "mais-vendidos", "selo", "selos", "tema", "temas",
    "novidades", "ficcao", "infantil", "produtos",
    # "livraria": seção de categorias da Ubu Editora (/livraria/literatura.html
    # etc.) — sem este termo o crawler nem enfileirava essas páginas de listagem
    # (não batia em nenhum LISTING_TERM nem em BOOK_SEGMENTS).
    "livraria",
)
# No crawl de HTML, não vale a pena seguir (não listam livros): conta, busca, blog...
CRAWL_SKIP_TERMS = (
    "/blog", "noticia", "/news", "/tag/", "imprensa", "autor-detalhe", "/agenda",
    "/evento", "/release", "/login", "/cadastro", "/carrinho", "/cart", "/checkout",
    "/minha-conta", "/conta", "/busca", "/search", "/wishlist", "/favoritos",
    "/contato", "/sobre", "/ajuda", "/politica", "/termos",
)
# Segmentos SINGULARES que indicam página de produto no crawl (plural vira listagem).
BOOK_SINGULAR_SEGMENTS = {"livro", "produto", "obra", "product", "book", "detalhe", "p"}
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
# Sessão compartilhada: alguns sites (ex.: cia_das_letras, ASP.NET clássico) validam
# rotas contra um cookie de sessão emitido na primeira resposta (home). requests.get()
# avulso não carrega cookies entre chamadas — a Session resolve isso e, de quebra,
# reaproveita conexões HTTP entre as páginas de uma mesma editora.
SESSION = requests.Session()
SESSION.headers.update(HEADERS)
# platform: "auto" tenta shopify -> vtex -> id_range -> sitemap -> html. Pode forçar uma só.
# group: separa as fontes entre os workflows de sync que rodam em PARALELO
# (cada workflow tem seu concurrency group próprio no Actions e filtra por
# PUBLISHER_GROUP). Sem "group" = "principal" (sync-publishers.yml).
SOURCES = [
    {
        # Plataforma custom (agência "Communiplex", não é uma API pública): a home
        # lista /livro/{ISBN}/{slug} e o ISBN vem da URL. O grid de cada página de
        # categoria (/Busca?categoria=...) é montado via JS/Angular, mas por trás
        # dele tem uma API JSON (POST action=buscar&categoria=...&pg=N) que devolve
        # os livros da página já estruturados — ver collect_via_categoria_json e
        # diagnosticar_paginacao_categoria. Tenta sitemap (não existe hoje) ->
        # categoria via JSON -> crawl HTML como fallback.
        "slug": "cia_das_letras",
        "name": "Companhia das Letras",
        "base_url": "https://www.companhiadasletras.com.br",
        "platforms": ["sitemap", "categoria_json", "html"],
        # group próprio (sync-publishers-cia.yml): a coleta via categoria_json
        # varre ~218 categorias × ~16 páginas com sleep entre elas, o que leva
        # bem mais tempo que as demais do principal (Shopify/sitemap/id_range,
        # que pulam o já-visto de graça). Isolada num workflow com cron a cada
        # 2h pra não segurar as editoras rápidas do principal.
        "group": "cia",
    },
    {
        "slug": "editora_34",
        "name": "Editora 34",
        "base_url": "https://www.editora34.com.br",
        "platform": "id_range",
        "id_template": "https://www.editora34.com.br/livro/{id}",
        "id_start": 1,
        # Faixa ampla: ~40% dos ids são páginas mortas (puladas de graça), então o
        # teto efetivo de livros reais fica bem abaixo do fim da faixa.
        "id_end": 3000,
        # group próprio (sync-publishers-editora34.yml): a faixa está esgotada
        # (~800 livros reais em 1–3000), então sem o cache de mortos ela re-baixava
        # ~2200 páginas mortas TODA execução (~37 min) — segurava o principal.
        # Isolada num cron espaçado; o cache de ids mortos (publisher_dead_ids)
        # faz as próximas execuções pularem tudo de graça.
        "group": "editora34",
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
    # ------------------------------------------------------------------
    # group=expansao — segunda leva de editoras comerciais
    # (sync-publishers-expansao.yml). Entram com platform=auto; a plataforma
    # real de cada uma é confirmada com o input diagnose=true do workflow
    # (a rede do ambiente de dev bloqueia os sites — ver README).
    # ------------------------------------------------------------------
    {
        "slug": "rocco",
        "name": "Rocco",
        "base_url": "https://www.rocco.com.br",
        "platform": "auto",
        "group": "expansao",
    },
    {
        "slug": "arqueiro",
        "name": "Editora Arqueiro",
        "base_url": "https://www.editoraarqueiro.com.br",
        "platform": "auto",
        "group": "expansao",
    },
    {
        "slug": "aleph",
        "name": "Editora Aleph",
        "base_url": "https://www.editoraaleph.com.br",
        "platform": "auto",
        "group": "expansao",
    },
    {
        "slug": "darkside",
        "name": "DarkSide Books",
        "base_url": "https://www.darksidebooks.com.br",
        "platform": "auto",
        "group": "expansao",
    },
    {
        "slug": "boitempo",
        "name": "Boitempo Editorial",
        "base_url": "https://www.boitempoeditorial.com.br",
        "platform": "auto",
        "group": "expansao",
    },
    {
        "slug": "ubu",
        "name": "Ubu Editora",
        "base_url": "https://www.ubueditora.com.br",
        "platform": "auto",
        "group": "expansao",
    },
    {
        "slug": "antofagica",
        "name": "Antofágica",
        "base_url": "https://antofagica.com.br",
        "platform": "auto",
        "group": "expansao",
    },
    {
        "slug": "carambaia",
        "name": "Carambaia",
        "base_url": "https://carambaia.com.br",
        "platform": "auto",
        "group": "expansao",
    },
    {
        "slug": "altabooks",
        "name": "Alta Books",
        "base_url": "https://www.altabooks.com.br",
        "platform": "auto",
        "group": "expansao",
    },
    {
        "slug": "lpm",
        "name": "L&PM Editores",
        "base_url": "https://www.lpm.com.br",
        "platform": "auto",
        "group": "expansao",
    },
    # ------------------------------------------------------------------
    # group=universitaria — editoras universitárias
    # (sync-publishers-universitarias.yml). Mesma regra: platform=auto até o
    # diagnose confirmar a plataforma de cada uma.
    # ------------------------------------------------------------------
    {
        "slug": "edusp",
        "name": "Edusp (USP)",
        "base_url": "https://www.edusp.com.br",
        "platform": "auto",
        "group": "universitaria",
    },
    {
        "slug": "editora_unesp",
        "name": "Editora Unesp",
        "base_url": "https://www.editoraunesp.com.br",
        "platform": "auto",
        "group": "universitaria",
    },
    {
        "slug": "editora_unicamp",
        "name": "Editora da Unicamp",
        "base_url": "https://www.editoraunicamp.com.br",
        "platform": "auto",
        "group": "universitaria",
    },
    {
        "slug": "editora_ufmg",
        "name": "Editora UFMG",
        "base_url": "https://www.editoraufmg.com.br",
        "platform": "auto",
        "group": "universitaria",
    },
    {
        "slug": "edufba",
        "name": "EDUFBA (UFBA)",
        "base_url": "https://edufba.ufba.br",
        "platform": "auto",
        "group": "universitaria",
    },
    {
        "slug": "editora_ufsc",
        "name": "Editora da UFSC",
        "base_url": "https://editora.ufsc.br",
        "platform": "auto",
        "group": "universitaria",
    },
    {
        "slug": "edipucrs",
        "name": "EDIPUCRS (PUCRS)",
        "base_url": "https://www.edipucrs.com.br",
        "platform": "auto",
        "group": "universitaria",
    },
    {
        "slug": "editora_unb",
        "name": "Editora UnB",
        "base_url": "https://editora.unb.br",
        "platform": "auto",
        "group": "universitaria",
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
        raise RuntimeError("DATABASE_URL deve apontar para Postgres.")
    return psycopg2.connect(normalized_url)


def connection_alive(conn) -> bool:
    """True se a conexão responde a um ping barato (SELECT 1).

    O Neon derruba conexões TCP ociosas e o upsert seguinte estourava com
    "SSL connection has been closed unexpectedly"; este ping detecta isso. Faz
    rollback depois para não deixar transação 'idle in transaction' pendurada.
    """
    if conn is None or conn.closed:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
        conn.rollback()
        return True
    except psycopg2.Error:
        try:
            conn.rollback()
        except psycopg2.Error:
            pass
        return False


def ensure_connection(conn):
    """Devolve uma conexão VIVA, reabrindo se a atual caiu.

    O scraping de cada editora leva minutos (centenas de páginas com sleep), e a
    conexão fica ociosa nesse meio-tempo. O Neon encerra conexões ociosas, então
    chamamos isto logo antes de cada operação de banco para reabrir quando preciso
    — assim o lote coletado não se perde por uma queda de socket.
    """
    if connection_alive(conn):
        return conn
    if conn is not None and not conn.closed:
        try:
            conn.close()
        except psycopg2.Error:
            pass
    return connect_database()


# Diagnóstico: por que extract_page() volta None em tanta URL (ex.: cia_das_letras
# teve 171/1264 de sucesso). Contadores + amostra de URLs, resetados por chamador
# via reset_fetch_diagnostics() — não custa nada às outras editoras.
FETCH_FAILURE_COUNTS: dict[str, int] = {}
FETCH_FAILURE_SAMPLES: dict[str, list[str]] = {}

# Status HTTP da ÚLTIMA chamada de fetch_url (0 = exceção de rede). Serve pro
# id_range distinguir uma página comprovadamente sem livro (200 soft-404 ou
# 404/410 → morto, dá pra nunca mais baixar) de uma falha transitória
# (403/429/5xx/timeout → NÃO marca morto, senão perderíamos um id bom numa
# oscilação do site).
LAST_FETCH_STATUS: int = 0

# IDs comprovadamente sem livro descobertos NESTA execução, por fonte
# (source -> {external_id}). Preenchido por collect_via_id_range e persistido
# por main() na tabela publisher_dead_ids, pra serem pulados de graça (igual ao
# `seen`) nas próximas execuções.
NEWLY_DEAD_IDS: dict[str, set[str]] = {}


def reset_fetch_diagnostics() -> None:
    FETCH_FAILURE_COUNTS.clear()
    FETCH_FAILURE_SAMPLES.clear()


def _record_fetch_failure(reason: str, url: str = "") -> None:
    FETCH_FAILURE_COUNTS[reason] = FETCH_FAILURE_COUNTS.get(reason, 0) + 1
    if url:
        samples = FETCH_FAILURE_SAMPLES.setdefault(reason, [])
        if len(samples) < 3:
            samples.append(url)


def fetch_url(url: str, accept: str | None = None, extra_headers: dict[str, str] | None = None) -> requests.Response | None:
    """GET com retry e backoff. Retorna None em falha definitiva (>=400 não-retryável)."""
    headers = dict(HEADERS)
    if extra_headers:
        headers.update(extra_headers)
    if accept:
        # Mantém a preferência (json/xml) mas aceita qualquer coisa: alguns servidores
        # (ex.: IIS) devolvem 404/406 a um Accept restritivo e escondem o sitemap.
        headers["Accept"] = f"{accept}, */*;q=0.1"
    global LAST_FETCH_STATUS
    for attempt in range(MAX_RETRIES):
        try:
            response = SESSION.get(url, headers=headers, timeout=REQUEST_TIMEOUT_SECONDS)
        except requests.RequestException as exc:
            # Host pendurado/inacessível não se recupera em 1s: não insiste (evita
            # acumular minutos de tempo morto × várias URLs por editora).
            print(f"Aviso: falha ao acessar {url}: {exc}", file=sys.stderr)
            _record_fetch_failure(f"exception:{type(exc).__name__}", url)
            LAST_FETCH_STATUS = 0  # exceção de rede = transitório
            return None
        if response.status_code in RETRYABLE_STATUS and attempt < MAX_RETRIES - 1:
            time.sleep(2 ** attempt)
            continue
        LAST_FETCH_STATUS = response.status_code
        if response.status_code >= 400:
            _record_fetch_failure(f"status:{response.status_code}", url)
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
    host = urlparse(base_url).netloc.replace("www.", "")
    sitemaps: list[str] = []
    for line in response.text.splitlines():
        if line.lower().startswith("sitemap:"):
            url = line.split(":", 1)[1].strip()
            # Só sitemap do MESMO domínio: alguns robots.txt (ex.: edufba.ufba.br)
            # anunciam o sitemap do site institucional pai (ufba.br), que não lista
            # os livros da editora e ainda pode falhar por certificado TLS distinto.
            if url and urlparse(url).netloc.replace("www.", "") == host:
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
    if _is_static_asset(path) or any(term in path for term in EXCLUDE_PATH_TERMS):
        return False
    segments = [seg for seg in path.split("/") if seg]
    # Livro = segmento conhecido (livro/produto/...) seguido de outro segmento (slug/id).
    for index, seg in enumerate(segments):
        if seg in BOOK_SEGMENTS and index < len(segments) - 1:
            return True
    # Mantém compatibilidade com padrões soltos (ex.: /p/123, /book123) via termos.
    if any(term in path for term in BOOK_PATH_TERMS) and not any(
        seg in BOOK_SEGMENTS for seg in segments
    ):
        return True
    return False


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


_AUTOR_LABEL_RE = re.compile(r"Autor(?:\(a\)|es)?\s*[:\-]\s*([A-ZÀ-Ý][^\n|·•]{2,60})")


def extract_author_from_text(text: str) -> str:
    """Padrão comum em e-commerce de livro: "Autor: Fulano" solto no texto
    (descrição do produto, corpo da página etc.)."""
    match = _AUTOR_LABEL_RE.search(text or "")
    return match.group(1).strip() if match else ""


def extract_author_from_soup(soup: BeautifulSoup, bookish: dict[str, Any]) -> str:
    author = first_text(bookish.get("author") or bookish.get("creator"))
    if author:
        return author
    for prop in ("book:author", "author", "og:author", "article:author"):
        value = meta_content(soup, prop)
        if value and not value.lower().startswith("http"):
            return value
    return extract_author_from_text(soup.get_text(" ", strip=True))


# Marcadores que, no bloco do título da Editora 34, vêm DEPOIS do nome do autor
# (o layout é: "{título} {autor} Tradução de ... ISBN ... {ano}"). O autor é o
# trecho entre o fim do título e o primeiro destes marcadores (ou o 1º dígito).
_ED34_MARCADOR = re.compile(
    r"(Tradu[çc][ãa]o|Ilustra[çc][õo]es|Organiza[çc][ãa]o|Sele[çc][ãa]o|"
    r"Introdu[çc][ãa]o|Pref[áa]cio|Posf[áa]cio|Apresenta[çc][ãa]o|Notas|"
    r"Edi[çc][ãa]o|Cole[çc][ãa]o|ISBN|R\$|\d|—)",
    re.I,
)
# Primeira palavra que denuncia subtítulo (não é nome de autor).
_ED34_NAO_AUTOR = {
    "poemas", "poema", "poesia", "poesias", "contos", "conto", "antologia",
    "obras", "obra", "romance", "romances", "ensaios", "ensaio", "cartas",
    "teatro", "crônicas", "cronicas", "diário", "diario", "volume", "novelas",
    "novela", "correspondência", "correspondencia", "memórias", "memorias",
}


def autor_editora34(soup: BeautifulSoup) -> str:
    """Extrai o autor no layout da Editora 34, que não tem JSON-LD/meta/label.

    No container (parent) do <h1> o texto é "{título} {autor} Tradução de ...";
    então tiramos o título do começo e pegamos o trecho até o primeiro marcador
    de metadado da edição. Livros só "organizados" (sem autor) caem para "".
    """
    h1 = soup.find("h1")
    if not h1 or not h1.parent:
        return ""
    titulo = " ".join(h1.get_text(" ", strip=True).split())
    bloco = " ".join(h1.parent.get_text(" ", strip=True).split())
    if not titulo or not bloco.lower().startswith(titulo.lower()):
        return ""
    resto = bloco[len(titulo):].strip()
    m = _ED34_MARCADOR.search(resto)
    autor = (resto[:m.start()] if m else resto).strip(" -–—·|,;").strip()
    if not (2 <= len(autor) <= 60 and re.match(r"[A-ZÀ-Ý]", autor)):
        return ""
    # Rejeita subtítulos que vazam pro lugar do autor (o h1 traz só o título
    # principal): "Poemas escolhidos ...", "Contos reunidos ...", "Antologia ...".
    primeira = autor.split()[0].lower()
    if primeira in _ED34_NAO_AUTOR or re.search(r"\b(escolhid|reunid|complet|selecionad)", autor, re.I):
        return ""
    return autor


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


_NOME_CONECTORES_PT = {"de", "da", "do", "dos", "das", "e"}
# palavras comuns em SUBTÍTULO (não em nome de autor) — evita que algo como
# "O Iluminismo Radical - As Origens Intelectuais da Democracia" seja lido
# como se "As Origens Intelectuais da Democracia" fosse um nome de pessoa.
_PALAVRAS_SUBTITULO_PT = {
    "historia", "guia", "manual", "ensaio", "ensaios", "reflexao", "reflexoes",
    "introducao", "origem", "origens", "teoria", "arte", "ciencia", "filosofia",
    "sociedade", "cultura", "mundo", "vida", "poder", "tempo", "memoria",
    "verdade", "liberdade", "revolucao", "epoca", "seculo", "romance",
    "contos", "poemas", "cronicas", "biografia", "obra", "volume", "uma", "um",
    "as", "os",
}


def _sem_acento(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c))


def parece_nome_de_pessoa(segmento: str) -> bool:
    palavras = segmento.split()
    # exige nome E sobrenome — um segmento de 1 palavra só é ambíguo demais
    # com subtítulo de uma palavra (ex.: "Grande Sertão - Veredas").
    if not (2 <= len(palavras) <= 4):
        return False
    if any(ch.isdigit() for ch in segmento):
        return False
    for p in palavras:
        limpo = re.sub(r"[^\wÀ-ÿ]", "", p)
        if not limpo:
            return False
        if limpo.lower() in _NOME_CONECTORES_PT:
            continue
        if _sem_acento(limpo.lower()) in _PALAVRAS_SUBTITULO_PT:
            return False
        if not limpo[0].isupper():
            return False
    return True


def dividir_titulo_autor_cia_das_letras(title: str) -> tuple[str, str]:
    """Nas páginas de livro da Cia das Letras o <title>/h1 vem como "{Título} —
    {Autor}", sem JSON-LD nem meta de autor (confirmado: coleta real trouxe
    ISBN 171/171 mas autor só 1/171, com títulos tipo "Seja ousado - Ranjay
    Gulati"). Separa o autor quando o último segmento parece um nome próprio;
    senão deixa o título como está — mais seguro não separar do que cortar um
    subtítulo legítimo por engano."""
    partes = re.split(r"\s+[\-|–—]\s+", title)
    if len(partes) < 2:
        return title, ""
    candidato = partes[-1].strip()
    if parece_nome_de_pessoa(candidato):
        return " - ".join(partes[:-1]).strip(), candidato
    return title, ""


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
    if not author and publisher.get("slug") == "editora_34":
        author = autor_editora34(soup)
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
    if not author and publisher.get("slug") == "cia_das_letras":
        title, author = dividir_titulo_autor_cia_das_letras(title)

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

    if not title.strip():
        _record_fetch_failure("titulo_vazio", url)

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


def _isbn_de_variantes(variants: list[dict[str, Any]]) -> str:
    return (
        next((norm_isbn(v.get("barcode")) for v in variants if norm_isbn(v.get("barcode"))), "")
        or next((norm_isbn(v.get("sku")) for v in variants if norm_isbn(v.get("sku"))), "")
    )


def _vendor_e_a_propria_editora(vendor: str, publisher_name: str) -> bool:
    """"vendor" no Shopify costuma ser o selo/editora, não o autor do livro —
    confirmado na prática: Record e Sextante tinham vendor="Editora Record"/
    "Editora Sextante" em 100% dos produtos, o que geraria autor=editora se
    usado direto. Descarta o vendor quando ele é só a própria editora (mais
    genérica que específica: não pega imprints diferentes do nome principal,
    mas evita o caso confirmado)."""
    if not vendor:
        return False
    palavras_editora = {_sem_acento(w) for w in re.findall(r"\w+", publisher_name.lower()) if len(w) > 2}
    palavras_editora |= {"grupo", "editora", "selo", "livraria", "editorial"}
    palavras_vendor = {_sem_acento(w) for w in re.findall(r"\w+", vendor.lower())}
    return bool(palavras_vendor) and palavras_vendor <= palavras_editora


def _isbn_via_produto_unico(base_url: str, handle: str, sleep_seconds: float) -> str:
    """Fallback quando a listagem em lote (/products.json) não trouxe barcode/sku —
    algumas lojas (ex.: sextante.com.br) omitem barcode do endpoint de listagem mas
    incluem no endpoint de produto único (/products/{handle}.json). 1 request a mais
    só quando os outros sinais falharam, então não pesa nas lojas que já funcionam
    (ex.: record.com.br) via listagem."""
    if not handle:
        return ""
    data = fetch_json(f"{base_url}/products/{handle}.json")
    if sleep_seconds:
        time.sleep(sleep_seconds / 4)
    if not isinstance(data, dict):
        return ""
    variants = (data.get("product") or {}).get("variants") or []
    return _isbn_de_variantes(variants)


def collect_via_shopify(
    publisher: dict[str, str],
    max_urls: int,
    sleep_seconds: float,
    seen: set[str] | None = None,
    offset: int | None = None,
) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    seen = seen or set()
    base_url = publisher["base_url"].rstrip("/")
    records: list[tuple[dict[str, Any], dict[str, Any]]] = []
    index = -1  # posição do produto no catálogo (p/ modo faixa)
    for page in range(1, 21):
        data = fetch_json(f"{base_url}/products.json?limit=250&page={page}")
        if not isinstance(data, dict):
            break
        products = data.get("products") or []
        if not products:
            break
        for product in products:
            index += 1
            if offset is not None and index < offset:
                continue  # ainda antes da faixa pedida
            handle = product.get("handle", "")
            url = f"{base_url}/products/{handle}"
            if offset is None and stable_external_id(url) in seen:
                continue  # incremental: já ingerido em run anterior
            variants = product.get("variants") or []
            description_full = BeautifulSoup(product.get("body_html") or "", "html.parser").get_text(" ", strip=True)
            description = description_full[:600]
            # barcode é o campo "certo", mas muita loja de livro (ex.: record.com.br)
            # deixa barcode vazio e põe o ISBN no sku da variante — cai pra descrição,
            # depois pro endpoint de produto único (mais lento, só quando precisa) e
            # pra própria URL só como último recurso.
            isbn = (
                _isbn_de_variantes(variants)
                or extract_isbn(description)
                or _isbn_via_produto_unico(base_url, handle, sleep_seconds)
                or isbn_from_url(url)
            )
            images = product.get("images") or []
            thumbnail = (images[0].get("src") if images else "") or ""
            year = extract_year(str(product.get("published_at") or ""))
            # "vendor" no Shopify costuma ser o selo/editora (ex.: "Record",
            # "Bertrand Brasil"), não o autor do livro — só serve de último
            # recurso, e nunca quando é claramente a própria editora (ver
            # _vendor_e_a_propria_editora). Preferimos um "Autor: Fulano"
            # explícito na descrição.
            vendor = (product.get("vendor") or "").strip()
            author = extract_author_from_text(description_full)
            if not author and vendor and not _vendor_e_a_propria_editora(vendor, publisher["name"]):
                author = vendor
            record = build_record(
                publisher,
                url,
                title=product.get("title") or "",
                author=author,
                isbn=isbn,
                year=year,
                thumbnail=thumbnail,
                description=description,
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
    publisher: dict[str, str],
    max_urls: int,
    sleep_seconds: float,
    seen: set[str] | None = None,
    offset: int | None = None,
) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    seen = seen or set()
    base_url = publisher["base_url"].rstrip("/")
    records: list[tuple[dict[str, Any], dict[str, Any]]] = []
    step = 50
    index = -1
    # Em modo faixa, começa a paginar já perto do offset (passos de 50).
    start_at = (offset // step * step) if offset is not None else 0
    if offset is not None:
        index = start_at - 1
    for start in range(start_at, start_at + 2500, step):
        url = f"{base_url}/api/catalog_system/pub/products/search?_from={start}&_to={start + step - 1}"
        data = fetch_json(url)
        if not isinstance(data, list) or not data:
            break
        for product in data:
            index += 1
            if offset is not None and index < offset:
                continue
            link = product.get("link") or (
                f"{base_url}/{product['linkText']}/p" if product.get("linkText") else base_url
            )
            if offset is None and stable_external_id(link) in seen:
                continue  # incremental: já ingerido em run anterior
            items = product.get("items") or []
            isbn = ""
            thumbnail = ""
            for item in items:
                isbn = isbn or norm_isbn(item.get("ean"))
                images = item.get("images") or []
                thumbnail = thumbnail or (images[0].get("imageUrl") if images else "")
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


def valid_extracted_record(extracted: tuple[dict[str, Any], dict[str, Any]] | None) -> bool:
    """Filtro mínimo anti-lixo: precisa ter título e permalink http(s)."""
    if extracted is None:
        return False
    normalized, _ = extracted
    permalink = str(normalized.get("permalink") or "").strip()
    parsed = urlparse(permalink)
    return bool(str(normalized.get("title") or "").strip() and parsed.scheme in {"http", "https"} and parsed.netloc)


def collect_via_id_range(
    publisher: dict[str, Any],
    max_urls: int,
    sleep_seconds: float,
    seen: set[str] | None = None,
    offset: int | None = None,
) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    """Enumera URLs numéricas configuradas em id_template/id_start/id_end.

    Em modo incremental, IDs já vistos em source_records (ou já marcados como
    mortos em publisher_dead_ids — ambos chegam em `seen`) são pulados sem
    download; os que baixarem e não tiverem livro entram na lista de mortos
    novos (NEWLY_DEAD_IDS) pra nunca mais serem baixados.
    Em modo faixa, offset é a posição zero-based dentro da faixa configurada.
    """
    seen = seen or set()
    id_template = str(publisher.get("id_template") or "").strip()
    if "{id}" not in id_template:
        print(f"  [id_range] id_template inválido para {publisher['slug']}: {id_template!r}")
        return []

    id_start = int(publisher.get("id_start") or 1)
    id_end = int(publisher.get("id_end") or id_start)
    if id_end < id_start:
        print(f"  [id_range] faixa inválida para {publisher['slug']}: {id_start}–{id_end}")
        return []

    # id_range varre MUITOS ids numa fonte só (não é crawl de páginas de um
    # catálogo grande), então uma pausa menor acelera bastante a varredura sem
    # martelar o site — cap de 0.3s por padrão, editora pode sobrescrever com
    # id_sleep_seconds, e nunca ultrapassa o sleep global pedido.
    id_sleep = float(publisher.get("id_sleep_seconds", min(sleep_seconds, 0.3)))

    records: list[tuple[dict[str, Any], dict[str, Any]]] = []
    attempted = 0
    valid_pages = 0
    with_isbn = 0
    with_author = 0
    dead_new: set[str] = set()  # ids que baixaram e comprovadamente não têm livro

    if offset is not None:
        first_id = id_start + offset
        last_id = min(id_end, first_id + max_urls - 1)
        candidate_ids = range(first_id, last_id + 1) if first_id <= id_end else range(0)
        print(f"  [id_range] faixa: offset={offset} ids={first_id}–{last_id} de {id_start}–{id_end}")
    else:
        candidate_ids = range(id_start, id_end + 1)

    for numeric_id in candidate_ids:
        if offset is None and len(records) >= max_urls:
            break
        url = id_template.format(id=numeric_id)
        external_id = stable_external_id(url)
        if offset is None and external_id in seen:
            continue

        attempted += 1
        extracted = extract_page(url, publisher)
        if valid_extracted_record(extracted):
            normalized, raw = extracted
            valid_pages += 1
            with_isbn += 1 if normalized["isbn"] else 0
            with_author += 1 if normalized["author"] else 0
            records.append((normalized, raw))
        elif offset is None and (LAST_FETCH_STATUS == 200 or LAST_FETCH_STATUS in (404, 410)):
            # Baixou (200 sem livro) ou 404/410 (não existe): id morto de verdade.
            # 403/429/5xx/timeout NÃO entram aqui (poderia ser oscilação do site).
            # Só no modo incremental — o modo faixa é re-scrape manual e ignora
            # o cache de mortos de propósito (é a via de recuperação se um id bom
            # for marcado morto por engano).
            dead_new.add(external_id)
        if id_sleep:
            time.sleep(id_sleep)

    if dead_new:
        NEWLY_DEAD_IDS[f"publisher:{publisher['slug']}"] = dead_new

    print(
        "  [id_range] "
        f"ids_tentados={attempted} paginas_validas={valid_pages} "
        f"isbn={with_isbn}/{valid_pages} autor={with_author}/{valid_pages} "
        f"mortos_novos={len(dead_new)}"
    )
    return records


def _collect_from_urls(
    book_urls: list[str],
    publisher: dict[str, str],
    max_urls: int,
    sleep_seconds: float,
    seen: set[str] | None = None,
    offset: int | None = None,
) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    """Baixa páginas de livro do catálogo.

    - Modo FAIXA (offset != None): pega exatamente a fatia [offset : offset+max_urls]
      da lista ordenada de candidatos. Serve p/ ir "0-100, 101-200..." na mão.
    - Modo INCREMENTAL (offset None): pula as já ingeridas (seen) e leva as próximas
      max_urls novas. O teto conta só downloads; pular URL conhecida é de graça.
    """
    if offset is not None:
        window = book_urls[offset : offset + max_urls]
        print(f"  faixa: {offset}–{offset + len(window) - 1} de {len(book_urls)} candidatos")
        records: list[tuple[dict[str, Any], dict[str, Any]]] = []
        local_seen: set[str] = set()
        for url in window:
            external_id = stable_external_id(url)
            if external_id in local_seen:
                continue
            local_seen.add(external_id)
            extracted = extract_page(url, publisher)
            if extracted is not None:
                records.append(extracted)
            if sleep_seconds:
                time.sleep(sleep_seconds)
        return records

    seen = seen or set()
    records = []
    local_seen = set()
    fetched = 0
    max_attempts = max_urls * 3
    for url in book_urls:
        if len(records) >= max_urls or fetched >= max_attempts:
            break
        external_id = stable_external_id(url)
        if external_id in seen or external_id in local_seen:
            continue
        local_seen.add(external_id)
        fetched += 1
        extracted = extract_page(url, publisher)
        if extracted is None:
            continue
        records.append(extracted)
        if sleep_seconds:
            time.sleep(sleep_seconds)
    return records


def collect_via_sitemap(
    publisher: dict[str, str],
    max_urls: int,
    sleep_seconds: float,
    seen: set[str] | None = None,
    offset: int | None = None,
) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    sitemap_urls = collect_sitemap_urls(publisher["base_url"])
    if not sitemap_urls:
        print(f"  [sitemap] nenhum sitemap acessível para {publisher['slug']} ({publisher['base_url']}).")
        return []
    book_urls = [url for url in sitemap_urls if looks_like_book_url(url)]
    print(f"  [sitemap] urls={len(sitemap_urls)} candidatos_livro={len(book_urls)}")
    return _collect_from_urls(book_urls, publisher, max_urls, sleep_seconds, seen, offset)


def _is_book_path(path: str) -> bool:
    """Página de produto: segmento singular conhecido seguido de slug/id."""
    if _is_static_asset(path):
        return False
    segments = [seg for seg in path.split("/") if seg]
    return any(
        seg in BOOK_SINGULAR_SEGMENTS and index < len(segments) - 1
        for index, seg in enumerate(segments)
    )


def harvest_links(html: str, base_url: str) -> tuple[list[str], list[str]]:
    """Separa links internos em (urls_de_livro, urls_de_listagem).

    Ordem importa: paginação e termos de listagem (incl. plurais como /livros) vêm
    antes do teste de livro, pra que categorias/paginação sejam seguidas e só as
    páginas de produto (/livro/{x}) sejam coletadas.

    Nota sobre cia_das_letras: chegamos a seguir /busca?categoria=... de propósito
    (o menu de categorias da home é estático e ISSO é onde a navegação mora), mas
    testado ao vivo o resultado piorou (131 livros contra o platô de ~255) — a
    PÁGINA DE RESULTADO em si vem com template não renderizado no HTML bruto
    (ex.: "{{ extras.anoMin }}" literal), ou seja o grid de livros é populado via
    JS/AJAX depois do load. Revertido; ver README (Companhia das Letras) pro
    diagnóstico completo.
    """
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
        if any(term in path for term in CRAWL_SKIP_TERMS):
            continue
        if PAGINATION_RE.search(clean) or any(term in path for term in LISTING_TERMS):
            listing_urls.append(clean)
        elif _is_book_path(path):
            book_urls.append(clean)
    return list(dict.fromkeys(book_urls)), list(dict.fromkeys(listing_urls))


def collect_via_html_crawl(
    publisher: dict[str, str],
    max_urls: int,
    sleep_seconds: float,
    seen: set[str] | None = None,
    offset: int | None = None,
) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    """Fallback p/ sites sem sitemap/JSON: BFS a partir da home, seguindo categorias
    e PAGINAÇÃO (?page=2...) pra descobrir o catálogo fundo, não só os destaques."""
    base_url = publisher["base_url"].rstrip("/")
    home = fetch_url(base_url + "/")
    if home is None:
        print(f"  [html] home inacessível para {publisher['slug']}.")
        return []

    seen = seen or set()
    needed = (offset or 0) + max_urls
    # Modo faixa precisa da lista ordenada inteira até offset+max_urls.
    target = max(max_urls * 5, needed * 2)
    max_pages = max(60, min(250, target // 4))      # teto de páginas de listagem visitadas

    book_urls: list[str] = []
    book_set: set[str] = set()
    enqueued: set[str] = set()
    visited: set[str] = set()
    queue: deque[str] = deque()
    new_found = 0  # URLs de livro ainda NÃO ingeridas (avança a fronteira no incremental)

    def absorb(html_text: str) -> None:
        nonlocal new_found
        books, listings = harvest_links(html_text, base_url)
        for url in books:
            if url not in book_set:
                book_set.add(url)
                book_urls.append(url)
                if offset is None and stable_external_id(url) not in seen:
                    new_found += 1
        for url in listings:
            if url not in enqueued:
                enqueued.add(url)
                queue.append(url)

    def enough() -> bool:
        # Incremental: para ao achar livros novos suficientes (frente avança a cada run).
        # Faixa: junta URLs bastante pra conseguir fatiar [offset : offset+max_urls].
        return len(book_urls) >= target if offset is not None else new_found >= needed

    absorb(home.text)
    pages = 0
    while queue and pages < max_pages and not enough():
        listing_url = queue.popleft()
        if listing_url in visited:
            continue
        visited.add(listing_url)
        resp = fetch_url(listing_url)
        pages += 1
        if resp is not None:
            absorb(resp.text)
        if sleep_seconds:
            time.sleep(sleep_seconds)

    extra = "" if offset is not None else f" novos~{new_found}"
    print(f"  [html] urls_livro={len(book_urls)}{extra} (visitou {pages} páginas de listagem)")
    return _collect_from_urls(book_urls, publisher, max_urls, sleep_seconds, seen, offset)


def _categoria_urls_da_home(publisher: dict[str, str]) -> list[str]:
    """Páginas /Busca?categoria=... linkadas no menu da home (HTML estático,
    não precisa de browser pra achar os links em si — só o GRID de cada
    página de categoria é que precisa de Playwright)."""
    base_url = publisher["base_url"].rstrip("/")
    home = fetch_url(base_url + "/")
    if home is None:
        return []
    host = urlparse(base_url).netloc.replace("www.", "")
    soup = BeautifulSoup(home.text, "html.parser")
    categoria_urls: list[str] = []
    for anchor in soup.find_all("a", href=True):
        full = urljoin(base_url, anchor["href"]).split("#", 1)[0]
        parsed = urlparse(full)
        if parsed.netloc.replace("www.", "") != host:
            continue
        query = parsed.query.lower()
        if "/busca" in parsed.path.lower() and "categoria=" in query and full not in categoria_urls:
            categoria_urls.append(full)
    return categoria_urls


def diagnosticar_paginacao_categoria(url: str) -> None:
    """Investiga por que collect_via_categoria_playwright só achava ~6
    livros/categoria em média (1374 no total, pra Cia das Letras): visita UMA
    página de categoria de verdade, mede quantos links /livro/ aparecem no
    primeiro render, e testa se rolar a página carrega mais (infinite
    scroll) e se existem controles de paginação (?pagina=N, botão "carregar
    mais"/"próxima") que o crawl atual ignora por só olhar o primeiro render."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(user_agent=HEADERS["User-Agent"])

        # Captura chamadas xhr/fetch feitas durante o carregamento — se o
        # grid é montado por Angular chamando uma API JSON por trás, é aqui
        # que aparece o endpoint real de paginação (parâmetro page/skip/take
        # etc.), que nenhum controle visível na página revelou.
        chamadas: list[Any] = []

        def registrar_resposta(response: Any) -> None:
            try:
                if response.request.resource_type in ("xhr", "fetch"):
                    chamadas.append(response)
            except Exception:  # noqa: BLE001
                pass

        page.on("response", registrar_resposta)
        page.goto(url, timeout=20000, wait_until="domcontentloaded")
        try:
            page.wait_for_selector("a[href*='/livro/']", timeout=8000)
        except Exception as exc:  # noqa: BLE001 — segue mesmo sem o seletor, pra medir 0 livros
            print(f"  [diag] seletor de livro não apareceu: {exc!r}")

        def contar_livros() -> int:
            return len(set(re.findall(r'href="([^"]*?/livro/[^"]*?)"', page.content())))

        print(f"  [diag] url={url}")
        contagem = contar_livros()
        print(f"  [diag] livros após 1o carregamento: {contagem}")

        for i in range(6):
            page.mouse.wheel(0, 20000)
            page.wait_for_timeout(1500)
            nova = contar_livros()
            delta = nova - contagem
            print(f"  [diag] após scroll #{i + 1}: {nova} livros ({'+' if delta >= 0 else ''}{delta})")
            contagem = nova

        html = page.content()
        paginas = sorted({int(n) for n in re.findall(r"[?&](?:pagina|page)=(\d+)", html, re.I)})
        print(f"  [diag] números de página em hrefs: {paginas[:20]}")

        botoes = page.locator("button, a").filter(has_text=re.compile("pr[oó]xim|carregar mais|ver mais|mais resultados", re.I))
        try:
            n_botoes = botoes.count()
        except Exception as exc:  # noqa: BLE001
            n_botoes = 0
            print(f"  [diag] erro procurando botões de paginação: {exc!r}")
        print(f"  [diag] botões/links tipo 'próxima página'/'carregar mais': {n_botoes}")
        for i in range(min(n_botoes, 5)):
            try:
                print(f"    - {botoes.nth(i).text_content()!r}")
            except Exception:  # noqa: BLE001
                pass

        texto = BeautifulSoup(html, "html.parser").get_text(" ", strip=True)
        m = re.search(r"(\d{1,5})\s*(resultados?|livros?|itens?)\b", texto, re.I)
        if m:
            print(f"  [diag] texto de contagem total na página: {m.group(0)!r}")

        print(f"  [diag] chamadas xhr/fetch capturadas: {len(chamadas)}")
        for resp in chamadas[:15]:
            print(f"    - {resp.request.method} {resp.url} -> status={resp.status}")
            if resp.request.method == "POST":
                try:
                    print(f"      post_data={resp.request.post_data!r}")
                except Exception:  # noqa: BLE001
                    pass
            try:
                corpo = resp.json()
                amostra = json.dumps(corpo, ensure_ascii=False)[:600]
                print(f"      json[:600]={amostra!r}")
            except Exception:  # noqa: BLE001 — resposta não-JSON ou já consumida, ignora
                pass

        browser.close()


def _categoria_valor(url: str) -> str:
    """Decodifica o parâmetro 'categoria' da URL da página de listagem.

    A home usa Latin-1 nos hrefs (ex.: %E7=ç, %F3=ó), diferente do UTF-8 que
    o corpo do POST espera (ver diagnosticar_paginacao_categoria) — por isso
    o decode explícito aqui em vez de deixar o default (utf-8) do parse_qs.
    """
    valores = parse_qs(urlparse(url).query, encoding="latin-1")
    return (valores.get("categoria") or [""])[0]


def _buscar_pagina_categoria_json(url: str, categoria: str, pg: int) -> dict[str, Any] | None:
    """POST que alimenta o grid da página de categoria — descoberto via
    diagnosticar_paginacao_categoria: a própria página faz `action=buscar` +
    `categoria` + `pg=N` de volta pra si mesma e recebe os livros já
    estruturados (título, autor(es), ISBN via link, selo) em JSON."""
    try:
        response = SESSION.post(
            url,
            data={
                "action": "buscar",
                "categoria": categoria,
                "pg": pg,
                "anoMin": 1900,
                "anoMax": datetime.now().year + 1,
                "idadeMax": 18,
                "ordem": "cronologica",
            },
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        print(f"Aviso: falha ao buscar {url} pg={pg}: {exc}", file=sys.stderr)
        return None
    if response.status_code >= 400:
        return None
    try:
        return response.json()
    except ValueError:
        return None


def _normaliza_titulo_caixa_alta(title: str) -> str:
    """A API JSON devolve 'titulo' em CAIXA ALTA; a página de livro (fonte
    anterior, via extract_page) vinha em minúsculas com só a inicial maiúscula
    (ver amostras em DividirTituloAutorCiaDasLetrasTest) -- normaliza aqui pra
    não regredir a formatação já exibida no catálogo."""
    if title and title == title.upper() and title != title.lower():
        return title.capitalize()
    return title


def _monta_registro_categoria_json(
    livro: dict[str, Any], publisher: dict[str, str], categoria: str
) -> tuple[dict[str, Any], dict[str, Any]] | None:
    base_url = publisher["base_url"].rstrip("/")
    link = str(livro.get("link") or "").strip()
    if not link:
        return None
    url = urljoin(base_url + "/", link.lstrip("/"))
    autores = livro.get("autores") or []
    autor = ", ".join(
        str(a.get("nome") or "").strip() for a in autores if isinstance(a, dict) and a.get("nome")
    )
    titulo = _normaliza_titulo_caixa_alta(str(livro.get("titulo") or "").strip())
    return build_record(
        publisher,
        url,
        title=clean_title(titulo, publisher["name"]),
        author=autor,
        isbn=isbn_from_url(url),
        thumbnail=str(livro.get("capa") or "").strip(),
        structured=True,
        raw_extra={"platform": "categoria_json", "categoria": categoria, "selo": livro.get("selo")},
    )


def collect_via_categoria_json(
    publisher: dict[str, str],
    max_urls: int,
    sleep_seconds: float,
    seen: set[str] | None = None,
    offset: int | None = None,
) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    """Isolado pra cia_das_letras (não usado por nenhuma outra editora).

    Substitui a versão anterior baseada em Playwright: em vez de renderizar
    o grid via Chromium e depois baixar o HTML de cada livro individualmente
    (extract_page, com ~35% de falha por página), aqui vamos direto na API
    JSON que alimenta o grid (ver diagnosticar_paginacao_categoria) — cada
    página de categoria já devolve os livros da página, com título,
    autor(es) e link (de onde tiramos o ISBN), sem precisar de browser nem
    de uma segunda requisição por livro.
    """
    categoria_urls = _categoria_urls_da_home(publisher)
    if not categoria_urls:
        print(f"  [categoria-json] nenhuma página de categoria encontrada na home de {publisher['slug']}.")
        return []
    print(f"  [categoria-json] {len(categoria_urls)} categorias na home")

    seen = seen or set()
    needed = (offset or 0) + max_urls
    target = max(max_urls * 5, needed * 2)

    candidatos: list[tuple[str, dict[str, Any], str]] = []  # (external_id, livro, categoria)
    book_set: set[str] = set()
    new_found = 0

    def enough() -> bool:
        return len(candidatos) >= target if offset is not None else new_found >= needed

    paginas_consultadas = 0
    for url in categoria_urls:
        if enough():
            break
        categoria = _categoria_valor(url)
        pg = 1
        total_pages = 1
        while pg <= total_pages and not enough():
            data = _buscar_pagina_categoria_json(url, categoria, pg)
            paginas_consultadas += 1
            if not isinstance(data, dict):
                break
            total_pages = int(data.get("totalPages") or 1)
            for livro in data.get("livros") or []:
                link = str(livro.get("link") or "").strip()
                if not link or link in book_set:
                    continue
                book_set.add(link)
                external_id = stable_external_id(urljoin(publisher["base_url"].rstrip("/") + "/", link.lstrip("/")))
                candidatos.append((external_id, livro, categoria))
                if offset is None and external_id not in seen:
                    new_found += 1
            pg += 1
            if sleep_seconds:
                time.sleep(sleep_seconds)

    extra = "" if offset is not None else f" novos~{new_found}"
    print(
        f"  [categoria-json] livros_descobertos={len(candidatos)}{extra} "
        f"(páginas de categoria consultadas: {paginas_consultadas})"
    )

    if offset is not None:
        janela = candidatos[offset : offset + max_urls]
    else:
        janela = []
        local_seen: set[str] = set()
        for external_id, livro, categoria in candidatos:
            if len(janela) >= max_urls:
                break
            if external_id in seen or external_id in local_seen:
                continue
            local_seen.add(external_id)
            janela.append((external_id, livro, categoria))

    records: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for _external_id, livro, categoria in janela:
        record = _monta_registro_categoria_json(livro, publisher, categoria)
        if record:
            records.append(record)
    return records


PLATFORM_COLLECTORS = {
    "shopify": collect_via_shopify,
    "vtex": collect_via_vtex,
    "id_range": collect_via_id_range,
    "sitemap": collect_via_sitemap,
    "html": collect_via_html_crawl,
    "categoria_json": collect_via_categoria_json,
}
AUTO_ORDER = ["shopify", "vtex", "id_range", "sitemap", "html"]


def collect_publisher(
    publisher: dict[str, str],
    max_urls: int,
    sleep_seconds: float,
    seen: set[str] | None = None,
    offset: int | None = None,
) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    # `platforms` (lista) permite uma ordem explícita de métodos com fallback:
    # ex.: ["sitemap", "html"] tenta o sitemap e, se não render nada, cai no crawl.
    platforms = publisher.get("platforms")
    if isinstance(platforms, (list, tuple)) and platforms:
        order = [p for p in platforms if p in PLATFORM_COLLECTORS]
    else:
        platform = publisher.get("platform", "auto")
        order = [platform] if platform in PLATFORM_COLLECTORS else AUTO_ORDER
    for name in order:
        collector = PLATFORM_COLLECTORS[name]
        try:
            records = collector(publisher, max_urls, sleep_seconds, seen, offset)
        except Exception as exc:  # noqa: BLE001 — uma plataforma falhar não derruba as outras
            print(f"  [{name}] erro: {exc!r}", file=sys.stderr)
            continue
        if records:
            print(f"  método={name} registros={len(records)}")
            return records
    print(f"  nenhum método retornou registros para {publisher['slug']}.")
    return []


def load_seen_external_ids(conn, source: str) -> set[str]:
    """external_ids já gravados p/ esta fonte — base da ingestão incremental."""
    with conn.cursor() as cur:
        cur.execute("SELECT external_id FROM source_records WHERE source = %s", (source,))
        return {row[0] for row in cur.fetchall()}


def ensure_dead_ids_table(conn) -> None:
    """Cache de IDs comprovadamente sem livro (só do id_range), owned por este
    script — não passa pelo migrar() do app. Evita re-baixar toda execução as
    páginas mortas de uma faixa numérica esgotada (ex.: editora_34, ~2200 ids
    mortos em 1–3000). Só cria se ainda não existe."""
    with conn.cursor() as cur:
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


def load_dead_external_ids(conn, source: str) -> set[str]:
    """external_ids já marcados como mortos p/ esta fonte — pulados de graça,
    somados ao `seen`. Tolera a tabela ainda não existir (1ª execução)."""
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT external_id FROM publisher_dead_ids WHERE source = %s", (source,))
            return {row[0] for row in cur.fetchall()}
    except psycopg2.Error:
        conn.rollback()
        return set()


def upsert_dead_ids(conn, source: str, dead: set[str]) -> int:
    """Grava os IDs mortos novos (ON CONFLICT DO NOTHING: idempotente)."""
    if not dead:
        return 0
    with conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO publisher_dead_ids (source, external_id) VALUES (%s, %s) "
            "ON CONFLICT (source, external_id) DO NOTHING",
            [(source, external_id) for external_id in dead],
        )
    conn.commit()
    return len(dead)


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
    if not records:
        return 0

    params_list = []
    for normalized, raw in records:
        params = dict(normalized)
        params["normalized_json"] = Json(normalized)
        params["raw_json"] = Json(raw)
        params_list.append(params)

    with conn.cursor() as cur:
        execute_batch(cur, sql, params_list, page_size=250)
    conn.commit()
    return len(params_list)


def select_sources() -> list[dict[str, str]]:
    # PUBLISHER_SLUGS explícito vence tudo (inclusive o grupo): permite testar
    # qualquer editora a partir de qualquer workflow.
    raw = os.getenv("PUBLISHER_SLUGS", "").strip()
    if raw:
        wanted = {s.strip().lower() for s in raw.split(",") if s.strip()}
        escolhidas = [s for s in SOURCES if s["slug"].lower() in wanted]
        if escolhidas:
            return escolhidas
    # PUBLISHER_GROUP separa as fontes entre os workflows paralelos (cada um
    # com seu concurrency group). Fonte sem "group" pertence ao "principal".
    grupo = os.getenv("PUBLISHER_GROUP", "").strip().lower()
    if grupo:
        do_grupo = [s for s in SOURCES if s.get("group", "principal").lower() == grupo]
        if do_grupo:
            return do_grupo
    return SOURCES


def diagnose(publisher: dict[str, str]) -> None:
    """Mostra status/content-type de cada endpoint candidato — revela a plataforma."""
    base_url = publisher["base_url"].rstrip("/")
    if publisher.get("platform") == "id_range":
        print(
            "  id_range: "
            f"template={publisher.get('id_template')} "
            f"start={publisher.get('id_start')} end={publisher.get('id_end')}"
        )
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


def _iter_json_paths(payload: Any, key: tuple[str, ...]):
    """Acha listas em `payload[key[0]][key[1]]...` não importa o quão fundo
    estejam aninhadas (ex.: {"product": {"variants": [...]}} ou {"variants": [...]})."""
    if isinstance(payload, dict):
        if key[0] in payload:
            found = payload[key[0]]
            if len(key) == 1 and isinstance(found, list):
                yield from found
                return
            yield from _iter_json_paths(found, key[1:] if len(key) > 1 else key)
        for value in payload.values():
            yield from _iter_json_paths(value, key)
    elif isinstance(payload, list):
        for item in payload:
            yield from _iter_json_paths(item, key)


def dump_url(url: str) -> None:
    """Despeja JSON-LD, metatags e trechos de uma página — para entender a extração."""
    home = urlparse(url)._replace(path="/", query="").geturl()
    if home != url:
        # Visita a home antes: alguns sites (ASP.NET clássico) só liberam rotas
        # internas depois de um cookie de sessão emitido na primeira resposta —
        # SESSION (requests.Session) guarda esse cookie para a chamada seguinte.
        fetch_url(home)
    response = fetch_url(url, extra_headers={"Referer": home})
    if response is None:
        print(f"  inacessível: {url}")
        return
    print(f"  URL {url} ({len(response.text)} bytes)")
    try:
        payload = response.json()
    except ValueError:
        payload = None
    if payload is not None:
        # Endpoint JSON (ex.: {handle}.json do Shopify) — mostra campos que
        # costumam guardar o ISBN (barcode/sku), que o texto[:900] recortado
        # pode não alcançar.
        print(f"  JSON top-level keys={sorted(payload.keys()) if isinstance(payload, dict) else type(payload)}")
        for variant in _iter_json_paths(payload, ("variants",)):
            print(f"    variant: barcode={variant.get('barcode')!r} sku={variant.get('sku')!r} title={variant.get('title')!r}")
        print(f"    json[:2000]={json.dumps(payload, ensure_ascii=False)[:2000]!r}")
        return
    soup = BeautifulSoup(response.text, "html.parser")
    json_ld = load_json_ld(soup)
    print(f"  JSON-LD blocos={len(json_ld)}")
    for obj in list(iter_json_objects(json_ld))[:8]:
        keys = sorted(obj.keys())
        print(f"    @type={obj.get('@type')} keys={keys}")
    for prop in ("og:title", "og:image", "author", "book:author", "book:isbn", "twitter:title"):
        value = meta_content(soup, prop)
        if value:
            print(f"    meta[{prop}]={value[:120]}")
    if soup.title:
        print(f"    <title>={soup.title.get_text(' ', strip=True)[:140]!r}")
    for tag in soup.find_all(["h1", "h2", "h3"])[:12]:
        classe = " ".join(tag.get("class") or [])
        txt = tag.get_text(" ", strip=True)
        if txt:
            print(f"    <{tag.name} class={classe!r}>={txt[:90]!r}")
    # Elementos cuja classe/id menciona autor/author (onde o nome costuma ficar).
    for tag in soup.find_all(attrs={"class": re.compile(r"autor|author", re.I)})[:6]:
        print(f"    .autor <{tag.name} class={' '.join(tag.get('class') or [])!r}>={tag.get_text(' ', strip=True)[:90]!r}")
    for tag in soup.find_all(attrs={"id": re.compile(r"autor|author", re.I)})[:6]:
        print(f"    #autor <{tag.name} id={tag.get('id')!r}>={tag.get_text(' ', strip=True)[:90]!r}")
    h1 = soup.find("h1")
    if h1 and h1.parent:
        print(f"    h1.parent<{h1.parent.name}>={h1.parent.get_text(' ', strip=True)[:280]!r}")
    text = soup.get_text(" ", strip=True)
    print(f"    txt[:900]={text[:900]!r}")
    for label in ("ISBN", "Autor", "Tradu", "Editora", "Ano"):
        idx = text.find(label)
        if idx != -1:
            print(f"    txt~{label}: {text[idx:idx+80]!r}")
    # hrefs crus (sem os filtros de CRAWL_SKIP_TERMS/harvest_links) — revela para
    # onde apontam menus de categoria que o crawl normal pode estar descartando.
    host = urlparse(url).netloc.replace("www.", "")
    hrefs = []
    for a in soup.find_all("a", href=True):
        full = urljoin(url, a["href"]).split("#", 1)[0]
        if full not in hrefs:
            hrefs.append(full)
    internos = [h for h in hrefs if urlparse(h).netloc.replace("www.", "") == host]
    print(f"    hrefs brutos: {len(hrefs)} únicos ({len(internos)} do mesmo domínio)")
    bookish = [h for h in internos if looks_like_book_url(h)]
    nao_busca = [h for h in internos if "/busca" not in h.lower() and h not in bookish]
    selo = [h for h in nao_busca if re.search(r"selo", h, re.I)]
    outros_padroes = [h for h in nao_busca if h not in selo and not re.search(r"login|carrinho|valepresente|^https://www\.companhiadasletras\.com\.br/$", h, re.I)]
    print(f"    hrefs internos que PARECEM livro (looks_like_book_url): {len(bookish)}")
    for h in bookish[:40]:
        print(f"      [livro?] {h}")
    print(f"    hrefs SEM /busca, não-livro: {len(nao_busca)} (selo={len(selo)})")
    for h in selo[:20]:
        print(f"      [selo] {h}")
    for h in outros_padroes[:150]:
        print(f"      [outro] {h}")


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

    if getenv_bool("PUBLISHER_DEBUG_CATEGORIA_PAGINACAO", False):
        sources = select_sources()
        alvo = next((p for p in sources if p["slug"] == "cia_das_letras"), sources[0] if sources else None)
        if not alvo:
            print("nenhuma editora selecionada para diagnosticar.")
            return 0
        urls = _categoria_urls_da_home(alvo)
        print(f"{len(urls)} páginas de categoria encontradas na home de {alvo['slug']}.")
        if not urls:
            return 0
        try:
            import playwright.sync_api  # noqa: F401  (só valida cedo que está instalado)
        except ImportError:
            print("playwright não instalado.", file=sys.stderr)
            return 1
        diagnosticar_paginacao_categoria(urls[0])
        return 0

    max_urls = getenv_int("PUBLISHER_MAX_URLS", 20, minimum=1, maximum=2000)
    sleep_seconds = getenv_float("PUBLISHER_SLEEP_SECONDS", 1.0)
    dry_run = getenv_bool("PUBLISHER_DRY_RUN", False)
    # offset vazio => modo incremental (pula o que já tem); número => modo FAIXA.
    offset_raw = os.getenv("PUBLISHER_OFFSET", "").strip()
    offset = max(0, int(offset_raw)) if offset_raw.lstrip("-").isdigit() else None
    sources = select_sources()
    modo = "DRY_RUN (não grava)" if dry_run else "gravando no banco"
    faixa = f" faixa a partir de {offset}" if offset is not None else " incremental (pula já gravados)"
    print(f"max_urls={max_urls}/editora sleep={sleep_seconds}s editoras={len(sources)} —{faixa} — {modo}\n")

    # Conecta antes de coletar: a ingestão é incremental (pula o que já gravamos),
    # então cada run avança pelos PRÓXIMOS livros do catálogo, sem repetir os mesmos.
    conn = None
    if os.getenv("DATABASE_URL", "").strip():
        conn = connect_database()
        ensure_source_records(conn)
        ensure_publisher_dead_ids(conn)  # cache de ids mortos do id_range (idempotente)

    total_written = 0
    total_collected = 0
    failures: list[str] = []
    try:
        for publisher in sources:
            print("=" * 60)
            print(f"{publisher['slug']} — {publisher['name']} ({publisher['base_url']})")
            source = f"publisher:{publisher['slug']}"
            # Uma editora que falha (queda de socket, erro de parsing) NÃO derruba o
            # run inteiro: registramos a falha e seguimos para a próxima.
            try:
                # No modo faixa não pulamos por "seen" (o usuário escolheu a fatia exata).
                if conn is not None and offset is None:
                    conn = ensure_connection(conn)
                    seen = load_seen_external_ids(conn, source)
                    dead = load_dead_external_ids(conn, source)
                    if dead:
                        print(f"  ids mortos conhecidos: {len(dead)} (pulados de graça)")
                    seen = seen | dead  # ambos são pulados sem download
                else:
                    seen = set()
                if seen:
                    print(f"  já no banco: {len(seen)} (serão pulados)")
                records = collect_publisher(publisher, max_urls, sleep_seconds, seen, offset)
                with_isbn = sum(1 for normalized, _ in records if normalized["isbn"])
                with_author = sum(1 for normalized, _ in records if normalized["author"])
                print(f"  cobertura: ISBN {with_isbn}/{len(records)} · autor {with_author}/{len(records)}")
                for normalized, _ in records[:5]:
                    print(
                        f"   - {normalized['title'][:44]:44} | {normalized['author'][:20]:20} "
                        f"| isbn={normalized['isbn'] or '-'}"
                    )
                total_collected += len(records)
                if records and not dry_run and conn is not None:
                    # Reabre a conexão (ela ficou ociosa durante o scraping) ANTES de
                    # gravar, para o lote não se perder por SSL caído.
                    conn = ensure_connection(conn)
                    written = upsert_records(conn, records)
                    total_written += written
                    print(f"  gravados: {written}")
                # Persiste os ids mortos descobertos (fora do dry_run: é escrita no
                # banco). Roda mesmo com records vazio — numa faixa esgotada o
                # resultado ÚTIL é justamente marcar os mortos pra próxima execução
                # pular tudo de graça.
                dead_new = NEWLY_DEAD_IDS.pop(source, set())
                if dead_new and not dry_run and conn is not None:
                    conn = ensure_connection(conn)
                    marked = upsert_dead_ids(conn, source, dead_new)
                    print(f"  ids mortos novos registrados: {marked}")
            except Exception as exc:  # noqa: BLE001 — isola a falha de UMA editora
                print(f"  ERRO em {publisher['slug']}: {exc!r}", file=sys.stderr)
                failures.append(publisher["slug"])
                # Reabre a conexão para a próxima editora não herdar um socket morto.
                if conn is not None:
                    try:
                        conn = ensure_connection(conn)
                    except Exception as reconnect_exc:  # noqa: BLE001
                        print(f"  reconexão falhou: {reconnect_exc!r}", file=sys.stderr)
                        conn = None
            print()
    finally:
        if conn is not None and not conn.closed:
            conn.close()

    if dry_run:
        print(f"DRY_RUN: {total_collected} registros novos coletados, nada gravado.")
    else:
        print(f"{total_written} registros novos salvos em source_records com status=pending.")
    if failures:
        # Sai com erro para o job ficar VERMELHO e visível (mas só depois de ter
        # gravado tudo o que deu — as editoras que funcionaram já estão salvas).
        print(f"⚠️  {len(failures)} editora(s) com falha: {', '.join(failures)}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"Erro na sincronização de editoras: {exc}", file=sys.stderr)
        raise SystemExit(1)
