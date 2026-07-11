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


# Logo público compartilhado com o app (mesmo desenho do header da SPA).
def _logo_mark(mark_cls: str = "brand-logo__mark") -> str:
    return (
        f'<span class="{mark_cls}" aria-hidden="true">'
        '<svg viewBox="448 397 183 293" aria-hidden="true" focusable="false">'
        '<path fill="currentColor" d="M448 397.7c0 .5 2.7 2 5.9 3.5 10.5 4.9 9.6-9.2 9.9 141L464 673l4.3-.6c3.6-.4 5.5.2 13.2 4l9 4.5-14.8.1c-13.5 0-15.2.2-17.8 2.1-1.6 1.1-4.5 2.5-6.5 3.1-2 .5-3.4 1.4-3.1 2.1.3.9 22.3 1.3 91.5 1.5l91.2.2v-29c0-15.9-.4-29-.8-29s-1.8 3.2-3.1 7c-5.2 16.2-10.7 24.9-20.3 32.3-11.6 8.8-13.5 9.1-57.3 9.5-37.9.3-38 .3-42.4-2-5.3-2.7-7.9-6-9.1-11.4-.6-2.2-1-60.8-1-137.2V397h-24.5c-13.5 0-24.5.3-24.5.7"/>'
        '<path fill="currentColor" d="M511.5 399.2c-.3 1.3-.4 61.6-.3 134.1.3 115.8.5 131.9 1.8 132.7.8.5 3.9 1 6.8 1h5.2V538.1c0-110.2.2-129 1.4-130 .8-.7 3.6-1.1 6.3-.9l4.8.3.5 129.2c.3 71 .7 129.4 1 129.6.6.6 6.3 1.1 10.2.8l2.8-.1.2-129.8c.3-123 .4-129.9 2.1-132.5 1-1.5 3.4-3.5 5.2-4.4 1.9-.9 3.5-2 3.5-2.5 0-.4-11.5-.8-25.5-.8H512z"/>'
        '</svg></span>'
    )


def _brand_logo(cls: str = "lp-brand brand-logo brand-logo--wordmark", mark_cls: str = "brand-logo__mark") -> str:
    return (
        f'<span class="{cls}" role="img" aria-label="Lombada">'
        f'{_logo_mark(mark_cls)}'
        '<span class="lp-brand-word brand-logo__word"><span class="brand-logo__rest">ombada</span><span class="dot">.</span></span>'
        '</span>'
    )


