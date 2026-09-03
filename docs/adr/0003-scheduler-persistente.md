# 0003 — Scheduler persistente in processo

- **Stato:** Accettato
- **Data:** 2026-09-03
- **Attuazione:** milestone `v0.2.0`

## Contesto

Il sistema non ha alcuno scheduler lato server. Il conto alla rovescia dei timer
vive in un `setInterval` nel browser (`index.html`, `startTimerTick`): chiusa la
scheda, nessun timer suona. I promemoria stanno peggio — vengono scritti in
`data/reminders.json` e nessun processo li rilegge mai, quindi non si attivano
in nessuna circostanza, mentre l'assistente ha risposto «ti ricordero'».

Questo blocca anche tutto cio' che verra' dopo: automazioni a orario, briefing
mattutino, check-in di presenza, promemoria di manutenzione.

## Decisione

**APScheduler** con `AsyncIOScheduler`, avviato nel ciclo di vita
dell'applicazione FastAPI, e job store `SQLAlchemyJobStore` sullo stesso
database dell'ADR 0002.

Persistente significa che i job sopravvivono al riavvio del servizio: e' il
requisito, non un dettaglio implementativo. Un promemoria per le 17:30 deve
scattare anche se il server e' stato riavviato alle 17:00.

Alla scadenza il job pubblica un evento interno; i canali in ascolto (interfaccia
web via WebSocket, notifica push dalla `0.4.0`, altoparlante Echo tramite
`notify.alexa_media`) lo consegnano. Lo scheduler non sa come si avvisa
l'utente: e' responsabilita' dei canali.

## Alternative considerate

**Un task asyncio proprio con `asyncio.sleep`.** Nessuna dipendenza in piu', ma
va riscritto tutto cio' che APScheduler gia' fa bene: persistenza, ricalcolo
delle scadenze dopo un riavvio, job persi mentre il servizio era fermo, espressioni
ricorrenti. E' lavoro che non aggiunge valore al progetto.

**Delegare le automazioni a Home Assistant.** Ha uno scheduler eccellente, ma
significherebbe che Shinra non puo' programmare nulla di proprio e che ogni
promemoria diventa un'automazione HA da creare via API. Si perde il controllo
sul comportamento e si vincola una funzione base a un servizio esterno che
potrebbe essere spento.

**Celery o un job runner esterno.** Richiede un broker e un processo separato.
Per una casa e' complessita' senza contropartita.

## Conseguenze

**Positive.** Timer e promemoria funzionano davvero, indipendenti dal browser.
Nasce l'infrastruttura su cui poggiano tutte le automazioni della `0.4.0`.

**Negative.** Lo scheduler vive nello stesso processo del server web: un job
lento blocca il ciclo di eventi. I job devono restare brevi e delegare il lavoro
pesante.

**Da definire.** Il comportamento per i job scaduti mentre il servizio era
fermo: `misfire_grace_time` va scelto per tipo di job — un promemoria di
mezz'ora fa va probabilmente ancora consegnato, un timer della pasta no.
