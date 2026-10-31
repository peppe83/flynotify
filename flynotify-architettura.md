# flynotify — Documento di Architettura

> Sistema di ricerca voli, alert intelligenti e notifiche email.
> Versione 1.0 — 30 ottobre 2026

---

## 1. Visione e obiettivi

flynotify permette a un utente di:

1. **Cercare voli** per una tratta e un periodo (date flessibili, scali, compagnie), oppure esplorare **"Ovunque"** per scoprire le mete più economiche da un aeroporto di partenza.
2. **Creare alert** su una tratta con un prezzo-soglia o una logica "avvisami se scende".
3. **Ricevere un'email riepilogativa** con tutti gli avvisi scattati, alla cadenza che **ogni utente sceglie** per sé (default 6h, minimo 2h fissato dall'admin).

Il cuore del prodotto non è la ricerca "una tantum", ma il **monitoraggio continuo nel tempo**: il sistema ricontrolla periodicamente i prezzi e decide *in autonomia* quando vale la pena avvisare l'utente ("alert intelligenti", non spam).

### Principi guida

- **Dati sempre freschi (nessuna cache persistente)**: le risposte non vengono memorizzate tra un ciclo e l'altro. Ogni ricerca interattiva e ogni ciclo dello scheduler chiamano l'API in tempo reale. L'unica cache ammessa è **di esecuzione (in-run)**: un dizionario in memoria vivo solo per la durata del singolo run/richiesta, che deduplica le chiamate identiche fatte in quel momento e poi viene scartato. Così si evitano chiamate doppie nello stesso ciclo senza mai servire prezzi vecchi.
- **Idempotenza delle notifiche**: lo stesso alert non deve generare due email identiche a distanza di minuti.
- **Separazione search / monitoring**: la ricerca interattiva e il polling in background sono flussi distinti.
- **Provider-agnostico**: l'integrazione con l'API voli è isolata dietro un'interfaccia, così da poter cambiare fornitore senza riscrivere la logica di business.

---

## 1bis. Versione iniziale — MVP in pochi giorni

Il resto del documento descrive il prodotto completo (alert, email, monitoraggio). La **prima versione**, però, è molto più piccola: **solo ricerca voli**. È ciò che si costruisce in pochi giorni e che dà subito valore.

### Cosa include l'MVP

- ✅ Aeroporto di **partenza**
- ✅ Destinazione **specifica** oppure **"Ovunque"**
- ✅ Ricerca dei **prezzi più bassi**
- ✅ **Ordinamento per costo** (crescente)
- ✅ **Fonte del prezzo** (provider dei dati + compagnia), **senza** link di prenotazione

### Cosa NON include (rinviato alle fasi successive)

- ❌ Account utente / login
- ❌ Alert e notifiche email
- ❌ Worker schedulato (Task Scheduler)
- ❌ Storico prezzi
- ❌ Scheda-guida della destinazione (§2quater) — feature ricca, successiva

### Stack dell'MVP

| Livello | Tecnologia |
|---|---|
| Frontend | **HTML + Bootstrap** (una pagina, nessun framework JS) |
| Backend | **FastAPI** (Python) con 2 endpoint |
| API voli | **Amadeus** (ambiente test, gratuito) |
| Database | **MySQL — facoltativo**: non serve per la sola ricerca; utile solo per loggare le ricerche o salvare preferenze |

> Senza utenti né alert, l'MVP **non ha bisogno di database**: ogni ricerca chiama Amadeus in tempo reale. MySQL entra in gioco con la versione 2 (alert/utenti).

### Architettura dell'MVP (minima)

```
  Browser (HTML + Bootstrap)
        │  fetch JSON
        ▼
  FastAPI
   ├─ GET /search?origin=MXP&destination=LON&date=2026-11-10   → offerte reali, ordinate per prezzo
   └─ GET /explore?origin=MXP&month=2026-11                    → mete "Ovunque", ordinate per prezzo
        │
        ▼
  AmadeusClient  (OAuth, chiamate live a ogni richiesta)
        │
        ▼
  Amadeus API (test)
```

### Fonte del prezzo (niente link di prenotazione)

flynotify **non mostra un link di prenotazione** e non gestisce acquisti: mostra il prezzo e **da dove arriva**. Ogni risultato riporta quindi:

- **Provider dei dati**: chi ha fornito il prezzo (es. `Amadeus`; in futuro `Travelpayouts`).
- **Compagnia/e** (validating carrier): es. `Lufthansa (LH)`, ricavata dall'offerta.

In interfaccia compare un'etichetta tipo **"Fonte: Amadeus · LH"** accanto al prezzo. Niente pagamenti né redirect commerciali: l'utente sa quanto costa e chi lo offre, e decide per conto suo dove prenotare.

### Struttura del progetto (proposta)

```
flynotify/
├─ app/
│  ├─ main.py            # FastAPI: /search, /explore
│  ├─ amadeus_client.py  # OAuth + chiamate live + normalizzazione
│  └─ models.py          # Pydantic: FlightOffer, DestinationDeal (incl. fonte prezzo)
├─ static/
│  └─ index.html         # UI: form + risultati (Bootstrap)
├─ .env                  # AMADEUS_CLIENT_ID / SECRET (non nel repo)
├─ requirements.txt
└─ run.bat               # avvio uvicorn
```

### Piano (≈ pochi giorni)

1. **Giorno 1** — `AmadeusClient`: OAuth + `flight-offers` + normalizzazione (chiamate live); endpoint `/search`.
2. **Giorno 2** — endpoint `/explore` (flight-destinations); normalizzazione della **fonte prezzo** (provider + compagnia) nei modelli.
3. **Giorno 3** — `index.html` con Bootstrap: form (partenza, destinazione/"Ovunque", data), risultati ordinati per prezzo con etichetta **"Fonte: …"**; rifinitura ed errori.

Da qui la versione completa (questo documento) è un'**estensione additiva**: si aggiungono MySQL, utenti, alert, email e worker senza buttare via nulla dell'MVP.

---

## 2. Scelta dell'API voli

La scelta del provider è la decisione tecnica più importante, perché condiziona costi, copertura e funzionalità.

| Provider | Punti di forza | Limiti | Adatto a |
|---|---|---|---|
| **Amadeus Self-Service** ⭐ | Free tier generoso, *Flight Offers Search*, *Flight Price Analysis* (prezzo "basso/medio/alto"), dati aeroporti/compagnie | Inventario test in sandbox più limitato; **poche low-cost** | **Primario: dettaglio live** |
| **Travelpayouts (Aviasales)** ⭐ | Gratuito, **copertura low-cost** (Ryanair/Wizz/easyJet), ricerca "Ovunque"/calendario | Prezzi da catalogo (indicativi), orientato affiliati | **Primario: scoperta/offerte** (§2cinque) |
| Kiwi.com (Tequila) | Prezzi aggressivi, split ticket/self-transfer | Richiede approvazione partner | Fonte aggiuntiva (futuro) |
| Duffel | API moderna | Orientato al booking, non al price-watching | Fuori scope (no booking) |
| Aviationstack | Stato voli real-time | **Non fornisce prezzi** | Fuori scope |

**Raccomandazione:** architettura **multi-provider** (§4): **Travelpayouts** (gratuito, copre le low-cost) per la scoperta ampia delle offerte e **Amadeus** per il dettaglio live e la ri-validazione. L'MVP può partire col solo Amadeus e aggiungere Travelpayouts subito dopo. Amadeus espone gli endpoint chiave per flynotify:

- `GET /v1/shopping/flight-destinations` — **Flight Inspiration Search**: data un'origine, restituisce le destinazioni più economiche. È il motore della ricerca **"Ovunque"**.
- `GET /v1/shopping/flight-dates` — **Flight Cheapest Date Search**: per una tratta, le date più convenienti (utile per le "date flessibili").
- `GET /v2/shopping/flight-offers` — **Flight Offers Search**: offerte voli reali e dettagliate per una tratta specifica (date, passeggeri, scali, prezzo live).
- `GET /v1/analytics/itinerary-price-metrics` — metriche di prezzo storiche, utili per decidere se un prezzo è "buono" (strategia `deal`).

L'autenticazione è OAuth2 client-credentials: si ottiene un `access_token` (durata ~30 min) da riusare tra le chiamate.

> Per restare nel **piano gratuito** (sviluppo in ambiente test, produzione entro la quota free, oppure Travelpayouts a costo zero) e per il calcolo del budget di chiamate, vedi **§2ter**.

> **Attenzione alla natura dei dati "Ovunque".** *Flight Inspiration Search* e *Cheapest Date Search* non calcolano i prezzi in tempo reale: leggono un **catalogo pre-calcolato/cache** lato Amadeus. Quindi: (a) la copertura delle origini è limitata (nel sandbox soprattutto grandi hub, più ampia in produzione); (b) i prezzi sono **indicativi**. Il pattern corretto è a due stadi — si usa l'Inspiration Search per *scoprire* le destinazioni interessanti, poi si **ri-valida** la singola destinazione con *Flight Offers Search* per avere il prezzo reale prima di mostrarlo come definitivo o inviarlo in un alert.

> Le chiavi API (`AMADEUS_CLIENT_ID`, `AMADEUS_CLIENT_SECRET`) vanno in variabili d'ambiente / secret manager, **mai** nel codice o nel repo.

---

## 2bis. Le tre modalità di ricerca

Il tool web espone un unico form; la combinazione **destinazione** + **data** seleziona una delle tre modalità. **Tutti i risultati sono ordinati per prezzo crescente.**

| # | Modalità | Input | Endpoint Amadeus | Cosa restituisce |
|---|---|---|---|---|
| 1 | **Classica** | partenza + destinazione (IATA) + data singola o intervallo + passeggeri | `flight-offers` | offerte reali e dettagliate per quella rotta |
| 2 | **Ovunque** | partenza + "Ovunque" + mese/periodo | `flight-destinations` (poi `flight-offers` per il drill-down) | elenco di **destinazioni** dalla più economica |
| 3 | **Mese più economico** | partenza + destinazione + data **flessibile** | `flight-dates` (`viewBy=MONTH`/`DATE`) | elenco di **date** per quella tratta, dalla più economica |

