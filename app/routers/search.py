"""Endpoint di ricerca (JSON), sotto autenticazione."""
from fastapi import APIRouter, Depends, HTTPException, Query

from ..config import settings
from ..deps import get_current_user
from ..providers.run_cache import RunCache
from ..services.search import SearchService

router = APIRouter(prefix="/api", tags=["search"])


def _service() -> SearchService:
    return SearchService(RunCache())


@router.get("/search")
def search(origin: str, destination: str, departDate: str,
           returnDate: str | None = None, adults: int = 1,
           currency: str = "EUR", _user=Depends(get_current_user)):
    svc = _service()
    offers = svc.search_offers(origin.upper(), destination.upper(), departDate,
                               returnDate, adults, currency.upper())
    return {"query": {"origin": origin, "destination": destination, "date": departDate},
            "offers": [o.model_dump() for o in offers],
            "providers": [p.name for p in svc.enabled_providers], "fresh": True}


@router.get("/explore")
def explore(origin: str, maxPrice: float | None = None, currency: str = "EUR",
            _user=Depends(get_current_user)):
    svc = _service()
    deals = svc.explore(origin.upper(), maxPrice, currency.upper())
    return {"query": {"origin": origin, "maxPrice": maxPrice},
            "destinations": [d.model_dump() for d in deals],
            "providers": [p.name for p in svc.enabled_providers], "fresh": True}


@router.get("/cheapest-dates")
def cheapest_dates(origin: str, destination: str, currency: str = "EUR",
                   _user=Depends(get_current_user)):
    svc = _service()
    deals = svc.cheapest_dates(origin.upper(), destination.upper(), currency.upper())
    return {"dates": [d.model_dump() for d in deals], "fresh": True}


@router.get("/guide")
def guide(q: str, date_from: str = Query(...), date_to: str = Query(...),
          _user=Depends(get_current_user)):
    if not settings.ENABLE_GUIDE:
        raise HTTPException(status_code=404, detail="Scheda destinazione disattivata")
    from ..services.guide import get_guide
    return get_guide(q, date_from, date_to)
