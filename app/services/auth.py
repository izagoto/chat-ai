"""User authentication against SQLite users table."""

from __future__ import annotations

import hashlib
import hmac
import time
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.user import User
from app.services.passwords import verify_password

TOKEN_TTL_SECONDS = 60 * 60 * 12


@dataclass
class AuthUser:
    id: int
    email: str
    fullname: str
    role: str = "user"


def _sign(payload: str) -> str:
    return hmac.new(settings.auth_secret.encode(), payload.encode(), hashlib.sha256).hexdigest()


def issue_token(email: str) -> str:
    exp = int(time.time()) + TOKEN_TTL_SECONDS
    payload = f"{email}|{exp}"
    return f"{payload}|{_sign(payload)}"


def parse_token(token: str, db: Session) -> AuthUser | None:
    try:
        email, exp_s, signature = token.split("|", 2)
        payload = f"{email}|{exp_s}"
        if not hmac.compare_digest(signature, _sign(payload)):
            return None
        if int(exp_s) < int(time.time()):
            return None
        user = db.scalar(select(User).where(User.email == email.lower().strip()))
        if not user or not user.is_active:
            return None
        return AuthUser(id=user.id, email=user.email, fullname=user.fullname, role=user.role)
    except (ValueError, TypeError):
        return None


def authenticate(db: Session, email: str, password: str) -> AuthUser | None:
    user = db.scalar(select(User).where(User.email == email.lower().strip()))
    if not user or not user.is_active:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return AuthUser(id=user.id, email=user.email, fullname=user.fullname, role=user.role)
