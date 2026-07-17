import tempfile
import unittest
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from frontend_v2 import ASSET_CACHE_CONTROL, HTML_CACHE_CONTROL
from preview_v3_kimi import DEFAULT_DIST_DIR, create_preview_v3_kimi_router


class PreviewV3KimiTest(unittest.TestCase):
    def _client(self, dist_dir: Path) -> TestClient:
        app = FastAPI()
        app.include_router(create_preview_v3_kimi_router(dist_dir))
        return TestClient(app)

    def test_build_ausente_retorna_503_sem_afetar_app_legado(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self._client(Path(tmp) / "dist") as client:
                response = client.get("/v3-kimi")

        self.assertEqual(response.status_code, 503)
        self.assertIn("não está disponível", response.text)
        self.assertIn('href="/"', response.text)
        self.assertEqual(response.headers["cache-control"], "no-store")

    def test_serve_index_e_assets_com_cache_adequado(self):
        with tempfile.TemporaryDirectory() as tmp:
            dist = Path(tmp) / "dist"
            assets = dist / "assets"
            assets.mkdir(parents=True)
            (dist / "index.html").write_text("<h1>Preview Kimi</h1>", encoding="utf-8")
            (assets / "index-abc.js").write_text("console.log('ok')", encoding="utf-8")

            with self._client(dist) as client:
                index = client.get("/v3-kimi/")
                asset = client.get("/v3-kimi/assets/index-abc.js")

        self.assertEqual(index.status_code, 200)
        self.assertIn("Preview Kimi", index.text)
        self.assertEqual(index.headers["cache-control"], HTML_CACHE_CONTROL)
        self.assertEqual(asset.status_code, 200)
        self.assertEqual(asset.headers["cache-control"], ASSET_CACHE_CONTROL)

    def test_rota_futura_da_spa_retorna_index(self):
        with tempfile.TemporaryDirectory() as tmp:
            dist = Path(tmp) / "dist"
            dist.mkdir(parents=True)
            (dist / "index.html").write_text("<h1>Fallback SPA</h1>", encoding="utf-8")

            with self._client(dist) as client:
                response = client.get("/v3-kimi/estante/lidos")

        self.assertEqual(response.status_code, 200)
        self.assertIn("Fallback SPA", response.text)

    def test_asset_inexistente_retorna_404(self):
        with tempfile.TemporaryDirectory() as tmp:
            dist = Path(tmp) / "dist"
            dist.mkdir(parents=True)
            (dist / "index.html").write_text("<h1>Preview Kimi</h1>", encoding="utf-8")

            with self._client(dist) as client:
                response = client.get("/v3-kimi/assets/inexistente.js")

        self.assertEqual(response.status_code, 404)

    def test_build_versionado_existe_e_aponta_para_v3_kimi(self):
        """O dist do preview é versionado no repositório, pronto para deploy."""
        index = DEFAULT_DIST_DIR / "index.html"
        self.assertTrue(index.is_file(), "previews/v3-kimi/index.html ausente")
        html = index.read_text(encoding="utf-8")
        self.assertIn('src="/v3-kimi/assets/', html)

        with self._client(DEFAULT_DIST_DIR) as client:
            response = client.get("/v3-kimi")

        self.assertEqual(response.status_code, 200)
        self.assertIn("/v3-kimi/assets/", response.text)


if __name__ == "__main__":
    unittest.main()
