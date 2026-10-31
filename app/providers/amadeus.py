"""Provider Amadeus Self-Service (GDS): dati live e dettagliati.

Docs: https://developers.amadeus.com — OAuth2 client_credentials, poi:
  GET /v2/shopping/flight-offers
  GET /v1/shopping/flight-destinations   (Flight Inspiration Search)
  GET /v1/shopping/flight-dates          (Flight Cheapest Date Search)
"""
from __future__ import annotations

import logging
import time

import httpx

from ..config import settings
from .base import DateDeal, DestinationDeal, FlightOffer, FlightProvider, Source

log = logging.getLogger("flynotify.amadeus")


class AmadeusClient(FlightProvider):
    name = "amadeus"

    def __init__(self) -> None:
        super().__init__()
        self._token: str | None = None
        self._token_exp: float = 0.0

    @property
    def enabled(self) -> bool:
        return bool(settings.AMADEUS_CLIENT_ID and settings.AMADEUS_CLIENT_SECRET)

    # -- interno ----------------------------------------------------------
    def _client(self) -> httpx.Client:
        return httpx.Client(base_url=settings.AMADEUS_BASE_URL,
                            timeout=settings.AMADEUS_TIMEOUT_SECONDS)

    def _get_token(self) -> str | None:
        if not self.enabled:
            return None
        if self._token and time.time() < self._token_exp - 30:
            return self._token
        try:
            with self._client() as c:
                self.calls += 1
                r = c.post(
                    "/v1/security/oauth2/token",
                    data={
                        "grant_type": "client_credentials",
                        "client_id": settings.AMADEUS_CLIENT_ID,
                        "client_secret": settings.AMADEUS_CLIENT_SECRET,
                    },
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )
                r.raise_for_status()
                data = r.json()
                self._token = data["access_token"]
                self._token_exp = time.time() + int(data.get("expires_in", 1799))
                return self._token
        except Exception as e:  # noqa: BLE001
            log.warning("Amadeus token error: %s", e)
            return None

    def _headers(self) -> dict | None:
        tok = self._get_token()
        return {"Authorization": f"Bearer {tok}"} if tok else None

    # -- API --------------------------------------------------------------
    def search_offers(self, origin, destination, depart_date, return_date=None,
                      adults=1, currency="EUR") -> list[FlightOffer]:
        headers = self._headers()
        if not headers:
            return []
        params = {
            "originLocationCode": origin,
            "destinationLocationCode": destination,
            "departureDate": depart_date,
            "adults": adults,
            "currencyCode": currency,
            "max": 20,
        }
        if return_date:
            params["returnDate"] = return_date
        try:
            with self._client() as c:
                self.calls += 1
                r = c.get("/v2/shopping/flight-offers", params=params, headers=headers)
                r.raise_for_status()
                return [self._parse_offer(o, origin, destination, depart_date,
                                          return_date, currency)
                        for o in r.json().get("data", [])]
        except Exception as e:  # noqa: BLE001
            log.warning("Amadeus flight-offers error: %s", e)
            return []

    def _parse_offer(self, o, origin, destination, depart_date, return_date, currency):
        price = float(o.get("price", {}).get("total", 0) or 0)
        itins = o.get("itineraries", [])
        first = itins[0] if itins else {}
        segs = first.get("segments", [])
        stops = max(len(segs) - 1, 0)
        carriers = sorted({s.get("carrierCode") for s in segs if s.get("carrierCode")})
        return FlightOffer(
            origin=origin, destination=destination,
            depart_date=depart_date, return_date=return_date,
            price=price, currency=currency,
            stops=stops, duration=first.get("duration"),
            carriers=carriers,
            source=Source(provider=self.name, carrier=carriers[0] if carriers else None),
        )

    def inspiration_search(self, origin, max_price=None, currency="EUR") -> list[DestinationDeal]:
        headers = self._headers()
        if not headers:
            return []
        params = {"origin": origin}
        if max_price:
            params["maxPrice"] = int(max_price)
        try:
            with self._client() as c:
                self.calls += 1
                r = c.get("/v1/shopping/flight-destinations", params=params, headers=headers)
                r.raise_for_status()
                out = []
                for d in r.json().get("data", []):
                    out.append(DestinationDeal(
                        origin=origin, destination=d.get("destination"),
                        depart_date=d.get("departureDate"), return_date=d.get("returnDate"),
                        price=float(d.get("price", {}).get("total", 0) or 0),
                        currency=currency, indicative=True,
                        source=Source(provider=self.name),
                    ))
                return out
        except Exception as e:  # noqa: BLE001
            log.warning("Amadeus flight-destinations error: %s", e)
            return []

    def cheapest_dates(self, origin, destination, currency="EUR") -> list[DateDeal]:
        headers = self._headers()
        if not headers:
            return []
        try:
            with self._client() as c:
                self.calls += 1
                r = c.get("/v1/shopping/flight-dates",
                          params={"origin": origin, "destination": destination}, headers=headers)
                r.raise_for_status()
                out = []
                for d in r.json().get("data", []):
                    out.append(DateDeal(
                        origin=origin, destination=destination,
                        depart_date=d.get("departureDate"), return_date=d.get("returnDate"),
                        price=float(d.get("price", {}).get("total", 0) or 0),
                        currency=currency, source=Source(provider=self.name),
                    ))
                return out
        except Exception as e:  # noqa: BLE001
            log.warning("Amadeus flight-dates error: %s", e)
            return []
