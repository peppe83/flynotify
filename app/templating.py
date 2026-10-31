"""Istanza condivisa dei template Jinja2."""
from fastapi.templating import Jinja2Templates

from .config import settings

templates = Jinja2Templates(directory="templates")
templates.env.globals["APP_NAME"] = settings.APP_NAME
