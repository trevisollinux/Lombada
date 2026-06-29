#!/usr/bin/env python3
"""
Lombada — scraper de catálogos de editoras (para construir base própria).

Filosofia: nada de seletor de HTML chumbado (quebra toda hora). Usa a camada
de dados que os sites já expõem, em ordem de robustez:
  1) Shopify  -> {base}/products.json
  2) VTEX     -> {base}/api/catalog_system/pub/products/search
  3) Sitemap + JSON-LD / Open Graph nas páginas dos livros

Educação obrigatória: respeita robots.txt, dá intervalo entre requisições e
se identifica no User-Agent. Coleta só metadado factual (título, autor, ISBN,
editora, ano) + a URL da capa (não baixa a imagem).

Modos (env MODO ou 1º argumento):
  probe  (padrão) — detecta a plataforma de cada editora e mostra uma amostra.
                    NÃO escreve arquivo. Serve pra descobrir o que funciona.
  full            — varre e grava data/catalog_scraped.json.

Filtros por env:
  EDITORA   substring do nome (ex.: "intrinseca") para rodar só uma
  LIMITE    máx. de livros por editora (default: 8 no probe, 500 no full)
  INTERVALO segundos entre requisições (default 1.0)

Só stdlib — roda em qualquer lugar (inclusive GitHub Actions) sem pip install.
"""
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
import urllib.robotparser
import xml.etree.ElementTree as ET

UA = "LombadaBot/0.1 (+https://github.com/trevisollinux/lombada; catalogo de leitura)"
TIMEOUT = 25
INTERVALO = float(os.getenv("INTERVALO", "1.0"))

# Edite/expanda. base SEM barra final. Corrija URLs que estiverem erradas.
EDITORAS = [
    {"nome": "Companhia das Letras", "base": "https://www.companhiadasletras.com.br"},
    {"nome": "Intrínseca",           "base": "https://www.intrinseca.com.br"},
    {"nome": "Todavia",              "base": "https://todavialivros.com.br"},
    {"nome": "Sextante",             "base": "https://www.sextante.com.br"},
    {"nome": "Editora 34",           "base": "https://www.editora34.com.br"},
    {"nome": "Autêntica",            "base": "https://grupoautentica.com.br"},
]


# ─── utils ────────────────────────────────────────────────
def fetch(url, accept=None):
    headers = {"User-Agent": UA}
    if accept:
        headers["Accept"] = accept
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return r.status, r.read()


def robots_permite(base, caminho="/"):
    try:
        rp = urllib.robotparser.RobotFileParser()
        rp.set_url(base + "/robots.txt")
        rp.read()
        return rp.can_fetch(UA, base + caminho)
    except Exception:
        return True  # sem robots legível: não bloqueia, mas seguimos educados


def norm_isbn(v):
    c = re.sub(r"[^0-9Xx]", "", str(v or "")).upper()
    if len(c) == 13 and c.isdigit():
        return c
    if len(c) == 10 and re.fullmatch(r"[0-9]{9}[0-9X]", c):
        return c
    return ""


def ano_de(v):
    m = re.search(r"\b(\d{4})\b", str(v or ""))
    return int(m.group(1)) if m else None


def registro(titulo, autor, isbn, editora, ano, capa, url):
    return {
        "titulo": (titulo or "").strip(),
        "autor": (autor or "").strip(),
        "isbn": norm_isbn(isbn),
        "editora": (editora or "").strip(),
        "ano": ano_de(ano),
        "idioma": "Português",
        "capa_url": (capa or "").strip(),
        "fonte_url": url,
    }


# ─── extração genérica: JSON-LD / Open Graph ──────────────
_LD_RE = re.compile(rb'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', re.I | re.S)