_LANDING_CSS = """
html{scroll-behavior:smooth}
.lp-nav{position:sticky;top:0;z-index:20;display:flex;align-items:center;justify-content:space-between;gap:14px;flex-wrap:wrap;padding:12px 0;margin-bottom:8px;background:var(--paper);border-bottom:1px solid var(--rule)}
.lp-brand-link{display:inline-flex;align-items:center;color:inherit;text-decoration:none}
.lp-brand,.lp-hero-brand{display:inline-flex;align-items:center;gap:2px;min-width:0;font-family:"Fraunces",serif;font-style:normal;font-weight:650;letter-spacing:-.055em;color:var(--ink)}
.lp-brand{font-size:21px;line-height:1}.lp-brand .dot,.lp-hero-brand .dot{color:var(--gold)}
.brand-logo__mark{flex:0 0 auto;width:auto;height:.92em;padding:0;border:0;border-radius:0;background:transparent;color:var(--ink);align-self:baseline;transform:translateY(.075em);display:inline-flex;align-items:center;justify-content:center}
.brand-logo__mark svg{height:100%;width:auto;display:block;fill:currentColor;overflow:visible}
.lp-brand-word{white-space:nowrap}
.lp-nav-links{display:flex;align-items:center;gap:6px;flex-wrap:wrap}
.lp-nav-links a{font-family:"Space Mono",monospace;font-size:10px;letter-spacing:.12em;text-transform:uppercase;color:var(--dim);padding:6px 8px}
.lp-nav-links a:hover{color:var(--ink)}
.lp-nav-links a.lp-nav-cta{color:var(--paper);background:var(--ink);border:1px solid var(--ink)}
.lp{max-width:720px;margin:0 auto}
.lp-hero{text-align:center;padding:26px 0 8px}
.lp-logo{width:72px;height:72px;border-radius:20px;box-shadow:var(--shadow);display:inline-block;flex:0 0 auto}
.lp-hero-brand{font-size:clamp(38px,9vw,58px);line-height:.95;gap:2px;justify-content:center}
.lp-hero-brand .brand-logo__mark{height:.92em}
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

.lp-code{display:block;max-width:100%;box-sizing:border-box;background:var(--paper-3);color:var(--ink);border:1px solid var(--rule);padding:14px 16px;overflow-x:auto;font-family:"Space Mono",monospace;font-size:12px;line-height:1.55;white-space:pre;border-radius:10px;-webkit-overflow-scrolling:touch;opacity:1;scrollbar-color:var(--gold) var(--paper-3);scrollbar-width:thin}
.lp-code code,.lp-code pre,.lp-prose .lp-code code,.lp-prose .lp-code pre{font:inherit;color:var(--ink);background:transparent;padding:0;border:0;white-space:inherit;opacity:1}
.lp-code::-webkit-scrollbar{height:10px}.lp-code::-webkit-scrollbar-track{background:var(--paper-3)}.lp-code::-webkit-scrollbar-thumb{background:var(--gold);border-radius:999px}
.lp-prose input,.lp-prose textarea,.api-card input,.api-card textarea{background:var(--paper-3);color:var(--ink);border:1px solid var(--rule);border-radius:10px;padding:10px 12px;opacity:1;-webkit-text-fill-color:var(--ink)}
.lp-prose input::placeholder,.lp-prose textarea::placeholder,.api-card input::placeholder,.api-card textarea::placeholder{color:var(--dim);opacity:1}
html[data-theme="dark"] .lp-code,html[data-theme="dark"] .lp-code code,html[data-theme="dark"] .lp-code pre,html[data-theme="dark"] .lp-prose .lp-code code,html[data-theme="dark"] .lp-prose .lp-code pre{background:#171310;color:#F3EBDD}
html[data-theme="dark"] .lp-prose input,html[data-theme="dark"] .lp-prose textarea,html[data-theme="dark"] .api-card input,html[data-theme="dark"] .api-card textarea{background:#171310;color:#F3EBDD;-webkit-text-fill-color:#F3EBDD}
html[data-theme="dark"] .lp-prose input::placeholder,html[data-theme="dark"] .lp-prose textarea::placeholder,html[data-theme="dark"] .api-card input::placeholder,html[data-theme="dark"] .api-card textarea::placeholder{color:#CABEAA;opacity:1}
.lp-inline-code,.lp-prose code{font-family:"Space Mono",monospace;font-size:.92em;background:rgba(0,0,0,.06);padding:2px 5px;border-radius:5px;color:var(--ink)}
html[data-theme="dark"] .lp-inline-code,html[data-theme="dark"] .lp-prose code{background:rgba(255,255,255,.08);color:var(--ink)}
.api-notice{border:1px solid var(--rule);background:rgba(151,62,43,.08);padding:18px 20px;border-radius:14px;color:var(--ink-2);margin:22px 0 24px;font-size:15px;line-height:1.5}
html[data-theme="dark"] .api-notice{background:rgba(243,235,221,.05)}
.api-kicker{font-family:"Space Mono",monospace;font-size:10px;letter-spacing:.16em;text-transform:uppercase;color:var(--gold);margin:30px 0 10px}
.api-endpoints{display:grid;gap:14px;margin-top:16px}
.api-card{border:1px solid var(--rule);background:rgba(255,255,255,.10);border-radius:16px;padding:18px;min-width:0}
html[data-theme="dark"] .api-card{background:rgba(243,235,221,.05)}
.api-card-head{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:10px}
.api-method{font-family:"Space Mono",monospace;font-size:11px;letter-spacing:.12em;color:var(--paper);background:var(--ink);border:1px solid var(--ink);border-radius:999px;padding:4px 8px;line-height:1}
.api-route{font-family:"Space Mono",monospace;font-size:15px;color:var(--ink);overflow-wrap:anywhere}
.api-desc{font-size:15px;line-height:1.5;color:var(--ink-2);margin:0 0 12px}
.api-params{display:flex;gap:7px;flex-wrap:wrap;margin-top:10px}
.api-param{font-family:"Space Mono",monospace;font-size:11px;color:var(--ink);background:rgba(0,0,0,.06);border:1px solid var(--rule);border-radius:999px;padding:4px 8px}
html[data-theme="dark"] .api-param{background:rgba(255,255,255,.08)}
.api-example{font-size:13px;line-height:1.45;color:var(--dim);margin-top:12px;overflow-wrap:anywhere}
.api-example .lp-inline-code{font-size:11px}
.lp-theme{border:1px solid var(--rule);background:rgba(255,255,255,.10);border-radius:16px;padding:20px;margin-top:14px}
html[data-theme="dark"] .lp-theme{background:rgba(243,235,221,.05)}
.lp-theme p{font-size:15px;line-height:1.5;color:var(--ink-2);margin:0 0 14px}
.lp-theme-options{display:grid;grid-template-columns:repeat(2,1fr);gap:9px}
.lp-theme-option{min-width:0;cursor:pointer}.lp-theme-option input{position:absolute;opacity:0;pointer-events:none}
.lp-theme-option span{display:block;border:1px solid var(--rule);border-radius:999px;background:transparent;color:var(--ink);font-family:"Space Mono",monospace;font-size:11px;letter-spacing:.12em;text-align:center;text-transform:uppercase;padding:11px 10px;transition:background .16s ease,color .16s ease,border-color .16s ease;opacity:1}
.lp-theme-option input:checked+span{background:var(--ink);border-color:var(--ink);color:var(--paper)}
.lp-theme-option input:focus-visible+span{outline:2px solid var(--gold);outline-offset:2px}
html[data-theme="dark"] .lp-theme-option input:checked+span{background:var(--paper-3);border-color:var(--rule);color:var(--ink)}
.lp-theme-toggle{display:inline-flex;align-items:center;justify-content:center;width:32px;height:32px;padding:0;margin-left:2px;border:1px solid var(--rule);border-radius:999px;background:transparent;color:var(--ink);cursor:pointer;transition:background .16s ease,border-color .16s ease}
.lp-theme-toggle:hover{background:rgba(255,255,255,.06);border-color:var(--ink)}
.lp-theme-toggle:focus-visible{outline:2px solid var(--gold);outline-offset:2px}
.lp-theme-toggle svg{width:15px;height:15px;display:block;fill:none;stroke:currentColor;stroke-width:1.6;stroke-linecap:round;stroke-linejoin:round}
.lp-ti--sun{display:none}
html[data-theme="dark"] .lp-ti--sun{display:block}
html[data-theme="dark"] .lp-ti--moon{display:none}
@media(max-width:520px){.lp-code{font-size:11px;padding:12px 13px}.api-card{padding:16px 14px;border-radius:13px}.api-route{font-size:13px}.api-param{font-size:10px}.api-notice{padding:16px}}
"""


