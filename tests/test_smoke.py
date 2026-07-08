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

import auth  # noqa: E402
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

    def test_healthz_responde(self):
        r = self.client.get("/healthz")
        self.assertEqual(r.status_code, 200)

    def test_api_buscar_crime_nao_quebra(self):
        r = self.client.get("/api/buscar", params={"q": "crime"})
        self.assertEqual(r.status_code, 200)
        self.assertIsInstance(r.json(), list)

    def test_busca_catalogo_local_retorna_lista(self):
        with main.Session(main.engine) as s:
            docs = main._buscar_catalogo_local("crime", s)
        self.assertIsInstance(docs, list)

    def test_home_page_loads(self):
        r = self.client.get("/")
        self.assertEqual(r.status_code, 200)
        self.assertIn("Lombada", r.text)

    def test_landing_page_loads(self):
        r = self.client.get("/sobre")
        self.assertEqual(r.status_code, 200)
        self.assertIn("Lombada", r.text)
        self.assertIn("abrir o app", r.text)
        # sem env vars de apoio/Play, os botões correspondentes não aparecem
        self.assertNotIn("apoiar ☕", r.text)
        self.assertNotIn("instalar no Android", r.text)

    def test_quem_somos_page_loads(self):
        r = self.client.get("/quem-somos")
        self.assertEqual(r.status_code, 200)
        self.assertIn("projeto independente", r.text)

    def test_privacidade_page_loads(self):
        r = self.client.get("/privacidade")
        self.assertEqual(r.status_code, 200)
        self.assertIn("Política de Privacidade", r.text)

    def test_manifest_tem_icones_png(self):
        r = self.client.get("/manifest.json")
        self.assertEqual(r.status_code, 200)
        tipos = {i["type"] for i in r.json()["icons"]}
        self.assertIn("image/png", tipos)  # Play Store exige PNG

    def test_assetlinks_vazio_por_padrao(self):
        r = self.client.get("/.well-known/assetlinks.json")
        self.assertEqual(r.status_code, 200)
        # sem ANDROID_PACKAGE_NAME/CERT configurados, lista vazia mas JSON válido
        self.assertEqual(r.json(), [])

    def test_blog_index_loads(self):
        r = self.client.get("/blog")
        self.assertEqual(r.status_code, 200)
        self.assertIn("Notas do Lombada", r.text)

    def test_blog_post_renders_markdown(self):
        import blog as blog_mod
        posts = blog_mod.listar_posts()
        self.assertTrue(posts, "deve haver ao menos um post de exemplo")
        r = self.client.get(f"/blog/{posts[0]['slug']}")
        self.assertEqual(r.status_code, 200)
        self.assertIn("<h2", r.text)  # markdown convertido pra HTML

    def test_blog_post_not_found(self):
        r = self.client.get("/blog/post-que-nao-existe-xyz")
        self.assertEqual(r.status_code, 404)

    def test_blog_post_slug_traversal_blocked(self):
        r = self.client.get("/blog/..%2fmain")
        self.assertEqual(r.status_code, 404)

    def test_search_curta_sem_filtros_retorna_lista_vazia(self):
        r = self.client.get("/api/buscar", params={"q": "x"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), [])

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

    def test_merge_usuario_orfao_moves_reading_journal_entries(self):
        with main.Session(main.engine) as s:
            anon = main.Usuario(handle="merge-anon", nome="Anon")
            google = main.Usuario(handle="merge-google", nome="Google", google_sub="google-merge-sub")
            s.add(anon)
            s.add(google)
            s.commit()
            s.refresh(anon)
            s.refresh(google)

            obra = main.Obra(ol_work_key="merge-journal-work", titulo="Livro Merge", autor="Autora Merge")
            s.add(obra)
            s.commit()
            s.refresh(obra)
            edicao = main.Edicao(obra_id=obra.id, ol_edition_key="merge-journal-edition")
            s.add(edicao)
            s.commit()
            s.refresh(edicao)
            leitura = main.Leitura(edicao_id=edicao.id, usuario_id=anon.id, relato="Diário")
            s.add(leitura)
            s.commit()
            s.refresh(leitura)
            entry = main.ReadingJournalEntry(leitura_id=leitura.id, usuario_id=anon.id, nota="entrada")
            s.add(entry)
            s.commit()
            s.refresh(entry)

            auth._merge_usuario_orfao(s, anon.id, google.id)
            orphan_entries = s.exec(
                main.select(main.ReadingJournalEntry).where(main.ReadingJournalEntry.usuario_id == anon.id)
            ).all()
            moved_entry = s.get(main.ReadingJournalEntry, entry.id)
            moved_leitura = s.get(main.Leitura, leitura.id)

            self.assertEqual(orphan_entries, [])
            self.assertEqual(moved_entry.usuario_id, google.id)
            self.assertEqual(moved_entry.leitura_id, moved_leitura.id)
            self.assertEqual(moved_leitura.usuario_id, google.id)

    def test_literaturas_endpoint_lista_canonica(self):
        r = self.client.get("/api/literaturas")
        self.assertEqual(r.status_code, 200)
        slugs = {item["slug"] for item in r.json()}
        self.assertIn("brasileira", slugs)
        self.assertIn("latino-americana", slugs)

    def _semear_obras_filtros(self):
        """Três obras do mesmo autor-alvo: uma com origem Brasil (capa, ISBN,
        pt, leitura pública), uma com origem Rússia e uma sem metadado."""
        with main.Session(main.engine) as s:
            ja_existe = s.exec(main.select(main.Obra).where(main.Obra.ol_work_key == "filtros-br")).first()
            if ja_existe:
                return
            obra_br = main.Obra(ol_work_key="filtros-br", titulo="Mar de Ipanema", autor="Autorfiltro Silva",
                                literatura_pais="Brasil", literatura_regiao="América Latina", autor_pais="Brasil")
            obra_ru = main.Obra(ol_work_key="filtros-ru", titulo="Neve de Moscou", autor="Autorfiltro Ivanov",
                                literatura_pais="Rússia")
            obra_sem = main.Obra(ol_work_key="filtros-sem", titulo="Caminho Perdido", autor="Autorfiltro Souza")
            for obra in (obra_br, obra_ru, obra_sem):
                s.add(obra)
            s.commit()
            for obra in (obra_br, obra_ru, obra_sem):
                s.refresh(obra)
            ed_br = main.Edicao(obra_id=obra_br.id, editora="Editora Filtros", isbn="9788512345678",
                                idioma="pt", capa_url="https://exemplo.com/capa.jpg", ano=2021)
            ed_ru = main.Edicao(obra_id=obra_ru.id, editora="Editora Filtros")
            ed_sem = main.Edicao(obra_id=obra_sem.id, editora="Editora Filtros")
            for ed in (ed_br, ed_ru, ed_sem):
                s.add(ed)
            s.commit()
            s.refresh(ed_br)
            leitor = main.Usuario(handle="leitor-filtros", nome="Leitor Filtros")
            s.add(leitor)
            s.commit()
            s.refresh(leitor)
            s.add(main.Leitura(edicao_id=ed_br.id, usuario_id=leitor.id, status="Lido",
                               nota=4.5, relato="Crítica pública dos filtros", publico=True))
            s.add(main.Leitura(edicao_id=ed_br.id, usuario_id=leitor.id, status="Lendo"))
            s.commit()

    def test_buscar_permite_filtro_sem_texto(self):
        self._semear_obras_filtros()
        r = self.client.get("/api/buscar", params={"literatura": "brasileira", "idioma": "pt", "com_capa": "true"})
        self.assertEqual(r.status_code, 200)
        docs = r.json()
        self.assertEqual([d["titulo"] for d in docs], ["Mar de Ipanema"])
        self.assertEqual(docs[0]["capa_url"], "https://exemplo.com/capa.jpg")

    def test_buscar_filtro_literatura_prioriza_sem_esconder_obras_sem_metadado(self):
        self._semear_obras_filtros()
        r = self.client.get("/api/buscar", params={"q": "autorfiltro", "literatura": "brasileira"})
        self.assertEqual(r.status_code, 200)
        docs = r.json()
        titulos = [d["titulo"] for d in docs]
        self.assertIn("Mar de Ipanema", titulos)
        self.assertNotIn("Neve de Moscou", titulos)          # origem incompatível catalogada sai
        self.assertIn("Caminho Perdido", titulos)            # sem metadado não some da busca
        self.assertEqual(titulos[0], "Mar de Ipanema")       # match confirmado vem primeiro
        doc_br = next(d for d in docs if d["titulo"] == "Mar de Ipanema")
        self.assertEqual(doc_br["literatura_pais"], "Brasil")
        self.assertEqual(doc_br["literatura_regiao"], "América Latina")
        self.assertTrue(doc_br.get("_literatura_match"))

    def test_buscar_filtro_regiao_latino_americana(self):
        self._semear_obras_filtros()
        r = self.client.get("/api/buscar", params={"q": "autorfiltro", "literatura": "latino-americana"})
        self.assertEqual(r.status_code, 200)
        titulos = [d["titulo"] for d in r.json()]
        self.assertIn("Mar de Ipanema", titulos)
        self.assertNotIn("Neve de Moscou", titulos)

    def test_buscar_filtro_pais_nao_vaza_a_regiao_inteira(self):
        # Navegação só por filtro "argentina": um vizinho de OUTRO país catalogado
        # (Uruguai/América Latina) não pode vazar sob "Argentina". Obra sem origem
        # e sem nenhum sinal de qualidade (sem capa/ISBN) também não entra — cai no
        # piso `score <= 0`. A origem argentina confirmada vem no topo.
        with main.Session(main.engine) as s:
            if not s.exec(main.select(main.Obra).where(main.Obra.ol_work_key == "arg-borges")).first():
                arg = main.Obra(ol_work_key="arg-borges", titulo="Ficciones Teste", autor="Autorpais Borges",
                                literatura_pais="Argentina", literatura_regiao="América Latina", autor_pais="Argentina")
                vizinho = main.Obra(ol_work_key="arg-vizinho", titulo="Vizinho Teste", autor="Autorpais Onetti",
                                    literatura_pais="Uruguai", literatura_regiao="América Latina", autor_pais="Uruguai")
                sem = main.Obra(ol_work_key="arg-sem", titulo="Anonimo Teste", autor="Autorpais Souza")
                for o in (arg, vizinho, sem):
                    s.add(o)
                s.commit()
                for o in (arg, vizinho, sem):
                    s.refresh(o)
                for o, capa in ((arg, "https://x/arg.jpg"), (vizinho, "https://x/uy.jpg"), (sem, "")):
                    s.add(main.Edicao(obra_id=o.id, editora="Editora Pais", capa_url=capa))
                s.commit()

        r = self.client.get("/api/buscar", params={"literatura": "argentina"})
        self.assertEqual(r.status_code, 200)
        titulos = [d["titulo"] for d in r.json()]
        self.assertIn("Ficciones Teste", titulos)
        self.assertEqual(titulos[0], "Ficciones Teste")  # origem confirmada vem primeiro
        self.assertNotIn("Vizinho Teste", titulos)     # país catalogado diferente não vaza
        self.assertNotIn("Anonimo Teste", titulos)     # sem origem e sem capa/ISBN cai no piso

        # com_capa aplicado por cima continua funcionando
        r2 = self.client.get("/api/buscar", params={"literatura": "argentina", "com_capa": "true"})
        self.assertEqual(r2.status_code, 200)
        self.assertEqual([d["titulo"] for d in r2.json()], ["Ficciones Teste"])

    def test_buscar_filtro_so_traz_obra_sem_origem_com_capa(self):
        # Regressão: navegação só por filtro (sem texto digitado) deve funcionar
        # como nome+filtro — obra sem país catalogado, mas com capa, aparece na
        # vitrine (o catálogo tem poucos países preenchidos). A obra brasileira
        # confirmada vem primeiro; a sem origem entra logo atrás.
        self._semear_obras_filtros()   # garante "Mar de Ipanema" (Brasil, com capa)
        with main.Session(main.engine) as s:
            if not s.exec(main.select(main.Obra).where(main.Obra.ol_work_key == "solo-sem-origem")).first():
                obra = main.Obra(ol_work_key="solo-sem-origem", titulo="Sertao Sem Origem", autor="Autorsolo Ramos")
                s.add(obra)
                s.commit()
                s.refresh(obra)
                # idioma não-pt de propósito: mantém esta obra fora de outros
                # testes que filtram por idioma=pt e exigem igualdade exata.
                s.add(main.Edicao(obra_id=obra.id, editora="Editora Solo", idioma="en",
                                  capa_url="https://x/solo.jpg", isbn="9788599999999"))
                s.commit()

        r = self.client.get("/api/buscar", params={"literatura": "brasileira", "com_capa": "true"})
        self.assertEqual(r.status_code, 200)
        titulos = [d["titulo"] for d in r.json()]
        self.assertIn("Sertao Sem Origem", titulos)     # sem origem, mas com capa: entra no filtro-só
        self.assertIn("Mar de Ipanema", titulos)        # origem brasileira confirmada também
        self.assertEqual(titulos[0], "Mar de Ipanema")  # match confirmado no topo

    def test_buscar_filtros_sociais_e_de_qualidade(self):
        self._semear_obras_filtros()
        r = self.client.get("/api/buscar", params={"q": "autorfiltro", "com_capa": "true", "com_isbn": "true"})
        self.assertEqual(r.status_code, 200)
        titulos = [d["titulo"] for d in r.json()]
        self.assertEqual(titulos, ["Mar de Ipanema"])

        r = self.client.get("/api/buscar", params={"q": "autorfiltro", "com_criticas": "true"})
        self.assertEqual(r.status_code, 200)
        titulos = [d["titulo"] for d in r.json()]
        self.assertEqual(titulos, ["Mar de Ipanema"])
        doc = r.json()[0]
        self.assertEqual(doc["criticas_publicas"], 1)
        self.assertEqual(doc["lendo_agora_count"], 1)
        self.assertEqual(doc["nota_media"], 4.5)

        r = self.client.get("/api/buscar", params={"q": "autorfiltro", "lendo_agora": "true"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual([d["titulo"] for d in r.json()], ["Mar de Ipanema"])

        # idioma=pt mantém docs sem dado de idioma (filtro só age quando o dado existe)
        r = self.client.get("/api/buscar", params={"q": "autorfiltro", "idioma": "pt"})
        self.assertEqual(r.status_code, 200)
        titulos = [d["titulo"] for d in r.json()]
        self.assertIn("Mar de Ipanema", titulos)
        self.assertIn("Caminho Perdido", titulos)

        r = self.client.get("/api/buscar", params={"q": "autorfiltro", "ordenar": "popular"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()[0]["titulo"], "Mar de Ipanema")

    def test_buscar_sem_filtros_continua_igual(self):
        self._semear_obras_filtros()
        r = self.client.get("/api/buscar", params={"q": "autorfiltro"})
        self.assertEqual(r.status_code, 200)
        titulos = [d["titulo"] for d in r.json()]
        for titulo in ("Mar de Ipanema", "Neve de Moscou", "Caminho Perdido"):
            self.assertIn(titulo, titulos)

    def test_version_endpoint(self):
        r = self.client.get("/api/version")
        self.assertEqual(r.status_code, 200)

    def test_config_endpoint_expone_amazon_tag(self):
        r = self.client.get("/api/config")
        self.assertEqual(r.status_code, 200)
        self.assertIn("amazon_tag", r.json())  # vazio por padrão (sem env var)

    def test_eu_endpoint_anonymous(self):
        r = self.client.get("/api/eu")
        self.assertEqual(r.status_code, 200)

    def test_parsear_sumario_colado_extrai_titulo_e_pagina(self):
        texto = "Capítulo 1 — A Chegada .... 15\n\n2. O Encontro    34\nsem numeração nem página"
        itens = main._parsear_sumario_colado(texto)
        self.assertEqual(len(itens), 3)
        self.assertEqual(itens[0], {"ordem": 1, "titulo": "A Chegada", "pagina": 15})
        self.assertEqual(itens[1], {"ordem": 2, "titulo": "O Encontro", "pagina": 34})
        self.assertEqual(itens[2], {"ordem": 3, "titulo": "sem numeração nem página", "pagina": None})

    def test_interpolar_pagina_so_interpola_dentro_do_intervalo_conhecido(self):
        mapa = {1: 10, 3: 50}
        self.assertEqual(main._interpolar_pagina(mapa, 1), 10)
        self.assertEqual(main._interpolar_pagina(mapa, 2), 30)
        self.assertIsNone(main._interpolar_pagina(mapa, 5))  # fora do intervalo: sem extrapolação
        self.assertIsNone(main._interpolar_pagina({1: 10}, 2))  # só um ponto conhecido: sem interpolação

    def _criar_leitura_para_diario(self, sufixo: str):
        with main.Session(main.engine) as s:
            obra = main.Obra(ol_work_key=f"fase3-work-{sufixo}", titulo="Livro Fase 3", autor="Autora")
            s.add(obra); s.commit(); s.refresh(obra)
            edicao = main.Edicao(obra_id=obra.id, ol_edition_key=f"fase3-edicao-{sufixo}")
            s.add(edicao); s.commit(); s.refresh(edicao)
        r = self.client.get("/api/eu")
        handle = r.json()["handle"]
        with main.Session(main.engine) as s:
            usuario_id = s.exec(main.select(main.Usuario).where(main.Usuario.handle == handle)).first().id
        with main.Session(main.engine) as s:
            leitura = main.Leitura(edicao_id=edicao.id, usuario_id=usuario_id, status="Lendo")
            s.add(leitura); s.commit(); s.refresh(leitura)
        return edicao.id, leitura.id

    def test_colar_sumario_endpoint_cria_e_atualiza_capitulos(self):
        edicao_id, _ = self._criar_leitura_para_diario("colar")
        texto = "1. Início .... 10\n2. Meio .... 40"
        r = self.client.post(f"/api/edicoes/{edicao_id}/capitulos/colar", json={"texto": texto})
        self.assertEqual(r.status_code, 200)
        capitulos = r.json()
        self.assertEqual(len(capitulos), 2)
        self.assertEqual(capitulos[0]["titulo"], "Início")
        self.assertEqual(capitulos[0]["fonte"], "comunidade")

        r = self.client.get(f"/api/edicoes/{edicao_id}/capitulos")
        self.assertEqual(r.status_code, 200)
        self.assertEqual([c["titulo"] for c in r.json()], ["Início", "Meio"])

        # colar de novo corrige o título mas não sobrescreve página já conhecida
        r = self.client.post(f"/api/edicoes/{edicao_id}/capitulos/colar", json={"texto": "1. Início (revisado) .... 999"})
        self.assertEqual(r.status_code, 200)
        with main.Session(main.engine) as s:
            cap = s.exec(
                main.select(main.EdicaoCapitulo).where(main.EdicaoCapitulo.edicao_id == edicao_id, main.EdicaoCapitulo.ordem == 1)
            ).first()
            self.assertEqual(cap.titulo, "Início (revisado)")
            self.assertEqual(cap.pagina_inicio, 10)

    def test_colar_sumario_endpoint_rejeita_texto_sem_capitulos_reconheciveis(self):
        edicao_id, _ = self._criar_leitura_para_diario("colar-vazio")
        r = self.client.post(f"/api/edicoes/{edicao_id}/capitulos/colar", json={"texto": "   \n   "})
        self.assertEqual(r.status_code, 422)

    def test_diario_capitulo_com_pagina_alimenta_mapa_e_estima_capitulo_sem_pagina(self):
        edicao_id, leitura_id = self._criar_leitura_para_diario("mapa")

        r = self.client.post(
            f"/api/leitura/{leitura_id}/diario",
            json={"progresso_tipo": "capitulo", "capitulo": "Um", "capitulo_ordem": 1, "pagina": 10},
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["pagina"], 10)

        r = self.client.post(
            f"/api/leitura/{leitura_id}/diario",
            json={"progresso_tipo": "capitulo", "capitulo": "Três", "capitulo_ordem": 3, "pagina": 50},
        )
        self.assertEqual(r.status_code, 200)

        r = self.client.post(
            f"/api/leitura/{leitura_id}/diario",
            json={"progresso_tipo": "capitulo", "capitulo": "Dois", "capitulo_ordem": 2},
        )
        self.assertEqual(r.status_code, 200)
        self.assertIsNone(r.json()["pagina"])

        r = self.client.get(f"/api/leitura/{leitura_id}/diario")
        self.assertEqual(r.status_code, 200)
        entradas = {e["capitulo_ordem"]: e for e in r.json()}
        self.assertEqual(entradas[2]["pagina_estimada"], 30)
        self.assertIsNone(entradas[1]["pagina_estimada"])  # já tem página real, não precisa estimar

        with main.Session(main.engine) as s:
            capitulos = s.exec(
                main.select(main.EdicaoCapitulo).where(main.EdicaoCapitulo.edicao_id == edicao_id)
            ).all()
            mapa = {c.ordem: c.pagina_inicio for c in capitulos}
            self.assertEqual(mapa.get(1), 10)
            self.assertEqual(mapa.get(3), 50)


class NationalityInferenceTest(unittest.TestCase):
    """Valida o parsing/mapa do script de inferência de nacionalidade sem rede
    (a Wikidata é mockada por um client fake)."""

    @classmethod
    def setUpClass(cls):
        from scripts import infer_author_nationality as ni
        cls.ni = ni

    def _humano(self, *, pais_qid=None, ocupacao_qid=None, instancia_qid="Q5"):
        def snak(qid):
            return {"mainsnak": {"snaktype": "value", "datavalue": {"value": {"id": qid}}}}
        claims = {"P31": [snak(instancia_qid)]}
        if pais_qid:
            claims["P27"] = [snak(pais_qid)]
        if ocupacao_qid:
            claims["P106"] = [snak(ocupacao_qid)]
        return claims

    def _fake_client(self, qid, claims):
        ni = self.ni
        class _Resp:
            def __init__(self, p): self._p = p
            def raise_for_status(self): pass
            def json(self): return self._p
        class _Client:
            def get(self, url, params=None):
                if params.get("action") == "wbsearchentities":
                    return _Resp({"search": [{"id": qid}]})
                return _Resp({"entities": {qid: {"claims": claims}}})
        return _Client()

    def test_claim_qids_ignora_snak_sem_valor(self):
        claims = {"P27": [
            {"mainsnak": {"snaktype": "value", "datavalue": {"value": {"id": "Q155"}}}},
            {"mainsnak": {"snaktype": "novalue"}},
        ]}
        self.assertEqual(self.ni._claim_qids(claims, "P27"), ["Q155"])

    def test_escritor_com_pais_canonico_resolve(self):
        # Q155 = Brasil, Q36180 = writer
        c = self._fake_client("Q311145", self._humano(pais_qid="Q155", ocupacao_qid="Q36180"))
        self.assertEqual(self.ni._pais_do_autor(c, "Machado de Assis", ["pt"]), "Brasil")

    def test_estado_historico_mapeia_para_pais_moderno(self):
        # Q34266 = Império Russo → Rússia
        c = self._fake_client("Q991", self._humano(pais_qid="Q34266", ocupacao_qid="Q6625963"))
        self.assertEqual(self.ni._pais_do_autor(c, "Dostoievski", ["pt"]), "Rússia")

    def test_entidade_nao_humana_nao_resolve(self):
        # Q571 = livro (não é Q5/humano)
        c = self._fake_client("Q42", self._humano(pais_qid="Q155", instancia_qid="Q571"))
        self.assertEqual(self.ni._pais_do_autor(c, "Algum Livro", ["pt"]), "")

    def test_pais_fora_das_literaturas_canonicas_nao_resolve(self):
        c = self._fake_client("Q999", self._humano(pais_qid="Q1000"))  # país não mapeado
        self.assertEqual(self.ni._pais_do_autor(c, "Autor Estrangeiro", ["pt"]), "")

    def test_regiao_e_label_derivados_da_lista_canonica(self):
        self.assertEqual(self.ni._PAIS_REGIAO.get("Brasil"), "América Latina")
        self.assertEqual(self.ni._PAIS_REGIAO.get("Rússia"), "")
        self.assertEqual(self.ni._PAIS_LABEL.get("Brasil"), "brasileira")


if __name__ == "__main__":
    unittest.main()
