import pytest

from aisearcharab_api.security import PasswordPolicyError, hash_password, normalize_email, secret_digest, verify_password


def test_scrypt_password_hash_round_trip() -> None:
    encoded = hash_password("a-long-secure-password-2026")
    assert encoded.startswith("scrypt-v1$")
    assert verify_password("a-long-secure-password-2026", encoded)
    assert not verify_password("wrong-password", encoded)
    assert "a-long-secure-password-2026" not in encoded


def test_password_policy_and_email_normalization() -> None:
    with pytest.raises(PasswordPolicyError):
        hash_password("short")
    assert normalize_email(" Owner@Example.COM ") == "owner@example.com"
    with pytest.raises(ValueError):
        normalize_email("invalid")


def test_high_entropy_session_digest_is_fixed_length() -> None:
    assert len(secret_digest("random-session-value")) == 64
