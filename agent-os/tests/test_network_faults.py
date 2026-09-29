import io
import json
import sys
import unittest
from pathlib import Path
from urllib.error import HTTPError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agent_os.network_faults import ToxiproxyClient, ToxiproxyError


class _Response:
    def __init__(self, payload=None):
        self.payload = b"" if payload is None else json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return self.payload


class _Opener:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    def __call__(self, request, timeout):
        self.requests.append((request, timeout))
        response = self.responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        return _Response(response)


class TestToxiproxyClient(unittest.TestCase):
    def test_rejects_non_loopback_control_plane(self):
        for url in (
            "https://127.0.0.1:8474",
            "http://example.com:8474",
            "http://user:pass@127.0.0.1:8474",
            "http://127.0.0.1:8474?x=1",
        ):
            with self.subTest(url=url):
                with self.assertRaises(ValueError):
                    ToxiproxyClient(url)

    def test_version_parses_expected_shape(self):
        opener = _Opener([{"version": "2.12.0"}])
        client = ToxiproxyClient(opener=opener)
        self.assertEqual(client.version(), "2.12.0")
        request, timeout = opener.requests[0]
        self.assertEqual(request.full_url, "http://127.0.0.1:8474/version")
        self.assertEqual(timeout, 2.0)

    def test_create_proxy_is_json_post(self):
        opener = _Opener([{"name": "p", "listen": "127.0.0.1:1234"}])
        client = ToxiproxyClient(opener=opener)
        result = client.create_proxy("p", "127.0.0.1:0", "127.0.0.1:9999")
        self.assertEqual(result["name"], "p")
        request, _ = opener.requests[0]
        self.assertEqual(request.method, "POST")
        payload = json.loads(request.data.decode("utf-8"))
        self.assertEqual(payload["upstream"], "127.0.0.1:9999")
        self.assertTrue(payload["enabled"])

    def test_add_toxic_validates_stream(self):
        client = ToxiproxyClient(opener=_Opener([]))
        with self.assertRaises(ValueError):
            client.add_toxic("p", name="x", toxic_type="latency", stream="sideways")

    def test_not_found_delete_is_idempotent(self):
        error = HTTPError(
            "http://127.0.0.1:8474/proxies/missing",
            404,
            "missing",
            {},
            io.BytesIO(b""),
        )
        client = ToxiproxyClient(opener=_Opener([error]))
        client.delete_proxy("missing")

    def test_unexpected_http_error_is_wrapped_without_body(self):
        secret_body = io.BytesIO(b'{"error":"credential=SECRET"}')
        error = HTTPError(
            "http://127.0.0.1:8474/version",
            500,
            "boom",
            {},
            secret_body,
        )
        client = ToxiproxyClient(opener=_Opener([error]))
        with self.assertRaisesRegex(ToxiproxyError, "HTTP 500") as caught:
            client.version()
        self.assertNotIn("SECRET", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
