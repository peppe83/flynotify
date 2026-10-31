# flynotify

Ricerca voli (multi-provider Amadeus + Travelpayouts), alert sui prezzi con
**sospensione**, email riepilogativa via Gmail, ruoli utente/admin/superadmin.
UI responsive (Bootstrap) per telefono e tablet. Pagine sotto autenticazione,
tranne la home e login/registrazione.

## Requisiti
- Python 3.11+
- MySQL 8 (in produzione). In sviluppo, senza credenziali DB, usa SQLite in automatico.

## Setup

```bat
cd /d D:\webserver\apache24\flynotify
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Compila `.env` con le tue chiavi (vedi Appendice A/B del documento di architettura):
- `AMADEUS_CLIENT_ID` / `AMADEUS_CLIENT_SECRET`
- `TRAVELPAYOUTS_TOKEN` / `TRAVELPAYOUTS_MARKER`
- `GMAIL_USER` / `GMAIL_APP_PASSWORD`
- per MySQL: `DB_*` (oppure `DATABASE_URL=mysql+pymysql://user:pass@host/flynotify?charset=utf8mb4`)

> Senza chiavi l'app parte lo stesso: la ricerca restituirà risultati vuoti e le
> email non verranno inviate, ma potrai navigare l'interfaccia (DB su SQLite).

## Primo avvio

```bat
REM crea il primo superadmin
python -m app.seed admin@example.com LaTuaPassword "Nome Cognome"

REM avvia il server
run.bat
```

Apri http://127.0.0.1:8000

## Worker (alert + email)
Lo script controlla i prezzi e invia i digest. Va lanciato da **Windows Task
Scheduler** (tick base ~30 min; ogni utente ha poi il suo intervallo):

```bat
schtasks /Create /TN "flynotify-worker" /TR "D:\webserver\apache24\flynotify\run_worker.bat" /SC MINUTE /MO 30 /RU SYSTEM /RL LIMITED /F
```

Esecuzione manuale per prova:

```bat
python -m app.worker
```

## Struttura
```
app/
  main.py            FastAPI (monta router, static, template)
  config.py          impostazioni da .env
  db.py / models.py  SQLAlchemy (MySQL/SQLite)
  security.py deps.py auth JWT via cookie + ruoli
  providers/         AmadeusClient, TravelpayoutsClient (interfaccia comune)
  services/          search (merge multi-provider), alert_engine, email, guide
  routers/           pages, auth, search, alerts, prefs, admin
  worker.py          worker schedulato
  seed.py            crea il superadmin
templates/           pagine Bootstrap responsive
static/              css + js
```

## Note
- **Nessuna cache persistente** dei prezzi: chiamate live a ogni ricerca/ciclo;
  solo cache di esecuzione (in memoria, per singola richiesta/run).
- I prezzi sono **indicativi**; l'app mostra la **fonte** (provider + compagnia),
  non link di prenotazione.
- La scheda-destinazione (Gemini/eventi/clima) è opzionale: `ENABLE_GUIDE=true`.
