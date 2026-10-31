"""Dipendenze condivise: sessione DB e autenticazione via cookie JWT."""
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from .db import get_db
from .models import User
from .security import decode_access_token

COOKIE_NAME = "access_token"


class NotAuthenticated(Exception):
    """Sollevata dalle pagine HTML protette: l'handler reindirizza al login."""


def _user_from_request(request: Request, db: Session) -> User | None:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth[7:]
    if not token:
        return None
    payload = decode_access_token(token)
    if not payload:
        return None
    user = db.get(User, payload.get("sub"))
    if not user or user.status != "active":
        return None
    return user


def get_current_user_optional(request: Request, db: Session = Depends(get_db)) -> User | None:
    return _user_from_request(request, db)


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    """Per gli endpoint JSON: 401 se non autenticato."""
    user = _user_from_request(request, db)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Non autenticato")
    return user


def require_role(*roles: str):
    def dep(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permesso negato")
        return user
    return dep


def require_user_page(request: Request, db: Session = Depends(get_db)) -> User:
    """Per le pagine HTML protette: reindirizza al login se non autenticato."""
    user = _user_from_request(request, db)
    if not user:
        raise NotAuthenticated()
    return user
