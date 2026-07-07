import os
import tempfile
import unittest
from unittest.mock import patch

_DB_FD, _DB_PATH = tempfile.mkstemp(suffix=".db")
os.close(_DB_FD)
os.environ["DATABASE_URL"] = f"sqlite:///{_DB_PATH}"
os.environ.setdefault("COOKIE_SECURE", "false")
os.environ.setdefault("SECRET_KEY", "cover-proxy-test-secret")

from fastapi import HTTPException  # noqa: E402

import main  # noqa: E402


class FakeStream:
    def __init__(self, status_code=200, headers=None, chunks=None):
        self.status_code = status_code
        self.headers = headers or {}
        self._chunks = chunks or []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def aiter_bytes(self, chunk_size):
        for chunk in self._chunks:
            yield chunk


class FakeClient:
    stream_response = None

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    def stream(self, method, url):
        return self.stream_response


class CoverProxyTest(unittest.IsolatedAsyncioTestCase):
    async def asyncTearDown(self):
        try:
            os.remove(_DB_PATH)
        except OSError:
            pass

    async def _proxy(self, stream):
        FakeClient.stream_response = stream
        with patch.object(main, "_host_publico", return_value=True), patch.object(main.httpx, "AsyncClient", FakeClient):
            return await main.proxy_capa("https://covers.example/book.jpg")

    async def test_accepts_common_content_type_with_parameters(self):
        response = await self._proxy(FakeStream(headers={"content-type": "image/jpeg; charset=binary"}, chunks=[b"abc"]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.media_type, "image/jpeg")
        self.assertEqual(response.body, b"abc")
        self.assertIn("stale-while-revalidate=604800", response.headers["Cache-Control"])

    async def test_rejects_invalid_content_type(self):
        with self.assertRaises(HTTPException) as ctx:
            await self._proxy(FakeStream(headers={"content-type": "text/html"}, chunks=[b"nope"]))
        self.assertEqual(ctx.exception.status_code, 415)

    async def test_rejects_large_content_length_before_download(self):
        with self.assertRaises(HTTPException) as ctx:
            await self._proxy(FakeStream(headers={"content-type": "image/png", "content-length": str(main.CAPA_MAX_BYTES + 1)}, chunks=[]))
        self.assertEqual(ctx.exception.status_code, 413)

    async def test_rejects_stream_that_exceeds_limit(self):
        with self.assertRaises(HTTPException) as ctx:
            await self._proxy(FakeStream(headers={"content-type": "image/webp"}, chunks=[b"x" * (main.CAPA_MAX_BYTES + 1)]))
        self.assertEqual(ctx.exception.status_code, 413)

    async def test_upstream_error_status_returns_502(self):
        with self.assertRaises(HTTPException) as ctx:
            await self._proxy(FakeStream(status_code=404, headers={"content-type": "image/jpeg"}, chunks=[]))
        self.assertEqual(ctx.exception.status_code, 502)


if __name__ == "__main__":
    unittest.main()
