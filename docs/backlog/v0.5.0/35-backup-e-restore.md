---
title: "feat(dati): backup, ripristino e versione di schema"
issue: 35
milestone: "v0.5.0"
labels: ["tipo: funzione", "area: infra"]
---

## Contesto

Nessun modo di esportare la configurazione, nessuna versione di schema, nessuna
procedura di ripristino. Chi ha passato un'ora a configurare alias e routine non
ha modo di metterle al sicuro ne' di spostarle su un'altra macchina.

## Cosa fare

- [x] Esportazione completa in un unico archivio: configurazione, conoscenza, alias, modalita', utenti — **con i segreti esclusi**
- [x] Importazione con validazione e anteprima di cosa verra' sovrascritto
- [x] Versione di schema nell'esportazione, con migrazione automatica dalle versioni precedenti
- [ ] Backup automatico programmato tramite lo scheduler, con rotazione
- [x] Comando da riga di comando per backup e ripristino

## Criteri di accettazione

- [x] Un'esportazione ripristinata su un'installazione pulita riproduce la configurazione
- [x] L'esportazione non contiene token ne' PIN
- [x] L'importazione di un backup di una versione precedente funziona con migrazione automatica

## A che punto siamo

Fatto tutto tranne il **backup automatico programmato**, che resta l'unica
casella aperta e vale una PR sua: tocca lo scheduler e la rotazione, che sono
un problema diverso da «scrivere e rileggere un archivio».

Quello che c'e':

- `src/shinra/services/salvataggio.py` — un archivio JSON unico, che dichiara
  di che schema e', da che Shinra viene e quando e' stato scritto.
- `scripts/salvataggio.py` — `salva`, `guarda`, `ripristina --conferma`.
- Lo **schema 0**: la cartella di file JSON che `scripts/esporta_json.py`
  scrive dalla v0.2.0, e che esiste su disco in casa di chi ha seguito quel
  consiglio. Rientra migrata — i timer di allora si lasciano cadere, la
  colonna `pin` si toglie entrando.

Due cose trovate per strada:

- `scripts/esporta_json.py` scriveva `users.json` con dentro la colonna `pin`,
  cioe' l'impronta del PIN di ogni persona di casa, in chiaro, in una cartella
  che nasce per essere copiata su una chiavetta. Sei cifre dietro una funzione
  di hash si ritrovano in pochi secondi. Adesso chiede a `salvataggio` cos'e'
  un segreto, invece di tenerne una seconda idea.
- Il ripristino **non** svuota le tabelle che l'archivio non porta: un
  salvataggio scritto da una versione che non conosceva le modalita' non deve
  cancellare le modalita' di chi lo rilegge.

La guardia che tiene in piedi le altre e' `test_ogni_tabella_e_stata_decisa`:
una tabella nuova non puo' finire nell'archivio — ne' restarne fuori — senza
che qualcuno l'abbia scritto in `TABELLE` o in `FUORI`, col perche'.
