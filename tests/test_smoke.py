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

    def test_profile_bio_special_chars_are_stored_raw_and_escaped_on_render(self):
        bio = "Leio A & B <3"
        r = self.client.get("/api/eu")
        self.assertEqual(r.status_code, 200)
        handle = r.json()["handle"]

        with main.Session(main.engine) as s:
            u = s.exec(main.select(main.Usuario).where(main.Usuario.handle == handle)).first()
            u.google_sub = f"smoke-google-{u.id}"
            s.add(u)
            s.commit()

        r = self.client.patch("/api/eu/perfil", json={"nome": "Leitor Teste", "handle": handle, "bio": bio})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["bio"], bio)

        with main.Session(main.engine) as s:
            u = s.exec(main.select(main.Usuario).where(main.Usuario.handle == handle)).first()
            self.assertEqual(u.bio, bio)
            self.assertNotIn("&amp;", u.bio)
            self.assertNotIn("&lt;", u.bio)

            reader = main.Usuario(handle="bio-reader", nome="Bio Reader", bio=bio)
            s.add(reader)
            s.commit()
            s.refresh(reader)
            obra = main.Obra(ol_work_key="smoke-bio-work", titulo="Livro Bio", autor="Autora Bio")
            s.add(obra)
            s.commit()
            s.refresh(obra)
            edicao = main.Edicao(obra_id=obra.id, ol_edition_key="smoke-bio-edition")
            s.add(edicao)
            s.commit()
            s.refresh(edicao)
            leitura = main.Leitura(edicao_id=edicao.id, usuario_id=reader.id, relato="Crítica pública", publico=True)
            s.add(leitura)
            s.commit()

        r = self.client.get("/api/eu")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["bio"], bio)

        r = self.client.get(f"/api/u/{handle}")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["bio"], bio)

        r = self.client.get("/api/feed/discover")
        self.assertEqual(r.status_code, 200)
        reader = next(item for item in r.json()["readers"] if item["handle"] == "bio-reader")
        self.assertEqual(reader["bio"], bio)

        r = self.client.get(f"/u/{handle}")
        self.assertEqual(r.status_code, 200)
        self.assertIn("Leio A &amp; B &lt;3", r.text)
        self.assertNotIn("&amp;amp;", r.text)

    def test_version_endpoint(self):
        r = self.client.get("/api/version")
        self.assertEqual(r.status_code, 200)

    def test_eu_endpoint_anonymous(self):
        r = self.client.get("/api/eu")
        self.assertEqual(r.status_code, 200)


if __name__ == "__main__":
    unittest.main()
