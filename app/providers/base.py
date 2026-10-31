"""Modelli di dominio normalizzati e interfaccia comune dei provider voli."""
from __future__ import annotations

from abc import ABC
from typing import Optional

from pydantic import BaseModel


class Source(BaseModel):
    provider: str                     # 'amadeus' | 'travelpayouts'
    carrier: Optional[str] = None     # compagnia (validating carrier)


class FlightOffer(BaseModel):
    origin: str
    destination: str
    depart_date: str
    return_date: Optional[str] = None
    price: float
    currency: str = "EUR"
    stops: Optional[int] = None
    duration: Optional[str] = None
    carriers: list[str] = []
    source: Source

    @property
    def dedupe_key(self) -> str:
        return f"{self.origin}-{self.destination}-{self.depart_date}-{self.return_date}"


class DestinationDeal(BaseModel):
    origin: str
    destination: str
    depart_date: Optional[str] = None
    return_date: Optional[str] = None
    price: float
    currency: str = "EUR"
    indicative: bool = True
    source: Source


class DateDeal(BaseModel):
    origin: str
    destination: str
    depart_date: str
    return_date: Optional[str] = None
    price: float
    currency: str = "EUR"
    source: Source


class FlightProvider(ABC):
    """Interfaccia comune. Ogni implementazione deve essere resiliente:
    in caso di credenziali mancanti o errori di rete restituisce liste vuote."""

    name: str = "base"

    def __init__(self) -> None:
        self.calls: int = 0  # contatore chiamate effettuate (per quota/log)

    @property
    def enabled(self) -> bool:
        return False

    def search_offers(self, origin: str, destination: str, depart_date: str,
                      return_date: str | None = None, adults: int = 1,
                      currency: str = "EUR") -> list[FlightOffer]:
        return []

    def inspiration_search(self, origin: str, max_price: float | None = None,
                           currency: str = "EUR") -> list[DestinationDeal]:
        return []

    def cheapest_dates(self, origin: str, destination: str,
                       currency: str = "EUR") -> list[DateDeal]:
        return []
