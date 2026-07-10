"""Regression tests for the shelf and explore information hierarchy."""
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class HomeHierarchyTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (ROOT / "index.html").read_text(encoding="utf-8")
        cls.js = (ROOT / "static" / "app.js").read_text(encoding="utf-8")

    def test_shelf_is_the_default_tab(self):
        self.assertIn('class="tab active" id="tabEstante"', self.html)
        self.assertIn("estadoNav('estante','home')", self.js)

    def test_shelf_places_onboarding_before_books(self):
        shelf = self.html.index('id="shelfView"')
        onboarding = self.html.index('id="onboardingBox"', shelf)
        books = self.html.index('id="prateleira"', shelf)

        self.assertLess(shelf, onboarding)
        self.assertLess(onboarding, books)

    def test_current_reading_is_rendered_inside_shelf_before_controls(self):
        block_start = self.js.index("function blocoLendoEstante(){")
        render_start = self.js.index("function renderPrateleira(){")
        block = self.js[block_start:render_start]
        render_end = self.js.index("async function carregarPrateleira()", render_start)
        render = self.js[render_start:render_end]

        self.assertIn("lendoAgoraCard(", block)
        self.assertIn("blocoLendoEstante()+controlesEstante()", render)

    def test_discovery_lives_in_explore_and_is_bounded(self):
        explore = self.html.index('id="secFeed"')
        popular = self.html.index('id="populares"', explore)
        publishers = self.html.index('id="editorasHome"', explore)
        shelf = self.html.index('id="secEstante"')

        self.assertLess(explore, popular)
        self.assertLess(popular, publishers)
        self.assertLess(publishers, shelf)
        self.assertIn(".map(normalizarObraPopular).slice(0,8)", self.js)


if __name__ == "__main__":
    unittest.main()
