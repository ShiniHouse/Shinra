# 0005 — SQLAlchemy sincrono, non asincrono

- **Stato:** Accettato
- **Data:** 2026-09-04
- **Attuazione:** milestone `v0.2.0`, issue #12
- **Modifica:** precisa l'ADR 0002, che sceglieva SQLite e SQLAlchemy senza
  dire se in modalita' sincrona o asincrona. La scheda della issue #12
  diceva «modalita' asincrona»: questa decisione la sostituisce.

## Contesto

Shinra e' un'applicazione FastAPI, quindi asincrona. La scelta naturale
sembrerebbe SQLAlchemy in modalita' asincrona con `aiosqlite`.

Due fatti la rendono meno naturale di quanto sembri.

**Il primo.** `aiosqlite` non rende SQLite non bloccante: SQLite e' una
libreria C sincrona, e `aiosqlite` la esegue in un thread di servizio
inoltrandole le chiamate. Il blocco non sparisce, cambia thread. FastAPI fa
gia' la stessa cosa, da solo, con le funzioni sincrone. Il guadagno reale su
un database locale, dove una query dura decine di microsecondi, e' nullo.

**Il secondo, che pesa di piu'.** Rendere asincrono l'accesso ai dati vuol
dire rendere asincrone tutte le funzioni che lo usano. `autenticazione_attiva()`
legge l'anagrafica ed e' chiamata da `utente_corrente()`, da
`richiedi_autenticazione()`, dal WebSocket e dal gestore della skill Alexa —
tutte sincrone. La migrazione a SQLite tocca gia' la persistenza di tre
moduli e i dati veri di una casa in funzione: aggiungerci la conversione ad
async di mezzo albero delle chiamate significa cambiare due cose insieme e,
quando qualcosa non torna, non sapere quale delle due.

## Decisione

SQLAlchemy 2.x **sincrono**, con `sqlite3` e `check_same_thread=False`.
FastAPI esegue le dipendenze sincrone nel proprio pool di thread; le
transazioni durano microsecondi e non tengono occupato il ciclo di eventi in
modo percepibile.

La concorrenza fra scrittori e' governata da SQLite: modalita' WAL, cosi'
chi legge non blocca chi scrive, e `busy_timeout` a cinque secondi, cosi'
chi trova occupato aspetta invece di fallire. Sono queste due impostazioni a
risolvere il problema della issue #12, non il modello di concorrenza di
Python: senza `busy_timeout`, cento scritture in parallelo falliscono con
«database is locked» tanto in sincrono quanto in asincrono. C'e' un test che
lo dimostra, e che fallisce se qualcuno toglie il pragma.

## Alternative considerate

**SQLAlchemy asincrono con aiosqlite.** Il costo e' la conversione ad async
di tutta la catena delle chiamate; il beneficio, su un database locale in
una casa, non e' misurabile. Resta la scelta giusta se un giorno si passasse
a PostgreSQL su un'altra macchina, dove la latenza di rete e' reale: allora
il costo si paga per qualcosa.

## Conseguenze

**Positive.** La migrazione cambia dove stanno i dati e nient'altro: le
firme delle funzioni restano quelle di prima, e cio' che si rompe si rompe
per un motivo solo. Un livello di astrazione in meno da spiegare.

**Negative.** Se un giorno il database diventasse remoto, andrebbe rifatto
il lavoro qui evitato. E' un rischio che si accetta: PostgreSQL e' gia'
stato scartato nell'ADR 0002 come sovradimensionato per una casa.
