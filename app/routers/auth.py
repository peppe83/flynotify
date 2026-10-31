"""Registrazione, login, logout (form-based, cookie JWT)."""
from fastapi import APIRouter, Depends, Form, Response
from fastapi.responses import RedirectResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..deps import COOKIE_NAME
from ..models import User
from ..security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])

_COOKIE_MAX_AGE = settings.ACCESS_TOKEN_MINUTES * 60


def _set_auth_cookie(resp: Response, user: User) -> None:
    token = create_access_token(user.id, user.role)
    resp.set_cookie(COOKIE_NAME, token, httponly=True, samesite="lax",
                    max_age=_COOKIE_MAX_AGE, secure=settings.APP_ENV == "production")


@router.post("/signup")
def signup(email: str = Form(...), password: str = Form(...),
           full_name: str = Form(""), db: Session = Depends(get_db)):
    email = email.strip().lower()
    if db.query(User).filter(func.lower(User.email) == email).first():
        return RedirectResponse("/signup?error=exists", status_code=302)
    if db.query(func.count(User.id)).scalar() >= settings.MAX_USERS:
        return RedirectResponse("/signup?error=full", status_code=302)

    user = User(email=email, full_name=full_name or None,
                password_hash=hash_password(password),
                role="user", status="active", verified=True,
                poll_interval_hours=settings.DEFAULT_POLL_INTERVAL_HOURS,
                timezone=settings.DEFAULT_TIMEZONE, currency=settings.DEFAULT_CURRENCY)
    db.add(user)
    db.commit()
    resp = RedirectResponse("/dashboard", status_code=302)
    _set_auth_cookie(resp, user)
    return resp


@router.post("/login")
def login(email: str = Form(...), password: str = Form(...),
          db: Session = Depends(get_db)):
    email = email.strip().lower()
    user = db.query(User).filter(func.lower(User.email) == email).first()
    if not user or user.status != "active" or not verify_password(password, user.password_hash):
        return RedirectResponse("/login?error=1", status_code=302)
    resp = RedirectResponse("/dashboard", status_code=302)
    _set_auth_cookie(resp, user)
    return resp


@router.get("/logout")
def logout():
    resp = RedirectResponse("/", status_code=302)
    resp.delete_cookie(COOKIE_NAME)
    return resp
