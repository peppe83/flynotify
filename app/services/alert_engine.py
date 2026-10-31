"""Alert Engine: decide se un prezzo merita un avviso.

Strategie:
  - threshold : prezzo <= soglia (target_price)
  - drop      : prezzo <= media ultimi 7 gg * (1 - DROP_PCT)
  - deal      : nuovo minimo storico (o, senza storico, sotto soglia)
Anti-spam: notifica solo se migliora l'ultimo prezzo già notificato.
"""
from __future__ import annotations

import hashlib
import statistics
from datetime import date

DROP_PCT = 0.15


def build_dedupe_key(alert_id: str, price: float, day: date | None = None) -> str:
    day = day or date.today()
    raw = f"{alert_id}:{round(float(price))}:{day.isoformat()}"
    return hashlib.sha256(raw.encode()).hexdigest()


def should_notify(alert, price: float, history_prices: list[float],
                  last_notified_price: float | None) -> tuple[bool, str | None]:
    target = float(alert.target_price) if alert.target_price is not None else None
    reason: str | None = None

    if alert.strategy == "threshold":
        if target is None or price > target:
            return False, None
        reason = "below_target"

    elif alert.strategy == "drop":
        if not history_prices:
            return False, None
        avg = statistics.mean(history_prices)
        if price > avg * (1 - DROP_PCT):
            return False, None
        reason = "price_drop"

    elif alert.strategy == "deal":
        if history_prices:
            if price > min(history_prices):
                return False, None
            reason = "good_deal"
        elif target is not None and price <= target:
            reason = "good_deal"
        else:
            return False, None
    else:
        return False, None

    # Solo miglioramenti: niente avviso se non è migliore dell'ultimo notificato
    if last_notified_price is not None and price >= last_notified_price:
        return False, None

    return True, reason