In sintesi: la modalità **1** risponde a *"quanto costa questo volo?"*, la **2** a *"dove posso andare spendendo poco?"*, la **3** a *"quand'è più conveniente andare proprio lì?"*.

### Flusso dell'interfaccia (UX)

```
Form:  [ Partenza: MXP ]  [ Destinazione: ______ / ☑ Ovunque ]
       [ Quando: data andata/ritorno · ± offset giorni · ☑ flessibile/mese ]  [ Passeggeri ]  [ ☐ solo diretti ]  [ Prezzo max ]
       [ Giorni: ☐Lun ☐Ven ☐Dom … ]  [ Fascia oraria partenza: 18:00–22:00 ]   (filtri opzionali)

   ├─ Dest = IATA  +  data/intervallo ───────► (1) Flight Offers Search
   │                                            → lista voli (orari, scali, prezzo, fonte)
   │
   ├─ Dest = "Ovunque" ──────────────────────► (2) Flight Inspiration Search
   │                                            → griglia/mappa di mete ordinate per prezzo
   │                                              (es. Barcellona 48€, Atene 61€, Lisbona 73€…)
   │                                              └─ click su una meta ──► (1) Flight Offers Search
   │                                                                       (prezzo reale + dettagli)
   │
   └─ Dest = IATA  +  data "flessibile" ─────► (3) Flight Cheapest Date Search
                                                → calendario/elenco date ordinate per prezzo
                                                  (es. 12 gen 512€, feb 548€, mar 503€…)
                                                  └─ click su una data ──► (1) Flight Offers Search
                                                                           (prezzo reale + dettagli)
```

### "Mese più economico" in dettaglio (modalità 3)

1. L'utente fissa **partenza e destinazione** (es. Milano → Tokyo) e lascia la data **flessibile**.
2. flynotify chiama `flight-dates?origin=MIL&destination=TYO&oneWay=false&viewBy=MONTH` (o `DATE` per il dettaglio giornaliero).
3. Riceve `{ dataAndata, dataRitorno, prezzo }` già ordinabili per prezzo → il frontend evidenzia **il mese/giorno più economico**.
4. Al click su una data si lancia *Flight Offers Search* per il **prezzo reale** e i dettagli di volo.

Come per "Ovunque", i prezzi di `flight-dates` provengono dal **catalogo pre-calcolato** di Amadeus: sono indicativi e vanno confermati con *Flight Offers Search*.

### Comportamento "Ovunque" in dettaglio

1. L'utente mette solo la **partenza** (+ eventuali filtri: prezzo massimo, mese, solo diretti, durata viaggio).
2. flynotify chiama `flight-destinations?origin=FCO&maxPrice=...&departureDate=...&oneWay=false&nonStop=false`.
3. Riceve un elenco `{ destinazione, dataAndata, dataRitorno, prezzo }` già ordinato per prezzo; il drill-down con *Flight Offers Search* aggiunge la **fonte** (provider + compagnia).
4. Il frontend mostra le mete come **card / mappa**; i prezzi sono indicativi (etichetta "da 48€").
5. Al click su una meta si lancia *Flight Offers Search* per quel giorno: è qui che compare il **prezzo reale** con la relativa **fonte** (provider + compagnia).

### Ricaduta sugli alert

Questo abilita due tipi di alert:

- **Alert su tratta** (già previsto): "FCO→JFK sotto 400€".
- **Alert "Ovunque"** (nuovo, potente): "da FCO, qualsiasi meta sotto 50€". Il worker usa *Flight Inspiration Search* con `maxPrice` e avvisa quando spunta una destinazione sotto soglia — poi ri-valida con *Flight Offers Search* prima di inviare l'email. Nello schema questo si traduce in `destination = 'ANY'` (vedi §5).

### Limiti da conoscere

- La modalità "Ovunque" dipende dalla **copertura del catalogo Amadeus** per l'origine scelta: per alcuni aeroporti minori potrebbe restituire pochi o nessun risultato. In quel caso il frontend mostra un messaggio e suggerisce un hub vicino.
- I prezzi "Ovunque" sono **indicativi**: vanno sempre confermati con *Flight Offers Search* prima di mostrarli come definitivi o inviarli in un alert.
- **Più aeroporti per la stessa città** (es. Milano = MXP, LIN, BGY): il modo pulito è usare il **codice città IATA** (`MIL` per Milano, `LON` per Londra, `PAR` per Parigi, `TYO` per Tokyo), che Amadeus espande sugli aeroporti della città. Attenzione però: alcuni scali low-cost (p.es. Bergamo/BGY) possono non rientrare nel codice città — in quei casi si fanno **più chiamate** (una per aeroporto) e si **uniscono i risultati**, deduplicando per destinazione e tenendo il prezzo minimo.

### Filtri: giorno della settimana e fascia oraria

Due esigenze tipiche ("un weekend venerdì→domenica", "partenza di sera 18:00–22:00") si gestiscono così:

**Fascia oraria — supportata (nativa + filtro).**
*Flight Offers Search* (versione POST) accetta una finestra oraria sulla partenza:

```jsonc
"originDestinations": [{
  "originLocationCode": "MXP", "destinationLocationCode": "LON",
  "departureDateTimeRange": { "date": "2026-11-13", "time": "20:00:00", "timeWindow": "6H" }
}]
```

`time` + `timeWindow` (es. `6H` = ±6 ore) restringono già i risultati; un **filtro lato app** sugli orari dei segmenti rifinisce la fascia esatta (es. 18:00–22:00) e si applica anche al volo di ritorno.

**Giorno della settimana — non nativo, si fa lato app.**
L'API ragiona su **date precise**, non su "tutti i venerdì". flynotify lo realizza espandendo il periodo scelto nelle coppie di date che rispettano il pattern:

1. L'utente sceglie partenza/ritorno per **giorno** (es. VEN→DOM) e un **periodo** (es. novembre 2026).
2. flynotify calcola le coppie di date corrispondenti (tutti i Ven/Dom del mese).
3. **Scoperta a basso costo**: una chiamata a *Cheapest Date Search* (`flight-dates`) sul mese, poi si **filtrano** le date tenendo solo quelle Ven/Dom → ordinate per prezzo.
4. **Dettaglio**: sulla coppia scelta si lancia *Flight Offers Search* con l'eventuale **fascia oraria**.

> **Attenzione ai costi:** espandere "tutti i venerdì" in offerte live significa **tante chiamate**. Mitigazioni: usare prima `flight-dates` (una sola chiamata) per il grezzo e filtrare i weekday lato app; la **cache di esecuzione** deduplica le date/combinazioni ripetute nello stesso run; limitare il periodo (es. un mese per volta); rispettare l'intervallo per-utente. Per gli **alert** ricorrenti su pattern (es. "weekend sotto 120€"), la valutazione periodica resta una sola ricerca grezza + ri-validazione mirata.

### Date flessibili con offset ±X giorni

L'utente può fissare una **data di andata** e una **di ritorno** e aggiungere un **offset ±X giorni** su una o entrambe (es. "parto il 13/11 ±3, torno il 16/11 ±3"). Due vie, a seconda di X:

**Offset piccolo (≤ 3 giorni) — nativo.**
*Flight Offers Search* accetta una finestra sulla data con `dateWindow`:

```jsonc
"departureDateTimeRange": { "date": "2026-11-13", "dateWindow": "I3D" }   // I3D = ± 3 giorni
```

Si applica sia all'andata sia al ritorno (seconda `originDestinations`). Amadeus restituisce in **una sola chiamata** le combinazioni nella finestra, già confrontabili per prezzo. Il limite nativo è **±3 giorni**.

**Offset grande (> 3 giorni) — lato app.**
Si enumerano le date da `data−X` a `data+X` per andata e ritorno e si cercano le combinazioni. Attenzione: il numero di combinazioni è **combinatorio** `(2X+1) × (2X+1)` → molte chiamate. Mitigazioni: usare *Cheapest Date Search* (`flight-dates`) per lo screening a basso costo, poi *Flight Offers Search* solo sulle combinazioni migliori; la **cache di esecuzione** evita di ripetere combinazioni identiche nello stesso run; cap sull'offset (es. max ±7) nell'interfaccia.

> **Mapping sul modello:** l'offset è una comodità d'interfaccia. Internamente diventa la **finestra di date** già presente nello schema (`alerts.depart_from`/`depart_to` e `return_from`/`return_to`, §5): `depart_from = data_andata − X`, `depart_to = data_andata + X`, idem per il ritorno. Così non serve un campo nuovo e gli alert supportano già l'offset.

---

## 2ter. Fonti dati e budget di chiamate (piano gratuito)

Vincolo reale di partenza: **restare nel gratuito**, con un intervallo **per-utente** (min ~2h), **pochi utenti** e **poche ricerche**. Senza cache persistente ogni ciclo chiama l'API, quindi i numeri dipendono soprattutto da **cadenza** e **tetti**; la cache di esecuzione aiuta solo a non ripetere chiamate identiche nello stesso run.

### Opzioni gratuite

| Fonte | Gratis? | Prezzi? | "Ovunque" / "Date economiche"? | Note |
|---|---|---|---|---|
| **Amadeus Self-Service** ⭐ | Ambiente **test gratuito**; in produzione **quota mensile gratuita** poi a consumo | Sì | Sì (entrambi nativi) | Qualità migliore, copre tutte e 3 le modalità. Ideale in test per sviluppo |
| **Travelpayouts (Aviasales) Data API** ⭐ | **Sì, completamente gratuito** (token di registrazione) | Sì (cache) | Sì (prices map, calendar) | Dati meno "freschi" (cache), ma gratuito: ottimo come fonte prezzi per un price-watcher |
| **Kiwi.com (Tequila)** | API key gratuita | Sì | Sì | Richiede approvazione partner |
| RapidAPI (vari flight API) | Tier free con **poche** chiamate/mese | Variabile | Variabile | Utile per test, limiti stretti |
| Aviationstack | Free 100 req/mese | **No (solo stato voli)** | No | Escluso: non dà prezzi |

