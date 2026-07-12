"""Contratos do feedback pós-sessão do ritual `Li mais`."""
from __future__ import annotations

from pathlib import Path
from unittest import TestCase

from feature_flags import feature_enabled, public_feature_flags
from product_analytics import ProductEventInput, validate_product_event


ROOT = Path(__file__).resolve().parents[1]


class ProgressFeedbackFlagTest(TestCase):
    def test_flag_is_public_and_safe_by_default(self):
        self.assertFalse(feature_enabled("progress_feedback", {}))
        self.assertTrue(
            feature_enabled("progress_feedback", {"FF_PROGRESS_FEEDBACK": "true"})
        )
        self.assertIn("progress_feedback", public_feature_flags({}))
        self.assertFalse(public_feature_flags({})["progress_feedback"])

    def test_browser_allowlist_contains_flag(self):
        source = (ROOT / "static" / "feature-flags.js").read_text(encoding="utf-8")
        self.assertIn("'progress_feedback'", source)
        self.assertIn("state[name] = false", source)


class ProgressFeedbackUxContractTest(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = (ROOT / "static" / "activation-events.js").read_text(encoding="utf-8")

    def test_only_new_diary_entries_receive_feedback(self):
        self.assertIn("if (method !== 'POST') return null", self.source)
        self.assertIn("if (method === 'POST') scheduleProgressFeedback", self.source)
        self.assertIn("Edições de entradas antigas", self.source)

    def test_feedback_uses_real_progress_and_handles_corrections(self):
        for contract in (
            "previousPage",
            "previousPercent",
            "maxPageDelta",
            "maxPercentDelta",
            "totalPagesForReading",
            "current - previous",
            "insightType: 'correction'",
            "insightType: 'chapter'",
            "insightType: 'session'",
        ):
            self.assertIn(contract, self.source)

    def test_at_most_one_structural_insight_is_rendered(self):
        self.assertIn("const insight = progressInsight(snapshot, body)", self.source)
        self.assertIn("copy.title", self.source)
        self.assertIn("copy.detail", self.source)
        self.assertNotIn("insights.map", self.source)
        self.assertNotIn("confete", self.source)

    def test_feedback_is_non_blocking_accessible_and_gentle(self):
        self.assertIn("setAttribute('role', 'status')", self.source)
        self.assertIn("setAttribute('aria-live', 'polite')", self.source)
        self.assertIn("auto_closed", self.source)
        self.assertIn("navigator.vibrate(18)", self.source)
        self.assertIn("prefers-reduced-motion: reduce", self.source)
        self.assertNotIn("aria-modal", self.source)

    def test_old_toast_remains_the_fallback_when_flag_is_off(self):
        self.assertIn("features.isEnabled?.('progress_feedback')", self.source)
        self.assertIn("if (!insight) return", self.source)
        self.assertIn("originalToast.call", self.source)
        self.assertIn("suppressProgressToastUntil", self.source)

    def test_copy_exists_in_three_locales(self):
        for text in (
            "+${number(insight.delta)} páginas nesta sessão.",
            "+${number(insight.delta)} pages in this session.",
            "+${number(insight.delta)} páginas en esta sesión.",
            "Sua maior sessão nesta leitura.",
            "Your biggest session in this book.",
            "Tu mayor sesión en este libro.",
        ):
            self.assertIn(text, self.source)


class ProgressFeedbackAnalyticsContractTest(TestCase):
    def test_backend_accepts_only_structural_feedback_properties(self):
        properties = {
            "source": "diary",
            "insight_type": "page_delta",
            "action": "viewed",
        }
        name, normalized, _ = validate_product_event(
            ProductEventInput(
                event="progress_feedback",
                properties=properties,
                client_event_id="progress-feedback-0001",
            )
        )
        self.assertEqual(name, "progress_feedback")
        self.assertEqual(normalized, properties)

    def test_client_allowlist_and_source_contain_no_reading_content(self):
        client = (ROOT / "static" / "product-analytics.js").read_text(encoding="utf-8")
        source = (ROOT / "static" / "activation-events.js").read_text(encoding="utf-8")
        self.assertIn("progress_feedback: ['source', 'insight_type', 'action']", client)
        self.assertIn("emit('progress_feedback'", source)
        for forbidden in ("title:", "author:", "isbn:", "query:", "note:"):
            feedback_calls = [
                line for line in source.splitlines()
                if "progress_feedback" in line or "insight_type" in line or "action:" in line
            ]
            self.assertNotIn(forbidden, "\n".join(feedback_calls).lower())


if __name__ == "__main__":
    import unittest

    unittest.main()
