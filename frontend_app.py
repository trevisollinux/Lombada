"""Entrega o frontend React na raiz `/` e mantém o app legado em `/app-v1`.

Histórico das rotas: o redesign estreou como preview em `/v3-kimi`, foi
promovido a `/app-v2` e agora assume `/`. Os dois caminhos antigos viram
redirecionamento permanente para a raiz, preservando o subcaminho.

O app legado continua servido por `main.py` em `/app-v1`, como rota de escape
para os fluxos que ainda não têm paridade no React.

Este roteador precisa ser instalado **por último** no app ASGI: o catch-all de
SPA captura qualquer caminho que nenhuma rota anterior tenha reivindicado.
"""

from collections.abc import Callable
from pathlib import Path

from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response


AQUI = Path(__file__).resolve().parent
DEFAULT_DIST_DIR = AQUI / "frontend" / "dist"
LEGACY_SW_FILE = AQUI / "sw.js"
HTML_CACHE_CONTROL = "no-cache, max-age=0, must-revalidate"
ASSET_CACHE_CONTROL = "public, max-age=31536000, immutable"
WORKER_CACHE_CONTROL = "no-store, no-cache, must-revalidate, max-age=0"

# Primeiro segmento das rotas do React Router (espelha frontend/src/App.tsx).
# O catch-all responde só por elas: sem essa lista, qualquer caminho
# inexistente — /api/xxx, /blog/yyy, um asset com hash errado — voltaria como
# o HTML do app com status 200, escondendo 404 reais do servidor e fazendo o
# navegador tentar interpretar HTML como JSON, JavaScript ou CSS.
SPA_ROUTES = ("explorar", "obra", "feed", "estante", "diario", "memorias", "perfil")

MISSING_BUILD_HTML = """<!doctype html>
<html lang="pt-BR">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Lombada indisponível</title>
  </head>
  <body>
    <main>
      <h1>O frontend React ainda não foi compilado.</h1>
      <p>O aplicativo anterior continua disponível em <a href="/app-v1">/app-v1</a>.</p>
    </main>
  </body>
</html>
"""


def _is_spa_route(relative_path: str) -> bool:
    """A raiz e os caminhos sob uma rota declarada no React Router."""
    if not relative_path:
        return True
    return relative_path.split("/", 1)[0] in SPA_ROUTES


def _safe_file(dist_dir: Path, relative_path: str) -> Path | None:
    """Resolve um arquivo dentro do dist e bloqueia path traversal."""
    if not relative_path:
        return None

    root = dist_dir.resolve()
    candidate = (root / relative_path).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return None
    return candidate if candidate.is_file() else None


def create_frontend_router(
    dist_dir: Path = DEFAULT_DIST_DIR,
    legacy_index: Callable[[], Response] | None = None,
    legacy_sw_file: Path | None = LEGACY_SW_FILE,
) -> APIRouter:
    """Roteador da SPA na raiz.

    `legacy_index` é o renderizador do app legado. Quando o build do React não
    existe — ambiente Python sem Node, build quebrado no deploy — a raiz cai
    para ele em vez de derrubar o site.
    """
    router = APIRouter(include_in_schema=False)
    index_file = dist_dir / "index.html"

    def sem_build(relative_path: str) -> Response:
        if not relative_path and legacy_index is not None:
            return legacy_index()
        return HTMLResponse(
            MISSING_BUILD_HTML,
            status_code=503,
            headers={"Cache-Control": "no-store"},
        )

    def serve(relative_path: str = "") -> Response:
        requested_file = _safe_file(dist_dir, relative_path)
        if requested_file:
            cache_control = (
                ASSET_CACHE_CONTROL
                if relative_path.startswith("assets/")
                else HTML_CACHE_CONTROL
            )
            return FileResponse(
                requested_file,
                headers={"Cache-Control": cache_control},
            )

        if not _is_spa_route(relative_path):
            raise HTTPException(status_code=404, detail="não encontrado")

        if not index_file.is_file():
            return sem_build(relative_path)

        # Fallback de SPA para as rotas do React Router.
        return FileResponse(
            index_file,
            media_type="text/html",
            headers={"Cache-Control": HTML_CACHE_CONTROL},
        )

    @router.get("/")
    def spa_index() -> Response:
        return serve()

    @router.get("/index.html")
    def spa_index_html() -> Response:
        # A SPA legada cacheava /index.html no service worker; manter o caminho
        # vivo evita 404 para quem volta com o worker antigo instalado.
        return RedirectResponse("/", status_code=308)

    @router.get("/sw.js")
    def service_worker() -> Response:
        """Escopo `/`: o worker do build do React, com o legado como reserva.

        Sem o dist quem responde a raiz é o app legado — e aí o worker correto
        é justamente o antigo.
        """
        worker = dist_dir / "sw.js"
        if not worker.is_file():
            if legacy_sw_file is None or not legacy_sw_file.is_file():
                raise HTTPException(status_code=404, detail="worker indisponível")
            worker = legacy_sw_file
        return FileResponse(
            worker,
            media_type="application/javascript",
            headers={"Cache-Control": WORKER_CACHE_CONTROL},
        )

    # /v3-kimi foi o preview do redesign e /app-v2 a etapa intermediária. Os
    # dois viram redirecionamento permanente para a raiz, preservando o
    # subcaminho, para não quebrar links antigos nem PWAs já instalados.
    @router.get("/app-v2")
    @router.get("/app-v2/")
    def app_v2_index_redirect() -> Response:
        return RedirectResponse("/", status_code=308)

    @router.get("/app-v2/{relative_path:path}")
    def app_v2_path_redirect(relative_path: str) -> Response:
        return RedirectResponse(f"/{relative_path}", status_code=308)

    @router.get("/v3-kimi")
    @router.get("/v3-kimi/")
    def v3_kimi_index_redirect() -> Response:
        return RedirectResponse("/", status_code=308)

    @router.get("/v3-kimi/{relative_path:path}")
    def v3_kimi_path_redirect(relative_path: str) -> Response:
        return RedirectResponse(f"/{relative_path}", status_code=308)

    # Catch-all: precisa ser a última rota registrada no app inteiro.
    @router.get("/{relative_path:path}")
    def spa_path(relative_path: str) -> Response:
        return serve(relative_path)

    return router


def install_frontend(
    app: FastAPI,
    dist_dir: Path = DEFAULT_DIST_DIR,
    legacy_index: Callable[[], Response] | None = None,
    legacy_sw_file: Path | None = LEGACY_SW_FILE,
) -> None:
    """Instala as rotas uma única vez, sempre depois de todas as outras."""
    if getattr(app.state, "frontend_installed", False):
        return
    app.include_router(create_frontend_router(dist_dir, legacy_index, legacy_sw_file))
    app.state.frontend_installed = True
