"""Password hashing (PBKDF2) and signed access tokens (JWT)."""

import base64
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

import jwt


def hash_password(password: str) -> str:
    if len(password) < 12:
        raise ValueError("Use at least 12 characters")
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 600_000)
    return f"pbkdf2$600000${base64.b64encode(salt).decode()}${base64.b64encode(digest).decode()}"


def verify_password(password: str, encoded: str) -> bool:
    _, iterations, salt, expected = encoded.split("$")
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), base64.b64decode(salt), int(iterations))
    return hmac.compare_digest(digest, base64.b64decode(expected))


def token_for(user_id: str, secret: str) -> str:
    return jwt.encode(
        {"sub": user_id, "exp": datetime.now(timezone.utc) + timedelta(hours=8)}, secret, algorithm="HS256"
    )
