"""
Lombada — páginas institucionais server-rendered: /sobre (landing),
/quem-somos e /blog. Todas compartilham o mesmo shell (nav no topo + rodapé)
e reaproveitam os tokens de design da estante pública (publica.py): paleta
paper/ink, fontes e tema claro/escuro compartilhado via localStorage.

Posicionamento: o Lombada é (1) uma rede social de livros e (2) a fonte mais
completa pra pesquisar livros publicados no Brasil. O "tipo Letterboxd" fica
como legenda pequena, não como manchete.

Os botões de "instalar no Android" (PLAY_STORE_URL), "apoiar" (APOIO_URL) e
"instagram" (INSTAGRAM_URL) só aparecem quando a env var correspondente está
preenchida. O blog agora é interno (/blog), sempre no menu.
"""
from publica import _esc, _FONTES, _CSS


# logo (mesmo desenho de static/icons/icon.svg), inline pra não depender de rede
def _logo(cls: str = "lp-logo") -> str:
    return (
        f'<svg class="{cls}" viewBox="0 0 512 512" role="img" aria-label="Lombada">'
        '<rect width="512" height="512" rx="96" fill="#ECE4D4"/>'
        '<rect x="52" y="52" width="408" height="408" rx="62" fill="none" '
        'stroke="#973E2B" stroke-width="24"/>'
        '<path d="M168 126h70v204h132v64H168z" fill="#1A1714"/></svg>'
    )


