"""Scheda destinazione (opzionale, dietro ENABLE_GUIDE).

Fonti free: Open-Meteo (geocoding + clima, no key), Ticketmaster (eventi),
Google Gemini (overview/itinerario, ancorato ai dati). Tutto best-effort:
se una fonte non è configurata o fallisce, il campo viene semplicemente omesso.
Nessun dato persistito qui (la cache/tabelle sono un'ottimizzazione successiva).
"""
from __future__ import annotations

import logging

import httpx

from ..config import settings

log = logging.getLogger("flynotify.guide")


def _geocode(q: str) -> dict | None:
    try:
        r = httpx.get("https://geocoding-api.open-meteo.com/v1/search",
                      params={"name": q, "count": 1, "language": "it"}, timeout=12)
        r.raise_for_status()
        res = r.json().get("results") or []
        return res[0] if res else None
    except Exception as e:  # noqa: BLE001
        log.warning("geocode error: %s", e)
        return None


def _climate(lat: float, lon: float, date_from: str, date_to: str) -> dict | None:
    try:
        r = httpx.get(f"{settings.OPENMETEO_BASE_URL}/v1/forecast", params={
            "latitude": lat, "longitude": lon,
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum",
            "start_date": date_from, "end_date": date_to, "timezone": "auto",
        }, timeout=12)
        r.raise_for_status()
        daily = r.json().get("daily", {})
        tmax = daily.get("temperature_2m_max") or []
        tmin = daily.get("temperature_2m_min") or []
        if not tmax:
            return None
        return {"t_max_avg": round(sum(tmax) / len(tmax), 1),
                "t_min_avg": round(sum(tmin) / len(tmin), 1)}
    except Exception as e:  # noqa: BLE001
        log.info("climate non disponibile: %s", e)
        return None


def _events(city: str, date_from: str, date_to: str) -> list[dict]:
    if not settings.TICKETMASTER_API_KEY:
        return []
    try:
        r = httpx.get("https://app.ticketmaster.com/discovery/v2/events.json", params={
            "city": city, "startDateTime": f"{date_from}T00:00:00Z",
            "endDateTime": f"{date_to}T23:59:59Z", "size": 5,
            "apikey": settings.TICKETMASTER_API_KEY,
        }, timeout=12)
        r.raise_for_status()
        evs = r.json().get("_embedded", {}).get("events", [])
        return [{"name": e.get("name"),
                 "date": e.get("dates", {}).get("start", {}).get("localDate")}
                for e in evs]
    except Exception as e:  # noqa: BLE001
        log.info("eventi non disponibili: %s", e)
        return []


def _gemini_overview(place: str, facts: dict) -> str | None:
    if not (settings.ENABLE_LLM and settings.GEMINI_API_KEY):
        return None
    prompt = (
        f"Scrivi in italiano una breve guida (max 120 parole) per un viaggio a {place}. "
        f"Includi: tipo di meta, 3-4 cose da vedere, cosa vedere nei dintorni, se serve "
        f"l'auto o bastano i mezzi pubblici, e un cenno al trasferimento aeroporto-centro. "
        f"Basati SOLO su questi dati, non inventare numeri: {facts}"
    )
    try:
        url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
               f"{settings.GEMINI_MODEL}:generateContent?key={settings.GEMINI_API_KEY}")
        r = httpx.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=25)
        r.raise_for_status()
        cand = r.json().get("candidates", [])
        if cand:
            return cand[0]["content"]["parts"][0]["text"].strip()
    except Exception as e:  # noqa: BLE001
        log.info("Gemini non disponibile: %s", e)
    return None


def get_guide(q: str, date_from: str, date_to: str) -> dict:
    """q = nome città (o IATA). Ritorna i campi disponibili."""
    geo = _geocode(q)
    if not geo:
        return {"query": q, "available": False,
                "message": "Dati destinazione non disponibili."}
    city = geo.get("name", q)
    country = geo.get("country")
    climate = _climate(geo["latitude"], geo["longitude"], date_from, date_to)
    events = _events(city, date_from, date_to)
    facts = {"città": city, "paese": country, "clima": climate,
             "eventi": [e["name"] for e in events]}
    overview = _gemini_overview(f"{city} ({country})", facts)
    return {
        "query": q, "available": True,
        "city": city, "country": country,
        "climate": climate, "events": events, "overview": overview,
    }