### Raccomandazione per il tuo caso

- **In sviluppo**: **Amadeus in ambiente test** — gratuito, nessun costo mentre costruisci e provi le 3 modalità.
- **In produzione (gratis)**: due strade valide —
  1. **Amadeus produzione** sfruttando la quota mensile gratuita (sufficiente con pochi utenti e cadenze non troppo fitte);
  2. **Travelpayouts/Aviasales**, gratuito e senza quota a consumo — la scelta più "a costo zero" per un progetto con utenti limitati.

> Il `FlightClient` è già isolato dietro un'interfaccia (§4): si può partire con Amadeus e aggiungere/commutare Travelpayouts **senza toccare l'Alert Engine**.

### Il "budget" di chiamate — la matematica

La variabile che determina tutto è **quante chiamate API si generano al mese**:

```
chiamate/mese per alert ≈ (24h / intervallo_ore) × 30
   intervallo 2h  → 12 run/giorno × 30 ≈ 360 chiamate/mese per alert
```

Quindi, senza ottimizzazioni:

| Alert attivi | Intervallo | Chiamate/mese |
|---|---|---|
| 5  | 2h | ~1.800 |
| 10 | 2h | ~3.600 |
| 10 | 6h | ~1.200 |

### Le leve per restare gratis

1. **Cadenza** — l'intervallo per-utente `users.poll_interval_hours` (default 6h). 2h è il minimo sensato per i prezzi voli (non cambiano al minuto); un default più alto (6–12h) riduce molto le chiamate. L'admin impone un **minimo** (`min_poll_interval_hours`, es. 2h) sotto cui l'utente non può scendere. **È la leva principale** (niente cache persistente che risparmi tra un ciclo e l'altro).
2. **Tetti di piano** — limiti applicativi: max **N utenti**, max **M alert per utente**, cadenza minima 2h. Sono proprio i "limiti" che citi, e vanno resi espliciti come regole di prodotto.
3. **Cache di esecuzione** — dentro un singolo run (o una singola ricerca web), chiamate identiche vengono fatte **una sola** volta: utile quando più alert/combinazioni toccano la stessa tratta/finestra, oppure per le espansioni offset/weekday. Non riduce le chiamate tra cicli diversi (lì i dati sono sempre freschi).

### Guardrail consigliati (MVP gratuito)

- Minimo consentito per l'intervallo utente: **2 ore** (default nuovi utenti: 6h).
- Max alert per utente: **es. 5**; max utenti in beta: **es. 50**.
- **Cache di esecuzione** attiva nel worker e nelle ricerche web: deduplica le chiamate identiche nello stesso run (nessuna persistenza tra cicli).
- Un **contatore mensile di chiamate** (tabella o log) con soglia d'allarme: quando ci si avvicina alla quota free, il worker allunga automaticamente le cadenze.
- Backoff su `429`/quota esaurita: si salta il giro e si riprova al run successivo, senza perdere alert.

Con questi paletti i numeri restano contenuti; la cache di esecuzione li riduce solo quando ci sono sovrapposizioni dentro lo stesso ciclo. Se un mese ci si avvicina al limite, il sistema **si auto-rallenta** (allunga le cadenze) invece di costare.

---

## 2quater. Scheda destinazione (guida alla meta)

Accanto a ogni volo, nei risultati, una **card-guida** della destinazione con: tipo di meta, itinerario ipotetico e cose da vedere, dintorni, eventi nelle date scelte, costo medio albergo, come muoversi (auto vs mezzi pubblici) e trasferimento aeroporto↔città (costo e tempo).

Questi dati **non** vengono da Amadeus-voli: servono più fonti, quasi tutte con tier gratuito.

| Campo della card | Fonte consigliata (free-first) |
|---|---|
| **Tipo meta** (mare / montagna / neve / città / lago…) | Classificazione da tabella `destinations` (curata) + stagione (la "neve" dipende dal meteo nelle date) |
| **Overview + itinerario ipotetico + cosa vedere** | POI: **OpenTripMap** (free) o Amadeus *Points of Interest* / *Tours & Activities*; testo narrativo generato da **LLM: Google Gemini** (free tier) ancorato ai POI |
| **Cosa vedere nei dintorni** | OpenTripMap "radius search" attorno alla città |
| **Eventi nelle date** | **Ticketmaster Discovery API** (free) filtrando città + intervallo date |
| **Costo medio albergo** | Amadeus *Hotel Search* (media delle offerte per quelle date) → consuma quota; in alternativa un indice statico |
| **Mare / montagna / neve nelle date** (clima) | **Open-Meteo** (free, no key): previsioni o medie climatiche |
| **Auto vs mezzi pubblici** | Campo curato in `destinations` + giudizio **Gemini** ancorato ai dati |
| **Trasferimento aeroporto↔città (costo + tempo)** | Amadeus *Transfer Search* (transfer privato: prezzo + durata) + campo curato per il trasporto pubblico (treno/bus: tempo e costo tipico) |

### Come si costruisce (architettura)

- **On-demand, non per ogni riga.** Nella lista dei risultati (soprattutto in "Ovunque", con decine di mete) si mostra al massimo un **badge leggero** (tipo meta) preso da `destinations`. La **card completa** si carica solo quando l'utente **apre/espande** un risultato, via endpoint `GET /guide` (§7). Così non si moltiplicano le chiamate a tante API per mete che l'utente non guarderà.
- **Caricamento asincrono**: la card arriva dopo i voli, senza rallentare la ricerca.
- **DestinationGuide service** (§4) aggrega le fonti, normalizza e compone il `DestinationGuide`.

### Memorizzazione (qui la cache ha senso)

> La regola **"no cache"** riguarda i **prezzi dei voli** (devono essere freschi). I dati della scheda destinazione sono **informazioni di riferimento** che cambiano lentamente, quindi vanno **memorizzati**, altrimenti ogni apertura brucerebbe le quote di più API:
> - **Dati stabili** (tipo meta, POI, trasferimento, auto/mezzi, overview/itinerario): tabella `destinations` + guida con **TTL lungo** (giorni/settimane).
> - **Dati legati alle date** (eventi, costo albergo, meteo): **TTL breve** (es. 24h), chiave = destinazione + intervallo date.
>
> È una deroga **esplicita** e circoscritta alla guida; i prezzi dei voli restano senza cache. *(Da confermare.)*

### Nota sui contenuti LLM (Google Gemini)

Itinerario e giudizi ("conviene l'auto") sono generati con **Google Gemini** *ancorato ai fatti* (POI, eventi, meteo, transfer realmente recuperati) per evitare invenzioni; l'output è memorizzato con la guida (niente chiamate LLM ripetute per la stessa meta/date). Senza LLM, si ripiega su testo curato nella tabella `destinations`.

- **Chiave**: si ottiene gratis da **Google AI Studio** (`aistudio.google.com` → *Get API key*); va nel `.env`:
  ```ini
  GEMINI_API_KEY=la_tua_chiave
  ```
- **Free tier**: Gemini offre un piano gratuito con limiti di richieste/minuto e /giorno — ampiamente sufficiente visto che la generazione è **on-demand e memorizzata**.
- **Grounding**: nel prompt si passano solo i dati raccolti dalle API; si chiede a Gemini di **non inventare** e di segnalare quando un'informazione manca.

### Costi/quota

Ogni card tocca più API: per restare nel free è decisivo **costruirla solo on-demand**, **memorizzarla** e preferire fonti gratuite (OpenTripMap, Ticketmaster, Open-Meteo) riservando gli endpoint Amadeus a pagamento-a-quota (Hotel, Transfer) ai casi in cui servono davvero.

---

## 2cinque. Scovare le vere offerte (copertura + deal detection)

Mostrare un prezzo è facile; capire che è **davvero un affare** e, prima ancora, **vederlo** è il cuore del prodotto. Ecco cosa serve davvero.

### 1. Copertura: il vero collo di bottiglia
- **Amadeus è un GDS**: copre bene le compagnie tradizionali, ma **sotto-rappresenta le low-cost** (Ryanair, Wizz, easyJet), dove in Europa stanno moltissime offerte reali. Con il solo Amadeus molte "vere offerte" **non compaiono proprio**.
- **Serve almeno una fonte low-cost/aggregata**: **Travelpayouts/Aviasales** (include le low-cost) o **Kiwi.com** (che fa anche **self-transfer / split ticket**). Strategia: **multi-provider**, risultati **uniti e deduplicati** per tratta/data tenendo il prezzo minore.
- Senza questo passo, il resto conta poco: è la singola leva con più impatto sulle offerte trovate.

### 2. Baseline: senza riferimento non esiste "affare"
Un prezzo è un'offerta solo rispetto a **quanto è normale** per quella tratta/periodo. Servono:
- **Amadeus Flight Price Analysis** (quartili min/mediana/max): giudizio oggettivo "è basso?" senza aspettare mesi di storico.
- **Storico proprio** (`price_history`) che matura nel tempo per i confronti "−X% vs media".
- **Stagionalità** (mese/giorno della settimana): un prezzo "basso" a Ferragosto non è lo stesso a novembre.
→ In card ed email si mostra **il perché** ("−32% rispetto alla mediana della rotta"): è ciò che rende l'avviso credibile.

### 3. Prezzo totale, non tariffa base
Le low-cost mostrano basi bassissime poi aggiungono bagaglio/posto. Per confrontare offerte **vere** serve ragionare sul **prezzo totale realistico** (con bagaglio dove disponibile), non sulla sola base fare.

### 4. Combinazioni "furbe" che fanno emergere gli affari
- **Aeroporti vicini** (già previsto: city code + scali extra).
- **Date flessibili / offset ±X** e **"mese più economico"** (già previsti).
- **Open-jaw** (parti da A, torni su B) e **split ticket / self-transfer** (tipico di Kiwi): spesso battono il biglietto unico.

