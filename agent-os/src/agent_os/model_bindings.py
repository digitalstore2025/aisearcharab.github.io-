from __future__ import annotations

import os

from .model_router import ModelChoice


class ModelBindingResolver:
    """Resolve policy aliases to provider model IDs without hard-coding deployment choices."""

    def __init__(self, *, env_prefix: str = "ASTRA_MODEL_"):
        self.env_prefix = env_prefix

    def environment_key(self, choice: ModelChoice) -> str:
        alias = (choice.alias or choice.tier).upper().replace("-", "_")
        return f"{self.env_prefix}{alias}"

    def resolve(self, choice: ModelChoice) -> str:
        key = self.environment_key(choice)
        configured = os.getenv(key, "").strip()
        if configured:
            return configured

        model = choice.model.strip()
        placeholder = (
            not model
            or model.endswith("-model")
            or "reasoning-model" in model
            or "+independent-verifier" in model
        )
        if placeholder:
            raise RuntimeError(
                f"No provider model binding for policy alias '{choice.alias or choice.tier}'. "
                f"Set {key} to a deployment model ID."
            )
        return model
