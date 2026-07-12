"""Integração entre o ritual de progresso e a instrumentação de ativação."""
from pathlib import Path
from unittest import TestCase


ROOT = Path(__file__).resolve().parents[1]


class ActivationAnalyticsContractTest(TestCase):
    def test_helpers_and_instrumentation_load_before_app(self):
        index = (ROOT / "index.html").read_text(encoding="utf-8")
        flags = index.index('/static/feature-flags.js')
        analytics = index.index('/static/product-analytics.js')
        activation = index.index('/static/activation-events.js')
        app = index.index('/static/app.js')

        self.assertLess(flags, analytics)
        self.assertLess(analytics, activation)
        self.assertLess(activation, app)
        self.assertIn('id="lendoAgora"', index)

    def test_small_batches_flush_and_routes_match_real_writes(self):
        client = (ROOT / "static" / "product-analytics.js").read_text(encoding="utf-8")
        activation = (ROOT / "static" / "activation-events.js").read_text(encoding="utf-8")

        self.assertIn("LombadaFeatures.isEnabled('product_analytics')", client)
        self.assertIn("FLUSH_DELAY_MS", client)
        self.assertIn("visibilitychange", client)
        self.assertIn("keepalive: true", client)
        self.assertIn("/api/prateleira", activation)
        self.assertIn("/api\\/leitura\\/\\d+\\/diario", activation)
        self.assertIn("/api\\/diario\\/\\d+", activation)
        self.assertNotIn("path === '/api/manual'", activation)
        self.assertIn("emitAppOpenedAfterSession", activation)


if __name__ == "__main__":
    import unittest

    unittest.main()
