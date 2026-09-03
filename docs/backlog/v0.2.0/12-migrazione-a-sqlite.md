---
title: "refactor(persistenza): SQLite e SQLAlchemy al posto dei file JSON"
milestone: "v0.2.0"
labels: ["tipo: attivita'", "area: infra", "gravita': alta"]
riferimento: "REL-05 — ADR 0002"
---

## Contesto

Tutto lo stato vive in sei file JSON letti e riscritti integralmente a ogni
modifica. Ogni salvataggio e' una sequenza leggi-modifica-riscrivi su file
aperto in `"w"`, senza lock e senza sostituzione atomica.

Due richieste in parallelo — plausibili con dashboard ed Echo attivi insieme —
perdono una modifica. Se il processo si interrompe a meta' scrittura, resta un
file troncato che l'avvio successivo scarta in silenzio restituendo una lista
vuota: **perdita totale dei dati senza alcun errore visibile.**

Manca inoltre qualunque storico, il che blocca registro azioni, spiegabilita' e
diario della casa.

Le motivazioni complete e le alternative scartate sono in
[ADR 0002](../../adr/0002-sqlite-al-posto-dei-file-json.md).

## Cosa fare

- [ ] SQLAlchemy 2.x in modalita' asincrona, con SQLite in `data/shinra.db`
- [ ] Alembic per le migrazioni di schema
- [ ] Modelli: utenti, conoscenza, alias, modalita', fonti, timer, promemoria, registro azioni, eventi
- [ ] Livello repository che sostituisce `DataStore`, `UserManager` e la parte di persistenza di `TimerEngine`, mantenendo le firme pubbliche dove possibile
- [ ] Script di migrazione una tantum dai JSON esistenti — **scrive su un database nuovo e non tocca i file originali**, che restano come backup finche' non si verifica l'esito
- [ ] Abilitare la modalita' WAL di SQLite per la concorrenza in lettura
- [ ] Esportazione in JSON mantenuta come formato di backup, non come archivio primario

## Criteri di accettazione

- [ ] La migrazione importa senza perdita i dati esistenti, verificata per conteggio su ogni entita'
- [ ] Cento scritture concorrenti non perdono alcun record
- [ ] Interrompere il processo durante una scrittura non corrompe il database
- [ ] Tutte le funzioni esistenti operano invariate dopo la migrazione
- [ ] I file JSON originali sono ancora presenti e leggibili dopo la migrazione
