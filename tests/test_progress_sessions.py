"""Campos de sessão do diário e resumo de progresso (Lombada 2.0, L2/EPIC 2).

Cobre: flag desligada mantém o comportamento atual (endpoint 404, diário
igual); flag ligada devolve o resumo; origem é sanitizada; paginas_delta é
calculado entre sessões e nulo quando não dá pra estimar.
"""
import os
import tempfile
import unittest
from unittest.mock import patch

_DB_FD, _DB_PATH = tempfile.mkstemp(suffix=".db")
os.close(_DB_FD)
os.environ["DATABASE_URL"] = f"sqlite:///{_DB_PATH}"
os.environ.setdefault("COOKIE_SECURE", "false")
os.environ.setdefault("SECRET_KEY", "progress-test-secret")

from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402


def _criar_leitura(client, titulo="Livro Progresso", paginas=200):
    r = client.post("/api/prateleira", json={
        "work_key": f"progresso-{titulo.lower().replace(' ', '-')}",
        "titulo": titulo, "autor": "Autora Teste", "status": "Lendo",
        "publico": False, "spoiler": False, "relato": "",
        "isbn": "", "editora": "", "idioma": "", "data": "",
        "paginas": paginas,
    })
    assert r.status_code == 200, r.text
    r = client.get("/api/prateleira")
    return next(l for l in r.json() if l["titulo"] == titulo)


class ProgressSessionsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._ctx = TestClient(main.app)
        cls.client = cls._ctx.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls._ctx.__exit__(None, None, None)
        try:
            os.remove(_DB_PATH)
        except OSError:
            pass

    def test_resumo_404_com_flag_desligada(self):
        leitura = _criar_leitura(self.client, "Flag Desligada")
        r = self.client.get(f"/api/leitura/{leitura['leitura_id']}/progresso")
        self.assertEqual(r.status_code, 404)

    def test_diario_continua_igual_com_flag_desligada(self):
        leitura = _criar_leitura(self.client, "Diario Intacto")
        r = self.client.post(f"/api/leitura/{leitura['leitura_id']}/diario",
                             json={"progresso_tipo": "pagina", "pagina": 10})
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["origem"], "diario")
        self.assertIsNone(body["paginas_delta"])  # primeira sessão não tem anterior

    def test_origem_li_mais_e_delta_entre_sessoes(self):
        leitura = _criar_leitura(self.client, "Delta Sessoes")
        lid = leitura["leitura_id"]
        self.client.post(f"/api/leitura/{lid}/diario",
                         json={"progresso_tipo": "pagina", "pagina": 40})
        r = self.client.post(f"/api/leitura/{lid}/diario",
                             json={"progresso_tipo": "pagina", "pagina": 63, "origem": "li_mais"})
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["origem"], "li_mais")
        self.assertEqual(body["paginas_delta"], 23)

    def test_origem_invalida_vira_diario(self):
        leitura = _criar_leitura(self.client, "Origem Suja")
        r = self.client.post(f"/api/leitura/{leitura['leitura_id']}/diario",
                             json={"progresso_tipo": "pagina", "pagina": 5,
                                   "origem": "<script>alert(1)</script>"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["origem"], "diario")

    def test_delta_nulo_quando_nao_da_pra_estimar(self):
        leitura = _criar_leitura(self.client, "Sem Estimativa")
        lid = leitura["leitura_id"]
        self.client.post(f"/api/leitura/{lid}/diario",
                         json={"progresso_tipo": "livre", "nota": "só uma anotação"})
        r = self.client.post(f"/api/leitura/{lid}/diario",
                             json={"progresso_tipo": "livre", "nota": "outra anotação"})
        self.assertEqual(r.status_code, 200)
        self.assertIsNone(r.json()["paginas_delta"])

    def test_resumo_com_flag_ligada(self):
        leitura = _criar_leitura(self.client, "Resumo Completo", paginas=300)
        lid = leitura["leitura_id"]
        self.client.post(f"/api/leitura/{lid}/diario",
                         json={"progresso_tipo": "pagina", "pagina": 30})
        self.client.post(f"/api/leitura/{lid}/diario",
                         json={"progresso_tipo": "pagina", "pagina": 75, "origem": "li_mais"})
        with patch.dict(os.environ, {"FF_PROGRESS_SESSIONS": "1"}):
            r = self.client.get(f"/api/leitura/{lid}/progresso")
        self.assertEqual(r.status_code, 200)
        d = r.json()
        self.assertEqual(d["paginas_total"], 300)
        self.assertEqual(d["pagina_atual"], 75)
        self.assertEqual(d["porcentagem"], 25)
        self.assertEqual(d["paginas_restantes"], 225)
        self.assertEqual(d["sessoes"], 2)
        self.assertEqual(d["delta_ultima"], 45)
        self.assertEqual(d["paginas_7d"], 45)
        self.assertIsNotNone(d["previsao_dias"])
        self.assertIsNotNone(d["ultima_sessao_em"])

    def test_resumo_leitura_de_outro_usuario_nao_vaza(self):
        leitura = _criar_leitura(self.client, "Privacidade")
        with patch.dict(os.environ, {"FF_PROGRESS_SESSIONS": "1"}):
            outro = TestClient(main.app)  # sessão anônima nova = outro usuário
            with outro:
                r = outro.get(f"/api/leitura/{leitura['leitura_id']}/progresso")
        self.assertEqual(r.status_code, 404)

    def test_resumo_sem_entradas(self):
        leitura = _criar_leitura(self.client, "Sem Sessoes")
        with patch.dict(os.environ, {"FF_PROGRESS_SESSIONS": "1"}):
            r = self.client.get(f"/api/leitura/{leitura['leitura_id']}/progresso")
        self.assertEqual(r.status_code, 200)
        d = r.json()
        self.assertEqual(d["sessoes"], 0)
        self.assertIsNone(d["pagina_atual"])
        self.assertIsNone(d["ultima_sessao_em"])


if __name__ == "__main__":
    unittest.main()