def _theme_toggle() -> str:
    """Botão de alternância de tema — presente na nav de toda página institucional."""
    return (
        '<button type="button" class="lp-theme-toggle" onclick="alternarTemaPublico()"'
        ' aria-label="Alternar tema claro e escuro" title="Alternar tema">'
        '<svg class="lp-ti lp-ti--moon" viewBox="0 0 24 24" aria-hidden="true">'
        '<path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/></svg>'
        '<svg class="lp-ti lp-ti--sun" viewBox="0 0 24 24" aria-hidden="true">'
        '<circle cx="12" cy="12" r="4"/>'
        '<path d="M12 2v2M12 20v2M2 12h2M20 12h2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4'
        'M19.1 4.9l-1.4 1.4M6.3 17.7l-1.4 1.4"/></svg>'
        '</button>'
    )


def _nav(app_url: str) -> str:
    """Menu do topo — links absolutos, funcionam de qualquer página institucional."""
    links = (
        '<a href="/quem-somos">quem somos</a>'
        '<a href="/blog">blog</a>'
        '<a href="/api-docs">API</a>'
        '<a href="/sobre#contribua">contribua</a>'
        f'{_theme_toggle()}'
        f'<a class="lp-nav-cta" href="{_esc(app_url)}">abrir o app</a>'
    )
    return (
        '<nav class="lp-nav">'
        f'<a class="lp-brand-link" href="/sobre">{_brand_logo()}</a>'
        f'<div class="lp-nav-links">{links}</div>'
        '</nav>'
    )


