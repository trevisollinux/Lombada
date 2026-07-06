"""
Lombada — landing page (/sobre): apresenta o app pra quem chega de fora.

Reaproveita os tokens de design da estante pública (publica.py): mesma paleta
paper/ink, fontes e troca de tema claro/escuro. Não usa o menu inferior do app
(_TABS) porque aqui o objetivo é converter visitante → app, não navegar.

Os botões de "instalar no Android" e "apoiar" só aparecem quando as env vars
correspondentes estão preenchidas — assim a página fica coerente antes de a
conta da Play Store / do apoio existir.
"""
from publica import _esc, _FONTES, _CSS


# logo (mesmo desenho de static/icons/icon.svg), inline pra não depender de rede
_LOGO = (
    '<svg class="lp-logo" viewBox="0 0 512 512" role="img" aria-label="Lombada">'
    '<rect width="512" height="512" rx="96" fill="#ECE4D4"/>'
    '<rect x="52" y="52" width="408" height="408" rx="62" fill="none" '
    'stroke="#973E2B" stroke-width="24"/>'
    '<path d="M168 126h70v204h132v64H168z" fill="#1A1714"/></svg>'
)

_LANDING_CSS = """
.lp{max-width:680px;margin:0 auto}
.lp-hero{text-align:center;padding:16px 0 8px}
.lp-logo{width:76px;height:76px;border-radius:20px;box-shadow:var(--shadow);display:inline-block}
.lp .wordmark{font-size:26px;margin-top:14px;display:inline-block}
.lp-tag{font-family:"Space Mono",monospace;font-size:10px;letter-spacing:.18em;text-transform:uppercase;color:var(--dim);margin-top:10px}
.lp-hero h1{font-family:"Fraunces",serif;font-style:italic;font-weight:400;font-size:38px;line-height:1.06;margin:18px auto 0;max-width:14ch}
.lp-sub{font-size:18px;line-height:1.5;color:var(--ink-2);margin:16px auto 0;max-width:38ch}
.lp-ctas{display:flex;flex-wrap:wrap;gap:12px;justify-content:center;margin:30px 0 6px}
.lp-btn{display:inline-block;padding:15px 26px;font-family:"Space Mono",monospace;font-size:12px;letter-spacing:.16em;text-transform:uppercase;border:1px solid var(--ink);cursor:pointer}
.lp-btn.primary{background:var(--ink);color:var(--paper)}
.lp-btn.ghost{background:transparent;color:var(--ink)}
.lp-note{font-family:"Space Mono",monospace;font-size:10px;color:var(--dim);letter-spacing:.06em;text-align:center;margin-top:4px}
.lp-section{margin-top:52px;border-top:1px solid var(--rule);padding-top:34px}
.lp-section h2{font-family:"Fraunces",serif;font-style:italic;font-weight:400;font-size:26px;margin-bottom:8px}
.lp-section .label{display:block;margin-bottom:12px}
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
.lp-support{text-align:center;border:1px solid var(--rule);background:rgba(255,255,255,.10);padding:30px 22px;margin-top:52px}
html[data-theme="dark"] .lp-support{background:rgba(243,235,221,.05)}
.lp-support p{font-size:16px;line-height:1.5;color:var(--ink-2);margin:10px auto 20px;max-width:40ch}
.lp-foot{margin-top:46px;border-top:1px solid var(--rule);padding:24px 0 40px;text-align:center;font-family:"Space Mono",monospace;font-size:11px;color:var(--dim);letter-spacing:.06em}
.lp-foot a{border-bottom:1px solid var(--rule);padding-bottom:1px}
.lp-foot .sep{margin:0 8px;opacity:.5}
"""


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


