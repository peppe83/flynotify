"""Schemi Pydantic per le richieste/risposte JSON."""
from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel, Field


class AlertCreate(BaseModel):
    origin: str = Field(min_length=3, max_length=3)
    destination: str = Field(min_length=3, max_length=3)   # IATA o 'ANY'
    depart_from: date
    depart_to: Optional[date] = None
    return_from: Optional[date] = None
    return_to: Optional[date] = None
    adults: int = 1
    cabin: str = "ECONOMY"
    max_stops: Optional[int] = None
    depart_dow: Optional[int] = None
    return_dow: Optional[int] = None
    depart_time_from: Optional[str] = None
    depart_time_to: Optional[str] = None
    target_price: Optional[float] = None
    currency: str = "EUR"
    strategy: str = "threshold"


class AlertOut(BaseModel):
    id: str
    origin: str
    destination: str
    depart_from: date
    depart_to: date
    return_from: Optional[date]
    return_to: Optional[date]
    adults: int
    target_price: Optional[float]
    currency: str
    strategy: str
    status: str
    last_price: Optional[float]
    last_checked: Optional[str] = None

    class Config:
        from_attributes = True


class PreferencesUpdate(BaseModel):
    poll_interval_hours: int
    currency: str = "EUR"
    timezone: str = "Europe/Rome"


class RoleUpdate(BaseModel):
    role: str
