"""Regression tests for the central quick-actions sheet."""
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class QuickActionsUxTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.js = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
        cls.css = (ROOT / "static" / "app.css").read_text(encoding="utf-8")

    def test_sheet_has_three_predictable_paths_for_active_reading(self):
        self.assertIn('onclick="atualizarProgressoRapido()"', self.js)
        self.assertIn('onclick="adicionarNotaRapida()"', self.js)
        self.assertIn('onclick="registrarLeituraRapida()"', self.js)
        block = self.js.split('body.innerHTML=`${seletorLeituraRapidaHTML(lendo)}', 1)[1].split('`;', 1)[0]
        self.assertEqual(block.count('<button class="quick-action'), 3)

    def test_multiple_readings_use_one_selector_instead_of_many_rows(self):
        self.assertIn('id="quickReadingSelect"', self.js)
        self.assertNotIn('quick-reading-row', self.js)
        self.assertIn('function indiceLeituraRapida()', self.js)

    def test_note_path_focuses_diary_note(self):
        self.assertIn("abrirDiarioLeitura(alvo,{foco:'nota'})", self.js)
        self.assertIn("opcoes.foco==='nota'", self.js)
        self.assertIn('[data-diary-input="nota"], textarea', self.js)

    def test_empty_shelf_only_offers_registration(self):
        self.assertIn("if(!lendo.length)", self.js)
        self.assertIn("quick_register_reading", self.js)

    def test_selector_and_action_layout_are_styled(self):
        self.assertIn('.quick-reading-picker select', self.css)
        self.assertIn('.quick-actions-grid', self.css)


if __name__ == "__main__":
    unittest.main()
