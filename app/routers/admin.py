"""Area admin: gestione utenti, ruoli (solo superadmin), metriche."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import get_current_user, require_role
from ..models import Alert, EmailLog, RunLog, User
from ..schemas import RoleUpdate

router = APIRouter(prefix="/api/admin", tags=["admin"])

_ROLES = {"user", "admin", "superadmin"}


@router.get("/users")
def list_users(_a=Depends(require_role("admin", "superadmin")), db: Session = Depends(get_db)):
    rows = db.query(User).order_by(User.created_at.desc()).all()
    return {"users": [{"id": u.id, "email": u.email, "full_name": u.full_name,
                       "role": u.role, "status": u.status,
                       "poll_interval_hours": u.poll_interval_hours} for u in rows]}


@router.post("/users/{user_id}/suspend")
def suspend_user(user_id: str, actor: User = Depends(require_role("admin", "superadmin")),
                 db: Session = Depends(get_db)):
    u = db.get(User, user_id)
    if not u:
        raise HTTPException(404, "Utente non trovato")
    if u.role in ("admin", "superadmin") and actor.role != "superadmin":
        raise HTTPException(403, "Un admin non può gestire altri admin")
    u.status = "suspended"
    db.commit()
    return {"id": u.id, "status": u.status}


@router.post("/users/{user_id}/resume")
def resume_user(user_id: str, actor: User = Depends(require_role("admin", "superadmin")),
                db: Session = Depends(get_db)):
    u = db.get(User, user_id)
    if not u:
        raise HTTPException(404, "Utente non trovato")
    u.status = "active"
    db.commit()
    return {"id": u.id, "status": u.status}


@router.patch("/users/{user_id}/role")
def change_role(user_id: str, body: RoleUpdate,
                _a=Depends(require_role("superadmin")), db: Session = Depends(get_db)):
    if body.role not in _ROLES:
        raise HTTPException(400, "Ruolo non valido")
    u = db.get(User, user_id)
    if not u:
        raise HTTPException(404, "Utente non trovato")
    # Deve restare almeno un superadmin
    if u.role == "superadmin" and body.role != "superadmin":
        others = db.query(func.count(User.id)).filter(
            User.role == "superadmin", User.id != u.id).scalar()
        if others == 0:
            raise HTTPException(400, "Deve esistere almeno un superadmin")
    u.role = body.role
    db.commit()
    return {"id": u.id, "role": u.role}


@router.get("/stats")
def stats(_a=Depends(require_role("admin", "superadmin")), db: Session = Depends(get_db)):
    last_run = db.query(RunLog).order_by(RunLog.started_at.desc()).first()
    return {
        "users": db.query(func.count(User.id)).scalar(),
        "alerts_active": db.query(func.count(Alert.id)).filter(Alert.status == "active").scalar(),
        "emails_sent": db.query(func.count(EmailLog.id)).filter(EmailLog.status == "sent").scalar(),
        "last_run": {
            "started_at": last_run.started_at.isoformat() if last_run else None,
            "status": last_run.status if last_run else None,
            "users_checked": last_run.users_checked if last_run else None,
            "emails_sent": last_run.emails_sent if last_run else None,
            "api_calls": last_run.api_calls if last_run else None,
        } if last_run else None,
    }
