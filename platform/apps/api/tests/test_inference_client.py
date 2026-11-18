from __future__ import annotations

from collections.abc import Iterator

import httpx2
import pytest

from aisearcharab_api.inference_client import ResponseSizeLimitTransport, ResponseTooLargeError


class ChunkStream(httpx2.SyncByteStream):
    def __init__(self, chunks: list[bytes]) -> None:
        self.chunks = chunks
        self.iterated = False
        self.closed = False

    def __iter__(self) -> Iterator[bytes]:
        self.iterated = True
        yield from self.chunks

    def close(self) -> None:
        self.closed = True


def _client_for(stream: ChunkStream, headers: dict[str, str], limit: int = 8) -> httpx2.Client:
    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(200, headers=headers, stream=stream, request=request)

    return httpx2.Client(
        transport=ResponseSizeLimitTransport(limit, transport=httpx2.MockTransport(handler)),
        follow_redirects=False,
    )


def test_content_length_limit_rejects_before_reading_body() -> None:
    stream = ChunkStream([b"123456789"])
    client = _client_for(stream, {"Content-Length": "9"})

    with client, pytest.raises(ResponseTooLargeError, match="declared more than 8 bytes"):
        client.get("https://gateway.example/v1/responses")

    assert stream.iterated is False
    assert stream.closed is True


def test_chunked_body_is_counted_while_streaming() -> None:
    stream = ChunkStream([b"1234", b"56789"])
    client = _client_for(stream, {"Transfer-Encoding": "chunked"})

    with client, pytest.raises(ResponseTooLargeError, match="exceeded 8 bytes"):
        client.get("https://gateway.example/v1/responses")

    assert stream.iterated is True
    assert stream.closed is True


def test_compressed_provider_body_is_rejected() -> None:
    stream = ChunkStream([b"compressed"])
    client = _client_for(stream, {"Content-Encoding": "gzip", "Content-Length": "10"})

    with client, pytest.raises(ResponseTooLargeError, match="compressed provider responses"):
        client.get("https://gateway.example/v1/responses")

    assert stream.iterated is False
    assert stream.closed is True


def test_response_under_limit_is_read_normally() -> None:
    stream = ChunkStream([b"abc", b"defg"])
    client = _client_for(stream, {"Content-Length": "7"})

    with client:
        response = client.get("https://gateway.example/v1/responses")

    assert response.content == b"abcdefg"
    assert stream.closed is True


@pytest.mark.parametrize("content_length", ["-1", "not-a-number"])
def test_invalid_content_length_is_rejected(content_length: str) -> None:
    stream = ChunkStream([b"x"])
    client = _client_for(stream, {"Content-Length": content_length})

    with client, pytest.raises(ResponseTooLargeError):
        client.get("https://gateway.example/v1/responses")

    assert stream.iterated is False
    assert stream.closed is True
