---
title: "feat(audit): registro delle azioni eseguite in casa"
issue: 15
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

- [x] Tabella del registro: momento, utente, canale, intento, tool, parametri, esito, durata, identificativo di correlazione
- [x] Registrare ogni esecuzione di tool, ogni attivazione di modalita', ogni accesso e ogni modifica alle impostazioni
      (l'aggancio e' in `execute_tool`, il passaggio obbligato di ogni
      azione: un tool nuovo risulta tracciato senza che nessuno se ne
      debba ricordare. L'attivazione di modalita' e' essa stessa un tool.)
- [x] Identificativo di correlazione propagato dalla richiesta fino ai tool
- [x] Log applicativo strutturato in JSON, con rotazione
- [x] Endpoint di consultazione con filtri, riservato al ruolo `admin`
- [x] Politica di conservazione configurabile
- [x] **Mai registrare segreti**: token e PIN vanno oscurati

## Criteri di accettazione

- [x] Ogni azione domotica produce una voce nel registro
- [x] Il registro risponde a «chi ha acceso cosa e quando»
- [x] Nessun segreto compare nel registro
- [x] Un utente non amministratore non puo' consultarlo