### 5. Latenza e frequenza (le offerte spariscono)
Le vere occasioni durano poco. Il compromesso con "no cache + ogni 2h + quota free" è reale:
- cadenza più fitta = più offerte prese ma più chiamate;
- possibile compromesso: cadenza più alta solo su **poche rotte "calde"** scelte dall'utente.
- Per gli avvisi, **notifica rapida** batte il digest ritardato (oggi: digest alla cadenza dell'utente; in futuro push/Telegram per i cali forti).

### 6. Error fare / mistake fare: gioco diverso
Le tariffe-errore leggendarie le scovano servizi specializzati che **monitorano molte fonti in tempo reale** (es. Secret Flying, Jack's Flight Club). Con un solo provider ogni 2h se ne catturano poche: realistico puntare a **buone offerte oggettive** (baseline), non alla caccia all'errore.

### In sintesi — cosa manca davvero
1. **Fonte con copertura low-cost** (Travelpayouts/Kiwi) in multi-provider → *l'intervento a maggior impatto*.
2. **Baseline** (Price Analysis + storico + stagionalità) per distinguere prezzo da affare.
3. **Prezzo totale** (ancillari) per confronti onesti.
4. **Combinazioni** (open-jaw, split ticket) e **flessibilità** già previste: da sfruttare a fondo.
5. **Latenza/frequenza** tarate, con notifica rapida sui cali forti.

### Integrazione Travelpayouts (Aviasales Data API)

Provider **gratuito** con copertura low-cost, usato in multi-provider accanto ad Amadeus.

- **Account e credenziali**: registrazione su `travelpayouts.com` → si ottengono un **token** API e un **marker** (id affiliato). Vanno nel `.env` (`TRAVELPAYOUTS_TOKEN`, `TRAVELPAYOUTS_MARKER`). Base host: `https://api.travelpayouts.com`.
- **Natura dei dati**: prezzi da **catalogo/cache** lato Travelpayouts (indicativi), non in tempo reale → ottimi per la **scoperta**, da confermare con Amadeus dove serve il dettaglio.

Mapping sulle tre modalità (§2bis):

| Modalità flynotify | Endpoint Travelpayouts |
|---|---|
| **Classica** (tratta+date) | `aviasales/v3/prices_for_dates` (origin, destination, departure/return) |
| **Ovunque** (solo origine) | `v2/prices/latest` o `aviasales/v3/get_latest_prices` con sola origine → mete per prezzo |
| **Mese più economico** | `v1/prices/calendar` (calendario dei prezzi minimi per data) |

Esempio (classica):

```
GET https://api.travelpayouts.com/aviasales/v3/prices_for_dates
    ?origin=MIL&destination=LON&departure_at=2026-11&return_at=2026-11
    &sorting=price&currency=eur&token=$TRAVELPAYOUTS_TOKEN&marker=$TRAVELPAYOUTS_MARKER
```

- **Normalizzazione**: la risposta viene mappata su `FlightOffer`/`DestinationDeal`/`DateDeal` con `source.provider = "travelpayouts"`, così il merge con Amadeus è trasparente.
- **Merge & dedup** (Search Service): stesse tratta/date da provider diversi → si tiene il **prezzo minimo** e si indica la fonte nella card.

> **Nota ToS/affiliazione:** Travelpayouts è pensato per partner affiliati (il `marker` serve a quello). flynotify **non mostra link di prenotazione** (mostra solo la fonte del prezzo): va verificato che l'uso come **sola fonte dati** rispetti i loro termini. Se richiesto, si può reintrodurre un link affiliato opzionale senza stravolgere il resto. *(Da verificare.)*

---

## 3. Stack tecnologico

| Livello | Tecnologia | Motivazione |
|---|---|---|
| Backend API | **Python + FastAPI** | Async nativo (ideale per chiamate HTTP esterne), tipizzazione con Pydantic, OpenAPI automatico |
| Scheduler / worker | **Windows Task Scheduler** che lancia uno script Python "one-shot" | Polling periodico degli alert senza processo sempre attivo né broker; nativo nell'ambiente Windows |
| Database | **MySQL 8** | Relazionale, affidabile per utenti/alert/storico prezzi; già disponibile nell'ambiente Apache |
| Cache | **Solo di esecuzione (in-memory, per run/richiesta)** | Deduplica le chiamate identiche nello stesso ciclo; **nessuna cache persistente** |
| Email | **Gmail** (account Google) via SMTP con **App Password** | Zero costi e setup rapido; deliverability gestita da Google. Limite ~500 invii/giorno (Gmail free) |
| Frontend | **React + Vite** (o Next.js) | SPA per ricerca e gestione alert |
| Deploy | Docker + (Fly.io / Render / AWS) | Container riproducibili |

> **Nota sulla scelta MySQL (senza Redis):** Redis svolgeva due ruoli — cache e broker per Celery. Rimuovendolo:
> - **Cache** → non serve alcuna cache persistente: le chiamate sono sempre live. La sola deduplica è **in memoria per la durata del run/richiesta** (un dizionario scartato alla fine), quindi non richiede né Redis né tabelle.
> - **Scheduler** → **Windows Task Scheduler** (vedi §6bis): nessun processo worker sempre attivo, nessun broker.
>
> Alternativa "tutto JS": Node + NestJS, sempre su MySQL, con il worker lanciato comunque da Task Scheduler.

---

## 4. Architettura dei componenti

```
                    ┌─────────────┐
                    │  Frontend   │  ricerca voli, gestione alert
                    │ (React SPA) │
                    └──────┬──────┘
                           │ REST / JSON
                    ┌──────▼──────────┐
                    │   API Backend   │  FastAPI
                    │                 │
          ┌─────────┤ • /search       │
          │         │ • /alerts CRUD  │
          │         │ • /auth         │
          │         └───┬────────┬────┘
          │             │        │
   ┌──────▼──────┐  ┌───▼─────────────────┐
   │ FlightClient│  │     MySQL 8         │
   │ (Amadeus)   │  │ users / alerts /    │
   │ + cache     │  │ price_history /     │
   │ di run      │  │ notifications /     │
   └──────┬──────┘  │ app_settings        │
   ┌──────▼──────┐  └───▲─────────────────┘
   │  API (ext)  │      │
   └─────────────┘      │
                        │
   ┌────────────────────┴───────────┐
   │  Alert Worker (script one-shot) │  lanciato da Windows Task Scheduler ogni N min
   │  1. legge alert attivi          │
   │  2. interroga FlightClient      │
   │  3. valuta Alert Engine         │
   │  4. accoda email se necessario  │
   └────────────────┬────────────────┘
                    │
             ┌──────▼───────┐
             │ Email Service│  Gmail SMTP → utente
             └──────────────┘
```

### Moduli

- **FlightProvider (interfaccia)** — contratto comune per i provider di prezzi, con metodi `search_offers`, `inspiration_search`, `cheapest_dates` che restituiscono i modelli interni normalizzati (`FlightOffer`, `DestinationDeal`, `DateDeal`, con `source.provider`). Due implementazioni:
  - **AmadeusClient** — GDS: OAuth, retry/backoff, dati **live** e dettagliati (orari, scali); copre bene le compagnie tradizionali. Usato anche per la ri-validazione e per `price_history`.
  - **TravelpayoutsClient** — Aviasales Data API: **gratuito** e con **copertura low-cost** (Ryanair/Wizz/easyJet); dati da catalogo (indicativi). Ideale per la scoperta ampia (§2cinque).
- **Search Service** — orchestratore multi-provider: interroga i provider pertinenti alla modalità, **normalizza, unisce e deduplica** per tratta/data tenendo il **prezzo minimo**, e ordina per prezzo. Chiama i provider **in tempo reale** (nessuna cache persistente); una **cache di esecuzione** (dizionario in memoria del run/richiesta) evita doppioni dentro la stessa richiesta (es. espansioni offset/weekday). Default consigliato: **Travelpayouts** (free) per la scoperta ampia, **Amadeus** per il dettaglio live sulle opzioni scelte — così si risparmia la quota Amadeus.
- **Alert Service** — CRUD degli alert (creazione, pausa, cancellazione). Alla **creazione** esegue un **primo check immediato** (una ricerca subito), così l'utente vede subito il prezzo attuale senza attendere il primo ciclo.
- **Alert Worker** — script "one-shot" (`python -m flynotify.worker`): all'avvio legge gli utenti/alert scaduti, interroga il FlightClient, invoca l'Alert Engine, invia i digest e termina. Scrive una riga in `run_log` (heartbeat + esito) e aggiorna il contatore chiamate mensile. Lo avvia **Windows Task Scheduler** a intervalli regolari (vedi §6bis).
- **Alert Engine** — la logica "intelligente" (vedi §6).
- **Email Service** — `send_digest(user_id, items)`: compone **un'unica email riepilogativa** con tutti gli avvisi dell'utente, la invia via **Gmail SMTP** (§8bis) e registra l'esito in `email_log`.
- **Settings** — legge/scrive le preferenze: l'intervallo del singolo utente (`users.poll_interval_hours`) e i vincoli globali in `app_settings` (`min_poll_interval_hours`), usati da worker ed endpoint.
- **DestinationGuide** — compone la scheda-guida della meta (§2quater): legge i dati stabili da `destinations`, recupera on-demand eventi/hotel/meteo (con `guide_cache`), eventualmente genera overview/itinerario con **Gemini** ancorato ai POI, e restituisce un `DestinationGuide`. Isolato dietro interfaccia come il FlightClient, così le fonti (e l'LLM) sono sostituibili.

---

## 5. Modello dati

```sql
-- Utenti
CREATE TABLE users (
    id            CHAR(36) PRIMARY KEY DEFAULT (UUID()),
    email         VARCHAR(255) NOT NULL,            -- collation _ci = confronto case-insensitive
    full_name     VARCHAR(120),
    password_hash VARCHAR(255),                     -- se auth con password; altrimenti magic-link
    role          VARCHAR(20) NOT NULL DEFAULT 'user',   -- 'user' | 'admin' | 'superadmin'
    status        VARCHAR(20) NOT NULL DEFAULT 'active', -- 'active' | 'suspended'
    poll_interval_hours INT NOT NULL DEFAULT 6,     -- intervallo SCELTO DAL SINGOLO UTENTE (min imposto dall'admin)
    last_run_at   TIMESTAMP NULL,                   -- ultimo ciclo completato per questo utente
    timezone      VARCHAR(40) NOT NULL DEFAULT 'Europe/Rome',  -- per interpretare date/orari e fasce orarie
    currency      CHAR(3) NOT NULL DEFAULT 'EUR',    -- valuta preferita per prezzi ed email
    verified      BOOLEAN NOT NULL DEFAULT FALSE,
    created_by    CHAR(36) NULL,                    -- chi ha creato l'account (per utenti creati da admin)
    created_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_users_email (email),
    KEY idx_users_role (role)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Alert configurati dall'utente
CREATE TABLE alerts (
    id               CHAR(36) PRIMARY KEY DEFAULT (UUID()),
    user_id          CHAR(36) NOT NULL,
    origin           CHAR(3) NOT NULL,              -- IATA, es. 'FCO'
    destination      CHAR(3) NOT NULL,              -- IATA (es. 'JFK') oppure 'ANY' = alert "Ovunque"
    depart_from      DATE NOT NULL,                 -- inizio finestra andata
    depart_to        DATE NOT NULL,                 -- fine finestra andata
    return_from      DATE NULL,                     -- NULL = solo andata
    return_to        DATE NULL,
    adults           TINYINT NOT NULL DEFAULT 1,
    cabin            VARCHAR(20) NOT NULL DEFAULT 'ECONOMY',
    max_stops        TINYINT NULL,                  -- NULL = qualsiasi
    depart_dow       TINYINT NULL,                  -- giorno settimana andata (1=Lun..7=Dom, ISO); NULL = qualsiasi
    return_dow       TINYINT NULL,                  -- giorno settimana ritorno; es. VEN=5, DOM=7
    depart_time_from TIME NULL,                     -- fascia oraria partenza (da), es. '18:00'
    depart_time_to   TIME NULL,                     -- fascia oraria partenza (a),  es. '22:00'
    target_price     DECIMAL(10,2) NULL,            -- soglia "avvisami sotto X"
    currency         CHAR(3) NOT NULL DEFAULT 'EUR',
    strategy         VARCHAR(20) NOT NULL DEFAULT 'threshold', -- 'threshold' | 'drop' | 'deal'
    status           VARCHAR(20) NOT NULL DEFAULT 'active',    -- 'active' | 'paused'
    last_checked     TIMESTAMP NULL,                 -- solo informativo: la cadenza è per-utente (users.poll_interval_hours)
    created_at       TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_alerts_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    KEY idx_alerts_due (status, last_checked)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Storico prezzi osservati (per decidere i "drop" e i "deal")
CREATE TABLE price_history (
    id          BIGINT PRIMARY KEY AUTO_INCREMENT,
    alert_id    CHAR(36) NOT NULL,
    price       DECIMAL(10,2) NOT NULL,
    currency    CHAR(3) NOT NULL,
    offer_json  JSON NOT NULL,                      -- offerta normalizzata completa
    observed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_ph_alert FOREIGN KEY (alert_id) REFERENCES alerts(id) ON DELETE CASCADE,
    KEY idx_price_history_alert_time (alert_id, observed_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Notifiche inviate (idempotenza + audit)
CREATE TABLE notifications (
    id          CHAR(36) PRIMARY KEY DEFAULT (UUID()),
    alert_id    CHAR(36) NOT NULL,
    price       DECIMAL(10,2) NOT NULL,
    reason      VARCHAR(20) NOT NULL,               -- 'below_target' | 'price_drop' | 'good_deal'
    dedupe_key  VARCHAR(255) NOT NULL,              -- hash(alert_id + prezzo + giorno)
    sent_at     TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_notif_alert FOREIGN KEY (alert_id) REFERENCES alerts(id) ON DELETE CASCADE,
    UNIQUE KEY uq_notif_dedupe (dedupe_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Nessuna tabella di cache: le risposte API non sono persistite.
-- La deduplica avviene solo in memoria per la durata del run/richiesta (vedi §4, cache di esecuzione).

-- Impostazioni globali dell'app (chiave/valore)
CREATE TABLE app_settings (
    setting_key   VARCHAR(64) PRIMARY KEY,
    setting_value VARCHAR(255) NOT NULL,
    updated_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- L'intervallo è PER-UTENTE (colonna users.poll_interval_hours); qui solo i vincoli globali
INSERT INTO app_settings (setting_key, setting_value) VALUES
    ('min_poll_interval_hours',     '2'),   -- minimo consentito all'utente (protezione quota API, impostato dall'admin)
    ('default_poll_interval_hours', '6'),   -- valore iniziale per i nuovi utenti
    ('monthly_call_count',          '0'),   -- contatore chiamate API del mese corrente
    ('monthly_call_period',         ''),    -- 'YYYY-MM' del contatore (reset a inizio mese)
    ('call_budget_soft_limit',      '2000');-- soglia oltre cui il worker auto-rallenta le cadenze

-- Osservabilità: log di ogni esecuzione del worker (heartbeat + esito)
CREATE TABLE run_log (
    id            BIGINT PRIMARY KEY AUTO_INCREMENT,
    started_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finished_at   TIMESTAMP NULL,
    users_checked INT NOT NULL DEFAULT 0,
    alerts_checked INT NOT NULL DEFAULT 0,
    emails_sent   INT NOT NULL DEFAULT 0,
    api_calls     INT NOT NULL DEFAULT 0,
    status        VARCHAR(20) NOT NULL DEFAULT 'ok',   -- 'ok' | 'error' | 'skipped'
    error_text    TEXT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Log degli invii email (audit + diagnosi deliverability)
CREATE TABLE email_log (
    id          BIGINT PRIMARY KEY AUTO_INCREMENT,
    user_id     CHAR(36) NULL,
    to_email    VARCHAR(255) NOT NULL,
    subject     VARCHAR(255) NOT NULL,
    status      VARCHAR(20) NOT NULL,                  -- 'sent' | 'error'
    error_text  TEXT NULL,
    sent_at     TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Dati di riferimento della destinazione (stabili): base della scheda-guida (§2quater)
CREATE TABLE destinations (
    iata          CHAR(3) PRIMARY KEY,                 -- città/aeroporto (es. 'BCN')
    city_name     VARCHAR(120) NOT NULL,
    country       VARCHAR(80),
    lat           DECIMAL(9,6),
    lon           DECIMAL(9,6),
    kind          VARCHAR(30),                         -- 'mare' | 'montagna' | 'neve' | 'città' | 'lago' | ...
    transit_hint  VARCHAR(255),                        -- es. 'treno dall'aeroporto 35 min, ~5€; auto non necessaria'
    needs_car     BOOLEAN NULL,                        -- true/false/NULL = non noto
    overview      TEXT,                                -- descrizione/itinerario curato o LLM (ancorato)
    pois_json     JSON,                                -- POI principali + dintorni (normalizzati)
    updated_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Cache della guida legata alle DATE (eventi/hotel/meteo): TTL breve
CREATE TABLE guide_cache (
    cache_key   VARCHAR(255) PRIMARY KEY,              -- hash(destinazione + intervallo date)
    payload     JSON NOT NULL,                         -- eventi + costo medio albergo + meteo
    created_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at  TIMESTAMP NOT NULL,                    -- es. +24h
    KEY idx_guide_cache_expiry (expires_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
```

> Nota: `guide_cache` **non** contraddice la regola "no cache": riguarda informazioni di destinazione (eventi/hotel/meteo), non i prezzi dei voli, che restano sempre live.

Note sulla sintassi MySQL 8:

- **ID**: `CHAR(36)` con `DEFAULT (UUID())` (MySQL 8.0.13+). In alternativa, per performance, `BINARY(16)` con `UUID_TO_BIN()`; oppure `BIGINT AUTO_INCREMENT` se non servono ID opachi.
- **Email case-insensitive**: nessun tipo `CITEXT`; si usa la collation di default `utf8mb4_0900_ai_ci`, che confronta già senza distinzione di maiuscole.
- **Intervallo per-utente**: ogni utente sceglie il **proprio** intervallo (`users.poll_interval_hours`), non inferiore al minimo globale `app_settings.min_poll_interval_hours` (default 2h, fissato dall'admin). Il worker confronta `users.last_run_at` con l'intervallo del singolo utente per decidere se processarlo in questo giro. `alerts.last_checked` resta solo informativo.
- **`offer_json` / `payload`**: tipo nativo `JSON` di MySQL (interrogabile con `->>`, `JSON_EXTRACT`).
- **`observed_at` DESC nell'indice**: l'ordinamento DESC negli indici è supportato da MySQL 8; qui l'indice ascendente è sufficiente perché il DB può scorrerlo al contrario.

Il campo `offer_json` conserva l'offerta normalizzata (orari, scali, compagnia, **fonte del prezzo**) così l'email può mostrare i dettagli senza una nuova chiamata API.

---

## 5bis. Utenti, ruoli e permessi

Tre ruoli, memorizzati in `users.role`:

| Ruolo | Chi è | Cosa può fare |
|---|---|---|
| **user** | utente finale | Gestisce **solo i propri** alert; riceve l'email riepilogativa; modifica le proprie preferenze e il proprio account |
| **admin** | gestore del servizio | Tutto ciò che fa `user`, **più**: gestione utenti (crea, sospende, riattiva, elimina utenti `user`), vista su tutti gli alert, **imposta il minimo consentito** per l'intervallo (`min_poll_interval_hours`), vede metriche/consumo quota |
| **superadmin** | proprietario del sistema | Tutto ciò che fa `admin`, **più**: gestione degli **admin** (promuove/retrocede ruoli), configurazione di sistema (chiavi API, provider email). Tipicamente **uno solo**, creato al primo avvio (seed) |

### Matrice dei permessi (sintesi)

| Azione | user | admin | superadmin |
|---|:--:|:--:|:--:|
| CRUD sui **propri** alert | ✅ | ✅ | ✅ |
| Vedere/gestire gli alert di **tutti** | ❌ | ✅ | ✅ |
| Creare/sospendere/eliminare utenti `user` | ❌ | ✅ | ✅ |
| Scegliere il **proprio** intervallo (≥ minimo) | ✅ | ✅ | ✅ |
| Fissare il **minimo** consentito per l'intervallo | ❌ | ✅ | ✅ |
| Vedere metriche e consumo quota API | ❌ | ✅ | ✅ |
| Promuovere/retrocedere **admin**, cambiare ruoli | ❌ | ❌ | ✅ |
| Configurazione di sistema (chiavi API, email) | ❌ | ❌ | ✅ |

### Regole di sicurezza sui ruoli

- Un `admin` **non** può modificare o eliminare un altro `admin`/`superadmin`, né assegnare ruoli: solo il `superadmin` tocca i ruoli.
- Deve esistere **sempre almeno un `superadmin`**: il sistema impedisce di retrocedere/eliminare l'ultimo.
- Il primo `superadmin` è creato da un **comando di seed** (non da un endpoint pubblico), con password da cambiare al primo accesso.
- Un utente `suspended` non può autenticarsi né ricevere email; i suoi alert restano ma non vengono valutati.

### Come si applica (autorizzazione)

Il JWT emesso al login include `sub` (id utente) e `role`. Nel backend una dependency FastAPI applica il controllo:

```python
def require_role(*roles):
    def dep(user = Depends(current_user)):
        if user.role not in roles:
            raise HTTPException(403, "Permesso negato")
        return user
    return dep

# esempi d'uso
@app.get("/admin/users",     dependencies=[Depends(require_role("admin", "superadmin"))])
@app.patch("/admin/users/{id}/role", dependencies=[Depends(require_role("superadmin"))])
```

Le risorse "proprie" (es. `/alerts`) filtrano sempre per `user_id` del token; un `user` non può leggere gli alert altrui nemmeno indovinando l'id.

---

## 6. Alert Engine — la parte "intelligente"

L'obiettivo è **avvisare solo quando serve davvero**. Tre strategie, selezionabili per alert:

### `threshold` — soglia fissa
Avvisa se `prezzo_corrente <= target_price`. Semplice e prevedibile.

### `drop` — calo significativo
Avvisa se il prezzo scende di una percentuale rilevante rispetto alla media recente:

```
media_7gg = AVG(price) su price_history negli ultimi 7 giorni
avvisa SE prezzo_corrente <= media_7gg * (1 - soglia_calo)   # es. soglia_calo = 0.15 → -15%
```

### `deal` — buon affare oggettivo
Usa il *Flight Price Analysis* di Amadeus (quartili di prezzo storici per quella tratta):
avvisa se il prezzo corrente cade nel quartile più basso ("MINIMUM"/"FIRST").

### Regole anti-spam (valgono per tutte le strategie)

1. **Deduplica**: `dedupe_key = hash(alert_id + prezzo_arrotondato + data)`. Se esiste già in `notifications`, non si invia.
2. **Cooldown**: nessuna seconda email per lo stesso alert entro N ore (es. 24h), salvo un ulteriore calo ≥ X%.
3. **Solo miglioramenti**: non si avvisa se il nuovo prezzo è ≥ dell'ultimo già notificato.

Pseudocodice del worker:

```python
# Ogni utente ha il PROPRIO intervallo: si processa solo chi è "scaduto"
for user in active_users():                               # status = 'active'
    if user.last_run_at and now() - user.last_run_at < hours(user.poll_interval_hours):
        continue                                          # non ancora ora per questo utente

    triggered = []                                        # avvisi di QUESTO utente
    for alert in active_alerts_of(user):
        best = find_best_offer(alert)                     # ramo tratta singola / 'ANY' (vedi sotto)
        if best and alert_engine.should_notify(alert, best):  # strategia + anti-spam (dedupe)
            triggered.append((alert, best))
            record_notification(alert, best)
        alert.last_checked = now()

    if triggered:                                         # una sola email riepilogativa per utente
        email_service.send_digest(user.id, triggered)
    user.last_run_at = now()                              # cadenza propria dell'utente
```

`find_best_offer(alert)` incapsula i due rami visti prima: se `alert.destination == 'ANY'` usa *Flight Inspiration Search* + ri-validazione, altrimenti *Flight Offers Search* sulla tratta. Gli utenti senza alcun avviso in questo ciclo **non ricevono email**.

---

## 6bis. Scheduling con Windows Task Scheduler

Il worker **non è un processo residente**: è uno script che parte, lavora e termina. Windows Task Scheduler lo richiama a un **tick base** frequente (es. ogni 30 minuti); a ogni tick il worker scorre gli utenti e processa **solo quelli il cui intervallo personale è scaduto** (`now - users.last_run_at ≥ users.poll_interval_hours`).

Questo è il punto chiave: ogni utente sceglie il **proprio** intervallo da un menu a tendina nel sito (es. 2h, 6h, 12h), salvato in `users.poll_interval_hours`; il worker lo rispetta per ciascuno **senza riconfigurare Task Scheduler**. Il tick base deve solo essere ≤ del minimo consentito (es. 30 min con minimo 2h).

```
Task Scheduler (tick ogni 30 min) ──► worker parte
                                        │
                                        └─ per ogni utente attivo:
                                             now - user.last_run_at < user.poll_interval_hours ?  → salta
                                             altrimenti → valuta i suoi alert, invia il digest, aggiorna last_run_at
```

> L'admin non fissa l'intervallo di nessuno: imposta solo il **minimo consentito** (`min_poll_interval_hours`), così nessun utente può scendere sotto una soglia che brucerebbe la quota API.

### Come si avvia

1. Uno script wrapper `run_worker.bat` nella cartella del progetto:

```bat
@echo off
cd /d D:\webserver\apache24\flynotify
call .venv\Scripts\activate.bat
python -m flynotify.worker >> logs\worker.log 2>&1
```

2. Registrazione dell'attività (da PowerShell come amministratore), tick base ogni 30 minuti:

```bat
schtasks /Create /TN "flynotify-worker" ^
  /TR "D:\webserver\apache24\flynotify\run_worker.bat" ^
  /SC MINUTE /MO 30 ^
  /RU "SYSTEM" /RL LIMITED /F
```

> Il tick è solo il "battito": la cadenza reale di ogni utente è la sua `users.poll_interval_hours`, applicata dal worker. In alternativa si può creare l'attività dall'interfaccia "Utilità di pianificazione" con un trigger "Ripeti ogni 30 minuti per una durata indefinita".

### Protezione dalle sovrapposizioni

Se un'esecuzione dura più dell'intervallo, due worker potrebbero girare insieme. Due difese, cumulabili:

- **Lato Task Scheduler**: impostare *"Non avviare una nuova istanza"* se l'attività è già in esecuzione (opzione nativa).
- **Lato applicazione**: un lock su MySQL all'inizio del run —

```sql
SELECT GET_LOCK('flynotify_worker', 0);   -- restituisce 0 se già preso: il worker esce subito
-- ... elaborazione ...
SELECT RELEASE_LOCK('flynotify_worker');
```

### Cache di esecuzione

Nessuna pulizia da pianificare: non c'è cache persistente. La cache di esecuzione è un semplice dizionario in memoria, creato all'inizio del run e **scartato automaticamente** quando il worker termina. Serve solo a non ripetere, nello stesso ciclo, una chiamata identica (stessa tratta/finestra) richiesta da più alert o da espansioni offset/weekday.

### Affidabilità (la macchina deve essere accesa)

Task Scheduler non può lanciare il worker se il PC/server è **spento o in sospensione**. Dato che l'ambiente è un server Apache su Windows, in genere è sempre acceso; comunque: disattivare la sospensione automatica, e nell'attività spuntare *"Riattiva il computer per eseguire"* e *"Esegui l'attività il prima possibile dopo un avvio pianificato non riuscito"*. Il `run_log` permette di accorgersi se un ciclo è saltato.

### Scalabilità

Il modello "un run alla volta" copre ampiamente l'MVP e oltre. Se un giorno servisse maggiore frequenza o parallelismo, le strade sono: ridurre l'intervallo del Task Scheduler, far processare al worker gli alert in batch concorrenti (async), oppure passare a un worker residente con broker — **senza toccare l'Alert Engine**, che resta indipendente da come viene invocato.

---

## 7. API Backend (bozza endpoint)

| Metodo | Endpoint | Descrizione |
|---|---|---|
| `POST` | `/auth/signup` | Registrazione (email + verifica) |
| `POST` | `/auth/login` | Login → JWT |
| `GET`  | `/search` | Tratta singola: `origin`, `destination`, `departDate`/`returnDate`, `offset` (±X giorni), `dow` (giorni sett.), `timeFrom`/`timeTo` (fascia oraria) → offerte reali |
| `GET`  | `/explore` | Modalità "Ovunque": `origin` (+ `maxPrice`, `month`, `nonStop`) → mete ordinate per prezzo |
| `GET`  | `/cheapest-dates` | Modalità "Mese più economico": `origin`, `destination` (+ `oneWay`, `viewBy`) → date ordinate per prezzo |
| `GET`  | `/guide` | Scheda destinazione (§2quater): `destination`, `from`/`to` → tipo meta, itinerario, dintorni, eventi, hotel medio, meteo, trasferimento. On-demand, memorizzata |
| `POST` | `/alerts` | Crea alert |
| `GET`  | `/alerts` | Lista alert dell'utente |
| `GET`  | `/alerts/{id}` | Dettaglio + storico prezzi |
| `PATCH`| `/alerts/{id}` | Modifica / pausa / riattiva |
| `DELETE`| `/alerts/{id}` | Elimina alert |
| `GET`  | `/alerts/{id}/history` | Serie storica prezzi (per grafico) |
| `GET`  | `/me/preferences` | Legge le preferenze dell'utente (incl. il proprio `poll_interval_hours`) |
| `PUT`  | `/me/preferences` | L'utente imposta il **proprio** intervallo (≥ `min_poll_interval_hours`) |
| `GET`  | `/settings` | Legge i vincoli globali (incl. `min_poll_interval_hours`) — **admin+** |
| `PUT`  | `/settings` | Fissa il **minimo** consentito per l'intervallo — **admin+** |
| `GET`  | `/admin/users` | Lista utenti — **admin+** |
| `POST` | `/admin/users` | Crea utente — **admin+** |
| `PATCH`| `/admin/users/{id}` | Sospendi/riattiva/modifica utente — **admin+** (non altri admin) |
| `DELETE`| `/admin/users/{id}` | Elimina utente `user` — **admin+** (non altri admin) |
| `PATCH`| `/admin/users/{id}/role` | Cambia ruolo (promuovi/retrocedi) — **superadmin** |
| `GET`  | `/admin/alerts` | Tutti gli alert del sistema — **admin+** |
| `GET`  | `/admin/stats` | Metriche e consumo quota API — **admin+** |

Esempio risposta `/search` (modello normalizzato, provider-agnostico):

```json
{
  "query": { "origin": "FCO", "destination": "JFK", "date": "2026-12-15" },
  "offers": [
    {
      "price": 412.30, "currency": "EUR",
      "stops": 1, "duration": "PT10H25M",
      "carriers": ["LH"],
      "segments": [ { "from": "FCO", "to": "FRA", "dep": "2026-12-15T09:10", "arr": "..." } ],
      "source": { "provider": "amadeus", "carrier": "LH" }
    }
  ],
  "fresh": true
}
```

---

Esempio risposta `/explore` (modalità "Ovunque", prezzi indicativi):

```json
{
  "query": { "origin": "FCO", "maxPrice": 80, "month": "2026-12" },
  "destinations": [
    { "destination": "BCN", "departDate": "2026-12-05", "returnDate": "2026-12-09", "price": 48.00, "currency": "EUR", "indicative": true },
    { "destination": "ATH", "departDate": "2026-12-11", "returnDate": "2026-12-15", "price": 61.00, "currency": "EUR", "indicative": true }
  ],
  "fresh": true
}
```

> Ogni voce porta `indicative: true`: il prezzo reale si ottiene aprendo la meta (`/search` su quella destinazione).

## 8. Email di notifica

- **Invio tramite Gmail (account Google).** Si usa SMTP autenticato con una **App Password** (vedi §8bis), via `smtplib`/`aiosmtplib`. SPF/DKIM sono già gestiti da Google, quindi buona deliverability senza configurare un dominio. Limite pratico: **~500 destinatari/giorno** su Gmail gratuito (~2.000 con Google Workspace) — ampiamente sufficiente con pochi utenti e un digest per ciclo.
- Mittente = l'indirizzo dell'account Google; è consigliabile un **account dedicato** (es. `flynotify.alerts@gmail.com`), non la casella personale.
- **Email riepilogativa (digest), una per utente per ciclo.** Alla fine di ogni ciclo del worker, tutti gli avvisi scattati per uno stesso utente vengono raccolti e inviati in **un'unica email**, non una per alert. Chi non ha avvisi in quel ciclo non riceve nulla.
- **Template HTML** del digest:
  - intestazione "Hai N nuovi avvisi di prezzo";
  - **una riga/card per avviso**: tratta (o meta, per gli alert "Ovunque"), prezzo trovato, confronto con la soglia/prezzo precedente, date e orari, ed **etichetta "Fonte: provider · compagnia"** (nessun link di prenotazione);
  - piè di pagina con link **"Gestisci i tuoi alert"** e **disiscrizione** (obbligatorio).
- Ogni avviso incluso resta registrato in `notifications` con il suo motivo (la dedupe è per-alert, così lo stesso avviso non ricompare nel digest successivo).
- Rispetto GDPR: conferma email alla registrazione, disiscrizione a un click, cancellazione account → `ON DELETE CASCADE`.

---

## 8bis. Invio email con Gmail (App Password)

Per usare un account Google come mittente senza OAuth complesso:

1. Usa (o crea) un **account Google dedicato**, es. `flynotify.alerts@gmail.com`.
2. Attiva la **Verifica in due passaggi** sull'account (obbligatoria per le App Password): *Account Google → Sicurezza → Verifica in due passaggi*.
3. Crea una **Password per le app**: *Account Google → Sicurezza → Password per le app* → genera una password di 16 caratteri (è diversa dalla password dell'account).
4. Metti le credenziali in `.env` (mai nel repo):

```ini
GMAIL_USER=flynotify.alerts@gmail.com
GMAIL_APP_PASSWORD=xxxxxxxxxxxxxxxx     # la App Password di 16 caratteri
```

5. Invio via SMTP TLS:

```python
import smtplib
from email.mime.text import MIMEText

def send_email(to: str, subject: str, html: str):
    msg = MIMEText(html, "html", "utf-8")
    msg["Subject"], msg["From"], msg["To"] = subject, GMAIL_USER, to
    with smtplib.SMTP("smtp.gmail.com", 587) as s:   # 587 = STARTTLS
        s.starttls()
        s.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        s.send_message(msg)
```

> **Limiti e note:** Gmail gratuito ~**500 invii/giorno** (Workspace ~2.000). La "Password per le app" si revoca in qualsiasi momento dalla stessa pagina. Se il volume cresce oltre i limiti, si passa a un provider transazionale (Resend/SES) **cambiando solo l'Email Service**, senza toccare il resto. Le vecchie "app meno sicure" non sono più supportate: serve App Password (o OAuth2).

---

## 9. Gestione di rate limit e costi

- **Nessuna cache persistente**: ogni ricerca e ogni ciclo chiamano l'API in tempo reale (dati sempre freschi).
- **Cache di esecuzione (in-run)**: dentro un singolo run/richiesta, chiamate identiche vengono fatte una sola volta; alla fine la cache viene scartata. Evita doppioni senza mai servire prezzi vecchi.
- **Backoff esponenziale** su errori 429/5xx del provider.
- **Cadenza per-utente** (`users.poll_interval_hours`): è la leva principale sul numero di chiamate, visto che non c'è risparmio tra un ciclo e l'altro.
- Monitorare il **consumo di quota** come metrica di prodotto: è il principale costo variabile. Tenere un contatore mensile di chiamate e far **auto-rallentare** le cadenze all'avvicinarsi del limite free (vedi §2ter).

---

## 10. Sicurezza e privacy

- Secret in env/secret manager; niente chiavi nel repo. Rientrano qui le chiavi Amadeus, il **token Travelpayouts**, la **Gmail App Password** e la **chiave Gemini**.
- Password con hashing forte (bcrypt/argon2) **oppure** auth passwordless via magic-link.
- JWT a breve durata + refresh token; il token porta il **ruolo**, verificato lato server a ogni richiesta (`require_role`, §5bis). Mai fidarsi del ruolo dichiarato dal client.
- **Autorizzazione per ruolo** su tutti gli endpoint `/admin/*` e `/settings`; le risorse "proprie" filtrate per `user_id` del token.
- Rate limiting sugli endpoint pubblici (`/auth`, `/search`).
- Validazione input (codici IATA, date coerenti) con Pydantic.
- Dati personali minimi (solo email); diritto all'oblio implementato.

---

## 11. Roadmap di sviluppo

**Fase 0 — Fondamenta (settimana 1)**
- Setup repo, Docker, MySQL 8, FastAPI scheletro.
- `FlightClient` Amadeus: OAuth + `flight-offers` + normalizzazione + test.

**Fase 1 — Ricerca (settimana 2)**
- Endpoint `/search` (classica) + `/explore` ("Ovunque") + `/cheapest-dates` ("Mese più economico"), chiamate live con cache di esecuzione.
- `FlightProvider`: `AmadeusClient` (`search_offers`, `inspiration_search`, `cheapest_dates`).
- **Secondo provider Travelpayouts** (copertura low-cost) + Search Service multi-provider con merge/dedup per prezzo minimo.
- Frontend minimale: form con toggle "Ovunque" e "date flessibili"; lista voli (classica), griglia mete ("Ovunque"), calendario date ("Mese più economico"), tutti con drill-down.

**Fase 2 — Alert + Auth (settimane 3-4)**
- Auth (signup/login/verifica email) con **ruoli** (`user`/`admin`/`superadmin`) nel JWT e dependency `require_role`.
- **Seed del primo `superadmin`** (comando CLI) + area **admin**: endpoint `/admin/users`, `/admin/alerts`, `/admin/stats`.
- CRUD alert + `price_history` + **primo check immediato** alla creazione.
- Worker "one-shot" avviato da Windows Task Scheduler + Alert Engine strategia `threshold`; scrittura `run_log` + contatore chiamate.
- Intervallo **per-utente** (`users.poll_interval_hours`) via `/me/preferences`; minimo globale (`min_poll_interval_hours`) via `/settings` (admin).
- **Email via Gmail** (App Password, §8bis): digest (una email per utente) + template + deduplica + `email_log`.

**Fase 3 — Intelligenza (settimana 5)**
- Strategie `drop` e `deal` (Price Analysis) con **delta vs mediana** mostrato in card/email ("−32%").
- Prezzo **totale** (bagaglio/ancillari dove disponibile) per confronti onesti.
- Alert "Ovunque" (`destination = 'ANY'`) con ri-validazione via Flight Offers Search.
- Grafico storico prezzi nel frontend.
- Regole anti-spam complete.

**Fase 4 — Hardening (settimana 6)**
- **Fuso orario e valuta** per utente applicati a date, fasce orarie e prezzi.
- **Osservabilità**: `run_log` (heartbeat del worker: "ha girato?"), `email_log`, contatore quota con **auto-rallentamento** oltre `call_budget_soft_limit`.
- **Auth hardening**: verifica email, reset/magic-link, rate limiting su `/auth` e `/search`.
- **GDPR**: privacy policy, consenso, disiscrizione a un click, retention, cancellazione account.
- **Scheduler affidabile**: assicurarsi che la macchina Windows non vada in sospensione (vedi §6bis); gestione errori e backoff Amadeus.
- Test end-to-end (focus Alert Engine) e deploy.

**Fase 5 — Scheda destinazione (§2quater)**
- Tabella `destinations` (dati curati) + `DestinationGuide` service + endpoint `/guide` (on-demand, memorizzato).
- Integrazione fonti free: OpenTripMap (POI), Ticketmaster (eventi), Open-Meteo (clima); Amadeus Hotel/Transfer dove serve.
- Overview/itinerario con **Gemini** ancorato ai dati; card asincrona nei risultati.

**Fase 6 — Estensioni**
- Terza fonte **Kiwi** (open-jaw / split ticket / self-transfer); notifiche push/Telegram per i cali forti.

---

## 12. Rischi e decisioni aperte

| Rischio / Domanda | Nota |
|---|---|
| Copertura inventario sandbox Amadeus | Validare presto con dati reali; valutare tier produzione |
| **Copertura low-cost** | Risolta con **Travelpayouts** come secondo provider (§2cinque); verificare che copra le tue rotte/origini |
| Travelpayouts ToS/affiliazione | Pensato per affiliati (marker): verificare l'uso come sola fonte dati senza link di prenotazione; eventualmente link affiliato opzionale |
| Freschezza Travelpayouts | Prezzi da catalogo (indicativi): usarlo per scoperta e ri-validare con Amadeus dove serve il prezzo live |
| Riconoscere un "affare" | Serve baseline: Price Analysis + storico + stagionalità; mostrare il delta vs mediana |
| Prezzo totale vs base fare | Confrontare il totale realistico (bagaglio/ancillari), non solo la tariffa base |
| Costi/quota API | Senza cache persistente, restare nel free dipende da cadenza + tetti utenti/alert (§2ter); contatore mensile con auto-rallentamento |
| Freschezza dati "Ovunque"/date | Prezzi da catalogo cache (Amadeus Inspiration/Dates o Travelpayouts): sempre ri-validare con Flight Offers Search |
| Email via Gmail | Semplice e gratis, ma **limite ~500/giorno** e account personale legato al servizio: usare account dedicato; oltre i limiti passare a provider transazionale |
| Scelta auth (password vs magic-link) | Magic-link riduce superficie d'attacco e attrito |
| Sovrapposizione run worker | Un run più lungo dell'intervallo può sovrapporsi: usare "non avviare nuova istanza" del Task Scheduler + `GET_LOCK` su MySQL (vedi §6bis) |
| Niente cache persistente | Scelta voluta (prezzi sempre freschi): il costo è più chiamate API, contenuto da cadenza e tetti |
| Scheda destinazione: molte fonti | Più API (POI/eventi/hotel/meteo/transfer): costruirla **on-demand** e **memorizzarla** (deroga cache circoscritta, §2quater); fonti free dove possibile |
| Contenuti LLM (Gemini) | Rischio "allucinazioni": generare solo **ancorato** ai dati raccolti e memorizzare; fallback a testo curato in `destinations` |

---

## 13. Checklist di completezza (stato)

I punti che prima mancavano sono ora **incorporati nel progetto** (schema, moduli, roadmap). Restano come prerequisiti esterni solo quelli che dipendono da te.

### A. Prerequisiti esterni — **da fare (tu)**
- **Account e chiavi Amadeus** + verifica della **copertura inventario** sulle tratte/origini target (test → produzione). Vedi **Appendice A**.
- **Account Google dedicato** + **App Password** per l'invio email. Vedi **§8bis**.
- **Scheduler sempre attivo**: macchina Windows accesa e non in sospensione (§6bis) → *progettato* (impostazioni Task Scheduler + `run_log`).
- **Il codice**: oggi è tutta progettazione. Serve almeno l'MVP (§1bis) e poi il blocco alert/worker.

### B. Qualità delle notifiche — **progettato**
- **Storico prezzi** (`price_history`): le strategie `drop`/`deal` maturano col tempo; all'inizio affidabile `threshold`.
- **Price Analysis** (Amadeus) per la strategia `deal`.
- **Anti-spam** (cooldown, "solo miglioramenti", dedupe) — §6; da rifinire sul campo.
- **Primo check immediato** alla creazione dell'alert → Alert Service (§4).

### C. Correttezza tecnica — **progettato**
- **Fuso orario** e **valuta** per utente (`users.timezone`, `users.currency`) applicati a date/fasce orarie/prezzi.
- **Normalizzazione aeroporti/città** (MIL/LON…) e deduplica destinazioni (§2bis).
- **Gestione errori e rate limit** Amadeus (backoff/retry, §9).
- **Osservabilità**: `run_log` (heartbeat "ha girato?"), `email_log`, contatore quota con auto-rallentamento (§5, §9).
- **Test** dell'Alert Engine e integrazione sul sandbox → Fase 4.

### D. Prodotto e legale — **progettato (da realizzare in Fase 4)**
- **UI complete**: risultati, gestione alert, preferenze (intervallo/valuta/TZ), area admin, pagine auth.
- **Auth**: verifica email, reset/magic-link, rate limiting su `/auth`.
- **GDPR**: privacy policy, consenso, **disiscrizione** a un click, retention, cancellazione account (`ON DELETE CASCADE`).

> In breve: il disegno è completo. Per partire davvero servono solo **le chiavi Amadeus** (Appendice A) e **l'account Google** (§8bis); poi si scrive il codice a partire dall'MVP.

---

*Prossimo passo suggerito: validare la copertura dell'API Amadeus sulle tratte target e congelare il modello `FlightOffer` normalizzato, da cui dipende tutto il resto.*

---

## Appendice A — Come ottenere le chiavi Amadeus

Le chiavi sono **gratuite** e si ottengono in pochi minuti dal portale Self-Service.

1. Vai su **developers.amadeus.com** e crea un account (*Register*), poi conferma l'email e accedi.
2. Apri **My Self-Service Workspace** (menu in alto a destra, dopo il login).
3. Clicca **Create New App**: dai un nome (es. `flynotify`) e conferma.
4. L'app ti mostra due valori — copiali:
   - **API Key** → è il `client_id` (`AMADEUS_CLIENT_ID`)
   - **API Secret** → è il `client_secret` (`AMADEUS_CLIENT_SECRET`)
5. Mettili nel `.env` del progetto (mai nel repo):

```ini
AMADEUS_CLIENT_ID=la_tua_api_key
AMADEUS_CLIENT_SECRET=il_tuo_api_secret
AMADEUS_BASE_URL=https://test.api.amadeus.com   # TEST (gratis). In produzione: https://api.amadeus.com
```

6. Ottieni il token OAuth2 (da riusare ~30 min) e chiama le API:

```bash
curl -X POST "https://test.api.amadeus.com/v1/security/oauth2/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=client_credentials&client_id=$AMADEUS_CLIENT_ID&client_secret=$AMADEUS_CLIENT_SECRET"
# → { "access_token": "...", "expires_in": 1799, ... }
```

### Test vs Produzione
- **Test** (default): gratuito, ma **dati/inventario ridotti** e non sempre reali → perfetto per sviluppare, non per prezzi definitivi.
- **Produzione**: nel portale, apri l'app e scegli **Move to Production** (richiede di inserire i dati di fatturazione; alcune API richiedono una breve approvazione). C'è una **quota mensile gratuita** per API, poi si paga a consumo. Cambia solo `AMADEUS_BASE_URL`.

### Limiti da ricordare
- Rate limit indicativo in test: ~**10 richieste/secondo** e quote mensili per endpoint → rispettare backoff e il contatore chiamate (§9).
- Gli endpoint "Ovunque"/date (*Inspiration*, *Cheapest Date*) hanno **copertura limitata** in test: verifica presto le tue origini (es. MXP/BGY/LIN).

---

## Appendice B — Come ottenere le chiavi Travelpayouts

Anche queste sono **gratuite**; Travelpayouts è un network affiliato di Aviasales.

1. Vai su **travelpayouts.com** e registrati (*Sign up*), poi conferma l'email e accedi.
2. Dalla dashboard apri **Developers / API** (a volte sotto *Tools → API* o *Flight Data API*).
3. Copia i due valori:
   - **Token API** → `TRAVELPAYOUTS_TOKEN`
   - **Marker** (id affiliato, associato al tuo account) → `TRAVELPAYOUTS_MARKER`
4. Mettili nel `.env`:

```ini
TRAVELPAYOUTS_TOKEN=il_tuo_token
TRAVELPAYOUTS_MARKER=il_tuo_marker
TRAVELPAYOUTS_BASE_URL=https://api.travelpayouts.com
```

5. Esempio di chiamata (prezzi per date su una tratta):

```bash
curl "https://api.travelpayouts.com/aviasales/v3/prices_for_dates\
?origin=MIL&destination=LON&departure_at=2026-11&currency=eur&sorting=price\
&token=$TRAVELPAYOUTS_TOKEN&marker=$TRAVELPAYOUTS_MARKER"
```

### Note
- **Gratuito e senza OAuth**: basta passare `token` (e `marker`) come parametri; nessun flusso di login come Amadeus.
- **Dati indicativi** (catalogo/cache): ottimi per scoprire le offerte low-cost, da ri-validare con Amadeus per il prezzo live.
- **Marker/affiliazione**: il network è pensato per gli affiliati; se usi solo i dati senza link di prenotazione, verifica i loro termini (vedi §12).
