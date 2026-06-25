"""
Lombada — estante pública: HTML server-rendered + Open Graph para /u/{handle}.
"""
from sqlmodel import select, Session

from models import Leitura, Edicao, Obra, Usuario


def _esc(s) -> str:
    return (str(s if s is not None else "")
            .replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def _estrelas(n) -> str:
    n = n or 0
    return "".join("★" if i <= n else ("⯪" if i - 0.5 == n else "☆") for i in range(1, 6))


def _leituras_de(s: Session, usuario_id: int) -> list:
    rows = s.exec(
        select(Leitura, Edicao, Obra)
        .join(Edicao, Leitura.edicao_id == Edicao.id)
        .join(Obra, Edicao.obra_id == Obra.id)
        .where(Leitura.usuario_id == usuario_id)
        .order_by(Leitura.criado_em.desc())
    ).all()
    return [{
        "status": l.status, "nota": l.nota, "relato": l.relato if l.publico else "", "publico": bool(l.publico), "spoiler": bool(l.spoiler), "data": l.data,
        "titulo": o.titulo, "autor": o.autor,
        "editora": ed.editora, "tradutor": ed.tradutor,
        "ano": ed.ano, "isbn": ed.isbn, "capa_url": ed.capa_url,
    } for (l, ed, o) in rows]


# CSS inline pra página pública (independente do static/app.css do SPA)
_FONTES = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
    '<link href="https://fonts.googleapis.com/css2?'
    'family=Fraunces:ital,opsz,wght@0,9..144,400;0,9..144,600;1,9..144,400;1,9..144,600'
    '&family=Spectral:ital,wght@0,400;1,400&family=Space+Mono:wght@400;700&display=swap" '
    'rel="stylesheet">'
)

_CSS = """
:root{--paper:#ECE4D4;--paper-3:#D6CBB3;--ink:#1A1714;--ink-2:#3A322A;--dim:#6F6655;--gold:#A8842F;
--rule:rgba(26,23,20,.18);--shadow:6px 8px 0 rgba(26,23,20,.12),1px 2px 0 rgba(26,23,20,.25)}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--paper);color:var(--ink);font-family:"Spectral",Georgia,serif;-webkit-font-smoothing:antialiased}
a{color:inherit;text-decoration:none}
.wrap{max-width:560px;margin:0 auto;padding:26px 16px 60px}
.wordmark{font-family:"Fraunces",serif;font-style:italic;font-weight:600;font-size:22px}
.wordmark .dot{color:var(--gold)}
.head{border-bottom:1px solid var(--rule);padding-bottom:18px;margin-bottom:22px}
.label{font-family:"Space Mono",monospace;font-size:10px;letter-spacing:.16em;text-transform:uppercase;color:var(--dim)}
h1{font-family:"Fraunces",serif;font-style:italic;font-weight:400;font-size:30px;line-height:1.05;margin:14px 0 4px}
.count{font-family:"Space Mono",monospace;font-size:11px;color:var(--ink-2);letter-spacing:.04em}
.wall{display:grid;grid-template-columns:repeat(2,1fr);gap:18px 14px}
@media(min-width:420px){.wall{grid-template-columns:repeat(3,1fr)}}
.cover{position:relative;aspect-ratio:2/3;background:var(--paper-3);box-shadow:var(--shadow);overflow:hidden}
.cover img{width:100%;height:100%;object-fit:cover;display:block}
.cover .fb{position:absolute;inset:0;display:flex;align-items:flex-end;padding:12px;font-family:"Fraunces",serif;font-style:italic;font-size:18px;line-height:1.1;color:rgba(26,23,20,.75)}
.cover .stars{position:absolute;left:6px;bottom:6px;font-family:"Space Mono",monospace;font-size:11px;color:var(--paper);background:rgba(26,23,20,.78);padding:3px 6px;letter-spacing:.05em}
.t{font-family:"Fraunces",serif;font-style:italic;font-size:15px;line-height:1.15;margin-top:8px}
.a{font-size:12px;color:var(--dim);margin-top:2px}
.cta{display:block;text-align:center;margin:34px auto 0;max-width:360px;background:var(--ink);color:var(--paper);padding:16px;font-family:"Space Mono",monospace;font-size:12px;letter-spacing:.18em;text-transform:uppercase}
.empty{padding:40px 6px;text-align:center;color:var(--dim);font-style:italic}
"""


def _pagina(titulo: str, corpo: str, og: dict | None = None) -> str:
    og_tags = ""
    if og:
        for k, v in og.items():
            og_tags += f'<meta property="og:{k}" content="{_esc(v)}">'
        og_tags += '<meta name="twitter:card" content="summary_large_image">'
    return (
        '<!DOCTYPE html><html lang="pt-BR"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f'<title>{_esc(titulo)}</title>{og_tags}{_FONTES}'
        f'<style>{_CSS}</style></head><body><div class="wrap">{corpo}</div></body></html>'
    )


def _card_publico(l: dict) -> str:
    cap   = l.get("capa_url") or ""
    t     = _esc(l.get("titulo"))
    a     = _esc(l.get("autor"))
    stars = f'<div class="stars">{_estrelas(l.get("nota"))}</div>' if l.get("nota") else ""
    if cap:
        cover = (
            f'<div class="cover"><img src="{_esc(cap)}" alt="" loading="lazy" '
            "onerror=\"this.style.display='none';this.nextElementSibling.style.display='flex'\">"
            f'<div class="fb" style="display:none">{t}</div>{stars}</div>'
        )
    else:
        cover = f'<div class="cover"><div class="fb">{t}</div>{stars}</div>'
    return f'<div class="book">{cover}<div class="t">{t}</div><div class="a">{a}</div></div>'


def render_estante_publica(u: Usuario, leituras: list) -> str:
    n    = len(leituras)
    cont = "1 livro" if n == 1 else f"{n} livros"
    grid = (
        '<div class="wall">' + "".join(_card_publico(l) for l in leituras) + "</div>"
        if leituras else '<div class="empty">estante ainda vazia.</div>'
    )
    corpo = (
        f'<div class="head"><div class="wordmark">LOMBADA<span class="dot">.</span></div>'
        f'<div class="label" style="margin-top:14px">a estante de</div>'
        f'<h1>@{_esc(u.handle)}</h1><div class="count">{cont}</div></div>'
        f'{grid}<a class="cta" href="/">criar a minha estante →</a>'
    )
    og = {
        "title":       f"a estante de @{u.handle}",
        "type":        "website",
        "description": f"{cont} · veja o que @{u.handle} anda lendo na Lombada",
    }
    primeira = next((l.get("capa_url") for l in leituras if l.get("capa_url")), "")
    if primeira:
        og["image"] = primeira
    return _pagina(f"@{u.handle} · Lombada", corpo, og)
