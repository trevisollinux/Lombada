"""Regressões da busca por autor sem depender das APIs externas."""
import atexit
import os
import tempfile
import unittest

_DB_FD, _DB_PATH = tempfile.mkstemp(suffix=".db")
os.close(_DB_FD)
os.environ["DATABASE_URL"] = f"sqlite:///{_DB_PATH}"
os.environ.setdefault("COOKIE_SECURE", "false")
os.environ.setdefault("SECRET_KEY", "author-search-test-secret")
atexit.register(lambda: os.path.exists(_DB_PATH) and os.remove(_DB_PATH))

from fastapi.testclient import TestClient  # noqa: E402

import app_entry  # noqa: E402
import author_search_patch  # noqa: E402
import main  # noqa: E402
from author_search_patch import sanitize_search_query  # noqa: E402

# A produção usa PostgreSQL e suporta o fold completo. O SQLite da suíte possui
# um limite baixo para expressões profundamente aninhadas e estoura o parser com
# as 51 chamadas de replace do mapa completo. Mantemos aqui o subconjunto que
# cobre português/espanhol e os casos de regressão, sem mudar a busca de produção.
if main.engine.dialect.name == "sqlite":
    author_search_patch._SQL_ACCENT_REPLACEMENTS = (
        ("á", "a"), ("à", "a"), ("ã", "a"), ("â", "a"), ("ä", "a"),
        ("é", "e"), ("è", "e"), ("ê", "e"), ("ë", "e"),
        ("í", "i"), ("ì", "i"), ("î", "i"), ("ï", "i"),
        ("ó", "o"), ("ò", "o"), ("õ", "o"), ("ô", "o"), ("ö", "o"),
        ("ú", "u"), ("ù", "u"), ("û", "u"), ("ü", "u"),
        ("ç", "c"), ("ñ", "n"), ("ý", "y"), ("ÿ", "y"),
        ("Á", "a"), ("É", "e"), ("Í", "i"), ("Ó", "o"),
        ("Ú", "u"), ("Ç", "c"), ("Ñ", "n"),
    )


class AuthorSearchPatchTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._ctx = TestClient(app_entry.app)
        cls.client = cls._ctx.__enter__()
        with main.Session(main.engine) as s:
            fixtures = [
                ("reg-author-dost", "Caderno do Subsolo", "Fiódor Dostoiévski"),
                ("reg-author-marquez", "Crônica de Macondo", "Gabriel García Márquez"),
                ("reg-author-erico", "Caminhos do Sul", "Érico Veríssimo"),
            ]
            for work_key, titulo, autor in fixtures:
                obra = main.Obra(ol_work_key=work_key, titulo=titulo, autor=autor)
                s.add(obra)
                s.commit()
                s.refresh(obra)
                s.add(main.Edicao(obra_id=obra.id, editora="Editora Regressão", idioma="Português"))
                s.commit()

            for i in range(12):
                obra = main.Obra(
                    ol_work_key=f"reg-author-many-{i}",
                    titulo=f"Obra Numerosa {i}",
                    autor="Autór Abundante",
                )
                s.add(obra)
                s.commit()
                s.refresh(obra)
                s.add(main.Edicao(obra_id=obra.id, editora="Editora Regressão", idioma="Português"))
                s.commit()

    @classmethod
    def tearDownClass(cls):
        cls._ctx.__exit__(None, None, None)

    def _titulos(self, consulta):
        with main.Session(main.engine) as s:
            return {d["titulo"] for d in main._buscar_catalogo_local(consulta, s)}

    def test_dostoievski_sem_acento_encontra_dostoievski_acentuado(self):
        self.assertIn("Caderno do Subsolo", self._titulos("Dostoievski"))

    def test_outros_autores_acentuados_tambem_funcionam(self):
        self.assertIn("Crônica de Macondo", self._titulos("Garcia Marquez"))
        self.assertIn("Caminhos do Sul", self._titulos("Erico Verissimo"))

    def test_busca_por_autor_nao_e_cortada_em_dez_obras(self):
        with main.Session(main.engine) as s:
            docs = main._buscar_catalogo_local("Autor Abundante", s)
        encontrados = [
            d for d in docs
            if main._normalizar_busca(d.get("autor")) == "autor abundante"
        ]
        self.assertGreaterEqual(len(encontrados), 12)

    def test_limpa_metadados_colados_no_nome_do_autor(self):
        self.assertEqual(
            sanitize_search_query("Fiódor Dostoiévski Autor: Fiódor Dostoiévski Tradutor: Fulano"),
            "Fiódor Dostoiévski",
        )


if __name__ == "__main__":
    unittest.main()