def _ld_objs(html):
    objs = []
    for bloco in _LD_RE.findall(html or b""):
        try:
            data = json.loads(bloco.decode("utf-8", "ignore").strip())
        except Exception:
            continue
        if isinstance(data, list):
            objs.extend([d for d in data if isinstance(d, dict)])
        elif isinstance(data, dict):
            objs.append(data)
            if isinstance(data.get("@graph"), list):
                objs.extend([d for d in data["@graph"] if isinstance(d, dict)])
    return objs


def _tipo(o):
    t = o.get("@type") or ""
    return " ".join(t) if isinstance(t, list) else str(t)


def _autor_ld(o):
    a = o.get("author") or o.get("brand")
    if isinstance(a, dict):
        return a.get("name", "")
    if isinstance(a, list) and a:
        return (a[0].get("name") if isinstance(a[0], dict) else str(a[0])) or ""
    return str(a or "")


def extrair_pagina(url):
    _, html = fetch(url, accept="text/html")
    for o in _ld_objs(html):
        if re.search(r"\b(Book|Product)\b", _tipo(o)):
            isbn = o.get("isbn") or o.get("gtin13") or o.get("gtin") or ""
            img = o.get("image")
            if isinstance(img, list):
                img = img[0] if img else ""
            if isinstance(img, dict):
                img = img.get("url", "")
            pub = o.get("publisher")
            pub = pub.get("name") if isinstance(pub, dict) else (pub or "")
            r = registro(o.get("name"), _autor_ld(o), isbn, pub, o.get("datePublished"), img, url)
            if r["titulo"]:
                return r
    # fallback Open Graph
    def og(prop):
        m = re.search(rb'<meta[^>]+property=["\']og:' + prop.encode() + rb'["\'][^>]+content=["\'](.*?)["\']', html or b"", re.I)
        return m.group(1).decode("utf-8", "ignore") if m else ""
    titulo = og("title")
    if titulo:
        return registro(titulo, "", "", "", "", og("image"), url)
    return None


# ─── plataformas ──────────────────────────────────────────
def via_shopify(base, limite):
    out = []
    for page in range(1, 6):
        st, body = fetch(f"{base}/products.json?limit=250&page={page}", accept="application/json")
        prods = json.loads(body).get("products", [])
        if not prods:
            break
        for p in prods:
            variants = p.get("variants") or [{}]
            isbn = ""
            for v in variants:
                isbn = norm_isbn(v.get("barcode"))
                if isbn:
                    break
            imgs = p.get("images") or []
            capa = (imgs[0].get("src") if imgs else "") or ""
            out.append(registro(p.get("title"), p.get("vendor"), isbn, p.get("vendor"),
                                 p.get("published_at"), capa, f"{base}/products/{p.get('handle','')}"))
            if len(out) >= limite:
                return out
        time.sleep(INTERVALO)
    return out


def _vtex_autor(p):
    for k, v in p.items():
        if "autor" in k.lower() and isinstance(v, list) and v:
            return str(v[0])
    return (p.get("brand") or "")


def via_vtex(base, limite):
    out = []
    passo = 50
    for start in range(0, 500, passo):
        url = f"{base}/api/catalog_system/pub/products/search?_from={start}&_to={start + passo - 1}"
        st, body = fetch(url, accept="application/json")
        prods = json.loads(body)
        if not isinstance(prods, list) or not prods:
            break
        for p in prods:
            items = p.get("items") or [{}]
            isbn = ""
            capa = ""
            for it in items:
                isbn = isbn or norm_isbn(it.get("ean"))
                imgs = it.get("images") or []
                capa = capa or (imgs[0].get("imageUrl") if imgs else "")
            out.append(registro(p.get("productName"), _vtex_autor(p), isbn, p.get("brand"),
                                 p.get("releaseDate"), capa, p.get("link") or (base + (p.get("linkText", "") and "/" + p["linkText"]))))
            if len(out) >= limite:
                return out
        time.sleep(INTERVALO)
    return out


