from __future__ import annotations

import base64
import hashlib
import hmac
import re
import secrets
import struct
from datetime import datetime, timezone
from urllib.parse import quote

from cryptography.fernet import Fernet, InvalidToken

TOTP_PERIOD_SECONDS = 30
TOTP_DIGITS = 6
TOTP_WINDOW = 1
_RECOVERY_CODE_PATTERN = re.compile(r"^[A-Z2-7]{4}(?:-[A-Z2-7]{4}){5}$")


class MfaSecretError(ValueError):
    """Raised when encrypted MFA material cannot be decoded safely."""


def _fernet(master_key: str) -> Fernet:
    if len(master_key.encode("utf-8")) < 32:
        raise MfaSecretError("MFA encryption key must contain at least 32 bytes")
    derived = hashlib.sha256(master_key.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(derived))


def new_totp_secret() -> str:
    """Return a 160-bit RFC 4648 Base32 secret without padding."""
    return base64.b32encode(secrets.token_bytes(20)).decode("ascii").rstrip("=")


def encrypt_totp_secret(secret: str, master_key: str) -> str:
    return _fernet(master_key).encrypt(secret.encode("ascii")).decode("ascii")


def decrypt_totp_secret(token: str, master_key: str) -> str:
    try:
        return _fernet(master_key).decrypt(token.encode("ascii")).decode("ascii")
    except (InvalidToken, UnicodeDecodeError, ValueError) as exc:
        raise MfaSecretError("stored MFA secret cannot be decrypted") from exc


def _decode_base32(secret: str) -> bytes:
    normalized = secret.strip().replace(" ", "").upper()
    padding = "=" * ((8 - len(normalized) % 8) % 8)
    try:
        return base64.b32decode(normalized + padding, casefold=True)
    except (ValueError, TypeError) as exc:
        raise MfaSecretError("invalid TOTP secret") from exc


def totp_code(secret: str, *, counter: int, digits: int = TOTP_DIGITS) -> str:
    if counter < 0:
        raise ValueError("counter must be non-negative")
    key = _decode_base32(secret)
    digest = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    binary = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
    return f"{binary % (10**digits):0{digits}d}"


def current_counter(*, now: datetime | None = None) -> int:
    moment = now or datetime.now(timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return int(moment.timestamp()) // TOTP_PERIOD_SECONDS


def verify_totp(
    secret: str,
    code: str,
    *,
    last_counter: int = -1,
    now: datetime | None = None,
    window: int = TOTP_WINDOW,
) -> int | None:
    candidate = code.strip()
    if len(candidate) != TOTP_DIGITS or not candidate.isdigit():
        return None
    center = current_counter(now=now)
    for counter in range(center - window, center + window + 1):
        if counter <= last_counter or counter < 0:
            continue
        if hmac.compare_digest(totp_code(secret, counter=counter), candidate):
            return counter
    return None


def build_otpauth_uri(secret: str, *, account_name: str, issuer: str) -> str:
    safe_issuer = issuer.strip() or "AISearcharab.com"
    label = quote(f"{safe_issuer}:{account_name}", safe="")
    return (
        f"otpauth://totp/{label}?secret={quote(secret, safe='')}"
        f"&issuer={quote(safe_issuer, safe='')}&algorithm=SHA1&digits={TOTP_DIGITS}&period={TOTP_PERIOD_SECONDS}"
    )


def new_recovery_codes(*, count: int = 10) -> list[str]:
    if not 5 <= count <= 20:
        raise ValueError("recovery-code count must be between 5 and 20")
    codes: list[str] = []
    for _ in range(count):
        raw = base64.b32encode(secrets.token_bytes(15)).decode("ascii").rstrip("=")
        groups = [raw[index : index + 4] for index in range(0, len(raw), 4)]
        codes.append("-".join(groups))
    return codes


def normalize_recovery_code(code: str) -> str:
    compact = code.strip().upper().replace(" ", "").replace("_", "-")
    if not _RECOVERY_CODE_PATTERN.fullmatch(compact):
        raise ValueError("invalid recovery code")
    return compact


def recovery_code_digest(code: str) -> str:
    normalized = normalize_recovery_code(code)
    return hashlib.sha256(normalized.encode("ascii")).hexdigest()
