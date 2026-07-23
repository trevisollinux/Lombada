"""Entrega o frontend React em /app-v2 sem alterar o aplicativo legado em /.

O redesign v3 foi promovido a frontend/src (o preview /v3-kimi separado deixou
de existir), então /app-v2 já serve o redesign. As rotas /v3-kimi ficam como
redirecionamento permanente para /app-v2 para não quebrar links antigos."""

from pathlib import Path

from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response


DEFAULT_DIST_DIR = Path(__file__).resolve().parent / "frontend" / "dist"
HTML_CACHE_CONTROL = "no-cache, max-age=0, must-revalidate"
ASSET_CACHE_CONTROL = "public, max-age=31536000, immutable"
MISSING_BUILD_HTML = """<!doctype html>
<html lang="pt-BR">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>App v2 indisponível · Lombada</title>
  </head>
  <body>
    <main>
      <h1>O frontend React ainda não foi compilado.</h1>
      <p>O aplicativo atual continua disponível normalmente em <a href="/">/</a>.</p>
    </main>
  </body>
</html>
"""


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


def create_frontend_v2_router(dist_dir: Path = DEFAULT_DIST_DIR) -> APIRouter:
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

        # Fallback de SPA para rotas futuras do React Router.
        return FileResponse(
            index_file,
            media_type="text/html",
            headers={"Cache-Control": HTML_CACHE_CONTROL},
        )

    @router.get("/app-v2")
    @router.get("/app-v2/")
    def app_v2_index() -> Response:
        return serve()

    @router.get("/app-v2/{relative_path:path}")
    def app_v2_path(relative_path: str) -> Response:
        return serve(relative_path)

    # /v3-kimi era o preview do redesign, hoje promovido a /app-v2. Mantém os
    # links antigos vivos com redirect permanente, preservando o subcaminho.
    @router.get("/v3-kimi")
    @router.get("/v3-kimi/")
    def v3_kimi_index_redirect() -> Response:
        return RedirectResponse("/app-v2/", status_code=308)

    @router.get("/v3-kimi/{relative_path:path}")
    def v3_kimi_path_redirect(relative_path: str) -> Response:
        return RedirectResponse(f"/app-v2/{relative_path}", status_code=308)

    return router


def install_frontend_v2(app: FastAPI, dist_dir: Path = DEFAULT_DIST_DIR) -> None:
    """Instala as rotas uma única vez no app ASGI de produção."""
    if getattr(app.state, "frontend_v2_installed", False):
        return
    app.include_router(create_frontend_v2_router(dist_dir))
    app.state.frontend_v2_installed = True
