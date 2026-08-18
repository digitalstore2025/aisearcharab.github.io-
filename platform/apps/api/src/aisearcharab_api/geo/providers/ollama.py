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


class OllamaProviderError(RuntimeError):
    """Raised when the local Ollama runtime returns an invalid or failed response."""


@dataclass(frozen=True, slots=True)
class OllamaProvider:
    """Minimal, self-hosted Ollama provider using only the Python standard library.

    The endpoint is configuration-controlled rather than user-controlled. By default
    it may only target the local Docker service or loopback interfaces so this
    adapter cannot become a generic SSRF primitive.
    """

    model: str
    base_url: str = "http://ollama:11434"
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS
    allowed_hosts: frozenset[str] = DEFAULT_ALLOWED_HOSTS
    name: str = "ollama"

    def __post_init__(self) -> None:
        if not self.model.strip():
            raise ValueError("Ollama model must be non-empty")
        if not 1 <= self.timeout_seconds <= 600:
            raise ValueError("Ollama timeout_seconds must be between 1 and 600")

        parsed = urlparse(self.base_url)
        if parsed.scheme not in {"http", "https"}:
            raise ValueError("Ollama base_url must use http or https")
        if not parsed.hostname or parsed.hostname not in self.allowed_hosts:
            raise ValueError("Ollama base_url host is not allowlisted")
        if parsed.username is not None or parsed.password is not None:
            raise ValueError("Ollama base_url credentials are forbidden")
        if parsed.path not in {"", "/"} or parsed.params or parsed.query or parsed.fragment:
            raise ValueError("Ollama base_url must not include a path, query, or fragment")

    def capabilities(self) -> tuple[str, ...]:
        return ("local-inference", "open-source-runtime", "no-native-citations")

    def run_query(self, query: str, *, locale: str = "ar") -> ProviderResult:
        normalized_query = query.strip()
        if not normalized_query:
            raise ValueError("query must be non-empty")
        if locale not in {"ar", "en", "tr"}:
            raise ValueError("locale must be ar, en, or tr")

        body = json.dumps(
            {
                "model": self.model.strip(),
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "Answer the user query directly. Preserve the requested language. "
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
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:  # noqa: S310 -- host is allowlisted above
                raw_bytes = response.read(MAX_RESPONSE_BYTES + 1)
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError) as exc:
            raise OllamaProviderError("Ollama request failed") from exc

        latency_ms = max(0, round((time.monotonic() - started) * 1000))
        if len(raw_bytes) > MAX_RESPONSE_BYTES:
            raise OllamaProviderError("Ollama response exceeds size limit")

        try:
            payload = json.loads(raw_bytes.decode("utf-8"))
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

        raw_payload = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
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
