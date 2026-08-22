from dataclasses import replace

import pytest

from aisearcharab_api.config import ConfigurationError, Settings


def test_generated_answers_are_blocked_in_production_until_operational_controls_exist(settings: Settings) -> None:
    production = replace(
        settings,
        environment="production",
        database_url="postgresql+psycopg://user:password@db.example/aisearcharab",
        allowed_origins=("https://aisearcharab.com",),
        allowed_hosts=("aisearcharab.com",),
        enforce_separation_of_duties=True,
        require_mfa_for_privileged=True,
        mfa_encryption_key="test-mfa-encryption-key-32-bytes-long",
        login_throttle_key="test-login-throttle-key-32-bytes-long",
        generated_answers_enabled=True,
        openai_api_key="test-openai-key-not-a-production-secret",
    )
    with pytest.raises(ConfigurationError, match="distributed rate limiting and observability"):
        production.validate()