_LANDING_CSS = """
html{scroll-behavior:smooth}
.lp-nav{position:sticky;top:0;z-index:20;display:flex;align-items:center;justify-content:space-between;gap:14px;flex-wrap:wrap;padding:12px 0;margin-bottom:8px;background:var(--paper);border-bottom:1px solid var(--rule)}
.lp-brand{display:flex;align-items:center;gap:9px;font-family:"Fraunces",serif;font-style:italic;font-weight:600;font-size:19px}
.lp-brand .dot{color:var(--gold)}
.lp-brand svg{width:26px;height:26px;border-radius:7px}
.lp-nav-links{display:flex;align-items:center;gap:6px;flex-wrap:wrap}
.lp-nav-links a{font-family:"Space Mono",monospace;font-size:10px;letter-spacing:.12em;text-transform:uppercase;color:var(--dim);padding:6px 8px}
.lp-nav-links a:hover{color:var(--ink)}
.lp-nav-links a.lp-nav-cta{color:var(--paper);background:var(--ink);border:1px solid var(--ink)}
.lp{max-width:720px;margin:0 auto}
.lp-hero{text-align:center;padding:26px 0 8px}
.lp-logo{width:72px;height:72px;border-radius:20px;box-shadow:var(--shadow);display:inline-block}
.lp-tag{font-family:"Space Mono",monospace;font-size:10px;letter-spacing:.18em;text-transform:uppercase;color:var(--dim);margin-top:16px}
.lp-hero h1{font-family:"Fraunces",serif;font-style:italic;font-weight:400;font-size:36px;line-height:1.08;margin:14px auto 0;max-width:18ch}
.lp-hero h1 em{font-style:normal;color:var(--gold)}
.lp-sub{font-size:18px;line-height:1.5;color:var(--ink-2);margin:18px auto 0;max-width:42ch}
.lp-ctas{display:flex;flex-wrap:wrap;gap:12px;justify-content:center;margin:30px 0 6px}
.lp-btn{display:inline-block;padding:15px 26px;font-family:"Space Mono",monospace;font-size:12px;letter-spacing:.16em;text-transform:uppercase;border:1px solid var(--ink);cursor:pointer}
.lp-btn.primary{background:var(--ink);color:var(--paper)}
.lp-btn.ghost{background:transparent;color:var(--ink)}
.lp-note{font-family:"Space Mono",monospace;font-size:10px;color:var(--dim);letter-spacing:.06em;text-align:center;margin-top:4px}
.lp-pillars{display:grid;gap:16px;margin-top:40px}
@media(min-width:560px){.lp-pillars{grid-template-columns:repeat(2,1fr)}}
.lp-pillar{border:1px solid var(--rule);background:rgba(255,255,255,.10);padding:22px}
html[data-theme="dark"] .lp-pillar{background:rgba(243,235,221,.05)}
.lp-pillar .k{font-family:"Space Mono",monospace;font-size:10px;letter-spacing:.14em;text-transform:uppercase;color:var(--gold)}
.lp-pillar h3{font-family:"Fraunces",serif;font-style:italic;font-weight:400;font-size:22px;margin:8px 0 8px}
.lp-pillar p{font-size:15px;line-height:1.5;color:var(--ink-2)}
.lp-section{margin-top:56px;border-top:1px solid var(--rule);padding-top:34px;scroll-margin-top:70px}
.lp-section h2{font-family:"Fraunces",serif;font-style:italic;font-weight:400;font-size:26px;margin-bottom:8px}
.lp-section .label{display:block;margin-bottom:12px}
.lp-prose{font-size:16px;line-height:1.6;color:var(--ink-2)}
.lp-prose p{margin-top:14px}.lp-prose p:first-child{margin-top:0}
.lp-prose h2{font-family:"Fraunces",serif;font-style:italic;font-weight:400;font-size:24px;margin:26px 0 4px;color:var(--ink)}
.lp-prose h3{font-family:"Fraunces",serif;font-style:italic;font-weight:400;font-size:20px;margin:20px 0 4px;color:var(--ink)}
.lp-prose a{color:var(--gold);border-bottom:1px solid var(--rule)}
.lp-prose ul,.lp-prose ol{margin:12px 0 0 22px}.lp-prose li{margin-top:6px}
.lp-prose strong{color:var(--ink)}
.lp-steps{display:grid;gap:20px;margin-top:8px}
@media(min-width:560px){.lp-steps{grid-template-columns:repeat(3,1fr)}}
.lp-step{border:1px solid var(--rule);background:rgba(255,255,255,.10);padding:20px}
html[data-theme="dark"] .lp-step{background:rgba(243,235,221,.05)}
.lp-step .n{font-family:"Space Mono",monospace;font-size:11px;color:var(--gold);letter-spacing:.12em}
.lp-step h3{font-family:"Fraunces",serif;font-style:italic;font-weight:400;font-size:20px;margin:8px 0 6px}
.lp-step p{font-size:15px;line-height:1.5;color:var(--ink-2)}
.lp-feats{display:grid;gap:14px;margin-top:8px}
@media(min-width:560px){.lp-feats{grid-template-columns:repeat(2,1fr)}}
.lp-feat{display:flex;gap:12px;align-items:flex-start}
.lp-feat .b{font-family:"Fraunces",serif;font-style:italic;font-size:22px;color:var(--gold);line-height:1;margin-top:2px}
.lp-feat h3{font-family:"Fraunces",serif;font-style:italic;font-weight:400;font-size:18px;margin-bottom:2px}
.lp-feat p{font-size:14px;line-height:1.45;color:var(--dim)}
.lp-support{text-align:center;border:1px solid var(--rule);background:rgba(255,255,255,.10);padding:30px 22px;margin-top:14px}
html[data-theme="dark"] .lp-support{background:rgba(243,235,221,.05)}
.lp-support p{font-size:16px;line-height:1.55;color:var(--ink-2);margin:10px auto 20px;max-width:42ch}
.lp-page-head{padding:14px 0 4px}
.lp-page-head .label{display:block;margin-bottom:10px}
.lp-page-head h1{font-family:"Fraunces",serif;font-style:italic;font-weight:400;font-size:34px;line-height:1.1}
.lp-page-head .lp-date{font-family:"Space Mono",monospace;font-size:11px;color:var(--dim);letter-spacing:.06em;margin-top:10px}
.lp-posts{display:grid;gap:2px;margin-top:22px}
.lp-post-item{display:block;border-top:1px solid var(--rule);padding:20px 0}
.lp-post-item:hover{background:rgba(255,255,255,.05)}
.lp-post-item .d{font-family:"Space Mono",monospace;font-size:10px;color:var(--dim);letter-spacing:.08em;text-transform:uppercase}
.lp-post-item h2{font-family:"Fraunces",serif;font-style:italic;font-weight:400;font-size:23px;margin:6px 0 6px}
.lp-post-item p{font-size:15px;line-height:1.5;color:var(--ink-2)}
.lp-empty{border:1px dashed var(--rule);background:rgba(255,255,255,.10);padding:28px;text-align:center;color:var(--dim);font-style:italic;margin-top:22px}
.lp-back{display:inline-block;margin-top:34px;font-family:"Space Mono",monospace;font-size:10px;letter-spacing:.12em;text-transform:uppercase;color:var(--dim);border-bottom:1px solid var(--rule);padding-bottom:1px}
.lp-foot{margin-top:52px;border-top:1px solid var(--rule);padding:24px 0 40px;text-align:center;font-family:"Space Mono",monospace;font-size:11px;color:var(--dim);letter-spacing:.06em}
.lp-foot a{border-bottom:1px solid var(--rule);padding-bottom:1px}
.lp-foot .sep{margin:0 8px;opacity:.5}
"""


