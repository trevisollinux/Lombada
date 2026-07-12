"""ASGI entrypoint com correções e módulos opcionais instalados antes do primeiro request."""
import busca as busca_module
import main

from author_search_patch import (
    SearchQuerySanitizerMiddleware,
    buscar_catalogo_local as _buscar_catalogo_local_patch,
    install,
)
from feature_flags import router as feature_flags_router
from product_analytics import router as product_analytics_router
from retention_dashboard import router as retention_dashboard_router


install()


def _buscar_catalogo_local_estrito(
    q,
    s,
    editora="",
    genero="",
    literatura=None,
):
    """Mantém gênero como filtro estrito, inclusive para obras sem metadado.

    A busca-base marca `_genero_match` apenas quando o gênero foi confirmado.
    Quando o usuário escolhe um estilo, resultados sem gênero catalogado não
    devem aparecer como se fossem compatíveis.
    """
    docs = _buscar_catalogo_local_patch(
        q,
        s,
        editora=editora,
        genero=genero,
        literatura=literatura,
    )
    if genero:
        return [doc for doc in docs if doc.get("_genero_match")]
    return docs


main._buscar_catalogo_local = _buscar_catalogo_local_estrito
busca_module._CACHE_SCHEMA_VERSION = max(
    getattr(busca_module, "_CACHE_SCHEMA_VERSION", 0),
    4,
)
app = main.app

if not getattr(app.state, "feature_flags_router_installed", False):
    app.include_router(feature_flags_router)
    app.state.feature_flags_router_installed = True

if not getattr(app.state, "product_analytics_router_installed", False):
    app.include_router(product_analytics_router)
    app.state.product_analytics_router_installed = True

if not getattr(app.state, "retention_dashboard_router_installed", False):
    app.include_router(retention_dashboard_router)
    app.state.retention_dashboard_router_installed = True

if not getattr(app.state, "author_search_patch_installed", False):
    app.add_middleware(SearchQuerySanitizerMiddleware)
    app.state.author_search_patch_installed = True
