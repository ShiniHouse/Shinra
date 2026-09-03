# 0002 — SQLite al posto della persistenza su file JSON

- **Stato:** Accettato
- **Data:** 2026-09-03
- **Attuazione:** milestone `v0.2.0`

## Contesto

Tutto lo stato del sistema vive in sei file JSON in `data/`, letti e riscritti
integralmente a ogni modifica (`core/data_store.py`, `core/timer_engine.py`).

Ne derivano quattro problemi concreti:

1. **Scritture concorrenti.** La sequenza e' leggi-modifica-riscrivi su file
   aperto in `"w"`, senza lock. Dashboard ed Echo attivi insieme — scenario
   normale — possono perdere una modifica. Un'interruzione a meta' scrittura
   lascia un file troncato che all'avvio successivo viene scartato in silenzio
   restituendo una lista vuota: perdita totale dei dati senza alcun errore.
2. **Nessuno storico.** Non e' possibile sapere cosa e' successo ieri. Questo
   blocca il registro delle azioni, la spiegabilita' e il diario della casa.
3. **Nessuna query.** Ogni filtro e' un ciclo Python sull'intero file.
4. **Nessuna migrazione.** Un campo nuovo in un modello rompe i file esistenti
   senza che nulla se ne accorga.

## Decisione

Migrare a **SQLite tramite SQLAlchemy 2.x**, con **Alembic** per le migrazioni.
Uno script di migrazione una tantum importa i JSON esistenti. I file JSON
restano leggibili come formato di esportazione, non come archivio primario.

## Alternative considerate

**Restare su JSON aggiungendo lock e scrittura atomica** (`os.replace`).
Risolverebbe il punto 1 e nessuno degli altri tre. Lo storico e' un requisito di
tre funzioni della roadmap: rimandare significa migrare comunque, piu' tardi e
con piu' dati da spostare.

**PostgreSQL.** Sovradimensionato per una casa: aggiunge un servizio da
installare, configurare e mantenere. SQLite e' un file, non ha server, e regge
ordini di grandezza piu' di quanto un'abitazione produca.

**TinyDB o simili.** Mantengono la semplicita' dei file ma non offrono
transazioni reali ne' migrazioni, cioe' i due motivi per cui si migra.

## Conseguenze

**Positive.** Transazioni, nessuna perdita per concorrenza, storico
interrogabile, migrazioni versionate. Sblocca registro azioni, spiegabilita',
diario della casa e analisi energetica.

**Negative.** Due dipendenze in piu' e un livello di astrazione da imparare.
Ispezionare i dati non e' piu' un `cat` ma richiede un client SQL.

**Rischio.** La migrazione deve essere idonea a fallire senza perdite: lo script
scrive su un database nuovo e non tocca i JSON originali, che restano come
backup finche' non si verifica l'esito.
