"""CRUD alert dell'utente, con SOSPENSIONE/RIPRESA."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..deps import get_current_user
from ..models import Alert, User
from ..providers.run_cache import RunCache
from ..schemas import AlertCreate
from ..services.search import SearchService

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


def _serialize(a: Alert) -> dict:
    return {
        "id": a.id, "origin": a.origin, "destination": a.destination,
        "depart_from": a.depart_from.isoformat(),
        "depart_to": a.depart_to.isoformat(),
        "return_from": a.return_from.isoformat() if a.return_from else None,
        "return_to": a.return_to.isoformat() if a.return_to else None,
        "adults": a.adults, "cabin": a.cabin,
        "target_price": float(a.target_price) if a.target_price is not None else None,
        "currency": a.currency, "strategy": a.strategy, "status": a.status,
        "last_price": float(a.last_price) if a.last_price is not None else None,
        "last_checked": a.last_checked.isoformat() if a.last_checked else None,
    }


def _get_owned(alert_id: str, user: User, db: Session) -> Alert:
    a = db.get(Alert, alert_id)
    if not a or a.user_id != user.id:
        raise HTTPException(status_code=404, detail="Alert non trovato")
    return a


@router.get("")
def list_alerts(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.query(Alert).filter(Alert.user_id == user.id).order_by(Alert.created_at.desc()).all()
    return {"alerts": [_serialize(a) for a in rows]}


@router.post("")
def create_alert(body: AlertCreate, user: User = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    count = db.query(func.count(Alert.id)).filter(Alert.user_id == user.id).scalar()
    if count >= settings.MAX_ALERTS_PER_USER:
        raise HTTPException(status_code=400,
                            detail=f"Raggiunto il massimo di {settings.MAX_ALERTS_PER_USER} alert")

    a = Alert(
        user_id=user.id,
        origin=body.origin.upper(), destination=body.destination.upper(),
        depart_from=body.depart_from, depart_to=body.depart_to or body.depart_from,
        return_from=body.return_from, return_to=body.return_to or body.return_from,
        adults=body.adults, cabin=body.cabin, max_stops=body.max_stops,
        depart_dow=body.depart_dow, return_dow=body.return_dow,
        depart_time_from=body.depart_time_from, depart_time_to=body.depart_time_to,
        target_price=body.target_price, currency=body.currency.upper(),
        strategy=body.strategy, status="active",
    )
    db.add(a)
    db.commit()
    db.refresh(a)

    # Primo check immediato (best effort), per mostrare subito un prezzo
    if settings.FIRST_CHECK_ON_CREATE:
        try:
            best = SearchService(RunCache()).best_offer_for_alert(a)
            if best:
                a.last_price = best.price
                from datetime import datetime
                a.last_checked = datetime.utcnow()
                db.commit()
                db.refresh(a)
        except Exception:  # noqa: BLE001
            pass

    return _serialize(a)


@router.post("/{alert_id}/suspend")
def suspend_alert(alert_id: str, user: User = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    a = _get_owned(alert_id, user, db)
    a.status = "paused"
    db.commit()
    return {"id": a.id, "status": a.status}


@router.post("/{alert_id}/resume")
def resume_alert(alert_id: str, user: User = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    a = _get_owned(alert_id, user, db)
    a.status = "active"
    db.commit()
    return {"id": a.id, "status": a.status}


@router.delete("/{alert_id}")
def delete_alert(alert_id: str, user: User = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    a = _get_owned(alert_id, user, db)
    db.delete(a)
    db.commit()
    return {"deleted": alert_id}
