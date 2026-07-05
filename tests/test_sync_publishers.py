"""
Testes das funções puras de extração de metadado em scripts/sync_publishers.py.

Não testa scraping real (rede/HTML de terceiros) -- só a lógica de parsing
que decide qual texto vira "autor" no source_record. Existe porque um bug
real (autor ausente em "Noitada", promovido via publisher Shopify) veio de
usar o campo "vendor" do Shopify como autor -- no e-commerce de editora,
vendor é o selo/editora, não o autor do livro.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import sync_publishers as sp  # noqa: E402


class ExtractAuthorFromTextTest(unittest.TestCase):
    def test_extracts_author_after_label(self):
        texto = "Um romance intenso sobre a vida na fazenda. Autor: Graciliano Ramos | Páginas: 176"
        self.assertEqual(sp.extract_author_from_text(texto), "Graciliano Ramos")

    def test_accepts_autora_parens_and_dash_separator(self):
        self.assertEqual(sp.extract_author_from_text("Autor(a) - Clarice Lispector · 120 págs"), "Clarice Lispector")

    def test_no_label_returns_empty(self):
        self.assertEqual(sp.extract_author_from_text("descrição qualquer sem menção a autoria"), "")


class ShopifyAuthorPreferenceTest(unittest.TestCase):
    """Reproduz o bug do #168: o produto Shopify tem 'vendor' vazio (ou é só o
    selo da editora), mas a descrição cita o autor explicitamente."""

    def test_prefers_autor_label_in_description_over_vendor(self):
        description_full = "Poemas reunidos. Autor: Manoel de Barros | ISBN 9788535900000"
        vendor = "Selo Alfaguara"
        author = sp.extract_author_from_text(description_full) or vendor
        self.assertEqual(author, "Manoel de Barros")

    def test_falls_back_to_vendor_when_no_label_in_description(self):
        description_full = "Uma coletânea de contos sobre a cidade grande."
        vendor = "Companhia das Letras"
        author = sp.extract_author_from_text(description_full) or vendor
        self.assertEqual(author, vendor)

    def test_empty_vendor_and_no_label_yields_empty_author(self):
        author = sp.extract_author_from_text("sem nenhuma pista de autoria aqui") or ""
        self.assertEqual(author, "")


class VendorEAPropriaEditoraTest(unittest.TestCase):
    """Reproduz o incidente real: rodar o scraper corrigido em produção mostrou
    vendor="Editora Record"/"Editora Sextante" em 100% dos produtos dessas
    lojas -- ou seja, vendor era só a marca da própria editora, não teria
    dado pra usar como autor sem essa checagem."""

    def test_vendor_is_the_publisher_itself_record(self):
        self.assertTrue(sp._vendor_e_a_propria_editora("Editora Record", "Grupo Editorial Record"))

    def test_vendor_is_the_publisher_itself_sextante(self):
        self.assertTrue(sp._vendor_e_a_propria_editora("Editora Sextante", "Sextante"))

    def test_vendor_that_is_a_real_author_passes_through(self):
        self.assertFalse(sp._vendor_e_a_propria_editora("Machado de Assis", "Sextante"))

    def test_empty_vendor_is_not_the_publisher(self):
        self.assertFalse(sp._vendor_e_a_propria_editora("", "Sextante"))


class DividirTituloAutorCiaDasLetrasTest(unittest.TestCase):
    """Casos reais observados numa coleta real (issue #168): a página de livro
    da Cia das Letras não expõe autor via JSON-LD/meta, só embutido no
    <title>/h1 como "{Título} - {Autor}"."""

    def test_splits_real_samples_from_production_run(self):
        casos = [
            ("Seja ousado - Ranjay Gulati", ("Seja ousado", "Ranjay Gulati")),
            ("Aventureiros e larápios - Roberto Teixeira de Freitas", ("Aventureiros e larápios", "Roberto Teixeira de Freitas")),
            ("Empatia estoica - Shermin Kruse", ("Empatia estoica", "Shermin Kruse")),
            ("1929 - Andrew Ross Sorkin", ("1929", "Andrew Ross Sorkin")),
        ]
        for titulo, esperado in casos:
            with self.subTest(titulo=titulo):
                self.assertEqual(sp.dividir_titulo_autor_cia_das_letras(titulo), esperado)

    def test_title_without_separator_is_untouched(self):
        titulo = "As 12 competências da inteligência emocional"
        self.assertEqual(sp.dividir_titulo_autor_cia_das_letras(titulo), (titulo, ""))

    def test_does_not_mistake_subtitle_for_author_name(self):
        # todas as palavras do último segmento são capitalizadas/conectores,
        # mas é claramente um subtítulo de não-ficção, não um nome de pessoa.
        titulo = "O Iluminismo Radical - As Origens Intelectuais da Democracia"
        self.assertEqual(sp.dividir_titulo_autor_cia_das_letras(titulo), (titulo, ""))

    def test_single_word_subtitle_is_not_mistaken_for_author(self):
        titulo = "Grande Sertão - Veredas"
        self.assertEqual(sp.dividir_titulo_autor_cia_das_letras(titulo), (titulo, ""))


class CategoriaValorTest(unittest.TestCase):
    """A home da Cia das Letras usa Latin-1 nos hrefs (%E7=ç, %F3=ó) -- diferente
    do UTF-8 que o corpo do POST espera (ver diagnosticar_paginacao_categoria).
    URL real capturada num run de diagnóstico."""

    def test_decodes_latin1_query_param(self):
        url = "https://www.companhiadasletras.com.br/Busca?categoria=Administra%E7%E3o%2C+Neg%F3cios+e+Economia"
        self.assertEqual(sp._categoria_valor(url), "Administração, Negócios e Economia")

    def test_missing_categoria_param_yields_empty(self):
        self.assertEqual(sp._categoria_valor("https://www.companhiadasletras.com.br/Busca"), "")


class NormalizaTituloCaixaAltaTest(unittest.TestCase):
    def test_all_caps_becomes_sentence_case(self):
        self.assertEqual(
            sp._normaliza_titulo_caixa_alta("AS 12 COMPETÊNCIAS DA INTELIGÊNCIA EMOCIONAL"),
            "As 12 competências da inteligência emocional",
        )

    def test_already_mixed_case_is_untouched(self):
        titulo = "Seja ousado"
        self.assertEqual(sp._normaliza_titulo_caixa_alta(titulo), titulo)

    def test_empty_title_is_untouched(self):
        self.assertEqual(sp._normaliza_titulo_caixa_alta(""), "")


class MontaRegistroCategoriaJsonTest(unittest.TestCase):
    """livro vem estruturado da API JSON por trás do grid de categoria (ver
    collect_via_categoria_json) -- amostra real capturada no diagnóstico."""

    publisher = {"slug": "cia_das_letras", "name": "Companhia das Letras", "base_url": "https://www.companhiadasletras.com.br"}

    def test_builds_record_from_real_sample(self):
        livro = {
            "titulo": "AS 12 COMPETÊNCIAS DA INTELIGÊNCIA EMOCIONAL",
            "selo": "Objetiva",
            "preco": "R$ 89,90",
            "capa": "https://cdl-static.s3-sa-east-1.amazonaws.com/covers/160/9788539009794/capa.jpg",
            "link": "/livro/9788539009794/as-12-competencias-da-inteligencia-emocional",
            "autores": [{"nome": "Daniel Goleman", "link": "/colaborador/04392/daniel-goleman"}],
        }
        record = sp._monta_registro_categoria_json(livro, self.publisher, "Administração, Negócios e Economia")
        self.assertIsNotNone(record)
        normalized, _raw = record
        self.assertEqual(normalized["title"], "As 12 competências da inteligência emocional")
        self.assertEqual(normalized["author"], "Daniel Goleman")
        self.assertEqual(normalized["isbn"], "9788539009794")
        self.assertEqual(
            normalized["permalink"],
            "https://www.companhiadasletras.com.br/livro/9788539009794/as-12-competencias-da-inteligencia-emocional",
        )
        self.assertEqual(normalized["thumbnail"], livro["capa"])

    def test_joins_multiple_authors(self):
        livro = {
            "titulo": "Livro a Quatro Mãos",
            "link": "/livro/9780000000001/livro-a-quatro-maos",
            "autores": [{"nome": "Autor Um"}, {"nome": "Autor Dois"}],
        }
        record = sp._monta_registro_categoria_json(livro, self.publisher, "Ficção")
        normalized, _raw = record
        self.assertEqual(normalized["author"], "Autor Um, Autor Dois")

    def test_missing_link_yields_none(self):
        self.assertIsNone(sp._monta_registro_categoria_json({"titulo": "Sem link"}, self.publisher, "Ficção"))


if __name__ == "__main__":
    unittest.main()
