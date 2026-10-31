"""Invio email via Gmail (SMTP + App Password). Digest riepilogativo per utente."""
from __future__ import annotations

import logging
import smtplib
from email.mime.text import MIMEText

from ..config import settings

log = logging.getLogger("flynotify.email")

_REASON_LABEL = {
    "below_target": "sotto la soglia",
    "price_drop": "prezzo in calo",
    "good_deal": "buon affare",
}


def is_configured() -> bool:
    return bool(settings.GMAIL_USER and settings.GMAIL_APP_PASSWORD)


def build_digest_html(user_name: str | None, items: list[dict]) -> str:
    """items: dict con route, price, currency, dates, source, reason."""
    rows = []
    for it in items:
        label = _REASON_LABEL.get(it.get("reason", ""), "offerta")
        rows.append(f"""
          <tr>
            <td style="padding:10px 12px;border-bottom:1px solid #eee;">
              <strong>{it['route']}</strong><br>
              <span style="color:#555;font-size:13px;">{it.get('dates','')}</span>
            </td>
            <td style="padding:10px 12px;border-bottom:1px solid #eee;text-align:right;">
              <strong style="color:#0a7d2c;">{it['price']:.0f} {it['currency']}</strong><br>
              <span style="font-size:12px;color:#777;">{label} · Fonte: {it.get('source','')}</span>
            </td>
          </tr>""")
    hello = f"Ciao {user_name}," if user_name else "Ciao,"
    manage = f"{settings.APP_BASE_URL}/alerts"
    return f"""
    <div style="font-family:Arial,Helvetica,sans-serif;max-width:560px;margin:auto;">
      <h2 style="color:#1a56db;">✈️ flynotify — {len(items)} nuovi avvisi di prezzo</h2>
      <p>{hello} ecco le offerte che rientrano nei tuoi alert:</p>
      <table style="width:100%;border-collapse:collapse;border:1px solid #eee;">{''.join(rows)}</table>
      <p style="margin-top:18px;font-size:13px;color:#555;">
        <a href="{manage}">Gestisci i tuoi alert</a> ·
        I prezzi sono indicativi e vanno verificati presso la compagnia/agenzia.
      </p>
    </div>"""


def send_email(to_email: str, subject: str, html: str) -> tuple[bool, str | None]:
    if not is_configured():
        return False, "Gmail non configurato (GMAIL_USER / GMAIL_APP_PASSWORD)"
    msg = MIMEText(html, "html", "utf-8")
    msg["Subject"] = subject
    msg["From"] = f"{settings.EMAIL_FROM_NAME} <{settings.GMAIL_USER}>"
    msg["To"] = to_email
    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=20) as s:
            s.starttls()
            s.login(settings.GMAIL_USER, settings.GMAIL_APP_PASSWORD)
            s.send_message(msg)
        return True, None
    except Exception as e:  # noqa: BLE001
        log.warning("Invio email fallito a %s: %s", to_email, e)
        return False, str(e)
