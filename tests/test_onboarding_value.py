"""Contratos do onboarding que leva ao primeiro valor pessoal."""
from __future__ import annotations

from pathlib import Path
from unittest import TestCase

from feature_flags import feature_enabled, public_feature_flags
from product_analytics import ProductEventInput, validate_product_event


ROOT = Path(__file__).resolve().parents[1]


class OnboardingValueFlagTest(TestCase):
    def test_flag_defaults_off_and_is_public(self):
        self.assertFalse(feature_enabled("onboarding_value", {}))
        self.assertTrue(
            feature_enabled("onboarding_value", {"FF_ONBOARDING_VALUE": "true"})
        )
        self.assertIn("onboarding_value", public_feature_flags({}))
        self.assertFalse(public_feature_flags({})["onboarding_value"])

    def test_browser_allowlist_contains_flag_and_safe_status_override(self):
        source = (ROOT / "static" / "feature-flags.js").read_text(encoding="utf-8")
        self.assertIn("'onboarding_value'", source)
        self.assertIn("state[name] = false", source)
        self.assertIn("catch (_)", source)
        self.assertIn("installOnboardingStatusDefault", source)
        self.assertIn("selected === 'Lido' ? 'Lendo' : selected", source)
        self.assertIn("isEnabled('onboarding_value')", source)
        self.assertIn("lombada_onboarding_value", source)


class OnboardingValueUxContractTest(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ux = (ROOT / "static" / "ux-fixes.js").read_text(encoding="utf-8")
        cls.app = (ROOT / "static" / "app.js").read_text(encoding="utf-8")

    def test_new_experience_is_flag_gated_and_falls_back_to_existing_checklist(self):
        self.assertIn("isEnabled?.('onboarding_value')", self.ux)
        self.assertIn("onboardingChecklistBase(passos)", self.ux)
        self.assertIn("passos?.registrou", self.ux)
        self.assertIn("onboardingChecklistInterativo", self.ux)
        self.assertIn("abrirPassoProgressoOnboarding", self.ux)

    def test_primary_action_reuses_search_and_manual_fallback(self):
        self.assertIn("iniciarOnboardingPrimeiroValor", self.ux)
        self.assertIn("irPara('buscar')", self.ux)
        self.assertIn("document.querySelector('#q')?.focus", self.ux)
        self.assertIn("iniciarCadastroManualOnboarding", self.ux)
        self.assertIn("abrirManual", self.ux)
        self.assertNotIn("showModal", self.ux)

    def test_copy_exists_in_three_locales_and_describes_returning_value(self):
        for text in (
            "Qual livro está com você agora?",
            "Which book is with you right now?",
            "¿Qué libro está contigo ahora?",
            "Li mais",
            "Read more",
            "Leí más",
        ):
            self.assertIn(text, self.ux)

    def test_first_reading_removes_onboarding_through_existing_reload(self):
        save_start = self.app.index("async function salvar(event)")
        shelf_start = self.app.index("async function carregarPrateleira()")
        shelf_end = self.app.index("/* diário", shelf_start)
        save_flow = self.app[save_start:shelf_start]
        reload_flow = self.app[shelf_start:shelf_end]

        self.assertIn("await carregarPrateleira()", save_flow)
        self.assertIn("renderOnboarding()", reload_flow)

    def test_mobile_dark_and_reduced_motion_contracts_exist(self):
        self.assertIn("@media(max-width:720px)", self.ux)
        self.assertIn(".theme-dark .onboarding-value-card", self.ux)
        self.assertIn("@media(prefers-reduced-motion:reduce)", self.ux)


class OnboardingValueAnalyticsContractTest(TestCase):
    def test_backend_allows_onboarding_as_structural_source(self):
        cases = (
            ("search_submitted", {"source": "onboarding", "has_filters": False, "result_state": "submitted"}),
            ("book_opened", {"source": "onboarding", "has_cover": True}),
            ("reading_created", {"source": "onboarding", "status": "Lendo", "has_rating": False, "public": False}),
        )
        for event_name, properties in cases:
            with self.subTest(event=event_name):
                normalized_name, normalized, _ = validate_product_event(
                    ProductEventInput(
                        event=event_name,
                        properties=properties,
                        client_event_id=f"onboard-{event_name}",
                    )
                )
                self.assertEqual(normalized_name, event_name)
                self.assertEqual(normalized, properties)

    def test_frontend_marker_never_contains_book_or_query_content(self):
        source = (ROOT / "static" / "activation-events.js").read_text(encoding="utf-8")
        self.assertIn("lombada_onboarding_value", source)
        self.assertIn("source: onboardingValueActive() ? 'onboarding' : 'home'", source)
        self.assertIn("clearOnboardingValueMarker", source)
        self.assertIn("source === 'onboarding'", source)
        self.assertNotIn("properties: { query", source)
        self.assertNotIn("properties: { title", source)
        self.assertNotIn("properties: { isbn", source)


if __name__ == "__main__":
    import unittest

    unittest.main()
