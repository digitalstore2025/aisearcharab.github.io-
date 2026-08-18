from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from urllib.parse import urlparse

from .base import ProviderResult

DEFAULT_TIMEOUT_SECONDS = 120.0
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
DEFAULT_ALLOWED_HOSTS = frozenset({"ollama", "localhost", "127.0.0.1"})
DEFAULT_ALLOWED_PORTS = frozenset({11434})
_LOCALE_NAMES = {"ar": "Arabic", "en": "English", "tr": "Turkish"}


class OllamaProviderError(RuntimeError):
    """Raised when the local Ollama runtime returns an invalid or failed response."""


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Reject redirects so an allowlisted Ollama endpoint cannot pivot to another target."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001, ANN201 - urllib override
        raise urllib.error.HTTPError(newurl, code, "Ollama redirects are forbidden", headers, fp)


def _open_no_redirect(request: urllib.request.Request, *, timeout: float):
    opener = urllib.request.build_opener(_NoRedirectHandler())
    return opener.open(request, timeout=timeout)


@dataclass(frozen=True, slots=True)
class OllamaProvider:
    """Minimal, self-hosted Ollama provider using only the Python standard library.

    The endpoint is configuration-controlled rather than user-controlled. By default
    it may only target the local Docker service or loopback interfaces on Ollama's
    expected port. Redirects are rejected so this adapter cannot be used to pivot
    from an allowlisted local endpoint to an arbitrary network destination.
    """

    model: str
    base_url: str = "http://ollama:11434"
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS
    allowed_hosts: frozenset[str] = DEFAULT_ALLOWED_HOSTS
    allowed_ports: frozenset[int] = DEFAULT_ALLOWED_PORTS
    name: str = "ollama"

    def __post_init__(self) -> None:
        if not isinstance(self.model, str) or not self.model.strip():
            raise ValueError("Ollama model must be non-empty")
        if not isinstance(self.timeout_seconds, (int, float)) or isinstance(self.timeout_seconds, bool):
            raise ValueError("Ollama timeout_seconds must be numeric")
        if not 1 <= self.timeout_seconds <= 600:
            raise ValueError("Ollama timeout_seconds must be between 1 and 600")

        parsed = urlparse(self.base_url)
        if parsed.scheme not in {"http", "https"}:
            raise ValueError("Ollama base_url must use http or https")
        if not parsed.hostname or parsed.hostname not in self.allowed_hosts:
            raise ValueError("Ollama base_url host is not allowlisted")
        try:
            port = parsed.port
        except ValueError as exc:
            raise ValueError("Ollama base_url contains an invalid port") from exc
        if port is None or port not in self.allowed_ports:
            raise ValueError("Ollama base_url port is not allowlisted")
        if parsed.username is not None or parsed.password is not None:
            raise ValueError("Ollama base_url credentials are forbidden")
        if parsed.path not in {"", "/"} or parsed.params or parsed.query or parsed.fragment:
            raise ValueError("Ollama base_url must not include a path, query, or fragment")

    def capabilities(self) -> tuple[str, ...]:
        return ("local-inference", "open-source-runtime", "no-native-citations")

    def run_query(self, query: str, *, locale: str = "ar") -> ProviderResult:
        if not isinstance(query, str):
            raise ValueError("query must be a string")
        normalized_query = query.strip()
        if not normalized_query:
            raise ValueError("query must be non-empty")
        if locale not in _LOCALE_NAMES:
            raise ValueError("locale must be ar, en, or tr")
        response_language = _LOCALE_NAMES[locale]

        body = json.dumps(
            {
                "model": self.model.strip(),
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            f"Answer the user query in {response_language} ({locale}). "
                            "Do not invent citations, URLs, or sources that were not supplied to you."
                        ),
                    },
                    {"role": "user", "content": normalized_query},
                ],
                "stream": False,
            },
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")

        request = urllib.request.Request(
            f"{self.base_url.rstrip('/')}/api/chat",
            data=body,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            method="POST",
        )

        started = time.monotonic()
        try:
            with _open_no_redirect(request, timeout=float(self.timeout_seconds)) as response:
                raw_bytes = response.read(MAX_RESPONSE_BYTES + 1)
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError) as exc:
            raise OllamaProviderError("Ollama request failed") from exc

        latency_ms = max(0, round((time.monotonic() - started) * 1000))
        if len(raw_bytes) > MAX_RESPONSE_BYTES:
            raise OllamaProviderError("Ollama response exceeds size limit")

        try:
            raw_payload = raw_bytes.decode("utf-8")
            payload = json.loads(raw_payload)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise OllamaProviderError("Ollama returned invalid JSON") from exc

        if not isinstance(payload, dict):
            raise OllamaProviderError("Ollama response must be a JSON object")
        message = payload.get("message")
        if not isinstance(message, dict):
            raise OllamaProviderError("Ollama response is missing message")
        answer_text = message.get("content")
        if not isinstance(answer_text, str):
            raise OllamaProviderError("Ollama response message content must be a string")
        returned_model = payload.get("model")
        if not isinstance(returned_model, str) or not returned_model.strip():
            returned_model = self.model.strip()

        return ProviderResult(
            provider=self.name,
            model=returned_model,
            query=normalized_query,
            answer_text=answer_text,
            citations=(),
            mentions=(),
            raw_payload=raw_payload,
            latency_ms=latency_ms,
        )
