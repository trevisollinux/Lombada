"""Testes do paralelismo limitado na hidratação de páginas de livro."""
import os
import sys
import threading
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import sync_publishers as sp  # noqa: E402


def extracted(url):
    normalized = {
        "title": url.rsplit("/", 1)[-1],
        "author": "Autor",
        "isbn": "",
        "permalink": url,
    }
    return normalized, {"url": url}


class BoundedParallelFetchTest(unittest.TestCase):
    def test_uses_bounded_concurrency_and_preserves_order(self):
        lock = threading.Lock()
        active = 0
        max_active = 0

        def fake_extract(url, publisher):
            nonlocal active, max_active
            with lock:
                active += 1
                max_active = max(max_active, active)
            time.sleep(0.04)
            with lock:
                active -= 1
            return extracted(url)

        urls = [f"https://example.test/livro/{n}" for n in range(8)]
        with patch.dict(os.environ, {"PUBLISHER_FETCH_CONCURRENCY": "4"}), patch.object(
            sp, "extract_page", side_effect=fake_extract
        ):
            records = sp._collect_from_urls(
                urls, {"slug": "teste"}, max_urls=8, sleep_seconds=0
            )

        self.assertEqual([item[0]["permalink"] for item in records], urls)
        self.assertGreaterEqual(max_active, 2)
        self.assertLessEqual(max_active, 4)

    def test_stops_after_first_successful_batch(self):
        calls = []

        def fake_extract(url, publisher):
            calls.append(url)
            return extracted(url)

        urls = [f"https://example.test/livro/{n}" for n in range(12)]
        with patch.dict(os.environ, {"PUBLISHER_FETCH_CONCURRENCY": "4"}), patch.object(
            sp, "extract_page", side_effect=fake_extract
        ):
            records = sp._collect_from_urls(
                urls, {"slug": "teste"}, max_urls=2, sleep_seconds=0
            )

        self.assertEqual(len(records), 2)
        self.assertEqual(len(calls), 4)

    def test_skips_seen_and_duplicate_urls_before_scheduling(self):
        calls = []
        urls = [
            "https://example.test/livro/1",
            "https://example.test/livro/1",
            "https://example.test/livro/2",
        ]
        seen = {sp.stable_external_id(urls[0])}

        with patch.dict(os.environ, {"PUBLISHER_FETCH_CONCURRENCY": "4"}), patch.object(
            sp, "extract_page", side_effect=lambda url, publisher: calls.append(url) or extracted(url)
        ):
            records = sp._collect_from_urls(
                urls,
                {"slug": "teste"},
                max_urls=2,
                sleep_seconds=0,
                seen=seen,
            )

        self.assertEqual(calls, ["https://example.test/livro/2"])
        self.assertEqual(len(records), 1)

    def test_concurrency_setting_is_clamped(self):
        with patch.dict(os.environ, {"PUBLISHER_FETCH_CONCURRENCY": "99"}):
            self.assertEqual(sp.fetch_concurrency(), 8)
        with patch.dict(os.environ, {"PUBLISHER_FETCH_CONCURRENCY": "0"}):
            self.assertEqual(sp.fetch_concurrency(), 1)
        with patch.dict(os.environ, {"PUBLISHER_FETCH_CONCURRENCY": "invalido"}):
            self.assertEqual(sp.fetch_concurrency(), 4)


if __name__ == "__main__":
    unittest.main()
