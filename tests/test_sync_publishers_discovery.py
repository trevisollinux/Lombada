"""Testes de descoberta e normalização do scraper de editoras.

Mantém cobertos os filtros que impedem páginas institucionais, listagens e
assets estáticos de entrarem como livros no catálogo.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import sync_publishers as sp  # noqa: E402


class IsbnExtractionTest(unittest.TestCase):
    def test_prefers_labeled_isbn_and_ignores_trailing_year(self):
        texto = "ISBN 978-85-359-4784-7 2025 · 320 páginas"
        self.assertEqual(sp.extract_isbn(texto), "9788535947847")

    def test_reads_isbn_from_book_url_segment(self):
        url = "https://editora.example/livro/9788535947847/dom-casmurro"
        self.assertEqual(sp.isbn_from_url(url), "9788535947847")

    def test_rejects_unrelated_phone_number(self):
        self.assertEqual(sp.extract_isbn("Contato: (21) 99876-5432"), "")


class SitemapParsingTest(unittest.TestCase):
    def test_parses_sitemap_index(self):
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
          <sitemap><loc>https://editora.example/books.xml</loc></sitemap>
        </sitemapindex>
        """

        children, pages = sp.parse_sitemap_urls(xml)

        self.assertEqual(children, ["https://editora.example/books.xml"])
        self.assertEqual(pages, [])

    def test_parses_urlset(self):
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
          <url><loc>https://editora.example/livro/dom-casmurro</loc></url>
        </urlset>
        """

        children, pages = sp.parse_sitemap_urls(xml)

        self.assertEqual(children, [])
        self.assertEqual(
            pages, ["https://editora.example/livro/dom-casmurro"]
        )

    def test_invalid_xml_returns_empty_lists(self):
        self.assertEqual(sp.parse_sitemap_urls("<xml quebrado"), ([], []))


class BookUrlClassificationTest(unittest.TestCase):
    def test_accepts_product_detail_page(self):
        self.assertTrue(
            sp.looks_like_book_url(
                "https://editora.example/produto/dom-casmurro"
            )
        )

    def test_rejects_catalog_listing(self):
        self.assertFalse(
            sp.looks_like_book_url("https://editora.example/produtos")
        )

    def test_rejects_static_asset_with_product_path(self):
        self.assertFalse(
            sp.looks_like_book_url(
                "https://editora.example/pub/media/catalog/product/capa.jpg"
            )
        )

    def test_rejects_editorial_page_that_mentions_book(self):
        self.assertFalse(
            sp.looks_like_book_url(
                "https://editora.example/blog/novo-livro-da-editora"
            )
        )


class HtmlLinkHarvestTest(unittest.TestCase):
    def test_separates_book_pages_from_catalog_navigation(self):
        html = """
        <a href="/livros">Catálogo</a>
        <a href="/livros?page=2">Página 2</a>
        <a href="/produto/dom-casmurro">Dom Casmurro</a>
        <a href="/blog/novo-livro">Notícia</a>
        <a href="https://outro.example/produto/externo">Externo</a>
        """

        books, listings = sp.harvest_links(
            html, "https://editora.example"
        )

        self.assertEqual(
            books, ["https://editora.example/produto/dom-casmurro"]
        )
        self.assertIn("https://editora.example/livros", listings)
        self.assertIn("https://editora.example/livros?page=2", listings)
        self.assertNotIn(
            "https://outro.example/produto/externo", books
        )


if __name__ == "__main__":
    unittest.main()
