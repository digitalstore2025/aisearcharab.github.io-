from __future__ import annotations

from collections.abc import Iterator

import httpx2


class ResponseTooLargeError(httpx2.TransportError):
    """Raised before a provider response larger than the configured cap is buffered."""


class _LimitedSyncByteStream(httpx2.SyncByteStream):
    def __init__(self, response: httpx2.Response, max_response_bytes: int) -> None:
        self._response = response
        self._max_response_bytes = max_response_bytes

    def __iter__(self) -> Iterator[bytes]:
        total_bytes = 0
        try:
            for chunk in self._response.stream:
                total_bytes += len(chunk)
                if total_bytes > self._max_response_bytes:
                    raise ResponseTooLargeError(
                        f"provider response exceeded {self._max_response_bytes} bytes"
                    )
                yield chunk
        finally:
            self._response.close()

    def close(self) -> None:
        self._response.close()


class ResponseSizeLimitTransport(httpx2.BaseTransport):
    """Reject oversized responses before the OpenAI SDK reads them into memory."""

    def __init__(
        self,
        max_response_bytes: int,
        *,
        transport: httpx2.BaseTransport | None = None,
    ) -> None:
        if max_response_bytes <= 0:
            raise ValueError("max_response_bytes must be positive")
        self._max_response_bytes = max_response_bytes
        self._transport = transport or httpx2.HTTPTransport(trust_env=False)

    def handle_request(self, request: httpx2.Request) -> httpx2.Response:
        response = self._transport.handle_request(request)
        try:
            content_encoding = response.headers.get("content-encoding", "identity").strip().lower()
            if content_encoding not in {"", "identity"}:
                raise ResponseTooLargeError("compressed provider responses are not accepted")

            content_length = response.headers.get("content-length")
            if content_length is not None:
                try:
                    declared_length = int(content_length)
                except ValueError as exc:
                    raise ResponseTooLargeError("provider returned an invalid Content-Length") from exc
                if declared_length < 0 or declared_length > self._max_response_bytes:
                    raise ResponseTooLargeError(
                        f"provider response declared more than {self._max_response_bytes} bytes"
                    )

            return httpx2.Response(
                status_code=response.status_code,
                headers=response.headers,
                stream=_LimitedSyncByteStream(response, self._max_response_bytes),
                request=request,
                extensions=response.extensions,
            )
        except Exception:
            response.close()
            raise

    def close(self) -> None:
        self._transport.close()

