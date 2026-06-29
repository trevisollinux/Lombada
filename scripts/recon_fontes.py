#!/usr/bin/env python3
"""
Lombada — reconhecimento de fontes de dados de livro.

Objetivo: medir, de forma reproduzível, QUAIS fontes retornam livros que
hoje somem da busca (ex.: "Comporte-se", do Sapolsky), e COM QUAIS campos
(ISBN, capa, tradutor, ano). Ajuda a decidir o que vale ingerir na base.

Rode onde a rede é aberta (o ambiente do Claude na web bloqueia a maioria
dos hosts por política):

    python3 scripts/recon_fontes.py
    GOOGLE_BOOKS_API_KEY=xxxxx python3 scripts/recon_fontes.py   # evita 429

Sem dependências externas — só a stdlib. Edite TESTES para incluir os livros
que você sabe que somem.
"""
import json
import os
import sys
import time
import urllib.parse
import urllib.request

TIMEOUT = 20
UA = {"User-Agent": "Lombada-recon/1.0 (diario de leitura)"}
GB_KEY = os.getenv("GOOGLE_BOOKS_API_KEY", "")

# (titulo, autor/sobrenome esperado, isbn_conhecido opcional)
TESTES = [
    ("Comporte-se", "Sapolsky", ""),
    ("Sapiens", "Harari", ""),
    ("Torto Arado", "Itamar Vieira", ""),
]


def _get(url, headers=None):
    req = urllib.request.Request(url, headers={**UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return r.status, r.read()


def _get_json(url, headers=None):
    st, body = _get(url, headers)
    return json.loads(body)


def _hit(texto, esperado):
    return esperado.lower() in (texto or "").lower()


# ─── Google Books ──────────────────────────────────────────
def gb(q, **extra):
    params = {"q": q, "country": "BR", "printType": "books", "maxResults": 20, "orderBy": "relevance"}
    params.update(extra)
    if GB_KEY:
        params["key"] = GB_KEY
    url = "https://www.googleapis.com/books/v1/volumes?" + urllib.parse.urlencode(params)
    data = _get_json(url)
    out = []
    for it in data.get("items", []):
        vi = it.get("volumeInfo", {})
        ids = {d.get("type"): d.get("identifier") for d in (vi.get("industryIdentifiers") or [])}
        out.append({
            "titulo": vi.get("title", ""),
            "autor": ", ".join(vi.get("authors") or []),
            "ano": (vi.get("publishedDate") or "")[:4],
            "idioma": vi.get("language", ""),
            "isbn": ids.get("ISBN_13") or ids.get("ISBN_10") or "",
            "capa": bool((vi.get("imageLinks") or {}).get("thumbnail")),
            "editora": vi.get("publisher", ""),
        })
    return out


# ─── Open Library ──────────────────────────────────────────
def ol(q):
    url = "https://openlibrary.org/search.json?" + urllib.parse.urlencode({
        "q": q, "limit": 20,
        "fields": "title,author_name,first_publish_year,language,isbn,cover_i",
    })
    data = _get_json(url)
    out = []
    for d in data.get("docs", []):
        out.append({
            "titulo": d.get("title", ""),
            "autor": ", ".join(d.get("author_name") or []),
            "ano": d.get("first_publish_year", ""),
            "idioma": ",".join(d.get("language") or []),
            "isbn": (d.get("isbn") or [""])[0],
            "capa": bool(d.get("cover_i")),
            "editora": "",
        })
    return out


# ─── Mercado Livre (marketplace BR, sem auth p/ busca) ─────
def ml(q):
    url = "https://api.mercadolibre.com/sites/MLB/search?" + urllib.parse.urlencode({"q": q, "limit": 10})
    data = _get_json(url)
    out = []
    for r in data.get("results", []):
        attrs = {a.get("id"): a.get("value_name") for a in (r.get("attributes") or [])}
        out.append({
            "titulo": r.get("title", ""),
            "autor": attrs.get("AUTHOR") or attrs.get("BOOK_AUTHOR") or "",
            "ano": attrs.get("PUBLICATION_YEAR") or "",
            "idioma": attrs.get("BOOK_LANGUAGE") or "",
            "isbn": attrs.get("ISBN") or attrs.get("GTIN") or "",
            "capa": bool(r.get("thumbnail")),
            "editora": attrs.get("PUBLISHER") or "",
        })
    return out


FONTES = {"Google Books": gb, "Open Library": ol, "Mercado Livre": ml}


def avalia(resultados, titulo, autor):
    """Acha o melhor candidato e descreve a cobertura de campos."""
    for r in resultados:
        if _hit(r["titulo"], titulo.split()[0]) and _hit(r["autor"] + " " + r["titulo"], autor):
            campos = []
            if r["isbn"]:
                campos.append("ISBN")
            if r["capa"]:
                campos.append("capa")
            if r["ano"]:
                campos.append("ano")
            if r["editora"]:
                campos.append("editora")
            pt = "pt" in (r["idioma"] or "").lower() or "por" in (r["idioma"] or "").lower()
            return True, f"ACHOU [{r['idioma'] or '?'}{' PT' if pt else ''}] campos={'+'.join(campos) or 'nenhum'} :: {r['titulo'][:40]}"
    return False, "não achou no top dos resultados"


def main():
    print(f"GOOGLE_BOOKS_API_KEY: {'definida' if GB_KEY else 'AUSENTE (sujeito a 429)'}\n")
    for titulo, autor, isbn in TESTES:
        print("=" * 70)
        print(f"LIVRO: {titulo}  ·  autor~{autor}  ·  isbn={isbn or '-'}")
        for nome, fn in FONTES.items():
            q = f"{titulo} {autor}"
            for tentativa in range(3):
                try:
                    res = fn(q)
                    ok, msg = avalia(res, titulo, autor)
                    print(f"  {nome:16} {'✓' if ok else '✗'} {msg}")
                    break
                except Exception as e:
                    err = repr(e)[:80]
                    if tentativa == 2:
                        print(f"  {nome:16} ! erro: {err}")
                    else:
                        time.sleep(2)
        print()


if __name__ == "__main__":
    sys.exit(main())
