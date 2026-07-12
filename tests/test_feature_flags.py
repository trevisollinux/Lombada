"""Contratos da fundação de feature flags do Lombada 2.0."""
from __future__ import annotations

import os
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from feature_flags import (
    FEATURE_FLAGS,
    INTERNAL_FEATURE_NAMES,
    PUBLIC_FEATURE_NAMES,
    all_feature_flags,
    feature_enabled,
    parse_flag_value,
    public_feature_flags,
    router,
)


ROOT = Path(__file__).resolve().parents[1]


class FeatureFlagParsingTest(TestCase):
    def test_true_values(self):
        for value in (True, "1", "true", "TRUE", " yes ", "on", "enabled"):
            with self.subTest(value=value):
                self.assertTrue(parse_flag_value(value))

    def test_false_values(self):
        for value in (False, None, "", "0", "false", "NO", " off ", "disabled"):
            with self.subTest(value=value):
                self.assertFalse(parse_flag_value(value))

    def test_invalid_value_uses_safe_default(self):
        self.assertFalse(parse_flag_value("talvez"))
        self.assertTrue(parse_flag_value("talvez", default=True))

    def test_all_registered_flags_default_to_off(self):
        snapshot = all_feature_flags({})
        self.assertEqual(set(snapshot), set(FEATURE_FLAGS))
        self.assertTrue(snapshot)
        self.assertTrue(all(value is False for value in snapshot.values()))

    def test_registered_flag_reads_its_environment_variable(self):
        self.assertTrue(feature_enabled("home_ritual", {"FF_HOME_RITUAL": "true"}))
        self.assertFalse(feature_enabled("home_ritual", {"FF_HOME_RITUAL": "invalid"}))

    def test_unknown_flag_fails_early(self):
        with self.assertRaisesRegex(KeyError, "desconhecida"):
            feature_enabled("typo_flag", {})


class FeatureFlagExposureTest(TestCase):
    def test_public_snapshot_excludes_internal_flags(self):
        env = {
            "FF_HOME_RITUAL": "true",
            "FF_ADMIN_RETENTION_DASHBOARD": "true",
        }
        public = public_feature_flags(env)
        complete = all_feature_flags(env)

        self.assertTrue(public["home_ritual"])
        self.assertTrue(complete["admin_retention_dashboard"])
        self.assertNotIn("admin_retention_dashboard", public)
        self.assertEqual(set(public), set(PUBLIC_FEATURE_NAMES))
        self.assertEqual(INTERNAL_FEATURE_NAMES, ("admin_retention_dashboard",))

    def test_public_endpoint_returns_only_allowlisted_booleans(self):
        app = FastAPI()
        app.include_router(router)

        with patch.dict(
            os.environ,
            {
                "FF_HOME_RITUAL": "true",
                "FF_ADMIN_RETENTION_DASHBOARD": "true",
            },
            clear=True,
        ):
            response = TestClient(app).get("/api/features")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["cache-control"], "no-store, no-cache, must-revalidate, max-age=0")
        payload = response.json()
        self.assertEqual(payload["version"], 1)
        self.assertTrue(payload["features"]["home_ritual"])
        self.assertNotIn("admin_retention_dashboard", payload["features"])
        self.assertTrue(all(isinstance(value, bool) for value in payload["features"].values()))

    def test_production_entrypoint_registers_router_once(self):
        source = (ROOT / "app_entry.py").read_text(encoding="utf-8")
        self.assertIn("feature_flags_router", source)
        self.assertIn("feature_flags_router_installed", source)
        self.assertIn("app.include_router(feature_flags_router)", source)


class FeatureFlagFrontendContractTest(TestCase):
    def test_frontend_helper_is_allowlisted_and_fail_closed(self):
        source = (ROOT / "static" / "feature-flags.js").read_text(encoding="utf-8")

        self.assertIn("/api/features", source)
        self.assertIn("cache: 'no-store'", source)
        self.assertIn("global.LombadaFeatures", source)
        self.assertIn("state[name] = received[name] === true", source)
        self.assertIn("catch (_)", source)
        self.assertIn("state[name] = false", source)
        self.assertNotIn("admin_retention_dashboard", source)

        for name in PUBLIC_FEATURE_NAMES:
            self.assertIn(f"'{name}'", source)

    def test_frontend_helper_loads_before_gated_code(self):
        """A primeira experiência gated (sheet "Li mais", L2/EPIC 2) exige o
        helper carregado antes do app.js — fail-closed continua garantido
        pelo próprio helper quando /api/features falha."""
        index = (ROOT / "index.html").read_text(encoding="utf-8")
        self.assertIn("/static/feature-flags.js", index)
        self.assertLess(index.index("/static/feature-flags.js"), index.index("/static/app.js"))


if __name__ == "__main__":
    import unittest

    unittest.main()
