import re
import tempfile
import unittest
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.testclient import TestClient

from frontend_app import (
    ASSET_CACHE_CONTROL,
    HTML_CACHE_CONTROL,
    SPA_ROUTES,
    _safe_file,
    create_frontend_router,
)


class FrontendAppTest(unittest.TestCase):
    def _client(self, dist_dir: Path, **kwargs) -> TestClient:
        app = FastAPI()
        app.include_router(create_frontend_router(dist_dir, **kwargs))
        return TestClient(app)

    def _dist_com_build(self, tmp: str) -> Path:
        dist = Path(tmp) / "dist"
        assets = dist / "assets"
        assets.mkdir(parents=True)
        (dist / "index.html").write_text("<h1>App React</h1>", encoding="utf-8")
        (assets / "index-abc.js").write_text("console.log('ok')", encoding="utf-8")
        return dist

    def test_raiz_serve_o_app_react(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self._client(self._dist_com_build(tmp)) as client:
                index = client.get("/")
                asset = client.get("/assets/index-abc.js")

        self.assertEqual(index.status_code, 200)
        self.assertIn("App React", index.text)
        self.assertEqual(index.headers["cache-control"], HTML_CACHE_CONTROL)
        self.assertEqual(asset.status_code, 200)
        self.assertIn("console.log", asset.text)
        self.assertEqual(asset.headers["cache-control"], ASSET_CACHE_CONTROL)

    def test_rota_da_spa_retorna_index(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self._client(self._dist_com_build(tmp)) as client:
                response = client.get("/estante/lidos")

        self.assertEqual(response.status_code, 200)
        self.assertIn("App React", response.text)

    def test_caminhos_de_api_e_assets_inexistentes_retornam_404(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self._client(self._dist_com_build(tmp)) as client:
                asset = client.get("/assets/inexistente.js")
                api = client.get("/api/rota-que-nao-existe")
                static = client.get("/static/sumiu.css")

        # Nunca devolver o HTML da SPA aqui: o navegador tentaria interpretar
        # HTML como JavaScript, CSS ou JSON.
        self.assertEqual(asset.status_code, 404)
        self.assertEqual(api.status_code, 404)
        self.assertEqual(static.status_code, 404)

    def test_build_ausente_cai_para_o_app_legado_na_raiz(self):
        def legado() -> HTMLResponse:
            return HTMLResponse("<h1>App legado</h1>")

        with tempfile.TemporaryDirectory() as tmp:
            with self._client(Path(tmp) / "dist", legacy_index=legado) as client:
                response = client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn("App legado", response.text)

    def test_build_ausente_sem_legado_retorna_503_apontando_para_app_v1(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self._client(Path(tmp) / "dist") as client:
                response = client.get("/")

        self.assertEqual(response.status_code, 503)
        self.assertIn("ainda não foi compilado", response.text)
        self.assertIn('href="/app-v1"', response.text)
        self.assertEqual(response.headers["cache-control"], "no-store")

    def test_service_worker_vem_do_build_e_nunca_e_cacheado(self):
        with tempfile.TemporaryDirectory() as tmp:
            dist = self._dist_com_build(tmp)
            (dist / "sw.js").write_text("/* worker react */", encoding="utf-8")

            with self._client(dist) as client:
                response = client.get("/sw.js")

        self.assertEqual(response.status_code, 200)
        self.assertIn("worker react", response.text)
        self.assertIn("no-store", response.headers["cache-control"])

    def test_service_worker_cai_para_o_legado_quando_nao_ha_build(self):
        with tempfile.TemporaryDirectory() as tmp:
            legado = Path(tmp) / "sw.js"
            legado.write_text("/* worker legado */", encoding="utf-8")

            with self._client(Path(tmp) / "dist", legacy_sw_file=legado) as client:
                response = client.get("/sw.js")

        self.assertEqual(response.status_code, 200)
        self.assertIn("worker legado", response.text)

    def test_rotas_antigas_redirecionam_para_a_raiz(self):
        caminhos = {
            "/app-v2": "/",
            "/app-v2/estante": "/estante",
            "/app-v2/assets/index-abc.js": "/assets/index-abc.js",
            "/v3-kimi": "/",
            "/v3-kimi/estante": "/estante",
            "/index.html": "/",
        }

        with tempfile.TemporaryDirectory() as tmp:
            with self._client(self._dist_com_build(tmp)) as client:
                respostas = {
                    caminho: client.get(caminho, follow_redirects=False)
                    for caminho in caminhos
                }

        for caminho, destino in caminhos.items():
            with self.subTest(caminho=caminho):
                self.assertEqual(respostas[caminho].status_code, 308)
                self.assertEqual(respostas[caminho].headers["location"], destino)

    def test_safe_file_bloqueia_path_traversal(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dist = root / "dist"
            dist.mkdir()
            outside = root / "segredo.txt"
            outside.write_text("segredo", encoding="utf-8")

            self.assertIsNone(_safe_file(dist, "../segredo.txt"))


class SpaRouteContractTest(unittest.TestCase):
    """SPA_ROUTES precisa acompanhar o React Router e o service worker.

    Uma rota nova em App.tsx que ficasse de fora daria 404 do servidor no
    acesso direto e no refresh — quebra que só aparece fora da navegação
    interna do app.
    """

    def _frontend(self, relative: str) -> str:
        root = Path(__file__).resolve().parents[1] / "frontend"
        return (root / relative).read_text(encoding="utf-8")

    def test_rotas_do_react_router_estao_cobertas_pelo_backend(self):
        app_tsx = self._frontend("src/App.tsx")
        declaradas = {
            path.split("/", 1)[0]
            for path in re.findall(r'<Route path="([^"*:]+)"', app_tsx)
        }

        self.assertTrue(declaradas, "App.tsx deve declarar rotas com path=")
        self.assertLessEqual(declaradas, set(SPA_ROUTES))

    def test_service_worker_usa_a_mesma_lista_de_rotas(self):
        worker = self._frontend("public/sw.js")
        match = re.search(r"const APP_ROUTES = \[(.*?)\]", worker, flags=re.DOTALL)

        self.assertIsNotNone(match, "sw.js deve declarar APP_ROUTES")
        self.assertEqual(
            set(re.findall(r"'([^']+)'", match.group(1))),
            set(SPA_ROUTES),
        )


class FrontendRouteOrderTest(unittest.TestCase):
    def test_entrypoint_instala_o_frontend_por_ultimo(self):
        source = (Path(__file__).resolve().parents[1] / "app_entry.py").read_text(
            encoding="utf-8"
        )
        instalacao = source.index("install_frontend(app")
        # O catch-all da SPA engoliria qualquer rota registrada depois dele.
        for router in (
            "app.include_router(feature_flags_router)",
            "app.include_router(product_analytics_router)",
            "app.include_router(retention_dashboard_router)",
            "app.include_router(essential_books_router)",
            "app.include_router(period_recaps_router)",
            "app.include_router(literary_reactions_router)",
        ):
            with self.subTest(router=router):
                self.assertLess(source.index(router), instalacao)


if __name__ == "__main__":
    unittest.main()