def render_landing(
    app_url: str = "/",
    play_store_url: str = "",
    apoio_url: str = "",
    instagram_url: str = "",
) -> str:
    """HTML completo da landing. URLs vazias omitem os botões/links correspondentes."""
    app_url = app_url or "/"

    # CTAs do hero
    ctas = [f'<a class="lp-btn primary" href="{_esc(app_url)}">abrir o app</a>']
    if play_store_url:
        ctas.append(f'<a class="lp-btn ghost" href="{_esc(play_store_url)}">instalar no Android</a>')
    else:
        ctas.append('<a class="lp-btn ghost" href="' + _esc(app_url) + '">usar no navegador</a>')
    ctas_html = "".join(ctas)

    play_note = "" if play_store_url else '<p class="lp-note">app Android chegando na Play Store — por enquanto, roda direto no navegador (e instala como PWA)</p>'

    steps = "".join([
        _step("01", "Busque a edição", "Ache o livro no catálogo — com editora, tradução, ano e capa certos. Nada de misturar edições."),
        _step("02", "Registre a leitura", "Marque como quero ler, lendo ou lido. Dê nota, escreva a crítica, guarde o que achou."),
        _step("03", "Monte sua estante", "Sua estante vira uma página pública compartilhável. Siga outros leitores e veja o feed."),
    ])

    feats = "".join([
        _feat("✦", "Edição importa", "Diferencia edições e traduções da mesma obra — o catálogo é próprio, alimentado de editoras brasileiras."),
        _feat("✦", "Crítica de verdade", "Nota, relato e spoiler marcado. Sua opinião fica registrada, pública ou só pra você."),
        _feat("✦", "Estante compartilhável", "Um perfil com cara de estante real pra mostrar o que você lê."),
        _feat("✦", "Sem fricção", "Começa a usar na hora, login opcional. Funciona offline como app instalável."),
    ])

    # seção de apoio (só com APOIO_URL)
    support = ""
    if apoio_url:
        support = (
            '<div class="lp-support"><span class="label">apoie o projeto</span>'
            '<p>O Lombada é feito por uma pessoa só e roda de graça. Se ele te ajuda '
            'a organizar suas leituras, um cafezinho mantém as luzes acesas.</p>'
            f'<a class="lp-btn primary" href="{_esc(apoio_url)}" rel="noopener" target="_blank">apoiar ☕</a></div>'
        )

    # rodapé
    foot_links = [f'<a href="{_esc(app_url)}">abrir o app</a>']
    if apoio_url:
        foot_links.append(f'<a href="{_esc(apoio_url)}" rel="noopener" target="_blank">apoiar</a>')
    if instagram_url:
        foot_links.append(f'<a href="{_esc(instagram_url)}" rel="noopener" target="_blank">instagram</a>')
    foot = '<span class="sep">·</span>'.join(foot_links)

    corpo = (
        f'<style>{_LANDING_CSS}</style>'
        '<main class="lp">'
        '<section class="lp-hero">'
        f'{_LOGO}'
        '<div class="wordmark">Lombada<span class="dot">.</span></div>'
        '<div class="lp-tag">diário de leituras</div>'
        '<h1>Tipo Letterboxd, mas pra livros.</h1>'
        '<p class="lp-sub">Registre o que leu, com qual edição e tradução. '
        'Dê nota, escreva a crítica e monte uma estante que é sua.</p>'
        f'<div class="lp-ctas">{ctas_html}</div>'
        f'{play_note}'
        '</section>'

        '<section class="lp-section"><span class="label">como funciona</span>'
        f'<div class="lp-steps">{steps}</div></section>'

        '<section class="lp-section"><span class="label">por que</span>'
        '<h2>O que muda no Lombada</h2>'
        f'<div class="lp-feats">{feats}</div></section>'

        f'{support}'

        f'<footer class="lp-foot">{foot}<div style="margin-top:10px;opacity:.7">'
        'Lombada — feito no Brasil, pra quem lê em português.</div></footer>'
        '</main>'
    )

    og = {
        "title": "Lombada — diário de leituras",
        "description": "Registre o que leu, com qual edição e tradução. Tipo Letterboxd, mas pra livros.",
        "type": "website",
    }
    og_tags = "".join(
        f'<meta property="og:{k}" content="{_esc(v)}">' for k, v in og.items()
    ) + '<meta name="twitter:card" content="summary_large_image">'
    og_tags += '<meta name="description" content="Registre o que leu, com qual edição e tradução. Tipo Letterboxd, mas pra livros.">'

    return (
        '<!DOCTYPE html><html lang="pt-BR"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<script>(function(){try{var t=localStorage.getItem("lombada_theme");'
        'if(t!=="light"&&t!=="dark"){t=window.matchMedia&&matchMedia("(prefers-color-scheme: dark)").matches?"dark":"light"}'
        'document.documentElement.setAttribute("data-theme",t);'
        'var m=document.createElement("meta");m.name="theme-color";m.content=t==="dark"?"#0E0D0B":"#ECE4D4";document.head.appendChild(m);'
        '}catch(e){}})()</script>'
        '<title>Lombada — diário de leituras</title>'
        f'{og_tags}{_FONTES}<style>{_CSS}</style></head>'
        '<body><div class="wrap">'  # .wrap dá o padding/centragem base
        + corpo +
        '</div></body></html>'
    )
