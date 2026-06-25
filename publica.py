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
        "status": l.status, "nota": l.nota,
        "relato": l.relato if l.publico else "",
        "publico": bool(l.publico), "spoiler": bool(l.spoiler), "data": l.data,
        "titulo": o.titulo, "autor": o.autor,
        "editora": ed.editora, "tradutor": ed.tradutor,
        "ano": ed.ano, "isbn": ed.isbn, "capa_url": ed.capa_url,
    } for (l, ed, o) in rows]


def resumo_perfil_publico(leituras: list) -> dict:
    total = len(leituras)
    lidos = sum(1 for l in leituras if l.get("status") == "Lido")
    lendo = sum(1 for l in leituras if l.get("status") == "Lendo")
    quero = sum(1 for l in leituras if l.get("status") == "Quero ler")
    notas = [float(l.get("nota")) for l in leituras if l.get("nota")]
    media = round(sum(notas) / len(notas), 1) if notas else None
    criticas = [l for l in leituras if l.get("publico") and (l.get("relato") or "").strip()]
    favoritos = sorted(
        leituras,
        key=lambda l: (float(l.get("nota") or 0), bool((l.get("relato") or "").strip()), l.get("data") or ""),
        reverse=True,
    )
    favoritos = [l for l in favoritos if (l.get("nota") and float(l.get("nota")) >= 4.5) or l.get("publico")][:5]
    return {
        "stats": {"total": total, "lidos": lidos, "lendo": lendo, "quero_ler": quero, "media_nota": media},
        "lendo_agora": [l for l in leituras if l.get("status") == "Lendo"],
        "ultimas_leituras": leituras[:12],
        "criticas_publicas": criticas[:8],
        "favoritos": favoritos,
    }


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
.empty{padding:28px 6px;text-align:center;color:var(--dim);font-style:italic;border:1px dashed var(--rule);background:rgba(255,255,255,.12)}
.profile-name{font-family:"Fraunces",serif;font-size:18px;font-style:italic;color:var(--ink-2);margin-top:14px}
.metrics{display:flex;flex-wrap:wrap;gap:8px;margin-top:12px}.pill{border:1px solid var(--rule);padding:8px 10px;background:rgba(255,255,255,.16);font-family:"Space Mono",monospace;font-size:10px;text-transform:uppercase;letter-spacing:.08em}
.section{margin-top:30px}.section h2{font-family:"Fraunces",serif;font-style:italic;font-weight:400;font-size:24px;margin-bottom:14px}.shelf-strip{display:grid;grid-template-columns:repeat(2,1fr);gap:16px 14px}@media(min-width:420px){.shelf-strip{grid-template-columns:repeat(4,1fr)}.shelf-strip.favs{grid-template-columns:repeat(5,1fr)}}
.list{display:grid;gap:12px}.row{display:grid;grid-template-columns:62px 1fr;gap:12px;align-items:start;border-top:1px solid var(--rule);padding-top:12px}.row .cover{width:62px}.meta{font-family:"Space Mono",monospace;font-size:10px;color:var(--dim);text-transform:uppercase;letter-spacing:.08em;margin-top:5px}.badge{display:inline-block;border:1px solid var(--rule);padding:2px 6px;margin-left:4px}.review{border:1px solid var(--rule);background:rgba(255,255,255,.14);padding:16px;margin-bottom:12px}.review-title{font-family:"Fraunces",serif;font-style:italic;font-size:20px}.review-text{margin-top:10px;line-height:1.45}.spoiler{cursor:pointer;color:var(--dim);font-style:italic}.stats{display:grid;grid-template-columns:repeat(2,1fr);gap:10px}.stat{border:1px solid var(--rule);padding:14px;background:rgba(255,255,255,.12)}.stat strong{display:block;font-family:"Fraunces",serif;font-size:28px}.stat span{font-family:"Space Mono",monospace;font-size:10px;color:var(--dim);letter-spacing:.1em;text-transform:uppercase}
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


def _meta_edicao(l: dict) -> str:
    partes = [l.get("editora"), f"trad. {l.get('tradutor')}" if l.get("tradutor") else "", l.get("ano")]
    return " · ".join(_esc(p) for p in partes if p)


def _trecho(s: str, n: int = 220) -> str:
    s = " ".join((s or "").split())
    return s if len(s) <= n else s[:n].rsplit(" ", 1)[0] + "…"


