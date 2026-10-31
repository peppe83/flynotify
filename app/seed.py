"""Crea il primo superadmin (eseguire una volta).

Uso:
    python -m app.seed <email> <password> ["Nome Cognome"]
"""
import sys

from sqlalchemy import func

from .db import Base, SessionLocal, engine
from .models import User
from .security import hash_password


def create_superadmin(email: str, password: str, full_name: str | None = None) -> None:
    Base.metadata.create_all(engine)
    db = SessionLocal()
    try:
        email = email.strip().lower()
        existing = db.query(User).filter(func.lower(User.email) == email).first()
        if existing:
            existing.role = "superadmin"
            existing.status = "active"
            existing.password_hash = hash_password(password)
            db.commit()
            print(f"Utente esistente promosso a superadmin: {email}")
            return
        u = User(email=email, full_name=full_name, password_hash=hash_password(password),
                 role="superadmin", status="active", verified=True)
        db.add(u)
        db.commit()
        print(f"Superadmin creato: {email}")
    finally:
        db.close()


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Uso: python -m app.seed <email> <password> [\"Nome\"]")
        raise SystemExit(1)
    create_superadmin(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None)
