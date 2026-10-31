"""Pagine HTML. Pubbliche: index, login, signup. Le altre sotto autenticazione."""
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from ..config import settings
from ..deps import get_current_user_optional, require_user_page
from ..models import User
from ..templating import templates

router = APIRouter(tags=["pages"])


def _ctx(request: Request, user: User | None, **extra) -> dict:
    base = {"request": request, "user": user, "settings": settings}
    base.update(extra)
    return base


@router.get("/", response_class=HTMLResponse)
def index(request: Request, user: User | None = Depends(get_current_user_optional)):
    return templates.TemplateResponse(request, "index.html", _ctx(request, user))


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request, user: User | None = Depends(get_current_user_optional)):
    if user:
        return RedirectResponse("/dashboard", status_code=302)
    return templates.TemplateResponse(request, "login.html", _ctx(request, None))


@router.get("/signup", response_class=HTMLResponse)
def signup_page(request: Request, user: User | None = Depends(get_current_user_optional)):
    if user:
        return RedirectResponse("/dashboard", status_code=302)
    return templates.TemplateResponse(request, "signup.html", _ctx(request, None))


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request, user: User = Depends(require_user_page)):
    return templates.TemplateResponse(request, "dashboard.html", _ctx(request, user))


@router.get("/alerts", response_class=HTMLResponse)
def alerts_page(request: Request, user: User = Depends(require_user_page)):
    return templates.TemplateResponse(request, "alerts.html", _ctx(request, user))


@router.get("/preferences", response_class=HTMLResponse)
def preferences_page(request: Request, user: User = Depends(require_user_page)):
    return templates.TemplateResponse(request, "preferences.html", _ctx(request, user))


@router.get("/admin", response_class=HTMLResponse)
def admin_page(request: Request, user: User = Depends(require_user_page)):
    if user.role not in ("admin", "superadmin"):
        return RedirectResponse("/dashboard", status_code=302)
    return templates.TemplateResponse(request, "admin.html", _ctx(request, user))