def _nav(app_url: str) -> str:
    """Menu do topo — links absolutos, funcionam de qualquer página institucional."""
    links = (
        '<a href="/quem-somos">quem somos</a>'
        '<a href="/blog">blog</a>'
        '<a href="/sobre#contribua">contribua</a>'
        f'<a class="lp-nav-cta" href="{_esc(app_url)}">abrir o app</a>'
    )
    return (
        '<nav class="lp-nav">'
        f'<a class="lp-brand" href="/sobre">{_logo("")}Lombada<span class="dot">.</span></a>'
        f'<div class="lp-nav-links">{links}</div>'
        '</nav>'
    )


def _footer(app_url: str, instagram_url: str = "") -> str:
    links = [
        f'<a href="{_esc(app_url)}">abrir o app</a>',
        '<a href="/quem-somos">quem somos</a>',
        '<a href="/blog">blog</a>',
        '<a href="/sobre#contribua">contribua</a>',
    ]
    if instagram_url:
        links.append(f'<a href="{_esc(instagram_url)}" rel="noopener" target="_blank">instagram</a>')
    foot = '<span class="sep">·</span>'.join(links)
    return (
        f'<footer class="lp-foot">{foot}<div style="margin-top:10px;opacity:.7">'
        'Lombada — feito no Brasil, pra quem lê em português.</div></footer>'
    )


def _shell(title: str, inner: str, og: dict | None = None,
           app_url: str = "/", instagram_url: str = "", description: str = "") -> str:
    """Documento HTML completo com nav + conteúdo + rodapé."""
    og_tags = ""
    if og:
        og_tags = "".join(
            f'<meta property="og:{k}" content="{_esc(v)}">' for k, v in og.items()
        ) + '<meta name="twitter:card" content="summary_large_image">'
    desc_tag = f'<meta name="description" content="{_esc(description)}">' if description else ""
    return (
        '<!DOCTYPE html><html lang="pt-BR"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<script>(function(){try{var t=localStorage.getItem("lombada_theme");'
        'if(t!=="light"&&t!=="dark"){t=window.matchMedia&&matchMedia("(prefers-color-scheme: dark)").matches?"dark":"light"}'
        'document.documentElement.setAttribute("data-theme",t);'
        'var m=document.createElement("meta");m.name="theme-color";m.content=t==="dark"?"#0E0D0B":"#ECE4D4";document.head.appendChild(m);'
        '}catch(e){}})()</script>'
        f'<title>{_esc(title)}</title>{desc_tag}{og_tags}{_FONTES}'
        f'<style>{_CSS}</style><style>{_LANDING_CSS}</style></head>'
        '<body><div class="wrap">'
        f'{_nav(app_url)}<main class="lp">{inner}</main>{_footer(app_url, instagram_url)}'
        '</div></body></html>'
    )


def _step(n: str, titulo: str, texto: str) -> str:
    return (
        f'<div class="lp-step"><div class="n">{_esc(n)}</div>'
        f'<h3>{_esc(titulo)}</h3><p>{_esc(texto)}</p></div>'
    )


def _feat(b: str, titulo: str, texto: str) -> str:
    return (
        f'<div class="lp-feat"><div class="b">{_esc(b)}</div>'
        f'<div><h3>{_esc(titulo)}</h3><p>{_esc(texto)}</p></div></div>'
    )


def _pillar(kicker: str, titulo: str, texto: str) -> str:
    return (
        f'<div class="lp-pillar"><div class="k">{_esc(kicker)}</div>'
        f'<h3>{_esc(titulo)}</h3><p>{_esc(texto)}</p></div>'
    )


