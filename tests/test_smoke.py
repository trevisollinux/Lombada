"""
Smoke tests: garantem que a aplicação importa e as rotas principais
respondem sem erro 500, antes do deploy. Não substitui testes de
unidade -- existe pra pegar erros de import/sintaxe/rota quebrada (foi
assim que um bug de sintaxe só-Python-3.12 passou despercebido até o
deploy quebrar em produção).
"""
import os
import tempfile
import unittest

_DB_FD, _DB_PATH = tempfile.mkstemp(suffix=".db")
os.close(_DB_FD)
os.environ["DATABASE_URL"] = f"sqlite:///{_DB_PATH}"
os.environ.setdefault("COOKIE_SECURE", "false")
os.environ.setdefault("SECRET_KEY", "smoke-test-secret")

from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402


class SmokeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._ctx = TestClient(main.app)
        cls.client = cls._ctx.__enter__()  # roda o lifespan (create_all etc.)

    @classmethod
    def tearDownClass(cls):
        cls._ctx.__exit__(None, None, None)
        try:
            os.remove(_DB_PATH)
        except OSError:
            pass

    def test_home_page_loads(self):
        r = self.client.get("/")
        self.assertEqual(r.status_code, 200)
        self.assertIn("Lombada", r.text)

    def test_search_validates_query(self):
        r = self.client.get("/api/buscar", params={"q": "x"})
        self.assertEqual(r.status_code, 422)

    def test_public_profile_not_found(self):
        r = self.client.get("/u/handle-que-nao-existe-123456")
        self.assertEqual(r.status_code, 404)

    def test_version_endpoint(self):
        r = self.client.get("/api/version")
        self.assertEqual(r.status_code, 200)

    def test_eu_endpoint_anonymous(self):
        r = self.client.get("/api/eu")
        self.assertEqual(r.status_code, 200)


if __name__ == "__main__":
    unittest.main()
