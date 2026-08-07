from __future__ import annotations

import base64
import hashlib
import hmac
import os
import re
import secrets

PASSWORD_VERSION = "scrypt-v1"
SCRYPT_N = 2**15
SCRYPT_R = 8
SCRYPT_P = 2
SCRYPT_DKLEN = 32
SCRYPT_MAXMEM = 64 * 1024 * 1024
SCRYPT_VERIFY_MAX_N = 2**16
SCRYPT_VERIFY_MAX_R = 8
SCRYPT_VERIFY_MAX_P = 4
COMMON_PASSWORDS = {
    "password",
    "password123",
    "qwerty123456",
    "12345678901234",
    "admin123456789",
    "changeme123456",
}
EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


class PasswordPolicyError(ValueError):
    pass


def normalize_email(value: str) -> str:
    normalized = value.strip().casefold()
    if len(normalized) > 254 or not EMAIL_PATTERN.fullmatch(normalized):
        raise ValueError("invalid email address")
    return normalized


def validate_password(password: str, *, minimum_length: int = 14) -> None:
    if len(password) < minimum_length:
        raise PasswordPolicyError(f"password must contain at least {minimum_length} characters")
    if len(password) > 256:
        raise PasswordPolicyError("password is too long")
    if password.casefold() in COMMON_PASSWORDS:
        raise PasswordPolicyError("password is too common")
    if password.isspace() or password.strip() == "":
        raise PasswordPolicyError("password is invalid")


def hash_password(password: str, *, minimum_length: int = 14, salt: bytes | None = None) -> str:
    validate_password(password, minimum_length=minimum_length)
    actual_salt = salt or os.urandom(16)
    digest = hashlib.scrypt(
        password.encode("utf-8"),
        salt=actual_salt,
        n=SCRYPT_N,
        r=SCRYPT_R,
        p=SCRYPT_P,
        dklen=SCRYPT_DKLEN,
        maxmem=SCRYPT_MAXMEM,
    )
    return "$".join(
        [
            PASSWORD_VERSION,
            str(SCRYPT_N),
            str(SCRYPT_R),
            str(SCRYPT_P),
            base64.urlsafe_b64encode(actual_salt).decode("ascii"),
            base64.urlsafe_b64encode(digest).decode("ascii"),
        ]
    )


def _decode_hash(encoded: str) -> tuple[str, int, int, int, bytes, bytes] | None:
    try:
        version, n, r, p, salt_b64, digest_b64 = encoded.split("$", 5)
        decoded = (
            version,
            int(n),
            int(r),
            int(p),
            base64.urlsafe_b64decode(salt_b64.encode("ascii")),
            base64.urlsafe_b64decode(digest_b64.encode("ascii")),
        )
    except (ValueError, TypeError):
        return None
    _version, n_value, r_value, p_value, salt, digest = decoded
    if n_value < 2**14 or n_value > SCRYPT_VERIFY_MAX_N or n_value & (n_value - 1):
        return None
    if not 1 <= r_value <= SCRYPT_VERIFY_MAX_R or not 1 <= p_value <= SCRYPT_VERIFY_MAX_P:
        return None
    if not 8 <= len(salt) <= 64 or len(digest) != SCRYPT_DKLEN:
        return None
    return decoded


def verify_password(password: str, encoded: str) -> bool:
    decoded = _decode_hash(encoded)
    if decoded is None:
        return False
    version, n, r, p, salt, expected = decoded
    if version != PASSWORD_VERSION:
        return False
    try:
        actual = hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=n,
            r=r,
            p=p,
            dklen=len(expected),
            maxmem=max(SCRYPT_MAXMEM, 128 * r * n + 1024 * 1024),
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(actual, expected)


def needs_password_rehash(encoded: str) -> bool:
    decoded = _decode_hash(encoded)
    if decoded is None:
        return True
    version, n, r, p, _salt, digest = decoded
    return (
        version != PASSWORD_VERSION
        or n != SCRYPT_N
        or r != SCRYPT_R
        or p != SCRYPT_P
        or len(digest) != SCRYPT_DKLEN
    )


def new_secret() -> str:
    return secrets.token_urlsafe(32)


def secret_digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


_DUMMY_HASH = hash_password("not-a-real-password-2026", minimum_length=14, salt=b"aisearcharab-demo")


def perform_dummy_password_check(password: str) -> None:
    verify_password(password, _DUMMY_HASH)
