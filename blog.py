"""
Lombada — blog simples baseado em arquivos Markdown em blog/*.md.

Cada post é um .md com front-matter opcional entre linhas '---':

    ---
    title: Título do post
    date: 2026-07-06
    resumo: Uma frase que aparece na listagem.
    ---
    Corpo em **Markdown**.

O slug é o nome do arquivo sem .md. Sem banco, sem admin: escrever um post é
adicionar um arquivo e commitar.
"""
from __future__ import annotations

import datetime as _dt
from pathlib import Path

import markdown as _md

AQUI = Path(__file__).resolve().parent
POSTS_DIR = AQUI / "blog"


def _parse_front_matter(texto: str) -> tuple[dict, str]:
    """Separa o front-matter (bloco entre '---') do corpo. Tolerante a ausência."""
    meta: dict[str, str] = {}
    corpo = texto
    if texto.lstrip().startswith("---"):
        # remove um BOM/whitespace inicial e o primeiro '---'
        resto = texto.lstrip()[3:]
        fim = resto.find("\n---")
        if fim != -1:
            bloco = resto[:fim]
            corpo = resto[fim + 4:]
            for linha in bloco.splitlines():
                if ":" in linha:
                    k, v = linha.split(":", 1)
                    meta[k.strip().lower()] = v.strip()
    return meta, corpo.lstrip("\n")


def _data_fmt(iso: str) -> str:
    """'2026-07-06' → '6 de julho de 2026'. Devolve o original se não parsear."""
    meses = ["", "janeiro", "fevereiro", "março", "abril", "maio", "junho",
             "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"]
    try:
        d = _dt.date.fromisoformat(iso.strip())
        return f"{d.day} de {meses[d.month]} de {d.year}"
    except (ValueError, IndexError):
        return iso


def _slug_de(p: Path) -> str:
    return p.stem


def _carregar(p: Path) -> dict | None:
    try:
        texto = p.read_text(encoding="utf-8")
    except OSError:
        return None
    meta, corpo = _parse_front_matter(texto)
    titulo = meta.get("title") or _slug_de(p).replace("-", " ").capitalize()
    data_iso = meta.get("date", "")
    return {
        "slug": _slug_de(p),
        "titulo": titulo,
        "data_iso": data_iso,
        "data": _data_fmt(data_iso) if data_iso else "",
        "resumo": meta.get("resumo", ""),
        "corpo_md": corpo,
    }


def listar_posts() -> list[dict]:
    """Todos os posts, mais recentes primeiro (por date; sem date vai pro fim)."""
    if not POSTS_DIR.is_dir():
        return []
    posts = [_carregar(p) for p in POSTS_DIR.glob("*.md")]
    posts = [p for p in posts if p]
    posts.sort(key=lambda p: p.get("data_iso") or "", reverse=True)
    return posts


def carregar_post(slug: str) -> dict | None:
    """Um post pelo slug, com o corpo já convertido pra HTML. None se não existir."""
    # slug é nome de arquivo — barra o path traversal
    if not slug or "/" in slug or "\\" in slug or slug.startswith("."):
        return None
    p = POSTS_DIR / f"{slug}.md"
    if not p.is_file():
        return None
    post = _carregar(p)
    if not post:
        return None
    post["corpo_html"] = _md.markdown(
        post["corpo_md"], extensions=["extra", "sane_lists"]
    )
    return post