# ─────────────────────────── /sobre (landing) ───────────────────────────
def render_landing(
    app_url: str = "/",
    play_store_url: str = "",
    apoio_url: str = "",
    instagram_url: str = "",
    blog_url: str = "",  # mantido por compat; blog agora é interno (/blog)
) -> str:
    app_url = app_url or "/"

    ctas = [f'<a class="lp-btn primary" href="{_esc(app_url)}">abrir o app</a>']
    if play_store_url:
        ctas.append(f'<a class="lp-btn ghost" href="{_esc(play_store_url)}">instalar no Android</a>')
    else:
        ctas.append(f'<a class="lp-btn ghost" href="{_esc(app_url)}">usar no navegador</a>')
    ctas_html = "".join(ctas)

    play_note = "" if play_store_url else '<p class="lp-note">app Android chegando na Play Store — por enquanto, roda direto no navegador (e instala como PWA)</p>'

    pillars = "".join([
        _pillar("rede social", "Uma rede social de livros",
                "Registre o que leu, dê nota e escreva a crítica. Monte uma estante que é sua, siga outros leitores e acompanhe o feed de quem você segue."),
        _pillar("catálogo", "O catálogo mais completo do Brasil",
                "Pesquise entre livros publicados no Brasil com editora, tradução e ISBN certos — um catálogo próprio, alimentado direto dos sites das editoras brasileiras."),
    ])

    steps = "".join([
        _step("01", "Busque a edição", "Ache o livro no catálogo — com editora, tradução, ano e capa certos. Nada de misturar edições."),
        _step("02", "Registre a leitura", "Marque como quero ler, lendo ou lido. Dê nota, escreva a crítica, guarde o que achou."),
        _step("03", "Monte sua estante", "Sua estante vira uma página pública compartilhável. Siga outros leitores e veja o feed."),
    ])

    feats = "".join([
        _feat("✦", "Edição importa", "Diferencia edições e traduções da mesma obra — o catálogo é próprio, alimentado de editoras brasileiras."),
        _feat("✦", "Busca de verdade", "Pesquise por título, autor, editora ou tradução. A fonte mais completa pra achar livros publicados no Brasil."),
        _feat("✦", "Estante compartilhável", "Um perfil com cara de estante real pra mostrar o que você lê, com nota e crítica."),
        _feat("✦", "Sem fricção", "Começa a usar na hora, login opcional. Funciona offline como app instalável."),
    ])

    support_btn = (
        f'<a class="lp-btn primary" href="{_esc(apoio_url)}" rel="noopener" target="_blank">apoiar ☕</a>'
        if apoio_url else ''
    )
    contribua = (
        '<section class="lp-section" id="contribua"><span class="label">contribua</span>'
        '<h2>Ajude o Lombada a crescer</h2>'
        '<div class="lp-support">'
        '<p>O Lombada é independente e roda de graça. Você ajuda de dois jeitos: '
        'usando o app e sugerindo livros que faltam no catálogo — e, se puder e ele '
        'te for útil, com um cafezinho que mantém o servidor no ar.</p>'
        f'{support_btn}</div></section>'
    )

    inner = (
        '<section class="lp-hero">'
        f'{_logo()}'
        '<div class="lp-tag">tipo Letterboxd, mas pra livros</div>'
        '<h1>Uma rede social de livros. E a fonte mais completa pra '
        '<em>pesquisar livros</em> no Brasil.</h1>'
        '<p class="lp-sub">Registre o que leu — com a edição e a tradução certas —, '
        'siga outros leitores e monte sua estante. Tudo sobre o catálogo de livros '
        'brasileiros mais completo, feito direto das editoras.</p>'
        f'<div class="lp-ctas">{ctas_html}</div>'
        f'{play_note}'
        f'<div class="lp-pillars">{pillars}</div>'
        '</section>'
        '<section class="lp-section"><span class="label">como funciona</span>'
        f'<div class="lp-steps">{steps}</div></section>'
        '<section class="lp-section"><span class="label">por que</span>'
        '<h2>O que muda no Lombada</h2>'
        f'<div class="lp-feats">{feats}</div></section>'
        f'{contribua}'
    )

    og = {
        "title": "Lombada — rede social de livros e catálogo do Brasil",
        "description": "Rede social de livros e a fonte mais completa pra pesquisar livros publicados no Brasil.",
        "type": "website",
    }
    return _shell(
        "Lombada — rede social de livros e catálogo do Brasil",
        inner, og, app_url, instagram_url,
        description="Rede social de livros e a fonte mais completa pra pesquisar livros publicados no Brasil. Registre o que leu, com qual edição e tradução.",
    )


