"""ASGI entrypoint com correções e módulos opcionais instalados antes do primeiro request."""
import busca as busca_module
import main
import product_analytics as product_analytics_module

from author_search_patch import (
    SearchQuerySanitizerMiddleware,
    buscar_catalogo_local as _buscar_catalogo_local_patch,
    install,
)
from essential_books import (
    install_product_analytics_contract as install_essential_analytics_contract,
    install_public_profile_patch,
    router as essential_books_router,
)
from feature_flags import router as feature_flags_router
from frontend_v2 import install_frontend_v2
from literary_reactions import (
    install_product_analytics_contract as install_reaction_analytics_contract,
    router as literary_reactions_router,
)
from period_recaps import (
    install_product_analytics_contract as install_recap_analytics_contract,
    router as period_recaps_router,
)
from product_analytics import router as product_analytics_router
from retention_dashboard import router as retention_dashboard_router


install()
install_essential_analytics_contract(product_analytics_module)
install_recap_analytics_contract(product_analytics_module)
install_reaction_analytics_contract(product_analytics_module)
install_public_profile_patch(main)


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

install_frontend_v2(app)

if not getattr(app.state, "feature_flags_router_installed", False):
    app.include_router(feature_flags_router)
    app.state.feature_flags_router_installed = True

if not getattr(app.state, "product_analytics_router_installed", False):
    app.include_router(product_analytics_router)
    app.state.product_analytics_router_installed = True

if not getattr(app.state, "retention_dashboard_router_installed", False):
    app.include_router(retention_dashboard_router)
    app.state.retention_dashboard_router_installed = True

if not getattr(app.state, "essential_books_router_installed", False):
    app.include_router(essential_books_router)
    app.state.essential_books_router_installed = True

if not getattr(app.state, "period_recaps_router_installed", False):
    app.include_router(period_recaps_router)
    app.state.period_recaps_router_installed = True

if not getattr(app.state, "literary_reactions_router_installed", False):
    app.include_router(literary_reactions_router)
    app.state.literary_reactions_router_installed = True

if not getattr(app.state, "author_search_patch_installed", False):
    app.add_middleware(SearchQuerySanitizerMiddleware)
    app.state.author_search_patch_installed = True
