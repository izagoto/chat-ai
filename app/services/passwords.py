"""Password hashing helpers (PBKDF2-SHA256)."""

from __future__ import annotations

import hashlib
import hmac
import secrets


_ITERATIONS = 200_000
_SCHEME = "pbkdf2_sha256"


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), _ITERATIONS).hex()
    return f"{_SCHEME}${_ITERATIONS}${salt}${digest}"


def verify_password(password: str, password_hash: str) -> bool:
    try:
        scheme, iterations_s, salt, expected = password_hash.split("$", 3)
        if scheme != _SCHEME:
            return False
        iterations = int(iterations_s)
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("utf-8"),
            iterations,
        ).hex()
        return hmac.compare_digest(digest, expected)
    except (ValueError, TypeError):
        return False
