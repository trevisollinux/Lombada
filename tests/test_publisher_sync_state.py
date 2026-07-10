"""Testes da persistência resumida das execuções dos scrapers."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import init_ingestion_tables as tables  # noqa: E402
import publisher_sync_state as state  # noqa: E402


class FakeCursor:
    def __init__(self, rowcount=1):
        self.rowcount = rowcount
        self.executions = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def execute(self, sql, params=None):
        self.executions.append((sql, params))


class FakeConnection:
    def __init__(self, rowcount=1):
        self.fake_cursor = FakeCursor(rowcount=rowcount)
        self.commit_calls = 0
        self.rollback_calls = 0

    def cursor(self):
        return self.fake_cursor

    def commit(self):
        self.commit_calls += 1

    def rollback(self):
        self.rollback_calls += 1


class PublisherSyncStateSchemaTest(unittest.TestCase):
    def test_schema_has_primary_key_metrics_and_status_constraint(self):
        sql = tables.PUBLISHER_SYNC_STATE_SQL

        self.assertIn("source text PRIMARY KEY", sql)
        self.assertIn("duration_ms bigint", sql)
        self.assertIn("records_collected integer", sql)
        self.assertIn("request_failures jsonb", sql)
        self.assertIn("CHECK (status IN", sql)
        self.assertIn("'running'", sql)
        self.assertIn("'failed'", sql)


class PublisherSyncStateWriteTest(unittest.TestCase):
    def test_mark_started_resets_previous_attempt_and_commits(self):
        conn = FakeConnection()

        state.mark_sync_started(
            conn,
            " publisher:todavia ",
            platform=" sitemap ",
            metadata={"workflow": "principal"},
        )

        sql, params = conn.fake_cursor.executions[0]
        self.assertIn("ON CONFLICT (source) DO UPDATE", sql)
        self.assertIn("status = 'running'", sql)
        self.assertEqual(params["source"], "publisher:todavia")
        self.assertEqual(params["platform"], "sitemap")
        self.assertEqual(params["metadata"].adapted, {"workflow": "principal"})
        self.assertEqual(conn.commit_calls, 1)

    def test_mark_finished_normalizes_counts_and_error_message(self):
        conn = FakeConnection(rowcount=1)
        long_error = " erro " * 600

        state.mark_sync_finished(
            conn,
            "publisher:todavia",
            status="partial",
            duration_ms=-20,
            records_collected=5,
            records_written=-1,
            isbn_count=4,
            author_count=3,
            request_failures={"status:503": 2},
            error_message=long_error,
            metadata={"collector": "sitemap"},
        )

        sql, params = conn.fake_cursor.executions[0]
        self.assertIn("metadata = metadata ||", sql)
        self.assertEqual(params["duration_ms"], 0)
        self.assertEqual(params["records_collected"], 5)
        self.assertEqual(params["records_written"], 0)
        self.assertEqual(params["request_failures"].adapted, {"status:503": 2})
        self.assertLessEqual(len(params["error_message"]), 2000)
        self.assertEqual(conn.commit_calls, 1)
        self.assertEqual(conn.rollback_calls, 0)

    def test_mark_finished_rejects_invalid_status(self):
        with self.assertRaisesRegex(ValueError, "status inválido"):
            state.mark_sync_finished(
                FakeConnection(),
                "publisher:todavia",
                status="running",
                duration_ms=10,
            )

    def test_mark_finished_rolls_back_when_start_row_is_missing(self):
        conn = FakeConnection(rowcount=0)

        with self.assertRaisesRegex(RuntimeError, "mark_sync_started"):
            state.mark_sync_finished(
                conn,
                "publisher:inexistente",
                status="failed",
                duration_ms=10,
            )

        self.assertEqual(conn.rollback_calls, 1)
        self.assertEqual(conn.commit_calls, 0)

    def test_mark_failed_delegates_with_normalized_error(self):
        conn = FakeConnection(rowcount=1)

        state.mark_sync_failed(
            conn,
            "publisher:todavia",
            duration_ms=123,
            error=RuntimeError("site indisponível"),
        )

        _, params = conn.fake_cursor.executions[0]
        self.assertEqual(params["status"], "failed")
        self.assertEqual(params["error_message"], "site indisponível")


if __name__ == "__main__":
    unittest.main()
