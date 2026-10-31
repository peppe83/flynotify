"""Hashing password e gestione token JWT."""
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from .config import settings


def hash_password(plain: str) -> str:
    # bcrypt gestisce al massimo 72 byte: troncamento esplicito (limite intrinseco)
    return bcrypt.hashpw(plain.encode("utf-8")[:72], bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str | None) -> bool:
    if not hashed:
        return False
    try:
        return bcrypt.checkpw(plain.encode("utf-8")[:72], hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def create_access_token(user_id: str, role: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "role": role,
        "iat": now,
        "exp": now + timedelta(minutes=settings.ACCESS_TOKEN_MINUTES),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    except jwt.PyJWTError:
        return None
