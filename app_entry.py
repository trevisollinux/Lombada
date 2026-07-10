"""ASGI entrypoint com correções de busca instaladas antes do primeiro request."""
import main

from author_search_patch import SearchQuerySanitizerMiddleware, install

install()
app = main.app

if not getattr(app.state, "author_search_patch_installed", False):
    app.add_middleware(SearchQuerySanitizerMiddleware)
    app.state.author_search_patch_installed = True
