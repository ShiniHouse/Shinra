---
title: "feat(dati): backup, ripristino e versione di schema"
milestone: "v0.5.0"
labels: ["tipo: funzione", "area: infra"]
---

## Contesto

Nessun modo di esportare la configurazione, nessuna versione di schema, nessuna
procedura di ripristino. Chi ha passato un'ora a configurare alias e routine non
ha modo di metterle al sicuro ne' di spostarle su un'altra macchina.

## Cosa fare

- [ ] Esportazione completa in un unico archivio: configurazione, conoscenza, alias, modalita', utenti — **con i segreti esclusi**
- [ ] Importazione con validazione e anteprima di cosa verra' sovrascritto
- [ ] Versione di schema nell'esportazione, con migrazione automatica dalle versioni precedenti
- [ ] Backup automatico programmato tramite lo scheduler, con rotazione
- [ ] Comando da riga di comando per backup e ripristino

## Criteri di accettazione

- [ ] Un'esportazione ripristinata su un'installazione pulita riproduce la configurazione
- [ ] L'esportazione non contiene token ne' PIN
- [ ] L'importazione di un backup di una versione precedente funziona con migrazione automatica
