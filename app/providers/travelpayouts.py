"""Provider Travelpayouts (Aviasales) Data API: gratuito, copertura low-cost.

Prezzi da catalogo (indicativi). Auth via query param `token` (+ `marker`).
Docs: https://support.travelpayouts.com/hc/en-us/categories/200358578
NB: gli endpoint della Data API possono variare; parsing difensivo con fallback.
"""
from __future__ import annotations

import logging

import httpx

from ..config import settings
from .base import DateDeal, DestinationDeal, FlightOffer, FlightProvider, Source

log = logging.getLogger("flynotify.travelpayouts")


class TravelpayoutsClient(FlightProvider):
    name = "travelpayouts"

    @property
    def enabled(self) -> bool:
        return bool(settings.TRAVELPAYOUTS_TOKEN)

    def _client(self) -> httpx.Client:
        return httpx.Client(base_url=settings.TRAVELPAYOUTS_BASE_URL, timeout=15)

    def _params(self, **kw) -> dict:
        base = {"token": settings.TRAVELPAYOUTS_TOKEN,
                "currency": settings.TRAVELPAYOUTS_CURRENCY}
        if settings.TRAVELPAYOUTS_MARKER:
            base["marker"] = settings.TRAVELPAYOUTS_MARKER
        base.update({k: v for k, v in kw.items() if v is not None})
        return base

    def search_offers(self, origin, destination, depart_date, return_date=None,
                      adults=1, currency="EUR") -> list[FlightOffer]:
        if not self.enabled:
            return []
        params = self._params(origin=origin, destination=destination,
                               departure_at=depart_date, return_at=return_date,
                               sorting="price", unique="false", limit=20,
                               one_way=(return_date is None))
        try:
            with self._client() as c:
                self.calls += 1
                r = c.get("/aviasales/v3/prices_for_dates", params=params)
                r.raise_for_status()
                out = []
                for d in r.json().get("data", []):
                    price = float(d.get("price", 0) or 0)
                    if price <= 0:
                        continue
                    carrier = d.get("airline")
                    out.append(FlightOffer(
                        origin=d.get("origin", origin),
                        destination=d.get("destination", destination),
                        depart_date=(d.get("departure_at") or depart_date)[:10],
                        return_date=(d.get("return_at") or return_date or None),
                        price=price, currency=currency.upper(),
                        stops=d.get("transfers"),
                        carriers=[carrier] if carrier else [],
                        source=Source(provider=self.name, carrier=carrier),
                    ))
                return out
        except Exception as e:  # noqa: BLE001
            log.warning("Travelpayouts prices_for_dates error: %s", e)
            return []

    def inspiration_search(self, origin, max_price=None, currency="EUR") -> list[DestinationDeal]:
        if not self.enabled:
            return []
        params = self._params(origin=origin, one_way="false", period_type="year",
                              sorting="price", limit=30, show_to_affiliates="true")
        try:
            with self._client() as c:
                self.calls += 1
                r = c.get("/v2/prices/latest", params=params)
                r.raise_for_status()
                out = []
                for d in r.json().get("data", []):
                    price = float(d.get("value", 0) or 0)
                    if price <= 0 or (max_price and price > max_price):
                        continue
                    out.append(DestinationDeal(
                        origin=d.get("origin", origin), destination=d.get("destination"),
                        depart_date=d.get("depart_date"), return_date=d.get("return_date"),
                        price=price, currency=currency.upper(), indicative=True,
                        source=Source(provider=self.name),
                    ))
                return out
        except Exception as e:  # noqa: BLE001
            log.warning("Travelpayouts prices/latest error: %s", e)
            return []

    def cheapest_dates(self, origin, destination, currency="EUR") -> list[DateDeal]:
        if not self.enabled:
            return []
        params = self._params(origin=origin, destination=destination,
                              calendar_type="departure_date")
        try:
            with self._client() as c:
                self.calls += 1
                r = c.get("/v1/prices/calendar", params=params)
                r.raise_for_status()
                data = r.json().get("data", {})
                out = []
                for dep_date, info in data.items():
                    price = float(info.get("price", 0) or 0)
                    if price <= 0:
                        continue
                    out.append(DateDeal(
                        origin=origin, destination=destination,
                        depart_date=dep_date, return_date=info.get("return_at"),
                        price=price, currency=currency.upper(),
                        source=Source(provider=self.name),
                    ))
                return out
        except Exception as e:  # noqa: BLE001
            log.warning("Travelpayouts prices/calendar error: %s", e)
            return []
