"""Engine e sessione SQLAlchemy. Compatibile MySQL e SQLite."""
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import settings

_connect_args = {}
if settings.sqlalchemy_url.startswith("sqlite"):
    _connect_args = {"check_same_thread": False}

engine = create_engine(
    settings.sqlalchemy_url,
    pool_pre_ping=True,
    connect_args=_connect_args,
    future=True,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class Base(DeclarativeBase):
    pass


def get_db():
    """Dependency FastAPI: fornisce una sessione e la chiude a fine richiesta."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