def _urls_sitemap(base, limite):
    """Coleta URLs de livro a partir do sitemap (segue sitemapindex 1 nível)."""
    alvos = []
    fila = [f"{base}/sitemap.xml"]
    vistos = set()
    while fila and len(alvos) < limite * 4:
        sm = fila.pop(0)
        if sm in vistos:
            continue
        vistos.add(sm)
        try:
            _, body = fetch(sm, accept="application/xml")
            root = ET.fromstring(body)
        except Exception:
            continue
        ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        filhos = [e.text for e in root.findall(".//s:sitemap/s:loc", ns) if e.text]
        if filhos:
            fila.extend(filhos[:10])
            continue
        locs = [e.text for e in root.findall(".//s:url/s:loc", ns) if e.text]
        # heurística: páginas de livro/produto
        for u in locs:
            if re.search(r"/(livro|livros|produto|product|book|p)/", u):
                alvos.append(u)
        time.sleep(INTERVALO)
    return alvos[: limite * 2]


def via_sitemap(base, limite):
    out = []
    for u in _urls_sitemap(base, limite):
        try:
            r = extrair_pagina(u)
        except Exception:
            r = None
        if r and r["titulo"]:
            out.append(r)
        time.sleep(INTERVALO)
        if len(out) >= limite:
            break
    return out


METODOS = [("shopify", via_shopify), ("vtex", via_vtex), ("sitemap", via_sitemap)]


def coletar(pub, limite):
    base = pub["base"].rstrip("/")
    if not robots_permite(base, "/"):
        return "robots_bloqueado", []
    for nome, fn in METODOS:
        try:
            res = fn(base, limite)
        except Exception as e:
            print(f"      [{nome}] erro: {repr(e)[:90]}")
            continue
        validos = [r for r in res if r["titulo"]]
        if validos:
            return nome, validos
    return "nenhum", []


# ─── main ─────────────────────────────────────────────────
def main():
    modo = (sys.argv[1] if len(sys.argv) > 1 else os.getenv("MODO", "probe")).strip().lower()
    filtro = os.getenv("EDITORA", "").strip().lower()
    limite = int(os.getenv("LIMITE", "8" if modo != "full" else "500"))
    editoras = [e for e in EDITORAS if (not filtro or filtro in e["nome"].lower())]

    print(f"MODO={modo}  LIMITE={limite}/editora  INTERVALO={INTERVALO}s  editoras={len(editoras)}\n")
    catalogo = []
    for pub in editoras:
        print("=" * 64)
        print(f"{pub['nome']}  ({pub['base']})")
        metodo, registros = coletar(pub, limite)
        print(f"  método: {metodo}  ·  livros: {len(registros)}")
        com_isbn = sum(1 for r in registros if r["isbn"])
        com_autor = sum(1 for r in registros if r["autor"])
        com_capa = sum(1 for r in registros if r["capa_url"])
        if registros:
            print(f"  cobertura: ISBN {com_isbn}/{len(registros)} · autor {com_autor} · capa {com_capa}")
            for r in registros[:5]:
                print(f"   - {r['titulo'][:42]:42} | {r['autor'][:18]:18} | isbn={r['isbn'] or '-'}")
        for r in registros:
            r["editora_fonte"] = pub["nome"]
        catalogo.extend(registros)
        print()

    if modo == "full":
        # dedup por ISBN (fallback título+editora)
        vistos, final = set(), []
        for r in catalogo:
            chave = r["isbn"] or (r["titulo"].lower() + "|" + r["editora_fonte"].lower())
            if chave in vistos:
                continue
            vistos.add(chave)
            final.append(r)
        destino = os.path.join("data", "catalog_scraped.json")
        os.makedirs("data", exist_ok=True)
        with open(destino, "w", encoding="utf-8") as f:
            json.dump(final, f, ensure_ascii=False, indent=2)
        print(f"GRAVADO: {destino}  ({len(final)} livros únicos de {len(catalogo)} coletados)")
    else:
        print("MODO probe: nada gravado. Rode com MODO=full para gerar data/catalog_scraped.json")


if __name__ == "__main__":
    main()
