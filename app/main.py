"""Entry point FastAPI: monta static, template, router e crea le tabelle."""
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from .config import settings
from .db import Base, engine
from .deps import NotAuthenticated
from .routers import admin, alerts, auth, pages, prefs, search

logging.basicConfig(level=logging.INFO)

BASE_DIR = Path(__file__).resolve().parent.parent


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(engine)
    yield


app = FastAPI(title=settings.APP_NAME, lifespan=lifespan)

# File statici
static_dir = BASE_DIR / "static"
static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.exception_handler(NotAuthenticated)
async def not_authenticated_handler(request: Request, exc: NotAuthenticated):
    return RedirectResponse(url="/login", status_code=302)


@app.get("/healthz", include_in_schema=False)
def healthz():
    return {"status": "ok", "app": settings.APP_NAME}


# Router
app.include_router(pages.router)
app.include_router(auth.router)
app.include_router(search.router)
app.include_router(alerts.router)
app.include_router(prefs.router)
app.include_router(admin.router)