def _section(titulo: str, html: str) -> str:
    return f'<section class="section"><h2>{titulo}</h2>{html}</section>'


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


def _row_livro(l: dict) -> str:
    return f'<div class="row">{_card_publico(l).replace("book", "book mini", 1)}<div><div class="t">{_esc(l.get("titulo"))}</div><div class="a">{_esc(l.get("autor"))}</div><div class="meta">{_esc(l.get("status"))}{" · " + _estrelas(l.get("nota")) if l.get("nota") else ""}{" · " + _esc(l.get("data")) if l.get("data") else ""}{" · " + _meta_edicao(l) if _meta_edicao(l) else ""}{" <span class=\"badge\">tem crítica</span>" if l.get("publico") and l.get("relato") else ""}</div></div></div>'


def render_estante_publica(u: Usuario, leituras: list) -> str:
    resumo = resumo_perfil_publico(leituras)
    stats = resumo["stats"]
    n = stats["total"]
    cont = "1 livro" if n == 1 else f"{n} livros"
    nome = (u.nome or "").strip() or "Leitor Lombada"
    header = (
        f'<div class="head"><div class="wordmark">LOMBADA<span class="dot">.</span></div>'
        f'<div class="profile-name">{_esc(nome)}</div><h1>@{_esc(u.handle)}</h1>'
        f'<div class="count">{cont} · {stats["lidos"]} lidos · {stats["lendo"]} lendo · {stats["quero_ler"]} quero ler</div>'
        f'<div class="metrics"><div class="pill">{cont}</div><div class="pill">{stats["lidos"]} lidos</div><div class="pill">{stats["lendo"]} lendo</div><div class="pill">{stats["quero_ler"]} quero ler</div></div></div>'
    )
    favs = _section("Favoritos", '<div class="shelf-strip favs">' + "".join(_card_publico(l) for l in resumo["favoritos"]) + '</div>') if resumo["favoritos"] else ""
    lendo = _section("Lendo agora", '<div class="shelf-strip">' + "".join(_card_publico(l) for l in resumo["lendo_agora"][:4]) + '</div>' if resumo["lendo_agora"] else '<div class="empty">nada em leitura agora.</div>')
    reviews_html = ""
    for l in resumo["criticas_publicas"]:
        texto = '<details class="spoiler"><summary>Crítica com spoiler — tocar para revelar</summary><p class="review-text">' + _esc(_trecho(l.get("relato"))) + '</p></details>' if l.get("spoiler") else '<p class="review-text">' + _esc(_trecho(l.get("relato"))) + '</p>'
        reviews_html += f'<article class="review"><div class="review-title">{_esc(l.get("titulo"))}</div><div class="a">{_esc(l.get("autor"))}</div><div class="meta">{_estrelas(l.get("nota")) if l.get("nota") else "sem nota"}{" · " + _esc(l.get("data")) if l.get("data") else ""}{" · " + _meta_edicao(l) if _meta_edicao(l) else ""}</div>{texto}</article>'
    criticas = _section("Críticas públicas", reviews_html or '<div class="empty">ainda não há críticas públicas.</div>')
    ultimas = _section("Últimas leituras", '<div class="list">' + "".join(_row_livro(l) for l in resumo["ultimas_leituras"][:8]) + '</div>' if resumo["ultimas_leituras"] else '<div class="empty">estante ainda vazia.</div>')
    media = f'{stats["media_nota"]:.1f} ★' if stats["media_nota"] else "—"
    estat = _section("Estatísticas", f'<div class="stats"><div class="stat"><strong>{n}</strong><span>livros</span></div><div class="stat"><strong>{stats["lidos"]}</strong><span>lidos</span></div><div class="stat"><strong>{stats["lendo"]}</strong><span>lendo</span></div><div class="stat"><strong>{stats["quero_ler"]}</strong><span>quero ler</span></div><div class="stat"><strong>{media}</strong><span>média de nota</span></div></div>')
    corpo = header + favs + lendo + criticas + ultimas + estat + '<a class="cta" href="/">criar a minha estante →</a>'
    og = {"title": f"o perfil literário de @{u.handle}", "type": "website", "description": f"{cont} · {stats['lidos']} lidos · veja o perfil público de @{u.handle} na Lombada"}
    primeira = next((l.get("capa_url") for l in leituras if l.get("capa_url")), "")
    if primeira:
        og["image"] = primeira
    return _pagina(f"@{u.handle} · Lombada", corpo, og)
