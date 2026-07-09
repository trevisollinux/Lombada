"""
Testes das funções puras de scripts/promote_source_records.py.

promote_source_records.py exige Postgres real (connect() recusa qualquer
outro esquema), então backfill_source_record_authors() é testada com uma
conexão/cursor fake (duck typing) em vez de subir um banco de verdade —
só a lógica em Python (extração + guarda de dry_run) precisa de cobertura,
o SQL em si roda contra Postgres de produção via GitHub Actions.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import promote_source_records as psr  # noqa: E402


class FakeCursor:
    def __init__(self, select_result):
        self._select_result = select_result
        self.executed = []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=None):
        self.executed.append((" ".join(sql.split()), params))

    def fetchall(self):
        return self._select_result


class FakeConn:
    def __init__(self, select_result):
        self._cursor = FakeCursor(select_result)
        self.committed = False

    def cursor(self):
        return self._cursor

    def commit(self):
        self.committed = True


class ExtractAuthorFromTextTest(unittest.TestCase):
    def test_extracts_author_after_label(self):
        self.assertEqual(psr.extract_author_from_text("Autor: Graciliano Ramos | 176 págs"), "Graciliano Ramos")

    def test_no_label_returns_empty(self):
        self.assertEqual(psr.extract_author_from_text("sem menção a autoria"), "")


class BackfillSourceRecordAuthorsTest(unittest.TestCase):
    def test_updates_and_commits_when_not_dry_run(self):
        conn = FakeConn([(1, "Poemas reunidos. Autor: Manoel de Barros | ISBN 9788535900000"), (2, "sem pista nenhuma")])
        count = psr.backfill_source_record_authors(conn, dry_run=False)
        self.assertEqual(count, 1)
        updates = [call for call in conn.cursor().executed if call[0].startswith("UPDATE")]
        self.assertEqual(len(updates), 1)
        self.assertEqual(updates[0][1], ("Manoel de Barros", 1))
        self.assertTrue(conn.committed)

    def test_dry_run_counts_but_does_not_write(self):
        conn = FakeConn([(1, "Autor: Clarice Lispector")])
        count = psr.backfill_source_record_authors(conn, dry_run=True)
        self.assertEqual(count, 1)
        updates = [call for call in conn.cursor().executed if call[0].startswith("UPDATE")]
        self.assertEqual(updates, [])
        self.assertFalse(conn.committed)

    def test_empty_description_yields_zero(self):
        conn = FakeConn([(1, None), (2, "")])
        count = psr.backfill_source_record_authors(conn, dry_run=False)
        self.assertEqual(count, 0)
        self.assertTrue(conn.committed)  # commit acontece mesmo sem updates, é barato e idempotente


class PromoteInsertDefaultsTest(unittest.TestCase):
    class Cursor:
        def __init__(self):
            self.executed = []
            self.rowcount = 0
            self._last_sql = ""

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def execute(self, sql, params=None):
            self._last_sql = " ".join(sql.split())
            self.executed.append((self._last_sql, params))
            self.rowcount = 0

        def fetchone(self):
            if "information_schema.columns" in self._last_sql:
                return (1,)
            if self._last_sql.startswith("SELECT id, obra_id FROM edicao"):
                return None
            if self._last_sql.startswith("SELECT id FROM obra"):
                return None
            if self._last_sql.startswith("INSERT INTO obra"):
                return (42,)
            return None

    class Conn:
        def __init__(self):
            self.cur = PromoteInsertDefaultsTest.Cursor()
            self.committed = False

        def cursor(self):
            return self.cur

        def commit(self):
            self.committed = True

    def test_new_obra_insert_includes_required_text_defaults_and_description(self):
        conn = self.Conn()
        rows = [(7, "A sociedade desigual", "Mario Theodoro", "9786555252279", "Editora 34", 2025, "", "x" * 2505)]

        stats = psr.promote(conn, rows, dry_run=False)

        obra_insert = next(call for call in conn.cur.executed if call[0].startswith("INSERT INTO obra"))
        self.assertIn("descricao", obra_insert[0])
        self.assertIn("generos_json", obra_insert[0])
        self.assertEqual(len(obra_insert[1][5]), 2000)
        self.assertEqual(obra_insert[1][6:], ("", "", "", "", ""))
        self.assertEqual(stats["obras_criadas"], 1)
        self.assertEqual(stats["promovidos"], 1)
        self.assertTrue(conn.committed)


class SafeDescricaoTest(unittest.TestCase):
    def test_uses_empty_string_for_missing_description(self):
        self.assertEqual(psr._safe_descricao(None), "")
        self.assertEqual(psr._safe_descricao(""), "")

    def test_trims_and_limits_description_to_2000_chars(self):
        self.assertEqual(psr._safe_descricao("  resumo  "), "resumo")
        self.assertEqual(len(psr._safe_descricao("x" * 2500)), 2000)


if __name__ == "__main__":
    unittest.main()
