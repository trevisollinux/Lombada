"""Contrato que impede o observador de re-renderizar o próprio inbox em ciclo."""
from pathlib import Path
from unittest import TestCase


ROOT = Path(__file__).resolve().parents[1]


class LiteraryReactionDomStabilityTest(TestCase):
    def test_inbox_uses_a_stable_signature_before_replacing_children(self):
        source = (ROOT / "static" / "literary-reactions.js").read_text(encoding="utf-8")
        self.assertIn("const signature = JSON.stringify(inboxData)", source)
        self.assertIn("section.dataset.signature !== signature", source)
        self.assertIn("section.dataset.signature = signature", source)
        signature_check = source.index("section.dataset.signature !== signature")
        inner_html_write = source.index("section.innerHTML = inboxHTML(inboxData)")
        self.assertLess(signature_check, inner_html_write)


if __name__ == "__main__":
    import unittest

    unittest.main()