def _footer(app_url: str, instagram_url: str = "") -> str:
    links = [
        f'<a href="{_esc(app_url)}">abrir o app</a>',
        '<a href="/quem-somos">quem somos</a>',
        '<a href="/blog">blog</a>',
        '<a href="/api-docs">API</a>',
        '<a href="/sobre#contribua">contribua</a>',
        '<a href="/privacidade">privacidade</a>',
    ]
    if instagram_url:
        links.append(f'<a href="{_esc(instagram_url)}" rel="noopener" target="_blank">instagram</a>')
    foot = '<span class="sep">·</span>'.join(links)
    return (
        f'<footer class="lp-foot">{foot}<div style="margin-top:10px;opacity:.7">'
        'Como participante do Programa de Associados da Amazon, o Lombada é '
        'remunerado pelas compras qualificadas efetuadas.</div>'
        '<div style="margin-top:10px;opacity:.7">'
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
        '</div><script>(function(){var KEY="lombada_theme";function apply(t){t=t==="dark"?"dark":"light";document.documentElement.setAttribute("data-theme",t);try{localStorage.setItem(KEY,t)}catch(e){};document.querySelectorAll("input[name=publicThemeChoice]").forEach(function(i){i.checked=i.value===t});var m=document.querySelector("meta[name=theme-color]");if(m)m.content=t==="dark"?"#0E0D0B":"#ECE4D4"}window.definirTemaPublico=apply;window.alternarTemaPublico=function(){var cur=document.documentElement.getAttribute("data-theme")==="dark"?"dark":"light";apply(cur==="dark"?"light":"dark")};document.addEventListener("DOMContentLoaded",function(){var t=document.documentElement.getAttribute("data-theme")||"light";document.querySelectorAll("input[name=publicThemeChoice]").forEach(function(i){i.checked=i.value===t})})})()</script></body></html>'
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
    tema = (
        '<section class="lp-section" id="tema"><span class="label">aparência</span>'
        '<h2>Tema</h2>'
        '<div class="lp-theme">'
        '<p>Escolha o tema do Lombada neste navegador. A preferência é salva no mesmo local do app e vale para o site inteiro.</p>'
        '<div class="lp-theme-options" role="radiogroup" aria-label="Tema">'
        '<label class="lp-theme-option"><input type="radio" name="publicThemeChoice" value="light" onchange="definirTemaPublico(this.value)"><span>Claro</span></label>'
        '<label class="lp-theme-option"><input type="radio" name="publicThemeChoice" value="dark" onchange="definirTemaPublico(this.value)"><span>Escuro</span></label>'
        '</div></div></section>'
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
        f'{_brand_logo("lp-hero-brand", "brand-logo__mark")}'
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
        '<section class="lp-section"><span class="label">dados abertos</span>'
        '<h2>Dados abertos do catálogo</h2>'
        '<div class="lp-support"><p>O Lombada também disponibiliza uma API pública para consulta de livros, edições, editoras, traduções e ISBNs catalogados. Ela é gratuita, somente leitura e pensada para pesquisadores, leitores, projetos independentes e desenvolvedores.</p>'
        '<a class="lp-btn ghost" href="/api-docs">Ver documentação da API</a></div></section>'
        f'{tema}'
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



def render_api_docs(base_url: str = "", app_url: str = "/", instagram_url: str = "") -> str:
    base = (base_url.rstrip("/") if base_url else "https://lombada-production.up.railway.app") + "/api/public/v1"
    health_json = '{\n  "ok": true,\n  "service": "lombada-public-api",\n  "version": "v1"\n}'
    books_json = '{\n  "data": [\n    {\n      "id": 1,\n      "work_key": "machado-de-assis-dom-casmurro",\n      "title": "Dom Casmurro",\n      "author": "Machado de Assis",\n      "year": 1899,\n      "original_language": "pt",\n      "description": "",\n      "genres": [],\n      "editions": []\n    }\n  ],\n  "pagination": {\n    "page": 1,\n    "limit": 20,\n    "total": 1,\n    "pages": 1\n  }\n}'

    def endpoint_card(route: str, desc: str, params: list[str] | None = None, example_path: str = "") -> str:
        params_html = ""
        if params:
            params_html = '<div class="api-params" aria-label="Parâmetros">' + "".join(
                f'<span class="api-param">{_esc(param)}</span>' for param in params
            ) + '</div>'
        example_html = (
            f'<div class="api-example">Exemplo: <code class="lp-inline-code">{_esc(example_path)}</code></div>'
            if example_path else ""
        )
        return (
            '<article class="api-card">'
            '<div class="api-card-head"><span class="api-method">GET</span>'
            f'<span class="api-route">{_esc(route)}</span></div>'
            f'<p class="api-desc">{_esc(desc)}</p>{params_html}{example_html}'
            '</article>'
        )

    endpoint_html = "".join([
        endpoint_card("/health", "Status simples da API pública.", example_path="/api/public/v1/health"),
        endpoint_card(
            "/books",
            "Lista obras do catálogo local com paginação e filtros.",
            ["q", "title", "author", "publisher", "translator", "isbn", "language", "year", "has_cover", "page", "limit"],
            "/api/public/v1/books?q=machado&limit=5",
        ),
        endpoint_card("/books/{book_id}", "Detalha uma obra e todas as edições locais relacionadas.", example_path="/api/public/v1/books/1"),
        endpoint_card("/editions/{edition_id}", "Detalha uma edição e a obra associada.", example_path="/api/public/v1/editions/1"),
        endpoint_card("/publishers", "Lista editoras do catálogo com contagem de edições.", ["q", "page", "limit"], "/api/public/v1/publishers?q=companhia"),
        endpoint_card("/literatures", "Lista origens e literaturas catalogadas quando houver dados locais.", example_path="/api/public/v1/literatures"),
    ])

    inner = (
        '<header class="lp-page-head"><span class="label">desenvolvedores</span>'
        '<h1>API pública do Lombada</h1></header>'
        '<div class="lp-prose">'
        '<p>Consulte metadados catalográficos de livros, edições, editoras, traduções e ISBNs do catálogo Lombada.</p>'
        '<div class="api-notice"><strong>A API retorna apenas metadados catalográficos.</strong> Não inclui conteúdo integral de livros nem dados de usuários.</div>'
        '<h2>Base URL</h2>'
        f'<pre class="lp-code"><code>{_esc(base)}</code></pre>'
        '<h2>Quickstart</h2>'
        f'<pre class="lp-code"><code>curl {_esc(base)}/health\ncurl "{_esc(base)}/books?q=machado&amp;limit=5"\ncurl "{_esc(base)}/publishers?q=companhia"</code></pre>'
        '<h2>Endpoints</h2>'
        f'<div class="api-endpoints">{endpoint_html}</div>'
        '<h2>Exemplo de resposta</h2>'
        f'<pre class="lp-code"><code>{_esc(health_json)}\n\n{_esc(books_json)}</code></pre>'
        '<h2>Boas práticas</h2>'
        '<ul><li>Use paginação: <code>page</code> começa em 1 e <code>limit</code> vai até 50.</li><li>Cacheie respostas sempre que possível; as respostas públicas têm cache curto.</li><li>Identifique o Lombada como fonte dos metadados quando reutilizar os dados.</li></ul>'
        '</div><a class="lp-back" href="/sobre">← voltar para /sobre</a>'
    )
    return _shell("API pública do Lombada", inner, {"title": "API pública do Lombada", "type": "website"}, app_url, instagram_url, description="Documentação da API pública somente leitura do catálogo do Lombada.")

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


# ─────────────────────────── /privacidade ───────────────────────────
def render_privacidade(app_url: str = "/", instagram_url: str = "",
                       contact_email: str = "", atualizado_em: str = "") -> str:
    """Política de privacidade (exigida pra publicar na Play Store)."""
    contato = (
        f'<p>Dúvidas ou pedidos sobre seus dados? Escreva para '
        f'<a href="mailto:{_esc(contact_email)}">{_esc(contact_email)}</a>.</p>'
        if contact_email else
        '<p>Para dúvidas ou pedidos sobre seus dados, entre em contato pelo perfil '
        'do Lombada nas redes ou pelo canal informado na loja de aplicativos.</p>'
    )
    data_html = f'<p class="lp-date">Última atualização: {_esc(atualizado_em)}</p>' if atualizado_em else ""
    inner = (
        '<header class="lp-page-head"><span class="label">privacidade</span>'
        f'<h1>Política de Privacidade</h1>{data_html}</header>'
        '<div class="lp-prose">'
        '<p>Esta política explica quais dados o Lombada coleta, como usa e quais '
        'são suas opções. Em resumo: coletamos o mínimo pra o app funcionar, '
        '<strong>não vendemos seus dados</strong> e não exibimos anúncios.</p>'

        '<h2>Dados que coletamos</h2>'
        '<ul>'
        '<li><strong>Sessão anônima:</strong> ao abrir o app, criamos um usuário '
        'anônimo com um cookie de sessão, pra você registrar leituras sem precisar '
        'de conta.</li>'
        '<li><strong>Login com Google (opcional):</strong> se você entrar com o '
        'Google, recebemos seu nome, e-mail e foto de perfil pra identificar sua '
        'conta. Não temos acesso à sua senha.</li>'
        '<li><strong>Conteúdo que você cria:</strong> livros, edições, notas, '
        'críticas, status de leitura, progresso e quem você segue.</li>'
        '<li><strong>Dados técnicos:</strong> registros básicos de acesso '
        '(como endereço IP e tipo de dispositivo) gerados pelo servidor, usados '
        'pra segurança e diagnóstico.</li>'
        '</ul>'

        '<h2>Como usamos</h2>'
        '<ul>'
        '<li>Manter sua estante, seu perfil e o funcionamento social do app '
        '(seguir, feed, críticas públicas).</li>'
        '<li>O que você marca como público (críticas, estante) fica visível na sua '
        'página pública; o que é privado permanece só pra você.</li>'
        '<li>Melhorar o catálogo e a experiência de uso.</li>'
        '</ul>'

        '<h2>Compartilhamento com terceiros</h2>'
        '<p>Usamos serviços de terceiros apenas pra operar o Lombada:</p>'
        '<ul>'
        '<li><strong>Google</strong> — autenticação (login opcional).</li>'
        '<li><strong>Hospedagem e banco de dados</strong> — para rodar o app e '
        'guardar seus registros.</li>'
        '<li><strong>Amazon</strong> — alguns links de compra são de afiliado. '
        'Como participante do Programa de Associados da Amazon, o Lombada é '
        'remunerado pelas compras qualificadas efetuadas — sem custo extra pra '
        'você. A Amazon trata esses acessos conforme a política dela.</li>'
        '</ul>'
        '<p>Não vendemos nem alugamos seus dados pessoais a ninguém.</p>'

        '<h2>Cookies</h2>'
        '<p>Usamos um cookie de sessão essencial pra manter você conectado (anônimo '
        'ou via Google). Sem ele, o app não consegue lembrar da sua estante.</p>'

        '<h2>Seus direitos</h2>'
        '<p>Você pode pedir acesso, correção ou exclusão dos seus dados, incluindo '
        'apagar sua conta e o conteúdo associado. Ao excluir a conta, removemos '
        'seus dados pessoais, salvo o que a lei exigir manter.</p>'

        '<h2>Crianças</h2>'
        '<p>O Lombada não é direcionado a menores de 13 anos e não coleta '
        'intencionalmente dados dessas crianças.</p>'

        '<h2>Alterações</h2>'
        '<p>Podemos atualizar esta política. Mudanças relevantes serão sinalizadas '
        'nesta página, com a data de atualização acima.</p>'

        '<h2>Contato</h2>'
        f'{contato}'
        '</div>'
        '<a class="lp-back" href="/sobre">← voltar pra apresentação</a>'
    )
    og = {"title": "Política de Privacidade — Lombada", "type": "website",
          "description": "Como o Lombada coleta, usa e protege seus dados."}
    return _shell("Política de Privacidade — Lombada", inner, og, app_url, instagram_url,
                  description="Como o Lombada coleta, usa e protege seus dados.")
