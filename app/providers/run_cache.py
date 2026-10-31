"""Cache di ESECUZIONE (in-run): vive solo per la durata della richiesta/ciclo.
Evita di ripetere la stessa chiamata API nello stesso run. Nessuna persistenza:
i prezzi dei voli restano sempre freschi tra un ciclo e l'altro."""
from typing import Any, Callable


class RunCache:
    def __init__(self) -> None:
        self._store: dict[str, Any] = {}

    def get_or_call(self, key: str, fn: Callable[[], Any]) -> Any:
        if key in self._store:
            return self._store[key]
        value = fn()
        self._store[key] = value
        return value

    def clear(self) -> None:
        self._store.clear()
