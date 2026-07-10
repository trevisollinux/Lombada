"""Testes do lote de persistência dos registros coletados."""
import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import sync_publishers as sp  # noqa: E402


class FakeCursor:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False


class FakeConnection:
    def __init__(self):
        self.cursor_calls = 0
        self.commit_calls = 0

    def cursor(self):
        self.cursor_calls += 1
        return FakeCursor()

    def commit(self):
        self.commit_calls += 1


def record(external_id, title):
    normalized = {
        "source": "publisher:teste",
        "external_id": external_id,
        "status": "pending",
        "title": title,
        "author": "Autor",
        "isbn": "9788535947847",
        "publisher": "Editora Teste",
        "publication_year": 2026,
        "price": None,
        "currency_id": "BRL",
        "permalink": f"https://example.test/{external_id}",
        "thumbnail": "",
        "category_id": "",
        "search_term": "",
        "confidence_score": 0.9,
    }
    raw = {"id": external_id, "name": title}
    return normalized, raw


class UpsertRecordsBatchTest(unittest.TestCase):
    def test_writes_all_records_in_one_batch_and_one_commit(self):
        conn = FakeConnection()
        records = [record("1", "Livro 1"), record("2", "Livro 2")]
        captured = {}

        def fake_execute_batch(cursor, sql, params, page_size):
            captured["cursor"] = cursor
            captured["sql"] = sql
            captured["params"] = params
            captured["page_size"] = page_size

        with patch.object(sp, "execute_batch", side_effect=fake_execute_batch) as batch:
            written = sp.upsert_records(conn, records)

        self.assertEqual(written, 2)
        self.assertEqual(conn.cursor_calls, 1)
        self.assertEqual(conn.commit_calls, 1)
        batch.assert_called_once()
        self.assertEqual(captured["page_size"], 250)
        self.assertEqual(len(captured["params"]), 2)
        self.assertIn("ON CONFLICT (source, external_id)", captured["sql"])
        self.assertIn("status = 'pending'", captured["sql"])
        self.assertEqual(captured["params"][0]["external_id"], "1")
        self.assertEqual(
            captured["params"][0]["normalized_json"].adapted,
            records[0][0],
        )
        self.assertEqual(
            captured["params"][0]["raw_json"].adapted,
            records[0][1],
        )

    def test_empty_batch_does_not_open_transaction(self):
        conn = FakeConnection()

        with patch.object(sp, "execute_batch") as batch:
            written = sp.upsert_records(conn, [])

        self.assertEqual(written, 0)
        self.assertEqual(conn.cursor_calls, 0)
        self.assertEqual(conn.commit_calls, 0)
        batch.assert_not_called()


if __name__ == "__main__":
    unittest.main()
