"""Regression tests for the home information hierarchy."""
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class HomeHierarchyTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (ROOT / "index.html").read_text(encoding="utf-8")
        cls.js = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
        cls.css = (ROOT / "static" / "app.css").read_text(encoding="utf-8")

    def test_current_reading_precedes_onboarding_and_discovery(self):
        reading = self.html.index('id="lendoAgora"')
        onboarding = self.html.index('id="onboardingBox"')
        popular = self.html.index('id="populares"')
        publishers = self.html.index('id="editorasHome"')

        self.assertLess(reading, onboarding)
        self.assertLess(onboarding, popular)
        self.assertLess(popular, publishers)

    def test_returning_reader_hides_redundant_hero(self):
        self.assertIn("classList.toggle('has-current-reading'", self.js)
        self.assertIn(
            ".home-feed.has-current-reading .home-intro{display:none}",
            self.css,
        )

    def test_see_shelf_is_a_real_button(self):
        self.assertIn('class="more home-more-button"', self.js)
        self.assertIn('<button type="button"', self.js)

    def test_home_discovery_is_intentionally_bounded(self):
        self.assertIn(".map(normalizarObraPopular).slice(0,8)", self.js)


if __name__ == "__main__":
    unittest.main()
