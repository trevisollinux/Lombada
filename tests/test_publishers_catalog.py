"""Validação do cadastro normalizado e do adaptador de fontes de editoras."""
import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, os.path.join(ROOT, "scripts"))

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
        self.assertIn("globo_livros", slugs)

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


if __name__ == "__main__":
    unittest.main()
