import tempfile
import unittest
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from frontend_v2 import (
    ASSET_CACHE_CONTROL,
    HTML_CACHE_CONTROL,
    _safe_file,
    create_frontend_v2_router,
)


class FrontendV2Test(unittest.TestCase):
    def _client(self, dist_dir: Path) -> TestClient:
        app = FastAPI()
        app.include_router(create_frontend_v2_router(dist_dir))
        return TestClient(app)

    def test_build_ausente_retorna_503_sem_afetar_app_legado(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self._client(Path(tmp) / "dist") as client:
                response = client.get("/app-v2")

        self.assertEqual(response.status_code, 503)
        self.assertIn("ainda não foi compilado", response.text)
        self.assertIn('href="/"', response.text)
        self.assertEqual(response.headers["cache-control"], "no-store")

    def test_serve_index_e_assets_com_cache_adequado(self):
        with tempfile.TemporaryDirectory() as tmp:
            dist = Path(tmp) / "dist"
            assets = dist / "assets"
            assets.mkdir(parents=True)
            (dist / "index.html").write_text("<h1>App React</h1>", encoding="utf-8")
            (assets / "index-abc.js").write_text("console.log('ok')", encoding="utf-8")

            with self._client(dist) as client:
                index = client.get("/app-v2/")
                asset = client.get("/app-v2/assets/index-abc.js")

        self.assertEqual(index.status_code, 200)
        self.assertIn("App React", index.text)
        self.assertEqual(index.headers["cache-control"], HTML_CACHE_CONTROL)
        self.assertEqual(asset.status_code, 200)
        self.assertIn("console.log", asset.text)
        self.assertEqual(asset.headers["cache-control"], ASSET_CACHE_CONTROL)

    def test_rota_futura_da_spa_retorna_index(self):
        with tempfile.TemporaryDirectory() as tmp:
            dist = Path(tmp) / "dist"
            dist.mkdir(parents=True)
            (dist / "index.html").write_text("<h1>Fallback SPA</h1>", encoding="utf-8")

            with self._client(dist) as client:
                response = client.get("/app-v2/estante/lidos")

        self.assertEqual(response.status_code, 200)
        self.assertIn("Fallback SPA", response.text)

    def test_asset_inexistente_retorna_404(self):
        with tempfile.TemporaryDirectory() as tmp:
            dist = Path(tmp) / "dist"
            dist.mkdir(parents=True)
            (dist / "index.html").write_text("<h1>App React</h1>", encoding="utf-8")

            with self._client(dist) as client:
                response = client.get("/app-v2/assets/inexistente.js")

        self.assertEqual(response.status_code, 404)

    def test_v3_kimi_redireciona_para_app_v2(self):
        with tempfile.TemporaryDirectory() as tmp:
            dist = Path(tmp) / "dist"
            dist.mkdir(parents=True)
            (dist / "index.html").write_text("<h1>App React</h1>", encoding="utf-8")

            with self._client(dist) as client:
                raiz = client.get("/v3-kimi", follow_redirects=False)
                subpagina = client.get("/v3-kimi/estante", follow_redirects=False)
                asset = client.get(
                    "/v3-kimi/assets/index-abc.js", follow_redirects=False
                )

        self.assertEqual(raiz.status_code, 308)
        self.assertEqual(raiz.headers["location"], "/app-v2/")
        self.assertEqual(subpagina.status_code, 308)
        self.assertEqual(subpagina.headers["location"], "/app-v2/estante")
        self.assertEqual(asset.status_code, 308)
        self.assertEqual(asset.headers["location"], "/app-v2/assets/index-abc.js")

    def test_safe_file_bloqueia_path_traversal(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dist = root / "dist"
            dist.mkdir()
            outside = root / "segredo.txt"
            outside.write_text("segredo", encoding="utf-8")

            self.assertIsNone(_safe_file(dist, "../segredo.txt"))


if __name__ == "__main__":
    unittest.main()
