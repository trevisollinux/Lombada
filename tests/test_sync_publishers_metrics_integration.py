"""Testes da integração do estado operacional no loop dos scrapers."""
import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import sync_publishers as sp  # noqa: E402


class FakeConnection:
    def __init__(self):
        self.closed = 0

    def close(self):
        self.closed = 1


PUBLISHER = {
    "slug": "todavia",
    "name": "Todavia",
    "base_url": "https://todavialivros.com.br",
    "platforms": ["sitemap", "html"],
}


def record():
    return ({
        "title": "Livro",
        "author": "Autora",
        "isbn": "9788535947847",
    }, {"raw": True})


class SyncMetricsHelpersTest(unittest.TestCase):
    def test_platform_label_preserves_fallback_order(self):
        self.assertEqual(
            sp.publisher_platform_label(PUBLISHER),
            "sitemap -> html",
        )
        self.assertEqual(
            sp.publisher_platform_label({"platform": "shopify"}),
            "shopify",
        )

    def test_status_is_partial_when_any_fetch_failure_was_recorded(self):
        self.assertEqual(sp.sync_state_status({}), "success")
        self.assertEqual(
            sp.sync_state_status({"status:503": 2}),
            "partial",
        )


class SyncMetricsMainTest(unittest.TestCase):
    def base_patches(self, conn):
        return (
            patch.dict(os.environ, {
                "DATABASE_URL": "postgresql://test",
                "PUBLISHER_SLUGS": "todavia",
                "PUBLISHER_MAX_URLS": "5",
                "PUBLISHER_SLEEP_SECONDS": "0",
                "PUBLISHER_DRY_RUN": "false",
            }, clear=False),
            patch.object(sp, "select_sources", return_value=[PUBLISHER]),
            patch.object(sp, "connect_database", return_value=conn),
            patch.object(sp, "ensure_connection", side_effect=lambda value: value),
            patch.object(sp, "ensure_source_records"),
            patch.object(sp, "ensure_publisher_dead_ids"),
            patch.object(sp, "ensure_publisher_sync_state"),
            patch.object(sp, "load_seen_external_ids", return_value=set()),
            patch.object(sp, "load_dead_external_ids", return_value=set()),
        )

    def test_success_records_counts_and_duration(self):
        conn = FakeConnection()
        patches = self.base_patches(conn)
        with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6], patches[7], patches[8], patch.object(
            sp, "collect_publisher", return_value=[record()]
        ), patch.object(sp, "upsert_records", return_value=1), patch.object(
            sp, "mark_sync_started"
        ) as started, patch.object(sp, "mark_sync_finished") as finished, patch.object(
            sp, "mark_sync_failed"
        ) as failed:
            result = sp.main()

        self.assertEqual(result, 0)
        started.assert_called_once()
        finished.assert_called_once()
        failed.assert_not_called()
        kwargs = finished.call_args.kwargs
        self.assertEqual(kwargs["status"], "success")
        self.assertEqual(kwargs["records_collected"], 1)
        self.assertEqual(kwargs["records_written"], 1)
        self.assertEqual(kwargs["isbn_count"], 1)
        self.assertEqual(kwargs["author_count"], 1)
        self.assertGreaterEqual(kwargs["duration_ms"], 0)

    def test_failure_marks_source_failed_and_continues_to_summary(self):
        conn = FakeConnection()
        patches = self.base_patches(conn)
        with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6], patches[7], patches[8], patch.object(
            sp, "collect_publisher", side_effect=RuntimeError("site indisponível")
        ), patch.object(sp, "mark_sync_started"), patch.object(
            sp, "mark_sync_finished"
        ) as finished, patch.object(sp, "mark_sync_failed") as failed:
            result = sp.main()

        self.assertEqual(result, 1)
        finished.assert_not_called()
        failed.assert_called_once()
        self.assertEqual(
            str(failed.call_args.kwargs["error"]),
            "site indisponível",
        )


if __name__ == "__main__":
    unittest.main()
