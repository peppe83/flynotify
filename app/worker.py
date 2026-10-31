"""Worker schedulato (lanciato da Windows Task Scheduler).

Per OGNI utente attivo il cui intervallo personale è scaduto:
  - valuta i suoi alert ATTIVI (quelli sospesi vengono saltati);
  - registra lo storico prezzi e, se scatta un avviso, lo accumula;
  - invia UNA email riepilogativa (digest) con tutti gli avvisi dell'utente;
  - aggiorna last_run_at dell'utente.
Nessuna cache persistente: ogni run fa chiamate fresche.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

from sqlalchemy import select

from .config import settings
from .db import SessionLocal, engine
from .models import Alert, EmailLog, Notification, PriceHistory, RunLog, User
from .providers.run_cache import RunCache
from .services import email as email_svc
from .services.alert_engine import build_dedupe_key, should_notify
from .services.search import SearchService

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("flynotify.worker")

_REASON = {"below_target": "sotto soglia", "price_drop": "prezzo in calo", "good_deal": "buon affare"}


def _is_due(user: User, now: datetime) -> bool:
    if user.last_run_at is None:
        return True
    return now - user.last_run_at >= timedelta(hours=user.poll_interval_hours)


def _history_prices(db, alert_id: str, days: int = 7) -> list[float]:
    since = datetime.utcnow() - timedelta(days=days)
    rows = db.execute(
        select(PriceHistory.price).where(
            PriceHistory.alert_id == alert_id, PriceHistory.observed_at >= since)
    ).scalars().all()
    return [float(p) for p in rows]


def _last_notified_price(db, alert_id: str) -> float | None:
    row = db.execute(
        select(Notification.price).where(Notification.alert_id == alert_id)
        .order_by(Notification.sent_at.desc()).limit(1)
    ).scalar_one_or_none()
    return float(row) if row is not None else None


def run_worker() -> None:
    if not settings.ENABLE_ALERTS:
        log.info("ENABLE_ALERTS=false: worker non attivo.")
        return

    db = SessionLocal()
    rl = RunLog(status="ok")
    db.add(rl)
    db.commit()
    db.refresh(rl)

    now = datetime.utcnow()
    users_checked = alerts_checked = emails_sent = api_calls = 0

    try:
        users = db.query(User).filter(User.status == "active").all()
        for user in users:
            if not _is_due(user, now):
                continue
            users_checked += 1
            svc = SearchService(RunCache())      # cache di esecuzione per-utente
            triggered: list[dict] = []

            alerts = db.query(Alert).filter(
                Alert.user_id == user.id, Alert.status == "active").all()
            for alert in alerts:
                alerts_checked += 1
                alert.last_checked = datetime.utcnow()
                try:
                    best = svc.best_offer_for_alert(alert)
                except Exception as e:  # noqa: BLE001
                    log.warning("Ricerca fallita alert %s: %s", alert.id, e)
                    best = None
                if not best:
                    continue

                alert.last_price = best.price
                db.add(PriceHistory(alert_id=alert.id, price=best.price,
                                    currency=best.currency, offer_json=best.model_dump()))

                history = _history_prices(db, alert.id)
                last_notified = _last_notified_price(db, alert.id)
                ok, reason = should_notify(alert, best.price, history, last_notified)
                if not ok:
                    continue

                dedupe = build_dedupe_key(alert.id, best.price)
                exists = db.query(Notification).filter(
                    Notification.dedupe_key == dedupe).first()
                if exists:
                    continue
                db.add(Notification(alert_id=alert.id, price=best.price,
                                    reason=reason, dedupe_key=dedupe))

                dest = best.destination
                dates = best.depart_date + (f" → {best.return_date}" if best.return_date else "")
                triggered.append({
                    "route": f"{best.origin} → {dest}",
                    "price": float(best.price), "currency": best.currency,
                    "dates": dates, "reason": reason,
                    "source": best.source.provider,
                })

            # UNA email riepilogativa per utente
            if triggered:
                html = email_svc.build_digest_html(
                    user.full_name, triggered)
                subject = f"✈️ flynotify — {len(triggered)} nuovi avvisi di prezzo"
                sent, err = email_svc.send_email(user.email, subject, html)
                db.add(EmailLog(user_id=user.id, to_email=user.email, subject=subject,
                                status="sent" if sent else "error", error_text=err))
                if sent:
                    emails_sent += 1

            user.last_run_at = datetime.utcnow()
            api_calls += svc.total_calls
            db.commit()

        rl.status = "ok"
    except Exception as e:  # noqa: BLE001
        db.rollback()
        rl.status = "error"
        rl.error_text = str(e)
        log.exception("Worker error")
    finally:
        rl.finished_at = datetime.utcnow()
        rl.users_checked = users_checked
        rl.alerts_checked = alerts_checked
        rl.emails_sent = emails_sent
        rl.api_calls = api_calls
        db.add(rl)
        db.commit()
        db.close()
        log.info("Run completato: utenti=%s alert=%s email=%s chiamate=%s",
                 users_checked, alerts_checked, emails_sent, api_calls)


if __name__ == "__main__":
    # assicura che le tabelle esistano anche se il worker gira per primo
    from .db import Base
    Base.metadata.create_all(engine)
    run_worker()
