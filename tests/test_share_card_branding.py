import pathlib
import unittest


class ShareCardBrandingTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ux = pathlib.Path("static/ux-fixes.js").read_text(encoding="utf-8")

    def test_uses_lombada_domain(self):
        self.assertIn("ctx.fillText('lombada.app'", self.ux)

    def test_domain_is_right_aligned(self):
        self.assertIn("ctx.textAlign = 'right'", self.ux)

    def test_random_handle_is_not_drawn_by_footer_override(self):
        footer = self.ux.split("window.drawFooter =", 1)[1].split("window.abrirPassoProgressoOnboarding", 1)[0]
        self.assertNotIn("meuHandle", footer)
        self.assertNotIn("@${", footer)

    def test_all_share_card_layouts_are_overridden(self):
        self.assertIn("window.drawFooter =", self.ux)
        self.assertIn("window.drawReviewShareCardText =", self.ux)
        self.assertIn("window.drawDiaryShareCardText =", self.ux)


if __name__ == "__main__":
    unittest.main()
