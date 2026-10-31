"""SearchService: orchestratore multi-provider.

Interroga i provider abilitati, normalizza, UNISCE e DEDUPLICA tenendo il
prezzo minimo, ordina per prezzo. Nessuna cache persistente: solo cache di
esecuzione (RunCache) per non ripetere chiamate identiche nello stesso run.
"""
from __future__ import annotations

from ..providers.amadeus import AmadeusClient
from ..providers.base import DateDeal, DestinationDeal, FlightOffer
from ..providers.run_cache import RunCache
from ..providers.travelpayouts import TravelpayoutsClient


class SearchService:
    def __init__(self, run_cache: RunCache | None = None) -> None:
        # Travelpayouts per la scoperta (free, low-cost); Amadeus per il dettaglio live.
        self.providers = [TravelpayoutsClient(), AmadeusClient()]
        self.cache = run_cache or RunCache()

    @property
    def enabled_providers(self):
        return [p for p in self.providers if p.enabled]

    @property
    def total_calls(self) -> int:
        return sum(p.calls for p in self.providers)

    # -- ricerche ---------------------------------------------------------
    def search_offers(self, origin, destination, depart_date, return_date=None,
                      adults=1, currency="EUR") -> list[FlightOffer]:
        results: list[FlightOffer] = []
        for p in self.enabled_providers:
            key = f"offers:{p.name}:{origin}:{destination}:{depart_date}:{return_date}:{adults}:{currency}"
            results += self.cache.get_or_call(
                key, lambda p=p: p.search_offers(origin, destination, depart_date,
                                                  return_date, adults, currency))
        return self._dedup_offers(results)

    def explore(self, origin, max_price=None, currency="EUR") -> list[DestinationDeal]:
        results: list[DestinationDeal] = []
        for p in self.enabled_providers:
            key = f"insp:{p.name}:{origin}:{max_price}:{currency}"
            results += self.cache.get_or_call(
                key, lambda p=p: p.inspiration_search(origin, max_price, currency))
        return self._dedup_destinations(results)

    def cheapest_dates(self, origin, destination, currency="EUR") -> list[DateDeal]:
        results: list[DateDeal] = []
        for p in self.enabled_providers:
            key = f"dates:{p.name}:{origin}:{destination}:{currency}"
            results += self.cache.get_or_call(
                key, lambda p=p: p.cheapest_dates(origin, destination, currency))
        return sorted(results, key=lambda d: d.price)

    # -- merge/dedup ------------------------------------------------------
    @staticmethod
    def _dedup_offers(offers: list[FlightOffer]) -> list[FlightOffer]:
        best: dict[str, FlightOffer] = {}
        for o in offers:
            cur = best.get(o.dedupe_key)
            if cur is None or o.price < cur.price:
                best[o.dedupe_key] = o
        return sorted(best.values(), key=lambda o: o.price)

    @staticmethod
    def _dedup_destinations(deals: list[DestinationDeal]) -> list[DestinationDeal]:
        best: dict[str, DestinationDeal] = {}
        for d in deals:
            cur = best.get(d.destination)
            if cur is None or d.price < cur.price:
                best[d.destination] = d
        return sorted(best.values(), key=lambda d: d.price)

    # -- helper per il worker --------------------------------------------
    def best_offer_for_alert(self, alert) -> FlightOffer | None:
        """Ritorna l'offerta migliore (prezzo minimo) per un alert."""
        currency = alert.currency or "EUR"
        depart = alert.depart_from.isoformat()
        ret = alert.return_from.isoformat() if alert.return_from else None

        if alert.destination == "ANY":
            deals = self.explore(alert.origin,
                                 float(alert.target_price) if alert.target_price else None,
                                 currency)
            if not deals:
                return None
            d = deals[0]
            offers = self.search_offers(alert.origin, d.destination,
                                        d.depart_date or depart, d.return_date or ret,
                                        alert.adults, currency)
            if offers:
                return offers[0]
            from ..providers.base import FlightOffer as FO, Source
            return FO(origin=alert.origin, destination=d.destination,
                      depart_date=d.depart_date or depart, return_date=d.return_date,
                      price=d.price, currency=d.currency, source=d.source)

        offers = self.search_offers(alert.origin, alert.destination, depart, ret,
                                    alert.adults, currency)
        return offers[0] if offers else None