# ─────────────────────────── /quem-somos ───────────────────────────
def render_quem_somos(app_url: str = "/", instagram_url: str = "") -> str:
    inner = (
        '<header class="lp-page-head"><span class="label">quem somos</span>'
        '<h1>Um projeto independente, feito por quem lê</h1></header>'
        '<div class="lp-prose">'
        '<p>O Lombada nasceu de uma vontade simples: ter, em português, um lugar '
        'sério pra registrar leituras — que respeite qual edição e qual tradução '
        'você leu — e, junto, um catálogo de verdade dos livros publicados no Brasil.</p>'
        '<h2>Por que existe</h2>'
        '<p>Os apps que existiam ou eram de fora (com catálogo pobre em livros '
        'brasileiros e edições misturadas) ou não levavam a sério a diferença entre '
        'uma edição e outra. Pra quem se importa com tradução, editora e projeto '
        'gráfico, isso faz toda a diferença. O Lombada trata edição como cidadã de '
        'primeira classe.</p>'
        '<h2>Como o catálogo é feito</h2>'
        '<p>O catálogo é próprio, alimentado por raspagem direta dos sites das '
        'editoras brasileiras — do 34 à Companhia das Letras, passando por Record, '
        'Todavia, Autêntica, universitárias e muitas outras. É por isso que ele é, '
        'hoje, a fonte mais completa pra pesquisar livros publicados no Brasil.</p>'
        '<h2>Nosso compromisso</h2>'
        '<p>Sem anúncio e sem venda de dado. É um projeto tocado por uma pessoa só, '
        'e a intenção é manter assim: leve, honesto e focado em quem lê. Se ele te '
        'for útil, você pode <a href="/sobre#contribua">contribuir</a> — mas o '
        'essencial vai ser sempre de graça.</p>'
        '</div>'
        '<a class="lp-back" href="/sobre">← voltar pra apresentação</a>'
    )
    og = {"title": "Quem somos — Lombada", "type": "website",
          "description": "O Lombada é um projeto independente com catálogo próprio dos livros publicados no Brasil."}
    return _shell("Quem somos — Lombada", inner, og, app_url, instagram_url,
                  description="O Lombada é um projeto independente, com catálogo próprio dos livros publicados no Brasil.")


# ─────────────────────────── /blog ───────────────────────────
def render_blog_index(posts: list, app_url: str = "/", instagram_url: str = "") -> str:
    if posts:
        itens = "".join(
            f'<a class="lp-post-item" href="/blog/{_esc(p["slug"])}">'
            + (f'<div class="d">{_esc(p["data"])}</div>' if p.get("data") else '')
            + f'<h2>{_esc(p["titulo"])}</h2>'
            + (f'<p>{_esc(p["resumo"])}</p>' if p.get("resumo") else '')
            + '</a>'
            for p in posts
        )
        corpo = f'<div class="lp-posts">{itens}</div>'
    else:
        corpo = '<div class="lp-empty">Ainda não há posts por aqui. Em breve. 📚</div>'
    inner = (
        '<header class="lp-page-head"><span class="label">blog</span>'
        '<h1>Notas do Lombada</h1></header>'
        f'{corpo}'
        '<a class="lp-back" href="/sobre">← voltar pra apresentação</a>'
    )
    og = {"title": "Blog — Lombada", "type": "website",
          "description": "Notas, novidades e bastidores do Lombada."}
    return _shell("Blog — Lombada", inner, og, app_url, instagram_url,
                  description="Notas, novidades e bastidores do Lombada.")


def render_blog_post(post: dict, app_url: str = "/", instagram_url: str = "") -> str:
    data_html = f'<div class="lp-date">{_esc(post["data"])}</div>' if post.get("data") else ""
    inner = (
        '<header class="lp-page-head"><span class="label">blog</span>'
        f'<h1>{_esc(post["titulo"])}</h1>{data_html}</header>'
        f'<article class="lp-prose" style="margin-top:24px">{post["corpo_html"]}</article>'
        '<a class="lp-back" href="/blog">← todos os posts</a>'
    )
    og = {"title": f'{post["titulo"]} — Lombada', "type": "article",
          "description": post.get("resumo", "")}
    return _shell(f'{post["titulo"]} — Lombada', inner, og, app_url, instagram_url,
                  description=post.get("resumo", ""))
