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


if __name__ == "__main__":
    unittest.main()
