"""Contratos estáticos da primeira rodada de paridade do frontend React."""
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend" / "src"


class ReactV2ParityRitualTest(unittest.TestCase):
    def read(self, relative: str) -> str:
        return (FRONTEND / relative).read_text(encoding="utf-8")

    def test_feature_flags_fail_closed_and_use_public_endpoint(self):
        source = self.read("providers/FeatureFlagsProvider.tsx")
        self.assertIn("/api/features", source)
        self.assertIn("cache: 'no-store'", source)
        self.assertIn("disabledSnapshot", source)
        self.assertIn("payload.features?.[name] === true", source)

    def test_analytics_is_gated_and_uses_private_allowlisted_endpoint(self):
        service = self.read("services/analytics.ts")
        bridge = self.read("components/ProductAnalyticsBridge.tsx")
        self.assertIn("/api/events", service)
        self.assertIn("keepalive: true", service)
        self.assertIn("if (!analyticsEnabled) return false", service)
        self.assertIn("enabled('product_analytics')", bridge)
        for forbidden in ("titulo", "autor", "isbn", "email", "handle"):
            self.assertNotIn(forbidden, service.lower())

    def test_quick_progress_reuses_existing_contracts(self):
        dialog = self.read("features/progress/ProgressQuickDialog.tsx")
        api = self.read("features/progress/progressApi.ts")
        self.assertIn("/api/leitura/${readingId}/progresso", api)
        self.assertIn("createDiaryEntry", dialog)
        self.assertIn("origem: 'li_mais'", dialog)
        self.assertIn("progress_type", dialog)
        self.assertIn("public: false", dialog)

    def test_onboarding_is_optional_and_reuses_search(self):
        search = self.read("pages/SearchPage.tsx")
        card = self.read("features/progress/OnboardingValueCard.tsx")
        self.assertIn("enabled('onboarding_value')", search)
        self.assertIn("sessionStorage.setItem(ONBOARDING_MARKER, 'active')", search)
        self.assertIn("inputRef.current?.focus()", search)
        self.assertIn("onDismiss", card)

    def test_onboarding_aponta_para_a_home_do_app(self):
        # Antes do corte para `/`, este teste também exigia um link de volta ao
        # app legado dentro do detalhe da estante. Esse link não existe mais:
        # a raiz agora é o próprio React, e o legado virou rota de escape em
        # /app-v1, fora dos fluxos do app.
        card = self.read("features/progress/OnboardingValueCard.tsx")
        self.assertIn('href="/"', card)


if __name__ == "__main__":
    unittest.main()
