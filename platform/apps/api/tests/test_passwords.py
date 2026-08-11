import base64
import hashlib

import pytest

from aisearcharab_api.security import (
    PasswordPolicyError,
    hash_password,
    needs_password_rehash,
    normalize_email,
    secret_digest,
    verify_password,
)


def test_scrypt_password_hash_round_trip() -> None:
    encoded = hash_password("a-long-secure-password-2026")
    assert encoded.startswith("scrypt-v1$")
    assert verify_password("a-long-secure-password-2026", encoded)
    assert not verify_password("wrong-password", encoded)
    assert "a-long-secure-password-2026" not in encoded
    assert needs_password_rehash(encoded) is False


def test_legacy_scrypt_profile_is_accepted_but_marked_for_rehash() -> None:
    password = "legacy-secure-password-2026"
    salt = b"legacy-profile-16"
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1, dklen=32)
    encoded = "$".join(
        [
            "scrypt-v1",
            str(2**14),
            "8",
            "1",
            base64.urlsafe_b64encode(salt).decode("ascii"),
            base64.urlsafe_b64encode(digest).decode("ascii"),
        ]
    )
    assert verify_password(password, encoded)
    assert needs_password_rehash(encoded) is True


def test_hostile_stored_work_factor_is_rejected_before_scrypt() -> None:
    salt = base64.urlsafe_b64encode(b"bounded-salt-1234").decode("ascii")
    digest = base64.urlsafe_b64encode(b"0" * 32).decode("ascii")
    encoded = f"scrypt-v1${2**24}$8$1${salt}${digest}"
    assert verify_password("attacker-controlled", encoded) is False
    assert needs_password_rehash(encoded) is True


def test_password_policy_and_email_normalization() -> None:
    with pytest.raises(PasswordPolicyError):
        hash_password("short")
    assert normalize_email(" Owner@Example.COM ") == "owner@example.com"
    with pytest.raises(ValueError):
        normalize_email("invalid")


def test_high_entropy_session_digest_is_fixed_length() -> None:
    assert len(secret_digest("random-session-value")) == 64
