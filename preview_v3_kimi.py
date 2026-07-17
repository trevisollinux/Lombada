"""Entrega o preview do redesign (Kimi) em /v3-kimi sem alterar / nem /app-v2.

O build estático versionado em `previews/v3-kimi/` foi gerado a partir do
frontend React atual com o patch de redesign aplicado, usando
`VITE_BASE=/v3-kimi/` e `VITE_BASENAME=/v3-kimi`, apontando para a API real.
O patch original fica em `previews/v3-kimi/redesign-lombada.patch`.

Este módulo é descartável: para remover o preview basta apagar este arquivo,
o diretório `previews/v3-kimi/` e a instalação em `app_entry.py`.
"""

from pathlib import Path

from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, Response

from frontend_v2 import ASSET_CACHE_CONTROL, HTML_CACHE_CONTROL, _safe_file

DEFAULT_DIST_DIR = Path(__file__).resolve().parent / "previews" / "v3-kimi"
MISSING_BUILD_HTML = """<!doctype html>
<html lang="pt-BR">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Preview v3 indisponível · Lombada</title>
  </head>
  <body>
    <main>
      <h1>O preview do redesign não está disponível.</h1>
      <p>O aplicativo atual continua disponível normalmente em <a href="/">/</a>.</p>
    </main>
  </body>
</html>
"""


def create_preview_v3_kimi_router(dist_dir: Path = DEFAULT_DIST_DIR) -> APIRouter:
    router = APIRouter(include_in_schema=False)
    index_file = dist_dir / "index.html"

    def serve(relative_path: str = "") -> Response:
        if not index_file.is_file():
            return HTMLResponse(
                MISSING_BUILD_HTML,
                status_code=503,
                headers={"Cache-Control": "no-store"},
            )

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

        # Assets inexistentes devem retornar 404, não o HTML da SPA. Caso
        # contrário o navegador tentaria interpretar HTML como JavaScript/CSS.
        if relative_path.startswith("assets/"):
            raise HTTPException(status_code=404, detail="asset não encontrado")

        # Fallback de SPA para as rotas do React Router.
        return FileResponse(
            index_file,
            media_type="text/html",
            headers={"Cache-Control": HTML_CACHE_CONTROL},
        )

    @router.get("/v3-kimi")
    @router.get("/v3-kimi/")
    def v3_kimi_index() -> Response:
        return serve()

    @router.get("/v3-kimi/{relative_path:path}")
    def v3_kimi_path(relative_path: str) -> Response:
        return serve(relative_path)

    return router


def install_preview_v3_kimi(app: FastAPI, dist_dir: Path = DEFAULT_DIST_DIR) -> None:
    """Instala as rotas uma única vez no app ASGI de produção."""
    if getattr(app.state, "preview_v3_kimi_installed", False):
        return
    app.include_router(create_preview_v3_kimi_router(dist_dir))
    app.state.preview_v3_kimi_installed = True
