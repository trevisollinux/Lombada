"""Validação do cadastro normalizado e do adaptador de fontes de editoras."""
import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import publisher_catalog_policies as policies  # noqa: E402
import sync_publishers as sp  # noqa: E402
import sync_publishers_catalog as catalog_adapter  # noqa: E402


class PublisherCatalogValidationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.path = ROOT / "data" / "publishers"
        cls.catalog = catalog_adapter.load_catalog(cls.path)
        cls.publishers = cls.catalog["publishers"]

    def test_schema_and_size(self):
        self.assertEqual(self.catalog["schema_version"], 1)
        self.assertGreaterEqual(len(self.publishers), 100)

    def test_slugs_are_unique_and_normalized(self):
        slugs = [publisher["slug"] for publisher in self.publishers]
        self.assertEqual(len(slugs), len(set(slugs)))
        for slug in slugs:
            self.assertRegex(slug, r"^[a-z0-9_]+$")

    def test_enabled_sources_have_https_url_and_group(self):
        enabled = [
            publisher
            for publisher in self.publishers
            if publisher["scrape"]["enabled"]
        ]
        self.assertGreaterEqual(len(enabled), 80)
        for publisher in enabled:
            scrape = publisher["scrape"]
            self.assertEqual(publisher["status"], "active")
            self.assertTrue(scrape["base_url"].startswith("https://"))
            self.assertRegex(scrape["group"], r"^catalogo_[a-h]$")

    def test_historical_publishers_are_never_scraped(self):
        historical = [
            publisher
            for publisher in self.publishers
            if publisher["status"] == "historical"
        ]
        self.assertTrue(historical)
        self.assertTrue(
            all(not publisher["scrape"]["enabled"] for publisher in historical)
        )

    def test_normalization_corrections_are_preserved(self):
        by_slug = {publisher["slug"]: publisher for publisher in self.publishers}

        jandaira = by_slug["editora_jandaira"]
        self.assertIn("Pólen Livros", jandaira["aliases"])
        self.assertEqual(jandaira["status"], "active")

        brasiliense = by_slug["editora_brasiliense"]
        self.assertEqual(brasiliense["status"], "active")
        self.assertNotEqual(brasiliense["category"], "historica")

        estacao = by_slug["estacao_liberdade"]
        self.assertEqual(estacao["category"], "independente")

    def test_portuguese_is_normalized_to_pt_br(self):
        raw = "\n".join(path.read_text(encoding="utf-8") for path in self.path.glob("*.csv")).lower()
        for european_form in (
            "económicas",
            "académico",
            "guiões",
            "recolhas",
            "banda desenhada",
        ):
            self.assertNotIn(european_form, raw)

    def test_globo_remains_registered_but_direct_scrape_is_blocked(self):
        by_slug = {publisher["slug"]: publisher for publisher in self.publishers}
        globo = by_slug["globo_livros"]

        self.assertEqual(globo["status"], "active")
        self.assertFalse(globo["scrape"]["enabled"])
        self.assertEqual(globo["scrape"]["url_status"], "blocked")


class PublisherCatalogAdapterTest(unittest.TestCase):
    def test_adapter_skips_existing_specialized_source(self):
        fake_module = SimpleNamespace(
            SOURCES=[
                {
                    "slug": "ubu",
                    "name": "Ubu especializada",
                    "base_url": "https://example.test",
                    "platform": "custom",
                }
            ]
        )
        catalog = catalog_adapter.load_catalog(ROOT / "data" / "publishers")

        added = catalog_adapter.extend_sources(fake_module, catalog)

        slugs = [source["slug"] for source in fake_module.SOURCES]
        self.assertEqual(slugs.count("ubu"), 1)
        self.assertGreater(added, 80)
        self.assertIn("global_editora", slugs)
        self.assertNotIn("globo_livros", slugs)

    def test_adapter_ignores_disabled_and_historical_entries(self):
        catalog = {
            "schema_version": 1,
            "publishers": [
                {
                    "slug": "ativa",
                    "name": "Ativa",
                    "status": "active",
                    "scrape": {
                        "enabled": True,
                        "base_url": "https://ativa.example",
                        "platform": "auto",
                        "group": "catalogo_a",
                    },
                },
                {
                    "slug": "desabilitada",
                    "name": "Desabilitada",
                    "status": "active",
                    "scrape": {
                        "enabled": False,
                        "base_url": "https://desabilitada.example",
                    },
                },
                {
                    "slug": "historica",
                    "name": "Histórica",
                    "status": "historical",
                    "scrape": {
                        "enabled": True,
                        "base_url": "https://historica.example",
                    },
                },
            ],
        }

        sources = catalog_adapter.scraper_sources(catalog)

        self.assertEqual([source["slug"] for source in sources], ["ativa"])

    def test_global_uses_current_official_domain(self):
        catalog = catalog_adapter.load_catalog(ROOT / "data" / "publishers")
        sources = {source["slug"]: source for source in catalog_adapter.scraper_sources(catalog)}

        self.assertEqual(
            sources["global_editora"]["base_url"],
            "https://grupoeditorialglobal.com.br",
        )


class PublisherCatalogPolicyTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        policies.install(sp)

    def test_decodes_nested_html_entities_in_titles(self):
        record = sp.build_record(
            {"slug": "martin_claret", "name": "Martin Claret"},
            "https://example.test/livro",
            title="Recordações d&amp;#039;Arc",
            isbn="9780000000000",
        )

        self.assertIsNotNone(record)
        self.assertEqual(record[0]["title"], "Recordações d'Arc")

    def test_rejects_planeta_author_pages_and_generic_titles(self):
        generic = sp.build_record(
            {"slug": "planeta_livros_brasil", "name": "Planeta"},
            "https://www.planetadelivros.com.br/autor/james-shapiro/000057",
            title="Outros livros de James Shapiro",
            isbn="9788542226683",
        )

        self.assertFalse(sp.valid_extracted_record(generic))

    def test_planeta_extractor_prefers_h1_and_real_author_link(self):
        page = SimpleNamespace(
            text="""
            <html><head>
              <meta property="og:title" content="Outros livros de Erich Fromm">
              <meta property="og:image" content="https://cdn.example/capa.jpg">
            </head><body>
              <h1>A arte de ser</h1>
              <a href="/autor/erich-fromm/000123">Erich Fromm</a>
              <section>ISBN 978-85-422-3194-6</section>
            </body></html>
            """
        )
        publisher = {
            "slug": "planeta_livros_brasil",
            "name": "Editora Planeta de Livros Brasil",
        }

        with patch.object(sp, "fetch_url", return_value=page):
            record = sp.extract_page(
                "https://www.planetadelivros.com.br/livro-a-arte-de-ser/413414",
                publisher,
            )

        self.assertIsNotNone(record)
        self.assertEqual(record[0]["title"], "A arte de ser")
        self.assertEqual(record[0]["author"], "Erich Fromm")
        self.assertEqual(record[0]["isbn"], "9788542231946")

    def test_extracts_author_from_semantic_links(self):
        soup = BeautifulSoup(
            '<main><a href="/autor/jane-austen/">Jane Austen</a></main>',
            "html.parser",
        )

        self.assertEqual(sp.extract_author_from_soup(soup, {}), "Jane Austen")

    def test_explicit_unknown_slug_never_falls_back_to_all_sources(self):
        with patch.dict(os.environ, {"PUBLISHER_SLUGS": "nao_existe"}, clear=False):
            self.assertEqual(sp.select_sources(), [])


if __name__ == "__main__":
    unittest.main()
