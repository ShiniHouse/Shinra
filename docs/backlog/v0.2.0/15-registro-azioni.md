---
title: "feat(audit): registro delle azioni eseguite in casa"
milestone: "v0.2.0"
labels: ["tipo: funzione", "area: sicurezza", "area: infra"]
---

## Contesto

Il sistema comanda luci, prese e clima — e presto serrature e allarme — senza
tenere alcuna traccia. Il logging va solo su standard output, senza rotazione e
senza identificativo di correlazione.

Non e' possibile rispondere a «chi ha spento il riscaldamento alle 3 di notte?».
Per un sistema che controlla una casa e' una lacuna di sicurezza, oltre che il
prerequisito della funzione di spiegabilita' prevista dopo la 1.0.0.

## Cosa fare

- [ ] Tabella del registro: momento, utente, canale, intento, tool, parametri, esito, durata, identificativo di correlazione
- [ ] Registrare ogni esecuzione di tool, ogni attivazione di modalita', ogni accesso e ogni modifica alle impostazioni
- [ ] Identificativo di correlazione propagato dalla richiesta fino ai tool
- [ ] Log applicativo strutturato in JSON, con rotazione
- [ ] Endpoint di consultazione con filtri, riservato al ruolo `admin`
- [ ] Politica di conservazione configurabile
- [ ] **Mai registrare segreti**: token e PIN vanno oscurati

## Criteri di accettazione

- [ ] Ogni azione domotica produce una voce nel registro
- [ ] Il registro risponde a «chi ha acceso cosa e quando»
- [ ] Nessun segreto compare nel registro
- [ ] Un utente non amministratore non puo' consultarlo
