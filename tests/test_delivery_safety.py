"""Contratos mínimos de segurança para mudanças no Lombada.

Estes testes são intencionalmente estáticos: não duplicam o TestClient e o banco
já usados em ``test_smoke.py``. Eles protegem os pontos necessários para verificar
e reverter um deploy e impedem DDL destrutivo no mecanismo de migração do boot.
"""
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]


class DeliverySafetyContractTest(unittest.TestCase):
    def _read(self, relative_path: str) -> str:
        return (ROOT / relative_path).read_text(encoding="utf-8")

    def test_health_readiness_and_version_routes_remain_available(self):
        source = self._read("main.py")
        for route in ("/healthz", "/readyz", "/api/version"):
            self.assertIn(f'@app.get("{route}")', source)

    def test_pwa_release_contract_remains_declared(self):
        index = self._read("index.html")
        self.assertIn('rel="manifest"', index)
        self.assertIn('/static/app.js?v={{APP_VERSION}}', index)
        self.assertIn('/static/app.css?v={{APP_VERSION}}', index)
        self.assertTrue((ROOT / "manifest.json").exists())
        self.assertTrue((ROOT / "sw.js").exists())

    def test_boot_migration_contains_no_destructive_ddl(self):
        source = self._read("models.py")
        match = re.search(r"\ndef migrar\(\):(?P<body>.*)\Z", source, flags=re.DOTALL)
        self.assertIsNotNone(match, "models.py deve continuar declarando migrar()")
        body = match.group("body").lower()
        forbidden = ("drop table", "truncate table", "drop column")
        for statement in forbidden:
            self.assertNotIn(statement, body, f"DDL destrutivo proibido em migrar(): {statement}")

    def test_delivery_documentation_and_pr_template_exist(self):
        for relative_path in (
            "docs/MIGRATIONS.md",
            "docs/ROLLBACK.md",
            "docs/SMOKE_TESTS.md",
            ".github/pull_request_template.md",
        ):
            self.assertTrue((ROOT / relative_path).exists(), relative_path)


if __name__ == "__main__":
    unittest.main()
