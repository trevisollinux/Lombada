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


if __name__ == "__main__":
    unittest.main()
