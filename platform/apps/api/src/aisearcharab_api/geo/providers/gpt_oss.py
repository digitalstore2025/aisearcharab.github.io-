from __future__ import annotations

from dataclasses import dataclass

from .ollama import OllamaProvider

GPT_OSS_20B = "gpt-oss:20b"
GPT_OSS_120B = "gpt-oss:120b"
SUPPORTED_GPT_OSS_MODELS = frozenset({GPT_OSS_20B, GPT_OSS_120B})


@dataclass(frozen=True, slots=True)
class GptOssOllamaProvider(OllamaProvider):
    """Constrained Ollama adapter for OpenAI gpt-oss open-weight models.

    This provider intentionally accepts only the two official gpt-oss Ollama
    model identifiers. Network validation, redirect rejection, bounded I/O,
    locale handling, and evidence-preservation behavior are inherited from the
    hardened ``OllamaProvider`` implementation.
    """

    model: str = GPT_OSS_20B
    name: str = "gpt-oss-ollama"

    def __post_init__(self) -> None:
        OllamaProvider.__post_init__(self)
        normalized_model = self.model.strip()
        if normalized_model not in SUPPORTED_GPT_OSS_MODELS:
            allowed = ", ".join(sorted(SUPPORTED_GPT_OSS_MODELS))
            raise ValueError(f"gpt-oss model must be one of: {allowed}")

    def capabilities(self) -> tuple[str, ...]:
        return (
            "local-inference",
            "open-weight",
            "gpt-oss",
            "reasoning",
            "no-native-citations",
        )
